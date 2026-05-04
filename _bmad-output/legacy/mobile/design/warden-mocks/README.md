# Handoff: Warden — VR FPS Match Review (Mobile)

## Overview
Warden is a mobile companion app (Android-first, landscape-primary) for reviewing VR FPS scrim sessions. Coaches and players auto-slice raw session footage into per-map "episodes," scrub through them in a cinema-style player, flip to a top-down minimap view, cut clips with three slots of voice commentary (before / on-clip / after), and export to share.

This handoff covers **9 screens** in the Tactical HUD design language.

## About the Design Files
The files in this bundle are **design references created as static HTML/JSX prototypes** — they show the intended look, layout, and visual system, not production code to copy directly. Your task is to **recreate these designs in the target codebase's environment** (React Native, Jetpack Compose, SwiftUI, Flutter, etc.) using that codebase's established patterns, component library, and conventions. If no environment exists yet, pick the most appropriate framework for an Android-first mobile app and build there.

The mocks are **static** (no real interactions wired) and use placeholder visuals for video content (gradient + grid + abstract dots). Real footage / minimap rendering will be plugged in by engineering.

## Fidelity
**High-fidelity.** Final colors, typography, spacing, brackets, and tactical decoration are intended to be reproduced pixel-perfect. Sizes are tuned for a Pixel-class Android device:
- **Landscape inner viewport:** 896 × 412 px
- **Portrait inner viewport:** 360 × 720 px

## Design Tokens

### Colors
| Token | Hex | Usage |
|---|---|---|
| `bg` | `#0a0a0d` | Page / app background |
| `surface` | `#101014` | Card and panel surfaces |
| `elev` | `#15151a` | Elevated tracks (timeline base) |
| `elev2` | `#1c1c22` | Map-block geometry / further elevation |
| `line` | `#26262e` | Hairlines, borders, dividers |
| `text` | `#F0F0F0` | Primary text |
| `muted` | `#8a8a92` | Secondary text |
| `dim` | `#52525a` | Tertiary / disabled text |
| `accent` | `#FF6B00` | **Default orange** — used ONLY as 1px brackets, separators, glow, recording dot, primary CTA fill, focused field outline. Never as a generic background fill. |
| `accent-soft` | `rgba(255,107,0,0.18)` | Active backgrounds (subtle), highlight fills |
| `accent-dim` | `rgba(255,107,0,0.5)` | Mid-state strokes |
| `team-blue` | `#3a8eff` / `#5b8aff` | Opposing team color on minimap / loss tag |

Accent is themeable (Orange / Cyan / Red presets + free color picker). Implement as a CSS variable / theme token (`--hud-accent`).

### Typography
- **UI sans:** Roboto (400/500/700) — body, buttons, labels
- **Mono:** JetBrains Mono (400/500/700) — timecodes, scores, tactical labels (CALLSIGN / EMAIL / PASSWORD / SKYLINE EP04 / 13–9 / etc.), readouts. Always uppercase with letter-spacing 1.5–2.5.
- **Stamp** (small tactical labels): mono, 9–11px, uppercase, letter-spacing 1, color `muted` or `dim`.

### Spacing
4 / 8 / 12 / 16 / 20 / 24 px scale.

### Touch Targets
- Minimum 44 × 44 px (circle buttons in cinema overlay).
- Pill / chip targets ≥ 28 px tall.

### Tactical decoration (key motifs)
- **HUD brackets:** 1px L-shaped corners (10×10 legs) on cards, panels, and focal frames. Two variants:
  - **Active**: `accent` color
  - **Dim**: `rgba(255,255,255,0.18)`
- **Scanlines:** `repeating-linear-gradient(0deg, rgba(255,255,255,0.022) 0 1px, transparent 1px 3px)` overlay at `mix-blend-mode: overlay` on dark surfaces. Only on UI screens, not on video frames.
- **Corner ticks:** small L crosshairs at the 4 corners of full-screen surfaces (login).
- **Recon grid backdrop:** 32px dotted SVG pattern at low opacity behind login.
- **Reticle**: 4-prong open-center crosshair, used on POV center and minimap toggle.

