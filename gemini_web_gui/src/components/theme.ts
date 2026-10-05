/* ── Shared Theme, Types & Helpers ────────────────────────── */

/* ── Shared Theme, Types & Helpers ────────────────────────── */

export const C_light = {
  // Modern Clean Light Theme
  bg:       '#f8fafc', 
  bgChat:   '#ffffff', 
  bgSide:   '#f1f5f9', 
  bgInput:  '#ffffff', 
  bgHover:  '#e2e8f0', 
  border:   '#e2e8f0', 
  borderHi: '#cbd5e1',
  
  // Status Colors
  green:    '#10b981',
  greenDim: '#059669',
  greenGlow:'rgba(16, 185, 129, 0.15)',
  yellow:   '#d97706',
  
  // Text Colors
  white:    '#ffffff',
  text:     '#0f172a', 
  textDim:  '#475569',
  textMuted:'#94a3b8',
  
  red:      '#ef4444',
  redGlow:  'rgba(239, 68, 68, 0.15)',
  
  blue:     '#2563eb', 
  blueGlow: 'rgba(37, 99, 235, 0.15)',
  accent:   '#7c3aed', 
  accentDim:'#6d28d9',
  accentGlow:'rgba(124, 58, 237, 0.15)',
  
  orange:   '#ea580c',
  purple:   '#9333ea',
  purpleGlow:'rgba(147, 51, 234, 0.15)',
  cyan:     '#0891b2',
  magenta:  '#db2777',
  lime:     '#65a30d',
  
  glassBg:  'rgba(255, 255, 255, 0.88)',
  cardBg:   'linear-gradient(135deg, #ffffff, #f1f5f9)',

  // Node & Flow Cards
  nodeBg: 'linear-gradient(145deg, #ffffff 0%, #f8fafc 100%)',
  nodeBorder: 'rgba(0, 0, 0, 0.12)',
  nodeBorderHi: 'rgba(0, 0, 0, 0.24)',
  nodeShadow: '0 10px 25px -4px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.04)',
  subCardBg: 'rgba(241, 245, 249, 0.9)',
  subCardBorder: 'rgba(0, 0, 0, 0.08)',
  subCardText: '#1e293b',
  
  // Canvas & React Flow
  canvasBg: '#f8fafc',
  canvasGrid: 'rgba(0, 0, 0, 0.06)',
  canvasGridLines: '#e2e8f0',
  canvasGridDots: '#cbd5e1',
  edgeColor: '#94a3b8',
  
  // HUD Floating Bar
  hudBg: 'rgba(255, 255, 255, 0.94)',
  hudBorder: 'rgba(0, 0, 0, 0.1)',
  hudText: '#0f172a',
  hudTextDim: '#64748b',
  hudShadow: '0 6px 20px rgba(0, 0, 0, 0.06)',
  
  // Form Controls & Inputs
  inputBg: '#ffffff',
  inputBorder: '#cbd5e1',
  inputText: '#0f172a',
  selectBg: '#ffffff',
  
  // Minimap & Controls
  controlsBg: 'rgba(255, 255, 255, 0.95)',
  controlsBorder: 'rgba(0, 0, 0, 0.12)',
  miniMapBg: 'rgba(255, 255, 255, 0.95)',
  miniMapBorder: 'rgba(0, 0, 0, 0.12)',
  miniMapMask: 'rgba(0, 0, 0, 0.06)',
  
  // 2D Workspace Elements
  tableCenterBg: 'linear-gradient(145deg, #f1f5f9, #e2e8f0)',
  tableSourceBg: 'linear-gradient(145deg, #f8fafc, #f1f5f9)',
  tableBorder: 'rgba(0, 0, 0, 0.2)',
  tableText: '#1e293b',
  tableTextDim: '#64748b',
  robotBaseBg: 'linear-gradient(145deg, #ffffff, #f8fafc)',
  robotBaseBorder: '#cbd5e1',
  blockText: '#0f172a',
  elevationBadgeBg: '#ffffff',
  elevationBadgeText: '#b45309',
  elevationBadgeBorder: 'rgba(0, 0, 0, 0.15)',
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

  // Node & Flow Cards
  nodeBg: 'linear-gradient(145deg, rgba(28, 28, 35, 0.96) 0%, rgba(15, 15, 20, 0.98) 100%)',
  nodeBorder: 'rgba(255, 255, 255, 0.08)',
  nodeBorderHi: 'rgba(255, 255, 255, 0.2)',
  nodeShadow: '0 14px 32px -4px rgba(0, 0, 0, 0.6), 0 0 1px 1px rgba(255, 255, 255, 0.05)',
  subCardBg: 'rgba(24, 24, 27, 0.65)',
  subCardBorder: 'rgba(255, 255, 255, 0.05)',
  subCardText: '#e4e4e7',
  
  // Canvas & React Flow
  canvasBg: '#09090b',
  canvasGrid: 'rgba(255, 255, 255, 0.06)',
  canvasGridLines: '#18181b',
  canvasGridDots: '#27272a',
  edgeColor: '#27272a',
  
  // HUD Floating Bar
  hudBg: 'rgba(18, 18, 22, 0.85)',
  hudBorder: 'rgba(255, 255, 255, 0.08)',
  hudText: '#f4f4f5',
  hudTextDim: '#94a3b8',
  hudShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
  
  // Form Controls & Inputs
  inputBg: 'rgba(0, 0, 0, 0.45)',
  inputBorder: '#3f3f46',
  inputText: '#f4f4f5',
  selectBg: '#18181b',
  
  // Minimap & Controls
  controlsBg: 'rgba(18, 18, 22, 0.85)',
  controlsBorder: 'rgba(255, 255, 255, 0.08)',
  miniMapBg: 'rgba(9, 9, 11, 0.85)',
  miniMapBorder: 'rgba(255, 255, 255, 0.08)',
  miniMapMask: 'rgba(0, 0, 0, 0.6)',
  
  // 2D Workspace Elements
  tableCenterBg: 'linear-gradient(145deg, rgba(24, 24, 27, 0.85), rgba(9, 9, 11, 0.95))',
  tableSourceBg: 'linear-gradient(145deg, rgba(18, 18, 22, 0.75), rgba(9, 9, 12, 0.9))',
  tableBorder: 'rgba(255, 255, 255, 0.18)',
  tableText: '#f4f4f5',
  tableTextDim: '#a1a1aa',
  robotBaseBg: 'linear-gradient(145deg, rgba(24, 24, 30, 0.95), rgba(12, 12, 16, 0.98))',
  robotBaseBorder: '#3f3f46',
  blockText: '#ffffff',
  elevationBadgeBg: 'rgba(0, 0, 0, 0.85)',
  elevationBadgeText: '#fbbf24',
  elevationBadgeBorder: 'rgba(255, 255, 255, 0.1)',
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

export interface MonitoringAnomaly {
  severity: 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL';
  component: string;
  description: string;
}

export interface MonitoringStats {
  total_logs: number;
  errors: number;
  warnings: number;
  guardrail_denies: number;
  pick_success_rate_pct: number;
}

export interface MonitoringSummary {
  health_score: number;
  status: 'HEALTHY' | 'DEGRADED' | 'ANOMALOUS' | 'CRITICAL';
  executive_summary: string;
  anomalies: MonitoringAnomaly[];
  recommendations: string[];
  timestamp: number;
  model: string;
  stats: MonitoringStats;
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
  background: 'transparent', color: C.textDim, cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  transition: 'all 0.15s ease',
};

export const btnCtrl: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px',
  borderRadius: 8, cursor: 'pointer', border: `1px solid ${C.border}`,
  background: C.inputBg, color: C.text, fontSize: 12, fontWeight: 600,
  transition: 'all 0.15s ease',
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
