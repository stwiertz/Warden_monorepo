# Story 1.8: Firebase v12 RN Auth Migration — Migrate detectionConfigService.ts (Story 3.E)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane**,
I want **`apps/mobile/src/features/video-processing/detectionConfigService.ts` rewritten to read `detection_config/latest` via `@react-native-firebase/firestore` (native module) instead of the `firebase/firestore` JS SDK — AND the now-orphaned `firebase/app` shim (`firebaseConfig.ts`) + the `firebase` JS-SDK npm dependency removed**,
so that **the LAST JS-SDK Firestore consumer moves to the native module, the BF-3 migration's transitional `app` shim is retired, and the `firebase@^12.8.0` package leaves the bundle entirely — completing the code-side of the Firebase v12 RN migration so Story 1.9's E2E manual pass can sign off Sprint 3.**

## Context & Position in BF-3 Sequence

This is **Story 3.E** in the architecture-bound Firebase v12 RN migration sequence (V1-blocking):
3.A deps+prebuild (1.4 ✅ done) → 3.B firebaseConfig (1.5 ✅ done) → 3.C authService (1.6 ✅ done) → 3.D subscriptionService (1.7 ✅ done) → **3.E detectionConfigService (this story)** → 3.F E2E manual (1.9). [Source: epics-and-stories.md:308 (BF-3), 2988]

`detectionConfigService.ts` is the **last** `firebase/firestore` JS-SDK consumer in the mobile app. Story 1.7 (done, commit `a8c179c` + patches `141f6e3`) migrated `subscriptionService.ts` and explicitly left the `app` shim in place for this story:

> "After this story only `detectionConfigService.ts` remains on `firebase/firestore`; Story 1.8 migrates it and removes the transitional `app` shim from `firebaseConfig.ts`." [Source: 1-7 story §Context; sprint-status.yaml:88 "firebaseConfig `app` shim + `firebase` dep + package.json untouched (1.8 owns removal)"]

**This story owns three things 1.4–1.7 deliberately deferred:** (a) migrate `detectionConfigService.ts` reads to RNFB firestore, (b) delete the orphaned `firebaseConfig.ts` `app` shim, (c) drop `firebase@^12.8.0` from `apps/mobile/package.json`.

Dependency **Story 1.7 is satisfied** (merged to main: `a8c179c` feat + `141f6e3` code-review patches; `subscriptionService.ts` now on RNFB firestore, the cross-SDK seam cast removed). [Source: sprint-status.yaml:88]

## Acceptance Criteria

