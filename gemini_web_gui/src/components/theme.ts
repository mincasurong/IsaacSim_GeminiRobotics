/* ── Shared Theme, Types & Helpers ────────────────────────── */

export const C = {
  bg:       '#080a0f',
  bgChat:   '#0d111a',
  bgSide:   '#0f1420',
  bgInput:  '#161c2b',
  bgHover:  '#1e2538',
  border:   'rgba(255, 255, 255, 0.08)',
  borderHi: 'rgba(255, 255, 255, 0.16)',
  green:    '#22c55e',
  greenDim: '#16a34a',
  greenGlow:'rgba(34, 197, 94, 0.25)',
  yellow:   '#facc15',
  white:    '#f8fafc',
  text:     '#e2e8f0',
  textDim:  '#94a3b8',
  textMuted:'#64748b',
  red:      '#ef4444',
  redGlow:  'rgba(239, 68, 68, 0.25)',
  blue:     '#38bdf8',
  blueGlow: 'rgba(56, 189, 248, 0.25)',
  accent:   '#0ea5e9',
  accentDim:'#0284c7',
  accentGlow:'rgba(14, 165, 233, 0.3)',
  orange:   '#f97316',
  purple:   '#a78bfa',
  purpleGlow:'rgba(167, 139, 250, 0.25)',
  cyan:     '#06b6d4',
  magenta:  '#f472b6',
  lime:     '#a3e635',
  glassBg:  'rgba(15, 23, 42, 0.75)',
  cardBg:   'linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.7))',
};

export interface ChatMessage { 
  id: number | string; 
  role: 'user' | 'system' | 'architect' | 'vla'; 
  text: string; 
  ts: Date;
  senderName?: string;
  emoji?: string;
}
export interface LogEntry { id: number; level: number; name: string; msg: string; ts: Date; }
export interface RobotAction { id: number; raw: string; ts: Date; }

export interface RobotMetrics {
  state: string;
  phase: string;
  action: string;
  target: string;
  busy_pct: number;
  idle_pct: number;
  tasks_completed: number;
  tasks_failed: number;
}

export interface MetricsData {
  timestamp: number;
  robots: Record<string, RobotMetrics>;
  tower_height: number;
  center_occupied_by: string | null;
  collaborative_active?: boolean;
  collaborative_pair?: string[];
  collaborative_object?: string;
}

export interface KitchenObjectDef {
  name: string;
  label: string;
  shape: 'plate' | 'cup' | 'bar';
  color: string;
  stroke: string;
  nominalPos: { x: number; y: number };
  assignedRobot?: string;
  affordance: 'single_arm' | 'dual_arm';
}

export const KITCHEN_OBJECTS: Record<string, KitchenObjectDef> = {
  Dish1: {
    name: 'Dish1',
    label: 'White Ceramic Dish 1',
    shape: 'plate',
    color: '#f8fafc',
    stroke: '#94a3b8',
    nominalPos: { x: -0.10, y: -1.05 },
    assignedRobot: 'FR3_1',
    affordance: 'single_arm',
  },
  Dish2: {
    name: 'Dish2',
    label: 'Cobalt Blue Dish 2',
    shape: 'plate',
    color: '#38bdf8',
    stroke: '#0284c7',
    nominalPos: { x: 0.00, y: -1.15 },
    assignedRobot: 'FR3_1',
    affordance: 'single_arm',
  },
  Dish3: {
    name: 'Dish3',
    label: 'Terracotta Dish 3',
    shape: 'plate',
    color: '#fb923c',
    stroke: '#ea580c',
    nominalPos: { x: 0.10, y: -1.05 },
    assignedRobot: 'FR3_1',
    affordance: 'single_arm',
  },
  Cup1: {
    name: 'Cup1',
    label: 'Mustard Cup 1',
    shape: 'cup',
    color: '#facc15',
    stroke: '#ca8a04',
    nominalPos: { x: 0.82, y: 0.43 },
    assignedRobot: 'FR3_2',
    affordance: 'single_arm',
  },
  Cup2: {
    name: 'Cup2',
    label: 'Mint Tea Mug 2',
    shape: 'cup',
    color: '#4ade80',
    stroke: '#16a34a',
    nominalPos: { x: 1.00, y: 0.48 },
    assignedRobot: 'FR3_2',
    affordance: 'single_arm',
  },
  Cup3: {
    name: 'Cup3',
    label: 'Espresso Cup 3',
    shape: 'cup',
    color: '#a8a29e',
    stroke: '#57534e',
    nominalPos: { x: 0.91, y: 0.62 },
    assignedRobot: 'FR3_2',
    affordance: 'single_arm',
  },
  LongBar1: {
    name: 'LongBar1',
    label: 'Oversized Long Bar',
    shape: 'bar',
    color: '#c084fc',
    stroke: '#9333ea',
    nominalPos: { x: 0.20, y: -0.11 },
    affordance: 'dual_arm',
  },
};

export const LOG_COLORS: Record<number, string> = { 10: C.textMuted, 20: C.green, 30: C.yellow, 40: C.red, 50: '#f472b6' };
export const LOG_LABELS: Record<number, string> = { 10: 'DBG', 20: 'INF', 30: 'WRN', 40: 'ERR', 50: 'FTL' };

