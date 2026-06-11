# Story 1.5: Firebase v12 RN Auth Migration — Migrate firebaseConfig.ts (Story 3.B)

Status: review

<!-- Validation is optional. Run validate-create-story before dev-story for a quality check. -->

## Story

As **Stephane** (solo developer; Sprint 3 mobile critical-path lead),
I want **`apps/mobile/src/features/auth/firebaseConfig.ts` rewritten to initialize auth through `@react-native-firebase/auth` (native auto-persistence from `google-services.json`), dropping the `firebase/auth` JS-SDK init and the now-removed `getReactNativePersistence` symbol**,
so that **the V1-blocking typecheck error is cleared, auth sessions persist natively (Keystore on Android V1), and Stories 1.6–1.8 can migrate their call sites onto the native modules that Story 1.4 installed — without a broken build in between.**

**Type:** Brownfield Item 5 (BF-3) implementation — **Story 3.B** of the architecture-bound 6-story migration sequence (`architecture.md:624-645`: 3.A deps → **3.B config** → 3.C auth → 3.D subscription → 3.E detection-config → 3.F e2e). Story 1.4 (3.A) landed **done** on `main` (feature `50309fd`, merge `692629a`): the 3 `@react-native-firebase/{app,auth,firestore}@^24.1.0` deps, the `app`+`auth` Expo config plugins, and the committed `apps/mobile/google-services.json` (`team.warden.mobile` / `warden-8ce50`) are all present.

**Sprint-fit:** **fits-in-one-sprint.** The edit is one config module; the risk is entirely **build-integration + cross-consumer coupling** (the `app`/`auth` exports of `firebaseConfig.ts` are load-bearing for four still-JS-SDK consumers that aren't migrated until 1.6–1.8). The binding gate is **typecheck → 0 errors** + a **manual login smoke** on a dev build (auth runs on native modules → cannot be unit-asserted). **AC0 below records the central design decision the dev MUST resolve before coding.**

## ⚠️ AC0 — Kickoff design decisions (resolve + record verdicts in the implementation record BEFORE Task 2)

The reconnaissance surfaced a hard sequencing/typing conflict that the epics' per-file framing does not address. Resolve these two before writing code.

### (0a) — How to keep the build green while `firebaseConfig.ts`'s export contract changes

`firebaseConfig.ts` today `export { app, auth }` (`firebaseConfig.ts:31`). Those exports are consumed JS-SDK-modular-style by **four** files, none migrated in this story:

| Consumer | Imports | Uses | Migrated in |
|---|---|---|---|
| `authService.ts:7` | `auth` | `signInWithEmailAndPassword(auth, …)`, `signOut(auth)`, `onAuthStateChanged(auth, cb)` | **1.6** |
| `googleSignInService.ts:6` | `auth` | `signInWithCredential(auth, cred)`, `GoogleAuthProvider.credential(idToken)` | **unassigned** (see 0a-note) |
| `subscriptionService.ts:3` | `app` | `getFirestore(app)` → `getDoc(doc(fs,"users",uid))`, `instanceof Timestamp` | **1.7** |
| `detectionConfigService.ts:25` | `app` | `getFirestore(app)` → `getDoc(doc(fs,"detection_config/latest"))` | **1.8** |

The migration is **type-coupled** through these exports: changing the `auth` export from the JS-SDK `Auth` object to a native `@react-native-firebase/auth` surface makes `signInWithEmailAndPassword(auth, …)` etc. a **new typecheck error** in `authService.ts`/`googleSignInService.ts` — yet AC3 (success criterion) is "typecheck → 0". You cannot land a green build by touching `firebaseConfig.ts` alone.

- **Option A — RECOMMENDED: "auth-native now + migrate the two `auth` call-sites in this PR; keep `firebase/app` `app` export for Firestore."** Rewrite `firebaseConfig.ts` to drop `firebase/auth`/`getReactNativePersistence`/the AsyncStorage adapter and route auth through `@react-native-firebase/auth` (`auth()`, native auto-persistence). Because the `auth` export contract changes, **also update the two `auth` consumers** (`authService.ts`, `googleSignInService.ts`) to the namespaced API (`auth().signInWithEmailAndPassword(...)`, `auth().signInWithCredential(...)`, `auth.GoogleAuthProvider.credential(...)`) — the minimum needed to compile + smoke-pass. **Retain a minimal `firebase/app` `initializeApp` solely to keep the `app` export** alive for the still-JS-SDK Firestore consumers (1.7/1.8). This unavoidably pulls a thin slice of "1.6 authService" forward (the type system forces it); document the overlap so 1.6 doesn't re-litigate. Firestore (`getFirestore(app)`) is untouched and the residual `firebase/app` import is removed in **1.8**.
- **Option B — strict per-file, accept a transient red build.** Touch ONLY `firebaseConfig.ts`; drop the `auth` export; keep `app`. `authService.ts`/`googleSignInService.ts` won't compile until 1.6 — i.e., 1.5+1.6 must ship together (or the build is knowingly red between them). Cleaner ownership, dirtier intermediate state; contradicts AC3's "typecheck 0 in this story".
- **Option C — JS-SDK-shaped compatibility shim.** `firebaseConfig.ts` exports an adapter that wraps native RNFB in the JS-SDK call shape so existing modular call-sites keep working unchanged. Most code, least idiomatic, fragile across 4 consumers — not recommended.

_Decision: **A** (Stephane, 2026-06-11)._ ✅ Migrate the auth side + the two `auth` call-sites in this PR; retain the `firebase/app` `app` export for Firestore (removed in 1.8).

**(0a-note) `googleSignInService.ts` is an UNLISTED consumer.** Story 1.4's source-tree anchors (and the epics' per-file plan) name only `firebaseConfig/authService/subscriptionService/detectionConfigService`. `googleSignInService.ts` imports `auth` and calls `GoogleAuthProvider.credential()` / `signInWithCredential(auth, …)` — a JS-SDK static-method shape with a **different** RNFB surface (`auth.GoogleAuthProvider.credential(idToken)` + `auth().signInWithCredential(cred)`). Under Option A it is migrated here (AC3 smoke-tests Google sign-in); under B it must be assigned to 1.6. **Flag it explicitly — do not orphan Google sign-in.**

