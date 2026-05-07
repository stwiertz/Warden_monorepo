# API Contracts — apps/web

All HTTP endpoints exposed by the Next.js app, derived from [src/app/api/\*\*/route.ts](../apps/web/src/app/api/). Every route handler exports `runtime = 'nodejs'`. Bodies are JSON. Auth is via the httpOnly `session` cookie (Firebase Admin sessionCookie) unless noted.

## Response envelope conventions

Every JSON response follows one of two shapes:

```json
{ "data": <object | null> }
{ "error": { "code": "<UPPER_SNAKE>", "message": "<human readable>" } }
```

`error.code` values used:

| Code                                                                                      | Where                                                         |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ---------------------- |
| `INVALID_REQUEST`                                                                         | Body missing/malformed at validation time                     |
| `INVALID_TOKEN`                                                                           | Firebase verifyIdToken failure                                |
| `INVALID_SIGNATURE`                                                                       | Stripe webhook signature failure                              |
| `UNAUTHENTICATED` / `NO_SESSION` / `SESSION_EXPIRED` / `SESSION_REVOKED` / `UNAUTHORIZED` | Session cookie missing/expired/revoked/invalid                |
| `MISSING_STRIPE_PRICE_ID`                                                                 | `STRIPE*PRICE*{MONTHLY                                        | YEARLY}` env var unset |
| `COUPON_INVALID`                                                                          | Stripe coupon doesn't exist / inactive / expired              |
| `COUPON_LOOKUP_FAILED`                                                                    | Stripe lookup threw                                           |
| `CHECKOUT_FAILED`                                                                         | `stripe.checkout.sessions.create` errored, or returned no URL |
| `WEBHOOK_NOT_CONFIGURED`                                                                  | `STRIPE_WEBHOOK_SECRET` env var unset                         |
| `NO_CUSTOMER`                                                                             | `users/{uid}` missing or has no `stripe_customer_id`          |
| `PORTAL_SESSION_FAILED`                                                                   | Stripe billing portal create errored                          |
| `SUBSCRIPTION_FETCH_FAILED`                                                               | Firestore read errored after successful auth                  |

## Endpoints

### `POST /api/auth/session` — create session cookie

Takes a Firebase ID token, verifies it, mints an httpOnly session cookie.

|            |                                                                                                                             |
| ---------- | --------------------------------------------------------------------------------------------------------------------------- |
| Auth       | None (this is the auth handshake)                                                                                           |
| Body       | `{ "idToken": string }` (`min(1)`)                                                                                          |
| Cookie set | `session` — httpOnly, sameSite=lax, secure (prod only), path=/, maxAge=7 days                                               |
| Success    | `200` `{ "data": { "status": "success" } }`                                                                                 |
| Errors     | `400 INVALID_REQUEST` (body fails Zod), `401 INVALID_TOKEN` (verifyIdToken throws — also covers createSessionCookie throws) |

Source: [route.ts](../apps/web/src/app/api/auth/session/route.ts).

### `DELETE /api/auth/session` — destroy session cookie

|         |                                                |
| ------- | ---------------------------------------------- |
| Auth    | None — caller's cookie is what's being deleted |
| Body    | (none)                                         |
| Cookie  | `session` deleted                              |
| Success | `200` `{ "data": { "status": "success" } }`    |
| Errors  | n/a — always succeeds                          |

Client also calls `firebase signOut` separately, see [destroySessionAndRedirect](../apps/web/src/lib/firebase/session.ts).

### `POST /api/checkout/coupon` — preview a coupon code

Read-only Stripe coupon lookup. Used by the pricing page to show inline discount feedback.

|         |                                                                                                                       |
| ------- | --------------------------------------------------------------------------------------------------------------------- |
| Auth    | None (advertised before sign-in)                                                                                      |
| Body    | `{ "code": string }` (`trim`, `min(1)`, `max(64)`)                                                                    |
| Success | `200` `{ "data": { "code": string, "percentOff"?: number, "amountOffCents"?: number, "durationInMonths"?: number } }` |
| Errors  | `400 INVALID_REQUEST`, `400 COUPON_INVALID`, `500 COUPON_LOOKUP_FAILED`                                               |

Internally calls `previewCoupon(code)` from [lib/stripe/coupons.ts](../apps/web/src/lib/stripe/coupons.ts).

### `POST /api/checkout/session` — start a Stripe Checkout

