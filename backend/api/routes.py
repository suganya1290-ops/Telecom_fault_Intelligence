import logging
import time
from typing import Dict, List, Literal, Optional, Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from backend.models.schemas import (
    QueryRequest,
    QueryResponse,
    DashboardMetrics,
    PredictiveOutageResponse,
    RiskAlert,
)
from backend.utils.guardrails import validate_query, sanitize_query

logger = logging.getLogger(__name__)

# ── Per-group routers — each gets its own Swagger tag ────────────────────────

router_analysis   = APIRouter(prefix="/api/v1", tags=["Fault Analysis"])
router_predictive = APIRouter(prefix="/api/v1", tags=["Predictive Intelligence"])
router_dashboard  = APIRouter(prefix="/api/v1", tags=["Dashboard & Metrics"])
router_system     = APIRouter(prefix="/api/v1", tags=["System"])

# Single composite router the app mounts (keeps URL structure unchanged)
router = APIRouter(prefix="/api/v1")

# ── Service handles — injected from main.py at startup ───────────────────────

orchestrator      = None
rag_pipeline      = None
predictive_engine = None
fallback_analyzer = None


def set_orchestrator(orch):      global orchestrator;      orchestrator      = orch
def set_rag_pipeline(rag):       global rag_pipeline;      rag_pipeline      = rag
def set_predictive_engine(eng):  global predictive_engine; predictive_engine = eng
def set_fallback_analyzer(fa):   global fallback_analyzer; fallback_analyzer = fa


# ── Helper: read real dataset metrics ────────────────────────────────────────

def _real_dataset_metrics() -> Dict[str, Any]:
    """Return distribution counts directly from CSV — used by the dashboard."""
    # Prefer the predictive engine's already-loaded DataFrame to avoid a second
    # file read; fall back to reading the CSV if the engine is not available.
    df: Optional[pd.DataFrame] = None
    if predictive_engine and getattr(predictive_engine, "_df", None) is not None:
        df = predictive_engine._df
    else:
        try:
            from backend.config import get_settings
            df = pd.read_csv(get_settings().dataset_path)
            df.columns = [c.lower().strip() for c in df.columns]
        except Exception:
            pass

    if df is None or df.empty:
        return {}

    avg_outage = round(float(df["outage_duration"].mean()), 1) if "outage_duration" in df.columns else 0.0

    return {
        "total_incidents":         len(df),
        "incidents_by_region":     df["network_region"].value_counts().to_dict()  if "network_region"  in df.columns else {},
        "incidents_by_severity":   df["severity"].value_counts().to_dict()        if "severity"        in df.columns else {},
        "incidents_by_technology": df["technology_type"].value_counts().to_dict() if "technology_type" in df.columns else {},
        "incidents_by_vendor":     df["device_vendor"].value_counts().to_dict()   if "device_vendor"   in df.columns else {},
        "average_outage_duration": avg_outage,
        # MTTR approximated as 60 % of average outage (heuristic — replace with
        # actual resolution-time data when available)
        "mttr": round(avg_outage * 0.60, 1),
    }


# =============================================================================
#  FAULT ANALYSIS
# =============================================================================

