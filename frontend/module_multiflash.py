MULTIFLASH_JSX = r"""
window.MultiFlash = function({ flashOp, sessionLog }) {
  const { useState, useEffect, useRef } = React;
  
  const [plan, setPlan] = useState(() => (
    Array.from({ length: 10 }, (_, i) => ({
      enabled: i === 0,
      fileObj: null,
      fileName: "",
      priority: null
    }))
  ));
  
  const [times, setTimes] = useState(1);
  const running = flashOp?.running || false;

  const prevSessionLogRef = useRef(0);

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
    fetch('/api/start_multiflash', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ files: filesData, times: times }) });
  }

  const opsCount = buildOps().length; const canStart = !running && opsCount > 0;
  const successCount = sessionLog.filter(e => e.status === "success").length;
  const failCount = sessionLog.filter(e => e.status === "failed").length;

  const opRunning = !!flashOp?.running;
  const opPct = Math.min(100, Math.max(0, flashOp?.progress ?? 0));
  const opElapsed = flashOp?.elapsedMs ?? 0;
  const opCycle = flashOp?.cycle ?? 0;
  const opTotal = flashOp?.total ?? 0;
  const opFile = flashOp?.swFile ?? "—";
  
  const totalLogTimeSec = sessionLog.reduce((acc, log) => acc + (parseFloat(log.duration) || 0), 0);
  const totalLogTimeStr = window.fmtMs ? window.fmtMs(totalLogTimeSec * 1000) : `${totalLogTimeSec.toFixed(1)}s`;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: -10 }}>
      <style>{`
        input[type=number]::-webkit-inner-spin-button,
        input[type=number]::-webkit-outer-spin-button {
          opacity: 1 !important;
        }
      `}</style>
      <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 22, fontWeight: 700 }}>Multi-Flash Queue</h2>
      
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 12 }}>
        {/* Left Column: Local File Selection */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <window.Card>
            <window.SectionLabel>Local File Selection</window.SectionLabel>
            <div style={{ fontSize: 11, color: "#64748B", marginBottom: 8 }}>Pick files and assign absolute sequence priorities (1-10).</div>
            <div style={{ border: "1px solid rgba(51,65,85,0.6)", borderRadius: 8, overflow: "hidden", background: "#F8FAFC", marginBottom: 12, marginTop: 8, maxHeight: 220, overflowY: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead style={{ position: "sticky", top: 0, background: "#F8FAFC", zIndex: 1 }}><tr style={{ color: "#64748B", borderBottom: "1px solid #E2E8F0" }}><th style={{ width: 30, padding: 4 }}>Use</th><th style={{ width: 60, padding: 4 }}>Sequence</th><th style={{ padding: 4, textAlign: "left" }}>Select Local Hex File</th></tr></thead>
                <tbody>
                  {plan.map((row, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #E2E8F0" }}>
                      <td style={{ padding: 4, textAlign: "center" }}><input type="checkbox" checked={row.enabled} disabled={running} onChange={e => handleEnableChange(i, e.target.checked)} style={{ width: 14, height: 14, accentColor: "#10b981" }} /></td>
                      <td style={{ padding: 4, color: "#64748B", fontFamily: "monospace", textAlign: "center" }}>
                        <select value={row.priority || ""} disabled={!row.enabled || running} onChange={e => handlePriorityChange(i, e.target.value)} className={`bg-slate-900 border border-slate-700/50 rounded p-1 text-xs outline-none focus:border-blue-500 ${!row.enabled ? 'opacity-50' : 'text-slate-200'}`}>
                          <option value="">--</option>
                          {[1,2,3,4,5,6,7,8,9,10].map(n => {
                            const isUsedByOther = plan.some((r, idx) => r.enabled && r.priority === n && idx !== i);
                            return <option key={n} value={n} disabled={isUsedByOther} className={isUsedByOther ? "text-slate-600 bg-slate-800" : "text-slate-200"}>Seq {n}</option>;
                          })}
                        </select>
                      </td>
                      <td style={{ padding: 4 }}><input type="file" accept=".hex,.bin" disabled={running} onChange={e => handleFileChange(i, e)} className="text-[10px] text-slate-300 file:mr-2 file:py-1 file:px-2 file:rounded-full file:border-0 file:text-[10px] file:font-semibold file:bg-blue-500/20 file:text-blue-400 hover:file:bg-blue-500/30 transition shadow-none cursor-pointer outline-none w-full" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>Repeat Sequence Array (up to 100k)</div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ flex: 1 }}><input type="range" min={1} max={100000} value={times} onChange={e => setTimes(+e.target.value)} disabled={running} style={{ width: "100%", outline: "none" }} className="accent-[#1e3a8a]" /></div>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <input type="number" min={1} max={100000} value={times} onChange={e => { let v = parseInt(e.target.value); if (isNaN(v)) v = 1; if (v > 100000) v = 100000; if (v < 1) v = 1; setTimes(v); }} disabled={running} style={{ background: "#ffffff", border: "1px solid #CBD5E1", borderRadius: 4, color: "#000000", fontWeight: "bold", width: 70, outline: "none", fontSize: 12, textAlign: "right", height: 24 }} />
                  <span className="text-slate-500 text-xs font-medium">loops</span>
                </div>
              </div>
            </div>
            <window.Btn onClick={startFlashing} disabled={!canStart} className="w-full py-1 text-[12px]">
              {running ? `Execution in Progress (${flashOp?.cycle || 0}/${flashOp?.total || 0})...` : "▶ Begin Hardware Flashing"}
            </window.Btn>
          </window.Card>
        </div>

        {/* Right Column: Progress & Current Flash Operation */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <window.Card>
            <div style={{ marginBottom: 12 }}>
              <window.SectionLabel style={{ margin: 0, whiteSpace: "nowrap" }}>Flashing Progress</window.SectionLabel>
            </div>
            
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}><span style={{ color: "#64748B" }}>Master Sequence</span><span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{Math.round(flashOp?.total_progress || 0)}%</span></div>
              <div style={{ width: "100%", background: "#E2E8F0", borderRadius: 9999, height: 8, overflow: "hidden" }}>
                <div className={running ? "progress-stripes animate-stripe-slide" : ""} style={{ width: `${!running && (flashOp?.total_progress || 0) >= 99.5 ? 100 : Math.max(0, Math.min(100, flashOp?.total_progress || 0))}%`, height: "100%", background: "var(--accent-blue)", transition: "width 0.4s" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748B", marginTop: 4 }}><span>ETA: <span className={`font-mono font-bold ${opRunning && flashOp?.eta_seconds >= 0 ? "text-emerald-500" : "text-slate-500"}`}>{opRunning ? (flashOp?.eta_seconds >= 0 ? window.fmtMs(flashOp.eta_seconds * 1000) : "Calculating...") : "—"}</span></span><span>Flashes: <span className="font-bold text-slate-400">{flashOp?.cycle || 0}</span> / <span className="font-bold text-slate-400">{flashOp?.total || 0}</span></span></div>
            </div>

            <div>
              <window.SectionLabel style={{ margin: "0 0 6px 0", fontSize: 10, color: "#94a3b8" }}>Active Component Segment</window.SectionLabel>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748B", marginBottom: 4 }}><span className="font-mono text-indigo-400 truncate max-w-[200px]" title={flashOp?.swFile}>{flashOp?.swFile}</span><span className="font-bold text-slate-400">{Math.round(flashOp?.progress || 0)}%</span></div>
              <div style={{ width: "100%", background: "#E2E8F0", borderRadius: 9999, height: 6, overflow: "hidden" }}>
                <div className="progress-stripes animate-stripe-slide" style={{ width: `${flashOp?.progress || 0}%`, height: "100%", background: "var(--accent-primary)", transition: "width 0.2s" }} />
              </div>
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, paddingTop: 10, borderTop: "1px solid #E2E8F0" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#059669" }}>Successful: {successCount}</div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#DC2626" }}>Failed: {failCount}</div>
            </div>
          </window.Card>

          <window.Card style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <window.SectionLabel>Current Flash Operation</window.SectionLabel>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
              {!opRunning ? (
                <div style={{ fontSize: 11, color: "#64748B", padding: "8px 0" }}>No flashing operation running.</div>
              ) : (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
                    <div style={{ fontFamily: "monospace", fontSize: 14, fontWeight: 800, color: "var(--accent-primary)" }}>{window.fmtMs(opElapsed)}</div>
                    <div style={{ fontSize: 11, color: "#64748B", fontWeight: 700 }}>{opCycle}/{opTotal}</div>
                  </div>
                  <div style={{ width: "100%", background: "#E2E8F0", borderRadius: 9999, height: 8, marginBottom: 8, overflow: "hidden" }}>
                    <div className="progress-stripes animate-stripe-slide" style={{ width: `${opPct}%`, height: "100%", background: "var(--accent-primary)", transition: "width 0.15s" }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748B" }}>
                    <span style={{ fontFamily: "monospace", maxWidth: "120px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{opFile}</span>
                    <span className="font-bold">{Math.round(opPct)}%</span>
                  </div>
                </>
              )}
            </div>
          </window.Card>
        </div>
      </div>

      {/* Bottom Row: Flash Log */}
      <window.Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <window.SectionLabel style={{ margin: 0 }}>Flash Log</window.SectionLabel>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600 }}>Total Time: <span style={{ color: "var(--accent-primary)" }}>{totalLogTimeStr}</span></div>
            <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600 }}>Total Flashes: <span style={{ color: "var(--accent-blue)" }}>{sessionLog.length}</span></div>
            <window.Btn onClick={() => {
              const csv = ["File Processed,Execution Timestamp,Time Elapsed,Result\n", ...sessionLog.map(e => `${e.swFile},${e.timestamp},${e.duration},${e.status}`)].join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url; a.download = 'flash_log.csv'; a.click();
            }} style={{ padding: "4px 8px", fontSize: 11 }}>Download Log</window.Btn>
          </div>
        </div>
        <div style={{ border: "1px solid rgba(51,65,85,0.6)", borderRadius: 8, overflow: "hidden", background: "#F8FAFC", maxHeight: 110, overflowY: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead style={{ position: "sticky", top: 0, background: "#F8FAFC", zIndex: 1 }}>
              <tr style={{ color: "#64748B", borderBottom: "1px solid #E2E8F0" }}>
                {["File Processed", "Execution Timestamp", "Time Elapsed", "Result"].map(h => <th key={h} style={{ textAlign: "left", padding: "8px 12px", fontWeight: 500 }}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {sessionLog.length === 0 ? <tr><td colSpan={4} style={{ textAlign: "center", color: "#64748B", padding: "16px", fontSize: 12 }}>Waiting for backend Python events...</td></tr> : sessionLog.map(e => (
                <tr key={e.id} style={{ borderBottom: "1px solid #E2E8F0" }}>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "var(--accent-blue)" }}>{e.swFile}</td>
                  <td style={{ padding: "8px 12px", color: "var(--text-primary)" }}>{e.timestamp}</td>
                  <td style={{ padding: "8px 12px", color: "var(--text-primary)" }}>{e.duration}</td>
                  <td style={{ padding: "8px 12px" }}><window.Badge type={e.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </window.Card>
    </div>
  );
};
"""
