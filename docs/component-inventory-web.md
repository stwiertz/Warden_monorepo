# Component Inventory — apps/web

Catalogues every React component in [src/components/](../apps/web/src/components/) and surfaces in [src/app/](../apps/web/src/app/). Web uses **shadcn/ui 4** (Base UI primitives) for low-level UI, with feature-specific compositions on top.

## App Router pages

[src/app/](../apps/web/src/app/)

| Route                 | File                                                               | Type             | Purpose                                         |
| --------------------- | ------------------------------------------------------------------ | ---------------- | ----------------------------------------------- |
| `/`                   | [page.tsx](../apps/web/src/app/page.tsx)                           | server component | Marketing landing                               |
| (root layout)         | [layout.tsx](../apps/web/src/app/layout.tsx)                       | server component | Root HTML, fonts, AuthProvider                  |
| `/auth/sign-in`       | [auth/sign-in/page.tsx](../apps/web/src/app/auth/sign-in/page.tsx) | client component | Sign-in (email/password + Google)               |
| `/pricing`            | [pricing/page.tsx](../apps/web/src/app/pricing/page.tsx)           | mixed            | Plan picker + checkout entry                    |
| `/dashboard`          | [dashboard/page.tsx](../apps/web/src/app/dashboard/page.tsx)       | mixed            | Authed surface with SubscriptionCard            |
| `/dashboard/(layout)` | [dashboard/layout.tsx](../apps/web/src/app/dashboard/layout.tsx)   | server component | Dashboard sub-layout, gates on `requireSession` |

Plus tests next to each: `page.test.tsx`, `layout.test.tsx`.

## Auth — [src/components/auth/](../apps/web/src/components/auth/)

| Component          | File                                                                             | Role                                            |
| ------------------ | -------------------------------------------------------------------------------- | ----------------------------------------------- |
| AuthFormToggle     | [AuthFormToggle.tsx](../apps/web/src/components/auth/AuthFormToggle.tsx)         | Switches between sign-in and registration forms |
| EmailSignInForm    | [EmailSignInForm.tsx](../apps/web/src/components/auth/EmailSignInForm.tsx)       | Email/password sign-in (react-hook-form + Zod)  |
| RegistrationForm   | [RegistrationForm.tsx](../apps/web/src/components/auth/RegistrationForm.tsx)     | Email/password registration                     |
| GoogleSignInButton | [GoogleSignInButton.tsx](../apps/web/src/components/auth/GoogleSignInButton.tsx) | Google OAuth via firebase client SDK            |
| SignOutButton      | [SignOutButton.tsx](../apps/web/src/components/auth/SignOutButton.tsx)           | Calls `destroySessionAndRedirect`               |

All have `*.test.tsx` co-located.

## Checkout — [src/components/checkout/](../apps/web/src/components/checkout/)

| Component       | File                                                                           | Role                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| CheckoutContext | [CheckoutContext.tsx](../apps/web/src/components/checkout/CheckoutContext.tsx) | React context for the in-flight checkout (selected plan, coupon, loading flags). No persistence — session-scoped only. |
| PlanCard        | [PlanCard.tsx](../apps/web/src/components/checkout/PlanCard.tsx)               | Renders one `Plan` (from `lib/pricing/plans.ts`) — name, price, savings, features                                      |
| PlanCta         | [PlanCta.tsx](../apps/web/src/components/checkout/PlanCta.tsx)                 | The button that POSTs `/api/checkout/session` and redirects to Stripe                                                  |
| CouponInput     | [CouponInput.tsx](../apps/web/src/components/checkout/CouponInput.tsx)         | Inline coupon code field — debounced POST to `/api/checkout/coupon` for preview                                        |

All except `CheckoutContext` have `*.test.tsx`.

## Dashboard — [src/components/dashboard/](../apps/web/src/components/dashboard/)

| Component        | File                                                                              | Role                                                                                                                                    |
| ---------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| SubscriptionCard | [SubscriptionCard.tsx](../apps/web/src/components/dashboard/SubscriptionCard.tsx) | Shows current `SubscriptionResponse` — status badge, plan, next renewal, "Manage subscription" button (POST `/api/subscription/portal`) |

`*.test.tsx` co-located.

## Layout — [src/components/layout/](../apps/web/src/components/layout/)

| Component         | File                                                                             | Role                                             |
| ----------------- | -------------------------------------------------------------------------------- | ------------------------------------------------ |
| Header            | [Header.tsx](../apps/web/src/components/layout/Header.tsx)                       | Site header, nav links, brand                    |
| HeaderAuthActions | [HeaderAuthActions.tsx](../apps/web/src/components/layout/HeaderAuthActions.tsx) | Sign-in/sign-out CTA in header — reads `useAuth` |
| Footer            | [Footer.tsx](../apps/web/src/components/layout/Footer.tsx)                       | Site footer                                      |
| CookieBanner      | [CookieBanner.tsx](../apps/web/src/components/layout/CookieBanner.tsx)           | GDPR-style cookie consent banner                 |

