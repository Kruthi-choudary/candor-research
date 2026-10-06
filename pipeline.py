"""Candor end-to-end pipeline for a single earnings call.

    python pipeline.py --ticker NVDA --quarter Q1-2025
    python pipeline.py --ticker NVDA --date 2024-05-22

Stages: audio -> transcription -> sentiment -> prosody -> RAG context -> LLM report
-> citation verification -> standardized JSON (src/common/schema.py).

Only operates on calls Candor already has audio for (data/raw/audio/{TICKER}/{QUARTER}.mp3) —
it does not download new audio. Each stage's intermediate output is cached to disk and reused
on a later run unless --force is passed.
"""
import argparse
import json
import logging
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from src.common.errors import PipelineError
from src.common.logging_setup import setup_logging
from src.common.manifest import resolve_call
from src.common.schema import build_report
from src.data.transcribe import transcribe_file, load_model as load_whisper_model
from src.nlp.sentiment import score_segments, load_classifier
from src.audio.extract_features import extract_features_for_call
from src.rag.build_index import query_prior_quarters
from src.report.generate_report import sentiment_distribution
from src.report.generate_structured_report import generate_structured
from src.eval.check_citations_structured import check_report

ENV_PATH = Path(__file__).parent / ".env"
logger = logging.getLogger("candor.pipeline")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _audio_feature_summary(scored_segments: list) -> dict:
    def avg(key):
        values = [s["audio_features"][key] for s in scored_segments if s["audio_features"].get(key) is not None]
        return round(sum(values) / len(values), 2) if values else None

    return {
        "mean_pitch_hz": avg("mean_pitch_hz"),
        "mean_energy": avg("mean_energy"),
        "mean_speaking_rate_wps": avg("speaking_rate_wps"),
        "segments_analyzed": len(scored_segments),
    }


def run_pipeline(ticker: str, quarter: str = None, date: str = None, force: bool = False) -> dict:
    call = resolve_call(ticker, quarter=quarter, date=date)
    logger.info(f"Starting {call.ticker} {call.quarter}")
    durations = {}

    if not call.audio_path.exists():
        raise PipelineError(
            f"No audio found for {call.ticker} {call.quarter} at {call.audio_path}. "
            f"Candor does not download audio automatically — it must be added manually first."
        )

    # Stage 1: Transcription
    t0 = time.monotonic()
    if call.transcript_path.exists() and not force:
        transcript = json.loads(call.transcript_path.read_text())
        logger.info("Transcript already exists, reusing cached result")
    else:
        model = load_whisper_model()
        transcript = transcribe_file(model, call.audio_path)
        if not transcript["segments"]:
            raise PipelineError(
                f"Transcription produced zero segments for {call.ticker} {call.quarter} — audio may be empty or corrupt."
            )
        _write_json(call.transcript_path, transcript)
    durations["transcription_sec"] = round(time.monotonic() - t0, 1)
    logger.info(f"Transcription completed: {durations['transcription_sec']}s ({len(transcript['segments'])} segments)")

    # Stage 2: Sentiment
    t0 = time.monotonic()
    if call.sentiment_path.exists() and not force:
        sentiment_result = json.loads(call.sentiment_path.read_text())
        logger.info("Sentiment already scored, reusing cached result")
    else:
        classifier = load_classifier()
        sentiment_result = {"segments": score_segments(classifier, transcript["segments"])}
        _write_json(call.sentiment_path, sentiment_result)
    durations["sentiment_sec"] = round(time.monotonic() - t0, 1)
    logger.info(f"Sentiment analysis completed: {durations['sentiment_sec']}s")

    scored_segments = [s for s in sentiment_result["segments"] if s["sentiment"]]
    if not scored_segments:
        raise PipelineError(
            f"No scored segments for {call.ticker} {call.quarter} — transcript may be entirely non-speech or too short."
        )

    # Stage 3: Prosody
    t0 = time.monotonic()
    if call.audio_features_path.exists() and not force:
        prosody_segments = json.loads(call.audio_features_path.read_text())["segments"]
        logger.info("Audio features already extracted, reusing cached result")
    else:
        prosody_segments = extract_features_for_call(transcript["segments"], call.audio_path)
        _write_json(call.audio_features_path, {"segments": prosody_segments})
    durations["prosody_sec"] = round(time.monotonic() - t0, 1)
    logger.info(f"Prosodic feature extraction completed: {durations['prosody_sec']}s")
    audio_summary = _audio_feature_summary(prosody_segments)

    # Stage 4: RAG — best-effort cross-quarter context (see query_prior_quarters docstring)
    t0 = time.monotonic()
    prior_context = query_prior_quarters(call.ticker, exclude_quarter=call.quarter)
    durations["rag_sec"] = round(time.monotonic() - t0, 1)
    logger.info(f"Retrieved {len(prior_context)} prior-quarter context chunks")

    # Stage 5: LLM report generation
    t0 = time.monotonic()
    if call.claims_path.exists() and not force:
        structured_claims = json.loads(call.claims_path.read_text())
        logger.info("Claims already generated, reusing cached result")
    else:
        load_dotenv(ENV_PATH)
        client = Groq()
        structured_claims = generate_structured(call.ticker, call.quarter, client, prior_context=prior_context)
        _write_json(call.claims_path, structured_claims)
    durations["generation_sec"] = round(time.monotonic() - t0, 1)
    logger.info(f"LLM generation completed: {durations['generation_sec']}s ({len(structured_claims['claims'])} claims)")

    # Stage 6: Citation verification
    t0 = time.monotonic()
    citation_eval = check_report(call.ticker, call.quarter)
    _write_json(call.citation_eval_path, citation_eval)
    durations["citation_check_sec"] = round(time.monotonic() - t0, 1)
    accuracy_pct = f"{citation_eval['accuracy'] * 100:.1f}%" if citation_eval["accuracy"] is not None else "N/A"
    logger.info(f"Citation verification: {citation_eval['verified']}/{citation_eval['total_citations']} verified ({accuracy_pct})")

    # Final standardized output (src/common/schema.py is the contract)
    distribution = sentiment_distribution(scored_segments)
    report = build_report(
        call_ref=call,
        structured_claims=structured_claims,
        sentiment_distribution=distribution,
        citation_eval=citation_eval,
        audio_feature_summary=audio_summary,
        prior_quarter_context=prior_context,
        stage_durations_sec=durations,
    )
    _write_json(call.pipeline_output_path, report)
    logger.info(f"Pipeline complete -> {call.pipeline_output_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Run the Candor earnings-call pipeline for one ticker + quarter.")
    parser.add_argument("--ticker", required=True, help="e.g. NVDA")
    parser.add_argument("--quarter", help="e.g. Q1-2025, Q1_2025, or 'Q1 2025'")
    parser.add_argument("--date", help="Call date as YYYY-MM-DD, alternative to --quarter")
    parser.add_argument("--force", action="store_true", help="Recompute every stage even if cached output already exists")
    args = parser.parse_args()

    setup_logging()
    try:
        report = run_pipeline(args.ticker, quarter=args.quarter, date=args.date, force=args.force)
    except PipelineError as e:
        logger.error(str(e))
        raise SystemExit(1)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
