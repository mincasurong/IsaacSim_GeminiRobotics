import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic, MicOff, Send, Bot, Trash2,
  Terminal, ChevronDown, ChevronUp,
  Play, Square, RotateCcw, User,
  BarChart3, Network, Map, Clock, Moon, Sun, Activity, Layers,
  Lock, Unlock,
} from 'lucide-react';
import { BACKEND_API, C, C_light, C_dark, btnSmall, btnCtrl, monoFont, stripAnsi, fmt, LOG_COLORS, LOG_LABELS,
  type ChatMessage, type LogEntry, type RobotAction, type MetricsData, type MonitoringSummary } from './components/theme';
import KpiDashboard from './components/KpiDashboard';
import GanttChart from './components/GanttChart';
import SceneMap from './components/SceneMap';
import EventTrace from './components/EventTrace';
import { AgentWorkflowGraph } from './components/AgentWorkflowGraph';
import SystemMonitor from './components/SystemMonitor';
import VisualWorkflowBuilder from './components/VisualWorkflowBuilder';
import OpeningPage from './components/OpeningPage';
import AuthPage, { type OperatorProfile } from './components/AuthPage';
import IntroPage from './components/IntroPage';

const ROSLIB = (window as any).ROSLIB;
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
const API = BACKEND_API;


