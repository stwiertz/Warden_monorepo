# Story 5.2: Stripe Customer Portal Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a subscriber,
I want to manage my subscription (view payment history, change plan, cancel, update payment method) via Stripe's Customer Portal,
So that I can handle all billing tasks in a secure, Stripe-hosted environment.

## Acceptance Criteria

1. **Given** an authenticated subscriber is on the `/dashboard` page
   **When** the subscriber clicks the "Manage Subscription" button
   **Then** a server-side API route creates a Stripe Customer Portal session via `stripe.billingPortal.sessions.create()` (FR20)
   **And** the subscriber is redirected to the Stripe Customer Portal
   **And** the portal provides access to payment history (FR17), plan switching with proration (FR18), subscription cancellation (FR19), and payment method updates
   **And** after the subscriber returns from the portal, they land back on `/dashboard`
   **And** any changes made in the portal trigger existing webhook handlers (Stories 4.2, 4.3) to update Firestore state

2. **Given** a signed-in user views any page
   **When** the header renders
   **Then** the header navigation shows a "Dashboard" link pointing to `/dashboard` (replacing the signed-out "Home" and "Pricing" links per UX spec line 715)
   **And** this fulfills the deferred nav task from Story 1.3

3. **Given** the portal session API route
   **When** a request is made
   **Then** the route validates the session cookie before processing (FR33, defense in depth)
   **And** the route reads the `stripe_customer_id` from the subscriber's `users/{uid}` Firestore document
   **And** the route returns 200 with `{ data: { url: string } }` on success
   **And** the route returns a structured error response on failure (`{ error: { code, message } }`)

