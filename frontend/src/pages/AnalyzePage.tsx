import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  UploadCloud, 
  FileVideo, 
  Music,
  CheckCircle2, 
  AlertTriangle, 
  ShieldAlert, 
  Lock, 
  Layers, 
  Clock, 
  FileCheck,
  X,
  ArrowRight,
  Loader2,
  Headphones
} from 'lucide-react';
import { analyzeVideo, ApiError } from '../services/api';

const MAX_FILE_SIZE_MB = 100;
const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.webm', '.mkv'];
const AUDIO_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac', '.wma'];
const ALLOWED_EXTENSIONS = [...VIDEO_EXTENSIONS, ...AUDIO_EXTENSIONS];

const VIDEO_STEPS = [
  'Media validated & container parsed',
  'Extracting video frames & audio stream',
  'Running visual facial manipulation detection (EfficientNet-B0)',
  'Running acoustic anti-spoofing analysis (AASIST)',
  'Transcribing speech & detecting language (Whisper)',
  'Inspecting C2PA Content Credentials provenance',
  'Synthesizing multi-modal evidence timeline',
  'Evaluating social-engineering & fraud indicators',
];

const AUDIO_STEPS = [
  'Audio container & format validated',
  'Extracting 16kHz forensic audio waveform',
  'Running acoustic anti-spoofing analysis (AASIST)',
  'Transcribing speech & detecting language (Whisper)',
  'Inspecting C2PA Content Credentials provenance',
  'Synthesizing acoustic timeline events',
  'Evaluating social-engineering & fraud indicators',
];

