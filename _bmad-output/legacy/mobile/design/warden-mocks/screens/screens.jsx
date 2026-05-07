// screens.jsx — All 8 Warden screens (6 landscape + 2 portrait)
// Tactical HUD direction. Static hi-fi; no interactions wired.

// ───────────────────────────────────────────────────────────────────
// Common bits
// ───────────────────────────────────────────────────────────────────
const EPISODES = [
  { map: 'Skyline',       score: '13–9',  duration: '22:14', win: true,  result: 'W', seed: 3 },
  { map: 'Tank Factory',  score: '13–11', duration: '28:42', win: true,  result: 'W', seed: 7 },
  { map: 'Siberia',       score: '11–13', duration: '26:08', win: false, result: 'L', seed: 12 },
  { map: 'Skyline',       score: '13–6',  duration: '18:51', win: true,  result: 'W', seed: 18 },
  { map: 'Refinery',      score: '9–13',  duration: '24:33', win: false, result: 'L', seed: 22 },
  { map: 'Tank Factory',  score: '13–10', duration: '23:17', win: true,  result: 'W', seed: 27 },
  { map: 'Siberia',       score: '13–12', duration: '31:04', win: true,  result: 'W', seed: 33 },
  { map: 'Refinery',      score: '8–13',  duration: '21:49', win: false, result: 'L', seed: 41 },
];

// Tactical app mark — minimal hex+slash glyph
function WardenMark({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2L21 7v10l-9 5-9-5V7l9-5z" stroke="var(--hud-accent)" strokeWidth="1.4" />
      <path d="M8 9l4 6 4-6" stroke="#F0F0F0" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Top app strip — used in Card View / portrait variants
function AppStrip({ title = 'WARDEN', sub, right }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 16px 12px', borderBottom: `1px solid ${HUD.line}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <WardenMark size={18} />
        <div>
          <div style={{ fontFamily: HUD.mono, fontSize: 12, fontWeight: 700, letterSpacing: 2, color: HUD.text }}>{title}</div>
          {sub && <div style={{ fontFamily: HUD.mono, fontSize: 10, color: HUD.dim, letterSpacing: 1, marginTop: 1 }}>{sub}</div>}
        </div>
      </div>
      {right}
    </div>
  );
}

// Tiny tactical timestamp tag
function Stamp({ children, mono = true, color, style }) {
  return (
    <span style={{
      fontFamily: mono ? HUD.mono : HUD.font, fontSize: 10, letterSpacing: 1,
      color: color || HUD.muted, textTransform: 'uppercase',
      ...style,
    }}>{children}</span>
  );
}

// ───────────────────────────────────────────────────────────────────
// 1. Cold Start (landscape + portrait)
// ───────────────────────────────────────────────────────────────────
function ColdStart({ portrait = false }) {
  return (
    <Screen>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: portrait ? 'column' : 'row',
        padding: portrait ? '20px 16px 16px' : '16px 20px',
        gap: portrait ? 16 : 20,
      }}>
        {/* Header — top-left brand */}
        <div style={{
          position: 'absolute', top: portrait ? 18 : 16, left: portrait ? 18 : 20,
          display: 'flex', alignItems: 'center', gap: 10, zIndex: 2,
        }}>
          <WardenMark size={20} />
          <div>
            <div style={{ fontFamily: HUD.mono, fontSize: 12, fontWeight: 700, letterSpacing: 2 }}>WARDEN</div>
            <Stamp style={{ fontSize: 9 }}>MATCH ANALYSIS · v0.4.1</Stamp>
          </div>
        </div>
        {/* Coordinate ticks in corner — pure decoration */}
        <div style={{ position: 'absolute', top: portrait ? 18 : 16, right: portrait ? 18 : 20, zIndex: 2 }}>
          <Stamp style={{ fontSize: 9 }}>SES · 24·04·26</Stamp>
        </div>

        {/* Two paths */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: portrait ? 'column' : 'row',
          gap: portrait ? 12 : 16, marginTop: portrait ? 56 : 48,
          alignItems: 'stretch',
        }}>
          <ColdCard
            kind="resume"
            title="RESUME LAST REVIEW"
            subtitle="SCRIM · 24·04·26"
            meta={['Skyline · Episode 4 of 8', '02:41 → 22:14', 'Last opened 18h ago']}
            portrait={portrait}
            primary
          />
          <ColdCard
            kind="import"
            title="IMPORT NEW VIDEO"
            subtitle="MP4 · MOV · MKV"
            meta={['Auto-detect map breaks', 'Up to 4h source', 'Black-frame slicing']}
            portrait={portrait}
          />
        </div>

        {/* Bottom tactical strip */}
        <div style={{
          position: 'absolute', bottom: portrait ? 14 : 12, left: portrait ? 18 : 20, right: portrait ? 18 : 20,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          paddingTop: 10, borderTop: `1px solid ${HUD.line}`,
        }}>
          <Stamp>4 SESSIONS · 31 EPISODES ON DEVICE</Stamp>
          <Stamp style={{ color: 'var(--hud-accent)' }}>● READY</Stamp>
        </div>
      </div>
    </Screen>
  );
}

