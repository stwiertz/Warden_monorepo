## Product Identity & Positioning
- WardenWeb: subscription-management portal for Warden mobile app (EVA After-h video review tool); "Reader App" model bypasses 30% app store fees
- Tagline: "Progresser plus vite en investissant moins de temps" (French; mobile app speaks French to coaches; web UI English with French tagline)
- Three jobs: (1) explain Warden (landing), (2) hand off to Stripe Checkout (pricing), (3) show subscription status + link to Stripe Portal (dashboard); WardenWeb is the door, mobile app is the product
- Marketing channel: Discord word-of-mouth + coupon links among EVA After-h coaches; niche; no paid ads at MVP
- Domain: web_app, complexity low-medium, greenfield (at original creation 2026-02-05)
- Author: Developer (single dev / AI-assisted); created 2026-02-05; architecture finalized 2026-02-06; UX spec 2026-04-02; sprint-change 2026-04-16

## User Segments
- Primary: Coach Thomas, 26 — EVA After-h coach, reviews from couch after work, mobile, tired; values speed/simplicity; arrives via Discord coupon link; visits WardenWeb only for billing (rare)
- Secondary: Active Player Lucas, 22 — converts from Passive Player after seeing coach's clip; self-analyzes own gameplay; subscribes individually (no team billing in V1)
- Passive Player: only visits WardenWeb out of curiosity; conversion opportunity into Active Player; landing copy must work for non-coaches too
- No team/group billing in V1 — individual subscriptions only

## Conversion Funnel & KPIs
- Funnel stages: Awareness (landing visits) → Interest (pricing views) → Intent (checkout initiated) → Drop-off (abandonment) → Conversion (Coupon→Paid) → Expansion (Monthly→Yearly upgrade)
- Business targets: 20 paying coaches in 3 months; monthly churn < 15%; Coupon→Retained ≥ 10% after trial
- Activation (mobile-side): first clip exported < 5 min; reviews/week ≥ 1; clips/review 3-5
- Tracked ratios: Visit→CheckoutStart, CheckoutStart→Complete, Coupon→Retained
- Critical UX moment: "I won't be charged yet" (Stripe shows deferred billing when coupon applied) reduces checkout anxiety

## Pricing & Plans
- Monthly: €7.99/mo
- Yearly: €79.90/yr (~17% savings vs 12×monthly = €95.88; positioned as "économisez 2 mois")
- Coupons: Stripe promotion codes; pass via URL param to Checkout Session; auto-shown on pricing page when present in URL
- Trial model: card capture upfront + coupon-based free period; "Vous ne serez pas débité avant le [date]"
- Coupon admin in V1: Stripe dashboard only (no in-app admin UI)

## MVP Scope (Original)
- IN: Landing, Pricing+Checkout, Account Dashboard (email/next-payment-date/history/upgrade/cancel/redeem coupon), Privacy Policy, Terms of Service, Cookie Banner
- OUT V1: Discord OAuth (Google/Email sufficient), Coupon Admin UI (Stripe dashboard suffices), Custom Analytics Dashboard (Firebase Analytics suffices), Team/Group Billing, Localization (English UI + French tagline only)
- Deferred from MVP (contingency): account deletion button (manual via support email), churn survey, in-dashboard coupon redemption (only at checkout)
- V2 Growth: Discord OAuth, Coupon Admin UI, account deletion button, advanced analytics dashboard
- V3 Vision: referral system (free months for inviters), team subscriptions, full French localization

## MVP Scope Revision (Sprint Change Proposal 2026-04-16) — AUTHORITATIVE OVER PRD
- Trigger: Epic 4 retro + Stripe best-practices consultation; Root directive "delegate to Stripe everything I can"
- Epic 5 reduced from 5 stories → 3 stories (portal-first); ~2 stories of custom UI eliminated
- REMOVED stories: 5.2 Payment History, 5.3 Upgrade Monthly→Yearly, 5.4 Cancel Subscription — all delegated to Stripe Customer Portal
- REVISED 5.1: added "no onSnapshot real-time listeners" constraint (load once from Firestore)
- NEW 5.2: Stripe Customer Portal Integration (server-side portal session via `stripe.billingPortal.sessions.create()`, "Manage Subscription" button, return URL = /dashboard); also moves "Dashboard" link into header for signed-in users (fulfils deferred nav task from Story 1.3)
- NEW 5.3: Payment Failure Warning Banner (`past_due` warning + Update-payment CTA; `canceled` info banner + Resubscribe CTA)
- NEW Epic 7 added (Launch Readiness) — absorbs carried retro debt
- PRD unchanged — all FRs still delivered (FR17/18/19 satisfied via Stripe Customer Portal); architecture doc updates deferred to implementation
- Conflict resolution rule: where original PRD/epics show custom payment-history/upgrade/cancel UI, Sprint Change Proposal supersedes — Stripe Customer Portal handles these

