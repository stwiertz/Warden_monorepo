---
stepsCompleted:
  [
    'step-01-validate-prerequisites',
    'step-02-design-epics',
    'step-03-create-stories',
    'step-04-final-validation',
  ]
inputDocuments:
  - '_bmad/planning-artifacts/prd.md'
  - '_bmad/planning-artifacts/architecture.md'
workflowType: 'epics'
project_name: 'WardenWeb'
user_name: 'Developer'
date: '2026-02-09'
---

# WardenWeb - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for WardenWeb, decomposing the requirements from the PRD, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: User can sign in using Google account
FR2: User can sign in using email and password
FR3: User can sign out from their account
FR4: User can create a new account during checkout flow
FR5: Visitor can view landing page with Warden app value proposition
FR6: Visitor can navigate from landing page to pricing page
FR7: Visitor can view app download links (iOS/Android)
FR8: User can view available subscription plans (monthly €7.99, yearly €79.90)
FR9: User can subscribe to monthly plan via Stripe checkout
FR10: User can subscribe to yearly plan via Stripe checkout
FR11: User can apply a coupon code during checkout
FR12: User can see deferred billing date when coupon is applied
FR13: Subscriber can view their account email
FR14: Subscriber can view their current subscription plan
FR15: Subscriber can view subscription status (active, past_due, canceled)
FR16: Subscriber can view next payment date
FR17: Subscriber can view payment history
FR18: Subscriber can upgrade from monthly to yearly plan
FR19: Subscriber can cancel their subscription
FR20: Subscriber can access Stripe Customer Portal to update payment method
FR21: System processes `invoice.paid` webhook to activate/renew subscription
FR22: System processes `customer.subscription.deleted` webhook to deactivate subscription
FR23: System processes `invoice.payment_failed` webhook to mark subscription as past_due
FR24: System verifies Stripe webhook signatures before processing
FR25: Dashboard displays payment failure warning when status is past_due
FR26: Visitor can view Privacy Policy page
FR27: Visitor can view Terms of Service page
FR28: Visitor can accept or reject analytics cookies via banner
FR29: System loads Firebase Analytics only after cookie consent
FR30: User can request account deletion via support email
FR31: Support can delete user account (Stripe cancel + Firestore delete + Auth delete)
FR32: Firestore rules restrict users to read/write only their own data
FR33: API routes validate authentication before processing requests
FR34: Stripe API keys are stored as environment variables (not in client bundle)

### NonFunctional Requirements

NFR1: Page Load (LCP) < 2.5s for landing and pricing pages
NFR2: Interaction (FID) < 100ms on all pages
NFR3: Visual Stability (CLS) < 0.1 on all pages
NFR4: Checkout completion < 30s end-to-end from plan selection to confirmation
NFR5: Dashboard load < 2s after authentication
NFR6: HTTPS enforced on all endpoints
NFR7: Firebase Auth managed with HttpOnly cookies
NFR8: Stripe webhook signature verification required
NFR9: API keys server-side only via environment variables
NFR10: Firestore rules restrict users to read/write only users/{uid}
NFR11: PCI compliance delegated to Stripe (no card data stored)
NFR12: Auto-logout after 7 days inactivity
NFR13: Handle Stripe API transient failures with retry (3 attempts)
NFR14: Idempotent webhook processing with 200 response within 5s
NFR15: Firebase Auth graceful fallback UI if service unavailable
NFR16: Firestore matches Stripe subscription state within 30s of webhook
NFR17: WCAG 2.1 Level A accessibility compliance

### Additional Requirements

- Starter template: `npx create-next-app@latest wardenweb --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"` (Next.js 16.1.x) — must be Epic 1, Story 1
- Component library: shadcn/ui (Radix UI primitives + Tailwind CSS)
- Data validation: Zod v3.x schemas at all data boundaries (webhooks, forms, Firestore)
- Session management: Server-side session cookies via Firebase Admin `createSessionCookie()`, HttpOnly, Secure, SameSite=Lax, 7-day expiry
- Route protection: Next.js middleware validates session cookie for /dashboard/\* routes
- Webhook idempotency: Event ID dedup in Firestore + Firestore transactions for state updates
- Code formatting: Prettier with `prettier-plugin-tailwindcss`
- Commit convention: Conventional Commits enforced via commitlint + husky
- Testing: Vitest 4.x (unit) + React Testing Library (components) + Playwright (E2E)
- CI/CD: GitHub Actions (lint, typecheck, test) + Vercel (deployment)
- Mobile-first responsive design: 320px-768px primary, progressive enhancement to desktop
- Feature-based component organization: `components/{feature}/` not flat structure
- Firestore naming: snake_case (matches Stripe), code naming: camelCase/PascalCase
- Zod `.transform()` for Firestore-to-frontend data conversion
- Environment management: `.env.local` for dev, Vercel env vars for production

