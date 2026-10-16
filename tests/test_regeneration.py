"""Staged regeneration must not publish partial or unreviewed outputs."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class RegenerationTests(unittest.TestCase):
    def setUp(self):
        try:
            from src.report import regenerate
            from src.report import generate_structured_report
        except ImportError:
            self.skipTest("Optional generation dependencies not installed")
        self.regenerate = regenerate
        self.generation = generate_structured_report
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.call = SimpleNamespace(
            ticker="AAPL", quarter="Q1_2025", company_name="Apple", call_date="2025-01-30",
            pipeline_output_path=root / "served.json", sentiment_path=root / "sentiment.json",
            transcript_path=root / "transcript.json", audio_path=root / "missing.mp3",
        )
        self.segments = [{"start": 10.2, "end": 15.2, "text": "Revenue is expected to grow low to mid-single digits.",
                          "sentiment": {"label": "positive", "score": .9}}]
        self.call.pipeline_output_path.write_text(json.dumps({
            "audio_features_summary": {"mean_pitch_hz": 150},
            "prior_quarter_context_used": [{"quarter": "Q3 2025", "text": "Future leakage"}],
        }))
        self.call.sentiment_path.write_text(json.dumps({"segments": self.segments}))
        self.call.transcript_path.write_text(json.dumps({"segments": self.segments}))
        self.originals = {path: path.read_bytes() for path in root.glob("*.json")}
        self.claims = {
            "evidence_policy": "complete_passages_v1", "overall_summary": "Modest growth is expected.",
            "claims": [{"claim": "Revenue growth is expected in the low to mid-single digits.", "sentiment": "positive",
                        "citation": {"timestamp_sec": 10, "source_text": self.segments[0]["text"]}}],
        }
        self.resolve = patch.object(regenerate, "resolve_call", return_value=self.call)
        self.resolve.start()
        self.addCleanup(self.resolve.stop)
        generation = patch.object(generate_structured_report, "generate_structured", return_value=self.claims)
        self.generate = generation.start()
        self.addCleanup(generation.stop)
        retrieval = patch("src.rag.build_index.query_prior_quarters", return_value=[])
        self.retrieve = retrieval.start()
        self.addCleanup(retrieval.stop)

    def assert_originals_unchanged(self):
        for path, content in self.originals.items():
            self.assertEqual(path.read_bytes(), content)

    def test_no_audio_no_history_candidate_does_not_reuse_leaked_context_or_write_served_files(self):
        client = object()
        candidate = self.regenerate.regenerate_candidate("AAPL", "Q1-2025", client, include_history=False)
        self.assertFalse(self.call.audio_path.exists())
        self.retrieve.assert_not_called()
        self.generate.assert_called_once_with("AAPL", "Q1_2025", client, prior_context=[])
        self.assertEqual(candidate["report"]["prior_quarter_context_used"], [])
        self.assertEqual(candidate["review"]["previous_context_quarters"], ["Q3 2025"])
        self.assertEqual(candidate["report"]["regeneration"]["historical_context"], "explicitly_omitted")
        self.assertEqual(candidate["report"]["audio_features_summary"], {"mean_pitch_hz": 150})
        self.assertEqual(candidate["review"]["status"], "pending")
        self.assertEqual(candidate["citation_evaluation"]["verified"], 1)
        self.assert_originals_unchanged()

    def test_history_is_freshly_retrieved_instead_of_copied_from_saved_report(self):
        root = Path(__file__).resolve().parents[1]
        first = json.loads((root / "data/processed/transcripts/AAPL/Q4_2024.json").read_text())["segments"][0]
        context = [{"quarter": "Q4 2024", "start_sec": first["start"], "text": first["text"]}]
        self.retrieve.return_value = context
        client = object()
        candidate = self.regenerate.regenerate_candidate("AAPL", "Q1-2025", client)
        self.retrieve.assert_called_once_with("AAPL", "Q1_2025", strict=True,
                                              queries=[self.segments[0]["text"]])
        self.generate.assert_called_once_with("AAPL", "Q1_2025", client, prior_context=context)
        self.assertEqual(candidate["review"]["new_context_quarters"], ["Q4 2024"])
        self.assert_originals_unchanged()

    def test_future_or_wrong_source_context_fails_before_generation(self):
        for context in [
            {"quarter": "Q3 2025", "start_sec": 0, "text": "Later-quarter evidence."},
            {"quarter": "Q4 2024", "start_sec": 0, "text": "Not the earlier transcript's opening."},
        ]:
            with self.subTest(context=context):
                self.retrieve.return_value = [context]
                with self.assertRaisesRegex(self.regenerate.PipelineError, "source/date validation"):
                    self.regenerate.regenerate_candidate("AAPL", "Q1_2025", object())
        self.generate.assert_not_called()
        self.assert_originals_unchanged()

    def test_generation_failure_keeps_existing_files(self):
        self.generate.side_effect = self.regenerate.PipelineError("Provider unreachable")
        with self.assertRaisesRegex(self.regenerate.PipelineError, "unreachable"):
            self.regenerate.regenerate_candidate("AAPL", "Q1_2025", object(), include_history=False)
        self.assert_originals_unchanged()

    def test_input_changes_during_generation_prevent_staging(self):
        def change_source(*args, **kwargs):
            self.call.sentiment_path.write_bytes(self.call.sentiment_path.read_bytes() + b"\n")
            return self.claims

        self.generate.side_effect = change_source
        with self.assertRaisesRegex(self.regenerate.PipelineError, "inputs changed"):
            self.regenerate.regenerate_candidate("AAPL", "Q1_2025", object(), include_history=False)
        self.assertEqual(self.call.pipeline_output_path.read_bytes(), self.originals[self.call.pipeline_output_path])

    def test_generator_snapshot_must_match_the_audited_segments(self):
        self.claims["generation_provenance"] = {"input_segments_sha256": "wrong-snapshot"}
        with self.assertRaisesRegex(self.regenerate.PipelineError, "different transcript snapshot"):
            self.regenerate.regenerate_candidate("AAPL", "Q1_2025", object(), include_history=False)
        self.assert_originals_unchanged()

    def test_unmatched_citation_is_not_staged(self):
        self.claims["claims"][0]["citation"]["source_text"] = "Revenue is expected to grow low to"
        with self.assertRaisesRegex(self.regenerate.PipelineError, "unmatched citations"):
            self.regenerate.regenerate_candidate("AAPL", "Q1_2025", object(), include_history=False)
        self.assert_originals_unchanged()

    def test_stale_sentiment_text_fails_before_generation(self):
        self.call.transcript_path.write_text(json.dumps({"segments": []}))
        with self.assertRaisesRegex(self.regenerate.PipelineError, "differ from the source transcript"):
            self.regenerate.regenerate_candidate("AAPL", "Q1_2025", object(), include_history=False)
        self.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
