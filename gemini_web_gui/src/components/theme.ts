/* ── Shared Theme, Types & Helpers ────────────────────────── */

export const C = {
  // CCS Brand Colors (Dark Theme)
  bg:       '#262624', // Background RGB(38, 38, 36)
  bgChat:   '#2a2a28', // Slightly lighter for chat area
  bgSide:   '#212120', // Slightly darker for sidebars
  bgInput:  '#30302e', // Input fields (muted)
  bgHover:  '#3a3a38', // Hover state
  border:   '#454441', // CCS --border
  borderHi: '#555451',
  
  // Status Colors (Softened to match CCS vibe)
  green:    '#4ade80',
  greenDim: '#22c55e',
  greenGlow:'rgba(74, 222, 128, 0.25)',
  yellow:   '#facc15',
  
  // Text Colors
  white:    '#ffffff',
  text:     '#f4f3f1', // Pampas (CCS foreground)
  textDim:  '#a09e9c',
  textMuted:'#757471',
  
  // Danger / Destructive
  red:      '#ef4444',
  redGlow:  'rgba(239, 68, 68, 0.25)',
  
  // Brand Accent (Crail / Rust Orange)
  blue:     '#d46a43', // Repurposing 'blue' base to the CCS Accent so existing uses get the brand color
  blueGlow: 'rgba(212, 106, 67, 0.25)',
  accent:   '#d46a43', // Crail
  accentDim:'#b35532',
  accentGlow:'rgba(212, 106, 67, 0.3)',
  
  // Other accents (warmed up)
  orange:   '#f97316',
  purple:   '#a78bfa',
  purpleGlow:'rgba(167, 139, 250, 0.25)',
  cyan:     '#06b6d4',
  magenta:  '#f472b6',
  lime:     '#a3e635',
  
  // Surfaces
  glassBg:  'rgba(38, 38, 36, 0.75)',
  cardBg:   'linear-gradient(135deg, rgba(48, 48, 46, 0.9), rgba(38, 38, 36, 0.7))',
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
