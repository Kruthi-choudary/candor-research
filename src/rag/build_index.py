import json
import hashlib
import logging
from datetime import date
from pathlib import Path

from src.common.config import load_pipeline_config
from src.common.errors import PipelineError
from src.common.manifest import ROOT, CALL_DATES_PATH, normalize_quarter

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
                    id_=hashlib.sha256(json.dumps([ticker, quarter, i, chunk], sort_keys=True).encode()).hexdigest(),
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


def index_identity(nodes: list) -> dict:
    return {"model": EMBED_MODEL, "embedding_dimensions": EMBED_DIM, "chunk_words": CHUNK_WORDS,
            "node_ids": sorted(n.node_id for n in nodes),
            "database": {k: v for k, v in PG_CONFIG.items() if k != "password"}, "table": TABLE_NAME}


def stored_node_ids() -> list:
    import psycopg2
    from psycopg2 import sql

    with psycopg2.connect(**PG_CONFIG, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            table = f"data_{TABLE_NAME.lower()}"
            cursor.execute("SELECT to_regclass(%s)", (f"public.{table}",))
            if cursor.fetchone()[0] is None:
                return []
            cursor.execute(sql.SQL("SELECT node_id FROM public.{}").format(sql.Identifier(table)))
            return sorted(row[0] for row in cursor.fetchall())


def check_existing_index(identity: dict, stored: list, manifest: dict | None) -> bool:
    if not stored:
        return False
    if stored == identity["node_ids"] and manifest == identity:
        return True
    raise PipelineError("The target index is nonempty but does not match this dataset/configuration. No data was deleted or appended. Use a separate empty index or investigate the existing data.")


def run():
    from llama_index.core import VectorStoreIndex, StorageContext, Settings
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.vector_stores.postgres import PGVectorStore

    nodes = build_nodes()
    identity = index_identity(nodes)
    manifest_path = ROOT / ".local/index_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if check_existing_index(identity, stored_node_ids(), manifest):
        print(f"Index already matches: {len(nodes)} unique chunks; no duplicate rows added.")
        return
    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    Settings.llm = None
    print(f"\nTotal chunks to embed and index: {len(nodes)}")

    vector_store = PGVectorStore.from_params(
        **PG_CONFIG,
        table_name=TABLE_NAME,
        embed_dim=EMBED_DIM,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    print("Embedding and writing to pgvector...")
    VectorStoreIndex(nodes, storage_context=storage_context)
    if stored_node_ids() != identity["node_ids"]:
        raise PipelineError("Index readback does not match the expected unique chunks; verification failed.")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(identity, indent=2) + "\n")
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


def current_call_queries(segments: list) -> list[str]:
    """Use the same current-call passages as claim generation to search history."""
    from src.report.evidence import select_evidence_passages

    positive, negative = select_evidence_passages(segments, _cfg["generation"]["top_k_quotes"])
    ordered = [passages[index]["text"] for index in range(2) for passages in (positive, negative)
               if index < len(passages)]
    return list(dict.fromkeys(ordered))


def _retrieve_nodes(ticker: str, eligible_quarters: list[str], top_k: int,
                    queries: list[str] | None = None) -> list:
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
    search_texts = queries if queries else ["key financial highlights, guidance, and outlook"]
    results = [retriever.retrieve(query) for query in search_texts]
    # Give each current-call topic a chance before taking a second hit for any
    # one topic. The old fixed query repeatedly returned unrelated cash/CAPEX
    # passages for Apple revenue claims.
    chosen, seen = [], set()
    for matches in results:
        for item in matches:
            if item.node.node_id not in seen:
                seen.add(item.node.node_id)
                chosen.append(item)
                break
        if len(chosen) == top_k:
            return chosen
    for matches in results:
        for item in matches:
            if item.node.node_id in seen:
                continue
            seen.add(item.node.node_id)
            chosen.append(item)
            if len(chosen) == top_k:
                return chosen
    return chosen


def query_prior_quarters(ticker: str, exclude_quarter: str, top_k: int = None,
                         *, strict: bool = False, queries: list[str] | None = None) -> list:
    """Retrieve same-company context strictly before the target's recorded date.

    ``exclude_quarter`` is the target call, retaining the existing pipeline
    interface. In strict mode a missing date or failed/empty retrieval for a
    call with earlier history stops generation. The earliest dated call needs
    no retrieval or model initialization at all.
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
        nodes = _retrieve_nodes(ticker, eligible_quarters, limit, queries=queries) if queries else _retrieve_nodes(ticker, eligible_quarters, limit)

        # Defense in depth: never trust an unexpected index result merely
        # because a metadata filter was requested. Keep the output contract.
        matches = [
            n for n in nodes
            if n.node.metadata.get("ticker") == ticker
            and n.node.metadata.get("quarter") in eligible_quarters
        ][:limit]
        if strict and not matches:
            raise PipelineError(f"Historical retrieval returned no eligible passages for {ticker} {current_quarter}.")
        return [
            {
                "quarter": n.node.metadata["quarter"].replace("_", " "),
                "start_sec": n.node.metadata["start_sec"],
                "text": n.node.text,
            }
            for n in matches
        ]
    except Exception as e:
        if strict:
            raise PipelineError(f"Historical retrieval failed for {ticker} {exclude_quarter}: {e}") from e
        logger.warning(f"RAG retrieval unavailable ({e.__class__.__name__}: {e}) — continuing without prior-quarter context")
        return []


if __name__ == "__main__":
    run()
