"""
Dataset Enrichment Script
=========================
Adds 5 new RCA-critical columns to telecom_dataset_merged.csv:
  root_cause_category   – high-level fault class
  root_cause_detail     – specific root cause for this record
  fault_component       – network element that failed
  affected_layer        – Radio / Transport / Core / Service / OSS
  symptom_keywords      – comma-separated terms boosting BM25 recall
  contributing_factors  – pipe-separated secondary causes

Also expands the 10 generic 5G descriptions into 50+ specific variants
and rewrites resolution_notes to match the specific root cause.
Output: Data/telecom_dataset_enriched.csv  (12,500 records)
"""

import pandas as pd
import hashlib

IN  = "Data/telecom_dataset_merged.csv"
OUT = "Data/telecom_dataset_enriched.csv"

df = pd.read_csv(IN)

# ── Deterministic hash → index ────────────────────────────────────────────────
def h(alarm_id: str, n: int) -> int:
    """Reproducible index from alarm_id so enrichment is deterministic."""
    digest = hashlib.md5(alarm_id.encode()).digest()
    return int.from_bytes(digest[:4], "little") % n


# ══════════════════════════════════════════════════════════════════════════════
# Root-cause knowledge base  (keyed by canonical incident_description)
# ══════════════════════════════════════════════════════════════════════════════

