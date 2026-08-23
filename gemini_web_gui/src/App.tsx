import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic, MicOff, Send, Bot, Wifi, WifiOff, Trash2,
  Activity, Cpu, Terminal, ChevronDown, ChevronUp,
  Play, Square, RotateCcw, Plus, Minus, Wrench, GanttChart, FileCode2,
  PanelRightOpen, PanelRightClose, User
} from 'lucide-react';

const ROSLIB = (window as any).ROSLIB;
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
const API = 'http://localhost:3001';

/* ── Theme ──────────────────────────────────────────────── */
const C = {
  bg:       '#0d0d0d',
  bgChat:   '#171717',
  bgSide:   '#1a1a1a',
  bgInput:  '#2a2a2a',
  bgHover:  '#333333',
  border:   '#2e2e2e',
  borderHi: '#444',
  green:    '#22c55e',
  greenDim: '#16a34a',
  greenGlow:'rgba(34,197,94,0.25)',
  yellow:   '#facc15',
  white:    '#ececec',
  text:     '#d1d5db',
  textDim:  '#9ca3af',
  textMuted:'#6b7280',
  red:      '#ef4444',
  redGlow:  'rgba(239,68,68,0.3)',
  blue:     '#38bdf8',
  accent:   '#10a37f',
  accentDim:'#0d8c6d',
};

/* ── Types ──────────────────────────────────────────────── */
interface ChatMessage { id: number; role: 'user' | 'system'; text: string; ts: Date; }
interface LogEntry { id: number; level: number; name: string; msg: string; ts: Date; }
interface RobotAction { id: number; raw: string; ts: Date; }

