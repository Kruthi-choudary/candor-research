import json
from pathlib import Path
from faster_whisper import WhisperModel
from companies import COMPANIES

AUDIO_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "audio"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "transcripts"
MODEL_SIZE = "base.en"


def transcribe_file(model: WhisperModel, audio_path: Path) -> dict:
    segments, info = model.transcribe(str(audio_path), beam_size=5)
    segment_list = [
        {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
        for seg in segments
    ]
    return {
        "duration_sec": info.duration,
        "language": info.language,
        "segments": segment_list,
        "full_text": " ".join(s["text"] for s in segment_list),
    }


def run():
    print(f"Loading Whisper model ({MODEL_SIZE})...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    for ticker in COMPANIES:
        ticker_audio_dir = AUDIO_DIR / ticker
        audio_files = sorted(ticker_audio_dir.glob("*.mp3")) if ticker_audio_dir.exists() else []

        if not audio_files:
            print(f"{ticker}: no audio files found in {ticker_audio_dir}, skipping")
            continue

        out_dir = OUTPUT_DIR / ticker
        out_dir.mkdir(parents=True, exist_ok=True)

        for audio_path in audio_files:
            quarter = audio_path.stem
            out_path = out_dir / f"{quarter}.json"
            if out_path.exists():
                print(f"{ticker} {quarter}: already transcribed, skipping")
                continue

            print(f"{ticker} {quarter}: transcribing {audio_path.name}...")
            result = transcribe_file(model, audio_path)
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f"  {len(result['segments'])} segments, {result['duration_sec']:.0f}s audio → {out_path}")


if __name__ == "__main__":
    run()
