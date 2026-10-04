# Story 4.2: OG Image Asset + Layout Meta (UX-DR13 + UX-DR14, web-LANDING-002)

Status: done

<!-- Created 2026-10-04 by bmad-create-story in the "bonus lane" worktree (branch bonus/web-epic-4).
     sprint-status.yaml is NOT edited from this lane (owned by the engine lane on main) — the
     backlog → ready-for-dev transition is applied at merge time. -->

## Story

As **Coach Thomas seeing the Discord card preview when a coupon link is shared**,
I want **the Discord (and Twitter, etc.) preview to show a 1200×630 OG image with the FR-locked hero tagline, the Warden wordmark and the `#FF6B00` accent, plus accurate meta (title, description, og:image, twitter:card)**,
so that **the J5 distribution moat is reinforced — the Discord preview is itself a brand surface; passive players (Lucas) see Warden every time a clip's coupon link is shared.**

## Acceptance Criteria

1. `apps/web/public/og/landing.jpg` exists: 1200×630, baseline/progressive JPEG, sRGB (ICC profile embedded), ≤ 200 KB, `#FF6B00` as the primary accent (FU-3, locked by Story 4.1).
2. Image content follows the UX §3.3.2 locked composition, with the FU-3 accent substituted for the superseded `#E8731A`: `#0F0F0F` background, "W" mark in `#FF6B00` + `WARDEN` wordmark top-left, the FR-locked hero `Progresser plus vite en investissant moins de temps.` (verbatim, I18N-002), the subtitle `Coaching FPS sur mobile · Auto-slicing · Voix · Discord-ready`, a `warden.team` URL chip bottom-right, and a minimal `#FF6B00` accent border (epic AC). No screenshots, testimonials or counters.
3. Root metadata (`apps/web/src/app/layout.tsx`) carries Open Graph + Twitter Card meta per UX §3.3.1 / §4.2.9:
   - `metadataBase` = an absolute site URL (see Dev Notes → "metadataBase"), so `og:image` / `twitter:image` render as absolute URLs (`https://warden.team/og/landing.jpg` in production), never `http://localhost:3000/...`.
   - `og:type=website`, `og:title` = `Warden — Le clip est le produit. Le téléphone suffit.`, `og:description` = `L'app de coaching mobile pour joueurs FPS compétitifs. Auto-slicing, minimap, voix, partage Discord — tout sur le téléphone.`, `og:url` = `/`, `og:image` = `/og/landing.jpg` with `width=1200`, `height=630`, `type=image/jpeg` and an `alt`, `og:locale=fr_FR`, `og:site_name=Warden`.
   - `twitter:card=summary_large_image`, `twitter:title` = `Warden — Progresser plus vite en investissant moins de temps.`, `twitter:description` = `L'app de coaching mobile pour joueurs FPS compétitifs.`, `twitter:image` = `/og/landing.jpg`.
   - Root `title.default` = `Warden — Coaching companion mobile pour joueurs compétitifs` (epic AC literal; the `%s | Warden` template is kept), root `description` = the OG landing description.
