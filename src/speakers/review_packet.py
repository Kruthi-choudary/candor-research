"""Make a local listening packet for the provisional Nvidia speaker pilot.

The packet is a review aid, not evidence that any voice has been identified.
It never changes annotations or marks segments as baseline eligible.
"""

import argparse
import html
import json
import subprocess
from pathlib import Path

from src.common.manifest import ROOT
from src.speakers.annotations import ANNOTATIONS, validate_collection


def review_items(records: list[dict], root: Path = ROOT) -> list[dict]:
    items = []
    for record in records:
        ticker, quarter = record["ticker"], record["quarter"]
        segments = json.loads((root / "data/processed/transcripts" / ticker / f"{quarter}.json").read_text())["segments"]
        for turn in record["turns"][1:]:
            index = turn["start_segment"]
            items.append({
                "id": f"{ticker}-{quarter}-{index}",
                "label": f"{ticker} {quarter}: handoff to {turn['speaker_display_name']}",
                "ticker": ticker,
                "quarter": quarter,
                "boundary_segment": index,
                "boundary_sec": segments[index]["start"],
                "excerpt": [(j, segments[j]["text"]) for j in range(max(0, index - 2), min(len(segments), index + 3))],
            })
        index = record["unlabeled_from_segment"]
        items.append({
            "id": f"{ticker}-{quarter}-{index}-qa",
            "label": f"{ticker} {quarter}: prepared remarks / Q&A boundary (unlabeled)",
            "ticker": ticker,
            "quarter": quarter,
            "boundary_segment": index,
            "boundary_sec": segments[index]["start"],
            "excerpt": [(j, segments[j]["text"]) for j in range(max(0, index - 2), min(len(segments), index + 3))],
        })
    return items


def clip_window(boundary_sec: float) -> tuple[float, float]:
    start = max(0.0, boundary_sec - 10.0)
    return start, boundary_sec + 12.0 - start


def make_packet(output: Path, *, root: Path = ROOT) -> list[dict]:
    paths = sorted((root / "data/processed/speaker_annotations/pilot").glob("*/*.json"))
    validate_collection(paths, root=root)
    records = [json.loads(path.read_text()) for path in paths]
    items = review_items(records, root=root)
    output.mkdir(parents=True, exist_ok=True)
    for item in items:
        start, duration = clip_window(item["boundary_sec"])
        source = root / "data/raw/audio" / item["ticker"] / f"{item['quarter']}.mp3"
        destination = output / f"{item['id']}.mp3"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source),
            "-vn", "-codec:a", "libmp3lame", "-q:a", "5", str(destination),
        ], check=True)
        item["clip_start_sec"] = round(start, 3)
        item["clip_file"] = destination.name

    sections = []
    for item in items:
        excerpts = "".join(
            f"<li><small>Segment {index}</small> {html.escape(text)}</li>"
            for index, text in item["excerpt"]
        )
        sections.append(
            f"<section data-review-id='{html.escape(item['id'], quote=True)}'><h2>{html.escape(item['label'])}</h2>"
            f"<p>Transcript boundary: {item['boundary_sec']:.2f}s · Clip starts: {item['clip_start_sec']:.2f}s</p>"
            f"<audio controls preload='none' src='{html.escape(item['clip_file'], quote=True)}'></audio>"
            f"<ol>{excerpts}</ol>"
            "<p>Listen for the voice change and check whether it occurs at the proposed segment boundary. "
            "A spoken name alone does not confirm the voice's identity.</p>"
            "<label>Review note <textarea rows='2' placeholder='Voice change, boundary, uncertainty…'></textarea></label>"
            "</section>"
        )
    page = (
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Candor speaker review packet</title>"
        "<style>body{font:16px/1.55 system-ui;background:#eee4d1;color:#111113;max-width:800px;margin:auto;padding:24px}"
        "section{border-top:1px solid #b69a61;padding:24px 0}h1,h2{line-height:1.2}h2{font-size:1.25rem}"
        "audio,textarea{width:100%}li{margin:8px 0}small{color:#55514b}textarea{box-sizing:border-box}"
        "</style><h1>Candor speaker review</h1>"
        "<p>Local listening aid for provisional Nvidia prepared-remarks labels. Compare the Q4 and Q1 "
        "Colette Kress clips as well as the individual handoffs. Record uncertainty explicitly. "
        "Nothing on this page verifies a voice or changes the project data. Export your notes before closing the page.</p>"
        + "".join(sections)
        + "<button id='export-notes' type='button'>Download review notes</button>"
        "<script>document.getElementById('export-notes').addEventListener('click', () => {"
        "const notes = [...document.querySelectorAll('section[data-review-id]')].map(section => ({"
        "review_id: section.dataset.reviewId, note: section.querySelector('textarea').value.trim()}));"
        "const link = document.createElement('a');"
        "link.href = URL.createObjectURL(new Blob([JSON.stringify({status:'human_review_notes_only',notes},null,2)],"
        "{type:'application/json'})); link.download = 'speaker-review-notes.json'; link.click();"
        "setTimeout(() => URL.revokeObjectURL(link.href), 1000); });</script></html>"
    )
    (output / "index.html").write_text(page)
    (output / "manifest.json").write_text(json.dumps(items, indent=2) + "\n")
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local audio review packet for provisional speaker handoffs")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/speaker_review")
    args = parser.parse_args()
    items = make_packet(args.output)
    print(f"Generated {len(items)} review clips in {args.output / 'index.html'}")
    print("Annotations remain provisional; no segments were approved for baselines.")


if __name__ == "__main__":
    main()
