# Architecture — apps/mobile

> Part `mobile` (Expo / React Native). Imported from the legacy `Warden` repo at Phase 4 with full git history (88 commits). Currently mid-Sprint 2.5 in legacy planning terms.

## Executive summary

A React Native (Expo SDK 54) coaching app that ingests a video file, segments it into "rounds" by classifying each keyframe against ROI/HSV zone rules, identifies the EVA map per round from the same rule fires, and lets the coach review, clip, and annotate selected rounds. Detection runs **on-device** — since Story 12.4c that means **one native call per session**: MediaCodec decodes the keyframes in RAM and a Kotlin integer evaluator produces per-rule fire bits, which TypeScript scores. A 60–90 minute session is processed without a server round-trip, and without writing a single frame to disk.

_(Superseded 2026-09-17: this chain used to be "black-screen + KDA / map-bar transitions" and "perceptual hashing" over JPEGs decoded by an OpenCV JSI bridge. The pHash path produced `unknown` map labels on HUD 2.0 footage, which is the hole Story 12.4c closes; `react-native-fast-opencv` was removed from the app in the same story, its last caller having gone.)_

State is split across:

- **expo-sqlite** (`warden.db`) — durable session/segment/clip/audio rows.
- **react-native-mmkv** — ephemeral key/value: auth cache, prefs, processing checkpoints, detection-config cache.
- **Firestore** — `users/{uid}` (subscription gate) and `detection_config/latest` (tunable detector params with stale-while-revalidate).

## Architecture pattern

**Feature-sliced + thin app shell.** [`src/app/`](../apps/mobile/src/app/) is just navigation + screen composition. All domain logic lives under [`src/features/<slice>/`](../apps/mobile/src/features/), one folder per epic-level concern. Cross-cutting primitives live under [`src/shared/`](../apps/mobile/src/shared/).

```
src/app/
  RootNavigator.tsx       Auth-gated stack — Login | (Home + Processing)
  screens/HomeScreen.tsx
src/features/
  auth/                   Firebase Auth + subscription gate
  audio-commentary/       (Story 6 — audio comments on clips)
  clip-export/            Clip mode + share screens
  session/                List, repository (SQLite), Card View
  video-import/           DocumentPicker → MP4 validation → SQLite insert
  video-playback/         Cinema mode
  video-processing/       The detection pipeline (heaviest folder)
src/shared/
  components/             {Button, Card, LoadingSpinner, Toast} + hud/ atoms
  services/               {database, ffmpeg, detectionEngine, foregroundService, storage} — native bridges
  types/index.ts          Domain types: Session, MapSegment, ClipExport, AudioComment
  hooks/, utils/
```

## Technology stack

| Category              | Tech                                    | Version       | Notes                                                                                                                                                        |
| --------------------- | --------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Runtime               | Expo SDK                                | 54            | `newArchEnabled: true` in [app.json](../apps/mobile/app.json)                                                                                                |
| RN                    | react-native                            | 0.81.5        |                                                                                                                                                              |
| React                 | react                                   | 19.1.0        |                                                                                                                                                              |
| Auth                  | firebase                                | ^12.8.0       | + `@react-native-google-signin/google-signin` ^14 (Web client ID flow)                                                                                       |
| Persistence (durable) | expo-sqlite                             | ^16.0.10      | WAL + foreign_keys ON, 4 tables (see [data-models-mobile.md](./data-models-mobile.md))                                                                       |
| Persistence (KV)      | react-native-mmkv                       | ^3.3.3        | **Pinned to v3** — v4 requires Nitro Modules incompatible with RN 0.81 (silent boot crash). See [storage.ts](../apps/mobile/src/shared/services/storage.ts). |
| State                 | zustand                                 | ^5.0.11       | + zustand/middleware persist with MMKV adapter                                                                                                               |
| UI                    | nativewind                              | ^4.2.1        | Tailwind on RN                                                                                                                                               |
|                       | tailwindcss                             | ^3.3.2        |                                                                                                                                                              |
| Video                 | @wokcito/ffmpeg-kit-react-native        | ^6.1.2        | FFmpeg-kit 6.1.4 native AAR, 16-kb page-aligned for Android 15+. Auto-links via RN autolinking.                                                              |
|                       | expo-file-system                        | ^19.0.21      |                                                                                                                                                              |
|                       | expo-document-picker                    | ^14.0.8       |                                                                                                                                                              |
| Crypto                | expo-crypto                             | ~15.0.8       | UUID generation for SQLite primary keys                                                                                                                      |
| Navigation            | @react-navigation/native + native-stack | ^7.1 / ^7.12  |                                                                                                                                                              |
| Test                  | jest, jest-expo                         | ^29.7 / ~54.0 | `transformIgnorePatterns` widened for ESM RN deps                                                                                                            |
| TS                    | typescript                              | ~5.9.2        | extends `@warden/tsconfig/react-native.json`                                                                                                                 |

