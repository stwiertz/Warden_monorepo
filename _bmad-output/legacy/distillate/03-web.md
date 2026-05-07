> This section covers WardenWeb (Next.js + Stripe subscription portal) full planning state. Part 3 of 8 of the Warden legacy distillate.

## Identity & Positioning
- WardenWeb = subscription-management portal for Warden mobile; "Reader App" model bypasses 30% app store fees
- Three jobs: (1) explain Warden (landing), (2) hand off to Stripe Checkout (pricing), (3) show subscription status + link to Stripe Portal (dashboard)
- WardenWeb is the door, mobile is the product
- Marketing channel: Discord word-of-mouth + coupon links among EVA After-h coaches; niche; no paid ads at MVP
- Domain: web_app, complexity low-medium, greenfield (created 2026-02-05, architecture finalized 2026-02-06, UX 2026-04-02, sprint-change 2026-04-16)
- Author: solo dev / AI-assisted

## Tech Stack & Versions
- Framework: Next.js 16.1.x (latest stable as of Feb 2026), App Router, src/ directory, Turbopack (stable default), TypeScript strict, `@/*` import alias
- Init: `npx create-next-app@latest wardenweb --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"` (Epic 1 Story 1.1)
- Styling: Tailwind CSS v4
- UI: shadcn/ui (Radix primitives, copy-paste, dark theme via CSS variables); only 7 components installed: Button, Card, Dialog, Input, Badge, Alert, Skeleton
- Auth: Firebase JS SDK v12.9.x (client) + Firebase Admin SDK (server); Firebase project SHARED with mobile (same auth, same Firestore)
- DB: Firestore, region `europe-west` (GDPR-locked)
- Payments: Stripe (Node SDK server, Stripe.js client)
- Validation: Zod v3.x — runtime validation at all boundaries (webhooks, forms, Firestore reads); shared client/server schemas; TypeScript inference via `z.infer`
- Forms: React Hook Form + Zod
- State: React Context only (`AuthContext` for `{user, loading, error}`); no Zustand/React Query (subscription data fetched per page)
- Hosting: Vercel (native Next.js, serverless functions for API routes, edge for static, preview deploys on PRs); free tier sufficient for MVP
- Testing: Vitest 4.x (unit) + React Testing Library (components) + Playwright (E2E checkout/auth/dashboard); Vitest is Next.js recommended
- CI/CD: GitHub Actions (lint/typecheck/unit/E2E on PR) + Vercel (preview on PR, production on main merge)
- Code formatting: Prettier (semi:false, singleQuote:true, trailingComma:"all", printWidth:100, tabWidth:2) + `prettier-plugin-tailwindcss` (auto-sorts classes); integrated via eslint-config-prettier
- Commits: Conventional Commits enforced via commitlint + husky pre-commit (`feat`/`fix`/`docs`/`style`/`refactor`/`test`/`chore`; scopes `auth`/`checkout`/`dashboard`/`webhooks`/`landing`/`legal`/`infra`)
- Rejected: SaaS boilerplates (Divjoy/Makerkit/supastarter) — paid $100-400+, excessive features (team billing/admin/email), opinionated non-standard patterns, harder for AI agents

## Routing & Rendering Strategy
- App Router routes: `/` (landing, SSR + cached), `/pricing` (client-interactive), `/dashboard` (protected, fresh reads), `/privacy` (static), `/terms` (static)
- API routes: `/api/auth/session` (POST create, DELETE destroy session cookie), `/api/webhooks/stripe` (POST), `/api/subscription/upgrade`, `/api/subscription/cancel`
- Caching: Next.js built-in only (`cacheLife` + revalidation for static); Dashboard always fresh from Firestore (state changes via webhooks); no external caching layer at MVP
- Real-time: NONE — no WebSocket, no Firestore `onSnapshot`; webhook-driven async updates; dashboard reads on load only (revised constraint per Sprint Change Proposal Story 5.1)
- Post-payment sync: Stripe webhook → Firestore update → app reads on next dashboard load
- SEO priority: Landing=Medium (meta+OG), Pricing=Low (indexable but not priority), Dashboard=None (noindex behind auth), Legal=Low

