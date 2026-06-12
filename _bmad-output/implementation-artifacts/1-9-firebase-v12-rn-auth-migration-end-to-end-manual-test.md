# Story 1.9: Firebase v12 RN Auth Migration — End-to-End Manual Test of All 10 PRD Journeys (Story 3.F)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane**,
I want **the Firebase v12 RN auth migration (BF-3, Stories 1.4→1.8) signed off on the Android dev build by manually exercising every PRD journey (J1–J10) that is reachable on the current feature surface, with every unreachable leg explicitly recorded as deferred to the V1-launch-readiness gate**,
so that **Sprint 3 (Epic 3 — the entitlement state machine) binds on a Firebase foundation proven not to have regressed auth, entitlement reads, the processing pipeline, the foreground service, or the offline cache — the architecture's "sign-off binds Sprint 3" gate — without falsely claiming end-to-end coverage of journey legs whose UI does not yet exist.**

## Acceptance Criteria

> **AC checkboxes** per `[[feedback_ac_checkbox_tighten]]`: each box stays `[ ]` until the named verification is recorded in the Dev Agent Record. Manual/device steps are `[ ]`-held until Stephane runs them on the Poco X5 Pro 5G. Legs whose feature does not exist on the current dev build are marked `[DEFERRED]` (not `[ ]`) and recorded in the deferral ledger (AC13) — they are NOT failures and must NOT block this story's sign-off.

### AC0 — Scope decision (kickoff; resolve before any device run)

- [ ] **AC0 — Sign-off scope confirmed.** This story's literal epic AC ("all 10 PRD journeys end-to-end on dev build") collides with the current feature surface: per the feature audit (Dev Notes §Feature Reachability Matrix), the review/clip/voice/export tail (Epics 5/6), the entitlement banners + lapsed/subscription-required screens + `deriveEntitlementState` (Epic 3 / Story 3.1), and the web cancel flow (Epic 4) are stubs or unbuilt. Confirm the scope reading before testing:
  - **Option A (RECOMMENDED) — Migration Regression Sign-off.** Story 1.9 verifies, on the current Android dev build, every journey leg that is reachable now (auth, entitlement read, import, auto-slice pipeline, foreground-service background-survival, offline auth-cache grace, tooling pipeline J10) PLUS the batched device-smoke checks deferred from Stories 1.2/1.5/1.6/1.7/1.8. Every unreachable leg is logged in the AC13 deferral ledger and carried forward to a **V1-launch-readiness gate (Epic 10)** that runs the true full J1–J10 pass once Epics 3/4/5/6 ship. This satisfies the architecture's intent — "sign-off binds Sprint 3" — because Sprint 3 (Epic 3) only needs a regression-clean Firebase foundation, not features Epic 3 itself builds. Sign-off verdict per journey is one of `PASS` / `PASS (reachable legs only)` / `DEFERRED (feature not built)`.
  - **Option B — Hold for full coverage.** Keep Story 1.9 `blocked` until Epics 3/4/5/6 ship, then run the literal full J1–J10 end-to-end pass. Faithful to the literal AC but contradicts "binds Sprint 3" (it would gate Epic 3 on features built in Epic 3+), and strands the BF-3 migration's device sign-off + 5 stories' worth of batched device-smoke checks indefinitely.
  - _Recommended default: **Option A.** Rationale + the circular-dependency argument in Dev Notes §AC0 Decision Detail. If Option B is chosen, this story flips to `blocked` and the remaining ACs become a forward spec for the Epic-10 gate._

### Reachable-now journey sign-off (Option A surface)