### FR Coverage Map

FR1: Epic 2 - Google sign-in
FR2: Epic 2 - Email/password sign-in
FR3: Epic 2 - Sign out
FR4: Epic 2 - Account creation during checkout
FR5: Epic 1 - Landing page value proposition
FR6: Epic 1 - Navigate to pricing
FR7: Epic 1 - App download links
FR8: Epic 3 - View subscription plans
FR9: Epic 3 - Subscribe monthly via Stripe
FR10: Epic 3 - Subscribe yearly via Stripe
FR11: Epic 3 - Apply coupon during checkout
FR12: Epic 3 - See deferred billing with coupon
FR13: Epic 5 - View account email
FR14: Epic 5 - View current plan
FR15: Epic 5 - View subscription status
FR16: Epic 5 - View next payment date
FR17: Epic 5 - View payment history (via Stripe Customer Portal)
FR18: Epic 5 - Upgrade monthly to yearly (via Stripe Customer Portal)
FR19: Epic 5 - Cancel subscription (via Stripe Customer Portal)
FR20: Epic 5 - Access Stripe Customer Portal
FR21: Epic 4 - Process invoice.paid webhook
FR22: Epic 4 - Process subscription.deleted webhook
FR23: Epic 4 - Process payment_failed webhook
FR24: Epic 4 - Verify webhook signatures
FR25: Epic 5 - Display payment failure warning
FR26: Epic 6 - Privacy Policy page
FR27: Epic 6 - Terms of Service page
FR28: Epic 1 (Story 1.3) - Cookie consent banner
FR29: Epic 1 (Story 1.3) - Conditional analytics loading
FR30: Epic 6 - Account deletion via support
FR31: Epic 6 - Support cascading delete process
FR32: Epic 2 - Firestore security rules
FR33: Epic 2 - API route auth validation
FR34: Epic 2 - Env variable secret management

## Epic List

### Epic 1: Project Foundation & Landing Experience

Visitors can discover Warden's value proposition and navigate to pricing.
**FRs covered:** FR5, FR6, FR7

### Epic 2: Authentication & Identity

Users can create accounts and sign in to access protected features.
**FRs covered:** FR1, FR2, FR3, FR4, FR32, FR33, FR34

### Epic 3: Subscription & Checkout

Users can choose a plan and subscribe via Stripe, with optional coupon support.
**FRs covered:** FR8, FR9, FR10, FR11, FR12

### Epic 4: Webhook Processing & Subscription Sync

System reliably syncs Stripe payment events to Firestore, keeping subscription state accurate.
**FRs covered:** FR21, FR22, FR23, FR24

### Epic 5: Account Dashboard & Subscription Management (Portal-First)

Subscribers can view their account status and manage their subscription via Stripe's Customer Portal.
**FRs covered:** FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR25
**Approach:** Delegate subscription management (payment history, plan switching, cancellation, payment method updates) to Stripe Customer Portal. Build custom UI only for dashboard overview and payment failure warnings.

### Epic 6: Legal, Compliance & Analytics

Visitors and users have access to legal pages and privacy-compliant analytics.
**FRs covered:** FR26, FR27, FR28, FR29, FR30, FR31

### Epic 7: Launch Readiness & Production Verification

Verify the complete platform end-to-end and deploy to production.
**Scope:** Firestore security rules deployment, Firebase auth E2E verification, PlanCta hydration fix, guided payment flow E2E testing, Stripe production activation, go-live checklist.
**External dependency:** Company number required for Stripe production mode.

---

## Epic 1: Project Foundation & Landing Experience

**Goal:** Visitors can discover Warden's value proposition and navigate to pricing.
**FRs covered:** FR5, FR6, FR7

### Story 1.1: Initialize Next.js Project with Development Tooling

As a developer,
I want the project scaffolded with the chosen starter template and dev tooling configured,
So that all subsequent stories build on a consistent, properly tooled foundation.

**Acceptance Criteria:**

