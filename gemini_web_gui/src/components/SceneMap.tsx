import { useMemo, useState } from 'react';
import {
  C,
  BLOCK_COLORS,
  BLOCK_LABELS,
  BLOCK_SHAPES,
  KITCHEN_OBJECTS,
  resolveObjectKey,
  monoFont,
  type RobotAction,
  type MetricsData,
  parseAction,
  parseResult,
} from './theme';

interface SceneMapProps {
  actions: RobotAction[];
  results: RobotAction[];
  metrics: MetricsData | null;
  fontSize: number;
  tfTransforms?: Record<string, { x: number; y: number; z?: number; rotation?: any }>;
  detectedObjects?: any;
}

// Physical layout constants (normalized to 300x280 SVG viewport)
const SVG_W = 300;
const SVG_H = 280;
const TABLE_W = 60;
const TABLE_H = 40;

// Clamps coordinates safely to within the SVG viewport bounds [0, SVG_W] and [0, SVG_H]
function clampCoord(x: number, y: number): { x: number; y: number } {
  return {
    x: Math.max(0, Math.min(x, SVG_W)),
    y: Math.max(0, Math.min(y, SVG_H)),
  };
}

// Helper to map Isaac Sim / ROS 2 world coordinates (meters) to 300x280 SVG canvas coordinates
// Center is at (150, 140), 1.0 meter = 100 pixels, Y is inverted (positive world Y is up in world, -y in SVG)
function worldToSvg(x: number, y: number): { x: number; y: number } {
  return clampCoord(150 + x * 100, 140 - y * 100);
}

// Stations & Tables (real world coords: Center=[0, 0], Table1=[0, -1.05], Table2=[0.91, 0.525], Table3=[-0.91, 0.525])
const TABLE1 = { x: 150 - TABLE_W / 2, y: 245 - TABLE_H / 2, label: 'Table 1 (Dishes)' };   // Bottom (FR3_1)
const TABLE2 = { x: 241 - TABLE_W / 2, y: 87.5 - TABLE_H / 2, label: 'Table 2 (Cups)' };    // Top Right (FR3_2)
const TABLE3 = { x: 59 - TABLE_W / 2, y: 87.5 - TABLE_H / 2, label: 'Table 3 (Prep)' };     // Top Left (FR3_3)
const TARGET = { x: 150 - TABLE_W / 2, y: 140 - TABLE_H / 2, label: 'Dining Table' };       // Center
const BAR_STAND = { x: 170, y: 151, label: 'Bar Stand' };                                    // LongBar Rest Stand (0.20m, -0.11m)

// Robot base positions (scaled from meters to pixels: center 150,140, 1m=100px)
const ROBOT_BASES: Record<string, { x: number; y: number; color: string }> = {
  FR3_1: { x: 150, y: 185, color: C.blue },
  FR3_2: { x: 189, y: 117.5, color: C.yellow },
  FR3_3: { x: 111, y: 117.5, color: C.green },
};

// Initial block assignments: Robot1 → Block1-3, Robot2 → Block4-6, Robot3 → Block7-9
const INITIAL_BLOCK_TABLE: Record<string, { x: number; y: number }> = {
  Block1: { x: TABLE1.x + 10, y: TABLE1.y + 10 },
  Block2: { x: TABLE1.x + 30, y: TABLE1.y + 10 },
  Block3: { x: TABLE1.x + 50, y: TABLE1.y + 10 },
  Block4: { x: TABLE2.x + 10, y: TABLE2.y + 10 },
  Block5: { x: TABLE2.x + 30, y: TABLE2.y + 10 },
  Block6: { x: TABLE2.x + 50, y: TABLE2.y + 10 },
  Block7: { x: TABLE3.x + 10, y: TABLE3.y + 10 },
  Block8: { x: TABLE3.x + 30, y: TABLE3.y + 10 },
  Block9: { x: TABLE3.x + 50, y: TABLE3.y + 10 },
};

// Initial Kitchenware positions on respective stations
const INITIAL_KITCHEN_TABLE: Record<string, { x: number; y: number; rot?: number }> = {
  Dish1: { x: TABLE1.x + 12, y: TABLE1.y + 24 },
  Dish2: { x: TABLE1.x + 30, y: TABLE1.y + 24 },
  Dish3: { x: TABLE1.x + 48, y: TABLE1.y + 24 },
  Cup1:  { x: TABLE2.x + 12, y: TABLE2.y + 24 },
  Cup2:  { x: TABLE2.x + 30, y: TABLE2.y + 24 },
  Cup3:  { x: TABLE2.x + 48, y: TABLE2.y + 24 },
  LongBar1: { x: BAR_STAND.x, y: BAR_STAND.y, rot: 60 },
};

type ObjectState = 'on_table' | 'in_gripper' | 'in_dual_gripper' | 'placed' | 'on_tower';