- [ ] **AC1 — J1 / J6 reachable legs (first-time activation + Passive→Active conversion).** On the dev build, with a real paid test account and `EXPO_PUBLIC_AUTH_BYPASS=false`: web checkout (apps/web) → mobile **email/password sign-in** AND **Google sign-in** succeed → mobile confirms entitlement (`users/{uid}.status ∈ {active, trialing}`) and reaches `Home` → **import** the reference session via the file picker → **auto-slice** runs to `session.status === 'ready'` with per-round `map_segments` produced. Record per-stage outcome. The review tail (Card View → Cinema Mode → clip → voice → export → share) and T0/T1 telemetry are `[DEFERRED]` (Epics 5/6 stubs; Epic 2 telemetry) → AC13.
- [ ] **AC2 — J2 reachable legs (steady-state + interruption auto-save).** Foreground-service background-survival + MMKV checkpoint resume verified per the batched Story-1.2 procedure (AC8 below): background mid-pipeline → reopen → pipeline either continues (FGS alive) or resumes from the last completed stage via the `processingPipeline.ts` MMKV checkpoint. "Resume Cinema Mode at exact frame + half-recorded voice preserved" is `[DEFERRED]` (Cinema/voice stubs) → AC13.
- [ ] **AC3 — J3 reachable legs (CV failure modes at the data layer).** On a session that produces them, confirm the pipeline emits `map_name = "unknown"` for an unidentified round and that a missed round-boundary leaves a gap (no crash, no blocking error; session still reaches `ready`). The UI legs — unknown-map Card, Cinema "defaults to Full view," manual-clip-from-timeline — are `[DEFERRED]` (Card/Cinema stubs) → AC13.
- [ ] **AC4 — J9 reachable legs (offline-grace 30-day cache).** Airplane mode: a signed-in session stays usable because `subscriptionService.checkSubscription`'s catch falls back to the MMKV-cached `isPaid`, and `useAuthStore` honors its 30-day TTL (`cachedAt`); confirm a >30-day-old `cachedAt` forces re-auth on next foreground (day-31 expiry). The "app fully usable for review + offline export" leg and the offline-grace banner are `[DEFERRED]` (Cinema/export stubs; banner unbuilt) → AC13.
- [ ] **AC5 — J10 (developer regenerates map_config) — tooling pipeline.** On the laptop (independent of the mobile dev build), the consolidated `apps/tooling` pipeline runs end-to-end per the **current** tool inventory (label → zone-pick → test on PNGs → test on video → emit `map_config.<hud_version>.json`) and the cross-language schema gate passes (`jsonschema` on tooling). Note: J10's literal "Tool 1/2/3/4 / `hash_comparator`" names in the PRD are legacy — Epic 9 (Stories 9.9c/9.11/9.12/9.13/9.14, all `done`) replaced them; verify against `wardentooling.py`, the source of truth, not `prd.md:452-465`. → AC13 records any PRD-text drift for the Epic-9/10 editorial pass.

### Batched device-smoke checks (deferred from Stories 1.2 / 1.5 / 1.6 / 1.7 / 1.8)

> All five upstream stories deferred their human-in-the-loop device checks here per `[[feedback_batch_manual_checks_epic_end]]`. Source: `deferred-work.md` §§ dev-story-1.2, 1.5, code-review-1.6/1.7, dev-story-1.8.

- [ ] **AC6 — Login smoke (Story 1.5 AC3).** `EXPO_PUBLIC_AUTH_BYPASS=false`: email/password sign-in succeeds; Google sign-in via `@react-native-google-signin/google-signin` v14 succeeds (namespaced `auth.GoogleAuthProvider.credential(idToken)` + `auth().signInWithCredential(cred)`). Requires `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` set.
- [ ] **AC7 — Native persistence regression guard (Story 1.5 AC2).** A signed-in session **survives an app cold restart** — confirm native Keystore persistence (replacing the removed `getReactNativePersistence(AsyncStorage)` wiring) did NOT silently regress to in-memory auth (reopening cold must NOT bounce to `LoginScreen`).
- [ ] **AC8 — J2 foreground-service background/resume (Story 1.2 AC7 + AC8).** Run the *Manual J2 verification* procedure (Dev Notes §Manual J2 Procedure) with Battery Optimization both **ENABLED** (Tier-2 acceptable: OS kill + MMKV-checkpoint resume) and **DISABLED** (Tier-1: process stays alive). While backgrounded, explicitly observe live notification stage-text updates (code-review-1.2 watch item). Either tier is a PASS for J2; the guarded regression is "pipeline silently abandoned + no resume."
- [ ] **AC9 — Dev auth-bypass re-confirm (Story 1.5 AC4).** `EXPO_PUBLIC_AUTH_BYPASS=true`: `App.tsx` short-circuits to `{uid:'dev-bypass-user', isPaid:true}` and cold start reaches `Home`; with bypass `false` and no session, cold start reaches `LoginScreen`. (Runtime re-confirm only — `App.tsx:26-58` was not touched by the migration.)
- [ ] **AC10 — detectionConfig stale-while-revalidate smoke (Story 1.8 AC9).** On the dev build post-migration: cache miss → Firestore read (`detection_config/latest` via RNFB) → cache populate → next read returns cache; a higher remote `version` triggers a background refresh. Singleflight gates intact (no duplicate inflight reads).
- [ ] **AC11 — subscription status read smoke (Story 1.7 — load-bearing regression scope).** Confirm `subscriptionService.checkSubscription` reads `users/{uid}` via RNFB firestore and correctly classifies a `past_due` doc as not-paid and an `active`/`trialing` (future `current_period_end`) doc as paid, using the duck-typed `Timestamp.toMillis()` guard (NOT `instanceof`). Banner/UI reaction is `[DEFERRED]` (Epic 3). The architecture flags 3.D as the "load-bearing regression scope" for the entitlement state machine — this AC is the device-level confirmation that the migrated Firestore reads return correct truth.

