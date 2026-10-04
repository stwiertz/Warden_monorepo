# Story 4.1: Web Token Bump #FF6B00 + Accent-Hover #FF8533 + A11Y-001 Contrast Re-Verify (UX-DR16, FU-3)

Status: done

<!-- Created 2026-10-04 by bmad-create-story in the "bonus lane" worktree (branch bonus/web-epic-4).
     sprint-status.yaml is NOT edited from this lane (owned by the engine lane on main) — the
     backlog → ready-for-dev transition is applied at merge time. -->

## Story

As **Stephane**,
I want **the web brand-accent token bumped from `#E8731A` to `#FF6B00` and accent-hover from `#F28A2E` to `#FF8533` in the web theme, with A11Y-001 contrast re-verified across all surfaces**,
so that **the cross-surface accent reconciliation per FU-3 is locked at `#FF6B00` (mobile + web both anchor here) and the OG image asset (Story 4.2) renders against a consistent brand color.**

## Acceptance Criteria

1. `apps/web/src/app/globals.css`: the brand-accent token is `#FF6B00` (replacing `#E8731A`) and an accent-hover token is `#FF8533` (replacing `#F28A2E`). See Dev Notes → "Token-name mapping" — in this codebase the brand accent is the shadcn `--primary` variable, NOT `--accent`.
2. Theme config: same bumps reach the Tailwind theme. **This app is Tailwind v4 CSS-first — there is no `apps/web/tailwind.config.ts`**; the theme is the `@theme inline` block of `globals.css`, which must expose the hover token as a utility colour (`--color-primary-hover`).
3. Contrast check on key surfaces — orange-on-dark-bg, orange-on-card, button-default, button-hover — with each ratio recorded in `_bmad-output/web-contrast-audit-2026-10-04.md`. (Ratios computed with the WCAG 2.1 relative-luminance formula and locked by an automated test; the DevTools spot-check is a manual confirmation.)
4. All checked ratios meet WCAG AA (text-primary ~16:1, text-secondary ~5.5:1, orange ~4.8:1 — PRD A11Y-001). Normal-size text ≥ 4.5:1; the bar is NOT relaxed to AA-large for the CTA labels (16 px semibold is not "large" per WCAG: large = ≥ 24 px regular or ≥ 18.66 px bold).
5. If any ratio falls below AA: token NOT bumped to that value; alternative shade picked (e.g. `#E2630B` or `#F26A00`); FU-3 reconciliation re-opened. (See Dev Notes → "Known AA failure: white-on-orange" — the failing pair is the *foreground*, not the accent, and no nearby orange shade fixes it; resolution is recorded in the audit.)
6. No regression: `pnpm --filter web build` succeeds; `npx lighthouse` accessibility score remains ≥ baseline; web vitest + typecheck + lint pass.

## Tasks / Subtasks

- [x] Task 1 — Token bump (AC: 1, 2)
  - [x] 1.1 In `:root` of `globals.css`, replace every `#e8731a` (`--primary`, `--ring`, `--chart-1`, `--sidebar-primary`, `--sidebar-ring`) with `#ff6b00`.
  - [x] 1.2 Replace `--chart-2: #f28a2e` with `#ff8533`; add `--primary-hover: #ff8533`.
  - [x] 1.3 Expose `--color-primary-hover: var(--primary-hover)` in `@theme inline` so `bg-primary-hover` exists.
- [x] Task 2 — Wire the hover token (AC: 1, 3)
  - [x] 2.1 `src/components/ui/cta-class.ts` `ctaPrimaryClass`: replace `hover:opacity-90` with `hover:bg-primary-hover` (UX §3.1.3: "hover → accent-hover background").
  - [x] 2.2 `src/components/ui/button.tsx` + `badge.tsx` default variant: `[a]:hover:bg-primary/80` → `[a]:hover:bg-primary-hover`.
- [x] Task 3 — Resolve the white-on-orange AA failure (AC: 4, 5)
  - [x] 3.1 Set `--primary-foreground` and `--sidebar-primary-foreground` to `#0f0f0f` (the page background) — ≥ 6.7:1 on `#FF6B00`, ≥ 7.9:1 on `#FF8533`.
- [x] Task 4 — Automated contrast guard (AC: 3, 4)
  - [x] 4.1 New `src/app/globals-contrast.test.ts` (vitest): parse `globals.css` `:root`, assert token values, compute WCAG ratios for every surface pair in the audit, assert ≥ 4.5:1 (normal text) / ≥ 3:1 (focus ring, non-text UI), and assert no legacy `#e8731a` / `#f28a2e` remains.
  - [x] 4.2 Update any existing test that asserts on the replaced class strings.
