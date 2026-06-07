# System Architecture Document

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                                │
│                  (React 18 + Vite + Tailwind)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Query Panel  │  │  Dashboard   │  │ Results Panel            │   │
│  │ - Input box  │  │  - Charts    │  │ - RCA + Probable Causes  │   │
│  │ - Filters    │  │  - Metrics   │  │ - Impact + Revenue       │   │
│  └──────────────┘  └──────────────┘  │ - Resolution Steps       │   │
│  ┌──────────────┐  ┌──────────────┐  │ - A2A Timeline           │   │
│  │ Predictive   │  │ Incident     │  └──────────────────────────┘   │
│  │ Panel        │  │ Details      │                                  │
│  └──────────────┘  └──────────────┘                                  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ HTTP/JSON
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         API LAYER                                    │
│                    (FastAPI + Uvicorn)                                │
│  Prefix: /api/v1/                                                    │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ /query         │  │ /root-cause      │  │ /correlate          │  │
│  │ /ingest        │  │ /evaluate        │  │ /impact             │  │
│  │ /reinitialize  │  │ /health /status  │  │ /dashboard/metrics  │  │
│  └────────────────┘  └──────────────────┘  └─────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ /predict/outage-risk  /predict/high-risk-alerts                │  │
│  │ /predict/risk-by-dimension                                     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Guardrails: prompt-injection detection + query sanitization         │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
┌────────────────────────┐  ┌────────────────────────────────────────┐
│   FALLBACK MODE        │  │         AI MODE                        │
│   FallbackAnalyzer     │  │         AgentOrchestrator              │
│   (no API key needed)  │  │   (requires OPENAI_API_KEY)            │
│                        │  │                                        │
│ • BM25 keyword search  │  │  ┌─────────────────────────────────┐   │
│   on local CSV         │  │  │     A2ABus (per request)        │   │
│ • Evidence-based RCA   │  │  │  REQUEST / RESPONSE /           │   │
│   from declared causes │  │  │  NOTIFICATION / ESCALATION      │   │
│ • Data-driven          │  │  └──────────────┬──────────────────┘   │
│   confidence scoring   │  │                 │                       │
│ • Predictive engine    │  │   Step 1 AlarmRetrievalAgent            │
│   (outage risk stats)  │  │   Step 2 RootCauseAnalysisAgent         │
│                        │  │   Step 3 Alarm Correlation              │
└────────────────────────┘  │   Step 4 ServiceImpactAgent             │
                            │   Step 5 ResolutionRecommendationAgent  │
                            └────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     SERVICES LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ RAGPipeline  │  │ RootCause    │  │ ServiceImpact│               │
│  │              │  │ Engine       │  │ Engine       │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                  │                       │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐               │
│  │ HybridSearch │  │ GPT-3.5-turbo│  │ GPT-3.5-turbo│               │
│  │ BM25+Vector  │  │ + Pattern    │  │ + LLM Impact │               │
│  │ +RRF fusion  │  │ Matching     │  │ Assessment   │               │
│  └──────┬───────┘  └──────────────┘  └──────────────┘               │
│         │                                                            │
│  ┌──────▼───────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Embedding    │  │ Resolution   │  │ Predictive   │               │
│  │ Reranker     │  │ Engine       │  │ Outage Engine│               │
│  │ (OpenAI      │  │ GPT-3.5-turbo│  │ (stats-only) │               │
│  │ cosine-sim)  │  │ + History    │  │              │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ TokenOptimizer (tiktoken)  ·  AlarmCorrelation (NetworkX)   │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   DATA PERSISTENCE LAYER                             │
│  ┌──────────────────────────┐  ┌─────────────────────────────────┐  │
│  │ ChromaDB (local SQLite)  │  │ telecom_dataset_merged.csv (12,500 rows)│  │
│  │ • cosine similarity      │  │ • BM25 index (in-memory)        │  │
│  │ • metadata filtering     │  │ • Fallback + Predictive source  │  │
│  │ • 1536-dim embeddings    │  │                                 │  │
│  └──────────────────────────┘  └─────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Data Flow

