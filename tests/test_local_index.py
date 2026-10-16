import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common import config
from src.common.errors import PipelineError
from src.rag.build_index import check_existing_index, index_identity, query_prior_quarters


class LocalIndexTests(unittest.TestCase):
    def test_local_database_override_preserves_shared_model_configuration(self):
        base = {"postgres": {"host": "localhost", "user": "old", "port": 5432}, "models": {"embedding": "saved-model"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pipeline.local.yaml").write_text("postgres:\n  user: zaggle\n  port: 5433\n")
            with patch.object(config, "CONFIG_DIR", root), patch.object(config, "_load_yaml", return_value=base):
                result = config.load_pipeline_config()
            self.assertEqual(result["postgres"]["port"], 5433)
            self.assertEqual(result["models"], base["models"])
            self.assertEqual(base["postgres"]["user"], "old")

    def test_algorithm_overrides_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pipeline.local.yaml").write_text("models:\n  embedding: changed\n")
            with patch.object(config, "CONFIG_DIR", root), patch.object(config, "_load_yaml", return_value={}):
                with self.assertRaises(ValueError):
                    config.load_pipeline_config()

    def test_repeat_build_is_safe_but_duplicates_or_changed_inputs_fail(self):
        identity = {"node_ids": ["one", "two"], "model": "existing"}
        self.assertFalse(check_existing_index(identity, [], None))
        self.assertTrue(check_existing_index(identity, ["one", "two"], identity))
        for stored, manifest in [(["one", "one", "two"], identity), (["one"], identity), (["one", "two"], None)]:
            with self.assertRaises(PipelineError):
                check_existing_index(identity, stored, manifest)

    def test_index_manifest_does_not_include_password(self):
        with patch("src.rag.build_index.PG_CONFIG", {"password": "private", "user": "zaggle"}):
            self.assertNotIn("password", index_identity([])["database"])

    def test_strict_history_fails_before_generation_when_retrieval_is_unavailable(self):
        with patch("src.rag.build_index._eligible_prior_quarters", return_value=["Q4_2024"]), \
             patch("src.rag.build_index._retrieve_nodes", side_effect=ConnectionError("database offline")):
            with self.assertRaisesRegex(PipelineError, "database offline"):
                query_prior_quarters("AAPL", "Q1_2025", strict=True)

        with patch("src.rag.build_index._eligible_prior_quarters", return_value=["Q4_2024"]), \
             patch("src.rag.build_index._retrieve_nodes", return_value=[]):
            with self.assertRaisesRegex(PipelineError, "no eligible passages"):
                query_prior_quarters("AAPL", "Q1_2025", strict=True)

        with patch("src.rag.build_index._eligible_prior_quarters", return_value=[]), \
             patch("src.rag.build_index._retrieve_nodes") as retrieve:
            self.assertEqual(query_prior_quarters("AAPL", "Q4_2024", strict=True), [])
            retrieve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
