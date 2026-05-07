# Data Models — Shared (`contracts/`)

The two language-agnostic contracts that bind apps together. Both are JSON Schema (Draft 2020-12) at the repo root. TS Zod modules are auto-generated under [packages/contracts/src/generated/](../packages/contracts/src/generated/) by [`generate-zod.mjs`](../packages/contracts/scripts/generate-zod.mjs).

## `MapConfig` — [contracts/map-config.schema.json](../contracts/map-config.schema.json)

Map identification fingerprint emitted by `apps/tooling` and consumed by `apps/mobile`. Each map has a perceptual hash computed over a fixed ROI of the minimap region. Mobile uses these to identify the map without running OpenCV on device.

**`additionalProperties: false`** — strict.

```jsonc
{
  "reference_resolution": {
    "width":  integer >= 1,
    "height": integer >= 1
  },
  "roi": {                              // map-name banner rectangle at reference_resolution
    "x":      integer >= 0,
    "y":      integer >= 0,
    "width":  integer >= 1,
    "height": integer >= 1
  },
  "canvas_size": integer >= 1,          // square canvas the ROI is normalized into before hashing
  "hash_size":   integer >= 1,          // 16 → 256-bit hash → 64 hex chars
  "hash_method": "ahash"|"phash"|"dhash"|"whash",
  "text_anchor_width"?: integer >= 0,   // optional sub-cropping inside the ROI
  "maps": {
    [mapNameSlug]: string  // hex-encoded perceptual hash, ^[0-9a-f]+$, length depends on hash_size
    // minProperties: 1
  }
}
```

Map name slugs are lowercase ASCII (e.g. `the_cliff`, `frostbite`).

**Producer:** [tools/map_config_generator.py](../apps/tooling/tools/map_config_generator.py). Runtime validation in Python via `jsonschema`. Output filename is `map_config.json` (not the `.schema.json` master).

**Consumer:** `apps/mobile`. Today via Firestore document `detection_config/latest`, which is a _superset_ of `MapConfig` (adds `version`, ROI zones for detection, HSV bands). The bare `MapConfig` JSON file is not currently bundled. Phase 6 must decide:

- Bundle `map_config.json` as a Metro asset (immutable, ships with app) — simpler, no runtime read, but requires app release for new maps.
- Continue Firestore-fetched (live update path) — current behaviour but adds an explicit Firestore read.

**TS surface (auto-generated):** `MapConfigSchema` exported from `@warden/contracts/map-config`. Re-exported via the package barrel.

## `UserDoc` — [contracts/user-doc.schema.json](../contracts/user-doc.schema.json)

Firestore `users/{uid}` document. Web writes (Stripe webhook handlers); mobile reads (subscription gate).

**`additionalProperties: true`** — explicitly lax so the legacy `isPaid` field is tolerated until Phase 6 drops it. `created_at`/`updated_at` (server-stamped Timestamps) are also permitted but not part of the formal schema.

```jsonc
{
  "status": "active" | "past_due" | "canceled",            // mirrored from Stripe by web webhook handler
  "plan":   "monthly" | "yearly",
  "current_period_end"?:    number,                         // Unix seconds
  "stripe_customer_id"?:    string,                         // for customer-portal handoff
  "stripe_subscription_id"?: string,                        // for webhook reconciliation
  "isPaid"?:                boolean                         // legacy denormalized flag (mobile reads historically)
}
```

**Required fields:** `status`, `plan`. Everything else is optional or `additionalProperties`.

**Producer:** `apps/web`, [src/lib/stripe/webhooks.ts](../apps/web/src/lib/stripe/webhooks.ts). Three handlers:

- `invoice.paid` → set `{status:'active', plan, current_period_end (Timestamp), stripe_customer_id, stripe_subscription_id, updated_at}` (and `created_at` on first write).
- `customer.subscription.deleted` → set `{status:'canceled', updated_at}`.
- `invoice.payment_failed` → set `{status:'past_due', updated_at}`.

**Consumer:** `apps/mobile`, [features/auth/subscriptionService.ts](../apps/mobile/src/features/auth/subscriptionService.ts). Considers paid iff `status ∈ {active, trialing}` AND `current_period_end > now`. (Note: web never writes `'trialing'` — that comes from Stripe directly, e.g. via the Checkout flow when the price has a trial; the schema enum doesn't list `trialing` because web's set is a strict subset.)

**Open conflict.** Web stores `current_period_end` as a Firestore `Timestamp` while the schema documents it as `number` (Unix seconds). Mobile reads it as `Timestamp` and calls `.toMillis()`. The `GET /api/subscription` endpoint translates to `Timestamp.seconds` for the wire response. The schema's "number" reflects the wire format; in-Firestore it's a Timestamp. This is intentional but worth a Phase 6 doc-fix.

**TS surface (auto-generated):** `UserDocSchema` exported from `@warden/contracts/user-doc`. Web does NOT yet import this — it has its own [`subscriptionResponseSchema`](../apps/web/src/lib/schemas/subscription.ts) with stricter status enum (`active` | `past_due` | `canceled`). Phase 6 unification candidate.

## Why JSON Schema, not Zod-master

`apps/tooling` is Python. The team picked **JSON Schema as master** so both ecosystems can validate without a TS toolchain dependency. Zod is generated, not authored. Reverse direction (Zod-master, generate JSON Schema) was rejected — it would force tooling to depend on `node` to validate map_config emissions, which contradicts the lab's standalone-CLI ergonomics.

## Schema authorship rules

1. Edit only the `.schema.json` files in `contracts/`.
2. Re-run `pnpm --filter @warden/contracts build` to regenerate Zod.
3. Update consumers that diverged (currently `apps/web/src/lib/schemas/subscription.ts` is a candidate for replacement).
4. Commit schema + regenerated TS + consumer updates together.
5. Validate with both producers (run mobile tests + a tooling round-trip; web validates implicitly via webhook-event tests).

## Versioning

- `@warden/contracts` is `private: true` and `version: 0.0.0` — there's no SemVer discipline because nothing outside the monorepo consumes it.
- The wire-level `MapConfig` JSON has **no version field** — versioning is handled at the Firestore `detection_config/latest` document level (which has a `version: number` for stale-while-revalidate). If `map_config.json` ever ships as a Metro asset, add a version field at that point.
- The `users/{uid}` document has no version field. Schema migrations would need to be coordinated with mobile (which reads via the firebase JS SDK, not via the Zod schema today).

## Phase 6 candidates

- Drop `isPaid` from `user-doc.schema.json` and migrate any remaining legacy reads.
- Add `trialing` to the `status` enum (currently web's domain doesn't allow it; Stripe-driven trials would write `trialing` via the SDK and break the enum check).
- Add a `version: number` field to `MapConfig` if mobile ever bundles the JSON instead of fetching the Firestore superset.
- Add a `created_at` / `updated_at` formal slot to `user-doc.schema.json` (currently relies on `additionalProperties: true`).
- Wire `apps/web` to import `@warden/contracts/user-doc` instead of redeclaring the schema.
