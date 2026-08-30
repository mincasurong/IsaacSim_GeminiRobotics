import { useMemo } from 'react';
import { C, BLOCK_COLORS, BLOCK_LABELS, BLOCK_SHAPES, monoFont, type RobotAction, type MetricsData, parseAction, parseResult } from './theme';

interface SceneMapProps {
  actions: RobotAction[];
  results: RobotAction[];
  metrics: MetricsData | null;
  fontSize: number;
}

// Physical layout constants (normalized to 300x300 SVG viewport)
const SVG_W = 300;
const SVG_H = 280;
const TABLE_W = 60;
const TABLE_H = 40;

// Source tables (top-left corners, centered around real coordinates)
const TABLE1 = { x: 150 - TABLE_W / 2, y: 245 - TABLE_H / 2, label: 'Table 1' };   // Bottom (FR3_1)
const TABLE2 = { x: 241 - TABLE_W / 2, y: 87.5 - TABLE_H / 2, label: 'Table 2' };  // Top Right (FR3_2)
const TABLE3 = { x: 59 - TABLE_W / 2, y: 87.5 - TABLE_H / 2, label: 'Table 3' };   // Top Left (FR3_3)
const TARGET = { x: 150 - TABLE_W / 2, y: 140 - TABLE_H / 2, label: 'Target' };    // Center

// Robot base positions (scaled from meters to pixels: center 150,140, 1m=100px)
const ROBOT_BASES: Record<string, { x: number; y: number; color: string }> = {
  FR3_1: { x: 150, y: 185, color: C.blue },
  FR3_2: { x: 189, y: 117.5, color: C.yellow },
  FR3_3: { x: 111, y: 117.5, color: C.green },
};

// Initial block assignments: Robot1 → Block1-3, Robot2 → Block4-6, Robot3 → Block7-9
// Placed visually on their respective tables
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

type BlockState = 'on_table' | 'in_gripper' | 'on_tower';

