# Story 1.7: Firebase v12 RN Auth Migration — Migrate subscriptionService.ts (Story 3.D)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane**,
I want **`apps/mobile/src/features/auth/subscriptionService.ts` rewritten to read `users/{uid}` via `@react-native-firebase/firestore` (native module) instead of the `firebase/firestore` JS SDK**,
so that **all entitlement reads (`status`, `current_period_end`) come from the native module — closing the BF-3 migration's load-bearing Firestore consumer and unblocking the six-state entitlement machine (`deriveEntitlementState`) in Epic 3.**

## Context & Position in BF-3 Sequence

This is **Story 3.D** in the architecture-bound Firebase v12 RN migration sequence (V1-blocking):
3.A deps+prebuild (1.4 ✅ done) → 3.B firebaseConfig (1.5 ✅ merged) → 3.C authService (1.6 ✅ merged, at `review`) → **3.D subscriptionService (this story)** → 3.E detectionConfigService (1.8) → 3.F E2E manual (1.9).

`subscriptionService.ts` is one of the **last two JS-SDK Firestore consumers**. After this story only `detectionConfigService.ts` remains on `firebase/firestore`; Story 1.8 migrates it and removes the transitional `app` shim from `firebaseConfig.ts`. **Do NOT remove the `app` export or the `firebase/app` init from `firebaseConfig.ts` in this story** — `detectionConfigService.ts` still imports it (`apps/mobile/src/features/video-processing/detectionConfigService.ts:26`). [Source: firebaseConfig.ts:10-13; epics-and-stories.md:893-908]

Dependency **Story 1.6 is satisfied** (merged to main: `c3601b7`/`010d153`; authService now on RNFB auth). [Source: sprint-status.yaml:84]

## Acceptance Criteria

