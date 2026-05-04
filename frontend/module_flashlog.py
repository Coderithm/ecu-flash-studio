FLASHLOG_JSX = r"""
window.FlashLog = function({ sessionLog }) {
  const { useState } = React;
  const [downloading, setDownloading] = useState(false);
  
  const successCnt = sessionLog.filter(e => e.status === "success").length;
  const failCnt    = sessionLog.filter(e => e.status === "failed").length;
  
  // Parse duration like "0.5s" back to MS. E.g. "0.5s" -> 0.5 * 1000 = 500ms
  const totalMs = sessionLog.reduce((acc, e) => {
    let secs = parseFloat((e.duration || "0").replace('s', ''));
    if (isNaN(secs)) secs = 0;
    return acc + (secs * 1000);
  }, 0);

  async function downloadTrc() {
    if (downloading) return;
    setDownloading(true);
    try {
      const res = await fetch('/api/export_trc');
      if (!res.ok) { alert("No trace data available to export."); return; }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.download = `flash_trace_${ts}.trc`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch(e) {
      alert("Export failed: " + e.message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <window.Container style={{ marginTop: 64 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 20, fontWeight: 700 }}>Flash Log</h2>
        <window.Btn onClick={downloadTrc} disabled={downloading} color="#7c3aed" style={{ padding: "8px 20px", fontSize: 12 }}>
          {downloading ? "Exporting…" : "⬇ Download .TRC Log"}
        </window.Btn>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
        {[
          ["Total Flashes", sessionLog.length, "var(--text-primary)"],
          ["✓ Successful", successCnt, "#059669"],
          ["✗ Failed", failCnt, "#DC2626"],
          ["Total Flash Time", window.fmtMs(totalMs), "var(--accent-blue)"]
        ].map(([label,val,color]) => (
          <window.Card key={label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 30, fontWeight: 700, color }}>{val}</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 4 }}>{label}</div>
          </window.Card>
        ))}
      </div>
      <window.Card>
        <window.SectionLabel>Complete Flash History</window.SectionLabel>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ color: "#64748B", borderBottom: "1px solid #E2E8F0" }}>
              {["#","SW File","Timestamp","Duration","Result"].map(h => <th key={h} style={{ textAlign: "left", padding: "6px 12px 6px 0", fontWeight: 500, fontSize: 11 }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {sessionLog.length === 0
              ? <tr><td colSpan={5} style={{ textAlign: "center", color: "#64748B", padding: 20, fontSize: 13 }}>No flash history yet.</td></tr>
              : sessionLog.map((e, i) => (
                <tr key={e.id} style={{ borderBottom: "1px solid #E2E8F0", color: "var(--text-primary)" }}>
                  <td style={{ padding: "7px 12px 7px 0", color: "#64748B" }}>{sessionLog.length - i}</td>
                  <td style={{ padding: "7px 12px 7px 0", fontFamily: "monospace", fontSize: 11 }}>{e.swFile}</td>
                  <td style={{ padding: "7px 12px 7px 0", fontSize: 11 }}>{e.timestamp}</td>
                  <td style={{ padding: "7px 12px 7px 0" }}>{e.duration}</td>
                  <td style={{ padding: "7px 0" }}><window.Badge type={e.status} /></td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </window.Card>
    </window.Container>
  );
};
"""