## Screens

All screens render inside an Android Pixel-style frame (dark bezel, status bar, gesture pill). The starter `android-frame.jsx` shows the M3 chrome we used; landscape uses a hand-rolled rotated variant in `Warden.html` for reference.

### 00 · Login (landscape + portrait)
Sign-in screen.
- **Brand block (left in landscape, top in portrait):** big hex Warden mark, "WARDEN" wordmark in mono w/ letter-spacing 4, subtitle "MATCH ANALYSIS · v0.4.1", short muted descriptive paragraph.
- **Auth panel (right / bottom):** bracketed surface with subtle accent-tinted top gradient.
  - Top label row: "▸ ACCESS" (accent) + "OP-24-04-26" (muted), both mono.
  - Heading "LOGIN" (mono, 16px, weight 700, letter-spacing 1.5).
  - Field: **EMAIL** (focused state — accent border + accent label + "● ACTIVE" badge + 8×14 blinking accent caret block). Value "dust.eagle@warden.gg".
  - Field: **PASSWORD** (default state). Value "••••••••••••" + trailing "SHOW".
  - Row: checkbox "REMEMBER ME" (left) + "FORGOT KEY?" (right, muted, dotted underline).
  - **Primary CTA "ENGAGE"** — orange fill, black mono text, right arrow, glow shadow `0 0 18px rgba(255,107,0,0.35)`.
  - Divider "OR" between hairlines.
  - SSO row: single full-width button **"CONTINUE WITH GOOGLE"** (Google glyph in muted, mono label). Email is already the default form, so no separate email SSO.
  - Footer: "NEW HERE? CREATE ACCOUNT ›" (muted + accent link).
- **Bottom strip:** "WARDEN · CONFIDENTIAL · TEAM SYS-7" (left), "TERMS · PRIVACY" (right). 1px top hairline.
- **Decoration:** corner ticks (TL/TR/BL/BR), recon grid + radial accent vignette behind everything.

### 01 · Cold Start
Two large bracketed cards side-by-side (stacked in portrait):
- **Resume Last Review** (primary, accent gradient tint): mini timeline preview showing 8 episode slabs with episode 4 highlighted, title "RESUME LAST REVIEW", meta lines "Skyline · Episode 4 of 8 / 02:41 → 22:14 / Last opened 18h ago".
- **Import New Video** (dim brackets): dashed "+" placeholder bracket, "DROP OR BROWSE", title "IMPORT NEW VIDEO", subtitle "MP4 · MOV · MKV", meta about black-frame slicing.
- Top-left brand chip; top-right session date stamp.
- Bottom strip: "4 SESSIONS · 31 EPISODES ON DEVICE" + "● READY" (accent).

### 02 · Processing
- Centered radar-style ring chart: 3 concentric circles, crosshair axes, accent progress arc, sweep line, center pip, big mono "62%" inside.
- Right column readouts: SOURCE filename, DURATION, EPISODES FOUND (accent), ETA. Underlined on each row.
- Bottom: bracketed tip banner "TIP 02 · 04 — Double-tap the top-left of any clip to flip to minimap." with 4 dot pagination.
- Top header: brand mark + "WARDEN · ANALYZING" + "● ENCODING" (accent) right.

### 03 · Card View (landscape: 3 cols / portrait: 2 cols)
- Top strip: brand + session metadata "SCRIM · 24·04·26 · 8 EPISODES". Right: bracketed sort dropdown "ORANGE BIGGEST WIN".
- Filter chips: ALL (active — accent border + tinted bg + accent text) / WINS / LOSSES / CLOSE. Right: "SES TOTAL · 1:48:32".
- Grid of episode cards. Each card:
  - 16:9 thumbnail with corner brackets (active card has accent brackets).
  - Top-left: score in mono, accent for win / blue for loss (`text-shadow: 0 1px 4px rgba(0,0,0,0.8)`).
  - Top-right: 1×1 W/L tag with thin border.
  - Bottom-left: duration mono.
  - Bottom-right: "EP01" episode index in muted mono.
  - Below: map name uppercase mono with separator line. Active card's separator is accent w/ glow.