**Given** no existing project directory
**When** the project is initialized using `npx create-next-app@latest wardenweb --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"`
**Then** the project builds and runs locally without errors
**And** Prettier is configured with `prettier-plugin-tailwindcss` (semi: false, singleQuote: true, trailingComma: all, printWidth: 100, tabWidth: 2)
**And** commitlint + husky are configured enforcing Conventional Commits
**And** `.env.example` is created with placeholder values for all required environment variables
**And** `.gitignore` includes `.env.local`
**And** shadcn/ui is initialized with the required components (Button, Card, Input, Badge, Alert, Skeleton)

### Story 1.2: Landing Page with Value Proposition

As a visitor,
I want to see a landing page that explains the Warden app's value proposition,
So that I can understand what the app does and decide if I want to subscribe.

**Acceptance Criteria:**

**Given** a visitor navigates to `/`
**When** the landing page loads
**Then** the page displays the Warden app value proposition content
**And** the page includes app download links for iOS and Android (FR7)
**And** a visible CTA navigates the visitor to the `/pricing` page (FR6)
**And** the page is server-side rendered and cached for performance (LCP < 2.5s)
**And** the layout is mobile-first responsive (320px-768px primary, progressive enhancement to desktop)
**And** the page meets WCAG 2.1 Level A accessibility requirements

### Story 1.3: Shared Layout with Header, Footer, and Cookie Consent

As a visitor,
I want consistent navigation and legal links across all pages, and a cookie consent banner,
So that I can easily navigate the site and control my privacy preferences.

**Acceptance Criteria:**

**Given** a visitor loads any page on the site
**When** the page renders
**Then** a Header component is displayed with navigation links (home, pricing)
**And** a Footer component is displayed with links to Privacy Policy and Terms of Service pages
**And** a cookie consent banner is displayed if the visitor has not yet accepted or rejected cookies (FR28)
**When** the visitor accepts cookies
**Then** the consent preference is persisted (localStorage) and Firebase Analytics is loaded (FR29)
**When** the visitor rejects cookies
**Then** the preference is persisted and Firebase Analytics is NOT loaded
**And** the banner does not reappear on subsequent page loads

---

## Epic 2: Authentication & Identity

**Goal:** Users can create accounts and sign in to access protected features.
**FRs covered:** FR1, FR2, FR3, FR4, FR32, FR33, FR34

### Story 2.1: Firebase Auth Setup with Google Sign-In

As a user,
I want to sign in using my Google account,
So that I can quickly access protected features without creating a new password.

**Acceptance Criteria:**

**Given** the Firebase client SDK and Admin SDK are initialized (`lib/firebase/client.ts`, `lib/firebase/admin.ts`)
**When** a user clicks the Google sign-in button
**Then** Firebase `signInWithPopup()` is triggered with the Google provider (FR1)
**And** on success, the client obtains a Firebase ID token
**And** the ID token is sent to `/api/auth/session` which creates a server-side session cookie (HttpOnly, Secure, SameSite=Lax, 7-day expiry)
**And** the user is redirected to `/dashboard`
**And** `AuthContext` provides `{user, loading, error}` state to the app

### Story 2.2: Email/Password Sign-In and Registration

As a user,
I want to sign in or create an account using email and password,
So that I can access protected features without a Google account.

**Acceptance Criteria:**

**Given** a user navigates to the sign-in page
**When** the user submits valid email and password credentials
**Then** Firebase `signInWithEmailAndPassword()` authenticates the user (FR2)
**And** a session cookie is created via `/api/auth/session`
**And** the user is redirected to `/dashboard`
**When** the user does not have an account and submits registration details
**Then** a new Firebase Auth account is created (FR4)
**And** a session cookie is created and the user is redirected to `/dashboard`
**And** form validation uses React Hook Form + Zod with inline error display

### Story 2.3: Sign-Out and Session Destruction

As a user,
I want to sign out from my account,
So that my session is securely terminated.

**Acceptance Criteria:**

**Given** a signed-in user clicks the sign-out button
**When** the sign-out action is triggered
**Then** the client calls Firebase `signOut()` (FR3)
**And** a DELETE request to `/api/auth/session` destroys the server-side session cookie
**And** the `AuthContext` state is cleared
**And** the user is redirected to the landing page

### Story 2.4: Route Protection and API Auth Validation

As a system,
I want protected routes and API endpoints to require authentication,
So that unauthorized users cannot access subscriber-only features or data.

**Acceptance Criteria:**

