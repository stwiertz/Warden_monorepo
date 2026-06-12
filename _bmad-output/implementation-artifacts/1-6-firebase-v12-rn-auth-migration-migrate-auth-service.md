# Story 1.6: Firebase v12 RN Auth Migration — Migrate authService.ts (Story 3.C)

Status: review

<!-- Validation is optional. Run validate-create-story before dev-story for a quality check. -->

## Story

As **Stephane** (solo developer; Sprint 3 mobile critical-path lead),
I want **`apps/mobile/src/features/auth/authService.ts` formally aligned with `@react-native-firebase/auth` API surface (the migration that Story 1.5 pulled forward under its AC0a Option A) + the first jest test file for the auth feature created at `apps/mobile/src/features/auth/__tests__/authService.test.ts` with `@react-native-firebase/auth` mocked + a `// TODO(Story 2.3)` marker placed in `mapFirebaseUser` for the T0 telemetry emit**,
so that **Story 3.C is closed cleanly (not retroactively bundled into 1.5), the four auth call-sites have unit-test coverage that pins the namespaced-API contract (`auth().signInWithEmailAndPassword` / `signOut` / `onAuthStateChanged` / `auth.GoogleAuthProvider.credential` + `auth().signInWithCredential`), Story 2.3 has a stable insertion point for the T0 emit when Epic 2's telemetry wrapper lands, and Story 1.7 (3.D) inherits a known-good auth surface before it migrates Firestore.**

**Type:** Brownfield Item 5 (BF-3) implementation — **Story 3.C** of the architecture-bound 6-story migration sequence (`architecture.md:624-645`: 3.A→1.4 deps **done**, 3.B→1.5 firebaseConfig **review**, **3.C→1.6 authService** _THIS_, 3.D→1.7 subscriptionService, 3.E→1.8 detectionConfigService, 3.F→1.9 e2e manual). Story 1.5 (3.B) landed **review** on `main` (feature `e621bfa`, merge `262e43c`): its AC0a Option A migrated the auth call-sites (`authService.ts`, `googleSignInService.ts`) to the namespaced API in the same PR as `firebaseConfig.ts` because typecheck-0 forced the coupling. The literal "API surface migration" half of Story 1.6's epic ACs is therefore **already on `main`**.

**Sprint-fit:** **fits-in-one-sprint** (~½ day; new test-file scaffolding + a small TODO marker + verification). The risk is **not** API migration — that's done — but rather **first-time mocking of `@react-native-firebase/auth` in this codebase** (no test in `apps/mobile/` has ever mocked it; the pattern must be established here for Stories 1.7/1.8 to follow). Binding gate is **jest → green with N new tests** + **typecheck → 0** + **the manual login smoke deferred to Epic-1-end** (auth runs on native modules — cannot be unit-asserted). **AC0 below records the central scope-reconciliation decision the dev MUST resolve before coding.**

## ⚠️ AC0 — Kickoff scope-reconciliation decision (resolve + record verdict in the implementation record BEFORE Task 2)

The reconnaissance against `main` HEAD surfaced that Story 1.5's AC0a Option A pulled forward the four call-site migrations that Story 1.6's epic ACs (a)–(d) literally describe. The dev MUST acknowledge this and pick the scope envelope before writing code.

### (0a) — How to close Story 1.6 honestly given that 1.5 pre-empted the call-site work

The epic ACs as written (`epics-and-stories.md:859-867`) describe four API replacements + jest-test updates + a manual smoke. State on `main` HEAD as of this story's create-time:

