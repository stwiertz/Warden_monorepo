> This section covers Warden mobile app (Expo/React Native) full planning state. Part 2 of 8 of the Warden legacy distillate.

## Identity & Stack
- Warden mobile = match-review app for EVA After-h coaches; offline-first; 100% on-device processing; Reader App login screen only (no IAP UI)
- Framework: Expo (managed → dev-client) + React Native + TypeScript strict; init via `npx create-expo-app@latest Warden --template blank-typescript`
- Rejected at init: Obytes (overhead), ExpoStarter (opinionated), custom (paid)
- State: Zustand per feature, MMKV `persist` middleware; pure stores, async logic in hooks/services
- Navigation: React Navigation (root stack)
- Styling: NativeWind (Tailwind for RN) + tailwind.config.ts for design tokens; React Native Reusables (shadcn/ui for RN, copy-paste ownership) themed dark + accent orange
- Rejected styling: Material Design (productivity-app look)
- Video processing: `ffmpeg-kit-react-native` community fork `jdarshan5/ffmpeg-kit-react-native` (original deprecated Jan 2025, archived June 2025); integrated via custom Expo config plugin `plugins/with-ffmpeg.js`; Plan B = custom native module via Expo Modules API if fork becomes unstable
- Computer vision: `react-native-fast-opencv` (JSI/C++, cross-platform); used for HSV color analysis + 64-bit pHash computation (NOT template matching post-pivot)
- Video player + audio recording: `expo-av` (Audio.Recording in AAC/.m4a so muxes without re-encoding); 100% custom UI
- Data layer (hybrid): MMKV (`react-native-mmkv`) for auth cache + session state + prefs; SQLite via `expo-sqlite` for structured data; filesystem for audio .m4a files
- Auth: Firebase JS SDK (modular v9+), no extra native module; Firebase Auth + Firestore
- Payments: external web (NextJS + Stripe); webhook → Firebase sets user.isPaid; mobile reads, never writes
- Build/deploy: EAS Build (cloud) + EAS Submit; envs = development / preview / production
- Required design-system deps: `react-native-svg`, `@expo-google-fonts/roboto`, `@expo-google-fonts/jetbrains-mono`, `expo-font`, `expo-linear-gradient`
- Min platform: Android API 24+ (Android 7.0); MVP Android only; iOS Phase 2 (after Apple license); stack chosen 100% cross-platform-ready

## Functional Requirements (33 FRs across 7 domains)
- Video import (FR1-4): import MP4 from device storage; list sessions; delete sessions; validate format with error toast on incompatibility
- Video processing (FR5-10): auto-detect game-state transitions on-device via keyframe analysis (FR5, methodology-agnostic); identify map per segment (FR6); compute time ranges per map/round (FR7); mark lobby segments excluded (FR8); process 1h20 video in background (FR9); resume processing after interruption (FR10)
- Playback & navigation (FR11-15): episode-style nav between maps using time ranges (FR11); play/pause within allowed ranges (FR12); seek within map segment (FR13); instant view-mode toggle Full/Minimap/Minimap+HUD (FR14, post-pivot 3-value); minimap = cropped ROI from source video, optional KDA+Score HUD overlay (FR15)
- Audio commentary (FR16-20): record voice before clip (FR16), during playback overlay (FR17), after clip (FR18); delete recorded comment (FR19); preview clip with comments before export (FR20)
- Clip export (FR21-25): select clip start/end within map (FR21); export Mobile 720p fast (FR22); export HD source resolution (FR23); export as standalone MP4 with embedded audio (FR24); exported clip plays without Warden installed (FR25)
- Session persistence (FR26-28): auto-save every 30s including position/comments/clips-in-progress (FR26); resume exactly where left off (FR27); persist across restarts and reboots (FR28)
- Auth & subscription (FR29-33): Firebase login (FR29); validate subscription on login (FR30); cache auth locally for offline (FR31); periodic re-validation when online (FR32); non-subscribed users see login screen only with no pricing/CTA (FR33, Reader App)