## Tech Stack & Versions
- Framework: Next.js 16.1.x (latest stable as of Feb 2026), App Router, src/ directory, Turbopack (stable default), TypeScript strict, `@/*` import alias
- Init: `npx create-next-app@latest wardenweb --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"` (must be Epic 1 Story 1.1)
- Styling: Tailwind CSS v4
- UI: shadcn/ui (Radix primitives, copy-paste, dark theme via CSS variables); only 7 components installed: Button, Card, Dialog, Input, Badge, Alert, Skeleton
- Auth: Firebase JS SDK v12.9.x (client) + Firebase Admin SDK (server); Firebase project shared with mobile app (same auth, same Firestore)
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

## Cross-cutting integrations
- Firebase project SHARED between mobile app (Warden) and web portal (WardenWeb) — same Firebase Auth, same Firestore database, same project; auth provider config (apiKey, authDomain, projectId) MUST align between web and mobile clients
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
- Mobile entitlement check: mobile reads `users/{uid}` from same Firestore to determine subscription state (this is the consumer-side contract — web is the writer, mobile is the reader)
- Doc creation: webhook handler creates `users/{uid}` if absent on `invoice.paid` (FR21 / Story 4.2 acceptance)
- Naming convention chosen for cross-system consistency: Firestore stores snake_case (matches Stripe webhook payloads → no conversion at boundary), code uses camelCase (TS/React); conversion via Zod `.transform()` in `src/lib/firebase/`
- Date formats: Firestore=Timestamp; Stripe=Unix seconds; JSON API responses=ISO 8601; UI=`Intl.DateTimeFormat` (no date library)
- Schemas live in `src/lib/schemas/{user.ts,subscription.ts,webhook-events.ts}` — `SubscriptionResponse` Zod schema referenced as part of webhook validation surface (specific schema content not in source docs but inferred location)
- Firebase Analytics conditionally loaded only AFTER cookie consent (FR29) — relevant if mobile shares analytics; web uses Firebase Analytics, mobile config independent

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

## UX & Design System
- Direction chosen: A (Clean Minimal) — soft borders, rounded cards, subtle orange accents, generous whitespace; rejected B (Bold Tactical/uppercase/grid) and C (Warm/emoji)
- Rationale: ship-speed; gaming-native via dark theme without heavy-handed tactical typography; aligns with Stripe Checkout's clean aesthetic for seamless handoff
- Theme: dark mode default (Tailwind `darkMode: "class"` + CSS vars)
- Colors: bg `#0F0F0F`, surface `#1A1A1A`, surface-elevated `#252525`, border `#333333`, text `#F0F0F0`, text-secondary `#999999`, accent (Warden orange) `#E8731A`, accent-hover `#F28A2E`, success `#22C55E`, warning `#F59E0B`, error `#EF4444`
- Contrast: text-primary on bg ~16:1 (AAA), text-secondary ~5.5:1 (AA), orange ~4.8:1 (AA large/bold)
- Typography: Inter (Google Font) — H1 800/32-48px, H2 700/24-32px, H3 600/20-24px, body 400/16px, small 500/14px, badge 600/12px; line-height 1.2 headings, 1.5 body
- Spacing base: 4px tokens (space-1 4px → space-16 64px); page padding 16px mobile / 32px desktop; max content width 1024px centered
- Border radius: buttons 6px (slightly sharp/tactical), cards 8px, badges 4px, full round only avatars/status dots
- Touch target: min 44x44px (`min-h-11 min-w-11`)
- Breakpoints: ONLY two — mobile (default, no prefix) + `md:` (768px+); no tablet-specific layout
- Layout pattern: stacked on mobile, side-by-side cards on desktop; full-width hero, single-column dashboard with wider card on desktop
- Component coverage: 100% of MVP needs from 7 shadcn components; NO custom components for V1; compositions (hero, plan-selector, status-card, etc.) built directly from primitives — extract later if pattern repeats
- Button hierarchy: primary=orange-fill (one per page section, full-width-in-cards on mobile), secondary=ghost/outline gray, destructive=ghost red (in confirmation dialogs only), link=text-only orange-on-hover
- Feedback: success=transient banner/redirect green; error=red alert top-of-content; warning=amber alert with action button (persists until resolved, not dismissible); loading=skeleton matching final shape
- Modal patterns: auth modal (Google + email/password Dialog), upgrade confirmation (proration), cancel confirmation ("access until [date]"); overlay-click closes
- Header: logo left + links right (Home, Pricing OR Dashboard if signed-in); sticky; "Sign in" when anonymous, "Sign out" when authenticated; active link orange
- Footer: centered Privacy / Terms / copyright; same on every page
- Reduced motion: respect `prefers-reduced-motion` (no animations for MVP anyway)
- Empty states: dashboard with no subscription → "No active subscription" + link to pricing; canceled → status + "Resubscribe" button

