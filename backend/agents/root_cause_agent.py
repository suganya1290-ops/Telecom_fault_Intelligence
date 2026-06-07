"""
RootCauseAnalysisAgent — identifies the primary fault cause from retrieved incidents.

A2A participation
-----------------
Sends (when confidence < LOW_CONFIDENCE_THRESHOLD)
  REQUEST  → AlarmRetrievalAgent  action="expand_retrieval"
             Bus dispatches synchronously; agent reads the RESPONSE from its own inbox
             and re-runs analysis on the expanded incident set.

Sends (always, after analysis completes)
  NOTIFICATION broadcast  reason="rca_complete"
  Downstream agents (ServiceImpact, Resolution) read this from their inboxes.

Reads (from its own inbox, before first analysis)
  NOTIFICATION  reason="low_data_quality"  from AlarmRetrievalAgent
  Logged as a state warning; reduces expected confidence.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.a2a_protocol import (
    A2ABus, AgentMessage, MessageType,
    make_message, make_response,
)
from backend.models.schemas import RetrievedIncident, RootCauseAnalysis, TelecomIncident
from backend.services.root_cause_engine import RootCauseAnalysisEngine

logger = logging.getLogger(__name__)

AGENT_NAME          = "RootCauseAgent"
LOW_CONF_THRESHOLD  = 0.50


class RootCauseAnalysisAgent:

    def __init__(self, root_cause_engine: RootCauseAnalysisEngine) -> None:
        self.root_cause_engine = root_cause_engine
        self._bus: Optional[A2ABus] = None

    # ── A2A wiring ────────────────────────────────────────────────────────────

    def set_bus(self, bus: A2ABus) -> None:
        """Register on the bus (no incoming handler — RCA initiates requests)."""
        self._bus = bus
        bus.register(AGENT_NAME)

    # ── Main process ──────────────────────────────────────────────────────────

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            retrieved = state.get("retrieved_incidents", [])
            query     = state.get("query", "")

            logger.info(
                f"[{AGENT_NAME}] Analyzing root cause from {len(retrieved)} incidents"
            )

            # ── Read inbox: data-quality notification from AlarmRetrievalAgent ─
            if self._bus:
                for msg in self._bus.receive(AGENT_NAME):
                    if (
                        msg.msg_type == MessageType.NOTIFICATION
                        and msg.payload.get("reason") == "low_data_quality"
                    ):
                        logger.warning(
                            f"[{AGENT_NAME}] Data-quality warning: "
                            f"{msg.payload.get('detail', '')}"
                        )
                        state.setdefault("warnings", []).append({
                            "source": msg.from_agent,
                            "detail": msg.payload.get("detail", ""),
                        })

            if not retrieved:
                state["root_cause_analysis"] = self._default_analysis()
                state["messages"].append({
                    "role": "agent",
                    "content": f"{AGENT_NAME}: No incidents to analyze",
                    "agent": AGENT_NAME,
                })
                return state

            # ── First-pass analysis ───────────────────────────────────────────
            root_cause, tok = self._run_analysis(query, retrieved)
            state.setdefault("_token_usage", {})["rca"] = tok
            confidence = root_cause.confidence_score

            # ── A2A: request expanded retrieval when confidence is low ─────────
            if (
                confidence < LOW_CONF_THRESHOLD
                and not state.get("re_retrieval_done")
                and self._bus
            ):
                logger.info(
                    f"[{AGENT_NAME}] Confidence {confidence:.0%} < {LOW_CONF_THRESHOLD:.0%} "
                    "— sending REQUEST to AlarmRetrievalAgent for expanded context"
                )
                expanded = self._request_expansion(query, state, confidence)
                if expanded:
                    state["retrieved_incidents"] = expanded
                    state["re_retrieval_done"]   = True
                    root_cause, tok2 = self._run_analysis(query, expanded)
                    state["_token_usage"]["rca"] = tok2   # overwrite with re-analysis stats
                    logger.info(
                        f"[{AGENT_NAME}] Re-analysis confidence: "
                        f"{root_cause.confidence_score:.0%}"
                    )

            state["root_cause_analysis"] = root_cause

            # ── A2A: broadcast result to downstream agents ────────────────────
            if self._bus:
                self._bus.send(make_message(
                    AGENT_NAME, "broadcast", MessageType.NOTIFICATION,
                    {
                        "reason":           "rca_complete",
                        "primary_cause":    root_cause.primary_cause,
                        "confidence_score": round(root_cause.confidence_score, 3),
                        "re_retrieval":     state.get("re_retrieval_done", False),
                        "pattern_detected": root_cause.pattern_detected,
                    },
                ))

            state["messages"].append({
                "role": "agent",
                "content": (
                    f"{AGENT_NAME}: Primary cause = {root_cause.primary_cause} "
                    f"(conf={root_cause.confidence_score:.0%})"
                ),
                "agent": AGENT_NAME,
            })
            logger.info(
                f"[{AGENT_NAME}] ✓ {root_cause.primary_cause} "
                f"({root_cause.confidence_score:.0%})"
            )
            return state

        except Exception as exc:
            logger.error(f"[{AGENT_NAME}] ✗ {exc}")
            state["root_cause_analysis"] = self._default_analysis()
            state["messages"].append({
                "role": "agent",
                "content": f"{AGENT_NAME}: Error — {exc}",
                "agent": AGENT_NAME,
            })
            return state

    # ── A2A: send expansion REQUEST and process RESPONSE ─────────────────────

    def _request_expansion(
        self,
        query:      str,
        state:      Dict[str, Any],
        confidence: float,
    ) -> Optional[List[RetrievedIncident]]:
        """
        Send REQUEST to AlarmRetrievalAgent via bus.
        The bus dispatches synchronously; read the RESPONSE from our own inbox.
        Returns a new list of RetrievedIncident objects, or None on failure.
        """
        request = make_message(
            AGENT_NAME, "AlarmRetrievalAgent", MessageType.REQUEST,
            {
                "action": "expand_retrieval",
                "query":  query,
                "top_k":  8,
                "reason": (
                    f"Confidence {confidence:.0%} below threshold "
                    f"({LOW_CONF_THRESHOLD:.0%}) — need broader incident context"
                ),
                "filters": {
                    "region_filter":      state.get("region_filter"),
                    "severity_filter":    state.get("severity_filter"),
                    "technology_filter":  state.get("technology_filter"),
                    "vendor_filter":      state.get("vendor_filter"),
                },
            },
        )
        corr_id = request.correlation_id
        self._bus.send(request)

        # The bus synchronously dispatches to AlarmRetrievalAgent's handler and
        # places the RESPONSE in our inbox — read it now.
        for msg in self._bus.receive(AGENT_NAME):
            if (
                msg.msg_type == MessageType.RESPONSE
                and msg.correlation_id == corr_id
            ):
                if msg.payload.get("status") == "ok":
                    raw = msg.payload.get("raw_results", [])
                    n   = msg.payload.get("incidents_found", 0)
                    logger.info(
                        f"[{AGENT_NAME}] Expansion RESPONSE received: "
                        f"{n} incidents"
                    )
                    if raw:
                        return self._hydrate_incidents(raw, query)
                else:
                    logger.warning(
                        f"[{AGENT_NAME}] Expansion failed: "
                        f"{msg.payload.get('error', 'unknown')}"
                    )
        return None

    # ── Analysis helpers ──────────────────────────────────────────────────────

    def _run_analysis(
        self,
        query:     str,
        incidents: List[RetrievedIncident],
    ) -> Tuple[RootCauseAnalysis, Dict[str, Any]]:
        """Run RCA engine and return (pydantic model, token_usage dict)."""
        similar_incs = [inc.incident.dict() for inc in incidents[1:]]
        primary_meta = incidents[0].incident.dict()
        analysis = self.root_cause_engine.analyze_root_cause(
            incident_description=query,
            similar_incidents=similar_incs,
            metadata=primary_meta,
        )
        token_usage = analysis.pop("_token_usage", {})
        return RootCauseAnalysis(
            primary_cause=      analysis.get("primary_cause", "Unknown"),
            secondary_causes=   analysis.get("secondary_causes", []),
            confidence_score=   float(analysis.get("confidence_score", 0.5)),
            analysis_reasoning= analysis.get("analysis_reasoning", ""),
            similar_incidents=  [inc.incident.alarm_id for inc in incidents[:3]],
            pattern_detected=   ", ".join(analysis.get("pattern_evidence", [])),
            probable_causes=    analysis.get("probable_causes", []),
            evidence_items=     analysis.get("evidence_items", []),
        ), token_usage

    @staticmethod
    def _hydrate_incidents(
        raw_results: List,  # list-of-lists: [doc_id, score, metadata, text]
        query:       str,
    ) -> List[RetrievedIncident]:
        """Re-hydrate expansion response payload into RetrievedIncident objects."""
        incidents = []
        for item in raw_results:
            try:
                _doc_id, score, metadata, _text = item[0], item[1], item[2], item[3]
                inc = TelecomIncident(
                    alarm_id=            metadata.get("alarm_id", ""),
                    incident_description=query,
                    network_region=      metadata.get("network_region", ""),
                    technology_type=     metadata.get("technology_type", ""),
                    severity=            metadata.get("severity", ""),
                    outage_duration=     int(metadata.get("outage_duration", 0)),
                    device_vendor=       metadata.get("device_vendor", ""),
                    resolution_notes=    "",
                    timestamp=           datetime.now(),
                    service_impact=      metadata.get("service_impact", ""),
                )
                incidents.append(RetrievedIncident(
                    incident=        inc,
                    similarity_score=float(score),
                    bm25_score=      0.0,
                    vector_score=    0.0,
                    hybrid_score=    float(score),
                ))
            except Exception as exc:
                logger.warning(f"[{AGENT_NAME}] Hydration skipped: {exc}")
        return incidents

    @staticmethod
    def _default_analysis() -> RootCauseAnalysis:
        return RootCauseAnalysis(
            primary_cause=      "No historical evidence available",
            secondary_causes=   [],
            confidence_score=   0.0,
            analysis_reasoning= "No similar incidents were found in the database for this query.",
            similar_incidents=  [],
            pattern_detected=   "",
            probable_causes=    [],
            evidence_items=     [],
        )
