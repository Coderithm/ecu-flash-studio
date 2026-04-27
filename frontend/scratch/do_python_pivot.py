import os
import shutil

base = r"C:\Users\KIIT0001\OneDrive\Desktop\FYI Dashboard"
frontend_dir = os.path.join(base, "frontend")

os.makedirs(frontend_dir, exist_ok=True)

# ─── 1. Core HTML Structure ───
html_core = '''
HTML_WRAPPER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ECU Flash Tool — Diagnostic & Flash Studio</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://unpkg.com/react@18/umd/react.development.js"></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    theme: {
      extend: {
        fontFamily: { sans: ['Outfit', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] },
        animation: {
          'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          'glow': 'glow 2s ease-in-out infinite alternate',
          'fade-in-up': 'fadeInUp 0.5s ease-out forwards',
        },
        keyframes: {
          glow: { '0%': { boxShadow: '0 0 5px rgba(59,130,246,0.2)' }, '100%': { boxShadow: '0 0 20px rgba(59,130,246,0.6)' } },
          fadeInUp: { '0%': { opacity: '0', transform: 'translateY(10px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        }
      }
    }
  }
</script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: radial-gradient(circle at 10% 20%, #080b17, #020617); color: #e2e8f0; }
  ::-webkit-scrollbar { width: 8px; height: 8px; }
  ::-webkit-scrollbar-track { background: #0f172a; border-radius: 4px; }
  ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: #475569; }
  table { width: 100%; border-collapse: separate; border-spacing: 0; }
  th { background: rgba(15, 23, 42, 0.6); padding: 12px; font-weight: 500; color: #94a3b8; text-transform: uppercase; font-size: 10px; letter-spacing: 0.1em; border-bottom: 2px solid rgba(51,65,85,0.4); text-align: left; }
  td { padding: 10px 12px; border-bottom: 1px solid rgba(51,65,85,0.2); }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(30, 41, 59, 0.4); }
  input[type=range] { -webkit-appearance: none; background: transparent; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; height: 16px; width: 16px; border-radius: 50%; background: #3b82f6; cursor: pointer; transform: translateY(-6px); box-shadow: 0 0 10px rgba(59,130,246,0.6); }
  input[type=range]::-webkit-slider-runnable-track { width: 100%; height: 6px; cursor: pointer; background: #334155; border-radius: 3px; }
</style>
</head>
<body>
<div id="root"></div>

<!-- STITCHED COMPONENTS -->
<script type="text/babel">
{CONTENT}
</script>

</body>
</html>
"""
'''
with open(os.path.join(frontend_dir, "html_core.py"), 'w', encoding='utf-8') as f:
    f.write(html_core)

