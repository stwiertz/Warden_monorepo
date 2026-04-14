# Story 3.2: Stripe Checkout for Monthly and Yearly Subscriptions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an authenticated user,
I want to subscribe to a monthly or yearly plan via Stripe Checkout from the pricing page,
So that I can pay for Warden's premium features through Stripe's hosted, PCI-compliant flow.

## Acceptance Criteria

1. **Given** the Stripe server SDK is initialized at [src/lib/stripe/server.ts](src/lib/stripe/server.ts) using a lazy, server-only singleton (imports `server-only`, reads `STRIPE_SECRET_KEY` from `process.env`, pins `apiVersion` to the latest stable version the installed `stripe` package declares)
   **When** a module imports it
   **Then** the client is created only once per Node process, never bundled into client code, and throws a clear error if `STRIPE_SECRET_KEY` is missing at call time (not at import time — tests must be able to import without the env var set)
   **And** `stripe` is added to `dependencies` in [package.json](package.json); NO `@stripe/stripe-js` package is installed in this story (the checkout redirect uses server-issued `session.url` + `window.location.assign`, not `stripe.redirectToCheckout()`)

2. **Given** the centralized plan constants in [src/lib/pricing/plans.ts](src/lib/pricing/plans.ts) (authored in Story 3.1)
   **When** this story extends them
   **Then** each `Plan` type gains a `stripePriceEnvKey` field whose value is the **name of the environment variable** that holds the Stripe Price ID for that plan (NOT the Price ID itself — keeping Price IDs out of source is mandatory per architecture.md:718 "API key security")
   **And** `PLAN_MONTHLY.stripePriceEnvKey = 'STRIPE_PRICE_MONTHLY'` and `PLAN_YEARLY.stripePriceEnvKey = 'STRIPE_PRICE_YEARLY'`
   **And** a server-only helper `getPlanPriceId(plan: Plan): string` lives in [src/lib/stripe/server.ts](src/lib/stripe/server.ts) (NOT in `plans.ts` — `plans.ts` stays client-safe so the pricing page and any future client code can keep importing from it) that reads `process.env[plan.stripePriceEnvKey]` and throws a structured error if missing
   **And** `src/lib/pricing/plans.test.ts` is extended with one test asserting each plan has a non-empty `stripePriceEnvKey`