**Given** Next.js middleware (`middleware.ts`) is configured
**When** an unauthenticated user navigates to any `/dashboard/*` route
**Then** they are redirected to the sign-in page
**When** an authenticated user navigates to `/dashboard/*`
**Then** the middleware validates the session cookie and allows access
**And** all `/api/subscription/*` routes independently validate the session cookie before processing (FR33)
**And** Firestore security rules restrict users to read/write only their own `users/{uid}` document (FR32)
**And** Stripe API keys are stored as environment variables, never exposed in client bundles (FR34)

---

## Epic 3: Subscription & Checkout

**Goal:** Users can choose a plan and subscribe via Stripe, with optional coupon support.
**FRs covered:** FR8, FR9, FR10, FR11, FR12

### Story 3.1: Pricing Page with Plan Display

As a visitor,
I want to view available subscription plans with pricing details,
So that I can compare options and decide which plan to subscribe to.

**Acceptance Criteria:**

**Given** a visitor navigates to `/pricing`
**When** the page loads
**Then** two plan options are displayed: monthly (€7.99) and yearly (€79.90) (FR8)
**And** each plan card clearly shows the price, billing period, and any savings
**And** the page is mobile-first responsive
**And** the page meets WCAG 2.1 Level A accessibility requirements

### Story 3.2: Stripe Checkout for Monthly and Yearly Subscriptions

As a user,
I want to subscribe to a monthly or yearly plan via Stripe checkout,
So that I can start using Warden's premium features.

**Acceptance Criteria:**

**Given** the Stripe client SDK (`lib/stripe/client.ts`) and server SDK (`lib/stripe/server.ts`) are initialized
**And** an authenticated user selects a plan on the pricing page
**When** the user proceeds to checkout
**Then** a Stripe Checkout Session is created server-side for the selected plan (FR9, FR10)
**And** the user is redirected to Stripe's hosted checkout page
**And** on successful payment, a `users/{uid}` Firestore document is created with subscription fields (plan, status, current_period_end)
**And** the user is redirected to `/dashboard` with a success confirmation
**And** checkout completion takes less than 30s end-to-end (NFR4)
**When** the user is not authenticated
**Then** they are prompted to sign in or create an account before checkout proceeds (FR4)

### Story 3.3: Coupon Code Support During Checkout

As a user,
I want to apply a coupon code during checkout,
So that I can receive a discount on my subscription.

**Acceptance Criteria:**

**Given** a user is on the checkout flow
**When** the user enters a valid coupon code in the coupon input field
**Then** the coupon is validated against Stripe (FR11)
**And** the updated price or discount is displayed
**And** if the coupon results in a deferred billing date, that date is shown to the user (FR12)
**When** the user enters an invalid or expired coupon code
**Then** an error message is displayed indicating the coupon is not valid
**And** the checkout can still proceed without a coupon

---

## Epic 4: Webhook Processing & Subscription Sync

**Goal:** System reliably syncs Stripe payment events to Firestore, keeping subscription state accurate.
**FRs covered:** FR21, FR22, FR23, FR24

### Story 4.1: Stripe Webhook Endpoint with Signature Verification

As a system,
I want to receive and verify Stripe webhook events,
So that only authentic Stripe events are processed and subscription state stays secure.

**Acceptance Criteria:**

**Given** the webhook endpoint exists at `/api/webhooks/stripe`
**When** Stripe sends a POST request with an event payload
**Then** the handler verifies the webhook signature using `stripe.webhooks.constructEvent()` and the webhook secret (FR24)
**And** if verification fails, the request is rejected with a 400 response
**And** if verification succeeds, the event is parsed and routed by event type
**And** processed event IDs are stored in Firestore to prevent duplicate processing (idempotency)
**And** if an event ID has already been processed, it is skipped and a 200 is returned
**And** the handler returns a 200 response within 5s (NFR14)

### Story 4.2: Process invoice.paid Webhook to Activate Subscriptions

As a system,
I want to process `invoice.paid` events from Stripe,
So that user subscriptions are activated or renewed in Firestore.

**Acceptance Criteria:**

**Given** a verified `invoice.paid` webhook event is received
**When** the event is processed
**Then** the corresponding `users/{uid}` Firestore document is updated within a Firestore transaction (FR21)
**And** the subscription fields are set: `status: "active"`, `plan`, `current_period_end`, `stripe_subscription_id`
**And** if the user document doesn't exist, it is created
**And** the Firestore state reflects the Stripe state within 30s of the webhook (NFR16)
**And** transient Stripe API failures are retried up to 3 times (NFR13)

### Story 4.3: Process subscription.deleted and payment_failed Webhooks

