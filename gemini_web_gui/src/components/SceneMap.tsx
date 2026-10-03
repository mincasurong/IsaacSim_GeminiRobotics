import { useEffect } from 'react';
import { ReactFlow, Background, Controls, useNodesState, type Node, BackgroundVariant } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { monoFont, type RobotAction, type MetricsData, parseAction } from './theme';

interface SceneMapProps {
  actions: RobotAction[];
  results: RobotAction[];
  metrics: MetricsData | null;
  fontSize: number;
}

// ─────────────────────────────────────────────────────────────
// Robotic Monitoring Node Styles
// ─────────────────────────────────────────────────────────────
const RobotNode = ({ data }: any) => {
  const isActive = data.phase && data.phase !== 'IDLE' && data.phase !== 'INIT';
  return (
    <div style={{
      width: 64, height: 64, borderRadius: '50%',
      background: '#09090b',
      border: `2px solid ${data.color}`,
      boxShadow: isActive ? `0 0 12px ${data.color}80, inset 0 0 10px ${data.color}40` : 'none',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      color: '#e4e4e7', fontFamily: monoFont, fontSize: 10, fontWeight: 'bold',
      position: 'relative'
    }}>
      {/* Outer spinning ring effect when active */}
      {isActive && (
        <div style={{
          position: 'absolute', top: -6, left: -6, right: -6, bottom: -6,
          border: `1px dashed ${data.color}`, borderRadius: '50%',
          animation: 'spin 4s linear infinite', opacity: 0.5
        }} />
      )}
      <div style={{ color: data.color }}>{data.label}</div>
      {data.phase && <div style={{ fontSize: 7, color: isActive ? '#fff' : '#71717a', marginTop: 4 }}>{data.phase}</div>}
      {data.target && <div style={{ fontSize: 7, color: '#a1a1aa', marginTop: 2, background: '#18181b', padding: '1px 4px', borderRadius: 2 }}>{data.target}</div>}
    </div>
  );
};

const WorkspaceNode = ({ data }: any) => {
  return (
    <div style={{
      width: data.width, height: data.height,
      background: 'rgba(15, 23, 42, 0.4)',
      border: `1px dashed #3f3f46`,
      borderRadius: 4,
      display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-start',
      padding: 6,
      color: '#71717a', fontFamily: monoFont, fontSize: 10, fontWeight: 'bold'
    }}>
      <div style={{ background: '#18181b', padding: '2px 6px', border: '1px solid #27272a', borderRadius: 2, fontSize: 8 }}>
        {data.label}
      </div>
    </div>
  );
};

const ObjectNode = ({ data }: any) => {
  return (
    <div style={{
      width: data.width || 30, height: data.height || 30,
      background: '#18181b',
      border: `1px solid ${data.color || '#52525b'}`,
      borderRadius: data.shape === 'circle' ? '50%' : 2,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#d4d4d8', fontSize: 8, fontWeight: 'bold', fontFamily: monoFont
    }}>
      {data.label}
    </div>
  );
};

const nodeTypes = {
  robot: RobotNode,
  workspace: WorkspaceNode,
  object: ObjectNode
};

