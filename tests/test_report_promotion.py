"""Versioned update acceptance: preview, validation, readback and rollback."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common.errors import PipelineError
from src.report import promote

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "data/processed/report_candidates/AAPL/Q1_2025.json"


class PromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.candidate_path = Path(cls.directory.name) / "candidate.json"
        candidate = json.loads(CANDIDATE.read_text())
        # Distinct fixture identity makes the suite reusable after the real candidate
        # is active. It does not create a new real report or make a model call.
        for key in ("report", "structured_claims"):
            candidate[key]["overall_summary"] += "\n"
        cls.candidate_path.write_bytes(promote.encoded(candidate))
        cls.plan = promote.prepare_update(cls.candidate_path)

    def temporary_plan(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        plan = {**self.plan, "root": root}
        for relative, content in plan["tracked"].items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        plan["candidate_path"] = root / "candidate.json"
        plan["candidate_path"].write_bytes(self.candidate_path.read_bytes())
        return plan

    def invalid_candidate(self, change):
        with tempfile.TemporaryDirectory() as directory:
            candidate = json.loads(self.candidate_path.read_text())
            change(candidate)
            path = Path(directory) / "invalid.json"
            path.write_bytes(promote.encoded(candidate))
            with self.assertRaises((PipelineError, ValueError)):
                promote.prepare_update(path)

    def test_preview_changes_no_served_files_and_preserves_old_bundle(self):
        for relative, content in self.plan["tracked"].items():
            self.assertEqual((ROOT / relative).read_bytes(), content)
        self.assertEqual(len(self.plan["new_files"]), 4)
        self.assertNotEqual(self.plan["manifest"]["previous"], self.plan["manifest"]["replacement"])
        self.assertTrue(self.plan["manifest"]["version"].startswith("complete-passages-"))
        self.assertFalse((ROOT / self.plan["archive_path"]).exists())

    def test_invalid_candidates_are_rejected_before_any_update(self):
        changes = [
            lambda c: c["report"].update(call_date="2025-01-29"),
            lambda c: c["report"]["key_claims"][0].update(claim="Different report claim"),
            lambda c: c["citation_evaluation"].update(verified=0),
            lambda c: c["report"].update(prior_quarter_context_used=[{"quarter": "Q3 2025", "start_sec": 0, "text": "Future"}]),
            lambda c: c["review"].update(status="pending"),
            lambda c: c["review"].update(per_claim=[]),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.invalid_candidate(change)

    def test_apply_requires_exact_candidate_and_unchanged_inputs(self):
        plan = self.temporary_plan()
        with self.assertRaisesRegex(PipelineError, "checksum"):
            promote.apply_update(plan, "0" * 64)
        path = plan["root"] / "data/processed/transcripts/AAPL/Q1_2025.json"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(PipelineError, "Input changed"):
            promote.apply_update(plan, plan["candidate_sha256"])
        self.assertFalse((plan["root"] / plan["archive_path"]).exists())

    def test_successful_apply_archives_both_versions_and_keeps_benchmarks(self):
        plan = self.temporary_plan()
        promote.apply_update(plan, plan["candidate_sha256"])
        for relative, content in plan["new_files"].items():
            self.assertEqual((plan["root"] / relative).read_bytes(), content)
        archive = json.loads((plan["root"] / plan["archive_path"]).read_text())
        self.assertEqual(archive["previous"], plan["manifest"]["previous"])
        self.assertEqual(archive["replacement"], plan["manifest"]["replacement"])
        for relative, content in plan["tracked"].items():
            if relative not in plan["new_files"]:
                self.assertEqual((plan["root"] / relative).read_bytes(), content)

    def test_partial_write_failure_rolls_back_all_changed_files(self):
        plan = self.temporary_plan()
        replace = promote.replace_file
        writes = 0

        def fail_once(path, content):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("simulated disk failure")
            replace(path, content)

        with patch.object(promote, "replace_file", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "simulated disk"):
                promote.apply_update(plan, plan["candidate_sha256"])
        self.assertFalse((plan["root"] / plan["archive_path"]).exists())
        for relative, content in plan["tracked"].items():
            self.assertEqual((plan["root"] / relative).read_bytes(), content)

    def test_demo_contains_entire_long_evidence_span(self):
        plan = self.temporary_plan()
        root = plan["root"]
        bundle = copy.deepcopy(plan["manifest"]["replacement"])
        parts = ["Management expects revenue", "to grow", "low to", "mid-single digits", "during the", "next quarter."]
        rows = [{"start": 10.9 + i, "end": 11.9 + i, "text": text} for i, text in enumerate(parts)]
        transcript_path = root / "data/processed/transcripts/AAPL/Q1_2025.json"
        transcript = json.loads(transcript_path.read_text())
        transcript["segments"] = rows
        transcript_path.write_bytes(promote.encoded(transcript))
        quote = " ".join(parts)
        claim = {"claim": "Management expects growth.", "sentiment": "neutral",
                 "citation": {"timestamp_sec": 10, "source_text": quote}}
        bundle["structured_claims"]["claims"] = [claim]
        bundle["citation_evaluation"]["citations"] = [{"verdict": "VERIFIED", "match_ratio": 1}]
        path, output = root / "override.json", root / "new-demo.json"
        path.write_bytes(promote.encoded(bundle))
        subprocess.run(["node", str(root / "frontend/scripts/build-demo.mjs"), "--override-bundle", str(path),
                        "--output", str(output)], check=True, capture_output=True)
        demo = json.loads(output.read_text())
        self.assertEqual(demo["transcripts"]["AAPL/Q1-2025"]["segments"], rows)
        self.assertEqual(demo["claims"]["AAPL/Q1-2025"]["claims"][0]["evidence"], quote)


if __name__ == "__main__":
    unittest.main()
