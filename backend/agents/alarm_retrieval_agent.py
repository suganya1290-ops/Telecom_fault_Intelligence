"""
AlarmRetrievalAgent — retrieves relevant historical incidents via the RAG pipeline.

A2A participation
-----------------
Sends
  ESCALATION broadcast  — when any retrieved incident has severity == "critical"
  NOTIFICATION          — data-quality warning to RootCauseAgent when descriptions are empty

Handles (via registered bus handler)
  REQUEST  action="expand_retrieval"  — from RootCauseAgent when its confidence is low;
                                        re-runs retrieval with a larger top_k and returns
                                        the expanded result set as a RESPONSE message.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from backend.agents.a2a_protocol import (
    A2ABus, AgentMessage, MessageType,
    make_message, make_response,
)
from backend.models.schemas import RetrievedIncident, TelecomIncident

logger = logging.getLogger(__name__)

AGENT_NAME = "AlarmRetrievalAgent"


class AlarmRetrievalAgent:

    def __init__(self, rag_pipeline: Any) -> None:
        self.rag_pipeline = rag_pipeline
        self._bus: Optional[A2ABus] = None

    # ── A2A wiring ────────────────────────────────────────────────────────────

    def set_bus(self, bus: A2ABus) -> None:
        """Attach this agent to a workflow bus and register its request handler."""
        self._bus = bus
        bus.register(AGENT_NAME, handler=self._handle_request)

    # ── Main process ──────────────────────────────────────────────────────────

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            query = state.get("query", "")
            top_k = state.get("top_k_override") or 5

            logger.info(f"[{AGENT_NAME}] Retrieving incidents (top_k={top_k})")

            retrieved = self.rag_pipeline.retrieve_incidents(
                query=query,
                top_k=top_k,
                region_filter=   state.get("region_filter"),
                severity_filter= state.get("severity_filter"),
                technology_filter=state.get("technology_filter"),
                vendor_filter=   state.get("vendor_filter"),
            )

            incidents = self._to_retrieved_incidents(retrieved, query)
            state["retrieved_incidents"] = incidents

            # ── A2A: broadcast ESCALATION if critical severity found ───────────
            critical_ids = [
                inc.incident.alarm_id
                for inc in incidents
                if str(inc.incident.severity).lower() == "critical"
            ]
            if critical_ids and self._bus:
                self._bus.send(make_message(
                    AGENT_NAME, "broadcast", MessageType.ESCALATION,
                    {
                        "reason":            "critical_severity_detected",
                        "critical_alarm_ids": critical_ids,
                        "total_retrieved":   len(incidents),
                        "query":             query,
                        "action_required":   "Activate deep-analysis mode — expand retrieval scope",
                    },
                ))
                logger.info(f"[{AGENT_NAME}] ESCALATION broadcast: {len(critical_ids)} critical alarm(s)")

            # ── A2A: notify RootCauseAgent of data-quality issue if needed ─────
            if incidents and self._bus:
                empty_desc = all(
                    not str(inc.incident.incident_description or "").strip()
                    for inc in incidents
                )
                if empty_desc:
                    self._bus.send(make_message(
                        AGENT_NAME, "RootCauseAgent", MessageType.NOTIFICATION,
                        {
                            "reason": "low_data_quality",
                            "detail": "Retrieved incidents have no description data — RCA confidence will be reduced",
                            "count":  len(incidents),
                        },
                    ))

            state["messages"].append({
                "role":    "agent",
                "content": f"{AGENT_NAME}: Retrieved {len(incidents)} incidents (top_k={top_k})",
                "agent":   AGENT_NAME,
            })
            logger.info(f"[{AGENT_NAME}] ✓ {len(incidents)} incidents retrieved")
            return state

        except Exception as exc:
            logger.error(f"[{AGENT_NAME}] ✗ {exc}")
            state["messages"].append({
                "role": "agent", "content": f"{AGENT_NAME}: Retrieval error — {exc}",
                "agent": AGENT_NAME,
            })
            return state

    # ── A2A handler (registered with bus) ────────────────────────────────────

    def _handle_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Synchronous dispatcher for incoming REQUEST messages.
        Currently handles action="expand_retrieval" from RootCauseAgent.
        """
        action = message.payload.get("action", "")
        logger.info(
            f"[{AGENT_NAME}] ← {message.msg_type} from {message.from_agent}: action={action!r}"
        )

        if action == "expand_retrieval":
            return self._handle_expand_retrieval(message)

        # Unknown action — return error response so the caller isn't left hanging
        logger.warning(f"[{AGENT_NAME}] Unknown request action: {action!r}")
        return make_response(
            AGENT_NAME, message.from_agent,
            {"status": "error", "error": f"Unknown action: {action}"},
            message.correlation_id,
        )

    def _handle_expand_retrieval(self, message: AgentMessage) -> AgentMessage:
        """
        Re-run retrieval with an expanded top_k and return results as a RESPONSE.

        The response payload carries:
          status          — "ok" | "error"
          incidents_found — integer count
          incidents       — list of serialisable incident summaries
          raw_results     — list-of-lists for RootCauseAgent to re-hydrate into
                            RetrievedIncident objects (truncated text, fully JSON-safe)
        """
        query   = message.payload.get("query", "")
        top_k   = message.payload.get("top_k", 8)
        reason  = message.payload.get("reason", "")
        filters = message.payload.get("filters", {})

        logger.info(
            f"[{AGENT_NAME}] Expanding retrieval: top_k={top_k}, reason={reason!r}"
        )

        try:
            retrieved = self.rag_pipeline.retrieve_incidents(
                query=            query,
                top_k=            top_k,
                region_filter=    filters.get("region_filter"),
                severity_filter=  filters.get("severity_filter"),
                technology_filter=filters.get("technology_filter"),
                vendor_filter=    filters.get("vendor_filter"),
            )

            # Build a serialisable summary for the API log
            incidents_summary = [
                {
                    "doc_id":      r[0],
                    "score":       round(float(r[1]), 4),
                    "alarm_id":    r[2].get("alarm_id", ""),
                    "region":      r[2].get("network_region", ""),
                    "severity":    r[2].get("severity", ""),
                    "technology":  r[2].get("technology_type", ""),
                    "vendor":      r[2].get("device_vendor", ""),
                }
                for r in retrieved
            ]

            # raw_results for RootCauseAgent to re-hydrate — text truncated to 300 chars
            raw_results = [
                [r[0], float(r[1]), r[2], (r[3] or "")[:300]]
                for r in retrieved
            ]

            logger.info(f"[{AGENT_NAME}] Expansion complete: {len(retrieved)} incidents found")
            return make_response(
                AGENT_NAME, message.from_agent,
                {
                    "status":           "ok",
                    "incidents_found":  len(retrieved),
                    "top_k_requested":  top_k,
                    "incidents_summary": incidents_summary,
                    "raw_results":      raw_results,
                },
                message.correlation_id,
            )

        except Exception as exc:
            logger.error(f"[{AGENT_NAME}] Expansion failed: {exc}")
            return make_response(
                AGENT_NAME, message.from_agent,
                {"status": "error", "error": str(exc), "incidents_found": 0},
                message.correlation_id,
            )

    # ── Conversion helpers ────────────────────────────────────────────────────

    def _to_retrieved_incidents(
        self,
        raw: List,          # List[Tuple[str, float, Dict, str]] from RAG pipeline
        query: str,
    ) -> List[RetrievedIncident]:
        incidents = []
        for _doc_id, hybrid_score, metadata, _ in raw:
            try:
                incident = TelecomIncident(
                    alarm_id=            metadata.get("alarm_id", ""),
                    incident_description=query,
                    network_region=      metadata.get("network_region", ""),
                    technology_type=     metadata.get("technology_type", ""),
                    severity=            metadata.get("severity", ""),
                    outage_duration=     int(metadata.get("outage_duration", 0)),
                    device_vendor=       metadata.get("device_vendor", ""),
                    resolution_notes=    "",
                    timestamp=           self._parse_ts(metadata.get("timestamp", "")),
                    service_impact=      metadata.get("service_impact", ""),
                )
                incidents.append(RetrievedIncident(
                    incident=        incident,
                    similarity_score=float(hybrid_score),
                    bm25_score=      0.0,
                    vector_score=    0.0,
                    hybrid_score=    float(hybrid_score),
                ))
            except Exception as exc:
                logger.warning(f"[{AGENT_NAME}] Skipping incident: {exc}")
        return incidents

    @staticmethod
    def _parse_ts(ts: str) -> datetime:
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return datetime.now()