@router.post(
    "/query",
    tags=["Fault Analysis"],
    summary="Run full multi-agent fault analysis",
    description=(
        "Execute the complete fault-intelligence workflow: "
        "Alarm Retrieval → Root Cause Analysis → Service Impact → Resolution Recommendation. "
        "When an OpenAI key is present the AI orchestrator runs; otherwise the "
        "rule-based fallback analyser (BM25 keyword retrieval from local CSV) is used. "
        "Guardrails validate and sanitize the query before processing."
    ),
    response_description="Full analysis result including retrieved incidents, RCA, impact, resolution, and agent workflow trace",
)
async def query_fault_intelligence(request: QueryRequest) -> dict:
    is_valid, err_msg = validate_query(request.query)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)
    safe_query = sanitize_query(request.query)

    # AI path
    if orchestrator:
        try:
            start  = time.time()
            result = orchestrator.execute_workflow(
                query=safe_query,
                region_filter=request.region_filter,
                severity_filter=request.severity_filter,
                technology_filter=request.technology_filter,
                vendor_filter=request.vendor_filter,
            )
            result["processing_time_ms"] = (time.time() - start) * 1000
            logger.info(f"Query processed (AI) in {result['processing_time_ms']:.1f}ms")
            return result
        except Exception as exc:
            logger.error(f"✗ AI workflow error: {exc} — falling back to rule-based analysis")

    # Fallback path
    if fallback_analyzer:
        try:
            start  = time.time()
            result = fallback_analyzer.analyze(
                query=safe_query,
                region_filter=request.region_filter,
                severity_filter=request.severity_filter,
                technology_filter=request.technology_filter,
                vendor_filter=request.vendor_filter,
            )
            result["processing_time_ms"] = (time.time() - start) * 1000
            logger.info(f"Query processed (fallback) in {result['processing_time_ms']:.1f}ms")
            return result
        except Exception as exc:
            logger.error(f"✗ Fallback analysis error: {exc}")
            raise HTTPException(status_code=500, detail="Analysis failed — see server logs")

    raise HTTPException(
        status_code=503,
        detail="No analysis service available. Please restart the backend.",
    )


@router.get(
    "/root-cause",
    tags=["Fault Analysis"],
    summary="Root cause analysis only",
    description=(
        "Convenience endpoint: runs the full workflow and returns only the "
        "root-cause block. Useful for lightweight integrations that don't need "
        "service-impact or resolution data."
    ),
)
async def analyze_root_cause(
    query: str = Query(..., description="Natural language fault query", min_length=3, max_length=2000)
) -> dict:
    result = await query_fault_intelligence(QueryRequest(query=query))
    rca = result.get("root_cause_analysis") or {}
    if hasattr(rca, "dict"):
        rca = rca.dict()
    return {
        "primary_cause":    rca.get("primary_cause", ""),
        "secondary_causes": rca.get("contributing_factors", rca.get("secondary_causes", [])),
        "confidence_score": rca.get("confidence_score", 0),
        "confidence_level": rca.get("confidence_level", ""),
        "evidence_source":  rca.get("evidence_source", ""),
        "reasoning":        rca.get("analysis_reasoning", ""),
        "rca_evidence":     rca.get("rca_evidence", []),
    }


@router.get(
    "/correlate",
    tags=["Fault Analysis"],
    summary="Alarm correlation analysis only",
    description=(
        "Convenience endpoint: runs the full workflow and returns only the "
        "alarm-correlation block. Returns dimensional breakdowns by region, "
        "vendor, technology, severity, and root cause."
    ),
)
async def correlate_alarms(
    query: str = Query(..., description="Natural language fault query", min_length=3, max_length=2000)
) -> dict:
    result = await query_fault_intelligence(QueryRequest(query=query))
    corr = result.get("alarm_correlations", {})
    return {
        "correlated_alarms":    corr.get("correlated_alarms", []),
        "correlation_strength": corr.get("correlation_strength", 0),
        "cascade_risk":         corr.get("cascade_risk", False),
        "cascade_analysis":     corr.get("cascade_analysis"),
        "pattern_summary":      corr.get("pattern_summary", ""),
        "by_region":            corr.get("by_region", {}),
        "by_vendor":            corr.get("by_vendor", {}),
        "by_technology":        corr.get("by_technology", {}),
        "by_severity":          corr.get("by_severity", {}),
        "by_cause":             corr.get("by_cause", {}),
    }