|         |                                                                                                                          |
| ------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------- |
| Auth    | **Required** — session cookie (parsed inline; `verifySessionCookie(cookie, true)`)                                       |
| Body    | `{ "planId": "monthly"                                                                                                   | "yearly", "couponCode"?: string }` |
| Success | `200` `{ "data": { "url": string } }` (Stripe-hosted checkout URL)                                                       |
| Errors  | `400 INVALID_REQUEST`, `401 UNAUTHENTICATED`, `400 COUPON_INVALID`, `500 MISSING_STRIPE_PRICE_ID`, `500 CHECKOUT_FAILED` |

Stripe session args:

```ts
{
  mode: 'subscription',
  line_items: [{ price: STRIPE_PRICE_<plan>, quantity: 1 }],
  success_url: `${appUrl}/dashboard?checkout=success&session_id={CHECKOUT_SESSION_ID}`,
  cancel_url:  `${appUrl}/pricing?checkout=canceled`,
  client_reference_id: <firebase uid>,
  customer_email: <decoded.email | omit>,
  metadata:           { firebase_uid, plan_id },
  subscription_data: { metadata: { firebase_uid, plan_id } },
  // mutually exclusive:
  discounts: [{ promotion_code }] // when couponCode provided + previewCoupon returned a promo id
  allow_promotion_codes: true     // otherwise
}
```

The metadata pair on **both** the session and the subscription is load-bearing — the webhook reads `subscription.metadata.firebase_uid` + `plan_id` to know which Firestore doc to update.

`appUrl` resolves from `NEXT_PUBLIC_APP_URL` (trailing slash trimmed) or the request origin.

Source: [route.ts](../apps/web/src/app/api/checkout/session/route.ts).

### `GET /api/subscription` — read subscription state

|         |                                                                                               |
| ------- | --------------------------------------------------------------------------------------------- | ------- |
| Auth    | **Required** (`withAuth` wrapper)                                                             |
| Body    | (none)                                                                                        |
| Success | `200` `{ "data": SubscriptionResponse                                                         | null }` |
| Errors  | `401 NO_SESSION/UNAUTHORIZED/...` (from `UnauthorizedError`), `500 SUBSCRIPTION_FETCH_FAILED` |

`SubscriptionResponse` shape (validated server-side and client-side with the same Zod schema in [lib/schemas/subscription.ts](../apps/web/src/lib/schemas/subscription.ts)):

```ts
{
  status: 'active' | 'past_due' | 'canceled',
  plan:   'monthly' | 'yearly',
  current_period_end: number,        // Unix seconds
  stripe_customer_id: string,
  stripe_subscription_id: string
}
```

When the Firestore document doesn't exist, the handler returns `200 { data: null }` (NOT 404). When the doc exists but fails Zod, the handler **logs the error and returns `200 { data: null }`** — clients treat that as "no subscription". This swallows distinguishable corruption errors; document explicitly.

Source: [route.ts](../apps/web/src/app/api/subscription/route.ts).

### `POST /api/subscription/portal` — open Stripe Customer Portal

|         |                                                                                                          |
| ------- | -------------------------------------------------------------------------------------------------------- |
| Auth    | **Required**                                                                                             |
| Body    | (none)                                                                                                   |
| Success | `200` `{ "data": { "url": string } }` (Stripe billingPortal URL)                                         |
| Errors  | `401`, `404 NO_CUSTOMER` (user doc missing OR `stripe_customer_id` missing), `500 PORTAL_SESSION_FAILED` |

`return_url` is `${appUrl}/dashboard`.

Source: [route.ts](../apps/web/src/app/api/subscription/portal/route.ts).

### `POST /api/webhooks/stripe` — Stripe webhook ingress

The most carefully-engineered handler in the app.

|                          |                                                                                                                                                                               |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Auth                     | Stripe signature (`stripe-signature` header → `STRIPE_WEBHOOK_SECRET`)                                                                                                        |
| Body                     | Raw text (NOT JSON-parsed by the framework; we read `request.text()` ourselves so the signature check operates on bytes)                                                      |
| Idempotency              | Firestore `stripe_events/{event.id}` doc — created in the same transaction that checks for existence                                                                          |
| Routing                  | `routeEvent(event)` in [lib/stripe/webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts)                                                                                       |
| Retry policy             | `retryStripeCall` retries `subscriptions.retrieve` on `StripeConnectionError` / `StripeRateLimitError` / 5xx at delays `[250, 750, 2250]`ms                                   |
| Routing failure response | `200 { data: { received:true, duplicate:false, routingError:true, eventId } }` — to **stop Stripe retries**, since the event is already in `stripe_events/` for manual replay |
| Success                  | `200 { data: { received: true, duplicate: false, eventId, eventType } }` (or `duplicate: true` for repeats)                                                                   |
| Errors                   | `400 INVALID_SIGNATURE` (missing header or constructEvent throws), `500 WEBHOOK_NOT_CONFIGURED` (env var unset)                                                               |
| Other config             | `export const dynamic = 'force-dynamic'` (no static rendering / caching)                                                                                                      |

