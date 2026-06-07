import logging
import logging.config
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI

from backend.config import get_settings
from backend.api.routes import router, set_orchestrator, set_rag_pipeline, set_predictive_engine, set_fallback_analyzer
from backend.services.rag_pipeline import RAGPipeline
from backend.services.root_cause_engine import RootCauseAnalysisEngine
from backend.services.service_impact_engine import ServiceImpactEngine
from backend.services.resolution_engine import ResolutionRecommendationEngine
from backend.services.predictive_engine import PredictiveOutageEngine
from backend.services.fallback_analyzer import FallbackAnalyzer
from backend.agents.orchestrator import AgentOrchestrator

# Load .env before anything else reads the environment
load_dotenv()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_file: str = "logs/telecom_fault.log") -> None:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s %(name)s %(levelname)s %(message)s"},
            "detailed":  {"format": "%(asctime)s %(name)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s"},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "level": "INFO",  "formatter": "standard"},
            "file":    {"class": "logging.FileHandler",  "level": "DEBUG", "formatter": "detailed",
                        "filename": log_file},
        },
        "root": {"level": "DEBUG", "handlers": ["console", "file"]},
    })


setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App factory / lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Telecom Fault Intelligence System…")
    _settings = get_settings()

    # --- Fallback analyzer (no API key needed) --------------------------------
    try:
        fallback_analyzer = FallbackAnalyzer(_settings.dataset_path)
        fallback_analyzer.load()
        set_fallback_analyzer(fallback_analyzer)
        logger.info("✓ Fallback analyzer ready")
    except Exception as exc:
        logger.error(f"✗ Fallback analyzer failed: {exc}")

    # --- Predictive engine (no API key needed) --------------------------------
    try:
        predictive_engine = PredictiveOutageEngine(_settings.dataset_path)
        predictive_engine.load_and_analyze()
        set_predictive_engine(predictive_engine)
        logger.info("✓ Predictive outage engine ready")
    except Exception as exc:
        logger.error(f"✗ Predictive engine failed: {exc}")

    # --- OpenAI-dependent services -------------------------------------------
    try:
        openai_client = OpenAI(api_key=_settings.openai_api_key)

        rag_pipeline = RAGPipeline(
            openai_client=openai_client,
            db_path=_settings.chroma_db_path,
            dataset_path=_settings.dataset_path,
            embedding_model=_settings.openai_embedding_model,
            chunk_size=_settings.chunk_size,
            chunk_overlap=_settings.chunk_overlap,
        )

        root_cause_engine     = RootCauseAnalysisEngine(openai_client, _settings.openai_model)
        service_impact_engine = ServiceImpactEngine(openai_client, _settings.openai_model)
        resolution_engine     = ResolutionRecommendationEngine(openai_client, _settings.openai_model)

        orchestrator = AgentOrchestrator(
            rag_pipeline=rag_pipeline,
            root_cause_engine=root_cause_engine,
            service_impact_engine=service_impact_engine,
            resolution_engine=resolution_engine,
        )

        logger.info("Initializing RAG pipeline with data…")
        rag_pipeline.initialize()

        set_orchestrator(orchestrator)
        set_rag_pipeline(rag_pipeline)

        logger.info("✓ RAG pipeline and orchestrator ready")
    except Exception as exc:
        logger.error(
            f"✗ RAG/Orchestrator init failed: {exc}  "
            f"— Set a valid OPENAI_API_KEY in .env to enable query endpoints."
        )

    logger.info("✓ Server startup complete (some services may be unavailable)")
    yield

    logger.info("Shutting down Telecom Fault Intelligence System…")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title="AI-Powered Telecom Network Fault Intelligence Assistant",
    description=(
        "Multi-agent fault intelligence system for telecom network operations.\n\n"
        "## Architecture\n"
        "- **Alarm Retrieval Agent** — BM25 keyword + vector hybrid search over 500+ historical incidents\n"
        "- **Root Cause Analysis Agent** — evidence-based cause detection from declared incident causes\n"
        "- **Service Impact Agent** — revenue loss estimation, vendor/region/tech breakdowns\n"
        "- **Resolution Recommendation Agent** — ranked action steps from historical resolution notes\n\n"
        "## Analysis Modes\n"
        "| Mode | Requires | Quality |\n"
        "|------|----------|---------|\n"
        "| **AI (GPT + RAG)** | `OPENAI_API_KEY=sk-...` | Full vector similarity + LLM reasoning |\n"
        "| **Fallback (rule-based)** | Nothing | BM25 keyword scoring from local CSV |\n\n"
        "## Quick Start\n"
        "POST `/api/v1/query` with `{\"query\": \"5G outage South India Ericsson\"}` to run a full analysis.\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name":        "Fault Analysis",
            "description": "Core multi-agent fault diagnosis: retrieve incidents, identify root cause, "
                           "assess service impact, and generate resolution steps.",
        },
        {
            "name":        "Predictive Intelligence",
            "description": "Statistical outage-risk scoring derived from historical incident patterns. "
                           "No external ML service required.",
        },
        {
            "name":        "Dashboard & Metrics",
            "description": "Real-time analytics computed from the live telecom incident dataset.",
        },
        {
            "name":        "System",
            "description": "Health checks, RAG pipeline status, and administrative operations.",
        },
    ],
)

# ---------------------------------------------------------------------------
# CORS  — must be added BEFORE any routes
# ---------------------------------------------------------------------------

# Merge hardcoded safe origins with anything configured in .env so the
# frontend at http://localhost:5173 always works even if CORS_ORIGINS is
# mis-configured.
_ALWAYS_ALLOW = {"http://localhost:5173", "http://localhost:3000"}
_allowed_origins = list(_ALWAYS_ALLOW | set(settings.cors_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(router)


@app.get("/", tags=["system"])
async def root():
    return {
        "message": "Telecom Fault Intelligence System",
        "version": "1.0.0",
        "api_base": "/api/v1",
        "docs": "/docs",
        "status": "operational",
    }


@app.get("/health", tags=["system"])
async def root_health():
    """Top-level health check (mirrors /api/v1/health without the prefix)."""
    from backend.api.routes import rag_pipeline, orchestrator, predictive_engine
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "backend_url": f"http://{settings.api_host}:{settings.api_port}",
        "services": {
            "orchestrator":      orchestrator      is not None,
            "rag_pipeline":      rag_pipeline      is not None and getattr(rag_pipeline, "is_initialized", False),
            "predictive_engine": predictive_engine is not None and getattr(predictive_engine, "_loaded", False),
        },
    }


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
