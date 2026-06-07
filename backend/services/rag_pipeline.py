import logging
from typing import List, Dict, Any, Tuple, Optional
from openai import OpenAI
from backend.database import ChromaDBManager
from backend.ingestion import IncidentIngestionPipeline
from backend.services.hybrid_search import HybridSearchEngine
from backend.services.reranker import EmbeddingReranker
from backend.utils.token_optimizer import TokenOptimizer

logger = logging.getLogger(__name__)


class RAGPipeline:
    """End-to-end RAG pipeline for telecom incident retrieval and analysis."""
    
    def __init__(self,
                 openai_client: OpenAI,
                 db_path: str,
                 dataset_path: str,
                 embedding_model: str = "text-embedding-3-small",
                 chunk_size: int = 500,
                 chunk_overlap: int = 100):
        """Initialize RAG pipeline.
        
        Args:
            openai_client: OpenAI client
            db_path: Path to ChromaDB
            dataset_path: Path to dataset CSV
            embedding_model: Embedding model name
            chunk_size: Chunk size for documents
            chunk_overlap: Overlap between chunks
        """
        self.openai_client = openai_client
        self.embedding_model = embedding_model

        # Initialize components
        self.db_manager = ChromaDBManager(db_path)
        self.ingestion_pipeline = IncidentIngestionPipeline(dataset_path, chunk_size, chunk_overlap)
        self.hybrid_search = HybridSearchEngine(openai_client, embedding_model)
        self.reranker = EmbeddingReranker(openai_client, embedding_model)
        self.token_optimizer    = TokenOptimizer(max_context_tokens=3000)
        self.last_token_usage:  Dict[str, Any] = {}   # updated after every retrieve_incidents()

        self.is_initialized = False
    
    def initialize(self) -> None:
        """Initialize RAG pipeline with data."""
        try:
            logger.info("Initializing RAG pipeline...")
            
            # Load and process dataset
            logger.info("Loading dataset...")
            self.ingestion_pipeline.load_dataset()
            
            # Chunk documents
            logger.info("Chunking documents...")
            texts, metadatas = self.ingestion_pipeline.get_texts_and_metadata()
            doc_ids = self.ingestion_pipeline.get_document_ids()
            
            # Generate embeddings
            logger.info("Generating embeddings...")
            embeddings = self._generate_embeddings(texts)
            
            # Initialize ChromaDB collection
            logger.info("Initializing ChromaDB...")
            self.db_manager.get_or_create_collection()
            
            # Add documents to ChromaDB
            logger.info("Adding documents to vector database...")
            self.db_manager.add_documents(doc_ids, embeddings, texts, metadatas)
            
            # Index documents for hybrid search
            logger.info("Indexing documents for hybrid search...")
            self.hybrid_search.index_documents(doc_ids, texts, metadatas)
            
            self.is_initialized = True
            logger.info("✓ RAG pipeline initialized successfully")
        
        except Exception as e:
            logger.error(f"✗ Error initializing RAG pipeline: {str(e)}")
            raise
    
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts.
        
        Args:
            texts: List of text documents
            
        Returns:
            List of embeddings
        """
        try:
            embeddings = []
            batch_size = 100
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                logger.info(f"Generating embeddings batch {i//batch_size + 1}...")
                
                response = self.openai_client.embeddings.create(
                    input=batch,
                    model=self.embedding_model,
                    dimensions=1536
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
            
            logger.info(f"✓ Generated {len(embeddings)} embeddings")
            return embeddings
        
        except Exception as e:
            logger.error(f"✗ Error generating embeddings: {str(e)}")
            raise
    
    def retrieve_incidents(self,
                          query: str,
                          top_k: int = 5,
                          region_filter: Optional[str] = None,
                          severity_filter: Optional[str] = None,
                          technology_filter: Optional[str] = None,
                          vendor_filter: Optional[str] = None) -> List[Tuple[str, float, Dict, str]]:
        """Retrieve relevant incidents using hybrid search.
        
        Args:
            query: Query text
            top_k: Number of results to return
            region_filter: Optional region filter
            severity_filter: Optional severity filter
            technology_filter: Optional technology filter
            vendor_filter: Optional vendor filter
            
        Returns:
            List of (doc_id, hybrid_score, metadata, full_text) tuples
        """
        try:
            if not self.is_initialized:
                raise RuntimeError("RAG pipeline not initialized")
            
            # Build metadata filters
            where_filter = self._build_where_filter(
                region_filter, severity_filter, technology_filter, vendor_filter
            )
            
            # Perform hybrid search
            search_results = self.hybrid_search.hybrid_search(
                query,
                lambda embeddings, k: self.db_manager.query(embeddings, k, where=where_filter),
                top_k=top_k
            )
            
            # Build (doc_id, hybrid_score, metadata, text) tuples
            full_results = []
            for doc_id, hybrid_score, metadata in search_results:
                document_text = self._reconstruct_document(metadata) if metadata else ""
                full_results.append((doc_id, hybrid_score, metadata, document_text))

            # Rerank: precision pass using direct query-document embedding similarity
            reranked = self.reranker.rerank(query, full_results, top_k=top_k)

            # ── Token stats for retrieved documents (activates self.token_optimizer) ──
            doc_texts = [text for _, _, _, text in reranked if text]
            if doc_texts:
                stats = self.token_optimizer.token_stats(doc_texts)
                self.last_token_usage = {
                    "documents_retrieved": len(reranked),
                    "total_doc_tokens":    stats["total_tokens"],
                    "avg_doc_tokens":      stats["avg_tokens"],
                    "max_doc_tokens":      stats["max_tokens"],
                    "doc_count":           stats["document_count"],
                }
                logger.info(
                    f"✓ Retrieved and reranked {len(reranked)} incidents | "
                    f"doc_tokens={stats['total_tokens']} total "
                    f"(avg={stats['avg_tokens']}, max={stats['max_tokens']})"
                )
            else:
                logger.info(f"✓ Retrieved and reranked {len(reranked)} incidents for query")

            return reranked
        
        except Exception as e:
            logger.error(f"✗ Error retrieving incidents: {str(e)}")
            return []
    
    def _build_where_filter(self,
                           region: Optional[str],
                           severity: Optional[str],
                           technology: Optional[str],
                           vendor: Optional[str]) -> Optional[Dict[str, Any]]:
        """Build ChromaDB where filter.
        
        Args:
            region: Region filter
            severity: Severity filter
            technology: Technology filter
            vendor: Vendor filter
            
        Returns:
            Where filter dictionary or None
        """
        filters = []
        
        if region:
            filters.append({"network_region": region})
        if severity:
            filters.append({"severity": severity})
        if technology:
            filters.append({"technology_type": technology})
        if vendor:
            filters.append({"device_vendor": vendor})
        
        if not filters:
            return None
        elif len(filters) == 1:
            return filters[0]
        else:
            return {"$and": filters}
    
    def _reconstruct_document(self, metadata: Dict[str, Any]) -> str:
        """Reconstruct document text from metadata.
        
        Args:
            metadata: Document metadata
            
        Returns:
            Reconstructed text
        """
        doc = f"""