### Cross-platform + delivery

- [ ] **AC12 — iOS prebuild leg (Story 1.2 AC10).** `pnpm --filter mobile exec expo prebuild --platform ios` produces no NEW errors attributable to the Firebase plugins or the foreground-service plugin. UNVERIFIABLE on a Windows/non-macOS host (Expo skips iOS generation) → run on macOS/Linux/CI, or record `[DEFERRED — no macOS/Linux host]` with the iOS-Phase-2 caveat (`deferred-work.md` §code-review-1.4: no `GoogleService-Info.plist`/`ios.googleServicesFile` yet — an iOS prebuild is EXPECTED to fail at Firebase pod link; this AC only binds "no NEW error from the plugins themselves").

### Sign-off artifact

- [ ] **AC13 — Sign-off + deferral ledger recorded.** Create `_bmad-output/v1-launch-readiness-checklist.md` (Epic-10-owned launch-readiness artifact; the epic AC permits "a separate artifact in Epic 10") containing: (a) a per-journey J1–J10 verdict table (`PASS` / `PASS (reachable legs only)` / `DEFERRED (feature not built)`); (b) a **deferral ledger** listing every unreachable leg with its blocking epic/story (J1/J6 review tail → Epics 5/6; J4 → Epic 5; J5 → Epic 6; J7/J8 banners+screens → Epic 3 + Epic 4; J9 review/export legs → Epics 5/6) so the Epic-10 gate inherits a precise punch-list; (c) the BF-3 migration verdict (regression-clean on the reachable surface → Sprint 3 unblocked, OR defects found); (d) any PRD-journey-text drift found in AC5 (J10 legacy tool names). Do NOT delete or overwrite the existing `architecture-spike-perf-floor.md` sign-off content.

## Tasks / Subtasks

- [ ] **Task 0 — Resolve AC0 scope decision (AC: 0)**
  - [ ] Confirm Option A vs B with Stephane (see closing question). If A, proceed; if B, flip story to `blocked` and stop.
- [ ] **Task 1 — Build + install the dev build (agent-controllable prep; AC: 1,2,3,6,7,8,9,10,11)**
  - [ ] `pnpm --filter mobile exec expo prebuild --platform android --clean` (regenerates the gitignored `android/` tree; emits the foreground-service Kotlin + Firebase Gradle wiring).
  - [ ] `pnpm --filter mobile exec expo run:android --device dc72b871` (dev build REQUIRED — RNFB, FFmpeg-kit, fast-opencv, and the foreground service are native modules; Expo Go cannot host them).
  - [ ] Verify env: `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` present; `apps/mobile/google-services.json` committed (Story 1.4); reference video staged at `/sdcard/Download/2026-01-18 12-10-30.mp4` (Story 1.1 Task 3).
  - [ ] Re-confirm the static gates that bind here are green on the working tree: `pnpm --filter mobile typecheck` (0), `pnpm --filter mobile test` (18 suites / 158), `expo export --platform android` (≤ 5.23 MB; Story 1.8 = 4.44 MB).
- [ ] **Task 2 — Reachable-now journey pass (AC: 1,2,3,4,5)**
  - [ ] J1/J6 auth→entitlement→import→auto-slice→`ready`; record per-stage.
  - [ ] J3 unknown-map + missed-round at the data layer (inspect `map_segments`).
  - [ ] J9 airplane-mode auth-cache fallback + day-31 expiry (manipulate `cachedAt`).
  - [ ] J10 tooling pipeline on the laptop against `wardentooling.py`.
- [ ] **Task 3 — Batched device-smoke checks (AC: 6,7,8,9,10,11)**
  - [ ] Login smoke (email + Google); cold-restart persistence; J2 FGS background/resume (BatOpt enabled + disabled); auth-bypass re-confirm; detectionConfig SWR; subscription status read (active/trialing/past_due).
