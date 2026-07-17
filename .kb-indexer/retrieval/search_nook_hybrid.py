import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from qdrant_client import QdrantClient

NOOK_ROOT = Path(__file__).resolve().parents[2]
COLLECTION = "nicks_nook"
QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
RRF_K = 60


@dataclass
class ChunkDoc:
    id: str
    source_path: str
    chunk_index: int
    text: str


@dataclass
class Hit:
    id: str
    source_path: str
    chunk_index: int
    text: str
    semantic_score: Optional[float] = None
    bm25_score: Optional[float] = None
    fused_score: Optional[float] = None
    rerank_score: Optional[float] = None


class HybridSearcher:
    def __init__(self, use_bm25: bool, use_rerank: bool, rerank_model: str):
        self.client = QdrantClient(url=QDRANT_URL)
        self.use_bm25 = use_bm25
        self.use_rerank = use_rerank
        self.rerank_model = rerank_model

        self.docs: List[ChunkDoc] = []
        self.id_to_doc: Dict[str, ChunkDoc] = {}
        self._bm25 = None
        self._bm25_docs: List[ChunkDoc] = []

        self._cross_encoder = None

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9_]+", text.lower())

    def embed(self, text: str) -> List[float]:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def _vector_search(self, qvec: List[float], k: int):
        # qdrant-client >= 1.7 uses query_points; older versions use search.
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=COLLECTION,
                query=qvec,
                limit=k,
                with_payload=True,
            )
            return response.points if hasattr(response, "points") else response

        return self.client.search(
            collection_name=COLLECTION,
            query_vector=qvec,
            limit=k,
            with_payload=True,
        )

    def load_chunks(self) -> None:
        all_docs: List[ChunkDoc] = []
        next_offset = None

        while True:
            points, next_offset = self.client.scroll(
                collection_name=COLLECTION,
                limit=256,
                with_payload=True,
                with_vectors=False,
                offset=next_offset,
            )

            for point in points:
                payload = point.payload or {}
                text = payload.get("text")
                source_path = payload.get("source_path")
                chunk_index = payload.get("chunk_index", -1)

                if not text or not source_path:
                    continue

                doc = ChunkDoc(
                    id=str(point.id),
                    source_path=str(source_path),
                    chunk_index=int(chunk_index),
                    text=str(text),
                )
                all_docs.append(doc)

            if next_offset is None:
                break

        self.docs = all_docs
        self.id_to_doc = {doc.id: doc for doc in all_docs}

    def build_bm25(self) -> None:
        if not self.use_bm25:
            return

        try:
            from rank_bm25 import BM25Okapi
        except Exception:
            print("BM25 disabled: install rank-bm25 to enable lexical retrieval.")
            self.use_bm25 = False
            return

        tokenized = []
        bm25_docs = []
        for doc in self.docs:
            tokens = self._tokenize(doc.text)
            if not tokens:
                continue
            tokenized.append(tokens)
            bm25_docs.append(doc)

        if not tokenized:
            print("BM25 disabled: no tokenizable chunks found.")
            self.use_bm25 = False
            return

        self._bm25 = BM25Okapi(tokenized)
        self._bm25_docs = bm25_docs

    def semantic_search(self, query: str, k: int) -> List[Hit]:
        qvec = self.embed(query)
        results = self._vector_search(qvec, k)

        hits = []
        for result in results:
            payload = result.payload or {}
            text = payload.get("text")
            source_path = payload.get("source_path")
            chunk_index = payload.get("chunk_index", -1)
            if not text or not source_path:
                continue
            hits.append(
                Hit(
                    id=str(result.id),
                    source_path=str(source_path),
                    chunk_index=int(chunk_index),
                    text=str(text),
                    semantic_score=float(result.score),
                )
            )
        return hits

    def bm25_search(self, query: str, k: int) -> List[Hit]:
        if not self.use_bm25 or self._bm25 is None:
            return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        hits = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            doc = self._bm25_docs[idx]
            hits.append(
                Hit(
                    id=doc.id,
                    source_path=doc.source_path,
                    chunk_index=doc.chunk_index,
                    text=doc.text,
                    bm25_score=score,
                )
            )
        return hits

    def fuse_rrf(self, semantic_hits: List[Hit], bm25_hits: List[Hit]) -> List[Hit]:
        by_id: Dict[str, Hit] = {}
        rank_scores: Dict[str, float] = {}

        for rank, hit in enumerate(semantic_hits, start=1):
            existing = by_id.get(hit.id)
            if existing is None:
                by_id[hit.id] = hit
            else:
                existing.semantic_score = hit.semantic_score
            rank_scores[hit.id] = rank_scores.get(hit.id, 0.0) + 1.0 / (RRF_K + rank)

        for rank, hit in enumerate(bm25_hits, start=1):
            existing = by_id.get(hit.id)
            if existing is None:
                by_id[hit.id] = hit
            else:
                existing.bm25_score = hit.bm25_score
            rank_scores[hit.id] = rank_scores.get(hit.id, 0.0) + 1.0 / (RRF_K + rank)

        merged = []
        for doc_id, hit in by_id.items():
            hit.fused_score = rank_scores.get(doc_id, 0.0)
            merged.append(hit)

        merged.sort(key=lambda h: h.fused_score or 0.0, reverse=True)
        return merged

    def _load_reranker(self):
        if self._cross_encoder is not None:
            return self._cross_encoder

        try:
            from sentence_transformers import CrossEncoder
        except Exception:
            print("Rerank disabled: install sentence-transformers and torch.")
            self.use_rerank = False
            return None

        self._cross_encoder = CrossEncoder(self.rerank_model)
        return self._cross_encoder

    def rerank(self, query: str, hits: List[Hit], rerank_k: int) -> List[Hit]:
        if not self.use_rerank or not hits:
            return hits

        model = self._load_reranker()
        if model is None:
            return hits

        candidates = hits[:rerank_k]
        pairs = [(query, hit.text) for hit in candidates]
        scores = model.predict(pairs)

        for hit, score in zip(candidates, scores):
            hit.rerank_score = float(score)

        reranked = sorted(candidates, key=lambda h: h.rerank_score or 0.0, reverse=True)
        reranked.extend(hits[rerank_k:])
        return reranked

    @staticmethod
    def _format_snippet(text: str, max_len: int = 220) -> str:
        clean = " ".join(text.split())
        if len(clean) <= max_len:
            return clean
        return clean[: max_len - 3] + "..."

    def search(
        self,
        query: str,
        top_k: int,
        semantic_k: int,
        bm25_k: int,
        rerank_k: int,
    ) -> List[Hit]:
        semantic_hits = self.semantic_search(query, semantic_k)
        bm25_hits = self.bm25_search(query, bm25_k) if self.use_bm25 else []

        if self.use_bm25:
            fused = self.fuse_rrf(semantic_hits, bm25_hits)
        else:
            fused = semantic_hits
            for i, hit in enumerate(fused, start=1):
                hit.fused_score = 1.0 / (RRF_K + i)

        reranked = self.rerank(query, fused, rerank_k)
        return reranked[:top_k]

    def print_results(self, query: str, results: List[Hit]) -> None:
        print("=" * 90)
        print(f"Query: {query}")
        print(f"Results: {len(results)}")
        print("=" * 90)

        for i, hit in enumerate(results, start=1):
            abs_path = NOOK_ROOT / hit.source_path
            print(f"[{i}] {hit.source_path} (chunk {hit.chunk_index})")
            print(f"    file: {abs_path}")
            print(
                "    scores: "
                f"semantic={hit.semantic_score if hit.semantic_score is not None else 'n/a'} | "
                f"bm25={hit.bm25_score if hit.bm25_score is not None else 'n/a'} | "
                f"fused={hit.fused_score if hit.fused_score is not None else 'n/a'} | "
                f"rerank={hit.rerank_score if hit.rerank_score is not None else 'n/a'}"
            )
            print(f"    snippet: {self._format_snippet(hit.text)}")
            print("-" * 90)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid search (semantic + BM25 + optional rerank)")
    parser.add_argument("--query", type=str, default=None, help="Single query to run")
    parser.add_argument("--top-k", type=int, default=8, help="Final number of results")
    parser.add_argument("--semantic-k", type=int, default=20, help="Semantic candidate pool")
    parser.add_argument("--bm25-k", type=int, default=20, help="BM25 candidate pool")
    parser.add_argument("--no-bm25", action="store_true", help="Disable BM25")
    parser.add_argument("--rerank", action="store_true", help="Enable reranking")
    parser.add_argument("--rerank-k", type=int, default=30, help="Candidates passed to reranker")
    parser.add_argument(
        "--rerank-model",
        type=str,
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        help="Cross-encoder model name",
    )
    return parser.parse_args()


