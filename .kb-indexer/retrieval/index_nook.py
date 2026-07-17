import hashlib
import json
from pathlib import Path
from typing import List, Dict

import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from tqdm import tqdm

NOOK_ROOT = Path(__file__).resolve().parents[2]
COLLECTION = "nicks_nook"
STATE_FILE = Path(__file__).with_name("index_state.json")
QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"

INCLUDE_EXT = {".md", ".txt", ".py", ".json", ".csv"}
EXCLUDE_DIRS = {".git", ".obsidian", "node_modules", "__pycache__", ".venv", "kb-indexer"}

CHUNK_SIZE = 600
CHUNK_OVERLAP = 80


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_state() -> Dict[str, str]:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: Dict[str, str]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def list_files(root: Path) -> List[Path]:
    files = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in INCLUDE_EXT:
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        files.append(p)
    return files


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def chunk_text(text: str, size: int, overlap: int) -> List[str]:
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def embed(text: str) -> List[float]:
    r = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["embedding"]


def ensure_collection(client: QdrantClient, dim: int) -> None:
    cols = [c.name for c in client.get_collections().collections]
    if COLLECTION not in cols:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def delete_by_source_path(client: QdrantClient, rel_path: str) -> None:
    client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="source_path",
                    match=MatchValue(value=rel_path),
                )
            ]
        ),
    )


def main() -> None:
    client = QdrantClient(url=QDRANT_URL)
    state = load_state()
    current = {}
    files = list_files(NOOK_ROOT)

    changed = []
    for f in files:
        rel = str(f.relative_to(NOOK_ROOT))
        h = file_hash(f)
        current[rel] = h
        if state.get(rel) != h:
            changed.append((f, rel, h))

    removed = set(state.keys()) - set(current.keys())

    # Probe embedding dimension + ensure collection exists
    probe = embed("hello world")
    ensure_collection(client, len(probe))

    # Remove deleted docs
    for rel in removed:
        delete_by_source_path(client, rel)

    if not changed and not removed:
        print("No changes to index.")
        return

    points = []
    for f, rel, h in tqdm(changed, desc="Indexing files"):
        # remove previous chunks for this file before re-upserting
        delete_by_source_path(client, rel)

        text = read_text(f)
        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

        for i, ch in enumerate(chunks):
            if not ch.strip():
                continue
            vec = embed(ch)
            pid = int(hashlib.sha256(f"{rel}:{i}".encode()).hexdigest()[:16], 16)
            points.append(
                PointStruct(
                    id=pid,
                    vector=vec,
                    payload={
                        "source_path": rel,
                        "chunk_index": i,
                        "text": ch,
                        "file_hash": h,
                    },
                )
            )

            if len(points) >= 64:
                client.upsert(collection_name=COLLECTION, points=points)
                points = []

    if points:
        client.upsert(collection_name=COLLECTION, points=points)

    save_state(current)
    print(f"Indexed changed files: {len(changed)}, removed files: {len(removed)}")


if __name__ == "__main__":
    main()