### 2.1 AI Mode (with OPENAI_API_KEY)

```
USER QUERY (Natural Language)
        ↓
  [Guardrails] — prompt-injection check, sanitize, length 3–2000 chars
        ↓
  [Apply Filters] — region / severity / technology / vendor
        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1 · ALARM RETRIEVAL AGENT                             │
│  1. Generate query embedding (OpenAI text-embedding-3-small)│
│  2. BM25 keyword search                                     │
│  3. Vector search (ChromaDB cosine similarity)              │
│  4. RRF fusion (k=60, alpha=0.5)                            │
│  5. Embedding reranker (OpenAI cosine-sim, 65/35 blend)     │
│  6. If critical severity → ESCALATION broadcast; top-k=10  │
│  Output: Top-5 incidents with hybrid scores                 │
└──────────────────────────┬──────────────────────────────────┘
                           ↓  [A2A NOTIFICATION "start_rca"]
┌─────────────────────────────────────────────────────────────┐
│  Step 2 · ROOT CAUSE ANALYSIS AGENT                         │
│  1. Pattern matching (8 telecom fault patterns)             │
│  2. TokenOptimizer: build 2500-token context from incidents │
│  3. LLM analysis (GPT-3.5-turbo)                            │
│  4. Blend LLM confidence + pattern probability              │
│  5. Build probable_causes list + evidence_items             │
│  6. If confidence < 50% → A2A REQUEST for expanded retrieval│
│  Output: Primary/secondary causes, confidence, evidence     │
│  [A2A NOTIFICATION "rca_complete" → broadcast]              │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3 · ALARM CORRELATION (NetworkX)                      │
│  1. Build directed correlation graph from alarm IDs         │
│  2. Homogeneity scoring across vendor/region/tech/severity  │
│  3. Compute weighted correlation strength                   │
│  4. If strength ≥ 70% → Orchestrator sends CASCADE broadcast│
│  Output: Correlation strength, clusters, cascade risk       │
└──────────────────────────┬──────────────────────────────────┘
                           ↓  [A2A NOTIFICATION "start_impact_analysis"]
┌─────────────────────────────────────────────────────────────┐
│  Step 4 · SERVICE IMPACT AGENT                              │
│  1. Read inbox: ESCALATION / cascade / rca_complete signals │
│  2. Cascade promotion: medium → high if cascade detected    │
│  3. LLM impact assessment (GPT-3.5-turbo)                   │
│  4. Revenue-loss estimation ($1,200/min × avg outage)       │
│  5. Priority: critical / high / medium / low / unknown      │
│  [A2A NOTIFICATION "impact_complete" → broadcast]           │
│  Output: Customer/network/business impact, revenue loss     │
└──────────────────────────┬──────────────────────────────────┘
                           ↓  [A2A NOTIFICATION "start_resolution"]
┌─────────────────────────────────────────────────────────────┐
│  Step 5 · RESOLUTION RECOMMENDATION AGENT                   │
│  1. Read inbox: impact_complete priority for escalation text│
│  2. Extract resolution steps from historical notes          │
│  3. TokenOptimizer: 2500-token context budget               │
│  4. LLM recommendations (GPT-3.5-turbo)                     │
│  5. Prepend urgency prefix if cascade or critical priority  │
│  [A2A NOTIFICATION "resolution_complete" → broadcast]       │
│  Output: Ranked action steps, escalation guidance           │
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
              │  • a2a_stats           │
              │  • processing_time_ms  │
              └────────────────────────┘
                           ↓
                  [Response to Client]
```

### 2.2 Fallback Mode (no API key)

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
            ├─ _build_root_cause()   evidence-based from declared causes
            ├─ _build_service_impact() priority from actual severity counts
            ├─ _build_resolution()   steps from resolution_notes
            └─ _build_correlation()  homogeneity-based strength
      ↓
  [Same response schema as AI mode]
      ↓
  [Response to Client]
