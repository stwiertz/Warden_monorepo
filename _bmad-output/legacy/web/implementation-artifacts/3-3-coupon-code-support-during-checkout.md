# Story 3.3: Coupon Code Support During Checkout

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user on the pricing page,
I want to enter a coupon code and see the discounted price (and the deferred billing date when applicable) before I click through to Stripe Checkout,
So that I feel confident about what I'll be charged and when, and trust the offer that brought me here.

## Acceptance Criteria

1. **Given** a new client-side checkout state container [src/components/checkout/CheckoutContext.tsx](src/components/checkout/CheckoutContext.tsx) (first co-resident of the existing `src/components/checkout/` folder)
   **When** it is imported
   **Then** it exports a `CheckoutProvider` component and a `useCheckout()` hook with the shape `{ coupon: AppliedCoupon | null, applyCoupon(c: AppliedCoupon): void, clearCoupon(): void }`
   **And** `AppliedCoupon` is `{ code: string; percentOff: number | null; amountOffCents: number | null; durationInMonths: number | null }` — one of `percentOff` or `amountOffCents` is always non-null; `durationInMonths` is non-null only when the coupon has `duration: 'repeating'` (captured so the client can compute the deferred billing date locally without another round trip)
   **And** `useCheckout()` throws a clear error (`'useCheckout must be used within a CheckoutProvider'`) when called outside a provider — matches the `useAuth()` failure-mode convention already established in [src/hooks/useAuth.ts](src/hooks/useAuth.ts)
   **And** the provider accepts an optional `initialCoupon?: AppliedCoupon` prop so the server-rendered pricing page can seed the state from a URL param without a client-side re-fetch

