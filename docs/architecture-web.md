# Architecture — apps/web

> Part `web` (Next.js 16). Imported from the legacy `WardenWeb` repo at Phase 2 with full git history (66 commits). Five legacy epics shipped; current state is post-migration with brownfield TypeScript debt.

> ⚠ **Heads up**: [apps/web/AGENTS.md](../apps/web/AGENTS.md) explicitly says "This is NOT the Next.js you know" — Next.js 16 has breaking changes from older training data. When in doubt, read `node_modules/next/dist/docs/`.

## Executive summary

Marketing landing + subscription portal. Three jobs:

1. **Sell the subscription** — pricing page, Stripe Checkout, optional coupon flow.
2. **Reflect Stripe state into Firestore** — webhook handler ingests `invoice.paid`, `customer.subscription.deleted`, `invoice.payment_failed` and projects them onto `users/{uid}` (the document mobile reads to gate paid features).
3. **Self-service** — dashboard surfaces subscription status, hands off to Stripe Customer Portal.

There is no app-specific user data beyond `users/{uid}` and `stripe_events/{event_id}` (idempotency log). All session-protected reads/writes are server-side via firebase-admin; client writes are denied at the rules layer.

## Architecture pattern

**Next.js App Router with server-only route handlers**. Browser components are minimal (auth forms, plan picker, dashboard cards); business logic lives in [`src/app/api/*/route.ts`](../apps/web/src/app/api/) and [`src/lib/`](../apps/web/src/lib/). Every route handler exports `runtime = 'nodejs'` (firebase-admin and Stripe SDK both need Node).

```
src/
├── app/                       App Router (URL ≡ folder)
│   ├── layout.tsx                 Root — fonts, AuthProvider, body wrapper
│   ├── page.tsx                   Marketing landing
│   ├── auth/sign-in/page.tsx      Sign-in form (email + Google)
│   ├── pricing/page.tsx           Plan picker + checkout entry
│   ├── dashboard/                 Authed surface
│   │   ├── layout.tsx             Sub-layout — gates on requireSession()
│   │   └── page.tsx               SubscriptionCard + portal CTA
│   └── api/
│       ├── auth/session/route.ts        POST/DELETE — session cookie lifecycle
│       ├── checkout/coupon/route.ts     POST — preview coupon
│       ├── checkout/session/route.ts    POST — create Stripe Checkout
│       ├── subscription/route.ts        GET  — read users/{uid}
│       ├── subscription/portal/route.ts POST — Stripe billing portal
│       └── webhooks/stripe/route.ts     POST — Stripe webhook ingress
├── components/
│   ├── auth/                  Sign-in/up forms, Google button, sign-out
│   ├── checkout/              Plan card, CTA, coupon input, CheckoutContext
│   ├── dashboard/             SubscriptionCard
│   ├── layout/                Header, HeaderAuthActions, Footer, CookieBanner
│   └── ui/                    shadcn/ui primitives (button, card, input, alert, dialog, badge, skeleton)
├── contexts/AuthContext.tsx   Firebase onAuthStateChanged → React context
├── hooks/                     useAuth (consumes AuthContext), useSubscription (fetches /api/subscription)
├── lib/
│   ├── env.ts
│   ├── utils.ts                cn() = clsx + tailwind-merge
│   ├── firebase/{admin,client,auth,session,analytics,errors}.ts
│   ├── stripe/{server,webhooks,coupons}.ts
│   ├── pricing/{plans,discount}.ts
│   └── schemas/{auth,subscription,webhook-events}.ts  Zod 4 validators
└── fonts/                     Local font files (Inter)
```

## Technology stack