1. **Firestore read migrated.** In `fetchRemoteConfig()`, `getDoc(doc(getFirestore(app), DETECTION_CONFIG_DOC_PATH))` → `firestore().collection("detection_config").doc("latest").get()`. **No `firebase/firestore` import and no `import { app } from "../auth/firebaseConfig"` remain in `detectionConfigService.ts`.** [Source: detectionConfigService.ts:24-25, 104-107; epics:901; architecture.md BF-3]
2. **Three singleflight inflight gates preserved.** `inflightInitialFetch`, `inflightBackgroundRefresh`, `inflightForcedRefresh` keep their exact current semantics — concurrent callers share one Firestore round-trip + one cache write; each gate is nulled in its `finally`. No change to the gate logic; **only `fetchRemoteConfig`'s body changes.** [Source: detectionConfigService.ts:122-124, 140-227; epics:902]
3. **Schema validation + error-path semantics preserved.** `validateDetectionConfig` (Zod) still runs on `snap.data()`; an invalid payload still raises `MalformedRemoteConfigError`; a missing document or network failure still raises `OfflineFirstLaunchError` on the no-cache path; a present cache is still returned untouched on any fetch failure (stale-while-revalidate). **Bundled-asset fallback is OUT OF SCOPE — Story 1.13 (AR-4) implements the bundled `map_config.json` path; do NOT add it here.** [Source: detectionConfigService.ts:1-19, 104-120; epics:903; epics-and-stories.md:318 (AR-4), 1003-1022]
4. **`exists()` stays a METHOD.** Keep `snap.exists()` (call), not `snap.exists` (property). RNFB v24.1.0 `DocumentSnapshot.exists()` is a method — same shape as the JS SDK — verified and inherited from Story 1.7. [Source: subscriptionService.ts:48-49 comment; sprint-status.yaml:88 "RNFB v24.1.0 DocumentSnapshot.exists() is a METHOD … Story 1.8 inherits this verdict"]
5. **Orphaned `app` shim removed.** After AC1, `firebaseConfig.ts`'s `app` export has zero consumers (confirmed: only `detectionConfigService.ts` + its test mock import it; auth/googleSignInService import `auth` directly from `@react-native-firebase/auth`). **Delete `apps/mobile/src/features/auth/firebaseConfig.ts`** (removing the last `firebase/app` JS-SDK import). [Source: firebaseConfig.ts:1,10-26; grep confirms only 2 importers, both migrated away in this story]
6. **`firebase` JS-SDK dependency removed.** Remove `"firebase": "^12.8.0"` from `apps/mobile/package.json` dependencies (line 34). The `@react-native-firebase/*` packages (app/auth/firestore `^24.1.0`) stay. Optionally drop the now-dead `firebase|@firebase` entry from the jest `transformIgnorePatterns` (line 59) — leaving it is harmless but stale. [Source: package.json:19-21,34,59; sprint-status.yaml:88 "`firebase` dep … (1.8 owns removal)"]
7. **`detectionConfigService.test.ts` migrated.** The existing suite at `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts` swaps `jest.mock("firebase/firestore", …)` for a `jest.mock("@react-native-firebase/firestore", …)` using the **lazy-thunk + `__esModule`/`default` factory pattern** established in 1.7 (`subscriptionService.test.ts:26-33`), and **drops** the `jest.mock("../../auth/firebaseConfig", …)` block. All existing assertions (singleflight, version-refresh, offline-fallback, malformed, missing-doc) continue to pass unchanged — the `mockSnapshot`/`exists()`-as-method fixtures are already RNFB-compatible. [Source: detectionConfigService.test.ts:1-12,55-60; subscriptionService.test.ts:3-12,26-33,61-65; epics:906]
8. **Gates green (binding).** `pnpm --filter mobile typecheck` → **0 errors** (0 new vs current 0 baseline). `pnpm --filter mobile test` (jest) → all suites green, **no regressions** (baseline **18 suites / 158** = 148 passed + 10 todo, per 1.7 code-review). `pnpm --filter mobile exec expo export --platform android` builds clean with **no `firebase` (JS SDK) resolution** and a bundle size **≤ the 1.5 baseline of 5.23 MB** (the JS-SDK firestore code leaves the bundle). [Source: sprint-status.yaml:88 (158 count); 1-5 dev notes (5.23 MB)]

> AC checkboxes per `[[feedback_ac_checkbox_tighten]]`: hold `[ ]` until verified. AC9 manual smoke (below) and the post-merge review/PR flip are `[HELD]`.

9. **Manual smoke (deferred, `[HELD]`).** Stale-while-revalidate cycle works on the Android dev build post-migration: cache miss → Firestore read → cache populate → next read returns cache; background refresh fires after a higher remote `version`. Per the Epic-1 precedent ([[feedback_batch_manual_checks_epic_end]]), this is folded into **Story 1.9's** consolidated E2E manual pass (J1–J10), not run standalone here. [Source: epics:904; 1-5/1-6/1-7 device-smoke deferrals]

## Tasks / Subtasks