- [x] Task 5 — Audit record (AC: 3, 4, 5)
  - [x] 5.1 Write `_bmad-output/web-contrast-audit-2026-10-04.md` with before/after ratio table + the foreground decision.
- [ ] Task 6 — Regression gates (AC: 6) — automated half done; Lighthouse half held for the epic-end manual pass
  - [x] 6.1 `pnpm --filter web test`, `typecheck`, `lint`, `build`.
  - [ ] 6.2 Lighthouse a11y before/after — **PENDING MANUAL** (epic-end manual pass; needs real `.env.local` + Chrome, run on the commit before and after this story).
- [x] Task 7 — Repair the pre-existing red web baseline (AC: 6; deferred-work "Web surface is red on `main`", whose stated home is "whichever story next owns the web surface")
  - [x] 7.1 Duplicate React under `node-linker=hoisted`: new `apps/web/vitest.react-singleton.ts` (first setupFile) pins Node-side `require('react')` to apps/web's react@19.2.4; `vitest.config.ts` adds `resolve.dedupe` + `server.deps.inline` for ESM React libs that ship a nested react copy; `testTimeout` 15 s (cold dynamic imports under full parallel load).
  - [x] 7.2 Duplicate zod (root zod@3.25 hoisted for mobile vs web zod@4.4) broke `@hookform/resolvers` types (TS2769 ×2): `tsconfig.json` `paths` pins `zod` / `zod/*` to apps/web's copy.
  - [x] 7.3 `user-doc-strict.test.ts` needs the generated `@warden/contracts` sources — run `pnpm --filter @warden/contracts build` first (turbo `test` already `dependsOn: ["^build"]`; only a bare `pnpm --filter web test` skips it). No code change.

### Review Findings

_Code review 2026-10-04 (Blind Hunter + Edge Case Hunter + Acceptance Auditor). Defer items go to `deferred-work.md` at merge time (this lane does not edit it)._

- [x] [Review][Defer] zod `paths` pin leaks beyond `@hookform/resolvers` — `tsconfig.json` `zod`/`zod/*` applies to the whole web tsc program, so `@warden/contracts` (`zod ^3.23.8`, resolves root zod@3.25.76 at runtime) is type-checked against web's zod@4.4.3; `zod/*` also maps by folder, bypassing zod's `exports` [apps/web/tsconfig.json:23] — deferred (decision 2026-10-04): harmless today (contracts only used in `user-doc-strict.test.ts`); real fix belongs with the hoisting/zod-version alignment
- [x] [Review][Patch] Default `<Button>` rendered as native `<button>` has no hover — `[a]:hover:` only matches anchors; sign-in/register submit + cookie Accept never show accent-hover (UX §3.1.3) [apps/web/src/components/ui/button.tsx:13]
- [x] [Review][Patch] Base focus outline `outline-ring/50` ≈ 2.45:1 on page bg — fails WCAG 1.4.11 3:1; it is the only focus indicator on plain links (e.g. AuthFormToggle); test checks opaque ring only [apps/web/src/app/globals.css:94]
- [x] [Review][Patch] Audit "before" hover ratio (≈3.64) is miscomputed — `opacity-90` fades the label too; still FAIL, number wrong [_bmad-output/web-contrast-audit-2026-10-04.md:27]
- [x] [Review][Patch] Contrast guard gaps — feature icon tile on `bg-card` not asserted (only page bg); "PRD headline figures" test asserts only text-primary, not orange ~4.8 / text-secondary ~5.5 [apps/web/src/app/globals-contrast.test.ts:110]
- [x] [Review][Patch] React resolver patch not idempotent and drops caller `options` — stacks a wrapper per setup run in a reused worker; replaces `options` instead of merging [apps/web/vitest.react-singleton.ts:25]
- [x] [Review][Defer] `react-dom` / `scheduler` not pinned by the singleton — aligned with web react@19.2.4 only by version coincidence [apps/web/vitest.react-singleton.ts:26] — deferred, pre-existing hoisting debt
- [x] [Review][Defer] `server.deps.inline` is a hand-maintained, unanchored list — a new ESM React lib with a nested react copy brings back the `useState` null crash [apps/web/vitest.config.ts:18] — deferred, pre-existing hoisting debt
- [x] [Review][Defer] Global `testTimeout: 15000` masks slow/hung tests suite-wide [apps/web/vitest.config.ts:13] — deferred, root cause is cold inlined transforms

## Dev Notes

### Token-name mapping (critical — do not rename shadcn variables)

The epic AC says `--accent` / `colors.accent`. In the shipped web theme (shadcn/ui + Tailwind 4), the names mean something else:

