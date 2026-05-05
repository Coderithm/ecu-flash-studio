APP_JSX = """
function App() {
  const { useState, useEffect } = React;
  const [active, setActive] = useState("dashboard");
  const [flashOp, setFlashOp] = useState({ running: false, swFile: "—", cycle: 0, total: 0, progress: 0, elapsedMs: 0, total_progress: 0, eta_seconds: -1 });
  const [flashCount, setFlashCount] = useState(0);
  const [sessionLog, setSessionLog] = useState([]);
  const [ecuConfig, setEcuConfig] = useState({ can_tx: "—", can_rx: "—" });

  useEffect(() => {
    fetch('/api/ecu_config').then(r => r.json()).then(cfg => setEcuConfig(cfg)).catch(() => {});
  }, []);

  useEffect(() => {
    const iv = setInterval(async () => {
      try {
        const res = await fetch('/api/flash_status');
        const st = await res.json();
        setFlashOp(st);
        if (st.flashCount !== undefined) setFlashCount(st.flashCount);
        if (st.sessionLog) setSessionLog(st.sessionLog);
      } catch(e) { }
    }, 250);
    return () => clearInterval(iv);
  }, []);

  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    window.showToast = (msg, type = 'info') => {
      const id = Date.now();
      setToasts(prev => [...prev, { id, msg, type }]);
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 3000);
    };
    
    // Initial hardware status toast
    setTimeout(() => {
      window.showToast("System Initialized", "success");
    }, 1000);
  }, []);

  const pages = {
    dashboard: <window.Dashboard flashOp={flashOp} flashCount={flashCount} ecuConfig={ecuConfig} sessionLog={sessionLog} />,
    multiflash: <window.MultiFlash flashOp={flashOp} sessionLog={sessionLog} />,
    interruptions: <window.InterruptionTests flashOp={flashOp} sessionLog={sessionLog} />,
    nvm: <window.NvmData />,
    flashlog: <window.FlashLog sessionLog={sessionLog} />,
    cantrace: <window.CanTrace flashOp={flashOp} />
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <window.Sidebar active={active} setActive={setActive} />
      <main style={{ flex: 1, padding: 32, overflowY: "auto", position: "relative", height: "100%" }}>
        
        {/* Persistent Branding */}
        <div style={{ position: "absolute", top: 16, right: 32, display: "flex", alignItems: "center", gap: 10, background: "#FFFFFF", padding: "8px 16px", borderRadius: 8, border: "1px solid #E2E8F0", boxShadow: "0 1px 2px rgba(0,0,0,0.05)", zIndex: 50 }}>
          <img src="/static/image.png" alt="Branding Logo" style={{ height: 32, objectFit: "contain", mixBlendMode: "multiply" }} />
        </div>

        <div key={active} className="animate-fade-in-up" style={{ marginTop: 10 }}>
          {pages[active]}
        </div>
        
        {/* Toast Container */}
        <div style={{ position: "fixed", top: 20, right: 20, zIndex: 9999, display: "flex", flexDirection: "column", gap: 10 }}>
          {toasts.map(t => (
            <div key={t.id} className="animate-toast-slide" style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 8, padding: "12px 24px", display: "flex", alignItems: "center", gap: 12, minWidth: 250, boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" }}>
              {t.type === 'success' && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 10px #10b981" }} />}
              {t.type === 'error' && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#0ea5e9", boxShadow: "0 0 10px #0ea5e9" }} />}
              {t.type === 'info' && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#E30613", boxShadow: "0 0 10px #E30613" }} />}
              <span style={{ fontSize: 14, fontWeight: 500, color: "#1E293B" }}>{t.msg}</span>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
"""
