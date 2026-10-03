/* ── Shared Theme, Types & Helpers ────────────────────────── */

/* ── Shared Theme, Types & Helpers ────────────────────────── */

export const C_light = {
  // E-Commerce Minimalist Light Theme (Default)
  bg:       '#fafafa', 
  bgChat:   '#ffffff', 
  bgSide:   '#f4f4f4', 
  bgInput:  '#ffffff', 
  bgHover:  '#e5e5e5', 
  border:   '#e0e0e0', 
  borderHi: '#cccccc',
  
  // Status Colors
  green:    '#10b981',
  greenDim: '#059669',
  greenGlow:'rgba(16, 185, 129, 0.15)',
  yellow:   '#f59e0b',
  
  // Text Colors
  white:    '#111111', // Changed to dark for contrast in light mode
  text:     '#111111', 
  textDim:  '#555555',
  textMuted:'#888888',
  
  red:      '#ef4444',
  redGlow:  'rgba(239, 68, 68, 0.15)',
  
  blue:     '#111111', 
  blueGlow: 'rgba(17, 17, 17, 0.1)',
  accent:   '#000000', 
  accentDim:'#333333',
  accentGlow:'rgba(0, 0, 0, 0.15)',
  
  orange:   '#f97316',
  purple:   '#8b5cf6',
  purpleGlow:'rgba(139, 92, 246, 0.15)',
  cyan:     '#06b6d4',
  magenta:  '#ec4899',
  lime:     '#84cc16',
  
  glassBg:  'rgba(255, 255, 255, 0.85)',
  cardBg:   'linear-gradient(135deg, #ffffff, #f4f4f4)',
};

export const C_dark = {
  // 2026 Trendy Glassmorphic Dark Theme
  bg: '#09090b',          // Zinc 950
  bgChat: '#18181b',      // Zinc 900
  bgSide: '#09090b',
  bgInput: '#27272a',     // Zinc 800
  bgHover: '#27272a',
  border: '#27272a',
  borderHi: '#3f3f46',    // Zinc 700
  
  green: '#10b981',
  greenDim: '#059669',
  greenGlow: 'rgba(16, 185, 129, 0.25)',
  yellow: '#fbbf24',
  
  white: '#ffffff',
  text: '#f4f4f5',        // Zinc 100
  textDim: '#a1a1aa',     // Zinc 400
  textMuted: '#52525b',   // Zinc 600
  
  red: '#ef4444',
  redGlow: 'rgba(239, 68, 68, 0.25)',
  
  blue: '#3b82f6',
  blueGlow: 'rgba(59, 130, 246, 0.3)',
  
  accent: '#8b5cf6',      // Violet 500
  accentDim: '#7c3aed',
  accentGlow: 'rgba(139, 92, 246, 0.35)',
  
  orange: '#f97316',
  purple: '#d946ef',      // Fuchsia
  purpleGlow: 'rgba(217, 70, 239, 0.25)',
  cyan: '#22d3ee',        // Cyan 400
  magenta: '#ec4899',
  lime: '#a3e635',
  
  glassBg: 'rgba(9, 9, 11, 0.7)',
  cardBg: 'linear-gradient(145deg, rgba(24, 24, 27, 0.95), rgba(9, 9, 11, 0.95))',
};

// Map CSS variables to C so existing inline styles work unmodified!
export const C = Object.keys(C_light).reduce((acc, key) => {
  acc[key as keyof typeof C_light] = `var(--${key})`;
  return acc;
}, {} as typeof C_light);

export interface ChatMessage { 
  id: number | string; 
  role: 'user' | 'system' | 'architect' | 'vla' | 'generator' | 'verifier'; 
  text: string; 
  ts: Date;
  senderName?: string;
  emoji?: string;
}
export interface LogEntry { id: number; level: number; name: string; msg: string; ts: Date; }
export interface RobotAction { id: number; raw: string; ts: Date; }

export interface BlockData {
  x: number;
  y: number;
  z: number;
  status: string; // 'TABLE_1' | 'TABLE_2' | 'TABLE_3' | 'STACKED' | 'HELD' | 'TRANSIT'
  holder?: string | null;
}

export interface RobotMetrics {
  state: string;
  phase: string;
  action: string;
  target: string;
  busy_pct: number;
  idle_pct: number;
  tasks_completed: number;
  tasks_failed: number;
  j1_deg?: number;
  base_yaw_deg?: number;
}

export interface MetricsData {
  timestamp: number;
  robots: Record<string, RobotMetrics>;
  tower_height: number;
  center_occupied_by: string | null;
  blocks?: Record<string, BlockData>;
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