# ─── 2. Utils ───
utils = '''
UTILS_JSX = """
window.fmtMs = function(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m ${sec}s`;
  return `${m}m ${sec}s`;
};

window.Badge = function({ type }) {
  const map = {
    success:     { bg: "#064e3b", color: "#34d399", border: "#059669", glow: "rgba(52,211,153,0.3)" },
    failed:      { bg: "#7f1d1d", color: "#fca5a5", border: "#dc2626", glow: "rgba(248,113,113,0.3)" },
    running:     { bg: "#78350f", color: "#fde68a", border: "#d97706", glow: "rgba(251,191,36,0.3)" },
    interrupted: { bg: "#7c2d12", color: "#fdba74", border: "#ea580c", glow: "rgba(249,115,22,0.3)" },
    idle:        { bg: "#1e293b", color: "#94a3b8", border: "#334155", glow: "none" },
  };
  const s = map[type] || map.idle;
  return (
    <span style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}`, boxShadow: s.glow !== "none" ? `0 0 10px ${s.glow}` : "none", borderRadius: 9999, padding: "3px 12px", fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", display: "inline-block" }}>{type}</span>
  );
};

window.SectionLabel = function({ children }) {
  return <div className="text-[11px] font-bold tracking-[0.2em] text-indigo-300/80 uppercase mb-4 flex items-center gap-2"><span className="w-2 h-2 rounded-sm bg-indigo-500/50"></span>{children}</div>;
};

window.Btn = function({ children, onClick, disabled, color = "#3b82f6", style, className="" }) {
  const isDanger = color === "#7f1d1d" || color === "#dc2626" || color === "#c2410c" || color === "#92400e";
  const isSuccess = color === "#065f46" || color === "#10b981";
  
  let bgClass = "bg-slate-700/50 text-slate-400 border-slate-600/50";
  if (!disabled) {
    if (isDanger) bgClass = "bg-red-600/80 hover:bg-red-500 text-white border-red-500/50 hover:shadow-[0_0_15px_rgba(239,68,68,0.5)] hover:-translate-y-0.5";
    else if (isSuccess) bgClass = "bg-emerald-600/80 hover:bg-emerald-500 text-white border-emerald-500/50 hover:shadow-[0_0_15px_rgba(16,185,129,0.5)] hover:-translate-y-0.5";
    else if (color === "#334155") bgClass = "bg-slate-700 hover:bg-slate-600 text-white border-slate-600/50 hover:shadow-lg hover:-translate-y-0.5";
    else bgClass = "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white border-blue-500/50 hover:shadow-[0_0_20px_rgba(59,130,246,0.6)] hover:-translate-y-0.5";
  }

  return (
    <button onClick={onClick} disabled={disabled} className={`relative overflow-hidden font-bold rounded-xl px-4 py-2 text-xs transition-all duration-300 border backdrop-blur-sm shadow-lg ${bgClass} ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer active:scale-95'} ${className}`} style={style}>
      {children}
    </button>
  );
};

window.Card = function({ children, style }) {
  return (
    <div className="bg-slate-800/30 backdrop-blur-xl border border-slate-700/40 rounded-2xl p-6 shadow-xl hover:shadow-2xl hover:border-slate-600/50 transition-all duration-500 animate-fade-in-up relative overflow-hidden group" style={style}>
      <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/5 rounded-full blur-3xl group-hover:bg-blue-500/10 transition-colors duration-700 pointer-events-none"></div>
      <div className="relative z-10">{children}</div>
    </div>
  );
};
"""
'''
with open(os.path.join(frontend_dir, "module_utils.py"), 'w', encoding='utf-8') as f: f.write(utils)

# ─── 3. Sidebar ───
sidebar = '''
SIDEBAR_JSX = """
const NAV = [
  { id: "dashboard",    icon: "⬛", label: "Dashboard"          },
  { id: "multiflash",   icon: "🔁", label: "Multi-Flash Mode"   },
];

window.Sidebar = function({ active, setActive }) {
  return (
    <aside className="w-[240px] min-h-screen border-r border-slate-800/80 flex flex-col py-6 relative z-10" style={{ background: "linear-gradient(180deg, rgba(15,23,42,0.8) 0%, rgba(2,6,23,0.95) 100%)", backdropFilter: "blur(20px)" }}>
      <div className="px-6 mb-8">
        <div className="text-[10px] font-bold tracking-[0.2em] text-blue-500 uppercase mb-2">ECU System</div>
        <div className="text-[22px] font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400 leading-tight drop-shadow-md">Flash Studio</div>
      </div>
      <div className="flex-1 flex flex-col gap-1.5 px-3">
      {NAV.map(n => (
        <button key={n.id} onClick={() => setActive(n.id)} 
          className={`flex items-center gap-3 px-4 py-3.5 text-[14px] font-medium rounded-xl cursor-pointer transition-all duration-300 w-full text-left
          ${active === n.id ? 'bg-blue-600/15 text-blue-300 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]' : 'bg-transparent text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 border border-transparent'}`}>
          <span className={`text-lg transition-transform duration-300 ${active === n.id ? 'scale-110' : 'opacity-70'}`}>{n.icon}</span>{n.label}
        </button>
      ))}
      </div>
      <div className="mt-auto px-6 py-5 border-t border-slate-800 bg-slate-900/30">
        <div className="text-[11px] text-slate-500 mb-1.5 font-medium uppercase tracking-wider">Backend Status</div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse-slow shadow-[0_0_8px_rgba(52,211,153,0.8)]"></span>
          <span className="text-[12px] text-emerald-400 font-bold">Python API Live</span>
        </div>
      </div>
    </aside>
  );
};
"""
'''
with open(os.path.join(frontend_dir, "module_sidebar.py"), 'w', encoding='utf-8') as f: f.write(sidebar)

