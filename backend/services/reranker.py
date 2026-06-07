import logging
import numpy as np
from typing import List, Tuple, Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class EmbeddingReranker:
    """
    Reranks retrieved candidates by direct query-document cosine similarity.

    After an initial hybrid search (BM25 + vector + RRF), this reranker generates
    a fresh query embedding and scores each candidate document individually.
    It then blends the reranker score with the hybrid score so keyword signal
    is not entirely discarded.
    """

    # Weight given to the reranker score vs the incoming hybrid score.
    RERANK_WEIGHT = 0.65
    HYBRID_WEIGHT = 0.35

    def __init__(self, client: OpenAI, embedding_model: str = "text-embedding-3-small"):
        self.client = client
        self.embedding_model = embedding_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[str, float, Dict[str, Any], str]],
        top_k: int = 3,
    ) -> List[Tuple[str, float, Dict[str, Any], str]]:
        """
        Rerank (doc_id, hybrid_score, metadata, text) tuples.

        Args:
            query: The user's natural-language query.
            candidates: Results from the hybrid search — each is a 4-tuple
                        (doc_id, hybrid_score, metadata, document_text).
            top_k: How many results to return after reranking.

        Returns:
            Top-k candidates sorted by blended rerank score (descending).
        """
        if not candidates:
            return candidates

        try:
            query_emb = self._embed(query)

            scored: List[Tuple[float, Tuple[str, float, Dict[str, Any], str]]] = []
            for item in candidates:
                doc_id, hybrid_score, metadata, text = item
                doc_text = text if text else self._metadata_to_text(metadata)
                doc_emb = self._embed(doc_text)
                rerank_score = self._cosine(query_emb, doc_emb)
                blended = self.RERANK_WEIGHT * rerank_score + self.HYBRID_WEIGHT * hybrid_score
                scored.append((blended, item))

            scored.sort(key=lambda x: x[0], reverse=True)

            result = []
            for blended_score, (doc_id, _, metadata, text) in scored[:top_k]:
                result.append((doc_id, blended_score, metadata, text))

            logger.info(
                f"✓ Reranker: {len(candidates)} candidates → top {len(result)} returned"
            )
            return result

        except Exception as e:
            logger.error(f"✗ Reranker error: {str(e)} — falling back to hybrid order")
            return candidates[:top_k]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=text[:8000],  # guard against oversized inputs
            model=self.embedding_model,
            dimensions=1536,
        )
        return response.data[0].embedding

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        va, vb = np.array(a), np.array(b)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        return float(np.dot(va, vb) / denom) if denom > 0 else 0.0

    @staticmethod
    def _metadata_to_text(metadata: Dict[str, Any]) -> str:
        return (
            f"Alarm {metadata.get('alarm_id', '')} | "
            f"{metadata.get('severity', '')} severity | "
            f"Region: {metadata.get('network_region', '')} | "
            f"Technology: {metadata.get('technology_type', '')} | "
            f"Vendor: {metadata.get('device_vendor', '')} | "
            f"Impact: {metadata.get('service_impact', '')}"
        )