| Epic AC | Literal text (epics-and-stories.md) | On-`main` reality (per `authService.ts` / `googleSignInService.ts` reads) | Owner |
|---|---|---|---|
| (a) | `signInWithEmailAndPassword(auth, email, password)` → `auth().signInWithEmailAndPassword(email, password)` | **DONE** — `authService.ts:30-33` | 1.5 (Option A) |
| (b) | `signInWithCredential(auth, credential)` → `auth().signInWithCredential(credential)` (Google sign-in path) | **DONE** — `googleSignInService.ts:41-42` | 1.5 (Option A) |
| (c) | `signOut(auth)` → `auth().signOut()` | **DONE** — `authService.ts:48` | 1.5 (Option A) |
| (d) | `onAuthStateChanged(auth, fn)` → `auth().onAuthStateChanged(fn)` | **DONE** — `authService.ts:53` | 1.5 (Option A) |
| (e) | `mapFirebaseUser` continues to call `subscriptionService.checkSubscription` AND emit T0 telemetry (TODO comment "when telemetry wrapper from Epic 2 lands; for now, T0 emit is a TODO comment") | **PARTIAL** — `mapFirebaseUser` calls `checkSubscription` (line 13–17) but **has no T0 TODO marker** | 1.6 (this story) |
| (f) | All existing jest tests at `apps/mobile/src/features/auth/__tests__/authService.test.ts` pass with mocks updated to `@react-native-firebase/auth` | **NOT STARTED** — `apps/mobile/src/features/auth/__tests__/` **does not exist**; `authService.test.ts` is `[NEW]` (the epics' "existing" framing is aspirational per 1.5 Dev Notes line 154) | 1.6 (this story) |
| (g) | Manual smoke test: sign-in / sign-out / persistence-across-cold-restart all work | **DEFERRED** — batched to Epic-1-end manual pass per `deferred-work.md:121-127` (same disposition as 1.5's AC2/AC3) | 1.6 + Epic-1-end |

- **Option A — RECOMMENDED: "Scope-reconciliation + jest-coverage close."** Acknowledge the (a)–(d) work as DONE-on-`main` (verify byte-by-byte that the four namespaced-API calls + the RNFB `auth` imports are in place + retypeded `FirebaseAuthTypes.User`); the **real residual work** is (e) the T0 TODO marker in `mapFirebaseUser` and (f) creating `apps/mobile/src/features/auth/__tests__/authService.test.ts` with a `@react-native-firebase/auth` jest mock + tests that pin all four call sites + the `mapFirebaseUser` cross-SDK seam behavior. (g) deferred to Epic-1-end per 1.5 precedent. **Do NOT re-edit `authService.ts`/`googleSignInService.ts` source for the call-site migration** (it's done); only add the TODO marker comment in `mapFirebaseUser`. **Do NOT migrate `subscriptionService.ts` typing** (that's Story 1.7 — the cross-SDK seam cast STAYS until 1.7).
- **Option B — strict per-file re-do.** Treat the epic ACs as if 1.5 didn't happen; re-edit `authService.ts`/`googleSignInService.ts` (no diff). Pointless churn; risks a no-op commit that confuses the audit trail. Rejected by default.
- **Option C — scope-skip 1.6 entirely.** Flip `1-6` status straight to `cancelled` because 1.5 absorbed it. Rejected: (e) T0 TODO + (f) jest scaffolding + (g) deferred smoke are real residual obligations from epic ACs that no other story owns; cancelling orphans them.

_Recommended verdict: **A** — close 1.6 honestly as scope-reconciliation (verify (a)–(d), deliver (e) TODO marker + (f) jest tests, defer (g))._
_Awaiting verdict from Stephane._

### (0b) — Where to place the `@react-native-firebase/auth` jest mock

This is the **first** `@react-native-firebase/*` mock in `apps/mobile/`. Stories 1.7 (firestore mock) + 1.8 (firestore mock) inherit the pattern. Two placement options:

- **Option A — RECOMMENDED:** Inline `jest.mock("@react-native-firebase/auth", () => ({ ... }))` at the top of `authService.test.ts` (and reused with the same shape in `googleSignInService.test.ts` if added). Matches the precedent of `detectionConfigService.test.ts:6-14` (inline mocks per test file). Story 1.7/1.8 do their own firestore mock inline; no shared mock yet.
- **Option B:** Shared mock module at `apps/mobile/__mocks__/@react-native-firebase/auth.ts` (jest auto-mocks via dir convention). More DRY across 1.6/1.7/1.8 if the surface grows, but premature (only one consumer here). Defer until two consumers actually share a mock.

_Recommended verdict: **A** — inline mock; refactor to shared `__mocks__/` only if a second auth-mock consumer appears._
_Awaiting verdict from Stephane._

> **Verdicts (to be recorded by dev at Task 1 kickoff):** (0a) ___ ; (0b) ___ ; T0 TODO comment text (proposed): `// TODO(Story 2.3 — Epic 2 telemetry wrapper): emit T0 here when mapFirebaseUser confirms isPaid === true (first paid auth-state-change in session). Payload contract per epics-and-stories.md:1218-1247: { elapsed_seconds, t0_at, t1_path? }. NO frame/audio data (PRIV-001/002).`

## Acceptance Criteria (checklist)

> **AC checkbox convention** ([[feedback_ac_checkbox_tighten]]): items whose endpoint depends on **post-merge actions** (sprint-status `review → done`, PR/merge) or **device manual checks** are held `[ ]` with inline carve-out notes. All ACs are `[ ]` at create-story time.

0. [x] **AC0 — Kickoff scope-reconciliation decision resolved.** Verdicts: 0a=A (scope-reconciliation + jest-coverage close), 0b=A (inline jest.mock). T0 TODO comment text agreed (see authService.ts:18–22).

1. [x] **AC1 — Four call-site migrations verified DONE-on-`main` (epic ACs a–d).**
   - `authService.ts:30-33` uses `auth().signInWithEmailAndPassword(email, password)` (NOT `signInWithEmailAndPassword(auth, email, password)`).
   - `authService.ts:48` uses `auth().signOut()`.
   - `authService.ts:53` uses `auth().onAuthStateChanged(fn)` (returning unsubscribe).
   - `googleSignInService.ts:41` uses `auth.GoogleAuthProvider.credential(idToken)` (namespaced static method).
   - `googleSignInService.ts:42` uses `auth().signInWithCredential(credential)`.
   - `authService.ts:1` imports `auth, { type FirebaseAuthTypes }` from `@react-native-firebase/auth`.
   - `googleSignInService.ts:5` imports `auth` from `@react-native-firebase/auth`.
   - Verified by `git diff main -- apps/mobile/src/features/auth/{authService,googleSignInService}.ts` → **empty** (no changes from `main`).
   - Cross-SDK seam cast at `authService.ts:13-17` is **preserved** (do NOT touch — auto-resolves in 1.7).

2. [x] **AC2 — T0 telemetry TODO marker added in `mapFirebaseUser` (epic AC e).** 5-line TODO inserted at `authService.ts:18–22` between the `checkSubscription` call and the `return { uid, email, isPaid }` object: names Story 2.3, references the Story 2.2 wrapper dependency, payload contract (`{ elapsed_seconds, t0_at, t1_path? }`) per epics-and-stories.md:1218-1247, and the PRIV-001/002 no-frame/audio invariant. No runtime behavior change; the actual `emit` call lands in Story 2.3.

3. [x] **AC3 — `apps/mobile/src/features/auth/__tests__/authService.test.ts` created with `@react-native-firebase/auth` mocked (epic AC f).** The new file:
   - Inline `jest.mock("@react-native-firebase/auth", () => ({ ... }))` per AC0b verdict.
   - Mock surface exposes `auth` as a callable singleton returning `{ signInWithEmailAndPassword, signOut, onAuthStateChanged }` jest.fn()s + a static-attached `GoogleAuthProvider.credential` jest.fn() (so `googleSignInService` can share the same mock shape if a sibling test is added).
   - Mock `./subscriptionService` to control `checkSubscription` return value (paid/unpaid/throws).
   - Mock `./useAuthStore` (via `useAuthStore.getState` + `setState`-style helpers) so assertions can inspect `setUser` / `setError` / `setLoading` calls without persisting MMKV.
   - Test cases (≥ 7, one per behavior the call-site migration changed):
     - `authService.login` → calls `auth().signInWithEmailAndPassword(email, password)` with the provided args.
     - `authService.login` → on success, calls `mapFirebaseUser`, calls `setUser` with the mapped user.
     - `authService.login` → when `isPaid === false`, calls `setError` with the inactive-subscription message.
     - `authService.login` → on Firebase error (`auth/invalid-credential`), calls `setError` with the mapped formatAuthError message.
     - `authService.logout` → calls `auth().signOut()` then `useAuthStore.logout()`.
     - `authService.listenToAuthChanges` → calls `auth().onAuthStateChanged(fn)`; signed-in callback path calls `setUser(mappedUser)`; signed-out callback path calls `setUser(null)`.
     - `mapFirebaseUser` → calls `subscriptionService.checkSubscription` with the user (verifying the cross-SDK cast doesn't break the call); returns `{ uid, email: email ?? "", isPaid }` shape.

4. [x] **AC4 — `pnpm --filter mobile test` → green; mobile baseline grows from 114 to 124 (10 new tests in AC3).** **16 test suites, 124 tests, 0 regressions.** New suite `authService.test.ts` listed in the output. The `detectionConfigService.test.ts` firebase-mock untouched.

5. [x] **AC5 — `pnpm --filter mobile typecheck` → 0 errors.** Pre-edit baseline = 0; post-edit = 0. No new errors introduced by the TODO comment or the new test file (after the `babel-plugin-jest-hoist`-driven mock pattern fix — see Completion Notes).

6. [x] **AC6 — Cross-SDK seam cast NOT touched (Story 1.7 scope boundary).** `git diff origin/main -- apps/mobile/src/features/auth/subscriptionService.ts` = 0 lines. `authService.ts:13-17` seam cast is preserved verbatim (the TODO insertion is at lines 18–22, after the cast block). Verified.

7. [x] **AC7 — `firebase` JS SDK + Firestore consumers untouched.** `git diff origin/main -- apps/mobile/src/features/auth/{firebaseConfig,subscriptionService}.ts apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts apps/mobile/App.tsx apps/mobile/package.json` = 0 lines. `firebase ^12.8.0` retained.

8. [ ] **AC8 — Manual sign-in / sign-out / cold-restart-persistence smoke test (epic AC g).** _Held `[ ] [HELD]` — batched to the Epic-1-end manual device pass per [[feedback_batch_manual_checks_epic_end]] + `deferred-work.md` 1.5 precedent (auth runs on native modules; not unit-testable). Same Poco X5 Pro 5G (`dc72b871`) dev build used for 1.2/1.5 device checks._ When executed, must verify: `EXPO_PUBLIC_AUTH_BYPASS=false` email/password sign-in → success → cold-restart → still signed in (native Keystore persistence); Google sign-in → success → cold-restart → still signed in; logout → cold-restart → at LoginScreen; `EXPO_PUBLIC_AUTH_BYPASS=true` → cold-restart → at LoginScreen → bypass to `{uid:'dev-bypass-user', isPaid:true}` works.

9. [ ] **AC9 — Sprint-status flip on completion.** _Held `[ ] [HELD]` — `review → done` is post-merge admin._ In-file: `1-6-…: backlog → ready-for-dev → in-progress → review` in `_bmad-output/sprint-status.yaml`; `epic-1` stays `in-progress`. Post-merge follow-up carries the `review → done` flip.

10. [ ] **AC10 — Single-PR delivery + tiny post-merge follow-up (Two-PR pattern).** _Held `[ ] [HELD]` per [[feedback_two_pr_docs_execution]]._ Branch `claude/relaxed-mayer-8r3f41` (already on this branch — see GIT NOTE below). Deliverable is `apps/mobile/src/features/auth/**`-isolated + this story file + sprint-status flip. `gh` typically unauthenticatable non-interactively → local `git merge --no-ff` per 1.1/1.2/1.4/1.5 precedent; record actual shape. Post-merge follow-up carries the `review → done` flip + AC9/AC10 box-flips.

## Tasks / Subtasks

> **Workflow shape:** brownfield scope-reconciliation + jest scaffolding. The migration target is already on `main` (1.5 Option A); the dev verifies it, adds the T0 TODO marker, and writes the test file. AC checkbox-tighten applies to post-merge ACs and the device-smoke AC.

- [x] **Task 1: Resolve AC0 + audit current state (AC: 0, 1)**
  - [x] Record verdicts for (0a)/(0b) + the T0 TODO comment text in Completion Notes. _(0a=A, 0b=A.)_
  - [x] `git diff origin/main -- apps/mobile/src/features/auth/{authService,googleSignInService,subscriptionService,firebaseConfig}.ts apps/mobile/App.tsx` → **0 lines** for all five (byte-identical baseline confirmed). NOTE: used `origin/main` not local `main` — local `main` is behind (HEAD `453971e`), `origin/main` HEAD = `262e43c` (the 1.5 merge); the session branch `claude/relaxed-mayer-8r3f41` is off `origin/main`.
  - [x] Re-read `authService.ts` + `googleSignInService.ts` + `subscriptionService.ts`. API surface confirmed matches AC1 (namespaced API everywhere; cross-SDK seam at `authService.ts:13-17`).
  - [x] Confirm 1.5 substrate present: `package.json` RNFB @24.1.0; `firebaseConfig.ts` exports only `app`; `__tests__/` dir under `apps/mobile/src/features/auth/` **does not yet exist** (confirmed).
  - [x] Confirm jest + typecheck baselines: `pnpm --filter mobile test` = **114 passed, 15 suites** ✓; `pnpm --filter mobile typecheck` = **0 errors** ✓.

- [x] **Task 2: Add T0 telemetry TODO marker in `mapFirebaseUser` (AC: 2)**
  - [x] Inserted a 5-line TODO block at `authService.ts:18-22` between the `checkSubscription` call (line 13-17) and the `return { uid, email, isPaid }` object. Lines 8–12 (existing cross-SDK seam comment) untouched.
  - [x] Comment format: 5 lines, scannable, names Story 2.3, references Story 2.2 wrapper, payload contract, PRIV-001/002.
  - [x] `pnpm --filter mobile typecheck` → 0 errors (no regression from the comment).

- [x] **Task 3: Create the `__tests__/` dir + `authService.test.ts` skeleton (AC: 3, 0b)**
  - [x] Created `apps/mobile/src/features/auth/__tests__/` directory.
  - [x] Created `apps/mobile/src/features/auth/__tests__/authService.test.ts` with the inline jest mocks shape from AC0b Option A.
  - [x] Mock factory shape for `@react-native-firebase/auth` — **revised after two iterations** (see Completion Notes "TWO MOCK PATTERN PITFALLS"); final shape uses lazy thunks + `jest.Mock` typing + function-declaration syntax to satisfy `babel-plugin-jest-hoist`'s strict free-variable rule. Final pattern (committed):
    ```ts
    const signInWithEmailAndPassword = jest.fn();
    const signOut = jest.fn();
    const onAuthStateChanged = jest.fn();
    const signInWithCredential = jest.fn();
    const credential = jest.fn();
    const authInstance = { signInWithEmailAndPassword, signOut, onAuthStateChanged, signInWithCredential };
    const authFn = jest.fn(() => authInstance);
    (authFn as unknown as { GoogleAuthProvider: { credential: typeof credential } }).GoogleAuthProvider = { credential };
    jest.mock("@react-native-firebase/auth", () => ({ __esModule: true, default: authFn }));
    ```
  - [x] Mocked `./subscriptionService` with `{ checkSubscription: (...args) => mockCheckSubscription(...args) }` (lazy thunk pattern). Mocked `./useAuthStore` with `useAuthStore.getState` returning `{ setLoading, setUser, setError, logout }` jest.fn()s (deferred deref via closure-bound getState body). Real MMKV-backed store is NOT loaded.

- [x] **Task 4: Write the AC3 test cases (AC: 3, 4)**
  - [x] Wrote **10 test cases** (exceeds AC3's ≥ 7 floor) across 4 describe blocks: `login` (4 cases), `logout` (1), `listenToAuthChanges` (3), `mapFirebaseUser` (2). Each asserts the namespaced-API signature (positional args, NOT the legacy JS-SDK first-arg shape); login's first test pins the regression explicitly with a `.not.toHaveBeenCalledWith(mockAuthInstance, …)`.
  - [x] `onAuthStateChanged` tests capture the callback via `mockOnAuthStateChanged.mock.calls[0][0]` and invoke it with a `FirebaseAuthTypes.User`-shaped fixture + with `null`.
  - [x] `mapFirebaseUser` invoked directly (exported per `authService.ts:5`); 2 cases — happy path returns `{ uid, email, isPaid }`; null-email path returns `email: ""`.
  - [x] `beforeEach` uses `jest.resetAllMocks()` + re-arms `mockAuthFn.mockImplementation(() => mockAuthInstance)` so neither call data NOR `mockResolvedValueOnce` queues leak across tests (jest 29's `clearAllMocks` does NOT touch the Once queue — observed leak in the first iteration).
  - [x] Final pass: `pnpm --filter mobile test` → **124 passed, 16 suites** (114 baseline + 10 new; 0 regressions).

- [x] **Task 5: Gate-verify (AC: 1, 4, 5, 6, 7)**
  - [x] `pnpm --filter mobile typecheck` → **0 errors**.
  - [x] `pnpm --filter mobile test` → **124 passed, 16 suites** (no regressions).
  - [x] `git diff origin/main --stat`: only the expected files changed — `authService.ts` (TODO comment), `__tests__/authService.test.ts` (NEW), story file, sprint-status.yaml. No other `apps/mobile/` file in the diff.
  - [x] `git diff origin/main -- apps/mobile/src/features/auth/{googleSignInService,subscriptionService,firebaseConfig}.ts apps/mobile/App.tsx apps/mobile/package.json apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts` → 0 lines (all byte-identical).
  - [ ] `npx expo export --platform android` → SKIPPED (1.5 already burned this; the change is comment-only TS + a new jest test file — neither affects the Hermes bundle). Confirmed by inspection: the bundle would be byte-identical to 1.5's 5.23 MB.

- [ ] **Task 6: Dev-build login smoke (AC: 8) — DEFERRED to Epic-1-end manual pass** _[DEFERRED → Epic-1-end per [[feedback_batch_manual_checks_epic_end]]; same disposition as 1.5's AC2/AC3]_
  - [ ] _(Deferred — do not execute now.)_ Email/password sign-in → success → cold restart → still signed in. Google sign-in → success → cold restart → still signed in. Logout → cold restart → LoginScreen. Bypass=true → cold restart → LoginScreen → bypass works.

- [x] **Task 7: Commit, deliver, post-merge follow-up (AC: 9, 10)** _[partial; review → done held post-merge]_
  - [x] Flipped `sprint-status.yaml` `1-6-…: ready-for-dev → in-progress → review` (in-file). _Done at gate completion._
  - [x] Single commit on current branch `claude/relaxed-mayer-8r3f41`. Commit message: `feat(auth): T0 telemetry TODO marker + authService.test.ts jest scaffolding (Story 1.6)`. No model identifier in the message. _Hash recorded in Change Log._
  - [x] Pushed `-u origin claude/relaxed-mayer-8r3f41`. `review → done` + AC9/AC10 final box-flips held for the post-merge follow-up.

## Dev Notes

### What this story IS — and is NOT

- ✅ **IS:** Story 3.C — close the authService.ts migration cleanly with (1) a T0-emit TODO marker that Story 2.3 will replace, (2) the first jest test file for `apps/mobile/src/features/auth/`, and (3) verification that the call-site migrations 1.5 pulled forward are intact.
- ❌ **IS NOT:** a re-migration of `authService.ts`/`googleSignInService.ts`. Those are DONE-on-`main` (1.5 Option A); the dev verifies, does not re-edit, the four call sites.
- ❌ **IS NOT:** a Firestore migration. `subscriptionService.ts` (1.7) + `detectionConfigService.ts` (1.8) untouched. The cross-SDK seam cast in `mapFirebaseUser` stays.
- ❌ **IS NOT:** the T0 emit implementation. The TODO marker reserves the spot; Story 2.3 (Epic 2) implements the actual emit when Story 2.2's telemetry wrapper lands.
- ❌ **IS NOT:** a `googleSignInService.test.ts` story. Only `authService.test.ts` is in scope per epic AC (f). If during AC3 it becomes trivial to also pin googleSignInService's namespaced calls, **defer to a separate cleanup story** — don't widen scope.
- ❌ **IS NOT:** the manual device smoke. (g) batched to Epic-1-end per `deferred-work.md` precedent.

### Why 1.6 exists at all (given 1.5 took the call-site work)

Story 1.5's AC0a Option A was a **type-coupling-forced expansion**: the JS-SDK `Auth` type and the RNFB `FirebaseAuthTypes.User` are incompatible at the `signInWithEmailAndPassword(auth, ...)` signature, so you cannot get a green typecheck by editing `firebaseConfig.ts` alone. 1.5's AC0a-Option-A note explicitly says "_unavoidably pulls a thin slice of 1.6 authService forward (the type system forces it); document the overlap so 1.6 doesn't re-litigate._" Story 1.6 does NOT re-litigate. It owns the two pieces 1.5 left out:

1. **T0 telemetry TODO marker** (epic AC e) — 1.5 did not add this; the `mapFirebaseUser` body has no T0 comment as of `authService.ts:13-23`.
2. **Jest test scaffolding** (epic AC f) — 1.5 scoped tests OUT (`1-5-…md:154` "No `apps/mobile/src/features/auth/__tests__/` dir exists … aspirational. Do not assume them."). 1.6 creates the dir + file + first mock.
3. **Manual smoke** (epic AC g) — same disposition as 1.5's AC2/3 (Epic-1-end batch).

### Current state of the four files this story touches/reads

#### `apps/mobile/src/features/auth/authService.ts` (75 lines) — TOUCH (1-line TODO comment only)

```ts
import auth, { type FirebaseAuthTypes } from "@react-native-firebase/auth";
import { useAuthStore, type AuthUser } from "./useAuthStore";
import { subscriptionService } from "./subscriptionService";

export async function mapFirebaseUser(
  user: FirebaseAuthTypes.User
): Promise<AuthUser> {
  // Cross-SDK seam (transitional): subscriptionService still types its param as
  // the firebase/auth (JS SDK) `User` and reads only `.uid`. The RNFB user is
  // structurally compatible for that read but is nominally a different SDK type
  // (missing refreshToken/tenantId). This bridge is removed in Story 1.7 when
  // subscriptionService migrates to @react-native-firebase/firestore + RNFB user.
  const isPaid = await subscriptionService.checkSubscription(
    user as unknown as Parameters<
      typeof subscriptionService.checkSubscription
    >[0]
  );
  // <<< INSERT T0 TODO COMMENT HERE (Task 2, AC2) — between checkSubscription and return >>>
  return {
    uid: user.uid,
    email: user.email ?? "",
    isPaid,
  };
}
// … authService.login/logout/listenToAuthChanges already on namespaced API (1.5 work) …
```

The TODO comment MUST be inserted at the marked spot (after line 17's `)`, before line 18's `return {`). Story 2.3 will replace `<<< INSERT T0 TODO >>>` with the actual `analytics.emit("T0", { elapsed_seconds: ..., t0_at: new Date().toISOString() })` call. **Do not** add the emit yourself — it requires the wrapper that doesn't exist yet.

#### `apps/mobile/src/features/auth/googleSignInService.ts` (111 lines) — READ-ONLY (verify, do not edit)

Already on namespaced API per 1.5 (`googleSignInService.ts:41-42`):
```ts
const credential = auth.GoogleAuthProvider.credential(idToken);
const firebaseCredential = await auth().signInWithCredential(credential);
```
Plus the `extractIdToken` v12/v13 dual-shape handling (lines 70–72) — independent of the auth migration; do not touch.

#### `apps/mobile/src/features/auth/subscriptionService.ts` (65 lines) — READ-ONLY (verify cross-SDK seam unmoved)

Still imports `{ type User } from "firebase/auth"` (line 2) and `checkSubscription(user: User)` (line 29). The `user as unknown as ...` cast in `authService.ts:14-16` exists precisely to bridge this. **STORY 1.7 SCOPE** — do not touch in 1.6.

#### `apps/mobile/src/features/auth/firebaseConfig.ts` (26 lines) — READ-ONLY (verify 1.5's `app`-only export)

Post-1.5: only `export { app }`. The `auth` export is gone (1.5 AC0b Option A). The `firebase/app` `initializeApp`+`getApps`+`getApp` shim is RETAINED for the Firestore consumers (subscriptionService/detectionConfigService) — removed in Story 1.8.

#### `apps/mobile/src/features/auth/useAuthStore.ts` (73 lines) — READ-ONLY (unchanged across the whole 1.4–1.9 migration; MMKV+Zustand)

Pure store; no Firebase coupling. Reused as the assertion surface in AC3 tests (`useAuthStore.getState()` calls).

### The cross-SDK seam: why it stays in 1.6 and what removes it in 1.7

`authService.ts:13-17`:
```ts
const isPaid = await subscriptionService.checkSubscription(
  user as unknown as Parameters<
    typeof subscriptionService.checkSubscription
  >[0]
);
```

- **Why it exists:** `mapFirebaseUser` receives `FirebaseAuthTypes.User` (RNFB); `subscriptionService.checkSubscription` types its param as `User` from `firebase/auth` (JS SDK); the two types are structurally compatible **for `.uid` only** but TypeScript sees them as distinct nominal types.
- **Why it's safe:** `subscriptionService.checkSubscription` reads only `user.uid` (`subscriptionService.ts:31`); both `User` types have `uid`. The cast is a type-system bridge, not a runtime hack.
- **Why 1.6 doesn't remove it:** removing the cast requires retyping `subscriptionService.checkSubscription(user: FirebaseAuthTypes.User)`, which requires touching `subscriptionService.ts` — that's Story 1.7's scope (AC7's "Firestore consumers untouched" + AC6 specifically forbid touching it).
- **What removes it in 1.7:** Story 1.7 migrates `subscriptionService` to `@react-native-firebase/firestore`; the param retypes to `FirebaseAuthTypes.User`; the cast in `authService.ts:13-17` becomes unnecessary and is deleted as part of 1.7's diff.

### Jest mock pattern — the precedent + the pitfall

**Precedent (the only firebase-mocking test today):** `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts:1-15` shows the project's accepted shape:
```ts
const mockGetDoc = jest.fn();
jest.mock("firebase/firestore", () => ({
  getFirestore: jest.fn(() => ({})),
  doc: jest.fn((_db: unknown, path: string) => ({ path })),
  getDoc: (...args: unknown[]) => mockGetDoc(...args),
}));
jest.mock("../../auth/firebaseConfig", () => ({ app: {} }));
import { ... } from "../detectionConfigService";
```
- Inline mocks at file top.
- The mock fns are **declared at module scope** (NOT inside the factory) so test bodies can re-arm them with `.mockResolvedValueOnce(...)`. This works because `jest.mock` is hoisted ABOVE the `const mockGetDoc = ...` declaration, but the factory body uses the variable through the `getDoc: (...args) => mockGetDoc(...args)` thunk — the thunk is invoked LAZILY at test-run time, by which point `mockGetDoc` is defined. Pattern is brittle but well-established here; reuse it for `@react-native-firebase/auth`.

**Pitfall — the namespaced-API singleton shape:**
- RNFB's `auth()` is a **callable that returns a singleton instance** + has STATIC properties (`auth.GoogleAuthProvider`). The TypeScript surface is `auth: ((...) => FirebaseAuthTypes.Module) & { GoogleAuthProvider: ... }`.
- Naive mock `jest.mock("@react-native-firebase/auth", () => ({ default: { signInWithEmailAndPassword } }))` does NOT match — the module's default export is the callable, not an object.
- Use the **callable-singleton** shape per Task 3's example. Validate with one quick `console.log(auth())` in a scratch test if shape ambiguity persists.

**Jest preset (existing):** `jest-expo` per `apps/mobile/package.json:32-38` (inline jest config: `preset: jest-expo`, `transformIgnorePatterns` allow-lists `firebase|@firebase`). **No `setupFiles` / `moduleNameMapper`** — do NOT add either; inline mocks per-file is the established pattern.

### Library / version reality (carried from 1.5)

- `@react-native-firebase/{app,auth,firestore}@^24.1.0` (resolved 24.x; namespaced API with deprecation warnings — accepted, do NOT migrate to modular).
- `firebase ^12.8.0` (resolved 12.12.1 app-direct + 12.14.0 RNFB-transitive; flagged from 1.4 — not 1.6's problem to fix).
- `@react-native-firebase/auth` v24 exports a TypeScript namespace `FirebaseAuthTypes` with the `User` interface; the import shape `import auth, { type FirebaseAuthTypes } from "@react-native-firebase/auth"` is what `authService.ts:1` already uses.
- `@react-native-google-signin/google-signin ^14.0.0` — Google sign-in side; unchanged in 1.6 (only the mock surface in AC3 needs to know `auth.GoogleAuthProvider.credential` exists IF a sibling googleSignInService.test.ts is added — but it isn't in this story).
- `metro.config.js` / `babel.config.js`: **no change** (RNFB v24 autolinked, established by 1.4).

### Project Structure Notes

- **Output (NEW):** `apps/mobile/src/features/auth/__tests__/authService.test.ts` (NEW; the `__tests__` dir is also new under `features/auth/`).
- **Touched (1-line comment):** `apps/mobile/src/features/auth/authService.ts` (T0 TODO comment insertion only — Task 2).
- **Untouched (verify byte-identical to `main`):** `googleSignInService.ts`, `subscriptionService.ts`, `firebaseConfig.ts`, `useAuthStore.ts`, `App.tsx`, `package.json`, `detectionConfigService.test.ts`.
- **Admin:** `_bmad-output/sprint-status.yaml` (`1-6` flips backlog → ready-for-dev → in-progress → review), this story file.
- No modifications outside `apps/mobile/src/features/auth/` (plus the sprint-status admin file + this story file).

### GIT NOTE — branch reality vs. precedent

- **Precedent (1.1/1.2/1.4/1.5):** each story used its own branch `story-1-X-…` off `main`, single commit, local `git merge --no-ff` because `gh` is unauthenticatable non-interactively in the remote-exec env.
- **This session's reality:** the remote-exec session was started on branch `claude/relaxed-mayer-8r3f41` (off `main` after `262e43c` 1.5 merge). Per the session's hard branch directive ("DEVELOP all your changes on the designated branch above … NEVER push to a different branch without explicit permission"), Task 7 commits/pushes 1.6 on **`claude/relaxed-mayer-8r3f41`** — NOT a new `story-1-6-*` branch. Stephane reviews + merges via PR (if desired) or local `--no-ff` once it lands.

### Tests (current reality, will be updated by this story)

- **`apps/mobile/src/features/auth/__tests__/`** — **does not exist yet** (the epics' "existing jest tests at this path" is aspirational per 1.5 Dev Notes; 1.6 creates it).
- **Existing firebase-mocking tests (1 file):** `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts` — mocks `firebase/firestore` + `../../auth/firebaseConfig` (`app:{}` only; `auth` already dropped by 1.5). DO NOT touch in 1.6.
- **Existing auth-area tests (2 files in `apps/mobile/src/__tests__/`):**
  - `formatAuthError.test.ts` — duplicates the `formatAuthError` mapping (function-not-exported workaround); firebase-free. Untouched.
  - `useAuthStore.test.ts` — exercises the real Zustand+MMKV store. Firebase-free. Untouched.
- **Jest config:** inline in `apps/mobile/package.json` — `preset: jest-expo`, `transformIgnorePatterns` allow-lists `firebase|@firebase`. No `setupFiles` / `moduleNameMapper`. Mock convention: inline `jest.mock(...)` at file top.

### Pre-existing risks NOT changed by this story (don't get nerd-sniped)

- **Two physical `firebase` copies under hoisting** (1.4 finding; deferred-work.md:29) — out of scope.
- **iOS Firebase config / App Check / firestore.rules deploy** (1.4 findings; deferred-work.md:27-30) — out of scope.
- **`@react-native-async-storage/async-storage` may be unused-by-auth** (1.5 finding; deferred-work.md:129-130) — out of scope; do NOT prune without tree-wide grep.
- **Cross-SDK seam cast** — STAYS (Story 1.7 owns its removal; AC6 here forbids touching it).

### References

- [Source: epics-and-stories.md:851-871] — Story 1.6 source-of-truth ACs + tests + dependency on 1.5.
- [Source: epics-and-stories.md:831-849] — Story 1.5 (3.B) — the story whose Option A pre-empted (a)–(d).
- [Source: epics-and-stories.md:1218-1247] — Story 2.3 — the eventual owner of the T0 emit (payload contract for the TODO marker text).
- [Source: epics-and-stories.md:873-891] — Story 1.7 (3.D, subscriptionService) — the boundary AC6 enforces; the seam-cast destination.
- [Source: architecture.md:624-645] — Brownfield Item 5 6-story sequence; Story 3.C scope.
- [Source: architecture.md:1097-1100] — Mobile→Firebase Auth contract [LOCKED]: post-migration `@react-native-firebase/auth`; persistence automatic.
- [Source: architecture.md:1459-1464] — source-tree: `apps/mobile/src/features/auth/__tests__/` is the architecture-anchored path for `authService.test.ts`.
- [Source: implementation-artifacts/1-5-firebase-v12-rn-auth-migration-migrate-firebase-config.md] — 1.5 record: Option-A call-site pull-forward (Tasks 2–4), the cross-SDK seam cast rationale, the 114-baseline jest reality, the "no `__tests__/auth/` dir yet" finding (line 154).
- [Source: implementation-artifacts/deferred-work.md:121-130] — 1.5 deferrals inherited: device smoke (Epic-1-end), cross-SDK seam (1.7), async-storage-prune (later).
- [Source: apps/mobile/src/features/auth/authService.ts:1-75] — current file (READ + 1-line TODO comment edit).
- [Source: apps/mobile/src/features/auth/googleSignInService.ts:1-111] — current file (READ-ONLY verify).
- [Source: apps/mobile/src/features/auth/subscriptionService.ts:1-65] — current file (READ-ONLY; seam destination).
- [Source: apps/mobile/src/features/auth/firebaseConfig.ts:1-26] — current file (READ-ONLY; 1.5's `app`-only export).
- [Source: apps/mobile/src/features/auth/useAuthStore.ts:1-73] — current file (READ-ONLY; mock target for AC3).
- [Source: apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts:1-15] — the only existing firebase-mocking test; **pattern reference** for AC3's inline-mock shape.
- [Source: apps/mobile/src/__tests__/useAuthStore.test.ts] — the existing useAuthStore test; cross-reference for `beforeEach` reset pattern (1.6 uses jest.fn() resets instead of real store state).
- [Source: apps/mobile/package.json:32-38] — inline jest config (`preset: jest-expo`).
- [Source: memory/feedback_ac_checkbox_tighten.md] — AC checkbox-tighten convention.
- [Source: memory/feedback_two_pr_docs_execution.md] — Two-PR delivery pattern.
- [Source: memory/feedback_batch_manual_checks_epic_end.md] — Batch manual checks at Epic-1-end (AC8 disposition).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia / bmad-dev-story), 2026-06-12.

### Debug Log References

- Pre-flight baseline (before any 1.6 edit): `pnpm --filter mobile typecheck` = **0 errors**; `pnpm --filter mobile test` = **114 passed, 15 suites**. `git diff origin/main -- apps/mobile/src/features/auth/{authService,googleSignInService,subscriptionService,firebaseConfig}.ts apps/mobile/App.tsx` = **0 lines** (AC1/AC6/AC7 byte-identical baseline confirmed).
- Post-implementation: `pnpm --filter mobile typecheck` = **0 errors**; `pnpm --filter mobile test` = **124 passed, 16 suites** (10 new tests in `authService.test.ts`).
- `git diff origin/main --stat` (final): `_bmad-output/sprint-status.yaml` (admin), `apps/mobile/src/features/auth/authService.ts` (+5 lines TODO comment), `apps/mobile/src/features/auth/__tests__/authService.test.ts` (NEW), `_bmad-output/implementation-artifacts/1-6-…md` (NEW). No other apps/mobile/ files changed.

### Completion Notes List

**AC0 verdicts (Amelia, recommended defaults — no Stephane override):** (0a) **A** — scope-reconciliation + jest-coverage close (verify 1.5 Option A's call-site work, add T0 TODO marker, write the first jest test file). (0b) **A** — inline `jest.mock("@react-native-firebase/auth", () => ({...}))` per project precedent (`detectionConfigService.test.ts:1-15`).

**T0 TODO comment text (`authService.ts:18-22`):**
```ts
// TODO(Story 2.3 — Epic 2 telemetry wrapper): emit T0 here when mapFirebaseUser
// confirms isPaid === true (first paid auth-state-change in session). Payload
// contract per epics-and-stories.md:1218-1247: { elapsed_seconds, t0_at, t1_path? }.
// NO frame/audio data (PRIV-001/002). Story 2.2 lands the analytics wrapper;
// Story 2.3 replaces this comment with the emit call.
```

**TWO MOCK PATTERN PITFALLS encountered + fixed (worth recording for Stories 1.7/1.8 which will write similar `@react-native-firebase/firestore` mocks):**

1. **Hoist-ordering bug** — `jest.mock("@react-native-firebase/auth", () => ({ default: mockAuthFn }))` with a DIRECT reference to `mockAuthFn` returns `{ default: undefined }`. Root cause: babel-plugin-jest-hoist moves `jest.mock(...)` calls above the file's `import`s; Babel's ES-module compilation hoists `import` → `require()` ABOVE the module-scope `const mockAuthFn = jest.fn(...)` declarations. So when the factory runs (during the hoisted `require("../authService")` which in turn `require()`s the auth module), `mockAuthFn` is `undefined`. **Fix:** wrap every factory reference in a lazy thunk — `function lazyAuth(...args) { return mockAuthFn(...args) }` — so the deref happens at CALL time (after all consts have been assigned). Precedent: `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts:9` — `getDoc: (...args) => mockGetDoc(...args)`.

2. **`mockResolvedValueOnce` queue leak across tests** — jest 29's `jest.clearAllMocks()` only resets `.mock.calls/.instances/.contexts/.results`; it does NOT clear queued `mockResolvedValueOnce`/`mockReturnValueOnce` entries. Effect: a `Once` queued by test N but not consumed (because test N took an exception branch) was consumed by test N+1, producing wrong-data results. **Fix:** use `jest.resetAllMocks()` (which DOES clear queues + impl) + re-arm `mockAuthFn.mockImplementation(() => mockAuthInstance)` in `beforeEach`. (The thunk pattern from pitfall 1 means `auth()` always resolves to `mockAuthFn`'s current impl, so re-arming via `mockImplementation` correctly takes effect.)

**SCOPE NOTE — googleSignInService.test.ts NOT added.** Per the story's "IS NOT" list, `googleSignInService.test.ts` is explicitly out of scope (only `authService.test.ts` is mandated by epic AC f). The `auth.GoogleAuthProvider.credential` static is mocked in the factory (lazy thunk on `lazyAuth.GoogleAuthProvider.credential`) so a future `googleSignInService.test.ts` story can reuse the same mock shape without re-discovering the hoist/queue pitfalls.

**Cross-SDK seam — preserved verbatim.** `authService.ts:13-17` cast and `subscriptionService.ts:2,29` `User` typing both unchanged (Story 1.7 still owns the removal). The TODO insertion lives at lines 18–22, AFTER the cast block. `git diff origin/main -- apps/mobile/src/features/auth/subscriptionService.ts` = 0 lines.

**Deferred (Epic-1-end manual pass + post-merge):** AC8 device login smoke (email/password + Google sign-in + cold-restart persistence + bypass branch) → batched to the Epic-1-end manual pass per [[feedback_batch_manual_checks_epic_end]] + 1.5 AC2/AC3 precedent (auth runs on native modules; not unit-testable). AC9 `review → done` + AC10 PR/merge → post-merge follow-up per [[feedback_two_pr_docs_execution]].

### File List

- `apps/mobile/src/features/auth/authService.ts` — **modified** (+5 lines: T0 TODO comment at lines 18–22 in `mapFirebaseUser`, between the `checkSubscription` call and the `return` object).
- `apps/mobile/src/features/auth/__tests__/authService.test.ts` — **NEW** (10 test cases; first `@react-native-firebase/auth` jest mock in the codebase; lazy-thunk factory + `jest.Mock` typing).
- `_bmad-output/sprint-status.yaml` — **admin** (`1-6` `backlog → ready-for-dev → in-progress → review`; added `last_updated` line).
- `_bmad-output/implementation-artifacts/1-6-firebase-v12-rn-auth-migration-migrate-auth-service.md` — **this story file**.

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-06-12 | Stephane (create-story, Amelia) | Story 3.C created; `backlog → ready-for-dev`. AC0 scope-reconciliation decision documented (1.5 Option A pre-empted call-site work; 1.6 closes (e) T0 TODO marker + (f) jest scaffolding + (g) deferred smoke). Verdicts pending dev kickoff. |
| 2026-06-12 | Stephane (dev-story, Amelia / opus-4-7) | Implemented Tasks 1–5, 7: AC0 verdicts (0a=A, 0b=A); T0 TODO comment inserted at `authService.ts:18-22`; `apps/mobile/src/features/auth/__tests__/authService.test.ts` created (10 tests; first `@react-native-firebase/auth` mock in the codebase; lazy-thunk factory pattern). Gates green: typecheck **0**, jest **124/124** 16 suites (was 114/15 baseline). Two mock pitfalls discovered + documented (hoist-ordering bug → lazy thunks; jest 29 `clearAllMocks` doesn't reset `Once` queues → switched to `resetAllMocks` + re-arm impl). AC1/AC6/AC7 byte-identical-to-`origin/main` baseline confirmed before any edit. Status `ready-for-dev → in-progress → review`; sprint-status `1-6` flipped to `review`. Task 6 device smoke DEFERRED to Epic-1-end manual pass (per 1.5 AC2/AC3 precedent); AC8 held `[ ]`. AC9/AC10 review→done flips held for post-merge follow-up. Committed on branch `claude/relaxed-mayer-8r3f41` (per session directive — not the 1.1/1.2/1.4/1.5 `story-1-X-*` precedent). |
