import { useMemo, useEffect } from 'react';
import { ReactFlow, Background, Controls, Node, Position, useNodesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { C, monoFont, type RobotAction, type MetricsData, parseAction, parseResult } from './theme';

interface SceneMapProps {
  actions: RobotAction[];
  results: RobotAction[];
  metrics: MetricsData | null;
  fontSize: number;
}

// Custom Node for Robots
const RobotNode = ({ data }: any) => {
  const isActive = data.phase && data.phase !== 'IDLE' && data.phase !== 'INIT';
  return (
    <div style={{
      width: 60, height: 60, borderRadius: '50%',
      background: `${data.color}20`,
      border: `3px solid ${data.color}`,
      boxShadow: isActive ? `0 0 15px ${data.color}80` : 'none',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      color: '#fff', fontFamily: monoFont, fontSize: 10, fontWeight: 'bold'
    }}>
      <div>{data.label}</div>
      {data.phase && <div style={{ fontSize: 8, color: isActive ? data.color : C.textMuted, marginTop: 4 }}>{data.phase}</div>}
      {data.target && <div style={{ fontSize: 7, color: '#fff' }}>[{data.target}]</div>}
    </div>
  );
};

// Custom Node for Tables/Conveyors
const WorkspaceNode = ({ data }: any) => {
  return (
    <div style={{
      width: data.width, height: data.height,
      background: 'rgba(255,255,255,0.03)',
      border: `2px dashed ${C.border}`,
      borderRadius: 8,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: C.textDim, fontFamily: monoFont, fontSize: 12, fontWeight: 'bold'
    }}>
      {data.label}
    </div>
  );
};

// Custom Node for Objects (Blocks, Chassis, etc.)
const ObjectNode = ({ data }: any) => {
  return (
    <div style={{
      width: data.width || 30, height: data.height || 30,
      background: data.color || C.textMuted,
      border: '1px solid rgba(255,255,255,0.3)',
      borderRadius: data.shape === 'circle' ? '50%' : 4,
      boxShadow: '0 4px 6px rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#000', fontSize: 8, fontWeight: 'bold'
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

export default function SceneMap({ actions, results, metrics, fontSize }: SceneMapProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);

  // Dynamically compute graph topology based on Isaac Sim capabilities (number of robots)
  useEffect(() => {
    if (!metrics || !metrics.robots) return;

    const robotKeys = Object.keys(metrics.robots);
    const newNodes: Node[] = [];

    // --- DESIGNTIFIC LAYOUT GENERATION ---
    if (robotKeys.length === 2) {
      // MODE 5 / 7 / 8: Dual-Arm Conveyor / Assembly
      // 1. Structural Environment
      newNodes.push({
        id: 'conveyor', type: 'workspace', position: { x: 100, y: 150 },
        data: { label: 'Conveyor Belt / Assembly Line', width: 400, height: 100 },
        draggable: false, selectable: false
      });

      // 2. Robots
      if (metrics.robots['FR3_1']) {
        newNodes.push({
          id: 'FR3_1', type: 'robot', position: { x: 260, y: 280 },
          data: { label: 'R1', color: C.blue, phase: metrics.robots['FR3_1'].phase, target: metrics.robots['FR3_1'].target }
        });
      }
      if (metrics.robots['FR3_2']) {
        newNodes.push({
          id: 'FR3_2', type: 'robot', position: { x: 260, y: 50 },
          data: { label: 'R2', color: C.yellow, phase: metrics.robots['FR3_2'].phase, target: metrics.robots['FR3_2'].target }
        });
      }

      // 3. Extracted Dynamic Objects (Looking at recent actions for targets)
      const activeObjects = new Set<string>();
      actions.forEach(a => {
        const pa = parseAction(a.raw);
        if (pa.target) activeObjects.add(pa.target);
      });

      let ox = 120;
      Array.from(activeObjects).forEach((obj, idx) => {
        const isChassis = obj.toLowerCase().includes('chassis') || obj.toLowerCase().includes('bar');
        newNodes.push({
          id: `obj_${obj}`, type: 'object', position: { x: ox, y: 175 },
          data: { label: obj.substring(0, 4), width: isChassis ? 80 : 30, height: isChassis ? 30 : 30, color: C.orange, shape: isChassis ? 'rect' : 'circle' }
        });
        ox += isChassis ? 100 : 50;
      });

    } else {
      // MODE 1 / 2: 3-Arm Tower Stacking
      newNodes.push({
        id: 'target_table', type: 'workspace', position: { x: 200, y: 200 },
        data: { label: 'Target Center', width: 100, height: 100 },
        draggable: false, selectable: false
      });
      newNodes.push({ id: 'table1', type: 'workspace', position: { x: 200, y: 350 }, data: { label: 'T1', width: 100, height: 60 }, draggable: false, selectable: false });
      newNodes.push({ id: 'table2', type: 'workspace', position: { x: 350, y: 100 }, data: { label: 'T2', width: 100, height: 60 }, draggable: false, selectable: false });
      newNodes.push({ id: 'table3', type: 'workspace', position: { x: 50, y: 100 }, data: { label: 'T3', width: 100, height: 60 }, draggable: false, selectable: false });

      if (metrics.robots['FR3_1']) newNodes.push({ id: 'FR3_1', type: 'robot', position: { x: 220, y: 430 }, data: { label: 'R1', color: C.blue, phase: metrics.robots['FR3_1'].phase, target: metrics.robots['FR3_1'].target } });
      if (metrics.robots['FR3_2']) newNodes.push({ id: 'FR3_2', type: 'robot', position: { x: 400, y: 30 }, data: { label: 'R2', color: C.yellow, phase: metrics.robots['FR3_2'].phase, target: metrics.robots['FR3_2'].target } });
      if (metrics.robots['FR3_3']) newNodes.push({ id: 'FR3_3', type: 'robot', position: { x: 40, y: 30 }, data: { label: 'R3', color: C.green, phase: metrics.robots['FR3_3'].phase, target: metrics.robots['FR3_3'].target } });
      
      // Dynamic objects
      const activeObjects = new Set<string>();
      actions.forEach(a => {
        const pa = parseAction(a.raw);
        if (pa.target) activeObjects.add(pa.target);
      });
      let ox = 210, oy = 210;
      Array.from(activeObjects).forEach((obj, idx) => {
        newNodes.push({
          id: `obj_${obj}`, type: 'object', position: { x: ox, y: oy },
          data: { label: obj.substring(0, 4), width: 25, height: 25, color: C.blue, shape: 'rect' }
        });
        ox += 30;
        if (ox > 280) { ox = 210; oy += 30; }
      });
    }

    setNodes(newNodes);
  }, [metrics, actions, setNodes]);

  return (
    <div style={{ width: '100%', height: '100%', background: C.bgLight }}>
      <ReactFlow
        nodes={nodes}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color={C.border} gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
      <div style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(0,0,0,0.5)', padding: '4px 8px', borderRadius: 4, color: C.textDim, fontSize: 10, fontFamily: monoFont }}>
        Designtific XYFlow Map (Auto-Adapting)
      </div>
    </div>
  );
}
