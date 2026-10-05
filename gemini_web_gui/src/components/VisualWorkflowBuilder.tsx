import React, { useState, useCallback, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  MarkerType,
  BackgroundVariant,
  type Connection,
  type NodeProps,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Play,
  Square,
  Trash2,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Zap,
} from 'lucide-react';
import { C, monoFont } from './theme';

export interface WorkflowStepData {
  [key: string]: any;
  id: string;
  action: 'pick' | 'place' | 'dual_arm_pick' | 'dual_arm_circle' | 'dual_arm_place' | 'go_home' | 'wait_mutex';
  robot: string;
  target?: string;
  x?: number;
  y?: number;
  speed?: string;
  radius?: number;
  plane?: string;
  cycles?: number;
  status: 'idle' | 'running' | 'success' | 'failed';
  label?: string;
}

// ─────────────────────────────────────────────────────────────
// Custom Node Component: TaskActionNode
// ─────────────────────────────────────────────────────────────
const TaskActionNode = ({ id, data }: NodeProps<Node<WorkflowStepData>>) => {
  const { setNodes, setEdges } = useReactFlow();

  const updateField = (field: keyof WorkflowStepData, val: any) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === id) {
          return { ...n, data: { ...n.data, [field]: val } };
        }
        return n;
      })
    );
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  };

  const getActionColor = () => {
    switch (data.action) {
      case 'pick': return '#3b82f6';
      case 'place': return '#10b981';
      case 'dual_arm_pick': return '#8b5cf6';
      case 'dual_arm_circle': return '#ec4899';
      case 'dual_arm_place': return '#06b6d4';
      case 'wait_mutex': return '#f59e0b';
      case 'go_home': return '#6b7280';
      default: return '#3b82f6';
    }
  };

  const getStatusBorder = () => {
    if (data.status === 'running') return '2px solid #fbbf24';
    if (data.status === 'success') return '2px solid #10b981';
    if (data.status === 'failed') return '2px solid #ef4444';
    return `1px solid ${C.nodeBorderHi}`;
  };

  const getStatusGlow = () => {
    if (data.status === 'running') return '0 0 16px rgba(251, 191, 36, 0.4)';
    if (data.status === 'success') return '0 0 16px rgba(16, 185, 129, 0.4)';
    if (data.status === 'failed') return '0 0 16px rgba(239, 68, 68, 0.4)';
    return C.nodeShadow;
  };

  const color = getActionColor();
  const isDual = data.action.startsWith('dual_arm');

  return (
    <div
      style={{
        background: C.nodeBg,
        border: getStatusBorder(),
        boxShadow: getStatusGlow(),
        borderRadius: 14,
        padding: '12px 14px',
        width: 240,
        color: C.text,
        fontSize: 12,
        position: 'relative',
        transition: 'all 0.2s ease',
      }}
    >
      {/* Input Port (Top) - Sleek Half-Moon Translucent Port */}
      <Handle
        type="target"
        position={Position.Top}
        style={{
          width: 30,
          height: 8,
          top: -4,
          borderRadius: '16px 16px 0 0',
          background: C.nodeBorderHi,
          border: `1px solid ${C.borderHi}`,
          backdropFilter: 'blur(8px)',
          boxShadow: '0 -2px 6px rgba(0, 0, 0, 0.15)',
          cursor: 'crosshair',
          transition: 'all 0.15s ease',
        }}
        title="Input: Connect predecessor step"
      />

      {/* Node Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 6,
              background: `${color}25`,
              border: `1px solid ${color}50`,
              color: color,
              fontSize: 10.5,
              fontWeight: 800,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            {data.action.replace(/_/g, ' ')}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {data.status === 'running' && <Zap size={14} color="#fbbf24" className="animate-spin" />}
          {data.status === 'success' && <CheckCircle2 size={14} color="#10b981" />}
          {data.status === 'failed' && <AlertTriangle size={14} color="#ef4444" />}
          <button
            onClick={handleDelete}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: C.textMuted,
              padding: 2,
              display: 'flex',
              alignItems: 'center',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ef4444')}
            onMouseLeave={(e) => (e.currentTarget.style.color = C.textMuted)}
            title="Delete step"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Interactive Form Controls */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
        {/* Robot Selector */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ color: C.textDim, fontWeight: 600 }}>Robot:</span>
          {isDual ? (
            <select
              value={data.robot}
              onChange={(e) => updateField('robot', e.target.value)}
              style={{
                background: C.inputBg,
                border: `1px solid ${C.inputBorder}`,
                borderRadius: 5,
                color: C.inputText,
                fontSize: 11,
                fontWeight: 700,
                padding: '2px 6px',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="FR3_1+FR3_2">FR3_1 + FR3_2 (Bimanual)</option>
            </select>
          ) : (
            <select
              value={data.robot}
              onChange={(e) => updateField('robot', e.target.value)}
              style={{
                background: C.inputBg,
                border: `1px solid ${C.inputBorder}`,
                borderRadius: 5,
                color: C.inputText,
                fontSize: 11,
                fontWeight: 700,
                padding: '2px 6px',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="FR3_1">FR3_1 (Bottom / Table 1)</option>
              <option value="FR3_2">FR3_2 (Right / Table 2)</option>
              <option value="FR3_3">FR3_3 (Left / Table 3)</option>
            </select>
          )}
        </div>

        {/* Target Selector (for pick actions) */}
        {data.action === 'pick' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: C.textDim, fontWeight: 600 }}>Target:</span>
            <select
              value={data.target || 'Block1'}
              onChange={(e) => updateField('target', e.target.value)}
              style={{
                background: C.inputBg,
                border: `1px solid ${C.inputBorder}`,
                borderRadius: 5,
                color: C.inputText,
                fontSize: 11,
                fontWeight: 600,
                padding: '2px 6px',
                outline: 'none',
                cursor: 'pointer',
                maxWidth: 145,
              }}
            >
              <optgroup label="Cubes & Cylinders (Tower)">
                <option value="Block1">Block 1 (Red Cube)</option>
                <option value="Block2">Block 2 (Green Cyl)</option>
                <option value="Block3">Block 3 (Blue Cube)</option>
                <option value="Block4">Block 4 (Yellow Cyl)</option>
                <option value="Block5">Block 5 (Magenta Cube)</option>
                <option value="Block6">Block 6 (Cyan Cyl)</option>
                <option value="Block7">Block 7 (Orange Cube)</option>
                <option value="Block8">Block 8 (Purple Cyl)</option>
                <option value="Block9">Block 9 (Lime Cube)</option>
              </optgroup>
              <optgroup label="Conveyor Stream">
                <option value="ConvItem0">ConvItem 0</option>
                <option value="ConvItem1">ConvItem 1</option>
                <option value="ConvItem2">ConvItem 2</option>
                <option value="ConvItem3">ConvItem 3</option>
              </optgroup>
            </select>
          </div>
        )}

        {data.action === 'dual_arm_pick' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: C.textDim, fontWeight: 600 }}>Object:</span>
            <select
              value={data.target || 'LongBar'}
              onChange={(e) => updateField('target', e.target.value)}
              style={{
                background: C.inputBg,
                border: `1px solid ${C.inputBorder}`,
                borderRadius: 5,
                color: C.inputText,
                fontSize: 11,
                fontWeight: 600,
                padding: '2px 6px',
                outline: 'none',
                cursor: 'pointer',
                maxWidth: 145,
              }}
            >
              <option value="LongBar">LongBar (0.8m Blue)</option>
              <option value="HeavyEnginePart">HeavyEnginePart (1.0m)</option>
            </select>
          </div>
        )}

        {/* Coordinate Targets (for place & dual_arm_place) */}
        {(data.action === 'place' || data.action === 'dual_arm_place') && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: C.textDim, fontWeight: 600 }}>Pos [X, Y]:</span>
            <div style={{ display: 'flex', gap: 4 }}>
              <input
                type="number"
                step="0.05"
                value={data.x ?? 0.0}
                onChange={(e) => updateField('x', parseFloat(e.target.value) || 0)}
                style={{
                  width: 52,
                  background: C.inputBg,
                  border: `1px solid ${C.inputBorder}`,
                  borderRadius: 4,
                  color: C.inputText,
                  fontSize: 11,
                  textAlign: 'center',
                  padding: '2px 3px',
                  fontFamily: monoFont,
                  outline: 'none',
                }}
                title="X Coordinate"
              />
              <input
                type="number"
                step="0.05"
                value={data.y ?? (data.action === 'dual_arm_place' ? 0.25 : 0.0)}
                onChange={(e) => updateField('y', parseFloat(e.target.value) || 0)}
                style={{
                  width: 52,
                  background: C.inputBg,
                  border: `1px solid ${C.inputBorder}`,
                  borderRadius: 4,
                  color: C.inputText,
                  fontSize: 11,
                  textAlign: 'center',
                  padding: '2px 3px',
                  fontFamily: monoFont,
                  outline: 'none',
                }}
                title="Y Coordinate"
              />
            </div>
          </div>
        )}

        {/* Circular Wave Trajectory Parameters */}
        {data.action === 'dual_arm_circle' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: C.textDim, fontWeight: 600 }}>Plane/Rad:</span>
            <div style={{ display: 'flex', gap: 4 }}>
              <select
                value={data.plane || 'XY'}
                onChange={(e) => updateField('plane', e.target.value)}
                style={{
                  background: C.inputBg,
                  border: `1px solid ${C.inputBorder}`,
                  borderRadius: 4,
                  color: C.inputText,
                  fontSize: 10.5,
                  padding: '2px 4px',
                  outline: 'none',
                }}
              >
                <option value="XY">XY (Flat)</option>
                <option value="YZ">YZ (Pitch)</option>
                <option value="XZ">XZ (Roll)</option>
              </select>
              <select
                value={data.radius ?? 0.08}
                onChange={(e) => updateField('radius', parseFloat(e.target.value))}
                style={{
                  background: C.inputBg,
                  border: `1px solid ${C.inputBorder}`,
                  borderRadius: 4,
                  color: C.inputText,
                  fontSize: 10.5,
                  padding: '2px 4px',
                  outline: 'none',
                }}
              >
                <option value={0.06}>6 cm</option>
                <option value={0.08}>8 cm</option>
                <option value={0.10}>10 cm</option>
              </select>
            </div>
          </div>
        )}

        {/* Speed Option */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ color: C.textDim, fontWeight: 600 }}>Speed:</span>
          <select
            value={data.speed || 'fast'}
            onChange={(e) => updateField('speed', e.target.value)}
            style={{
              background: C.inputBg,
              border: `1px solid ${C.inputBorder}`,
              borderRadius: 4,
              color: C.inputText,
              fontSize: 10.5,
              fontWeight: 600,
              padding: '2px 6px',
              outline: 'none',
              cursor: 'pointer',
            }}
          >
            <option value="fast">Fast (Agile 50Hz)</option>
            <option value="normal">Normal</option>
            <option value="slow">Slow (Precision)</option>
          </select>
        </div>
      </div>

      {/* Output Port (Bottom) - Sleek Half-Moon Translucent Port */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          width: 30,
          height: 8,
          bottom: -4,
          borderRadius: '0 0 16px 16px',
          background: color,
          border: `1px solid ${color}`,
          boxShadow: `0 2px 8px ${color}60`,
          cursor: 'crosshair',
          transition: 'all 0.15s ease',
        }}
        title="Output: Drag wire to next step"
      />
    </div>
  );
};

