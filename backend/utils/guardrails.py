import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Prompt injection and jailbreak patterns
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+)?",
    r"pretend\s+(you\s+are|to\s+be)",
    r"do\s+not\s+follow",
    r"override\s+(your\s+)?(instructions|rules|guidelines)",
    r"<\s*system\s*>",
    r"\{\{.*\}\}",
    r"jailbreak",
    r"\bdan\s+mode\b",
    r"prompt\s+injection",
    r"system\s*:\s*['\"]",
    r"forget\s+(all\s+)?previous",
    r"new\s+instructions?\s*:",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

MAX_QUERY_LENGTH = 2000
MIN_QUERY_LENGTH = 3


def validate_query(query: str) -> Tuple[bool, str]:
    """Return (is_valid, error_message). Empty error means valid."""
    if not query or not query.strip():
        return False, "Query cannot be empty"

    stripped = query.strip()

    if len(stripped) < MIN_QUERY_LENGTH:
        return False, f"Query too short (minimum {MIN_QUERY_LENGTH} characters)"

    if len(stripped) > MAX_QUERY_LENGTH:
        return False, f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters"

    for pattern in _COMPILED:
        if pattern.search(stripped):
            logger.warning(f"Guardrail blocked query containing disallowed pattern: {pattern.pattern}")
            return False, "Query contains disallowed content"

    return True, ""


def sanitize_query(query: str) -> str:
    """Strip, collapse whitespace, and remove non-printable characters."""
    sanitized = query.strip()
    # Remove non-printable characters except common whitespace
    sanitized = re.sub(r'[^\x20-\x7E\n\t]', '', sanitized)
    # Collapse runs of whitespace
    sanitized = re.sub(r'[ \t]+', ' ', sanitized)
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    return sanitized
