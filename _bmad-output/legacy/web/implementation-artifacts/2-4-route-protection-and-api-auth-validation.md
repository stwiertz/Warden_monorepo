# Story 2.4: Route Protection and API Auth Validation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a system,
I want protected routes and API endpoints to require authentication,
So that unauthorized users cannot access subscriber-only features or data.

## Acceptance Criteria

1. **Given** Next.js `proxy.ts` (the Next.js 16 rename of middleware) is configured with `matcher: ['/dashboard/:path*']`
   **When** an unauthenticated request (no `session` cookie) hits any `/dashboard/*` route
   **Then** the proxy redirects the request to `/auth/sign-in?next=<original-path>` (preserves the intended destination)
   **And** on successful sign-in, the user is returned to the originally requested dashboard route
   **And** the proxy only performs an **optimistic presence check** on the session cookie — full cryptographic verification is NOT performed in the proxy (Edge runtime cannot import `firebase-admin`). Per Next.js 16 docs: *"Proxy should not be used as a full session management or authorization solution."*

2. **Given** an authenticated request with a valid session cookie hits `/dashboard/*`
   **When** the proxy runs
   **Then** the request is allowed to proceed (`NextResponse.next()`)
   **And** the dashboard Server Component layout (`src/app/dashboard/layout.tsx`) performs the **authoritative** session cookie verification via `adminAuth.verifySessionCookie(sessionCookie, true /* checkRevoked */)` before rendering any dashboard child page
   **And** if verification fails (expired, revoked, malformed), the layout redirects server-side to `/auth/sign-in?next=/dashboard` using `redirect()` from `next/navigation`
   **And** if verification succeeds, the decoded claims (`uid`, `email`) are made available to child pages (via a typed helper, not prop drilling)

3. **Given** the current `src/app/dashboard/page.tsx` is a client component that does `useEffect` + `router.push('/auth/sign-in')`
   **When** this story is complete
   **Then** the redundant client-side guard is removed (the RSC layout guard is now authoritative and runs before the client renders) — the page can still be a client component for `useAuth()` display purposes, but the `useEffect` redirect block is deleted
   **And** the dashboard page reads `user.email` / `user.displayName` from `useAuth()` as before (no regression in the visible UI)

4. **Given** FR33 requires all `/api/subscription/*` routes to validate authentication
   **When** this story lands
   **Then** a reusable helper `requireSession()` is exported from `src/lib/firebase/auth.ts` that:
   - Reads the `session` cookie via `await cookies()` (async in Next.js 16)
   - Calls `adminAuth.verifySessionCookie(cookie, true)` with revocation check
   - Returns `{ uid, email }` on success
   - Throws a typed `UnauthorizedError` on missing/invalid/revoked cookie
   **And** a helper `withAuth(handler)` wraps a route handler to auto-return the project's standard `{ error: { code: 'UNAUTHORIZED', message: '...' } }` JSON shape with status `401` when `requireSession()` throws
   **And** both helpers have unit tests covering: valid cookie, missing cookie, expired cookie, revoked cookie
   **And** the helpers are documented as the **mandatory** pattern for every future `/api/subscription/*` route (Epic 5)

5. **Given** FR32 requires Firestore rules that restrict users to their own `users/{uid}` document
   **When** this story lands
   **Then** a `firestore.rules` file exists at the project root containing:
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /users/{userId} {
         allow read: if request.auth != null && request.auth.uid == userId;
         allow write: if false;  // All writes go through Admin SDK server-side
       }
       match /{document=**} {
         allow read, write: if false;  // Default deny
       }
     }
   }
   ```
   **And** a `firebase.json` file exists (or is updated) declaring the rules file path so `firebase deploy --only firestore:rules` can deploy them
   **And** the rules file is documented in Dev Notes — deployment to the Firebase project is a MANUAL step (not performed by this story) because credentials/CI for Firebase deploys are out of scope for MVP and will be handled in Epic 5 or via support runbook

6. **Given** FR34 requires Stripe API keys never leak into the client bundle
   **When** this story lands
   **Then** a guard unit test asserts that `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` are **not** prefixed with `NEXT_PUBLIC_` in `.env.example`
   **And** the test also asserts that `FIREBASE_SERVICE_ACCOUNT_KEY` is not `NEXT_PUBLIC_*`
   **And** the `src/lib/firebase/admin.ts` module retains its `import 'server-only'` guard (already present — verify, do not remove)
   **And** no new `lib/stripe/` code is introduced in this story (Stripe client/server SDK initialization belongs to Epic 3)

7. **Given** the sign-in page currently redirects to `/dashboard` on successful auth
   **When** the sign-in page receives a `next` query param (e.g., `/auth/sign-in?next=/dashboard/billing`)
   **Then** after successful sign-in the user is redirected to the `next` path **only if** it is a safe relative path (starts with `/` and does NOT start with `//` or `/\\` — open-redirect protection)
   **And** if `next` is missing or unsafe, it defaults to `/dashboard`

## Tasks / Subtasks