# ─── 4. Dashboard ───
dash = '''
DASHBOARD_JSX = """
window.Dashboard = function({ flashOp }) {
  const opRunning = !!flashOp?.running;
  const opPct = Math.min(100, Math.max(0, flashOp?.progress ?? 0));
  const opElapsed = flashOp?.elapsedMs ?? 0;
  
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ color: "#f1f5f9", margin: 0, fontSize: 24, fontWeight: 700 }}>Dashboard Overview</h2>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        <window.Card>
          <window.SectionLabel>Live Execution</window.SectionLabel>
          {!opRunning ? (
            <div style={{ fontSize: 13, color: "#475569", padding: "10px 0" }}>No flashing operation running on the Python backend.</div>
          ) : (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
                <div style={{ fontFamily: "monospace", fontSize: 16, fontWeight: 700, color: "#93c5fd" }}>{window.fmtMs(opElapsed)}</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>{flashOp?.cycle}/{flashOp?.total}</div>
              </div>
              <div style={{ width: "100%", background: "#334155", borderRadius: 9999, height: 12, marginBottom: 10 }}>
                <div style={{ width: `${opPct}%`, height: 12, background: "linear-gradient(90deg, #3b82f6, #06b6d4)", borderRadius: 9999, transition: "width 0.3s ease" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#64748b" }}>
                <span style={{ fontFamily: "monospace", color: "#94a3b8" }}>{flashOp?.swFile}</span>
                <span className="font-bold">{Math.round(opPct)}%</span>
              </div>
            </>
          )}
        </window.Card>
      </div>
    </div>
  );
};
"""
'''
with open(os.path.join(frontend_dir, "module_dashboard.py"), 'w', encoding='utf-8') as f: f.write(dash)

