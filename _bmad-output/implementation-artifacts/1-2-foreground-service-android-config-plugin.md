# Story 1.2: Foreground Service Android Config Plugin (BF-5)

Status: in-progress

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

1. [x] **AC1 — Expo config plugin file exists at the architecture-bound path with the architecture-bound behavior.** `apps/mobile/plugins/with-foreground-service.js` exists. It is a Node-resolvable `@expo/config-plugins`-style plugin (the function exported by default takes `(config, props?)` and returns the modified `ExpoConfig`). It MUST:
   - Add `<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>` to `AndroidManifest.xml` (Android 9+ baseline permission).
   - Add `<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>` to `AndroidManifest.xml` (Android 14+ mandatory granular permission matching the FGS type — see Dev Note "Android 14/15 FGS API contract").
   - Add `<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>` to `AndroidManifest.xml` (Android 13+ runtime permission for displaying the sticky notification; without it the notification silently doesn't appear on 13+ devices — the FGS still runs but is invisible to the user).
   - Add a `<service>` element inside `<application>` declaring `android:name=".WardenProcessingService"`, `android:foregroundServiceType="dataSync"`, `android:exported="false"`, `android:stopWithTask="false"` (the FGS keeps running even after the launcher task is swiped away — exactly the J2 backgrounding case).
   - Use `withAndroidManifest` (from `@expo/config-plugins`) for the manifest edits — NOT a `withDangerousMod` raw-file rewrite. Idempotency: re-running `expo prebuild --clean` must produce identical output (no duplicate permission entries, no duplicate `<service>` blocks).
   - Use `withDangerousMod` for the Kotlin source-file emission ONLY — there is no `@expo/config-plugins` helper for generating arbitrary Kotlin files. Write to `android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt` per architecture line 818. Idempotent — re-run overwrites the file rather than appending or duplicating.

2. [x] **AC2 — Plugin registered in `app.json` and `expo prebuild` runs clean.** `apps/mobile/app.json` `expo.plugins` array contains `"./plugins/with-foreground-service"` (relative path; Expo resolves `.js` automatically). After registration: `pnpm --filter mobile exec expo prebuild --platform android --clean` succeeds with no warnings related to the new plugin or duplicate-permission errors. The regenerated `apps/mobile/android/app/src/main/AndroidManifest.xml` contains the 3 `<uses-permission>` lines (AC1) and the `<service>` declaration. The regenerated `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt` exists with the AC4 implementation. **Verification commands** to paste into the implementation record:
   - `grep -c FOREGROUND_SERVICE apps/mobile/android/app/src/main/AndroidManifest.xml` returns at least 2 (the two FGS permission lines).
   - `grep -c WardenProcessingService apps/mobile/android/app/src/main/AndroidManifest.xml` returns at least 1 (the `<service>` declaration).
   - `test -f apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt && echo OK`.

3. [x] **AC3 — Android service class implemented.** _(Mechanism adapted, user-approved 2026-06-11: stage PUSHED from JS via the `updateStage` bridge instead of polled from `com.tencent.mmkv.MMKV`, which react-native-mmkv@3.3.3 does not expose. **Code-review deviation #2, user-approved 2026-06-11: `START_NOT_STICKY` instead of START_STICKY** — a sticky restart resurrects the service with a dead JS context (permanent orphan notification); recovery after an OS kill is the checkpoint-resume path on relaunch, plus `App.tsx` launch reconciliation. Code review also added: `onTimeout` override (Android 15 dataSync cap → graceful self-stop), FIFO `action="stop"` stop-delivery, and defensive `Log.w` warnings. All other contract points implemented as written — see Dev Agent Record → Completion Notes + Review Findings.)_ `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt` is generated by the plugin and contains a Kotlin class `WardenProcessingService` extending `android.app.Service` with the following contract:
   - `onStartCommand(intent, flags, startId)` calls `startForeground(notificationId, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)` within 5 seconds (Android 14+ requirement — see Dev Note "Android 14/15 FGS API contract"). Returns `START_STICKY` so the OS attempts to restart the service if the process is killed under memory pressure.
   - `onCreate()` creates the notification channel `processing` if it does not exist: `IMPORTANCE_LOW` (non-disruptive — no sound, no vibration, no heads-up), name "Traitement vidéo" (French; the user-facing app is French per the legacy distillate), description "Notifications affichées pendant l'analyse vidéo en arrière-plan."
   - The sticky notification displays title "Analyse en cours…" (verbatim per architecture line 818), text "Préparation…" as the initial fallback when the MMKV key has no value, and dynamic text rebuilt by reading `processing.<sessionId>.stage` from MMKV via a 1-second handler loop (`Handler(Looper.getMainLooper()).postDelayed(...)`). The stage values are `keyframes` / `detection` / `segmentation` / `results` per `processingPipeline.ts:113-118`; the Kotlin side maps them to French strings (see Dev Note "Stage→French copy mapping").
   - `onDestroy()` cancels the polling Handler, removes the notification (`stopForeground(STOP_FOREGROUND_REMOVE)`), and releases the MMKV reader instance (best-effort).
   - Intent extras: `sessionId: String` (passed by the JS bridge so the service knows which MMKV key to poll). If the extra is missing, the service logs a warning and shows "Préparation…" indefinitely (defensive — the JS bridge MUST pass it, but a missing extra is not a crash).
   - The class is registered in the same package as the app (`team.warden.mobile` per `app.json` `android.package`).
   - Reads MMKV via `com.tencent.mmkv.MMKV` direct Kotlin API (the same native module that powers JS-side `react-native-mmkv@3.3.3`; the underlying library is `tencent/MMKV`). The MMKV instance ID must match the JS side: `MMKV.mmkvWithID("warden-storage")` — see `apps/mobile/src/shared/services/storage.ts:8` (`new MMKV({ id: "warden-storage" })`).
   - **Do NOT** instantiate Firebase / FFmpeg / OpenCV from Kotlin — the service's sole jobs are (a) keep the process alive (b) display the notification (c) poll MMKV. The actual pipeline work runs in the JS context via the existing `processingPipeline.ts` orchestrator.

4. [x] **AC4 — JS bridge module exposing `start(sessionId)` / `stop()` to JS.** _(Legacy RN Native Modules path chosen; a 3rd method `updateStage(stage)` added for the JS→Kotlin stage push — see Completion Notes. The MainApplication.kt registration uses the purpose-built `withMainApplication` modifier rather than AC4's literal `withDangerousMod` — same effect, safer mechanism. Code review 2026-06-11: the JS wrapper gained an owner-token — `stopForegroundService(sessionId)` from a stale owner no-ops — plus `reconcileForegroundServiceAtLaunch()`.)_ A small native bridge enables JS-to-Kotlin start/stop calls. Implementation choices (the architecture says "JSI bridge module"; the dev agent picks the lighter-weight option that satisfies the contract):
   - **Recommended path: legacy React Native Native Modules API** (TurboModules / new-arch compatible; `newArchEnabled: true` in `app.json:9`). Kotlin class `WardenProcessingModule` extends `ReactContextBaseJavaModule`; exposes two `@ReactMethod`-annotated methods `start(sessionId: String, promise: Promise)` and `stop(promise: Promise)`; registered via a `ReactPackage` listed in `MainApplication.kt` (which is itself prebuild-generated — the config plugin MUST also append the `add(WardenProcessingPackage())` line to `MainApplication.kt`'s `getPackages()` via `withDangerousMod`).
   - **Alternative path (acceptable if simpler in practice): Expo Modules API** (`expo-modules-core`). Same start/stop surface; auto-registered via `expo.modules.json` or a `kotlin Module()` definition; no `MainApplication.kt` mod required. **Note:** as of Expo SDK 54 the Expo Modules API is the recommended path for new native modules — pick this if the dev agent finds the `MainApplication.kt` patching messy.
   - JS-side wrapper file `apps/mobile/src/shared/services/foregroundService.ts` exposes a typed API: `export async function startForegroundService(sessionId: string): Promise<void>` + `export async function stopForegroundService(): Promise<void>`. **iOS guard:** both functions early-return on iOS (`if (Platform.OS !== 'android') return;`) — iOS Phase 2 ships `BGTaskScheduler` instead per architecture line 881.
   - The bridge module's Kotlin file lives at `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingModule.kt` (or wherever Expo Modules autolinking expects it for the alternative path) — generated by the plugin via `withDangerousMod` per AC1.

5. [x] **AC5 — `processingPipeline.ts` wired to start/stop the service.** _(start inside the try as the first statement + finally-stop on the existing try/catch; `__DEV__`/PERF blocks byte-identical per `git diff`.)_ `apps/mobile/src/features/video-processing/processingPipeline.ts` imports `startForegroundService` + `stopForegroundService` from `../../shared/services/foregroundService` and:
   - Calls `await startForegroundService(sessionId)` immediately after `updateSessionStatus(sessionId, "processing")` (line 274) and BEFORE the checkpoint-gated stage execution (line 280).
   - Calls `await stopForegroundService()` in a `finally` block that wraps the existing `try/catch` (currently lines 280-520). The `finally` block ensures the service stops on success, on error, AND on any future code path that may exit early. **Critical: never leak the service** (architecture line 821) — `finally` is the only correct construct here.
   - The bridge calls MUST NOT throw if the native module is unavailable (e.g., in jest) — the JS wrapper at `foregroundService.ts` swallows `Error: native module WardenProcessing not found` and logs a `__DEV__`-gated warning. This preserves the existing test surface in `apps/mobile/src/features/video-processing/__tests__/*.test.ts` which does NOT load the native module.
   - **Idempotency at the JS side:** if `startForegroundService` is called twice in a row (e.g., the user retries a failed pipeline before the previous service has fully shut down), the Kotlin `onStartCommand` re-enters with the new `sessionId`; the Handler loop simply switches to the new MMKV key. No leak.
   - **Existing perf instrumentation preserved:** the `__perfStart` / `__perfMark` / `__perfStages` / `[PERF-002]` / `[PERF-009]` logging added by Story 1.1 stays untouched. The new bridge calls are added around (not inside) that instrumentation. **Verify** by diffing `processingPipeline.ts` after the change: the `__DEV__`-gated blocks at lines 249-265 and 484-499 + 502-517 are byte-identical post-edit.

6. [x] **AC6 — `processingPipeline.test.ts` and sibling tests still pass.** _(14 suites / 109 tests green; +4 new, no regressions.)_ `apps/mobile/src/features/video-processing/__tests__/` jest suite is green after the wire-up. The bridge module is mocked via `jest.mock('../../shared/services/foregroundService', () => ({ startForegroundService: jest.fn().mockResolvedValue(undefined), stopForegroundService: jest.fn().mockResolvedValue(undefined) }))` at the top of any new test file that needs it. **No regression:** every pre-existing test in this directory passes without modification (the mock at the JS wrapper layer means existing tests don't see the native bridge at all).
   - **New test file `apps/mobile/src/features/video-processing/__tests__/processingPipeline.test.ts`** (this file does NOT currently exist — confirmed by glob): scaffold it with the start/stop bridge-call contract. **Minimum 4 test cases:** (1) start is called once on entry with the correct sessionId; (2) stop is called on successful completion; (3) stop is called when an inner stage throws (verify via a forced throw in `extractKeyframes` mock); (4) stop is called even when start itself throws — defensive double-finally. The test wires synthetic `FrameLoader` + `detectionConfig` per the existing pattern in `apps/mobile/src/features/video-processing/__tests__/blackScreenDetector.test.ts:1-30` (verify the canonical mock shape there).
   - Full mobile jest suite `pnpm --filter mobile test` is green at story close.

7. [ ] **AC7 — Manual J2 test on Android dev build passes with Battery Optimization ENABLED.** Manual end-to-end procedure (record raw outcome in the implementation record's "Manual J2 verification" section):
   - **Setup:** Connect the Poco X5 Pro 5G (`dc72b871` per Story 1.1) via ADB. Battery optimization for Warden: `adb shell dumpsys deviceidle whitelist` — confirm `team.warden.mobile` is NOT on the whitelist (default; Battery Optimization is ENABLED). `pnpm --filter mobile exec expo run:android --device dc72b871` to install the dev build.
   - **Procedure:** Sign in with a paid test account. Import the 1h49 EVA After-h reference video staged at `/sdcard/Download/2026-01-18 12-10-30.mp4` (per Story 1.1 Task 3). Auto-slice begins → sticky notification appears with title "Analyse en cours…" and text matching the current stage. Press HOME button to background the app (Battery Optimization should NOT immediately kill the process because the FGS is running). Wait 60 seconds. Reopen the app via the launcher. **Expected:** the pipeline is still running (not in `error` state); the notification is still visible; the progress indicator on `ProcessingScreen` continues from where it was; the pipeline eventually completes successfully with `session.status === 'ready'`. **Or** the OS killed the JS context anyway (Doze / aggressive OEM management) — in which case the relaunch path reads the MMKV checkpoint and resumes from the last completed stage per `processingPipeline.ts:281-300`. **Either outcome is acceptable for J2** — the regression we are guarding against is "pipeline silently abandoned + no resume", not "process never killed under any circumstances".
   - **Record raw observations:** time-of-background; was-process-still-alive-on-resume (verify via `adb shell ps -A | grep team.warden.mobile`); did-checkpoint-resume-fire (verify via logcat `[processingPipeline]` traces or by inspecting MMKV `processing.<sid>.stage` post-resume); final session status; total wall-clock to completion.

8. [ ] **AC8 — Manual J2 test on Android dev build passes with Battery Optimization DISABLED.** Same procedure as AC7 with one change: add `team.warden.mobile` to the doze whitelist before running (`adb shell dumpsys deviceidle whitelist +team.warden.mobile`). **Expected:** the process stays alive across HOME-press indefinitely; auto-slice runs to completion without any OS interference; notification visible throughout. This is the upper-bound case (best for the user; closest to "desktop background process" semantics). **Record raw observations** per AC7 in the implementation record.

9. [x] **AC9 — POST_NOTIFICATIONS runtime permission request wired.** _(Path (b): `ensureNotificationPermission()` in `foregroundService.ts`, fired just-in-time inside `startForegroundService` on Android 13+; denial logged, pipeline never blocked. Code review 2026-06-11: the request is now fire-and-forget — `native.start()` no longer awaits the dialog, so an unanswered prompt can't stall the pipeline. Runtime grant prompt to be observed during the manual J2.)_ On Android 13+, the `POST_NOTIFICATIONS` permission must be requested at runtime — declaring it in `AndroidManifest.xml` (AC1) is necessary but not sufficient. The dev agent adds a runtime permission request that fires:
   - Either (a) at app first-launch right before the import flow can be initiated (the natural moment — the user is about to start a pipeline that will use the notification);
   - Or (b) the first time `startForegroundService` is called in JS, just-in-time before the bridge actually starts the service.
   - Either path uses `PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS)` from `react-native`'s built-in `PermissionsAndroid` API — **no new dep**.
   - If the user denies the permission: the service still runs (the FGS itself does not require POST_NOTIFICATIONS — only the notification's visibility does), but the notification is invisible. Log a `__DEV__`-gated warning; **do not block the pipeline**. The user can re-grant via Android Settings → Notifications.
   - Implementation lives in `foregroundService.ts` (path b) or in `useVideoImport.ts` / `videoImportService.ts` (path a) — dev's choice. **Path (b) is preferred** because it co-locates with the service and survives if future code paths bypass video import.

10. [ ] **AC10 — Cross-platform readiness asserted; iOS Phase 2 path documented.** _Held `[ ]`: code-side done — plugin uses only Android-scoped modifiers (iOS-inert), `foregroundService.ts` early-returns on iOS, and the `// iOS Phase 2: BGTaskScheduler …` TODO is present. The literal `expo prebuild --platform ios` success check is UNVERIFIABLE on this Windows host (Expo skips iOS gen off macOS/Linux); re-verify on macOS/Linux/CI._ Per architecture line 884, V1 architecture asserts all mobile decisions are **cross-platform-ready**. This story does NOT ship iOS code — but it MUST NOT break iOS prebuild. Specifically:
    - The plugin's `withAndroidManifest` and `withDangerousMod` calls are Android-only; they MUST be guarded so they no-op on iOS (the `@expo/config-plugins` modifiers run regardless of platform — wrap any iOS-relevant logic in `if (config.modPlatform === 'android')` or rely on the modifier being Android-scoped, which `withAndroidManifest` already is).
    - `pnpm --filter mobile exec expo prebuild --platform ios` MUST succeed without errors mentioning the new plugin. **Note:** iOS prebuild may fail for OTHER reasons (FFmpeg-kit iOS fork, Firebase native modules, etc. — see architecture line 873-883); this AC only binds "no NEW iOS-prebuild errors are caused by `with-foreground-service.js`". Document any pre-existing iOS-prebuild errors separately if they surface.
    - JS wrapper `foregroundService.ts` MUST early-return on iOS (per AC4) — `Platform.OS !== 'android'` is the guard.
    - A `// iOS Phase 2: BGTaskScheduler + state checkpointing (architecture.md:881)` TODO comment lives in `foregroundService.ts` documenting the iOS deferral. **No iOS implementation in this story.**

11. [ ] **AC11 — Sprint-status flip on completion.** _Held `[ ]` per AC checkbox tighten — the `review → done` portion is post-merge admin._ `_bmad-output/sprint-status.yaml` `development_status[1-2-foreground-service-android-config-plugin]` flips `backlog → ready-for-dev → in-progress → review → done` across the work; `last_updated` bumps to current ISO date at each flip. `epic-1` is already `in-progress` (verified at story creation 2026-05-14); no epic flip. Flips to `[x]` once `done` lands on `main`.

12. [ ] **AC12 — Single-PR delivery; tiny post-merge follow-up per Two-PR pattern.** _Held `[ ]` per the [[feedback_two_pr_docs_execution]] convention adapted for code stories._ All deliverable file modifications ship in **one PR** titled exactly `feat: foreground service Android config plugin (Story 1.2)`. PR body links to: this story file; architecture line 804-823 (`#### Brownfield Item 6`); epics-and-stories line 768-788 (`### Story 1.2`). Branch name: `foreground-service-android-config-plugin`. A tiny post-merge follow-up commit/PR carries the `review → done` flip + this AC + AC11. Flips to `[x]` once the main PR is open with the verbatim title; the post-merge flip is owned by the follow-up PR.

## Tasks / Subtasks

> **Workflow shape:** This is a brownfield-implementation story. The architectural choice (option a vs option b) is already bound; the dev agent's job is faithful execution. The AC checkbox-tighten convention (Story 1.1 precedent) applies to ACs whose endpoint depends on post-merge actions.

- [x] **Task 1: Audit current state — plugins/, app.json, package.json (AC: 1, 2)**
  - [x] Confirm `apps/mobile/plugins/` exists with only `.gitkeep` — **the architecture's `with-ffmpeg.js` mention at `architecture.md:1440` is plan-side, NOT a real file** (verified at story-creation glob 2026-05-14). The dev agent has NO in-repo plugin precedent to copy from; build from `@expo/config-plugins` scratch. (See Dev Note "No legacy plugin to mimic".) — _Confirmed: only `.gitkeep` present._
  - [x] Confirm `apps/mobile/app.json:30-32` `expo.plugins` array currently contains only `"@react-native-google-signin/google-signin"`. The new entry will be appended. — _Actual: array already held `@react-native-google-signin/google-signin`, `@react-native-firebase/app`, `@react-native-firebase/auth` (Story 1.4). Appended the new entry as the 4th._
  - [x] Confirm `apps/mobile/package.json` does NOT yet declare `@expo/config-plugins` as a direct dep. It is transitively available via `expo@~54.0.33` (the Expo SDK re-exports `@expo/config-plugins`). **Decision for the dev agent:** add `@expo/config-plugins` as a `devDependency` for explicit version pinning + clean type imports, OR import it from `expo/config-plugins` (the re-export path). **Recommendation:** explicit `devDependency` to avoid the re-export indirection breaking under a future Expo SDK bump. — _Chose explicit `devDependency` pinned to `~54.0.4` (the resolved transitive version)._

- [x] **Task 2: Implement `apps/mobile/plugins/with-foreground-service.js` (AC: 1)**
  - [x] Create the file. Use plain CommonJS `module.exports = withForegroundService;` (matches the Expo plugin convention; no `.ts` — config plugins run at Metro pre-bundle time, not in the RN runtime).
  - [x] Compose two modifiers via `withPlugins(config, [withManifestMod, withKotlinFileMod])` from `@expo/config-plugins`. **Idempotency principle:** every modifier reads the existing state, checks if the target entry already exists, and adds it only if absent. — _Composed 3 modifiers (manifest, Kotlin files, MainApplication registration) under `withPlugins`, guarded by `withRunOnce`._
  - [x] **`withManifestMod`** uses `withAndroidManifest(config, async (config) => {...})`. Inside:
    - Get the `<manifest>` root via `config.modResults.manifest`.
    - For each of the 3 permissions (`FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`, `POST_NOTIFICATIONS`): if `manifest['uses-permission']?.some(p => p.$['android:name'] === '<perm>')` is false, push `{ $: { 'android:name': '<perm>' } }`.
    - For the `<service>` element: locate the `<application>` array (`manifest.application[0]`); ensure `application.service` is an array; if no entry with `$['android:name'] === '.WardenProcessingService'` exists, push `{ $: { 'android:name': '.WardenProcessingService', 'android:foregroundServiceType': 'dataSync', 'android:exported': 'false', 'android:stopWithTask': 'false' } }`. — _Used `AndroidConfig.Manifest.getMainApplicationOrThrow` to locate `<application>`._
    - Return `config`.
  - [x] **`withKotlinFileMod`** uses `withDangerousMod(config, ['android', async (config) => {...}])`. Inside:
    - Resolve the target path: `path.join(config.modRequest.platformProjectRoot, 'app', 'src', 'main', 'java', 'team', 'warden', 'mobile', 'WardenProcessingService.kt')`.
    - Ensure parent directories exist via `fs.mkdirSync(path.dirname(targetPath), { recursive: true })`.
    - Write the Kotlin source per AC3 contract (embed the Kotlin code as a template-literal constant at the top of the plugin file — keep the Kotlin readable; do NOT base64-encode or otherwise obscure it). — _Emits 3 Kotlin files: Service + Module + Package._
    - Overwrite-on-prebuild (do NOT append). Idempotent.
    - Return `config`.
  - [x] **Optional but recommended:** add `withRunOnce` from `@expo/config-plugins` to guard against double-application if the plugin is accidentally registered twice in `app.json`. — _Added._
  - [x] **No props.** The plugin takes no configuration object — service name, package name, FGS type, notification channel, and notification copy are all architecturally-bound constants. **Do not** add a `props` surface for "future flexibility"; per Story 1.1 "do NOT" pattern, premature configurability is anti-pattern. — _No props surface._

- [x] **Task 3: Implement the Kotlin service `WardenProcessingService.kt` (AC: 3)** — _⚠️ STAGE-SOURCE MECHANISM ADAPTED (user-approved 2026-06-11): see Completion Notes. react-native-mmkv@3.3.3 ships NO `com.tencent.mmkv.MMKV` Kotlin API, so the stage is PUSHED from JS via the bridge instead of polled from MMKV. All other AC3 contract points (title, channel, French stage text, lifecycle, typed-FGS overload, defensive null-stage) implemented as written._
  - [x] Inside the `withKotlinFileMod` template literal, write the Kotlin class per AC3 contract. Reference Dev Note "Kotlin service implementation sketch" for the full skeleton.
  - [x] ~~**MMKV integration from Kotlin**~~ **SUPERSEDED** — react-native-mmkv@3.3.3 builds only the MMKV C++ Core (namespace `com.mrousavy.mmkv`; CMake `add_subdirectory(../MMKV/Core core)`) and exposes **no** `com.tencent.mmkv.MMKV` Java/Kotlin class (verified: zero `tencent` refs in its android sources). That was a react-native-mmkv **v2** API; v3 dropped it. Per user decision, the stage is delivered by a JS→Kotlin push (`updateStage(stage)` bridge method → `startForegroundService` re-delivers `onStartCommand` with a fresh `stage` extra). The service reads `intent.getStringExtra("stage")` — no MMKV dependency.
  - [x] **Stage→French copy mapping** (see Dev Note for the full table): `null/undefined → "Préparation…"`, `keyframes → "Extraction des images-clés"`, `detection → "Analyse des images"`, `segmentation → "Segmentation des parties"`, `results → "Extraction des miniatures"`. — _Implemented in `stageToText()` Kotlin `when`._
  - [x] Notification channel creation MUST be guarded by `if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)` (Android 8.0+; Expo SDK 54 minSdk is 24 — old devices skip the channel creation but the notification still appears). — _Guarded; `ensureChannel()` early-returns below API 26._
  - [x] `startForeground(notificationId, notification, FOREGROUND_SERVICE_TYPE_DATA_SYNC)` — pass the typed-FGS-int as the third argument (Android 14+ overload). For older Android, fall back to the 2-arg overload via `if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) { startForeground(id, n, type) } else { startForeground(id, n) }`. — _Implemented with the SDK_INT guard._

- [x] **Task 4: Implement JS bridge — Kotlin module + JS wrapper (AC: 4)**
  - [x] **Decision point:** pick legacy Native Modules API OR Expo Modules API. Document the choice in the implementation record's "Notes / decisions" section. — _Chose **legacy RN Native Modules API** (ReactPackage + `withMainApplication`). Rationale: a Kotlin file emitted into the prebuild-generated app source tree is NOT discovered by `expo-modules-autolinking` (which only scans `node_modules` packages carrying `expo-module.config.json`), so the "Expo Modules auto-register" path does not actually work for an app-embedded file. The legacy `ReactPackage` registered via `withMainApplication` is the reliable contract and works under bridgeless/new-arch via RN's interop layer. See Completion Notes._
  - [x] ~~**If Expo Modules API**~~ — not chosen (see above).
  - [x] **Legacy Native Modules API:** `WardenProcessingModule.kt` extends `ReactContextBaseJavaModule`; `@ReactMethod start(sessionId, promise)` / `updateStage(stage, promise)` / `stop(promise)`. `WardenProcessingPackage.kt` returns the module. The plugin's `withMainApplication` mod inserts `add(WardenProcessingPackage())` inside the SDK-54 `PackageList(this).packages.apply { … }` block (anchored on the `// add(MyReactNativePackage())` autolink marker; idempotent). — _Note: a 3rd bridge method `updateStage` was added vs the AC4-listed start/stop because the stage is now pushed from JS (see Task 3 deviation)._
  - [x] Write `apps/mobile/src/shared/services/foregroundService.ts` per AC4 + AC9 + AC10:
    - Import the native module via `NativeModules.WardenProcessing` (legacy).
    - Export `async startForegroundService(sessionId: string): Promise<void>` — iOS guard, POST_NOTIFICATIONS request, native-module-missing swallow.
    - Export `async updateForegroundServiceStage(stage: string): Promise<void>` — iOS guard, best-effort (never throws), native-module-missing swallow.
    - Export `async stopForegroundService(): Promise<void>` — iOS guard, native-module-missing swallow.
    - Inline the iOS Phase 2 TODO comment per AC10.

- [x] **Task 5: Wire `processingPipeline.ts` (AC: 5, 6)**
  - [x] Add imports: `import { startForegroundService, stopForegroundService, updateForegroundServiceStage } from "../../shared/services/foregroundService";`
  - [x] In `runProcessingPipeline`: add `await startForegroundService(sessionId);` as the **first statement inside the existing `try`** (not before it). **Placement rationale:** AC5 requires a native start failure to propagate to the existing catch (session → `"error"`) AND Test 4 requires `stop` to still fire when start throws. Both hold only if start is inside the finally-protected region. Adding a `finally` to the existing try/catch (rather than re-indenting the whole block under a new outer try) keeps the `__DEV__` perf blocks **byte-identical** (AC5). Task 5's literal "before line 280" wording is inconsistent with its own AC5 semantics; AC5 governs. No `try/catch` wraps the start call.
  - [x] Append `} finally { await stopForegroundService(); }` to the existing try/catch. Verified the original `try { stages } catch { setError; throw }` is untouched and the `finally` runs after the catch re-throws (covers success, error, and start-throws paths). — _`git diff` confirms the `__DEV__`/`[PERF-002]`/`[PERF-009]` blocks are byte-identical._
  - [x] Also added a single-point stage-push hook in `reportProgress` (`void updateForegroundServiceStage(stage)` on stage change) — fire-and-forget, never blocks/fails the pipeline.
  - [x] Run `pnpm --filter mobile typecheck` / `pnpm --filter mobile test`. — _Tests green (109/109). Typecheck: my files clean; one **pre-existing** error in unmodified `firebaseConfig.ts` (`getReactNativePersistence` removed in firebase v12 — Story 1.5 scope), not introduced here._

- [x] **Task 6: Author new test file `apps/mobile/src/features/video-processing/__tests__/processingPipeline.test.ts` (AC: 6)**
  - [x] Use `jest.mock('../../../shared/services/foregroundService', ...)` at the top. Mock start + stop + updateStage as resolved-undefined Promise spies.
  - [x] Mock the OTHER deps the pipeline pulls in: ffmpeg, opencv, sessionRepository, segmentRepository, storage, detectionConfigService — plus gameDetector/mapIdentifier/blackScreenDetector/segmentation for full isolation. Followed the canonical mock-shape from `blackScreenDetector.test.ts`.
  - [x] Test 1: "starts FGS on entry with sessionId" — asserts `startForegroundService` called once with `'test-session-1'`.
  - [x] Test 2: "stops FGS on successful completion" — asserts `stopForegroundService` called once + status `'ready'` + `updateForegroundServiceStage('keyframes')` pushed.
  - [x] Test 3: "stops FGS when a stage throws" — `extractKeyframes` rejects; asserts `stopForegroundService` called once + status `'error'`.
  - [x] Test 4: "stops FGS when start itself throws" — `startForegroundService` rejects; asserts `stopForegroundService` STILL called (validates the finally-protected shape).
  - [x] Run `pnpm --filter mobile test`; capture the green count. — _**109/109 green** (14 suites), matching the expected 105 → 109._

- [x] **Task 7: Register the plugin + prebuild + verify (AC: 2, 10)**
  - [x] Edit `apps/mobile/app.json` to append `"./plugins/with-foreground-service"` to the `expo.plugins` array (4th entry, after the firebase plugins). — _Ordering verified fine; prebuild produced no duplicate-permission conflicts._
  - [x] Run `pnpm exec expo prebuild --platform android --clean`. — _Succeeded. Only pre-existing `userInterfaceStyle`/expo-system-ui note (unrelated to this plugin); no plugin-related or duplicate-permission warnings._
  - [x] Verify the 3 grep checks per AC2 sub-bullets + the Kotlin file exists. — _`grep -c FOREGROUND_SERVICE` = **2**; `grep -c WardenProcessingService` = **1**; `WardenProcessingService.kt` exists (+ Module + Package); `MainApplication.kt` patched with `add(WardenProcessingPackage())`._
  - [~] Run `expo prebuild --platform ios` — **BLOCKED ON THIS HOST:** Expo refuses to generate iOS project files off macOS/Linux (`Skipping generating the iOS native project files. Run npx expo prebuild again from macOS or Linux`). The plugin is iOS-inert by construction (only `withAndroidManifest` / `withDangerousMod('android')` / `withMainApplication` modifiers, all Android-scoped) and the JS wrapper early-returns on iOS, so no NEW iOS-prebuild error is possible from it — but the literal "ios prebuild succeeds" assertion (AC10) must be re-verified on macOS/Linux/CI. **AC10 held `[ ]`.**
  - [x] **Did NOT commit the regenerated `apps/mobile/android/` or `apps/mobile/ios/` directories** — confirmed both are git-ignored (Story 1.1). Only the plugin SOURCE (`.js` + Kotlin template strings) ships.

- [~] **Task 8: Manual J2 verification on Poco X5 Pro 5G (AC: 7, 8)** — _Build/install done by the agent; the human-in-the-loop background-and-resume observation is handed off to Stephane (see "Manual J2 verification" section below). AC7/AC8 held `[ ]`._
  - [x] Build the dev APK + verify install/launch. — _`:app:assembleDebug` → BUILD SUCCESSFUL (445 MB `app-debug.apk`); `adb install -r` Success; `am start` → process alive, no native crash (only the expected debug "Unable to load script" without Metro). APK path: `apps/mobile/android/app/build/outputs/apk/debug/app-debug.apk`._
  - [ ] **AC7 procedure (Battery Optimization ENABLED):** _PENDING — requires Stephane: `expo start` (Metro) or a release build, sign in with a paid account, run auto-slice, press HOME, wait 60s, reopen; record observations._
  - [ ] **AC8 procedure (Battery Optimization DISABLED):** _PENDING — same, with `adb shell dumpsys deviceidle whitelist +team.warden.mobile`._
  - [ ] **Substrate-gap stub-test fallback** still applies if gap #6 blocks the live pipeline (instrument a temporary `HomeScreen` debug button: `startForegroundService('test-sid')` → `sleep(60s)` → `stopForegroundService()`; observe the sticky notification appears, survives HOME-press, and clears on stop). _PENDING Stephane._

- [~] **Task 9: Commit, push, open PR (AC: 11, 12)** — _Commit leg done 2026-06-11 on Stephane's "commit it" (post-code-review); push/PR legs still held to Epic-1-end._
  - [x] `git checkout -b foreground-service-android-config-plugin` (off `main`). — _Done 2026-06-11, branched after the 1.3 follow-up commit (`694e795`); the 1.3 doc flip was committed separately first to keep the shared-doc boundary clean._
  - [x] Commit shape recommendation: **single commit** `feat: foreground service Android config plugin (Story 1.2)`. Subject lower-case verb-first per `@commitlint/config-conventional`. Body: brief summary of file changes; reference to architecture.md:804-823. — _Done: single commit (code + tests + App.tsx + app.json/package.json/lockfile + story md + deferred-work 1.2 sections + sprint-status 1.2 line), --no-ff merged to main per the 1.1/1.4 local-merge precedent._
  - [~] Flip `_bmad-output/sprint-status.yaml` `1-2-...: ready-for-dev → review` (one commit per Story 0.2 Lesson #7 — collapse intermediate `in-progress` into the single review-time diff). — _DEVIATION: flipped to `in-progress`, not `review` — the code review already ran (this session, pre-commit) and the remaining gates are the AC7/AC8/AC10 manual pass, not another review. `review → done` semantics ride with the Epic-1-end pass._
  - [ ] `git push -u origin foreground-service-android-config-plugin`. Capture the PR-create URL (no `gh` CLI on Stephane's host — manual PR open via the URL, per Story 0.2 lesson + Story 1.1 Task 12 sub-bullet). — _HELD to Epic-1-end (commit-only per Stephane's instruction)._
  - [ ] Open the PR with **exact** title `feat: foreground service Android config plugin (Story 1.2)` per AC12. Body links per AC12. — _HELD to Epic-1-end._
  - [ ] **Hold the post-merge follow-up** (the `done` flip + AC11/AC12 to `[x]` + any retrospective AC closures) for a tiny separate PR per the [[feedback_two_pr_docs_execution]] convention applied to code stories; ships with the Epic-1-end pass.

### Review Findings

> /bmad-code-review (2026-06-11, Stephane, claude-fable-5[1m]). Three adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) on the uncommitted working tree. Auditor verdict: every `[x]` checkbox independently re-verified honest (AC2 greps, jest 109/109, typecheck baseline, byte-identical PERF blocks); architecture §BF-6 conformance clean. The substantive findings are native-lifecycle robustness, not AC violations. **2 decision-needed, 5 patch, 3 defer, 3 dismissed.**

- [x] [Review][Decision→Patch, APPLIED] **Orphaned FGS with no owner after process/JS death** — `START_STICKY` + `stopWithTask="false"` resurrect the service after an OS kill with a **dead JS context**: `onStartCommand(null)` re-shows "Préparation…" and nothing ever calls stop (the only stop site is the pipeline `finally`, which died with JS). Result: permanent sticky "Analyse en cours…" notification, process pinned alive, battery drain, continuous dataSync-budget burn. Same orphan family reachable without an OS kill via dev-reload/JS-engine crash. [with-foreground-service.js SERVICE_KT; blind+edge, HIGH] — **RESOLVED (Stephane, 2026-06-11): `START_NOT_STICKY` (recorded AC3 deviation — sticky restart can never be reclaimed by JS; checkpoint-resume on relaunch is the recovery path) + `reconcileForegroundServiceAtLaunch()` called from `App.tsx` mount to clear dev-reload/JS-crash orphans.**
- [x] [Review][Decision→Patch, APPLIED] **Concurrent pipelines share the singleton FGS with no ownership** — `isRunning` in `useVideoProcessing.ts:38` is per-hook-instance and the pipeline promise survives unmount, so session B can start while A runs; when A finishes, A's `finally → stopForegroundService()` stops the one shared service and B silently loses its J2 keep-alive. [foregroundService.ts + processingPipeline.ts; edge, MEDIUM] — **RESOLVED (Stephane, 2026-06-11): owner-token in the wrapper — `startForegroundService(sessionId)` claims ownership; `stopForegroundService(sessionId)` from a stale owner is a no-op; the pipeline `finally` passes its sessionId. JS-only change; the `sessionId` is no longer dead payload.**
- [x] [Review][Patch, APPLIED] **`stopForegroundService` native rejection unguarded — a `finally`-thrown reject masks the real pipeline error / fails a succeeded run** [apps/mobile/src/shared/services/foregroundService.ts] — unlike `updateStage`, `await native.stop()` had no try/catch; Kotlin rejects `WARDEN_FGS_STOP_FAILED`, which (a) replaces the in-flight error on the error path, (b) rejects a run whose session is already `"ready"`. **Fixed: swallow-and-warn; new wrapper test suite `src/shared/services/__tests__/foregroundService.test.ts` (5 tests) covers stop-rejection, owner-token, start-throw, non-blocking permission, and reconciliation.** [blind+edge]
- [x] [Review][Patch, APPLIED] **Awaited POST_NOTIFICATIONS dialog gated pipeline start, contradicting AC9 "do not block the pipeline"** [apps/mobile/src/shared/services/foregroundService.ts] — first run on Android 13+ blocked `runProcessingPipeline` on the user dialog after the session was already `"processing"`. **Fixed: `void ensureNotificationPermission()` — the request fires but `native.start()` no longer waits on the dialog.** [blind+edge]
- [x] [Review][Patch, APPLIED] **No `Service.onTimeout()` override — Android 15+ dataSync budget exhaustion crashes the app** [apps/mobile/plugins/with-foreground-service.js SERVICE_KT] — API 35+ caps `dataSync` at 6h/24h cumulative; on exhaustion the system calls `onTimeout()` and ANR-crashes if the service doesn't stop itself. **Fixed: `onTimeout` override → `Log.w` + `stopForeground(STOP_FOREGROUND_REMOVE)` + `stopSelf()` (graceful degrade to the MMKV checkpoint path).** [blind+edge]
- [x] [Review][Patch, APPLIED] **start/updateStage → stop ordering race could hit the "did not call startForeground" framework crash** [apps/mobile/plugins/with-foreground-service.js MODULE_KT+SERVICE_KT] — `stopService` racing a queued `startForegroundService` (fast resume-at-`results` path; error-adjacent stage push) triggers `ForegroundServiceDidNotStartInTimeException`. **Fixed: stop is now delivered as an `action="stop"` start-command through the same `startForegroundService` channel (FIFO; the service always reaches `startForeground` before `stopSelf()`), with a `stopService` fallback if the start-command path is rejected (background-start restriction edge).** [blind+edge]
- [x] [Review][Patch, APPLIED] **Contract/doc fidelity cleanup** [foregroundService.ts + with-foreground-service.js + this story] — (a) stale "repoints the poll loop" JSDoc removed (wrapper header rewritten to the real guarantee set); (b) `sessionId` is now consumed JS-side as the owner token (no longer dead payload; the Kotlin extra remains informational); (c) defensive `Log.w` added for null-intent redelivery and unknown stage keys (AC3); (d) AC4 annotation now records the `withMainApplication`-instead-of-`withDangerousMod` substitution. [auditor F1/F2/F3/F5 + blind]
- [x] [Review][Defer] **Checkpoint-resume freezes/regresses the notification stage text** [apps/mobile/src/features/video-processing/processingPipeline.ts:285-343] — resume at `lastStage="results"` shows "Préparation…" for the whole run (no `reportProgress` fires); resume at `"keyframes"` flips the text back to "Extraction des images-clés" for the entire detection compute. Cosmetic (notification copy only) — observe + polish at the Epic-1-end J2 manual pass. [edge, LOW]
- [x] [Review][Defer] **Android 12+ background-start restriction may block `updateStage` redelivery while backgrounded** [apps/mobile/plugins/with-foreground-service.js MODULE_KT] — `ContextCompat.startForegroundService` from a backgrounded app can throw `ForegroundServiceStartNotAllowedException` (version/OEM-dependent; HyperOS aggressive). Gracefully swallowed by design (worst case: stage text freezes at the last foregrounded value). Deferred: explicitly observe live stage-text updates **while backgrounded** during the AC7/AC8 manual pass. [auditor F4, MEDIUM risk-note]
- [x] [Review][Defer] **Stage-string contract duplicated TS↔Kotlin with silent "Préparation…" fallback** [foregroundService.ts `updateForegroundServiceStage(stage: string)` + SERVICE_KT `stageToText`] — a future stage rename degrades silently on both sides with no compile/test signal. Cosmetic hardening; the 4 stage strings are architecture-bound and stable for V1. [blind, LOW]

Dismissed (3): hardcoded `team.warden.mobile` package (verified == `app.json` `android.package`; architecture-bound constant, no-props is spec'd); direct `@expo/config-plugins` devDependency (deliberate, documented Task-1 decision pinned to the resolved transitive version); test file not wiring synthetic FrameLoader frames per the literal Task-6 text (AC6's 4 mandated lifecycle cases all present and meaningful).

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

claude-opus-4-8[1m] (Claude Opus 4.8, 1M context) — via `/bmad-dev-story`.

### Debug Log References

- `pnpm --filter mobile test` → 14 suites / **109 passed** (was 105; +4 from the new `processingPipeline.test.ts`).
- `pnpm --filter mobile typecheck` → only error is pre-existing `firebaseConfig.ts(5,3)` (`getReactNativePersistence` removed in firebase v12; Story 1.5 scope). Zero errors in this story's files.
- `expo prebuild --platform android --clean` → clean; AC2 greps: `FOREGROUND_SERVICE`=2, `WardenProcessingService`=1, Kotlin files emitted, `MainApplication.kt` patched.
- Android Gradle `:app:assembleDebug` attempted on-device to validate native compilation (see Completion Notes / Task 8).

### Completion Notes List

**Scope delivered (agent-controllable):** Tasks 1–7 complete. AC1, AC2, AC4, AC5, AC6, AC9 satisfied and verified. AC3 satisfied with a user-approved mechanism change (below). AC7, AC8 (manual J2), AC10 (iOS prebuild leg), AC11, AC12 are **pending** — see "Remaining / handoff".

**⚠️ AC3 mechanism change (user-approved 2026-06-11):** AC3 + Dev Notes specified the Kotlin FGS reads the pipeline stage from MMKV via `com.tencent.mmkv.MMKV`. That Java/Kotlin API **does not exist** in react-native-mmkv@3.3.3 — v3 was rewritten to build only the MMKV **C++ Core** (CMake `add_subdirectory(../MMKV/Core core)`, namespace `com.mrousavy.mmkv`) and ships no `com.tencent.mmkv` class (the v2 API). The Kotlin `import com.tencent.mmkv.MMKV` would not compile. Presented 3 options; **Stephane chose "push stage from JS via the bridge."** Implementation: a 3rd bridge method `updateStage(stage)` re-delivers `onStartCommand` with a fresh `stage` extra; the JS pipeline pushes the stage on each transition via a single-point hook in `reportProgress`. The service has no MMKV dependency. All other AC3 contract points (title "Analyse en cours…", channel `processing`/IMPORTANCE_LOW/French copy, lifecycle, typed Android-14 `startForeground` overload, defensive null-stage fallback, `START_STICKY`, `stopWithTask=false`) are implemented as written. The `processing.<sessionId>.stage` MMKV write on the JS side (Story 7.5) is untouched.

**Bridge API choice:** legacy RN Native Modules (`ReactContextBaseJavaModule` + `ReactPackage`, registered via `withMainApplication`), NOT Expo Modules API. A Kotlin file emitted into the prebuild-generated app source tree is not discovered by `expo-modules-autolinking` (it only scans `node_modules` packages with `expo-module.config.json`), so the story's "Expo Modules auto-register" alternative would not actually link. The legacy `ReactPackage` path works under bridgeless/new-arch (`newArchEnabled: true`) via RN's interop layer.

**Pipeline wire-up (AC5):** `startForegroundService(sessionId)` is the first statement **inside** the existing `try`; a `finally { await stopForegroundService(); }` is appended to the existing try/catch. This guarantees stop on success, on re-thrown error, and when start itself throws — while keeping the `__DEV__`/`[PERF-002]`/`[PERF-009]` blocks **byte-identical** (verified via `git diff`). The start call is intentionally un-try/caught so a native failure flips the session to `"error"` (AC5).

**Native compile + install validation (Task 8):** the connected Poco X5 Pro 5G is `dc72b871`. `expo run:android --device dc72b871` failed device-name resolution; ran `:app:assembleDebug` directly via Gradle → **BUILD SUCCESSFUL in 5m19s**, producing `app-debug.apk` (445 MB). This proves the generated Kotlin (Service + Module + Package + the `MainApplication.kt` patch + `AndroidManifest.xml`) compiles. One harmless Kotlin deprecation **warning** on `WardenProcessingPackage.kt:12` (`ReactPackage.createNativeModules` is deprecated in RN's TurboModule migration but is the correct legacy path; build green). Installed (`adb install -r`) + launched (`am start … /.MainActivity`) → app process stays alive (PID), **no native FATAL / no module-registration crash** in logcat; the only error is `ReactHost: Unable to load script`, which is expected for a debug build with no Metro dev-server attached (debug loads JS from Metro). The native layer (incl. the `WardenProcessingPackage` registration) initialised without fault. Note: react-native-fast-opencv emits Windows path-length (`CMAKE_OBJECT_PATH_MAX`) **warnings** during the NDK build — an environment quirk, not a code issue.

**Remaining / handoff — BATCHED TO END OF EPIC 1 (Stephane decision, 2026-06-11):** rather than verify per-story, the manual checks ride along to one complete manual pass at the close of Epic 1. Logged in `deferred-work.md`.
- **AC7 / AC8 (manual J2):** human on the physical device with a paid test account; background-and-resume observation (Battery-Opt ENABLED + DISABLED). Use the *Manual J2 verification* section template. Stub-test fallback per Task 8 if substrate gap #6 blocks the live pipeline.
- **AC10 (iOS prebuild):** re-run `expo prebuild --platform ios` on macOS/Linux/CI (cannot run on this Windows host).
- **AC11 / AC12 + Task 9 (commit / push / PR):** held for the Epic-1-end pass. Branch `foreground-service-android-config-plugin`, single commit `feat: foreground service Android config plugin (Story 1.2)`. Status stays `in-progress`; `sprint-status.yaml` untouched.

### File List

**New:**
- `apps/mobile/plugins/with-foreground-service.js` — Expo config plugin (manifest perms + `<service>`; emits 3 Kotlin files; registers the ReactPackage in `MainApplication.kt`). Embeds the Kotlin source for `WardenProcessingService.kt`, `WardenProcessingModule.kt`, `WardenProcessingPackage.kt`.
- `apps/mobile/src/shared/services/foregroundService.ts` — typed JS wrapper: `startForegroundService` / `updateForegroundServiceStage` / `stopForegroundService` (iOS-guarded, POST_NOTIFICATIONS request, missing-module swallow, iOS Phase 2 TODO).
- `apps/mobile/src/features/video-processing/__tests__/processingPipeline.test.ts` — 4 bridge-lifecycle tests (+ owner-token/ordering assertions from code review).
- `apps/mobile/src/shared/services/__tests__/foregroundService.test.ts` — 5 wrapper-guarantee tests (code review 2026-06-11): stop never rejects, stale-owner skip, start-throw ownership, non-blocking POST_NOTIFICATIONS, launch reconciliation.

**Modified:**
- `apps/mobile/App.tsx` — `reconcileForegroundServiceAtLaunch()` on mount (code review 2026-06-11: clears FGS orphans from a dead JS context).
- `apps/mobile/app.json` — appended `"./plugins/with-foreground-service"` to `expo.plugins`.
- `apps/mobile/package.json` — added `@expo/config-plugins` `~54.0.4` devDependency.
- `apps/mobile/src/features/video-processing/processingPipeline.ts` — import + start-inside-try + finally-stop + single-point stage-push hook.
- `pnpm-lock.yaml` — `@expo/config-plugins` now a direct devDependency of `mobile`.

**Regenerated (NOT committed — git-ignored):** `apps/mobile/android/**` (incl. the 3 emitted `.kt` files + patched `MainApplication.kt`/`AndroidManifest.xml`).

### Manual J2 verification

> _To be completed by Stephane on the Poco X5 Pro 5G (`dc72b871`). The dev APK is already built + installed (`apps/mobile/android/app/build/outputs/apk/debug/app-debug.apk`); start Metro (`pnpm --filter mobile start`) or make a release build to load JS, then follow the AC7/AC8 procedures. Record raw observations below._

**AC7 — Battery Optimization ENABLED:**
- time-of-background: _…_
- process-alive-on-resume (`adb shell ps -A | grep team.warden.mobile`): _…_
- checkpoint-resume fired? (logcat `[processingPipeline]` / MMKV `processing.<sid>.stage`): _…_
- final session status: _…_
- total wall-clock: _…_
- notification observed (title "Analyse en cours…", live stage text): _…_

**AC8 — Battery Optimization DISABLED (`dumpsys deviceidle whitelist +team.warden.mobile`):**
- (same fields) _…_

**Stub-test fallback used? (Y/N + observations):** _…_

## Change Log

| Date       | Author    | Change                                                                                          |
|------------|-----------|-------------------------------------------------------------------------------------------------|
| 2026-05-14 | Stephane (bmad-create-story) | Story created via create-story skill; sprint-status flipped `backlog → ready-for-dev`. |
| 2026-06-11 | Stephane (bmad-code-review, claude-fable-5[1m]) | Adversarial 3-layer review on the working tree. Auditor: all `[x]` honest, architecture §BF-6 conformant. 2 decisions resolved + 7 patches applied: `START_NOT_STICKY` (AC3 deviation #2) + `App.tsx` launch reconciliation (orphan FGS); owner-token stop (concurrent pipelines); never-rejecting `stop()` (finally-safety); fire-and-forget POST_NOTIFICATIONS (AC9); `onTimeout` override (Android 15 dataSync cap); FIFO `action="stop"` delivery (startForeground race); docs/`Log.w` fidelity. +1 test suite (5 wrapper tests). 3 defers logged in deferred-work.md (resume stage-text, backgrounded updateStage observation, stage-string duplication); 3 dismissed. Verified: jest 15/114 green; typecheck baseline-only; prebuild clean + AC2 greps; Gradle `:app:assembleDebug` re-run. |
| 2026-06-11 | Stephane (bmad-dev-story, claude-opus-4-8[1m]) | Implemented Tasks 1–7 + the build/install leg of Task 8. New: `with-foreground-service.js` (Expo config plugin emitting 3 Kotlin files + manifest perms/service + MainApplication registration), `foregroundService.ts` (JS bridge wrapper), `processingPipeline.test.ts` (+4 tests). Modified: `app.json`, `package.json` (+`@expo/config-plugins`), `processingPipeline.ts` (start/finally-stop + stage-push). **AC3 stage-source adapted (user-approved): JS-push via `updateStage` bridge — react-native-mmkv@3.3.3 ships no `com.tencent.mmkv.MMKV` API.** Verified: jest 109/109; android prebuild clean + AC2 greps; `:app:assembleDebug` BUILD SUCCESSFUL (445 MB APK) + installs/launches with no native crash. **Pending handoff to Stephane:** manual J2 (AC7/AC8), iOS-prebuild verify (AC10), commit/push/PR (AC11/AC12, Task 9). Status held `in-progress`. |