- [ ] **Task 4 — iOS prebuild leg (AC: 12)**
  - [ ] Run on macOS/Linux/CI if available; else record `[DEFERRED — no host]` with the iOS-Phase-2 caveat.
- [ ] **Task 5 — Author the sign-off artifact (AC: 13)**
  - [ ] Create `_bmad-output/v1-launch-readiness-checklist.md` with the J1–J10 verdict table + deferral ledger + BF-3 verdict + PRD-drift notes.
- [ ] **Task 6 — Story-close admin (held; post-pass)**
  - [ ] Commit on the session branch `claude/nifty-brahmagupta-d8194j`; flip `sprint-status.yaml` `1-9 → review` (or `done` if Stephane signs off in-session); update epic-1 status only when ALL Epic-1 stories close.

## Dev Notes

### AC0 Decision Detail — why "all 10 journeys" can't run at Epic-1-end

The architecture sequences BF-3 as `3.A → 3.F` and places **Story 3.F (= 1.9)** immediately after `3.E` (`detectionConfigService`, Story 1.8 — `done`): "Story 3.F — End-to-end manual test. All 10 PRD journeys (J1–J10) on Android dev build. Sign-off binds Sprint 3." [Source: architecture.md:643]

But the BF-3 migration was sequenced into **Epic 1 (foundation)**, while the *journey feature surface* lives in later epics:
- **Card View, Cinema Mode, view-mode toggle** → Epic 5 (Stories 5.1–5.8) — `backlog`.
- **Clip region, voice (3 slots), MP4 export, share sheet** → Epic 6 (Stories 6.1–6.9) — `backlog`.
- **Entitlement banners (payment-failed), lapsed/subscription-required screens, `deriveEntitlementState`** → Epic 3 (3.1–3.10) — `backlog`. `subscriptionService.deriveEntitlementState` literally `throw`s "not implemented until Story 3.1".
- **Web cancel flow / dashboard banners** → Epic 4 — `backlog`.

So "binds Sprint 3" cannot mean "run all journeys first" — Sprint 3 **is** Epic 3, and the journeys need Epic 3+ features. The only non-circular reading is **Option A**: 1.9 proves the *migration* is regression-clean on the surface that exists now, so Epic 3 can build the entitlement state machine on a trusted Firebase foundation. The full J1–J10 pass is the aspirational regression scope, fully exercised at an **Epic-10 V1-launch-readiness gate** once the feature epics ship. The AC13 deferral ledger is the hand-off contract to that gate.

### Feature Reachability Matrix (current dev build)

Source: feature audit of `apps/mobile/src` (2026-06-12). RootNavigator registers only `Login`, `Home`, `Processing`. `CardView`/`CinemaMode`/`ClipMode`/`ExportShare` screens exist as **visual stubs, not wired to navigation**.

| Capability | Status | Path / note |
|---|---|---|
| Email/password + Google sign-in | ✅ REAL | `features/auth/{LoginScreen,authService,googleSignInService}.ts` (RNFB v24.1.0; google-signin v14) |
| Entitlement read (`users/{uid}.status`) | ✅ REAL | `features/auth/subscriptionService.ts` (RNFB firestore; 1h revalidation) |
| `deriveEntitlementState` (6-state machine) | ❌ STUB | `subscriptionService.ts` → `throw "...until Story 3.1"`; `__tests__/deriveEntitlementState.test.ts` all `it.todo` |
| Payment-failed / lapsed / subscription-required UI | ❌ MISSING | no banner/gate components exist |
| Session import (file picker) | ✅ REAL | `features/video-import/{videoImportService,useVideoImport}.ts` (`expo-document-picker`; mp4/H.264/AAC) |
| Auto-slice pipeline (6-stage) | ✅ REAL | `features/video-processing/processingPipeline.ts` + `gameDetector`/`blackScreenDetector`; FFmpeg-kit; pHash map ID |
| OpenCV frame loader (JSI) | ✅ REAL (needs native build) | `shared/services/opencv.ts:412-470` `loadFrameFromPath` (`react-native-fast-opencv` v0.4.8); throws a helpful error if the native binding is absent |
| Card View | ⚠️ STUB | `features/session/CardViewScreen.tsx` — mock data, unrouted |
| Cinema Mode + view-mode toggle | ⚠️ STUB | `features/video-playback/CinemaModeScreen.tsx` — no real player |
| Clip region selector (30s brackets) | ⚠️ STUB | `features/clip-export/ClipModeScreen.tsx` — no gesture handling |
| Voice recording (before/during/after) | ❌ MISSING | schema + DB table exist; **no audio library** in `package.json`; UI slots inert |
| MP4 export (FFmpeg + tier) | ⚠️ SCHEMA-ONLY | `ExportShareScreen.tsx` stub; FFmpeg service exists but no encode job/state machine |
| OS share sheet | ❌ MISSING | `expo-sharing` not a dependency; no `Share.share()` |
| Offline-grace MMKV cache | ✅ REAL | `shared/services/storage.ts` + `useAuthStore` 30-day TTL (`cachedAt`); offline banner ❌ |
| Foreground service (Android) | ✅ REAL | `shared/services/foregroundService.ts` + `plugins/with-foreground-service.js` (Story 1.2) |
| `EXPO_PUBLIC_AUTH_BYPASS` short-circuit | ✅ WIRED | `App.tsx:26-58` → mock `{uid:'dev-bypass-user', isPaid:true}` |
| J10 tooling pipeline | ✅ REAL (laptop) | `apps/tooling` consolidated tools (Epic 9 9.9c/9.11/9.12/9.13/9.14 `done`) |

