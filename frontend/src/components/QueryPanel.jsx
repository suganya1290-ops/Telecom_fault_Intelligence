import React, { memo } from 'react';
import { FiSearch, FiX, FiZap } from 'react-icons/fi';

const SAMPLES = [
  {
    label: '5G Drops',
    tag: 'Critical · 5G · North India',
    tagCls: 'text-red-300 border-red-700/60',
    query: 'Multiple users in North India reporting 5G connectivity drops and handover failures during peak hours on Ericsson equipment',
    filters: { region: 'North India', severity: 'critical', technology: '5G', vendor: 'Ericsson' },
  },
  {
    label: 'Fiber Backhaul Cut',
    tag: 'Critical · Fiber · South India',
    tagCls: 'text-red-300 border-red-700/60',
    query: 'Complete fiber backhaul outage causing service disruption across multiple sites in South India, optical signal loss detected',
    filters: { region: 'South India', severity: 'critical', technology: 'Fiber', vendor: '' },
  },
  {
    label: 'BTS Power Failure',
    tag: 'High · 4G · West India',
    tagCls: 'text-orange-300 border-orange-700/60',
    query: 'Multiple BTS towers reporting power supply failures and going offline in West India, battery backup depleted',
    filters: { region: 'West India', severity: 'high', technology: '4G', vendor: '' },
  },
  {
    label: 'LTE Sync Failure',
    tag: 'High · LTE · East India',
    tagCls: 'text-orange-300 border-orange-700/60',
    query: 'BTS synchronization failures causing call drops and degraded throughput on LTE network in East India Nokia infrastructure',
    filters: { region: 'East India', severity: 'high', technology: 'LTE', vendor: 'Nokia' },
  },
  {
    label: 'GSM Interference',
    tag: 'Medium · GSM · Central India',
    tagCls: 'text-yellow-300 border-yellow-700/60',
    query: 'GSM interference from adjacent channels causing voice quality degradation and dropped calls in rural Central India',
    filters: { region: 'Central India', severity: 'medium', technology: 'GSM', vendor: '' },
  },
  {
    label: 'Microwave Link Down',
    tag: 'High · Microwave · South India',
    tagCls: 'text-orange-300 border-orange-700/60',
    query: 'Microwave backhaul link showing high latency and packet loss, link degraded between transmission sites in South India',
    filters: { region: 'South India', severity: 'high', technology: 'Microwave', vendor: '' },
  },
  {
    label: 'Network Congestion',
    tag: 'High · 5G · West India',
    tagCls: 'text-orange-300 border-orange-700/60',
    query: 'Severe network congestion on 5G mmWave cells in West India causing timeout errors and throughput degradation during peak traffic',
    filters: { region: 'West India', severity: 'high', technology: '5G', vendor: '' },
  },
  {
    label: 'Hardware Module Fault',
    tag: 'Critical · 4G · Huawei',
    tagCls: 'text-red-300 border-red-700/60',
    query: 'Huawei baseband unit hardware module failure causing complete cell outage and loss of all 4G services at multiple sites',
    filters: { region: '', severity: 'critical', technology: '4G', vendor: 'Huawei' },
  },
];

function QueryPanel({ query, onQueryChange, filters, onFilterChange, onSubmit, onClearFilters, onLoadSample, loading }) {
  const activeQuery = query.trim();

  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <FiSearch className="text-blue-500 text-xl" />
        <h2 className="text-xl font-bold text-white">Fault Query</h2>
      </div>

      {/* Sample incidents */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <FiZap className="text-yellow-400 w-3.5 h-3.5" />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Sample Incidents</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {SAMPLES.map((s) => {
            const isActive = query === s.query;
            return (
              <button
                key={s.label}
                type="button"
                disabled={loading}
                onClick={() => onLoadSample({ query: s.query, filters: s.filters })}
                className={`text-left p-2.5 rounded-lg border transition-colors group
                  ${isActive
                    ? 'bg-blue-900/40 border-blue-500/70 ring-1 ring-blue-500/40'
                    : 'bg-slate-800/60 border-slate-700/60 hover:bg-slate-700/60 hover:border-slate-500/80'
                  }
                  ${loading ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <p className={`text-xs font-semibold mb-1 ${isActive ? 'text-blue-300' : 'text-slate-200 group-hover:text-white'}`}>
                  {s.label}
                </p>
                <p className={`text-[10px] font-medium border rounded px-1 py-0.5 inline-block ${s.tagCls}`}>
                  {s.tag}
                </p>
                <p className="text-[10px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                  {s.query}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        {/* Query Input */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Describe the Network Issue
          </label>
          <textarea
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Example: Users in North India experiencing 5G connectivity drops during peak hours..."
            rows="3"
            className="input resize-none"
            disabled={loading}
          />
          <p className="text-slate-400 text-xs mt-1">
            Click a sample above or describe the incident in natural language. Include region, technology, symptoms, and relevant details.
          </p>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Region</label>
            <select
              value={filters.region}
              onChange={(e) => onFilterChange('region', e.target.value)}
              className="select"
              disabled={loading}
            >
              <option value="">All Regions</option>
              <option value="North India">North India</option>
              <option value="South India">South India</option>
              <option value="East India">East India</option>
              <option value="West India">West India</option>
              <option value="Central India">Central India</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Severity</label>
            <select
              value={filters.severity}
              onChange={(e) => onFilterChange('severity', e.target.value)}
              className="select"
              disabled={loading}
            >
              <option value="">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Technology</label>
            <select
              value={filters.technology}
              onChange={(e) => onFilterChange('technology', e.target.value)}
              className="select"
              disabled={loading}
            >
              <option value="">All Technologies</option>
              <option value="5G">5G</option>
              <option value="4G">4G</option>
              <option value="LTE">LTE</option>
              <option value="GSM">GSM</option>
              <option value="Fiber">Fiber</option>
              <option value="Microwave">Microwave</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Vendor</label>
            <select
              value={filters.vendor}
              onChange={(e) => onFilterChange('vendor', e.target.value)}
              className="select"
              disabled={loading}
            >
              <option value="">All Vendors</option>
              <option value="Ericsson">Ericsson</option>
              <option value="Nokia">Nokia</option>
              <option value="Huawei">Huawei</option>
              <option value="Cisco">Cisco</option>
              <option value="Juniper">Juniper</option>
              <option value="Samsung">Samsung</option>
            </select>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-3 justify-end pt-4">
          <button
            type="button"
            onClick={onClearFilters}
            className="btn btn-secondary"
            disabled={loading || !activeQuery}
          >
            <FiX className="mr-2" />
            Clear
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !activeQuery}
          >
            <FiSearch className="mr-2" />
            {loading ? 'Analyzing...' : 'Analyze Fault'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default memo(QueryPanel);
