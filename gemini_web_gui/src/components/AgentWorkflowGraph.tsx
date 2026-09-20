import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  MarkerType,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Cpu, ShieldAlert, ShieldCheck, Box, Compass, Activity } from 'lucide-react';
import { type MetricsData, type ChatMessage, type RobotAction } from './theme';

interface AgentWorkflowGraphProps {
  metrics: MetricsData | null;
  chatMessages: ChatMessage[];
  actions: RobotAction[];
  userGoal: string;
}

/* ─────────────────────────────────────────────────────────────
   Custom Node: Human / Goal Node
───────────────────────────────────────────────────────────── */
const GoalNode = ({ data }: { data: { goal: string } }) => {
  return (
    <div
      style={{
        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.95))',
        border: '1px solid rgba(148, 163, 184, 0.3)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 15px rgba(56, 189, 248, 0.15)',
        borderRadius: 14,
        padding: '12px 16px',
        color: '#f8fafc',
        width: 260,
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <div
          style={{
            width: 26,
            height: 26,
            borderRadius: 7,
            background: 'linear-gradient(135deg, #0ea5e9, #38bdf8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
          }}
        >
          <Compass size={15} />
        </div>
        <div>
          <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', fontWeight: 700 }}>
            Task Directive
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9' }}>Human Operator Intent</div>
        </div>
      </div>
      <div
        style={{
          fontSize: 11,
          color: '#cbd5e1',
          lineHeight: 1.4,
          background: 'rgba(15, 23, 42, 0.6)',
          borderRadius: 8,
          padding: '8px 10px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          maxHeight: 65,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        "{data.goal || 'Build 9-layer tower using all available blocks.'}"
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#38bdf8', width: 8, height: 8 }} />
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Custom Node: Multi-Agent Persona Node
───────────────────────────────────────────────────────────── */
const AgentPersonaNode = ({
  data,
}: {
  data: {
    role: string;
    model: string;
    emoji: string;
    color: string;
    isActive: boolean;
    lastSnippet: string;
  };
}) => {
  return (
    <div
      style={{
        background: `linear-gradient(135deg, rgba(17, 24, 39, 0.95), rgba(15, 23, 42, 0.95))`,
        border: data.isActive
          ? `1.5px solid ${data.color}`
          : '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow: data.isActive
          ? `0 0 25px ${data.color}40, 0 10px 30px rgba(0,0,0,0.5)`
          : '0 8px 24px rgba(0, 0, 0, 0.4)',
        borderRadius: 14,
        padding: '12px 14px',
        width: 250,
        color: '#f8fafc',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: data.color, width: 8, height: 8 }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: `linear-gradient(135deg, ${data.color}22, ${data.color}55)`,
              border: `1px solid ${data.color}66`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
            }}
          >
            {data.emoji}
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#f8fafc' }}>{data.role}</div>
            <div style={{ fontSize: 9.5, color: '#94a3b8', fontFamily: 'monospace' }}>{data.model}</div>
          </div>
        </div>
        {data.isActive && (
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 9.5,
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: 12,
              background: `${data.color}22`,
              color: data.color,
              border: `1px solid ${data.color}55`,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: data.color,
                boxShadow: `0 0 8px ${data.color}`,
              }}
            />
            ACTIVE
          </span>
        )}
      </div>

      <div
        style={{
          fontSize: 10.5,
          color: '#cbd5e1',
          background: 'rgba(0, 0, 0, 0.35)',
          padding: '6px 8px',
          borderRadius: 6,
          border: '1px solid rgba(255, 255, 255, 0.04)',
          lineHeight: 1.35,
          minHeight: 38,
          maxHeight: 52,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {data.lastSnippet || 'Ready for task brainstorm iteration.'}
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: data.color, width: 8, height: 8 }} />
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Custom Node: Robot Arm (FR3_1, FR3_2, FR3_3)
───────────────────────────────────────────────────────────── */
const RobotArmNode = ({
  data,
}: {
  data: {
    name: string;
    quadrant: string;
    phase: string;
    target: string;
    busyPct: number;
    tasksCompleted: number;
    color: string;
    isBusy: boolean;
  };
}) => {
  const isExecuting = data.phase && data.phase !== 'IDLE' && data.phase !== 'QUEUED';

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95))',
        border: isExecuting
          ? `1.5px solid ${data.color}`
          : '1px solid rgba(148, 163, 184, 0.2)',
        boxShadow: isExecuting
          ? `0 0 20px ${data.color}33, 0 10px 25px rgba(0,0,0,0.5)`
          : '0 6px 20px rgba(0, 0, 0, 0.35)',
        borderRadius: 14,
        padding: '12px 14px',
        width: 240,
        color: '#f8fafc',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: data.color, width: 8, height: 8 }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: 6,
              background: `${data.color}22`,
              border: `1px solid ${data.color}55`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: data.color,
            }}
          >
            <Cpu size={15} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>{data.name}</div>
            <div style={{ fontSize: 9.5, color: '#94a3b8' }}>{data.quadrant}</div>
          </div>
        </div>

        <div
          style={{
            fontSize: 9.5,
            fontWeight: 700,
            padding: '3px 8px',
            borderRadius: 8,
            background: isExecuting ? `${data.color}25` : 'rgba(255,255,255,0.06)',
            color: isExecuting ? data.color : '#94a3b8',
            border: isExecuting ? `1px solid ${data.color}66` : '1px solid rgba(255,255,255,0.08)',
            textTransform: 'uppercase',
          }}
        >
          {data.phase || 'IDLE'}
        </div>
      </div>

      <div style={{ fontSize: 11, marginBottom: 8, background: 'rgba(0,0,0,0.25)', padding: '6px 8px', borderRadius: 6 }}>
        <div style={{ color: '#94a3b8', fontSize: 9.5, marginBottom: 2 }}>CURRENT TARGET</div>
        <div style={{ fontWeight: 600, color: data.target ? '#f1f5f9' : '#64748b' }}>
          {data.target ? data.target : 'No active block target'}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10, color: '#94a3b8' }}>
        <span>Utilization: <b style={{ color: '#f8fafc' }}>{Math.round(data.busyPct)}%</b></span>
        <span>Tasks: <b style={{ color: '#22c55e' }}>{data.tasksCompleted}</b></span>
        <span style={{ color: '#38bdf8', fontWeight: 600 }}>⚡ 20 stp</span>
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: data.color, width: 8, height: 8 }} />
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Custom Node: Mutex & Workspace Collision Arbiter
───────────────────────────────────────────────────────────── */
const MutexNode = ({
  data,
}: {
  data: {
    occupiedBy: string | null;
  };
}) => {
  const isLocked = Boolean(data.occupiedBy);

  return (
    <div
      style={{
        background: isLocked
          ? 'linear-gradient(135deg, rgba(234, 88, 12, 0.25), rgba(15, 23, 42, 0.95))'
          : 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(15, 23, 42, 0.95))',
        border: isLocked
          ? '1.5px solid #f97316'
          : '1.5px solid rgba(16, 185, 129, 0.4)',
        boxShadow: isLocked
          ? '0 0 25px rgba(249, 115, 22, 0.35)'
          : '0 0 15px rgba(16, 185, 129, 0.2)',
        borderRadius: 14,
        padding: '10px 14px',
        width: 230,
        color: '#f8fafc',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: isLocked ? '#f97316' : '#10b981', width: 8, height: 8 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 7,
            background: isLocked ? '#ea580c' : '#10b981',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
          }}
        >
          {isLocked ? <ShieldAlert size={16} /> : <ShieldCheck size={16} />}
        </div>
        <div>
          <div style={{ fontSize: 9.5, textTransform: 'uppercase', color: '#94a3b8', fontWeight: 700 }}>
            Central Table Arbiter
          </div>
          <div style={{ fontSize: 12, fontWeight: 700, color: isLocked ? '#fb923c' : '#34d399' }}>
            {isLocked ? `LOCKED (${data.occupiedBy})` : 'UNLOCKED / CLEAR'}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 6, lineHeight: 1.3 }}>
        {isLocked
          ? `Arbitrating exclusive entry for ${data.occupiedBy} to prevent multi-arm center collision.`
          : 'Safe for next arm entry into target table.'}
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: isLocked ? '#f97316' : '#10b981', width: 8, height: 8 }} />
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Custom Node: Physical Isaac Sim Construction
───────────────────────────────────────────────────────────── */
const ConstructionNode = ({
  data,
}: {
  data: {
    towerHeight: number;
    placedCount: number;
  };
}) => {
  return (
    <div
      style={{
        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.95))',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5), 0 0 20px rgba(56, 189, 248, 0.15)',
        borderRadius: 14,
        padding: '12px 16px',
        width: 250,
        color: '#f8fafc',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#38bdf8', width: 8, height: 8 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 7,
            background: 'linear-gradient(135deg, #0284c7, #38bdf8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
          }}
        >
          <Box size={16} />
        </div>
        <div>
          <div style={{ fontSize: 9.5, textTransform: 'uppercase', color: '#94a3b8', fontWeight: 700 }}>
            Isaac Sim 4.5 Physics
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>Target Construction</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <div
          style={{
            flex: 1,
            background: 'rgba(0,0,0,0.3)',
            borderRadius: 8,
            padding: '8px 10px',
            border: '1px solid rgba(255,255,255,0.05)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 9, color: '#94a3b8', fontWeight: 600 }}>TOWER LAYERS</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: '#38bdf8' }}>{data.towerHeight}</div>
        </div>
        <div
          style={{
            flex: 1,
            background: 'rgba(0,0,0,0.3)',
            borderRadius: 8,
            padding: '8px 10px',
            border: '1px solid rgba(255,255,255,0.05)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 9, color: '#94a3b8', fontWeight: 600 }}>PHYSICS STATE</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#34d399', marginTop: 4 }}>STABLE</div>
        </div>
      </div>
    </div>
  );
};

const nodeTypes = {
  goalNode: GoalNode,
  agentNode: AgentPersonaNode,
  robotNode: RobotArmNode,
  mutexNode: MutexNode,
  constructionNode: ConstructionNode,
};

/* ─────────────────────────────────────────────────────────────
   Main Agent Workflow Graph Component
───────────────────────────────────────────────────────────── */
export const AgentWorkflowGraph: React.FC<AgentWorkflowGraphProps> = ({
  metrics,
  chatMessages,
  actions,
  userGoal,
}) => {
  // Find latest messages per persona
  const latestVla = [...chatMessages].reverse().find(m => m.role === 'vla');
  const latestArchitect = [...chatMessages].reverse().find(m => m.role === 'architect' && (m.senderName?.includes('Spatial') || m.emoji === '📐'));
  const latestOptimizer = [...chatMessages].reverse().find(m => m.role === 'architect' && (m.senderName?.includes('Performance') || m.senderName?.includes('Optimizer') || m.emoji === '⚡'));

  const lastMessage = chatMessages[chatMessages.length - 1];
  const isVlaSpeaking = lastMessage?.role === 'vla';
  const isArchitectSpeaking = lastMessage?.role === 'architect' && (lastMessage?.senderName?.includes('Spatial') || lastMessage?.emoji === '📐');
  const isOptimizerSpeaking = lastMessage?.role === 'architect' && (lastMessage?.senderName?.includes('Performance') || lastMessage?.emoji === '⚡');

  const r1 = metrics?.robots?.FR3_1;
  const r2 = metrics?.robots?.FR3_2;
  const r3 = metrics?.robots?.FR3_3;

  const isR1Active = r1 && r1.phase !== 'IDLE' && r1.phase !== 'QUEUED';
  const isR2Active = r2 && r2.phase !== 'IDLE' && r2.phase !== 'QUEUED';
  const isR3Active = r3 && r3.phase !== 'IDLE' && r3.phase !== 'QUEUED';

  // Construct Flow Nodes
  const nodes: Node[] = useMemo(
    () => [
      // Top: Goal
      {
        id: 'goal',
        type: 'goalNode',
        position: { x: 370, y: 20 },
        data: { goal: userGoal },
      },

      // Level 1: Three-Agent Brainstorm Pipeline
      {
        id: 'orchestrator',
        type: 'agentNode',
        position: { x: 50, y: 160 },
        data: {
          role: 'Robotics Orchestrator',
          model: 'gemini-robotics-er-2-preview',
          emoji: '🦾',
          color: '#38bdf8',
          isActive: isVlaSpeaking,
          lastSnippet: latestVla?.text ? latestVla.text.slice(0, 100) + '...' : 'Coordinates task schedule and execution.',
        },
      },
      {
        id: 'architect',
        type: 'agentNode',
        position: { x: 370, y: 160 },
        data: {
          role: 'Spatial Architect',
          model: 'gemini-3.8-flash',
          emoji: '📐',
          color: '#a78bfa',
          isActive: isArchitectSpeaking,
          lastSnippet: latestArchitect?.text ? latestArchitect.text.slice(0, 100) + '...' : 'Generates ASCII relative spatial layouts.',
        },
      },
      {
        id: 'optimizer',
        type: 'agentNode',
        position: { x: 690, y: 160 },
        data: {
          role: 'Performance Optimizer',
          model: 'gemini-3.8-flash',
          emoji: '⚡',
          color: '#fbbf24',
          isActive: isOptimizerSpeaking,
          lastSnippet: latestOptimizer?.text ? latestOptimizer.text.slice(0, 100) + '...' : 'Enforces speed=fast and max concurrency.',
        },
      },

      // Level 2: Three Robot Arms
      {
        id: 'robot1',
        type: 'robotNode',
        position: { x: 50, y: 350 },
        data: {
          name: 'FR3_1 (Arm 1)',
          quadrant: 'Bottom Table 1',
          phase: r1?.phase || 'IDLE',
          target: r1?.target || '',
          busyPct: r1?.busy_pct || 0,
          tasksCompleted: r1?.tasks_completed || 0,
          color: '#ef4444',
          isBusy: isR1Active,
        },
      },
      {
        id: 'robot2',
        type: 'robotNode',
        position: { x: 370, y: 350 },
        data: {
          name: 'FR3_2 (Arm 2)',
          quadrant: 'Top-Right Table 2',
          phase: r2?.phase || 'IDLE',
          target: r2?.target || '',
          busyPct: r2?.busy_pct || 0,
          tasksCompleted: r2?.tasks_completed || 0,
          color: '#10b981',
          isBusy: isR2Active,
        },
      },
      {
        id: 'robot3',
        type: 'robotNode',
        position: { x: 690, y: 350 },
        data: {
          name: 'FR3_3 (Arm 3)',
          quadrant: 'Top-Left Table 3',
          phase: r3?.phase || 'IDLE',
          target: r3?.target || '',
          busyPct: r3?.busy_pct || 0,
          tasksCompleted: r3?.tasks_completed || 0,
          color: '#3b82f6',
          isBusy: isR3Active,
        },
      },

      // Level 3: Center Mutex Arbiter
      {
        id: 'mutex',
        type: 'mutexNode',
        position: { x: 380, y: 550 },
        data: {
          occupiedBy: metrics?.center_occupied_by || null,
        },
      },

      // Level 4: Physical Construction
      {
        id: 'construction',
        type: 'constructionNode',
        position: { x: 370, y: 690 },
        data: {
          towerHeight: metrics?.tower_height || 0,
          placedCount: actions.length,
        },
      },
    ],
    [
      userGoal,
      isVlaSpeaking,
      isArchitectSpeaking,
      isOptimizerSpeaking,
      latestVla,
      latestArchitect,
      latestOptimizer,
      r1,
      r2,
      r3,
      isR1Active,
      isR2Active,
      isR3Active,
      metrics,
      actions.length,
    ]
  );

  // Construct Flow Edges with dynamic animations
  const edges: Edge[] = useMemo(
    () => [
      // Goal to Agents
      {
        id: 'e-goal-orch',
        source: 'goal',
        target: 'orchestrator',
        animated: isVlaSpeaking,
        style: { stroke: isVlaSpeaking ? '#38bdf8' : '#64748b', strokeWidth: isVlaSpeaking ? 2.5 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isVlaSpeaking ? '#38bdf8' : '#64748b' },
      },
      {
        id: 'e-orch-arch',
        source: 'orchestrator',
        target: 'architect',
        animated: isArchitectSpeaking,
        style: { stroke: isArchitectSpeaking ? '#a78bfa' : '#64748b', strokeWidth: isArchitectSpeaking ? 2.5 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isArchitectSpeaking ? '#a78bfa' : '#64748b' },
      },
      {
        id: 'e-arch-opt',
        source: 'architect',
        target: 'optimizer',
        animated: isOptimizerSpeaking,
        style: { stroke: isOptimizerSpeaking ? '#fbbf24' : '#64748b', strokeWidth: isOptimizerSpeaking ? 2.5 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isOptimizerSpeaking ? '#fbbf24' : '#64748b' },
      },

      // Optimizer / Orchestrator dispatching to Robots
      {
        id: 'e-opt-r1',
        source: 'optimizer',
        target: 'robot1',
        animated: isR1Active,
        style: { stroke: isR1Active ? '#ef4444' : 'rgba(148, 163, 184, 0.3)', strokeWidth: isR1Active ? 2 : 1 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isR1Active ? '#ef4444' : '#64748b' },
      },
      {
        id: 'e-opt-r2',
        source: 'optimizer',
        target: 'robot2',
        animated: isR2Active,
        style: { stroke: isR2Active ? '#10b981' : 'rgba(148, 163, 184, 0.3)', strokeWidth: isR2Active ? 2 : 1 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isR2Active ? '#10b981' : '#64748b' },
      },
      {
        id: 'e-opt-r3',
        source: 'optimizer',
        target: 'robot3',
        animated: isR3Active,
        style: { stroke: isR3Active ? '#3b82f6' : 'rgba(148, 163, 184, 0.3)', strokeWidth: isR3Active ? 2 : 1 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isR3Active ? '#3b82f6' : '#64748b' },
      },

      // Robots through Mutex
      {
        id: 'e-r1-mutex',
        source: 'robot1',
        target: 'mutex',
        animated: metrics?.center_occupied_by === 'FR3_1',
        style: {
          stroke: metrics?.center_occupied_by === 'FR3_1' ? '#f97316' : 'rgba(148, 163, 184, 0.3)',
          strokeWidth: metrics?.center_occupied_by === 'FR3_1' ? 2.5 : 1,
        },
      },
      {
        id: 'e-r2-mutex',
        source: 'robot2',
        target: 'mutex',
        animated: metrics?.center_occupied_by === 'FR3_2',
        style: {
          stroke: metrics?.center_occupied_by === 'FR3_2' ? '#f97316' : 'rgba(148, 163, 184, 0.3)',
          strokeWidth: metrics?.center_occupied_by === 'FR3_2' ? 2.5 : 1,
        },
      },
      {
        id: 'e-r3-mutex',
        source: 'robot3',
        target: 'mutex',
        animated: metrics?.center_occupied_by === 'FR3_3',
        style: {
          stroke: metrics?.center_occupied_by === 'FR3_3' ? '#f97316' : 'rgba(148, 163, 184, 0.3)',
          strokeWidth: metrics?.center_occupied_by === 'FR3_3' ? 2.5 : 1,
        },
      },

      // Mutex to Construction Output
      {
        id: 'e-mutex-const',
        source: 'mutex',
        target: 'construction',
        animated: Boolean(metrics?.center_occupied_by),
        style: { stroke: '#38bdf8', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#38bdf8' },
      },
    ],
    [
      isVlaSpeaking,
      isArchitectSpeaking,
      isOptimizerSpeaking,
      isR1Active,
      isR2Active,
      isR3Active,
      metrics?.center_occupied_by,
    ]
  );

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: 'radial-gradient(circle at 50% 20%, #111827 0%, #030712 100%)',
        position: 'relative',
      }}
    >
      {/* Visual Header Overlay */}
      <div
        style={{
          position: 'absolute',
          top: 14,
          left: 16,
          zIndex: 10,
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 10,
          padding: '6px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 11,
          color: '#f8fafc',
          fontWeight: 600,
        }}
      >
        <Activity size={14} color="#38bdf8" />
        <span>Multi-Agent Task & Kinematics Flow</span>
        <span
          style={{
            fontSize: 9.5,
            padding: '2px 6px',
            borderRadius: 4,
            background: 'rgba(56, 189, 248, 0.15)',
            color: '#38bdf8',
            border: '1px solid rgba(56, 189, 248, 0.3)',
          }}
        >
          LIVE REACT-FLOW
        </span>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.2} color="rgba(255, 255, 255, 0.12)" />
        <Controls
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 8,
            overflow: 'hidden',
          }}
        />
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 10,
          }}
          nodeColor={n => {
            if (n.type === 'goalNode') return '#38bdf8';
            if (n.type === 'agentNode') return '#a78bfa';
            if (n.type === 'robotNode') return '#10b981';
            if (n.type === 'mutexNode') return '#f97316';
            return '#0ea5e9';
          }}
        />
      </ReactFlow>
    </div>
  );
};
