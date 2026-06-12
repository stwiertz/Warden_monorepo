# Story 1.10: user-doc.schema.json Tighten + Reconcile (AR-1, Decision #1)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane**,
I want **`contracts/user-doc.schema.json` cleaned up: drop legacy `isPaid`, add formal `created_at` / `updated_at`, tighten `additionalProperties: true → false`, and regenerate the Zod surface**,
so that **the `users/{uid}` Firestore wire-shape contract is the single source of truth across web (Zod) and mobile (read-only) and no schema drift is possible at runtime.**

## Context & Boundaries

This is **AR-1 / Decision #1** — the first leg of the coordinated contract triple **Decision #1 → #6 → #9** (`architecture.md:911`, `:922`). It tightens the contract **only**. It does **not** re-wire web (that is **Story 1.11 / AR-2 / Decision #6** — replacing `apps/web/src/lib/schemas/subscription.ts` with a re-export) and does **not** touch the webhook (Story 1.12 / AR-3 / Decision #9).

**This story is the upstream gate for 1.11 and 1.13** (both list "Story 1.10" as a dependency — `epics-and-stories.md:975`, `:1024`). It has **no upstream dependency** of its own (`epics-and-stories.md:956`: independent of the spike + Firebase migration).

**No production app behavior changes.** Mobile already reads `status` + `current_period_end` (never `isPaid`) via `subscriptionService.isSubscriptionPaid()` (migrated through Stories 1.4–1.8). Web already declares a local schema with no `isPaid` and no transform. This story makes the *contract* match the already-shipped reality and adds a strict-mode guard against future drift.

## Acceptance Criteria

> All ACs start unchecked. The dev agent flips each `[ ]→[x]` only when the gate is independently verified.

**AC0 — Kickoff decision (resolve at dev-story start, record verdict in the dev record):**

- [x] **Strict-test home → VERDICT: Option (A).** Added `"@warden/contracts": "workspace:*"` to `apps/web/package.json` `dependencies` (runtime, so Story 1.11 needs zero `package.json` change), ran `pnpm install`, and placed the strict test at the epic-pinned web path `apps/web/src/lib/schemas/__tests__/user-doc-strict.test.ts`. Rationale: trivial, non-conflicting pull-forward of 1.11's inevitable dep-add; the web→contract *wiring* (replacing `subscription.ts`) still belongs to 1.11. The cross-version zod seam (web v4 / contracts v3) is harmless for a pure `.safeParse` test (verified green). AC4's epic-pinned test path is `apps/web/src/lib/schemas/__tests__/user-doc-strict.test.ts`, but **`apps/web` did not yet depend on `@warden/contracts`** (verified: no entry in `apps/web/package.json`, no `@warden/contracts` import anywhere under `apps/web/`). Choose:
  - **(A) — RECOMMENDED:** Add `"@warden/contracts": "workspace:*"` to `apps/web/package.json` `dependencies` (runtime, not dev — Story 1.11 consumes the re-export at runtime in `route.ts`/`useSubscription.ts`, so adding it as a `dependency` now means 1.11 needs **zero** `package.json` change), run `pnpm install`, and place the strict test at the epic-pinned web path. Trivial, non-conflicting pull-forward of 1.11's inevitable dep-add; the web→contract *wiring* (replacing `subscription.ts`) still belongs to 1.11.
  - **(B):** Keep `apps/web` untouched until 1.11; author the strict test inside `packages/contracts` (e.g. `packages/contracts/src/generated/__tests__/user-doc-strict.test.ts` with a vitest runner added to the contracts package). Strictly scopes 1.10 to the contract, but diverges from the epic's named test path and adds a test runner to a package that currently has none (`packages/contracts/package.json` → `"test": "echo 'no tests yet'"`).

**Contract edits (`contracts/user-doc.schema.json` — the hand-authored master, NOT `packages/contracts/`):**