```

### 2.3 Zero-Incident Handling

When no incidents match (either mode), the system returns graceful defaults instead of an error:

| Field | Value |
|---|---|
| `confidence_score` | 0.0 (0 %) |
| `primary_cause` | "No historical evidence available" |
| `probable_causes` | `[]` |
| `priority_level` | "unknown" |
| `customer_impact` | "No Historical Evidence Available" |
| `estimated_revenue_loss` | 0 |
| `recommended_actions` | 7 generic telecom troubleshooting steps |
| `workflow_status` | "completed" (not "failed") |

## 3. A2A Message Bus Protocol

Each `execute_workflow()` call creates a fresh `A2ABus` instance — no cross-request state leakage. All agents register themselves and dispatch messages synchronously.

### Message Types

| Type | Direction | Trigger | Effect |
|---|---|---|---|
| `NOTIFICATION` | Orchestrator → Agent | Start signal for each step | Agent begins processing |
| `NOTIFICATION` | Agent → broadcast | Stage completion | Downstream agents read cause/priority/confidence for context |
| `ESCALATION` | AlarmRetrievalAgent → broadcast | Critical severity detected | Orchestrator expands top-k to 10, re-runs retrieval |
| `REQUEST` | RootCauseAgent → AlarmRetrievalAgent | Confidence < 50 % | Returns expanded incident set via RESPONSE |
| `RESPONSE` | AlarmRetrievalAgent → RootCauseAgent | Received REQUEST | RCA re-runs on richer context |
| `NOTIFICATION` | Orchestrator → broadcast | Correlation strength ≥ 70 % | ServiceImpact/Resolution agents activate cascade mode |

### Cascade Path

```
AlarmRetrievalAgent detects critical severity
  → ESCALATION broadcast
  → Orchestrator reads inbox, sets top_k=10
  → AlarmRetrievalAgent.process() re-runs with expanded budget

RootCauseAgent confidence < 50%
  → REQUEST to AlarmRetrievalAgent (action="expand_retrieval", top_k=8)
  → AlarmRetrievalAgent dispatches RESPONSE synchronously
  → RootCauseAgent re-runs on expanded incident set

Correlation strength ≥ 70%
  → Orchestrator broadcasts "cascade_analysis" NOTIFICATION
  → ServiceImpactAgent: promotes medium → high, sets cascade_flagged=True
  → ResolutionAgent: prepends "URGENT (cascade detected)" to escalation text
