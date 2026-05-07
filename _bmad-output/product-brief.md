---
title: "Product Brief: Warden"
status: "complete"
created: "2026-05-07"
updated: "2026-05-07"
inputs:
  - _bmad-output/legacy/distillate/01-product-strategy.md
  - docs/project-overview.md
  - docs/integration-architecture.md
  - docs/index.md (open-decisions section only)
---

# Product Brief: Warden

> *"Progresser plus vite en investissant moins de temps."* — live web hero

## Executive Summary

Warden is a coaching companion for competitive players. The thesis is simple: **the clip is the product.** A post-match phone recording becomes a sharable, voice-annotated tactical clip in under five minutes — entirely on-device, with no upload, no cloud-vision tax, and no friction between the player who recorded the round and the coach who reviews it on Discord that night.

The product is one thing across three surfaces. **A mobile app** does the work — auto-slicing, minimap-aware ROI detection, three-mode video review, three-slot voice annotation, and standalone MP4 export — built natively for phones because that is where the footage lives. **A web subscription portal** does the monetization — a Stripe-driven door that paid coaches walk through once for purchase (in under sixty seconds, from a Discord coupon link), returning only for billing self-service via Stripe Customer Portal. **A Python tooling CLI** does the lab work — generating the per-game `map_config.json` that gives the mobile app its tactical eye, and the architecture meant to let Warden expand: new maps as configs, new titles as configs plus per-title detector tuning.

Two structural commitments shape every downstream decision: the mobile app is **login-screen-only with zero monetization surface** (Reader-App model — bypasses 30% store fees, forbids in-app pricing), and **all video processing is on-device by design** (privacy, offline, structurally lower marginal cost vs. cloud-pipeline incumbents whose unit economics worsen with every uploaded match — the **OpenCV JSI binding is the load-bearing V1 milestone**, currently a tested-via-injection stub). V1 lands as the unified Phase-6 BMad chain (PRD → architecture → UX → epics/stories) and Phase-7 sprint complete.

## The Problem

Competitive amateur and semi-pro players generate hours of high-stakes gameplay every week and have nowhere good to debrief it. The tools that exist split badly:

- **Cloud video platforms** (Insights.gg, CoachNow) require uploading every match. Bandwidth, privacy, and latency punish the casual reviewer.
- **Desktop overlays** (Mobalytics, Blitz, Porofessor) sit next to the game, not next to the footage. They show stats, not tactical narrative.
- **Generic video editors** are designed for content creators, not coaches. A part-time coach uses ~5% of the features and pays for the other 95%.
- **Replay analysis platforms** (Leetify) parse server-side demo files for one specific game. They don't help anyone whose title doesn't expose demo files.

The concrete user is **Thomas, 26, a part-time esports coach** who records his evening reviews on a phone, opens the laptop, juggles a video player and a notepad and an editor, and ships clips to his team's Discord at midnight. He wants the editor *out* of the loop. He wants the phone to do the boring 80% — find the rounds, clip them, let him say what happened, push them to Discord.

For Thomas, the cost of the status quo is not money — it's the hour he spends per session that should have been spent coaching.

**Demand signal.** The FR/BE EVA After-h community currently fields **300+ active teams**, each either self-coached or with a dedicated coach — yielding an addressable beachhead of approximately 300+ individual buyers. Against this base, the legacy 12-month target (100 subscribers) implies ~33% penetration; the 3-month target (20) implies ~7%. **Word-of-mouth is the dominant acquisition channel in this community** — which both increases the realism of these penetration targets and validates Warden's Discord-native distribution and Coupon → Retained funnel as on-pattern with how the audience already moves information. *Interview count, waitlist depth, and explicit willingness-to-pay validation are not yet captured — `bmad-create-prd` should source these directly from the community before re-baselining the targets.*

## The Solution

A three-surface product anchored on a single insight: **the clip is the product, and the phone is enough**.

- **Mobile (Expo / React Native, Firebase auth, fully French UI):** record or import gameplay footage, auto-slice into rounds via on-device map detection (FFmpeg + OpenCV via JSI + perceptual hashing), review in Card View / Cinema Mode / 3-mode toggle, attach up to three voice annotations per clip (before/during/after), export Mobile or HD MP4, ship via OS share sheet. Crash-recovery and auto-save baked in. No IAP, no plan picker, no pricing in the binary.