### 04 · Cinema Mode (POV)
Full-bleed video, vertical-vignette overlay top + bottom for legibility.
- **Top overlay:** back chevron circle btn — title block (map name mono "SKYLINE" + "EP 04 · 13–9" muted, subtitle "SCRIM · 24·04·26"). Right: two circle buttons with tiny labels — "MAPS" (grid icon) and "MINIMAP" (recon icon).
- **Bottom overlay:** Timeline strip + time row + controls.
  - Timeline (height 22px): 4px elev base track, white-60% progress fill (34%), 5 dim scene-marker ticks at auto-detected episode breaks, 2px accent scrub head with glow.
  - Time row: current "07:34" / total "22:14" mono.
  - Controls row: prev / **play-pause primary** (44px circle, accent fill, dark icon) / next on the left; "CLIP" scissors button on the right.

### 04b · Cinema · Minimap mode
Same screen, MINIMAP toggle now active:
- Map placeholder switches to top-down `variant="minimap"` (dotted grid + 6 colored player dots — orange teammates, blue opponents — each with `box-shadow` glow).
- 64px reticle SVG at viewport center (dashed accent ring + 4 inward ticks).
- MINIMAP circle button shows active state: `rgba(255,107,0,0.15)` bg, accent border, `0 0 12px rgba(255,107,0,0.5)` glow, accent icon.

### 05 · Clip Creation
Same video bg, dimmed 42%.
- **Top:** small bracketed "✂ CLIP · 00:31" pill (accent border + accent-tinted bg) + "SKYLINE · EP 04". Right: orange "EXPORT ›" CTA.
- **Bottom panel** (frosted dark gradient): timeline now shows a clip region.
  - Clip region: tinted accent fill over the active range, accent border, glow, with **reticle-style L-bracket handles** at start/end (14×26 SVG: open square corner + inner tick).
  - Time row: current / "CLIP 06:14 → 06:45" (accent middle) / total.
- **Voice slots panel** (bracketed, 3 slots in a row):
  - **BEFORE** — recorded state: small play button + waveform in muted color, "0:08" duration.
  - **ON CLIP** — recording state: accent border, accent-tinted bg, blinking "●" + accent label, accent stop button (filled square), accent waveform, "0:04".
  - **AFTER** — empty state: muted mic icon, "TAP TO RECORD" stamp.

### 06 · Export / Share
- Top half: dimmed video preview with vertical fade to bg, "✂ EXPORTING CLIP" stamp top-left.
- Bottom panel: bracketed surface.
  - Heading "PREPARING CLIP" mono + "74%" right (accent).
  - Subheading "SKYLINE · 06:14 → 06:45 · 31s · MP4 720p".
  - 6px progress bar w/ accent glow + 3 vertical tick marks at 25/50/75%.
  - 4 step pills: TRIM (done) / MUX VOICE (done) / ENCODE (active, accent) / SHARE (pending). Each: 2px top bar (state color) + label below.
  - 5-up share targets row at 50% opacity: DISCORD / WHATSAPP / DRIVE / COPY / MORE — square outline thumbnail + small mono label.

### Portrait variants
The same Login, Cold Start, and Card View are also delivered in portrait (360×720) — same components, vertical layout. Auth panel stacks below brand; Cold Start cards stack vertically; Card View grid switches to 2 columns.

## Interactions & Behavior
**Static mocks — none of these are wired.** Below is the intended behavior:

- **Login → Cold Start**: ENGAGE / Continue with Google / Create account submit transitions to Cold Start.
- **Cold Start → Processing**: Tapping "Import New Video" opens system file picker; selection kicks off processing. "Resume Last Review" jumps to Card View at last episode.
- **Processing → Card View**: Auto-advance when 100%. Show brief "DONE" pulse on the radar.
- **Card View tap → Cinema** at episode 1.
- **Cinema controls**:
  - Play/pause toggles primary button icon.
  - Prev/Next jumps to scene-marker ticks (episode boundaries).
  - Scrub head is draggable along the timeline.
  - Tap MINIMAP toggle — flips video region between POV and overhead minimap (smooth crossfade).
  - Tap MAPS opens a sheet of the 8 episodes (not designed yet — engineering choice OK).
  - Tap CLIP enters Clip Mode — handles appear at current scrub ±15s.
