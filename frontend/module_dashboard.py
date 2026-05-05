DASHBOARD_JSX = r"""
window.Dashboard = function({ flashOp, flashCount, ecuConfig, sessionLog }) {
  const { useState, useEffect, useRef } = React;
  const [swVersion, setSwVersion] = useState("—");
  const [swError, setSwError] = useState("");
  const [reading, setReading] = useState(false);
  const [flashReading, setFlashReading] = useState(false);
  const [localFC, setLocalFC] = useState("—");
  const [cmd, setCmd] = useState("");
  const [cmdLog, setCmdLog] = useState([]);
  const [sending, setSending] = useState(false);
  const QUICK = ["0x10 03", "0x22 F1 80", "0x27 01", "0x31 01 FF 00", "0x3E 00"]; 

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
    if (nvmAutoRead && sessionLog && sessionLog.length > prevSessionLogRef.current) {
        readNvmSaveCycle("Auto (after flash)");
    }
    prevSessionLogRef.current = sessionLog ? sessionLog.length : 0;
  }, [sessionLog, nvmAutoRead]);

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

  const txId = ecuConfig?.can_tx || "—";
  const rxId = ecuConfig?.can_rx || "—";

  async function readSW() {
    setReading(true);
    setSwError("");
    try {
      const res = await fetch('/api/ecu_read_sw');
      const json = await res.json();
      if (json.status === "ok" && json.version) {
        setSwVersion(json.version);
      } else {
        setSwVersion("—");
        setSwError(json.error || "No ECU connected");
      }
    } catch(e) {
      setSwVersion("—");
      setSwError("No ECU connected");
    } finally {
      setReading(false);
    }
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
    <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: -10 }}>
      <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 22, fontWeight: 700 }}>Dashboard Overview</h2>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        {/* SW Version */}
        <window.Card>
          <window.SectionLabel style={{ marginBottom: 8 }}>SW Version</window.SectionLabel>
          <div style={{ fontFamily: "monospace", fontSize: 14, fontWeight: 700, color: swVersion === "—" ? "#64748B" : "var(--accent-primary)", background: "#F1F5F9", borderRadius: 8, padding: "6px 10px", marginBottom: 6, minHeight: 30, display: "flex", alignItems: "center", border: "1px solid #E2E8F0" }}>
            {reading ? <span className="animate-pulse" style={{ color: "#64748B" }}>Reading ECU…</span> : swVersion}
          </div>
          {swError && <div style={{ fontSize: 10, color: "#0284c7", marginBottom: 6, fontFamily: "monospace" }}>{swError}</div>}
          <window.Btn onClick={readSW} disabled={reading} style={{ width: "100%", padding: "6px" }}>Read SW Version</window.Btn>
        </window.Card>

        <window.Card>
          <window.SectionLabel style={{ marginBottom: 8 }}>Flash Cycle Count</window.SectionLabel>
          <div style={{ fontFamily: "monospace", fontSize: 32, fontWeight: 800, color: "var(--accent-primary)", background: "#F1F5F9", borderRadius: 8, padding: "2px 10px", marginBottom: 12, textAlign: "center", minHeight: 40, lineHeight: "40px", border: "1px solid #E2E8F0" }}>
            {flashReading ? <span className="animate-pulse" style={{ fontSize: 14, color: "#64748B", fontWeight: 400 }}>Reading…</span> : localFC}
          </div>
          <window.Btn onClick={readFC} disabled={flashReading} color="#065f46" style={{ width: "100%", padding: "6px" }}>Read Flash Count</window.Btn>
        </window.Card>

        {/* ECU Status */}
        <window.Card>
          <window.SectionLabel style={{ marginBottom: 8 }}>ECU Status</window.SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Session</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>Extended Diagnostic</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Protocol</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>UDS over CAN</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>CAN ID (TX)</span>
              <span style={{ fontFamily: "monospace", fontSize: 13, color: "var(--accent-primary)", fontWeight: 700 }}>0x{txId}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>CAN ID (RX)</span>
              <span style={{ fontFamily: "monospace", fontSize: 13, color: "var(--accent-primary)", fontWeight: 700 }}>0x{rxId}</span>
            </div>
          </div>
        </window.Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
        {/* Application Command */}
        <window.Card>
          <window.SectionLabel style={{ marginBottom: 8 }}>Application Command</window.SectionLabel>
          <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
            <input value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={e => e.key === "Enter" && sendCmd()} placeholder="e.g. 0x10 03 or 22 F1 80" style={{ flex: 1, background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "6px 10px", fontSize: 12, fontFamily: "monospace", color: "#1E293B", outline: "none", transition: "border-color 0.15s" }} />
            <window.Btn onClick={sendCmd} disabled={sending || !cmd.trim()} style={{ padding: "6px 12px" }}>{sending ? "Sending…" : "Send"}</window.Btn>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
            {QUICK.map(c => (
              <button key={c} onClick={() => setCmd(c)} style={{ background: "#F1F5F9", color: "#475569", border: "1px solid #E2E8F0", borderRadius: 6, padding: "2px 6px", fontSize: 10, fontFamily: "monospace", cursor: "pointer", transition: "all 0.15s" }}>{c}</button>
            ))}
          </div>
          <div style={{ background: "#F8FAFC", borderRadius: 8, border: "1px solid #E2E8F0", maxHeight: 110, overflowY: "auto" }}>
            {cmdLog.length === 0
              ? <div style={{ padding: 12, fontSize: 11, color: "#64748B" }}>No commands sent yet.</div>
              : cmdLog.map((e, i) => (
                <div key={i} style={{ display: "flex", gap: 12, padding: "6px 12px", borderBottom: "1px solid #E2E8F0", fontSize: 11, fontFamily: "monospace", background: i === 0 ? "rgba(0,0,0,0.02)" : "transparent" }}>
                  <span style={{ color: "#64748B", width: 130, flexShrink: 0 }}>{e.ts}</span>
                  <span style={{ color: "#B45309" }}>TX: {e.cmd}</span>
                  <span style={{ color: e.response ? (e.response.startsWith("7F") ? "#0284c7" : "#047857") : "#64748B" }}>
                    {e.response ? `RX: ${e.response}` : "…waiting"}
                  </span>
                </div>
              ))
            }
          </div>
        </window.Card>
      </div>

      {/* NVM Data Section */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <window.Card>
         <window.SectionLabel style={{ marginBottom: 8 }}>NVM save cycle — Write (0x2E) then Read (0x22)</window.SectionLabel>
         <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div style={{ fontSize: 11, color: "#64748B" }}>Status</div>
            <div style={{ fontSize: 11, color: nvmErr ? "#0284c7" : (nvmWriting ? "#fde68a" : "#64748B") }}>
              {nvmErr ? nvmErr : (nvmWriting ? "Writing…" : (nvmReading ? "Reading…" : (nvmWriteStatus || "Idle")))}
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div>
              <div style={{ fontSize: 10, color: "#64748B", marginBottom: 2 }}>DID</div>
              <input value={nvmDid} onChange={e => setNvmDid(e.target.value)} placeholder="F1 90" disabled={nvmReading || nvmWriting} style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "6px 10px", fontSize: 12, fontFamily: "monospace", color: "var(--text-primary)", outline: "none", width: "100%" }} />
              <div style={{ fontSize: 9, color: "#64748B", marginTop: 4 }}>Write TX: <span style={{ fontFamily: "monospace" }}>2E {nvmDid || "F1 90"} &lt;data…&gt;</span></div>
              <div style={{ fontSize: 9, color: "#64748B", marginTop: 2 }}>Read TX: <span style={{ fontFamily: "monospace" }}>22 {nvmDid || "F1 90"}</span></div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: "#64748B", marginBottom: 2 }}>Write Data (bytes)</div>
              <input value={nvmWriteData} onChange={e => setNvmWriteData(e.target.value)} placeholder="00 0A" disabled={nvmReading || nvmWriting} style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "6px 10px", fontSize: 12, fontFamily: "monospace", color: "var(--text-primary)", outline: "none", width: "100%" }} />
              <div style={{ fontSize: 9, color: "#64748B", marginTop: 4 }}>Example: <span style={{ fontFamily: "monospace" }}>00 0A</span></div>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginTop: 2 }}>
            <window.Btn onClick={() => writeThenReadNvm('Manual')} disabled={nvmReading || nvmWriting} color="#6d28d9" style={{ width: "100%", padding: "6px" }}>
              {nvmWriting ? "Writing…" : "Write + Read"}
            </window.Btn>
            <window.Btn onClick={() => readNvmSaveCycle('Manual')} disabled={nvmReading || nvmWriting} color="#065f46" style={{ width: "100%", padding: "6px" }}>
              {nvmReading ? "Reading…" : "Read Only"}
            </window.Btn>
            <window.Btn onClick={() => { setNvmSaveCycleDec("—"); setNvmSaveCycleHex("—"); setNvmLastRead("—"); setNvmErr(""); setNvmWriteStatus("—"); }} disabled={nvmReading || nvmWriting} color="#E2E8F0" style={{ width: "100%", padding: "6px" }}>
              Clear
            </window.Btn>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 4 }}>
            <div style={{ background: "rgba(167,139,250,0.08)", borderRadius: 10, padding: 8, border: "1px solid rgba(167,139,250,0.25)" }}>
              <div style={{ fontSize: 9, color: "#64748B", marginBottom: 4 }}>Decimal</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#a78bfa", lineHeight: 1, fontFamily: "monospace" }}>{nvmSaveCycleDec}</div>
            </div>
            <div style={{ background: "rgba(59,130,246,0.08)", borderRadius: 10, padding: 8, border: "1px solid rgba(59,130,246,0.25)" }}>
              <div style={{ fontSize: 9, color: "#64748B", marginBottom: 4 }}>Hex</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: "var(--accent-blue)", lineHeight: 1.2, fontFamily: "monospace", paddingTop: 4 }}>{nvmSaveCycleHex}</div>
            </div>
          </div>
          <div style={{ fontSize: 10, color: "#64748B" }}>Last read: <span style={{ color: "var(--text-primary)", fontFamily: "monospace" }}>{nvmLastRead}</span></div>
         </div>
        </window.Card>

        <window.Card>
         <window.SectionLabel style={{ marginBottom: 8 }}>Every NVM save counter</window.SectionLabel>
         <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: '#64748B' }}>
            <input type='checkbox' checked={nvmAutoRead} onChange={e => setNvmAutoRead(e.target.checked)} disabled={nvmReading || nvmWriting} />
            Auto-read after each flash
          </label>
          <window.Btn onClick={() => setNvmCounterLog([])} disabled={nvmReading || nvmWriting} color='#E2E8F0' style={{ padding: '4px 8px', fontSize: 10 }}>Clear</window.Btn>
         </div>
         <div style={{ background: '#F8FAFC', borderRadius: 10, border: '1px solid #E2E8F0', maxHeight: 160, overflowY: 'auto' }}>
          {nvmCounterLog.length === 0 ? (
            <div style={{ padding: 12, fontSize: 11, color: '#64748B' }}>No counter reads yet.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead style={{ position: "sticky", top: 0, background: "#F8FAFC", zIndex: 1 }}>
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
  );
};
"""
