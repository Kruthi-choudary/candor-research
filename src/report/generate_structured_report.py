import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from src.common.config import load_pipeline_config
from src.common.errors import PipelineError
from src.report.generate_report import (
    COMPANIES, SENTIMENT_DIR, ENV_PATH, MODEL_NAME, TOP_K_QUOTES,
    load_scored_segments, sentiment_distribution, top_quotes,
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

Positively-scored source quotes (use only these for positive claims):
{quote_lines(positive_quotes)}

Negatively-scored source quotes (use only these for negative claims):
{quote_lines(negative_quotes)}{prior_block}

For each source quote above, produce one claim object. Each claim's citation.timestamp_sec and citation.source_text MUST be copied exactly from one of the quotes listed above — do not invent, paraphrase, or combine quotes. Then write a short overall_summary (2-3 sentences) synthesizing the claims and the sentiment distribution."""


def generate_structured(ticker: str, quarter: str, client: Groq, prior_context: list = None) -> dict:
    segments = load_scored_segments(ticker, quarter)
    distribution = sentiment_distribution(segments)
    positive_quotes = top_quotes(segments, "positive", TOP_K_QUOTES)
    negative_quotes = top_quotes(segments, "negative", TOP_K_QUOTES)

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
        return json.loads(response.choices[0].message.content)
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
