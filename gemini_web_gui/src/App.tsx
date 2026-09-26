import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic, MicOff, Send, Bot, Wifi, WifiOff, Trash2,
  Terminal, ChevronDown, ChevronUp,
  Play, Square, RotateCcw, Plus, Minus, Wrench,
  PanelRightOpen, PanelRightClose, User,
  BarChart3, Network, Map, Clock, Sparkles,
} from 'lucide-react';
import { C, btnSmall, btnCtrl, monoFont, stripAnsi, fmt, LOG_COLORS, LOG_LABELS,
  type ChatMessage, type LogEntry, type RobotAction, type MetricsData } from './components/theme';
import KpiDashboard from './components/KpiDashboard';
import GanttChart from './components/GanttChart';
import SceneMap from './components/SceneMap';
import EventTrace from './components/EventTrace';
import { AgentWorkflowGraph } from './components/AgentWorkflowGraph';

const ROSLIB = (window as any).ROSLIB;
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
const API = 'http://localhost:3001';


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
  const [rightPanelWidth, setRightPanelWidth] = useState(55);
  const [activeRightTab, setActiveRightTab] = useState<'graph' | 'map' | 'gantt' | 'telemetry'>('graph');
  const isDragging = useRef(false);
  
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 0, role: 'system', text: 'Welcome to Gemini Robotics ER. Click **▶ Start** to launch the robot workspace, then type or speak a goal to begin.', ts: new Date() },
  ]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [actions, setActions] = useState<RobotAction[]>([]);
  const [actionResults, setActionResults] = useState<RobotAction[]>([]);
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
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

  const addMsg = useCallback((role: 'user'|'system'|'architect'|'vla', text: string, idOverride?: string | number, senderName?: string, emoji?: string) => {
    setMessages(p => {
      if (idOverride !== undefined) {
        const idx = p.findIndex(m => m.id === idOverride);
        if (idx >= 0) {
          const n = [...p];
          n[idx] = { ...n[idx], text: n[idx].text + text };
          if (senderName) n[idx].senderName = senderName;
          if (emoji) n[idx].emoji = emoji;
          if (role !== 'system') n[idx].role = role;
          return n;
        }
      }
      return [...p, { id: idOverride ?? seqRef.current++, role, text, ts: new Date(), senderName, emoji }];
    });
  }, []);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { if (logAutoScroll) logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs, logAutoScroll]);
  useEffect(() => { termEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [termLines]);

  /* ── Drag to Resize ───────────────────────────────────── */
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const newWidth = 100 - (e.clientX / window.innerWidth) * 100;
      setRightPanelWidth(Math.max(30, Math.min(newWidth, 70)));
    };
    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

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

        // Subscribe to chat replies from the VLA agent
        new ROSLIB.Topic({ ros: ros.current, name: '/gemini/chat_reply', messageType: 'std_msgs/String' })
          .subscribe((m: any) => {
            try {
              const obj = JSON.parse(m.data);
              if (obj.id && obj.text !== undefined) {
                addMsg(obj.role || 'system', obj.text, obj.id, obj.senderName, obj.emoji);
                return;
              }
            } catch (e) {}
            addMsg('system', m.data);
          });

        // NEW: Subscribe to robot metrics topic
        new ROSLIB.Topic({ ros: ros.current, name: '/multi_robot/robot_metrics', messageType: 'std_msgs/String' })
          .subscribe((m: any) => {
            try { setMetrics(JSON.parse(m.data)); } catch {}
          });
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
  const [bringupMode, setBringupMode] = useState(1);
  const startBringup = async () => { try { await fetch(`${API}/api/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: bringupMode }) }); setBringupRunning(true); } catch { addMsg('system', '❌ Backend unreachable.'); } };
  const stopBringup = async () => { try { await fetch(`${API}/api/stop`, { method: 'POST' }); setBringupRunning(false); } catch {} };
  const triggerBuild = async () => { try { await fetch(`${API}/api/build`, { method: 'POST' }); addMsg('system', '🔧 Build triggered. Check WSL terminal.'); } catch { addMsg('system', '❌ Backend unreachable.'); } };
  const resetSim = () => { if (!connected || !resetTopic.current) { addMsg('system', '⚠️ Not connected.'); return; } resetTopic.current.publish(new ROSLIB.Message({})); addMsg('system', '🔄 Simulation reset sent.'); };

  const filteredLogs = logs.filter(l => l.level >= minLogLevel);
  const renderMarkdown = (t: string) => t.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');


  /* ── Render ───────────────────────────────────────────── */
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: C.bg, fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif', color: C.text, fontSize }}>

      {/* ════ Top Bar ════ */}
      <div style={{ height: 50, padding: '0 16px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${C.border}`, background: 'rgba(13, 17, 26, 0.85)', backdropFilter: 'blur(16px)', flexShrink: 0 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, #0ea5e9, #38bdf8)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 15px rgba(56, 189, 248, 0.3)' }}><Bot size={17} color="#fff" /></div>
        <div>
          <span style={{ fontWeight: 800, color: C.white, fontSize: 14, letterSpacing: '-0.02em' }}>Gemini Robotics ER</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: -2 }}>
            <span style={{ fontSize: 9.5, color: '#38bdf8', fontWeight: 600, fontFamily: monoFont }}>VLA × FRANKA MULTI-ARM</span>
          </div>
        </div>
        <div style={{ width: 1, height: 22, background: C.border, margin: '0 4px' }} />
        <a href="https://blog.google/technology/google-deepmind/antigravity-ai-coding/" target="_blank" rel="noreferrer" title="Powered by Google Antigravity" style={{ display: 'flex', alignItems: 'center', gap: 6, textDecoration: 'none', padding: '3px 8px', borderRadius: 6, background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, transition: 'all 0.2s' }}>
          <img src="/antigravity.svg" alt="Antigravity" style={{ width: 18, height: 18 }} />
          <span style={{ fontSize: 10.5, color: C.textDim, fontWeight: 600 }}>Antigravity</span>
        </a>

        {/* Model Indicator Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 9px', borderRadius: 6, background: 'rgba(251, 191, 36, 0.1)', border: '1px solid rgba(251, 191, 36, 0.25)', color: '#fbbf24', fontSize: 10.5, fontWeight: 700 }}>
          <Sparkles size={12} />
          <span>Gemini 3.8-Flash (High Agility ⚡)</span>
        </div>

        <div style={{ flex: 1 }} />

        {/* Font size */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 3, background: 'rgba(0,0,0,0.2)', padding: '2px 4px', borderRadius: 6, border: `1px solid ${C.border}` }}>
          <button onClick={() => setFontSize(s => Math.max(10, s-1))} style={btnSmall}><Minus size={11} /></button>
          <span style={{ fontSize: 10, color: C.textMuted, width: 20, textAlign: 'center', fontFamily: monoFont }}>{fontSize}</span>
          <button onClick={() => setFontSize(s => Math.min(20, s+1))} style={btnSmall}><Plus size={11} /></button>
        </div>

        <div style={{ width: 1, height: 20, background: C.border, margin: '0 2px' }} />

        {/* Controls */}
        <button onClick={triggerBuild} style={{ ...btnCtrl, color: C.blue, background: 'rgba(56, 189, 248, 0.08)', borderColor: 'rgba(56, 189, 248, 0.2)' }}><Wrench size={13} /> Build</button>
        <select value={bringupMode} onChange={(e) => setBringupMode(parseInt(e.target.value))} style={{ ...btnCtrl, background: 'transparent', color: C.text, width: 90 }}>
          <option value={1}>Mode 1</option>
          <option value={7}>Mode 7 (Dual FR3)</option>
        </select>
        {!bringupRunning
          ? <button onClick={startBringup} style={{ ...btnCtrl, background: 'linear-gradient(135deg, #0ea5e9, #0284c7)', color: '#fff', border: 'none', boxShadow: '0 0 12px rgba(14, 165, 233, 0.35)' }}><Play size={13} /> Start</button>
          : <button onClick={stopBringup} style={{ ...btnCtrl, background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', border: 'none', boxShadow: '0 0 12px rgba(239, 68, 68, 0.35)' }}><Square size={13} /> Stop</button>
        }
        <button onClick={resetSim} style={{ ...btnCtrl, color: C.yellow, background: 'rgba(250, 204, 21, 0.08)', borderColor: 'rgba(250, 204, 21, 0.2)' }}><RotateCcw size={13} /> Reset</button>

        <div style={{ width: 1, height: 20, background: C.border, margin: '0 2px' }} />

        {/* Tower height badge */}
        {metrics && metrics.tower_height > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 8px', borderRadius: 6, background: 'rgba(14, 165, 233, 0.12)', border: '1px solid rgba(14, 165, 233, 0.3)', fontSize: 11, color: '#38bdf8', fontWeight: 700 }}>
            🏗️ {metrics.tower_height}/9
          </div>
        )}

        {/* ROS Connection Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 8px', borderRadius: 6, background: connected ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)', border: connected ? '1px solid rgba(34, 197, 94, 0.25)' : '1px solid rgba(239, 68, 68, 0.25)', fontSize: 11, color: connected ? C.green : C.red }}>
          {connected ? <Wifi size={12} color={C.green} /> : <WifiOff size={12} color={C.red} />}
          <span style={{ fontWeight: 600 }}>{connected ? 'ROS 2 Live' : 'Offline'}</span>
        </div>

        {/* Toggle side */}
        <button onClick={() => setSideOpen(!sideOpen)} style={{ ...btnSmall, marginLeft: 2 }}>
          {sideOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
        </button>
      </div>

      {/* ════ Main Body ════ */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* ── Chat Area (center) ──────────────────────── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'linear-gradient(180deg, #090c14 0%, #0d111a 100%)' }}>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
            <div style={{ maxWidth: 760, width: '100%', margin: '0 auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              {messages.map(m => {
                const isOrch = m.role === 'vla';
                const isArch = m.role === 'architect' && (m.senderName?.includes('Spatial') || m.emoji === '📐');
                const isOpt = m.role === 'architect' && (m.senderName?.includes('Performance') || m.emoji === '⚡');
                const isUser = m.role === 'user';
                
                const borderColor = isOrch ? '#38bdf8' : (isArch ? '#a78bfa' : (isOpt ? '#fbbf24' : (isUser ? 'rgba(148, 163, 184, 0.3)' : 'rgba(34, 197, 94, 0.3)')));
                const badgeBg = isOrch ? 'rgba(56, 189, 248, 0.15)' : (isArch ? 'rgba(167, 139, 250, 0.15)' : (isOpt ? 'rgba(251, 191, 36, 0.15)' : (isUser ? 'rgba(255,255,255,0.06)' : 'rgba(34, 197, 94, 0.15)')));
                const badgeColor = isOrch ? '#38bdf8' : (isArch ? '#a78bfa' : (isOpt ? '#fbbf24' : (isUser ? '#94a3b8' : '#22c55e')));

                return (
                  <div key={m.id} style={{
                    padding: '14px 16px',
                    borderRadius: 12,
                    background: 'rgba(15, 23, 42, 0.65)',
                    backdropFilter: 'blur(8px)',
                    border: `1px solid ${C.border}`,
                    borderLeft: `3px solid ${borderColor}`,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
                    display: 'flex', gap: 12, alignItems: 'flex-start',
                  }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                      background: badgeBg,
                      border: `1px solid ${borderColor}55`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {m.role === 'user' ? <User size={15} color="#94a3b8" /> : (m.emoji ? <span style={{ fontSize: 16, lineHeight: 1 }}>{m.emoji}</span> : <Bot size={15} color="#38bdf8" />)}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 12.5, fontWeight: 700, color: C.white }}>
                            {m.role === 'user' ? 'Human Operator' : (m.senderName || 'Gemini Robotics')}
                          </span>
                          <span style={{ fontSize: 9.5, padding: '1px 6px', borderRadius: 4, background: badgeBg, color: badgeColor, fontWeight: 600, fontFamily: monoFont }}>
                            {isUser ? 'USER' : (isOrch ? 'ORCHESTRATOR' : (isArch ? 'SPATIAL ARCHITECT' : (isOpt ? 'PERFORMANCE OPTIMIZER' : 'SYSTEM')))}
                          </span>
                        </div>
                        <span style={{ fontSize: 10, color: C.textMuted }}>{fmt(m.ts)}</span>
                      </div>
                      <div
                        style={{
                          fontSize: fontSize,
                          lineHeight: 1.6,
                          color: '#e2e8f0',
                          wordBreak: 'break-word',
                          whiteSpace: 'pre-wrap',
                          fontFamily: (m.role === 'architect' && m.text.includes('[')) ? monoFont : 'inherit',
                        }}
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }}
                      />
                    </div>
                  </div>
                );
              })}
              {messages.length === 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.textMuted, gap: 16 }}>
                  <div style={{ fontSize: 16, fontWeight: 600, color: C.white, marginTop: 40 }}>Welcome to Gemini Robotics ER</div>
                  <div style={{ fontSize: 13, maxWidth: 400, textAlign: 'center', lineHeight: 1.5 }}>
                    Multi-Agent Vision-Language-Action platform for 3 Franka FR3 manipulators.
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          </div>

          {/* Quick Prompts Bar */}
          <div style={{ padding: '6px 24px 0', display: 'flex', gap: 8, overflowX: 'auto', maxWidth: 760, width: '100%', margin: '0 auto' }}>
            {[
              { label: '⚡ Fast 9-Layer Tower', prompt: 'Build a 9-layer tower on the central target table using all blocks with maximum speed and concurrency.' },
              { label: '📐 3x3 Coplanar Grid', prompt: 'Arrange all 9 blocks into a 3x3 coplanar grid on the central target table centered at (0, 0).' },
              { label: '🔺 Triangle Pyramid', prompt: 'Arrange 6 blocks into a flat triangular formation on the central target table (3 in base, 2 in middle, 1 on top).' },
              { label: '🔄 Table 1 to 3 Relay', prompt: 'Transfer 2 blocks from Table 1 to Table 3 using the Central Target Table as a staging relay.' },
            ].map((qp, idx) => (
              <button
                key={idx}
                onClick={() => setText(qp.prompt)}
                style={{
                  padding: '4px 10px',
                  borderRadius: 20,
                  fontSize: 10.5,
                  fontWeight: 600,
                  color: '#94a3b8',
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: `1px solid ${C.border}`,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.color = '#38bdf8';
                  e.currentTarget.style.borderColor = 'rgba(56, 189, 248, 0.4)';
                  e.currentTarget.style.background = 'rgba(56, 189, 248, 0.08)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.color = '#94a3b8';
                  e.currentTarget.style.borderColor = C.border;
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                }}
              >
                {qp.label}
              </button>
            ))}
          </div>

          {/* Input Bar */}
          <div style={{ borderTop: `1px solid ${C.border}`, background: 'rgba(13, 17, 26, 0.85)', backdropFilter: 'blur(16px)', padding: '12px 24px' }}>
            <div style={{ maxWidth: 760, margin: '0 auto', display: 'flex', gap: 10, alignItems: 'center', background: 'rgba(22, 28, 43, 0.95)', borderRadius: 12, padding: '4px 6px 4px 16px', border: `1px solid ${C.borderHi}`, boxShadow: '0 4px 20px rgba(0,0,0,0.35)' }}>
              <button onClick={toggleMic} style={{
                width: 32, height: 32, borderRadius: '50%', border: 'none', cursor: 'pointer', flexShrink: 0,
                background: isRecording ? C.red : 'transparent', color: isRecording ? '#fff' : C.textMuted,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: isRecording ? `0 0 12px ${C.redGlow}` : 'none',
              }}>{isRecording ? <MicOff size={15} /> : <Mic size={15} />}</button>

              <input type="text" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendGoal()}
                placeholder={isRecording ? 'Listening...' : 'Send goal or shape command to multi-agent team...'}
                style={{ flex: 1, height: 38, border: 'none', background: 'transparent', color: C.white, fontSize: fontSize, outline: 'none' }}
              />

              <button onClick={sendGoal} disabled={!text.trim()} style={{
                width: 34, height: 34, borderRadius: 8, border: 'none', cursor: text.trim() ? 'pointer' : 'default', flexShrink: 0,
                background: text.trim() ? 'linear-gradient(135deg, #0ea5e9, #0284c7)' : 'transparent', color: text.trim() ? '#fff' : C.textMuted,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: text.trim() ? '0 0 10px rgba(14, 165, 233, 0.4)' : 'none',
                transition: 'all 0.15s',
              }}><Send size={14} /></button>
            </div>
            <div style={{ maxWidth: 760, margin: '6px auto 0', fontSize: 10.5, color: C.textMuted, textAlign: 'center' }}>
              Gemini Robotics-ER Orchestrator × Spatial Architect × Performance Optimizer
              {' · '}
              <a href="https://mincasurong.ai.studio/" target="_blank" rel="noreferrer" style={{ color: C.blue, textDecoration: 'none' }}>m9g</a>
              {' · '}
              <a href="https://blog.google/technology/google-deepmind/antigravity-ai-coding/" target="_blank" rel="noreferrer" style={{ color: C.textMuted, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 3, verticalAlign: 'middle' }}>
                <img src="/antigravity.svg" alt="" style={{ width: 12, height: 12, verticalAlign: 'middle' }} />
                Powered by Antigravity
              </a>
            </div>
          </div>
        </div>

        {/* ── Right Dashboard Panel & Divider ─────────────────── */}
        {sideOpen && (
          <div
            onMouseDown={() => {
              isDragging.current = true;
              document.body.style.cursor = 'col-resize';
              document.body.style.userSelect = 'none';
            }}
            style={{
              width: 5,
              cursor: 'col-resize',
              background: C.border,
              flexShrink: 0,
              zIndex: 10,
              transition: 'background 0.2s'
            }}
            onMouseOver={e => e.currentTarget.style.background = C.accent}
            onMouseOut={e => e.currentTarget.style.background = C.border}
          />
        )}
        {sideOpen && (
          <div style={{ width: `${rightPanelWidth}%`, background: C.bgSide, display: 'flex', flexDirection: 'column', flexShrink: 0, position: 'relative' }}>
            {/* Header with high-tech tab switcher */}
            <div style={{ padding: '8px 14px', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(15, 20, 32, 0.85)', backdropFilter: 'blur(10px)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <button
                  onClick={() => setActiveRightTab('graph')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 7,
                    fontSize: 11, fontWeight: 700, cursor: 'pointer',
                    background: activeRightTab === 'graph' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                    color: activeRightTab === 'graph' ? '#38bdf8' : C.textDim,
                    border: activeRightTab === 'graph' ? '1px solid rgba(56, 189, 248, 0.35)' : '1px solid transparent',
                  }}
                >
                  <Network size={12} />
                  <span>Workflow Graph</span>
                </button>

                <button
                  onClick={() => setActiveRightTab('map')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 7,
                    fontSize: 11, fontWeight: 700, cursor: 'pointer',
                    background: activeRightTab === 'map' ? 'rgba(167, 139, 250, 0.15)' : 'transparent',
                    color: activeRightTab === 'map' ? '#a78bfa' : C.textDim,
                    border: activeRightTab === 'map' ? '1px solid rgba(167, 139, 250, 0.35)' : '1px solid transparent',
                  }}
                >
                  <Map size={12} />
                  <span>2D Workspace</span>
                </button>

                <button
                  onClick={() => setActiveRightTab('gantt')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 7,
                    fontSize: 11, fontWeight: 700, cursor: 'pointer',
                    background: activeRightTab === 'gantt' ? 'rgba(34, 197, 94, 0.15)' : 'transparent',
                    color: activeRightTab === 'gantt' ? '#22c55e' : C.textDim,
                    border: activeRightTab === 'gantt' ? '1px solid rgba(34, 197, 94, 0.35)' : '1px solid transparent',
                  }}
                >
                  <Clock size={12} />
                  <span>Gantt</span>
                </button>

                <button
                  onClick={() => setActiveRightTab('telemetry')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 7,
                    fontSize: 11, fontWeight: 700, cursor: 'pointer',
                    background: activeRightTab === 'telemetry' ? 'rgba(251, 191, 36, 0.15)' : 'transparent',
                    color: activeRightTab === 'telemetry' ? '#fbbf24' : C.textDim,
                    border: activeRightTab === 'telemetry' ? '1px solid rgba(251, 191, 36, 0.35)' : '1px solid transparent',
                  }}
                >
                  <BarChart3 size={12} />
                  <span>KPIs & Trace</span>
                </button>
              </div>

              {/* Status pill on right of tab bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: C.textMuted }}>
                {metrics?.center_occupied_by ? (
                  <span style={{ padding: '2px 7px', borderRadius: 5, background: 'rgba(249, 115, 22, 0.15)', color: '#f97316', border: '1px solid rgba(249, 115, 22, 0.3)', fontWeight: 700 }}>
                    🔒 Mutex: {metrics.center_occupied_by}
                  </span>
                ) : (
                  <span style={{ padding: '2px 7px', borderRadius: 5, background: 'rgba(34, 197, 94, 0.12)', color: '#22c55e', border: '1px solid rgba(34, 197, 94, 0.25)', fontWeight: 600 }}>
                    🔓 Center Clear
                  </span>
                )}
              </div>
            </div>

            {/* Tab content */}
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
              {activeRightTab === 'graph' && (
                <AgentWorkflowGraph
                  metrics={metrics}
                  chatMessages={messages}
                  actions={actions}
                  userGoal={messages.filter(m => m.role === 'user').slice(-1)[0]?.text || 'Build a 9-layer tower on the central target table'}
                />
              )}

              {activeRightTab === 'map' && (
                <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
                  <SceneMap actions={actions} results={actionResults} metrics={metrics} fontSize={fontSize} />
                </div>
              )}

              {activeRightTab === 'gantt' && (
                <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
                  <GanttChart actions={actions} results={actionResults} metrics={metrics} fontSize={fontSize} />
                </div>
              )}

              {activeRightTab === 'telemetry' && (
                <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
                  <KpiDashboard metrics={metrics} fontSize={fontSize} />
                  <div style={{ borderTop: `1px solid ${C.border}`, flex: 1, minHeight: 320 }}>
                    <EventTrace actions={actions} results={actionResults} fontSize={fontSize} />
                  </div>
                </div>
              )}
            </div>
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

export default App;