- [x] **Task 1 — Migrate the Firestore read (AC: 1, 2, 3, 4)**
  - [x] Replace `import { doc, getDoc, getFirestore } from "firebase/firestore"` (line 24) and `import { app } from "../auth/firebaseConfig"` (line 25) with a single `import firestore from "@react-native-firebase/firestore"`.
  - [x] Rewrite **only** the body of `fetchRemoteConfig()` (lines 104-120). Replace the three JS-SDK lines:
    ```ts
    const db = getFirestore(app);
    const ref = doc(db, DETECTION_CONFIG_DOC_PATH);
    const snap = await getDoc(ref);
    ```
    with one RNFB chain:
    ```ts
    const snap = await firestore()
      .collection(DETECTION_CONFIG_COLLECTION)
      .doc(DETECTION_CONFIG_DOC_ID)
      .get();
    ```
  - [x] Keep `DETECTION_CONFIG_DOC_PATH = "detection_config/latest"` exported (used in the not-found error message). Add module consts `DETECTION_CONFIG_COLLECTION = "detection_config"` and `DETECTION_CONFIG_DOC_ID = "latest"` for the RNFB chain (RNFB takes collection + doc segments separately, unlike the JS SDK's slash path). Do not change the exported constant's value or the error string.
  - [x] Leave `snap.exists()` as a method call and `snap.data()` unchanged — RNFB v24.1.0 matches the JS-SDK shape here (AC4).
  - [x] **Do not touch** the singleflight gates, `readCache`/`writeCache`/memoization, `getDetectionConfig`/`backgroundRefresh`/`refreshDetectionConfig`/`getCachedDetectionConfig`, the two error classes, or `validateDetectionConfig` — they are SDK-agnostic and must remain byte-stable except for the import line.

- [x] **Task 2 — Retire the `app` shim (AC: 5)**
  - [x] Confirm no remaining importer of `../auth/firebaseConfig` (after Task 1, grep `firebaseConfig` across `apps/mobile/src` should hit only the file itself + the test mock you remove in Task 3).
  - [x] Delete `apps/mobile/src/features/auth/firebaseConfig.ts` (this removes the final `firebase/app` JS-SDK import in the app).

- [x] **Task 3 — Migrate the test (AC: 7)**
  - [x] In `detectionConfigService.test.ts`, replace the `jest.mock("firebase/firestore", …)` block (lines 4-10) with an RNFB firestore mock following `subscriptionService.test.ts:14-33`: module-scope `mockGet`/`mockDoc`/`mockCollection`/`mockFirestoreFn` (`jest.fn`), then `jest.mock("@react-native-firebase/firestore", () => ({ __esModule: true, default: lazyFirestore }))` where `lazyFirestore` is a thunk deferring the `mockFirestoreFn` deref to call time (HOIST NOTE).
  - [x] **Delete** the `jest.mock("../../auth/firebaseConfig", () => ({ app: {} }))` block (lines 12-14) — the module no longer exists.
  - [x] Re-point every `mockGetDoc.mockResolvedValue*`/`mockRejectedValue*`/`mockImplementation` onto the new `mockGet` (the leaf of the `firestore().collection().doc().get()` chain). The existing `mockSnapshot()` helper (`exists: () => …`, `data: () => …`) already matches RNFB — keep it.
  - [x] In `beforeEach`, re-arm the chain after reset if you adopt 1.7's `resetAllMocks()` pattern; or keep the existing `mockReset()` on the leaf and leave the chain stubs as stable closures (simpler — the chain functions don't carry per-test queues). Either is fine as long as `mockGet.toHaveBeenCalledTimes(1)` still holds for the singleflight tests. **Chose the leaf-reset path** (`mockGet.mockReset()`; chain stubs stay stable closures).
  - [x] Keep all describe/it bodies and assertions intact — only the mock wiring changes.

