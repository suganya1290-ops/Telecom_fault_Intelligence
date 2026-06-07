import logging
from typing import List, Dict, Any, Tuple
import numpy as np
from rank_bm25 import BM25Okapi
from openai import OpenAI

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """Hybrid search combining BM25 keyword search and vector search with RRF."""
    
    def __init__(self, 
                 client: OpenAI,
                 embedding_model: str = "text-embedding-3-small",
                 k1: float = 2.0,
                 b: float = 0.75,
                 alpha: float = 0.5):
        """Initialize hybrid search engine.
        
        Args:
            client: OpenAI client for embeddings
            embedding_model: Model for embeddings
            k1: BM25 k1 parameter
            b: BM25 b parameter
            alpha: Weight for vector search in hybrid score (1-alpha for BM25)
        """
        self.client = client
        self.embedding_model = embedding_model
        self.k1 = k1
        self.b = b
        self.alpha = alpha
        self.bm25 = None
        self.documents = []
        self.document_ids = []
        self.document_metadata = []
    
    def index_documents(self, 
                       document_ids: List[str],
                       documents: List[str],
                       metadatas: List[Dict[str, Any]]) -> None:
        """Index documents for BM25 search.
        
        Args:
            document_ids: Document IDs
            documents: Document texts
            metadatas: Document metadata
        """
        try:
            # Tokenize for BM25
            tokenized_docs = [doc.lower().split() for doc in documents]
            self.bm25 = BM25Okapi(tokenized_docs, k1=self.k1, b=self.b)
            
            self.documents = documents
            self.document_ids = document_ids
            self.document_metadata = metadatas
            
            logger.info(f"✓ Indexed {len(documents)} documents for hybrid search")
        except Exception as e:
            logger.error(f"✗ Error indexing documents: {str(e)}")
            raise
    
    def _get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for query.
        
        Args:
            query: Query text
            
        Returns:
            Query embedding
        """
        try:
            response = self.client.embeddings.create(
                input=query,
                model=self.embedding_model,
                dimensions=1536
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"✗ Error generating query embedding: {str(e)}")
            raise
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity score
        """
        a = np.array(a)
        b = np.array(b)
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def bm25_search(self, query: str, top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        """Perform BM25 keyword search.
        
        Args:
            query: Query text
            top_k: Number of results to return
            
        Returns:
            List of (doc_id, score, metadata) tuples
        """
        if not self.bm25:
            raise RuntimeError("BM25 not indexed")
        
        try:
            tokenized_query = query.lower().split()
            scores = self.bm25.get_scores(tokenized_query)
            
            # Get top-k indices
            top_indices = np.argsort(scores)[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                if scores[idx] > 0:  # Only include non-zero scores
                    results.append((
                        self.document_ids[idx],
                        float(scores[idx]),
                        self.document_metadata[idx]
                    ))
            
            return results
        except Exception as e:
            logger.error(f"✗ Error in BM25 search: {str(e)}")
            return []
    
    def vector_search(self, 
                     query: str,
                     vector_search_func,
                     top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        """Perform vector similarity search.
        
        Args:
            query: Query text
            vector_search_func: Function for vector search in ChromaDB
            top_k: Number of results to return
            
        Returns:
            List of (doc_id, score, metadata) tuples
        """
        try:
            query_embedding = self._get_query_embedding(query)
            results = vector_search_func([query_embedding], top_k=top_k)
            
            search_results = []
            if results and 'ids' in results and len(results['ids']) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    # ChromaDB returns distances (0 = identical, 1 = completely different for cosine)
                    # Convert to similarity (1 - distance)
                    distance = results['distances'][0][i] if 'distances' in results else 0
                    similarity = 1 - (distance / 2)  # Normalize
                    
                    metadata = results['metadatas'][0][i] if 'metadatas' in results else {}
                    search_results.append((doc_id, float(similarity), metadata))
            
            return search_results
        except Exception as e:
            logger.error(f"✗ Error in vector search: {str(e)}")
            return []
    
    def reciprocal_rank_fusion(self,
                              bm25_results: List[Tuple[str, float, Dict]],
                              vector_results: List[Tuple[str, float, Dict]],
                              top_k: int = 5,
                              k: int = 60) -> List[Tuple[str, float, Dict]]:
        """Combine BM25 and vector results using Reciprocal Rank Fusion.
        
        Args:
            bm25_results: BM25 search results
            vector_results: Vector search results
            top_k: Number of final results to return
            k: RRF parameter (typically 60)
            
        Returns:
            Fused results
        """
        fused_scores = {}
        doc_info = {}
        
        # Add BM25 scores
        for rank, (doc_id, score, metadata) in enumerate(bm25_results):
            bm25_rank = rank + 1
            rrf_score = 1 / (k + bm25_rank)
            fused_scores[doc_id] = fused_scores.get(doc_id, 0) + rrf_score
            doc_info[doc_id] = (score, metadata)
        
        # Add vector scores
        for rank, (doc_id, score, metadata) in enumerate(vector_results):
            vector_rank = rank + 1
            rrf_score = 1 / (k + vector_rank)
            fused_scores[doc_id] = fused_scores.get(doc_id, 0) + rrf_score
            if doc_id not in doc_info:
                doc_info[doc_id] = (score, metadata)
        
        # Sort by fused score
        sorted_docs = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for doc_id, fused_score in sorted_docs:
            original_score, metadata = doc_info[doc_id]
            results.append((doc_id, fused_score, metadata))
        
        return results
    
    def hybrid_search(self,
                     query: str,
                     vector_search_func,
                     top_k: int = 5,
                     alpha: float = None) -> List[Tuple[str, float, Dict]]:
        """Perform hybrid search combining BM25 and vector search with RRF.
        
        Args:
            query: Query text
            vector_search_func: Function for vector search
            top_k: Number of results to return
            alpha: Override alpha parameter
            
        Returns:
            List of (doc_id, hybrid_score, metadata) tuples
        """
        try:
            # Perform BM25 search
            bm25_results = self.bm25_search(query, top_k=top_k * 2)
            
            # Perform vector search
            vector_results = self.vector_search(query, vector_search_func, top_k=top_k * 2)
            
            # Combine using RRF
            fused_results = self.reciprocal_rank_fusion(
                bm25_results,
                vector_results,
                top_k=top_k
            )
            
            logger.info(f"✓ Hybrid search returned {len(fused_results)} results")
            return fused_results
        
        except Exception as e:
            logger.error(f"✗ Error in hybrid search: {str(e)}")
            return []
