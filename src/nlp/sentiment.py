import argparse
import json
from pathlib import Path
from transformers import pipeline

TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "transcripts"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "sentiment"
MODEL_NAME = "ProsusAI/finbert"
CHUNK_WORDS = 400


def score_text(classifier, text: str) -> dict:
    result = classifier(text, truncation=True, max_length=512)[0]
    return {"label": result["label"], "score": result["score"]}


def score_segments(classifier, segments: list) -> list:
    scored = []
    for seg in segments:
        sentiment = score_text(classifier, seg["text"]) if seg["text"].strip() else None
        scored.append({**seg, "sentiment": sentiment})
    return scored


def score_full_transcript(classifier, full_text: str) -> dict:
    words = full_text.split()
    chunks = [" ".join(words[i:i + CHUNK_WORDS]) for i in range(0, len(words), CHUNK_WORDS)]
    totals = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}

    for chunk in chunks:
        result = classifier(chunk, truncation=True, max_length=512)[0]
        totals[result["label"]] += result["score"]

    averaged = {label: total / len(chunks) for label, total in totals.items()}
    overall_label = max(averaged, key=averaged.get)
    return {"label": overall_label, "scores": averaged, "num_chunks": len(chunks)}


def run(mode: str):
    print(f"Loading FinBERT ({MODEL_NAME})...")
    classifier = pipeline("sentiment-analysis", model=MODEL_NAME, tokenizer=MODEL_NAME)

    for ticker_dir in sorted(TRANSCRIPTS_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name
        out_dir = OUTPUT_DIR / mode / ticker
        out_dir.mkdir(parents=True, exist_ok=True)

        for transcript_path in sorted(ticker_dir.glob("*.json")):
            quarter = transcript_path.stem
            out_path = out_dir / f"{quarter}.json"
            if out_path.exists():
                print(f"{ticker} {quarter} ({mode}): already scored, skipping")
                continue

            with open(transcript_path) as f:
                transcript = json.load(f)

            print(f"{ticker} {quarter} ({mode}): scoring...")
            if mode == "segment":
                result = {"segments": score_segments(classifier, transcript["segments"])}
            else:
                result = score_full_transcript(classifier, transcript["full_text"])

            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f"  -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["segment", "transcript"], default="segment",
                         help="segment: sentiment per transcript segment. transcript: one overall sentiment per call.")
    args = parser.parse_args()
    run(args.mode)
