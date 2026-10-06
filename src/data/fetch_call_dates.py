import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

from src.data.companies import QUARTERS, CASTIFY_FEEDS

OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "call_dates.json"


def extract_call_dates(ticker: str, feed_url: str) -> dict:
    resp = requests.get(feed_url, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    targets = [q.replace("_", " ") for q in QUARTERS]
    dates = {}
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        for target in targets:
            if target in title:
                pubdate = item.findtext("pubDate")
                dt = datetime.strptime(pubdate, "%a, %d %b %Y %H:%M:%S %z")
                dates[target.replace(" ", "_")] = dt.strftime("%Y-%m-%d")
    return dates


def run():
    call_dates = {}
    for ticker, feed_url in CASTIFY_FEEDS.items():
        print(f"Fetching call dates for {ticker}...")
        call_dates[ticker] = extract_call_dates(ticker, feed_url)
        print(f"  {call_dates[ticker]}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(call_dates, f, indent=2)
    print(f"-> {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
