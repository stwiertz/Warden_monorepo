---
title: "Product Brief Distillate: Warden"
type: llm-distillate
source: "_bmad-output/product-brief.md"
created: "2026-05-07"
purpose: "Token-efficient context for downstream PRD creation"
---

# Product Brief Distillate — Warden

> Companion to `_bmad-output/product-brief.md`. Captures detail that doesn't belong in a 1-2 page exec brief but is load-bearing for `bmad-create-prd`, `bmad-create-architecture`, `bmad-create-ux-design`. Bullets are theme-grouped, each self-contained. Pair with `_bmad-output/legacy/distillate/` (plan-level grain) and `docs/` (as-built grain).

## Vision & Tagline (verbatim)

- Live web hero (FR, kept verbatim per Phase-6 decision): *"Progresser plus vite en investissant moins de temps."*
- Defining-experience tagline (web): *"Subscribe from a Discord link in under 60 seconds."*
- Defining-experience tagline (mobile): *"Clip the play, say what happened, send it to the team."*
- Brand metaphor (legacy): "Double XP" — convert paid EVA After-h sessions into accelerated learning.
- Brief thesis (lifted to ExSum): **the clip is the product.**

## Personas — deep detail

### Coach Thomas, 26 (primary buyer)
- Sports / physio coaching background; 10y FPS; 2y EVA After-h; ex-COD coach.
- Reviews on PC at home in 30–60-minute evening sessions.
- Pain narrative: juggles a video player + notepad + editor; "uses ~5% of generic-tool features"; ships clips at midnight.
- Visits WardenWeb only for billing, rarely, after a Discord coupon link. Never the product surface.
- Buys for himself; pays for outcomes (team improvement) not for tools.
- Activation moment: first clip exported in < 5 minutes (event chain TBD by PRD).

### Active Player, 22 (secondary, individual subscriber)
- High-division amateur AND assistant coach for his crew. Proactive analyst archetype.
- Subscribes individually (no team billing in V1).
- **PERSONA NAME DISCREPANCY** — legacy web doc names this archetype "Lucas, 22"; legacy mobile doc names same archetype "Maxime, 22". Phase-6 decision required to canonicalize.

### Passive Player Lucas, 17 (secondary, conversion target)
- Reflexes excellent; game-vision weak.
- Receives clips from his coach via Discord; never installs the app.
- Web-landing conversion target: passive → active → subscriber funnel.
- Implication: every shipped MP4 is a branded touchpoint to this archetype — opportunity reviewer flagged subtle attribution / "made with Warden" deeplink in share-sheet as a near-zero-cost growth instrument (out of brief scope; PRD optional).

## Demand evidence

- **Confirmed**: FR/BE EVA After-h community fields **300+ active teams**, each self-coached or with a dedicated coach. Addressable beachhead ≈ 300+ buyers.
- **Confirmed**: word-of-mouth is the dominant acquisition channel in this community.
- **Implied math**: legacy 12-month target (100 subs) ≈ 33% beachhead penetration; 3-month (20) ≈ 7%.
- **NOT YET CAPTURED** (PRD must source from community): coach-interview count, willingness-to-pay test results, waitlist or pre-order signal, exact Discord-server reach for coupon-link channel.

## Pricing — full detail

- Canonical (live on web, matches `apps/web/src/lib/pricing/plans.ts`): **€7.99/mo** or **€79.90/yr** (~17% annual savings).
- Web copy under price: *"économisez 2 mois"* (yearly = 12 × €7.99 = €95.88 list, ~10 months effective).
- Checkout reassurance copy (deferred-billing): *"Vous ne serez pas débité avant le [date]"* — load-bearing UX moment.
- Currency: EUR; FR/BE focus.
- **DRIFT TO RECONCILE**: mobile legacy docs reference €7/mo in places — €7.99 is canonical.
- V1 coupon admin happens via Stripe Dashboard only (no custom UI). Free-month coupons issued to local-league winners as the primary growth lever ("dealer of comfort").
- Open decision #12 (surfaced by brief, not from `docs/index.md`): €7.99 sits below the $10–$30 band that adjacent B2C amateur subscriptions cluster in. Deliberate FR/BE niche price OR under-monetized?

## Web funnel — event taxonomy

- `Visit` → `CheckoutStart`
- `CheckoutStart` → `CheckoutComplete`
- `Coupon → Retained` ≥ 10% post-trial (key retention metric)
- Tracked via Firebase Analytics (legacy strategy).

