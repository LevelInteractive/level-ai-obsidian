from pathlib import Path
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient

NOOK_ROOT = Path(__file__).resolve().parents[2]
COLLECTION = "nicks_nook"
QDRANT_URL = "http://127.0.0.1:6333"
OLLAMA_URL = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text"

mcp = FastMCP("nicksnook")
client = QdrantClient(url=QDRANT_URL)


def embed(text: str) -> list[float]:
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def _vector_search(qvec: list[float], top_k: int):
    # qdrant-client >= 1.7 uses query_points; older versions use search.
    if hasattr(client, "query_points"):
        response = client.query_points(
            collection_name=COLLECTION,
            query=qvec,
            limit=top_k,
            with_payload=True,
        )
        return response.points if hasattr(response, "points") else response

    return client.search(
        collection_name=COLLECTION,
        query_vector=qvec,
        limit=top_k,
        with_payload=True,
    )


def _iter_points(batch_size: int = 256):
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION,
            limit=batch_size,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        for point in points:
            yield point
        if offset is None:
            break


@mcp.tool()
def search_chunks(
    query: str,
    top_k: int = 8,
    source_prefix: str | None = None,
) -> list[dict[str, Any]]:
    """Semantic search over indexed chunks in Qdrant."""
    if top_k < 1:
        top_k = 1
    if top_k > 50:
        top_k = 50

    qvec = embed(query)
    hits = _vector_search(qvec, top_k)

    rows: list[dict[str, Any]] = []
    for hit in hits:
        payload = hit.payload or {}
        source_path = str(payload.get("source_path", ""))
        if source_prefix and not source_path.lower().startswith(source_prefix.lower()):
            continue

        text = str(payload.get("text", "")).strip()
        rows.append(
            {
                "source_path": source_path,
                "chunk_index": int(payload.get("chunk_index", -1)),
                "score": float(hit.score),
                "snippet": text[:320],
                "retrieval_mode": "semantic",
            }
        )
    return rows


@mcp.tool()
def get_chunk(source_path: str, chunk_index: int) -> dict[str, Any]:
    """Fetch exact chunk text by source path and chunk index."""
    for point in _iter_points():
        payload = point.payload or {}
        if (
            str(payload.get("source_path", "")) == source_path
            and int(payload.get("chunk_index", -1)) == chunk_index
        ):
            text = str(payload.get("text", ""))
            return {
                "source_path": source_path,
                "chunk_index": chunk_index,
                "text": text,
                "full_path": str(NOOK_ROOT / source_path),
            }

    return {
        "error": "chunk_not_found",
        "source_path": source_path,
        "chunk_index": chunk_index,
    }


@mcp.tool()
def list_sources(query: str, top_k: int = 20) -> list[dict[str, Any]]:
    """Return unique source files ranked by best chunk score for a query."""
    hits = search_chunks(query=query, top_k=max(top_k, 20))

    best_by_source: dict[str, float] = {}
    for hit in hits:
        source_path = str(hit.get("source_path", ""))
        score = float(hit.get("score", 0.0))
        previous = best_by_source.get(source_path)
        if previous is None or score > previous:
            best_by_source[source_path] = score

    ranked = sorted(best_by_source.items(), key=lambda x: x[1], reverse=True)
    return [
        {"source_path": source_path, "best_score": score}
        for source_path, score in ranked[:top_k]
    ]


@mcp.tool()
def index_status() -> dict[str, Any]:
    """Return stack and index status for quick health checks."""
    qdrant_ok = False
    ollama_ok = False
    approx_chunk_count = 0

    try:
        client.get_collection(COLLECTION)
        qdrant_ok = True
        approx_chunk_count = client.count(collection_name=COLLECTION, exact=False).count
    except Exception:
        qdrant_ok = False

    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        response.raise_for_status()
        ollama_ok = True
    except Exception:
        ollama_ok = False

    return {
        "collection": COLLECTION,
        "qdrant_ok": qdrant_ok,
        "ollama_ok": ollama_ok,
        "approx_chunk_count": approx_chunk_count,
    }


if __name__ == "__main__":
    mcp.run()
