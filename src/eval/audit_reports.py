"""Read-only, reproducible report audit; no audio, database, LLM or network calls.

Date checks validate curated source records, not the current contents of a website.
Evidence completeness is a punctuation/continuity check, not a claim-support score.
"""
import argparse
import hashlib
import json
import yaml
from datetime import date
from pathlib import Path

from src.common.manifest import ROOT, normalize_quarter
from src.eval.check_citations_structured import evaluate_report, find_segment_at
from src.report.evidence import EVIDENCE_POLICY, select_evidence_passages


def context_issues(ticker: str, quarter: str, context: list, dates: dict, load_transcript) -> list:
    issues = []
    try:
        target = date.fromisoformat(dates[ticker][quarter])
    except (KeyError, ValueError, TypeError):
        return [{"kind": "unknown_target_date"}]
    for index, item in enumerate(context):
        try:
            earlier = normalize_quarter(item["quarter"])
            recorded = date.fromisoformat(dates[ticker][earlier])
            if recorded >= target:
                issues.append({"index": index, "quarter": earlier, "kind": "nonhistorical_context"})
                continue
            rows = load_transcript(ticker, earlier)["segments"]
            words = item["text"].split()
            starts = [i for i, row in enumerate(rows) if abs(row["start"] - item["start_sec"]) < .01]
            if not words or not any(" ".join(row["text"] for row in rows[i:]).split()[:len(words)] == words for i in starts):
                issues.append({"index": index, "quarter": earlier, "kind": "context_source_mismatch"})
        except (KeyError, ValueError, TypeError, OSError):
            issues.append({"index": index, "kind": "invalid_or_missing_context_source"})
    return issues


def date_source_matches(ticker: str, quarter: str, recorded: str, sources: dict) -> bool:
    try:
        entry = sources["calls"][ticker][quarter]
        date.fromisoformat(recorded)
        date.fromisoformat(entry["checked_on"])
        return (entry["status"] == "primary_source_checked" and entry["call_date"] == recorded
                and entry["source_url"].startswith("https://") and bool(entry["evidence_basis"]))
    except (KeyError, ValueError, TypeError, AttributeError):
        return False


def audit_reports(root: Path = ROOT) -> dict:
    fingerprints = {}

    def read(relative):
        content = (root / relative).read_bytes()
        fingerprints[relative] = hashlib.sha256(content).hexdigest()
        return json.loads(content)

    base = "data/processed"
    dates = read(f"{base}/call_dates.json")
    sources = read(f"{base}/call_date_sources.json")
    configuration = (root / "config/pipeline.yaml").read_bytes()
    top_k = yaml.safe_load(configuration)["generation"]["top_k_quotes"]
    results = []
    for path in sorted((root / base / "pipeline_runs").glob("*/*.json")):
        ticker, quarter = path.parent.name, path.stem
        report = read(str(path.relative_to(root)))
        transcript = read(f"{base}/transcripts/{ticker}/{quarter}.json")
        sentiment = read(f"{base}/sentiment/segment/{ticker}/{quarter}.json")
        generated = read(f"{base}/reports_structured_citations_v1/{ticker}/{quarter}.json")
        saved_eval = read(f"{base}/eval/per_call/{ticker}/{quarter}.json")
        rows = transcript["segments"]
        source = lambda items: [(s["start"], s["end"], s["text"]) for s in items]
        inputs_agree = source(rows) == source(sentiment["segments"])
        evaluation = evaluate_report(ticker, quarter, generated, rows)
        incomplete = []
        out_of_range = []
        for index, claim in enumerate(generated["claims"]):
            citation = claim["citation"]
            timestamp, text = citation["timestamp_sec"], citation["source_text"]
            passage = find_segment_at(rows, timestamp, text, require_complete=True)
            if passage is None or passage["text"].strip() != text.strip():
                incomplete.append(index)
            if not 0 <= timestamp <= transcript["duration_sec"]:
                out_of_range.append(index)
        history = context_issues(ticker, quarter, report.get("prior_quarter_context_used", []), dates,
                                 lambda t, q: read(f"{base}/transcripts/{t}/{q}.json"))
        positive, negative = select_evidence_passages(sentiment["segments"], top_k)
        complete_policy = generated.get("evidence_policy") == report.get("evidence_policy") == EVIDENCE_POLICY
        expected = [{"claim": c["claim"], "evidence": c["citation"]["source_text"],
                     "timestamp_sec": c["citation"]["timestamp_sec"], "sentiment": c["sentiment"]}
                    for c in generated["claims"]]
        date_matches = date_source_matches(ticker, quarter, dates[ticker][quarter], sources)
        results.append({
            "ticker": ticker, "quarter": quarter, "call_date": dates[ticker][quarter],
            "date_source_record_matches": date_matches,
            "report_date_matches_registry": report["call_date"] == dates[ticker][quarter],
            "source_transcript_and_sentiment_agree": inputs_agree,
            "report_claims_and_summary_agree": expected == report["key_claims"] and generated["overall_summary"] == report["overall_summary"],
            "citation_matches": {"matched": evaluation["verified"], "total": evaluation["total_citations"]},
            "saved_citation_evaluation_matches": all(saved_eval.get(k) == v for k, v in evaluation.items()),
            "incomplete_or_nonexact_passage_claim_indices": incomplete,
            "out_of_range_timestamp_claim_indices": out_of_range,
            "historical_context_issues": history,
            "eligible_complete_passages": {"positive_seed": len(positive), "negative_seed": len(negative)},
            "needs_regeneration": not complete_policy,
            "ready_to_stage": inputs_agree and date_matches and bool(positive or negative),
            "claim_support_review": report.get("regeneration", {}).get("claim_support_review", "not_recorded"),
        })
    for relative in ("src/eval/audit_reports.py", "src/report/evidence.py", "src/eval/check_citations_structured.py",
                     "src/report/regenerate.py", "src/report/generate_structured_report.py", "src/rag/build_index.py",
                     "config/pipeline.yaml", "config/companies.yaml"):
        fingerprints[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    local_config = root / "config/pipeline.local.yaml"
    if local_config.exists():
        fingerprints["config/pipeline.local.yaml"] = hashlib.sha256(local_config.read_bytes()).hexdigest()
    return {
        "schema_version": "1.0",
        "scope": "Saved report integrity and evidence continuity; not claim correctness, recording identity, deviation detection or market evaluation.",
        "date_check_scope": sources["scope"],
        "input_sha256": dict(sorted(fingerprints.items())),
        "summary": {
            "calls": len(results), "needs_regeneration": sum(r["needs_regeneration"] for r in results),
            "calls_with_nonhistorical_context": sum(any(i["kind"] == "nonhistorical_context" for i in r["historical_context_issues"]) for r in results),
            "nonhistorical_context_passages": sum(i["kind"] == "nonhistorical_context" for r in results for i in r["historical_context_issues"]),
            "incomplete_or_nonexact_passages": sum(len(r["incomplete_or_nonexact_passage_claim_indices"]) for r in results),
        },
        "reports": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit saved report inputs without generating or replacing any report.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_reports()
    if args.output:
        served = ROOT / "data/processed"
        resolved = args.output.resolve()
        if resolved.is_relative_to(served) and not resolved.is_relative_to(served / "audits"):
            parser.error("Audit output must not overwrite report inputs or version archives.")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"] if args.output else result, indent=2))


if __name__ == "__main__":
    main()
