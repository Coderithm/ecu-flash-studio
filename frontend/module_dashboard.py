DASHBOARD_JSX = """
window.Dashboard = function({ flashOp, flashCount }) {
  const { useState, useEffect } = React;
  const [swVersion, setSwVersion] = useState("—");
  const [reading, setReading] = useState(false);
  const [flashReading, setFlashReading] = useState(false);
  const [localFC, setLocalFC] = useState("—");
  const [cmd, setCmd] = useState("");
  const [cmdLog, setCmdLog] = useState([]);
  const [sending, setSending] = useState(false);
  const QUICK = ["0x10 03", "0x22 F1 80", "0x27 01", "0x31 01 FF 00", "0x3E 00"]; 

  function readSW() {
    setReading(true);
    setTimeout(() => { setSwVersion("SW_ECU_v3.4.2-release"); setReading(false); }, 1400);
  }
  function readFC() {
    setFlashReading(true);
    setTimeout(() => { setLocalFC((flashCount || 0).toString()); setFlashReading(false); }, 1000);
  }
  function sendCmd() {
    if (!cmd.trim()) return;
    setSending(true);
    const entry = { cmd: cmd.trim(), ts: new Date().toLocaleString("en-IN", { hour12: false }).replace(",", ""), response: null };
    const snap = { ...entry };
    setTimeout(() => {
      let rx = `7F ${cmd.trim().substring(0, 2)} 31`;
      if (cmd.includes("22") || cmd.includes("3E")) rx = `62 ${cmd.trim().split(" ").slice(1).join(" ")} AA BB`;
      setCmdLog(l => [{ ...snap, response: rx }, ...l].slice(0, 20));
      setSending(false);
    }, 900);
    setCmdLog(l => [entry, ...l].slice(0, 20));
    setCmd("");
  }

  const opRunning = !!flashOp?.running;
  const opPct = Math.min(100, Math.max(0, flashOp?.progress ?? 0));
  const opElapsed = flashOp?.elapsedMs ?? 0;
  const opCycle = flashOp?.cycle ?? 0;
  const opTotal = flashOp?.total ?? 0;
  const opFile = flashOp?.swFile ?? "—";

  const [chartData, setChartData] = useState(Array(40).fill(0));

  useEffect(() => {
    if (!opRunning) {
      setChartData(Array(40).fill(0));
      return;
    } else {
      const iv = setInterval(() => {
        setChartData(prev => [...prev.slice(1), 40 + Math.random() * 50]);
      }, 100);
      return () => clearInterval(iv);
    }
  }, [opRunning]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 24, fontWeight: 800, letterSpacing: "-0.02em" }}>Dashboard Overview</h2>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        {/* SW Version */}
        <window.Card>
          <window.SectionLabel>SW Version</window.SectionLabel>
          <div className="text-glow" style={{ fontFamily: "monospace", fontSize: 16, fontWeight: 700, color: "var(--accent-primary)", background: "rgba(15, 23, 42, 0.4)", borderRadius: 8, padding: "8px 12px", marginBottom: 16, minHeight: 40, display: "flex", alignItems: "center", border: "1px solid rgba(34, 211, 238, 0.2)" }}>
            {reading ? <span className="animate-pulse" style={{ color: "#475569" }}>Reading…</span> : swVersion}
          </div>
          <window.Btn onClick={readSW} disabled={reading} style={{ width: "100%" }}>Read SW Version</window.Btn>
        </window.Card>

        {/* Flash Count */}
        <window.Card>
          <window.SectionLabel>Flash Cycle Count</window.SectionLabel>
          <div className="text-glow" style={{ fontFamily: "monospace", fontSize: 42, fontWeight: 800, color: "var(--accent-primary)", background: "rgba(15, 23, 42, 0.4)", borderRadius: 8, padding: "4px 12px", marginBottom: 16, textAlign: "center", minHeight: 60, lineHeight: "60px", border: "1px solid rgba(34, 211, 238, 0.2)" }}>
            {flashReading ? <span className="animate-pulse" style={{ fontSize: 16, color: "#475569", fontWeight: 400 }}>Reading…</span> : localFC}
          </div>
          <window.Btn onClick={readFC} disabled={flashReading} color="#065f46" style={{ width: "100%" }}>Read Flash Count</window.Btn>
        </window.Card>

        {/* ECU Status */}
        <window.Card>
          <window.SectionLabel>ECU Status</window.SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Session</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>Extended Diagnostic</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Protocol</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>UDS over CAN</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>CAN ID (TX)</span>
              <span className="text-glow" style={{ fontFamily: "monospace", fontSize: 14, color: "var(--accent-primary)", fontWeight: 700 }}>0x7E0</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>CAN ID (RX)</span>
              <span className="text-glow" style={{ fontFamily: "monospace", fontSize: 14, color: "var(--accent-primary)", fontWeight: 700 }}>0x7E8</span>
            </div>
          </div>
        </window.Card>

        {/* Current Flashing Operation Time */}
        <window.Card>
          <window.SectionLabel>Current Flash Operation</window.SectionLabel>

          {!opRunning ? (
            <div style={{ fontSize: 12, color: "#475569", padding: "8px 0" }}>No flashing operation running.</div>
          ) : (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
                <div className="text-glow" style={{ fontFamily: "monospace", fontSize: 14, fontWeight: 800, color: "var(--accent-primary)" }}>{window.fmtMs(opElapsed)}</div>
                <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>{opCycle}/{opTotal}</div>
              </div>
              <div style={{ width: "100%", background: "#1e293b", borderRadius: 9999, height: 10, marginBottom: 8, overflow: "hidden", position: "relative" }}>
                <div className="progress-stripes animate-stripe-slide" style={{ width: `${opPct}%`, height: 10, background: "var(--accent-primary)", borderRadius: 9999, transition: "width 0.15s" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748b" }}>
                <span style={{ fontFamily: "monospace", color: "#94a3b8" }}>{opFile}</span>
                <span className="font-bold">{Math.round(opPct)}%</span>
              </div>
            </>
          )}
        </window.Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16 }}>
        {/* Application Command */}
        <window.Card>
          <window.SectionLabel>Application Command</window.SectionLabel>
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <input value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={e => e.key === "Enter" && sendCmd()} placeholder="e.g. 0x10 03 or 22 F1 80" style={{ flex: 1, background: "#0f172a", border: "1px solid #334155", borderRadius: 8, padding: "8px 12px", fontSize: 12, fontFamily: "monospace", color: "#f1f5f9", outline: "none" }} />
            <window.Btn onClick={sendCmd} disabled={sending || !cmd.trim()}>{sending ? "Sending…" : "Send"}</window.Btn>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
            {QUICK.map(c => (
              <button key={c} onClick={() => setCmd(c)} style={{ background: "#334155", color: "#94a3b8", border: "none", borderRadius: 6, padding: "3px 8px", fontSize: 11, fontFamily: "monospace", cursor: "pointer" }}>{c}</button>
            ))}
          </div>
          <div style={{ background: "#0f172a", borderRadius: 8, border: "1px solid #334155", maxHeight: 180, overflowY: "auto" }}>
            {cmdLog.length === 0
              ? <div style={{ padding: 12, fontSize: 11, color: "#475569" }}>No commands sent yet.</div>
              : cmdLog.map((e, i) => (
                <div key={i} style={{ display: "flex", gap: 12, padding: "6px 12px", borderBottom: "1px solid #1e293b", fontSize: 11, fontFamily: "monospace", background: i === 0 ? "rgba(255,255,255,0.02)" : "transparent" }}>
                  <span style={{ color: "#475569", width: 130, flexShrink: 0 }}>{e.ts}</span>
                  <span style={{ color: "#fde68a" }}>TX: {e.cmd}</span>
                  <span style={{ color: e.response ? (e.response.startsWith("7F") ? "#fca5a5" : "#6ee7b7") : "#475569" }}>
                    {e.response ? `RX: ${e.response}` : "…waiting"}
                  </span>
                </div>
              ))
            }
          </div>
        </window.Card>

        {/* CAN Bus Load Visualization */}
        <window.Card>
          <window.SectionLabel>Real-Time CAN Bus Load</window.SectionLabel>
          <div style={{ height: 120, position: "relative", marginBottom: 12, background: "rgba(0,0,0,0.2)", borderRadius: 12, overflow: "hidden", border: "1px solid rgba(255,255,255,0.05)" }}>
            <svg width="100%" height="100%" viewBox="0 0 400 100" preserveAspectRatio="none">
              <defs>
                <linearGradient id="waveGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent-primary)" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="var(--accent-primary)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path 
                d={`M 0 100 ${chartData.map((v, i) => `L ${i * 10} ${100 - v}`).join(' ')} L 400 100 Z`}
                fill="url(#waveGrad)"
                stroke="none"
              />
              <path 
                d={chartData.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i * 10} ${100 - v}`).join(' ')}
                fill="none"
                stroke="var(--accent-primary)"
                strokeWidth="2"
                strokeLinecap="round"
                className="text-glow"
              />
            </svg>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>Simulated Data Rate</div>
            <div className="text-glow" style={{ fontSize: 18, fontWeight: 800, color: "var(--accent-primary)", fontFamily: "monospace" }}>
              {opRunning ? (450 + Math.random() * 50).toFixed(1) : "0.0"} <span style={{ fontSize: 10, color: "#475569" }}>fps</span>
            </div>
          </div>
        </window.Card>
      </div>
    </div>
  );
};
"""
