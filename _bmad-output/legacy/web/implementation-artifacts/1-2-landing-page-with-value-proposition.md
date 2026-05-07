# Story 1.2: Landing Page with Value Proposition

Status: done

## Story

As a visitor,
I want to see a landing page that explains the Warden app's value proposition,
so that I can understand what the app does and decide if I want to subscribe.

## Acceptance Criteria

1. **Given** a visitor navigates to `/`, **When** the landing page loads, **Then** the page displays the Warden app value proposition content (FR5)
2. **Given** a visitor is on the landing page, **Then** the page includes app download links for iOS and Android (FR7)
3. **Given** a visitor is on the landing page, **Then** a visible CTA navigates the visitor to the `/pricing` page (FR6)
4. **Given** the landing page is rendered, **Then** the page is server-side rendered and cached for performance (LCP < 2.5s, NFR1)
5. **Given** the landing page is viewed on any device, **Then** the layout is mobile-first responsive (320px-768px primary, progressive enhancement to desktop)
6. **Given** the landing page is audited for accessibility, **Then** the page meets WCAG 2.1 Level A accessibility requirements (NFR17)

## Tasks / Subtasks

- [x] Task 1: Implement dark theme and Warden design system CSS variables (AC: #5, #6)
  - [x] 1.1: Update `globals.css` to use the Warden color palette from UX spec — dark background (#0F0F0F), surface (#1A1A1A), Warden orange (#E8731A) as primary accent, proper text colors (#F0F0F0 primary, #999999 secondary)
  - [x] 1.2: Configure Inter font (replace Geist fonts) in `layout.tsx` using `next/font/local` with variable weight woff2 files
  - [x] 1.3: Set dark theme as default by adding `dark` class to `<html>` element in root layout
  - [x] 1.4: Update border radius tokens to match UX spec (buttons 6px, cards 8px, badges 4px)
- [x] Task 2: Update landing page hero section (AC: #1, #3, #5)
  - [x] 2.1: Implement centered hero with h1 headline, descriptive paragraph, and single primary CTA button linking to `/pricing`
  - [x] 2.2: Apply UX typography — h1 uses Inter ExtraBold (800), 2rem mobile / 3rem desktop, line-height 1.2
  - [x] 2.3: Style CTA button with Warden orange fill (`#E8731A`), white text, 6px radius, hover state (`#F28A2E`), full-width on mobile inside cards
  - [x] 2.4: Ensure hero section uses `<section>` with proper heading hierarchy and landmark structure
- [x] Task 3: Implement features section with value proposition (AC: #1, #5)
  - [x] 3.1: Display feature cards (Session Review, Clip Export, Minimap Analysis, Coaching Workflows) using semantic feature blocks with border and dark surface
  - [x] 3.2: Apply dark surface background (#1A1A1A) to feature cards with subtle border (#333333), 8px radius
  - [x] 3.3: Mobile layout: stacked single column; Desktop (md: 768px+): grid layout — features in row
  - [x] 3.4: Ensure feature icons use `aria-hidden="true"` and all text content is accessible
- [x] Task 4: Implement app download section with store links (AC: #2, #5)
  - [x] 4.1: Create download section with iOS App Store and Android Google Play links (FR7)
  - [x] 4.2: Download links should use `target="_blank"` with `rel="noopener noreferrer"` and descriptive `aria-label` attributes
  - [x] 4.3: Style download buttons as secondary (outline/ghost) style, not primary
- [x] Task 5: Implement pricing CTA section (AC: #3)
  - [x] 5.1: Bottom-of-page CTA section with headline, brief pricing mention, and link to `/pricing`
  - [x] 5.2: Use primary orange CTA button style consistent with hero
- [x] Task 6: Ensure SSR caching and performance (AC: #4)
  - [x] 6.1: Verify page is a Server Component (no 'use client' directive) for SSR
  - [x] 6.2: Verify no client-side JS is required for rendering landing page content (icons can be server-rendered)
  - [x] 6.3: Add appropriate `<meta>` viewport tag and ensure no CLS from layout shifts (Skeleton not needed for static content)
- [x] Task 7: Ensure WCAG 2.1 Level A compliance (AC: #6)
  - [x] 7.1: Verify proper heading hierarchy: single h1, h2 for sections, h3 for card titles
  - [x] 7.2: All interactive elements have minimum 44x44px touch targets (`min-h-11 min-w-11`)
  - [x] 7.3: Add skip-to-content link hidden until focused at top of page
  - [x] 7.4: Verify color contrast: primary text on dark bg (~16:1 AAA), secondary text (~5.5:1 AA), orange on dark bg (4.8:1 AA large text)
  - [x] 7.5: Keyboard-test: all links and buttons are focusable and operable with Tab/Enter
- [x] Task 8: Write unit and integration tests (AC: all)
  - [x] 8.1: Write render tests for landing page — verifies all sections render (hero, features, download, CTA)
  - [x] 8.2: Test that `/pricing` link is present and correct
  - [x] 8.3: Test that iOS and Android download links are present with correct attributes
  - [x] 8.4: Test proper heading hierarchy (h1 exists, h2s for sections)
  - [x] 8.5: Test that page exports metadata with title and description

## Dev Notes

### Architecture Requirements

- **Page location:** `src/app/page.tsx` (already exists, needs updating)
- **Server Component:** Must remain a Server Component (no 'use client') for SSR and caching (NFR1: LCP < 2.5s)
- **Max content width:** 1024px centered (`max-w-5xl` in current implementation maps to this)
- **Routing:** Landing page is public, no auth required
- **Component library:** shadcn/ui for any Card usage; compose directly from primitives, no wrapper abstractions
- **Font:** Switch from Geist to Inter (Google Font) per UX spec — Inter with weights 400, 500, 600, 700, 800

### UX Design Specifications

**Design direction:** Clean Minimal (Direction A) — dark theme, subtle orange accents, generous whitespace

**Color system (from UX spec):**
| Role | Hex | CSS Variable mapping |
|------|-----|---------------------|
| Background | `#0F0F0F` | `--background` |
| Surface | `#1A1A1A` | `--card` |
| Surface elevated | `#252525` | hover states |
| Border | `#333333` | `--border` |
| Text primary | `#F0F0F0` | `--foreground` |
| Text secondary | `#999999` | `--muted-foreground` |
| Accent primary (Warden orange) | `#E8731A` | `--primary` |
| Accent hover | `#F28A2E` | hover variant |

**Typography:**
- Font: Inter (Google Font) — clean, geometric, highly legible
- H1: 800 weight, 2rem mobile / 3rem desktop, line-height 1.2
- H2: 700 weight, 1.5rem mobile / 2rem desktop, line-height 1.2
- H3: 600 weight, 1.25rem mobile / 1.5rem desktop
- Body: 400 weight, 1rem, line-height 1.5
- No text smaller than 12px (0.75rem)

**Spacing:**
- Base unit: 4px
- Page padding: 16px mobile, 32px desktop
- Section spacing: 32px mobile, 48px desktop
- Max content width: 1024px centered

**Border radius:**
- Buttons: 6px
- Cards: 8px
- Badges: 4px

**Landing page compositions (from UX spec):**
- Hero: Heading + paragraph + single orange CTA Button
- Feature row: 3-4x small Cards with icon + text (stacked mobile, row desktop)
- Nav bar: Logo text left + nav links right (implemented in Header.tsx — Story 1.3)
- Footer: Legal links + copyright (implemented in Footer.tsx — Story 1.3)

**Button hierarchy:**
- Primary: Orange fill (#E8731A), white text, 6px radius — one per section max
- Secondary: Ghost/outline, gray text — supporting actions
- Download buttons: Secondary style (outline)

**Responsive:**
- One breakpoint: `md:` (768px)
- Mobile (default): full-width, stacked
- Desktop (md:+): wider max-width, features in row, larger typography

### Existing Implementation Notes

**Already implemented (from git commit `6cf6e29`):**
- Basic landing page structure with hero, features, pricing CTA, and download sections
- Uses Lucide React icons for features
- Header/Footer/CookieBanner are in layout (Story 1.3 scope)
- shadcn/ui components installed: Button, Card, Dialog, Input, Badge, Alert, Skeleton

**What needs to change:**
1. **Colors:** Currently using default shadcn/ui light theme. Must switch to dark theme with Warden color palette
2. **Font:** Currently Geist. Must switch to Inter per UX spec
3. **Dark mode:** Must be default (add `dark` class to `<html>`)
4. **CTA styling:** Must use Warden orange (#E8731A) instead of generic primary
5. **Touch targets:** Verify all interactive elements meet 44x44px minimum
6. **Skip link:** Not implemented — needs to be added
7. **Feature cards:** May want to use actual Card components with dark surface styling
8. **Accessibility audit:** Heading hierarchy looks correct (h1 hero, h2 sections), but contrast and touch targets need verification against UX spec values

### Testing Standards

- **Framework:** Vitest 4.x + React Testing Library
- **Test location:** Co-located next to source: `src/app/page.test.tsx`
- **Setup:** `vitest.setup.ts` already configured with jsdom environment
- **Existing tests:** Layout components (Header, Footer, CookieBanner) and Firebase modules already have tests
- **What to test:**
  - Render tests verifying sections appear
  - Link presence and href values
  - Metadata exports
  - Heading hierarchy
  - Accessibility attributes (aria-labels, roles)

### Coding Standards

- **Prettier:** semi: false, singleQuote: true, trailingComma: all, printWidth: 100, tabWidth: 2
- **Import order:** React/Next.js → Third-party → @/ project → Relative → Type-only
- **Naming:** PascalCase components, camelCase utilities, kebab-case routes
- **No `any` types** — use proper TypeScript types
- **Semantic HTML:** `<nav>`, `<main>`, `<footer>`, `<section>`, `<h1>`-`<h3>`, `<button>` (not div with onClick)
- **Commit convention:** `feat(landing): ...` scope for this story

### Project Structure Notes

- Root layout (`src/app/layout.tsx`) wraps all pages — Header, Footer, CookieBanner are there (Story 1.3)
- `src/app/page.tsx` is the landing page — this is the primary file to modify
- `src/app/globals.css` contains CSS variables — needs dark theme colors
- `src/components/ui/` has shadcn/ui components available
- All files use `@/` import alias

### References

- [Source: _bmad/planning-artifacts/epics.md#Story 1.2] — Acceptance criteria and user story
- [Source: _bmad/planning-artifacts/architecture.md#Frontend Architecture] — Component library, routing strategy
- [Source: _bmad/planning-artifacts/architecture.md#Implementation Patterns] — Naming, formatting, commit conventions
- [Source: _bmad/planning-artifacts/ux-design-specification.md#Visual Design Foundation] — Color system, typography, spacing
- [Source: _bmad/planning-artifacts/ux-design-specification.md#Design Direction Decision] — Clean Minimal direction
- [Source: _bmad/planning-artifacts/ux-design-specification.md#Component Strategy] — shadcn/ui components for Epic 1: Button, Card, Skeleton
- [Source: _bmad/planning-artifacts/ux-design-specification.md#Responsive Design] — Mobile-first, one breakpoint at md:768px
- [Source: _bmad/planning-artifacts/ux-design-specification.md#Accessibility Strategy] — WCAG 2.1 Level A implementation guidelines
- [Source: _bmad/planning-artifacts/prd.md#FR5] — Landing page value proposition
- [Source: _bmad/planning-artifacts/prd.md#FR6] — Navigate to pricing
- [Source: _bmad/planning-artifacts/prd.md#FR7] — App download links

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Google Fonts blocked in build environment (403) — switched from `next/font/google` to `next/font/local` using `@fontsource-variable/inter` woff2 files
- Pre-existing Firebase `auth/invalid-api-key` error during `next build` page generation — unrelated to this story's changes

### Completion Notes List

- Replaced default shadcn/ui light theme with Warden dark color palette (hex values) across both `:root` and `.dark` CSS scopes
- Switched font from Geist to Inter using local variable font files (woff2)
- Added `dark` class to `<html>` element for default dark mode
- Updated border radius base to 0.5rem (8px cards, ~6px buttons, ~5px badges)
- Styled hero CTA and pricing CTA buttons with Warden orange (#E8731A) fill, white text, 6px radius, hover state (#F28A2E)
- Feature cards styled with dark surface bg (#1A1A1A), border (#333333), 8px radius, responsive grid (stacked mobile → row desktop)
- Download buttons styled as secondary/outline style per button hierarchy spec
- All interactive elements have min 44x44px touch targets (min-h-11 min-w-11)
- Added skip-to-content link in root layout (sr-only, visible on focus)
- Page remains a Server Component (no 'use client') for SSR performance
- Proper heading hierarchy maintained: 1x h1, 3x h2, 4x h3
- All icons have aria-hidden="true", download links have descriptive aria-labels
- 13 new tests covering all sections, links, heading hierarchy, metadata, and accessibility attributes
- Full test suite: 48 tests across 7 files, all passing with 0 regressions

### File List

- `src/app/globals.css` — Updated CSS variables to Warden dark color palette
- `src/app/layout.tsx` — Switched from Geist to Inter font, added `dark` class, added skip-to-content link, added `id="main-content"` to `<main>`
- `src/app/page.tsx` — Restyled hero, features, pricing CTA, and download sections per UX spec
- `src/app/page.test.tsx` — New: 13 unit tests for landing page
- `src/fonts/inter-latin-wght-normal.woff2` — New: Inter variable font file (latin)
- `src/fonts/inter-latin-ext-wght-normal.woff2` — New: Inter variable font file (latin-ext)
- `package.json` — Added `@fontsource-variable/inter` dependency
- `package-lock.json` — Updated lockfile for `@fontsource-variable/inter`

### Change Log

- 2026-04-08: Implemented Story 1.2 — Landing page with Warden dark theme, value proposition content, Inter font, WCAG 2.1 Level A compliance, and 13 unit tests
- 2026-04-09: Code review fixes — removed bg-card from feature/download sections for card contrast, fixed grid to md:grid-cols-4 (single breakpoint per UX spec), removed redundant .dark CSS block, extracted shared CTA className constant, fixed sm: to md: breakpoint in download section, added package-lock.json to File List
