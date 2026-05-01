// login.jsx — Warden login screen, Tactical HUD direction.
// Same vocabulary as the rest of the app: bracketed surfaces, mono labels,
// accent only on focused field + primary CTA, bottom tactical status strip.

function LoginScreen({ portrait = false }) {
  return (
    <Screen>
      {/* Faint recon-grid backdrop drawn directly on the surface */}
      <div style={{ position: 'absolute', inset: 0, opacity: 0.5 }}>
        <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <pattern id="login-grid" width="32" height="32" patternUnits="userSpaceOnUse">
              <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#1c1c22" strokeWidth="0.5" />
            </pattern>
            <radialGradient id="login-vignette" cx="50%" cy="50%" r="60%">
              <stop offset="0%" stopColor="rgba(255,107,0,0.06)" />
              <stop offset="100%" stopColor="rgba(0,0,0,0)" />
            </radialGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#login-grid)" />
          <rect width="100%" height="100%" fill="url(#login-vignette)" />
        </svg>
      </div>

      {/* Crosshair ticks in the corners — pure decoration */}
      <CornerTick pos="tl" />
      <CornerTick pos="tr" />
      <CornerTick pos="bl" />
      <CornerTick pos="br" />

      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: portrait ? 'column' : 'row',
        padding: portrait ? '24px 20px 16px' : '20px 28px',
        gap: portrait ? 0 : 32,
      }}>
        {/* Brand block */}
        <div style={{
          flex: portrait ? '0 0 auto' : 1,
          display: 'flex', flexDirection: 'column',
          justifyContent: portrait ? 'flex-start' : 'center',
          paddingTop: portrait ? 16 : 0,
          paddingBottom: portrait ? 24 : 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: portrait ? 14 : 18 }}>
            <BigMark size={portrait ? 28 : 36} />
            <div>
              <div style={{
                fontFamily: HUD.mono, fontWeight: 700,
                fontSize: portrait ? 18 : 22, letterSpacing: 4, color: HUD.text,
              }}>WARDEN</div>
              <Stamp style={{ fontSize: 9, marginTop: 2 }}>MATCH ANALYSIS · v0.4.1</Stamp>
            </div>
          </div>
          <div style={{
            fontFamily: HUD.font, fontSize: portrait ? 13 : 14,
            color: HUD.muted, lineHeight: 1.5, maxWidth: 320,
          }}>
            Sign in to sync sessions, voice notes, and clips across<br/>headset, phone, and coach review.
          </div>
        </div>

        {/* Login panel */}
        <div style={{
          flex: portrait ? 1 : '0 0 auto',
          width: portrait ? '100%' : 340,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <HudBracket style={{
            width: '100%', padding: '20px 22px 22px',
            background: 'linear-gradient(180deg, rgba(255,107,0,0.04) 0%, rgba(255,107,0,0) 60%)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
              <Stamp style={{ color: 'var(--hud-accent)' }}>▸ ACCESS</Stamp>
              <Stamp>OP-24-04-26</Stamp>
            </div>

            <div style={{
              fontFamily: HUD.mono, fontSize: 16, fontWeight: 700,
              letterSpacing: 1.5, color: HUD.text, marginBottom: 16,
            }}>LOGIN</div>

            <Field label="EMAIL" value="dust.eagle@warden.gg" focused />
            <Field label="PASSWORD" value="••••••••••••" trailing="SHOW" />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '14px 0 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: 14, height: 14, border: '1px solid var(--hud-accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'rgba(255,107,0,0.12)',
                }}>
                  <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
                    <path d="M1 4.5L3.5 7L8 1.5" stroke="var(--hud-accent)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <Stamp style={{ color: HUD.text, fontSize: 10 }}>REMEMBER ME</Stamp>
              </div>
              <Stamp style={{ color: HUD.muted, fontSize: 10, textDecoration: 'underline', textDecorationColor: HUD.dim, textUnderlineOffset: 3 }}>
                FORGOT KEY?
              </Stamp>
            </div>

            {/* Primary CTA */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 16px',
              background: 'var(--hud-accent)',
              boxShadow: '0 0 18px rgba(255,107,0,0.35)',
              cursor: 'pointer',
            }}>
              <span style={{ fontFamily: HUD.mono, fontSize: 12, fontWeight: 700, letterSpacing: 2.5, color: '#0a0a0d' }}>
                ENGAGE
              </span>
              <svg width="16" height="12" viewBox="0 0 16 12" fill="none">
                <path d="M1 6H14M9 1L14 6L9 11" stroke="#0a0a0d" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>

            {/* Divider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '16px 0 12px' }}>
              <div style={{ flex: 1, height: 1, background: HUD.line }} />
              <Stamp style={{ fontSize: 9 }}>OR</Stamp>
              <div style={{ flex: 1, height: 1, background: HUD.line }} />
            </div>

            {/* SSO row — Google as alternative; email is the default above */}
            <div style={{ display: 'flex', gap: 8 }}>
              <SsoBtn label="CONTINUE WITH GOOGLE" icon="google" />
            </div>

            <div style={{ marginTop: 18, textAlign: 'center' }}>
              <Stamp>NEW HERE? </Stamp>
              <span style={{ fontFamily: HUD.mono, fontSize: 10, color: 'var(--hud-accent)', letterSpacing: 1.5, textTransform: 'uppercase' }}>
                CREATE ACCOUNT ›
              </span>
            </div>
          </HudBracket>
        </div>
      </div>

      {/* Bottom tactical strip */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        padding: portrait ? '8px 20px' : '8px 28px',
        borderTop: `1px solid ${HUD.line}`,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(10,10,13,0.6)',
      }}>
        <Stamp style={{ fontSize: 9 }}>WARDEN · CONFIDENTIAL · TEAM SYS-7</Stamp>
        <Stamp style={{ fontSize: 9 }}>TERMS · PRIVACY</Stamp>
      </div>
    </Screen>
  );
}