## Boot sequence

1. [index.ts](../apps/mobile/index.ts) registers `App` with Expo.
2. [App.tsx](../apps/mobile/App.tsx) loads Roboto + JetBrainsMono fonts (each in 400/500/700) and renders a dark splash placeholder until fonts resolve.
3. `useEffect` (one-shot):
   - `void bootstrapDetectionConfig()` — primes the MMKV cache from Firestore (best-effort; surfaces `OfflineFirstLaunchError` / `MalformedRemoteConfigError` to the bootstrap, not the UI).
   - If `EXPO_PUBLIC_AUTH_BYPASS === 'true'`: injects a fake `{uid:'dev-bypass-user', isPaid:true}` user and returns. Logs a warning. **Remove this branch + the env var before shipping.**
   - Otherwise: `googleSignInService.configure()` → `authService.listenToAuthChanges()` (Firebase `onAuthStateChanged` → maps to `AuthUser` via `mapFirebaseUser`, which calls `subscriptionService.checkSubscription`) → `subscriptionService.startPeriodicRevalidation()` (60-min interval).
4. `RootNavigator` reads `useAuthStore.isAuthenticated` and renders `Login` or `Home + Processing` accordingly. **Note: `isAuthenticated` is set to `true` only when both `user !== null` AND `user.isPaid`** — the subscription gate is enforced at navigation level, not just at backend level.

## State management

| Concern                             | Mechanism                                                                                                                         | Where                    | Persisted?                                                                                                                     |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| Auth user + paid flag               | Zustand store ([useAuthStore.ts](../apps/mobile/src/features/auth/useAuthStore.ts))                                               | feature/auth             | Yes — MMKV via zustand persist. Partialized to `{user, isAuthenticated, cachedAt}`. **30-day TTL** invalidates on rehydration. |
| Current session UI state            | Zustand store ([useSessionStore.ts](../apps/mobile/src/features/session/useSessionStore.ts))                                      | feature/session          | Yes — MMKV. Holds `currentSessionId`, `currentEpisodeIndex`, `playbackPositionMs`, `viewMode`, `sortOrder`.                    |
| Sessions / segments / clips / audio | SQLite ([database.ts](../apps/mobile/src/shared/services/database.ts))                                                            | shared/services          | Yes — `warden.db`                                                                                                              |
| Processing pipeline checkpoints     | MMKV keyed `processing.<sessionId>.<field>`                                                                                       | feature/video-processing | Yes                                                                                                                            |
| Detection config cache              | MMKV key `detection.config` ([detectionConfigService.ts](../apps/mobile/src/features/video-processing/detectionConfigService.ts)) | feature/video-processing | Yes                                                                                                                            |
| MMKV adapter                        | [storage.ts](../apps/mobile/src/shared/services/storage.ts)                                                                       | shared/services          | n/a — typed wrapper + Zustand `StateStorage` adapter                                                                           |

Domain types are exported from [src/shared/types/index.ts](../apps/mobile/src/shared/types/index.ts):

