import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic, MicOff, Send, Bot, Wifi, WifiOff, Trash2,
  Terminal, ChevronDown, ChevronUp,
  Play, Square, RotateCcw, Plus, Minus, Wrench,
  PanelRightOpen, PanelRightClose, User,
  BarChart3,
} from 'lucide-react';
import { C, btnSmall, btnCtrl, monoFont, stripAnsi, fmt, LOG_COLORS, LOG_LABELS,
  type ChatMessage, type LogEntry, type RobotAction, type MetricsData } from './components/theme';
import KpiDashboard from './components/KpiDashboard';
import GanttChart from './components/GanttChart';
import SceneMap from './components/SceneMap';
import EventTrace from './components/EventTrace';

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
  const startBringup = async () => { try { await fetch(`${API}/api/start`, { method: 'POST' }); setBringupRunning(true); } catch { addMsg('system', '❌ Backend unreachable.'); } };
  const stopBringup = async () => { try { await fetch(`${API}/api/stop`, { method: 'POST' }); setBringupRunning(false); } catch {} };
  const triggerBuild = async () => { try { await fetch(`${API}/api/build`, { method: 'POST' }); addMsg('system', '🔧 Build triggered. Check WSL terminal.'); } catch { addMsg('system', '❌ Backend unreachable.'); } };
  const resetSim = () => { if (!connected || !resetTopic.current) { addMsg('system', '⚠️ Not connected.'); return; } resetTopic.current.publish(new ROSLIB.Message({})); addMsg('system', '🔄 Simulation reset sent.'); };

  const filteredLogs = logs.filter(l => l.level >= minLogLevel);
  const renderMarkdown = (t: string) => t.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');


  /* ── Render ───────────────────────────────────────────── */
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: C.bg, fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif', color: C.text, fontSize }}>

      {/* ════ Top Bar ════ */}
      <div style={{ height: 48, padding: '0 16px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${C.border}`, background: C.bgChat, flexShrink: 0 }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: C.accent, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Bot size={16} color="#fff" /></div>
        <span style={{ fontWeight: 700, color: C.white, fontSize: 15 }}>Gemini Robotics ER</span>

        <div style={{ flex: 1 }} />

        {/* Font size */}
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

        {/* Tower height badge */}
        {metrics && metrics.tower_height > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: C.accent, fontWeight: 700 }}>
            🏗️ {metrics.tower_height}/9
          </div>
        )}

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
                  padding: '20px 0', borderBottom: `1px solid ${C.border}`,
                  display: 'flex', gap: 14, alignItems: 'flex-start',
                }}>
                  <div style={{
                    width: 30, height: 30, borderRadius: 6, flexShrink: 0,
                    background: m.role === 'user' ? C.bgHover : (m.role === 'architect' ? C.purple : (m.role === 'vla' ? C.blue : C.accent)),
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {m.role === 'user' ? <User size={14} color={C.textDim} /> : (m.emoji ? <span style={{ fontSize: 16, lineHeight: 1 }}>{m.emoji}</span> : <Bot size={14} color="#fff" />)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: fontSize - 1, fontWeight: 700, color: C.white, marginBottom: 4 }}>
                      {m.role === 'user' ? 'You' : (m.senderName || 'Gemini Robotics')}
                    </div>
                    <div
                      style={{ fontSize: fontSize, lineHeight: 1.65, color: C.text, wordBreak: 'break-word' }}
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }}
                    />
                    <div style={{ fontSize: 10, color: C.textMuted, marginTop: 6 }}>{fmt(m.ts)}</div>
                  </div>
                </div>
              ))}
              {messages.length === 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.textMuted, gap: 16 }}>
                  <div style={{ fontSize: 16, fontWeight: 600, color: C.white, marginTop: 40 }}>Welcome to Gemini Robotics ER</div>
                  <div style={{ fontSize: 13, maxWidth: 400, textAlign: 'center', lineHeight: 1.5 }}>
                    I can orchestrate 3 Franka arms to build towers and organize objects. Try an example command:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8, width: '100%', maxWidth: 480 }}>
                    {[
                      "Build a 3-layer tower with the red cube as the base, green cylinder in the middle, and blue cube on top.",
                      "Move all the cubes to the center target table.",
                      "Stack the yellow cylinder and lime cube on top of the blue cube."
                    ].map((example, i) => (
                      <div key={i} onClick={() => setText(example)}
                           onMouseEnter={(e) => e.currentTarget.style.background = C.bgHover}
                           onMouseLeave={(e) => e.currentTarget.style.background = C.bgInput}
                           style={{ background: C.bgInput, padding: '12px 16px', borderRadius: 12, border: `1px solid ${C.border}`, fontSize: 13, color: C.text, cursor: 'pointer', transition: 'background 0.2s' }}>
                        {example}
                      </div>
                    ))}
                  </div>
                </div>
              )}
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
            <div style={{ maxWidth: 720, margin: '8px auto 0', fontSize: 11, color: C.textMuted, textAlign: 'center', lineHeight: 1.4 }}>
              Gemini Robotics ER controls 3 Franka FR3 arms via Isaac Sim.<br/>
              Made by <a href="https://mincasurong.ai.studio/" target="_blank" rel="noreferrer" style={{ color: C.blue, textDecoration: 'none' }}>m9g</a>
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
          <div style={{ width: `${rightPanelWidth}%`, background: C.bgSide, display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
            <div style={{ padding: '12px 16px', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', gap: 8, color: C.textDim, fontWeight: 600 }}>
              <BarChart3 size={14} /> System Monitoring Dashboard
            </div>
            
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <KpiDashboard metrics={metrics} fontSize={fontSize} />
                </div>
                <div style={{ flex: 1, minWidth: 0, borderLeft: `1px solid ${C.border}` }}>
                  <SceneMap actions={actions} results={actionResults} metrics={metrics} fontSize={fontSize} />
                </div>
              </div>
              <div style={{ borderTop: `1px solid ${C.border}` }}>
                <GanttChart actions={actions} results={actionResults} metrics={metrics} fontSize={fontSize} />
              </div>
              <div style={{ borderTop: `1px solid ${C.border}`, flex: 1, minHeight: 300, display: 'flex', flexDirection: 'column' }}>
                <EventTrace actions={actions} results={actionResults} fontSize={fontSize} />
              </div>
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