ROOT_CAUSES = {

    "Radio link failures across sectors": {
        "category": "Radio Access Network Failure",
        "layer": "Radio",
        "component": "RRU/AAU",
        "details": [
            ("RRU hardware fault — baseband processing unit failure",
             "Replaced faulty RRU module and re-ran cell bring-up procedure",
             "RRU failure|VSWR alarm|cell outage|hardware fault|RF power degradation",
             "Antenna feeder degradation|Power supply instability"),
            ("AAU antenna feeder cable cut or high VSWR",
             "Inspected and replaced damaged feeder cable; re-aligned antenna",
             "antenna feeder|VSWR|RF mismatch|high VSWR|cable fault",
             "Weather-related damage|Physical obstruction"),
            ("Adjacent cell interference — pilot pollution",
             "Adjusted RF parameters: reduced pilot power, updated neighbor list",
             "interference|pilot pollution|SINR degradation|handover failure",
             "Frequency reuse conflict|Overshooting cells"),
            ("Software-triggered radio link failure after parameter push",
             "Rolled back SON parameter update; re-validated handover thresholds",
             "parameter misconfiguration|SON error|handover threshold|software regression",
             "Incorrect neighbor relation|Timer misconfiguration"),
            ("Power supply instability causing intermittent RRU resets",
             "Replaced rectifier module; tested battery backup under load",
             "power supply|rectifier fault|site power|battery backup|UPS failure",
             "AC mains fluctuation|Aging battery bank"),
        ],
    },

    "Fiber latency spike between backbone nodes": {
        "category": "Transmission / Backhaul Failure",
        "layer": "Transport",
        "component": "Optical Fiber / DWDM",
        "details": [
            ("Fiber cut due to civil excavation near route",
             "Rerouted traffic to protection path; dispatched field team for splicing",
             "fiber cut|optical signal loss|LOS alarm|physical damage|civil work",
             "Route exposure to civil works|No diverse path"),
            ("Optical amplifier (EDFA) gain tilt causing BER increase",
             "Adjusted EDFA gain settings; replaced degraded pump laser",
             "EDFA|optical amplifier|BER increase|gain tilt|OTN alarm",
             "Aging optical components|Temperature variation"),
            ("SFP/XFP transceiver module degradation",
             "Replaced SFP module; cleaned fiber connectors with IPA",
             "SFP failure|transceiver|optical Tx power|Rx sensitivity|dirty connector",
             "Dust contamination|Module end-of-life"),
            ("MPLS routing loop causing micro-bursts and queuing delay",
             "Cleared MPLS routing table; fixed BGP route redistribution policy",
             "routing loop|MPLS|BGP|micro-burst|queuing delay|packet loss",
             "BGP misconfiguration|IGP route leak"),
            ("Wavelength contention in DWDM ring after node failure",
             "Switched to protection wavelength; raised DWDM ring recovery",
             "DWDM|wavelength|OTN|ring protection|APS switching|optical path",
             "Single-ring topology risk|Protection switching delay"),
        ],
    },

    "5G users unable to establish data sessions": {
        "category": "5G Core / gNB Session Failure",
        "layer": "Core",
        "component": "AMF / SMF / UPF",
        "details": [
            ("AMF overload — signaling storm from mass UE re-registration",
             "Scaled AMF instances; applied rate-limiting on registration requests",
             "AMF overload|5GC|signaling storm|UE registration|NAS reject|5G core",
             "UE firmware bug causing re-registration loop|Capacity under-provisioning"),
            ("SMF PDU session establishment failure — UPF path unreachable",
             "Restarted UPF instance; re-established N4 session between SMF and UPF",
             "SMF failure|PDU session|UPF|N4 interface|data plane|5G session",
             "N4 heartbeat timeout|UPF software crash"),
            ("gNB software defect — RRC connection reject after upgrade",
             "Rolled back gNB software; applied vendor hotfix for RRC state machine",
             "gNB|RRC reject|software defect|NR|radio bearer|5G NR",
             "Incompatible parameter set after upgrade|Software regression"),
            ("Backhaul bandwidth saturation — F1 interface congestion",
             "Applied QoS prioritisation on F1 link; scheduled capacity upgrade",
             "backhaul|F1 interface|CU-DU split|bandwidth|congestion|throughput",
             "Traffic growth exceeding capacity plan|No QoS marking on F1"),
            ("DNS / FQDN resolution failure in 5GC service mesh",
             "Fixed DNS entry for NRF FQDN; cleared stale SBI service cache",
             "DNS|FQDN|NRF|SBI|service mesh|5GC|service discovery",
             "Expired DNS TTL|NRF de-registration not propagated"),
        ],
    },

    "Packet gateway overload during peak traffic": {
        "category": "Core Network Capacity / Congestion",
        "layer": "Core",
        "component": "PGW / UPF / SGW",
        "details": [
            ("GTP tunnel leak causing PGW memory exhaustion",
             "Cleared stale GTP tunnels via CLI; patched GTP-U leak in software",
             "GTP tunnel|PGW|memory exhaustion|tunnel leak|EPC|packet gateway",
             "Incomplete bearer teardown|Session accounting mismatch"),
            ("Traffic surge 40% above baseline — no pre-provisioned capacity",
             "Added horizontal PGW instances; load-balanced across two SGW clusters",
             "traffic surge|capacity|load balancing|PGW scaling|peak traffic|congestion",
             "Event-driven traffic spike|Under-dimensioned capacity plan"),
            ("Signaling storm from rogue UE firmware — excessive Attach/Detach",
             "Blocked IMEI range; applied rate-limiting on Attach procedures at MME",
             "signaling storm|rogue UE|MME|Attach|Detach|IMSI|rate limiting",
             "Faulty device firmware|Mass device deployment without testing"),
            ("License capacity limit reached on PGW bearer count",
             "Requested emergency license extension; shed low-priority bearer sessions",
             "license|bearer count|PGW capacity|license expiry|bearer limit",
             "License renewal not tracked|Rapid subscriber growth"),
            ("PGW process crash due to malformed GTPv2 IE from roaming partner",
             "Applied input validation patch; added GTPv2 sanity filter at border",
             "GTPv2|malformed packet|roaming|PGW crash|IE parsing|inter-PLMN",
             "Roaming partner software defect|No input validation at GTP border"),
        ],
    },

    "DNS resolution issues impacting services": {
        "category": "DNS / Service Discovery Failure",
        "layer": "Service",
        "component": "DNS Server / Resolver",
        "details": [
            ("DNS server misconfiguration after zone file edit",
             "Restored DNS zone file from backup; reloaded BIND service",
             "DNS misconfiguration|zone file|BIND|NXDOMAIN|resolution failure",
             "Manual zone edit without validation|No change management gate"),
            ("DNS cache poisoning — stale negative cache entries",
             "Flushed DNS cache on all resolvers; corrected TTL values",
             "DNS cache|poisoning|stale cache|negative cache|TTL|resolver",
             "Short TTL causing amplification|Resolver not DNSSEC-validated"),
            ("Network partition isolating DNS servers from resolvers",
             "Restored ACL rules; added secondary DNS in separate network segment",
             "network partition|DNS isolation|ACL|firewall|DNS split-brain",
             "Firewall rule change blocking DNS|Single DNS segment risk"),
            ("DNS flood attack consuming resolver thread pool",
             "Rate-limited DNS queries per source IP; enabled anycast DNS failover",
             "DNS flood|DDoS|resolver overload|rate limiting|anycast DNS|attack",
             "No DNS rate-limiting policy|Public resolver exposed"),
            ("Recursive DNS query loop between internal resolvers",
             "Fixed forwarder configuration; broke circular delegation chain",
             "DNS loop|recursive query|forwarder|circular delegation|query storm",
             "Misconfigured conditional forwarder|Missing root hints"),
        ],
    },

    "Multiple BTS synchronization failures": {
        "category": "Timing & Synchronisation Failure",
        "layer": "Radio",
        "component": "GPS / PTP / SyncE",
        "details": [
            ("GPS/GNSS antenna signal loss due to obstruction or jamming",
             "Relocated GPS antenna to clear line-of-sight; validated GNSS lock",
             "GPS|GNSS|antenna|synchronisation|timing|clock failure|jamming",
             "Urban canyon multipath|Deliberate GNSS jamming near site"),
            ("PTP/IEEE 1588 grandmaster clock failure",
             "Switched to backup grandmaster; verified boundary clock chain",
             "PTP|IEEE 1588|grandmaster|boundary clock|synchronisation|timing",
             "Single grandmaster SPOF|Holdover duration insufficient"),
            ("SyncE reference clock degradation — SSM QL-EEC1 → QL-DNU",
             "Traced SSM degradation to upstream switch; replaced faulty SFP",
             "SyncE|synchronous Ethernet|SSM|QL-EEC1|timing|clock quality",
             "Upstream SFP generating wrong SSM|No redundant SyncE path"),
            ("Holdover oscillator drift after extended GPS outage",
             "Replaced OCXO oscillator; reduced holdover period in config",
             "holdover|oscillator|OCXO|drift|frequency error|timing degradation",
             "Aging oscillator|Extended GPS unavailability"),
            ("Backhaul latency asymmetry corrupting PTP offset calculation",
             "Enabled TC (Transparent Clock) on all intermediate switches",
             "PTP asymmetry|backhaul delay|transparent clock|timing offset",
             "Asymmetric delay on backhaul|No TC on intermediate nodes"),
        ],
    },

    "Core authentication service failures": {
        "category": "Authentication / Subscriber Management Failure",
        "layer": "Core",
        "component": "HSS / UDM / AAA",
        "details": [
            ("HSS/UDM database replication lag causing stale subscription data",
             "Forced DB resync; increased replication bandwidth allocation",
             "HSS|UDM|database replication|subscriber|authentication|EPC|5GC",
             "Network partition between DB nodes|Replication lag threshold exceeded"),
            ("TLS certificate expiry on Diameter/SBI interface",
             "Renewed certificate; automated cert rotation with Let's Encrypt",
             "certificate expiry|TLS|Diameter|SBI|authentication|PKI|certificate",
             "No certificate expiry monitoring|Manual renewal process"),
            ("EPC/5GC signaling storm from mass UE authentication retry",
             "Applied back-off timer; rate-limited S6a/Nudm messages at HSS",
             "signaling storm|authentication retry|S6a|Nudm|HSS|MME|AUSF",
             "UE storm after paging area update|No retry throttling"),
            ("HSS software crash due to malformed MAP message from roaming HLR",
             "Applied input validation patch; blocked malformed MAP source",
             "HSS crash|MAP|HLR|roaming|SS7|malformed message|authentication",
             "Roaming partner MAP defect|No input validation at STP"),
            ("AAA RADIUS server disk full — accounting records not written",
             "Cleared disk; moved accounting to remote syslog; expanded storage",
             "RADIUS|AAA|disk full|accounting|authentication log|capacity",
             "No disk monitoring|Log retention policy misconfigured"),
        ],
    },

    "Intermittent voice service degradation": {
        "category": "VoLTE / VoNR Quality Degradation",
        "layer": "Service",
        "component": "IMS / P-CSCF / QoS",
        "details": [
            ("IMS P-CSCF overload — SIP transaction timeout",
             "Scaled P-CSCF capacity; applied SIP load balancing across cluster",
             "IMS|P-CSCF|SIP|VoLTE|voice quality|SIP timeout|overload",
             "IMS capacity not scaled with data growth|No P-CSCF load balancer"),
            ("QoS misconfiguration — voice bearer marked as best-effort",
             "Corrected DSCP marking for QCI-1 bearer; validated end-to-end QoS",
             "QoS|DSCP|QCI|voice bearer|jitter|packet loss|VoLTE|marking",
             "QoS policy not propagated after upgrade|Transport ignoring DSCP"),
            ("Codec negotiation failure — mismatched CODEC list in SDP",
             "Aligned CODEC priority list between IMS core and RAN; tested AMR-WB",
             "codec|SDP|AMR-WB|VoLTE|EVS|codec negotiation|voice quality",
             "Vendor interop issue|Feature flag mismatch after upgrade"),
            ("RTP jitter buffer overflow due to transport delay variation",
             "Tuned jitter buffer depth; implemented DSCP re-marking at transport",
             "RTP|jitter|jitter buffer|delay variation|voice quality|MOS score",
             "Transport congestion causing delay variation|Buffer too small"),
            ("VoNR hand-in failure from 5G to 4G during voice call",
             "Fixed EPS fallback timer; updated SRVCC parameters in gNB",
             "VoNR|VoLTE|handover|SRVCC|EPS fallback|5G|4G|voice continuity",
             "EPS fallback not configured|Missing SRVCC neighbour relation"),
        ],
    },

    "Increased call drops after configuration update": {
        "category": "Configuration / Change Management Error",
        "layer": "Radio",
        "component": "eNB / gNB / SON",
        "details": [
            ("Incorrect handover A3 offset pushed via SON — aggressive handover",
             "Rolled back A3 offset to previous value; added CI/CD gate for params",
             "handover|A3 offset|SON|call drop|HO failure|configuration error",
             "SON parameter validation missing|No staged rollout of parameters"),
            ("Timer T310/T311 misconfiguration causing premature RLF declaration",
             "Reset RLF timers to 3GPP default; tested in lab before re-push",
             "T310|T311|RLF|radio link failure|call drop|timer|configuration",
             "Timer defaults overridden without testing|No pre-change simulation"),
            ("Neighbour relation update removing active neighbours",
             "Restored neighbour list from backup; added mandatory neighbours",
             "neighbour relation|ANR|handover|call drop|missing neighbour|NRT",
             "ANR over-pruning|No HO success rate check post-update"),
            ("Software regression in scheduler after eNB firmware upgrade",
             "Downgraded to previous firmware version; raised vendor JIRA",
             "software regression|firmware upgrade|scheduler|eNB|call drop|bug",
             "Upgrade without lab validation|Insufficient regression test suite"),
            ("Power control parameter error causing uplink interference",
             "Corrected P0 and alpha for PUSCH; ran interference scan post-fix",
             "power control|PUSCH|uplink interference|call drop|P0|alpha|UL SINR",
             "Incorrect cell-specific power control|No UL interference monitoring"),
        ],
    },

    "Backhaul congestion detected": {
        "category": "Backhaul / Transmission Congestion",
        "layer": "Transport",
        "component": "Microwave / Ethernet / MPLS",
        "details": [
            ("Microwave link rain fade — SNR below adaptive modulation threshold",
             "Switched to protection link; lowered modulation to QPSK during fade",
             "microwave|rain fade|SNR|adaptive modulation|backhaul|link budget",
             "Insufficient link margin for heavy rain|No space diversity"),
            ("Ethernet uplink port speed negotiation failure — running at 100M",
             "Fixed port autoneg to 1G forced; replaced faulty SFP on aggregation",
             "Ethernet|port speed|autoneg|100M|SFP|backhaul|throughput",
             "Auto-negotiation mismatch|Aging SFP causing CRC errors"),
            ("MPLS QoS policy missing — all traffic best-effort during congestion",
             "Deployed QoS policy with 5 traffic classes; prioritised voice/signalling",
             "MPLS|QoS|best-effort|congestion|traffic class|backhaul|priority",
             "No QoS policy post-MPLS migration|Missing traffic classification"),
            ("Backhaul bandwidth capacity exceeded — no upgrade in plan",
             "Activated dormant capacity on existing microwave; accelerated upgrade",
             "bandwidth|capacity|backhaul|congestion|throughput|capacity planning",
             "Traffic growth not tracked|Procurement lead time exceeded"),
            ("GRE tunnel MTU mismatch causing IP fragmentation and retransmission",
             "Set MTU to 1400 on GRE tunnel; enabled DF-bit and PMTUD",
             "GRE|MTU|fragmentation|retransmission|PMTUD|backhaul|tunnel",
             "No MTU alignment after GRE encapsulation|DF-bit not set"),
        ],
    },
}