```ts
Session       { id, video_file_path, name, duration_ms, status, created_at, updated_at }
MapSegment    { id, session_id, map_index, start_time_ms, end_time_ms, map_name, result_frame_path, score_orange, score_blue, created_at }
ClipExport    { id, session_id, map_segment_id, start_time_ms, end_time_ms, view_mode, status, export_quality, file_path, created_at, updated_at }
AudioComment  { id, clip_export_id, slot, file_path, duration_ms, created_at }
```

These match the SQLite schema 1:1 — see [data-models-mobile.md](./data-models-mobile.md).

## The processing pipeline

The detection / segmentation / map-id chain lives in [`src/features/video-processing/`](../apps/mobile/src/features/video-processing/). Orchestrated by [processingPipeline.ts](../apps/mobile/src/features/video-processing/processingPipeline.ts) in **3 stages** (Story 12.4c: it was 4 — keyframe extraction and detection COLLAPSED), each gated by an MMKV checkpoint so a relaunched pipeline resumes from the last completed stage.

```
Stage              Outputs (MMKV keys)                              Progress range
──────────────────────────────────────────────────────────────────────────────
detection          processing.<sid>.schema  (= 2)                      0–70 %
                   processing.<sid>.gameSegments                    incremental:
                   processing.<sid>.mapIdentifications              the native call
                   processing.<sid>.duration                        reports keyframe
                   processing.<sid>.analysis  (what ran, not the    progress as
                                               timeline)            device events
segmentation       processing.<sid>.segmentIds                       70–90 %
                   processing.<sid>.segmentData
                   (rows in SQLite map_segments)
results            (./results/map_<i>.jpg score-screen thumbs)        90–100 %
                   updates map_segments.result_frame_path
```

**There is no `keyframes` stage and no `events` key any more**, and a checkpoint written by the old
shape is DISCARDED on read (`schema !== 2`) rather than resumed — resuming one would skip the only
stage that now detects anything.

Detection is one call — `analyzeSession(requestId, videoPath, configJson, limit)` through
[detectionEngine.ts](../apps/mobile/src/shared/services/detectionEngine.ts) — which returns the rule
index (`refs`) and one hex fire-bit row per keyframe. **There is no GOP branch:** the engine decodes
keyframes only, by construction, and never holds the frame set, so the `hasShortGop` fork and the
two-pass black-screen fallback it selected were both deleted.

Above the bits, all in TypeScript and all pure:

1. [engineScoring.ts](../apps/mobile/src/features/video-processing/engineScoring.ts) — the **three
   distinct** classifier formulas (HUD `fires/n` normalized; `in_match` `fires/n` normalized then
   **hard-binary**; map-ID a **RAW unnormalized** weighted sum vs `identification_threshold`).
2. [gameDetector.ts](../apps/mobile/src/features/video-processing/gameDetector.ts) — the phase
   machine, in which **doubt is first-class and doubt HOLDS**: a split vote is emitted as `doubt`
   but does not advance the machine, so every frame has an emitted state and an internal one, and
   **spans are cut from the internal state**.
3. [mapIdentifier.ts](../apps/mobile/src/features/video-processing/mapIdentifier.ts) — one map label
   per span, from the summed per-frame aggregates; below threshold it is `null`, which is how
   `unknown` is spelled here.
4. [detectionTimeline.ts](../apps/mobile/src/features/video-processing/detectionTimeline.ts) —
   composes the above in Tool 12's order.

`buildMapSegments` zips game segments with map IDs into the `MapSegmentData[]` written to SQLite.
`extractFrameAt(video, ts, outputPath)` saves a score-screen thumbnail per segment at the
**timing-derived** score screen (the first keyframe after the span that resolved to `score_screen`,
per `score_screen_duration_ms`), clamped to `videoDurationMs - 50` to avoid past-EOF reads.

`analyze` is injectable in `RunPipelineOptions`, exactly as `FrameLoader` was: it is what lets the
pipeline's tests run without a device.

## Map config (v2) — what detection actually reads

[mapConfig.ts](../apps/mobile/src/features/video-processing/mapConfig.ts) owns the **v2** config:
`assets/detection/map_config.v2.json`, bundled by Metro (62 kB; present on first launch, offline,
with no I/O), validated against `contracts/map-config.schema.json` via `@warden/contracts`, and
handed to the native packer **as JSON text** — map iteration order lives in that string, because
`org.json.JSONObject` is a HashMap and loses it.

