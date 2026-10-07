# Story 1.14: Firestore Rules Coverage Extended (AR-6, Decision #7)

Status: done

<!-- Created 2026-10-04 by /bmad-create-story 1.14 (claude-opus-5-5). Epic text: epics-and-stories.md:1054-1091.
     Architecture: Decision #7 (architecture.md:535-586), amended by Story 1.13 (architecture.md:399).
     Trigger context: Story 1.13 (done, ca46a5b) moved the mobile overlay read to post-auth and it now gets
     PERMISSION_DENIED because the repo's rules have no detection_config match (deferred-work.md:316-317). -->

## Story

As **Stephane**,
I want **`apps/web/firestore.rules` rewritten to cover `users/{uid}` (owner read; deny client write), `detection_config/{docId}` (signed-in read; deny client write) and `stripe_events/{eventId}` (deny all client access), with a catch-all deny, and verified against the Firestore emulator**,
so that **the Reader-App contract is enforced at the rules layer ([INVARIANT 2]), the mobile `detection_config/latest` overlay read from Story 1.13 can succeed once 1.15 deploys, and `stripe_events` is server-only.**

## Why now

```
mobile (1.13) signs in → refreshMapConfigOverlay()
  → firestore().collection("detection_config").doc("latest").get()     ← a single-doc GET
  → rules today: users/{userId} + {document=**} deny
  → PERMISSION_DENIED → logged, bundled config used (correct, but the OTA overlay is dead)
```

1.13 fixed the code side. This story writes the rule. **1.15 deploys it** (operator action); until then nothing changes in production.

## Kickoff decisions

