import logging
from typing import Dict, List, Any, Set, Tuple
import networkx as nx
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlarmCorrelationEngine:
    """Correlates alarms across network to identify related incidents."""
    
    def __init__(self):
        """Initialize correlation engine."""
        self.graph = nx.DiGraph()
        self.alarms = {}
        self.correlation_rules = self._initialize_rules()
    
    def _initialize_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize correlation rules for telecom alarms.
        
        Returns:
            Dictionary of correlation rules
        """
        return {
            "same_region_and_technology": {
                "weight": 0.9,
                "description": "Same network region and technology type"
            },
            "same_vendor": {
                "weight": 0.7,
                "description": "Same device vendor"
            },
            "temporal_proximity": {
                "weight": 0.8,
                "description": "Incidents within 1 hour of each other"
            },
            "same_service_impact": {
                "weight": 0.6,
                "description": "Same type of service impact"
            },
            "severity_cascade": {
                "weight": 0.85,
                "description": "Critical incident followed by high severity in same region"
            },
        }
    
    def add_alarm(self, alarm: Dict[str, Any]) -> None:
        """Add alarm to correlation engine.
        
        Args:
            alarm: Alarm data dictionary
        """
        alarm_id = alarm.get("alarm_id", "")
        if not alarm_id:
            return
        
        self.alarms[alarm_id] = alarm
        self.graph.add_node(alarm_id, **alarm)
    
    def correlate_alarms(self, alarm_ids: List[str], time_window_hours: int = 24) -> Dict[str, Any]:
        """Correlate a set of alarms.
        
        Args:
            alarm_ids: List of alarm IDs to correlate
            time_window_hours: Time window for correlation
            
        Returns:
            Correlation analysis result
        """
        if not alarm_ids:
            return {"correlations": {}, "root_node": None, "strength": 0.0}
        
        try:
            # Build correlation graph
            self._build_correlation_graph(alarm_ids, time_window_hours)
            
            # Identify root alarm (most central node)
            root_node = self._find_root_alarm(alarm_ids)
            
            # Measure correlation strength
            correlation_strength = self._measure_correlation_strength(alarm_ids)
            
            # Find correlated groups
            correlated_groups = self._find_correlated_groups(alarm_ids)
            
            # Extract common attributes
            common_attrs = self._extract_common_attributes(alarm_ids)
            
            return {
                "correlated_alarms": alarm_ids,
                "root_node": root_node,
                "correlation_strength": correlation_strength,
                "correlated_groups": correlated_groups,
                "common_attributes": common_attrs,
                "explanation": self._generate_correlation_explanation(
                    alarm_ids, root_node, correlation_strength, common_attrs
                )
            }
        
        except Exception as e:
            logger.error(f"✗ Error correlating alarms: {str(e)}")
            return {"correlations": {}, "root_node": None, "strength": 0.0}
    
    def _build_correlation_graph(self, alarm_ids: List[str], time_window_hours: int) -> None:
        """Build correlation graph between alarms.
        
        Args:
            alarm_ids: Alarm IDs
            time_window_hours: Time window for correlation
        """
        for i, alarm_id_1 in enumerate(alarm_ids):
            if alarm_id_1 not in self.alarms:
                continue
            
            alarm_1 = self.alarms[alarm_id_1]
            
            for alarm_id_2 in alarm_ids[i+1:]:
                if alarm_id_2 not in self.alarms:
                    continue
                
                alarm_2 = self.alarms[alarm_id_2]
                
                # Calculate correlation strength
                strength = self._calculate_correlation_strength(
                    alarm_1, alarm_2, time_window_hours
                )
                
                if strength > 0.3:  # Only add if meaningful correlation
                    self.graph.add_edge(alarm_id_1, alarm_id_2, weight=strength)
                    self.graph.add_edge(alarm_id_2, alarm_id_1, weight=strength)
    
    def _calculate_correlation_strength(self, 
                                       alarm_1: Dict[str, Any],
                                       alarm_2: Dict[str, Any],
                                       time_window_hours: int) -> float:
        """Calculate correlation strength between two alarms.
        
        Args:
            alarm_1: First alarm
            alarm_2: Second alarm
            time_window_hours: Time window
            
        Returns:
            Correlation strength 0-1
        """
        strength = 0.0
        
        # Rule 1: Same region and technology
        if (alarm_1.get("network_region") == alarm_2.get("network_region") and
            alarm_1.get("technology_type") == alarm_2.get("technology_type")):
            strength += self.correlation_rules["same_region_and_technology"]["weight"]
        
        # Rule 2: Same vendor
        if alarm_1.get("device_vendor") == alarm_2.get("device_vendor"):
            strength += self.correlation_rules["same_vendor"]["weight"]
        
        # Rule 3: Temporal proximity
        try:
            time_1 = datetime.fromisoformat(str(alarm_1.get("timestamp", "")))
            time_2 = datetime.fromisoformat(str(alarm_2.get("timestamp", "")))
            time_diff = abs((time_1 - time_2).total_seconds() / 3600)
            
            if time_diff < time_window_hours:
                temporal_score = self.correlation_rules["temporal_proximity"]["weight"] * (1 - time_diff / time_window_hours)
                strength += temporal_score
        except:
            pass
        
        # Rule 4: Same service impact
        if alarm_1.get("service_impact") == alarm_2.get("service_impact"):
            strength += self.correlation_rules["same_service_impact"]["weight"]
        
        # Rule 5: Severity cascade
        if (alarm_1.get("network_region") == alarm_2.get("network_region") and
            alarm_1.get("severity") in ["critical", "high"] and
            alarm_2.get("severity") in ["high", "medium"]):
            strength += self.correlation_rules["severity_cascade"]["weight"]
        
        # Normalize to 0-1
        return min(strength / 3.5, 1.0)  # Max possible is ~3.5
    
    def _find_root_alarm(self, alarm_ids: List[str]) -> str:
        """Find root alarm (most central node).
        
        Args:
            alarm_ids: Alarm IDs
            
        Returns:
            Root alarm ID
        """
        if not alarm_ids:
            return None
        
        # Calculate centrality
        subgraph = self.graph.subgraph(alarm_ids)
        if len(subgraph) == 0:
            return alarm_ids[0]
        
        try:
            centrality = nx.betweenness_centrality(subgraph)
            root = max(centrality, key=centrality.get) if centrality else alarm_ids[0]
            return root
        except:
            return alarm_ids[0]
    
    def _measure_correlation_strength(self, alarm_ids: List[str]) -> float:
        """Measure overall correlation strength.
        
        Args:
            alarm_ids: Alarm IDs
            
        Returns:
            Correlation strength 0-1
        """
        if len(alarm_ids) <= 1:
            return 0.0
        
        subgraph = self.graph.subgraph(alarm_ids)
        if len(subgraph.edges()) == 0:
            return 0.0
        
        # Average edge weight
        total_weight = sum(d['weight'] for u, v, d in subgraph.edges(data=True))
        return total_weight / len(subgraph.edges())
    
    def _find_correlated_groups(self, alarm_ids: List[str]) -> List[List[str]]:
        """Find correlated groups within alarms.
        
        Args:
            alarm_ids: Alarm IDs
            
        Returns:
            List of correlated groups
        """
        subgraph = self.graph.subgraph(alarm_ids)
        
        # Find connected components
        try:
            components = list(nx.connected_components(subgraph.to_undirected()))
            return [list(comp) for comp in components]
        except:
            return [alarm_ids]
    
    def _extract_common_attributes(self, alarm_ids: List[str]) -> List[str]:
        """Extract common attributes of alarms.
        
        Args:
            alarm_ids: Alarm IDs
            
        Returns:
            List of common attributes
        """
        if not alarm_ids:
            return []
        
        common_attrs = []
        attributes = ["network_region", "technology_type", "device_vendor", "severity", "service_impact"]
        
        for attr in attributes:
            values = [self.alarms[aid].get(attr) for aid in alarm_ids if aid in self.alarms]
            
            if values and len(set(values)) == 1:
                common_attrs.append(f"{attr}: {values[0]}")
        
        return common_attrs
    
    def _generate_correlation_explanation(self,
                                        alarm_ids: List[str],
                                        root_node: str,
                                        strength: float,
                                        common_attrs: List[str]) -> str:
        """Generate explanation for correlations.
        
        Args:
            alarm_ids: Alarm IDs
            root_node: Root alarm ID
            strength: Correlation strength
            common_attrs: Common attributes
            
        Returns:
            Explanation text
        """
        explanation = f"Identified {len(alarm_ids)} correlated alarms with {strength:.1%} correlation strength. "
        
        if root_node and root_node in self.alarms:
            root_alarm = self.alarms[root_node]
            explanation += f"Root alarm is {root_node} ({root_alarm.get('severity', 'unknown')} severity) in {root_alarm.get('network_region', 'unknown')}. "
        
        if common_attrs:
            explanation += f"Common attributes: {', '.join(common_attrs)}."
        
        return explanation
    
    def clear(self) -> None:
        """Clear all data."""
        self.graph.clear()
        self.alarms.clear()
