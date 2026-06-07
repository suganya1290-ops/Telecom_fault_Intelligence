import React, { useState } from 'react';
import {
  FiChevronDown, FiChevronUp, FiAlertTriangle, FiTrendingUp,
  FiClock, FiCheckCircle, FiDatabase, FiZap, FiMapPin, FiWifi,
  FiShield, FiInfo, FiAlertCircle, FiSearch, FiCpu, FiActivity,
  FiFileText, FiMessageSquare, FiArrowRight,
} from 'react-icons/fi';

// ── Style maps ────────────────────────────────────────────────────────────────

const SEV = {
  critical: { badge: 'bg-red-900/40 text-red-300 border-red-600',         bar: 'bg-red-500'    },
  high:     { badge: 'bg-orange-900/40 text-orange-300 border-orange-600', bar: 'bg-orange-500' },
  medium:   { badge: 'bg-yellow-900/40 text-yellow-300 border-yellow-600', bar: 'bg-yellow-500' },
  low:      { badge: 'bg-green-900/40 text-green-300 border-green-600',    bar: 'bg-green-500'  },
  info:     { badge: 'bg-cyan-900/40 text-cyan-300 border-cyan-600',       bar: 'bg-cyan-500'   },
};

const PRIORITY_COLOR = {
  critical: 'text-red-400', high: 'text-orange-400',
  medium:   'text-yellow-400', low: 'text-green-400',
  unknown:  'text-slate-400',
};

const AGENT_ICONS = [
  <FiSearch className="w-4 h-4" />,
  <FiCpu className="w-4 h-4" />,
  <FiShield className="w-4 h-4" />,
  <FiCheckCircle className="w-4 h-4" />,
];

/** Safely convert any value to a display string — prevents "[object Object]". */
function toDisplayString(v) {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) return v.slice(0, 3).map(toDisplayString).join(', ');
  if (typeof v === 'object') {
    return Object.entries(v)
      .slice(0, 3)
      .map(([k, val]) => `${k}: ${val}`)
      .join(', ');
  }
  return String(v);
}

// ── Atoms ─────────────────────────────────────────────────────────────────────