function ColdCard({ kind, title, subtitle, meta, portrait, primary = false }) {
  return (
    <HudBracket dim={!primary} style={{
      flex: 1, padding: portrait ? '20px 18px' : '24px 22px',
      background: primary ? 'linear-gradient(180deg, rgba(255,107,0,0.05) 0%, rgba(255,107,0,0) 50%)' : HUD.surface,
      display: 'flex', flexDirection: 'column',
      cursor: 'pointer',
    }}>
      {/* Top label */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Stamp color={primary ? 'var(--hud-accent)' : HUD.dim}>
          {primary ? '▸ RESUME' : '▸ IMPORT'}
        </Stamp>
        <Stamp>{subtitle}</Stamp>
      </div>

      {/* Center visual */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: portrait ? 80 : 100 }}>
        {kind === 'resume' ? (
          <div style={{ width: '100%', maxWidth: 220, position: 'relative' }}>
            {/* mini timeline preview */}
            <div style={{ display: 'flex', gap: 2, marginBottom: 6 }}>
              {[0,1,2,3,4,5,6,7].map(i => (
                <div key={i} style={{
                  flex: 1, height: 22 + (i === 3 ? 6 : 0),
                  background: i === 3 ? 'var(--hud-accent)' : i < 3 ? 'rgba(255,107,0,0.25)' : HUD.elev2,
                  borderRadius: 1,
                }} />
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: HUD.mono, fontSize: 9, color: HUD.dim, letterSpacing: 1 }}>
              <span>EP 01</span><span>· · ·</span><span>EP 08</span>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <HudBracket dim style={{ width: 56, height: 56, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon.Plus s={22} c={HUD.muted} />
            </HudBracket>
            <Stamp>DROP OR BROWSE</Stamp>
          </div>
        )}
      </div>

      {/* Title */}
      <div style={{
        fontFamily: HUD.mono, fontWeight: 700, letterSpacing: 1.5,
        fontSize: portrait ? 15 : 17, marginBottom: 6,
        color: primary ? HUD.text : HUD.text,
      }}>{title}</div>

      {/* Meta lines */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {meta.map((m, i) => (
          <div key={i} style={{ fontSize: 11, color: HUD.muted, fontFamily: HUD.font }}>
            <span style={{ color: HUD.dim, marginRight: 6 }}>›</span>{m}
          </div>
        ))}
      </div>
    </HudBracket>
  );
}

// ───────────────────────────────────────────────────────────────────
// 2. Processing
// ───────────────────────────────────────────────────────────────────
function Processing() {
  const progress = 0.62;
  return (
    <Screen>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', padding: '16px 20px' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <WardenMark size={18} />
            <Stamp style={{ fontSize: 11 }}>WARDEN · ANALYZING</Stamp>
          </div>
          <Stamp style={{ color: 'var(--hud-accent)' }}>● ENCODING</Stamp>
        </div>

        {/* Center — concentric tactical rings + filename */}
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 36 }}>
            {/* Radar */}
            <div style={{ position: 'relative', width: 140, height: 140 }}>
              <svg width="140" height="140" viewBox="0 0 140 140" style={{ position: 'absolute', inset: 0 }}>
                <circle cx="70" cy="70" r="64" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
                <circle cx="70" cy="70" r="46" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
                <circle cx="70" cy="70" r="28" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                <line x1="70" y1="6" x2="70" y2="134" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />
                <line x1="6" y1="70" x2="134" y2="70" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />
                {/* progress arc */}
                <circle cx="70" cy="70" r="56" fill="none"
                  stroke="var(--hud-accent)" strokeWidth="2"
                  strokeDasharray={`${2 * Math.PI * 56 * progress} ${2 * Math.PI * 56}`}
                  strokeDashoffset={2 * Math.PI * 56 * 0.25}
                  transform="rotate(-90 70 70)" strokeLinecap="butt" />
                {/* sweep line */}
                <line x1="70" y1="70" x2="70" y2="14" stroke="var(--hud-accent)" strokeWidth="1" opacity="0.7" transform="rotate(120 70 70)" />
                {/* center pip */}
                <circle cx="70" cy="70" r="2.5" fill="var(--hud-accent)" />
              </svg>
              <div style={{
                position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
              }}>
                <div style={{ fontFamily: HUD.mono, fontSize: 26, fontWeight: 700, letterSpacing: 1, color: HUD.text }}>62<span style={{ fontSize: 14, color: HUD.muted }}>%</span></div>
                <Stamp style={{ fontSize: 9, marginTop: 2 }}>SLICING</Stamp>
              </div>
            </div>

            {/* Stats column */}
            <div style={{ minWidth: 220, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <Stat label="SOURCE" value="raw_session_24_apr.mp4" mono small />
              <Stat label="DURATION" value="01:48:32" mono />
              <Stat label="EPISODES FOUND" value="6 / ~8" mono accent />
              <Stat label="ETA" value="00:42" mono />
            </div>
          </div>
        </div>

        {/* Tip banner */}
        <HudBracket dim style={{ padding: '12px 16px', background: HUD.surface }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <Stamp style={{ color: 'var(--hud-accent)' }}>TIP 02 · 04</Stamp>
            <div style={{ width: 1, height: 14, background: HUD.line }} />
            <div style={{ fontSize: 13, color: HUD.text, flex: 1 }}>
              Double-tap the top-left of any clip to <span style={{ color: 'var(--hud-accent)' }}>flip to minimap</span>.
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              {[0,1,2,3].map(i => (
                <div key={i} style={{ width: 18, height: 2, background: i === 1 ? 'var(--hud-accent)' : HUD.line }} />
              ))}
            </div>
          </div>
        </HudBracket>
      </div>
    </Screen>
  );
}

function Stat({ label, value, mono = false, accent = false, small = false }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', borderBottom: `1px solid ${HUD.line}`, paddingBottom: 6 }}>
      <Stamp>{label}</Stamp>
      <span style={{
        fontFamily: mono ? HUD.mono : HUD.font, fontSize: small ? 11 : 13,
        color: accent ? 'var(--hud-accent)' : HUD.text,
        fontWeight: 500, letterSpacing: 0.3,
      }}>{value}</span>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// 3. Card View (Home) — landscape + portrait
// ───────────────────────────────────────────────────────────────────
function CardView({ portrait = false }) {
  const cols = portrait ? 2 : 3;
  return (
    <Screen>
      {/* Top strip */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px 12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <WardenMark size={18} />
          <div>
            <div style={{ fontFamily: HUD.mono, fontSize: 12, fontWeight: 700, letterSpacing: 2 }}>WARDEN</div>
            <Stamp style={{ fontSize: 9 }}>SCRIM · 24·04·26 · 8 EPISODES</Stamp>
          </div>
        </div>
        {/* Sort dropdown */}
        <HudBracket dim style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8, background: HUD.surface }}>
          <Icon.Sort s={12} c={HUD.muted} />
          <Stamp style={{ color: HUD.text }}>ORANGE BIGGEST WIN</Stamp>
          <Icon.ChevDown s={10} c={HUD.muted} />
        </HudBracket>
      </div>

      {/* Slim filter bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 16px 12px', overflowX: 'hidden' }}>
        {['ALL', 'WINS', 'LOSSES', 'CLOSE'].map((t, i) => (
          <div key={t} style={{
            padding: '4px 10px',
            border: i === 0 ? `1px solid var(--hud-accent)` : `1px solid ${HUD.line}`,
            color: i === 0 ? 'var(--hud-accent)' : HUD.muted,
            fontFamily: HUD.mono, fontSize: 10, letterSpacing: 1.5,
            background: i === 0 ? 'rgba(255,107,0,0.08)' : 'transparent',
          }}>{t}</div>
        ))}
        <div style={{ flex: 1 }} />
        <Stamp>SES TOTAL · 1:48:32</Stamp>
      </div>

      {/* Grid */}
      <div style={{
        padding: '0 16px 16px',
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: portrait ? 12 : 14,
        overflow: 'hidden',
        height: 'auto',
      }}>
        {EPISODES.slice(0, portrait ? 6 : 6).map((ep, i) => (
          <EpisodeCard key={i} ep={ep} idx={i} active={i === 0} />
        ))}
      </div>
    </Screen>
  );
}

function EpisodeCard({ ep, idx, active }) {
  return (
    <div style={{ position: 'relative' }}>
      {/* Thumbnail with corner brackets */}
      <HudBracket dim={!active} style={{
        aspectRatio: '16/9',
        background: HUD.surface,
        marginBottom: 8,
      }}>
        <MapArt seed={ep.seed} variant="pov" />
        {/* Top-left HUD readout — score */}
        <div style={{ position: 'absolute', top: 8, left: 10 }}>
          <div style={{
            fontFamily: HUD.mono, fontSize: 16, fontWeight: 700, letterSpacing: 1,
            color: ep.win ? 'var(--hud-accent)' : '#5b8aff',
            textShadow: '0 1px 4px rgba(0,0,0,0.8)',
          }}>{ep.score}</div>
        </div>
        {/* Top-right — W/L tag */}
        <div style={{
          position: 'absolute', top: 8, right: 10,
          fontFamily: HUD.mono, fontSize: 10, letterSpacing: 1.5,
          color: ep.win ? 'var(--hud-accent)' : '#7e95c4',
          padding: '2px 6px',
          border: `1px solid ${ep.win ? 'rgba(255,107,0,0.4)' : 'rgba(123,149,196,0.4)'}`,
        }}>{ep.result}</div>
        {/* Bottom-left — duration */}
        <div style={{
          position: 'absolute', bottom: 8, left: 10,
          fontFamily: HUD.mono, fontSize: 10, color: HUD.text,
          textShadow: '0 1px 4px rgba(0,0,0,0.8)',
        }}>{ep.duration}</div>
        {/* Bottom-right — episode index */}
        <div style={{
          position: 'absolute', bottom: 8, right: 10,
          fontFamily: HUD.mono, fontSize: 10, color: HUD.muted,
        }}>EP{String(idx + 1).padStart(2, '0')}</div>
      </HudBracket>

      {/* Map name + active separator */}
      <div style={{
        fontFamily: HUD.mono, fontSize: 12, fontWeight: 700, letterSpacing: 1.5,
        color: HUD.text, paddingBottom: 6,
        borderBottom: active ? `1px solid var(--hud-accent)` : `1px solid ${HUD.line}`,
        boxShadow: active ? '0 1px 6px rgba(255,107,0,0.4)' : 'none',
      }}>{ep.map.toUpperCase()}</div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// 4. Cinema Mode — landscape, full-screen video, overlay revealed
// ───────────────────────────────────────────────────────────────────
function CinemaMode({ minimap = false, overlayVisible = true }) {
  return (
    <Screen scan={false}>
      {/* Full-bleed video */}
      <MapArt seed={3} variant={minimap ? 'minimap' : 'pov'} />
      {/* Subtle vignette for legibility */}
      <div style={{ position: 'absolute', inset: 0, background: overlayVisible
        ? 'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 24%, rgba(0,0,0,0) 60%, rgba(0,0,0,0.7) 100%)'
        : 'none', pointerEvents: 'none' }} />

      {overlayVisible && (
        <>
          {/* Top overlay */}
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
            <CircleBtn><Icon.ChevRight s={16} c={HUD.text} /></CircleBtn>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: HUD.mono, fontSize: 12, fontWeight: 700, letterSpacing: 1.5, color: HUD.text }}>
                SKYLINE <span style={{ color: HUD.muted, marginLeft: 8 }}>EP 04 · 13–9</span>
              </div>
              <Stamp style={{ fontSize: 9 }}>SCRIM · 24·04·26</Stamp>
            </div>
            {/* Map list trigger */}
            <CircleBtn label="MAPS"><Icon.Grid s={16} c={HUD.text} /></CircleBtn>
            {/* Minimap toggle — emphasized when minimap mode active */}
            <CircleBtn active={minimap} label="MINIMAP"><Icon.Map s={16} c={minimap ? 'var(--hud-accent)' : HUD.text} /></CircleBtn>
          </div>

          {/* Center reticle when minimap (overhead recon vibe) */}
          {minimap && (
            <div style={{
              position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
              pointerEvents: 'none',
            }}>
              <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                <circle cx="32" cy="32" r="24" stroke="rgba(255,107,0,0.4)" strokeWidth="0.8" strokeDasharray="2 3"/>
                <line x1="32" y1="4" x2="32" y2="14" stroke="var(--hud-accent)" strokeWidth="1"/>
                <line x1="32" y1="50" x2="32" y2="60" stroke="var(--hud-accent)" strokeWidth="1"/>
                <line x1="4" y1="32" x2="14" y2="32" stroke="var(--hud-accent)" strokeWidth="1"/>
                <line x1="50" y1="32" x2="60" y2="32" stroke="var(--hud-accent)" strokeWidth="1"/>
              </svg>
            </div>
          )}

          {/* Bottom overlay — controls + timeline */}
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '12px 16px 14px' }}>
            {/* Timeline */}
            <Timeline progress={0.34} />
            {/* Time row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, marginBottom: 12 }}>
              <Stamp style={{ color: HUD.text }}>07:34</Stamp>
              <Stamp>22:14</Stamp>
            </div>
            {/* Controls */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <CircleBtn><Icon.Prev s={16} c={HUD.text} /></CircleBtn>
                <CircleBtn primary><Icon.Pause s={18} c="#0a0a0d" /></CircleBtn>
                <CircleBtn><Icon.Next s={16} c={HUD.text} /></CircleBtn>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <CircleBtn label="CLIP"><Icon.Scissors s={16} c={HUD.text} /></CircleBtn>
              </div>
            </div>
          </div>
        </>
      )}
    </Screen>
  );
}

function CircleBtn({ children, primary = false, active = false, label }) {
  const showLabel = !!label;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
      <div style={{
        width: 44, height: 44, borderRadius: primary ? 22 : 6,
        background: primary ? 'var(--hud-accent)' : active ? 'rgba(255,107,0,0.15)' : 'rgba(20,20,26,0.7)',
        border: primary ? 'none' : active ? '1px solid var(--hud-accent)' : '1px solid rgba(255,255,255,0.12)',
        backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: active ? '0 0 12px rgba(255,107,0,0.5)' : 'none',
      }}>
        {children}
      </div>
      {showLabel && <Stamp style={{ fontSize: 8, color: active ? 'var(--hud-accent)' : HUD.muted }}>{label}</Stamp>}
    </div>
  );
}

// Reusable timeline strip — used in cinema + clip
function Timeline({ progress = 0.34, clip = null, scrubColor = 'var(--hud-accent)' }) {
  // Generate fake waveform / scene markers
  const segs = 60;
  return (
    <div style={{ position: 'relative', height: 22, width: '100%' }}>
      {/* base track */}
      <div style={{
        position: 'absolute', top: 9, left: 0, right: 0, height: 4,
        background: HUD.elev, borderRadius: 1,
      }}>
        {/* progress fill */}
        <div style={{
          position: 'absolute', top: 0, left: 0, height: '100%', width: `${progress * 100}%`,
          background: 'rgba(255,255,255,0.6)', borderRadius: 1,
        }} />
      </div>
      {/* scene markers (auto-detected episode breaks) */}
      {[0.18, 0.35, 0.52, 0.7, 0.86].map((p, i) => (
        <div key={i} style={{
          position: 'absolute', top: 5, left: `${p * 100}%`, width: 1, height: 12,
          background: HUD.dim, transform: 'translateX(-0.5px)',
        }} />
      ))}
      {/* clip region */}
      {clip && (
        <>
          <div style={{
            position: 'absolute', top: 4, left: `${clip.start * 100}%`, width: `${(clip.end - clip.start) * 100}%`, height: 14,
            background: 'rgba(255,107,0,0.18)',
            border: '1px solid var(--hud-accent)',
            boxShadow: '0 0 12px rgba(255,107,0,0.4)',
          }} />
          {/* bracket handles */}
          {['start', 'end'].map((k, i) => (
            <div key={k} style={{
              position: 'absolute', top: -2, left: `${(k === 'start' ? clip.start : clip.end) * 100}%`,
              transform: 'translateX(-50%)',
            }}>
              <ClipHandle dir={k} />
            </div>
          ))}
        </>
      )}
      {/* scrub head */}
      <div style={{
        position: 'absolute', top: 0, left: `${progress * 100}%`, transform: 'translateX(-50%)',
        width: 2, height: 22, background: scrubColor, borderRadius: 1,
        boxShadow: '0 0 8px rgba(255,107,0,0.6)',
      }} />
    </div>
  );
}

function ClipHandle({ dir }) {
  // Reticle-style bracket: open square corner facing into clip region
  const out = dir === 'start' ? -1 : 1;
  return (
    <svg width="14" height="26" viewBox="0 0 14 26" style={{ display: 'block' }}>
      <g stroke="var(--hud-accent)" strokeWidth="1.4" fill="none">
        {/* outer L bracket */}
        <path d={dir === 'start'
          ? 'M9 1 H1 V25 H9'
          : 'M5 1 H13 V25 H5'} />
        {/* inner tick */}
        <line x1="7" y1="9" x2="7" y2="17" strokeWidth="1.6" />
      </g>
    </svg>
  );
}

// ───────────────────────────────────────────────────────────────────
// 5. Clip Creation — landscape, timeline shows clip, voice slots panel
// ───────────────────────────────────────────────────────────────────
function ClipMode() {
  const clip = { start: 0.28, end: 0.42 };
  return (
    <Screen scan={false}>
      {/* Video bg, slightly dimmer to push focus to controls */}
      <MapArt seed={3} variant="pov" />
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(10,10,13,0.42)' }} />

      {/* Top strip — clip context */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 10px', border: '1px solid var(--hud-accent)', background: 'rgba(255,107,0,0.08)' }}>
          <Icon.Scissors s={12} c="var(--hud-accent)" />
          <Stamp style={{ color: 'var(--hud-accent)' }}>CLIP · 00:31</Stamp>
        </div>
        <Stamp>SKYLINE · EP 04</Stamp>
        <div style={{ flex: 1 }} />
        <div style={{ padding: '6px 14px', background: 'var(--hud-accent)', color: '#0a0a0d', fontFamily: HUD.mono, fontSize: 11, fontWeight: 700, letterSpacing: 1.5, cursor: 'pointer' }}>
          EXPORT ›
        </div>
      </div>

      {/* Bottom: timeline + voice panel */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'linear-gradient(0deg, rgba(10,10,13,0.95) 60%, rgba(10,10,13,0) 100%)', paddingTop: 28 }}>
        <div style={{ padding: '0 16px 12px' }}>
          <Timeline progress={0.34} clip={clip} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
            <Stamp>06:14</Stamp>
            <Stamp style={{ color: 'var(--hud-accent)' }}>CLIP 06:14 → 06:45</Stamp>
            <Stamp>22:14</Stamp>
          </div>
        </div>

        {/* Voice slots */}
        <HudBracket dim style={{ margin: '0 16px 14px', padding: '12px 14px', background: HUD.surface }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
            <Stamp style={{ color: HUD.text }}>VOICE COMMENTARY</Stamp>
            <Stamp>3 SLOTS</Stamp>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <VoiceSlot label="BEFORE" state="recorded" duration="0:08" seed={1} />
            <VoiceSlot label="ON CLIP" state="recording" duration="0:04" seed={2} />
            <VoiceSlot label="AFTER" state="empty" />
          </div>
        </HudBracket>
      </div>
    </Screen>
  );
}

function VoiceSlot({ label, state, duration, seed = 1 }) {
  const isRec = state === 'recording';
  const isEmpty = state === 'empty';
  return (
    <div style={{
      flex: 1, padding: '10px 12px',
      border: isRec ? '1px solid var(--hud-accent)' : `1px solid ${HUD.line}`,
      background: isRec ? 'rgba(255,107,0,0.06)' : isEmpty ? 'transparent' : HUD.elev,
      minHeight: 56,
      position: 'relative',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <Stamp style={{ color: isRec ? 'var(--hud-accent)' : isEmpty ? HUD.dim : HUD.text }}>
          {isRec && <span className="hud-blink" style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--hud-accent)', marginRight: 6, verticalAlign: 'middle', animation: 'hud-pulse 1s infinite' }} />}
          {label}
        </Stamp>
        {duration && (
          <span style={{ fontFamily: HUD.mono, fontSize: 10, color: isRec ? 'var(--hud-accent)' : HUD.muted, letterSpacing: 0.5 }}>
            {duration}
          </span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {isEmpty ? (
          <>
            <div style={{ width: 26, height: 26, border: `1px solid ${HUD.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon.Mic s={13} c={HUD.muted} />
            </div>
            <Stamp>TAP TO RECORD</Stamp>
          </>
        ) : isRec ? (
          <>
            <div style={{ width: 26, height: 26, background: 'var(--hud-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 10px rgba(255,107,0,0.6)' }}>
              <Icon.Stop s={11} c="#0a0a0d" />
            </div>
            <Waveform seed={seed} bars={18} color="var(--hud-accent)" height={16} />
          </>
        ) : (
          <>
            <div style={{ width: 26, height: 26, border: `1px solid ${HUD.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon.Play s={11} c={HUD.text} />
            </div>
            <Waveform seed={seed} bars={18} color={HUD.muted} height={16} />
          </>
        )}
      </div>
    </div>
  );
}

// inject blink keyframes
if (typeof document !== 'undefined' && !document.getElementById('hud-anim')) {
  const s = document.createElement('style');
  s.id = 'hud-anim';
  s.textContent = `@keyframes hud-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }`;
  document.head.appendChild(s);
}

// ───────────────────────────────────────────────────────────────────
// 6. Export / Share
// ───────────────────────────────────────────────────────────────────
function ExportShare() {
  return (
    <Screen>
      {/* Dimmed video preview at top */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '52%', overflow: 'hidden' }}>
        <MapArt seed={3} variant="pov" />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(10,10,13,0.4) 0%, rgba(10,10,13,1) 100%)' }} />
        {/* Floating clip frame */}
        <div style={{ position: 'absolute', top: 14, left: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Icon.Scissors s={14} c="var(--hud-accent)" />
          <Stamp style={{ color: 'var(--hud-accent)' }}>EXPORTING CLIP</Stamp>
        </div>
      </div>

      {/* Bottom export panel */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        padding: '20px 20px 16px',
      }}>
        <HudBracket style={{ padding: '20px 20px 16px', background: HUD.surface }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
            <div style={{ fontFamily: HUD.mono, fontSize: 14, fontWeight: 700, letterSpacing: 2, color: HUD.text }}>
              PREPARING CLIP
            </div>
            <span style={{ fontFamily: HUD.mono, fontSize: 12, color: 'var(--hud-accent)' }}>74<span style={{ color: HUD.muted }}>%</span></span>
          </div>
          <Stamp style={{ marginBottom: 14 }}>SKYLINE · 06:14 → 06:45 · 31s · MP4 720p</Stamp>

          {/* Progress bar */}
          <div style={{ height: 6, background: HUD.elev, position: 'relative', marginBottom: 14 }}>
            <div style={{ position: 'absolute', top: 0, left: 0, height: '100%', width: '74%', background: 'var(--hud-accent)', boxShadow: '0 0 10px rgba(255,107,0,0.5)' }} />
            {/* tactical tick marks */}
            {[0.25, 0.5, 0.75].map((p, i) => (
              <div key={i} style={{ position: 'absolute', top: -3, left: `${p * 100}%`, width: 1, height: 12, background: HUD.dim }} />
            ))}
          </div>

          {/* Steps row */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            {[
              { l: 'TRIM', s: 'done' },
              { l: 'MUX VOICE', s: 'done' },
              { l: 'ENCODE', s: 'active' },
              { l: 'SHARE', s: 'pending' },
            ].map((st, i) => (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{
                  height: 2,
                  background: st.s === 'done' ? 'var(--hud-accent)' : st.s === 'active' ? 'rgba(255,107,0,0.5)' : HUD.line,
                }} />
                <Stamp style={{ fontSize: 9, color: st.s === 'pending' ? HUD.dim : st.s === 'active' ? 'var(--hud-accent)' : HUD.text }}>
                  {st.l}
                </Stamp>
              </div>
            ))}
          </div>

          {/* Mock OS share targets sliding in */}
          <div style={{ display: 'flex', gap: 10, opacity: 0.5 }}>
            {['DISCORD', 'WHATSAPP', 'DRIVE', 'COPY', 'MORE'].map((n, i) => (
              <div key={n} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <div style={{ width: 36, height: 36, border: `1px solid ${HUD.line}`, background: HUD.elev }} />
                <Stamp style={{ fontSize: 8 }}>{n}</Stamp>
              </div>
            ))}
          </div>
        </HudBracket>
      </div>
    </Screen>
  );
}

Object.assign(window, {
  ColdStart, Processing, CardView, CinemaMode, ClipMode, ExportShare, EPISODES,
});
