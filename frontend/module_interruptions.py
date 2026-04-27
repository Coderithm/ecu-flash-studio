INTERRUPTIONS_JSX = r"""
window.InterruptionTests = function({ flashOp, sessionLog }) {
  const tests = flashOp.interruption_tests || [];
  const lastResult = flashOp.last_interruption_result;
  const running = flashOp.running;
  const progress = flashOp.progress || 0;

  function runTest(id) {
    fetch('/api/run_interruption_test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test_id: id })
    });
  }

  function runAll() {
    // Simply fire them off sequentially if we wanted, but let's just do one for now
    if (tests.length > 0) runTest(tests[0].id);
  }

  return (
    <window.Container>
      <h2 style={{ color: "#f1f5f9", margin: 0, fontSize: 20, fontWeight: 700 }}>Flashing Interruption Tests</h2>

      {lastResult && (
        <div style={{ background: lastResult.interrupted ? "rgba(234,88,12,0.1)" : "rgba(220,38,38,0.1)", border: `1px solid ${lastResult.interrupted ? "#ea580c" : "#dc2626"}`, borderRadius: 12, padding: 16, display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontSize: 30 }}>{lastResult.interrupted ? "⚡" : "✗"}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: lastResult.interrupted ? "#fdba74" : "#fca5a5" }}>
              {lastResult.interrupted ? "Interruption Detected — ECU Responded Correctly" : "Flash Failed — No Interruption Detected"}
            </div>
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
              {lastResult.interrupted ? "Negative Response (NRC 0x70 / 0x72) received — interruption test PASSED" : "Unexpected failure — check ECU logs"}
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.3)", borderRadius: 12, padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 24 }}>✅</span>
          <div>
            <div style={{ color: "#34d399", fontWeight: 700, fontSize: 13 }}>Positive Response</div>
            <div style={{ fontSize: 11, color: "#94a3b8" }}>0x78 / 0x67 — Flash completed successfully</div>
          </div>
        </div>
        <div style={{ background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.3)", borderRadius: 12, padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 24 }}>❌</span>
          <div>
            <div style={{ color: "#f87171", fontWeight: 700, fontSize: 13 }}>Negative Response</div>
            <div style={{ fontSize: 11, color: "#94a3b8" }}>NRC 0x70 / 0x72 — Flash failed or interrupted</div>
          </div>
        </div>
      </div>

      <window.Card>
        <div style={{ display: "flex", alignItems: "center", marginBottom: 14 }}>
          <window.SectionLabel style={{ flex: 1, margin: 0 }}>Test Cases</window.SectionLabel>
          <window.Btn onClick={runAll} disabled={running} color="#c2410c">Run Sequence</window.Btn>
        </div>
        {running && flashOp.swFile && flashOp.swFile.includes("Interruption") && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>
              <span>Running {flashOp.swFile}…</span><span>{Math.round(progress)}%</span>
            </div>
            <div style={{ width: "100%", background: "#334155", borderRadius: 9999, height: 8 }}>
              <div style={{ width: `${progress}%`, height: 8, background: "#f97316", borderRadius: 9999, transition: "width 0.25s" }} />
            </div>
          </div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {tests.map(t => (
            <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 12, background: "#0f172a", borderRadius: 8, padding: "10px 14px", border: "1px solid #334155" }}>
              <span style={{ fontSize: 11, color: "#475569", width: 16 }}>{t.id}</span>
              <span style={{ flex: 1, fontSize: 13, color: "#cbd5e1" }}>{t.name}</span>
              <window.Badge type={running && flashOp.swFile && flashOp.swFile.includes(t.name) ? "running" : t.status} />
              <window.Btn onClick={() => runTest(t.id)} disabled={running} color="#334155" style={{ padding: "4px 12px", fontSize: 11 }}>Run</window.Btn>
            </div>
          ))}
        </div>
      </window.Card>

      <window.Card>
        <window.SectionLabel>Recent Flash Results</window.SectionLabel>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ color: "#64748b", borderBottom: "1px solid #334155" }}>
              {["SW File","Timestamp","Duration","Result"].map(h => <th key={h} style={{ textAlign: "left", padding: "6px 12px 6px 0", fontWeight: 500, fontSize: 11 }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {sessionLog.slice(0, 6).map(e => (
              <tr key={e.id} style={{ borderBottom: "1px solid rgba(51,65,85,0.4)", color: "#cbd5e1" }}>
                <td style={{ padding: "7px 12px 7px 0", fontFamily: "monospace", fontSize: 11 }}>{e.swFile}</td>
                <td style={{ padding: "7px 12px 7px 0", fontSize: 11 }}>{e.timestamp}</td>
                <td style={{ padding: "7px 12px 7px 0" }}>{e.duration}</td>
                <td style={{ padding: "7px 0" }}><window.Badge type={e.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </window.Card>
    </window.Container>
  );
};
"""