def run_interactive(searcher: HybridSearcher, args: argparse.Namespace) -> None:
    print("Hybrid search ready. Enter a query (or 'exit').")
    while True:
        query = input("\nQuery> ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            break

        results = searcher.search(
            query=query,
            top_k=args.top_k,
            semantic_k=args.semantic_k,
            bm25_k=args.bm25_k,
            rerank_k=args.rerank_k,
        )
        searcher.print_results(query, results)


def main() -> None:
    args = parse_args()

    searcher = HybridSearcher(
        use_bm25=not args.no_bm25,
        use_rerank=args.rerank,
        rerank_model=args.rerank_model,
    )

    searcher.load_chunks()
    if not searcher.docs:
        print(f"No chunks found in collection '{COLLECTION}'. Run index_nook.py first.")
        return

    print(f"Loaded chunks: {len(searcher.docs)}")

    searcher.build_bm25()
    if searcher.use_bm25:
        print(f"BM25 ready: {len(searcher._bm25_docs)} tokenized chunks")
    else:
        print("BM25 not active")

    if args.rerank:
        print(f"Rerank requested with model: {args.rerank_model}")

    if args.query:
        results = searcher.search(
            query=args.query,
            top_k=args.top_k,
            semantic_k=args.semantic_k,
            bm25_k=args.bm25_k,
            rerank_k=args.rerank_k,
        )
        searcher.print_results(args.query, results)
    else:
        run_interactive(searcher, args)


if __name__ == "__main__":
    main()
