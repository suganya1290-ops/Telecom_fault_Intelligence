# System Architecture Document

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                                │
│                  (React 18 + Vite + Tailwind)                        │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Query Panel  │  │  Dashboard   │  │ Predictive Intelligence  │   │
│  │ - Input box  │  │  - KPI cards │  │ - Risk scores            │   │
│  │ - Filters    │  │  - Charts    │  │ - MTBF, trend            │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
│                                                                      │
│  Results Panel sub-tabs (after /query):                              │
│  ┌────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐      │
│  │ Root Cause │ │ Impact & Fix │ │ Evidence │ │  Timeline    │      │
│  │ + Enhance  │ │              │ │          │ │ (A2A log)    │      │
│  │   with AI  │ │              │ │          │ │              │      │
│  └────────────┘ └──────────────┘ └──────────┘ └──────────────┘      │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ HTTP/JSON
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         API LAYER                                    │
│                    (FastAPI + Uvicorn)                                │
│  Prefix: /api/v1/                                                    │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ POST /query    │  │ POST /enhance    │  │ /root-cause         │  │
│  │ POST /ingest   │  │ /reinitialize    │  │ /correlate /impact  │  │
│  └────────────────┘  └──────────────────┘  └─────────────────────┘  │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ /health        │  │ /dashboard/      │  │ /predict/           │  │
│  │ /status        │  │   metrics        │  │   outage-risk       │  │
│  └────────────────┘  └──────────────────┘  │   high-risk-alerts  │  │
│                                            │   risk-by-dimension │  │
│                                            └─────────────────────┘  │
│  Guardrails: prompt-injection detection + query sanitization         │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌──────────────┐ ┌────────────────────┐
│  OLLAMA+BM25    │ │  BM25 ONLY   │ │   AI MODE          │
│  MODE           │ │  FALLBACK    │ │   (optional)       │
│  (default)      │ │              │ │                    │
│                 │ │ FallbackAna- │ │ AgentOrchestrator  │
│ FallbackAnalyzer│ │ lyzer only   │ │ + RAGPipeline      │
│ + OllamaRCA-    │ │              │ │ (requires          │
│ Enhancer        │ │ • BM25 on    │ │  OPENAI_API_KEY    │
│                 │ │   local CSV  │ │  sk-...)           │
│ • BM25 instant  │ │ • No LLM     │ │                    │
│   retrieval     │ │              │ │ Full A2A 5-agent   │
│ • Llama 3.2 LLM │ │              │ │ workflow +         │
│   reasoning via │ │              │ │ vector RAG         │
│   /enhance btn  │ │              │ │                    │
│ • 0.5s timeout  │ │              │ │                    │
│   on /query;    │ │              │ │                    │
│   35s on        │ │              │ │                    │
│   /enhance      │ │              │ │                    │
└────────┬────────┘ └──────┬───────┘ └─────────┬──────────┘
         └─────────────────┴─────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     SERVICES LAYER                                   │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ FallbackAnalyzer │  │ OllamaRCA-   │  │ PredictiveOutage-    │   │
│  │ (BM25 on CSV)    │  │ Enhancer     │  │ Engine               │   │
│  │                  │  │ (Llama 3.2 / │  │ (stats, no ML svc)   │   │
│  │ • BM25Okapi      │  │  Groq /      │  │                      │   │
│  │ • Evidence RCA   │  │  OpenAI      │  │ • Risk score 0-1     │   │
│  │ • Correlation    │  │  compatible) │  │ • MTBF estimation    │   │
│  │ • Revenue est.   │  │              │  │ • 30-day trend       │   │
│  └──────────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                      │
│  ── Optional (AI mode only) ──────────────────────────────────────  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ RAGPipeline  │  │ RootCause-   │  │ ServiceImpact│               │
│  │ HybridSearch │  │ Engine       │  │ Engine       │               │
│  │ BM25+Vector  │  │ (pattern +   │  │ (LLM impact) │               │
│  │ +RRF+Reranker│  │  LLM)        │  │              │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ TokenOptimizer (tiktoken)  ·  AlarmCorrelation (NetworkX)   │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   DATA PERSISTENCE LAYER                             │
│  ┌──────────────────────────────┐  ┌─────────────────────────────┐  │
│  │ telecom_dataset_merged.csv   │  │ ChromaDB (optional, AI mode)│  │
│  │ 12,500 incidents             │  │ • cosine similarity         │  │
│  │ • BM25 index (in-memory)     │  │ • metadata filtering        │  │
│  │ • Fallback + Predictive src  │  │ • 1536-dim embeddings       │  │
│  └──────────────────────────────┘  └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Data Flow

### 2.1 Primary Mode — Ollama + BM25 (`ollama+bm25`)

