import React, { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate, Link } from 'react-router-dom';
import { 
  ShieldAlert, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  HelpCircle, 
  Download, 
  Copy, 
  Check, 
  FileVideo, 
  Clock, 
  Layers, 
  Cpu, 
  Mic, 
  Eye, 
  FileCheck2, 
  Info, 
  ArrowLeft,
  Flame,
  KeyRound,
  ExternalLink,
  ShieldQuestion,
  Sparkles
} from 'lucide-react';
import { AnalysisResponse, TimelineEvent, FraudRequestedAction, FraudCategoryEvidence } from '../types/analysis';
import { getAnalysisById, fetchAnalysisById } from '../services/api';

export const ResultsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(() => {
    // Check router state first
    if (location.state && location.state.analysis) {
      return location.state.analysis;
    }
    // Fallback to local history cache
    if (id) {
      return getAnalysisById(id);
    }
    return null;
  });

  const [isLoading, setIsLoading] = useState<boolean>(() => {
    if (location.state && location.state.analysis) return false;
    if (id && getAnalysisById(id)) return false;
    return !!id;
  });
  const [loadError, setLoadError] = useState<string | null>(null);

  const [copiedHash, setCopiedHash] = useState<boolean>(false);
  const [selectedTimelineEvent, setSelectedTimelineEvent] = useState<TimelineEvent | null>(null);

  useEffect(() => {
    if (!analysis && id) {
      const stored = getAnalysisById(id);
      if (stored) {
        setAnalysis(stored);
        setIsLoading(false);
      } else {
        setIsLoading(true);
        setLoadError(null);
        fetchAnalysisById(id)
          .then(fetched => {
            if (fetched) {
              setAnalysis(fetched);
            } else {
              setLoadError("The forensic analysis report was not found on the server or in local session cache.");
            }
          })
          .catch(err => {
            setLoadError(err?.message || "Failed to load forensic analysis.");
          })
          .finally(() => {
            setIsLoading(false);
          });
      }
    } else {
      setIsLoading(false);
    }
  }, [id, analysis]);

  if (isLoading) {
    return (
      <div className="min-h-[calc(100vh-140px)] flex flex-col items-center justify-center p-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-cyan-950/40 border border-cyan-800/60 flex items-center justify-center text-cyan-400 mb-4 animate-pulse">
          <Sparkles className="w-8 h-8 animate-spin" />
        </div>
        <h2 className="text-xl font-bold text-white">Loading Forensic Analysis...</h2>
        <p className="text-sm text-slate-400 mt-2 max-w-md">
          Retrieving multi-modal verification report from Authentica backend engine.
        </p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="min-h-[calc(100vh-140px)] flex flex-col items-center justify-center p-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mb-4">
          <ShieldQuestion className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-white">Analysis Not Found</h2>
        <p className="text-sm text-slate-400 mt-1 max-w-md">
          {loadError || "The requested analysis session ID is not in local memory or was cleared."}
        </p>
        <div className="flex items-center gap-3 mt-6">
          {id && (
            <button
              onClick={() => {
                setIsLoading(true);
                fetchAnalysisById(id).then(fetched => {
                  if (fetched) setAnalysis(fetched);
                  setIsLoading(false);
                });
              }}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-sm transition-colors"
            >
              Retry Connection
            </button>
          )}
          <Link
            to="/"
            className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-sm flex items-center space-x-2 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Upload New Media</span>
          </Link>
        </div>
      </div>
    );
  }

  const { video, visual, audio, speech, reliability, evidence, timeline, assessment, explanation, limitations, fraud } = analysis;

  const mediaVerdict = assessment?.media || 'UNCERTAIN';
  const fraudLevel = assessment?.fraud || fraud?.level || 'NOT_ASSESSABLE';
  const finalAction = assessment?.action || 'VERIFY';

  const copySha256 = () => {
    navigator.clipboard.writeText(video.sha256);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const exportJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(analysis, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `authentica_report_${video.filename}_${analysis.id.slice(0, 8)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // Color & badge helpers
  const getMediaVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case 'LIKELY_MANIPULATED':
        return {
          bg: 'bg-rose-950/80 border-rose-600/70 text-rose-300',
          dot: 'bg-rose-500',
          label: 'LIKELY MANIPULATED',
          desc: 'Multiple visual/acoustic anomalies indicate high-confidence synthetic generation or manipulation.',
          icon: ShieldAlert,
        };
      case 'SUSPICIOUS':
        return {
          bg: 'bg-amber-950/80 border-amber-600/70 text-amber-300',
          dot: 'bg-amber-500',
          label: 'SUSPICIOUS',
          desc: 'Moderate artifacts or single-modality anomalies observed.',
          icon: AlertTriangle,
        };
      case 'NO_STRONG_EVIDENCE':
        return {
          bg: 'bg-emerald-950/80 border-emerald-600/70 text-emerald-300',
          dot: 'bg-emerald-500',
          label: 'NO STRONG EVIDENCE',
          desc: 'No conclusive manipulation artifacts identified within tested detector boundaries.',
          icon: ShieldCheck,
        };
      case 'UNCERTAIN':
      default:
        return {
          bg: 'bg-slate-900/80 border-slate-700 text-slate-300',
          dot: 'bg-slate-400',
          label: 'UNCERTAIN',
          desc: 'Media quality or detector coverage was degraded, preventing reliable classification.',
          icon: HelpCircle,
        };
    }
  };

  const getFraudRiskBadge = (level: string) => {
    switch (level) {
      case 'HIGH':
        return {
          bg: 'bg-rose-950/80 border-rose-600/70 text-rose-300',
          dot: 'bg-rose-500',
          label: 'HIGH FRAUD RISK',
          desc: 'Direct extraction requests (e.g. OTP, wire funds, remote access) paired with social engineering pressure.',
          icon: Flame,
        };
      case 'MEDIUM':
        return {
          bg: 'bg-amber-950/80 border-amber-600/70 text-amber-300',
          dot: 'bg-amber-500',
          label: 'MEDIUM FRAUD RISK',
          desc: 'Suspicious authority or payment mentions without direct extraction directives, or scam reporting context.',
          icon: AlertTriangle,
        };
      case 'LOW':
        return {
          bg: 'bg-emerald-950/80 border-emerald-600/70 text-emerald-300',
          dot: 'bg-emerald-500',
          label: 'LOW FRAUD RISK',
          desc: 'Benign dialogue or artistic speech without social engineering indicators.',
          icon: ShieldCheck,
        };
      case 'NOT_ASSESSABLE':
      default:
        return {
          bg: 'bg-slate-900/80 border-slate-700 text-slate-400',
          dot: 'bg-slate-500',
          label: 'NOT ASSESSABLE',
          desc: 'No speech or audio transcript segments were available to analyze.',
          icon: Info,
        };
    }
  };

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'STOP_AND_VERIFY':
        return {
          panelClass: 'glass-panel-danger border-rose-500/50',
          badgeClass: 'bg-rose-600 text-white font-extrabold shadow-[0_0_15px_rgba(244,63,94,0.4)]',
          title: 'STOP AND VERIFY',
          subtitle: 'High-risk social engineering or direct credential/financial extraction detected.',
          callout: 'Do NOT transfer money, share OTPs, or click unverified links until you independently confirm identity via a trusted secondary channel.',
          icon: ShieldAlert,
        };
      case 'VERIFY':
        return {
          panelClass: 'glass-panel-warning border-amber-500/50',
          badgeClass: 'bg-amber-600 text-white font-extrabold shadow-[0_0_15px_rgba(245,158,11,0.4)]',
          title: 'VERIFY INDEPENDENTLY',
          subtitle: 'Moderate risks, degraded evidence, or suspicious patterns detected.',
          callout: 'Perform secondary verification before trusting the content or acting on instructions.',
          icon: AlertTriangle,
        };
      case 'CAUTION':
        return {
          panelClass: 'glass-panel-glow border-cyan-500/50',
          badgeClass: 'bg-cyan-600 text-slate-950 font-extrabold shadow-[0_0_15px_rgba(6,182,212,0.4)]',
          title: 'EXERCISE CAUTION',
          subtitle: 'Media shows signs of AI manipulation or synthesis (e.g., artistic or benign deepfakes).',
          callout: 'Synthetic media detected. Ensure attribution and authenticity before sharing.',
          icon: Sparkles,
        };
      case 'NO_ACTION_FLAGGED':
      default:
        return {
          panelClass: 'glass-panel-success border-emerald-500/50',
          badgeClass: 'bg-emerald-600 text-white font-extrabold shadow-[0_0_15px_rgba(16,185,129,0.4)]',
          title: 'NO ACTION FLAGGED',
          subtitle: 'No high-risk manipulation or fraud indicators identified.',
          callout: 'Standard security practices apply. Content shows no immediate red flags.',
          icon: CheckCircle2,
        };
    }
  };

  const mediaBadge = getMediaVerdictBadge(mediaVerdict);
  const fraudBadge = getFraudRiskBadge(fraudLevel);
  const actionBadge = getActionBadge(finalAction);

  // Helper for timeline duration
  const totalDuration = video.duration_s || 1.0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* 1. Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center space-x-3">
            <Link
              to="/"
              className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
              title="Back to Upload"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center space-x-2">
              <span>Forensic Analysis Report</span>
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-3 mt-2 text-xs font-mono text-slate-400">
            <span className="flex items-center space-x-1 text-slate-300">
              <FileVideo className="w-3.5 h-3.5 text-cyan-400" />
              <span>{video.filename}</span>
            </span>
            <span>·</span>
            <span>{video.duration_s.toFixed(1)}s ({video.width}×{video.height} @ {video.fps.toFixed(0)}fps)</span>
            <span>·</span>
            <span>Analyzed {new Date(analysis.created_at).toLocaleTimeString()}</span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center space-x-3">
          <button
            type="button"
            onClick={copySha256}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-mono flex items-center space-x-2 transition-colors"
            title="Copy SHA-256 Fingerprint"
          >
            {copiedHash ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
            <span>SHA-256: {video.sha256.slice(0, 10)}...</span>
          </button>

          <button
            type="button"
            onClick={exportJson}
            className="px-4 py-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 hover:bg-cyan-500/20 text-cyan-300 text-xs font-semibold flex items-center space-x-2 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export JSON</span>
          </button>
        </div>
      </div>

      {/* 2. Top Risk & Action Section */}
      <div className="space-y-4">
        
        {/* Main Action Banner */}
        <div className={`p-6 sm:p-8 rounded-2xl border transition-all ${actionBadge.panelClass}`}>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center space-x-3">
                <span className={`px-3 py-1 rounded-lg text-xs tracking-wider uppercase font-mono ${actionBadge.badgeClass}`}>
                  RECOMMENDATION: {actionBadge.title}
                </span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">{actionBadge.subtitle}</h2>
              <p className="text-sm text-slate-300 max-w-3xl leading-relaxed">{actionBadge.callout}</p>
            </div>

            <div className="shrink-0 p-4 rounded-2xl bg-black/40 border border-white/10 flex items-center space-x-4">
              <actionBadge.icon className="w-12 h-12 text-white/90" />
            </div>
          </div>
        </div>

        {/* Orthogonal Dimension Cards (Media Risk vs Fraud Risk) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          
          {/* Dimension 1: Media Manipulation Risk */}
          <div className={`p-6 rounded-2xl border flex flex-col justify-between ${mediaBadge.bg}`}>
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                  <Eye className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Media Manipulation Dimension</span>
                </span>
                <span className={`w-2.5 h-2.5 rounded-full ${mediaBadge.dot}`} />
              </div>
              <div className="mt-3">
                <h3 className="text-2xl font-black tracking-tight">{mediaBadge.label}</h3>
                <p className="mt-1 text-xs text-slate-300 leading-relaxed">{mediaBadge.desc}</p>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400">Visual &amp; Voice Synthesis Check</span>
              <span className="text-slate-200">
                {evidence?.reliability.level === 'OK' ? 'Reliability OK' : 'Low Quality Media'}
              </span>
            </div>
          </div>

          {/* Dimension 2: Fraud Intent Risk */}
          <div className={`p-6 rounded-2xl border flex flex-col justify-between ${fraudBadge.bg}`}>
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                  <Flame className="w-3.5 h-3.5 text-rose-400" />
                  <span>Fraud Intent Dimension</span>
                </span>
                <span className={`w-2.5 h-2.5 rounded-full ${fraudBadge.dot}`} />
              </div>
              <div className="mt-3">
                <h3 className="text-2xl font-black tracking-tight">{fraudBadge.label}</h3>
                <p className="mt-1 text-xs text-slate-300 leading-relaxed">{fraudBadge.desc}</p>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400">Social Engineering &amp; Demands</span>
              <span className="text-slate-200">
                {fraud?.news_context_downgrade ? 'News/Report Context' : `${fraud?.categories.length || 0} Categories Flagged`}
              </span>
            </div>
          </div>

        </div>

        {/* Orthogonal note */}
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 flex items-center space-x-2">
          <Info className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>
            <strong>Independent Dimensions:</strong> Authentic media can be used in scams (e.g. real CEO footage with fake demands), while synthetic media can be benign/artistic (e.g. parody videos).
          </span>
        </div>

      </div>

      {/* 3. Stage 2 Evidence Matrix */}
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center space-x-2">
              <Layers className="w-5 h-5 text-cyan-400" />
              <span>Evidence Matrix (Stage 2 Synthesis)</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Multi-modal forensic sensor outputs evaluated by the Reliability Gate.
            </p>
          </div>
          <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-3 py-1 rounded-lg border border-slate-800">
            Model scores are raw forensic activations, not probabilities
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* Card 1: Visual Modality */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400 flex items-center space-x-1.5">
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                <span>Visual Forensics</span>
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                evidence?.visual.level === 'HIGH' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
                evidence?.visual.level === 'MEDIUM' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                'bg-emerald-950 text-emerald-400 border border-emerald-800'
              }`}>
                {evidence?.visual.level || 'N/A'}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-200">{visual.model || 'EfficientNet-B0-FFPP-C23'}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-1">
                Peak Score: {evidence?.visual.models[0]?.score.toFixed(4) ?? visual.results[0]?.fake_score?.toFixed(4) ?? '0.0000'}
              </p>
              <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                Faces Analyzed: {visual.faces_found}/{visual.frames_analyzed} frames
              </p>
            </div>
          </div>

          {/* Card 2: Audio Anti-Spoofing */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400 flex items-center space-x-1.5">
                <Mic className="w-3.5 h-3.5 text-purple-400" />
                <span>Audio Anti-Spoof</span>
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                evidence?.audio.level === 'HIGH' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
                evidence?.audio.level === 'MEDIUM' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                evidence?.audio.level === 'LOW' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                'bg-slate-800 text-slate-400'
              }`}>
                {evidence?.audio.level || 'N/A'}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-200">{audio.model || 'AASIST-ASVspoof2019-LA'}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-1">
                Peak Score: {evidence?.audio.models[0]?.score.toFixed(4) ?? audio.results[0]?.spoof_score?.toFixed(4) ?? '0.0000'}
              </p>
              <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                Windows: {audio.windows_analyzed ?? 0} ({audio.processing_time_s?.toFixed(2) ?? '0.00'}s)
              </p>
            </div>
          </div>

          {/* Card 3: C2PA Provenance */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400 flex items-center space-x-1.5">
                <FileCheck2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>Provenance (C2PA)</span>
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                evidence?.provenance.state === 'FOUND' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                'bg-slate-800 text-slate-400 border border-slate-700'
              }`}>
                {evidence?.provenance.state || 'NONE_FOUND'}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-200">
                {evidence?.provenance.signer ? `Signer: ${evidence.provenance.signer}` : 'Content Credentials'}
              </p>
              <p className="text-[11px] text-slate-400 font-sans mt-1 leading-snug">
                {evidence?.provenance.note || 'Absence of credentials does not imply manipulation.'}
              </p>
            </div>
          </div>

          {/* Card 4: Reliability Gate */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400 flex items-center space-x-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
                <span>Reliability Gate</span>
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                reliability?.level === 'OK' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                'bg-amber-950 text-amber-400 border border-amber-800'
              }`}>
                {reliability?.level || 'OK'}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-200">
                {reliability?.level === 'OK' ? 'Quality Criteria Met' : 'Degraded Quality / Warnings'}
              </p>
              <div className="mt-1 text-[11px] text-slate-400">
                {reliability?.reasons && reliability.reasons.length > 0 ? (
                  <ul className="list-disc list-inside space-y-0.5 text-amber-300">
                    {reliability.reasons.map((r, i) => (
                      <li key={i} className="truncate">{r}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-emerald-400">Resolution, duration &amp; face coverage pass thresholds.</p>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* 4. Interactive Horizontal Evidence Timeline */}
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center space-x-2">
              <Clock className="w-5 h-5 text-cyan-400" />
              <span>Multi-Modal Evidence Timeline</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Chronological alignment of visual artifacts, acoustic anomalies, fraud triggers, and speech segments.
            </p>
          </div>
          <div className="flex items-center space-x-3 text-xs font-mono text-slate-400">
            <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded bg-rose-500 inline-block"/><span>High Anomaly</span></span>
            <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded bg-amber-500 inline-block"/><span>Medium</span></span>
            <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded bg-cyan-500 inline-block"/><span>Speech</span></span>
          </div>
        </div>

        {/* Timeline Tracks */}
        <div className="p-4 sm:p-6 rounded-xl bg-cyber-950 border border-slate-800 space-y-4 relative overflow-hidden">
          
          {/* Time axis markers */}
          <div className="flex justify-between text-[11px] font-mono text-slate-500 border-b border-slate-800 pb-2">
            <span>00:00</span>
            <span>{(totalDuration * 0.25).toFixed(1)}s</span>
            <span>{(totalDuration * 0.50).toFixed(1)}s</span>
            <span>{(totalDuration * 0.75).toFixed(1)}s</span>
            <span>{totalDuration.toFixed(1)}s</span>
          </div>

          {/* Track 1: Visual Windows */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono text-slate-400">
              <span className="flex items-center space-x-1.5">
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                <span>VISUAL DETECTIONS</span>
              </span>
            </div>
            <div className="h-6 w-full bg-slate-900 rounded-lg relative overflow-hidden flex items-center">
              {visual.results.map((vr, i) => {
                const left = (vr.timestamp_s / totalDuration) * 100;
                const width = Math.max((1.0 / totalDuration) * 100, 3);
                const isHigh = (vr.fake_score || 0) >= 0.70;
                return (
                  <div
                    key={i}
                    style={{ left: `${left}%`, width: `${width}%` }}
                    onClick={() => setSelectedTimelineEvent({
                      start_s: vr.timestamp_s,
                      end_s: vr.timestamp_s + 1.0,
                      kind: 'visual',
                      level: isHigh ? 'HIGH' : 'LOW',
                      evidence_source: 'EfficientNet-B0 Face Crop',
                      score: vr.fake_score,
                    })}
                    className={`absolute h-4 rounded cursor-pointer transition-all hover:scale-110 ${
                      isHigh ? 'bg-rose-500 hover:bg-rose-400' : 'bg-emerald-600/60 hover:bg-emerald-500'
                    }`}
                    title={`Visual @ ${vr.timestamp_s.toFixed(1)}s | Fake Score: ${(vr.fake_score || 0).toFixed(4)}`}
                  />
                );
              })}
            </div>
          </div>

          {/* Track 2: Audio Windows */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono text-slate-400">
              <span className="flex items-center space-x-1.5">
                <Mic className="w-3.5 h-3.5 text-purple-400" />
                <span>AUDIO WINDOWS</span>
              </span>
            </div>
            <div className="h-6 w-full bg-slate-900 rounded-lg relative overflow-hidden flex items-center">
              {audio.results.map((ar, i) => {
                const left = (ar.start_s / totalDuration) * 100;
                const width = Math.max(((ar.end_s - ar.start_s) / totalDuration) * 100, 4);
                const isHigh = (ar.spoof_score || 0) >= 0.70;
                return (
                  <div
                    key={i}
                    style={{ left: `${left}%`, width: `${width}%` }}
                    onClick={() => setSelectedTimelineEvent({
                      start_s: ar.start_s,
                      end_s: ar.end_s,
                      kind: 'audio',
                      level: isHigh ? 'HIGH' : 'LOW',
                      evidence_source: 'AASIST Audio Window',
                      score: ar.spoof_score,
                    })}
                    className={`absolute h-4 rounded cursor-pointer transition-all hover:scale-110 ${
                      isHigh ? 'bg-purple-500 hover:bg-purple-400' : 'bg-emerald-600/60 hover:bg-emerald-500'
                    }`}
                    title={`Audio window [${ar.start_s.toFixed(1)}s - ${ar.end_s.toFixed(1)}s] | Spoof Score: ${(ar.spoof_score || 0).toFixed(4)}`}
                  />
                );
              })}
            </div>
          </div>

          {/* Track 3: Fraud Intent Triggers */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono text-slate-400">
              <span className="flex items-center space-x-1.5">
                <Flame className="w-3.5 h-3.5 text-rose-400" />
                <span>FRAUD INTENT SPANS</span>
              </span>
            </div>
            <div className="h-6 w-full bg-slate-900 rounded-lg relative overflow-hidden flex items-center">
              {fraud?.requested_actions && fraud.requested_actions.length > 0 ? (
                fraud.requested_actions.map((act, i) => {
                  const left = (act.start_s / totalDuration) * 100;
                  const width = Math.max(((act.end_s - act.start_s) / totalDuration) * 100, 6);
                  return (
                    <div
                      key={i}
                      style={{ left: `${left}%`, width: `${width}%` }}
                      onClick={() => setSelectedTimelineEvent({
                        start_s: act.start_s,
                        end_s: act.end_s,
                        kind: 'fraud',
                        level: 'HIGH',
                        evidence_source: `Action: ${act.action}`,
                        score: null,
                      })}
                      className="absolute h-4 rounded bg-rose-600 hover:bg-rose-500 cursor-pointer shadow-[0_0_8px_rgba(244,63,94,0.5)] flex items-center justify-center text-[9px] font-mono text-white"
                      title={`Fraud Action: ${act.action} ("${act.phrase}")`}
                    >
                      {act.action.slice(0, 10)}
                    </div>
                  );
                })
              ) : (
                <div className="text-[11px] font-mono text-slate-600 pl-3">No direct extraction triggers</div>
              )}
            </div>
          </div>

          {/* Track 4: Speech Segments */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono text-slate-400">
              <span className="flex items-center space-x-1.5">
                <FileCheck2 className="w-3.5 h-3.5 text-cyan-400" />
                <span>TRANSCRIPT SEGMENTS</span>
              </span>
            </div>
            <div className="h-6 w-full bg-slate-900 rounded-lg relative overflow-hidden flex items-center">
              {speech.segments.map((seg, i) => {
                const left = (seg.start_s / totalDuration) * 100;
                const width = Math.max(((seg.end_s - seg.start_s) / totalDuration) * 100, 5);
                return (
                  <div
                    key={i}
                    style={{ left: `${left}%`, width: `${width}%` }}
                    onClick={() => setSelectedTimelineEvent({
                      start_s: seg.start_s,
                      end_s: seg.end_s,
                      kind: 'speech',
                      level: 'INFO',
                      evidence_source: `Transcript: "${seg.text}"`,
                      score: null,
                    })}
                    className="absolute h-4 rounded bg-cyan-700/70 hover:bg-cyan-600 cursor-pointer text-[9px] font-mono text-cyan-200 px-1 truncate"
                    title={`[${seg.start_s.toFixed(1)}s - ${seg.end_s.toFixed(1)}s]: "${seg.text}"`}
                  >
                    {seg.text}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected event drawer preview */}
          {selectedTimelineEvent && (
            <div className="mt-4 p-3 rounded-xl bg-slate-900 border border-cyan-500/30 flex items-center justify-between animate-fadeIn">
              <div className="text-xs">
                <span className="font-mono text-cyan-400 font-bold">
                  [{selectedTimelineEvent.start_s.toFixed(1)}s – {selectedTimelineEvent.end_s.toFixed(1)}s]
                </span>
                <span className="text-slate-300 ml-2">{selectedTimelineEvent.evidence_source}</span>
                {selectedTimelineEvent.score !== null && (
                  <span className="ml-2 font-mono text-slate-400">
                    (Score: {selectedTimelineEvent.score.toFixed(4)})
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => setSelectedTimelineEvent(null)}
                className="text-xs text-slate-400 hover:text-slate-200"
              >
                Close
              </button>
            </div>
          )}

        </div>
      </div>

      {/* 5. Stage 3 Fraud Intent Findings & Requested Directives */}
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center space-x-2">
              <Flame className="w-5 h-5 text-rose-400" />
              <span>Social-Engineering &amp; Fraud Directives (Stage 3)</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Extracted directive extraction patterns and category indicators from spoken speech.
            </p>
          </div>
          {fraud?.news_context_downgrade && (
            <span className="px-2.5 py-1 rounded-full bg-cyan-950 border border-cyan-800 text-cyan-300 text-xs font-mono">
              Scam Awareness Context Detected (Downgraded)
            </span>
          )}
        </div>

        {/* Direct Requested Actions */}
        {fraud?.requested_actions && fraud.requested_actions.length > 0 ? (
          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-rose-400 font-bold">
              Detected High-Risk Extraction Directives
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {fraud.requested_actions.map((act, i) => (
                <div key={i} className="p-4 rounded-xl bg-rose-950/40 border border-rose-900/60 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-rose-900 text-rose-200">
                      {act.action}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      {act.start_s.toFixed(1)}s – {act.end_s.toFixed(1)}s
                    </span>
                  </div>
                  <p className="text-xs text-rose-100 italic bg-black/40 p-2.5 rounded-lg border border-rose-950">
                    "{act.phrase}"
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
            No direct extortion or extraction directives (OTP theft, wire transfer demands, remote software) were detected in the transcript.
          </div>
        )}

        {/* Detected Categories */}
        {fraud?.categories && fraud.categories.length > 0 && (
          <div className="space-y-3 pt-4 border-t border-slate-800/80">
            <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400">
              Matched Social-Engineering Tactics
            </h3>
            <div className="flex flex-wrap gap-2">
              {fraud.categories.map((cat, i) => (
                <span
                  key={i}
                  className={`px-3 py-1.5 rounded-xl text-xs font-mono font-semibold border ${
                    cat.severity === 'HIGH'
                      ? 'bg-rose-950/80 border-rose-800 text-rose-300'
                      : 'bg-amber-950/80 border-amber-800 text-amber-300'
                  }`}
                >
                  {cat.category} ({cat.evidence.length} triggers)
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 6. Explanations & Limitations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Explanations */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-4">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <Info className="w-4 h-4 text-cyan-400" />
            <span>Grounded Media Explanations</span>
          </h2>
          <ul className="space-y-2.5 text-xs text-slate-300">
            {explanation.map((exp, i) => (
              <li key={i} className="flex items-start space-x-2">
                <span className="text-cyan-400 font-bold shrink-0">·</span>
                <span className="leading-relaxed">{exp}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Limitations */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-4">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Forensic Limitations &amp; Disclaimers</span>
          </h2>
          <ul className="space-y-2.5 text-xs text-slate-400">
            {limitations.map((lim, i) => (
              <li key={i} className="flex items-start space-x-2">
                <span className="text-amber-400 font-bold shrink-0">·</span>
                <span className="leading-relaxed">{lim}</span>
              </li>
            ))}
          </ul>
        </div>

      </div>

      {/* 7. Actionable Safe Steps Checklist */}
      <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-br from-slate-900 to-cyber-950 border border-cyan-500/20 space-y-4">
        <h2 className="text-lg font-bold text-white flex items-center space-x-2">
          <ShieldCheck className="w-5 h-5 text-cyan-400" />
          <span>Recommended Next Steps &amp; Verification Protocol</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1.5">
            <p className="font-bold text-slate-200">1. Out-of-Band Call</p>
            <p className="text-slate-400">Call the claimed sender on their known, saved phone number — not any new number provided in the video.</p>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1.5">
            <p className="font-bold text-slate-200">2. Never Share Secrets</p>
            <p className="text-slate-400">Banks and legitimate executives will never ask you to read out 2FA OTP codes or wire funds secretly.</p>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1.5">
            <p className="font-bold text-slate-200">3. Report Incident</p>
            <p className="text-slate-400">If financial or credential theft was attempted, immediately alert your security team or fraud department.</p>
          </div>
        </div>
      </div>

    </div>
  );
};