## Cross-surface contracts — technical detail

### `users/{uid}` Firestore doc
- Web writes (Stripe webhook), mobile reads. Server-only via firebase-admin; `firestore.rules` denies client writes.
- Web canonical shape: `{ status ∈ active|past_due|canceled, plan ∈ monthly|yearly, current_period_end, stripe_customer_id, stripe_subscription_id, created_at, updated_at }`.
- Legacy mobile reads `isPaid: boolean`. Mobile auth-store offline-fallback path **still reads `isPaid`** — Phase-6 decision #1 directly drives the offline-entitlement story.
- Contract `contracts/user-doc.schema.json` keeps **both halves** with `additionalProperties: true` — explicitly loose to tolerate the duplication during Phase 6.
- `apps/web` does NOT yet import `@warden/contracts/user-doc` — redeclares own schema at `apps/web/src/lib/schemas/subscription.ts` (Phase-6 decision #6).

### `map_config.json` pipeline
- Generator: apps/tooling Python CLI (`map_config_generator`).
- Validator (TS, strict): `contracts/map-config.schema.json`, `additionalProperties: false`. Auto-generated Zod via `packages/contracts/scripts/generate-zod.mjs` (banner: "AUTO-GENERATED — do not edit").
- Validator (Python, documented intent): `jsonschema` per pyproject.toml deps; runtime assertion-in-code is a Phase-6 confirmation item.
- Consumer: apps/mobile.
- Runtime delivery (today): Firestore-fetched at `detection_config/latest`; MMKV cached as `detection.config`; stale-while-revalidate gated by `version` field; three singleflight paths (initial / background / forced).
- Bootstrap error disambiguation: `OfflineFirstLaunchError` vs `MalformedRemoteConfigError` for distinct UX copy.
- **Map count discrepancy**: legacy distillate / docs say 14 EVA maps; user flagged 14-vs-15 as the Phase-6 reconciliation item (#10). Surfaces as "unknown map" fallthroughs at activation.

### Shared Firebase project
- Apparent yes (mobile + web) from env conventions; not asserted in code today. Phase-6 decision #3: assert + CI-check.
- Region pinned: **europe-west** (GDPR).

## Web — technical context

- Stack: Next.js 16.2.2, React 19.2, Tailwind 4, shadcn/ui, Firebase 12 client + admin 13, Stripe 22, Zod 4, Vitest. All `runtime = 'nodejs'`.
- 7 HTTP route handlers (auth, checkout, subscription, portal, webhooks). See `docs/api-contracts-web.md` for shapes.
- Stripe webhook flow:
  - Signature-verified.
  - Idempotency table at `stripe_events/{event.id}`; created in **same transaction** as dedupe check.
  - Required Checkout Session metadata: `firebase_uid` + `plan_id ∈ {monthly, yearly}`.
  - Routing failures return **200** to stop Stripe retries.
  - Transient-error retry policy: `[250, 750, 2250]` ms.
- Auth/session flow:
  - Firebase ID token traded server-side for **httpOnly session cookie** via `POST /api/auth/session`.
  - Cookie: `sameSite=lax`, 7-day max age, `secure` in prod.
  - Helpers: `requireSession`, `withAuth`, `UnauthorizedError`.
  - Error codes: `NO_SESSION`, `SESSION_EXPIRED`, `SESSION_REVOKED`, `UNAUTHORIZED`.
- Test invariant (load-bearing): `import * as self from './webhooks'` self-namespace pattern is required for `vi.spyOn` to work (Stories 4.2 / 4.3). Direct calls bypass spies due to ESM local-binding resolution. **Do not refactor away.**
- Surfaces: marketing landing, `apps/dashboard` with `SubscriptionCard` + Stripe Customer Portal CTA, sign-in.
- Brownfield: Stripe API version pin `2026-03-25.dahlia` vs installed `@stripe` types wanting `2026-04-22.dahlia` — multiple `*.test.ts` carry spread / implicit-any errors. Pre-existing, not migration-introduced.

## Mobile — technical context

- Stack: Expo SDK 54, RN 0.81, React 19.1, Firebase 12, NativeWind 4, Zustand 5, FFmpeg-kit, expo-sqlite, MMKV.
- Persistence: SQLite (sessions, segments, clips, audio — 4 tables) + MMKV (auth, prefs, processing checkpoints, detection-config cache).
- Entry: `App.tsx` → `RootNavigator.tsx` (auth-gated).
- **OpenCV JSI binding is a stub today** — `loadFrameFromPath` throws; tests inject synthetic `FrameLoader`s. Detection pipeline wired end-to-end only via injection. **The V1 load-bearing milestone is shipping the JSI binding.**
- FFmpeg-kit is wired and working.
- pHash matcher is pure TS.
- Auth-store rehydration partial: `{ user, isAuthenticated, cachedAt }` — **30-day TTL** on auth cache (NOT a 30-day general offline cache; brief uses precise term "offline auth-cache").
- Network-failure fallback path reads `useAuthStore.user.isPaid` — depends on Phase-6 decision #1 resolution.
- Voice annotation: feature `audio-commentary/`, model `AudioComment { ..., slot, ... }`. 30s clip + 3-slot semantics (before/during/after) come from legacy planning; not visibly asserted in as-built docs (PRD should lock).
- Validated build: `pnpm --filter mobile exec expo export --platform android` produces 5.22 MB Hermes bundle (Phase 4 acceptance test).
- Brownfield: `apps/mobile/src/features/auth/firebaseConfig.ts` imports `getReactNativePersistence` from `firebase/auth` — removed/relocated in Firebase v12. Forcing-function deprecation; future minor may drop the symbol entirely. Phase-6 decision #5.

## Tooling — technical context

- Stack: Python ≥3.11, OpenCV, NumPy, imagehash, FFmpeg subprocess, questionary TUI, pytest. uv-managed.
- Workspace package name: `tooling`.
- Entry: `apps/tooling/wardentooling.py` (TUI launcher); also direct invocation per tool.
- Five user-facing tools: `game_detector`, `frame_labeler`, `map_config_generator`, `hash_validator`, `warden_analyzer`.
- Output artifact: `map_config.json` per `contracts/map-config.schema.json`.
- Pre-merge implementation-artifacts at `_bmad-output/legacy/tooling/` (32 specs) — Phase-6 triage required: which become legacy reference, which inform unified architecture, which become future stories.
- ROI/HSV/saturation tuning + round-state semantics in current detector pipeline are **EVA-specific** — new titles need detector tuning, not pure config swap (bounded moat).

## Repo / build / monorepo invariants

- pnpm workspaces + Turborepo (TS) + uv workspace (Python).
- Workspace package names: `mobile`, `web`, `tooling`, `@warden/contracts`, `@warden/tsconfig`, `@warden/eslint-config`.
- `.npmrc` `node-linker=hoisted` is **REQUIRED** — Metro's `disableHierarchicalLookup` cannot traverse pnpm's nested `.pnpm/` store. Do not change without re-validating Expo bundling.
- `packages/contracts/src/index.ts` uses bare imports (no `.js` extensions) — Metro can't do TS-ESM `.js→.ts` mapping.
- Hoisted root configs: `.husky/`, `commitlint.config.ts`, `.prettierrc` (`endOfLine: auto`), `.prettierignore` (excludes `apps/mobile/` until modernized; `apps/tooling/` is Python).
- Codegen command (TS Zod from JSON Schema): `pnpm --filter @warden/contracts build` regenerates `src/generated/*.ts`.
- Node ≥ 20; pnpm 9.12.0.
- BMad install at `_bmad/`; output at `_bmad-output/`.

## V1 MVP — granular scope (mobile, beyond brief)

In:
- Auto-slicing (subsumes JSI binding ship + map detection accuracy floor + round-boundary detection accuracy floor — bars TBD by PRD).
- Card View + sorting.
- Cinema Mode.
- 3-mode view toggle.
- 30-second clip + 3-slot voice (before / during / after).
- Mobile/HD export + standalone MP4.
- OS share sheet.
- Auto-save + crash recovery.
- Firebase auth + entitlement validation + 30-day offline auth-cache.
- French UI (locked).

Out (V1):
- OCR scores/kills.
- Advanced ROI composition.
- Vertical export.
- Custom ROI templates.
- Review import mode.
- Pick & Ban tool.
- iOS (Phase 2).
- Multi-view clip export.
- Export queue.
- Discord stream group review (Desktop / Phase 3).

## V1 MVP — granular scope (web)

In:
- Stripe Checkout with deferred-billing copy.
- Stripe Customer Portal for history/upgrade/cancel.
- Webhook-driven `users/{uid}` writes (server-only).
- Marketing landing optimized for Discord coupon entry.
- English UI with French hero.
- Firebase Analytics for funnel.
- Revised Epic 5 (legacy): portal-first dashboard via Stripe Customer Portal — no custom UI.

Out (V1):
- Discord OAuth.
- Custom Coupon Admin UI.
- Custom analytics dashboard.
- Team / group billing.
- Full French web localization.
- Self-serve account deletion.
- Churn survey.
- In-dashboard coupon redemption.

## V2 deferred (with rationale)

- **Discord OAuth** — community already lives on Discord; native auth is V2 friction-reducer once core funnel works.
- **Coupon Admin UI** — V1 admin-via-Stripe-dashboard suffices; custom UI scales when coupon volume grows.
- **Custom analytics dashboard** — V1 reads Firebase Analytics directly; custom dashboard once metrics stabilize.
- **Team / group billing** — V1 is individual-only; team SKU lands when first amateur orgs ask.
- **Full French web localization** — V1 ships English UI with French hero; full FR localization once funnel data validates the channel.

## V3 deferred (with rationale)

- **Broader tactical-FPS expansion** (CS2 / Valorant / R6) — config + per-title detector tuning; needs the EVA After-h beachhead to validate the pipeline first.
- **Referrals** — once WoM is instrumented and quantified.
- **iOS** — Android-first per FR/BE coach hardware skew; iOS post-Phase-2.
- **Desktop / Discord stream group review** — multi-coach live-review surface; Phase-3.
- **Multi-view clip export, export queue** — power-user features post-MVP.

## Rejected for V1 (with rationale, per legacy strategy)

- **Discord OAuth** — Discord owns social. Anti-pattern to compete; V1 stays Google/Email auth.
- **In-app social features** — clips ship via Discord. Distribution is the product; do not rebuild Discord.
- **Custom coupon admin UI** — V1 uses Stripe Dashboard for coupon admin. Out of scope.
- **Custom analytics dashboard** — V1 uses Firebase Analytics direct.
- **Self-serve account deletion** — manual via support in V1.
- **Churn survey** — V2 once retention data is meaningful.

## Competitive intelligence — full detail

### Direct / adjacent
- **Mobalytics** — all-in-one cloud companion, GPI scoring, Mobalytics Plus subscription, Overwolf desktop overlay. **Gaps**: web/desktop-first (no on-device mobile video); declining performance reputation (RAM spikes, crashes, ad creep on free tier); cloud-based — no privacy story.
- **Leetify** — CS2/CS:GO replay analysis, server-side demo parsing, deepest tactical-FPS performance tool. **Gaps**: single-game; demo-file pipeline (not phone video); web-centric; no mobile experience; no map-zone configurability.
- **Blitz.gg** — lightweight desktop overlay across LoL/Valorant/CS2/Apex/Fortnite. **Gaps**: overlay only, not coaching/replay; no video; desktop-bound; no mobile coaching surface.
- **Insights.gg** — cloud video review + auto-highlight for streamers/teams. **Gaps**: cloud-upload (privacy + bandwidth); coach/creator-oriented, not solo amateur; no on-device option.
- **Onform / CoachNow / Sprongo / VueMotion** — mobile sports video analysis (AI skeleton, slow-mo, side-by-side) for traditional sports. **Gaps**: built for physical sports (golf swing, jump shot), not screen-recorded gameplay; mostly cloud-sync; no esports semantics; no game-specific tactical overlays.

### Sentiment signals
- Incumbents (Mobalytics, Porofessor, Blitz) perceived as losing innovation momentum.
- Mobalytics-specific: RAM spikes, crashes, ad creep on free tier.
- Free tiers are widely "enough to make a difference" — high free-tier expectation bar.
- Privacy-respecting on-device tools (e.g. My Jump Lab in adjacent sports) explicitly praised — "no login, works offline, data stays on device" — validates Warden's on-device angle.
- Coach/creator cloud tools (Insights.gg, CoachNow) seen as overkill for solo amateurs.

### Market context (numerical)
- Esports coaching market ~$2.8B in 2025 → ~$3.2B in 2026 → ~$9.6B by 2034 (CAGR ~14.7%).
- **Caveat (skeptic-flagged)**: figure is *category-level esports coaching* (mostly human coaches). The *coaching software / tooling* slice is materially smaller.
- Source examples (web research): Marketintelo, Growth Market Reports, The Business Research Company, ACM live-companion-tools paper.
- 2026 named pivotal shifts: subscription-based coaching revenue, AI-powered analytics integration.
- B2C amateur acquisition subscription band: $10–$30/mo dominant. **Warden anchors below this band at €7.99** (decision #12).
- Tactical-FPS map-zone games (CS2, Valorant, R6) have most established replay-analysis spend and clearest "discrete maps + zones" pattern matching `map_config.json`.

## Risks — full inventory (8 in brief, more flagged)

In brief Risks section:
1. **Game-publisher ToS** — EVA-specific not yet researched; PRD owns mitigation.
2. **On-device perf ceiling** — pre-PRD spike; architecture's first task; reference-device floor + graceful-degradation path required. *Note: NPUs accelerate ML models, not FFmpeg/CV/pHash CPU work.*
3. **Free-tier expectation bar** — adjacent companion apps condition users to expect generous free tiers; PRD must make free→paid line narrative-explicit.
4. **Brownfield triage backlog** — Stripe pin drift, Firebase v12 deprecation (forcing function), users/{uid} schema duplication.
5. **Auto-slicing accuracy ceiling** — false-positive round detection ships broken clips at activation moment. No quality threshold or HITL fallback in V1 scope.
6. **Voice + GDPR** — voice annotations exported with MP4s travel through Discord; biometric-adjacent. Controller/processor obligation chain. PRD names data-protection posture.
7. **Discord as distribution rail** — third-party dependency; ToS changes, server bans, API throttling on coupon links.
8. **Maintenance surface concentration** — three apps + Python tooling + Stripe webhooks + Firestore rules + Expo build matrix maintained as "one product"; sprint planning may discover four.

Skeptic-surfaced (subset folded into the 8 above; remainder for PRD discretion):
- Apple/Google **Reader-App enforcement tightening** (post-Epic, post-DMA): a 2026 policy shift on external-purchase links or login-only-no-IAP could break the entire monetization seam. **High severity** — explicitly worth promoting if not already implied by Risk #4.
- Single-codebase concentration risk (folded into Risk #8).
- Language-split conversion friction (FR Discord → FR hero → EN checkout copy → FR app) — no test data showing FR/BE conversion through partial-English Stripe Checkout at the rate the 3-month MRR target requires.
- Discord-channel ceiling — coupon-link channel may be bounded by Stephane's personal Discord network; supply ceiling could cap MRR before V2 work begins.

## Open Phase-6 Decisions — full text + dependencies

1. **`users/{uid}` schema** — drop legacy `isPaid` vs. formalize as denormalized convenience derived from `status`. **Load-bearing**: mobile offline-fallback path reads `isPaid`; resolution rewrites that path.
2. **`map_config.json` runtime delivery** — Firestore-fetched (current via `detection_config/latest`) vs bundle as immutable Metro asset. **Load-bearing tension**: Firestore preserves V3 "ship new maps without an app release" but means detector params round-trip through cloud (video doesn't, config does). Metro-bundled fully closes the device but new maps need an OTA / app release. One choice will dim one of the two moats.
3. **Same Firebase project for web + mobile?** Apparent yes from env conventions; not asserted in code. CI-check + assert in unified architecture. **Load-bearing**: brief's "one product in code" claim hinges on this.
4. **Stripe API version pin** (`2026-03-25.dahlia`) vs installed types (`2026-04-22.dahlia`) — bump or freeze.
5. **Mobile auth migration** to `@react-native-firebase/*` — escapes `getReactNativePersistence` deprecation. **Forcing function**: future Firebase v12 minor may drop the symbol; deferring may pull migration into V1 unscheduled.
6. **Wire `apps/web` to `@warden/contracts/user-doc`** — replace redeclared `apps/web/src/lib/schemas/subscription.ts`. Single-source-of-truth issue.
7. **`firestore.rules` coverage** for `detection_config/*` and `stripe_events/*` — explicit rules. Entitlement leg is enforced; surrounding Firestore surface is partially un-ruled.
8. **Ownership of `detection_config/latest`** — manual / out-of-band vs wire to web-admin / tooling-emit.
9. **`status` enum scope** — does mobile need `trialing` if web never writes it but Stripe might?
10. **14 vs 15 maps reconciliation** across `config/config.yaml`, `map_config.json`, legacy distillate. **Activation-path adjacent**: unreconciled list surfaces as "unknown map" fallthroughs in the activation flow.
11. **In-flight mobile Sprint 2.5 stories** — finish as legacy work in monorepo then start unified Sprint 3 vs roll into unified sprint. Timeline-binding for `bmad-sprint-planning`.
12. **Pricing positioning** (surfaced by brief, not docs/index.md) — €7.99/mo below the $10–$30 band of adjacent B2C amateur subscriptions. Deliberate FR/BE niche price or under-monetized?

## Brownfield specifics (verbatim)

- **Stripe API version drift**: `apps/web/src/lib/stripe/server.ts` pins `"2026-03-25.dahlia"` but installed `@stripe` types want `"2026-04-22.dahlia"`. Multiple `*.test.ts` have spread-argument and implicit-any errors. **Pre-existing, NOT migration-introduced.**
- **Firebase v12 mobile**: `apps/mobile/src/features/auth/firebaseConfig.ts` imports `getReactNativePersistence` from `firebase/auth` — removed/relocated in Firebase v12. **Pre-existing.**
- Both above: do not fix without coordinating with the unified architecture decisions.

## Source provenance

Brief drew from three explicitly-curated inputs (tight scope by user choice):
1. `_bmad-output/legacy/distillate/01-product-strategy.md` — plan-level product strategy distillate from three legacy PRDs (mobile FR, web EN, tooling).
2. `docs/project-overview.md` — as-built Phase-5b monorepo overview.
3. `docs/integration-architecture.md` — cross-part wiring + open Phase-6 decisions.
4. `docs/index.md` (open-decisions section only) — canonical 11-item list.

Other source surfaces available to downstream agents (not pulled into brief):
- `_bmad-output/legacy/distillate/{02-mobile, 03-web, 04-tooling, 05-architecture-cross-cutting, 06-ux-design, 07-epics-and-sprint-state, 08-open-questions-and-risks}.md`
- `_bmad-output/legacy/_intermediates/{g1..g5}.md` — fan-out distillates with deeper detail (audit trail / fallback).
- `_bmad-output/legacy/{mobile, web, tooling}/` — pre-merge planning artifacts per legacy repo.
- `docs/{architecture-mobile, architecture-web, architecture-tooling, architecture-shared}.md`
- `docs/{data-models-mobile, data-models-web, data-models-shared}.md`
- `docs/{api-contracts-web, component-inventory-mobile, component-inventory-web, development-guide, deployment-guide}.md`
- `apps/web/AGENTS.md` — "This is NOT the Next.js you know."

## Glossary / terms

- **EVA After-h** — competitive VR FPS; FR/BE community. Warden's V1 beachhead.
- **Reader-App architecture** — Apple/Google policy precedent (Netflix-style): app contains zero monetization surface, login-only; subscription unlocks sourced externally. Bypasses 30% store fees but forbids in-app pricing display.
- **Discord-native, viral-by-artifact** — distribution loop where the product output (annotated MP4) is the share unit; recipients consume without installing.
- **Double XP** — internal product metaphor: paid EVA After-h sessions accelerated via fast voice-annotated minimap clips that recipients view inline.
- **Coupon → Retained** — funnel metric: free-month coupon recipients who convert to paid retention post-trial. Target ≥ 10%.
- **dealer of comfort** — internal metaphor for free-month coupons issued to local-league winners as growth lever.
- **JSI binding** — JavaScript Interface binding for OpenCV inside React Native; load-bearing V1 milestone (currently a tested-via-injection stub).
- **singleflight** — concurrency pattern in detection-config fetch: ensures only one in-flight load at a time across initial / background / forced paths.

## Confidence calibration

- **High**: cross-surface contracts (technical detail), Stripe webhook flow, persona archetypes, V1 scope, pricing, brownfield specifics, the 11 open decisions canonical from `docs/index.md`.
- **Medium**: legacy success metrics (300+ teams confirms beachhead size; targets themselves are reference-only per brief framing), market TAM (category-level), competitor gaps (web research is light).
- **Low / unverified**: shared Firebase project assertion, Python jsonschema runtime validation, EVA publisher ToS posture, on-device perf reference-device floor, coach-interview count and WTP signal — all parked for PRD / architecture sourcing.
