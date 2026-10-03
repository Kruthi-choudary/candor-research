import json
from datetime import datetime
from pathlib import Path

CALL_DATES_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "call_dates.json"
PRICES_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "prices_historical"
SENTIMENT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "sentiment" / "segment"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "analysis" / "price_reaction.json"

# "Notable" is based purely on price-move magnitude, not on sentiment direction.
# Earlier version also required net_sentiment >= 10 to flag something — but all 16 calls in this
# dataset came back net-positive (earnings calls are near-universally framed positively by
# management), so that check never actually filtered anything. With only 16 calls we also don't
# have enough data to build a real "expected sentiment" baseline per company. So this reports
# price-move size plus sentiment as context, rather than claiming to detect a statistical anomaly.
NOTABLE_PRICE_MOVE_PCT = 5.0


def load_price_series(ticker: str) -> list:
    data = json.load(open(PRICES_DIR / f"{ticker}.json"))
    return sorted(data["price_history"], key=lambda p: p["Date"])


def find_baseline_and_reaction(price_series: list, call_date: str) -> tuple:
    call_dt = datetime.strptime(call_date, "%Y-%m-%d")
    baseline, reaction = None, None
    for price in price_series:
        price_dt = datetime.strptime(price["Date"], "%Y-%m-%d")
        if price_dt <= call_dt:
            baseline = price
        elif price_dt > call_dt and reaction is None:
            reaction = price
            break
    return baseline, reaction


def sentiment_net(ticker: str, quarter: str) -> dict:
    segments = json.load(open(SENTIMENT_DIR / ticker / f"{quarter}.json"))["segments"]
    scored = [s for s in segments if s["sentiment"]]
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for s in scored:
        counts[s["sentiment"]["label"]] += 1
    total = len(scored)
    pct = {label: round(100 * c / total, 1) for label, c in counts.items()}
    return {**pct, "net": round(pct["positive"] - pct["negative"], 1)}


def classify_notable(net_sentiment: float, pct_change: float) -> str:
    if abs(pct_change) < NOTABLE_PRICE_MOVE_PCT:
        return None
    direction = "DROP" if pct_change < 0 else "RALLY"
    tone = "positive" if net_sentiment > 0 else "negative" if net_sentiment < 0 else "neutral"
    return f"NOTABLE_{direction}_DESPITE_{tone.upper()}_TONE" if (
        (pct_change < 0 and net_sentiment > 0) or (pct_change > 0 and net_sentiment < 0)
    ) else f"NOTABLE_{direction}"


def analyze(ticker: str, quarter: str, call_date: str, price_series: list) -> dict:
    baseline, reaction = find_baseline_and_reaction(price_series, call_date)
    sentiment = sentiment_net(ticker, quarter)

    result = {
        "ticker": ticker, "quarter": quarter, "call_date": call_date,
        "sentiment_positive_pct": sentiment["positive"], "sentiment_negative_pct": sentiment["negative"],
        "net_sentiment": sentiment["net"],
    }

    if baseline is None or reaction is None:
        result.update({"pct_change": None, "notable": None, "note": "price data does not cover this call date"})
        return result

    pct_change = round(100 * (reaction["Close"] - baseline["Close"]) / baseline["Close"], 2)
    result.update({
        "baseline_date": baseline["Date"], "baseline_close": baseline["Close"],
        "reaction_date": reaction["Date"], "reaction_close": reaction["Close"],
        "pct_change": pct_change, "notable": classify_notable(sentiment["net"], pct_change),
    })
    return result


def run():
    call_dates = json.load(open(CALL_DATES_PATH))
    results = []

    for ticker, quarters in call_dates.items():
        price_series = load_price_series(ticker)
        for quarter, call_date in quarters.items():
            result = analyze(ticker, quarter, call_date, price_series)
            results.append(result)
            flag = f" NOTABLE: {result['notable']}" if result.get("notable") else ""
            pct = result.get("pct_change")
            pct_str = f"{pct:+.2f}%" if pct is not None else "N/A"
            print(f"{ticker} {quarter}: net_sentiment={result['net_sentiment']:+.1f}, price_reaction={pct_str}{flag}")

    notable = [r for r in results if r.get("notable")]
    print(f"\n{len(notable)} notable price moves (>= {NOTABLE_PRICE_MOVE_PCT}%) out of {len(results)} calls")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"results": results, "notable_count": len(notable)}, f, indent=2)
    print(f"-> {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