# ─── 5. MultiFlash ───
multi = '''
MULTIFLASH_JSX = """
const { useState, useEffect } = React;

window.MultiFlash = function({ flashOp, setFlashOp }) {
  const [plan, setPlan] = useState(() => (
    Array.from({ length: 10 }, (_, i) => ({
      enabled: i === 0,
      fileObj: null,
      fileName: "",
      priority: null
    }))
  ));
  
  const [times, setTimes] = useState(1);
  const [running, setRunning] = useState(false);
  const [sessionLog, setSessionLog] = useState([]);
  
  useEffect(() => {
    const iv = setInterval(async () => {
      try {
        const res = await fetch('/api/flash_status');
        const st = await res.json();
        setRunning(st.running);
        setFlashOp({ 
          running: st.running, swFile: st.swFile, cycle: st.current_op, total: st.total_ops, 
          progress: st.progress, elapsedMs: st.elapsedMs, total_progress: st.total_progress, eta_seconds: st.eta_seconds
        });
        if (st.sessionLog) setSessionLog(st.sessionLog);
      } catch(e) { }
    }, 250);
    return () => clearInterval(iv);
  }, [setFlashOp]);

  function handleFileChange(i, e) {
    const f = e.target.files[0];
    setPlan(p => {
      const next = [...p];
      if (f) {
        let assumedPri = next[i].priority;
        if (!assumedPri) {
           for (let n = 1; n <= 10; n++) {
             if (!next.some(r => r.enabled && r.priority === n)) { assumedPri = n; break; }
           }
        }
        next[i] = { ...next[i], fileObj: f, fileName: f.name, enabled: true, priority: assumedPri };
      } else {
        next[i] = { ...next[i], fileObj: null, fileName: "", priority: null };
      }
      return next;
    });
  }

  function handleEnableChange(i, enabled) {
    setPlan(p => { const next = [...p]; next[i] = { ...next[i], enabled, priority: enabled ? next[i].priority : null }; return next; });
  }
  
  function handlePriorityChange(i, val) {
    const next = [...plan]; next[i] = { ...next[i], priority: val ? parseInt(val) : null }; setPlan(next);
  }

  function buildOps() {
    return plan.filter(r => r.enabled && r.fileName && r.priority !== null).sort((a, b) => a.priority - b.priority);
  }

  async function startFlashing() {
    const ops = buildOps(); if (ops.length === 0) return;
    const filePromises = ops.map(r => new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve({ name: r.fileName, data_b64: e.target.result.split(',')[1] || "" });
      reader.readAsDataURL(r.fileObj);
    }));
    const filesData = await Promise.all(filePromises);
    setRunning(true);
    fetch('/api/start_multiflash', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ files: filesData, times: times }) });
  }

  const opsCount = buildOps().length; const canStart = !running && opsCount > 0;
  const successCount = sessionLog.filter(e => e.status === "success").length;
  const failCount = sessionLog.filter(e => e.status === "failed").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ color: "#f1f5f9", margin: 0, fontSize: 24, fontWeight: 700 }}>Multi-Flash Queue</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <window.Card>
          <window.SectionLabel>Local File Selection</window.SectionLabel>
          <div style={{ fontSize: 12, color: "#64748b", marginBottom: 12 }}>Pick files and assign absolute sequence priorities (1-10).</div>
          <div style={{ border: "1px solid rgba(51,65,85,0.6)", borderRadius: 12, overflow: "hidden", background: "#0f172a", marginBottom: 16, marginTop: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead><tr style={{ color: "#64748b", borderBottom: "1px solid #334155" }}><th style={{ width: 40 }}>Use</th><th style={{ width: 90 }}>Priority</th><th>Select Local Hex File</th></tr></thead>
              <tbody>
                {plan.map((row, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid rgba(51,65,85,0.4)" }}>
                    <td><input type="checkbox" checked={row.enabled} disabled={running} onChange={e => handleEnableChange(i, e.target.checked)} style={{ width: 16, height: 16, accentColor: "#3b82f6" }} /></td>
                    <td style={{ color: "#94a3b8", fontFamily: "monospace" }}>
                      <select value={row.priority || ""} disabled={!row.enabled || running} onChange={e => handlePriorityChange(i, e.target.value)} className={`bg-slate-900 border border-slate-700/50 rounded p-1 text-xs outline-none focus:border-blue-500 ${!row.enabled ? 'opacity-50' : 'text-slate-200'}`}>
                        <option value="">--</option>
                        {[1,2,3,4,5,6,7,8,9,10].map(n => {
                          const isUsedByOther = plan.some((r, idx) => r.enabled && r.priority === n && idx !== i);
                          return <option key={n} value={n} disabled={isUsedByOther} className={isUsedByOther ? "text-slate-600 bg-slate-800" : "text-slate-200"}>Seq {n}</option>;
                        })}
                      </select>
                    </td>
                    <td><input type="file" accept=".hex,.bin" disabled={running} onChange={e => handleFileChange(i, e)} className="text-xs text-slate-300 file:mr-4 file:py-1 file:px-3 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-500/20 file:text-blue-400 hover:file:bg-blue-500/30 transition shadow-none cursor-pointer outline-none w-full" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 6 }}>Repeat Sequence Array (up to 100,000)</div>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ flex: 1 }}><input type="range" min={1} max={100000} value={times} onChange={e => setTimes(+e.target.value)} disabled={running} style={{ width: "100%", outline: "none", accentColor: "#3b82f6" }} /></div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="number" min={1} max={100000} value={times} onChange={e => { let v = parseInt(e.target.value); if (isNaN(v)) v = 1; if (v > 100000) v = 100000; if (v < 1) v = 1; setTimes(v); }} disabled={running} className="bg-slate-900 border border-slate-700/50 rounded-lg p-2 text-white font-bold w-28 outline-none focus:border-blue-500 text-base shadow-inner text-right" />
                <span className="text-slate-500 text-sm font-medium">loops</span>
              </div>
            </div>
          </div>
          <window.Btn onClick={startFlashing} disabled={!canStart} className="w-full py-3 text-[14px]">
            {running ? `Execution in Progress (${flashOp?.cycle || 0}/${flashOp?.total || 0})...` : "▶ Begin Hardware Flashing"}
          </window.Btn>
        </window.Card>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <window.Card>
            <window.SectionLabel>Global Flashing Progress</window.SectionLabel>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10, fontSize: 14 }}><span style={{ color: "#94a3b8" }}>Master Sequence</span><span style={{ fontWeight: 800, color: "#f1f5f9" }}>{Math.round(flashOp?.total_progress || 0)}%</span></div>
            <div style={{ width: "100%", background: "#1e293b", borderRadius: 9999, height: 16, border: "1px solid #334155" }}><div style={{ width: `${Math.max(0, Math.min(100, flashOp?.total_progress || 0))}%`, height: 14, background: "linear-gradient(90deg, #10b981, #3b82f6)", borderRadius: 9999, transition: "width 0.4s" }} /></div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#64748b", marginTop: 8 }}><span>ETA: <span className={`font-mono font-bold ${flashOp?.eta_seconds >= 0 ? "text-emerald-400" : "text-slate-500"}`}>{flashOp?.eta_seconds >= 0 ? window.fmtMs(flashOp.eta_seconds * 1000) : "Calculating..."}</span></span><span>Total Flashes: <span className="font-bold text-slate-300">{flashOp?.total || 0}</span></span></div>
          </window.Card>

          <window.Card>
            <window.SectionLabel>Active Component Segment</window.SectionLabel>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#64748b", marginBottom: 8 }}><span className="font-mono text-indigo-300 truncate max-w-[200px]" title={flashOp?.swFile}>{flashOp?.swFile}</span><span className="font-bold text-slate-300">{Math.round(flashOp?.progress || 0)}%</span></div>
            <div style={{ width: "100%", background: "#1e293b", borderRadius: 9999, height: 10, border: "1px solid #334155", marginBottom: 8 }}><div style={{ width: `${flashOp?.progress || 0}%`, height: 8, background: "linear-gradient(90deg, #3b82f6, #06b6d4)", borderRadius: 9999, transition: "width 0.2s" }} /></div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 24 }}>{[["✓ Succeeded", successCount, "#34d399", "bg-emerald-900/20 border-emerald-500/30"], ["✗ Failed", failCount, "#f87171", "bg-red-900/20 border-red-500/30"]].map(([label, val, color, cls]) => (<div key={label} className={`rounded-xl p-3 border text-center ${cls}`}><div style={{ fontSize: 24, fontWeight: 800, color }}>{val}</div><div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div></div>))}</div>
          </window.Card>
        </div>
      </div>
      <window.Card>
        <window.SectionLabel>Python Execution Logs</window.SectionLabel>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead><tr style={{ color: "#64748b", borderBottom: "1px solid #334155" }}>{["File Processed", "Execution Timestamp", "Time Elapsed", "Result"].map(h => <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontWeight: 500 }}>{h}</th>)}</tr></thead>
          <tbody>
            {sessionLog.length === 0 ? <tr><td colSpan={4} style={{ textAlign: "center", color: "#475569", padding: "24px", fontSize: 14 }}>Waiting for backend Python events...</td></tr> : sessionLog.map(e => (<tr key={e.id} style={{ borderBottom: "1px solid rgba(51,65,85,0.4)" }}><td style={{ padding: "10px 14px", fontFamily: "monospace", color: "#93c5fd" }}>{e.swFile}</td><td style={{ padding: "10px 14px", color: "#cbd5e1" }}>{e.timestamp}</td><td style={{ padding: "10px 14px", color: "#cbd5e1" }}>{e.duration}</td><td style={{ padding: "10px 14px" }}><window.Badge type={e.status} /></td></tr>))}
          </tbody>
        </table>
      </window.Card>
    </div>
  );
};
"""
'''
with open(os.path.join(frontend_dir, "module_multiflash.py"), 'w', encoding='utf-8') as f: f.write(multi)

