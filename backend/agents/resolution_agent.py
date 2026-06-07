"""
ResolutionRecommendationAgent — generates ranked remediation actions.

A2A participation
-----------------
Reads (from inbox before processing)
  ESCALATION  broadcast               — from AlarmRetrievalAgent (critical severity)
  NOTIFICATION reason="cascade_analysis"    — from Orchestrator
  NOTIFICATION reason="impact_complete"     — from ServiceImpactAgent
                                              carries priority_level + cascade_active
  NOTIFICATION reason="rca_complete"        — from RootCauseAgent

Behaviour changes driven by A2A intel
  • ESCALATION or cascade_analysis → prepends "URGENT (cascade detected)" to
    the escalation recommendation string.
  • impact_complete priority == "critical" | "high" → prepends the confirmed
    priority level (from ServiceImpactAgent) to the escalation recommendation.
  • rca_complete → logs confirmed cause for traceability.

Sends (after generating recommendations)
  NOTIFICATION broadcast  reason="resolution_complete"
  Signals end-of-workflow to Orchestrator and any future agents.
"""

import logging
from typing import Any, Dict, Optional

from backend.agents.a2a_protocol import (
    A2ABus, AgentMessage, MessageType,
    make_message,
)
from backend.models.schemas import ResolutionRecommendation
from backend.services.resolution_engine import ResolutionRecommendationEngine

logger = logging.getLogger(__name__)

AGENT_NAME = "ResolutionAgent"


class ResolutionRecommendationAgent:

    def __init__(self, resolution_engine: ResolutionRecommendationEngine) -> None:
        self.resolution_engine = resolution_engine
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

            logger.info(f"[{AGENT_NAME}] Generating resolution recommendations…")

            # ── Drain inbox ───────────────────────────────────────────────────
            cascade_active  = False
            impact_priority = None
            rca_cause       = None

            if self._bus:
                for msg in self._bus.receive(AGENT_NAME):
                    mtype  = msg.msg_type
                    reason = msg.payload.get("reason", "")

                    if mtype == MessageType.ESCALATION:
                        cascade_active = True
                        logger.info(
                            f"[{AGENT_NAME}] ← ESCALATION from {msg.from_agent}: "
                            f"{reason}"
                        )

                    elif mtype == MessageType.NOTIFICATION:
                        if reason == "cascade_analysis":
                            cascade_active = True
                            logger.info(
                                f"[{AGENT_NAME}] ← CASCADE notification "
                                f"(strength={msg.payload.get('correlation_strength', 0):.0%})"
                            )
                        elif reason == "impact_complete":
                            impact_priority = msg.payload.get("priority_level")
                            if msg.payload.get("cascade_active"):
                                cascade_active = True
                            logger.info(
                                f"[{AGENT_NAME}] ← impact_complete: "
                                f"priority={impact_priority}, "
                                f"cascade={cascade_active}"
                            )
                        elif reason == "rca_complete":
                            rca_cause = msg.payload.get("primary_cause")
                            logger.info(
                                f"[{AGENT_NAME}] ← rca_complete: cause={rca_cause!r}"
                            )
                        elif reason == "start_resolution":
                            if msg.payload.get("cascade"):
                                cascade_active = True

            if state.get("cascade_analysis"):
                cascade_active = True

            if not retrieved or not root_cause_analysis:
                state["resolution_recommendations"] = self._default_recommendations()
                state["messages"].append({
                    "role": "agent",
                    "content": f"{AGENT_NAME}: Insufficient data for recommendations",
                    "agent": AGENT_NAME,
                })
                return state

            incident          = retrieved[0].incident.dict()
            root_cause        = root_cause_analysis.dict()
            similar_incidents = [inc.incident.dict() for inc in retrieved[1:]]

            recommendations = self.resolution_engine.generate_recommendations(
                incident=incident,
                root_cause_analysis=root_cause,
                similar_incidents=similar_incidents,
            )

            # Capture token usage before reading individual keys
            tok_usage = recommendations.pop("_token_usage", {})
            state.setdefault("_token_usage", {})["resolution"] = tok_usage

            # ── A2A-informed escalation prefix ────────────────────────────────
            escalation_rec = recommendations.get("escalation_recommendation", "")
            if cascade_active:
                escalation_rec = "URGENT (cascade detected) — " + escalation_rec
            if impact_priority in ("critical", "high"):
                escalation_rec = (
                    f"[{impact_priority.upper()} priority confirmed by ServiceImpactAgent] "
                    + escalation_rec
                )

            resolution = ResolutionRecommendation(
                recommended_actions=      recommendations.get("recommended_actions", []),
                historical_fixes=         recommendations.get("historical_fixes", []),
                escalation_recommendation=escalation_rec,
                confidence_score=         float(recommendations.get("confidence_score", 0.5)),
                estimated_resolution_time=int(recommendations.get("estimated_resolution_time", 30)),
            )

            # ── A2A: signal end of workflow ───────────────────────────────────
            if self._bus:
                self._bus.send(make_message(
                    AGENT_NAME, "broadcast", MessageType.NOTIFICATION,
                    {
                        "reason":         "resolution_complete",
                        "actions_count":  len(resolution.recommended_actions),
                        "confidence":     round(resolution.confidence_score, 3),
                        "cascade_active": cascade_active,
                        "rca_cause":      rca_cause,
                    },
                ))

            state["resolution_recommendations"] = resolution
            state["messages"].append({
                "role": "agent",
                "content": (
                    f"{AGENT_NAME}: {len(resolution.recommended_actions)} actions generated "
                    f"(cascade={cascade_active})"
                ),
                "agent": AGENT_NAME,
            })
            logger.info(
                f"[{AGENT_NAME}] ✓ {len(resolution.recommended_actions)} actions, "
                f"cascade={cascade_active}"
            )
            return state

        except Exception as exc:
            logger.error(f"[{AGENT_NAME}] ✗ {exc}")
            state["resolution_recommendations"] = self._default_recommendations()
            state["messages"].append({
                "role": "agent",
                "content": f"{AGENT_NAME}: Error — {exc}",
                "agent": AGENT_NAME,
            })
            return state

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _default_recommendations() -> ResolutionRecommendation:
        return ResolutionRecommendation(
            recommended_actions=[
                "Check physical connectivity and power status of affected network elements.",
                "Review recent configuration changes (last 24 h) and roll back if suspect.",
                "Inspect alarm logs on the NMS/EMS for correlated or preceding fault events.",
                "Verify backhaul and transport links to isolate the fault domain.",
                "Run self-test or built-in diagnostics on the affected node/card.",
                "Coordinate with the vendor TAC if fault persists after standard checks.",
                "Open a P2 ticket and escalate to L2/L3 NOC if unresolved within SLA.",
            ],
            historical_fixes=[],
            escalation_recommendation="Escalate to senior NOC engineer — no historical precedent found",
            confidence_score=0.0,
            estimated_resolution_time=60,
        )
