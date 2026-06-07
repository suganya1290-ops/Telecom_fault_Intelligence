import logging
from typing import Any, Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# Fallback character-based estimate when tiktoken is unavailable
_CHARS_PER_TOKEN = 4


def _get_encoding(model: str):
    try:
        import tiktoken
        return tiktoken.encoding_for_model(model)
    except Exception:
        try:
            import tiktoken
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None


class TokenOptimizer:
    """Counts and manages tokens to stay within LLM context limits."""

    def __init__(self, model: str = "gpt-3.5-turbo", max_context_tokens: int = 3000):
        self.model = model
        self.max_context_tokens = max_context_tokens
        self._enc = _get_encoding(model)

    def count_tokens(self, text: str) -> int:
        if self._enc is not None:
            return len(self._enc.encode(text))
        return max(1, len(text) // _CHARS_PER_TOKEN)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text so it fits within max_tokens."""
        if self._enc is not None:
            tokens = self._enc.encode(text)
            if len(tokens) <= max_tokens:
                return text
            return self._enc.decode(tokens[:max_tokens])
        # Character fallback
        max_chars = max_tokens * _CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def build_context(
        self,
        documents: List[Tuple[str, float]],
        reserved_tokens: int = 500,
        separator: str = "\n---\n",
    ) -> str:
        """
        Select and concatenate documents within the token budget.

        Args:
            documents: List of (text, relevance_score) sorted by descending score.
            reserved_tokens: Tokens reserved for the prompt template and completion.
            separator: String placed between documents.

        Returns:
            Concatenated context string that fits the budget.
        """
        budget = self.max_context_tokens - reserved_tokens
        sep_tokens = self.count_tokens(separator)
        parts: List[str] = []
        used = 0

        for text, _ in sorted(documents, key=lambda x: x[1], reverse=True):
            doc_tokens = self.count_tokens(text)
            if used + doc_tokens + sep_tokens <= budget:
                parts.append(text)
                used += doc_tokens + sep_tokens
            elif budget - used > 100:
                # Partial inclusion: truncate to remaining budget
                remaining = budget - used - sep_tokens
                truncated = self.truncate_to_tokens(text, remaining)
                parts.append(truncated)
                break

        result = separator.join(parts)
        logger.debug(
            f"Token optimizer: {len(documents)} docs → {len(parts)} kept, "
            f"~{used} tokens used of {budget} budget"
        )
        return result

    def fits_in_context(self, text: str, extra_tokens: int = 0) -> bool:
        return self.count_tokens(text) + extra_tokens <= self.max_context_tokens

    def token_stats(self, texts: List[str]) -> dict:
        counts = [self.count_tokens(t) for t in texts]
        return {
            "total_tokens": sum(counts),
            "avg_tokens": round(sum(counts) / len(counts), 1) if counts else 0,
            "max_tokens": max(counts) if counts else 0,
            "min_tokens": min(counts) if counts else 0,
            "document_count": len(counts),
        }

    def build_incident_context(
        self,
        incidents:          List[Dict[str, Any]],
        description_field:  str = "incident_description",
        resolution_field:   str = "resolution_notes",
        max_desc_tokens:    int = 200,
        max_res_tokens:     int = 100,
        reserved_tokens:    int = 500,
        separator:          str = "\n---\n",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a token-budget-aware context string from incident dicts.

        Per-field caps (max_desc_tokens / max_res_tokens) prevent any single
        field from consuming the whole budget.  The global budget
        (max_context_tokens - reserved_tokens) is then enforced via
        build_context(), which may further trim or drop lower-ranked incidents.

        Returns:
            (context_str, stats) where stats contains:
              incidents_in, raw_tokens, context_tokens, savings_pct
        """
        if not incidents:
            empty = "No similar incidents found."
            return empty, {
                "incidents_in":   0,
                "raw_tokens":     0,
                "context_tokens": self.count_tokens(empty),
                "savings_pct":    0.0,
            }

        blocks:    List[Tuple[str, float]] = []
        raw_total: int = 0

        for i, inc in enumerate(incidents):
            alarm_id = str(inc.get("alarm_id", f"INC-{i+1}"))
            desc     = str(inc.get(description_field, "N/A"))
            res      = str(inc.get(resolution_field,  "N/A"))

            # Raw token count (no truncation)
            raw_total += self.count_tokens(f"{alarm_id} {desc} {res}")

            # Per-field caps: smarter than a fixed character slice
            desc_trunc = self.truncate_to_tokens(desc, max_desc_tokens)
            res_trunc  = self.truncate_to_tokens(res,  max_res_tokens)

            block = (
                f"{i+1}. Alarm {alarm_id}:\n"
                f"   Description: {desc_trunc}\n"
                f"   Resolution:  {res_trunc}"
            )
            # Earlier (higher-ranked) incidents get budget priority
            score = 1.0 - i * 0.1
            blocks.append((block, score))

        # Enforce global token budget; may drop or truncate lower-ranked blocks
        context        = self.build_context(blocks, reserved_tokens=reserved_tokens, separator=separator)
        context_tokens = self.count_tokens(context)

        savings = (raw_total - context_tokens) / max(raw_total, 1) * 100
        return context, {
            "incidents_in":   len(incidents),
            "raw_tokens":     raw_total,
            "context_tokens": context_tokens,
            "savings_pct":    round(savings, 1),
        }
