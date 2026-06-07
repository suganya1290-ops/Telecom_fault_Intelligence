"""
ServiceImpactAgent — quantifies customer and business impact of a fault.

A2A participation
-----------------
Reads (from inbox before processing)
  ESCALATION  broadcast          — from AlarmRetrievalAgent (critical severity)
  NOTIFICATION reason="cascade_analysis"   — from Orchestrator (high correlation)
  NOTIFICATION reason="rca_complete"       — from RootCauseAgent (carries confidence)

Behaviour changes driven by A2A intel
  • Any ESCALATION or cascade_analysis NOTIFICATION → enables cascade mode,
    which promotes a "medium" priority to "high" and sets cascade_flagged=True.
  • rca_complete NOTIFICATION → logs the confirmed root cause for traceability.

Sends (after analysis)
  NOTIFICATION broadcast  reason="impact_complete"
  Carries priority_level, revenue_loss, and cascade_active flag for ResolutionAgent.
"""

import logging
from typing import Any, Dict, Optional

from backend.agents.a2a_protocol import (
    A2ABus, AgentMessage, MessageType,
    make_message,
)
from backend.models.schemas import ServiceImpactAnalysis
from backend.services.service_impact_engine import ServiceImpactEngine

logger = logging.getLogger(__name__)

AGENT_NAME = "ServiceImpactAgent"


class ServiceImpactAgent:

    def __init__(self, service_impact_engine: ServiceImpactEngine) -> None:
        self.service_impact_engine = service_impact_engine
        self._bus: Optional[A2ABus] = None

    # ── A2A wiring ────────────────────────────────────────────────────────────

    def set_bus(self, bus: A2ABus) -> None:
        self._bus = bus
        bus.register(AGENT_NAME)

    # ── Main process ──────────────────────────────────────────────────────────

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            retrieved           = state.get("retrieved_incidents", [])
            root_cause_analysis = state.get("root_cause_analysis")

            logger.info(f"[{AGENT_NAME}] Analyzing service impact…")

            # ── Drain inbox: react to escalation / cascade notifications ───────
            cascade_active  = False
            rca_cause       = None
            rca_confidence  = None

            if self._bus:
                for msg in self._bus.receive(AGENT_NAME):
                    mtype  = msg.msg_type
                    reason = msg.payload.get("reason", "")

                    if mtype == MessageType.ESCALATION:
                        cascade_active = True
                        logger.info(
                            f"[{AGENT_NAME}] ← ESCALATION from {msg.from_agent}: "
                            f"{msg.payload.get('reason', '')}"
                        )

                    elif mtype == MessageType.NOTIFICATION:
                        if reason == "cascade_analysis":
                            cascade_active = True
                            logger.info(
                                f"[{AGENT_NAME}] ← CASCADE notification "
                                f"(strength={msg.payload.get('correlation_strength', 0):.0%})"
                            )
                        elif reason == "rca_complete":
                            rca_cause      = msg.payload.get("primary_cause")
                            rca_confidence = msg.payload.get("confidence_score")
                            logger.info(
                                f"[{AGENT_NAME}] ← RCA notification: "
                                f"cause={rca_cause!r}, conf={rca_confidence}"
                            )
                        elif reason == "start_impact_analysis":
                            # Orchestrator start signal — pick up cascade flag from it
                            if msg.payload.get("cascade"):
                                cascade_active = True

            # Also honour the state flag set by the orchestrator
            if state.get("cascade_analysis"):
                cascade_active = True

            if not retrieved:
                state["service_impact_analysis"] = self._default_impact()
                state["messages"].append({
                    "role": "agent",
                    "content": f"{AGENT_NAME}: No incidents to analyze",
                    "agent": AGENT_NAME,
                })
                return state

            incident   = retrieved[0].incident.dict()
            root_cause = root_cause_analysis.dict() if root_cause_analysis else {}

            if cascade_active:
                # Signal to the engine that cascade context is active
                incident["_cascade_analysis"] = True
                logger.info(f"[{AGENT_NAME}] Running with cascade analysis enabled")

            impact_data = self.service_impact_engine.analyze_impact(
                incident=incident,
                root_cause_analysis=root_cause,
            )

            # Capture token usage before reading individual keys
            tok_usage = impact_data.pop("_token_usage", {})
            state.setdefault("_token_usage", {})["impact"] = tok_usage

            # Cascade promotion: medium → high if cascade was detected
            priority = impact_data.get("priority_level", "medium")
            if cascade_active and priority == "medium":
                priority = "high"
                impact_data["cascade_flagged"] = True
                logger.info(f"[{AGENT_NAME}] Priority promoted medium→high (cascade)")

            impact = ServiceImpactAnalysis(
                customer_impact=       impact_data.get("customer_impact", "Unknown"),
                network_impact=        impact_data.get("network_impact", "Unknown"),
                business_impact=       impact_data.get("business_impact", "Unknown"),
                affected_services=     impact_data.get("affected_services", []),
                priority_level=        priority,
                estimated_revenue_loss=float(impact_data.get("estimated_revenue_loss", 0.0)),
            )

            # ── A2A: notify ResolutionAgent and Orchestrator ──────────────────
            if self._bus:
                self._bus.send(make_message(
                    AGENT_NAME, "broadcast", MessageType.NOTIFICATION,
                    {
                        "reason":         "impact_complete",
                        "priority_level": impact.priority_level,
                        "revenue_loss":   impact.estimated_revenue_loss,
                        "cascade_active": cascade_active,
                        "rca_cause":      rca_cause,
                    },
                ))

            state["service_impact_analysis"] = impact
            state["messages"].append({
                "role": "agent",
                "content": (
                    f"{AGENT_NAME}: {impact.priority_level.upper()} priority, "
                    f"cascade={cascade_active}"
                ),
                "agent": AGENT_NAME,
            })
            logger.info(
                f"[{AGENT_NAME}] ✓ {impact.priority_level} priority, "
                f"cascade={cascade_active}"
            )
            return state

        except Exception as exc:
            logger.error(f"[{AGENT_NAME}] ✗ {exc}")
            state["service_impact_analysis"] = self._default_impact()
            state["messages"].append({
                "role": "agent",
                "content": f"{AGENT_NAME}: Error — {exc}",
                "agent": AGENT_NAME,
            })
            return state

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _default_impact() -> ServiceImpactAnalysis:
        return ServiceImpactAnalysis(
            customer_impact=       "No Historical Evidence Available",
            network_impact=        "N/A",
            business_impact=       "N/A — no matching historical incidents",
            affected_services=     [],
            priority_level=        "unknown",
            estimated_revenue_loss=0.0,
        )
