import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

sys.path.insert(0, str(Path(__file__).parent.parent / "data"))
from companies import COMPANIES

SENTIMENT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "sentiment" / "segment"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "reports"
ENV_PATH = Path(__file__).parent.parent.parent / ".env"
MODEL_NAME = "openai/gpt-oss-120b"
TOP_K_QUOTES = 4
MAX_TOKENS = 1500


def load_scored_segments(ticker: str, quarter: str) -> list:
    path = SENTIMENT_DIR / ticker / f"{quarter}.json"
    with open(path) as f:
        data = json.load(f)
    return [s for s in data["segments"] if s["sentiment"]]


def sentiment_distribution(segments: list) -> dict:
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for s in segments:
        counts[s["sentiment"]["label"]] += 1
    total = len(segments)
    return {label: round(100 * count / total, 1) for label, count in counts.items()}


def top_quotes(segments: list, label: str, k: int) -> list:
    candidates = [s for s in segments if s["sentiment"]["label"] == label and len(s["text"].split()) > 5]
    candidates.sort(key=lambda s: s["sentiment"]["score"], reverse=True)
    return candidates[:k]


def format_quote(seg: dict) -> str:
    minutes = int(seg["start"] // 60)
    seconds = int(seg["start"] % 60)
    return f'[{minutes}:{seconds:02d}] "{seg["text"].strip()}"'


def build_prompt(ticker: str, quarter: str, distribution: dict, positive_quotes: list, negative_quotes: list) -> str:
    company = COMPANIES.get(ticker, {}).get("name", ticker)
    positive_block = "\n".join(format_quote(q) for q in positive_quotes) or "(none found)"
    negative_block = "\n".join(format_quote(q) for q in negative_quotes) or "(none found)"

    return f"""You are writing a short, factual earnings call sentiment brief for an investor.

Company: {company} ({ticker})
Quarter: {quarter}
FinBERT sentiment distribution across the call: {distribution['positive']}% positive, {distribution['negative']}% negative, {distribution['neutral']}% neutral.

The most positively-scored statements from the call:
{positive_block}

The most negatively-scored statements from the call:
{negative_block}

Write a brief (3-4 short paragraphs) summarizing the overall tone of this call. You MUST ground every specific claim in the quotes above and cite them with their timestamp, e.g. [14:32]. Do not invent facts, numbers, or statements that are not present in the quotes or distribution given. If the quotes are too sparse or generic to support a strong claim, say so plainly instead of overstating."""


def generate(ticker: str, quarter: str, client: Groq) -> str:
    segments = load_scored_segments(ticker, quarter)
    distribution = sentiment_distribution(segments)
    positive_quotes = top_quotes(segments, "positive", TOP_K_QUOTES)
    negative_quotes = top_quotes(segments, "negative", TOP_K_QUOTES)

    prompt = build_prompt(ticker, quarter, distribution, positive_quotes, negative_quotes)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
    )
    return response.choices[0].message.content


def run():
    load_dotenv(ENV_PATH)
    client = Groq()

    for ticker_dir in sorted(SENTIMENT_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name
        out_dir = OUTPUT_DIR / ticker
        out_dir.mkdir(parents=True, exist_ok=True)

        for sentiment_path in sorted(ticker_dir.glob("*.json")):
            quarter = sentiment_path.stem
            out_path = out_dir / f"{quarter}.md"
            if out_path.exists():
                print(f"{ticker} {quarter}: already generated, skipping")
                continue

            print(f"{ticker} {quarter}: generating report...")
            report = generate(ticker, quarter, client)
            with open(out_path, "w") as f:
                f.write(report)
            print(f"  -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", help="Run for a single ticker only, e.g. AAPL")
    parser.add_argument("--quarter", help="Run for a single quarter only, e.g. Q3_2025")
    args = parser.parse_args()

    if args.ticker and args.quarter:
        load_dotenv(ENV_PATH)
        print(generate(args.ticker, args.quarter, Groq()))
    else:
        run()
