"""Resume candidate generation for audited legacy calls; never publish outputs."""
import argparse
import json
import time
from pathlib import Path

from src.common.errors import PipelineError
from src.common.manifest import ROOT
from src.eval.audit_reports import audit_reports


def pending_calls(audit: dict) -> list:
    calls = [r for r in audit["reports"] if r["needs_regeneration"]]
    blocked = [f"{r['ticker']}/{r['quarter']}" for r in calls if not r["ready_to_stage"] or not r["report_date_matches_registry"]]
    if blocked:
        raise PipelineError(f"Fix audited input/date problems before generation: {', '.join(blocked)}")
    return sorted(calls, key=lambda r: (r["ticker"], r["call_date"]))


def stage_remaining(audit: dict, output_dir: Path, generate, *, include_history: bool, limit: int | None = None) -> list:
    """One bounded request per call; stop on first failure and retain prior candidates."""
    calls = pending_calls(audit)
    completed = []
    for call in calls:
        path = output_dir / call["ticker"] / f"{call['quarter']}.json"
        if path.exists():
            # Do not silently accept a truncated file, different call or context mode.
            existing = json.loads(path.read_text())
            report = existing["report"]
            expected_mode = "explicitly_omitted" if not include_history else None
            if report["ticker"] != call["ticker"] or report["quarter"].replace(" ", "_") != call["quarter"]:
                raise PipelineError(f"Existing candidate has the wrong identity: {path}")
            mode = report.get("regeneration", {}).get("historical_context")
            if mode not in {"explicitly_omitted", "retrieved", "none_returned"}:
                raise PipelineError(f"Existing candidate has no valid historical-context provenance: {path}")
            if (mode == "explicitly_omitted") != (expected_mode == "explicitly_omitted"):
                raise PipelineError(f"Existing candidate uses a different historical-context mode: {path}")
            provenance = report.get("regeneration", {}).get("provenance", {})
            hashes = provenance.get("input_sha256", {})
            expected_paths = [f"data/processed/{folder}/{call['ticker']}/{call['quarter']}.json"
                              for folder in ("transcripts", "sentiment/segment", "pipeline_runs")]
            if not hashes or any(hashes.get(p) != audit["input_sha256"].get(p) for p in expected_paths):
                raise PipelineError(f"Existing candidate inputs are stale or unrecorded: {path}")
            if any(audit["input_sha256"].get(p) != value for p, value in hashes.items()):
                raise PipelineError(f"Existing candidate configuration, context or source data changed: {path}")
            print(f"Already staged: {path}")
            continue
        if limit is not None and len(completed) >= limit:
            break
        print(f"Generating {call['ticker']} {call['quarter']}…", flush=True)
        candidate = generate(call["ticker"], call["quarter"], include_history=include_history)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(candidate, stream, indent=2)
        completed.append(str(path))
        print(f"Staged {path}; evidence review pending.", flush=True)
        # Deliberately sequential and paced; no parallel requests or hidden retries.
        if call is not calls[-1] and (limit is None or len(completed) < limit):
            time.sleep(1)
    return completed


def main():
    parser = argparse.ArgumentParser(description="Preview or execute resumable candidate generation for remaining legacy calls.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/report_candidates/remaining")
    parser.add_argument("--without-history", action="store_true", help="Explicitly omit context; does not test historical retrieval")
    parser.add_argument("--execute", action="store_true", help="Make generation requests; without this flag only show the queue")
    parser.add_argument("--limit", type=int, help="Maximum new candidates generated in this invocation")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    output = args.output_dir.resolve()
    protected = ROOT / "data/processed"
    if any(output.is_relative_to(protected / folder) for folder in
           ("pipeline_runs", "reports_structured_citations_v1", "eval", "transcripts", "sentiment", "report_versions")):
        parser.error("Output must be a candidate directory, not a served or evaluation directory")
    try:
        audit = audit_reports()
        calls = pending_calls(audit)
        print(f"Pending legacy calls: {len(calls)}. Historical context: {'explicitly omitted' if args.without_history else 'fresh retrieval with source/date validation'}.")
        if not args.execute:
            for call in calls:
                print(f"  {call['ticker']} {call['quarter']} ({call['call_date']})")
            print("Preview only. Add --execute to generate candidates; no served outputs will be changed.")
            return
        from dotenv import load_dotenv
        from groq import Groq
        from src.report.generate_report import ENV_PATH
        from src.report.regenerate import regenerate_candidate

        load_dotenv(ENV_PATH)
        client = Groq(timeout=30.0, max_retries=0)
        completed = stage_remaining(audit, output, lambda t, q, **kw: regenerate_candidate(t, q, client, **kw),
                                    include_history=not args.without_history, limit=args.limit)
        print(f"Staged {len(completed)} new candidates. Review and explicitly promote each version separately.")
    except (PipelineError, OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"Stopped; served reports unchanged and completed candidates retained: {exc}") from exc


if __name__ == "__main__":
    main()
