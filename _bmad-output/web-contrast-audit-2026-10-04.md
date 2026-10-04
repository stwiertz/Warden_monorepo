# Web Contrast Audit — 2026-10-04 (Story 4.1, A11Y-001 re-verify after FU-3 token bump)

**Scope:** `apps/web` dark theme (`:root` in `apps/web/src/app/globals.css`), after bumping the brand accent `#E8731A → #FF6B00` and accent-hover `#F28A2E → #FF8533` (UX §5.2.2 Option B, locked 2026-05-07).
**Method:** WCAG 2.1 relative-luminance contrast ratio, computed from the token hex values. Locked by the automated guard `apps/web/src/app/globals-contrast.test.ts` (fails CI if any pair below drops under its bar). Browser DevTools spot-check is a pending manual confirmation (see bottom).
**Bars:** normal text 4.5:1 (WCAG 1.4.3). CTA labels are 16 px / 600 — *not* "large text" (≥ 24 px, or ≥ 18.66 px bold), so 4.5:1 applies. Focus rings and meaningful icons 3:1 (WCAG 1.4.11).

## Token mapping

| UX token | Code variable | Before | After |
|---|---|---|---|
| `accent` (Warden orange) | `--primary`, `--ring`, `--chart-1`, `--sidebar-primary`, `--sidebar-ring` | `#e8731a` | `#ff6b00` |
| `accent-hover` | `--primary-hover` (new) + `--chart-2` | `#f28a2e` (chart-2 only) | `#ff8533` |
| on-accent text | `--primary-foreground`, `--sidebar-primary-foreground` | `#ffffff` | `#0f0f0f` |
| — (shadcn neutral hover surface) | `--accent` | `#252525` | unchanged |

## Ratios

| Surface | Pair | Before | After | Bar | Result |
|---|---|---|---|---|---|
| Text-primary on page bg | `#F0F0F0` / `#0F0F0F` | 16.82 | 16.82 | 4.5 | AA (AAA) |
| Text-primary on card | `#F0F0F0` / `#1A1A1A` | 15.27 | 15.27 | 4.5 | AA (AAA) |
| Text-secondary on page bg | `#999999` / `#0F0F0F` | 6.73 | 6.73 | 4.5 | AA |
| Text-secondary on card | `#999999` / `#1A1A1A` | 6.11 | 6.11 | 4.5 | AA |
| **Orange on dark bg** (links, savings label) | orange / `#0F0F0F` | 6.30 | **6.71** | 4.5 | AA |
| **Orange on card** (AuthFormToggle links, PlanCard savings) | orange / `#1A1A1A` | 5.72 | **6.10** | 4.5 | AA |
| **Button-default** (CTA, featured badge, skip link) — label on orange | `#FFFFFF` / orange (before) · `#0F0F0F` / orange (after) | **3.04 — FAIL** | **6.71** | 4.5 | AA |
| **Button-hover** — label on hover fill | `opacity-90` fades label + fill: `#E7E7E7` / `#D26919` (before) · `#0F0F0F` / `#FF8533` (after) | **2.94 — FAIL** | **7.90** | 4.5 | AA |
| Focus ring on page bg | orange / `#0F0F0F` | 6.30 | 6.71 | 3.0 | AA |
| Focus ring on card | orange / `#1A1A1A` | 5.72 | 6.10 | 3.0 | AA |
| Landing feature icon on `bg-primary/10` tile | orange / 10 % orange over bg | 5.63 | 6.01 | 3.0 | AA |
| Landing feature icon on `bg-primary/10` tile inside `bg-card` | orange / 10 % orange over card | 5.01 | 5.36 | 3.0 | AA |
| Base focus outline (`* { outline-ring }`, e.g. plain links) | `outline-ring/50` = 50 % orange over bg (before) · opaque orange (after) | **2.40 — FAIL** | **6.71** | 3.0 | AA |

## Finding — white-on-orange fails AA, before and after the bump

White labels on the orange fill were already below AA at `#E8731A` (3.04:1) and get worse at `#FF6B00` (2.86:1; 2.43:1 on `#FF8533`). UX §5.2.2's "~4.8:1 / ~5.0:1, AA-large" figures measured orange **on the background**, not text **on orange**, and treated the CTAs as large/bold text, which 16 px/600 is not.

AC5's prescribed remedy (keep the old token / pick `#E2630B` or `#F26A00`) does not fix this pair: white on `#E2630B` = 3.49, on `#F26A00` = 3.07. No orange in this hue family carries white text at 4.5:1 while staying recognisably "Warden orange".

**Resolution applied:** keep the FU-3 accent at `#FF6B00` (all orange-on-dark ratios improve) and switch the on-accent foreground to the page background `#0F0F0F` (6.71:1 default, 7.90:1 hover). FU-3 stays locked; nothing is re-opened.

**Needs Stephane's visual sign-off** (epic-end manual pass): CTA / featured-badge / skip-link labels change from white to near-black. If rejected, the only AA-compliant alternative is to re-open FU-3 for a much darker orange (white text needs luminance ≤ ~0.18, i.e. roughly `#C24E00` or darker), which would break the mobile `#FF6B00` anchor.

## Hover behaviour change

UX §3.1.3 specifies "hover → `accent-hover` background". Before this story the CTA hover was `hover:opacity-90` (faded the whole button, label included) and the shadcn Button/Badge used `[a]:hover:bg-primary/80` (darkened toward the bg). Both now use `bg-primary-hover` (`#FF8533`).

## Pending manual checks

- [ ] DevTools contrast spot-check on `/`, `/pricing`, `/auth/sign-in`, `/dashboard` confirms the computed values above.
- [ ] Visual sign-off of dark-on-orange CTA labels (see Finding).
- [ ] `npx lighthouse` accessibility score ≥ pre-bump baseline (baseline not captured in the agent lane — needs a build with real env + Chrome; run on the commit before and after Story 4.1).