4. The OG image actually reaches the rendered `<head>` of `/` and `/pricing`. Next merges route metadata **shallowly**, so the existing `openGraph` blocks in `src/app/page.tsx` and `src/app/pricing/page.tsx` would otherwise erase the root image. `/pricing` gets `og:url=/pricing` and `og:title` = `Warden — €7.99/mois ou €79.90/an. Coaching FPS sur mobile.` (UX §3.3.1 / §4.2.9). Page `<title>`s and English page descriptions are NOT changed (English web copy is Story 4.7's).
5. Per-route overrides supported: one helper builds a route's `openGraph` block from the shared defaults, taking an optional path, title and image. `/pricing` uses it. A pricing-specific image is out of V1 scope, but the helper accepts one.
6. Dashboard routes emit `<meta name="robots" content="noindex">` (UX §3.3.1 "Dashboard: protected user data, no OG preview surface").
7. Automated guard (the epic says "no automated tests"; this story adds them because both AC1 and AC4 can regress silently): vitest asserts the asset's dimensions, size, JPEG format and sRGB ICC marker, plus the resolved metadata of root, `/` and `/pricing` (image present, absolute-URL base, FR strings verbatim).
8. Discord card preview tested manually (paste the deployed / staging URL into a Discord channel → the preview shows the new image) and checked in a Twitter/X card validator. **Held for the epic-end manual pass** (needs a publicly reachable deployment).
9. The image (and its reproducible generator) is committed to the repo.
10. No regression: web vitest, `typecheck`, `lint`, `build` green.

## Tasks / Subtasks

- [x] Task 1 — Site URL + shared OG metadata module (AC: 3, 4, 5)
  - [x] 1.1 New `src/lib/seo/site-url.ts`: `resolveSiteUrl(env = process.env.NEXT_PUBLIC_APP_URL): URL`. It returns the env value when it parses as an absolute http(s) URL, otherwise `https://warden.team`, and strips any trailing slash. Unit-test valid, empty, malformed, trailing-slash and non-http cases.
  - [x] 1.2 New `src/lib/seo/og.ts`: the copy constants (UX §4.2.9 verbatim), `LANDING_OG_IMAGE` (`/og/landing.jpg`, 1200, 630, `image/jpeg`, alt), `buildOpenGraph({ path, title?, description?, images? })` and `defaultTwitter`.
- [x] Task 2 — Wire the metadata (AC: 3, 4, 5, 6)
  - [x] 2.1 New `src/lib/seo/root-metadata.ts` exporting `rootMetadata` (metadataBase, title, description, openGraph, twitter); `layout.tsx` re-exports it as `metadata`. This keeps it testable without loading `next/font/local`.
  - [x] 2.2 `src/app/page.tsx`: replace its English `openGraph` block with `buildOpenGraph({ path: '/' })`; keep `title` / `description`.
  - [x] 2.3 `src/app/pricing/page.tsx`: `openGraph: buildOpenGraph({ path: '/pricing', title: OG_COPY.pricingTitle })`; keep `title` / `description`.
  - [x] 2.4 `src/app/dashboard/layout.tsx`: add `robots: { index: false, follow: false }`.
  - [x] 2.5 Update the existing metadata assertions in `page.test.tsx` / `pricing/page.test.tsx` / `dashboard/layout.test.tsx` as needed.
- [x] Task 3 — Produce the OG image (AC: 1, 2, 9)
  - [x] 3.1 New `apps/web/scripts/og/generate-landing-og.mjs`: builds the composition with `sharp`, using Next's own copy (resolved from `next`'s install location, so the project gains no dependency) and Pango text with Inter. It writes `public/og/landing.jpg` (sRGB ICC embedded, mozjpeg, quality tuned to stay ≤ 200 KB).
  - [x] 3.2 Fonts: FreeType in sharp's libvips cannot read the vendored `src/fonts/inter-latin-wght-normal.woff2`, so the script takes `--font <ttf>` (Inter variable TTF, OFL). The header documents how to obtain it: decompress the vendored woff2 with `fontTools`, or download it from the rsms/inter release.
  - [x] 3.3 Run it, eyeball the output, commit `public/og/landing.jpg`.
- [x] Task 4 — Automated guards (AC: 7)
  - [x] 4.1 New `src/app/og-asset.test.ts`: read `public/og/landing.jpg` and assert the JPEG SOI, the SOFn frame at 1200×630, ≤ 200 KB, and an APP2 `ICC_PROFILE` segment naming sRGB (pure Node byte parsing, no sharp in tests).
  - [x] 4.2 New `src/lib/seo/og.test.ts` + `root-metadata.test.ts`: the root, `/` and `/pricing` metadata each carry the image (1200×630), FR copy verbatim, `twitter.card` `summary_large_image`, and a `metadataBase` that is an absolute URL.
- [ ] Task 5 — Regression gates (AC: 8, 10) — automated half done; Discord/X half held for the epic-end manual pass
  - [x] 5.1 `pnpm --filter @warden/contracts build` then `pnpm --filter web test`, `typecheck`, `lint`, `build` (with placeholder `NEXT_PUBLIC_FIREBASE_*` env, as in 4.1); grep the prerendered `/` and `/pricing` HTML for absolute `og:image` / `twitter:image`.
  - [ ] 5.2 Discord preview + Twitter/X card validator — **PENDING MANUAL** (epic-end manual pass; needs a public deployment).

### Review Findings

_`/bmad-code-review 4.2`, 2026-10-04. Uncommitted working tree on `bonus/web-epic-4`; three layers (blind, edge, acceptance)._