## Non-Functional Requirements (12 NFRs)
- Performance: NFR1 1h20 analysis <2min on Poco X5; NFR2 view-mode toggle <100ms; NFR3 Mobile-quality export <30s per minute of clip; NFR4 UI responsive during background processing (foreground service); NFR5 RAM <2GB during processing
- Reliability: NFR6 auto-save every 30s; NFR7 automatic resume after crash/kill; NFR8 voice recordings persisted immediately; NFR9 auth cache valid 30 days offline
- Security: NFR10 Firebase OAuth 2.0; NFR11 automatic token refresh; NFR12 no user data stored server-side (privacy by design)

## Detection Methodology — Post-Pivot (Sprint 2.5, validated 2026-04, approved 2026-04-20)
- Approach: KDA + HSV color-space analysis on ROIs from config (game-state 2-state machine: game-on / game-off, with long-GOP black-screen 3-state fallback); pHash 64-bit perceptual hash compared against fingerprints from Firestore config for map identification
- SUPERSEDES initial methodology (luminosity black-screen detector + OpenCV template matching against bundled `assets/images/map-templates/`); rejected because: less accurate, less maintainable (must redeploy app to update templates), brittle to luminosity/resolution/encoding variation
- Story 7.5 deletes `templateMatcher.ts` + `assets/images/map-templates/`; OpenCV wrapper retained but repurposed (HSV + pHash, not template matching)
- Detector files: `gameDetector.ts` (KDA/HSV), `mapIdentifier.ts` (pHash), `blackScreenDetector.ts` (long-GOP fallback)
- Unidentified-map handling: segments with no pHash match stored as `map_name = 'unknown'` but remain navigable (Story 2.5 AC4)
- Reference impl lives in `apps/tooling` Python (warden_analyzer.py + hash_validator.py + game_detector.py); mobile is a port of that pipeline

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

## Boundaries & Conventions
- Features never import each other; only `shared/services/{ffmpeg,opencv,database,storage}.ts` access native libs; cross-feature comm via Zustand stores or shared services; screens orchestrate feature hooks/components
- Naming: PascalCase components/types/interfaces; camelCase functions/vars/hooks (with `use` prefix); UPPER_SNAKE_CASE constants; kebab-case folders; co-located tests
- DB naming: snake_case plural tables, snake_case cols, `{table_singular}_id` FKs

## Data Model — SQLite Schema
- `sessions` (id TEXT PK, video_file_path TEXT NOT NULL, name TEXT, duration_ms INTEGER, status CHECK IN ('importing','processing','ready','error'), created_at, updated_at)
- `map_segments` (id PK, session_id FK CASCADE, map_index INT, start_time_ms INT, end_time_ms INT, map_name TEXT, result_frame_path TEXT, score_orange INT NULL, score_blue INT NULL, created_at) — score columns NULL in MVP, populated post-MVP via OCR; result_frame_path = scoreboard screenshot for Card View thumbnail
- `clip_exports` (id PK, session_id FK CASCADE, map_segment_id FK CASCADE, start_time_ms, end_time_ms, view_mode CHECK IN ('full','minimap','minimap_hud') — POST-PIVOT 3-value, was ('pov','minimap'), status CHECK IN ('defining','locked','exporting','ready','shared'), export_quality CHECK IN ('mobile','hd'), file_path NULL until export complete, created_at, updated_at)
- `audio_comments` (id PK, clip_export_id FK CASCADE, slot CHECK IN ('before','during','after'), file_path NOT NULL, duration_ms NOT NULL, created_at) — 0 to 3 rows per clip, one per slot; silent clips have zero rows
- Schema migration tracked under Story 7.1: bump version, idempotent + reversible, existing `pov` rows → `full`

## Domain Types & MMKV Keys
- TypeScript domain types: `Session`, `MapSegment`, `ClipExport`, `AudioComment`, `ViewMode = 'full' | 'minimap' | 'minimap_hud'` (named union exported from `src/features/clip-export/types.ts`), `GameDetectorEvent`, `MapIdentificationResult`, `DetectionConfig`
- MMKV key conventions (dot-notation): `auth.token`, `auth.user`, `session.current.position`, `session.current.episode`, `prefs.viewMode`, `prefs.minimapHud`, `prefs.exportQuality`, `prefs.sortOrder`, `detection.config`