export default function SceneMap({
  actions,
  results,
  metrics,
  fontSize,
  tfTransforms,
  detectedObjects,
}: SceneMapProps) {
  const hasKitchenScene = Boolean(
    (tfTransforms && Object.keys(tfTransforms).some(k => k.startsWith('Dish') || k.startsWith('Cup') || k.startsWith('LongBar') || k.startsWith('dish') || k.startsWith('cup') || k.startsWith('bar'))) ||
    metrics?.collaborative_active ||
    (Array.isArray(actions) && actions.some(a => {
      const raw = String(a?.raw || '').toLowerCase();
      return raw.includes('dish') || raw.includes('cup') || raw.includes('bar');
    }))
  );

  const [legendTab, setLegendTab] = useState<'kitchen' | 'blocks'>(hasKitchenScene ? 'kitchen' : 'blocks');

  // Check if dual arm collaboration is currently active
  const isDualArmCollaborating = Boolean(
    metrics?.collaborative_active ||
    (metrics?.collaborative_pair && metrics.collaborative_pair.length >= 2) ||
    metrics?.center_occupied_by?.includes('DUAL') ||
    (Array.isArray(actions) && actions.some(a => {
      try {
        const pa = parseAction(a?.raw || '');
        const act = String(pa.action || '').toLowerCase();
        const tgt = String(pa.target || '').toLowerCase();
        const aTime = a?.ts instanceof Date ? a.ts.getTime() : 0;
        const isDone = Array.isArray(results) && results.some(r => {
          const rTime = r?.ts instanceof Date ? r.ts.getTime() : 0;
          return rTime >= aTime;
        });
        return (act.includes('dual') || tgt.includes('bar') || tgt.includes('tray')) && !isDone;
      } catch {
        return false;
      }
    }))
  );

  // Compute block states from action history
  const blockStates = useMemo(() => {
    const states: Record<string, { state: ObjectState; robot?: string; towerIndex?: number }> = {};
    for (let i = 1; i <= 9; i++) states[`Block${i}`] = { state: 'on_table' };

    let towerCount = 0;
    actions.forEach(a => {
      const pa = parseAction(a.raw);
      const robot = pa.robot?.toUpperCase();
      const target = pa.target || '';
      const key = resolveObjectKey(target);
      if (!key || !key.startsWith('Block')) return;

      const res = results.find(r => {
        const pr = parseResult(r.raw);
        return pr.robot_id === robot && r.ts.getTime() >= a.ts.getTime();
      });

      if (!res) {
        if (pa.action === 'pick') states[key] = { state: 'in_gripper', robot };
        return;
      }

      const pr = parseResult(res.raw);
      if (pa.action === 'pick' && pr.success) {
        states[key] = { state: 'in_gripper', robot };
      } else if (pa.action === 'place' && pr.success) {
        const held = Object.entries(states).find(([, s]) => s.state === 'in_gripper' && s.robot === robot);
        if (held) {
          states[held[0]] = { state: 'on_tower', towerIndex: towerCount++ };
        }
      }
    });

    return states;
  }, [actions, results]);

  // Compute kitchenware states from action history
  const kitchenStates = useMemo(() => {
    const states: Record<
      string,
      { state: ObjectState; robot?: string; robots?: string[]; placedIndex?: number }
    > = {
      Dish1: { state: 'on_table' },
      Dish2: { state: 'on_table' },
      Dish3: { state: 'on_table' },
      Cup1:  { state: 'on_table' },
      Cup2:  { state: 'on_table' },
      Cup3:  { state: 'on_table' },
      LongBar1: { state: isDualArmCollaborating ? 'in_dual_gripper' : 'on_table', robots: ['FR3_1', 'FR3_2'] },
    };

    let placedCount = 0;
    actions.forEach(a => {
      const pa = parseAction(a.raw);
      const target = pa.target || '';
      const key = resolveObjectKey(target);
      const robot = pa.robot?.toUpperCase() || 'FR3_1';

      if (!key || !KITCHEN_OBJECTS[key]) return;

      const res = results.find(r => {
        const pr = parseResult(r.raw);
        return (pr.robot_id === robot || pr.robot_id.includes('FR3')) && r.ts.getTime() >= a.ts.getTime();
      });

      const isDualAction = pa.action.includes('dual') || key === 'LongBar1';

      if (!res) {
        if (isDualAction) {
          states[key] = { state: 'in_dual_gripper', robots: ['FR3_1', 'FR3_2'] };
        } else if (pa.action === 'pick') {
          states[key] = { state: 'in_gripper', robot };
        }
        return;
      }

      const pr = parseResult(res.raw);
      if (pr.success) {
        if (pa.action === 'pick') {
          states[key] = isDualAction
            ? { state: 'in_dual_gripper', robots: ['FR3_1', 'FR3_2'] }
            : { state: 'in_gripper', robot };
        } else if (pa.action === 'place' || pa.action.includes('transport') || pa.action.includes('carry')) {
          states[key] = { state: 'placed', placedIndex: placedCount++ };
        }
      }
    });

    if (isDualArmCollaborating) {
      states['LongBar1'] = { state: 'in_dual_gripper', robots: ['FR3_1', 'FR3_2'] };
    }

    return states;
  }, [actions, results, isDualArmCollaborating]);

  // Compute live SVG position for a kitchen object
  const getKitchenObjectPos = (key: string): { x: number; y: number; rot: number } => {
    const st = kitchenStates[key];
    const def = KITCHEN_OBJECTS[key];

    // 1. In-gripper states take visual precedence during live transport
    if (st?.state === 'in_dual_gripper') {
      // Bar suspended centered between FR3_1 and FR3_2
      const midX = (ROBOT_BASES.FR3_1.x + ROBOT_BASES.FR3_2.x) / 2;
      const midY = (ROBOT_BASES.FR3_1.y - 10 + ROBOT_BASES.FR3_2.y - 10) / 2;
      const pt = clampCoord(midX, midY);
      return { x: pt.x, y: pt.y, rot: 45 };
    }

    if (st?.state === 'in_gripper' && st.robot) {
      const base = ROBOT_BASES[st.robot] || ROBOT_BASES.FR3_1;
      const pt = clampCoord(base.x, base.y - 18);
      return { x: pt.x, y: pt.y, rot: 0 };
    }

    // 2. Dynamic /tf transform override (if available and valid)
    if (tfTransforms && (tfTransforms[key] || tfTransforms[key.toLowerCase()])) {
      const tf = tfTransforms[key] || tfTransforms[key.toLowerCase()];
      if (
        tf &&
        typeof tf.x === 'number' &&
        typeof tf.y === 'number' &&
        !Number.isNaN(tf.x) &&
        !Number.isNaN(tf.y) &&
        !(tf.x === 0 && tf.y === 0 && st?.state !== 'placed')
      ) {
        const svg = worldToSvg(tf.x, tf.y);
        let rot = 0;
        if (tf.rotation) {
          const { x: qx, y: qy, z: qz, w: qw } = tf.rotation;
          const siny_cosp = 2 * (qw * qz + qx * qy);
          const cosy_cosp = 1 - 2 * (qy * qy + qz * qz);
          rot = (Math.atan2(siny_cosp, cosy_cosp) * 180) / Math.PI;
        }
        return { x: svg.x, y: svg.y, rot };
      }
    }

    // 3. Dynamic /gemini/detected_objects override
    if (detectedObjects) {
      let det = null;
      if (Array.isArray(detectedObjects)) {
        det = detectedObjects.find((d: any) => d.name === key || d.label === key || d.id === key);
      } else if (typeof detectedObjects === 'object') {
        det = detectedObjects[key] || detectedObjects[key.toLowerCase()];
      }
      if (det && typeof det.x === 'number' && typeof det.y === 'number' && !Number.isNaN(det.x) && !Number.isNaN(det.y)) {
        const svg = worldToSvg(det.x, det.y);
        return { x: svg.x, y: svg.y, rot: det.yaw ?? det.rotation ?? 0 };
      }
    }

    // 4. Synthesized placed state
    if (st?.state === 'placed') {
      // Organized dining table arrangement: dishes centered, cups upper-right, long bar front
      if (key.startsWith('Dish')) {
        const dishNum = parseInt(key.replace('Dish', ''), 10) || 1;
        const pt = clampCoord(TARGET.x + 16 + (dishNum - 1) * 14, TARGET.y + 22);
        return { x: pt.x, y: pt.y, rot: 0 };
      }
      if (key.startsWith('Cup')) {
        const cupNum = parseInt(key.replace('Cup', ''), 10) || 1;
        const pt = clampCoord(TARGET.x + 40 + ((cupNum - 1) % 2) * 12, TARGET.y + 10 + Math.floor((cupNum - 1) / 2) * 12);
        return { x: pt.x, y: pt.y, rot: 0 };
      }
      if (key === 'LongBar1') {
        const pt = clampCoord(TARGET.x + TABLE_W / 2, TARGET.y + TABLE_H - 8);
        return { x: pt.x, y: pt.y, rot: 0 };
      }
    }

    // Default: nominal initial table coordinates
    const initial = INITIAL_KITCHEN_TABLE[key];
    if (initial) {
      const pt = clampCoord(initial.x, initial.y);
      return { x: pt.x, y: pt.y, rot: initial.rot ?? 0 };
    }
    if (def?.nominalPos) {
      const nominalSvg = worldToSvg(def.nominalPos.x, def.nominalPos.y);
      return { x: nominalSvg.x, y: nominalSvg.y, rot: 0 };
    }
    return { x: 150, y: 140, rot: 0 };
  };

  // Compute live SVG position for a block (combining /tf live stream, in_gripper tracking, and tower state)
  const getBlockPos = (blockName: string): { x: number; y: number } => {
    const st = blockStates[blockName];

    // 1. In-gripper state: attach to grasping robot arm base/hand
    if (st?.state === 'in_gripper' && st.robot) {
      const base = ROBOT_BASES[st.robot] || ROBOT_BASES.FR3_1;
      return clampCoord(base.x, base.y - 14);
    }

    // 2. Dynamic /tf transform override (if available from Isaac Sim and valid)
    const tf = tfTransforms && (tfTransforms[blockName] || tfTransforms[blockName.toLowerCase()]);
    if (
      tf &&
      typeof tf.x === 'number' &&
      typeof tf.y === 'number' &&
      !Number.isNaN(tf.x) &&
      !Number.isNaN(tf.y) &&
      !(tf.x === 0 && tf.y === 0 && st?.state !== 'on_tower')
    ) {
      return worldToSvg(tf.x, tf.y);
    }

    // 3. On-tower state: stack on central target table
    if (st?.state === 'on_tower') {
      const idx = st.towerIndex || 0;
      return {
        x: TARGET.x + 15 + (idx % 3) * 10,
        y: TARGET.y + TABLE_H - 6 - idx * 6,
      };
    }

    // 4. Default: nominal table coordinates
    return INITIAL_BLOCK_TABLE[blockName] || { x: 150, y: 140 };
  };

  const towerBlocks = Object.entries(blockStates)
    .filter(([, s]) => s.state === 'on_tower')
    .sort((a, b) => (a[1].towerIndex || 0) - (b[1].towerIndex || 0));

  const towerHeight = metrics?.tower_height ?? towerBlocks.length;

  // Center mutex indicator color & label
  const isDualOccupied = Boolean(
    metrics?.collaborative_active ||
    metrics?.center_occupied_by?.includes('DUAL') ||
    isDualArmCollaborating
  );
  const centerMutexColor = isDualOccupied
    ? '#c084fc'
    : (metrics?.center_occupied_by ? (ROBOT_BASES[metrics.center_occupied_by]?.color || C.orange) : `${C.textMuted}40`);

  // Long Bar grasp coordinates for kinematic linkage lines
  const barPos = getKitchenObjectPos('LongBar1');
  const barRotRad = (barPos.rot * Math.PI) / 180;
  const barGrasp1 = {
    x: barPos.x - 18 * Math.cos(barRotRad),
    y: barPos.y - 18 * Math.sin(barRotRad),
  };
  const barGrasp2 = {
    x: barPos.x + 18 * Math.cos(barRotRad),
    y: barPos.y + 18 * Math.sin(barRotRad),
  };

  return (
    <div style={{ padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ fontSize: fontSize - 2, fontWeight: 600, color: C.textDim }}>
          2D Workspace Digital Twin
        </div>
        {isDualArmCollaborating && (
          <div style={{
            fontSize: 9.5, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
            background: 'rgba(192, 132, 252, 0.15)', color: '#c084fc', border: '1px solid rgba(192, 132, 252, 0.4)',
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#c084fc', boxShadow: '0 0 8px #c084fc' }} />
            🤝 DUAL-ARM ACTIVE
          </div>
        )}
      </div>

      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        style={{
          width: '100%',
          borderRadius: 12,
          background: 'linear-gradient(135deg, #0b0f19 0%, #111827 100%)',
          boxShadow: 'inset 0 0 24px rgba(0,0,0,0.6), 0 4px 20px rgba(0,0,0,0.3)',
        }}
      >
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke={C.border} strokeWidth="0.25" opacity="0.25" />
          </pattern>
          <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="1" dy="2" stdDeviation="1.5" floodColor="#000" floodOpacity="0.65" />
          </filter>
          <linearGradient id="tableGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#222b3d" />
            <stop offset="100%" stopColor="#151c2c" />
          </linearGradient>
          <linearGradient id="targetGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(14, 165, 233, 0.22)" />
            <stop offset="100%" stopColor="rgba(14, 165, 233, 0.05)" />
          </linearGradient>
          <linearGradient id="barGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#7e22ce" />
            <stop offset="50%" stopColor="#a855f7" />
            <stop offset="100%" stopColor="#6b21a8" />
          </linearGradient>
        </defs>

        {/* Background Grid */}
        <rect width={SVG_W} height={SVG_H} fill="url(#grid)" />

        {/* Tables & Stations */}
        {[TABLE1, TABLE2, TABLE3, TARGET].map(t => (
          <g key={t.label}>
            <rect
              x={t.x}
              y={t.y}
              width={TABLE_W}
              height={TABLE_H}
              rx={6}
              fill={t === TARGET ? 'url(#targetGrad)' : 'url(#tableGrad)'}
              stroke={t === TARGET ? (isDualOccupied ? '#c084fc' : C.accent) : '#334155'}
              strokeWidth={t === TARGET ? 1.5 : 1}
              filter="url(#shadow)"
            />
            <text
              x={t.x + TABLE_W / 2}
              y={t.y + TABLE_H + 12}
              textAnchor="middle"
              fill={t === TARGET ? (isDualOccupied ? '#c084fc' : C.accent) : C.textDim}
              fontSize={8.5}
              fontWeight="bold"
              fontFamily={monoFont}
              opacity={0.85}
            >
              {t.label}
            </text>
          </g>
        ))}

        {/* Bar Stand Standby Station */}
        <g opacity={0.65}>
          <rect
            x={BAR_STAND.x - 24}
            y={BAR_STAND.y - 5}
            width={48}
            height={10}
            rx={4}
            transform={`rotate(60 ${BAR_STAND.x} ${BAR_STAND.y})`}
            fill="none"
            stroke="#a855f7"
            strokeWidth={1}
            strokeDasharray="3 2"
          />
          <text
            x={BAR_STAND.x + 18}
            y={BAR_STAND.y + 16}
            fill="#c084fc"
            fontSize={6.5}
            fontFamily={monoFont}
            fontWeight="bold"
            opacity={0.7}
          >
            BAR STAND
          </text>
        </g>

        {/* Center Mutex Ring */}
        <circle
          cx={TARGET.x + TABLE_W / 2}
          cy={TARGET.y + TABLE_H / 2}
          r={42}
          fill="none"
          stroke={centerMutexColor}
          strokeWidth={metrics?.center_occupied_by || isDualOccupied ? 2.2 : 1}
          strokeDasharray={metrics?.center_occupied_by || isDualOccupied ? '0' : '4 4'}
          opacity={0.85}
          filter={metrics?.center_occupied_by || isDualOccupied ? 'url(#glow)' : 'none'}
        />

        {/* Center Mutex Status Label */}
        {isDualOccupied ? (
          <text
            x={TARGET.x + TABLE_W / 2}
            y={TARGET.y - 6}
            textAnchor="middle"
            fill="#c084fc"
            fontSize={8}
            fontWeight="bold"
            fontFamily={monoFont}
            filter="url(#glow)"
          >
            🔒 DUAL-ARM MUTEX
          </text>
        ) : towerHeight > 0 ? (
          <text
            x={TARGET.x + TABLE_W / 2}
            y={TARGET.y - 6}
            textAnchor="middle"
            fill={C.accent}
            fontSize={9}
            fontWeight="bold"
            fontFamily={monoFont}
            filter="url(#glow)"
          >
            {towerHeight} LAYERS
          </text>
        ) : null}

        {/* ── Kitchen Objects Tokens (Active in Kitchen Scene or when selected) ── */}
        {(hasKitchenScene || legendTab === 'kitchen') && (
          <>
            {/* Dishes (Concentric Ceramic Platter Styling) */}
            {['Dish1', 'Dish2', 'Dish3'].map(dishKey => {
              const def = KITCHEN_OBJECTS[dishKey];
              const pos = getKitchenObjectPos(dishKey);
              const st = kitchenStates[dishKey];
              if (!def) return null;

              return (
                <g key={dishKey} filter="url(#shadow)" style={{ cursor: 'pointer' }}>
                  {/* Outer Ceramic Rim */}
                  <circle cx={pos.x} cy={pos.y} r={11.5} fill={def.color} stroke={def.stroke} strokeWidth={1.8} />
                  {/* Concentric Plate Rim Accent */}
                  <circle cx={pos.x} cy={pos.y} r={9.5} fill="none" stroke={def.stroke} strokeWidth={0.5} strokeDasharray="2 1" opacity={0.4} />
                  {/* Inner Plate Well (Depth) */}
                  <circle cx={pos.x} cy={pos.y} r={7.2} fill="none" stroke={def.stroke} strokeWidth={0.8} opacity={0.65} />
                  {/* Ceramic Glaze Reflection Highlight */}
                  <circle cx={pos.x - 3} cy={pos.y - 3} r={2.2} fill="#ffffff" opacity={0.45} />
                  {/* Dish Identifier */}
                  <text x={pos.x} y={pos.y + 2.5} textAnchor="middle" fill="#1e293b" fontSize={6} fontWeight="bold" fontFamily={monoFont}>
                    {dishKey.replace('Dish', 'D')}
                  </text>
                  <title>{def.label} ({dishKey}) [{st?.state}]</title>
                </g>
              );
            })}

            {/* Cups (Cylindrical Mug with Handle Notch & Rim Styling) */}
            {['Cup1', 'Cup2', 'Cup3'].map(cupKey => {
              const def = KITCHEN_OBJECTS[cupKey];
              const pos = getKitchenObjectPos(cupKey);
              const st = kitchenStates[cupKey];
              if (!def) return null;

              return (
                <g key={cupKey} filter="url(#shadow)" style={{ cursor: 'pointer' }}>
                  {/* Cup Cylinder Body */}
                  <circle cx={pos.x} cy={pos.y} r={7.5} fill={def.color} stroke={def.stroke} strokeWidth={1.5} />
                  {/* Inner Liquid Rim / Well */}
                  <circle cx={pos.x} cy={pos.y} r={5} fill="rgba(15, 23, 42, 0.7)" stroke={def.stroke} strokeWidth={0.8} opacity={0.8} />
                  {/* Liquid Surface */}
                  <circle cx={pos.x} cy={pos.y} r={3.8} fill={def.color} opacity={0.45} />
                  {/* Handle Notch Arc on Right Side */}
                  <path
                    d={`M ${pos.x + 6} ${pos.y - 3.5} C ${pos.x + 11} ${pos.y - 3}, ${pos.x + 11} ${pos.y + 3}, ${pos.x + 6} ${pos.y + 3.5}`}
                    fill="none"
                    stroke={def.stroke}
                    strokeWidth={1.8}
                    strokeLinecap="round"
                  />
                  {/* Cup Identifier */}
                  <text x={pos.x} y={pos.y + 2.5} textAnchor="middle" fill="#ffffff" fontSize={6} fontWeight="bold" fontFamily={monoFont}>
                    {cupKey.replace('Cup', 'C')}
                  </text>
                  <title>{def.label} ({cupKey}) [{st?.state}]</title>
                </g>
              );
            })}

            {/* Oversized Long Bar (Elongated Rounded Bar Spanning Reach) */}
            <g key="LongBar1" filter="url(#shadow)" style={{ cursor: 'pointer' }}>
              <g transform={`translate(${barPos.x}, ${barPos.y}) rotate(${barPos.rot})`}>
                {/* Rounded Long Bar Body */}
                <rect
                  x={-27}
                  y={-5.5}
                  width={54}
                  height={11}
                  rx={5}
                  fill="url(#barGrad)"
                  stroke="#c084fc"
                  strokeWidth={isDualArmCollaborating ? 2.2 : 1.4}
                />
                {/* Center Runner Metallic Spine */}
                <line x1={-20} y1={0} x2={20} y2={0} stroke="rgba(255,255,255,0.3)" strokeWidth={0.8} strokeDasharray="3 2" />
                {/* Dual Contact Grasp Points: Blue (FR3_1) & Yellow (FR3_2) */}
                <circle cx={-18} cy={0} r={2.8} fill="#38bdf8" stroke="#ffffff" strokeWidth={0.8}>
                  <title>FR3_1 Grasp Contact</title>
                </circle>
                <circle cx={18} cy={0} r={2.8} fill="#facc15" stroke="#ffffff" strokeWidth={0.8}>
                  <title>FR3_2 Grasp Contact</title>
                </circle>
                {/* Bar Label */}
                <text x={0} y={2.2} textAnchor="middle" fill="#f8fafc" fontSize={6} fontWeight="bold" fontFamily={monoFont} opacity={0.95}>
                  LONG BAR
                </text>
                {/* Pulsating Glow Aura during Co-Transport */}
                {isDualArmCollaborating && (
                  <rect x={-30} y={-8.5} width={60} height={17} rx={7} fill="none" stroke="#c084fc" strokeWidth={1.5}>
                    <animate attributeName="opacity" values="0.9;0.2;0.9" dur="1.2s" repeatCount="indefinite" />
                  </rect>
                )}
              </g>

              {/* Dynamic Kinematic Dual-Arm Linkage Lines during Co-Transport */}
              {isDualArmCollaborating && (
                <g>
                  <line
                    x1={ROBOT_BASES.FR3_1.x}
                    y1={ROBOT_BASES.FR3_1.y - 12}
                    x2={barGrasp1.x}
                    y2={barGrasp1.y}
                    stroke="#38bdf8"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                    opacity={0.85}
                    filter="url(#glow)"
                  />
                  <line
                    x1={ROBOT_BASES.FR3_2.x}
                    y1={ROBOT_BASES.FR3_2.y - 12}
                    x2={barGrasp2.x}
                    y2={barGrasp2.y}
                    stroke="#facc15"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                    opacity={0.85}
                    filter="url(#glow)"
                  />
                </g>
              )}
              <title>Oversized Long Bar (Dual-Arm Affordance: FR3_1 + FR3_2)</title>
            </g>
          </>
        )}

        {/* ── Unknown / Detected Object Fallback Tokens ─────── */}
        {detectedObjects && (
          (Array.isArray(detectedObjects)
            ? detectedObjects
            : Object.entries(detectedObjects).map(([k, v]: [string, any]) => ({ name: k, ...(typeof v === 'object' ? v : {}) }))
          )
            .filter((d: any) => {
              const name = d.name || d.label || d.id || '';
              return name && !KITCHEN_OBJECTS[name] && !name.startsWith('Block');
            })
            .map((d: any) => {
              const name = d.name || d.label || d.id || 'MysteryObject';
              const pos = (typeof d.x === 'number' && typeof d.y === 'number')
                ? worldToSvg(d.x, d.y)
                : { x: 150, y: 140 };
              return (
                <g key={name} filter="url(#shadow)" style={{ cursor: 'pointer' }}>
                  <rect
                    x={pos.x - 5}
                    y={pos.y - 5}
                    width={10}
                    height={10}
                    rx={2}
                    fill="#94a3b8"
                    stroke="#cbd5e1"
                    strokeWidth={1}
                  />
                  <circle cx={pos.x} cy={pos.y} r={2} fill="#ffffff" />
                  <text x={pos.x} y={pos.y + 11} textAnchor="middle" fill="#94a3b8" fontSize={6} fontFamily={monoFont}>
                    {name}
                  </text>
                  <title>{name} (Fallback Token)</title>
                </g>
              );
            })
        )}

        {/* ── Blocks: Dynamic Positions (Source Tables, In-Gripper, or Stacking Tower) ── */}
        {Object.entries(blockStates).map(([blockName, s]) => {
          const pos = getBlockPos(blockName);
          const shape = BLOCK_SHAPES[blockName] || 'cube';
          const color = BLOCK_COLORS[blockName] || C.textMuted;
          const isInGripper = s.state === 'in_gripper';
          const isOnTower = s.state === 'on_tower';

          return (
            <g key={blockName} filter="url(#shadow)" style={{ cursor: 'pointer' }}>
              {shape === 'cube' ? (
                <rect
                  x={pos.x - 5}
                  y={pos.y - 5}
                  width={10}
                  height={10}
                  rx={2}
                  fill={color}
                  stroke={isInGripper ? '#38bdf8' : (isOnTower ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.25)')}
                  strokeWidth={isInGripper ? 1.5 : 0.6}
                  opacity={0.95}
                />
              ) : (
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={5}
                  fill={color}
                  stroke={isInGripper ? '#38bdf8' : (isOnTower ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.25)')}
                  strokeWidth={isInGripper ? 1.5 : 0.6}
                  opacity={0.95}
                />
              )}
              {isInGripper && (
                <circle cx={pos.x} cy={pos.y} r={7.5} fill="none" stroke="#38bdf8" strokeWidth={1} opacity={0.75}>
                  <animate attributeName="r" values="6.5;9;6.5" dur="1s" repeatCount="indefinite" />
                </circle>
              )}
              <title>{BLOCK_LABELS[blockName] || blockName} [{s.state}{isOnTower ? ` Layer ${(s.towerIndex || 0) + 1}` : ''}]</title>
            </g>
          );
        })}

        {/* ── Robot Bases & Trajectories ──────────────────── */}
        {Object.entries(ROBOT_BASES).map(([name, rb]) => {
          const rm = metrics?.robots[name];
          const isActive = (rm && rm.phase !== 'IDLE' && rm.phase !== 'INIT') || (isDualArmCollaborating && (name === 'FR3_1' || name === 'FR3_2'));
          return (
            <g key={name}>
              {/* Arm line from robot to active target area */}
              {rm && rm.phase === 'PICKING' && (
                <line
                  x1={rb.x}
                  y1={rb.y - 12}
                  x2={rb.x + (TARGET.x + TABLE_W / 2 - rb.x) * 0.2}
                  y2={rb.y - 12 + (TABLE1.y - rb.y) * 0.4}
                  stroke={rb.color}
                  strokeWidth={2}
                  opacity={0.7}
                  strokeLinecap="round"
                  filter="url(#glow)"
                />
              )}
              {rm && (rm.phase === 'PLACING' || rm.phase === 'HOMING') && (
                <line
                  x1={rb.x}
                  y1={rb.y - 12}
                  x2={TARGET.x + TABLE_W / 2}
                  y2={TARGET.y + TABLE_H / 2}
                  stroke={rb.color}
                  strokeWidth={1.5}
                  opacity={0.5}
                  strokeDasharray="4 4"
                  strokeLinecap="round"
                />
              )}

              {/* Base circle */}
              <circle
                cx={rb.x}
                cy={rb.y}
                r={14}
                fill={`${rb.color}25`}
                stroke={rb.color}
                strokeWidth={isActive ? 2.5 : 1.5}
                opacity={isActive ? 1 : 0.6}
                filter={isActive ? 'url(#glow)' : 'none'}
              />

              {/* Pulsing outer ring when active */}
              {isActive && (
                <circle cx={rb.x} cy={rb.y} r={18} fill="none" stroke={rb.color} strokeWidth={1} opacity={0.5}>
                  <animate attributeName="r" values="16;22;16" dur="1.5s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.6;0;0.6" dur="1.5s" repeatCount="indefinite" />
                </circle>
              )}

              {/* Robot label */}
              <text x={rb.x} y={rb.y + 3} textAnchor="middle" fill="#fff" fontSize={8} fontWeight="bold" fontFamily={monoFont} filter="url(#shadow)">
                {name.replace('FR3_', 'R')}
              </text>
              {/* Phase label */}
              <text
                x={rb.x}
                y={rb.y + 26}
                textAnchor="middle"
                fill={isActive ? (isDualArmCollaborating && (name === 'FR3_1' || name === 'FR3_2') ? '#c084fc' : rb.color) : C.textMuted}
                fontSize={7}
                fontWeight="bold"
                fontFamily={monoFont}
              >
                {isDualArmCollaborating && (name === 'FR3_1' || name === 'FR3_2') ? 'DUAL_SYNC' : (rm?.phase || 'IDLE')}
              </text>
            </g>
          );
        })}
      </svg>

      {/* ── Digital Twin Legend & Category Switcher ──────── */}
      <div style={{ marginTop: 10, background: 'rgba(0,0,0,0.25)', borderRadius: 8, border: `1px solid ${C.border}`, overflow: 'hidden' }}>
        <div style={{ display: 'flex', borderBottom: `1px solid ${C.border}`, background: 'rgba(15, 23, 42, 0.4)' }}>
          <button
            onClick={() => setLegendTab('kitchen')}
            style={{
              flex: 1,
              padding: '6px 10px',
              fontSize: 10,
              fontWeight: 700,
              border: 'none',
              background: legendTab === 'kitchen' ? 'rgba(192, 132, 252, 0.15)' : 'transparent',
              color: legendTab === 'kitchen' ? '#c084fc' : C.textDim,
              cursor: 'pointer',
              borderBottom: legendTab === 'kitchen' ? '2px solid #c084fc' : '2px solid transparent',
            }}
          >
            🍽️ Kitchenware Tokens (R5)
          </button>
          <button
            onClick={() => setLegendTab('blocks')}
            style={{
              flex: 1,
              padding: '6px 10px',
              fontSize: 10,
              fontWeight: 700,
              border: 'none',
              background: legendTab === 'blocks' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
              color: legendTab === 'blocks' ? '#38bdf8' : C.textDim,
              cursor: 'pointer',
              borderBottom: legendTab === 'blocks' ? '2px solid #38bdf8' : '2px solid transparent',
            }}
          >
            🧱 Tower Blocks (9)
          </button>
        </div>

        <div style={{ padding: '8px 12px' }}>
          {legendTab === 'kitchen' ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {Object.entries(KITCHEN_OBJECTS).map(([name, def]) => {
                const st = kitchenStates[name];
                return (
                  <div
                    key={name}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 5,
                      fontSize: 9.5,
                      color: C.textDim,
                      fontWeight: 500,
                    }}
                  >
                    {def.shape === 'plate' && (
                      <div
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          background: def.color,
                          border: `1.5px solid ${def.stroke}`,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
                        }}
                      />
                    )}
                    {def.shape === 'cup' && (
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: def.color,
                          border: `1px solid ${def.stroke}`,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
                        }}
                      />
                    )}
                    {def.shape === 'bar' && (
                      <div
                        style={{
                          width: 18,
                          height: 6,
                          borderRadius: 3,
                          background: 'linear-gradient(90deg, #7e22ce, #c084fc)',
                          border: `1px solid #9333ea`,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
                        }}
                      />
                    )}
                    <span>{def.label}</span>
                    {st?.state === 'in_gripper' && <span style={{ color: C.blue, fontWeight: 'bold' }}>↑</span>}
                    {st?.state === 'in_dual_gripper' && <span style={{ color: '#c084fc', fontWeight: 'bold' }}>🤝</span>}
                    {st?.state === 'placed' && <span style={{ color: C.green, fontWeight: 'bold' }}>✓</span>}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {Object.entries(BLOCK_COLORS).map(([name, color]) => {
                const state = blockStates[name];
                const shape = BLOCK_SHAPES[name] || 'cube';
                return (
                  <div
                    key={name}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      fontSize: 9,
                      color: C.textDim,
                      fontWeight: 500,
                      opacity: state?.state === 'on_tower' ? 0.35 : 1,
                      transition: 'opacity 0.3s',
                    }}
                  >
                    {shape === 'cube' ? (
                      <div style={{ width: 8, height: 8, borderRadius: 2, background: color, boxShadow: '0 1px 3px rgba(0,0,0,0.5)' }} />
                    ) : (
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, boxShadow: '0 1px 3px rgba(0,0,0,0.5)' }} />
                    )}
                    {BLOCK_LABELS[name]}
                    {state?.state === 'in_gripper' && <span style={{ color: C.blue, fontWeight: 'bold' }}>↑</span>}
                    {state?.state === 'on_tower' && <span style={{ color: C.green, fontWeight: 'bold' }}>✓</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
