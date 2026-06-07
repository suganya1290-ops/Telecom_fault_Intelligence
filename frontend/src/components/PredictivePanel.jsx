import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import { FiAlertTriangle, FiTrendingUp, FiTrendingDown, FiMinus, FiRefreshCw } from 'react-icons/fi';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const RISK_COLOR = { HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#22c55e' };
const RISK_BG   = { HIGH: 'bg-red-900/20 border-red-700', MEDIUM: 'bg-yellow-900/20 border-yellow-700', LOW: 'bg-green-900/20 border-green-700' };

function TrendIcon({ trend }) {
  if (trend === 'increasing') return <FiTrendingUp className="text-red-400" />;
  if (trend === 'decreasing') return <FiTrendingDown className="text-green-400" />;
  return <FiMinus className="text-slate-400" />;
}

function RiskBadge({ level }) {
  const colours = { HIGH: 'text-red-400 bg-red-900/30', MEDIUM: 'text-yellow-400 bg-yellow-900/30', LOW: 'text-green-400 bg-green-900/30' };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold ${colours[level] ?? colours.LOW}`}>
      {level}
    </span>
  );
}

export default function PredictivePanel() {
  const [riskData, setRiskData]     = useState(null);
  const [alerts, setAlerts]         = useState([]);
  const [dimension, setDimension]   = useState('region');
  const [dimData, setDimData]       = useState([]);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [riskRes, alertRes, dimRes] = await Promise.all([
        axios.get(`${API_BASE}/predict/outage-risk`),
        axios.get(`${API_BASE}/predict/high-risk-alerts`),
        axios.get(`${API_BASE}/predict/risk-by-dimension?dimension=${dimension}`),
      ]);
      setRiskData(riskRes.data);
      setAlerts(alertRes.data.alerts ?? []);
      setDimData(dimRes.data.data ?? []);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Failed to load predictions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const fetchDimension = async (dim) => {
    setDimension(dim);
    try {
      const res = await axios.get(`${API_BASE}/predict/risk-by-dimension?dimension=${dim}`);
      setDimData(res.data.data ?? []);
    } catch {/* silent */ }
  };

  const summary = riskData?.summary;
  const predictions = riskData?.predictions ?? [];

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Predictive Outage Intelligence</h2>
          <p className="text-slate-400 text-sm mt-0.5">
            Statistical risk analysis from historical incident patterns — no external ML service required
          </p>
        </div>
        <button
          onClick={fetchAll}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          <FiRefreshCw className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-900/20 border border-red-700 rounded-lg text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Summary KPIs */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-slate-400 text-xs uppercase tracking-wide">Incidents Analysed</p>
            <p className="text-2xl font-bold text-white mt-1">{summary.total_incidents_analyzed}</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-slate-400 text-xs uppercase tracking-wide">MTBF</p>
            <p className="text-2xl font-bold text-white mt-1">{summary.mtbf_hours}h</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-slate-400 text-xs uppercase tracking-wide">30-day Trend</p>
            <div className="flex items-center gap-2 mt-1">
              <TrendIcon trend={summary.incident_trend_30d} />
              <p className={`text-lg font-semibold capitalize ${summary.incident_trend_30d === 'increasing' ? 'text-red-400' : summary.incident_trend_30d === 'decreasing' ? 'text-green-400' : 'text-slate-300'}`}>
                {summary.incident_trend_30d}
              </p>
            </div>
          </div>
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-slate-400 text-xs uppercase tracking-wide">Current Hour Risk</p>
            <p className={`text-lg font-semibold mt-1 capitalize ${summary.current_time_risk === 'elevated' ? 'text-yellow-400' : 'text-green-400'}`}>
              {summary.current_time_risk}
            </p>
          </div>
        </div>
      )}

      {/* High-risk alerts */}
      {alerts.length > 0 && (
        <div className="bg-slate-800 rounded-lg p-5">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
            <FiAlertTriangle className="text-yellow-400" />
            High-Risk Alerts ({alerts.length})
          </h3>
          <div className="space-y-2">
            {alerts.map((alert, i) => (
              <div key={i} className={`border rounded-lg p-3 ${RISK_BG[alert.risk_level] ?? RISK_BG.LOW}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-white font-medium text-sm capitalize">{alert.dimension}: </span>
                    <span className="text-slate-200 text-sm">{alert.value}</span>
                    <p className="text-slate-400 text-xs mt-1">{alert.recommendation}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <RiskBadge level={alert.risk_level ?? (alert.risk_score >= 0.65 ? 'HIGH' : 'MEDIUM')} />
                    <span className="text-slate-400 text-xs">{(alert.risk_score * 100).toFixed(0)}% risk</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risk bar chart by dimension */}
      <div className="bg-slate-800 rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold">Risk Score by Dimension</h3>
          <div className="flex gap-2">
            {['region', 'technology', 'vendor'].map(dim => (
              <button
                key={dim}
                onClick={() => fetchDimension(dim)}
                className={`px-3 py-1 rounded text-sm transition-colors capitalize ${dimension === dim ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}
              >
                {dim}
              </button>
            ))}
          </div>
        </div>

        {dimData.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dimData} layout="vertical" margin={{ left: 10, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" domain={[0, 1]} tickFormatter={v => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey={dimension === 'region' ? 'region' : dimension === 'technology' ? 'technology' : 'vendor'}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                width={90}
              />
              <Tooltip
                formatter={(v) => [`${(v * 100).toFixed(1)}%`, 'Risk Score']}
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Bar dataKey="risk_score" radius={[0, 4, 4, 0]}>
                {dimData.map((entry, i) => (
                  <Cell key={i} fill={RISK_COLOR[entry.risk_level] ?? '#3b82f6'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-40 text-slate-500 text-sm">
            {loading ? 'Loading…' : 'No data available'}
          </div>
        )}
      </div>

      {/* Top risk predictions table */}
      {predictions.length > 0 && (
        <div className="bg-slate-800 rounded-lg p-5">
          <h3 className="text-white font-semibold mb-3">Top Risk Predictions</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 text-xs uppercase border-b border-slate-700">
                  <th className="pb-2 text-left">Dimension</th>
                  <th className="pb-2 text-left">Value</th>
                  <th className="pb-2 text-right">Risk Score</th>
                  <th className="pb-2 text-right">Level</th>
                  <th className="pb-2 text-right">Incidents</th>
                  <th className="pb-2 text-right">Avg Outage</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map((p, i) => (
                  <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="py-2 text-slate-400 capitalize">{p.dimension}</td>
                    <td className="py-2 text-white font-medium">{p.value}</td>
                    <td className="py-2 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 bg-slate-700 rounded-full h-1.5">
                          <div
                            className="h-1.5 rounded-full"
                            style={{ width: `${p.risk_score * 100}%`, backgroundColor: RISK_COLOR[p.risk_level] ?? '#3b82f6' }}
                          />
                        </div>
                        <span className="text-slate-300 w-10 text-right">{(p.risk_score * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="py-2 text-right"><RiskBadge level={p.risk_level} /></td>
                    <td className="py-2 text-right text-slate-300">{p.incident_count}</td>
                    <td className="py-2 text-right text-slate-300">{p.avg_outage_minutes}m</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
