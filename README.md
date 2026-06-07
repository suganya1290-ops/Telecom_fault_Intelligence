# AI-Powered Telecom Network Fault Intelligence Assistant

Advanced multi-agent AI system for telecom network fault analysis, root cause identification, and intelligent troubleshooting recommendations.

## Project Overview

This system uses a custom A2A (Agent-to-Agent) multi-agent architecture, hybrid retrieval-augmented generation (RAG), and LLM reasoning to help telecom engineers rapidly diagnose network faults, analyze root causes, assess service impact, and generate actionable troubleshooting steps.

The system operates in two modes and requires no external services beyond an optional OpenAI API key:

| Mode | Requires | Quality |
|------|----------|---------|
| **AI (GPT + RAG)** | `OPENAI_API_KEY=sk-...` | Full vector similarity + LLM reasoning + embedding reranking |
| **Fallback (rule-based)** | Nothing | BM25 keyword scoring from local CSV — works offline |

**Key Technologies:**
- **Custom A2A Bus**: Per-request Agent-to-Agent message protocol (REQUEST / RESPONSE / NOTIFICATION / ESCALATION)
- **OpenAI**: `text-embedding-3-small` (1536-dim) + `gpt-3.5-turbo`
- **Embedding Reranker**: OpenAI cosine-similarity reranking (65 % reranker / 35 % hybrid blend)
- **ChromaDB**: Local persistent vector database for incident retrieval
- **rank-bm25**: BM25Okapi keyword search engine
- **NetworkX**: Alarm correlation graph analysis
- **tiktoken**: Token-budget context building (replaces fixed character slices)
- **FastAPI**: Production-ready REST API with input guardrails
- **React 18 + Vite + Tailwind**: Modern dark-theme frontend UI
- **DeepEval**: Troubleshooting response quality evaluation

## Project Structure

```
telecom-fault-intelligence/
├── backend/
│   ├── agents/                        # Multi-agent workflow
│   │   ├── a2a_protocol.py            # A2A bus: MessageType, AgentMessage, A2ABus
│   │   ├── alarm_retrieval_agent.py   # Step 1 — hybrid RAG retrieval
│   │   ├── root_cause_agent.py        # Step 2 — RCA with A2A expansion
│   │   ├── service_impact_agent.py    # Step 4 — revenue & customer impact
│   │   ├── resolution_agent.py        # Step 5 — ranked remediation actions
│   │   └── orchestrator.py            # Workflow coordinator + A2A bus wiring
│   ├── services/                      # Business logic engines
│   │   ├── rag_pipeline.py            # ChromaDB ingest + hybrid retrieval
│   │   ├── hybrid_search.py           # BM25 + vector + RRF fusion
│   │   ├── reranker.py                # OpenAI embedding cosine-similarity reranker
│   │   ├── alarm_correlation.py       # NetworkX correlation graph
│   │   ├── root_cause_engine.py       # Pattern matching + LLM RCA
│   │   ├── service_impact_engine.py   # Impact quantification + LLM
│   │   ├── resolution_engine.py       # Resolution generation + LLM
│   │   ├── fallback_analyzer.py       # Offline BM25-only analysis (no API key)
│   │   └── predictive_engine.py       # Statistical outage-risk scoring
│   ├── api/
│   │   └── routes.py                  # FastAPI endpoints (/api/v1/*)
│   ├── evaluation/
│   │   └── deepeval_metrics.py        # DeepEval quality evaluation framework
│   ├── models/
│   │   └── schemas.py                 # Pydantic v2 models
│   ├── utils/
│   │   ├── guardrails.py              # Query validation + prompt-injection detection
│   │   └── token_optimizer.py         # tiktoken-based context budget management
│   ├── config.py                      # pydantic-settings configuration
│   ├── database.py                    # ChromaDB collection manager
│   ├── ingestion.py                   # CSV → chunks → embeddings pipeline
│   └── main.py                        # FastAPI app factory + lifespan startup
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── QueryPanel.jsx         # Query input + filter controls
│   │   │   ├── ResultsPanel.jsx       # Main results view (RCA, impact, resolution)
│   │   │   ├── Dashboard.jsx          # Analytics dashboard
│   │   │   ├── PredictivePanel.jsx    # Outage risk predictions
│   │   │   └── IncidentDetails.jsx    # Incident detail modal
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── index.html
├── Data/
│   ├── telecom_dataset_merged.csv     # 12,500 incidents (merged + normalised)
│   ├── telecom_dataset.csv            # Original 500-record base dataset
│   ├── 5G_Network_Performance_Dataset_12000.csv  # 12,000-record supplementary dataset
│   └── chroma_db/                     # Local ChromaDB persistent store
├── logs/
│   └── telecom_fault.log              # Rotating application log
├── generate_dataset.py                # Dataset generation script
├── test_api.py                        # API smoke tests
├── requirements.txt                   # Python dependencies
├── .env.example                       # Environment variables template
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm or yarn
- OpenAI API key *(optional — system runs in fallback mode without one)*

### 1. Backend Setup

```bash
# Install dependencies (from project root)
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set OPENAI_API_KEY=sk-... for full AI mode
# Leave it blank or unset to run in fallback (offline) mode

