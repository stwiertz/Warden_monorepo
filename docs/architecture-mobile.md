# Architecture — apps/mobile

> Part `mobile` (Expo / React Native). Imported from the legacy `Warden` repo at Phase 4 with full git history (88 commits). Currently mid-Sprint 2.5 in legacy planning terms.

## Executive summary

A React Native (Expo SDK 54) coaching app that ingests a video file, segments it into "rounds" by detecting black-screen + KDA / map-bar transitions, identifies the EVA map per round via perceptual hashing, and lets the coach review, clip, and annotate selected rounds. Detection runs **on-device** (FFmpeg-kit + an OpenCV JSI bridge — pending — and a pHash matcher in pure TS), so a 60–90 minute session can be processed without a server round-trip.

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
  services/               {database, ffmpeg, opencv, storage} — native bridges
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

The detection / segmentation / map-id chain lives in [`src/features/video-processing/`](../apps/mobile/src/features/video-processing/). Orchestrated by [processingPipeline.ts](../apps/mobile/src/features/video-processing/processingPipeline.ts) in 4 stages, each gated by an MMKV checkpoint so a relaunched pipeline resumes from the last completed stage.

```
Stage              Outputs (MMKV keys)                              Progress range
──────────────────────────────────────────────────────────────────────────────
keyframes          (FFmpeg ./keyframes/*.jpg on disk)                 0–30 %
detection          processing.<sid>.events                            30–70 %
                   processing.<sid>.gameSegments
                   processing.<sid>.mapIdentifications
                   processing.<sid>.duration
segmentation       processing.<sid>.segmentIds                        70–90 %
                   processing.<sid>.segmentData
                   (rows in SQLite map_segments)
results            (./results/map_<i>.jpg score-screen thumbs)        90–100 %
                   updates map_segments.result_frame_path
```

Detection has two paths driven by GOP info from `getGopInfo(videoPath)`:

- **shortGop (fast path):** stream every keyframe through `createGameDetector({config, processingResolution}).processFrame(buf, ts)`. KDA/HSV-driven — see [gameDetector.ts](../apps/mobile/src/features/video-processing/gameDetector.ts).
- **longGop fallback (memory-tight):** two passes. Pass 1 walks every keyframe, collects `saturationMean(buf, teamBarRoi)` only (a single float). `buildSaturationWindowsFromValues` finds windows. Pass 2 re-loads only the buffers inside each window and runs `detectBlackScreensInWindow`. This avoids holding ~600 MB of decoded frames for a 60–90 min session.

Both paths emit the same `GameDetectorEvent[]` stream → `pairEventsIntoSegments` → `GameSegmentTimeline[]` → `identifyMapsForSegments` (samples a mid-segment keyframe per segment, pHashes it, looks up against `detection_config.maps`).

`buildMapSegments` zips game segments with map IDs into the `MapSegmentData[]` written to SQLite. `extractFrameAt(video, ts, outputPath)` saves a result-screen thumbnail per segment (clamped to `videoDurationMs - 50` to avoid past-EOF reads).

`FrameLoader` is injectable so the pipeline lands before the OpenCV JSI binding does. Default loader (`loadFrameFromPath`) **throws** until the native bridge is wired up; tests inject a synthetic loader.

## Detection-config cache

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

| Module                                                                           | Purpose                                                                         | Status                                                                                                                                            |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| [@wokcito/ffmpeg-kit-react-native](../apps/mobile/src/shared/services/ffmpeg.ts) | Keyframe extraction, frame extraction at timestamp, GOP probing, video duration | **Wired.** Lazy-loaded via `require(...)` to surface a clear error if not present. Log redirection set to `NEVER_PRINT_LOGS` to avoid Metro spam. |
| [opencv](../apps/mobile/src/shared/services/opencv.ts) (JSI)                     | `loadFrameFromPath`, `saturationMean`, `scaleRoi`, `FrameBuffer`, `Resolution`  | **Stub.** `loadFrameFromPath` throws — tests inject synthetic loaders. Plan: ship a JSI binding to OpenCV.                                        |
| react-native-mmkv                                                                | KV store + Zustand persist storage                                              | Wired (v3 pinned).                                                                                                                                |
| expo-sqlite                                                                      | Durable rows                                                                    | Wired.                                                                                                                                            |

## Path traversal hardening

[ffmpeg.ts](../apps/mobile/src/shared/services/ffmpeg.ts) defines `SAFE_SESSION_ID = /^[a-zA-Z0-9_-]+$/` and `assertSafeSessionId(sessionId)` to reject session ids that could escape the cache root via path traversal (`..`, `/`, etc.). All on-disk paths are namespaced under `getProcessingDir(sessionId)`.

## Tests

| Layer          | Suite                                                                                                                                                                                        |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pipeline atoms | `src/features/video-processing/__tests__/` — `blackScreenDetector`, `detectionConfig`, `detectionConfigBootstrap`, `detectionConfigService`, `gameDetector`, `mapIdentifier`, `segmentation` |
| Video import   | `src/features/video-import/__tests__/` — `useVideoImport`, `videoImportService`                                                                                                              |
| OpenCV bridge  | `src/shared/services/__tests__/opencv.test.ts`                                                                                                                                               |
| App-level      | `src/__tests__/`                                                                                                                                                                             |

Run with `pnpm --filter mobile test` (jest-expo preset, ESM transformIgnorePatterns widened for RN ecosystem).

## Known issues / debt

- [`getReactNativePersistence`](../apps/mobile/src/features/auth/firebaseConfig.ts) is removed/relocated in firebase v12. There is a TODO about migrating to `@react-native-firebase/*` for native token refresh + offline auth.
- OpenCV JSI binding pending — pipeline runs end-to-end in tests via injected `FrameLoader`s only.
- ESLint not configured for mobile yet (`"lint": "echo 'eslint not configured for mobile yet'"`).
- `EXPO_PUBLIC_AUTH_BYPASS` env var must be removed before shipping.
- mobile `.env.example` still describes the legacy `users/{uid}.isPaid` schema even though `subscriptionService.ts` reads `status` + `current_period_end`. Update before Phase 6 sign-off.