@router.get(
    "/impact",
    tags=["Fault Analysis"],
    summary="Service impact analysis only",
    description=(
        "Convenience endpoint: runs the full workflow and returns only the "
        "service-impact block including revenue loss estimate and affected services."
    ),
)
async def analyze_service_impact(
    query: str = Query(..., description="Natural language fault query", min_length=3, max_length=2000)
) -> dict:
    result = await query_fault_intelligence(QueryRequest(query=query))
    impact = result.get("service_impact_analysis") or {}
    if hasattr(impact, "dict"):
        impact = impact.dict()
    return {
        "customer_impact":          impact.get("customer_impact", ""),
        "business_impact":          impact.get("business_impact", ""),
        "priority_level":           impact.get("priority_level", ""),
        "estimated_revenue_loss":   impact.get("estimated_revenue_loss", 0),
        "affected_services":        impact.get("affected_services", []),
        "affected_regions":         impact.get("affected_regions", []),
        "affected_technologies":    impact.get("affected_technologies", []),
        "affected_vendors":         impact.get("affected_vendors", []),
        "average_outage_minutes":   impact.get("average_outage_minutes", 0),
        "revenue_loss_breakdown":   impact.get("revenue_loss_breakdown"),
    }


@router.post(
    "/ingest",
    tags=["Fault Analysis"],
    summary="Ingest and re-initialise RAG pipeline",
    description=(
        "Triggers a full data ingestion cycle: reads the telecom incident CSV, "
        "generates embeddings, and re-populates the ChromaDB vector store. "
        "Only relevant when an OpenAI API key is configured."
    ),
)
async def ingest_data() -> dict:
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized — OpenAI key required")
    try:
        rag_pipeline.initialize()
        return {
            "status":           "success",
            "message":          "Data ingestion completed",
            "collection_stats": rag_pipeline.get_collection_stats(),
        }
    except Exception as exc:
        logger.error(f"✗ Ingestion error: {exc}")
        raise HTTPException(status_code=500, detail="Ingestion failed — see server logs")


@router.get(
    "/evaluate",
    tags=["Fault Analysis"],
    summary="Response quality evaluation",
    description=(
        "Evaluates the fault analysis response for the given query using the "
        "DeepEval framework.\n\n"
        "**TelecomTroubleshootingMetric** (always active — no API key needed): "
        "pure-Python scorer measuring action specificity, context relevance, "
        "output clarity, and confidence validity.\n\n"
        "**LLM-based metrics** (AnswerRelevancy, Faithfulness, ContextPrecision, "
        "ContextRecall): active only when a valid `OPENAI_API_KEY` is configured. "
        "When the key is absent or invalid these fall back to offline benchmark "
        "values and are flagged as `skipped_reason: no_valid_openai_key`."
    ),
)
async def evaluate_response(
    query: str = Query(..., description="Fault query to evaluate", min_length=3)
) -> dict:
    from backend.evaluation.deepeval_metrics import get_evaluation_framework

    # Run the full analysis first so the evaluator has real output + context
    analysis_result = await query_fault_intelligence(QueryRequest(query=query))

    # Build a flat text representation of the analysis for the evaluator
    rca    = analysis_result.get("root_cause_analysis", {}) or {}
    impact = analysis_result.get("service_impact_analysis", {}) or {}
    res    = analysis_result.get("resolution_recommendations", {}) or {}

    output_text = " ".join(filter(None, [
        rca.get("primary_cause", ""),
        rca.get("analysis_reasoning", ""),
        impact.get("customer_impact", ""),
        " ".join(res.get("recommended_actions", [])[:3]),
    ]))

    # Context = descriptions of retrieved incidents
    context_chunks = [
        inc.get("incident", inc).get("incident_description", "")
        for inc in analysis_result.get("retrieved_incidents", [])[:5]
        if isinstance(inc, dict)
    ]

    framework = get_evaluation_framework()
    metrics   = framework.evaluate_troubleshooting_response(
        query=query,
        output=output_text,
        context=context_chunks,
    )

    # Rename for API consistency
    llm_active   = metrics.get("llm_metrics_active", False)
    eval_mode    = "live_deepeval" if llm_active else "custom_metric_only"
    skipped      = metrics.get("skipped_metrics", [])

    return {
        "query":           query,
        "evaluation_mode": eval_mode,
        "metrics": {
            "telecom_troubleshooting_score": metrics.get("telecom_troubleshooting_score", 0.0),
            "answer_relevancy":              metrics.get("answer_relevancy", 0.0),
            "faithfulness":                  metrics.get("faithfulness", 0.0),
            "context_precision":             metrics.get("context_precision", 0.0),
            "context_recall":                metrics.get("context_recall", 0.0),
            "overall_score":                 metrics.get("overall_score", 0.0),
        },
        "deepeval_available": metrics.get("deepeval_available", False),
        "llm_metrics_active": llm_active,
        "skipped_metrics":    skipped,
        "skipped_reason":     metrics.get("skipped_reason"),
        "note": (
            "All metrics live (LLM + custom)." if llm_active else
            "TelecomTroubleshootingMetric scored live. "
            "LLM metrics (AnswerRelevancy, Faithfulness, etc.) show offline benchmarks "
            "— set OPENAI_API_KEY=sk-... to enable live LLM evaluation."
        ),
        "status": "evaluation_complete",
    }


