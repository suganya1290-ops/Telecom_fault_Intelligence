"""
Agent-to-Agent (A2A) communication protocol.

Components
----------
AgentMessage   — typed envelope for every inter-agent message
MessageType    — REQUEST | RESPONSE | ESCALATION | NOTIFICATION | BROADCAST | ACK
MessageStatus  — sent | delivered | processed | failed
A2ABus         — central routing bus with synchronous request-dispatch
make_message   — factory helper (generates ids/timestamps automatically)
make_response  — convenience wrapper that sets msg_type=RESPONSE and copies correlation_id

Routing rules
-------------
• BROADCAST or to_agent=="broadcast" → delivered to every mailbox except the sender
• REQUEST / ESCALATION directed at an agent with a registered handler
  → bus dispatches synchronously; response is placed in the sender's inbox
• RESPONSE / NOTIFICATION → placed in the target mailbox only

All messages are appended to an immutable history list that is returned at the
end of the workflow as `a2a_messages` in the API response.
"""

import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Protocol enums ────────────────────────────────────────────────────────────

class MessageType(str, Enum):
    REQUEST      = "REQUEST"       # one agent asks another to perform work
    RESPONSE     = "RESPONSE"      # reply to a REQUEST (same correlation_id)
    ESCALATION   = "ESCALATION"    # urgent situation, usually broadcast
    NOTIFICATION = "NOTIFICATION"  # one-way informational push
    BROADCAST    = "BROADCAST"     # delivered to every registered agent
    ACK          = "ACK"           # lightweight acknowledgement


class MessageStatus(str, Enum):
    SENT      = "sent"
    DELIVERED = "delivered"
    PROCESSED = "processed"
    FAILED    = "failed"


# ── Message envelope ──────────────────────────────────────────────────────────

