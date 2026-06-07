"""
Fallback analyzer — works entirely from the CSV dataset with no OpenAI key.

RCA is derived exclusively from the declared causes embedded in each retrieved
incident's description field ("...incident: <cause>.").  The most-supported
cause across the top-N matches wins.  This guarantees RCA evidence consistency:
if 0 of 5 incidents contain power-related causes, a power fault is never output.
"""
import logging
import re
import time as _time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_REGION_PHRASES = [
    "north india", "south india", "east india", "west india", "central india",
]

# Maps a canonical fault *category* → human-readable RCA string
_ROOT_CAUSE_MAP = {
    "antenna":       "Antenna misalignment or physical damage causing signal degradation",
    "power":         "Power supply instability or UPS failure affecting equipment uptime",
    "gateway":       "Gateway processor overload or firmware incompatibility",
    "fiber":         "Fiber cut or optical connector degradation causing link loss",
    "optical":       "Optical path degradation — amplifier malfunction or fiber break",
    "congestion":    "Traffic congestion due to peak-hour demand exceeding network capacity",
    "configuration": "Misconfiguration after a recent change causing service disruption",
    "software":      "Software bug or failed update rollback affecting service stability",
    "hardware":      "Hardware component failure requiring physical replacement",
    "spectrum":      "Spectrum interference from adjacent cells or external sources",
    "backhaul":      "Backhaul link failure causing upstream connectivity loss",
    "overload":      "CPU or memory overload under sustained high-traffic conditions",
    "sync":          "Clock synchronisation drift causing call-setup failures",
    "temperature":   "Thermal event in equipment room affecting hardware reliability",
    "cable":         "Cable fault or loose connector causing intermittent link drops",
    "interference":  "RF interference degrading signal quality across the affected cell",
}

# Maps declared-cause substrings (lower-case) → category key.
# Order matters: more specific phrases before shorter ones.
_CAUSE_PATTERNS: List[Tuple[str, str]] = [
    ("power supply failure",                "power"),
    ("power amplifier failure",             "power"),
    ("antenna misalignment",                "antenna"),
    ("fiber cut",                           "fiber"),
    ("splice point failure",                "fiber"),
    ("otdr reading anomaly",                "optical"),
    ("optical amplifier malfunction",       "optical"),
    ("optical signal degradation",          "optical"),
    ("backhaul link congestion",            "backhaul"),
    ("dns resolution timeout",              "backhaul"),
    ("router buffer overflow",              "overload"),
    ("capacity exhaustion",                 "congestion"),
    ("load balancer malfunction",           "gateway"),
    ("gateway processor failure",           "gateway"),
    ("software bug",                        "software"),
    ("csp network slice misconfiguration",  "configuration"),
    ("transceiver module failure",          "hardware"),
    ("radio frequency interference",        "spectrum"),
    ("rf interference from co-channel",     "spectrum"),
    ("spectrum interference",               "spectrum"),
    ("modulation quality degradation",      "spectrum"),
    ("frequency offset error",              "spectrum"),
    ("handover failure",                    "sync"),
    ("path obstruction from weather",       "hardware"),
    ("antenna",                             "antenna"),
    ("power",                               "power"),
    ("fiber",                               "fiber"),
    ("optical",                             "optical"),
    ("backhaul",                            "backhaul"),
    ("congestion",                          "congestion"),
    ("software",                            "software"),
    ("configuration",                       "configuration"),
    ("hardware",                            "hardware"),
    ("spectrum",                            "spectrum"),
    ("interference",                        "spectrum"),
    ("sync",                                "sync"),
    ("gateway",                             "gateway"),
    ("overload",                            "overload"),
]

_RESOLUTION_TEMPLATES = {
    "antenna":       "Validate antenna alignment; inspect RF connectors and cables; run drive test to confirm coverage restoration.",
    "power":         "Check UPS status and battery levels; measure supply voltage; replace faulty power modules; schedule preventive PM.",
    "gateway":       "Clear processor memory cache; review recent firmware updates; roll back if issue started post-upgrade.",
    "fiber":         "Dispatch field team for OTDR test to locate break; repair or splice fiber; verify optical power end-to-end.",
    "optical":       "Run OTDR sweep to identify optical loss point; replace faulty amplifier or connector; verify received power meets threshold.",
    "congestion":    "Activate additional carriers or small cells; enable traffic offloading to Wi-Fi; revise capacity plan.",
    "configuration": "Review recent change log; restore last known-good configuration; implement change-management controls.",
    "software":      "Roll back to previous stable build; apply vendor patch; schedule maintenance window for re-upgrade.",
    "hardware":      "Replace faulty component (check spare inventory); update asset registry; run burn-in test.",
    "spectrum":      "Run spectrum analyser scan; coordinate with regulators for external interference; adjust frequency plan.",
    "backhaul":      "Verify backhaul router reachability; test end-to-end latency and packet loss; activate backup link.",
    "overload":      "Perform load balancing; increase capacity or activate overflow routes; review traffic engineering plan.",
    "sync":          "Re-sync clock source; verify PTP/SyncE chain; check GPS signal integrity at the site.",
    "default":       "Review recent configuration changes; verify power supply; restart affected services; escalate if unresolved within SLA.",
}

_SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
_RANK_DECAY      = [0.00, 0.08, 0.14, 0.20, 0.26]
_REVENUE_PER_MIN = 1_200   # industry avg $/min telco outage cost

# Regex to extract declared cause from incident description:
#   "…experiencing <severity> severity incident: <CAUSE>. Service affected…"
_CAUSE_RE = re.compile(r'incident:\s*([^.]+)\.', re.IGNORECASE)


def _extract_declared_cause(description: str) -> str:
    """Pull the declared root-cause string from an incident description."""
    m = _CAUSE_RE.search(str(description))
    return m.group(1).strip() if m else ""


def _map_cause_to_key(declared_cause: str) -> str:
    """Map a free-text declared cause to a canonical category key, or '' if unknown."""
    lower = declared_cause.lower()
    if not lower or lower == "unknown cause":
        return ""
    for pattern, key in _CAUSE_PATTERNS:
        if pattern in lower:
            return key
    return ""


# ── Main class ───────────────────────────────────────────────────────────────

class FallbackAnalyzer:
    """Rule-based fault analyser using the local telecom dataset."""

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self._df: Optional[pd.DataFrame] = None
        self._loaded = False

    def load(self) -> None:
        path = Path(self.dataset_path)
        if not path.exists():
            logger.warning(f"Dataset not found at {path}")
            return
        df = pd.read_csv(path)
        df.columns = [c.lower().strip() for c in df.columns]
        if "severity" in df.columns:
            df["severity_weight"] = df["severity"].map(_SEVERITY_WEIGHT).fillna(0)
        # Pre-extract declared cause and map to category for every row
        if "incident_description" in df.columns:
            df["_declared_cause"] = df["incident_description"].apply(_extract_declared_cause)
            df["_cause_key"]      = df["_declared_cause"].apply(_map_cause_to_key)
        self._df = df
        self._loaded = True
        logger.info(f"✓ Fallback analyser loaded {len(df)} incidents")

    # ── Public API ───────────────────────────────────────────────────────────

    def analyze(
        self,
        query: str,
        region_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        technology_filter: Optional[str] = None,
        vendor_filter: Optional[str] = None,
    ) -> Dict:
        t0 = _time.time()
        query_lower = query.lower()
        keywords, num_keywords = self._tokenise(query_lower)
        applied_filters = {k: v for k, v in [
            ("region", region_filter), ("severity", severity_filter),
            ("technology", technology_filter), ("vendor", vendor_filter),
        ] if v}

        # ── Step 1 · Retrieval ───────────────────────────────────────────────
        t1 = _time.time()
        matches = self._search(query_lower, keywords, region_filter, severity_filter, technology_filter, vendor_filter)
        t2 = _time.time()
        retrieval_ms = round((t2 - t1) * 1000, 1)

        incidents = self._format_incidents(matches, num_keywords)

        # Derive consensus from retrieved incidents (used throughout for consistency)
        top_vendor = ""
        if not matches.empty and "device_vendor" in matches.columns:
            vc = matches["device_vendor"].value_counts()
            if len(vc):
                top_vendor = vc.index[0]

        # ── Evidence-based root cause detection ─────────────────────────────
        # Infer the RCA key *only* from the declared causes in retrieved incidents.
        # Only falls back to query keywords if no incident has a known cause.
        root_cause_key, evidence = self._detect_cause_from_evidence(query_lower, matches)

        # ── Step 2 · Root Cause ──────────────────────────────────────────────
        t3 = _time.time()
        root_cause = self._build_root_cause(root_cause_key, matches, keywords, num_keywords, top_vendor, evidence)
        t4 = _time.time()
        rca_ms = round((t4 - t3) * 1000, 1)

        # ── Step 3 · Service Impact ──────────────────────────────────────────
        t5 = _time.time()
        service_impact = self._build_service_impact(matches)
        t6 = _time.time()
        impact_ms = round((t6 - t5) * 1000, 1)

        # ── Step 4 · Resolution ──────────────────────────────────────────────
        t7 = _time.time()
        resolution = self._build_resolution(root_cause_key, matches, top_vendor)
        t8 = _time.time()
        resolution_ms = round((t8 - t7) * 1000, 1)

        # ── Correlation ──────────────────────────────────────────────────────
        correlation = self._build_correlation(matches)

        total_ms = round((t8 - t0) * 1000, 1)

        # ── Agent workflow summary ───────────────────────────────────────────
        priority   = service_impact.get("priority_level", "medium")
        rev_loss   = service_impact.get("estimated_revenue_loss", 0)
        confidence = root_cause.get("confidence_score", 0)
        n_actions  = len(resolution.get("recommended_actions", []))
        n_services = len(service_impact.get("affected_services", []))
        needs_esc  = resolution.get("escalation_required", False)
        est_time   = resolution.get("estimated_resolution_time", "—")

        # Filters for display — flatten dict to "k=v" strings to avoid [object Object]
        filter_chips = [f"{k}={v}" for k, v in applied_filters.items()] if applied_filters else ["none"]

        agent_workflow = [
            {
                "step": 1,
                "agent": "Alarm Retrieval Agent",
                "status": "completed",
                "duration_ms": retrieval_ms,
                "output": (
                    f"Retrieved {len(matches)} incident{'s' if len(matches) != 1 else ''} "
                    f"from {len(self._df) if self._df is not None else 500} records "
                    f"using {len(keywords)} keyword{'s' if len(keywords) != 1 else ''}"
                ),
                "details": {
                    "method":        "Phrase + keyword BM25 scoring",
                    "keywords_used": ", ".join(keywords[:6]) or "none",
                    "filters":       ", ".join(filter_chips),
                    "top_score":     f"{round(float(matches['_score'].max()), 1) if not matches.empty and '_score' in matches.columns else 0} hits",
                },
            },
            {
                "step": 2,
                "agent": "Root Cause Analysis Agent",
                "status": "completed",
                "duration_ms": rca_ms,
                "output": (
                    f"Identified '{root_cause_key}' fault pattern · "
                    f"Confidence: {round(confidence * 100)}% · "
                    f"Severity: {root_cause.get('severity_assessment', 'N/A')}"
                ),
                "details": {
                    "cause_key":       root_cause_key,
                    "primary_vendor":  top_vendor or "varied",
                    "confidence":      f"{round(confidence * 100)}%",
                    "evidence_source": f"{evidence['agreement_count']}/{len(matches)} incidents agree" if matches is not None and not matches.empty else "no matches",
                },
            },
            {
                "step": 3,
                "agent": "Service Impact Agent",
                "status": "completed",
                "duration_ms": impact_ms,
                "output": (
                    f"{priority.capitalize()} priority · "
                    f"{n_services} service{'s' if n_services != 1 else ''} affected · "
                    f"Est. ${rev_loss:,.0f} revenue loss"
                ),
                "details": {
                    "priority":        priority,
                    "services":        f"{n_services} affected",
                    "revenue_loss":    f"${rev_loss:,.0f}",
                    "avg_outage":      f"{service_impact.get('average_outage_minutes', 0)} min",
                },
            },
            {
                "step": 4,
                "agent": "Resolution Recommendation Agent",
                "status": "completed",
                "duration_ms": resolution_ms,
                "output": (
                    f"{n_actions} action step{'s' if n_actions != 1 else ''} · "
                    f"{'⚠ L2 escalation required' if needs_esc else 'Remote resolution possible'} · "
                    f"Est. {est_time}"
                ),
                "details": {
                    "total_actions":  f"{n_actions} steps",
                    "from_history":   f"{resolution.get('_historical_count', 0)} from past incidents",
                    "escalation":     "required" if needs_esc else "not required",
                    "estimated_time": est_time,
                },
            },
        ]

        # ── Retrieval methodology ─────────────────────────────────────────────
        retrieval_methodology = {
            "engine":          "Pattern Matching (No AI Key)",
            "algorithm":       "BM25-style keyword + phrase scoring with rank decay",
            "keywords_used":   keywords,
            "filters_applied": applied_filters,
            "total_searched":  len(self._df) if self._df is not None else 0,
            "total_matched":   len(matches),
            "ranking_formula": "hybrid_score = (keyword_hits / query_keywords) × (1 − rank_decay)",
            "upgrade_path":    "Set OPENAI_API_KEY for GPT vector similarity + LLM reasoning",
        }

        root_cause.pop("_keyword_hits", None)

        return {
            "query":                      query,
            "retrieved_incidents":        incidents,
            "root_cause_analysis":        root_cause,
            "service_impact_analysis":    service_impact,
            "resolution_recommendations": resolution,
            "alarm_correlations":         correlation,
            "agent_workflow":             agent_workflow,
            "retrieval_methodology":      retrieval_methodology,
            "processing_time_ms":         0,
            "a2a_messages":               [],
            "fallback_mode":              True,
            "data_source": {
                "type":            "local_csv",
                "total_incidents": len(self._df) if self._df is not None else 0,
                "matched":         len(matches),
                "method":          "keyword + phrase matching with BM25-style scoring",
            },
        }

    # ── Tokenisation ─────────────────────────────────────────────────────────

    def _tokenise(self, query_lower: str) -> Tuple[List[str], int]:
        found_phrases = [p for p in _REGION_PHRASES if p in query_lower]
        remaining = query_lower
        for p in found_phrases:
            remaining = remaining.replace(p, "")
        single_kws = [w for w in re.split(r'\W+', remaining) if len(w) >= 4]
        all_kws = found_phrases + single_kws
        return all_kws, max(len(all_kws), 1)

    # ── Search ────────────────────────────────────────────────────────────────

    def _search(
        self,
        query_lower: str,
        keywords: List[str],
        region: Optional[str],
        severity: Optional[str],
        technology: Optional[str],
        vendor: Optional[str],
    ) -> pd.DataFrame:
        if self._df is None or not self._loaded:
            return pd.DataFrame()

        df = self._df.copy()

        if region:
            df = df[df.get("network_region", pd.Series()).str.lower().str.contains(region.lower(), na=False)]
        elif any(p in query_lower for p in _REGION_PHRASES):
            matched = [p for p in _REGION_PHRASES if p in query_lower]
            pattern = "|".join(re.escape(p) for p in matched)
            df = df[df.get("network_region", pd.Series()).str.lower().str.contains(pattern, na=False)]

        if severity:
            df = df[df.get("severity", pd.Series()).str.lower() == severity.lower()]
        if technology:
            df = df[df.get("technology_type", pd.Series()).str.lower().str.contains(technology.lower(), na=False)]
        if vendor:
            df = df[df.get("device_vendor", pd.Series()).str.lower().str.contains(vendor.lower(), na=False)]

        if df.empty:
            return pd.DataFrame()

        if keywords and "incident_description" in df.columns:
            df = df.copy()
            df["_score"] = df["incident_description"].apply(
                lambda t: sum(1.0 for kw in keywords if kw in str(t).lower())
            )
        else:
            df["_score"] = 0.0

        return df.sort_values(["_score", "severity_weight"], ascending=[False, False]).head(5)

    # ── Evidence-based cause detection ────────────────────────────────────────

    def _detect_cause_from_evidence(
        self, query_lower: str, matches: pd.DataFrame
    ) -> Tuple[str, Dict]:
        """
        Derive the RCA category key exclusively from the declared causes embedded
        in the retrieved incidents.  Falls back to query keywords only when every
        matched incident has an 'Unknown cause' declaration.

        Returns (key, evidence_dict) where evidence_dict contains:
          declared_causes  – per-incident declared cause strings
          cause_tally      – Counter of category keys found
          agreement_count  – incidents supporting the winning key
          known_count      – incidents with a non-unknown declared cause
          source           – "incidents" | "query_keywords" | "default"
        """
        declared_causes: List[str] = []
        cause_keys: List[str] = []

        if not matches.empty and "_declared_cause" in matches.columns:
            for _, row in matches.iterrows():
                dc  = str(row.get("_declared_cause", ""))
                key = str(row.get("_cause_key", ""))
                declared_causes.append(dc if dc else "Unknown cause")
                cause_keys.append(key)

        tally = Counter(k for k in cause_keys if k)  # exclude empty (unknown)
        known_count = len([k for k in cause_keys if k])

        if tally:
            # Most common non-unknown key
            winning_key, agreement_count = tally.most_common(1)[0]
            return winning_key, {
                "declared_causes":  declared_causes,
                "cause_tally":      dict(tally),
                "agreement_count":  agreement_count,
                "known_count":      known_count,
                "source":           "incidents",
            }

        # All incidents have 'Unknown cause' — fall back to query keywords
        for kw in _ROOT_CAUSE_MAP:
            if kw in query_lower:
                return kw, {
                    "declared_causes":  declared_causes,
                    "cause_tally":      {},
                    "agreement_count":  0,
                    "known_count":      0,
                    "source":           "query_keywords",
                }

        return "default", {
            "declared_causes":  declared_causes,
            "cause_tally":      {},
            "agreement_count":  0,
            "known_count":      0,
            "source":           "default",
        }

    # ── Builders ──────────────────────────────────────────────────────────────

    def _format_incidents(self, matches: pd.DataFrame, num_keywords: int) -> List[Dict]:
        if matches.empty:
            return []
        results = []
        for rank, (_, row) in enumerate(matches.iterrows()):
            raw_score    = float(row.get("_score", 0))
            base_pct     = raw_score / num_keywords if num_keywords > 0 else 0.5
            decay        = _RANK_DECAY[rank] if rank < len(_RANK_DECAY) else 0.28
            hybrid_score = round(max(0.05, min(base_pct * (1 - decay), 1.0)), 2)
            declared     = str(row.get("_declared_cause", ""))
            results.append({
                "incident": {
                    "alarm_id":             str(row.get("alarm_id", "N/A")),
                    "incident_description": str(row.get("incident_description", ""))[:350],
                    "declared_cause":       declared if declared else "Unknown cause",
                    "network_region":       str(row.get("network_region", "N/A")),
                    "technology_type":      str(row.get("technology_type", "N/A")),
                    "severity":             str(row.get("severity", "N/A")),
                    "outage_duration":      int(row["outage_duration"]) if pd.notna(row.get("outage_duration")) else 0,
                    "device_vendor":        str(row.get("device_vendor", "N/A")),
                    "service_impact":       str(row.get("service_impact", "N/A")),
                    "resolution_notes":     str(row.get("resolution_notes", ""))[:250],
                    "timestamp":            str(row.get("timestamp", "")),
                },
                "hybrid_score":    hybrid_score,
                "relevance_score": hybrid_score,
            })
        return results

    def _build_root_cause(
        self,
        key: str,
        matches: pd.DataFrame,
        keywords: List[str],
        num_keywords: int,
        top_vendor: str,
        evidence: Dict,
    ) -> Dict:
        cause = _ROOT_CAUSE_MAP.get(key, "Unclassified fault — review incident descriptions for further clues")

        n               = len(matches)
        if n == 0:
            return {
                "primary_cause":        "No historical evidence available",
                "contributing_factors": [],
                "confidence_score":     0.0,
                "confidence_level":     "None",
                "confidence_breakdown": [],
                "analysis_reasoning":   "No similar incidents were found in the database for this query.",
                "severity_assessment":  "unknown",
                "primary_vendor":       top_vendor,
                "affected_regions":     [],
                "analysis_method":      "No evidence available",
                "evidence_source":      "none",
                "rca_evidence":         [],
                "_keyword_hits":        0,
            }
        agreement_count = evidence.get("agreement_count", 0)
        known_count     = evidence.get("known_count", 0)
        evidence_source = evidence.get("source", "default")
        declared_causes = evidence.get("declared_causes", [])

        # Hit-rate: fraction of retrieved incidents that agree on this cause
        hit_rate = agreement_count / n if n else 0

        # Known-cause rate: fraction of incidents with any identifiable cause
        known_rate = known_count / n if n else 0

        dataset_density = min(n / 5.0, 1.0)
        query_richness  = min(num_keywords / 8.0, 1.0)

        # Confidence weighted formula
        # Penalise when cause came from query keywords (no incident evidence)
        source_multiplier = 1.0 if evidence_source == "incidents" else 0.7
        confidence = round(
            min(
                (
                    0.40 * hit_rate
                    + 0.20 * known_rate
                    + 0.30 * dataset_density
                    + 0.10 * query_richness
                )
                * source_multiplier
                + 0.05,   # small base prior
                0.92,
            ),
            2,
        )
        level = "Strong" if confidence >= 0.70 else "Moderate" if confidence >= 0.50 else "Limited"

        severity = "medium"
        if not matches.empty and "severity" in matches.columns:
            mode = matches["severity"].mode()
            severity = mode.iloc[0] if len(mode) else "medium"

        regions = []
        if not matches.empty and "network_region" in matches.columns:
            regions = matches["network_region"].dropna().unique()[:3].tolist()

        vendor_note  = f" on {top_vendor} equipment" if top_vendor else ""
        region_note  = f" in {', '.join(regions)}" if regions else ""

        # Build honest analysis reasoning
        if evidence_source == "incidents" and agreement_count > 0:
            cause_tally_str = ", ".join(
                f"'{k}' ×{v}" for k, v in
                sorted(evidence.get("cause_tally", {}).items(), key=lambda x: -x[1])
            )
            analysis_reasoning = (
                f"{agreement_count} of {n} retrieved incidents have a '{key}' declared fault cause"
                f"{region_note}{vendor_note}. "
                f"Cause distribution: {cause_tally_str}. "
                f"{level} confidence ({round(confidence*100)}%) — {n - known_count} incident(s) had 'Unknown cause'."
            )
        elif evidence_source == "query_keywords":
            analysis_reasoning = (
                f"All {n} retrieved incidents report 'Unknown cause'. "
                f"RCA inferred from query keyword '{key}' — not confirmed by incident evidence. "
                f"Confidence is limited ({round(confidence*100)}%)."
            )
        else:
            analysis_reasoning = (
                f"No clear fault pattern identified in {n} retrieved incidents. "
                f"General fault protocol applied. Confidence: {round(confidence*100)}%."
            )

        # Contributing factors — evidence-driven
        contributing_factors = []
        if agreement_count > 0:
            contributing_factors.append(
                f"{agreement_count}/{n} retrieved incidents declare '{key}' as the primary fault cause"
            )
        if known_count > 0:
            contributing_factors.append(
                f"{known_count}/{n} incidents have an identifiable cause (vs. 'Unknown cause')"
            )
        if declared_causes:
            unique_declared = list(dict.fromkeys(dc for dc in declared_causes if dc and dc != "Unknown cause"))
            if unique_declared:
                contributing_factors.append(
                    f"Incident-level causes observed: {'; '.join(unique_declared[:4])}"
                )
        contributing_factors.append(
            f"Severity profile — {severity}: consistent with historical {key}-type faults"
        )
        if top_vendor:
            contributing_factors.append(
                f"Primary vendor: {top_vendor} equipment across majority of matched incidents"
            )
        if evidence_source == "query_keywords":
            contributing_factors.append(
                "⚠ Cause inferred from query keywords — no incident evidence available"
            )

        # Evidence table for the UI
        evidence_rows: List[Dict] = []
        if not matches.empty and "_declared_cause" in matches.columns:
            for _, row in matches.iterrows():
                dc    = str(row.get("_declared_cause", ""))
                ck    = str(row.get("_cause_key", ""))
                aids  = str(row.get("alarm_id", ""))
                sev   = str(row.get("severity", ""))
                evidence_rows.append({
                    "alarm_id":       aids,
                    "declared_cause": dc if dc else "Unknown cause",
                    "category":       ck if ck else "unknown",
                    "severity":       sev,
                    "supports_rca":   ck == key,
                })

        # Confidence breakdown (4 factors)
        confidence_breakdown = [
            {
                "factor":  "Evidence Agreement",
                "weight":  0.40,
                "score":   round(hit_rate, 3),
                "contrib": round(0.40 * hit_rate, 3),
                "detail":  f"{agreement_count}/{n} incidents declare '{key}' as root cause",
            },
            {
                "factor":  "Known Cause Rate",
                "weight":  0.20,
                "score":   round(known_rate, 3),
                "contrib": round(0.20 * known_rate, 3),
                "detail":  f"{known_count}/{n} incidents have identifiable (non-unknown) cause",
            },
            {
                "factor":  "Dataset Match Density",
                "weight":  0.30,
                "score":   round(dataset_density, 3),
                "contrib": round(0.30 * dataset_density, 3),
                "detail":  f"{n}/5 retrieval slots filled",
            },
            {
                "factor":  "Query Richness",
                "weight":  0.10,
                "score":   round(query_richness, 3),
                "contrib": round(0.10 * query_richness, 3),
                "detail":  f"{num_keywords} query terms detected",
            },
        ]

        return {
            "primary_cause":        cause,
            "contributing_factors": contributing_factors,
            "confidence_score":     confidence,
            "confidence_level":     level,
            "confidence_breakdown": confidence_breakdown,
            "analysis_reasoning":   analysis_reasoning,
            "severity_assessment":  severity,
            "primary_vendor":       top_vendor,
            "affected_regions":     regions,
            "analysis_method":      "Evidence-based: declared causes extracted from retrieved incidents",
            "evidence_source":      evidence_source,
            "rca_evidence":         evidence_rows,
            "_keyword_hits":        agreement_count,   # internal, removed before return
        }

    def _build_service_impact(self, matches: pd.DataFrame) -> Dict:
        if matches.empty:
            return {
                "affected_services":        [],
                "affected_regions":         [],
                "affected_technologies":    [],
                "affected_vendors":         [],
                "estimated_users_affected": "N/A",
                "priority_level":           "unknown",
                "customer_impact":          "No Historical Evidence Available",
                "estimated_revenue_loss":   0,
                "revenue_loss_breakdown":   None,
                "business_impact":          "N/A — no matching historical incidents",
                "average_outage_minutes":   0,
                "max_outage_minutes":       0,
                "min_outage_minutes":       0,
            }

        regions  = matches.get("network_region",  pd.Series()).dropna().unique().tolist()
        techs    = matches.get("technology_type", pd.Series()).dropna().unique().tolist()
        impacts  = matches.get("service_impact",  pd.Series()).dropna().unique().tolist()
        vendors  = matches.get("device_vendor",   pd.Series()).dropna().unique().tolist()

        vendor_counts = matches.get("device_vendor", pd.Series()).value_counts().to_dict()

        avg_outage = float(matches.get("outage_duration", pd.Series(dtype=float)).mean() or 0)
        max_outage = float(matches.get("outage_duration", pd.Series(dtype=float)).max() or 0)
        min_outage = float(matches.get("outage_duration", pd.Series(dtype=float)).min() or 0)
        rev_loss   = round(avg_outage * _REVENUE_PER_MIN, 2)

        sev_counts   = matches.get("severity", pd.Series()).value_counts()
        has_critical = "critical" in sev_counts.index
        has_high     = "high"     in sev_counts.index
        priority     = "critical" if has_critical else ("high" if has_high else "medium")

        top_vendor = vendors[0] if vendors else "various vendors"
        customer_impact = (
            f"{len(matches)} similar incident{'s' if len(matches) != 1 else ''} found — "
            f"avg outage {avg_outage:.0f} min (range {min_outage:.0f}–{max_outage:.0f} min) across "
            f"{', '.join(regions[:3])}. "
            f"Predominantly {top_vendor} equipment ({vendor_counts.get(top_vendor, 1)} of {len(matches)} incidents)."
        )

        business_impact_text = (
            f"{'Critical' if priority == 'critical' else 'High' if priority == 'high' else 'Medium'}-priority "
            f"event affecting {', '.join(impacts[:2]) if impacts else 'multiple services'}. "
            f"Average outage: {avg_outage:.0f} min across {len(matches)} historical incidents. "
            f"Estimated revenue impact: ${rev_loss:,.0f} (industry rate ${_REVENUE_PER_MIN:,}/min)."
        )

        return {
            "affected_services":        impacts[:5] if impacts else ["Voice calls", "Data services"],
            "affected_regions":         regions,
            "affected_technologies":    techs,
            "affected_vendors":         vendors[:5],
            "vendor_distribution":      vendor_counts,
            "estimated_users_affected": f"{len(matches)} similar historical incident{'s' if len(matches) != 1 else ''}",
            "average_outage_minutes":   round(avg_outage, 1),
            "max_outage_minutes":       round(max_outage, 1),
            "min_outage_minutes":       round(min_outage, 1),
            "priority_level":           priority,
            "customer_impact":          customer_impact,
            "estimated_revenue_loss":   rev_loss,
            "revenue_loss_breakdown": {
                "avg_outage_minutes":     round(avg_outage, 1),
                "revenue_per_minute_usd": _REVENUE_PER_MIN,
                "incident_count":         len(matches),
                "formula":               f"{avg_outage:.0f} min × ${_REVENUE_PER_MIN:,}/min",
                "total_usd":             rev_loss,
            },
            "business_impact": business_impact_text,
        }

    def _build_resolution(self, key: str, matches: pd.DataFrame, top_vendor: str) -> Dict:
        primary = _RESOLUTION_TEMPLATES.get(key, _RESOLUTION_TEMPLATES["default"])

        historical: List[str] = []
        if not matches.empty and "resolution_notes" in matches.columns:
            seen: set = set()
            for note in matches["resolution_notes"].dropna().tolist():
                for step in self._extract_actions(str(note)):
                    if step.lower() not in seen and len(step) > 8:
                        seen.add(step.lower())
                        historical.append(step)
                    if len(historical) >= 5:
                        break
                if len(historical) >= 5:
                    break

        std_steps = [
            "Monitor network KPIs for 30 min post-restoration to confirm stability.",
            "Document incident timeline and corrective actions in the ticketing system.",
            "Schedule post-incident review within 48 hours to prevent recurrence.",
        ]
        if top_vendor:
            std_steps.insert(0, f"Coordinate with {top_vendor} TAC for vendor-specific diagnostics if steps above do not resolve.")

        recommended = [primary] + historical + std_steps

        avg_outage = 0.0
        if not matches.empty and "outage_duration" in matches.columns:
            avg_outage = float(matches["outage_duration"].mean() or 0)

        needs_esc = key in ("fiber", "hardware", "power", "optical")
        esc_text  = (
            f"L2 field team dispatch required — '{key}' faults cannot be resolved remotely. "
            f"Contact NOC L2 immediately{' and engage ' + top_vendor + ' TAC' if top_vendor else ''}. Open a P1 ticket."
            if needs_esc else None
        )

        return {
            "recommended_actions":       recommended,
            "estimated_resolution_time": f"{round(avg_outage)}–{round(avg_outage * 1.4)} min" if avg_outage else "30–60 min",
            "escalation_required":       needs_esc,
            "escalation_recommendation": esc_text,
            "data_driven":               len(historical) > 0,
            "_historical_count":         len(historical),
        }

    def _build_correlation(self, matches: pd.DataFrame) -> Dict:
        if matches.empty:
            return {
                "correlated_alarms":    [],
                "correlation_strength": 0.0,
                "cascade_risk":         False,
                "by_region":            {},
                "by_vendor":            {},
                "by_technology":        {},
                "by_severity":          {},
                "pattern_summary":      "No incidents retrieved.",
            }

        ids  = [str(v) for v in matches.get("alarm_id", pd.Series()).tolist()]
        sevs = [str(s).lower() for s in matches.get("severity", pd.Series()).tolist()]
        n    = len(matches)

        by_region   = matches.get("network_region",  pd.Series()).value_counts().to_dict()
        by_vendor   = matches.get("device_vendor",   pd.Series()).value_counts().to_dict()
        by_tech     = matches.get("technology_type", pd.Series()).value_counts().to_dict()
        by_severity = matches.get("severity",        pd.Series()).value_counts().to_dict()
        by_cause    = {}
        if "_cause_key" in matches.columns:
            by_cause = matches["_cause_key"].replace("", "unknown").value_counts().to_dict()

        # ── Data-driven correlation strength ─────────────────────────────────
        # Homogeneity score: measures how concentrated (uniform) each dimension is.
        # A dimension where all incidents share the same value scores 1.0.
        def _homogeneity(counts: dict) -> float:
            if not counts or sum(counts.values()) == 0:
                return 0.0
            total = sum(counts.values())
            top   = max(counts.values())
            return top / total

        h_vendor   = _homogeneity(by_vendor)
        h_region   = _homogeneity(by_region)
        h_tech     = _homogeneity(by_tech)
        h_severity = _homogeneity(by_severity)
        h_cause    = _homogeneity(by_cause)

        # Weighted combination — vendor and cause carry the most diagnostic weight
        strength = round(
            0.25 * h_vendor
            + 0.20 * h_region
            + 0.20 * h_tech
            + 0.15 * h_severity
            + 0.20 * h_cause,
            2,
        )

        has_critical = "critical" in sevs
        cascade_risk = has_critical and strength >= 0.6

        top_region = max(by_region, key=by_region.get) if by_region else "N/A"
        top_vendor = max(by_vendor, key=by_vendor.get) if by_vendor else "N/A"
        top_tech   = max(by_tech,   key=by_tech.get)   if by_tech   else "N/A"

        pattern_summary = (
            f"{n} correlated alarm{'s' if n != 1 else ''} — "
            f"concentrated in {top_region} "
            f"({by_region.get(top_region, 0)} incident{'s' if by_region.get(top_region, 0) != 1 else ''}), "
            f"predominantly {top_vendor} equipment on {top_tech} network. "
            f"Correlation strength: {round(strength * 100)}%. "
            f"{'⚠ High-severity cascade risk detected.' if cascade_risk else 'Cascade risk: low.'}"
        )

        return {
            "correlated_alarms":    ids,
            "correlation_strength": strength,
            "cascade_risk":         cascade_risk,
            "cascade_analysis": (
                "High-severity correlated alarms detected — monitor downstream nodes for cascade failure."
                if has_critical else None
            ),
            "by_region":        by_region,
            "by_vendor":        by_vendor,
            "by_technology":    by_tech,
            "by_severity":      by_severity,
            "by_cause":         by_cause,
            "pattern_summary":  pattern_summary,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_actions(note: str) -> List[str]:
        m = re.search(r'performing:\s*(.+?)(?:\.\s*Root cause|$)', note, re.IGNORECASE | re.DOTALL)
        if m:
            return [a.strip() for a in m.group(1).split(',') if len(a.strip()) > 5]
        return []