# ── Vendor → component specialisation ────────────────────────────────────────
VENDOR_COMPONENT = {
    "Ericsson": {"Radio": "Ericsson Radio System (ERS)", "Core": "Ericsson Cloud Core", "Transport": "Ericsson MINI-LINK"},
    "Nokia":    {"Radio": "Nokia AirScale RRH",           "Core": "Nokia CloudBand",      "Transport": "Nokia WaveFlex"},
    "Huawei":   {"Radio": "Huawei AAU",                   "Core": "Huawei CloudEPC",      "Transport": "Huawei RTN"},
    "Cisco":    {"Radio": "Cisco Ultra RAN",              "Core": "Cisco Ultra Packet Core","Transport": "Cisco ASR"},
    "Juniper":  {"Radio": "Juniper RAN Stack",            "Core": "Juniper 5G UPF",       "Transport": "Juniper MX"},
    "Samsung":  {"Radio": "Samsung Massive MIMO",         "Core": "Samsung vCore",        "Transport": "Samsung Backhaul"},
}

# ── Severity → contributing factor prefix ────────────────────────────────────
SEV_FACTOR = {
    "critical": "Single point of failure with no redundancy",
    "high":     "Delayed detection due to alert suppression",
    "medium":   "Gradual degradation not caught in capacity review",
    "low":      "Low-priority maintenance deferred",
    "info":     "Informational — no immediate user impact",
}

