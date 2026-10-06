import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.common.config import load_companies
from src.common.errors import PipelineError

ROOT = Path(__file__).parent.parent.parent
CALL_DATES_PATH = ROOT / "data" / "processed" / "call_dates.json"

QUARTER_PATTERN = re.compile(r"^Q([1-4])[\s_-]?(\d{4})$", re.IGNORECASE)


def normalize_quarter(raw: str) -> str:
    match = QUARTER_PATTERN.match(raw.strip())
    if not match:
        raise PipelineError(
            f"Could not parse quarter '{raw}' — expected a form like Q1_2025, Q1-2025, or 'Q1 2025'."
        )
    q, year = match.groups()
    return f"Q{q}_{year}"


@dataclass
class CallRef:
    ticker: str
    quarter: str
    company_name: str
    call_date: str | None
    audio_path: Path
    transcript_path: Path
    sentiment_path: Path
    audio_features_path: Path
    claims_path: Path
    citation_eval_path: Path
    pipeline_output_path: Path


def _load_call_dates(ticker: str) -> dict:
    if not CALL_DATES_PATH.exists():
        return {}
    return json.loads(CALL_DATES_PATH.read_text()).get(ticker, {})


def _quarter_from_date(ticker: str, date: str) -> str:
    call_dates = _load_call_dates(ticker)
    for quarter, call_date in call_dates.items():
        if call_date == date:
            return quarter
    known = ", ".join(f"{q} ({d})" for q, d in sorted(call_dates.items(), key=lambda kv: kv[1])) or "(none)"
    raise PipelineError(
        f"No known call for {ticker} on {date}. Candor only has data for calls it already knows about: {known}. "
        f"New audio has to be added manually (data/raw/audio/{ticker}/) before a new date can be processed."
    )


def resolve_call(ticker: str, quarter: str = None, date: str = None) -> CallRef:
    ticker = ticker.strip().upper()
    companies = load_companies()["companies"]
    if ticker not in companies:
        raise PipelineError(f"Unknown ticker '{ticker}'. Known tickers: {', '.join(sorted(companies))}.")

    if quarter:
        quarter = normalize_quarter(quarter)
    elif date:
        quarter = _quarter_from_date(ticker, date)
    else:
        raise PipelineError("Must provide --quarter or --date.")

    return CallRef(
        ticker=ticker,
        quarter=quarter,
        company_name=companies[ticker]["name"],
        call_date=_load_call_dates(ticker).get(quarter),
        audio_path=ROOT / "data" / "raw" / "audio" / ticker / f"{quarter}.mp3",
        transcript_path=ROOT / "data" / "processed" / "transcripts" / ticker / f"{quarter}.json",
        sentiment_path=ROOT / "data" / "processed" / "sentiment" / "segment" / ticker / f"{quarter}.json",
        audio_features_path=ROOT / "data" / "processed" / "audio_features" / ticker / f"{quarter}.json",
        claims_path=ROOT / "data" / "processed" / "reports_structured_citations_v1" / ticker / f"{quarter}.json",
        citation_eval_path=ROOT / "data" / "processed" / "eval" / "per_call" / ticker / f"{quarter}.json",
        pipeline_output_path=ROOT / "data" / "processed" / "pipeline_runs" / ticker / f"{quarter}.json",
    )
