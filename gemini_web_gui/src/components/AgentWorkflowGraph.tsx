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
import { type MetricsData, type ChatMessage, type RobotAction, parseAction } from './theme';

interface AgentWorkflowGraphProps {
  metrics: MetricsData | null;
  chatMessages: ChatMessage[];
  actions: RobotAction[];
  userGoal: string;
  results?: RobotAction[];
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
    isCollaborating?: boolean;
    collabObject?: string;
  };
}) => {
  const isExecuting = data.phase && data.phase !== 'IDLE' && data.phase !== 'QUEUED';
  const isCollab = Boolean(data.isCollaborating);

  return (
    <div
      style={{
        background: isCollab
          ? 'linear-gradient(135deg, rgba(30, 20, 50, 0.95), rgba(15, 23, 42, 0.95))'
          : 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95))',
        border: isCollab
          ? '1.8px solid #c084fc'
          : (isExecuting ? `1.5px solid ${data.color}` : '1px solid rgba(148, 163, 184, 0.2)'),
        boxShadow: isCollab
          ? '0 0 24px rgba(192, 132, 252, 0.4), 0 10px 25px rgba(0,0,0,0.5)'
          : (isExecuting ? `0 0 20px ${data.color}33, 0 10px 25px rgba(0,0,0,0.5)` : '0 6px 20px rgba(0, 0, 0, 0.35)'),
        borderRadius: 14,
        padding: '12px 14px',
        width: 240,
        color: '#f8fafc',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        position: 'relative',
      }}
    >
      <Handle type="target" id="top" position={Position.Top} style={{ background: data.color, width: 8, height: 8 }} />
      <Handle type="source" id="right" position={Position.Right} style={{ background: isCollab ? '#c084fc' : data.color, width: 7, height: 7, opacity: 0.6 }} />
      <Handle type="target" id="left" position={Position.Left} style={{ background: isCollab ? '#c084fc' : data.color, width: 7, height: 7, opacity: 0.6 }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: 6,
              background: isCollab ? 'rgba(192, 132, 252, 0.25)' : `${data.color}22`,
              border: isCollab ? '1px solid #c084fc' : `1px solid ${data.color}55`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: isCollab ? '#c084fc' : data.color,
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
            background: isCollab ? 'rgba(192, 132, 252, 0.25)' : (isExecuting ? `${data.color}25` : 'rgba(255,255,255,0.06)'),
            color: isCollab ? '#c084fc' : (isExecuting ? data.color : '#94a3b8'),
            border: isCollab ? '1px solid #c084fc' : (isExecuting ? `1px solid ${data.color}66` : '1px solid rgba(255,255,255,0.08)'),
            textTransform: 'uppercase',
          }}
        >
          {isCollab ? 'DUAL_SYNC' : (data.phase || 'IDLE')}
        </div>
      </div>

      <div style={{ fontSize: 11, marginBottom: 8, background: 'rgba(0,0,0,0.25)', padding: '6px 8px', borderRadius: 6 }}>
        <div style={{ color: '#94a3b8', fontSize: 9.5, marginBottom: 2 }}>CURRENT TARGET</div>
        <div style={{ fontWeight: 600, color: (isCollab || data.target) ? '#f1f5f9' : '#64748b' }}>
          {isCollab ? (data.collabObject || 'LongBar1') : (data.target ? data.target : 'No active block target')}
        </div>
      </div>

      {isCollab && (
        <div
          style={{
            marginBottom: 8,
            padding: '3px 8px',
            borderRadius: 6,
            background: 'rgba(192, 132, 252, 0.2)',
            border: '1px solid rgba(192, 132, 252, 0.5)',
            color: '#f3e8ff',
            fontSize: 9.5,
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: 5,
          }}
        >
          <span>🤝</span>
          <span>DUAL-ARM SYNC ({data.collabObject || 'LongBar1'})</span>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10, color: '#94a3b8' }}>
        <span>Utilization: <b style={{ color: '#f8fafc' }}>{Math.round(data.busyPct)}%</b></span>
        <span>Tasks: <b style={{ color: '#22c55e' }}>{data.tasksCompleted}</b></span>
        <span style={{ color: isCollab ? '#c084fc' : '#38bdf8', fontWeight: 600 }}>{isCollab ? '🤝 SYNC' : '⚡ 20 stp'}</span>
      </div>

      <Handle type="source" id="bottom" position={Position.Bottom} style={{ background: data.color, width: 8, height: 8 }} />
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
    isCollaborative?: boolean;
  };
}) => {
  const isDualLocked = Boolean(
    data.isCollaborative ||
    data.occupiedBy?.includes('DUAL')
  );
  const isLocked = Boolean(data.occupiedBy) || isDualLocked;

  return (
    <div
      style={{
        background: isDualLocked
          ? 'linear-gradient(135deg, rgba(168, 85, 247, 0.3), rgba(15, 23, 42, 0.95))'
          : (isLocked
            ? 'linear-gradient(135deg, rgba(234, 88, 12, 0.25), rgba(15, 23, 42, 0.95))'
            : 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(15, 23, 42, 0.95))'),
        border: isDualLocked
          ? '1.8px solid #c084fc'
          : (isLocked ? '1.5px solid #f97316' : '1.5px solid rgba(16, 185, 129, 0.4)'),
        boxShadow: isDualLocked
          ? '0 0 25px rgba(192, 132, 252, 0.4)'
          : (isLocked ? '0 0 25px rgba(249, 115, 22, 0.35)' : '0 0 15px rgba(16, 185, 129, 0.2)'),
        borderRadius: 14,
        padding: '10px 14px',
        width: 230,
        color: '#f8fafc',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: isDualLocked ? '#c084fc' : (isLocked ? '#f97316' : '#10b981'), width: 8, height: 8 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 7,
            background: isDualLocked ? '#9333ea' : (isLocked ? '#ea580c' : '#10b981'),
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
          <div style={{ fontSize: 12, fontWeight: 700, color: isDualLocked ? '#e9d5ff' : (isLocked ? '#fb923c' : '#34d399') }}>
            {isDualLocked
              ? `LOCKED (${data.occupiedBy || 'DUAL_ARM'})`
              : (isLocked ? `LOCKED (${data.occupiedBy})` : 'UNLOCKED / CLEAR')}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 6, lineHeight: 1.3 }}>
        {isDualLocked
          ? 'Arbitrating exclusive dual-arm clearance for oversized long bar collaborative transport.'
          : (isLocked
            ? `Arbitrating exclusive entry for ${data.occupiedBy} to prevent multi-arm center collision.`
            : 'Safe for next arm entry into target table.')}
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: isDualLocked ? '#c084fc' : (isLocked ? '#f97316' : '#10b981'), width: 8, height: 8 }} />
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

