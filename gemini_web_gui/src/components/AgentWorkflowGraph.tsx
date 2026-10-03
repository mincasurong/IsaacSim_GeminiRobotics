import React, { useEffect } from 'react';
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
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  ShieldAlert,
  ShieldCheck,
  Activity,
  Sparkles,
  Bot,
  Layers,
  CheckCircle2,
} from 'lucide-react';
import { type MetricsData, type ChatMessage, type RobotAction } from './theme';

interface AgentWorkflowGraphProps {
  metrics: MetricsData | null;
  chatMessages: ChatMessage[];
  actions: RobotAction[];
  userGoal: string;
}

// ─────────────────────────────────────────────────────────────
// Design System: Organic Flow & Modern Frosted Glassmorphism
// ─────────────────────────────────────────────────────────────
const fontSans = '-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif';
const fontMono = '"JetBrains Mono", ui-monospace, SFMono-Regular, monospace';

const baseFlowCardStyle = {
  background: 'linear-gradient(145deg, rgba(24, 24, 30, 0.88) 0%, rgba(13, 13, 18, 0.94) 100%)',
  backdropFilter: 'blur(16px)',
  WebkitBackdropFilter: 'blur(16px)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  boxShadow: '0 12px 32px -4px rgba(0, 0, 0, 0.6), 0 0 1px 1px rgba(255, 255, 255, 0.05)',
  borderRadius: 22,
  padding: '16px 18px',
  color: '#f4f4f5',
  fontFamily: fontSans,
  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
};

// Circular synapse handles
const makeHandleStyle = (color: string) => ({
  width: 10,
  height: 10,
  borderRadius: '50%',
  background: color,
  border: '2px solid #09090b',
  boxShadow: `0 0 10px ${color}`,
  transition: 'transform 0.2s ease',
});

// Soft Pill Badge
const Pill = ({
  color,
  bg,
  children,
  pulse = false,
}: {
  color: string;
  bg?: string;
  children: React.ReactNode;
  pulse?: boolean;
}) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      padding: '3px 10px',
      borderRadius: 9999,
      background: bg || `${color}18`,
      border: `1px solid ${color}35`,
      color: color,
      fontSize: 10,
      fontWeight: 600,
      letterSpacing: '0.02em',
      fontFamily: fontSans,
    }}
  >
    {pulse && (
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: color,
          boxShadow: `0 0 8px ${color}`,
          display: 'inline-block',
        }}
      />
    )}
    {children}
  </div>
);