- [x] Task 1: Enhance `proxy.ts` to preserve intended destination on redirect (AC: #1)
  - [x] 1.1 Read `src/proxy.ts` and confirm current matcher is `['/dashboard/:path*']`
  - [x] 1.2 When no `session` cookie present, build redirect URL: `new URL('/auth/sign-in', request.url)` then `.searchParams.set('next', request.nextUrl.pathname + request.nextUrl.search)`
  - [x] 1.3 Do NOT call `adminAuth.verifySessionCookie` in proxy — Edge runtime cannot import `firebase-admin` (Node-only). Keep the check as a lightweight cookie-presence check only.
  - [x] 1.4 Update `src/proxy.test.ts`: add a test asserting the `next` query param is present on the redirect URL; keep existing 4 tests green

- [x] Task 2: Create `src/lib/firebase/auth.ts` server-only auth helpers (AC: #2, #4)
  - [x] 2.1 Create `src/lib/firebase/auth.ts` with `import 'server-only'` as the first line
  - [x] 2.2 Export `class UnauthorizedError extends Error` with `code: 'UNAUTHORIZED' | 'SESSION_EXPIRED' | 'SESSION_REVOKED' | 'NO_SESSION'` discriminant
  - [x] 2.3 Export `async function requireSession(): Promise<{ uid: string; email: string | undefined }>` that:
    - `const cookieStore = await cookies()` (next/headers, async in Next 16)
    - `const sessionCookie = cookieStore.get('session')?.value`
    - Throws `UnauthorizedError` with code `'NO_SESSION'` if absent
    - `const decoded = await adminAuth.verifySessionCookie(sessionCookie, true)` — the `true` enables revocation check
    - On Firebase error, map to `UnauthorizedError` with code `'SESSION_EXPIRED'` (or `'SESSION_REVOKED'` when error message contains `revoked`) — otherwise `'UNAUTHORIZED'`
    - Returns `{ uid: decoded.uid, email: decoded.email }`
  - [x] 2.4 Export `async function getSession(): Promise<{ uid: string; email: string | undefined } | null>` — same as `requireSession` but returns `null` instead of throwing (for cases where presence is optional)
  - [x] 2.5 Export a helper `function unauthorizedResponse(error: UnauthorizedError): Response` that returns `Response.json({ error: { code: error.code, message: 'Authentication required' } }, { status: 401 })` using the project's structured response convention (see `src/app/api/auth/session/route.ts` error shape)
  - [x] 2.6 Export `async function withAuth<T>(handler: (session: { uid: string; email: string | undefined }) => Promise<T>): Promise<T | Response>` — a thin wrapper that calls `requireSession()`, invokes the handler on success, and returns `unauthorizedResponse()` on `UnauthorizedError`. Other errors propagate.
  - [x] 2.7 DO NOT place this in `src/lib/firebase/session.ts` — that file is client-side (imports `firebase/auth` SDK). `auth.ts` is server-only. Keep them separate.

- [x] Task 3: Unit tests for `auth.ts` (AC: #4)
  - [x] 3.1 Create `src/lib/firebase/auth.test.ts`
  - [x] 3.2 Mock `next/headers` `cookies()` to return a controllable cookie store (same pattern as `src/app/api/auth/session/route.test.ts` — check that file for the existing mock shape)
  - [x] 3.3 Mock `@/lib/firebase/admin` — `adminAuth.verifySessionCookie` as `vi.fn()`
  - [x] 3.4 Test cases:
    - `requireSession()` returns `{uid, email}` on valid cookie (mock resolves with `{uid: 'abc', email: 'x@y.z'}`)
    - `requireSession()` throws `UnauthorizedError` with code `'NO_SESSION'` when cookie absent
    - `requireSession()` throws `UnauthorizedError` with code `'SESSION_REVOKED'` when mock rejects with error message containing `revoked`
    - `requireSession()` throws `UnauthorizedError` with code `'SESSION_EXPIRED'` when mock rejects with generic error
    - `getSession()` returns `null` instead of throwing when cookie absent
    - `withAuth()` invokes handler with session on success
    - `withAuth()` returns 401 Response on `UnauthorizedError`
    - `withAuth()` rethrows non-auth errors
    - `verifySessionCookie` is called with `checkRevoked = true` (assert second argument)

- [x] Task 4: Convert `src/app/dashboard/layout.tsx` to authoritative RSC session guard (AC: #2, #3)
  - [x] 4.1 Rewrite `src/app/dashboard/layout.tsx` as an `async` Server Component
  - [x] 4.2 Inside the layout: `try { await requireSession() } catch (err) { if (err instanceof UnauthorizedError) redirect('/auth/sign-in?next=/dashboard'); throw err }`
  - [x] 4.3 `redirect` is imported from `next/navigation`
  - [x] 4.4 Render `<>{children}</>` after the guard passes (no UI chrome needed — existing test only checks pass-through)
  - [x] 4.5 Keep `export const metadata: Metadata = { title: 'Dashboard' }`
  - [x] 4.6 IMPORTANT: the layout is now async — ensure `src/app/dashboard/page.tsx` (still `'use client'`) continues to work as a child. React 19 + Next 16 fully supports this composition.
  - [x] 4.7 Remove the `useEffect` + `router.push('/auth/sign-in')` block from `src/app/dashboard/page.tsx` (now redundant — layout guards server-side). Keep the `loading || !user` skeleton branch because `AuthContext` still hydrates client-side and briefly shows loading on first client render.
  - [x] 4.8 Remove now-unused imports (`useEffect`, `useRouter` if not referenced elsewhere) from `dashboard/page.tsx`

- [x] Task 5: Tests for dashboard layout and page updates (AC: #2, #3)
  - [x] 5.1 Create `src/app/dashboard/layout.test.tsx`:
    - Mock `@/lib/firebase/auth` — `requireSession` as `vi.fn()`
    - Mock `next/navigation` — `redirect` as a `vi.fn()` that throws a sentinel (mirror how Next handles redirect)
    - Test: valid session → renders children
    - Test: `UnauthorizedError` → calls `redirect('/auth/sign-in?next=/dashboard')`
  - [x] 5.2 Update `src/app/dashboard/page.test.tsx`:
    - Remove tests asserting `router.push('/auth/sign-in')` behavior from the page (that logic moved to the layout)
    - Keep tests for: loading skeleton, displaying user info, rendering `SignOutButton`
  - [x] 5.3 Update `src/proxy.test.ts`: add test for `next` query param preservation

- [x] Task 6: Sign-in page — honor safe `next` redirect param (AC: #7)
  - [x] 6.1 Read `src/app/auth/sign-in/page.tsx` and its companion sign-in form component (find it under `src/components/auth/` or similar)
  - [x] 6.2 After `createSessionAndRedirect()` resolves, the redirect target currently hardcodes `/dashboard`. Change the call site (not the `session.ts` helper itself — keep that reusable) to read the `next` query param via `useSearchParams()` and pass a safe value to `router.push`
  - [x] 6.3 Add a small `sanitizeRedirect(next: string | null): string` util that returns `next` only if: (a) non-empty, (b) starts with exactly one `/`, (c) does NOT start with `//` or `/\` (open-redirect defense). Otherwise returns `/dashboard`. Place util in `src/lib/utils.ts` OR inline in the sign-in component — pick whichever keeps the test surface smallest.
  - [x] 6.4 Add unit tests for `sanitizeRedirect`: `/dashboard` → `/dashboard`, `/dashboard/settings?x=1` → preserved, `//evil.com` → `/dashboard`, `/\evil.com` → `/dashboard`, `https://evil.com` → `/dashboard`, `null` → `/dashboard`, `''` → `/dashboard`
  - [x] 6.5 Update the sign-in form test(s) to cover the `next` param path (mock `useSearchParams()` from `next/navigation`)

- [x] Task 7: Add `firestore.rules` and `firebase.json` for FR32 (AC: #5)
  - [x] 7.1 Create `firestore.rules` at project root (exact content in AC #5)
  - [x] 7.2 Create OR update `firebase.json` at project root with:
    ```json
    {
      "firestore": {
        "rules": "firestore.rules"
      }
    }
    ```
  - [x] 7.3 Add a note to Dev Notes (and in the story's Change Log) that the rules are committed as code but NOT deployed by this story — deployment is a manual `firebase deploy --only firestore:rules` step with a Firebase CLI auth'd against the project. Track the manual deploy in a follow-up item for Epic 5 or support runbook.
  - [x] 7.4 DO NOT install `firebase-tools` as a dependency — it's a dev-only CLI, not a runtime dep

- [x] Task 8: Guard test for env-var client/server split (FR34, AC: #6)
  - [x] 8.1 Create `src/lib/env.test.ts` (or add to an existing env helper test if one exists)
  - [x] 8.2 Test reads `.env.example` from project root via `fs.readFileSync`
  - [x] 8.3 Assert no line matches `/^NEXT_PUBLIC_STRIPE_SECRET_KEY/` or `/^NEXT_PUBLIC_STRIPE_WEBHOOK_SECRET/` or `/^NEXT_PUBLIC_FIREBASE_SERVICE_ACCOUNT_KEY/`
  - [x] 8.4 Assert positive presence: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `FIREBASE_SERVICE_ACCOUNT_KEY` all appear (ungated by `NEXT_PUBLIC_`)
  - [x] 8.5 This test is a tripwire — it does not verify any runtime Stripe code (there is none yet), it only enforces the `.env.example` contract so a future dev cannot accidentally regress it

- [x] Task 9: Verification (all ACs)
  - [x] 9.1 `npm run build` passes with no TypeScript errors (async layout must type-check cleanly with Next 16)
  - [x] 9.2 `npm run lint` passes — fix any new lint issues introduced by this story (NOTE: the pre-existing `CookieBanner.tsx` lint error is out of scope per Story 2.3)
  - [x] 9.3 `npm test` — full suite passes. Baseline from Story 2.3 is **119 tests**. This story should add: ~9 in `auth.test.ts`, ~2 in `layout.test.tsx`, ~7 in `sanitizeRedirect`, ~1–2 in `proxy.test.ts`, ~2 in `env.test.ts`. Expected new total: ~139–142. Zero regressions.
  - [x] 9.4 Manual test: sign out → navigate to `/dashboard/settings` → redirected to `/auth/sign-in?next=%2Fdashboard%2Fsettings` → sign in → returned to `/dashboard/settings` (if that route exists; otherwise `/dashboard`)
  - [x] 9.5 Manual test: sign out → navigate to `/dashboard` directly → redirected to `/auth/sign-in?next=%2Fdashboard`
  - [x] 9.6 Manual test: open-redirect defense — hit `/auth/sign-in?next=//evil.com` → sign in → redirected to `/dashboard`, NOT evil.com
  - [x] 9.7 Manual test: tamper with `session` cookie value in DevTools → refresh `/dashboard` → RSC layout redirect to sign-in fires (not just client-side loop)
  - [x] 9.8 Confirm `firestore.rules` and `firebase.json` are staged in commit and call out the manual deploy in the PR description

## Dev Notes

### Architecture Compliance

- **Proxy vs full auth:** Per Next.js 16 docs (`node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md:29`): *"Proxy should not be used as a full session management or authorization solution."* Next.js recommends "optimistic checks" in proxy and authoritative verification in Server Components or Route Handlers. Our split:
  - **Proxy** (`src/proxy.ts`, Edge runtime): presence check on `session` cookie only. Redirect on miss. No Firebase Admin SDK (not compatible with Edge).
  - **RSC layout** (`src/app/dashboard/layout.tsx`, Node runtime): full `verifySessionCookie(cookie, checkRevoked=true)` via `adminAuth`. This is the authoritative gate.
  - **API routes** (`src/app/api/subscription/*`, Node runtime): same full verification via `requireSession()` helper. Defense in depth — routes do NOT trust the proxy.
- **Why two layers:** An attacker who forges/steals the cookie name cannot bypass the RSC layout or API auth even if they get past the proxy. And legitimate users with expired cookies get redirected cleanly from both the proxy (fast) and the RSC (authoritative).
- **`requireSession()` lives in `lib/firebase/auth.ts` (NOT `session.ts`):** `session.ts` imports `firebase/auth` (client SDK) — safe for client components but NOT server-only. `auth.ts` is `import 'server-only'` and uses `firebase-admin`. Mixing them would break the client/server boundary.
- **Existing admin proxy-init pattern (`src/lib/firebase/admin.ts:31-45`):** `adminAuth` is a lazy `Proxy` — reading `verifySessionCookie` from it triggers `initializeApp()` on first use. Respect this; do NOT call `getAuth(...)` directly from `auth.ts`.

### Technical Stack (Verified Versions — from Story 2.3)

- Next.js **16.2.2**, App Router, `src/` directory, `@/*` import alias
- React **19.2.4**
- Tailwind CSS **4** (config in `globals.css`, no `tailwind.config.ts`)
- shadcn/ui **4.1.2** — uses **Base UI** (NOT Radix UI). `asChild` does NOT exist.
- Firebase JS SDK **v12.11.0**
- Firebase Admin SDK **v13.7.0** — `adminAuth.verifySessionCookie(cookie, checkRevoked)` is the authoritative verification call
- Vitest **4.1.3** + React Testing Library
- `next/headers` `cookies()` is **async** in Next.js 16 — always `await cookies()`
- `next/navigation` `redirect()` throws a special error in RSCs — tests mocking `redirect` must account for this
- Test baseline from Story 2.3: **119 passing tests**

### Proxy Behavior in Next.js 16 (CRITICAL)

From `node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md`:

> Starting with Next.js 16, Middleware is now called **Proxy** to better reflect its purpose.

- File lives at `src/proxy.ts` (already correct)
- Exports either a named `proxy` function or a default export
- `export const config = { matcher: [...] }` controls which routes it runs on
- Runs on Edge runtime by default → **no Node-only APIs**, **no `firebase-admin`**
- Fetching with cache options has no effect in proxy — don't try to cache `verifySessionCookie` calls via fetch

### API Route Auth Pattern (to be used by Epic 5)

The helper contract documented here is the MANDATORY pattern for every future `/api/subscription/*` route handler:

```typescript
// src/app/api/subscription/upgrade/route.ts (Epic 5 — example, do NOT implement in this story)
import { withAuth } from '@/lib/firebase/auth'

export async function POST(request: Request) {
  return withAuth(async ({ uid }) => {
    const body = await request.json()
    // ... subscription upgrade logic using uid ...
    return Response.json({ data: { status: 'success' } })
  })
}
```

The `withAuth` wrapper guarantees:
- `session` cookie is present
- Cookie is cryptographically valid (signed by our Firebase project)
- Cookie has NOT been revoked (checkRevoked = true)
- The handler receives the verified `uid` — route handlers must NEVER trust a `uid` from the request body

### Proposed `src/lib/firebase/auth.ts` Shape

```typescript
import 'server-only'

import { cookies } from 'next/headers'

import { adminAuth } from '@/lib/firebase/admin'

const SESSION_COOKIE_NAME = 'session'

type UnauthorizedCode = 'NO_SESSION' | 'SESSION_EXPIRED' | 'SESSION_REVOKED' | 'UNAUTHORIZED'

export class UnauthorizedError extends Error {
  readonly code: UnauthorizedCode
  constructor(code: UnauthorizedCode, message = 'Authentication required') {
    super(message)
    this.code = code
    this.name = 'UnauthorizedError'
  }
}

export interface Session {
  uid: string
  email: string | undefined
}

export async function requireSession(): Promise<Session> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME)?.value

  if (!sessionCookie) {
    throw new UnauthorizedError('NO_SESSION')
  }

  try {
    const decoded = await adminAuth.verifySessionCookie(sessionCookie, true)
    return { uid: decoded.uid, email: decoded.email }
  } catch (err) {
    const message = err instanceof Error ? err.message.toLowerCase() : ''
    if (message.includes('revoked')) throw new UnauthorizedError('SESSION_REVOKED')
    throw new UnauthorizedError('SESSION_EXPIRED')
  }
}

export async function getSession(): Promise<Session | null> {
  try {
    return await requireSession()
  } catch (err) {
    if (err instanceof UnauthorizedError) return null
    throw err
  }
}

export function unauthorizedResponse(error: UnauthorizedError): Response {
  return Response.json(
    { error: { code: error.code, message: 'Authentication required' } },
    { status: 401 },
  )
}

export async function withAuth<T>(
  handler: (session: Session) => Promise<T>,
): Promise<T | Response> {
  try {
    const session = await requireSession()
    return await handler(session)
  } catch (err) {
    if (err instanceof UnauthorizedError) return unauthorizedResponse(err)
    throw err
  }
}
```

### Proposed Dashboard Layout Shape

```typescript
// src/app/dashboard/layout.tsx
import { redirect } from 'next/navigation'
import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import { requireSession, UnauthorizedError } from '@/lib/firebase/auth'

export const metadata: Metadata = {
  title: 'Dashboard',
}

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  try {
    await requireSession()
  } catch (err) {
    if (err instanceof UnauthorizedError) redirect('/auth/sign-in?next=/dashboard')
    throw err
  }

  return <>{children}</>
}
```

### Proposed Proxy Shape

```typescript
// src/proxy.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const SESSION_COOKIE_NAME = 'session'

export function proxy(request: NextRequest) {
  const session = request.cookies.get(SESSION_COOKIE_NAME)

  if (!session) {
    const signInUrl = new URL('/auth/sign-in', request.url)
    signInUrl.searchParams.set(
      'next',
      request.nextUrl.pathname + request.nextUrl.search,
    )
    return NextResponse.redirect(signInUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
```

### Proposed `sanitizeRedirect` Shape

```typescript
// add to src/lib/utils.ts
export function sanitizeRedirect(next: string | null | undefined): string {
  if (!next) return '/dashboard'
  // Must start with exactly one '/'
  if (!next.startsWith('/')) return '/dashboard'
  // Reject protocol-relative ('//evil.com') and backslash tricks ('/\\evil.com')
  if (next.startsWith('//') || next.startsWith('/\\')) return '/dashboard'
  return next
}
```

### Firestore Rules

Exact content for `firestore.rules`:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read: if request.auth != null && request.auth.uid == userId;
      allow write: if false;
    }
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

Rationale:
- `users/{userId}` client reads allowed only when `request.auth.uid == userId` (FR32)
- All client writes blocked — subscription writes happen server-side via Admin SDK from the Stripe webhook handler (bypasses rules). Keeps the client from ever mutating subscription state directly.
- Default-deny on `{document=**}` ensures no other collections are readable/writable until explicitly opened up
- `coupon_batches` will need to be added in Epic 3 when coupon logic is built — NOT in scope for Story 2.4

`firebase.json`:
```json
{
  "firestore": {
    "rules": "firestore.rules"
  }
}
```

**Deployment is a manual step** — `firebase deploy --only firestore:rules` requires the Firebase CLI authenticated against the project. Not automated in this story; flag in PR description.

### File Structure

```
src/
├── proxy.ts                                # MODIFY: preserve 'next' param on redirect
├── proxy.test.ts                           # MODIFY: add 'next' param test
├── app/
│   ├── dashboard/
│   │   ├── layout.tsx                      # MODIFY: convert to async RSC with requireSession guard
│   │   ├── layout.test.tsx                 # NEW: cover RSC guard
│   │   ├── page.tsx                        # MODIFY: remove redundant useEffect redirect
│   │   └── page.test.tsx                   # MODIFY: remove useEffect redirect test, keep UI tests
│   └── auth/
│       └── sign-in/
│           ├── page.tsx                    # MODIFY (or companion client component): honor safe 'next' query param
│           └── <tests>                     # MODIFY: cover 'next' param path
├── lib/
│   ├── firebase/
│   │   ├── auth.ts                         # NEW: server-only requireSession/getSession/withAuth/UnauthorizedError
│   │   └── auth.test.ts                    # NEW: unit tests for the helpers
│   ├── utils.ts                            # MODIFY: add sanitizeRedirect (or co-locate in sign-in page)
│   ├── utils.test.ts                       # NEW or MODIFY: cover sanitizeRedirect
│   └── env.test.ts                         # NEW: tripwire test for .env.example client/server split
firestore.rules                             # NEW: FR32 rules
firebase.json                               # NEW: firebase project config (rules path only)
```

### Testing Requirements

- **Test framework:** Vitest 4.1.3 + React Testing Library
- **Test pattern:** Co-located tests next to source files
- **Mock patterns to reuse:**
  - `vi.mock('next/headers', () => ({ cookies: vi.fn() }))` — same pattern as `src/app/api/auth/session/route.test.ts`
  - `vi.mock('@/lib/firebase/admin', () => ({ adminAuth: { verifySessionCookie: vi.fn() } }))`
  - `vi.mock('next/navigation', () => ({ redirect: vi.fn((path) => { throw new Error(`REDIRECT:${path}`) }) }))` — Next's real `redirect` throws, so the mock should too, to preserve control-flow semantics
  - `vi.mock('next/server')` — see `src/proxy.test.ts` for the existing NextResponse mock pattern
- **Async RSC layout tests:** since the layout is an async function, tests can `await DashboardLayout({ children: <div>ok</div> })` and inspect the returned JSX — no need for full rendering. See how async RSCs are tested in Vitest docs if unsure.
- **What NOT to test:** Real Firebase Admin SDK calls (manual test only), real proxy execution (the existing proxy test already uses NextRequest + NextResponse mocks), real Firestore rules (they are a deploy artifact — rules testing requires `@firebase/rules-unit-testing` + emulator, out of scope for MVP)
- **Coverage target:** at least one happy + one sad + one edge per public function

### Previous Story (2.3) Learnings — CRITICAL for Dev Agent

Carry forward from completed Stories 2.1, 2.2, 2.3. The items below are either (a) still applicable or (b) new lessons specific to this story's surface area.

1. **Next.js 16 renamed middleware to proxy** — file is `src/proxy.ts`, not `src/middleware.ts`. The architecture doc (`architecture.md:185,559,618,624`) references `middleware.ts` but that's pre-rename terminology. Honor the Next 16 naming in code; treat architecture doc references as pointing to the proxy file.
2. **`cookies()` is async in Next 16** — every call site uses `await cookies()`. See `src/app/api/auth/session/route.ts:34,53` for working examples.
3. **`import 'server-only'` must be the FIRST line** — otherwise bundler won't catch accidental client imports at build time. See `src/lib/firebase/admin.ts:1`.
4. **`adminAuth` is a lazy Proxy** — `src/lib/firebase/admin.ts:31-45`. Calls to `adminAuth.verifySessionCookie` trigger `initializeApp` on first access. Safe to use in tests when mocked.
5. **`FIREBASE_SERVICE_ACCOUNT_KEY` is required** — `admin.ts:17-22` throws if unset. Tests must mock `@/lib/firebase/admin` to avoid this.
6. **shadcn/ui = Base UI, not Radix** — `asChild` does NOT exist. No UI components added in this story, but worth remembering for any quick fixes.
7. **No new Firebase `auth` instances** — reuse `@/lib/firebase/client` on the client side and the `adminAuth` Proxy on the server side.
8. **Pre-existing `CookieBanner.tsx` lint error is out of scope** — do NOT fix it as part of this story. Same for the pre-existing `route.test.ts` TypeScript warning called out in Story 2.3.
9. **Spinner/error display patterns from `GoogleSignInButton.tsx`** — not needed in this story (no new buttons), noted for completeness.
10. **Project uses the `{data: ...}` / `{error: {code, message}}` structured response convention** — `unauthorizedResponse()` must follow this. See `src/app/api/auth/session/route.ts:20-24,43,45-48` for working examples.
11. **Zod import convention is `from 'zod/v4'`** — no Zod schemas added in this story, noted in case of drift.
12. **Pre-commit hook runs Prettier + ESLint** on staged files. Don't bypass it.
13. **Read Next.js 16 docs (`node_modules/next/dist/docs/`) before writing ANY Next.js API** (per `AGENTS.md`). This story relies on async layouts, proxy runtime constraints, and `cookies()` async — all of which have docs in the tree.
14. **Test baseline:** Story 2.3 ended at 119 passing tests. This story should not regress any of them.
15. **Commit scope:** `feat(auth): implement route protection and API auth validation (Story 2.4)` follows the convention of commits `848cd3b`, `f3a908f`, `8ceed0c`.

### Security Considerations

- **`checkRevoked = true` is mandatory** on `verifySessionCookie` — without it, a compromised/stolen cookie remains valid until natural expiry even after the user signs out. This is the entire point of the server-side DELETE endpoint in Story 2.3. Do NOT pass `false` or omit the argument.
- **Open-redirect defense:** `sanitizeRedirect` MUST reject `//` and `/\\` prefixes. A naive `startsWith('/')` check is NOT sufficient because `//evil.com` is protocol-relative and will navigate off-site. Also reject full URLs (`https://...`) implicitly via the `startsWith('/')` check.
- **Never trust a `uid` from the request body** — every `/api/subscription/*` route gets its `uid` from `requireSession()`, never from JSON. This is why `withAuth` injects the session into the handler.
- **No CSRF token needed on `/api/subscription/*` GETs** — cookie-based auth on same-origin requests is fine for MVP. If/when state-mutating routes land in Epic 5, revisit (Stripe subscription cancel/upgrade will want either a CSRF token or an origin check).
- **Edge runtime caveat:** DO NOT attempt to import `firebase-admin` in `src/proxy.ts`. It will break the build or fail at Edge runtime. The presence check is all the proxy should do.
- **`firebase.json` does NOT contain credentials** — only points at the rules file. Safe to commit.
- **`firestore.rules` `allow write: if false`** on `users/{userId}` is deliberate — the webhook handler (Epic 4) writes via Admin SDK, which bypasses rules. If a future story needs client writes, it must be a conscious, reviewed change to the rules.

### Anti-Patterns to Avoid

- Do NOT call `adminAuth.verifySessionCookie` inside `src/proxy.ts` — Edge runtime incompatibility
- Do NOT place `requireSession()` in `src/lib/firebase/session.ts` — that file is client-side; use `src/lib/firebase/auth.ts` with `import 'server-only'`
- Do NOT keep the `useEffect` `router.push('/auth/sign-in')` in `dashboard/page.tsx` after the RSC layout guard is added — it's now dead code that flashes briefly on first render
- Do NOT hardcode redirect targets inside `requireSession()` — redirect decisions belong to the caller (the layout or the route handler), keep the helper pure
- Do NOT use `window.location.href` for the post-sign-in redirect — use `router.push(sanitizeRedirect(next))` for consistent Next.js client-side navigation
- Do NOT create `/api/subscription/*` example routes in this story — Epic 5 owns them. The helper + documented contract is the deliverable.
- Do NOT install `firebase-tools` or add a `deploy:rules` script — deployment is a manual support/ops step for now
- Do NOT attempt to test the Firestore rules file from unit tests — that requires the Firebase emulator and `@firebase/rules-unit-testing`, which is out of scope for MVP (can be added in a later story if we get a rules-regression incident)
- Do NOT forget to `await cookies()` — a missing `await` returns a Promise that doesn't have `.get()` and will fail at runtime
- Do NOT mutate `request.cookies` in the proxy — read-only
- Do NOT leak Firebase/Admin SDK error messages to the client — `unauthorizedResponse()` returns a generic `'Authentication required'` string
- Do NOT add a sign-in check to the `/` landing page — it's a public route and should stay public
- Do NOT assume the dashboard page will still work if you remove the client-side `loading || !user` skeleton — keep it, because `AuthContext` needs a tick to hydrate on the client even after the RSC guard passes

### Naming Conventions (from Architecture)

- **Server modules:** camelCase files → `auth.ts`, `admin.ts`
- **Classes/Errors:** PascalCase → `UnauthorizedError`
- **Functions:** camelCase → `requireSession`, `getSession`, `withAuth`, `sanitizeRedirect`
- **Error codes:** UPPER_SNAKE_CASE string literals → `'NO_SESSION'`, `'SESSION_EXPIRED'`, `'SESSION_REVOKED'`, `'UNAUTHORIZED'`

### Import Order Convention

1. React/Next.js imports
2. Third-party libraries (firebase-admin, zod)
3. `@/` project imports
4. Relative imports
5. Type-only imports last

### Prettier Config (enforced by pre-commit hook)

```json
{ "semi": false, "singleQuote": true, "trailingComma": "all", "printWidth": 100, "tabWidth": 2 }
```

### Commit Convention

- Format: `feat(auth): implement route protection and API auth validation (Story 2.4)`
- Scope: `auth`
- Recent commit on branch: `8ceed0c feat(auth): implement sign-out and session destruction (Story 2.3)`

### Project Structure Notes

- `src/lib/firebase/auth.ts` is a NEW file but aligns with the architecture doc's project structure (`architecture.md:541` explicitly lists `lib/firebase/auth.ts` as "Auth helpers (session cookie, token verify)")
- `firestore.rules` and `firebase.json` are new project-root files — the architecture doc (`architecture.md:618`) lists rules/middleware/env as the canonical location for Security (FR32-34). Committing rules-as-code is standard Firebase practice.
- No architecture deviations. The only naming nuance: architecture says "middleware.ts"; Next 16 says "proxy.ts". The code reality (current `src/proxy.ts`) already reflects the rename — continue with that.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.4 (route protection + API auth)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Authentication & Security — Session Management (lines 174-192)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Route Protection (lines 183-187)]
- [Source: _bmad-output/planning-artifacts/architecture.md — API Boundaries (lines 580-585)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Project Structure (lines 537-559)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Security FR32-34 mapping (line 618)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR32, FR33, FR34, NFR7, NFR10]
- [Source: _bmad-output/implementation-artifacts/2-1-firebase-auth-setup-with-google-sign-in.md — createSessionAndRedirect pattern, admin Proxy pattern]
- [Source: _bmad-output/implementation-artifacts/2-2-email-password-sign-in-and-registration.md — Base UI / shadcn caveat, test count baseline]
- [Source: _bmad-output/implementation-artifacts/2-3-sign-out-and-session-destruction.md — destroySessionAndRedirect, test baseline 119]
- [Source: src/proxy.ts — current presence-check proxy to extend]
- [Source: src/proxy.test.ts — existing test mock pattern for NextResponse]
- [Source: src/lib/firebase/admin.ts — adminAuth lazy Proxy, server-only guard]
- [Source: src/app/api/auth/session/route.ts — async cookies() usage, structured error response shape, createSessionCookie call site]
- [Source: src/app/api/auth/session/route.test.ts — cookies() mock pattern to reuse in auth.test.ts]
- [Source: src/app/dashboard/layout.tsx — current pass-through layout to replace]
- [Source: src/app/dashboard/page.tsx — current client-side useEffect guard to remove]
- [Source: src/contexts/AuthContext.tsx — onAuthStateChanged for client hydration rationale]
- [Source: node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md — Proxy is NOT a full auth solution; use optimistic checks only]
- [Source: node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md — matcher config and Edge runtime constraints]
- [Source: AGENTS.md — Next.js 16 breaking changes reminder; read docs before writing Next.js APIs]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6[1m]

### Debug Log References

- `npx vitest run` — 23 files, 149 tests passed (baseline 119 + 30 new)
- `npm run build` — success, TypeScript clean, all pages generated
- `npm run lint` — only pre-existing `CookieBanner.tsx` error (out of scope per Dev Notes)

### Completion Notes List

- Proxy now preserves intended destination as `next` query param (Edge-safe presence check only; no firebase-admin import).
- New `src/lib/firebase/auth.ts` (`import 'server-only'`) exports `UnauthorizedError`, `requireSession`, `getSession`, `unauthorizedResponse`, `withAuth`. `verifySessionCookie` is always invoked with `checkRevoked = true`.
- Dashboard layout is now an async RSC that calls `requireSession()` and redirects to `/auth/sign-in?next=/dashboard` on `UnauthorizedError`. Non-auth errors propagate.
- `dashboard/page.tsx` client `useEffect` redirect removed; loading skeleton retained for AuthContext hydration.
- `sanitizeRedirect` added in `src/lib/utils.ts`. All three sign-in entry points (`EmailSignInForm`, `RegistrationForm`, `GoogleSignInButton`) read `?next=` via `useSearchParams` and sanitize it before passing to `router.push`. `createSessionAndRedirect` helper kept unchanged — call sites wrap the redirect.
- `sign-in/page.tsx` wraps `AuthFormToggle` in `<Suspense fallback={null}>` — required by Next.js 16 prerendering because `useSearchParams` now triggers a CSR bailout.
- `firestore.rules` (FR32) and `firebase.json` committed at project root. **Deployment is manual** via `firebase deploy --only firestore:rules`; out of scope for this story (flag in PR description).
- `src/lib/env.test.ts` is a tripwire asserting `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `FIREBASE_SERVICE_ACCOUNT_KEY` are NOT `NEXT_PUBLIC_`-prefixed in `.env.example` and are present.
- Pre-existing `CookieBanner.tsx` lint error is untouched (out of scope per Story 2.3 guidance).

**Post-review fixes (AI code review, 2026-04-14):**

- **M1 — Error classification:** `requireSession` now switches on Firebase Admin's `err.code` discriminator (`auth/session-cookie-revoked`, `auth/session-cookie-expired`, `auth/id-token-expired`) instead of brittle `err.message.includes('revoked')` matching. Unknown verify failures now correctly map to the `'UNAUTHORIZED'` variant (previously dead).
- **M2 — Preserve intended destination through the RSC layout:** the proxy now sets an `x-warden-pathname` request header on pass-through (`NextResponse.next({ request: { headers } })`). `DashboardLayout` reads it via `headers()` and passes it (sanitized + URL-encoded) as `next=` when redirecting. Users hitting `/dashboard/settings?tab=billing` with a revoked cookie are now sent back to that exact path after sign-in, not `/dashboard`. `PATHNAME_HEADER` is exported from `src/proxy.ts` for layout + test consumption.
- **M3 — Dead `'UNAUTHORIZED'` union member:** now used as the default bucket for unknown Firebase verify errors (see M1).
- **L1 — `env.test.ts` file read moved to `beforeAll`:** a missing `.env.example` now produces a clean failing test instead of a module-load error.
- **L2 — Layout happy-path assertion strengthened:** test now asserts the returned element's `children` reference is the child passed in, not just `defined`. Also added tests for (a) pathname-header preservation in redirect, (b) fallback when header absent, (c) `sanitizeRedirect` rejecting unsafe header values.
- **L3 — Redundant `objectContaining` matcher removed** from the proxy `next`-param preservation test.
- **L4 — `UnauthorizedError` now accepts an `ErrorOptions` third arg and passes `{ cause: err }`** — Firebase's original error is retained in server logs for debugging. Verified via a new `cause` assertion in `auth.test.ts`.

**Post-fix verification:**

- `npx vitest run` — **153 / 153 passing** (149 baseline + 4 new).
- `npm run build` — success, TypeScript clean, all pages generated.
- `npm run lint` — only the pre-existing `CookieBanner.tsx` error remains (explicitly out of scope).

### File List

- `src/proxy.ts` (MODIFIED)
- `src/proxy.test.ts` (MODIFIED)
- `src/lib/firebase/auth.ts` (NEW)
- `src/lib/firebase/auth.test.ts` (NEW)
- `src/lib/utils.ts` (MODIFIED)
- `src/lib/utils.test.ts` (NEW)
- `src/lib/env.test.ts` (NEW)
- `src/app/dashboard/layout.tsx` (MODIFIED)
- `src/app/dashboard/layout.test.tsx` (NEW)
- `src/app/dashboard/page.tsx` (MODIFIED)
- `src/app/dashboard/page.test.tsx` (MODIFIED)
- `src/app/auth/sign-in/page.tsx` (MODIFIED — Suspense boundary)
- `src/components/auth/EmailSignInForm.tsx` (MODIFIED)
- `src/components/auth/EmailSignInForm.test.tsx` (MODIFIED)
- `src/components/auth/RegistrationForm.tsx` (MODIFIED)
- `src/components/auth/RegistrationForm.test.tsx` (MODIFIED)
- `src/components/auth/GoogleSignInButton.tsx` (MODIFIED)
- `src/components/auth/GoogleSignInButton.test.tsx` (MODIFIED)
- `src/components/auth/AuthFormToggle.test.tsx` (MODIFIED — useSearchParams mock)
- `firestore.rules` (NEW)
- `firebase.json` (NEW)

### Change Log

| Date       | Version | Change                                                           |
| ---------- | ------- | ---------------------------------------------------------------- |
| 2026-04-14 | 0.2.0   | Code review fixes (M1–M3, L1–L4): Firebase error codes, pathname preservation in layout, test hardening. 153/153 tests. |
| 2026-04-14 | 0.1.0   | Implemented Story 2.4 — route protection + API auth helpers      |
| 2026-04-14 | 0.1     | Story drafted (ready-for-dev) — proxy hardening, RSC session guard, `requireSession/withAuth` helpers, `firestore.rules`, `.env.example` tripwire test. |
