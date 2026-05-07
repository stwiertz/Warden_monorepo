# Story 5.1: Dashboard with Account and Subscription Overview

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a subscriber,
I want to see my account details and current subscription status on a dashboard,
So that I know what plan I'm on and when my next payment is due.

## Acceptance Criteria

1. **Given** an authenticated subscriber navigates to `/dashboard`
   **When** the dashboard loads
   **Then** the user's account email is displayed (FR13)
   **And** the current subscription plan (monthly/yearly) is displayed with the human-readable label (FR14)
   **And** the subscription status (active, past_due, canceled) is displayed with a visual Badge component using distinct colors per status (FR15): green for `active`, amber for `past_due`, red/neutral for `canceled`
   **And** the next payment date is displayed formatted via `Intl.DateTimeFormat` — no external date library (FR16)
   **And** the dashboard loads within 2s (NFR5)
   **And** the page meets WCAG 2.1 Level A accessibility requirements (NFR17)

2. **Given** the dashboard is loading data
   **When** the Firestore fetch is in progress
   **Then** loading states use Skeleton components matching the layout shape of the subscription card (architecture.md loading-state pattern)
   **And** the Skeleton layout visually matches the real content dimensions so the page does not shift (CLS < 0.1, NFR3)

3. **Given** the subscriber's Firestore `users/{uid}` document is fetched
   **When** the data is received
   **Then** data is fetched via a server-side API route (`GET /api/subscription`) that reads from `users/{uid}` using the admin SDK — **not** via client-side Firestore SDK, maintaining the existing pattern where all Firestore access is server-side
   **And** no `onSnapshot` real-time listeners are used — the fetch is a one-time read on page load (epics.md AC, memory feedback)
   **And** the API route validates the session cookie before reading Firestore (defense in depth, FR33)
   **And** the response is validated with a Zod schema on the client side before rendering

4. **Given** the subscriber has no Firestore `users/{uid}` document (new user who hasn't checked out yet, or checkout webhook hasn't arrived)
   **When** the dashboard loads
   **Then** a "No active subscription" message is displayed
   **And** a CTA button links to `/pricing` to encourage subscription
   **And** the user's account email is still displayed (from auth state, not Firestore)

5. **Given** the existing checkout success banner (`?checkout=success` query param, Story 3.2)
   **When** the dashboard renders
   **Then** the checkout success banner behavior is preserved exactly as-is
   **And** no regression to existing dashboard page tests in [page.test.tsx](src/app/dashboard/page.test.tsx)

6. **Given** the API route encounters a Firestore error
   **When** the dashboard displays
   **Then** a user-friendly error message is shown (not a raw error) with a "Try again" action
   **And** the error does not crash the page — the user info (email, display name) from auth state is still visible
   **And** the error is logged server-side with a `[dashboard/api]` prefix tag including ISO timestamp

7. **Given** the dashboard test suite
   **When** `npx vitest run` is executed
   **Then** the existing 6 tests in [page.test.tsx](src/app/dashboard/page.test.tsx) continue to pass (possibly updated to account for new subscription UI, but no tests removed)
   **And** the existing 5 tests in [layout.test.tsx](src/app/dashboard/layout.test.tsx) continue to pass without modification
   **And** new tests cover: subscription data display (plan, status badge, next date), loading skeleton, no-subscription state, error state, API route response validation
   **And** `npm run build` passes with zero type errors
   **And** `npm run lint` shows 0 errors, 0 warnings

## Tasks / Subtasks