- [x] Removed the optional `isPaid` boolean property **and** scrubbed its mention from the top-level `description` (now describes the derive-at-read-time/strict shape, no `isPaid`).
- [x] Added optional `created_at: { "type": "string" }` and `updated_at: { "type": "string" }` properties (NOT in `required`). Landed **before** flipping `additionalProperties` per the Decision #1 sub-decision (`architecture.md:369`).
- [x] Set `"additionalProperties": false` (was `true`).
- [x] `required` stays `["status", "plan"]`; `status` enum stays `["active","past_due","canceled"]`; `plan` enum stays `["monthly","yearly"]`; `current_period_end`/`stripe_customer_id`/`stripe_subscription_id` stay optional. Did **not** widen `status` to include `trialing`/`incomplete` — that is out of scope (the mobile `PAID_STATUSES` superset lives in app code, not the wire contract; `subscriptionService.ts:15`).

**Regeneration:**

- [x] `pnpm install` (container started with `node_modules` ABSENT), then `pnpm --filter @warden/contracts build` regenerated `packages/contracts/src/generated/user-doc.ts`. Confirmed the emitted `UserDocSchema` (a) contains no `isPaid`, (b) contains optional `created_at`/`updated_at`, (c) is `.strict()`. Did **not** hand-edit the generated file — it carries the `AUTO-GENERATED … Do not edit by hand` banner.

**Strict regression test (location per AC0):**

- [x] New test asserts the regenerated `UserDocSchema` **rejects** a payload carrying an unknown key (`{ status:'active', plan:'monthly', bogus:true }` → `.safeParse(...).success === false`), proving `additionalProperties:false` round-tripped to `.strict()`.
- [x] Same test asserts a payload carrying `isPaid` is now **rejected** (legacy field gone from the wire contract), a minimal valid `{ status:'active', plan:'monthly' }` **passes**, and `created_at`/`updated_at` strings are **accepted** (plus a full-doc-with-all-optionals pass). 5/5 green.

**Mobile documentation + regression:**

- [x] `apps/mobile/.env.example` — removed the legacy `users/{uid}.isPaid` documentation comment. Replaced with a note that the doc carries `status` + `current_period_end` (+ billing IDs) and that the mobile `isPaid` flag is **derived locally** (and MMKV-cached), not a Firestore field. Surrounding Firestore/Auth setup bullets intact.
- [x] `apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts` adds an assertion that `isPaid` is NOT part of the wire shape — doc fixture `{ status:'active', current_period_end: FUTURE, isPaid:false }` still returns `true` from `checkSubscription` (proves derivation from `status`+period, IGNORING the wire `isPaid`). Reuses the existing `snap(...)`/`ts(...)`/`mockGet` fixtures.

**Preservation gates (verify-and-record-negative — do NOT edit these files in 1.10):**

