INTERRUPTIONS_JSX = r"""
window.InterruptionTests = function({ flashOp, sessionLog }) {
  const { useState } = React;
  const tests = flashOp.interruption_tests || [];
  const lastResult = flashOp.last_interruption_result;
  const running = flashOp.running;
  const progress = flashOp.progress || 0;
  
  const currentRunningTest = tests.find(t => t.status === "running");
  const activeTestId = lastResult ? lastResult.testId : null;
  const activeTest = tests.find(t => t.id === activeTestId);
  const displayTest = currentRunningTest || activeTest || null;

  const [hexFile, setHexFile] = useState({ fileObj: null, fileName: "", data_b64: "" });

  function handleFileChange(e) {
    const f = e.target.files[0];
    if (f) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        setHexFile({ fileObj: f, fileName: f.name, data_b64: ev.target.result.split(',')[1] || "" });
      };
      reader.readAsDataURL(f);
    } else {
      setHexFile({ fileObj: null, fileName: "", data_b64: "" });
    }
  }

  function runTest(id) {
    if (!hexFile.fileName) {
      if (window.showToast) window.showToast("Please select a HEX file first", "error");
      else alert("Please select a HEX file first");
      return;
    }
    fetch('/api/run_interruption_test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        test_id: id, 
        file: { name: hexFile.fileName, data_b64: hexFile.data_b64 } 
      })
    });
  }

  let passFailDisplay = null;
  if (!running && lastResult) {
    const passed = lastResult.interrupted;
    passFailDisplay = (
      <div style={{ background: passed ? "rgba(16,185,129,0.15)" : "rgba(220,38,38,0.15)", border: `1px solid ${passed ? "#10b981" : "#ef4444"}`, borderRadius: 8, padding: "8px 16px", display: "inline-flex", alignItems: "center", gap: 8, marginTop: 10 }}>
        <span style={{ fontSize: 20 }}>{passed ? "✅" : "❌"}</span>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: 13, fontWeight: 800, color: passed ? "#059669" : "#b91c1c" }}>{passed ? "TEST PASSED" : "TEST FAILED"}</span>
        </div>
      </div>
    );
  }

  return (
    <window.Container>
      <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 24, fontWeight: 800, display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 28 }}>⚡</span> Interruption Tests
      </h2>

      {/* TOP SECTION: Active State & Progress */}
      <window.Card style={{ borderTop: "4px solid #0ea5e9" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 24 }}>
          
          {/* Left: Info & File */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "#64748B", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>Active Test Case</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: displayTest ? "var(--accent-blue)" : "#94A3B8" }}>
                  {displayTest ? displayTest.name : "None Selected"}
                </div>
              </div>
              <div style={{ background: running ? "rgba(14,165,233,0.1)" : "#F1F5F9", padding: "6px 12px", borderRadius: 8, display: "flex", alignItems: "center", gap: 8, border: `1px solid ${running ? "#38bdf8" : "#E2E8F0"}` }}>
                <span className={running ? "animate-pulse" : ""} style={{ width: 8, height: 8, borderRadius: "50%", background: running ? "#38bdf8" : "#94A3B8" }}></span>
                <span style={{ fontSize: 12, fontWeight: 700, color: running ? "#0284c7" : "#64748B" }}>{running ? "Flashing Active" : "ECU Idle"}</span>
              </div>
            </div>

            <div style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 11, color: "#64748B", fontWeight: 700, textTransform: "uppercase", marginBottom: 6 }}>Firmware File Selection</div>
              <input type="file" accept=".hex" disabled={running} onChange={handleFileChange} className="text-[12px] text-slate-600 file:mr-3 file:py-1.5 file:px-4 file:rounded-full file:border-0 file:text-[11px] file:font-semibold file:bg-sky-50 file:text-sky-600 hover:file:bg-sky-100 transition cursor-pointer outline-none w-full" />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{ background: "rgba(245,158,11,0.05)", border: "1px dashed rgba(245,158,11,0.3)", borderRadius: 8, padding: 10 }}>
                <div style={{ fontSize: 10, color: "#d97706", fontWeight: 700, textTransform: "uppercase", marginBottom: 2 }}>Expected Behavior</div>
                <div style={{ fontSize: 12, color: "#78350f", fontWeight: 500 }}>{displayTest ? "NRC 0x70 / 0x72 received safely" : "—"}</div>
              </div>
              <div style={{ background: "rgba(16,185,129,0.05)", border: "1px dashed rgba(16,185,129,0.3)", borderRadius: 8, padding: 10 }}>
                <div style={{ fontSize: 10, color: "#059669", fontWeight: 700, textTransform: "uppercase", marginBottom: 2 }}>Actual Behavior</div>
                <div style={{ fontSize: 12, color: "#064e3b", fontWeight: 500 }}>
                  {running ? "Testing in progress..." : (lastResult ? (lastResult.interrupted ? "Interruption Detected (NRC 0x70)" : "Fatal Error / No Response") : "—")}
                </div>
              </div>
            </div>
          </div>

          {/* Right: Progress & Status */}
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", borderLeft: "1px solid #E2E8F0", paddingLeft: 24 }}>
            <div style={{ width: "100%", marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 700, color: "#64748B", marginBottom: 6 }}>
                <span>Flash Progress</span>
                <span style={{ color: "var(--accent-blue)" }}>{Math.round(progress)}%</span>
              </div>
              <div style={{ width: "100%", background: "#E2E8F0", borderRadius: 9999, height: 14, overflow: "hidden", boxShadow: "inset 0 1px 3px rgba(0,0,0,0.1)" }}>
                <div className={running ? "progress-stripes animate-stripe-slide" : ""} style={{ width: `${progress}%`, height: "100%", background: "linear-gradient(90deg, #0ea5e9, #3b82f6)", transition: "width 0.3s" }} />
              </div>
            </div>
            
            <div style={{ minHeight: 60, display: "flex", alignItems: "center", justifyContent: "center", width: "100%" }}>
              {passFailDisplay}
              {running && (
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10 }}>
                  <div className="animate-spin" style={{ width: 20, height: 20, border: "3px solid #E2E8F0", borderTopColor: "#0ea5e9", borderRadius: "50%" }}></div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#0ea5e9" }}>Executing Test...</span>
                </div>
              )}
            </div>
          </div>

        </div>
      </window.Card>

      {/* BOTTOM SECTION: Test Cases List */}
      <window.Card>
        <window.SectionLabel>Available Interruption Scenarios</window.SectionLabel>
        <div style={{ fontSize: 12, color: "#64748B", marginBottom: 16 }}>
          Select a test case below. The system will flash the chosen HEX file and inject the fault at the appropriate diagnostic sequence.
        </div>
        
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
          {tests.map(t => (
            <button key={t.id} onClick={() => runTest(t.id)} disabled={running}
              className="relative overflow-hidden group text-left"
              style={{
                background: running ? "#F8FAFC" : "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 12,
                padding: "16px",
                cursor: running ? "not-allowed" : "pointer",
                transition: "all 0.2s",
                boxShadow: running ? "none" : "0 2px 4px rgba(0,0,0,0.02)",
                opacity: running ? 0.6 : 1
              }}
              onMouseEnter={e => { if(!running) { e.currentTarget.style.borderColor = "#0ea5e9"; e.currentTarget.style.boxShadow = "0 4px 12px rgba(14,165,233,0.1)"; } }}
              onMouseLeave={e => { if(!running) { e.currentTarget.style.borderColor = "#E2E8F0"; e.currentTarget.style.boxShadow = "0 2px 4px rgba(0,0,0,0.02)"; } }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div style={{ background: "#F1F5F9", color: "#64748B", fontWeight: 800, fontSize: 11, padding: "4px 8px", borderRadius: 6 }}>#{t.id}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4, lineHeight: 1.3 }}>{t.name}</div>
                  <div style={{ fontSize: 11, color: "#94A3B8" }}>Injects fault during operation to verify ECU recovery logic.</div>
                </div>
              </div>
              
              {!running && (
                <div className="absolute inset-0 bg-sky-50/0 group-hover:bg-sky-50/50 transition-colors pointer-events-none" />
              )}
            </button>
          ))}
        </div>
      </window.Card>
      
    </window.Container>
  );
};
"""