- **Web (Next.js 16, English UI with French hero, Stripe + Firebase):** marketing landing optimized for the Discord-link conversion flow, Stripe Checkout with deferred-billing reassurance ("*Vous ne serez pas débité avant le [date]*"), Stripe Customer Portal for history/upgrade/cancel, server-only Firestore writes to `users/{uid}` on Stripe webhooks. Pricing is **€7.99/mo or €79.90/yr** (~17% annual savings, "économisez 2 mois").

- **Tooling (Python ≥3.11 CLI, joins the workspace via uv):** five user-facing tools — game_detector, frame_labeler, map_config_generator, hash_validator, warden_analyzer — emit a single shared artifact, `map_config.json`, validated cross-language by `contracts/map-config.schema.json` (TypeScript via auto-generated Zod; Python validation via `jsonschema` is the documented intent — assertion-in-code is a Phase-6 architecture confirmation).

The three surfaces are **designed to bind** via two cross-language contracts and one shared Firebase project. Today, `map-config.schema.json` is enforced strictly (`additionalProperties: false`); `user-doc.schema.json` is intentionally loose (`additionalProperties: true`) and not yet imported by `apps/web` — Phase-6 decisions #1, #3, and #6 below close the remaining gaps and elevate this from architectural intent to architectural assertion.

## What Makes This Different

1. **Empty-niche positioning — with a defensibility clock.** Web research surfaced no direct competitor doing on-device mobile video analysis for esports. Cloud pipelines exist (Insights.gg, Leetify); desktop overlays exist (Mobalytics, Blitz); physical-sports-on-mobile exists (Onform, CoachNow). Phone-records-gameplay-and-phone-analyzes-it is open. The defensibility clock isn't *"no one will copy us"* — it's *"a fast-follower must rebuild the on-device video pipeline (FFmpeg + OpenCV-JSI + pHash), the cross-language schema-driven config pipeline, and the Discord-native distribution flywheel before V1 has 100 subscribers."* Warden's lead time is the asset.

2. **Reader-App architecture as moat.** Mobile is intentionally login-only — bypassing 30% store fees while keeping the paid product price-competitive. This is not an accident of phasing; it is a structural choice that propagates into every decision (no IAP, web-Stripe-unlock, Firestore-mediated entitlement, 30-day offline auth-cache). The entitlement leg of the model is asserted in code today (server-only `users/{uid}` writes via firebase-admin, `firestore.rules` denies client writes); decisions #1 and #9 close the remaining schema-side gaps. **Entitlement states** — *paid, lapsed, offline-grace (≤ 30d), payment-failed, multi-device, signed-out* — are the most leveraged piece of cross-surface logic; transition semantics owned by `bmad-create-architecture`.

3. **On-device privacy + structurally lower marginal cost.** No video leaves the phone. The on-device pipeline (CPU-bound — FFmpeg, OpenCV via JSI, pHash) carries zero per-match infrastructure cost; fixed costs (Firebase reads/writes, Stripe %) scale linearly with paying users, not with footage volume. Cloud-pipeline competitors absorb per-match storage + GPU-vision cost on every uploaded clip — at €7.99/mo their margin compresses with every active session; Warden's does not.

4. **Discord-native, viral-by-artifact distribution.** The output of a coaching session is a sharable MP4 that a non-installer can watch inline. Recipients do not need the app. Distribution is the product, and every shipped clip is a branded touchpoint to the next archetype (Passive Player Lucas — see below).