```

## 4. Design Decisions

### 4.1 Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Agent orchestration | Custom A2A Bus | Full control over message routing, cascade logic, per-request isolation |
| Embeddings | OpenAI text-embedding-3-small | 1536 dimensions, cost-effective, excellent retrieval quality |
| Vector DB | ChromaDB (local SQLite) | No cloud account required, persistent, metadata filtering, Python-native |
| Keyword search | rank-bm25 (BM25Okapi) | Fast, exact-match for telecom terminology (BTS, MTTR, NTP, RAN) |
| Search fusion | RRF (k=60) | Robust rank combination without score normalization |
| Reranking | OpenAI embedding cosine-sim | No Cohere account needed; 65/35 reranker/hybrid blend improves top-k quality |
| LLM reasoning | GPT-3.5-turbo | Balances cost and quality for telecom fault analysis |
| Token management | tiktoken (gpt-3.5-turbo encoding) | Enforces per-field and per-engine token budgets; replaces character slicing |
| Graph analysis | NetworkX | Efficient directed graph algorithms for alarm correlation |
| Fallback | FallbackAnalyzer (BM25 + CSV) | System works offline without any API key |
| Predictive scoring | PredictiveOutageEngine (stats) | No ML service required; derives risk from incident history |
| Guardrails | Custom regex + sanitizer | Prompt injection and jailbreak detection before LLM calls |
| Backend | FastAPI + Uvicorn | Async, type-safe, auto-generated OpenAPI docs |
| Frontend | React 18 + Vite + Tailwind | Dark-theme SPA, fast HMR, responsive |
| Evaluation | DeepEval | Purpose-built RAG quality metrics; falls back to heuristic when no key |

### 4.2 Why Custom A2A Bus (not LangGraph)?

The implementation uses a hand-written `A2ABus` (see `backend/agents/a2a_protocol.py`) rather than a framework like LangGraph:

- **Full cascade control** — ESCALATION and REQUEST/RESPONSE paths require precise routing logic that is cleaner to express explicitly
- **Per-request isolation** — a fresh bus per `execute_workflow()` call guarantees no cross-request state leakage
- **Zero extra dependencies** — no `langgraph` or `langchain` packages required
- **Full message history** — every message is recorded and returned in `a2a_messages` for UI rendering and debugging

### 4.3 Why OpenAI Embedding Reranker (not Cohere)?

The `EmbeddingReranker` (`backend/services/reranker.py`) uses a fresh OpenAI embedding per candidate document and scores it by cosine similarity against the query embedding:

- **No additional API key** — reuses the same OpenAI client already needed for LLM calls
- **Transparent scoring** — cosine similarity is interpretable; Cohere's cross-encoder is a black box
- **Blended score** — 65 % reranker + 35 % hybrid preserves keyword signal
- **Graceful fallback** — on error, returns candidates in hybrid-score order

### 4.4 Vector Database (ChromaDB)

**Why ChromaDB?**
- No cloud account or external service required
- Persistent local storage (SQLite + parquet)
- Cosine similarity natively supported
- Metadata filtering for region/severity/technology/vendor
- Python-native, zero-config

**Alternatives considered:**
- Pinecone — hosted, external dependency, cost
- Weaviate — more features, overkill at 500 incidents
- FAISS — fast, but in-memory only, no persistence

### 4.5 Chunking Strategy

**Semantic chunking with overlap:**
- Chunk size: 500 characters
- Overlap: 100 characters
- Each chunk contains all incident fields (alarm ID, description, region, vendor, resolution notes)
- Overlap preserves boundary context across long descriptions

### 4.6 Hybrid Search Design

**Three-layer approach:**

1. **BM25 (Keyword)** — fast exact-match; handles telecom abbreviations (BTS, RAN, MTTR, NTP, NMS); parameters k1=2.0, b=0.75
2. **Vector (Semantic)** — conceptual similarity via OpenAI embeddings + ChromaDB; handles paraphrased queries and synonyms
3. **RRF Fusion** — combines both rankings: `score = 1/(k + rank)`, k=60; weighted by `hybrid_alpha=0.5`
4. **Embedding Reranker** — final OpenAI cosine-similarity pass; blends 65 % reranker score + 35 % RRF score

**Why not semantic-only?**
- Misses exact-match telecom technical terms
- Higher latency (additional embedding API call per query)
- Less interpretable for operators

### 4.7 Token Optimization

All LLM calls use `TokenOptimizer` (tiktoken) to enforce context budgets:

| Engine | Max context | Description cap | Resolution cap |
|---|---|---|---|
| RootCauseEngine | 2 500 tokens | 200 tokens/incident | 100 tokens/incident |
| ResolutionEngine | 2 500 tokens | — | 150 tokens/incident |

Savings are reported per-call in the `token_usage` block of every `/api/v1/query` response. This replaced the old fixed character slicing (`[:200]`/`[:150]`) which was wasting ~87 % of available context.

### 4.8 Agent Execution Order

```
AlarmRetrieval → RootCause → AlarmCorrelation → ServiceImpact → Resolution
      1               2              3                 4               5
