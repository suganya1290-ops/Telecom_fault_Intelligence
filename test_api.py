#!/usr/bin/env python
"""
Example script demonstrating API usage for Telecom Fault Intelligence System.
Run this after starting the backend server.
"""

import requests
import json
import time
from typing import Dict, Any

API_BASE = "http://localhost:8000/api"

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")

def health_check():
    """Check system health."""
    print_section("1. Health Check")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        result = response.json()
        print(f"Status: {result.get('status')}")
        print(f"Services: {json.dumps(result.get('services'), indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False

def get_status():
    """Get system status."""
    print_section("2. System Status")
    try:
        response = requests.get(f"{API_BASE}/status", timeout=5)
        result = response.json()
        print(f"RAG Initialized: {result.get('rag_initialized')}")
        if result.get('collection_stats'):
            stats = result['collection_stats']
            print(f"Collection Stats:")
            print(f"  - Total Documents: {stats.get('total_documents')}")
            print(f"  - Path: {stats.get('database_path')}")
    except Exception as e:
        print(f"❌ Status check failed: {str(e)}")

def example_queries():
    """Run example fault queries."""
    print_section("3. Example Fault Analysis Queries")
    
    queries = [
        {
            "query": "Users in North India experiencing intermittent 5G connectivity issues",
            "region_filter": "North India",
            "severity_filter": "high",
            "technology_filter": "5G"
        },
        {
            "query": "Call drops have suddenly increased after a recent network configuration update",
            "severity_filter": "critical"
        },
        {
            "query": "Data sessions are timing out during peak traffic hours in Fiber backbone",
            "technology_filter": "Fiber",
            "severity_filter": "medium"
        }
    ]
    
    for i, query_obj in enumerate(queries, 1):
        print(f"\n--- Query {i} ---")
        print(f"Query: {query_obj['query']}")
        if query_obj.get('region_filter'):
            print(f"Region Filter: {query_obj['region_filter']}")
        if query_obj.get('severity_filter'):
            print(f"Severity Filter: {query_obj['severity_filter']}")
        if query_obj.get('technology_filter'):
            print(f"Technology Filter: {query_obj['technology_filter']}")
        
        try:
            print("\nProcessing...")
            start = time.time()
            
            response = requests.post(
                f"{API_BASE}/query",
                json=query_obj,
                timeout=15
            )
            
            elapsed = time.time() - start
            result = response.json()
            
            if response.status_code == 200:
                print(f"✅ Query completed in {elapsed:.2f}s\n")
                
                # Print retrieved incidents
                incidents = result.get('retrieved_incidents', [])
                print(f"Retrieved {len(incidents)} incidents:")
                for j, incident in enumerate(incidents[:2], 1):
                    inc_data = incident.get('incident', {})
                    print(f"  {j}. {inc_data.get('alarm_id')} - "
                          f"{inc_data.get('network_region')} - "
                          f"{inc_data.get('severity').upper()}")
                    print(f"     Match: {incident.get('hybrid_score', 0):.0%}")
                
                # Print root cause
                root_cause = result.get('root_cause_analysis', {})
                if root_cause:
                    print(f"\nRoot Cause: {root_cause.get('primary_cause')}")
                    print(f"Confidence: {root_cause.get('confidence_score', 0):.0%}")
                
                # Print service impact
                impact = result.get('service_impact_analysis', {})
                if impact:
                    print(f"\nService Impact: {impact.get('priority_level').upper()}")
                    print(f"Revenue Loss: ${impact.get('estimated_revenue_loss', 0):.2f}")
                
                # Print resolution recommendations
                resolution = result.get('resolution_recommendations', {})
                if resolution and resolution.get('recommended_actions'):
                    actions = resolution['recommended_actions']
                    print(f"\nRecommended Actions ({len(actions)} steps):")
                    for k, action in enumerate(actions[:3], 1):
                        print(f"  {k}. {action}")
                    if len(actions) > 3:
                        print(f"  ... and {len(actions) - 3} more steps")
                
                print(f"\nProcessing Time: {result.get('processing_time_ms', 0):.0f}ms")
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.text)
        
        except requests.Timeout:
            print("❌ Request timeout (>15s)")
        except Exception as e:
            print(f"❌ Error: {str(e)}")

