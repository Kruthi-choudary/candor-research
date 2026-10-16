"""Validate source-bound, provisional speaker annotations.

An explicit transcript handoff is useful evidence for preparing a review queue,
but it does not establish audio identity. These records are never inputs to
executive baselines until a separate recording-level review is implemented.
"""

import argparse
import hashlib
import json
from pathlib import Path

from src.common.manifest import ROOT


ANNOTATIONS = ROOT / "data/processed/speaker_annotations/pilot"
ROLES = {"operator", "investor_relations", "executive"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_annotation(path: Path, *, root: Path = ROOT) -> dict:
    record = json.loads(path.read_text())
    if record.get("schema_version") != "1.0" or record.get("status") != "transcript_handoff_provisional":
        raise ValueError("Only provisional speaker-annotation schema 1.0 is supported")
    ticker, quarter = record["ticker"], record["quarter"]
    transcript_path = root / "data/processed/transcripts" / ticker / f"{quarter}.json"
    audio_path = root / "data/raw/audio" / ticker / f"{quarter}.mp3"
    if sha256(transcript_path) != record["transcript_sha256"] or sha256(audio_path) != record["audio_sha256"]:
        raise ValueError("Transcript or audio has changed since annotation")
    segments = json.loads(transcript_path.read_text())["segments"]
    if not segments or not record["turns"]:
        raise ValueError("Annotation has no transcript or turns")
    expected_start = 0
    for turn in record["turns"]:
        start, end = turn["start_segment"], turn["end_segment_exclusive"]
        if not isinstance(start, int) or not isinstance(end, int) or start != expected_start or not start < end <= len(segments):
            raise ValueError("Speaker turns must cover a nonoverlapping transcript prefix")
        if turn["role"] not in ROLES or turn["identity_status"] != "provisional_from_transcript_handoff":
            raise ValueError("Invalid role or unverified identity status")
        if turn["audio_identity_checked"] or turn["usable_for_baseline"]:
            raise ValueError("A transcript handoff cannot authorize audio identity or baseline use")
        if turn["role"] == "operator" and turn["speaker_id"] is not None:
            raise ValueError("The operator's first name is not a verified cross-call identity")
        if turn["role"] != "operator" and (not turn["speaker_id"] or not turn["role_source_url"].startswith("https://")):
            raise ValueError("Named speaker turn needs an identity key and role source")
        anchor = turn["handoff_evidence"]["segment_index"]
        quote = turn["handoff_evidence"]["source_text"]
        if not isinstance(anchor, int) or not 0 <= anchor < len(segments) or not quote or quote not in segments[anchor]["text"]:
            raise ValueError("Handoff evidence does not match the saved transcript")
        if not ((start == 0 and anchor == 0) or (start > 0 and max(0, start - 2) <= anchor < start)):
            raise ValueError("Handoff evidence is not next to the speaker turn")
        if not turn["review_note"]:
            raise ValueError("Every turn requires a review note")
        expected_start = end
    if expected_start != record["unlabeled_from_segment"] or expected_start >= len(segments):
        raise ValueError("Unlabeled boundary must start after the annotated prefix")
    return {
        "ticker": ticker,
        "quarter": quarter,
        "labeled_segments": expected_start,
        "total_segments": len(segments),
        "audio_identity_verified": False,
        "baseline_eligible_segments": 0,
    }


def validate_collection(paths: list[Path], *, root: Path = ROOT) -> list[dict]:
    summaries = []
    identities = {}
    for path in paths:
        summaries.append(validate_annotation(path, root=root))
        for turn in json.loads(path.read_text())["turns"]:
            key = turn["speaker_id"]
            if key is None:
                continue
            identity = (turn["speaker_display_name"], turn["role"])
            if key in identities and identities[key] != identity:
                raise ValueError(f"Speaker identity conflicts across calls: {key}")
            identities[key] = identity
    return summaries


def main():
    parser = argparse.ArgumentParser(description="Validate provisional speaker-turn annotations against saved sources")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    paths = args.paths or sorted(ANNOTATIONS.glob("*/*.json"))
    if not paths:
        parser.error("No annotation files found")
    for summary in validate_collection(paths):
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
