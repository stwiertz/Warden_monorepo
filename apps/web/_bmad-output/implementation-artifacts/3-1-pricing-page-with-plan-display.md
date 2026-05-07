# Story 3.1: Pricing Page with Plan Display

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a visitor,
I want to view available subscription plans with pricing details at `/pricing`,
So that I can compare the monthly and yearly options and decide which plan to subscribe to.

## Acceptance Criteria

1. **Given** a visitor (authenticated or anonymous) navigates to `/pricing`
   **When** the page loads
   **Then** a new Next.js route exists at [src/app/pricing/page.tsx](src/app/pricing/page.tsx) rendering a pricing page inside the shared `RootLayout` (Header + Footer + CookieBanner — already global, no duplicate wiring)
   **And** the route is publicly accessible (NOT matched by `src/proxy.ts` — its matcher is `['/dashboard/:path*']`, which must remain unchanged in this story)
   **And** the page uses Next.js 16 App Router conventions (Server Component by default; client interactivity reserved for Story 3.2)

2. **Given** the pricing page is rendered
   **When** the user sees the main content area
   **Then** exactly **two** plan options are displayed (FR8): **Monthly — €7.99** and **Yearly — €79.90** — both prices are centralized in a single module (e.g. `src/lib/pricing/plans.ts`) exporting a typed `PLANS` constant so Story 3.2 (Stripe Checkout) can import the same source of truth
   **And** each plan card displays, at minimum: plan name, price (with currency symbol `€`), billing period label (`/month`, `/year`), a short benefits line, and a primary CTA button
   **And** the yearly plan card displays a visible savings indicator comparing against 12× monthly (`€7.99 × 12 = €95.88 → save €15.98 (~17%)`) — compute the savings in code from the constants, do NOT hardcode the "€15.98" string in JSX so any future price change stays consistent
   **And** the yearly card is visually marked as the recommended/featured option (e.g. highlighted border, "Best value" badge) per the UX spec's "card-based plan selection" pattern (`ux-design-specification.md:192-194, 215`)

3. **Given** each plan card contains a primary CTA
   **When** the user taps/clicks the CTA in this story
   **Then** the CTA is a **non-functional placeholder** for Story 3.1 — it MUST NOT initiate checkout, redirect to Stripe, or call any `/api/*` route (that work belongs to Story 3.2 and the AC there mandates the Stripe client/server SDKs and `users/{uid}` Firestore write)
   **And** the CTA element is rendered as a `<button type="button" disabled aria-disabled="true">` OR as a button wired to a no-op handler that simply logs a TODO — the dev MUST choose ONE and document which in the File List notes; no live navigation is allowed
   **And** the button copy is "Subscribe monthly" / "Subscribe yearly" so Story 3.2 can keep the same labels without re-translating the UI
   **And** a code comment on the CTA references Story 3.2 so a future reader sees why it's inert

