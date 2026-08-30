import { C, PHASE_COLORS, monoFont, type MetricsData } from './theme';

interface KpiDashboardProps {
  metrics: MetricsData | null;
  fontSize: number;
}

export default function KpiDashboard({ metrics, fontSize }: KpiDashboardProps) {
  const robots = ['FR3_1', 'FR3_2', 'FR3_3'];

  if (!metrics) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: C.textMuted, fontSize: fontSize - 1 }}>
        Waiting for robot metrics...
      </div>
    );
  }

  return (
    <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Tower height indicator */}
      <div style={{
        padding: '10px 14px', borderRadius: 10,
        background: `linear-gradient(135deg, ${C.accent}15, ${C.accent}08)`,
        border: `1px solid ${C.accent}30`,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <div style={{ fontSize: 22 }}>🏗️</div>
        <div>
          <div style={{ fontSize: fontSize - 2, color: C.textDim, fontWeight: 600 }}>Tower Height</div>
          <div style={{ fontSize: fontSize + 4, fontWeight: 800, color: C.accent }}>
            {metrics.tower_height} <span style={{ fontSize: fontSize - 2, fontWeight: 400, color: C.textDim }}>/ 9 layers</span>
          </div>
        </div>
        <div style={{ flex: 1 }} />
        {/* Mini tower visualization */}
        <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 1, alignItems: 'center' }}>
          {Array.from({ length: 9 }, (_, i) => (
            <div key={i} style={{
              width: 16, height: 4, borderRadius: 1,
              background: i < metrics.tower_height ? C.accent : `${C.textMuted}30`,
              transition: 'background 0.3s',
            }} />
          ))}
        </div>
      </div>

      {/* Center mutex indicator */}
      {metrics.center_occupied_by && (
        <div style={{
          padding: '6px 12px', borderRadius: 8, fontSize: fontSize - 2,
          background: `${C.orange}12`, border: `1px solid ${C.orange}30`,
          color: C.orange, fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{ fontSize: 10 }}>🔒</span>
          Center workspace locked by {metrics.center_occupied_by}
        </div>
      )}

      {/* Per-robot cards */}
      {robots.map(robotName => {
        const r = metrics.robots[robotName];
        if (!r) return null;
        const phaseColor = PHASE_COLORS[r.phase] || C.textMuted;

        return (
          <div key={robotName} style={{
            padding: '10px 14px', borderRadius: 10,
            background: C.bgInput,
            border: `1px solid ${C.border}`,
          }}>
            {/* Header row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              {/* Pulsing dot */}
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: phaseColor,
                boxShadow: r.phase !== 'IDLE' ? `0 0 8px ${phaseColor}80` : 'none',
                animation: r.phase === 'PICKING' || r.phase === 'PLACING' ? 'pulse 1.5s infinite' : 'none',
              }} />
              <span style={{ fontWeight: 700, color: C.white, fontSize: fontSize - 1 }}>{robotName}</span>
              <span style={{
                marginLeft: 'auto',
                padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                background: `${phaseColor}20`, color: phaseColor,
                border: `1px solid ${phaseColor}40`,
              }}>{r.phase}</span>
            </div>

            {/* Target info */}
            {r.target && (
              <div style={{ fontSize: fontSize - 3, color: C.textDim, marginBottom: 6, fontFamily: monoFont }}>
                {r.action === 'pick' ? '📦' : '📍'} {r.target} {r.action ? `(${r.action})` : ''}
              </div>
            )}

            {/* Utilization bar */}
            <div style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: C.textMuted, marginBottom: 3 }}>
                <span>Utilization</span>
                <span style={{ color: C.green, fontWeight: 600 }}>{r.busy_pct}%</span>
              </div>
              <div style={{ height: 6, background: `${C.textMuted}20`, borderRadius: 3, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 3,
                  width: `${r.busy_pct}%`,
                  background: `linear-gradient(90deg, ${C.green}, ${C.accent})`,
                  transition: 'width 0.5s ease',
                }} />
              </div>
            </div>

            {/* Counters */}
            <div style={{ display: 'flex', gap: 12, fontSize: fontSize - 3, color: C.textDim }}>
              <span>✅ {r.tasks_completed} completed</span>
              {r.tasks_failed > 0 && <span style={{ color: C.red }}>❌ {r.tasks_failed} failed</span>}
            </div>
          </div>
        );
      })}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