## Emotional/Brand Principles
- Boring is good — subscription portal should be invisible
- No dark patterns: no fake urgency, no countdown timers, no hidden cancellation flow, no guilt-trip on cancel ("coaches talk to each other on Discord — one bad experience spreads fast")
- Error = action — every error tells the user what to do next; no dead ends
- Ship working, polish later — no fake screenshots, no testimonials, no stock photos of "happy teams" (gaming audience sees through it)
- Trust through transparency — show billing dates/plan/status; no surprises
- Stage emotions: Landing=Clarity, Pricing=Confidence, Checkout=Safety (delegated to Stripe brand), Dashboard=Control, Error=Calm
- Defining experience tagline: "Subscribe from a Discord link in under 60 seconds"

## User Journeys
- J1 New Subscriber via coupon: Discord link `?coupon=XXX` → Landing (5s) → Pricing (auto-applied coupon, 5s) → Auth modal Google/Email (10s) → Stripe Checkout w/ deferred billing date (15s) → /dashboard?success=1
- J2 Returning Subscriber: visits site → session cookie auto-signs in → Dashboard (plan/status/next-date/email) → "Manage billing" → Stripe Customer Portal → returns to /dashboard
- J3 Payment Failure Recovery: Stripe webhook `invoice.payment_failed` → Firestore `status=past_due` → user dashboard shows warning banner + "Update payment method" button → Stripe Customer Portal → card update → Stripe auto-retries → next visit shows Active
- J4 Cancellation: Dashboard → Cancel → confirmation dialog "access until [date]" → Stripe cancel-at-period-end → status badge "Canceling" → period end → webhook `subscription.deleted` → status "Canceled" + Resubscribe path; NO exit survey for MVP, NO guilt-trip
- J5 Passive→Active Conversion: Lucas receives clip on Discord → curious → Landing (must work for non-coaches too) → Pricing → same checkout flow as J1
- Status badge mapping: green=active, amber=past_due, red=canceled, gray=canceling

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

