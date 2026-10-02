import json
from pathlib import Path

from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.schema import TextNode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "processed" / "transcripts"
CHUNK_WORDS = 250
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
TABLE_NAME = "transcript_chunks"

PG_CONFIG = {
    "database": "candor",
    "host": "localhost",
    "port": 5432,
    "user": "kannaiah",
    "password": "",
}


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


if __name__ == "__main__":
    run()
