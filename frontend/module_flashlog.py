FLASHLOG_JSX = r"""
window.FlashLog = function({ sessionLog }) {
  const successCnt = sessionLog.filter(e => e.status === "success").length;
  const failCnt    = sessionLog.filter(e => e.status === "failed").length;
  
  // Parse duration like "0.5s" back to MS. E.g. "0.5s" -> 0.5 * 1000 = 500ms
  const totalMs = sessionLog.reduce((acc, e) => {
    let secs = parseFloat((e.duration || "0").replace('s', ''));
    if (isNaN(secs)) secs = 0;
    return acc + (secs * 1000);
  }, 0);

  return (
    <window.Container>
      <h2 style={{ color: "#f1f5f9", margin: 0, fontSize: 20, fontWeight: 700 }}>Flash Log</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
        {[
          ["Total Flashes", sessionLog.length, "#f1f5f9"],
          ["✓ Successful", successCnt, "#34d399"],
          ["✗ Failed", failCnt, "#f87171"],
          ["Total Flash Time", window.fmtMs(totalMs), "#93c5fd"]
        ].map(([label,val,color]) => (
          <window.Card key={label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 30, fontWeight: 700, color }}>{val}</div>
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>{label}</div>
          </window.Card>
        ))}
      </div>
      <window.Card>
        <window.SectionLabel>Complete Flash History</window.SectionLabel>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ color: "#64748b", borderBottom: "1px solid #334155" }}>
              {["#","SW File","Timestamp","Duration","Result"].map(h => <th key={h} style={{ textAlign: "left", padding: "6px 12px 6px 0", fontWeight: 500, fontSize: 11 }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {sessionLog.length === 0
              ? <tr><td colSpan={5} style={{ textAlign: "center", color: "#475569", padding: 20, fontSize: 13 }}>No flash history yet.</td></tr>
              : sessionLog.map((e, i) => (
                <tr key={e.id} style={{ borderBottom: "1px solid rgba(51,65,85,0.4)", color: "#cbd5e1" }}>
                  <td style={{ padding: "7px 12px 7px 0", color: "#475569" }}>{sessionLog.length - i}</td>
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
