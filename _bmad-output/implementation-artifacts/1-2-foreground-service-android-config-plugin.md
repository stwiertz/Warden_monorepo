# Story 1.2: Foreground Service Android Config Plugin (BF-5)

Status: ready-for-dev

<!-- Validation is optional. Run validate-create-story before dev-story for a quality check. -->

## Story

As **Stephane** (solo developer; Sprint 3 mobile critical-path lead),
I want **a custom Expo config plugin (`apps/mobile/plugins/with-foreground-service.js`) that injects an Android Foreground Service (`WardenProcessingService.kt`) hosting the main JS context, wired into `processingPipeline.ts` start/stop**,
So that **the J2 interruption-and-resume scenario works on Android — `runProcessingPipeline` survives backgrounding without the OS killing the JS context, FFmpeg subprocess + OpenCV JSI bindings remain usable across foreground/background transitions, and the sticky "Analyse en cours…" notification communicates progress to the user.**

**Type:** Brownfield Item 6 (BF-5) implementation — the architecture-bound choice (option a: custom `expo-config-plugin`, NOT `expo-task-manager`) materialises here. Hybrid deliverable: a JS Expo config plugin + a generated Kotlin Android service + a JS-side bridge module + processingPipeline.ts wire-up + manual J2 regression. **No automated tests for the native side** — the J2 manual gate IS the regression. Existing `processingPipeline.test.ts`-style unit coverage mocks the bridge calls.

**Why this is Brownfield, not greenfield:** the **decision** (option a over option b) was bound in `_bmad-output/architecture.md:804-823` and **the choice itself was the BF-5 item**. This story is the implementation of an already-made decision, not a decision-making spike. The dev agent does NOT re-litigate `expo-config-plugin` vs `expo-task-manager`; it executes option (a).

**Why this is NOT blocked by Story 1.1's binding-only cut:** Story 1.1 published a provisional rung-0 verdict; Story 1.1.1 (cancelled 2026-05-09) was replaced by ship-and-observe per the AR-SPIKE binding-only cut decision (see [[project_warden_ar_spike_binding_only]]). The foreground service is **independent of the perf-floor rung verdict** — even rung-3 (V2-defer auto-slice) needs the service if manual-clip-only V1 still runs FFmpeg encodes that may take seconds-to-minutes (PERF-005 soft target: 60s for a 30s Mobile-tier export). The architecture asserts "independent of spike; can land in parallel" (`epics-and-stories.md:786`).

**Sprint-fit:** **fits-in-one-sprint.** No automated test suite to write (manual J2 verification); the binding piece is small (~150 lines plugin + ~120 lines Kotlin + ~40 lines processingPipeline.ts wire-up); the risk surface is largely Android-14/15 FGS-API compliance + Expo-prebuild integration, not algorithmic complexity.

## Acceptance Criteria (checklist)

> **AC checkbox convention:** Items whose endpoint depends on **post-merge actions** (sprint-status `review → done` flip, PR-open) are held `[ ]` with inline carve-out notes. Items the dev agent fully controls during the work flip to `[x]` on completion. Convention inherited from Story 0.2's D1 resolution and Story 1.1 — tighten over precedent.

