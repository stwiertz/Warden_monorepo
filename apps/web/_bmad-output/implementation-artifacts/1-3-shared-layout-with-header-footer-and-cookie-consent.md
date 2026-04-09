# Story 1.3: Shared Layout with Header, Footer, and Cookie Consent

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a visitor,
I want consistent navigation and legal links across all pages, and a cookie consent banner,
So that I can easily navigate the site and control my privacy preferences.

## Acceptance Criteria

1. **Given** a visitor loads any page on the site
   **When** the page renders
   **Then** a Header component is displayed with navigation links (home, pricing)
   **And** a Footer component is displayed with links to Privacy Policy and Terms of Service pages

2. **Given** a visitor loads any page on the site
   **When** the page renders and the visitor has not yet accepted or rejected cookies
   **Then** a cookie consent banner is displayed (FR28)

3. **Given** the visitor clicks "Accept" on the cookie consent banner
   **When** the consent preference is saved
   **Then** the preference is persisted to `localStorage` and Firebase Analytics is loaded (FR29)

4. **Given** the visitor clicks "Reject" on the cookie consent banner
   **When** the consent preference is saved
   **Then** the preference is persisted to `localStorage` and Firebase Analytics is NOT loaded

5. **Given** the visitor has previously accepted or rejected cookies
   **When** the visitor loads any page
   **Then** the cookie consent banner does not reappear

6. **Given** the Header is rendered
   **Then** the navigation links are keyboard-accessible with visible focus indicators (WCAG 2.1 Level A, NFR17)

7. **Given** the layout is loaded on a mobile device (320px-768px)
   **Then** the Header and Footer are mobile-first responsive with progressive enhancement to desktop

## Tasks / Subtasks