# Generate dataset if not already present
python generate_dataset.py

# Start backend (from project root)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  User Query (React UI — dark-theme SPA)                             │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  API Layer — FastAPI /api/v1/*                                      │
│  • Input validation + prompt-injection guardrails                   │
│  • Routes: /query  /root-cause  /impact  /correlate                 │
│            /predict/outage-risk  /dashboard/metrics  /health        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AI Mode — AgentOrchestrator  (requires OPENAI_API_KEY)             │
│  One A2ABus instance per request — full message history returned    │
│                                                                     │
│  Step 1 · AlarmRetrievalAgent                                       │
│    └─ RAGPipeline: HybridSearch (BM25 + vector, RRF fusion)         │
│       → EmbeddingReranker (OpenAI cosine-similarity, top-k=3)       │
│       → ESCALATION broadcast if critical severity detected          │
│                                                                     │
│  Step 2 · RootCauseAnalysisAgent                                    │
│    └─ RootCauseEngine: pattern matching + GPT-3.5-turbo             │
│       → A2A REQUEST to AlarmRetrievalAgent if confidence < 50 %     │
│       → NOTIFICATION broadcast "rca_complete" to downstream agents  │
│       → TokenOptimizer: 2 500-token context budget per call         │
│                                                                     │
│  Step 3 · Alarm Correlation (NetworkX graph)                        │
│    └─ Strength ≥ 70 % → Orchestrator sends cascade NOTIFICATION     │
│                                                                     │
│  Step 4 · ServiceImpactAgent                                        │
│    └─ ServiceImpactEngine: revenue-loss estimation, LLM impact      │
│       → NOTIFICATION broadcast "impact_complete"                    │
│                                                                     │
│  Step 5 · ResolutionRecommendationAgent                             │
│    └─ ResolutionEngine: ranked steps from history + LLM             │
│       → NOTIFICATION broadcast "resolution_complete"                │
│                                                                     │
│  0-incident handling: agents return graceful defaults               │
│  (confidence 0 %, priority UNKNOWN, N/A revenue, generic steps)     │
└─────────────────────────────────────────────────────────────────────┘
                            │  (no OPENAI_API_KEY → FallbackAnalyzer)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Fallback Mode — FallbackAnalyzer  (offline, no API key needed)     │