# =============================================================================
#  PREDICTIVE INTELLIGENCE
# =============================================================================

@router.get(
    "/predict/outage-risk",
    tags=["Predictive Intelligence"],
    summary="Predict outage risk by region and technology",
    description=(
        "Returns outage-risk predictions derived from historical incident patterns "
        "using a weighted score formula: 40% incident frequency + 40% average severity "
        "+ 20% average outage duration. No external ML service required. "
        "Optionally scope predictions to a specific region, technology, or vendor."
    ),
)
async def predict_outage_risk(
    region:     Optional[str] = Query(None, description="Filter by network region (e.g. 'South India')"),
    technology: Optional[str] = Query(None, description="Filter by technology (e.g. '5G', 'LTE')"),
    vendor:     Optional[str] = Query(None, description="Filter by device vendor (e.g. 'Ericsson')"),
) -> dict:
    if not predictive_engine:
        raise HTTPException(status_code=503, detail="Predictive engine not initialized")
    try:
        return predictive_engine.predict_outage_risk(region=region, technology=technology, vendor=vendor)
    except Exception as exc:
        logger.error(f"✗ Prediction error: {exc}")
        raise HTTPException(status_code=500, detail="Prediction failed — see server logs")


@router.get(
    "/predict/high-risk-alerts",
    tags=["Predictive Intelligence"],
    summary="Get active high-risk alerts",
    description=(
        "Returns all regions, technologies, and vendors whose computed risk score "
        "exceeds the HIGH threshold (≥ 0.65). Also includes a trend-based alert "
        "when the 30-day incident rate is rising. Results are sorted by risk score descending."
    ),
)
async def get_high_risk_alerts() -> dict:
    if not predictive_engine:
        raise HTTPException(status_code=503, detail="Predictive engine not initialized")
    try:
        alerts = predictive_engine.get_high_risk_alerts()
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as exc:
        logger.error(f"✗ Alert generation error: {exc}")
        raise HTTPException(status_code=500, detail="Alert generation failed — see server logs")


@router.get(
    "/predict/risk-by-dimension",
    tags=["Predictive Intelligence"],
    summary="Risk scores for all values in one dimension",
    description=(
        "Returns every entry in the requested dimension (region, technology, or vendor) "
        "sorted by risk score descending. Useful for building ranked risk leaderboards."
    ),
)
async def get_risk_by_dimension(
    dimension: Literal["region", "technology", "vendor"] = Query(
        ...,
        description="Dimension to break down: 'region', 'technology', or 'vendor'",
    )
) -> dict:
    if not predictive_engine:
        raise HTTPException(status_code=503, detail="Predictive engine not initialized")
    try:
        rows = predictive_engine.get_risk_by_dimension(dimension)
        return {"dimension": dimension, "data": rows}
    except Exception as exc:
        logger.error(f"✗ Risk-by-dimension error: {exc}")
        raise HTTPException(status_code=500, detail="Risk dimension query failed — see server logs")