function CornerTick({ pos }) {
  const inset = 10, len = 14;
  const styles = {
    tl: { top: inset, left: inset, borderTop: '1px solid rgba(255,255,255,0.18)', borderLeft: '1px solid rgba(255,255,255,0.18)' },
    tr: { top: inset, right: inset, borderTop: '1px solid rgba(255,255,255,0.18)', borderRight: '1px solid rgba(255,255,255,0.18)' },
    bl: { bottom: inset + 22, left: inset, borderBottom: '1px solid rgba(255,255,255,0.18)', borderLeft: '1px solid rgba(255,255,255,0.18)' },
    br: { bottom: inset + 22, right: inset, borderBottom: '1px solid rgba(255,255,255,0.18)', borderRight: '1px solid rgba(255,255,255,0.18)' },
  };
  return <div style={{ position: 'absolute', width: len, height: len, ...styles[pos] }} />;
}

function BigMark({ size = 36 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none">
      <path d="M18 2L32 10v16l-14 8-14-8V10L18 2z" stroke="var(--hud-accent)" strokeWidth="1.4" />
      <path d="M18 6L28 12v12l-10 6-10-6V12L18 6z" stroke="rgba(255,107,0,0.4)" strokeWidth="0.8" />
      <path d="M11 14l7 10 7-10" stroke="#F0F0F0" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="18" cy="18" r="1.5" fill="var(--hud-accent)" />
    </svg>
  );
}

function Readout({ label, value, accent = false, hide = false }) {
  if (hide) return null;
  return (
    <div style={{ background: HUD.surface, padding: '8px 10px' }}>
      <div style={{ fontFamily: HUD.mono, fontSize: 8, color: HUD.dim, letterSpacing: 1.5, marginBottom: 2 }}>{label}</div>
      <div style={{
        fontFamily: HUD.mono, fontSize: 11, fontWeight: 500, letterSpacing: 0.5,
        color: accent ? 'var(--hud-accent)' : HUD.text,
      }}>{value}</div>
    </div>
  );
}

function Field({ label, value, focused = false, trailing }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <Stamp style={{ fontSize: 9, color: focused ? 'var(--hud-accent)' : HUD.muted }}>{label}</Stamp>
        {focused && <Stamp style={{ fontSize: 9, color: 'var(--hud-accent)' }}>● ACTIVE</Stamp>}
      </div>
      <div style={{
        position: 'relative',
        padding: '10px 12px',
        background: HUD.surface,
        border: `1px solid ${focused ? 'var(--hud-accent)' : HUD.line}`,
        boxShadow: focused ? '0 0 12px rgba(255,107,0,0.25), inset 0 0 0 0 transparent' : 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
          <span style={{ fontFamily: HUD.mono, fontSize: 13, color: HUD.text, letterSpacing: 0.5 }}>
            {value}
          </span>
          {focused && (
            <span style={{
              display: 'inline-block', width: 8, height: 14,
              background: 'var(--hud-accent)', animation: 'hud-pulse 1s infinite',
            }} />
          )}
        </div>
        {trailing && <Stamp style={{ fontSize: 9, color: HUD.muted, letterSpacing: 1.5 }}>{trailing}</Stamp>}
      </div>
    </div>
  );
}

function SsoBtn({ label, icon }) {
  const glyph = icon === 'google' ? (
    <svg width="12" height="12" viewBox="0 0 18 18">
      <path d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 01-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" fill="#8a8a92"/>
      <path d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.83.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 009 18z" fill="#8a8a92"/>
      <path d="M3.97 10.72A5.4 5.4 0 013.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 000 9c0 1.45.35 2.83.96 4.05l3.01-2.33z" fill="#8a8a92"/>
      <path d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 009 0 9 9 0 00.96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" fill="#8a8a92"/>
    </svg>
  ) : (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#8a8a92" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="1"/>
      <path d="M3 7l9 6 9-6"/>
    </svg>
  );
  return (
    <div style={{
      flex: 1, padding: '10px 0',
      border: `1px solid ${HUD.line}`,
      background: HUD.surface,
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
      fontFamily: HUD.mono, fontSize: 10, fontWeight: 500, letterSpacing: 1.5,
      color: HUD.muted,
      cursor: 'pointer',
    }}>{glyph}{label}</div>
  );
}

Object.assign(window, { LoginScreen });