│  • BM25-style keyword + phrase scoring on telecom_dataset_merged.csv │
│  • Evidence-based RCA from declared causes in matched incidents     │
│  • Data-driven confidence, revenue-loss, correlation strength       │
│  • Generic defaults when 0 incidents match                          │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Response (same schema for both modes)                              │
│  • retrieved_incidents — similarity-ranked, with hybrid scores      │
│  • root_cause_analysis — primary/secondary causes, confidence       │
│  • service_impact_analysis — priority, revenue loss, customer impact│
│  • resolution_recommendations — ranked action steps                 │
│  • alarm_correlations — by region/vendor/technology/severity        │
│  • token_usage — per-stage context budgets and savings              │
│  • a2a_messages / a2a_stats — full inter-agent message timeline     │
└─────────────────────────────────────────────────────────────────────┘
```

## API Endpoints

All endpoints are under the `/api/v1` prefix.

### Fault Analysis

**POST /api/v1/query** — Full multi-agent workflow
```json
{
  "query": "Users in North India experiencing 5G connectivity drops",
  "region_filter": "North India",
  "severity_filter": "critical",
  "technology_filter": "5G",
  "vendor_filter": "Ericsson"
}
```

**GET /api/v1/root-cause?query=...** — Root cause analysis only

**GET /api/v1/impact?query=...** — Service impact only

**GET /api/v1/correlate?query=...** — Alarm correlation only

**GET /api/v1/evaluate?query=...** — DeepEval quality metrics

**POST /api/v1/ingest** — Re-ingest dataset into ChromaDB (AI mode only)

**POST /api/v1/reinitialize** — Reinitialize all services

### Predictive Intelligence

**GET /api/v1/predict/outage-risk** — Statistical outage-risk scores

**GET /api/v1/predict/high-risk-alerts** — Active high-risk alerts

**GET /api/v1/predict/risk-by-dimension?dimension=region|technology|vendor** — Risk breakdown

### System

**GET /api/v1/dashboard/metrics** — Analytics: incident counts, MTTR, token optimization stats

**GET /api/v1/health** — Service health and active mode (AI or fallback)

**GET /api/v1/status** — RAG pipeline and ChromaDB collection statistics

## A2A Multi-Agent Protocol

Each `execute_workflow()` call creates a fresh `A2ABus` instance. Messages are dispatched synchronously; the full history is returned in the API response under `a2a_messages`.

| Message type | Direction | Purpose |
|---|---|---|
| `NOTIFICATION` | Orchestrator → Agent | Start signals (`start_rca`, `start_impact_analysis`, …) |
| `NOTIFICATION` | Agent → broadcast | Stage completion (`rca_complete`, `impact_complete`, `resolution_complete`) |
| `ESCALATION` | AlarmRetrievalAgent → broadcast | Critical severity detected — orchestrator expands top-k to 10 |
| `REQUEST` | RootCauseAgent → AlarmRetrievalAgent | Confidence < 50 % — request expanded incident set |
| `RESPONSE` | AlarmRetrievalAgent → RootCauseAgent | Expanded incidents for re-analysis |
| `NOTIFICATION` | Orchestrator → broadcast | Cascade analysis when correlation ≥ 70 % |

## Data Processing

### Dataset
- **Source**: Synthetic 5G Network Performance Dataset
- **Records**: 500 realistic telecom incidents
- **Fields**: `alarm_id`, `incident_description`, `network_region`, `technology_type`, `severity`, `outage_duration`, `device_vendor`, `resolution_notes`, `timestamp`, `service_impact`

### Ingestion Pipeline (AI mode)
1. **Load CSV** — Data validation and cleaning
2. **Chunk Documents** — Semantic chunking (500 chars, 100 char overlap)
3. **Generate Embeddings** — OpenAI `text-embedding-3-small` (1536 dimensions)
4. **Store Vectors** — ChromaDB with cosine similarity
5. **Index for Search** — BM25Okapi tokenization for keyword search

### Hybrid Search Strategy
- **BM25 (Keyword Search)** — Fast, exact-match retrieval with `rank-bm25`
- **Vector Search (Semantic)** — Conceptual similarity via OpenAI embeddings + ChromaDB
- **Reciprocal Rank Fusion (RRF)** — Combines rankings with k=60 parameter
- **OpenAI Embedding Reranker** — Cosine-similarity cross-scoring blended 65 % reranker / 35 % hybrid score

### Token Optimization
`TokenOptimizer` (tiktoken `gpt-3.5-turbo` encoding) enforces per-engine context budgets:

| Engine | Budget | Description field cap | Resolution field cap |
|---|---|---|---|
| RootCauseEngine | 2 500 tokens | 200 tokens | 100 tokens |
| ResolutionEngine | 2 500 tokens | — | 150 tokens |

Token usage per stage is returned in the `token_usage` block of every `/api/v1/query` response.

## Multi-Agent Workflow Detail

### 1. Alarm Retrieval Agent
- Accepts natural language fault query
- Performs hybrid BM25 + vector search across 500+ incident history
- Applies metadata filters (region, severity, technology, vendor)
- Detects critical severity → sends ESCALATION broadcast to expand retrieval to top-10
- Returns top-5 most relevant incidents with hybrid similarity scores

### 2. Root Cause Analysis Agent
- Analyzes retrieved incidents against 8 telecom fault patterns
- Uses LLM (GPT-3.5-turbo) for detailed root cause reasoning
- Sends A2A REQUEST to AlarmRetrievalAgent when confidence < 50 %
- Broadcasts `rca_complete` with primary cause and confidence to downstream agents
- Produces ranked `probable_causes` list and structured `evidence_items`
- **0 incidents**: confidence 0 %, primary cause "No historical evidence available"

### 3. Alarm Correlation (NetworkX)
- Builds directed correlation graph from retrieved alarm IDs
- Computes homogeneity-weighted correlation strength across vendor/region/tech/severity/cause
- Strength ≥ 70 % → Orchestrator broadcasts `cascade_analysis` notification
- ServiceImpactAgent and ResolutionAgent promote priority and add urgency prefix accordingly

### 4. Service Impact Agent
- Reads A2A inbox for escalation/cascade/rca_complete signals before processing
- Cascade promotion: medium → high if cascade was detected
- Estimates revenue loss at $1,200/min industry rate
- Priority levels: critical / high / medium / low / **unknown** (no historical data)
- **0 incidents**: priority UNKNOWN, revenue N/A, "No Historical Evidence Available"

### 5. Resolution Recommendation Agent
- Reads impact_complete notification for priority-aware escalation prefix
- Generates ranked remediation steps from historical resolution notes + LLM
- **0 incidents**: returns 7 generic telecom troubleshooting steps, confidence 0 %

## Input Guardrails

All queries pass through `backend/utils/guardrails.py` before processing:
- Prompt injection and jailbreak pattern detection
- Query length validation (min 3, max 2 000 characters)
- Suspicious token sanitization before LLM calls

## Evaluation (DeepEval)

### Metrics
- **Answer Relevancy** — Is the response relevant to the query?
- **Faithfulness** — Are claims grounded in retrieved context?
- **Contextual Precision** — How many retrieved chunks are relevant?
- **Contextual Recall** — What fraction of relevant chunks are retrieved?
- **Telecom Troubleshooting Score** — Custom heuristic metric (no API key needed)

LLM-dependent metrics fall back to the custom heuristic automatically when no valid OpenAI key is configured.

### Usage
```python
from backend.evaluation.deepeval_metrics import get_evaluation_framework