# ── Region → geography context ───────────────────────────────────────────────
REGION_CONTEXT = {
    "North India": "high-density urban corridor",
    "South India": "coastal metro with high data demand",
    "East India":  "semi-urban rollout with legacy 2G co-existence",
    "West India":  "financial hub with SLA-critical enterprise traffic",
    "Central India": "rural coverage expansion zone",
}


def enrich_row(row: pd.Series) -> dict:
    """Return enrichment dict for one row."""
    desc  = row["incident_description"]
    alid  = str(row["alarm_id"])
    vend  = str(row.get("device_vendor", "Ericsson"))
    sev   = str(row.get("severity", "medium")).lower()
    layer_default = "Radio"

    if desc not in ROOT_CAUSES:
        # Original 500-record dataset — descriptions already have specific causes
        # Extract the declared cause from parenthetical if present
        cause_text = desc
        return {
            "root_cause_category":  "Network Fault — see incident description",
            "root_cause_detail":    cause_text[:120],
            "fault_component":      vend,
            "affected_layer":       "Mixed",
            "symptom_keywords":     " ".join(desc.lower().split()[:12]),
            "contributing_factors": SEV_FACTOR.get(sev, ""),
        }

    kb    = ROOT_CAUSES[desc]
    idx   = h(alid, len(kb["details"]))
    detail, resolution, keywords, factors = kb["details"][idx]

    layer     = kb["layer"]
    base_comp = kb["component"]
    vend_comp = VENDOR_COMPONENT.get(vend, {}).get(layer, base_comp)
    region    = str(row.get("network_region", ""))
    geo       = REGION_CONTEXT.get(region, "regional telecom zone")

    contrib = f"{SEV_FACTOR.get(sev,'')} | {factors} | Deployed in {geo}"

    return {
        "root_cause_category":  kb["category"],
        "root_cause_detail":    f"{detail} ({vend_comp})",
        "fault_component":      f"{vend_comp} ({vend})",
        "affected_layer":       layer,
        "symptom_keywords":     keywords,
        "contributing_factors": contrib,
    }


