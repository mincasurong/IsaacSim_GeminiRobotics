import { useMemo } from 'react';
import { C, BLOCK_COLORS, BLOCK_LABELS, monoFont, type RobotAction, type MetricsData, parseAction, parseResult } from './theme';

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

// Source tables
const TABLE1 = { x: 30, y: 140, label: 'Table 1' };   // Left (FR3_1)
const TABLE2 = { x: 210, y: 140, label: 'Table 2' };  // Right (FR3_2)
const TABLE3 = { x: 120, y: 30, label: 'Table 3' };   // Top (FR3_3)
const TARGET = { x: 120, y: 140, label: 'Target' };    // Center

// Robot base positions
const ROBOT_BASES: Record<string, { x: number; y: number; color: string }> = {
  FR3_1: { x: 60,  y: 200, color: C.blue },
  FR3_2: { x: 240, y: 200, color: C.yellow },
  FR3_3: { x: 150, y: 80,  color: C.green },
};

// Initial block assignments: Robot1 → Block1-3, Robot2 → Block4-6, Robot3 → Block7-9
const INITIAL_BLOCK_TABLE: Record<string, { x: number; y: number }> = {
  Block1: { x: TABLE1.x + 10, y: TABLE1.y + 5 },
  Block2: { x: TABLE1.x + 30, y: TABLE1.y + 5 },
  Block3: { x: TABLE1.x + 50, y: TABLE1.y + 5 },
  Block4: { x: TABLE2.x + 10, y: TABLE2.y + 5 },
  Block5: { x: TABLE2.x + 30, y: TABLE2.y + 5 },
  Block6: { x: TABLE2.x + 50, y: TABLE2.y + 5 },
  Block7: { x: TABLE3.x + 10, y: TABLE3.y + 5 },
  Block8: { x: TABLE3.x + 30, y: TABLE3.y + 5 },
  Block9: { x: TABLE3.x + 50, y: TABLE3.y + 5 },
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
      <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ width: '100%', borderRadius: 10, background: '#111' }}>
        {/* Grid lines */}
        <defs>
          <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M 30 0 L 0 0 0 30" fill="none" stroke={C.border} strokeWidth="0.3" opacity="0.3" />
          </pattern>
        </defs>
        <rect width={SVG_W} height={SVG_H} fill="url(#grid)" />

        {/* Tables */}
        {[TABLE1, TABLE2, TABLE3, TARGET].map(t => (
          <g key={t.label}>
            <rect x={t.x} y={t.y} width={TABLE_W} height={TABLE_H} rx={4}
              fill={t === TARGET ? `${C.accent}15` : `${C.textMuted}12`}
              stroke={t === TARGET ? C.accent : C.border} strokeWidth={t === TARGET ? 1.5 : 0.8} />
            <text x={t.x + TABLE_W / 2} y={t.y + TABLE_H + 12} textAnchor="middle"
              fill={C.textMuted} fontSize={8} fontFamily={monoFont}>
              {t.label}
            </text>
          </g>
        ))}

        {/* Center mutex ring */}
        <circle cx={TARGET.x + TABLE_W / 2} cy={TARGET.y + TABLE_H / 2} r={38}
          fill="none"
          stroke={metrics?.center_occupied_by
            ? ROBOT_BASES[metrics.center_occupied_by]?.color || C.orange
            : `${C.textMuted}30`}
          strokeWidth={1.2}
          strokeDasharray={metrics?.center_occupied_by ? '0' : '4 3'}
          opacity={0.6} />

        {/* Tower blocks (stacked on target) */}
        {towerBlocks.map(([blockName, s], i) => {
          const bx = TARGET.x + 15 + (i % 3) * 10;
          const by = TARGET.y + TABLE_H - 6 - (s.towerIndex || 0) * 5;
          return (
            <rect key={blockName} x={bx} y={by} width={8} height={4} rx={1}
              fill={BLOCK_COLORS[blockName] || C.textMuted} opacity={0.9}>
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
            return (
              <g key={blockName}>
                <rect x={pos.x - 4} y={pos.y + 12} width={8} height={8} rx={2}
                  fill={BLOCK_COLORS[blockName] || C.textMuted} opacity={0.9}>
                  <title>{BLOCK_LABELS[blockName] || blockName}</title>
                </rect>
              </g>
            );
          })}

        {/* Robot bases */}
        {Object.entries(ROBOT_BASES).map(([name, rb]) => {
          const rm = metrics?.robots[name];
          const isActive = rm && rm.phase !== 'IDLE' && rm.phase !== 'INIT';
          return (
            <g key={name}>
              {/* Base circle */}
              <circle cx={rb.x} cy={rb.y} r={12}
                fill={`${rb.color}20`} stroke={rb.color}
                strokeWidth={isActive ? 2 : 1}
                opacity={isActive ? 1 : 0.5} />
              {/* Pulsing outer ring when active */}
              {isActive && (
                <circle cx={rb.x} cy={rb.y} r={16}
                  fill="none" stroke={rb.color} strokeWidth={0.8} opacity={0.4}>
                  <animate attributeName="r" values="14;18;14" dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.5;0.1;0.5" dur="2s" repeatCount="indefinite" />
                </circle>
              )}
              {/* Robot label */}
              <text x={rb.x} y={rb.y + 3} textAnchor="middle"
                fill={rb.color} fontSize={7} fontWeight="bold" fontFamily={monoFont}>
                {name.replace('FR3_', 'R')}
              </text>
              {/* Phase label */}
              {rm && (
                <text x={rb.x} y={rb.y + 24} textAnchor="middle"
                  fill={C.textMuted} fontSize={6} fontFamily={monoFont}>
                  {rm.phase}
                </text>
              )}

              {/* Arm line from robot to active target area */}
              {rm && (rm.phase === 'PICKING') && (
                <line x1={rb.x} y1={rb.y - 12}
                  x2={rb.x + (TARGET.x + TABLE_W / 2 - rb.x) * 0.15}
                  y2={rb.y - 12 + (TABLE1.y - rb.y) * 0.4}
                  stroke={rb.color} strokeWidth={1.5} opacity={0.5}
                  strokeLinecap="round" />
              )}
              {rm && (rm.phase === 'PLACING' || rm.phase === 'HOMING') && (
                <line x1={rb.x} y1={rb.y - 12}
                  x2={TARGET.x + TABLE_W / 2} y2={TARGET.y + TABLE_H / 2}
                  stroke={rb.color} strokeWidth={1} opacity={0.3}
                  strokeDasharray="3 3" strokeLinecap="round" />
              )}

              {/* Block in gripper indicator */}
              {Object.entries(blockStates)
                .filter(([, s]) => s.state === 'in_gripper' && s.robot === name)
                .map(([blockName]) => (
                  <rect key={blockName} x={rb.x - 4} y={rb.y - 22} width={8} height={8} rx={2}
                    fill={BLOCK_COLORS[blockName]} opacity={0.95}>
                    <title>{BLOCK_LABELS[blockName]} (held by {name})</title>
                  </rect>
                ))}
            </g>
          );
        })}

        {/* Tower height label */}
        <text x={TARGET.x + TABLE_W / 2} y={TARGET.y - 6} textAnchor="middle"
          fill={C.accent} fontSize={9} fontWeight="bold" fontFamily={monoFont}>
          {towerHeight > 0 ? `${towerHeight} layers` : ''}
        </text>
      </svg>

      {/* Block legend */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
        {Object.entries(BLOCK_COLORS).map(([name, color]) => {
          const state = blockStates[name];
          return (
            <div key={name} style={{
              display: 'flex', alignItems: 'center', gap: 3,
              fontSize: 8, color: C.textMuted,
              opacity: state?.state === 'on_tower' ? 0.4 : 1,
            }}>
              <div style={{ width: 6, height: 6, borderRadius: 1, background: color }} />
              {BLOCK_LABELS[name]}
              {state?.state === 'in_gripper' && <span style={{ color: C.blue }}>⬆</span>}
              {state?.state === 'on_tower' && <span>✓</span>}
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
