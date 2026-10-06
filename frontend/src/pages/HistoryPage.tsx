import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  History as HistoryIcon, 
  Trash2, 
  FileVideo, 
  ArrowRight, 
  ShieldAlert, 
  ShieldCheck, 
  AlertTriangle, 
  Clock, 
  Search,
  Flame,
  Plus
} from 'lucide-react';
import { HistoryItem } from '../types/analysis';
import { getHistory, clearHistory } from '../services/api';

export const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [searchTerm, setSearchTerm] = useState<string>('');

  useEffect(() => {
    setHistoryItems(getHistory());
  }, []);

  const handleClear = () => {
    if (window.confirm('Are you sure you want to clear your local analysis history?')) {
      clearHistory();
      setHistoryItems([]);
    }
  };

  const filteredItems = historyItems.filter((item) =>
    item.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.sha256.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.action.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center space-x-3">
            <HistoryIcon className="w-7 h-7 text-cyan-400" />
            <span>Analysis History</span>
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-400">
            Locally cached forensic reports from your recent video analyses.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {historyItems.length > 0 && (
            <button
              type="button"
              onClick={handleClear}
              className="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-rose-900 text-slate-400 hover:text-rose-400 text-xs font-mono flex items-center space-x-1.5 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear History</span>
            </button>
          )}

          <Link
            to="/"
            className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center space-x-1.5 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>New Analysis</span>
          </Link>
        </div>
      </div>

      {/* Search & Filter */}
      {historyItems.length > 0 && (
        <div className="relative max-w-md">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by filename, SHA-256 or verdict..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-sans"
          />
        </div>
      )}

      {/* History List */}
      {filteredItems.length > 0 ? (
        <div className="grid grid-cols-1 gap-4">
          {filteredItems.map((item) => {
            const isHigh = item.action === 'STOP_AND_VERIFY' || item.fraud_level === 'HIGH' || item.media_verdict === 'LIKELY_MANIPULATED';
            const isMedium = item.action === 'VERIFY' || item.media_verdict === 'SUSPICIOUS';

            return (
              <div
                key={item.id}
                onClick={() => navigate(`/results/${item.id}`, { state: { analysis: item.analysis } })}
                className="glass-panel p-5 rounded-2xl border border-slate-800 hover:border-slate-700 transition-all cursor-pointer group flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                {/* File info */}
                <div className="flex items-start space-x-4">
                  <div className={`p-3 rounded-xl border shrink-0 ${
                    isHigh ? 'bg-rose-950/60 border-rose-900 text-rose-400' :
                    isMedium ? 'bg-amber-950/60 border-amber-900 text-amber-400' :
                    'bg-slate-900 border-slate-800 text-cyan-400'
                  }`}>
                    <FileVideo className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-200 group-hover:text-cyan-300 transition-colors">
                      {item.filename}
                    </h3>
                    <div className="flex flex-wrap items-center gap-2 mt-1 text-xs font-mono text-slate-400">
                      <span>{item.duration_s.toFixed(1)}s</span>
                      <span>·</span>
                      <span>SHA-256: {item.sha256.slice(0, 12)}...</span>
                      <span>·</span>
                      <span>{new Date(item.created_at).toLocaleDateString()} {new Date(item.created_at).toLocaleTimeString()}</span>
                    </div>
                  </div>
                </div>

                {/* Badges & Jump */}
                <div className="flex flex-wrap items-center gap-3">
                  
                  {/* Media verdict */}
                  <div className="text-right">
                    <span className="text-[10px] block font-mono text-slate-500 uppercase">Media Risk</span>
                    <span className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold ${
                      item.media_verdict === 'LIKELY_MANIPULATED' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
                      item.media_verdict === 'SUSPICIOUS' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                      'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    }`}>
                      {item.media_verdict}
                    </span>
                  </div>

                  {/* Fraud risk */}
                  <div className="text-right">
                    <span className="text-[10px] block font-mono text-slate-500 uppercase">Fraud Risk</span>
                    <span className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold ${
                      item.fraud_level === 'HIGH' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
                      item.fraud_level === 'MEDIUM' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                      item.fraud_level === 'LOW' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                      'bg-slate-800 text-slate-400'
                    }`}>
                      {item.fraud_level}
                    </span>
                  </div>

                  {/* Action recommendation */}
                  <div className="text-right">
                    <span className="text-[10px] block font-mono text-slate-500 uppercase">Action</span>
                    <span className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold ${
                      item.action === 'STOP_AND_VERIFY' ? 'bg-rose-600 text-white shadow-[0_0_10px_rgba(244,63,94,0.3)]' :
                      item.action === 'CAUTION' ? 'bg-cyan-600 text-slate-950' :
                      item.action === 'VERIFY' ? 'bg-amber-600 text-white' :
                      'bg-emerald-600 text-white'
                    }`}>
                      {item.action}
                    </span>
                  </div>

                  <div className="p-2 rounded-xl bg-slate-900 border border-slate-800 group-hover:bg-cyan-500 group-hover:text-slate-950 transition-all text-slate-400 ml-2">
                    <ArrowRight className="w-4 h-4" />
                  </div>

                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-12 text-center rounded-2xl glass-panel border border-slate-800">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mb-4">
            <HistoryIcon className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-white">No Analysis History Yet</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            Uploaded videos are processed locally and their forensic summaries will be saved in your browser history.
          </p>
          <Link
            to="/"
            className="mt-5 inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs transition-colors"
          >
            <span>Analyze Your First Media</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      )}

    </div>
  );
};
