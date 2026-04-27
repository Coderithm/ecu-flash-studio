
SIDEBAR_JSX = """
const NAV = [
  { id: "dashboard",    icon: "⬛", label: "Dashboard"          },
  { id: "multiflash",   icon: "🔁", label: "Multi-Flash Mode"   },
  { id: "interruptions",icon: "⚡", label: "Interruption Tests" },
  { id: "nvm",          icon: "💾", label: "NVM Data"           },
  { id: "flashlog",     icon: "📋", label: "Flash Log"          },
  { id: "cantrace",     icon: "📡", label: "CAN Trace"          },
];

window.Sidebar = function({ active, setActive, theme, setTheme }) {
  return (
    <aside className="w-[260px] min-h-screen border-r border-slate-800/80 flex flex-col py-6 relative z-10" style={{ background: "linear-gradient(180deg, rgba(15,23,42,0.8) 0%, rgba(2,6,23,0.95) 100%)", backdropFilter: "blur(20px)" }}>
      <div className="px-6 mb-8">
        <div className="text-[10px] font-bold tracking-[0.2em] text-blue-500 uppercase mb-2">ECU System</div>
        <div className="text-[22px] font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400 leading-tight drop-shadow-md">Flash Studio</div>
      </div>
      <div className="flex-1 flex flex-col gap-1.5 px-3">
      {NAV.map(n => (
        <button key={n.id} onClick={() => setActive(n.id)} 
          className={`flex items-center gap-3 px-4 py-3.5 text-[14px] font-medium rounded-xl cursor-pointer transition-all duration-300 w-full text-left
          ${active === n.id ? 'bg-blue-600/15 text-blue-300 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]' : 'bg-transparent text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 border border-transparent'}`}>
          <span className={`text-lg transition-transform duration-300 ${active === n.id ? 'scale-110' : 'opacity-70'}`}>{n.icon}</span>{n.label}
        </button>
      ))}
      </div>
      
      {/* Theme Switcher */}
      <div className="px-4 mb-4">
        <div className="text-[10px] text-slate-500 mb-2 uppercase tracking-widest font-bold px-2">Visual Theme</div>
        <div className="flex gap-2 bg-slate-900/50 p-1 rounded-xl border border-slate-800">
          {[
            { id: 'default',   label: 'Std',  color: '#3b82f6' },
            { id: 'cyberpunk', label: 'Neon', color: '#d946ef' },
            { id: 'matrix',    label: 'Mtx',  color: '#22c55e' }
          ].map(t => (
            <button key={t.id} onClick={() => setTheme(t.id)}
              className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold transition-all duration-300 ${theme === t.id ? 'bg-slate-800 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
              style={{ borderTop: theme === t.id ? `2px solid ${t.color}` : 'none' }}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="px-6 py-5 border-t border-slate-800 bg-slate-900/30">
        <div className="text-[11px] text-slate-500 mb-1.5 font-medium uppercase tracking-wider">Backend Status</div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse-slow shadow-[0_0_8px_rgba(52,211,153,0.8)]"></span>
          <span className="text-[12px] text-emerald-400 font-bold">Python API Live</span>
        </div>
      </div>
    </aside>
  );
};
"""