This is the default operating mode. No ChromaDB initialisation or batch embedding required — startup is instant.

```
USER QUERY (Natural Language)
        ↓
  [Guardrails] — prompt-injection check, sanitize, length 3–2000 chars
        ↓
  [Apply Filters] — region / severity / technology / vendor
        ↓
  FallbackAnalyzer.analyze()  (BM25 keyword + phrase scoring on CSV)
        ↓
  ┌─────────────────────────────────────────────────────────┐
  │  BM25 RESULT (instant, <200ms)                          │
  │  • retrieved_incidents                                  │
  │  • root_cause_analysis   (evidence-based from CSV)      │
  │  • service_impact_analysis                              │
  │  • resolution_recommendations                           │
  │  • alarm_correlations                                   │
  └──────────────────────────────┬──────────────────────────┘
                                 │
               ┌─────────────────┴──────────────────┐
               │  asyncio.wait_for (timeout=0.5s)    │
               │  OllamaRCAEnhancer.enhance()         │
               │  Llama 3.2 via Ollama (CPU)          │
               │                                     │
               │  Timeout? → return BM25 result       │
               │  Success? → inject llm_reasoning     │
               │             into root_cause_analysis │
               └─────────────────────────────────────┘
                                 │
                  ┌──────────────┘
                  │   /query returns (BM25 or enhanced)
                  ▼
        [Frontend renders results]
                  │
                  │  User clicks "Enhance with AI" button
                  ▼
  POST /api/v1/enhance  (asyncio.wait_for, timeout=35s)
        ↓
  FallbackAnalyzer.analyze()  (fresh BM25 pass)
        ↓
  OllamaRCAEnhancer.enhance(..., timeout=30)
        ↓
  Returns LLM-enhanced result OR 504 if Llama >35s
```

### 2.2 Fallback Mode — BM25 Only (`bm25_fallback`)

Active when no LLM key is configured or Ollama is unreachable.

```
USER QUERY
      ↓
  [Guardrails]
      ↓
  FallbackAnalyzer.analyze()
      ↓
  [BM25 keyword + phrase scoring on telecom_dataset_merged.csv]
      ↓ 0 matches?
      ├── YES → confidence=0, priority=unknown, N/A fields, generic steps
      └── NO  →
            ├─ _build_root_cause()    evidence-based from declared causes
            ├─ _build_service_impact() priority from actual severity counts
            ├─ _build_resolution()    steps from resolution_notes
            └─ _build_correlation()   homogeneity-based strength
      ↓
  [Same response schema as AI mode]
```

### 2.3 AI Mode — Full Agent Workflow (`ai`)

Optional. Requires `OPENAI_API_KEY=sk-...`. Activates the full A2A multi-agent pipeline with ChromaDB vector retrieval.

```
USER QUERY
        ↓
  [Guardrails]
        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1 · ALARM RETRIEVAL AGENT                             │
│  1. Generate query embedding (OpenAI text-embedding-3-small)│
│  2. BM25 keyword search                                     │
│  3. Vector search (ChromaDB cosine similarity)              │
│  4. RRF fusion (k=60, alpha=0.5)                            │
│  5. Embedding reranker (OpenAI cosine-sim, 65/35 blend)     │
│  6. If critical severity → ESCALATION broadcast; top-k=10  │
└──────────────────────────┬──────────────────────────────────┘
                           ↓  [A2A NOTIFICATION "start_rca"]
┌─────────────────────────────────────────────────────────────┐
│  Step 2 · ROOT CAUSE ANALYSIS AGENT                         │
│  1. Pattern matching (8 telecom fault patterns)             │
│  2. TokenOptimizer: 2500-token context from incidents       │
│  3. LLM analysis (configured model)                         │
│  4. If confidence < 50% → A2A REQUEST for expanded retrieval│
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3 · ALARM CORRELATION (NetworkX)                      │
│  Strength ≥ 70% → Orchestrator sends CASCADE broadcast      │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4 · SERVICE IMPACT AGENT                              │
│  Revenue-loss estimation ($1,200/min × avg outage)          │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5 · RESOLUTION RECOMMENDATION AGENT                   │
│  Ranked action steps from history + LLM                     │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
              ┌────────────────────────┐
              │   FINAL REPORT         │
              │  • retrieved_incidents │
              │  • root_cause_analysis │
              │  • service_impact      │
              │  • resolution_recs     │
              │  • alarm_correlations  │
              │  • token_usage         │
              │  • a2a_messages (15–25)│
              └────────────────────────┘
```

### 2.4 Zero-Incident Handling

When no incidents match (any mode), the system returns graceful defaults instead of an error:

| Field | Value |
|---|---|
| `confidence_score` | 0.0 (0%) |
| `primary_cause` | "No historical evidence available" |
| `probable_causes` | `[]` |
| `priority_level` | "unknown" |
| `customer_impact` | "No Historical Evidence Available" |
| `estimated_revenue_loss` | 0 |
| `recommended_actions` | 7 generic telecom troubleshooting steps |
| `workflow_status` | "completed" (not "failed") |

## 3. A2A Message Bus Protocol

Used in AI mode only. Each `execute_workflow()` call creates a fresh `A2ABus` instance — no cross-request state leakage.

### Message Types

| Type | Direction | Trigger | Effect |
|---|---|---|---|
| `NOTIFICATION` | Orchestrator → Agent | Start signal for each step | Agent begins processing |
| `NOTIFICATION` | Agent → broadcast | Stage completion | Downstream agents read cause/priority/confidence |
| `ESCALATION` | AlarmRetrievalAgent → broadcast | Critical severity detected | Orchestrator expands top-k to 10 |
| `REQUEST` | RootCauseAgent → AlarmRetrievalAgent | Confidence < 50% | Returns expanded incident set via RESPONSE |
| `RESPONSE` | AlarmRetrievalAgent → RootCauseAgent | Received REQUEST | RCA re-runs on richer context |
| `NOTIFICATION` | Orchestrator → broadcast | Correlation strength ≥ 70% | ServiceImpact/Resolution agents activate cascade mode |

## 4. Design Decisions

### 4.1 Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Primary LLM | Ollama (llama3.2) / Groq / OpenAI (OpenAI-compatible API) | Instant startup, no embeddings required; provider-agnostic via base_url swap |
| LLM timeout strategy | 0.5s on /query (deferred); 35s on /enhance | Keeps /query fast; users opt-in to Llama via Enhance button |
| Keyword search | rank-bm25 (BM25Okapi) | Fast, exact-match for telecom terminology (BTS, MTTR, NTP, RAN) |
| Fallback analyzer | FallbackAnalyzer (BM25 + CSV) | System runs offline without any API key |
| Optional embeddings | OpenAI text-embedding-3-small (1536-dim) | Used in AI mode only for vector retrieval |
| Optional vector DB | ChromaDB (local SQLite) | AI mode only; no cloud required |
| Search fusion | RRF (k=60) | Robust rank combination without score normalization |
| Reranking | OpenAI embedding cosine-sim | AI mode only; 65/35 reranker/hybrid blend |
| Token management | tiktoken | Enforces per-field and per-engine token budgets |
| Graph analysis | NetworkX | Directed graph algorithms for alarm correlation |
| Predictive scoring | PredictiveOutageEngine (stats) | No ML service required |
| Guardrails | Custom regex + sanitizer | Prompt injection and jailbreak detection |
| Backend | FastAPI + Uvicorn | Async, type-safe, auto-generated OpenAPI docs |
| Frontend | React 18 + Vite + Tailwind | Dark-theme SPA, fast HMR, responsive |
| Evaluation | DeepEval | RAG quality metrics; falls back to heuristic when no key |
| Agent orchestration | Custom A2A Bus (AI mode) | Full cascade control, per-request isolation, zero extra deps |

### 4.2 Three-Mode Architecture

The backend auto-detects the active mode at startup:

```
OPENAI_BASE_URL points to Ollama (port 11434)?
  └── YES + non-empty key → OllamaRCAEnhancer initialised
        mode = "ollama+bm25"

OPENAI_API_KEY = sk-... (real OpenAI)?
  └── YES → AgentOrchestrator + RAGPipeline initialised
        mode = "ai"

No valid key / Ollama unreachable?
  └── mode = "bm25_fallback"  (FallbackAnalyzer only)
```

All three modes expose the same response schema and the same API surface.

### 4.3 Deferred LLM Enhancement

Llama 3.2 running on CPU can take 20–30s. Blocking `/query` for that duration would make the UI feel unresponsive. The solution is a two-phase design:

1. **`POST /query`** — returns BM25 result instantly (< 200ms). Tries Ollama with a 0.5s timeout; if it doesn't respond in time, returns BM25 as-is.
2. **`POST /enhance`** — dedicated endpoint with a 35s timeout. The frontend calls this when the user clicks "Enhance with AI", overlaying the LLM reasoning on the already-visible BM25 result.

Cloud providers (Groq, OpenAI) use a 10s timeout on `/query` and complete inline without needing the enhance button.

### 4.4 Why Custom A2A Bus (not LangGraph)?

- **Full cascade control** — ESCALATION and REQUEST/RESPONSE paths require explicit routing logic
- **Per-request isolation** — a fresh bus per `execute_workflow()` guarantees no cross-request leakage
- **Zero extra dependencies** — no `langgraph` or `langchain` packages
- **Full message history** — every message returned in `a2a_messages` for UI rendering and debugging

