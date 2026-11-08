import { useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  MarkerType,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Layers,
  Lock,
  Unlock,
  Crosshair,
  Cpu,
} from 'lucide-react';
import {
  monoFont,
  type RobotAction,
  type MetricsData,
  type BlockData,
  BLOCK_COLORS,
  BLOCK_SHAPES,
  PHASE_COLORS,
} from './theme';

interface SceneMapProps {
  actions: RobotAction[];
  results: RobotAction[];
  metrics: MetricsData | null;
  fontSize: number;
}

// ─────────────────────────────────────────────────────────────
// Coordinate Transformation & Physical Workspace Configuration
// ─────────────────────────────────────────────────────────────
// Physical Workspace (meters in Isaac Sim):
// Center Target Table: [0.0, 0.0], 0.36m x 0.36m
// Source Table 1 (FR3_1): [0.0, -1.05], 0.50m x 0.50m
// Source Table 2 (FR3_2): [0.9093, 0.525], 0.50m x 0.50m
// Source Table 3 (FR3_3): [-0.9093, 0.525], 0.50m x 0.50m
// Robot 1: [0.0, -0.45], Base Yaw: 168.0°
// Robot 2: [0.3897, 0.225], Base Yaw: -64.0°
// Robot 3: [-0.3897, 0.225], Base Yaw: 42.0°

const CANVAS_CX = 380;
const CANVAS_CY = 340;
const METRIC_SCALE = 220; // 220 pixels per meter

function worldToCanvas(x: number, y: number, nodeWidth: number = 0, nodeHeight: number = 0) {
  return {
    x: Math.round(CANVAS_CX + x * METRIC_SCALE - nodeWidth / 2),
    y: Math.round(CANVAS_CY - y * METRIC_SCALE - nodeHeight / 2), // World +Y is Up; Canvas +Y is Down
  };
}

// Nominal block locations on source tables (Table 1: 1-3, Table 2: 4-6, Table 3: 7-9)
const NOMINAL_BLOCK_POSITIONS: Record<string, { x: number; y: number; z: number }> = {
  Block1: { x: -0.12, y: -1.05, z: 0.33 },
  Block2: { x: 0.00, y: -1.15, z: 0.33 },
  Block3: { x: 0.12, y: -1.05, z: 0.33 },
  Block4: { x: 0.8093, y: 0.425, z: 0.33 },
  Block5: { x: 1.0093, y: 0.475, z: 0.33 },
  Block6: { x: 0.9093, y: 0.625, z: 0.33 },
  Block7: { x: -1.0093, y: 0.475, z: 0.33 },
  Block8: { x: -0.8093, y: 0.425, z: 0.33 },
  Block9: { x: -0.9093, y: 0.625, z: 0.33 },
};

// ─────────────────────────────────────────────────────────────
// Custom Node Components
// ─────────────────────────────────────────────────────────────