### (0b) — `auth` export shape under the namespaced API

RN Firebase's namespaced API is called as the module singleton (`auth().signInWithEmailAndPassword(...)`) — there is **no shared `Auth` instance to inject**. So a `firebaseConfig.auth` export is largely vestigial post-migration; the idiomatic pattern is consumers `import auth from '@react-native-firebase/auth'` directly.

- **Option A — RECOMMENDED:** `firebaseConfig.ts` keeps a tiny ensure-initialized side-effect (RNFB auto-inits the native `[DEFAULT]` app from `google-services.json`, so this may be a no-op import) and **stops exporting `auth`**; the two auth consumers import `auth` from `@react-native-firebase/auth` directly. Cleanest end-state.
- **Option B:** re-export `import auth from '@react-native-firebase/auth'; export { auth }` so consumers' import path is unchanged. Lower churn, but `auth` then means "the RNFB module," not "an instance" — mildly confusing.

_Decision: **A** (Stephane, 2026-06-11)._ ✅ Stop exporting `auth`; the two consumers `import auth from '@react-native-firebase/auth'` directly. Keep the `app` (JS-SDK firebase/app) export regardless, for Firestore, until 1.8.

> **Verdicts (Stephane, 2026-06-11):** (0a) **A** ; (0b) **A** ; googleSignInService → **migrate in this PR** (namespaced `auth.GoogleAuthProvider.credential` + `auth().signInWithCredential`).

## Acceptance Criteria (checklist)

> **AC checkbox convention** ([[feedback_ac_checkbox_tighten]]): items whose endpoint depends on **post-merge actions** (sprint-status `review → done`, PR/merge) are held `[ ]` with inline carve-out notes. All ACs are `[ ]` at create-story time.

0. [x] **AC0 — Kickoff design decisions resolved.** ✅ **Resolved (Stephane, 2026-06-11): (0a) A, (0b) A, googleSignInService → migrate in this PR.** Re-affirmed in the implementation record (Completion Notes) before Task 2. (0a) build-green strategy + (0b) `auth` export shape + googleSignInService disposition (see §AC0 above).