Alarm ID: {metadata.get('alarm_id', 'N/A')}
Timestamp: {metadata.get('timestamp', 'N/A')}
Region: {metadata.get('network_region', 'N/A')}
Technology: {metadata.get('technology_type', 'N/A')}
Vendor: {metadata.get('device_vendor', 'N/A')}
Severity: {metadata.get('severity', 'N/A')}
Outage Duration: {metadata.get('outage_duration', 'N/A')} minutes
Service Impact: {metadata.get('service_impact', 'N/A')}
        """.strip()
        return doc
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection.
        
        Returns:
            Collection statistics
        """
        try:
            count = self.db_manager.get_collection_count()
            return {
                "total_documents": count,
                "database_path": self.db_manager.db_path,
                "collection_name": self.db_manager.collection_name,
                "initialized": self.is_initialized
            }
        except Exception as e:
            logger.error(f"✗ Error getting collection stats: {str(e)}")
            return {}
    
    def clear_and_reinitialize(self) -> None:
        """Clear all data and reinitialize.
        
        Useful for rebuilding the index.
        """
        try:
            logger.info("Clearing and reinitializing RAG pipeline...")
            self.db_manager.delete_collection()
            self.is_initialized = False
            self.initialize()
            logger.info("✓ RAG pipeline cleared and reinitialized")
        except Exception as e:
            logger.error(f"✗ Error reinitializing: {str(e)}")
            raise
