import pandas as pd
import logging
from typing import List, Tuple, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class TelecomDocumentChunker:
    """Chunks telecom incidents into semantic documents."""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        """Initialize chunker.
        
        Args:
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_incident(self, incident: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """Chunk a single incident into multiple documents.
        
        Args:
            incident: Incident dictionary
            
        Returns:
            List of (text, metadata) tuples
        """
        chunks = []
        
        # Create full incident document
        full_text = self._format_incident(incident)
        
        # If document is small, return as single chunk
        if len(full_text) <= self.chunk_size:
            return [(full_text, self._extract_metadata(incident))]
        
        # Split into overlapping chunks
        words = full_text.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1
            
            if current_length >= self.chunk_size:
                chunk_text = " ".join(current_chunk)
                chunks.append((chunk_text, self._extract_metadata(incident)))
                
                # Create overlap
                overlap_words = int(self.chunk_overlap / 5)  # Approximate
                current_chunk = current_chunk[-overlap_words:] if len(current_chunk) > overlap_words else current_chunk
                current_length = sum(len(w) for w in current_chunk) + len(current_chunk)
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append((chunk_text, self._extract_metadata(incident)))
        
        return chunks if chunks else [(full_text, self._extract_metadata(incident))]
    
    def _format_incident(self, incident: Dict[str, Any]) -> str:
        """Format incident into readable text.
        
        Args:
            incident: Incident dictionary
            
        Returns:
            Formatted text
        """
        return f"""
Alarm ID: {incident.get('alarm_id', 'N/A')}
Timestamp: {incident.get('timestamp', 'N/A')}
Region: {incident.get('network_region', 'N/A')}
Technology: {incident.get('technology_type', 'N/A')}
Vendor: {incident.get('device_vendor', 'N/A')}
Severity: {incident.get('severity', 'N/A')}
Outage Duration: {incident.get('outage_duration', 'N/A')} minutes
Service Impact: {incident.get('service_impact', 'N/A')}

Description:
{incident.get('incident_description', 'N/A')}

Resolution:
{incident.get('resolution_notes', 'N/A')}
        """.strip()
    
    def _extract_metadata(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from incident.
        
        Args:
            incident: Incident dictionary
            
        Returns:
            Metadata dictionary
        """
        return {
            "alarm_id": str(incident.get("alarm_id", "")),
            "network_region": str(incident.get("network_region", "")),
            "technology_type": str(incident.get("technology_type", "")),
            "severity": str(incident.get("severity", "")),
            "device_vendor": str(incident.get("device_vendor", "")),
            "outage_duration": int(incident.get("outage_duration", 0)),
            "service_impact": str(incident.get("service_impact", "")),
            "timestamp": str(incident.get("timestamp", "")),
        }


class IncidentIngestionPipeline:
    """Pipeline for loading and processing telecom incidents."""
    
    def __init__(self, dataset_path: str, chunk_size: int = 500, chunk_overlap: int = 100):
        """Initialize ingestion pipeline.
        
        Args:
            dataset_path: Path to CSV dataset
            chunk_size: Chunk size for documents
            chunk_overlap: Overlap between chunks
        """
        self.dataset_path = dataset_path
        self.chunker = TelecomDocumentChunker(chunk_size, chunk_overlap)
        self.df = None
    
    def load_dataset(self) -> pd.DataFrame:
        """Load telecom dataset from CSV.
        
        Returns:
            Loaded DataFrame
        """
        try:
            if not Path(self.dataset_path).exists():
                raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")
            
            self.df = pd.read_csv(self.dataset_path)
            logger.info(f"✓ Loaded dataset with {len(self.df)} incidents")
            
            # Validate required columns
            required_cols = [
                "alarm_id", "incident_description", "network_region",
                "technology_type", "severity", "outage_duration",
                "device_vendor", "resolution_notes", "timestamp", "service_impact"
            ]
            
            missing_cols = [col for col in required_cols if col not in self.df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Clean data
            self.df = self._clean_data()
            
            return self.df
        
        except Exception as e:
            logger.error(f"✗ Error loading dataset: {str(e)}")
            raise
    
    def _clean_data(self) -> pd.DataFrame:
        """Clean and validate data.
        
        Returns:
            Cleaned DataFrame
        """
        df = self.df.copy()
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['alarm_id'], keep='first')
        logger.info(f"✓ Removed duplicates, {len(df)} records remaining")
        
        # Handle missing values
        df['incident_description'] = df['incident_description'].fillna("No description available")
        df['resolution_notes'] = df['resolution_notes'].fillna("No resolution notes available")
        df['service_impact'] = df['service_impact'].fillna("Unknown impact")
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df['timestamp'] = df['timestamp'].fillna(datetime.now())
        
        # Ensure numeric fields
        df['outage_duration'] = pd.to_numeric(df['outage_duration'], errors='coerce').fillna(0).astype(int)
        
        logger.info("✓ Data cleaning completed")
        return df
    
    def chunk_incidents(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Chunk all incidents.
        
        Returns:
            List of (text, metadata) tuples
        """
        if self.df is None:
            self.load_dataset()
        
        all_chunks = []
        
        for idx, incident in self.df.iterrows():
            incident_dict = incident.to_dict()
            chunks = self.chunker.chunk_incident(incident_dict)
            all_chunks.extend(chunks)
        
        logger.info(f"✓ Created {len(all_chunks)} document chunks from {len(self.df)} incidents")
        return all_chunks
    
    def get_document_ids(self, start_idx: int = 0) -> List[str]:
        """Generate document IDs.
        
        Args:
            start_idx: Starting index
            
        Returns:
            List of document IDs
        """
        chunks = self.chunk_incidents()
        return [f"doc_{i+start_idx:06d}" for i in range(len(chunks))]
    
    def get_texts_and_metadata(self) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Get all texts and metadata.
        
        Returns:
            Tuple of (texts, metadatas)
        """
        chunks = self.chunk_incidents()
        texts = [chunk[0] for chunk in chunks]
        metadatas = [chunk[1] for chunk in chunks]
        return texts, metadatas