## Data Flow
- DetectionConfig (Firestore + MMKV cache + bundled default) feeds processing
- Import MP4 → Processing Pipeline → keyframes (FFmpeg `-skip_frame nokey`, low-res) → gameDetector (KDA/HSV 2-state machine) → mapIdentifier (pHash) → blackScreenDetector (long-GOP 3-state fallback when gameDetector uncertain) → MapSegments → SQLite
- Playback (expo-av) → ViewModeToggle (Full / Minimap / Minimap+HUD) → Audio commentary recording (expo-av) → Clip export (exportRecipes per view_mode + FFmpeg mux) → Standalone MP4 → OS Share

## Mobile Cross-cutting Integrations (mobile-side detail; see also `05-architecture-cross-cutting.md`)
- Firestore `map_config.json` / DetectionConfig: served from Firestore; cached in MMKV under `detection.config`; bundled default config shipped with app as final fallback; consumed by `src/features/video-processing/detectionConfig.ts` (schema + validator), `detectionConfigService.ts` (Firestore fetch + MMKV cache + singleflight), `detectionConfigBootstrap.ts` (startup wiring + offline-first-launch gate); Story 7.4 lands as no-op shim until Story 7.5 consumes it; config version checked, stale caches refreshed on next online launch; tunable without app redeploy
- Firestore `users/{uid}` doc: mobile reads `user.isPaid` boolean for entitlement gating (FR30); validated at login + periodically when online (FR32); written by web Stripe webhook flow (mobile is read-only); Reader App model means mobile NEVER references plans/prices/Stripe IDs — only the boolean
- Firebase Auth flow: `[Web NextJS + Stripe] → Stripe webhook → Firebase (user.isPaid=true)` then `[App RN] ← Firebase Auth Login → check user.isPaid → unlock features`; first connection requires online login; subsequent sessions use MMKV-cached auth (30d offline); processing 100% offline; auth via `auth/authService.ts` (Firebase JS SDK)
- Filesystem: source video referenced in-place (no copy); audio comments stored as .m4a files referenced by SQLite rows
- OS Share Sheet: clip distribution via Expo Sharing API; status updates clip_exports.status to `shared`
- Firebase project config (apiKey/authDomain/projectId): NOT specified in mobile artifacts — must come from monorepo shared config or env (must align with web)

