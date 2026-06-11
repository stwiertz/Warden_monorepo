# Story 1.3: Stripe API Pin Bump 2026-03-25.dahlia → 2026-04-22.dahlia (BF-1)

Status: review

<!-- Validation is optional. Run validate-create-story before dev-story for a quality check. -->

> ### 🔧 Scope Adjustment #1 (dev-story, 2026-06-09) — AC4 "full suite green" re-scoped to the changed-code surface
>
> **AC0 resolved = Option A** (the 2 `EmailSignInForm.tsx` / `RegistrationForm.tsx` Zod-4/`@hookform/resolvers` errors stay out of scope).
>
> **The story's premise that the runtime Vitest suite was green pre-change was wrong.** At baseline — **before any edit** — `pnpm --filter web test` reports **133 failed / 192 passed (8 errors)**. The failures are **component/hook render tests** (`src/app/page.test.tsx`, `src/contexts/AuthContext.test.tsx`, `src/hooks/useSubscription.test.ts`, …) returning **empty DOM** (`Unable to find role "heading"`, `expected length 1 but got 0`) — a pre-existing **React/@testing-library/jsdom environment breakage**, entirely unrelated to Stripe and **not introduced by this story** (proven: identical 133 failures with zero code changes). Fixing the web test environment is a separate story, well outside BF-1.
>
> **AC4 is therefore satisfied against its real intent** — "webhook event schemas still parse against the new API version." Evidence: the **6 Stripe/webhook test files (58 tests) + the 3 other API-route files I touched (19 tests) = 77 tests, all green** both before and after the change. The pre-existing 133-failure component-test breakage is recorded here as an out-of-scope condition for the user to triage separately. **No regression was introduced by this story.**

## Story

As **Stephane** (solo developer; Sprint 3 web/billing maintainer),
I want **the Stripe API version pin bumped from `2026-03-25.dahlia` to `2026-04-22.dahlia` to match the installed `stripe@^22.0.1` SDK's `LatestApiVersion`, plus the pre-existing Vitest test-file TypeScript errors cleaned up**,
So that **`pnpm --filter web typecheck` stops reporting the pin-literal mismatch and the test-file `tsc` errors (spread args, implicit `any`, tuple-index), and the webhook event schemas continue to parse against the dahlia API line.**

**Type:** Brownfield Item 1 (BF-1) — a one-line version-pin bump plus a web test-suite TypeScript-hygiene pass. **No new runtime behavior, no new dependencies, no new tests.** The existing Vitest suite is the regression gate.

> ### ⚠️ READ THIS FIRST — the scope is two things, only one of which is "Stripe"
>
> The one-line epic stub hides a real scope split that an import-graph + `tsc` audit surfaced. **Bumping the pin fixes exactly ONE of the 16 current web typecheck errors** — `server.ts(17,31)`. The other errors this story is asked to clean up (AC3) are **pre-existing Vitest mock-typing errors that have nothing to do with Stripe** — they appear identically in `auth/session`, `subscription`, AND `stripe` tests, all caused by `vi.fn()` / `vi.fn(() => …)` losing their call signature under `vitest@^4` + this `tsconfig`. Do **not** assume bumping the pin auto-resolves them; each is a separate manual fix. See **Dev Notes → "The 16-error map"** for the exact per-error breakdown and fix pattern. Two further errors (`EmailSignInForm.tsx`, `RegistrationForm.tsx`) are a Zod-4-vs-`@hookform/resolvers` incompatibility — see **AC0**.

## Acceptance Criteria (checklist)

> **AC checkbox convention** (per [[feedback_ac_checkbox_tighten]], inherited from Stories 0.2 / 1.1 / 1.2): items whose endpoint depends on **post-merge actions** (Stripe Dashboard operator change, sprint-status `review → done` flip, PR-open) are held `[ ]` with inline carve-out notes. Items the dev agent fully controls during the work flip to `[x]` on completion.