## Authentication Architecture
- Provider: Firebase Auth (Google Sign-In via `signInWithPopup` + Email/Password via `signInWithEmailAndPassword`)
- Auth flow: client signs in → `user.getIdToken()` → POST to `/api/auth/session` with ID token → server creates session cookie via `createSessionCookie()` → client redirects to dashboard
- Session: HttpOnly + Secure + SameSite=Lax cookies; 7-day expiry with activity-based refresh (per PRD NFR12 auto-logout after 7 days inactivity)
- Route protection: dual layer — `middleware.ts` validates cookie + redirects unauth from `/dashboard/*`; API routes independently re-validate (defense in depth)
- Public routes: landing, pricing, legal (no auth)
- Auth modal pattern: lazy auth — don't ask sign-in until user picks plan; modal overlay on /pricing with Google button + email/password form
- AuthContext fallback UI per NFR15 (graceful UI if Firebase service unavailable)
- Account creation happens at checkout time (FR4)

## Stripe Integration
- API key strategy: server-side only `STRIPE_SECRET_KEY`; client uses `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`; secrets in Vercel env vars + `.env.local` (gitignored); `.env.example` committed
- Checkout: server-side creates Stripe Checkout Session for selected plan; full redirect to Stripe-hosted page (NOT embedded — maximum trust)
- Coupon: passed to Checkout Session via URL param; validated by Stripe; deferred billing date displayed
- Customer Portal: `stripe.billingPortal.sessions.create()` server-side; return URL `/dashboard`; portal handles payment history (FR17), plan switching with proration (FR18), cancellation (FR19), payment method updates (FR20)
- Portal prerequisites (human): configured in Stripe Dashboard — enable plan switching, cancellation, payment-method updates; portal branding (logo, colors, return URL)
- Webhook endpoint: `/api/webhooks/stripe` (no auth — uses signature instead)
- Webhook signature verification: `stripe.webhooks.constructEvent()` with `STRIPE_WEBHOOK_SECRET`; reject unsigned/invalid → 400; valid → parse + route by event type (FR24)
- Webhook events handled: `invoice.paid` (activate/renew → `status: "active"`, `plan`, `current_period_end`, `stripe_subscription_id`; create user doc if missing) — FR21; `customer.subscription.deleted` (→ `status: "canceled"`) — FR22; `invoice.payment_failed` (→ `status: "past_due"`) — FR23
- Webhook idempotency: dual strategy — (1) event ID dedup stored in Firestore (skip if already processed, return 200); (2) Firestore transactions to check current state before update (race-condition protection)
- Webhook error handling: log error + return 200 (prevents Stripe retries on permanent failures)
- Reliability: 200 response within 5s (NFR14); Firestore syncs within 30s of webhook (NFR16); Stripe API transient failures retried up to 3 attempts (NFR13)
- Retry handling: at-least-once delivery from Stripe; idempotency layer absorbs duplicates
- Subscription actions: upgrade and cancel originally planned as custom API (`/api/subscription/upgrade`, `/api/subscription/cancel`) — REVISED: delegated to Stripe Customer Portal per Sprint Change Proposal

## Web Cross-cutting Integrations (web-side detail; see also `05-architecture-cross-cutting.md`)
- Firebase project SHARED between mobile (Warden) and web (WardenWeb) — same Firebase Auth, same Firestore database, same project; auth provider config (apiKey, authDomain, projectId) MUST align between web and mobile clients
- Firestore region locked to `europe-west` for GDPR — mobile must use the same project/region
- Firestore collections: `users/{uid}` (subscription state), `coupon_batches/{batchId}` (coupon redemption tracking; client read-only, writes from Stripe dashboard)
- `users/{uid}` document schema written by web (snake_case to match Stripe webhook payloads):
  - `status`: "active" | "past_due" | "canceled" (and "canceling" used in UI badge for cancel-at-period-end)
  - `plan`: monthly | yearly
  - `current_period_end`: Firestore Timestamp (converted from Stripe Unix seconds)
  - `stripe_subscription_id`: string
  - `stripe_customer_id`: implicit from webhook payloads (set when invoice.paid creates/updates doc)
  - `redeemed_batches`: array (referenced in naming-convention examples)
  - email implied via Auth (FR13 displays account email)