export default function SceneMap({ actions, metrics }: SceneMapProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);

  // Dynamically compute graph topology while preserving dragged positions
  useEffect(() => {
    if (!metrics || !metrics.robots || Object.keys(metrics.robots).length === 0) {
      setNodes([{
        id: 'waiting', type: 'workspace', position: { x: 50, y: 120 },
        data: { label: 'AWAITING_TELEMETRY', width: 250, height: 60 },
        draggable: false, selectable: false
      }]);
      return;
    }

    const robotKeys = Object.keys(metrics.robots);
    const newNodes: Node[] = [];

    // --- TOPOLOGY GENERATION ---
    if (robotKeys.length === 2) {
      // Dual-Arm Topology
      newNodes.push({
        id: 'conveyor', type: 'workspace', position: { x: 100, y: 150 },
        data: { label: 'ZONE: CONVEYOR_BELT', width: 400, height: 100 },
        draggable: false, selectable: false
      });

      if (metrics.robots['FR3_1']) {
        newNodes.push({
          id: 'FR3_1', type: 'robot', position: { x: 260, y: 280 },
          data: { label: 'FR3_1', color: '#ef4444', phase: metrics.robots['FR3_1'].phase, target: metrics.robots['FR3_1'].target }
        });
      }
      if (metrics.robots['FR3_2']) {
        newNodes.push({
          id: 'FR3_2', type: 'robot', position: { x: 260, y: 50 },
          data: { label: 'FR3_2', color: '#10b981', phase: metrics.robots['FR3_2'].phase, target: metrics.robots['FR3_2'].target }
        });
      }

      const activeObjects = new Set<string>();
      actions.forEach(a => {
        const pa = parseAction(a.raw);
        if (pa.target) activeObjects.add(pa.target);
      });

      let ox = 120;
      Array.from(activeObjects).forEach((obj) => {
        const isChassis = obj.toLowerCase().includes('chassis') || obj.toLowerCase().includes('bar');
        newNodes.push({
          id: `obj_${obj}`, type: 'object', position: { x: ox, y: 185 },
          data: { label: obj.substring(0, 4), width: isChassis ? 80 : 30, height: isChassis ? 30 : 30, color: '#f97316', shape: isChassis ? 'rect' : 'circle' }
        });
        ox += isChassis ? 100 : 50;
      });

    } else {
      // Triple-Arm Topology
      newNodes.push({
        id: 'target_table', type: 'workspace', position: { x: 200, y: 200 },
        data: { label: 'ZONE: TARGET_CENTER', width: 100, height: 100 },
        draggable: false, selectable: false
      });
      newNodes.push({ id: 'table1', type: 'workspace', position: { x: 200, y: 350 }, data: { label: 'ZONE: T1', width: 100, height: 60 }, draggable: false, selectable: false });
      newNodes.push({ id: 'table2', type: 'workspace', position: { x: 350, y: 100 }, data: { label: 'ZONE: T2', width: 100, height: 60 }, draggable: false, selectable: false });
      newNodes.push({ id: 'table3', type: 'workspace', position: { x: 50, y: 100 }, data: { label: 'ZONE: T3', width: 100, height: 60 }, draggable: false, selectable: false });

      if (metrics.robots['FR3_1']) newNodes.push({ id: 'FR3_1', type: 'robot', position: { x: 220, y: 430 }, data: { label: 'FR3_1', color: '#ef4444', phase: metrics.robots['FR3_1'].phase, target: metrics.robots['FR3_1'].target } });
      if (metrics.robots['FR3_2']) newNodes.push({ id: 'FR3_2', type: 'robot', position: { x: 400, y: 30 }, data: { label: 'FR3_2', color: '#10b981', phase: metrics.robots['FR3_2'].phase, target: metrics.robots['FR3_2'].target } });
      if (metrics.robots['FR3_3']) newNodes.push({ id: 'FR3_3', type: 'robot', position: { x: 40, y: 30 }, data: { label: 'FR3_3', color: '#3b82f6', phase: metrics.robots['FR3_3'].phase, target: metrics.robots['FR3_3'].target } });
      
      const activeObjects = new Set<string>();
      actions.forEach(a => {
        const pa = parseAction(a.raw);
        if (pa.target) activeObjects.add(pa.target);
      });
      let ox = 210, oy = 210;
      Array.from(activeObjects).forEach((obj) => {
        newNodes.push({
          id: `obj_${obj}`, type: 'object', position: { x: ox, y: oy },
          data: { label: obj.substring(0, 4), width: 25, height: 25, color: '#38bdf8', shape: 'rect' }
        });
        ox += 30;
        if (ox > 280) { ox = 210; oy += 30; }
      });
    }

    // Smart merge to preserve positions!
    setNodes((currentNodes) => {
      const existing = new Map(currentNodes.map(n => [n.id, n]));
      return newNodes.map(nn => {
        if (existing.has(nn.id)) {
          // Keep the existing position, just update the data payload
          return { ...existing.get(nn.id)!, data: nn.data };
        }
        return nn;
      });
    });
  }, [metrics, actions, setNodes]);

  return (
    <div style={{ width: '100%', height: '100%', background: '#000', position: 'relative' }}>
      <style>
        {`
          @keyframes spin { 100% { transform: rotate(360deg); } }
        `}
      </style>
      
      {/* HUD Info Header - Replaces overlapping text */}
      <div style={{
        position: 'absolute', top: 12, left: 12, zIndex: 10,
        background: '#09090b', border: '1px solid #27272a', borderRadius: 4,
        padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 8,
        color: '#e4e4e7', fontFamily: monoFont, fontSize: 10
      }}>
        <div style={{ width: 6, height: 6, background: '#10b981', borderRadius: '50%' }} />
        <span>SYS.WORKSPACE_MAP_2D</span>
      </div>

      <ReactFlow
        nodes={nodes}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Lines} gap={30} size={1} color="#18181b" />
        <Background variant={BackgroundVariant.Dots} gap={30} size={2} color="#27272a" />
        <Controls 
          style={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 4, overflow: 'hidden' }} 
        />
      </ReactFlow>
    </div>
  );
}