| Category  | Tech                                        | Version               | Notes                                                                                                                                                      |
| --------- | ------------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Framework | next                                        | 16.2.2                | App Router; **server actions / forms behaviour may differ from older Next** — see `apps/web/AGENTS.md`                                                     |
| React     | react / react-dom                           | 19.2.4                | Server Components by default                                                                                                                               |
| Styling   | Tailwind CSS                                | ^4                    | Via `@tailwindcss/postcss`                                                                                                                                 |
| UI        | shadcn/ui (Base UI primitives)              | ^4.1.2                | Generated into `src/components/ui/`                                                                                                                        |
|           | @base-ui/react                              | ^1.3.0                |                                                                                                                                                            |
|           | lucide-react                                | ^1.7.0                | Icons                                                                                                                                                      |
| Forms     | react-hook-form + @hookform/resolvers + zod | ^7.72 / ^5.2 / ^4.3.6 | Zod 4 (`zod/v4`) — note the import path                                                                                                                    |
| Auth      | firebase                                    | ^12.11.0              | client SDK                                                                                                                                                 |
|           | firebase-admin                              | ^13.7.0               | server only — service account creds via env                                                                                                                |
| Payments  | stripe                                      | ^22.0.1               | API version pinned `'2026-03-25.dahlia'` ([server.ts](../apps/web/src/lib/stripe/server.ts)). **Type drift** with installed types (`'2026-04-22.dahlia'`). |
| Test      | vitest                                      | ^4.1.3                | + jsdom + @testing-library/react                                                                                                                           |
| TS        | typescript                                  | ^5                    | extends `@warden/tsconfig/next.json`                                                                                                                       |

## Boot sequence (server)

Next.js boots normally; firebase-admin is **lazy-initialised** behind a `Proxy` in [admin.ts](../apps/web/src/lib/firebase/admin.ts) so that route handlers that don't need it (e.g. `/api/checkout/coupon`) don't pay the init cost. The Stripe client is similarly lazy in [server.ts](../apps/web/src/lib/stripe/server.ts).

[`adminAuth`](../apps/web/src/lib/firebase/admin.ts) and [`adminDb`](../apps/web/src/lib/firebase/admin.ts) are exported as `Proxy` objects — first property access initialises the App with the service account from `FIREBASE_SERVICE_ACCOUNT_KEY` (a JSON string in env). Re-uses an existing app when `getApps().length > 0`.

## Auth model

The model is **Firebase Auth client-side, session-cookie server-side**.

- The browser signs in via firebase client SDK ([client.ts](../apps/web/src/lib/firebase/client.ts) + [contexts/AuthContext.tsx](../apps/web/src/contexts/AuthContext.tsx)).
- After sign-in, the client immediately calls `POST /api/auth/session` with `{ idToken }`. The handler verifies the ID token via firebase-admin and creates a `sessionCookie` (7 days). Sets `session` cookie: `httpOnly; sameSite=lax; secure (prod); path=/`.
- Server-side authed reads/writes use [`requireSession`](../apps/web/src/lib/firebase/session.ts) → `adminAuth.verifySessionCookie(cookie, true)`. Throws typed `UnauthorizedError` with codes `NO_SESSION | SESSION_EXPIRED | SESSION_REVOKED | UNAUTHORIZED`.
- `withAuth(handler)` wraps a route handler so unauthorised callers get a `Response.json({error:{code,message:'Authentication required'}}, {status:401})` automatically.
- Sign-out: `POST /api/auth/session DELETE` → `cookies().delete('session')`. Client calls `firebase signOut` and `DELETE /api/auth/session` in [destroySessionAndRedirect](../apps/web/src/lib/firebase/session.ts).

See [api-contracts-web.md](./api-contracts-web.md) for full HTTP semantics.

## Stripe integration

### Pricing model

Two plans, hard-coded in [plans.ts](../apps/web/src/lib/pricing/plans.ts):

| Plan      | priceCents | Currency | Period | Stripe price env key   |
| --------- | ---------: | -------- | ------ | ---------------------- |
| `monthly` |        799 | EUR      | month  | `STRIPE_PRICE_MONTHLY` |
| `yearly`  |       7990 | EUR      | year   | `STRIPE_PRICE_YEARLY`  |

Yearly savings derived: `getYearlySavings(monthly, yearly) → { amountCents, percent }`.

EUR formatting uses `Intl.NumberFormat('en-IE', { style:'currency', currency:'EUR' })`.

### Checkout flow

`POST /api/checkout/session` → [route.ts](../apps/web/src/app/api/checkout/session/route.ts):