`listMapConfigCandidates()` is **the seam Story 1.13 widens** into the hybrid
stale-while-revalidate Firestore overlay, `schema_version` migration and the per-HUD manifest. HUD
version is selected **once per session** (`resolveSessionHudVersion`), and an unmatched HUD degrades
gracefully rather than aborting the session.

## Detection-config cache (v1 — no longer a detection input)

> **Story 12.4c:** the engine reads none of this. It is kept running because the first-launch-offline
> gate still blocks video processing, and removing `OfflineFirstLaunchError` is **Story 1.13's AC7**,
> which is engine-agnostic. Its ~20 tests stay green; nothing in the detection path calls it.

[detectionConfigService.ts](../apps/mobile/src/features/video-processing/detectionConfigService.ts) is a stale-while-revalidate cache over Firestore `detection_config/latest`:

- **Cache present + online:** return cache immediately, kick off background refresh **only if** `remote.version > cached.version`. Errors logged, never propagated.
- **Cache present + offline:** return cache.
- **No cache + online + valid payload:** fetch, validate, cache, return.
- **No cache + offline (or doc missing):** throw `OfflineFirstLaunchError`.
- **No cache + malformed remote payload:** throw `MalformedRemoteConfigError` (so bootstrap can avoid the misleading "open while online" copy).

Three singleflights guard `inflightInitialFetch`, `inflightBackgroundRefresh`, `inflightForcedRefresh` so per-frame detector reads in the hot path share a single Firestore round-trip.

A module-level memo (`memoCache`) avoids re-parsing JSON / re-validating on every read. The synchronous accessor `getCachedDetectionConfig()` is for callers that already know the cache is primed (e.g. detectors invoked after `getDetectionConfig()` resolved at startup).

## Auth + subscription gate

[authService.ts](../apps/mobile/src/features/auth/authService.ts):

- `login(email, password)` → `signInWithEmailAndPassword` → `mapFirebaseUser` → `useAuthStore.setUser`. Sets a friendly error message via `formatAuthError` if Firebase rejects.
- `logout()` → `signOut(auth)` → `useAuthStore.logout`.
- `listenToAuthChanges()` → `onAuthStateChanged` → on user, runs `mapFirebaseUser` (which calls `subscriptionService.checkSubscription`); on null, clears the store.

[subscriptionService.ts](../apps/mobile/src/features/auth/subscriptionService.ts):

- `checkSubscription(user)` reads `users/{uid}` from Firestore. Considers `status ∈ {active, trialing}` AND `current_period_end > now` as paid. **Network failure falls back to the cached `useAuthStore.user.isPaid`** rather than logging the user out.
- `startPeriodicRevalidation()` re-checks every 60 min, only updating the store on transition.

## Native modules

