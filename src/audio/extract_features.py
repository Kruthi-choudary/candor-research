import json
from pathlib import Path

import librosa
import numpy as np

TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "transcripts"
AUDIO_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "audio"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "audio_features"
SAMPLE_RATE = 16000
PITCH_FMIN = 75
PITCH_FMAX = 500


def extract_segment_features(y: np.ndarray, sr: int, start: float, end: float, prev_end: float, word_count: int) -> dict:
    start_sample = int(start * sr)
    end_sample = int(end * sr)
    y_seg = y[start_sample:end_sample]
    duration = end - start

    features = {
        "pause_before_sec": round(start - prev_end, 3) if prev_end is not None else None,
        "speaking_rate_wps": round(word_count / duration, 2) if duration > 0 else None,
        "mean_pitch_hz": None,
        "pitch_std_hz": None,
        "mean_energy": None,
    }

    if len(y_seg) < sr * 0.1:
        return features

    try:
        rms = librosa.feature.rms(y=y_seg)
        features["mean_energy"] = round(float(np.mean(rms)), 5)
    except Exception:
        pass

    try:
        f0, voiced_flag, _ = librosa.pyin(y_seg, fmin=PITCH_FMIN, fmax=PITCH_FMAX, sr=sr)
        voiced_f0 = f0[voiced_flag]
        if len(voiced_f0) > 0:
            features["mean_pitch_hz"] = round(float(np.mean(voiced_f0)), 2)
            features["pitch_std_hz"] = round(float(np.std(voiced_f0)), 2)
    except Exception:
        pass

    return features


def extract_features_for_call(segments: list, audio_path: Path) -> list:
    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE)
    scored_segments = []
    prev_end = None
    for seg in segments:
        word_count = len(seg["text"].split())
        features = extract_segment_features(y, sr, seg["start"], seg["end"], prev_end, word_count)
        scored_segments.append({**seg, "audio_features": features})
        prev_end = seg["end"]
    return scored_segments


def run():
    for ticker_dir in sorted(TRANSCRIPTS_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name
        out_dir = OUTPUT_DIR / ticker
        out_dir.mkdir(parents=True, exist_ok=True)

        for transcript_path in sorted(ticker_dir.glob("*.json")):
            quarter = transcript_path.stem
            out_path = out_dir / f"{quarter}.json"
            if out_path.exists():
                print(f"{ticker} {quarter}: already extracted, skipping")
                continue

            audio_path = AUDIO_DIR / ticker / f"{quarter}.mp3"
            if not audio_path.exists():
                print(f"{ticker} {quarter}: no audio file found, skipping")
                continue

            with open(transcript_path) as f:
                segments = json.load(f)["segments"]

            print(f"{ticker} {quarter}: extracting features for {len(segments)} segments...")
            scored_segments = extract_features_for_call(segments, audio_path)

            with open(out_path, "w") as f:
                json.dump({"segments": scored_segments}, f, indent=2)
            print(f"  -> {out_path}")


if __name__ == "__main__":
    run()
