# Story 1.7: Firebase v12 RN Auth Migration — Migrate subscriptionService.ts (Story 3.D)

Status: ready-for-dev

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

- [ ] **Task 1 — Migrate imports & module init (AC: 1, 2)**
  - [ ] Replace `import { getFirestore, doc, getDoc, Timestamp } from "firebase/firestore"` with `import firestore, { FirebaseFirestoreTypes } from "@react-native-firebase/firestore"`.
  - [ ] Replace `import { type User } from "firebase/auth"` with `import { type FirebaseAuthTypes } from "@react-native-firebase/auth"`.
  - [ ] Remove `import { app } from "./firebaseConfig"` and the module-scope `const firestore = getFirestore(app)` (the RNFB `firestore()` singleton replaces it — pick a name that doesn't shadow the imported `firestore`; the default import IS the factory, call `firestore()`).
  - [ ] Keep `import { useAuthStore } from "./useAuthStore"` and `REVALIDATION_INTERVAL_MS`, `PAID_STATUSES`, `revalidationTimer` unchanged.
- [ ] **Task 2 — Migrate the two reads (AC: 1, 3, 4)**
  - [ ] `checkSubscription`: `const userDoc = await firestore().collection("users").doc(user.uid).get();`
  - [ ] Revalidation timer: same `firestore().collection("users").doc(user.uid).get()` call.
  - [ ] Resolve the doc-existence check — see **CRITICAL GOTCHA: `exists` API** in Dev Notes. Verify against the installed type def and let `typecheck` be the gate.
  - [ ] Retype `checkSubscription(user: FirebaseAuthTypes.User)`.
- [ ] **Task 3 — Migrate `isSubscriptionPaid` Timestamp guard (AC: 2)**
  - [ ] Replace `periodEnd instanceof Timestamp` — see **CRITICAL GOTCHA: Timestamp `instanceof`** in Dev Notes. Preferred: structural/duck-typed guard `typeof (periodEnd as FirebaseFirestoreTypes.Timestamp)?.toMillis === "function"`; acceptable alt: `periodEnd instanceof firestore.Timestamp`. Preserve the `> Date.now()` comparison.
- [ ] **Task 4 — Remove the seam cast in authService.ts (AC: 6)**
  - [ ] In `mapFirebaseUser`, change `await subscriptionService.checkSubscription(user as unknown as Parameters<...>[0])` to `await subscriptionService.checkSubscription(user)`.
  - [ ] Delete the now-stale 8-line "Cross-SDK seam (transitional)" comment block (`authService.ts:8-17`). Keep the `TODO(Story 2.3 …)` T0-telemetry comment intact.
  - [ ] Confirm `authService.test.ts` still passes unchanged (it mocks `../subscriptionService`, so this is type-level only).
- [ ] **Task 5 — Add `deriveEntitlementState` stub (AC: 5)**
  - [ ] Export a typed stub from `subscriptionService.ts` (signature + return union; throws-not / returns a documented placeholder). See Dev Notes "deriveEntitlementState contract" for the exact signature, the six string literals, and the `EntitlementState` type to declare. Add a `// Story 3.1 (AR-11) implements; stub here only so the 1.7 scaffold compiles.` comment.
- [ ] **Task 6 — Scaffold `deriveEntitlementState.test.ts` (AC: 5)**
  - [ ] One `describe` per state (`paid`, `lapsed`, `offline-grace ≤30d`, `payment-failed`, `multi-device`, `signed-out`) with `it.todo("…")` placeholders mirroring the Gherkin in epics:1342-1374. Do NOT write real assertions — Story 3.1 fills them. Import the stub so the file type-checks.
- [ ] **Task 7 — Write `subscriptionService.test.ts` (AC: 7)**
  - [ ] Mock `@react-native-firebase/firestore` per the RNFB mock pattern in Dev Notes (lazy thunks; `firestore()` callable returning a `.collection().doc().get()` chain; static `firestore.Timestamp`).
  - [ ] Mock `../useAuthStore` (`getState` returning `{ user, setUser }`) the same way `authService.test.ts` mocks its store.
  - [ ] Cover the AC-7 cases. Use fake timers (`jest.useFakeTimers()`) for the `startPeriodicRevalidation` interval test; assert `stopPeriodicRevalidation` clears it.
- [ ] **Task 8 — Gates (AC: 8)**
  - [ ] `pnpm --filter mobile typecheck` → 0 errors.
  - [ ] `pnpm --filter mobile test` → green, no regressions; new suites counted.
- [ ] **Task 9 — Git delivery** — commit on branch `claude/festive-hamilton-pp0jgv` per session directive (NOT a new `story-1-7-*` branch — same remote-exec rule the 1.6 entry recorded). Device-login smoke + any PR/merge bookkeeping follow the Epic-1-end batched manual pass per `[[feedback_batch_manual_checks_epic_end]]`.

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

### Debug Log References

### Completion Notes List

### File List