const LOG_COLORS: Record<number, string> = { 10: C.textMuted, 20: C.green, 30: C.yellow, 40: C.red, 50: '#f472b6' };
const LOG_LABELS: Record<number, string> = { 10: 'DBG', 20: 'INF', 30: 'WRN', 40: 'ERR', 50: 'FTL' };
const stripAnsi = (s: string) => s ? s.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '').replace(/\[[0-9;]+m/g, '').replace(/\[0m/g, '') : '';
const fmt = (d: Date) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
const monoFont = '"SF Mono","Fira Code","Cascadia Code","Consolas",monospace';

/* ── Gantt Chart ────────────────────────────────────────── */
function GanttView({ actions, results, fontSize }: { actions: any[], results: any[], fontSize: number }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 200); return () => clearInterval(t); }, []);

  const robots = ['FR3_1', 'FR3_2', 'FR3_3'];
  const tasks: any[] = [];
  actions.forEach(a => {
    try {
      const p = JSON.parse(a.raw);
      const robot = p.robot || 'GLOBAL';
      const actionName = p.action || '?';
      const res = results.find((r: any) => { try { const rp = JSON.parse(r.raw); return rp.robot_id === robot && r.ts.getTime() >= a.ts.getTime(); } catch { return false; } });
      tasks.push({ robot, action: actionName, start: a.ts.getTime(), end: res ? res.ts.getTime() : now, finished: !!res, success: res ? JSON.parse(res.raw).success : true });
    } catch {}
  });

  if (tasks.length === 0) return <div style={{ color: C.textMuted, padding: 24, textAlign: 'center', fontSize: fontSize - 1 }}>No actions yet</div>;

  const maxTime = Math.max(now, ...tasks.map(t => t.end));
  let minTime = maxTime - 15000;
  if (tasks.some(t => !t.finished)) { const e = Math.min(...tasks.filter(t => !t.finished).map(t => t.start)); if (e < minTime) minTime = e - 2000; }
  const duration = Math.max(5000, maxTime - minTime);

  return (
    <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {robots.map(r => (
        <div key={r}>
          <div style={{ fontSize: fontSize - 2, fontWeight: 600, color: C.textDim, marginBottom: 4 }}>{r}</div>
          <div style={{ height: 28, background: C.bgInput, borderRadius: 8, position: 'relative', overflow: 'hidden' }}>
            {tasks.filter(t => t.robot === r && t.end > minTime).map((t, i) => {
              const left = Math.max(0, (t.start - minTime) / duration * 100);
              const width = Math.min(100 - left, (t.end - Math.max(minTime, t.start)) / duration * 100);
              const color = !t.finished ? C.blue : (t.success ? C.green : C.red);
              return (
                <div key={i} style={{
                  position: 'absolute', left: `${left}%`, width: `${Math.max(width, 1)}%`, top: 3, bottom: 3,
                  background: color, borderRadius: 5, opacity: 0.85,
                  display: 'flex', alignItems: 'center', padding: '0 6px', overflow: 'hidden',
                  boxShadow: !t.finished ? `0 0 12px ${color}66` : 'none',
                  transition: 'width 0.2s ease',
                }}>
                  <span style={{ fontSize: 9, fontWeight: 700, color: '#000', whiteSpace: 'nowrap' }}>{t.action.toUpperCase()}</span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Main App ───────────────────────────────────────────── */
function App() {
  const [connected, setConnected] = useState(false);
  const [text, setText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [bringupRunning, setBringupRunning] = useState(false);
  const [termLines, setTermLines] = useState<string[]>([]);
  const [fontSize, setFontSize] = useState(14);
  const [sideOpen, setSideOpen] = useState(true);
  const [bottomOpen, setBottomOpen] = useState(true);
  const [sideTab, setSideTab] = useState<'gantt'|'results'>('gantt');

  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 0, role: 'system', text: 'Welcome to Gemini Robotics ER. Click **▶ Start** to launch the robot workspace, then type or speak a goal to begin.', ts: new Date() },
  ]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [actions, setActions] = useState<RobotAction[]>([]);
  const [actionResults, setActionResults] = useState<RobotAction[]>([]);
  const [logAutoScroll, setLogAutoScroll] = useState(true);
  const [minLogLevel, setMinLogLevel] = useState(20);

  const ros = useRef<any>(null);
  const goalTopic = useRef<any>(null);
  const resetTopic = useRef<any>(null);
  const recognition = useRef<any>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const termEndRef = useRef<HTMLDivElement>(null);
  const seqRef = useRef(1);

  const addMsg = useCallback((role: 'user'|'system', text: string) => setMessages(p => [...p, { id: seqRef.current++, role, text, ts: new Date() }]), []);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { if (logAutoScroll) logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs, logAutoScroll]);
  useEffect(() => { termEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [termLines]);

  /* ── SSE ──────────────────────────────────────────────── */
  useEffect(() => {
    let es: EventSource | null = null;
    const connectSSE = () => {
      es = new EventSource(`${API}/api/logs`);
      es.onmessage = (e) => { try { const d = JSON.parse(e.data); if (d.type === 'log') setTermLines(p => { const n = [...p, d.line]; return n.length > 500 ? n.slice(-500) : n; }); else if (d.type === 'status') setBringupRunning(d.running); } catch {} };
      es.onerror = () => { es?.close(); setTimeout(connectSSE, 3000); };
    };
    fetch(`${API}/api/status`).then(r => r.json()).then(d => setBringupRunning(d.running)).catch(() => {});
    connectSSE();
    return () => { es?.close(); };
  }, []);

  /* ── ROS + Speech ─────────────────────────────────────── */
  useEffect(() => {
    const initROS = () => {
      if (!ROSLIB) return;
      ros.current = new ROSLIB.Ros({ url: 'ws://localhost:9090' });
      ros.current.on('connection', () => {
        setConnected(true);
        goalTopic.current = new ROSLIB.Topic({ ros: ros.current, name: '/gemini/custom_goal', messageType: 'std_msgs/String' });
        resetTopic.current = new ROSLIB.Topic({ ros: ros.current, name: '/reset_simulation', messageType: 'std_msgs/Empty' });
        new ROSLIB.Topic({ ros: ros.current, name: '/rosout', messageType: 'rcl_interfaces/Log' })
          .subscribe((m: any) => { setLogs(p => { const n = [...p, { id: seqRef.current++, level: m.level, name: m.name, msg: m.msg, ts: new Date() }]; return n.length > 500 ? n.slice(-500) : n; }); });
        new ROSLIB.Topic({ ros: ros.current, name: '/gemini/action', messageType: 'std_msgs/String' })
          .subscribe((m: any) => { setActions(p => { const n = [...p, { id: seqRef.current++, raw: m.data, ts: new Date() }]; return n.length > 100 ? n.slice(-100) : n; }); });
        new ROSLIB.Topic({ ros: ros.current, name: '/gemini/action_result', messageType: 'std_msgs/String' })
          .subscribe((m: any) => { setActionResults(p => { const n = [...p, { id: seqRef.current++, raw: m.data, ts: new Date() }]; return n.length > 100 ? n.slice(-100) : n; }); });
      });
      ros.current.on('error', () => setConnected(false));
      ros.current.on('close', () => { setConnected(false); setTimeout(initROS, 3000); });
    };
    initROS();
    if (SpeechRecognition) {
      recognition.current = new SpeechRecognition();
      recognition.current.continuous = true;
      recognition.current.interimResults = true;
      recognition.current.onresult = (e: any) => { let t = ''; for (let i = e.resultIndex; i < e.results.length; ++i) if (e.results[i].isFinal) t += e.results[i][0].transcript; if (t) setText(prev => prev ? prev + ' ' + t : t); };
      recognition.current.onerror = () => setIsRecording(false);
      recognition.current.onend = () => setIsRecording(false);
    }
    return () => { ros.current?.close(); recognition.current?.stop(); };
  }, []);

  /* ── Handlers ─────────────────────────────────────────── */
  const toggleMic = () => { if (!recognition.current) { alert('Chrome/Edge only'); return; } if (isRecording) { recognition.current.stop(); setIsRecording(false); } else { setText(''); recognition.current.start(); setIsRecording(true); } };
  const sendGoal = () => {
    if (!text.trim()) return;
    if (!connected || !goalTopic.current) { addMsg('system', '⚠️ Not connected to ROS 2. Start the backend first.'); return; }
    addMsg('user', text.trim());
    goalTopic.current.publish(new ROSLIB.Message({ data: text.trim() }));
    addMsg('system', '✅ Goal sent to Gemini agent.');
    setText('');
  };
  const startBringup = async () => { try { await fetch(`${API}/api/start`, { method: 'POST' }); setBringupRunning(true); } catch { addMsg('system', '❌ Backend unreachable.'); } };
  const stopBringup = async () => { try { await fetch(`${API}/api/stop`, { method: 'POST' }); setBringupRunning(false); } catch {} };
  const triggerBuild = async () => { try { await fetch(`${API}/api/build`, { method: 'POST' }); addMsg('system', '🔧 Build triggered. Check WSL terminal.'); } catch { addMsg('system', '❌ Backend unreachable.'); } };
  const resetSim = () => { if (!connected || !resetTopic.current) { addMsg('system', '⚠️ Not connected.'); return; } resetTopic.current.publish(new ROSLIB.Message({})); addMsg('system', '🔄 Simulation reset sent.'); };

  const filteredLogs = logs.filter(l => l.level >= minLogLevel);

  const parseAction = (raw: string) => { try { const o = JSON.parse(raw); return { action: o.action || '?', detail: `${o.robot || ''} ${o.target || ''}${o.x !== undefined ? ` x=${o.x}` : ''}${o.y !== undefined ? ` y=${o.y}` : ''}`.trim() }; } catch { return { action: '?', detail: raw }; } };

  const renderMarkdown = (t: string) => t.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  /* ── Render ───────────────────────────────────────────── */
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: C.bg, fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif', color: C.text, fontSize }}>

      {/* ════ Top Bar ════ */}
      <div style={{ height: 48, padding: '0 16px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${C.border}`, background: C.bgChat, flexShrink: 0 }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: C.accent, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Bot size={16} color="#fff" /></div>
        <span style={{ fontWeight: 700, color: C.white, fontSize: 15 }}>Gemini Robotics ER</span>
        
        <div style={{ flex: 1 }} />

        {/* Font */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <button onClick={() => setFontSize(s => Math.max(10, s-1))} style={btnSmall}><Minus size={11} /></button>
          <span style={{ fontSize: 10, color: C.textMuted, width: 20, textAlign: 'center' }}>{fontSize}</span>
          <button onClick={() => setFontSize(s => Math.min(20, s+1))} style={btnSmall}><Plus size={11} /></button>
        </div>

        <div style={{ width: 1, height: 20, background: C.border, margin: '0 4px' }} />

        {/* Controls */}
        <button onClick={triggerBuild} style={{ ...btnCtrl, color: C.blue }}><Wrench size={13} /> Build</button>
        {!bringupRunning
          ? <button onClick={startBringup} style={{ ...btnCtrl, background: C.accent, color: '#fff', border: 'none' }}><Play size={13} /> Start</button>
          : <button onClick={stopBringup} style={{ ...btnCtrl, background: C.red, color: '#fff', border: 'none' }}><Square size={13} /> Stop</button>
        }
        <button onClick={resetSim} style={{ ...btnCtrl, color: C.yellow }}><RotateCcw size={13} /> Reset</button>

        <div style={{ width: 1, height: 20, background: C.border, margin: '0 4px' }} />

        {/* Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: connected ? C.green : C.red }}>
          {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
          <span style={{ fontWeight: 600 }}>{connected ? 'Connected' : 'Offline'}</span>
        </div>

        {/* Toggle side */}
        <button onClick={() => setSideOpen(!sideOpen)} style={{ ...btnSmall, marginLeft: 4 }}>
          {sideOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
        </button>
      </div>

      {/* ════ Main Body ════ */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* ── Chat Area (center) ──────────────────────── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
            <div style={{ maxWidth: 720, width: '100%', margin: '0 auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 0 }}>
              {messages.map(m => (
                <div key={m.id} style={{
                  padding: '20px 0',
                  borderBottom: `1px solid ${C.border}`,
                  display: 'flex', gap: 14, alignItems: 'flex-start',
                }}>
                  {/* Avatar */}
                  <div style={{
                    width: 30, height: 30, borderRadius: 6, flexShrink: 0,
                    background: m.role === 'user' ? C.bgHover : C.accent,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {m.role === 'user' ? <User size={14} color={C.textDim} /> : <Bot size={14} color="#fff" />}
                  </div>
                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: fontSize - 1, fontWeight: 700, color: C.white, marginBottom: 4 }}>
                      {m.role === 'user' ? 'You' : 'Gemini Robotics'}
                    </div>
                    <div
                      style={{ fontSize: fontSize, lineHeight: 1.65, color: C.text, wordBreak: 'break-word' }}
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }}
                    />
                    <div style={{ fontSize: 10, color: C.textMuted, marginTop: 6 }}>{fmt(m.ts)}</div>
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
          </div>

          {/* Input Bar */}
          <div style={{ borderTop: `1px solid ${C.border}`, background: C.bgChat, padding: '16px 24px' }}>
            <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', gap: 10, alignItems: 'center', background: C.bgInput, borderRadius: 14, padding: '4px 6px 4px 16px', border: `1px solid ${C.borderHi}` }}>
              <button onClick={toggleMic} style={{
                width: 32, height: 32, borderRadius: '50%', border: 'none', cursor: 'pointer', flexShrink: 0,
                background: isRecording ? C.red : 'transparent', color: isRecording ? '#fff' : C.textMuted,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: isRecording ? `0 0 12px ${C.redGlow}` : 'none',
              }}>{isRecording ? <MicOff size={15} /> : <Mic size={15} />}</button>

              <input type="text" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendGoal()}
                placeholder={isRecording ? 'Listening...' : 'Send a goal to Gemini...'}
                style={{ flex: 1, height: 40, border: 'none', background: 'transparent', color: C.white, fontSize: fontSize, outline: 'none' }}
              />

              <button onClick={sendGoal} disabled={!text.trim()} style={{
                width: 36, height: 36, borderRadius: 10, border: 'none', cursor: text.trim() ? 'pointer' : 'default', flexShrink: 0,
                background: text.trim() ? C.accent : 'transparent', color: text.trim() ? '#fff' : C.textMuted,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s',
              }}><Send size={15} /></button>
            </div>
            <div style={{ maxWidth: 720, margin: '6px auto 0', fontSize: 10, color: C.textMuted, textAlign: 'center' }}>
              Gemini Robotics ER controls 3 Franka FR3 arms via Isaac Sim
            </div>
          </div>
        </div>

        {/* ── Right Sidebar ──────────────────────────── */}
        {sideOpen && (
          <div style={{ width: 360, borderLeft: `1px solid ${C.border}`, background: C.bgSide, display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
            {/* Tabs */}
            <div style={{ display: 'flex', borderBottom: `1px solid ${C.border}` }}>
              <button onClick={() => setSideTab('gantt')} style={{
                flex: 1, padding: '10px 0', border: 'none', cursor: 'pointer', fontSize: fontSize - 2, fontWeight: 600,
                background: 'transparent', color: sideTab === 'gantt' ? C.accent : C.textMuted,
                borderBottom: sideTab === 'gantt' ? `2px solid ${C.accent}` : '2px solid transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}><GanttChart size={13} /> Timeline</button>
              <button onClick={() => setSideTab('results')} style={{
                flex: 1, padding: '10px 0', border: 'none', cursor: 'pointer', fontSize: fontSize - 2, fontWeight: 600,
                background: 'transparent', color: sideTab === 'results' ? C.accent : C.textMuted,
                borderBottom: sideTab === 'results' ? `2px solid ${C.accent}` : '2px solid transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}><FileCode2 size={13} /> Results</button>
            </div>

            {sideTab === 'gantt' ? (
              <div style={{ flex: 1, overflowY: 'auto' }}>
                {/* Gantt */}
                <GanttView actions={actions} results={actionResults} fontSize={fontSize} />

                {/* Action blocks */}
                <div style={{ padding: '6px 16px 8px', borderTop: `1px solid ${C.border}` }}>
                  <div style={{ fontSize: fontSize - 2, fontWeight: 600, color: C.textDim, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Cpu size={12} /> Actions <span style={{ marginLeft: 'auto', fontSize: 10, color: C.textMuted }}>{actions.length}</span>
                  </div>
                  {actions.length === 0 && <div style={{ color: C.textMuted, fontSize: fontSize - 2, padding: 10, textAlign: 'center' }}>Waiting for commands...</div>}
                  {actions.map(a => {
                    const p = parseAction(a.raw);
                    const pillColor = p.action === 'pick' ? C.blue : p.action === 'place' ? C.yellow : p.action === 'go_home' ? C.green : C.textMuted;
                    return (
                      <div key={a.id} style={{ padding: '7px 10px', marginBottom: 4, borderRadius: 8, background: C.bgInput, fontSize: fontSize - 2 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                          <span style={{ padding: '1px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: pillColor + '22', color: pillColor, border: `1px solid ${pillColor}44` }}>{p.action.toUpperCase()}</span>
                          <span style={{ color: C.textMuted, fontSize: 10, marginLeft: 'auto' }}>{fmt(a.ts)}</span>
                        </div>
                        <div style={{ color: C.text, fontFamily: monoFont, fontSize: fontSize - 2 }}>{p.detail}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div style={{ flex: 1, overflowY: 'auto', padding: '10px 16px' }}>
                <div style={{ fontSize: fontSize - 2, fontWeight: 600, color: C.textDim, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Activity size={12} /> Results <span style={{ marginLeft: 'auto', fontSize: 10, color: C.textMuted }}>{actionResults.length}</span>
                </div>
                {actionResults.map(r => {
                  let success = false; try { success = JSON.parse(r.raw).success; } catch {}
                  return (
                    <div key={r.id} style={{
                      padding: '7px 10px', marginBottom: 4, borderRadius: 8, fontFamily: monoFont, fontSize: fontSize - 2,
                      background: success ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
                      border: `1px solid ${success ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)'}`,
                      color: success ? C.green : C.red,
                    }}>
                      {r.raw}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ════ Bottom Panel (Logs + Terminal) ════ */}
      <div style={{ borderTop: `1px solid ${C.border}`, background: C.bgSide }}>
        {/* Toggle bar */}
        <div onClick={() => setBottomOpen(!bottomOpen)} style={{
          padding: '5px 16px', display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', userSelect: 'none',
        }}>
          {bottomOpen ? <ChevronDown size={12} color={C.textMuted} /> : <ChevronUp size={12} color={C.textMuted} />}
          <Terminal size={12} color={C.textDim} />
          <span style={{ fontSize: 11, fontWeight: 600, color: C.textDim }}>Logs & Terminal</span>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: bringupRunning ? C.green : C.textMuted, marginLeft: 4 }} />
          <div style={{ flex: 1 }} />
          {bottomOpen && (
            <>
              <select value={minLogLevel} onChange={e => { e.stopPropagation(); setMinLogLevel(Number(e.target.value)); }}
                onClick={e => e.stopPropagation()}
                style={{ background: C.bgInput, color: C.textDim, border: `1px solid ${C.border}`, borderRadius: 4, padding: '1px 4px', fontSize: 10, outline: 'none', cursor: 'pointer' }}>
                <option value={10}>DEBUG+</option><option value={20}>INFO+</option><option value={30}>WARN+</option><option value={40}>ERR+</option>
              </select>
              <button onClick={(e) => { e.stopPropagation(); setLogAutoScroll(!logAutoScroll); }} style={{ ...btnSmall, background: logAutoScroll ? 'rgba(34,197,94,0.1)' : 'transparent', color: logAutoScroll ? C.green : C.textMuted, fontSize: 10, gap: 2 }}>
                {logAutoScroll ? <ChevronDown size={9} /> : <ChevronUp size={9} />}Auto
              </button>
            </>
          )}
        </div>

        {bottomOpen && (
          <div style={{ display: 'flex', height: 180, borderTop: `1px solid ${C.border}` }}>
            {/* ROS 2 Logs */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '4px 12px', fontFamily: monoFont, fontSize: fontSize - 2 }}>
              {filteredLogs.length === 0 && <div style={{ color: C.textMuted, padding: 12, textAlign: 'center', fontSize: 11 }}>Waiting for ROS 2 logs...</div>}
              {filteredLogs.map(l => (
                <div key={l.id} style={{ padding: '1px 0', display: 'flex', gap: 6, alignItems: 'flex-start', borderBottom: `1px solid ${C.border}22` }}>
                  <span style={{ color: C.textMuted, flexShrink: 0, width: 56, fontSize: 10 }}>{fmt(l.ts)}</span>
                  <span style={{ flexShrink: 0, width: 26, fontWeight: 700, fontSize: 10, color: LOG_COLORS[l.level] || C.textMuted }}>{LOG_LABELS[l.level] || '?'}</span>
                  <span style={{ flexShrink: 0, color: C.accent, width: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 10 }}>{l.name}</span>
                  <span style={{ color: l.level >= 30 ? LOG_COLORS[l.level] : C.text, wordBreak: 'break-word', fontSize: 11 }}>{stripAnsi(l.msg)}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>

            {/* Divider */}
            <div style={{ width: 1, background: C.border }} />

            {/* WSL Terminal */}
            <div style={{ width: '40%', overflowY: 'auto', padding: '4px 12px', fontFamily: monoFont, fontSize: 11, color: C.textDim }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: C.yellow, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 5 }}>
                <Terminal size={10} /> WSL2 Terminal
                <div style={{ flex: 1 }} />
                <button onClick={() => setTermLines([])} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: C.textMuted, padding: 0, display: 'flex' }}><Trash2 size={10} /></button>
              </div>
              {termLines.map((line, i) => (
                <div key={i} style={{
                  color: line.includes('[ERROR]') || line.includes('[stderr]') ? C.red :
                         line.includes('[WARN') ? C.yellow :
                         line.includes('[GUI]') || line.includes('[OK]') || line.includes('[LAUNCH]') ? C.green : C.textDim,
                }}>{stripAnsi(line)}</div>
              ))}
              <div ref={termEndRef} />
            </div>
          </div>
        )}
      </div>

      <style>{`::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#333;border-radius:3px}::-webkit-scrollbar-thumb:hover{background:#555}input::placeholder{color:${C.textMuted}}`}</style>
    </div>
  );
}

/* ── Shared button styles ───────────────────────────────── */
const btnSmall: React.CSSProperties = { width: 24, height: 24, borderRadius: 6, border: 'none', background: 'transparent', color: '#9ca3af', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const btnCtrl: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px', borderRadius: 8, cursor: 'pointer', border: '1px solid #2e2e2e', background: 'transparent', color: '#9ca3af', fontSize: 12, fontWeight: 600 };

export default App;
