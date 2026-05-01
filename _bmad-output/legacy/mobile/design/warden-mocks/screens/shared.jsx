// shared.jsx — Tactical HUD primitives
// Brackets, scanlines, type, color tokens. All screens reuse these.

const HUD = {
  bg: '#0a0a0d',
  surface: '#101014',
  elev: '#15151a',
  elev2: '#1c1c22',
  line: '#26262e',
  text: '#F0F0F0',
  muted: '#8a8a92',
  dim: '#52525a',
  // accent injected at runtime via CSS var --hud-accent
  font: 'Roboto, "Helvetica Neue", system-ui, sans-serif',
  mono: '"JetBrains Mono", "SF Mono", "Roboto Mono", ui-monospace, monospace',
};

// One-time CSS injection
if (typeof document !== 'undefined' && !document.getElementById('hud-styles')) {
  const s = document.createElement('style');
  s.id = 'hud-styles';
  s.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
    :root { --hud-accent: #FF6B00; --hud-accent-soft: rgba(255,107,0,0.18); --hud-accent-dim: rgba(255,107,0,0.5); }
    .hud-scanlines { position: relative; }
    .hud-scanlines::after {
      content: ''; position: absolute; inset: 0; pointer-events: none;
      background: repeating-linear-gradient(0deg, rgba(255,255,255,0.022) 0 1px, transparent 1px 3px);
      mix-blend-mode: overlay;
    }
    .hud-bracket { position: relative; }
    .hud-bracket::before, .hud-bracket::after,
    .hud-bracket > .hud-brc-bl, .hud-bracket > .hud-brc-br {
      content: ''; position: absolute; width: 10px; height: 10px;
      border-color: var(--hud-accent); border-style: solid; pointer-events: none;
    }
    .hud-bracket::before { top: 0; left: 0; border-width: 1px 0 0 1px; }
    .hud-bracket::after { top: 0; right: 0; border-width: 1px 1px 0 0; }
    .hud-bracket > .hud-brc-bl { bottom: 0; left: 0; border-width: 0 0 1px 1px; }
    .hud-bracket > .hud-brc-br { bottom: 0; right: 0; border-width: 0 1px 1px 0; }
    .hud-bracket-dim::before, .hud-bracket-dim::after,
    .hud-bracket-dim > .hud-brc-bl, .hud-bracket-dim > .hud-brc-br {
      border-color: rgba(255,255,255,0.18) !important;
    }
  `;
  document.head.appendChild(s);
}

// Reusable: 4 corner brackets (children fill the box)
function HudBracket({ children, dim = false, size = 10, color, style, className = '', ...rest }) {
  const c = color || (dim ? 'rgba(255,255,255,0.22)' : 'var(--hud-accent)');
  const leg = (s) => ({ position: 'absolute', width: size, height: size, borderColor: c, borderStyle: 'solid', pointerEvents: 'none', ...s });
  return (
    <div className={className} style={{ position: 'relative', ...style }} {...rest}>
      {children}
      <span style={leg({ top: 0, left: 0, borderWidth: '1px 0 0 1px' })} />
      <span style={leg({ top: 0, right: 0, borderWidth: '1px 1px 0 0' })} />
      <span style={leg({ bottom: 0, left: 0, borderWidth: '0 0 1px 1px' })} />
      <span style={leg({ bottom: 0, right: 0, borderWidth: '0 1px 1px 0' })} />
    </div>
  );
}

// Tactical map placeholder — abstract grid + path lines + dots
function MapArt({ name, w = '100%', h = '100%', seed = 1, variant = 'pov' }) {
  // Deterministic pseudo-random based on seed for stable visuals
  const rand = (n) => {
    const x = Math.sin(seed * 9999 + n) * 10000;
    return x - Math.floor(x);
  };
  const dots = Array.from({ length: 6 }, (_, i) => ({
    x: 12 + rand(i) * 76,
    y: 18 + rand(i + 10) * 64,
    team: i < 3 ? 'o' : 'b',
  }));
  const accent = 'var(--hud-accent)';
  return (
    <div style={{
      width: w, height: h, position: 'relative', overflow: 'hidden',
      background: variant === 'minimap'
        ? `radial-gradient(ellipse at 50% 40%, #1a1f2c 0%, #0d0f15 60%, #07080c 100%)`
        : `linear-gradient(135deg, #1a1418 0%, #0f0d12 50%, #0a0a0d 100%)`,
    }}>
      {/* grid */}
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: variant === 'minimap' ? 0.35 : 0.18 }}>
        <defs>
          <pattern id={`g-${seed}`} width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#3a3a44" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#g-${seed})`} />
      </svg>
      {/* simulated geometry blocks */}
      <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0 }}>
        <rect x="20" y="30" width="20" height="14" fill="#1f1f28" stroke="#2a2a34" strokeWidth="0.3" />
        <rect x="50" y="20" width="16" height="22" fill="#1f1f28" stroke="#2a2a34" strokeWidth="0.3" />
        <rect x="35" y="60" width="28" height="12" fill="#1f1f28" stroke="#2a2a34" strokeWidth="0.3" />
        <rect x="68" y="55" width="18" height="20" fill="#1f1f28" stroke="#2a2a34" strokeWidth="0.3" />
        <line x1="0" y1="50" x2="100" y2="50" stroke="#2a2a34" strokeWidth="0.3" strokeDasharray="2 2" />
        <line x1="50" y1="0" x2="50" y2="100" stroke="#2a2a34" strokeWidth="0.3" strokeDasharray="2 2" />
      </svg>
      {/* player dots */}
      {variant === 'minimap' && dots.map((d, i) => (
        <div key={i} style={{
          position: 'absolute', left: `${d.x}%`, top: `${d.y}%`,
          width: 8, height: 8, borderRadius: 2,
          background: d.team === 'o' ? accent : '#3a8eff',
          boxShadow: `0 0 8px ${d.team === 'o' ? 'rgba(255,107,0,0.6)' : 'rgba(58,142,255,0.6)'}`,
          transform: 'translate(-50%, -50%)',
        }} />
      ))}
      {/* POV center reticle on POV variant */}
      {variant === 'pov' && (
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
          <g stroke="rgba(240,240,240,0.35)" strokeWidth="1" fill="none">
            <line x1="50%" y1="calc(50% - 10px)" x2="50%" y2="calc(50% - 4px)" />
            <line x1="50%" y1="calc(50% + 4px)" x2="50%" y2="calc(50% + 10px)" />
            <line x1="calc(50% - 10px)" y1="50%" x2="calc(50% - 4px)" y2="50%" />
            <line x1="calc(50% + 4px)" y1="50%" x2="calc(50% + 10px)" y2="50%" />
          </g>
        </svg>
      )}
    </div>
  );
}