const nodeTypes = {
  taskAction: TaskActionNode,
};

// ─────────────────────────────────────────────────────────────
// Custom Removable Edge Component with Inline Delete Button
// ─────────────────────────────────────────────────────────────
const RemovableEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
}: EdgeProps) => {
  const { setEdges } = useReactFlow();
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const onEdgeDeleteClick = (evt: React.MouseEvent) => {
    evt.stopPropagation();
    setEdges((edges) => edges.filter((edge) => edge.id !== id));
  };

  return (
    <>
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={{ ...style, strokeWidth: 2.5 }} />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            fontSize: 11,
            pointerEvents: 'all',
            zIndex: 1000,
          }}
          className="nodrag nopan"
        >
          <button
            onClick={onEdgeDeleteClick}
            style={{
              width: 20,
              height: 20,
              background: C.hudBg,
              border: '1.5px solid rgba(239, 68, 68, 0.7)',
              color: '#ef4444',
              borderRadius: '50%',
              fontSize: 11,
              fontWeight: 800,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0,0,0,0.6), 0 0 6px rgba(239, 68, 68, 0.3)',
              padding: 0,
              lineHeight: 1,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#ef4444';
              e.currentTarget.style.color = '#ffffff';
              e.currentTarget.style.transform = 'scale(1.25)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'var(--hudBg, #18181b)';
              e.currentTarget.style.color = '#ef4444';
              e.currentTarget.style.transform = 'scale(1)';
            }}
            title="Delete this connection (wire)"
          >
            ✕
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

