# Integration Architecture — Warden Monorepo

How the four parts (mobile, web, tooling, shared) talk to each other. This is the document Phase 6's `bmad-create-architecture` should consume to make unified architecture decisions.

## Map of integration points

```
                      ┌──────────────────────────────────────┐
                      │              Stripe                  │
                      │    (Checkout, Customer Portal,       │
                      │     subscription state of record)    │
                      └─────────────┬────────────────────────┘
                                    │ webhook events
                                    │ (invoice.paid, subscription.deleted, payment_failed)
                                    ▼
┌──────────────┐                ┌────────────────────────┐
│ apps/tooling │                │      apps/web          │
│ (Python CLI) │                │ Next.js 16 App Router  │
└──────┬───────┘                │ runtime = nodejs       │
       │                        └─────────┬──────────────┘
       │ emits                            │ writes (server-only via firebase-admin)
       │ map_config.json                  │
       │ (validated by                    │
       │  contracts/map-                  │
       │  config.schema.json)             │
       │                                  ▼
       │                        ┌────────────────────────┐
       │                        │      Firebase          │
       │                        │  - Auth (shared)       │
       │                        │  - Firestore           │
       │                        │     • users/{uid}      │
       │                        │     • stripe_events    │
       │                        │     • detection_config │
       │                        └────────┬───────────────┘
       │                                 │ reads (client SDK)
       │                                 ▼
       │                       ┌────────────────────────┐
       │  bundle / OTA         │     apps/mobile        │
       └──────────────────────►│ Expo / React Native    │
                                │  - SQLite (sessions)   │
                                │  - MMKV (auth, prefs)  │
                                │  - FFmpeg/OpenCV/JSI   │
                                └────────────────────────┘
```

## Integrations (one row per directional edge)

