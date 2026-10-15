"""Preview and explicitly apply a verified candidate to the read-only product.

No network or model calls. Previous and replacement bundles are archived together.
Local multi-file updates roll back on failure; commit all outputs in one deployment.
"""
import argparse
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import yaml
from datetime import date, datetime, timezone
from pathlib import Path

from src.common.errors import PipelineError
from src.common.manifest import ROOT, normalize_quarter
from src.common.schema import validate_report
from src.eval.check_citations_structured import evaluate_report
from src.report.evidence import EVIDENCE_POLICY


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def prepare_update(candidate_path: Path, *, root: Path = ROOT) -> dict:
    """Validate all inputs and build replacement bytes without modifying the repo."""
    tracked = {}

    def read(relative):
        content = (root / relative).read_bytes()
        tracked[relative] = content
        return json.loads(content)

    raw = candidate_path.read_bytes()
    candidate = json.loads(raw)
    report = candidate["report"]
    ticker, quarter = report["ticker"], normalize_quarter(report["quarter"])
    company_config = (root / "config/companies.yaml").read_bytes()
    tracked["config/companies.yaml"] = company_config
    if ticker not in yaml.safe_load(company_config)["companies"]:
        raise PipelineError("Candidate is outside the configured dataset.")
    prefix = "data/processed"
    paths = {
        "structured_claims": f"{prefix}/reports_structured_citations_v1/{ticker}/{quarter}.json",
        "citation_evaluation": f"{prefix}/eval/per_call/{ticker}/{quarter}.json",
        "report": f"{prefix}/pipeline_runs/{ticker}/{quarter}.json",
    }
    previous = {key: read(path) for key, path in paths.items()}
    transcript_path = f"{prefix}/transcripts/{ticker}/{quarter}.json"
    sentiment_path = f"{prefix}/sentiment/segment/{ticker}/{quarter}.json"
    transcript, sentiment = read(transcript_path), read(sentiment_path)
    dates = read(f"{prefix}/call_dates.json")
    for path in ("config/pipeline.yaml", "config/companies.yaml"):
        tracked[path] = (root / path).read_bytes()
    # Also bind the preview to the code used to construct and validate it.
    for path in ("src/report/evidence.py", "src/common/schema.py", "src/eval/check_citations_structured.py",
                 "src/report/promote.py", "frontend/scripts/build-demo.mjs"):
        tracked[path] = (root / path).read_bytes()
    validate_report(report)
    if report["company"] != previous["report"]["company"] or report["schema_version"] != previous["report"]["schema_version"]:
        raise PipelineError("Candidate changes report identity or schema.")
    current_date = date.fromisoformat(dates[ticker][quarter])
    if report["call_date"] != current_date.isoformat():
        raise PipelineError("Candidate call date differs from the recorded registry.")
    source = lambda rows: [(s["start"], s["end"], s["text"]) for s in rows]
    if source(transcript["segments"]) != source(sentiment["segments"]):
        raise PipelineError("Transcript and sentiment source segments differ.")
    for context in report["prior_quarter_context_used"]:
        earlier = normalize_quarter(context["quarter"])
        if date.fromisoformat(dates[ticker][earlier]) >= current_date:
            raise PipelineError("Historical context includes a current or future call.")
        prior = read(f"{prefix}/transcripts/{ticker}/{earlier}.json")["segments"]
        text = " ".join(context["text"].split())
        matching = [i for i, s in enumerate(prior) if abs(s["start"] - context["start_sec"]) < .01]
        if not text or not any(" ".join(s["text"] for s in prior[i:]).split()[:len(text.split())] == text.split() for i in matching):
            raise PipelineError("Historical context is not traceable to the earlier call at its timestamp.")
    claims = candidate["structured_claims"]
    if claims.get("evidence_policy") != EVIDENCE_POLICY or report.get("evidence_policy") != EVIDENCE_POLICY:
        raise PipelineError("Complete-passage evidence policy is required.")
    expected_claims = [{"claim": c["claim"], "evidence": c["citation"]["source_text"],
                        "timestamp_sec": c["citation"]["timestamp_sec"], "sentiment": c["sentiment"]}
                       for c in claims["claims"]]
    if expected_claims != report["key_claims"] or claims["overall_summary"] != report["overall_summary"]:
        raise PipelineError("Candidate report and structured claims disagree.")
    if not expected_claims or any(not c["claim"].strip() or c["sentiment"] not in {"positive", "negative", "neutral"} for c in expected_claims):
        raise PipelineError("Candidate has empty or invalid claims.")
    evaluation = evaluate_report(ticker, quarter, claims, transcript["segments"])
    if evaluation != candidate["citation_evaluation"] or evaluation["verified"] != len(expected_claims):
        raise PipelineError("Stored citation evaluation is stale or contains unmatched evidence.")
    expected_summary = {k: evaluation[k] for k in ("total_citations", "verified", "accuracy")}
    if report["citation_verification"] != expected_summary:
        raise PipelineError("Report citation counts disagree with recomputed results.")
    scored = [s for s in sentiment["segments"] if s.get("sentiment")]
    distribution = {label: round(100 * sum(s["sentiment"]["label"] == label for s in scored) / len(scored), 1)
                    for label in ("positive", "negative", "neutral")}
    if distribution != report["sentiment_distribution"] or report["audio_features_summary"] != previous["report"]["audio_features_summary"]:
        raise PipelineError("Sentiment distribution or reused audio measurements changed unexpectedly.")
    review = candidate["review"]
    if review["status"] != "ai_assisted_review_human_review_pending":
        raise PipelineError("Candidate requires an explicitly recorded evidence review.")
    assessments = review.get("per_claim", [])
    if sorted(a["claim_index"] for a in assessments) != list(range(len(expected_claims))) or any(a["support_assessment"] != "supported_by_saved_transcript" for a in assessments):
        raise PipelineError("Every candidate claim needs a recorded support assessment.")

    replacement = copy.deepcopy(candidate)
    version = f"complete-passages-{digest(raw)[:12]}"
    previous_version = previous["report"].get("report_version", f"legacy-{digest(encoded(previous))[:12]}")
    if previous_version == version:
        raise PipelineError("This candidate is already active.")
    for key in paths:
        replacement[key]["report_version"] = version
    replacement["report"]["publication"] = {
        "previous_report_version": previous_version,
        "review_status": review["status"],
        "call_date_verification": "registry_consistent_external_verification_pending",
        "scope": "current_call_only" if not report["prior_quarter_context_used"] else "current_call_with_earlier_context",
    }
    demo_path = "frontend/src/data/demo.json"
    read(demo_path)
    # The original comparison is an archived experiment, not a new score for this update.
    for name in ("citation_accuracy_baseline_free_text_v1.json", "citation_accuracy_structured_citations_v1.json", "claim_coverage.json"):
        read(f"{prefix}/eval/{name}")
    # Bind all source files read by the demo builder to this preview.
    for company in ("AAPL", "MSFT", "NVDA", "META"):
        for folder in ("pipeline_runs", "reports_structured_citations_v1", "transcripts", "eval/per_call"):
            path = f"{prefix}/{folder}/{company}/Q1_2025.json"
            if path not in tracked:
                read(path)
    with tempfile.TemporaryDirectory() as directory:
        bundle_path, demo_output = Path(directory) / "bundle.json", Path(directory) / "demo.json"
        bundle_path.write_bytes(encoded(replacement))
        subprocess.run(["node", str(root / "frontend/scripts/build-demo.mjs"), "--override-bundle", str(bundle_path),
                        "--output", str(demo_output)], cwd=root, check=True, capture_output=True, text=True)
        demo_bytes = demo_output.read_bytes()
    new_files = {paths[key]: encoded(replacement[key]) for key in paths}
    new_files[demo_path] = demo_bytes
    archive_path = f"{prefix}/report_versions/{ticker}/{quarter}/{version}.json"
    if (root / archive_path).exists():
        raise PipelineError("Version archive already exists; investigate instead of overwriting it.")
    manifest = {
        "version": version, "previous_version": previous_version, "candidate_sha256": digest(raw),
        "previous": previous, "replacement": replacement,
        "input_sha256": {path: digest(content) for path, content in tracked.items()},
        "output_sha256": {path: digest(content) for path, content in new_files.items()},
        "configuration_at_promotion": {
            key: value for key, value in yaml.safe_load(tracked["config/pipeline.yaml"]).items()
            if key in {"models", "generation", "retrieval", "evaluation"}
        },
        "limitations": ["AI-assisted support review; independent human review pending.",
                        "Call date checked against feed-derived registry; external verification pending.",
                       ] + (["Original generation request did not record a full configuration manifest."]
                            if "provenance" not in report.get("regeneration", {}) else []),
    }
    return {"root": root, "candidate_path": candidate_path, "candidate_sha256": digest(raw),
            "tracked": tracked, "new_files": new_files, "archive_path": archive_path, "manifest": manifest}