1. [ ] **AC1 — Expo config plugin file exists at the architecture-bound path with the architecture-bound behavior.** `apps/mobile/plugins/with-foreground-service.js` exists. It is a Node-resolvable `@expo/config-plugins`-style plugin (the function exported by default takes `(config, props?)` and returns the modified `ExpoConfig`). It MUST:
   - Add `<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>` to `AndroidManifest.xml` (Android 9+ baseline permission).
   - Add `<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>` to `AndroidManifest.xml` (Android 14+ mandatory granular permission matching the FGS type — see Dev Note "Android 14/15 FGS API contract").
   - Add `<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>` to `AndroidManifest.xml` (Android 13+ runtime permission for displaying the sticky notification; without it the notification silently doesn't appear on 13+ devices — the FGS still runs but is invisible to the user).
   - Add a `<service>` element inside `<application>` declaring `android:name=".WardenProcessingService"`, `android:foregroundServiceType="dataSync"`, `android:exported="false"`, `android:stopWithTask="false"` (the FGS keeps running even after the launcher task is swiped away — exactly the J2 backgrounding case).
   - Use `withAndroidManifest` (from `@expo/config-plugins`) for the manifest edits — NOT a `withDangerousMod` raw-file rewrite. Idempotency: re-running `expo prebuild --clean` must produce identical output (no duplicate permission entries, no duplicate `<service>` blocks).
   - Use `withDangerousMod` for the Kotlin source-file emission ONLY — there is no `@expo/config-plugins` helper for generating arbitrary Kotlin files. Write to `android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt` per architecture line 818. Idempotent — re-run overwrites the file rather than appending or duplicating.

2. [ ] **AC2 — Plugin registered in `app.json` and `expo prebuild` runs clean.** `apps/mobile/app.json` `expo.plugins` array contains `"./plugins/with-foreground-service"` (relative path; Expo resolves `.js` automatically). After registration: `pnpm --filter mobile exec expo prebuild --platform android --clean` succeeds with no warnings related to the new plugin or duplicate-permission errors. The regenerated `apps/mobile/android/app/src/main/AndroidManifest.xml` contains the 3 `<uses-permission>` lines (AC1) and the `<service>` declaration. The regenerated `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt` exists with the AC4 implementation. **Verification commands** to paste into the implementation record:
   - `grep -c FOREGROUND_SERVICE apps/mobile/android/app/src/main/AndroidManifest.xml` returns at least 2 (the two FGS permission lines).
   - `grep -c WardenProcessingService apps/mobile/android/app/src/main/AndroidManifest.xml` returns at least 1 (the `<service>` declaration).
   - `test -f apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt && echo OK`.

3. [ ] **AC3 — Android service class implemented.** `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt` is generated by the plugin and contains a Kotlin class `WardenProcessingService` extending `android.app.Service` with the following contract:
   - `onStartCommand(intent, flags, startId)` calls `startForeground(notificationId, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)` within 5 seconds (Android 14+ requirement — see Dev Note "Android 14/15 FGS API contract"). Returns `START_STICKY` so the OS attempts to restart the service if the process is killed under memory pressure.
   - `onCreate()` creates the notification channel `processing` if it does not exist: `IMPORTANCE_LOW` (non-disruptive — no sound, no vibration, no heads-up), name "Traitement vidéo" (French; the user-facing app is French per the legacy distillate), description "Notifications affichées pendant l'analyse vidéo en arrière-plan."
   - The sticky notification displays title "Analyse en cours…" (verbatim per architecture line 818), text "Préparation…" as the initial fallback when the MMKV key has no value, and dynamic text rebuilt by reading `processing.<sessionId>.stage` from MMKV via a 1-second handler loop (`Handler(Looper.getMainLooper()).postDelayed(...)`). The stage values are `keyframes` / `detection` / `segmentation` / `results` per `processingPipeline.ts:113-118`; the Kotlin side maps them to French strings (see Dev Note "Stage→French copy mapping").
   - `onDestroy()` cancels the polling Handler, removes the notification (`stopForeground(STOP_FOREGROUND_REMOVE)`), and releases the MMKV reader instance (best-effort).
   - Intent extras: `sessionId: String` (passed by the JS bridge so the service knows which MMKV key to poll). If the extra is missing, the service logs a warning and shows "Préparation…" indefinitely (defensive — the JS bridge MUST pass it, but a missing extra is not a crash).
   - The class is registered in the same package as the app (`team.warden.mobile` per `app.json` `android.package`).
   - Reads MMKV via `com.tencent.mmkv.MMKV` direct Kotlin API (the same native module that powers JS-side `react-native-mmkv@3.3.3`; the underlying library is `tencent/MMKV`). The MMKV instance ID must match the JS side: `MMKV.mmkvWithID("warden-storage")` — see `apps/mobile/src/shared/services/storage.ts:8` (`new MMKV({ id: "warden-storage" })`).
   - **Do NOT** instantiate Firebase / FFmpeg / OpenCV from Kotlin — the service's sole jobs are (a) keep the process alive (b) display the notification (c) poll MMKV. The actual pipeline work runs in the JS context via the existing `processingPipeline.ts` orchestrator.

4. [ ] **AC4 — JS bridge module exposing `start(sessionId)` / `stop()` to JS.** A small native bridge enables JS-to-Kotlin start/stop calls. Implementation choices (the architecture says "JSI bridge module"; the dev agent picks the lighter-weight option that satisfies the contract):
   - **Recommended path: legacy React Native Native Modules API** (TurboModules / new-arch compatible; `newArchEnabled: true` in `app.json:9`). Kotlin class `WardenProcessingModule` extends `ReactContextBaseJavaModule`; exposes two `@ReactMethod`-annotated methods `start(sessionId: String, promise: Promise)` and `stop(promise: Promise)`; registered via a `ReactPackage` listed in `MainApplication.kt` (which is itself prebuild-generated — the config plugin MUST also append the `add(WardenProcessingPackage())` line to `MainApplication.kt`'s `getPackages()` via `withDangerousMod`).
   - **Alternative path (acceptable if simpler in practice): Expo Modules API** (`expo-modules-core`). Same start/stop surface; auto-registered via `expo.modules.json` or a `kotlin Module()` definition; no `MainApplication.kt` mod required. **Note:** as of Expo SDK 54 the Expo Modules API is the recommended path for new native modules — pick this if the dev agent finds the `MainApplication.kt` patching messy.
   - JS-side wrapper file `apps/mobile/src/shared/services/foregroundService.ts` exposes a typed API: `export async function startForegroundService(sessionId: string): Promise<void>` + `export async function stopForegroundService(): Promise<void>`. **iOS guard:** both functions early-return on iOS (`if (Platform.OS !== 'android') return;`) — iOS Phase 2 ships `BGTaskScheduler` instead per architecture line 881.
   - The bridge module's Kotlin file lives at `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingModule.kt` (or wherever Expo Modules autolinking expects it for the alternative path) — generated by the plugin via `withDangerousMod` per AC1.

5. [ ] **AC5 — `processingPipeline.ts` wired to start/stop the service.** `apps/mobile/src/features/video-processing/processingPipeline.ts` imports `startForegroundService` + `stopForegroundService` from `../../shared/services/foregroundService` and:
   - Calls `await startForegroundService(sessionId)` immediately after `updateSessionStatus(sessionId, "processing")` (line 274) and BEFORE the checkpoint-gated stage execution (line 280).
   - Calls `await stopForegroundService()` in a `finally` block that wraps the existing `try/catch` (currently lines 280-520). The `finally` block ensures the service stops on success, on error, AND on any future code path that may exit early. **Critical: never leak the service** (architecture line 821) — `finally` is the only correct construct here.
   - The bridge calls MUST NOT throw if the native module is unavailable (e.g., in jest) — the JS wrapper at `foregroundService.ts` swallows `Error: native module WardenProcessing not found` and logs a `__DEV__`-gated warning. This preserves the existing test surface in `apps/mobile/src/features/video-processing/__tests__/*.test.ts` which does NOT load the native module.
   - **Idempotency at the JS side:** if `startForegroundService` is called twice in a row (e.g., the user retries a failed pipeline before the previous service has fully shut down), the Kotlin `onStartCommand` re-enters with the new `sessionId`; the Handler loop simply switches to the new MMKV key. No leak.
   - **Existing perf instrumentation preserved:** the `__perfStart` / `__perfMark` / `__perfStages` / `[PERF-002]` / `[PERF-009]` logging added by Story 1.1 stays untouched. The new bridge calls are added around (not inside) that instrumentation. **Verify** by diffing `processingPipeline.ts` after the change: the `__DEV__`-gated blocks at lines 249-265 and 484-499 + 502-517 are byte-identical post-edit.

6. [ ] **AC6 — `processingPipeline.test.ts` and sibling tests still pass.** `apps/mobile/src/features/video-processing/__tests__/` jest suite is green after the wire-up. The bridge module is mocked via `jest.mock('../../shared/services/foregroundService', () => ({ startForegroundService: jest.fn().mockResolvedValue(undefined), stopForegroundService: jest.fn().mockResolvedValue(undefined) }))` at the top of any new test file that needs it. **No regression:** every pre-existing test in this directory passes without modification (the mock at the JS wrapper layer means existing tests don't see the native bridge at all).
   - **New test file `apps/mobile/src/features/video-processing/__tests__/processingPipeline.test.ts`** (this file does NOT currently exist — confirmed by glob): scaffold it with the start/stop bridge-call contract. **Minimum 4 test cases:** (1) start is called once on entry with the correct sessionId; (2) stop is called on successful completion; (3) stop is called when an inner stage throws (verify via a forced throw in `extractKeyframes` mock); (4) stop is called even when start itself throws — defensive double-finally. The test wires synthetic `FrameLoader` + `detectionConfig` per the existing pattern in `apps/mobile/src/features/video-processing/__tests__/blackScreenDetector.test.ts:1-30` (verify the canonical mock shape there).
   - Full mobile jest suite `pnpm --filter mobile test` is green at story close.

7. [ ] **AC7 — Manual J2 test on Android dev build passes with Battery Optimization ENABLED.** Manual end-to-end procedure (record raw outcome in the implementation record's "Manual J2 verification" section):
   - **Setup:** Connect the Poco X5 Pro 5G (`dc72b871` per Story 1.1) via ADB. Battery optimization for Warden: `adb shell dumpsys deviceidle whitelist` — confirm `team.warden.mobile` is NOT on the whitelist (default; Battery Optimization is ENABLED). `pnpm --filter mobile exec expo run:android --device dc72b871` to install the dev build.
   - **Procedure:** Sign in with a paid test account. Import the 1h49 EVA After-h reference video staged at `/sdcard/Download/2026-01-18 12-10-30.mp4` (per Story 1.1 Task 3). Auto-slice begins → sticky notification appears with title "Analyse en cours…" and text matching the current stage. Press HOME button to background the app (Battery Optimization should NOT immediately kill the process because the FGS is running). Wait 60 seconds. Reopen the app via the launcher. **Expected:** the pipeline is still running (not in `error` state); the notification is still visible; the progress indicator on `ProcessingScreen` continues from where it was; the pipeline eventually completes successfully with `session.status === 'ready'`. **Or** the OS killed the JS context anyway (Doze / aggressive OEM management) — in which case the relaunch path reads the MMKV checkpoint and resumes from the last completed stage per `processingPipeline.ts:281-300`. **Either outcome is acceptable for J2** — the regression we are guarding against is "pipeline silently abandoned + no resume", not "process never killed under any circumstances".
   - **Record raw observations:** time-of-background; was-process-still-alive-on-resume (verify via `adb shell ps -A | grep team.warden.mobile`); did-checkpoint-resume-fire (verify via logcat `[processingPipeline]` traces or by inspecting MMKV `processing.<sid>.stage` post-resume); final session status; total wall-clock to completion.

8. [ ] **AC8 — Manual J2 test on Android dev build passes with Battery Optimization DISABLED.** Same procedure as AC7 with one change: add `team.warden.mobile` to the doze whitelist before running (`adb shell dumpsys deviceidle whitelist +team.warden.mobile`). **Expected:** the process stays alive across HOME-press indefinitely; auto-slice runs to completion without any OS interference; notification visible throughout. This is the upper-bound case (best for the user; closest to "desktop background process" semantics). **Record raw observations** per AC7 in the implementation record.

9. [ ] **AC9 — POST_NOTIFICATIONS runtime permission request wired.** On Android 13+, the `POST_NOTIFICATIONS` permission must be requested at runtime — declaring it in `AndroidManifest.xml` (AC1) is necessary but not sufficient. The dev agent adds a runtime permission request that fires:
   - Either (a) at app first-launch right before the import flow can be initiated (the natural moment — the user is about to start a pipeline that will use the notification);
   - Or (b) the first time `startForegroundService` is called in JS, just-in-time before the bridge actually starts the service.
   - Either path uses `PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS)` from `react-native`'s built-in `PermissionsAndroid` API — **no new dep**.
   - If the user denies the permission: the service still runs (the FGS itself does not require POST_NOTIFICATIONS — only the notification's visibility does), but the notification is invisible. Log a `__DEV__`-gated warning; **do not block the pipeline**. The user can re-grant via Android Settings → Notifications.
   - Implementation lives in `foregroundService.ts` (path b) or in `useVideoImport.ts` / `videoImportService.ts` (path a) — dev's choice. **Path (b) is preferred** because it co-locates with the service and survives if future code paths bypass video import.

10. [ ] **AC10 — Cross-platform readiness asserted; iOS Phase 2 path documented.** Per architecture line 884, V1 architecture asserts all mobile decisions are **cross-platform-ready**. This story does NOT ship iOS code — but it MUST NOT break iOS prebuild. Specifically:
    - The plugin's `withAndroidManifest` and `withDangerousMod` calls are Android-only; they MUST be guarded so they no-op on iOS (the `@expo/config-plugins` modifiers run regardless of platform — wrap any iOS-relevant logic in `if (config.modPlatform === 'android')` or rely on the modifier being Android-scoped, which `withAndroidManifest` already is).
    - `pnpm --filter mobile exec expo prebuild --platform ios` MUST succeed without errors mentioning the new plugin. **Note:** iOS prebuild may fail for OTHER reasons (FFmpeg-kit iOS fork, Firebase native modules, etc. — see architecture line 873-883); this AC only binds "no NEW iOS-prebuild errors are caused by `with-foreground-service.js`". Document any pre-existing iOS-prebuild errors separately if they surface.
    - JS wrapper `foregroundService.ts` MUST early-return on iOS (per AC4) — `Platform.OS !== 'android'` is the guard.
    - A `// iOS Phase 2: BGTaskScheduler + state checkpointing (architecture.md:881)` TODO comment lives in `foregroundService.ts` documenting the iOS deferral. **No iOS implementation in this story.**

11. [ ] **AC11 — Sprint-status flip on completion.** _Held `[ ]` per AC checkbox tighten — the `review → done` portion is post-merge admin._ `_bmad-output/sprint-status.yaml` `development_status[1-2-foreground-service-android-config-plugin]` flips `backlog → ready-for-dev → in-progress → review → done` across the work; `last_updated` bumps to current ISO date at each flip. `epic-1` is already `in-progress` (verified at story creation 2026-05-14); no epic flip. Flips to `[x]` once `done` lands on `main`.

12. [ ] **AC12 — Single-PR delivery; tiny post-merge follow-up per Two-PR pattern.** _Held `[ ]` per the [[feedback_two_pr_docs_execution]] convention adapted for code stories._ All deliverable file modifications ship in **one PR** titled exactly `feat: foreground service Android config plugin (Story 1.2)`. PR body links to: this story file; architecture line 804-823 (`#### Brownfield Item 6`); epics-and-stories line 768-788 (`### Story 1.2`). Branch name: `foreground-service-android-config-plugin`. A tiny post-merge follow-up commit/PR carries the `review → done` flip + this AC + AC11. Flips to `[x]` once the main PR is open with the verbatim title; the post-merge flip is owned by the follow-up PR.

## Tasks / Subtasks

> **Workflow shape:** This is a brownfield-implementation story. The architectural choice (option a vs option b) is already bound; the dev agent's job is faithful execution. The AC checkbox-tighten convention (Story 1.1 precedent) applies to ACs whose endpoint depends on post-merge actions.

- [ ] **Task 1: Audit current state — plugins/, app.json, package.json (AC: 1, 2)**
  - [ ] Confirm `apps/mobile/plugins/` exists with only `.gitkeep` — **the architecture's `with-ffmpeg.js` mention at `architecture.md:1440` is plan-side, NOT a real file** (verified at story-creation glob 2026-05-14). The dev agent has NO in-repo plugin precedent to copy from; build from `@expo/config-plugins` scratch. (See Dev Note "No legacy plugin to mimic".)
  - [ ] Confirm `apps/mobile/app.json:30-32` `expo.plugins` array currently contains only `"@react-native-google-signin/google-signin"`. The new entry will be appended.
  - [ ] Confirm `apps/mobile/package.json` does NOT yet declare `@expo/config-plugins` as a direct dep. It is transitively available via `expo@~54.0.33` (the Expo SDK re-exports `@expo/config-plugins`). **Decision for the dev agent:** add `@expo/config-plugins` as a `devDependency` for explicit version pinning + clean type imports, OR import it from `expo/config-plugins` (the re-export path). **Recommendation:** explicit `devDependency` to avoid the re-export indirection breaking under a future Expo SDK bump.

- [ ] **Task 2: Implement `apps/mobile/plugins/with-foreground-service.js` (AC: 1)**
  - [ ] Create the file. Use plain CommonJS `module.exports = withForegroundService;` (matches the Expo plugin convention; no `.ts` — config plugins run at Metro pre-bundle time, not in the RN runtime).
  - [ ] Compose two modifiers via `withPlugins(config, [withManifestMod, withKotlinFileMod])` from `@expo/config-plugins`. **Idempotency principle:** every modifier reads the existing state, checks if the target entry already exists, and adds it only if absent.
  - [ ] **`withManifestMod`** uses `withAndroidManifest(config, async (config) => {...})`. Inside:
    - Get the `<manifest>` root via `config.modResults.manifest`.
    - For each of the 3 permissions (`FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`, `POST_NOTIFICATIONS`): if `manifest['uses-permission']?.some(p => p.$['android:name'] === '<perm>')` is false, push `{ $: { 'android:name': '<perm>' } }`.
    - For the `<service>` element: locate the `<application>` array (`manifest.application[0]`); ensure `application.service` is an array; if no entry with `$['android:name'] === '.WardenProcessingService'` exists, push `{ $: { 'android:name': '.WardenProcessingService', 'android:foregroundServiceType': 'dataSync', 'android:exported': 'false', 'android:stopWithTask': 'false' } }`.
    - Return `config`.
  - [ ] **`withKotlinFileMod`** uses `withDangerousMod(config, ['android', async (config) => {...}])`. Inside:
    - Resolve the target path: `path.join(config.modRequest.platformProjectRoot, 'app', 'src', 'main', 'java', 'team', 'warden', 'mobile', 'WardenProcessingService.kt')`.
    - Ensure parent directories exist via `fs.mkdirSync(path.dirname(targetPath), { recursive: true })`.
    - Write the Kotlin source per AC3 contract (embed the Kotlin code as a template-literal constant at the top of the plugin file — keep the Kotlin readable; do NOT base64-encode or otherwise obscure it).
    - Overwrite-on-prebuild (do NOT append). Idempotent.
    - Return `config`.
  - [ ] **Optional but recommended:** add `withRunOnce` from `@expo/config-plugins` to guard against double-application if the plugin is accidentally registered twice in `app.json`.
  - [ ] **No props.** The plugin takes no configuration object — service name, package name, FGS type, notification channel, and notification copy are all architecturally-bound constants. **Do not** add a `props` surface for "future flexibility"; per Story 1.1 "do NOT" pattern, premature configurability is anti-pattern.

- [ ] **Task 3: Implement the Kotlin service `WardenProcessingService.kt` (AC: 3)**
  - [ ] Inside the `withKotlinFileMod` template literal, write the Kotlin class per AC3 contract. Reference Dev Note "Kotlin service implementation sketch" for the full skeleton.
  - [ ] **MMKV integration from Kotlin:** the `tencent/MMKV` library is auto-included by `react-native-mmkv@3.3.3`'s autolinking (verify via `grep -r MMKV apps/mobile/android/app/build.gradle` after prebuild). From Kotlin: `MMKV.initialize(this)` in `onCreate`; `val mmkv = MMKV.mmkvWithID("warden-storage")`; `val stage = mmkv.decodeString("processing.<sessionId>.stage")` (the dot-notation key matches `processingPipeline.ts:90` `checkpointKey`).
  - [ ] **Stage→French copy mapping** (see Dev Note for the full table): `null/undefined → "Préparation…"`, `keyframes → "Extraction des images-clés"`, `detection → "Analyse des images"`, `segmentation → "Segmentation des parties"`, `results → "Extraction des miniatures"`. **Match `useVideoProcessing.ts:STAGE_LABELS:17-22` semantically; translate to French.** (The JS-side labels are in English today — there is a follow-up i18n story (Epic 8: Story 8.1 french-i18n-bundle) but Story 1.2 hardcodes French strings on the Kotlin side because the notification IS user-facing and English would be jarring in the French app context.)
  - [ ] Notification channel creation MUST be guarded by `if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)` (Android 8.0+; Expo SDK 54 minSdk is 24 — old devices skip the channel creation but the notification still appears). The min-SDK for Expo SDK 54 is **24** (Android 7.0); verify via `apps/mobile/android/app/build.gradle` `minSdkVersion` post-prebuild.
  - [ ] `startForeground(notificationId, notification, FOREGROUND_SERVICE_TYPE_DATA_SYNC)` — pass the typed-FGS-int as the third argument (Android 14+ overload). For older Android, fall back to the 2-arg overload via `if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) { startForeground(id, n, type) } else { startForeground(id, n) }`.

- [ ] **Task 4: Implement JS bridge — Kotlin module + JS wrapper (AC: 4)**
  - [ ] **Decision point:** pick legacy Native Modules API OR Expo Modules API. Document the choice in the implementation record's "Notes / decisions" section.
  - [ ] **If Expo Modules API (recommended for SDK 54):**
    - Generate `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingModule.kt` containing an `expo.modules.kotlin.modules.Module()`-style definition with two `AsyncFunction` slots: `start(sessionId: String)` and `stop()`. Inside `start`: `Intent` targeting `WardenProcessingService::class.java`, put `"sessionId"` extra, call `ContextCompat.startForegroundService(reactApplicationContext, intent)`. Inside `stop`: `Intent` for the same class, `reactApplicationContext.stopService(intent)`.
    - Register the module via `expo-modules-autolinking` (which the Expo SDK handles automatically once the file exists in the right path with the right package declaration).
  - [ ] **If legacy Native Modules API:**
    - Same Kotlin class as above but extending `ReactContextBaseJavaModule`; `@ReactMethod start(sessionId: String, promise: Promise) { startService...; promise.resolve(null) }`. Plus `WardenProcessingPackage.kt` that returns the module. Plus a `withDangerousMod` block that appends `add(WardenProcessingPackage())` to `MainApplication.kt`'s `getPackages()` — **this is fragile** (the `MainApplication.kt` is itself prebuild-generated and may change shape across Expo SDK versions). Prefer the Expo Modules API path.
  - [ ] Write `apps/mobile/src/shared/services/foregroundService.ts` per AC4 + AC9 + AC10:
    - Import the native module via `requireNativeModule('WardenProcessing')` (Expo) OR `NativeModules.WardenProcessing` (legacy).
    - Export `async startForegroundService(sessionId: string): Promise<void>` — iOS guard, POST_NOTIFICATIONS request, native-module-missing swallow.
    - Export `async stopForegroundService(): Promise<void>` — iOS guard, native-module-missing swallow.
    - Inline the iOS Phase 2 TODO comment per AC10.

- [ ] **Task 5: Wire `processingPipeline.ts` (AC: 5, 6)**
  - [ ] Add imports at line 39 area: `import { startForegroundService, stopForegroundService } from "../../shared/services/foregroundService";`
  - [ ] In `runProcessingPipeline` (lines 245-521): immediately after `await updateSessionStatus(sessionId, "processing");` (line 274), add `await startForegroundService(sessionId);`. **Do not** add `try/catch` around the start call — let any throw propagate to the existing outer `try/catch` so the session status flips to `"error"` naturally; the JS wrapper at `foregroundService.ts` already swallows the native-module-missing case (AC4).
  - [ ] Wrap the existing `try/catch` (lines 280-520) with a `try { ...existing try/catch... } finally { await stopForegroundService(); }`. **Pattern check before commit:** verify the original `try { stages } catch { setError; throw }` is untouched and the new `finally` is the OUTER layer, not nested inside the existing `try`. (Nesting inside would skip the stop call when the catch re-throws.)
  - [ ] Run `pnpm --filter mobile typecheck` to confirm no TS errors. Run `pnpm --filter mobile test` to confirm no jest regressions.

- [ ] **Task 6: Author new test file `apps/mobile/src/features/video-processing/__tests__/processingPipeline.test.ts` (AC: 6)**
  - [ ] Use `jest.mock('../../../shared/services/foregroundService', ...)` at the top. Mock both start+stop as resolved-undefined Promise spies.
  - [ ] Mock the OTHER deps the pipeline pulls in: `../../shared/services/ffmpeg` (extractKeyframes, getGopInfo, getVideoDuration, getProcessingDir, extractFrameAt), `../../shared/services/opencv` (loadFrameFromPath, saturationMean, scaleRoi), `../session/sessionRepository` (getSession, updateSessionStatus), `./segmentRepository` (insertMapSegments, updateResultFramePath), `../../shared/services/storage` (storage), `./detectionConfigService` (getDetectionConfig). Reference `apps/mobile/src/features/video-processing/__tests__/blackScreenDetector.test.ts:1-30` for the canonical mock-shape used elsewhere in this directory.
  - [ ] Test 1: "starts FGS on entry with sessionId" — invoke `runProcessingPipeline('test-session-1')`, assert `startForegroundService` called with `'test-session-1'` exactly once.
  - [ ] Test 2: "stops FGS on successful completion" — happy path through all 4 stages, assert `stopForegroundService` called once at the end.
  - [ ] Test 3: "stops FGS when a stage throws" — make `extractKeyframes` reject with `new Error('synthetic')`; assert `stopForegroundService` still called once. Assert `updateSessionStatus` called with `'error'` (existing behavior).
  - [ ] Test 4: "stops FGS when start itself throws" — make the mocked `startForegroundService` reject; assert `stopForegroundService` STILL called in the `finally`. (This validates the `try/finally` outer-wrap shape from Task 5.)
  - [ ] Run `pnpm --filter mobile test`; capture the green count (current count = 105 per Story 1.1 Task 2 sub-bullet; expect 109 after this story).

- [ ] **Task 7: Register the plugin + prebuild + verify (AC: 2, 10)**
  - [ ] Edit `apps/mobile/app.json:30-32` to append `"./plugins/with-foreground-service"` to the `expo.plugins` array. **Order matters in some cases**: the foreground-service plugin should run AFTER `@react-native-google-signin/google-signin` because the google-sign-in plugin also touches `AndroidManifest.xml` and tag-ordering after a prior plugin's edits is the simpler invariant. Verify ordering is fine by running prebuild; if there's a conflict, swap order and re-prebuild.
  - [ ] Run `pnpm --filter mobile exec expo prebuild --platform android --clean`. Verify zero new warnings.
  - [ ] Verify the 3 grep checks per AC2 sub-bullets. Verify the Kotlin file exists per AC2 sub-bullet.
  - [ ] Run `pnpm --filter mobile exec expo prebuild --platform ios` — confirm AC10 (no NEW iOS-prebuild errors caused by this plugin). Document any pre-existing iOS errors separately; **do not bundle iOS fixes into this story**.
  - [ ] **Do NOT commit the regenerated `apps/mobile/android/` or `apps/mobile/ios/` directories.** Per Story 1.1 Task 1 sub-bullet 3 + the root `.gitignore` entries added in Story 1.1, the prebuild artifacts stay un-committed. The plugin's SOURCE (the `.js` + the Kotlin template strings) is what ships; the regeneration is per-build.

- [ ] **Task 8: Manual J2 verification on Poco X5 Pro 5G (AC: 7, 8)**
  - [ ] Build the dev APK: `pnpm --filter mobile exec expo run:android --device dc72b871`. Verify the install succeeds and the app launches without React Native bridge errors. Capture the APK SHA-256 for the implementation record.
  - [ ] **AC7 procedure (Battery Optimization ENABLED):** follow the AC7 step-by-step. Record raw observations: time-of-background, was-process-alive-on-resume, did-checkpoint-resume-fire, final session status, total wall-clock.
  - [ ] **AC8 procedure (Battery Optimization DISABLED):** add `team.warden.mobile` to doze whitelist, re-run AC7 procedure. Record the same observations.
  - [ ] **Note on substrate gaps from Story 1.1:** the auto-slice path is currently blocked by gap #6 (detection_config not seeded + Firestore rules deny reads — see [[project_warden_ar_spike_binding_only]] Substrate gap audit). If `runProcessingPipeline` cannot fire in this dev environment, the manual J2 verification falls back to a **stub test**: instrument a temporary "fake pipeline" path that calls `startForegroundService('test-sid'); await sleep(60_000); stopForegroundService()` directly from a debug button on `HomeScreen`; verify the notification appears, persists during HOME-press, and disappears after stop. Document the stub-test fallback in the implementation record. This still validates AC1-AC6 + AC9 + AC10 + the FGS lifecycle; only AC7/AC8's "end-to-end pipeline survives backgrounding" assertion is weakened. **Open the substrate-gap follow-up commit if the gaps block real verification** — Stories 1-13/1-14/1-16 (per Story 1.1 substrate gap audit) eventually unblock the real flow.

- [ ] **Task 9: Commit, push, open PR (AC: 11, 12)**
  - [ ] `git checkout -b foreground-service-android-config-plugin` (off `main`).
  - [ ] Commit shape recommendation: **single commit** `feat: foreground service Android config plugin (Story 1.2)`. Subject lower-case verb-first per `@commitlint/config-conventional`. Body: brief summary of file changes; reference to architecture.md:804-823.
  - [ ] Flip `_bmad-output/sprint-status.yaml` `1-2-...: ready-for-dev → review` (one commit per Story 0.2 Lesson #7 — collapse intermediate `in-progress` into the single review-time diff).
  - [ ] `git push -u origin foreground-service-android-config-plugin`. Capture the PR-create URL (no `gh` CLI on Stephane's host — manual PR open via the URL, per Story 0.2 lesson + Story 1.1 Task 12 sub-bullet).
  - [ ] Open the PR with **exact** title `feat: foreground service Android config plugin (Story 1.2)` per AC12. Body links per AC12.
  - [ ] **Hold the post-merge follow-up** (the `review → done` flip + AC11/AC12 to `[x]` + any retrospective AC closures) for a tiny separate PR per the [[feedback_two_pr_docs_execution]] convention applied to code stories. Status stays `review` at this story's natural close; the follow-up PR ships the `done` flip.

## Dev Notes

### What this story is — and is NOT

- ✅ **IS:** Implementation of Brownfield Item 6's already-bound architectural choice (custom `expo-config-plugin`, NOT `expo-task-manager`). The decision-making is upstream; the dev agent ships the build.
- ✅ **IS:** A V1-launch-supportive deliverable. Without the FGS, J2 (steady-state weekly review with interruption) breaks on Android — the pipeline silently dies when the user backgrounds the app, even though MMKV checkpoints exist (the checkpoints only help on relaunch; mid-run survival is the FGS's job).
- ✅ **IS:** Cross-platform-ready in the architectural sense — iOS Phase 2 ships `BGTaskScheduler` per architecture line 881, and the JS wrapper's iOS-no-op guard means iOS prebuild + dev builds are unaffected.
- ❌ **IS NOT:** An iOS-implementation story. iOS gets a TODO + an early-return; no code, no test, no spike.
- ❌ **IS NOT:** Blocked by Story 1.1's binding-only cut. Architecture asserts "independent of spike; can land in parallel" (`epics-and-stories.md:786`). Even at rung-3 (V2-defer auto-slice), the FGS is still needed for manual-clip FFmpeg exports.
- ❌ **IS NOT:** A re-litigation of option (a) vs option (b). The architecture's `expo-task-manager` rejection (line 811: "FFmpeg/OpenCV JSI bindings cannot be shared across the headless context boundary") is authoritative.
- ❌ **IS NOT:** A "polish the notification UX" story. The notification's title ("Analyse en cours…") and channel importance (LOW) are bound by architecture. Future UX iteration (custom RemoteViews layout, animated progress bar, etc.) is V2 backlog.
- ❌ **IS NOT:** A push-notification story. No FCM, no APNS, no remote pushes. The notification is **local-only** — generated on-device by the FGS itself. Per [[architecture-no-push-notifications-V1]] and the architecture invariant "no_push_notifications_v1" (line 63).

### No legacy plugin to mimic (2026-05-14 audit)

The architecture's project-tree at `architecture.md:1440` lists `apps/mobile/plugins/with-ffmpeg.js` as "FFmpeg-kit Expo config plugin (legacy, retained)" — but **the file does not exist in the codebase as of 2026-05-14** (verified by `glob apps/mobile/plugins/*` returning only `.gitkeep`). The active FFmpeg integration is `@wokcito/ffmpeg-kit-react-native@^6.1.2` (per `apps/mobile/package.json:23`), which is autolinked and does NOT require an Expo config plugin.

**Implication for the dev agent:** there is no in-repo precedent to copy. Build the plugin from `@expo/config-plugins` scratch. The reference patterns are external — see "Reference materials" below.

### Architecture sources of truth

The dev agent should treat these as load-bearing reads and re-check any contract decisions against them:

- `_bmad-output/architecture.md:804-823` — **Brownfield Item 6 [RESOLVED]** — the binding decision, rationale, implementation outline. **This is the authoritative spec.**
- `_bmad-output/architecture.md:817-821` — exact file paths, AndroidManifest fragment, service lifecycle.
- `_bmad-output/architecture.md:1440-1441` — project-tree placement (`apps/mobile/plugins/`).
- `_bmad-output/architecture.md:1497-1508` — `video-processing/` directory shape; `processingPipeline.ts:1499` is the orchestrator that wires in start/stop.
- `_bmad-output/architecture.md:1693` — `apps/mobile/plugins/with-foreground-service.js — keeps pipeline alive in background (Decision: Brownfield Item 6)`.
- `_bmad-output/architecture.md:881` — iOS Phase 2 deferral via `BGTaskScheduler`.
- `_bmad-output/architecture.md:884` — V1 cross-platform-readiness assertion.
- `_bmad-output/epics-and-stories.md:768-788` — the story-spec source (Story 1.2's 7 ACs as originally written).
- `_bmad-output/prd.md:676` — FR-NFR-trace: "Background processing (Android Foreground Service) — required for export-during-background and auto-save through interruption (J2). Choice between `expo-config-plugin` vs `expo-task-manager` — architecture-owned; decision binds before Sprint 3 commits".

### Android 14/15 FGS API contract

**Why the granular permission matters:** Android 14 (API 34) introduced **mandatory granular permissions** for foreground services. Declaring only the legacy `FOREGROUND_SERVICE` permission is **insufficient** — the OS rejects the FGS start with a `SecurityException` if the granular permission matching the `foregroundServiceType` is not also declared. For `foregroundServiceType="dataSync"`, the matching granular permission is `FOREGROUND_SERVICE_DATA_SYNC`. Both are required in V1.

**FGS type choice — `dataSync` (architecture-bound):** the architecture (line 817) explicitly chose `dataSync`. Alternative considered-and-deferred is `mediaProcessing` (introduced in Android 14 for transcoding-style workloads that don't require user interaction; arguably more semantically correct for our auto-slice). **Per Story 1.0's "do not re-litigate architecture" precedent (Story 1.1 "What to NOT do"): ship `dataSync` as bound.** A future re-fingerprinting story may revisit if Android imposes `dataSync`-specific behavior caps that bite V1 (Android 15 caps `dataSync` to 6h/day; auto-slice runs are well under that — non-issue for V1).

**Android 14 `startForeground(id, notification, type)` overload:** the 3-arg version with `FOREGROUND_SERVICE_TYPE_DATA_SYNC` is **required** on API 34+. The 2-arg version still compiles but the OS may reject the call. Use SDK_INT guard (`Build.VERSION_CODES.UPSIDE_DOWN_CAKE` = 34) to fall back to 2-arg on older devices.

**Android 13+ runtime POST_NOTIFICATIONS request:** declared-in-manifest is necessary but NOT sufficient on API 33+. AC9 captures the runtime request via `PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS`. **If the user denies**: the FGS itself runs (the notification's invisibility is the only consequence) — do NOT block the pipeline.

**`stopWithTask="false"`:** the architecturally-relevant flag. The FGS keeps running when the user swipes the app away from Recents. Without this, swiping the launcher task kills the service → pipeline silently dies — the exact J2 failure we are guarding against.

### Kotlin service implementation sketch

For the dev agent's reference; the `withDangerousMod` template literal in `with-foreground-service.js` should produce something like:

```kotlin
package team.warden.mobile

import android.app.*
import android.content.*
import android.content.pm.ServiceInfo
import android.os.*
import androidx.core.app.NotificationCompat
import com.tencent.mmkv.MMKV

class WardenProcessingService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private var sessionId: String? = null
    private var mmkv: MMKV? = null

    private val tick = object : Runnable {
        override fun run() {
            updateNotification()
            handler.postDelayed(this, 1000)
        }
    }

    override fun onCreate() {
        super.onCreate()
        MMKV.initialize(this)
        mmkv = MMKV.mmkvWithID("warden-storage")
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        sessionId = intent?.getStringExtra("sessionId")
        val notification = buildNotification("Préparation…")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIF_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIF_ID, notification)
        }
        handler.post(tick)
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(tick)
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun updateNotification() {
        val sid = sessionId ?: return
        val stage = mmkv?.decodeString("processing.$sid.stage")
        val text = when (stage) {
            "keyframes" -> "Extraction des images-clés"
            "detection" -> "Analyse des images"
            "segmentation" -> "Segmentation des parties"
            "results" -> "Extraction des miniatures"
            else -> "Préparation…"
        }
        val n = buildNotification(text)
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIF_ID, n)
    }

    private fun buildNotification(text: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Analyse en cours…")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.stat_notify_sync)  // TODO: app icon
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID, "Traitement vidéo", NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Notifications affichées pendant l'analyse vidéo en arrière-plan."
            setShowBadge(false)
        }
        nm.createNotificationChannel(channel)
    }

    companion object {
        private const val NOTIF_ID = 1001
        private const val CHANNEL_ID = "processing"
    }
}
```

Verify import paths against the actual Android SDK + AndroidX versions resolved by `expo prebuild --platform android`; minor adjustments may be needed.

### Stage→French copy mapping (notification text)

| Pipeline stage | English JS label (`useVideoProcessing.STAGE_LABELS:17-22`) | French notification text |
|---|---|---|
| (no stage yet — pre-checkpoint) | n/a | Préparation… |
| `keyframes` | Extracting keyframes | Extraction des images-clés |
| `detection` | Analyzing frames | Analyse des images |
| `segmentation` | Segmenting maps | Segmentation des parties |
| `results` | Extracting result frames | Extraction des miniatures |

These strings should later flow into Epic 8 Story 8.1's french-i18n-bundle once that lands; the Kotlin file would then read from a `strings.xml` resource and the i18n contract would unify. **Story 1.2 hardcodes the strings** — it's a few lines of Kotlin, not 14 maps × 8 surfaces. Premature abstraction blocked per the [[feedback]] principle.

### Reference materials (external — not in-repo)

The dev agent should consult these at implementation time:

1. **Expo config plugins docs** — `https://docs.expo.dev/config-plugins/introduction/` (the `withAndroidManifest` + `withDangerousMod` + `withRunOnce` API surface). Verify the `@expo/config-plugins` package version exposed by `expo@~54.0.33` and use the docs matching that version.
2. **Android FGS migration guide (API 34)** — `https://developer.android.com/about/versions/14/changes/fgs-types-required` (granular permission names, type→permission mapping, behavior changes).
3. **Android 15 FGS caps** — `https://developer.android.com/about/versions/15/behavior-changes-15#data-sync-fgs` (6h/day cap on `dataSync`; non-issue for V1's auto-slice runs).
4. **react-native-mmkv Android API** — `https://github.com/mrousavy/react-native-mmkv/blob/v3.3.3/README.md` (verify the MMKV instance-ID convention matches `apps/mobile/src/shared/services/storage.ts:8`).
5. **Expo Modules API** — `https://docs.expo.dev/modules/overview/` (for the AC4 alternative path; recommended over legacy NativeModules in SDK 54).
6. **`@expo/config-plugins` source** — `https://github.com/expo/expo/tree/main/packages/%40expo/config-plugins/src/android` (the actual implementation of `withAndroidManifest` — useful when the docs are sparse on edge cases).

### J2 manual test interpretation

Per `_bmad-output/prd.md` Section 4 (J2 journey definition) + architecture line 781: J2 is "steady-state weekly review with interruption". The interruption is the user backgrounding the app mid-pipeline. The success criterion is:

- **Tier 1 (best — and what the FGS enables):** the process stays alive across the background; the pipeline continues; on resume, the user sees finished segments without waiting again. **AC8 verifies this** (Battery Optimization DISABLED).
- **Tier 2 (acceptable):** the process is killed by the OS (Doze / aggressive OEM management); on relaunch, the user sees a "Resuming…" indicator; the pipeline picks up from the last completed stage per `processingPipeline.ts:281-300` MMKV checkpoint logic. **AC7 verifies this** (Battery Optimization ENABLED).
- **Tier 3 (failure — what we're guarding against):** the process is killed; on relaunch, the pipeline starts over from scratch (no checkpoint) OR shows an error state. **This story prevents Tier 3** by adding the FGS to mitigate Tier-2-vs-Tier-1, AND by inheriting Story 7.5's existing MMKV checkpointing for the Tier-2 case.

**Note on Poco X5 Pro 5G + HyperOS:** Xiaomi/Poco's HyperOS is among the most aggressive Android skins re: background process management. Even with FGS, HyperOS may still kill the process under sufficient memory pressure. This is a known issue across Android OEMs (see `dontkillmyapp.com` for the ecosystem state). **For V1 we accept this graceful-degrade-to-Tier-2** — the MMKV checkpoint is the safety net. No code workaround attempted in this story.

### Existing perf instrumentation must survive untouched

Story 1.1's `__DEV__`-gated `[PERF-002]` / `[PERF-009]` log lines (processingPipeline.ts:249-265 + 311 + 355-367 + 484-499 + 502-517) + the MMKV `processing.<sid>.perf002` writes are the binding evidence for the AR-SPIKE rung verdict. **Do not remove, refactor, or "tidy" any of that code.** If the new `startForegroundService` / `stopForegroundService` calls need to live near those blocks, add them around (not inside). Diff `processingPipeline.ts` before/after at PR-open time and confirm byte-identical `__DEV__` blocks.

### MMKV key contract (read-side, Kotlin)

| Key | Producer | Consumer (this story) | Format |
|---|---|---|---|
| `processing.<sessionId>.stage` | `processingPipeline.ts:94 saveCheckpoint` | Kotlin `WardenProcessingService.updateNotification()` poll loop | string: one of `keyframes` / `detection` / `segmentation` / `results` |
| `processing.<sessionId>.perf002` | `processingPipeline.ts:491 storage.setObject` | (no read by this story — Story 1.1 + Story 1.1.1's diagnostic-only field) | JSON object |
| `processing.<sessionId>.events` | `processingPipeline.ts:342` | (no read by this story) | JSON array |

Only `.stage` is read by the FGS. The Kotlin side MUST NOT read any other key — adding side-effects to the FGS poll loop is premature and brittle.

### What to NOT do

- **Do NOT** swap the architecture's choice from option (a) to option (b) ("but `expo-task-manager` looks simpler"). The architectural rationale at `architecture.md:811` is explicit: "FFmpeg/OpenCV JSI bindings cannot be shared across the headless context boundary." Option (b) is rejected; the dev agent ships option (a).
- **Do NOT** add a 3rd-party "react-native-foreground-service"-style library. The architecture explicitly bound a **custom config plugin** — using a community wrapper is a different choice with different tradeoffs (transitive dep surface, abandonment risk, version lock-in to a non-Anthropic-controlled package). Ship the bespoke plugin.
- **Do NOT** create a `props` surface on the plugin (channel id, notification title, FGS type). All are architecturally-bound constants; premature configurability per the [[feedback]] "don't design for hypothetical future requirements" principle.
- **Do NOT** add iOS implementation. AC10 deferral is explicit; iOS gets a TODO + an early-return. iOS code in this story is anti-scope (architecture line 881).
- **Do NOT** commit `apps/mobile/android/` or `apps/mobile/ios/` regenerated dirs. The root `.gitignore` excludes them per Story 1.1 Task 1; do not undo that exclusion.
- **Do NOT** silently catch errors from `startForeground`. The 5-second window (Android requires `startForeground` within 5s of `startForegroundService`) is a hard contract; missing it crashes the OS with a `ForegroundServiceDidNotStartInTimeException`. Catch + log only — let the exception propagate to the OS so failures are visible, not hidden.
- **Do NOT** use `Service` (background service) without converting to FGS. Android 12+ disallows starting background services from app background; this is exactly the bug we're solving. FGS is the only correct shape.
- **Do NOT** use a `targetSdkVersion` downgrade workaround to escape the granular-permission requirement. Expo SDK 54 targets API 35 (Android 15); we don't fight the platform.
- **Do NOT** add Firebase Crashlytics or any cloud-side telemetry from the Kotlin service. The FGS is purely local. Telemetry is Epic 2's job, runs in JS, and uses the existing `analytics.ts` wrapper with payload allowlist per `architecture.md:1518`.
- **Do NOT** read MMKV keys other than `processing.<sessionId>.stage` from the FGS. Single-key contract; tight scope.
- **Do NOT** rewrite `processingPipeline.ts:280-520` for "cleanup" while adding the bridge calls. The Story 1.1 review found 8 patches + 4 defers in that block; any further unrelated edits is exactly the kind of incidental-refactor that earned the Story 1.1 disposition annotation. Minimal-diff principle.
- **Do NOT** retitle the PR after creation. AC12 binds the title verbatim.
- **Do NOT** wait for Story 1.1.1 (cancelled per [[project_warden_ar_spike_binding_only]]) — Story 1.2 was always architectured as parallel-with-spike. If substrate gaps block end-to-end J2 verification on the live pipeline, use the stub-test fallback documented in Task 8 sub-bullet.

### Project Structure Notes

- **Output locations** for this story:
  - `apps/mobile/plugins/with-foreground-service.js` — NEW: the Expo config plugin.
  - `apps/mobile/app.json` — UPDATE: append to `expo.plugins` array.
  - `apps/mobile/package.json` — UPDATE: add `@expo/config-plugins` as `devDependency` (per Task 1 sub-bullet 3 recommendation).
  - `apps/mobile/src/shared/services/foregroundService.ts` — NEW: JS wrapper for the native bridge (typed, iOS-guarded, POST_NOTIFICATIONS-requesting).
  - `apps/mobile/src/features/video-processing/processingPipeline.ts` — UPDATE: import + start-call + try/finally stop-call. Minimal diff per "What to NOT do".
  - `apps/mobile/src/features/video-processing/__tests__/processingPipeline.test.ts` — NEW: 4 test cases per Task 6 / AC6.
  - `pnpm-lock.yaml` — UPDATE (transitively for `@expo/config-plugins`).
  - `apps/mobile/android/` — REGENERATED by `expo prebuild`; NOT committed. The plugin's `withDangerousMod` writes `WardenProcessingService.kt` (+ optionally `WardenProcessingModule.kt` per Task 4 path choice) into the regenerated tree.
  - `_bmad-output/implementation-artifacts/1-2-foreground-service-android-config-plugin.md` — UPDATE: this file (Tasks/Subtasks checkboxes marked, Dev Agent Record / File List / Change Log populated, Status flipped `ready-for-dev → review` per Story 0.2 Lesson #7 single-diff collapse).
  - `_bmad-output/sprint-status.yaml` — UPDATE: `1-2-...` status flip per AC11.

- **No file modifications outside `apps/mobile/`** (plus the two `_bmad-output/` admin files). The plugin is mobile-scoped; web + tooling + contracts untouched.

- **Cross-platform readiness assertion** (architecture line 884): the plugin is Android-only by construction (`withAndroidManifest` is a no-op on iOS); the JS wrapper guards on `Platform.OS`. iOS Phase 2 will add a sibling plugin (`with-background-task.js` or similar) when iOS prebuild + FFmpeg-kit-iOS land. **This story creates no iOS-specific files.**

### References

- [Source: architecture.md:804-823] — Brownfield Item 6 [RESOLVED] (the binding spec).
- [Source: architecture.md:817-821] — exact file paths + AndroidManifest fragment + service lifecycle.
- [Source: architecture.md:881] — iOS Phase 2 `BGTaskScheduler` deferral.
- [Source: architecture.md:884] — V1 cross-platform-readiness assertion.
- [Source: architecture.md:1440-1441] — project-tree placement.
- [Source: architecture.md:1497-1508] — video-processing/ directory shape.
- [Source: architecture.md:1693] — FR cross-reference.
- [Source: epics-and-stories.md:768-788] — Story 1.2 source-of-truth ACs.
- [Source: prd.md:676] — J2 + FGS NFR trace.
- [Source: prd.md:1037] — REL-001: mobile session data survives crash/force-close/OS-killed/restart (the broader contract this story serves).
- [Source: processingPipeline.ts:245-521] — `runProcessingPipeline` orchestrator (the wire-up site).
- [Source: processingPipeline.ts:89-106] — MMKV checkpoint key convention (`processing.<sessionId>.<field>`).
- [Source: useVideoProcessing.ts:17-22] — STAGE_LABELS (the English JS counterpart of the French Kotlin notification copy).
- [Source: storage.ts:8] — MMKV instance ID `"warden-storage"` (Kotlin must match).
- [Source: app.json:5-9 + 18-26 + 30-32] — Expo config: `newArchEnabled: true`, Android package `team.warden.mobile`, plugins array.
- [Source: package.json:23] — `@wokcito/ffmpeg-kit-react-native@^6.1.2` (active FFmpeg integration; no config plugin currently needed for it).
- [Source: package.json:35-36] — `react-native-fast-opencv@0.4.8` + `react-native-mmkv@^3.3.3` (the two native modules whose JSI contexts must survive the backgrounding scenario).
- [Source: implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md] — Story 1.1 (precedent for the AC-checkbox-tighten convention, the "what to NOT do" pattern, the manual-test-as-regression pattern, the single-PR + post-merge-follow-up pattern).
- [Source: memory/feedback_two_pr_docs_execution.md] — Two-PR pattern (adapted from docs-only stories to this code story).
- [Source: memory/feedback_ac_checkbox_tighten.md] — AC checkbox tighten convention.
- [Source: memory/project_warden_ar_spike_binding_only.md] — AR-SPIKE binding-only cut; Story 1.1.1 cancellation; ship-and-observe stance.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Author    | Change                                                                                          |
|------------|-----------|-------------------------------------------------------------------------------------------------|
| 2026-05-14 | Stephane (bmad-create-story) | Story created via create-story skill; sprint-status flipped `backlog → ready-for-dev`. |
