import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

# Define telecom data
regions = ["North India", "South India", "East India", "West India", "Central India"]
technologies = ["5G", "4G", "LTE", "GSM", "Fiber", "Microwave"]
vendors = ["Ericsson", "Nokia", "Huawei", "Cisco", "Juniper", "Samsung"]
severities = ["critical", "high", "medium", "low", "info"]

# Root causes and descriptions
root_causes = {
    "5G": [
        "Radio frequency interference in millimeter wave bands",
        "Power supply failure in base station",
        "Software bug in RAN controller",
        "Handover failure between cells",
        "Backhaul link congestion",
        "CSP network slice misconfiguration",
    ],
    "4G": [
        "Capacity exhaustion during peak hours",
        "Spectrum interference from adjacent channels",
        "Router buffer overflow",
        "DNS resolution timeout",
        "Gateway processor failure",
        "Load balancer malfunction",
    ],
    "Fiber": [
        "Fiber cut due to construction",
        "Optical signal degradation",
        "OTDR reading anomaly",
        "Splice point failure",
        "Transceiver module failure",
        "Optical amplifier malfunction",
    ],
    "Microwave": [
        "Path obstruction from weather",
        "RF interference from co-channel source",
        "Antenna misalignment",
        "Power amplifier failure",
        "Frequency offset error",
        "Modulation quality degradation",
    ],
}

# Service impacts
service_impacts = [
    "Voice call failures",
    "SMS delivery delays",
    "Data session timeouts",
    "Video streaming buffering",
    "Emergency call drops",
    "Roaming service unavailable",
    "M2M connectivity loss",
    "IoT data transmission failures",
]

# Resolution steps
resolution_steps = [
    "Power cycle base station",
    "Verify power supply specifications",
    "Check RF parameters configuration",
    "Inspect optical fiber continuity",
    "Clear processor memory cache",
    "Reboot network controller",
    "Validate antenna alignment",
    "Check spectrum analyzer readings",
    "Review recent configuration changes",
    "Perform traffic engineering reroute",
]

# Generate dataset
num_records = 500  # Generating 500 realistic incidents

data = []
start_date = datetime(2023, 1, 1)

for i in range(num_records):
    alarm_id = f"ALM_{i+1:06d}"
    
    # Random timestamp within the year
    days_offset = random.randint(0, 364)
    hours_offset = random.randint(0, 23)
    minutes_offset = random.randint(0, 59)
    timestamp = start_date + timedelta(days=days_offset, hours=hours_offset, minutes=minutes_offset)
    
    # Select technology and corresponding root cause
    technology = random.choice(technologies)
    root_cause = random.choice(root_causes.get(technology, ["Unknown cause"]))
    
    # Generate incident description
    region = random.choice(regions)
    vendor = random.choice(vendors)
    severity = random.choice(severities)
    
    if severity == "critical":
        outage_duration = random.randint(30, 240)
    elif severity == "high":
        outage_duration = random.randint(15, 120)
    elif severity == "medium":
        outage_duration = random.randint(5, 60)
    else:
        outage_duration = random.randint(1, 30)
    
    service_impact = random.choice(service_impacts)
    
    # Generate description
    description = f"{technology} network in {region} experiencing {severity} severity incident: {root_cause}. Service affected: {service_impact}. Device vendor: {vendor}."
    
    # Generate resolution notes
    resolution_notes = f"Incident resolved by performing: {', '.join(random.sample(resolution_steps, k=random.randint(2, 4)))}. Root cause verified and preventive measures implemented."
    
    data.append({
        "alarm_id": alarm_id,
        "incident_description": description,
        "network_region": region,
        "technology_type": technology,
        "severity": severity,
        "outage_duration": outage_duration,
        "device_vendor": vendor,
        "resolution_notes": resolution_notes,
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "service_impact": service_impact,
    })

# Create DataFrame
df = pd.DataFrame(data)

# Save to CSV
output_path = "/mnt/user-data/outputs/telecom-fault-intelligence/data/telecom_dataset.csv"
df.to_csv(output_path, index=False)

print(f"✓ Generated {len(df)} telecom incidents")
print(f"✓ Saved to: {output_path}")
print(f"\nDataset schema:")
print(df.head())
print(f"\nDataset info:")
print(df.info())
print(f"\nSeverity distribution:")
print(df['severity'].value_counts())
print(f"\nTechnology distribution:")
print(df['technology_type'].value_counts())
print(f"\nRegion distribution:")
print(df['network_region'].value_counts())
