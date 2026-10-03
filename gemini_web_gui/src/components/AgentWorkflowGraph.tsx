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
  Lock,
} from 'lucide-react';
import { type MetricsData, type ChatMessage, type RobotAction } from './theme';

interface AgentWorkflowGraphProps {
  metrics: MetricsData | null;
  chatMessages: ChatMessage[];
  actions: RobotAction[];
  results: RobotAction[];
  userGoal: string;
  mode?: number;
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
  const isDenied = Boolean(data.deny);
  const glow = isDenied ? `0 0 25px rgba(239, 68, 68, 0.35)` : (isExecuting ? `0 0 25px ${data.color}35` : 'none');
  const borderColor = isDenied ? '#ef4444' : (isExecuting ? data.color : 'rgba(255, 255, 255, 0.1)');

  return (
    <div
      style={{
        ...baseFlowCardStyle,
        width: 250,
        border: `1px solid ${borderColor}`,
        boxShadow: `0 14px 32px -4px rgba(0, 0, 0, 0.6), ${glow}`,
      }}
    >
      <Handle type="target" position={Position.Top} style={makeHandleStyle(isDenied ? '#ef4444' : data.color)} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 10,
              background: isDenied ? 'rgba(239, 68, 68, 0.2)' : `${data.color}20`,
              border: `1px solid ${isDenied ? 'rgba(239, 68, 68, 0.5)' : `${data.color}50`}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: `0 0 10px ${isDenied ? 'rgba(239, 68, 68, 0.25)' : `${data.color}25`}`,
            }}
          >
            {isDenied ? <Lock size={16} color="#ef4444" /> : <Bot size={16} color={data.color} />}
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ffffff' }}>{data.name}</div>
            <div style={{ fontSize: 9, color: '#a1a1aa' }}>{data.quadrant}</div>
          </div>
        </div>
        <Pill color={isDenied ? '#ef4444' : (isExecuting ? data.color : '#71717a')} pulse={isExecuting || isDenied}>
          {isDenied ? 'DENIED' : (data.phase || 'IDLE')}
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

      {isDenied && (
        <div style={{ fontSize: 10, color: '#ef4444', marginBottom: 10, lineHeight: 1.3 }}>
          {data.deny.reason}
        </div>
      )}

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

      <Handle type="source" position={Position.Bottom} style={makeHandleStyle(isDenied ? '#ef4444' : data.color)} />
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
// Custom Node: Construction / Workspace Output Node
// ─────────────────────────────────────────────────────────────
const ConstructionNode = ({ data }: any) => {
  const currentMode = data.mode ?? 1;
  const isConveyor = currentMode === 5;
  const isAssembly = currentMode === 6;

  const title = isConveyor ? 'Conveyor Digital Twin' : (isAssembly ? 'Dual-Arm Workcell' : 'Tower Digital Twin');
  const subtitle = isConveyor ? 'PhysX Conveyor Feed' : (isAssembly ? 'Assembly Station' : 'PhysX Rigid Bodies');
  const metricLabel = isConveyor ? 'Items Handled' : (isAssembly ? 'Parts Placed' : 'Layers Stacked');
  const metricValue = isConveyor || isAssembly ? (data.placedCount || 0) : (data.towerHeight || 0);
  const metricSub = isConveyor || isAssembly ? ' processed' : '/9';

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
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ffffff' }}>{title}</div>
            <div style={{ fontSize: 9, color: '#94a3b8' }}>{subtitle}</div>
          </div>
        </div>
        <Pill color="#10b981">
          <CheckCircle2 size={10} style={{ marginRight: 2 }} /> Active
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
          <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 2 }}>{metricLabel}</div>
          <div style={{ fontSize: 18, color: '#38bdf8', fontWeight: 800, fontFamily: fontMono }}>
            {metricValue}
            <span style={{ fontSize: 11, color: '#64748b' }}>{metricSub}</span>
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
          <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 2 }}>Execution State</div>
          <div style={{ fontSize: 13, color: '#10b981', fontWeight: 700, marginTop: 4 }}>
            Synchronized
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

const getRobotMeta = (robotKey: string, currentMode: number) => {
  if (currentMode === 5) {
    if (robotKey === 'FR3_1') return { name: 'FR3_1 (Left Arm)', color: '#ef4444', quadrant: 'Conveyor Sector L' };
    if (robotKey === 'FR3_2') return { name: 'FR3_2 (Right Arm)', color: '#10b981', quadrant: 'Conveyor Sector R' };
  } else if (currentMode === 6) {
    if (robotKey === 'FR3_1') return { name: 'FR3_1 (Primary)', color: '#ef4444', quadrant: 'Assembly Cell A' };
    if (robotKey === 'FR3_2') return { name: 'FR3_2 (Secondary)', color: '#10b981', quadrant: 'Assembly Cell B' };
  }
  if (robotKey === 'FR3_1') return { name: 'FR3_1 (Bottom)', color: '#ef4444', quadrant: 'Table 1' };
  if (robotKey === 'FR3_2') return { name: 'FR3_2 (Top-Right)', color: '#10b981', quadrant: 'Table 2' };
  if (robotKey === 'FR3_3') return { name: 'FR3_3 (Top-Left)', color: '#3b82f6', quadrant: 'Table 3' };
  return { name: robotKey, color: '#a855f7', quadrant: 'Workstation' };
};

const getRobotId = (robotKey: string) => {
  if (robotKey === 'FR3_1') return 'robot1';
  if (robotKey === 'FR3_2') return 'robot2';
  if (robotKey === 'FR3_3') return 'robot3';
  return `robot_${robotKey.toLowerCase()}`;
};

// ─────────────────────────────────────────────────────────────
// Main Agent Workflow Graph Component
// ─────────────────────────────────────────────────────────────
export const AgentWorkflowGraph: React.FC<AgentWorkflowGraphProps> = ({
  metrics,
  chatMessages,
  actions,
  results = [],
  userGoal,
  mode = 1,
}) => {
  // Dynamically compute active robot keys based on mode or live telemetry
  const robotKeys = React.useMemo(() => {
    if (mode === 5 || mode === 6) {
      return ['FR3_1', 'FR3_2'];
    }
    if (metrics?.robots && Object.keys(metrics.robots).length > 0) {
      return Object.keys(metrics.robots).sort();
    }
    return ['FR3_1', 'FR3_2', 'FR3_3'];
  }, [metrics?.robots, mode]);

  // Center robot cards dynamically under X=500
  const getRobotX = (index: number, count: number) => {
    const gap = count === 2 ? 80 : 60;
    const totalWidth = count * 260 + Math.max(0, count - 1) * gap;
    const startX = 500 - totalWidth / 2;
    return startX + index * (260 + gap);
  };

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
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

    const isRobotActive = (key: string) => {
      const r = metrics?.robots?.[key];
      return Boolean(r && r.phase !== 'IDLE' && r.phase !== 'QUEUED');
    };
    const anyRobotActive = robotKeys.some(isRobotActive);

    // Build the complete, adaptive nodes list
    const currentNodes: Node[] = [
      { id: 'goal', type: 'goalNode', position: { x: 370, y: 20 }, data: { goal: userGoal } },
      {
        id: 'generator',
        type: 'generatorNode',
        position: { x: 370, y: 160 },
        data: {
          isActive: Boolean(isGeneratorSpeaking || latestGenerator),
          lastSnippet: latestGenerator?.text ? latestGenerator.text.slice(0, 95) + '...' : '',
        },
      },
      {
        id: 'orchestrator',
        type: 'agentNode',
        position: { x: 370, y: 310 },
        data: {
          role: 'VLA Brain',
          emoji: '🦾',
          color: '#38bdf8',
          model: 'gemini-robotics-er-2',
          isActive: isVlaSpeaking,
          lastSnippet: latestVla?.text ? latestVla.text.slice(0, 95) + '...' : '',
        },
      },
      {
        id: 'verifier',
        type: 'verifierNode',
        position: { x: 370, y: 460 },
        data: {
          isActive: Boolean(anyRobotActive),
          lastSnippet: anyRobotActive
            ? 'Guarding active pick/place kinematics, table ownership, & mutex locks'
            : (mode === 5
                ? 'Conveyor tracking reachability: FR3_1 (Sector L), FR3_2 (Sector R)'
                : (mode === 6
                    ? 'Dual-arm assembly workspace: FR3_1 (Cell A), FR3_2 (Cell B)'
                    : 'Grounded physical reachability: Table 1 (FR3_1), Table 2 (FR3_2), Table 3 (FR3_3)')),
        },
      },
    ];

    // Add active robot nodes with dynamic positioning
    robotKeys.forEach((rKey, index) => {
      const rId = getRobotId(rKey);
      const rData = metrics?.robots?.[rKey];
      const meta = getRobotMeta(rKey, mode);
      
      // Find latest result for this robot
      const latestResult = [...results].reverse().find(r => {
        try {
          const parsed = JSON.parse(r.raw);
          return parsed.robot_id === rKey;
        } catch {
          return false;
        }
      });
      
      let deny = null;
      if (latestResult) {
        try {
          const parsed = JSON.parse(latestResult.raw);
          if (!parsed.success && parsed.message.includes('Guardrail Deny')) {
            const denyJson = parsed.message.split('Guardrail Deny: ')[1];
            deny = JSON.parse(denyJson);
          }
        } catch (e) {}
      }

      currentNodes.push({
        id: rId,
        type: 'robotNode',
        position: { x: getRobotX(index, robotKeys.length), y: 620 },
        data: {
          name: meta.name,
          color: meta.color,
          quadrant: meta.quadrant,
          phase: rData?.phase,
          target: rData?.target,
          busyPct: rData?.busy_pct,
          tasksCompleted: rData?.tasks_completed,
          deny: deny,
        },
      });
    });

    currentNodes.push({
      id: 'mutex',
      type: 'mutexNode',
      position: { x: 370, y: 810 },
      data: { occupiedBy: metrics?.center_occupied_by },
    });

    currentNodes.push({
      id: 'construction',
      type: 'constructionNode',
      position: { x: 370, y: 960 },
      data: {
        towerHeight: metrics?.tower_height,
        placedCount: actions.length,
        mode: mode,
      },
    });

    setNodes(currentNodes);

    // Build adaptive edges
    const currentEdges: Edge[] = [
      {
        id: 'e-goal-gen',
        source: 'goal',
        target: 'generator',
        type: 'default',
        animated: isGeneratorSpeaking || isVlaSpeaking,
        style: {
          stroke: isGeneratorSpeaking || isVlaSpeaking ? '#10b981' : '#27272a',
          strokeWidth: isGeneratorSpeaking || isVlaSpeaking ? 2.5 : 1.5,
          filter: isGeneratorSpeaking || isVlaSpeaking ? 'drop-shadow(0 0 6px #10b981)' : 'none',
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: isGeneratorSpeaking || isVlaSpeaking ? '#10b981' : '#27272a', width: 14, height: 14 },
      },
      {
        id: 'e-gen-vla',
        source: 'generator',
        target: 'orchestrator',
        type: 'default',
        animated: isVlaSpeaking,
        style: {
          stroke: isVlaSpeaking ? '#38bdf8' : '#27272a',
          strokeWidth: isVlaSpeaking ? 2.5 : 1.5,
          filter: isVlaSpeaking ? 'drop-shadow(0 0 6px #38bdf8)' : 'none',
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: isVlaSpeaking ? '#38bdf8' : '#27272a', width: 14, height: 14 },
      },
      {
        id: 'e-vla-verif',
        source: 'orchestrator',
        target: 'verifier',
        type: 'default',
        animated: Boolean(anyRobotActive),
        style: {
          stroke: anyRobotActive ? '#a855f7' : '#27272a',
          strokeWidth: anyRobotActive ? 2.5 : 1.5,
          filter: anyRobotActive ? 'drop-shadow(0 0 6px #a855f7)' : 'none',
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: anyRobotActive ? '#a855f7' : '#27272a', width: 14, height: 14 },
      },
    ];

    robotKeys.forEach((rKey) => {
      const rId = getRobotId(rKey);
      const meta = getRobotMeta(rKey, mode);
      const isAct = isRobotActive(rKey);
      const isMutexAct = metrics?.center_occupied_by === rKey;

      currentEdges.push({
        id: `e-verif-${rId}`,
        source: 'verifier',
        target: rId,
        type: 'default',
        animated: isAct,
        style: {
          stroke: isAct ? meta.color : '#27272a',
          strokeWidth: isAct ? 2.5 : 1.5,
          filter: isAct ? `drop-shadow(0 0 6px ${meta.color})` : 'none',
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: isAct ? meta.color : '#27272a', width: 14, height: 14 },
      });

      currentEdges.push({
        id: `e-${rId}-mutex`,
        source: rId,
        target: 'mutex',
        type: 'default',
        animated: isMutexAct,
        style: {
          stroke: isMutexAct ? '#f97316' : '#27272a',
          strokeWidth: isMutexAct ? 2.5 : 1.5,
          filter: isMutexAct ? 'drop-shadow(0 0 6px #f97316)' : 'none',
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: isMutexAct ? '#f97316' : '#27272a', width: 14, height: 14 },
      });
    });

    const isConstAct = Boolean(metrics?.center_occupied_by);
    currentEdges.push({
      id: 'e-mutex-const',
      source: 'mutex',
      target: 'construction',
      type: 'default',
      animated: isConstAct,
      style: {
        stroke: isConstAct ? '#38bdf8' : '#27272a',
        strokeWidth: isConstAct ? 2.5 : 1.5,
        filter: isConstAct ? 'drop-shadow(0 0 6px #38bdf8)' : 'none',
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: isConstAct ? '#38bdf8' : '#27272a', width: 14, height: 14 },
    });

    setEdges(currentEdges);
  }, [metrics, chatMessages, actions.length, results, userGoal, mode, robotKeys, setNodes, setEdges]);

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