const FIT_VIEW_OPTIONS = { padding: 0.2 };

/* ─────────────────────────────────────────────────────────────
   Main Agent Workflow Graph Component
───────────────────────────────────────────────────────────── */
const AgentWorkflowGraphComponent: React.FC<AgentWorkflowGraphProps> = ({
  metrics,
  chatMessages,
  actions,
  userGoal,
  results,
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

  const isR1Active = Boolean(r1 && r1.phase !== 'IDLE' && r1.phase !== 'QUEUED');
  const isR2Active = Boolean(r2 && r2.phase !== 'IDLE' && r2.phase !== 'QUEUED');
  const isR3Active = Boolean(r3 && r3.phase !== 'IDLE' && r3.phase !== 'QUEUED');

  // Collaborative Linkage Detection (Dual-Arm) with defensive string and type guards
  const isDualArmCollaborating = Boolean(
    metrics?.collaborative_active === true ||
    metrics?.center_occupied_by === 'DUAL_FR3_1_FR3_2' ||
    (typeof metrics?.center_occupied_by === 'string' && metrics.center_occupied_by.includes('DUAL')) ||
    (Array.isArray(metrics?.collaborative_pair) && metrics.collaborative_pair.length >= 2) ||
    (Array.isArray(actions) && actions.some(a => {
      try {
        const pa = parseAction(a?.raw || '');
        const act = String(pa?.action || '').toLowerCase();
        const tgt = String(pa?.target || '').toLowerCase();
        const aTime = a?.ts instanceof Date ? a.ts.getTime() : 0;
        const isFinished = Array.isArray(results) && results.some(r => {
          const rTime = r?.ts instanceof Date ? r.ts.getTime() : 0;
          return rTime >= aTime;
        });
        return (act.includes('dual') || tgt.includes('bar') || tgt.includes('tray')) && !isFinished;
      } catch {
        return false;
      }
    }))
  );

  const rawPair = metrics?.collaborative_pair;
  const collabPair = (rawPair && Array.isArray(rawPair) && rawPair.length >= 2)
    ? rawPair
    : ['FR3_1', 'FR3_2'];
  const collabObject = metrics?.collaborative_object || 'LongBar1';

  // Construct Flow Nodes
  const nodes: Node[] = useMemo(
    () => [
      // Top: Goal
      {
        id: 'goal',
        type: 'goalNode',
        position: { x: 370, y: 20 },
        width: 280,
        height: 95,
        data: { goal: userGoal },
      },

      // Level 1: Three-Agent Brainstorm Pipeline
      {
        id: 'orchestrator',
        type: 'agentNode',
        position: { x: 50, y: 160 },
        width: 250,
        height: 130,
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
        width: 250,
        height: 130,
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
        width: 250,
        height: 130,
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
        width: 240,
        height: 155,
        data: {
          name: 'FR3_1 (Arm 1)',
          quadrant: 'Bottom Table 1',
          phase: r1?.phase || 'IDLE',
          target: r1?.target || '',
          busyPct: r1?.busy_pct || 0,
          tasksCompleted: r1?.tasks_completed || 0,
          color: '#ef4444',
          isBusy: isR1Active,
          isCollaborating: isDualArmCollaborating && collabPair.includes('FR3_1'),
          collabObject: collabObject,
        },
      },
      {
        id: 'robot2',
        type: 'robotNode',
        position: { x: 370, y: 350 },
        width: 240,
        height: 155,
        data: {
          name: 'FR3_2 (Arm 2)',
          quadrant: 'Top-Right Table 2',
          phase: r2?.phase || 'IDLE',
          target: r2?.target || '',
          busyPct: r2?.busy_pct || 0,
          tasksCompleted: r2?.tasks_completed || 0,
          color: '#10b981',
          isBusy: isR2Active,
          isCollaborating: isDualArmCollaborating && collabPair.includes('FR3_2'),
          collabObject: collabObject,
        },
      },
      {
        id: 'robot3',
        type: 'robotNode',
        position: { x: 690, y: 350 },
        width: 240,
        height: 155,
        data: {
          name: 'FR3_3 (Arm 3)',
          quadrant: 'Top-Left Table 3',
          phase: r3?.phase || 'IDLE',
          target: r3?.target || '',
          busyPct: r3?.busy_pct || 0,
          tasksCompleted: r3?.tasks_completed || 0,
          color: '#3b82f6',
          isBusy: isR3Active,
          isCollaborating: isDualArmCollaborating && collabPair.includes('FR3_3'),
          collabObject: collabObject,
        },
      },

      // Level 3: Center Mutex Arbiter
      {
        id: 'mutex',
        type: 'mutexNode',
        position: { x: 380, y: 550 },
        width: 230,
        height: 120,
        data: {
          occupiedBy: metrics?.center_occupied_by || null,
          isCollaborative: isDualArmCollaborating,
        },
      },

      // Level 4: Physical Construction
      {
        id: 'construction',
        type: 'constructionNode',
        position: { x: 370, y: 690 },
        width: 240,
        height: 120,
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
      latestVla?.text,
      latestArchitect?.text,
      latestOptimizer?.text,
      r1?.phase,
      r1?.target,
      r1?.busy_pct,
      r1?.tasks_completed,
      r2?.phase,
      r2?.target,
      r2?.busy_pct,
      r2?.tasks_completed,
      r3?.phase,
      r3?.target,
      r3?.busy_pct,
      r3?.tasks_completed,
      isR1Active,
      isR2Active,
      isR3Active,
      metrics?.tower_height,
      metrics?.center_occupied_by,
      actions.length,
      isDualArmCollaborating,
      collabPair[0],
      collabPair[1],
      collabObject,
    ]
  );

  // Construct Flow Edges with dynamic animations
  const edges: Edge[] = useMemo(
    () => {
      const baseEdges: Edge[] = [
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
          targetHandle: 'top',
          animated: isR1Active,
          style: { stroke: isR1Active ? '#ef4444' : 'rgba(148, 163, 184, 0.3)', strokeWidth: isR1Active ? 2 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, color: isR1Active ? '#ef4444' : '#64748b' },
        },
        {
          id: 'e-opt-r2',
          source: 'optimizer',
          target: 'robot2',
          targetHandle: 'top',
          animated: isR2Active,
          style: { stroke: isR2Active ? '#10b981' : 'rgba(148, 163, 184, 0.3)', strokeWidth: isR2Active ? 2 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, color: isR2Active ? '#10b981' : '#64748b' },
        },
        {
          id: 'e-opt-r3',
          source: 'optimizer',
          target: 'robot3',
          targetHandle: 'top',
          animated: isR3Active,
          style: { stroke: isR3Active ? '#3b82f6' : 'rgba(148, 163, 184, 0.3)', strokeWidth: isR3Active ? 2 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, color: isR3Active ? '#3b82f6' : '#64748b' },
        },

        // Robots through Mutex
        {
          id: 'e-r1-mutex',
          source: 'robot1',
          sourceHandle: 'bottom',
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
          sourceHandle: 'bottom',
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
          sourceHandle: 'bottom',
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
      ];

      // Dynamic Dual-Arm Collaborative Linkage Edge
      if (isDualArmCollaborating) {
        const rNodeMap: Record<string, string> = {
          FR3_1: 'robot1',
          FR3_2: 'robot2',
          FR3_3: 'robot3',
          R1: 'robot1',
          R2: 'robot2',
          R3: 'robot3',
          '1': 'robot1',
          '2': 'robot2',
          '3': 'robot3',
        };
        const rOrder: Record<string, number> = { robot1: 1, robot2: 2, robot3: 3 };
        const validNodes = new Set(['robot1', 'robot2', 'robot3']);
        const n1 = rNodeMap[collabPair[0]] || (validNodes.has(collabPair[0]) ? collabPair[0] : 'robot1');
        const n2 = rNodeMap[collabPair[1]] || (validNodes.has(collabPair[1]) ? collabPair[1] : 'robot2');
        const [srcNode, tgtNode] = (rOrder[n1] <= rOrder[n2]) ? [n1, n2] : [n2, n1];

        baseEdges.push({
          id: 'e-collab-dual-arm',
          source: srcNode,
          target: tgtNode,
          sourceHandle: 'right',
          targetHandle: 'left',
          animated: true,
          className: 'collab-glow-edge',
          style: {
            stroke: '#c084fc',
            strokeWidth: 3.5,
            strokeDasharray: '6 3',
            filter: 'drop-shadow(0 0 12px #c084fc)',
          },
          label: `🤝 Dual-Arm Co-Transport: ${collabObject}`,
          labelStyle: {
            fill: '#f3e8ff',
            fontWeight: 800,
            fontSize: 10.5,
            letterSpacing: '0.06em',
          },
          labelBgStyle: {
            fill: 'rgba(24, 16, 42, 0.95)',
            stroke: '#a855f7',
            strokeWidth: 1.5,
            rx: 8,
            ry: 8,
          },
          labelBgPadding: [8, 5],
        });
      }

      return baseEdges;
    },
    [
      isVlaSpeaking,
      isArchitectSpeaking,
      isOptimizerSpeaking,
      isR1Active,
      isR2Active,
      isR3Active,
      metrics?.center_occupied_by,
      isDualArmCollaborating,
      collabPair[0],
      collabPair[1],
      collabObject,
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
        fitViewOptions={FIT_VIEW_OPTIONS}
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

      <style>{`
        @keyframes pulseCollabEdge {
          0%, 100% {
            filter: drop-shadow(0 0 5px #a855f7) drop-shadow(0 0 12px #c084fc);
            stroke: #c084fc;
          }
          50% {
            filter: drop-shadow(0 0 14px #e879f9) drop-shadow(0 0 28px #a855f7);
            stroke: #f0abfc;
          }
        }
        .collab-glow-edge path {
          animation: pulseCollabEdge 1.4s ease-in-out infinite !important;
        }
      `}</style>
    </div>
  );
};

export const AgentWorkflowGraph = React.memo<AgentWorkflowGraphProps>(AgentWorkflowGraphComponent);
