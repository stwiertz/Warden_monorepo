---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-02-06'
inputDocuments:
  - '_bmad/planning-artifacts/prd.md'
  - '_bmad/planning-artifacts/product-brief-WardenWeb-2026-02-05.md'
  - '_bmad/brainstorming/brainstorming-session-2026-02-05.md'
  - '_bmad/planning-artifacts/prd-validation-report.md'
workflowType: 'architecture'
project_name: 'WardenWeb'
user_name: 'Developer'
date: '2026-02-06'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
34 FRs across 8 categories. The system is primarily a service orchestration layer:

- Authentication (FR1-4): Firebase Auth with Google + Email/Password
- Discovery (FR5-7): Static/SSR landing page with CTAs
- Checkout (FR8-12): Stripe-powered subscription with coupon support
- Dashboard (FR13-20): Read subscription state from Firestore, trigger Stripe actions
- Webhooks (FR21-25): Server-side Stripe event processing → Firestore state updates
- Legal (FR26-29): Static pages + cookie consent gating
- Account Deletion (FR30-31): MVP via support email, cascading delete across services
- Security (FR32-34): Firestore rules, auth validation, secret management

**Non-Functional Requirements:**
16 NFRs across 4 categories:

- Performance: LCP < 2.5s, FID < 100ms, CLS < 0.1, dashboard < 2s, checkout < 30s
- Security: HTTPS, HttpOnly cookies, webhook signature verification, PCI via Stripe
- Integration: Retry logic for Stripe API (3 attempts), idempotent webhook processing, 200 response within 5s
- Data Integrity: Firestore-Stripe sync within 30s, at-least-once webhook delivery with idempotency

**Scale & Complexity:**

- Primary domain: Full-stack web application (Next.js)
- Complexity level: Low-Medium
- Estimated architectural components: ~8 (landing, pricing/checkout, auth, dashboard, webhooks API, Firestore data layer, Stripe integration layer, legal pages)

### Technical Constraints & Dependencies

- **Firebase project shared** between mobile app and web portal (same auth, same Firestore)
- **Stripe as payment processor** — all card handling delegated, PCI compliance via Stripe
- **Firestore europe-west region** locked for GDPR compliance
- **No WebSocket/real-time** — webhook-driven async state updates
- **Mobile-first responsive** — 320px-768px primary, progressive enhancement to desktop
- **Browser support** — Last 2 versions of Chrome, Firefox, Safari, Edge (no IE11)
- **Cookie consent required** before loading Firebase Analytics

### Cross-Cutting Concerns Identified

- **Authentication**: Protects dashboard, checkout, API routes. Firebase Auth token validation on every protected request.
- **Stripe-Firestore Sync**: The most critical architectural concern. Webhooks must reliably update Firestore to reflect Stripe state. Idempotency and signature verification are mandatory.
- **GDPR Compliance**: Affects data storage location, cookie consent flow, account deletion cascade, and privacy policy content.
- **Error Handling**: Payment failures, auth failures, and webhook processing failures all need distinct handling patterns visible to the user.
- **Environment Configuration**: Stripe keys, Firebase config, webhook secrets must be managed securely across development and production.

## Starter Template Evaluation

### Primary Technology Domain

Full-stack web application based on project requirements analysis. Next.js provides React frontend + API routes for Stripe webhooks in a single deployment.

### Starter Options Considered

**Option 1: `create-next-app` (Official Next.js CLI)**

- Next.js 16.1.x (latest stable, Feb 2026)
- Defaults: TypeScript, Tailwind CSS, ESLint, App Router, Turbopack
- Add Firebase/Stripe manually
- Pros: Minimal, standard conventions, zero cost, AI-agent-friendly
- Cons: No pre-wired integrations

**Option 2: SaaS Boilerplates (Divjoy, Makerkit, supastarter)**

