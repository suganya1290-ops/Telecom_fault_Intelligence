import React from 'react';
import { FiX, FiCopy } from 'react-icons/fi';

function IncidentDetails({ incident, onClose }) {
  const inc = incident.incident || {};
  
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const getSeverityColor = (severity) => {
    const colors = {
      critical: 'bg-red-900/30 text-red-300 border-red-700',
      high: 'bg-orange-900/30 text-orange-300 border-orange-700',
      medium: 'bg-yellow-900/30 text-yellow-300 border-yellow-700',
      low: 'bg-green-900/30 text-green-300 border-green-700',
      info: 'bg-cyan-900/30 text-cyan-300 border-cyan-700',
    };
    return colors[severity] || 'bg-slate-900/30 text-slate-300 border-slate-700';
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-2xl w-full max-h-96 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 flex items-center justify-between p-4 border-b border-slate-700 bg-slate-800">
          <div>
            <h2 className="text-xl font-bold text-white">Incident Details</h2>
            <p className="text-slate-400 text-sm">Alarm ID: {inc.alarm_id}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <FiX className="text-white text-xl" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-slate-400 text-sm font-medium">Alarm ID</label>
              <div className="flex items-center gap-2 mt-1">
                <code className="text-white font-mono text-sm bg-slate-700/50 px-2 py-1 rounded">
                  {inc.alarm_id}
                </code>
                <button
                  onClick={() => copyToClipboard(inc.alarm_id)}
                  className="p-1 hover:bg-slate-700 rounded transition-colors"
                >
                  <FiCopy className="text-slate-400 text-sm" />
                </button>
              </div>
            </div>

            <div>
              <label className="text-slate-400 text-sm font-medium">Severity</label>
              <p className={`badge ${getSeverityColor(inc.severity)} mt-1`}>
                {inc.severity?.toUpperCase()}
              </p>
            </div>

            <div>
              <label className="text-slate-400 text-sm font-medium">Network Region</label>
              <p className="text-white mt-1">{inc.network_region}</p>
            </div>

            <div>
              <label className="text-slate-400 text-sm font-medium">Technology Type</label>
              <p className="text-white mt-1">{inc.technology_type}</p>
            </div>

            <div>
              <label className="text-slate-400 text-sm font-medium">Device Vendor</label>
              <p className="text-white mt-1">{inc.device_vendor}</p>
            </div>

            <div>
              <label className="text-slate-400 text-sm font-medium">Outage Duration</label>
              <p className="text-white mt-1">{inc.outage_duration} minutes</p>
            </div>

            <div>
              <label className="text-slate-400 text-sm font-medium">Timestamp</label>
              <p className="text-white mt-1 text-sm">{inc.timestamp}</p>
            </div>

            <div>
              <label className="text-slate-400 text-sm font-medium">Service Impact</label>
              <p className="text-white mt-1">{inc.service_impact}</p>
            </div>
          </div>

          {/* Match Score */}
          <div className="p-4 bg-blue-900/20 border border-blue-700 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <label className="text-blue-300 text-sm font-medium">Match Confidence</label>
              <span className="text-2xl font-bold text-blue-400">
                {Math.round((incident.hybrid_score || 0) * 100)}%
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full"
                style={{ width: `${(incident.hybrid_score || 0) * 100}%` }}
              ></div>
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="text-slate-300 text-sm font-medium block mb-2">
              Incident Description
            </label>
            <div className="p-3 bg-slate-700/30 border border-slate-600 rounded-lg">
              <p className="text-slate-300 text-sm leading-relaxed">
                {inc.incident_description || 'No description available'}
              </p>
            </div>
          </div>

          {/* Resolution Notes */}
          <div>
            <label className="text-slate-300 text-sm font-medium block mb-2">
              Resolution Notes
            </label>
            <div className="p-3 bg-slate-700/30 border border-slate-600 rounded-lg">
              <p className="text-slate-300 text-sm leading-relaxed">
                {inc.resolution_notes || 'No resolution notes available'}
              </p>
            </div>
          </div>

          {/* Close Button */}
          <div className="flex justify-end pt-4">
            <button
              onClick={onClose}
              className="btn btn-primary"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default IncidentDetails;