**Per-journey reachability (Option A surface):**
- **J1 / J6** — `PASS (reachable legs only)`: web checkout → login → entitlement → import → auto-slice→`ready`. Review/clip/voice/export/share + T0/T1 telemetry → DEFERRED.
- **J2** — `PASS (reachable legs only)`: FGS background-survival + MMKV-checkpoint resume. Cinema/voice exact-frame resume → DEFERRED.
- **J3** — `PASS (reachable legs only)`: pipeline `unknown` map + missed boundary at data layer. UI degradation + manual clip → DEFERRED.
- **J4** — `DEFERRED`: Cinema Mode + view-mode toggle + minimap+HUD all stubs; T1-active-player telemetry absent.
- **J5** — `DEFERRED`: no exporter / no share sheet.
- **J7** — `PASS (data-layer only)` for the `past_due` status read (AC11); banner + Customer Portal round-trip → DEFERRED (Epic 3/4).
- **J8** — `DEFERRED`: cancel flow (Epic 4) + lapsed/subscription-required screens (Epic 3) absent; data-layer `canceled→not-paid` confirmable via AC11 mechanism if a `canceled` test doc is staged.
- **J9** — `PASS (reachable legs only)`: offline auth-cache fallback + day-31 expiry. Review/offline-export legs + banner → DEFERRED.
- **J10** — `PASS`: tooling pipeline (verify against `wardentooling.py`, not the legacy PRD tool names).

### Build / device setup

- **Device:** Poco X5 Pro 5G, ADB id **`dc72b871`** (Story 1.1 reference device; SM7325/Android 14). HyperOS is among the most aggressive Android skins for background-process management — even with the FGS, the OS may kill under memory pressure; **Tier-2 graceful-degrade (MMKV checkpoint resume) is accepted for V1** (Story 1.2 Dev Notes; `dontkillmyapp.com`).
- **Why a dev build (not Expo Go):** RNFB, `@wokcito/ffmpeg-kit-react-native`, `react-native-fast-opencv`, and the foreground-service native module require a custom dev client. `expo run:android --device dc72b871` (or `:app:assembleDebug` → `adb install -r`).
- **Reference video:** `/sdcard/Download/2026-01-18 12-10-30.mp4` (≈1h49 EVA After-h, staged in Story 1.1 Task 3).
- **Env:** `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` (Google sign-in), `apps/mobile/google-services.json` (committed Story 1.4 — package `team.warden.mobile`, project `warden-8ce50`), `EXPO_PUBLIC_AUTH_BYPASS` toggled per AC9.

### Manual J2 Procedure (batched from Story 1.2 AC7/AC8)

- **Setup (BatOpt ENABLED — AC8 default):** `adb shell dumpsys deviceidle whitelist` → confirm `team.warden.mobile` is NOT whitelisted. Install the dev build. Sign in with a paid account.
- **Setup (BatOpt DISABLED):** `adb shell dumpsys deviceidle whitelist +team.warden.mobile` first.
- **Procedure:** Import the reference video → auto-slice begins → sticky notification "Analyse en cours…" appears with stage text → press HOME (background) → wait 60s → reopen via launcher.
- **Expected (PASS either tier):** pipeline continues (notification visible, progress advances) **OR** OS killed the JS context and relaunch reads the MMKV checkpoint and resumes from the last completed stage (`processingPipeline.ts` checkpoint logic). The regression guarded against is "pipeline silently abandoned + no resume," NOT "process never killed."
- **Watch items (code-review-1.2 deferrals):** while backgrounded, observe whether the notification stage-text updates live (Android 12+ background-start restriction may freeze it — swallowed by design; cosmetic). Resume at `lastStage="results"`/`"keyframes"` may show frozen/wrong stage copy (cosmetic only).