@dataclass
class AgentMessage:
    message_id:     str
    from_agent:     str
    to_agent:       str              # agent name, or "broadcast"
    msg_type:       MessageType
    payload:        Dict[str, Any]
    timestamp:      str
    correlation_id: str              # links request ↔ response pairs
    status:         str = MessageStatus.SENT

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe dict (tuples in payload become lists via recursion)."""
        def _safe(v: Any) -> Any:
            if isinstance(v, tuple):
                return [_safe(x) for x in v]
            if isinstance(v, list):
                return [_safe(x) for x in v]
            if isinstance(v, dict):
                return {k: _safe(val) for k, val in v.items()}
            return v

        # Use .value to get the plain string ("REQUEST" not "MessageType.REQUEST")
        return {
            "message_id":     self.message_id,
            "from_agent":     self.from_agent,
            "to_agent":       self.to_agent,
            "msg_type":       self.msg_type.value,
            "payload":        _safe(self.payload),
            "timestamp":      self.timestamp,
            "correlation_id": self.correlation_id,
            "status":         self.status.value if hasattr(self.status, "value") else self.status,
        }


# ── Central message bus ───────────────────────────────────────────────────────

class A2ABus:
    """
    Synchronous agent-to-agent message bus.

    Each workflow creates one bus instance.  Agents register with optional
    handler callbacks; the bus dispatches REQUEST/ESCALATION messages
    synchronously to registered handlers and places the response in the
    sender's inbox.  All messages are recorded in an immutable history list.
    """

    def __init__(self) -> None:
        # per-agent inbox queues
        self._mailboxes: Dict[str, deque]  = {}
        # optional synchronous dispatch handlers  (agent_name → callable)
        self._handlers:  Dict[str, Callable[[AgentMessage], Optional[AgentMessage]]] = {}
        # full ordered message log
        self._history:   List[AgentMessage] = []

    # ── Registration ──────────────────────────────────────────────────────────

    def register(
        self,
        agent_name: str,
        handler: Optional[Callable[[AgentMessage], Optional[AgentMessage]]] = None,
    ) -> None:
        """
        Register an agent on the bus.

        Parameters
        ----------
        agent_name : str
            Unique agent identifier.
        handler : callable, optional
            If provided, called synchronously whenever a REQUEST or ESCALATION
            is addressed to this agent.  The callable receives the incoming
            AgentMessage and must return an AgentMessage (response) or None.
        """
        self._mailboxes.setdefault(agent_name, deque())
        if handler:
            self._handlers[agent_name] = handler
        logger.info(
            f"[A2ABus] Registered: {agent_name}"
            + (" (with handler)" if handler else "")
        )

    # ── Send ─────────────────────────────────────────────────────────────────

    def send(self, message: AgentMessage) -> str:
        """
        Route a message and return its message_id.

        Side-effects
        ------------
        • Appends message to history.
        • For BROADCAST: delivers to every inbox except the sender.
        • For REQUEST/ESCALATION: if the target has a registered handler,
          dispatches synchronously and places the response in the sender's inbox.
        • For all other types: places message in the target's inbox.
        """
        message.status = MessageStatus.DELIVERED
        self._history.append(message)

        logger.info(
            f"[A2ABus] {str(message.msg_type):12s} | "
            f"{message.from_agent} → {message.to_agent} | "
            f"id={message.message_id[:8]} | "
            f"payload_keys={list(message.payload.keys())}"
        )

        # ── Broadcast ─────────────────────────────────────────────────────────
        is_broadcast = (
            message.to_agent == "broadcast"
            or message.msg_type == MessageType.BROADCAST
        )
        if is_broadcast:
            for name, box in self._mailboxes.items():
                if name != message.from_agent:
                    box.append(message)
            message.status = MessageStatus.PROCESSED
            return message.message_id

        # ── Unicast delivery ──────────────────────────────────────────────────
        target_box = self._mailboxes.get(message.to_agent)
        if target_box is not None:
            target_box.append(message)

        # ── Synchronous dispatch for REQUEST / ESCALATION ─────────────────────
        if message.msg_type in (MessageType.REQUEST, MessageType.ESCALATION):
            handler = self._handlers.get(message.to_agent)
            if handler:
                try:
                    response = handler(message)
                    if response is not None:
                        response.status = MessageStatus.DELIVERED
                        self._history.append(response)
                        # Return the response to the sender's inbox
                        self._mailboxes.setdefault(message.from_agent, deque()).append(response)
                        message.status = MessageStatus.PROCESSED
                        logger.info(
                            f"[A2ABus] RESPONSE dispatched: "
                            f"{response.from_agent} → {response.to_agent} | "
                            f"corr={response.correlation_id[:8]}"
                        )
                except Exception as exc:
                    logger.error(f"[A2ABus] Handler error ({message.to_agent}): {exc}")
                    message.status = MessageStatus.FAILED

        return message.message_id

    # ── Receive ───────────────────────────────────────────────────────────────

    def receive(self, agent_name: str) -> List[AgentMessage]:
        """Drain and return all messages from an agent's inbox."""
        box  = self._mailboxes.get(agent_name, deque())
        msgs = list(box)
        box.clear()
        for m in msgs:
            m.status = MessageStatus.PROCESSED
        return msgs

    def peek(self, agent_name: str) -> List[AgentMessage]:
        """Return inbox contents without draining."""
        return list(self._mailboxes.get(agent_name, deque()))

    # ── History & stats ───────────────────────────────────────────────────────

    def get_history(self) -> List[Dict[str, Any]]:
        """Return all messages as JSON-safe dicts."""
        return [m.to_dict() for m in self._history]

    def stats(self) -> Dict[str, Any]:
        by_type:  Dict[str, int] = {}
        by_agent: Dict[str, int] = {}
        for m in self._history:
            key = m.msg_type.value   # plain string e.g. "REQUEST" not "MessageType.REQUEST"
            by_type[key]           = by_type.get(key, 0) + 1
            by_agent[m.from_agent] = by_agent.get(m.from_agent, 0) + 1
        return {
            "total_messages":    len(self._history),
            "by_type":           by_type,
            "by_agent":          by_agent,
            "registered_agents": list(self._mailboxes.keys()),
        }


# ── Factory helpers ───────────────────────────────────────────────────────────

def make_message(
    from_agent:     str,
    to_agent:       str,
    msg_type:       MessageType,
    payload:        Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> AgentMessage:
    """Create a new AgentMessage with auto-generated id and timestamp."""
    return AgentMessage(
        message_id=     str(uuid.uuid4()),
        from_agent=     from_agent,
        to_agent=       to_agent,
        msg_type=       msg_type,
        payload=        payload,
        timestamp=      datetime.now().isoformat(),
        correlation_id= correlation_id or str(uuid.uuid4()),
    )


def make_response(
    from_agent:     str,
    to_agent:       str,
    payload:        Dict[str, Any],
    correlation_id: str,
) -> AgentMessage:
    """Create a RESPONSE message that shares the originating request's correlation_id."""
    return make_message(from_agent, to_agent, MessageType.RESPONSE, payload, correlation_id)