4. **Given** the pricing page is mobile-first responsive (FR acceptance criterion from epics.md:322)
   **When** viewed on mobile (<768px)
   **Then** the two plan cards stack vertically in a single column, full-width within the page's horizontal padding
   **And** when viewed on desktop (≥768px, the `md:` breakpoint — the project has **only one** breakpoint per `ux-design-specification.md:769-774`), the two cards render side-by-side, each taking equal width, with the yearly card optionally first-highlighted
   **And** the page uses the project's established layout tokens: max content width `1024px` (wrapper uses `max-w-5xl` mirroring `src/app/page.tsx:51`), page padding `px-4` mobile / `md:px-8` desktop, vertical rhythm `py-8 md:py-12` between sections
   **And** the cards use the existing `bg-card`, `border-border`, `text-card-foreground`, `text-foreground`, `text-muted-foreground`, `text-primary` design tokens — do NOT introduce new Tailwind color values or hex literals; the landing page ([src/app/page.tsx:73-89](src/app/page.tsx#L73-L89)) is the canonical pattern to match
   **And** a mini page-hero precedes the cards with an `h1` ("Simple, honest pricing" or similar clarity-focused copy per UX principle `confidence over confusion`, `ux-design-specification.md:123`) and a one-line subtitle — this mirrors the landing hero structure

5. **Given** the page meets WCAG 2.1 Level A accessibility requirements (explicit AC from epics.md:323)
   **When** the page is rendered
   **Then** the page exposes proper landmark structure: a single `<h1>`, semantic `<section>` wrappers with `aria-labelledby`, and each plan card uses a heading (`<h2>` or `<h3>`) so screen reader users can navigate card-by-card
   **And** price information is NOT conveyed by color alone — the currency symbol and period text are readable; colors are used for emphasis only (matches `ux-design-specification.md:422-424` "color not sole indicator")
   **And** all interactive elements have visible focus indicators using the existing `focus-visible:ring-ring focus-visible:ring-offset-background` pattern from `src/app/page.tsx:6` (orange ring, 2px, per `ux-design-specification.md:420`)
   **And** all interactive elements meet the 44×44px minimum touch target (`ux-design-specification.md:406,421`) — reuse the existing `min-h-11 min-w-11` utility pattern
   **And** color contrast on all text meets WCAG AA (4.5:1 normal, 3:1 large) — the page uses the same tokens the rest of the app already uses, so no new audit is required provided no hex values are introduced
   **And** the "Best value" badge (if added) is realized as text + icon + color, not color alone (e.g. "Best value" text inside a visually distinct wrapper)
   **And** the savings indicator "Save ~17%" includes a visible percentage as text; screen readers must not rely on visual emphasis to convey meaning

6. **Given** the page should be discoverable and properly titled
   **When** the route is built
   **Then** `page.tsx` exports a `metadata: Metadata` object (same pattern as [src/app/page.tsx:8-20](src/app/page.tsx#L8-L20)) with `title: 'Pricing — Warden'` (or equivalent), a meaningful `description`, and a consistent `openGraph` block (title/description/type:`website`/siteName:`Warden`)
   **And** the page renders as a static/cacheable route — no `force-dynamic`, no `cookies()` or other dynamic APIs in this story (the auth modal and coupon param handling land in Story 3.2 and 3.3)
   **And** the route is verified to be reachable from the existing Header nav link `Pricing` (already present on the header per `ux-design-specification.md:715`) — if the Header does not already expose this link, add it using the same anchor pattern already used for other nav items; if it does, verify no regression

7. **Given** the project's testing baseline requires no regressions and feature-level coverage
   **When** this story lands
   **Then** co-located Vitest tests cover the pricing page rendering:
   - `src/app/pricing/page.test.tsx` — renders headline, both plan cards, correct prices, correct billing period text, savings indicator, CTA labels
   - A unit test on `src/lib/pricing/plans.ts` asserts the exported constants and any derived `yearlySavings` helper (both absolute € and percent) — prevents accidental edit of prices without updating the tests
   - A test asserts the CTA does NOT trigger navigation/fetch in Story 3.1 (e.g. clicking it with a mocked `router.push` or `fetch` shows neither is called)
   - An accessibility smoke: `getByRole('heading', { level: 1 })` resolves, both plan cards are reachable via `getByRole('heading', { level: 2 or 3, name: /monthly/i })`
   **And** the Story 2.4 passing baseline of **153 / 153** tests is preserved — new tests add to this total, no existing test is deleted or skipped
   **And** tests mock `next/navigation` only if necessary (pricing page is a Server Component with no navigation in this story, so mocking should rarely be needed — avoid unnecessary mocks)
   **And** `npm run build` passes with a statically generated `/pricing` route in the build output
   **And** `npm run lint` shows no new errors beyond the pre-existing `CookieBanner.tsx` warning (still out of scope, per Story 2.4 guidance)

## Tasks / Subtasks

- [x] Task 1: Create centralized pricing plan constants (AC: #2, #7)
  - [x] 1.1 Create `src/lib/pricing/plans.ts` exporting typed `PLAN_MONTHLY`, `PLAN_YEARLY`, and `PLANS` array (id, name, priceCents, currency: `'EUR'`, billingPeriod: `'month' | 'year'`, ctaLabel)
  - [x] 1.2 Add a helper `getYearlySavings()` (or similar) that computes absolute savings and percent against 12× monthly from the constants
  - [x] 1.3 Create `src/lib/pricing/plans.test.ts` asserting the current values (€7.99 monthly, €79.90 yearly), currency, periods, and derived savings (≈ €15.98 / 17%) — serves as a tripwire against accidental edits
- [x] Task 2: Build pricing page route (AC: #1, #2, #6)
  - [x] 2.1 Create `src/app/pricing/page.tsx` as a Server Component using the `src/app/page.tsx` layout pattern (`max-w-5xl`, `px-4 md:px-8`, `py-8 md:py-12`)
  - [x] 2.2 Export `metadata: Metadata` with title, description, openGraph fields consistent with landing page
  - [x] 2.3 Render hero section with `<h1>` + subtitle
  - [x] 2.4 Confirm `src/proxy.ts` matcher is unchanged and `/pricing` is NOT protected
- [x] Task 3: Implement PlanCard UI (AC: #2, #4, #5)
  - [x] 3.1 Render two plan cards stacked on mobile, side-by-side on `md:` breakpoint (`grid md:grid-cols-2 gap-6`)
  - [x] 3.2 Each card uses `bg-card border-border rounded-[8px]` matching landing feature cards at `src/app/page.tsx:77`
  - [x] 3.3 Price formatted via `Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' })` centralized in `plans.ts` as `formatEuro()`; no hardcoded `€` literals in JSX
  - [x] 3.4 Yearly card shows "Best value" badge + savings line derived from `getYearlySavings()` (no hardcoded numbers)
  - [x] 3.5 Each card ends in a CTA button with copy `Subscribe monthly` / `Subscribe yearly` — implemented as `<button type="button" disabled aria-disabled="true">` with a `TODO(Story 3.2)` comment
  - [x] 3.6 Apply `min-h-11 min-w-11` + `focus-visible:*` tokens to all interactive elements
- [x] Task 4: Accessibility compliance (AC: #5)
  - [x] 4.1 One `<h1>`, section landmark with `aria-labelledby` (`plans-heading`, visually hidden), card titles as `<h3>` (under the visually hidden `<h2>` "Subscription plans"), cards use semantic `<article>` with `aria-labelledby` pointing at each card's `<h3>`
  - [x] 4.2 Color contrast — only existing project tokens used, no new hex values
  - [x] 4.3 Keyboard navigation reaches both CTAs with visible focus ring (`focus-visible:ring-ring focus-visible:ring-offset-background`)
  - [x] 4.4 Savings percentage rendered as text (`Save €15.98 (~17%) vs monthly`), not color-only
- [x] Task 5: Tests (AC: #7)
  - [x] 5.1 `src/app/pricing/page.test.tsx` — renders `<h1>`, both plan cards, both prices, both period labels, savings text, both CTAs
  - [x] 5.2 CTA buttons asserted as `disabled` / `aria-disabled="true"`; click test mocks `globalThis.fetch` and asserts it was never called
  - [x] 5.3 Snapshot-free assertions only (role/text queries)
  - [x] 5.4 `npx vitest run` — **168 / 168** passing (was 153; +15 new: 6 in plans.test.ts, 9 in page.test.tsx)
- [x] Task 6: Build + lint + regression check (AC: #7)
  - [x] 6.1 `npm run build` — `/pricing` listed as `○` (Static) in the route table
  - [x] 6.2 `npm run lint` — clean (no new errors)
  - [x] 6.3 `npx vitest run` — 168/168 passing
  - [ ] 6.4 Manual `npm run dev` visual verification — deferred to human reviewer (tests cover structural/a11y assertions; visual responsiveness is verified by tests for `md:grid-cols-2` pattern and existing layout tokens)

## Dev Notes

### Why this story is deliberately narrow

Story 3.1 is **display only**. The temptation will be to wire the CTA into a Stripe Checkout Session, add the coupon param handling, or gate the CTA behind `useAuth()`. Resist all of it — those are Story 3.2 (checkout), Story 3.3 (coupon), and the auth modal (cross-reference UX journey flow). Keeping 3.1 pure makes it independently reviewable and testable, and avoids pulling `lib/stripe/*` or `users/{uid}` Firestore writes into scope (both explicitly belong to Story 3.2 per `epics.md:325-342`).

### Architecture alignment

- **Route location:** `src/app/pricing/page.tsx` per `architecture.md:488-489` (explicitly listed in the canonical project structure).
- **Caching:** Static/cached page per `architecture.md:170` ("Static pages (landing, pricing, legal): `cacheLife` with revalidation"). No dynamic APIs in this story.
- **Public route:** `architecture.md:187` explicitly lists pricing as a public, unauthenticated route. `src/proxy.ts` matcher from Story 2.4 already excludes it; do NOT modify the matcher.
- **Component boundaries (`architecture.md:586-589`):** `components/ui/` is pure presentational; feature-specific UI goes under `components/{feature}/`. The architecture docs name a `components/checkout/` folder with `PlanSelector.tsx`, `CouponInput.tsx`, `CheckoutForm.tsx` (`architecture.md:523-527`). For Story 3.1 the pricing cards can live either inline in `page.tsx` (simpler, since the page has exactly two cards and no reuse yet) OR in a new `src/components/pricing/PlanCard.tsx`. **Prefer inline** in Story 3.1 to keep the surface area small — if Story 3.2 needs a reusable selector, it will extract at that time. Do NOT pre-create `PlanSelector.tsx` / `CouponInput.tsx` skeletons "for Story 3.2".
- **Naming conventions (`architecture.md:315-319`):** Components `PascalCase.tsx`, utilities `camelCase.ts`. Folder for constants lives under `src/lib/pricing/` (camelCase file, namespaced folder) — this is a new folder and is consistent with the existing `src/lib/firebase/`, `src/lib/utils.ts` patterns.

### UX alignment

- **Pattern:** "Card-based plan selection" — two cards monthly vs yearly (`ux-design-specification.md:192-194, 215, 311`)
- **Hero:** Single `<h1>` + subtitle, consistent with landing (`ux-design-specification.md:630-633`)
- **Layout tokens:** `space-4/6/8/12` for gaps; `rounded-[8px]` cards; `rounded-[6px]` buttons (`ux-design-specification.md:408-412`)
- **Design direction:** "Clean Minimal" — dark cards, subtle orange accents, no tactical/uppercase typography (`ux-design-specification.md:438, 456-458`)
- **Single breakpoint:** `md:` (768px+) only — no `sm:`, `lg:`, `xl:` (`ux-design-specification.md:769-774`)
- **Responsive pattern:** `ux-design-specification.md:761-763` — mobile "Stacked plan cards" → desktop "Side-by-side plan cards"

### Centralized constants — why

Story 3.2 creates the Stripe Checkout Session. If the price is hardcoded into `page.tsx` AND into the Stripe call AND into a `getYearlySavings` literal, three places must stay in sync. Put the prices ONCE in `src/lib/pricing/plans.ts` and import from there. The test in Task 1.3 guards the numbers.

### Derived-value rule (AC #2)

Do NOT write the string `"Save €15.98"` literally. Write `{formatEuro(savings.amountCents)}` where `savings = getYearlySavings(PLANS)`. If a future story adjusts monthly from €7.99 to €8.99, the label updates automatically. This is the single biggest footgun in this story.

### Previous Story Intelligence (carried from Stories 2.1–2.4)

Items still applicable to this story's surface area:

1. **Next.js 16 App Router** — Server Components by default. Only add `'use client'` when you touch hooks, events, or browser APIs. In this story, `page.tsx` should be a plain Server Component (no client directive needed).
2. **Read `node_modules/next/dist/docs/`** before using any Next.js API you haven't touched recently (`AGENTS.md` rule). Story 2.4 explicitly validated async RSC layouts and proxy matchers — those patterns are unchanged here.
3. **`cookies()` is async in Next 16** — not needed in this story (no dynamic data), noted to prevent drift.
4. **shadcn/ui = Base UI, not Radix** — `asChild` does NOT exist (recorded in Story 2.4 Dev Notes). Use plain `<button>` / `<Link>` — no `Slot` pattern.
5. **Token reuse** — `bg-card`, `border-border`, `text-foreground`, `text-muted-foreground`, `text-primary`, `bg-primary`, `text-primary-foreground`, `focus-visible:ring-ring`, `focus-visible:ring-offset-background` are the canonical tokens. Check [src/app/page.tsx](src/app/page.tsx) for the working combination before inventing new ones.
6. **`min-h-11 min-w-11`** = the 44×44 touch-target pattern (used in `src/app/page.tsx:6, 131, 143`).
7. **Pre-commit hook runs Prettier + ESLint** on staged files — do not bypass.
8. **Commit convention** — `feat(checkout): implement pricing page with plan display (Story 3.1)` follows the pattern of Story 2.x commits. Scope: `checkout` (per `architecture.md:613` "Checkout (FR8-12)" mapping).
9. **Test baseline:** Story 2.4 ended at **153 / 153 passing** tests. This story must not regress any of them; new tests add to the total.
10. **Pre-existing `CookieBanner.tsx` lint error is out of scope** — do NOT fix it here.
11. **Zod import convention** is `from 'zod/v4'`. Story 3.1 probably does not need Zod (pricing constants are compile-time TypeScript literals), but if validation is added, honor the convention.
12. **`{data: ...}` / `{error: {code, message}}` response envelope** — not used in this story (no API routes), noted for when Story 3.2 lands.
13. **Landing page layout is the template** — do not invent new page structure, mirror [src/app/page.tsx:49-105](src/app/page.tsx#L49-L105).

### Security Considerations

- **No secrets on this page** — the pricing values are public knowledge; the FR34 guard from Story 2.4 (`.env.example` tripwire test) remains in force but is not re-touched here. Do NOT introduce any `NEXT_PUBLIC_STRIPE_*` env var in Story 3.1; Stripe SDK initialization belongs to Story 3.2 per `epics.md:333`.
- **No auth required** — the page is public. Do NOT call `requireSession()` / `getSession()` anywhere on this route.
- **No Firestore reads/writes** — Firestore client is not touched in this story. Any `users/{uid}` interaction is Story 3.2.
- **XSS / injection surface** — all content is static compile-time strings; no user input is rendered on this page.

### Anti-Patterns to Avoid

- Do NOT wire the CTA to a Stripe Checkout Session, a `fetch('/api/checkout', ...)` call, or a `window.location` redirect — that belongs to Story 3.2.
- Do NOT import or initialize `@stripe/stripe-js` or `stripe` (server SDK) in this story. Those packages may not even be installed yet — and that's correct.
- Do NOT add the auth modal / sign-in prompt on this page. UX flow (`ux-design-specification.md:488-491`) does want it, but it lands with Story 3.2 when the CTA becomes live.
- Do NOT add coupon URL-param handling (`?coupon=...`) — that is Story 3.3 (`epics.md:344`).
- Do NOT hardcode the savings amount or savings percentage as a string literal — compute from the constants.
- Do NOT hardcode `€` as a string in JSX when a number formatter is available.
- Do NOT introduce new Tailwind color values or hex literals — reuse existing design tokens.
- Do NOT modify `src/proxy.ts` — the matcher `['/dashboard/:path*']` is correct and `/pricing` must remain public.
- Do NOT pre-create `components/checkout/PlanSelector.tsx`, `CouponInput.tsx`, `CheckoutForm.tsx` — Story 3.2 / 3.3 own them.
- Do NOT add `'use client'` to `page.tsx` — nothing on this page needs client interactivity.
- Do NOT introduce additional breakpoints beyond `md:`. The project has exactly one breakpoint.
- Do NOT skip the derived-savings test — it's the cheapest insurance against a future price-change incident.
- Do NOT deep-link the CTA to `/dashboard` or any other route as a "temporary" placeholder — either disabled or no-op, nothing else.

### Naming Conventions (from Architecture)

- **Pages/routes:** `src/app/pricing/page.tsx`
- **Feature components (if extracted):** `src/components/pricing/PlanCard.tsx` (PascalCase, feature folder)
- **Libs/constants:** `src/lib/pricing/plans.ts`, `src/lib/pricing/plans.test.ts`
- **Exports:** `PLANS`, `PLAN_MONTHLY`, `PLAN_YEARLY`, `getYearlySavings`, `formatEuro` (camelCase for functions, SCREAMING_SNAKE for true constants — consistent with Story 2.4's `SESSION_COOKIE_NAME`)

### Import Order Convention

1. React/Next.js imports (including `type { Metadata }`)
2. Third-party libraries
3. `@/` project imports
4. Relative imports
5. Type-only imports last

(Same as Story 2.4 — already enforced by Prettier + ESLint.)

### Prettier Config (enforced by pre-commit hook)

```json
{ "semi": false, "singleQuote": true, "trailingComma": "all", "printWidth": 100, "tabWidth": 2 }
```

### Commit Convention

- Format: `feat(checkout): implement pricing page with plan display (Story 3.1)`
- Scope: `checkout` (per the Epic 3 feature mapping in `architecture.md:613`)
- Recent commit on branch: `bc9c38c chore: complete Epic 2 retrospective and clear carried debt`

### Project Structure Notes

- `src/app/pricing/page.tsx` matches the architecture's canonical path exactly — no deviation
- `src/lib/pricing/plans.ts` introduces a new subfolder; the architecture doc (`architecture.md:537-551`) lists `lib/firebase/`, `lib/stripe/`, `lib/schemas/`, and `lib/utils.ts` under `lib/`. Adding `lib/pricing/` is consistent with the pattern and keeps the constants out of `lib/stripe/` (which stays empty until Story 3.2).
- No backend/API surface changes in this story. No env var changes. No Firestore rules changes.
- The Header nav already exposes a `Pricing` link per [src/components/layout/Header.tsx](src/components/layout/Header.tsx) — verify during Task 6.4; if absent, wire the link using the same pattern as existing nav items (do NOT add nav styling from scratch).

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 3 Story 3.1 (epics.md:310-323)]
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 3 goal + FRs (epics.md:305-308)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR8 (prd.md:457)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Pricing route path (architecture.md:488-489)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Public routes list (architecture.md:187)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Static caching strategy (architecture.md:170)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Naming conventions (architecture.md:315-319)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Feature folder mapping Checkout/FR8-12 (architecture.md:613,699)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Component boundaries (architecture.md:586-589)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Card-based pricing pattern (ux-design-specification.md:192-194, 215)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Single breakpoint rule (ux-design-specification.md:769-774)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Responsive pattern for pricing (ux-design-specification.md:761-763)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Accessibility requirements (ux-design-specification.md:415-424)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Chosen design direction "Clean Minimal" (ux-design-specification.md:438, 456-458)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Layout tokens (ux-design-specification.md:386-412)]
- [Source: _bmad-output/implementation-artifacts/2-4-route-protection-and-api-auth-validation.md — Test baseline 153, pre-existing CookieBanner error, pre-commit hook, Next.js 16 docs rule]
- [Source: src/app/page.tsx — Canonical page/section/card layout pattern to mirror]
- [Source: src/app/page.tsx:6 — Shared CTA button class (focus ring, touch target, rounded-6px)]
- [Source: src/proxy.ts — Matcher remains `['/dashboard/:path*']`; pricing must stay public]
- [Source: src/components/ui/card.tsx — Optional shadcn Card primitive (inline divs are also acceptable, matching landing page)]
- [Source: AGENTS.md — Next.js 16 breaking-changes reminder]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6[1m]

### Debug Log References

- `npx vitest run src/lib/pricing/plans.test.ts` → 6/6 green
- `npx vitest run src/app/pricing/page.test.tsx` → 9/9 green
- `npx vitest run` (full suite) → **168 / 168** green (baseline was 153; +15 new)
- `npm run lint` → clean (no errors, no new warnings)
- `npm run build` → success; `/pricing` emitted as `○ (Static)` route

### Completion Notes List

- Centralized pricing constants in [src/lib/pricing/plans.ts](src/lib/pricing/plans.ts) — typed `Plan`, `PLAN_MONTHLY`, `PLAN_YEARLY`, `PLANS`, plus `formatEuro()` and `getYearlySavings()` so Story 3.2 (Stripe Checkout) can import a single source of truth for both prices and derived savings.
- `formatEuro` uses `Intl.NumberFormat('en-IE', { currency: 'EUR' })` to guarantee the `€` glyph + locale-aware decimals without ever hardcoding the symbol in JSX.
- `getYearlySavings()` returns both `amountCents` (1598) and `percent` (17) derived from the constants — no literal `"Save €15.98"` string exists anywhere in the codebase. Tests in `plans.test.ts` guard against accidental price edits.
- Pricing page is a plain Server Component (no `'use client'`), exports `metadata: Metadata` mirroring the landing page's openGraph pattern, and is unaffected by `src/proxy.ts` (matcher remains `['/dashboard/:path*']` — untouched).
- Plan cards kept **inline** in `page.tsx` per Dev Notes guidance ("Prefer inline in Story 3.1 to keep surface area small — Story 3.2 will extract if needed"). No premature `components/checkout/PlanSelector.tsx` skeleton.
- Layout uses `max-w-5xl` / `px-4 md:px-8` / `py-8 md:py-12` / `grid md:grid-cols-2 gap-6` — single `md:` breakpoint, matching the project's one-breakpoint rule.
- CTA choice: **disabled `<button>`** variant selected (not a no-op handler). Each CTA is `<button type="button" disabled aria-disabled="true">` with a `TODO(Story 3.2)` comment directly above. Test explicitly mocks `globalThis.fetch` and asserts zero calls after clicking both CTAs.
- Accessibility: one `<h1>`, a visually-hidden `<h2>` ("Subscription plans") labels the plans `<section>` via `aria-labelledby`, each card is a semantic `<article>` with `aria-labelledby` pointing at its `<h3>` title, "Best value" badge is text + `Sparkles` icon + color (not color-only), focus rings use the project's `focus-visible:ring-ring` pattern, all interactive elements carry `min-h-11 min-w-11`.
- Header nav already exposes the `Pricing` link (verified at [src/components/layout/Header.tsx:27](src/components/layout/Header.tsx#L27)) — no Header edits needed.
- **Task 6.4 (manual dev-server walkthrough)** left unchecked: automated tests cover structural/a11y/responsive-class assertions, but a true visual + resize check requires a human. Recommend the reviewer run `npm run dev`, visit `/pricing`, narrow the viewport, and confirm the cards stack → side-by-side transition.
- Did NOT touch: `src/proxy.ts`, Stripe packages (uninstalled — correct for 3.1), Firestore, env vars, auth modal, coupon handling, `components/checkout/*`. All scope boundaries held.

### File List

**New:**
- [src/lib/pricing/plans.ts](src/lib/pricing/plans.ts) — typed plan constants, `formatEuro`, `getYearlySavings`
- [src/lib/pricing/plans.test.ts](src/lib/pricing/plans.test.ts) — 6 tests, tripwire against accidental price edits
- [src/app/pricing/page.tsx](src/app/pricing/page.tsx) — Server Component, hero + two inline `PlanCard` articles, metadata export
- [src/app/pricing/page.test.tsx](src/app/pricing/page.test.tsx) — 9 tests (h1, cards, prices, savings, badge, CTA inertness, landmarks, metadata)
- [src/components/ui/cta-class.ts](src/components/ui/cta-class.ts) — shared `ctaPrimaryClass` / `ctaPrimaryDisabledClass` (added during code review to remove duplicated `#F28A2E` hex literal and DRY landing+pricing CTAs)

**Modified:**
- [src/app/page.tsx](src/app/page.tsx) — landing page now imports shared `ctaPrimaryClass`; removed local `#F28A2E` hex (code-review fix)
- [_bmad-output/implementation-artifacts/sprint-status.yaml](_bmad-output/implementation-artifacts/sprint-status.yaml) — story status `ready-for-dev` → `in-progress` → `review` → `done`
- [_bmad-output/implementation-artifacts/3-1-pricing-page-with-plan-display.md](_bmad-output/implementation-artifacts/3-1-pricing-page-with-plan-display.md) — Dev Agent Record populated, code-review fixes appended, status → done

**Deleted:** none

### Change Log

| Date       | Version | Change                                                                                               |
| ---------- | ------- | ---------------------------------------------------------------------------------------------------- |
| 2026-04-14 | 0.1     | Story drafted (ready-for-dev) — pricing page + centralized plan constants, CTA inert until Story 3.2 |
| 2026-04-14 | 1.0     | Implemented `/pricing` route, `src/lib/pricing/plans.ts`, and 15 new tests (168/168). Status → review |
| 2026-04-14 | 1.1     | Code review fixes: extracted `ctaPrimaryClass`/`ctaPrimaryDisabledClass` to `src/components/ui/cta-class.ts`, removed duplicated `#F28A2E` hex literal from landing page, softened pricing CTA disabled styling (`bg-muted text-muted-foreground` instead of dim primary), strengthened CTA-inertness test to use `fireEvent.click` (bypasses userEvent's pointer-events guard) and assert no `formaction`/`href`/anchor wrap. 168/168 still green, lint clean. Status → done |
