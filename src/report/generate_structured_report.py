import json
import hashlib
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

def response_schema(source_ids: list[str]) -> dict:
    """The model selects a current-call passage; Python copies its exact citation."""
    return {
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
                                "source_id": {"type": "string", "enum": source_ids},
                            },
                            "required": ["claim", "sentiment", "source_id"],
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

    def quote_lines(quotes, first_id):
        return "\n".join(f'- P{index} (timestamp_sec={int(q["start"])}): "{q["text"].strip()}"'
                         for index, q in enumerate(quotes, first_id)) or "(none provided)"

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
{quote_lines(positive_quotes, 1)}

Source passages selected around negatively-scored transcript segments:
{quote_lines(negative_quotes, len(positive_quotes) + 1)}{prior_block}

The selection groups describe the seed segment's FinBERT score, not the sentiment of the complete passage or the claim. Read the whole passage, including qualifications and negations; assign each claim's sentiment from its meaning, independently of the selection group. Punctuation-based grouping does not establish speaker identity or guarantee complete context.

Choose at most six clear, material claims, with at most one claim from any source passage. Omit passages that are ambiguous or insufficient; never complete a thought by guessing. For each claim return only the ID of its supporting current-call passage as source_id; never cite prior-quarter context. The application will attach the exact passage text and timestamp. Preserve the exact metric scope, numeric ranges, comparison periods and qualifications. A percentage level described as "down year over year" is not a decrease of that many percentage points; if the wording is unclear, omit the claim. Do not turn a segment metric into total-company revenue or infer a cause not stated in the cited passage. Prior context must not introduce facts absent from the cited current-call passage. Then write a short overall_summary (2-3 sentences) synthesizing only the supported claims and the sentiment distribution. If no passages support a claim, return an empty claims array and explain the limitation. Return one JSON object with exactly the required claims and overall_summary fields; every element of claims must be a complete claim object, never a string, placeholder or null."""


def generate_structured(ticker: str, quarter: str, client: Groq, prior_context: list = None) -> dict:
    segments = load_segments(ticker, quarter)
    scored = [s for s in segments if s.get("sentiment")]
    if not scored:
        raise PipelineError(f"No scored segments for {ticker} {quarter}.")
    distribution = sentiment_distribution(scored)
    positive_quotes, negative_quotes = select_evidence_passages(segments, TOP_K_QUOTES)
    passages = positive_quotes + negative_quotes
    if not passages:
        raise PipelineError(f"No complete current-call passages for {ticker} {quarter}.")
    by_id = {f"P{index}": passage for index, passage in enumerate(passages, 1)}

    prompt = build_structured_prompt(ticker, quarter, distribution, positive_quotes, negative_quotes, prior_context)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=response_schema(list(by_id)),
            max_tokens=MAX_TOKENS,
        )
    except Exception as e:
        raise PipelineError(f"Groq API call failed for {ticker} {quarter}: {e}") from e

    try:
        result = json.loads(response.choices[0].message.content)
        used = set()
        for claim in result["claims"]:
            source_id = claim.pop("source_id", None)
            if source_id not in by_id or source_id in used:
                raise PipelineError(f"Generated source ID is unknown or repeated for {ticker} {quarter}: {source_id}.")
            used.add(source_id)
            passage = by_id[source_id]
            claim["citation"] = {"timestamp_sec": int(passage["start"]), "source_text": passage["text"].strip()}
        result["evidence_policy"] = EVIDENCE_POLICY
        result["generation_provenance"] = {
            "model": MODEL_NAME,
            "max_tokens": MAX_TOKENS,
            "response_id": getattr(response, "id", None),
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "input_segments_sha256": hashlib.sha256(json.dumps(segments, sort_keys=True).encode()).hexdigest(),
            "selection": {"policy": EVIDENCE_POLICY, "top_k_per_seed_label": TOP_K_QUOTES,
                          "citation_binding": "source_id_to_exact_selected_passage_v1"},
        }
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