export const stripAnsi = (s: string) => s ? s.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '').replace(/\[[0-9;]+m/g, '').replace(/\[0m/g, '') : '';
export const fmt = (d: Date) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
export const monoFont = '"SF Mono","Fira Code","Cascadia Code","Consolas",monospace';

export const BLOCK_COLORS: Record<string, string> = {
  Block1: '#ef4444', // Red
  Block2: '#22c55e', // Green
  Block3: '#3b82f6', // Blue
  Block4: '#facc15', // Yellow
  Block5: '#ec4899', // Magenta
  Block6: '#22d3ee', // Cyan
  Block7: '#f97316', // Orange
  Block8: '#a78bfa', // Purple
  Block9: '#a3e635', // Lime
};

export const BLOCK_LABELS: Record<string, string> = {
  Block1: 'Red Cube',       Block2: 'Green Cyl',  Block3: 'Blue Cube',
  Block4: 'Yellow Cyl',     Block5: 'Magenta Cube',Block6: 'Cyan Cyl',
  Block7: 'Orange Cube',    Block8: 'Purple Cyl', Block9: 'Lime Cube',
};

export const BLOCK_SHAPES: Record<string, 'cube' | 'cylinder'> = {
  Block1: 'cube',     Block2: 'cylinder', Block3: 'cube',
  Block4: 'cylinder', Block5: 'cube',     Block6: 'cylinder',
  Block7: 'cube',     Block8: 'cylinder', Block9: 'cube',
};

export const PHASE_COLORS: Record<string, string> = {
  PICKING: C.blue,
  PLACING: C.yellow,
  HOMING:  C.green,
  QUEUED:  C.orange,
  IDLE:    C.textMuted,
  INIT:    C.textDim,
  ERROR:   C.red,
};

export const btnSmall: React.CSSProperties = {
  width: 24, height: 24, borderRadius: 6, border: 'none',
  background: 'transparent', color: '#9ca3af', cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};

export const btnCtrl: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px',
  borderRadius: 8, cursor: 'pointer', border: '1px solid #2e2e2e',
  background: 'transparent', color: '#9ca3af', fontSize: 12, fontWeight: 600,
};

export const parseAction = (raw: string) => {
  try {
    const o = JSON.parse(raw);
    const robots: string[] = Array.isArray(o.robots) ? o.robots : (o.robot ? [o.robot] : []);
    const robotStr = o.robot || (robots.length > 0 ? robots.join('+') : '');
    const target = o.target || o.object || o.object_label || '';
    const x = o.x ?? o.target_x ?? (Array.isArray(o.destination) ? o.destination[0] : undefined);
    const y = o.y ?? o.target_y ?? (Array.isArray(o.destination) ? o.destination[1] : undefined);
    return {
      action: o.action || '?',
      robot: robotStr,
      robots,
      target,
      x,
      y,
      destination: o.destination,
      sync_mode: o.sync_mode,
      detail: `${robotStr} ${target}${x !== undefined ? ` x=${x}` : ''}${y !== undefined ? ` y=${y}` : ''}`.trim(),
    };
  } catch {
    return { action: '?', robot: '', robots: [] as string[], target: '', x: undefined, y: undefined, detail: raw };
  }
};

export const parseResult = (raw: string) => {
  try {
    const o = JSON.parse(raw);
    return { success: !!o.success, message: o.message || '', robot_id: o.robot_id || '' };
  } catch {
    return { success: false, message: raw, robot_id: '' };
  }
};

export function resolveObjectKey(target: string): string | null {
  if (!target) return null;
  const t = target.toLowerCase().trim();
  if (t.includes('dish1') || t.includes('white dish') || t.includes('plate1')) return 'Dish1';
  if (t.includes('dish2') || t.includes('blue dish') || t.includes('plate2')) return 'Dish2';
  if (t.includes('dish3') || t.includes('terracotta') || t.includes('clay') || t.includes('plate3')) return 'Dish3';
  if (t.includes('cup1') || t.includes('mustard') || t.includes('amber')) return 'Cup1';
  if (t.includes('cup2') || t.includes('mint') || t.includes('green cup') || t.includes('tea')) return 'Cup2';
  if (t.includes('cup3') || t.includes('espresso') || t.includes('charcoal')) return 'Cup3';
  if (t.includes('longbar') || t.includes('long bar') || t.includes('bar') || t.includes('tray')) return 'LongBar1';
  if (t.includes('block1') || t.includes('red')) return 'Block1';
  if (t.includes('block2') || t.includes('green')) return 'Block2';
  if (t.includes('block3') || t.includes('blue')) return 'Block3';
  if (t.includes('block4') || t.includes('yellow')) return 'Block4';
  if (t.includes('block5') || t.includes('magenta')) return 'Block5';
  if (t.includes('block6') || t.includes('cyan')) return 'Block6';
  if (t.includes('block7') || t.includes('orange')) return 'Block7';
  if (t.includes('block8') || t.includes('purple')) return 'Block8';
  if (t.includes('block9') || t.includes('lime')) return 'Block9';
  return null;
}

