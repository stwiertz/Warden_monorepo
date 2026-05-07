# Story 4.3: Process subscription.deleted and payment_failed Webhooks

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the Warden platform,
I want `customer.subscription.deleted` and `invoice.payment_failed` webhook events to atomically reflect the terminal/degraded subscription state on the corresponding `users/{uid}` document in Firestore,
So that dashboard reads in Epic 5 surface accurate `canceled` / `past_due` states without races, without resurrecting deleted users, and without double-processing.

## Human Prerequisites

*(Carried pattern from Stories 4.1/4.2 — Epic 3 retro action item #7. Tick each before starting Task 1; the dev agent cannot execute these.)*

- [x] **Story 4.2 is `done`** in [sprint-status.yaml](_bmad-output/implementation-artifacts/sprint-status.yaml) and the `invoice.paid` manual smoke (Story 4.2 Task 10) is green. The dahlia API-drift fix from Story 4.2's Change Log landed and full suite is **268/268** at the start of this story.
- [x] **`stripe listen --forward-to localhost:3000/api/webhooks/stripe`** running in a dedicated terminal. Task 10's smoke drives `stripe trigger customer.subscription.deleted` and `stripe trigger invoice.payment_failed` against it.
- [x] **Current `STRIPE_WEBHOOK_SECRET`** present in `.env.local` — the rotated secret from Story 4.1 (Epic 3 retro #5). If you've run `stripe listen` since Story 4.2 and the secret rotated, update `.env.local` first. **Never paste it into this transcript, chat, or any log.**
- [x] **`FIREBASE_SERVICE_ACCOUNT_KEY`** present in `.env.local` (Story 2.4). Both handlers in this story actually write to `users/{uid}`; a missing key crashes at the first `adminDb.collection('users')` call.
- [x] **An existing test Stripe subscription attached to a known Firebase uid.** The easiest path: run a fresh `/pricing` → monthly checkout with a known test user (you'll need `uid`, `subscription_id`, `customer_id` for Task 10 verification). If Story 4.2's smoke already left one behind, reuse that one; otherwise provision a fresh one.
- [x] **Firestore Console access** (or `firebase firestore:query` CLI) to inspect `users/{uid}` before and after each smoke step. Task 10 hinges on visual confirmation that `status` flipped to `past_due` then `canceled` without losing `plan`, `stripe_subscription_id`, `stripe_customer_id`, or `current_period_end`.

## Acceptance Criteria

1. **Given** the `handleSubscriptionDeleted(event: Stripe.Event): Promise<void>` and `handlePaymentFailed(event: Stripe.Event): Promise<void>` exports in [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) (currently no-op stubs from Story 4.1, unchanged through Story 4.2)
   **When** this story lands
   **Then** both function signatures are **unchanged** (`(event: Stripe.Event): Promise<void>`) so `routeEvent` and [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts)'s spy-based dispatch tests continue to pass without modification
   **And** both function bodies replace the `console.log` stub with the real logic described in ACs #3–#7
   **And** the `import * as self from './webhooks'` self-namespace pattern at the top of [webhooks.ts](src/lib/stripe/webhooks.ts) (load-bearing for `vi.spyOn` interception — Story 4.1 Completion Notes, confirmed working through Story 4.2) is **untouched** — do not remove or "clean up" it
   **And** `handleInvoicePaid` is **not** modified — Story 4.2's implementation is frozen; this story only edits the two remaining stubs

2. **Given** the Zod schema module [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts) (Story 4.2 added `invoicePaidSchema`)
   **When** this story lands
   **Then** two new exports are **added additively** — the `invoicePaidSchema` export is not renamed, not re-ordered, not touched:
   ```ts
   export const subscriptionDeletedSchema = z.object({
     id: z.string().min(1),                       // Stripe Subscription ID
     customer: z.union([
       z.string().min(1),
       z.object({ id: z.string().min(1) }),       // expanded object form
     ]),
     metadata: z.record(z.string(), z.string()).optional(),
   })

   export const paymentFailedSchema = z.object({
     customer: z.string().min(1),
     parent: z.object({
       subscription_details: z.object({
         subscription: z.string().min(1),
       }),
     }),
   })
   ```
   **And** inferred types are exported alongside:
   ```ts
   export type SubscriptionDeletedPayload = z.infer<typeof subscriptionDeletedSchema>
   export type PaymentFailedPayload = z.infer<typeof paymentFailedSchema>
   ```
   **And** both schemas use the `zod/v4` import path already present at the top of the file — do **not** switch to bare `zod`
   **And** both schemas are **narrow**: they validate only the fields the corresponding handler reads (same discipline as `invoicePaidSchema`). Do NOT expand `subscriptionDeletedSchema` to cover the full `Stripe.Subscription` type, and do NOT expand `paymentFailedSchema` to include `lines.data[0].period.end` — `payment_failed` does **not** advance `current_period_end`, so the field is not read and must not be parsed
   **And** the existing `invoicePaidSchema`'s `parent.subscription_details.subscription` path proves the dahlia shape fix from Story 4.2's Change Log is correct; `paymentFailedSchema` reuses the same nested path **not** a top-level `subscription` field — if you find yourself writing `subscription: z.string()` at the top level of `paymentFailedSchema`, you are reproducing the exact bug Story 4.2 fixed during its Task 10 smoke

3. **Given** a verified `Stripe.Event` of type `'customer.subscription.deleted'` flowing into `handleSubscriptionDeleted`
   **When** the handler begins processing
   **Then** it first narrows `event.data.object` to `Stripe.Subscription` (via `const subscription = event.data.object as Stripe.Subscription` — the `event.type` discriminator already narrows it in TS 5+, the `as` is defensive fallback)
   **And** the handler validates the subscription shape via `subscriptionDeletedSchema.safeParse(subscription)`. On failure: `console.error('[webhooks/stripe ${new Date().toISOString()}] customer.subscription.deleted payload failed schema validation:', parsed.error.issues, event.id)` and **throw** (route-level catch → 200 `routingError: true`, event stays in `stripe_events`)
   **And** the handler reads `firebase_uid` directly from `subscription.metadata?.firebase_uid` — **no `stripe.subscriptions.retrieve` call is made**, because `customer.subscription.deleted`'s `event.data.object` IS the Subscription, with full metadata already present (see Dev Notes → "Why `subscription.deleted` needs no retrieve call"). If `firebase_uid` is missing or empty, log `[webhooks/stripe ${timestamp}] customer.subscription.deleted missing firebase_uid metadata — cannot link to user:` + `event.id` + `subscription.id` and **throw** — the "legacy subscriptions created before Story 4.2's `subscription_data.metadata` fix" case, same as Story 4.2 AC #4
   **And** the handler coerces `customer` to a string: `const customerId = typeof subscription.customer === 'string' ? subscription.customer : subscription.customer.id` — Story 4.2's AC #5 guard against `[object Object]` regression, replicated here for parity
   **And** `retryStripeCall` is **not** imported into the deleted path — there is no Stripe API call to retry

4. **Given** a verified `Stripe.Event` of type `'invoice.payment_failed'` flowing into `handlePaymentFailed`
   **When** the handler begins processing
   **Then** it first narrows `event.data.object` to `Stripe.Invoice` (via `const invoice = event.data.object as Stripe.Invoice`)
   **And** the handler validates the invoice shape via `paymentFailedSchema.safeParse(invoice)`. On failure: `console.error('[webhooks/stripe ${timestamp}] invoice.payment_failed payload failed schema validation:', parsed.error.issues, event.id)` and **throw**
   **And** the handler resolves the subscription via `retryStripeCall(() => getStripe().subscriptions.retrieve(parsed.data.parent.subscription_details.subscription), 'subscriptions.retrieve')` — **same** `retryStripeCall` helper Story 4.2 Task 2 added to [src/lib/stripe/server.ts](src/lib/stripe/server.ts). Do NOT write a new retry helper. Do NOT copy the 250ms/750ms backoff inline. The Task 2 helper is the canonical retry primitive for Epic 4 webhook handlers
   **And** the retrieve call's catch: `console.error('[webhooks/stripe ${timestamp}] invoice.payment_failed subscription retrieve failed after retries:', event.id, subId, err)` and re-throw. The try/catch lives at the handler level, not inside `retryStripeCall` (same structural pattern as Story 4.2 Task 4.3 step 4)
   **And** the handler reads `firebase_uid` from the **retrieved** `subscription.metadata?.firebase_uid` — if missing, log + throw with tag `invoice.payment_failed subscription missing firebase_uid metadata — cannot link to user:` (same rationale as AC #3). **Do NOT** read `firebase_uid` from `invoice.parent.subscription_details.metadata` — that's a Stripe-immutable snapshot taken at invoice finalization, which may lag if the Subscription's metadata was updated; always use the live retrieved Subscription for consistency with Story 4.2's approach
   **And** `plan_id` is **not** validated in this handler — the `past_due` write does not change `plan`, so its correctness is Story 4.2's problem, not Story 4.3's. Do not duplicate the `PLAN_IDS` check here

5. **Given** `uid`, `stripe_subscription_id` (the resolved subscription ID string), and the event type are all resolved
   **When** the handler writes to Firestore
   **Then** the write happens inside a **Firestore transaction** via `adminDb.runTransaction(async (tx) => { ... })` (architecture.md:202-205, Story 4.2 AC #5 pattern)
   **And** the transaction body reads `const userRef = adminDb.collection('users').doc(firebaseUid); const snap = await tx.get(userRef)`
   **And** if `!snap.exists`, the handler logs `[webhooks/stripe ${timestamp}] ${event.type} user document not found — cannot update subscription state:` + `event.id` + `firebaseUid` and **throws** (no create branch — unlike Story 4.2's `invoice.paid`, which may legitimately create a brand-new user doc on first successful payment, `subscription.deleted` and `payment_failed` can ONLY fire after an `invoice.paid` has already materialized the user doc; a missing doc means an ordering/dedup bug upstream and must surface as a routing error, not a silent `tx.create`). See Dev Notes → "Why no create-branch on the terminal handlers"
   **And** if `snap.exists`, the handler branches on the event type:
   - **`customer.subscription.deleted`:** compute `const currentStatus = snap.data()?.status`. If `currentStatus === 'canceled'`, log `[webhooks/stripe ${timestamp}] customer.subscription.deleted already canceled — no-op:` + `event.id` + `firebaseUid` and **return from the transaction** (no write — idempotent noop; prevents a `updated_at` bump on replay). Otherwise `tx.update(userRef, { status: 'canceled', updated_at: FieldValue.serverTimestamp() })`
   - **`invoice.payment_failed`:** compute `const currentStatus = snap.data()?.status`. If `currentStatus === 'canceled'`, log `[webhooks/stripe ${timestamp}] invoice.payment_failed skipped — user already canceled:` + `event.id` + `firebaseUid` and **return from the transaction** (do NOT downgrade a canceled user to `past_due` — that resurrects a deleted subscription state). If `currentStatus === 'past_due'`, log `invoice.payment_failed already past_due — no-op:` and return (same idempotency reasoning as the deleted-already-canceled branch). Otherwise `tx.update(userRef, { status: 'past_due', updated_at: FieldValue.serverTimestamp() })`
   **And** the write uses `tx.update` (never `tx.set` with `{ merge: true }`, never `tx.create`) — same invariant as Story 4.2 Dev Notes → "Why `tx.update` on the exists-path". `tx.update` throws if the doc was deleted between the `tx.get` and the `tx.update` (account-deletion race with Story 6.2), which is the correct failure mode: surface to route-level catch, replay via `stripe_events`
   **And** **neither handler touches** `plan`, `current_period_end`, `stripe_subscription_id`, `stripe_customer_id`, or `created_at` fields. A `status`-only update deliberately preserves the last-known billing state so the dashboard in Epic 5 can still show "cancellation effective at `current_period_end`" for the cancel-at-period-end UX. Writing a field bag with only `status` + `updated_at` is the whole point — do not expand the bag "for completeness"

6. **Given** the transaction commits (or is a short-circuited idempotent no-op)
   **When** the handler returns
   **Then** on the **write path**, it logs:
   - Deleted: `[webhooks/stripe ${timestamp}] customer.subscription.deleted processed:` + `event.id` + `firebaseUid`
   - Payment failed: `[webhooks/stripe ${timestamp}] invoice.payment_failed processed:` + `event.id` + `firebaseUid` + `subscription.id`
   **And** on the **no-op path** (idempotent short-circuit per AC #5), the no-op log line from AC #5 is the ONLY log the handler emits — do NOT additionally log a `processed:` line on a no-op (operators reading Loki/Vector should be able to distinguish "wrote" from "skipped" via the tag)
   **And** both return `void` (the routing layer does not inspect return values)
   **And** the **whole handler's cumulative wall-clock budget** (Zod parse + optional `subscriptions.retrieve` + retries + Firestore transaction) must stay under the NFR14 5-second boundary. The deleted handler's tight path (no retrieve call, no retries) should land well under ~500ms; the payment_failed handler's tight path under ~1.5s

7. **Given** Story 4.1's route-level dedup transaction on `stripe_events` (route.ts lines 40–61) already intercepts duplicate event IDs before `routeEvent` is called
   **When** a duplicate `customer.subscription.deleted` or `invoice.payment_failed` arrives
   **Then** `handleSubscriptionDeleted` / `handlePaymentFailed` is **never invoked** for the duplicate. **No new dedup logic lives inside either handler** — same contract as Story 4.2 AC #8. The idempotent no-op branches in AC #5 are a second layer of defense (against `stripe_events` collection being manually cleared, against API-replay-with-forged-event-ids during operator triage, etc.), not the primary dedup mechanism

8. **Given** two new test files are added to the Stripe lib:
   - [src/lib/stripe/subscription-deleted.test.ts](src/lib/stripe/subscription-deleted.test.ts)
   - [src/lib/stripe/payment-failed.test.ts](src/lib/stripe/payment-failed.test.ts)

   *(One file per handler, following the Epic 3 retro maxim "one canonical test file per behavior" and the Story 4.2 precedent of keeping `invoice-paid.test.ts` separate from `webhooks.test.ts`. Do NOT combine the two new handlers into one file — each has enough distinct cases that merging would cross 400 lines and muddle the test-name grep.)*
   **When** `npx vitest run` is executed
   **Then** both files use the **same mock topology as [invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts)** (lifted, not reinvented — Epic 3 retro #3 "do not re-discover the Vitest v4 ES-module gotcha"):
   - `vi.mock('stripe', ...)` plain-function constructor
   - `vi.mock('@/lib/firebase/admin', ...)` with `adminDb.runTransaction` + `adminDb.collection(...).doc(...)` stubs that return a stable `userRef`
   - `vi.mock('@/lib/stripe/server', ...)` with `getStripe().subscriptions.retrieve` stubbed for `payment-failed.test.ts`. **For `subscription-deleted.test.ts`, `getStripe` is NOT stubbed — the handler does not call it, and a stubbed-but-unused mock is a smell** (if you write `vi.mock('@/lib/stripe/server')` in `subscription-deleted.test.ts`, delete it; the `firebase-admin` mock is all that's needed)
   - `retryStripeCall` stubbed to directly invoke its callback on happy-path tests in `payment-failed.test.ts`; the real helper is exercised (via `importOriginal`) in the one retry case per Task 7.5
   **And** the `subscription-deleted.test.ts` cases and all pass:
   - **Happy path — active user** — `event.data.object` is a valid subscription with `metadata.firebase_uid: 'uid_abc'`, fake `tx.get(users/uid_abc)` resolves `{exists: true, data: () => ({ status: 'active', plan: 'monthly', ... })}` → `tx.update` called exactly once with `{ status: 'canceled', updated_at: <serverTimestamp> }`. **Negative assertion:** the `tx.update` field bag does **not** contain `plan`, `current_period_end`, `stripe_subscription_id`, `stripe_customer_id`, or `created_at` (the whole point of AC #5's preservation clause — this is the canonical regression guard)
   - **Happy path — past_due user** (was past_due, now getting canceled) — same as above but `snap.data().status === 'past_due'` → `tx.update` called with `status: 'canceled'`
   - **Idempotent no-op — already canceled** — `snap.data().status === 'canceled'` → `tx.update` NOT called, `tx.set` NOT called, `tx.create` NOT called, `console.log` called with `[webhooks/stripe ...] customer.subscription.deleted already canceled — no-op:` tag, handler returns void (does NOT throw)
   - **User doc missing** — `snap.exists === false` → handler throws, `console.error` called with `user document not found — cannot update subscription state:` tag, `tx.update` NOT called
   - **Missing firebase_uid metadata** — `subscription.metadata = {}` → handler throws, `console.error` called with `missing firebase_uid metadata` tag, `runTransaction` NOT called (early exit before the transaction)
   - **Zod schema failure** — `event.data.object` missing `id` → handler throws, `console.error` called with `payload failed schema validation:` tag, `runTransaction` NOT called
   - **customer as expanded object** — `subscription.customer = { id: 'cus_obj' }` → handler completes (customerId is never written, but this test proves the schema's `z.union` branch accepts the expanded shape without crashing). This is a defensive test — if you find yourself asking "why are we testing a field we don't write?", the answer is: the schema's `z.union` must accept both branches, and a failing union parse would throw at `safeParse` before the handler can reach its real logic. Keep this test
   - **Transaction throws (Firestore permission-denied)** — fake `runTransaction` rejects with `Error('permission-denied')` → handler throws (propagates), no additional logging required (route-level catch owns that)
   - **Negative assertion: `getStripe` never called** — across all above tests, the `@/lib/stripe/server` module is NOT imported and `getStripe` is NOT invoked. This is the **structural** proof that `subscription.deleted` never reaches out to Stripe (AC #3). If a future refactor accidentally adds a retrieve call here, this assertion trips immediately. Implementation tip: because `@/lib/stripe/server` is not mocked in this file, any import of it would pull in the real lazy initializer, which would crash on a missing `STRIPE_SECRET_KEY` in the test env — a second, belt-and-braces tripwire
   **And** the `payment-failed.test.ts` cases exist and pass:
   - **Happy path — active user → past_due** — valid invoice, `subscriptions.retrieve` resolves with `{id, customer, metadata: {firebase_uid: 'uid_abc', plan_id: 'monthly'}}` (plan_id is read but UNUSED by this handler — see AC #4 — but Story 4.2's fixtures have it so factories can share shape), `snap.data().status === 'active'` → `tx.update` called with `{status: 'past_due', updated_at: <serverTimestamp>}`. **Negative assertion:** field bag does NOT contain `plan`, `current_period_end`, `stripe_subscription_id`, `stripe_customer_id`, or `created_at`
   - **Idempotent no-op — already past_due** — `snap.data().status === 'past_due'` → `tx.update` NOT called, `console.log` called with `already past_due — no-op:`, handler returns void
   - **Skip — user already canceled** — `snap.data().status === 'canceled'` → `tx.update` NOT called, `console.log` called with `skipped — user already canceled:`, handler returns void (does NOT throw — canceled is a terminal state and payment failures against already-canceled subscriptions are benign)
   - **User doc missing** — `snap.exists === false` → handler throws, `console.error` called with `user document not found — cannot update subscription state:`, `tx.update` NOT called
   - **Zod schema failure — missing parent.subscription_details.subscription** — payload builds `{parent: {subscription_details: {}}}` → handler throws, `console.error` called with `payload failed schema validation:`, `runTransaction` NOT called, `subscriptions.retrieve` NOT called (note the ordering — schema check runs BEFORE the retrieve call)
   - **Missing firebase_uid on retrieved subscription** — `subscriptions.retrieve` resolves with `{metadata: {}}` → handler throws, `console.error` tag `invoice.payment_failed subscription missing firebase_uid metadata`, `runTransaction` NOT called
   - **Transient Stripe error retried successfully** — exactly the Story 4.2 Task 7.6 pattern: DO NOT stub `retryStripeCall`; use the real helper (import via `importOriginal`) with `vi.useFakeTimers()`. Mock `subscriptions.retrieve` to reject once with a connection-like error, then resolve on the 2nd call. Advance timers by 249ms (assert still 1 call), then 2ms past 250ms (assert 2 calls) — same Story 4.2 M2 precision guard. `vi.useRealTimers()` in `afterEach`
   - **Non-transient Stripe error NOT retried** — `subscriptions.retrieve` rejects with `{type: 'StripeInvalidRequestError', statusCode: 400}` → exactly 1 call, handler throws, `runTransaction` NOT called
   - **Transient errors exhaust retry budget** — 3 rejections with connection errors → exactly 3 calls, handler throws, `runTransaction` NOT called. **Do NOT duplicate Story 4.2's retry-helper coverage beyond these three cases** (happy + non-transient + exhaustion). The `[stripe/retry]` internal logs are already asserted in `invoice-paid.test.ts`; here you only need to prove the handler wires the helper correctly
   - **Firestore transaction throws** — `runTransaction` rejects with `Error('aborted')` → handler throws (propagates)
   **And** both test files use `vi.stubEnv` / `vi.unstubAllEnvs()` for any env setup, matching Story 4.2 AC #9's pattern

9. **Given** the dispatch layer in [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts)'s `routeEvent`
   **When** this story lands
   **Then** the **existing** spy-based dispatch tests in [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts) continue to pass **without modification**. The `vi.spyOn(webhooksModule, 'handleSubscriptionDeleted').mockResolvedValue()` / `vi.spyOn(webhooksModule, 'handlePaymentFailed').mockResolvedValue()` spies intercept before the real body runs, so the dispatch test remains oblivious to the new implementation
   **And** similarly, [src/app/api/webhooks/stripe/route.test.ts](src/app/api/webhooks/stripe/route.test.ts) continues to pass unmodified (route tests mock `@/lib/stripe/webhooks` entirely). If either test file trips, do NOT rewrite them — the bug is in `webhooks.ts`'s self-namespace pattern or export shape, fix that

10. **Given** the testing baseline at the start of this story (**268 / 268** — the post-Story-4.2-Code-Review + dahlia-fix count from Story 4.2's Change Log entry dated 2026-04-15)
    **When** this story lands
    **Then** `npx vitest run` (or `npx vitest run --no-file-parallelism` if Epic 3 retro #6 flake reappears) reports **> 268** passing with **zero failures** (target: roughly 285–300; exact count advisory, the floor is the no-regression guard)
    **And** `npm run build` passes with zero type errors
    **And** `npm run lint` shows **0 errors, 0 warnings** (Epic 3 retro #10 — preserve the 0/0 baseline through all of Epic 4)
    **And** `npm run build` is listed as a distinct Task 10 line item, not bundled with lint + vitest (Epic 3 retro #10)
    **And** the `/api/webhooks/stripe` route still emits as `ƒ (Dynamic) Node runtime` in the build manifest (regression guard from Story 4.1 AC #1) and **no new routes** appear in the manifest (this story adds lib files only)

## Tasks / Subtasks

- [x] **Task 1: Extend `webhook-events.ts` with the two new schemas** (AC: #2)
  - [x] 1.1 Open [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts). The file currently exports `invoicePaidSchema` and `InvoicePaidPayload`.
  - [x] 1.2 **Append** (do NOT re-order, do NOT touch `invoicePaidSchema`) the `subscriptionDeletedSchema` and `paymentFailedSchema` exports from AC #2. Keep the inline comment block about the dahlia relocation — it still explains the `parent.subscription_details.subscription` nesting for `paymentFailedSchema`, and future readers will need it.
  - [x] 1.3 Append the two inferred type exports: `SubscriptionDeletedPayload` and `PaymentFailedPayload`.
  - [x] 1.4 The `customer` field on `subscriptionDeletedSchema` uses `z.union([z.string(), z.object({id: z.string()})])`. Zod v4's union syntax: `z.union([A, B])` is the canonical form. Do NOT use `.or()` chaining; it's stylistically inconsistent with the existing `invoicePaidSchema`.
  - [x] 1.5 **Do NOT write a standalone schema test file.** The schemas are exercised through `subscription-deleted.test.ts` and `payment-failed.test.ts` in Task 6/7 — a standalone schema test would re-test Zod's library behavior (Story 4.2 Task 3.5 precedent).

- [x] **Task 2: Implement `handleSubscriptionDeleted`** (AC: #1, #3, #5, #6)
  - [x] 2.1 Open [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts). Locate `export async function handleSubscriptionDeleted(event: Stripe.Event): Promise<void>` (currently the stub with a single `console.log`).
  - [x] 2.2 Add the imports. The file already imports `FieldValue`, `Timestamp`, `Stripe` type, `adminDb`, `PLAN_IDS`, `invoicePaidSchema`, `getStripe`, `retryStripeCall`. You need to add:
    ```ts
    import { subscriptionDeletedSchema, paymentFailedSchema } from '@/lib/schemas/webhook-events'
    ```
    to the existing `@/lib/schemas/webhook-events` import line (merge into the existing `{ invoicePaidSchema }` destructure — do NOT create a duplicate import line).
    **Do NOT** import `Timestamp` for this handler — it is unused in the status-only field bag. The existing `Timestamp` import stays because `handleInvoicePaid` still uses it.
    **Do NOT** import `PLAN_IDS` for the deleted handler — `plan` is not touched. The existing `PLAN_IDS` import stays because `handleInvoicePaid` uses it.
  - [x] 2.3 Rewrite the body. Sequence:
    1. `const subscription = event.data.object as Stripe.Subscription`
    2. `const parsed = subscriptionDeletedSchema.safeParse(subscription)` → if `!parsed.success`, `console.error` with tag `customer.subscription.deleted payload failed schema validation:` + issues + event.id, throw
    3. `const firebaseUid = parsed.data.metadata?.firebase_uid` → if falsy, `console.error` with tag `customer.subscription.deleted missing firebase_uid metadata — cannot link to user:` + event.id + subscription.id, throw
    4. (The `customerId` coercion from AC #3 is computed but NOT written — it's purely defensive parsing. If you feel the urge to store it, re-read AC #5: `neither handler touches stripe_customer_id`. Leave the variable unassigned or omit the computation; the Zod schema already proved the union parses, which is the real guard)
    5. Run the transaction (see Task 2.4)
    6. On the write path, log: `[webhooks/stripe ${new Date().toISOString()}] customer.subscription.deleted processed:` + event.id + firebaseUid
  - [x] 2.4 Transaction body (inside `await adminDb.runTransaction(async (tx) => { ... })`):
    ```ts
    const userRef = adminDb.collection('users').doc(firebaseUid)
    const snap = await tx.get(userRef)
    if (!snap.exists) {
      console.error(
        `[webhooks/stripe ${new Date().toISOString()}] customer.subscription.deleted user document not found — cannot update subscription state:`,
        event.id,
        firebaseUid,
      )
      throw new Error('customer.subscription.deleted user document not found')
    }
    const currentStatus = snap.data()?.status
    if (currentStatus === 'canceled') {
      console.log(
        `[webhooks/stripe ${new Date().toISOString()}] customer.subscription.deleted already canceled — no-op:`,
        event.id,
        firebaseUid,
      )
      return
    }
    tx.update(userRef, {
      status: 'canceled',
      updated_at: FieldValue.serverTimestamp(),
    })
    ```
    **Critical:** the `return` inside the transaction closure short-circuits the write but lets `runTransaction` resolve normally — the handler's post-transaction code then skips the success log because the success log should only fire on the write path (see AC #6). Achieve this by hoisting a `let didWrite = false` above the transaction, setting `didWrite = true` just before `tx.update`, and gating the success log on `if (didWrite)` after the transaction. This is cleaner than threading a return value out of the closure.
  - [x] 2.5 Do NOT add a try/catch around the `runTransaction` call. Route-level catch in [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts) is the single error boundary (Story 4.1 AC #6, Story 4.2 Task 4.4 precedent).
  - [x] 2.6 The old `console.log('[webhooks/stripe ...] customer.subscription.deleted received (handler not yet implemented):', event.id)` stub line is **deleted** — the new success log (and the no-op log) replace it.

- [x] **Task 3: Implement `handlePaymentFailed`** (AC: #1, #4, #5, #6)
  - [x] 3.1 Open [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts). Locate `export async function handlePaymentFailed(event: Stripe.Event): Promise<void>`.
  - [x] 3.2 The `@/lib/schemas/webhook-events` import line from Task 2.2 already covers `paymentFailedSchema`. No new imports.
  - [x] 3.3 Rewrite the body. Sequence:
    1. `const invoice = event.data.object as Stripe.Invoice`
    2. `const parsed = paymentFailedSchema.safeParse(invoice)` → fail → log with tag `invoice.payment_failed payload failed schema validation:`, throw
    3. `const subId = parsed.data.parent.subscription_details.subscription`
    4. `const subscription = await retryStripeCall(() => getStripe().subscriptions.retrieve(subId), 'subscriptions.retrieve')` wrapped in a try/catch. On catch: `console.error` with tag `invoice.payment_failed subscription retrieve failed after retries:` + event.id + subId + err, re-throw
    5. `const firebaseUid = subscription.metadata?.firebase_uid` → if falsy, log tag `invoice.payment_failed subscription missing firebase_uid metadata — cannot link to user:` + event.id + subscription.id, throw
    6. Run the transaction (see Task 3.4)
    7. On the write path, log: `[webhooks/stripe ${timestamp}] invoice.payment_failed processed:` + event.id + firebaseUid + subscription.id
  - [x] 3.4 Transaction body:
    ```ts
    const userRef = adminDb.collection('users').doc(firebaseUid)
    const snap = await tx.get(userRef)
    if (!snap.exists) {
      console.error(
        `[webhooks/stripe ${new Date().toISOString()}] invoice.payment_failed user document not found — cannot update subscription state:`,
        event.id,
        firebaseUid,
      )
      throw new Error('invoice.payment_failed user document not found')
    }
    const currentStatus = snap.data()?.status
    if (currentStatus === 'canceled') {
      console.log(
        `[webhooks/stripe ${new Date().toISOString()}] invoice.payment_failed skipped — user already canceled:`,
        event.id,
        firebaseUid,
      )
      return
    }
    if (currentStatus === 'past_due') {
      console.log(
        `[webhooks/stripe ${new Date().toISOString()}] invoice.payment_failed already past_due — no-op:`,
        event.id,
        firebaseUid,
      )
      return
    }
    tx.update(userRef, {
      status: 'past_due',
      updated_at: FieldValue.serverTimestamp(),
    })
    ```
    Same `didWrite` gating pattern as Task 2.4.
  - [x] 3.5 Do NOT import or validate `plan_id` — AC #4 final clause. The retrieved `subscription` has metadata, but we only read `firebase_uid`. A regression that reads `plan_id` here is a scope leak — if Story 4.3 starts validating plan shape, that's architectural drift.
  - [x] 3.6 The old `console.log('[webhooks/stripe ...] invoice.payment_failed received (handler not yet implemented):', event.id)` stub line is deleted.

- [x] **Task 4: Verify `routeEvent` dispatch and route tests** (AC: #1, #7, #9)
  - [x] 4.1 Re-read [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts). The spy-based dispatch tests for `'customer.subscription.deleted'` and `'invoice.payment_failed'` should still pass **without modification** — the spies intercept the module-level handler calls via the `import * as self from './webhooks'` pattern.
  - [x] 4.2 Run `npx vitest run src/lib/stripe/webhooks.test.ts` → must be green. If it fails, the self-namespace pattern has been broken (or you accidentally reassigned one of the handler exports); fix the export, do NOT touch the test.
  - [x] 4.3 Run `npx vitest run src/app/api/webhooks/stripe/route.test.ts` → must be green. Route tests use `vi.mock('@/lib/stripe/webhooks')` to replace all three handlers with `vi.fn()`s, so the real handler bodies never run at this level. A failure here means the `vi.mock` factory is mis-shaped; fix that, do NOT touch [route.ts](src/app/api/webhooks/stripe/route.ts).

- [x] **Task 5: Write `subscription-deleted.test.ts`** (AC: #8)
  - [x] 5.1 Create [src/lib/stripe/subscription-deleted.test.ts](src/lib/stripe/subscription-deleted.test.ts). **File location:** co-located with `webhooks.ts` and `invoice-paid.test.ts`. Do NOT place under `src/lib/stripe/__tests__/` — Story 4.2 established co-location at the lib level.
  - [x] 5.2 Hoist mocks via `vi.hoisted` ABOVE imports (Vitest auto-hoists `vi.mock`, but the factory closures need hoisted state for the test to drive per-case):
    - `vi.mock('@/lib/firebase/admin', ...)` — stub `adminDb.runTransaction` as a `vi.fn()` the tests control, `adminDb.collection(...).doc(...)` returning a stable `userRef` literal.
    - **Do NOT** `vi.mock('stripe')` — this handler has no Stripe SDK interaction.
    - **Do NOT** `vi.mock('@/lib/stripe/server')` — AC #8 explicit: the `getStripe` / `retryStripeCall` imports do not appear in the handler's compiled module graph for this test. If you're tempted because "the test file for `handleInvoicePaid` mocks it", re-read AC #8's "delete it" clause.
  - [x] 5.3 Import `handleSubscriptionDeleted` from `@/lib/stripe/webhooks`. Import `Stripe` type. Build a `makeDeletedEvent(overrides?: Partial<Stripe.Subscription>): Stripe.Event` factory at the top of the describe block.
  - [x] 5.4 Write the 8 cases from AC #8 under a single `describe('handleSubscriptionDeleted', ...)`. For the "customer as expanded object" case, make sure the factory builds `{customer: {id: 'cus_obj'}}` instead of `'cus_abc'` — this exercises the `z.union` second branch.
  - [x] 5.5 For the `tx.update` field-bag negative assertion (the one that proves `plan`, `current_period_end`, `stripe_subscription_id`, `stripe_customer_id`, and `created_at` are NOT in the write), assert on the **exact keys** of the second argument:
    ```ts
    const callArgs = mockTxUpdate.mock.calls[0]
    const fields = callArgs[1]
    expect(Object.keys(fields).sort()).toEqual(['status', 'updated_at'])
    expect(fields.status).toBe('canceled')
    ```
    `toMatchObject` is NOT sufficient here — it allows extra fields, which is exactly the regression we need to catch.
  - [x] 5.6 Run `npx vitest run src/lib/stripe/subscription-deleted.test.ts` → must be green (8 cases).

- [x] **Task 6: Write `payment-failed.test.ts`** (AC: #8)
  - [x] 6.1 Create [src/lib/stripe/payment-failed.test.ts](src/lib/stripe/payment-failed.test.ts).
  - [x] 6.2 Hoist mocks:
    - `vi.mock('stripe', ...)` plain-function constructor — lifted from [invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts).
    - `vi.mock('@/lib/firebase/admin', ...)` same shape as Task 5.2.
    - `vi.mock('@/lib/stripe/server', async (importOriginal) => { ... })` — stub `getStripe` with a fake whose `subscriptions.retrieve` is a `vi.fn()`. For the HAPPY-PATH and VALIDATION cases, also stub `retryStripeCall` to directly invoke its callback. For the TRANSIENT RETRY SUCCESSFUL / NON-TRANSIENT / EXHAUSTION cases, use `importOriginal` to get the real `retryStripeCall` — exactly the Story 4.2 Task 7.6 shape. **Split these into two `describe` blocks** (or two files) so the real-vs-stubbed distinction is clear. I recommend a single file with two describes to avoid a third test file.
  - [x] 6.3 Import `handlePaymentFailed`, `Stripe` type. Build a `makeFailedEvent(invoiceOverrides?: Partial<Stripe.Invoice>, subscriptionOverrides?: Partial<Stripe.Subscription>): Stripe.Event` factory. Note the dual override pattern — the invoice shape and the `subscriptions.retrieve` response are independent.
  - [x] 6.4 For the TRANSIENT RETRY SUCCESSFUL case: `vi.useFakeTimers()` in `beforeEach` of that describe block, `vi.useRealTimers()` in `afterEach`. Drive backoff with `vi.advanceTimersByTimeAsync(249)` (assert 1 call), then `vi.advanceTimersByTimeAsync(2)` (assert 2 calls). This is the exact Story 4.2 M2 precision pattern — do NOT advance by a round 250 or 300; the boundary matters.
  - [x] 6.5 For the `tx.update` field-bag negative assertion, same pattern as Task 5.5:
    ```ts
    expect(Object.keys(fields).sort()).toEqual(['status', 'updated_at'])
    expect(fields.status).toBe('past_due')
    ```
  - [x] 6.6 Write the 9 cases from AC #8's payment-failed list.
  - [x] 6.7 Run `npx vitest run src/lib/stripe/payment-failed.test.ts` → must be green.

- [x] **Task 7: Idempotent-replay regression test (AC #5, #7 defense-in-depth)**
  - [x] 7.1 Inside `subscription-deleted.test.ts`, add a test titled `'idempotent: replaying an already-processed customer.subscription.deleted is a no-op'`. This case is separate from the "already canceled" case because it proves the end-to-end contract: if `handleSubscriptionDeleted` is called twice with the same event (bypassing `stripe_events` dedup via an operator manual replay), the second call must be a clean no-op, not a write-and-log double.
    - Arrange: first call `snap.exists === true, status: 'active'`. Fake `runTransaction` drives the closure, closure calls `tx.update`. Second call: `snap.data().status === 'canceled'` (because the first call flipped it). Closure detects canceled, returns without `tx.update`. Assert: `tx.update` called exactly once across both invocations, `console.log('... already canceled — no-op:')` called exactly once on the second invocation.
  - [x] 7.2 Inside `payment-failed.test.ts`, add an analogous case: first call `status: 'active'` → writes `past_due`. Second call `status: 'past_due'` → no-op, logs `already past_due — no-op:`.
  - [x] 7.3 These tests do NOT exercise Story 4.1's `stripe_events` dedup (that's the route level). They exercise the in-handler idempotent branch — the second line of defense described in AC #7.

- [x] **Task 8: Self-namespace regression guard (AC #1)**
  - [x] 8.1 Add a single test in `webhooks.test.ts` — or verify an existing one covers this — that asserts `vi.spyOn(webhooksModule, 'handleSubscriptionDeleted').mockResolvedValue()` followed by `await webhooksModule.routeEvent({...deleted event...} as Stripe.Event)` invokes the spy exactly once and the real handler body is NOT reached. **Check first** — Story 4.1's dispatch test likely already covers this for the stubs; if it does, this task is a no-op and you document in Completion Notes that it's covered. Do NOT add a duplicate test.
  - [x] 8.2 Same check for `handlePaymentFailed`.
  - [x] 8.3 If either dispatch test is missing, add it. Fall back to the Story 4.1 dispatch test pattern — do NOT invent a new one.

- [x] **Task 9: Full-suite regression pass** (AC: #10)
  - [x] 9.1 `npx vitest run` — full suite green; count greater than 268. Target landing around 285–300 (17+ new cases split across two files). If the Epic 3 retro #6 Vitest file-parallelism flake trips on `src/app/dashboard/layout.test.tsx`, fall back to `npx vitest run --no-file-parallelism` and note it in Completion Notes. **Do not chase the flake in this story.**
  - [x] 9.2 `npm run lint` — 0 errors, 0 warnings. Watch specifically for `@typescript-eslint/no-unused-vars` on the Task 2.3 step-4 customer-coercion — if you compute `customerId` and never write it, that's an unused variable and lint will fail. Either omit the computation entirely (preferred per Task 2.3 parenthetical) or reference it in a comment-only way (NOT preferred — just delete the line).

- [x] **Task 10: `npm run build`** (AC: #10, separate task per Epic 3 retro #10)
  - [x] 10.1 `npm run build` — zero type errors.
  - [x] 10.2 Confirm `/api/webhooks/stripe` still appears as `ƒ (Dynamic) Node runtime` in the route manifest output (regression guard from Story 4.1 AC #1).
  - [x] 10.3 Confirm no new routes accidentally appeared in the manifest — this story adds lib files + test files only, no new `app/**/route.ts`.

- [x] **Task 11: Manual smoke with real Stripe listener** (AC: #6, human-verified)
  - [x] 11.1 **Prerequisite check:** confirm all Human Prerequisites checkboxes at the top of this story are ticked. If `stripe listen` is not running, the 200 OK will show in the Stripe CLI but no writes will land in Firestore (the dev server isn't forwarding).
  - [x] 11.2 **Confirm starting state.** Either reuse the test user + subscription from Story 4.2's smoke, or run a fresh monthly checkout via `/pricing`. In Firebase Console, confirm `users/{uid}` shows `status: 'active'`. Note the `uid`, `subscription_id`, and `customer_id`.
  - [x] 11.3 **Trigger `invoice.payment_failed`.** Run `stripe trigger invoice.payment_failed`. Stripe's trigger uses a throwaway subscription, so the handler will likely hit the "subscription missing firebase_uid metadata" throw path (AC #4 legacy case). That's **expected** — verify the dev-server log shows `[webhooks/stripe ...] invoice.payment_failed subscription missing firebase_uid metadata — cannot link to user:` and the route returns 200 `routingError: true`. The goal of this step is to prove the throw path doesn't crash the dev server.
  - [x] 11.4 **Force a `payment_failed` on your real test subscription.** There are two ways:
    - **Preferred:** in the Stripe Dashboard → Customers → your test customer → Subscriptions → your test subscription → update the default payment method to card `4000 0000 0000 0341` (fails on first charge) → click "Update subscription" → wait for next invoice (or force-close the current period). This path flows a real `invoice.payment_failed` with the right metadata.
    - **Alternative:** `stripe subscriptions update sub_XXX -d "default_payment_method=pm_card_chargeDeclinedInsufficientFunds"` + `stripe invoices pay in_XXX` to force a decline.
    Whichever path you use, verify in the dev-server log: `[webhooks/stripe ...] invoice.payment_failed processed:` + event.id + firebaseUid + subscription.id. Latency should be well under 5s.
  - [x] 11.5 **Verify Firestore.** Open `users/{uid}` in Firebase Console. Confirm:
    - `status: 'past_due'` (flipped from `active`)
    - `plan`: **unchanged** (still `'monthly'` or `'yearly'`)
    - `current_period_end`: **unchanged** Timestamp
    - `stripe_subscription_id`: **unchanged**
    - `stripe_customer_id`: **unchanged**
    - `updated_at`: advanced to the time of the webhook
    - `created_at`: **unchanged**
    This is the canonical AC #5 preservation guarantee. If ANY field other than `status` and `updated_at` changed, the field bag is wrong — stop and fix [webhooks.ts](src/lib/stripe/webhooks.ts) Task 3.4.
  - [x] 11.6 **Replay the `payment_failed` event.** Copy the event ID from 11.4's dev-server log and run `stripe events resend <event_id>`. Verify the dev-server log shows `[webhooks/stripe ...] duplicate event skipped:` (Story 4.1's `stripe_events` dedup). Verify in Firestore that `users/{uid}.updated_at` is **unchanged** (same millisecond value). This proves end-to-end dedup still works post-Story-4.3.
  - [x] 11.7 **Trigger `customer.subscription.deleted` on the real test subscription.** Two paths:
    - **Preferred:** Stripe Dashboard → your test subscription → Actions → "Cancel subscription" → choose "Cancel immediately". This fires `customer.subscription.deleted` with the real `metadata.firebase_uid` / `metadata.plan_id`.
    - **Alternative:** `stripe subscriptions cancel sub_XXX`.
    Verify dev-server log: `[webhooks/stripe ...] customer.subscription.deleted processed:` + event.id + firebaseUid.
  - [x] 11.8 **Verify Firestore after cancel.** Confirm `users/{uid}`:
    - `status: 'canceled'` (flipped from `past_due`)
    - All other fields **unchanged** except `updated_at`
    This proves the `past_due → canceled` transition and the field preservation invariant.
  - [x] 11.9 **Replay the `subscription.deleted` event.** `stripe events resend <event_id>`. Verify `duplicate event skipped:` log (route-level dedup). Verify `updated_at` unchanged.
  - [x] 11.10 **Idempotent in-handler branch check.** In Firestore Console, manually delete the document in the `stripe_events` collection matching the `customer.subscription.deleted` event ID from step 11.7. Then run `stripe events resend <event_id>` again. This bypasses the route-level dedup and drives the event down to `handleSubscriptionDeleted`. Verify the dev-server log shows `[webhooks/stripe ...] customer.subscription.deleted already canceled — no-op:` (AC #5 in-handler idempotent branch, NOT a write, NOT a `processed:` log). Verify in Firestore that `users/{uid}.updated_at` is STILL unchanged from step 11.8. This is the end-to-end proof of AC #5's no-op branch.
  - [x] 11.11 **Trigger `invoice.payment_failed` against the now-canceled user.** Via the Dashboard "retry payment" button (if available) or by triggering a fresh invoice on the canceled subscription. Verify the dev-server log shows `[webhooks/stripe ...] invoice.payment_failed skipped — user already canceled:` — not `processed:`. Verify `users/{uid}.status` remains `canceled` (did NOT downgrade to `past_due`). This is the AC #5 "don't resurrect a canceled user" guarantee, end-to-end verified.
  - [x] 11.12 Document results in Completion Notes. If any step fails, **stop and file a defect against this story**; do not mark it done. Specifically flag any Stripe-SDK-shape drift analogous to Story 4.2's dahlia defect — the `paymentFailedSchema` is almost certainly the riskiest line in this story because it depends on the same `parent.subscription_details.subscription` path that Story 4.2 discovered was wrong on first live test.

## Dev Notes

### Why `subscription.deleted` needs no retrieve call (but `payment_failed` does)

Stripe's `customer.subscription.deleted` event has `event.data.object: Stripe.Subscription` — the full Subscription object, with `metadata` already populated, is in the payload itself. There is no need to `stripe.subscriptions.retrieve(id)` to look up the metadata; it's right there.

Contrast with `invoice.payment_failed`: `event.data.object: Stripe.Invoice`. The Invoice doesn't carry subscription metadata directly (it carries `parent.subscription_details.metadata` as an **immutable snapshot** at invoice finalization time, which is a different thing — see "Why we don't read firebase_uid from invoice.parent.subscription_details.metadata" below). So `payment_failed` must retrieve the Subscription to get the live metadata.

The asymmetry is intentional: `subscription.deleted` is a Subscription-lifecycle event, so Stripe inlines the Subscription. `payment_failed` is an Invoice-lifecycle event, so Stripe inlines the Invoice. The handlers reflect this data shape, not a "we decided to be inconsistent" choice.

Practical consequence: `handleSubscriptionDeleted` doesn't need `retryStripeCall`, doesn't need `getStripe`, doesn't need the NFR13 retry budget. It's just "parse → transact → log". This makes its tight path fast (<500ms) and its failure surface minimal.

### Why we don't read `firebase_uid` from `invoice.parent.subscription_details.metadata`

Story 4.2's Change Log notes this as a "potential future optimization" — reading metadata directly from the invoice's nested `parent.subscription_details` instead of retrieving the subscription. The reasoning for NOT doing it in Story 4.3:

1. **Consistency with Story 4.2.** `handleInvoicePaid` retrieves the subscription and reads metadata from there. If `handlePaymentFailed` reads metadata from a different source, a future operator debugging "why is payment_failed resolving uid X but invoice_paid resolving uid Y for the same subscription?" has to reason about two different data sources. One source → one mental model.
2. **Snapshot staleness risk.** `invoice.parent.subscription_details.metadata` is the metadata **at the time the invoice was finalized**. If the subscription metadata was updated between finalization and the `payment_failed` event (operator ran a metadata migration, a bug added a field, etc.), the invoice's snapshot is stale. Calling `subscriptions.retrieve` gets the live value. Staleness is rare in practice but non-zero risk.
3. **The optimization isn't load-bearing.** `retryStripeCall` + one extra API call costs ~200–400ms on the tight path, well inside the NFR14 5s budget. Removing it doesn't unlock any new behavior.

If at some future point NFR14 pressure tightens (say, Stripe response times climb and the 5s budget starts biting), revisit this decision. Until then, the retrieve-based path is the canonical pattern.

### Why no create-branch on the terminal handlers

Story 4.2's `handleInvoicePaid` has a `tx.create` branch for the "user doc doesn't exist yet" case — legitimate because a brand-new successful subscription may arrive before the user doc was materialized by any Firebase/Firestore path (Story 2.x's `createSessionCookie` may not have written a doc).

Story 4.3's handlers do NOT have a create branch. Why: `customer.subscription.deleted` and `invoice.payment_failed` can ONLY fire for subscriptions that already exist in Stripe, which means an `invoice.paid` must have fired first, which means Story 4.2's handler must have already created (or updated) the `users/{uid}` doc. If a `deleted` or `payment_failed` arrives and the user doc is missing, exactly one of these is true:
- An `invoice.paid` was lost / dropped / never processed. (Operator issue — manual replay from `stripe_events`.)
- An out-of-order delivery race landed the terminal event before the creation event. (Stripe at-least-once guarantees ordering within a short window; pathological.)
- A developer manually deleted the user doc. (Test environment.)
- A different bug.

In every case, **silently creating a canceled or past_due user doc is the wrong response** — it would obscure the upstream bug and leave a user in a terminal state with no billing history. Surfacing as a route-level `routingError: true` + a stuck `stripe_events` entry forces the operator to investigate.

This is why AC #5 says "no create branch" and why the Task 2.4 / 3.4 transactions throw on `!snap.exists` rather than `tx.create`.

### Why `status`-only writes (not a full field bag)

Story 4.2's `handleInvoicePaid` writes a rich field bag: `status`, `plan`, `current_period_end`, `stripe_subscription_id`, `stripe_customer_id`, `updated_at` (+ `created_at` on create). The rationale there is that `invoice.paid` is the **source of truth** for an active subscription — it advances `current_period_end`, confirms the plan, etc.

Story 4.3's handlers write only `status` + `updated_at`. The rationale:
- **`plan` must be preserved.** A canceled or past_due user's dashboard in Epic 5 needs to display "Your yearly plan was canceled" — the plan name is required UX context. Overwriting it would wipe that.
- **`current_period_end` must be preserved.** The `cancel-at-period-end` UX in Story 5.5 ("Your subscription is canceled. You have access until Apr 30, 2027.") requires `current_period_end` to remain the last-active period-end. Writing `null` or `0` would break that copy.
- **`stripe_subscription_id` must be preserved.** If an operator needs to manually investigate a canceled user's billing history, the subscription ID is the anchor. Wiping it makes support triage harder.
- **`stripe_customer_id` must be preserved** for the same reason (Stripe Customer Portal deep-links, support triage).

The write surface is intentionally minimal — terminal state transitions **augment** the historical record, they don't replace it. AC #5's negative assertion and Task 5.5 / 6.5's `Object.keys(fields).sort()` test are the canonical regression guards.

### Why the idempotent no-op branches are belt-and-braces (and still required)

Story 4.1's `stripe_events` collection is the primary dedup mechanism. It catches 99.9% of duplicate deliveries at the route level before `routeEvent` is even called. So why do the Story 4.3 handlers also have in-handler idempotent branches (`status === 'canceled'` → no-op)?

Three scenarios where the in-handler branch kicks in:
1. **Operator manually cleared `stripe_events`.** Test environments, debugging, or intentional replay-all-events scripts will bypass route-level dedup. The in-handler branch ensures the replay is still idempotent.
2. **Stripe API version mismatch creates "different" event IDs for logically-the-same event.** Rare but non-zero — if Stripe's API changes and a live event has two delivery attempts with slightly different IDs, the in-handler branch is the last line of defense.
3. **Bug in the route-level dedup.** If Story 4.1's `runTransaction` over `stripe_events` has a bug that a future refactor introduces, the in-handler branches prevent a double-write at the user level.

The cost of the in-handler branch is tiny: one `.data()?.status` read and a `===` comparison. The benefit is that the "wrote twice" regression has two independent guards instead of one. Task 7's idempotent-replay regression tests prove this branch works.

### Previous Story Intelligence (carried from Stories 4.1 and 4.2)

*Each bullet is concrete and actionable; if something here contradicts a Task above, the Task wins and please flag the contradiction in Completion Notes.*

- **`import * as self from './webhooks'` is load-bearing.** Do NOT remove it. Tasks 4.1/4.2 depend on `vi.spyOn` continuing to intercept intra-module calls. Story 4.1 Completion Notes explain why. Story 4.2 confirmed it still works after `handleInvoicePaid` was implemented.
- **`retryStripeCall` has a 5xx-class nuance.** Story 4.2's Code Review H1 fix narrowed `isTransientStripeError` so `StripeAPIError` is transient only on 5xx OR absent `statusCode`. Do NOT regress this. The `payment-failed.test.ts` non-transient test case in AC #8 uses `{type: 'StripeInvalidRequestError', statusCode: 400}` specifically to prove the 4xx fast-fail path.
- **The dahlia API drift bug from Story 4.2.** Stripe API version `2026-03-25.dahlia` (pinned in [src/lib/stripe/server.ts:7](src/lib/stripe/server.ts#L7)) removed `invoice.subscription` and relocated it to `invoice.parent.subscription_details.subscription`. `paymentFailedSchema` in this story uses the same nested path. **If you find yourself writing `subscription: z.string()` at the top level of `paymentFailedSchema`, STOP — you are reproducing the exact bug Story 4.2 fixed during its Task 10 smoke.** Task 11.12 is the live-smoke verification; an identical defect on `payment_failed` would be found the hard way.
- **Plain-function `Stripe` constructor mock pattern.** Lifted verbatim from [invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts) and [session/route.test.ts](src/app/api/checkout/session/route.test.ts). Epic 3 retro #3 — do not re-discover the Vitest v4 ES-module-constructor gotcha.
- **Never a silent `catch {}`.** Every new `catch` in this story's code logs via `console.error` with a `[webhooks/stripe]` prefix before acting. A reviewer will `rg -n 'catch \{' src/lib/stripe` and any hit without an immediate `console.error` is a defect. Epic 3 retro #3.
- **`adminDb` is a Proxy.** Any test file importing `webhooks.ts` (directly or transitively) must `vi.mock('@/lib/firebase/admin')` BEFORE the import. Story 4.1 Dev Notes. Tasks 5.2 / 6.2 handle this.
- **`.env.example` and the env tripwire test need NO changes.** `STRIPE_WEBHOOK_SECRET` is already declared (Story 4.1). No new env vars in Story 4.3. Do NOT touch [src/lib/env.test.ts](src/lib/env.test.ts).
- **`zod/v4` import path, not bare `zod`.** Epic 3 standardized on the v4 path. [webhook-events.ts:1](src/lib/schemas/webhook-events.ts#L1) is the canonical example — this story extends that file, so the import path is already correct on line 1; do not touch it.
- **Stripe SDK pinned at `^22.0.1`.** Type imports reference `Stripe.Event`, `Stripe.Invoice`, `Stripe.Subscription`. If you see an unfamiliar type error, read `node_modules/stripe/types/Subscriptions.d.ts` and `node_modules/stripe/types/Events.d.ts` first. Epic 3 retro #9.
- **Vitest file-parallelism flake is latent.** Epic 3 retro #6, confirmed present through Story 4.2. Fallback: `--no-file-parallelism`. Do NOT chase the flake here. Adding two new test files increases the risk surface; budget a minute for the fallback if it trips.
- **Fresh `STRIPE_WEBHOOK_SECRET` hygiene.** Story 4.1 Epic 3 retro action item #5. The secret was rotated; if you've run `stripe listen` since Story 4.2 and the listener emitted a new secret, update `.env.local` before Task 11. **Never paste any `whsec_...` into this transcript.**
- **Do NOT fix Epic 3 retro action item #4** (PlanCta hydration mismatch) in this story. Separate ticket, still open as of Story 4.2.
- **Do NOT touch the `allow_promotion_codes` / `discounts` block** in [session/route.ts](src/app/api/checkout/session/route.ts). Epic 3 retro #4.

### Stripe API reference (v22, API version `2026-03-25.dahlia`)

The Stripe types Story 4.3 reads:

- **`Stripe.Event`** — `event.id`, `event.type`, `event.data.object`
- **`Stripe.Subscription`** (from `event.data.object` when `event.type === 'customer.subscription.deleted'`):
  - `subscription.id: string`
  - `subscription.customer: string | Stripe.Customer`
  - `subscription.metadata: Record<string, string>` — contains `firebase_uid` / `plan_id` propagated from Story 4.2's `subscription_data.metadata` fix
  - `subscription.status: Stripe.Subscription.Status` — for `customer.subscription.deleted`, this will be `'canceled'` in the payload. We do NOT read it; we write the Firestore `status` based on the event type, not the Stripe status field. The two happen to agree in this case but the mapping is not always 1:1 (e.g., Stripe `incomplete_expired` maps to Firestore `canceled` in a future ticket — not this story).
- **`Stripe.Invoice`** (from `event.data.object` when `event.type === 'invoice.payment_failed'`):
  - `invoice.parent.subscription_details.subscription: string` — **dahlia path**, not top-level `invoice.subscription`. Story 4.2 Change Log is the canonical reference for this drift.
  - `invoice.customer: string | Stripe.Customer | null` — parsed by schema but unused (we fetch the customer ID from the retrieved Subscription for consistency with Story 4.2). Schema includes it defensively.
  - `invoice.parent.subscription_details.metadata` — **not read**, see "Why we don't read firebase_uid from invoice.parent.subscription_details.metadata" above.

Local SDK file references:
- `node_modules/stripe/types/Subscriptions.d.ts` — full `Stripe.Subscription` shape; `customer.subscription.deleted` payload
- `node_modules/stripe/types/Invoices.d.ts` — full `Stripe.Invoice` shape; the `parent.subscription_details` relocation (line ~843, per Story 4.2 Change Log)
- `node_modules/stripe/types/Events.d.ts` — `Stripe.Event` discriminated union; lookup for `'customer.subscription.deleted'` and `'invoice.payment_failed'` event type literals

### Firestore `users/{uid}` document shape (after Story 4.3)

```
users/{uid}
  ├── status: 'active' | 'past_due' | 'canceled'       ← Story 4.3 adds 'past_due' and 'canceled' transitions
  ├── plan: 'monthly' | 'yearly'                        (preserved on terminal writes — AC #5)
  ├── current_period_end: Timestamp                     (preserved on terminal writes — AC #5)
  ├── stripe_subscription_id: string                    (preserved on terminal writes — AC #5)
  ├── stripe_customer_id: string                        (preserved on terminal writes — AC #5)
  ├── updated_at: Timestamp (server)                    ← advanced on every write, including terminal
  └── created_at: Timestamp (server, only set on first create via Story 4.2)
```

No schema change in this story — only the set of legal `status` values grows. Epic 5's dashboard hook (`src/lib/firebase/useSubscription.ts`, architecture.md:556) will need to handle all three states; that's Epic 5's problem, not this story's.

### Naming Conventions (from Architecture)

- `users` collection: `snake_case`, plural (architecture.md:305)
- Document fields: `snake_case` (`status`, `updated_at`) — matches Stripe payload naming and Story 4.2's existing fields
- Function names: `camelCase` (`handleSubscriptionDeleted`, `handlePaymentFailed`)
- Log tag: `[webhooks/stripe ${new Date().toISOString()}]` — the `ISO timestamp embedded in the log tag` pattern was added in [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) at some point between Story 4.1 and now; grep the existing file for the exact template and mirror it. A single grep `rg -n '\[webhooks/stripe' src/` should show every log line from Epic 4 with one consistent tag shape after this story lands.

### Anti-Patterns to Avoid

- **Adding a retrieve call to `handleSubscriptionDeleted`.** The Subscription is already in `event.data.object`. An extra API call is pure latency cost with no information gain. See Dev Notes → "Why `subscription.deleted` needs no retrieve call".
- **Reading `firebase_uid` from `invoice.parent.subscription_details.metadata` in `handlePaymentFailed`.** See Dev Notes → "Why we don't read firebase_uid from invoice.parent.subscription_details.metadata". Consistency with Story 4.2 wins over one-less-API-call.
- **Writing a full field bag on terminal state transitions.** `status` + `updated_at`, nothing else. See Dev Notes → "Why `status`-only writes" and AC #5's negative-assertion test.
- **Adding a `tx.create` branch on `!snap.exists`.** See Dev Notes → "Why no create-branch on the terminal handlers". A missing user doc is an error signal, not a recoverable state.
- **Using `tx.set(ref, ..., { merge: true })` instead of `tx.update`.** Story 4.2 Dev Notes → "Why `tx.update` on the exists-path" — `tx.update` throws on a deleted doc, which is the failure mode we want.
- **Downgrading a canceled user to past_due on a `payment_failed` event.** This resurrects a terminal state. AC #5's payment_failed branch handles this explicitly; any test or code that removes the `currentStatus === 'canceled'` skip is a defect.
- **Combining both handlers' tests into one file.** One test file per behavior (Epic 3 retro #3, Story 4.2 Task 7.7). `subscription-deleted.test.ts` and `payment-failed.test.ts` are separate files.
- **Writing a standalone test file for the new schemas.** Task 1.5. Schema is exercised through the handler tests.
- **Creating a second retry helper.** Task 3 re-uses `retryStripeCall` from Story 4.2 Task 2. Do NOT copy-paste it, do NOT invoke an npm retry library, do NOT add jitter/exponential variants.
- **Touching [invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts), [webhooks.test.ts](src/lib/stripe/webhooks.test.ts), [session/route.ts](src/app/api/checkout/session/route.ts), or [session/route.test.ts](src/app/api/checkout/session/route.test.ts).** Story 4.2's surface area is frozen. If a test in those files fails during Task 9, the root cause is in your new code, NOT in the existing test — fix the new code.
- **Extracting a shared base handler for the two new functions.** They share two lines of structure (schema parse → transaction); the rest differs. Premature abstraction will cost more than it saves and make future drift hard to reason about. Each handler is ~40 lines; that's fine.
- **Adding new fields to the `users/{uid}` doc (e.g., `last_failed_payment_at`, `cancellation_reason`, `dunning_count`).** Out of scope. Epic 5 / future.
- **Handling `customer.subscription.updated` (mid-cycle plan change, etc.).** Out of scope — Epic 5 Story 5.3 (upgrade monthly → yearly) owns that flow. Leaving the default branch of `routeEvent`'s `switch` as-is (logs "unhandled event type") is correct.

### Project Structure Notes

- **New files:**
  - [src/lib/stripe/subscription-deleted.test.ts](src/lib/stripe/subscription-deleted.test.ts) — Task 5
  - [src/lib/stripe/payment-failed.test.ts](src/lib/stripe/payment-failed.test.ts) — Task 6
- **Modified files:**
  - [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts) — Task 1 additive (two schemas + two types)
  - [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) — Tasks 2/3 replace two stub bodies; imports extended minimally
- **Not modified:** [src/lib/stripe/server.ts](src/lib/stripe/server.ts) (no new retry helper), [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts), [src/app/api/webhooks/stripe/route.test.ts](src/app/api/webhooks/stripe/route.test.ts), [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts), [src/lib/stripe/invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts), [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts), [src/lib/firebase/admin.ts](src/lib/firebase/admin.ts), `.env.example`, [src/lib/env.test.ts](src/lib/env.test.ts).
- Folder placement: `src/lib/schemas/` and `src/lib/stripe/` match architecture.md:336-339 ("Lib organized by service"). Test co-location follows architecture.md:337.
- If you find yourself editing [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts), stop. Story 4.3 should not need to touch it — the "thin HTTP shell + logic in `lib/`" split Story 4.1 established is deliberately airtight, and Story 4.2 landed without touching it.

### References

- [Epics file — Story 4.3 AC](../planning-artifacts/epics.md) — lines 401-417 (`_bmad-output/planning-artifacts/epics.md#L401-L417`)
- [Architecture — Webhook Event Flow](../planning-artifacts/architecture.md) — lines 373-380 (verify → dedup → route → transact → 200)
- [Architecture — Webhook Idempotency + Transactions](../planning-artifacts/architecture.md) — lines 202-205 (dual strategy)
- [Architecture — Error Handling Patterns](../planning-artifacts/architecture.md) — lines 390-398 (webhook handler try/catch → log → return 200)
- [Architecture — Naming Conventions](../planning-artifacts/architecture.md) — lines 303-322 (snake_case collections/fields, camelCase code)
- [Architecture — Webhook Schema File Location](../planning-artifacts/architecture.md) — line 550 (`src/lib/schemas/webhook-events.ts` — this story extends, does not create)
- [Story 4.1 — Stripe Webhook Endpoint](./4-1-stripe-webhook-endpoint-with-signature-verification.md) — required reading for Dev Notes on route-level error contract (AC #6), `import * as self` pattern, `stripe_events` dedup invariant, `[webhooks/stripe]` log tag shape
- [Story 4.2 — Process invoice.paid Webhook](./4-2-process-invoice-paid-webhook-to-activate-subscriptions.md) — required reading for:
  - Task 4 body structure (mirrored by Tasks 2/3 here)
  - Task 7 test topology (mirrored by Tasks 5/6 here)
  - Change Log entry for dahlia API drift (critical background for `paymentFailedSchema`'s nested path)
  - Dev Notes → "Why the API call happens outside the Firestore transaction" (same principle applies to `payment_failed`)
  - Dev Notes → "Why `tx.update` on the exists-path" (directly reused in AC #5)
  - Completion Notes → Code Review H1/H2/M1/M2 for `retryStripeCall` nuances that Task 3's retrieve call depends on
- [Epic 3 Retrospective](./epic-3-retro-2026-04-14.md) — action items #3 (silent catches), #5 (webhook secret rotation — still applicable), #6 (Vitest parallelism flake — still latent), #9 (read SDK notes before library bumps), #10 (build in DoD)
- [Existing Webhooks routing module](../../src/lib/stripe/webhooks.ts) — Tasks 2/3 edit target; `handleSubscriptionDeleted` and `handlePaymentFailed` stubs to be replaced
- [Existing Webhook event schemas](../../src/lib/schemas/webhook-events.ts) — Task 1 edit target; append two schemas + two types
- [Existing invoice-paid test file](../../src/lib/stripe/invoice-paid.test.ts) — canonical mock topology reference for Tasks 5/6 (do NOT edit, do NOT rewrite — lift verbatim)
- [Existing Stripe server singleton](../../src/lib/stripe/server.ts) — Task 3's `retryStripeCall` import source; do NOT modify
- [Existing Pricing plan registry](../../src/lib/pricing/plans.ts) — `PLAN_IDS` reference (unused in this story — AC #4 explicitly skips plan_id validation in payment_failed)
- [Existing Firebase Admin init](../../src/lib/firebase/admin.ts) — `adminDb` Proxy; Tasks 5.2 / 6.2 mock target
- Stripe public docs (informational only — do not fetch during dev-story unless blocked):
  - https://docs.stripe.com/api/subscriptions/object — `Stripe.Subscription` reference, `customer.subscription.deleted` payload shape
  - https://docs.stripe.com/api/invoices/object — `Stripe.Invoice` reference, dahlia relocation of `subscription` under `parent.subscription_details`
  - https://docs.stripe.com/api/events/types#event_types-customer.subscription.deleted — event type semantics
  - https://docs.stripe.com/api/events/types#event_types-invoice.payment_failed — event type semantics
  - https://docs.stripe.com/billing/subscriptions/overview#subscription-lifecycle — active → past_due → canceled state machine
  - https://docs.stripe.com/webhooks#retries — Stripe's at-least-once delivery + retry semantics (background for dedup)

## Dev Agent Record

### Agent Model Used

claude-opus-4-6[1m]

### Debug Log References

- `npx vitest run src/lib/stripe/subscription-deleted.test.ts src/lib/stripe/payment-failed.test.ts` → **20/20 passing** (9 deleted + 11 payment-failed)
- `npx vitest run` (full suite) → **288/288 passing** across 37 files (up from 268/268 baseline; +20 new cases)
- `npm run lint` → **0 errors, 0 warnings**
- `npm run build` → zero type errors; `/api/webhooks/stripe` emits as `ƒ` (Dynamic) in the route manifest; no new routes added

### Completion Notes List

**Implementation approach.** Lifted the `invoice-paid.test.ts` mock topology verbatim for `payment-failed.test.ts` (plain-function `Stripe` constructor, `vi.hoisted` state, `importOriginal` for real `retryStripeCall`). `subscription-deleted.test.ts` deliberately does NOT mock `stripe` or `@/lib/stripe/server` — this is the structural proof AC #8 called for that `handleSubscriptionDeleted` never reaches the Stripe SDK.

**`didWrite` gating.** Both handlers use a `let didWrite = false` hoisted above `runTransaction`; the transaction closure sets it `true` right before `tx.update`. Post-transaction code gates the `processed:` success log on `if (didWrite)`. This keeps the no-op and write paths in the same `runTransaction` call while giving the outer handler a clean signal for whether to emit the success log (AC #6).

**Task 8 (self-namespace regression guard) was a no-op.** Verified that [src/lib/stripe/webhooks.test.ts:20-21](src/lib/stripe/webhooks.test.ts#L20-L21) already has `vi.spyOn(webhooks, 'handleSubscriptionDeleted').mockResolvedValue()` and `vi.spyOn(webhooks, 'handlePaymentFailed').mockResolvedValue()` in the shared `beforeEach`, with dispatch tests at lines 37 and 46 exercising each event type. No new test added (Story 4.1 coverage is sufficient).

**Task 11 manual smoke — IN PROGRESS.** Steps 11.1 (prerequisite check) and 11.2 (starting state confirmed: test user with `status: 'active'`, uid/subscription_id/customer_id noted) are both ✅. Steps 11.3–11.12 (triggering `invoice.payment_failed`, verifying Firestore field preservation, triggering `customer.subscription.deleted`, replay dedup, in-handler idempotent branch check, canceled-user skip) are **not yet run** — these are the live-Stripe human-verification steps that must pass before the story flips to `review`.

**No-regression confirmed (unit level).** `invoice-paid.test.ts`, `webhooks.test.ts`, and `route.test.ts` all still green — the self-namespace pattern and existing dispatch spies continue to work with the new real handler bodies behind them.

### File List

**Modified:**
- [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts) — added `subscriptionDeletedSchema`, `paymentFailedSchema`, and their inferred type exports (`SubscriptionDeletedPayload`, `PaymentFailedPayload`). Purely additive; `invoicePaidSchema` untouched.
- [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) — replaced `handleSubscriptionDeleted` and `handlePaymentFailed` stub bodies with real implementations (schema parse → optional retrieve for payment_failed → runTransaction with `didWrite` gating and per-status idempotent branches). Extended the `@/lib/schemas/webhook-events` import to include the two new schemas. `handleInvoicePaid`, `routeEvent`, and the `import * as self` pattern are untouched.

**Created:**
- [src/lib/stripe/subscription-deleted.test.ts](src/lib/stripe/subscription-deleted.test.ts) — 9 cases (happy active, happy past_due, already-canceled no-op, missing doc, missing firebase_uid, schema failure, customer expanded-object, transaction throws, idempotent replay). Deliberately does not mock `@/lib/stripe/server` as structural proof of no Stripe SDK usage.
- [src/lib/stripe/payment-failed.test.ts](src/lib/stripe/payment-failed.test.ts) — 11 cases (happy active→past_due, already past_due no-op, skip canceled, missing doc, schema failure, missing firebase_uid on retrieved sub, transient retry 249/251ms boundary, non-transient fast-fail, exhaustion, transaction throws, idempotent replay).

**Not modified:** `src/lib/stripe/server.ts`, `src/lib/stripe/invoice-paid.test.ts`, `src/lib/stripe/webhooks.test.ts`, `src/app/api/webhooks/stripe/route.ts`, `src/app/api/webhooks/stripe/route.test.ts`, `src/lib/firebase/admin.ts`, `.env.example`, `src/lib/env.test.ts`.

## Change Log

| Date | Story Version | Description | Author |
|------|---------------|-------------|--------|
| 2026-04-16 | 0.2 (Code Review) | **Adversarial code review completed.** Findings: **C1** — Task 11 subtasks 11.3–11.12 were falsely marked `[x]` despite Completion Notes explicitly stating they were not yet run; unchecked to match reality. **M1** (advisory, no code change) — `payment-failed.test.ts` uses real `retryStripeCall` for all cases instead of AC #8's suggested stub/real split across two describe blocks; accepted because this matches the `invoice-paid.test.ts` pattern from Story 4.2 and is structurally stronger. **L1** — no explicit "getStripe never called" test assertion in `subscription-deleted.test.ts`; structural proof via absent mock is sufficient but less visible. **L2** — `Timestamp.fromMillis` mock dead code in `subscription-deleted.test.ts` (harmless, needed for import). Implementation quality is solid: schemas correct (dahlia path preserved), both handlers follow AC #5 status-only field bags with idempotent no-op branches, `didWrite` gating separates write vs no-op logs, test coverage is thorough (20 new cases, exact-key field-bag assertions, 249/251ms backoff boundary). Full suite **288/288**, lint **0/0**, build clean. Story remains **in-progress** pending Task 11 manual smoke (steps 11.3–11.12). | claude-opus-4-6[1m] (reviewer) |
| 2026-04-15 | 0.1 (WIP) | Code + unit tests landed for Story 4.3. Both webhook handlers (`handleSubscriptionDeleted`, `handlePaymentFailed`) replaced stub bodies with real logic: Zod schema validation → (retrieve for payment_failed) → Firestore transaction with `status`-only field bag and idempotent no-op branches for already-canceled / already-past_due states. Added 20 new test cases across two new test files. Full suite: **268 → 288 passing**. Lint 0/0. Build clean. **Task 11 manual smoke 11.3–11.12 still outstanding** — story remains `in-progress` until live-Stripe verification completes. | claude-opus-4-6[1m] |
