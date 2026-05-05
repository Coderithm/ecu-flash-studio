UTILS_JSX = """
window.fmtMs = function(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m ${sec}s`;
  return `${m}m ${sec}s`;
};

window.dirColor = function(dir) {
  if (dir === "TX") return "#B45309";
  if (dir === "RX") return "#047857";
  return "#6366F1";
};

window.Badge = function({ type }) {
  const map = {
    success:     { bg: "#ECFDF5", color: "#059669", border: "#A7F3D0" },
    failed:      { bg: "#e0f2fe", color: "#0284c7", border: "#bae6fd" },
    running:     { bg: "#FFFBEB", color: "#D97706", border: "#FDE68A" },
    interrupted: { bg: "#FFF7ED", color: "#EA580C", border: "#FED7AA" },
    idle:        { bg: "#F8FAFC", color: "#94A3B8", border: "#E2E8F0" },
  };
  const s = map[type] || map.idle;
  return (
    <span style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}`, borderRadius: 9999, padding: "3px 12px", fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", display: "inline-block" }}>{type}</span>
  );
};

window.SectionLabel = function({ children, style }) {
  return <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.15em", color: "#64748B", textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 8, ...style }}><span style={{ width: 3, height: 14, borderRadius: 2, background: "#0ea5e9" }}></span>{children}</div>;
};

window.Btn = function({ children, onClick, disabled, color = "#0ea5e9", style, className="" }) {
  const isDanger = color === "#0284c7" || color === "#0ea5e9" || color === "#c2410c" || color === "#92400e";
  const isSuccess = color === "#065f46" || color === "#10b981";
  const isGhost = color === "#334155";
  const isPurple = color === "#7c3aed" || color === "#6d28d9";
  
  let bgClass = "bg-gray-200 text-gray-400 border-gray-200";
  if (!disabled) {
    if (isDanger) bgClass = "bg-sky-600 hover:bg-sky-700 text-white border-sky-500 hover:shadow-lg hover:-translate-y-0.5";
    else if (isSuccess) bgClass = "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-500 hover:shadow-lg hover:-translate-y-0.5";
    else if (isGhost) bgClass = "bg-gray-100 hover:bg-gray-200 text-gray-700 border-gray-300 hover:shadow hover:-translate-y-0.5";
    else if (isPurple) bgClass = "bg-violet-600 hover:bg-violet-700 text-white border-violet-500 hover:shadow-lg hover:-translate-y-0.5";
    else bgClass = "bg-[#0ea5e9] hover:bg-[#0284c7] text-white border-[#0ea5e9] hover:shadow-lg hover:-translate-y-0.5";
  }

  return (
    <button onClick={onClick} disabled={disabled} className={`relative overflow-hidden font-semibold rounded-lg px-4 py-2 text-xs transition-all duration-200 border shadow-sm ${bgClass} ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer active:scale-[0.97]'} ${className}`} style={style}>
      {children}
    </button>
  );
};

window.Card = function({ children, style }) {
  return (
    <div className="animate-fade-in-up" style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 12, padding: 24, boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)", transition: "box-shadow 0.2s, border-color 0.2s", ...style }}>
      {children}
    </div>
  );
};

window.Container = function({ children, style }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 20, ...style }}>{children}</div>;
};

window.MonoInput = function({ value, onChange, placeholder, disabled, style, onKeyDown }) {
  return (
    <input value={value} onChange={onChange} onKeyDown={onKeyDown} placeholder={placeholder} disabled={disabled} style={{
      background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8,
      padding: "8px 12px", fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: "#1E293B",
      outline: "none", width: "100%", transition: "border-color 0.15s", ...style
    }} />
  );
};
"""