- Mobile entitlement check: mobile reads `users/{uid}` from same Firestore — CONFLICT: web writes rich schema, mobile legacy reads `isPaid` boolean only (see `05-architecture-cross-cutting.md`)
- Doc creation: webhook handler creates `users/{uid}` if absent on `invoice.paid` (FR21 / Story 4.2 acceptance)
- Naming convention chosen for cross-system consistency: Firestore stores snake_case (matches Stripe webhook payloads → no conversion at boundary), code uses camelCase (TS/React); conversion via Zod `.transform()` in `src/lib/firebase/`
- Date formats: Firestore=Timestamp; Stripe=Unix seconds; JSON API responses=ISO 8601; UI=`Intl.DateTimeFormat` (no date library)
- Schemas live in `src/lib/schemas/{user.ts,subscription.ts,webhook-events.ts}` — `SubscriptionResponse` Zod schema referenced as part of webhook validation surface
- Firebase Analytics conditionally loaded only AFTER cookie consent (FR29)

## Project Structure (Next.js, src-dir)
- `src/app/`: layout.tsx, page.tsx (landing), loading.tsx, error.tsx, globals.css, pricing/page.tsx, dashboard/{layout,page,loading}.tsx (auth-protected layout), privacy/page.tsx, terms/page.tsx
- `src/app/api/`: auth/session/route.ts, webhooks/stripe/route.ts, subscription/{upgrade,cancel}/route.ts
- `src/components/ui/`: shadcn primitives (button, card, dialog, input, badge, alert, skeleton)
- `src/components/{auth,checkout,dashboard,layout}/`: feature folders (NOT type-based)
  - auth/: SignInForm, GoogleSignInButton, AuthGuard
  - checkout/: PlanSelector, CouponInput, CheckoutForm
  - dashboard/: SubscriptionCard, PaymentHistory, UpgradeButton, CancelDialog, PaymentWarning (PaymentHistory/UpgradeButton/CancelDialog removed scope post-Sprint Change → portal-first)
  - layout/: Header, Footer, CookieBanner
- `src/lib/firebase/`: client.ts, admin.ts, auth.ts, firestore.ts (client/admin separated for SSR safety)
- `src/lib/stripe/`: client.ts, server.ts, webhooks.ts (event routing)
- `src/lib/schemas/`: user.ts, subscription.ts, webhook-events.ts (Zod)
- `src/contexts/AuthContext.tsx`, `src/hooks/{useAuth,useSubscription}.ts`, `src/types/index.ts`, `src/middleware.ts`
- Top-level: `e2e/{checkout,auth,dashboard}.spec.ts`, `.github/workflows/ci.yml`, `.husky/commit-msg`, `.prettierrc`, `commitlint.config.ts`, `components.json`, `playwright.config.ts`, `tailwind.config.ts`, `vitest.config.ts`
- Tests co-located: `src/lib/__tests__/stripe.test.ts`; E2E in top-level `e2e/`

## Naming Conventions (CRITICAL — AI agent enforcement)
- Firestore: snake_case collections (`users`, `coupon_batches`) + snake_case fields (`current_period_end`, `redeemed_batches`)
- API routes: kebab-case directories; query params camelCase (`?batchId=abc`); JSON response fields camelCase
- Code: PascalCase components/types, camelCase utilities/files (`stripeClient.ts`), camelCase hooks with `use` prefix, SCREAMING_SNAKE_CASE constants (`STRIPE_PLANS`, `AUTH_COOKIE_NAME`); Tailwind utilities only (no custom CSS classes)
- API response shape: success `{ data: { ... } }`; error `{ error: { code: "ERR_CODE", message: "..." } }`
- Anti-patterns: mixing snake/camel in Firestore docs; using `any` instead of Zod-inferred types; secrets in client-accessible files; global state for per-page data; importing `firebase-admin` in client components

