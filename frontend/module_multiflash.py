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

  const [nvmSaveCycleDec, setNvmSaveCycleDec] = useState("—");
  const [nvmSaveCycleHex, setNvmSaveCycleHex] = useState("—");
  const [nvmLastRead, setNvmLastRead] = useState("—");
  const [nvmDid, setNvmDid] = useState("F1 90");
  const [nvmReading, setNvmReading] = useState(false);
  const [nvmAutoRead, setNvmAutoRead] = useState(true);
  const [nvmWriteData, setNvmWriteData] = useState("00 00");
  const [nvmWriting, setNvmWriting] = useState(false);
  const [nvmWriteStatus, setNvmWriteStatus] = useState("—");
  const [nvmCounterLog, setNvmCounterLog] = useState([]);
  const [nvmErr, setNvmErr] = useState("");
  
  const prevSessionLogRef = useRef(0);

  useEffect(() => {
    // If auto read is enabled and a new flash operation just completed (sessionLog grew)
    if (nvmAutoRead && sessionLog.length > prevSessionLogRef.current) {
        readNvmSaveCycle("Auto (after flash)");
    }
    prevSessionLogRef.current = sessionLog.length;
  }, [sessionLog, nvmAutoRead]);

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
    setNvmSaveCycleDec("—");
    setNvmSaveCycleHex("—");
    setNvmLastRead("—");
    setNvmErr("");
    fetch('/api/start_multiflash', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ files: filesData, times: times }) });
  }

  async function readNvmSaveCycle(reason = "Manual") {
    if (nvmReading) return;
    const did = (nvmDid || "").trim().toUpperCase();
    if (!did) { setNvmErr("DID is required"); return; }
    setNvmErr("");
    setNvmReading(true);

    try {
        const res = await fetch('/api/nvm_read?did=' + encodeURIComponent(did));
        const json = await res.json();
        
        let val = 0;
        let hex = "0x0000";
        if (json.data && json.data.length >= 2) {
            val = (json.data[0] << 8) | json.data[1];
            hex = `0x${val.toString(16).toUpperCase().padStart(4, '0')}`;
        }
        
        setNvmSaveCycleDec(val.toString());
        setNvmSaveCycleHex(hex);
        setNvmLastRead(new Date().toLocaleString("en-IN", { hour12: false }).replace(",", ""));
        setNvmCounterLog(l => [{ ts: new Date().toLocaleString("en-IN", { hour12: false }).replace(",", ""), did, dec: val.toString(), hex, reason }, ...l].slice(0, 200));
    } catch (e) {
        setNvmErr("Failed to read");
    } finally {
        setNvmReading(false);
    }
  }

  function parseHexBytes(str) {
    const s = (str || '').trim().toUpperCase().replace(/0X/g,'');
    if (!s) return [];
    return s.split(/\s+/).filter(Boolean).map(b => {
      const bb = b.replace(/[^0-9A-F]/g,'');
      return bb ? parseInt(bb, 16) : NaN;
    }).filter(x => !Number.isNaN(x));
  }

  async function writeThenReadNvm(reason = 'Manual') {
    if (nvmWriting || nvmReading) return;
    const did = (nvmDid || '').trim().toUpperCase();
    if (!did) { setNvmErr('DID is required'); return; }
    const bytes = parseHexBytes(nvmWriteData);
    if (bytes.length === 0) { setNvmErr('Write data bytes are required'); return; }
    setNvmErr('');
    setNvmWriting(true);
    setNvmWriteStatus('Writing…');

    try {
        const res = await fetch('/api/nvm_write', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ did, data: bytes })
        });
        await res.json();
        setNvmWriteStatus(`OK`);
        await readNvmSaveCycle('After write');
    } catch(e) {
        setNvmWriteStatus(`Error`);
    } finally {
        setNvmWriting(false);
    }
  }

  const opsCount = buildOps().length; const canStart = !running && opsCount > 0;
  const successCount = sessionLog.filter(e => e.status === "success").length;
  const failCount = sessionLog.filter(e => e.status === "failed").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 24, fontWeight: 700 }}>Multi-Flash Queue</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <window.Card>
          <window.SectionLabel>Local File Selection</window.SectionLabel>
          <div style={{ fontSize: 12, color: "#64748B", marginBottom: 12 }}>Pick files and assign absolute sequence priorities (1-10).</div>
          <div style={{ border: "1px solid rgba(51,65,85,0.6)", borderRadius: 12, overflow: "hidden", background: "#F8FAFC", marginBottom: 16, marginTop: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead><tr style={{ color: "#64748B", borderBottom: "1px solid #E2E8F0" }}><th style={{ width: 40 }}>Use</th><th style={{ width: 90 }}>Priority</th><th>Select Local Hex File</th></tr></thead>
              <tbody>
                {plan.map((row, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #E2E8F0" }}>
                    <td><input type="checkbox" checked={row.enabled} disabled={running} onChange={e => handleEnableChange(i, e.target.checked)} style={{ width: 16, height: 16, accentColor: "var(--accent-primary)" }} /></td>
                    <td style={{ color: "#64748B", fontFamily: "monospace" }}>
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
            <div style={{ fontSize: 12, color: "#64748B", marginBottom: 6 }}>Repeat Sequence Array (up to 100,000)</div>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ flex: 1 }}><input type="range" min={1} max={100000} value={times} onChange={e => setTimes(+e.target.value)} disabled={running} style={{ width: "100%", outline: "none", accentColor: "var(--accent-primary)" }} /></div>
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
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10, fontSize: 14 }}><span style={{ color: "#64748B" }}>Master Sequence</span><span style={{ fontWeight: 800, color: "var(--text-primary)" }}>{Math.round(flashOp?.total_progress || 0)}%</span></div>
            <div style={{ width: "100%", background: "#FFFFFF", borderRadius: 9999, height: 16, border: "1px solid #E2E8F0", overflow: "hidden", position: "relative" }}><div className={running ? "progress-stripes animate-stripe-slide" : ""} style={{ width: `${!running && (flashOp?.total_progress || 0) >= 99.5 ? 100 : Math.max(0, Math.min(100, flashOp?.total_progress || 0))}%`, height: 16, background: "linear-gradient(90deg, #10b981, var(--accent-primary))", borderRadius: 9999, transition: "width 0.4s" }} /></div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#64748B", marginTop: 8 }}><span>ETA: <span className={`font-mono font-bold ${flashOp?.eta_seconds >= 0 ? "text-emerald-400" : "text-slate-500"}`}>{flashOp?.eta_seconds >= 0 ? window.fmtMs(flashOp.eta_seconds * 1000) : "Calculating..."}</span></span><span>Flashes: <span className="font-bold text-slate-300">{flashOp?.cycle || 0}</span><span className="text-slate-500"> / </span><span className="font-bold text-slate-300">{flashOp?.total || 0}</span></span></div>
          </window.Card>

          <window.Card>
            <window.SectionLabel>Active Component Segment</window.SectionLabel>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#64748B", marginBottom: 8 }}><span className="font-mono text-indigo-300 truncate max-w-[200px]" title={flashOp?.swFile}>{flashOp?.swFile}</span><span className="font-bold text-slate-300">{Math.round(flashOp?.progress || 0)}%</span></div>
            <div style={{ width: "100%", background: "#FFFFFF", borderRadius: 9999, height: 10, border: "1px solid #E2E8F0", marginBottom: 8, overflow: "hidden", position: "relative" }}><div className="progress-stripes animate-stripe-slide" style={{ width: `${flashOp?.progress || 0}%`, height: 10, background: "linear-gradient(90deg, var(--accent-primary), #06b6d4)", borderRadius: 9999, transition: "width 0.2s" }} /></div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 24 }}>{[["✓ Succeeded", successCount, "#059669", "bg-emerald-900/20 border-emerald-500/30"], ["✗ Failed", failCount, "#DC2626", "bg-red-900/20 border-red-500/30"]].map(([label, val, color, cls]) => (<div key={label} className={`rounded-xl p-3 border text-center ${cls}`}><div style={{ fontSize: 24, fontWeight: 800, color }}>{val}</div><div style={{ fontSize: 10, color: "#64748B", marginTop: 2, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div></div>))}</div>
          </window.Card>
          
          <window.Card>
             <window.SectionLabel>NVM save cycle — Write (0x2E) then Read (0x22)</window.SectionLabel>
             <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <div style={{ fontSize: 11, color: "#64748B" }}>Status</div>
                <div style={{ fontSize: 11, color: nvmErr ? "#DC2626" : (nvmWriting ? "#fde68a" : "#64748B") }}>
                  {nvmErr ? nvmErr : (nvmWriting ? "Writing…" : (nvmReading ? "Reading…" : (nvmWriteStatus || "Idle")))}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>DID</div>
                  <input value={nvmDid} onChange={e => setNvmDid(e.target.value)} placeholder="F1 90" disabled={nvmReading || nvmWriting} style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "8px 12px", fontSize: 12, fontFamily: "monospace", color: "var(--text-primary)", outline: "none", width: "100%" }} />
                  <div style={{ fontSize: 10, color: "#64748B", marginTop: 6 }}>Write TX: <span style={{ fontFamily: "monospace" }}>2E {nvmDid || "F1 90"} &lt;data…&gt;</span></div>
                  <div style={{ fontSize: 10, color: "#64748B", marginTop: 2 }}>Read TX: <span style={{ fontFamily: "monospace" }}>22 {nvmDid || "F1 90"}</span></div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>Write Data (bytes)</div>
                  <input value={nvmWriteData} onChange={e => setNvmWriteData(e.target.value)} placeholder="00 0A" disabled={nvmReading || nvmWriting} style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "8px 12px", fontSize: 12, fontFamily: "monospace", color: "var(--text-primary)", outline: "none", width: "100%" }} />
                  <div style={{ fontSize: 10, color: "#64748B", marginTop: 6 }}>Example: <span style={{ fontFamily: "monospace" }}>00 0A</span> (big-endian)</div>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 2 }}>
                <window.Btn onClick={() => writeThenReadNvm('Manual')} disabled={nvmReading || nvmWriting} color="#6d28d9" style={{ width: "100%" }}>
                  {nvmWriting ? "Writing…" : "Write (0x2E) + Read (0x22)"}
                </window.Btn>
                <window.Btn onClick={() => readNvmSaveCycle('Manual')} disabled={nvmReading || nvmWriting} color="#065f46" style={{ width: "100%" }}>
                  {nvmReading ? "Reading…" : "Read Only (0x22)"}
                </window.Btn>
                <window.Btn onClick={() => { setNvmSaveCycleDec("—"); setNvmSaveCycleHex("—"); setNvmLastRead("—"); setNvmErr(""); setNvmWriteStatus("—"); }} disabled={nvmReading || nvmWriting} color="#E2E8F0" style={{ width: "100%" }}>
                  Clear Display
                </window.Btn>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 6 }}>
                <div style={{ background: "rgba(167,139,250,0.08)", borderRadius: 10, padding: 10, border: "1px solid rgba(167,139,250,0.25)" }}>
                  <div style={{ fontSize: 10, color: "#64748B", marginBottom: 6 }}>Decimal</div>
                  <div style={{ fontSize: 30, fontWeight: 800, color: "#a78bfa", lineHeight: 1, fontFamily: "monospace" }}>{nvmSaveCycleDec}</div>
                </div>
                <div style={{ background: "rgba(59,130,246,0.08)", borderRadius: 10, padding: 10, border: "1px solid rgba(59,130,246,0.25)" }}>
                  <div style={{ fontSize: 10, color: "#64748B", marginBottom: 6 }}>Hex</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: "var(--accent-blue)", lineHeight: 1.2, fontFamily: "monospace", paddingTop: 6 }}>{nvmSaveCycleHex}</div>
                </div>
              </div>

              <div style={{ fontSize: 11, color: "#64748B" }}>Last read: <span style={{ color: "var(--text-primary)", fontFamily: "monospace" }}>{nvmLastRead}</span></div>
             </div>
            </window.Card>

            <window.Card>
             <window.SectionLabel>Every NVM save counter</window.SectionLabel>
             <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#64748B' }}>
                <input type='checkbox' checked={nvmAutoRead} onChange={e => setNvmAutoRead(e.target.checked)} disabled={nvmReading || nvmWriting} />
                Auto-read after each flash operation
              </label>
              <window.Btn onClick={() => setNvmCounterLog([])} disabled={nvmReading || nvmWriting} color='#E2E8F0' style={{ padding: '6px 10px' }}>Clear</window.Btn>
             </div>
             <div style={{ background: '#F8FAFC', borderRadius: 10, border: '1px solid #E2E8F0', maxHeight: 220, overflowY: 'auto' }}>
              {nvmCounterLog.length === 0 ? (
                <div style={{ padding: 12, fontSize: 11, color: '#64748B' }}>No counter reads yet.</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                  <thead>
                    <tr style={{ color: '#64748B', borderBottom: '1px solid #E2E8F0' }}>
                      {['#','Time','Reason','Dec','Hex'].map(h => (
                        <th key={h} style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 500, fontSize: 10 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {nvmCounterLog.map((e, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #E2E8F0', color: 'var(--text-primary)' }}>
                        <td style={{ padding: '7px 10px', color: '#64748B' }}>{nvmCounterLog.length - i}</td>
                        <td style={{ padding: '7px 10px', color: '#64748B', whiteSpace: 'nowrap' }}>{e.ts}</td>
                        <td style={{ padding: '7px 10px', color: '#64748B' }}>{e.reason}</td>
                        <td style={{ padding: '7px 10px', fontFamily: 'monospace', color: '#a78bfa' }}>{e.dec}</td>
                        <td style={{ padding: '7px 10px', fontFamily: 'monospace', color: 'var(--accent-blue)' }}>{e.hex}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
             </div>
            </window.Card>
        </div>
      </div>
      <window.Card>
        <window.SectionLabel>Python Execution Logs</window.SectionLabel>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead><tr style={{ color: "#64748B", borderBottom: "1px solid #E2E8F0" }}>{["File Processed", "Execution Timestamp", "Time Elapsed", "Result"].map(h => <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontWeight: 500 }}>{h}</th>)}</tr></thead>
          <tbody>
            {sessionLog.length === 0 ? <tr><td colSpan={4} style={{ textAlign: "center", color: "#64748B", padding: "24px", fontSize: 14 }}>Waiting for backend Python events...</td></tr> : sessionLog.map(e => (<tr key={e.id} style={{ borderBottom: "1px solid #E2E8F0" }}><td style={{ padding: "10px 14px", fontFamily: "monospace", color: "var(--accent-blue)" }}>{e.swFile}</td><td style={{ padding: "10px 14px", color: "var(--text-primary)" }}>{e.timestamp}</td><td style={{ padding: "10px 14px", color: "var(--text-primary)" }}>{e.duration}</td><td style={{ padding: "10px 14px" }}><window.Badge type={e.status} /></td></tr>))}
          </tbody>
        </table>
      </window.Card>
    </div>
  );
};
"""