- [x] **No snake→camel transform exists to "preserve" — negative RECORDED.** Re-verified: `grep -rn "\.transform(" apps/web/src/lib/firebase/` returns nothing; the dir holds only admin/analytics/auth/client/errors/session modules. Touched **nothing** in `apps/web/src/lib/firebase/`, `route.ts`, `useSubscription.ts`, or `subscription.ts` (the last is **Story 1.11's** file). `git diff --name-only` confirms no boundary-guard file modified.
- [x] Mobile `useAuthStore.user.isPaid` stays a derived TS field on `AuthUser` (computed at last successful Firestore read, persisted in MMKV) — NOT a Firestore field. `subscriptionService.ts` (incl. the offline fallback at `:52-53` `cached?.isPaid ?? false`) is **unchanged** — only its test file gained an assertion.

**Gates green:**

- [x] `pnpm --filter @warden/contracts build` succeeds and `pnpm --filter @warden/contracts typecheck` passes (exit 0).
- [x] `pnpm --filter web test` — the new strict test passes (5/5, isolated + in-suite). **Pre-existing environmental caveat (NOT a regression of this story):** this fresh container reproduces a duplicate-React-under-pnpm fault that makes every React-rendering test (`*.tsx` + `useSubscription.test.ts`, which renders via testing-library) throw `Cannot read properties of null (reading 'useState')`. Proven pre-existing by reverting `apps/web/package.json` + `pnpm-lock.yaml` to baseline and re-installing: **identical** 132 failed / 198 passed, with and without my change → **zero regressions introduced**. The pure-schema layer this story touches is fully green: `pnpm exec vitest run src/lib/schemas/` → 2 files / 15 tests passed (auth + the new strict test). Web `typecheck` has 2 pre-existing errors (`RegistrationForm.tsx`, `@hookform/resolvers`/zod-v4 overload) — none reference my files; not a story gate.
- [x] `pnpm --filter mobile test` passes with the added wire-shape assertion — **18 suites / 159 (149 passed + 10 todo)**, up from the 158 baseline (+1 new test), 0 regressions.

## Tasks / Subtasks

- [x] **Task 1 — Resolve AC0** (AC: 0). VERDICT Option A: added `"@warden/contracts": "workspace:*"` to `apps/web/package.json` `dependencies`, ran `pnpm install`. Verdict + rationale recorded in Dev Agent Record + AC0.
- [x] **Task 2 — Edit the master schema** (AC: contract edits). In `contracts/user-doc.schema.json`: deleted `isPaid` property + scrubbed its description mentions; added optional `created_at`/`updated_at` string slots; flipped `additionalProperties` to `false`. Order honored: explicit slots added BEFORE flipping strict.
- [x] **Task 3 — Install + regenerate** (AC: regeneration). `pnpm install` then `pnpm --filter @warden/contracts build`; verified regenerated `packages/contracts/src/generated/user-doc.ts` has no-`isPaid` + optional `created_at`/`updated_at` + `.strict()`. Generated file not hand-edited.
- [x] **Task 4 — Strict regression test** (AC: strict test). Authored `apps/web/src/lib/schemas/__tests__/user-doc-strict.test.ts`: unknown-key rejection, `isPaid` rejection, minimal-valid pass, `created_at`/`updated_at` accept, full-doc pass. 5/5 green.
- [x] **Task 5 — Mobile docs + test** (AC: mobile). Updated `apps/mobile/.env.example` comment; added the wire-shape "isPaid ignored / derived locally" assertion to `subscriptionService.test.ts`.
- [x] **Task 6 — Gates** (AC: gates green). Ran contracts build+typecheck (green), `pnpm --filter web test` (strict test green; pre-existing React-render failures documented as non-regression), `pnpm --filter mobile test` (18/159, +1, 0 regressions). Results recorded.
- [x] **Task 7 — Deliver** (AC: —). Committed on the session branch `claude/keen-mayer-6rx8j5` (per this remote-exec session's directive — supersedes the story's stale `claude/wizardly-brown-qvcfne`; NOT a new `story-1-10-*` branch). `review → done` flip + any PR/merge handled at code-review time per the Two-PR follow-up convention, not here.

## Dev Notes

### What's already true (do not re-derive, do not "fix")

- **Mobile never read `isPaid` from Firestore.** `subscriptionService.ts:40-49` reads `users/{uid}`, checks `userDoc.exists()` (a METHOD under RNFB v24.1.0 — Story 1.7/1.8 verdict), and derives paid-ness from `status ∈ {active,trialing}` + `current_period_end.toMillis() > Date.now()` via `isSubscriptionPaid()`. The `isPaid` on `AuthUser`/`useAuthStore` is a *derived, MMKV-persisted TS field*, used only as the offline-read-failure fallback (`subscriptionService.ts:52-53`) and the revalidation diff (`:71`). Removing `isPaid` from the *wire contract* changes nothing at runtime.
- **Web already has no `isPaid` and no transform.** `apps/web/src/lib/schemas/subscription.ts` is a local `z.object({ status, plan, current_period_end:number, stripe_customer_id, stripe_subscription_id })` on `zod/v4` — no `isPaid`, no `created_at`/`updated_at`, no `.transform()`. `route.ts` hand-projects the Firestore doc (turning the Firestore `current_period_end` Timestamp into `.seconds`) and the schema's `current_period_end: z.number()` matches. This local schema is **Story 1.11's** to replace — leave it alone here.

### Files this story TOUCHES

| File | Action | Note |
|------|--------|------|
| `contracts/user-doc.schema.json` | EDIT | The hand-authored JSON Schema master. Drop `isPaid`, add `created_at`/`updated_at`, `additionalProperties:false`. |
| `apps/web/package.json` | EDIT (AC0=A) | Add `"@warden/contracts": "workspace:*"` to `dependencies`. |
| `apps/web/src/lib/schemas/__tests__/user-doc-strict.test.ts` | NEW (AC0=A) | Strict-mode + no-`isPaid` regression. Vitest (`apps/web/vitest.config.ts`). |
| `apps/mobile/.env.example` | EDIT | Scrub the legacy `isPaid` setup comment (line 25). |
| `apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts` | EDIT | Add the "wire `isPaid` ignored" assertion. |
| `packages/contracts/src/generated/user-doc.ts` | GENERATED | Output of `pnpm --filter @warden/contracts build`. Do NOT hand-edit; may be git-ignored/untracked (absent in the container until built). |

### Files this story must NOT touch (boundary guards)

- `apps/web/src/lib/schemas/subscription.ts` — **Story 1.11 (AR-2/Decision #6)** replaces it with `export { UserDocSchema as subscriptionResponseSchema } from '@warden/contracts/user-doc'`. Editing it here collides with 1.11.
- `apps/web/src/lib/stripe/webhooks.ts` / `webhook-events.ts` — **Story 1.12 (AR-3/Decision #9)**.
- `apps/web/src/lib/firebase/*`, `route.ts`, `useSubscription.ts` — no transform helpers live there; nothing to change.
- `contracts/map-config.schema.json` and the mobile detection-config path — **Story 1.13**.

### The generation pipeline (so the regen step is not a black box)

`packages/contracts/scripts/generate-zod.mjs` reads `contracts/{map-config,user-doc}.schema.json` from `repoRoot/contracts/`, runs `jsonSchemaToZod(schema, { name:'UserDocSchema', module:'esm' })`, and writes `packages/contracts/src/generated/user-doc.ts` with the auto-gen banner. `package.json` exports map `"./user-doc" → "./src/generated/user-doc.ts"`, so consumers import `@warden/contracts/user-doc`. The generated module emits `import { z } from "zod"` and the contracts package pins `zod ^3.23.8` + `json-schema-to-zod ^2.6.1` — the generator targets **zod v3 syntax** (`.strict()`, `.optional()`, `.enum([...])`), all valid in v3 and v4.

### Cross-version zod seam (latent — flag for 1.11, harmless here)

`apps/web` runs **zod v4** (`zod ^4.3.6`, imports `zod/v4`); the contracts package pins **zod v3**. Under pnpm the generated `user-doc.ts`'s bare `import { z } from "zod"` resolves to the contracts package's own v3 zod. For 1.10's strict test this is fine (`.safeParse`/`.strict` exist in both). For **1.11** (route/hook consuming the re-export) this means web would parse with a v3 schema instance while the rest of web is v4 — two zod runtimes in one app. **Not 1.10's problem**, but record it so 1.11 plans for it (options: bump contracts to zod v4 + a v4-capable generator, or accept the dual-runtime). Do not "fix" it preemptively in 1.10.

### Testing standards

- **Web:** Vitest (`apps/web/vitest.config.ts`, jsdom, setup `vitest.setup.ts`). Run `pnpm --filter web test`. The strict test is pure schema-parse — no React/jsdom needed, just `import { UserDocSchema } from '@warden/contracts/user-doc'` + `.safeParse`.
- **Mobile:** jest. The `subscriptionService.test.ts` mock harness (lazy-thunk `jest.mock('@react-native-firebase/firestore')`, `resetAllMocks()` + re-arm in `beforeEach`, `ts(ms)` Timestamp stand-in, `exists()`-as-method fixtures) is established — reuse it verbatim for the new assertion; do not introduce a new mocking style. Run `pnpm --filter mobile test`.
- All ACs verified independently; flip `[ ]→[x]` only on a green gate, never on intent.

### Previous-story intelligence (Stories 1.4–1.9 / BF-3)

- The Firebase v12 RN migration (1.4–1.8, all `done`/`review`) already moved mobile onto native RNFB and proved `DocumentSnapshot.exists()` is a method. Story 1.9 (`blocked`, AC0=Option B — held for full feature coverage) is the device sign-off and does not interact with this contract-only story.
- **Branch convention for this remote session:** develop + commit on the designated branch `claude/wizardly-brown-qvcfne`. Do NOT cut a `story-1-10-*` branch (the 1.1/1.2/1.4/1.5 local-branch precedent does not apply in this remote-exec session — see 1.6/1.7/1.8 history).
- **Two-PR / status-flip convention:** `review → done` flips and any merge bookkeeping happen at code-review time via the post-merge follow-up, not inside this create/dev step.

### Project Structure Notes

- Master schemas live at repo-root `contracts/*.schema.json` (NOT under `packages/contracts/` — that package only holds the generator + generated output). This is the single source of truth consumed by both TS (Zod, generated) and Python tooling (`jsonschema`, direct) per `architecture.md:172`.
- No conflict with project structure. The only structural addition is the optional `apps/web → @warden/contracts` workspace edge (AC0=A), which 1.11 requires anyway.

### References

- [Source: _bmad-output/epics-and-stories.md#Story 1.10] (lines 938–958) — AC checklist + dependencies + sprint fit.
- [Source: _bmad-output/architecture.md#Decision #1] (lines 350–375) — drop `isPaid`, add `created_at`/`updated_at`, tighten `additionalProperties`, regen, scrub `.env.example`; sub-decision ordering (line 369).
- [Source: _bmad-output/architecture.md#Decision #6] (lines 402–421) — confirms `subscription.ts` re-export is **1.11**, gated on Decision #1.
- [Source: contracts/user-doc.schema.json] — current master (isPaid at 32–35, `additionalProperties:true` at 8).
- [Source: packages/contracts/scripts/generate-zod.mjs] — generation pipeline; [Source: packages/contracts/package.json] — exports map + zod v3 pin.
- [Source: apps/web/src/lib/schemas/subscription.ts] / [apps/web/src/app/api/subscription/route.ts] / [apps/web/src/hooks/useSubscription.ts] — proves no transform helper + snake_case wire shape; 1.11 boundary.
- [Source: apps/mobile/src/features/auth/subscriptionService.ts] — `isPaid` derived locally, not read from wire; offline fallback at 52–53.
- [Source: apps/mobile/.env.example] (line 25) — legacy `isPaid` comment to scrub.

## Dev Agent Record

### Agent Model Used

opus-4-8 (BMad `/bmad-dev-story`, Amelia) — remote-exec session, branch `claude/keen-mayer-6rx8j5`.

### Debug Log References

- `pnpm install` (×2): first to seed the absent `node_modules`, second to wire the new `apps/web → @warden/contracts` workspace edge after the dep-add. Both exit 0.
- `pnpm --filter @warden/contracts build` → `generated map-config.ts` / `generated user-doc.ts`. Inspected output: `z.object({...}).strict()`, no `isPaid`, optional `created_at`/`updated_at`.
- `pnpm --filter @warden/contracts typecheck` → exit 0.
- `pnpm exec vitest run src/lib/schemas/__tests__/user-doc-strict.test.ts` → 1 file / 5 tests passed.
- `pnpm exec vitest run src/lib/schemas/` → 2 files / 15 tests passed (auth + strict).
- `pnpm --filter mobile test` → 18 suites / 159 (149 passed + 10 todo), 0 regressions.
- Baseline diff probe: `git stash push apps/web/package.json pnpm-lock.yaml` + `pnpm install` + `pnpm --filter web test` → identical 132 failed / 198 passed → web React-render failures pre-date this story (then `git stash pop` + reinstall + rebuild contracts to restore).

### Completion Notes List

- **AC0 = Option A.** Added `"@warden/contracts": "workspace:*"` to `apps/web` `dependencies` (runtime — zero `package.json` change needed by 1.11) and placed the strict test at the epic-pinned web path. The web v4 / contracts v3 zod seam is harmless for a pure `.safeParse` test (flagged for 1.11 in Dev Notes; not "fixed" here).
- **Contract tightened** (`contracts/user-doc.schema.json`): dropped `isPaid` + scrubbed its description mention; added optional `created_at`/`updated_at` string slots **before** flipping `additionalProperties: true → false` (sub-decision ordering honored); `required`/enums/optional billing fields unchanged; `status` NOT widened.
- **Regenerated** `packages/contracts/src/generated/user-doc.ts` (gitignored, untracked) via the package build — `.strict()`, no `isPaid`, optional timestamps. Not hand-edited.
- **No production app behavior changed.** Mobile already derives paid-ness from `status`+`current_period_end` and ignores any wire `isPaid`; web already declares a local `isPaid`-free schema. This story aligns the *contract* with shipped reality and adds a strict-mode drift guard.
- **Boundary guards held:** no edits to `subscription.ts`, `route.ts`, `useSubscription.ts`, `apps/web/src/lib/firebase/*`, `webhooks.ts`/`webhook-events.ts`, `subscriptionService.ts`, or `map-config.schema.json`. The "no snake→camel transform" negative was re-verified (grep-clean) and recorded.
- **Known non-regression:** this fresh container has a pre-existing duplicate-React-under-pnpm fault failing all React-rendering web tests (`useState` null); proven identical on baseline (132 failed) with and without this change. Pure-schema layer + the new strict test are green. Out of scope for this contract-only story.

### File List

| File | Action |
|------|--------|
| `contracts/user-doc.schema.json` | EDIT — dropped `isPaid`, added optional `created_at`/`updated_at`, `additionalProperties: true → false`, description scrubbed |
| `apps/web/package.json` | EDIT — added `"@warden/contracts": "workspace:*"` dependency (AC0=A) |
| `apps/web/src/lib/schemas/__tests__/user-doc-strict.test.ts` | NEW — strict-mode + no-`isPaid` regression (Vitest, 5 tests) |
| `apps/mobile/.env.example` | EDIT — scrubbed legacy `isPaid` setup comment; documents derived-locally model |
| `apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts` | EDIT — added "wire `isPaid` ignored / derived from status+period" assertion |
| `pnpm-lock.yaml` | EDIT — re-resolved for the `apps/web → @warden/contracts` workspace edge |
| `packages/contracts/src/generated/user-doc.ts` | GENERATED (gitignored, untracked) — output of `pnpm --filter @warden/contracts build` |

## Change Log

| Date | Change |
|------|--------|
| 2026-06-12 | Story 1.10 (AR-1 / Decision #1) implemented: tightened `contracts/user-doc.schema.json` (drop `isPaid`, add optional `created_at`/`updated_at`, `additionalProperties:false`), regenerated the Zod surface, added a strict-mode regression test (AC0=A web path + `@warden/contracts` dep pull-forward), scrubbed the mobile `.env.example` `isPaid` comment, and added a mobile wire-shape assertion. Contracts build+typecheck green; mobile 18/159 (+1, 0 regressions); web pure-schema green (React-render failures pre-existing/environmental). Status `ready-for-dev → in-progress → review`. Branch `claude/keen-mayer-6rx8j5`. |
