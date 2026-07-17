import requests
from qdrant_client import QdrantClient

QDRANT_URL = "http://127.0.0.1:6333"
OLLAMA_URL = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text"
COLLECTION = "nicks_nook"


def embed(text: str):
    r = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["embedding"]


client = QdrantClient(url=QDRANT_URL)
query = input("Query: ").strip()
vec = embed(query)

if hasattr(client, "query_points"):
    response = client.query_points(
        collection_name=COLLECTION,
        query=vec,
        limit=5,
        with_payload=True,
    )
    hits = response.points if hasattr(response, "points") else response
else:
    hits = client.search(
        collection_name=COLLECTION,
        query_vector=vec,
        limit=5,
        with_payload=True,
    )

for i, h in enumerate(hits, 1):
    p = h.payload or {}
    text = (p.get("text") or "").replace("\n", " ")
    print(f"\n[{i}] score={h.score:.4f} file={p.get('source_path')} chunk={p.get('chunk_index')}")
    print(text[:300])