# ─── 6. App ───
app = '''
APP_JSX = """
const { useState } = React;

function App() {
  const [active, setActive] = useState("multiflash");
  const [flashOp, setFlashOp] = useState({ running: false, swFile: "—", cycle: 0, total: 0, progress: 0, elapsedMs: 0, total_progress: 0, eta_seconds: -1 });

  const pages = {
    dashboard: <window.Dashboard flashOp={flashOp} />,
    multiflash: <window.MultiFlash flashOp={flashOp} setFlashOp={setFlashOp} />,
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <window.Sidebar active={active} setActive={setActive} />
      <main style={{ flex: 1, padding: 32, overflowY: "auto" }}>
        {pages[active]}
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
"""
'''
with open(os.path.join(frontend_dir, "module_app.py"), 'w', encoding='utf-8') as f: f.write(app)

with open(os.path.join(frontend_dir, "__init__.py"), 'w') as f: pass

# ─── 7. Server update ───
server_code = r"""
import http.server
import socketserver
import webbrowser
import threading
import sys
import socket
import json
import time

from core.api_routes import get_flash_status, start_multiflash
from frontend.html_core import HTML_WRAPPER
from frontend.module_utils import UTILS_JSX
from frontend.module_sidebar import SIDEBAR_JSX
from frontend.module_dashboard import DASHBOARD_JSX
from frontend.module_multiflash import MULTIFLASH_JSX
from frontend.module_app import APP_JSX

# Dynamically construct the application payload
PAYLOAD = f"{UTILS_JSX}\n{SIDEBAR_JSX}\n{DASHBOARD_JSX}\n{MULTIFLASH_JSX}\n{APP_JSX}"
GENERATED_HTML = HTML_WRAPPER.replace("{CONTENT}", PAYLOAD)

class PurePythonRouter(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/flash_status':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_flash_status()).encode("utf-8"))
            return
        
        # Route ALL valid standard paths to the Python-generated UI
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(GENERATED_HTML.encode("utf-8"))
        
    def do_POST(self):
        if self.path == '/api/start_multiflash':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            files = payload.get('files', [])
            times = payload.get('times', 1)
            
            start_multiflash(files, times)
                
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode("utf-8"))
            return

    def log_message(self, format, *args):
        pass

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

if __name__ == "__main__":
    port = get_free_port()
    httpd = socketserver.TCPServer(("", port), PurePythonRouter)
    
    print(f"[*] Starting Pure-Python Engine on port {port}...")
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    url = f"http://localhost:{port}"
    print(f"[*] Opening browser to {url}")
    webbrowser.open(url)
    
    print("[*] Architecture strictly locked to Python components. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
        httpd.shutdown()
        httpd.server_close()
        sys.exit(0)
"""

with open(os.path.join(base, "server.py"), 'w', encoding='utf-8') as f:
    f.write(server_code)

# ─── Cleanup Operation ───
import shutil
# Delete public
if os.path.exists(os.path.join(base, "public")):
    shutil.rmtree(os.path.join(base, "public"))
    
# Delete single-file anomalies
old_dash = os.path.join(base, "dashboard.py")
if os.path.exists(old_dash):
    os.remove(old_dash)

# Clean scratch
scratch_dir = os.path.join(base, "scratch")
for root, dirs, files in os.walk(scratch_dir):
    for f in files:
        if f not in ["do_python_pivot.py"]: # Keep this logic executing
            os.remove(os.path.join(root, f))

print("Python-Exclusive Architecture Deployed.")
