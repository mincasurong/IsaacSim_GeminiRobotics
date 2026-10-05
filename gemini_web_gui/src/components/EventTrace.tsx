import { useState, useMemo } from 'react';
import { ArrowUpDown, Copy, Check } from 'lucide-react';
import { C, BLOCK_LABELS, monoFont, fmt, type RobotAction, parseAction, parseResult } from './theme';

interface EventTraceProps {
  actions: RobotAction[];
  results: RobotAction[];
  fontSize: number;
}

interface TraceEvent {
  id: number;
  ts: Date;
  robot: string;
  event: string;
  target: string;
  duration: number | null; // seconds
  status: 'success' | 'failed' | 'active';
}

type SortKey = 'ts' | 'robot' | 'event' | 'duration' | 'status';
type SortDir = 'asc' | 'desc';

export default function EventTrace({ actions, results, fontSize }: EventTraceProps) {
  const [robotFilter, setRobotFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('ts');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [copied, setCopied] = useState(false);

  // Build structured events from actions + results
  const events: TraceEvent[] = useMemo(() => {
    const list: TraceEvent[] = [];
    actions.forEach(a => {
      const pa = parseAction(a.raw);
      const robot = (pa.robot || '').toUpperCase();
      if (!robot.startsWith('FR3')) return;

      const res = results.find(r => {
        const pr = parseResult(r.raw);
        return pr.robot_id === robot && r.ts.getTime() >= a.ts.getTime();
      });

      const pr = res ? parseResult(res.raw) : null;
      const targetLabel = pa.target
        ? (BLOCK_LABELS[resolveBlockKey(pa.target) || ''] || pa.target)
        : (pa.x !== undefined ? `(${pa.x}, ${pa.y})` : '');

      list.push({
        id: a.id,
        ts: a.ts,
        robot,
        event: pa.action.toUpperCase(),
        target: targetLabel,
        duration: res ? +((res.ts.getTime() - a.ts.getTime()) / 1000).toFixed(1) : null,
        status: res ? (pr?.success ? 'success' : 'failed') : 'active',
      });
    });
    return list;
  }, [actions, results]);

  // Apply filters
  const filtered = useMemo(() => {
    let list = events;
    if (robotFilter) list = list.filter(e => e.robot === robotFilter);
    if (statusFilter) list = list.filter(e => e.status === statusFilter);
    return list;
  }, [events, robotFilter, statusFilter]);

  // Apply sorting
  const sorted = useMemo(() => {
    const list = [...filtered];
    list.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'ts': cmp = a.ts.getTime() - b.ts.getTime(); break;
        case 'robot': cmp = a.robot.localeCompare(b.robot); break;
        case 'event': cmp = a.event.localeCompare(b.event); break;
        case 'duration': cmp = (a.duration || 999) - (b.duration || 999); break;
        case 'status': cmp = a.status.localeCompare(b.status); break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [filtered, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  // CSV export
  const copyCSV = () => {
    const header = 'Timestamp,Robot,Event,Target,Duration(s),Status';
    const rows = sorted.map(e =>
      `${fmt(e.ts)},${e.robot},${e.event},${e.target},${e.duration ?? ''},${e.status}`
    );
    navigator.clipboard.writeText([header, ...rows].join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusIcon = (s: string) => s === 'success' ? '✅' : s === 'failed' ? '❌' : '⏳';
  const statusColor = (s: string) => s === 'success' ? C.green : s === 'failed' ? C.red : C.blue;

  return (
    <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
      {/* Filters row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ fontSize: fontSize - 2, fontWeight: 600, color: C.textDim }}>Events</span>
        <span style={{ fontSize: 10, color: C.textMuted }}>({sorted.length})</span>
        <div style={{ flex: 1 }} />

        {/* Robot filter */}
        <select value={robotFilter || ''} onChange={e => setRobotFilter(e.target.value || null)}
          style={selectStyle}>
          <option value="">All Robots</option>
          <option value="FR3_1">FR3_1</option>
          <option value="FR3_2">FR3_2</option>
          <option value="FR3_3">FR3_3</option>
        </select>

        {/* Status filter */}
        <select value={statusFilter || ''} onChange={e => setStatusFilter(e.target.value || null)}
          style={selectStyle}>
          <option value="">All Status</option>
          <option value="success">✅ Success</option>
          <option value="failed">❌ Failed</option>
          <option value="active">⏳ Active</option>
        </select>

        {/* Copy CSV */}
        <button onClick={copyCSV} title="Copy as CSV"
          style={{
            ...selectStyle, cursor: 'pointer', display: 'flex',
            alignItems: 'center', gap: 3, color: copied ? C.green : C.textMuted,
          }}>
          {copied ? <Check size={10} /> : <Copy size={10} />}
          {copied ? 'Copied!' : 'CSV'}
        </button>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {/* Header */}
        <div style={{
          display: 'grid', gridTemplateColumns: '58px 52px 50px 1fr 48px 38px',
          gap: 4, padding: '4px 6px', borderBottom: `1px solid ${C.border}`,
          position: 'sticky', top: 0, background: C.bgSide, zIndex: 1,
        }}>
          {([
            ['ts', 'Time'],
            ['robot', 'Robot'],
            ['event', 'Event'],
            [null, 'Target'],
            ['duration', 'Dur.'],
            ['status', ''],
          ] as [SortKey | null, string][]).map(([key, label]) => (
            <div key={label || 'status'}
              onClick={key ? () => toggleSort(key) : undefined}
              style={{
                fontSize: 9, fontWeight: 700, color: C.textMuted, cursor: key ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center', gap: 2, userSelect: 'none',
                textTransform: 'uppercase', letterSpacing: 0.5,
              }}>
              {label}
              {key && sortKey === key && <ArrowUpDown size={8} color={C.accent} />}
            </div>
          ))}
        </div>

        {/* Rows */}
        {sorted.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: C.textMuted, fontSize: fontSize - 2 }}>
            No events yet
          </div>
        )}
        {sorted.map(e => (
          <div key={e.id} style={{
            display: 'grid', gridTemplateColumns: '58px 52px 50px 1fr 48px 38px',
            gap: 4, padding: '5px 6px', borderBottom: `1px solid ${C.border}15`,
            background: e.status === 'active' ? `${C.blue}08` : 'transparent',
            fontSize: fontSize - 3, fontFamily: monoFont,
          }}>
            <span style={{ color: C.textMuted }}>{fmt(e.ts)}</span>
            <span style={{ color: C.textDim, fontWeight: 600 }}>{e.robot.replace('FR3_', 'R')}</span>
            <span style={{
              padding: '0 4px', borderRadius: 3, fontSize: 9, fontWeight: 700,
              background: e.event === 'PICK' ? `${C.blue}20`
                : e.event === 'PLACE' ? `${C.yellow}20`
                : e.event === 'GO_HOME' ? `${C.green}20`
                : `${C.textMuted}20`,
              color: e.event === 'PICK' ? C.blue
                : e.event === 'PLACE' ? C.yellow
                : e.event === 'GO_HOME' ? C.green
                : C.textMuted,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>{e.event}</span>
            <span style={{ color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {e.target}
            </span>
            <span style={{ color: e.duration ? C.textDim : C.textMuted, textAlign: 'right' }}>
              {e.duration !== null ? `${e.duration}s` : '...'}
            </span>
            <span style={{ textAlign: 'center', color: statusColor(e.status) }}>
              {statusIcon(e.status)}
            </span>
          </div>
        ))}
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

const selectStyle: React.CSSProperties = {
  background: C.bgInput, color: C.textDim, border: `1px solid ${C.border}`,
  borderRadius: 4, padding: '2px 6px', fontSize: 10, outline: 'none',
};
