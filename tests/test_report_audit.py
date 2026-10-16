"""Offline audit and resumable queue regressions; no model calls or new labels."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common.errors import PipelineError
from src.eval.audit_reports import ROOT, audit_reports, context_issues, date_source_matches
from src.eval.check_citations_structured import evaluate_report, find_segment_at
from src.report.regenerate_remaining import pending_calls, stage_remaining


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = audit_reports()

    def test_all_recorded_dates_have_consistent_primary_source_records(self):
        self.assertEqual(len(self.audit["reports"]), 16)
        self.assertTrue(all(r["date_source_record_matches"] for r in self.audit["reports"]))
        self.assertTrue(all(r["report_date_matches_registry"] for r in self.audit["reports"]))

    def test_audit_is_deterministic_and_does_not_rewrite_inputs(self):
        first = self.audit
        self.assertEqual(first, audit_reports())
        for path, expected in first["input_sha256"].items():
            import hashlib
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)

    def test_corrected_apple_is_excluded_from_legacy_queue(self):
        apple = next(r for r in self.audit["reports"] if (r["ticker"], r["quarter"]) == ("AAPL", "Q1_2025"))
        self.assertFalse(apple["needs_regeneration"])
        self.assertEqual(apple["incomplete_or_nonexact_passage_claim_indices"], [])
        self.assertEqual(apple["historical_context_issues"], [])
        self.assertNotIn(apple, pending_calls(self.audit))

    def test_claim_and_saved_evaluation_consistency_remains_separate_from_completeness(self):
        self.assertTrue(all(r["saved_citation_evaluation_matches"] for r in self.audit["reports"]))
        self.assertTrue(all(r["report_claims_and_summary_agree"] for r in self.audit["reports"]))
        self.assertEqual(self.audit["summary"]["incomplete_or_nonexact_passages"], 0)
        segments = [
            {"start": 1.0, "end": 1.5, "text": "Revenue was"},
            {"start": 1.6, "end": 2.0, "text": "up 5%."},
        ]
        legacy = {"claims": [{"claim": "Revenue rose 5%", "citation": {
            "timestamp_sec": 1, "source_text": "Revenue was"}}]}
        self.assertEqual(evaluate_report("TEST", "Q1_2025", legacy, segments)["verified"], 1)
        complete = find_segment_at(segments, 1, "Revenue was", require_complete=True)
        self.assertEqual(complete["text"], "Revenue was up 5%.")
        self.assertNotEqual(legacy["claims"][0]["citation"]["source_text"], complete["text"])

    def test_invalid_or_changed_date_source_records_fail_closed(self):
        sources = json.loads((ROOT / "data/processed/call_date_sources.json").read_text())
        for change in [lambda x: x.update(call_date="2025-01-29"),
                       lambda x: x.update(status="unverified"),
                       lambda x: x.update(checked_on="invalid")]:
            modified = copy.deepcopy(sources)
            change(modified["calls"]["AAPL"]["Q1_2025"])
            self.assertFalse(date_source_matches("AAPL", "Q1_2025", "2025-01-30", modified))
        self.assertFalse(date_source_matches("UNKNOWN", "Q1_2025", "2025-01-30", sources))

    def test_context_requires_earlier_date_and_exact_source_at_timestamp(self):
        dates = {"AAPL": {"Q4_2024": "2024-10-31", "Q1_2025": "2025-01-30", "Q2_2025": "2025-05-01"}}
        load = lambda ticker, quarter: {"segments": [{"start": 10.1, "text": "Earlier evidence."}]}
        good = {"quarter": "Q4 2024", "start_sec": 10.1, "text": "Earlier evidence."}
        self.assertEqual(context_issues("AAPL", "Q1_2025", [good], dates, load), [])
        for altered in [{**good, "quarter": "Q2 2025"}, {**good, "start_sec": 9},
                        {**good, "text": "Text from another call."}, {**good, "quarter": "Q4 2020"}]:
            with self.subTest(context=altered):
                self.assertTrue(context_issues("AAPL", "Q1_2025", [altered], dates, load))


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.audit = {
            "reports": [{"ticker": "AAPL", "quarter": q, "call_date": d, "needs_regeneration": True,
                         "ready_to_stage": True, "report_date_matches_registry": True}
                        for q, d in [("Q4_2024", "2024-10-31"), ("Q1_2025", "2025-01-30")]],
            "input_sha256": {f"data/processed/{folder}/AAPL/{q}.json": "source-hash"
                             for folder in ("transcripts", "sentiment/segment", "pipeline_runs")
                             for q in ("Q4_2024", "Q1_2025")},
        }

    def generate(self, ticker, quarter, *, include_history):
        return {"report": {"ticker": ticker, "quarter": quarter.replace("_", " "), "regeneration": {
            "historical_context": "none_returned" if include_history else "explicitly_omitted",
            "provenance": {"input_sha256": {p: h for p, h in self.audit["input_sha256"].items() if quarter in p}},
        }}, "review": {"status": "pending"}}

    def test_limit_and_resume_do_not_overwrite_previously_staged_candidates(self):
        first = stage_remaining(self.audit, self.output, self.generate, include_history=False, limit=1)
        self.assertEqual(len(first), 1)
        original = Path(first[0]).read_bytes()
        second = stage_remaining(self.audit, self.output, self.generate, include_history=False, limit=1)
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first, second)
        self.assertEqual(Path(first[0]).read_bytes(), original)
        self.assertEqual(stage_remaining(self.audit, self.output, self.generate, include_history=False), [])

    def test_first_failure_stops_new_requests_and_keeps_completed_candidates(self):
        generated = []

        def fail_second(t, q, **kwargs):
            generated.append(q)
            if len(generated) == 2:
                raise PipelineError("Provider unavailable")
            return self.generate(t, q, **kwargs)

        with patch("src.report.regenerate_remaining.time.sleep"):
            with self.assertRaisesRegex(PipelineError, "Provider unavailable"):
                stage_remaining(self.audit, self.output, fail_second, include_history=False)
        self.assertEqual(len(generated), 2)
        self.assertEqual(len(list(self.output.glob("*/*.json"))), 1)

    def test_bad_inputs_context_mode_and_stale_candidates_are_not_silently_accepted(self):
        self.audit["reports"][0]["ready_to_stage"] = False
        with self.assertRaisesRegex(PipelineError, "audited input"):
            pending_calls(self.audit)
        self.audit["reports"][0]["ready_to_stage"] = True
        stage_remaining(self.audit, self.output, self.generate, include_history=False, limit=1)
        with self.assertRaisesRegex(PipelineError, "different historical-context mode"):
            stage_remaining(self.audit, self.output, self.generate, include_history=True)
        path = self.output / "AAPL/Q4_2024.json"
        candidate = json.loads(path.read_text())
        candidate["report"]["regeneration"]["provenance"]["input_sha256"] = {}
        path.write_text(json.dumps(candidate))
        with self.assertRaisesRegex(PipelineError, "stale or unrecorded"):
            stage_remaining(self.audit, self.output, self.generate, include_history=False)


if __name__ == "__main__":
    unittest.main()
