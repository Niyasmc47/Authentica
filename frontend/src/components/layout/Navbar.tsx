import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, History, BookOpen, Activity, Lock } from 'lucide-react';
import { checkHealth } from '../../services/api';

export const Navbar: React.FC = () => {
  const location = useLocation();
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);

  useEffect(() => {
    checkHealth().then(res => {
      setServerOnline(res.status === 'ok');
    });
  }, [location.pathname]);

  const isActive = (path: string) => location.pathname === path;

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-cyber-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Logo & Brand */}
          <Link to="/" className="flex items-center space-x-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/40 flex items-center justify-center group-hover:border-cyan-400 group-hover:shadow-[0_0_15px_rgba(6,182,212,0.3)] transition-all">
              <Shield className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-extrabold tracking-wider bg-gradient-to-r from-cyan-400 via-sky-300 to-blue-400 bg-clip-text text-transparent font-mono">
                  AUTHENTICA
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-bold bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
                  v2.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans tracking-tight">AI Media & Fraud Protection</p>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center space-x-1 sm:space-x-2">
            <Link
              to="/"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center space-x-1.5 ${
                isActive('/')
                  ? 'bg-slate-800/90 text-cyan-400 border border-slate-700'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Analyze</span>
            </Link>

            <Link
              to="/history"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center space-x-1.5 ${
                isActive('/history')
                  ? 'bg-slate-800/90 text-cyan-400 border border-slate-700'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <History className="w-4 h-4" />
              <span>History</span>
            </Link>

            <Link
              to="/awareness"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center space-x-1.5 ${
                isActive('/awareness')
                  ? 'bg-slate-800/90 text-cyan-400 border border-slate-700'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              <span>Awareness</span>
            </Link>
          </nav>

          {/* Server / Privacy Status */}
          <div className="hidden sm:flex items-center space-x-3 text-xs font-mono">
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-slate-300">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-[11px]">Local Zero-Retention</span>
            </div>

            <div className="flex items-center space-x-1.5 px-2 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-slate-400">
              <span
                className={`w-2 h-2 rounded-full ${
                  serverOnline === true
                    ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                    : serverOnline === false
                    ? 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.8)]'
                    : 'bg-amber-400 animate-pulse'
                }`}
              />
              <span className="text-[11px]">
                {serverOnline === true ? 'Engine Ready' : serverOnline === false ? 'Offline' : 'Connecting'}
              </span>
            </div>
          </div>

        </div>
      </div>
    </header>
  );
};
