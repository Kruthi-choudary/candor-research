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
from src.common.manifest import resolve_call, ROOT
from src.common.schema import build_report
from src.eval.check_citations_structured import evaluate_report
from src.report.generate_report import sentiment_distribution


def regenerate_candidate(ticker: str, quarter: str, client, *, include_history: bool = True) -> dict:
    # Keep optional generation dependencies out of read-only imports and tests.
    from src.report.generate_structured_report import generate_structured
    from src.rag.build_index import current_call_queries, query_prior_quarters

    call = resolve_call(ticker, quarter=quarter)
    watched = {
        path: path.read_bytes() for path in (
            call.transcript_path, call.sentiment_path, call.pipeline_output_path,
            ROOT / "data/processed/call_dates.json", ROOT / "data/processed/call_date_sources.json",
            ROOT / "config/pipeline.yaml", ROOT / "config/companies.yaml",
            ROOT / "src/report/regenerate.py", ROOT / "src/report/evidence.py",
            ROOT / "src/report/generate_structured_report.py", ROOT / "src/rag/build_index.py",
        )
    }
    local_config = ROOT / "config/pipeline.local.yaml"
    if local_config.exists():
        watched[local_config] = local_config.read_bytes()
    existing = json.loads(watched[call.pipeline_output_path])
    segments = json.loads(watched[call.sentiment_path])["segments"]
    transcript = json.loads(watched[call.transcript_path])["segments"]
    # The generation input must remain traceable to the actual transcript served
    # by the API, including unscored neighbours used to complete sentences.
    source = lambda rows: [(s["start"], s["end"], s["text"]) for s in rows]
    if source(segments) != source(transcript):
        raise PipelineError("Saved sentiment segments differ from the source transcript; regenerate the upstream data first.")
    if not any(s.get("sentiment") for s in segments):
        raise PipelineError("No scored transcript segments are available.")

    started = time.monotonic()
    retrieval_queries = current_call_queries(segments) if include_history else []
    if include_history and not retrieval_queries:
        raise PipelineError("No complete current-call passages available for historical retrieval.")
    context = query_prior_quarters(call.ticker, call.quarter, strict=True, queries=retrieval_queries) if include_history else []
    if context:
        # Check returned text/timestamps against saved same-company transcripts,
        # not only vector-index metadata. Reject bad context before any model call.
        from src.eval.audit_reports import context_issues
        dates = json.loads(watched[ROOT / "data/processed/call_dates.json"])

        def prior_transcript(ticker, quarter):
            path = ROOT / f"data/processed/transcripts/{ticker}/{quarter}.json"
            watched[path] = path.read_bytes()
            return json.loads(watched[path])

        issues = context_issues(call.ticker, call.quarter, context, dates,
                                prior_transcript)
        if issues:
            raise PipelineError(f"Historical context failed source/date validation: {issues}")
    # Never pass cached prior context from the old report to generation.
    claims = generate_structured(call.ticker, call.quarter, client, prior_context=context)
    if any(path.read_bytes() != content for path, content in watched.items()):
        raise PipelineError("Generation inputs changed while the request was running; candidate was not staged.")
    requested_hash = claims.get("generation_provenance", {}).get("input_segments_sha256")
    if requested_hash and requested_hash != hashlib.sha256(json.dumps(segments, sort_keys=True).encode()).hexdigest():
        raise PipelineError("Generator used a different transcript snapshot; candidate was not staged.")
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
            "retrieval": {"query_policy": "selected_current_call_passages_v1",
                          "queries_sha256": hashlib.sha256(json.dumps(retrieval_queries).encode()).hexdigest(),
                          "query_count": len(retrieval_queries)} if include_history else {"query_policy": "explicitly_omitted"},
            "input_sha256": {
                str(path.relative_to(Path(__file__).resolve().parents[2])) if path.is_relative_to(Path(__file__).resolve().parents[2]) else path.name:
                    hashlib.sha256(content).hexdigest()
                for path, content in watched.items()
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