**AC0 — DECISION (resolve at dev-story kickoff): scope of the 2 Zod-4/react-hook-form `.tsx` errors.**
`pnpm --filter web typecheck` currently reports 16 errors. Fourteen are in this story's natural scope (1 Stripe pin + 13 `*.test.ts` errors). The remaining **two are NOT test files and NOT Stripe-related**: `src/components/auth/EmailSignInForm.tsx(32,27)` and `src/components/auth/RegistrationForm.tsx(32,27)`, both `TS2769` (`zodResolver(...)` overload mismatch — `zod@^4.3.6`'s `ZodObject` internals not assignable to `@hookform/resolvers@^5.2.2`'s expected shape). A literal reading of "typecheck **passes** (exit 0)" requires fixing these too, but that means a `@hookform/resolvers`/Zod-resolver change outside the Stripe-pin remit. Choose:
- **Option A (RECOMMENDED — default): out of scope.** AC3 is satisfied when the 14 in-scope errors are gone and **only** those 2 documented baseline `.tsx` errors remain. They are part of the long-standing "web 16-error baseline" repeatedly preserved across Stories 9.9a/9.9c (see [[project_warden_new_hud_labeler]] sprint-status notes) and belong to the Firebase/Zod-migration track (Epic 1 Stories 1.4–1.9 touch the auth surface), not BF-1. Record the residual 2 in the implementation notes.
- **Option B: in scope.** Also fix the 2 `.tsx` resolver errors (e.g. bump/adjust `@hookform/resolvers`, or wrap the schema) so `typecheck` exits 0. Larger blast radius (auth forms, resolver version) for a story whose deliverable is a Stripe pin.

**→ RESOLVED: Option A** (out of scope; AC3 satisfied with only those 2 baseline `.tsx` errors remaining). `[x]`

1. [x] **AC1 — Pin bumped.** `apps/web/src/lib/stripe/server.ts:7` — `const STRIPE_API_VERSION = '2026-03-25.dahlia'` → `'2026-04-22.dahlia'`. This is the single line that resolves `server.ts(17,31) TS2322` (`Type '"2026-03-25.dahlia"' is not assignable to type '"2026-04-22.dahlia"'`). Do **not** change the `getStripe()` lazy-singleton, the `retryStripeCall` logic, or anything else in this file.

