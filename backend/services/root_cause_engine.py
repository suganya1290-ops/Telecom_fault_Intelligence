import logging
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import json

from backend.utils.token_optimizer import TokenOptimizer

logger = logging.getLogger(__name__)


class RootCauseAnalysisEngine:
    """Analyzes root causes of telecom incidents using LLM and pattern matching."""
    
    def __init__(self, client: OpenAI, model: str = "gpt-3.5-turbo"):
        """Initialize root cause analysis engine.
        
        Args:
            client: OpenAI client
            model: Model name
        """
        self.client = client
        self.model = model
        self.cause_patterns = self._initialize_patterns()
        # 2500 context budget: 3500 total − 1000 completion − ~800 template overhead
        self._tok = TokenOptimizer(max_context_tokens=2500)
    
    def _initialize_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize cause patterns for different scenarios.
        
        Returns:
            Dictionary of cause patterns
        """
        return {
            "5G_rf_interference": {
                "keywords": ["mmwave", "frequency", "interference", "5g"],
                "causes": ["Radio frequency interference in millimeter wave bands"],
                "probability": 0.8
            },
            "power_failure": {
                "keywords": ["power", "supply", "battery", "outage", "offline"],
                "causes": ["Power supply failure", "Generator malfunction"],
                "probability": 0.85
            },
            "software_issue": {
                "keywords": ["software", "bug", "crash", "error", "update"],
                "causes": ["Software bug in RAN controller", "Configuration error"],
                "probability": 0.75
            },
            "network_congestion": {
                "keywords": ["congestion", "capacity", "peak", "timeout", "latency"],
                "causes": ["Network capacity exhaustion", "Backhaul congestion"],
                "probability": 0.8
            },
            "fiber_issue": {
                "keywords": ["fiber", "optical", "splice", "cut", "degradation"],
                "causes": ["Fiber cut", "Optical signal degradation", "Splice failure"],
                "probability": 0.9
            },
            "hardware_failure": {
                "keywords": ["hardware", "module", "transceiver", "processor", "failure"],
                "causes": ["Hardware component failure", "Module malfunction"],
                "probability": 0.85
            },
            "configuration_error": {
                "keywords": ["configuration", "parameter", "setting", "misconfiguration"],
                "causes": ["Network misconfiguration", "Parameter error"],
                "probability": 0.75
            },
            "vendor_specific_issue": {
                "keywords": ["vendor", "equipment", "proprietary", "incompatibility"],
                "causes": ["Vendor-specific issue", "Equipment incompatibility"],
                "probability": 0.7
            },
        }
    
    def analyze_root_cause(self,
                          incident_description: str,
                          similar_incidents: List[Dict[str, Any]],
                          metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze root cause of incident.

        Args:
            incident_description: Description of incident
            similar_incidents: List of similar historical incidents
            metadata: Incident metadata

        Returns:
            Root cause analysis result (includes _token_usage key)
        """
        try:
            # Pattern matching
            pattern_matches = self._match_patterns(incident_description, metadata)

            # LLM-based analysis (returns dict with _token_usage)
            llm_analysis = self._llm_analyze(incident_description, similar_incidents, pattern_matches)

            # Extract token usage before combining (pydantic won't accept extra keys)
            token_usage = llm_analysis.pop("_token_usage", {})

            # Combine analyses
            result = self._combine_analyses(pattern_matches, llm_analysis, metadata)
            result["_token_usage"] = token_usage
            return result

        except Exception as e:
            logger.error(f"✗ Error analyzing root cause: {str(e)}")
            return self._default_analysis()
    
    def _match_patterns(self, description: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Match incident against known patterns.
        
        Args:
            description: Incident description
            metadata: Incident metadata
            
        Returns:
            List of matched patterns
        """
        matches = []
        description_lower = description.lower()
        
        for pattern_name, pattern in self.cause_patterns.items():
            match_count = sum(1 for keyword in pattern["keywords"] if keyword in description_lower)
            
            if match_count > 0:
                match_score = min(match_count / len(pattern["keywords"]), 1.0)
                matches.append({
                    "pattern": pattern_name,
                    "causes": pattern["causes"],
                    "match_score": match_score,
                    "base_probability": pattern["probability"]
                })
        
        return sorted(matches, key=lambda x: x["match_score"], reverse=True)
    
    def _llm_analyze(self,
                    description: str,
                    similar_incidents: List[Dict[str, Any]],
                    pattern_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use LLM for detailed analysis. Returns dict with _token_usage key."""
        try:
            # Build token-budgeted context (replaces fixed char slicing)
            similar_context, ctx_stats = self._build_incident_context(similar_incidents)
            patterns_context = self._build_patterns_context(pattern_matches)

            prompt = f"""You are a telecom network fault analysis expert. Analyze the following incident and provide root cause analysis.

CURRENT INCIDENT:
{description}

SIMILAR HISTORICAL INCIDENTS:
{similar_context}

DETECTED PATTERNS:
{patterns_context}

Provide a JSON response with:
- primary_cause: Most likely root cause
- secondary_causes: List of contributing factors
- confidence_score: Your confidence 0-1
- reasoning: Detailed reasoning
"""
            prompt_tokens = self._tok.count_tokens(prompt)
            logger.info(
                f"[RCA] prompt_tokens={prompt_tokens} | "
                f"context={ctx_stats['context_tokens']}t "
                f"(raw={ctx_stats['raw_tokens']}t, "
                f"saved={ctx_stats['savings_pct']:.1f}%)"
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=1000
            )

            analysis_text = response.choices[0].message.content

            # Try to parse as JSON
            try:
                json_start = analysis_text.find('{')
                json_end = analysis_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = analysis_text[json_start:json_end]
                    result = json.loads(json_str)
                    result["_token_usage"] = {**ctx_stats, "prompt_tokens": prompt_tokens}
                    return result
            except Exception:
                pass

            # Fallback parsing
            return {
                "primary_cause": "Unable to determine primary cause",
                "secondary_causes": [],
                "confidence_score": 0.3,
                "reasoning": analysis_text,
                "_token_usage": {**ctx_stats, "prompt_tokens": prompt_tokens},
            }

        except Exception as e:
            logger.error(f"✗ Error in LLM analysis: {str(e)}")
            return {}
    
    def _build_incident_context(
        self, similar_incidents: List[Dict[str, Any]]
    ) -> Tuple[str, Dict[str, Any]]:
        """Build token-budgeted context from similar incidents.

        Replaces the old fixed character-slice approach ([:200] / [:150]) with
        per-field token caps enforced by TokenOptimizer, then applies a global
        budget so the whole block fits within the LLM context window.

        Returns:
            (context_str, stats) — stats keys: incidents_in, raw_tokens,
            context_tokens, savings_pct
        """
        return self._tok.build_incident_context(
            similar_incidents[:3],
            description_field="incident_description",
            resolution_field="resolution_notes",
            max_desc_tokens=200,
            max_res_tokens=100,
            reserved_tokens=600,
        )
    
    def _build_patterns_context(self, matches: List[Dict[str, Any]]) -> str:
        """Build context from pattern matches.
        
        Args:
            matches: List of matched patterns
            
        Returns:
            Formatted context string
        """
        if not matches:
            return "No patterns matched."
        
        context = ""
        for i, match in enumerate(matches[:3]):
            context += f"\n{i+1}. Pattern: {match['pattern']} (Match score: {match['match_score']:.0%})"
            context += f"\n   Possible causes: {', '.join(match['causes'][:2])}"
        
        return context
    
    def _combine_analyses(self,
                         patterns: List[Dict[str, Any]],
                         llm_result: Dict[str, Any],
                         metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Combine pattern and LLM analyses."""
        # Primary cause — prefer LLM, fall back to top pattern
        primary_cause = llm_result.get("primary_cause", "")
        if not primary_cause and patterns:
            primary_cause = patterns[0]["causes"][0]

        # Blended confidence
        llm_confidence     = llm_result.get("confidence_score", 0.5)
        pattern_confidence = patterns[0]["base_probability"] if patterns else 0.4
        combined_confidence = (llm_confidence + pattern_confidence) / 2

        # ── Probable causes ranked list ───────────────────────────────────────
        probable_causes: List[Dict[str, Any]] = []

        # 1. LLM primary cause
        if primary_cause and primary_cause not in ("Unknown cause", "Unable to determine primary cause"):
            probable_causes.append({
                "cause":       primary_cause,
                "probability": round(min(llm_confidence, 1.0), 3),
                "source":      "llm_analysis",
            })

        # 2. LLM secondary causes (reduced confidence)
        for sc in llm_result.get("secondary_causes", [])[:3]:
            if sc and not any(c["cause"].lower() == sc.lower() for c in probable_causes):
                probable_causes.append({
                    "cause":       sc,
                    "probability": round(min(llm_confidence * 0.55, 0.85), 3),
                    "source":      "llm_secondary",
                })

        # 3. Pattern matches not already listed
        for p in patterns[:4]:
            cause_str = p["causes"][0] if p["causes"] else p["pattern"].replace("_", " ")
            if not any(c["cause"].lower() == cause_str.lower() for c in probable_causes):
                prob = round(p["match_score"] * p["base_probability"], 3)
                if prob > 0.10:
                    probable_causes.append({
                        "cause":       cause_str,
                        "probability": prob,
                        "source":      "pattern_match",
                    })

        probable_causes = sorted(probable_causes, key=lambda x: x["probability"], reverse=True)[:5]

        # ── Evidence items (human-readable bullets) ───────────────────────────
        evidence_items: List[str] = []
        tech   = metadata.get("technology_type", "")
        region = metadata.get("network_region", "")
        sev    = metadata.get("severity", "")
        vendor = metadata.get("device_vendor", "")

        if sev:
            evidence_items.append(f"Incident severity: {sev.upper()} — increases diagnostic weight")
        if tech:
            evidence_items.append(f"Technology stack: {tech} infrastructure")
        if region:
            evidence_items.append(f"Network region: {region}")
        if vendor:
            evidence_items.append(f"Equipment vendor: {vendor}")
        for p in patterns[:2]:
            kw_pct = round(p["match_score"] * 100)
            evidence_items.append(
                f"Pattern '{p['pattern'].replace('_', ' ')}' matched — {kw_pct}% keyword coverage"
            )
        # First meaningful sentence from LLM reasoning
        reasoning = llm_result.get("reasoning", "")
        if reasoning and len(reasoning) > 40:
            sentences = [s.strip() for s in reasoning.replace(";", ".").split(".") if len(s.strip()) > 25]
            if sentences:
                evidence_items.append(f"LLM insight: {sentences[0][:180]}")

        return {
            "primary_cause":    primary_cause or "Unknown cause",
            "secondary_causes": llm_result.get("secondary_causes", []),
            "confidence_score": min(combined_confidence, 1.0),
            "analysis_reasoning": llm_result.get("reasoning", ""),
            "pattern_evidence": [p["pattern"] for p in patterns[:2]],
            "probable_causes":  probable_causes,
            "evidence_items":   evidence_items,
            "technology_type":  metadata.get("technology_type", ""),
            "vendor":           metadata.get("device_vendor", ""),
            "region":           metadata.get("network_region", ""),
            "severity":         metadata.get("severity", ""),
        }
    
    def _default_analysis(self) -> Dict[str, Any]:
        """Return default analysis when error occurs.
        
        Returns:
            Default analysis result
        """
        return {
            "primary_cause": "Analysis in progress",
            "secondary_causes": [],
            "confidence_score": 0.3,
            "analysis_reasoning": "Unable to perform detailed analysis at this time",
            "pattern_evidence": [],
            "technology_type": "",
            "vendor": "",
            "region": "",
            "severity": ""
        }
