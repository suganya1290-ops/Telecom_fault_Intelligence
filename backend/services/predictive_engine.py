import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SEVERITY_WEIGHT = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.1}


class PredictiveOutageEngine:
    """
    Predicts outage risk and surfaces early-warning signals from historical
    telecom incident patterns.

    All analysis is purely statistical (pandas / numpy) — no external ML
    service or extra API key is required.
    """

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self._df: Optional[pd.DataFrame] = None
        self._risk: Dict[str, Any] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def load_and_analyze(self) -> None:
        if self._loaded:
            return
        try:
            if not Path(self.dataset_path).exists():
                logger.warning(f"Predictive engine: dataset not found at {self.dataset_path}")
                return

            df = pd.read_csv(self.dataset_path)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"])
            df["severity_weight"] = df["severity"].map(_SEVERITY_WEIGHT).fillna(0.3)
            df["outage_duration"] = pd.to_numeric(df["outage_duration"], errors="coerce").fillna(0)
            df["hour"] = df["timestamp"].dt.hour
            df["day_of_week"] = df["timestamp"].dt.dayofweek  # 0=Monday

            self._df = df
            self._build_risk_matrix()
            self._loaded = True
            logger.info("✓ Predictive engine: analysis complete")
        except Exception as exc:
            logger.error(f"✗ Predictive engine load failed: {exc}")

    def _build_risk_matrix(self) -> None:
        df = self._df

        def _risk_score(grp: pd.DataFrame, total: int) -> float:
            freq = len(grp) / max(total, 1)
            avg_sev = grp["severity_weight"].mean()
            max_dur = df["outage_duration"].max() or 1
            avg_dur = grp["outage_duration"].mean() / max_dur
            return round(0.40 * freq + 0.40 * avg_sev + 0.20 * avg_dur, 4)

        total = len(df)

        # --- Region risk ---
        region_rows = []
        for region, grp in df.groupby("network_region"):
            region_rows.append({
                "region": region,
                "incident_count": len(grp),
                "critical_count": int((grp["severity"] == "critical").sum()),
                "avg_duration": round(float(grp["outage_duration"].mean()), 1),
                "risk_score": _risk_score(grp, total),
            })
        self._risk["by_region"] = {r["region"]: r for r in region_rows}

        # --- Technology risk ---
        tech_rows = []
        for tech, grp in df.groupby("technology_type"):
            tech_rows.append({
                "technology": tech,
                "incident_count": len(grp),
                "avg_duration": round(float(grp["outage_duration"].mean()), 1),
                "risk_score": _risk_score(grp, total),
            })
        self._risk["by_technology"] = {r["technology"]: r for r in tech_rows}

        # --- Vendor risk ---
        vendor_rows = []
        for vendor, grp in df.groupby("device_vendor"):
            vendor_rows.append({
                "vendor": vendor,
                "incident_count": len(grp),
                "avg_duration": round(float(grp["outage_duration"].mean()), 1),
                "risk_score": _risk_score(grp, total),
            })
        self._risk["by_vendor"] = {r["vendor"]: r for r in vendor_rows}

        # --- Hourly pattern (normalised incident rate per hour) ---
        hourly = df.groupby("hour").size() / max(total, 1)
        self._risk["hourly_pattern"] = hourly.to_dict()

        # --- Day-of-week pattern ---
        dow = df.groupby("day_of_week").size() / max(total, 1)
        self._risk["dow_pattern"] = dow.to_dict()

        # --- 30-day rolling window trend ---
        latest = df["timestamp"].max()
        last_30 = len(df[df["timestamp"] >= latest - timedelta(days=30)])
        prev_30 = len(
            df[
                (df["timestamp"] >= latest - timedelta(days=60))
                & (df["timestamp"] < latest - timedelta(days=30))
            ]
        )
        if last_30 > prev_30 * 1.1:
            trend = "increasing"
        elif last_30 < prev_30 * 0.9:
            trend = "decreasing"
        else:
            trend = "stable"
        self._risk["trend"] = trend
        self._risk["last_30_count"] = last_30
        self._risk["prev_30_count"] = prev_30

        # MTBF (mean time between failures) in hours
        days_span = max((latest - df["timestamp"].min()).days, 1)
        self._risk["mtbf_hours"] = round((days_span * 24) / max(total, 1), 1)
        self._risk["total_incidents"] = total

    # ------------------------------------------------------------------
    # Public predictions
    # ------------------------------------------------------------------

    def predict_outage_risk(
        self,
        region: Optional[str] = None,
        technology: Optional[str] = None,
        vendor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return risk predictions optionally scoped to region / technology / vendor."""
        if not self._loaded:
            self.load_and_analyze()
        if not self._loaded:
            return {"error": "Predictive engine unavailable — dataset not found"}

        predictions: List[Dict[str, Any]] = []

        # Region predictions
        region_data = self._risk.get("by_region", {})
        if region and region in region_data:
            rd = region_data[region]
            predictions.append(self._fmt("region", region, rd["risk_score"],
                                         rd["incident_count"], rd["avg_duration"],
                                         rd.get("critical_count", 0)))
        else:
            for reg, rd in sorted(region_data.items(),
                                   key=lambda x: x[1]["risk_score"], reverse=True)[:3]:
                predictions.append(self._fmt("region", reg, rd["risk_score"],
                                             rd["incident_count"], rd["avg_duration"],
                                             rd.get("critical_count", 0)))

        # Technology predictions
        tech_data = self._risk.get("by_technology", {})
        if technology and technology in tech_data:
            td = tech_data[technology]
            predictions.append(self._fmt("technology", technology, td["risk_score"],
                                         td["incident_count"], td["avg_duration"]))
        else:
            for tech, td in sorted(tech_data.items(),
                                    key=lambda x: x[1]["risk_score"], reverse=True)[:2]:
                predictions.append(self._fmt("technology", tech, td["risk_score"],
                                             td["incident_count"], td["avg_duration"]))

        # Current-hour and day-of-week contextual risk
        now = datetime.now()
        hourly = self._risk.get("hourly_pattern", {})
        dow = self._risk.get("dow_pattern", {})
        hour_rate = hourly.get(now.hour, 0)
        dow_rate = dow.get(now.weekday(), 0)
        time_risk = "elevated" if hour_rate > 0.055 or dow_rate > 0.16 else "normal"

        return {
            "predictions": predictions,
            "summary": {
                "total_incidents_analyzed": self._risk.get("total_incidents", 0),
                "mtbf_hours": self._risk.get("mtbf_hours", 0),
                "incident_trend_30d": self._risk.get("trend", "stable"),
                "last_30_days_incidents": self._risk.get("last_30_count", 0),
                "prev_30_days_incidents": self._risk.get("prev_30_count", 0),
                "current_time_risk": time_risk,
                "analysis_timestamp": now.isoformat(),
            },
        }

    def get_high_risk_alerts(self) -> List[Dict[str, Any]]:
        """Return alert entries for any dimension scoring above 0.65."""
        if not self._loaded:
            self.load_and_analyze()
        if not self._loaded:
            return []

        alerts: List[Dict[str, Any]] = []

        for region, rd in self._risk.get("by_region", {}).items():
            if rd["risk_score"] >= 0.65:
                alerts.append({
                    "type": "high_risk_region",
                    "dimension": "region",
                    "value": region,
                    "risk_score": rd["risk_score"],
                    "critical_incidents": rd.get("critical_count", 0),
                    "recommendation": f"Increase monitoring frequency for {region}",
                })

        for tech, td in self._risk.get("by_technology", {}).items():
            if td["risk_score"] >= 0.65:
                alerts.append({
                    "type": "high_risk_technology",
                    "dimension": "technology",
                    "value": tech,
                    "risk_score": td["risk_score"],
                    "recommendation": f"Review {tech} infrastructure health",
                })

        for vendor, vd in self._risk.get("by_vendor", {}).items():
            if vd["risk_score"] >= 0.65:
                alerts.append({
                    "type": "high_risk_vendor",
                    "dimension": "vendor",
                    "value": vendor,
                    "risk_score": vd["risk_score"],
                    "recommendation": f"Audit {vendor} equipment across all sites",
                })

        # Trend-based alert
        if self._risk.get("trend") == "increasing":
            alerts.append({
                "type": "increasing_trend",
                "dimension": "overall",
                "value": "network",
                "risk_score": 0.75,
                "recommendation": "Incident rate is rising — review capacity and maintenance schedule",
            })

        return sorted(alerts, key=lambda a: a["risk_score"], reverse=True)

    def get_risk_by_dimension(self, dimension: str) -> List[Dict[str, Any]]:
        """Return all risk entries for 'region', 'technology', or 'vendor', sorted by risk."""
        if not self._loaded:
            self.load_and_analyze()
        if not self._loaded:
            return []

        key_map = {"region": "by_region", "technology": "by_technology", "vendor": "by_vendor"}
        data = self._risk.get(key_map.get(dimension, ""), {})
        rows = sorted(data.values(), key=lambda x: x["risk_score"], reverse=True)
        for r in rows:
            r["risk_level"] = self._level(r["risk_score"])
        return rows

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(
        dim: str,
        value: str,
        risk_score: float,
        incident_count: int,
        avg_duration: float,
        critical_count: int = 0,
    ) -> Dict[str, Any]:
        return {
            "dimension": dim,
            "value": value,
            "risk_score": risk_score,
            "risk_level": PredictiveOutageEngine._level(risk_score),
            "incident_count": incident_count,
            "avg_outage_minutes": avg_duration,
            "critical_incidents": critical_count,
        }

    @staticmethod
    def _level(score: float) -> str:
        if score >= 0.65:
            return "HIGH"
        if score >= 0.35:
            return "MEDIUM"
        return "LOW"
