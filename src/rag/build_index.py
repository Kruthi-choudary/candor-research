import json
import logging
from pathlib import Path

from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

from src.common.config import load_pipeline_config

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

    print("Embedding and writing to pgvector (this rebuilds the table fresh each run)...")
    VectorStoreIndex(nodes, storage_context=storage_context)
    print(f"Done. {len(nodes)} chunks indexed into table '{TABLE_NAME}'.")


def query_prior_quarters(ticker: str, exclude_quarter: str, top_k: int = None) -> list:
    """Best-effort retrieval of prior-quarter context for the same ticker, for cross-quarter
    comparison in the generated report. This is an enrichment, not a hard dependency — if the
    index hasn't been built yet or Postgres isn't reachable, it logs a warning and returns []
    rather than failing the pipeline.
    """
    top_k = top_k or _cfg["retrieval"]["top_k"]
    try:
        embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
        vector_store = PGVectorStore.from_params(**PG_CONFIG, table_name=TABLE_NAME, embed_dim=EMBED_DIM)
        index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
        # Filter server-side by ticker — oversampling from the whole corpus and filtering in
        # Python isn't reliable once there are several tickers: the nearest neighbors across
        # all companies can easily contain zero chunks from the one ticker we actually want.
        filters = MetadataFilters(filters=[MetadataFilter(key="ticker", value=ticker, operator=FilterOperator.EQ)])
        retriever = index.as_retriever(similarity_top_k=top_k + 4, filters=filters)
        nodes = retriever.retrieve("key financial highlights, guidance, and outlook")
    except Exception as e:
        logger.warning(f"RAG retrieval unavailable ({e.__class__.__name__}: {e}) — continuing without prior-quarter context")
        return []

    matches = [n for n in nodes if n.node.metadata.get("quarter") != exclude_quarter][:top_k]
    return [
        {
            "quarter": n.node.metadata["quarter"].replace("_", " "),
            "start_sec": n.node.metadata["start_sec"],
            "text": n.node.text,
        }
        for n in matches
    ]


if __name__ == "__main__":
    run()
