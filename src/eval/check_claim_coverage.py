"""Claim-extraction precision/recall/F1 against hand-labeled ground truth (see scaffold_labels.py).
Only scores calls that actually have a data/eval_labels/{ticker}/{quarter}.json with filled-in
claims — unlabeled calls are silently skipped rather than faked.

Matching is text-similarity based (same approach as check_citations.py), which is approximate:
a hand-written claim and the LLM's paraphrase of the same fact won't always score as a match.
Good enough to catch "the LLM missed this entirely" or "the LLM hallucinated a claim nothing
supports," not precise enough to be the only signal — read the per-call output, don't just
trust the aggregate.
"""
import json
from difflib import SequenceMatcher
from pathlib import Path

from src.eval.check_citations import normalize

LABELS_DIR = Path(__file__).parent.parent.parent / "data" / "eval_labels"
CLAIMS_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "reports_structured_citations_v1"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "eval" / "claim_coverage.json"

MATCH_THRESHOLD = 0.5  # looser than citation matching (0.6) — claims are paraphrased, not verbatim


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def score_call(ticker: str, quarter: str) -> dict:
    labels_path = LABELS_DIR / ticker / f"{quarter}.json"
    claims_path = CLAIMS_DIR / ticker / f"{quarter}.json"

    ground_truth = [c for c in json.loads(labels_path.read_text())["claims"] if c.get("claim")]
    if not ground_truth or not claims_path.exists():
        return None

    generated = json.loads(claims_path.read_text())["claims"]

    gt_matched = [False] * len(ground_truth)
    gen_matched = [False] * len(generated)
    for gi, gen in enumerate(generated):
        best_j, best_score = None, 0.0
        for j, gt in enumerate(ground_truth):
            if gt_matched[j]:
                continue
            score = similarity(gen["claim"], gt["claim"])
            if score > best_score:
                best_j, best_score = j, score
        if best_score >= MATCH_THRESHOLD:
            gen_matched[gi] = True
            gt_matched[best_j] = True

    true_positives = sum(gen_matched)
    precision = round(true_positives / len(generated), 3) if generated else None
    recall = round(true_positives / len(ground_truth), 3) if ground_truth else None
    f1 = round(2 * precision * recall / (precision + recall), 3) if precision and recall and (precision + recall) > 0 else None

    return {
        "ticker": ticker, "quarter": quarter,
        "generated_claims": len(generated), "ground_truth_claims": len(ground_truth),
        "true_positives": true_positives, "precision": precision, "recall": recall, "f1": f1,
    }


def run():
    if not LABELS_DIR.exists():
        print(f"No ground-truth labels yet at {LABELS_DIR} — run src/eval/scaffold_labels.py first, then hand-edit.")
        return

    results = []
    for ticker_dir in sorted(LABELS_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        for labels_path in sorted(ticker_dir.glob("*.json")):
            ticker, quarter = ticker_dir.name, labels_path.stem
            result = score_call(ticker, quarter)
            if result is None:
                print(f"{ticker} {quarter}: no filled-in claims yet, skipping")
                continue
            results.append(result)
            print(f"{ticker} {quarter}: precision={result['precision']}, recall={result['recall']}, f1={result['f1']} "
                  f"({result['true_positives']}/{result['ground_truth_claims']} ground-truth claims covered)")

    if not results:
        print("No labeled calls found yet. Nothing to score.")
        return

    def avg(key):
        values = [r[key] for r in results if r[key] is not None]
        return round(sum(values) / len(values), 3) if values else None

    summary = {
        "calls_evaluated": len(results),
        "avg_precision": avg("precision"), "avg_recall": avg("recall"), "avg_f1": avg("f1"),
        "results": results,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2))
    print(f"\nAvg across {len(results)} labeled call(s): "
          f"precision={summary['avg_precision']}, recall={summary['avg_recall']}, f1={summary['avg_f1']}")
    print(f"-> {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