| # | Fork | Decision | Rationale |
|---|------|----------|-----------|
| D1 | `detection_config/{docId}` vs `detection_config/latest` only | **`{docId}`, as the architecture and epic spec it** (pending Stephane's answer to Q2; the dev agent applies the answer if it differs). | The epic AC says "matches the architecture spec exactly". Everything in the collection is non-secret map-zone config that also ships inside the APK. Restricting to `latest` buys no confidentiality and would block a future revision-history doc. `allow read` also grants `list`, which only enumerates the same non-secret docs. |
| D2 | `stripe_events` explicit block although the catch-all already denies | **Keep the explicit block.** | Defense-in-depth and self-documentation. The block reads as policy; the catch-all reads as a default. firebase-admin (the only writer, `apps/web/src/app/api/webhooks/stripe/route.ts:42`) bypasses rules. |
| D3 | Emulator verification: manual doc vs automated suite | **AC0: Stephane chooses** (it adds a devDependency). Recommended: **Option C**. See the AC0 table. | Java 21 is installed (`openjdk 21.0.10`, the Android Studio JBR), and `@firebase/rules-unit-testing@5.0.2` has peer `firebase ^12`, which web already has (`^12.11.0`). Automation is now cheap. The epic's "manual" was written when none of this was established. |

## Acceptance Criteria

> Checkbox convention: an AC whose endpoint depends on a post-commit, device or operator action stays `[ ]`. Manual checks batch to the Epic 1 close-out pass.

- [x] **AC0 — Test-mechanism decision (Stephane, before dev starts).** Record the choice in Completion Notes.

  | Option | What it adds | Cost | Runs in `pnpm --filter web test`? |
  |---|---|---|---|
  | **A** Full automated | devDeps `@firebase/rules-unit-testing@^5` **and** `firebase-tools@^15` in `apps/web` | firebase-tools has a big dependency tree, and under `node-linker=hoisted` it lands in the root `node_modules` beside Metro. It also adds lockfile churn. | No. It runs as a separate `test:rules` script because it needs the emulator. |
  | **B** Manual (epic as written) | Nothing. `firestore.rules.test.md` is a step list run with `npx -y firebase-tools@15.32.1 emulators:start --only firestore` plus the Emulator UI Rules Playground | No dependency changes, but AC2 stays `[ ]` until someone runs it by hand (epic-end batch) | No |
  | **C** Hybrid (**recommended**) | devDep `@firebase/rules-unit-testing@^5` only. The `test:rules` script fetches the pinned CLI with `npx -y firebase-tools@15.32.1 emulators:exec ...` | One small devDep. The first run needs the network (npx download plus the ~60 MB emulator jar, cached at `~/.cache/firebase/emulators`). | No. Separate `test:rules` script. |

- [x] **AC1 — Rules file matches the spec.** `apps/web/firestore.rules` is exactly the architecture.md:550-576 rule set (comments allowed): `users/{userId}` → `allow read: if request.auth != null && request.auth.uid == userId; allow write: if false;` · `detection_config/{docId}` → `allow read: if request.auth != null; allow write: if false;` · `stripe_events/{eventId}` → `allow read, write: if false;` · `{document=**}` → `allow read, write: if false;`. `rules_version = '2'`. If Q2 is answered "latest only", the `detection_config` match becomes `/detection_config/latest` and the AC2 matrix row for `detection_config/other` flips to deny.
- [x] **AC2 — Emulator verification of the full matrix** (seed docs with security rules disabled; unique `projectId` with the `demo-` prefix, e.g. `demo-warden-rules`, so no real project or credentials are ever touched):

  | Path | anon | signed-in `u1` | Expected |
  |---|---|---|---|
  | `users/u1` get | deny | **allow** | owner read only |
  | `users/u2` get | deny | deny | not someone else's |
  | `users` list (unfiltered) | deny | deny | |
  | `users/u1` set / update / delete | deny | deny | [INVARIANT 2]: web (admin) is the sole writer |
  | `users/u1/anything/x` get | deny | deny | sub-collections fall to the catch-all |
  | `detection_config/latest` get | **deny** | **allow** | the 1.13 read |
  | `detection_config/other` get | deny | allow (D1) / deny (latest-only) | |
  | `detection_config/latest` create / update / delete | deny | deny | |
  | `stripe_events/evt_1` get / list / set | deny | deny | |
  | `random/doc` get / set | deny | deny | catch-all |

  Option A/C: `pnpm --filter web test:rules` green → tick at dev time. Option B: the matrix is executed by hand from `firestore.rules.test.md`. It stays `[ ]` and is logged in deferred-work.md for the Epic 1 close-out pass.
- [x] **AC3 — `apps/web/firestore.rules.test.md` exists** (the epic requires it under every option). It contains the AC2 matrix, the prerequisites (Java 21+, Node 20+, network on the first run), the exact run command, and a "V2: wire into CI (Phase 7 `ci.yml`)" note. Under Option B it also holds the click-by-click manual procedure.
- [x] **AC4 — Emulator wiring, deploy-neutral.** `apps/web/firebase.json` keeps `"firestore": {"rules": "firestore.rules"}` unchanged and gains an `"emulators"` block (`firestore.port` 8080, `ui.enabled` per option: true for B, false for A/C, and `"singleProjectMode": true`). `apps/web/.gitignore` adds `firebase-debug.log`, `firestore-debug.log` and `ui-debug.log`. No `.firebaserc` (that is project binding, so it belongs to 1.15; see Q3).
- [x] **AC5 — Option A/C only: the suite does not leak into the default run.** The rules test lives at `apps/web/firestore.rules.test.ts`, outside `src/`. It has its own `apps/web/vitest.rules.config.ts` (`environment: 'node'`, `include: ['firestore.rules.test.ts']`, `testTimeout` ≥ 20000 because the emulator is slow on a cold start). `apps/web/vitest.config.ts` adds `exclude: [...configDefaults.exclude, 'firestore.rules.test.ts']`. `package.json` gets `"test:rules": "npx -y firebase-tools@15.32.1 emulators:exec --only firestore --project demo-warden-rules \"vitest run --config vitest.rules.config.ts\""` (Option A uses the local `firebase` bin instead of npx). `pnpm --filter web test` still reports **351/351**.
- [x] **AC6 — No webhook or server code change.** Evidence in Completion Notes: every `stripe_events` and `users` write in `apps/web/src` goes through `adminDb` (firebase-admin): `route.ts:42`, `webhooks.ts:87/129/206`, `subscription/route.ts:12`, `subscription/portal/route.ts:12`. Also: `rg "firebase/firestore" apps/web/src` returns nothing (web has no client-SDK Firestore use). On mobile, `subscriptionService.ts:43,65` reads only the owner's `users/{uid}` and `mapConfigOverlay.ts` only gets `detection_config/latest`. Both stay allowed.
- [x] **AC7 — Stale docs corrected** (dated "AMENDED 2026-10-xx (Story 1.14)" notes where the file is a planning artefact; plain rewrites in `docs/`). `docs/architecture-web.md:160-175` (rules block plus the "detection_config does not appear" paragraph) and the debt row at :203. `docs/data-models-web.md:38-46`. `docs/deployment-guide.md:58`: replace only the "not covered … Phase 6 must reconcile" sentence and the reconcile item at :157. Leave the upload/`DetectionConfig` row at :101 to 1.16. `_bmad-output/architecture.md:541`: add a note that the "mobile reads work in dev" puzzle is resolved, because they never did (12.4d hit PERMISSION_DENIED and 1.13 confirmed it).
- [x] **AC8 — deferred-work.md updated.** Append to the :317 resolution line: "rules written 2026-10-xx by 1.14; prod deploy = 1.15". Leave :30 (deploy binding) open and re-home it to 1.15. Leave :349 (overlay retry) untouched, to be revisited after 1.15. Option B: log the AC2 manual run under the Epic 1 close-out pass.
- [x] **AC9 — Gates.** Web `pnpm --filter web typecheck` returns 0. The new `.ts` files fall under the tsconfig `**/*.ts` include, so `@firebase/rules-unit-testing` types must resolve. `pnpm --filter web test` passes 351/351 (the first cold run may time out, so re-run once). `pnpm --filter web test:rules` is green (A/C). Mobile is untouched, so no jest run is needed. Prettier check on touched files.
- [x] **AC10 — Scope fence** (see Dev Notes). No `firebase deploy` (1.15). No `.firebaserc` or project binding (1.15, Q3). No upload procedure or `deployment-guide.md` OTA section (1.16). No webhook tests (1.17). No mobile change. No CI workflow (Phase 7). No App Check (deferred-work.md:28).
- [x] **AC11 — `sprint-status.yaml`:** `1-14-firestore-rules-coverage-extended` `ready-for-dev → in-progress → review` with a reason comment, and `last_updated` bumped.

## Tasks / Subtasks

- [x] **T0 — Get the AC0 answer** (and Q2/Q3 if open). Do not add any dependency without it. (AC0)
- [x] **T1 — Rewrite `apps/web/firestore.rules`** per AC1. (AC1)
- [x] **T2 — Emulator wiring:** `firebase.json` emulators block, `.gitignore` log lines. (AC4)
- [x] **T3 — Option A/C:** `pnpm --filter web add -D @firebase/rules-unit-testing@^5` (A: also `firebase-tools@^15`). Write `firestore.rules.test.ts` covering every AC2 row, plus `vitest.rules.config.ts`, the default-config exclude and the `test:rules` script. Run it. (AC2, AC5)
  - [x] `initializeTestEnvironment({ projectId: 'demo-warden-rules', firestore: { rules: readFileSync('firestore.rules', 'utf8') } })`. Let `emulators:exec` provide `FIRESTORE_EMULATOR_HOST`, and do not hard-code host or port.
  - [x] `beforeEach`: `clearFirestore()`, then seed `users/u1`, `users/u2`, `detection_config/latest`, `detection_config/other` and `stripe_events/evt_1` through `withSecurityRulesDisabled`.
  - [x] Use `assertSucceeds` / `assertFails` on `authenticatedContext('u1').firestore()` and `unauthenticatedContext().firestore()`. Use the modular `firebase/firestore` API (`doc`, `getDoc`, `getDocs`, `collection`, `setDoc`, `updateDoc`, `deleteDoc`).
  - [x] `afterAll`: `testEnv.cleanup()`.
- [x] **T3-B — Option B:** *(N/A: Option C chosen; a manual fallback section is still in `firestore.rules.test.md`.)* write the manual procedure into `firestore.rules.test.md`, run it once if you can, and log it. (AC2, AC3)
- [x] **T4 — `firestore.rules.test.md`.** (AC3)
- [x] **T5 — AC6 evidence greps.** (AC6)
- [x] **T6 — Docs and deferred-work.** (AC7, AC8)
- [x] **T7 — Gates, sprint-status flip.** (AC9, AC11)

## Dev Notes

### Current state of what you touch

- **`apps/web/firestore.rules` (11 lines):** only `users/{userId}` (owner read, `write: if false`) plus the catch-all deny. Preserve the `users` rule byte-for-byte in meaning, because mobile `subscriptionService.ts` and the web session depend on it.
- **`apps/web/firebase.json`:** `{"firestore": {"rules": "firestore.rules"}}`. This is the deploy pointer 1.15 uses, so do not move or rename the rules file.
- **No `.firebaserc`, no `.github/workflows`, no firebase-tools installed globally** (`which firebase` → none). Java: `openjdk 21.0.10`. Node `v22.14.0` (`.nvmrc` 20). firebase-tools latest is `15.32.1` (engines node ≥ 20). Its emulators need JDK 21+.
- **`apps/web/vitest.config.ts`** uses `environment: 'jsdom'` and the default include. A rules test must not run there: jsdom plus no emulator means failure. Hence the separate config and the exclude (AC5).

### Rules semantics the dev must not get wrong

- **Matches OR together.** The catch-all `allow read, write: if false` does **not** cancel an allow granted by a more specific match. It only covers paths no other block allows. So a mistake in an explicit block cannot be "saved" by the catch-all. Test every row.
- **`read` = `get` + `list`; `write` = `create` + `update` + `delete`.** The 1.13 mobile read is a `get` (`mapConfigOverlay.ts`, `.doc("latest").get()`).
- **`/users/{userId}` does not match sub-collections.** `users/u1/x/y` falls to the catch-all (AC2 row).
- **An unfiltered `list` on `users` is denied.** Rules are not filters: the query cannot prove `userId == auth.uid` for every result.
- `request.auth != null` is true for any Firebase Auth user, anonymous included. Warden does not use anonymous auth (`rg signInAnonymously` gives no hits), and the overlay is **sign-in gated, not subscription gated**, per Stephane's decision of 2026-10-04 (1.13 Q5). Do **not** add an `isPaid` check.

### Testing standards

- Web tests use Vitest; repo prettier uses single quotes. The rules suite is integration-level and kept out of `pnpm test` (it needs the emulator). This matches the epic's "not yet wired into `pnpm --filter web test`".
- `demo-*` project IDs keep the emulator fully offline from real Firebase, with no credentials needed.
- **Hoisting caution** (deferred-work.md:29: two physical `firebase` copies under `node-linker=hoisted`). `@firebase/rules-unit-testing` must resolve the same `firebase` that the test's `firebase/firestore` import resolves, or `assertFails` misreads errors. If you see "Firestore instance type mismatch", import from the copy next to rules-unit-testing. Record what you did.

### Scope fences

| Not here | Owner |
|---|---|
| `firebase deploy --only firestore:rules`, Console verification, production smoke test | **1.15** (operator) |
| `.firebaserc` / binding to `warden-8ce50` (deferred-work.md:30) | **1.15** (Q3) |
| Envelope upload procedure, `deployment-guide.md` OTA section, `deployment-guide.md:101` `DetectionConfig` row | **1.16** |
| Webhook idempotency tests (`stripe_events` dedup) | **1.17** |
| Overlay retry on reconnect (deferred-work.md:349); AC14(c) device check of 1.13 | after 1.15 / Epic 1 close-out |
| `deploy-firestore-rules.yml`, CI wiring of `test:rules` | Phase 7 |
| App Check | security-hardening (deferred-work.md:28) |

### Previous story intelligence (1.13, done, `ca46a5b`)

- `detection_config/latest` now holds an **envelope** (`contracts/detection-config-envelope.schema.json`). Rules do not care about its shape, but the seeded test doc should be envelope-shaped for realism (copy `apps/mobile/src/features/video-processing/__tests__/fixtures/overlay-envelope.json`, or use a minimal `{envelope_version: 1, revision: 1, configs: {}}`, since rules never validate data).
- On `permission-denied` today, the mobile app logs `[map-config] overlay refresh failed (permission-denied, code=firestore/permission-denied)` and uses the bundle. After 1.15 this becomes the 1.13 AC14(c) device check. **This story cannot close that check.**
- The 1.13 review deferred two items until "after 1.14/1.15": the single refresh per `uid` with no retry, and the uid rehydrating before native auth. Neither is this story's.

### Git intelligence

Recent commits on `main`: `ca46a5b` (1.13), `fbc088e` (4.1 merge), `5ee936c` (12.4d). Sole dev on `main`, no PR. Commitlint needs a lowercase subject, e.g. `feat(web): extend firestore rules to detection_config and stripe_events (story 1.14)`. Do not commit unless Stephane says so.

### Latest tech notes

- `@firebase/rules-unit-testing` v5.0.2 (peer `firebase ^12`). API: `initializeTestEnvironment`, `authenticatedContext(uid)`, `unauthenticatedContext()`, `withSecurityRulesDisabled`, `clearFirestore`, `cleanup`, `assertSucceeds`, `assertFails`.
- `firebase-tools` v15.32.1. `emulators:exec "<cmd>"` starts the emulator, sets `FIRESTORE_EMULATOR_HOST`, runs the command and tears down. The first run downloads the Firestore emulator jar.

### References

- [Source: _bmad-output/epics-and-stories.md:1054-1091] Story 1.14; :1093-1110 (1.15); :1112-1136 (1.16, with its 1.13 amendment); :1138-1158 (1.17)
- [Source: _bmad-output/architecture.md:535-586] Decision #7; :399 (1.13 amendment); :1027-1029 (collection and doc-id conventions); :1317 [INVARIANT 2]
- [Source: _bmad-output/prd.md:1058] SEC-003; :948 web-WEBHOOK-002
- [Source: _bmad-output/implementation-artifacts/1-13-hybrid-map-config-delivery-schema-version-1.md] D5, AC14, scope fences :164-168
- [Source: _bmad-output/implementation-artifacts/deferred-work.md:28,29,30,316-317,334,349]
- [Source: apps/web/src/app/api/webhooks/stripe/route.ts:42; apps/web/src/lib/stripe/webhooks.ts:87,129,206]
- [Source: apps/mobile/src/features/auth/subscriptionService.ts:43,65; apps/mobile/src/features/video-processing/mapConfigOverlay.ts]

## Questions for Stephane (answer before dev; recommended answer first)

1. **AC0: test mechanism?** Recommended: **C** (devDep `@firebase/rules-unit-testing` only, CLI via pinned `npx`). It is automated and re-runnable, it closes AC2 at dev time instead of at epic end, and it avoids hoisting firebase-tools's large tree next to Metro.
2. **D1: `detection_config/{docId}` or `latest` only?** Recommended: **`{docId}`** (spec-exact; the content is non-secret and ships in the APK).
3. **Add a `.firebaserc` binding `apps/web` to `warden-8ce50` (deferred-work.md:30)?** Recommended: **yes, but in 1.15**, alongside the deploy it governs.

## Dev Agent Record

### Agent Model Used

claude-opus-5-5 (/bmad-dev-story 1.14, 2026-10-07)

### Debug Log References

- Red check: the suite run against the HEAD rules (`git show HEAD:apps/web/firestore.rules`) gives **2 failed / 15 passed**: exactly the two signed-in `detection_config` reads, i.e. the 1.13 `PERMISSION_DENIED` reproduced. With the new rules: **17/17 green** on a real emulator (`cloud-firestore-emulator-v1.22.0.jar`, downloaded on the first run; Java 21.0.10).
- Hoisting check: `firebase/firestore` and `@firebase/rules-unit-testing` both resolve from the root `node_modules` (one `firebase 12.12.1`). No "instance type mismatch", so no workaround was needed.

### Completion Notes List

- Story context created 2026-10-04 by /bmad-create-story. Comprehensive developer guide created; AC0 decision pending Stephane.
- **AC0 — Stephane's kickoff decisions (2026-10-07):**
  1. Test mechanism = **Option C**. Only `@firebase/rules-unit-testing` is added, as a devDependency of `apps/web`, **pinned exact at `5.0.2`** (peer `firebase ^12`, matching web's `^12.11.0`). The Firebase CLI is fetched on demand by `test:rules` via `npx -y firebase-tools@15.32.1`; firebase-tools is in no `package.json`. A separate `vitest.rules.config.ts` plus `test:rules` script; the default web vitest run excludes the rules test and stays 351/351. Project id `demo-warden-rules`.
  2. Rule shape = `match /detection_config/{docId}`, signed-in read (no `isPaid`), deny writes, per the architecture spec (D1 confirmed).
  3. `.firebaserc` binding to the production project = Story 1.15, not here (deferred-work.md entry re-homed to 1.15).
- **AC1:** `firestore.rules` is the architecture.md Decision #7 rule set verbatim (comments included).
- **AC2:** all 10 matrix rows covered by 17 vitest cases (the `it.each` rows run once for anon and once for `u1`). Writes are checked for create (new id), set (overwrite), update and delete. Real emulator run, green.
- **AC4:** `firebase.json` keeps `"firestore": {"rules": "firestore.rules"}` and adds `emulators` (firestore 8080, `ui.enabled: false`, `singleProjectMode: true`). Three emulator log names added to `apps/web/.gitignore` (verified: `firestore-debug.log` shows as ignored). No `.firebaserc`.
- **AC5:** `vitest.config.ts` adds `exclude: [...configDefaults.exclude, 'firestore.rules.test.ts']`. `vitest.rules.config.ts` uses node env, `testTimeout` 30000, `hookTimeout` 60000 and `fileParallelism: false`.
- **AC6 evidence (no server code changed):** every `users`/`stripe_events` access in `apps/web/src` goes through `adminDb`: `webhooks/stripe/route.ts:42` (`stripe_events`), `webhooks.ts:87/129/206`, `subscription/route.ts:12`, `subscription/portal/route.ts:12` (`users`). `rg "firebase/firestore" apps/web/src` returns no hits. Mobile: `subscriptionService.ts:43,65` reads `users/{user.uid}` (owner, allowed); `mapConfigOverlay.ts:207` gets `detection_config/latest` (signed-in, allowed).
- **AC7:** `docs/architecture-web.md` (rules block, the "does not appear" paragraph and the debt row), `docs/data-models-web.md`, `docs/deployment-guide.md` (the "not covered … Phase 6 must reconcile" sentence and Phase-7 item 3; the :101 `DetectionConfig` row was left for 1.16). `_bmad-output/architecture.md` Decision #7 gets an AMENDED 2026-10-07 note: the "mobile reads work in dev" puzzle is resolved because they never worked.
- **AC8:** deferred-work.md: the 12.4d resolution line gets "rules written 2026-10-07 by 1.14; prod deploy = 1.15"; the deploy-binding entry is re-homed to 1.15 and left open; the overlay-retry entry is untouched.
- **AC9 gates (baseline → now):** web tsc 0 → 0; web vitest 351/351 → 351/351 (passed on the first run); `test:rules` 17/17; mobile jest 20 suites / 270 + 10 todo → same; mobile tsc 0 → 0; tooling pytest 333 → 333. Prettier is clean on every touched TS, JSON and MD file.
- **Lockfile:** one package added (`@firebase/rules-unit-testing@5.0.2`, no own dependencies; peer `firebase` resolves to the existing 12.12.1). pnpm also re-serialised the snapshot keys of `eslint-import-resolver-typescript` / `eslint-module-utils` (shorter peer-suffix form, same versions). That is cosmetic, with no version change.
- **AC10:** no deploy, no `.firebaserc`, no mobile, webhook, uploader or CI change.
- **Deviation:** the story says `^5`; the dependency is pinned exact `5.0.2` per Stephane's "pin the version" instruction. `testTimeout` is 30000 (the AC asks for ≥ 20000).

### Review Findings

Code review 2026-10-07 (/bmad-code-review, claude-opus-5-5, uncommitted working tree on `ca46a5b`). 0 decision-needed, 4 patches, 2 deferred, 6 dismissed.

- [x] [Review][Patch] **`detection_config` list was untested.** `allow read` grants `list` too (D1 accepts it). Added: anon deny, signed-in allow. [firestore.rules.test.ts]
- [x] [Review][Patch] **No sub-collection row under `detection_config`.** Seeded `detection_config/latest/history/r0`; get is denied for both (catch-all). [firestore.rules.test.ts]
- [x] [Review][Patch] **Collection-group queries were unverified.** Added `collectionGroup` on `users`, `anything`, `history`, `stripe_events`: all denied for anon and `u1` (no `{path=**}` match grants them). [firestore.rules.test.ts]
- [x] [Review][Patch] **The `users` "create" case wrote `users/brand-new-doc` (someone else's id).** A future `allow create: if request.auth.uid == userId` would have passed unnoticed. Added `u3` creating `users/u3`: denied. The matrix in `firestore.rules.test.md` gains the 4 new rows. Suite **17 → 23/23** on the real emulator.
- [x] [Review][Defer] Anonymous auth would pass `request.auth != null`: accepted posture (1.13 Q5); confirm the Anonymous provider is disabled at deploy → **1.15**.
- [x] [Review][Defer] `test:rules` is not in CI (Java 21, port 8080, first-run network) → **Phase 7**.
- Dismissed: rule blocks OR together and no block grants beyond spec (verified line by line); `demo-warden-rules` is used by both the script and the suite, and without `FIRESTORE_EMULATOR_HOST` `initializeTestEnvironment` refuses to start, so production is unreachable; the default vitest exclude works (351/351, file not collected); the lockfile adds only `@firebase/rules-unit-testing@5.0.2` (no deps, peer = the existing hoisted `firebase 12.12.1`) plus cosmetic eslint key re-serialisation, mobile jest/tsc unchanged; docs match the shipped rules; consistent with `mapConfigOverlay.ts:207` (single-doc `get` of `detection_config/latest`, signed-in); npm "Unknown env config" warnings under `npx` are cosmetic.

Gates after review: web tsc 0; web vitest 351/351; `test:rules` 23/23; mobile jest 20 suites / 270 + 10 todo; mobile tsc 0; eslint + prettier clean on touched files; tooling untouched (pytest 333 baseline).

### File List

- apps/web/firestore.rules (modified)
- apps/web/firebase.json (modified)
- apps/web/.gitignore (modified)
- apps/web/package.json (modified)
- apps/web/vitest.config.ts (modified)
- apps/web/vitest.rules.config.ts (new)
- apps/web/firestore.rules.test.ts (new)
- apps/web/firestore.rules.test.md (new)
- pnpm-lock.yaml (modified)
- docs/architecture-web.md (modified)
- docs/data-models-web.md (modified)
- docs/deployment-guide.md (modified)
- _bmad-output/architecture.md (modified)
- _bmad-output/implementation-artifacts/deferred-work.md (modified)
- _bmad-output/implementation-artifacts/1-14-firestore-rules-coverage-extended.md (modified)
- _bmad-output/sprint-status.yaml (modified)

### Change Log

- 2026-10-07: Story 1.14 implemented (Option C). Firestore rules extended to `detection_config/{docId}` and `stripe_events`; emulator suite `test:rules` (17/17, real emulator); docs and deferred-work updated. Status → review.
- 2026-10-07: Code review: 4 test patches (rules suite 17 → 23), 2 deferred, 0 open decisions. Status → done.
