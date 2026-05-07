## Product Concept
- Warden: mobile match-review app for EVA After-h (competitive VR FPS); transforms paid game sessions into accelerated learning by making review frictionless ("Double XP" metaphor)
- Value proposition: progress faster while investing less time; review from couch in 10 minutes, send standalone clips that recipients watch without installing anything
- Core insight: paid EVA sessions lose most learning value because reviewing footage with generic tools is too painful; Warden makes review a habit, not a chore
- Killer differentiator: 100% on-device processing; no upload, no cloud cost, no tokens, no waiting; offline-first
- Core loop: navigate to round → review with minimap → create clip with voice → share; the minimap+voice clip artifact IS the product

## Problem Space
- Paid EVA sessions yield slow learning curve because teams "play" without "training"; same mistakes repeat match after match
- Impacts: financial (poor ROI on paid sessions), progression (flat curve), emotional (player + coach frustration), engagement (abandonment risk)
- Existing tools fail: video editors are complex/not EVA-configured/slow workflow; YouTube clips lack minimap mode + integrated review workflow; EVA Battle Plan = cloud upload latency, token costs, unused stats
- Identified gap: no tool specifically built for mobile EVA review with workflow optimized for non-professional coaches

## Differentiators
- EVA-specialized: pre-configured ROI templates and map detection
- Minimap mode: full-screen tactical overhead view; no competitor offers this on mobile
- 100% on-device: fixed cost, offline, no upload latency
- Voice-first: minimal friction for tired coach
- Standalone clips: recipient does not need the app; viral loop via Discord/WhatsApp inline playback

## Target Users
- Primary -- Coach Thomas (26, sports/physio coach, FPS 10y, EVA 2y, ex-COD coach): reviews evenings on PC at home in 30-60min sessions; current pain = juggling video player + notes + editor, uses 5% of generic-tool features, irregular reviews; wants unified EVA workflow + minimap mode + fast voice-clip export
- Secondary -- Passive Player Lucas (17, lycéen, competitive): excellent reflexes/aim, follows instructions, lacks game-vision; thinks progress = play more; needs to be SHOWN; receives clips, never installs app
- Secondary -- Active Player Maxime (22, high-division + assistant coach): proactive analyst; pipeline passive→active→coach; imports coach reviews + watches solo to develop analytical capability; uses app
- Discovery channels: word-of-mouth in EVA Discord community, FR/BE coach network, free-month coupons to monthly local-league winners ("dealer of comfort" strategy)

## Success Criteria
- Coach: can review comfortably from couch (mobile-first UX); ≥1 review/week; -50% to -80% time vs current workflow
- Team engagement (qualitative): non-communicating teams start exchanging on games; passive players watch AND respond; reduction of repeated errors
- Business 3mo: 20 paying coaches, 140€ MRR, MVP validation
- Business 12mo: 100 subscribers, 700€ MRR
- Churn: <15% (3mo) → <10% (12mo)
- Pricing: 7€/month or 70€/year (-17%); explicitly NOT shown inside the app (Reader App constraint)
- Leading indicators: coupon→subscription conversion rate, clips shared per coach/month, time-to-first-clip
- Technical: 1h20 video sliced <2min on Poco X5 (Snapdragon 695, 6GB RAM) reference device; auto lobby removal (~10% video saved); export quality configurable (Mobile/HD); 100% on-device
- Per-clip target: 3-5 (3mo) → 5+ (12mo) clips/review

## Functional Requirements (33 FRs across 7 domains)
- Video import (FR1-4): import MP4 from device storage; list sessions; delete sessions; validate format at import with error toast on incompatibility
- Video processing (FR5-10): auto-detect game-state transitions on-device via keyframe analysis (FR5, post-pivot wording is methodology-agnostic); identify map per segment (FR6); compute time ranges per map/round (FR7); mark lobby segments as excluded from navigation (FR8); process 1h20 video in background (FR9); resume processing after interruption (FR10)
- Playback & navigation (FR11-15): episode-style navigation between maps using time ranges (FR11); play/pause within allowed ranges (FR12); seek within map segment (FR13); instant view-mode toggle Full/Minimap/Minimap+HUD (FR14, post-pivot 3-value); minimap = cropped ROI from source video, optional KDA+Score HUD overlay (FR15)
- Audio commentary (FR16-20): record voice before clip (FR16), during playback overlay (FR17), after clip (FR18); delete recorded comment (FR19); preview clip with comments before export (FR20)
- Clip export (FR21-25): select clip start/end within map (FR21); export Mobile quality 720p fast (FR22); export HD quality source resolution (FR23); export as standalone MP4 with embedded audio (FR24); exported clip plays without Warden installed (FR25)
- Session persistence (FR26-28): auto-save state including position/comments/clips-in-progress (FR26); resume exactly where left off (FR27); persist across restarts and reboots (FR28)
- Auth & subscription (FR29-33): Firebase login (FR29); validate subscription on login (FR30); cache auth locally for offline (FR31); periodic re-validation when online (FR32); non-subscribed users see login screen only with no pricing/CTA (FR33, Reader App)