// ─────────────────────────────────────────────────────────────
// Custom Node: Human / Directive Goal Node
// ─────────────────────────────────────────────────────────────
const GoalNode = ({ data }: { data: { goal: string } }) => {
  return (
    <div
      style={{
        ...baseFlowCardStyle,
        width: 280,
        border: '1px solid rgba(56, 189, 248, 0.35)',
        boxShadow: '0 16px 36px -6px rgba(0, 0, 0, 0.7), 0 0 20px rgba(56, 189, 248, 0.15)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 10,
              background: 'linear-gradient(135deg, #0284c7, #38bdf8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 12px rgba(56, 189, 248, 0.4)',
            }}
          >
            <Sparkles size={15} color="#ffffff" />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ffffff' }}>Operator Directive</div>
            <div style={{ fontSize: 9, color: '#94a3b8' }}>High-Level Goal</div>
          </div>
        </div>
        <Pill color="#38bdf8" pulse>VLA Input</Pill>
      </div>

      <div
        style={{
          background: 'rgba(15, 23, 42, 0.65)',
          borderRadius: 14,
          padding: '10px 12px',
          border: '1px solid rgba(56, 189, 248, 0.15)',
          color: '#e2e8f0',
          fontSize: 11,
          lineHeight: '1.45',
          fontStyle: 'italic',
          maxHeight: 70,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        "{data.goal || 'Build a 9-layer tower on the central target table'}"
      </div>

      <Handle type="source" position={Position.Bottom} style={makeHandleStyle('#38bdf8')} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Custom Node: Multi-Agent Persona Node
// ─────────────────────────────────────────────────────────────
const AgentPersonaNode = ({ data }: any) => {
  const activeColor = data.isActive ? data.color : 'rgba(255, 255, 255, 0.12)';
  const activeGlow = data.isActive ? `0 0 24px ${data.color}35` : 'none';

  return (
    <div
      style={{
        ...baseFlowCardStyle,
        width: 260,
        border: `1px solid ${activeColor}`,
        boxShadow: `0 14px 32px -4px rgba(0, 0, 0, 0.6), ${activeGlow}`,
      }}
    >
      <Handle type="target" position={Position.Top} style={makeHandleStyle(data.color)} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: `${data.color}20`,
              border: `1px solid ${data.color}50`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              boxShadow: `0 0 12px ${data.color}30`,
            }}
          >
            {data.emoji}
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#f4f4f5' }}>{data.role}</div>
            <div style={{ fontSize: 9, color: '#71717a', fontFamily: fontMono }}>{data.model}</div>
          </div>
        </div>
        <Pill color={data.isActive ? data.color : '#71717a'} pulse={data.isActive}>
          {data.isActive ? 'Active' : 'Standby'}
        </Pill>
      </div>

      <div
        style={{
          background: 'rgba(24, 24, 27, 0.6)',
          borderRadius: 14,
          padding: '8px 12px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          color: data.isActive ? '#e4e4e7' : '#a1a1aa',
          fontSize: 10,
          lineHeight: '1.4',
          minHeight: 40,
          maxHeight: 56,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {data.lastSnippet || 'Awaiting turn deliberation...'}
      </div>

      <Handle type="source" position={Position.Bottom} style={makeHandleStyle(data.color)} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Custom Node: Rule-Based Task Generator Node
// ─────────────────────────────────────────────────────────────
const RuleGeneratorNode = ({ data }: any) => {
  const activeColor = data.isActive ? '#10b981' : 'rgba(255, 255, 255, 0.12)';
  const activeGlow = data.isActive ? '0 0 24px rgba(16, 185, 129, 0.35)' : 'none';

  return (
    <div
      style={{
        ...baseFlowCardStyle,
        width: 270,
        border: `1px solid ${activeColor}`,
        boxShadow: `0 14px 32px -4px rgba(0, 0, 0, 0.6), ${activeGlow}`,
      }}
    >
      <Handle type="target" position={Position.Top} style={makeHandleStyle('#10b981')} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.2)',
              border: '1px solid rgba(16, 185, 129, 0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              boxShadow: '0 0 12px rgba(16, 185, 129, 0.3)',
            }}
          >
            📋
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#f4f4f5' }}>Rule-Based Generator</div>
            <div style={{ fontSize: 9, color: '#10b981', fontFamily: fontMono }}>Deterministic Blueprint</div>
          </div>
        </div>
        <Pill color="#10b981" pulse={data.isActive}>
          {data.isActive ? 'Blueprint Ready' : 'Standby'}
        </Pill>
      </div>

      <div
        style={{
          background: 'rgba(24, 24, 27, 0.6)',
          borderRadius: 14,
          padding: '8px 12px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          color: data.isActive ? '#e4e4e7' : '#a1a1aa',
          fontSize: 10,
          lineHeight: '1.4',
          minHeight: 40,
          maxHeight: 56,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {data.lastSnippet || 'Formulates physical reachability & layer schedule from /tf'}
      </div>

      <Handle type="source" position={Position.Bottom} style={makeHandleStyle('#10b981')} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Custom Node: Rule-Based Safety Verifier Node
// ─────────────────────────────────────────────────────────────
const RuleVerifierNode = ({ data }: any) => {
  const activeColor = data.isActive ? '#a855f7' : 'rgba(255, 255, 255, 0.12)';
  const activeGlow = data.isActive ? '0 0 24px rgba(168, 85, 247, 0.35)' : 'none';

  return (
    <div
      style={{
        ...baseFlowCardStyle,
        width: 270,
        border: `1px solid ${activeColor}`,
        boxShadow: `0 14px 32px -4px rgba(0, 0, 0, 0.6), ${activeGlow}`,
      }}
    >
      <Handle type="target" position={Position.Top} style={makeHandleStyle('#a855f7')} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: 'rgba(168, 85, 247, 0.2)',
              border: '1px solid rgba(168, 85, 247, 0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              boxShadow: '0 0 12px rgba(168, 85, 247, 0.3)',
            }}
          >
            🛡️
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#f4f4f5' }}>Rule-Based Verifier</div>
            <div style={{ fontSize: 9, color: '#a855f7', fontFamily: fontMono }}>Pre-execution Interceptor</div>
          </div>
        </div>
        <Pill color="#a855f7" pulse={data.isActive}>
          {data.isActive ? 'Guarding' : 'Standby'}
        </Pill>
      </div>

      <div
        style={{
          background: 'rgba(24, 24, 27, 0.6)',
          borderRadius: 14,
          padding: '8px 12px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          color: data.isActive ? '#e4e4e7' : '#a1a1aa',
          fontSize: 10,
          lineHeight: '1.4',
          minHeight: 40,
          maxHeight: 56,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {data.lastSnippet || 'Validates table ownership, holding state, & center table bounds'}
      </div>

      <Handle type="source" position={Position.Bottom} style={makeHandleStyle('#a855f7')} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Custom Node: Robot Arm Node
// ─────────────────────────────────────────────────────────────
const RobotArmNode = ({ data }: any) => {
  const isExecuting = data.phase && data.phase !== 'IDLE' && data.phase !== 'QUEUED';
  const glow = isExecuting ? `0 0 25px ${data.color}35` : 'none';

  return (
    <div
      style={{
        ...baseFlowCardStyle,
        width: 250,
        border: `1px solid ${isExecuting ? data.color : 'rgba(255, 255, 255, 0.1)'}`,
        boxShadow: `0 14px 32px -4px rgba(0, 0, 0, 0.6), ${glow}`,
      }}
    >
      <Handle type="target" position={Position.Top} style={makeHandleStyle(data.color)} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 10,
              background: `${data.color}20`,
              border: `1px solid ${data.color}50`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: `0 0 10px ${data.color}25`,
            }}
          >
            <Bot size={16} color={data.color} />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ffffff' }}>{data.name}</div>
            <div style={{ fontSize: 9, color: '#a1a1aa' }}>{data.quadrant}</div>
          </div>
        </div>
        <Pill color={isExecuting ? data.color : '#71717a'} pulse={isExecuting}>
          {data.phase || 'IDLE'}
        </Pill>
      </div>

      {/* Target object capsule */}
      <div
        style={{
          background: 'rgba(24, 24, 27, 0.7)',
          borderRadius: 12,
          padding: '6px 10px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          marginBottom: 10,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: 9, color: '#71717a', textTransform: 'uppercase', fontWeight: 600 }}>Target</span>
        <span style={{ fontSize: 10, color: data.target ? '#f4f4f5' : '#52525b', fontWeight: 600 }}>
          {data.target || 'None'}
        </span>
      </div>

      {/* Metrics Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'rgba(0, 0, 0, 0.25)',
          borderRadius: 10,
          padding: '6px 10px',
          fontSize: 10,
          fontFamily: fontMono,
          color: '#a1a1aa',
        }}
      >
        <span>
          Util: <strong style={{ color: '#fff' }}>{Math.round(data.busyPct || 0)}%</strong>
        </span>
        <span>
          Ops: <strong style={{ color: data.color }}>{data.tasksCompleted || 0}</strong>
        </span>
        <span style={{ color: '#38bdf8', fontSize: 9, fontWeight: 600 }}>100 Hz</span>
      </div>

      <Handle type="source" position={Position.Bottom} style={makeHandleStyle(data.color)} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Custom Node: Mutex Arbiter Node
// ─────────────────────────────────────────────────────────────
const MutexNode = ({ data }: any) => {
  const isLocked = Boolean(data.occupiedBy);
  const color = isLocked ? '#f97316' : '#10b981';

  return (
    <div
      style={{
        ...baseFlowCardStyle,
        width: 250,
        border: `1px solid ${color}60`,
        boxShadow: `0 14px 32px -4px rgba(0, 0, 0, 0.6), 0 0 20px ${color}20`,
      }}
    >
      <Handle type="target" position={Position.Top} style={makeHandleStyle(color)} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 10,
              background: `${color}20`,
              border: `1px solid ${color}50`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: `0 0 10px ${color}30`,
            }}
          >
            {isLocked ? <ShieldAlert size={16} color={color} /> : <ShieldCheck size={16} color={color} />}
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ffffff' }}>Spatial Arbiter</div>
            <div style={{ fontSize: 9, color: '#a1a1aa' }}>Center Staging Zone</div>
          </div>
        </div>
        <Pill color={color} pulse={isLocked}>
          {isLocked ? 'Locked' : 'Clear'}
        </Pill>
      </div>

      <div
        style={{
          background: 'rgba(24, 24, 27, 0.7)',
          borderRadius: 12,
          padding: '8px 12px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: 10, color: '#a1a1aa' }}>Active Possession:</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: isLocked ? '#f4f4f5' : '#71717a' }}>
          {isLocked ? data.occupiedBy : 'Available'}
        </span>
      </div>

      <Handle type="source" position={Position.Bottom} style={makeHandleStyle(color)} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Custom Node: Construction / Tower State Node
// ─────────────────────────────────────────────────────────────
const ConstructionNode = ({ data }: any) => {
  return (
    <div
      style={{
        ...baseFlowCardStyle,
        width: 260,
        border: '1px solid rgba(56, 189, 248, 0.3)',
        boxShadow: '0 16px 36px -4px rgba(0, 0, 0, 0.7), 0 0 20px rgba(56, 189, 248, 0.15)',
      }}
    >
      <Handle type="target" position={Position.Top} style={makeHandleStyle('#38bdf8')} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 10,
              background: 'rgba(56, 189, 248, 0.2)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 10px rgba(56, 189, 248, 0.3)',
            }}
          >
            <Layers size={16} color="#38bdf8" />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ffffff' }}>Tower Digital Twin</div>
            <div style={{ fontSize: 9, color: '#94a3b8' }}>PhysX Rigid Bodies</div>
          </div>
        </div>
        <Pill color="#10b981">
          <CheckCircle2 size={10} style={{ marginRight: 2 }} /> Stable
        </Pill>
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <div
          style={{
            flex: 1,
            background: 'rgba(15, 23, 42, 0.6)',
            border: '1px solid rgba(56, 189, 248, 0.15)',
            borderRadius: 14,
            padding: '10px 8px',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 2 }}>Layers Stacked</div>
          <div style={{ fontSize: 18, color: '#38bdf8', fontWeight: 800, fontFamily: fontMono }}>
            {data.towerHeight || 0}
            <span style={{ fontSize: 11, color: '#64748b' }}>/9</span>
          </div>
        </div>

        <div
          style={{
            flex: 1,
            background: 'rgba(15, 23, 42, 0.6)',
            border: '1px solid rgba(16, 185, 129, 0.15)',
            borderRadius: 14,
            padding: '10px 8px',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 2 }}>Placement State</div>
          <div style={{ fontSize: 13, color: '#10b981', fontWeight: 700, marginTop: 4 }}>
            Aligned
          </div>
        </div>
      </div>
    </div>
  );
};

const nodeTypes = {
  goalNode: GoalNode,
  generatorNode: RuleGeneratorNode,
  agentNode: AgentPersonaNode,
  verifierNode: RuleVerifierNode,
  robotNode: RobotArmNode,
  mutexNode: MutexNode,
  constructionNode: ConstructionNode,
};

const initialNodes: Node[] = [
  { id: 'goal', type: 'goalNode', position: { x: 370, y: 20 }, data: { goal: '' } },
  { id: 'generator', type: 'generatorNode', position: { x: 370, y: 160 }, data: { isActive: true, lastSnippet: '' } },
  { id: 'orchestrator', type: 'agentNode', position: { x: 370, y: 310 }, data: { role: 'VLA Brain', emoji: '🦾', color: '#38bdf8', model: 'gemini-robotics-er-2' } },
  { id: 'verifier', type: 'verifierNode', position: { x: 370, y: 460 }, data: { isActive: true, lastSnippet: '' } },
  { id: 'robot1', type: 'robotNode', position: { x: 50, y: 620 }, data: { name: 'FR3_1 (Bottom)', color: '#ef4444', quadrant: 'Table 1' } },
  { id: 'robot2', type: 'robotNode', position: { x: 370, y: 620 }, data: { name: 'FR3_2 (Top-Right)', color: '#10b981', quadrant: 'Table 2' } },
  { id: 'robot3', type: 'robotNode', position: { x: 690, y: 620 }, data: { name: 'FR3_3 (Top-Left)', color: '#3b82f6', quadrant: 'Table 3' } },
  { id: 'mutex', type: 'mutexNode', position: { x: 370, y: 810 }, data: { occupiedBy: null } },
  { id: 'construction', type: 'constructionNode', position: { x: 370, y: 960 }, data: { towerHeight: 0, placedCount: 0 } },
];

// Fluid cubic Bezier curves ('default') instead of rigid square 'step'
const initialEdges: Edge[] = [
  { id: 'e-goal-gen', source: 'goal', target: 'generator', type: 'default' },
  { id: 'e-gen-vla', source: 'generator', target: 'orchestrator', type: 'default' },
  { id: 'e-vla-verif', source: 'orchestrator', target: 'verifier', type: 'default' },
  { id: 'e-verif-r1', source: 'verifier', target: 'robot1', type: 'default' },
  { id: 'e-verif-r2', source: 'verifier', target: 'robot2', type: 'default' },
  { id: 'e-verif-r3', source: 'verifier', target: 'robot3', type: 'default' },
  { id: 'e-r1-mutex', source: 'robot1', target: 'mutex', type: 'default' },
  { id: 'e-r2-mutex', source: 'robot2', target: 'mutex', type: 'default' },
  { id: 'e-r3-mutex', source: 'robot3', target: 'mutex', type: 'default' },
  { id: 'e-mutex-const', source: 'mutex', target: 'construction', type: 'default' },
];

// ─────────────────────────────────────────────────────────────
// Main Agent Workflow Graph Component
// ─────────────────────────────────────────────────────────────
export const AgentWorkflowGraph: React.FC<AgentWorkflowGraphProps> = ({
  metrics,
  chatMessages,
  actions,
  userGoal,
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    // Find latest messages per persona
    const latestGenerator = [...chatMessages].reverse().find(
      m => m.role === 'generator' || m.senderName?.includes('Generator') || m.emoji === '📋'
    );
    const latestVla = [...chatMessages].reverse().find(
      m => m.role === 'vla' || m.senderName?.includes('Gemini') || m.emoji === '🦾'
    );

    const lastMessage = chatMessages[chatMessages.length - 1];
    const isGeneratorSpeaking =
      lastMessage?.role === 'generator' || lastMessage?.senderName?.includes('Generator') || lastMessage?.emoji === '📋';
    const isVlaSpeaking =
      lastMessage?.role === 'vla' || lastMessage?.senderName?.includes('Gemini') || lastMessage?.emoji === '🦾';

    const r1 = metrics?.robots?.FR3_1;
    const r2 = metrics?.robots?.FR3_2;
    const r3 = metrics?.robots?.FR3_3;

    const isR1Active = r1 && r1.phase !== 'IDLE' && r1.phase !== 'QUEUED';
    const isR2Active = r2 && r2.phase !== 'IDLE' && r2.phase !== 'QUEUED';
    const isR3Active = r3 && r3.phase !== 'IDLE' && r3.phase !== 'QUEUED';
    const anyRobotActive = isR1Active || isR2Active || isR3Active;

    // Update Nodes Data (preserving coordinates)
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === 'goal') n.data = { ...n.data, goal: userGoal };
        if (n.id === 'generator')
          n.data = {
            ...n.data,
            isActive: Boolean(isGeneratorSpeaking || latestGenerator),
            lastSnippet: latestGenerator?.text ? latestGenerator.text.slice(0, 95) + '...' : n.data.lastSnippet,
          };
        if (n.id === 'orchestrator')
          n.data = {
            ...n.data,
            isActive: isVlaSpeaking,
            lastSnippet: latestVla?.text ? latestVla.text.slice(0, 95) + '...' : n.data.lastSnippet,
          };
        if (n.id === 'verifier')
          n.data = {
            ...n.data,
            isActive: Boolean(anyRobotActive),
            lastSnippet: anyRobotActive
              ? 'Guarding active pick/place kinematics, table ownership, & mutex locks'
              : 'Grounded physical reachability: Table 1 (FR3_1), Table 2 (FR3_2), Table 3 (FR3_3)',
          };

        if (n.id === 'robot1')
          n.data = {
            ...n.data,
            phase: r1?.phase,
            target: r1?.target,
            busyPct: r1?.busy_pct,
            tasksCompleted: r1?.tasks_completed,
          };
        if (n.id === 'robot2')
          n.data = {
            ...n.data,
            phase: r2?.phase,
            target: r2?.target,
            busyPct: r2?.busy_pct,
            tasksCompleted: r2?.tasks_completed,
          };
        if (n.id === 'robot3')
          n.data = {
            ...n.data,
            phase: r3?.phase,
            target: r3?.target,
            busyPct: r3?.busy_pct,
            tasksCompleted: r3?.tasks_completed,
          };

        if (n.id === 'mutex') n.data = { ...n.data, occupiedBy: metrics?.center_occupied_by };
        if (n.id === 'construction')
          n.data = { ...n.data, towerHeight: metrics?.tower_height, placedCount: actions.length };

        return n;
      })
    );

    // Update Flow Edges with organic Bezier curves & fluid glow animations
    setEdges((eds) =>
      eds.map((e) => {
        let active = false;
        let color = '#3f3f46';

        if (e.id === 'e-goal-gen') {
          active = isGeneratorSpeaking || isVlaSpeaking;
          color = active ? '#10b981' : '#27272a';
        }
        if (e.id === 'e-gen-vla') {
          active = isVlaSpeaking;
          color = active ? '#38bdf8' : '#27272a';
        }
        if (e.id === 'e-vla-verif') {
          active = Boolean(anyRobotActive);
          color = active ? '#a855f7' : '#27272a';
        }

        if (e.id === 'e-verif-r1') {
          active = Boolean(isR1Active);
          color = active ? '#ef4444' : '#27272a';
        }
        if (e.id === 'e-verif-r2') {
          active = Boolean(isR2Active);
          color = active ? '#10b981' : '#27272a';
        }
        if (e.id === 'e-verif-r3') {
          active = Boolean(isR3Active);
          color = active ? '#3b82f6' : '#27272a';
        }

        if (e.id === 'e-r1-mutex') {
          active = metrics?.center_occupied_by === 'FR3_1';
          color = active ? '#f97316' : '#27272a';
        }
        if (e.id === 'e-r2-mutex') {
          active = metrics?.center_occupied_by === 'FR3_2';
          color = active ? '#f97316' : '#27272a';
        }
        if (e.id === 'e-r3-mutex') {
          active = metrics?.center_occupied_by === 'FR3_3';
          color = active ? '#f97316' : '#27272a';
        }

        if (e.id === 'e-mutex-const') {
          active = Boolean(metrics?.center_occupied_by);
          color = active ? '#38bdf8' : '#27272a';
        }

        return {
          ...e,
          type: 'default', // Organic Bezier curved flow
          animated: active,
          style: {
            stroke: color,
            strokeWidth: active ? 2.5 : 1.5,
            filter: active ? `drop-shadow(0 0 6px ${color})` : 'none',
            transition: 'stroke 0.3s ease, stroke-width 0.3s ease',
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: color,
            width: 14,
            height: 14,
          },
        };
      })
    );
  }, [metrics, chatMessages, actions.length, userGoal, setNodes, setEdges]);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#09090b',
        position: 'relative',
        fontFamily: fontSans,
      }}
    >
      {/* Floating HUD Pill */}
      <div
        style={{
          position: 'absolute',
          top: 16,
          left: 18,
          zIndex: 10,
          background: 'rgba(24, 24, 27, 0.75)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          padding: '6px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: 11,
          color: '#f4f4f5',
          borderRadius: 9999,
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
        }}
      >
        <Activity size={14} color="#38bdf8" />
        <span style={{ fontWeight: 600, letterSpacing: '0.01em' }}>Neural Task Topology</span>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 9,
            padding: '2px 8px',
            background: 'rgba(56, 189, 248, 0.2)',
            color: '#38bdf8',
            borderRadius: 9999,
            fontWeight: 700,
          }}
        >
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#38bdf8', display: 'inline-block' }} />
          LIVE
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.22 }}
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1.2} color="rgba(255, 255, 255, 0.08)" />
        <Controls
          style={{
            background: 'rgba(24, 24, 27, 0.85)',
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 14,
            overflow: 'hidden',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
          }}
        />
        <MiniMap
          nodeStrokeWidth={2}
          zoomable
          pannable
          style={{
            background: 'rgba(18, 18, 24, 0.85)',
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 16,
            overflow: 'hidden',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
          }}
          nodeColor={(n) => {
            if (n.type === 'goalNode') return '#38bdf8';
            if (n.type === 'generatorNode') return '#10b981';
            if (n.type === 'agentNode') return '#38bdf8';
            if (n.type === 'verifierNode') return '#a855f7';
            if (n.type === 'robotNode') return '#10b981';
            if (n.type === 'mutexNode') return '#f97316';
            return '#0ea5e9';
          }}
        />
      </ReactFlow>
    </div>
  );
};