export default function SceneMap({ actions, results, metrics, fontSize }: SceneMapProps) {
  // Compute block states from action history
  const blockStates = useMemo(() => {
    const states: Record<string, { state: BlockState; robot?: string; towerIndex?: number }> = {};
    // Initialize all blocks on their tables
    for (let i = 1; i <= 9; i++) states[`Block${i}`] = { state: 'on_table' };

    let towerCount = 0;
    actions.forEach(a => {
      const pa = parseAction(a.raw);
      const robot = pa.robot?.toUpperCase();
      const target = pa.target || '';

      // Find matching result
      const res = results.find(r => {
        const pr = parseResult(r.raw);
        return pr.robot_id === robot && r.ts.getTime() >= a.ts.getTime();
      });

      if (!res) {
        // Action still in progress
        if (pa.action === 'pick' && target) {
          const blockKey = resolveBlockKey(target);
          if (blockKey && states[blockKey]) {
            states[blockKey] = { state: 'in_gripper', robot };
          }
        }
        return;
      }

      const pr = parseResult(res.raw);
      if (pa.action === 'pick' && pr.success && target) {
        const blockKey = resolveBlockKey(target);
        if (blockKey) states[blockKey] = { state: 'in_gripper', robot };
      } else if (pa.action === 'place' && pr.success) {
        // Find which block this robot is holding
        const held = Object.entries(states).find(([, s]) => s.state === 'in_gripper' && s.robot === robot);
        if (held) {
          states[held[0]] = { state: 'on_tower', towerIndex: towerCount++ };
        }
      }
    });

    return states;
  }, [actions, results]);

  const towerBlocks = Object.entries(blockStates)
    .filter(([, s]) => s.state === 'on_tower')
    .sort((a, b) => (a[1].towerIndex || 0) - (b[1].towerIndex || 0));

  const towerHeight = metrics?.tower_height ?? towerBlocks.length;

  return (
    <div style={{ padding: '12px 14px' }}>
      <div style={{ fontSize: fontSize - 2, fontWeight: 600, color: C.textDim, marginBottom: 8 }}>
        Workspace Map
      </div>
      <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ width: '100%', borderRadius: 12, background: 'linear-gradient(135deg, #0f0f13 0%, #1a1a24 100%)', boxShadow: 'inset 0 0 20px rgba(0,0,0,0.5), 0 4px 20px rgba(0,0,0,0.3)' }}>
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke={C.border} strokeWidth="0.2" opacity="0.2" />
          </pattern>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="1" dy="2" stdDeviation="1.5" floodColor="#000" floodOpacity="0.6" />
          </filter>
          <linearGradient id="tableGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#2a2a35" />
            <stop offset="100%" stopColor="#1a1a24" />
          </linearGradient>
          <linearGradient id="targetGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(16, 163, 127, 0.2)" />
            <stop offset="100%" stopColor="rgba(16, 163, 127, 0.05)" />
          </linearGradient>
        </defs>
        <rect width={SVG_W} height={SVG_H} fill="url(#grid)" />

        {/* Tables */}
        {[TABLE1, TABLE2, TABLE3, TARGET].map(t => (
          <g key={t.label}>
            <rect x={t.x} y={t.y} width={TABLE_W} height={TABLE_H} rx={6}
              fill={t === TARGET ? 'url(#targetGrad)' : 'url(#tableGrad)'}
              stroke={t === TARGET ? C.accent : '#3a3a45'} strokeWidth={t === TARGET ? 1.5 : 1}
              filter="url(#shadow)" />
            <text x={t.x + TABLE_W / 2} y={t.y + TABLE_H + 14} textAnchor="middle"
              fill={t === TARGET ? C.accent : C.textDim} fontSize={9} fontWeight="bold" fontFamily={monoFont} opacity={0.8}>
              {t.label}
            </text>
          </g>
        ))}

        {/* Center mutex ring */}
        <circle cx={TARGET.x + TABLE_W / 2} cy={TARGET.y + TABLE_H / 2} r={42}
          fill="none"
          stroke={metrics?.center_occupied_by
            ? ROBOT_BASES[metrics.center_occupied_by]?.color || C.orange
            : `${C.textMuted}40`}
          strokeWidth={metrics?.center_occupied_by ? 2 : 1}
          strokeDasharray={metrics?.center_occupied_by ? '0' : '4 4'}
          opacity={0.8}
          filter={metrics?.center_occupied_by ? 'url(#glow)' : 'none'} />

        {/* Tower blocks (stacked on target) */}
        {towerBlocks.map(([blockName, s], i) => {
          const shape = BLOCK_SHAPES[blockName] || 'cube';
          const bx = TARGET.x + 15 + (i % 3) * 10;
          const by = TARGET.y + TABLE_H - 6 - (s.towerIndex || 0) * 6;
          const color = BLOCK_COLORS[blockName] || C.textMuted;
          return (
            <rect key={blockName} x={bx} y={by} width={10} height={5} rx={shape === 'cylinder' ? 2.5 : 1}
              fill={color} stroke="rgba(255,255,255,0.3)" strokeWidth={0.5} opacity={0.95} filter="url(#shadow)">
              <title>{BLOCK_LABELS[blockName] || blockName} (Layer {(s.towerIndex || 0) + 1})</title>
            </rect>
          );
        })}

        {/* Blocks on source tables */}
        {Object.entries(blockStates)
          .filter(([, s]) => s.state === 'on_table')
          .map(([blockName]) => {
            const pos = INITIAL_BLOCK_TABLE[blockName];
            if (!pos) return null;
            const shape = BLOCK_SHAPES[blockName] || 'cube';
            const color = BLOCK_COLORS[blockName] || C.textMuted;
            return (
              <g key={blockName} filter="url(#shadow)">
                {shape === 'cube' ? (
                  <rect x={pos.x - 5} y={pos.y + 11} width={10} height={10} rx={2} fill={color} stroke="rgba(255,255,255,0.2)" strokeWidth={0.5}>
                    <title>{BLOCK_LABELS[blockName] || blockName}</title>
                  </rect>
                ) : (
                  <circle cx={pos.x} cy={pos.y + 16} r={5} fill={color} stroke="rgba(255,255,255,0.2)" strokeWidth={0.5}>
                    <title>{BLOCK_LABELS[blockName] || blockName}</title>
                  </circle>
                )}
              </g>
            );
          })}

        {/* Robot bases */}
        {Object.entries(ROBOT_BASES).map(([name, rb]) => {
          const rm = metrics?.robots[name];
          const isActive = rm && rm.phase !== 'IDLE' && rm.phase !== 'INIT';
          return (
            <g key={name}>
              {/* Arm line from robot to active target area */}
              {rm && (rm.phase === 'PICKING') && (
                <line x1={rb.x} y1={rb.y - 12}
                  x2={rb.x + (TARGET.x + TABLE_W / 2 - rb.x) * 0.2}
                  y2={rb.y - 12 + (TABLE1.y - rb.y) * 0.4}
                  stroke={rb.color} strokeWidth={2} opacity={0.7}
                  strokeLinecap="round" filter="url(#glow)" />
              )}
              {rm && (rm.phase === 'PLACING' || rm.phase === 'HOMING') && (
                <line x1={rb.x} y1={rb.y - 12}
                  x2={TARGET.x + TABLE_W / 2} y2={TARGET.y + TABLE_H / 2}
                  stroke={rb.color} strokeWidth={1.5} opacity={0.5}
                  strokeDasharray="4 4" strokeLinecap="round" />
              )}

              {/* Base circle */}
              <circle cx={rb.x} cy={rb.y} r={14}
                fill={`${rb.color}25`} stroke={rb.color}
                strokeWidth={isActive ? 2.5 : 1.5}
                opacity={isActive ? 1 : 0.6} filter={isActive ? "url(#glow)" : "none"} />
              
              {/* Pulsing outer ring when active */}
              {isActive && (
                <circle cx={rb.x} cy={rb.y} r={18}
                  fill="none" stroke={rb.color} strokeWidth={1} opacity={0.5}>
                  <animate attributeName="r" values="16;22;16" dur="1.5s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.6;0;0.6" dur="1.5s" repeatCount="indefinite" />
                </circle>
              )}
              
              {/* Robot label */}
              <text x={rb.x} y={rb.y + 3} textAnchor="middle"
                fill="#fff" fontSize={8} fontWeight="bold" fontFamily={monoFont} filter="url(#shadow)">
                {name.replace('FR3_', 'R')}
              </text>
              {/* Phase label */}
              {rm && (
                <text x={rb.x} y={rb.y + 26} textAnchor="middle"
                  fill={isActive ? rb.color : C.textMuted} fontSize={7} fontWeight="bold" fontFamily={monoFont}>
                  {rm.phase}
                </text>
              )}

              {/* Block in gripper indicator */}
              {Object.entries(blockStates)
                .filter(([, s]) => s.state === 'in_gripper' && s.robot === name)
                .map(([blockName]) => {
                  const shape = BLOCK_SHAPES[blockName] || 'cube';
                  const color = BLOCK_COLORS[blockName];
                  return (
                    <g key={blockName} filter="url(#shadow)">
                      {shape === 'cube' ? (
                        <rect x={rb.x - 5} y={rb.y - 24} width={10} height={10} rx={2} fill={color} stroke="#fff" strokeWidth={0.5}>
                          <title>{BLOCK_LABELS[blockName]} (held by {name})</title>
                        </rect>
                      ) : (
                        <circle cx={rb.x} cy={rb.y - 19} r={5} fill={color} stroke="#fff" strokeWidth={0.5}>
                          <title>{BLOCK_LABELS[blockName]} (held by {name})</title>
                        </circle>
                      )}
                    </g>
                  );
                })}
            </g>
          );
        })}

        {/* Tower height label */}
        <text x={TARGET.x + TABLE_W / 2} y={TARGET.y - 8} textAnchor="middle"
          fill={C.accent} fontSize={10} fontWeight="bold" fontFamily={monoFont} filter="url(#glow)">
          {towerHeight > 0 ? `${towerHeight} LAYERS` : ''}
        </text>
      </svg>

      {/* Block legend */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12, padding: '8px 12px', background: 'rgba(0,0,0,0.2)', borderRadius: 8, border: `1px solid ${C.border}` }}>
        {Object.entries(BLOCK_COLORS).map(([name, color]) => {
          const state = blockStates[name];
          const shape = BLOCK_SHAPES[name] || 'cube';
          return (
            <div key={name} style={{
              display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 9, color: C.textDim, fontWeight: 500,
              opacity: state?.state === 'on_tower' ? 0.3 : 1,
              transition: 'opacity 0.3s'
            }}>
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
    </div>
  );
}

function resolveBlockKey(target: string): string | null {
  const t = target.toLowerCase();
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
