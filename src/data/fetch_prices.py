import requests
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv

from src.data.companies import COMPANIES

load_dotenv(Path(__file__).parent.parent.parent / ".env")

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "prices"
API_KEY = os.getenv("ALPHA_VANTAGE_KEY")
BASE_URL = "https://www.alphavantage.co/query"


def fetch_prices(ticker: str) -> dict:
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "apikey": API_KEY,
    }
    resp = requests.get(BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if "Time Series (Daily)" not in data:
        raise ValueError(f"Unexpected response for {ticker}: {list(data.keys())}")

    series = data["Time Series (Daily)"]
    price_list = [
        {
            "Date": date,
            "Close": float(values["4. close"]),
            "Volume": int(values["5. volume"]),
        }
        for date, values in sorted(series.items())
    ]

    return {
        "ticker": ticker,
        "source": "alphavantage",
        "price_history": price_list,
    }


def run():
    if not API_KEY:
        print("ERROR: ALPHA_VANTAGE_KEY not set in .env")
        print("Get a free key at: https://www.alphavantage.co/support/#api-key")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for ticker in COMPANIES:
        print(f"Fetching {ticker}...")
        data = fetch_prices(ticker)
        out_path = OUTPUT_DIR / f"{ticker}.json"
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  {len(data['price_history'])} rows saved → {out_path}")
        time.sleep(15)  # free tier: 5 calls/min max


if __name__ == "__main__":
    run()
