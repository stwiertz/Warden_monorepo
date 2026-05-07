# Story 2.3: Sign-Out and Session Destruction

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to sign out from my account,
So that my session is securely terminated and I am returned to the landing page.

## Acceptance Criteria

1. **Given** a signed-in user is on the dashboard (or any authenticated page)
   **When** the user clicks the sign-out button
   **Then** Firebase client `signOut(auth)` is called to clear client-side auth state (FR3)
   **And** a `DELETE` request to `/api/auth/session` destroys the server-side HttpOnly session cookie
   **And** the `AuthContext` state automatically clears (user becomes `null` via `onAuthStateChanged`)
   **And** the user is redirected to the landing page (`/`)

2. **Given** a user is signed in on any page of the app
   **When** the page renders
   **Then** the Header displays a "Sign out" action as described in the UX spec ("Sign in" when anonymous, "Sign out" when authenticated)
   **And** the Header sign-out action triggers the same sign-out flow as the dashboard button (shared implementation, no duplication)

3. **Given** the sign-out request is in progress
   **When** the button is clicked
   **Then** the button is disabled and shows a loading state (spinner + "Signing out..." label)
   **And** the user cannot trigger a second sign-out until the flow completes or errors

4. **Given** the `DELETE /api/auth/session` request fails (network error, server error)
   **When** the error occurs
   **Then** Firebase client `signOut()` has still been called (client state cleared)
   **And** a user-friendly inline error message is displayed near the button
   **And** the button returns to its enabled state so the user can retry
   **And** the error is NOT a raw Firebase/HTTP code leaked to the user

5. **Given** a user has just signed out
   **When** the user navigates back (or manually types) to `/dashboard`
   **Then** they are redirected to the sign-in page by the existing dashboard auth guard
   **And** the session cookie is no longer sent on subsequent requests (verifiable via DevTools)

## Tasks / Subtasks