// Tiny inline icons
const Icon = {
  Play: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill={c}><path d="M7 5v14l12-7z" /></svg>
  ),
  Pause: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill={c}><rect x="6" y="5" width="4" height="14"/><rect x="14" y="5" width="4" height="14"/></svg>
  ),
  Prev: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill={c}><path d="M6 5h2v14H6zM20 5L9 12l11 7z"/></svg>
  ),
  Next: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill={c}><path d="M16 5h2v14h-2zM4 5l11 7L4 19z"/></svg>
  ),
  Mic: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>
    </svg>
  ),
  Scissors: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/>
    </svg>
  ),
  Share: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/>
    </svg>
  ),
  Map: ({ s = 18, c = 'currentColor' }) => (
    // satellite/recon: outer dashed ring + crosshair + inner pip
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="9" strokeDasharray="2 2" />
      <circle cx="12" cy="12" r="4" />
      <line x1="12" y1="1" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="1" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="23" y2="12"/>
      <circle cx="12" cy="12" r="1.2" fill={c} stroke="none"/>
    </svg>
  ),
  Grid: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
      <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
    </svg>
  ),
  Plus: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
  ),
  Sort: ({ s = 14, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8" strokeLinecap="round"><path d="M4 6h16M7 12h10M10 18h4"/></svg>
  ),
  ChevDown: ({ s = 12, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round"><path d="M5 9l7 7 7-7"/></svg>
  ),
  ChevRight: ({ s = 14, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round"><path d="M9 6l6 6-6 6"/></svg>
  ),
  Folder: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5"><path d="M3 6a1 1 0 011-1h5l2 2h9a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V6z"/></svg>
  ),
  Stop: ({ s = 18, c = 'currentColor' }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill={c}><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
  ),
};

// Render-once waveform — deterministic per seed
function Waveform({ seed = 1, bars = 28, color = 'currentColor', height = 18 }) {
  const r = (n) => { const x = Math.sin(seed * 13 + n * 1.7) * 10000; return x - Math.floor(x); };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 2, height }}>
      {Array.from({ length: bars }).map((_, i) => (
        <div key={i} style={{
          width: 2, height: 3 + r(i) * (height - 3),
          background: color, borderRadius: 1, opacity: 0.5 + r(i + 100) * 0.5,
        }} />
      ))}
    </div>
  );
}

// Common screen wrapper — fills the Android frame's content area in landscape
// or portrait, applying subtle scanlines and the dark base.
function Screen({ children, style, scan = true }) {
  return (
    <div className={scan ? 'hud-scanlines' : ''} style={{
      width: '100%', height: '100%', background: HUD.bg,
      color: HUD.text, fontFamily: HUD.font, position: 'relative', overflow: 'hidden',
      ...style,
    }}>{children}</div>
  );
}

Object.assign(window, { HUD, HudBracket, MapArt, Icon, Waveform, Screen });
