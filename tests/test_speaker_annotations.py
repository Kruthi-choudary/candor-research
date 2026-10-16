"""Provisional handoff records must not silently become baseline-ready labels."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.common.manifest import ROOT
from src.speakers.annotations import validate_annotation, validate_collection
from src.speakers.review_packet import clip_window, review_items


FILES = sorted((ROOT / "data/processed/speaker_annotations/pilot/NVDA").glob("*.json"))


class SpeakerAnnotationTests(unittest.TestCase):
    def altered(self, data):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "annotation.json"
        path.write_text(json.dumps(data))
        return path

    def test_pilot_is_source_bound_and_has_no_baseline_eligible_segments(self):
        self.assertEqual(len(FILES), 2)
        summaries = validate_collection(FILES)
        self.assertEqual(sum(s["labeled_segments"] for s in summaries), 507)
        self.assertTrue(all(not s["audio_identity_verified"] and s["baseline_eligible_segments"] == 0
                            for s in summaries))

    def test_stale_audio_or_transcript_is_rejected(self):
        original = json.loads(FILES[0].read_text())
        for key in ("audio_sha256", "transcript_sha256"):
            modified = copy.deepcopy(original)
            modified[key] = "0" * 64
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "changed"):
                validate_annotation(self.altered(modified))

    def test_overlap_and_unverified_baseline_use_are_rejected(self):
        original = json.loads(FILES[0].read_text())
        overlapping = copy.deepcopy(original)
        overlapping["turns"][1]["start_segment"] -= 1
        with self.assertRaisesRegex(ValueError, "nonoverlapping"):
            validate_annotation(self.altered(overlapping))
        premature = copy.deepcopy(original)
        premature["turns"][1]["usable_for_baseline"] = True
        with self.assertRaisesRegex(ValueError, "baseline use"):
            validate_annotation(self.altered(premature))

    def test_conflicting_cross_call_identity_is_rejected(self):
        changed = json.loads(FILES[1].read_text())
        named = next(t for t in changed["turns"] if t["speaker_id"] == "nvda:colette_kress")
        named["speaker_display_name"] = "Another Person"
        with self.assertRaisesRegex(ValueError, "conflicts across calls"):
            validate_collection([FILES[0], self.altered(changed)])

    def test_review_packet_covers_handoffs_and_unlabeled_boundaries(self):
        records = [json.loads(path.read_text()) for path in FILES]
        items = review_items(records)
        self.assertEqual(len(items), 7)
        self.assertEqual(
            {item["boundary_segment"] for item in items if item["quarter"] == "Q1_2025"},
            {9, 38, 262, 308},
        )
        self.assertEqual(clip_window(5), (0.0, 17.0))
        for item in items:
            start, duration = clip_window(item["boundary_sec"])
            self.assertLess(start, item["boundary_sec"])
            self.assertGreater(start + duration, item["boundary_sec"])


if __name__ == "__main__":
    unittest.main()
