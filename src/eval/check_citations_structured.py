import json
from difflib import SequenceMatcher
from pathlib import Path

from src.common.config import load_pipeline_config
from src.eval.check_citations import normalize
from src.report.evidence import EVIDENCE_POLICY, passage_at

_cfg = load_pipeline_config()

# Wider than the baseline checker's tolerance: structured timestamps are truncated ints
# (see generate_structured_report.py), so the true segment can drift up to ~1s from the
# cited value. Safe to widen since matching now ranks candidates by text similarity,
# not merely by closest timestamp (see find_segment_at).
TIMESTAMP_TOLERANCE_SEC = _cfg["evaluation"]["citation_tolerance_sec"]
MATCH_THRESHOLD = _cfg["evaluation"]["citation_match_threshold"]

RUN_LABEL = "structured_citations_v1"
REPORTS_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / f"reports_{RUN_LABEL}"
SENTIMENT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "sentiment" / "segment"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "eval" / f"citation_accuracy_{RUN_LABEL}.json"


def find_segment_at(segments: list, target_sec: float, source_text: str,
                    require_complete: bool = False) -> dict:
    candidates = [s for s in segments if abs(s["start"] - target_sec) <= TIMESTAMP_TOLERANCE_SEC]
    if require_complete:
        # New reports must cite a complete contiguous passage at its copied integer
        # start. Do not let the legacy fuzzy matcher bless a cut-off fragment.
        candidates = []
        for i, s in enumerate(segments):
            if int(s["start"]) != target_sec:
                continue
            passage = passage_at(segments, i)
            if passage and passage["segment_start"] == i:
                candidates.append(passage)
    if not candidates:
        return None
    return max(candidates, key=lambda s: SequenceMatcher(None, normalize(source_text), normalize(s["text"])).ratio())


def check_report(ticker: str, quarter: str) -> dict:
    report_path = REPORTS_DIR / ticker / f"{quarter}.json"
    sentiment_path = SENTIMENT_DIR / ticker / f"{quarter}.json"

    report = json.loads(report_path.read_text())
    segments = json.loads(sentiment_path.read_text())["segments"]
    require_complete = report.get("evidence_policy") == EVIDENCE_POLICY

    citations = []
    for c in report["claims"]:
        citation = c["citation"]
        segment = find_segment_at(segments, citation["timestamp_sec"], citation["source_text"], require_complete)

        if segment is None:
            citations.append({"claim": c["claim"], "source_text": citation["source_text"],
                               "timestamp_sec": citation["timestamp_sec"], "verdict": "TIMESTAMP_NOT_FOUND", "match_ratio": 0.0})
            continue

        ratio = SequenceMatcher(None, normalize(citation["source_text"]), normalize(segment["text"])).ratio()
        matches = (
            citation["source_text"].strip() == segment["text"].strip()
            if require_complete else ratio >= MATCH_THRESHOLD
        )
        verdict = "VERIFIED" if matches else "TEXT_MISMATCH"
        citations.append({
            "claim": c["claim"],
            "source_text": citation["source_text"],
            "timestamp_sec": citation["timestamp_sec"],
            "verdict": verdict,
            "match_ratio": round(ratio, 3),
            "actual_segment_text": segment["text"] if verdict != "VERIFIED" else None,
        })

    verified = sum(1 for c in citations if c["verdict"] == "VERIFIED")
    return {
        "ticker": ticker,
        "quarter": quarter,
        "total_citations": len(citations),
        "verified": verified,
        "accuracy": round(verified / len(citations), 3) if citations else None,
        "citations": citations,
    }


def run():
    results = []
    for ticker_dir in sorted(REPORTS_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name
        for report_path in sorted(ticker_dir.glob("*.json")):
            quarter = report_path.stem
            result = check_report(ticker, quarter)
            results.append(result)
            print(f"{ticker} {quarter}: {result['verified']}/{result['total_citations']} citations verified "
                  f"({result['accuracy']*100:.0f}%)" if result["total_citations"] else f"{ticker} {quarter}: no citations found")

    total_citations = sum(r["total_citations"] for r in results)
    total_verified = sum(r["verified"] for r in results)
    overall_accuracy = round(total_verified / total_citations, 3) if total_citations else None
    format_compliance = round(len(results) / 16, 3)

    print(f"\nOverall content accuracy: {total_verified}/{total_citations} citations verified ({overall_accuracy*100:.1f}%)")
    print(f"Format compliance: {len(results)}/16 reports produced valid structured output ({format_compliance*100:.1f}%)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"run_label": RUN_LABEL, "format_compliance": format_compliance,
                    "overall_accuracy": overall_accuracy, "total_citations": total_citations,
                    "total_verified": total_verified, "reports": results}, f, indent=2)
    print(f"Full results -> {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