All have `*.test.tsx`.

## UI primitives — [src/components/ui/](../apps/web/src/components/ui/)

shadcn/ui 4 components, generated into the repo (NOT runtime imports from a package). Edit-friendly.

| Primitive      | File                                                       | Notes                                                           |
| -------------- | ---------------------------------------------------------- | --------------------------------------------------------------- |
| Button         | [button.tsx](../apps/web/src/components/ui/button.tsx)     | Variants: default, destructive, outline, secondary, ghost, link |
| Card           | [card.tsx](../apps/web/src/components/ui/card.tsx)         | + CardHeader / CardContent / CardFooter                         |
| Input          | [input.tsx](../apps/web/src/components/ui/input.tsx)       |                                                                 |
| Alert          | [alert.tsx](../apps/web/src/components/ui/alert.tsx)       | + AlertTitle / AlertDescription                                 |
| Dialog         | [dialog.tsx](../apps/web/src/components/ui/dialog.tsx)     | Base UI primitive                                               |
| Badge          | [badge.tsx](../apps/web/src/components/ui/badge.tsx)       | Variants for subscription status colour                         |
| Skeleton       | [skeleton.tsx](../apps/web/src/components/ui/skeleton.tsx) | Loading placeholder                                             |
| `cta-class.ts` | [cta-class.ts](../apps/web/src/components/ui/cta-class.ts) | Shared class-variance helper for CTA-style buttons              |

`components.json` at the web root is the shadcn registry config (paths, tailwind config, RSC mode). Re-add primitives via `pnpm --filter web exec shadcn add <name>` (not yet documented as a workflow — assume per the shadcn CLI defaults).

## Contexts and hooks

| Surface         | File                                                                     | Notes                                                                                                 |
| --------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| AuthContext     | [src/contexts/AuthContext.tsx](../apps/web/src/contexts/AuthContext.tsx) | Wraps Firebase `onAuthStateChanged`. Provides `{user, loading, error}`. Mounted in root `layout.tsx`. |
| useAuth         | [src/hooks/useAuth.ts](../apps/web/src/hooks/useAuth.ts)                 | Consumer of `AuthContext`.                                                                            |
| useSubscription | [src/hooks/useSubscription.ts](../apps/web/src/hooks/useSubscription.ts) | Fetches `/api/subscription` once on mount, parses with Zod, returns `{subscription, loading, error}`. |

There is **no global state library** (no Redux, no Zustand). Auth is React context; subscription is a per-page hook; everything else is local component state or server-rendered.

## Styling

- **Tailwind CSS 4** via `@tailwindcss/postcss`. Theme tokens in `src/app/globals.css` (per legacy [README](../apps/web/README.md)).
- **`cn()` utility** in [lib/utils.ts](../apps/web/src/lib/utils.ts) — `clsx + tailwind-merge` (deduplicates conflicting Tailwind classes).
- **Class-variance-authority** for variant props on shadcn primitives.
- **Geist** font (sans + mono), local files in `src/fonts/` + `@fontsource-variable/inter`.

## Testing

Vitest + jsdom + @testing-library/react. Co-located `*.test.tsx` for every UI component listed above. Render assertions are typically:

- Render with required props.
- Click → assert callback / DOM update.
- For data-loading components: mock `fetch` (or use `vi.spyOn(global, 'fetch')`) for API routes.

Setup file: [vitest.setup.ts](../apps/web/vitest.setup.ts).

## Conventions

- **PascalCase filenames** for components, **kebab-case** for utility modules in `lib/`.
- Components default to **server components**; opt into client with `'use client'` at the top (auth/checkout/dashboard interactive surfaces).
- Components use the `@/` alias (`@/lib/...`, `@/components/ui/...`, `@/contexts/...`).
- Forms use `react-hook-form` + `@hookform/resolvers/zod` with schemas from [lib/schemas/](../apps/web/src/lib/schemas/).
- Single-quoted strings, no semicolons, trailing commas (Prettier conventions inherited from legacy `WardenWeb`).

## Not yet inventoried

- Loading skeletons per route — currently `<Skeleton />` is used inline; no per-page `loading.tsx` files in the App Router (Next 16 supports them, the team hasn't standardised).
- Error boundaries — `error.tsx` per route segment is unused. Failures surface as un-pretty 500s. Phase 6 candidate.
