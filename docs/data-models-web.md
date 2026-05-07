# Data Models — apps/web

Web has no SQL store. Persistence is entirely **Firestore** (server-only writes via `firebase-admin`) plus the **Firebase Admin sessionCookie** (an opaque JWT minted by the SDK).

## Firestore collections

### `users/{uid}` — subscription state of record

The integration boundary with mobile. **Web writes via Stripe webhook handlers; mobile reads** to gate paid features. Schema in [contracts/user-doc.schema.json](../contracts/user-doc.schema.json) (lax — `additionalProperties: true` to tolerate legacy `isPaid`).

Fields written by web:

| Field                    | Type                  | Set by                                                                                                                | Notes                                                                                                                        |
| ------------------------ | --------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `status`                 | string                | `handleInvoicePaid` (→`'active'`), `handleSubscriptionDeleted` (→`'canceled'`), `handlePaymentFailed` (→`'past_due'`) | One of `active` / `past_due` / `canceled` (plus `trialing` written by Stripe externally — handled by mobile's status check). |
| `plan`                   | string                | `handleInvoicePaid` only                                                                                              | One of `monthly` / `yearly`. Validated against `PLAN_IDS`.                                                                   |
| `current_period_end`     | Firestore `Timestamp` | `handleInvoicePaid`                                                                                                   | `Timestamp.fromMillis(periodEndSeconds * 1000)` from `invoice.lines.data[0].period.end`.                                     |
| `stripe_customer_id`     | string                | `handleInvoicePaid`                                                                                                   | From `subscription.customer` (string-coerced).                                                                               |
| `stripe_subscription_id` | string                | `handleInvoicePaid`                                                                                                   | From `subscription.id`.                                                                                                      |
| `created_at`             | server `Timestamp`    | `handleInvoicePaid` (only when creating a new doc)                                                                    | `FieldValue.serverTimestamp()`.                                                                                              |
| `updated_at`             | server `Timestamp`    | every write                                                                                                           | `FieldValue.serverTimestamp()`.                                                                                              |
| `isPaid` (legacy)        | boolean               | NOT written by web today                                                                                              | Defined in the contract for legacy-mobile read path. Phase 6 to decide whether to materialize.                               |

Read by [GET /api/subscription](./api-contracts-web.md#get-apisubscription--read-subscription-state). Projected payload before the Zod check:

```ts
{
  status:                 data?.status,
  plan:                   data?.plan,
  current_period_end:     data?.current_period_end?.seconds ?? null,  // Timestamp → seconds
  stripe_customer_id:     data?.stripe_customer_id,
  stripe_subscription_id: data?.stripe_subscription_id
}
```

Validated with [`subscriptionResponseSchema`](../apps/web/src/lib/schemas/subscription.ts) — note this is currently a web-local Zod schema **not yet importing from `@warden/contracts/user-doc`** (Phase 6 unification candidate).

[firestore.rules](../apps/web/firestore.rules):

```
match /users/{userId} {
  allow read:  if request.auth != null && request.auth.uid == userId;
  allow write: if false;
}
```

Reads are limited to the owner; client writes are denied at the rules layer. firebase-admin bypasses rules for server-side writes.

### `stripe_events/{event_id}` — webhook idempotency log

Created in the same transaction as the dedupe check inside [POST /api/webhooks/stripe](./api-contracts-web.md#post-apiwebhooksstripe--stripe-webhook-ingress).

| Field         | Type               | Notes                                           |
| ------------- | ------------------ | ----------------------------------------------- |
| `event_id`    | string             | Mirror of doc id — kept as a field for queries. |
| `event_type`  | string             | e.g. `invoice.paid`.                            |
| `received_at` | server `Timestamp` | `FieldValue.serverTimestamp()`.                 |
| `api_version` | string \| null     | From the Stripe event (`event.api_version`).    |
| `livemode`    | boolean            | From the Stripe event.                          |

No client access — not in the Firestore rules at all (denied by the wildcard catch-all). Only the webhook route handler touches it via `firebase-admin`.

### `detection_config/latest` (read by mobile, NOT written by web)

Mentioned here for completeness — the document lives in the same Firebase project but web never touches it. Currently maintained out-of-band (operator script or manual edit). Schema is the mobile-side `DetectionConfig`.

Phase 6 may move ownership to web (a `/api/admin/detection-config` route) or wire it to `apps/tooling`'s `map_config.json` emit. Document explicitly.

## Auth artifacts

### `session` cookie

Not Firestore — but the only durable auth artifact aside from the Firebase user record itself.

| Property     | Value                                                                                                                                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Format       | Firebase Admin sessionCookie (opaque JWT)                                                                                                                                                              |
| Lifetime     | 7 days (`SESSION_EXPIRY_MS`)                                                                                                                                                                           |
| Cookie attrs | `httpOnly`, `sameSite=lax`, `secure` (prod only), `path=/`, `maxAge=604800`                                                                                                                            |
| Source       | `adminAuth.createSessionCookie(idToken, { expiresIn })` after `verifyIdToken(idToken)`                                                                                                                 |
| Verified by  | `adminAuth.verifySessionCookie(cookie, true)` (the `true` enables revocation check). Errors mapped to `UnauthorizedError` codes `NO_SESSION` / `SESSION_EXPIRED` / `SESSION_REVOKED` / `UNAUTHORIZED`. |

There is **no second persistence layer for sessions** — revocation is delegated to Firebase Auth (admin SDK can revoke, the verify-with-check flag picks it up).

## Pricing tables (in-code, not DB)

Both plans are hard-coded in [lib/pricing/plans.ts](../apps/web/src/lib/pricing/plans.ts) (NOT in the database):

| `id`      | `name`  | `priceCents` | `currency` | `billingPeriod` | `stripePriceEnvKey`    |
| --------- | ------- | -----------: | ---------- | --------------- | ---------------------- |
| `monthly` | Monthly |          799 | EUR        | month           | `STRIPE_PRICE_MONTHLY` |
| `yearly`  | Yearly  |         7990 | EUR        | year            | `STRIPE_PRICE_YEARLY`  |

The Stripe `price_id` lives in env vars per environment, not in code. Plan benefits text is in code: "Full access to session review, clip export, and minimap analysis." for monthly; "Everything in Monthly, billed once per year." for yearly.

## Schemas (Zod, web-local)

[lib/schemas/](../apps/web/src/lib/schemas/) — all imports use `'zod/v4'`.

| File                | Schema                                                                                                                              | Used by                                   |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `auth.ts`           | sign-in / sign-up form fields                                                                                                       | client forms                              |
| `subscription.ts`   | `subscriptionResponseSchema` (`status`, `plan`, `current_period_end:number`, `stripe_customer_id`, `stripe_subscription_id`)        | `GET /api/subscription` (server + client) |
| `webhook-events.ts` | `invoicePaidSchema`, `subscriptionDeletedSchema`, `paymentFailedSchema` (dahlia `parent.subscription_details.subscription` nesting) | webhook handlers                          |

### `invoicePaidSchema`

```ts
{
  customer: string,
  parent: { subscription_details: { subscription: string } },
  lines: {
    data: [
      { period: { end: number /* unix seconds */ } },
      ...
    ]
  }
}
```

### `subscriptionDeletedSchema`

```ts
{
  id: string,
  customer: string | { id: string },
  metadata?: Record<string, string>
}
```

`metadata.firebase_uid` MUST be present at runtime; the handler enforces this (per-event throw if missing). Set when the Checkout Session is created.

### `paymentFailedSchema`

Same `parent.subscription_details.subscription` nesting as `invoicePaidSchema`. Don't regress to top-level `invoice.subscription`.

## Stripe metadata schema (out-of-band but load-bearing)

Stripe does not enforce shapes; the webhook handlers do. Stripe artifacts the web app **expects** to carry `metadata.firebase_uid` and `metadata.plan_id`:

| Stripe object    | Required metadata                                                               | Set when                     |
| ---------------- | ------------------------------------------------------------------------------- | ---------------------------- |
| Checkout Session | `firebase_uid`, `plan_id`                                                       | `POST /api/checkout/session` |
| Subscription     | `firebase_uid`, `plan_id` (via Checkout Session's `subscription_data.metadata`) | Same — Checkout copies it    |
| Customer         | (inferred from `subscription.customer` at webhook time, no metadata required)   | n/a                          |

If `firebase_uid` is missing on a subscription at webhook time, the handler **throws** rather than silently dropping the event — surfaces orphaned-subscription bugs.

## Reading and writing — quick reference

| Operation                              | Direction                                     | Code path                                                                       |
| -------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------- |
| Browser sign-in → cookie               | client → admin SDK                            | `firebase signInWith…` → `getIdToken()` → `POST /api/auth/session`              |
| Cookie verify                          | admin SDK                                     | `requireSession()` → `verifySessionCookie(cookie, true)`                        |
| Cookie destroy                         | server                                        | `cookies().delete('session')` (server) + client `signOut(auth)`                 |
| Read `users/{uid}`                     | server (server-only handlers + dashboard SSR) | `withAuth(session => adminDb.collection('users').doc(session.uid).get())`       |
| Read `users/{uid}` (browser, indirect) | server fetch                                  | `useSubscription` → `GET /api/subscription`                                     |
| Write `users/{uid}`                    | webhook only                                  | `adminDb.runTransaction(tx => tx.update(userRef, baseFields))`                  |
| Write `stripe_events/{id}`             | webhook only                                  | same transaction as dedupe check                                                |
| Stripe Checkout / Portal create        | server                                        | `getStripe().checkout.sessions.create(…)` / `…billingPortal.sessions.create(…)` |
