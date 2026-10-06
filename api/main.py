"""Minimal local API serving the Candor pipeline — this runs on your own machine for your own
demo, not a public-facing service (see the hosting scope decision in project memory). Just
enough endpoints for the frontend (frontend/) to list calls, fetch a processed report, play the
source audio, or trigger a new run:

    uvicorn api.main:app --reload

GET  /companies                            -> the 4 known tickers (config/companies.yaml)
GET  /calls                                -> every processed call, with summary fields for cards
GET  /calls/{ticker}/{quarter}              -> that call's standardized report (src/common/schema.py)
GET  /calls/{ticker}/{quarter}/claims       -> key claims merged with their per-citation verdict
GET  /calls/{ticker}/{quarter}/transcript   -> raw transcript segments
GET  /calls/{ticker}/{quarter}/audio        -> the source mp3, for playback
GET  /eval/summary                         -> baseline-vs-structured comparison + claim coverage
POST /analyze?ticker=X&quarter=Y            -> run the pipeline for a call (reuses cached stages)
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline import run_pipeline
from src.common.config import load_companies
from src.common.errors import PipelineError
from src.common.logging_setup import setup_logging
from src.common.manifest import resolve_call

ROOT = Path(__file__).parent.parent
PIPELINE_RUNS_DIR = ROOT / "data" / "processed" / "pipeline_runs"
EVAL_DIR = ROOT / "data" / "processed" / "eval"
CLAIMS_DIR = ROOT / "data" / "processed" / "reports_structured_citations_v1"

setup_logging()
app = FastAPI(title="Candor API", version="1.0")

# Local-only demo: frontend dev server runs on a different port, same machine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/companies")
def list_companies():
    companies = load_companies()["companies"]
    return {"companies": [{"ticker": t, "name": c["name"]} for t, c in companies.items()]}


@app.get("/calls")
def list_calls():
    calls = []
    if PIPELINE_RUNS_DIR.exists():
        for ticker_dir in sorted(PIPELINE_RUNS_DIR.iterdir()):
            if not ticker_dir.is_dir():
                continue
            for report_path in sorted(ticker_dir.glob("*.json")):
                report = json.loads(report_path.read_text())
                calls.append({
                    "ticker": report["ticker"],
                    "quarter": report["quarter"].replace(" ", "-"),
                    "company": report["company"],
                    "call_date": report["call_date"],
                    "overall_summary": report["overall_summary"],
                    "sentiment_distribution": report["sentiment_distribution"],
                    "citation_accuracy": report["citation_verification"]["accuracy"],
                })
    calls.sort(key=lambda c: (c["ticker"], c["call_date"] or ""))
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


@app.get("/calls/{ticker}/{quarter}/claims")
def get_claims(ticker: str, quarter: str):
    call = _resolve_or_400(ticker, quarter)
    if not call.claims_path.exists():
        raise HTTPException(status_code=404, detail=f"No claims generated for {call.ticker} {call.quarter} yet.")

    claims = json.loads(call.claims_path.read_text())["claims"]
    verdicts = []
    if call.citation_eval_path.exists():
        verdicts = json.loads(call.citation_eval_path.read_text())["citations"]

    merged = []
    for i, c in enumerate(claims):
        verdict = verdicts[i] if i < len(verdicts) else None
        merged.append({
            "claim": c["claim"],
            "evidence": c["citation"]["source_text"],
            "timestamp_sec": c["citation"]["timestamp_sec"],
            "sentiment": c["sentiment"],
            "verdict": verdict["verdict"] if verdict else None,
            "match_ratio": verdict["match_ratio"] if verdict else None,
        })
    return {"ticker": call.ticker, "quarter": call.quarter.replace("_", " "), "claims": merged}


@app.get("/calls/{ticker}/{quarter}/transcript")
def get_transcript(ticker: str, quarter: str):
    call = _resolve_or_400(ticker, quarter)
    if not call.transcript_path.exists():
        raise HTTPException(status_code=404, detail=f"No transcript for {call.ticker} {call.quarter} yet.")
    return json.loads(call.transcript_path.read_text())


@app.get("/calls/{ticker}/{quarter}/audio")
def get_audio(ticker: str, quarter: str):
    call = _resolve_or_400(ticker, quarter)
    if not call.audio_path.exists():
        raise HTTPException(status_code=404, detail=f"No audio file for {call.ticker} {call.quarter}.")
    return FileResponse(call.audio_path, media_type="audio/mpeg")


@app.get("/eval/summary")
def eval_summary():
    def read(name):
        path = EVAL_DIR / name
        return json.loads(path.read_text()) if path.exists() else None

    baseline = read("citation_accuracy_baseline_free_text_v1.json")
    structured = read("citation_accuracy_structured_citations_v1.json")
    claim_coverage = read("claim_coverage.json")

    return {
        "citation_grounding": {
            "baseline": {
                "label": "Free-text citations",
                "schema_compliance": baseline.get("format_compliance") if baseline else None,
                "citation_accuracy": baseline["overall_accuracy"] if baseline else None,
                "total_citations": baseline["total_citations"] if baseline else None,
            } if baseline else None,
            "structured": {
                "label": "JSON-schema citations",
                "schema_compliance": structured["format_compliance"] if structured else None,
                "citation_accuracy": structured["overall_accuracy"] if structured else None,
                "total_citations": structured["total_citations"] if structured else None,
            } if structured else None,
        },
        "claim_coverage": claim_coverage,  # null until at least one call has hand-labeled ground truth
    }


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