Handled event types and their effects on Firestore:

| Event                           | Effect on `users/{firebase_uid}`                                                                                                                                                                                                                                                                                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `invoice.paid`                  | Set `{status:'active', plan, current_period_end:Timestamp.fromMillis(periodEndSeconds*1000), stripe_subscription_id, stripe_customer_id, updated_at: serverTimestamp()}`. If doc doesn't exist, creates it with `created_at`. **Plan id validated against `PLAN_IDS = ['monthly','yearly']`**; unknown plan throws. **`firebase_uid` metadata required**; missing throws. |
| `customer.subscription.deleted` | Set `{status: 'canceled', updated_at: serverTimestamp()}`. **No-op if already canceled.** **Errors out** if user doc doesn't exist (this represents an orphan subscription event — the team wants it visible).                                                                                                                                                            |
| `invoice.payment_failed`        | Set `{status: 'past_due', updated_at: serverTimestamp()}`. No-op if already `past_due` or `canceled`.                                                                                                                                                                                                                                                                     |
| anything else                   | Logs `unhandled event type` and returns 200.                                                                                                                                                                                                                                                                                                                              |

Validation: `invoicePaidSchema`, `subscriptionDeletedSchema`, `paymentFailedSchema` from [lib/schemas/webhook-events.ts](../apps/web/src/lib/schemas/webhook-events.ts). They reflect dahlia (`2026-03-25.dahlia`) nesting `parent.subscription_details.subscription` — **don't regress to the older top-level `invoice.subscription` field**.

The handler uses `import * as self from './webhooks'` and calls `self.handleX` so `vi.spyOn(webhooksModule, 'handleX')` actually intercepts the intra-module call — direct `handleX(event)` would bypass the spy due to ESM local-binding. Stories 4.2/4.3 rely on this.

Source: [route.ts](../apps/web/src/app/api/webhooks/stripe/route.ts), [webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts).

## Cookies

| Cookie    | Set by                   | Read by                                                                                    | Properties                                                                                               |
| --------- | ------------------------ | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `session` | `POST /api/auth/session` | `requireSession` / `withAuth` server-side; `POST /api/checkout/session` parses it manually | `httpOnly; sameSite=lax; path=/; maxAge=604800; secure` (prod only). 7-day Firebase Admin sessionCookie. |

There is **no CSRF token** — the API relies on `sameSite=lax` + the fact that POSTs require a JSON content-type (which preflights for cross-origin requests). If the dashboard ever needs to be embedded in third-party origins, revisit.

## Environment variables

| Var                                            | Purpose                                                          | Where used                                                                   |
| ---------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `FIREBASE_SERVICE_ACCOUNT_KEY`                 | JSON-encoded service account credentials                         | [admin.ts](../apps/web/src/lib/firebase/admin.ts)                            |
| `NEXT_PUBLIC_FIREBASE_*`                       | Browser firebase client config                                   | [client.ts](../apps/web/src/lib/firebase/client.ts)                          |
| `STRIPE_SECRET_KEY`                            | Server Stripe SDK                                                | [server.ts](../apps/web/src/lib/stripe/server.ts)                            |
| `STRIPE_WEBHOOK_SECRET`                        | Webhook signature verification                                   | [webhooks/stripe/route.ts](../apps/web/src/app/api/webhooks/stripe/route.ts) |
| `STRIPE_PRICE_MONTHLY` / `STRIPE_PRICE_YEARLY` | Stripe price IDs per plan                                        | [server.ts](../apps/web/src/lib/stripe/server.ts) (`getPlanPriceId(plan)`)   |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`           | (Currently unused in code path, declared in env example)         | n/a                                                                          |
| `NEXT_PUBLIC_APP_URL`                          | Used to build Stripe `success_url` / `cancel_url` / `return_url` | checkout/portal routes                                                       |
| `NODE_ENV`                                     | Cookie `secure` flag                                             | session route                                                                |

See [.env.example](../apps/web/.env.example) for the canonical list.