As a system,
I want to process `customer.subscription.deleted` and `invoice.payment_failed` events,
So that subscription cancellations and payment failures are reflected in Firestore.

**Acceptance Criteria:**

**Given** a verified `customer.subscription.deleted` webhook event is received
**When** the event is processed
**Then** the `users/{uid}` Firestore document `status` is set to `"canceled"` within a Firestore transaction (FR22)

**Given** a verified `invoice.payment_failed` webhook event is received
**When** the event is processed
**Then** the `users/{uid}` Firestore document `status` is set to `"past_due"` within a Firestore transaction (FR23)
**And** both handlers use Firestore transactions to check current state before updating (race condition protection)
**And** both return 200 to Stripe, even on permanent processing errors (log and continue)

---

## Epic 5: Account Dashboard & Subscription Management (Portal-First)

**Goal:** Subscribers can view their account status and manage their subscription via Stripe's Customer Portal.
**FRs covered:** FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR25
**Approach:** Delegate subscription management (payment history, plan switching, cancellation, payment method updates) to Stripe Customer Portal. Build custom UI only for dashboard overview and payment failure warnings.

### Story 5.1: Dashboard with Account and Subscription Overview

As a subscriber,
I want to see my account details and current subscription status on a dashboard,
So that I know what plan I'm on and when my next payment is due.

**Acceptance Criteria:**

**Given** an authenticated subscriber navigates to `/dashboard`
**When** the dashboard loads
**Then** the user's account email is displayed (FR13)
**And** the current subscription plan (monthly/yearly) is displayed (FR14)
**And** the subscription status (active, past_due, canceled) is displayed with a visual badge (FR15)
**And** the next payment date is displayed (FR16)
**And** the dashboard loads within 2s (NFR5)
**And** loading states use Skeleton components while data is fetched from Firestore
**And** data is fetched from `users/{uid}` on load (no `onSnapshot` real-time listeners)

### Story 5.2: Stripe Customer Portal Integration

As a subscriber,
I want to manage my subscription (view payment history, change plan, cancel, update payment method) via Stripe's Customer Portal,
So that I can handle all billing tasks in a secure, Stripe-hosted environment.

**Acceptance Criteria:**

**Given** an authenticated subscriber is on the `/dashboard` page
**When** the subscriber clicks the "Manage Subscription" button
**Then** a server-side API route creates a Stripe Customer Portal session via `stripe.billingPortal.sessions.create()` (FR20)
**And** the subscriber is redirected to the Stripe Customer Portal
**And** the portal provides access to payment history (FR17), plan switching with proration (FR18), subscription cancellation (FR19), and payment method updates
**And** after the subscriber returns from the portal, they land back on `/dashboard`
**And** any changes made in the portal trigger existing webhook handlers (Stories 4.2, 4.3) to update Firestore state

**Given** a signed-in user views any page
**When** the header renders
**Then** the header navigation shows a "Dashboard" link pointing to `/dashboard` (replacing the signed-out navigation links per UX spec line 715)
**And** this fulfills the deferred nav task from Story 1.3

**Human Prerequisites:**
- [ ] Stripe Customer Portal configured in Stripe Dashboard (enable plan switching, cancellation, payment method updates)
- [ ] Portal branding configured (logo, colors, return URL pointing to `/dashboard`)

### Story 5.3: Payment Failure Warning Banner

As a subscriber,
I want to be warned when my payment has failed or my subscription is canceled,
So that I can take action to resolve billing issues and maintain access.

**Acceptance Criteria:**

**Given** a subscriber's subscription status is `past_due`
**When** the dashboard loads
**Then** a prominent warning banner is displayed with the message indicating payment failure (FR25)
**And** the banner includes a CTA button pointing to the Stripe Customer Portal to update payment method

**Given** a subscriber's subscription status is `canceled`
**When** the dashboard loads
**Then** an informational banner is displayed indicating the subscription has been canceled
**And** the banner includes a CTA to resubscribe via the pricing page

**And** banners are visually distinct (warning style for `past_due`, neutral/info style for `canceled`)
**And** status is read from `users/{uid}` Firestore document (no real-time listeners)

---

## Epic 6: Legal, Compliance & Analytics

**Goal:** Visitors and users have access to legal pages and privacy-compliant analytics.
**FRs covered:** FR26, FR27, FR28, FR29, FR30, FR31

> **Note:** FR28 (cookie consent banner) and FR29 (conditional Firebase Analytics loading) are implemented in Story 1.3 (Shared Layout with Header, Footer, and Cookie Consent) as they are part of the shared layout infrastructure.