1. Read body — `{ planId: 'monthly'|'yearly', couponCode?: string }` (Zod-validated).
2. Read session cookie (manual parse to avoid Next's `cookies()` overhead inside the handler — yes the handler does its own cookie parsing).
3. Verify session cookie → `decoded = { uid, email? }`.
4. Look up `priceId` from `plan.stripePriceEnvKey`.
5. If `couponCode` provided → `previewCoupon(code)` — returns `{ promotionCodeId, coupon: {...} }` or `null`. Errors map to `COUPON_INVALID` / `COUPON_LOOKUP_FAILED`.
6. `stripe.checkout.sessions.create({mode:'subscription', line_items:[{price, quantity:1}], success_url:`/dashboard?checkout=success&session_id={CHECKOUT_SESSION_ID}`, cancel_url:`/pricing?checkout=canceled`, client_reference_id: uid, customer_email: email?, metadata: {firebase_uid, plan_id}, subscription_data: {metadata: {firebase_uid, plan_id}}, [discounts | allow_promotion_codes]})`.
7. Return `{ data: { url } }`.

The metadata pair `firebase_uid` + `plan_id` is **load-bearing** — the webhook reads them to know which Firestore doc to update.

### Webhook flow

`POST /api/webhooks/stripe` → [route.ts](../apps/web/src/app/api/webhooks/stripe/route.ts):

1. Verify `stripe-signature` header against `STRIPE_WEBHOOK_SECRET` via `stripe.webhooks.constructEvent`. Returns 400 with `INVALID_SIGNATURE` on failure.
2. **Idempotency:** in a Firestore transaction, look up `stripe_events/{event.id}` — if it exists, return 200 with `{duplicate: true}`. Otherwise create the doc with `{event_id, event_type, received_at, api_version, livemode}`.
3. `routeEvent(event)` (in [webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts)):
   - `invoice.paid` → `handleInvoicePaid` → `users/{firebase_uid}` set/merge `{status:'active', plan, current_period_end:Timestamp.fromMillis(periodEndSeconds*1000), stripe_subscription_id, stripe_customer_id, updated_at}` (creates with `created_at` if not exists).
   - `customer.subscription.deleted` → `handleSubscriptionDeleted` → `users/{firebase_uid}.status = 'canceled'`. No-op if already canceled. **Requires the user doc to exist** — errors out with a logged failure if not.
   - `invoice.payment_failed` → `handlePaymentFailed` → `users/{firebase_uid}.status = 'past_due'`. No-op if already past_due or canceled.
   - Unknown types → log + 200.
4. Routing failures → return **200** with `{routingError: true}` to **stop Stripe retries**; the event is in `stripe_events/` for manual replay.

The handlers go through `routeEvent` → `self.handleX` (self-namespace import) so `vi.spyOn(webhooksModule, 'handleX')` intercepts; **don't refactor to direct calls without rewriting the spy-based tests** — there's a comment in the source pointing at this.

The dahlia API (`2026-03-25.dahlia`) removed `invoice.subscription`; the schemas in [webhook-events.ts](../apps/web/src/lib/schemas/webhook-events.ts) reflect the new nesting `parent.subscription_details.subscription`. Don't regress this.

`retryStripeCall(fn, label)` in [server.ts](../apps/web/src/lib/stripe/server.ts) retries `subscriptions.retrieve` on transient errors (`StripeConnectionError`, `StripeRateLimitError`, 5xx) at delays `[250, 750, 2250]`ms.

### Coupons

[coupons.ts](../apps/web/src/lib/stripe/coupons.ts) (read but inferred from usage in [route.ts](../apps/web/src/app/api/checkout/coupon/route.ts) and [route.ts](../apps/web/src/app/api/checkout/session/route.ts)):

`previewCoupon(code: string) → Promise<{ promotionCodeId: string, coupon: {percentOff, amountOffCents, durationInMonths} } | null>`

Returns `null` for unknown / inactive / expired coupons. Throws on lookup failure (mapped to 500 by callers).

## Schemas

[lib/schemas/](../apps/web/src/lib/schemas/) is the Zod 4 layer. Note: imports use `'zod/v4'` — the project sits on the v4 candidate path, not `'zod'`.

- [auth.ts](../apps/web/src/lib/schemas/auth.ts) — sign-in/sign-up form validation.
- [subscription.ts](../apps/web/src/lib/schemas/subscription.ts) — `subscriptionResponseSchema` for `GET /api/subscription` payload (`{ status, plan, current_period_end (number), stripe_customer_id, stripe_subscription_id }`). **This is web-local; it doesn't yet import from `@warden/contracts/user-doc`** — Phase 6 candidate to unify.
- [webhook-events.ts](../apps/web/src/lib/schemas/webhook-events.ts) — `invoicePaidSchema`, `subscriptionDeletedSchema`, `paymentFailedSchema`. Reflects dahlia nesting.

## Dashboard data flow

[useSubscription.ts](../apps/web/src/hooks/useSubscription.ts) is the only client-side data hook of note. Fetches `/api/subscription` once on mount, parses with `subscriptionResponseSchema.safeParse`, returns `{subscription, loading, error}`. Cancellation flag on the closure to avoid setting state after unmount.

[GET /api/subscription](../apps/web/src/app/api/subscription/route.ts) reads `users/{uid}` server-side, projects `{status, plan, current_period_end: data.current_period_end.seconds ?? null, stripe_customer_id, stripe_subscription_id}`, validates with the same Zod schema. Returns `{data: null}` (NOT 404) when the doc doesn't exist or schema-fails — keeps the dashboard flow simple at the cost of swallowing distinguishable errors.

## Firestore security

[firestore.rules](../apps/web/firestore.rules) is minimal:

```
match /users/{userId} {
  allow read:  if request.auth != null && request.auth.uid == userId;
  allow write: if false;
}
match /{document=**} { allow read, write: if false; }
```

`users/{uid}`: owner-read only; client writes denied. Server-side writes go through `firebase-admin` which **bypasses rules**. `stripe_events/{id}` is server-only — no client access at all.

`detection_config/latest` does **not** appear in these rules — meaning under the wildcard `{document=**}` deny, mobile cannot currently read it through `firestore.rules`. Either rules are out of date, or mobile reads against a different rule set. Phase 6 must reconcile.

## Tests

Vitest + jsdom. Tests sit next to their subjects (`*.test.ts(x)`). Coverage from spot-reading the file list:

- All API routes have a `route.test.ts`.
- All Firebase lib helpers have `*.test.ts`.
- All Stripe handlers have tests (`coupons.test.ts`, `invoice-paid.test.ts`, `payment-failed.test.ts`, `subscription-deleted.test.ts`, `webhooks.test.ts`).
- All UI components have `*.test.tsx`.
- App pages have `page.test.tsx`.

Setup file: [vitest.setup.ts](../apps/web/vitest.setup.ts). Alias `@/*` → `./src/*` configured in [vitest.config.ts](../apps/web/vitest.config.ts).

## Conventions

- **Filenames** — PascalCase for components (`SubscriptionCard.tsx`), kebab-case for utility modules (`stripe/server.ts`, `pricing/plans.ts`).
- **Imports** — `@/*` alias maps to `./src/*`.
- **Quotes** — single-quoted (legacy WardenWeb prettier preset).
- **Server-only modules** — start with `import 'server-only'` so accidental client imports fail the build.
- **Conventional Commits** — root husky + commitlint enforce.

## Known issues / debt

| Issue                                                                  | File                                                           | Action                                                                                                |
| ---------------------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Stripe API version drift (pinned vs installed types)                   | [stripe/server.ts](../apps/web/src/lib/stripe/server.ts)       | Bump pin to `2026-04-22.dahlia` and re-run schemas + tests, **or** freeze types to the older version. |
| Test files have spread-arg / implicit-any errors (per memory)          | various `*.test.ts`                                            | Tighten types or revert TS strictness in tests only.                                                  |
| `firestore.rules` doesn't cover `detection_config` and `stripe_events` | [firestore.rules](../apps/web/firestore.rules)                 | Phase 6: write explicit rules.                                                                        |
| `subscription.ts` schema diverges from `@warden/contracts/user-doc`    | [subscription.ts](../apps/web/src/lib/schemas/subscription.ts) | Phase 6: import from contracts.                                                                       |
| `next.config.ts` is empty                                              | [next.config.ts](../apps/web/next.config.ts)                   | Phase 6: add image domains, headers, etc. as needed.                                                  |