def replace_file(path: Path, content: bytes):
    """Replace one local file atomically; caller coordinates rollback across files."""
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_update(plan: dict, expected_sha256: str):
    if expected_sha256 != plan["candidate_sha256"] or digest(plan["candidate_path"].read_bytes()) != expected_sha256:
        raise PipelineError("Candidate checksum changed; preview the exact candidate again.")
    root = plan["root"]
    for relative, before in plan["tracked"].items():
        if (root / relative).read_bytes() != before:
            raise PipelineError(f"Input changed since preview: {relative}")
    archive = root / plan["archive_path"]
    archive.parent.mkdir(parents=True, exist_ok=True)
    manifest = {**plan["manifest"], "applied_at": datetime.now(timezone.utc).isoformat()}
    with archive.open("xb") as stream:
        stream.write(encoded(manifest))
    changed = []
    try:
        for relative, content in plan["new_files"].items():
            path = root / relative
            replace_file(path, content)
            changed.append(relative)
        for relative, content in plan["new_files"].items():
            if (root / relative).read_bytes() != content:
                raise PipelineError(f"Update readback failed: {relative}")
    except Exception:
        for relative in reversed(changed):
            replace_file(root / relative, plan["tracked"][relative])
        archive.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description="Preview a versioned report update; --apply explicitly replaces local served outputs.")
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.apply and not args.expected_sha256:
        parser.error("--apply requires --expected-sha256 from a reviewed preview")
    try:
        plan = prepare_update(args.candidate)
        print(f"Candidate SHA256: {plan['candidate_sha256']}")
        print(f"Version: {plan['manifest']['previous_version']} -> {plan['manifest']['version']}")
        print(f"Updates: {', '.join(plan['new_files'])}")
        if args.apply:
            apply_update(plan, args.expected_sha256)
            print("Applied and verified locally. Commit all updated files together to deploy.")
        else:
            print("Preview only. No served files changed.")
    except (PipelineError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Report update failed: {exc}") from exc


if __name__ == "__main__":
    main()
