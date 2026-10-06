import requests
import json
from pathlib import Path

from src.data.companies import CIK_MAP

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "filings"
HEADERS = {"User-Agent": "candor-project research@candor.dev"}


def get_recent_8k(cik: str, ticker: str, limit: int = 5) -> list:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    filings = data["filings"]["recent"]
    results = []
    for i, form in enumerate(filings["form"]):
        if form == "8-K" and len(results) < limit:
            results.append({
                "ticker": ticker,
                "form": form,
                "filed": filings["filingDate"][i],
                "accession": filings["accessionNumber"][i],
                "primary_doc": filings["primaryDocument"][i],
            })
    return results


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for ticker, cik in CIK_MAP.items():
        print(f"Fetching 8-K filings for {ticker}...")
        filings = get_recent_8k(cik, ticker)
        out_path = OUTPUT_DIR / f"{ticker}_8k.json"
        with open(out_path, "w") as f:
            json.dump(filings, f, indent=2)
        print(f"  Found {len(filings)} filings → {out_path}")


if __name__ == "__main__":
    run()