## Functional Requirements (34 total)
- Auth (FR1-4): Google sign-in, Email/Password sign-in, sign-out, account creation during checkout
- Landing/Discovery (FR5-7): value-prop landing, navigate to pricing, app download links iOS/Android
- Subscription/Checkout (FR8-12): view plans (monthly €7.99 / yearly €79.90), subscribe monthly via Stripe, subscribe yearly via Stripe, apply coupon, see deferred billing date
- Dashboard (FR13-20): view email, view plan, view status (active/past_due/canceled), view next payment date, view payment history (via portal), upgrade monthly→yearly (via portal), cancel (via portal), access Stripe Customer Portal
- Webhooks (FR21-25): process invoice.paid, process customer.subscription.deleted, process invoice.payment_failed, verify signatures, dashboard past_due warning
- Legal (FR26-29): Privacy Policy page, Terms of Service page, cookie consent banner, conditional Firebase Analytics loading
- Account Deletion (FR30-31): user requests via support email; support cancels Stripe + deletes Firestore doc + deletes Firebase Auth account
- Security (FR32-34): Firestore rules users own data only, API routes auth-validate, env vars for Stripe keys

## Non-Functional Requirements (16 total + WCAG = 17)
- Performance: LCP < 2.5s (landing/pricing), FID < 100ms, CLS < 0.1, checkout < 30s end-to-end, dashboard < 2s post-auth
- Security: HTTPS enforced (Vercel default), HttpOnly cookies (Firebase Auth), Stripe webhook signature verification, server-only API keys (no NEXT_PUBLIC_ prefix for secrets), Firestore rules `users/{uid}` only, PCI delegated to Stripe (no card data stored), 7-day inactivity auto-logout
- Integration: Stripe API retry 3x, idempotent webhook 200 within 5s, Firebase Auth graceful fallback UI, no offline-first (web)
- Data integrity: Firestore matches Stripe within 30s of webhook, at-least-once delivery + idempotency, Stripe dashboard = source of truth for payments
- Accessibility: WCAG 2.1 Level A — color contrast AA, keyboard nav (Radix primitives default), 2px orange focus-visible outline, semantic HTML (`<nav>`/`<main>`/`<footer>`/`<h1-3>`/`<button>`), labeled inputs, status badges with text+color (not color-only), `prefers-reduced-motion`, skip-to-content link, alt text on logo
- Browsers: last 2 versions of Chrome, Firefox, Safari, Edge; no IE11
- Testing strategy (pragmatic for MVP): Browser DevTools contrast check, manual keyboard tab-through, Chrome device mode + real phone, `npx lighthouse` accessibility in CI, VoiceOver pass before launch; full audit deferred post-MVP

## GDPR / Legal / Compliance
- Base légale: contrat (subscription service)
- Data collected: email, name (via Google), subscription history, coupons used
- Payment data: handled by Stripe (PCI-DSS) — never stored in WardenWeb
- Right to erasure: account deletion flow — (1) cancel Stripe subscription if active, (2) delete `users/{uid}`, (3) delete Firebase Auth account, (4) confirmation + sign-out; MVP via support email (FR30/31), V2 self-serve button
- Data residency: Firestore `europe-west` region locked
- Cookie banner: required (Firebase Analytics uses cookies); accept/reject choice persisted in localStorage; banner does not reappear; Analytics loads ONLY after acceptance
- Legal pages: `/privacy` (collected data, purposes, user rights, DPO contact), `/terms` (subscription conditions, cancellation, limitations); both statically rendered + cached; linked from footer

## Web User Journeys
- J1 New Subscriber via coupon: Discord link `?coupon=XXX` → Landing (5s) → Pricing (auto-applied coupon, 5s) → Auth modal Google/Email (10s) → Stripe Checkout w/ deferred billing date (15s) → /dashboard?success=1
- J2 Returning Subscriber: visits site → session cookie auto-signs in → Dashboard (plan/status/next-date/email) → "Manage billing" → Stripe Customer Portal → returns to /dashboard
- J3 Payment Failure Recovery: Stripe webhook `invoice.payment_failed` → Firestore `status=past_due` → user dashboard shows warning banner + "Update payment method" button → Stripe Customer Portal → card update → Stripe auto-retries → next visit shows Active
- J4 Cancellation: Dashboard → Cancel → confirmation dialog "access until [date]" → Stripe cancel-at-period-end → status badge "Canceling" → period end → webhook `subscription.deleted` → status "Canceled" + Resubscribe path; NO exit survey for MVP, NO guilt-trip
- J5 Passive→Active Conversion: Lucas receives clip on Discord → curious → Landing (must work for non-coaches too) → Pricing → same checkout flow as J1
- Status badge mapping: green=active, amber=past_due, red=canceled, gray=canceling