5. **Tooling as expansion moat — bounded.** `map_config.json` plus the Python CLI means new **maps** roll out as configs, not code releases. New **games** require config *plus* per-title detector tuning (HSV thresholds, saturation rules, and round-state semantics are EVA-specific in today's pipeline). The lever is real but bounded: maps are config-only; titles are config + a focused engineering task — still materially cheaper than the per-title cloud pipelines competitors hand-build.

## Who This Serves

**Primary — Coach Thomas, 26.** Part-time esports coach with 10 years of FPS / 2 years of EVA After-h experience, often a former competitive player turned mentor. Reviews on PC at home in 30–60-minute evening sessions. Visits the web portal only to subscribe — billing rarely, never the product. Buys for himself; pays for outcomes (his team's improvement) not for tools. Activation moment: first clip exported in under five minutes.

**Secondary A — Active Player, 22.** High-division amateur who also doubles as an assistant coach for his crew. Subscribes individually. Wants to self-review without waiting for a coach. (*Note: a Phase-6 decision will canonicalize the persona name — legacy web docs say "Lucas, 22"; legacy mobile docs say "Maxime, 22" — same archetype.*)

**Secondary B — Passive Player Lucas, 17.** Reflexes great, game-vision weak, receives clips from his coach via Discord. Never installs the app. The conversion target of the web landing — passive → active → subscriber funnel.

## Success Criteria

**Reference targets — not bound.** The legacy product strategy authored the following targets when the three surfaces were planned as three independent products under separate P&Ls. Carried forward verbatim as a starting position; **`bmad-create-prd` should re-baseline rather than inherit them as commitments**:

- **3-month:** 20 paying coaches, **140 € MRR**, churn < 15%
- **12-month:** 100 subscribers, **700 € MRR**, churn < 10%
- **Activation:** first clip exported in < 5 minutes (*activation event chain — start, end, telemetry path under on-device-only constraints — to be defined by `bmad-create-prd`*)
- **Engagement:** ≥ 1 review session per week per coach; 3–5 clips per review at launch, climbing to 5+ at maturity
- **Web funnel:** Visit → CheckoutStart → CheckoutComplete; Coupon → Retained (≥ 10% post-trial)

## Scope

**V1 — in (mobile):** auto-slicing via on-device map detection — *subsumes the OpenCV JSI binding (currently a tested-via-injection stub) and accuracy floors for map detection + round-boundary detection, both to be set by `bmad-create-prd`*; Card View + sorting; Cinema Mode; 3-mode view toggle; 30-second clip + 3-slot voice (before/during/after); Mobile/HD export + standalone MP4; OS share; auto-save + crash recovery; Firebase auth + entitlement validation + 30-day offline auth-cache; French UI.

**V1 — in (web):** Stripe Checkout with deferred-billing copy; Stripe Customer Portal for history/upgrade/cancel; webhook-driven `users/{uid}` writes (server-only); marketing landing optimized for Discord coupon entry; English UI with French hero copy; Firebase Analytics for funnel tracking.

**V1 — in (tooling):** five-tool Python CLI emitting `map_config.json`; cross-language schema validation via `contracts/`.

**V1 — out (deferred to V2/V3 per legacy strategy):** Discord OAuth, custom coupon admin UI, custom analytics dashboard, team / group billing, full French web localization (currently English with French hero), self-serve account deletion, churn survey, in-dashboard coupon redemption, OCR scores/kills, advanced ROI composition, vertical export, custom ROI templates, review import mode, Pick & Ban tool, iOS (Phase 2), multi-view clip export, export queue, Discord stream group review (Desktop / Phase 3).

## Vision (V2 / V3)

Warden's V1 is **laser-focused on EVA After-h, FR/BE community, Discord-native distribution** — disciplined scope keeps the brief honest. The architectural moat (on-device + `map_config.json` + Python CLI) is built for a longer arc:

- **V2:** Discord OAuth, coupon admin UI, custom analytics dashboard, team / group billing — the "build the business around the existing audience" phase.
- **V3:** broader **tactical-FPS coaching companion** — additional titles (CS2, Valorant, R6) added by `map_config.json` *plus* per-title detector tuning (not pure config swap), referrals, full French localization, iOS / Desktop, Discord stream group review.

The V3 arc is where the tooling moat compounds, and where the web research saw real market headroom — *category-level* esports coaching is ~$2.8B in 2025 → ~$9.6B by 2034 (CAGR ~14.7% per industry research); the *coaching software / tooling* slice Warden actually plays in is materially smaller and more honest as a TAM than the headline figure, but the underlying buyer segment (amateur / semi-competitive) is the largest by volume and the named B2C beachhead.

## Risks & Open Questions

The web research, the brownfield triage, and the review panel surfaced eight risk classes the unified PRD and architecture must engage with explicitly:

1. **Game-publisher ToS risk.** Screen-recording and overlaying competitive titles has historically tightened across publishers (Riot, Valve, Ubisoft). EVA-specific policy is not yet researched. Mitigation must live in the unified PRD.
2. **On-device performance ceiling.** Real-time map detection + FFmpeg + perceptual hashing on mid / low-end Android phones is the make-or-break UX risk. Cloud incumbents have a perceived-accuracy advantage on weak hardware. **Treated as a pre-PRD spike — `bmad-create-architecture`'s first task is to bind a reference-device floor and a graceful-degradation path with measured numbers.** *(Note: NPUs accelerate ML-style models; FFmpeg + OpenCV-CV + pHash are largely CPU work — the brief makes no NPU-acceleration claim.)*
3. **Free-tier expectations.** Adjacent companion apps (Mobalytics, Blitz) condition users to expect generous free tiers. Warden's mobile app is fully usable without subscription except for paid-feature gating — the brief asserts this is sufficient, but the PRD should make the free → paid line narrative-explicit.
4. **Brownfield triage backlog.** Three pre-existing issues (Stripe API version pin drift, Firebase v12 `getReactNativePersistence` removal in mobile — a forcing-function deprecation, `users/{uid}` schema duplication) are parked in the open-decisions list below. None are blockers; all must be resolved by `bmad-create-architecture`.
5. **Auto-slicing accuracy ceiling.** False-positive round detection ships broken clips at the activation moment. There is no quality threshold or human-in-the-loop fallback in V1 scope — the PRD must set an accuracy bar and define what happens below it.
6. **Voice + GDPR exposure.** Voice annotations exported with MP4s travel through Discord; voice clips are personal data adjacent to biometric and create a controller/processor obligation chain. PRD must name the data-protection posture explicitly (consent, retention, export rights).
7. **Discord as a distribution rail.** Discord is a third-party dependency outside Warden's control — ToS changes, server bans, or API throttling on coupon links are single-point-of-failure exposures the moat narrative would otherwise ignore.
8. **Maintenance surface concentration.** Three apps + Python tooling + Stripe webhooks + Firestore rules + Expo build matrix — all maintained as "one product." The brief treats it as one; sprint planning may discover four. Warrants explicit maintenance-budget thinking in `bmad-sprint-planning`.

## Open Phase-6 Decisions

These are **not pre-decided in this brief** — they are surfaced for resolution by the unified BMad agent chain (`bmad-create-prd`, `bmad-create-architecture`, `bmad-create-ux-design`). Eleven canonical from `docs/index.md` plus a twelfth surfaced by this brief:

1. **`users/{uid}` schema duplication** — drop legacy `isPaid`, or formalize as denormalized convenience derived from `status`?
2. **`map_config.json` runtime delivery** — keep Firestore-fetched (current via `detection_config/latest`), or bundle as immutable Metro asset? *Note: this decision is in tension with the moat narrative. Firestore-fetched preserves the V3 "ship new maps without an app release" lever but means detector params round-trip through the cloud (the video never leaves the phone, but the config does). Metro-bundled fully closes the device, but new maps require an OTA / app release. The brief presents both moats as if they coexist; one Phase-6 choice will dim one of them.*
3. **Same Firebase project for web + mobile?** Apparent yes from env conventions — assert in unified architecture and CI-check.
4. **Stripe API version pin** (`2026-03-25.dahlia`) vs. installed types (`2026-04-22.dahlia`) — bump or freeze?
5. **Mobile auth migration** to `@react-native-firebase/*` to escape `getReactNativePersistence` deprecation? *Forcing function: a future Firebase v12 minor may drop the symbol entirely; deferring may pull migration work into V1 unscheduled.*
6. **Wire `apps/web` to `@warden/contracts/user-doc`** instead of redeclaring `apps/web/src/lib/schemas/subscription.ts`?
7. **`firestore.rules` coverage** — add explicit rules for `detection_config/*` and `stripe_events/*`?
8. **Ownership of `detection_config/latest`** — keep manual / out-of-band, or wire to web-admin / tooling-emit?
9. **`status` enum scope** — does mobile need `trialing` if web never writes it but Stripe might?
10. **14 vs 15 maps** — reconcile the discrepancy across `config/config.yaml`, `map_config.json`, and the legacy distillate. *Activation-path adjacent: an unreconciled map list surfaces as "unknown map" fallthroughs in the very flow the brief claims is the activation moment.*
11. **In-flight mobile Sprint 2.5 stories** — complete as legacy work in monorepo, then start unified sprint at "Sprint 3"?
12. **Pricing positioning (new)** — €7.99/mo sits below the $10–$30/mo band that adjacent B2C amateur subscriptions cluster in. Deliberate below-market FR/BE niche price, or under-monetized? Validate or adjust before V1 launch.

## Timeline

V1 launch follows completion of the **Phase-6 unified BMad chain** (this brief → PRD → architecture → UX → epics & stories → readiness check) and **the first Phase-7 unified sprint**. Concretely, the unified sprint runs *parallel to or sequential with* completion of the in-flight legacy mobile Sprint 2.5 stories — Phase-6 decision #11 binds whether those finish as legacy work in the monorepo or roll into the unified Sprint 3. No calendar date is bound at the brief level — `bmad-sprint-planning` will commit dates once epics and stories are sized against the brownfield triage backlog.
