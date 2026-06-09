import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FiAlertCircle, FiZap, FiSearch, FiBarChart2, FiTrendingUp } from 'react-icons/fi';
import QueryPanel from './components/QueryPanel';
import ResultsPanel from './components/ResultsPanel';
import Dashboard from './components/Dashboard';
import IncidentDetails from './components/IncidentDetails';
import PredictivePanel from './components/PredictivePanel';

const TABS = [
  { id: 'analysis',   label: 'Fault Analysis',         icon: FiSearch      },
  { id: 'dashboard',  label: 'Dashboard',               icon: FiBarChart2   },
  { id: 'predictive', label: 'Predictive Intelligence', icon: FiTrendingUp  },
];

function App() {
  const [query, setQuery]                   = useState('');
  const [results, setResults]               = useState(null);
  const [loading, setLoading]               = useState(false);
  const [error, setError]                   = useState(null);
  const [activeTab, setActiveTab]           = useState('analysis');
  const [metrics, setMetrics]               = useState(null);
  const [showDetails, setShowDetails]       = useState(false);
  const [selectedIncident, setSelectedIncident] = useState(null);

  const [filters, setFilters] = useState({
    region: '', severity: '', technology: '', vendor: '',
  });

  const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

  useEffect(() => { fetchMetrics(); }, []);

  const fetchMetrics = async () => {
    try {
      const res = await axios.get(`${API_BASE}/dashboard/metrics`);
      setMetrics(res.data);
    } catch (err) {
      console.error('Error fetching metrics:', err);
    }
  };

  const handleQuery = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await axios.post(`${API_BASE}/query`, {
        query: query.trim(),
        region_filter:     filters.region     || undefined,
        severity_filter:   filters.severity   || undefined,
        technology_filter: filters.technology || undefined,
        vendor_filter:     filters.vendor     || undefined,
      });
      setResults(res.data);
      setActiveTab('analysis');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Error processing query');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (field, value) =>
    setFilters(prev => ({ ...prev, [field]: value }));

  const handleClearFilters = () => {
    setFilters({ region: '', severity: '', technology: '', vendor: '' });
    setQuery('');
    setResults(null);
    setError(null);
  };

  const handleLoadSample = ({ query: q, filters: f }) => {
    setQuery(q);
    setFilters({ region: f.region || '', severity: f.severity || '', technology: f.technology || '', vendor: f.vendor || '' });
    setResults(null);
    setError(null);
  };

  const isServiceError = error && (error.includes('unavailable') || error.includes('503'));

  return (
    <div className="min-h-screen flex flex-col">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <header className="bg-slate-900 border-b border-slate-700 shadow-lg flex-shrink-0">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <FiZap className="text-blue-500 text-2xl flex-shrink-0" />
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-white leading-tight whitespace-nowrap">Telecom Fault Intelligence</h1>
              <p className="text-slate-400 text-xs hidden sm:block">AI-Powered Network Fault Analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 rounded-lg flex-shrink-0">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-green-400 text-xs font-medium">Online</span>
          </div>
        </div>
      </header>

      {/* ── Tab Bar ─────────────────────────────────────────────────────────── */}
      <nav className="bg-slate-900 border-b border-slate-700 flex-shrink-0 sticky top-0 z-20">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 flex gap-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === id
                  ? 'text-blue-400 border-blue-500'
                  : 'text-slate-400 border-transparent hover:text-slate-200 hover:border-slate-500'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="hidden sm:inline">{label}</span>
              <span className="sm:hidden">{label.split(' ')[0]}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 sm:px-6 py-4">

        {/* Analysis tab — two-column on large screens */}
        {activeTab === 'analysis' && (
          <div className="flex flex-col lg:flex-row gap-4 items-start">

            {/* Left: Query panel (sticky on desktop) */}
            <div className="w-full lg:w-[400px] xl:w-[440px] flex-shrink-0 lg:sticky lg:top-[57px]">
              <QueryPanel
                query={query}
                onQueryChange={setQuery}
                filters={filters}
                onFilterChange={handleFilterChange}
                onSubmit={handleQuery}
                onClearFilters={handleClearFilters}
                onLoadSample={handleLoadSample}
                loading={loading}
              />

              {/* Error */}
              {error && (
                <div className={`mt-3 p-3 rounded-lg flex items-start gap-3 border text-sm ${
                  isServiceError ? 'bg-yellow-900/20 border-yellow-700' : 'bg-red-900/20 border-red-700'
                }`}>
                  <FiAlertCircle className={`mt-0.5 flex-shrink-0 ${isServiceError ? 'text-yellow-400' : 'text-red-400'}`} />
                  <div>
                    <p className={`font-medium ${isServiceError ? 'text-yellow-300' : 'text-red-300'}`}>
                      {isServiceError ? 'AI Service Unavailable' : 'Analysis Error'}
                    </p>
                    <p className="text-slate-300 text-xs mt-0.5">{error}</p>
                  </div>
                </div>
              )}

              {/* Loading indicator (compact, in left panel) */}
              {loading && (
                <div className="mt-3 p-4 bg-slate-800/60 rounded-lg flex items-center gap-3 border border-slate-700">
                  <div className="w-6 h-6 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin flex-shrink-0" />
                  <div>
                    <p className="text-slate-200 text-sm font-medium">Analyzing fault…</p>
                    <p className="text-slate-500 text-xs">Running multi-agent workflow</p>
                  </div>
                </div>
              )}
            </div>

            {/* Right: Results panel */}
            <div className="flex-1 min-w-0">
              {results && !loading ? (
                <ResultsPanel
                  results={results}
                  query={query}
                  filters={filters}
                  onIncidentSelect={(incident) => {
                    setSelectedIncident(incident);
                    setShowDetails(true);
                  }}
                />
              ) : !loading && !error ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <FiZap className="text-slate-600 text-4xl mb-4" />
                  <p className="text-slate-500 text-sm">Run a fault analysis to see results here.</p>
                  <p className="text-slate-600 text-xs mt-1">Select a sample or describe your incident.</p>
                </div>
              ) : null}
            </div>
          </div>
        )}

        {/* Dashboard tab */}
        {activeTab === 'dashboard' && (
          <Dashboard metrics={metrics} />
        )}

        {/* Predictive tab */}
        {activeTab === 'predictive' && (
          <PredictivePanel />
        )}
      </main>

      {/* Incident Details Modal */}
      {showDetails && selectedIncident && (
        <IncidentDetails
          incident={selectedIncident}
          onClose={() => { setShowDetails(false); setSelectedIncident(null); }}
        />
      )}
    </div>
  );
}

export default App;
