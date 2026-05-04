
HTML_WRAPPER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ECU Flash Tool — MAHLE Diagnostic & Flash Studio</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="/static/react.development.js"></script>
<script src="/static/react-dom.development.js"></script>
<script src="/static/babel.min.js"></script>
<script src="/static/tailwindcss.js"></script>
<script>
  tailwind.config = {
    theme: {
      extend: {
        fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] },
        animation: {
          'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          'fade-in-up': 'fadeInUp 0.4s ease-out forwards',
          'toast-slide': 'toastSlide 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) forwards',
          'stripe-slide': 'stripeSlide 1s linear infinite'
        },
        keyframes: {
          fadeInUp: { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
          toastSlide: { '0%': { opacity: '0', transform: 'translateX(100%)' }, '100%': { opacity: '1', transform: 'translateX(0)' } },
          stripeSlide: { '0%': { backgroundPosition: '0 0' }, '100%': { backgroundPosition: '2rem 0' } }
        }
      }
    }
  }
</script>
<style>
  * { box-sizing: border-box; }
  
  :root {
    --mahle-red: #E30613;
    --mahle-dark: #1A1A2E;
    --mahle-navy: #0D1B3E;
    --bg-main: #F4F6F9;
    --bg-card: #FFFFFF;
    --bg-sidebar: #0D1B3E;
    --border-light: #E2E8F0;
    --border-medium: #CBD5E1;
    --text-primary: #1E293B;
    --text-secondary: #64748B;
    --text-muted: #94A3B8;
    --accent-primary: #E30613;
    --accent-blue: #1E40AF;
  }

  body { 
    margin: 0; 
    background: var(--bg-main);
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
  }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #F1F5F9; border-radius: 4px; }
  ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
  
  /* Tables */
  table { width: 100%; border-collapse: separate; border-spacing: 0; }
  th { background: #F8FAFC; padding: 12px; font-weight: 600; color: #64748B; text-transform: uppercase; font-size: 10px; letter-spacing: 0.1em; border-bottom: 2px solid #E2E8F0; text-align: left; }
  td { padding: 10px 12px; border-bottom: 1px solid #F1F5F9; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #F8FAFC; }
  
  /* Sliders */
  input[type=range] { -webkit-appearance: none; background: transparent; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; height: 16px; width: 16px; border-radius: 50%; background: var(--accent-primary); cursor: pointer; transform: translateY(-6px); box-shadow: 0 2px 6px rgba(227, 6, 19, 0.3); }
  input[type=range]::-webkit-slider-runnable-track { width: 100%; height: 6px; cursor: pointer; background: #E2E8F0; border-radius: 3px; }

  /* Animated Progress Bar */
  .progress-stripes {
    background-image: linear-gradient(45deg, rgba(255, 255, 255, 0.25) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, 0.25) 50%, rgba(255, 255, 255, 0.25) 75%, transparent 75%, transparent);
    background-size: 2rem 2rem;
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