| Epic/UX name | Code variable | Current | Target |
|---|---|---|---|
| `accent` (Warden orange) | `--primary` (+ `--ring`, `--chart-1`, `--sidebar-primary`, `--sidebar-ring`) | `#e8731a` | `#ff6b00` |
| `accent-hover` | none today; `#f28a2e` lives only in `--chart-2` | `#f28a2e` | new `--primary-hover` `#ff8533` (+ `--chart-2`) |
| — | shadcn `--accent` = neutral hover surface `#252525` | `#252525` | **unchanged** |

Renaming shadcn's `--accent` to orange would turn every ghost/outline hover (`hover:bg-accent`, e.g. landing-page store buttons in `src/app/page.tsx`) orange. Don't.

### Files in play (current state → change → preserve)

- `apps/web/src/app/globals.css` — `@theme inline` maps `--color-*` to `:root` vars; `:root` is dark-only (no `.dark` override block). Change: hex values above + `--primary-hover`. Preserve: every other token, the `@custom-variant dark`, base layer.
- `apps/web/src/components/ui/cta-class.ts` — `ctaPrimaryClass` used by `src/app/page.tsx` (hero CTA), `PlanCta.tsx`, `CouponInput.tsx`. Hover today is `hover:opacity-90` (fades label too). Preserve: min 44×44 target, focus-visible ring (A11Y-002), radius 6.
- `apps/web/src/components/ui/button.tsx`, `badge.tsx` — shadcn primitives (codebase-owned per UX §6.6); only the default-variant hover class changes.
- Orange-as-text surfaces (no change, re-verified): `text-primary` in `AuthFormToggle.tsx` (links, on card), `PlanCard.tsx` savings label (on card), landing feature icons (`page.tsx`, on `bg-primary/10` tile over bg). Orange-fill: `PlanCard.tsx` "featured" badge (`bg-primary text-primary-foreground`, text-xs), skip-link in `layout.tsx` (focus).

### Known AA failure: white-on-orange (pre-existing, worsened by the bump)

Computed ratios (WCAG 2.1):

| Pair | `#E8731A` (old) | `#FF6B00` (new) |
|---|---|---|
| orange on bg `#0F0F0F` | 6.30 | 6.71 |
| orange on card `#1A1A1A` | 5.72 | 6.10 |
| white `#FFFFFF` on orange (CTA label) | **3.04** | **2.86** |
| white on hover `#F28A2E` / `#FF8533` | **2.49** | **2.43** |
| `#0F0F0F` on orange | 6.30 | 6.71 |

The CTA label (`text-base font-semibold` = 16 px/600) is normal-size text → needs 4.5:1. White fails at the old AND new value, and AC5's suggested alternatives don't help (`#E2630B` white = 3.49, `#F26A00` = 3.07). UX §5.2.2's "~4.8:1 / AA-large" figures describe orange-on-background, not text-on-orange. The only fix that keeps FU-3 locked at `#FF6B00` is a dark on-accent foreground: `--primary-foreground: #0f0f0f`. This is a visible design change (CTA labels go from white to near-black) → flagged for Stephane's visual sign-off in the epic-end manual pass. If rejected, FU-3 must be re-opened (AC5) because no orange in this hue family carries white text at AA.

### Testing standards

- Vitest 4 + jsdom (`apps/web/vitest.config.ts`, `globals: true`, `@` alias → `src`). Tests are co-located (`*.test.ts(x)` next to source). jsdom does not compute Tailwind styles, so contrast is asserted from the CSS source, not from rendered DOM.
- Scripts: `pnpm --filter web test | typecheck | lint | build`.

### Project Structure Notes

- No `tailwind.config.ts` exists (Tailwind 4 `@import 'tailwindcss'` + `@theme inline`). AC2 is satisfied in `globals.css`; do not create a JS config.
- Next 16.2 — `apps/web/AGENTS.md` warns APIs differ from training data; this story touches no Next APIs.
- Lane constraint: do not edit `_bmad-output/sprint-status.yaml` / `deferred-work.md` from this worktree.

### References

