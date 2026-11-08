import React, { useState } from 'react';
import { ArrowRight, ArrowLeft, CheckCircle2, ShieldCheck, Loader2, UserCheck } from 'lucide-react';

export interface OperatorProfile {
  name: string;
  email: string;
  role: string;
}

interface AuthPageProps {
  userProfile: OperatorProfile | null;
  onLoginSuccess: (profile: OperatorProfile) => void;
  onContinueGuest: () => void;
  onContinueLoggedIn: () => void;
  onBack: () => void;
}

export const AuthPage: React.FC<AuthPageProps> = ({
  userProfile,
  onLoginSuccess,
  onContinueGuest,
  onContinueLoggedIn,
  onBack,
}) => {
  const [isSigningIn, setIsSigningIn] = useState(false);

  const handleGoogleSignIn = () => {
    setIsSigningIn(true);
    setTimeout(() => {
      const profile: OperatorProfile = {
        name: 'Physical AI Researcher',
        email: 'operator@isaacsim-gemini.ai',
        role: 'Lead Robotics Operator',
      };
      try {
        localStorage.setItem('isaac_operator_profile', JSON.stringify(profile));
      } catch {}
      setIsSigningIn(false);
      onLoginSuccess(profile);
    }, 350);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-950 to-black text-white flex flex-col items-center justify-center p-4 sm:p-6 select-none">
      <div className="w-full max-w-md bg-slate-900/90 backdrop-blur-xl rounded-3xl p-7 sm:p-9 border-2 border-b-4 border-slate-800 shadow-2xl space-y-6 text-center">
        <div className="flex items-center justify-between text-xs font-mono text-slate-400">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1 hover:text-white cursor-pointer font-bold"
          >
            <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Opening</span>
          </button>
          <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-[11px] font-extrabold">
            STEP 1 / 2 · Sign In
          </span>
        </div>

        <div className="w-16 h-16 mx-auto rounded-2xl bg-slate-800 border-2 border-b-4 border-slate-700 flex items-center justify-center shadow-sm">
          <svg className="w-8 h-8" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z" />
            <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.35 24 12 24z" />
            <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 10.04 0 12s.45 3.82 1.25 5.42l4.03-3.15z" />
            <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.35 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z" />
          </svg>
        </div>

        <div className="space-y-2">
          <h2 className="text-xl sm:text-2xl font-extrabold text-white">
            Connect Operator Account
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
            Sign in with Google to save your workflow presets and VLA model comparison benchmarks.
          </p>
        </div>

        {userProfile ? (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-emerald-500/10 border-2 border-emerald-500/30 flex items-center justify-between text-left">
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white font-bold font-mono flex items-center justify-center shrink-0">
                  {userProfile.name.charAt(0).toUpperCase()}
                </div>
                <div className="truncate">
                  <p className="text-sm font-extrabold text-white truncate">
                    {userProfile.name}
                  </p>
                  <p className="text-xs font-mono text-slate-400 truncate">
                    {userProfile.email}
                  </p>
                </div>
              </div>
              <UserCheck className="w-5 h-5 text-emerald-400 shrink-0" aria-hidden="true" />
            </div>

            <button
              type="button"
              onClick={onContinueLoggedIn}
              className="w-full py-4 px-6 rounded-2xl bg-amber-400 hover:bg-amber-300 text-amber-950 font-extrabold text-sm sm:text-base border-b-4 border-amber-600 active:border-b-0 active:translate-y-1 cursor-pointer flex items-center justify-center gap-2 transition-all"
            >
              <span>Continue as {userProfile.name}</span>
              <ArrowRight className="w-5 h-5" aria-hidden="true" />
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <button
              type="button"
              disabled={isSigningIn}
              onClick={handleGoogleSignIn}
              className="w-full py-4 px-5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-sm sm:text-base border-b-4 border-indigo-800 active:border-b-0 active:translate-y-1 cursor-pointer flex items-center justify-center gap-2.5 shadow-md transition-all disabled:opacity-50"
            >
              {isSigningIn ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                  <span>Connecting Google Account...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-5 h-5" aria-hidden="true" />
                  <span>Continue with Google</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={onContinueGuest}
              className="w-full py-3.5 px-5 rounded-2xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-extrabold text-xs sm:text-sm border-2 border-b-4 border-slate-700 active:border-b-2 active:translate-y-0.5 cursor-pointer flex items-center justify-center gap-1.5 transition-all"
            >
              <span>Continue as Open-Source Guest</span>
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        )}

        <div className="pt-2 border-t border-slate-800 flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" aria-hidden="true" />
          <span>Individual users start safely in the open-source Mode 1 workspace</span>
        </div>
      </div>
    </div>
  );
};

export default AuthPage;
