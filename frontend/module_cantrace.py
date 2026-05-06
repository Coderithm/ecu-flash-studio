CANTRACE_JSX = r"""
window.CanTrace = function({ flashOp }) {
  const { useState, useEffect, useRef } = React;
  const [canTrace, setCanTrace] = useState([]);
  const [q, setQ] = useState("");
  const [showTX, setShowTX] = useState(true);
  const [showRX, setShowRX] = useState(true);
  const [showEVT, setShowEVT] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const [traceMeta, setTraceMeta] = useState({ total: 0, returned: 0, truncated: false, limit: 1500 });
  const [busMeta, setBusMeta] = useState({ bits_per_second: 0, frames_per_second: 0, window_ms: 1000 });
  const wrapRef = useRef(null);

  const opRunning = !!flashOp?.running;
  const [chartData, setChartData] = useState(Array(40).fill(0));
  const [displayLoad, setDisplayLoad] = useState(0);
  const canLoadRef = useRef(0);
  const displayLoadRef = useRef(0);
  const prevTraceLen = useRef(0);

  useEffect(() => {
    const iv = setInterval(() => {
      const target = Math.max(0, Math.min(100, canLoadRef.current));
      const prev = displayLoadRef.current;
      const next = Math.abs(target - prev) < 0.05 ? target : prev + ((target - prev) * 0.35);
      displayLoadRef.current = next;
      setDisplayLoad(next);
      setChartData(history => [...history.slice(1), next]);
    }, 200);
    return () => clearInterval(iv);
  }, []);

  function normalizeFrame(f) {
    return {
      id: f?.id || `${f?.ts || ""}-${f?.dir || ""}-${Math.random()}`,
      ts: String(f?.ts ?? ""),
      dir: String(f?.dir ?? "EVT").toUpperCase(),
      canId: String(f?.canId ?? ""),
      data: String(f?.data ?? ""),
      note: String(f?.note ?? "")
    };
  }

  // Poll for a bounded trace snapshot so the table stays responsive during flashing.
  useEffect(() => {
    let alive = true;
    async function pollTrace() {
      try {
        const res = await fetch('/api/can_trace?limit=1500');
        const st = await res.json();
        if (!alive) return;
        const newTrace = Array.isArray(st.trace) ? st.trace.map(normalizeFrame) : [];
        setCanTrace(newTrace);
        setTraceMeta({
          total: Number(st.total ?? newTrace.length),
          returned: Number(st.returned ?? newTrace.length),
          truncated: !!st.truncated,
          limit: Number(st.limit ?? 1500)
        });
        const busLoad = st.bus_load || {};
        setBusMeta({
          bits_per_second: Number(busLoad.bits_per_second ?? 0),
          frames_per_second: Number(busLoad.frames_per_second ?? 0),
          window_ms: Number(busLoad.window_ms ?? 1000)
        });
        
        const totalFrames = Number(st.total ?? newTrace.length);
        const dFrames = Math.max(0, totalFrames - prevTraceLen.current);
        prevTraceLen.current = totalFrames;

        const backendPercent = Number(busLoad.percent);
        const fallbackPercent = Math.min(100, dFrames * 0.08);
        canLoadRef.current = Number.isFinite(backendPercent) ? backendPercent : fallbackPercent;
        if (!opRunning && dFrames === 0 && canLoadRef.current < 0.1) canLoadRef.current = 0;
      } catch(e) { }
    }
    pollTrace();
    const iv = setInterval(pollTrace, 500);
    return () => { alive = false; clearInterval(iv); };
  }, [opRunning]);

  const filtered = canTrace.filter(f => {
    const dir = f.dir || "EVT";
    if (!showTX && dir === "TX") return false;
    if (!showRX && dir === "RX") return false;
    if (!showEVT && dir === "EVT") return false;
    if (!q) return true;
    const hay = `${f.ts} ${f.dir} ${f.canId} ${f.data} ${f.note}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  useEffect(() => {
    if (!autoScroll) return;
    const el = wrapRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [filtered.length, autoScroll]);

  async function clearAll() {
    await fetch('/api/can_trace_clear', { method: 'POST' });
    setCanTrace([]);
    setTraceMeta({ total: 0, returned: 0, truncated: false, limit: 1500 });
    setBusMeta({ bits_per_second: 0, frames_per_second: 0, window_ms: 1000 });
    prevTraceLen.current = 0;
    canLoadRef.current = 0;
    displayLoadRef.current = 0;
    setDisplayLoad(0);
    setChartData(Array(40).fill(0));
  }

  async function exportLog() {
    try {
      const res = await fetch('/api/export_trc');
      if (res.status === 204) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `can_trace_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.trc`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch(e) {
      const lines = canTrace.map(f => `${f.ts}\t${f.dir}\t${f.canId}\t${f.data}\t${f.note || ""}`);
      const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `can_trace_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.log`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }
  }

  async function copyLog() {
    const lines = filtered.map(f => `${f.ts}\t${f.dir}\t${f.canId}\t${f.data}\t${f.note || ""}`);
    try { await navigator.clipboard.writeText(lines.join("\n")); } catch (e) {}
  }

  const getRowStyle = (f) => {
    const data = String(f?.data || "").toUpperCase();
    if (data.startsWith("7F")) return { background: "rgba(14, 165, 233, 0.08)", borderLeft: "4px solid #0ea5e9" }; // Sky Blue for NRCs
    if (data.startsWith("27")) return { background: "rgba(251, 191, 36, 0.08)", borderLeft: "4px solid #fbbf24" };
    if (data.startsWith("36") || data.startsWith("34")) return { background: "rgba(59, 130, 246, 0.08)", borderLeft: "4px solid var(--accent-primary)" };
    if (data.startsWith("3E")) return { opacity: 0.6 };
    return { borderLeft: "4px solid transparent" };
  };

  return (
    <window.Container>
      <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 24, fontWeight: 800 }}>Full CAN Trace</h2>

      <window.Card style={{ marginBottom: 16 }}>
        <window.SectionLabel>Real-Time CAN Bus Load (500 kbps)</window.SectionLabel>
        <div style={{ display: "flex", gap: 16, alignItems: "stretch", height: 80 }}>
          {/* Left: Line Graph */}
          <div style={{ flex: 1, position: "relative", background: "#F8FAFC", borderRadius: 8, overflow: "hidden", border: "1px solid #E2E8F0" }}>
            <div style={{ position: "absolute", left: 6, top: 4, fontSize: 9, color: "#94a3b8", fontWeight: 700 }}>100%</div>
            <div style={{ position: "absolute", left: 6, bottom: 4, fontSize: 9, color: "#94a3b8", fontWeight: 700 }}>0%</div>
            <svg width="100%" height="100%" viewBox="0 0 400 100" preserveAspectRatio="none">
              <defs>
                <linearGradient id="waveGradGreen" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d={`M 0 100 ${chartData.map((v, i) => `L ${i * 10} ${100 - v}`).join(' ')} L 400 100 Z`} fill="url(#waveGradGreen)" stroke="none" />
              <path d={chartData.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i * 10} ${100 - v}`).join(' ')} fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>

          {/* Right: Tank Filler */}
          <div style={{ width: 60, display: "flex", flexDirection: "column", gap: 6, alignItems: "center", justifyContent: "center" }}>
            <div style={{ height: 50, width: 24, background: "#E2E8F0", borderRadius: 4, overflow: "hidden", position: "relative", boxShadow: "inset 0 2px 4px rgba(0,0,0,0.1)" }}>
              <div style={{ 
                position: "absolute", bottom: 0, left: 0, right: 0, 
                height: `${displayLoad}%`, background: "#0ea5e9", 
                transition: "height 0.1s linear" 
              }} />
            </div>
            <div style={{ fontSize: 11, fontWeight: 800, color: "#0ea5e9", fontFamily: "monospace" }}>{displayLoad.toFixed(1)}%</div>
            <div style={{ fontSize: 9, color: "#64748B", fontFamily: "monospace", textAlign: "center", lineHeight: 1.2 }}>{busMeta.frames_per_second.toFixed(0)} fps</div>
          </div>
        </div>
      </window.Card>

      <window.Card>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <window.MonoInput value={q} onChange={e => setQ(e.target.value)} placeholder="Filter by time / ID / data / note…" />
          </div>
          <div style={{ display: "flex", gap: 12, padding: "0 10px" }}>
            {[["TX", showTX, setShowTX], ["RX", showRX, setShowRX], ["EVT", showEVT, setShowEVT]].map(([l, v, s]) => (
              <label key={l} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: v ? "var(--text-primary)" : "#64748B", cursor: "pointer", fontWeight: v ? 700 : 400 }}>
                <input type="checkbox" checked={v} onChange={e => s(e.target.checked)} className="accent-blue-500" /> {l}
              </label>
            ))}
          </div>
          <div style={{ borderLeft: "1px solid #E2E8F0", height: 20, margin: "0 10px" }} />
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: autoScroll ? "var(--text-primary)" : "#64748B", cursor: "pointer" }}>
            <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} /> Auto-scroll
          </label>
          <div style={{ display: "flex", gap: 6 }}>
            <window.Btn onClick={copyLog} color="#E2E8F0">Copy</window.Btn>
            <window.Btn onClick={exportLog} color="#E2E8F0">Export</window.Btn>
            <window.Btn onClick={clearAll} color="#0ea5e9">Clear</window.Btn>
          </div>
        </div>
      </window.Card>

      <window.Card style={{ padding: 0 }}>
        <div style={{ padding: "12px 20px", borderBottom: "1px solid #E2E8F0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.15em", color: "#64748B", textTransform: "uppercase" }}>Diagnostic Trace Stream</div>
          <div style={{ fontSize: 11, color: "#64748B", fontWeight: 700 }}>
            {filtered.length} shown{traceMeta.truncated ? ` / ${traceMeta.total} total` : ""}
          </div>
        </div>

        <div ref={wrapRef} style={{ maxHeight: 520, overflowY: "auto", overflowX: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ color: "#64748B", borderBottom: "1px solid #E2E8F0", position: "sticky", top: 0, background: "rgba(255, 255, 255, 0.95)", backdropFilter: "blur(4px)", zIndex: 10 }}>
                {['Time','Dir','CAN ID','Data','Note'].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "12px 14px", fontWeight: 700, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0
                ? <tr><td colSpan={5} style={{ textAlign: "center", color: "#64748B", padding: 32, fontSize: 13 }}>No frames match filters.</td></tr>
                : filtered.map((f, i) => (
                  <tr key={f.id || i} style={{ ...getRowStyle(f), borderBottom: "1px solid #E2E8F0", transition: "all 0.2s" }} className="group">
                    <td style={{ padding: "10px 14px", fontSize: 11, color: "#64748B", fontFamily: "monospace" }}>{f.ts}</td>
                    <td style={{ padding: "10px 14px" }}>
                      <span style={{ padding: "2px 6px", borderRadius: 4, background: String(f.dir || "EVT") === "TX" ? "rgba(253, 230, 138, 0.1)" : "rgba(110, 231, 183, 0.1)", color: window.dirColor(String(f.dir || "EVT")), fontWeight: 800, fontSize: 10 }}>{String(f.dir || "EVT")}</span>
                    </td>
                    <td style={{ padding: "10px 14px", fontFamily: "monospace", color: "var(--accent-primary)", fontWeight: 700 }}>{f.canId}</td>
                    <td style={{ padding: "10px 14px", fontFamily: "monospace", color: String(f.data || "").startsWith("7F") ? "#0ea5e9" : "var(--text-primary)", letterSpacing: "0.05em" }}>{String(f.data || "")}</td>
                    <td style={{ padding: "10px 14px", fontSize: 11, color: "#64748B", fontStyle: f.note ? "normal" : "italic" }}>{f.note || "—"}</td>
                  </tr>
                ))
              }
            </tbody>
          </table>
        </div>
      </window.Card>
    </window.Container>
  );
};
"""