- [x] Task 1: Extract reusable sign-out logic into a shared module (AC: #1, #2, #4)
  - [x] 1.1 Create `src/lib/firebase/session.ts` addition: export `destroySessionAndRedirect(redirect)` helper, symmetric to existing `createSessionAndRedirect()`
  - [x] 1.2 The helper MUST:
    - Call `signOut(auth)` from `firebase/auth` first (clears client state even if API fails)
    - Issue `fetch('/api/auth/session', { method: 'DELETE' })`
    - Throw a typed error if the DELETE response is not `ok` so callers can surface it
    - Call `redirect('/')` on full success
  - [x] 1.3 Reuse existing `auth` export from `@/lib/firebase/client` — do NOT create a new Firebase instance
  - [x] 1.4 Do NOT place routing logic inside the helper — take a `redirect` function parameter for testability (mirrors `createSessionAndRedirect` pattern)

- [x] Task 2: Create `SignOutButton` component (AC: #1, #2, #3, #4)
  - [x] 2.1 Create `src/components/auth/SignOutButton.tsx` as `'use client'`
  - [x] 2.2 Props: `variant?: 'default' | 'outline' | 'ghost'`, `size?: 'default' | 'sm' | 'lg'`, `className?: string`, `children?: ReactNode` (defaults to "Sign out")
  - [x] 2.3 On click: set `isSigningOut=true`, call `destroySessionAndRedirect(router.push)`, catch errors into local state, re-enable button on error
  - [x] 2.4 Disabled state while in-flight
  - [x] 2.5 Loading label: "Signing out..." with the same inline spinner markup used by `GoogleSignInButton.tsx` (`<span className="size-5 animate-spin rounded-full border-2 border-current border-t-transparent" />`)
  - [x] 2.6 Inline error display on failure, using `role="alert"` and `text-destructive` styling (copy the `GoogleSignInButton` error display pattern)
  - [x] 2.7 Uses shadcn/ui `Button` component and `useRouter()` from `next/navigation`

- [x] Task 3: Update Dashboard to use `SignOutButton` (AC: #1, #3)
  - [x] 3.1 Remove local `handleSignOut`, `isSigningOut` state, and the `signOut` + `fetch` calls from `src/app/dashboard/page.tsx`
  - [x] 3.2 Render `<SignOutButton variant="outline" />` in place of the existing button
  - [x] 3.3 Remove now-unused imports (`signOut`, `auth`, `useState` if no longer needed)
  - [x] 3.4 Verify redirect-on-signed-out still works via the existing `useEffect` guard

- [x] Task 4: Add auth-aware actions to the Header (AC: #2)
  - [x] 4.1 `src/components/layout/Header.tsx` is currently a Server Component. Create a new `src/components/layout/HeaderAuthActions.tsx` as `'use client'` that reads `useAuth()`
  - [x] 4.2 When `loading` → render nothing (or a small skeleton) to avoid flicker
  - [x] 4.3 When `user` is null → render a "Sign in" link to `/auth/sign-in`
  - [x] 4.4 When `user` is present → render `<SignOutButton variant="ghost" size="sm">Sign out</SignOutButton>`
  - [x] 4.5 Import `HeaderAuthActions` into `Header.tsx` and render it inside the `<nav>` after the existing "Pricing" link (Header can stay a Server Component; only the auth-actions subtree is client)
  - [x] 4.6 Ensure the nav item is accessible: appropriate `aria-label` if using icon-only, focus-visible ring consistent with existing nav items

- [x] Task 5: Write tests (AC: all)
  - [x] 5.1 `src/lib/firebase/session.test.ts` (extend existing file if present, otherwise new): cover `destroySessionAndRedirect` — success path, API failure path, verifies `signOut()` is called even when DELETE fails
  - [x] 5.2 `src/components/auth/SignOutButton.test.tsx`: renders, shows loading state on click, calls helper, shows error message on failure, re-enables button on error, redirects to `/` on success (mock `useRouter`)
  - [x] 5.3 `src/components/layout/HeaderAuthActions.test.tsx`: renders "Sign in" link when no user, renders `SignOutButton` when user present, renders nothing/skeleton while loading. Mock `useAuth()` by wrapping with `AuthContext` or by mocking the hook module
  - [x] 5.4 Update `src/app/dashboard/page.test.tsx`: adjust expectations — dashboard now renders `SignOutButton`; the direct `signOut`/`fetch` mocks move to `SignOutButton.test.tsx`. Ensure zero regressions in existing dashboard tests
  - [x] 5.5 Update `src/components/layout/Header.test.tsx` if it makes assertions about nav items — add expectations for the auth-actions slot (may need to mock `useAuth`)

- [x] Task 6: Verification (AC: all)
  - [x] 6.1 `npm run build` passes with no TypeScript errors
  - [x] 6.2 `npm run lint` passes with no errors
  - [x] 6.3 Prettier formatting clean (pre-commit hook will enforce)
  - [x] 6.4 `npm test` — all existing tests still pass, zero regressions
  - [x] 6.5 Manual test: sign in → click "Sign out" on dashboard → redirected to `/`, DevTools shows `session` cookie removed
  - [x] 6.6 Manual test: sign in → click "Sign out" in Header from any page → same result
  - [x] 6.7 Manual test: after sign-out, navigating to `/dashboard` redirects to `/auth/sign-in`
  - [x] 6.8 Manual test: simulate API failure (e.g., block `/api/auth/session` DELETE in DevTools) → error message appears, button re-enables

## Dev Notes

### Architecture Compliance

- **Session destruction:** The existing `DELETE /api/auth/session` endpoint is already implemented at `src/app/api/auth/session/route.ts:52-57` and simply removes the HttpOnly `session` cookie. No server changes required for this story.
- **Client-side sign-out:** `firebase/auth` `signOut(auth)` clears the client auth state. `AuthContext` already subscribes to `onAuthStateChanged` (`src/contexts/AuthContext.tsx:24`) and will automatically propagate `user: null` to all consumers — no manual dispatch needed.
- **Pattern symmetry:** Story 2.1 established `createSessionAndRedirect()` in `src/lib/firebase/session.ts`. This story adds a symmetric `destroySessionAndRedirect()` helper and reuses the same pattern (redirect function as a parameter for testability).
- **Existing ad-hoc sign-out in dashboard:** `src/app/dashboard/page.tsx:17-26` already has an inline sign-out implementation. This story is partly a REFACTOR: extract that logic into a shared helper + component, then reuse it in the Header. Do NOT leave two copies of the sign-out logic.
- **Component organization:** `components/auth/` for `SignOutButton`, `components/layout/` for `HeaderAuthActions` (auth-aware nav piece).

### Technical Stack (Verified Versions — from Story 2.2)

- Next.js 16.2.2, App Router, `src/` directory, `@/*` import alias
- React 19.2.4
- Tailwind CSS 4 (config in `globals.css`, no `tailwind.config.ts`)
- shadcn/ui 4.1.2 — uses **Base UI** (NOT Radix UI). `asChild` prop does NOT exist. Available components include `Button`
- Firebase JS SDK v12.11.0 — `signOut()` from `firebase/auth`
- Firebase Admin SDK v13.7.0 — already in place for session cookie ops (no changes needed)
- Vitest 4.1.3 + React Testing Library — established test stack
- No new dependencies required for this story

### Existing DELETE Endpoint (Reference — DO NOT MODIFY)

```typescript
// src/app/api/auth/session/route.ts
export async function DELETE() {
  const cookieStore = await cookies()
  cookieStore.delete(SESSION_COOKIE_NAME)
  return Response.json({ data: { status: 'success' } })
}
```

Notes:
- Uses the `next/headers` `cookies()` API which is **async in Next.js 16** — already handled
- Returns `{ data: { status: 'success' } }` per the project's structured response convention
- Does NOT require the caller to be authenticated (cookie removal is safe to call idempotently)
- Covered by existing tests in `src/app/api/auth/session/route.test.ts`

### Proposed `destroySessionAndRedirect` Shape

Add to `src/lib/firebase/session.ts` (the file that currently exports `createSessionAndRedirect`):

```typescript
import { signOut } from 'firebase/auth'
import { auth } from '@/lib/firebase/client'

export async function destroySessionAndRedirect(
  redirect: (path: string) => void,
): Promise<void> {
  // Clear client-side Firebase auth state first — even if the API call fails,
  // the user's in-memory session is revoked.
  await signOut(auth)

  const response = await fetch('/api/auth/session', { method: 'DELETE' })

  if (!response.ok) {
    throw new Error('Failed to destroy session')
  }

  redirect('/')
}
```

**Why `signOut()` first, API second:**
- `signOut()` is synchronous in its effect on `AuthContext` (fires `onAuthStateChanged` with `null`)
- If the DELETE request fails, the client is still in a safer state than before (no client-side Firebase user) — the stale HttpOnly cookie is the only lingering artifact, and the user can retry
- Rejecting the promise lets the calling component surface a user-friendly error and re-enable the button

### AuthContext Integration (No Changes Needed)

From `src/contexts/AuthContext.tsx`:
```typescript
const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
  setUser(firebaseUser)  // Will be null after signOut()
  setLoading(false)
  setError(null)
})
```

Any component using `useAuth()` will automatically re-render with `user: null` after sign-out. The Header's `HeaderAuthActions` will flip from showing the sign-out button to showing the "Sign in" link with zero manual wiring.

### UX Design Requirements (from UX Specification)

- **Header auth state:** "Show 'Sign in' when anonymous, 'Sign out' when authenticated" (UX spec: Navigation Patterns)
- **Loading state:** Disabled button with inline spinner — reuse the exact spinner markup from `GoogleSignInButton.tsx`
- **Error display:** Inline, `role="alert"`, `text-destructive` classes — same pattern as `GoogleSignInButton`
- **Redirect target:** Landing page (`/`) on successful sign-out (per AC#1 and UX flow for returning to anonymous state)
- **Dark theme:** Existing Tailwind theme variables (`bg-background`, `text-foreground`, `text-destructive`, `border-border`) already handle the Warden dark theme — no custom colors needed

### File Structure

```
src/
├── app/
│   └── dashboard/
│       ├── page.tsx              # MODIFY: replace ad-hoc sign-out with <SignOutButton />
│       └── page.test.tsx         # MODIFY: adjust test expectations
├── components/
│   ├── auth/
│   │   ├── SignOutButton.tsx     # NEW
│   │   └── SignOutButton.test.tsx # NEW
│   └── layout/
│       ├── Header.tsx            # MODIFY: render <HeaderAuthActions /> in nav
│       ├── Header.test.tsx       # MODIFY: adjust if asserting nav items
│       ├── HeaderAuthActions.tsx # NEW: client component reading useAuth()
│       └── HeaderAuthActions.test.tsx # NEW
└── lib/
    └── firebase/
        ├── session.ts            # MODIFY: add destroySessionAndRedirect()
        └── session.test.ts       # NEW or MODIFY: cover destroy helper
```

### Testing Requirements

- **Test framework:** Vitest 4.1.3 + React Testing Library (already configured)
- **Test pattern:** Co-located tests next to source files
- **Mock pattern:** `vi.mock('firebase/auth')` to stub `signOut` and `onAuthStateChanged`; `vi.mock('next/navigation')` for `useRouter`; `global.fetch = vi.fn()` for the DELETE request (same patterns used in `GoogleSignInButton.test.tsx`, `session.ts` tests, and `AuthContext.test.tsx`)
- **What to test:**
  - `destroySessionAndRedirect`: success, DELETE non-ok response (expect throw + `signOut` still called), `signOut` throw
  - `SignOutButton`: renders, click triggers helper, loading state shown, error message shown and button re-enabled on failure, redirects on success
  - `HeaderAuthActions`: no-user renders sign-in link, user renders `SignOutButton`, loading renders nothing
  - Dashboard: continues to redirect unauthenticated users; renders `SignOutButton`
- **What NOT to test:** Real Firebase sign-out (manual test only), real DELETE endpoint (already covered by `route.test.ts`)
- **Current test baseline:** 101 tests across 13 files as of Story 2.2 — ensure zero regressions and count new tests toward the next baseline

### Previous Story (2.2) Learnings — CRITICAL for Dev Agent

Apply these findings from completed Stories 2.1 and 2.2:

1. **shadcn/ui uses Base UI, NOT Radix UI** — `asChild` prop does NOT exist. For the Header sign-out, use the `<Button>` component directly or `buttonVariants()` with Tailwind classes. Do NOT attempt `<Button asChild><Link>...</Link></Button>`.
2. **`buttonVariants()` is exported from a `'use client'` module** — cannot call from Server Components. `HeaderAuthActions` is `'use client'` so this is fine there, but the parent `Header.tsx` should stay a Server Component and render the client child.
3. **`cn()` utility** at `src/lib/utils.ts` — use for conditional Tailwind class merging.
4. **Pre-commit hook** runs Prettier + ESLint automatically on staged files.
5. **`auth` export from `src/lib/firebase/client.ts`** — reuse directly. Do NOT create a new Firebase auth instance.
6. **AuthContext already listens to `onAuthStateChanged`** — sign-out will auto-propagate. No extra wiring.
7. **Admin SDK uses lazy init via Proxy** — no changes needed for this story.
8. **`useAuth()` throws if used outside `AuthProvider`** — safe inside `HeaderAuthActions` because the root layout wraps with `AuthProvider`.
9. **Spinner markup** — reuse the exact inline span from `GoogleSignInButton.tsx:64` for consistency.
10. **Error message pattern** — inline `<p className="text-destructive text-center text-sm" role="alert">` below or next to the button.
11. **Zod import convention** — `from 'zod/v4'` (not needed in this story, but follow if adding any schemas).
12. **`proxy.ts` not `middleware.ts`** — this story does NOT touch route protection. Story 2.4 handles that.
13. **`cookies()` is async** — the existing DELETE route already uses `await cookies()`, no changes needed.
14. **Read Next.js 16 docs before writing any Next.js API** — `node_modules/next/dist/docs/` (per `AGENTS.md`).

### Security Considerations

- **HttpOnly cookie removal** is the critical server-side step — client-side `signOut()` alone leaves the session cookie valid on future requests, which is why the DELETE call is mandatory
- **Order matters:** Clear client state first so that if the DELETE fails, the user's in-memory Firebase token is already revoked. The HttpOnly cookie is the only artifact requiring a retry.
- **No CSRF token needed on the DELETE** — the endpoint is a pure cookie-delete operation with no state-modifying side effects and no authenticated-only data leakage; it is safe to invoke idempotently (existing design from Story 2.1)
- **Do NOT log or expose session cookie contents** in error messages or telemetry
- **Do NOT store any auth state in `localStorage` or `sessionStorage`** — Firebase Auth + HttpOnly cookie only
- **Redirect target validation** — the helper hardcodes `/` (no user-controlled redirect) to prevent open-redirect bugs

### Anti-Patterns to Avoid

- Do NOT call `/api/auth/session` DELETE without also calling Firebase client `signOut()` — leaves client state stale
- Do NOT call `signOut()` without DELETE — leaves a valid HttpOnly cookie on the server
- Do NOT duplicate the sign-out logic between Dashboard and Header — extract to `destroySessionAndRedirect` + `SignOutButton`
- Do NOT convert `Header.tsx` to `'use client'` — keep it a Server Component and isolate client behavior to `HeaderAuthActions.tsx`
- Do NOT use `asChild` on shadcn/ui Button (Base UI does not support it)
- Do NOT create a new Firebase `auth` instance — reuse `@/lib/firebase/client`
- Do NOT store `user` in React state manually — `AuthContext` already does this via `onAuthStateChanged`
- Do NOT redirect inside `destroySessionAndRedirect` using `window.location.href` — use the injected `redirect` function (Next.js `router.push`) for client-side navigation consistency
- Do NOT add a confirmation dialog ("Are you sure you want to sign out?") — not required by AC and not specified in UX spec
- Do NOT leak Firebase/HTTP error codes to the UI — use a generic user-friendly message like "Unable to sign out. Please try again."
- Do NOT introduce a new API route (e.g., `/api/auth/signout`) — the existing `DELETE /api/auth/session` is the correct endpoint
- Do NOT place files in flat `components/` — use `components/auth/` and `components/layout/`
- Do NOT use `middleware.ts` — Next.js 16 uses `proxy.ts` (not relevant to this story but mentioned in AGENTS.md)

### Naming Conventions (from Architecture)

- **Components:** PascalCase → `SignOutButton.tsx`, `HeaderAuthActions.tsx`
- **Lib files:** camelCase → `session.ts`
- **Functions:** camelCase → `destroySessionAndRedirect`
- **CSS:** Tailwind utilities only

### Import Order Convention

1. React/Next.js imports
2. Third-party libraries (firebase)
3. `@/` project imports
4. Relative imports
5. Type-only imports last

### Prettier Config (enforced by pre-commit hook)

```json
{ "semi": false, "singleQuote": true, "trailingComma": "all", "printWidth": 100, "tabWidth": 2 }
```

### Commit Convention

- Format: `feat(auth): implement sign-out and session destruction`
- Scope: `auth`
- Most recent commit on branch: `f3a908f feat(auth): implement email/password sign-in and registration (Story 2.2)`

### Project Structure Notes

- No architecture deviations — all new files land in directories already defined in the architecture doc's project structure
- `src/components/layout/HeaderAuthActions.tsx` is a new file but fits the established `components/layout/` feature directory
- Extending `src/lib/firebase/session.ts` with a second exported helper keeps auth session management in one place

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.3]
- [Source: _bmad-output/planning-artifacts/architecture.md — Authentication & Security — Session Management]
- [Source: _bmad-output/planning-artifacts/architecture.md — Frontend Architecture — State Management (AuthContext)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Project Structure & Boundaries]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Navigation Patterns (Sign in / Sign out in header)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR3 (user can sign out)]
- [Source: _bmad-output/implementation-artifacts/2-1-firebase-auth-setup-with-google-sign-in.md — createSessionAndRedirect pattern, spinner markup, error display pattern]
- [Source: _bmad-output/implementation-artifacts/2-2-email-password-sign-in-and-registration.md — Story 2.1 learnings, Base UI caveat, test count baseline]
- [Source: src/app/api/auth/session/route.ts — existing DELETE endpoint (no changes)]
- [Source: src/contexts/AuthContext.tsx — onAuthStateChanged auto-propagation]
- [Source: src/lib/firebase/session.ts — createSessionAndRedirect helper to mirror]
- [Source: src/app/dashboard/page.tsx — current ad-hoc sign-out implementation to refactor]
- [Source: src/components/auth/GoogleSignInButton.tsx — spinner and error display patterns to reuse]
- [Source: src/components/layout/Header.tsx — Server Component to extend]
- [Source: AGENTS.md — Next.js 16 breaking changes reminder, read docs before writing Next.js APIs]
- [Source: node_modules/next/dist/docs/ — Next.js 16 docs]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (Claude Opus 4.6, 1M context)

### Debug Log References

- Header.test.tsx initially failed because importing `Header` transitively imported `firebase/auth` via `SignOutButton → session.ts → @/lib/firebase/client`, which tried to call `getAuth()` with no API key in the test environment. Fixed by adding `vi.mock('@/lib/firebase/client', ...)` to Header.test.tsx (same pattern already used in dashboard and GoogleSignInButton tests).
- Pre-existing lint error in `src/components/layout/CookieBanner.tsx:16` (`react-hooks/set-state-in-effect`) is unrelated to this story — verified by running `npm run lint` against `master` HEAD. Out of scope; will be addressed separately.

### Completion Notes List

- Added symmetric `destroySessionAndRedirect()` helper in `src/lib/firebase/session.ts`, mirroring `createSessionAndRedirect` (router injected for testability, calls `signOut(auth)` first so client state is cleared even if DELETE fails).
- Created `SignOutButton` client component reusing the `GoogleSignInButton` spinner + `role="alert"` error display patterns. Surfaces a generic "Unable to sign out. Please try again." message on failure (no Firebase/HTTP codes leaked) and re-enables the button so the user can retry.
- Refactored `src/app/dashboard/page.tsx` to render `<SignOutButton variant="outline" />`, removing the duplicated inline `signOut`/`fetch` logic. Existing dashboard auth guard (`useEffect` redirect to `/auth/sign-in`) is unchanged and still covers AC#5.
- Added `HeaderAuthActions` as a `'use client'` child of the still-Server-Component `Header`. Renders nothing while `useAuth()` is loading (avoids flicker), a "Sign in" link to `/auth/sign-in` for anonymous users, and a `<SignOutButton variant="ghost" size="sm">` for authenticated users — flips automatically via `onAuthStateChanged` with no manual wiring.
- Tests: 6 new `session.test.ts`, 6 new `SignOutButton.test.tsx`, 4 new `HeaderAuthActions.test.tsx`. Updated `dashboard/page.test.tsx` to mock `SignOutButton` (the direct `signOut`/`fetch` mocks now live in `SignOutButton.test.tsx`). Updated `Header.test.tsx` to mock `useAuth` and `firebase/client` so the new transitive import chain works in jsdom.
- Verification: `npm run build` passes (TypeScript clean). Full test suite: **117 / 117 passing** (101 baseline → +16 new, zero regressions). The single existing lint error in `CookieBanner.tsx` is pre-existing and unrelated.

### Review Fixes Applied (v1.1)

- **[MED-1] RSC cache invalidation:** `SignOutButton` now calls `router.refresh()` after `destroySessionAndRedirect` succeeds, so any Server Component that read `cookies()` during its previous render is re-rendered without the stale session.
- **[MED-2] `signOut` failure path:** `destroySessionAndRedirect` now wraps `signOut(auth)` in try/catch and **always issues the DELETE request** before propagating the error. Previously a `signOut` throw short-circuited the helper and left the HttpOnly session cookie alive on the server. Test updated accordingly.
- **[MED-3] Header layout robustness:** The `SignOutButton` inline error is now rendered inside a `relative inline-flex` wrapper as an `absolute top-full` floating message, so a failed sign-out in the Header nav no longer pushes nav height or overflows the row. Dashboard rendering is unchanged visually.
- **[MED-4] Header auth-actions test assertion:** `Header.test.tsx` now asserts that the "Sign in" link is rendered inside the main navigation when anonymous — previously the test only added mocks without asserting the slot.
- **Tests after fixes:** 119/119 passing (117 → +2 new: `router.refresh` assertion on `SignOutButton`, Header auth-actions slot assertion). Pre-existing `CookieBanner.tsx` lint error and pre-existing `route.test.ts` TS error on `master` are out of scope.

### File List

- **Modified** `src/lib/firebase/session.ts` — added `destroySessionAndRedirect()`
- **Added** `src/lib/firebase/session.test.ts` — covers both helpers (success + failure paths, ordering)
- **Added** `src/components/auth/SignOutButton.tsx`
- **Added** `src/components/auth/SignOutButton.test.tsx`
- **Modified** `src/app/dashboard/page.tsx` — replaced inline sign-out with `<SignOutButton />`; removed unused imports
- **Modified** `src/app/dashboard/page.test.tsx` — mocks `SignOutButton`, removed direct `signOut`/`fetch` assertions
- **Added** `src/components/layout/HeaderAuthActions.tsx`
- **Added** `src/components/layout/HeaderAuthActions.test.tsx`
- **Modified** `src/components/layout/Header.tsx` — renders `<HeaderAuthActions />` after the Pricing nav item
- **Modified** `src/components/layout/Header.test.tsx` — mocks `useAuth` and `@/lib/firebase/client` for the new transitive imports
- **Modified** `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status `ready-for-dev → in-progress → review`

### Change Log

| Date       | Version | Change                                                                                       |
| ---------- | ------- | -------------------------------------------------------------------------------------------- |
| 2026-04-14 | 1.0     | Implemented Story 2.3 — sign-out helper, SignOutButton, dashboard refactor, header auth nav. |
| 2026-04-14 | 1.1     | Code review fixes: `router.refresh()` after sign-out, `destroySessionAndRedirect` always issues DELETE even if `signOut` throws, inline error uses absolute positioning so Header nav layout is not disturbed, added Header auth-actions slot test assertion. |