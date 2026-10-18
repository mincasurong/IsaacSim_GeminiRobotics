import React from 'react';
import { ArrowRight, ArrowLeft, CheckCircle2, Layers, Cpu, Sparkles, Workflow, Bot } from 'lucide-react';

interface IntroPageProps {
  bringupMode: number;
  setBringupMode: (mode: number) => void;
  executionMode: 'flow' | 'vla';
  setExecutionMode: (mode: 'flow' | 'vla') => void;
  onEnterMain: () => void;
  onStartComparisonNow: () => void;
  onBack: () => void;
}

const WORKCELL_MODES = [
  {
    id: 1,
    badge: 'Mode 1 · Open-Source Outline',
    title: '3-Arm Tower Stacking',
    summary: 'Core Isaac Sim (Windows) ↔ ROS 2 (WSL2) ↔ Gemini-4-Argon architecture. Supports 3-arm cooperative 9-block tower stacking and the automated 3-stage model & cost benchmark.',
    icon: <Layers className="w-5 h-5 text-amber-400" aria-hidden="true" />,
  },
  {
    id: 2,
    badge: 'Mode 2 · Multi-Robot Collab',
    title: 'Dual-Arm Bar & Conveyor',
    summary: 'Challenging multi-robot collaboration: synchronized dual-arm 0.8m LongBar lifting, 3D circular wave motion (dual_arm_circle), and moving-conveyor interception (Flying Grasp).',
    icon: <Workflow className="w-5 h-5 text-sky-400" aria-hidden="true" />,
  },
  {
    id: 3,
    badge: 'Mode 3 · ATAMP Research',
    title: 'Long-Horizon Assembly',
    summary: 'Agentic Task and Motion Planning (ATAMP) research mode featuring pre-flight safety shielding, contention-aware wavefront scheduling, and local subgraph fault recovery.',
    icon: <Cpu className="w-5 h-5 text-purple-400" aria-hidden="true" />,
  },
];

export const IntroPage: React.FC<IntroPageProps> = ({
  bringupMode,
  setBringupMode,
  executionMode,
  setExecutionMode,
  onEnterMain,
  onStartComparisonNow,
  onBack,
}) => {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-950 to-black text-white flex flex-col items-center justify-center p-4 sm:p-6 select-none overflow-y-auto">
      <div className="max-w-3xl w-full bg-slate-900/90 backdrop-blur-xl rounded-3xl p-6 sm:p-9 border-2 border-b-4 border-slate-800 shadow-2xl space-y-6 text-left my-6">
        <div className="flex items-center justify-between text-xs font-mono text-slate-400">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1 hover:text-white cursor-pointer font-bold"
          >
            <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Sign In</span>
          </button>
          <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-[11px] font-extrabold">
            STEP 2 / 2 · Workcell & Mode Selection
          </span>
        </div>

        <div className="space-y-1.5">
          <h2 className="text-xl sm:text-2xl font-extrabold text-white">
            Choose Your Workcell & Execution Mode
          </h2>
          <p className="text-xs sm:text-sm text-slate-400">
            Select a simulation workcell and control engine below to enter the main studio without complex setup.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-2.5 text-center text-xs bg-slate-800/60 p-3.5 rounded-2xl border border-slate-700/80">
          <div className="space-y-1">
            <Layers className="w-4 h-4 text-emerald-400 mx-auto" aria-hidden="true" />
            <p className="font-extrabold text-slate-200">1. Select Workcell</p>
          </div>
          <div className="space-y-1">
            <Sparkles className="w-4 h-4 text-amber-400 mx-auto" aria-hidden="true" />
            <p className="font-extrabold text-slate-200">2. Prompt or Visual Flow</p>
          </div>
          <div className="space-y-1">
            <Bot className="w-4 h-4 text-sky-400 mx-auto" aria-hidden="true" />
            <p className="font-extrabold text-slate-200">3. 50Hz Robot Execution</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {WORKCELL_MODES.map((m) => {
            const isSelected = bringupMode === m.id;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => setBringupMode(m.id)}
                className={`p-5 rounded-2xl border-2 border-b-4 text-left cursor-pointer flex flex-col justify-between space-y-3 transition-all ${
                  isSelected
                    ? 'bg-amber-400/15 border-amber-400 shadow-lg'
                    : 'bg-slate-800/50 border-slate-700 hover:border-amber-400/50'
                }`}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span
                      className={`px-2.5 py-0.5 rounded-lg font-mono text-[11px] font-extrabold ${
                        isSelected
                          ? 'bg-amber-400 text-amber-950'
                          : 'bg-slate-700 text-slate-300'
                      }`}
                    >
                      {m.badge}
                    </span>
                    {m.icon}
                  </div>
                  <h3 className="text-base font-extrabold text-white">{m.title}</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">{m.summary}</p>
                </div>

                <div className="flex items-center gap-1 text-xs font-mono font-extrabold text-emerald-400 pt-1">
                  <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
                  <span>{isSelected ? 'Selected' : 'Select Mode'}</span>
                </div>
              </button>
            );
          })}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          <button
            type="button"
            onClick={() => setExecutionMode('flow')}
            className={`p-3.5 rounded-2xl border-2 text-left cursor-pointer flex items-center gap-3 transition-all ${
              executionMode === 'flow'
                ? 'bg-sky-500/15 border-sky-400 text-white'
                : 'bg-slate-800/40 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            <div className="w-9 h-9 rounded-xl bg-sky-500/20 flex items-center justify-center shrink-0 text-lg">
              🧩
            </div>
            <div>
              <div className="text-xs font-extrabold text-white">User-Defined Visual Flow (Recommended)</div>
              <div className="text-[11px] text-slate-400">Auto-build visual task blocks with Gemini-4-Argon and execute at 0 token cost</div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setExecutionMode('vla')}
            className={`p-3.5 rounded-2xl border-2 text-left cursor-pointer flex items-center gap-3 transition-all ${
              executionMode === 'vla'
                ? 'bg-purple-500/15 border-purple-400 text-white'
                : 'bg-slate-800/40 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            <div className="w-9 h-9 rounded-xl bg-purple-500/20 flex items-center justify-center shrink-0 text-lg">
              🧠
            </div>
            <div>
              <div className="text-xs font-extrabold text-white">Autonomous VLA Mode</div>
              <div className="text-[11px] text-slate-400">Closed-loop Gemini-4-Argon Brain + Flash-Lite executor & 3-stage benchmark</div>
            </div>
          </button>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            type="button"
            onClick={onEnterMain}
            className="flex-1 py-4 px-6 rounded-2xl bg-amber-400 hover:bg-amber-300 text-amber-950 font-extrabold text-sm sm:text-base border-b-4 border-amber-600 active:border-b-0 active:translate-y-1 cursor-pointer flex items-center justify-center gap-2 shadow-lg transition-all"
          >
            <span>Enter Main Studio</span>
            <ArrowRight className="w-5 h-5" aria-hidden="true" />
          </button>

          <button
            type="button"
            onClick={onStartComparisonNow}
            className="sm:w-64 py-4 px-5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-xs sm:text-sm border-b-4 border-indigo-800 active:border-b-0 active:translate-y-1 cursor-pointer flex items-center justify-center gap-1.5 transition-all"
          >
            <span>⚖️ Launch 3-Stage Benchmark</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default IntroPage;
