import chromadb
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ChromaDBManager:
    """Manages ChromaDB vector database operations."""

    def __init__(self, db_path: str, collection_name: str = "telecom_incidents"):
        """Initialize ChromaDB manager.

        Args:
            db_path: Path to ChromaDB persistent storage
            collection_name: Name of the collection
        """
        self.db_path = db_path
        self.collection_name = collection_name

        # Create directory if it doesn't exist
        Path(db_path).mkdir(parents=True, exist_ok=True)

        # Use local persistent storage — no cloud vector DB required
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = None
        
    def get_or_create_collection(self, metadata_config: Optional[Dict[str, Any]] = None) -> Any:
        """Get or create collection.
        
        Args:
            metadata_config: Optional metadata configuration
            
        Returns:
            Chroma collection object
        """
        try:
            # Try to get existing collection
            self.collection = self.client.get_collection(
                name=self.collection_name,
                metadata=metadata_config or {"hnsw:space": "cosine"}
            )
            logger.info(f"✓ Using existing collection: {self.collection_name}")
        except Exception:
            # Create new collection if it doesn't exist
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata=metadata_config or {"hnsw:space": "cosine"}
            )
            logger.info(f"✓ Created new collection: {self.collection_name}")
        
        return self.collection
    
    def add_documents(self, 
                     ids: List[str],
                     embeddings: List[List[float]],
                     documents: List[str],
                     metadatas: List[Dict[str, Any]]) -> None:
        """Add documents to collection.
        
        Args:
            ids: Document IDs
            embeddings: Document embeddings
            documents: Document texts
            metadatas: Document metadata
        """
        if not self.collection:
            self.get_or_create_collection()
        
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"✓ Added {len(ids)} documents to collection")
        except Exception as e:
            logger.error(f"✗ Error adding documents: {str(e)}")
            raise
    
    def query(self,
             query_embeddings: List[List[float]],
             n_results: int = 5,
             where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Query collection.
        
        Args:
            query_embeddings: Query embeddings
            n_results: Number of results to return
            where: Optional metadata filter
            
        Returns:
            Query results
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized")
        
        try:
            results = self.collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                include=["embeddings", "documents", "metadatas", "distances"]
            )
            return results
        except Exception as e:
            logger.error(f"✗ Error querying collection: {str(e)}")
            raise
    
    def get_collection_count(self) -> int:
        """Get number of documents in collection.
        
        Returns:
            Document count
        """
        if not self.collection:
            return 0
        return self.collection.count()
    
    def delete_collection(self) -> None:
        """Delete the collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = None
            logger.info(f"✓ Deleted collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"✗ Error deleting collection: {str(e)}")
    
    def clear_collection(self) -> None:
        """Clear all documents from collection."""
        if self.collection:
            try:
                # Get all IDs and delete
                all_items = self.collection.get()
                if all_items['ids']:
                    self.collection.delete(ids=all_items['ids'])
                logger.info("✓ Cleared collection")
            except Exception as e:
                logger.error(f"✗ Error clearing collection: {str(e)}")


class DBSession:
    """Context manager for database operations."""
    
    def __init__(self, db_path: str):
        self.manager = ChromaDBManager(db_path)
    
    def __enter__(self):
        self.manager.get_or_create_collection()
        return self.manager
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