| #   | From               | To                        | Protocol                          | Where in code                                                                                                                                                                                                                              | Format / payload                                                                                                                                                                                                                                                           |
| --- | ------------------ | ------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | apps/web           | Stripe                    | HTTPS (Stripe SDK)                | [lib/stripe/server.ts](../apps/web/src/lib/stripe/server.ts), [api/checkout/session/route.ts](../apps/web/src/app/api/checkout/session/route.ts), [api/subscription/portal/route.ts](../apps/web/src/app/api/subscription/portal/route.ts) | Stripe Checkout Session, Billing Portal Session. API version `2026-03-25.dahlia`.                                                                                                                                                                                          |
| 2   | Stripe             | apps/web                  | HTTPS POST webhook                | [api/webhooks/stripe/route.ts](../apps/web/src/app/api/webhooks/stripe/route.ts) → [lib/stripe/webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts)                                                                                        | `invoice.paid`, `customer.subscription.deleted`, `invoice.payment_failed`. Signature verified with `STRIPE_WEBHOOK_SECRET`. Idempotency table at `stripe_events/{event.id}`.                                                                                               |
| 3   | apps/web           | Firestore                 | firebase-admin (server)           | [lib/firebase/admin.ts](../apps/web/src/lib/firebase/admin.ts), [lib/stripe/webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts)                                                                                                           | Writes `users/{uid}` (`status`, `plan`, `current_period_end`, `stripe_customer_id`, `stripe_subscription_id`, `created_at`, `updated_at`); writes `stripe_events/{event.id}` for dedupe. Server-only — `firestore.rules` denies client writes.                             |
| 4   | apps/web (browser) | Firebase Auth             | firebase client SDK               | [lib/firebase/client.ts](../apps/web/src/lib/firebase/client.ts), [contexts/AuthContext.tsx](../apps/web/src/contexts/AuthContext.tsx)                                                                                                     | Email/password + Google sign-in. ID token traded for an httpOnly session cookie via `POST /api/auth/session`.                                                                                                                                                              |
| 5   | apps/web (browser) | apps/web (route handlers) | HTTP (same origin)                | [api/](../apps/web/src/app/api/)                                                                                                                                                                                                           | All route handlers under [api-contracts-web.md](./api-contracts-web.md). Session cookie carries auth.                                                                                                                                                                      |
| 6   | apps/mobile        | Firebase Auth             | firebase JS SDK + AsyncStorage    | [features/auth/firebaseConfig.ts](../apps/mobile/src/features/auth/firebaseConfig.ts), [authService.ts](../apps/mobile/src/features/auth/authService.ts)                                                                                   | Email/password + Google sign-in (via `@react-native-google-signin/google-signin`). Persistence via `getReactNativePersistence(AsyncStorage)` — see [Brownfield issue](#brownfield-issues).                                                                                 |
| 7   | apps/mobile        | Firestore                 | firebase JS SDK                   | [features/auth/subscriptionService.ts](../apps/mobile/src/features/auth/subscriptionService.ts)                                                                                                                                            | Reads `users/{uid}` to gate paid features. Treats `status ∈ {active, trialing}` AND `current_period_end > now` as paid. Periodic re-validation every 60 min.                                                                                                               |
| 8   | apps/mobile        | Firestore                 | firebase JS SDK                   | [features/video-processing/detectionConfigService.ts](../apps/mobile/src/features/video-processing/detectionConfigService.ts)                                                                                                              | Reads `detection_config/latest` (single-doc collection). MMKV cache + stale-while-revalidate (`version` field gates background refresh). Singleflighted.                                                                                                                   |
| 9   | apps/tooling       | filesystem                | local files                       | [tools/map_config_generator.py](../apps/tooling/tools/map_config_generator.py)                                                                                                                                                             | Emits `map_config.json` containing pHash fingerprints per EVA map. Schema-validated against [contracts/map-config.schema.json](../contracts/map-config.schema.json).                                                                                                       |
| 10  | apps/tooling       | apps/mobile               | indirect (via Firestore + bundle) | n/a                                                                                                                                                                                                                                        | The output of (9) is the input to (8). **Runtime delivery method is an open Phase 6 question** — bundle vs. Firestore-fetched. Currently mobile fetches via (8).                                                                                                           |
| 11  | packages/contracts | apps/web                  | TS package import                 | direct ESM                                                                                                                                                                                                                                 | `@warden/contracts/user-doc` — auto-generated Zod from `contracts/user-doc.schema.json`. Currently `apps/web` re-declares its own Zod schemas ([schemas/subscription.ts](../apps/web/src/lib/schemas/subscription.ts)) — they are not yet pointing at `@warden/contracts`. |
| 12  | packages/contracts | apps/mobile               | TS package import                 | declared in [apps/mobile/package.json](../apps/mobile/package.json) (`"@warden/contracts": "workspace:*"`)                                                                                                                                 | Mobile imports the workspace package; resolution goes via Metro `nodeModulesPaths` + the contracts package's `main`/`exports` (TS source — Metro transpiles directly, no build step needed).                                                                               |
| 13  | apps/tooling       | contracts/                | filesystem read (Python)          | inferred — schema validation expected to use `jsonschema` per memory and `pyproject.toml` deps                                                                                                                                             | Python tools validate emitted JSON against `contracts/*.schema.json` using `jsonschema`.                                                                                                                                                                                   |

## Schemas — the single source of truth

[`contracts/`](../contracts/) at the repo root holds JSON Schema files that bind both languages:

- [`map-config.schema.json`](../contracts/map-config.schema.json) — `reference_resolution`, `roi`, `canvas_size`, `hash_size`, `hash_method ∈ {ahash,phash,dhash,whash}`, `text_anchor_width?`, `maps: { [mapName]: hexHashString }`.
- [`user-doc.schema.json`](../contracts/user-doc.schema.json) — Firestore `users/{uid}` shape: `status ∈ {active,past_due,canceled}`, `plan ∈ {monthly,yearly}`, `current_period_end?`, `stripe_customer_id?`, `stripe_subscription_id?`, `isPaid?` (legacy). `additionalProperties: true` to keep the legacy `isPaid` field tolerable.

[`packages/contracts/scripts/generate-zod.mjs`](../packages/contracts/scripts/generate-zod.mjs) reads both schemas and emits typed Zod modules at [`packages/contracts/src/generated/*.ts`](../packages/contracts/src/generated/). The generated files carry an "AUTO-GENERATED — do not edit" banner. Regenerate with:

```sh
pnpm --filter @warden/contracts build
```

The Python side has no generator yet; tooling validates against the JSON Schema files directly via `jsonschema`.

## Auth flow (web)

```
Browser              Next.js route handler           Firebase
  │                          │                          │
  │  signInWith{Email,Google}                           │
  ├─────────────────────────────────────────────────────►│
  │  ◄─ User + idToken ─────────────────────────────────│
  │                          │                          │
  │  POST /api/auth/session  │                          │
  │  { idToken }             │                          │
  ├─────────────────────────►│                          │
  │                          │  adminAuth.verifyIdToken │
  │                          ├─────────────────────────►│
  │                          │  adminAuth.createSessionCookie
  │                          ├─────────────────────────►│
  │                          │  ◄─ sessionCookie ───────│
  │  Set-Cookie: session=…   │                          │
  │  ◄───────────────────────│                          │
  │                          │                          │
  │  GET /api/subscription   │                          │
  ├─────────────────────────►│  withAuth → requireSession
  │                          │  adminDb.collection('users').doc(uid).get()
  │                          ├─────────────────────────►│
  │  ◄ data: SubscriptionResponse                       │
  │                          │                          │
  │  DELETE /api/auth/session                           │
  ├─────────────────────────►│  cookies().delete('session')
  │  ◄ Set-Cookie: session=  │                          │
```

Session cookie: `httpOnly`, `sameSite=lax`, 7-day max age, `secure` in production. See [lib/firebase/session.ts](../apps/web/src/lib/firebase/session.ts) for `requireSession` / `withAuth` / `UnauthorizedError` (codes: `NO_SESSION`, `SESSION_EXPIRED`, `SESSION_REVOKED`, `UNAUTHORIZED`).

## Stripe webhook flow (web → Firestore)

```
Stripe        POST /api/webhooks/stripe                  Firestore
  │                       │                                  │
  ├─ event ───────────────►│ verify signature (constructEvent)
  │                       │ runTransaction:                  │
  │                       │   if stripe_events/{id} exists ─►│ duplicate, return 200
  │                       │   else create stripe_events/{id} │
  │                       │ routeEvent(event):               │
  │                       │   handleInvoicePaid          → users/{uid}.status=active, current_period_end, plan
  │                       │   handleSubscriptionDeleted  → users/{uid}.status=canceled
  │                       │   handlePaymentFailed        → users/{uid}.status=past_due
  │                       │                                  │
  │  ◄─ 200 (always) ─────│                                  │
```

Important details from [webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts):

- **Self-namespace import (`import * as self from './webhooks'`)** — `routeEvent` calls `self.handleX` so `vi.spyOn(webhooksModule, 'handleX')` works in tests. Direct calls would bypass the spy due to ESM local-binding resolution. Stories 4.2/4.3 rely on this.
- **`firebase_uid` metadata required.** Webhooks pull `subscription.metadata.firebase_uid`; without it the handler errors. Set when the Checkout Session is created ([api/checkout/session/route.ts](../apps/web/src/app/api/checkout/session/route.ts)).
- **`plan_id` metadata required and validated** against `PLAN_IDS = ['monthly','yearly']`.
- **Idempotency table.** `stripe_events/{event.id}` doc with fields `event_id, event_type, received_at, api_version, livemode`. Created in the same transaction as the dedupe check.
- **Retry policy.** `retryStripeCall` retries on transient errors (`StripeConnectionError`, `StripeRateLimitError`, 5xx) at delays `[250, 750, 2250]`ms.
- **Routing failure returns 200** (with `routingError: true`) to stop Stripe retries; the event is still in `stripe_events/` for manual replay.

## Detection-config flow (mobile pulls from Firestore)

```
mobile boot                    Firestore
   │                                │
   │  getDetectionConfig()          │
   ├──┐ readCache() (MMKV)          │
   │  │  ◄─ cached config ──┐       │
   │  └─ return cached ─────┘       │
   │  & spawn backgroundRefresh ────►│ doc(detection_config/latest).get()
   │                                │ if remote.version > cached.version
   │                                │   writeCache(remote)  (MMKV)
```

- Path: `detection_config/latest` (single-doc collection).
- MMKV key: `detection.config`.
- Validation: every read goes through `validateDetectionConfig`. Cache misses on schema validation are silently discarded (corrupted MMKV writes / schema migrations).
- Concurrency: `inflightInitialFetch`, `inflightBackgroundRefresh`, `inflightForcedRefresh` singleflight all three paths so concurrent per-frame detector reads (Story 7.5 hot path) share a single round-trip.
- Error surfaces: `OfflineFirstLaunchError` (no cache + offline) vs `MalformedRemoteConfigError` (no cache + remote payload schema-invalid) so the bootstrap can pick disambiguated user copy.

## Brownfield issues

These are pre-existing (NOT migration-introduced). Phase 6 must triage before merging fixes.

| Issue                                               | Where                                                                                                                                                                                                                                      | Impact                                                                                                                        | Decision needed                                                                                                       |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Stripe API version drift                            | [server.ts](../apps/web/src/lib/stripe/server.ts) pins `2026-03-25.dahlia` but installed `@stripe` types want `2026-04-22.dahlia`                                                                                                          | TS errors in `*.test.ts` (spread args, implicit any). Runtime is fine — webhook event schemas already reflect dahlia nesting. | Bump pinned API version to match installed types and re-validate.                                                     |
| `getReactNativePersistence` removed in Firebase v12 | [firebaseConfig.ts](../apps/mobile/src/features/auth/firebaseConfig.ts)                                                                                                                                                                    | Build/runtime warning; future minor version may drop the symbol.                                                              | Migrate to `@react-native-firebase/auth` (TODO in source) or pin firebase to a version that still exposes the helper. |
| `users/{uid}` `isPaid` vs `status` duplication      | [contracts/user-doc.schema.json](../contracts/user-doc.schema.json), [.env.example](../apps/mobile/.env.example) (legacy doc), [subscriptionService.ts](../apps/mobile/src/features/auth/subscriptionService.ts) (currently uses `status`) | Mobile already migrated to `status`; mobile `.env.example` and the JSON schema's optional `isPaid` are still legacy carriers. | Phase 6 architecture: drop `isPaid` or formalize as a denormalized read-only convenience.                             |
| `map_config.json` runtime delivery                  | tooling emits, mobile reads via Firestore today (`detection_config/latest`)                                                                                                                                                                | Couples mobile to a Firestore round-trip even though the data is map-static.                                                  | Phase 6: bundle as Metro asset (immutable, ships with app) vs continue Firestore-fetched (runtime updatable).         |
| Same Firebase project for web + mobile?             | Apparent from env conventions, not asserted by code                                                                                                                                                                                        | Risks running mobile against a different project.                                                                             | Phase 6: assert in Architecture and configure CI to enforce.                                                          |

## Phase 6 inputs (what consumers should read)

`bmad-create-architecture` should ingest:

1. This file ([integration-architecture.md](./integration-architecture.md)).
2. [`_bmad-output/legacy/distillate/05-architecture-cross-cutting.md`](../_bmad-output/legacy/distillate/05-architecture-cross-cutting.md) — plan-level architecture decisions from the three legacy PRDs.
3. Per-part: [architecture-mobile.md](./architecture-mobile.md), [architecture-web.md](./architecture-web.md), [architecture-tooling.md](./architecture-tooling.md), [architecture-shared.md](./architecture-shared.md).
4. The contracts: [contracts/map-config.schema.json](../contracts/map-config.schema.json), [contracts/user-doc.schema.json](../contracts/user-doc.schema.json).
