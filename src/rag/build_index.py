import json
import logging
from datetime import date
from pathlib import Path

from src.common.config import load_pipeline_config
from src.common.errors import PipelineError
from src.common.manifest import CALL_DATES_PATH, normalize_quarter

_cfg = load_pipeline_config()
logger = logging.getLogger("candor.rag")

TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "transcripts"
CHUNK_WORDS = _cfg["retrieval"]["chunk_words"]
EMBED_MODEL = _cfg["models"]["embedding"]
EMBED_DIM = _cfg["retrieval"]["embed_dim"]
TABLE_NAME = _cfg["retrieval"]["table_name"]
PG_CONFIG = _cfg["postgres"]


def chunk_segments(segments: list) -> list:
    chunks = []
    current_words, current_segments = [], []

    for seg in segments:
        words = seg["text"].split()
        current_words.extend(words)
        current_segments.append(seg)

        if len(current_words) >= CHUNK_WORDS:
            chunks.append({
                "text": " ".join(current_words),
                "start": current_segments[0]["start"],
                "end": current_segments[-1]["end"],
            })
            current_words, current_segments = [], []

    if current_words:
        chunks.append({
            "text": " ".join(current_words),
            "start": current_segments[0]["start"],
            "end": current_segments[-1]["end"],
        })

    return chunks


def build_nodes() -> list:
    from llama_index.core.schema import TextNode

    nodes = []
    for ticker_dir in sorted(TRANSCRIPTS_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name

        for transcript_path in sorted(ticker_dir.glob("*.json")):
            quarter = transcript_path.stem
            with open(transcript_path) as f:
                transcript = json.load(f)

            chunks = chunk_segments(transcript["segments"])
            print(f"{ticker} {quarter}: {len(chunks)} chunks")

            for i, chunk in enumerate(chunks):
                nodes.append(TextNode(
                    text=chunk["text"],
                    metadata={
                        "ticker": ticker,
                        "quarter": quarter,
                        "start_sec": chunk["start"],
                        "end_sec": chunk["end"],
                        "chunk_index": i,
                    },
                ))
    return nodes


def run():
    from llama_index.core import VectorStoreIndex, StorageContext, Settings
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.vector_stores.postgres import PGVectorStore

    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    Settings.llm = None

    nodes = build_nodes()
    print(f"\nTotal chunks to embed and index: {len(nodes)}")

    vector_store = PGVectorStore.from_params(
        **PG_CONFIG,
        table_name=TABLE_NAME,
        embed_dim=EMBED_DIM,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    print("Embedding and writing to pgvector...")
    VectorStoreIndex(nodes, storage_context=storage_context)
    print(f"Done. {len(nodes)} chunks indexed into table '{TABLE_NAME}'.")


def _eligible_prior_quarters(ticker: str, current_quarter: str) -> list[str]:
    """Select strictly earlier calls using recorded dates, not fiscal-quarter labels.

    An unknown target date cannot establish chronology and must fail closed.
    Undated or malformed candidate calls are excluded rather than guessed.
    """
    call_dates = json.loads(CALL_DATES_PATH.read_text()).get(ticker, {})
    try:
        current_date = date.fromisoformat(call_dates[current_quarter])
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineError(
            f"No valid recorded call date for {ticker} {current_quarter}; "
            "historical context cannot be selected safely."
        ) from exc

    eligible = []
    for quarter, recorded_date in call_dates.items():
        try:
            candidate_date = date.fromisoformat(recorded_date)
            normalized_quarter = normalize_quarter(quarter)
        except (TypeError, ValueError, PipelineError):
            logger.warning("Skipping invalid call-date entry for %s %s", ticker, quarter)
            continue
        if normalized_quarter != current_quarter and candidate_date < current_date:
            eligible.append((candidate_date, normalized_quarter))
    return [quarter for _, quarter in sorted(eligible)]


def _retrieve_nodes(ticker: str, eligible_quarters: list[str], top_k: int) -> list:
    """Apply company AND historical eligibility before the vector similarity limit.

    Filtering existing quarter metadata also works with the existing index: a
    new date field and re-embedding the transcripts are not required.
    """
    from llama_index.core import VectorStoreIndex
    from llama_index.core.vector_stores import (
        MetadataFilter, MetadataFilters, FilterOperator, FilterCondition,
    )
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.vector_stores.postgres import PGVectorStore

    embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    vector_store = PGVectorStore.from_params(**PG_CONFIG, table_name=TABLE_NAME, embed_dim=EMBED_DIM)
    index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="ticker", value=ticker, operator=FilterOperator.EQ),
            MetadataFilter(key="quarter", value=eligible_quarters, operator=FilterOperator.IN),
        ],
        condition=FilterCondition.AND,
    )
    retriever = index.as_retriever(similarity_top_k=top_k, filters=filters)
    return retriever.retrieve("key financial highlights, guidance, and outlook")


def query_prior_quarters(ticker: str, exclude_quarter: str, top_k: int = None) -> list:
    """Retrieve same-company context strictly before the target's recorded date.

    ``exclude_quarter`` is the target call, retaining the existing pipeline
    interface. Missing dates or unavailable retrieval yield no context. The
    earliest dated call needs no retrieval or model initialization at all.
    """
    try:
        ticker = ticker.strip().upper()
        current_quarter = normalize_quarter(exclude_quarter)
        limit = _cfg["retrieval"]["top_k"] if top_k is None else top_k
        if limit <= 0:
            return []
        eligible_quarters = _eligible_prior_quarters(ticker, current_quarter)
        if not eligible_quarters:
            return []
        nodes = _retrieve_nodes(ticker, eligible_quarters, limit)

        # Defense in depth: never trust an unexpected index result merely
        # because a metadata filter was requested. Keep the output contract.
        matches = [
            n for n in nodes
            if n.node.metadata.get("ticker") == ticker
            and n.node.metadata.get("quarter") in eligible_quarters
        ][:limit]
        return [
            {
                "quarter": n.node.metadata["quarter"].replace("_", " "),
                "start_sec": n.node.metadata["start_sec"],
                "text": n.node.text,
            }
            for n in matches
        ]
    except Exception as e:
        logger.warning(f"RAG retrieval unavailable ({e.__class__.__name__}: {e}) — continuing without prior-quarter context")
        return []


if __name__ == "__main__":
    run()