framework = get_evaluation_framework()
metrics = framework.evaluate_troubleshooting_response(
    query="5G drops in North India",
    output="Recommended actions...",
    context=["Retrieved incident 1", "Retrieved incident 2"]
)
print(metrics)  # Returns dict with scores 0-1
```

## Predictive Intelligence

The `PredictiveOutageEngine` derives statistical outage-risk scores from the historical incident CSV — no external ML service required:

- **Risk score** (0–1) per region, technology, or vendor based on incident count, severity weight, and average outage duration
- **MTBF** (mean time between failures in hours)
- **30-day incident trend** (increasing / stable / decreasing)
- **High-risk alerts** with actionable recommendations

## Example Usage

### Command Line
```bash
# Terminal 1: start backend (from project root)
uvicorn backend.main:app --reload

# Terminal 2: start frontend
cd frontend && npm run dev

# Terminal 3: test API
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Multiple BTS towers reporting synchronization failures in South India",
    "region_filter": "South India",
    "severity_filter": "high"
  }'
```

### Web UI
1. Navigate to `http://localhost:5173`
2. Enter fault query in natural language
3. Optionally apply filters (region, severity, technology, vendor)
4. Click "Analyze Fault"
5. View results:
   - Retrieved incidents with similarity and hybrid scores
   - Root cause analysis with probability breakdown and evidence basis
   - Historical similar incidents table
   - Service impact: priority, revenue loss, outage statistics
   - Resolution recommendations with escalation guidance
   - Alarm correlation heatmap by region/vendor/technology