### Story 6.1: Privacy Policy and Terms of Service Pages

As a visitor,
I want to view the Privacy Policy and Terms of Service,
So that I can understand how my data is handled and what rules apply.

**Acceptance Criteria:**

**Given** a visitor navigates to `/privacy`
**When** the page loads
**Then** the Privacy Policy content is displayed (FR26)
**And** the page is statically rendered and cached for performance

**Given** a visitor navigates to `/terms`
**When** the page loads
**Then** the Terms of Service content is displayed (FR27)
**And** the page is statically rendered and cached for performance
**And** both pages are accessible from the Footer on every page

### Story 6.2: Account Deletion Process

As a user,
I want to request deletion of my account,
So that my personal data is removed in compliance with privacy regulations.

**Acceptance Criteria:**

**Given** a user wants to delete their account
**When** they navigate to account settings or the privacy policy page
**Then** instructions are displayed for requesting account deletion via support email (FR30)

**Given** support receives an account deletion request
**When** support processes the deletion
**Then** the Stripe subscription is canceled (FR31)
**And** the Firestore `users/{uid}` document is deleted (FR31)
**And** the Firebase Auth account is deleted (FR31)
**And** deletion steps are documented for the support team

---

## Epic 7: Launch Readiness & Production Verification

**Goal:** Verify the complete platform end-to-end and deploy to production.
**Scope:** Consolidates carried retro items from Epics 2–3 and adds production-readiness verification.
**External dependency:** Company number required for Stripe production mode activation.

### Story 7.1: Firestore Security Rules Deployment

As a system,
I want Firestore security rules deployed to production,
So that client SDK reads are properly restricted and users can only access their own data.

**Acceptance Criteria:**

**Given** Firestore security rules are defined for the `users/{uid}` collection
**When** the rules are deployed to the production Firebase project
**Then** authenticated users can read/write only their own `users/{uid}` document (FR32)
**And** unauthenticated requests are denied
**And** rules are tested against expected access patterns before deployment

**Origin:** Carried from Epic 2 retrospective action item #1.

### Story 7.2: Firebase Auth E2E & PlanCta Hydration Fix

As a developer,
I want to verify Firebase auth flows end-to-end and fix the PlanCta hydration mismatch,
So that sign-in/registration/sign-out work reliably and there are no console warnings in production.

**Acceptance Criteria:**

**Given** the Firebase auth integration is complete
**When** E2E verification is performed
**Then** Google sign-in, email/password sign-in, registration, and sign-out flows all work correctly across supported browsers
**And** session cookies are created and destroyed as expected
**And** the PlanCta `disabled={null}` vs `disabled={true}` hydration mismatch is fixed (no React hydration warnings in dev console)

**Origin:** Carried from Epic 2 retrospective action item #2 and Epic 3 retrospective action item #4.

### Story 7.3: Guided Payment Flow E2E Testing

As the project lead (Root),
I want to walk through the complete subscription lifecycle end-to-end,
So that I have full confidence in the payment system before going live.

**Acceptance Criteria:**

**Given** all prior epics are complete and the platform is running in Stripe test mode
**When** a guided walkthrough is performed
**Then** the following lifecycle is verified end-to-end:
- Sign up (new account creation)
- Subscribe to monthly plan via Stripe Checkout
- Verify dashboard shows active subscription with correct plan/status/next payment date
- Simulate payment failure (via Stripe test tools)
- Verify dashboard shows `past_due` warning banner
- Fix payment via Stripe Customer Portal
- Verify dashboard returns to `active` status
- Upgrade to yearly plan via Stripe Customer Portal
- Verify dashboard reflects yearly plan
- Cancel subscription via Stripe Customer Portal
- Verify dashboard shows `canceled` status and persists correctly

### Story 7.4: Stripe Production Activation & Go-Live

As the project lead (Root),
I want to activate Stripe production mode and deploy the platform,
So that real customers can subscribe and pay.

**Acceptance Criteria:**

**Given** all E2E testing is complete and the company number is available
**When** production activation is performed
**Then** Stripe account is activated for production mode with the company number
**And** production environment variables are configured (Stripe live keys, webhook secret)
**And** DNS is configured for the production domain
**And** Vercel production deployment is verified
**And** a go-live checklist is completed covering: security review, environment variables, monitoring, webhook endpoint verification, SSL/HTTPS

**External dependency:** Root must provide company number before this story can begin.