### 4.5 Token Optimization

All LLM calls use `TokenOptimizer` (tiktoken) to enforce context budgets:

| Engine | Max context | Description cap | Resolution cap |
|---|---|---|---|
| RootCauseEngine | 2,500 tokens | 200 tokens/incident | 100 tokens/incident |
| ResolutionEngine | 2,500 tokens | — | 150 tokens/incident |

### 4.6 Input Guardrails

All queries pass through `backend/utils/guardrails.py`:
- Prompt injection and jailbreak pattern detection (regex)
- Query length: minimum 3 chars, maximum 2,000 chars
- Suspicious token sanitization before any LLM call
- Pydantic v2 schema validation on all API inputs

## 5. Deployment Architecture

### Local Development

```
localhost:5173     localhost:8000
  (React/Vite)       (FastAPI/Uvicorn)
      |                    |
      └──── HTTP/JSON ─────┘
                |
         ./logs/telecom_fault.log
         ./Data/telecom_dataset_merged.csv
         ./Data/chroma_db/  (AI mode only)
```

### Backend Startup Modes

```
Key / base_url in .env?
  ├── base_url → localhost:11434 (Ollama) + any key
  │     → FallbackAnalyzer + PredictiveEngine + OllamaRCAEnhancer
  │       mode = "ollama+bm25"  ← default local setup
  │
  ├── OPENAI_API_KEY = sk-... (OpenAI)
  │     → FallbackAnalyzer + PredictiveEngine + AgentOrchestrator + RAGPipeline
  │       mode = "ai"
  │
  └── No key / Ollama unreachable
        → FallbackAnalyzer + PredictiveEngine only
          mode = "bm25_fallback"
```

### Production (Docker)

```
nginx (80/443)
  ├─ serve frontend dist/
  └─ proxy /api/v1/* → FastAPI (8000)

Volumes:
  - chroma_db/   (persistent vector store, AI mode)
  - logs/        (application logs)
```

## 6. Monitoring & Observability

### Logging

| Level | Content |
|---|---|
| DEBUG | Per-agent trace, token counts, A2A message payloads |
| INFO | Stage completion, confidence scores, LLM provider/model |
| WARNING | Low confidence, LLM timeout/fallback, missing filters |
| ERROR | LLM failures, ChromaDB errors, agent exceptions |

Logs written to both console (INFO) and `logs/telecom_fault.log` (DEBUG).

### Health Check (`GET /api/v1/health`)

```json
{
  "status": "healthy",
  "mode": "ollama+bm25",
  "fallback_mode": true,
  "api_key_configured": true,
  "dataset_records": 12500,
  "services": {
    "orchestrator": false,
    "rag_pipeline": false,
    "predictive_engine": true,
    "fallback_analyzer": true,
    "ollama_enhancer": true
  }
}
```

### Dashboard Metrics (`GET /api/v1/dashboard/metrics`)

- Total incidents, breakdown by region/severity/technology/vendor
- Average outage duration and MTTR
- Token optimization configuration
- Active mode and service status

## 7. Performance Benchmarks

| Operation | BM25 fallback | Ollama+BM25 | AI mode (OpenAI) |
|---|---|---|---|
| `/query` end-to-end | 50–200 ms | 50–200 ms (BM25; Llama deferred) | 3–6 s |
| `/enhance` (Llama CPU) | — | 15–35 s | — |
| `/enhance` (Groq) | — | ~1–3 s | — |
| Incident retrieval | 10–50 ms | 10–50 ms | 200–500 ms |
| A2A messages/request | — | — | 15–25 msgs |

## 8. Security Considerations

- API keys in `.env` only — never hardcoded or logged
- Prompt injection and jailbreak detection on every query
- CORS restricted to configured trusted origins
- Query length limits enforced at API layer (3–2,000 chars)
- Enum validation on all filter parameters
- No sensitive incident data logged at INFO level

## 9. Scalability Roadmap

**Short-term:**
- Stream LLM responses to reduce perceived latency on `/enhance`
- Redis caching for repeated BM25 queries
- Groq / cloud LLM for fast inline enhancement without the deferred pattern

**Medium-term:**
- Async parallel agent execution for AI mode
- Distributed task queue (Celery + Redis)
- Increase ChromaDB index (10k+ incidents)

**Long-term:**
- Custom LLM fine-tuning on labelled telecom fault data
- Real-time incident streaming via Kafka
- Integration with OSS/BSS systems (Netcracker, Amdocs)
- Active learning loop from operator feedback

---

**Document Version**: 3.0
**Last Updated**: 2026-06-09
**Status**: Production Ready