### Sample Queries
- "Voice call failures in Mumbai during peak hours"
- "5G handover failures between adjacent cells"
- "Fiber latency spikes between backbone nodes"
- "BTS power supply failure in tier-2 cities"
- "GSM interference from adjacent channels in rural areas"

## Configuration

Copy `.env.example` to `.env` and edit:

```bash
# OpenAI (leave blank to run in fallback mode)
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_MODEL=gpt-3.5-turbo

# ChromaDB (local — no cloud account needed)
CHROMA_DB_PATH=./Data/chroma_db

# Search
BM25_K1=2.0           # BM25 saturation parameter
BM25_B=0.75           # BM25 length normalization
HYBRID_ALPHA=0.5      # Vector/keyword balance (0=BM25 only, 1=vector only)
TOP_K_RETRIEVAL=5     # Incidents retrieved per query
RERANK_TOP_K=3        # Top-k returned after embedding reranking

# Data
DATASET_PATH=./Data/telecom_dataset_merged.csv
CHUNK_SIZE=500
CHUNK_OVERLAP=100

# API
API_PORT=8000
API_WORKERS=4
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Evaluation
EVALUATION_ENABLED=true
DEEPEVAL_MODEL=gpt-3.5-turbo
DEEPEVAL_THRESHOLD=0.7

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/telecom_fault.log
```

## Monitoring

### Logs
Application logs are written to `logs/telecom_fault.log` (DEBUG level) and to the console (INFO level).

### Dashboard Metrics (`GET /api/v1/dashboard/metrics`)
- Total incidents in dataset
- Breakdown by region / severity / technology / vendor
- Average outage duration and MTTR
- Critical incident count
- Token optimization configuration and per-engine budgets

## Performance Benchmarks

- **Fallback mode (no API key)** — ~50–200 ms end-to-end
- **AI mode — full workflow** — ~3–6 seconds (5 LLM calls + embeddings)
- **Incident retrieval** — ~200–800 ms (hybrid search on 12,500 incidents)
- **A2A messages per request** — ~15–25 messages in typical workflow

## Security Considerations

- API keys stored in `.env` (never committed)
- Prompt injection and jailbreak detection on every query
- CORS configured for trusted origins only
- Input length limits enforced at API layer
- Queries sanitized before LLM calls

## Testing

```bash
# Smoke-test all endpoints
python test_api.py

# Run pytest suite
pytest backend/ -v

# Test query latency
time curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "5G drops"}'
```

## Contributing

1. Create feature branch
2. Implement changes with full type hints
3. Add or update tests
4. Submit pull request

## References

- [ChromaDB Documentation](https://docs.trychroma.com/)
- [FastAPI Tutorial](https://fastapi.tiangolo.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/)
- [rank-bm25](https://github.com/dorianbrown/rank_bm25)
- [DeepEval](https://docs.confident-ai.com/)
- [React 18 Docs](https://react.dev/)
- [Tailwind CSS](https://tailwindcss.com/)

## License

MIT License — See LICENSE file

---

**Version**: 1.0.0  
**Status**: Production Ready  
**Last updated**: 2026-06-07