2. **Given** a new API route handler at [src/app/api/checkout/coupon/route.ts](src/app/api/checkout/coupon/route.ts)
   **When** it receives `POST { code: string }`
   **Then** the file sets `export const runtime = 'nodejs'` (the `stripe` SDK is Node-only — same constraint as Story 3.2's `/api/checkout/session`)
   **And** it validates the body with a Zod schema `z.object({ code: z.string().trim().min(1).max(64) })` using the project's `from 'zod/v4'` convention
   **And** on invalid body returns `400 { error: { code: 'INVALID_REQUEST', message: 'Coupon code is required' } }`
   **And** it calls `getStripe().promotionCodes.list({ code, active: true, limit: 1, expand: ['data.coupon'] })`
   **And** if the result list is empty, or `data[0].coupon.valid === false`, or `data[0].active === false`, or `data[0].expires_at` is in the past, returns `400 { error: { code: 'COUPON_INVALID', message: 'This coupon is not valid or has expired' } }`
   **And** on a valid hit, returns `200 { data: { code, percentOff, amountOffCents, durationInMonths } }` where:
   - `code` — the **original user input** (preserves casing so the CouponInput can redisplay exactly what the user typed), NOT `data[0].code` which is Stripe's normalized value
   - `percentOff` — `coupon.percent_off ?? null` (Stripe stores this as a number 0-100; pass through unchanged)
   - `amountOffCents` — `coupon.amount_off ?? null` (Stripe stores cents; pass through — DO NOT convert currency, this app is single-currency EUR per plans.ts)
   - `durationInMonths` — `coupon.duration === 'repeating' ? coupon.duration_in_months : null` (ONLY set for repeating coupons — `'once'` and `'forever'` produce `null` to keep the client logic simple)
   **And** on any thrown Stripe error that is NOT an invalid-coupon, returns `500 { error: { code: 'COUPON_LOOKUP_FAILED', message: 'Unable to validate coupon' } }` — distinct from `COUPON_INVALID` so the CouponInput can distinguish "bad code" (user error) from "Stripe down" (retry button)
   **And** the route does NOT read the session cookie — coupon preview is **public information** per the UX spec's "coupon-first flow" (ux-design-specification.md:62, 95). Requiring auth to preview a coupon would defeat the pre-signin conversion path (Discord link → pricing → coupon preview → sign in → checkout)

3. **Given** a new client component [src/components/checkout/CouponInput.tsx](src/components/checkout/CouponInput.tsx)
   **When** it is rendered on the pricing page
   **Then** it exposes:
   - an `<input type="text">` with `aria-label="Coupon code"`, `name="coupon"`, `autoComplete="off"`, `spellCheck={false}`, `maxLength={64}`, placeholder `e.g. COACH2FREE`
   - an `<button type="button">Apply</button>` next to the input, `min-h-11 min-w-11` touch target, reusing `ctaPrimaryClass` from [src/components/ui/cta-class.ts](src/components/ui/cta-class.ts) — this is the only additional use of that token in this story
   - a `Remove` text button (`<button type="button" className="text-muted-foreground underline">`) that appears ONLY when a coupon is already applied; clicking it invokes `clearCoupon()` and resets the input
   **And** on Apply, the component `POST`s to `/api/checkout/coupon` with `{ code: input.trim() }`, disables the button while pending, and on success calls `applyCoupon(data)` from `useCheckout()` AND renders a success message `Coupon applied: {code}` via `role="status"` live region
   **And** on `400 COUPON_INVALID`, renders an inline error `role="alert"` with copy `This coupon is not valid or has expired.` and does NOT touch context state
   **And** on `500 COUPON_LOOKUP_FAILED` or a network error, renders `Something went wrong — please try again.` (no retry button; the Apply button re-enables and the user retries manually)
   **And** when a coupon is already applied, the input renders `disabled` and pre-filled with `coupon.code`; the Apply button is replaced by the Remove button (mutually exclusive UI state — do NOT render both Apply and Remove at the same time)
   **And** the component handles `Enter` keypress inside the input as equivalent to clicking Apply (wrap in a `<form onSubmit>` with `event.preventDefault()` to get this for free — do not add a keydown handler)

4. **Given** a new exported helper `computeDiscountedPrice(plan: Plan, coupon: AppliedCoupon): { discountedCents: number; deferredUntil: Date | null }` in [src/lib/pricing/discount.ts](src/lib/pricing/discount.ts) (new file — NOT inside `plans.ts`, which stays stable and is transitively imported by client bundles)
   **When** this story lands
   **Then** the function:
   - If `coupon.percentOff === 100`, returns `{ discountedCents: 0, deferredUntil: <computed> }`
   - If `coupon.percentOff` is 1-99, returns `{ discountedCents: Math.round(plan.priceCents * (1 - coupon.percentOff / 100)), deferredUntil: null }` (no deferred date for partial percent coupons — Stripe simply reduces the first charge)
   - If `coupon.amountOffCents` is set, returns `{ discountedCents: Math.max(0, plan.priceCents - coupon.amountOffCents), deferredUntil: <computed if result is 0> }`
   - `deferredUntil` is computed ONLY when `discountedCents === 0` AND `coupon.durationInMonths !== null`: returns `addMonthsUTC(new Date(), coupon.durationInMonths)` where `addMonthsUTC` is a local pure helper (DO NOT import `date-fns` or `dayjs` — the project has zero date libraries, avoid adding one for a single call site)
   - If `discountedCents === 0` AND `durationInMonths === null` (a 100%-off `forever` or `once` coupon), `deferredUntil` is `null` — the UI will render "Free with this coupon" instead of a date (see AC #5)
   **And** the helper is pure (no `Date.now()` capture at module load — always call `new Date()` inside the function so tests can seed with `vi.useFakeTimers()`)
   **And** a unit test file [src/lib/pricing/discount.test.ts](src/lib/pricing/discount.test.ts) covers: 100% repeating (deferred date set), 50% percent-off (no deferred date), 500c amount-off (no deferred date), 799c amount-off on monthly plan (zero result, no date because durationInMonths is null), month-arithmetic edge case (Jan 31 + 1 month → Feb 28/29)

5. **Given** the extracted plan card component [src/components/checkout/PlanCard.tsx](src/components/checkout/PlanCard.tsx) (moved out of [src/app/pricing/page.tsx](src/app/pricing/page.tsx); the inline `PlanCard` function there is DELETED and replaced by the import)
   **When** a coupon is NOT applied
   **Then** the card renders exactly as it does today: plan name, benefits, full price, period label, savings label (yearly only), `<PlanCta />` — zero visual regression
   **When** a coupon IS applied
   **Then** the card additionally renders:
   - The original price with `<s>` strikethrough styling (`text-muted-foreground line-through text-base`) immediately above the new price
   - The discounted price (from `computeDiscountedPrice`) in the same `text-[2rem] font-extrabold` slot the full price previously occupied
   - If `deferredUntil !== null`: a muted line `First charge on {formatDate(deferredUntil)}` — `formatDate` is `new Intl.DateTimeFormat('en-IE', { dateStyle: 'long' }).format(date)`, inlined in `PlanCard.tsx` (one call site, no helper needed)
   - If `discountedCents === 0` AND `deferredUntil === null`: a muted line `Free with this coupon`
   - The savings label (yearly card) is suppressed when a coupon is applied — the discount IS the savings story, comparing to the non-coupon monthly is noise
   **And** `PlanCard` is a Client Component (`'use client'` at the top — required because it calls `useCheckout()`); the pricing page itself (`page.tsx`) remains a Server Component — only the leaf cards and the coupon input cross the client boundary
   **And** `PlanCard` preserves the existing accessibility landmarks (`<article aria-labelledby>`, heading id `plan-${plan.id}-name`, the `Best value` `<span>` for yearly) — the ONLY changes are the price block and the conditional coupon display lines

6. **Given** the checkout provider wiring in [src/app/pricing/page.tsx](src/app/pricing/page.tsx)
   **When** a user navigates to `/pricing` or `/pricing?coupon=COACH2FREE`
   **Then** the page:
   - Stays a Server Component (`async` function, `searchParams` is still `Promise<{ checkout?: string; coupon?: string }>`)
   - Reads `resolved.coupon` — if present and non-empty, server-side performs a best-effort preview by calling a new server-only helper `previewCoupon(code: string): Promise<AppliedCoupon | null>` that wraps the same `stripe.promotionCodes.list` call used by the API route (co-locate the core logic in a new [src/lib/stripe/coupons.ts](src/lib/stripe/coupons.ts), import it from BOTH the API route AND the page — DO NOT fetch the app's own API from `page.tsx`, that's the classic Next.js footgun)
   - Passes the preview result (or `null`) as `initialCoupon` to `<CheckoutProvider initialCoupon={...}>` which wraps the `<CouponInput />` + plan grid
   - If `previewCoupon` throws (Stripe outage), the page renders normally WITHOUT an initial coupon — it must NOT 500. Log with `console.warn` and move on; the user can still enter a code manually
   **And** `<CouponInput />` is rendered ABOVE the plan grid inside the `<section aria-labelledby="plans-heading">`, with its own sub-heading `<h3 className="sr-only">Coupon code</h3>` for landmark navigation, and `className="mx-auto max-w-md mb-6"` to keep it visually centered above the cards
   **And** the canceled banner from Story 3.2 still renders in its current position (between the section heading and any coupon UI, or between the coupon UI and the grid — reviewer's call; the test assertion just checks the banner is rendered when `checkout === 'canceled'`)

7. **Given** the extended checkout session route [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts)
   **When** this story lands
   **Then** the Zod body schema becomes `z.object({ planId: z.enum(PLAN_IDS), couponCode: z.string().trim().min(1).max(64).optional() })`
   **And** on a request that includes `couponCode`, the handler re-resolves the code server-side via the same `previewCoupon` helper (DO NOT trust the client to send a valid code — always revalidate; client state is authoritative for UX display, NEVER for security)
   **And** if re-resolution fails, returns `400 { error: { code: 'COUPON_INVALID', message: 'This coupon is no longer valid' } }` — the user is bounced back to the pricing page by `PlanCta` which renders the error inline (AC #8) and `clearCoupon()`s the stale context
   **And** when a valid promotion code resolves, the handler fetches the **promotion_code ID** (Stripe's `promo_xxx`, NOT the user-facing `code` string) and passes it to `stripe.checkout.sessions.create` as:
   - `discounts: [{ promotion_code: promotionCodeId }]`
   - `allow_promotion_codes` is **OMITTED** in this call path — Stripe rejects the combination with `allow_promotion_codes` + `discounts` (`You cannot pass both allow_promotion_codes and discounts...`). When `couponCode` is present, drop the flag; when absent, keep the Story 3.2 behavior (`allow_promotion_codes: true` so the hosted page still accepts entry for users who skipped the in-app input).
   **And** `previewCoupon` is enhanced to ALSO return the Stripe `promotionCodeId` (`data[0].id`) so the session route can pass it without a second round trip — the API `/api/checkout/coupon` route does NOT return the ID to the client (it's server-only plumbing; the client only needs the display-level fields from AC #2)
   **And** the existing 200/400/401/500 error branches, envelope shapes, and success response `{ data: { url } }` are **unchanged** for the no-coupon path

8. **Given** the updated CTA component [src/components/checkout/PlanCta.tsx](src/components/checkout/PlanCta.tsx)
   **When** this story lands
   **Then** `PlanCta` calls `useCheckout()` and, when `coupon !== null`, includes `couponCode: coupon.code` in the `fetch` body `JSON.stringify({ planId: plan.id, couponCode: coupon.code })`
   **And** on a response with `error.code === 'COUPON_INVALID'`, `PlanCta` calls `clearCoupon()` AND renders the inline error `The applied coupon is no longer valid. Please try another.` (distinct copy from the generic error so the user understands WHY the flow bounced)
   **And** on all other error codes, the existing `GENERIC_CHECKOUT_ERROR` behavior from Story 3.2 is preserved unchanged
   **And** the `min-h-11`, `ctaPrimaryClass`, `type="button"`, focus-ring pattern, and `getCtaLabel(plan)` label are all unchanged
   **And** the `useCheckout()` call is moved inside `PlanCta` only — do NOT thread `coupon` as a prop from `PlanCard` into `PlanCta`; context is cleaner when both components live in the same feature folder and the provider wraps them at the page level

9. **Given** the testing baseline at the start of this story (191 / 191 from Story 3.2 code review)
   **When** this story lands
   **Then** the following tests exist and pass:
   - [src/app/api/checkout/coupon/route.test.ts](src/app/api/checkout/coupon/route.test.ts) — happy path (valid promo, percent-off), happy path (amount-off), happy path (repeating duration_in_months populated), empty list → `400 COUPON_INVALID`, inactive coupon (`data[0].active === false`) → `400`, expired promo (`data[0].expires_at` in the past) → `400`, invalid JSON → `400 INVALID_REQUEST`, empty string code → `400 INVALID_REQUEST`, Stripe throws → `500 COUPON_LOOKUP_FAILED`. Mocks `stripe` the same way the existing `route.test.ts` does (`vi.mock('stripe', ...)` with a plain `function Stripe(...)` constructor — the ES-module-constructor gotcha from Story 3.2's debug log applies here too).
   - [src/lib/pricing/discount.test.ts](src/lib/pricing/discount.test.ts) — five cases per AC #4 including the month-arithmetic edge case.
   - [src/lib/stripe/coupons.test.ts](src/lib/stripe/coupons.test.ts) — `previewCoupon()` direct unit test for: returns normalized shape on hit, returns `null` on empty list, returns `null` on inactive/expired, re-throws only on non-Stripe errors (Stripe API errors are caught and returned as `null` so the API route can distinguish the 400 vs 500 path via a second call pattern — wait, this contradicts AC #2. See clarification in Dev Notes → "COUPON_INVALID vs COUPON_LOOKUP_FAILED decoding"). The test file drives the chosen contract.
   - [src/components/checkout/CouponInput.test.tsx](src/components/checkout/CouponInput.test.tsx) — renders input+button, empty submit is a no-op (or relies on `min={1}` rejecting server-side; test both), happy path (mock `fetch` → `200 { data: ... }` → `applyCoupon` called), `400 COUPON_INVALID` → inline error shown, `500` → generic error shown, Remove button clears context, Enter key submits, input is disabled when coupon already applied. Wraps under a real `CheckoutProvider` (not a mocked context — integration shape is part of the contract).
   - [src/components/checkout/PlanCard.test.tsx](src/components/checkout/PlanCard.test.tsx) — renders full price + savings when no coupon, renders strikethrough + discounted price when a 50%-off coupon is applied, renders `First charge on ...` when 100% repeating coupon applied (mock clock with `vi.useFakeTimers()` to get a deterministic date string), renders `Free with this coupon` when 100%-off `forever`, savings label is hidden when coupon applied on yearly.
   - [src/components/checkout/PlanCta.test.tsx](src/components/checkout/PlanCta.test.tsx) is **extended** — new cases: wraps in `CheckoutProvider` with an applied coupon, verifies the `fetch` body includes `couponCode`, verifies `400 COUPON_INVALID` calls `clearCoupon()` and renders the coupon-specific error copy.
   - [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) is **extended** — new cases: valid `couponCode` path → Stripe called with `discounts: [{ promotion_code: 'promo_xxx' }]` AND `allow_promotion_codes` is OMITTED from the args, invalid `couponCode` → `400 COUPON_INVALID`, no-`couponCode` path still sends `allow_promotion_codes: true` (regression guard on Story 3.2 behavior).
   - [src/app/pricing/page.test.tsx](src/app/pricing/page.test.tsx) is **extended** — new assertions: `<CouponInput />` is rendered, the `?coupon=CODE` search param triggers a server-side `previewCoupon` call (mock it), initialCoupon flows into the provider so the grid renders discounted prices on first paint, and `previewCoupon` throwing does NOT crash the render (graceful null fallback).
   **And** all tests pass. Full-suite `npx vitest run` reports **> 191 passing** with zero failures (target: roughly **~220**; exact count is advisory, the floor is the regression guard)
   **And** `npm run build` passes; the new `/api/checkout/coupon` route appears as `ƒ (Dynamic)` Node runtime in the build output alongside `/api/checkout/session`
   **And** `npm run lint` shows zero errors and zero new warnings (Story 3.2 ended at 0/0 — maintain it)

10. **Given** env var rules from architecture.md:265-273 and the `.env.example` tripwire test
    **When** this story lands
    **Then** **NO new environment variables are added**. Coupons live in Stripe's system and are queried at runtime via the already-configured `STRIPE_SECRET_KEY`. `.env.example` is untouched. [src/lib/env.test.ts](src/lib/env.test.ts) is untouched. If a reviewer is tempted to add a `STRIPE_COUPON_PREFIX` or similar — don't. The coupon model is server-config-free by design.

## Tasks / Subtasks

- [x] Task 1: Create the CheckoutContext provider (AC: #1)
  - [x] 1.1 Create [src/components/checkout/CheckoutContext.tsx](src/components/checkout/CheckoutContext.tsx) with `'use client'`, `AppliedCoupon` type, `CheckoutProvider`, `useCheckout` hook, throw-outside-provider guard, `initialCoupon?` prop
  - [x] 1.2 Export named exports (no default export — matches project convention)
  - [x] 1.3 Unit test not required for pure context plumbing; indirect coverage via CouponInput + PlanCard tests is sufficient

- [x] Task 2: Build the server-side coupon lookup helper (AC: #2, #7)
  - [x] 2.1 Create [src/lib/stripe/coupons.ts](src/lib/stripe/coupons.ts) with `import 'server-only'`
  - [x] 2.2 Export `previewCoupon(code: string): Promise<{ coupon: AppliedCoupon; promotionCodeId: string } | null>` — single source of truth for BOTH the API route (AC #2) and the session route (AC #7) and the page-level preview (AC #6)
  - [x] 2.3 Inside `previewCoupon`, call `getStripe().promotionCodes.list({ code, active: true, limit: 1, expand: ['data.coupon'] })`; handle empty list, inactive, expired → return `null`; on a valid hit, map to the normalized `AppliedCoupon` shape
  - [x] 2.4 Let Stripe API errors propagate (throw) — the callers decide how to map them to HTTP responses. The page-level caller catches and falls back; the API route catches and returns `COUPON_LOOKUP_FAILED`.
  - [x] 2.5 Write [src/lib/stripe/coupons.test.ts](src/lib/stripe/coupons.test.ts) — mock `stripe` with the same plain-function constructor pattern as `session/route.test.ts`

- [x] Task 3: Build the coupon validation API route (AC: #2)
  - [x] 3.1 Create [src/app/api/checkout/coupon/route.ts](src/app/api/checkout/coupon/route.ts) with `runtime = 'nodejs'`, Zod body, envelope helper (extract the `envelopeError` helper from `session/route.ts` to [src/app/api/checkout/_shared.ts](src/app/api/checkout/_shared.ts) if you notice the duplication — otherwise inline a copy; the `_shared.ts` extraction is a small optional refactor and ONLY worthwhile if both routes converge on 2+ helpers)
  - [x] 3.2 Call `previewCoupon(code)`; on `null` → `400 COUPON_INVALID`; on thrown Stripe error → `500 COUPON_LOOKUP_FAILED`
  - [x] 3.3 Preserve the original user input casing in the response (return `{ code: input.trim(), ...fromStripe }`, NOT `{ code: stripeResponse.code }`)
  - [x] 3.4 Write [src/app/api/checkout/coupon/route.test.ts](src/app/api/checkout/coupon/route.test.ts) covering all branches in AC #2

- [x] Task 4: Build the discount computation helper (AC: #4)
  - [x] 4.1 Create [src/lib/pricing/discount.ts](src/lib/pricing/discount.ts) with `computeDiscountedPrice` and a local `addMonthsUTC` helper (pure, ~10 lines — copy-safe Jan-31 → Feb-28 clamp logic: if the target day exceeds the target month's last day, clamp to the last day)
  - [x] 4.2 Export the `AppliedCoupon` type from here too — NO, keep the type export in `CheckoutContext.tsx` to avoid a circular import; `discount.ts` imports it as a type-only import (`import type { AppliedCoupon } from '@/components/checkout/CheckoutContext'`)
  - [x] 4.3 Write [src/lib/pricing/discount.test.ts](src/lib/pricing/discount.test.ts) with the five cases from AC #4

- [x] Task 5: Build the CouponInput component (AC: #3)
  - [x] 5.1 Create [src/components/checkout/CouponInput.tsx](src/components/checkout/CouponInput.tsx) with `'use client'`
  - [x] 5.2 Wire `<form onSubmit>` for Enter-to-submit semantics, local `pending`/`error`/`success` state, `fetch('/api/checkout/coupon', ...)`, call `applyCoupon` / `clearCoupon` via `useCheckout`
  - [x] 5.3 Style with Tailwind tokens already in use: `bg-card`, `border-border`, `text-foreground`, `text-muted-foreground`, `text-destructive`, `focus-visible:ring-ring`, `focus-visible:ring-offset-background`
  - [x] 5.4 Render `Remove` button when `coupon !== null`, swapping out the Apply button (mutually exclusive — see AC #3)
  - [x] 5.5 Write [src/components/checkout/CouponInput.test.tsx](src/components/checkout/CouponInput.test.tsx) with the cases from AC #9

- [x] Task 6: Extract and extend PlanCard as a client component (AC: #5)
  - [x] 6.1 Create [src/components/checkout/PlanCard.tsx](src/components/checkout/PlanCard.tsx) with `'use client'`, import the existing `PlanCta`, `computeDiscountedPrice`, `useCheckout`, `formatEuro`, `getPeriodLabel`, `getYearlySavings`
  - [x] 6.2 Copy the existing inline `PlanCard` JSX out of `page.tsx` verbatim first, then add the coupon-aware branches: strikethrough original price, discounted price, `First charge on ...` OR `Free with this coupon`, suppressed savings label
  - [x] 6.3 Delete the inline `PlanCard` function in [src/app/pricing/page.tsx](src/app/pricing/page.tsx); replace the `<PlanCard plan={...} />` references with imports from the new file
  - [x] 6.4 Write [src/components/checkout/PlanCard.test.tsx](src/components/checkout/PlanCard.test.tsx) per AC #9

- [x] Task 7: Wire the pricing page with CheckoutProvider and URL-param preview (AC: #6)
  - [x] 7.1 Widen `searchParams` typing in [src/app/pricing/page.tsx](src/app/pricing/page.tsx) to `Promise<{ checkout?: string; coupon?: string }>`
  - [x] 7.2 Import `previewCoupon` from `@/lib/stripe/coupons`; if `resolved.coupon` is non-empty, `await previewCoupon(resolved.coupon.trim()).catch(err => { console.warn('[pricing] coupon preview failed', err); return null })`
  - [x] 7.3 Wrap the plan grid section's children in `<CheckoutProvider initialCoupon={previewedCoupon ?? undefined}>`
  - [x] 7.4 Insert `<CouponInput />` between the section heading and the grid (or between the canceled banner and the grid — whichever preserves the existing banner position)
  - [x] 7.5 Update [src/app/pricing/page.test.tsx](src/app/pricing/page.test.tsx) per AC #9: mock `previewCoupon`, assert `CouponInput` renders, assert `?coupon=X` path renders discounted grid, assert throw path falls through to the default render

- [x] Task 8: Extend the checkout session route (AC: #7)
  - [x] 8.1 Widen the Zod body schema in [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts) to include `couponCode?: string`
  - [x] 8.2 On `couponCode` present: call `previewCoupon`, on `null` → `400 COUPON_INVALID`, on success extract `promotionCodeId`
  - [x] 8.3 In the `stripe.checkout.sessions.create` payload, when `couponCode` is present, build the args object WITHOUT `allow_promotion_codes` AND WITH `discounts: [{ promotion_code: promotionCodeId }]`; when absent, keep the Story 3.2 shape exactly
  - [x] 8.4 Preserve the 500 fallback envelope for any thrown Stripe error (unchanged from Story 3.2)
  - [x] 8.5 Extend [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) per AC #9 — regression-guard the no-coupon path first, then add the coupon cases

- [x] Task 9: Extend PlanCta for the coupon-aware flow (AC: #8)
  - [x] 9.1 Add `useCheckout()` call to [src/components/checkout/PlanCta.tsx](src/components/checkout/PlanCta.tsx); spread `couponCode` into the body when `coupon !== null`
  - [x] 9.2 Branch on `error.code === 'COUPON_INVALID'` in the response handler: call `clearCoupon()`, set a coupon-specific error message
  - [x] 9.3 Extend [src/components/checkout/PlanCta.test.tsx](src/components/checkout/PlanCta.test.tsx) — wrap the existing tests in a `CheckoutProvider` (no applied coupon) for regression parity, then add the two new coupon-applied cases

- [x] Task 10: Regression and verification (AC: #9)
  - [x] 10.1 `npx vitest run` — full suite green, new count > 191
  - [x] 10.2 `npm run build` — both new routes (`/api/checkout/coupon`, `/api/checkout/session`) listed as Node dynamic
  - [x] 10.3 `npm run lint` — 0 errors, 0 warnings
  - [x] 10.4 Manual smoke (defer to reviewer with their `.env.local` test keys; document in Completion Notes): visit `/pricing?coupon=KNOWN_TEST_CODE` → verify the coupon is pre-applied → verify Monthly card shows strikethrough price + `First charge on ...` → click Subscribe → verify Stripe Checkout shows the discount line → cancel → verify `/pricing?checkout=canceled` still works → apply an invalid coupon → verify inline error → apply a valid coupon → remove it → verify return to full-price UI

## Dev Notes

### COUPON_INVALID vs COUPON_LOOKUP_FAILED decoding

This is the single subtle design call in the story. The architecture boils down to:

| Stripe outcome                                | `previewCoupon` returns | `/api/checkout/coupon` response | `/api/checkout/session` response |
| --------------------------------------------- | ----------------------- | ------------------------------- | -------------------------------- |
| Code resolves to active valid coupon          | object                  | `200 { data }`                  | `200 { data: { url } }`          |
| Code resolves but inactive/expired/empty list | `null`                  | `400 COUPON_INVALID`            | `400 COUPON_INVALID`             |
| Stripe API throws (network, auth, 5xx)        | throws                  | `500 COUPON_LOOKUP_FAILED`      | `500 CHECKOUT_FAILED`            |
| `page.tsx` server-side preview throws         | n/a                     | n/a                             | falls through to default render  |

Key insight: `previewCoupon` returns `null` for "user gave us a bad code" and THROWS for "Stripe is unreachable or misbehaving". This lets callers pick the right status code without string-matching error messages. The API route uses a try/catch; the page-level caller uses `.catch(() => null)` because for SSR a silent fallback is strictly better than a 500 (the coupon input still works client-side).

The session route ({AC #7}) deliberately does NOT distinguish `COUPON_INVALID` from `CHECKOUT_FAILED` at the 5xx boundary — if the coupon was valid enough to pass the API route preview but fails re-resolution during `sessions.create`, something is racy/wrong and the generic `CHECKOUT_FAILED` envelope is appropriate. The 4xx `COUPON_INVALID` branch in the session route is ONLY for the revalidation step, not for downstream Stripe errors.

### Why the API route does NOT return the `promotionCodeId` to the client

You might be tempted to put `promotionCodeId` in the `/api/checkout/coupon` response and thread it through the client so the session route doesn't have to re-resolve. **Don't.** Three reasons:

1. **Trust boundary.** The client must never be the source of truth for a Stripe-internal ID that gates a discount. A malicious client could swap in any `promo_xxx` and get a 100%-off subscription. Server-side revalidation on `/api/checkout/session` is non-negotiable.
2. **Cache invalidation.** Between "coupon preview" and "click Subscribe", the coupon could expire or be deactivated. Re-resolving catches this and hands the user a clean `COUPON_INVALID` + `clearCoupon()` reset rather than a cryptic Stripe error.
3. **Network cost is trivial.** `promotionCodes.list` is a cheap Stripe call; doing it twice per flow (preview + checkout) is fine at MVP scale. If it ever matters, a 60-second in-memory cache on `previewCoupon(code)` is a one-line follow-up.

### Why the CouponInput does NOT live inside each PlanCard

One coupon per checkout session, shared across both plan cards. Putting the input inside `PlanCard` would either (a) duplicate the UI, (b) force the user to pick a plan before entering a coupon, or (c) synchronize two inputs via context anyway. A single `CouponInput` above the grid is simpler, matches the "coupon-first flow" from ux-design-specification.md:62, and maps cleanly to the Discord-link auto-apply journey.

### Why `CheckoutProvider` lives in `components/checkout/` instead of `hooks/` or `contexts/`

Two reasons: (1) the architecture's directory tree (architecture.md:523-527) explicitly puts all checkout-surface components under `src/components/checkout/` including plumbing like `CheckoutForm.tsx`; (2) `src/hooks/` currently holds only `useAuth.ts`, which is a global concern cross-cutting the entire app. The coupon context is checkout-feature-local and should stay colocated.

### Auto-apply from URL param

The UX spec (ux-design-specification.md:471, 490) treats `?coupon=COACH2FREE` auto-application as the primary conversion journey ("Discord link → pricing page with coupon already applied"). Epics.md Story 3.3 AC does NOT explicitly mention this — but implementing it is cheap (one `previewCoupon` call at the Server Component layer) and skipping it would leave the flagship conversion flow broken. Included in AC #6. If a reviewer flags it as scope creep: the cost is ~15 lines in `page.tsx` + one test case, and it's the literal journey map from the UX spec.

### Why `addMonthsUTC` is inlined instead of adding `date-fns`

`date-fns` is ~75kb on disk for a 10-line helper with one call site. `addMonths` has a well-known clamp edge case (Jan 31 → Feb 28/29) that's ~5 lines to get right:

```ts
function addMonthsUTC(date: Date, months: number): Date {
  const d = new Date(date)
  const targetMonth = d.getUTCMonth() + months
  d.setUTCDate(1) // avoid rollover before setting month
  d.setUTCMonth(targetMonth)
  const lastDay = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate()
  d.setUTCDate(Math.min(date.getUTCDate(), lastDay))
  return d
}
```

Write it, test the Jan-31 case, move on. If a future story needs more date math, extract to `lib/date/` and add a library then.

### Previous Story Intelligence (carried from Stories 3.1–3.2)

1. **Next.js 16 App Router** — Server Components by default; only the components that call hooks or hold interactive state carry `'use client'`. Read `node_modules/next/dist/docs/` before touching any App Router API you haven't seen in the 3.1/3.2 diffs. `searchParams` is `Promise<...>` in Next 16 (confirmed in the 3.2 merge).
2. **Stripe mock in tests** — `vi.mock('stripe', ...)` with a plain `function Stripe(this: ...)` constructor, NOT an arrow function or class. The 3.2 debug log captures why: Vitest v4 warns and happy-paths fail when the mock is not `new`-able.
3. **Envelope shape** — `{ data: ... }` on 2xx, `{ error: { code, message } }` on 4xx/5xx. Codes are `SCREAMING_SNAKE_CASE`. Do not invent a new shape.
4. **Zod v4 import** — `from 'zod/v4'`, project-wide.
5. **Session-cookie reading** — use `request.headers.get('cookie')` parsing (pattern from `session/route.ts`), not `next/headers` `cookies()`. Consistent with Story 3.2.
6. **shadcn/ui = Base UI, not Radix.** No `asChild`, no `Slot`. Plain elements with className composition.
7. **Token set** — `bg-card`, `border-border`, `text-foreground`, `text-muted-foreground`, `text-primary`, `text-destructive`, `focus-visible:ring-ring`, `focus-visible:ring-offset-background`. `text-destructive` is confirmed in the theme by Story 3.2.
8. **Touch targets** — `min-h-11 min-w-11` = 44×44.
9. **Pre-commit hook** — Prettier + ESLint on staged files. Do NOT bypass. Prettier config: `{ semi: false, singleQuote: true, trailingComma: 'all', printWidth: 100, tabWidth: 2 }`.
10. **Commit scope** — `feat(checkout): add coupon code support (Story 3.3)` per architecture.md:613 + architecture.md:439 precedent literally spelling it out.
11. **Test baseline** — 191 / 191 at story start. Do not regress. Target ~220 on completion.
12. **Pre-existing CookieBanner.tsx warning** — was resolved during Story 3.2 (0/0 lint output). Do NOT re-introduce.
13. **ctaPrimaryClass** — use it, do not redefine.
14. **`allow_promotion_codes` + `discounts` are mutually exclusive** at the Stripe API layer. Story 3.2 passes `allow_promotion_codes: true`; this story ONLY drops it when a server-validated discount is attached. The no-coupon path keeps the flag.
15. **Server-only enforcement** — `import 'server-only'` at the top of `lib/stripe/coupons.ts` AND `lib/stripe/server.ts`. The coupon route imports from `coupons.ts` from the server side; nothing in the client bundle should resolve either file.

### Stripe API specifics — promotion codes and coupons

Stripe separates **coupons** (internal, reusable discount config: `percent_off` / `amount_off`, `duration`, `duration_in_months`) from **promotion codes** (customer-facing strings like `COACH2FREE` that reference a coupon and add restrictions like `active`, `expires_at`, `max_redemptions`, `restrictions.first_time_transaction`).

- The user types a **promotion code**, never a raw coupon ID.
- `stripe.promotionCodes.list({ code, active: true, limit: 1, expand: ['data.coupon'] })` is the canonical lookup. `expand: ['data.coupon']` inlines the referenced coupon object so you don't need a second `stripe.coupons.retrieve` call.
- `data[0].active` AND `data[0].coupon.valid` are the flags to check. A code can be `active: true` but reference an invalidated coupon (e.g., redemption limit hit) — check both. Stripe's `promotionCodes.list` with `active: true` already filters the first flag; the `coupon.valid` check is belt-and-braces.
- `expires_at` is a Unix timestamp in seconds. `Date.now() / 1000 > expires_at` ⇒ expired.
- When passing to `checkout.sessions.create`, use `discounts: [{ promotion_code: 'promo_xxx' }]`. `discounts[].coupon` is the alternative but requires the coupon ID directly — using `promotion_code` is more idiomatic and matches what Stripe's dashboard surfaces.
- `restrictions.first_time_transaction: true` coupons will silently fail at checkout if the user's Stripe customer already has a successful charge — there is NO pre-validation API for this. For MVP, assume all coupons at launch are non-restricted, and document in Completion Notes if the reviewer hits this edge case.

### Anti-Patterns to Avoid

- Do NOT trust `couponCode` from the client without server-side revalidation in `/api/checkout/session`.
- Do NOT return the Stripe `promotionCodeId` from `/api/checkout/coupon` — the client doesn't need it and exposing it weakens the trust boundary.
- Do NOT pass BOTH `allow_promotion_codes: true` AND `discounts: [...]` to `checkout.sessions.create` — Stripe rejects the combination.
- Do NOT call `previewCoupon` or any Stripe API from a Client Component — always through a Route Handler or Server Component.
- Do NOT use `coupon.amount_off` values as if they were in the plan's currency without checking — Stripe stores `amount_off` in the coupon's currency. For this app, single-currency EUR means the check is a no-op in practice, but if future multi-currency comes, this is the bug. Flag it in Completion Notes if you notice it.
- Do NOT fetch the app's own API from `page.tsx`. Call the shared helper (`previewCoupon`) directly. Internal HTTP self-calls from Server Components are a well-known Next.js anti-pattern.
- Do NOT convert `amount_off` cents to euros in the API response — keep the whole pipeline in cents, format only at the UI edge via `formatEuro`.
- Do NOT add a retry button to `CouponInput` for the `COUPON_LOOKUP_FAILED` path. The Apply button re-enables; the user retries by clicking Apply again. Simpler, less state.
- Do NOT split `CouponInput` into a controlled input + separate button component. One file, one form, one submit handler.
- Do NOT add a debounce on the coupon input. The user explicitly clicks Apply (or presses Enter); on-change validation invites rate-limit trouble and duplicate Stripe reads.
- Do NOT add `date-fns` or `dayjs`. The inline `addMonthsUTC` is the right call at this scale.
- Do NOT forget to mock `previewCoupon` in the page test — if it's unmocked, the server-side render hits the real Stripe API at test time and the test either fails or slows the suite.
- Do NOT auto-apply a coupon from the URL if the user has manually applied a different one (N/A on first load — the URL param sets `initialCoupon` and the user's subsequent Apply/Remove overrides it via context, which is the correct behavior). Make sure no effect in `CheckoutProvider` re-syncs `initialCoupon` after mount.
- Do NOT modify `src/proxy.ts` — `/api/checkout/coupon` is public (AC #2 rationale), auth is not required, and the proxy matcher stays untouched.
- Do NOT add new Tailwind breakpoints (`md:` is the only one).
- Do NOT extract `envelopeError` to a new `_shared.ts` unless both routes end up sharing 2+ helpers. One-off duplication of a 3-line helper is fine.

### Naming Conventions (from Architecture)

- **Routes:** `src/app/api/checkout/coupon/route.ts`
- **Feature components:** `src/components/checkout/CouponInput.tsx`, `src/components/checkout/PlanCard.tsx`, `src/components/checkout/CheckoutContext.tsx` (PascalCase files for components, PascalCase exported symbols)
- **Server-only lib:** `src/lib/stripe/coupons.ts` (matches `src/lib/stripe/server.ts` pattern)
- **Pricing helper:** `src/lib/pricing/discount.ts` (matches `src/lib/pricing/plans.ts` pattern)
- **Error codes:** `SCREAMING_SNAKE_CASE` — `COUPON_INVALID`, `COUPON_LOOKUP_FAILED`, `INVALID_REQUEST` (reused), `CHECKOUT_FAILED` (reused)
- **Type names:** `AppliedCoupon` (exported from `CheckoutContext.tsx`)

### Import Order Convention

1. React/Next.js imports (including `'use client'` pragma on the first line, above imports)
2. Third-party libraries (`stripe`, `zod/v4`)
3. `@/` project imports
4. Relative imports
5. Type-only imports last

(Unchanged from Stories 3.1 / 3.2 — Prettier + ESLint enforce.)

### Project Structure Notes

- `src/components/checkout/` — currently holds `PlanCta.tsx` + test; this story adds `CheckoutContext.tsx`, `CouponInput.tsx` (+ test), `PlanCard.tsx` (+ test), and a test for `CheckoutContext` IF the provider grows past trivial plumbing (it shouldn't — skip the test and rely on indirect coverage).
- `src/app/api/checkout/` — currently holds `session/`; this story adds `coupon/`.
- `src/lib/stripe/` — currently holds `server.ts`; this story adds `coupons.ts` (+ test).
- `src/lib/pricing/` — currently holds `plans.ts` (+ test); this story adds `discount.ts` (+ test).
- `src/app/pricing/page.tsx` — the inline `PlanCard` function is deleted; the page becomes shorter, the plan card lives in its own file.
- No Firestore writes, no Firestore rules changes, no schema changes, no new env vars.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 3 Story 3.3 (epics.md:344-359)]
- [Source: _bmad-output/planning-artifacts/epics.md — FR11, FR12 (epics.md:38-39, 113-114)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR11, FR12 definitions (prd.md:460-461)]
- [Source: _bmad-output/planning-artifacts/architecture.md — checkout folder + CouponInput.tsx placement (architecture.md:525)]
- [Source: _bmad-output/planning-artifacts/architecture.md — API envelope convention (architecture.md:345-351)]
- [Source: _bmad-output/planning-artifacts/architecture.md — commit scope for coupon work (architecture.md:439)]
- [Source: _bmad-output/planning-artifacts/architecture.md — API key security, server-only rules (architecture.md:265-273)]
- [Source: _bmad-output/planning-artifacts/architecture.md — FR8-12 → checkout feature mapping (architecture.md:699)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Coupon-first flow journey (ux-design-specification.md:62, 95, 104, 465-493)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Coupon auto-apply from URL param (ux-design-specification.md:490)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Coupon input field styling (ux-design-specification.md:617, 701)]
- [Source: _bmad-output/implementation-artifacts/3-2-stripe-checkout-for-monthly-and-yearly-subscriptions.md — Stripe mock pattern, `allow_promotion_codes: true` pre-seed, envelope shape, `useAuth`/`useRouter` patterns, test baseline 191]
- [Source: _bmad-output/implementation-artifacts/3-1-pricing-page-with-plan-display.md — `ctaPrimaryClass` extraction, pricing page scaffolding, Next 16 `searchParams` promise]
- [Source: src/app/api/checkout/session/route.ts — envelope helper, session cookie reading, Zod body pattern, Stripe session create args]
- [Source: src/components/checkout/PlanCta.tsx — fetch + `window.location.assign` redirect, error state pattern]
- [Source: src/app/pricing/page.tsx — existing inline `PlanCard` structure, canceled banner position, `searchParams` pattern]
- [Source: src/lib/pricing/plans.ts — `Plan` type, `PLAN_BY_ID`, `formatEuro`, `getPeriodLabel`, `getYearlySavings`, `getCtaLabel`]
- [Source: src/lib/stripe/server.ts — `getStripe()` singleton, `getPlanPriceId` helper]
- [Source: src/hooks/useAuth.ts — `useAuth` hook shape; `useCheckout` should mirror the throw-outside-provider guard]
- [Source: AGENTS.md — Next.js 16 breaking changes, read `node_modules/next/dist/docs/` before App Router changes]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (Claude Opus 4.6, 1M context)

### Debug Log References

- Stripe SDK v22 nests the coupon under `PromotionCode.promotion.coupon` (NOT `PromotionCode.coupon` directly as the story drafted). The `expand` parameter was changed from `data.coupon` to `data.promotion.coupon`, and the resolution code reads `promo.promotion.coupon` then guards on object-vs-string. Test fixtures updated to mirror the wrapped shape.
- Initial parallel `vitest run` reproduced a global `Cannot read properties of undefined (reading 'config')` flake across all 32 test files, but a single-file run and `--no-file-parallelism` ran clean. Pre-existing concurrency flake in the repo, NOT introduced by this story. Final regression executed with `--no-file-parallelism`.

### Completion Notes List

- All 10 tasks complete. Test suite: 238 / 238 passing (baseline was 191; +47 new). `npm run build` succeeds with `/api/checkout/coupon` and `/api/checkout/session` both listed as ƒ Dynamic Node routes. `npm run lint` is clean (0 errors / 0 warnings).
- `previewCoupon` is the single source of truth for coupon resolution and is consumed by the public preview API route, the session-create route, and the SSR pricing page. It returns `null` for "user error" cases (empty list / inactive / expired / invalid coupon) and throws for "Stripe is unreachable", letting each caller pick the right HTTP status. Promotion code ID is intentionally NOT returned to the client — the session route always re-resolves server-side.
- `CheckoutContext` is the single coupon state container; both `CouponInput` and `PlanCta` consume it via `useCheckout()`. The provider accepts `initialCoupon` so the SSR `?coupon=CODE` auto-apply path requires no client re-fetch.
- `PlanCard` was extracted out of `pricing/page.tsx` into `src/components/checkout/PlanCard.tsx` as a Client Component (because it now calls `useCheckout()`); the page itself stays a Server Component. Strikethrough original price, discounted price, deferred-charge label, and Free-with-coupon label render only when a coupon is applied; the yearly savings label is suppressed when a coupon is active.
- `discount.ts` includes a tiny `addMonthsUTC` helper with a Jan-31 → Feb-28 clamp, validated by a fake-timer unit test. No date library was added.
- The Story 3.2 `allow_promotion_codes: true` flag is preserved on the no-coupon path and dropped (in favor of `discounts: [{ promotion_code: ... }]`) when a server-validated coupon is attached, satisfying the Stripe API mutual-exclusion constraint.
- No new env vars added; `.env.example` and `src/lib/env.test.ts` untouched, per AC #10.

### File List

- src/components/checkout/CheckoutContext.tsx (new)
- src/components/checkout/CouponInput.tsx (new)
- src/components/checkout/CouponInput.test.tsx (new)
- src/components/checkout/PlanCard.tsx (new)
- src/components/checkout/PlanCard.test.tsx (new)
- src/components/checkout/PlanCta.tsx (modified — `useCheckout` integration, `couponCode` body, `COUPON_INVALID` branch)
- src/components/checkout/PlanCta.test.tsx (modified — wraps in `CheckoutProvider`, two new coupon cases)
- src/lib/pricing/discount.ts (new)
- src/lib/pricing/discount.test.ts (new)
- src/lib/stripe/coupons.ts (new)
- src/lib/stripe/coupons.test.ts (new)
- src/app/api/checkout/coupon/route.ts (new)
- src/app/api/checkout/coupon/route.test.ts (new)
- src/app/api/checkout/session/route.ts (modified — Zod `couponCode`, `previewCoupon` revalidation, `discounts` payload, conditional `allow_promotion_codes`)
- src/app/api/checkout/session/route.test.ts (modified — three new cases for coupon path)
- src/app/pricing/page.tsx (modified — `CheckoutProvider` wiring, SSR `previewCoupon` for `?coupon=` param, `CouponInput` insertion, inline `PlanCard` deleted)
- src/app/pricing/page.test.tsx (modified — `previewCoupon` mock, two new cases for coupon path + graceful fallback)
- _bmad-output/implementation-artifacts/sprint-status.yaml (status flip ready-for-dev → in-progress → review)

### Change Log

| Date       | Version | Change                                                                                                         |
| ---------- | ------- | -------------------------------------------------------------------------------------------------------------- |
| 2026-04-14 | 0.1     | Story drafted (ready-for-dev) — coupon validation API, CouponInput client component, CheckoutContext provider, PlanCard extraction with discount display, session route coupon path, URL-param auto-apply |
| 2026-04-14 | 1.0     | Story implemented and marked review — all 10 tasks complete, 238/238 tests passing (+47), build green with both checkout routes ƒ Dynamic, lint 0/0. Stripe v22 SDK promotion-code shape change (`promo.promotion.coupon`) discovered during build type-check and corrected. |
| 2026-04-14 | 1.1     | Code review fixes applied — added missing session-route throw-path test, added `amount_off: 0` malformed-coupon rejection test, tightened `previewCoupon` to reject `percent_off`/`amount_off` ≤ 0, aligned `computeDiscountedPrice` to strict `=== 100` per AC #4, typed `initialCoupon` explicitly in `page.tsx`, switched `CheckoutContext` to classic `.Provider` syntax for React 16+ compat, added `cache: 'no-store'` and pending affordance (`aria-busy`, "Applying…" label) to `CouponInput`. Test suite now 240/240. |
