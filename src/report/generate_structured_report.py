import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from src.common.config import load_pipeline_config
from src.common.errors import PipelineError
from src.report.evidence import EVIDENCE_POLICY, select_evidence_passages
from src.report.generate_report import (
    COMPANIES, SENTIMENT_DIR, ENV_PATH, MODEL_NAME, TOP_K_QUOTES,
    load_segments, sentiment_distribution,
)

_cfg = load_pipeline_config()

RUN_LABEL = "structured_citations_v1"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / f"reports_{RUN_LABEL}"
MAX_TOKENS = _cfg["generation"]["max_tokens_structured"]

CITATION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "earnings_call_claims",
        "schema": {
            "type": "object",
            "properties": {
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "claim": {"type": "string", "description": "A single factual or analytical statement about the call."},
                            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                            "citation": {
                                "type": "object",
                                "properties": {
                                    "timestamp_sec": {"type": "integer", "description": "Must be copied exactly from one of the provided source quotes' timestamp."},
                                    "source_text": {"type": "string", "description": "Must be copied verbatim from the matching provided source quote, no paraphrasing."},
                                },
                                "required": ["timestamp_sec", "source_text"],
                                "additionalProperties": False,
                            },
                        },
                        "required": ["claim", "sentiment", "citation"],
                        "additionalProperties": False,
                    },
                },
                "overall_summary": {"type": "string"},
            },
            "required": ["claims", "overall_summary"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


def build_structured_prompt(ticker: str, quarter: str, distribution: dict, positive_quotes: list, negative_quotes: list,
                             prior_context: list = None) -> str:
    company = COMPANIES.get(ticker, {}).get("name", ticker)

    def quote_lines(quotes):
        return "\n".join(f'- timestamp_sec={int(q["start"])}: "{q["text"].strip()}"' for q in quotes) or "(none provided)"

    prior_block = ""
    if prior_context:
        lines = "\n".join(f'- {c["quarter"]}: "{c["text"].strip()}"' for c in prior_context)
        prior_block = f"""

Context from prior-quarter calls for the same company (for cross-quarter comparison only —
do not cite these with a timestamp, they belong to a different call):
{lines}"""

    return f"""You are extracting grounded claims from an earnings call for an investor brief.

Company: {company} ({ticker})
Quarter: {quarter}
FinBERT sentiment distribution: {distribution['positive']}% positive, {distribution['negative']}% negative, {distribution['neutral']}% neutral.

Source passages selected around positively-scored transcript segments:
{quote_lines(positive_quotes)}

Source passages selected around negatively-scored transcript segments:
{quote_lines(negative_quotes)}{prior_block}

The selection groups describe the seed segment's FinBERT score, not the sentiment of the complete passage or the claim. Read the whole passage, including qualifications and negations; assign each claim's sentiment from its meaning, independently of the selection group. Punctuation-based grouping does not establish speaker identity or guarantee complete context.

For each source passage that supports a clear claim, produce at most one claim object. Omit passages that are ambiguous or insufficient; never complete a thought by guessing. Each claim's citation.timestamp_sec and citation.source_text MUST be copied exactly from one of the passages listed above — do not invent, paraphrase, shorten, or combine passages. Preserve numeric ranges and qualifications in the claim. Prior context must not introduce facts absent from the cited current-call passage. Then write a short overall_summary (2-3 sentences) synthesizing the supported claims and the sentiment distribution. If no passages support a claim, return an empty claims array and explain the limitation."""


def generate_structured(ticker: str, quarter: str, client: Groq, prior_context: list = None) -> dict:
    segments = load_segments(ticker, quarter)
    scored = [s for s in segments if s.get("sentiment")]
    if not scored:
        raise PipelineError(f"No scored segments for {ticker} {quarter}.")
    distribution = sentiment_distribution(scored)
    positive_quotes, negative_quotes = select_evidence_passages(segments, TOP_K_QUOTES)

    prompt = build_structured_prompt(ticker, quarter, distribution, positive_quotes, negative_quotes, prior_context)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=CITATION_SCHEMA,
            max_tokens=MAX_TOKENS,
        )
    except Exception as e:
        raise PipelineError(f"Groq API call failed for {ticker} {quarter}: {e}") from e

    try:
        result = json.loads(response.choices[0].message.content)
        allowed = {(int(q["start"]), q["text"].strip()) for q in positive_quotes + negative_quotes}
        for claim in result["claims"]:
            citation = claim["citation"]
            if (citation["timestamp_sec"], citation["source_text"].strip()) not in allowed:
                raise PipelineError(
                    f"Generated citation is not an exact provided passage for {ticker} {quarter}."
                )
        result["evidence_policy"] = EVIDENCE_POLICY
        return result
    except json.JSONDecodeError as e:
        raise PipelineError(f"LLM returned malformed JSON for {ticker} {quarter}: {e}") from e


def run():
    load_dotenv(ENV_PATH)
    client = Groq()

    for ticker_dir in sorted(SENTIMENT_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name
        out_dir = OUTPUT_DIR / ticker
        out_dir.mkdir(parents=True, exist_ok=True)

        for sentiment_path in sorted(ticker_dir.glob("*.json")):
            quarter = sentiment_path.stem
            out_path = out_dir / f"{quarter}.json"
            if out_path.exists():
                print(f"{ticker} {quarter}: already generated, skipping")
                continue

            print(f"{ticker} {quarter}: generating structured claims...")
            result = generate_structured(ticker, quarter, client)
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f"  -> {out_path} ({len(result['claims'])} claims)")


if __name__ == "__main__":
    run()
