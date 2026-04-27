
APP_JSX = """
function App() {
  const { useState, useEffect } = React;
  const [active, setActive] = useState("dashboard");
  const [theme, setTheme] = useState("default");
  const [flashOp, setFlashOp] = useState({ running: false, swFile: "—", cycle: 0, total: 0, progress: 0, elapsedMs: 0, total_progress: 0, eta_seconds: -1 });
  const [flashCount, setFlashCount] = useState(0);
  const [sessionLog, setSessionLog] = useState([]);

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
    // Apply theme to document body
    document.body.className = theme === "default" ? "" : `theme-${theme}`;
  }, [theme]);

  const pages = {
    dashboard: <window.Dashboard flashOp={flashOp} flashCount={flashCount} />,
    multiflash: <window.MultiFlash flashOp={flashOp} sessionLog={sessionLog} />,
    interruptions: <window.InterruptionTests flashOp={flashOp} sessionLog={sessionLog} />,
    nvm: <window.NvmData />,
    flashlog: <window.FlashLog sessionLog={sessionLog} />,
    cantrace: <window.CanTrace />
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <window.Sidebar active={active} setActive={setActive} theme={theme} setTheme={setTheme} />
      <main style={{ flex: 1, padding: 32, overflowY: "auto", position: "relative" }}>
        <div key={active} className="animate-fade-in-up">
          {pages[active]}
        </div>
        
        {/* Toast Container */}
        <div style={{ position: "fixed", top: 20, right: 20, zIndex: 9999, display: "flex", flexDirection: "column", gap: 10 }}>
          {toasts.map(t => (
            <div key={t.id} className="animate-toast-slide glass-card" style={{ padding: "12px 24px", display: "flex", alignItems: "center", gap: 12, minWidth: 250 }}>
              {t.type === 'success' && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 10px #10b981" }} />}
              {t.type === 'error' && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444", boxShadow: "0 0 10px #ef4444" }} />}
              {t.type === 'info' && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#3b82f6", boxShadow: "0 0 10px #3b82f6" }} />}
              <span style={{ fontSize: 14, fontWeight: 500 }}>{t.msg}</span>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
"""
