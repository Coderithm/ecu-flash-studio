
SIDEBAR_JSX = """
const NAV = [
  { id: "dashboard",    icon: "⬛", label: "Dashboard"          },
  { id: "multiflash",   icon: "🔁", label: "Multi-Flash Mode"   },
  { id: "interruptions",icon: "⚡", label: "Interruption Tests" },
  { id: "nvm",          icon: "💾", label: "NVM Data"           },
  { id: "flashlog",     icon: "📋", label: "Flash Log"          },
  { id: "cantrace",     icon: "📡", label: "CAN Trace"          },
];

window.Sidebar = function({ active, setActive }) {
  return (
    <aside className="w-[260px] min-h-screen border-r border-slate-200 flex flex-col py-6 relative z-10" style={{ background: "var(--bg-sidebar)" }}>
      <div className="px-6 mb-8">
        <div className="text-[10px] font-bold tracking-[0.2em] text-red-500 uppercase mb-2">MAHLE Diagnostic Tool</div>
        <div className="text-[22px] font-extrabold text-white leading-tight drop-shadow-md">Flash Studio</div>
      </div>
      <div className="flex-1 flex flex-col gap-1.5 px-3">
      {NAV.map(n => (
        <button key={n.id} onClick={() => setActive(n.id)} 
          className={`flex items-center gap-3 px-4 py-3.5 text-[14px] font-medium rounded-xl cursor-pointer transition-all duration-300 w-full text-left
          ${active === n.id ? 'bg-red-600/20 text-white border border-red-500/50 shadow-[0_0_15px_rgba(227,6,19,0.2)]' : 'bg-transparent text-slate-300 hover:bg-slate-800/60 hover:text-white border border-transparent'}`}>
          <span className={`text-lg transition-transform duration-300 ${active === n.id ? 'scale-110' : 'opacity-70'}`}>{n.icon}</span>{n.label}
        </button>
      ))}
      </div>
      
      <div className="px-6 py-5 border-t border-slate-800 bg-slate-900/30">
        <div className="text-[11px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">Backend Status</div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse-slow shadow-[0_0_8px_rgba(52,211,153,0.8)]"></span>
          <span className="text-[12px] text-emerald-400 font-bold">Python API Live</span>
        </div>
      </div>
    </aside>
  );
};
"""