- [x] **Task 1: Create subscription Zod schema for API response** (AC: #3)
  - [x] 1.1 Create [src/lib/schemas/subscription.ts](src/lib/schemas/subscription.ts). This is the schema for the dashboard API response — **not** a webhook payload schema. The file location matches architecture.md:549 (`src/lib/schemas/`).
  - [x] 1.2 Define the schema:
    ```ts
    import { z } from 'zod/v4'

    export const subscriptionResponseSchema = z.object({
      status: z.enum(['active', 'past_due', 'canceled']),
      plan: z.enum(['monthly', 'yearly']),
      current_period_end: z.number(), // Unix timestamp (seconds) — Firestore Timestamp converted server-side
      stripe_customer_id: z.string(),
      stripe_subscription_id: z.string(),
    })

    export type SubscriptionResponse = z.infer<typeof subscriptionResponseSchema>
    ```
  - [x] 1.3 Use `zod/v4` import path — same as all other schema files in the project (Epic 3 standard, [webhook-events.ts:1](src/lib/schemas/webhook-events.ts#L1)).
  - [x] 1.4 The schema validates the **API response** shape, not the raw Firestore document. The API route handles the Firestore `Timestamp` → Unix seconds conversion. The client never sees Firestore types.
  - [x] 1.5 **Do NOT** include `created_at`, `updated_at`, or `firebase_uid` in the response — these are internal fields the dashboard UI does not need.

- [x] **Task 2: Create `GET /api/subscription` route** (AC: #3, #4, #6)
  - [x] 2.1 Create [src/app/api/subscription/route.ts](src/app/api/subscription/route.ts). This is a new route handler in the `/api/subscription/` directory (architecture.md:506-509 already planned this directory).
  - [x] 2.2 Use the `withAuth` helper from [src/lib/firebase/auth.ts](src/lib/firebase/auth.ts) to validate the session cookie. This matches the pattern established in [session/route.ts](src/app/api/auth/session/route.ts) and [checkout session/route.ts](src/app/api/checkout/session/route.ts).
  - [x] 2.3 Implementation:
    ```ts
    import { withAuth } from '@/lib/firebase/auth'
    import { adminDb } from '@/lib/firebase/admin'

    export async function GET() {
      return withAuth(async (session) => {
        const userRef = adminDb.collection('users').doc(session.uid)
        const snap = await userRef.get()

        if (!snap.exists) {
          return Response.json({ data: null }, { status: 200 })
        }

        const data = snap.data()
        return Response.json({
          data: {
            status: data?.status,
            plan: data?.plan,
            current_period_end: data?.current_period_end?.seconds ?? null,
            stripe_customer_id: data?.stripe_customer_id,
            stripe_subscription_id: data?.stripe_subscription_id,
          },
        })
      })
    }
    ```
  - [x] 2.4 When the user has no Firestore document (`!snap.exists`), return `{ data: null }` with status 200 — this is a valid state (user signed up but hasn't subscribed), NOT an error. The client handles this as the "no subscription" state (AC #4).
  - [x] 2.5 Convert `current_period_end` from Firestore `Timestamp` to Unix seconds (`.seconds` property) for JSON serialization. Do NOT send the raw Firestore Timestamp object — it's not JSON-serializable.
  - [x] 2.6 Wrap the Firestore read in a try/catch. On error: `console.error('[dashboard/api ${new Date().toISOString()}] subscription fetch failed:', session.uid, err)` and return `{ error: { code: 'SUBSCRIPTION_FETCH_FAILED', message: 'Unable to load subscription data' } }` with status 500. Follow architecture.md:343-348 structured error response format.
  - [x] 2.7 The route must NOT export a `dynamic` config — it is inherently dynamic because it reads session cookies. Verify it appears as a `ƒ` (Dynamic) route in `npm run build` manifest.
  - [x] 2.8 **Do NOT** import Stripe SDK in this route. The subscription data comes from Firestore, not Stripe. The route has no Stripe dependency.

- [x] **Task 3: Create `useSubscription` hook** (AC: #1, #2, #3, #4, #6)
  - [x] 3.1 Create [src/hooks/useSubscription.ts](src/hooks/useSubscription.ts). This file is planned in architecture.md:556 (`hooks/useSubscription.ts — Fetch subscription data from Firestore`).
  - [x] 3.2 The hook fetches from `GET /api/subscription`, validates the response with `subscriptionResponseSchema`, and returns `{ subscription, loading, error }`:
    ```ts
    import { useEffect, useState } from 'react'
    import { subscriptionResponseSchema, type SubscriptionResponse } from '@/lib/schemas/subscription'

    interface UseSubscriptionResult {
      subscription: SubscriptionResponse | null
      loading: boolean
      error: string | null
    }

    export function useSubscription(): UseSubscriptionResult {
      const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null)
      const [loading, setLoading] = useState(true)
      const [error, setError] = useState<string | null>(null)

      useEffect(() => {
        let cancelled = false

        async function fetchSubscription() {
          try {
            const res = await fetch('/api/subscription')
            if (!res.ok) {
              const body = await res.json().catch(() => ({}))
              throw new Error(body?.error?.message || 'Failed to load subscription')
            }
            const body = await res.json()
            if (!cancelled) {
              if (body.data === null) {
                setSubscription(null)
              } else {
                const parsed = subscriptionResponseSchema.safeParse(body.data)
                if (!parsed.success) {
                  throw new Error('Invalid subscription data')
                }
                setSubscription(parsed.data)
              }
              setLoading(false)
            }
          } catch (err) {
            if (!cancelled) {
              setError(err instanceof Error ? err.message : 'Failed to load subscription')
              setLoading(false)
            }
          }
        }

        fetchSubscription()
        return () => { cancelled = true }
      }, [])

      return { subscription, loading, error }
    }
    ```
  - [x] 3.3 The `cancelled` flag prevents state updates after unmount (React best practice for async effects).
  - [x] 3.4 The hook validates the API response with Zod `safeParse` — defensive against response shape drift. If validation fails, treat as an error (AC #3).
  - [x] 3.5 **Do NOT** add a `refetch` function for V1. The dashboard fetches once on load per the "no real-time listeners" constraint. If Story 5.2 (portal return) needs a refetch, it can reload the page via `router.refresh()`.
  - [x] 3.6 **Do NOT** import any Firebase SDK modules in this hook. It's a pure HTTP fetch to the API route.

- [x] **Task 4: Create `SubscriptionCard` component** (AC: #1, #2, #4)
  - [x] 4.1 Create [src/components/dashboard/SubscriptionCard.tsx](src/components/dashboard/SubscriptionCard.tsx). Create the `src/components/dashboard/` directory (it doesn't exist yet). Architecture.md:528-533 planned this directory.
  - [x] 4.2 The component receives subscription data as props (not a hook — the hook is called in the page):
    ```ts
    interface SubscriptionCardProps {
      subscription: SubscriptionResponse | null
      loading: boolean
      error: string | null
      userEmail: string | null
    }
    ```
  - [x] 4.3 **Loading state:** Render a Card with Skeleton components matching the real content layout:
    - Skeleton for email line (~200px width)
    - Skeleton for plan label + badge (~150px width)
    - Skeleton for next payment date (~180px width)
    The Skeleton shapes must match the real content to prevent CLS (NFR3).
  - [x] 4.4 **No-subscription state** (subscription is null, not loading, no error): Display the user's email (from `userEmail` prop sourced from auth), a "No active subscription" message, and a Button linking to `/pricing` with text "View plans". Use the Card component with a clean layout.
  - [x] 4.5 **Subscription data state:** Display inside a Card:
    - **Email:** from `userEmail` prop (FR13)
    - **Plan:** from `subscription.plan` — display human-readable label using `getPlanLabel()` utility (create in this task or reuse from plans.ts). "Monthly" or "Yearly" (FR14)
    - **Status badge:** from `subscription.status` — use the Badge component from shadcn/ui with distinct styling (FR15):
      - `active`: green badge (success semantic) — text "Active"
      - `past_due`: amber badge (warning semantic) — text "Past due"
      - `canceled`: neutral/muted badge — text "Canceled"
    - **Next payment date:** from `subscription.current_period_end` — format as locale date string using `new Intl.DateTimeFormat('en-GB', { dateStyle: 'long' }).format(new Date(subscription.current_period_end * 1000))` (FR16). Label: "Next payment" for active, "Access until" for canceled, "Payment due" for past_due.
  - [x] 4.6 **Error state:** Display the user's email, an error message, and a "Try again" button that reloads the page (`window.location.reload()`). Do NOT lose the user's auth information on API error (AC #6).
  - [x] 4.7 Use only existing shadcn/ui components: Card, CardHeader, CardTitle, CardContent, Badge, Button, Skeleton. **Do NOT** install new shadcn/ui components.
  - [x] 4.8 Apply the UX design spec's dark theme palette — surface color (`#1A1A1A`) for cards, subtle border (`#333`), 8px radius. The Badge component ([src/components/ui/badge.tsx](src/components/ui/badge.tsx)) has variants: `default`, `secondary`, `destructive`, `outline`, `ghost`, `link` — **none are green or amber**. Use custom `className` overrides on the Badge for status colors:
    - Active: `className="bg-green-500/15 text-green-500 border-transparent"` (green)
    - Past due: `className="bg-amber-500/15 text-amber-500 border-transparent"` (amber)
    - Canceled: use `secondary` variant (muted gray — appropriate for terminal state)
    Do NOT add new variants to `badge.tsx` — use `className` on the instance.
  - [x] 4.9 Accessibility: use semantic HTML — `<dl>` (description list) for the label/value pairs (email, plan, status, next date). Badge text is always present alongside color (color is never the sole indicator — WCAG). All interactive elements min 44x44px touch target.
  - [x] 4.10 Mobile-first: full-width card on mobile, max-width constrained on desktop. One-column layout, no side-by-side within the card.

- [x] **Task 5: Update dashboard page** (AC: #1, #2, #4, #5)
  - [x] 5.1 Edit [src/app/dashboard/page.tsx](src/app/dashboard/page.tsx). The page stays as a `'use client'` component (it uses `useSearchParams()` and `useAuth()`).
  - [x] 5.2 Add the `useSubscription` hook call alongside the existing `useAuth` hook.
  - [x] 5.3 Render the `SubscriptionCard` component, passing `subscription`, `loading`, `error`, and `userEmail` (from `user.email`).
  - [x] 5.4 **Preserve the existing checkout success banner** (`?checkout=success`) exactly as-is. It must render above the SubscriptionCard when the param is present (AC #5).
  - [x] 5.5 **Preserve the SignOutButton** with `variant="outline"`. Place it below the SubscriptionCard.
  - [x] 5.6 Update the loading state: when `auth.loading` is true OR (`auth.user` is null), show the existing Skeleton pattern. When auth is loaded but `subscriptionLoading` is true, the SubscriptionCard handles its own Skeleton internally.
  - [x] 5.7 Remove the existing inline user info display (`user.displayName`, `user.email` text) — these are now shown inside the SubscriptionCard.
  - [x] 5.8 Keep the existing `max-w-md` container width and centered layout.

- [x] **Task 6: Write API route tests** (AC: #7)
  - [x] 6.1 Create [src/app/api/subscription/route.test.ts](src/app/api/subscription/route.test.ts).
  - [x] 6.2 Mock `@/lib/firebase/auth` (provide `withAuth` that invokes the handler with a mock session) and `@/lib/firebase/admin` (provide `adminDb.collection().doc().get()` returning controlled snapshots). Follow the mock patterns from [src/app/api/webhooks/stripe/route.test.ts](src/app/api/webhooks/stripe/route.test.ts) and [src/app/api/checkout/session/route.test.ts](src/app/api/checkout/session/route.test.ts).
  - [x] 6.3 Test cases:
    - **Happy path — active subscription**: mock Firestore doc with `{status: 'active', plan: 'monthly', current_period_end: {seconds: 1735689600}, stripe_customer_id: 'cus_abc', stripe_subscription_id: 'sub_abc'}` → 200 response with matching data, `current_period_end` as number (seconds)
    - **Happy path — canceled subscription**: same but `status: 'canceled'` → 200 with canceled data
    - **No Firestore document**: `snap.exists` is false → 200 with `{ data: null }`
    - **Firestore read error**: mock `.get()` throws → 500 with `{ error: { code: 'SUBSCRIPTION_FETCH_FAILED', message: '...' } }`, `console.error` called with `[dashboard/api` prefix
    - **Unauthenticated**: `withAuth` returns 401 → 401 response (this is handled by `withAuth` itself, just verify the route uses it)
  - [x] 6.4 Verify the response shape matches `subscriptionResponseSchema` for happy-path cases (parse the response body).

- [x] **Task 7: Write `useSubscription` hook tests** (AC: #7)
  - [x] 7.1 Create [src/hooks/useSubscription.test.ts](src/hooks/useSubscription.test.ts).
  - [x] 7.2 Use `vi.stubGlobal('fetch', vi.fn())` to mock the `fetch` call. Use `@testing-library/react`'s `renderHook` + `waitFor` for testing hooks.
  - [x] 7.3 Test cases:
    - **Happy path**: fetch resolves with valid subscription data → hook returns `{ subscription: {...}, loading: false, error: null }`
    - **No subscription**: fetch resolves with `{ data: null }` → hook returns `{ subscription: null, loading: false, error: null }`
    - **Fetch error (network)**: fetch rejects → hook returns `{ subscription: null, loading: false, error: 'Failed to load subscription' }`
    - **API error (500)**: fetch resolves with status 500, error body → hook returns error message from body
    - **Zod validation failure**: fetch resolves with invalid data shape → hook returns error
    - **Loading state**: initially `{ subscription: null, loading: true, error: null }`

- [x] **Task 8: Write SubscriptionCard component tests** (AC: #7)
  - [x] 8.1 Create [src/components/dashboard/SubscriptionCard.test.tsx](src/components/dashboard/SubscriptionCard.test.tsx).
  - [x] 8.2 Test cases:
    - **Loading state**: renders Skeleton components (assert `[data-slot="skeleton"]` elements present)
    - **Active subscription**: displays plan name, "Active" badge (green), next payment date formatted, email
    - **Past_due subscription**: displays "Past due" badge (amber)
    - **Canceled subscription**: displays "Canceled" badge, date label is "Access until" (not "Next payment")
    - **No subscription**: displays "No active subscription", displays "View plans" link/button pointing to `/pricing`, still shows email
    - **Error state**: displays error message, "Try again" button exists, still shows email
    - **Date formatting**: `current_period_end` as Unix seconds is formatted to a readable date string
    - **Accessibility**: status badge text is always present (not color-only)

- [x] **Task 9: Update existing dashboard page tests** (AC: #5, #7)
  - [x] 9.1 Edit [src/app/dashboard/page.test.tsx](src/app/dashboard/page.test.tsx) to account for the new `useSubscription` hook.
  - [x] 9.2 Add a mock for `@/hooks/useSubscription`:
    ```ts
    let mockSubscriptionState = { subscription: null, loading: false, error: null }
    vi.mock('@/hooks/useSubscription', () => ({
      useSubscription: () => mockSubscriptionState,
    }))
    ```
  - [x] 9.3 Update existing tests to set `mockSubscriptionState` as needed. The existing tests should continue to pass with the subscription hook returning a default state.
  - [x] 9.4 Verify the checkout success banner test still passes — the banner must still render when `?checkout=success` is in the URL regardless of subscription state.
  - [x] 9.5 Verify the SignOutButton test still passes.
  - [x] 9.6 **Do NOT modify [layout.test.tsx](src/app/dashboard/layout.test.tsx)** — the layout is unchanged in this story.

- [x] **Task 10: Full-suite regression pass** (AC: #7)
  - [x] 10.1 `npx vitest run` — full suite green. Count should be > 288 (the Story 4.3 baseline). Target roughly 305-315 (new tests across 4 new test files + updated page test).
  - [x] 10.2 `npm run lint` — 0 errors, 0 warnings.

- [x] **Task 11: `npm run build`** (AC: #7, separate task per Epic 3 retro #10)
  - [x] 11.1 `npm run build` — zero type errors.
  - [x] 11.2 Confirm `/api/subscription` appears as `ƒ (Dynamic)` in the route manifest (new route).
  - [x] 11.3 Confirm `/api/webhooks/stripe` still appears as `ƒ (Dynamic) Node runtime` (regression guard from Story 4.1).
  - [x] 11.4 Confirm no routes accidentally disappeared from the manifest.

- [x] **Task 12: Manual smoke test** (AC: #1, #2, #4, human-verified)
  - [x] 12.1 Start the dev server (`npm run dev`).
  - [x] 12.2 **Test no-subscription state:** Sign in with a user that has no Firestore `users/{uid}` document (or a brand-new test user). Verify: dashboard shows email, "No active subscription" message, and "View plans" button linking to `/pricing`.
  - [x] 12.3 **Test active subscription state:** Sign in with the test user from Epic 4's smoke tests (has `status: 'active'` in Firestore). Verify:
    - Email is displayed correctly
    - Plan shows "Monthly" or "Yearly" (matching Firestore `plan` field)
    - Status badge shows "Active" with green styling
    - Next payment date is displayed as a formatted date (not a raw timestamp)
    - Page loads within 2s (subjective check — should be fast since it's one Firestore read)
  - [x] 12.4 **Test checkout success banner:** Navigate to `/dashboard?checkout=success`. Verify the "Subscription started" banner appears above the subscription card.
  - [x] 12.5 **Test loading state:** Throttle network in DevTools → observe Skeleton components appear before data loads.
  - [x] 12.6 **Test past_due state (if available):** If the Epic 4 smoke test left a user with `past_due` status, verify the amber badge displays. Otherwise, manually set `status: 'past_due'` in Firestore Console and reload.
  - [x] 12.7 **Test canceled state:** If available, verify the muted badge and "Access until" date label.
  - [x] 12.8 **Keyboard accessibility:** Tab through the dashboard page. Verify all interactive elements (Sign out button, "View plans" or "Manage billing" links) are focusable with visible orange focus ring.
  - [x] 12.9 Document results in Completion Notes.

## Dev Notes

### Data Fetching Architecture Decision

**Chosen approach: API route + client-side hook** (not server component, not client-side Firestore SDK).

**Why:**
1. **No Firestore client SDK is initialized.** The current codebase ([src/lib/firebase/client.ts](src/lib/firebase/client.ts)) exports only `auth` and `googleProvider` — no Firestore instance. Adding client-side Firestore would require initializing the SDK, adding security rules for reads, and shipping the Firestore JS SDK to the client bundle (~80KB). Overkill for a single read.
2. **Server-side Firestore via admin SDK is the established pattern.** Every Firestore read/write in the codebase (webhook handlers, session creation) uses `adminDb` from [src/lib/firebase/admin.ts](src/lib/firebase/admin.ts). The API route extends this pattern.
3. **The dashboard page is a client component.** It uses `useSearchParams()` and `useAuth()`, both of which require `'use client'`. Converting to a server component would require restructuring the page, extracting the interactive parts, and changing the data flow. The API route approach keeps the existing page shape intact.
4. **`withAuth` provides session validation.** The API route uses the same `withAuth` helper as checkout and auth routes, ensuring consistent auth checks (FR33 defense in depth).

**Trade-off:** One extra HTTP round-trip (client → API route → Firestore → client) vs. a server component that fetches directly. Acceptable because:
- The round-trip is localhost in dev, same-region in production (Vercel serverless + Firestore europe-west)
- NFR5's 2s budget is generous for a single Firestore read + JSON response
- The architecture.md planned for `hooks/useSubscription.ts` as a client-side hook (architecture.md:556)

### Why `current_period_end` is returned as Unix seconds (not ISO string)

The Firestore `Timestamp` object has a `.seconds` property (Unix epoch seconds). The API route extracts this directly. The client multiplies by 1000 to get a JS `Date`-compatible millisecond timestamp.

**Why not ISO string:** Consistency with Stripe's API, which uses Unix timestamps. The dashboard may eventually display Stripe-sourced dates alongside Firestore dates; using the same format avoids conversion asymmetry.

**Why not Firestore Timestamp:** Not JSON-serializable. The `toJSON()` output includes both `_seconds` and `_nanoseconds` which is an implementation detail.

### Firestore `users/{uid}` Document Shape (read by this story)

```
users/{uid}
  ├── status: 'active' | 'past_due' | 'canceled'       ← displayed as Badge
  ├── plan: 'monthly' | 'yearly'                        ← displayed as plan label
  ├── current_period_end: Timestamp                     ← displayed as formatted date
  ├── stripe_subscription_id: string                    ← not displayed (internal)
  ├── stripe_customer_id: string                        ← used by Story 5.2 for portal session
  ├── updated_at: Timestamp (server)                    ← not displayed
  └── created_at: Timestamp (server, only on first create)  ← not displayed
```

Written by: Story 4.2 (`handleInvoicePaid`), Story 4.3 (`handleSubscriptionDeleted`, `handlePaymentFailed`).

### Status Badge Mapping

| Firestore `status` | Badge Text   | Badge Color | Next Date Label |
|---------------------|-------------|-------------|-----------------|
| `active`            | Active      | Green (`#22C55E` / Tailwind `green-500`) | "Next payment" |
| `past_due`          | Past due    | Amber (`#F59E0B` / Tailwind `amber-500`) | "Payment due" |
| `canceled`          | Canceled    | Muted (gray / default Badge variant) | "Access until" |

From UX spec: "Status badge system — colored badges for active/past_due/canceled" (ux-design-specification.md, Journey Patterns table). Badges use text labels + color (not color alone) for WCAG compliance.

### No `onSnapshot` — Intentional

Memory feedback: "fetch on load, validate server-side before mutations; no onSnapshot." The subscription data changes rarely (webhook-driven state updates). Real-time listeners would add complexity (connection management, cleanup) and bandwidth for no UX benefit. If the user makes changes via Stripe Portal (Story 5.2), the dashboard reloads on return, fetching fresh data.

### Dashboard Layout Unchanged

[src/app/dashboard/layout.tsx](src/app/dashboard/layout.tsx) is a server component that validates the session via `requireSession()`. This story does NOT modify it. The layout's auth check is the first line of defense; the API route's `withAuth` is the second (belt and braces — if middleware or layout auth is somehow bypassed, the API route still rejects unauthenticated requests).

### Previous Story Intelligence (from Epic 4)

- **Testing baseline:** 288/288 passing tests across 37 files (post-Story 4.3). New tests in this story must not break existing ones.
- **Lint baseline:** 0 errors, 0 warnings. Maintain this.
- **`adminDb` is a Proxy.** Any test file importing modules that transitively import `adminDb` must `vi.mock('@/lib/firebase/admin')` BEFORE the import. Story 4.1 Dev Notes. Task 6.2 handles this for the API route test.
- **Vitest file-parallelism flake is latent.** Epic 3 retro #6. If full suite flakes, fall back to `--no-file-parallelism`.
- **Plain-function mock patterns.** Use `vi.mock` with factory functions, not `vi.spyOn` on default exports. Story 4.x established this.
- **Structured error responses.** Follow `{ error: { code, message } }` format from architecture.md:343-348. Story 4.1 route handler is the canonical example.
- **`withAuth` pattern.** Used by [checkout session/route.ts](src/app/api/checkout/session/route.ts). Returns 401 on auth failure, delegates to handler on success.
- **`server-only` import.** The API route needs `import 'server-only'` at the top to prevent accidental client-side bundling of `adminDb`. Follow the pattern in [src/lib/firebase/auth.ts](src/lib/firebase/auth.ts).

### Git Intelligence (recent commit patterns)

Last 5 commits are all Epic 4 webhook work. Key patterns established:
- Commit style: `feat(scope): description (Story X.Y)` — use `feat(dashboard):` scope for this story
- Test files co-located next to source (not in `__tests__/` directories)
- One test file per behavior unit

### UX Design Spec Summary (relevant to this story)

From [ux-design-specification.md](ux-design-specification.md):
- **Direction A: Clean Minimal** — dark theme, surface cards (`#1A1A1A`), subtle borders (`#333`), 8px radius
- **Dashboard:** "Single status card with label/value rows, action buttons stacked below" (Component Strategy table)
- **Loading:** "Skeleton card matching status card shape" (Loading & Empty States table)
- **No subscription:** "Dashboard shows 'No active subscription' + link to pricing" (Loading & Empty States table)
- **Typography:** Inter font, H1 2rem mobile / 3rem desktop, body 1rem
- **Touch targets:** Min 44x44px on all interactive elements
- **One primary CTA per page section** — "View plans" for no-subscription, "Manage billing" for active (Story 5.2 will add the latter)

### Anti-Patterns to Avoid

- **Adding client-side Firestore SDK.** All Firestore access stays server-side via admin SDK. Do NOT initialize `getFirestore()` in `client.ts`.
- **Using `onSnapshot` or real-time listeners.** One-time fetch only. Memory feedback is explicit about this.
- **Building subscription management UI (upgrade, cancel, payment history).** That's Stories 5.2 (portal) and 5.3 (warning banner). This story is display-only.
- **Adding Stripe SDK to the dashboard page or API route.** Subscription data comes from Firestore, not Stripe. Stripe portal integration is Story 5.2.
- **Creating a `loading.tsx` file for the dashboard route.** The existing page handles its own loading state via client-side Skeleton rendering. A `loading.tsx` Suspense boundary would flash between the layout's server-side auth check and the page's client-side render, causing visual jank.
- **Modifying the dashboard layout.** Layout is unchanged. Auth logic stays in the server component layout; data fetching is in the client component page.
- **Using external date formatting libraries (date-fns, luxon, dayjs).** `Intl.DateTimeFormat` is sufficient and already specified in architecture.md:358 ("Dates in UI: `Intl.DateTimeFormat`"). Zero bundle cost.
- **Adding `revalidate` or `use cache` to the API route.** Subscription data must be fresh on every load (webhook-driven state). Caching would show stale status.

### Project Structure Notes

- **New files:**
  - [src/lib/schemas/subscription.ts](src/lib/schemas/subscription.ts) — Task 1 (API response Zod schema)
  - [src/app/api/subscription/route.ts](src/app/api/subscription/route.ts) — Task 2 (API route)
  - [src/hooks/useSubscription.ts](src/hooks/useSubscription.ts) — Task 3 (client hook)
  - [src/components/dashboard/SubscriptionCard.tsx](src/components/dashboard/SubscriptionCard.tsx) — Task 4 (display component)
  - [src/app/api/subscription/route.test.ts](src/app/api/subscription/route.test.ts) — Task 6
  - [src/hooks/useSubscription.test.ts](src/hooks/useSubscription.test.ts) — Task 7
  - [src/components/dashboard/SubscriptionCard.test.tsx](src/components/dashboard/SubscriptionCard.test.tsx) — Task 8
- **Modified files:**
  - [src/app/dashboard/page.tsx](src/app/dashboard/page.tsx) — Task 5 (integrate hook + component)
  - [src/app/dashboard/page.test.tsx](src/app/dashboard/page.test.tsx) — Task 9 (add useSubscription mock)
- **Not modified:** [src/app/dashboard/layout.tsx](src/app/dashboard/layout.tsx), [src/app/dashboard/layout.test.tsx](src/app/dashboard/layout.test.tsx), [src/lib/firebase/client.ts](src/lib/firebase/client.ts), [src/lib/firebase/admin.ts](src/lib/firebase/admin.ts), [src/lib/stripe/*](src/lib/stripe/) (nothing in Stripe lib), `.env.example` (no new env vars).

### References

- [Epics file — Story 5.1 AC](../planning-artifacts/epics.md) — lines 434-451 (Story 5.1 acceptance criteria)
- [Epics file — Epic 5 approach](../planning-artifacts/epics.md) — lines 160-164 (Portal-First description)
- [Architecture — Dashboard route](../planning-artifacts/architecture.md) — lines 490-493 (`app/dashboard/`)
- [Architecture — API Subscription routes](../planning-artifacts/architecture.md) — lines 506-509 (`api/subscription/`)
- [Architecture — useSubscription hook](../planning-artifacts/architecture.md) — line 556 (`hooks/useSubscription.ts`)
- [Architecture — Dashboard components](../planning-artifacts/architecture.md) — lines 528-533 (`components/dashboard/`)
- [Architecture — Naming Conventions](../planning-artifacts/architecture.md) — lines 303-322 (snake_case Firestore, camelCase code)
- [Architecture — Error Handling](../planning-artifacts/architecture.md) — lines 390-398 (API route try/catch pattern)
- [Architecture — Data Exchange Formats](../planning-artifacts/architecture.md) — lines 355-361 (Firestore snake_case, frontend camelCase, `Intl.DateTimeFormat`)
- [Architecture — Loading State Pattern](../planning-artifacts/architecture.md) — lines 382-385 (Skeleton + loading booleans)
- [UX Spec — Dashboard component strategy](../planning-artifacts/ux-design-specification.md) — lines 629-635 (SubscriptionCard, PaymentWarning compositions)
- [UX Spec — Status badge system](../planning-artifacts/ux-design-specification.md) — lines 596, 349-363 (color system, badge colors)
- [UX Spec — Loading & Empty States](../planning-artifacts/ux-design-specification.md) — lines 729-735 (no-subscription state, loading skeleton)
- [UX Spec — Journey 2: Returning Subscriber](../planning-artifacts/ux-design-specification.md) — lines 497-518 (dashboard visit flow)
- [Story 4.3 — Completion Notes](./4-3-process-subscription-deleted-and-payment-failed-webhooks.md) — testing baseline (288/288), lint baseline (0/0)
- [Story 4.2 — handleInvoicePaid](./4-2-process-invoice-paid-webhook-to-activate-subscriptions.md) — Firestore document creation/update shape (the source of truth for what fields exist)
- [Sprint Change Proposal — Epic 5 scope revision](../planning-artifacts/sprint-change-proposal-2026-04-16.md) — portal-first approach rationale
- [Memory: Delegate to Stripe](feedback_delegate_to_stripe.md) — user preference for Stripe-hosted solutions
- [Memory: No real-time Firestore listeners](feedback_no_realtime_listeners.md) — no onSnapshot on dashboard

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Code review fixes applied (2026-04-16): H1 timezone-safe date formatting, M1 added `runtime = 'nodejs'`, M2 server-side Zod validation for partial docs, M3 updated File List with planning artifacts
- Tasks 1–11 implemented and verified (2026-04-16)
- Created Zod schema for subscription API response (`subscriptionResponseSchema`)
- Created `GET /api/subscription` route with `withAuth`, Firestore read, structured error response
- Created `useSubscription` hook with fetch, Zod validation, cancellation guard
- Created `SubscriptionCard` component with loading/error/no-sub/active/past_due/canceled states
- Updated dashboard page to integrate hook + component, preserved checkout success banner
- 5 API route tests, 6 hook tests, 8 component tests, 6 updated page tests — all green
- Full suite: 308/308 tests across 40 files (up from 288 baseline)
- Lint: 0 errors, 0 warnings
- Build: zero type errors, `/api/subscription` appears as `ƒ (Dynamic)` in manifest
- Task 12 (manual smoke) verified by user — dashboard loads with subscription data, checkout banner works, API responds 200 in ~275ms (Firestore latency from local dev to europe-west, acceptable in prod)

### File List

**New files:**
- src/lib/schemas/subscription.ts
- src/app/api/subscription/route.ts
- src/app/api/subscription/route.test.ts
- src/hooks/useSubscription.ts
- src/hooks/useSubscription.test.ts
- src/components/dashboard/SubscriptionCard.tsx
- src/components/dashboard/SubscriptionCard.test.tsx

**Modified files:**
- src/app/dashboard/page.tsx
- src/app/dashboard/page.test.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/sprint-change-proposal-2026-04-16.md (new)