### Latent auth-hardening items (do NOT fix here — observe + log)

These are pre-existing (1.5-era source), surfaced in code review of 1.6/1.7 (`deferred-work.md`). They are NOT in 1.9 scope (1.9 ships no code) but may manifest during the device pass — log any observation into AC13's ledger for the future auth-error-hardening story:
- Unhandled rejection in the `listenToAuthChanges` async callback / `login` path if `checkSubscription` rejects (latent — the real `checkSubscription` swallows its own errors). `authService.ts:58-65,13-17`.
- `logout()` doesn't guard `auth().signOut()` rejection → session could stay populated. `authService.ts:53-54`.
- Periodic revalidation timer not stopped on logout (`setInterval` leaks; bounded by the `if(!user)return` guard). `subscriptionService.ts:75`.
- Cross-user cache contamination on the offline `isPaid` fallback (spec-pinned by J9/AC4; correct home = Story 3.1's uid-aware state machine). `subscriptionService.ts:47-48`.

### Gates already green (static — bind here, re-confirm in Task 1)

From Story 1.8 (`done`, BF-3 code-complete): `pnpm --filter mobile typecheck` **0 errors**; `pnpm --filter mobile test` **18 suites / 158** (148 passed + 10 todo), 0 regressions; `expo export --platform android` **4.44 MB** (≤ 5.23 MB Story-1.5 baseline — the firebase JS SDK left the bundle). No `firebase/*` JS-SDK import remains in `apps/mobile/src`; `firebaseConfig.ts` deleted; `firebase` dep removed (`pnpm install --frozen-lockfile` consistent). RNFB v24.1.0 `DocumentSnapshot.exists(): boolean` is a METHOD.

### Project Structure Notes

- **No code changes.** This is a manual verification + documentation story. The only file artifact produced is `_bmad-output/v1-launch-readiness-checklist.md` (AC13). Task 1 regenerates the gitignored `apps/mobile/android/` tree via prebuild (not committed).
- **Sign-off artifact location:** the epic AC permits "`architecture-spike-perf-floor.md` OR a separate artifact in Epic 10." Chosen: a **new** `v1-launch-readiness-checklist.md` (the journeys span all epics; Epic 10 owns launch readiness; `architecture-spike-perf-floor.md` is a spike-scoped doc that must NOT be overwritten).
- **Git:** session branch `claude/nifty-brahmagupta-d8194j` (remote-exec session directive — NOT a new `story-1-9-*` branch; 1.6/1.7/1.8 precedent).

### References

- [Source: epics-and-stories.md:912-936] — Story 1.9 epic ACs (J1–J10), deps 1.4–1.8, sprint-fit.
- [Source: epics-and-stories.md:308, 2988, 3101] — BF-3 sequence 3.A→3.F; "architecture-bound BF-3 sequence preserved"; "1.9 large but bounded — one focused day."
- [Source: architecture.md:638-645] — BF-3 migration sequence; "Story 3.F — End-to-end manual test… Sign-off binds Sprint 3"; risk-fallback.
- [Source: prd.md:318-465] — J1–J10 narratives + Capabilities Revealed; [prd.md:452-465] J10 legacy tool names (drift vs Epic 9).
- [Source: deferred-work.md §§ dev-story-1.2, code-review-1.2, code-review-1.4, dev-story-1.5, code-review-1.6, code-review-1.7] — batched device-smoke checks + latent auth-hardening items + iOS Phase-2 caveat.
- [Source: sprint-status.yaml:85-91] — upstream story states (1.2 `in-progress`; 1.5 `review`; 1.4/1.7/1.8 `done`) + the "1.9 device sign-off" framing repeated across 1.5–1.8 entries.
- [Source: feature audit of apps/mobile/src, 2026-06-12] — Feature Reachability Matrix.
- [Source: architecture-spike-perf-floor.md] — AR-SPIKE rung-0 verdict (auto-slice ships as build-and-observe; PERF budgets are soft UX targets, not measurement gates) — relevant to J1/J2/J3 auto-slice expectations.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