- Pre-built Firebase + Stripe + auth flows
- Pros: Faster initial integration setup
- Cons: Paid ($100-400+), excessive features (team billing, admin, email), opinionated non-standard patterns, harder for AI agents to follow

### Selected Starter: create-next-app (Next.js 16.1.x)

**Rationale for Selection:**

- Project complexity (low-medium) doesn't justify boilerplate overhead
- Standard Next.js conventions ensure AI agent consistency
- Firebase SDK and Stripe SDK are well-documented for manual integration
- No unnecessary features bloating the codebase
- Free, always up-to-date, community-supported

**Initialization Command:**

```bash
npx create-next-app@latest wardenweb --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
TypeScript (strict mode), Node.js runtime for API routes

**Styling Solution:**
Tailwind CSS v4 (utility-first, configured out of the box)

**Build Tooling:**
Turbopack (stable default bundler in Next.js 16), optimized production builds

**Testing Framework:**
Not included — will be decided in Step 4

**Code Organization:**
App Router with `src/` directory, `@/*` import alias

**Development Experience:**
Turbopack hot reload, TypeScript type checking, ESLint linting

**Note:** Project initialization using this command should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**

- Data validation: Zod
- Auth session management: Server-side session cookies
- Hosting: Vercel
- Component library: shadcn/ui

**Important Decisions (Shape Architecture):**

- Caching strategy: Next.js built-in for static pages
- State management: React Context for auth
- Testing: Vitest + Playwright
- CI/CD: GitHub Actions + Vercel

**Deferred Decisions (Post-MVP):**

- CDN/edge caching optimization
- Monitoring/alerting (Vercel Analytics sufficient for MVP)
- Advanced logging (console logging sufficient for MVP)

### Data Architecture

**Database:** Firestore (Firebase JS SDK v12.9.x)

- Region: europe-west (GDPR)
- Collections: `users/{uid}`, `coupon_batches/{batchId}`
- Security rules: users read/write only own document

**Data Validation:** Zod v3.x

- Runtime validation on all webhook payloads (security-critical)
- Shared schemas between client and server
- TypeScript type inference from schemas
- Rationale: Webhook payloads from Stripe must be validated at runtime, not just at type level

**Caching Strategy:** Next.js built-in caching only

- Static pages (landing, pricing, legal): `cacheLife` with revalidation
- Dashboard: Always fresh reads from Firestore (subscription state changes via webhooks)
- No external caching layer needed at MVP scale

### Authentication & Security

**Session Management:** Server-side session cookies

- Firebase Auth `createSessionCookie()` after client-side sign-in
- HttpOnly, Secure, SameSite=Lax cookies
- 7-day expiry with activity-based refresh (per PRD: auto-logout after 7 days inactivity)
- Rationale: PRD requires HttpOnly cookies; server-side sessions enable SSR auth checks

**Route Protection:** Next.js middleware + per-route API checks

- `middleware.ts`: Validates session cookie, redirects unauthenticated users from `/dashboard/*`
- API routes: Validate session cookie independently (defense in depth)
- Public routes: Landing, pricing, legal pages (no auth required)

**Stripe Webhook Security:** Signature verification (per PRD FR24)

- `stripe.webhooks.constructEvent()` with webhook secret
- Reject unsigned or invalid payloads before processing

### API & Communication Patterns

**API Routes:** Next.js App Router Route Handlers

- `/api/webhooks/stripe` — Stripe webhook endpoint
- `/api/auth/*` — Session management (create/destroy session cookies)
- `/api/subscription/*` — Subscription actions (upgrade, cancel)

**Webhook Idempotency:** Dual strategy

- Event ID deduplication: Store processed Stripe event IDs in Firestore, skip duplicates
- Firestore transactions: Check current state before updating (handles race conditions)
- Rationale: At-least-once delivery requires both dedup and transactional state updates

**Error Handling:** Three-layer approach

- API routes: Structured `{error: {code, message}}` JSON responses
- React error boundaries: Catch unexpected rendering failures
- User-facing error states: Specific components for payment failed, auth failed, generic error
- Stripe webhook errors: Log and return 200 to prevent Stripe retries on permanent failures

### Frontend Architecture

**State Management:** React Context (minimal)

- `AuthContext`: Firebase Auth state (user, loading, error)
- No global store needed — subscription data fetched per-page from Firestore
- Rationale: Portal has minimal client state; adding Zustand/React Query is unnecessary

**Component Library:** shadcn/ui

- Radix UI primitives styled with Tailwind CSS
- Copy-paste ownership (no npm dependency)
- Accessible by default (WCAG 2.1 Level A per PRD)
- Components needed: Button, Card, Dialog, Form, Input, Badge, Alert, Skeleton

**Form Handling:** React Hook Form + Zod

- Checkout form: Plan selection + coupon code
- Auth forms: Email/password sign-in/sign-up
- Zod schemas shared with server-side validation

**Routing Strategy:** Next.js App Router

- `/` — Landing page (SSR, cached)
- `/pricing` — Pricing + checkout (client-side interactivity)
- `/dashboard` — Account dashboard (protected, fresh data)
- `/privacy` — Privacy policy (static)
- `/terms` — Terms of service (static)

### Infrastructure & Deployment

**Hosting:** Vercel

- Native Next.js support, zero-config deployment
- API routes → serverless functions (auto-scaled)
- Edge network for static assets
- Preview deployments on PRs
- Rationale: Best-in-class Next.js hosting, free tier sufficient for MVP

**Testing:** Vitest 4.x + Playwright

- Vitest: Unit tests for utilities, Zod schemas, webhook handlers
- React Testing Library: Component tests
- Playwright: E2E tests for checkout flow, auth flow, dashboard actions
- Rationale: Vitest is Next.js recommended; Playwright covers critical payment flows

**CI/CD:** GitHub Actions + Vercel

- GitHub Actions: Run linting, type checking, unit tests, E2E tests on PR
- Vercel: Automatic preview deployments on PR, production deploy on main merge
- Rationale: Separation of concerns — GH Actions validates code quality, Vercel handles deployment

**Environment Management:**

- `.env.local` — Local development secrets
- `.env.example` — Template with placeholder values (committed)
- Vercel Environment Variables — Production/preview secrets
- Required vars: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_FIREBASE_*` config values

### Decision Impact Analysis

**Implementation Sequence:**

1. Project initialization (`create-next-app`)
2. Firebase Auth + session cookie setup
3. Firestore data layer + security rules
4. Stripe integration + webhook endpoint
5. UI components (shadcn/ui setup)
6. Page implementations (landing → pricing → dashboard)
7. Testing setup (Vitest + Playwright)
8. CI/CD pipeline (GitHub Actions)
9. Vercel deployment

**Cross-Component Dependencies:**

- Auth decisions affect: middleware, API routes, dashboard, checkout
- Stripe decisions affect: webhook handler, dashboard state display, checkout flow
- Zod schemas affect: webhook validation, form validation, Firestore writes
- shadcn/ui affects: all page implementations

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 5 categories where AI agents could make different choices — naming, structure, formats, communication, and process patterns.

### Naming Patterns

**Firestore Naming Conventions:**

- Collection names: `snake_case` plural → `users`, `coupon_batches`
- Document fields: `snake_case` → `current_period_end`, `redeemed_batches`
- Rationale: Matches Stripe webhook field naming (Stripe uses snake_case), avoids constant conversion

**API Naming Conventions:**

- Route handlers: kebab-case directories → `/api/webhooks/stripe`, `/api/auth/session`
- Query parameters: `camelCase` → `?batchId=abc`
- JSON response fields: `camelCase` → `{currentPlan, nextPaymentDate}`

**Code Naming Conventions:**

- Components: `PascalCase` files → `PricingCard.tsx`, `DashboardLayout.tsx`
- Utilities/lib: `camelCase` files → `stripeClient.ts`, `firebaseAdmin.ts`
- Hooks: `camelCase` with `use` prefix → `useAuth.ts`, `useSubscription.ts`
- Types: `PascalCase` → `User`, `Subscription`, `WebhookEvent`
- Constants: `SCREAMING_SNAKE_CASE` → `STRIPE_PLANS`, `AUTH_COOKIE_NAME`
- CSS classes: Tailwind utilities only (no custom CSS class names)

### Structure Patterns

**Project Organization:**

- Components organized by feature, not by type
- `src/components/ui/` for shadcn/ui base components
- `src/components/auth/` for auth-specific components
- `src/components/checkout/` for checkout components
- `src/components/dashboard/` for dashboard components
- `src/components/layout/` for shared layout (Header, Footer, CookieBanner)

**File Structure Patterns:**

- Tests co-located next to source: `src/lib/__tests__/stripe.test.ts`
- E2E tests in top-level `e2e/` directory
- Lib organized by service: `src/lib/firebase/`, `src/lib/stripe/`, `src/lib/schemas/`

### Format Patterns

**API Response Formats:**

```typescript
// Success
{ data: { subscription: {...} } }

// Error
{ error: { code: "SUBSCRIPTION_NOT_FOUND", message: "No active subscription" } }
```

**Data Exchange Formats:**

- Firestore stores `snake_case` (matches Stripe webhook payloads)
- Frontend uses `camelCase` (TypeScript convention)
- Conversion happens in data layer (`src/lib/firebase/`) using Zod `.transform()`
- Dates in Firestore: `Timestamp` objects
- Dates from Stripe: Unix timestamps (seconds)
- Dates in JSON responses: ISO 8601 strings
- Dates in UI: `Intl.DateTimeFormat` (no date library needed)

### Communication Patterns

**Auth Flow Pattern:**

1. Client: Firebase `signInWithPopup()` or `signInWithEmailAndPassword()`
2. Client gets ID token: `user.getIdToken()`
3. POST to `/api/auth/session` with ID token
4. Server creates session cookie via `createSessionCookie()`, returns success
5. Client redirects to dashboard

**Stripe Webhook Event Flow:**

1. Stripe POSTs to `/api/webhooks/stripe`
2. Verify signature → parse event
3. Check event ID dedup in Firestore
4. Route by event type (`invoice.paid`, `customer.subscription.deleted`, `invoice.payment_failed`)
5. Firestore transaction to update `users/{uid}` subscription fields
6. Return 200

**Loading State Pattern:**

- Component-level: `isLoading` boolean + Skeleton component from shadcn/ui
- Page-level: Next.js `loading.tsx` files
- Auth loading: `AuthContext` provides `{user, loading, error}`

### Process Patterns

**Error Handling Patterns:**

| Layer            | Pattern                                                    |
| ---------------- | ---------------------------------------------------------- |
| API routes       | Try/catch → structured JSON error response                 |
| Webhook handler  | Try/catch → log error, return 200 (prevent Stripe retries) |
| React components | Error boundaries around feature sections                   |
| Forms            | React Hook Form validation errors → inline display         |
| Auth             | Redirect to sign-in on 401, toast on other errors          |

**Environment Variable Access:**

- Server-only: `process.env.STRIPE_SECRET_KEY` (no `NEXT_PUBLIC_` prefix)
- Client-safe: `process.env.NEXT_PUBLIC_FIREBASE_API_KEY`
- Rule: Server secrets must never appear in client bundles

**Import Order Convention:**

1. React/Next.js imports
2. Third-party libraries
3. `@/` project imports
4. Relative imports
5. Type-only imports last

**Code Formatting:** Prettier

- `prettier` + `prettier-plugin-tailwindcss` (auto-sorts Tailwind classes)
- Config in `.prettierrc` at project root
- Integrated with ESLint via `eslint-config-prettier`
- Run on save (editor) and in CI (GitHub Actions)
- Settings: single quotes, no semicolons, 2-space indent, trailing commas, 100 char print width

```json
{
  "semi": false,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "plugins": ["prettier-plugin-tailwindcss"]
}
```

**Commit Convention:** Conventional Commits

- Format: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Scopes: `auth`, `checkout`, `dashboard`, `webhooks`, `landing`, `legal`, `infra`
- Examples:
  - `feat(checkout): add coupon code input with validation`
  - `fix(webhooks): handle duplicate Stripe event IDs`
  - `chore(infra): configure GitHub Actions CI pipeline`
- Enforced via `commitlint` + `husky` pre-commit hook
- Breaking changes: `feat(auth)!: switch to server-side session cookies`

### Enforcement Guidelines

**All AI Agents MUST:**

- Follow naming conventions exactly (snake_case in Firestore, camelCase in code, PascalCase for components)
- Use Zod schemas for all data flowing between boundaries (webhook → server, server → client)
- Place components in feature directories, not flat in `components/`
- Use the structured API response format for all route handlers
- Never import server-only modules in client components
- Format code with Prettier before committing
- Use Conventional Commits format for all commit messages

**Anti-Patterns:**

- Mixing `snake_case` and `camelCase` in Firestore documents
- Using `any` type instead of Zod-inferred types
- Placing API keys or secrets in client-accessible files
- Creating global state for data that should be fetched per-page
- Importing `firebase-admin` in client components

## Project Structure & Boundaries

### Complete Project Directory Structure

```
wardenweb/
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions: lint, typecheck, test
├── e2e/
│   ├── checkout.spec.ts              # E2E: subscription checkout flow
│   ├── auth.spec.ts                  # E2E: sign-in/sign-out flows
│   └── dashboard.spec.ts             # E2E: dashboard actions (upgrade, cancel)
├── public/
│   ├── favicon.ico
│   └── images/                       # Static images (logo, app screenshots)
├── src/
│   ├── app/
│   │   ├── layout.tsx                # Root layout (HTML head, fonts, providers)
│   │   ├── page.tsx                  # Landing page (/)
│   │   ├── loading.tsx               # Root loading state
│   │   ├── error.tsx                 # Root error boundary
│   │   ├── globals.css               # Tailwind base + custom properties
│   │   ├── pricing/
│   │   │   └── page.tsx              # Pricing + checkout (/pricing)
│   │   ├── dashboard/
│   │   │   ├── layout.tsx            # Dashboard layout (auth-protected)
│   │   │   ├── page.tsx              # Account dashboard (/dashboard)
│   │   │   └── loading.tsx           # Dashboard loading skeleton
│   │   ├── privacy/
│   │   │   └── page.tsx              # Privacy policy (/privacy)
│   │   ├── terms/
│   │   │   └── page.tsx              # Terms of service (/terms)
│   │   └── api/
│   │       ├── auth/
│   │       │   └── session/
│   │       │       └── route.ts      # POST: create session, DELETE: destroy
│   │       ├── webhooks/
│   │       │   └── stripe/
│   │       │       └── route.ts      # POST: Stripe webhook handler
│   │       └── subscription/
│   │           ├── upgrade/
│   │           │   └── route.ts      # POST: upgrade to yearly
│   │           └── cancel/
│   │               └── route.ts      # POST: cancel subscription
│   ├── components/
│   │   ├── ui/                       # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── alert.tsx
│   │   │   └── skeleton.tsx
│   │   ├── auth/
│   │   │   ├── SignInForm.tsx         # Email/password sign-in
│   │   │   ├── GoogleSignInButton.tsx # Google OAuth button
│   │   │   └── AuthGuard.tsx         # Client-side auth check wrapper
│   │   ├── checkout/
│   │   │   ├── PlanSelector.tsx       # Monthly/yearly plan cards
│   │   │   ├── CouponInput.tsx        # Coupon code entry + validation
│   │   │   └── CheckoutForm.tsx       # Stripe Elements wrapper
│   │   ├── dashboard/
│   │   │   ├── SubscriptionCard.tsx   # Current plan + status display
│   │   │   ├── PaymentHistory.tsx     # Past invoices list
│   │   │   ├── UpgradeButton.tsx      # Upgrade to yearly CTA
│   │   │   ├── CancelDialog.tsx       # Cancel confirmation dialog
│   │   │   └── PaymentWarning.tsx     # Past-due alert banner
│   │   └── layout/
│   │       ├── Header.tsx             # Navigation header
│   │       ├── Footer.tsx             # Footer with legal links
│   │       └── CookieBanner.tsx       # GDPR cookie consent
│   ├── lib/
│   │   ├── firebase/
│   │   │   ├── client.ts             # Firebase client SDK init
│   │   │   ├── admin.ts              # Firebase Admin SDK init (server-only)
│   │   │   ├── auth.ts               # Auth helpers (session cookie, token verify)
│   │   │   └── firestore.ts          # Firestore read/write helpers
│   │   ├── stripe/
│   │   │   ├── client.ts             # Stripe.js client init
│   │   │   ├── server.ts             # Stripe Node SDK init (server-only)
│   │   │   └── webhooks.ts           # Webhook handler + event routing
│   │   ├── schemas/
│   │   │   ├── user.ts               # User document Zod schema
│   │   │   ├── subscription.ts       # Subscription Zod schema
│   │   │   └── webhook-events.ts     # Stripe webhook payload schemas
│   │   └── utils.ts                  # Generic utilities (date formatting, etc.)
│   ├── contexts/
│   │   └── AuthContext.tsx            # Firebase Auth React context + provider
│   ├── hooks/
│   │   ├── useAuth.ts                # Auth state hook (wraps AuthContext)
│   │   └── useSubscription.ts        # Fetch subscription data from Firestore
│   ├── types/
│   │   └── index.ts                  # Shared TypeScript types (Zod-inferred)
│   └── middleware.ts                  # Next.js middleware (session cookie validation)
├── .env.example                       # Environment variable template
├── .env.local                         # Local dev secrets (gitignored)
├── .gitignore
├── .husky/
│   └── commit-msg                     # commitlint hook
├── .prettierrc                        # Prettier configuration
├── commitlint.config.ts               # Conventional Commits config
├── components.json                    # shadcn/ui configuration
├── eslint.config.mjs                  # ESLint configuration
├── next.config.ts                     # Next.js configuration
├── package.json
├── playwright.config.ts               # Playwright E2E configuration
├── postcss.config.mjs                 # PostCSS (Tailwind)
├── tailwind.config.ts                 # Tailwind CSS configuration
├── tsconfig.json                      # TypeScript configuration
└── vitest.config.ts                   # Vitest unit test configuration
```

### Architectural Boundaries

**API Boundaries:**

- `/api/webhooks/stripe` — Stripe-only (no auth required, signature verification instead)
- `/api/auth/*` — Public (receives Firebase ID token, returns session cookie)
- `/api/subscription/*` — Protected (requires valid session cookie)

**Component Boundaries:**

- `components/ui/` — Pure presentational, no business logic, no data fetching
- `components/{feature}/` — Feature-specific, may use hooks for data
- `components/layout/` — Shared across pages, may access auth context

**Service Boundaries:**

- `lib/firebase/client.ts` — Client-safe imports only (browser)
- `lib/firebase/admin.ts` — Server-only (API routes, middleware)
- `lib/stripe/client.ts` — Client-safe (Stripe.js, publishable key)
- `lib/stripe/server.ts` — Server-only (Stripe Node SDK, secret key)

**Data Boundaries:**

- Firestore `users/{uid}` — Read via hooks (client) or admin SDK (server)
- Firestore `coupon_batches/{batchId}` — Read-only from client, write from Stripe dashboard
- Stripe API — Server-only access via `lib/stripe/server.ts`

### Requirements to Structure Mapping

**FR Category → Directory Mapping:**

| FR Category                | Primary Location                                                   |
| -------------------------- | ------------------------------------------------------------------ |
| Auth (FR1-4)               | `components/auth/`, `lib/firebase/auth.ts`, `api/auth/`            |
| Landing (FR5-7)            | `app/page.tsx`, `components/layout/`                               |
| Checkout (FR8-12)          | `app/pricing/`, `components/checkout/`, `lib/stripe/`              |
| Dashboard (FR13-20)        | `app/dashboard/`, `components/dashboard/`                          |
| Webhooks (FR21-25)         | `api/webhooks/stripe/`, `lib/stripe/webhooks.ts`                   |
| Legal (FR26-29)            | `app/privacy/`, `app/terms/`, `components/layout/CookieBanner.tsx` |
| Account Deletion (FR30-31) | Manual via support (no code for MVP)                               |
| Security (FR32-34)         | `middleware.ts`, `lib/firebase/admin.ts`, `.env.*`                 |

**Cross-Cutting Concerns:**

| Concern               | Location                                                                        |
| --------------------- | ------------------------------------------------------------------------------- |
| Auth state            | `contexts/AuthContext.tsx`, `hooks/useAuth.ts`, `middleware.ts`                 |
| Stripe-Firestore sync | `lib/stripe/webhooks.ts`, `lib/firebase/firestore.ts`                           |
| Data validation       | `lib/schemas/*.ts`                                                              |
| Error handling        | `app/error.tsx`, API route try/catch, `components/dashboard/PaymentWarning.tsx` |
| Environment config    | `.env.local`, `.env.example`, Vercel env vars                                   |

### Integration Points

**Internal Communication:**

- Pages → Hooks → Firestore (client reads)
- Pages → API routes → Stripe SDK (server actions)
- Middleware → Firebase Admin → session validation

**External Integrations:**

- Firebase Auth: `lib/firebase/client.ts` (browser) + `lib/firebase/admin.ts` (server)
- Stripe: `lib/stripe/client.ts` (Stripe.js) + `lib/stripe/server.ts` (Node SDK)
- Firebase Analytics: Loaded conditionally after cookie consent in root layout

**Data Flow:**

```
User Browser
    ↓ (sign-in)
Firebase Auth SDK → ID Token → /api/auth/session → Session Cookie
    ↓ (checkout)
Stripe.js → Stripe API → Subscription Created
    ↓ (webhook)
Stripe → /api/webhooks/stripe → Verify Signature → Firestore Update
    ↓ (dashboard)
Firestore Read → components/dashboard/* → Display subscription state
```

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:**

- Next.js 16.1.x + TypeScript + Tailwind + App Router: fully compatible standard stack
- Firebase JS SDK v12.9.x + Next.js: compatible (client/admin SDK separation handled)
- Stripe + Next.js API routes: standard integration, well-documented
- shadcn/ui + Tailwind v4: designed for each other
- Zod + React Hook Form: first-class integration
- Prettier + ESLint: integrated via eslint-config-prettier (no conflicts)
- commitlint + husky: standard enforcement, no build impact
- Vitest + Next.js 16: officially recommended
- Vercel + Next.js: native support
- No contradictory decisions found

**Pattern Consistency:**

- snake_case in Firestore aligns with Stripe webhook payloads (no conversion at boundary)
- camelCase in code aligns with TypeScript/React conventions
- Zod `.transform()` handles Firestore-to-frontend conversion cleanly
- Feature-based component organization aligns with route structure
- Prettier enforces consistent formatting across all agents
- Conventional Commits enforce consistent git history

**Structure Alignment:**

- Every API route maps to a documented API pattern
- Every component directory maps to a PRD feature area
- Service boundaries (client vs server) enforced by file separation
- Config files (.prettierrc, commitlint, husky) in project root

### Requirements Coverage Validation

**Functional Requirements: 34/34 covered**

| FR Range | Category  | Architecture Support                                                                                |
| -------- | --------- | --------------------------------------------------------------------------------------------------- |
| FR1-4    | Auth      | Firebase Auth + session cookies + AuthContext + middleware                                          |
| FR5-7    | Landing   | `app/page.tsx`, SSR cached, Header/Footer                                                           |
| FR8-12   | Checkout  | `app/pricing/`, Stripe.js, PlanSelector, CouponInput, CheckoutForm                                  |
| FR13-20  | Dashboard | `app/dashboard/`, SubscriptionCard, PaymentHistory, UpgradeButton, CancelDialog, Stripe Portal link |
| FR21-25  | Webhooks  | `/api/webhooks/stripe`, signature verify, idempotency, event routing                                |
| FR26-29  | Legal     | `app/privacy/`, `app/terms/`, CookieBanner, conditional Analytics                                   |
| FR30-31  | Deletion  | Manual via support for MVP (documented)                                                             |
| FR32-34  | Security  | Firestore rules, middleware auth, .env management                                                   |

**Non-Functional Requirements: 16/16 covered**

| NFR                  | Architecture Support                             |
| -------------------- | ------------------------------------------------ |
| LCP < 2.5s           | SSR + caching for static pages, Turbopack builds |
| FID < 100ms          | Minimal JS, React Compiler auto-memoization      |
| CLS < 0.1            | Skeleton loading states, fixed layouts           |
| Dashboard < 2s       | Direct Firestore reads                           |
| Checkout < 30s       | Single-page flow, Stripe Elements                |
| HTTPS                | Vercel enforces by default                       |
| HttpOnly cookies     | Server-side session cookie architecture          |
| Webhook signatures   | `constructEvent()` with secret                   |
| API key security     | .env + Vercel vars, no NEXT*PUBLIC* for secrets  |
| Firestore rules      | Documented in security section                   |
| Stripe retry 3x      | Stripe client config                             |
| Webhook idempotency  | Event ID dedup + Firestore transactions          |
| 200 response < 5s    | Vercel serverless, lightweight handler           |
| Sync < 30s           | Webhook → immediate Firestore write              |
| Session 7-day expiry | Cookie expiry + activity refresh                 |
| WCAG 2.1 A           | shadcn/ui Radix primitives, keyboard nav         |

### Implementation Readiness Validation

**Decision Completeness:** All critical and important decisions documented with versions, rationale, and concrete examples.

**Structure Completeness:** Full directory tree with 50+ files, every file mapped to requirements.

**Pattern Completeness:** Naming, structure, format, communication, process, formatting, and commit patterns all defined.

### Gap Analysis Results

**Critical Gaps:** 0
**Important Gaps:** 0
**Nice-to-Have Gaps:** 0

### Architecture Completeness Checklist

**Requirements Analysis**

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**

- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**Implementation Patterns**

- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented
- [x] Code formatting configured (Prettier)
- [x] Commit convention defined (Conventional Commits)

**Project Structure**

- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**

- Clean service-boundary separation (client vs server for Firebase and Stripe)
- Every FR and NFR maps to specific architectural components
- Consistency patterns prevent AI agent conflicts
- Standard, well-documented tech stack minimizes risk
- Code formatting and commit conventions ensure clean codebase

**Areas for Future Enhancement:**

- Monitoring/alerting (post-MVP, Vercel Analytics for now)
- Advanced caching strategies (post-MVP, as traffic grows)

### Implementation Handoff

**AI Agent Guidelines:**

- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Format code with Prettier, use Conventional Commits
- Refer to this document for all architectural questions

**First Implementation Priority:**

```bash
npx create-next-app@latest wardenweb --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"
```