# =============================================================================
#  DASHBOARD & METRICS
# =============================================================================

@router.get(
    "/dashboard/metrics",
    tags=["Dashboard & Metrics"],
    summary="Analytics dashboard metrics",
    description=(
        "Returns incident distribution metrics computed from the live dataset: "
        "counts by region, severity, technology, and vendor; average outage duration; "
        "MTTR; and a predictive summary. Works with or without an OpenAI key — "
        "all values are derived from the local CSV."
    ),
)
async def get_dashboard_metrics() -> dict:
    try:
        metrics = _real_dataset_metrics()

        workflow_metrics   = orchestrator.get_workflow_metrics()    if orchestrator      else {}
        predictive_summary = {}
        if predictive_engine:
            try:
                pred = predictive_engine.predict_outage_risk()
                predictive_summary = pred.get("summary", {})
            except Exception:
                pass

        return {
            **metrics,
            "rag_available":       rag_pipeline      is not None,
            "ai_mode":             orchestrator      is not None,
            "fallback_available":  fallback_analyzer is not None,
            "workflow_metrics":    workflow_metrics,
            "predictive_summary":  predictive_summary,
            "token_optimization": {
                "active":             True,
                "engine":             "tiktoken (gpt-3.5-turbo encoding)",
                "max_context_tokens": 2500,
                "rca_field_caps":     {"description": "200 tokens", "resolution": "100 tokens"},
                "resolution_field_caps": {"resolution_notes": "150 tokens"},
                "features": [
                    "per-field token budgeting replaces fixed char slicing",
                    "global context budget via reciprocal-rank-fusion priority",
                    "prompt token count logged before every LLM call",
                    "before/after savings measured per request (see token_usage in /query)",
                ],
            },
        }
    except Exception as exc:
        logger.error(f"✗ Dashboard metrics error: {exc}")
        raise HTTPException(status_code=500, detail="Metrics unavailable — see server logs")


# =============================================================================
#  SYSTEM
# =============================================================================

@router.get(
    "/health",
    tags=["System"],
    summary="Service health check",
    description=(
        "Returns the operational status of each internal service. "
        "Use this for load-balancer health probes. "
        "The endpoint always returns 200 — check the `services` object for individual status."
    ),
)
async def health_check() -> dict:
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "orchestrator":      orchestrator      is not None,
            "rag_pipeline":      rag_pipeline      is not None and getattr(rag_pipeline, "is_initialized", False),
            "predictive_engine": predictive_engine is not None and getattr(predictive_engine, "_loaded", False),
            "fallback_analyzer": fallback_analyzer is not None and getattr(fallback_analyzer, "_loaded", False),
        },
        "analysis_mode": "ai" if orchestrator else "fallback" if fallback_analyzer else "unavailable",
    }


@router.get(
    "/status",
    tags=["System"],
    summary="RAG pipeline status",
    description="Returns ChromaDB collection statistics and RAG initialization state.",
)
async def get_status() -> dict:
    stats = rag_pipeline.get_collection_stats() if rag_pipeline else {}
    return {
        "rag_initialized":    getattr(rag_pipeline, "is_initialized", False) if rag_pipeline else False,
        "collection_stats":   stats,
        "timestamp":          time.time(),
    }


@router.post(
    "/reinitialize",
    tags=["System"],
    summary="Clear and re-initialise RAG pipeline",
    description=(
        "Drops the existing ChromaDB collection and re-ingests the full dataset. "
        "Use only after dataset updates. Requires a valid OpenAI API key."
    ),
)
async def reinitialize_pipeline() -> dict:
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized — OpenAI key required")
    try:
        rag_pipeline.clear_and_reinitialize()
        return {
            "status":           "success",
            "message":          "Pipeline reinitialized",
            "collection_stats": rag_pipeline.get_collection_stats(),
        }
    except Exception as exc:
        logger.error(f"✗ Reinitialize error: {exc}")
        raise HTTPException(status_code=500, detail="Reinitialization failed — see server logs")