- [x] **Task 4 — Drop the `firebase` dependency (AC: 6)**
  - [x] Remove `"firebase": "^12.8.0"` from `apps/mobile/package.json` dependencies (line 34).
  - [x] Optionally remove the dead `firebase|@firebase` token from the jest `transformIgnorePatterns` regex (line 59). **Done** — removed `|firebase|@firebase`.
  - [x] Run the package manager install so the lockfile drops `firebase` (and its now-unused transitive deps): `pnpm install` (or the repo's lock-update command). Verify `firebase` is gone from `pnpm-lock.yaml` for the mobile workspace. **Verified** — mobile importer block lists only `@react-native-firebase/*`; `apps/web`'s `firebase@^12.11.0` is the only remaining JS-SDK consumer (untouched).

- [x] **Task 5 — Gates (AC: 8)**
  - [x] `pnpm --filter mobile typecheck` → **0 errors**. `grep 'from "firebase'` over `apps/mobile/src` → no matches.
  - [x] `pnpm --filter mobile test` → **18 suites / 158 (148 passed + 10 todo)**, 0 regressions vs the baseline.
  - [x] `pnpm --filter mobile exec expo export --platform android` → clean build, no `firebase` (JS SDK) module in the graph, bundle **4.44 MB** (down from the 5.23 MB baseline — the JS-SDK firestore code left the bundle).

- [ ] **Task 6 — Git delivery (`[HELD]` — post-merge Two-PR per [[feedback_two_pr_docs_execution]])**
  - [x] Commit on the session branch `claude/hopeful-sagan-estln9` (this remote-exec session; NOT a new `story-1-8-*` branch — same precedent as 1.6/1.7). Push `-u origin claude/hopeful-sagan-estln9`.
  - [ ] [HELD] PR open + `--no-ff` merge to main; flip Status `review → done` and sprint-status entry post-review.

- [ ] **Task 7 — Manual smoke (`[HELD]` → Story 1.9) (AC: 9)**
  - [ ] Folded into Story 1.9's J1–J10 consolidated Epic-1-end manual pass on the Android dev build.

## Dev Notes

### What this story changes — and what it must NOT touch

`detectionConfigService.ts` is a 235-line stale-while-revalidate cache service. **The only SDK-coupled code is `fetchRemoteConfig()` (lines 104-120) and the two import lines (24-25).** Everything else — three singleflight gates, MMKV memoization (`memoCache`), `readCache`/`writeCache`, the `OfflineFirstLaunchError`/`MalformedRemoteConfigError` disambiguation, and the public API (`getDetectionConfig`, `refreshDetectionConfig`, `getCachedDetectionConfig`, `__clearDetectionConfigCacheForTests`) — is SDK-agnostic and must remain behaviorally identical. A clean migration touches ~6 lines of production code. [Source: detectionConfigService.ts:1-235]

**Current `fetchRemoteConfig` (the migration target):**
```ts
import { doc, getDoc, getFirestore } from "firebase/firestore";
import { app } from "../auth/firebaseConfig";
// ...
async function fetchRemoteConfig(): Promise<DetectionConfig> {
  const db = getFirestore(app);
  const ref = doc(db, DETECTION_CONFIG_DOC_PATH);
  const snap = await getDoc(ref);
  if (!snap.exists()) {
    throw new Error(`DetectionConfig: Firestore document ${DETECTION_CONFIG_DOC_PATH} does not exist`);
  }
  try {
    return validateDetectionConfig(snap.data());
  } catch (err) {
    throw new MalformedRemoteConfigError(err instanceof Error ? err : new Error(String(err)));
  }
}
```
This is the **direct analogue** of `subscriptionService.checkSubscription` migrated in 1.7 — copy its shape: `firestore().collection(...).doc(...).get()`, `snap.exists()` method, `snap.data()`. [Source: subscriptionService.ts:42-52]

### The DETECTION_CONFIG_DOC_PATH split (the one API-shape gotcha)

The JS SDK accepts a slash-path: `doc(db, "detection_config/latest")`. RNFB's namespaced API takes **separate segments**: `.collection("detection_config").doc("latest")`. The exported `DETECTION_CONFIG_DOC_PATH = "detection_config/latest"` constant is still referenced in the not-found error message, so keep it; add two new local consts for the segments rather than `.split("/")` at runtime (clearer, and the path is a fixed single-doc collection). [Source: detectionConfigService.ts:31, 104-109]

### `exists()` is a method, `data()` is fine (inherited 1.7 verdict)

Do NOT "fix" `snap.exists()` into a property access. RNFB v24.1.0's `DocumentSnapshot.exists()` is a method returning `boolean`, identical in usage to the JS SDK — verified against the installed type def in Story 1.7 and explicitly flagged for inheritance here. `snap.data()` returns `DocumentData | undefined` and is passed straight to `validateDetectionConfig` (Zod), which already tolerates `undefined`/garbage by throwing → `MalformedRemoteConfigError`. [Source: sprint-status.yaml:88; subscriptionService.ts:48-49]

### This is the LAST consumer — the cleanup is the point

Grep confirms after this story there are exactly **zero** `firebase/*` JS-SDK imports left in the app:
- `detectionConfigService.ts:24` (`firebase/firestore`) → migrated (AC1)
- `firebaseConfig.ts:1` (`firebase/app`) → file deleted (AC5)

`firebaseConfig.ts` has only two importers and both are eliminated in this story (the prod import via AC1, the test mock via AC7). Auth + Google sign-in already import `auth` directly from `@react-native-firebase/auth` (Stories 1.5/1.6) — they do NOT touch `firebaseConfig.ts`. So deleting the file is safe and is what unblocks dropping the `firebase` npm dep (AC6). **If typecheck or jest surface any other `from "firebase…"` reference, stop and report — the migration premise (last consumer) would be wrong.** [Source: grep `firebase/(app|firestore|auth)` over apps/mobile; firebaseConfig.ts importers = {detectionConfigService.ts, its test}]

### Scope boundary — bundled fallback is Story 1.13, not here

Epic AC3 mentions "bundled fallback engaged per Decision #2." That bundled-asset path (`apps/mobile/assets/map_config.json` + `detectionConfigBootstrap.ts` rewrite) is **Story 1.13 (AR-4)**, amended 2026-05-15 to the 9.9c unified schema. Story 1.8 only preserves the *existing* `MalformedRemoteConfigError`/`OfflineFirstLaunchError` error paths through the SDK swap — do not introduce any bundled-asset read or `MalformedRemoteConfigError`-triggered fallback here. [Source: epics:903; epics-and-stories.md:1003-1022]

### Test migration — reuse 1.7's hard-won mock pattern

`subscriptionService.test.ts` (1.7) and `authService.test.ts` (1.6) documented two jest pitfalls; reuse their fixes verbatim:
1. **Hoist-ordering:** Babel hoists `import`→`require()` above module-scope `const mockX = jest.fn()`, so a `default: mockFn` factory ref dereferences `undefined`. Fix = wrap in a lazy thunk (`function lazyFirestore(...a){ return mockFirestoreFn(...a); }`). [Source: subscriptionService.test.ts:3-9,26-33]
2. **Mock-queue leak:** jest 29 `clearAllMocks()` leaves `mockResolvedValueOnce` queues intact across tests. The current `detectionConfigService.test.ts` uses `mockGetDoc.mockReset()` per-test (not `clearAllMocks`), so it's already safe — but if you adopt `resetAllMocks()`, re-arm the chain `mockImplementation`s in `beforeEach`. [Source: subscriptionService.test.ts:10-12; detectionConfigService.test.ts:64]

The existing `mockSnapshot(payload)` helper returns `{ exists: () => …, data: () => payload }` — already RNFB-shaped (method `exists`). Keep it; just re-point the resolved/rejected values from `mockGetDoc` onto the chain leaf `mockGet`. The `firebase/firestore` factory currently fakes `getFirestore`/`doc`/`getDoc`; the RNFB factory only needs the `firestore().collection().doc().get()` chain.

### Architecture Compliance & Guardrails

- **Language/stack:** TypeScript (strict), React Native + Expo, jest 29. No `any`, no `@ts-expect-error`/`@ts-ignore` suppressions (1.3/1.7 review standard). [Source: prior story reviews]
- **Native module init:** the RNFB `[DEFAULT]` app auto-initializes from `google-services.json` (Story 1.4 prebuild) — `firestore()` needs no explicit app handle, which is exactly why the `app` shim becomes deletable. Do not re-introduce an explicit `initializeApp`/app-passing call. [Source: firebaseConfig.ts:3-14 comment; 1-4/1-5 notes]
- **File locations:** all edits stay under `apps/mobile/src/features/video-processing/` (+ delete one file under `…/auth/`) and `apps/mobile/package.json`. No new files. [Source: epics:893-908]
- **Test isolation:** no live network — mock `@react-native-firebase/firestore` (jest never loads the native module under node). [Source: epics:906; 1.7 precedent]

### Previous Story Intelligence (1.7 — done)

- 1.7's code review applied a tightened duck-typed Timestamp guard and moved a top-level `expect()` into a named `it()`. **Neither applies to 1.8** — `detectionConfigService` reads no Timestamps (its payload is a Zod-validated `DetectionConfig` with numeric `version` + thresholds), and its test already nests all assertions in `describe/it`. [Source: sprint-status.yaml:88]
- 1.7 left 5 pre-existing deferrals in `deferred-work.md` — all in `subscriptionService.ts` (cache contamination, revalidation-timer lifecycle, etc.). **None touch `detectionConfigService.ts`.** No `deferred-work.md` entries reference 1.8 or detectionConfig (grep empty). [Source: deferred-work.md grep]
- Established branch convention for this remote-exec session: work + commit on `claude/nice-bohr-lsdki5`, NOT a per-story `story-1-8-*` branch (1.6/1.7 precedent). [Source: sprint-status.yaml:87-88]

### Project Structure Notes

- `detectionConfigService.ts` lives in `video-processing/`, not `auth/` — but imports the auth feature's `firebaseConfig`. That cross-feature import is the coupling this story severs; after migration `video-processing` depends only on `@react-native-firebase/firestore` + its own `detectionConfig` (Zod) module. No structural conflict. [Source: detectionConfigService.ts:24-29]

### References

- [Source: epics-and-stories.md:893-910 — Story 1.8 user story, ACs, deps]
- [Source: epics-and-stories.md:308 — BF-3 migration sequence; :318 — AR-4 bundled config (Story 1.13)]
- [Source: apps/mobile/src/features/video-processing/detectionConfigService.ts:24-25,104-120 — migration target]
- [Source: apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts:1-14,55-60 — test to migrate]
- [Source: apps/mobile/src/features/auth/firebaseConfig.ts:1-26 — shim to delete]
- [Source: apps/mobile/src/features/auth/subscriptionService.ts:42-52 — 1.7 migrated reference]
- [Source: apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts:3-33,61-65 — RNFB mock pattern + exists() method]
- [Source: apps/mobile/package.json:19-21,34,59 — RNFB deps kept, `firebase` dep removed]
- [Source: _bmad-output/sprint-status.yaml:88 — 1.8 owns shim+dep removal; exists()-method verdict; 158-test baseline]

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Amelia / dev-story)