- [Source: _bmad-output/epics-and-stories.md#Story 4.1]
- [Source: _bmad-output/ux-design.md#1.5 Design Tokens (locked)] — web accent `#FF6B00`, accent-hover `#FF8533`
- [Source: _bmad-output/ux-design.md#5.2.2 Accent orange — divergent shade audit] — Option B locked 2026-05-07
- [Source: _bmad-output/ux-design.md#3.1.3 Google Sign-In button] — hover → accent-hover background
- [Source: _bmad-output/ux-design.md#6.5] — `feat(layout): bump web accent token to #FF6B00`
- [Source: _bmad-output/prd.md — A11Y-001/A11Y-002]

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (claude-opus-5-5), bonus-lane worktree `Warden_monorepo-bonus` on `bonus/web-epic-4` (from main @ f382634).

### Debug Log References

- Baseline before any change: web vitest **134 failed / 191 passed (325)**, 8 errors; tsc 2 errors (TS2769 in `EmailSignInForm.tsx`, `RegistrationForm.tsx`). Root cause: hoisted mobile react@19.1.0 + nested react@19.2.4 copies (`@base-ui/react`, `next`, `react-dom`, `lucide-react`, `react-hook-form`, `@floating-ui/react-dom`, ...) and hoisted zod@3.25.
- Tried and discarded: `resolve.dedupe` alone (no effect — the requires happen in externalized CJS); `deps.optimizer.client` prebundle (worse: 121 failed, `next/link` still loaded the root React).
- After Task 7: **43 files / 349 tests passed** (330 pre-existing incl. the previously unloadable `user-doc-strict` suite + 19 new contrast tests).
- `pnpm --filter web build`: compile + TypeScript OK; prerender of `/_not-found` fails without `.env.local` (`auth/invalid-api-key`) — environment, not code. With placeholder `NEXT_PUBLIC_FIREBASE_*` env: build fully green (12/12 static pages). Compiled CSS verified: `--primary:#ff6b00`, `--primary-foreground:#0f0f0f`, `.hover\:bg-primary-hover:hover{background-color:var(--primary-hover)}`.

### Completion Notes List

- AC1 met — tokens bumped in `globals.css`. Brand accent lives in shadcn `--primary` (+ ring / chart-1 / sidebar-primary / sidebar-ring); new `--primary-hover: #ff8533` (+ chart-2). shadcn `--accent` (neutral `#252525`) deliberately untouched.
- AC2 met (adapted) — no `tailwind.config.ts` exists (Tailwind 4 CSS-first); theme exposure via `--color-primary-hover` in `@theme inline` → `bg-primary-hover` utility, now used by `ctaPrimaryClass`, Button and Badge default variants (UX §3.1.3).
- AC3 met for computed ratios, recorded in `_bmad-output/web-contrast-audit-2026-10-04.md` and locked by `globals-contrast.test.ts`; DevTools spot-check **pending manual**.
- AC4 met — every pair ≥ 4.5:1 (text) / ≥ 3:1 (ring, icon) after the on-accent foreground switch.
- AC5 met without re-opening FU-3 — white-on-orange failed AA before (3.04) and after (2.86); AC5's alternative shades don't fix it (3.49 / 3.07). Applied `--primary-foreground: #0f0f0f` (6.71 / 7.90 on hover). **Visual sign-off pending** — CTA labels change white → near-black.
- AC6 partial — build, test, typecheck, lint green; Lighthouse ≥ baseline **pending manual**.
- Lint: 0 errors, 7 pre-existing `_args` warnings in untouched test files.
- Lane rules honoured: `sprint-status.yaml` / `deferred-work.md` untouched (transitions + deferred entries handed to the caller for merge time); nothing committed.

### File List

- `apps/web/src/app/globals.css` (modified)
- `apps/web/src/app/globals-contrast.test.ts` (new)
- `apps/web/src/components/ui/cta-class.ts` (modified)
- `apps/web/src/components/ui/button.tsx` (modified)
- `apps/web/src/components/ui/badge.tsx` (modified)
- `apps/web/vitest.config.ts` (modified)
- `apps/web/vitest.react-singleton.ts` (new)
- `apps/web/tsconfig.json` (modified)
- `_bmad-output/web-contrast-audit-2026-10-04.md` (new)
- `_bmad-output/implementation-artifacts/4-1-web-token-bump-accent-hover-a11y-001-contrast-re-verify.md` (new)

## Change Log

- 2026-10-04 — Story created (bmad-create-story), status ready-for-dev.
- 2026-10-04 — Implemented (bmad-dev-story): FU-3 token bump, `--primary-hover` wired to CTA/Button/Badge hover, on-accent foreground → `#0f0f0f` (AA fix), contrast guard test + audit doc; repaired the pre-existing red web baseline (Task 7). Status → review. Lighthouse + DevTools + visual sign-off held for the epic-end manual pass.
- 2026-10-04 — Code review (bmad-code-review): 5 patches applied (native `<Button>` hover, base focus outline `outline-ring/50` → opaque — was 2.40:1, audit before-hover ratio corrected to 2.94, contrast guard + PRD figures extended, idempotent React resolver pin); 4 deferred (zod `paths` leak into `@warden/contracts`, react-dom/scheduler pin, inline list, global timeout) — to `deferred-work.md` at merge. Web vitest 351/351, tsc 0, lint 0. Status → done (Lighthouse/DevTools/visual sign-off stay in the epic-end manual pass; sprint-status synced at merge, not from this lane).
