UTILS_JSX = """
const { useState, useEffect, useRef, useMemo, useCallback, useReducer } = React;
window.fmtMs = function(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m ${sec}s`;
  return `${m}m ${sec}s`;
};

window.Badge = function({ type }) {
  const map = {
    success:     { bg: "#064e3b", color: "#34d399", border: "#059669", glow: "rgba(52,211,153,0.3)" },
    failed:      { bg: "#7f1d1d", color: "#fca5a5", border: "#dc2626", glow: "rgba(248,113,113,0.3)" },
    running:     { bg: "#78350f", color: "#fde68a", border: "#d97706", glow: "rgba(251,191,36,0.3)" },
    interrupted: { bg: "#7c2d12", color: "#fdba74", border: "#ea580c", glow: "rgba(249,115,22,0.3)" },
    idle:        { bg: "#1e293b", color: "#94a3b8", border: "#334155", glow: "none" },
  };
  const s = map[type] || map.idle;
  return (
    <span style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}`, boxShadow: s.glow !== "none" ? `0 0 10px ${s.glow}` : "none", borderRadius: 9999, padding: "3px 12px", fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", display: "inline-block" }}>{type}</span>
  );
};

window.SectionLabel = function({ children }) {
  return <div className="text-[11px] font-bold tracking-[0.2em] text-indigo-300/80 uppercase mb-4 flex items-center gap-2"><span className="w-2 h-2 rounded-sm bg-indigo-500/50"></span>{children}</div>;
};

window.Btn = function({ children, onClick, disabled, color = "#3b82f6", style, className="" }) {
  const isDanger = color === "#7f1d1d" || color === "#dc2626" || color === "#c2410c" || color === "#92400e";
  const isSuccess = color === "#065f46" || color === "#10b981";
  
  let bgClass = "bg-slate-700/50 text-slate-400 border-slate-600/50";
  if (!disabled) {
    if (isDanger) bgClass = "bg-red-600/80 hover:bg-red-500 text-white border-red-500/50 hover:shadow-[0_0_15px_rgba(239,68,68,0.5)] hover:-translate-y-0.5";
    else if (isSuccess) bgClass = "bg-emerald-600/80 hover:bg-emerald-500 text-white border-emerald-500/50 hover:shadow-[0_0_15px_rgba(16,185,129,0.5)] hover:-translate-y-0.5";
    else if (color === "#334155") bgClass = "bg-slate-700 hover:bg-slate-600 text-white border-slate-600/50 hover:shadow-lg hover:-translate-y-0.5";
    else bgClass = "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white border-blue-500/50 hover:shadow-[0_0_20px_rgba(59,130,246,0.6)] hover:-translate-y-0.5";
  }

  return (
    <button onClick={onClick} disabled={disabled} className={`relative overflow-hidden font-bold rounded-xl px-4 py-2 text-xs transition-all duration-300 border backdrop-blur-sm shadow-lg ${bgClass} ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer active:scale-95'} ${className}`} style={style}>
      {children}
    </button>
  );
};

window.Card = function({ children, style }) {
  return (
    <div className="glass-card animate-fade-in-up relative overflow-hidden group" style={{ padding: 24, ...style }}>
      <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/5 rounded-full blur-3xl group-hover:bg-blue-500/10 transition-colors duration-700 pointer-events-none"></div>
      <div className="relative z-10">{children}</div>
    </div>
  );
};

window.MonoInput = function({ value, onChange, placeholder, disabled, style }) {
  return (
    <input 
      value={value} 
      onChange={onChange} 
      placeholder={placeholder} 
      disabled={disabled}
      className="bg-slate-900 border border-slate-700/50 rounded-lg p-2 text-xs font-mono text-slate-200 outline-none focus:border-blue-500 disabled:opacity-50 transition-colors w-full placeholder:text-slate-600"
      style={style}
    />
  );
};

window.Container = function({ children, style }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 20, ...style }}>{children}</div>;
};

window.dirColor = function(dir) {
  if (dir === "TX") return "#fcd34d";
  if (dir === "RX") return "#6ee7b7";
  return "#94a3b8";
};
"""