/* ── Main App ───────────────────────────────────────────── */
function App() {
  // Theme state
  const [isDark, setIsDark] = useState(true);
  useEffect(() => {
    const t = isDark ? C_dark : C_light;
    for (const [k, v] of Object.entries(t)) {
      document.documentElement.style.setProperty(`--${k}`, v as string);
    }
  }, [isDark]);

  const [connected, setConnected] = useState(false);
  const [text, setText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [bringupRunning, setBringupRunning] = useState(false);
  const [termLines, setTermLines] = useState<string[]>([]);
  const [bottomOpen, setBottomOpen] = useState(false);
  const [pageStep, setPageStep] = useState<'opening' | 'auth' | 'intro' | 'main'>('opening');
  const [userProfile, setUserProfile] = useState<OperatorProfile | null>(() => {
    try {
      const saved = localStorage.getItem('isaac_operator_profile');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const fontSize = 14;
  const sideOpen = true;
  const [rightPanelWidth, setRightPanelWidth] = useState(55);
  const [activeRightTab, setActiveRightTab] = useState<'builder' | 'graph' | 'map' | 'gantt' | 'telemetry' | 'monitor'>('builder');
  const [executionMode, setExecutionMode] = useState<'flow' | 'vla'>('flow');
  const [flowGenTrigger, setFlowGenTrigger] = useState<{ text: string; seq: number } | null>(null);
  const [brainMode, setBrainMode] = useState<'argon_optimized' | 'gemini-4-argon' | 'gemini-robotics-er-2-preview' | 'compare_ab'>('argon_optimized');
  const [compMonitorOpen, setCompMonitorOpen] = useState(false);
  const [modelCompData, setModelCompData] = useState<any>({
    status_text: 'Send "Start comparison test" in Autonomous VLA mode to run the 3-stage benchmark (Mode 1: 9-Block Tower | Modes 2/3: Dual-Arm Blue LongBar).',
    comparison_rows: [],
  });
  const isDragging = useRef(false);
  const isVla = executionMode === 'vla';
  
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 0, role: 'system', text: 'Welcome to Physical AI with Isaac / Gemini. Click **▶ Start** to launch the robot workspace, then choose User-Defined Flow or Autonomous VLA.', ts: new Date() },
  ]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [actions, setActions] = useState<RobotAction[]>([]);
  const [actionResults, setActionResults] = useState<RobotAction[]>([]);
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [monitoringSummary, setMonitoringSummary] = useState<MonitoringSummary | null>(null);
  const [logAutoScroll, setLogAutoScroll] = useState(true);
  const [minLogLevel, setMinLogLevel] = useState(20);

  const ros = useRef<any>(null);
  const goalTopic = useRef<any>(null);
  const actionTopic = useRef<any>(null);
  const resetTopic = useRef<any>(null);
  const summarizeClient = useRef<any>(null);
  const recognition = useRef<any>(null);
  const pendingGoalRef = useRef<{ goal: string; brain_mode: string } | null>(null);
  const actionListenersRef = useRef<Array<{
    expectedRobot: string;
    expectedAction?: string;
    resolve: (res: { success: boolean; message: string }) => void;
  }>>([]);
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
    let reconnectTimeout: any = null;
    const scheduleReconnect = () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      reconnectTimeout = setTimeout(initROS, 3000);
    };
    const initROS = () => {
      const RosLib = (window as any).ROSLIB || ROSLIB;
      if (!RosLib) {
        scheduleReconnect();
        return;
      }
      try {
        ros.current = new RosLib.Ros({ url: 'ws://localhost:9090' });
      } catch {
        scheduleReconnect();
        return;
      }
      ros.current.on('connection', () => {
        setConnected(true);
        goalTopic.current = new RosLib.Topic({ ros: ros.current, name: '/gemini/custom_goal', messageType: 'std_msgs/String' });
        actionTopic.current = new RosLib.Topic({ ros: ros.current, name: '/gemini/action', messageType: 'std_msgs/String' });
        resetTopic.current = new RosLib.Topic({ ros: ros.current, name: '/reset_simulation', messageType: 'std_msgs/Empty' });
        new RosLib.Topic({ ros: ros.current, name: '/rosout', messageType: 'rcl_interfaces/Log' })
          .subscribe((m: any) => { setLogs(p => { const n = [...p, { id: seqRef.current++, level: m.level, name: m.name, msg: m.msg, ts: new Date() }]; return n.length > 500 ? n.slice(-500) : n; }); });
        new RosLib.Topic({ ros: ros.current, name: '/gemini/action', messageType: 'std_msgs/String' })
          .subscribe((m: any) => { setActions(p => { const n = [...p, { id: seqRef.current++, raw: m.data, ts: new Date() }]; return n.length > 100 ? n.slice(-100) : n; }); });
        new RosLib.Topic({ ros: ros.current, name: '/gemini/action_result', messageType: 'std_msgs/String' })
          .subscribe((m: any) => {
            try {
              const resObj = JSON.parse(m.data);
              const resRobot = String(resObj.robot_id || 'global');

              // Dispatch to matching active workflow listener
              const matchIdx = actionListenersRef.current.findIndex(l => {
                const exp = l.expectedRobot.toUpperCase();
                const res = resRobot.toUpperCase();
                if (exp === 'GLOBAL' || res === 'GLOBAL') return true;
                if ((exp.includes('1') || exp.includes('FR3_1')) && (res.includes('1') || res.includes('FR3_1'))) return true;
                if ((exp.includes('2') || exp.includes('FR3_2')) && (res.includes('2') || res.includes('FR3_2'))) return true;
                if ((exp.includes('3') || exp.includes('FR3_3')) && (res.includes('3') || res.includes('FR3_3'))) return true;
                return false;
              });

              if (matchIdx >= 0) {
                const [listener] = actionListenersRef.current.splice(matchIdx, 1);
                listener.resolve({
                  success: Boolean(resObj.success),
                  message: resObj.message || (resObj.success ? 'Success' : 'Execution failed'),
                });
              }
            } catch (e) {
              console.warn('[ROS] Error parsing action_result:', e);
            }

            setActionResults(p => { const n = [...p, { id: seqRef.current++, raw: m.data, ts: new Date() }]; return n.length > 100 ? n.slice(-100) : n; });
          });

        // Subscribe to chat replies from the VLA agent
        new RosLib.Topic({ ros: ros.current, name: '/gemini/chat_reply', messageType: 'std_msgs/String' })
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

        // Subscribe to robot metrics topic
        new RosLib.Topic({ ros: ros.current, name: '/multi_robot/robot_metrics', messageType: 'std_msgs/String' })
          .subscribe((m: any) => {
            try { setMetrics(JSON.parse(m.data)); } catch {}
          });

        // Subscribe to monitoring summary
        new RosLib.Topic({ ros: ros.current, name: '/gemini/monitoring_summary', messageType: 'std_msgs/String' })
          .subscribe((m: any) => {
            try { setMonitoringSummary(JSON.parse(m.data)); } catch {}
          });

        new RosLib.Topic({ ros: ros.current, name: '/gemini/model_comparison', messageType: 'std_msgs/String' })
          .subscribe((m: any) => {
            try {
              const parsed = JSON.parse(m.data);
              if (Array.isArray(parsed.comparison_rows) && parsed.comparison_rows.length > 0) {
                setCompMonitorOpen(true);
              }
              setModelCompData((prev: any) => ({
                ...prev,
                ...parsed,
                status_text: parsed.status_text || prev.status_text,
                comparison_rows: Array.isArray(parsed.comparison_rows) ? parsed.comparison_rows : prev.comparison_rows,
              }));
            } catch {}
          });

        summarizeClient.current = new RosLib.Service({
          ros: ros.current,
          name: '/gemini/summarize_logs',
          serviceType: 'std_srvs/Trigger'
        });

        if (pendingGoalRef.current && goalTopic.current) {
          const queued = pendingGoalRef.current;
          pendingGoalRef.current = null;
          goalTopic.current.publish(new RosLib.Message({ data: JSON.stringify(queued) }));
          addMsg('system', `✅ Connected to ROS 2 — dispatched queued goal to VLA (${queued.brain_mode}).`);
        }
      });
      ros.current.on('error', () => setConnected(false));
      ros.current.on('close', () => { setConnected(false); scheduleReconnect(); });
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
    return () => { if (reconnectTimeout) clearTimeout(reconnectTimeout); ros.current?.close(); recognition.current?.stop(); };
  }, []);

  const quickPromptsByMode: Record<number, Array<{ label: string; prompt: string }>> = {
    1: [
      { label: '⚖️ Start Comparison Test', prompt: 'Start comparison test' },
      { label: '⚡ Fast 9-Layer Tower', prompt: 'Build a 9-layer tower on the central target table using all blocks with maximum speed and concurrency.' },
      { label: '📐 3x3 Coplanar Grid', prompt: 'Arrange all 9 blocks into a 3x3 coplanar grid on the central target table centered at (0, 0).' },
      { label: '🔺 Triangle Pyramid', prompt: 'Arrange 6 blocks into a flat triangular formation on the central target table (3 in base, 2 in middle, 1 on top).' },
      { label: '🔄 Table 1 to 3 Relay', prompt: 'Transfer 2 blocks from Table 1 to Table 3 using the Central Target Table as a staging relay.' },
    ],
    2: [
      { label: '🎯 50Hz Conveyor Follow & Pick', prompt: 'Follow and pick moving objects from the conveyor belt in real time with FR3_1 and FR3_2 and place them onto the workbench.' },
      { label: '⚖️ Start Bar Comparison Test', prompt: 'Start comparison test' },
      { label: '🌊 Dual-Arm Pick & Wave Circle', prompt: 'Pick the LongBar with both arms, lift it, and execute a synchronized circular wave in the XY plane.' },
      { label: '🔄 Dual-Arm Circle (YZ Plane)', prompt: 'Pick the LongBar and synchronously draw a vertical circle in the YZ plane with 2 complete cycles.' },
    ],
    3: [
      { label: '🧺 Pack Balls & Cubes into Flexible Basket', prompt: 'Pick RedBall, YellowBall, Block1, and Block2 with FR3_1 and FR3_2, pack them into the FlexibleBasket at (0.0, -0.25), and lift the FlexibleBasket with both arms.' },
      { label: '⚖️ Start Bar Comparison Test', prompt: 'Start comparison test' },
      { label: '🛠️ Sub-Assembly Sequence', prompt: 'Perform cooperative assembly: FR3_1 holds the LongBar while FR3_2 fastens the HeavyEnginePart at the central station.' },
      { label: '📐 Precision Bar Insertion', prompt: 'Grasp the LongBar jointly and perform high-precision compliance insertion at the target jig coordinates.' },
    ],
    5: [
      { label: '⚖️ Start Bar Comparison Test', prompt: 'Start comparison test' },
      { label: '🌊 Dual-Arm Pick & Wave Circle', prompt: 'Pick the LongBar with both arms, lift it, and execute a synchronized circular wave in the XY plane.' },
      { label: '🎯 Conveyor Dynamic Intercept', prompt: 'Track and pick moving items from the conveyor belt with the nearest arm and place them onto the workbench.' },
      { label: '🔄 Dual-Arm Circle (YZ Plane)', prompt: 'Pick the LongBar and synchronously draw a vertical circle in the YZ plane with 2 complete cycles.' },
      { label: '🤝 Asymmetric Engine Pick', prompt: 'Coordinate FR3_1 and FR3_2 to pick the HeavyEnginePart using asymmetric grasp offsets and place it on the workbench.' },
    ],
    6: [
      { label: '⚖️ Start Bar Comparison Test', prompt: 'Start comparison test' },
      { label: '🛠️ Sub-Assembly Sequence', prompt: 'Perform cooperative assembly: FR3_1 holds the LongBar while FR3_2 fastens the HeavyEnginePart at the central station.' },
      { label: '📐 Precision Bar Insertion', prompt: 'Grasp the LongBar jointly and perform high-precision compliance insertion at the target jig coordinates.' },
      { label: '🔄 Dual-Arm Handoff & Tool Swap', prompt: 'Pick the bar with FR3_1, transfer it to FR3_2 at the handoff station, then return FR3_1 to home.' },
      { label: '⚡ Agile Bi-Manual Sort', prompt: 'Sort all components on the assembly table by assigning heavy parts to dual-arm grasp and standard blocks to single arms.' },
    ],
  };

  /* ── Handlers ─────────────────────────────────────────── */
  const toggleMic = () => { if (!recognition.current) { alert('Chrome/Edge only'); return; } if (isRecording) { recognition.current.stop(); setIsRecording(false); } else { setText(''); recognition.current.start(); setIsRecording(true); } };
  const sendGoal = (overrideText?: string) => {
    const goalStr = (overrideText !== undefined ? overrideText : text).trim();
    if (!goalStr) return;
    const isCompCmd = goalStr.toLowerCase().includes('comparison test') || goalStr.toLowerCase().includes('compare model');
    if (!isCompCmd && executionMode === 'flow') {
      addMsg('user', goalStr);
      setActiveRightTab('builder');
      setFlowGenTrigger(prev => ({ text: goalStr, seq: (prev?.seq || 0) + 1 }));
      if (overrideText === undefined) setText('');
      return;
    }
    if (isCompCmd && executionMode !== 'vla') {
      setExecutionMode('vla');
    }
    const effectiveBrain = isCompCmd ? 'compare_ab' : brainMode;
    if (!connected || !goalTopic.current) {
      addMsg('user', goalStr);
      pendingGoalRef.current = { goal: goalStr, brain_mode: effectiveBrain };
      addMsg('system', `⏳ Connecting to WSL2 ROS 2 (Mode ${bringupMode}) and queuing goal...`);
      startBringup();
      if (overrideText === undefined) setText('');
      return;
    }
    addMsg('user', goalStr);
    const payload = JSON.stringify({ goal: goalStr, brain_mode: effectiveBrain });
    const RosLib = (window as any).ROSLIB || ROSLIB;
    goalTopic.current.publish(new RosLib.Message({ data: payload }));
    addMsg('system', `✅ Goal sent to VLA (${effectiveBrain}).`);
    if (overrideText === undefined) setText('');
  };
  const [bringupMode, setBringupMode] = useState(1);
  const startAutomatedComparisonTest = () => {
    setExecutionMode('vla');
    setCompMonitorOpen(true);
    sendGoal('Start comparison test');
  };
  const startBringup = async () => { try { await fetch(`${API}/api/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: bringupMode }) }); setBringupRunning(true); } catch { addMsg('system', '❌ Backend unreachable.'); } };
  const stopBringup = async () => { try { await fetch(`${API}/api/stop`, { method: 'POST' }); setBringupRunning(false); } catch {} };
  const resetSim = () => { if (!connected || !resetTopic.current) { addMsg('system', '⚠️ Not connected.'); return; } resetTopic.current.publish(new ROSLIB.Message({})); addMsg('system', '🔄 Simulation reset sent.'); };
  const triggerAudit = () => {
    if (!connected || !summarizeClient.current) { addMsg('system', '⚠️ Not connected.'); return; }
    addMsg('system', '⚡ Requesting AI Diagnostic Audit...');
    summarizeClient.current.callService(new ROSLIB.ServiceRequest({}), (res: any) => {
      if (res.success) addMsg('system', `✅ Audit complete: ${res.message}`);
      else addMsg('system', `❌ Audit failed: ${res.message}`);
    });
  };

  const executeWorkflowActionAsync = useCallback((actionMsg: any): Promise<{ success: boolean; message: string }> => {
    return new Promise((resolve) => {
      if (!ros.current || !connected) {
        resolve({ success: false, message: 'ROS 2 Bridge offline' });
        return;
      }

      const robotKey = String(actionMsg.robot || 'global');
      let timeoutTimer: any = null;

      const listenerEntry = {
        expectedRobot: robotKey,
        expectedAction: actionMsg.action,
        resolve: (val: any) => {
          if (timeoutTimer) clearTimeout(timeoutTimer);
          resolve(val);
        },
      };

      // 40-second safety timeout
      timeoutTimer = setTimeout(() => {
        const idx = actionListenersRef.current.indexOf(listenerEntry);
        if (idx >= 0) actionListenersRef.current.splice(idx, 1);
        console.warn(`[WORKFLOW] Action timed out for robot ${robotKey}`);
        resolve({ success: false, message: 'Action execution timed out (40s)' });
      }, 40000);

      actionListenersRef.current.push(listenerEntry);

      // Publish action command to ROS 2
      if (actionTopic.current) {
        actionTopic.current.publish(new ROSLIB.Message({ data: JSON.stringify(actionMsg) }));
      } else {
        const topic = new ROSLIB.Topic({ ros: ros.current, name: '/gemini/action', messageType: 'std_msgs/String' });
        topic.publish(new ROSLIB.Message({ data: JSON.stringify(actionMsg) }));
      }
    });
  }, [connected]);

  const filteredLogs = logs.filter(l => l.level >= minLogLevel);
  const renderMarkdown = (t: string) => t.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');


  if (pageStep === 'opening') {
    return <OpeningPage onNext={() => setPageStep('auth')} />;
  }

  if (pageStep === 'auth') {
    return (
      <AuthPage
        userProfile={userProfile}
        onLoginSuccess={(profile) => {
          setUserProfile(profile);
          setPageStep('intro');
        }}
        onContinueGuest={() => setPageStep('intro')}
        onContinueLoggedIn={() => setPageStep('intro')}
        onBack={() => setPageStep('opening')}
      />
    );
  }

  if (pageStep === 'intro') {
    return (
      <IntroPage
        bringupMode={bringupMode}
        setBringupMode={setBringupMode}
        executionMode={executionMode}
        setExecutionMode={(m) => {
          setExecutionMode(m);
          setActiveRightTab(m === 'flow' ? 'builder' : 'graph');
        }}
        onEnterMain={() => setPageStep('main')}
        onStartComparisonNow={() => {
          setExecutionMode('vla');
          setActiveRightTab('graph');
          setPageStep('main');
          setTimeout(() => startAutomatedComparisonTest(), 150);
        }}
        onBack={() => setPageStep('auth')}
      />
    );
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: isDark ? 'radial-gradient(ellipse at 50% -20%, #18181b, #09090b 80%)' : C.bg, fontFamily: "var(--font-sans, 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif)", color: C.text, fontSize }}>

      <div style={{ height: 48, padding: '0 16px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : C.border}`, background: C.glassBg, backdropFilter: 'blur(20px)', flexShrink: 0, zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: isDark ? 'linear-gradient(135deg, #a855f7, #6366f1)' : '#111', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 10px rgba(168, 85, 247, 0.35)' }}>
            <Bot size={15} color="#fff" />
          </div>
          <span style={{ fontWeight: 800, color: C.white, fontSize: 13.5, letterSpacing: '-0.02em' }}>IsaacSim × Gemini</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(0,0,0,0.28)', borderRadius: 8, border: `1px solid ${C.border}`, padding: 2 }}>
          {([
            { id: 'opening', label: '1. Opening' },
            { id: 'auth', label: '2. Auth' },
            { id: 'intro', label: '3. Intro' },
            { id: 'main', label: '4. Studio' },
          ] as const).map((st) => (
            <button
              key={st.id}
              onClick={() => setPageStep(st.id)}
              style={{
                padding: '3px 8px',
                borderRadius: 6,
                border: 'none',
                cursor: 'pointer',
                fontSize: 10.5,
                fontWeight: 700,
                background: pageStep === st.id ? 'rgba(250, 204, 21, 0.2)' : 'transparent',
                color: pageStep === st.id ? '#fbbf24' : C.textDim,
              }}
            >
              {st.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(0,0,0,0.3)', borderRadius: 8, border: `1px solid ${C.border}`, padding: 2 }}>
          <button
            onClick={() => { setExecutionMode('flow'); setActiveRightTab('builder'); }}
            style={{
              padding: '3px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 10.5, fontWeight: 700,
              background: executionMode === 'flow' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
              color: executionMode === 'flow' ? '#38bdf8' : C.textDim,
              transition: 'all 0.15s',
            }}
          >
            🧩 User-Defined Flow
          </button>
          <button
            onClick={() => { setExecutionMode('vla'); setActiveRightTab('graph'); }}
            style={{
              padding: '3px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 10.5, fontWeight: 700,
              background: executionMode === 'vla' ? 'rgba(168, 85, 247, 0.22)' : 'transparent',
              color: executionMode === 'vla' ? '#c084fc' : C.textDim,
              transition: 'all 0.15s',
            }}
          >
            🧠 Autonomous VLA
          </button>
        </div>

        <div style={{ flex: 1 }} />

        <select
          value={bringupMode}
          onChange={(e) => setBringupMode(parseInt(e.target.value))}
          style={{
            ...btnCtrl,
            background: 'rgba(0,0,0,0.28)',
            color: C.text,
            width: 155,
            height: 28,
            fontSize: 11,
            borderRadius: 6,
            border: `1px solid ${C.border}`,
          }}
        >
          <option value={1}>Mode 1: Tower (Outline)</option>
          <option value={2}>Mode 2: Conveyor & Bar</option>
          <option value={3}>Mode 3: Assembly (ATAMP)</option>
        </select>

        {executionMode === 'vla' && (
          <select
            value={brainMode}
            onChange={(e) => setBrainMode(e.target.value as any)}
            title="Select VLA Brain Architecture"
            style={{
              ...btnCtrl,
              background: brainMode === 'compare_ab' ? 'rgba(168, 85, 247, 0.18)' : 'rgba(0,0,0,0.28)',
              color: brainMode === 'compare_ab' ? '#d8b4fe' : C.text,
              width: 205,
              height: 28,
              fontSize: 11,
              borderRadius: 6,
              border: `1px solid ${brainMode === 'compare_ab' ? '#a855f7' : C.border}`,
            }}
          >
            <option value="argon_optimized">⚡ Argon Brain + Flash-Lite</option>
            <option value="gemini-4-argon">🦾 Gemini-4-Argon Only</option>
            <option value="gemini-robotics-er-2-preview">🤖 Gemini Robotics-ER 2</option>
            <option value="compare_ab">⚖️ 3-Stage Auto Compare</option>
          </select>
        )}

        {/* Start / Stop Bringup */}
        {!bringupRunning ? (
          <button
            onClick={startBringup}
            style={{
              ...btnCtrl,
              height: 28,
              padding: '0 12px',
              background: 'linear-gradient(135deg, #10b981, #059669)',
              color: '#fff',
              border: 'none',
              fontWeight: 700,
              fontSize: 11,
              borderRadius: 6,
              boxShadow: '0 2px 8px rgba(16, 185, 129, 0.35)',
            }}
          >
            <Play size={12} fill="#fff" /> Start
          </button>
        ) : (
          <button
            onClick={stopBringup}
            style={{
              ...btnCtrl,
              height: 28,
              padding: '0 12px',
              background: 'linear-gradient(135deg, #ef4444, #dc2626)',
              color: '#fff',
              border: 'none',
              fontWeight: 700,
              fontSize: 11,
              borderRadius: 6,
              boxShadow: '0 2px 8px rgba(239, 68, 68, 0.35)',
            }}
          >
            <Square size={12} fill="#fff" /> Stop
          </button>
        )}

        {/* Reset Sim Button */}
        <button
          onClick={resetSim}
          style={{
            ...btnCtrl,
            height: 28,
            padding: '0 9px',
            color: C.yellow,
            background: 'rgba(250, 204, 21, 0.08)',
            borderColor: 'rgba(250, 204, 21, 0.25)',
            fontSize: 11,
            borderRadius: 6,
          }}
          title="Reset simulation objects"
        >
          <RotateCcw size={12} /> Reset
        </button>

        {/* Tower Height Badge */}
        {metrics && metrics.tower_height > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 6, background: 'rgba(14, 165, 233, 0.14)', border: '1px solid rgba(14, 165, 233, 0.32)', fontSize: 10.5, color: '#38bdf8', fontWeight: 700 }}>
            🏗️ {metrics.tower_height}/9
          </div>
        )}

        {/* ROS 2 Status Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '3px 8px',
            borderRadius: 6,
            background: connected ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
            border: connected ? '1px solid rgba(34, 197, 94, 0.28)' : '1px solid rgba(239, 68, 68, 0.28)',
            fontSize: 10.5,
            color: connected ? C.green : C.red,
            fontWeight: 600,
          }}
        >
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: connected ? C.green : C.red, boxShadow: connected ? `0 0 6px ${C.green}` : 'none' }} />
          <span>{connected ? 'ROS 2' : 'Offline'}</span>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={() => setIsDark(!isDark)}
          style={{ ...btnSmall, border: `1px solid ${C.border}`, width: 28, height: 28, borderRadius: 6 }}
          title="Toggle light/dark theme"
        >
          {isDark ? <Sun size={13} color={C.yellow} /> : <Moon size={13} color={C.textDim} />}
        </button>
      </div>

      {/* ════ Main Body ════ */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* ── Chat Area (center) ──────────────────────── */}
        <div style={{
          flex: 1,
          display: isVla ? 'flex' : 'none',
          flexDirection: 'column',
          minWidth: 0,
          background: C.bgChat
        }}>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
            <div style={{ maxWidth: 760, width: '100%', margin: '0 auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              {messages.map(m => {
                const isOrch = m.role === 'vla';
                const isGen = m.role === 'generator' || m.senderName?.includes('Generator') || m.emoji === '📋';
                const isVerif = m.role === 'verifier' || m.senderName?.includes('Verifier') || m.emoji === '🛡️';
                const isArch = m.role === 'architect' && (m.senderName?.includes('Spatial') || m.emoji === '📐');
                const isOpt = m.role === 'architect' && (m.senderName?.includes('Performance') || m.emoji === '⚡');
                const isUser = m.role === 'user';
                
                const borderColor = isOrch ? '#38bdf8' : (isGen ? '#10b981' : (isVerif ? '#a855f7' : (isArch ? '#a78bfa' : (isOpt ? '#fbbf24' : (isUser ? 'rgba(148, 163, 184, 0.3)' : 'rgba(34, 197, 94, 0.3)')))));
                const badgeBg = isOrch ? 'rgba(56, 189, 248, 0.15)' : (isGen ? 'rgba(16, 185, 129, 0.15)' : (isVerif ? 'rgba(168, 85, 247, 0.15)' : (isArch ? 'rgba(167, 139, 250, 0.15)' : (isOpt ? 'rgba(251, 191, 36, 0.15)' : (isUser ? 'rgba(255,255,255,0.06)' : 'rgba(34, 197, 94, 0.15)')))));
                const badgeColor = isOrch ? '#38bdf8' : (isGen ? '#10b981' : (isVerif ? '#a855f7' : (isArch ? '#a78bfa' : (isOpt ? '#fbbf24' : (isUser ? '#94a3b8' : '#22c55e')))));

                return (
                  <div key={m.id} style={{
                    padding: '14px 16px',
                    borderRadius: 12,
                    background: C.glassBg,
                    backdropFilter: 'blur(12px)',
                    border: `1px solid ${C.border}`,
                    borderLeft: `3px solid ${borderColor}`,
                    boxShadow: '0 4px 18px rgba(0,0,0,0.28)',
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
                            {isUser ? 'USER' : (isOrch ? 'VLA BRAIN' : (isGen ? 'TASK GENERATOR' : (isVerif ? 'SAFETY VERIFIER' : (isArch ? 'SPATIAL ARCHITECT' : (isOpt ? 'PERFORMANCE OPTIMIZER' : 'SYSTEM')))))}
                          </span>
                        </div>
                        <span style={{ fontSize: 10, color: C.textMuted }}>{fmt(m.ts)}</span>
                      </div>
                      <div
                        style={{
                          fontSize: fontSize,
                          lineHeight: 1.6,
                          color: C.text,
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
                  <div style={{ fontSize: 16, fontWeight: 600, color: C.white, marginTop: 40 }}>Welcome to Physical AI with Isaac / Gemini</div>
                  <div style={{ fontSize: 13, maxWidth: 400, textAlign: 'center', lineHeight: 1.5 }}>
                    Multi-Agent Vision-Language-Action platform for 3 Franka FR3 manipulators.
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          </div>

          {/* Quick Prompts Bar (Dynamically adapts to Mode 1, 5, or 6) */}
          <div style={{ padding: '6px 24px 0', display: 'flex', gap: 8, overflowX: 'auto', maxWidth: 760, width: '100%', margin: '0 auto' }}>
            {(quickPromptsByMode[bringupMode] || quickPromptsByMode[1]).map((qp, idx) => (
              <button
                key={idx}
                onClick={() => setText(qp.prompt)}
                style={{
                  padding: '4px 10px',
                  borderRadius: 20,
                  fontSize: 10.5,
                  fontWeight: 600,
                  color: C.textDim,
                  background: C.bgInput,
                  border: `1px solid ${C.border}`,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.color = C.text;
                  e.currentTarget.style.borderColor = C.borderHi;
                  e.currentTarget.style.background = C.bgHover;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.color = C.textDim;
                  e.currentTarget.style.borderColor = C.border;
                  e.currentTarget.style.background = C.bgInput;
                }}
              >
                {qp.label}
              </button>
            ))}
          </div>

          {/* Input Bar */}
          <div style={{ borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : C.border}`, background: isDark ? 'rgba(9, 9, 11, 0.75)' : C.glassBg, backdropFilter: 'blur(24px) saturate(180%)', padding: '16px 24px', zIndex: 10 }}>
            <div style={{ maxWidth: 760, margin: '0 auto', display: 'flex', gap: 10, alignItems: 'center', background: isDark ? 'rgba(255, 255, 255, 0.03)' : C.bgInput, borderRadius: 16, padding: '6px 8px 6px 18px', border: `1px solid ${isDark ? 'rgba(255, 255, 255, 0.1)' : C.borderHi}`, boxShadow: isDark ? '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)' : '0 4px 20px rgba(0,0,0,0.1)' }}>
              <button onClick={toggleMic} style={{
                width: 32, height: 32, borderRadius: '50%', border: 'none', cursor: 'pointer', flexShrink: 0,
                background: isRecording ? C.red : 'transparent', color: isRecording ? '#fff' : C.textMuted,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: isRecording ? `0 0 12px ${C.redGlow}` : 'none',
              }}>{isRecording ? <MicOff size={15} /> : <Mic size={15} />}</button>

              <input type="text" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendGoal()}
                placeholder={isRecording ? 'Listening...' : ((bringupMode === 2 || bringupMode === 5) ? 'Send dual-arm LongBar or conveyor pick-place directive...' : ((bringupMode === 3 || bringupMode === 6) ? 'Send ATAMP cooperative assembly directive...' : 'Send task directive to Gemini-4-Argon VLA...'))}
                style={{ flex: 1, height: 38, border: 'none', background: 'transparent', color: C.white, fontSize: fontSize, outline: 'none' }}
              />

              <button onClick={() => sendGoal()} disabled={!text.trim()} style={{
                width: 34, height: 34, borderRadius: 8, border: 'none', cursor: text.trim() ? 'pointer' : 'default', flexShrink: 0,
                background: text.trim() ? C.text : 'transparent', color: text.trim() ? C.bg : C.textMuted,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: 'none',
                transition: 'all 0.15s',
              }}><Send size={14} /></button>
            </div>
            <div style={{ maxWidth: 760, margin: '6px auto 0', fontSize: 10.5, color: C.textMuted, textAlign: 'center' }}>
              Rule-Based Task Generator × Gemini-4-Argon VLA Brain × Rule-Based Safety Verifier
            </div>
          </div>
        </div>

        {/* ── Right Dashboard Panel & Divider ─────────────────── */}
        {sideOpen && isVla && (
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
          <div style={{
            width: isVla ? `${rightPanelWidth}%` : '100%',
            flex: isVla ? undefined : 1,
            background: C.bgSide,
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
            position: 'relative'
          }}>
            {/* Header with high-tech tab switcher */}
            <div style={{ padding: '8px 14px', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: C.glassBg, backdropFilter: 'blur(10px)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {executionMode === 'flow' ? (
                  <button
                    onClick={() => setActiveRightTab('builder')}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 7,
                      fontSize: 11, fontWeight: 700, cursor: 'pointer',
                      background: activeRightTab === 'builder' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                      color: activeRightTab === 'builder' ? '#38bdf8' : C.textDim,
                      border: activeRightTab === 'builder' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
                    }}
                  >
                    <Layers size={12} />
                    <span>Task Blocks</span>
                  </button>
                ) : (
                  <button
                    onClick={() => setActiveRightTab('graph')}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 7,
                      fontSize: 11, fontWeight: 700, cursor: 'pointer',
                      background: activeRightTab === 'graph' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                      color: activeRightTab === 'graph' ? '#d46a43' : C.textDim,
                      border: activeRightTab === 'graph' ? '1px solid rgba(56, 189, 248, 0.35)' : '1px solid transparent',
                    }}
                  >
                    <Network size={12} />
                    <span>Workflow Graph</span>
                  </button>
                )}

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

                <button
                  onClick={() => setActiveRightTab('monitor')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 7,
                    fontSize: 11, fontWeight: 700, cursor: 'pointer',
                    background: activeRightTab === 'monitor' ? 'rgba(236, 72, 153, 0.15)' : 'transparent',
                    color: activeRightTab === 'monitor' ? '#ec4899' : C.textDim,
                    border: activeRightTab === 'monitor' ? '1px solid rgba(236, 72, 153, 0.35)' : '1px solid transparent',
                  }}
                >
                  <Activity size={12} />
                  <span>AI Monitor</span>
                </button>
              </div>

              {/* Status pill on right of tab bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: C.textMuted }}>
                {metrics?.center_occupied_by ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 5, background: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.25)', fontWeight: 600 }}>
                    <Lock size={10} /> Mutex: {metrics.center_occupied_by}
                  </span>
                ) : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 5, background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.22)', fontWeight: 600 }}>
                    <Unlock size={10} /> Center Clear
                  </span>
                )}
              </div>
            </div>

            {/* Tab content */}
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
              {/* Task Blocks (Flow) - Kept mounted to preserve user graph and node edits across tab switches */}
              <div style={{ flex: 1, minHeight: 0, display: activeRightTab === 'builder' ? 'flex' : 'none', flexDirection: 'column' }}>
                <VisualWorkflowBuilder
                  onPublishAction={executeWorkflowActionAsync}
                  mode={bringupMode}
                  externalPrompt={flowGenTrigger}
                  onFlowGenerated={(summary) => addMsg('vla', summary, undefined, 'Gemini-4-Argon Workflow Architect', '🧩')}
                />
              </div>

              {activeRightTab === 'graph' && (
                <AgentWorkflowGraph
                  metrics={metrics}
                  chatMessages={messages}
                  actions={actions}
                  results={actionResults}
                  userGoal={messages.filter(m => m.role === 'user').slice(-1)[0]?.text || ((bringupMode === 2 || bringupMode === 5) ? 'Pick LongBar or items from conveyor' : ((bringupMode === 3 || bringupMode === 6) ? 'Assemble components (ATAMP)' : 'Build a 9-layer tower on the central target table'))}
                  mode={bringupMode}
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

              {activeRightTab === 'monitor' && (
                <div style={{ flex: 1, overflowY: 'auto' }}>
                  <SystemMonitor summary={monitoringSummary} onTriggerAudit={triggerAudit} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ════ Text-Based Model & Cost Monitor (Modes 1, 2 & 3 — Above Logs & Terminal) ════ */}
      <div style={{ borderTop: `1px solid ${C.border}`, background: isDark ? '#0b0f17' : '#f8fafc', fontFamily: monoFont }}>
        <div
          onClick={() => setCompMonitorOpen(!compMonitorOpen)}
          style={{
            padding: '5px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            cursor: 'pointer',
            userSelect: 'none',
            borderBottom: compMonitorOpen ? `1px solid ${C.border}` : 'none',
          }}
        >
          {compMonitorOpen ? <ChevronDown size={12} color={C.textMuted} /> : <ChevronUp size={12} color={C.textMuted} />}
          <span style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8' }}>
            {`[MODE ${bringupMode} MODEL & COST MONITOR: ER-2 Legacy -> Pure Argon -> Argon Brain + Flash-Lite]`}
          </span>
          <span style={{ fontSize: 10.5, color: C.textMuted }}>
            {modelCompData?.status_text || 'Updates after each completed test stage.'}
          </span>
          <div style={{ flex: 1 }} />
          <button
            onClick={(e) => {
              e.stopPropagation();
              startAutomatedComparisonTest();
            }}
            style={{
              ...btnSmall,
              width: 'auto',
              height: 22,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.25), rgba(99, 102, 241, 0.25))',
              border: '1px solid rgba(168, 85, 247, 0.45)',
              color: '#e9d5ff',
              fontSize: 10,
              fontWeight: 700,
              padding: '0 9px',
            }}
          >
            ⚖️ Start Comparison Test
          </button>
        </div>

        {compMonitorOpen && (
          <div style={{ padding: '6px 16px', overflowX: 'auto', fontSize: 11, lineHeight: 1.45, color: C.text }}>
            <pre style={{ margin: 0, fontFamily: monoFont, fontSize: 10.5, whiteSpace: 'pre' }}>
{(modelCompData?.comparison_rows || []).length === 0
  ? [
      '┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐',
      `│ [WAITING FOR COMPLETED STAGE] In Autonomous VLA Mode (Mode ${bringupMode}), send "Start comparison test" (or click the button on the right):      │`,
      bringupMode === 1
        ? '│   Task: Build 9-Block Tower on Central Table (FR3_1 + FR3_2 + FR3_3)                                                                 │'
        : '│   Task: Dual-Arm Blue LongBar Manipulation (FR3_1 + FR3_2: dual_arm_pick -> dual_arm_circle -> dual_arm_place)                       │',
      '│   Stage 1: Execute with Legacy Loop (gemini-robotics-er-2-preview) -> Generate Stage 1 Report -> Reset Simulation                    │',
      '│   Stage 2: Execute with Gemini-4-Argon Only (gemini-4-argon)       -> Generate Stage 2 Report -> Reset Simulation                    │',
      '│   Stage 3: Execute with Argon Brain (1x) + Flash-Lite Executor     -> Generate Final Report   -> Finish                              │',
      '└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘',
    ].join('\n')
  : [
      '┌──────────────────────────────────────────────┬───────────┬───────────────────────────────┬──────────────────────┬────────────────────────────────────────────────────┐',
      '│ COMPLETED TEST STAGE / MODEL ARCHITECTURE    │ PLAN TIME │ MEASURED TOKENS (In/Ca/Th/O)  │ TASK & VERIFIER      │ MEASURED RUN (Calls | Time | Cost $USD | Savings)  │',
      '├──────────────────────────────────────────────┼───────────┼───────────────────────────────┼──────────────────────┼────────────────────────────────────────────────────┤',
      ...(modelCompData?.comparison_rows || []).map((r: any) => {
        const col1 = String(r.label || r.id).padEnd(44, ' ').slice(0, 44);
        const col2 = `${Number(r.plan_latency_ms || 0).toFixed(0)} ms`.padStart(9, ' ');
        const st = r.single_turn || {};
        const tokStr = `${st.input_tokens || 0}/${st.cached_tokens || 0}/${st.thinking_tokens || 0}/${st.output_tokens || 0}`.padEnd(29, ' ').slice(0, 29);
        const q = r.quality || {};
        const tgt = q.target_count ?? (bringupMode === 1 ? 9 : 3);
        const unit = tgt === 3 ? 'bar' : 'blk';
        const qualStr = `${q.blocks_placed ?? 0}/${tgt} ${unit} | ${q.verified_calls ?? 0}/${q.tool_calls ?? 0} (${Number(q.pass_rate_pct ?? 100).toFixed(0)}%)`.padEnd(20, ' ').slice(0, 20);
        const fp = r.full_task_projection || {};
        const sav = Number(fp.savings_vs_pure_argon_pct || 0);
        const savTag = sav > 0 ? ` (-${sav.toFixed(1)}%)` : (sav < 0 ? ` (+${Math.abs(sav).toFixed(1)}%)` : '');
        const callsTag = `${fp.argon_calls ?? 0}A+${fp.flash_lite_calls ?? 0}F+${fp.er2_calls ?? 0}E`;
        const projStr = `${callsTag} | ${Number(fp.est_wall_time_s ?? 0).toFixed(1)}s | $${Number(fp.cost_usd ?? 0).toFixed(5)}${savTag}`.padEnd(50, ' ').slice(0, 50);
        return `│ ${col1} │ ${col2} │ ${tokStr} │ ${qualStr} │ ${projStr} │`;
      }),
      '└──────────────────────────────────────────────┴───────────┴───────────────────────────────┴──────────────────────┴────────────────────────────────────────────────────┘',
    ].join('\n')}
            </pre>
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
