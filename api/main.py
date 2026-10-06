"""Minimal local API serving the Candor pipeline — this runs on your own machine for your own
demo, not a public-facing service (see the hosting scope decision in project memory). Just
enough endpoints for a frontend to list calls, fetch a processed report, or trigger a new run:

    uvicorn api.main:app --reload

GET  /calls                          -> every ticker+quarter that's already been processed
GET  /calls/{ticker}/{quarter}       -> that call's standardized report (src/common/schema.py)
GET  /calls/{ticker}/{quarter}/transcript  -> raw transcript segments
POST /analyze?ticker=X&quarter=Y     -> run the pipeline for a call (reuses cached stages)
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

from pipeline import run_pipeline
from src.common.errors import PipelineError
from src.common.logging_setup import setup_logging
from src.common.manifest import resolve_call

ROOT = Path(__file__).parent.parent
PIPELINE_RUNS_DIR = ROOT / "data" / "processed" / "pipeline_runs"

setup_logging()
app = FastAPI(title="Candor API", version="1.0")


@app.get("/calls")
def list_calls():
    calls = []
    if PIPELINE_RUNS_DIR.exists():
        for ticker_dir in sorted(PIPELINE_RUNS_DIR.iterdir()):
            if not ticker_dir.is_dir():
                continue
            for report_path in sorted(ticker_dir.glob("*.json")):
                calls.append({"ticker": ticker_dir.name, "quarter": report_path.stem.replace("_", " ")})
    return {"calls": calls}


@app.get("/calls/{ticker}/{quarter}")
def get_call(ticker: str, quarter: str):
    call = _resolve_or_400(ticker, quarter)
    if not call.pipeline_output_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No processed report for {call.ticker} {call.quarter} yet. POST /analyze to generate one.",
        )
    return json.loads(call.pipeline_output_path.read_text())


@app.get("/calls/{ticker}/{quarter}/transcript")
def get_transcript(ticker: str, quarter: str):
    call = _resolve_or_400(ticker, quarter)
    if not call.transcript_path.exists():
        raise HTTPException(status_code=404, detail=f"No transcript for {call.ticker} {call.quarter} yet.")
    return json.loads(call.transcript_path.read_text())


@app.post("/analyze")
def analyze(ticker: str, quarter: str = None, date: str = None, force: bool = False):
    try:
        return run_pipeline(ticker, quarter=quarter, date=date, force=force)
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _resolve_or_400(ticker: str, quarter: str):
    try:
        return resolve_call(ticker, quarter=quarter)
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e))
