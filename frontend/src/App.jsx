import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FiAlertCircle, FiZap } from 'react-icons/fi';
import QueryPanel from './components/QueryPanel';
import ResultsPanel from './components/ResultsPanel';
import Dashboard from './components/Dashboard';
import IncidentDetails from './components/IncidentDetails';
import PredictivePanel from './components/PredictivePanel';

function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('analysis');
  const [metrics, setMetrics] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState(null);

  const [filters, setFilters] = useState({
    region: '',
    severity: '',
    technology: '',
    vendor: ''
  });

  const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

  useEffect(() => {
    fetchMetrics();
  }, []);

  const fetchMetrics = async () => {
    try {
      const response = await axios.get(`${API_BASE}/dashboard/metrics`);
      setMetrics(response.data);
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
      const response = await axios.post(`${API_BASE}/query`, {
        query: query.trim(),
        region_filter: filters.region || undefined,
        severity_filter: filters.severity || undefined,
        technology_filter: filters.technology || undefined,
        vendor_filter: filters.vendor || undefined,
      });

      setResults(response.data);
      setActiveTab('analysis');
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Error processing query';
      setError(errorMsg);
      console.error('Query error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleClearFilters = () => {
    setFilters({
      region: '',
      severity: '',
      technology: '',
      vendor: ''
    });
    setQuery('');
    setResults(null);
  };

  const handleLoadSample = ({ query: q, filters: f }) => {
    setQuery(q);
    setFilters({ region: f.region || '', severity: f.severity || '', technology: f.technology || '', vendor: f.vendor || '' });
    setResults(null);
    setError(null);
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-slate-900 border-b border-slate-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FiZap className="text-blue-500 text-3xl" />
              <div>
                <h1 className="text-3xl font-bold text-white">Telecom Fault Intelligence</h1>
                <p className="text-slate-400 text-sm">AI-Powered Network Fault Analysis System</p>
              </div>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-green-400 text-sm font-medium">System Online</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Tab Navigation */}
        <div className="flex gap-4 mb-6 border-b border-slate-700">
          <button
            onClick={() => setActiveTab('analysis')}
            className={`px-4 py-3 font-medium transition-colors ${
              activeTab === 'analysis'
                ? 'text-blue-500 border-b-2 border-blue-500'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            Fault Analysis
          </button>
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`px-4 py-3 font-medium transition-colors ${
              activeTab === 'dashboard'
                ? 'text-blue-500 border-b-2 border-blue-500'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => setActiveTab('predictive')}
            className={`px-4 py-3 font-medium transition-colors ${
              activeTab === 'predictive'
                ? 'text-blue-500 border-b-2 border-blue-500'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            Predictive Intelligence
          </button>
        </div>

        {/* Analysis Tab */}
        {activeTab === 'analysis' && (
          <div className="space-y-6">
            {/* Query Panel */}
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

            {/* Error Message */}
            {error && (
              <div className={`p-4 rounded-lg flex items-start gap-3 border ${
                error.includes('unavailable') || error.includes('503')
                  ? 'bg-yellow-900/20 border-yellow-700'
                  : 'bg-red-900/20 border-red-700'
              }`}>
                <FiAlertCircle className={`mt-1 flex-shrink-0 ${error.includes('unavailable') || error.includes('503') ? 'text-yellow-400' : 'text-red-500'}`} />
                <div>
                  <h3 className={`font-medium ${error.includes('unavailable') || error.includes('503') ? 'text-yellow-400' : 'text-red-400'}`}>
                    {error.includes('unavailable') || error.includes('503') ? 'AI Service Unavailable' : 'Error'}
                  </h3>
                  <p className="text-slate-300 text-sm mt-1">{error}</p>
                  {(error.includes('unavailable') || error.includes('503')) && (
                    <p className="text-slate-400 text-xs mt-2">
                      Add a valid <code className="bg-slate-700 px-1 rounded">OPENAI_API_KEY=sk-...</code> to <code className="bg-slate-700 px-1 rounded">.env</code> and restart the backend.
                      The <strong>Dashboard</strong> and <strong>Predictive Intelligence</strong> tabs work without an API key.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="p-8 bg-slate-800/50 rounded-lg text-center">
                <div className="inline-block">
                  <div className="w-10 h-10 border-4 border-slate-600 border-t-blue-500 rounded-full animate-spin"></div>
                </div>
                <p className="text-slate-300 mt-4 font-medium">Analyzing fault...</p>
                <p className="text-slate-400 text-sm mt-1">Running multi-agent workflow</p>
              </div>
            )}

            {/* Results */}
            {results && !loading && (
              <ResultsPanel
                results={results}
                onIncidentSelect={(incident) => {
                  setSelectedIncident(incident);
                  setShowDetails(true);
                }}
              />
            )}
          </div>
        )}

        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <Dashboard metrics={metrics} />
        )}

        {/* Predictive Intelligence Tab */}
        {activeTab === 'predictive' && (
          <PredictivePanel />
        )}
      </main>

      {/* Incident Details Modal */}
      {showDetails && selectedIncident && (
        <IncidentDetails
          incident={selectedIncident}
          onClose={() => {
            setShowDetails(false);
            setSelectedIncident(null);
          }}
        />
      )}
    </div>
  );
}

export default App;