def get_dashboard_metrics():
    """Fetch dashboard metrics."""
    print_section("4. Dashboard Metrics")
    
    try:
        response = requests.get(f"{API_BASE}/dashboard/metrics", timeout=5)
        result = response.json()
        
        print(f"Total Incidents: {result.get('total_incidents')}")
        print(f"Average Outage Duration: {result.get('average_outage_duration'):.1f} minutes")
        print(f"Mean Time to Resolution: {result.get('mttr', 0):.1f} minutes")
        
        print("\nIncidents by Severity:")
        for severity, count in result.get('incidents_by_severity', {}).items():
            print(f"  - {severity.capitalize()}: {count}")
        
        print("\nIncidents by Technology:")
        for tech, count in result.get('incidents_by_technology', {}).items():
            print(f"  - {tech}: {count}")
        
        print("\nIncidents by Region:")
        for region, count in result.get('incidents_by_region', {}).items():
            print(f"  - {region}: {count}")
    
    except Exception as e:
        print(f"❌ Error fetching metrics: {str(e)}")

def test_root_cause_analysis():
    """Test root cause analysis endpoint."""
    print_section("5. Root Cause Analysis Endpoint")
    
    try:
        response = requests.get(
            f"{API_BASE}/root-cause",
            params={"query": "BTS power supply failure in Mumbai"},
            timeout=10
        )
        
        result = response.json()
        print(f"Primary Cause: {result.get('primary_cause')}")
        print(f"Confidence: {result.get('confidence_score', 0):.0%}")
        print(f"\nReasoning: {result.get('reasoning')}")
        
        if result.get('secondary_causes'):
            print(f"\nSecondary Causes:")
            for cause in result['secondary_causes']:
                print(f"  - {cause}")
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_alarm_correlation():
    """Test alarm correlation endpoint."""
    print_section("6. Alarm Correlation Endpoint")
    
    try:
        response = requests.get(
            f"{API_BASE}/correlate",
            params={"query": "Multiple cell site failures in same region"},
            timeout=10
        )
        
        result = response.json()
        print(f"Root Alarm: {result.get('root_node')}")
        print(f"Correlation Strength: {result.get('correlation_strength', 0):.0%}")
        print(f"Correlated Alarms: {len(result.get('correlated_alarms', []))}")
        print(f"\nExplanation: {result.get('explanation')}")
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def performance_test():
    """Test API performance."""
    print_section("7. Performance Test")
    
    query = {
        "query": "5G network synchronization failure in tower cluster"
    }
    
    latencies = []
    
    for i in range(3):
        try:
            start = time.time()
            response = requests.post(f"{API_BASE}/query", json=query, timeout=20)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            
            if response.status_code == 200:
                print(f"Attempt {i+1}: {latency:.0f}ms ✅")
            else:
                print(f"Attempt {i+1}: Error {response.status_code}")
        except Exception as e:
            print(f"Attempt {i+1}: Failed - {str(e)}")
    
    if latencies:
        print(f"\nPerformance Summary:")
        print(f"  Min: {min(latencies):.0f}ms")
        print(f"  Max: {max(latencies):.0f}ms")
        print(f"  Avg: {sum(latencies)/len(latencies):.0f}ms")

def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  TELECOM FAULT INTELLIGENCE - API TEST SUITE")
    print("=" * 70)
    
    # Check if server is running
    if not health_check():
        print("\n❌ Server not running. Start with:")
        print("   cd backend && python -m uvicorn main:app --reload")
        return
    
    # Run tests
    get_status()
    example_queries()
    get_dashboard_metrics()
    test_root_cause_analysis()
    test_alarm_correlation()
    performance_test()
    
    print_section("Test Suite Complete")
    print("✅ All tests completed!\n")

if __name__ == "__main__":
    main()