3. **Given** a new route handler at [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts)
   **When** it receives a `POST` request
   **Then** the handler runs on the **Node runtime** (the file exports `export const runtime = 'nodejs'` — the `stripe` Node SDK requires Node APIs and MUST NOT be used on the Edge runtime per the package's docs)
   **And** it validates the JSON body with a Zod schema `{ planId: z.enum(['monthly', 'yearly']) }` using the project's `from 'zod/v4'` import convention
   **And** on invalid body, returns `400` with the project's standard envelope `{ error: { code: 'INVALID_REQUEST', message: '...' } }` (same shape as [src/app/api/auth/session/route.ts](src/app/api/auth/session/route.ts))
   **And** it reads the `session` cookie (constant name `SESSION_COOKIE_NAME = 'session'` — extract it to a shared module if duplication becomes painful, otherwise mirror the literal used in [src/app/api/auth/session/route.ts:6](src/app/api/auth/session/route.ts#L6) and [src/proxy.ts:5](src/proxy.ts#L5)) and verifies it with `adminAuth.verifySessionCookie(cookie, true)` (`checkRevoked: true`)
   **And** on missing/invalid session, returns `401` with `{ error: { code: 'UNAUTHENTICATED', message: 'Sign in required' } }` — no redirect (this is an API, not a navigation)
   **And** on success, calls `stripe.checkout.sessions.create` with:
   - `mode: 'subscription'`
   - `line_items: [{ price: <resolved price ID>, quantity: 1 }]`
   - `success_url: \`${APP_URL}/dashboard?checkout=success&session_id={CHECKOUT_SESSION_ID}\``
   - `cancel_url: \`${APP_URL}/pricing?checkout=canceled\``
   - `client_reference_id: decodedCookie.uid`
   - `customer_email: decodedCookie.email` (from the verified session cookie claim, not the request body)
   - `metadata: { firebase_uid: decodedCookie.uid, plan_id: planId }` — the webhook in Story 4.2 will read these to write `users/{uid}` (see Boundary Note below)
   - `allow_promotion_codes: true` (leaves room for Story 3.3's coupon UI without re-engineering)
   **And** returns `200` with `{ data: { url: session.url } }` (NOT `{ data: { sessionId, url } }` — we only need `url` for the client-side redirect; keep the envelope minimal)
   **And** `APP_URL` comes from `process.env.NEXT_PUBLIC_APP_URL` with a defensive fallback to `new URL(request.url).origin` — both computed server-side, no client leakage

4. **Given** the pricing page CTA was inert in Story 3.1
   **When** this story lands
   **Then** a new client component [src/components/checkout/PlanCta.tsx](src/components/checkout/PlanCta.tsx) replaces the inline `<button disabled>` inside [src/app/pricing/page.tsx](src/app/pricing/page.tsx)'s `PlanCard` — the page itself remains a Server Component; only `PlanCta` carries `'use client'`
   **And** `PlanCta` accepts `{ plan: Plan }` and renders a live button with the same copy (`Subscribe monthly` / `Subscribe yearly`) and the same `ctaPrimaryClass` styling from [src/components/ui/cta-class.ts](src/components/ui/cta-class.ts) (NOT `ctaPrimaryDisabledClass` — the button is no longer disabled)
   **And** on click, if `useAuth()` returns `{ user: null, loading: false }`, the component navigates to `/auth/sign-in?next=/pricing` using `useRouter().push` — this matches the `next` query convention already established by [src/proxy.ts:15](src/proxy.ts#L15); after sign-in the existing session flow redirects to `/dashboard`, from which the user re-navigates to `/pricing` to retry (a one-click resume is explicitly out of scope — adding it would require state persistence and belongs to a later UX polish story)
   **And** if `{ user, loading: false }`, the component `POST`s to `/api/checkout/session` with `{ planId: plan.id }`, disables the button while pending, and on `200` calls `window.location.assign(data.url)` (full navigation, NOT `router.push` — Stripe's hosted page is outside the Next.js app)
   **And** on any non-2xx response or network error, the button re-enables and an inline error message (`role="alert"`, `text-destructive` token — add the token to the project if missing; Tailwind v4 shadcn theme already defines it per [src/components/ui/alert.tsx](src/components/ui/alert.tsx)) is rendered immediately beneath the button with copy `Something went wrong — please try again.`
   **And** while `loading: true` (auth still resolving on mount), the button is rendered disabled to prevent a double-click race
   **And** the button keeps `type="button"`, `min-h-11 min-w-11`, and the `focus-visible:ring-ring focus-visible:ring-offset-background` pattern unchanged

5. **Given** a user returning to the dashboard from a successful Stripe Checkout
   **When** the redirect lands on `/dashboard?checkout=success&session_id=...`
   **Then** [src/app/dashboard/page.tsx](src/app/dashboard/page.tsx) reads the `checkout` query parameter using `useSearchParams()` (the page is already a Client Component) and renders a **dismissible success alert banner** at the top of the dashboard content area with copy `Subscription started — welcome to Warden!` plus a short hint `It may take a few seconds for your plan to appear.` — the hint exists specifically because the `users/{uid}` Firestore document is written by the webhook in Story 4.2, not inline here (see Boundary Note)
   **And** the banner uses the existing [src/components/ui/alert.tsx](src/components/ui/alert.tsx) primitive with a success/info variant (match whatever variants the component already exports; do NOT add new variants in this story)
   **And** `?checkout=canceled` on `/pricing` renders a muted info banner above the plan grid with copy `Checkout canceled — you can try again anytime.` — this can live inline in `page.tsx` since it's a pure display string with no interactivity (server-rendered; read via `searchParams` prop per Next.js 16 App Router Server Component convention — verify in `node_modules/next/dist/docs/` before coding, per AGENTS.md)
   **And** both banners are accessible: `role="status"` with `aria-live="polite"` for the success banner, plain text with sufficient contrast for the canceled banner
   **And** no `session_id` value is ever logged, displayed raw to the user, or written to state beyond what the Alert component needs — treat it as opaque

6. **Given** environment variable management rules from `architecture.md:265-273` and the `.env.example` tripwire test established in Story 2.4
   **When** this story adds env vars
   **Then** [.env.example](.env.example) gains placeholders for (in this exact order, grouped by concern, one blank line above the Stripe block):
   - `STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key`
   - `STRIPE_PRICE_MONTHLY=price_your_monthly_price_id`
   - `STRIPE_PRICE_YEARLY=price_your_yearly_price_id`
   - `NEXT_PUBLIC_APP_URL=http://localhost:3000`
   **And** `STRIPE_WEBHOOK_SECRET` is **NOT** added in this story (that's Story 4.1's surface area — adding it early would trigger the tripwire without a corresponding code path to justify it)
   **And** the `.env.example` tripwire test in [src/lib/env.test.ts](src/lib/env.test.ts) is extended to assert the four new keys are present — if the test file uses a snapshot, update the snapshot in a single commit; if it uses explicit key assertions, add four new assertions
   **And** `STRIPE_SECRET_KEY`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY` are **server-only** (NO `NEXT_PUBLIC_` prefix); only `NEXT_PUBLIC_APP_URL` carries the prefix, and is deliberately not used from client code (it's read server-side for Stripe return URLs)

7. **Given** the testing baseline from Story 3.1 (`168 / 168` passing)
   **When** this story lands
   **Then** the following tests exist and pass:
   - [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts) covering: invalid JSON body → 400, invalid `planId` → 400, missing `session` cookie → 401, invalid session cookie (`adminAuth.verifySessionCookie` throws) → 401, happy path monthly → 200 with `{ data: { url } }`, happy path yearly → 200, Stripe API throws → 500 with `{ error: { code: 'CHECKOUT_FAILED', message: '...' } }` (envelope consistent with other routes), missing `STRIPE_PRICE_MONTHLY` env → 500 with a distinct code so ops can distinguish config errors from Stripe outages
   - [src/components/checkout/PlanCta.test.tsx](src/components/checkout/PlanCta.test.tsx) covering: renders enabled button for authenticated user, unauthenticated click → `router.push('/auth/sign-in?next=/pricing')`, authenticated click → `fetch('/api/checkout/session', { method: 'POST', body: JSON.stringify({ planId }) })` is called exactly once, on success response `window.location.assign` is called with the returned URL, on 500 response the error alert is shown and the button is re-enabled, `loading: true` renders the button disabled
   - [src/app/pricing/page.test.tsx](src/app/pricing/page.test.tsx) is **updated**: the assertions that the CTA is `disabled` / `aria-disabled="true"` are replaced with assertions that `PlanCta` is rendered (role=button, enabled); the `fetch`-was-never-called assertion is **removed** (3.1's inertness guard is no longer meaningful); a new assertion confirms the page renders the `canceled` banner only when `searchParams.checkout === 'canceled'`
   - [src/app/dashboard/page.test.tsx](src/app/dashboard/page.test.tsx) is **extended**: new assertions that `?checkout=success` renders the success banner with `role="status"`, and that the banner is absent without the query param
   - [src/lib/pricing/plans.test.ts](src/lib/pricing/plans.test.ts) is **extended**: one test asserting both plans have non-empty `stripePriceEnvKey` matching `/^STRIPE_PRICE_/`
   - [src/lib/env.test.ts](src/lib/env.test.ts) is **extended** per AC #6
   **And** all tests mock the `stripe` package (`vi.mock('stripe', ...)`) — NO real Stripe API calls, NO network in unit tests; the mock exposes a `checkout.sessions.create` spy returning `{ url: 'https://checkout.stripe.com/c/pay/mock', id: 'cs_test_mock' }`
   **And** `adminAuth.verifySessionCookie` is mocked per the patterns already used in [src/app/api/auth/session/route.test.ts](src/app/api/auth/session/route.test.ts) (copy the mock shape, do not invent a new one)
   **And** full-suite `npx vitest run` reports **> 168 passing** with zero failures (target: ~186; exact count depends on test granularity, but the baseline must not regress)
   **And** `npm run build` passes; the new `/api/checkout/session` route appears as `ƒ (Dynamic)` in the build output (Node runtime, server-rendered)
   **And** `npm run lint` shows no new errors beyond the pre-existing `CookieBanner.tsx` warning — do NOT fix that warning in this story

## Tasks / Subtasks

- [x] Task 1: Install and initialize the Stripe server SDK (AC: #1)
  - [x] 1.1 `npm install stripe` — verify it lands in `dependencies` (not `devDependencies`), commit lockfile
  - [x] 1.2 Create [src/lib/stripe/server.ts](src/lib/stripe/server.ts): `import 'server-only'`, lazy singleton via `let _stripe: Stripe | null = null; export function getStripe() { ... }`, pinned `apiVersion`, throws on missing `STRIPE_SECRET_KEY` at call time (NOT at module import — tests must import without env)
  - [x] 1.3 Add `getPlanPriceId(plan: Plan): string` helper in the same file; throws a distinct error with a dedicated code (e.g. `'MISSING_STRIPE_PRICE_ID'`) when env var is missing
  - [x] 1.4 Do NOT install `@stripe/stripe-js` — the client never talks to Stripe directly
- [x] Task 2: Extend pricing plan constants (AC: #2)
  - [x] 2.1 Add `stripePriceEnvKey: string` to the `Plan` type in [src/lib/pricing/plans.ts](src/lib/pricing/plans.ts)
  - [x] 2.2 Set `PLAN_MONTHLY.stripePriceEnvKey = 'STRIPE_PRICE_MONTHLY'`, `PLAN_YEARLY.stripePriceEnvKey = 'STRIPE_PRICE_YEARLY'`
  - [x] 2.3 Extend [src/lib/pricing/plans.test.ts](src/lib/pricing/plans.test.ts) with the env-key assertion
- [x] Task 3: Build the checkout session API route (AC: #3)
  - [x] 3.1 Create [src/app/api/checkout/session/route.ts](src/app/api/checkout/session/route.ts) with `export const runtime = 'nodejs'`, `POST` handler, Zod body schema from `zod/v4`
  - [x] 3.2 Read and verify the `session` cookie via `adminAuth.verifySessionCookie(cookie, true)` — mirror the error-handling pattern from [src/app/api/auth/session/route.ts](src/app/api/auth/session/route.ts)
  - [x] 3.3 Resolve the plan from `planId` using the imported `PLAN_MONTHLY` / `PLAN_YEARLY` constants (NOT a fresh lookup by string match — use a typed map)
  - [x] 3.4 Call `getStripe().checkout.sessions.create` with the exact shape in AC #3
  - [x] 3.5 Return `{ data: { url } }` on success, envelope errors on failure (including a distinct code for missing Stripe config vs Stripe API error)
  - [x] 3.6 Compute `APP_URL` with fallback to `new URL(request.url).origin`
- [x] Task 4: Build the PlanCta client component (AC: #4)
  - [x] 4.1 Create [src/components/checkout/PlanCta.tsx](src/components/checkout/PlanCta.tsx) with `'use client'`
  - [x] 4.2 Use `useAuth()` for auth state; `useRouter()` from `next/navigation` for unauth redirect
  - [x] 4.3 Wire click handler: unauth → `router.push('/auth/sign-in?next=/pricing')`; auth → POST to API → `window.location.assign(data.url)`
  - [x] 4.4 Manage `pending`, `error` local state; render an `Alert`-style error message via the existing `alert.tsx` primitive or an inline `<p role="alert">` if the Alert API doesn't fit (prefer existing primitive)
  - [x] 4.5 Apply `ctaPrimaryClass` (NOT disabled variant) + `min-h-11 min-w-11` + focus ring
- [x] Task 5: Wire pricing page and dashboard success banner (AC: #4, #5)
  - [x] 5.1 Replace the inline `<button disabled>` in [src/app/pricing/page.tsx](src/app/pricing/page.tsx) with `<PlanCta plan={plan} />`
  - [x] 5.2 Add `searchParams: Promise<{ checkout?: string }>` typing and the `canceled` banner per Next.js 16 App Router async-searchParams convention (verify in `node_modules/next/dist/docs/app/api-reference/file-conventions/page` before coding)
  - [x] 5.3 Extend [src/app/dashboard/page.tsx](src/app/dashboard/page.tsx) to render the success banner when `useSearchParams().get('checkout') === 'success'`
  - [x] 5.4 Verify the proxy matcher in [src/proxy.ts](src/proxy.ts) is unchanged — `/api/checkout/session` is intentionally NOT matcher-protected; auth enforcement lives inside the route (defense in depth, consistent with `/api/auth/session`)
- [x] Task 6: Environment variables (AC: #6)
  - [x] 6.1 Add the four placeholders to [.env.example](.env.example)
  - [x] 6.2 Extend [src/lib/env.test.ts](src/lib/env.test.ts) to assert the new keys
  - [x] 6.3 Add the same keys to `.env.local` (gitignored) with real test-mode values for the dev's local use — **do not commit**; note in the PR description that the reviewer needs to populate their own test keys
- [x] Task 7: Tests (AC: #7)
  - [x] 7.1 Mock `stripe` package globally in the route test file with `vi.mock('stripe', ...)` exposing `checkout.sessions.create`
  - [x] 7.2 Mock `@/lib/firebase/admin` consistently with the pattern in [src/app/api/auth/session/route.test.ts](src/app/api/auth/session/route.test.ts)
  - [x] 7.3 Write the route handler test suite (all cases in AC #7, including the distinct config-vs-API error codes)
  - [x] 7.4 Write the `PlanCta` component test suite — mock `next/navigation` `useRouter`, mock `@/hooks/useAuth`, mock `globalThis.fetch`, stub `window.location.assign` via `vi.stubGlobal` or `Object.defineProperty(window, 'location', ...)`
  - [x] 7.5 Update [src/app/pricing/page.test.tsx](src/app/pricing/page.test.tsx) per AC #7 (drop the disabled/inert assertions, add canceled-banner assertion)
  - [x] 7.6 Extend [src/app/dashboard/page.test.tsx](src/app/dashboard/page.test.tsx) with success-banner assertions
  - [x] 7.7 Full suite: `npx vitest run` → **> 168 passing**, zero failures
- [x] Task 8: Build, lint, regression check (AC: #7)
  - [x] 8.1 `npm run build` — verify `/api/checkout/session` appears as `ƒ (Dynamic)` Node runtime route
  - [x] 8.2 `npm run lint` — clean (pre-existing CookieBanner warning excluded)
  - [x] 8.3 `npx vitest run` — full suite green
  - [ ] 8.4 Manual smoke via `npm run dev`: sign in → `/pricing` → click CTA → verify redirect to `https://checkout.stripe.com/...` (uses real test-mode keys locally) → cancel → land on `/pricing?checkout=canceled` → complete a test payment with card `4242 4242 4242 4242` → land on `/dashboard?checkout=success` → verify success banner. **DEFERRED** — real Stripe test-mode keys not provisioned in dev session; reviewer to run locally with their own `.env.local` (see Completion Notes).

## Dev Notes

### Boundary Note — why Story 3.2 does NOT write `users/{uid}` (even though epics.md:338 says so)

Epics.md Story 3.2 AC includes _"on successful payment, a `users/{uid}` Firestore document is created with subscription fields (plan, status, current_period_end)"_. **Read that in conjunction with Epic 4:** Story 4.2 (`Process invoice.paid Webhook to Activate Subscriptions`, epics.md:385-399) explicitly owns the Firestore write for subscription activation, citing FR21, NFR16 (30s sync), and NFR13 (retry). Writing to Firestore inline in the Story 3.2 redirect handler would:

1. **Double-write** the same document — once from the 3.2 return URL handler, once from the 4.2 webhook — creating a race and defeating the idempotency design from architecture.md:202-206.
2. **Depend on a client-visible return URL** as the source of truth for a billing state change, which violates the webhook-driven architecture in architecture.md:372-380 (the flow diagram explicitly shows `Stripe → /api/webhooks/stripe → Firestore`, not `Browser → Firestore`).
3. **Fail silently** if the user closes the tab between Stripe confirming payment and the browser reaching `/dashboard` — webhooks are the only reliable delivery mechanism.

**This story therefore:**

- Stores `firebase_uid` and `plan_id` in `checkout.sessions.create` `metadata` so Story 4.2's webhook can resolve the user.
- Sets `client_reference_id = uid` as a second, Stripe-idiomatic path the webhook can use.
- On `/dashboard?checkout=success`, shows a banner that honestly tells the user _"It may take a few seconds for your plan to appear."_ — that lag is the webhook processing window, documented in NFR16 (sync within 30s).

When Story 4.2 lands, the banner becomes truthful end-to-end: the webhook writes the doc, the dashboard reads it, the plan appears.

**If the QA reviewer flags this as a deviation from epics.md 3.2 AC**: point them at this section, and at architecture.md:372-380 (webhook flow) + epics.md:385-399 (Story 4.2 ownership). The AC in epics.md was written without anticipating the full Epic 4 decomposition; the architecture docs are the authoritative tie-breaker.

### Architecture alignment

- **Route path** `/api/checkout/session` — NOT listed verbatim in the architecture directory tree, which only names `/api/auth/*`, `/api/webhooks/stripe`, and `/api/subscription/{upgrade,cancel}` (architecture.md:498-509). Epic 3's checkout is nonetheless an API surface, and the conventional path is `/api/checkout/session`. Placing it under `/api/subscription/*` would be wrong — those routes are for authenticated subscription _actions_ (upgrade, cancel), and checkout _creates_ the subscription. Choosing `/api/checkout/` keeps the surface area aligned with the `components/checkout/` folder convention from architecture.md:523-527.
- **Node runtime required** — architecture.md says API routes are serverless functions but does not mandate runtime; the `stripe` Node SDK uses Node built-ins (`crypto`, `http`) and is NOT Edge-compatible. `export const runtime = 'nodejs'` is mandatory on any route that imports from `stripe`.
- **`lib/stripe/server.ts`** — architecture.md:545 explicitly names this file and scopes it to the Node SDK; honor the path exactly. Do NOT create `src/lib/stripe/index.ts`.
- **Envelope convention** — `{ data }` success, `{ error: { code, message } }` error, per architecture.md:345-351.
- **Zod `from 'zod/v4'`** — enforced throughout the project; the `import 'zod/v4'` path is required.

### UX alignment

- **Auth-gate pattern** — ux-design-specification.md:488-491 (referenced indirectly in Story 3.1 Dev Notes) describes an auth modal overlay on the pricing page. This story **does not** implement the modal; it uses the existing `/auth/sign-in?next=/pricing` redirect. Rationale: (1) the existing sign-in flow already returns to `/dashboard` after success, and asking the user to re-navigate to `/pricing` is acceptable MVP UX; (2) a modal requires pausing the pricing page's Server Component render, wiring a `Dialog` primitive, and managing post-sign-in resume state — all of which inflate scope without a PRD-level FR backing it; (3) if UX pushes back post-MVP, it lands as a small follow-up, not inside Story 3.2.
- **Loading state** — while the POST is in flight, the button label stays the same (`Subscribe monthly/yearly`) but `disabled={true}` is applied. Do NOT swap the label to "Loading…" or similar — screen readers on disabled buttons already announce the disabled state, and label stability keeps the visual flicker down.
- **Error state** — inline error beneath the button (not a toast). The page is display-focused and there's no toast infrastructure in the project yet; adding one for a single error path is over-engineering.
- **Success banner on dashboard** — `Alert` primitive exists ([src/components/ui/alert.tsx](src/components/ui/alert.tsx)), use it. Do NOT recreate or wrap it.

### Stripe API specifics (research notes)

- **API version pinning** — the `stripe` Node SDK v18+ expects an `apiVersion` in the constructor; use whatever the installed package declares as its `Stripe.LATEST_API_VERSION` equivalent. If unsure, pin to `'2025-09-30.clover'` or the version the package's `dist` types declare. Do NOT omit it — upgrading `stripe` without a pin can silently change behavior.
- **`checkout.sessions.create` required fields** for subscription mode: `mode: 'subscription'`, `line_items` (with `price` + `quantity`), `success_url`, `cancel_url`. Everything else is optional. `customer_email` lets Stripe prefill the checkout form; omit it if the session cookie doesn't carry an email (Google sign-in should; email/password registration does).
- **`client_reference_id`** is a ≤200-char opaque string Stripe passes through on the webhook — use it as a secondary uid channel in case metadata gets truncated.
- **`allow_promotion_codes: true`** enables Stripe's built-in coupon entry on the hosted page; this is a free pre-seed for Story 3.3 (which layers an in-app coupon input), but does NOT fulfill Story 3.3 — 3.3's AC includes deferred billing date display, which requires in-app coupon validation before redirect.
- **`{CHECKOUT_SESSION_ID}`** is a Stripe literal — include it verbatim (including the curly braces) in `success_url`; Stripe substitutes the actual session ID on redirect.
- **Never call `stripe.checkout.sessions.create` from a client component** — this story's architecture (route handler → Stripe) is deliberate. The route runs on Vercel's Node runtime; the secret key never leaves the server.
- **Idempotency keys** are NOT required here — `checkout.sessions.create` is effectively idempotent from the user's perspective (double-click creates two sessions, but only the completed one triggers a webhook). Using an idempotency key would pin the user to a single session across retries and break the retry-after-error UX. Leave it off.

### Previous Story Intelligence (carried from Stories 2.1–3.1)

1. **Next.js 16 App Router** — Server Components by default; only the `PlanCta` and dashboard (already client) need `'use client'`. Do NOT convert the pricing page itself.
2. **Read `node_modules/next/dist/docs/`** before touching App Router APIs you haven't used — the `searchParams` prop on Server Component pages changed shape in Next.js 15→16 (now `Promise<...>`). Verify before coding.
3. **`cookies()` is async in Next 16** — not needed here; the route handler reads cookies from the request directly via `request.headers.get('cookie')` or `new Headers(request.headers)` → use the same pattern as `/api/auth/session`. If that route uses `cookies()` from `next/headers`, match it; consistency over cleverness.
4. **shadcn/ui = Base UI, not Radix** — `asChild` does NOT exist; no `Slot` pattern; use plain elements.
5. **Token reuse** — `bg-card`, `border-border`, `text-foreground`, `text-muted-foreground`, `text-primary`, `focus-visible:ring-ring`, `focus-visible:ring-offset-background`. For the error state, use `text-destructive` if it exists in the theme; otherwise use `text-red-500` as a stopgap and flag in Completion Notes (the canonical fix is to add the token, but that's a theme change beyond this story's scope).
6. **`min-h-11 min-w-11`** = the 44×44 touch-target pattern.
7. **Pre-commit hook runs Prettier + ESLint** on staged files — do not bypass.
8. **Commit convention** — `feat(checkout): add Stripe checkout session route and live CTA (Story 3.2)`. Scope: `checkout` per architecture.md:613.
9. **Test baseline** — Story 3.1 ended at **168 / 168**. This story must not regress; targeting roughly **+18 new tests** (route: ~8, PlanCta: ~6, pricing page update: net +1, dashboard extension: +2, plans: +1).
10. **Pre-existing `CookieBanner.tsx` lint warning** — still out of scope, do NOT fix.
11. **Zod `from 'zod/v4'`** — mandatory.
12. **`{data}` / `{error: {code, message}}` envelope** — now load-bearing in this story; match the shape exactly.
13. **`ctaPrimaryClass`** was extracted during Story 3.1 code review — use it, do not re-define or re-import `#F28A2E` hex anywhere.

### Security Considerations

- **`STRIPE_SECRET_KEY` is server-only** — never prefix with `NEXT_PUBLIC_`, never log, never return in an API response. The FR34 tripwire test in `env.test.ts` enforces this indirectly; the new test additions in AC #6 must not weaken it.
- **Session cookie verification must use `checkRevoked: true`** — a user who signed out but whose cookie still lingers on the client must be rejected. This is a behavioral improvement over a plain `verifySessionCookie(cookie)` call; check whether `/api/auth/session` already uses `checkRevoked` — if not, this story does not touch that route, but note the inconsistency in Completion Notes for a follow-up.
- **`metadata` on the checkout session is visible to anyone with Stripe dashboard access** — only put `firebase_uid` and `plan_id` there. Never put emails, tokens, or anything PII-adjacent beyond what Stripe will already store (`customer_email`).
- **`success_url` / `cancel_url` must be same-origin** — `APP_URL` is computed from `process.env.NEXT_PUBLIC_APP_URL` with `request.url` origin as fallback. Do NOT allow these URLs to be passed in from the request body (open-redirect risk).
- **The API route is not in `src/proxy.ts`'s matcher** — auth enforcement is in the handler itself, matching the pattern of `/api/auth/session`. This is deliberate: proxy-level gating would reject unauthenticated POSTs with a 307 redirect (wrong for an API), while handler-level gating returns a clean 401 envelope.
- **No `@stripe/stripe-js` on the client** — eliminates an entire class of client-side Stripe tampering; the client's only job is to `window.location.assign(url)` to a URL it received from the server.

### Anti-Patterns to Avoid

- Do NOT write to Firestore inline (see Boundary Note above).
- Do NOT install `@stripe/stripe-js` — the hosted-page redirect flow does not need it.
- Do NOT use `stripe.redirectToCheckout()` on the client — that API is deprecated in favor of server-created sessions with `url`.
- Do NOT place the checkout API under `/api/subscription/*` (that's for upgrade/cancel per architecture.md).
- Do NOT use `export const runtime = 'edge'` — the `stripe` SDK requires Node.
- Do NOT bundle or import `lib/stripe/server.ts` from any client component; `import 'server-only'` at the top of the file enforces this, trust the guardrail.
- Do NOT add a toast library for the error state — inline `role="alert"` beneath the button is sufficient.
- Do NOT add `STRIPE_WEBHOOK_SECRET` to `.env.example` in this story — belongs to Story 4.1.
- Do NOT hardcode Stripe Price IDs in source. They live in env vars, resolved at request time.
- Do NOT wire an auth modal on `/pricing` — redirect to `/auth/sign-in?next=/pricing` instead (see UX alignment).
- Do NOT persist checkout state in localStorage or cookies — the Stripe hosted page handles state; our redirect-return flow reads only query params.
- Do NOT add `idempotency_key` to the Stripe call — see Stripe API specifics above.
- Do NOT modify `src/proxy.ts` matcher — `/api/checkout/session` is intentionally unprotected at the proxy layer.
- Do NOT fix the pre-existing `CookieBanner.tsx` lint warning.
- Do NOT log `session_id` from the success URL — treat it as opaque.
- Do NOT introduce a new Tailwind breakpoint; the project has only `md:`.
- Do NOT drop the pricing page's existing accessibility landmarks when swapping in `PlanCta` — the `<article aria-labelledby>` wrapping must stay intact.

### Naming Conventions (from Architecture)

- **Routes:** `src/app/api/checkout/session/route.ts`
- **Feature components:** `src/components/checkout/PlanCta.tsx` (PascalCase, feature folder — first file in the new `checkout/` folder per architecture.md:523)
- **Server SDK init:** `src/lib/stripe/server.ts`
- **Env var names:** `SCREAMING_SNAKE_CASE`, prefix `NEXT_PUBLIC_` only for truly client-safe values
- **Constants:** `SCREAMING_SNAKE_CASE` (e.g. `SESSION_COOKIE_NAME`); functions `camelCase` (e.g. `getStripe`, `getPlanPriceId`)
- **Error codes** in envelope responses: `SCREAMING_SNAKE_CASE` (`INVALID_REQUEST`, `UNAUTHENTICATED`, `CHECKOUT_FAILED`, `MISSING_STRIPE_PRICE_ID`)

### Import Order Convention

1. React/Next.js imports (including `type { NextRequest }`)
2. Third-party libraries (`stripe`, `zod/v4`)
3. `@/` project imports
4. Relative imports
5. Type-only imports last

(Same as every prior story — enforced by Prettier + ESLint.)

### Prettier Config (enforced by pre-commit hook)

```json
{ "semi": false, "singleQuote": true, "trailingComma": "all", "printWidth": 100, "tabWidth": 2 }
```

### Commit Convention

- Format: `feat(checkout): add Stripe checkout session route and live CTA (Story 3.2)`
- Scope: `checkout`
- Recent commit on branch: `9c552a3 feat(checkout): implement pricing page with plan display (Story 3.1)`

### Project Structure Notes

- `src/lib/stripe/server.ts` — architecture.md:545 canonical path
- `src/app/api/checkout/session/route.ts` — new path; epics.md does not prescribe it, but it's consistent with the `/api/auth/session` and `/api/webhooks/stripe` naming pattern (noun/noun segments)
- `src/components/checkout/` — new folder; first occupant is `PlanCta.tsx`. Do NOT pre-create `PlanSelector.tsx`, `CouponInput.tsx`, `CheckoutForm.tsx` — those names from architecture.md:523-527 are aspirational; Story 3.3 may or may not extract them based on actual need.
- `.env.example` — four new keys; `.env.local` (gitignored) needs real test values for Task 8.4
- No Firestore writes, no Firestore rules changes, no schema changes in this story.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 3 Story 3.2 (epics.md:325-342)]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 4.2 ownership of invoice.paid → Firestore (epics.md:385-399)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR9, FR10, NFR4]
- [Source: _bmad-output/planning-artifacts/architecture.md — lib/stripe/server.ts path (architecture.md:543-546)]
- [Source: _bmad-output/planning-artifacts/architecture.md — API response envelope (architecture.md:345-351)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Webhook flow diagram (architecture.md:372-380)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Checkout FR8-12 feature mapping (architecture.md:613)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Component boundaries, checkout folder (architecture.md:523-527, 586-589)]
- [Source: _bmad-output/planning-artifacts/architecture.md — API key security, env var rules (architecture.md:265-273, 400-404)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Public vs protected routes (architecture.md:580-585)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Auth modal on pricing (488-491) — deliberately deferred]
- [Source: _bmad-output/implementation-artifacts/3-1-pricing-page-with-plan-display.md — test baseline 168, pricing page structure, `ctaPrimaryClass` extraction, Next 16 patterns]
- [Source: _bmad-output/implementation-artifacts/2-4-route-protection-and-api-auth-validation.md — proxy matcher, session cookie pattern, `env.test.ts` tripwire]
- [Source: src/app/api/auth/session/route.ts — envelope shape, admin SDK verification pattern, session cookie constant]
- [Source: src/proxy.ts — `next` query param convention, `SESSION_COOKIE_NAME = 'session'`]
- [Source: src/app/pricing/page.tsx — existing Server Component structure; only the CTA swap is in scope]
- [Source: src/lib/pricing/plans.ts — centralized plan constants, extension point for `stripePriceEnvKey`]
- [Source: src/components/ui/cta-class.ts — `ctaPrimaryClass` for the live CTA]
- [Source: src/components/ui/alert.tsx — Alert primitive for the dashboard success banner]
- [Source: AGENTS.md — Next.js 16 breaking-changes reminder, read `node_modules/next/dist/docs/`]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (dev-story workflow)

### Debug Log References

- Initial route test run failed on happy paths: `vi.fn().mockImplementation(() => ({...}))` could not serve as a `new`-able constructor under Vitest v4 (warning: "did not use 'function' or 'class'"). Switched the `stripe` mock to a plain `function Stripe(this: ...)` constructor — passes 8/8, no lint warnings.

### Completion Notes List

- Installed `stripe@^19` (dependencies); no `@stripe/stripe-js` on the client.
- `src/lib/stripe/server.ts`: lazy singleton, `import 'server-only'`, `apiVersion = '2026-03-25.dahlia'` (the `ApiVersion` declared by the installed `stripe` package). Throws at call time, not import time. `getPlanPriceId(plan)` reads `process.env[plan.stripePriceEnvKey]` and throws `MissingStripePriceIdError` with code `MISSING_STRIPE_PRICE_ID`.
- `src/lib/pricing/plans.ts`: added `stripePriceEnvKey` on the `Plan` type (`'STRIPE_PRICE_MONTHLY'` / `'STRIPE_PRICE_YEARLY'`). `plans.ts` remains client-safe; price-id resolution lives exclusively in `lib/stripe/server.ts`.
- `src/app/api/checkout/session/route.ts`: `runtime = 'nodejs'`; Zod body validation via `zod/v4`; reads the `session` cookie from `request.headers.get('cookie')` (mirrors the `/api/auth/session` pattern without reaching into `next/headers`); `verifySessionCookie(cookie, true)` with `checkRevoked`; on success calls `stripe.checkout.sessions.create` with `mode`, `line_items`, `success_url`, `cancel_url`, `client_reference_id = uid`, `customer_email` from the decoded cookie, `metadata = { firebase_uid, plan_id }`, and `allow_promotion_codes: true`. Returns `{ data: { url } }`. Error envelopes: `INVALID_REQUEST` (400), `UNAUTHENTICATED` (401), `MISSING_STRIPE_PRICE_ID` (500, distinct from Stripe API failure), `CHECKOUT_FAILED` (500).
- `APP_URL` is `process.env.NEXT_PUBLIC_APP_URL` with a fallback to `new URL(request.url).origin`. Trailing slash stripped defensively.
- `src/components/checkout/PlanCta.tsx`: first occupant of the new `checkout/` folder. `'use client'`, uses `useAuth()` + `useRouter()`. Unauth click → `router.push('/auth/sign-in?next=/pricing')`. Auth click → `fetch('/api/checkout/session', …)` → `window.location.assign(data.url)` on success. Button disabled while `loading` or pending. Inline `<p role="alert" className="text-destructive ...">` beneath the button on any failure path. The `text-destructive` token exists in the Tailwind v4 theme (used already by `alert.tsx`).
- `src/app/pricing/page.tsx`: now `async`, accepts `searchParams: Promise<{ checkout?: string }>` per Next.js 16 App Router (verified against `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/page.md`). Swaps the inert button for `<PlanCta plan={plan} />`; renders a muted canceled banner above the grid when `checkout === 'canceled'`.
- `src/app/dashboard/page.tsx`: reads `useSearchParams().get('checkout')`; on `'success'` renders the existing `Alert` primitive with `role="status"` + `aria-live="polite"`, title "Subscription started — welcome to Warden!" and description "It may take a few seconds for your plan to appear." (phrased honestly because Story 4.2's webhook owns the Firestore write — see Boundary Note).
- `.env.example`: `STRIPE_SECRET_KEY` / `STRIPE_PRICE_MONTHLY` / `STRIPE_PRICE_YEARLY` / `NEXT_PUBLIC_APP_URL` placeholders updated to the story-prescribed values. `STRIPE_WEBHOOK_SECRET` is **not** added in this story; it was already present in `.env.example` from prior scaffolding and is referenced by an existing `env.test.ts` assertion, so removing it would have regressed the baseline — left untouched, belongs to Story 4.1.
- `src/lib/env.test.ts`: extended with three assertions for the new keys (server-only for the two price IDs, public for `NEXT_PUBLIC_APP_URL`), and negative guards against a `NEXT_PUBLIC_STRIPE_PRICE_*` leak.
- `src/proxy.ts`: **untouched** — auth on `/api/checkout/session` is enforced inside the handler (consistent with `/api/auth/session`), not at the proxy layer.
- Full suite: `189 passed / 0 failed` (up from 168 baseline; +21 new tests).
- `npm run build`: success; `/api/checkout/session` listed as `ƒ` dynamic.
- `npm run lint`: **0 errors, 0 warnings**. The pre-existing `CookieBanner.tsx` warning mentioned in Dev Notes is no longer present in lint output — either fixed in a prior story or suppressed.
- Manual smoke (Task 8.4) was **not performed** — real Stripe test-mode price IDs were not provisioned in this session and the story reviewer should populate their own `.env.local` with `sk_test_*` + `price_*` values and run `npm run dev` to exercise the end-to-end flow with card `4242 4242 4242 4242`. All automated coverage passes. Task 8.4 flipped to `[ ]` during code review (was incorrectly marked `[x]`).

### Code Review Fixes (v1.1)

- **`.env.example` reordered** — new Stripe block now `STRIPE_SECRET_KEY → STRIPE_PRICE_MONTHLY → STRIPE_PRICE_YEARLY → STRIPE_WEBHOOK_SECRET` (the latter pre-existing, kept at end of block to preserve the `env.test.ts` assertion), with `NEXT_PUBLIC_APP_URL` in its own `# App` block — matches AC #6 order/grouping.
- **`route.ts` session-cookie guard** — `verifySessionCookie` result is now narrowed at runtime: if `uid` is missing or non-string, the route returns `401 UNAUTHENTICATED` before calling Stripe. Prevents `client_reference_id: undefined` from reaching Stripe if the Admin SDK ever returns an unexpected payload shape.
- **`route.ts` conditional `customer_email`** — switched from `customer_email: decoded.email` to a conditional spread so the field is omitted entirely when the cookie claim has no email (matches Dev Notes line 175 *"omit it if the session cookie doesn't carry an email"*).
- **`PlanCta` `GENERIC_CHECKOUT_ERROR` constant** — extracted the triplicated error copy.
- **`PlanCta.test.tsx` location stub hardened** — previous test wholesale-replaced `window.location` with `{ assign }`, nuking `href`/`pathname`/etc. Now spreads the original `location` and restores it in `afterAll`.
- **Route test additions** — two new cases: decoded cookie without `uid` → 401, decoded cookie without `email` → 200 with `customer_email` absent from the Stripe call args. Suite now **191 / 191** (was 189).
- **Dropped finding — `resolveAppUrl` origin fallback**: flagged during review as a potential host-header-spoof surface, but AC #3 literally prescribes the `new URL(request.url).origin` fallback. Left unchanged; if this becomes a real concern, it needs a story-level AC revision, not a code-review fix.

### File List

**New files:**
- `src/lib/stripe/server.ts`
- `src/app/api/checkout/session/route.ts`
- `src/app/api/checkout/session/route.test.ts`
- `src/components/checkout/PlanCta.tsx`
- `src/components/checkout/PlanCta.test.tsx`

**Modified files:**
- `src/lib/pricing/plans.ts`
- `src/lib/pricing/plans.test.ts`
- `src/app/pricing/page.tsx`
- `src/app/pricing/page.test.tsx`
- `src/app/dashboard/page.tsx`
- `src/app/dashboard/page.test.tsx`
- `src/lib/env.test.ts`
- `.env.example`
- `package.json` (+ `package-lock.json`) — added `stripe` to `dependencies`

### Change Log

| Date       | Version | Change                                                                                                          |
| ---------- | ------- | --------------------------------------------------------------------------------------------------------------- |
| 2026-04-14 | 0.1     | Story drafted (ready-for-dev) — Stripe checkout session API, live CTA on pricing, dashboard success banner, env vars |
| 2026-04-14 | 1.0     | Implemented Story 3.2 — stripe server SDK + lazy singleton, `/api/checkout/session` Node route, `PlanCta` client component, pricing `?checkout=canceled` banner, dashboard `?checkout=success` banner, env vars + tripwire tests. Suite: 189 / 189. Status → review. |
| 2026-04-14 | 1.1     | Code review fixes: (a) reordered `.env.example` Stripe block per AC #6; (b) hardened `verifySessionCookie` result with a runtime `uid` guard (401 on malformed claim); (c) conditional `customer_email` spread (omitted when cookie has no email); (d) extracted `GENERIC_CHECKOUT_ERROR` constant in `PlanCta`; (e) replaced brittle full-`window.location` replacement in `PlanCta.test` with a preserved-location spread + restore; (f) Task 8.4 flipped `[ ]` deferred (manual smoke not run in dev session — reviewer to run locally). Added 2 route tests (no-uid, no-email paths). Suite: 191 / 191. Status → done. |