- **Clip Mode**:
  - Drag either L-handle to retrim. Show clip duration live in the accent stamp.
  - Tap a voice slot — starts 30s rolling record. Tap stop to commit. Tap play to preview. Long-press to delete.
  - EXPORT → Export screen.
- **Export**:
  - Animated progress bar fills 0→100%; step pills advance done/active/pending in lockstep.
  - At 100%, share targets row goes fully opaque; tapping invokes the OS share sheet with the rendered MP4 + voice tracks muxed.

### Animations
- Scrub head & progress fills: simple linear updates from current playback time.
- Recording slot blink: `@keyframes hud-pulse { 0%,100% { opacity:1 } 50% { opacity:0.25 } }`, 1s infinite.
- Mode transitions: 200ms ease for opacity/transform; longer (400ms) for the POV↔minimap crossfade.

## State Management
Suggested state shape (adapt to target framework):

```ts
type Session = { id, date, name, episodes: Episode[] }
type Episode = { id, map, score, durationSec, win, sourceUri, thumb }
type Clip = { id, episodeId, startSec, endSec, voice: { before?, on?, after? } }
type VoiceClip = { uri, durationSec }

// app state
{
  auth: { user?, status: 'signed-out' | 'signed-in' },
  sessions: Session[],
  activeSessionId,
  activeEpisodeId,
  player: { tSec, playing, mode: 'pov' | 'minimap', overlayVisible },
  clipDraft?: Clip,                       // present when in Clip Mode
  exportJob?: { clipId, progress, step } // present during export
}
```

Data fetching: local-first (SQLite / Room / Realm). Voice and exported MP4s live on disk; sync to backend on uplink.

## Assets
- **Fonts:** Roboto + JetBrains Mono via Google Fonts. Use the framework's font loader; bundle locally for offline if required.
- **Icons:** All icons are inline SVGs in `screens/shared.jsx` (`Icon.Play`, `Pause`, `Prev`, `Next`, `Mic`, `Scissors`, `Share`, `Map`, `Grid`, `Plus`, `Sort`, `ChevDown`, `ChevRight`, `Folder`, `Stop`). Lift these directly or swap for your icon library equivalents (Material Symbols, Phosphor, Lucide). Custom ones to keep close: **Map** (recon/satellite ring + crosshair + center pip) and the **clip handle** reticle bracket.
- **Brand mark:** small + big variants in `screens/screens.jsx` (`WardenMark`) and `screens/login.jsx` (`BigMark`). Hex outline + chevron mark + center pip.
- **Map / video imagery:** placeholders only — `MapArt` SVG (gradient + dotted grid + abstract block geometry + dots for minimap, reticle for POV). Replace with the real video surface.

## Files in this bundle
| File | Role |
|---|---|
| `Warden.html` | Single-file design canvas hosting all 9 screens + tweak panel. Open in a browser to review. |
| `screens/shared.jsx` | Tactical HUD primitives — color tokens, `HudBracket`, `MapArt`, icon set, `Waveform`, `Screen` shell, scanline CSS, fonts. **Start here.** |
| `screens/screens.jsx` | The 8 in-app screens (ColdStart, Processing, CardView, CinemaMode, ClipMode, ExportShare). |
| `screens/login.jsx` | Login screen (landscape + portrait). |
| `design-canvas.jsx` | Design canvas wrapper used to lay screens out — **not** part of the product, just for reviewing the mocks. |
| `android-frame.jsx` | Material 3 Android frame reference; the live frame in `Warden.html` is a hand-rolled landscape variant. |
| `tweaks-panel.jsx` | Tweak panel for the accent color picker — design-time only. |

## How to view the mocks
Open `Warden.html` in a browser. Pan/zoom the canvas, drag any screen tile to focus it fullscreen, ←/→ to navigate between tiles, Esc to exit focus. Top-right "Tweaks" toggle in the toolbar opens the accent color picker.
