NVM_JSX = r"""
window.NvmData = function() {
  const { useState } = React;
  const [data, setData]             = useState(null);
  const [reading, setReading]       = useState(false);
  const [filter, setFilter]         = useState("");
  const [writeAddr, setWriteAddr]   = useState("");
  const [writeVal, setWriteVal]     = useState("");
  const [writeLog, setWriteLog]     = useState([]);

  function now() {
    return new Date().toLocaleString("en-IN", { hour12: false }).replace(",", "");
  }

  async function readAll() {
    setReading(true);
    try {
        const res = await fetch('/api/nvm_map');
        const json = await res.json();
        setData(json.data);
    } catch(e) {
        console.error("Failed to read NVM map:", e);
    } finally {
        setReading(false);
    }
  }

  async function writeNVM() {
    if (!writeAddr || !writeVal) return;
    try {
        await fetch('/api/nvm_map_write', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address: writeAddr, value: writeVal })
        });
        const entry = { ts: now(), addr: writeAddr, val: writeVal };
        setWriteLog(l => [entry, ...l].slice(0, 10));
        setWriteAddr(""); setWriteVal("");
        // Re-read to reflect changes
        readAll();
    } catch(e) {
        console.error("Failed to write NVM:", e);
    }
  }

  const filtered = (data ?? []).filter(r => !filter || r.label.toLowerCase().includes(filter.toLowerCase()) || r.address.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ color: "var(--text-primary)", margin: 0, fontSize: 20, fontWeight: 700 }}>NVM Data</h2>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
        <window.Card>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <window.SectionLabel style={{ flex: 1, margin: 0 }}>NVM Memory Map</window.SectionLabel>
            <window.MonoInput value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter…" style={{ width: 130 }} />
            <window.Btn onClick={readAll} disabled={reading}>{reading ? "Reading…" : "Read All"}</window.Btn>
          </div>
          {!data && !reading && <div style={{ textAlign: "center", color: "#64748B", fontSize: 13, padding: 30 }}>Click "Read All" to fetch NVM data from ECU.</div>}
          {reading && <div className="animate-pulse" style={{ textAlign: "center", color: "#64748B", fontSize: 13, padding: 30 }}>Reading NVM from ECU…</div>}
          {data && (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ color: "#64748B", borderBottom: "1px solid #E2E8F0" }}>
                  {["Address","Label","Value","Raw Bytes"].map(h => <th key={h} style={{ textAlign: "left", padding: "6px 12px 6px 0", fontWeight: 500, fontSize: 11 }}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {filtered.map(r => (
                  <tr key={r.address} style={{ borderBottom: "1px solid #E2E8F0", color: "var(--text-primary)" }}>
                    <td style={{ padding: "7px 12px 7px 0", fontFamily: "monospace", fontSize: 11, color: "var(--accent-blue)" }}>{r.address}</td>
                    <td style={{ padding: "7px 12px 7px 0", fontSize: 12 }}>{r.label}</td>
                    <td style={{ padding: "7px 12px 7px 0", fontFamily: "monospace", fontSize: 11, color: "#6ee7b7" }}>{r.value}</td>
                    <td style={{ padding: "7px 0", fontFamily: "monospace", fontSize: 11, color: "#64748B" }}>{r.raw}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </window.Card>
        <window.Card style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <window.SectionLabel>Write NVM</window.SectionLabel>
          <div>
            <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>Address</div>
            <window.MonoInput value={writeAddr} onChange={e => setWriteAddr(e.target.value)} placeholder="0x0000" />
          </div>
          <div>
            <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>Value</div>
            <window.MonoInput value={writeVal} onChange={e => setWriteVal(e.target.value)} placeholder="0xABCD" />
          </div>
          <window.Btn onClick={writeNVM} disabled={!writeAddr || !writeVal} color="#92400e" style={{ width: "100%" }}>Write NVM</window.Btn>
          <div style={{ borderTop: "1px solid #E2E8F0", paddingTop: 10 }}>
            <div style={{ fontSize: 11, color: "#64748B", marginBottom: 6 }}>Write Log</div>
            {writeLog.length === 0
              ? <div style={{ fontSize: 11, color: "#64748B" }}>No writes yet.</div>
              : writeLog.map((e, i) => (
                <div key={i} style={{ fontSize: 11, fontFamily: "monospace", color: "#64748B", borderBottom: "1px solid #E2E8F0", padding: "4px 0" }}>
                  <span style={{ color: "#64748B" }}>{e.ts.split(" ")[1]}</span>{" "}
                  <span style={{ color: "var(--accent-blue)" }}>{e.addr}</span>{" ← "}
                  <span style={{ color: "#6ee7b7" }}>{e.val}</span>
                </div>
              ))
            }
          </div>
        </window.Card>
      </div>
    </div>
  );
};
"""
