
HTML_WRAPPER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ECU Flash Tool — Diagnostic & Flash Studio</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="/static/react.development.js"></script>
<script src="/static/react-dom.development.js"></script>
<script src="/static/babel.min.js"></script>
<script src="/static/tailwindcss.js"></script>
<script>
  tailwind.config = {
    theme: {
      extend: {
        fontFamily: { sans: ['Outfit', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] },
        animation: {
          'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          'glow': 'glow 2s ease-in-out infinite alternate',
          'fade-in-up': 'fadeInUp 0.5s ease-out forwards',
          'toast-slide': 'toastSlide 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) forwards',
          'toast-fade': 'toastFade 0.3s ease-in forwards',
          'stripe-slide': 'stripeSlide 1s linear infinite'
        },
        keyframes: {
          glow: { '0%': { boxShadow: '0 0 5px rgba(59,130,246,0.2)' }, '100%': { boxShadow: '0 0 20px rgba(59,130,246,0.6)' } },
          fadeInUp: { '0%': { opacity: '0', transform: 'translateY(10px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
          toastSlide: { '0%': { opacity: '0', transform: 'translateX(100%)' }, '100%': { opacity: '1', transform: 'translateX(0)' } },
          toastFade: { '0%': { opacity: '1', transform: 'translateX(0)' }, '100%': { opacity: '0', transform: 'translateX(100%)' } },
          stripeSlide: { '0%': { backgroundPosition: '0 0' }, '100%': { backgroundPosition: '2rem 0' } }
        }
      }
    }
  }
</script>
<style>
  * { box-sizing: border-box; }
  
  :root {
    --bg-grad-1: #0d142b;
    --bg-grad-2: #020617;
    --accent-primary: #3b82f6;
    --accent-glow: rgba(59, 130, 246, 0.6);
    --glass-bg: rgba(15, 23, 42, 0.6);
    --text-primary: #e2e8f0;
  }
  
  .theme-cyberpunk {
    --bg-grad-1: #1a0b2e;
    --bg-grad-2: #090014;
    --accent-primary: #d946ef;
    --accent-glow: rgba(217, 70, 239, 0.6);
    --glass-bg: rgba(26, 11, 46, 0.6);
    --text-primary: #f8fafc;
  }
  
  .theme-matrix {
    --bg-grad-1: #021c0b;
    --bg-grad-2: #000000;
    --accent-primary: #22c55e;
    --accent-glow: rgba(34, 197, 94, 0.6);
    --glass-bg: rgba(2, 28, 11, 0.6);
    --text-primary: #86efac;
  }

  body { 
    margin: 0; 
    background: radial-gradient(circle at 50% 0%, var(--bg-grad-1), var(--bg-grad-2) 80%); 
    background-attachment: fixed;
    color: var(--text-primary); 
    transition: background 0.5s ease;
  }
  ::-webkit-scrollbar { width: 8px; height: 8px; }
  ::-webkit-scrollbar-track { background: #0f172a; border-radius: 4px; }
  ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: #475569; }
  
  /* Tables */
  table { width: 100%; border-collapse: separate; border-spacing: 0; }
  th { background: rgba(15, 23, 42, 0.6); padding: 12px; font-weight: 500; color: #94a3b8; text-transform: uppercase; font-size: 10px; letter-spacing: 0.1em; border-bottom: 2px solid rgba(51,65,85,0.4); text-align: left; }
  td { padding: 10px 12px; border-bottom: 1px solid rgba(51,65,85,0.2); }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(30, 41, 59, 0.4); }
  
  /* Sliders */
  input[type=range] { -webkit-appearance: none; background: transparent; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; height: 16px; width: 16px; border-radius: 50%; background: var(--accent-primary); cursor: pointer; transform: translateY(-6px); box-shadow: 0 0 10px var(--accent-glow); transition: background 0.3s; }
  input[type=range]::-webkit-slider-runnable-track { width: 100%; height: 6px; cursor: pointer; background: #334155; border-radius: 3px; }

  /* Premium Glass Utilities */
  .glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(12px);
    border-radius: 0.75rem;
    border: 1px solid rgba(51, 65, 85, 0.5);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    border-left: 1px solid rgba(255, 255, 255, 0.05);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
    transition: all 0.2s ease-in-out, background 0.5s ease;
  }
  .glass-card:hover {
    transform: scale(1.01);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3), 0 0 15px var(--accent-glow);
  }

  /* Animated Progress Bar */
  .progress-stripes {
    background-image: linear-gradient(45deg, rgba(255, 255, 255, 0.15) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, 0.15) 50%, rgba(255, 255, 255, 0.15) 75%, transparent 75%, transparent);
    background-size: 2rem 2rem;
  }
  
  .text-glow {
    text-shadow: 0 0 10px currentColor, 0 0 20px currentColor;
  }
</style>
</head>
<body>
<div id="root"></div>

<!-- STITCHED COMPONENTS -->
<script type="text/babel">
{CONTENT}
</script>

</body>
</html>
"""