## Non-Functional Requirements (12 NFRs)
- Performance: NFR1 1h20 analysis <2min on Poco X5; NFR2 view-mode toggle <100ms; NFR3 Mobile-quality export <30s per minute of clip; NFR4 UI responsive during background processing (foreground service); NFR5 RAM <2GB during processing
- Reliability: NFR6 auto-save every 30s; NFR7 automatic resume after crash/kill; NFR8 voice recordings persisted immediately; NFR9 auth cache valid 30 days offline
- Security: NFR10 Firebase OAuth 2.0; NFR11 automatic token refresh; NFR12 no user data stored server-side (privacy by design)

## Architectural Stack
- Framework: Expo (managed → dev-client) + React Native + TypeScript strict; init via `npx create-expo-app@latest Warden --template blank-typescript`; rejected Obytes / ExpoStarter / custom (overhead, opinionated, paid)
- State: Zustand per feature, MMKV `persist` middleware; pure stores, async logic in hooks/services
- Navigation: React Navigation (root stack)
- Styling: NativeWind (Tailwind for RN) + tailwind.config.ts for design tokens; React Native Reusables (shadcn/ui for RN, copy-paste ownership) themed dark + accent orange; rejected Material Design (productivity-app look)
- Video processing: `ffmpeg-kit-react-native` community fork `jdarshan5/ffmpeg-kit-react-native` (original deprecated Jan 2025, archived June 2025); integrated via custom Expo config plugin `plugins/with-ffmpeg.js`; Plan B = custom native module via Expo Modules API if fork becomes unstable
- Computer vision: `react-native-fast-opencv` (JSI/C++, cross-platform Android+iOS); used for HSV color analysis + 64-bit pHash computation (NOT template matching post-pivot)
- Video player + audio recording: `expo-av` (Audio.Recording in AAC/.m4a so muxes without re-encoding); 100% custom UI (timeline, controls, view-mode toggle)
- Data layer (hybrid): MMKV (`react-native-mmkv`) for auth cache + session state + prefs (auto-save speed); SQLite via `expo-sqlite` for structured data (sessions, clips, comments metadata, map_segments); filesystem for audio .m4a files
- Auth: Firebase JS SDK (modular v9+), no extra native module; Firebase Auth + Firestore
- Payments: external web (NextJS + Stripe); webhook → Firebase sets user.isPaid = true; app reads, never writes
- Build/deploy: EAS Build (cloud) + EAS Submit; envs = development / preview / production
- Required design-system deps: `react-native-svg` (HUD brackets, icons, recon grid, radar progress, reticle, clip handles); `@expo-google-fonts/roboto`; `@expo-google-fonts/jetbrains-mono`; `expo-font`; `expo-linear-gradient`
- Min platform: Android API 24+ (Android 7.0); MVP Android only; iOS Phase 2 (after Apple license); stack chosen 100% cross-platform-ready

