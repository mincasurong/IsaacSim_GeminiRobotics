import { useState, useEffect } from 'react';
import { Plus, Minus } from 'lucide-react';
import { C, monoFont, type RobotAction, type MetricsData } from './theme';

interface GanttChartProps {
  actions: RobotAction[];
  results: RobotAction[];
  metrics: MetricsData | null;
  fontSize: number;
}

const ZOOM_LEVELS = [5000, 15000, 30000, 60000];

export default function GanttChart({ actions, results, metrics, fontSize }: GanttChartProps) {
  const [now, setNow] = useState(Date.now());
  const [zoomIdx, setZoomIdx] = useState(1); // default 15s window
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 200); return () => clearInterval(t); }, []);

  const robots = ['FR3_1', 'FR3_2', 'FR3_3'];
  const windowMs = ZOOM_LEVELS[zoomIdx];

  // Build task segments from action/result pairs
  const tasks: {
    robot: string; action: string; start: number; end: number;
    finished: boolean; success: boolean; queued: boolean;
  }[] = [];

  actions.forEach(a => {
    try {
      const p = JSON.parse(a.raw);
      const robot = (p.robot || 'GLOBAL').toUpperCase();
      if (!robot.startsWith('FR3')) return;
      const actionName = p.action || '?';

      const res = results.find((r) => {
        try {
          const rp = JSON.parse(r.raw);
          return rp.robot_id === robot && r.ts.getTime() >= a.ts.getTime();
        } catch { return false; }
      });

      tasks.push({
        robot,
        action: actionName,
        start: a.ts.getTime(),
        end: res ? res.ts.getTime() : now,
        finished: !!res,
        success: res ? JSON.parse(res.raw).success : true,
        queued: false,
      });
    } catch { /* ignore malformed */ }
  });

  // Add queue segments: detect gaps where robot is in QUEUED phase
  if (metrics) {
    for (const robotName of robots) {
      const rm = metrics.robots[robotName];
      if (rm && rm.phase === 'QUEUED') {
        // Find the last completed action for this robot
        const robotTasks = tasks.filter(t => t.robot === robotName);
        const lastEnd = robotTasks.length > 0 ? Math.max(...robotTasks.map(t => t.end)) : now - 3000;
        tasks.push({
          robot: robotName,
          action: 'WAIT',
          start: lastEnd,
          end: now,
          finished: false,
          success: true,
          queued: true,
        });
      }
    }
  }

  // Time axis
  const maxTime = now;
  const minTime = maxTime - windowMs;

  // Generate tick marks every 5s
  const tickInterval = windowMs <= 10000 ? 2000 : windowMs <= 30000 ? 5000 : 10000;
  const firstTick = Math.ceil(minTime / tickInterval) * tickInterval;
  const ticks: number[] = [];
  for (let t = firstTick; t <= maxTime; t += tickInterval) ticks.push(t);

  return (
    <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Zoom controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: fontSize - 2, fontWeight: 600, color: C.textDim }}>Timeline</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => setZoomIdx(i => Math.max(0, i - 1))} disabled={zoomIdx === 0}
          style={{ ...zoomBtn, opacity: zoomIdx === 0 ? 0.3 : 1 }}><Plus size={10} /></button>
        <span style={{ fontSize: 10, color: C.textMuted, minWidth: 28, textAlign: 'center' }}>
          {windowMs / 1000}s
        </span>
        <button onClick={() => setZoomIdx(i => Math.min(ZOOM_LEVELS.length - 1, i + 1))} disabled={zoomIdx === ZOOM_LEVELS.length - 1}
          style={{ ...zoomBtn, opacity: zoomIdx === ZOOM_LEVELS.length - 1 ? 0.3 : 1 }}><Minus size={10} /></button>
      </div>

      {/* Gantt rows */}
      {robots.map(r => {
        const phaseColor = metrics?.robots[r]
          ? (metrics.robots[r].phase === 'PICKING' ? C.blue
            : metrics.robots[r].phase === 'PLACING' ? C.yellow
            : metrics.robots[r].phase === 'QUEUED' ? C.orange
            : C.textMuted)
          : C.textMuted;

        return (
          <div key={r}>
            <div style={{
              fontSize: fontSize - 2, fontWeight: 600, color: C.textDim,
              marginBottom: 3, display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: phaseColor }} />
              {r}
            </div>
            <div style={{
              height: 26, background: C.bgInput, borderRadius: 6,
              position: 'relative', overflow: 'hidden',
            }}>
              {tasks.filter(t => t.robot === r && t.end > minTime && t.start < maxTime).map((t, i) => {
                const left = Math.max(0, (t.start - minTime) / windowMs * 100);
                const width = Math.min(100 - left, (t.end - Math.max(minTime, t.start)) / windowMs * 100);

                let color: string;
                if (t.queued) {
                  color = C.orange;
                } else if (!t.finished) {
                  color = C.blue;
                } else if (t.success) {
                  color = C.green;
                } else {
                  color = C.red;
                }

                const durationSec = ((t.end - t.start) / 1000).toFixed(1);

                return (
                  <div key={i} title={`${t.action.toUpperCase()} — ${durationSec}s${t.queued ? ' (waiting)' : ''}`}
                    style={{
                      position: 'absolute', left: `${left}%`, width: `${Math.max(width, 0.8)}%`,
                      top: 3, bottom: 3, borderRadius: 4,
                      background: t.queued
                        ? `repeating-linear-gradient(135deg, ${color}, ${color} 3px, ${color}80 3px, ${color}80 6px)`
                        : color,
                      opacity: 0.85,
                      display: 'flex', alignItems: 'center', padding: '0 5px', overflow: 'hidden',
                      boxShadow: !t.finished ? `0 0 10px ${color}50` : 'none',
                      transition: 'width 0.2s ease',
                    }}>
                    <span style={{
                      fontSize: 9, fontWeight: 700, color: '#000',
                      whiteSpace: 'nowrap', textShadow: '0 0 2px rgba(255,255,255,0.3)',
                    }}>
                      {t.action.toUpperCase()}{width > 8 ? ` ${durationSec}s` : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Time axis */}
      <div style={{ position: 'relative', height: 16, marginTop: 2 }}>
        {ticks.map(t => {
          const left = (t - minTime) / windowMs * 100;
          if (left < 0 || left > 100) return null;
          const label = new Date(t).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' });
          return (
            <div key={t} style={{
              position: 'absolute', left: `${left}%`, transform: 'translateX(-50%)',
              display: 'flex', flexDirection: 'column', alignItems: 'center',
            }}>
              <div style={{ width: 1, height: 4, background: C.border }} />
              <span style={{ fontSize: 8, color: C.textMuted, fontFamily: monoFont, marginTop: 1 }}>{label}</span>
            </div>
          );
        })}
        {/* Now marker */}
        <div style={{
          position: 'absolute', right: 0, top: 0,
          width: 2, height: 4, background: C.red,
        }} />
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
        {[
          { color: C.blue, label: 'Active' },
          { color: C.green, label: 'Success' },
          { color: C.red, label: 'Failed' },
          { color: C.orange, label: 'Queued' },
        ].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9, color: C.textMuted }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: l.color, opacity: 0.85 }} />
            {l.label}
          </div>
        ))}
      </div>
    </div>
  );
}

const zoomBtn: React.CSSProperties = {
  width: 20, height: 20, borderRadius: 4, border: `1px solid ${C.border}`,
  background: 'transparent', color: C.textDim, cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};
