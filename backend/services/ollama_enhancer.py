"""
OllamaRCAEnhancer — adds Llama 3.2 LLM reasoning on top of BM25 results.

No embeddings or vector store required. Flow per query:
  1. FallbackAnalyzer does BM25 retrieval  (always, instant)
  2. OllamaRCAEnhancer calls llama3.2 with the BM25 context  (if Ollama up)
  3. If Ollama is unreachable or times out → BM25 result returned as-is

Startup is instant — no batch embedding, no ChromaDB initialisation.
"""
import logging
from typing import Dict

from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert telecom network operations engineer specialising in fault "
    "diagnosis and root cause analysis. Be concise, technical, and actionable."
)


class OllamaRCAEnhancer:
    """Enhances BM25 fault analysis with Ollama LLM reasoning."""

    def __init__(self, client: OpenAI, model: str = "llama3.2"):
        self.client = client
        self.model  = model
        self._available: bool | None = None

    # ── Availability check (lazy, cached) ────────────────────────────────────

    def check_available(self) -> bool:
        try:
            self.client.models.list()
            self._available = True
            logger.info(f"✓ Ollama reachable — model: {self.model}")
        except Exception as exc:
            self._available = False
            logger.warning(f"⚠ Ollama not reachable: {exc} — will use BM25-only fallback")
        return self._available

    def is_available(self) -> bool:
        if self._available is None:
            self.check_available()
        return bool(self._available)

    # ── Main entry point ─────────────────────────────────────────────────────

    def enhance(self, query: str, bm25_result: Dict) -> Dict:
        """
        Add LLM reasoning to a BM25 analysis result.
        Returns the original dict unchanged if Ollama is unavailable.
        """
        if not self.is_available():
            return bm25_result

        rca       = bm25_result.get("root_cause_analysis", {})
        incidents = bm25_result.get("retrieved_incidents", [])[:3]

        # Build compact incident context
        inc_lines = []
        for inc in incidents:
            blob = inc.get("incident", inc)
            desc = blob.get("incident_description", "")[:180]
            sev  = blob.get("severity", "")
            reg  = blob.get("network_region", "")
            inc_lines.append(f"- [{sev.upper()}] {reg}: {desc}")
        incident_context = "\n".join(inc_lines) if inc_lines else "No matching incidents found."

        prompt = (
            f"Fault: {query}\n"
            f"Cause: {rca.get('primary_cause','Unknown')}\n"
            f"Evidence: {rca.get('analysis_reasoning','')[:150]}\n"
            f"Incidents:\n{incident_context}\n\n"
            "In 2 sentences: confirm/refine root cause. In 1 sentence: immediate action."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=150,
                temperature=0.2,
                timeout=45,
            )
            llm_text = response.choices[0].message.content.strip()

            # Inject LLM reasoning into a copy of the result
            enhanced = dict(bm25_result)
            enhanced["root_cause_analysis"] = dict(rca)
            enhanced["root_cause_analysis"]["llm_reasoning"]    = llm_text
            enhanced["root_cause_analysis"]["analysis_method"]  = (
                f"BM25 retrieval + {self.model} LLM reasoning"
            )
            enhanced["ai_enhanced"]  = True
            enhanced["llm_model"]    = self.model
            enhanced["fallback_mode"] = False
            logger.info(f"✓ Ollama enhanced RCA for query: {query[:60]}")
            return enhanced

        except Exception as exc:
            logger.warning(f"⚠ Ollama enhancement failed ({exc}) — returning BM25 result")
            self._available = None  # reset so next request re-checks
            return bm25_result
