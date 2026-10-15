"""Historical-context regressions; no recordings, database or model calls required.

Run from the repository root:
    python -m unittest discover -s tests -v
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.rag import build_index


def node(ticker, quarter, text="Earlier evidence", start=12.5):
    return SimpleNamespace(node=SimpleNamespace(
        metadata={"ticker": ticker, "quarter": quarter, "start_sec": start},
        text=text,
    ))


class HistoricalRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.dates_path = Path(self.directory.name) / "call_dates.json"
        self.dates = {
            "AAPL": {
                "Q4_2024": "2024-10-31",
                "Q1_2025": "2025-01-30",
                "Q2_2025": "2025-05-01",
                "Q3_2025": "2025-07-31",
            },
            "MSFT": {"Q4_2024": "2024-07-30"},
        }
        self.write_dates()
        dates_patch = patch.object(build_index, "CALL_DATES_PATH", self.dates_path)
        dates_patch.start()
        self.addCleanup(dates_patch.stop)
        retrieval_patch = patch.object(build_index, "_retrieve_nodes", return_value=[])
        self.retrieve = retrieval_patch.start()
        self.addCleanup(retrieval_patch.stop)

    def write_dates(self):
        self.dates_path.write_text(json.dumps(self.dates))

    def test_eligible_quarters_are_sent_to_search_before_limiting(self):
        self.retrieve.return_value = [node("AAPL", "Q4_2024")]
        result = build_index.query_prior_quarters(" aapl ", "Q1-2025", top_k=2)
        self.retrieve.assert_called_once_with("AAPL", ["Q4_2024"], 2)
        self.assertEqual(result, [{
            "quarter": "Q4 2024", "start_sec": 12.5, "text": "Earlier evidence",
        }])

    def test_earliest_call_does_not_initialize_retrieval(self):
        self.assertEqual(build_index.query_prior_quarters("AAPL", "Q4_2024"), [])
        self.retrieve.assert_not_called()

    def test_returned_future_current_other_company_and_unknown_calls_are_rejected(self):
        self.retrieve.return_value = [
            node("AAPL", "Q3_2025"),
            node("AAPL", "Q1_2025"),
            node("MSFT", "Q4_2024"),
            node("AAPL", "Q1_2020"),  # No date in the registry.
            node(None, "Q4_2024"),
            node("AAPL", "Q4_2024", text="Eligible evidence"),
        ]
        result = build_index.query_prior_quarters("AAPL", "Q1_2025", top_k=1)
        self.assertEqual([r["text"] for r in result], ["Eligible evidence"])

    def test_chronology_uses_recorded_dates_instead_of_quarter_sorting(self):
        self.dates["AAPL"]["Q4_2024"] = "2025-06-01"
        self.dates["AAPL"]["Q2_2025"] = "2024-12-01"
        self.write_dates()
        build_index.query_prior_quarters("AAPL", "Q1_2025", top_k=2)
        self.retrieve.assert_called_once_with("AAPL", ["Q2_2025"], 2)

    def test_same_day_calls_are_excluded(self):
        self.dates["AAPL"]["Q4_2024"] = "2025-01-30"
        self.write_dates()
        self.assertEqual(build_index.query_prior_quarters("AAPL", "Q1_2025"), [])
        self.retrieve.assert_not_called()

    def test_unknown_target_date_fails_closed(self):
        with self.assertLogs("candor.rag", level="WARNING") as logs:
            self.assertEqual(build_index.query_prior_quarters("AAPL", "Q1_2026"), [])
        self.assertIn("No valid recorded call date", " ".join(logs.output))
        self.retrieve.assert_not_called()

    def test_invalid_target_dates_fail_closed(self):
        for invalid in [None, "not-a-date", "2025-02-30"]:
            with self.subTest(date=invalid):
                self.dates["AAPL"]["Q1_2025"] = invalid
                self.write_dates()
                with self.assertLogs("candor.rag", level="WARNING"):
                    self.assertEqual(build_index.query_prior_quarters("AAPL", "Q1_2025"), [])
        self.retrieve.assert_not_called()

    def test_invalid_candidate_date_is_skipped(self):
        self.dates["AAPL"]["Q4_2024"] = "not-a-date"
        self.write_dates()
        with self.assertLogs("candor.rag", level="WARNING"):
            self.assertEqual(build_index.query_prior_quarters("AAPL", "Q1_2025"), [])
        self.retrieve.assert_not_called()

    def test_missing_or_malformed_registry_does_not_fall_back_to_unfiltered_search(self):
        for content in [None, "{broken json"]:
            with self.subTest(content=content):
                if content is None:
                    self.dates_path.unlink()
                else:
                    self.dates_path.write_text(content)
                with self.assertLogs("candor.rag", level="WARNING"):
                    self.assertEqual(build_index.query_prior_quarters("AAPL", "Q1_2025"), [])
        self.retrieve.assert_not_called()

    def test_unavailable_vector_search_returns_no_context(self):
        self.retrieve.side_effect = ConnectionError("Database unavailable")
        with self.assertLogs("candor.rag", level="WARNING"):
            self.assertEqual(build_index.query_prior_quarters("AAPL", "Q1_2025"), [])

    def test_zero_limit_does_not_search_or_use_the_default(self):
        self.assertEqual(build_index.query_prior_quarters("AAPL", "Q1_2025", top_k=0), [])
        self.retrieve.assert_not_called()

    def test_results_respect_limit_and_keep_relevance_order(self):
        self.retrieve.return_value = [
            node("AAPL", "Q1_2025", text="Most relevant"),
            node("AAPL", "Q4_2024", text="Next most relevant"),
            node("AAPL", "Q2_2025", text="Third most relevant"),
        ]
        result = build_index.query_prior_quarters("AAPL", "Q3_2025", top_k=2)
        self.assertEqual([r["text"] for r in result], ["Most relevant", "Next most relevant"])


class IncludedDatasetTests(unittest.TestCase):
    def test_each_company_has_zero_then_one_two_three_historical_calls(self):
        quarters = ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"]
        for ticker in ["AAPL", "MSFT", "NVDA", "META"]:
            for i, quarter in enumerate(quarters):
                with self.subTest(ticker=ticker, quarter=quarter):
                    self.assertEqual(build_index._eligible_prior_quarters(ticker, quarter), quarters[:i])


class VectorAdapterTests(unittest.TestCase):
    def test_adapter_applies_company_and_quarter_filters_before_top_k(self):
        # Optional integration with the installed LlamaIndex filter types.
        # Model construction, database access and vector search are substituted.
        try:
            from llama_index.core.vector_stores import FilterCondition, FilterOperator
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding  # noqa: F401
            from llama_index.vector_stores.postgres import PGVectorStore  # noqa: F401
        except ImportError:
            self.skipTest("Optional LlamaIndex dependencies are not installed")
        with (
            patch("llama_index.embeddings.huggingface.HuggingFaceEmbedding") as embedding,
            patch("llama_index.vector_stores.postgres.PGVectorStore.from_params"),
            patch("llama_index.core.VectorStoreIndex.from_vector_store") as make_index,
        ):
            index = make_index.return_value
            index.as_retriever.return_value.retrieve.return_value = []
            build_index._retrieve_nodes("AAPL", ["Q4_2024", "Q1_2025"], 2)
            kwargs = index.as_retriever.call_args.kwargs
            self.assertEqual(kwargs["similarity_top_k"], 2)
            filters = kwargs["filters"]
            self.assertEqual(filters.condition, FilterCondition.AND)
            self.assertEqual(
                [(f.key, f.operator, f.value) for f in filters.filters],
                [("ticker", FilterOperator.EQ, "AAPL"),
                 ("quarter", FilterOperator.IN, ["Q4_2024", "Q1_2025"])],
            )
            embedding.assert_called_once_with(model_name=build_index.EMBED_MODEL)


if __name__ == "__main__":
    unittest.main()