## Required Environment Variables
- Server-only (no NEXT_PUBLIC_): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, Firebase Admin credentials
- Client-safe: `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID` (and other public Firebase config)
- Local: `.env.local` (gitignored); template: `.env.example` (committed); production/preview: Vercel Environment Variables
- Rule: server secrets never appear in client bundles

## Sprint Change Proposal 2026-04-16 — AUTHORITATIVE OVER ORIGINAL PRD
- Trigger: Epic 4 retro + Stripe best-practices consultation; Root directive "delegate to Stripe everything I can"
- Epic 5 reduced from 5 stories → 3 stories (portal-first); ~2 stories of custom UI eliminated
- REMOVED stories: 5.2 Payment History, 5.3 Upgrade Monthly→Yearly, 5.4 Cancel Subscription — all delegated to Stripe Customer Portal
- REVISED 5.1: added "no onSnapshot real-time listeners" constraint (load once from Firestore)
- NEW 5.2: Stripe Customer Portal Integration (server-side portal session via `stripe.billingPortal.sessions.create()`, "Manage Subscription" button, return URL = /dashboard); also moves "Dashboard" link into header for signed-in users (fulfils deferred nav task from Story 1.3)
- NEW 5.3: Payment Failure Warning Banner (`past_due` warning + Update-payment CTA; `canceled` info banner + Resubscribe CTA)
- NEW Epic 7 added (Launch Readiness) — absorbs carried retro debt
- PRD unchanged — all FRs still delivered (FR17/18/19 satisfied via Stripe Customer Portal); architecture doc updates deferred to implementation
- Conflict resolution rule: where original PRD/epics show custom payment-history/upgrade/cancel UI, Sprint Change Proposal supersedes — Stripe Customer Portal handles these

## Web Risks
- Stripe webhook sync (HIGH severity for data integrity): mitigated by idempotent handlers + signature verification + retry; resolved via Epic 4 dual-strategy idempotency
- Data security ("vibe coding risk"): Firestore rules + server-side validation + no client-side secrets — Epic 7.1 deploys rules to production (carried debt)
- Auth token leakage: Firebase Auth best practices + secure HttpOnly cookie handling
- PlanCta hydration mismatch (`disabled={null}` vs `disabled={true}`) — known issue, scheduled in Story 7.2

## Web Brownfield Issues Parked (must surface in monorepo replanning — see `05-architecture-cross-cutting.md`)
- Stripe API version pin mismatch: code pins `"2026-03-25.dahlia"` while installed `@stripe/stripe-js` types are `"2026-04-22.dahlia"` — type-level inconsistency to resolve
- Test-file type errors (unspecified location)
- PlanCta hydration mismatch (Story 7.2)
- Carried retro debt: Firestore security rules not yet deployed to production (Story 7.1), Firebase auth E2E not fully verified (Story 7.2)
- Vitest parallelism flake (action item from Epic 4 retro)

## Web Rejected Alternatives
- SaaS boilerplates (Divjoy/Makerkit/supastarter): paid, excessive features, opinionated non-standard patterns harder for AI agents — chose `create-next-app` minimal
- Custom payment forms: Stripe Checkout more trusted, handles edge cases — full-page redirect to Stripe-hosted
- Custom payment-history/upgrade/cancel UI (originally Stories 5.2/5.3/5.4): duplicates Stripe Customer Portal — delegated to portal per Sprint Change Proposal
- WebSocket / `onSnapshot` real-time listeners: webhook-driven async sufficient; DB is source of truth refreshed on dashboard load
- Light/corporate SaaS aesthetic: feels out of place for gaming audience, kills trust — chose dark theme
- Long scrolling landing page with sections / testimonials / app screenshots: app not finished, no real testimonials, gaming audience sees through generic imagery — chose minimal hero + single CTA
- Feature comparison tables: only 2 plans differ by billing cycle not features — single price card each
- Animated illustrations / Lottie: adds complexity, delays ship date — chose CSS-only static
- Hamburger menu: only 2-3 nav links, always visible even on mobile
- Tablet-specific breakpoint: mobile layout works fine on tablet — only `md:` (768px+) breakpoint
- Custom components abstractions for V1: 7 shadcn primitives cover all needs — extract later only if pattern repeats
- Global state library (Zustand/React Query): minimal client state — React Context for auth only