- [x] Task 1: Create Header component (AC: #1, #6, #7)
  - [x] 1.1 Create `src/components/layout/Header.tsx` as a Server Component
  - [x] 1.2 Add navigation links: Home (`/`) and Pricing (`/pricing`) using `<Link>` from `next/link`
  - [x] 1.3 Add Warden logo/brand name as link to home
  - [x] 1.4 Style with Tailwind utilities, mobile-first responsive
  - [x] 1.5 Use semantic `<header>` and `<nav>` HTML elements
  - [x] 1.6 Ensure keyboard accessibility with visible focus indicators

- [x] Task 2: Create Footer component (AC: #1, #7)
  - [x] 2.1 Create `src/components/layout/Footer.tsx` as a Server Component
  - [x] 2.2 Add links to Privacy Policy (`/privacy`) and Terms of Service (`/terms`) pages
  - [x] 2.3 Add copyright notice
  - [x] 2.4 Style with Tailwind utilities, mobile-first responsive
  - [x] 2.5 Use semantic `<footer>` HTML element

- [x] Task 3: Create CookieBanner component (AC: #2, #3, #4, #5)
  - [x] 3.1 Create `src/components/layout/CookieBanner.tsx` as a Client Component (`'use client'`)
  - [x] 3.2 Check `localStorage` for existing cookie consent preference on mount
  - [x] 3.3 Show banner only if no preference is stored
  - [x] 3.4 Implement "Accept" button that saves `cookie-consent: accepted` to `localStorage`
  - [x] 3.5 Implement "Reject" button that saves `cookie-consent: rejected` to `localStorage`
  - [x] 3.6 On Accept: dynamically load Firebase Analytics (see Task 4)
  - [x] 3.7 Hide banner after user makes a choice (state-driven, no page reload)
  - [x] 3.8 Style as fixed bottom banner, mobile-first responsive

- [x] Task 4: Implement conditional Firebase Analytics loading (AC: #3, #4, #5)
  - [x] 4.1 Create `src/lib/firebase/analytics.ts` with a function to initialize Firebase Analytics
  - [x] 4.2 Use `next/script` with `afterInteractive` strategy OR dynamic import to load analytics conditionally
  - [x] 4.3 On page load: if `localStorage` has `cookie-consent: accepted`, load analytics immediately
  - [x] 4.4 On Accept click: load analytics dynamically
  - [x] 4.5 Never load analytics if consent is `rejected` or not yet given

- [x] Task 5: Integrate Header, Footer, and CookieBanner into root layout (AC: #1, #2)
  - [x] 5.1 Modify `src/app/layout.tsx` to include `<Header />`, `<Footer />`, and `<CookieBanner />`
  - [x] 5.2 Structure: Header above `{children}`, Footer below, CookieBanner as fixed overlay
  - [x] 5.3 Ensure `{children}` area uses `flex-grow` to push Footer to bottom (already has `flex min-h-full flex-col` on body)
  - [x] 5.4 Keep root layout as Server Component — only CookieBanner is a Client Component

- [x] Task 6: Accessibility and responsive testing (AC: #6, #7)
  - [x] 6.1 Verify all navigation links are keyboard-focusable with visible focus rings
  - [x] 6.2 Verify semantic HTML: `<header>`, `<nav>`, `<main>`, `<footer>`
  - [x] 6.3 Verify sufficient color contrast for all text (WCAG AA minimum)
  - [x] 6.4 Test layout at 320px, 768px, and 1024px+ breakpoints
  - [x] 6.5 Verify CookieBanner does not obscure critical content on mobile

## Dev Notes

### Architecture Compliance

- **Component locations:** `src/components/layout/Header.tsx`, `src/components/layout/Footer.tsx`, `src/components/layout/CookieBanner.tsx` — per architecture spec feature-based organization.
- **Server vs Client Components:** Header and Footer are Server Components (no interactivity). CookieBanner MUST be a Client Component (`'use client'`) because it uses `localStorage` and `useState`.
- **Root layout:** `src/app/layout.tsx` remains a Server Component. Importing a Client Component into a Server Component is fine — the Server Component itself does not become a Client Component.
- **Navigation:** Use `<Link>` from `next/link` for all internal navigation links (enables client-side navigation with prefetching).

### Technical Stack (from Architecture)

- **Next.js 16.2.2** with App Router, `src/` directory, `@/*` import alias
- **React 19.2.4** — Server Components by default
- **Tailwind CSS 4** via `@tailwindcss/postcss` (no `tailwind.config.ts` — config is in `globals.css` using `@theme inline`)
- **shadcn/ui 4.1.2** — uses Base UI (not Radix UI) as primitive layer. Available components: `Button`, `Card`, `Input`, `Badge`, `Alert`, `Skeleton`, `Dialog`
- **Lucide React** for icons (already installed)
- **Geist font family** (sans + mono) already configured in root layout

### File Structure

```
src/components/layout/Header.tsx     -- CREATE: Navigation header
src/components/layout/Footer.tsx     -- CREATE: Footer with legal links
src/components/layout/CookieBanner.tsx -- CREATE: GDPR cookie consent banner
src/lib/firebase/analytics.ts        -- CREATE: Conditional analytics loading
src/app/layout.tsx                   -- MODIFY: Add Header, Footer, CookieBanner
```

### Cookie Consent Implementation Pattern

The cookie consent banner uses `localStorage` (not HTTP cookies) for storing the user's preference. This is appropriate because:
- The preference only controls client-side behavior (loading Firebase Analytics)
- No server-side processing depends on this preference
- `localStorage` persists across sessions without expiry concerns

**Implementation flow:**
1. `CookieBanner` checks `localStorage.getItem('cookie-consent')` on mount
2. If `null` (no preference) → show banner
3. If `'accepted'` → hide banner, load Firebase Analytics
4. If `'rejected'` → hide banner, do NOT load analytics
5. Accept/Reject buttons set `localStorage` and update component state

**Firebase Analytics conditional loading:**
- Create a `loadAnalytics()` function in `src/lib/firebase/analytics.ts`
- This function dynamically imports Firebase Analytics and initializes it
- Call this function from CookieBanner on accept, and from a useEffect on page load if consent was previously given
- Do NOT install `firebase` package in this story — use placeholder/stub that will be wired when Epic 2 sets up Firebase. Instead, create the analytics module structure with a TODO comment for Firebase SDK integration.

**IMPORTANT:** Firebase SDK is NOT yet installed (will be added in Story 2.1). The analytics module should be structured to accept Firebase integration later. For now, implement the consent flow and localStorage persistence fully, and create the analytics.ts file with the loading pattern but guard against the Firebase SDK not being available.

### Naming Conventions

- Components: PascalCase files → `Header.tsx`, `Footer.tsx`, `CookieBanner.tsx`
- Utilities/lib: camelCase files → `analytics.ts`
- CSS: Tailwind utilities only (no custom CSS class names)
- Import order: React/Next.js first, then third-party, then `@/` imports, then relative, then type-only

### Prettier Config (enforced by pre-commit hook)

```json
{ "semi": false, "singleQuote": true, "trailingComma": "all", "printWidth": 100, "tabWidth": 2 }
```

Run `npm run format` before committing. The husky pre-commit hook runs `prettier --write` and `eslint` automatically.

### Content Notes

- **Header navigation:** Keep minimal for MVP — Home and Pricing links only. Auth links (Sign In, Dashboard) will be added in Epic 2 when AuthContext is available.
- **Footer content:** Privacy Policy (`/privacy`) and Terms of Service (`/terms`) links. These pages don't exist yet (Epic 6) — the links should point to the correct routes and will show 404 until those pages are created. This is acceptable.
- **Cookie banner text:** Brief, clear language explaining that the site uses analytics cookies. Provide Accept and Reject buttons. No need for granular cookie categories — Firebase Analytics is the only cookie-using service.
- **Product context:** Warden is a video review tool for EVA After-h coaches (esports). The web portal exists to sell subscriptions. UI is in English for MVP.

### Next.js 16 Specifics (CRITICAL)

- `params` and `searchParams` are `Promise` types in Next.js 16 — must be `await`ed. Not relevant for layout components (no dynamic segments).
- `LayoutProps` is globally available — no import needed for the layout type.
- Root layout (`src/app/layout.tsx`) wraps ALL pages. Header, Footer, and CookieBanner will appear on every page.
- Layouts do NOT re-render on route navigation — state in Client Components within the layout persists across navigations (important for CookieBanner state).
- Use `next/script` with `strategy="afterInteractive"` for analytics loading, OR use dynamic `import()` — both are valid approaches.

### Anti-Patterns to Avoid

- Do NOT use `'use client'` on Header or Footer — they have no interactivity and should be Server Components
- Do NOT use `document.cookie` for consent storage — use `localStorage` (client-only concern, simpler API)
- Do NOT import Firebase SDK directly at the top level of any component — analytics must be dynamically loaded only after consent
- Do NOT hardcode colors — use Tailwind theme tokens (defined in `globals.css`)
- Do NOT use `<a>` tags for internal navigation — use `<Link>` from `next/link`
- Do NOT place component files in a flat `components/` directory — use `components/layout/` per architecture spec
- Do NOT create a `<main>` wrapper in the layout if the page already provides semantic structure — let each page define its own `<main>` element
- Do NOT add sign-in/sign-out links to the Header yet — those require AuthContext from Epic 2

### Previous Story (1.2) Context

Story 1.2 (ready-for-dev, not yet implemented) will create:
- Landing page at `src/app/page.tsx` with value proposition, CTA to `/pricing`, and app download links
- Server Component, no client JS

Story 1.1 established:
- Project scaffolded with `create-next-app` (Next.js 16.2.2)
- shadcn/ui initialized with 7 base components (Button, Card, Input, Badge, Alert, Skeleton, Dialog)
- Prettier + commitlint + husky configured and enforced
- `.env.example` with Firebase and Stripe placeholder vars
- Root layout uses Geist fonts, flexbox column layout with `min-h-full` on body, `h-full` on html
- `cn()` utility at `src/lib/utils.ts` for Tailwind class merging
- Current root layout has NO Header/Footer — this story adds them

### Current Root Layout State

```tsx
// src/app/layout.tsx (current)
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  )
}
```

The `flex min-h-full flex-col` on body is already set up for the Header-Content-Footer pattern. Add:
- `<Header />` before `{children}`
- `<main className="flex-1">{children}</main>` wrapping children (gives content the remaining space)
- `<Footer />` after the main wrapper
- `<CookieBanner />` as a fixed overlay (rendered last in DOM)

### Git Intelligence

- Commit convention: `feat(layout): <description>` using Conventional Commits
- Scope for this story: `layout`
- The pre-commit hook runs Prettier automatically — code will be formatted on commit
- Last commit: `ce26c3f feat(infra): initialize Next.js project with dev tooling (Story 1.1)`

### Dependencies

- No new npm packages required for this story
- Firebase SDK is NOT installed yet — analytics module will be a placeholder structure
- All UI built with existing shadcn/ui `Button` component + Tailwind utilities

### References

- [Source: _bmad/planning-artifacts/epics.md - Story 1.3]
- [Source: _bmad/planning-artifacts/architecture.md - Frontend Architecture, Component Boundaries]
- [Source: _bmad/planning-artifacts/architecture.md - Project Structure, components/layout/]
- [Source: _bmad/planning-artifacts/prd.md - FR28, FR29]
- [Source: _bmad/planning-artifacts/prd.md - Analytics & Cookies section]
- [Source: _bmad/planning-artifacts/prd.md - Legal Pages section]
- [Source: node_modules/next/dist/docs/01-app/01-getting-started/03-layouts-and-pages.md]
- [Source: node_modules/next/dist/docs/01-app/03-api-reference/02-components/script.md]
- [Source: node_modules/next/dist/docs/01-app/02-guides/analytics.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- All 48 tests passing (7 test files) — verified 2026-04-09

### Completion Notes List

- ✅ Task 1: Header component created as Server Component with semantic HTML, keyboard-accessible nav links (Home, Pricing), Warden brand link, sticky top with backdrop blur, mobile-first responsive
- ✅ Task 2: Footer component created as Server Component with Privacy Policy and Terms of Service links, dynamic copyright year, semantic `<footer>` + `<nav>`
- ✅ Task 3: CookieBanner created as Client Component with localStorage-based consent flow, Accept/Reject buttons using shadcn Button, fixed bottom overlay with dialog role
- ✅ Task 4: Firebase Analytics conditional loading via dynamic import with singleton guard, SSR-safe, try/catch for missing SDK
- ✅ Task 5: Root layout updated — Header, Footer, CookieBanner integrated with `<main id="main-content" className="flex-1">` wrapper and skip-to-content link
- ✅ Task 6: Accessibility verified — focus-visible rings on all links, semantic elements (header, nav, main, footer), dialog role on cookie banner

### File List

- src/components/layout/Header.tsx (created)
- src/components/layout/Footer.tsx (created)
- src/components/layout/CookieBanner.tsx (created)
- src/lib/firebase/analytics.ts (created)
- src/app/layout.tsx (modified)
- src/components/layout/Header.test.tsx (created)
- src/components/layout/Footer.test.tsx (created)
- src/components/layout/CookieBanner.test.tsx (created)
- src/lib/firebase/analytics.test.ts (created)

## Change Log

- 2026-04-09: Story 1.3 verified complete — all 6 tasks implemented, 48 tests passing, all 7 acceptance criteria satisfied. Status → review.
- 2026-04-09: Code review fixes applied — fixed fake test assertion in CookieBanner.test.tsx (H1), added aria-describedby to CookieBanner dialog (M2), created analytics.test.ts with 4 tests (M1). 52 tests passing.
