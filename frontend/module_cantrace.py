CANTRACE_JSX = r"""
window.CanTrace = function() {
  const { useState, useEffect, useRef } = React;
  const [canTrace, setCanTrace] = useState([]);
  const [q, setQ] = useState("");
  const [showTX, setShowTX] = useState(true);
  const [showRX, setShowRX] = useState(true);
  const [showEVT, setShowEVT] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const wrapRef = useRef(null);

  // Poll for traces separately
  useEffect(() => {
    const iv = setInterval(async () => {
      try {
        const res = await fetch('/api/can_trace');
        const st = await res.json();
        setCanTrace(st.trace || []);
      } catch(e) { }
    }, 500);
    return () => clearInterval(iv);
  }, []);

  const filtered = canTrace.filter(f => {
    if (!showTX && f.dir === "TX") return false;
    if (!showRX && f.dir === "RX") return false;
    if (!showEVT && f.dir === "EVT") return false;
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
  }

  function exportLog() {
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

  async function copyLog() {
    const lines = filtered.map(f => `${f.ts}\t${f.dir}\t${f.canId}\t${f.data}\t${f.note || ""}`);
    try { await navigator.clipboard.writeText(lines.join("\n")); } catch (e) {}
  }

  const getRowStyle = (f) => {
    const data = (f.data || "").toUpperCase();
    if (data.startsWith("7F")) return { background: "rgba(239, 68, 68, 0.15)", borderLeft: "4px solid #ef4444" };
    if (data.startsWith("27")) return { background: "rgba(251, 191, 36, 0.08)", borderLeft: "4px solid #fbbf24" };
    if (data.startsWith("36") || data.startsWith("34")) return { background: "rgba(59, 130, 246, 0.08)", borderLeft: "4px solid var(--accent-primary)" };
    if (data.startsWith("3E")) return { opacity: 0.6 };
    return { borderLeft: "4px solid transparent" };
  };

  return (
    <window.Container>
      <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 24, fontWeight: 800 }}>Full CAN Trace</h2>

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
            <window.Btn onClick={clearAll} color="#7f1d1d">Clear</window.Btn>
          </div>
        </div>
      </window.Card>

      <window.Card style={{ padding: 0 }}>
        <div style={{ padding: "12px 20px", borderBottom: "1px solid #E2E8F0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.15em", color: "#64748B", textTransform: "uppercase" }}>Diagnostic Trace Stream</div>
          <div style={{ fontSize: 11, color: "#64748B", fontWeight: 700 }}>{filtered.length} frames</div>
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
                      <span style={{ padding: "2px 6px", borderRadius: 4, background: f.dir === "TX" ? "rgba(253, 230, 138, 0.1)" : "rgba(110, 231, 183, 0.1)", color: window.dirColor(f.dir), fontWeight: 800, fontSize: 10 }}>{f.dir}</span>
                    </td>
                    <td style={{ padding: "10px 14px", fontFamily: "monospace", color: "var(--accent-primary)", fontWeight: 700 }}>{f.canId}</td>
                    <td style={{ padding: "10px 14px", fontFamily: "monospace", color: f.data.startsWith("7F") ? "#DC2626" : "var(--text-primary)", letterSpacing: "0.05em" }}>{f.data}</td>
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
