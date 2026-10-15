"""Bounded, contiguous transcript passages for new structured generation.

Punctuation is a heuristic, not a guarantee of semantic completeness or speaker identity.
Never fill gaps with invented text or drop unscored neighbours from a statement.
"""
import re

EVIDENCE_POLICY = "complete_passages_v1"
MAX_SEGMENTS = 12
MAX_WORDS = 220
MAX_DURATION_SEC = 90
MAX_GAP_SEC = 2.5


def ends_sentence(text: str) -> bool:
    text = text.strip().rstrip('\"\'”’)]}')
    if not text or text.endswith("...") or text.endswith("…"):
        return False
    # Do not mistake common abbreviations or initials for sentence boundaries.
    if re.search(r"\b(?:Mr|Mrs|Ms|Dr|Prof|Inc|Corp|Co|vs|e\.g|i\.e)\.$", text, re.I):
        return False
    if re.search(r"(?:\b[A-Za-z]\.)+$", text):
        return False
    return text.endswith((".", "!", "?"))


def adjacent(left: dict, right: dict) -> bool:
    # Permit tiny floating-point overlaps in Whisper's saved timestamps.
    gap = right["start"] - left["end"]
    if not -0.05 <= gap <= MAX_GAP_SEC:
        return False
    # Respect explicit speaker labels if supplied by a future transcription stage.
    for key in ("speaker", "speaker_id"):
        if left.get(key) != right.get(key) and (left.get(key) is not None or right.get(key) is not None):
            return False
    return bool(left["text"].strip() and right["text"].strip())


def passage_at(segments: list, anchor: int) -> dict | None:
    """Expand a seed in both directions; reject gaps, limits and unfinished edges.

    Returns full original segments with only joining whitespace changed. The start
    is the first included segment, so existing integer timestamp/audio contracts work.
    """
    left = right = anchor

    def within_limits():
        return (
            right - left + 1 <= MAX_SEGMENTS
            and segments[right]["end"] - segments[left]["start"] <= MAX_DURATION_SEC
            and sum(len(s["text"].split()) for s in segments[left:right + 1]) <= MAX_WORDS
        )

    if not segments[anchor]["text"].strip() or not within_limits():
        return None
    while left > 0 and not ends_sentence(segments[left - 1]["text"]):
        if not adjacent(segments[left - 1], segments[left]):
            return None
        left -= 1
        if not within_limits():
            return None
    while not ends_sentence(segments[right]["text"]):
        if right + 1 == len(segments) or not adjacent(segments[right], segments[right + 1]):
            return None
        right += 1
        if not within_limits():
            return None
    return {
        "start": segments[left]["start"],
        "end": segments[right]["end"],
        "text": " ".join(s["text"].strip() for s in segments[left:right + 1]),
        "segment_start": left,
        "segment_end": right,
    }


def select_evidence_passages(segments: list, k: int) -> tuple[list, list]:
    """Rank by seed sentiment, then expand and deduplicate across both groups.

    Neighbouring text is NOT rescored. The seed's label must not be presented as
    a sentiment classification of the entire joined passage or of a generated claim.
    """
    groups = {"positive": [], "negative": []}
    occupied = set()
    seeds = [
        (i, s) for i, s in enumerate(segments)
        if s.get("sentiment") and s["sentiment"]["label"] in groups
        and len(s["text"].split()) > 5
    ]
    seeds.sort(key=lambda pair: pair[1]["sentiment"]["score"], reverse=True)
    for index, seed in seeds:
        label = seed["sentiment"]["label"]
        if len(groups[label]) >= k:
            continue
        passage = passage_at(segments, index)
        if passage is None:
            continue
        covered = set(range(passage["segment_start"], passage["segment_end"] + 1))
        if covered & occupied:
            continue
        occupied.update(covered)
        groups[label].append(passage)
    return groups["positive"], groups["negative"]


if __name__ == "__main__":
    # Local inspection only: no audio, model downloads, API calls or output writes.
    import argparse
    import json
    from src.common.config import load_pipeline_config
    from src.common.manifest import resolve_call

    parser = argparse.ArgumentParser(description="Preview complete evidence passages from saved transcripts.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--quarter", required=True)
    args = parser.parse_args()
    call = resolve_call(args.ticker, quarter=args.quarter)
    segments = json.loads(call.sentiment_path.read_text())["segments"]
    positive, negative = select_evidence_passages(segments, load_pipeline_config()["generation"]["top_k_quotes"])
    print(json.dumps({
        "ticker": call.ticker, "quarter": call.quarter, "evidence_policy": EVIDENCE_POLICY,
        "positive_seed_passages": positive, "negative_seed_passages": negative,
    }, indent=2))