## Epic Breakdown (7 epics)
- Epic 1 Project Foundation & Landing — FR5/6/7 — stories: 1.1 Init Next.js+tooling (Prettier, commitlint+husky, .env.example, shadcn init), 1.2 Landing page w/ value prop + iOS/Android download links + CTA → /pricing (SSR cached, mobile-first, WCAG-A), 1.3 Shared layout (Header w/ home+pricing nav, Footer w/ Privacy/Terms, CookieBanner persisting localStorage choice; conditional Analytics)
- Epic 2 Authentication & Identity — FR1/2/3/4/32/33/34 — stories: 2.1 Firebase + Google `signInWithPopup` → ID token → /api/auth/session → cookie → /dashboard + AuthContext, 2.2 Email/Password sign-in + registration (RHF + Zod inline errors), 2.3 Sign-out (Firebase signOut + DELETE /api/auth/session + clear context + redirect /), 2.4 Route protection middleware + Firestore rules + env-var secrets
- Epic 3 Subscription & Checkout — FR8/9/10/11/12 — stories: 3.1 Pricing page (2 plan cards, savings, mobile-first, WCAG-A), 3.2 Stripe Checkout for monthly+yearly (server-side session, redirect to Stripe, on success create `users/{uid}` doc + redirect /dashboard, prompt sign-in if anon, < 30s), 3.3 Coupon support (validate against Stripe, show discount + deferred billing date, error on invalid, can proceed without)
- Epic 4 Webhook Processing — FR21/22/23/24 — COMPLETE 3/3 — stories: 4.1 Stripe webhook endpoint w/ signature verify (constructEvent, 400 on fail, event-id dedup in Firestore, 200 < 5s), 4.2 Process invoice.paid (Firestore txn, set status=active/plan/current_period_end/stripe_subscription_id, create doc if missing, sync < 30s, retry 3x), 4.3 Process subscription.deleted (status=canceled) + payment_failed (status=past_due) — both transactional, both return 200 even on permanent error
- Epic 5 Dashboard & Subscription Management (Portal-First) — FR13-20+25 — REVISED 3 stories — stories: 5.1 Dashboard overview (email + plan + status badge + next payment date; Skeletons; load-once from Firestore, NO onSnapshot; < 2s), 5.2 Stripe Customer Portal Integration (server creates portal session, "Manage Subscription" button → portal handles history/upgrade/cancel/card-update, return URL /dashboard, webhooks update Firestore on changes; ALSO adds "Dashboard" header link for signed-in users — fulfils deferred nav from 1.3), 5.3 Payment Failure Warning Banner (past_due warning + Update-payment CTA; canceled info banner + Resubscribe CTA; status read from `users/{uid}` no real-time)
- Epic 6 Legal/Compliance/Analytics — FR26/27/28/29/30/31 — note FR28+29 implemented in Story 1.3 — stories: 6.1 Privacy + Terms pages (static cached, footer-linked), 6.2 Account deletion process (instructions in settings/privacy + support runbook for cascading delete)
- Epic 7 Launch Readiness (NEW per Sprint Change Proposal) — stories: 7.1 Firestore Security Rules deployment (carried Epic 2 retro #1), 7.2 Firebase Auth E2E + PlanCta hydration fix `disabled={null}` vs `disabled={true}` (carried Epic 2 retro #2 + Epic 3 retro #4), 7.3 Guided Payment Flow E2E walkthrough (Root-led: signup → monthly checkout → dashboard verify → simulated payment failure → past_due banner → portal fix → active → upgrade yearly → portal cancel → canceled persists), 7.4 Stripe Production Activation & Go-Live (BLOCKED by external dependency: company number from Root; live keys, webhook secret, DNS, Vercel prod, security review checklist)

## Sprint State (as of 2026-04-16)
- Done: Epic 4 (3/3 stories complete)
- In flight / Backlog: Epic 5 (3 revised stories — 5.1 next), Epic 7 (4 stories in backlog)
- Epic 5 prerequisite: configure Stripe Customer Portal in Stripe Dashboard before Story 5.2 (plan switching, cancellation, payment-method updates, branding, return URL)
- Epic 7.4 prerequisite: Root provides company number (external blocker)
- Action item from Epic 4 retro: diagnose Vitest parallelism flake before Epic 5 starts

## Required Environment Variables
- Server-only (no NEXT_PUBLIC_): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, Firebase Admin credentials
- Client-safe: `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID` (and other public Firebase config)
- Local: `.env.local` (gitignored); template: `.env.example` (committed); production/preview: Vercel Environment Variables
- Rule: server secrets never appear in client bundles

## Risks
- Stripe webhook sync (HIGH severity for data integrity): mitigated by idempotent handlers + signature verification + retry; resolved via Epic 4 dual-strategy idempotency
- Data security ("vibe coding risk"): Firestore rules + server-side validation + no client-side secrets — Epic 7.1 deploys rules to production (carried debt)
- Auth token leakage: Firebase Auth best practices + secure HttpOnly cookie handling
- PlanCta hydration mismatch (`disabled={null}` vs `disabled={true}`) — known issue, scheduled in Story 7.2

## Brownfield Issues Parked (must surface in monorepo replanning)
- Stripe API version pin mismatch: code pins `"2026-03-25.dahlia"` while installed `@stripe/stripe-js` types are `"2026-04-22.dahlia"` — type-level inconsistency to resolve
- Test-file type errors (unspecified location)
- PlanCta hydration mismatch (Story 7.2)
- Carried retro debt: Firestore security rules not yet deployed to production (Story 7.1), Firebase auth E2E not fully verified (Story 7.2)
- Vitest parallelism flake (action item from Epic 4 retro)

## Open Questions / Deferred
- Coupon Admin UI: Stripe dashboard for V1; self-serve admin UI deferred to V2
- Account deletion self-serve button deferred (V1 = manual via support email)
- Custom analytics dashboard deferred (V1 = Firebase Analytics)
- Discord OAuth deferred V2 (Google/Email sufficient V1)
- Full French localization deferred V3 (V1 = English UI + French tagline)
- Team subscriptions deferred V3
- Referral system deferred V3
- Monitoring/alerting beyond Vercel Analytics deferred post-MVP
- Advanced caching strategies deferred post-MVP
- Formal accessibility audit deferred post-MVP

## Rejected Alternatives
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
