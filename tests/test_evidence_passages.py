"""Evidence regressions using saved text; no audio, model or network calls."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.report.evidence import (
    EVIDENCE_POLICY, MAX_SEGMENTS, ends_sentence, passage_at, select_evidence_passages,
)
from src.eval import check_citations_structured as checker

ROOT = Path(__file__).resolve().parents[1]


def segment(text, start, label=None, score=0.9, **extra):
    return {"text": text, "start": start, "end": start + 1,
            "sentiment": {"label": label, "score": score} if label else None, **extra}


class PassageTests(unittest.TestCase):
    def test_split_range_preserves_unscored_continuation(self):
        segments = [
            segment("Revenue is expected to grow low to", 10, "negative"),
            segment("mid-single digits year-over-year.", 11),
        ]
        positive, negative = select_evidence_passages(segments, 4)
        self.assertEqual(positive, [])
        self.assertEqual(negative[0]["text"], "Revenue is expected to grow low to mid-single digits year-over-year.")
        self.assertEqual((negative[0]["start"], negative[0]["end"]), (10, 12))

    def test_expands_backwards_to_recover_negation_and_qualifications(self):
        segments = [segment("We do not expect", 0),
                    segment("revenue growth to remain strong next quarter.", 1, "positive")]
        positive, _ = select_evidence_passages(segments, 4)
        self.assertEqual(positive[0]["start"], 0)
        self.assertTrue(positive[0]["text"].startswith("We do not expect revenue growth"))

    def test_whole_segments_are_preserved_and_input_is_not_mutated(self):
        segments = [segment("Revenue grew. However, our next quarter", 0, "positive"),
                    segment("may be weaker.", 1, "negative")]
        original = json.dumps(segments)
        positive, negative = select_evidence_passages(segments, 4)
        self.assertEqual(len(positive) + len(negative), 1)
        self.assertEqual(positive[0]["text"], "Revenue grew. However, our next quarter may be weaker.")
        self.assertEqual(json.dumps(segments), original)

    def test_abbreviations_and_ellipses_are_not_sentence_boundaries(self):
        for text in ["the U.S.", "Dr.", "Apple Inc.", "continued...", "continued…"]:
            self.assertFalse(ends_sentence(text), text)
        self.assertTrue(ends_sentence('Growth was 2.5%."'))
        segments = [segment("We spoke with Dr.", 0), segment("Smith about revenue growth next quarter.", 1, "positive")]
        self.assertEqual(passage_at(segments, 1)["start"], 0)

    def test_does_not_cross_gap_empty_text_or_known_speaker_change(self):
        for tail in [segment("mid-single digits.", 6),
                     segment("", 1),
                     segment("mid-single digits.", 1, speaker="analyst")]:
            with self.subTest(tail=tail):
                segments = [segment("Revenue is expected to grow low to", 0, "positive"), tail]
                self.assertIsNone(passage_at(segments, 0))
        backwards = [segment("We do not expect", 0),
                     segment("revenue growth to remain strong next quarter.", 6, "positive")]
        self.assertIsNone(passage_at(backwards, 1))

    def test_unfinished_tail_and_oversized_passages_are_skipped(self):
        cases = [
            [segment("Revenue is expected to grow low to", 0, "positive")],
            [segment("continuing without punctuation", i) for i in range(MAX_SEGMENTS + 1)],
            [segment("word " * 221 + ".", 0, "positive")],
            [{**segment("Revenue rose.", 0, "positive"), "end": 91}],
        ]
        for segments in cases:
            with self.subTest(length=len(segments)):
                self.assertIsNone(passage_at(segments, 0))

    def test_rank_limits_and_deduplication_apply_across_sentiment_groups(self):
        segments = [segment("We expect revenue to grow low to", 0, "negative", .99),
                    segment("mid-single digits with a strong services performance.", 1, "positive", .98),
                    segment("Profit was higher than in the previous quarter.", 2, "positive", .97)]
        positive, negative = select_evidence_passages(segments, 1)
        self.assertEqual(len(positive), 1)
        self.assertEqual(len(negative), 1)
        self.assertEqual(positive[0]["start"], 2)
        self.assertEqual(negative[0]["start"], 0)
        self.assertEqual(select_evidence_passages(segments, 0), ([], []))

    def test_actual_apple_fragment_is_completed(self):
        segments = json.loads((ROOT / "data/processed/sentiment/segment/AAPL/Q1_2025.json").read_text())["segments"]
        _, negative = select_evidence_passages(segments, 4)
        growth = next(p for p in negative if "March quarter" in p["text"])
        self.assertIn("grow low to mid-single digits year-over-year.", growth["text"])
        self.assertEqual(growth["start"], 1256.3)

    def test_all_included_calls_have_traceable_nonoverlapping_passages(self):
        paths = list((ROOT / "data/processed/sentiment/segment").glob("*/*.json"))
        self.assertEqual(len(paths), 16)
        for path in paths:
            segments = json.loads(path.read_text())["segments"]
            groups = select_evidence_passages(segments, 4)
            occupied = set()
            with self.subTest(call=str(path)):
                self.assertTrue(any(groups))
                for group in groups:
                    self.assertLessEqual(len(group), 4)
                    for passage in group:
                        left, right = passage["segment_start"], passage["segment_end"]
                        self.assertEqual(passage["text"], " ".join(s["text"].strip() for s in segments[left:right + 1]))
                        self.assertTrue(ends_sentence(passage["text"]))
                        self.assertEqual(passage["start"], segments[left]["start"])
                        matched = checker.find_segment_at(segments, int(passage["start"]), passage["text"], True)
                        self.assertIsNotNone(matched)
                        self.assertEqual(matched["text"], passage["text"])
                        covered = set(range(left, right + 1))
                        self.assertFalse(occupied & covered)
                        occupied.update(covered)


class CitationTests(unittest.TestCase):
    def test_new_policy_checks_complete_text_and_copied_timestamp(self):
        segments = [segment("Revenue is expected to grow low to", 10, "negative"),
                    segment("mid-single digits year-over-year.", 11)]
        full = passage_at(segments, 0)["text"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AAPL").mkdir()
            (root / "AAPL/Q1_2025.json").write_text(json.dumps({"segments": segments}))
            reports = root / "reports"
            (reports / "AAPL").mkdir(parents=True)
            report_path = reports / "AAPL/Q1_2025.json"
            for text, timestamp, expected in [
                (full, 10, "VERIFIED"),
                (segments[0]["text"], 10, "TEXT_MISMATCH"),
                (full.replace("mid-single", "double"), 10, "TEXT_MISMATCH"),
                (full, 9, "TIMESTAMP_NOT_FOUND"),
                (full, 11, "TIMESTAMP_NOT_FOUND"),
            ]:
                with self.subTest(text=text, timestamp=timestamp):
                    report_path.write_text(json.dumps({"evidence_policy": EVIDENCE_POLICY, "claims": [
                        {"claim": "Growth guidance.", "citation": {"source_text": text, "timestamp_sec": timestamp}}
                    ]}))
                    with patch.object(checker, "REPORTS_DIR", reports), patch.object(checker, "SENTIMENT_DIR", root):
                        result = checker.check_report("AAPL", "Q1_2025")
                    self.assertEqual(result["citations"][0]["verdict"], expected)

    def test_legacy_saved_reports_keep_their_original_matching_results(self):
        for path in checker.REPORTS_DIR.glob("*/*.json"):
            if json.loads(path.read_text()).get("evidence_policy") == EVIDENCE_POLICY:
                continue
            result = checker.check_report(path.parent.name, path.stem)
            saved = json.loads((ROOT / "data/processed/eval/per_call" / path.parent.name / path.name).read_text())
            self.assertEqual(result["verified"], saved["verified"], str(path))
            self.assertEqual(result["total_citations"], saved["total_citations"], str(path))


class GenerationTests(unittest.TestCase):
    def setUp(self):
        try:
            from src.report import generate_structured_report as generation
        except ImportError:
            self.skipTest("Optional generation dependencies not installed")
        self.generation = generation

    def test_model_selects_source_id_and_code_binds_exact_citation(self):
        generation = self.generation
        segments = [segment("Revenue is expected to grow low to", 10, "negative"),
                    segment("mid-single digits year-over-year.", 11)]
        full = passage_at(segments, 0)["text"]
        seen = []

        def complete(**kwargs):
            seen.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "claims": [{"claim": "Growth guidance is low to mid-single digits.", "sentiment": "positive",
                            "source_id": "P1"}],
                "overall_summary": "Growth guidance.",
            })))])

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))
        with patch.object(generation, "load_segments", return_value=segments):
            result = generation.generate_structured("AAPL", "Q1_2025", client)
            self.assertIn(full, seen[0]["messages"][0]["content"])
            self.assertIn("independently of the selection group", seen[0]["messages"][0]["content"])
            source_enum = seen[0]["response_format"]["json_schema"]["schema"]["properties"]["claims"]["items"]["properties"]["source_id"]["enum"]
            self.assertEqual(source_enum, ["P1"])
            self.assertEqual(result["claims"][0]["citation"], {"timestamp_sec": 10, "source_text": full})
            self.assertEqual(result["evidence_policy"], EVIDENCE_POLICY)
            self.assertEqual(result["generation_provenance"]["selection"]["citation_binding"],
                             "source_id_to_exact_selected_passage_v1")

            def unknown(**kwargs):
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                    "claims": [{"claim": "Wrong source.", "sentiment": "neutral", "source_id": "P9"}],
                    "overall_summary": "Wrong source.",
                })))])

            client.chat.completions.create = unknown
            with self.assertRaisesRegex(generation.PipelineError, "unknown or repeated"):
                generation.generate_structured("AAPL", "Q1_2025", client)


if __name__ == "__main__":
    unittest.main()