function SeverityBadge({ severity }) {
  const s = SEV[(severity || '').toLowerCase()] || SEV.info;
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-semibold uppercase tracking-wide ${s.badge}`}>
      {severity || 'N/A'}
    </span>
  );
}

function ConfidenceBar({ score, height = 'h-2' }) {
  const pct   = Math.round((score || 0) * 100);
  const color = pct >= 70 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  const label = pct >= 70 ? 'text-green-400' : pct >= 50 ? 'text-yellow-400' : 'text-red-400';
  return (
    <div className="flex items-center gap-3">
      <div className={`flex-1 bg-slate-700 rounded-full ${height} overflow-hidden`}>
        <div className={`${height} rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-sm font-bold w-10 text-right tabular-nums ${label}`}>{pct}%</span>
    </div>
  );
}

function DimTable({ title, data, colorClass = 'text-blue-300' }) {
  if (!data || !Object.keys(data).length) return null;
  const total  = Object.values(data).reduce((a, b) => a + b, 0);
  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const barColor = colorClass.replace('text-', 'bg-').replace('-300', '-500');
  return (
    <div className="bg-slate-700/20 rounded-lg border border-slate-600/40 p-3">
      <p className="text-xs text-slate-400 font-semibold uppercase tracking-wide mb-2">{title}</p>
      <div className="space-y-1.5">
        {sorted.map(([label, count]) => (
          <div key={label} className="flex items-center gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-xs text-slate-300 truncate">{label}</span>
                <span className={`text-xs font-semibold tabular-nums ${colorClass}`}>{count}</span>
              </div>
              <div className="h-1 bg-slate-600 rounded-full overflow-hidden">
                <div className={`h-1 rounded-full ${barColor}`} style={{ width: `${(count / total) * 100}%` }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Section({ title, icon, children, defaultOpen = true, badge, accent }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`bg-slate-800/80 rounded-xl border overflow-hidden shadow-sm ${accent || 'border-slate-700'}`}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-slate-700/30 transition-colors text-left"
      >
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          {icon}{title}
          {badge && (
            <span className="ml-1 px-2 py-0.5 bg-slate-700 text-slate-400 rounded text-xs font-normal">{badge}</span>
          )}
        </h3>
        {open
          ? <FiChevronUp className="text-slate-500 w-4 h-4 flex-shrink-0" />
          : <FiChevronDown className="text-slate-500 w-4 h-4 flex-shrink-0" />}
      </button>
      {open && <div className="border-t border-slate-700/60 px-5 py-4 space-y-3">{children}</div>}
    </div>
  );
}

// ── Top Probable Causes ────────────────────────────────────────────────────────

const CAUSE_SOURCE = {
  llm_analysis:  { label: 'LLM',     cls: 'bg-blue-900/40 text-blue-300 border-blue-700/60'      },
  llm_secondary: { label: 'LLM',     cls: 'bg-blue-900/25 text-blue-400/70 border-blue-700/30'   },
  pattern_match: { label: 'Pattern', cls: 'bg-indigo-900/40 text-indigo-300 border-indigo-700/60' },
};

function ProbableCausesChart({ causes }) {
  if (!causes || causes.length === 0) return null;
  const maxProb = causes[0]?.probability || 1;

  return (
    <div>
      <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-2.5">
        Top Probable Causes
      </p>
      <div className="space-y-2">
        {causes.map((c, i) => {
          const pct      = Math.round(c.probability * 100);
          const barPct   = Math.round((c.probability / maxProb) * 100);
          const isTop    = i === 0;
          const barColor = isTop ? 'bg-orange-500' : i === 1 ? 'bg-amber-600/80' : 'bg-slate-500/70';
          const pctColor = isTop ? 'text-orange-300 font-bold' : i === 1 ? 'text-amber-400' : 'text-slate-400';
          const src      = CAUSE_SOURCE[c.source] || CAUSE_SOURCE.pattern_match;

          return (
            <div
              key={i}
              className={`px-3 py-2.5 rounded-lg border ${
                isTop
                  ? 'bg-orange-950/25 border-orange-800/50'
                  : 'bg-slate-700/10 border-slate-700/40'
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <span className={`text-xs leading-snug ${isTop ? 'text-white font-medium' : 'text-slate-300'} flex-1 min-w-0`}>
                  {isTop && <span className="text-orange-400 mr-1">▶</span>}
                  {c.cause}
                </span>
                <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                  <span className={`text-xs tabular-nums ${pctColor}`}>{pct}%</span>
                  <span className={`px-1.5 py-0.5 rounded border text-xs ${src.cls}`}>{src.label}</span>
                </div>
              </div>
              <div className="h-1.5 bg-slate-700/60 rounded-full overflow-hidden">
                <div
                  className={`h-1.5 rounded-full ${barColor}`}
                  style={{ width: `${barPct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Evidence-based reasoning ──────────────────────────────────────────────────

function EvidenceBasis({ reasoning, items }) {
  const hasItems = items && items.length > 0;
  if (!reasoning && !hasItems) return null;
  return (
    <div className="space-y-2">
      {reasoning && (
        <p className="text-slate-400 text-xs leading-relaxed">{reasoning}</p>
      )}
      {hasItems && (
        <div className="pl-1 space-y-1.5">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">Evidence basis</p>
          <ul className="space-y-1">
            {items.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-slate-400">
                <span className="text-indigo-400 mt-px flex-shrink-0 select-none">◆</span>
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Historical Similar Incidents table ────────────────────────────────────────

function HistoricalIncidentsTable({ incidents, onSelect }) {
  if (!incidents || incidents.length === 0) return null;
  return (
    <details className="group" open>
      <summary className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer hover:text-slate-200 select-none list-none mb-2 transition-colors">
        <FiDatabase className="w-3 h-3 flex-shrink-0" />
        <span className="font-semibold uppercase tracking-wide">Historical Similar Incidents</span>
        <span className="text-slate-600 font-normal ml-0.5">— {Math.min(incidents.length, 5)} retrieved</span>
        <FiChevronDown className="w-3 h-3 ml-auto group-open:rotate-180 transition-transform flex-shrink-0" />
      </summary>
      <div className="overflow-x-auto rounded-lg border border-slate-700/60">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-700/40 text-slate-400 uppercase tracking-wide">
              <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Alarm ID</th>
              <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Severity</th>
              <th className="px-3 py-2 text-left font-semibold whitespace-nowrap hidden sm:table-cell">Tech</th>
              <th className="px-3 py-2 text-left font-semibold whitespace-nowrap hidden md:table-cell">Region</th>
              <th className="px-3 py-2 text-right font-semibold whitespace-nowrap hidden sm:table-cell">Outage</th>
              <th className="px-3 py-2 text-right font-semibold whitespace-nowrap">Similarity</th>
              <th className="px-3 py-2 text-left font-semibold">Resolution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/40">
            {incidents.slice(0, 5).map((item, i) => {
              const inc   = item.incident || item;
              const score = Math.round((item.hybrid_score || item.similarity_score || 0) * 100);
              const scoreColor = score >= 70 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-slate-500';
              const res   = inc.resolution_notes || '—';
              return (
                <tr
                  key={i}
                  onClick={() => onSelect?.(item)}
                  className={`cursor-pointer transition-colors ${i === 0 ? 'bg-blue-950/20 hover:bg-blue-950/30' : 'hover:bg-slate-700/20'}`}
                >
                  <td className="px-3 py-2 font-mono text-blue-400 font-semibold whitespace-nowrap">
                    {i === 0 && <span className="text-blue-600 mr-1" title="Closest match">★</span>}
                    {inc.alarm_id || `INC-${i + 1}`}
                  </td>
                  <td className="px-3 py-2"><SeverityBadge severity={inc.severity} /></td>
                  <td className="px-3 py-2 text-slate-400 hidden sm:table-cell whitespace-nowrap">{inc.technology_type || '—'}</td>
                  <td className="px-3 py-2 text-slate-500 hidden md:table-cell whitespace-nowrap">{inc.network_region || '—'}</td>
                  <td className="px-3 py-2 text-right text-slate-400 tabular-nums hidden sm:table-cell whitespace-nowrap">
                    {inc.outage_duration > 0 ? `${inc.outage_duration}m` : '—'}
                  </td>
                  <td className={`px-3 py-2 text-right font-bold tabular-nums whitespace-nowrap ${scoreColor}`}>{score}%</td>
                  <td className="px-3 py-2 text-slate-400 max-w-[180px] truncate" title={res}>{res}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ── RCA Evidence table ─────────────────────────────────────────────────────────

function RcaEvidenceTable({ rows }) {
  if (!rows || !rows.length) return null;
  const supportCount = rows.filter(r => r.supports_rca).length;
  return (
    <details className="group">
      <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-300 flex items-center gap-1.5 select-none list-none">
        <FiFileText className="w-3 h-3 flex-shrink-0" />
        RCA evidence — {supportCount}/{rows.length} incident{rows.length !== 1 ? 's' : ''} support this diagnosis
        <FiChevronDown className="w-3 h-3 group-open:rotate-180 transition-transform" />
      </summary>
      <div className="mt-2 overflow-hidden rounded-lg border border-slate-700/60">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-700/40 text-slate-400 uppercase tracking-wide">
              <th className="px-3 py-2 text-left font-semibold">Alarm ID</th>
              <th className="px-3 py-2 text-left font-semibold">Declared Cause</th>
              <th className="px-3 py-2 text-left font-semibold">Category</th>
              <th className="px-3 py-2 text-left font-semibold">Severity</th>
              <th className="px-3 py-2 text-center font-semibold">Supports RCA</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/40">
            {rows.map((r, i) => (
              <tr key={i} className={r.supports_rca ? 'bg-green-950/20' : 'hover:bg-slate-700/10'}>
                <td className="px-3 py-2 font-mono text-blue-400">{r.alarm_id}</td>
                <td className="px-3 py-2 text-slate-300 max-w-[200px] truncate" title={r.declared_cause}>
                  {r.declared_cause}
                </td>
                <td className="px-3 py-2">
                  <span className={`px-1.5 py-0.5 rounded text-xs ${
                    r.category === 'unknown'
                      ? 'bg-slate-700 text-slate-400'
                      : 'bg-indigo-900/40 text-indigo-300 border border-indigo-800/40'
                  }`}>
                    {r.category}
                  </span>
                </td>
                <td className="px-3 py-2"><SeverityBadge severity={r.severity} /></td>
                <td className="px-3 py-2 text-center">
                  {r.supports_rca
                    ? <span className="text-green-400 font-bold">✓</span>
                    : <span className="text-slate-600">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ── Agent Workflow panel ───────────────────────────────────────────────────────

function AgentWorkflow({ steps }) {
  if (!steps || !steps.length) return null;
  const total = steps.reduce((s, a) => s + (a.duration_ms || 0), 0);
  return (
    <Section
      title="Multi-Agent Execution Workflow"
      icon={<FiActivity className="text-indigo-400 w-4 h-4" />}
      badge={`${steps.length} agents · ${total.toFixed(1)} ms`}
      accent="border-indigo-800/40"
    >
      <div className="relative">
        <div className="absolute left-[18px] top-6 bottom-6 w-px bg-slate-700/60" />
        <div className="space-y-3">
          {steps.map((step, i) => (
            <div key={i} className="flex gap-3">
              <div className="relative z-10 flex-shrink-0 w-9 h-9 rounded-full bg-indigo-900/50 border border-indigo-700/60 flex items-center justify-center text-indigo-300">
                {AGENT_ICONS[i] || <FiZap className="w-4 h-4" />}
              </div>
              <div className="flex-1 min-w-0 pb-1">
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm font-semibold text-white">{step.agent}</p>
                  <span className="text-xs text-green-400 flex items-center gap-1">
                    <FiCheckCircle className="w-3 h-3" />
                    {step.duration_ms?.toFixed(1)} ms
                  </span>
                  {total > 0 && (
                    <span className="text-xs text-slate-500 tabular-nums">
                      ({Math.round((step.duration_ms / total) * 100)}%)
                    </span>
                  )}
                </div>
                <p className="text-slate-300 text-xs leading-relaxed">{step.output}</p>
                {step.details && (
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {Object.entries(step.details)
                      .filter(([, v]) => v !== null && v !== undefined && v !== '' && v !== '—')
                      .slice(0, 5)
                      .map(([k, v]) => (
                        <span key={k} className="px-2 py-0.5 bg-slate-700/60 border border-slate-600/40 text-slate-400 rounded text-xs">
                          <span className="text-slate-500">{k.replace(/_/g, ' ')}: </span>
                          {/* toDisplayString prevents [object Object] for any value type */}
                          <span className="text-slate-300">{toDisplayString(v)}</span>
                        </span>
                      ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}

// ── Retrieval methodology header ──────────────────────────────────────────────

function RetrievalHeader({ methodology, isFallback, processingMs }) {
  const [expanded, setExpanded] = useState(false);
  if (!methodology) return null;
  return (
    <div className={`rounded-xl border px-4 py-3 ${
      isFallback
        ? 'bg-slate-800/60 border-slate-600/60'
        : 'bg-blue-950/40 border-blue-700/50'
    }`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          {isFallback
            ? <FiDatabase className="text-slate-400 w-4 h-4 flex-shrink-0" />
            : <FiZap className="text-blue-400 w-4 h-4 flex-shrink-0" />}
          <div className="min-w-0">
            <span className="text-sm font-semibold text-white">
              {isFallback ? methodology.engine : 'AI-Powered Analysis'}
            </span>
            <span className="text-slate-500 text-xs ml-2 hidden sm:inline">
              {isFallback
                ? `· ${methodology.algorithm}`
                : '· GPT vector similarity + LLM reasoning'}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {isFallback && (
            <span className="hidden sm:block px-2 py-0.5 bg-slate-700 rounded text-xs text-slate-300">
              {methodology.total_matched}/{methodology.total_searched} matched
            </span>
          )}
          <span className="text-slate-500 text-xs tabular-nums">{(processingMs || 0).toFixed(0)} ms</span>
          {isFallback && (
            <button onClick={() => setExpanded(e => !e)} className="text-slate-500 hover:text-slate-300 transition-colors">
              {expanded ? <FiChevronUp className="w-3.5 h-3.5" /> : <FiChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>
      </div>

      {isFallback && expanded && (
        <div className="mt-3 pt-3 border-t border-slate-700/60 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div>
            <p className="text-slate-500 mb-1 uppercase tracking-wide">Keywords Detected</p>
            <div className="flex flex-wrap gap-1">
              {(methodology.keywords_used || []).map((kw, i) => (
                <span key={i} className="px-2 py-0.5 bg-indigo-900/30 border border-indigo-800/40 text-indigo-300 rounded">
                  {kw}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-slate-500 mb-1 uppercase tracking-wide">Ranking Formula</p>
            <p className="text-slate-400 font-mono leading-relaxed">{methodology.ranking_formula}</p>
          </div>
          {Object.keys(methodology.filters_applied || {}).length > 0 && (
            <div>
              <p className="text-slate-500 mb-1 uppercase tracking-wide">Active Filters</p>
              <div className="flex flex-wrap gap-1">
                {Object.entries(methodology.filters_applied).map(([k, v]) => (
                  <span key={k} className="px-2 py-0.5 bg-green-900/20 border border-green-800/30 text-green-300 rounded">
                    {k}: {v}
                  </span>
                ))}
              </div>
            </div>
          )}
          {methodology.upgrade_path && (
            <div>
              <p className="text-slate-500 mb-1 uppercase tracking-wide">Upgrade Path</p>
              <p className="text-slate-400">{methodology.upgrade_path}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── A2A Message Timeline ──────────────────────────────────────────────────────

const MSG_STYLES = {
  REQUEST:      { bg: 'bg-blue-900/40 text-blue-300 border-blue-700/60',    dot: 'bg-blue-500',   label: 'REQ' },
  RESPONSE:     { bg: 'bg-green-900/40 text-green-300 border-green-700/60', dot: 'bg-green-500',  label: 'RSP' },
  ESCALATION:   { bg: 'bg-red-900/40 text-red-300 border-red-700/60',       dot: 'bg-red-500',    label: 'ESC' },
  NOTIFICATION: { bg: 'bg-purple-900/40 text-purple-300 border-purple-700/60', dot: 'bg-purple-500', label: 'NTF' },
  BROADCAST:    { bg: 'bg-amber-900/40 text-amber-300 border-amber-700/60', dot: 'bg-amber-500',  label: 'BRD' },
  ACK:          { bg: 'bg-slate-700/60 text-slate-400 border-slate-600',    dot: 'bg-slate-500',  label: 'ACK' },
};

const AGENT_ABBR = {
  Orchestrator:          'Orch',
  AlarmRetrievalAgent:   'Retrieval',
  RootCauseAgent:        'RootCause',
  ServiceImpactAgent:    'Impact',
  ResolutionAgent:       'Resolution',
  broadcast:             '⬡ ALL',
};

function A2AMessageCard({ msg }) {
  const [open, setOpen] = useState(false);
  const style  = MSG_STYLES[msg.msg_type] || MSG_STYLES.NOTIFICATION;
  const from   = AGENT_ABBR[msg.from_agent] || msg.from_agent;
  const to     = AGENT_ABBR[msg.to_agent]   || msg.to_agent;
  const reason = msg.payload?.reason || msg.payload?.action || '';

  // Filter payload for display — exclude raw_results (too large)
  const displayPayload = Object.entries(msg.payload || {})
    .filter(([k]) => k !== 'raw_results' && k !== 'incidents')
    .slice(0, 5);

  const ts = msg.timestamp
    ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '';

  return (
    <div className="flex gap-3 group">
      {/* Type dot */}
      <div className="relative z-10 flex-shrink-0 flex flex-col items-center">
        <div className={`w-2.5 h-2.5 rounded-full mt-2 ${style.dot}`} />
      </div>

      {/* Card */}
      <div className="flex-1 min-w-0 pb-3">
        <button
          onClick={() => setOpen(o => !o)}
          className="w-full text-left group/card"
        >
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={`px-1.5 py-0.5 rounded border text-xs font-bold tabular-nums ${style.bg}`}>
              {style.label}
            </span>
            <span className="text-xs font-semibold text-slate-300">{from}</span>
            <FiArrowRight className="w-3 h-3 text-slate-600 flex-shrink-0" />
            <span className={`text-xs font-semibold ${msg.to_agent === 'broadcast' ? 'text-amber-400' : 'text-slate-300'}`}>
              {to}
            </span>
            {reason && (
              <span className="text-slate-500 text-xs italic truncate max-w-[160px]">{reason}</span>
            )}
            <span className={`ml-auto text-xs hidden group-hover/card:inline tabular-nums ${
              msg.status === 'processed' ? 'text-green-700'
              : msg.status === 'delivered' ? 'text-blue-700'
              : 'text-slate-700'
            }`}>
              {msg.status}
            </span>
            <span className="text-slate-700 text-xs tabular-nums">{ts}</span>
          </div>

          {/* Collapsed payload preview */}
          {!open && displayPayload.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {displayPayload.slice(0, 3).map(([k, v]) => (
                <span key={k} className="text-xs px-1.5 py-0.5 bg-slate-800/60 rounded text-slate-600">
                  {k}: <span className="text-slate-500">{toDisplayString(v)}</span>
                </span>
              ))}
            </div>
          )}
        </button>

        {/* Expanded payload */}
        {open && (
          <div className="mt-1.5 p-2 bg-slate-800/40 rounded border border-slate-700/40 text-xs font-mono">
            {displayPayload.map(([k, v]) => (
              <div key={k} className="flex gap-2 py-0.5">
                <span className="text-slate-600 w-28 flex-shrink-0">{k}</span>
                <span className="text-slate-400 break-all">{toDisplayString(v)}</span>
              </div>
            ))}
            <div className="flex gap-2 py-0.5 border-t border-slate-700/40 mt-1 pt-1">
              <span className="text-slate-700 w-28 flex-shrink-0">corr_id</span>
              <span className="text-slate-700">{msg.correlation_id?.slice(0, 8)}…</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function A2ATimeline({ messages, stats }) {
  if (!messages || messages.length === 0) return null;

  const byType = stats?.by_type || {};
  const total  = stats?.total_messages || messages.length;

  return (
    <Section
      title="Agent-to-Agent Communication Log"
      icon={<FiMessageSquare className="text-cyan-400 w-4 h-4" />}
      badge={`${total} messages`}
      accent="border-cyan-800/40"
      defaultOpen={false}
    >
      {/* Stats row */}
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(byType).map(([type, count]) => {
          const s = MSG_STYLES[type] || MSG_STYLES.NOTIFICATION;
          return (
            <span key={type} className={`px-2 py-0.5 rounded border text-xs font-semibold ${s.bg}`}>
              {type}: {count}
            </span>
          );
        })}
        {stats?.by_agent && (
          <span className="ml-auto text-xs text-slate-600">
            {Object.keys(stats.by_agent).length} agents active
          </span>
        )}
      </div>

      {/* Message timeline */}
      <div className="relative pl-1">
        {/* Vertical line */}
        <div className="absolute left-[4px] top-2 bottom-2 w-px bg-slate-700/40" />

        <div className="space-y-0">
          {messages.map((msg, i) => (
            <A2AMessageCard key={msg.message_id || i} msg={msg} />
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 pt-2 border-t border-slate-700/40 text-xs text-slate-600">
        {Object.entries(MSG_STYLES).map(([type, s]) => (
          <span key={type} className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${s.dot}`} />
            {type}
          </span>
        ))}
      </div>
    </Section>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function ResultsPanel({ results, onIncidentSelect }) {
  const rootCause   = results?.root_cause_analysis       || {};
  const impact      = results?.service_impact_analysis   || {};
  const resolution  = results?.resolution_recommendations || {};
  const incidents   = results?.retrieved_incidents       || [];
  const correlation = results?.alarm_correlations        || {};
  const workflow    = results?.agent_workflow             || [];
  const methodology = results?.retrieval_methodology     || null;
  const dataSource  = results?.data_source               || {};

  const a2aMessages = results?.a2a_messages || [];
  const a2aStats    = results?.a2a_stats || results?.final_report?.a2a_stats || null;

  const isFallback     = results?.fallback_mode === true;
  const confidence     = rootCause.confidence_score || 0;
  const priority       = impact.priority_level || rootCause.severity_assessment || 'medium';
  const revLoss        = impact.estimated_revenue_loss || 0;
  const breakdown      = impact.revenue_loss_breakdown;
  const confFactors    = rootCause.confidence_breakdown || [];
  const rcaEvidence    = rootCause.rca_evidence || [];
  const evidenceSrc    = rootCause.evidence_source || 'default';
  const probableCauses = rootCause.probable_causes || [];
  const evidenceItems  = rootCause.evidence_items  || [];

  return (
    <div className="space-y-3">

      {/* Retrieval methodology header */}
      <RetrievalHeader
        methodology={methodology}
        isFallback={isFallback}
        processingMs={results?.processing_time_ms}
      />

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            label:      'Incidents Found',
            value:      incidents.length,
            sub:        `of ${dataSource.total_incidents || 500} searched`,
            accent:     'border-blue-500',
            valueClass: 'text-white',
          },
          {
            label:      'RCA Confidence',
            value:      `${Math.round(confidence * 100)}%`,
            sub:        rootCause.confidence_level || (confidence >= 0.7 ? 'Strong' : confidence >= 0.5 ? 'Moderate' : 'Limited'),
            accent:     'border-orange-500',
            valueClass: confidence >= 0.7 ? 'text-green-400' : confidence >= 0.5 ? 'text-yellow-400' : 'text-red-400',
          },
          {
            label:      'Priority Level',
            value:      priority.toUpperCase(),
            sub:        priority === 'unknown' ? 'N/A' : `${impact.average_outage_minutes || 0} min avg outage`,
            accent:     priority === 'critical' ? 'border-red-500' : priority === 'high' ? 'border-orange-500' : priority === 'unknown' ? 'border-slate-500' : 'border-yellow-500',
            valueClass: PRIORITY_COLOR[priority] || 'text-slate-300',
          },
          {
            label:      'Est. Resolution',
            value:      resolution.estimated_resolution_time?.split('–')[0] || '—',
            sub:        resolution.estimated_resolution_time
                          ? `up to ${resolution.estimated_resolution_time.split('–')[1] || ''}`
                          : 'based on history',
            accent:     'border-green-500',
            valueClass: 'text-white',
          },
        ].map(({ label, value, sub, accent, valueClass }) => (
          <div key={label} className={`bg-slate-800/80 rounded-xl border-l-4 border border-slate-700 ${accent} p-4 shadow-sm`}>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">{label}</p>
            <p className={`text-2xl font-bold leading-tight ${valueClass}`}>{value}</p>
            <p className="text-slate-500 text-xs mt-1">{sub}</p>
          </div>
        ))}
      </div>

      {/* Agent Workflow */}
      <AgentWorkflow steps={workflow} />

      {/* A2A Communication Log */}
      <A2ATimeline messages={a2aMessages} stats={a2aStats} />

      {/* Retrieved Incidents */}
      <Section
        title="Retrieved Incidents"
        badge={`${incidents.length} matches`}
        icon={<FiTrendingUp className="text-blue-400 w-4 h-4" />}
      >
        {incidents.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-4">No matching incidents found.</p>
        ) : (
          <div className="space-y-2">
            {incidents.map((item, idx) => {
              const inc    = item.incident || item;
              const score  = Math.round((item.hybrid_score || 0) * 100);
              const sev    = (inc.severity || '').toLowerCase();
              const styles = SEV[sev] || SEV.info;
              return (
                <div
                  key={idx}
                  onClick={() => onIncidentSelect?.(item)}
                  className="p-3 bg-slate-700/20 rounded-lg border border-slate-600/50 hover:border-blue-500/60 hover:bg-slate-700/40 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono text-xs text-blue-400 font-semibold flex-shrink-0">
                        {inc.alarm_id || `INC-${idx + 1}`}
                      </span>
                      <SeverityBadge severity={inc.severity} />
                      <span className="text-xs text-slate-500">#{idx + 1}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-slate-400 flex-shrink-0">
                      <div className="w-14 bg-slate-600 rounded-full h-1.5 overflow-hidden">
                        <div className={`h-1.5 rounded-full ${styles.bar}`} style={{ width: `${score}%` }} />
                      </div>
                      <span className="tabular-nums w-8 text-right">{score}%</span>
                    </div>
                  </div>
                  {/* Declared cause badge — shown when a specific cause is known */}
                  {inc.declared_cause && inc.declared_cause !== 'Unknown cause' && (
                    <div className="mb-1.5">
                      <span className="text-xs px-2 py-0.5 bg-orange-900/30 border border-orange-800/40 text-orange-300 rounded">
                        Cause: {inc.declared_cause}
                      </span>
                    </div>
                  )}
                  <p className="text-slate-300 text-xs leading-relaxed line-clamp-2 mb-2">
                    {inc.incident_description || inc.description}
                  </p>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <FiMapPin className="w-3 h-3" />{inc.network_region || inc.region}
                    </span>
                    <span className="flex items-center gap-1">
                      <FiWifi className="w-3 h-3" />{inc.technology_type || inc.technology}
                    </span>
                    <span>{inc.device_vendor || inc.vendor}</span>
                    {(inc.outage_duration > 0) && (
                      <span className="ml-auto flex items-center gap-1">
                        <FiClock className="w-3 h-3" />{inc.outage_duration} min
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Section>

      {/* Root Cause Analysis */}
      <Section title="Root Cause Analysis" icon={<FiAlertTriangle className="text-orange-400 w-4 h-4" />}>

        {/* Evidence source warning when no incident-level evidence */}
        {evidenceSrc === 'query_keywords' && (
          <div className="p-2.5 bg-amber-950/40 border border-amber-700/50 rounded-lg flex items-start gap-2 text-xs">
            <FiAlertCircle className="text-amber-400 w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            <p className="text-amber-300">
              <span className="font-semibold">Limited evidence:</span> All retrieved incidents have 'Unknown cause'.
              RCA inferred from query keywords — not confirmed by incident data. Confidence is reduced.
            </p>
          </div>
        )}

        {/* Primary cause */}
        <div className="p-3.5 bg-orange-950/30 border border-orange-800/40 rounded-lg">
          <p className="text-xs text-orange-400/80 font-semibold uppercase tracking-wide mb-1.5">Primary Cause</p>
          <p className="text-white text-sm leading-relaxed font-medium">
            {rootCause.primary_cause || 'Analysing fault pattern…'}
          </p>
          {rootCause.primary_vendor && (
            <p className="text-orange-300/60 text-xs mt-1.5">
              Primary vendor: <span className="text-orange-300 font-semibold">{rootCause.primary_vendor}</span>
            </p>
          )}
          {rootCause.analysis_method && (
            <p className="text-orange-300/40 text-xs mt-1">{rootCause.analysis_method}</p>
          )}
        </div>

        {/* Top probable causes with probability bars */}
        <ProbableCausesChart causes={probableCauses} />

        {/* Confidence bar + evidence-based reasoning */}
        <div className="space-y-1.5">
          <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold">Detection Confidence</p>
          <ConfidenceBar score={confidence} />
          <EvidenceBasis reasoning={rootCause.analysis_reasoning} items={evidenceItems} />
        </div>

        {/* Historical Similar Incidents table */}
        <HistoricalIncidentsTable incidents={incidents} onSelect={onIncidentSelect} />

        {/* RCA Evidence table — per-incident declared cause with support flag */}
        <RcaEvidenceTable rows={rcaEvidence} />

        {/* Confidence factor breakdown */}
        {confFactors.length > 0 && (
          <details className="group">
            <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-300 flex items-center gap-1.5 select-none list-none">
              <FiInfo className="w-3 h-3 flex-shrink-0" />
              Confidence factor breakdown
              <FiChevronDown className="w-3 h-3 group-open:rotate-180 transition-transform" />
            </summary>
            <div className="mt-2 overflow-hidden rounded-lg border border-slate-700/60">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-700/40 text-slate-400 uppercase tracking-wide">
                    <th className="px-3 py-2 text-left font-semibold">Factor</th>
                    <th className="px-3 py-2 text-right font-semibold">Weight</th>
                    <th className="px-3 py-2 text-right font-semibold">Score</th>
                    <th className="px-3 py-2 text-right font-semibold">Contribution</th>
                    <th className="px-3 py-2 text-left font-semibold hidden sm:table-cell">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/40">
                  {confFactors.map((f, i) => (
                    <tr key={i} className="hover:bg-slate-700/20">
                      <td className="px-3 py-2 text-slate-300">{f.factor}</td>
                      <td className="px-3 py-2 text-right text-slate-400 tabular-nums">{(f.weight * 100).toFixed(0)}%</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        <span className={f.score >= 0.7 ? 'text-green-400' : f.score >= 0.4 ? 'text-yellow-400' : 'text-red-400'}>
                          {(f.score * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-indigo-400 font-semibold tabular-nums">
                        +{(f.contrib * 100).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-slate-500 hidden sm:table-cell">{f.detail}</td>
                    </tr>
                  ))}
                  <tr className="bg-slate-700/20 font-semibold">
                    <td className="px-3 py-2 text-slate-300" colSpan={3}>Total (approx)</td>
                    <td className="px-3 py-2 text-right text-white tabular-nums">
                      {Math.round(confFactors.reduce((s, f) => s + f.contrib, 0) * 100)}%
                    </td>
                    <td className="hidden sm:table-cell" />
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        )}

        {/* Contributing factors */}
        {(rootCause.contributing_factors || []).length > 0 && (
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-2">Contributing Factors</p>
            <ul className="space-y-1.5">
              {rootCause.contributing_factors.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className={`mt-0.5 flex-shrink-0 font-bold ${String(f).startsWith('⚠') ? 'text-amber-400' : 'text-orange-400/80'}`}>▸</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex items-center gap-2 pt-1 border-t border-slate-700/60">
          <span className="text-slate-400 text-xs">Severity assessment:</span>
          <SeverityBadge severity={rootCause.severity_assessment} />
        </div>
      </Section>

      {/* Service Impact */}
      <Section title="Service Impact Analysis" icon={<FiShield className="text-red-400 w-4 h-4" />}>
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 bg-slate-700/30 rounded-lg border border-slate-600/60">
            <p className="text-slate-400 text-xs mb-1">Est. Revenue Loss</p>
            <p className={`text-xl font-bold tabular-nums ${priority === 'unknown' ? 'text-slate-400' : 'text-red-400'}`}>
              {priority === 'unknown' ? 'N/A' : revLoss >= 1_000_000
                ? `$${(revLoss / 1_000_000).toFixed(2)}M`
                : revLoss >= 1_000
                ? `$${(revLoss / 1_000).toFixed(1)}K`
                : `$${revLoss.toFixed(0)}`}
            </p>
            <p className="text-slate-500 text-xs mt-1">
              {priority === 'unknown' ? 'No historical data' : breakdown ? breakdown.formula : `${impact.average_outage_minutes || 0} min × $1,200/min`}
            </p>
          </div>
          <div className="p-3 bg-slate-700/30 rounded-lg border border-slate-600/60">
            <p className="text-slate-400 text-xs mb-1">Priority Level</p>
            <p className={`text-xl font-bold uppercase ${PRIORITY_COLOR[priority] || 'text-slate-300'}`}>{priority}</p>
            <p className="text-slate-500 text-xs mt-1">{impact.estimated_users_affected || 'historical match'}</p>
          </div>
        </div>

        {breakdown && priority !== 'unknown' && (
          <div className="p-3 bg-slate-700/20 rounded-lg border border-slate-600/40 text-xs text-slate-400">
            <span className="font-semibold text-slate-300">Calculation: </span>
            {breakdown.formula} ={' '}
            <span className="text-red-400 font-semibold">
              ${breakdown.total_usd >= 1000 ? `${(breakdown.total_usd / 1000).toFixed(1)}K` : breakdown.total_usd.toFixed(0)}
            </span>
            {' '}· avg across {breakdown.incident_count} incident{breakdown.incident_count !== 1 ? 's' : ''}{' '}
            · rate: ${breakdown.revenue_per_minute_usd?.toLocaleString()}/min
          </div>
        )}

        {(impact.average_outage_minutes > 0) && (
          <div className="flex items-center gap-4 text-xs text-slate-400 px-1">
            <span>Min: <span className="text-slate-300 font-semibold">{impact.min_outage_minutes || 0} min</span></span>
            <span>Avg: <span className="text-yellow-400 font-semibold">{impact.average_outage_minutes} min</span></span>
            <span>Max: <span className="text-red-400 font-semibold">{impact.max_outage_minutes || 0} min</span></span>
          </div>
        )}

        {impact.customer_impact && (
          <div className="p-3 bg-slate-700/20 rounded-lg border border-slate-600/40">
            <p className="text-slate-400 text-xs mb-1 uppercase tracking-wide font-semibold">Customer Impact</p>
            <p className="text-slate-200 text-sm leading-relaxed">{impact.customer_impact}</p>
          </div>
        )}

        {(impact.affected_services || []).length > 0 && (
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-2">Affected Services</p>
            <div className="flex flex-wrap gap-1.5">
              {impact.affected_services.map((s, i) => (
                <span key={i} className="px-2.5 py-1 bg-slate-700 border border-slate-600 text-slate-300 rounded-full text-xs font-medium">{s}</span>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {(impact.affected_regions || []).length > 0 && (
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-1.5">Regions</p>
              <div className="flex flex-col gap-1">
                {impact.affected_regions.map((r, i) => (
                  <span key={i} className="flex items-center gap-1 px-2 py-0.5 bg-blue-900/20 border border-blue-800/40 text-blue-300 rounded text-xs">
                    <FiMapPin className="w-3 h-3" />{r}
                  </span>
                ))}
              </div>
            </div>
          )}
          {(impact.affected_technologies || []).length > 0 && (
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-1.5">Technologies</p>
              <div className="flex flex-col gap-1">
                {impact.affected_technologies.map((t, i) => (
                  <span key={i} className="flex items-center gap-1 px-2 py-0.5 bg-purple-900/20 border border-purple-800/40 text-purple-300 rounded text-xs">
                    <FiWifi className="w-3 h-3" />{t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {(impact.affected_vendors || []).length > 0 && (
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-1.5">Vendors Affected</p>
              <div className="flex flex-col gap-1">
                {impact.affected_vendors.map((v, i) => (
                  <span key={i} className={`px-2 py-0.5 rounded border text-xs ${
                    i === 0
                      ? 'bg-amber-900/20 border-amber-800/40 text-amber-300'
                      : 'bg-slate-700/30 border-slate-600/40 text-slate-400'
                  }`}>
                    {i === 0 ? '★ ' : ''}{v}
                    {impact.vendor_distribution?.[v] ? ` (${impact.vendor_distribution[v]})` : ''}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {impact.business_impact && !['critical','high','medium','low','info'].includes(impact.business_impact) && (
          <p className="text-slate-400 text-sm leading-relaxed border-t border-slate-700/60 pt-3">
            {impact.business_impact}
          </p>
        )}
      </Section>

      {/* Resolution */}
      <Section title="Resolution Recommendations" icon={<FiCheckCircle className="text-green-400 w-4 h-4" />}>
        {resolution.escalation_recommendation && (
          <div className="p-3 bg-red-950/40 border border-red-700/50 rounded-lg flex items-start gap-2.5">
            <FiAlertCircle className="text-red-400 w-4 h-4 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-red-300 font-semibold text-sm">Escalation Required</p>
              <p className="text-red-300/80 text-xs mt-0.5 leading-relaxed">{resolution.escalation_recommendation}</p>
            </div>
          </div>
        )}

        {(resolution.recommended_actions || []).length > 0 && (
          <ol className="space-y-2">
            {resolution.recommended_actions.map((action, idx) => (
              <li key={idx} className="flex gap-3 text-sm text-slate-300">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-green-900/40 border border-green-700/60 flex items-center justify-center text-xs font-bold text-green-400 mt-0.5">
                  {idx + 1}
                </span>
                <span className="leading-relaxed">{action}</span>
              </li>
            ))}
          </ol>
        )}

        {resolution.estimated_resolution_time && (
          <div className="flex items-center gap-2 pt-2 border-t border-slate-700/60">
            <FiClock className="text-slate-400 w-4 h-4 flex-shrink-0" />
            <span className="text-slate-400 text-sm">Estimated resolution:</span>
            <span className="text-white font-semibold text-sm">{resolution.estimated_resolution_time}</span>
            {resolution.data_driven && (
              <span className="text-slate-500 text-xs ml-auto">from historical data</span>
            )}
          </div>
        )}
      </Section>

      {/* Alarm Correlation */}
      {(correlation.correlated_alarms || []).length > 0 && (
        <Section
          title="Alarm Correlation Analysis"
          badge={`${(correlation.correlated_alarms || []).length} alarms · strength ${Math.round((correlation.correlation_strength || 0) * 100)}%`}
          icon={<FiActivity className="text-purple-400 w-4 h-4" />}
          defaultOpen={true}
        >
          {correlation.pattern_summary && (
            <div className="p-3 bg-slate-700/20 rounded-lg border border-slate-600/40">
              <p className="text-slate-400 text-xs mb-1 uppercase tracking-wide font-semibold">Pattern Summary</p>
              <p className="text-slate-200 text-sm leading-relaxed">{correlation.pattern_summary}</p>
            </div>
          )}

          {correlation.cascade_risk && (
            <div className="p-3 bg-red-950/30 border border-red-700/40 rounded-lg text-sm text-red-300 flex items-start gap-2">
              <FiAlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              {correlation.cascade_analysis}
            </div>
          )}

          <div className="space-y-1">
            <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold">
              Correlation Strength
              <span className="text-slate-600 normal-case font-normal ml-1">(vendor + region + tech + severity + cause homogeneity)</span>
            </p>
            <ConfidenceBar score={correlation.correlation_strength || 0} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <DimTable title="By Region"     data={correlation.by_region}     colorClass="text-blue-300" />
            <DimTable title="By Vendor"     data={correlation.by_vendor}     colorClass="text-amber-300" />
            <DimTable title="By Technology" data={correlation.by_technology} colorClass="text-purple-300" />
            <DimTable title="By Severity"   data={correlation.by_severity}   colorClass="text-red-300" />
            {correlation.by_cause && Object.keys(correlation.by_cause).length > 0 && (
              <DimTable title="By Root Cause" data={correlation.by_cause} colorClass="text-orange-300" />
            )}
          </div>

          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-2">Correlated Alarm IDs</p>
            <div className="flex flex-wrap gap-1.5">
              {correlation.correlated_alarms.map((id, i) => (
                <span key={i} className="font-mono text-xs px-2 py-1 bg-slate-700/60 text-slate-300 rounded border border-slate-600/60">
                  {id}
                </span>
              ))}
            </div>
          </div>
        </Section>
      )}

      {/* Footer */}
      <div className="text-center text-slate-600 text-xs pt-1 pb-2 space-y-0.5">
        <p>
          Analysis in{' '}
          <span className="text-slate-500">{(results?.processing_time_ms || 0).toFixed(0)} ms</span>
          {dataSource.matched != null && (
            <> · <span className="text-slate-500">{dataSource.matched} matched</span> of {dataSource.total_incidents}</>
          )}
        </p>
        {isFallback && (
          <p>Source: local CSV · {dataSource.method || 'keyword matching'}</p>
        )}
      </div>
    </div>
  );
}