2. [x] **AC2 — Changelog due-diligence recorded; freeze-fallback documented but expected unused.** The `2026-03-25.dahlia → 2026-04-22.dahlia` delta MUST be reviewed and the finding recorded in the implementation notes. **Pre-recorded finding (verify, don't re-derive):** the dahlia **breaking** changes landed in `2026-03-25.dahlia` (our *current* pin); the `2026-04-22.dahlia` release is **non-breaking** — its changes (issuing-card cancellation/replacement reasons, Managed Payments, Stripe Apps distribution KYC, transaction-category reversal types, Sunbit / Pix recurring, shared-payment tokens) touch **none** of our three handled events (`invoice.paid`, `customer.subscription.deleted`, `invoice.payment_failed`) nor the `subscriptions.retrieve` call. → **No breaking change; the freeze-fallback is NOT expected to trigger.** FALLBACK (only if review surfaces a concrete breaking change against our event surface): freeze the pin at `2026-03-25.dahlia` and downgrade the installed `@stripe` types to match — per PRD Decision #4 ([prd.md:586](../prd.md#L586)). Sources: [Dahlia changelog](https://docs.stripe.com/changelog/dahlia), [2026-04-22 issuing-card entry](https://docs.stripe.com/changelog/dahlia/2026-04-22/fulfillment-error-to-issuing-card-cancellation-and-replacement), [Stripe SDK versioning](https://docs.stripe.com/sdks/versioning).

3. [x] **AC3 — `pnpm --filter web typecheck` clean of the in-scope errors.** ✅ All 14 in-scope errors eliminated; `tsc --noEmit` now reports only the 2 baseline `.tsx` Zod-resolver errors (Option A). No `any`/suppressions used — mocks got explicit rest signatures, callback params got real types. After the work, `tsc --noEmit` reports **zero** of the 14 in-scope errors (the AC1 pin error + the 13 `*.test.ts` errors enumerated in Dev Notes → "The 16-error map"). Per **AC0**, the only residual errors permitted are the 2 documented `.tsx` Zod-resolver baseline errors (Option A) or none (Option B). **The 13 test errors are fixed by typing the mocks/params — NOT by the pin bump.** Fix patterns are spelled out in Dev Notes; the standing rule: **no `any`, no `@ts-expect-error`, no `// eslint-disable`** — give the `vi.fn()` mocks explicit call signatures and annotate the implicit-`any` callback params with real types.

4. [x] **AC4 — webhook schemas still parse; dahlia nesting preserved; changed-code tests green (see Scope Adjustment #1).** ✅ The 77 tests across the 9 touched/Stripe files pass; `parent.subscription_details.subscription` nesting untouched. ⚠️ The *full* suite is NOT green due to a **pre-existing, out-of-scope** component-test environment breakage (133 failures present before any edit) — re-scoped per Scope Adjustment #1 at the top of this file. The full Vitest suite passes. The webhook event schemas in [src/lib/schemas/webhook-events.ts](../../apps/web/src/lib/schemas/webhook-events.ts) MUST still parse Stripe payloads — specifically the dahlia `parent.subscription_details.subscription` nesting ([INVARIANT 6](../epics-and-stories.md#L3166)) must remain intact; do not "simplify" it to a top-level `subscription` field (Story 4.2 already fixed that regression once — see the inline comment at `webhook-events.ts:37-39`). The relevant suites are the **co-located** `*.test.ts` files (`src/lib/stripe/{invoice-paid,payment-failed,subscription-deleted,webhooks,coupons}.test.ts` + `src/app/api/webhooks/stripe/route.test.ts`) — **note: there is NO `__tests__/` subdirectory** (the epics-and-stories.md AC reference to `src/lib/stripe/__tests__/webhooks.test.ts` is stale; the real path is `src/lib/stripe/webhooks.test.ts`).

5. [ ] **AC5 — [HELD] Stripe Dashboard webhook endpoint api_version + deployment-guide doc.** Operator action (post-merge): set the Stripe Dashboard webhook endpoint's API version to `2026-04-22.dahlia` so live event payloads match the SDK pin, and document the step in [docs/deployment-guide.md](../../docs/deployment-guide.md). Held `[ ]` — this is an external Dashboard change the dev agent cannot perform from code; it lands with the operator/deploy pass, not the code PR. **Code-side note:** the recorded `api_version` on each event comes from the *inbound event payload*, not our SDK pin, so the handler code needs no change for this; the two test fixtures at `src/app/api/webhooks/stripe/route.test.ts:50` + `:124` hardcode `api_version: '2026-03-25.dahlia'` — bumping them to `'2026-04-22.dahlia'` is **optional cosmetic realism** (keep both lines in sync if you do; leaving them is also correct — they only assert that whatever version the event carries is recorded verbatim).

6. [ ] **AC6 — [HELD] sprint-status lifecycle + Two-PR follow-up.** Per [[feedback_two_pr_docs_execution]] + 9.9c/9.11/9.12 precedent: main PR delivers the code + flips `1-3-stripe-api-pin-bump` `ready-for-dev → review`; a tiny follow-up flips `review → done` post-merge and closes AC5/AC6. Held `[ ]` (post-merge admin).

7. [x] **AC7 — No scope creep / no regression invariant.** ✅ `apps/web/package.json` unchanged (verified `git diff --stat` empty); diff is exactly `server.ts:7` + 7 `*.test.ts` files (annotations only); `webhooks.ts`/`coupons.ts`/schemas untouched. No new dependencies (`apps/web/package.json` unchanged). No runtime behavior change — only the pin literal + test-file type annotations. `webhook-events.ts` schemas unchanged in shape (annotation-only AC3 fixes touch `*.test.ts` and `server.ts:7` exclusively, plus optionally the 2 `.tsx` files per AC0). Do not touch `webhooks.ts`, `coupons.ts`, or any non-test source beyond `server.ts:7`.

## Tasks / Subtasks

- [x] **Task 1 — Pre-flight + AC0 decision** (AC0, AC2)
  - [x] Baseline captured: `typecheck` = 16 errors (matched the map); `test` = **133 failed / 192 passed** — premise corrected (suite was NOT green; pre-existing component-test environment breakage, see Scope Adjustment #1). Stripe + touched-file subset = 77 green at baseline.
  - [x] **AC0 = Option A** recorded.
  - [x] Changelog delta reviewed; AC2 "non-breaking" finding confirmed against our 3 events (breaking changes were in the `2026-03-25` pin we left).
- [x] **Task 2 — Bump the pin** (AC1)
  - [x] `apps/web/src/lib/stripe/server.ts:7` → `'2026-04-22.dahlia'`. `server.ts(17,31) TS2322` gone.
- [x] **Task 3 — Fix the 13 `*.test.ts` TS errors** (AC3)
  - [x] Spread errors (`TS2556`, 7 sites): gave each spread-called `vi.fn(() => …)` mock an explicit `(..._args: unknown[])` rest signature. `subscription/portal/route.test.ts:16`, `subscription/route.test.ts:18`, `webhooks/stripe/route.test.ts:22`+`:40`, `invoice-paid.test.ts:29`, `payment-failed.test.ts:21`, `subscription-deleted.test.ts:13`.
  - [x] Tuple-index errors (`TS2493`, 2 sites): fixed by giving `mockRouteEvent` (`webhooks/stripe/route.test.ts:40`) the `(..._args: unknown[])` signature → `.mock.calls[0][0]` now indexable (`:130` + `:149`).
  - [x] Implicit-`any` errors (`TS7006`, 3 sites): annotated `(c: unknown[])`. `payment-failed.test.ts:301`, `subscription-deleted.test.ts:152` + `:218`.
  - [x] `TS2554` (1 site): `auth/session/route.test.ts:125` — handler `DELETE()` is genuinely 0-arg (`route.ts:52`); removed the unused `request` construction and call `DELETE()`. (No route-source change — minimal, test-only.)
  - [x] Cosmetic consistency: bumped the two inbound-event `api_version` fixtures (`webhooks/stripe/route.test.ts:50` + the `:124` assertion, kept in sync) to `2026-04-22.dahlia`.
- [x] **Task 4 — (only if AC0 = Option B) fix the 2 `.tsx` resolver errors** — N/A (AC0 = Option A; skipped by design).
- [x] **Task 5 — Validate** (AC3, AC4, AC7)
  - [x] `typecheck` → only the 2 baseline `.tsx` errors (Option A).
  - [x] `test` (Stripe + all touched files) → 77 passed; nesting intact (INVARIANT 6). Full-suite caveat per Scope Adjustment #1.
  - [x] `git diff --stat apps/web/package.json` → empty (no change).
- [ ] **Task 6 — [HELD] deployment-guide + sprint-status + PR** (AC5, AC6) — post-merge admin.
  - [ ] Add the Dashboard-api_version operator step to `docs/deployment-guide.md`.
  - [ ] Main PR + `review`; Two-PR follow-up for `review → done`.

## Dev Notes

### Strategic context

BF-1 was dispositioned **default-to-bump** in PRD Decision #4 ([prd.md:586](../prd.md#L586)) and listed as an Epic 1 brownfield item ([epics-and-stories.md:306](../epics-and-stories.md#L306), [:529](../epics-and-stories.md#L529)). The forcing function is a **type-literal mismatch, not a runtime bug**: `stripe@^22.0.1` declares `Stripe.LatestApiVersion = '2026-04-22.dahlia'`, and `StripeConfig.apiVersion` is typed to that single literal, so passing the older `'2026-03-25.dahlia'` is a `tsc` error (empirically confirmed: `server.ts(17,31) TS2322`). At runtime nothing is broken today (Vitest ignores types); this is purely a typecheck-cleanliness story that also sweeps up adjacent pre-existing test-typing debt.

### The 16-error map (ground truth from `pnpm --filter web typecheck`, 2026-06-09)

| # | File:Line | TS code | Cause | Scope |
|---|-----------|---------|-------|-------|
| 1 | `src/lib/stripe/server.ts:17:31` | TS2322 | pin literal `2026-03-25` ≠ SDK `LatestApiVersion 2026-04-22` | **AC1 — the bump** |
| 2 | `src/app/api/auth/session/route.test.ts:125:37` | TS2554 | `DELETE(request)` vs 0-arg-inferred handler | AC3 (auth, not Stripe) |
| 3 | `src/app/api/subscription/portal/route.test.ts:20:56` | TS2556 | spread into `vi.fn(() => …)` mock | AC3 |
| 4 | `src/app/api/subscription/route.test.ts:22:56` | TS2556 | spread into `vi.fn(() => …)` mock | AC3 |
| 5 | `src/app/api/webhooks/stripe/route.test.ts:26:56` | TS2556 | spread into mock | AC3 |
| 6 | `src/app/api/webhooks/stripe/route.test.ts:43:54` | TS2556 | spread into mock | AC3 |
| 7 | `src/app/api/webhooks/stripe/route.test.ts:130:41` | TS2493 | `mockRouteEvent.mock.calls[0][0]` empty-tuple | AC3 |
| 8 | `src/app/api/webhooks/stripe/route.test.ts:149:41` | TS2493 | `mockRouteEvent.mock.calls[0][0]` empty-tuple | AC3 |
| 9 | `src/lib/stripe/invoice-paid.test.ts:55:62` | TS2556 | spread into mock | AC3 |
| 10 | `src/lib/stripe/payment-failed.test.ts:49:62` | TS2556 | spread into mock | AC3 |
| 11 | `src/lib/stripe/payment-failed.test.ts:301:49` | TS7006 | implicit-`any` param `c` | AC3 |
| 12 | `src/lib/stripe/subscription-deleted.test.ts:40:62` | TS2556 | spread into mock | AC3 |
| 13 | `src/lib/stripe/subscription-deleted.test.ts:152:54` | TS7006 | implicit-`any` param `c` | AC3 |
| 14 | `src/lib/stripe/subscription-deleted.test.ts:218:49` | TS7006 | implicit-`any` param `c` | AC3 |
| 15 | `src/components/auth/EmailSignInForm.tsx:32:27` | TS2769 | `zodResolver` Zod-4 vs `@hookform/resolvers@5` | **AC0** — out of scope (Option A) |
| 16 | `src/components/auth/RegistrationForm.tsx:32:27` | TS2769 | `zodResolver` Zod-4 vs `@hookform/resolvers@5` | **AC0** — out of scope (Option A) |

Errors 3–14 are a single root cause: `vi.fn()` and `vi.fn(() => X)` infer a **zero-arg** call signature under `vitest@^4`'s typings + this project's `tsconfig`, so (a) spreading `(...args)` into them violates "must have a tuple type / rest param" and (b) `.mock.calls[0][0]` indexes an inferred empty tuple `[]`. **The Stripe pin bump does not touch any of these.**

### Exact fix patterns (AC3) — no `any`, no `@ts-expect-error`

**Spread (TS2556)** — representative site `src/app/api/subscription/route.test.ts:22`:
```ts
// before — mockCollection = vi.fn(() => ({ doc: mockDoc }))  → infers () => …, zero args
collection: (...args: unknown[]) => mockCollection(...args),   // TS2556
// after — give the mock a rest signature so the spread has a target:
const mockCollection = vi.fn((..._args: unknown[]) => ({ doc: mockDoc }))
```
The same wrapper shape (`(...args: unknown[]) => mockX(...args)`) recurs in `invoice-paid.test.ts:55`, `payment-failed.test.ts:49`, `subscription-deleted.test.ts:40`, `subscription/portal/route.test.ts:20`, `webhooks/stripe/route.test.ts:26` + `:43` — apply the rest-signature fix to whichever `vi.fn()` each spreads into.

**Tuple-index (TS2493)** — `webhooks/stripe/route.test.ts:130` + `:149` read `mockRouteEvent.mock.calls[0][0]`. Type the spy with its call signature so `.mock.calls` element type is a real tuple:
```ts
const mockRouteEvent = vi.fn<(event: Stripe.Event) => Promise<void>>()   // vitest 4 vi.fn<T>() generic
```
(import `type Stripe from 'stripe'` if not already in the file.)

**Implicit-`any` (TS7006)** — `payment-failed.test.ts:301`, `subscription-deleted.test.ts:152` + `:218` have a callback param `c` (e.g. inside a `.find(...)`/`.filter(...)` over a mock-calls array). Read each site and annotate `c` with the element's real type (often `unknown[]` for a calls-array entry, then narrow, or the concrete arg type). Do not blanket-`any`.

**TS2554** — `auth/session/route.test.ts:125` is the one **non-mock** error and the one in an **auth (not billing)** test. Read `src/app/api/auth/session/route.ts` first: if the `DELETE` handler genuinely takes no `request`, call `DELETE()` in the test; if it should accept one, add `_request: Request`. Decide consistent with AC0's scope intent (this story is BF-1/Stripe — flag if it feels like Firebase/auth-track work, but it is a `*.test.ts` error and AC3 names "all `*.test.ts` errors").

### Files & contracts (read before editing)

- [apps/web/src/lib/stripe/server.ts](../../apps/web/src/lib/stripe/server.ts) — the pin (line 7) + `getStripe()` singleton + `retryStripeCall`. **Only line 7 changes.**
- [apps/web/src/lib/schemas/webhook-events.ts](../../apps/web/src/lib/schemas/webhook-events.ts) — `invoicePaidSchema` / `subscriptionDeletedSchema` / `paymentFailedSchema`. The dahlia `parent.subscription_details.subscription` nesting (lines 7–13, 40–47) is load-bearing — **do not regress** (INVARIANT 6; Story 4.2 history). **No edits expected here.**
- [apps/web/src/lib/stripe/webhooks.ts](../../apps/web/src/lib/stripe/webhooks.ts) — the three handlers + `routeEvent`; consumes the schemas + `getStripe()`. Read for context; **no edits** (the self-namespace-import spy pattern at line 20 is intentional — do not "clean up").
- Test files (the AC3 edit surface): `src/app/api/auth/session/route.test.ts`, `src/app/api/subscription/route.test.ts`, `src/app/api/subscription/portal/route.test.ts`, `src/app/api/webhooks/stripe/route.test.ts`, `src/lib/stripe/{invoice-paid,payment-failed,subscription-deleted}.test.ts`.

### Anti-patterns / disasters to avoid

1. **Assuming the pin bump fixes the test errors.** It fixes exactly error #1. The 13 test errors are independent — fix each explicitly or `typecheck` stays red.
2. **Silencing with `any` / `@ts-expect-error` / eslint-disable.** AC3 wants real types on the mocks/params. Suppressions will fail review.
3. **Regressing the dahlia nesting.** Flattening `parent.subscription_details.subscription` → `subscription` re-breaks invoice.paid/payment_failed (Story 4.2 already fixed this once). Schemas are out of edit scope.
4. **Scope creep into the Zod-4/RHF `.tsx` errors without resolving AC0.** Default is Option A (leave them). Don't silently bump `@hookform/resolvers`.
5. **Adding a dependency or changing runtime code.** AC7 — `package.json` unchanged; `webhooks.ts`/`server.ts` logic unchanged (only the pin literal).
6. **Trusting the stale `__tests__/` path** in the epics AC. Tests are co-located next to source (`src/lib/stripe/webhooks.test.ts`), not in a `__tests__/` dir.

### Testing standards

Web tests are **Vitest** (`vitest@^4`, `pnpm --filter web test` → `vitest run`), co-located `*.test.ts`. No new tests in this story — AC4's existing suite is the regression gate. Verify both gates: `typecheck` (the deliverable) and `test` (the no-regression guard). The runtime suite should already be green pre-change because the errors are type-only.

### Dependencies, sprint-fit, project structure

- **Dependencies:** None. Independent of the AR-spike and the Firebase migration ([epics-and-stories.md:806](../epics-and-stories.md#L806)) — can land in parallel.
- **Sprint-fit:** fits-in-one-sprint (genuinely small: 1-line pin + ~13 test-typing fixes across 6 files; the only judgment call is AC0).
- **Branch / delivery:** `story-1-3-stripe-api-pin-bump` off `main`; Two-PR + local `--no-ff` per [[feedback_two_pr_docs_execution]] (gh historically unauthenticatable non-interactively here — confirm at PR time).
- **Adjacent prior art** (git): Stripe webhook surface built in Stories 4.1 (`eaa2dab`), 4.2 (`688828b` invoice.paid), 4.3 (`b1451e6` subscription.deleted + payment_failed), dashboard 5.1 (`988f43a`). The dahlia nesting + self-namespace spy patterns originate there.

### Project Structure Notes

- `apps/web` is **Next.js with breaking changes vs. public docs** — per `apps/web/AGENTS.md`, consult `node_modules/next/dist/docs/` before writing Next.js code. (Relevant only if AC0=Option B or the TS2554 fix touches `auth/session/route.ts`.)
- `STRIPE_API_VERSION` lives only in `server.ts:7`; the `api_version` strings in `route.test.ts:50` + `:124` are **inbound-event fixtures**, not the SDK pin (see AC5 note).

### References

- [epics-and-stories.md#Story-1.3](../epics-and-stories.md#L790) — AC source (note: the `__tests__/` path and the "webhook-events.ts in stripe/" location are stale; real paths corrected above).
- [prd.md:586](../prd.md#L586) — PRD Decision #4 (default-to-bump; freeze fallback).
- [epics-and-stories.md:3166](../epics-and-stories.md#L3166) — INVARIANT 6 (dahlia nesting preserved by this story).
- [Stripe Dahlia changelog](https://docs.stripe.com/changelog/dahlia) · [2026-04-22 entries](https://docs.stripe.com/changelog/dahlia/2026-04-22/fulfillment-error-to-issuing-card-cancellation-and-replacement) · [SDK versioning](https://docs.stripe.com/sdks/versioning).

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-06-09 | 0.1 | Story created via /bmad-create-story. Ground-truth `tsc` audit (16-error map), AC2 changelog finding (04-22 non-breaking), AC0 scope decision for the 2 Zod/RHF `.tsx` errors, stale-path corrections. | Stephane (create-story) |
| 2026-06-09 | 0.2 | Implemented via /bmad-dev-story (AC0=Option A). Pin bumped; 13 in-scope `*.test.ts` errors fixed (no `any`/suppressions). typecheck 16→2 baseline. Scope Adjustment #1: discovered the runtime suite was pre-broken (133 component-test failures, out of scope); AC4 re-scoped to the 77-test changed-code surface (all green). Status → review. | Amelia (dev-story) |

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Amelia, /bmad-dev-story)

### Debug Log References

- Baseline (zero edits): `pnpm --filter web typecheck` → 16 errors (matched the map); `pnpm --filter web test` → **133 failed / 192 passed, 8 errors**.
- Post-change: `typecheck` → 2 errors (`EmailSignInForm.tsx`, `RegistrationForm.tsx` only). `test` (9 touched files: `src/lib/stripe/**`, `src/app/api/webhooks/**`, `auth/session`, `subscription`, `subscription/portal`) → **77 passed**.
- `git diff --stat apps/web/package.json` → empty (AC7).

### Completion Notes List

- **AC0 = Option A.** The 2 `.tsx` Zod-4/`@hookform/resolvers` `TS2769` errors are left as the documented baseline (out of BF-1 scope).
- **AC1:** one-line pin `server.ts:7` → `'2026-04-22.dahlia'`.
- **AC3 fixes are type-only, no behavior change:** root cause was `vi.fn(() => X)` inferring a strict zero-arg signature (vs. bare `vi.fn()` which is permissive `(...args: any[])`). Fix = give each *spread-called* mock a `(..._args: unknown[])` rest signature; this also resolved the two `.mock.calls[0][0]` tuple-index errors on `mockRouteEvent`. Implicit-`any` `.filter` callbacks annotated `(c: unknown[])`. The lone `TS2554` was a test passing `request` to the 0-arg `DELETE()` handler — dropped the arg.
- **AC2 verified:** `2026-04-22.dahlia` is non-breaking (dahlia breaking changes were in the prior `2026-03-25` pin); freeze-fallback not triggered.
- **⚠️ AC4 / Scope Adjustment #1 (needs user awareness):** `pnpm --filter web test` is **not** fully green — 133 pre-existing component/hook render failures (empty-DOM, React/@testing-library/jsdom environment breakage) exist independent of this story (present before any edit). Recommend filing a separate story to repair the web test environment. This story introduced **zero** regressions and the webhook-schema-parse intent of AC4 is verified green.
- **AC5/AC6 [HELD]:** Stripe Dashboard endpoint api_version → `2026-04-22.dahlia` + `docs/deployment-guide.md` note, and `review → done` flip, are post-merge admin.

### File List

- `apps/web/src/lib/stripe/server.ts` (modified — pin bump, 1 line)
- `apps/web/src/lib/stripe/invoice-paid.test.ts` (modified — mock rest signature)
- `apps/web/src/lib/stripe/payment-failed.test.ts` (modified — mock rest signature + `(c: unknown[])`)
- `apps/web/src/lib/stripe/subscription-deleted.test.ts` (modified — mock rest signature + 2× `(c: unknown[])`)
- `apps/web/src/app/api/webhooks/stripe/route.test.ts` (modified — 2 mock rest signatures + 2 api_version fixtures)
- `apps/web/src/app/api/subscription/route.test.ts` (modified — mock rest signature)
- `apps/web/src/app/api/subscription/portal/route.test.ts` (modified — mock rest signature)
- `apps/web/src/app/api/auth/session/route.test.ts` (modified — drop unused `request`, call `DELETE()`)

## Review Findings

> /bmad-code-review (2026-06-09, Stephane). Three adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) at session model capability. **Verdict: clean.** 0 decision-needed, 0 patch, 1 defer, 1 dismissed. AC1/AC3/AC4/AC7 independently verified green (typecheck → only the 2 AC0 baseline `.tsx` errors; INVARIANT 6 nesting intact at `webhooks.ts:34`/`:176`; `package.json`/`webhooks.ts`/`coupons.ts`/schemas untouched; pin literal `2026-04-22.dahlia` confirmed = installed `stripe@22.1.1` `LatestApiVersion`; `DELETE()` confirmed 0-arg at `route.ts:52`).

- [x] [Review][Defer] Stale `2026-03-25.dahlia` reference in schema comment [apps/web/src/lib/schemas/webhook-events.ts:3] — deferred, pre-existing. Historically accurate (that version *introduced* the `parent.subscription_details.subscription` nesting), but it is now the sole surviving old-version string in `apps/web/src` and reads as stale after the pin bump. Out of AC7 edit scope (schemas untouched); cosmetic only.