```

Correlation runs **before** ServiceImpact so the cascade broadcast (step 3) reaches ServiceImpact and ResolutionAgent **before** they process, allowing priority promotion and escalation prefix to be applied in the same request.

### 4.9 Input Guardrails

All queries pass through `backend/utils/guardrails.py`:
- Prompt injection and jailbreak pattern detection (regex)
- Query length: minimum 3 chars, maximum 2 000 chars
- Suspicious token sanitization before any LLM call
- Pydantic v2 schema validation on all API inputs (enum filters, type checks)

## 5. Deployment Architecture

### Local Development

```
localhost:5173     localhost:8000
  (React/Vite)       (FastAPI/Uvicorn)
      |                    |
      └──── HTTP/JSON ─────┘
                |
         ./logs/telecom_fault.log
         ./Data/chroma_db/
         ./Data/telecom_dataset_merged.csv
```

### Backend Startup Modes

```
OPENAI_API_KEY present?
      ├── YES → RAGPipeline + AgentOrchestrator initialised
      │          (ChromaDB ingest on first run)
      └── NO  → FallbackAnalyzer + PredictiveEngine only
                (all query endpoints still functional)
```

### Production (Docker)

```
nginx (80/443)
  ├─ serve frontend dist/
  └─ proxy /api/v1/* → FastAPI (8000)

Volumes:
  - chroma_db/   (persistent vector store)
  - logs/        (application logs)
```

## 6. Monitoring & Observability

### Logging

| Level | Content |
|---|---|
| DEBUG | Detailed per-agent trace, token counts, A2A message payloads |
| INFO | Stage completion, confidence scores, query IDs |
| WARNING | Low confidence, missing filters, expansion fallbacks |
| ERROR | LLM failures, ChromaDB errors, agent exceptions |

Logs are written to both console (INFO) and `logs/telecom_fault.log` (DEBUG).

### Dashboard Metrics (`GET /api/v1/dashboard/metrics`)

- Total incidents, breakdown by region/severity/technology/vendor
- Average outage duration and MTTR
- Token optimization configuration (budgets, encoding, field caps)
- AI mode vs fallback mode status

### Health Check (`GET /api/v1/health`)

```json
{
  "status": "healthy",
  "mode": "ai",
  "services": {
    "orchestrator": true,
    "rag_pipeline": true,
    "fallback_analyzer": true,
    "predictive_engine": true
  }
}
```

## 7. Performance Benchmarks

| Operation | Fallback mode | AI mode | Bottleneck |
|---|---|---|---|
| End-to-end query | 50–200 ms | 3–6 s | LLM API calls |
| Incident retrieval | 10–50 ms | 200–500 ms | OpenAI embedding API |
| Root cause analysis | — | ~800 ms | LLM call + pattern match |
| Service impact | — | ~600 ms | LLM call |
| Resolution | — | ~700 ms | LLM call |
| A2A messages/request | — | 15–25 msgs | Synchronous dispatch |

**Optimization potential:**
- Response streaming for UI (reduce perceived latency)
- Embedding batch requests for multiple documents
- Redis caching for repeated queries

## 8. Security Considerations

- API keys in `.env` only — never hardcoded or logged
- Prompt injection and jailbreak detection on every query before LLM calls
- CORS restricted to configured trusted origins
- Query length limits enforced at API layer (3–2 000 chars)
- Enum validation on all filter parameters
- No sensitive incident data logged at INFO level

## 9. Scalability Roadmap

**Short-term:**
- Increase ChromaDB index (10 k+ incidents)
- Add Redis caching for repeated queries
- Stream LLM responses to the UI

**Medium-term:**
- Async parallel agent execution for independent steps
- Distributed task queue (Celery + Redis)
- Multi-region ChromaDB sharding

**Long-term:**
- Custom LLM fine-tuning on labelled telecom fault data
- Real-time incident streaming via Kafka
- Integration with OSS/BSS systems (Netcracker, Amdocs)
- Active learning loop from operator feedback

---

**Document Version**: 2.0  
**Last Updated**: 2026-06-07  
**Status**: Production Ready
