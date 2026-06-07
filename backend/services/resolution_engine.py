import logging
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import json

from backend.utils.token_optimizer import TokenOptimizer

logger = logging.getLogger(__name__)


class ResolutionRecommendationEngine:
    """Generates troubleshooting recommendations for telecom incidents."""
    
    def __init__(self, client: OpenAI, model: str = "gpt-3.5-turbo"):
        """Initialize resolution engine.
        
        Args:
            client: OpenAI client
            model: Model name
        """
        self.client = client
        self.model = model
        self.resolution_steps = self._initialize_steps()
        # 2500 context budget: 3500 total − 1200 completion − ~700 template overhead
        self._tok = TokenOptimizer(max_context_tokens=2500)
    
    def _initialize_steps(self) -> Dict[str, List[str]]:
        """Initialize resolution steps for different scenarios.
        
        Returns:
            Dictionary of resolution steps
        """
        return {
            "power_failure": [
                "Verify power supply voltage specifications",
                "Check power supply continuity with multimeter",
                "Inspect for blown fuses or circuit breaker trips",
                "Power cycle equipment (30 second reset)",
                "Monitor backup battery status",
                "Check UPS configuration if applicable"
            ],
            "rf_interference": [
                "Measure RF power levels across frequency bands",
                "Scan for interfering signals using spectrum analyzer",
                "Verify antenna alignment and installation",
                "Check for nearby transmission sources",
                "Adjust transmission power if applicable",
                "Document interference source coordinates"
            ],
            "software_bug": [
                "Review recent software patches and changelog",
                "Check controller memory and CPU utilization",
                "Clear cache and temporary files",
                "Perform graceful restart of affected module",
                "Monitor system logs for error messages",
                "Contact vendor support with error codes"
            ],
            "network_congestion": [
                "Monitor real-time traffic load across links",
                "Identify peak usage times and patterns",
                "Implement traffic engineering reroute if available",
                "Check load balancer configuration",
                "Consider capacity upgrade planning",
                "Review QoS policies for optimization"
            ],
            "fiber_issue": [
                "Perform OTDR test to locate break or reflection point",
                "Check splice points with visual inspection",
                "Measure optical power levels",
                "Verify signal quality at both ends",
                "Check for macro bending or kinks",
                "Schedule repair/replacement if cut detected"
            ],
            "hardware_failure": [
                "Log hardware error messages from system",
                "Check LED indicators on affected module",
                "Verify hardware specifications in system",
                "Remove and reseat module connections",
                "Test with replacement hardware if available",
                "Request hardware RMA if defective"
            ],
            "configuration_error": [
                "Export current configuration for backup",
                "Review recent configuration changes",
                "Compare with known good configuration",
                "Validate parameter values against specs",
                "Restore previous known-good configuration",
                "Document changes and validate performance"
            ]
        }
    
    def generate_recommendations(self,
                               incident: Dict[str, Any],
                               root_cause_analysis: Dict[str, Any],
                               similar_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate resolution recommendations.

        Args:
            incident: Incident data
            root_cause_analysis: Root cause analysis result
            similar_incidents: List of similar incidents

        Returns:
            Resolution recommendations (includes _token_usage key)
        """
        try:
            known_steps = self._extract_known_steps(root_cause_analysis)
            llm_recommendations = self._llm_generate_recommendations(
                incident, root_cause_analysis, similar_incidents
            )

            # Extract token usage before combining
            token_usage = llm_recommendations.pop("_token_usage", {})

            historical_fixes = self._extract_historical_fixes(similar_incidents)
            result = self._combine_recommendations(
                known_steps, llm_recommendations, historical_fixes, root_cause_analysis
            )
            result["_token_usage"] = token_usage
            return result

        except Exception as e:
            logger.error(f"✗ Error generating recommendations: {str(e)}")
            return self._default_recommendations()
    
    def _extract_known_steps(self, root_cause: Dict[str, Any]) -> List[str]:
        """Extract known resolution steps based on root cause.
        
        Args:
            root_cause: Root cause analysis
            
        Returns:
            List of resolution steps
        """
        primary_cause = root_cause.get("primary_cause", "").lower()
        steps = []
        
        # Match cause to resolution steps
        for cause_type, cause_steps in self.resolution_steps.items():
            if cause_type.replace("_", " ") in primary_cause or \
               any(word in primary_cause for word in cause_type.split("_")):
                steps.extend(cause_steps)
                break
        
        # Default steps if no match
        if not steps:
            steps = [
                "Review incident logs and timestamps",
                "Identify affected network elements",
                "Check system health and resource utilization",
                "Verify connectivity between components",
                "Monitor recovery progress",
                "Document all findings"
            ]
        
        return steps
    
    def _llm_generate_recommendations(self,
                                    incident: Dict[str, Any],
                                    root_cause: Dict[str, Any],
                                    similar_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use LLM to generate detailed recommendations. Returns dict with _token_usage key."""
        try:
            # Token-budgeted resolution context (replaces fixed [:150] char slice)
            similar_resolutions, ctx_stats = self._build_similar_resolutions(similar_incidents)

            prompt = f"""You are a senior telecom network troubleshooting expert. Based on this incident and root cause, provide specific troubleshooting steps.

INCIDENT:
- Region: {incident.get('network_region', 'unknown')}
- Technology: {incident.get('technology_type', 'unknown')}
- Vendor: {incident.get('device_vendor', 'unknown')}
- Severity: {incident.get('severity', 'unknown')}
- Duration: {incident.get('outage_duration', 'unknown')} minutes
- Service Impact: {incident.get('service_impact', 'unknown')}

ROOT CAUSE:
{root_cause.get('primary_cause', 'Unknown')}

SIMILAR INCIDENT RESOLUTIONS:
{similar_resolutions}

Provide JSON with:
- recommended_actions: List of specific troubleshooting steps (7-10 steps)
- escalation_recommendation: When and to whom to escalate
- estimated_resolution_time: Time to resolve in minutes
- confidence_score: Your confidence in these recommendations 0-1
- critical_cautions: Any critical warnings or cautions
"""
            prompt_tokens = self._tok.count_tokens(prompt)
            logger.info(
                f"[Resolution] prompt_tokens={prompt_tokens} | "
                f"context={ctx_stats['context_tokens']}t "
                f"(raw={ctx_stats['raw_tokens']}t, "
                f"saved={ctx_stats['savings_pct']:.1f}%)"
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=1200
            )

            response_text = response.choices[0].message.content

            # Parse JSON
            try:
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    result = json.loads(json_str)
                    result["_token_usage"] = {**ctx_stats, "prompt_tokens": prompt_tokens}
                    return result
            except Exception:
                pass

            return {
                "response": response_text,
                "_token_usage": {**ctx_stats, "prompt_tokens": prompt_tokens},
            }

        except Exception as e:
            logger.error(f"✗ Error in LLM recommendations: {str(e)}")
            return {}
    
    def _extract_historical_fixes(self, similar_incidents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract historical fixes from similar incidents.
        
        Args:
            similar_incidents: Similar incidents
            
        Returns:
            List of historical fixes
        """
        fixes = []
        
        for incident in similar_incidents[:3]:
            if "resolution_notes" in incident:
                fixes.append({
                    "alarm_id": incident.get("alarm_id", ""),
                    "resolution": incident.get("resolution_notes", ""),
                    "outage_duration": incident.get("outage_duration", 0),
                    "timestamp": incident.get("timestamp", "")
                })
        
        return fixes
    
    def _build_similar_resolutions(
        self, similar_incidents: List[Dict[str, Any]]
    ) -> Tuple[str, Dict[str, Any]]:
        """Build token-budgeted resolution context. Returns (context_str, token_stats).

        Replaces the old [:150] character slice with per-field token caps,
        then applies a global budget to fit within the LLM context window.
        """
        if not similar_incidents:
            empty = "No historical resolutions available."
            return empty, {
                "incidents_in": 0,
                "raw_tokens": 0,
                "context_tokens": self._tok.count_tokens(empty),
                "savings_pct": 0.0,
            }

        blocks: List[Tuple[str, float]] = []
        raw_total = 0

        for i, inc in enumerate(similar_incidents[:2]):
            alarm_id = str(inc.get("alarm_id", f"INC-{i+1}"))
            res      = str(inc.get("resolution_notes", "N/A"))

            raw_total += self._tok.count_tokens(f"{alarm_id} {res}")
            res_trunc  = self._tok.truncate_to_tokens(res, 150)

            block = f"{i+1}. Alarm {alarm_id}:\n   {res_trunc}"
            blocks.append((block, 1.0 - i * 0.2))

        context        = self._tok.build_context(blocks, reserved_tokens=700, separator="\n")
        context_tokens = self._tok.count_tokens(context)
        savings        = (raw_total - context_tokens) / max(raw_total, 1) * 100

        return context, {
            "incidents_in":   len(similar_incidents[:2]),
            "raw_tokens":     raw_total,
            "context_tokens": context_tokens,
            "savings_pct":    round(savings, 1),
        }
    
    def _combine_recommendations(self,
                               known_steps: List[str],
                               llm_recommendations: Dict[str, Any],
                               historical_fixes: List[Dict[str, Any]],
                               root_cause: Dict[str, Any]) -> Dict[str, Any]:
        """Combine all recommendations.
        
        Args:
            known_steps: Known resolution steps
            llm_recommendations: LLM-generated recommendations
            historical_fixes: Historical fixes
            root_cause: Root cause analysis
            
        Returns:
            Combined recommendations
        """
        # Get actions from LLM or use known steps
        recommended_actions = llm_recommendations.get("recommended_actions", known_steps)
        if isinstance(recommended_actions, str):
            recommended_actions = [recommended_actions]
        
        if not recommended_actions:
            recommended_actions = known_steps
        
        # Confidence
        confidence = llm_recommendations.get("confidence_score", 0.7)
        
        # Estimated time
        estimated_time = llm_recommendations.get("estimated_resolution_time", 30)
        try:
            estimated_time = int(estimated_time)
        except:
            estimated_time = 30
        
        return {
            "recommended_actions": recommended_actions[:10],  # Limit to 10 actions
            "historical_fixes": historical_fixes,
            "escalation_recommendation": llm_recommendations.get(
                "escalation_recommendation",
                "Escalate to senior engineering team if not resolved within 30 minutes"
            ),
            "confidence_score": min(float(confidence) if confidence else 0.7, 1.0),
            "estimated_resolution_time": estimated_time,
            "critical_cautions": llm_recommendations.get("critical_cautions", []),
            "cause_confidence": root_cause.get("confidence_score", 0.5)
        }
    
    def _default_recommendations(self) -> Dict[str, Any]:
        """Return default recommendations.
        
        Returns:
            Default recommendations
        """
        return {
            "recommended_actions": [
                "Check system logs for error messages",
                "Verify component connectivity",
                "Monitor resource utilization",
                "Contact vendor support with incident details"
            ],
            "historical_fixes": [],
            "escalation_recommendation": "Escalate to senior engineering team",
            "confidence_score": 0.4,
            "estimated_resolution_time": 60,
            "critical_cautions": [],
            "cause_confidence": 0.3
        }
