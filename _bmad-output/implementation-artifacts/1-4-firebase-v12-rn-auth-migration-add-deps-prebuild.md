# Story 1.4: Firebase v12 RN Auth Migration — Add Deps + Prebuild (Story 3.A)

Status: review

<!-- Validation is optional. Run validate-create-story before dev-story for a quality check. -->

## Story

As **Stephane** (solo developer; Sprint 3 mobile critical-path lead),
I want **`@react-native-firebase/app`, `@react-native-firebase/auth`, `@react-native-firebase/firestore` added to `apps/mobile/package.json`, the RN-Firebase Expo config plugin registered, a real `google-services.json` committed at an Expo-managed (non-gitignored) location, and `expo prebuild` + `expo export --platform android` running cleanly**,
so that **the migration off the Firebase JS SDK v12 (whose now-deprecated `getReactNativePersistence` symbol is the V1-blocking forcing function) can proceed — the native modules are installed and the Android build is proven green BEFORE any auth/Firestore code is rewritten in Stories 1.5–1.8.**

**Type:** Brownfield Item 5 (BF-3) implementation — **Story 3.A** of the architecture-bound 6-story migration sequence (`architecture.md:624-645`). This is a **plumbing-only** story: add native deps, place the Firebase Android config asset, regenerate native, smoke-build. **No application code changes** to `firebaseConfig.ts` / `authService.ts` / `subscriptionService.ts` / `detectionConfigService.ts` — those are Stories 1.5 / 1.6 / 1.7 / 1.8 respectively. The dev agent does NOT re-litigate the `@react-native-firebase/*` target (PRD Decision #5 bound it).

**Sprint-fit:** **fits-in-one-sprint.** The work is a dependency add + one config-asset placement + a prebuild + a bundle smoke. The risk surface is entirely **build-integration** (the `com.google.gms.google-services` Gradle plugin needs a real `google-services.json` or the Android build fails; RN Firebase v22's modular-API deprecation has forward-implications for 1.5–1.8), **not** algorithmic. No automated tests are added (auth code paths still run on the legacy JS SDK at this point — see "Why no tests" Dev Note).

## Acceptance Criteria (checklist)

> **AC checkbox convention** ([[feedback_ac_checkbox_tighten]]): items whose endpoint depends on **post-merge actions** (sprint-status `review → done` flip, PR-open) are held `[ ]` with inline carve-out notes. Items the dev agent fully controls during the work flip to `[x]` on completion.

0. [x] **AC0 — Kickoff decisions resolved (record verdicts in the implementation record before Task 2).** ✅ **VERDICTS (Stephane, 2026-06-09):** (0a) **Option A** — Stephane supplied a REAL `google-services.json` (`package_name: team.warden.mobile`, `project_id: warden-8ce50`, project_number `1084356703602`), committed at `apps/mobile/google-services.json`; NOT blocked. (0b) **Accept v22+namespaced** for 1.5–1.8 — note the actual resolved line is **v24.1.0** (Expo-54 compat table moved past the story-assumed v22.x since creation); v24 still ships the namespaced API with deprecation warnings, so the verdict and the 1.5–1.8 epic ACs hold. Two create-time decisions block a clean build:
   - **(0a) `google-services.json` source + placement.** RN Firebase's Android build **fails at prebuild/Gradle time without a real `google-services.json`** (the `com.google.gms.google-services` plugin errors on a missing/placeholder file — see Dev Note "google-services.json is a hard build prerequisite"). Because `apps/mobile/android/` is **git-ignored** (root `.gitignore:73-75`, prebuild-on-demand convention from Story 1.1), the file CANNOT live at `apps/mobile/android/app/google-services.json` (it would be untracked and wiped by `expo prebuild --clean`). **RECOMMENDED (Option A):** Stephane downloads the real `google-services.json` from the Firebase console (Android app, package `team.warden.mobile`, the SHARED project per Decision #3), commits it at **`apps/mobile/google-services.json`**, and the story sets `app.json` → `expo.android.googleServicesFile: "./google-services.json"` so the plugin copies it into the regenerated native tree every prebuild. **Option B (blocked):** if Stephane does not yet have the Android app registered in the Firebase console, this story is **BLOCKED** until the app + `google-services.json` exist — there is no placeholder that lets the Android build pass. _Decision: ____ (A / B-blocked)._
   - **(0b) RN Firebase version line + forward-compat.** Versions are resolved by `npx expo install` (Expo-SDK-54-pinned) — do NOT hand-pick. **Caveat the dev MUST record:** the current Expo-54-compatible line is `@react-native-firebase/*` **v22.x**, which **deprecates the namespaced API** (`auth()`, `firestore()`) in favor of the modular API (`getAuth()`, `getFirestore()`). Stories 1.5–1.8's epic ACs are written against the **namespaced** surface (`auth().signInWithEmailAndPassword`, `firestore().collection(...)`). Namespaced still WORKS in v22 (emits deprecation warnings, removal slated for v23). _Decision: accept v22 + namespaced-with-warnings for 1.5–1.8 (recommended — matches epic ACs; revisit modular migration as a separate hardening story) vs. write 1.5–1.8 against the modular API now. Record the chosen surface so the downstream stories are consistent._

1. [x] **AC1 — Three RN Firebase deps added at Expo-SDK-54-compatible versions.** ✅ All three at parity `^24.1.0` via `expo install`. **DEVIATION — defensive pin DROPPED:** the recommended `firebase ^12.8.0 → 12.8.0` pin is **ineffective under the hoisted monorepo** ([INVARIANT 9], single shared `firebase`): `apps/web` requires `firebase ^12.11.0`, so the shared firebase floor is ≥12.11.0 and mobile's exact `12.8.0` cannot pin it lower (an exact `12.8.0` that resolves to 12.12.1/12.14.0 is also misleading). Kept `firebase ^12.8.0` (HEAD value) and held the direct resolution at **12.12.1** (HEAD) — see Completion Notes "Defensive-pin dropped". The 3 deps added + `firebase` retained = AC1 core satisfied. `apps/mobile/package.json` `dependencies` gains `@react-native-firebase/app`, `@react-native-firebase/auth`, `@react-native-firebase/firestore`, all at the SAME version (RN Firebase requires version parity across its packages). Versions are obtained via **`pnpm --filter mobile exec expo install @react-native-firebase/app @react-native-firebase/auth @react-native-firebase/firestore`** (resolves the Expo-54-pinned line; do not hand-edit version ranges). The legacy `firebase@^12.8.0` JS SDK dependency **remains** (it still backs `firebaseConfig.ts` until Story 1.5) — do NOT remove it in this story.
   - **Recommended defensive pin (per `architecture.md:644-645` risk-fallback):** change `firebase` from `^12.8.0` to exactly `12.8.0` (drop the caret) so a transitive minor bump cannot remove `getReactNativePersistence` mid-migration before Story 1.5 lands. This is a `package.json` edit only — NOT a code change to the auth files (AC6 is preserved).

2. [x] **AC2 — `pnpm install` succeeds; INVARIANT 9 preserved.** ✅ `pnpm install` green; lock gained the 3 `@react-native-firebase/*@24.1.0` packages + transitives (including `firebase@12.14.0` as a **direct dependency of `@react-native-firebase/app@24.1.0`** — expected, coexists with the app-facing direct `firebase@12.12.1`). Root `.npmrc` untouched (`node-linker=hoisted` only). `pnpm install` completes; `pnpm-lock.yaml` updates with the three `@react-native-firebase/*` packages. Root `.npmrc` `node-linker=hoisted` ([INVARIANT 9], `architecture.md:1265-1268`) is **unchanged** — do NOT touch `.npmrc`; mobile Metro bundling silently breaks without hoisted linking.

3. [x] **AC3 — RN-Firebase Expo config plugin registered + `google-services.json` wired in `app.json`.** ✅ `expo install` auto-added BOTH `"@react-native-firebase/app"` AND `"@react-native-firebase/auth"` to `expo.plugins` (the auth package ships a config plugin; firestore does not) — kept both (faithful output of the AC1-mandated `expo install`; the auth plugin is benign, mostly iOS/reCAPTCHA). `"@react-native-google-signin/google-signin"` retained. Added `expo.android.googleServicesFile: "./google-services.json"`. No other `app.json` keys changed. `apps/mobile/app.json` is edited so prebuild injects the Firebase Android Gradle integration:
   - `expo.plugins` array gains **`"@react-native-firebase/app"`** (the RN Firebase app config plugin — it injects the `com.google.gms.google-services` classpath into `android/build.gradle` and the `apply plugin` into `android/app/build.gradle` at prebuild time). The existing `"@react-native-google-signin/google-signin"` entry is **retained** (both plugins coexist; order is non-critical).
   - `expo.android.googleServicesFile` is set to **`"./google-services.json"`** (per AC0a Option A), pointing at the committed `apps/mobile/google-services.json`.
   - No other `app.json` keys change (`newArchEnabled: true`, `package: "team.warden.mobile"`, etc. untouched).

4. [x] **AC4 — `expo prebuild --clean` succeeds; native `android/` regenerated with Firebase Gradle wiring.** ✅ All 4 checks green: `android/build.gradle:9` `classpath 'com.google.gms:google-services:4.4.1'`; `android/app/build.gradle:184` `apply plugin: 'com.google.gms.google-services'`; `android/app/google-services.json` copied (1316 B); `android/` git-ignored + absent from `git status`. (Benign prebuild note: "Install expo-system-ui … to enable userInterfaceStyle" — pre-existing, unrelated to Firebase.) `pnpm --filter mobile exec expo prebuild --platform android --clean` completes with no errors. Post-prebuild verification (paste outputs into the implementation record):
   - `apps/mobile/android/build.gradle` contains the `com.google.gms:google-services` classpath (`grep -n "google-services" apps/mobile/android/build.gradle`).
   - `apps/mobile/android/app/build.gradle` applies the google-services plugin (`grep -n "com.google.gms.google-services" apps/mobile/android/app/build.gradle`).
   - `apps/mobile/android/app/google-services.json` exists in the regenerated tree (copied by the plugin from the committed source).
   - **Do NOT commit the regenerated `apps/mobile/android/` tree** — it is git-ignored (root `.gitignore:73-75`); the committed source-of-truth is `apps/mobile/google-services.json` + `app.json` + `package.json`.

5. [x] **AC5 — Android release-bundle smoke build is green (Phase 4 acceptance smoke).** ✅ `expo export --platform android` green on the final tree: `_expo/static/js/android/index-28ac3bc4c720fd3173e742676bed2d61.hbc` = **5.28 MB** (baseline 5.27 MB → **+0.01 MB delta**; RN Firebase is native/Gradle, not JS-bundled, and no app code imports it yet). Zero warnings naming `@react-native-firebase/*`. `pnpm --filter mobile exec expo export --platform android` succeeds and emits a Hermes bundle (`_expo/static/js/android/index-*.hbc`) **with no errors and no warnings about the new `@react-native-firebase/*` native modules**. Record the bundle size and hash. **Baseline reference:** Story 1.1 measured **5.27 MB** (`5.27 MB`, 2026-05-09) on the pre-Firebase tree; adding RN Firebase will grow it modestly — record the delta. (The epic's "≈5.22 MB" was a planning estimate; the real pre-Firebase baseline is 5.27 MB.)

6. [x] **AC6 — Zero application-code changes to the auth/Firestore service files.** ✅ `git diff --stat` over the 4 paths = empty (byte-identical). **Discovery (pre-existing, NOT introduced here):** `pnpm --filter mobile typecheck` reports exactly **1** error — `firebaseConfig.ts(5,3): TS2305 Module '"firebase/auth"' has no exported member 'getReactNativePersistence'` — which is **the V1-blocking forcing-function symbol this whole 1.4→1.8 migration exists to remove**. Verified PRE-EXISTING on `main` (git HEAD, firebase 12.12.1, no RN Firebase): the symbol was already dropped from the default `firebase/auth` entry by a 12.x minor. Story 1.4's dep-add introduces **0 new** TS errors (1 before, 1 after). Fixing `firebaseConfig.ts` is **Story 1.5's** scope (AC6 forbids touching it here). The 105-test mobile jest suite stays green (babel transpile, no type-check). See Completion Notes "Pre-existing typecheck baseline". `apps/mobile/src/features/auth/firebaseConfig.ts`, `authService.ts`, `subscriptionService.ts`, and `apps/mobile/src/features/video-processing/detectionConfigService.ts` are **byte-identical** before and after this story (verify via `git diff --stat` — these four paths must NOT appear). The app continues to run on the legacy `firebase` JS SDK at runtime; the RN Firebase native modules are installed-but-unused until Story 1.5. (RN Firebase auto-initializes a native `[DEFAULT]` app from `google-services.json` at native startup — this is harmless and does NOT conflict with the JS SDK's separately-initialized app; see Dev Note "Dual-SDK coexistence is safe".)

7. [x] **AC7 — `.env.example` Firebase-asset comment corrected (no stale path).** ✅ Comment rewritten to point at `apps/mobile/google-services.json` + `app.json` `expo.android.googleServicesFile`, with the "client config asset, NOT a secret → committed" note. Confirmed root `.gitignore` does NOT exclude `apps/mobile/google-services.json` (`git check-ignore` exit 1). `apps/mobile/.env.example`'s trailing comment currently reads "Android only: place google-services.json in android/app/ ..." — that path is git-ignored and wiped by prebuild. Update the comment to reflect the AC0a/AC3 reality: commit `google-services.json` at `apps/mobile/google-services.json` and reference it via `app.json` `expo.android.googleServicesFile`. **Also add `apps/mobile/google-services.json` is NOT a secret-to-gitignore** — it is a client config asset and IS committed (it contains no server secrets; the Firebase security model relies on Firestore rules + App Check, not on hiding this file). Confirm root `.gitignore` does not exclude `apps/mobile/google-services.json`.

8. [ ] **AC8 — Sprint-status flip on completion.** _Held `[ ]` — the `review → done` portion is post-merge admin._ ⏳ Done so far in-file: `ready-for-dev → in-progress → review` flipped in `_bmad-output/sprint-status.yaml`; `last_updated` bumped 2026-06-09; `epic-1` stays `in-progress` (no epic flip). `review → done` + this box flip to `[x]` land in the post-merge follow-up once `done` is on `main`.

9. [ ] **AC9 — Single-PR delivery; tiny post-merge follow-up per Two-PR pattern.** _Held `[ ]` per [[feedback_two_pr_docs_execution]] adapted for code stories._ All deliverable changes ship in **one PR** titled exactly `feat: Firebase v12 RN auth migration — add deps + prebuild (Story 1.4)`. PR body links: this story file; `architecture.md:624-645` (Brownfield Item 5 sequence); `epics-and-stories.md:810-829` (Story 1.4). Branch: `story-1-4-firebase-rn-add-deps-prebuild` (off `main`). A tiny post-merge follow-up carries the `review → done` flip + AC8/AC9 box-flips. `gh` is typically not authenticatable non-interactively on Stephane's host → delivery may be a local `git merge --no-ff` per the 1.1/1.2/9.x precedent; record the actual delivery shape. ⏳ **Delivery deferred for confirmation:** the working tree is on branch `story-9-12-picker-fixes` and entangles **Story 1.3's uncommitted work** (`apps/web/**` stripe files + `1-3-…md`) and 1.3's `sprint-status.yaml` flip in the same shared file ([[project_warden_shared_doc_commit_boundary]]). Committing/merging 1.4 now would break 1.3's commit boundary. The 1.4 deliverable is file-isolated (`apps/mobile/**` + `pnpm-lock.yaml` + 1.4 story file); awaiting Stephane's go on the branch/commit/merge shape — see Completion Notes "Delivery — entangled tree".

## Tasks / Subtasks

> **Workflow shape:** brownfield plumbing story. The target (`@react-native-firebase/*`) is bound by PRD Decision #5; the dev agent executes, it does not re-decide. AC checkbox-tighten convention applies to post-merge ACs.

- [x] **Task 1: Resolve AC0 kickoff decisions + audit current state (AC: 0)**
  - [x] **(0a)** Confirmed with Stephane — real `google-services.json` exists (`team.warden.mobile` / `warden-8ce50`); placed at `apps/mobile/google-services.json`. NOT blocked (Option A).
  - [x] **(0b)** Recorded: accept v22+namespaced — actual resolved line is **v24.1.0** (still ships namespaced API w/ deprecation warnings); verdict holds for 1.5–1.8.
  - [x] Confirmed current state: `firebase@^12.8.0` + NO `@react-native-firebase/*`; `app.json` plugins = google-signin only; `apps/mobile/android/` git-ignored (`.gitignore:74`).
  - [x] Confirmed `metro.config.js` + `babel.config.js` need **no** changes (RN Firebase v24 fully modular/autolinked). No transformer/resolver work.

- [x] **Task 2: Add the three RN Firebase deps (AC: 1, 2)**
  - [x] Ran `expo install …app …auth …firestore`. Resolved to **`^24.1.0`** (Expo-54 compat moved past the story-assumed v22.x).
  - [x] Verified all three at the same version `^24.1.0` (intra-suite parity).
  - [x] **Defensive pin DROPPED (not applied)** — ineffective under hoisted monorepo (`apps/web` firebase `^12.11.0` floors the shared firebase ≥12.11.0; mobile `12.8.0` cannot pin lower). Kept `firebase ^12.8.0` at HEAD's resolved **12.12.1**. See AC1 + Completion Notes.
  - [x] Ran `pnpm install` (root): green, lock updated with the 3 packages + transitives. `.npmrc` untouched (`node-linker=hoisted` only) — [INVARIANT 9] preserved.

- [x] **Task 3: Register the config plugin + wire google-services in `app.json` (AC: 3, 7)**
  - [x] Placed real `google-services.json` at `apps/mobile/google-services.json` (committed).
  - [x] `app.json`: `expo install` auto-added `"@react-native-firebase/app"` + `"@react-native-firebase/auth"` (kept both; google-signin retained); manually added `"googleServicesFile": "./google-services.json"` under `expo.android`.
  - [x] Updated stale `.env.example` comment per AC7.
  - [x] Confirmed `.gitignore` does NOT ignore `apps/mobile/google-services.json` (only `apps/mobile/android/`).

- [x] **Task 4: Prebuild + verify Firebase Gradle wiring (AC: 4)**
  - [x] Ran `expo prebuild --platform android --clean`: "✔ Finished prebuild", no errors.
  - [x] All four AC4 checks green (classpath, apply-plugin, copied json, ignored tree) — see AC4.
  - [x] Confirmed `apps/mobile/android/` absent from `git status` (git-ignored, not staged).

- [x] **Task 5: Android export smoke build (AC: 5, 6)**
  - [x] Ran `expo export --platform android`: green, `index-28ac3bc4….hbc` **5.28 MB** (+0.01 MB vs 5.27 baseline), zero `@react-native-firebase/*` warnings.
  - [x] `git diff --stat` over the 4 service files = empty (AC6 PASS). `typecheck` = **1 PRE-EXISTING** error (`getReactNativePersistence`, the migration's forcing-function; verified red on `main` HEAD before any change) — **0 new** errors from the dep-add. Mobile jest 105/105 green (no regressions).
  - [x] **`run:android` DEFERRED** — the `export` smoke is the binding AC5 gate (passed). Story 1.1 already proved the prebuild→gradle→install chain on `dc72b871`; a full device install is not re-run here (no native-surface change beyond the autolinked Firebase modules, which the Gradle wiring in AC4 confirms).

- [~] **Task 6: Commit, deliver, open PR (AC: 8, 9)** — _implementation complete; git delivery DEFERRED for Stephane's confirmation (entangled working tree)._
  - [ ] `git checkout -b story-1-4-firebase-rn-add-deps-prebuild` (off `main`). **PENDING** — current branch is `story-9-12-picker-fixes` with co-mingled uncommitted Story 1.3 (`apps/web/**`) work; need the branch/commit/merge shape confirmed before mutating history.
  - [ ] Single commit `feat: Firebase v12 RN auth migration — add deps + prebuild (Story 1.4)`. Files (1.4-isolated): `apps/mobile/package.json`, `apps/mobile/app.json`, `apps/mobile/google-services.json`, `apps/mobile/.env.example`, `pnpm-lock.yaml`, this story file, `_bmad-output/sprint-status.yaml` (the last shares 1.3's flip — shared-doc boundary). **PENDING.**
  - [x] Flipped `_bmad-output/sprint-status.yaml` `1-4-...: ready-for-dev → in-progress → review` in-file (collapse per 1.2 precedent); `last_updated` bumped.
  - [ ] Open PR with the exact AC9 title, or local `git merge --no-ff` if `gh` unauthenticatable. **Hold** `review → done` + AC8/AC9 box-flips for the post-merge follow-up. **PENDING** Stephane's go.

## Dev Notes

### What this story IS — and is NOT

- ✅ **IS:** Story 3.A — the deps+prebuild foundation of the 6-story Firebase migration (`architecture.md:624-645`). It makes the native modules present and the Android build green so Stories 1.5–1.8 can rewrite code against a working substrate.
- ✅ **IS:** A pure plumbing/build-integration story. The only "logic" is config: which deps, where `google-services.json` lives, which `app.json` keys.
- ❌ **IS NOT:** A code-migration story. `firebaseConfig.ts` / `authService.ts` / `subscriptionService.ts` / `detectionConfigService.ts` are NOT touched (AC6). The app still runs the legacy `firebase` JS SDK at runtime after this story.
- ❌ **IS NOT:** An iOS story. `google-services.json` is Android-only; iOS gets `GoogleService-Info.plist` in Phase 2 (`architecture.md:630`). No iOS work here. (`expo prebuild --platform android` is scoped to Android by the flag.)
- ❌ **IS NOT:** A re-decision of the target. PRD Decision #5 bound `@react-native-firebase/*` (`prd.md:590-591`); the "manual MMKV adapter alternative fights upstream guidance and breaks at next Firebase minor" — do not revive it.
- ❌ **IS NOT:** A `firebase`-JS-SDK removal. The JS SDK stays until Stories 1.5–1.8 have migrated each consumer; removing it now would break the live auth path.

### google-services.json is a HARD build prerequisite (the #1 disaster to prevent)

`@react-native-firebase/app` injects the **`com.google.gms.google-services` Gradle plugin**. That plugin **fails the Android build** if `google-services.json` is missing or is a placeholder with a mismatched `package_name`. There is no "build without it" path. Therefore:

- **The file must be a REAL config** downloaded from the Firebase console for an Android app whose package is **`team.warden.mobile`** (matches `app.json:25` `expo.android.package`).
- It must belong to the **SHARED Firebase project** (Decision #3, `architecture.md:499-529`) — the same project whose ID is in `apps/web/.env.example:NEXT_PUBLIC_FIREBASE_PROJECT_ID`. The `project_id` inside `google-services.json` is the cross-surface entitlement contract anchor ([INVARIANT 2]: web writes `users/{uid}`, mobile reads).
- **Placement:** because `apps/mobile/android/` is git-ignored (root `.gitignore:73-75`, the prebuild-on-demand convention established by Story 1.1), the file is committed at **`apps/mobile/google-services.json`** and surfaced to prebuild via `app.json` `expo.android.googleServicesFile: "./google-services.json"`. The RN Firebase plugin copies it into `android/app/` on every prebuild. **Never** commit it under `android/app/` — it would be untracked and lost on `--clean`.
- **If Stephane has not registered the Android app / cannot produce `google-services.json` yet → the story is BLOCKED (AC0a Option B).** Surface this immediately; do not fabricate a placeholder.

### Dual-SDK coexistence is safe (for the duration of the migration)

After this story, BOTH Firebase SDKs are installed: the pure-JS `firebase@12.8.0` (used by `firebaseConfig.ts`) and the native `@react-native-firebase/*` (installed, unused by app code). This is intentional and safe:

- The JS SDK initializes its own JS-side app instance in `firebaseConfig.ts:18`.
- RN Firebase **auto-initializes a native `[DEFAULT]` app** from `google-services.json` at Android startup. This native app is simply unused until Story 1.5 wires `firebaseConfig.ts` to it.
- The two do not collide — they live in different layers (JS heap vs. native). No double-auth, no token conflict, because no app code calls the RN Firebase modules yet.
- The migration retires the JS SDK incrementally (1.5 config → 1.6 auth → 1.7 subscription → 1.8 detection-config); `firebase` is removed from `package.json` only after the last consumer is migrated (a later story, not this one).

### RN Firebase v22 namespaced-API deprecation (forward-compat note for 1.5–1.8)

Expo SDK 54 resolves `@react-native-firebase/*` to the **v22.x** line. v22 **deprecates the namespaced API** (`auth()`, `firestore()`, `auth().signInWithEmailAndPassword(...)`) in favor of the modular API (`getAuth()`, `getFirestore()`, `signInWithEmailAndPassword(getAuth(), ...)`). The namespaced calls **still work** in v22 but log `This v8 method is deprecated...` warnings; removal is slated for v23.

The epic ACs for Stories 1.5–1.8 (`epics-and-stories.md:831-911`) are written against the **namespaced** surface. Recommended AC0b verdict: **accept v22 + namespaced-with-warnings** for 1.5–1.8 to match those ACs, and treat a modular-API migration as a separate hardening story if/when v23 forces it. This story (1.4) ships no Firebase calls, so the decision only needs to be RECORDED here so the downstream stories are internally consistent — it does not change any 1.4 code.

### Versions are Expo-pinned — do NOT hand-pick

Use `pnpm --filter mobile exec expo install @react-native-firebase/app @react-native-firebase/auth @react-native-firebase/firestore`, NOT `pnpm add` with manual ranges. `expo install` consults the Expo SDK 54 compatibility table and resolves the RN-0.81.5-compatible versions. Hand-picking risks a version that mismatches the RN/Expo native ABI and breaks the Gradle build. All three RN Firebase packages MUST be the same version.

### No new Metro / Babel / build-properties config needed

RN Firebase v22 is fully modular and autolinked. `apps/mobile/metro.config.js` and `babel.config.js` need **no** changes. `expo-build-properties` is **not** required for the Android-only V1 path (it would only be needed for iOS static-framework config or custom Maven repos — neither applies here). Do not add it.

### Why no automated tests in this story

Per the epic (`epics-and-stories.md:825`): "Smoke build verification only. No new automated tests in this story (auth code paths still use legacy v12 JS SDK at this point)." The jest suites that exercise auth/Firestore (`apps/mobile/src/features/auth/__tests__/`) still mock the JS SDK and pass unchanged — confirm they remain green if you run `pnpm --filter mobile test`, but no NEW test is authored. The binding acceptance gate is the green `expo export` (AC5). The first RN-Firebase-mocked jest tests appear in Story 1.6 (`authService.test.ts`) and 1.7 (`subscriptionService.test.ts` + `deriveEntitlementState.test.ts` scaffold).

### Build host reality (Windows; prebuild proven)

The dev host is Windows 11 / PowerShell. Story 1.1 (2026-05-09) proved the full `pnpm install → expo prebuild --platform android --clean → expo export --platform android → expo run:android` chain works on this host with a native module (`react-native-fast-opencv@0.4.8`): prebuild regenerated `apps/mobile/android/` cleanly, export produced a 5.27 MB Hermes bundle, and `expo run:android --device dc72b871` (Poco X5 Pro 5G) reached MainActivity (BUILD SUCCESSFUL, `app-debug.apk` 175 MB). The new variable in 1.4 is the RN Firebase native modules + the google-services Gradle plugin — the google-services.json prerequisite is the only realistic failure mode.

### Source-tree anchors (do not modify in this story)

- `apps/mobile/src/features/auth/firebaseConfig.ts` — current JS-SDK init (uses `getReactNativePersistence`); migrated in **Story 1.5**.
- `apps/mobile/src/features/auth/authService.ts` — migrated in **Story 1.6**.
- `apps/mobile/src/features/auth/subscriptionService.ts` — migrated in **Story 1.7**.
- `apps/mobile/src/features/video-processing/detectionConfigService.ts` — migrated in **Story 1.8**.
- `apps/mobile/src/features/auth/useAuthStore.ts` — **no change in the entire migration** (`architecture.md:634`; MMKV+Zustand persist unchanged).

### Project Structure Notes

- **Output locations** for this story:
  - `apps/mobile/package.json` — UPDATE: add 3 `@react-native-firebase/*` deps; (recommended) pin `firebase` to `12.8.0`.
  - `apps/mobile/app.json` — UPDATE: append `"@react-native-firebase/app"` to `expo.plugins`; add `expo.android.googleServicesFile`.
  - `apps/mobile/google-services.json` — NEW (committed): the real Android Firebase config asset.
  - `apps/mobile/.env.example` — UPDATE: correct the stale `android/app/` placement comment.
  - `pnpm-lock.yaml` — UPDATE (the 3 new packages + transitives).
  - `apps/mobile/android/` — REGENERATED by `expo prebuild`; **NOT committed** (git-ignored).
  - `_bmad-output/implementation-artifacts/1-4-...md` — UPDATE: this file (checkboxes, Dev Agent Record, File List, Change Log; Status `ready-for-dev → review`).
  - `_bmad-output/sprint-status.yaml` — UPDATE: `1-4-...` status flip per AC8.
- **No file modifications outside `apps/mobile/`** (plus the two `_bmad-output/` admin files). Web + tooling + contracts untouched.

### References

- [Source: architecture.md:624-645] — **Brownfield Item 5 [PLANNED]** — the migration scope + 6-story sequence (Story 3.A = this story); risk-fallback + `firebase` pin advisory.
- [Source: architecture.md:499-529] — **Decision #3 [RESOLVED]** — one shared Firebase project; `europe-west`; `.env.example` project-ID alignment is the codified contract + CI guard.
- [Source: architecture.md:1234-1237] — [INVARIANT 2] web is sole writer of `users/{uid}`; mobile read-only (why the shared project / matching `google-services.json` project_id matters).
- [Source: architecture.md:1261-1263] — [INVARIANT 8] `EXPO_PUBLIC_AUTH_BYPASS` must be false/unset in release builds.
- [Source: architecture.md:1265-1268] — [INVARIANT 9] `.npmrc node-linker=hoisted` required; agents MUST NOT change it.
- [Source: architecture.md:199-200] — tech stack: Expo SDK 54, RN 0.81.5, React 19.1, `newArchEnabled: true`; Metro `disableHierarchicalLookup`.
- [Source: architecture.md:1097-1105] — Mobile→Firebase Auth + Firestore read contracts (post-migration auto-persistence).
- [Source: architecture.md:1449-1456, 1498-1502] — source-tree placement of the auth + detection-config services.
- [Source: architecture.md:1983-1985] — the `expo export` / `expo prebuild` command convention (Hermes ≈5.22 MB planning figure).
- [Source: prd.md:590-591] — Brownfield Item 5 / PRD **Decision #5**: V1-blocking migration to `@react-native-firebase/*`; rationale rejects the manual-MMKV-adapter alternative.
- [Source: epics-and-stories.md:810-829] — Story 1.4 source-of-truth ACs (Story 3.A).
- [Source: epics-and-stories.md:831-911] — Stories 1.5–1.8 (downstream consumers; namespaced-API ACs — relevant to AC0b).
- [Source: epics-and-stories.md:308, 531] — BF-3 architecture-bound sequence + V1-blocking classification.
- [Source: implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md:37,74,535,581,625] — the `apps/mobile/android/` + `apps/mobile/ios/` `.gitignore` exclusion (prebuild-on-demand); 5.27 MB Hermes baseline; Poco X5 Pro 5G `dc72b871` build-host proof.
- [Source: implementation-artifacts/1-2-foreground-service-android-config-plugin.md] — precedent for the AC-checkbox-tighten convention, the "do NOT commit `apps/mobile/android/`" rule, the single-PR + post-merge-follow-up delivery shape.
- [Source: apps/mobile/.npmrc:1-6] — INVARIANT 9 rationale (Metro cannot traverse pnpm nested store).
- [Source: apps/mobile/app.json:18-32] — current Android package `team.warden.mobile` + plugins array (only google-signin today).
- [Source: apps/mobile/src/features/auth/firebaseConfig.ts:1-31] — the current JS-SDK init with `getReactNativePersistence` (the forcing-function symbol); migrated in 1.5, untouched here.
- [Source: apps/mobile/.env.example] — the stale `android/app/` google-services comment (corrected by AC7) + the Decision-#3 project-ID env vars.
- [Source: memory/feedback_two_pr_docs_execution.md] — Two-PR pattern (adapted to this code story).
- [Source: memory/feedback_ac_checkbox_tighten.md] — AC checkbox-tighten convention.
- [Source: memory/project_warden_ar_spike_binding_only.md] — AR-SPIKE binding-only cut; real JSI binding ships; ship-and-observe stance (1.4 is independent of the rung verdict).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Amelia / bmad-dev-story)

### Debug Log References

- `pnpm --filter mobile exec expo install @react-native-firebase/{app,auth,firestore}` → resolved `^24.1.0` (all 3 at parity); auto-added app+auth Expo config plugins.
- `pnpm install` (root) → lock + node_modules updated; `.npmrc` unchanged.
- `pnpm --filter mobile exec expo prebuild --platform android --clean` → "✔ Finished prebuild".
- AC4 greps: `build.gradle:9` classpath `com.google.gms:google-services:4.4.1`; `app/build.gradle:184` `apply plugin: 'com.google.gms.google-services'`; `android/app/google-services.json` present (1316 B); `git check-ignore apps/mobile/android/app/build.gradle` → ignored.
- `pnpm --filter mobile exec expo export --platform android` → `index-28ac3bc4….hbc` 5.28 MB, exit 0.
- Typecheck investigation: `git stash` + `pnpm install --frozen-lockfile` (HEAD firebase 12.12.1, no RN Firebase) → `typecheck` still reports the `getReactNativePersistence` error ⇒ PRE-EXISTING on `main`, not introduced by 1.4.
- `pnpm why firebase --filter mobile` → `@react-native-firebase/app@24.1.0 → firebase 12.14.0` (transitive); app-direct `firebase 12.12.1`.
- `pnpm --filter mobile test` → 13 suites, 105 passed.

### Completion Notes List

**What shipped (plumbing only):** 3 RN Firebase deps + Expo config plugins + committed `google-services.json` + `app.json`/`. env.example` wiring; native `android/` regenerated with the google-services Gradle plugin; green Android export. Zero app-code changes (AC6).

**Resolved-version deviation (v24, not v22):** Expo SDK 54's compatibility table now resolves `@react-native-firebase/*` to **v24.1.0** (the story Dev Notes assumed v22.x at creation). v24 still ships the namespaced API (`auth()`/`firestore()`) with deprecation warnings, so the AC0b verdict (accept namespaced for 1.5–1.8) and the downstream epic ACs remain valid. No 1.4 code depends on the API surface.

**Config-plugin deviation (auth plugin auto-added):** `expo install` appended BOTH `@react-native-firebase/app` and `@react-native-firebase/auth` to `expo.plugins` (the auth package ships an `app.plugin.js`; firestore does not). Kept both — it is the faithful output of the AC1-mandated `expo install` and the auth plugin is benign on the Android-only V1 path (it mainly drives iOS/reCAPTCHA setup).

**Defensive-pin dropped (AC1 sub-bullet):** the "Recommended" `firebase ^12.8.0 → 12.8.0` exact-pin is **structurally ineffective in this hoisted monorepo**. Under `node-linker=hoisted` ([INVARIANT 9]) there is one shared `firebase`; `apps/web` depends on `firebase ^12.11.0`, so the shared floor is ≥12.11.0 and a mobile-only exact `12.8.0` cannot pin it lower (an exact spec that resolves to 12.12.1/12.14.0 would also be misleading). I kept `firebase ^12.8.0` and held the app-direct resolution at HEAD's **12.12.1** (restored the lock to HEAD then installed, so the lock diff is just the 3 new packages + their transitives — including `firebase@12.14.0` which is a direct dependency of `@react-native-firebase/app@24`). **If you want firebase truly frozen below the symbol-removal point, that needs a root `pnpm.overrides` (and the symbol is gone by 12.12.1 anyway) — out of 1.4 scope; flag for Story 1.5.**

**Pre-existing typecheck baseline (the migration's whole reason):** `pnpm --filter mobile typecheck` reports exactly **1** error — `firebaseConfig.ts(5,3): TS2305 … 'firebase/auth' has no exported member 'getReactNativePersistence'`. This is **the V1-blocking forcing-function symbol** the 1.4→1.8 migration exists to remove. I verified it is **PRE-EXISTING on `main`** (stash test at HEAD's firebase 12.12.1 with no RN Firebase still fails identically), so Story 1.4 introduces **0 new** type errors. AC6 forbids touching `firebaseConfig.ts` — the fix lands in **Story 1.5** (migrate `firebaseConfig.ts` to RN Firebase's native auto-persistence, dropping the `getReactNativePersistence` import). Mobile jest stays 105/105 green (babel transpile does not type-check). Net: typecheck is **not a clean gate on this tree**, but it was already red before 1.4 and the binding AC5 export gate is green.

**Delivery — entangled tree (Task 6 git steps held):** the working tree is on branch `story-9-12-picker-fixes` and carries **uncommitted Story 1.3 work** (`apps/web/**` stripe files, `1-3-stripe-api-pin-bump.md`) plus 1.3's own `sprint-status.yaml` flip in the same shared file. The 1.4 deliverable is otherwise file-isolated (`apps/mobile/**`, `pnpm-lock.yaml`, this story file). Committing/merging 1.4 now would either drag 1.3's in-flight changes or break 1.3's commit boundary ([[project_warden_shared_doc_commit_boundary]]). All code is complete and verified; the branch/commit/merge-to-`main` shape is held for your go.

### File List

**Delivered (Story 1.4):**
- `apps/mobile/package.json` — MODIFIED: added `@react-native-firebase/{app,auth,firestore}@^24.1.0`; `firebase` kept `^12.8.0` (pin not applied — see notes).
- `apps/mobile/app.json` — MODIFIED: `expo.plugins` += `@react-native-firebase/app`, `@react-native-firebase/auth`; `expo.android.googleServicesFile: "./google-services.json"`.
- `apps/mobile/google-services.json` — NEW (committed): real Android Firebase config (`team.warden.mobile` / `warden-8ce50`).
- `apps/mobile/.env.example` — MODIFIED: corrected stale `android/app/` google-services comment (AC7).
- `pnpm-lock.yaml` — MODIFIED: 3 new RN Firebase packages + transitives.
- `_bmad-output/implementation-artifacts/1-4-firebase-v12-rn-auth-migration-add-deps-prebuild.md` — this story file (checkboxes, Dev Agent Record, Status `ready-for-dev → review`).
- `_bmad-output/sprint-status.yaml` — `1-4-…` flipped to `review` + header note.

**Regenerated, NOT committed (git-ignored):** `apps/mobile/android/**` (prebuild output), `apps/mobile/dist/**` (export output).

## Change Log

| Date       | Author    | Change                                                                                          |
|------------|-----------|-------------------------------------------------------------------------------------------------|
| 2026-06-09 | Stephane (bmad-create-story) | Story created via create-story skill; sprint-status flipped `backlog → ready-for-dev`. |
| 2026-06-09 | Amelia (bmad-dev-story) | Implemented Tasks 1–5 + AC0–AC7: added 3 `@react-native-firebase/*@^24.1.0` deps, wired `app.json` plugins + `googleServicesFile`, committed `google-services.json`, fixed `.env.example`; prebuild + export smoke green (5.28 MB). Deviations: dropped the ineffective `firebase` defensive pin; recorded the pre-existing `getReactNativePersistence` typecheck baseline (owned by Story 1.5). Status `ready-for-dev → review`. Git delivery (Task 6) deferred — entangled working tree. |