def enrich_resolution(row: pd.Series, enrichment: dict) -> str:
    """Replace generic resolution note with a cause-specific one."""
    desc  = row["incident_description"]
    if desc not in ROOT_CAUSES:
        return row["resolution_notes"]  # keep original rich notes

    kb    = ROOT_CAUSES[desc]
    alid  = str(row["alarm_id"])
    idx   = h(alid, len(kb["details"]))
    _, resolution, _, _ = kb["details"][idx]
    return resolution


def enrich_description(row: pd.Series, enrichment: dict) -> str:
    """Make generic 5G descriptions specific by appending root cause."""
    desc  = row["incident_description"]
    if desc not in ROOT_CAUSES:
        return desc   # original 500-record descriptions already specific

    detail = enrichment["root_cause_detail"]
    region = str(row.get("network_region", ""))
    tech   = str(row.get("technology_type", ""))
    sev    = str(row.get("severity", "")).capitalize()
    return (f"{desc} — {sev} severity on {tech} in {region}. "
            f"Root cause: {detail}.")


# ── Apply enrichment ──────────────────────────────────────────────────────────
print(f"Enriching {len(df)} records...")

enrichments       = df.apply(enrich_row, axis=1)
enrichment_df     = pd.DataFrame(list(enrichments))

df["root_cause_category"]  = enrichment_df["root_cause_category"].values
df["root_cause_detail"]    = enrichment_df["root_cause_detail"].values
df["fault_component"]      = enrichment_df["fault_component"].values
df["affected_layer"]       = enrichment_df["affected_layer"].values
df["symptom_keywords"]     = enrichment_df["symptom_keywords"].values
df["contributing_factors"] = enrichment_df["contributing_factors"].values