- [x] [Review][Decision] Type sizes differ from the UX §3.3.2 locked composition — hero is Inter 800 / 64 (UX: 56), subtitle Inter 400 / 26 (UX: 22). The sentence-case deviation is documented; the size change is not. Either regenerate at 56/22 or record the deviation in "Spec conflicts resolved here". **Resolved: keep 64/26, recorded there.**
- [x] [Review][Decision] `/pricing` X/Twitter card shows the landing title — `/pricing` overrides `openGraph` but inherits `defaultTwitter`, so X shows "Progresser plus vite…" while Discord shows the price. UX §4.2.9 lists no pricing twitter copy. Either add `twitter: { ...defaultTwitter, title: OG_COPY.pricingTitle }` or accept it as is. **Resolved: accepted as is** (UX §4.2.9 defines no pricing twitter copy).
- [x] [Review][Patch] Dashboard still emits the full OG/Twitter card — `robots` alone doesn't satisfy UX §3.3.1 "no OG preview surface"; dashboard inherits root `openGraph`/`twitter`. Set `openGraph: null, twitter: null` and assert it [apps/web/src/app/dashboard/layout.tsx:12]
- [x] [Review][Patch] Production `metadataBase` accepts `http://localhost` (the `.env.example` value), and the root test only checks `^https?:$`, so the exact AC3 regression passes — reject loopback hosts when `NODE_ENV === 'production'`, test it [apps/web/src/lib/seo/site-url.ts:11]
- [x] [Review][Patch] `resolveSiteUrl` keeps the URL path although documented as an origin — `https://warden.team/app` yields `/app` in `metadataBase`; return `url.origin` [apps/web/src/lib/seo/site-url.ts:16]
- [x] [Review][Patch] `buildOpenGraph({ images: [] })` ships no `og:image`, defeating the helper's guarantee — type `images` as a non-empty tuple [apps/web/src/lib/seo/og.ts:44]
- [x] [Review][Patch] Generator overwrites the committed JPEG before the 200 KB check — encode to a buffer, check, then write [apps/web/scripts/og/generate-landing-og.mjs:128]
- [x] [Review][Patch] Task 3.3 ticked `[x]` but the image and generator are not committed (AC9 open until the user's commit go) [_bmad-output/implementation-artifacts/4-2-og-image-asset-layout-meta.md:46]
- [x] [Review][Defer] `/pricing` `<title>` renders "Pricing — Warden | Warden" (page title + root `%s | Warden` template) [apps/web/src/app/pricing/page.tsx:11] — deferred, pre-existing
- [x] [Review][Defer] Prices are hard-coded in `OG_COPY.pricingTitle`, separate from `PLAN_MONTHLY`/`PLAN_YEARLY`; a price change leaves stale Discord previews [apps/web/src/lib/seo/og.ts:23] — deferred, copy is UX-locked verbatim
- [x] [Review][Defer] AC7 tests assert the exported metadata literals, not Next's resolved/merged `<head>`; the absolute `og:image` was verified only by a manual `next start` + curl [apps/web/src/lib/seo/root-metadata.test.ts:1] — deferred, needs a render-level harness

## Dev Notes

### Current state (read before touching)

- `src/app/layout.tsx` — root `metadata` = `{ title: { default: 'Warden — Video Review for Coaches', template: '%s | Warden' }, description: 'Warden helps EVA After-h coaches …' }`. No `metadataBase`, no OG/Twitter. It also loads `next/font/local` (Inter woff2) and renders the skip link, AuthProvider, Header, Footer and CookieBanner. **All of that must be preserved.**
- `src/app/page.tsx` (landing) — own `metadata` with an English `openGraph` block (`locale: 'en_US'`, no images). `page.test.tsx:91` asserts `title` + `description` only.
- `src/app/pricing/page.tsx` — own `metadata` with an English `openGraph` block. `pricing/page.test.tsx:97` asserts `openGraph` via `toMatchObject` and will need updating.
- `src/app/dashboard/layout.tsx` — `metadata = { title: 'Dashboard' }`, server-side `requireSession()` gate.
- `src/app/auth/sign-in/page.tsx` — `{ title: 'Sign In' }`; it inherits the root OG card, which is fine.
- `public/` holds only the create-next-app SVGs. No `og/` directory yet.

### Shallow-merge trap (why AC4 exists)

Next 16 docs (`node_modules/next/dist/docs/01-app/03-api-reference/04-functions/generate-metadata.md` § Merging): metadata from nested segments is **shallowly** merged, so a page's `openGraph` **replaces** the layout's whole `openGraph`, images included. Today both `/` and `/pricing` define `openGraph` without images. Adding the image to the root layout alone would leave the two most-shared URLs with **no** `og:image`. Every route that sets `openGraph` must build it from the shared helper. `twitter` has the same rule, so routes that don't override `twitter` inherit the root one intact.

### metadataBase

Relative image URLs are resolved against `metadataBase`. Without it, Next falls back (`next/dist/lib/metadata/resolvers/resolve-url.js` `getSocialImageMetadataBaseFallback`) to `VERCEL_*` env vars, then to `http://localhost:${PORT}`. **This app is hosted on Firebase, not Vercel** (`apps/web/firebase.json`), so production would ship `og:image=http://localhost:3000/og/landing.jpg` and Discord would render a blank card. The repo already uses `NEXT_PUBLIC_APP_URL` for absolute URLs (`api/checkout/session/route.ts:35` `resolveAppUrl`; `.env.example` = `http://localhost:3000`). Reuse it, with `https://warden.team` (UX §3.3.1 canonical) as the fallback when it is unset or malformed. `NEXT_PUBLIC_*` is inlined at build time, so the production build must have it set to the public origin. Note this for the deploy checklist.

### Copy (all verbatim — I18N-002 / UX §4.2.9)

OG copy is **French** even though the web UI is English: the audience is FR/BE Discord channels (UX §4.2.9 note). The hero `Progresser plus vite en investissant moins de temps.` is FR-locked and must be rendered character-for-character. The UX diagram draws it in capitals; the image keeps the verbatim casing (no text-transform) so the lock holds literally. That is a visual-only deviation from the diagram; flip to uppercase at visual sign-off if wanted.

### Spec conflicts resolved here

- The epic story statement says "tagline overlaid on a `#FF6B00` accent **background**". UX §3.3.2 (the "locked composition" the epic AC points to) uses a `#0F0F0F` background with the accent on the W mark. We follow UX and add the epic's "minimal accent border". (`#0F0F0F` text on `#FF6B00` would also work, but the UX layout is the locked one.)
- UX §3.3.2 says the W mark is `#E8731A`. That value was superseded by FU-3 / Story 4.1, so it becomes `#FF6B00`.
- The epic AC sets root `title` = `Warden — Coaching companion mobile pour joueurs compétitifs`. That applied as `title.default`. Landing and pricing keep their own English `<title>`s (Story 4.7 owns English copy).
- UX §3.3.2 sets the hero at Inter 800 / 56 and the subtitle at Inter 400 / 22. The card uses 64 / 26: at 56 / 22 the text reads small in a Discord embed, and 64 still fits the 1200 px card with margin. Kept deliberately (code review 2026-10-04).
- The epic AC names "UX §3.4" for the composition. §3.4 is the cookie banner; the OG composition is §3.3.2.

### Image production

UX says it was "designed once in a vector tool and exported; not runtime-generated". No design tool is available to the agent, so the asset comes from a committed generator script (static output, not a `opengraph-image.tsx` route). That keeps it reproducible for the next copy or accent change. `sharp@0.34.5` is present as Next's optional dependency (`node_modules/sharp`, `@img/sharp-win32-x64`). The script resolves it via `createRequire(require.resolve('next/package.json'))`, which adds no dependency to `apps/web/package.json`. Pango `text` input takes `fontfile`, but FreeType here does **not** read WOFF2: it was verified to fall back silently to a slab serif. A TTF is mandatory. Inter is a variable font (wght axis), so Pango `weight="800"` / `"700"` / `"400"` pick the instances.

### Testing standards

Vitest 4 + jsdom, `@/` → `src/`, tests co-located `*.test.ts(x)`. Run `pnpm --filter @warden/contracts build` before a bare `pnpm --filter web test` (4.1 Debug Log). The asset test reads the file with `fs` relative to the `apps/web` root (`process.cwd()` under vitest is `apps/web`; use `path.resolve(__dirname, '../../public/og/landing.jpg')` to be cwd-independent).

### Previous story intelligence (4.1)

- Web baseline was repaired in 4.1 (React singleton, zod `paths` pin); expected green baseline at start: **351/351**.
- `pnpm --filter web build` needs placeholder `NEXT_PUBLIC_FIREBASE_*` env to prerender `/_not-found`. That is environment, not code.
- Lane rules: do not edit `_bmad-output/sprint-status.yaml` / `deferred-work.md`; hand transitions + deferred entries to the merge.
- Manual gates go to the epic-end manual pass (memory: batch manual checks at epic end).

### Project Structure Notes

- New `src/lib/seo/` folder (siblings: `src/lib/stripe`, `src/lib/firebase`, `src/lib/pricing`): it matches the existing lib-by-concern layout.
- New `apps/web/scripts/og/`. No `scripts/` dir exists in apps/web yet; it is a dev-only tool, not part of the Next build (outside `src/`, untouched by tsc's `include`? Check `tsconfig.json` `include`. `.mjs` files are not type-checked unless `allowJs`/`checkJs`).

### References

- [Source: _bmad-output/epics-and-stories.md#Story 4.2] — ACs, dependencies (4.1)
- [Source: _bmad-output/ux-design.md#3.3.1 Open Graph metadata] — meta tags, pricing variant, dashboard noindex
- [Source: _bmad-output/ux-design.md#3.3.2 OG image design] — composition, format, ≤ 200 KB, sRGB
- [Source: _bmad-output/ux-design.md#4.2.9 Open Graph metadata] — copy table, fr_FR
- [Source: _bmad-output/prd.md — web-LANDING-002] — SSR meta for crawlers / Discord fetchers
- [Source: node_modules/next/dist/docs/01-app/03-api-reference/04-functions/generate-metadata.md] — metadataBase, openGraph, twitter, Merging
- [Source: _bmad-output/implementation-artifacts/4-1-web-token-bump-accent-hover-a11y-001-contrast-re-verify.md] — FU-3 accent, baseline, lane rules

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (claude-opus-5-5), bonus-lane worktree `Warden_monorepo-bonus` on `bonus/web-epic-4` (from `af177c3`).

### Debug Log References

- Baseline before any change: web vitest **43 files / 351 tests passed** (after `pnpm --filter @warden/contracts build`).
- Font probe: sharp/Pango with `fontfile` pointing at the vendored `inter-latin-wght-normal.woff2` rendered a **slab serif** (system fallback), with no error. FreeType here does not read WOFF2. The woff2 was decompressed to TTF with fontTools in a throwaway venv (`$CLAUDE_JOB_DIR/tmp`, not a project dependency). That TTF is the same Inter the site serves, wght axis 100–900, latin subset with é, €, ·.
- Generator: `node scripts/og/generate-landing-og.mjs --font <inter.ttf>` gives `public/og/landing.jpg` at 1200×630, **54.0 KB** (budget 200 KB). It is a progressive JPEG with 4:4:4 chroma and an lcms sRGB ICC profile in APP2. Re-running after prettier gave identical output.
- First asset-test run: the sRGB check failed because the profile's description is a UTF-16BE `mluc` tag, not ASCII. The test now matches both encodings.
- `next build` (placeholder `NEXT_PUBLIC_FIREBASE_*`, `NEXT_PUBLIC_APP_URL=https://warden.team`): green, 12/12 static pages. On `next start` + curl:
  - `/`, `/pricing` and `/auth/sign-in` all emit absolute `og:image` / `twitter:image` = `https://warden.team/og/landing.jpg`, plus width 1200, height 630, `image/jpeg`, alt, `fr_FR` and `summary_large_image`.
  - `/pricing` gets `og:url` `https://warden.team/pricing` and the pricing title.
  - `/og/landing.jpg` is served 200 `image/jpeg`.
- After all tasks: web vitest **47 files / 378 tests passed** (+27), `tsc` 0, eslint 0 errors (the 7 `_args` warnings are pre-existing, in untouched test files), prettier clean on every touched file.

### Completion Notes List

- **AC1 met.** 1200×630 JPEG with an sRGB ICC profile, 54 KB, `#FF6B00` accent. Locked by `og-asset.test.ts`.
- **AC2 met, visual sign-off pending.** Built to the UX §3.3.2 layout: `#0F0F0F` background, orange "W" mark with a `#0F0F0F` letter (the 4.1 on-accent foreground), `WARDEN` wordmark, the FR hero verbatim in sentence case on two lines, the subtitle, a `warden.team` chip, and a 10 px `#FF6B00` frame (the epic's "minimal accent border"). Inter 800/700/400/600. Uppercase hero (as drawn in UX) is a one-line change if wanted at sign-off.
- **AC3 met.** `rootMetadata` in `src/lib/seo/root-metadata.ts`, re-exported by `layout.tsx`. `metadataBase` comes from `resolveSiteUrl()`: `NEXT_PUBLIC_APP_URL`, falling back to `https://warden.team`. **Deploy note:** the production build must set `NEXT_PUBLIC_APP_URL` to the public origin. It is inlined at build time, and a `http://localhost:3000` value would ship localhost OG URLs.
- **AC4 met.** `/` and `/pricing` now build their `openGraph` through `buildOpenGraph`, so the shallow merge can no longer drop the image (verified in rendered HTML). Page `<title>` and English description untouched.
- **AC5 met.** `buildOpenGraph({ path, title?, description?, images? })` is the per-route override point.
- **AC6 met.** Dashboard layout sets `robots: { index: false, follow: false }`.
- **AC7 met.** 27 new tests: site-url 11, og 6, root-metadata 4, asset 4, landing +1, dashboard +1. The existing pricing metadata test was extended to cover url, title, locale and images.
- **AC8 pending manual.** Discord preview + X card validator need a public deployment. Held for the epic-end manual pass (Task 5.2).
- **AC9:** image + generator are in the working tree. **Not committed** (Task 3.3's "commit" waits for the user's go, as with 4.1).
- **AC10 met.** test / typecheck / lint / build green.
- No new dependency. sharp is resolved from Next's install location; fontTools lived only in a temp venv.
- **Found, not fixed** (Story 4.7 / English-copy scope): `/pricing` renders `<title>Pricing — Warden | Warden</title>`. The page title already contains "— Warden" and the root template appends `| Warden`. This predates this story.
- Lane rules honoured: `sprint-status.yaml` / `deferred-work.md` untouched. At merge, `4-2-og-image-asset-layout-meta` goes `backlog → review`.

### File List

- `apps/web/public/og/landing.jpg` (new)
- `apps/web/scripts/og/generate-landing-og.mjs` (new)
- `apps/web/src/lib/seo/site-url.ts` (new)
- `apps/web/src/lib/seo/site-url.test.ts` (new)
- `apps/web/src/lib/seo/og.ts` (new)
- `apps/web/src/lib/seo/og.test.ts` (new)
- `apps/web/src/lib/seo/root-metadata.ts` (new)
- `apps/web/src/lib/seo/root-metadata.test.ts` (new)
- `apps/web/src/app/og-asset.test.ts` (new)
- `apps/web/src/app/layout.tsx` (modified)
- `apps/web/src/app/page.tsx` (modified)
- `apps/web/src/app/page.test.tsx` (modified)
- `apps/web/src/app/pricing/page.tsx` (modified)
- `apps/web/src/app/pricing/page.test.tsx` (modified)
- `apps/web/src/app/dashboard/layout.tsx` (modified)
- `apps/web/src/app/dashboard/layout.test.tsx` (modified)
- `_bmad-output/implementation-artifacts/4-2-og-image-asset-layout-meta.md` (new)

## Change Log

- 2026-10-04 — Story created (bmad-create-story), status ready-for-dev.
- 2026-10-04 — Implemented (bmad-dev-story):
  - static OG card `public/og/landing.jpg` (54 KB) plus a reproducible generator;
  - shared `src/lib/seo` metadata, so root, `/` and `/pricing` all carry an absolute OG/Twitter image via `metadataBase`;
  - dashboard noindex;
  - 27 tests.
  
  Status → review. The Discord / X validator check and visual sign-off are held for the epic-end manual pass.
- 2026-10-04 — Code review (bmad-code-review): 2 decisions (kept 64/26 type sizes, documented; pricing X card accepted), 6 patches applied — dashboard `openGraph`/`twitter` set to `null`; `resolveSiteUrl` reduces to the origin and ignores loopback hosts in production builds; `buildOpenGraph` requires a non-empty image list; the generator checks the 200 KB budget before writing; Task 3.3 unticked (commit pending). 3 deferred to `deferred-work.md`. Web vitest 47 files / 383 tests, `tsc` 0, eslint 0 errors. Status → done; AC8 (Discord/X) still held for the epic-end manual pass, AC9 closes with the commit.
