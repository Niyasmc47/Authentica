import React from 'react';
import { ShieldCheck, Cpu, HardDrive, AlertCircle } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="mt-auto border-t border-slate-900 bg-cyber-950/90 py-8 text-xs text-slate-500">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
          
          {/* Col 1: System info */}
          <div className="flex items-center space-x-2.5">
            <ShieldCheck className="w-5 h-5 text-cyan-500 shrink-0" />
            <div>
              <p className="font-semibold text-slate-300">AUTHENTICA Forensics Engine</p>
              <p className="text-[11px] text-slate-500">Multi-modal deepfake detection & fraud intent analysis</p>
            </div>
          </div>

          {/* Col 2: Engine specs */}
          <div className="flex flex-wrap items-center gap-3 justify-start md:justify-center font-mono text-[11px]">
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
              <Cpu className="w-3 h-3 text-cyan-400" />
              <span>EfficientNet-B0 + AASIST + Whisper</span>
            </span>
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
              <HardDrive className="w-3 h-3 text-emerald-400" />
              <span>C2PA Provenance</span>
            </span>
          </div>

          {/* Col 3: Disclaimer */}
          <div className="text-left md:text-right text-[11px] text-slate-500">
            <p className="flex items-center md:justify-end space-x-1">
              <AlertCircle className="w-3.5 h-3.5 text-amber-500/80 inline shrink-0" />
              <span>Probabilistic advisory tool. Always verify high-risk actions.</span>
            </p>
            <p className="mt-0.5 text-slate-600">Zero data retention · Media purged immediately upon processing</p>
          </div>

        </div>
      </div>
    </footer>
  );
};
