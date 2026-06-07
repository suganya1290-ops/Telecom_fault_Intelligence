from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    # OpenAI — optional; omitting it (or leaving it blank) keeps the app in
    # fallback mode so all endpoints remain operational via BM25/pattern matching.
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_model: str = "gpt-3.5-turbo"

    # ChromaDB (local — no cloud API key needed)
    chroma_db_path: str = "./Data/chroma_db"

    # FastAPI server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_reload: bool = True

    # Data
    dataset_path: str = "./Data/telecom_dataset_enriched.csv"
    chunk_size: int = 500
    chunk_overlap: int = 100

    # Search
    bm25_k1: float = 2.0
    bm25_b: float = 0.75
    hybrid_alpha: float = 0.5
    top_k_retrieval: int = 5
    rerank_top_k: int = 3

    # Evaluation
    evaluation_enabled: bool = True
    deepeval_model: str = "gpt-3.5-turbo"
    deepeval_threshold: float = 0.7

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/telecom_fault.log"

    # CORS / Frontend
    frontend_url: str = "http://localhost:5173"
    # Accepts either a JSON array or a comma-separated string in the env file:
    #   CORS_ORIGINS=http://localhost:5173,http://localhost:3000
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Development
    debug: bool = False
    environment: str = "development"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Accept comma-separated string OR a Python/JSON list from the env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