## UX Architecture
- Two-layer architecture: Card View (episode triage, Netflix-style grid with result frames as thumbnails) + Cinema Mode (immersive review, YouTube-fullscreen-style, reveal-on-tap controls auto-hide 4s)
- Cold start: two clear paths "Resume last review" / "Import new session"; never blank state; if zero sessions → single prominent button "Import your first training session"
- Card sorting (triage-first): Temporal (default), Orange biggest win, Blue biggest win, Closest map; sort persists via `prefs.sortOrder`; sort sets next/prev order in Cinema Mode; score-based sorts gracefully degrade to temporal until OCR ships
- Cinema Mode navigation: explicit Next / Previous / Maps buttons (rejected swipe gestures because conflict with timeline scrubbing); single tap toggles controls overlay; double-tap top-left = power-user view-mode cycle Full → Minimap → Minimap+HUD
- Orientation: NO orientation lock (couch usage = unpredictable grip); landscape = video 100% + reveal-on-tap controls; portrait = video top + persistent controls below
- Screen sizes: 5.5" → 1-col Card grid; 6.0-6.4" → 2-col; 6.5"+ → 2-col with more metadata; 44x44 min touch targets; respect system font scaling
- Reference device: Poco X5 (Snapdragon 695, 6GB RAM, 6.67")
- Mock reference: `docs/design/warden-mocks/` static HTML/JSX (Warden.html opens 9 screens); mocks WIN on visual when this doc disagrees; this doc owns behavior + journeys + component contracts
- Visual revision 2026-05-01: adopted Tactical HUD direction (see `06-ux-design.md`)

## User Journeys (Mobile)
- J1 Coach happy path: import 1h20 → 90s auto-slice → Card View 8 maps lobby auto-removed → tap problem round → Cinema Mode → toggle Minimap → record voice "Lucas your flank is open" → export Mobile quality → share Discord → 15min total → done
- J2 Coach interruption: mid-review, app closed; 2h later reopens → exact map + position + comments-in-progress preserved → finish in 5min
- J3 Passive Player Lucas: Discord notification → tap clip → inline playback (no app install) → minimap + coach voice plays → "Ok compris, je me cale sur toi" → corrects next session
- J4 Active Player Maxime: imports session → auto-slice → toggles Full/Minimap solo without coach commentary → discovers patterns → develops analytical capability; identical to coach UI minus export step
- J3 lives entirely in Discord/WhatsApp; Warden UX responsibility ends at share sheet
- J4 partially supported in MVP (no review-import mode for coach annotations); review-import deferred to V2

## Voice Recorder & Clip Creation
- Clip creation flow: tap "clip" → 30s region centered on current playback → drag bracket handles to refine → optional 3-slot voice → preview → confirm; <10s to define
- Voice recorder 3 slots — all independent, all optional:
  - Before: tap "before" → still frame of clip first frame + blinking mic + red dot → audio over still frame plays before clip
  - During: tap "on clip" → countdown → clip plays + recording; if coach keeps talking past clip end, last frame freezes while audio continues
  - After: tap "after" → still frame of clip last frame + blinking mic → audio over still frame plays after during-overflow
- Tap-to-start, tap-to-stop; no auto-stop, no silence detection
- Silent clips skip all voice segments
- Exported clip structure: `[before voice + still frame] → [clip video + during voice] → [frozen frame + during overflow] → [after voice + still frame]`; all segments optional

## View Mode System (Stories 7.1-7.3+7.6)
- 3 modes: Full (source video, no crop, replaces original 'pov'); Minimap (cropped to map ROI from detection config); Minimap+HUD (minimap crop + KDA + Score overlays drawn from `map_segments` data)
- Top-level Full↔Minimap segmented control + HUD sub-toggle (only active when top-level=Minimap)
- Double-tap top-left cycles all 3
- Persisted via `prefs.viewMode` and `prefs.minimapHud` in MMKV
- Toggle target <100ms = crop/style change on same expo-av source (NFR2) — no player swap

## Components Catalog
- Video Player (Cinema Mode), View Mode System, Timeline Scrubber, Clip Region Selector (30s default with bracket handles), Voice Recorder (3 slots), Episode Card, Sort Dropdown, Export Progress (MVP Option 1 modal vs Goal Option 3 queue indicator)

## Feedback & Interaction Patterns
- Success toast bottom 3s auto-dismiss; minor error toast 5s red; critical error blocking modal (e.g., incompatible format)
- Short processing inline progress; long processing (auto-slice) full-screen progress + rotating tips every 5-8s
- Processing screen rotating tips: "Double tap top left to switch to minimap"; "Drag clip handles to adjust"; "Add voice before/during/after clip"; "Sort by closest score for important rounds"; "Progress saved automatically"
- Bottom sheet rules: never covers >40% (video stays visible), drag-down dismisses, dark surface + orange separator
- Gesture rules: every gesture has button equivalent; no hidden gestures required for core
- Export UX two-phase design: MVP Option 1 = encode immediately, "Preparing clip..." progress, share sheet opens when done (Story 5.4); Goal Option 3 = queue clip for background encoding, subtle queue indicator "2 ready, 1 processing", share-when-ready (deferred post-MVP, architecture supports via isolated `exportPipeline.ts` + extensible Zustand `clipQueue` + reusable foreground service); upgrade requires NO UI changes to clip creation flow

## Mobile Inspirations & Anti-Patterns
- Inspirations: Discord (dark content-first, inline media, no onboarding), YouTube (scrub bar with thumbnails, chapter markers = episodes, double-tap skip muscle memory, fullscreen toggle), Netflix (episode grid mental model)
- Anti-patterns: tiny overlay minimap (current failure mode — must be FULL-SCREEN), export friction (no format/quality/title pre-flight, one tap to share, OS sheet handles), onboarding tutorials, in-app social features (Discord owns social), productivity UX language (no "projects/workspaces/dashboards")
- Coach mental model: video editing tool (timeline-centric, non-destructive, export-oriented, tool-not-platform)

## Device Permissions (Android)
- READ_EXTERNAL_STORAGE: video import (mandatory)
- RECORD_AUDIO: voice comments (mandatory)
- FOREGROUND_SERVICE: background processing notification (mandatory)
- INTERNET: Firebase auth + subscription validation (mandatory)
- Foreground Service Android needs additional Expo config plugin OR `expo-task-manager` evaluation — flagged as non-blocking attention point in Architecture Gap Analysis #4

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

## Implementation Sequence (12 steps from architecture)
- 1 Init Expo + TypeScript; 2 NativeWind + React Native Reusables + design tokens; 3 React Navigation + Zustand; 4 Data layer MMKV + SQLite + schema (3-value view_mode CHECK); 5 FFmpeg integration (fork + config plugin); 6 OpenCV (react-native-fast-opencv) for HSV + pHash; 7 DetectionConfig service (Firestore fetch + MMKV cache + offline fallback); 8 Detectors (gameDetector + mapIdentifier + blackScreenDetector fallback); 9 Video player (expo-av) + Cinema Mode UI + ViewModeToggle 3-value; 10 Audio recording 3-slot model; 11 Firebase Auth + subscription validation; 12 Export pipeline (exportRecipes per view_mode + exportPipeline + audio overlay)

## Mobile Risks
- HIGH: ffmpeg-kit-react-native deprecated Jan 2025 (archived June 2025) — mitigation = community fork `jdarshan5` actively monitored, Plan B = custom native module via Expo Modules API
- MEDIUM: Process killed by Android OS in background — mitigation = save state, foreground service notification, resumable from checkpoint
- MEDIUM: Foreground Service Android config — mitigation = additional Expo config plugin or `expo-task-manager` evaluation
- LOW: Keyframe spacing variable — mitigation = tolerance on transition detection, long-GOP black-screen detector fallback
- LOW: Map not identified by pHash — mitigation = mark `map_name='unknown'`, navigation still works
- LOW: Detection config Firestore unreachable — mitigation = MMKV cache, then bundled default config
- LOW: Codec unsupported at import — mitigation = strict validation + clear error
- MARKET: niche size — mitigation = validate 20 early-adopter coupons in 3mo
- RESOURCE: solo dev — mitigation = ultra-lean MVP, Firebase simplifies backend
- TECHNICAL: React Native bridge perf — mitigation = native modules if overhead too high
- TECHNICAL: FFmpeg/OpenCV mobile perf — mitigation = PC prototype first, then mobile port (validated via R&D 2026-04 on KDA/HSV + pHash methodology)

## Mobile Test Strategy Notes
- Unit tests co-located with source (e.g., `VideoPlayer.test.tsx` next to `VideoPlayer.tsx`)
- Story 7.6 export recipes: tested headless via FFmpeg dry-run, no full encode in tests
- Story 2.2 testing seam = gameDetector + mapIdentifier (post-pivot)
- Manual: orientation in both portrait/landscape on all screens; reference Poco X5 + small phone 5.5" + large phone 6.7"+; WCAG AA contrast verification (4.5:1 normal text, 3:1 large); 44x44 touch targets especially timeline handles + overlay controls; system font scaling at largest setting

## Mobile Accessibility
- Target WCAG AA where applicable to mobile video review
- Soft white #F0F0F0 on #101014 = ~17:1 (exceeds AAA); secondary #8B8F96 ≈ 7:1 (exceeds AA)
- 44x44 min touch targets
- No color-only indicators: every state has shape/icon/content change as primary signal
- Respects system font scaling
- Intentionally skipped: TalkBack/VoiceOver (product inherently visual), audio descriptions (user-generated content), keyboard navigation (mobile-only)
- Motion sensitivity: blinking mic uses icon + color, not animation alone

## Architecture Status
- READY FOR IMPLEMENTATION (validated 2026-01-30, refreshed 2026-05-05 post-pivot)
- 33/33 FRs covered; 12/12 NFRs covered; no critical gaps
- Stack 100% cross-platform-ready (Android MVP, iOS Phase 2 with no refactoring)
- Service-boundary pattern (shared services as sole native-lib access) makes lib swaps low-risk
- Patterns chosen for junior dev profile (first prod app, RN experience exists)

## Mobile Sprint Authority
- Original PRD/architecture/UX/epics French wording where it conflicts with the post-pivot English wording: AUTHORITATIVE = sprint-change-proposal-2026-05-05 + post-pivot edits applied to source docs; PRE-PIVOT methodology mentions are historical/superseded
- See `07-epics-and-sprint-state.md` for current epic + story state
