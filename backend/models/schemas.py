from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SeverityLevel(str, Enum):
    """Severity levels for telecom incidents."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TechnologyType(str, Enum):
    """Telecom technology types."""
    FIVE_G = "5G"
    FOUR_G = "4G"
    LTE = "LTE"
    GSM = "GSM"
    FIBER = "Fiber"
    MICROWAVE = "Microwave"
    SATELLITE = "Satellite"


class DeviceVendor(str, Enum):
    """Telecom equipment vendors."""
    ERICSSON = "Ericsson"
    NOKIA = "Nokia"
    HUAWEI = "Huawei"
    CISCO = "Cisco"
    JUNIPER = "Juniper"
    SAMSUNG = "Samsung"
    QUALCOMM = "Qualcomm"


class TelecomIncident(BaseModel):
    """Base telecom incident model."""
    alarm_id: str = Field(..., description="Unique alarm identifier")
    incident_description: str = Field(..., description="Detailed incident description")
    network_region: str = Field(..., description="Geographic region of the incident")
    technology_type: TechnologyType = Field(..., description="Type of telecom technology")
    severity: SeverityLevel = Field(..., description="Incident severity level")
    outage_duration: int = Field(..., description="Duration of outage in minutes")
    device_vendor: DeviceVendor = Field(..., description="Equipment vendor")
    resolution_notes: str = Field(..., description="Notes on resolution")
    timestamp: datetime = Field(..., description="Incident timestamp")
    service_impact: str = Field(..., description="Service impact description")
    
    class Config:
        use_enum_values = True


class RetrievedIncident(BaseModel):
    """Retrieved incident with similarity score."""
    incident: TelecomIncident
    similarity_score: float = Field(..., description="Similarity score 0-1")
    bm25_score: float = Field(..., description="BM25 keyword score")
    vector_score: float = Field(..., description="Vector similarity score")
    hybrid_score: float = Field(..., description="Hybrid search score")


class RootCauseAnalysis(BaseModel):
    """Root cause analysis result."""
    primary_cause: str = Field(..., description="Primary root cause")
    secondary_causes: List[str] = Field(..., description="Secondary contributing causes")
    confidence_score: float = Field(..., description="Confidence in root cause 0-1")
    analysis_reasoning: str = Field(..., description="Detailed reasoning for root cause")
    similar_incidents: List[str] = Field(..., description="IDs of similar incidents")
    pattern_detected: str = Field(..., description="Detected pattern in incidents")
    probable_causes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Ranked list of probable causes with probability scores and source labels",
    )
    evidence_items: List[str] = Field(
        default_factory=list,
        description="Structured evidence bullets that support the primary root cause",
    )


class ServiceImpactAnalysis(BaseModel):
    """Service impact analysis result."""
    customer_impact: str = Field(..., description="Impact on customers")
    network_impact: str = Field(..., description="Impact on network")
    business_impact: str = Field(..., description="Business impact assessment")
    affected_services: List[str] = Field(..., description="List of affected services")
    priority_level: str = Field(..., description="Priority level (critical/high/medium/low/info/unknown)")
    estimated_revenue_loss: float = Field(default=0.0, description="Estimated revenue loss in USD")


class ResolutionRecommendation(BaseModel):
    """Resolution recommendation result."""
    recommended_actions: List[str] = Field(..., description="Recommended troubleshooting steps")
    historical_fixes: List[Dict[str, Any]] = Field(..., description="Historical fixes for similar issues")
    escalation_recommendation: Optional[str] = Field(None, description="Escalation recommendation")
    confidence_score: float = Field(..., description="Confidence in recommendation 0-1")
    estimated_resolution_time: int = Field(..., description="Estimated resolution time in minutes")


class AgentState(BaseModel):
    """State for LangGraph agent workflow."""
    query: str = Field(..., description="User query")
    retrieved_incidents: List[RetrievedIncident] = Field(default_factory=list)
    root_cause_analysis: Optional[RootCauseAnalysis] = None
    service_impact_analysis: Optional[ServiceImpactAnalysis] = None
    resolution_recommendations: Optional[ResolutionRecommendation] = None
    alarm_correlations: Dict[str, Any] = Field(default_factory=dict)
    final_report: Optional[Dict[str, Any]] = None
    messages: List[Dict[str, str]] = Field(default_factory=list)


class QueryRequest(BaseModel):
    """API request for fault query."""
    query: str = Field(..., description="Natural language fault query")
    region_filter: Optional[str] = None
    severity_filter: Optional[SeverityLevel] = None
    technology_filter: Optional[TechnologyType] = None
    vendor_filter: Optional[DeviceVendor] = None


class QueryResponse(BaseModel):
    """API response for fault query."""
    query_id: str = Field(..., description="Unique query ID")
    retrieved_incidents: List[RetrievedIncident] = Field(..., description="Retrieved incidents")
    root_cause_analysis: RootCauseAnalysis = Field(..., description="Root cause analysis")
    service_impact_analysis: ServiceImpactAnalysis = Field(..., description="Service impact")
    resolution_recommendations: ResolutionRecommendation = Field(..., description="Resolutions")
    alarm_correlations: Dict[str, Any] = Field(..., description="Alarm correlations")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class AlarmCorrelation(BaseModel):
    """Alarm correlation result."""
    correlated_alarms: List[str] = Field(..., description="IDs of correlated alarms")
    correlation_strength: float = Field(..., description="Strength of correlation 0-1")
    common_attributes: List[str] = Field(..., description="Common attributes between alarms")
    root_node: str = Field(..., description="Root node in correlation graph")


class DashboardMetrics(BaseModel):
    """Dashboard metrics for analytics."""
    total_incidents: int = Field(..., description="Total incidents in database")
    incidents_by_region: Dict[str, int] = Field(..., description="Incidents per region")
    incidents_by_severity: Dict[str, int] = Field(..., description="Incidents per severity")
    incidents_by_technology: Dict[str, int] = Field(..., description="Incidents per technology")
    incidents_by_vendor: Dict[str, int] = Field(..., description="Incidents per vendor")
    average_outage_duration: float = Field(..., description="Average outage duration in minutes")
    mttr: float = Field(..., description="Mean time to resolution in minutes")


class RiskPrediction(BaseModel):
    """Risk prediction for a single dimension value."""
    dimension: str = Field(..., description="Dimension type: region, technology, or vendor")
    value: str = Field(..., description="Dimension value, e.g. 'North India' or '5G'")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Risk score 0–1")
    risk_level: str = Field(..., description="HIGH | MEDIUM | LOW")
    incident_count: int = Field(..., description="Historical incident count")
    avg_outage_minutes: float = Field(..., description="Average outage duration in minutes")
    critical_incidents: int = Field(default=0, description="Number of critical incidents")


class PredictiveSummary(BaseModel):
    """Summary statistics returned alongside risk predictions."""
    total_incidents_analyzed: int
    mtbf_hours: float = Field(..., description="Mean time between failures in hours")
    incident_trend_30d: str = Field(..., description="increasing | stable | decreasing")
    last_30_days_incidents: int
    prev_30_days_incidents: int
    current_time_risk: str = Field(..., description="elevated | normal")
    analysis_timestamp: str


class PredictiveOutageResponse(BaseModel):
    """Full response from the predictive outage endpoint."""
    predictions: List[RiskPrediction]
    summary: PredictiveSummary


class RiskAlert(BaseModel):
    """A single high-risk alert entry."""
    type: str = Field(..., description="Alert type, e.g. high_risk_region")
    dimension: str
    value: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    recommendation: str
    critical_incidents: int = Field(default=0)


class EscalationMessage(BaseModel):
    """A2A inter-agent escalation message recorded in workflow state."""
    from_agent: str = Field(..., alias="from")
    to_agent: str = Field(..., alias="to")
    type: str
    reason: str
    timestamp: str

    class Config:
        populate_by_name = True
