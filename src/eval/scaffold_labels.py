"""Scaffolds a ground-truth claims file for hand-labeling — pulls candidate quotes straight from
the transcript (not from the LLM's output) so you're not starting from a blank page, but every
`claim` field still needs a human to actually write it (or delete the entry if it isn't
claim-worthy) before check_claim_coverage.py will treat it as real eval data.

    python -m src.eval.scaffold_labels --ticker AAPL --quarter Q1_2025
"""
import argparse
import json
from pathlib import Path

from src.common.manifest import resolve_call
from src.report.generate_report import load_scored_segments, top_quotes

LABELS_DIR = Path(__file__).parent.parent.parent / "data" / "eval_labels"


def scaffold(ticker: str, quarter: str, k: int = 8) -> dict:
    segments = load_scored_segments(ticker, quarter)
    positive = top_quotes(segments, "positive", k // 2)
    negative = top_quotes(segments, "negative", k // 2)

    def entry(seg, sentiment):
        return {
            "claim": None,  # TODO: write the actual claim this quote supports, or delete this entry
            "sentiment": sentiment,
            "evidence_hint": seg["text"].strip(),
            "timestamp_sec": int(seg["start"]),
        }

    return {
        "ticker": ticker,
        "quarter": quarter,
        "claims": [entry(s, "positive") for s in positive] + [entry(s, "negative") for s in negative],
    }


def run(ticker: str, quarter: str, force: bool) -> None:
    call = resolve_call(ticker, quarter=quarter)
    out_path = LABELS_DIR / call.ticker / f"{call.quarter}.json"
    if out_path.exists() and not force:
        print(f"{out_path} already exists — pass --force to overwrite.")
        return

    draft = scaffold(call.ticker, call.quarter)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(draft, indent=2))
    print(f"Wrote {len(draft['claims'])} draft entries -> {out_path}")
    print("Edit each 'claim' field by hand (or delete entries that aren't real claims), then run:")
    print("  python -m src.eval.check_claim_coverage")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--quarter", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run(args.ticker, args.quarter, args.force)
