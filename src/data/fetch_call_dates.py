import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests
from companies import QUARTERS

OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "call_dates.json"

# Castify "Earnings Call Podcast" RSS feeds per ticker — resolved once via iTunes search API,
# hardcoded here the same way fetch_filings.py hardcodes CIK numbers (fixed, known 4-company scope).
CASTIFY_FEEDS = {
    "AAPL": "https://casti.fyi/rss/144ea3762732432e8ec37a1d.xml",
    "MSFT": "https://casti.fyi/rss/fcacc710e8cdbd861bccc6b3.xml",
    "NVDA": "https://casti.fyi/rss/b36592e77a525c0f109d1bc9.xml",
    "META": "https://casti.fyi/rss/3437762148822bf05ced474b.xml",
}


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