| Module                                                                           | Purpose                                                                                                     | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [@wokcito/ffmpeg-kit-react-native](../apps/mobile/src/shared/services/ffmpeg.ts) | Frame extraction at a timestamp, video duration                                                             | **Wired.** Lazy-loaded via `require(...)` to surface a clear error if not present. Log redirection set to `NEVER_PRINT_LOGS` to avoid Metro spam. **Story 12.4c removed `extractKeyframes` and `getGopInfo`** — the engine decodes keyframes itself, and the GOP branch they served no longer exists.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ~~opencv (JSI)~~ — **REMOVED 2026-09-17, Story 12.4c**                           | —                                                                                                           | **Gone, dependency and all.** `loadFrameFromPath` existed to decode the keyframe JPEGs the old stage 1 wrote to disk; with that stage collapsed into `analyzeSession`, the binding had no callers, so `opencv.ts`, its pure-TS pHash primitives and `react-native-fast-opencv` were deleted together. This retires a native module and SEC-007 entry 2. The results stage uses **FFmpeg's** `extractFrameAt`, never OpenCV.                                                                                                                                                                                                                                                                                                                                                                                                          |
| react-native-mmkv                                                                | KV store + Zustand persist storage                                                                          | Wired (v3 pinned).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| expo-sqlite                                                                      | Durable rows                                                                                                | Wired.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| [detectionEngine](../apps/mobile/src/shared/services/detectionEngine.ts)         | `analyzeSession`, `cancelAnalysis` (production) + `runBench`, `describeDevice`, `isEngineAvailable` (bench) | **WIRED ON THE PRODUCTION PATH since Story 12.4c** — `processingPipeline.ts`'s detection stage is `analyzeSession`, one call per session, with progress as `WardenDetectionEngineProgress` device events and cooperative cancellation polled once per keyframe. (It was: bench only.) The **fifth** native module (architecture.md [INVARIANT: native-modules-only-via-shared-services] + SEC-007 entry 5). Android-only by construction (amendment 5c). Bound surface after Story 12.4b: `MediaCodec` + `MediaExtractor` + `WardenColorConvert` (bt709 limited-range YUV→BGR) + `WardenCpuBaseline` (integer rule evaluation) — **no GLES/EGL**, deleted 2026-09-17 once the CPU substitution was proved at 0 disagreements. Legacy `ReactPackage`, not a TurboModule. Wiring it into `processingPipeline.ts` is **Story 12.4c's**. |

## Path traversal hardening

[ffmpeg.ts](../apps/mobile/src/shared/services/ffmpeg.ts) defines `SAFE_SESSION_ID = /^[a-zA-Z0-9_-]+$/` and `assertSafeSessionId(sessionId)` to reject session ids that could escape the cache root via path traversal (`..`, `/`, etc.). All on-disk paths are namespaced under `getProcessingDir(sessionId)`.

## Tests

| Layer          | Suite                                                                                                                                                                                                                                               |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pipeline atoms | `src/features/video-processing/__tests__/` — `detectionConfig`, `detectionConfigBootstrap`, `detectionConfigService`, `gameDetector`, `mapConfig`, `mapIdentifier`, `processingPipeline`, `segmentation`                                            |
| Engine parity  | `src/features/video-processing/__tests__/tool12Parity.test.ts` — the TS scoring/phase port against a **generated, committed** fixture of Tool 12's own output, including all 1061 keyframes of a real capture (`apps/mobile/bench/12-4c/REPORT.md`) |
| Video import   | `src/features/video-import/__tests__/` — `useVideoImport`, `videoImportService`                                                                                                                                                                     |
| Native seams   | `src/shared/services/__tests__/` — `detectionEngine` (incl. cross-language lockstep guards read off the Kotlin), `colorConvert`, `foregroundService`                                                                                                |
| App-level      | `src/__tests__/`                                                                                                                                                                                                                                    |

Run with `pnpm --filter mobile test` (jest-expo preset, ESM transformIgnorePatterns widened for RN ecosystem).

## Known issues / debt

- [`getReactNativePersistence`](../apps/mobile/src/features/auth/firebaseConfig.ts) is removed/relocated in firebase v12. There is a TODO about migrating to `@react-native-firebase/*` for native token refresh + offline auth.
- The engine's on-device half is unverified in CI by construction: jest cannot run Kotlin and there is no instrumentation harness in the repo. The fire bits are held to an independent PC oracle instead (`apps/mobile/bench/12-4c/`), with the MediaCodec half deferred to the epic-end device pass.
- **`the_rock` fragments into 11 spans** on the reference capture: its `in_match` zones alternate 1.0/0.0 on a ~50 s period, confidently, so doubt-holding cannot merge them. Zone-data behaviour, not port behaviour — Stories 9.9b / 9.16.
- ESLint not configured for mobile yet (`"lint": "echo 'eslint not configured for mobile yet'"`).
- `EXPO_PUBLIC_AUTH_BYPASS` env var must be removed before shipping.
- mobile `.env.example` still describes the legacy `users/{uid}.isPaid` schema even though `subscriptionService.ts` reads `status` + `current_period_end`. Update before Phase 6 sign-off.
