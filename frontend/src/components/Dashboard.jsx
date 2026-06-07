import React from 'react';
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts';
import { FiTrendingUp, FiTrendingDown, FiAlertTriangle, FiClock } from 'react-icons/fi';

function Dashboard({ metrics }) {
  if (!metrics) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">Loading dashboard metrics...</p>
      </div>
    );
  }

  const COLORS = ['#dc2626', '#f97316', '#eab308', '#22c55e', '#06b6d4'];

  const severityData = Object.entries(metrics.incidents_by_severity || {}).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: value
  }));

  const technologyData = Object.entries(metrics.incidents_by_technology || {}).map(([name, value]) => ({
    name,
    value
  }));

  const regionData = Object.entries(metrics.incidents_by_region || {}).map(([name, value]) => ({
    name,
    value
  }));

  const vendorData = Object.entries(metrics.incidents_by_vendor || {}).map(([name, value]) => ({
    name,
    value
  }));

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-slate-400 text-sm font-medium">Total Incidents</p>
            <FiTrendingUp className="text-blue-500 text-lg" />
          </div>
          <p className="text-3xl font-bold text-white">{metrics.total_incidents || 0}</p>
          <p className="text-slate-400 text-xs mt-2">in database</p>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-slate-400 text-sm font-medium">Avg Outage Duration</p>
            <FiClock className="text-green-500 text-lg" />
          </div>
          <p className="text-3xl font-bold text-white">{(metrics.average_outage_duration || 0).toFixed(1)} min</p>
          <p className="text-slate-400 text-xs mt-2">mean duration</p>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-slate-400 text-sm font-medium">Mean Time to Resolution</p>
            <FiAlertTriangle className="text-orange-500 text-lg" />
          </div>
          <p className="text-3xl font-bold text-white">{(metrics.mttr || 0).toFixed(1)} min</p>
          <p className="text-slate-400 text-xs mt-2">MTTR</p>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-slate-400 text-sm font-medium">Critical Incidents</p>
            <FiTrendingDown className="text-red-500 text-lg" />
          </div>
          <p className="text-3xl font-bold text-red-400">{metrics.incidents_by_severity?.critical || 0}</p>
          <p className="text-slate-400 text-xs mt-2">this month</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Incidents by Severity */}
        <div className="card p-4">
          <h3 className="text-lg font-bold text-white mb-4">Incidents by Severity</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={severityData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value}`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {severityData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Incidents by Technology */}
        <div className="card p-4">
          <h3 className="text-lg font-bold text-white mb-4">Incidents by Technology</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={technologyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis dataKey="name" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }} />
              <Bar dataKey="value" fill="#0ea5e9" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Incidents by Region */}
        <div className="card p-4">
          <h3 className="text-lg font-bold text-white mb-4">Incidents by Region</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={regionData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis dataKey="name" type="category" stroke="#94a3b8" width={100} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }} />
              <Bar dataKey="value" fill="#f97316" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Incidents by Vendor */}
        <div className="card p-4">
          <h3 className="text-lg font-bold text-white mb-4">Incidents by Vendor</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={vendorData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis dataKey="name" stroke="#94a3b8" angle={-45} textAnchor="end" height={80} />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }} />
              <Bar dataKey="value" fill="#22c55e" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
