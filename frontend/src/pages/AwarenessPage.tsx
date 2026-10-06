import React from 'react';
import { 
  BookOpen, 
  ShieldAlert, 
  Flame, 
  Eye, 
  Mic, 
  CheckCircle2, 
  AlertTriangle, 
  Layers, 
  Lock, 
  Smartphone, 
  KeyRound, 
  Headphones,
  Check
} from 'lucide-react';

export const AwarenessPage: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
      
      {/* Header */}
      <div className="pb-6 border-b border-slate-800">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-cyan-950/60 border border-cyan-800/60 text-cyan-400 text-xs font-mono mb-3">
          <BookOpen className="w-3.5 h-3.5" />
          <span>Security &amp; Forensics Guide</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          AI Media Forensics &amp; Fraud Awareness Center
        </h1>
        <p className="mt-2 text-sm sm:text-base text-slate-400 max-w-3xl">
          Learn how modern synthetic media and social engineering attacks operate, and discover how to verify high-risk communications independently.
        </p>
      </div>

      {/* Core Principle: Two Independent Dimensions */}
      <div className="p-6 sm:p-8 rounded-2xl glass-panel-glow border border-cyan-500/30 space-y-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-400">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">The Golden Rule: Media Risk $\neq$ Fraud Risk</h2>
            <p className="text-xs text-slate-300">Why Authentica evaluates manipulation and fraud intent as separate dimensions</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
            <div className="flex items-center space-x-2 text-cyan-400 text-xs font-mono font-bold">
              <Eye className="w-4 h-4" />
              <span>DIMENSION 1: MEDIA MANIPULATION</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Analyzes physical and acoustic artifacts: facial warp boundaries, unnatural frequency spectra, and synthetic voice characteristics. 
              <strong> A video can be completely AI-generated without having any fraudulent intent (e.g. harmless art or movie CGI).</strong>
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
            <div className="flex items-center space-x-2 text-rose-400 text-xs font-mono font-bold">
              <Flame className="w-4 h-4" />
              <span>DIMENSION 2: FRAUD INTENT</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Analyzes social engineering directives: urgent payment demands, OTP extraction, secrecy orders, and impersonation. 
              <strong> Authentic, non-manipulated video footage can still be weaponized in financial scams.</strong>
            </p>
          </div>
        </div>
      </div>

      {/* Common Attack Vectors */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-white flex items-center space-x-2">
          <ShieldAlert className="w-5 h-5 text-rose-400" />
          <span>Common Generative AI Fraud Vectors</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-rose-950/60 border border-rose-900 flex items-center justify-center text-rose-400">
              <KeyRound className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-200">CEO / Wire Transfer Fraud</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Synthetic video or voice note impersonating an executive requesting an urgent, confidential wire transfer to a new vendor account.
            </p>
          </div>

          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-amber-950/60 border border-amber-900 flex items-center justify-center text-amber-400">
              <Headphones className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-200">Family Voice Cloning</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Cloned audio of a family member claiming an emergency, car accident, or arrest requiring instant gift card or crypto bail money.
            </p>
          </div>

          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-purple-950/60 border border-purple-900 flex items-center justify-center text-purple-400">
              <Smartphone className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-200">Remote Access Phishing</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Scammers claiming to be IT support or bank security instructing the victim to install AnyDesk, TeamViewer, or share their screen.
            </p>
          </div>

          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-950/60 border border-cyan-900 flex items-center justify-center text-cyan-400">
              <Lock className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-200">OTP / 2FA Interception</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Impersonators demanding that you "read out the one-time verification passcode received on your phone" to unblock your account.
            </p>
          </div>

        </div>
      </div>

      {/* Red Flags Checklist */}
      <div className="glass-panel p-6 sm:p-8 rounded-2xl border border-slate-800 space-y-6">
        <h2 className="text-xl font-bold text-white flex items-center space-x-2">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          <span>Top 5 Red Flags to Watch For</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          
          <div className="flex items-start space-x-3 p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-mono font-bold shrink-0 mt-0.5">
              1
            </div>
            <div>
              <p className="font-bold text-slate-200">Artificial Urgency &amp; Secrecy</p>
              <p className="text-slate-400 mt-1">"Act in the next 10 minutes", "Don't tell anyone in the office", or "Keep this strictly between us".</p>
            </div>
          </div>

          <div className="flex items-start space-x-3 p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-mono font-bold shrink-0 mt-0.5">
              2
            </div>
            <div>
              <p className="font-bold text-slate-200">Changing Established Channels</p>
              <p className="text-slate-400 mt-1">"I lost my phone, reach me on this new number" or "Message me on Telegram/WhatsApp instead".</p>
            </div>
          </div>

          <div className="flex items-start space-x-3 p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-mono font-bold shrink-0 mt-0.5">
              3
            </div>
            <div>
              <p className="font-bold text-slate-200">Any Demand for OTPs or Remote Control</p>
              <p className="text-slate-400 mt-1">No bank, law enforcement, or tech company will ever ask you to read out a 2FA OTP code.</p>
            </div>
          </div>

          <div className="flex items-start space-x-3 p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-mono font-bold shrink-0 mt-0.5">
              4
            </div>
            <div>
              <p className="font-bold text-slate-200">Visual Boundary Artifacts</p>
              <p className="text-slate-400 mt-1">Blurry jawlines, unnatural lack of eye blinks, or mismatched teeth/lip movements during rapid speech.</p>
            </div>
          </div>

        </div>
      </div>

      {/* 3-Step STOP AND VERIFY Protocol */}
      <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-r from-rose-950/40 via-slate-900 to-cyber-950 border border-rose-600/30 space-y-4">
        <h2 className="text-lg font-bold text-white flex items-center space-x-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <span>The 3-Step "STOP AND VERIFY" Protocol</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-black/40 border border-white/10 space-y-1">
            <p className="font-bold text-rose-400">Step 1: Pause Action</p>
            <p className="text-slate-300">Never execute a transaction or disclose sensitive info during an unverified incoming call or video message.</p>
          </div>
          <div className="p-4 rounded-xl bg-black/40 border border-white/10 space-y-1">
            <p className="font-bold text-amber-400">Step 2: Out-of-Band Call</p>
            <p className="text-slate-300">Hang up and initiate a new call using the contact's official number from your corporate directory or address book.</p>
          </div>
          <div className="p-4 rounded-xl bg-black/40 border border-white/10 space-y-1">
            <p className="font-bold text-emerald-400">Step 3: Pre-Agreed Safe Code</p>
            <p className="text-slate-300">Establish a private family or corporate passphrase that generative AI voice clones cannot guess.</p>
          </div>
        </div>
      </div>

    </div>
  );
};
