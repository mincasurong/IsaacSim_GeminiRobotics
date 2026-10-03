import os

filepath = r"D:\git\IsaacSim_Gemini\gemini_web_gui\src\components\AgentWorkflowGraph.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    original = f.read()

# I will write the new content to the file
new_content = '''import React, { useEffect } from 'react';
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
import { Cpu, ShieldAlert, ShieldCheck, Box, Compass, Activity, Terminal } from 'lucide-react';
import { type MetricsData, type ChatMessage, type RobotAction } from './theme';

interface AgentWorkflowGraphProps {
  metrics: MetricsData | null;
  chatMessages: ChatMessage[];
  actions: RobotAction[];
  userGoal: string;
}

// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
// Shared Robotic / Industrial Styles
// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
const roboticNodeStyle = {
  background: '#09090b',
  border: '1px solid #27272a',
  boxShadow: 'inset 0 0 10px rgba(0,0,0,0.5)',
  borderRadius: 4,
  padding: '10px 14px',
  color: '#e4e4e7',
  fontFamily: '"JetBrains Mono", ui-monospace, monospace',
  fontSize: 11,
};

const HeaderTag = ({ color, text, icon: Icon }: any) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 6, borderBottom: \1px solid \40\, paddingBottom: 6, marginBottom: 8 }}>
    <Icon size={14} color={color} />
    <span style={{ color, fontWeight: 700, letterSpacing: '0.05em', fontSize: 10, textTransform: 'uppercase' }}>{text}</span>
  </div>
);

// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
// Custom Node: Human / Goal Node
// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
const GoalNode = ({ data }: { data: { goal: string } }) => {
  return (
    <div style={{ ...roboticNodeStyle, width: 260, borderLeft: '3px solid #38bdf8' }}>
      <HeaderTag color="#38bdf8" text="CMD_DIRECTIVE" icon={Terminal} />
      <div style={{ fontSize: 10, color: '#a1a1aa', marginBottom: 4 }}>[SYS.OPERATOR_INPUT]</div>
      <div style={{
        background: '#18181b',
        padding: 8,
        border: '1px dashed #3f3f46',
        color: '#f4f4f5',
        maxHeight: 60,
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }}>
        > {data.goal || 'AWAITING_INPUT'}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#38bdf8', borderRadius: 0, width: 10, height: 4, border: 'none' }} />
    </div>
  );
};

// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
// Custom Node: Multi-Agent Persona Node
// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
const AgentPersonaNode = ({ data }: any) => {
  return (
    <div style={{ ...roboticNodeStyle, width: 250, borderLeft: \3px solid \\ }}>
      <Handle type="target" position={Position.Top} style={{ background: data.color, borderRadius: 0, width: 10, height: 4, border: 'none' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: \1px solid \40\, paddingBottom: 6, marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>{data.emoji}</span>
          <span style={{ color: data.color, fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>{data.role}</span>
        </div>
        <div style={{ fontSize: 9, color: data.isActive ? data.color : '#52525b', fontWeight: 'bold' }}>
          {data.isActive ? '≒ ACTIVE' : '∞ STANDBY'}
        </div>
      </div>
      <div style={{ fontSize: 9, color: '#71717a', marginBottom: 4 }}>MODEL: {data.model}</div>
      <div style={{
        background: '#18181b',
        padding: '6px 8px',
        border: '1px solid #27272a',
        color: '#a1a1aa',
        minHeight: 38,
        maxHeight: 52,
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }}>
        {data.lastSnippet || '...'}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: data.color, borderRadius: 0, width: 10, height: 4, border: 'none' }} />
    </div>
  );
};

// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
// Custom Node: Robot Arm
// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
const RobotArmNode = ({ data }: any) => {
  const isExecuting = data.phase && data.phase !== 'IDLE' && data.phase !== 'QUEUED';
  
  return (
    <div style={{ ...roboticNodeStyle, width: 240, borderLeft: \3px solid \\ }}>
      <Handle type="target" position={Position.Top} style={{ background: data.color, borderRadius: 0, width: 10, height: 4, border: 'none' }} />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: \1px solid \40\, paddingBottom: 6, marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Cpu size={14} color={data.color} />
          <span style={{ color: '#fff', fontWeight: 700 }}>{data.name}</span>
        </div>
        <div style={{
          background: isExecuting ? \\20\ : '#18181b',
          color: isExecuting ? data.color : '#71717a',
          padding: '2px 6px',
          border: \1px solid \\,
          fontSize: 9,
          fontWeight: 'bold'
        }}>
          {data.phase || 'IDLE'}
        </div>
      </div>
      
      <div style={{ fontSize: 9, color: '#71717a', marginBottom: 6 }}>LOC: {data.quadrant}</div>
      
      <div style={{ background: '#18181b', padding: '6px 8px', border: '1px solid #27272a', marginBottom: 8 }}>
        <div style={{ color: '#52525b', fontSize: 9, marginBottom: 2 }}>TRG_OBJECT:</div>
        <div style={{ color: data.target ? '#d4d4d8' : '#52525b' }}>{data.target || 'NONE'}</div>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#a1a1aa' }}>
        <span>UTIL: <span style={{ color: '#fff' }}>{Math.round(data.busyPct)}%</span></span>
        <span>OPS: <span style={{ color: data.color }}>{data.tasksCompleted}</span></span>
        <span style={{ color: '#38bdf8' }}>100Hz</span>
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: data.color, borderRadius: 0, width: 10, height: 4, border: 'none' }} />
    </div>
  );
};

// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
// Custom Node: Mutex Node
// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
const MutexNode = ({ data }: any) => {
  const isLocked = Boolean(data.occupiedBy);
  const color = isLocked ? '#f97316' : '#10b981';
  
  return (
    <div style={{ ...roboticNodeStyle, width: 230, borderLeft: \3px solid \\ }}>
      <Handle type="target" position={Position.Top} style={{ background: color, borderRadius: 0, width: 10, height: 4, border: 'none' }} />
      <HeaderTag color={color} text="COLLISION_ARBITER" icon={isLocked ? ShieldAlert : ShieldCheck} />
      <div style={{ fontSize: 10, color: '#a1a1aa', marginBottom: 4 }}>STATUS: <span style={{ color, fontWeight: 'bold' }}>{isLocked ? 'LOCKED' : 'CLEAR'}</span></div>
      <div style={{ background: '#18181b', padding: '6px 8px', border: '1px dashed #3f3f46', color: isLocked ? '#f4f4f5' : '#71717a' }}>
        {isLocked ? \OWNER: \\ : 'NO_ACTIVE_OWNER'}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: color, borderRadius: 0, width: 10, height: 4, border: 'none' }} />
    </div>
  );
};

// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
// Custom Node: Construction Node
// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
const ConstructionNode = ({ data }: any) => {
  return (
    <div style={{ ...roboticNodeStyle, width: 250, borderLeft: '3px solid #38bdf8' }}>
      <Handle type="target" position={Position.Top} style={{ background: '#38bdf8', borderRadius: 0, width: 10, height: 4, border: 'none' }} />
      <HeaderTag color="#38bdf8" text="WORLD_STATE" icon={Box} />
      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ flex: 1, background: '#18181b', border: '1px solid #27272a', padding: 8, textAlign: 'center' }}>
          <div style={{ fontSize: 9, color: '#71717a', marginBottom: 4 }}>LAYERS</div>
          <div style={{ fontSize: 16, color: '#38bdf8', fontWeight: 'bold' }}>{data.towerHeight}</div>
        </div>
        <div style={{ flex: 1, background: '#18181b', border: '1px solid #27272a', padding: 8, textAlign: 'center' }}>
          <div style={{ fontSize: 9, color: '#71717a', marginBottom: 4 }}>SIM_PHYSICS</div>
          <div style={{ fontSize: 12, color: '#10b981', fontWeight: 'bold', marginTop: 4 }}>STABLE</div>
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

const initialNodes: Node[] = [
  { id: 'goal', type: 'goalNode', position: { x: 370, y: 20 }, data: { goal: '' } },
  { id: 'orchestrator', type: 'agentNode', position: { x: 50, y: 160 }, data: { role: 'VLA_ORCHESTRATOR', emoji: '??', color: '#38bdf8', model: 'gemini-robotics-er-2' } },
  { id: 'architect', type: 'agentNode', position: { x: 370, y: 160 }, data: { role: 'SPATIAL_ARCHITECT', emoji: '??', color: '#a78bfa', model: 'gemini-3.8-flash' } },
  { id: 'optimizer', type: 'agentNode', position: { x: 690, y: 160 }, data: { role: 'AGILITY_OPTIMIZER', emoji: '?', color: '#fbbf24', model: 'gemini-3.8-flash' } },
  { id: 'robot1', type: 'robotNode', position: { x: 50, y: 350 }, data: { name: 'FR3_1', color: '#ef4444', quadrant: 'TABLE_1' } },
  { id: 'robot2', type: 'robotNode', position: { x: 370, y: 350 }, data: { name: 'FR3_2', color: '#10b981', quadrant: 'TABLE_2' } },
  { id: 'robot3', type: 'robotNode', position: { x: 690, y: 350 }, data: { name: 'FR3_3', color: '#3b82f6', quadrant: 'TABLE_3' } },
  { id: 'mutex', type: 'mutexNode', position: { x: 380, y: 550 }, data: { occupiedBy: null } },
  { id: 'construction', type: 'constructionNode', position: { x: 370, y: 690 }, data: { towerHeight: 0, placedCount: 0 } },
];

const initialEdges: Edge[] = [
  { id: 'e-goal-orch', source: 'goal', target: 'orchestrator', type: 'step' },
  { id: 'e-orch-arch', source: 'orchestrator', target: 'architect', type: 'step' },
  { id: 'e-arch-opt', source: 'architect', target: 'optimizer', type: 'step' },
  { id: 'e-opt-r1', source: 'optimizer', target: 'robot1', type: 'step' },
  { id: 'e-opt-r2', source: 'optimizer', target: 'robot2', type: 'step' },
  { id: 'e-opt-r3', source: 'optimizer', target: 'robot3', type: 'step' },
  { id: 'e-r1-mutex', source: 'robot1', target: 'mutex', type: 'step' },
  { id: 'e-r2-mutex', source: 'robot2', target: 'mutex', type: 'step' },
  { id: 'e-r3-mutex', source: 'robot3', target: 'mutex', type: 'step' },
  { id: 'e-mutex-const', source: 'mutex', target: 'construction', type: 'step' },
];

// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
// Main Agent Workflow Graph Component
// 式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式式
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
    const latestVla = [...chatMessages].reverse().find(m => m.role === 'vla');
    const latestArchitect = [...chatMessages].reverse().find(m => m.role === 'architect' && (m.senderName?.includes('Spatial') || m.emoji === '??'));
    const latestOptimizer = [...chatMessages].reverse().find(m => m.role === 'architect' && (m.senderName?.includes('Performance') || m.senderName?.includes('Optimizer') || m.emoji === '?'));

    const lastMessage = chatMessages[chatMessages.length - 1];
    const isVlaSpeaking = lastMessage?.role === 'vla';
    const isArchitectSpeaking = lastMessage?.role === 'architect' && (lastMessage?.senderName?.includes('Spatial') || lastMessage?.emoji === '??');
    const isOptimizerSpeaking = lastMessage?.role === 'architect' && (lastMessage?.senderName?.includes('Performance') || lastMessage?.emoji === '?');

    const r1 = metrics?.robots?.FR3_1;
    const r2 = metrics?.robots?.FR3_2;
    const r3 = metrics?.robots?.FR3_3;

    const isR1Active = r1 && r1.phase !== 'IDLE' && r1.phase !== 'QUEUED';
    const isR2Active = r2 && r2.phase !== 'IDLE' && r2.phase !== 'QUEUED';
    const isR3Active = r3 && r3.phase !== 'IDLE' && r3.phase !== 'QUEUED';

    // Update Nodes Data (preserving positions)
    setNodes((nds) => 
      nds.map((n) => {
        if (n.id === 'goal') n.data = { ...n.data, goal: userGoal };
        if (n.id === 'orchestrator') n.data = { ...n.data, isActive: isVlaSpeaking, lastSnippet: latestVla?.text ? latestVla.text.slice(0, 80) + '...' : n.data.lastSnippet };
        if (n.id === 'architect') n.data = { ...n.data, isActive: isArchitectSpeaking, lastSnippet: latestArchitect?.text ? latestArchitect.text.slice(0, 80) + '...' : n.data.lastSnippet };
        if (n.id === 'optimizer') n.data = { ...n.data, isActive: isOptimizerSpeaking, lastSnippet: latestOptimizer?.text ? latestOptimizer.text.slice(0, 80) + '...' : n.data.lastSnippet };
        
        if (n.id === 'robot1') n.data = { ...n.data, phase: r1?.phase, target: r1?.target, busyPct: r1?.busy_pct, tasksCompleted: r1?.tasks_completed };
        if (n.id === 'robot2') n.data = { ...n.data, phase: r2?.phase, target: r2?.target, busyPct: r2?.busy_pct, tasksCompleted: r2?.tasks_completed };
        if (n.id === 'robot3') n.data = { ...n.data, phase: r3?.phase, target: r3?.target, busyPct: r3?.busy_pct, tasksCompleted: r3?.tasks_completed };
        
        if (n.id === 'mutex') n.data = { ...n.data, occupiedBy: metrics?.center_occupied_by };
        if (n.id === 'construction') n.data = { ...n.data, towerHeight: metrics?.tower_height, placedCount: actions.length };
        
        // Hide robot3 if not present in metrics but we had it initialized, but keeping it visible as standby is also fine for industrial style.
        // We'll leave it as standby.
        return n;
      })
    );

    // Update Edges Data
    setEdges((eds) => 
      eds.map((e) => {
        let active = false;
        let color = '#3f3f46';
        if (e.id === 'e-goal-orch') { active = isVlaSpeaking; color = active ? '#38bdf8' : '#3f3f46'; }
        if (e.id === 'e-orch-arch') { active = isArchitectSpeaking; color = active ? '#a78bfa' : '#3f3f46'; }
        if (e.id === 'e-arch-opt') { active = isOptimizerSpeaking; color = active ? '#fbbf24' : '#3f3f46'; }
        
        if (e.id === 'e-opt-r1') { active = Boolean(isR1Active); color = active ? '#ef4444' : '#3f3f46'; }
        if (e.id === 'e-opt-r2') { active = Boolean(isR2Active); color = active ? '#10b981' : '#3f3f46'; }
        if (e.id === 'e-opt-r3') { active = Boolean(isR3Active); color = active ? '#3b82f6' : '#3f3f46'; }
        
        if (e.id === 'e-r1-mutex') { active = metrics?.center_occupied_by === 'FR3_1'; color = active ? '#f97316' : '#3f3f46'; }
        if (e.id === 'e-r2-mutex') { active = metrics?.center_occupied_by === 'FR3_2'; color = active ? '#f97316' : '#3f3f46'; }
        if (e.id === 'e-r3-mutex') { active = metrics?.center_occupied_by === 'FR3_3'; color = active ? '#f97316' : '#3f3f46'; }
        
        if (e.id === 'e-mutex-const') { active = Boolean(metrics?.center_occupied_by); color = active ? '#38bdf8' : '#3f3f46'; }

        return {
          ...e,
          animated: active,
          style: { stroke: color, strokeWidth: active ? 2 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, color: color }
        };
      })
    );
  }, [metrics, chatMessages, actions.length, userGoal, setNodes, setEdges]);

  return (
    <div style={{ width: '100%', height: '100%', background: '#000', position: 'relative', fontFamily: '"JetBrains Mono", monospace' }}>
      <div style={{
        position: 'absolute', top: 14, left: 16, zIndex: 10,
        background: '#09090b', border: '1px solid #27272a', padding: '6px 12px',
        display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#e4e4e7'
      }}>
        <Activity size={14} color="#38bdf8" />
        <span>SYS.TELEMETRY_GRAPH</span>
        <span style={{ fontSize: 9, padding: '2px 6px', background: '#0284c7', color: '#fff' }}>LIVE</span>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.5} color="#27272a" />
        <Controls style={{ background: '#09090b', border: '1px solid #27272a' }} />
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
          style={{ background: '#09090b', border: '1px solid #27272a' }}
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
'''

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)
print("Updated AgentWorkflowGraph.tsx")
