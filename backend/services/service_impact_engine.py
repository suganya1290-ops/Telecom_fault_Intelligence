import logging
from typing import Dict, Any, List
from openai import OpenAI
import json

from backend.utils.token_optimizer import TokenOptimizer

logger = logging.getLogger(__name__)


class ServiceImpactEngine:
    """Analyzes service impact and business effects of incidents."""
    
    def __init__(self, client: OpenAI, model: str = "gpt-3.5-turbo"):
        """Initialize service impact engine.
        
        Args:
            client: OpenAI client
            model: Model name
        """
        self.client = client
        self.model = model
        self.impact_multipliers = self._initialize_multipliers()
        # 2500 context budget: 3500 total − 1000 completion − ~800 template overhead
        self._tok = TokenOptimizer(max_context_tokens=2500)
    
    def _initialize_multipliers(self) -> Dict[str, Dict[str, float]]:
        """Initialize impact multipliers for different scenarios.
        
        Returns:
            Dictionary of impact multipliers
        """
        return {
            "severity_multiplier": {
                "critical": 1.0,
                "high": 0.7,
                "medium": 0.4,
                "low": 0.1,
                "info": 0.0
            },
            "region_multiplier": {
                "North India": 0.4,
                "South India": 0.3,
                "East India": 0.2,
                "West India": 0.35,
                "Central India": 0.25
            },
            "service_impact_multiplier": {
                "Voice call failures": 1.0,
                "Emergency call drops": 1.0,
                "Data session timeouts": 0.8,
                "SMS delivery delays": 0.6,
                "Video streaming buffering": 0.5,
                "Roaming service unavailable": 0.7,
                "M2M connectivity loss": 0.6,
                "IoT data transmission failures": 0.5
            },
            "technology_multiplier": {
                "5G": 0.6,
                "4G": 0.7,
                "LTE": 0.6,
                "GSM": 0.5,
                "Fiber": 0.8,
                "Microwave": 0.4,
                "Satellite": 0.3
            }
        }
    
    def analyze_impact(self,
                      incident: Dict[str, Any],
                      root_cause_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze service impact of incident.

        Args:
            incident: Incident data
            root_cause_analysis: Root cause analysis result

        Returns:
            Service impact analysis result (includes _token_usage key)
        """
        try:
            impact_metrics = self._calculate_impact_metrics(incident)
            llm_analysis   = self._llm_analyze_impact(incident, root_cause_analysis, impact_metrics)

            # Extract token usage before combining
            token_usage = llm_analysis.pop("_token_usage", {})

            result = self._combine_impact_analyses(impact_metrics, llm_analysis, incident)
            result["_token_usage"] = token_usage
            return result

        except Exception as e:
            logger.error(f"✗ Error analyzing service impact: {str(e)}")
            return self._default_impact()
    
    def _calculate_impact_metrics(self, incident: Dict[str, Any]) -> Dict[str, float]:
        """Calculate quantitative impact metrics.
        
        Args:
            incident: Incident data
            
        Returns:
            Impact metrics dictionary
        """
        multipliers = self.impact_multipliers
        
        # Severity impact (0-1)
        severity = incident.get("severity", "medium")
        severity_impact = multipliers["severity_multiplier"].get(severity, 0.5)
        
        # Region impact
        region = incident.get("network_region", "")
        region_impact = multipliers["region_multiplier"].get(region, 0.3)
        
        # Service impact
        service = incident.get("service_impact", "")
        service_impact_score = multipliers["service_impact_multiplier"].get(service, 0.5)
        
        # Technology impact
        technology = incident.get("technology_type", "")
        tech_impact = multipliers["technology_multiplier"].get(technology, 0.5)
        
        # Outage duration impact
        outage_duration = float(incident.get("outage_duration", 0))
        duration_impact = min(outage_duration / 60, 1.0)  # Normalize to 60 minutes
        
        # Combined impact score
        combined_impact = (
            severity_impact * 0.4 +
            service_impact_score * 0.3 +
            duration_impact * 0.2 +
            tech_impact * 0.1
        )
        
        return {
            "severity_impact": severity_impact,
            "region_impact": region_impact,
            "service_impact_score": service_impact_score,
            "tech_impact": tech_impact,
            "duration_impact": duration_impact,
            "combined_impact": min(combined_impact, 1.0)
        }
    
    def _llm_analyze_impact(self,
                           incident: Dict[str, Any],
                           root_cause: Dict[str, Any],
                           metrics: Dict[str, float]) -> Dict[str, Any]:
        """Use LLM for detailed impact analysis. Returns dict with _token_usage key."""
        try:
            prompt = f"""You are a telecom business impact analyst. Analyze the business impact of this incident.

INCIDENT DETAILS:
- Severity: {incident.get('severity', 'unknown')}
- Region: {incident.get('network_region', 'unknown')}
- Technology: {incident.get('technology_type', 'unknown')}
- Outage Duration: {incident.get('outage_duration', 'unknown')} minutes
- Service Impact: {incident.get('service_impact', 'unknown')}
- Device Vendor: {incident.get('device_vendor', 'unknown')}

ROOT CAUSE:
{root_cause.get('primary_cause', 'Unknown')}

IMPACT METRICS:
- Combined Impact Score: {metrics.get('combined_impact', 0):.1%}
- Service Impact: {metrics.get('service_impact_score', 0):.1%}
- Duration Impact: {metrics.get('duration_impact', 0):.1%}

Provide a JSON response with:
- customer_impact: Specific customer impact description
- network_impact: Network infrastructure impact
- business_impact: Business impact summary
- affected_services: List of affected services
- priority_level: Priority (critical/high/medium/low)
- estimated_revenue_loss: Estimated revenue loss in USD
- recommendation: Action recommendation
"""
            prompt_tokens = self._tok.count_tokens(prompt)
            logger.info(f"[Impact] prompt_tokens={prompt_tokens}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=1000
            )

            analysis_text = response.choices[0].message.content

            # Parse JSON
            try:
                json_start = analysis_text.find('{')
                json_end = analysis_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = analysis_text[json_start:json_end]
                    result = json.loads(json_str)
                    result["_token_usage"] = {"prompt_tokens": prompt_tokens}
                    return result
            except Exception:
                pass

            return {
                "analysis": analysis_text,
                "_token_usage": {"prompt_tokens": prompt_tokens},
            }

        except Exception as e:
            logger.error(f"✗ Error in LLM impact analysis: {str(e)}")
            return {}
    
    def _combine_impact_analyses(self,
                                metrics: Dict[str, float],
                                llm_analysis: Dict[str, Any],
                                incident: Dict[str, Any]) -> Dict[str, Any]:
        """Combine quantitative and LLM analyses.
        
        Args:
            metrics: Impact metrics
            llm_analysis: LLM analysis result
            incident: Incident data
            
        Returns:
            Combined impact analysis
        """
        # Estimate revenue loss
        base_revenue_loss = self._estimate_revenue_loss(incident, metrics)
        
        return {
            "customer_impact": llm_analysis.get("customer_impact", "Direct customer service degradation"),
            "network_impact": llm_analysis.get("network_impact", "Network infrastructure affected"),
            "business_impact": llm_analysis.get("business_impact", "Moderate business impact"),
            "affected_services": llm_analysis.get("affected_services", [incident.get("service_impact", "Unknown")]),
            "priority_level": self._determine_priority(metrics, incident),
            "estimated_revenue_loss": llm_analysis.get("estimated_revenue_loss", base_revenue_loss),
            "impact_score": metrics.get("combined_impact", 0),
            "recommendation": llm_analysis.get("recommendation", "Escalate to senior engineering team")
        }
    
    def _estimate_revenue_loss(self, incident: Dict[str, Any], metrics: Dict[str, float]) -> float:
        """Estimate revenue loss from incident.
        
        Args:
            incident: Incident data
            metrics: Impact metrics
            
        Returns:
            Estimated revenue loss in USD
        """
        # Base revenue impact per minute
        base_impact = 500  # USD per minute
        
        # Adjust for severity and duration
        severity_factor = metrics.get("severity_impact", 0.5)
        duration_minutes = float(incident.get("outage_duration", 0))
        service_factor = metrics.get("service_impact_score", 0.5)
        
        estimated_loss = base_impact * severity_factor * (duration_minutes / 10) * service_factor
        
        return max(round(estimated_loss, 2), 0)
    
    def _determine_priority(self, metrics: Dict[str, float], incident: Dict[str, Any]) -> str:
        """Determine priority level.
        
        Args:
            metrics: Impact metrics
            incident: Incident data
            
        Returns:
            Priority level
        """
        combined_impact = metrics.get("combined_impact", 0)
        
        if combined_impact >= 0.8:
            return "critical"
        elif combined_impact >= 0.6:
            return "high"
        elif combined_impact >= 0.4:
            return "medium"
        else:
            return "low"
    
    def _default_impact(self) -> Dict[str, Any]:
        """Return default impact analysis.
        
        Returns:
            Default impact analysis
        """
        return {
            "customer_impact": "Impact analysis in progress",
            "network_impact": "Unknown",
            "business_impact": "Under assessment",
            "affected_services": [],
            "priority_level": "medium",
            "estimated_revenue_loss": 0.0,
            "impact_score": 0.5,
            "recommendation": "Await detailed analysis"
        }
