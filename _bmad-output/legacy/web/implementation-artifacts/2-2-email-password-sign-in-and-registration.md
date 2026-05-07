# Story 2.2: Email/Password Sign-In and Registration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to sign in or create an account using email and password,
So that I can access protected features without a Google account.

## Acceptance Criteria

1. **Given** a user navigates to the sign-in page
   **When** the user submits valid email and password credentials
   **Then** Firebase `signInWithEmailAndPassword()` authenticates the user (FR2)
   **And** a session cookie is created via `/api/auth/session`
   **And** the user is redirected to `/dashboard`

2. **Given** a user does not have an account and submits registration details
   **When** `createUserWithEmailAndPassword()` completes successfully (FR4)
   **Then** a session cookie is created via `/api/auth/session`
   **And** the user is redirected to `/dashboard`

3. **Given** the user is filling out the sign-in or registration form
   **When** the form is submitted
   **Then** form validation uses React Hook Form + Zod with inline error display
   **And** email field validates proper email format
   **And** password field enforces minimum 8 characters
   **And** registration form validates password confirmation matches

4. **Given** the user submits invalid credentials (wrong password, non-existent account)
   **When** Firebase returns an authentication error
   **Then** user-friendly error messages are displayed inline (not raw Firebase error codes)
   **And** the form remains populated with the user's input (except password)

5. **Given** the sign-in page already has a Google sign-in button (from Story 2.1)
   **When** the page renders
   **Then** Google sign-in is displayed as the primary option above
   **And** a horizontal "or" divider separates it from the email/password form below
   **And** a toggle link switches between "Sign In" and "Create Account" modes

## Tasks / Subtasks