### Debug Log References

- `pnpm install` — updated `pnpm-lock.yaml`; mobile importer drops `firebase` JS SDK (45.4s).
- `pnpm --filter mobile typecheck` → 0 errors.
- `pnpm --filter mobile test` → 18 suites / 158 (148 passed + 10 todo), 0 regressions.
- `pnpm --filter mobile exec expo export --platform android` → android bundle 4.44 MB (`index-*.hbc`), no `firebase`/`@firebase/firestore` string in the Hermes bytecode.

### Completion Notes List

- **AC1 (Firestore read migrated):** `fetchRemoteConfig()` now reads via `firestore().collection("detection_config").doc("latest").get()`. Both JS-SDK imports (`firebase/firestore` + `../auth/firebaseConfig`) replaced by a single `import firestore from "@react-native-firebase/firestore"`. No `firebase/*` JS-SDK import remains anywhere in `apps/mobile/src` (grep-clean).
- **AC2 (singleflight gates preserved):** Only `fetchRemoteConfig`'s body + the import/const lines changed; the three inflight gates, MMKV memo, SWR cache, and public API are byte-stable. The two singleflight tests still assert `mockGet` called exactly once.
- **AC3 (error-path semantics preserved):** `validateDetectionConfig` still runs on `snap.data()`; `MalformedRemoteConfigError` / `OfflineFirstLaunchError` disambiguation unchanged. No bundled-asset fallback introduced (that stays Story 1.13/AR-4).
- **AC4 (`exists()` stays a method):** kept `snap.exists()` — RNFB v24.1.0 `DocumentSnapshot.exists(): boolean`, inheriting the 1.7 verdict.
- **AC5 (`app` shim removed):** deleted `apps/mobile/src/features/auth/firebaseConfig.ts` — the last `firebase/app` JS-SDK import. Confirmed its only two importers (prod service + test mock) were both eliminated this story; auth/googleSignIn import `auth` directly from RNFB.
- **AC6 (`firebase` dep removed):** dropped `"firebase": "^12.8.0"` from `apps/mobile/package.json` and the now-dead `firebase|@firebase` token from the jest `transformIgnorePatterns`. Lockfile re-resolved; mobile workspace no longer pulls the JS SDK (`apps/web` keeps its own `firebase` — untouched).
- **AC7 (test migrated):** swapped the `firebase/firestore` mock for an RNFB `@react-native-firebase/firestore` lazy-thunk + `__esModule`/`default` factory (1.7 pattern); dropped the `../../auth/firebaseConfig` mock; re-pointed all `mockGetDoc` → `mockGet` (chain leaf). Chose leaf-reset (`mockGet.mockReset()`), leaving the collection/doc/firestore() stubs as stable closures. All describe/it bodies unchanged.
- **AC8 (gates green):** typecheck 0; jest 18/158 no-regression; expo android export clean at 4.44 MB ≤ 5.23 MB baseline.
- **AC9 (manual smoke):** `[HELD]` → folded into Story 1.9's consolidated Epic-1-end Android device pass.
- **BF-3 complete (code side):** this was the last `firebase/firestore` JS-SDK consumer; with the `app` shim deleted and the dep dropped, the Firebase v12 RN migration is code-complete pending 1.9's manual sign-off.

### File List

- `apps/mobile/src/features/video-processing/detectionConfigService.ts` (modified — Firestore read migrated to RNFB; import + 2 segment consts)
- `apps/mobile/src/features/auth/firebaseConfig.ts` (deleted — orphaned `firebase/app` shim)
- `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts` (modified — RNFB firestore mock; dropped firebaseConfig mock)
- `apps/mobile/package.json` (modified — removed `firebase` dep + dead jest transformIgnore token)
- `pnpm-lock.yaml` (modified — re-resolved; mobile workspace drops `firebase` JS SDK)

## Change Log

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-12 | 1.0 | Story 3.E implemented — migrated `detectionConfigService.ts` `fetchRemoteConfig()` to `@react-native-firebase/firestore`, deleted the orphaned `firebaseConfig.ts` `app` shim, and dropped the `firebase@^12.8.0` JS-SDK dependency from the mobile app. Gates green (typecheck 0; jest 18/158; android bundle 4.44 MB). Status → review. |