1. **Firestore read migrated.** `getDoc(doc(firestore, "users", user.uid))` → `firestore().collection("users").doc(user.uid).get()` in BOTH `checkSubscription` and the `startPeriodicRevalidation` timer callback. No `firebase/firestore` import remains in `subscriptionService.ts`. [Source: architecture.md:632; epics:881]
2. **`isSubscriptionPaid` semantics preserved (defense-in-depth, Decision #9).** Still treats `status ∈ {active, trialing}` AND `current_period_end > now` as paid; everything else as not-paid. The Stripe-driven doc shape at `users/{uid}` is unchanged. [Source: subscriptionService.ts:13-25; architecture.md:352-356; epics:882]
3. **Periodic re-validation preserved.** `startPeriodicRevalidation` / `stopPeriodicRevalidation` keep the 60-min (`REVALIDATION_INTERVAL_MS`) interval and the same `setUser({...user, isPaid})` on-change behavior. [Source: subscriptionService.ts:42-67; architecture.md:774, 1100; epics:883]
4. **Network-failure fallback preserved (`mobile-AUTH-004`, 30-day offline-grace).** A failed Firestore read in `checkSubscription` falls back to `useAuthStore.getState().user?.isPaid ?? false` (does NOT throw, does NOT log the user out). The revalidation timer swallows its own errors (logs, leaves state unchanged). [Source: subscriptionService.ts:33-38; architecture.md:776, 1169; epics:884]
5. **Six-state regression scaffold added.** New file `apps/mobile/src/features/auth/__tests__/deriveEntitlementState.test.ts` with one `describe` block per entitlement state: `paid` / `lapsed` / `offline-grace ≤30d` / `payment-failed` / `multi-device` / `signed-out`. A `deriveEntitlementState` **stub** is exported from `subscriptionService.ts` so the scaffold compiles and imports resolve; **full implementation + filled assertions land in Story 3.1** — assertions here are `it.todo(...)` (or `describe`-level `.todo`), not real expectations. [Source: epics:885-887; architecture.md:793-796, 1454-1464; AR-11 epics:325]
6. **Cross-SDK seam cast removed.** With `checkSubscription`'s param retyped to `FirebaseAuthTypes.User`, delete the transitional `as unknown as Parameters<...>[0]` cast in `authService.ts:mapFirebaseUser` (and its explanatory comment block at `authService.ts:8-17`); pass the RNFB user directly. [Source: deferred-work.md:128; authService.ts:8-17]
7. **`subscriptionService.test.ts` created.** New jest test file at `apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts` mocking `@react-native-firebase/firestore` (no live network), covering: paid (active+future period), trialing+future, not-paid (canceled / past period / missing doc), missing/non-Timestamp `current_period_end`, the network-failure → cached-`isPaid` fallback, and the revalidation `setUser`-on-change path. [Source: epics:887]
8. **Gates green (binding).** `pnpm --filter mobile typecheck` → **0 errors** (0 new vs the current 0 baseline). `pnpm --filter mobile test` (jest) → all suites green, **no regressions** (current baseline 124 tests / 16 suites; this story adds the two new files). [Source: 1.6 dev notes — 124/124, 16 suites]

> AC checkboxes per `[[feedback_ac_checkbox_tighten]]`: hold `[ ]` until verified.

## Tasks / Subtasks

- [x] **Task 1 — Migrate imports & module init (AC: 1, 2)**
  - [x] Replace `import { getFirestore, doc, getDoc, Timestamp } from "firebase/firestore"` with `import firestore, { FirebaseFirestoreTypes } from "@react-native-firebase/firestore"`.
  - [x] Replace `import { type User } from "firebase/auth"` with `import { type FirebaseAuthTypes } from "@react-native-firebase/auth"`.
  - [x] Remove `import { app } from "./firebaseConfig"` and the module-scope `const firestore = getFirestore(app)` (the RNFB `firestore()` singleton replaces it — pick a name that doesn't shadow the imported `firestore`; the default import IS the factory, call `firestore()`).
  - [x] Keep `import { useAuthStore } from "./useAuthStore"` and `REVALIDATION_INTERVAL_MS`, `PAID_STATUSES`, `revalidationTimer` unchanged.
- [x] **Task 2 — Migrate the two reads (AC: 1, 3, 4)**
  - [x] `checkSubscription`: `const userDoc = await firestore().collection("users").doc(user.uid).get();`
  - [x] Revalidation timer: same `firestore().collection("users").doc(user.uid).get()` call.
  - [x] Resolve the doc-existence check — see **CRITICAL GOTCHA: `exists` API** in Dev Notes. Verify against the installed type def and let `typecheck` be the gate. **VERDICT: `exists()` is a METHOD in RNFB v24.1.0** (`namespaced.d.ts:500` `exists(): boolean`, `FirestoreDocumentSnapshot.ts:87`) — same shape as the JS SDK; kept `userDoc.exists()`. typecheck 0 confirms.
  - [x] Retype `checkSubscription(user: FirebaseAuthTypes.User)`.
- [x] **Task 3 — Migrate `isSubscriptionPaid` Timestamp guard (AC: 2)**
  - [x] Replace `periodEnd instanceof Timestamp` — used the **preferred** duck-typed guard (`toMillis` is a function → call it; compare `> Date.now()`). Comment added explaining why not `instanceof`.
- [x] **Task 4 — Remove the seam cast in authService.ts (AC: 6)**
  - [x] In `mapFirebaseUser`, change `await subscriptionService.checkSubscription(user as unknown as Parameters<...>[0])` to `await subscriptionService.checkSubscription(user)`.
  - [x] Delete the now-stale 8-line "Cross-SDK seam (transitional)" comment block (`authService.ts:8-17`). Kept the `TODO(Story 2.3 …)` T0-telemetry comment intact.
  - [x] Confirm `authService.test.ts` still passes unchanged (it mocks `../subscriptionService`, so this is type-level only).
- [x] **Task 5 — Add `deriveEntitlementState` stub (AC: 5)**
  - [x] Export a typed stub from `subscriptionService.ts` (signature + return union; throws a documented placeholder). `EntitlementState` union declared; stub comment added.
- [x] **Task 6 — Scaffold `deriveEntitlementState.test.ts` (AC: 5)**
  - [x] One `describe` per state (`paid`, `lapsed`, `offline-grace ≤30d`, `payment-failed`, `multi-device`, `signed-out`) with `it.todo("…")` placeholders mirroring the Gherkin in epics:1342-1374. No real assertions — Story 3.1 fills them. Imports the stub (and mocks the RNFB firestore module so the native module isn't loaded).
- [x] **Task 7 — Write `subscriptionService.test.ts` (AC: 7)**
  - [x] Mock `@react-native-firebase/firestore` per the RNFB lazy-thunk pattern (`firestore()` callable returning a `.collection().doc().get()` chain).
  - [x] Mock `../useAuthStore` (`getState` returning `{ user, setUser }`) the same way `authService.test.ts` mocks its store (`mock`-prefixed mutable user per babel-jest-hoist).
  - [x] Cover the AC-7 cases. Used fake timers for the `startPeriodicRevalidation` interval test; assert `stopPeriodicRevalidation` clears it.
- [x] **Task 8 — Gates (AC: 8)**
  - [x] `pnpm --filter mobile typecheck` → 0 errors.
  - [x] `pnpm --filter mobile test` → green, no regressions; 18 suites / 157 (147 passed + 10 todo), up from 16 / 133.
- [x] **Task 9 — Git delivery** — committed on branch `claude/eloquent-keller-pactbg` per this session's directive (NOT a new `story-1-7-*` branch — same remote-exec rule the 1.6 entry recorded; the create-story placeholder `claude/festive-hamilton-pp0jgv` was superseded by the session branch). Device-login smoke + any PR/merge bookkeeping follow the Epic-1-end batched manual pass per `[[feedback_batch_manual_checks_epic_end]]`.

## Dev Notes

### Current state of `subscriptionService.ts` (read before editing — 73 lines)

JS-SDK module today: `getFirestore(app)` at module scope; `checkSubscription(user: User)` does `getDoc(doc(firestore, "users", user.uid))` → `userDoc.exists()` → `isSubscriptionPaid(userDoc.data())`; `catch` falls back to `useAuthStore.getState().user?.isPaid ?? false`. `isSubscriptionPaid` gates on `PAID_STATUSES = {active, trialing}` AND `current_period_end instanceof Timestamp && periodEnd.toMillis() > Date.now()`. `startPeriodicRevalidation` runs a 60-min `setInterval` re-reading the same doc and calling `setUser({...user, isPaid})` only when `isPaid` changed. **Preserve every one of these behaviors** — only the Firebase API surface changes. [Source: subscriptionService.ts:1-73]

### 🚨 CRITICAL GOTCHA #1 — RNFB `DocumentSnapshot.exists` (property vs method)

The JS SDK (`firebase/firestore` v9 modular) exposes `snapshot.exists()` as a **method**. `@react-native-firebase/firestore`'s namespaced-API `DocumentSnapshot` historically exposes **`snapshot.exists` as a boolean property** (no parens). These are **not interchangeable** — calling a boolean is a runtime/type error, and reading a method reference as a boolean is always truthy.

`node_modules` is NOT installed in this container, so resolve at dev time, do not guess:
1. `grep -n "exists" node_modules/@react-native-firebase/firestore/lib/index.d.ts` (and `lib/modular/*.d.ts`). If it's `readonly exists: boolean` → use `if (!userDoc.exists) return false;`. If it's `exists(): boolean` → use `if (!userDoc.exists()) return false;`.
2. **`typecheck` is the binding gate** — a wrong choice surfaces as a TS error (calling a boolean / boolean-vs-function). AC8 (0 errors) cannot pass if this is wrong, so trust the compiler over memory. The migrated `detectionConfigService.ts` in Story 1.8 will hit the identical decision — record the verdict in your Completion Notes so 1.8 inherits it.

### 🚨 CRITICAL GOTCHA #2 — `Timestamp instanceof` across the SDK boundary

`current_period_end instanceof Timestamp` currently binds to the **JS-SDK `Timestamp` class**, which is going away with the `firebase/firestore` import (flagged for this story back in Story 1.5: "`subscriptionService.ts:22 instanceof Timestamp` is JS-SDK-class-bound"). The native module returns an RNFB `FirebaseFirestoreTypes.Timestamp` — a **different class object**, so `instanceof` the old class would be permanently `false` (silent entitlement-paid → false regression). Two valid fixes:
- **Preferred (robust to module-identity issues):** duck-type — `const ms = (periodEnd as FirebaseFirestoreTypes.Timestamp)?.toMillis?.(); return typeof ms === "number" && ms > Date.now();`. Survives any `instanceof` cross-realm fragility and is trivially unit-testable with a plain `{ toMillis: () => n }` mock.
- **Acceptable:** `periodEnd instanceof firestore.Timestamp` (the static `Timestamp` on the default `firestore` export). Verify the static exists in the installed type def first.
Add a one-line comment explaining the change so a future reader doesn't "restore" the JS-SDK `instanceof`.

### RNFB Firestore mock pattern for `subscriptionService.test.ts`

Reuse the hoist-safe **lazy-thunk** pattern proven in `authService.test.ts` and `detectionConfigService.test.ts` (Babel hoists `import`→`require` above module-scope `const`s, so factories must defer every mock deref to call time). `@react-native-firebase/firestore`'s default export is a **callable singleton with statics** — same shape problem as `auth` in 1.6. Sketch:

```ts
const mockGet = jest.fn();
const mockDoc = jest.fn(() => ({ get: (...a: unknown[]) => mockGet(...a) }));
const mockCollection = jest.fn(() => ({ doc: (...a: unknown[]) => mockDoc(...a) }));
const mockFirestoreFn: jest.Mock = jest.fn(() => ({ collection: (...a: unknown[]) => mockCollection(...a) }));

jest.mock("@react-native-firebase/firestore", () => {
  function lazyFirestore(...args: unknown[]): unknown { return mockFirestoreFn(...args); }
  // If the prod code uses `firestore.Timestamp`, attach a static here.
  return { __esModule: true, default: lazyFirestore };
});
```
- Build snapshot fixtures as `{ exists: true, data: () => ({...}) }` **or** `{ exists: () => true, data: () => ({...}) }` to match whichever Gotcha-#1 form you adopt — keep the fixture shape consistent with prod.
- For Timestamp fields use a plain `{ toMillis: () => <ms> }` object (matches the duck-typed guard; no real Timestamp class needed).
- `beforeEach`: `jest.resetAllMocks()` then re-arm `mockFirestoreFn.mockImplementation(...)` / the chain (jest 29's `clearAllMocks` leaves `mockResolvedValueOnce` queues — use `resetAllMocks` + re-arm, exactly the leak 1.6 documented).
- Mock `../useAuthStore` with `getState: () => ({ user, setUser: mockSetUser })`.

### `deriveEntitlementState` contract (stub now, fill in Story 3.1)

Pure function, single source of truth for the six-state machine (AR-11). Declare and export the type so 3.1 and the UI (3.2) can import it:

```ts
export type EntitlementState =
  | "paid"
  | "lapsed"
  | "offline-grace ≤30d"
  | "payment-failed"
  | "signed-out";
// multi-device is NOT a distinct state — it resolves to "paid" (entitlement is
// per-user, not per-device; not enforced per PRD). The scaffold keeps a
// `multi-device` describe block that asserts the "paid" outcome.

export function deriveEntitlementState(
  userDoc: Record<string, unknown> | null | undefined,
  cacheMeta: { isPaid: boolean; cachedAt: number | null; isAuthenticated: boolean },
): EntitlementState {
  // Story 3.1 (AR-11) implements the full derivation; stub only so the 1.7
  // regression scaffold compiles. Do not rely on this return value yet.
  throw new Error("deriveEntitlementState not implemented until Story 3.1");
}
```
State rules (for the `it.todo` text only — do NOT implement here): paid = active/trialing & period>now; lapsed = canceled OR period<now OR past_due≥grace; offline-grace ≤30d = read failed & cached isPaid & cachedAt>now−30d; payment-failed = past_due & within `paymentFailedGracePeriodMs` (default 7d, `EXPO_PUBLIC_PAYMENT_FAILED_GRACE_MS`); signed-out = no token / read failed & cache stale(>30d). [Source: epics:1342-1374; architecture.md:776, 793-796; AR-11 epics:325]

> Signature note: epics/architecture write `deriveEntitlementState(userDoc, cacheMeta)` but do not pin `cacheMeta`'s exact field names. The shape above is derived from `useAuthStore` (`user.isPaid`, `cachedAt`, `isAuthenticated`) + architecture.md:776. Story 3.1 may refine it — that's fine; the stub exists to make imports resolve, not to freeze the API. Flag this as an open question for 3.1 (see Questions).

### Project structure (target — matches architecture source tree)

```
apps/mobile/src/features/auth/
  subscriptionService.ts          isSubscriptionPaid + deriveEntitlementState stub  [UPDATE]
  authService.ts                  remove seam cast                                  [UPDATE]
  firebaseConfig.ts               DO NOT TOUCH (app shim removed in 1.8)            [keep]
  __tests__/
    subscriptionService.test.ts   [NEW]
    deriveEntitlementState.test.ts one describe/state, it.todo                      [NEW]
    authService.test.ts           unchanged (passes as-is)                          [keep]
```
[Source: architecture.md:1454-1464]

### Regression guardrails (system must stay working end-to-end)

- `firebaseConfig.ts` `app` export + `firebase/app` init **stay** — `detectionConfigService.ts:26` still imports `app`. Removing it breaks detection-config reads. (1.8 owns that removal.) [Source: firebaseConfig.ts:10-13]
- `useAuthStore`, `mapFirebaseUser`'s call flow (`auth-state-change → checkSubscription → setUser`), and the `LoginScreen` are unaffected — `checkSubscription` keeps the same `(user) => Promise<boolean>` contract; only the param's static type changes. [Source: architecture.md:1203; authService.ts:18-32]
- `package.json` is **untouched** — `@react-native-firebase/firestore ^24.1.0` already present (added Story 1.4). No `expo prebuild` / native rebuild needed for this JS-only swap. [Source: package.json:21]
- `firebase ^12.8.0` stays in `package.json` until the last JS-SDK consumer (detectionConfigService) migrates in 1.8 — do not remove it here. [Source: package.json:34]

### Previous-story intelligence (1.5 / 1.6)

- **Mock pitfalls already paid for (reuse, don't re-discover):** (1) hoist-ordering — direct `default: mockFn` refs deref `undefined`; wrap in lazy thunks. (2) `clearAllMocks()` leaks `mockResolvedValueOnce` queues across tests in jest 29 → use `resetAllMocks()` + re-arm `mockImplementation` in `beforeEach`. [Source: 1-6 dev notes / authService.test.ts header]
- **Baseline to protect:** typecheck 0; jest 124/124 across 16 suites (114 + 10 from 1.6's authService.test.ts). Your two new files add suites; nothing should turn red. [Source: sprint-status.yaml:84]
- **Auth runs native, not unit-testable** — device-login smoke is consistently deferred to the Epic-1-end consolidated manual pass; this story's value is the static migration + jest coverage. [Source: 1.5/1.6 entries, `[[feedback_batch_manual_checks_epic_end]]`]
- **Latent bug, out of scope (don't fix here):** the `onAuthStateChanged` async callback in `authService.ts` has no try/catch — a `checkSubscription` rejection could become an unhandled rejection. Today `checkSubscription` swallows its own errors (so it stays latent), and AC4 keeps that swallow. Note it; fold into a future auth-error-hardening story. [Source: deferred-work.md:133]

### References

- [Source: _bmad-output/epics-and-stories.md#Story-1.7 (lines 873-891)] — ACs, test paths, dependency.
- [Source: _bmad-output/epics-and-stories.md#Story-3.1 (lines 1336-1382)] — deriveEntitlementState Gherkin per state (the scaffold mirrors these).
- [Source: _bmad-output/architecture.md:632] — exact read rewrite `firestore().collection('users').doc(uid).get()`.
- [Source: _bmad-output/architecture.md:638-641] — BF-3 sequence; 3.D = "load-bearing regression scope".
- [Source: _bmad-output/architecture.md:774-796, 1100, 1169] — periodic re-validation, offline-grace/signed-out fallback, deriveEntitlementState home.
- [Source: apps/mobile/src/features/auth/subscriptionService.ts] — file being migrated.
- [Source: apps/mobile/src/features/auth/authService.ts:8-17] — seam cast to remove.
- [Source: apps/mobile/src/features/auth/firebaseConfig.ts:10-13] — `app` shim (do NOT remove).
- [Source: apps/mobile/src/features/auth/__tests__/authService.test.ts] — RNFB lazy-thunk mock + resetAllMocks pattern to reuse.
- [Source: _bmad-output/implementation-artifacts/deferred-work.md:128, 133] — seam-cast removal owned by 1.7; auth-listener latent rejection (out of scope).

## Open Questions (for dev / Story 3.1)

1. **`exists` API form** — resolve against the installed `@react-native-firebase/firestore@24.1.0` type def (Gotcha #1). Record the verdict for Story 1.8.
2. **`cacheMeta` shape** — the stub's `{ isPaid, cachedAt, isAuthenticated }` is inferred (epics/arch leave it loose). Story 3.1 may refine; the 1.7 stub deliberately doesn't freeze it.

## Dev Agent Record

### Agent Model Used

Amelia (dev-story) — claude-opus-4-8, 2026-06-12.

### Debug Log References

- `node_modules` was not present in the container → ran `pnpm install --frozen-lockfile` (21.9s) to make the gates runnable.
- Baseline before changes: `pnpm --filter mobile typecheck` = 0 errors; `pnpm --filter mobile test` = 16 suites / 133 tests (story header's "124/16" predated this checkout; actual baseline recorded here).
- Two false-starts on the new tests, both fixed:
  1. `babel-plugin-jest-hoist` rejected the `useAuthStore` mock factory closing over `storeUser` (variable not `mock`-prefixed) → renamed to `mockStoreUser`.
  2. The revalidation timer tests initially failed because **modern jest fake timers also fake `Date.now()`**: a `+1h` future Timestamp computed at module load was no longer `> Date.now()` after `advanceTimersByTime(1h)`, so `isSubscriptionPaid` flipped to false. Widened the fixture margins to ±100 days.
  3. `deriveEntitlementState.test.ts` imports the real `subscriptionService`, which top-level-imports the RNFB firestore native module → added a bare `jest.mock("@react-native-firebase/firestore")` to the scaffold so the native module isn't loaded.

### Completion Notes List

- **AC1** ✅ Both reads migrated to `firestore().collection("users").doc(user.uid).get()`; no `firebase/firestore` import remains in `subscriptionService.ts`.
- **AC2** ✅ `isSubscriptionPaid` unchanged in semantics: `status ∈ {active,trialing}` AND `current_period_end.toMillis() > now`. Doc shape untouched.
- **AC3** ✅ `startPeriodicRevalidation`/`stopPeriodicRevalidation` keep the 60-min interval and the `setUser({...user, isPaid})`-on-change behavior (test-covered with fake timers).
- **AC4** ✅ `checkSubscription` failure falls back to `useAuthStore.getState().user?.isPaid ?? false` (does not throw / log out); the revalidation timer swallows its own errors. Both paths test-covered.
- **AC5** ✅ `deriveEntitlementState` stub + `EntitlementState` union exported from `subscriptionService.ts`; `__tests__/deriveEntitlementState.test.ts` scaffold with one `describe`/state (6 blocks, 10 `it.todo`s; `multi-device` asserts the "paid" outcome). Assertions land in Story 3.1.
- **AC6** ✅ Removed the `as unknown as Parameters<...>[0]` seam cast and its 8-line comment block in `authService.ts:mapFirebaseUser`; the RNFB user passes directly now that the param is `FirebaseAuthTypes.User`. T0-telemetry TODO kept intact. `authService.test.ts` passes unchanged.
- **AC7** ✅ `__tests__/subscriptionService.test.ts` mocks `@react-native-firebase/firestore` (no live network), covering paid (active/trialing + future), not-paid (canceled / past period / missing doc / missing+non-Timestamp `current_period_end`), the network-failure→cached-`isPaid` fallback (with and without cache), and the revalidation `setUser`-on-change / no-change / error-swallow / `stop`-clears paths.
- **AC8** ✅ typecheck 0 errors; jest 18 suites / 157 tests (147 passed + 10 todo), 0 regressions (+2 suites, +24 tests vs the 16/133 baseline).
- **VERDICT for Story 1.8 (Gotcha #1):** in `@react-native-firebase/firestore@24.1.0`, `DocumentSnapshot.exists` is a **METHOD** (`exists(): boolean`), NOT a boolean property — verified against the installed type def (`dist/typescript/lib/types/namespaced.d.ts:500`, runtime `FirestoreDocumentSnapshot.ts:87`). Use `userDoc.exists()` (parens). 1.8's `detectionConfigService` migration inherits this.
- **Gotcha #2 resolution:** used the preferred duck-typed Timestamp guard (`toMillis` typeof-function check) rather than `instanceof firestore.Timestamp` — robust to cross-realm `instanceof` fragility and trivially mockable with `{ toMillis: () => n }`.
- **Untouched (regression guardrails honored):** `firebaseConfig.ts` (`app` shim stays — `detectionConfigService.ts:26` still imports it; 1.8 removes it), `package.json` (`@react-native-firebase/firestore` and `firebase` both stay). The `onAuthStateChanged` latent unhandled-rejection remains out of scope (AC4 keeps the error swallow).
- **Deferred:** device-login smoke (Epic-1-end consolidated manual pass); any PR/merge bookkeeping per `[[feedback_batch_manual_checks_epic_end]]`.

### File List

- `apps/mobile/src/features/auth/subscriptionService.ts` — MODIFIED (RNFB firestore migration; duck-typed Timestamp guard; `deriveEntitlementState` stub + `EntitlementState` union).
- `apps/mobile/src/features/auth/authService.ts` — MODIFIED (removed cross-SDK seam cast + comment block in `mapFirebaseUser`).
- `apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts` — NEW.
- `apps/mobile/src/features/auth/__tests__/deriveEntitlementState.test.ts` — NEW (six-state scaffold, `it.todo`).

### Change Log

- 2026-06-12 — Story 1.7 (Story 3.D) implemented: migrated `subscriptionService.ts` Firestore reads from the `firebase/firestore` JS SDK to `@react-native-firebase/firestore`; preserved `isSubscriptionPaid` semantics via a duck-typed Timestamp guard; preserved the 60-min revalidation and offline-grace fallback; removed the cross-SDK seam cast in `authService.ts`; added the `deriveEntitlementState` stub + six-state regression scaffold and a full `subscriptionService.test.ts`. Gates: typecheck 0; jest 18 suites / 157 (147 + 10 todo). Status → review.

## Review Findings

> BMad adversarial code review (2026-06-12, claude-opus-4-8). 3 layers: Blind Hunter + Edge Case Hunter + Acceptance Auditor. Acceptance Auditor: **8/8 ACs PASS** (AC8 gates asserted but unverifiable in-container — no `node_modules`). 2 patch, 5 defer, 9 dismissed as noise/by-design.

### Patch (actionable in this story's changed code)

- [x] [Review][Patch] Top-level `expect()` runs at jest collection time, not inside a test [`apps/mobile/src/features/auth/__tests__/deriveEntitlementState.test.ts:23`] — FIXED: wrapped in `describe("deriveEntitlementState — stub contract") → it("is exported as a function")` so it runs as a named test (jest now 158/18, +1 vs 157). (blind+edge)
- [x] [Review][Patch] Duck-typed Timestamp guard doesn't validate `toMillis()` return is a finite number [`apps/mobile/src/features/auth/subscriptionService.ts:26-29`] — FIXED: capture `const ms = toMillis.call(periodEnd)` and gate on `typeof ms === "number" && Number.isFinite(ms)` before `ms > Date.now()`, restoring the tightness lost vs the old `instanceof Timestamp` and rejecting NaN/non-number returns. typecheck 0; jest green. (blind+edge)

### Deferred (real but pre-existing — not introduced by this migration; structure unchanged from the JS-SDK original)

- [x] [Review][Defer] Cross-user cache contamination on the network-failure fallback [`subscriptionService.ts:47-48`] — deferred, pre-existing + **spec-pinned by AC4**. The `catch` returns `useAuthStore.getState().user?.isPaid ?? false` without comparing the cached user's `uid` to the user being checked; on a shared device / fast account switch while offline, user A could inherit user B's `isPaid`. AC4 explicitly mandates this exact fallback shape, and the correct home for uid-aware/offline-grace handling is the six-state machine in **Story 3.1** (`deriveEntitlementState`). Surface there.
- [x] [Review][Defer] Periodic revalidation timer not stopped on logout [`authService.ts:42-46` ↔ `subscriptionService.ts:75`] — deferred, pre-existing. `logout()` never calls `stopPeriodicRevalidation()`; the interval leaks for the process lifetime (bounded by the `if (!user) return` null-guard at line 56, so no active reads after logout). Fold into auth-error-hardening.
- [x] [Review][Defer] `this`-binding fragility in `startPeriodicRevalidation` [`subscriptionService.ts:53`] — deferred, pre-existing. `this.stopPeriodicRevalidation()` throws if the method is ever called detached (`const { startPeriodicRevalidation } = subscriptionService`). Prefer `subscriptionService.stopPeriodicRevalidation()`.
- [x] [Review][Defer] Stale-user read-modify-write across the revalidation `await` [`subscriptionService.ts:55-67`] — deferred, pre-existing. `user` is snapshotted before the awaited `get()`; if the user logs out / switches during the in-flight read, `setUser({ ...user, isPaid })` writes back the stale snapshot. Re-read `getState().user` (or recheck `uid`) before `setUser`.
- [x] [Review][Defer] No reentrancy guard on the revalidation interval [`subscriptionService.ts:54-72`] — deferred, pre-existing + theoretical at a 1-hour interval. If a `get()` ever exceeds the interval, overlapping async callbacks race on `setUser`. Add an in-flight flag if the interval is ever shortened.

### Dismissed (9 — noise / false positive / by-design)

- `mockGet` "never re-stubbed after `resetAllMocks`" (Blind, from summary only) — **false positive**: every read-path test arms `mockGet` via `mockResolvedValueOnce`/`mockRejectedValueOnce` (test:96-155); network-fail tests use genuine `mockRejectedValueOnce`, not an accidental `undefined.exists()` TypeError. Verified against the real file.
- `deriveEntitlementState` exported stub throws unconditionally — **by design**, AC5 mandates the stub + `throw` until Story 3.1.
- `EntitlementState` literal `"offline-grace ≤30d"` (space + Unicode `≤`) "fragile" — **by design**, the exact string is pinned in Dev Notes / architecture for Story 3.1.
- `firestore()` called per-method vs a cached singleton — **by design**, the RNFB default-instance factory is the intended pattern; functionally equivalent.
- `FirebaseFirestoreTypes` not imported via `import type` — type-only lint nit; typecheck is green and no project rule enforces it.
- Hand-counted `await Promise.resolve()` ×2 microtask flush "brittle" — Edge Hunter verified it reliably drains the single-`await` chain; tests pass. `advanceTimersByTimeAsync` is a nice-to-have, not a defect.
- "Other callers of `checkSubscription` may break on the retype" — only caller is `authService.mapFirebaseUser`, which passes `FirebaseAuthTypes.User`; typecheck 0 confirms.
- Unresolved `serverTimestamp()` read-back returns a client estimate — theoretical; the Stripe-written doc shape doesn't use pending server timestamps for `current_period_end`.
- Empty/undefined `user.uid` at `.doc(user.uid)` — upstream auth guarantees a non-empty uid; the seam is reached only post-authentication.