- [x] Task 1: Install Form Dependencies (AC: #3)
  - [x] 1.1 Install `react-hook-form` and `@hookform/resolvers`
  - [x] 1.2 Verify `@hookform/resolvers/zod` works with Zod v4 (`zod/v4` import)
  - [x] 1.3 If bundler resolution error occurs with Next.js, check resolvers issue #839 for workaround

- [x] Task 2: Create Zod Validation Schemas (AC: #3)
  - [x] 2.1 Create `src/lib/schemas/auth.ts` (new directory `schemas/`)
  - [x] 2.2 Sign-in schema: `{ email: z.email(), password: z.string().min(1) }`
  - [x] 2.3 Registration schema: `{ email: z.email(), password: z.string().min(8), confirmPassword: z.string() }` with `.check()` for password match (Zod v4 uses `.check()` not `.refine()`)
  - [x] 2.4 Export inferred TypeScript types: `SignInFormData`, `RegistrationFormData`
  - [x] 2.5 Import Zod from `zod/v4` (NOT `zod` — project convention)

- [x] Task 3: Build Email/Password Sign-In Form Component (AC: #1, #3, #4)
  - [x] 3.1 Create `src/components/auth/EmailSignInForm.tsx` as `'use client'`
  - [x] 3.2 Use React Hook Form with `zodResolver` for form state management
  - [x] 3.3 Implement `signInWithEmailAndPassword(auth, email, password)` on submit
  - [x] 3.4 After success, call `user.getIdToken()` and POST to `/api/auth/session` (reuse existing endpoint)
  - [x] 3.5 On session success, redirect to `/dashboard` via `useRouter().push()`
  - [x] 3.6 Display inline Zod validation errors below each field
  - [x] 3.7 Map Firebase error codes to user-friendly messages (see Dev Notes)
  - [x] 3.8 Show loading state: disabled button + spinner during auth + session creation
  - [x] 3.9 Style with shadcn/ui `Input` and `Button` components, Tailwind utilities

- [x] Task 4: Build Registration Form Component (AC: #2, #3, #4)
  - [x] 4.1 Create `src/components/auth/RegistrationForm.tsx` as `'use client'`
  - [x] 4.2 Use React Hook Form with `zodResolver` (registration schema with password confirmation)
  - [x] 4.3 Implement `createUserWithEmailAndPassword(auth, email, password)` on submit
  - [x] 4.4 After success, same session flow as sign-in (getIdToken -> POST /api/auth/session -> redirect)
  - [x] 4.5 Map Firebase registration error codes to user-friendly messages (see Dev Notes)
  - [x] 4.6 Show loading state during registration + session creation
  - [x] 4.7 Style consistent with EmailSignInForm

- [x] Task 5: Update Sign-In Page with Toggle UI (AC: #5)
  - [x] 5.1 Update `src/app/auth/sign-in/page.tsx` to include both sign-in methods
  - [x] 5.2 Convert page to have a client wrapper component for toggle state
  - [x] 5.3 Google sign-in button displayed above as primary option (per UX spec)
  - [x] 5.4 Horizontal divider with "or" text between Google button and email form
  - [x] 5.5 Show EmailSignInForm when mode is "sign-in", RegistrationForm when "register"
  - [x] 5.6 Toggle link at bottom: "Don't have an account? Create one" / "Already have an account? Sign in"
  - [x] 5.7 Page title changes: "Sign in to Warden" / "Create your account"

- [x] Task 6: Write Tests (AC: all)
  - [x] 6.1 Test `src/lib/schemas/auth.ts` — valid/invalid inputs for both schemas
  - [x] 6.2 Test `EmailSignInForm` — renders fields, shows validation errors, handles Firebase errors
  - [x] 6.3 Test `RegistrationForm` — renders fields, validates password match, handles Firebase errors
  - [x] 6.4 Test sign-in page — renders both modes, toggle works, Google button present

- [x] Task 7: Verification (AC: all)
  - [x] 7.1 Verify `npm run build` passes with no TypeScript errors
  - [x] 7.2 Verify ESLint passes with no errors
  - [x] 7.3 Verify Prettier formatting is clean
  - [ ] 7.4 Manual test: Email/password sign-in -> session cookie -> redirect to dashboard
  - [ ] 7.5 Manual test: Registration -> account created -> session cookie -> redirect
  - [ ] 7.6 Manual test: Invalid credentials -> user-friendly error displayed
  - [ ] 7.7 Manual test: Registration with existing email -> appropriate error

## Dev Notes

### Architecture Compliance

- **Auth pattern:** Firebase Client SDK for email/password auth -> ID token -> server-side session cookie via Firebase Admin SDK (identical flow to Google sign-in from Story 2.1)
- **Session management:** Reuses `/api/auth/session` POST endpoint — same HttpOnly, Secure, SameSite=Lax, 7-day expiry session cookie. NO new API routes needed.
- **Form validation:** React Hook Form + Zod at the client boundary, Firebase provides server-side auth validation. Zod schemas in `src/lib/schemas/` per architecture doc.
- **Component organization:** Feature-based in `components/auth/` directory
- **State management:** No global state — form state is local via React Hook Form, auth state flows through existing `AuthContext` (which already listens to `onAuthStateChanged` and will automatically pick up email/password sign-ins)

### Technical Stack (Verified Versions)

- **Next.js 16.2.2** with App Router, `src/` directory, `@/*` import alias
- **React 19.2.4** — `'use client'` for all form components
- **Tailwind CSS 4** via `@tailwindcss/postcss` (config in `globals.css`, no `tailwind.config.ts`)
- **shadcn/ui 4.1.2** — uses **Base UI** (NOT Radix UI). Available: `Button`, `Input`, `Card`, `Badge`, `Alert`, `Skeleton`, `Dialog`
- **Firebase JS SDK v12.11.0** — `signInWithEmailAndPassword()`, `createUserWithEmailAndPassword()` from `firebase/auth` (API unchanged from v10/v11)
- **Firebase Admin SDK v13.7.0** — session cookie creation (server-only, already in place)
- **Zod v4.3.6** — Import from `zod/v4` (NOT `zod`). Uses `z.email()` not `z.string().email()`
- **React Hook Form v7.72.x** — TO INSTALL. Use `useWatch()` instead of `watch()` with React 19
- **@hookform/resolvers v5.2.x** — TO INSTALL. Supports Zod v4 natively (auto-detects v3/v4)

### CRITICAL: Zod v4 Differences

Project uses `zod@^4.3.6`. Key API differences from v3:
- Import: `import { z } from 'zod/v4'` (NOT `from 'zod'`)
- Email validation: `z.email()` (NOT `z.string().email()`)
- Refinements: Zod v4 uses `.check()` instead of `.refine()` for custom validations
- Type inference: `z.infer<typeof schema>` still works in v4
- `zodResolver` from `@hookform/resolvers/zod` auto-detects v4 — no special config needed
- **Bundler caveat**: If `@hookform/resolvers/zod` throws module resolution errors in Next.js, check https://github.com/react-hook-form/resolvers/issues/839 for workarounds

### CRITICAL: Next.js 16 Breaking Changes (Relevant to This Story)

1. **`cookies()` is async** — already handled in existing session route, no changes needed
2. **`proxy.ts` not `middleware.ts`** — already implemented in Story 2.1, no changes needed
3. **Base UI not Radix** — `asChild` prop NOT available on shadcn/ui components. Use `buttonVariants()` pattern or apply Tailwind classes directly (from Story 2.1 learnings)
4. **Read the docs** before writing any Next.js API: `node_modules/next/dist/docs/`

### CRITICAL: React 19 + React Hook Form

- `watch()` may not trigger re-renders properly in React 19 — use `useWatch()` instead
- `useForm()` and `handleSubmit()` work normally
- React 19's native `useActionState` is NOT needed here — RHF handles client-side form state
- All form components MUST be `'use client'` (RHF uses hooks internally)

### Packages to Install

```bash
npm install react-hook-form @hookform/resolvers
```

No other new dependencies needed — Firebase, Zod, shadcn/ui components all already present.

### Firebase Auth Error Code Mapping

```typescript
// Shared across EmailSignInForm and RegistrationForm
const AUTH_ERROR_MESSAGES: Record<string, string> = {
  // Sign-in errors
  'auth/invalid-credential': 'Invalid email or password.',
  'auth/user-disabled': 'This account has been disabled.',
  'auth/too-many-requests': 'Too many attempts. Please wait and try again.',
  'auth/network-request-failed': 'Network error. Please try again.',
  // Registration errors
  'auth/email-already-in-use': 'An account with this email already exists. Try signing in instead.',
  'auth/weak-password': 'Password is too weak. Use at least 8 characters.',
  'auth/invalid-email': 'Please enter a valid email address.',
}
```

Note: `GoogleSignInButton.tsx` already has a similar `FIREBASE_ERROR_MESSAGES` map. Consider extracting a shared `getFirebaseErrorMessage()` helper or keeping them co-located per component (dev's judgment call — both approaches are acceptable).

### File Structure

```
src/
├── app/
│   └── auth/
│       └── sign-in/
│           └── page.tsx              # MODIFY: Add toggle UI, email form, registration form
├── components/
│   └── auth/
│       ├── GoogleSignInButton.tsx    # EXISTS: Keep as-is (from Story 2.1)
│       ├── EmailSignInForm.tsx       # NEW: Email/password sign-in form
│       ├── EmailSignInForm.test.tsx  # NEW: Tests for sign-in form
│       ├── RegistrationForm.tsx      # NEW: Registration form
│       └── RegistrationForm.test.tsx # NEW: Tests for registration form
└── lib/
    └── schemas/
        ├── auth.ts                   # NEW: Zod schemas for sign-in + registration
        └── auth.test.ts              # NEW: Schema validation tests
```

### Testing Requirements

- **Test framework:** Vitest 4.1.3 + React Testing Library (already configured)
- **Test pattern:** Co-located tests next to source files (e.g., `EmailSignInForm.test.tsx`)
- **Mock pattern:** Mock `firebase/auth` functions with `vi.mock()` (pattern established in `GoogleSignInButton.test.tsx` and `AuthContext.test.tsx`)
- **What to test:**
  - Schema tests: Valid/invalid email, password min length, password match
  - Form component tests: Renders fields, shows Zod validation errors on invalid submit, shows Firebase error messages on auth failure, shows loading state, calls session API on success
  - Page tests: Renders Google button + email form, toggle switches modes
- **What NOT to test:** Actual Firebase authentication (requires credentials — manual test only)
- **Current test count:** 70 tests across 12 files — ensure zero regressions

### Auth Flow Pattern (Reuses Story 2.1 Infrastructure)

**Sign-In Flow:**
1. User enters email + password in `EmailSignInForm`
2. React Hook Form validates via Zod schema (inline errors if invalid)
3. `signInWithEmailAndPassword(auth, email, password)` from `firebase/auth`
4. On success: `user.getIdToken()` -> POST to `/api/auth/session` with `{ idToken }`
5. Server verifies token, creates session cookie (existing endpoint handles this)
6. Client redirects to `/dashboard` via `useRouter().push()`

**Registration Flow:**
1. User enters email + password + confirm password in `RegistrationForm`
2. React Hook Form validates via Zod schema (password match + min length)
3. `createUserWithEmailAndPassword(auth, email, password)` from `firebase/auth`
4. On success: same session flow as sign-in (steps 4-6 above)

**Key:** Both flows produce a Firebase `UserCredential` with an ID token. The existing `/api/auth/session` endpoint accepts ANY valid Firebase ID token — no modifications needed.

### Security Considerations

- Password transmitted to Firebase Auth servers over HTTPS — never stored or logged locally
- Firebase Auth handles password hashing and storage — no custom implementation
- Session cookie creation reuses the same secure pattern from Story 2.1 (HttpOnly, Secure, SameSite=Lax)
- Client-side Zod validation is UX-only — Firebase Auth enforces its own server-side rules
- No password reset flow in this story (can be added later if needed)
- No password strength meter needed — Firebase enforces minimum 6 chars, our Zod schema enforces 8 chars (stricter than Firebase default)

### UX Design Requirements (from UX Specification)

- **Layout:** Google sign-in button as primary option above, "or" divider, email form below
- **Form inputs:** Stacked — email field, password field, submit button. Dark surface bg, orange focus ring (consistent with Warden dark theme)
- **Registration:** Same layout + confirm password field
- **Toggle:** Link text at bottom switches between sign-in and registration modes
- **Error display:** Inline below each field (RHF handles this) + form-level for Firebase errors
- **Loading:** Button shows spinner + disabled state during auth flow
- **Mobile-first:** Touch-friendly input sizes, adequate spacing for mobile keyboards
- **No separate pages:** Sign-in and registration live on the same page with a toggle, per UX spec

### Previous Story (2.1) Learnings — CRITICAL for Dev Agent

These findings come from the completed Story 2.1 implementation and code review. Apply them:

1. **shadcn/ui uses Base UI, NOT Radix UI** — `asChild` prop does NOT exist. Use `buttonVariants()` or apply Tailwind classes directly to elements.
2. **`buttonVariants()` is exported from a `'use client'` module** — cannot call from Server Components. Not an issue here since forms are all `'use client'`.
3. **`cn()` utility** at `src/lib/utils.ts` — use for conditional Tailwind class merging.
4. **Pre-commit hook** runs Prettier + ESLint automatically on staged files.
5. **`auth` export from `src/lib/firebase/client.ts`** — reuse directly for email/password functions. Do NOT create a new Firebase auth instance.
6. **AuthContext already listens to `onAuthStateChanged`** — when email/password sign-in completes, AuthContext automatically updates `{user, loading, error}` state. No extra wiring needed.
7. **Admin SDK uses lazy init via Proxy** — refactored in Story 2.1 to prevent build failures. No changes needed for this story.
8. **Session API validates with Zod** — uses `z.string().min(1)` for idToken. Import is `from 'zod/v4'`. Follow same Zod import pattern in new schemas.
9. **Error message pattern** — `GoogleSignInButton` maps Firebase error codes via a `Record<string, string>` lookup with fallback. Replicate this pattern.
10. **Spinner pattern** — `GoogleSignInButton` uses an inline CSS spinner: `<span className="size-5 animate-spin rounded-full border-2 border-current border-t-transparent" />`. Reuse this same spinner markup for loading states.
11. **`useAuth()` hook throws** if used outside `AuthProvider` — this was added in code review. Safe to use in form components since root layout wraps with `AuthProvider`.

### Git Intelligence

- **Commit convention:** `feat(auth): <description>` using Conventional Commits
- **Scope for this story:** `auth`
- **Most recent commit:** `848cd3b feat(auth): implement Firebase auth with Google sign-in and code review fixes`
- **Pre-commit hook:** Prettier runs automatically — code will be formatted on commit
- **Branch pattern:** Recent stories used feature branches (e.g., `claude/landing-page-value-prop-ZiYtw`)
- **Recent file patterns:**
  - Components: `src/components/auth/GoogleSignInButton.tsx` (PascalCase)
  - Tests: `src/components/auth/GoogleSignInButton.test.tsx` (co-located)
  - Lib: `src/lib/firebase/client.ts` (camelCase)
  - API routes: `src/app/api/auth/session/route.ts`

### Anti-Patterns to Avoid

- Do NOT import `firebase-admin` in client components — server-only
- Do NOT use `middleware.ts` — Next.js 16 uses `proxy.ts`
- Do NOT call `cookies()` synchronously — async in Next.js 16
- Do NOT use `localStorage` for session tokens — HttpOnly cookies only
- Do NOT create custom password hashing — Firebase Auth handles this entirely
- Do NOT validate password strength server-side — Firebase Auth enforces its own rules
- Do NOT use `watch()` from React Hook Form — use `useWatch()` with React 19
- Do NOT use Zod v3 API patterns (e.g., `z.string().email()`) — use Zod v4 (`z.email()`)
- Do NOT use `.refine()` for custom Zod validations — Zod v4 uses `.check()`
- Do NOT build a separate registration page — use toggle UI on the same sign-in page
- Do NOT create a new session API endpoint — reuse existing `/api/auth/session`
- Do NOT create a new Firebase auth instance — reuse `auth` from `@/lib/firebase/client`
- Do NOT add a global state store for form data — React Hook Form manages local state
- Do NOT place files in flat `components/` — use `components/auth/`
- Do NOT use `from 'zod'` — project convention is `from 'zod/v4'`

### Naming Conventions (from Architecture)

- **Components:** PascalCase -> `EmailSignInForm.tsx`, `RegistrationForm.tsx`
- **Schemas/lib:** camelCase -> `auth.ts`
- **Types:** PascalCase -> `SignInFormData`, `RegistrationFormData`
- **Constants:** SCREAMING_SNAKE_CASE -> `AUTH_ERROR_MESSAGES`
- **CSS:** Tailwind utilities only

### Import Order Convention

1. React/Next.js imports
2. Third-party libraries (firebase, react-hook-form, zod)
3. `@/` project imports
4. Relative imports
5. Type-only imports last

### Prettier Config (enforced by pre-commit hook)

```json
{ "semi": false, "singleQuote": true, "trailingComma": "all", "printWidth": 100, "tabWidth": 2 }
```

### Project Structure Notes

- `src/lib/schemas/` is a NEW directory — matches architecture doc's `lib/schemas/` pattern
- Sign-in page at `/auth/sign-in` — established in Story 2.1
- All new files follow architecture doc's directory structure exactly
- No architecture doc deviations needed for this story

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.2]
- [Source: _bmad-output/planning-artifacts/architecture.md — Authentication & Security]
- [Source: _bmad-output/planning-artifacts/architecture.md — Frontend Architecture — Form Handling: React Hook Form + Zod]
- [Source: _bmad-output/planning-artifacts/architecture.md — Implementation Patterns & Consistency Rules]
- [Source: _bmad-output/planning-artifacts/architecture.md — Project Structure & Boundaries]
- [Source: _bmad-output/planning-artifacts/prd.md — FR2 (email/password sign-in), FR4 (account creation)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Auth modal pattern, Form Patterns, Component Strategy]
- [Source: _bmad-output/implementation-artifacts/2-1-firebase-auth-setup-with-google-sign-in.md — Previous Story Learnings, File Patterns, Code Review Fixes]
- [Source: node_modules/next/dist/docs/ — Next.js 16 docs (check before writing any Next.js API)]
- [Source: https://github.com/react-hook-form/resolvers/issues/839 — Bundler resolution with Zod v4]
- [Source: Firebase Auth docs — signInWithEmailAndPassword, createUserWithEmailAndPassword]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Zod v4 `.check()` requires `input` property in issue objects (TypeScript type error caught during build)
- `@testing-library/user-event` was not installed — added as dev dependency

### Completion Notes List

- Installed `react-hook-form@7.72.1` and `@hookform/resolvers@5.2.2` (Zod v4 compatible)
- Created Zod v4 schemas with `z.email()` and `.check()` for password confirmation
- Built `EmailSignInForm` with RHF + zodResolver, Firebase signInWithEmailAndPassword, session creation, and redirect
- Built `RegistrationForm` with createUserWithEmailAndPassword, same session flow pattern
- Created `AuthFormToggle` client wrapper for sign-in/register mode toggle with "or" divider
- Updated sign-in page to use AuthFormToggle, keeping page as Server Component with metadata
- Both forms reuse existing `/api/auth/session` endpoint and `auth` from `@/lib/firebase/client`
- Firebase error codes mapped to user-friendly messages in each form component
- Loading states use same spinner pattern as GoogleSignInButton
- 29 new tests added (10 schema, 7 EmailSignInForm, 7 RegistrationForm, 5 AuthFormToggle)
- Total test count: 101 (72 existing + 29 new), zero regressions
- Build, ESLint, Prettier all pass clean
- Manual tests (7.4-7.7) require user verification with real Firebase credentials

### Implementation Plan

Followed story tasks sequentially: dependencies -> schemas -> sign-in form -> registration form -> page UI -> tests -> verification. Used red-green-refactor approach where applicable.

### Change Log

- 2026-04-09: Implemented email/password sign-in and registration (Story 2.2) — all automated tasks complete, manual tests pending user verification
- 2026-04-14: Code review fixes — clear password fields on auth error (AC#4), add aria-describedby for accessibility, remove unused fireEvent import, fix test count in notes, add sprint-status.yaml to File List

### File List

New files:
- src/lib/schemas/auth.ts
- src/lib/schemas/auth.test.ts
- src/components/auth/EmailSignInForm.tsx
- src/components/auth/EmailSignInForm.test.tsx
- src/components/auth/RegistrationForm.tsx
- src/components/auth/RegistrationForm.test.tsx
- src/components/auth/AuthFormToggle.tsx
- src/components/auth/AuthFormToggle.test.tsx

Modified files:
- src/app/auth/sign-in/page.tsx
- package.json (added react-hook-form, @hookform/resolvers, @testing-library/user-event)
- package-lock.json
- _bmad-output/implementation-artifacts/sprint-status.yaml