4. **Given** a subscriber has no `stripe_customer_id` in Firestore (edge case: webhook hasn't arrived yet)
   **When** the "Manage Subscription" button is clicked
   **Then** the API route returns an appropriate error
   **And** the dashboard shows a user-friendly message (not a raw error)

5. **Given** the existing test suite
   **When** `npx vitest run` is executed
   **Then** all 308 existing tests continue to pass
   **And** new tests cover: portal session API route (auth, happy path, no customer, Stripe error), header nav changes (signed-in shows Dashboard link, signed-out shows Home/Pricing/Sign-in), SubscriptionCard "Manage Subscription" button
   **And** `npm run build` passes with zero type errors
   **And** `npm run lint` shows 0 errors, 0 warnings

**Human Prerequisites:**
- [ ] Stripe Customer Portal configured in Stripe Dashboard (enable plan switching, cancellation, payment method updates)
- [ ] Portal branding configured (logo, colors, return URL pointing to `/dashboard`)

## Tasks / Subtasks

- [x] **Task 1: Create `POST /api/subscription/portal` route** (AC: #1, #3, #4)
  - [x] 1.1 Create `src/app/api/subscription/portal/route.ts`. This sits alongside the existing `GET /api/subscription` route ([src/app/api/subscription/route.ts](src/app/api/subscription/route.ts)).
  - [x] 1.2 Use `withAuth` from [src/lib/firebase/auth.ts](src/lib/firebase/auth.ts) — same pattern as the existing subscription route and checkout session route. This handles session cookie validation and returns 401 on failure.
  - [x] 1.3 Implementation:
    ```ts
    import 'server-only'

    import { withAuth } from '@/lib/firebase/auth'
    import { adminDb } from '@/lib/firebase/admin'
    import { getStripe } from '@/lib/stripe/server'

    export const runtime = 'nodejs'

    export async function POST(request: Request) {
      return withAuth(async (session) => {
        try {
          const userRef = adminDb.collection('users').doc(session.uid)
          const snap = await userRef.get()

          if (!snap.exists || !snap.data()?.stripe_customer_id) {
            return Response.json(
              { error: { code: 'NO_CUSTOMER', message: 'No subscription found to manage' } },
              { status: 404 },
            )
          }

          const stripeCustomerId = snap.data()!.stripe_customer_id as string

          // Resolve return URL — same pattern as checkout session route
          const fromEnv = process.env.NEXT_PUBLIC_APP_URL
          const appUrl = fromEnv && fromEnv.length > 0
            ? fromEnv.replace(/\/$/, '')
            : new URL(request.url).origin

          const stripe = getStripe()
          const portalSession = await stripe.billingPortal.sessions.create({
            customer: stripeCustomerId,
            return_url: `${appUrl}/dashboard`,
          })

          return Response.json({ data: { url: portalSession.url } })
        } catch (err) {
          console.error(
            `[subscription/portal ${new Date().toISOString()}] portal session creation failed:`,
            session.uid,
            err,
          )
          return Response.json(
            { error: { code: 'PORTAL_SESSION_FAILED', message: 'Unable to open subscription management' } },
            { status: 500 },
          )
        }
      })
    }
    ```
  - [x] 1.4 The route reads `stripe_customer_id` from Firestore, NOT from a request body. The customer ID is an internal field — the client should never send it.
  - [x] 1.5 Use `getStripe()` from [src/lib/stripe/server.ts](src/lib/stripe/server.ts) — the existing singleton Stripe instance (SDK v22.0.1, API version `2026-03-25.dahlia`).
  - [x] 1.6 The `return_url` is set to `/dashboard` so the subscriber lands back on the dashboard after leaving the portal. Use the same `NEXT_PUBLIC_APP_URL` resolution pattern from [checkout session/route.ts](src/app/api/checkout/session/route.ts) (lines 36-39).
  - [x] 1.7 **Do NOT** pass `configuration` to `billingPortal.sessions.create()` — use the default portal configuration set in the Stripe Dashboard. This keeps the portal config in one place (Stripe Dashboard), not split between code and dashboard.
  - [x] 1.8 **Do NOT** retry the Stripe call with `retryStripeCall`. Portal session creation is a one-time, user-initiated action — if it fails, the user clicks again. Retry logic is for webhook processing (Stories 4.2/4.3) where there's no user to retry.
  - [x] 1.9 Include `import 'server-only'` at the top to prevent accidental client-side bundling of `adminDb` and Stripe SDK.

- [x] **Task 2: Add "Manage Subscription" button to SubscriptionCard** (AC: #1, #4)
  - [x] 2.1 Edit [src/components/dashboard/SubscriptionCard.tsx](src/components/dashboard/SubscriptionCard.tsx).
  - [x] 2.2 Add a "Manage Subscription" button inside the subscription-data state (when `subscription` is not null and not in error/loading state). Place it below the `<dl>` description list, inside a `<div className="mt-4">` wrapper.
  - [x] 2.3 The button calls the portal API and redirects:
    ```tsx
    const [portalLoading, setPortalLoading] = useState(false)
    const [portalError, setPortalError] = useState<string | null>(null)

    async function handleManageSubscription() {
      setPortalLoading(true)
      setPortalError(null)
      try {
        const res = await fetch('/api/subscription/portal', { method: 'POST' })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body?.error?.message || 'Unable to open subscription management')
        }
        const body = await res.json()
        window.location.href = body.data.url
      } catch (err) {
        setPortalError(err instanceof Error ? err.message : 'Unable to open subscription management')
        setPortalLoading(false)
      }
    }
    ```
  - [x] 2.4 Button styling: use `variant="outline"` (secondary action per UX button hierarchy — "Manage billing" is a supporting action, not the page's primary CTA). Full-width on mobile. Show loading spinner text ("Loading...") when `portalLoading` is true.
  - [x] 2.5 Display `portalError` as a small red error text below the button if the portal API call fails. Matches the error display pattern already used in the error state of SubscriptionCard.
  - [x] 2.6 **Do NOT** show the "Manage Subscription" button in the no-subscription state or error state — only when the subscriber has an active/past_due/canceled subscription.
  - [x] 2.7 Add `import { useState } from 'react'` at the top (the component already has `'use client'` directive).

- [x] **Task 3: Update HeaderAuthActions for signed-in navigation** (AC: #2)
  - [x] 3.1 Edit [src/components/layout/HeaderAuthActions.tsx](src/components/layout/HeaderAuthActions.tsx).
  - [x] 3.2 When the user is signed in (`user` is truthy), render a "Dashboard" link pointing to `/dashboard` **in addition to** the existing SignOutButton. The Dashboard link replaces the need for "Home" and "Pricing" nav links for signed-in users — per UX spec line 715: header nav shows "Dashboard" link when signed in.
  - [x] 3.3 Updated signed-in rendering:
    ```tsx
    if (user) {
      return (
        <>
          <li>
            <Link
              href="/dashboard"
              className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 rounded-md px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-3"
            >
              Dashboard
            </Link>
          </li>
          <li>
            <SignOutButton variant="ghost" size="sm">
              Sign out
            </SignOutButton>
          </li>
        </>
      )
    }
    ```
  - [x] 3.4 The "Home" and "Pricing" links in the parent [Header.tsx](src/components/layout/Header.tsx) are **always visible** (they're rendered statically outside HeaderAuthActions). The UX spec says to replace them when signed in. To implement this correctly, the Header component needs to conditionally hide "Home" and "Pricing" links when signed in. However, Header.tsx is a server component — it cannot use `useAuth()`.
  - [x] 3.5 **Approach:** Move the conditional nav links into HeaderAuthActions. Edit [Header.tsx](src/components/layout/Header.tsx) to remove the static "Home" and "Pricing" `<li>` elements and instead render them inside HeaderAuthActions when the user is NOT signed in. This keeps all auth-conditional rendering in the client component.
  - [x] 3.6 Updated Header.tsx nav section:
    ```tsx
    <nav aria-label="Main navigation">
      <ul className="flex items-center gap-1">
        <HeaderAuthActions />
      </ul>
    </nav>
    ```
  - [x] 3.7 Updated HeaderAuthActions full rendering:
    - **Loading:** Same placeholder `<li>` as current (unchanged)
    - **Not signed in:** "Home" link + "Pricing" link + "Sign in" link (3 `<li>` elements)
    - **Signed in:** "Dashboard" link + SignOutButton (2 `<li>` elements)
  - [x] 3.8 The link styles (`text-muted-foreground hover:text-foreground ...`) are identical to what's currently in Header.tsx — copy them exactly. Use the same `className` string from the current static links.
  - [x] 3.9 **Do NOT** change the Warden logo/home link on the left side of the header — that always links to `/`.

- [x] **Task 4: Write portal API route tests** (AC: #5)
  - [x] 4.1 Create `src/app/api/subscription/portal/route.test.ts`.
  - [x] 4.2 Mock `@/lib/firebase/auth` (provide `withAuth` that invokes the handler), `@/lib/firebase/admin` (provide `adminDb.collection().doc().get()` returning controlled snapshots), and `@/lib/stripe/server` (provide `getStripe()` returning a mock with `billingPortal.sessions.create`). Follow mock patterns from [src/app/api/subscription/route.test.ts](src/app/api/subscription/route.test.ts) and [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts).
  - [x] 4.3 Test cases:
    - **Happy path:** Firestore doc has `stripe_customer_id: 'cus_abc'` -> mock `billingPortal.sessions.create` returns `{ url: 'https://billing.stripe.com/session/...' }` -> 200 with `{ data: { url: '...' } }`
    - **No Firestore document:** `snap.exists` is false -> 404 with `{ error: { code: 'NO_CUSTOMER' } }`
    - **No stripe_customer_id:** doc exists but field is missing -> 404 with `{ error: { code: 'NO_CUSTOMER' } }`
    - **Stripe API error:** `billingPortal.sessions.create` throws -> 500 with `{ error: { code: 'PORTAL_SESSION_FAILED' } }`, `console.error` called with `[subscription/portal` prefix
    - **Unauthenticated:** `withAuth` returns 401 (handled by withAuth itself)
  - [x] 4.4 Verify the `return_url` passed to `billingPortal.sessions.create` ends with `/dashboard`.
  - [x] 4.5 Verify the `customer` param matches the Firestore `stripe_customer_id` value.

- [x] **Task 5: Update HeaderAuthActions tests** (AC: #5)
  - [x] 5.1 Edit [src/components/layout/HeaderAuthActions.test.tsx](src/components/layout/HeaderAuthActions.test.tsx).
  - [x] 5.2 Update existing tests to account for the new rendering:
    - **Loading:** Same as before — no links or buttons rendered (just placeholder)
    - **Not signed in:** Now renders "Home", "Pricing", and "Sign in" links (previously "Sign in" was the only one from this component, Home/Pricing came from Header). Verify all three links with correct `href` values (`/`, `/pricing`, `/auth/sign-in`).
    - **Signed in:** Now renders "Dashboard" link (`href="/dashboard"`) + SignOutButton. Verify "Dashboard" link exists and Home/Pricing/Sign-in do NOT.
  - [x] 5.3 Add a test: signed-in state shows "Dashboard" link pointing to `/dashboard`.
  - [x] 5.4 Add a test: signed-in state does NOT show "Home", "Pricing", or "Sign in" links.

- [x] **Task 6: Update Header tests** (AC: #5)
  - [x] 6.1 Edit [src/components/layout/Header.test.tsx](src/components/layout/Header.test.tsx). Read the file first to understand current test structure.
  - [x] 6.2 The Header component no longer renders static "Home" and "Pricing" links (those moved to HeaderAuthActions). Update or remove tests that assert those links exist directly in Header. The Warden logo link to `/` should still be tested.
  - [x] 6.3 Header.tsx still imports HeaderAuthActions — ensure the mock for that component still works.

- [x] **Task 7: Write SubscriptionCard portal button tests** (AC: #5)
  - [x] 7.1 Edit [src/components/dashboard/SubscriptionCard.test.tsx](src/components/dashboard/SubscriptionCard.test.tsx). Read the file first.
  - [x] 7.2 Add test cases:
    - **Active subscription:** "Manage Subscription" button is rendered
    - **Past_due subscription:** "Manage Subscription" button is rendered
    - **Canceled subscription:** "Manage Subscription" button is rendered
    - **No subscription state:** "Manage Subscription" button is NOT rendered
    - **Loading state:** "Manage Subscription" button is NOT rendered
    - **Error state:** "Manage Subscription" button is NOT rendered
    - **Portal loading state:** Button shows loading text when clicked (mock fetch to hang)
    - **Portal error:** Error text appears below button when API fails (mock fetch to reject)
  - [x] 7.3 Mock `fetch` globally for portal API tests (`vi.stubGlobal('fetch', vi.fn())`).

- [x] **Task 8: Update dashboard page tests** (AC: #5)
  - [x] 8.1 Read [src/app/dashboard/page.test.tsx](src/app/dashboard/page.test.tsx) to check if any tests need updating due to SubscriptionCard changes.
  - [x] 8.2 The SubscriptionCard mock in page tests should still work — the page passes props to SubscriptionCard, and the card's internal portal button behavior is tested in SubscriptionCard.test.tsx. Page tests should not need changes unless the component interface (props) changed — and it hasn't (no new props).
  - [x] 8.3 Verify all 6 existing page tests still pass with no modifications.

- [x] **Task 9: Full-suite regression pass** (AC: #5)
  - [x] 9.1 `npx vitest run` — full suite green. Baseline: 308 tests across 40 files. Target: ~325-335 (new portal route tests + updated header tests + subscription card portal tests).
  - [x] 9.2 `npm run lint` — 0 errors, 0 warnings.

- [x] **Task 10: `npm run build`** (AC: #5)
  - [x] 10.1 `npm run build` — zero type errors.
  - [x] 10.2 Confirm `/api/subscription/portal` appears as `ƒ (Dynamic)` in the route manifest (new route).
  - [x] 10.3 Confirm existing routes (`/api/subscription`, `/api/webhooks/stripe`, `/api/auth/session`, `/api/checkout/session`) still appear in manifest.

- [x] **Task 11: Manual smoke test** (AC: #1, #2, human-verified)
  - [x] 11.1 Start the dev server (`npm run dev`).
  - [x] 11.2 **Test header — signed out:** Visit landing page. Verify header shows: Warden brand text, Home link, Pricing link, Sign in link. *(Note: "Warden" is rendered as text, not an image logo — unchanged from Story 1.3)*
  - [x] 11.3 **Test header — signed in:** Sign in. Verify header shows: Warden brand text, Home link, Dashboard link, Sign out button. Pricing and Sign in links are NOT shown. *(Deviation from original spec: Home link kept visible per user request)*
  - [x] 11.4 **Test Dashboard link:** Click "Dashboard" in header -> navigates to `/dashboard`.
  - [x] 11.5 **Test "Manage Subscription" button:** On dashboard with an active subscription, click "Manage Subscription". Verified: button shows loading state, redirects to Stripe Customer Portal with subscription details.
  - [x] 11.6 **Test portal return:** Click the return link in Stripe Portal. Verified landing back on `/dashboard`.
  - [x] 11.7 **Test no-subscription state:** Dashboard without subscription does NOT show "Manage Subscription" button.
  - [x] 11.8 **Keyboard accessibility:** Tab through header nav links and "Manage Subscription" button. All focusable with visible focus ring.
  - [x] 11.9 Document results in Completion Notes.

## Dev Notes

### Stripe Customer Portal API (SDK v22.0.1)

The `billingPortal.sessions.create()` method requires:
- `customer` (string) — the Stripe Customer ID (stored in Firestore `users/{uid}.stripe_customer_id`)
- `return_url` (string, optional) — where the subscriber goes after leaving the portal

Returns a `Session` object with:
- `url` (string) — the short-lived URL to redirect the subscriber to

The portal session URL is valid for a limited time. The client should redirect immediately after receiving it — do NOT store or cache it.

### Portal Configuration is in Stripe Dashboard

The Customer Portal is configured entirely in the Stripe Dashboard (not in code):
- Enable/disable features: subscription cancellation, plan switching, payment method updates, invoice history
- Set branding: logo, colors, custom return URL
- Set proration behavior for plan switches
- Configure cancellation flows

**Human prerequisite:** Root must configure the portal in the Stripe Dashboard before this story can be fully smoke-tested. The code will work without portal configuration, but the portal will show minimal functionality.

### Why POST (not GET) for Portal Session

The portal session creation is a server-side action that creates a resource in Stripe. POST is semantically correct (creating a new session). GET would be incorrect — the route has side effects (creates a Stripe object). This follows the same pattern as the checkout session route (`POST /api/checkout/session`).

### Header Nav Architecture Decision

The Header component ([Header.tsx](src/components/layout/Header.tsx)) is currently a server component that renders static "Home" and "Pricing" links. HeaderAuthActions is a client component (uses `useAuth()`) that renders auth-dependent content.

Story 5.2 requires the nav links to change based on auth state. Since Header.tsx cannot use client hooks, the auth-conditional links must move into HeaderAuthActions. This is a small refactor:
- Before: Header renders Home, Pricing (static) + HeaderAuthActions renders Sign-in or Sign-out (dynamic)
- After: Header renders only the logo + `<nav>` shell. HeaderAuthActions renders ALL nav links: Home/Pricing/Sign-in (not signed in) or Dashboard/Sign-out (signed in)

This keeps Header as a simple server component and concentrates all auth logic in one client component.

### Stripe Customer ID Source

The `stripe_customer_id` is written to Firestore by the webhook handlers in Stories 4.1-4.3. Specifically:
- `handleInvoicePaid` (Story 4.2) writes `stripe_customer_id` when processing `invoice.paid` events
- The field is available on any user who has completed checkout

Edge case: If a user just completed checkout but the webhook hasn't been processed yet, the Firestore doc may not have `stripe_customer_id`. The API route handles this by returning a 404 with a clear message. The dashboard shows a user-friendly error. This is a transient state — the webhook typically processes within seconds.

### No New Environment Variables

This story uses only existing environment variables:
- `STRIPE_SECRET_KEY` — for Stripe SDK (already configured)
- `NEXT_PUBLIC_APP_URL` — for return URL resolution (already configured)

No changes to `.env.example` needed.

### Firestore `users/{uid}` Document — Fields Used by This Story

```
users/{uid}
  ├── stripe_customer_id: string    ← READ by portal route to create portal session
  └── (all other fields unchanged)
```

### Previous Story Intelligence (from Story 5.1)

- **Testing baseline:** 308/308 passing tests across 40 files. New tests must not break existing ones.
- **Lint baseline:** 0 errors, 0 warnings. Maintain this.
- **`adminDb` is a Proxy.** Any test file importing modules that transitively import `adminDb` must `vi.mock('@/lib/firebase/admin')` BEFORE the import. Story 4.1 Dev Notes.
- **`withAuth` pattern.** Used by subscription route and checkout session route. Returns 401 on auth failure, delegates to handler on success.
- **`import 'server-only'`** at the top of API routes to prevent client-side bundling.
- **`export const runtime = 'nodejs'`** in API routes that use Node.js-specific features (Firebase Admin, Stripe SDK).
- **Mock patterns:** Use `vi.mock` with factory functions. Story 5.1 route test is the closest reference for the portal route test.
- **Structured error responses:** `{ error: { code, message } }` format (architecture.md:343-348).
- **`getStripe()` singleton:** Import from `@/lib/stripe/server` — lazy-initialized Stripe instance.
- **Commit style:** `feat(dashboard): description (Story X.Y)` — use `feat(dashboard):` scope.

### Git Intelligence (recent commit patterns)

Last commits are Story 5.1 (dashboard) and Epic 4 (webhooks). Key patterns:
- Test files co-located next to source
- One test file per behavior unit
- `feat(dashboard):` scope for dashboard-related work

### UX Design Spec Summary (relevant to this story)

- **Button hierarchy:** "Manage billing" is a supporting action → use `variant="outline"` (secondary)
- **Header nav (signed in):** "Dashboard" link replaces Home/Pricing (UX spec line 715)
- **Dashboard status card:** "Action buttons stacked below" the status card (UX spec Implementation Approach table)
- **Stripe redirect pattern:** Full-page redirect, return URL back to WardenWeb (Journey Patterns table)
- **Touch targets:** Min 44x44px on all interactive elements

### Anti-Patterns to Avoid

- **Building custom billing management UI.** Payment history, plan switching, cancellation, payment method updates — ALL handled by Stripe Customer Portal. Do NOT build any of this.
- **Sending `stripe_customer_id` from the client.** The client should never know or send the Stripe Customer ID. The server reads it from Firestore.
- **Caching the portal session URL.** Portal URLs are short-lived. Always create a fresh session on each click.
- **Adding portal configuration in code.** Portal features (which actions are enabled) are configured in Stripe Dashboard, not in `billingPortal.sessions.create()` parameters.
- **Modifying the dashboard layout ([layout.tsx](src/app/dashboard/layout.tsx)).** Layout is unchanged. Auth logic stays in the server component layout.
- **Adding Stripe SDK to client-side code.** All Stripe API calls are server-side.
- **Using `retryStripeCall` for portal session creation.** Retry is for webhook processing, not user-initiated actions.

### Project Structure Notes

- **New files:**
  - `src/app/api/subscription/portal/route.ts` — Task 1 (portal session API)
  - `src/app/api/subscription/portal/route.test.ts` — Task 4 (portal route tests)
- **Modified files:**
  - `src/components/dashboard/SubscriptionCard.tsx` — Task 2 (add "Manage Subscription" button)
  - `src/components/layout/Header.tsx` — Task 3 (remove static nav links, delegate to HeaderAuthActions)
  - `src/components/layout/HeaderAuthActions.tsx` — Task 3 (add conditional nav links + Dashboard link)
  - `src/components/layout/HeaderAuthActions.test.tsx` — Task 5 (update for new nav structure)
  - `src/components/layout/Header.test.tsx` — Task 6 (update for removed static links)
  - `src/components/dashboard/SubscriptionCard.test.tsx` — Task 7 (add portal button tests)
- **Not modified:** `src/app/dashboard/page.tsx`, `src/app/dashboard/page.test.tsx` (no new props), `src/app/dashboard/layout.tsx`, `src/lib/stripe/server.ts`, `src/lib/schemas/subscription.ts`, `.env.example`

### References

- [Epics file — Story 5.2 AC](../planning-artifacts/epics.md) — lines 453-476 (Story 5.2 acceptance criteria)
- [Epics file — Epic 5 approach](../planning-artifacts/epics.md) — lines 160-164 (Portal-First description)
- [Architecture — API Subscription routes](../planning-artifacts/architecture.md) — lines 506-509 (`api/subscription/`)
- [Architecture — Dashboard components](../planning-artifacts/architecture.md) — lines 528-533 (`components/dashboard/`)
- [Architecture — Error Handling](../planning-artifacts/architecture.md) — lines 390-398 (API route try/catch pattern)
- [Architecture — Button Hierarchy](../planning-artifacts/architecture.md) — secondary variant for supporting actions
- [UX Spec — Header nav signed-in](../planning-artifacts/ux-design-specification.md) — line 715 (Dashboard replaces Home/Pricing when signed in)
- [UX Spec — Journey 2: Returning Subscriber](../planning-artifacts/ux-design-specification.md) — lines 497-518 (dashboard → manage billing → portal flow)
- [UX Spec — Dashboard action list](../planning-artifacts/ux-design-specification.md) — line 635 (ghost buttons stacked below status card)
- [UX Spec — Stripe redirect pattern](../planning-artifacts/ux-design-specification.md) — line 594 (full-page redirect, return URL)
- [Story 5.1 — Dev Notes & Completion](./5-1-dashboard-with-account-and-subscription-overview.md) — testing baseline (308/308), SubscriptionCard implementation details, API route patterns
- [Sprint Change Proposal — Epic 5 scope revision](../planning-artifacts/sprint-change-proposal-2026-04-16.md) — portal-first approach rationale
- [Memory: Delegate to Stripe](feedback_delegate_to_stripe.md) — user preference for Stripe-hosted solutions
- [Stripe SDK v22.0.1 — BillingPortal.SessionCreateParams](node_modules/stripe/cjs/resources/BillingPortal/Sessions.d.ts) — API types for `billingPortal.sessions.create()`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Lint caught `useState` called conditionally after early returns — moved hooks to top of SubscriptionCard component before early returns. Fixed immediately.

### Completion Notes List

- **Task 1:** Created `POST /api/subscription/portal` route following withAuth + adminDb + getStripe pattern from existing routes. Returns portal URL on success, 404 for no customer, 500 for Stripe errors. No retry logic (user-initiated action). `import 'server-only'` included.
- **Task 2:** Added "Manage Subscription" button with `variant="outline"`, full-width mobile, loading/error states. Button only renders in subscription-data state (active/past_due/canceled). Portal error displayed as red text below button.
- **Task 3:** Moved Home/Pricing nav links from Header.tsx (server component) into HeaderAuthActions (client component). Signed-in users see Dashboard + Sign out. Signed-out users see Home + Pricing + Sign in. Extracted shared link className to a constant.
- **Tasks 4-7:** Comprehensive test coverage: 7 portal route tests, 5 HeaderAuthActions tests, 7 Header tests, 16 SubscriptionCard tests (including 8 new portal button tests).
- **Task 8:** Dashboard page tests verified — all 6 pass without modification (SubscriptionCard is mocked, no new props).
- **Task 9:** Full regression: 324/324 tests across 41 files. Lint: 0 errors, 0 warnings.
- **Task 10:** Build passes, zero type errors. `/api/subscription/portal` registered as dynamic route.
- **Task 11:** Manual smoke test passed (human-verified 2026-04-16). All 8 checks pass. Deviation from original UX spec: Home link remains visible for signed-in users per user request (users should still be able to navigate to the landing page after signing in).

### Change Log

- 2026-04-16: Implemented Story 5.2 — Stripe Customer Portal integration (Tasks 1-10). Added portal session API route, "Manage Subscription" button on dashboard, auth-conditional header navigation. 324 tests passing, lint clean, build clean.
- 2026-04-16: Code review (adversarial). Fixed 3 issues: (1) HIGH — added typeof validation for `stripe_customer_id` from Firestore, eliminating unsafe `as string` cast; (2) MEDIUM — added `vi.unstubAllGlobals()` cleanup to SubscriptionCard tests to prevent fetch stub leaking; (3) MEDIUM — stored `snap.data()` result once instead of calling twice, consistent with subscription GET route pattern. Added 1 new test for non-string customer ID. 325/325 tests, lint clean. 2 LOW findings documented (no redirect unit test, epics AC not updated for Home link deviation).

### File List

**New files:**
- `src/app/api/subscription/portal/route.ts` — Portal session API route
- `src/app/api/subscription/portal/route.test.ts` — Portal route tests (7 tests)

**Modified files:**
- `src/components/dashboard/SubscriptionCard.tsx` — Added "Manage Subscription" button with loading/error states
- `src/components/dashboard/SubscriptionCard.test.tsx` — Added 8 portal button tests (16 total)
- `src/components/layout/Header.tsx` — Removed static Home/Pricing nav links (delegated to HeaderAuthActions)
- `src/components/layout/Header.test.tsx` — Updated tests for new nav structure (7 tests)
- `src/components/layout/HeaderAuthActions.tsx` — Added conditional Home/Pricing/Sign-in (signed out) and Dashboard (signed in) nav links
- `src/components/layout/HeaderAuthActions.test.tsx` — Updated tests for new rendering (5 tests)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story status: ready-for-dev → in-progress
- `_bmad-output/implementation-artifacts/5-2-stripe-customer-portal-integration.md` — Task checkboxes, Dev Agent Record, File List, Change Log
