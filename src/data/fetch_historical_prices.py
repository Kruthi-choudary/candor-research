import json
from pathlib import Path

import yfinance as yf

from src.data.companies import COMPANIES

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "prices_historical"
START_DATE = "2024-01-01"
END_DATE = "2025-12-31"


def fetch_historical(ticker: str) -> dict:
    df = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False)
    df.columns = df.columns.droplevel(1)  # drop the redundant ticker level from the MultiIndex
    price_list = [
        {"Date": date.strftime("%Y-%m-%d"), "Close": round(float(row["Close"]), 2), "Volume": int(row["Volume"])}
        for date, row in df.iterrows()
    ]
    return {"ticker": ticker, "source": "yfinance", "price_history": price_list}


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for ticker in COMPANIES:
        print(f"Fetching historical prices for {ticker}...")
        data = fetch_historical(ticker)
        out_path = OUTPUT_DIR / f"{ticker}.json"
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  {len(data['price_history'])} rows saved -> {out_path}")


if __name__ == "__main__":
    run()
