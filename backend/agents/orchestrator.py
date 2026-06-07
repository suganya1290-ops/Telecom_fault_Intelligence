"""
AgentOrchestrator — coordinates the multi-agent fault-intelligence workflow
using the A2A message bus.

Standard flow
─────────────
  [1] AlarmRetrieval  →  retrieve top-k incidents from RAG pipeline
  [2] RootCause       →  identify primary fault cause
  [3] Correlation     →  compute alarm correlation strength
  [4] ServiceImpact   →  quantify customer / business impact
  [5] Resolution      →  generate ranked remediation steps

A2A escalation paths (all real, bus-driven)
───────────────────────────────────────────
  AlarmRetrievalAgent detects critical severity
    → ESCALATION broadcast
    → Orchestrator reads its inbox, expands top_k to 10, re-runs retrieval

  RootCauseAgent confidence < 0.50
    → REQUEST to AlarmRetrievalAgent  (bus dispatches synchronously)
    → AlarmRetrievalAgent returns RESPONSE with expanded incidents
    → RootCauseAgent re-runs analysis on richer context
    → NOTIFICATION broadcast "rca_complete" to downstream agents

  Correlation strength ≥ 0.70
    → Orchestrator sends NOTIFICATION broadcast "cascade_analysis"
    → ServiceImpactAgent and ResolutionAgent read it from their inboxes
      before they process, and adjust their analysis accordingly

All messages (24+ per typical workflow) are returned in `a2a_messages`
and `a2a_stats` in the API response, and rendered as a timeline in the UI.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.agents.a2a_protocol import A2ABus, MessageType, make_message
from backend.agents.alarm_retrieval_agent import AlarmRetrievalAgent
from backend.agents.resolution_agent import ResolutionRecommendationAgent
from backend.agents.root_cause_agent import RootCauseAnalysisAgent
from backend.agents.service_impact_agent import ServiceImpactAgent
from backend.services.alarm_correlation import AlarmCorrelationEngine

logger = logging.getLogger(__name__)

_LOW_CONFIDENCE_THRESHOLD  = 0.50
_HIGH_CORRELATION_THRESHOLD = 0.70


class AgentOrchestrator:
    """
    Orchestrates the multi-agent workflow via an A2A message bus.

    One A2ABus instance is created per `execute_workflow()` call so that
    every request gets a clean message history with no cross-request leakage.
    """

    def __init__(
        self,
        rag_pipeline:          Any,
        root_cause_engine:     Any,
        service_impact_engine: Any,
        resolution_engine:     Any,
    ) -> None:
        self.rag_pipeline             = rag_pipeline
        self.alarm_correlation_engine = AlarmCorrelationEngine()

        # Agent instances are reused across requests; the bus is per-request
        self.alarm_retrieval_agent = AlarmRetrievalAgent(rag_pipeline)
        self.root_cause_agent      = RootCauseAnalysisAgent(root_cause_engine)
        self.service_impact_agent  = ServiceImpactAgent(service_impact_engine)
        self.resolution_agent      = ResolutionRecommendationAgent(resolution_engine)

        logger.info("✓ AgentOrchestrator initialised with A2A bus support")

    # ── Public API ────────────────────────────────────────────────────────────

    def execute_workflow(
        self,
        query:             str,
        region_filter:     Optional[str] = None,
        severity_filter:   Optional[str] = None,
        technology_filter: Optional[str] = None,
        vendor_filter:     Optional[str] = None,
    ) -> Dict[str, Any]:
        query_id = str(uuid.uuid4())[:8]
        logger.info(f"[Orchestrator] Workflow start — id={query_id}")

        # ── Fresh A2A bus for this request ─────────────────────────────────────
        bus = A2ABus()

        # Register orchestrator as a participant so it can receive broadcasts
        bus.register("Orchestrator")

        # Wire each agent to the bus (agents register themselves + their handlers)
        self.alarm_retrieval_agent.set_bus(bus)
        self.root_cause_agent.set_bus(bus)
        self.service_impact_agent.set_bus(bus)
        self.resolution_agent.set_bus(bus)

        try:
            state = self._init_state(
                query, region_filter, severity_filter,
                technology_filter, vendor_filter, query_id,
            )

            # ── Step 1: Alarm Retrieval ────────────────────────────────────────
            logger.info("[Orchestrator] Step 1 — Alarm Retrieval")
            bus.send(make_message(
                "Orchestrator", "AlarmRetrievalAgent", MessageType.NOTIFICATION,
                {
                    "reason": "start_retrieval",
                    "query":  query,
                    "top_k":  state.get("top_k_override") or 5,
                },
            ))
            state = self.alarm_retrieval_agent.process(state)

            if not state.get("retrieved_incidents"):
                logger.warning("[Orchestrator] No incidents retrieved — proceeding with defaults")
                state["zero_incidents"] = True

            # ── A2A: react to ESCALATION broadcast from AlarmRetrievalAgent ───
            for msg in bus.receive("Orchestrator"):
                if (
                    msg.msg_type == MessageType.ESCALATION
                    and msg.payload.get("reason") == "critical_severity_detected"
                ):
                    critical_ids = msg.payload.get("critical_alarm_ids", [])
                    logger.info(
                        f"[Orchestrator] ← ESCALATION: {len(critical_ids)} critical alarm(s) "
                        "— expanding retrieval to top_k=10"
                    )
                    state["escalation_mode"]  = "critical"
                    state["top_k_override"]   = 10

                    # Notify AlarmRetrievalAgent that deep-analysis mode is active
                    bus.send(make_message(
                        "Orchestrator", "AlarmRetrievalAgent", MessageType.NOTIFICATION,
                        {
                            "reason":        "deep_analysis_expansion",
                            "top_k":         10,
                            "trigger_alarms": critical_ids,
                        },
                    ))
                    state = self.alarm_retrieval_agent.process(state)
                    break

            self._add_alarms_to_correlation(state.get("retrieved_incidents", []))

            # ── Step 2: Root Cause Analysis ────────────────────────────────────
            logger.info("[Orchestrator] Step 2 — Root Cause Analysis")
            bus.send(make_message(
                "Orchestrator", "RootCauseAgent", MessageType.NOTIFICATION,
                {
                    "reason":           "start_rca",
                    "incidents_count":  len(state.get("retrieved_incidents", [])),
                },
            ))
            state = self.root_cause_agent.process(state)

            # Drain orchestrator inbox (picks up rca_complete broadcast)
            for msg in bus.receive("Orchestrator"):
                if msg.payload.get("reason") == "rca_complete":
                    logger.info(
                        f"[Orchestrator] ← rca_complete: "
                        f"cause={msg.payload.get('primary_cause')!r}, "
                        f"conf={msg.payload.get('confidence_score', 0):.0%}"
                    )

            # ── Step 3: Alarm Correlation ──────────────────────────────────────
            logger.info("[Orchestrator] Step 3 — Alarm Correlation")
            alarm_ids          = [
                inc.incident.alarm_id
                for inc in state.get("retrieved_incidents", [])
            ]
            correlation_result = self.alarm_correlation_engine.correlate_alarms(alarm_ids)
            state["alarm_correlations"] = correlation_result

            # ── A2A: cascade analysis broadcast when correlation is high ───────
            corr_strength = correlation_result.get("correlation_strength", 0.0)
            if corr_strength >= _HIGH_CORRELATION_THRESHOLD:
                state["cascade_analysis"] = True
                bus.send(make_message(
                    "Orchestrator", "broadcast", MessageType.NOTIFICATION,
                    {
                        "reason":               "cascade_analysis",
                        "correlation_strength": round(corr_strength, 3),
                        "detail": (
                            f"High alarm correlation ({corr_strength:.0%}) — "
                            "cascade impact analysis required"
                        ),
                    },
                ))
                logger.info(
                    f"[Orchestrator] CASCADE broadcast (strength={corr_strength:.0%})"
                )

            # ── Step 4: Service Impact ─────────────────────────────────────────
            logger.info("[Orchestrator] Step 4 — Service Impact")
            bus.send(make_message(
                "Orchestrator", "ServiceImpactAgent", MessageType.NOTIFICATION,
                {
                    "reason":  "start_impact_analysis",
                    "cascade": state.get("cascade_analysis", False),
                },
            ))
            state = self.service_impact_agent.process(state)

            # ── Step 5: Resolution Recommendation ─────────────────────────────
            logger.info("[Orchestrator] Step 5 — Resolution Recommendation")
            bus.send(make_message(
                "Orchestrator", "ResolutionAgent", MessageType.NOTIFICATION,
                {
                    "reason":  "start_resolution",
                    "cascade": state.get("cascade_analysis", False),
                },
            ))
            state = self.resolution_agent.process(state)

            # ── Workflow-complete broadcast ─────────────────────────────────────
            bus.send(make_message(
                "Orchestrator", "broadcast", MessageType.NOTIFICATION,
                {
                    "reason":   "workflow_complete",
                    "query_id": query_id,
                    "steps_completed": 5,
                },
            ))

            # ── Attach full A2A history to state for API response ──────────────
            state["a2a_messages"] = bus.get_history()
            state["a2a_stats"]    = bus.stats()

            # ── Assemble token_usage from all pipeline stages ──────────────────
            state["token_usage"]  = self._build_token_usage(state)

            state["final_report"] = self._build_report(state, query_id, bus)

            logger.info(
                f"[Orchestrator] ✓ Workflow complete — id={query_id}, "
                f"a2a_messages={len(state['a2a_messages'])}"
            )
            return state

        except Exception as exc:
            logger.error(f"[Orchestrator] ✗ Workflow error: {exc}")
            return self._error_response(query_id, str(exc), bus)

    def get_workflow_metrics(self) -> Dict[str, Any]:
        return {
            "rag_collection_stats": self.rag_pipeline.get_collection_stats(),
            "agents_active":        4,
            "escalation_thresholds": {
                "low_confidence":   _LOW_CONFIDENCE_THRESHOLD,
                "high_correlation": _HIGH_CORRELATION_THRESHOLD,
            },
            "last_execution": datetime.now().isoformat(),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _init_state(
        self,
        query:     str,
        region:    Optional[str],
        severity:  Optional[str],
        technology:Optional[str],
        vendor:    Optional[str],
        query_id:  str,
    ) -> Dict[str, Any]:
        return {
            "query_id":           query_id,
            "query":              query,
            "region_filter":      region,
            "severity_filter":    severity,
            "technology_filter":  technology,
            "vendor_filter":      vendor,
            # Results populated by agents
            "retrieved_incidents":        [],
            "root_cause_analysis":        None,
            "service_impact_analysis":    None,
            "resolution_recommendations": None,
            "alarm_correlations":         {},
            "final_report":               None,
            # A2A state flags
            "escalation_mode":   None,    # None | "critical"
            "cascade_analysis":  False,
            "re_retrieval_done": False,
            "top_k_override":    None,
            # Will be filled after workflow completes
            "a2a_messages": [],
            "a2a_stats":    {},
            # Human-readable agent event log
            "messages": [
                {
                    "role":      "user",
                    "content":   query,
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

    def _add_alarms_to_correlation(self, incidents: List[Any]) -> None:
        for inc in incidents:
            try:
                self.alarm_correlation_engine.add_alarm(inc.incident.dict())
            except Exception as exc:
                logger.warning(f"[Orchestrator] Correlation add skipped: {exc}")

    def _build_report(
        self,
        state:    Dict[str, Any],
        query_id: str,
        bus:      A2ABus,
    ) -> Dict[str, Any]:
        rca        = state.get("root_cause_analysis")
        impact     = state.get("service_impact_analysis")
        resolution = state.get("resolution_recommendations")
        a2a_stats  = bus.stats()

        summary_lines = [
            f"Root Cause: {rca.primary_cause if rca else 'Unknown'}",
            f"Priority:   {impact.priority_level if impact else 'Unknown'}",
            f"Est. Resolution: {resolution.estimated_resolution_time if resolution else '?'} min",
            f"Confidence: {rca.confidence_score:.0%}" if rca else "Confidence: N/A",
            f"A2A Messages: {a2a_stats.get('total_messages', 0)}",
        ]
        if state.get("escalation_mode") == "critical":
            summary_lines.append("⚠ CRITICAL ESCALATION: deep-analysis mode activated")
        if state.get("cascade_analysis"):
            summary_lines.append("⚠ CASCADE ANALYSIS: high alarm correlation detected")
        if state.get("re_retrieval_done"):
            summary_lines.append("↺ RE-RETRIEVAL: expanded context via A2A request")

        return {
            "query_id":        query_id,
            "query":           state.get("query", ""),
            "timestamp":       datetime.now().isoformat(),
            "workflow_status": "completed",
            "escalation_mode": state.get("escalation_mode"),
            "cascade_analysis":state.get("cascade_analysis", False),
            "re_retrieval":    state.get("re_retrieval_done", False),
            "a2a_stats":       a2a_stats,
            "summary":         "\n".join(summary_lines),
            "details": {
                "retrieved_incidents_count": len(state.get("retrieved_incidents", [])),
                "root_cause":    rca.dict()        if rca        else {},
                "service_impact":impact.dict()     if impact     else {},
                "resolution_recommendations": resolution.dict() if resolution else {},
                "alarm_correlations":         state.get("alarm_correlations", {}),
            },
            "agent_messages": state.get("messages", []),
        }

    def _build_token_usage(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate per-stage token stats into a single summary block."""
        retrieval  = getattr(self.rag_pipeline, "last_token_usage", {})
        per_engine = state.get("_token_usage", {})

        rca = per_engine.get("rca", {})
        res = per_engine.get("resolution", {})
        imp = per_engine.get("impact", {})

        total_raw = rca.get("raw_tokens", 0) + res.get("raw_tokens", 0)
        total_ctx = rca.get("context_tokens", 0) + res.get("context_tokens", 0)
        total_sav = round(
            (total_raw - total_ctx) / max(total_raw, 1) * 100, 1
        ) if total_raw else 0.0

        return {
            "retrieval":  retrieval,
            "rca":        rca,
            "impact":     imp,
            "resolution": res,
            "totals": {
                "raw_context_tokens":       total_raw,
                "optimized_context_tokens": total_ctx,
                "total_savings_pct":        total_sav,
                "rca_prompt_tokens":        rca.get("prompt_tokens", 0),
                "impact_prompt_tokens":     imp.get("prompt_tokens", 0),
                "resolution_prompt_tokens": res.get("prompt_tokens", 0),
            },
        }

    @staticmethod
    def _error_response(
        query_id:  str,
        error_msg: str,
        bus:       Optional[A2ABus] = None,
    ) -> Dict[str, Any]:
        return {
            "query_id":        query_id,
            "workflow_status": "failed",
            "error":           error_msg,
            "timestamp":       datetime.now().isoformat(),
            "a2a_messages":    bus.get_history() if bus else [],
            "a2a_stats":       bus.stats()       if bus else {},
        }