const edgeTypes = {
  removable: RemovableEdge,
};

// ─────────────────────────────────────────────────────────────
// Predefined Workflow Templates (Parallel & Serial)
// ─────────────────────────────────────────────────────────────
const TEMPLATES: Record<string, { nodes: Node[]; edges: Edge[] }> = {
  parallel_tower: {
    nodes: [
      // Wavefront Stage 1: 3 Arms Pick Simultaneously in Parallel!
      { id: '1', type: 'taskAction', position: { x: 40, y: 40 }, data: { id: '1', action: 'pick', robot: 'FR3_1', target: 'Block1', speed: 'fast', status: 'idle' } },
      { id: '2', type: 'taskAction', position: { x: 310, y: 40 }, data: { id: '2', action: 'pick', robot: 'FR3_2', target: 'Block4', speed: 'fast', status: 'idle' } },
      { id: '3', type: 'taskAction', position: { x: 580, y: 40 }, data: { id: '3', action: 'pick', robot: 'FR3_3', target: 'Block7', speed: 'fast', status: 'idle' } },

      // Wavefront Stage 2: Sequenced Center Table Placement (protected by mutex)
      { id: '4', type: 'taskAction', position: { x: 40, y: 230 }, data: { id: '4', action: 'place', robot: 'FR3_1', x: 0.0, y: 0.0, speed: 'fast', status: 'idle' } },
      { id: '5', type: 'taskAction', position: { x: 310, y: 410 }, data: { id: '5', action: 'place', robot: 'FR3_2', x: 0.0, y: 0.0, speed: 'fast', status: 'idle' } },
      { id: '6', type: 'taskAction', position: { x: 580, y: 590 }, data: { id: '6', action: 'place', robot: 'FR3_3', x: 0.0, y: 0.0, speed: 'fast', status: 'idle' } },
    ],
    edges: [
      { id: 'e1-4', source: '1', target: '4', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
      { id: 'e2-5', source: '2', target: '5', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
      { id: 'e3-6', source: '3', target: '6', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
      // Mutex serialization for center table: FR3_1 -> FR3_2 -> FR3_3
      { id: 'e4-5', source: '4', target: '5', animated: true, style: { stroke: '#fbbf24', strokeDasharray: '5,5' }, markerEnd: { type: MarkerType.ArrowClosed } },
      { id: 'e5-6', source: '5', target: '6', animated: true, style: { stroke: '#fbbf24', strokeDasharray: '5,5' }, markerEnd: { type: MarkerType.ArrowClosed } },
    ],
  },
  parallel_conveyor: {
    nodes: [
      // Branch 1 (Left Conveyor Sector)
      { id: '1', type: 'taskAction', position: { x: 80, y: 40 }, data: { id: '1', action: 'pick', robot: 'FR3_1', target: 'ConvItem0', speed: 'fast', status: 'idle' } },
      { id: '2', type: 'taskAction', position: { x: 80, y: 220 }, data: { id: '2', action: 'place', robot: 'FR3_1', x: -0.25, y: 0.25, speed: 'fast', status: 'idle' } },

      // Branch 2 (Right Conveyor Sector - Runs in parallel!)
      { id: '3', type: 'taskAction', position: { x: 440, y: 40 }, data: { id: '3', action: 'pick', robot: 'FR3_2', target: 'ConvItem3', speed: 'fast', status: 'idle' } },
      { id: '4', type: 'taskAction', position: { x: 440, y: 220 }, data: { id: '4', action: 'place', robot: 'FR3_2', x: 0.25, y: 0.25, speed: 'fast', status: 'idle' } },
    ],
    edges: [
      { id: 'e1-2', source: '1', target: '2', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
      { id: 'e3-4', source: '3', target: '4', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    ],
  },
  mode5_dual: {
    nodes: [
      { id: '1', type: 'taskAction', position: { x: 260, y: 40 }, data: { id: '1', action: 'dual_arm_pick', robot: 'FR3_1+FR3_2', target: 'LongBar', speed: 'fast', status: 'idle' } },
      { id: '2', type: 'taskAction', position: { x: 260, y: 210 }, data: { id: '2', action: 'dual_arm_circle', robot: 'FR3_1+FR3_2', plane: 'XY', radius: 0.08, cycles: 1, speed: 'fast', status: 'idle' } },
      { id: '3', type: 'taskAction', position: { x: 260, y: 380 }, data: { id: '3', action: 'dual_arm_place', robot: 'FR3_1+FR3_2', x: 0.0, y: 0.25, speed: 'fast', status: 'idle' } },
    ],
    edges: [
      { id: 'e1-2', source: '1', target: '2', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
      { id: 'e2-3', source: '2', target: '3', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    ],
  },
  serial_tower: {
    nodes: [
      { id: '1', type: 'taskAction', position: { x: 260, y: 30 }, data: { id: '1', action: 'pick', robot: 'FR3_1', target: 'Block1', speed: 'fast', status: 'idle' } },
      { id: '2', type: 'taskAction', position: { x: 260, y: 190 }, data: { id: '2', action: 'place', robot: 'FR3_1', x: 0.0, y: 0.0, speed: 'fast', status: 'idle' } },
      { id: '3', type: 'taskAction', position: { x: 260, y: 350 }, data: { id: '3', action: 'pick', robot: 'FR3_2', target: 'Block4', speed: 'fast', status: 'idle' } },
      { id: '4', type: 'taskAction', position: { x: 260, y: 510 }, data: { id: '4', action: 'place', robot: 'FR3_2', x: 0.0, y: 0.0, speed: 'fast', status: 'idle' } },
    ],
    edges: [
      { id: 'e1-2', source: '1', target: '2', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
      { id: 'e2-3', source: '2', target: '3', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
      { id: 'e3-4', source: '3', target: '4', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    ],
  },
};

interface VisualWorkflowBuilderProps {
  onPublishAction: (actionMsg: any) => Promise<{ success: boolean; message: string }>;
  mode: number;
  isDark?: boolean;
}

export default function VisualWorkflowBuilder({
  onPublishAction,
  mode,
  isDark = true,
}: VisualWorkflowBuilderProps) {
  const initialTemplate = mode === 5 ? TEMPLATES.mode5_dual : TEMPLATES.parallel_tower;
  const [nodes, setNodes, onNodesChange] = useNodesState(initialTemplate.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialTemplate.edges);
  const [isRunning, setIsRunning] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const isExecutingRef = useRef(false);

  // Connect handles
  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, animated: true, markerEnd: { type: MarkerType.ArrowClosed } }, eds)),
    [setEdges]
  );

  // Load Template
  const loadTemplate = (key: string) => {
    const t = TEMPLATES[key];
    if (t) {
      setNodes(t.nodes.map((n) => ({ ...n, data: { ...n.data, status: 'idle' } })));
      setEdges(t.edges);
      setIsRunning(false);
    }
  };

  // Add a task node manually (no forced serial edge, staggered horizontally for parallel branches)
  const addNode = (actionType: WorkflowStepData['action']) => {
    const id = `${Date.now()}`;
    const colIdx = nodes.length % 3;
    const rowIdx = Math.floor(nodes.length / 3);
    const xPos = 80 + colIdx * 270;
    const yPos = 50 + rowIdx * 170;

    const defaultRobot = actionType.startsWith('dual_arm')
      ? 'FR3_1+FR3_2'
      : (colIdx === 0 ? 'FR3_1' : (colIdx === 1 ? 'FR3_2' : 'FR3_3'));

    const newNode: Node = {
      id,
      type: 'taskAction',
      position: { x: xPos, y: yPos },
      data: {
        id,
        action: actionType,
        robot: defaultRobot,
        target: actionType.startsWith('dual_arm') ? 'LongBar' : (actionType === 'pick' ? `Block${(nodes.length % 9) + 1}` : undefined),
        x: actionType === 'place' ? 0.0 : undefined,
        y: actionType === 'place' ? 0.0 : (actionType === 'dual_arm_place' ? 0.25 : undefined),
        speed: 'fast',
        radius: actionType === 'dual_arm_circle' ? 0.08 : undefined,
        plane: actionType === 'dual_arm_circle' ? 'XY' : undefined,
        status: 'idle',
      },
    };

    setNodes((prev) => [...prev, newNode]);
  };

  // ─────────────────────────────────────────────────────────────
  // True Parallel DAG Wavefront Execution Engine
  // Concurrently executes independent branches; synchronizes at barriers
  // ─────────────────────────────────────────────────────────────
  const handleExecuteWorkflow = async () => {
    if (isRunning) return;
    if (nodes.length === 0) return;

    setIsRunning(true);
    isExecutingRef.current = true;

    // Reset all nodes to idle
    setNodes((prev) => prev.map((n) => ({ ...n, data: { ...n.data, status: 'idle' } })));

    // Track status of each node
    const statusMap = new Map<string, 'idle' | 'running' | 'success' | 'failed'>();
    nodes.forEach((n) => statusMap.set(n.id, 'idle'));

    // Map parent dependencies (incoming edges)
    const parentsMap = new Map<string, string[]>();
    nodes.forEach((n) => parentsMap.set(n.id, []));
    edges.forEach((e) => {
      parentsMap.get(e.target)?.push(e.source);
    });

    const activeNodePromises = new Map<string, Promise<void>>();

    const executeNode = async (node: Node): Promise<boolean> => {
      const data = node.data as unknown as WorkflowStepData;

      // Construct ROS 2 action payload
      const payload: Record<string, any> = { action: data.action };
      if (data.action === 'pick') {
        payload.robot = data.robot;
        payload.target = data.target;
        payload.speed = data.speed || 'fast';
      } else if (data.action === 'place') {
        payload.robot = data.robot;
        payload.x = data.x ?? 0.0;
        payload.y = data.y ?? 0.0;
        payload.speed = data.speed || 'fast';
      } else if (data.action === 'dual_arm_pick') {
        payload.target = data.target || 'LongBar';
        payload.speed = data.speed || 'fast';
        payload.offset_1 = -0.25;
        payload.offset_2 = 0.25;
      } else if (data.action === 'dual_arm_circle') {
        payload.radius = data.radius ?? 0.08;
        payload.cycles = data.cycles ?? 1;
        payload.plane = data.plane ?? 'XY';
        payload.speed = data.speed || 'fast';
      } else if (data.action === 'dual_arm_place') {
        payload.x = data.x ?? 0.0;
        payload.y = data.y ?? 0.25;
        payload.speed = data.speed || 'fast';
      } else if (data.action === 'go_home') {
        payload.robot = data.robot;
      }

      // Publish to ROS 2 and await genuine physical execution completion
      try {
        const res = await onPublishAction(payload);
        return Boolean(res.success);
      } catch (err) {
        console.error(`[WORKFLOW] Execution error on node ${node.id}:`, err);
        return false;
      }
    };

    while (isExecutingRef.current) {
      // Find all ready nodes whose dependencies have all completed with 'success'
      const readyNodes = nodes.filter((n) => {
        if (statusMap.get(n.id) !== 'idle') return false;
        const parents = parentsMap.get(n.id) || [];
        return parents.every((pId) => statusMap.get(pId) === 'success');
      });

      // Terminate if nothing is ready and nothing is running
      if (readyNodes.length === 0 && activeNodePromises.size === 0) {
        break;
      }

      // Launch all ready nodes concurrently in parallel!
      for (const node of readyNodes) {
        statusMap.set(node.id, 'running');
        setNodes((prev) =>
          prev.map((n) => (n.id === node.id ? { ...n, data: { ...n.data, status: 'running' } } : n))
        );

        const promise = executeNode(node)
          .then((isSuccess) => {
            activeNodePromises.delete(node.id);
            const finalStatus = isSuccess ? 'success' : 'failed';
            statusMap.set(node.id, finalStatus);
            setNodes((prev) =>
              prev.map((n) => (n.id === node.id ? { ...n, data: { ...n.data, status: finalStatus } } : n))
            );

            if (!isSuccess) {
              console.warn(`[WORKFLOW] Node ${node.id} failed execution. Halting workflow to prevent damage.`);
              isExecutingRef.current = false;
            }
          })
          .catch(() => {
            activeNodePromises.delete(node.id);
            statusMap.set(node.id, 'failed');
            setNodes((prev) =>
              prev.map((n) => (n.id === node.id ? { ...n, data: { ...n.data, status: 'failed' } } : n))
            );
            isExecutingRef.current = false;
          });

        activeNodePromises.set(node.id, promise);
      }

      // Wait for at least one active parallel branch to resolve
      if (activeNodePromises.size > 0) {
        await Promise.race(Array.from(activeNodePromises.values()));
      }
    }

    setIsRunning(false);
    isExecutingRef.current = false;
  };

  const handleStopWorkflow = () => {
    isExecutingRef.current = false;
    setIsRunning(false);
    setNodes((prev) =>
      prev.map((n) =>
        (n.data as unknown as WorkflowStepData).status === 'running'
          ? { ...n, data: { ...n.data, status: 'idle' } }
          : n
      )
    );
  };

  // Generate workflow from natural language via Backend Gemini 3.5 Flash-Lite
  const handleAiGenerate = async () => {
    if (!aiPrompt.trim()) return;
    setIsGenerating(true);

    try {
      const res = await fetch('http://localhost:3001/api/workflow/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: aiPrompt, mode }),
      });
      const respData = await res.json();
      if (respData.ok && respData.data && respData.data.nodes?.length > 0) {
        const genNodes: Node[] = respData.data.nodes.map((n: any) => ({
          id: String(n.id),
          type: 'taskAction',
          position: { x: n.x_pos || 250, y: n.y_pos || 100 },
          data: {
            id: String(n.id),
            action: n.action,
            robot: n.robot,
            target: n.target,
            x: n.x,
            y: n.y,
            speed: n.speed || 'fast',
            radius: n.radius,
            plane: n.plane,
            status: 'idle',
          },
        }));

        const genEdges: Edge[] = (respData.data.edges || []).map((e: any, idx: number) => ({
          id: `e${e.source}-${e.target}-${idx}`,
          source: String(e.source),
          target: String(e.target),
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed },
        }));

        setNodes(genNodes);
        setEdges(genEdges);
        setIsGenerating(false);
        setAiPrompt('');
        return;
      }
    } catch (e) {
      console.warn('Backend workflow generator unavailable, falling back to local template:', e);
    }

    // Local deterministic fallback
    const lower = aiPrompt.toLowerCase();
    if (lower.includes('circle') || lower.includes('wave') || lower.includes('longbar') || lower.includes('mode 5')) {
      loadTemplate('mode5_dual');
    } else if (lower.includes('conveyor') || lower.includes('stream') || lower.includes('item')) {
      loadTemplate('parallel_conveyor');
    } else if (lower.includes('serial') || lower.includes('single')) {
      loadTemplate('serial_tower');
    } else {
      loadTemplate('parallel_tower');
    }

    setIsGenerating(false);
    setAiPrompt('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', background: C.bg }}>
      {/* Top Action Toolbar */}
      <div
        style={{
          padding: '10px 14px',
          borderBottom: `1px solid ${C.border}`,
          background: C.glassBg,
          backdropFilter: 'blur(10px)',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
        }}
      >
        {/* Left: Execution & Palette Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <button
            onClick={isRunning ? handleStopWorkflow : handleExecuteWorkflow}
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              background: isRunning ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #10b981, #059669)',
              color: '#fff',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              boxShadow: isRunning ? '0 4px 12px rgba(239, 68, 68, 0.4)' : '0 4px 12px rgba(16, 185, 129, 0.4)',
            }}
          >
            {isRunning ? <Square size={13} fill="#fff" /> : <Play size={13} fill="#fff" />}
            {isRunning ? 'Abort Run' : '▶ Run Workflow (Zero-Token)'}
          </button>

          <div style={{ width: 1, height: 20, background: C.border }} />

          {/* Quick Palette */}
          <span style={{ fontSize: 11, color: C.textDim, fontWeight: 600 }}>Add Step:</span>
          <button
            onClick={() => addNode('pick')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(59, 130, 246, 0.15)', color: '#38bdf8', border: '1px solid rgba(59, 130, 246, 0.3)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
          >
            + Pick
          </button>
          <button
            onClick={() => addNode('place')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.3)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
          >
            + Place
          </button>
          <button
            onClick={() => addNode('dual_arm_pick')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa', border: '1px solid rgba(139, 92, 246, 0.3)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
          >
            + Dual Pick
          </button>
          <button
            onClick={() => addNode('dual_arm_circle')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(236, 72, 153, 0.15)', color: '#f472b6', border: '1px solid rgba(236, 72, 153, 0.3)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
          >
            + Circle Wave
          </button>
          <button
            onClick={() => addNode('dual_arm_place')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(6, 182, 212, 0.15)', color: '#22d3ee', border: '1px solid rgba(6, 182, 212, 0.3)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
          >
            + Dual Place
          </button>
          <button
            onClick={() => addNode('go_home')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(107, 114, 128, 0.15)', color: '#9ca3af', border: '1px solid rgba(107, 114, 128, 0.3)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
          >
            + Home
          </button>
        </div>

        {/* Right: Template Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: C.textDim, fontWeight: 600 }}>Templates:</span>
          <button
            onClick={() => loadTemplate('parallel_tower')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.25)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
            title="3 Arms Pick simultaneously in parallel, serialized center placement"
          >
            ⚡ 3-Arm Parallel
          </button>
          <button
            onClick={() => loadTemplate('parallel_conveyor')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(16, 185, 129, 0.1)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.25)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
            title="Left and Right arms pick conveyor items simultaneously in parallel"
          >
            ⚡ Parallel Conveyor
          </button>
          <button
            onClick={() => loadTemplate('mode5_dual')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(236, 72, 153, 0.1)', color: '#f472b6', border: '1px solid rgba(236, 72, 153, 0.25)', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
            title="Coordinated dual-arm LongBar pick, wave, and place"
          >
            🌊 Dual Wave
          </button>
          <button
            onClick={() => loadTemplate('serial_tower')}
            style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(255,255,255,0.04)', color: C.textDim, border: `1px solid ${C.border}`, fontSize: 11, cursor: 'pointer' }}
            title="Classic single-arm serialized tower"
          >
            📐 Serial Tower
          </button>
          <button
            onClick={() => { setNodes([]); setEdges([]); }}
            style={{ padding: '4px 6px', borderRadius: 6, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', fontSize: 11, cursor: 'pointer' }}
            title="Clear all nodes"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {/* Natural Language Prompt to Workflow Bar */}
      <div
        style={{
          padding: '8px 14px',
          background: C.subCardBg,
          borderBottom: `1px solid ${C.border}`,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <Sparkles size={14} color="#a78bfa" />
        <input
          type="text"
          value={aiPrompt}
          onChange={(e) => setAiPrompt(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAiGenerate()}
          placeholder="Describe workflow to generate blocks (e.g. 'Build 3-layer tower' or 'Mode 5 wave and place')..."
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            color: C.text,
            fontSize: 12,
            outline: 'none',
          }}
        />
        <button
          onClick={handleAiGenerate}
          disabled={isGenerating || !aiPrompt.trim()}
          style={{
            padding: '4px 10px',
            borderRadius: 6,
            background: 'linear-gradient(135deg, #8b5cf6, #7c3aed)',
            color: '#fff',
            border: 'none',
            cursor: aiPrompt.trim() ? 'pointer' : 'default',
            fontSize: 11,
            fontWeight: 600,
            opacity: aiPrompt.trim() ? 1 : 0.5,
          }}
        >
          {isGenerating ? 'Generating...' : 'Auto-Build Flow'}
        </button>
      </div>

      {/* Visual Canvas */}
      <div style={{ flex: 1, position: 'relative', width: '100%', height: '100%', background: C.canvasBg }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          defaultEdgeOptions={{ type: 'removable', animated: true }}
          connectionRadius={40}
          deleteKeyCode={['Backspace', 'Delete']}
          onEdgeClick={(_e, edge) => setEdges((eds) => eds.filter((ed) => ed.id !== edge.id))}
          fitView
          minZoom={0.2}
          maxZoom={2.0}
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} color={isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)'} />
          <Controls style={{ background: C.controlsBg, borderColor: C.controlsBorder, color: C.text }} />
          <MiniMap
            style={{ background: C.miniMapBg, borderRadius: 8, border: `1px solid ${C.miniMapBorder}` }}
            nodeColor="#3b82f6"
            maskColor={C.miniMapMask}
          />
        </ReactFlow>
      </div>
    </div>
  );
}