# Enrich descriptions and resolution notes for generic 5G records
df["incident_description"] = df.apply(
    lambda r: enrich_description(r, enrich_row(r)), axis=1)
df["resolution_notes"]     = df.apply(
    lambda r: enrich_resolution(r, enrich_row(r)), axis=1)

# ── Validate ─────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("POST-ENRICHMENT VALIDATION")
print(f"{'='*60}")
print(f"Total records       : {len(df)}")
print(f"Null root_cause_cat : {df['root_cause_category'].isnull().sum()}")
print(f"Null root_cause_det : {df['root_cause_detail'].isnull().sum()}")
print(f"Unique descriptions : {df['incident_description'].nunique()}")
print(f"Unique resolutions  : {df['resolution_notes'].nunique()}")
print(f"\nRoot cause categories:\n{df['root_cause_category'].value_counts().to_string()}")
print(f"\nAffected layers:\n{df['affected_layer'].value_counts().to_string()}")
print(f"\nSample enriched record:")
sample = df[df['alarm_id'] == 'A100000'].iloc[0]
print(f"  description       : {sample['incident_description'][:120]}")
print(f"  root_cause_detail : {sample['root_cause_detail']}")
print(f"  fault_component   : {sample['fault_component']}")
print(f"  affected_layer    : {sample['affected_layer']}")
print(f"  symptom_keywords  : {sample['symptom_keywords']}")
print(f"  resolution_notes  : {sample['resolution_notes']}")

# ── Save ──────────────────────────────────────────────────────────────────────
df.to_csv(OUT, index=False)
import os
print(f"\n✓ Saved: {OUT}  ({os.path.getsize(OUT):,} bytes)")
print(f"  Columns: {list(df.columns)}")
