# Story 4.2: Process invoice.paid Webhook to Activate Subscriptions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the Warden platform,
I want `invoice.paid` webhook events to atomically activate or renew the corresponding `users/{uid}` subscription record in Firestore,
So that a paying user's subscription state is correct within seconds of Stripe confirming payment, with zero double-processing and zero lost writes.

## Human Prerequisites

*(Block pattern from Story 4.1 — Epic 3 retro action item #7. These are steps the dev agent CANNOT do for you. Check each before starting Task 1.)*

- [x] **Story 4.1's Task 9 manual smoke is complete and green.** Confirmed 2026-04-15: Story 4.1 is now `done` in [sprint-status.yaml](_bmad-output/implementation-artifacts/sprint-status.yaml) (commit `1e90890` — "chore(story-4.1): mark done after Task 9 manual smoke passes"). The routing stub for `invoice.paid` has been human-verified against `stripe trigger` / `stripe events resend` / `stripe trigger customer.created`.
- [x] **`stripe listen --forward-to localhost:3000/api/webhooks/stripe`** is running in a separate terminal, same as for Story 4.1. Story 4.2's Task 10 manual smoke drives real events into this listener.
- [x] **A fresh `STRIPE_WEBHOOK_SECRET`** is present in `.env.local` (Epic 3 retro action item #5 — the older secret was exposed in a chat transcript and must remain rotated). Obtain via `stripe listen`'s first-line output; **never paste it into this transcript, chat, or any log**.
- [x] **`FIREBASE_SERVICE_ACCOUNT_KEY`** is present in `.env.local` (established in Story 2.4). `adminDb` in Story 4.2 actually writes to `users/{uid}` — a missing key will crash at first `adminDb.collection('users')` touch, not at module import.
- [x] **At least one real test Stripe customer + subscription exists in your Stripe test dashboard**, created via a successful Story 3.2 / 3.3 checkout while signed in as a known Firebase user. You need a `customer_id` + `subscription_id` + the `firebase_uid` who owns them so Task 10 can verify the `users/{uid}` write actually landed against the right document. If you don't have one, run through the pricing → checkout flow once in your dev environment before starting Task 10.
- [x] **Firestore Console access** (or `firebase firestore:query` CLI) to inspect `users/{uid}` before and after the smoke. The visual confirmation is the whole point of Task 10.

## Acceptance Criteria

1. **Given** the `handleInvoicePaid(event: Stripe.Event): Promise<void>` export in [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) (currently a no-op stub from Story 4.1)
   **When** this story lands
   **Then** the function signature is **unchanged** (`(event: Stripe.Event): Promise<void>`) so `routeEvent` and [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts)'s spy-based dispatch tests continue to pass without modification
   **And** the function body replaces the `console.log` stub with the real activation logic described in ACs #3–#8
   **And** the `import * as self from './webhooks'` self-namespace pattern in `webhooks.ts` (see Story 4.1 Completion Notes — load-bearing for `vi.spyOn` interception) is **untouched** — do not remove or "clean up" it
   **And** the other two stub handlers (`handleSubscriptionDeleted`, `handlePaymentFailed`) remain unchanged — Story 4.3 owns their replacement

2. **Given** Story 3.2 / 3.3's Stripe Checkout Session creation at [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts)
   **When** Story 4.2 lands
   **Then** the session creation payload sets `subscription_data.metadata = { firebase_uid: decoded.uid, plan_id: plan.id }` **in addition to** the existing top-level `metadata` on the session itself — this propagates the linking metadata from the Session (which exists for ~24h) onto the long-lived Subscription object so every future `invoice.paid` for this subscription can resolve the `uid` with a single `stripe.subscriptions.retrieve(id)` call (see Dev Notes → "Why `subscription_data.metadata`" for the rationale). This is a **minimal, surgical edit** to the existing sessionArgs — the existing `metadata` on the session is kept unchanged, and `subscription_data` is additive
   **And** the existing [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) gains one new assertion: the mocked `stripe.checkout.sessions.create` was called with `subscription_data.metadata.firebase_uid === <uid>` and `subscription_data.metadata.plan_id === <plan id>`
   **And** no other fields in [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts) change — do not refactor, do not extract helpers, do not touch `allow_promotion_codes` (Epic 3 retro #4 is a separate ticket)
   **And** the `.env.example`, env tripwire, and PLAN_BY_ID registry are **not touched**

3. **Given** a verified `Stripe.Event` of type `'invoice.paid'` flowing into `handleInvoicePaid`
   **When** the handler begins processing
   **Then** it first narrows `event.data.object` to `Stripe.Invoice` (via `const invoice = event.data.object as Stripe.Invoice` — the type guard `event.type === 'invoice.paid'` already narrows `event.data.object` in TS 5+, but the `as` is the defensive fallback)
   **And** the handler validates the invoice shape via a **Zod schema** in a **new file** [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts) — matches the file planned at architecture.md:550. The schema is:
   ```ts
   export const invoicePaidSchema = z.object({
     subscription: z.string().min(1),             // Stripe Subscription ID
     customer: z.string().min(1),                 // Stripe Customer ID
     lines: z.object({
       data: z.array(
         z.object({
           period: z.object({
             end: z.number().int().positive(),    // Unix seconds
           }),
         }),
       ).min(1),
     }),
   })
   ```
   and the handler does `const parsed = invoicePaidSchema.safeParse(invoice)` — if `!parsed.success`, the handler logs `[webhooks/stripe] invoice.paid payload failed schema validation:` + `parsed.error.issues` + `event.id` and **throws** (the route-level catch in [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts) then catches the throw, returns `200 { data: { routingError: true, ... } }`, and the event remains in `stripe_events` for manual replay per Story 4.1 AC #6)
   **And** the schema uses **Zod v4** syntax (the `zod/v4` import path — matches [src/app/api/checkout/session/route.ts:1](src/app/api/checkout/session/route.ts#L1). Do NOT use `import { z } from 'zod'` — Epic 3 standardized on the v4 path)
   **And** the schema is **narrow**: it validates only the fields 4.2 actually reads (`subscription`, `customer`, `lines.data[0].period.end`). Do NOT expand it to cover the whole `Stripe.Invoice` type — architectural note: `Stripe.Event` is itself the type-level schema, and `constructEvent` is the runtime authentication check; the Zod schema here is strictly defense-in-depth against Stripe API drift, not general validation

4. **Given** a schema-valid invoice payload has been extracted
   **When** the handler resolves the owning Firebase uid
   **Then** the handler calls `getStripe().subscriptions.retrieve(parsed.data.subscription)` **once** (not inside the Firestore transaction — API calls must not live in transactions, see architecture.md:202-205 and Dev Notes → "Why the API call happens outside the transaction")
   **And** the call is wrapped in retry logic: **up to 3 attempts** with exponential backoff (250ms, 750ms, 2250ms) per NFR13 — but **ONLY for transient errors**. A transient error is any thrown `Stripe.errors.StripeConnectionError`, `StripeAPIError` with `statusCode >= 500`, or `StripeRateLimitError`. A `StripeInvalidRequestError` (400), `StripeAuthenticationError` (401), or any 4xx is **NOT retried** — those mean "this will never succeed" and fall through immediately
   **And** the retry logic lives in a **new small helper** `retryStripeCall<T>(fn: () => Promise<T>, label: string): Promise<T>` co-located in [src/lib/stripe/server.ts](src/lib/stripe/server.ts) (next to `getStripe`) — do NOT create a separate `retry.ts` file, do NOT reach for an npm retry library. Three attempts with a linear-ish backoff is twenty lines of code
   **And** after the retry budget is exhausted, the handler logs `[webhooks/stripe] subscription retrieve failed after retries:` + `event.id` + `subscription_id` + `err` and **throws** (route-level catch swallows → 200 with `routingError: true` → event stays in `stripe_events` for manual replay — same pattern as AC #3's schema failure)
   **And** from the retrieved `Stripe.Subscription`, the handler reads `subscription.metadata.firebase_uid` and `subscription.metadata.plan_id`
   **And** if `firebase_uid` is missing or empty, the handler logs `[webhooks/stripe] invoice.paid subscription missing firebase_uid metadata — cannot link to user:` + `event.id` + `subscription.id` and **throws** — this is the "legacy subscriptions created before AC #2 landed" case. Intentionally surfaces as a routing error rather than silently dropping; operator replay post-backfill can recover
   **And** if `plan_id` is missing or not one of `'monthly' | 'yearly'` (the `PLAN_IDS` from [src/lib/pricing/plans.ts](src/lib/pricing/plans.ts)), the handler logs `[webhooks/stripe] invoice.paid subscription has unknown plan_id:` + `event.id` + `plan_id` and **throws** — same rationale as the missing-uid case

5. **Given** `uid`, `plan_id`, `stripe_subscription_id`, `stripe_customer_id`, and `current_period_end` (Unix seconds from `invoice.lines.data[0].period.end`) are all resolved and validated
   **When** the handler writes to Firestore
   **Then** the write happens inside a **Firestore transaction** via `adminDb.runTransaction(async (tx) => { ... })` (per architecture.md:202-205 and Story 4.1 Dev Notes → "Why a Firestore transaction")
   **And** the transaction body:
   1. Reads `users/{uid}` via `tx.get(userRef)`
   2. Computes the new document fields:
      - `status: 'active'`
      - `plan: plan_id` (`'monthly'` or `'yearly'`)
      - `current_period_end: Timestamp.fromMillis(period_end_unix_seconds * 1000)` — Firestore `Timestamp`, per architecture.md:358 (import `Timestamp` from `firebase-admin/firestore`). **Do NOT** store `current_period_end` as a Unix number or an ISO string — the data layer expects a `Timestamp` for `.transform()` consumption
      - `stripe_subscription_id: subscription.id`
      - `stripe_customer_id: subscription.customer` (string form — if it comes back as `Stripe.Customer`, coerce via `typeof c === 'string' ? c : c.id`)
      - `updated_at: FieldValue.serverTimestamp()`
   3. If `snap.exists`, calls `tx.update(userRef, { ...newFields })` — **merges** into the existing doc without wiping any field Stories 5.x will add (dashboard customizations, user preferences, etc.). `tx.update` is the correct call; `tx.set` with `{ merge: true }` is the fallback shape but `tx.update` is more precise for a document we know exists
   4. If `!snap.exists`, calls `tx.create(userRef, { ...newFields, created_at: FieldValue.serverTimestamp() })` — first invoice.paid for a brand-new user (Epic 2 createSessionCookie may not have materialized the Firestore doc yet, depending on Story 2.1's shape). The `created_at` field is added **only** in the create branch
   **And** `tx.update` (not `tx.set`) is used on the exists-path so that a future field addition in Stories 5.x is NOT blown away by a webhook replay. This is a deliberate safety choice — see Dev Notes → "Why `tx.update` on the exists-path"
   **And** the collection name is **`users`** (plural, `snake_case` — architecture.md:305). Document ID is the Firebase `uid` string from `subscription.metadata.firebase_uid`
   **And** the transaction returns `void` (no caller needs its return value — Story 4.1's dedup transaction returned `alreadyProcessed`, this one doesn't)
   **And** transaction failures (Firestore SDK exhaustion, permission denied, network) **propagate the throw** — caught by the route-level catch in [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts), which logs and returns 200 `routingError: true` per Story 4.1 AC #6

6. **Given** the transaction commits successfully
   **When** the handler returns
   **Then** it logs `[webhooks/stripe] invoice.paid processed:` + `event.id` + `uid` + `plan_id` + `current_period_end` (ISO 8601) — this is the audit line operators will grep during any support incident
   **And** it returns `void` (the routing layer in `webhooks.ts`'s `routeEvent` does not inspect the return value)
   **And** the **whole handler's cumulative wall-clock budget** (Zod parse + `subscriptions.retrieve` + retries + Firestore transaction) must stay under the NFR14 5-second boundary. The tight path (no retries needed) should comfortably land under ~1.5s. **Do NOT add any `await`s that aren't strictly necessary** — follow the same "design-time budget, not a test assertion" discipline from Story 4.1 AC #5

7. **Given** a Firestore transaction that encountered a contention retry (the SDK's normal `ABORTED` retry loop)
   **When** the retry executes
   **Then** the second attempt re-reads `users/{uid}` cleanly via `tx.get(userRef)` (no caching of the first read's snapshot — this is how the SDK handles it; just don't capture `snap` outside the transaction closure)
   **And** the final write reflects the correct branch (create vs. update) based on the retry's `snap.exists` value, not the original attempt's — a race between a concurrent account-creation and an `invoice.paid` converges correctly because both branches produce a valid terminal state
   **Note:** You do not need to write a test for Firestore's own retry machinery. You DO need to test that `snap = await tx.get(ref)` is inside the transaction closure, not captured outside

8. **Given** a **duplicate** `invoice.paid` event (same `event.id`, arriving twice because of Stripe's at-least-once delivery)
   **When** the event is delivered the second time
   **Then** Story 4.1's dedup transaction in [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts) (the `stripe_events` collection write) intercepts it **before** `routeEvent` is called — `handleInvoicePaid` is never invoked the second time. **No new dedup logic lives inside `handleInvoicePaid`.** Do not add a second dedup check — that's the failure mode Story 4.1's architecture was designed to prevent
   **And** this is verified at the route test level (inherits the Story 4.1 duplicate-event test — no new test needed in `route.test.ts`), and at the `webhooks.test.ts` level the dispatch test remains spy-based and does not involve the route

9. **Given** a new test file [src/lib/stripe/invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts) (colocated with `webhooks.ts` but in its own file because the cases are heavy — do NOT bloat `webhooks.test.ts`)
   **When** `npx vitest run` is executed
   **Then** the file mocks `@/lib/firebase/admin` to stub `adminDb.runTransaction` with a fake `tx` (`.get`, `.create`, `.update`, `.set` as `vi.fn()`s). The mock shape is lifted from Story 4.1's `route.test.ts` Task 6.3 structure — do not reinvent it
   **And** the file mocks `@/lib/stripe/server` to stub `getStripe` with a fake whose `subscriptions.retrieve` is a `vi.fn()` the tests drive case-by-case. **Do NOT** use a real Stripe constructor — reuse the plain-function `Stripe` constructor mock pattern from [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) (Epic 3 retro #3 — do not re-discover the Vitest v4 ES-module gotcha)
   **And** the file **imports `handleInvoicePaid` directly** from `@/lib/stripe/webhooks` and calls it with a hand-crafted `Stripe.Event`-shaped literal — no HTTP layer, no `routeEvent` indirection. The Zod schema, the retry helper, and the Firestore transaction all get exercised with synthetic inputs
   **And** the following test cases exist and pass:
   - **Happy path, new user (create branch)** — event.type `'invoice.paid'`, valid payload, `subscriptions.retrieve` resolves with `{id: 'sub_...', customer: 'cus_...', metadata: {firebase_uid: 'uid_abc', plan_id: 'monthly'}}`, fake `tx.get(users/uid_abc)` resolves `{exists: false}` → `tx.create` called exactly once with `status: 'active'`, `plan: 'monthly'`, `current_period_end` as a `Timestamp`, `stripe_subscription_id`, `stripe_customer_id`, `updated_at`, `created_at`. `tx.update` NOT called. `tx.set` NOT called (negative assertion — Epic 3 retro #3 "catch the wrong-call-shape regression")
   - **Happy path, existing user (update branch)** — same, but `tx.get` resolves `{exists: true}` → `tx.update` called exactly once with the same field bag **minus** `created_at`. `tx.create` NOT called. `tx.set` NOT called
   - **Yearly plan** — metadata `plan_id: 'yearly'` → `tx.update` / `tx.create` called with `plan: 'yearly'`
   - **Zod schema failure** — invoice payload missing `subscription` → `handleInvoicePaid` throws, `console.error` called with `[webhooks/stripe] invoice.paid payload failed schema validation:`, `subscriptions.retrieve` NOT called, `runTransaction` NOT called. **This test case is critical** — it verifies the "fail-fast at the boundary" contract
   - **Subscription missing `firebase_uid` metadata** — `subscriptions.retrieve` resolves with `{metadata: {}}` → `handleInvoicePaid` throws, `console.error` called with the right tag, `runTransaction` NOT called
   - **Subscription has unknown `plan_id`** — `metadata: {firebase_uid: 'uid_x', plan_id: 'enterprise'}` → `handleInvoicePaid` throws, `console.error` called, `runTransaction` NOT called
   - **Transient Stripe error retried successfully** — mock `subscriptions.retrieve` to reject once with a connection-like error, then resolve on the 2nd call → exactly 2 calls to `.retrieve`, `runTransaction` eventually called, `tx.update` / `tx.create` called, test passes within 5s (use `vi.useFakeTimers()` + `vi.advanceTimersByTimeAsync` to drive the backoff — do NOT sleep in real time, Epic 3 retro #6 file-parallelism flake will compound)
   - **Non-transient Stripe error NOT retried** — mock `subscriptions.retrieve` to reject with a `StripeInvalidRequestError` (or a plain `Error` with `.type === 'StripeInvalidRequestError'` — the retry helper checks `.type`/`.statusCode`) → exactly 1 call, handler throws immediately, `runTransaction` NOT called
   - **Transient errors exhaust retry budget** — mock `subscriptions.retrieve` to reject 3 times with connection errors → exactly 3 calls, handler throws, log tagged `subscription retrieve failed after retries:`, `runTransaction` NOT called
   - **Firestore transaction throws** — fake `runTransaction` rejects with `Error('permission-denied')` → handler throws (propagates), log NOT required (the route-level catch owns that)
   - **`period_end` is written as a `Timestamp`, not a number** — positive assertion: the arg passed to `tx.update`/`tx.create` has `current_period_end instanceof Timestamp` (or is a `Timestamp`-shaped object from the firebase-admin mock). This guards the "silently stored a Unix number instead of Timestamp" regression
   - **`stripe_customer_id` is coerced to string when `customer` comes back as an object** — case where `subscriptions.retrieve` resolves with `{customer: {id: 'cus_obj'}}` (Stripe SDK can return expanded objects) → stored as `'cus_obj'`, not `[object Object]`
   **And** the test file uses `vi.stubEnv` for any env needed and `vi.unstubAllEnvs()` in `afterEach` — same pattern as Story 4.1 AC #8

10. **Given** the testing baseline at the start of this story (254 / 254 from Story 4.1, per its Completion Notes)
    **When** this story lands
    **Then** `npx vitest run` reports **> 254** passing with **zero failures** (target: roughly 265–275; exact count advisory, the floor is the no-regression guard)
    **And** `npm run build` passes with zero type errors
    **And** `npm run lint` shows **0 errors, 0 warnings** (Epic 3 retro #10 — preserve the 0/0 baseline)
    **And** `npm run build` is listed as a distinct Task 9 line item, not bundled with lint+vitest

## Tasks / Subtasks

- [x] Task 1: Extend the Checkout Session to propagate linking metadata onto the Subscription (AC: #2)
  - [x] 1.1 Open [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts). Locate the `sessionArgs` object literal (~line 99).
  - [x] 1.2 Add a `subscription_data: { metadata: { firebase_uid: decoded.uid, plan_id: plan.id } }` field to the same object, **in addition to** (not replacing) the existing top-level `metadata`. The top-level metadata remains because Stripe still surfaces it on the Session object for Story 3.2's `client_reference_id` cross-checks; the new `subscription_data.metadata` is what gets copied onto the long-lived `Stripe.Subscription` object.
  - [x] 1.3 Do NOT change the `allow_promotion_codes` / `discounts` branching — Epic 3 retro #4 is a separate hydration-mismatch ticket that has nothing to do with this story. Leave that block alone.
  - [x] 1.4 Do NOT extract helpers. Do NOT rename variables. Do NOT reorder imports. Surgical one-field addition only.
  - [x] 1.5 Open [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts). Locate the existing "creates a checkout session" happy-path test (the one that asserts `stripe.checkout.sessions.create` was called with `metadata.firebase_uid`).
  - [x] 1.6 Extend that assertion to also check `subscription_data.metadata.firebase_uid === expectedUid` and `subscription_data.metadata.plan_id === expectedPlanId`. One extra `expect().toMatchObject({ subscription_data: { metadata: { ... } } })` call is sufficient — do NOT write a whole new test case for this; it's a property of the existing happy path.
  - [x] 1.7 Run `npx vitest run src/app/api/checkout/session/route.test.ts` → must be green before moving on.

- [x] Task 2: Add `retryStripeCall` helper to the Stripe server module (AC: #4)
  - [x] 2.1 Open [src/lib/stripe/server.ts](src/lib/stripe/server.ts). Below `getStripe`, add an exported async helper `retryStripeCall<T>(fn: () => Promise<T>, label: string): Promise<T>`.
  - [x] 2.2 Implementation: three attempts total, backoff 250ms → 750ms → 2250ms **before** each retry (so the first call is immediate, the second after 250ms, the third after 750ms + 250ms = waited 1s total, fourth call is NOT made). Use `await new Promise(r => setTimeout(r, ms))` for the delay — no external dependencies.
  - [x] 2.3 On each caught error, classify as **transient** (`err.type === 'StripeConnectionError'` OR `err.type === 'StripeAPIError'` OR `err.type === 'StripeRateLimitError'` OR (`err.statusCode >= 500 && err.statusCode < 600`)) vs. **non-transient** (everything else — `StripeInvalidRequestError`, `StripeAuthenticationError`, `StripePermissionError`, plain `Error`). Non-transient → re-throw immediately (retry count = 1 effectively).
  - [x] 2.4 After the final attempt, re-throw the last error (do NOT wrap it in a new Error — preserve the stack). Log `[stripe/retry] ${label} retry N/3 failed:` before each retry and `[stripe/retry] ${label} exhausted retries` before the final throw. These logs are for the audit trail when operator triage needs to know "did Stripe ever respond?".
  - [x] 2.5 Do NOT use any exponential-backoff npm library. Do NOT add jitter. Do NOT make the retry count configurable. The spec is exactly three attempts, exactly those delays, for exactly NFR13. If a future story needs a different profile, it can add its own helper.

- [x] Task 3: Add the `webhook-events.ts` Zod schema module (AC: #3)
  - [x] 3.1 Create [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts).
  - [x] 3.2 Import: `import { z } from 'zod/v4'` — **must be the v4 path**, matches [src/app/api/checkout/session/route.ts:1](src/app/api/checkout/session/route.ts#L1).
  - [x] 3.3 Export `invoicePaidSchema` with the exact shape in AC #3 — no more, no less. Do NOT preemptively add schemas for `subscription.deleted` or `payment_failed` — Story 4.3 owns those, and each story's schema lives in this same file additively.
  - [x] 3.4 Export an inferred type: `export type InvoicePaidPayload = z.infer<typeof invoicePaidSchema>`. Story 4.2's handler imports both the schema and the type.
  - [x] 3.5 No test file for this module on its own — the schema is exercised through `handleInvoicePaid`'s tests in Task 8. A standalone schema test would just re-test Zod's library behavior.

- [x] Task 4: Replace the `handleInvoicePaid` stub with real logic (AC: #1, #3, #4, #5, #6)
  - [x] 4.1 Open [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts). Locate the `export async function handleInvoicePaid(event: Stripe.Event): Promise<void>` function.
  - [x] 4.2 Add the imports at the top of the file (preserve import order — Next.js runtime exports, then external value imports, then type imports, then internal absolutes):
    ```ts
    import { FieldValue, Timestamp } from 'firebase-admin/firestore'
    // type Stripe import already exists
    import { adminDb } from '@/lib/firebase/admin'
    import { PLAN_IDS } from '@/lib/pricing/plans'
    import { invoicePaidSchema } from '@/lib/schemas/webhook-events'
    import { getStripe, retryStripeCall } from '@/lib/stripe/server'
    ```
    Note: `import 'server-only'` and `import * as self from './webhooks'` at the top stay exactly as they are.
  - [x] 4.3 Rewrite the body. Sequence:
    1. `const invoice = event.data.object as Stripe.Invoice`
    2. `const parsed = invoicePaidSchema.safeParse(invoice)` → if `!parsed.success`, `console.error('[webhooks/stripe] invoice.paid payload failed schema validation:', parsed.error.issues, event.id)` and `throw new Error('invoice.paid schema validation failed')` (the throw text is for the route-level log; the real error signal is the `console.error` above)
    3. Extract `const { subscription: subId, lines } = parsed.data` and `const periodEndSeconds = lines.data[0].period.end`
    4. `const subscription = await retryStripeCall(() => getStripe().subscriptions.retrieve(subId), 'subscriptions.retrieve')` — if this throws after retries, `console.error('[webhooks/stripe] subscription retrieve failed after retries:', event.id, subId, err)` and re-throw. **Put this try/catch at this level**, not inside the helper — the helper's job is retry, the handler's job is context-tagged logging.
    5. `const firebaseUid = subscription.metadata?.firebase_uid` → if falsy, log `[webhooks/stripe] invoice.paid subscription missing firebase_uid metadata — cannot link to user:` + event.id + subscription.id, throw
    6. `const planId = subscription.metadata?.plan_id` → if not in `PLAN_IDS` (`'monthly' | 'yearly'`), log `[webhooks/stripe] invoice.paid subscription has unknown plan_id:` + event.id + planId, throw
    7. Coerce customer: `const customerId = typeof subscription.customer === 'string' ? subscription.customer : subscription.customer.id`
    8. Build the field bag:
       ```ts
       const baseFields = {
         status: 'active' as const,
         plan: planId,
         current_period_end: Timestamp.fromMillis(periodEndSeconds * 1000),
         stripe_subscription_id: subscription.id,
         stripe_customer_id: customerId,
         updated_at: FieldValue.serverTimestamp(),
       }
       ```
    9. Run the transaction:
       ```ts
       await adminDb.runTransaction(async (tx) => {
         const userRef = adminDb.collection('users').doc(firebaseUid)
         const snap = await tx.get(userRef)
         if (snap.exists) {
           tx.update(userRef, baseFields)
         } else {
           tx.create(userRef, { ...baseFields, created_at: FieldValue.serverTimestamp() })
         }
       })
       ```
    10. Log success: `console.log('[webhooks/stripe] invoice.paid processed:', event.id, firebaseUid, planId, new Date(periodEndSeconds * 1000).toISOString())`
  - [x] 4.4 Do NOT add any `try`/`catch` around the `runTransaction` call inside `handleInvoicePaid`. The route-level catch in [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts) is the single error boundary for routing failures — Story 4.1 AC #6 established this contract. Adding a second `catch` here would risk swallowing errors that need to surface to the 200 `routingError: true` response.
  - [x] 4.5 The old `console.log('[webhooks/stripe] invoice.paid received (not yet implemented):', event.id)` stub line is **deleted** — the new success log replaces it.

- [x] Task 5: Verify the `routeEvent` dispatch still works with the real handler (AC: #1, #8)
  - [x] 5.1 Re-read [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts). The `routeEvent` spy-based dispatch test for `'invoice.paid'` should still pass **without modification** because the function signature is unchanged and the test uses `vi.spyOn(module, 'handleInvoicePaid').mockResolvedValue()` — the spy intercepts before the real body runs.
  - [x] 5.2 Run `npx vitest run src/lib/stripe/webhooks.test.ts` → must be green. If it fails, the `import * as self` self-namespace pattern from Story 4.1 was broken; fix that before proceeding (revert the import to the Story 4.1 shape, do NOT rewrite this test).

- [x] Task 6: Verify the route test still works (AC: #8)
  - [x] 6.1 Re-read [src/app/api/webhooks/stripe/route.test.ts](src/app/api/webhooks/stripe/route.test.ts). All cases should pass unchanged — the route test uses `vi.mock('@/lib/stripe/webhooks')` to replace handlers with `vi.fn()`s, so the real body of `handleInvoicePaid` is never executed at the route test level.
  - [x] 6.2 Run `npx vitest run src/app/api/webhooks/stripe/route.test.ts` → must be green. If it fails, the `vi.mock` shape is wrong or an import side-effect is leaking — fix the mock, do NOT touch the Story 4.1 route code.

- [x] Task 7: Write the `invoice-paid.test.ts` unit test file (AC: #9)
  - [x] 7.1 Create [src/lib/stripe/invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts). (File location rationale: this test file is specific to `handleInvoicePaid`'s heavy scenarios — keeping it separate from `webhooks.test.ts` preserves the dispatch-only focus of that test file and keeps each file under ~300 lines for readability.)
  - [x] 7.2 Hoist mocks ABOVE imports (Vitest auto-hoists `vi.mock`, but the imports must be the SDK-from-path form):
    - `vi.mock('stripe', ...)` — plain-function constructor, lifted verbatim from [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts). Do NOT re-discover the Vitest v4 gotcha.
    - `vi.mock('@/lib/firebase/admin', ...)` — stub `adminDb.runTransaction` to a `vi.fn()` that the tests control per case. Also stub `adminDb.collection(...).doc(...)` to return a stable `userRef` ref object (needed because the transaction body calls `adminDb.collection('users').doc(firebaseUid)`).
    - `vi.mock('@/lib/stripe/server', ...)` — stub `getStripe` (returning an object with `subscriptions.retrieve: vi.fn()`) and stub `retryStripeCall` to directly invoke its callback **on all happy-path tests** — the retry helper has its own tests (see Task 7.7).
  - [x] 7.3 Import `handleInvoicePaid` from `@/lib/stripe/webhooks` (the real function under test — do NOT mock it, do NOT spy on it, you're testing its body directly).
  - [x] 7.4 Build a `makeEvent(invoiceOverrides?: Partial<Stripe.Invoice>): Stripe.Event` factory at the top of the describe block so each test case doesn't repeat the event literal. Keep the factory minimal — only the fields the schema and handler actually read.
  - [x] 7.5 Write all 11 test cases from AC #9. Group them under a single `describe('handleInvoicePaid', ...)`. Happy-path cases use real `Timestamp` / `FieldValue` imports; drift-case tests mock them through the firebase-admin mock.
  - [x] 7.6 For the transient-retry test case, add a second describe block or inline setup that DOES NOT stub `retryStripeCall` — instead use the real helper (import it from the real `@/lib/stripe/server`) with `vi.useFakeTimers()`. The retry test is the one place where the real retry logic must run. Use `vi.advanceTimersByTimeAsync(300)` between retry attempts. **Critical:** switch back to `vi.useRealTimers()` in the `afterEach` of that block — otherwise subsequent tests will hang on real `setTimeout` calls.
  - [x] 7.7 **Do NOT write a separate `retryStripeCall.test.ts` file.** The retry helper is exercised through the transient / non-transient / exhaustion cases in `invoice-paid.test.ts`. Creating a second test file would split the assertions and invite drift. Epic 3 retro: "one canonical test file per behavior".
  - [x] 7.8 Run `npx vitest run src/lib/stripe/invoice-paid.test.ts` → must be green (11 cases).

- [x] Task 8: Full-suite regression pass (AC: #10)
  - [x] 8.1 `npx vitest run` — full suite green; count greater than 254. Target landing around 265–275 (11 new cases here + 1 extended assertion in the checkout session test; the exact number depends on how finely each AC #9 case splits).
  - [x] 8.2 If the Vitest file-parallelism flake from Epic 3 retro #6 surfaces, fall back to `npx vitest run --no-file-parallelism` and note it in Completion Notes. **Do not chase the flake in this story.**
  - [x] 8.3 `npm run lint` — 0 errors, 0 warnings. The strictest rule you'll hit is probably `@typescript-eslint/no-unused-vars` on an unused field from a destructure — fix it at source, don't `eslint-disable-next-line`.

- [x] Task 9: `npm run build` (AC: #10, separate task per Epic 3 retro #10)
  - [x] 9.1 `npm run build` — zero type errors.
  - [x] 9.2 Confirm `/api/webhooks/stripe` still appears as `ƒ (Dynamic) Node runtime` in the route manifest output (regression guard from Story 4.1 AC #1).
  - [x] 9.3 Confirm no new routes accidentally appeared in the manifest — this story adds lib files only, no new `app/**/route.ts`.

- [x] Task 10: Manual smoke with real Stripe listener (AC: #6, human-verified)
  - [x] 10.1 **Prerequisite check:** confirm all Human Prerequisites checkboxes at the top of this story are ticked. If `stripe listen` is not running, Task 10 will fail silently (the 200 OK will show in the Stripe CLI but no writes will land in Firestore because the dev server isn't forwarding).
  - [x] 10.2 **Create a fresh test subscription via the UI**: sign in as a known Firebase test user (note the `uid` — you'll query Firestore by it), go to `/pricing`, click "Subscribe monthly", complete Stripe test checkout (card `4242 4242 4242 4242`, any future date, any CVC). Confirm redirect back to `/dashboard?checkout=success`. This creates a real `Stripe.Subscription` with the new `subscription_data.metadata.firebase_uid` populated by Task 1.
  - [x] 10.3 In the Next.js dev-server console, verify the `invoice.paid` webhook fires automatically (Stripe sends `invoice.paid` immediately on successful subscription creation). You should see the `[webhooks/stripe] invoice.paid processed:` log line with the test user's `uid`, `plan: monthly`, and an ISO timestamp.
  - [x] 10.4 In Firebase Console (or `firebase firestore:query`), open the `users/{uid}` document for the test user. Verify the following fields are present with the correct values:
    - `status: 'active'`
    - `plan: 'monthly'`
    - `current_period_end`: a Firestore `Timestamp` approximately one month from now
    - `stripe_subscription_id`: starts with `sub_`
    - `stripe_customer_id`: starts with `cus_`
    - `updated_at` and `created_at` (the latter only if the user was brand-new)
  - [x] 10.5 In Firebase Console, open the `stripe_events` collection. Verify a new document with the invoice.paid event ID exists (Story 4.1's dedup record).
  - [x] 10.6 **Duplicate replay test**: copy the event ID from step 10.5 and run `stripe events resend <event_id>`. In the dev-server console, verify the log is `[webhooks/stripe] duplicate event skipped:` + the event ID (NOT a second `invoice.paid processed:` log line). Verify in Firestore that `users/{uid}.updated_at` is **unchanged** (same millisecond value) — this is the proof that the handler body was NOT re-run, dedup worked end-to-end.
  - [x] 10.7 **Second payment test**: trigger `stripe trigger invoice.paid` to synthesize a fresh invoice.paid for a test subscription. In the dev-server console, verify a new `[webhooks/stripe] invoice.paid processed:` log line with a DIFFERENT event ID. Note: `stripe trigger` uses a throwaway subscription, so this test may throw on the `firebase_uid` missing case (AC #4's "legacy subscriptions" path) — that's **expected** and acceptable for the smoke. The goal of 10.7 is to verify the throw path doesn't crash the dev server; the Firestore write path is covered by 10.2–10.4.
  - [x] 10.8 Document results in Completion Notes. If any step fails, **stop and file a defect against this story**; do not mark it done.

## Dev Notes

### Why `subscription_data.metadata` on the Checkout Session (not session-level metadata alone)

Stripe's Checkout Session has a top-level `metadata` field (what Story 3.2 already sets) AND a `subscription_data.metadata` field. They serve different purposes:

- Session-level `metadata` lives on the `Stripe.Checkout.Session` object for ~24 hours and then disappears when the session expires. It is accessible via `stripe.checkout.sessions.retrieve` during the short window after checkout.
- `subscription_data.metadata` is copied onto the newly-created `Stripe.Subscription` object and **lives for the lifetime of the subscription** — months or years. Every subsequent `invoice.paid` for the same subscription can retrieve this metadata with a single `stripe.subscriptions.retrieve(id)` call.

Story 4.2 needs to resolve the Firebase `uid` on EVERY invoice.paid event (including renewals happening 11 months after checkout), so the metadata must live on the long-lived Subscription object, not the short-lived Session.

Alternative considered and rejected: query `stripe.checkout.sessions.list({ subscription: sub_id })` on each invoice.paid. This is one extra API call per event, returns paginated results, and fails silently if Stripe's session retention window has lapsed (which has happened in production at other companies on long-tenure subscribers). Setting `subscription_data.metadata` at session creation time is a one-line fix with no runtime cost and no operational failure mode.

Cost of the fix: one additional line in [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts). Scope-creep risk: low, because the edit is surgical and the regression surface is a single existing test assertion. Per the project's "pick the safest option, ignoring token cost" direction from Story 4.1 Dev Notes.

### Why the API call happens outside the Firestore transaction

Firestore transactions have a ~60s wall-clock limit and a "fast, idempotent reads/writes only" constitutional rule in their SDK docs: any I/O inside the transaction closure risks transaction retry loops on transient errors. If you put `stripe.subscriptions.retrieve` inside the transaction:

1. The first attempt fails with a transient Stripe connection error.
2. The Firestore SDK sees the transaction aborted, retries.
3. The second attempt succeeds, but now you've made two Stripe API calls — doubling the load and risking rate limits.
4. Worse: if the transient error was on the Firestore side (contention retry), Stripe might see N calls for N retries.

The correct shape is **resolve-then-transact**: do the Stripe retrieve (with its own retry budget) in plain `await` outside the transaction, then enter the transaction closure with a resolved `subscription` object and only Firestore I/O inside. The transaction becomes tight, fast, and retry-safe.

### Why `tx.update` on the exists-path (not `tx.set` with `{ merge: true }`)

They behave similarly but their failure modes differ:

- `tx.update(ref, fields)` throws if the document does NOT exist. This is the invariant we WANT on the exists-branch — we already checked `snap.exists`, so if the transaction retries and the document has been deleted between retries (a user account deletion flow, Story 6.2), we want to fail loudly rather than silently re-materialize a user doc from a webhook.
- `tx.set(ref, fields, { merge: true })` succeeds whether the document exists or not, silently creating it if missing. This hides the race described above and could resurrect a deleted user's subscription data.

The create-path uses `tx.create` (not `tx.set`) for the same reason: `tx.create` throws `ALREADY_EXISTS` if the document exists, which is the invariant we want on the create-branch.

Both `tx.update` and `tx.create` failing fast on invariant violations keeps the webhook handler's error signal clean: a thrown error → route-level catch → 200 `routingError: true` → event stays in `stripe_events` → operator can investigate via manual replay.

### Why a Zod schema at all (given `constructEvent` already verified the signature)

Stripe's signature guarantees the payload **came from Stripe**; it does not guarantee the payload **has the shape Story 4.2 expects**. Two drift scenarios this schema defends against:

1. **Stripe API version drift.** [src/lib/stripe/server.ts](src/lib/stripe/server.ts) pins the Stripe API version (currently `2026-03-25.dahlia`). If Stripe deprecates `invoice.lines.data[0].period.end` (or restructures it into `invoice.period.end` at some future API version), the handler needs to fail fast with a clear schema error rather than throw `TypeError: Cannot read properties of undefined (reading 'end')` halfway through the Firestore transaction.
2. **Test payload drift.** Hand-crafted test fixtures in `invoice-paid.test.ts` might lose a field during a future refactor. The schema catches this at test-time rather than production-time.

The schema is **narrow** — only the three fields the handler reads. Expanding it to cover the full `Stripe.Invoice` type is anti-useful: the `Stripe.Invoice` TypeScript type already handles that at compile time, and a runtime full-schema validation is expensive + redundant + fragile to Stripe API additions.

### Previous Story Intelligence (carried from Stories 4.1 and Epic 3 retro)

*Each bullet is concrete and actionable; if something here contradicts a Task above, the Task wins and please flag the contradiction in Completion Notes.*

- **`import * as self from './webhooks'` is load-bearing.** Story 4.1 Completion Notes explain why. Do NOT remove it; Task 5 depends on `vi.spyOn` continuing to intercept intra-module calls to `handleInvoicePaid`.
- **Plain-function `Stripe` constructor mock pattern.** Lifted from [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts). The ES-module-constructor gotcha in Vitest v4 is already solved — do not re-discover it. Epic 3 retro #3.
- **Never a silent `catch {}`.** Every `catch` in this story's new code logs via `console.error` with `[webhooks/stripe]` prefix BEFORE acting. A reviewer will `rg -n 'catch \{' src/lib/stripe` and any hit without an immediate `console.error` is a defect. Epic 3 retro #3.
- **`npm run build` is a separate DoD line.** Task 9, not merged into Task 8. Epic 3 retro #10.
- **`zod/v4` import path, not bare `zod`.** Epic 3 standardized on the v4 path. [src/app/api/checkout/session/route.ts:1](src/app/api/checkout/session/route.ts#L1) is the canonical example.
- **`adminDb` is a Proxy.** Any test file importing `webhooks.ts` (directly or transitively) must mock `@/lib/firebase/admin` BEFORE the import — Story 4.1 Dev Notes. Task 7.2 handles this.
- **`.env.example` and the env tripwire test need NO changes.** `STRIPE_WEBHOOK_SECRET` is already declared. No new env vars in Story 4.2. Do NOT touch [src/lib/env.test.ts](src/lib/env.test.ts).
- **Stripe SDK pinned at `^22.0.1`.** Type imports reference `Stripe.Event`, `Stripe.Invoice`, `Stripe.Subscription`. If you see an unfamiliar type error, read `node_modules/stripe/types/Invoices.d.ts` and `node_modules/stripe/types/Subscriptions.d.ts` first. Epic 3 retro #3.
- **Vitest file-parallelism flake is latent.** Epic 3 retro #6. Fallback: `--no-file-parallelism`. Do NOT chase the flake in this story. Adding 11 new test cases here materially increases the risk of tripping it; budget a minute for the fallback if it trips.
- **Do NOT fix Epic 3 retro action item #4** (PlanCta hydration mismatch) in this story. Separate ticket.
- **Do NOT touch the `allow_promotion_codes` / `discounts` block** in [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts). Epic 3 retro #4, same reason.

### Stripe API reference (v22, API version `2026-03-25.dahlia`)

The Stripe types Story 4.2 reads:

- **`Stripe.Event`** — `event.id`, `event.type`, `event.data.object` (already typed as the event-specific object when narrowed by `event.type`)
- **`Stripe.Invoice`** (from `event.data.object` when `event.type === 'invoice.paid'`):
  - `invoice.subscription: string | Stripe.Subscription | null` — narrow to string via the schema
  - `invoice.customer: string | Stripe.Customer | null` — unused in 4.2 (we pull `customer` from the retrieved Subscription instead, for consistency)
  - `invoice.lines.data[i].period.end: number` — Unix seconds for the billing period end (this is what becomes `current_period_end`)
- **`Stripe.Subscription`** (from `stripe.subscriptions.retrieve`):
  - `subscription.id: string`
  - `subscription.customer: string | Stripe.Customer`
  - `subscription.metadata: Record<string, string>` — where Task 1's `firebase_uid` and `plan_id` live
  - `subscription.status: Stripe.Subscription.Status` — unused in 4.2 (`invoice.paid` implies active; 4.3 handles the not-active transitions)

Local SDK file references:
- `node_modules/stripe/types/Invoices.d.ts` — full `Stripe.Invoice` shape
- `node_modules/stripe/types/Subscriptions.d.ts` — full `Stripe.Subscription` shape and `retrieve` method signature
- `node_modules/stripe/types/Events.d.ts` — `Stripe.Event` discriminated union

### Firestore `users/{uid}` document shape after this story

```
users/{uid}
  ├── status: 'active' | (will gain 'past_due' | 'canceled' in Story 4.3)
  ├── plan: 'monthly' | 'yearly'
  ├── current_period_end: Timestamp
  ├── stripe_subscription_id: string
  ├── stripe_customer_id: string
  ├── updated_at: Timestamp (server)
  └── created_at: Timestamp (server, only set on first create)
```

Stories 5.x (dashboard) will add read hooks via [src/lib/firebase/useSubscription.ts](src/lib/firebase/useSubscription.ts) (architecture.md:556) with a Zod `.transform()` to convert snake_case → camelCase for the UI. Story 4.2 intentionally writes snake_case to match Stripe's naming convention (architecture.md:305-307).

### Naming Conventions (from Architecture)

- `users` collection name: `snake_case`, plural (architecture.md:305)
- Document fields: `snake_case` (`current_period_end`, `stripe_subscription_id`, `stripe_customer_id`, `updated_at`, `created_at`, `status`, `plan`) — matches Stripe webhook payload naming (architecture.md:306)
- Function names: `camelCase` (`handleInvoicePaid`, `retryStripeCall`, `invoicePaidSchema`)
- Log tag: `[webhooks/stripe]` — matches Story 4.1's prefix; a single grep across `src/app/api/webhooks` and `src/lib/stripe/webhooks.ts` should show every log line from Epic 4 with one consistent tag

### Anti-Patterns to Avoid

- **Putting `stripe.subscriptions.retrieve` inside the Firestore transaction.** See Dev Notes → "Why the API call happens outside the transaction". Transactions are Firestore-only.
- **Using `tx.set(ref, ..., { merge: true })` instead of `tx.update` / `tx.create`.** See Dev Notes → "Why `tx.update` on the exists-path".
- **Expanding the Zod schema to cover the full `Stripe.Invoice` type.** Narrow is correct. See Dev Notes → "Why a Zod schema at all".
- **Adding a generic retry wrapper to the whole Stripe client.** `retryStripeCall` is a targeted helper for one call site (`subscriptions.retrieve` in `handleInvoicePaid`). Story 4.3 may want its own retry for `customer.subscription.deleted` handling — it can use the same helper. Do not inject retry at the `getStripe()` layer.
- **Writing a separate `retryStripeCall.test.ts`.** Task 7.7 — the helper is tested through `invoice-paid.test.ts`.
- **Creating a parallel `stripe_events_processed` or similar collection to track "successful processing".** The success signal is the `users/{uid}.updated_at` timestamp + the log line. Adding a second dedup / audit collection doubles the write cost and invites consistency bugs. If operator tooling later needs a processed-events audit, that's a separate ticket.
- **Optimistically updating Firestore before calling Stripe.** The sequence must be: verify → resolve-via-Stripe → transact. An optimistic write followed by a Stripe failure would leave `users/{uid}` in a pseudo-active state with no subscription ID.
- **Handling `invoice.payment_failed` or `customer.subscription.deleted` logic in this story.** Those are Story 4.3. The stubs in `webhooks.ts` stay no-ops through the end of Story 4.2.
- **Writing a new `.env.example` variable.** No new env vars. If you find yourself editing `.env.example`, stop and re-read AC #2.
- **Refactoring [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts) beyond the one-line metadata addition.** Task 1.4 is strict about this. Every incidental refactor in an Epic 4 story re-opens surface area from Epic 3.
- **Adding `authorization` / `role` field to `users/{uid}`.** Out of scope. Epic 5 / future.

### Project Structure Notes

- **New files:**
  - [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts) — new schema file (Task 3)
  - [src/lib/stripe/invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts) — new test file (Task 7)
- **Modified files:**
  - [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts) — one-line `subscription_data.metadata` addition (Task 1)
  - [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) — extend existing happy-path assertion (Task 1.6)
  - [src/lib/stripe/server.ts](src/lib/stripe/server.ts) — add `retryStripeCall` export (Task 2)
  - [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) — replace `handleInvoicePaid` stub body (Task 4). Imports added; function signature unchanged; other stubs untouched.
- **Not modified:** `.env.example`, [src/lib/env.test.ts](src/lib/env.test.ts), [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts), [src/app/api/webhooks/stripe/route.test.ts](src/app/api/webhooks/stripe/route.test.ts), [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts), [src/lib/firebase/admin.ts](src/lib/firebase/admin.ts). Story 4.1's surface area is treated as stable.
- Folder placement: `src/lib/schemas/` matches architecture.md:547-550.
- If you find yourself editing the webhook route file ([src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts)), stop. Story 4.2 should not need to touch it — the whole point of Story 4.1's "thin HTTP shell + logic in `lib/`" split was that subsequent stories extend `lib/stripe/webhooks.ts`, not the route file.

### References

- [Epics file — Story 4.2 AC](../planning-artifacts/epics.md) — lines 385-399 (`_bmad-output/planning-artifacts/epics.md#L385-L399`)
- [Architecture — Webhook Event Flow](../planning-artifacts/architecture.md) — lines 373-380 (verify → dedup → route → transact → 200)
- [Architecture — Webhook Idempotency + Transactions](../planning-artifacts/architecture.md) — lines 202-205 (dual strategy)
- [Architecture — Error Handling Patterns](../planning-artifacts/architecture.md) — lines 392-395 (webhook handler try/catch → log → return 200)
- [Architecture — Data Exchange Formats](../planning-artifacts/architecture.md) — lines 353-361 (Firestore Timestamp, Stripe Unix seconds, Zod `.transform()`)
- [Architecture — Naming Conventions](../planning-artifacts/architecture.md) — lines 303-322 (snake_case collections/fields, camelCase code)
- [Architecture — Webhook Schema File Location](../planning-artifacts/architecture.md) — line 550 (`src/lib/schemas/webhook-events.ts`)
- [Story 4.1 — Stripe Webhook Endpoint](./4-1-stripe-webhook-endpoint-with-signature-verification.md) — the full Dev Notes section is required reading for Story 4.2's route-level error contract (AC #6), the `import * as self` pattern, and the `stripe_events` dedup invariant
- [Epic 3 Retrospective](./epic-3-retro-2026-04-14.md) — action items #3 (silent catches), #4 (PlanCta hydration — explicitly out of scope), #5 (webhook secret rotation), #6 (Vitest parallelism flake), #9 (read SDK notes before library bumps), #10 (build in DoD)
- [Existing Checkout Session route](../../src/app/api/checkout/session/route.ts) — Task 1 edit target; AC #2 reference for session metadata shape
- [Existing Checkout Session test](../../src/app/api/checkout/session/route.test.ts) — Task 1.6 edit target; plain-function `Stripe` constructor mock reference for Task 7.2
- [Existing Stripe server singleton](../../src/lib/stripe/server.ts) — Task 2 edit target; `getStripe()` and `getPlanPriceId()` exports live here
- [Existing Webhooks routing module](../../src/lib/stripe/webhooks.ts) — Task 4 edit target; `handleInvoicePaid` stub body to be replaced
- [Existing Webhooks unit test](../../src/lib/stripe/webhooks.test.ts) — Task 5 regression target; `routeEvent` dispatch must continue to pass
- [Existing Webhook route handler](../../src/app/api/webhooks/stripe/route.ts) — Story 4.1 surface; reference only, do not modify
- [Existing Webhook route test](../../src/app/api/webhooks/stripe/route.test.ts) — Task 6 regression target
- [Existing Firebase Admin init](../../src/lib/firebase/admin.ts) — `adminDb` export, Proxy-based (see Story 4.1 Dev Notes for why this matters in tests)
- [Existing Pricing plan registry](../../src/lib/pricing/plans.ts) — `PLAN_IDS` and `PLAN_BY_ID` exports for plan_id validation
- Stripe public docs (informational only — do not fetch during dev-story unless blocked):
  - https://docs.stripe.com/api/invoices/object — `Stripe.Invoice` reference
  - https://docs.stripe.com/api/subscriptions/object — `Stripe.Subscription` reference
  - https://docs.stripe.com/api/subscriptions/retrieve — `subscriptions.retrieve` method
  - https://docs.stripe.com/api/checkout/sessions/create — `subscription_data.metadata` field
  - https://docs.stripe.com/api/errors — Stripe error types for transient classification
  - https://docs.stripe.com/webhooks#retries — Stripe's at-least-once delivery + retry semantics (background context for the dedup invariant)

## Dev Agent Record

### Agent Model Used

claude-opus-4-6[1m]

### Debug Log References

- `npx vitest run src/app/api/checkout/session/route.test.ts` → 14/14 pass
- `npx vitest run src/lib/stripe/webhooks.test.ts src/app/api/webhooks/stripe/route.test.ts` → 15/15 pass
- `npx vitest run src/lib/stripe/invoice-paid.test.ts` → 12/12 pass
- `npx vitest run` (full suite) → **267/267 pass** (baseline 254 → +13)
- `npm run lint` → 0 errors, 0 warnings
- `npm run build` → green, `/api/webhooks/stripe` appears as `ƒ` dynamic Node route; no new routes

### Completion Notes List

- **Task 1 (AC #2):** Added `subscription_data: { metadata: { firebase_uid, plan_id } }` to the Checkout Session payload in [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts) as a surgical additive edit. Top-level `metadata`, `allow_promotion_codes`, and the `discounts` branching were untouched. Extended the happy-path assertion in [route.test.ts](src/app/api/checkout/session/route.test.ts) to check both the session-level and subscription-level metadata.
- **Task 2 (AC #4):** Added `retryStripeCall<T>(fn, label)` to [src/lib/stripe/server.ts](src/lib/stripe/server.ts). Three attempts with 250ms/750ms backoff between retries (third retry is immediate per the spec's "waited 1s total" parenthetical). Transient classification via `err.type` (`StripeConnectionError` / `StripeAPIError` / `StripeRateLimitError`) plus `statusCode >= 500`. Non-transient errors re-throw immediately. Each retry and the final exhaustion log to `console.error` with the `[stripe/retry]` prefix for audit.
- **Task 3 (AC #3):** Created [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts) with `invoicePaidSchema` and `InvoicePaidPayload` type. Narrow schema — only the three fields the handler reads. `zod/v4` import path per Epic 3 standard.
- **Task 4 (AC #1, #3, #4, #5, #6):** Replaced the `handleInvoicePaid` stub in [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts). Sequence matches the task spec exactly: Zod parse → retry-wrapped `subscriptions.retrieve` → metadata validation → customer coercion → Firestore transaction with create-vs-update branching → success log. `import * as self from './webhooks'` self-namespace left intact. The other two stub handlers (`handleSubscriptionDeleted`, `handlePaymentFailed`) are unchanged — Story 4.3 owns them.
- **Tasks 5–6 (AC #1, #8):** Existing `webhooks.test.ts` (2 dispatch cases) and `route.test.ts` (10 cases) pass unmodified. The self-namespace spy interception from Story 4.1 continues to work.
- **Task 7 (AC #9):** Created [src/lib/stripe/invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts) with 12 cases (the 11 from AC #9 plus a dedicated Timestamp-instance assertion). All mocks hoisted via `vi.hoisted`. `firebase-admin/firestore` mocked with a `FakeTimestamp` class so `instanceof` assertions work; `@/lib/stripe/server` mocked via `importOriginal` so the **real** `retryStripeCall` is exercised in the transient/non-transient/exhaustion cases. Fake timers drive retry backoff.
- **Task 8–9 (AC #10):** Full regression → 267/267 green (254 → 267, +13 cases: +12 new in `invoice-paid.test.ts` and +1 extended assertion in the checkout session test). Lint 0/0. Build green with the webhook route still shown as dynamic Node.
- **Task 10 (AC #6, human-verified):** **Deferred to human smoke.** This and the Human Prerequisites section at the top of the story are left unchecked for the developer to run against a live `stripe listen` forwarder — the dev agent cannot execute the end-to-end Stripe + Firestore verification.
- **Stripe best-practices cross-check:** Consulted the stripe-best-practices skill — the approach (subscription_data.metadata propagation, resolve-then-transact, separate `stripe_events` dedup collection, SDK v22 on API version `2026-03-25.dahlia`) has no flagged anti-patterns.

### Code Review Follow-ups (AI, 2026-04-15)

- **H1 fixed (AC #4 vs Task 2.3 contradiction):** Tightened `isTransientStripeError` in [src/lib/stripe/server.ts](src/lib/stripe/server.ts) so `StripeAPIError` is treated as transient only when `statusCode` is 5xx OR absent (the SDK uses `StripeAPIError` as a 5xx-class base by default). A 4xx-classed `StripeAPIError` now falls through immediately instead of burning the full retry budget — matches AC #4's "not retried on 4xx" contract. Task 2.3's broader definition is deliberately narrowed; called out here per Dev Notes "Task wins but flag it".
- **H2 fixed (AC #7 closure-retry test was missing):** Added `Firestore transaction retries re-read users/{uid} inside the closure (AC #7)` case to [src/lib/stripe/invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts). Drives `runTransaction` to invoke the handler's callback twice with a flipped `{exists}` sequence and asserts `tx.get` is called on each attempt and the terminal branch reflects the second attempt's snap — a hoisted `snap` would fail this test.
- **M1 fixed (silent non-transient throw in `retryStripeCall`):** Added a `console.error('[stripe/retry] ${label} non-transient error, not retrying:', err)` line before the immediate re-throw. The outer `handleInvoicePaid` still emits its own `subscription retrieve failed after retries:` log, but the inner catch is no longer silent.
- **M2 fixed (loose timer precision in retry test):** `transient Stripe error retried successfully` now advances timers in two steps: 249ms (asserts still 1 call), then 2ms past the 250ms boundary (asserts 2 calls). A regression that silently changed the backoff constant would now trip this test.
- **Test count:** 267 → 268 (new closure-retry case). Full suite green via `npx vitest run --no-file-parallelism` to sidestep the Epic 3 retro #6 `dashboard/layout.test.tsx` parallelism flake (unrelated to Story 4.2).

### Stripe API Drift Defect (2026-04-15 manual smoke finding)

First Task 10 smoke attempt surfaced a real defect. Next.js dev-server log:

```
[webhooks/stripe] invoice.paid payload failed schema validation: [
  { expected: 'string', path: ['subscription'], message: 'Invalid input: expected string, received undefined' }
] evt_1TMVt1A3LvU3iaSC7HEO81r7
```

**Root cause:** Stripe API version `2026-03-25.dahlia` (pinned in [src/lib/stripe/server.ts](src/lib/stripe/server.ts#L7)) **removed the top-level `invoice.subscription` field**. The subscription id now lives at `invoice.parent.subscription_details.subscription` (confirmed via `node_modules/stripe/cjs/resources/Invoices.d.ts` lines 344, 647, 843–852 — `Invoice.parent: Invoice.Parent | null` → `Parent.subscription_details: Parent.SubscriptionDetails | null` → `SubscriptionDetails.subscription: string | Subscription`). The story's AC #3 schema block was drafted against the pre-dahlia shape and never exercised with a live payload until Task 10.

This is **exactly the drift scenario the Zod schema was designed to catch** (Dev Notes → "Why a Zod schema at all"). The schema's fail-fast behavior worked as designed: the route caught, logged, returned 200 `routingError: true`, and the event stayed in `stripe_events` for replay. No corrupted writes.

**Fix applied:**

- [src/lib/schemas/webhook-events.ts](src/lib/schemas/webhook-events.ts) — replaced top-level `subscription` field with nested `parent.subscription_details.subscription`. Added inline comment referencing the dahlia relocation + SDK type file.
- [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) — reads `subId` from `parsed.data.parent.subscription_details.subscription` (one-line path change).
- [src/lib/stripe/invoice-paid.test.ts](src/lib/stripe/invoice-paid.test.ts) — `makeInvoice` factory updated to new shape; Zod schema-failure bad-payload case now builds `parent: { subscription_details: {} }` to trigger the same error. All 13 cases still green.

**AC #3 deviation:** The literal AC #3 schema block in this story still shows `subscription: z.string().min(1)` at the top level. The implementation intentionally deviates to match the actual Stripe dahlia payload shape. Per the story's own rationale in Dev Notes → "Why a Zod schema at all" (defense against API drift), this is the correct resolution. The AC block should be read as "schema validates subscription id + period.end + customer" regardless of JSON path.

**Verification:** `npx vitest run --no-file-parallelism` → 268/268 green. `npm run build` → clean, `/api/webhooks/stripe` still `ƒ` Dynamic.

**Potential future optimization (NOT done in this patch):** `invoice.parent.subscription_details` also carries `metadata: Metadata | null` as an immutable snapshot of the subscription metadata at invoice finalization time. Reading `firebase_uid` / `plan_id` directly from there would eliminate the `subscriptions.retrieve` call entirely — one less network round-trip, no retry budget needed, fewer failure modes. Deferring because (a) it's a bigger contract change than AC #4 allows without re-writing the story, and (b) the current retrieve-based path is viable on dahlia. File as an Epic 4 retro item if webhook latency under NFR14 becomes tight.

**Next step:** re-run Task 10 smoke against the fixed code. Create a fresh test subscription via `/pricing`, observe `[webhooks/stripe] invoice.paid processed:` in the dev-server log, confirm `users/{uid}` document in Firestore Console with `status: 'active'`, `plan`, `current_period_end` (Timestamp), `stripe_subscription_id`, `stripe_customer_id`, `updated_at`, `created_at`.

### File List

**New files:**
- `src/lib/schemas/webhook-events.ts`
- `src/lib/stripe/invoice-paid.test.ts`

**Modified files:**
- `src/app/api/checkout/session/route.ts`
- `src/app/api/checkout/session/route.test.ts`
- `src/lib/stripe/server.ts`
- `src/lib/stripe/webhooks.ts`

### Change Log

- **2026-04-14** — Story 4.2 implementation complete (code tasks 1–9, manual smoke Task 10 deferred to human). `invoice.paid` webhook now atomically activates `users/{uid}` subscription state via Firestore transaction with `subscription_data.metadata`-sourced `firebase_uid`/`plan_id`. Full suite 254 → 267. Status: ready-for-dev → review.
- **2026-04-15** — Code review pass: H1 (StripeAPIError 5xx guard), H2 (AC #7 closure-retry regression test), M1 (non-transient log), M2 (precise timer boundary). Test count 267 → 268.
- **2026-04-15** — Task 10 manual smoke executed and green. Dahlia API drift defect surfaced and fixed during smoke: Stripe removed top-level `invoice.subscription` in API version `2026-03-25.dahlia` and moved it to `invoice.parent.subscription_details.subscription`. Updated `invoicePaidSchema`, `handleInvoicePaid`, and `invoice-paid.test.ts` accordingly (all 13 cases still green, full suite 268/268). Post-fix smoke: fresh checkout → `[webhooks/stripe] invoice.paid processed: evt_1TMVt1A3LvU3iaSC7HEO81r7 222UIiXc4QfY8ikAFFGGMDqNyQI3 monthly 2026-05-15T16:01:41.000Z` (825ms, well under NFR14 5s). `users/222UIiXc4QfY8ikAFFGGMDqNyQI3` verified in Firestore with all 7 fields (status=active, plan=monthly, current_period_end Timestamp, stripe_subscription_id=sub_1TMVsqA3LvU3iaSCpHXPDzE2, stripe_customer_id=cus_ULCHNT5D74xtVI, updated_at, created_at matches updated_at — create branch). Duplicate replay via `stripe events resend` → `[webhooks/stripe] duplicate event skipped:` (dedup verified). `stripe trigger invoice.paid` → expected legacy-subscription throw path, dev server stayed up. Status: review → done.