## Cross-cutting Integrations
- **Firestore `map_config.json` / DetectionConfig**: detection parameters (ROI definitions, KDA/HSV thresholds, map pHash fingerprints) served from Firestore; cached in MMKV under `detection.config`; bundled default config shipped with app as final fallback; consumed by `src/features/video-processing/detectionConfig.ts` (schema + validator), `detectionConfigService.ts` (Firestore fetch + MMKV cache + singleflight), `detectionConfigBootstrap.ts` (startup wiring + offline-first-launch gate); Story 7.4 lands as no-op shim until Story 7.5 consumes it; config version checked, stale caches refreshed on next online launch; tunable without app redeploy
- **Firestore `users/{uid}` doc — entitlement gating**: mobile reads `user.isPaid` boolean to grant/deny app access (FR30); validated at login + periodically when online (FR32); written by web Stripe webhook flow (mobile is read-only); subscription check in `auth/subscriptionService.ts`; Reader App model means mobile app NEVER references plans/prices/Stripe IDs — only the boolean (note: web side may write richer fields like `status`/`plan`/`stripe_*`; mobile distillate explicitly only mentions `isPaid` — flag this as a potential mismatch with web's data model)
- **Firebase Auth flow**: `[Web NextJS + Stripe] → Stripe webhook → Firebase (user.isPaid=true)` then `[App RN] ← Firebase Auth Login → check user.isPaid → unlock features`; first connection requires online login; subsequent sessions use MMKV-cached auth (30d offline); processing 100% offline; auth via `auth/authService.ts` (Firebase JS SDK)
- **Filesystem**: source video referenced in-place (no copy); audio comments stored as .m4a files referenced by SQLite rows
- **OS Share Sheet**: clip distribution via Expo Sharing API; status updates clip_exports.status to `shared`
- Firebase project config (apiKey/authDomain/projectId): NOT specified in mobile artifacts — must come from monorepo shared config or env

## Data Model — SQLite Schema
- `sessions` (id TEXT PK, video_file_path TEXT NOT NULL, name TEXT, duration_ms INTEGER, status CHECK IN ('importing','processing','ready','error'), created_at, updated_at)
- `map_segments` (id PK, session_id FK CASCADE, map_index INT, start_time_ms INT, end_time_ms INT, map_name TEXT, result_frame_path TEXT, score_orange INT NULL, score_blue INT NULL, created_at) — score columns NULL in MVP, populated post-MVP via OCR; result_frame_path = scoreboard screenshot extracted at end of processing for Card View thumbnail
- `clip_exports` (id PK, session_id FK CASCADE, map_segment_id FK CASCADE, start_time_ms, end_time_ms, view_mode CHECK IN ('full','minimap','minimap_hud') — POST-PIVOT 3-value, was ('pov','minimap'), status CHECK IN ('defining','locked','exporting','ready','shared'), export_quality CHECK IN ('mobile','hd'), file_path NULL until export complete, created_at, updated_at)
- `audio_comments` (id PK, clip_export_id FK CASCADE, slot CHECK IN ('before','during','after'), file_path NOT NULL, duration_ms NOT NULL, created_at) — 0 to 3 rows per clip, one per slot; silent clips have zero rows
- Schema migration tracked under Story 7.1: bump version, idempotent + reversible, existing `pov` rows → `full`
- DB naming: snake_case plural tables, snake_case cols, `{table_singular}_id` FKs

## Data Model — Domain Types & State
- TypeScript domain types: `Session`, `MapSegment`, `ClipExport`, `AudioComment`, `ViewMode = 'full' | 'minimap' | 'minimap_hud'` (named union exported from `src/features/clip-export/types.ts`), `GameDetectorEvent`, `MapIdentificationResult`, `DetectionConfig`
- MMKV key conventions (dot-notation): `auth.token`, `auth.user`, `session.current.position`, `session.current.episode`, `prefs.viewMode`, `prefs.minimapHud`, `prefs.exportQuality`, `prefs.sortOrder`, `detection.config`
- Naming conventions: PascalCase components/types/interfaces; camelCase functions/vars/hooks (with `use` prefix); UPPER_SNAKE_CASE constants; kebab-case folders; co-located tests
- Boundaries: features never import each other; only `shared/services/{ffmpeg,opencv,database,storage}.ts` access native libs; cross-feature comm via Zustand stores or shared services; screens orchestrate feature hooks/components

## Data Flow
- DetectionConfig (Firestore + MMKV cache + bundled default) feeds processing
- Import MP4 → Processing Pipeline → keyframes (FFmpeg `-skip_frame nokey`, low-res) → gameDetector (KDA/HSV 2-state machine) → mapIdentifier (pHash) → blackScreenDetector (long-GOP 3-state fallback when gameDetector uncertain) → MapSegments → SQLite
- Playback (expo-av) → ViewModeToggle (Full / Minimap / Minimap+HUD) → Audio commentary recording (expo-av) → Clip export (exportRecipes per view_mode + FFmpeg mux) → Standalone MP4 → OS Share

## Detection Methodology — Post-Pivot (Sprint 2.5)
- Approach: KDA + HSV color-space analysis on ROIs from config (game-state 2-state machine: game-on / game-off, with long-GOP black-screen 3-state fallback); pHash 64-bit perceptual hash compared against fingerprints from Firestore config for map identification
- Validated via R&D 2026-04; Proposals 4+6 approved 2026-04-20
- SUPERSEDES initial methodology (luminosity black-screen detector + OpenCV template matching against bundled `assets/images/map-templates/`); rejected because: less accurate, less maintainable (must redeploy app to update templates), brittle to luminosity/resolution/encoding variation
- Story 7.5 deletes `templateMatcher.ts` + `assets/images/map-templates/`; OpenCV wrapper retained but repurposed (HSV + pHash, not template matching)
- Detector files: `gameDetector.ts` (KDA/HSV), `mapIdentifier.ts` (pHash), `blackScreenDetector.ts` (long-GOP fallback)
- Unidentified-map handling: segments with no pHash match stored as `map_name = 'unknown'` but remain navigable (Story 2.5 AC4)
- Risk register updates: replaced "Template not recognized" with "Map not identified (pHash mismatch) → mark unknown_map, navigation still works"; added "Detection config Firestore inaccessible → MMKV cache, then bundled default"

## Project Structure
- `src/app/` entry + navigation (`_layout.tsx`, `index.tsx`, `session/[id].tsx`, `session/export.tsx`)
- `src/features/video-import/` (FR1-4): VideoImportScreen, useVideoImport, videoImportService, types
- `src/features/video-processing/` (FR5-10): useVideoProcessing, processingPipeline.ts, gameDetector.ts, mapIdentifier.ts, blackScreenDetector.ts, detectionConfig.ts, detectionConfigService.ts, detectionConfigBootstrap.ts, processingNotification.ts, types
- `src/features/video-playback/` (FR11-15): VideoPlayer.tsx (expo-av), PlayerControls.tsx, MinimapView.tsx (ROI crop), EpisodeNavigator.tsx, ViewModeToggle.tsx, HudToggle.tsx, usePlayback, types
- `src/features/audio-commentary/` (FR16-20): AudioRecorder.tsx, CommentaryTimeline.tsx, useAudioRecording, audioCommentService, types
- `src/features/clip-export/` (FR21-25): ExportOptions.tsx, ExportProgress.tsx, useClipExport, exportPipeline.ts, exportRecipes.ts, types
- `src/features/session/` (FR26-28): useSessionStore (Zustand+persist MMKV), sessionRepository (SQLite CRUD), autoSaveService (30s), types
- `src/features/auth/` (FR29-33): LoginScreen.tsx, useAuthStore (Zustand+persist MMKV), authService (Firebase JS), subscriptionService (isPaid), types
- `src/shared/`: components/ (Button, Toast, LoadingSpinner, hud/ primitives), hooks/ (usePermissions), services/ (ffmpeg, opencv, database, storage), types/, utils/ (fileSystem, formatters)
- Root: app.config.ts, eas.json (3 envs), tailwind.config.ts (design tokens), plugins/with-ffmpeg.js
- `assets/images/` carries app iconography only — NO map templates (post-pivot)

## UX Architecture
- Two-layer architecture: Card View (episode triage, Netflix-style grid with result frames as thumbnails) + Cinema Mode (immersive review, YouTube-fullscreen-style, reveal-on-tap controls auto-hide 4s)
- Cold start: two clear paths "Resume last review" / "Import new session"; never blank state; if zero sessions → single prominent button "Import your first training session"
- Card sorting (triage-first): Temporal (default), Orange biggest win, Blue biggest win, Closest map; sort persists via `prefs.sortOrder`; sort sets next/prev order in Cinema Mode; score-based sorts gracefully degrade to temporal until OCR ships
- Cinema Mode navigation: explicit Next / Previous / Maps buttons (rejected swipe gestures because they conflict with timeline scrubbing); single tap toggles controls overlay; double-tap top-left = power-user view-mode cycle Full → Minimap → Minimap+HUD
- Orientation: NO orientation lock (couch usage = unpredictable grip); landscape = video 100% + reveal-on-tap controls; portrait = video top + persistent controls below (vertical space available, no need to hide)
- Screen sizes: 5.5" → 1-col Card grid; 6.0-6.4" → 2-col; 6.5"+ → 2-col with more metadata; 44x44 min touch targets; respect system font scaling
- Reference device: Poco X5 (6.67")
- Mock reference: `docs/design/warden-mocks/` static HTML/JSX (Warden.html opens 9 screens); mocks WIN on visual when this doc disagrees; this doc owns behavior + journeys + component contracts
- Visual revision 2026-05-01: adopted Tactical HUD direction

## UX — Visual Design (Tactical HUD)
- Direction: Dark-first military-recon vocabulary; bracketed surfaces, mono tactical labels, accent-as-1px (NEVER as fill), subtle scanlines on UI surfaces; ~95% dark / 5% accent ("whisper not shout")
- Color tokens (canonical hex): bg #0a0a0d, surface #101014, elev #15151a, elev2 #1c1c22, line #26262e, text #F0F0F0, muted #8a8a92, dim #52525a, accent #FF6B00 (default orange), accent-soft rgba(255,107,0,0.18), accent-dim rgba(255,107,0,0.5), team-blue #3a8eff/#5b8aff, success #22C55E (share-complete toast only), error #EF4444
- Accent themeable runtime via Zustand-backed ThemeProvider exposing `--hud-accent` CSS-var-equivalent (Orange / Cyan / Red presets + free picker)
- Typography: Roboto sans (400/500/700) for body + UI labels; JetBrains Mono (400/500/700) for timecodes/scores/tactical labels — UPPERCASE with 1.5–2.5 letter-spacing; falls back to platform mono if Google Fonts not loaded but tactical aesthetic depends on JetBrains Mono
- Type scale: display-mono 22px tracking 4 (WARDEN wordmark), heading-mono 16px tracking 1.5 (LOGIN, PREPARING CLIP), subhead-mono 12px tracking 2 (top brand strip, card map names), value-mono 11-13px (field values, stats, timecodes), body 13-14px line-height 1.5, stamp 9-11px tracking 1 (top-row labels, meta lines), score 16px with text-shadow (episode card readouts)
- Tactical decoration motifs: HUD brackets (1px L-shaped corners 10×10), scanlines (repeating-linear-gradient overlay, NEVER on video frames), corner ticks (14×14), recon-grid (32px dotted SVG), reticle (4-prong 64×64 dashed accent ring), clip handles (14×26 SVG L-bracket reticle-style), status pills (1px border + mono ALL-CAPS), glow (box-shadow 0 0 12-18px rgba(255,107,0,0.25-0.6))
- Spacing base 4px; small 4 / med 8 / large 16 / section 24; edge safe zone 16px
- Component tier strategy: tactical primitives (`HudBracket`, `Stamp`, `Field`, `CircleBtn`, `Screen`, `Reticle`, `WardenMark`, `BigMark`, Icon set in `src/shared/components/hud/`) → standard UI (custom-themed buttons/toasts/modals/sheets, never library defaults) → custom core (video player, minimap view, view-mode toggle, clip creation, voice recorder, timeline scrubber, episode card)

## UX — Patterns & Components
- Inspirations: Discord (dark content-first, inline media, no onboarding), YouTube (scrub bar with thumbnails, chapter markers = episodes, double-tap skip muscle memory, fullscreen toggle), Netflix (episode grid mental model)
- No reference exists for tactical-overhead-VR-replay-with-voice — Warden defines this; format itself is viral hook in Discord (no watermark needed)
- Anti-patterns: tiny overlay minimap (current failure mode — must be FULL-SCREEN), export friction (no format/quality/title pre-flight, one tap to share, OS sheet handles), onboarding tutorials, in-app social features (Discord owns social), productivity UX language (no "projects/workspaces/dashboards")
- Defining experience: clip creation from minimap mode — "clip the play, say what happened, send it to the team"; clip = product
- Coach mental model: video editing tool (timeline-centric, non-destructive, export-oriented, tool-not-platform)
- Clip creation flow: tap "clip" → 30s region appears centered on current playback → drag bracket handles to refine → optional 3-slot voice → preview → confirm; <10s to define
- Voice recorder 3 slots: Before (tap "before" → still frame of clip first frame + blinking mic + red dot → audio over still frame plays before clip); During (tap "on clip" → countdown → clip plays + recording; if coach keeps talking past clip end, last frame freezes while audio continues); After (tap "after" → still frame of clip last frame + blinking mic → audio over still frame plays after during-overflow); tap-to-start, tap-to-stop, no auto-stop, no silence detection; all three slots independent on same clip; silent clips skip all voice segments
- Exported clip structure: `[before voice + still frame] → [clip video + during voice] → [frozen frame + during overflow] → [after voice + still frame]`; all segments optional
- View Mode System (3 modes from Stories 7.1-7.3+7.6): Full (source video, no crop, replaces original 'pov'); Minimap (cropped to map ROI from detection config); Minimap+HUD (minimap crop + KDA + Score overlays drawn from `map_segments` data); top-level Full↔Minimap segmented control + HUD sub-toggle (only active when top-level=Minimap); double-tap top-left cycles all 3; persisted via `prefs.viewMode` and `prefs.minimapHud` in MMKV
- Toggle target <100ms = crop/style change on same expo-av source (NFR2)
- Components catalog: Video Player (Cinema Mode), View Mode System, Timeline Scrubber, Clip Region Selector (30s default with bracket handles), Voice Recorder (3 slots), Episode Card, Sort Dropdown, Export Progress (MVP Option 1 modal vs Goal Option 3 queue indicator)
- Feedback patterns: success toast bottom 3s auto-dismiss; minor error toast 5s red; critical error blocking modal (e.g., incompatible format); short processing inline progress; long processing (auto-slice) full-screen progress + rotating tips every 5-8s
- Processing screen rotating tips: "Double tap top left to switch to minimap"; "Drag clip handles to adjust"; "Add voice before/during/after clip"; "Sort by closest score for important rounds"; "Progress saved automatically"
- Bottom sheet rules: never covers >40% (video stays visible), drag-down dismisses, dark surface + orange separator
- Gesture rules: every gesture has button equivalent; no hidden gestures required for core
- Export UX two-phase design: MVP Option 1 = encode immediately, "Preparing clip..." progress, share sheet opens when done (Story 5.4); Goal Option 3 = queue clip for background encoding, subtle queue indicator "2 ready, 1 processing", share-when-ready (deferred post-MVP, architecture supports via isolated `exportPipeline.ts` + extensible Zustand `clipQueue` + reusable foreground service); upgrade requires NO UI changes to clip creation flow

## Emotional Design
- Dominant emotion: purposeful immediacy ("let's see what went wrong" not "let me set up a review session")
- Secondary: momentum (after exporting, return to exact timeline position; never celebrate completion; feed next action; review feels like scrubbing replay in competitive game — quick, almost addictive)
- Anti-chore: no mandatory fields, no "save before closing" dialogs, no quick interactions blocked
- "Review is play not work": dark game-adjacent aesthetic vs productivity software
- The voice IS the tone (Warden never frames or labels feedback; coach's recording carries authority/casualness)
- Trust via reliability: state persistence is invisible — close mid-review, come back tomorrow, everything intact

## User Journeys
- J1 Coach happy path: import 1h20 → 90s auto-slice → Card View 8 maps lobby auto-removed → tap problem round → Cinema Mode → toggle Minimap → record voice "Lucas your flank is open" → export Mobile quality → share Discord → 15min total → done
- J2 Coach interruption: mid-review, app closed; 2h later reopens → exact map + position + comments-in-progress preserved → finish in 5min
- J3 Passive Player Lucas: Discord notification → tap clip → inline playback (no app install) → minimap + coach voice plays → "Ok compris, je me cale sur toi" → corrects next session
- J4 Active Player Maxime: imports session → auto-slice → toggles Full/Minimap solo without coach commentary → discovers patterns → develops analytical capability; identical to coach UI minus export step
- J3 lives entirely in Discord/WhatsApp; Warden UX responsibility ends at share sheet
- J4 partially supported in MVP (no review-import mode for coach annotations); review-import deferred to V2

## Scope — In MVP
- Auto-slicing (game-state KDA/HSV + pHash map ID, post-pivot)
- Card View + sorting (Temporal default + Orange/Blue biggest win + Closest map; score-sorts gracefully degrade until OCR)
- Cinema Mode + reveal-on-tap controls + persistent portrait controls
- 3-mode view toggle (Full / Minimap / Minimap+HUD) + double-tap power-user shortcut
- 30s default clip region with draggable bracket handles
- 3-slot voice recording (before/during/after) + clip preview + delete + re-record
- Export Mobile (720p) + HD (source) qualities; standalone MP4 with embedded audio
- OS share sheet
- Auto-save 30s + crash recovery + resume-where-left-off
- Firebase auth + Reader App login screen + isPaid validation + 30d offline cache

## Scope — Out / Deferred (Post-MVP)
- OCR scores/kills (V2; populates `score_orange`/`score_blue`; enables score-based Card View sorts) — deferred ML complexity
- Stats per map (V2, depends on OCR)
- Advanced ROI composition (minimap + killfeed + life) — V2; simple crop suffices for MVP
- Vertical export (stories/TikTok format) — V2+, nice-to-have
- Custom ROI templates — Desktop feature
- Review import mode (active player imports coach reviews with annotations) — V2; coach-first MVP
- Pick & Ban tool — V2+, community-requested
- iOS — Phase 2 after Apple license; entire stack already cross-platform-ready, only action = test build + validate config plugins
- Multi-view clip export (POV→minimap switch within single exported clip) — V2 via multi-segment FFmpeg encoding
- Export queue background encoding (Option 3 UX) — architecture supports evolution
- Stream Discord for group review — Desktop / Phase 3
- Advanced Desktop analysis — Phase 3

## Reader App Compliance Model
- 100% external monetization (web NextJS + Stripe) — 0% store commission
- App contains: login screen only — no IAP, no subscribe button, no pricing, no payment links, no plan names
- Login → check Firebase `user.isPaid` → unlock or block
- Reader App = Netflix-style precedent

## Device Permissions (Android)
- READ_EXTERNAL_STORAGE: video import (mandatory)
- RECORD_AUDIO: voice comments (mandatory)
- FOREGROUND_SERVICE: background processing notification (mandatory)
- INTERNET: Firebase auth + subscription validation (mandatory)
- (Foreground Service Android needs additional Expo config plugin OR `expo-task-manager` evaluation — flagged as non-blocking attention point in Architecture Gap Analysis #4)

## Video Format Constraints
- Format: MP4 (H.264 video / AAC audio) ONLY
- Source: local file on device (in-place reference, no copy)
- Typical duration: ~1h20 per session
- Validation: strict check at import; clear error message if codec/format unsupported

## Performance Constraints
- Device reference: Poco X5 (Snapdragon 695, 6GB RAM, 6.67")
- RAM budget: ~2GB during processing → keyframes extracted at LOW resolution only
- Battery: light processing via keyframes
- Process kill protection: state saved before crash, resumable from last checkpoint
- Keyframe spacing variance: tolerated; long-GOP black-screen detector kicks in as fallback when gameDetector uncertain
- Toggle <100ms: crop/style change on same expo-av source — no player swap
- Mobile export: <30s per minute of clip via FFmpeg mux with optional concat
- Foreground service Android keeps UI responsive while processing in background

## Epic Structure (7 epics)
- Epic 1 Project Setup & User Authentication: Stories 1.1 init Expo project, 1.2 nav + design system, 1.3 data layer (MMKV+SQLite), 1.4 Firebase login screen (Reader App), 1.5 subscription validation + offline cache; FR29-33; Reader App login UI per UX spec
- Epic 2 Video Import & Auto-Slice Processing: 2.1 import MP4 + format validation, 2.2 FFmpeg integration + keyframe extraction, ~~2.3 black-screen detector~~ SUPERSEDED by 7.5, ~~2.4 OpenCV template matcher~~ SUPERSEDED by 7.5, 2.5 segment video into map episodes (CONSUMES 7.5 output, rewritten), 2.6 background processing + crash recovery, 2.7 session list + management; FR1-4, 7-10 (FR5/6 moved to Epic 7)
- Epic 3 Video Playback & Episode Navigation: 3.1 Card View grid, 3.2 Cinema Mode + reveal-on-tap, 3.3 timeline scrubber, 3.4 Next/Previous/Maps nav, ~~3.5 minimap toggle~~ SUPERSEDED by 7.3 (precedent before Sprint 2.5), 3.6 Card View sorting; FR11-15
- Epic 4 Clip Creation & Voice Commentary: 4.1 clip region selector + bracket handles, 4.2 before voice, 4.3 during voice + freeze-frame overflow, 4.4 after voice, 4.5 clip preview with assembled voice, 4.6 delete + re-record; FR16-21
- Epic 5 Clip Export & Sharing: 5.1 export pipeline + quality options (Mobile/HD), 5.2 multi-segment assembly with voice overlay, 5.3 OS share sheet via Expo Sharing, 5.4 export progress modal; FR22-25 (jointly with Epic 7)
- Epic 6 Session Persistence & Reliability: 6.1 auto-save 30s, 6.2 resume exactly, 6.3 persist across restarts/reboots/crashes; FR26-28
- Epic 7 ROI Detection Redesign & View Mode Expansion (NEWLY EXPANDED Sprint 2.5): 7.1 SQLite view_mode CHECK 2-value→3-value migration + `pov`→`full` row migrate (ships same PR as 7.2), 7.2 ClipExport.view_mode TS union update + audit `'pov'` literals (same PR as 7.1), 7.3 view-mode toggle UI + HudToggle + Zustand+MMKV persistence (SUPERSEDES 3.5), 7.4 remote DetectionConfig service Firestore + MMKV cache + bundled fallback (no-op shim until 7.5), 7.5 replace detectors: gameDetector (KDA/HSV) + mapIdentifier (pHash) + blackScreenDetector refactored to long-GOP fallback + delete templateMatcher.ts + delete map-templates assets (SUPERSEDES 2.3 and 2.4), 7.6 export pipeline 3 view modes via exportRecipes + exportPipeline (SUPERSEDES view-mode portion of 5.1+5.2 which now layer Mobile/HD on top); FR5, FR6, FR14, FR15, FR22-25 (joint)

## Sprint State (as of 2026-05-05 / mid Sprint 2.5)
- Stories 1.1-1.5: done / ready-for-dev (Epic 1 essentially complete)
- Story 2.1 import: DONE
- Story 2.2 FFmpeg + keyframes: IN-PROGRESS; 3 minor edits applied (downstream consumer redirect to 7.5, supersession note in dev notes, testing approach updated to gameDetector+mapIdentifier seam); UNAFFECTED by methodology pivot, continues toward review (device-side smoke tests + RAM measurement)
- Stories 2.3, 2.4: SUPERSEDED by 7.5 (banners added, sprint-status YAMLs updated, never started — no rollback needed)
- Story 2.5: ready-for-dev, MAJOR REWRITE applied — now CONSUMES 7.5 output (gameDetector + mapIdentifier); 7 ACs (was 6); new AC4 for unknown-map handling (`map_name = 'unknown'`, segment remains navigable); tasks reference GameDetectorEvent + MapIdentificationResult types; explicitly does NOT re-implement detector logic
- Story 2.6: ready-for-dev, 1 minor dev note edit (template matching → gameDetector+mapIdentifier perf target wording)
- Story 2.7: ready-for-dev, unchanged
- Stories 3.1-3.4, 3.6: not_started, unchanged; Story 3.5 SUPERSEDED (pre-existing)
- Stories 4.1-4.6: not_started
- Stories 5.1-5.4: not_started
- Stories 6.1-6.3: not_started
- Stories 7.1-7.6: ready-for-dev; cosmetic file-path fix in 7.5 (`pipeline.ts` → `processingPipeline.ts`)
- Next steps order: (1) Finish Story 2.2 to review when device available; (2) Start Sprint 2.5 — 7.4 first (no-op shim), 7.1+7.2 ship same PR, then 7.5; (3) Resume Sprint 2 closure with 2.5+2.6 consuming 7.5 detectors
- Sprint Change Proposal 2026-05-05 = APPROVED + APPLIED (Incremental Mode); ~50 edits across PRD/epics/architecture/UX/4 stories/1 historical doc; pure documentation reconciliation, NO code changes, NO data migration (pre-production); MVP scope unchanged (all 33 FRs + 4 journeys preserved); methodology change invisible to user-facing value
- Original PRD/architecture/UX/epics French wording where it conflicts with the post-pivot English wording: AUTHORITATIVE = sprint-change-proposal-2026-05-05 + post-pivot edits applied to source docs; PRE-PIVOT methodology mentions are historical/superseded

## Implementation Sequence (12 steps from architecture)
- 1 Init Expo + TypeScript; 2 NativeWind + React Native Reusables + design tokens; 3 React Navigation + Zustand; 4 Data layer MMKV + SQLite + schema (3-value view_mode CHECK); 5 FFmpeg integration (fork + config plugin); 6 OpenCV (react-native-fast-opencv) for HSV + pHash; 7 DetectionConfig service (Firestore fetch + MMKV cache + offline fallback); 8 Detectors (gameDetector + mapIdentifier + blackScreenDetector fallback); 9 Video player (expo-av) + Cinema Mode UI + ViewModeToggle 3-value; 10 Audio recording 3-slot model; 11 Firebase Auth + subscription validation; 12 Export pipeline (exportRecipes per view_mode + exportPipeline + audio overlay)

## Risks
- HIGH: ffmpeg-kit-react-native deprecated Jan 2025 (archived June 2025) — mitigation = community fork `jdarshan5` actively monitored, Plan B = custom native module via Expo Modules API
- MEDIUM: Process killed by Android OS in background — mitigation = save state, foreground service notification, resumable from checkpoint
- MEDIUM: Foreground Service Android config — mitigation = additional Expo config plugin or `expo-task-manager` evaluation (Gap Analysis #4)
- LOW: Keyframe spacing variable — mitigation = tolerance on transition detection, long-GOP black-screen detector fallback
- LOW: Map not identified by pHash — mitigation = mark `map_name='unknown'`, navigation still works
- LOW: Detection config Firestore unreachable — mitigation = MMKV cache, then bundled default config
- LOW: Codec unsupported at import — mitigation = strict validation + clear error
- MARKET: niche size — mitigation = validate 20 early-adopter coupons in 3mo
- RESOURCE: solo dev — mitigation = ultra-lean MVP, Firebase simplifies backend
- TECHNICAL: React Native bridge perf — mitigation = native modules if overhead too high
- TECHNICAL: FFmpeg/OpenCV mobile perf — mitigation = PC prototype first, then mobile port (validated via R&D 2026-04 on KDA/HSV + pHash methodology)

## Open Questions / Attention Points
- Lib versions not pinned (Expo manages compatibility, fixed at init)
- Foreground Service Android: config plugin vs `expo-task-manager` — to evaluate
- iOS Phase 2: validate FFmpeg fork config plugin works on iOS build
- Optional follow-up: ultra-review rewritten Epic 7 in epics.md once Story 7.5 lands (any AC tweaks)
- Mobile reads `user.isPaid` boolean only; web/Stripe writes other fields — possible mismatch with web's richer schema (`status`/`plan`/`stripe_*`); flag for monorepo merge

## Test Strategy Notes
- Unit tests co-located with source (e.g., `VideoPlayer.test.tsx` next to `VideoPlayer.tsx`)
- Story 7.6 export recipes: tested headless via FFmpeg dry-run, no full encode in tests
- Story 2.2 testing seam = gameDetector + mapIdentifier (post-pivot)
- Manual: orientation in both portrait/landscape on all screens; reference Poco X5 + small phone 5.5" + large phone 6.7"+; WCAG AA contrast verification (4.5:1 normal text, 3:1 large); 44x44 touch targets especially timeline handles + overlay controls; system font scaling at largest setting

## Accessibility
- Target WCAG AA where applicable to mobile video review
- Soft white #F0F0F0 on #101014 = ~17:1 (exceeds AAA); secondary #8B8F96 ≈ 7:1 (exceeds AA)
- 44x44 min touch targets
- No color-only indicators: every state has shape/icon/content change as primary signal (clip selected = bracket handles + orange tint; minimap = video content itself changes; recording = blinking mic + red dot icon animation)
- Respects system font scaling
- Intentionally skipped: TalkBack/VoiceOver (product inherently visual), audio descriptions (user-generated content), keyboard navigation (mobile-only)
- Motion sensitivity: blinking mic uses icon + color, not animation alone

## Architecture Status
- READY FOR IMPLEMENTATION (validated 2026-01-30, refreshed 2026-05-05 post-pivot)
- 33/33 FRs covered; 12/12 NFRs covered; no critical gaps
- Stack 100% cross-platform-ready (Android MVP, iOS Phase 2 with no refactoring)
- Service-boundary pattern (shared services as sole native-lib access) makes lib swaps low-risk
- Patterns chosen for junior dev profile (first prod app, RN experience exists)