// 1. Table Node (Industrial Workbench Surface)
const TableNode = ({ data }: any) => {
  const isCenter = data.isCenter;
  const isLocked = Boolean(data.lockedBy);
  const lockColor = data.lockColor || '#fbbf24';

  return (
    <div
      style={{
        width: data.width,
        height: data.height,
        background: isCenter
          ? isLocked
            ? 'linear-gradient(145deg, rgba(30, 27, 75, 0.75), rgba(15, 23, 42, 0.9))'
            : 'linear-gradient(145deg, rgba(24, 24, 27, 0.85), rgba(9, 9, 11, 0.95))'
          : 'linear-gradient(145deg, rgba(18, 18, 22, 0.75), rgba(9, 9, 12, 0.9))',
        border: isCenter
          ? `2px ${isLocked ? 'solid' : 'dashed'} ${isLocked ? lockColor : '#38bdf8'}`
          : '1px dashed rgba(255, 255, 255, 0.18)',
        borderRadius: isCenter ? 12 : 8,
        boxShadow: isCenter && isLocked
          ? `0 0 24px ${lockColor}40, inset 0 0 16px ${lockColor}20`
          : isCenter
          ? '0 0 16px rgba(56, 189, 248, 0.15)'
          : '0 4px 12px rgba(0,0,0,0.4)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 8px',
        color: '#f4f4f5',
        fontFamily: monoFont,
        position: 'relative',
        boxSizing: 'border-box',
        pointerEvents: 'none',
      }}
    >
      {/* Table Header Badge */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          width: '100%',
          justifyContent: 'space-between',
          fontSize: 9,
          fontWeight: 700,
          color: isCenter ? (isLocked ? lockColor : '#38bdf8') : '#a1a1aa',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          paddingBottom: 3,
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {isCenter ? <Crosshair size={10} color={isLocked ? lockColor : '#38bdf8'} /> : <Layers size={10} />}
          {data.label}
        </span>
        <span style={{ fontSize: 7.5, color: '#71717a' }}>{data.coords}</span>
      </div>

      {/* Center Target Indicator / Mutex Badge */}
      {isCenter && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, margin: 'auto' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '2px 8px',
              borderRadius: 999,
              background: isLocked ? `${lockColor}25` : 'rgba(16, 185, 129, 0.15)',
              border: `1px solid ${isLocked ? lockColor : '#10b981'}50`,
              color: isLocked ? lockColor : '#10b981',
              fontSize: 8.5,
              fontWeight: 800,
              letterSpacing: '0.04em',
            }}
          >
            {isLocked ? <Lock size={9} /> : <Unlock size={9} />}
            {isLocked ? `MUTEX: ${data.lockedBy}` : 'MUTEX: FREE'}
          </div>
          {data.towerHeight !== undefined && (
            <div style={{ fontSize: 8, color: '#94a3b8', fontWeight: 600, marginTop: 2 }}>
              TOWER: <span style={{ color: '#fbbf24', fontWeight: 800 }}>{data.towerHeight}</span> / 9
            </div>
          )}
        </div>
      )}

      {/* Target Crosshairs Markings */}
      {isCenter && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 32,
            height: 32,
            border: '1px dashed rgba(56, 189, 248, 0.25)',
            borderRadius: '50%',
            pointerEvents: 'none',
          }}
        />
      )}
    </div>
  );
};