1. [x] **AC1 — `firebaseConfig.ts` no longer imports from `firebase/auth`.** ✅ Done: `firebase/auth` import + `getReactNativePersistence` + the `@react-native-async-storage/async-storage` adapter all removed; the `firebase/app` `initializeApp`/`getApps`/`getApp` import is **retained** as the transitional `app`-export shim (removed in 1.8) per the AC0a Option-A phased-removal carve-out. Verified by typecheck-0 + the diff. New auth import: `@react-native-firebase/auth`. The `getReactNativePersistence` import (`firebaseConfig.ts:5`) and the `@react-native-async-storage/async-storage` persistence adapter (`firebaseConfig.ts:7,27`) are **removed**. _Carve-out:_ the `firebase/app` `initializeApp`/`getApps`/`getApp` import **is retained** as a transitional shim **only** to keep the `app` export alive for the not-yet-migrated Firestore consumers (subscriptionService 1.7, detectionConfigService 1.8) — it is removed in **Story 1.8**. (Per AC0a Option A this re-scopes the epics' literal "no longer imports from `firebase/app`" to a phased removal; record the deviation.)

2. [ ] **AC2 — Auth persistence is automatic (native), no explicit `getReactNativePersistence`.** _Code done; device regression-guard held to Epic-1-end manual pass ([[feedback_batch_manual_checks_epic_end]], deferred-work.md)._ ✅ The AsyncStorage-backed `initializeAuth(app, { persistence: … })` block is gone; auth runs on `@react-native-firebase/auth` (native Keystore persistence, V1; iOS Keychain Phase 2). ⏳ **Regression guard (device):** a signed-in session **survives an app cold restart** — to be confirmed on the dev build at the Epic-1-end pass (must not silently regress to in-memory auth).

3. [ ] **AC3 — `pnpm --filter mobile typecheck` → 0 errors; login flow smoke-tested green on a dev build.** _Typecheck gate DONE; login smoke held to Epic-1-end device pass (deferred-work.md)._ ✅ **typecheck → 0**: baseline = exactly 1 error (`firebaseConfig.ts(5,3) TS2305 getReactNativePersistence`, re-verified red before edit) → **0 after** (incl. the Option-A `authService.ts`/`googleSignInService.ts` call-site migrations + the cross-SDK seam cast at `mapFirebaseUser`); 0 new errors. ⏳ **Smoke (device):** `EXPO_PUBLIC_AUTH_BYPASS=false` email/password + Google-sign-in (google-signin v14) success — recorded on Poco X5 Pro 5G at the Epic-1-end pass (native module → not unit-testable).

4. [ ] **AC4 — `EXPO_PUBLIC_AUTH_BYPASS` honored ([INVARIANT 8]).** _Code-undisturbed verified; runtime re-confirm held to Epic-1-end device pass._ ✅ The bypass branch lives in `App.tsx:29,48` and was **not touched** by this story (App.tsx is not in the diff; it does not import `firebaseConfig`, and the removed `auth` export had no other importers) — structurally undisturbed. ⏳ Runtime `=true`/`=false` behavior (`{uid:'dev-bypass-user', isPaid:true}` short-circuit vs real native auth) re-confirmed at the Epic-1-end pass. Must remain false/unset in release builds.

5. [ ] **AC5 — No boot regression.** _Export gate DONE; on-device boot held to Epic-1-end device pass._ ✅ `expo export --platform android` green at **5.23 MB** (vs 5.28 MB Story-1.4 baseline → **−0.05 MB**: the JS-SDK `initializeAuth`+AsyncStorage adapter dropped from the bundle; 0 RN-Firebase warnings). ⏳ Cold start reaches `LoginScreen` (unauth) / restores session (auth) — confirmed on device at the Epic-1-end pass.

6. [x] **AC6 — Existing jest suite stays green; firebase mock updated only as needed.** ✅ Mobile jest **114/114, 15 suites** (0 regressions). _Baseline note:_ the story's "105/105 per 1.4 baseline" is stale — Story 1.2's code review added `foregroundService.test.ts` (5 tests) when it landed on `main`, so the real current baseline is **114**. The only firebase-mocking test (`detectionConfigService.test.ts`) had its `firebaseConfig` mock factory updated to drop `auth` (Option A removed the `auth` export); `app` retained + Firestore untouched keep it green. **No NEW automated tests** (auth runs native; binding gate = typecheck + deferred device smoke).

7. [x] **AC7 — `firebase` JS SDK NOT removed; Firestore consumers untouched.** ✅ `package.json` keeps `firebase ^12.8.0` (untouched). `git diff --stat` confirms `subscriptionService.ts` + `detectionConfigService.ts` are **byte-identical** (neither appears in the diff). No mobile-only `firebase` pin attempted ([INVARIANT 9] — structurally impossible under `node-linker=hoisted`; moot anyway since `getReactNativePersistence` is gone by 12.12.1).

8. [ ] **AC8 — Sprint-status flip on completion.** _Held `[ ] [HELD]` — `review → done` is post-merge admin._ ✅ In-file flips done: `1-5-…: ready-for-dev → in-progress → review` in `_bmad-output/sprint-status.yaml`; `epic-1` stays `in-progress`. ⏳ `review → done` lands in the post-merge follow-up.

9. [ ] **AC9 — Single-PR delivery + tiny post-merge follow-up (Two-PR pattern).** _Held `[ ] [HELD]` per [[feedback_two_pr_docs_execution]]._ Branch `story-1-5-firebase-rn-migrate-config` (off `main`, already created). Deliverable is `apps/mobile/**`-isolated. `gh` typically unauthenticatable non-interactively → local `git merge --no-ff` per the 1.1/1.2/1.4/9.x precedent; record actual shape. Post-merge follow-up carries the `review → done` flip + AC8/AC9 box-flips.

## Tasks / Subtasks

> **Workflow shape:** brownfield migration story. The target (`@react-native-firebase/*`, namespaced API) is bound by PRD Decision #5 + AC0b carryover from 1.4; the dev executes, it does not re-decide the target. AC checkbox-tighten applies to post-merge ACs.

- [x] **Task 1: Resolve AC0 + audit current state (AC: 0)**
  - [x] Record verdicts for (0a)/(0b)/googleSignInService in the implementation record. _(0a=A, 0b=A, googleSignInService→migrate-here; see Completion Notes.)_
  - [x] Re-read `firebaseConfig.ts` (32 lines) + all 4 consumers; confirm the export-dependency map (auth ← authService, googleSignInService; app ← subscriptionService, detectionConfigService). _Confirmed exactly as documented._
  - [x] Confirm 1.4 substrate present: `package.json:19-21` RNFB@24.1.0; `app.json` `app`+`auth` plugins; `google-services.json` (`warden-8ce50`). _All present (also `google-signin@^14.0.0`, `firebase@^12.8.0`, `async-storage@^2.1.2`); no metro/babel change needed (RNFB v24 autolinked)._
  - [x] Confirm the typecheck baseline: `pnpm --filter mobile typecheck` = exactly 1 error (`getReactNativePersistence`) before any edit. _Confirmed: `firebaseConfig.ts(5,3): TS2305`, the only error._

- [x] **Task 2: Rewrite `firebaseConfig.ts` auth init → native (AC: 1, 2)**
  - [x] Removed `firebase/auth` import + `getReactNativePersistence` + the AsyncStorage `initializeAuth` block.
  - [x] Per 0b Option A: **stopped exporting `auth`**; the two consumers import `auth` from `@react-native-firebase/auth` directly (native auto-init from `google-services.json`; persistence automatic).
  - [x] **Retained** the `firebase/app` `initializeApp`/`getApps`/`getApp` block + `export { app }` (transitional Firestore shim; removed in 1.8) + the env-var-driven `firebaseConfig` object.
  - [x] Verified env `projectId` source + `google-services.json` `project_id` are the SAME shared project (`warden-8ce50`).

- [x] **Task 3: Update the `auth` call-sites to namespaced API (AC: 0a-A, 3) — Option A**
  - [x] `authService.ts`: `auth().signInWithEmailAndPassword(e,p)`, `auth().signOut()`, `auth().onAuthStateChanged(cb)`; retyped `User` → `FirebaseAuthTypes.User`; `mapFirebaseUser`/`formatAuthError` behavior unchanged. _(Cross-SDK seam to `subscriptionService.checkSubscription` bridged with one documented cast — removed in 1.7; see deferred-work.md.)_
  - [x] `googleSignInService.ts`: `auth.GoogleAuthProvider.credential(idToken)`; `auth().signInWithCredential(cred)`.

- [x] **Task 4: Typecheck + jest + export smoke (AC: 3, 5, 6, 7)**
  - [x] `pnpm --filter mobile typecheck` → **0** errors (before: 1 / after: 0).
  - [x] `pnpm --filter mobile test` → **114/114** (15 suites; baseline is 114 not 105 — Story 1.2 added `foregroundService.test.ts`); updated `detectionConfigService.test.ts` mock to drop `auth`.
  - [x] `git diff --stat` confirms `subscriptionService.ts` + `detectionConfigService.ts` untouched (AC7); `firebase` still in `package.json`.
  - [x] `expo export --platform android` green; bundle **5.23 MB** (−0.05 vs 5.28 MB baseline).

- [ ] **Task 5: Dev-build login smoke (AC: 2, 3, 4) — the binding native gate** _[DEFERRED → Epic-1-end manual pass per [[feedback_batch_manual_checks_epic_end]]; logged in deferred-work.md]_
  - [ ] Dev build (`EXPO_PUBLIC_AUTH_BYPASS=false`): email/password sign-in succeeds; Google sign-in succeeds; session **survives cold restart** (native persistence). Record device + outcomes.
  - [ ] `EXPO_PUBLIC_AUTH_BYPASS=true`: dev short-circuit still bypasses to `{uid:'dev-bypass-user', isPaid:true}`; cold start reaches LoginScreen when unauthenticated.

- [ ] **Task 6: Commit, deliver, post-merge follow-up (AC: 8, 9)** _[HELD]_
  - [x] Flip `sprint-status.yaml` `1-5-…: → in-progress → review` (in-file). _Done._
  - [ ] Single commit on `story-1-5-firebase-rn-migrate-config`; local `git merge --no-ff` if `gh` unauthenticatable. Hold `review → done` + AC8/AC9 flips for the post-merge follow-up.

## Dev Notes

### What this story IS — and is NOT

- ✅ **IS:** Story 3.B — migrate the auth **init/config** off the JS SDK to `@react-native-firebase/auth` native persistence, clearing the `getReactNativePersistence` forcing-function typecheck error (the reason the whole 1.4→1.9 migration exists).
- ✅ **IS (under Option A, unavoidably):** a thin slice of the `auth` **call-sites** (`authService.ts`, `googleSignInService.ts`) — the type system couples them to `firebaseConfig`'s export contract; you cannot reach "typecheck 0" otherwise. This overlaps 1.6's authService work; document it so 1.6 doesn't re-do it.
- ❌ **IS NOT:** a Firestore migration. `subscriptionService.ts` (1.7) + `detectionConfigService.ts` (1.8) and their `getFirestore(app)` reads are untouched; the `firebase/app` `app` export is **retained** as a transitional shim and removed in 1.8.
- ❌ **IS NOT:** a `firebase`-JS-SDK removal. The dep stays (Firestore consumers still use it) until after 1.8.
- ❌ **IS NOT:** an iOS story. Native persistence = Android Keystore in V1; iOS Keychain + `GoogleService-Info.plist` are Phase 2 (no iOS artifacts exist; do not block on iOS).
- ❌ **IS NOT:** a modular-API migration. Use the **namespaced** API (`auth()`) per the AC0b verdict carried from Story 1.4; v24 still ships namespaced with deprecation warnings — do not chase them.

### The forcing function (what this story actually fixes)

`firebaseConfig.ts:5` imports `getReactNativePersistence` from `firebase/auth`; that export was dropped by a `firebase@12.x` minor and is **gone at the resolved 12.12.1** (verified pre-existing red on `main` before Story 1.4). `pnpm --filter mobile typecheck` → `firebaseConfig.ts(5,3): TS2305`. Jest stays green (jest-expo babel-transpiles, no `tsc`), so **only typecheck catches it** — run typecheck explicitly as the gate. `@react-native-firebase/auth` persists natively (Keystore/Keychain), so the AsyncStorage adapter the symbol fed is no longer needed at all.

### `firebaseConfig.ts` — current state (the file you are rewriting)

```ts
// apps/mobile/src/features/auth/firebaseConfig.ts (32 lines, current)
import { initializeApp, getApps, getApp } from "firebase/app";
import { initializeAuth, getAuth, getReactNativePersistence } from "firebase/auth"; // ← TS2305 on getReactNativePersistence
import ReactNativeAsyncStorage from "@react-native-async-storage/async-storage";

const firebaseConfig = { apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY ?? "", /* +authDomain, projectId, storageBucket, messagingSenderId, appId — all EXPO_PUBLIC_FIREBASE_* */ };
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
const auth = getApps().length === 1
  ? initializeAuth(app, { persistence: getReactNativePersistence(ReactNativeAsyncStorage) })
  : getAuth(app);
export { app, auth };
```

- Reads **six** `EXPO_PUBLIC_FIREBASE_*` env vars (API_KEY, AUTH_DOMAIN, PROJECT_ID, STORAGE_BUCKET, MESSAGING_SENDER_ID, APP_ID).
- Idempotent app init (`getApps().length === 0 ? init : getApp`).
- The obsolete `TODO: Consider migrating to @react-native-firebase/*` comment (lines 22-23) is literally this story.

### Export-dependency map (why this is coupling-sensitive)

- **`auth`** ← `authService.ts:7` (modular: `signInWithEmailAndPassword(auth,…)`/`signOut(auth)`/`onAuthStateChanged(auth,cb)`), `googleSignInService.ts:6` (`signInWithCredential(auth,cred)`, `GoogleAuthProvider.credential`).
- **`app`** ← `subscriptionService.ts:3` (`getFirestore(app)` → `users/{uid}`; **`instanceof Timestamp`** at L22 is JS-SDK-class-bound — flag for 1.7, RNFB's Timestamp is a different class and the guard would silently read every subscription as unpaid), `detectionConfigService.ts:25` (`getFirestore(app)` → `detection_config/latest`).
- **`useAuthStore.ts`** consumes none of these (MMKV+Zustand) — unchanged across the entire migration (1.4 anchor).

### Tests (current reality)

- **No `apps/mobile/src/features/auth/__tests__/` dir exists** (the epics' "tests under auth/__tests__" is aspirational — those files are `[NEW]` in 1.6/1.7 per `architecture.md:1459-1464`). Do not assume them.
- The **only** firebase-mocking test is `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts` (`jest.mock("../../auth/firebaseConfig", () => ({ app:{}, auth:{} }))` + a `firebase/firestore` stub). Retained `app` + untouched Firestore ⇒ stays green; drop `auth` from the mock factory only if the `auth` export is removed (Option A).
- `formatAuthError.test.ts` / `useAuthStore.test.ts` are firebase-free (cannot break here).
- Jest config is **inline** in `package.json` (`preset: jest-expo`, `transformIgnorePatterns` allow-lists `firebase|@firebase`). **No `jest.setup`/`setupFiles`/`moduleNameMapper`.** No test mocks `@react-native-firebase/*` yet.

### Library / version reality

- `@react-native-firebase/{app,auth,firestore}@^24.1.0` present (1.4). **Namespaced API** per AC0b (`auth()`, not `getAuth()`); v24 deprecates namespaced with warnings — accepted, do not migrate to modular.
- `firebase ^12.8.0` (app-direct **12.12.1** + RNFB-transitive **12.14.0** under hoisting → Metro binds one non-deterministically; flagged from 1.4). 1.5 does not change this; if a single firebase must be pinned, that's a root `pnpm.overrides` (out of scope — flag).
- `@react-native-async-storage/async-storage ^2.1.2` — after this story it may be unused **by auth**; do NOT remove the dep without grepping other consumers (out of scope unless trivially confirmed unused).
- `metro.config.js`/`babel.config.js`: **no change** (RNFB v24 autolinked — 1.4 finding).

### Project Structure Notes

- **Output (1.5):** `apps/mobile/src/features/auth/firebaseConfig.ts` (REWRITE); under Option A also `authService.ts` + `googleSignInService.ts` (call-site migration). File stays at its current path (`architecture.md:1451` — do not relocate).
- **Untouched (verify byte-identical):** `subscriptionService.ts` (1.7), `detectionConfigService.ts` (1.8), `useAuthStore.ts` (no-change), `App.tsx` (bypass branch), `package.json` deps.
- **Admin:** `_bmad-output/sprint-status.yaml` (`1-5` flip, AC8), this story file.
- No modifications outside `apps/mobile/` (plus the sprint-status admin file).

### References

- [Source: epics-and-stories.md:831-849] — Story 1.5 (3.B) source-of-truth ACs + tests + dependency on 1.4.
- [Source: epics-and-stories.md:851-869] — Story 1.6 (authService, 3.C) — the boundary Option A partially borrows from.
- [Source: architecture.md:624-645] — Brownfield Item 5 migration scope + 6-story sequence; `firebaseConfig.ts` "replace JS SDK init with RN Firebase auto-config" (L630) + "persistence automatic, getReactNativePersistence no longer needed" (L631).
- [Source: architecture.md:1097-1100] — Mobile→Firebase Auth contract [LOCKED]: post-migration `@react-native-firebase/auth`; persistence automatic.
- [Source: architecture.md:499-529] — Decision #3: one shared Firebase project (`warden-8ce50`), `europe-west`, env project-ID alignment.
- [Source: architecture.md:1234-1237] — [INVARIANT 2] web sole writer of `users/{uid}`, mobile read-only.
- [Source: architecture.md:1261-1263] — [INVARIANT 8] `EXPO_PUBLIC_AUTH_BYPASS` false/unset in release (AC4).
- [Source: architecture.md:1265-1268] — [INVARIANT 9] `.npmrc node-linker=hoisted` MUST NOT change (why a mobile-only firebase pin is impossible).
- [Source: architecture.md:1449-1456] — source-tree: firebaseConfig.ts migrated per Item 5; stays in place.
- [Source: prd.md:590-591] — Decision #5: V1-blocking migration to `@react-native-firebase/*`; rejects the manual-MMKV-adapter alternative.
- [Source: implementation-artifacts/1-4-firebase-v12-rn-auth-migration-add-deps-prebuild.md] — 1.4 carryover: pre-existing `getReactNativePersistence` baseline (fix = 1.5); AC0b namespaced verdict; dual-SDK coexistence safe; two-firebase-copy hoist note flagged for 1.5; source-tree anchors; "no Metro/Babel change". Plus its `### Review Findings` (App-Check, iOS Phase 2, dual-firebase, firestore.rules — all forward-looking).
- [Source: apps/mobile/src/features/auth/firebaseConfig.ts:1-32] — the rewrite target (current JS-SDK init + the TS2305 symbol).
- [Source: apps/mobile/src/features/auth/{authService.ts,googleSignInService.ts}] — `auth` consumers (Option A call-site migration).
- [Source: apps/mobile/src/features/auth/subscriptionService.ts, video-processing/detectionConfigService.ts] — `app`/Firestore consumers (1.7/1.8; untouched here).
- [Source: memory/feedback_ac_checkbox_tighten.md] — AC checkbox-tighten convention.
- [Source: memory/feedback_two_pr_docs_execution.md] — Two-PR delivery pattern.
- [Source: memory/project_warden_firebase_rn_migration_1_4.md] — 1.4 facts + the firebase-pin-impossible-under-hoisting + getReactNativePersistence-fix-is-1.5 notes.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Amelia / bmad-dev-story), 2026-06-11.

### Debug Log References

- Typecheck baseline (before edit): `pnpm --filter mobile typecheck` → 1 error `src/features/auth/firebaseConfig.ts(5,3): TS2305 … 'getReactNativePersistence'` (the only error). After migration → **0 errors**.
- Intermediate red (expected coupling): first post-migration typecheck surfaced `authService.ts(8,62): TS2345` — RNFB `FirebaseAuthTypes.User` not assignable to `subscriptionService.checkSubscription`'s firebase/auth `User` param (missing `refreshToken`, `tenantId`). Resolved with a single documented cross-SDK cast (see Completion Notes); re-typecheck → 0.
- `pnpm --filter mobile test` → 114 passed, 15 suites (2.2 s).
- `npx expo export --platform android` → green; `index-….hbc` = **5.23 MB**.

### Completion Notes List

**AC0 verdicts re-affirmed before Task 2 (Stephane, 2026-06-11):** (0a) **Option A** — migrate the auth side now + the two `auth` call-sites (`authService.ts`, `googleSignInService.ts`), retain a transitional `firebase/app` `app` export for the still-JS-SDK Firestore consumers (1.7/1.8). (0b) **Option A** — stop exporting `auth`; the two consumers `import auth from "@react-native-firebase/auth"` directly. `googleSignInService.ts` migrated in this PR (namespaced `auth.GoogleAuthProvider.credential` + `auth().signInWithCredential`), not orphaned.

**What was implemented:**
- `firebaseConfig.ts` rewritten: dropped `firebase/auth` + `getReactNativePersistence` + `@react-native-async-storage/async-storage`; dropped the `auth` export. Kept `firebase/app` `initializeApp`/`getApps`/`getApp` + the env-driven `firebaseConfig` object + `export { app }` as the transitional Firestore shim (AC1 phased-removal carve-out; removed in 1.8). Auth now runs entirely on native `@react-native-firebase/auth` (Keystore auto-persistence).
- `authService.ts`: namespaced API (`auth().signInWithEmailAndPassword/signOut/onAuthStateChanged`); `User` → `FirebaseAuthTypes.User`. `formatAuthError`/error-handling behavior unchanged.
- `googleSignInService.ts`: `auth.GoogleAuthProvider.credential(idToken)` + `auth().signInWithCredential(cred)`; all Google-sign-in error handling / `extractIdToken` / `configure` logic unchanged.
- `detectionConfigService.test.ts`: dropped `auth` from the `firebaseConfig` mock factory (the export is gone); `app:{}` retained — stays green.

**Cross-SDK seam (transitional, removed in 1.7):** `mapFirebaseUser(user: FirebaseAuthTypes.User)` passes the user into `subscriptionService.checkSubscription`, which still types its param as the firebase/auth (JS SDK) `User` and reads only `.uid`. AC7 forbids touching `subscriptionService.ts`, so the seam is bridged with a single `user as unknown as Parameters<typeof subscriptionService.checkSubscription>[0]` cast (self-documenting; auto-resolves when 1.7 retypes `checkSubscription`). Logged in deferred-work.md.

**Deviations recorded:** (1) jest baseline is **114**, not the story's stale 105 — Story 1.2's `foregroundService.test.ts` (5 tests) landed on `main` between create-story and now. (2) bundle **5.23 MB** is 0.05 MB *below* the 5.28 MB baseline (JS-SDK auth init removed from the bundle), not the ≈0 delta the story predicted — favorable. (3) AC1's literal "no longer imports `firebase/app`" is re-scoped to phased removal (the `app` shim survives until 1.8) per AC0a Option A.

**Deferred (Epic-1-end manual pass + post-merge):** Task 5 device login smoke (AC2 cold-restart persistence, AC3 email/Google sign-in, AC4 runtime bypass) → batched to the Epic-1-end manual pass ([[feedback_batch_manual_checks_epic_end]], deferred-work.md); auth runs on native modules and cannot be unit-asserted. Task 6 git delivery + AC8 `review→done` + AC9 PR/merge → post-merge Two-PR follow-up ([[feedback_two_pr_docs_execution]]).

### File List

- `apps/mobile/src/features/auth/firebaseConfig.ts` — **rewrite** (auth init → native; drop `firebase/auth`/`getReactNativePersistence`/AsyncStorage + `auth` export; retain `firebase/app` `app` shim).
- `apps/mobile/src/features/auth/authService.ts` — **modified** (namespaced `auth()` API; `FirebaseAuthTypes.User`; cross-SDK seam cast).
- `apps/mobile/src/features/auth/googleSignInService.ts` — **modified** (namespaced `auth.GoogleAuthProvider.credential` + `auth().signInWithCredential`).
- `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts` — **modified** (drop `auth` from the `firebaseConfig` mock factory).
- `_bmad-output/sprint-status.yaml` — **admin** (`1-5` `ready-for-dev → in-progress → review`).
- `_bmad-output/implementation-artifacts/deferred-work.md` — **admin** (Story 1.5 deferred device gates + cross-SDK seam + async-storage prune note).
- `_bmad-output/implementation-artifacts/1-5-…-migrate-firebase-config.md` — **this story file** (Tasks/ACs/Dev Agent Record/Change Log).

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-06-11 | Stephane (create-story, Amelia) | Story 3.B created; AC0 decisions resolved (0a=A, 0b=A, googleSignInService→migrate-here); `backlog → ready-for-dev`. |
| 2026-06-11 | Stephane (dev-story, Amelia / opus-4-8) | Implemented Tasks 1–4: `firebaseConfig.ts` auth→native rewrite (drop `firebase/auth`/`getReactNativePersistence`/AsyncStorage + `auth` export; retain `firebase/app` `app` shim); namespaced-API migration of `authService.ts` + `googleSignInService.ts`; test mock updated. Gates green: typecheck **1→0** (cleared `getReactNativePersistence` TS2305), jest **114/114**, `expo export` **5.23 MB**. Status `ready-for-dev → in-progress → review`; sprint-status `1-5` flipped to `review`. Task 5 (device login smoke) deferred to Epic-1-end manual pass; Task 6 git delivery + AC8/AC9 held post-merge. |
