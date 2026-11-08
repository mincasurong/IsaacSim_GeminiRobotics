import React, { useEffect, useState } from 'react';
import { Crown, ArrowRight, Sparkles, Bot } from 'lucide-react';

interface OpeningPageProps {
  onNext: () => void;
}

interface Particle {
  id: number;
  x: number;
  y: number;
  color: string;
  size: number;
  duration: number;
  delay: number;
}

const COLORS = ['#8B5CF6', '#38BDF8', '#10B981', '#F59E0B', '#6366F1', '#FDE047'];

export const OpeningPage: React.FC<OpeningPageProps> = ({ onNext }) => {
  const [particles, setParticles] = useState<Particle[]>([]);

  useEffect(() => {
    const generated: Particle[] = [];
    for (let i = 0; i < 28; i++) {
      generated.push({
        id: i,
        x: 10 + ((i * 29) % 80),
        y: 12 + ((i * 43) % 72),
        color: COLORS[i % COLORS.length],
        size: 5 + (i % 4) * 2,
        duration: 2.2 + (i % 3) * 0.7,
        delay: (i % 5) * 0.35,
      });
    }
    setParticles(generated);
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-gradient-to-b from-indigo-700 via-slate-900 to-slate-950 text-white flex flex-col items-center justify-center p-4 sm:p-6 overflow-hidden select-none">
      <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
        {particles.map((p) => (
          <div
            key={p.id}
            style={{
              left: `${p.x}%`,
              top: `${p.y}%`,
              backgroundColor: p.color,
              width: p.size,
              height: p.size,
              boxShadow: `0 0 14px ${p.color}`,
              animation: `pulse ${p.duration}s ease-in-out ${p.delay}s infinite`,
            }}
            className="absolute rounded-full opacity-60"
          />
        ))}
      </div>

      <div className="relative z-10 max-w-md w-full text-center space-y-7 bg-white/10 backdrop-blur-xl border-2 border-b-4 border-white/25 p-8 sm:p-10 rounded-3xl shadow-2xl">
        <div className="relative mx-auto w-24 h-24 sm:w-28 sm:h-28">
          <div className="relative w-full h-full rounded-3xl bg-gradient-to-tr from-amber-400 via-yellow-400 to-amber-300 border-4 border-b-8 border-white shadow-2xl flex flex-col items-center justify-center text-amber-950">
            <div className="absolute -top-3.5 -right-2 bg-amber-500 text-white p-1.5 rounded-full border-2 border-white shadow-md">
              <Crown className="w-4 h-4 fill-current text-yellow-200" aria-hidden="true" />
            </div>
            <Bot className="w-9 h-9 text-amber-950 mb-0.5" strokeWidth={2.4} />
            <span className="text-[11px] font-black uppercase tracking-widest text-amber-900/90 font-mono">
              ARGON v4
            </span>
          </div>
        </div>

        <div className="space-y-2.5">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-400/20 border border-amber-400/40 text-amber-300 text-xs font-mono font-bold">
            <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
            <span>NVIDIA Isaac Sim 6.0 × ROS 2 Jazzy × Gemini-4-Argon</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            IsaacSim × Gemini AI Master
          </h1>

          <p className="text-xs sm:text-sm text-indigo-100/90 leading-relaxed">
            Multi-Robot Cooperative Control · Zero-Token Visual DAG Flow · Gemini-4-Argon VLA Digital Twin
          </p>
        </div>

        <button
          type="button"
          onClick={onNext}
          className="w-full py-4 px-6 rounded-2xl bg-amber-400 hover:bg-amber-300 text-amber-950 font-extrabold text-base tracking-wide shadow-xl shadow-amber-500/30 flex items-center justify-center space-x-2 border-b-4 border-amber-600 active:border-b-0 active:translate-y-1 cursor-pointer transition-all"
        >
          <span>Get Started</span>
          <ArrowRight className="w-5 h-5" aria-hidden="true" />
        </button>

        <div className="pt-1">
          <a
            href="https://mincasurong.github.io"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] font-bold text-indigo-200/80 hover:text-white transition-colors"
          >
            Developed by M9G · mincasurong.github.io ↗
          </a>
        </div>
      </div>
    </div>
  );
};

export default OpeningPage;