// 2. Robot Node (Franka FR3 with Dynamic Orientation Heading Needle)
const RobotNode = ({ data }: any) => {
  const isActive = data.phase && data.phase !== 'IDLE' && data.phase !== 'INIT';
  const color = data.color || '#3b82f6';
  const phase = data.phase || 'IDLE';
  const phaseColor = (PHASE_COLORS as any)[phase] || '#71717a';

  // Physical Angle: Base yaw + active joint 1 rotation
  const baseYaw = data.baseYaw || 0;
  const j1 = data.j1 || 0;
  const currentHeading = baseYaw + j1;

  return (
    <div
      style={{
        width: 82,
        height: 82,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #18181b 0%, #09090b 100%)',
        border: `2px solid ${isActive ? color : '#3f3f46'}`,
        boxShadow: isActive
          ? `0 0 20px ${color}50, inset 0 0 14px ${color}30`
          : '0 8px 18px rgba(0,0,0,0.6)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#f4f4f5',
        fontFamily: monoFont,
        position: 'relative',
        boxSizing: 'border-box',
      }}
    >
      {/* Outer Rotating Radar Ring when Active */}
      {isActive && (
        <div
          style={{
            position: 'absolute',
            top: -6,
            left: -6,
            right: -6,
            bottom: -6,
            border: `1.5px dashed ${color}`,
            borderRadius: '50%',
            animation: 'sceneSpin 6s linear infinite',
            opacity: 0.65,
          }}
        />
      )}

      {/* Directional Heading Needle (Link 1 Z Orientation) */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          transform: `rotate(${-(currentHeading - 90)}deg)`, // Canvas Y is inverted
          transition: 'transform 0.25s ease-out',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 2,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '4px solid transparent',
            borderRight: '4px solid transparent',
            borderBottom: `9px solid ${color}`,
            filter: `drop-shadow(0 0 4px ${color})`,
          }}
        />
      </div>

      {/* Robot Label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 3, color, fontWeight: 800, fontSize: 10 }}>
        <Cpu size={11} color={color} />
        {data.label}
      </div>

      {/* Phase Badge */}
      <div
        style={{
          fontSize: 7.5,
          fontWeight: 700,
          color: '#09090b',
          background: phaseColor,
          padding: '1px 5px',
          borderRadius: 4,
          marginTop: 3,
          boxShadow: `0 0 8px ${phaseColor}60`,
        }}
      >
        {phase}
      </div>

      {/* Target Object Pill */}
      {data.target ? (
        <div
          style={{
            fontSize: 7,
            color: '#e4e4e7',
            background: 'rgba(255,255,255,0.08)',
            border: '1px solid rgba(255,255,255,0.12)',
            padding: '1px 4px',
            borderRadius: 3,
            marginTop: 2,
            maxWidth: 68,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {data.target}
        </div>
      ) : (
        <div style={{ fontSize: 6.5, color: '#52525b', marginTop: 2 }}>
          {baseYaw.toFixed(0)}°
        </div>
      )}

      {/* Busy % Ring Indicator */}
      {data.busyPct !== undefined && (
        <div
          style={{
            position: 'absolute',
            bottom: -14,
            fontSize: 7.5,
            color: '#a1a1aa',
            background: '#18181b',
            border: '1px solid #27272a',
            padding: '1px 5px',
            borderRadius: 4,
            whiteSpace: 'nowrap',
          }}
        >
          {data.busyPct}%
        </div>
      )}
    </div>
  );
};

// 3. Block Node (PhysX Manipulable Target with 3D Aesthetics)
const BlockNode = ({ data }: any) => {
  const blockName = data.id || 'Block';
  const color = (BLOCK_COLORS as any)[blockName] || '#38bdf8';
  const shape = (BLOCK_SHAPES as any)[blockName] || 'cube';
  const isHeld = data.status === 'HELD';
  const isStacked = data.status === 'STACKED';

  return (
    <div
      style={{
        width: 32,
        height: 32,
        borderRadius: shape === 'cylinder' ? '50%' : 6,
        background: isHeld
          ? `radial-gradient(circle at 35% 35%, #ffffff, ${color} 70%)`
          : `linear-gradient(145deg, ${color}dd 0%, ${color} 100%)`,
        border: `2px solid ${isHeld ? '#ffffff' : isStacked ? '#fbbf24' : 'rgba(255,255,255,0.4)'}`,
        boxShadow: isHeld
          ? `0 0 16px #ffffff, 0 0 24px ${color}`
          : isStacked
          ? '0 0 12px rgba(251, 191, 36, 0.6), 0 4px 8px rgba(0,0,0,0.5)'
          : `0 4px 10px rgba(0,0,0,0.5), inset 0 1px 2px rgba(255,255,255,0.5)`,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#ffffff',
        fontFamily: monoFont,
        fontSize: 8.5,
        fontWeight: 900,
        position: 'relative',
        textShadow: '0 1px 3px rgba(0,0,0,0.8)',
        transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        transform: isHeld ? 'scale(1.2)' : 'scale(1)',
      }}
    >
      {/* Top Facet Highlight for 3D Cube/Cylinder feel */}
      <div
        style={{
          position: 'absolute',
          top: 2,
          left: 4,
          right: 4,
          height: shape === 'cylinder' ? 8 : 6,
          borderRadius: shape === 'cylinder' ? '50%' : 2,
          background: 'rgba(255,255,255,0.3)',
          pointerEvents: 'none',
        }}
      />

      {/* Short ID */}
      <span>{data.shortId}</span>

      {/* Stacked Layer / Held Status Tag */}
      {isStacked && (
        <div
          style={{
            position: 'absolute',
            bottom: -11,
            background: '#fbbf24',
            color: '#09090b',
            fontSize: 6.5,
            fontWeight: 900,
            padding: '0 3px',
            borderRadius: 2,
            boxShadow: '0 0 6px rgba(251, 191, 36, 0.8)',
          }}
        >
          {data.layer ? `L${data.layer}` : 'STACK'}
        </div>
      )}

      {isHeld && (
        <div
          style={{
            position: 'absolute',
            bottom: -11,
            background: '#ef4444',
            color: '#ffffff',
            fontSize: 6,
            fontWeight: 800,
            padding: '0 3px',
            borderRadius: 2,
            boxShadow: '0 0 6px rgba(239, 68, 68, 0.8)',
            whiteSpace: 'nowrap',
          }}
        >
          HELD
        </div>
      )}
    </div>
  );
};

const nodeTypes = {
  table: TableNode,
  robot: RobotNode,
  block: BlockNode,
};

// ─────────────────────────────────────────────────────────────
// Main SceneMap Component
// ─────────────────────────────────────────────────────────────
export default function SceneMap({ actions, metrics }: SceneMapProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Compute live scene graph from physical topology and TF metrics
  useEffect(() => {
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    const isDualArm = metrics?.robots && Object.keys(metrics.robots).length === 2 && !metrics.robots['FR3_3'];

    if (isDualArm) {
      // ═════════════════════════════════════════════════════════════
      // DUAL-ARM CONVEYOR TOPOLOGY
      // ═════════════════════════════════════════════════════════════
      const convPos = worldToCanvas(0.0, 0.6, 520, 110);
      newNodes.push({
        id: 'conveyor_belt',
        type: 'table',
        position: convPos,
        data: {
          label: 'CONVEYOR BELT LINE',
          coords: 'Y = +0.60m | V = 0.15m/s →',
          width: 520,
          height: 110,
          isCenter: false,
        },
        draggable: false,
        selectable: false,
      });

      const mainPos = worldToCanvas(0.0, -0.2, 500, 140);
      newNodes.push({
        id: 'main_table',
        type: 'table',
        position: mainPos,
        data: {
          label: 'MAIN WORKBENCH',
          coords: 'Y = -0.20m',
          width: 500,
          height: 140,
          isCenter: false,
        },
        draggable: false,
        selectable: false,
      });

      const r1Pos = worldToCanvas(-0.7, -0.2, 82, 82);
      const r1Data = metrics?.robots?.['FR3_1'];
      newNodes.push({
        id: 'FR3_1',
        type: 'robot',
        position: r1Pos,
        data: {
          label: 'FR3_1',
          color: '#ef4444',
          phase: r1Data?.phase || 'IDLE',
          target: r1Data?.target || '',
          baseYaw: 0,
          j1: r1Data?.j1_deg || 0,
          busyPct: r1Data?.busy_pct,
        },
      });

      const r2Pos = worldToCanvas(0.7, -0.2, 82, 82);
      const r2Data = metrics?.robots?.['FR3_2'];
      newNodes.push({
        id: 'FR3_2',
        type: 'robot',
        position: r2Pos,
        data: {
          label: 'FR3_2',
          color: '#10b981',
          phase: r2Data?.phase || 'IDLE',
          target: r2Data?.target || '',
          baseYaw: 0,
          j1: r2Data?.j1_deg || 0,
          busyPct: r2Data?.busy_pct,
        },
      });
    } else {
      // ═════════════════════════════════════════════════════════════
      // TRIPLE-ARM WORKSTATION TOPOLOGY (3x FR3 + Central Tower)
      // ═════════════════════════════════════════════════════════════
      const lockedBy = metrics?.center_occupied_by || null;
      const lockColor = lockedBy === 'FR3_1' ? '#ef4444' : lockedBy === 'FR3_2' ? '#10b981' : '#3b82f6';

      // 1. Central Target Table [0.0, 0.0]
      const targetPos = worldToCanvas(0.0, 0.0, 140, 140);
      newNodes.push({
        id: 'target_table',
        type: 'table',
        position: targetPos,
        data: {
          label: 'TARGET TABLE',
          coords: '[0.0, 0.0]',
          width: 140,
          height: 140,
          isCenter: true,
          lockedBy,
          lockColor,
          towerHeight: metrics?.tower_height ?? 0,
        },
        draggable: false,
        selectable: false,
      });

      // 2. Source Table 1 (FR3_1) [0.0, -1.05]
      const t1Pos = worldToCanvas(0.0, -1.05, 145, 95);
      newNodes.push({
        id: 'table1',
        type: 'table',
        position: t1Pos,
        data: {
          label: 'SOURCE TABLE 1',
          coords: '[0.0, -1.05]',
          width: 145,
          height: 95,
          isCenter: false,
        },
        draggable: false,
        selectable: false,
      });

      // 3. Source Table 2 (FR3_2) [0.9093, 0.525]
      const t2Pos = worldToCanvas(0.9093, 0.525, 135, 115);
      newNodes.push({
        id: 'table2',
        type: 'table',
        position: t2Pos,
        data: {
          label: 'SOURCE TABLE 2',
          coords: '[+0.91, +0.53]',
          width: 135,
          height: 115,
          isCenter: false,
        },
        draggable: false,
        selectable: false,
      });

      // 4. Source Table 3 (FR3_3) [-0.9093, 0.525]
      const t3Pos = worldToCanvas(-0.9093, 0.525, 135, 115);
      newNodes.push({
        id: 'table3',
        type: 'table',
        position: t3Pos,
        data: {
          label: 'SOURCE TABLE 3',
          coords: '[-0.91, +0.53]',
          width: 135,
          height: 115,
          isCenter: false,
        },
        draggable: false,
        selectable: false,
      });

      // 5. Robot 1 (FR3_1) at [0.0, -0.45], Base Yaw = 168.0°
      const r1Pos = worldToCanvas(0.0, -0.45, 82, 82);
      const r1Data = metrics?.robots?.['FR3_1'];
      newNodes.push({
        id: 'FR3_1',
        type: 'robot',
        position: r1Pos,
        data: {
          label: 'FR3_1',
          color: '#ef4444',
          phase: r1Data?.phase || 'IDLE',
          target: r1Data?.target || '',
          baseYaw: 168.0,
          j1: r1Data?.j1_deg || 0,
          busyPct: r1Data?.busy_pct,
        },
      });

      // 6. Robot 2 (FR3_2) at [0.3897, 0.225], Base Yaw = -64.0°
      const r2Pos = worldToCanvas(0.3897, 0.225, 82, 82);
      const r2Data = metrics?.robots?.['FR3_2'];
      newNodes.push({
        id: 'FR3_2',
        type: 'robot',
        position: r2Pos,
        data: {
          label: 'FR3_2',
          color: '#10b981',
          phase: r2Data?.phase || 'IDLE',
          target: r2Data?.target || '',
          baseYaw: -64.0,
          j1: r2Data?.j1_deg || 0,
          busyPct: r2Data?.busy_pct,
        },
      });

      // 7. Robot 3 (FR3_3) at [-0.3897, 0.225], Base Yaw = 42.0°
      const r3Pos = worldToCanvas(-0.3897, 0.225, 82, 82);
      const r3Data = metrics?.robots?.['FR3_3'];
      newNodes.push({
        id: 'FR3_3',
        type: 'robot',
        position: r3Pos,
        data: {
          label: 'FR3_3',
          color: '#3b82f6',
          phase: r3Data?.phase || 'IDLE',
          target: r3Data?.target || '',
          baseYaw: 42.0,
          j1: r3Data?.j1_deg || 0,
          busyPct: r3Data?.busy_pct,
        },
      });

      // 8. Blocks (Block1 through Block9)
      const tfBlocks = metrics?.blocks || {};
      let stackedCount = 0;

      for (let i = 1; i <= 9; i++) {
        const bName = `Block${i}`;
        const tfData = tfBlocks[bName];
        let bx: number, by: number, bz: number, status: string, holder: string | null = null;

        if (tfData) {
          bx = tfData.x;
          by = tfData.y;
          bz = tfData.z;
          status = tfData.status;
          holder = tfData.holder || null;
        } else {
          // Fallback to nominal table layout
          const nom = NOMINAL_BLOCK_POSITIONS[bName];
          bx = nom.x;
          by = nom.y;
          bz = nom.z;
          status = i <= 3 ? 'TABLE_1' : i <= 6 ? 'TABLE_2' : 'TABLE_3';
        }

        // Layer indexing for stacked blocks
        let layerNum: number | undefined;
        let cPos = worldToCanvas(bx, by, 32, 32);

        if (status === 'STACKED') {
          stackedCount++;
          layerNum = stackedCount;
          // Stagger slightly on center table so individual stacked blocks remain visually distinguishable
          const angle = (stackedCount - 1) * (Math.PI / 4);
          const r = Math.min((stackedCount - 1) * 3, 24);
          cPos = {
            x: Math.round(CANVAS_CX + Math.cos(angle) * r - 16),
            y: Math.round(CANVAS_CY + Math.sin(angle) * r - 16),
          };
        } else if (status === 'HELD' && holder) {
          // If held, anchor block near the corresponding robot
          const rNode = newNodes.find((n) => n.id === holder);
          if (rNode) {
            cPos = {
              x: rNode.position.x + 25,
              y: rNode.position.y + 25,
            };
          }
        }

        newNodes.push({
          id: `b_${bName}`,
          type: 'block',
          position: cPos,
          data: {
            id: bName,
            shortId: `B${i}`,
            status,
            holder,
            layer: layerNum,
            x: bx,
            y: by,
            z: bz,
          },
        });
      }

      // 9. Active Task Edges (Laser Beams connecting Robots to Targets / Center)
      const robots = [
        { id: 'FR3_1', data: r1Data, color: '#ef4444' },
        { id: 'FR3_2', data: r2Data, color: '#10b981' },
        { id: 'FR3_3', data: r3Data, color: '#3b82f6' },
      ];

      robots.forEach(({ id, data, color }) => {
        if (!data || !data.target) return;
        const targetBlockId = `b_${data.target}`;

        if (data.phase === 'PICKING') {
          newEdges.push({
            id: `edge_${id}_${targetBlockId}`,
            source: id,
            target: targetBlockId,
            animated: true,
            style: { stroke: color, strokeWidth: 2, strokeDasharray: '4 4' },
            markerEnd: { type: MarkerType.ArrowClosed, color },
          });
        } else if (data.phase === 'PLACING') {
          newEdges.push({
            id: `edge_${id}_target`,
            source: id,
            target: 'target_table',
            animated: true,
            style: { stroke: color, strokeWidth: 2.5 },
            markerEnd: { type: MarkerType.ArrowClosed, color },
          });
        } else if (data.phase === 'QUEUED') {
          newEdges.push({
            id: `edge_${id}_queued`,
            source: id,
            target: 'target_table',
            animated: false,
            style: { stroke: '#fbbf24', strokeWidth: 1.5, strokeDasharray: '2 6' },
          });
        }
      });
    }

    setNodes(newNodes);
    setEdges(newEdges);
  }, [metrics, actions, setNodes, setEdges]);

  // Overall Statistics for HUD
  const hudStats = useMemo(() => {
    const blocks = metrics?.blocks || {};
    let stacked = 0;
    let held = 0;
    let onTable = 0;

    Object.values(blocks).forEach((b: BlockData) => {
      if (b.status === 'STACKED') stacked++;
      else if (b.status === 'HELD') held++;
      else onTable++;
    });

    return {
      tower: metrics?.tower_height ?? stacked,
      held,
      onTable: 9 - stacked - held,
      locked: metrics?.center_occupied_by || 'FREE',
    };
  }, [metrics]);

  return (
    <div style={{ width: '100%', height: '100%', background: '#09090b', position: 'relative', overflow: 'hidden' }}>
      <style>
        {`
          @keyframes sceneSpin { 100% { transform: rotate(360deg); } }
        `}
      </style>

      {/* Futuristic Glassmorphic HUD Bar */}
      <div
        style={{
          position: 'absolute',
          top: 14,
          left: 14,
          right: 14,
          zIndex: 10,
          background: 'rgba(18, 18, 22, 0.85)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: 10,
          padding: '8px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: '#f4f4f5',
          fontFamily: monoFont,
          fontSize: 10,
          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 8, height: 8, background: '#10b981', borderRadius: '50%', boxShadow: '0 0 10px #10b981' }} />
          <span style={{ fontWeight: 800, letterSpacing: '0.04em', color: '#ffffff' }}>
            2D WORKSPACE TWIN
          </span>
          <span style={{ color: '#52525b' }}>|</span>
          <span style={{ color: '#94a3b8' }}>3x FR3 CELL</span>
        </div>

        {/* Live Counters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ color: '#71717a' }}>TOWER:</span>
            <span style={{ color: '#fbbf24', fontWeight: 800 }}>{hudStats.tower} / 9</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ color: '#71717a' }}>MUTEX:</span>
            <span
              style={{
                color: hudStats.locked === 'FREE' ? '#10b981' : '#f97316',
                fontWeight: 800,
              }}
            >
              {hudStats.locked}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ color: '#71717a' }}>BLOCKS:</span>
            <span style={{ color: '#38bdf8' }}>{hudStats.onTable} Table</span>
            <span style={{ color: '#52525b' }}>•</span>
            <span style={{ color: '#a855f7' }}>{hudStats.held} Held</span>
            <span style={{ color: '#52525b' }}>•</span>
            <span style={{ color: '#fbbf24' }}>{hudStats.tower} Stacked</span>
          </div>
        </div>
      </div>

      {/* Interactive 2D ReactFlow Viewport */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Lines} gap={24} size={1} color="#18181b" />
        <Background variant={BackgroundVariant.Dots} gap={24} size={2} color="#27272a" />
        <Controls
          style={{
            background: 'rgba(18, 18, 22, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 8,
            overflow: 'hidden',
          }}
        />
        <MiniMap
          nodeStrokeColor="#3f3f46"
          nodeColor={(n) => {
            if (n.type === 'robot') return (n.data as any)?.color || '#3b82f6';
            if (n.type === 'block') return (BLOCK_COLORS as any)[(n.data as any)?.id] || '#fbbf24';
            return '#18181b';
          }}
          style={{
            background: 'rgba(9, 9, 11, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 8,
          }}
        />
      </ReactFlow>
    </div>
  );
}