export const AnalyzePage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);

  const isAudioFile = selectedFile 
    ? AUDIO_EXTENSIONS.some(ext => selectedFile.name.toLowerCase().endsWith(ext)) || selectedFile.type.startsWith('audio/')
    : false;

  const currentSteps = isAudioFile ? AUDIO_STEPS : VIDEO_STEPS;

  // Deterministic step advancement during active upload/processing
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isAnalyzing) {
      setCurrentStepIndex(0);
      interval = setInterval(() => {
        setCurrentStepIndex((prev) => {
          if (prev < currentSteps.length - 1) {
            return prev + 1;
          }
          return prev;
        });
      }, 1400);
    }
    return () => clearInterval(interval);
  }, [isAnalyzing, currentSteps.length]);

  const validateFile = (file: File): boolean => {
    setError(null);
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file format "${ext}". Supported: ${ALLOWED_EXTENSIONS.join(', ')}`);
      return false;
    }

    const sizeMB = file.size / (1024 * 1024);
    if (sizeMB > MAX_FILE_SIZE_MB) {
      setError(`File size (${sizeMB.toFixed(1)} MB) exceeds maximum allowed limit of ${MAX_FILE_SIZE_MB} MB.`);
      return false;
    }

    if (file.size === 0) {
      setError('Selected file is empty (0 bytes).');
      return false;
    }

    return true;
  };

  const handleFileSelect = (file: File) => {
    if (validateFile(file)) {
      setSelectedFile(file);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleStartAnalysis = async () => {
    if (!selectedFile) return;

    setIsAnalyzing(true);
    setError(null);

    try {
      const result = await analyzeVideo(selectedFile);
      navigate(`/results/${result.id}`, { state: { analysis: result } });
    } catch (err: any) {
      setIsAnalyzing(false);
      if (err instanceof ApiError) {
        setError(`Analysis Error (${err.status}): ${err.detail}`);
      } else {
        setError(err.message || 'An unexpected error occurred during analysis.');
      }
    }
  };

  return (
    <div className="min-h-[calc(100vh-140px)] flex flex-col justify-center py-10 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
      
      {/* Title Section */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-cyan-950/60 border border-cyan-800/60 text-cyan-400 text-xs font-mono mb-4">
          <Layers className="w-3.5 h-3.5" />
          <span>Stage 1 · Stage 2 · Stage 3 Integrated Engine</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          AI Media Authenticity &amp; Fraud Protection
        </h1>
        <p className="mt-3 text-sm sm:text-base text-slate-400 max-w-2xl mx-auto">
          Analyze suspicious video or standalone audio files for synthetic manipulation, cloned voices, and social-engineering fraud directives.
        </p>
      </div>

      {/* Main Upload / Processing Card */}
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 shadow-2xl relative overflow-hidden">
        
        {/* Top ambient glow line */}
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-75" />

        {!isAnalyzing ? (
          <div>
            {/* Dropzone */}
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 sm:p-12 text-center cursor-pointer transition-all duration-200 ${
                dragActive 
                  ? 'border-cyan-400 bg-cyan-950/30 shadow-[0_0_20px_rgba(6,182,212,0.15)]' 
                  : 'border-slate-700/80 hover:border-slate-600 bg-slate-900/40 hover:bg-slate-900/70'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={ALLOWED_EXTENSIONS.join(',')}
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileSelect(e.target.files[0]);
                  }
                }}
              />

              <div className="w-16 h-16 mx-auto rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-4 text-cyan-400">
                <UploadCloud className="w-8 h-8" />
              </div>

              <p className="text-base font-medium text-slate-200">
                Drag &amp; drop your video or audio file here, or <span className="text-cyan-400 underline underline-offset-4">browse files</span>
              </p>

              <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs font-mono text-slate-400">
                <span className="px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700/60 text-cyan-300">Video: MP4, MOV, WEBM, AVI, MKV</span>
                <span className="px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700/60 text-purple-300">Audio: WAV, MP3, M4A, FLAC, OGG, AAC</span>
                <span className="px-2 py-1 rounded bg-slate-800/80 border border-slate-700/60">Max {MAX_FILE_SIZE_MB}MB</span>
                <span className="px-2 py-1 rounded bg-slate-800/80 border border-slate-700/60">Max 90s</span>
              </div>
            </div>

            {/* Selected File Card */}
            {selectedFile && (
              <div className="mt-5 p-4 rounded-xl bg-slate-900/90 border border-slate-700 flex items-center justify-between animate-fadeIn">
                <div className="flex items-center space-x-3 truncate">
                  <div className={`p-2.5 rounded-lg border ${
                    isAudioFile 
                      ? 'bg-purple-950 border-purple-800 text-purple-400' 
                      : 'bg-cyan-950 border-cyan-800 text-cyan-400'
                  }`}>
                    {isAudioFile ? <Music className="w-5 h-5" /> : <FileVideo className="w-5 h-5" />}
                  </div>
                  <div className="truncate">
                    <div className="flex items-center space-x-2">
                      <p className="text-sm font-semibold text-slate-200 truncate">{selectedFile.name}</p>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                        isAudioFile ? 'bg-purple-950 text-purple-300 border border-purple-800' : 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                      }`}>
                        {isAudioFile ? 'AUDIO' : 'VIDEO'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · {selectedFile.type || (isAudioFile ? 'audio' : 'video')}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
                  title="Remove file"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="mt-5 p-4 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-300 text-sm flex items-start space-x-3">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Validation / Server Error</p>
                  <p className="text-xs text-rose-200/90 mt-0.5">{error}</p>
                </div>
              </div>
            )}

            {/* Bottom Actions & Privacy Badge */}
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-4 pt-6 border-t border-slate-800/80">
              <div className="flex items-center space-x-2 text-xs text-slate-400">
                <Lock className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>Processed locally:</strong> Zero retention. Never sent to cloud AI APIs.</span>
              </div>

              <button
                type="button"
                disabled={!selectedFile}
                onClick={handleStartAnalysis}
                className={`w-full sm:w-auto px-6 py-3 rounded-xl font-semibold text-sm flex items-center justify-center space-x-2 transition-all shadow-lg ${
                  selectedFile
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold shadow-cyan-500/20 cursor-pointer'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                }`}
              >
                <span>Analyze {isAudioFile ? 'Audio' : 'Media'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : (
          /* Processing State UI with deterministic stages */
          <div className="py-6 px-2 sm:px-4">
            <div className="text-center mb-8">
              <div className="w-14 h-14 mx-auto rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center mb-4 text-cyan-400 relative">
                <Loader2 className="w-7 h-7 animate-spin" />
                <div className="absolute inset-0 rounded-2xl border border-cyan-400/40 animate-ping opacity-25" />
              </div>
              <h3 className="text-xl font-bold text-white">
                Analyzing {isAudioFile ? 'Audio' : 'Media'} Security &amp; Fraud Risk
              </h3>
              <p className="text-xs font-mono text-slate-400 mt-1">
                Processing: <span className="text-cyan-300">{selectedFile?.name}</span>
              </p>
            </div>

            {/* Stages checklist */}
            <div className="space-y-3 max-w-xl mx-auto">
              {currentSteps.map((step, idx) => {
                const isDone = idx < currentStepIndex;
                const isCurrent = idx === currentStepIndex;

                return (
                  <div
                    key={idx}
                    className={`flex items-center space-x-3 p-3 rounded-xl border transition-all ${
                      isDone
                        ? 'bg-slate-900/60 border-slate-800 text-slate-300'
                        : isCurrent
                        ? 'bg-cyan-950/40 border-cyan-600/60 text-cyan-300 shadow-[0_0_15px_rgba(6,182,212,0.1)]'
                        : 'bg-slate-950/40 border-slate-900/60 text-slate-600'
                    }`}
                  >
                    <div className="shrink-0">
                      {isDone ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : isCurrent ? (
                        <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                      ) : (
                        <div className="w-4 h-4 rounded-full border border-slate-700 flex items-center justify-center text-[10px] text-slate-600">
                          {idx + 1}
                        </div>
                      )}
                    </div>
                    <span className="text-xs sm:text-sm font-medium">{step}</span>
                  </div>
                );
              })}
            </div>

            <div className="mt-8 text-center text-xs text-slate-500 font-mono">
              Running native PyTorch AASIST &amp; Faster-Whisper models locally...
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
