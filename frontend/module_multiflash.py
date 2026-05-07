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
  const [starting, setStarting] = useState(false);
  const [failedDropOpen, setFailedDropOpen] = useState(false);
  const running = flashOp?.running || false;
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 });

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
    setStarting(true);
    try {
    const filePromises = ops.map(r => new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve({ name: r.fileName, data_b64: e.target.result.split(',')[1] || "" });
      reader.onerror = () => reject(new Error(`Unable to read ${r.fileName}`));
      reader.readAsDataURL(r.fileObj);
    }));
    const filesData = await Promise.all(filePromises);
    const res = await fetch('/api/start_multiflash', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ files: filesData, times: times }) });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || json.started === false) {
      const msg = running ? "Flash engine is already running." : "Unable to start flashing. Check selected files.";
      if (window.showToast) window.showToast(msg, "error"); else alert(msg);
    }
    } catch (e) {
      const msg = e?.message || "Unable to read selected files.";
      if (window.showToast) window.showToast(msg, "error"); else alert(msg);
    } finally {
      setStarting(false);
    }
  }

  async function stopFlashing() {
    await fetch('/api/stop_multiflash', { method: 'POST' });
  }

  const opsCount = buildOps().length; const canStart = !running && !starting && opsCount > 0;
  const successCount = sessionLog.filter(e => e.status === "success").length;
  const failCount = sessionLog.filter(e => e.status === "failed").length;
  const failedFlashes = flashOp?.failedFlashes || [];

  const opRunning = !!flashOp?.running;
  
  const totalLogTimeSec = sessionLog.reduce((acc, log) => acc + (parseFloat(log.duration) || 0), 0);
  const totalLogTimeStr = window.fmtMs ? window.fmtMs(totalLogTimeSec * 1000) : `${totalLogTimeSec.toFixed(1)}s`;
  const avgTimeSec = sessionLog.length > 0 ? (totalLogTimeSec / sessionLog.length) : 0;
  const avgTimeStr = sessionLog.length > 0 ? (window.fmtMs ? window.fmtMs(avgTimeSec * 1000) : `${avgTimeSec.toFixed(1)}s`) : "\u2014";

  // Scatter graph rendering
  const canvasRef = useRef(null);
  const wrapperRef = useRef(null);

  useEffect(() => {
    const ro = new ResizeObserver(entries => {
      for (let entry of entries) {
        setCanvasSize({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
    });
    if (wrapperRef.current) ro.observe(wrapperRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || canvasSize.w === 0) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width;
    const H = rect.height;
    
    ctx.clearRect(0, 0, W, H);
    
    // Draw background grid
    ctx.strokeStyle = '#E2E8F0';
    ctx.lineWidth = 0.5;
    const gridLines = [30, 60, 90, 120];
    const maxY = 150;
    for (const gl of gridLines) {
      const y = H - (gl / maxY) * (H - 24) - 2;
      ctx.beginPath();
      ctx.moveTo(40, y);
      ctx.lineTo(W - 8, y);
      ctx.stroke();
      ctx.fillStyle = '#94A3B8';
      ctx.font = '9px Inter, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(`${gl}s`, 36, y + 3);
    }
    
    // Draw Y axis base
    ctx.fillStyle = '#94A3B8';
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText('0s', 36, H - 2);
    
    // Plot data points (oldest first = left to right)
    const data = [...sessionLog].reverse();
    if (data.length === 0) {
      ctx.fillStyle = '#94A3B8';
      ctx.font = '11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No flash data yet', W / 2, H / 2);
      return;
    }
    
    const usableW = W - 48;
    const spacing = data.length > 1 ? usableW / (data.length - 1) : 0;
    
    for (let i = 0; i < data.length; i++) {
      const e = data[i];
      const durSec = parseFloat(e.duration) || (e.duration_ms ? e.duration_ms / 1000 : 0);
      const x = data.length === 1 ? W / 2 : 44 + i * spacing;
      const y = H - (Math.min(durSec, maxY) / maxY) * (H - 24) - 2;
      
      let color;
      if (durSec < 30) color = '#10b981';
      else if (durSec < 60) color = '#f59e0b';
      else color = '#38bdf8';
      
      // Glow
      ctx.beginPath();
      ctx.arc(x, y, 8, 0, Math.PI * 2);
      ctx.fillStyle = color + '30';
      ctx.fill();
      
      // Dot
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }
    
    // Draw legend (top-right)
    const legendY = 10;
    const legends = [
      { color: '#10b981', label: '< 30s' },
      { color: '#f59e0b', label: '30-60s' },
      { color: '#38bdf8', label: '> 60s' }
    ];
    let lx = W - 8;
    ctx.font = '9px Inter, sans-serif';
    for (let li = legends.length - 1; li >= 0; li--) {
      const l = legends[li];
      const tw = ctx.measureText(l.label).width;
      lx -= tw;
      ctx.fillStyle = '#64748B';
      ctx.textAlign = 'left';
      ctx.fillText(l.label, lx, legendY + 4);
      lx -= 12;
      ctx.beginPath();
      ctx.arc(lx + 4, legendY, 4, 0, Math.PI * 2);
      ctx.fillStyle = l.color;
      ctx.fill();
      lx -= 8;
    }
  }, [sessionLog, canvasSize]);

  async function downloadTrace(logId, fileName) {
    try {
      const res = await fetch(`/api/export_trc_file?log_id=${logId}`);
      if (res.status === 204) { alert('No trace data for this flash'); return; }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${fileName.replace(/\.[^.]+$/, '')}_trace.trc`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch(e) { alert('Failed to download trace'); }
  }

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
          <window.Card style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <window.SectionLabel>Local File Selection</window.SectionLabel>
            <div style={{ fontSize: 11, color: "#64748B", marginBottom: 8 }}>Pick files and assign absolute sequence priorities (1-10).</div>
            <div style={{ flex: 1, border: "1px solid rgba(51,65,85,0.6)", borderRadius: 8, overflow: "hidden", background: "#F8FAFC", marginBottom: 12, marginTop: 8, minHeight: 150, overflowY: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
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
                      <td style={{ padding: 4 }}><input type="file" accept=".hex" disabled={running || starting} onChange={e => handleFileChange(i, e)} className="text-[10px] text-slate-300 file:mr-2 file:py-1 file:px-2 file:rounded-full file:border-0 file:text-[10px] file:font-semibold file:bg-blue-500/20 file:text-blue-400 hover:file:bg-blue-500/30 transition shadow-none cursor-pointer outline-none w-full" /></td>
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
            <div style={{ display: "flex", gap: 8 }}>
              <window.Btn onClick={startFlashing} disabled={!canStart} className="py-1 text-[12px]" style={{ flex: 1 }}>
                {starting ? "Preparing files..." : (running ? `Execution in Progress (${flashOp?.cycle || 0}/${flashOp?.total || 0})...` : "\u25b6 Begin Hardware Flashing")}
              </window.Btn>
              {running && (
                <window.Btn onClick={stopFlashing} className="py-1 text-[12px]" style={{ background: "#0ea5e9" }}>
                  \u23f9 Force Stop
                </window.Btn>
              )}
            </div>
          </window.Card>
        </div>

        {/* Right Column: Progress & Flash Time Scatter */}
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
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748B", marginTop: 4 }}><span>ETA: <span className={`font-mono font-bold ${opRunning && flashOp?.eta_seconds >= 0 ? "text-emerald-500" : "text-slate-500"}`}>{opRunning ? (flashOp?.eta_seconds >= 0 ? window.fmtMs(flashOp.eta_seconds * 1000) : "Calculating...") : "\u2014"}</span></span><span>Flashes: <span className="font-bold text-slate-400">{flashOp?.cycle || 0}</span> / <span className="font-bold text-slate-400">{flashOp?.total || 0}</span></span></div>
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
              <div style={{ position: "relative" }}>
                <button onClick={() => setFailedDropOpen(p => !p)} style={{ fontSize: 11, fontWeight: 700, color: "#ef4444", background: failedFlashes.length > 0 ? "rgba(239,68,68,0.08)" : "transparent", border: failedFlashes.length > 0 ? "1px solid rgba(239,68,68,0.25)" : "1px solid transparent", borderRadius: 6, padding: "2px 10px", cursor: failedFlashes.length > 0 ? "pointer" : "default", transition: "all 0.15s", display: "flex", alignItems: "center", gap: 4 }}>
                  Failed: {failCount} {failedFlashes.length > 0 && <span style={{ fontSize: 9, opacity: 0.7 }}>{failedDropOpen ? "\u25b2" : "\u25bc"}</span>}
                </button>
                {failedDropOpen && failedFlashes.length > 0 && (
                  <div style={{ position: "absolute", bottom: "100%", right: 0, marginBottom: 6, background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 10, boxShadow: "0 8px 24px rgba(0,0,0,0.12)", zIndex: 100, minWidth: 280, maxHeight: 200, overflowY: "auto", padding: 0 }}>
                    <div style={{ padding: "10px 14px", borderBottom: "1px solid #E2E8F0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "#1E293B" }}>Failed Flash Sequences</span>
                      <span style={{ fontSize: 10, color: "#ef4444", fontWeight: 600, background: "rgba(239,68,68,0.1)", borderRadius: 9999, padding: "1px 8px" }}>{failedFlashes.length}</span>
                    </div>
                    {failedFlashes.map((f, i) => (
                      <div key={i} style={{ padding: "8px 14px", borderBottom: "1px solid #F1F5F9", display: "flex", gap: 10, alignItems: "flex-start", fontSize: 11 }}>
                        <span style={{ fontWeight: 800, color: "#ef4444", fontFamily: "monospace", minWidth: 30 }}>#{f.seq}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontFamily: "monospace", color: "#0284c7", fontWeight: 600 }}>{f.file}</div>
                          <div style={{ fontSize: 10, color: "#94A3B8", marginTop: 2 }}>{f.error || "Unknown error"}</div>
                          <div style={{ fontSize: 9, color: "#CBD5E1", marginTop: 1 }}>{f.timestamp}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </window.Card>

          <window.Card style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <window.SectionLabel>Flash Time Distribution</window.SectionLabel>
            <div ref={wrapperRef} style={{ flex: 1, minHeight: 110 }}>
              <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
            </div>
          </window.Card>
        </div>
      </div>

      {/* Bottom Row: Flash Log */}
      <window.Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <window.SectionLabel style={{ margin: 0 }}>Flash Log</window.SectionLabel>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600 }}>Avg Time: <span style={{ color: "#6366f1", fontWeight: 700 }}>{avgTimeStr}</span></div>
            <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600 }}>Total Time: <span style={{ color: "var(--accent-primary)" }}>{totalLogTimeStr}</span></div>
            <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600 }}>Total Flashes: <span style={{ color: "var(--accent-blue)" }}>{sessionLog.length}</span></div>
          </div>
        </div>
        <div style={{ border: "1px solid rgba(51,65,85,0.6)", borderRadius: 8, overflow: "hidden", background: "#F8FAFC", maxHeight: 110, overflowY: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead style={{ position: "sticky", top: 0, background: "#F8FAFC", zIndex: 1 }}>
              <tr style={{ color: "#64748B", borderBottom: "1px solid #E2E8F0" }}>
                {["File Processed", "Execution Timestamp", "Time Elapsed", "Result", "Trace"].map(h => <th key={h} style={{ textAlign: "left", padding: "8px 12px", fontWeight: 500 }}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {sessionLog.length === 0 ? <tr><td colSpan={5} style={{ textAlign: "center", color: "#64748B", padding: "16px", fontSize: 12 }}>Waiting for backend Python events...</td></tr> : sessionLog.slice(0, 3).map(e => (
                <tr key={e.id} style={{ borderBottom: "1px solid #E2E8F0" }}>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "var(--accent-blue)" }}>{e.swFile}</td>
                  <td style={{ padding: "8px 12px", color: "var(--text-primary)" }}>{e.timestamp}</td>
                  <td style={{ padding: "8px 12px", color: "var(--text-primary)" }}>{e.duration}</td>
                  <td style={{ padding: "8px 12px" }}><window.Badge type={e.status} /></td>
                  <td style={{ padding: "8px 12px" }}>
                    <button onClick={() => downloadTrace(e.id, e.swFile)} style={{ background: "none", border: "1px solid #CBD5E1", borderRadius: 4, padding: "2px 8px", fontSize: 10, color: "#1E40AF", cursor: "pointer", fontWeight: 600, transition: "all 0.15s" }} title="Download .trc trace for this flash">{"\u2b07"} .trc</button>
                  </td>
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
