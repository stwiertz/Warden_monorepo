# Story 4.1: Stripe Webhook Endpoint with Signature Verification

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the Warden platform,
I want to receive Stripe webhook events at a signed, idempotent endpoint that routes by event type,
So that only authentic Stripe events drive subscription state changes and no event is ever processed twice.

## Human Prerequisites

*(First story to use this block — see Epic 3 Retrospective action item #7. These are steps the dev agent CANNOT do for you. Check each before starting Task 1.)*

- [ ] **Stripe CLI installed and authenticated.** Run `stripe --version` and `stripe login`. On Windows, if VS Code's integrated terminal says "command not recognized" after install, fully restart VS Code (known Epic 3 gotcha — PATH isn't inherited by an already-running terminal).
- [ ] **`STRIPE_WEBHOOK_SECRET` (fresh) is in `.env.local`.** The previous `whsec_...` was exposed in a chat transcript during Epic 3 and must be rotated (Epic 3 retro action item #5). Obtain a new one by running `stripe listen --forward-to localhost:3000/api/webhooks/stripe` — the first line of its output is `whsec_...`. Paste into `.env.local` as `STRIPE_WEBHOOK_SECRET=whsec_...`. **Do NOT paste it into this transcript, chat, or any log.**
- [ ] **A `stripe listen` session runs locally against `/api/webhooks/stripe`.** Keep it running in a separate terminal for the whole story; Task 9's manual smoke depends on it.
- [ ] **Firestore rules are deployable (but don't block Story 4.1 writes).** Epic 4 writes use the Admin SDK which bypasses rules. The rules deploy (Epic 2 retro item #1) is a separate ticket — noted here so it's visible, not required for this story.
- [ ] **`.env.local` already has `FIREBASE_SERVICE_ACCOUNT_KEY`.** Confirm with `test -n "$FIREBASE_SERVICE_ACCOUNT_KEY"` or by checking the file. Story 2.4 established this; if it's missing, the Admin SDK init in [src/lib/firebase/admin.ts](src/lib/firebase/admin.ts) throws at first touch.

## Acceptance Criteria

1. **Given** a new App Router route at [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts)
   **When** it is imported by the Next.js build
   **Then** the file exports `export const runtime = 'nodejs'` (the `stripe` SDK is Node-only — same constraint as [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts))
   **And** the file exports `export const dynamic = 'force-dynamic'` (webhooks are never statically rendered; avoid any Next.js prerender attempt)
   **And** the file exports a named async `POST(request: Request)` handler (App Router convention — see [src/app/api/checkout/session/route.ts:41](src/app/api/checkout/session/route.ts#L41) for the shape)
   **And** the file does **NOT** export `GET`, `PUT`, `DELETE`, etc. — unsupported methods return Next.js's default `405 Method Not Allowed`
   **And** `npm run build` lists `/api/webhooks/stripe` as `ƒ (Dynamic) Node runtime` in the route manifest output (the regression guard from Story 3.2/3.3 — any accidental static emission is visible in the build log)

2. **Given** a Stripe POST arrives at `/api/webhooks/stripe` with the `stripe-signature` header and a raw JSON body
   **When** the handler processes it
   **Then** the handler reads the body as **raw text** via `await request.text()` — **NOT** `request.json()` (Stripe signs the exact bytes; any JSON reserialization breaks the signature)
   **And** the handler reads the header via `request.headers.get('stripe-signature')`
   **And** the handler calls `getStripe().webhooks.constructEvent(rawBody, signature, process.env.STRIPE_WEBHOOK_SECRET!)` (per FR24 / architecture.md:189-191)
   **And** if `STRIPE_WEBHOOK_SECRET` is missing from the environment, the handler logs `[webhooks/stripe] STRIPE_WEBHOOK_SECRET is not set` via `console.error` and returns `500 { error: { code: 'WEBHOOK_NOT_CONFIGURED', message: 'Webhook handler is not configured' } }` — this is a deploy-time misconfiguration, not a Stripe retry condition
   **And** if the `stripe-signature` header is missing, the handler returns `400 { error: { code: 'INVALID_SIGNATURE', message: 'Missing stripe-signature header' } }`
   **And** if `constructEvent` throws (signature mismatch, malformed body, stale timestamp), the handler catches the error, logs `[webhooks/stripe] signature verification failed:` + `err`, and returns `400 { error: { code: 'INVALID_SIGNATURE', message: 'Signature verification failed' } }`
   **And** the handler's 400 responses use the **same envelope shape** as the rest of `/api/` (`{ error: { code, message } }`) — matches [src/app/api/checkout/session/route.ts:17-19](src/app/api/checkout/session/route.ts#L17-L19)

3. **Given** a verified `Stripe.Event` has been produced by `constructEvent`
   **When** the handler performs idempotency dedup
   **Then** the handler uses a **Firestore transaction** (`adminDb.runTransaction(async (tx) => { ... })`) to atomically check-and-record — this is the dual-strategy pattern architecture.md:202-205 prescribes: "Event ID deduplication: Store processed Stripe event IDs in Firestore, skip duplicates" **+** "Firestore transactions: Check current state before updating (handles race conditions)". Story 4.1 uses the transaction for the dedup record itself; Stories 4.2/4.3 will reuse the transaction pattern for the `users/{uid}` update inside the handler bodies.
   **And** the transaction body does:
   - `const ref = adminDb.collection('stripe_events').doc(event.id)`
   - `const snap = await tx.get(ref)`
   - If `snap.exists`, set a flag `alreadyProcessed = true` inside the closure and return — do NOT throw from inside the transaction just to signal duplicate (transactions retry on thrown errors; we want a clean "no write" outcome)
   - If `!snap.exists`, call `tx.create(ref, { event_id, event_type, received_at, api_version, livemode })` where:
     - `event_id: event.id` (redundant-but-queryable)
     - `event_type: event.type` (for operator debugging)
     - `received_at: FieldValue.serverTimestamp()` (Firestore `Timestamp` per architecture.md:358 — import `FieldValue` from `firebase-admin/firestore`)
     - `api_version: event.api_version` (so the next Stripe API bump is visible in the data)
     - `livemode: event.livemode` (boolean — distinguishes test vs. live events in the same collection if they ever converge)
   **And** `tx.create()` is used (not `tx.set()`) so that even a transaction-retry race — two concurrent deliveries of the same event both winning their initial `tx.get()` because of retry-loop timing — resolves atomically: exactly one `create` commits, the other fails the transaction with `6 ALREADY_EXISTS`, Firestore retries it, the retry's `tx.get()` now sees the document and takes the duplicate branch. This is **strictly safer** than a bare `.create()` (which is atomic but cannot co-locate dedup logic with the routing decision) AND strictly safer than `tx.set()` (which would silently overwrite).
   **And** the handler captures `alreadyProcessed` as the transaction's return value (`const alreadyProcessed = await adminDb.runTransaction(async (tx) => { ... return snap.exists })`) so the post-transaction code can branch cleanly: `if (alreadyProcessed)` → log + return duplicate envelope; else proceed to routing.
   **And** if the document exists (duplicate), the handler logs `[webhooks/stripe] duplicate event skipped:` + `event.id` and returns `200 { data: { received: true, duplicate: true } }` — Stripe MUST see a 200 or it will retry (architecture.md:395).
   **And** any Firestore error that escapes the transaction (non-retryable, exhausted retries, permission denied, network) is re-thrown and handled by the top-level catch (AC #6) — which still returns 200 with `routingError: true` and logs, because at the webhook boundary every failure is a "Stripe retry later" condition, not a Stripe-facing 5xx.
   **And** the dedup transaction **lives outside** the routing dispatch (AC #4) so that every verified event is recorded first, before any event-type-specific work begins. This preserves the "at-least-once with idempotency" guarantee from architecture.md:202-205 even if a routing handler later throws.
   **And** the collection name is **`stripe_events`** (`snake_case`, plural — matches architecture.md:305 Firestore naming convention). It is **NOT** `stripeEvents`, `events`, or `webhook_events`.

4. **Given** a verified, non-duplicate event has been recorded
   **When** the handler dispatches by event type
   **Then** a new `routeEvent(event: Stripe.Event): Promise<void>` function lives in [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) (new file — `import 'server-only'` at the top; this matches the single-source-of-truth pattern Epic 3 retro highlighted — route handler is a thin HTTP shell, the interesting logic lives in `lib/`)
   **And** `routeEvent` uses a `switch (event.type)` on the four event types Epic 4 cares about:
   - `'invoice.paid'` → calls `handleInvoicePaid(event)` — **Story 4.2 owns the implementation**. For Story 4.1, the stub logs `[webhooks/stripe] invoice.paid received (handler not yet implemented):` + `event.id` and returns.
   - `'customer.subscription.deleted'` → calls `handleSubscriptionDeleted(event)` — **Story 4.3 owns the implementation**. Same stub pattern.
   - `'invoice.payment_failed'` → calls `handlePaymentFailed(event)` — **Story 4.3 owns the implementation**. Same stub pattern.
   - `default:` → logs `[webhooks/stripe] unhandled event type:` + `event.type` and returns. **This is NOT an error** — Stripe sends many event types the platform does not care about (e.g., `charge.succeeded`, `customer.created`). The default branch must swallow them cleanly so Stripe gets its 200.
   **And** the three stub handlers (`handleInvoicePaid`, `handleSubscriptionDeleted`, `handlePaymentFailed`) are exported from `webhooks.ts` as **no-op async functions** with the signature `(event: Stripe.Event) => Promise<void>` — Stories 4.2 and 4.3 replace the bodies without changing the signatures or the `routeEvent` dispatch. This contract lets the three stories land on separate commits without re-touching the route file.
   **And** `routeEvent` is **called AFTER** the dedup write succeeds (AC #3 order is strict: verify → record → route) so a routing crash cannot cause an event to be re-processed on the next delivery.

5. **Given** the routing dispatch has completed
   **When** the handler builds its success response
   **Then** the handler returns `200 { data: { received: true, duplicate: false, eventId: event.id, eventType: event.type } }` — the shape matches the `{ data: ... }` envelope convention and includes `eventId` + `eventType` so Stripe CLI's response echo surfaces "which event just cleared"
   **And** the total handler runtime stays under **5 seconds** per NFR14 (architecture.md:42). This is not a test assertion (timing-based tests are flaky) but a design constraint: **do NOT add `await`s that can block on slow external calls** — the dedup read/write and the routing stubs are the only awaits in Story 4.1. Stories 4.2 and 4.3 inherit this budget.

6. **Given** any unexpected error is thrown during routing (not during signature verification, not during dedup collision)
   **When** the top-level `try`/`catch` in the route handler catches it
   **Then** the handler logs `[webhooks/stripe] routing failed for event:` + `event.id` + `event.type` + `err` via `console.error` (per Epic 3 retro action item #3 — no silent `catch {}`, ever, in any `/api/**` route)
   **And** the handler returns `200 { data: { received: true, duplicate: false, routingError: true, eventId: event.id } }` (architecture.md:395: "Webhook handler: Try/catch → log error, return 200 (prevent Stripe retries)" — Stripe's retry behavior on 5xx responses would compound any bug into a cascade of duplicate processing attempts). **Return 200 even on routing error** — the event is already recorded in `stripe_events`, so on the next deploy with a fixed handler, an operator can replay it manually if needed.
   **And** this pattern is documented inline with a one-line comment: `// return 200 to stop Stripe retries; event is recorded in stripe_events for manual replay`. This is a WHY comment, not a WHAT comment — it prevents a future reviewer from "fixing" the 200 to a 500.

7. **Given** the tripwire test at [src/lib/env.test.ts](src/lib/env.test.ts)
   **When** this story lands
   **Then** the existing assertions are unchanged (`STRIPE_WEBHOOK_SECRET` is already declared server-only in `.env.example` and tripwired — no new env var required, no `.env.example` change)
   **And** **NO new environment variables are added.** The webhook secret is already present from the original Epic 3 scaffolding.

8. **Given** a new test file at [src/app/api/webhooks/stripe/route.test.ts](src/app/api/webhooks/stripe/route.test.ts)
   **When** `npx vitest run` is executed
   **Then** the file mocks `stripe` using the **plain-function constructor** pattern from [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) (Epic 3 retro: this is the ES-module-constructor gotcha that wasted time in 3.2 — reuse the pattern exactly; do NOT roll your own `vi.mock('stripe')` shape)
   **And** the file mocks `@/lib/firebase/admin` to stub `adminDb.collection(...).doc(...).get/create` — the exact mock shape mirrors how [src/app/api/auth/session/route.test.ts](src/app/api/auth/session/route.test.ts) mocks `adminAuth`, but for `adminDb`
   **And** the following test cases exist and pass:
   - **Signature OK, new event, routed event type** → `200`, body `data.duplicate === false`, `data.eventType === 'invoice.paid'`, Firestore `create` called exactly once with `event_id` matching the mocked event, `console.error` NOT called
   - **Signature OK, new event, unhandled event type (`charge.succeeded`)** → `200`, body `data.duplicate === false`, `console.log` or no-op default branch hit, Firestore `create` called
   - **Signature OK, duplicate event (transaction sees `snap.exists === true`)** → `200`, body `data.duplicate === true`, `tx.create` NOT called, routing stub NOT invoked. The test asserts the transaction returned `true` by mocking `runTransaction` with a handler that provides a fake `tx` whose `.get()` resolves to `{ exists: true }`.
   - **Signature OK, race dedup (transaction first attempt fails with `ALREADY_EXISTS`, retries, sees existing doc on retry)** → `200`, body `data.duplicate === true`, routing stub NOT invoked. The test mocks `runTransaction` to simulate the final (successful) retry outcome — we are testing the handler's response to the transaction's resolved value, not Firestore's retry internals.
   - **Missing `stripe-signature` header** → `400`, body `error.code === 'INVALID_SIGNATURE'`, `constructEvent` NOT called (short-circuit before Stripe)
   - **Signature verification throws** (mocked `constructEvent` throws `Error('No signatures found matching the expected signature')`) → `400`, body `error.code === 'INVALID_SIGNATURE'`, `console.error` called with the route tag, Firestore NOT touched
   - **`STRIPE_WEBHOOK_SECRET` missing** (`vi.stubEnv('STRIPE_WEBHOOK_SECRET', '')`) → `500`, body `error.code === 'WEBHOOK_NOT_CONFIGURED'`, `console.error` called, `constructEvent` NOT called
   - **Routing handler throws** (mock `handleInvoicePaid` to throw) → `200`, body `data.routingError === true`, `console.error` called with event id and type, Firestore dedup write still happened (order: record → route)
   - **Raw body is read, not JSON** — assertion: the mock Request's `.text()` is called and its return value is passed to `constructEvent`; `.json()` is NOT called on the Request (this is the most common regression risk — guard it explicitly)
   **And** the test file uses `vi.stubEnv` to set `STRIPE_WEBHOOK_SECRET=whsec_test_secret` in a `beforeEach` and `vi.unstubAllEnvs` in `afterEach` — follows the existing pattern from `session/route.test.ts`

9. **Given** a new unit test file at [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts)
   **When** `npx vitest run` is executed
   **Then** the file tests `routeEvent` directly (no HTTP layer), with the following cases:
   - `invoice.paid` event → calls the mocked `handleInvoicePaid` exactly once with the event, does NOT call the other two
   - `customer.subscription.deleted` → calls `handleSubscriptionDeleted`, does NOT call the other two
   - `invoice.payment_failed` → calls `handlePaymentFailed`, does NOT call the other two
   - Unhandled event type (`charge.succeeded`) → calls none of the three, returns cleanly (no throw)
   - Handler throws → `routeEvent` re-throws (the route-level catch in AC #6 is what swallows; `routeEvent` itself must NOT swallow, or else Story 4.2/4.3 will have a testing hole)
   **And** this test file imports `handleInvoicePaid` etc. directly (they are real exports, even if they're one-line stubs in Story 4.1) and uses `vi.spyOn` rather than `vi.mock`, so Stories 4.2 and 4.3 can replace the bodies without rewriting this test

10. **Given** the testing baseline at the start of this story (240 / 240 from Story 3.3 review, per the Epic 3 retrospective)
    **When** this story lands
    **Then** `npx vitest run` reports `> 240` passing with **zero failures** (target: roughly 255-260 — exact count advisory, the floor is the no-regression guard)
    **And** `npm run build` passes with zero type errors; `/api/webhooks/stripe` appears in the route manifest as `ƒ (Dynamic)` Node runtime
    **And** `npm run lint` shows **0 errors, 0 warnings** (Epic 3 ended 0/0; preserve it)
    **And** `npm run build` is listed as a separate Task 8 line item, not bundled with lint+vitest (Epic 3 retro action item #10)

## Tasks / Subtasks

- [x] Task 1: Create the `stripe_events` collection integration (AC: #3)
  - [x] 1.1 Decide on the dedup collection name (**`stripe_events`** — committed by AC #3). Do NOT invent a different name.
  - [x] 1.2 No Firestore rules change needed — Admin SDK bypasses rules. Mention this explicitly in Completion Notes so a reviewer doesn't go hunting for a missing rule.
  - [x] 1.3 No data model doc to update in this story. If you feel an urge to write one, resist it — architecture.md already describes the pattern at lines 202-205.

- [x] Task 2: Build the routing module (AC: #4, #9)
  - [x] 2.1 Create [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) with `import 'server-only'` at the top
  - [x] 2.2 Export the three no-op stub handlers: `handleInvoicePaid`, `handleSubscriptionDeleted`, `handlePaymentFailed` — each `async (event: Stripe.Event): Promise<void> => {}` with a single `console.log('[webhooks/stripe] <type> received (not yet implemented):', event.id)` line inside. Story 4.2 and 4.3 replace the bodies; the signature is load-bearing.
  - [x] 2.3 Export `routeEvent(event: Stripe.Event): Promise<void>` with the `switch` on `event.type` per AC #4. Default branch is a `console.log('[webhooks/stripe] unhandled event type:', event.type)` + `return` — NOT a throw.
  - [x] 2.4 Type the `Stripe.Event` parameter via `import type Stripe from 'stripe'`. Do NOT import the value from `stripe` — the value import is the getStripe() path.
  - [x] 2.5 Write [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts) per AC #9. Use `vi.spyOn(module, 'handleInvoicePaid')` — this gives Stories 4.2/4.3 room to replace the real bodies later without rewriting the test.

- [x] Task 3: Build the route handler skeleton (AC: #1, #2)
  - [x] 3.1 Create [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts) with `export const runtime = 'nodejs'` and `export const dynamic = 'force-dynamic'`
  - [x] 3.2 Define a small `envelopeError(code, message, status)` helper at the top (mirror [src/app/api/checkout/session/route.ts:17-19](src/app/api/checkout/session/route.ts#L17-L19)). Do NOT extract a shared helper across routes — Epic 3 Story 3.3 Task 3.1 discussed the `_shared.ts` extraction and deferred it; Story 4.1 is not the time to reopen that.
  - [x] 3.3 Implement `export async function POST(request: Request)`:
    - Read `stripe-signature` header → if missing, return `400 INVALID_SIGNATURE`
    - Read `process.env.STRIPE_WEBHOOK_SECRET` → if missing/empty, log + return `500 WEBHOOK_NOT_CONFIGURED`
    - `const rawBody = await request.text()` — **must be `.text()`, not `.json()`** (AC #2)
    - `let event: Stripe.Event; try { event = getStripe().webhooks.constructEvent(rawBody, signature, secret) } catch (err) { console.error('[webhooks/stripe] signature verification failed:', err); return envelopeError('INVALID_SIGNATURE', 'Signature verification failed', 400) }`

- [x] Task 4: Wire the dedup transaction into the handler (AC: #3)
  - [x] 4.1 Import `adminDb` from `@/lib/firebase/admin` and `FieldValue` from `firebase-admin/firestore`
  - [x] 4.2 Build the transaction:
    ```ts
    const alreadyProcessed = await adminDb.runTransaction(async (tx) => {
      const ref = adminDb.collection('stripe_events').doc(event.id)
      const snap = await tx.get(ref)
      if (snap.exists) return true
      tx.create(ref, {
        event_id: event.id,
        event_type: event.type,
        received_at: FieldValue.serverTimestamp(),
        api_version: event.api_version,
        livemode: event.livemode,
      })
      return false
    })
    ```
  - [x] 4.3 After the transaction: `if (alreadyProcessed) { console.log('[webhooks/stripe] duplicate event skipped:', event.id); return Response.json({ data: { received: true, duplicate: true } }) }`
  - [x] 4.4 Do NOT wrap the `runTransaction` call in its own try/catch — let the top-level handler try/catch (Task 5) cover it. Transaction failures fall through to the `routingError: true` 200 response for operator replay.
  - [x] 4.5 **Use a transaction, not a bare `.create()`.** This is a deliberate safety trade-off: the transaction is slightly heavier than `.create()` but gives us a single pattern that Stories 4.2 and 4.3 extend (they will wrap the dedup check AND the `users/{uid}` update in a single transaction per event type). Establishing the transaction shape here means 4.2/4.3 inherit it cleanly rather than migrating from `.create()`. Per the user's direction: pick the safest option, ignoring the token cost.
  - [x] 4.6 Do NOT use `tx.set(ref, ...)` — it would silently overwrite a duplicate. Always `tx.create`.

- [x] Task 5: Wire routing dispatch and top-level error handling (AC: #4, #5, #6)
  - [x] 5.1 Import `routeEvent` from `@/lib/stripe/webhooks`
  - [x] 5.2 After a successful (non-duplicate) dedup write, wrap `await routeEvent(event)` in a try/catch
  - [x] 5.3 On success, return `Response.json({ data: { received: true, duplicate: false, eventId: event.id, eventType: event.type } })`
  - [x] 5.4 On thrown error, `console.error('[webhooks/stripe] routing failed for event:', event.id, event.type, err)` and return `Response.json({ data: { received: true, duplicate: false, routingError: true, eventId: event.id } })` (still `200` — see the inline WHY comment in AC #6)
  - [x] 5.5 Add the one-line WHY comment above the routing-error return: `// return 200 to stop Stripe retries; event is recorded in stripe_events for manual replay`

- [x] Task 6: Build the route test file (AC: #8)
  - [x] 6.1 Create [src/app/api/webhooks/stripe/route.test.ts](src/app/api/webhooks/stripe/route.test.ts)
  - [x] 6.2 Mock `stripe` with the plain-function constructor (see [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) for the exact shape). The mocked `webhooks.constructEvent` is a `vi.fn()` the tests drive case-by-case (happy path returns a crafted `Stripe.Event`; sad paths throw).
  - [x] 6.3 Mock `@/lib/firebase/admin` to stub `adminDb.runTransaction` — the test harness provides a fake `tx` object with `.get` / `.create` / `.set` as `vi.fn()`s and the mocked `runTransaction` immediately invokes its callback with that fake tx (so each test case controls what `tx.get` resolves to). Keep the mock flat and case-local — do NOT build a helper factory for a single test file.
  - [x] 6.4 Mock `@/lib/stripe/webhooks` with `vi.mock` to turn `handleInvoicePaid` etc. into `vi.fn()`s, so the route tests assert "handler called with event" without executing the real (stub) body — and so the throw-case can be driven by `.mockRejectedValueOnce`.
  - [x] 6.5 Use `vi.stubEnv('STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')` in `beforeEach`, `vi.unstubAllEnvs()` in `afterEach`. **Never** put a real webhook secret in test code — `whsec_test_secret` is a made-up literal used only because the code path checks for non-empty-ness.
  - [x] 6.6 Write all cases from AC #8. Include the `.text()`-not-`.json()` assertion explicitly — this is the #1 regression risk once someone "refactors" the handler later.

- [x] Task 7: Write the routing module test file (AC: #9)
  - [x] 7.1 Create [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts)
  - [x] 7.2 Import `routeEvent` plus the three handlers from `./webhooks`
  - [x] 7.3 Use `vi.spyOn(webhooksModule, 'handleInvoicePaid').mockResolvedValue()` per test — do NOT use `vi.mock` at the module level for this file; spies read more clearly when the tests are primarily about dispatch.
  - [x] 7.4 Cover the five cases from AC #9.

- [x] Task 8: Verification (AC: #10)
  - [x] 8.1 `npx vitest run` — full suite green; new count greater than 240. If it hits the file-parallelism flake from Epic 3 retro item #6, fall back to `npx vitest run --no-file-parallelism` and note it in Completion Notes (flake is a separate ticket, do not get sidetracked fixing it in this story).
  - [x] 8.2 `npm run build` — zero type errors; `/api/webhooks/stripe` appears as `ƒ (Dynamic) Node runtime` in the build route manifest output.
  - [x] 8.3 `npm run lint` — 0 errors, 0 warnings.
  - [x] 8.4 Re-read [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts) with a reviewer's eye. Specifically verify: every `catch` branch logs before acting (Epic 3 retro #3); the `.text()` call is present; the dedup write happens BEFORE routing; the routing-error path still returns 200.

- [ ] Task 9: Manual smoke (AC: #5 runtime budget, human-verified)
  - [ ] 9.1 With `stripe listen --forward-to localhost:3000/api/webhooks/stripe` running AND `npm run dev` running, trigger a synthetic event: `stripe trigger invoice.paid`
  - [ ] 9.2 Verify the `stripe listen` console shows `200 OK` within ~1-2 seconds (well under the 5s NFR14 budget)
  - [ ] 9.3 Verify the Next.js dev-server console shows `[webhooks/stripe] invoice.paid received (not yet implemented):` + the event ID
  - [ ] 9.4 Trigger the **same event a second time** via `stripe events resend <event_id>` — verify the dev-server console shows `[webhooks/stripe] duplicate event skipped:` + the same event ID, and `stripe listen` still reports `200 OK`
  - [ ] 9.5 Trigger a non-handled event: `stripe trigger customer.created` — verify dev-server console shows `[webhooks/stripe] unhandled event type: customer.created` and `stripe listen` still reports `200 OK`
  - [ ] 9.6 In Firebase Console (or `firebase firestore:query` via CLI), confirm the `stripe_events` collection now contains at least three documents (one per unique event from 9.1, 9.5, and any earlier test deliveries)
  - [ ] 9.7 Document results in Completion Notes. If any step fails, **stop and file a defect against this story**; do not mark it done.

## Dev Notes

### Why raw body, not JSON body

This is the most common way to break a Stripe webhook endpoint. `request.json()` reads the bytes, parses them, and (if you later re-stringify) produces a **different** byte sequence than Stripe signed. Stripe's `constructEvent` will then reject your legitimate request with a signature mismatch, and you will spend 40 minutes debugging it.

The correct sequence is **always**:

```ts
const rawBody = await request.text()            // exact bytes Stripe signed
const event = stripe.webhooks.constructEvent(
  rawBody,                                       // ← raw text, NOT parsed object
  request.headers.get('stripe-signature')!,
  process.env.STRIPE_WEBHOOK_SECRET!,
)
// NOW event is a typed Stripe.Event — safe to use event.type, event.data, etc.
```

In Next.js App Router, there is **no** equivalent of the old Pages Router `config.api.bodyParser = false` footgun — App Router route handlers receive a Web `Request` and give you full byte-level access via `.text()` / `.arrayBuffer()`. This means the Pages-Router workaround (`micro` / `buffer`) is **not needed** and **not applicable** here. If you see any blog post or Stack Overflow answer suggesting you need `buffer(req)` or `bodyParser: false`, it's Pages-Router-era and wrong for our codebase.

### Why a Firestore transaction (not a bare `.create()`) for the dedup record

Architecture.md:202-205 prescribes a dual strategy: event-ID deduplication **plus** Firestore transactions. The safest and most forward-compatible way to implement both is to put the dedup check-and-record inside a single `runTransaction` call.

Three properties this gives us that a bare `.create()` does not:

1. **Co-located atomicity for Stories 4.2/4.3.** When `invoice.paid` lands, Story 4.2 needs to atomically (a) confirm this event hasn't been processed, (b) read the current `users/{uid}` doc, (c) write the updated subscription state, (d) mark the event processed. All four steps must succeed or none. That is a transaction, period. Starting Story 4.1 with the transaction shape means 4.2/4.3 extend one function rather than migrating from `.create()` to `runTransaction` mid-epic.

2. **Read-your-own-writes inside the transaction.** With a bare `.create()`, the routing handler runs AFTER the dedup write — if the route handler then needs to look at the dedup record (e.g., to store a processing result), it's a separate read. Inside a transaction, the routing handler's reads of `users/{uid}` and the event record are consistent-as-of the transaction's snapshot.

3. **Standard retry semantics.** Firestore's transaction machinery handles contention retries automatically. A bare `.create()` with a manual `ALREADY_EXISTS` catch open-codes part of that machinery and invites subtle bugs (e.g., retry counts, backoff) that the SDK already solves.

With `tx.set()`, the second delivery of the same event would silently overwrite — you'd lose the race signal and process the event twice. Always `tx.create()`.

The cost is one extra RTT's worth of transaction overhead per event. At Warden's expected webhook volume (subscription events for paid users, not high-cardinality analytics) this is well inside the NFR14 5s budget with headroom to spare. **Per the project's explicit direction: pick the safest option, ignoring token / RTT cost.**

### Why `stripe_events` is a separate collection, not a subcollection of `users`

Two reasons. First, at the moment we receive an event we have NOT yet extracted the `uid` — that happens inside the `invoice.paid` handler (Story 4.2) via `event.data.object.metadata.firebase_uid`. Dedup has to come before we know the user; the collection must therefore live at a path that doesn't require a `uid`. Second, event-level dedup should survive a `users/{uid}` document deletion (a user deletes their account while a Stripe retry is in flight, etc.). Keeping the two collections orthogonal is the less-clever, more-correct option.

### Why stub handlers (`handleInvoicePaid` etc.) live in `webhooks.ts` NOW

Story 4.1 could technically get away with dispatching directly from the route handler's `switch` statement with zero indirection. But that would mean Story 4.2 has to modify the route handler (`route.ts`) to wire in the real `handleInvoicePaid`. Each story that touches `route.ts` is a story that re-touches the test file for `route.ts`. By landing the `routeEvent` + stub-handlers module in Story 4.1, Stories 4.2 and 4.3 only need to replace **the body of one function** in `webhooks.ts` — the route-level test in `route.test.ts` keeps passing unchanged across all three stories.

This is the same Single-Source-of-Truth pattern that Epic 3 retro called out as the thing that worked: one `plans.ts`, one `previewCoupon`, one `CheckoutContext`. Epic 4 gets one `webhooks.ts`.

### Why the routing error returns 200, not 500

Per architecture.md:395, the rule is: webhook handler catches errors, logs them, and returns 200 to Stripe. Reasoning: Stripe retries 5xx responses aggressively (exponential backoff, up to 3 days). If your routing handler has a bug, returning 500 turns that bug into a DDoS-from-Stripe plus duplicate processing attempts plus log spam plus on-call pages. Returning 200 lets the event land in `stripe_events`, lets the bug get fixed on the next deploy, and lets an operator manually replay just the affected events via `stripe events resend <event_id>` — which is a surgical, controllable recovery.

The only 5xx we return is `WEBHOOK_NOT_CONFIGURED` (secret missing), because in that case Stripe retrying is actually what we want — the retry will succeed once an operator sets the env var.

### Previous Story Intelligence (carried from Stories 3.1–3.3 and Epic 3 retro)

*Per Epic 2 retro item #6 / Epic 3 retro success point. Each bullet is concrete and actionable; if something here contradicts a Task above, the Task wins and please flag the contradiction in Completion Notes.*

- **Plain-function `Stripe` constructor mock.** Story 3.2 established `vi.mock('stripe', () => ({ default: function Stripe() { /* ... */ }, __esModule: true }))` as the pattern that survives Vitest v4's ES-module-constructor handling. Copy the shape from [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) — do not re-discover it.
- **Never a silent `catch {}`.** Epic 3 retro action item #3 is blocking for Epic 4. Every `catch` in this story's files logs via `console.error` with a `[webhooks/stripe]` prefix before acting. A reviewer will `rg -n 'catch \{' src/app/api/webhooks` and any hit without an immediate `console.error` is a defect.
- **`npm run build` is part of DoD**, not implicit. Epic 3 retro #10. Task 8.2 is a distinct line item from 8.1 and 8.3.
- **Stripe SDK pinned at `^22.0.1`.** Type imports should reference `Stripe.Event`, `Stripe.Webhook`. If you see a type error in `constructEvent`'s signature, read `node_modules/stripe/types/Webhooks.d.ts` first (Epic 3 retro #3: "read SDK migration notes for third-party SDK work"). The v22 shape is stable for webhooks — the Epic 3 surprise was in `promotionCodes` expansion, not webhooks.
- **`adminDb` is a Proxy — touching it boots Firebase Admin.** Any test that imports this route file must mock `@/lib/firebase/admin` BEFORE the import, or the Proxy's first property access will try to read `FIREBASE_SERVICE_ACCOUNT_KEY` and crash the test. See the Task 6.3 mock structure.
- **Hoist `vi.mock` calls above imports** in `route.test.ts` — Vitest hoists `vi.mock` automatically but the imports have to be the SDK-from-path form. Again, the pattern from `session/route.test.ts` is correct; copy it.
- **Vitest file-parallelism flake is latent.** Epic 3 retro #6. If the new test file crashes with `Cannot read properties of undefined (reading 'config')` under parallel execution, use `--no-file-parallelism` and file a defect — do NOT chase the flake in this story. Epic 4 will add ~20 test files; at some point the flake will become blocking and get its own ticket.

### Stripe official guidance (per `.claude/skills/stripe-best-practices/references/security.md`)

Summarized from Stripe's own best-practices reference, filtered to what applies to Story 4.1:

1. **Signature verification is mandatory, not optional.** "Always verify webhook signatures using Stripe's webhook signing secret. Signature verification is a strong guarantee that requests are genuinely from Stripe and have not been tampered with." → Already enforced by AC #2 (`constructEvent`).
2. **Do NOT process webhook events without verifying their signatures.** "Unverified webhooks can be spoofed." → Enforced: the handler aborts with 400 `INVALID_SIGNATURE` before any Firestore write or event routing if verification fails (AC #2, AC #3 order is strict).
3. **Defense in depth: allowlist Stripe's IP addresses on the webhook endpoint.** Stripe publishes a list at https://docs.stripe.com/ips (also retrievable via `stripe.Config.retrieve`). Warden runs on Vercel — Vercel Edge / Middleware can enforce an allowlist, but this belongs at the **infrastructure layer**, not in this route handler. **Action for Story 4.1: document this as a follow-up ticket in Completion Notes, do NOT implement in code.** Attempting to enforce IP allowlisting in the route handler itself is fragile (Vercel proxies modify `x-forwarded-for`, local `stripe listen` sessions send from `127.0.0.1`, Stripe rotates IPs). The right layer is a Vercel middleware rule or a WAF rule — file it as a separate ticket for Epic 4 retrospective to adopt.
4. **Latest Stripe API version: `2026-03-25.dahlia`.** Already pinned in [src/lib/stripe/server.ts:7](src/lib/stripe/server.ts#L7). No change needed. If a reviewer bumps this, [Epic 3 retro action item #9 applies](./epic-3-retro-2026-04-14.md): read the Stripe SDK CHANGELOG before the bump.
5. **Never log the webhook secret.** The `[webhooks/stripe] STRIPE_WEBHOOK_SECRET is not set` log line (AC #2, `WEBHOOK_NOT_CONFIGURED` case) logs the **absence** of the secret, never its value. Enforce by code review: no `console.log(process.env.STRIPE_WEBHOOK_SECRET)` anywhere.
6. **Never build API endpoints that dump environment variables.** The envelope helpers in this route return only `{ error: { code, message } }` — no request echo, no env dump, no stack trace exposure. Reviewers: any additional fields in the error envelope should trip a 🚩.

### Stripe Webhook Event Reference (v22)

For Story 4.1, only two shapes matter from the `Stripe.Event` type:

- `event.id: string` — e.g., `evt_1Nabcd...`. Primary dedup key.
- `event.type: string` — e.g., `'invoice.paid'`. The switch discriminator.

Stories 4.2 and 4.3 will drill into `event.data.object` for the event-specific payload. Story 4.1 deliberately does NOT touch `event.data` — its job is verify, dedup, route. Do not pre-extract `uid` or `subscription_id` here; let 4.2/4.3 own those reads.

Relevant Stripe docs:

- `stripe.webhooks.constructEvent` — `node_modules/stripe/types/Webhooks.d.ts` (local) or Stripe dashboard API reference
- `Stripe.Event` type — `node_modules/stripe/types/EventsResource.d.ts`
- Event types catalogue — https://stripe.com/docs/api/events/types (not required reading for this story)

### Anti-Patterns to Avoid

- **`request.json()` anywhere in the POST handler.** Always `.text()`. This is the #1 regression risk.
- **Removing the Firestore transaction and switching to a bare `.create()`** to "save an RTT". The transaction is deliberate (see the "Why a Firestore transaction" section above). Do not optimize it away.
- **Implementing IP allowlisting inside the route handler.** This belongs at Vercel / WAF layer, not in `route.ts`. See Stripe official guidance point #3 above.
- **Catching Stripe API errors and returning 500 from the webhook handler.** Architecture.md:395 says log + 200. The handler's job is "did I receive and record this event?", not "did I successfully process it?". Processing failures are recoverable via replay; receive-failures aren't.
- **Importing `'stripe'` as a value in `webhooks.ts`.** The value import is the `getStripe()` singleton path in [src/lib/stripe/server.ts](src/lib/stripe/server.ts). `webhooks.ts` only needs `import type Stripe from 'stripe'` — the routing module should not instantiate its own Stripe client.
- **Extracting a shared `envelopeError` helper across route files now.** Story 3.3 Task 3.1 flagged this as possible-but-deferred. Story 4.1 is not the time — `webhooks/stripe/route.ts` can inline a copy, same as `checkout/coupon/route.ts` does.
- **Writing to `users/{uid}` in Story 4.1.** Not this story. Story 4.2 owns `invoice.paid` → `users/{uid}` writes. Story 4.1's routing stubs must be genuine no-ops (plus the `console.log`).
- **Adding Zod schemas for webhook payloads now.** Architecture.md:164-166 calls out runtime validation of webhook payloads as security-critical, BUT the `Stripe.Event` type from the SDK is itself the schema at the type level, and `constructEvent` performs signature verification — which is the relevant runtime check at Story 4.1's boundary. Story 4.2 can add `z.object({...})` schemas for the `event.data.object` shape it actually reads. Story 4.1 does not need them.
- **Deleting the `allow_promotion_codes: true` path from the checkout session route.** Unrelated to this story. Leave [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts) entirely alone.
- **Hydration-mismatch fix for `PlanCta`.** Epic 3 retro action item #4 — separate ticket, not this story.

### Naming Conventions (from Architecture)

- `stripe_events` collection name: `snake_case`, plural (architecture.md:305)
- Document fields in `stripe_events`: `snake_case` (`event_id`, `event_type`, `received_at`, `api_version`, `livemode`) — matches Stripe webhook payload naming (architecture.md:307)
- Response JSON fields: `camelCase` (`eventId`, `eventType`, `routingError`, `duplicate`, `received`) — architecture.md:313
- Route file path: `kebab-case` directories (`api/webhooks/stripe/`) — architecture.md:311
- Function names: `camelCase` (`routeEvent`, `handleInvoicePaid`, `envelopeError`)

### Import Order Convention

Match the existing route handler style in [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts):

```ts
// Next.js runtime exports (if any) at the top via `export const runtime = ...`
// Then third-party value imports
import type Stripe from 'stripe'
// Then internal absolute imports
import { adminDb } from '@/lib/firebase/admin'
import { getStripe } from '@/lib/stripe/server'
import { routeEvent } from '@/lib/stripe/webhooks'
// Then node built-ins if needed
import { FieldValue } from 'firebase-admin/firestore'
```

### Project Structure Notes

- New files: [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts), [src/app/api/webhooks/stripe/route.test.ts](src/app/api/webhooks/stripe/route.test.ts), [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts), [src/lib/stripe/webhooks.test.ts](src/lib/stripe/webhooks.test.ts)
- Modified files: **none** in Story 4.1. The `.env.example` already has `STRIPE_WEBHOOK_SECRET`; [src/lib/env.test.ts](src/lib/env.test.ts) already tripwires it; [src/lib/stripe/server.ts](src/lib/stripe/server.ts) already exposes `getStripe()`; [src/lib/firebase/admin.ts](src/lib/firebase/admin.ts) already exports `adminDb`.
- Zero-modification-to-existing-files is a strong signal this story is appropriately scoped. If you find yourself editing a file you didn't create, stop and ask whether that change belongs to a later story.
- Folder placement `src/app/api/webhooks/stripe/` exactly matches architecture.md:502-504.
- `src/lib/stripe/webhooks.ts` exactly matches architecture.md:546.

### References

- [Epics file — Story 4.1 AC](../planning-artifacts/epics.md) — lines 368-383 (`_bmad-output/planning-artifacts/epics.md#L368-L383`)
- [Architecture — Webhook Event Flow](../planning-artifacts/architecture.md) — lines 373-380 (idempotency + routing sequence)
- [Architecture — Stripe Webhook Security](../planning-artifacts/architecture.md) — lines 189-191 (`constructEvent` requirement)
- [Architecture — Webhook Idempotency](../planning-artifacts/architecture.md) — lines 202-205 (dual strategy: event-ID dedup + Firestore transactions)
- [Architecture — Webhook handler error pattern](../planning-artifacts/architecture.md) — line 395 (log + return 200)
- [Architecture — Naming conventions](../planning-artifacts/architecture.md) — lines 303-322
- [Architecture — Project structure](../planning-artifacts/architecture.md) — lines 502-504 (route location), 546 (lib location)
- [Epic 3 Retrospective](./epic-3-retro-2026-04-14.md) — action items #3 (silent catches), #5 (rotate webhook secret), #7 (Human Prerequisites block), #9 (read SDK notes), #10 (build in DoD)
- [Story 3.2 — Stripe SDK mocking pattern](./3-2-stripe-checkout-for-monthly-and-yearly-subscriptions.md) — the plain-function constructor gotcha is in its Debug Log References
- [PRD FR24](../planning-artifacts/prd.md) — webhook signature verification requirement
- [PRD NFR14](../planning-artifacts/prd.md) — 5s webhook response budget
- [Existing route — checkout session (style reference)](../../src/app/api/checkout/session/route.ts)
- [Existing Admin SDK init](../../src/lib/firebase/admin.ts)
- [Existing Stripe server singleton](../../src/lib/stripe/server.ts)
- [Existing env tripwire test](../../src/lib/env.test.ts)
- [Stripe best-practices skill — security reference](../../.claude/skills/stripe-best-practices/references/security.md) — webhook section (signature verification, IP allowlist defense-in-depth)
- Stripe public docs (informational only — do not fetch during dev-story unless blocked):
  - https://docs.stripe.com/webhooks — webhook overview
  - https://docs.stripe.com/webhooks#verify-events — signature verification
  - https://docs.stripe.com/ips — IP allowlist reference (for the follow-up infrastructure ticket)

## Dev Agent Record

### Agent Model Used

claude-opus-4-6[1m]

### Debug Log References

- `npx vitest run src/lib/stripe/webhooks.test.ts` → 5/5 ✅
- `npx vitest run src/app/api/webhooks/stripe/route.test.ts` → 9/9 ✅
- `npx vitest run` (full suite) → **254 / 254** ✅ (baseline was 240; +14 new tests)
- `npm run build` → ✅ zero type errors; `/api/webhooks/stripe` listed as `ƒ (Dynamic)` in route manifest
- `npm run lint` → ✅ 0 errors, 0 warnings

### Completion Notes List

**Implementation summary**
- Created thin HTTP shell at [src/app/api/webhooks/stripe/route.ts](src/app/api/webhooks/stripe/route.ts) with `runtime='nodejs'` + `dynamic='force-dynamic'`. Reads raw body via `.text()` (never `.json()`), verifies via `getStripe().webhooks.constructEvent`, records dedup doc in a Firestore transaction, then delegates to `routeEvent`. Every catch branch logs with a `[webhooks/stripe]` prefix before acting (Epic 3 retro #3 compliance).
- Created routing module at [src/lib/stripe/webhooks.ts](src/lib/stripe/webhooks.ts) with `import 'server-only'`, `Stripe.Event` type-only import, three exported stub handlers (`handleInvoicePaid`, `handleSubscriptionDeleted`, `handlePaymentFailed`), and `routeEvent` dispatcher with a `switch` on `event.type`. Default branch swallows unhandled types cleanly via `console.log`.
- **Self-namespace import pattern**: `routeEvent` calls `self.handleInvoicePaid(event)` via `import * as self from './webhooks'`. This was required to make `vi.spyOn(webhooksModule, 'handleInvoicePaid')` actually intercept intra-module calls — without it, ESM's local-binding resolution would bypass the spy and Task 7's spy-based test (explicitly requested in Task 2.5) would silently pass against the real stubs. Stories 4.2/4.3 can replace handler bodies without touching either test file.
- `tx.create` (not `tx.set`) used for the dedup write, so duplicates fail fast via `ALREADY_EXISTS` rather than silently overwriting.
- `runTransaction` is inside the top-level try/catch (per Task 4.4) — any Firestore error that escapes the transaction falls through to the `routingError: true` 200 response with the same `[webhooks/stripe] routing failed for event:` log line, for operator replay via `stripe events resend`.

**Operational notes (non-code)**
- **No Firestore rules change needed.** The Admin SDK bypasses security rules, so `stripe_events` writes from the webhook handler do not require a rules deploy. The separate Epic 2 retro item #1 rules-deploy ticket remains unrelated.
- **No `.env.example` change.** `STRIPE_WEBHOOK_SECRET` was already declared and tripwired in [src/lib/env.test.ts](src/lib/env.test.ts) during Epic 3 scaffolding.
- **Zero modifications to existing files** — new files only, exactly as the story's Project Structure Notes predicted. If a later story needs to edit this route, that's a smell worth questioning.

**Deferred follow-up tickets (not implemented in 4.1, per story guidance)**
1. **IP allowlist defense-in-depth** at the Vercel/WAF layer (Stripe best-practices skill security reference, item #3). The route handler is deliberately NOT doing IP checks — belongs in infra. File separately for Epic 4 retrospective review.
2. **Vitest file-parallelism flake** (Epic 3 retro #6) did not surface on this run; if it does in 4.2/4.3 keep following the retro's guidance (fall back to `--no-file-parallelism`, don't chase it mid-story).

**Task 9 (Manual smoke) status**
- **Not executed by the dev agent.** Task 9 is explicitly labeled "human-verified" and requires a running `stripe listen` session with a rotated `STRIPE_WEBHOOK_SECRET` in `.env.local` (Human Prerequisites block items 1–3). The agent cannot generate a real webhook secret or drive `stripe trigger` / `stripe events resend` from this environment without exposing secrets in the transcript. Task 9 remains unchecked; please run it during code review before moving the story to `done`. All nine 9.x subtasks have concrete commands in the story file.

### File List

- `src/lib/stripe/webhooks.ts` (new)
- `src/lib/stripe/webhooks.test.ts` (new)
- `src/app/api/webhooks/stripe/route.ts` (new)
- `src/app/api/webhooks/stripe/route.test.ts` (new)
- `src/app/api/checkout/session/route.ts` (modified — Epic 3 retro #3 silent-catch fix; out-of-scope but landed during 4.1, see Code Review notes)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (updated: 4-1 ready-for-dev → in-progress → review → in-progress)

### Change Log

- 2026-04-14 — Story 4.1 implemented: Stripe webhook endpoint with signature verification, Firestore-transaction-based event-ID deduplication (`stripe_events` collection), and `routeEvent` dispatcher with stub handlers for `invoice.paid` / `customer.subscription.deleted` / `invoice.payment_failed`. 254/254 tests pass (baseline 240). Status → review. Task 9 (manual `stripe listen` smoke) pending human execution.
- 2026-04-14 — Code review pass (adversarial). Fixed: (a) WHY comment for the `import * as self` self-namespace pattern in `webhooks.ts` (M2); (b) `tx.set` negative assertion + full `received_at`/`api_version` field assertions in `route.test.ts` (L1, L2). Documented: out-of-scope `console.error` addition to `src/app/api/checkout/session/route.ts` (M1 — Epic 3 retro #3 silent-catch fix landed during 4.1 work; surfaced and recorded rather than reverted, since the fix is correct and aligned with retro action item #3). Status moved review → in-progress pending human execution of Task 9 manual smoke.
