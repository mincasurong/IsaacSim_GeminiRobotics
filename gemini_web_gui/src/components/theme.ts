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
}

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
    return {
      action: o.action || '?',
      robot: o.robot || '',
      target: o.target || '',
      x: o.x,
      y: o.y,
      detail: `${o.robot || ''} ${o.target || ''}${o.x !== undefined ? ` x=${o.x}` : ''}${o.y !== undefined ? ` y=${o.y}` : ''}`.trim(),
    };
  } catch {
    return { action: '?', robot: '', target: '', x: undefined, y: undefined, detail: raw };
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
