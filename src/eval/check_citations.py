import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

REPORTS_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "reports"
SENTIMENT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "sentiment" / "segment"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "eval" / "citation_accuracy.json"

CITATION_PATTERN = re.compile(r'[“"]([^”"]+)[”"]\s*\[([^\]]+)\]')
MATCH_THRESHOLD = 0.6
TIMESTAMP_TOLERANCE_SEC = 1


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_timestamp(ts: str) -> float:
    minutes, seconds = ts.strip().split(":")
    return int(minutes) * 60 + int(seconds)


def find_segment_at(segments: list, target_sec: float) -> dict:
    best, best_diff = None, None
    for seg in segments:
        diff = abs(seg["start"] - target_sec)
        if diff <= TIMESTAMP_TOLERANCE_SEC and (best_diff is None or diff < best_diff):
            best, best_diff = seg, diff
    return best


def check_report(ticker: str, quarter: str) -> dict:
    report_path = REPORTS_DIR / ticker / f"{quarter}.md"
    sentiment_path = SENTIMENT_DIR / ticker / f"{quarter}.json"

    report_text = report_path.read_text()
    segments = json.load(open(sentiment_path))["segments"]

    citations = []
    for match in CITATION_PATTERN.finditer(report_text):
        quote_text, timestamps_raw = match.group(1), match.group(2)
        for ts in timestamps_raw.split(","):
            try:
                target_sec = parse_timestamp(ts)
            except ValueError:
                continue

            segment = find_segment_at(segments, target_sec)
            if segment is None:
                citations.append({"quote": quote_text, "timestamp": ts.strip(), "verdict": "TIMESTAMP_NOT_FOUND", "match_ratio": 0.0})
                continue

            ratio = SequenceMatcher(None, normalize(quote_text), normalize(segment["text"])).ratio()
            verdict = "VERIFIED" if ratio >= MATCH_THRESHOLD else "TEXT_MISMATCH"
            citations.append({
                "quote": quote_text,
                "timestamp": ts.strip(),
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
        for report_path in sorted(ticker_dir.glob("*.md")):
            quarter = report_path.stem
            result = check_report(ticker, quarter)
            results.append(result)
            print(f"{ticker} {quarter}: {result['verified']}/{result['total_citations']} citations verified "
                  f"({result['accuracy']*100:.0f}%)" if result["total_citations"] else f"{ticker} {quarter}: no citations found")

    total_citations = sum(r["total_citations"] for r in results)
    total_verified = sum(r["verified"] for r in results)
    overall_accuracy = round(total_verified / total_citations, 3) if total_citations else None

    print(f"\nOverall: {total_verified}/{total_citations} citations verified ({overall_accuracy*100:.1f}%)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"overall_accuracy": overall_accuracy, "total_citations": total_citations,
                    "total_verified": total_verified, "reports": results}, f, indent=2)
    print(f"Full results -> {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
