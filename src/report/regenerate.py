"""Stage one fresh report from saved sentiment/transcript outputs, without audio.

Writes one candidate bundle only. It does not publish reports, rewrite the original
benchmark experiment, or claim that citation matches establish claim correctness.
"""
import argparse
import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

from src.common.errors import PipelineError
from src.common.manifest import resolve_call
from src.common.schema import build_report
from src.eval.check_citations_structured import evaluate_report
from src.report.generate_report import sentiment_distribution


def regenerate_candidate(ticker: str, quarter: str, client, *, include_history: bool = True) -> dict:
    # Keep optional generation dependencies out of read-only imports and tests.
    from src.report.generate_structured_report import generate_structured
    from src.rag.build_index import query_prior_quarters

    call = resolve_call(ticker, quarter=quarter)
    existing = json.loads(call.pipeline_output_path.read_text())
    segments = json.loads(call.sentiment_path.read_text())["segments"]
    transcript = json.loads(call.transcript_path.read_text())["segments"]
    # The generation input must remain traceable to the actual transcript served
    # by the API, including unscored neighbours used to complete sentences.
    source = lambda rows: [(s["start"], s["end"], s["text"]) for s in rows]
    if source(segments) != source(transcript):
        raise PipelineError("Saved sentiment segments differ from the source transcript; regenerate the upstream data first.")
    if not any(s.get("sentiment") for s in segments):
        raise PipelineError("No scored transcript segments are available.")

    started = time.monotonic()
    context = query_prior_quarters(call.ticker, call.quarter) if include_history else []
    # Never pass cached prior context from the old report to generation.
    claims = generate_structured(call.ticker, call.quarter, client, prior_context=context)
    evaluation = evaluate_report(call.ticker, call.quarter, claims, segments)
    if evaluation["verified"] != evaluation["total_citations"]:
        raise PipelineError("Candidate contains unmatched citations; no served files were changed.")
    report = build_report(
        call, claims, sentiment_distribution([s for s in segments if s.get("sentiment")]),
        evaluation, existing["audio_features_summary"], context,
        {"regeneration_sec": round(time.monotonic() - started, 2)},
    )
    report["regeneration"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": "saved_transcript_and_sentiment",
        "audio_features": "reused_from_previous_report_not_recomputed",
        "historical_context": ("retrieved" if context else "none_returned") if include_history else "explicitly_omitted",
        "claim_support_review": "pending",
        "provenance": {
            "dataset_scope": [{"ticker": call.ticker, "quarter": call.quarter}],
            "generation": claims.get("generation_provenance"),
            "input_sha256": {
                str(path.relative_to(Path(__file__).resolve().parents[2])) if path.is_relative_to(Path(__file__).resolve().parents[2]) else path.name:
                    hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (call.transcript_path, call.sentiment_path, call.pipeline_output_path)
            },
        },
    }
    return {
        "structured_claims": claims,
        "citation_evaluation": evaluation,
        "report": report,
        "review": {
            "status": "pending",
            "previous_context_quarters": [c["quarter"] for c in existing.get("prior_quarter_context_used", [])],
            "new_context_quarters": [c["quarter"] for c in context],
            "note": "Exact citation matches do not establish that the generated claims are supported. Review claims and qualifications before publishing.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Stage one regenerated report without audio or changing served outputs.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--quarter", required=True)
    parser.add_argument("--output", required=True, type=Path, help="New candidate JSON file; existing files are never overwritten")
    parser.add_argument("--without-history", action="store_true", help="Generate from current-call evidence only; do not initialize vector retrieval")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new candidate path.")

    from dotenv import load_dotenv
    from groq import Groq
    from src.report.generate_report import ENV_PATH

    load_dotenv(ENV_PATH)
    try:
        # Bounded transport wait; don't conceal repeated provider failures.
        client = Groq(timeout=30.0, max_retries=0)
        candidate = regenerate_candidate(args.ticker, args.quarter, client, include_history=not args.without_history)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            json.dump(candidate, stream, indent=2)
    except (PipelineError, OSError, ValueError) as exc:
        raise SystemExit(f"Regeneration failed; served reports unchanged: {exc}") from exc
    evaluation = candidate["citation_evaluation"]
    print(f"Candidate saved to {args.output}")
    print(f"Citation matches: {evaluation['verified']}/{evaluation['total_citations']}; claim-support review pending.")
    print("Served reports, bundled demo and archived benchmarks were not changed.")


if __name__ == "__main__":
    main()
