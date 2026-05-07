---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
completedAt: '2026-05-07'
releaseMode: phased
classification:
  projectType: mobile_app
  surfaces: [mobile, web, tooling]
  requirementPrefixes: [mobile, web, tooling, cross]
  domain: general
  regulatoryComplexity: low
  crossCuttingConstraints:
    - stripe_checkout_delegated_payment
    - gdpr_voice_data
    - app_store_reader_app
    - on_device_cv_accuracy
  gameAdjacencyConstraints:
    - game_publisher_tos_monitoring
    - screen_recording_policy_compliance
  complexity: high_architectural_coordination
  complexityDrivers:
    - three_surface_coherence_via_cross_language_contracts
    - opencv_jsi_binding_load_bearing_v1_stub
    - reader_app_architecture_structural_commitment
  projectContext: brownfield
  prdGuards:
    - cross_surface_requirements_must_be_top_level_section
    - per_surface_toc_anchors_required
inputDocuments:
  - _bmad-output/product-brief.md
  - _bmad-output/product-brief-distillate.md
  - _bmad-output/legacy/distillate/01-product-strategy.md
  - _bmad-output/legacy/distillate/02-mobile.md
  - _bmad-output/legacy/distillate/03-web.md
  - _bmad-output/legacy/distillate/04-tooling.md
  - _bmad-output/legacy/distillate/06-ux-design.md
  - _bmad-output/legacy/distillate/07-epics-and-sprint-state.md
  - _bmad-output/legacy/distillate/08-open-questions-and-risks.md
  - docs/project-overview.md
  - docs/api-contracts-web.md
workflowType: 'prd'
documentCounts:
  briefs: 1
  briefDistillates: 1
  legacyDistillates: 7
  projectDocs: 2
  projectContext: 0
project: Warden_monorepo
outputPathOverride: '_bmad-output/prd.md'
---

# Product Requirements Document - Warden_monorepo

**Author:** Stephane
**Date:** 2026-05-07

## Table of Contents

1. [Executive Summary](#executive-summary)
   - [What Makes This Special](#what-makes-this-special)
   - [Project Classification](#project-classification)
2. [Success Criteria](#success-criteria)
3. [Product Scope](#product-scope)
4. [User Journeys](#user-journeys)
5. [Domain-Specific Requirements](#domain-specific-requirements)
6. [Innovation & Novel Patterns](#innovation--novel-patterns)
7. [Per-Surface Specific Requirements](#per-surface-specific-requirements)
8. [MVP Strategy & Scoping Risks](#mvp-strategy--scoping-risks)
9. [Functional Requirements](#functional-requirements)
10. [Non-Functional Requirements](#non-functional-requirements)

## Executive Summary

Warden is the phone-native coaching companion for competitive amateur and semi-pro players.

**Hero tagline (FR-locked, preserved verbatim across all surfaces):** *"Progresser plus vite en investissant moins de temps."*

The product is one thing across three surfaces. **Mobile** does the work — auto-slicing, minimap-aware ROI detection, three-mode video review, three-slot voice annotation, and standalone MP4 export — entirely on-device, with no upload, no cloud-vision tax, and no friction between the player who recorded the round and the coach who reviews it on Discord that night. **Web** does the monetization — a Stripe-driven door that paid coaches walk through once for purchase (in under sixty seconds, from a Discord coupon link), returning only for billing self-service via Stripe Customer Portal. **Tooling** does the lab work — Python CLI emitting `map_config.json`, the cross-language contract that gives mobile its tactical eye and lets new maps roll out as configs.

The concrete user is **Coach Thomas, 26**, part-time esports coach with ~10 years of FPS / 2 years of EVA After-h experience. Reviews on PC at home in 30–60-minute evening sessions. Currently juggles a video player, notepad, and editor; ships clips to his team's Discord at midnight. The cost of the status quo isn't money — it's the hour per session that should have been spent coaching. Warden replaces that hour with under five minutes from "I have footage" to "Discord has a clip."

**Secondary archetypes:** Active Player (22, high-division amateur, doubles as assistant coach, subscribes individually); Passive Player Lucas (17, receives clips via Discord, never installs the app, conversion target for the web landing). The Active Player persona name (Lucas-vs-Maxime across legacy docs) is reconciled in the Personas section.

**Demand signal:** The FR/BE EVA After-h community fields ~300+ active teams, each self-coached or with a dedicated coach — addressable beachhead of approximately 300+ individual buyers. Word-of-mouth is the dominant acquisition channel — both increases realism of penetration targets and validates Warden's Discord-native distribution and Coupon → Retained funnel as on-pattern with how the audience already moves information. Interview count, waitlist depth, and explicit willingness-to-pay validation are not yet captured; **the legacy 20-paying-coaches / 100-subscribers reference targets are not bound and will be re-baselined in the Success Criteria section once the missing demand evidence is sourced.**

### What Makes This Special

1. **Empty-niche positioning with a defensibility clock.** No direct competitor does on-device mobile video analysis for esports. Cloud video platforms (Insights.gg, CoachNow) require uploads; desktop overlays (Mobalytics, Blitz) sit next to the game, not the footage; replay analysis platforms (Leetify) parse server-side demos for one specific title. Phone-records-gameplay-and-phone-analyzes-it is open. Lead time is the asset — a fast-follower must rebuild the on-device video pipeline (FFmpeg + OpenCV-via-JSI + perceptual hashing), the cross-language schema-driven config pipeline, and the Discord-native flywheel before V1 reaches 100 subscribers.

2. **Reader-App architecture as moat.** Mobile is **paid-only with zero monetization surface** — login screen accepts only credentials issued via the web Stripe flow; no in-app pricing, no IAP, no plan picker, no free tier. This is not phasing; it is structural. It bypasses 30% store fees, keeps the paid product price-competitive, and forces Stripe-via-Firestore as the single entitlement source. *Note: this supersedes the product brief's Risk #3 framing of "fully usable without subscription except for paid-feature gating" — that brief language is stale; the PRD positions Warden as paid-only.*

3. **On-device privacy + structurally lower marginal cost.** No video leaves the phone. The on-device pipeline (CPU-bound — FFmpeg, OpenCV via JSI, pHash) carries zero per-match infrastructure cost; fixed costs (Firebase reads/writes, Stripe %) scale linearly with paying users, not footage volume. Cloud-pipeline competitors absorb per-match storage + GPU-vision cost on every uploaded clip — at €7.99/mo their margin compresses with every active session; Warden's does not. **The OpenCV JSI binding is the load-bearing V1 milestone** (currently a tested-via-injection stub). Functional requirements that depend on auto-slicing or on-device map identification inherit this risk and are flagged in their FR rows.

4. **Discord-native, viral-by-artifact distribution.** The output of a coaching session is a sharable MP4 that a non-installer can watch inline. Recipients do not need the app. Distribution is the product, and every shipped clip is a branded touchpoint to the Passive Player archetype — the Discord-link → web landing → checkout funnel that the Passive→Active conversion path depends on.

5. **Tooling as expansion moat — bounded honestly.** `map_config.json` plus the Python CLI means new **maps** roll out as configs, not code releases. New **games** require config *plus* per-title detector tuning (HSV thresholds, saturation rules, round-state semantics are EVA-specific in today's pipeline). The lever is real but bounded: maps are config-only; titles are config + a focused engineering task — still materially cheaper than the per-title cloud pipelines competitors hand-build.

**Core insight:** *The clip is the product, and the phone is enough.*

**Two structural commitments that flow from the insight:**
- **Reader-App contract** — mobile is paid-only with zero monetization surface (no IAP, no in-app pricing, no plan picker, no free tier; login-screen-only against Stripe-issued entitlement).
- **On-device-only video processing** — privacy, offline-capable, structurally lower marginal cost. The OpenCV JSI binding shipping as a real binding (not the current tested-via-injection stub) is V1-load-bearing.

**Differentiation moment (activation):** First clip exported in **under five minutes** from "I have footage" to "Discord has a clip" — the timer measures only post-checkout-complete + post-mobile-login through Discord share-sheet completion. There is no try-before-buy path; install + login + coupon redemption are *pre-activation* funnel, not part of the activation timer. The activation event chain (timer-start instrumentation, "exported" semantics, on-device-only telemetry path) is defined load-bearing in the Success Criteria section.

### Project Classification

This PRD covers a **multi-surface mobile-first product**:

- **Project type:** `mobile_app` (primary surface — "the product"), with `web_app` and `cli_tool` as secondary surfaces. The product is one thing across three surfaces; this PRD is unified, with all functional requirements prefixed by surface (`mobile-`, `web-`, `tooling-`) or by binding category (`cross-`).
- **Surfaces (deploy units):** mobile, web, tooling — three independent build/release units under the monorepo (`apps/mobile`, `apps/web`, `apps/tooling`).
- **Requirement prefixes (FR categories):** `mobile-`, `web-`, `tooling-`, `cross-`. The `cross-` prefix binds two or more surfaces (entitlement state observability, schema-contract conformance, activation event chain) — it is **not** a fourth deploy unit.
- **Domain:** general — no regulated-domain CSV row applies. Stripe Checkout offloads PCI; no FDA / KYC / DO-178C / FedRAMP. Cross-cutting constraints captured separately.
- **Cross-cutting constraints (load-bearing across the PRD):**
  - Stripe Checkout-delegated payment (PCI burden offloaded to Stripe; webhook idempotency owned by Warden web).
  - GDPR voice-data handling (voice annotations exported with MP4s travel through Discord; personal-data adjacent — controller/processor obligations apply).
  - App Store Reader-App policy (mobile login-only with no monetization surface — structural, not phased).
  - On-device CV accuracy floor (auto-slicing and map identification accuracy bars set in NFRs).
- **Game-adjacency constraints:**
  - Game-publisher ToS monitoring (per brief Risk #1 — screen-recording and competitive-title-overlay policy varies by publisher; EVA-specific policy must be researched and tracked).
  - Screen-recording policy compliance (mobile capture/import flows must respect publisher rules).
- **Complexity:** high (architectural-coordination — **not** regulatory). Drivers:
  - Three-surface coherence enforced via two cross-language contracts (`map-config.schema.json`, `user-doc.schema.json`) and one shared Firebase project.
  - The OpenCV JSI binding is currently a tested-via-injection stub — V1 load-bearing.
  - Reader-App architecture is a structural commitment propagating through every entitlement and monetization decision.
  - Regulatory complexity is low (no FDA/PCI/HIPAA/KYC/AML/DO-178C/FedRAMP).
- **Project context:** brownfield. Three pre-existing surfaces (`apps/mobile`, `apps/web` already imported under monorepo; `apps/tooling` planned next phase); in-flight Sprint 2.5 stories pending disposition; seven retro-debt items inherited.
- **PRD structural guards:**
  - The Cross-Surface Requirements section is top-level, not a tail dumping ground.
  - Per-surface table-of-contents anchors are required so readers can navigate to mobile-only / web-only / tooling-only / cross- views without scrolling the entire document.

## Success Criteria

### User Success

**Activation event chain (load-bearing definition).** Activation = first clip exported in **under five minutes**. The activation timer measures from `T0 = mobile login completes successfully against an active subscription` to `T1 = Discord share-sheet completion (OS share intent confirmed dispatched)`. Pre-T0 funnel (Discord coupon click → web landing → checkout → mobile install → mobile login) is **not** part of the activation timer; it is tracked separately as a `pre-activation funnel` metric.

**Activation timer-start instrumentation (on-device-only constraints).** Because no video leaves the phone, activation telemetry must be measurable without server-side video observation:
- T0 fires on mobile auth-state-change → `paid` (active entitlement observed locally; either fresh Firestore read or MMKV cache validated by `users/{uid}.status === "active"` and `current_period_end > now`).
- T1 fires on `expo-sharing` (or equivalent) successful share-intent **dispatch** — *not* on share-sheet open. Coach can cancel the share sheet; only confirmed-dispatch counts.
- Both events emit Firebase Analytics events (`activation_timer_started`, `activation_timer_completed`) carrying only `elapsed_seconds`. The clip itself never crosses the wire; only timestamps do.
- **OpenCV JSI binding dependency:** auto-slicing is the load-bearing path between T0 and T1. If the JSI binding ships as the current tested-via-injection stub rather than a real binding, T1 fires only on the manual-clip path. Treated as a V1 launch blocker.

**"Exported" semantics.** A clip is "exported" when *all three* hold:
1. On-device FFmpeg encode completes successfully (output MP4 written to app sandbox or shared storage).
2. OS share-sheet returns a confirmed dispatch (intent reached an external app — Discord, Messages, Files, etc.).
3. The clip's `exported_at` timestamp persists to local state (MMKV) for resume / re-share.

Encode-without-share does NOT count. Share-sheet-cancelled does NOT count. The brief's success target is *share*, not *encode*.

**No-free-tier positioning.** There is no try-before-buy or free-feature path. All activation paths assume an active subscription at T0. Mobile rejects login for any entitlement state other than `paid` or `offline-grace ≤30d` (state semantics defined under Technical Success).

**"Worth it" moment for Coach Thomas.** The hour-per-session he previously spent juggling video player + notepad + editor returns as coaching time. Dominant emotion: *purposeful immediacy* (not "I set up a review session" but "let's see what went wrong"). Anti-success: any sentence that includes "open the laptop" — Warden has failed if the coach reaches for the laptop after using the app.

**Engagement (post-activation).**
- ≥ 1 review session per week per active coach (defined as: Cinema Mode opened AND ≥ 1 clip exported within the same calendar week).
- 3–5 clips per review session at launch; climbing toward 5+ at maturity.
- Card-View → Cinema Mode → clip-export funnel completion rate within a single session ≥ TBD% (target set after first 30 days of telemetry).

### Business Success

**Reference targets — not bound until demand evidence is captured.** The legacy product strategy (when the three surfaces were planned as three independent products under separate P&Ls) named these numbers. Carried forward as starting position pending re-baselining:

| Horizon | Paying coaches | MRR | Churn | Status |
|---------|----------------|-----|-------|--------|
| 3 months post-V1 | 20 | 140€ | <15% | Reference — re-baseline pending |
| 12 months post-V1 | 100 | 700€ | <10% | Reference — re-baseline pending |

**Re-baselining inputs required (PRD demands these be captured before V1 launch, but not blocking V1 launch):**
1. **Interview count** — number of EVA After-h coaches interviewed about the existing "laptop + notepad + editor" workflow and Warden's proposed alternative. Target: ≥ TBD; current count: 0 captured in artifacts.
2. **Waitlist depth** — number of coaches who have given email or Discord handle indicating interest in V1 access. Target: ≥ TBD; current: not measured.
3. **Explicit willingness-to-pay validation** — number of coaches who, when asked the price-anchoring question, indicated €7.99/mo or €79.90/yr is acceptable for the value described. Target: ≥ TBD; current: not measured.

Once these three inputs are captured, the PRD owners re-write the targets table above. Until then, sprint planning treats the reference targets as a *not-bound* signal that V1 should not be over-scoped to chase.

**Web funnel (load-bearing for the WoM-driven Discord-link flow):**
- Visit → CheckoutStart conversion (target: TBD% — measurement instrumentation in scope).
- CheckoutStart → CheckoutComplete conversion (target: ≥ Stripe industry baseline; typically 70–80% for low-friction-auth Stripe Checkout).
- **Coupon → Retained ≥ 10% post-trial** — coaches who redeemed a Discord coupon AND remain subscribed past the deferred-billing date. The Coupon → Retained metric is the load-bearing Discord-distribution validator. Below 10% indicates either a leaky coupon flow (unlikely given Stripe-hosted Checkout) or that activation is not converting curiosity to commitment.

**Pricing positioning (Decision #12 from brief — RESOLVED in PRD).** €7.99/mo and €79.90/yr (~17% annual savings; "économisez 2 mois") are kept as PRD-bound. The brief flagged this as below-market for the $10–$30/mo B2C amateur band; **PRD treats €7.99 as deliberate FR/BE niche pricing for the WoM-driven Discord-distribution flow, not under-monetization.** Re-baselining decision deferred to post-V1 telemetry on Coupon → Retained.

### Technical Success

**V1-load-bearing technical milestones (any of which slips → V1 slips):**
- **OpenCV JSI binding ships as a real binding** (not the current tested-via-injection stub). Map identification + auto-slicing FRs depend on this.
- **Cross-language schema-contract conformance.** `map-config.schema.json` enforced strictly (`additionalProperties: false`) on web (Zod, build-time) and tooling (jsonschema, runtime). `user-doc.schema.json` schema duplication resolved per Decision #1 (escalated to architecture).
- **Stripe webhook idempotency** — dual-strategy idempotency (event ID + business-state observation) maintains entitlement correctness under retry. Already implemented per brief (Epic 4); PRD requires regression coverage.
- **Reader-App contract maintained** — no monetization surface ships in any mobile build artifact. CI gate: build-time AST / grep check for IAP imports, pricing strings, plan-picker components.
- **30-day offline auth-cache** — mobile maintains entitlement validity for 30 days after last successful Firestore read; lapses to `signed-out` on day 31 (precise transition semantics owned by architecture).

**Performance floor (escalated to architecture pre-PRD spike).** Reference-device target binds the on-device CV ceiling. Brief Risk #2 assigned `bmad-create-architecture`'s first task to bind the floor with measured numbers; PRD inherits that target once architecture publishes it.

**Accuracy floors (Risk #5 — auto-slicing accuracy ceiling).** No quality threshold or human-in-the-loop fallback in V1. PRD sets:
- **Map identification accuracy: ≥ 95% on a held-out test set** (consistent with legacy tooling target: 100% on training, ≥95% on unseen).
- **Round-boundary detection: ≥ TBD%** (legacy goal: 100% black-screen-transition detection with 0 false positives — set by tooling reference impl; mobile port must meet or close the gap).
- **Below-floor behavior:** if a map cannot be identified, mark `map_name = "unknown"` — navigation still works, sort-by-map degrades gracefully. If a round boundary is missed, the coach can manually create a clip from the timeline (no auto-slice safety net required in V1).

**Cross-surface entitlement state machine (load-bearing — semantics defined here, transitions owned by architecture):**

| State | Definition | App usability |
|-------|------------|---------------|
| `paid` | Active subscription observed (web wrote `status: "active"` to `users/{uid}`; mobile reads). | Fully usable. |
| `lapsed` | Subscription ended (`status: "canceled"` or expired; `current_period_end < now`). | **Unusable** — mobile shows "subscription required" screen with deep-link to web Customer Portal. Not a soft state. |
| `offline-grace ≤30d` | Mobile cannot reach Firestore but last successful read had `status: "active"` and was ≤ 30 days ago. | Fully usable. **Only soft state in the machine.** |
| `payment-failed` | Stripe webhook `invoice.payment_failed` flipped `status: "past_due"`. | Usable with warning banner + "Update payment method" CTA (deep-link to Stripe Customer Portal). Configurable grace period before transitioning to `lapsed`. |
| `multi-device` | Same `users/{uid}` observed on multiple device installations. | Fully usable. PRD does not enforce single-device; entitlement is per-user, not per-device. |
| `signed-out` | No auth token present. | **Unusable** — login screen only. |

Transition rules (which event triggers which transition, retry semantics, race-condition handling) are owned by `bmad-create-architecture`.

### Measurable Outcomes

| Outcome | Metric | Target | Owner | Instrumentation |
|---------|--------|--------|-------|-----------------|
| Activation | T1 − T0 elapsed seconds | < 300s | Mobile + Web | Firebase Analytics (`activation_timer_started` / `activation_timer_completed`) |
| Engagement | Active coach sessions / week | ≥ 1 / coach | Mobile | Cinema Mode opens with ≥ 1 export within 7-day window |
| Engagement | Clips per review session | 3–5 launch; 5+ maturity | Mobile | Per-session export count |
| Web funnel | Coupon → Retained | ≥ 10% post-trial | Web + Stripe | Stripe coupon redemption tracked against subscription persistence past deferred-billing |
| Web funnel | Visit → CheckoutComplete | ≥ Stripe baseline | Web | Firebase Analytics + Stripe Checkout completion |
| Business | Paying coaches @ 3 months | Reference: 20 (re-baseline pending) | Business | Stripe MRR |
| Business | Paying coaches @ 12 months | Reference: 100 (re-baseline pending) | Business | Stripe MRR |
| Technical | Map ID accuracy | ≥ 95% on unseen | Tooling + Mobile | `hash_validator` regression suite + on-device sampling |
| Technical | Reader-App contract intact | 0 monetization-surface artifacts in mobile build | Mobile | CI gate (build-time AST check) |
| Demand | Coach interviews captured | ≥ TBD pre-V1 | Business | Interview tracker (location TBD) |
| Demand | Waitlist depth | ≥ TBD pre-V1 | Business | Sign-up form / Discord poll |
| Demand | Explicit WTP validations | ≥ TBD pre-V1 | Business | Interview / survey response set |

## Product Scope

### MVP — Minimum Viable Product (V1)

**Mobile (paid-only Reader-App, FR-locked UI):**
- Auto-slicing via on-device map detection — subsumes OpenCV JSI binding shipping as real binding (not stub) AND map ID accuracy ≥ 95% on unseen AND round-boundary accuracy floor.
- Card View with episode-style triage grid + sort options (temporal default; score-based sorts gracefully degrade until OCR ships in V2).
- Cinema Mode (immersive review, reveal-on-tap controls, double-tap top-left view-mode cycle).
- 3-mode view toggle (Full / Minimap / Minimap+HUD) with persisted preference (MMKV).
- 30-second clip definition with bracket-handle refinement + 3-slot voice annotation (before / during / after) + standalone MP4 export.
- Mobile and HD encode tiers + OS share-sheet handoff.
- Auto-save + crash recovery (resume to exact map + position + comments-in-progress).
- Firebase auth + entitlement validation + 30-day offline auth-cache.
- Login-screen-only with no monetization surface (Reader-App contract).

**Web (English UI with FR-locked hero):**
- Marketing landing optimized for Discord coupon entry (Direction A "Clean Minimal" per legacy UX distillate).
- `/pricing` with 2 plan cards (€7.99/mo, €79.90/yr) + Stripe coupon URL param + auth modal (Google + Email/Password).
- Stripe Checkout (full-page redirect; Stripe-hosted) with deferred-billing copy ("*Vous ne serez pas débité avant le [date]*").
- `/dashboard` (protected, fresh reads from Firestore — no `onSnapshot`) showing email + plan + status badge + next payment date + "Manage Subscription" deep-link to Stripe Customer Portal.
- Webhook-driven `users/{uid}` writes (server-only, dual-strategy idempotent).
- Firebase Analytics for funnel tracking (Visit → CheckoutStart → CheckoutComplete + Coupon → Retained).

**Tooling (Python ≥3.11 CLI under uv workspace):**
- 5 user-facing tools — `game_detector`, `frame_labeler`, `map_config_generator` (or `hash_comparator`), `hash_validator`, `warden_analyzer` — emitting `map_config.json`.
- Cross-language schema validation via `contracts/map-config.schema.json` (Zod on web at build time; jsonschema on tooling — Phase-6 architecture asserts this in code).
- TUI launcher (`questionary`-based) for interactive workflow.

**Cross-surface (binding requirements):**
- Entitlement state machine semantics per Section 2 (transitions owned by architecture).
- `map-config.schema.json` enforced strictly across web + tooling.
- `user-doc.schema.json` schema duplication resolved (Decision #1 — escalated to architecture).
- Activation event chain instrumentation per Section 2 (telemetry without crossing the wire).

### Growth Features (V2 — Post-MVP)

- Discord OAuth (web — adds to existing Google + Email/Password).
- Coupon admin UI (web self-serve; replaces Stripe-dashboard-only coupon management).
- Custom analytics dashboard (web — replaces Firebase Analytics for richer funnel visibility).
- Team / group billing (web — replaces individual subscriptions for multi-seat coaches).
- Self-serve account deletion (web — V1 is manual via support email).
- Churn survey on cancellation (web — V1 has no exit survey).
- In-dashboard coupon redemption (web — V1 routes coupons through Stripe URL param).
- OCR scores / kills (mobile — populates `score_orange` / `score_blue`; enables score-based Card View sorts).
- Stats per map (mobile — depends on OCR).
- Advanced ROI composition (mobile — minimap + killfeed + life zones).
- Vertical export format (mobile — Stories / TikTok format).
- Custom ROI templates (cross-surface — desktop-flavored feature).
- Review import mode (mobile — active player imports coach reviews with annotations; closes the J4 partial-support gap).
- Pick & Ban tool (cross-surface).
- Multi-view clip export (mobile — POV → minimap switch within single exported clip via multi-segment FFmpeg encoding).
- Export queue with background encoding (mobile — replaces V1's encode-immediately-then-share UX).

### Vision (V3 — Future)

- **Broader tactical-FPS coaching companion** — additional titles (CS2, Valorant, R6) added by `map_config.json` *plus* per-title detector tuning (HSV thresholds, saturation rules, round-state semantics; not pure config swap).
- Referral system (web — "dealer of comfort" growth via local-league winners).
- Full French localization (web UI — V1 is English with FR-locked hero copy).
- iOS (mobile — Phase 2 after Apple license validation; FFmpeg-kit fork config plugin TBD per architecture).
- Desktop (cross-surface — power-user analysis flow).
- Discord stream group review (cross-surface — Phase 3, Desktop-flavored).

## User Journeys

The journeys below are the narrative spine connecting the personas in the Executive Summary to the functional requirements in subsequent sections. Each journey ends with a **Capabilities Revealed** block that names which FR clusters the journey demands; the FR section will use this to anchor traceability.

### Persona Reconciliation (Brief Open Question RESOLVED)

The product brief flagged a Lucas-vs-Maxime persona-name conflict between legacy mobile and web docs. **PRD resolution:**

- **Coach Thomas, 26** — primary; part-time esports coach.
- **Active Player Maxime, 22** — secondary; high-division amateur who doubles as assistant coach for his crew; subscribes individually. Name lifted from legacy mobile distillate.
- **Passive Player Lucas, 17** — secondary; receives clips via Discord, never installs the app initially; Passive→Active conversion target. Name lifted from legacy web distillate + brief Executive Summary.

When Lucas converts and becomes a paying Active Player, he becomes "an Active Player like Maxime" — same archetype-by-state, different ages and entry paths. They are not the same person; they are the same *role at different conversion stages*. J1's narrative coach-of-Lucas, J5's Discord-recipient-Lucas, and J6's converting-Lucas are the same character.

### J1 — Coach Thomas: First-time activation (cross-surface, happy path)

**Opening scene.** Thomas, a part-time esports coach in Lyon, manages a 4-player EVA After-h squad that climbed two divisions last season. His evening review ritual is the same it's been for two years: 1h20 of recorded footage on his laptop, a notepad open, a video player paused mid-round, a video editor in another window. Tonight one of his players DMs him on Discord: *"Coach, ce flank c'est moi qui ai foiré ?"* He opens Discord on his phone and sees a Warden coupon link from another local-league coach he respects. *"Essaie ça, ça change tout."*

**Rising action.** Thomas taps the link. Web landing loads in dark mode, hero in French ("*Progresser plus vite en investissant moins de temps.*"), single CTA. He clicks Pricing — Discord coupon auto-applied, billing deferred 7 days. He auths via Google in two taps, redirects to Stripe Checkout, confirms — total elapsed: 47 seconds. Lands on `/dashboard` with `?success=1`, status badge green. He installs the Warden mobile app from the success email, opens it, signs in with the same Google account.

**Climax.** Mobile login confirms entitlement (`status: "active"`); the activation timer starts (T0). Thomas taps "Import session," picks the 1h20 file from his phone's recordings. Auto-slice runs in ~90 seconds. Card View opens — 8 maps, lobby auto-removed. He spots the round his player asked about (Silva, sorted to top by recency), taps in. Cinema Mode loads, double-taps top-left to switch to Minimap+HUD view, scrubs to the 0:42 mark, taps "clip," drags the 30-second region to land on the flank rotation, taps "during" to record voice: *"Lucas, ton flank est ouvert parce que t'es trop avancé sur la passerelle — recule de 3 mètres."* Taps Export → Mobile quality → encode runs (~12s) → OS share-sheet opens → Discord. Confirmed dispatch.

**Resolution.** T1 fires: 4 minutes 31 seconds since mobile login. Activation hit. Thomas closes the app, opens Discord, watches the clip play inline in the channel, sees Lucas reply: *"Ok compris, je me cale sur toi."* The hour of editor wrestling didn't happen tonight.

**Capabilities revealed.**
- `web-LANDING`, `web-PRICING`, `web-CHECKOUT`, `web-AUTH-MODAL`, `web-COUPON-URL-PARAM`, `web-DEFERRED-BILLING-COPY`, `web-DASHBOARD-SUCCESS-STATE`
- `mobile-AUTH-LOGIN`, `mobile-ENTITLEMENT-VALIDATION`, `mobile-IMPORT-SESSION`, `mobile-AUTO-SLICE`, `mobile-CARD-VIEW`, `mobile-CINEMA-MODE`, `mobile-VIEW-MODE-TOGGLE`, `mobile-CLIP-REGION-SELECTOR`, `mobile-VOICE-RECORDER-DURING`, `mobile-EXPORT-MP4-MOBILE-TIER`, `mobile-OS-SHARE-SHEET`
- `cross-ACTIVATION-EVENT-CHAIN-T0-T1-INSTRUMENTATION`, `cross-ENTITLEMENT-STATE-PAID`

### J2 — Coach Thomas: Steady-state weekly review with interruption

**Opening scene.** A week later. Thomas has subscribed past the deferred-billing date (Coupon → Retained metric). Tuesday night: he opens Warden mobile, Card View is empty (no in-progress session). He imports last weekend's 1h05 footage. Auto-slice runs. He's halfway through the third map when his daughter wakes up. He closes the app mid-clip, voice annotation half-recorded, no warning prompt because Warden auto-saves silently.

**Rising action.** Two hours later he reopens. Cinema Mode resumes at the exact frame, the half-recorded voice annotation is still there, clip region preserved with bracket handles intact. He listens back to his half-recording — *"euh, donc là Maxime…"* — taps "during" again to overwrite, finishes the thought, exports.

**Climax.** Total elapsed across the two halves: 22 minutes — 4 minutes of which were the interruption. Without auto-save, the second half would have started from scratch.

**Resolution.** Thomas exports 4 clips total this session, ships them to the squad's Discord channel. He'll do this every Tuesday and Sunday now.

**Capabilities revealed.**
- `mobile-AUTO-SAVE`, `mobile-CRASH-RECOVERY`, `mobile-RESUME-CINEMA-MODE-EXACT-POSITION`, `mobile-RESUME-VOICE-ANNOTATION-IN-PROGRESS`, `mobile-CLIP-REGION-PERSISTENCE`
- `cross-ACTIVATION-EVENT-CHAIN-STEADY-STATE` — telemetry must distinguish first-time vs repeat sessions for retention metrics.

### J3 — Coach Thomas: On-device CV failure modes (edge cases)

**Opening scene.** Thomas imports a 50-minute session. Auto-slice completes, but two anomalies surface:
1. One round shows `map_name = "unknown"` on its Card.
2. Another expected round is missing entirely from the Card View — auto-slice missed the round boundary.

**Rising action.** He taps the unknown-map card; Cinema Mode opens normally, View Mode defaults to `Full` (Minimap+HUD requires a known map ROI). He uses the temporal sort to find the missed round — it's there in the timeline but not as a Card. He scrubs into Cinema Mode at the timestamp, taps "clip" with the bracket handles, defines a manual 30-second clip, records voice, exports. No auto-slice safety net was needed.

**Climax.** Both failure modes were handled via graceful degradation, not blocking errors. The "unknown map" never reached the publication channel; Discord saw two clean clips.

**Resolution.** Over 30 days Thomas will see this happen on ~5% of rounds (per the ≥95% map ID accuracy floor). He never treats it as a bug; he treats it as Warden being honest about what it does and doesn't know.

**Capabilities revealed.**
- `mobile-MAP-ID-UNKNOWN-FALLBACK`, `mobile-MANUAL-CLIP-CREATION-FROM-TIMELINE`, `mobile-VIEW-MODE-DEFAULTS-TO-FULL-WHEN-NO-MAP-ROI`
- `mobile-CARD-VIEW-MISSED-ROUND-DOES-NOT-BLOCK-NAVIGATION`
- Validates Section 2 accuracy floor + below-floor behavior.

### J4 — Active Player Maxime: Solo self-review

**Opening scene.** Maxime, 22, plays high-division EVA After-h and doubles as assistant coach for his crew. His coach reviews the team's footage; Maxime reviews his own POV separately, after his coach has shipped the squad clips. He subscribes individually because he wants the auto-slice + Minimap+HUD analytical view without depending on his coach's review schedule.

**Rising action.** Maxime imports his POV recording. Auto-slice runs. He opens Cinema Mode on a round he flagged as "I died too early on B." He toggles to Minimap+HUD view, scrubs around his death timestamp, sees on the minimap that he was off-angle relative to teammate positions — a pattern he didn't see in real-time. He doesn't record voice. He doesn't export. He just *watches*, switches Full / Minimap / Minimap+HUD several times, builds a mental note.

**Climax.** Maxime's value loop is shorter than Thomas's — he doesn't need an exported artifact because the audience is just himself. Card View and Cinema Mode are doing 100% of the work without the export tail of the funnel.

**Resolution.** Maxime closes the app. No clip exported, no Discord shared, no voice recorded. The activation event for Maxime is *Cinema Mode opened on a round + view-mode toggled at least once* — not export-completion. The PRD's activation telemetry distinguishes "Active Player solo path" (Cinema Mode engagement, no export) from "Coach path" (Cinema Mode + export).

**Capabilities revealed.**
- `mobile-CINEMA-MODE-WITHOUT-EXPORT`, `mobile-VIEW-MODE-PERSIST-PREFERENCE`, `mobile-MINIMAP-HUD-OVERLAY` (KDA + Score from `map_segments`)
- `cross-ACTIVATION-TELEMETRY-DISTINGUISHES-COACH-VS-ACTIVE-PLAYER-PATHS` — **open question:** does the < 5min activation target apply identically to Maxime's no-export path? PRD position: yes, but T1 = "Cinema Mode opened with view-mode toggled at least once" — *not* export. Architecture confirms the dual-T1 instrumentation.

### J5 — Passive Player Lucas: Receives clip, does NOT install

**Opening scene.** Lucas, 17, is the passive player on Thomas's squad. Reflexes great, game-vision weak. He doesn't review his own footage. He gets clips from Thomas via Discord, on his phone, in his bedroom, around 23h30.

**Rising action.** Discord notification: *Coach posted a clip in #replays.* He taps. The MP4 plays inline. He sees the minimap view (he wouldn't have known to look at the minimap on his own), hears Thomas's voice say *"Lucas, ton flank est ouvert parce que t'es trop avancé sur la passerelle — recule de 3 mètres."*

**Climax.** Two seconds after the clip ends, Lucas types in the channel: *"Ok compris, je me cale sur toi."*

**Resolution.** Lucas does not install Warden. He never will, in this journey. The product touches him exactly once — the inline-playable Discord MP4. Warden's UX responsibility ends at the share-sheet dispatch in J1; everything after that is Discord's surface, and that's the design.

**Capabilities revealed.**
- `mobile-EXPORT-STANDALONE-MP4-DISCORD-INLINE-PLAYABLE` — the MP4 must be a vanilla H.264/AAC container that Discord's preview pane can render. No Warden install required to view.
- The product's distribution depends on this constraint; failure here breaks the WoM moat.

### J6 — Passive→Active conversion: Lucas becomes a paying Active Player

**Opening scene.** Three months later. Lucas has been receiving Thomas's clips on Discord twice a week. He's started to notice patterns: he's always the one being told about flanks, about positioning, about where his game-vision drops off. He's curious. One Friday afternoon, he taps the coupon link Thomas pinned in the squad's general channel.

**Rising action.** Web landing in French. He scrolls — no testimonial farm, no fake screenshots, no countdown timer. Just the hero, three differentiator points, single CTA. He clicks Pricing — €7.99/mo, coupon auto-applied, deferred billing 7 days. He auths with his Discord-linked Google account. Completes Stripe Checkout in under 60 seconds. Installs the mobile app, signs in.

**Climax.** Lucas's first session: he imports his own POV recording (which he had never done before — the recordings were just sitting in his phone's gallery). He auto-slices, opens Cinema Mode, toggles Minimap+HUD. Sees his own positioning from above for the first time. Stays in the app for 35 minutes that night.

**Resolution.** Lucas does not export anything in his first session. He's not a coach; he's not building artifacts. But he keeps the subscription active past the deferred-billing date — Coupon → Retained.

**Capabilities revealed.**
- All J1 web-checkout capabilities (the conversion path is structurally identical to coach onboarding — the *only* difference is the use case after install).
- Validates the moat: the same web-checkout funnel converts both coach and active-player archetypes; the funnel doesn't need persona-specific variants.
- `cross-COUPON-RETAINED-METRIC` — Lucas's retention past deferred billing IS the WoM-driven Discord-distribution validator from Section 2.

### J7 — Subscription lapse: Thomas hits payment failure

**Opening scene.** Three months in. Thomas's bank reissues his card; he forgets to update Stripe. Auto-charge fails on the renewal date.

**Rising action.** Stripe webhook `invoice.payment_failed` flips Thomas's `users/{uid}.status` to `past_due`. Mobile shows a warning banner at the top of the home screen — *"Mise à jour du moyen de paiement nécessaire"* with a CTA. He keeps using the app for now (state = `payment-failed`, app remains usable during configurable grace period). Web dashboard, when he visits, shows the same status badge in amber + "Update payment method" deep-link.

**Climax.** He taps the deep-link, lands in Stripe Customer Portal, updates the card. Stripe auto-retries within hours; the next webhook flips status back to `active`. Mobile banner disappears on the next entitlement re-check.

**Resolution.** Thomas never lost access. The entitlement state machine handled the failure as a soft state (`payment-failed`), not a hard cutoff. Grace period prevented a brittle "card declined → app unusable mid-review-session" failure mode.

**Capabilities revealed.**
- `cross-ENTITLEMENT-STATE-PAYMENT-FAILED`, `cross-ENTITLEMENT-STATE-PAYMENT-FAILED-GRACE-PERIOD` (configurable; architecture sets duration based on Stripe Smart Retries cadence)
- `web-DASHBOARD-PAYMENT-WARNING-BANNER`, `mobile-PAYMENT-WARNING-BANNER`, `web-CUSTOMER-PORTAL-DEEP-LINK`
- `cross-ENTITLEMENT-RE-CHECK-AFTER-PORTAL-RETURN` — mobile re-fetches `users/{uid}` on app foreground after a Stripe Customer Portal round-trip.

### J8 — Subscription cancellation: Thomas cancels

**Opening scene.** Six months in. Thomas's life is changing — his squad disbanded, he's coaching less. He decides to cancel.

**Rising action.** Web dashboard → Cancel button → confirmation dialog ("access until [date]"). No exit survey. No guilt-trip. He confirms; Stripe sets `cancel_at_period_end: true`; status badge flips to "Canceling" (gray) with a "Resubscribe" CTA. Mobile shows the same banner at next foreground.

**Climax.** Period end arrives. Stripe webhook `customer.subscription.deleted` flips status to `canceled`. Mobile entitlement check on next foreground sees `lapsed`, transitions UI to "subscription required" screen. Thomas is signed out of the active-app surface.

**Resolution.** Three weeks later Thomas reopens — sees the "subscription required" screen, taps the deep-link to web Customer Portal, reactivates. Mobile entitlement re-checks on foreground; status flips to `paid`; he's back in. Cancellation flow was clean, reversible, and the lapsed-state UI did not corrupt his existing session data (preserved in MMKV).

**Capabilities revealed.**
- `web-DASHBOARD-CANCEL-FLOW`, `web-DASHBOARD-CONFIRMATION-DIALOG`, `web-DASHBOARD-RESUBSCRIBE-CTA`, `web-STATUS-BADGE-CANCELING-AMBER`
- `cross-ENTITLEMENT-STATE-LAPSED`, `mobile-LAPSED-STATE-SUBSCRIPTION-REQUIRED-SCREEN`, `mobile-DEEP-LINK-TO-WEB-CUSTOMER-PORTAL`
- `mobile-PRESERVE-SESSION-DATA-ACROSS-LAPSE` — do not delete user-generated content on lapse; restore-on-resubscribe.
- **No exit survey, no guilt-trip** — explicitly required (anti-dark-pattern policy from legacy UX distillate).

### J9 — Offline-grace: Thomas reviews on the train

**Opening scene.** Thomas takes the TGV to a tournament. No Wi-Fi, spotty cellular. He opens Warden mobile to review last week's session.

**Rising action.** Mobile cannot reach Firestore. Auth check falls back to MMKV cache: last successful read had `status: "active"` and was 3 days ago. State = `offline-grace ≤30d`. App is fully usable. Thomas reviews two maps, exports two clips, queues them for share — Discord delivers when connectivity returns; OS share sheet handles offline gracefully.

**Climax.** App never asks for re-auth. Coach experience is identical to online. The 30-day cache is the load-bearing concession to "reviewing-on-the-go" use.

**Resolution.** On day 31 of cache age, app forces a re-auth on next foreground. Thomas's case never hits this — he syncs back online within hours of the train ride.

**Capabilities revealed.**
- `cross-ENTITLEMENT-STATE-OFFLINE-GRACE-30D`, `mobile-OFFLINE-CACHE-MMKV`, `mobile-OFFLINE-EXPORT`, `mobile-OFFLINE-CACHE-EXPIRY-DAY-31`
- The 30-day grace is a structural privacy concession (offline = no Firestore round-trip; entitlement is locally validated). Reinforces no-cloud-vision-tax differentiator.

### J10 — Developer: Stephane regenerates `map_config.json`

**Opening scene.** Stephane wants to add support for a 15th EVA After-h map (or reconcile the 14-vs-15 maps discrepancy from brief Decision #10). He has 30 reference video clips of the new map. He's at his laptop with the Warden monorepo cloned.

**Rising action.** He runs `python wardentooling.py`, picks Tool 1 (BSD round extraction) on each video, then Tool 2 (frame labeler) to label start/end/score frames into `labeled/<new_map>/`, then Tool 3 (`hash_comparator`) with the new map included to regenerate `map_config.json`. Tool 4 (`hash_validator`) reports per-map accuracy on the regression set. New map: 96% accuracy on unseen — passes the floor.

**Climax.** He runs the cross-language schema validator: `pnpm contracts:validate map-config` (Zod side) and Python `jsonschema` validation (tooling side). Both pass. He commits the new `map_config.json` to the repo.

**Resolution.** Mobile pulls the new config (delivery mechanism = open architecture Decision #2 — Firestore-fetched vs Metro-bundled; PRD does not pre-decide). Either way, the new map is now identifiable on-device by all Warden users. Adding a map was a config change, not a code release. The brief's "tooling expansion moat — bounded honestly" claim is validated end-to-end on this journey.

**Capabilities revealed.**
- `tooling-TUI-LAUNCHER`, `tooling-BSD-ROUND-EXTRACTION`, `tooling-FRAME-LABELER`, `tooling-HASH-COMPARATOR`, `tooling-HASH-VALIDATOR`, `tooling-MAP-CONFIG-EMIT`
- `cross-MAP-CONFIG-SCHEMA-VALIDATION-CROSS-LANGUAGE` (Zod + jsonschema)
- `cross-MAP-CONFIG-RUNTIME-DELIVERY` (escalated to architecture — Decision #2 is moat-shaping; PRD does not pre-decide)

### Out-of-scope journeys (V1 explicit non-coverage)

- **Admin / Operations:** V1 has no admin UI; coupon management is via Stripe dashboard, manual. No PRD requirements; deferred to V2 (`web-COUPON-ADMIN-UI`).
- **Support:** V1 support is manual via support email. No PRD requirements; account deletion is also manual via support email per V2 deferral.
- **API consumer:** Warden has no external API in V1 or V2. Out of vision scope.

### Journey Requirements Summary

The 10 journeys collectively reveal the following capability clusters. Each cluster maps to one or more FR sections in the next part of the PRD; FRs without a journey trace will be flagged in Section 5 for re-justification or removal.

| Capability cluster | Journeys revealing it | Surface |
|--------------------|----------------------|---------|
| Web Stripe-handoff funnel (landing → pricing → checkout → dashboard) | J1, J6 | Web |
| Stripe Customer Portal deep-link round-trip | J7, J8 | Web + Cross |
| Mobile auto-slice + Card View + Cinema Mode + voice + export | J1, J2, J3, J4 | Mobile |
| Mobile auto-save + crash recovery + resume | J2 | Mobile |
| Mobile graceful degradation (unknown map, missed round) | J3 | Mobile |
| Active-player solo path (no export; activation telemetry distinction) | J4 | Mobile + Cross |
| Discord-inline-playable MP4 export contract | J1, J5 | Mobile |
| Entitlement state machine — all six states | J7, J8, J9 | Cross |
| Offline-grace ≤30d soft state | J9 | Mobile + Cross |
| Tooling pipeline (BSD → label → hash → validate → emit) | J10 | Tooling |
| Cross-language schema validation | J10 | Tooling + Web (cross) |
| `map_config.json` runtime delivery (escalated to architecture — Decision #2) | J10 | Cross |

## Domain-Specific Requirements

The classification puts Warden in the `general` domain with `regulatoryComplexity: low`. Yet the cross-cutting constraints surfaced in Project Classification and the eight risk classes in the product brief have domain-flavored teeth — privacy law for voice annotations, store policy for Reader-App, game-publisher ToS adjacency, and the brownfield triage backlog. This section formalizes those constraints into compliance / technical / integration / mitigation buckets so each gets an FR anchor downstream.

### Compliance & Regulatory

**GDPR — voice-data handling (load-bearing).** Voice annotations are personal-data adjacent (the voice itself can identify the speaker). Warden's structural compliance posture, asserted in this section:

- **Storage:** voice audio is captured on-device, encoded into the exported MP4 on-device, and never transmitted to any Warden-controlled server. The product controls no voice-data servers.
- **Transit:** voice leaves the device only inside an exported MP4 dispatched via the OS share sheet to a third-party app (Discord, Messages, etc.) at the *coach's explicit action*. That is the user-initiated transit; Warden is not the controller of the resulting Discord channel.
- **Consent:** the coach is the data subject of their own voice. Voice annotations OF other parties (e.g., voice describing or naming a player) are the coach's responsibility and are out of Warden's enforcement scope (Warden cannot detect or filter speech-content). Warden's UX must NOT prompt for "anonymize voice" or similar — the brief's emotional design says "the voice IS the tone."
- **Retention:** voice is local to the device; deleted when the user deletes the clip or the app. Warden does not retain voice on any server.
- **Subject rights (export / erasure):** since voice never reaches a Warden server, these rights are auto-satisfied — there is no server-side data to export or erase. The mobile app must support local clip deletion (in scope via clip management).

**Web checkout — PCI-DSS scope offloaded.** Stripe Checkout is the full-page redirect; card data never crosses Warden's servers. Webhook events from Stripe contain only Stripe IDs (`customer`, `subscription`, `invoice`) and never card primitives. Warden web is *out of PCI-DSS scope* as long as this contract holds — assertion: no FR may require card data to flow through Warden code paths.

**App Store Reader-App policy — build-time enforced.** The Reader-App contract (mobile login-only, no monetization surface, no IAP, no in-app pricing, no plan picker, no free tier) is the compliance posture that bypasses Apple's 30% / Google Play's equivalent.

- **Build-time CI gate (signaling-tier defense-in-depth, NOT absolute prevention).** The gate catches accidental drift — copy-paste from tutorials pulling in pricing strings, library upgrades pulling in monetization deps transitively, i18n bundles accidentally getting a `subscription.monthly` string. It does NOT defend against intentional bypass; intentional bypass is a code-review responsibility, not a CI responsibility.
- **Direct-import bans:** mobile build artifacts must contain zero imports of `react-native-iap`, `expo-in-app-purchases`, or any Stripe Mobile SDK.
- **Transitive-dependency scan (required, not optional):** `pnpm ls --depth=Infinity` (or equivalent for the package manager in use) must report zero entries for the banned packages. Direct manifest scan alone is insufficient — banned packages may arrive via sub-dependency.
- **String bans:** zero pricing strings (€7.99, €79.90, "subscribe", "buy", "monthly", "yearly", and locale equivalents) in app source or i18n bundles; zero plan-picker UI components.
- **Reviewability posture:** if Apple/Google reviewers query the entitlement source, Warden's answer is "Stripe via web; the mobile app has no store-billable transaction." This is the structural Reader-App stance.

**Game-publisher ToS — operational tracking obligation.** Per brief Risk #1, EVA-specific ToS regarding screen-recording and overlaid analysis is not yet researched. PRD requires:

- A **ToS-monitoring tracker** (location TBD, likely under `docs/compliance/` or an issues board) that captures, per supported title: current ToS version, screen-recording policy, monetization-around-game policy, last-reviewed date.
- For V1, a single entry for EVA After-h ToS is sufficient; the tracker structure must support multi-title for V3.
- Architecture / sprint-planning owns the cadence; PRD owns the requirement that the tracker exists.

**Screen-recording policy compliance.** Mobile capture/import flows must not fingerprint or DRM-bypass game footage. Warden imports footage that the *user* recorded; Warden does not record game footage on the user's behalf. This boundary is structural to the import-only flow.

### Technical Constraints

**On-device-only video processing — structural constraint.** No video frames, audio frames, or derived video data (clips, thumbnails, OCR'd text in V2) cross any wire to a Warden-controlled server.

- **Permitted transit:** users may, by their action, share an exported MP4 through OS share sheets — the J1 / J5 distribution path.
- **Forbidden transit:** Warden code may not implement upload-to-Warden-server, telemetry-with-frame-data, or "send a clip to support" features. Activation telemetry (Section 2) carries only timestamps and event names; not frames, not voice durations, not raw audio.

**30-day offline auth-cache — soft-state-only entitlement persistence.** Mobile maintains entitlement validity for 30 days post last successful Firestore read. Implementation surface (MMKV) is owned by architecture; PRD owns the 30-day window, the day-31 expiry behavior (force re-auth on next foreground), and the constraint that during the offline-grace window the app behaves identically to `paid` (J9).

**OpenCV JSI binding — V1-load-bearing milestone.** Currently a tested-via-injection stub; V1 launch requires shipping as a real binding. FRs that depend on auto-slicing or on-device map identification inherit this risk and are flagged in their FR rows. Architecture decides JSI vs alternative binding strategy (Expo Modules API, native module); PRD requires "shipped as real binding," not stub.

**Cross-language schema-contract enforcement.** `map-config.schema.json` enforced strictly (`additionalProperties: false`) on web (Zod, build-time) and tooling (jsonschema, runtime / CI). `user-doc.schema.json` schema duplication resolved per Decision #1 (escalated to architecture). Both contracts are first-class repo artifacts under `packages/contracts/` (location confirmed by architecture).

**Stripe webhook idempotency — dual-strategy.** Already implemented per brief (Epic 4); PRD requires regression coverage. Strategy: (1) event ID deduplication via `stripe_events/{event_id}` Firestore document existence check; (2) business-state observation (re-applying the same event to an already-correct state is a no-op). Architecture documents the precise idempotency contract; PRD requires both legs.

**Reader-App build-time enforcement** (above; restated as a technical constraint with the signaling-tier CI gate spec).

**Performance floor — escalated to architecture pre-PRD spike.** Reference-device target binds the on-device CV ceiling per brief Risk #2. PRD inherits the target once architecture publishes it. V1 launch criteria includes architecture's spike completion.

**Accuracy floors** (already set in Section 2): map ID ≥ 95% on unseen; round-boundary detection ≥ TBD%; below-floor behavior is graceful degradation, not blocking error.

### Integration Requirements

| System | Role | Integration depth | Owned by | Failure-mode contract |
|--------|------|-------------------|----------|-----------------------|
| Stripe Checkout | Payment capture (full-page redirect) | First-class | Web | Stripe down → user sees Stripe-hosted error; Warden landing/dashboard remain up |
| Stripe Customer Portal | Billing self-service | First-class | Web | Portal down → "manage billing" CTA shows fallback message; no billing data corruption |
| Stripe Webhooks | Entitlement state source | First-class | Web | Webhook delay → `users/{uid}` lags actual subscription state; tolerable for ≤ minutes; >1h indicates webhook-processing fault |
| Firebase Auth | Identity | First-class | Web + Mobile | Auth down → mobile uses MMKV-cached entitlement (offline-grace); web shows fallback error on login |
| Firestore | Entitlement persistence + detection_config storage | First-class | Web (writes) + Mobile (reads) | Firestore down on mobile → offline-grace path; Firestore down on web → webhook idempotency retries until restoration |
| Firebase Analytics | Funnel + activation telemetry | First-class | Web + Mobile | Analytics down → silent (telemetry events buffered; no user-visible failure) |
| Discord | Distribution channel | **Passive** — via OS share sheet; not via Discord API | Mobile (passive) | Discord down → user picks alternate share target (Messages, Drive, etc.); Warden has no Discord-API dependency |
| OS Share Sheets | Mobile share dispatch | First-class | Mobile | OS-level concern; Warden assumes share intent dispatch; no failure-recovery code in mobile (OS handles) |
| FFmpeg (mobile) | Video encode/decode | First-class | Mobile | Architecture-decided binding (FFmpeg-kit fork or successor) — V1 risk surface; escalated for binding-choice resolution |
| FFmpeg (tooling) | Pipeline I-frame extraction | First-class | Tooling | Subprocess invocation; user-installed; surfaces clean error if FFmpeg not on PATH |
| OpenCV (mobile) | On-device CV (auto-slice + map ID) | First-class | Mobile | Via JSI binding (V1 load-bearing); failure to ship real binding = V1 slip |
| OpenCV (tooling) | Pipeline image processing | First-class | Tooling | `opencv-python>=4.8,<5` per pyproject |

**Notable non-integrations (declarative):**
- **No Discord API integration** — distribution is OS-share-sheet-mediated; Warden does not auth against Discord, does not post to Discord channels via API, does not require Discord OAuth in V1 (deferred to V2).
- **No iOS in V1** — Phase 2 after Apple license validation; FFmpeg-kit fork iOS support TBD per architecture.
- **No external Warden-controlled video infrastructure** — no ingest pipeline, no GPU instances, no transcoding workers; the structural marginal-cost-floor differentiator depends on this absence.

### Risk Mitigations

The brief surfaced eight risk classes. PRD ownership map:

| # | Risk class | PRD owns? | Mitigation |
|---|-----------|-----------|------------|
| 1 | Game-publisher ToS | Partial | PRD requires ToS-monitoring tracker exists (this section); architecture/sprint-planning owns cadence and per-title research depth |
| 2 | On-device performance ceiling | No — escalated | Architecture pre-PRD spike binds reference-device floor with measured numbers; V1 launch blocked on spike completion |
| 3 | ~~Free-tier expectations~~ → **No-free-tier positioning** | Yes (PRD-resolved) | Reframed via no-free-tier decision; activation speed (<5min, Section 2) + on-device privacy + structurally-lower-marginal-cost are the price-justification arguments. Mobalytics/Blitz freemium baseline is irrelevant — different value proposition (analysis tool vs companion overlay) |
| 4 | Brownfield triage backlog | Yes — PRD lists below | See "Brownfield triage backlog disposition" |
| 5 | Auto-slicing accuracy ceiling | Yes (PRD-resolved Section 2) | ≥95% map ID on unseen; round-boundary TBD; graceful degradation per J3; no human-in-the-loop fallback in V1 |
| 6 | Voice + GDPR exposure | Yes (PRD-resolved this section) | On-device-only voice = structural mitigation; subject rights auto-satisfied; consent of third-parties out of Warden's enforcement scope |
| 7 | Discord as distribution rail | Yes (PRD-resolved) | OS-share-sheet-mediated, not API-integrated. If Discord changes ToS or API, the OS share sheet path remains. Warden has no Discord-side dependency |
| 8 | Maintenance surface concentration | No — escalated | Brief acknowledges "maintained as one product" may discover four; explicit maintenance budget thinking owned by `bmad-sprint-planning` |

**Brownfield triage backlog disposition (Risk #4 detail).** Seven items inherited from pre-merge Warden / WardenWeb / Warden-tooling repos:

| # | Item | Surface | V1 disposition |
|---|------|---------|----------------|
| 1 | Stripe API version pin (`2026-03-25.dahlia`) vs installed types (`2026-04-22.dahlia`) | Web | **V1: default-to-bump pending architecture changelog review** (Decision #4 PRD-resolves to "bump unless architecture surfaces concrete breaking-change risk in the 03-25 → 04-22 API delta; freeze fallback if surfaced") |
| 2 | Firestore Security Rules not yet deployed to production (Story 7.1) | Web | **V1-blocking: deploy** before launch; security rules govern entitlement-state integrity |
| 3 | Firebase Auth E2E not fully verified + PlanCta hydration mismatch (Story 7.2) | Web | **V1-blocking: fix** before launch |
| 4 | Vitest parallelism flake | Web | V2 backlog with **V1 CI workaround: run Vitest in serial mode for V1 commits** (parallelism speedup is post-V1 polish; serial-mode bypasses the flake without fixing it) |
| 5 | Firebase v12 `getReactNativePersistence` removed (forcing function) | Mobile | **V1-blocking: migrate** to `@react-native-firebase/*` per Decision #5. **Rationale:** matches Firebase team guidance for RN auth persistence; preserves shared-Firebase-project path with web (Decision #3); non-Firebase-auth is vendor-swap tier and out of brownfield V1 scope; manual MMKV adapter alternative fights upstream guidance and breaks at next Firebase minor. Architecture plans migration sequence. |
| 6 | Foreground Service Android decision | Mobile | Architecture-owned; **decision binds before Sprint 3 commits**. V1 must pick `expo-config-plugin` vs `expo-task-manager` (foreground-service choice affects J2 auto-save-through-interruption behavior) |
| 7 | `map_config.json` schema-version field absent | Tooling | **V1: add `schema_version: 1` field at next regeneration**. Cheap and load-bearing for cross-language schema evolution; without it, schema validators have no backward-compat mechanism when the schema evolves |

**In-flight Sprint 2.5 disposition (brief Decision #11 — RESOLVED in PRD).** Sprint 2.5 mobile stories that are mid-flight at the time of monorepo consolidation **complete as legacy work in the monorepo AFTER per-story unified-PRD conflict audit**. Any story implying a free-tier or pre-no-free-tier flow conflicts with the unified PRD and must be re-scoped into Sprint 3 rather than completed under legacy AC. `bmad-sprint-planning` runs the audit before Sprint 3 commits. Rationale for the audit-gated complete-as-legacy path: forcing the unified Sprint 3 to inherit ALL Sprint 2.5 mid-flight stories adds coordination cost without product benefit; finishing non-conflicting Sprint 2.5 stories cleanly under existing AC, then starting Sprint 3 against the unified PRD with the conflict-flagged subset re-scoped, is lower-risk than either extreme.

**Maps reconciliation (brief Decision #10 — RESOLVED in PRD).** Canonical count: **14 maps**, sourced from `tools/frame_labeler.py:19-34` `MAP_LABELS = [horizon, engine, outlaw, ceres, artefact, silva, bastion, polaris, coliseum, the_cliff, helios, atlantis, the_rock, lunar_outpost]`. The 15-map reference in legacy `map_config_generator.py` spec is stale and should be reconciled to 14. Adding a 15th map per J10 is a future operation, not a V1 reconciliation task.

## Innovation & Novel Patterns

### Detected Innovation Areas

Warden combines five innovations, each load-bearing in the moat narrative. Each is classified by *kind of novelty* so downstream architecture and sprint-planning can size the validation work.

1. **On-device mobile video analysis for esports — architectural novelty.** No direct competitor identified by web research. Cloud platforms (Insights.gg, CoachNow) require uploads; desktop overlays (Mobalytics, Blitz) sit next to the game; replay analysis (Leetify) parses server-side demos for one specific title. Phone-records-gameplay-and-phone-analyzes-it is open. The novelty is the *combination* of FFmpeg + OpenCV-via-JSI + perceptual hashing on a mobile CPU under a < 5min activation budget — a build the on-device-CV community largely skips because most CV apps assume cloud or desktop class.

2. **Reader-App architecture as cross-surface monetization moat — structural novelty.** Reader-App is a known Apple designation (carve-out for content apps that read paid content but don't sell it in-app), but using it deliberately as a 30%-fee bypass for a tool-not-content paid subscription is an under-exploited pattern in the gaming-coaching segment. The novelty is the *commitment depth* — login-only, no IAP, no plan picker, no free tier, build-time-enforced — propagated through every entitlement, monetization, and store-policy decision. Competitors who later adopt the pattern must rebuild their billing surface against it.

3. **Discord-native viral-by-artifact distribution — distributional novelty.** The output of a coaching session is a sharable MP4 a non-installer can watch inline. Distribution IS the product. The novelty is that Warden has *no Discord-side dependency* — distribution is OS-share-sheet-mediated, not API-integrated. If Discord changes, the share path stays. Competitors with Discord OAuth or Discord-bot integration carry vendor risk that Warden does not.

4. **Cross-language schema-driven config pipeline — methodological novelty.** `map_config.json` is the single contract bridging Python tooling (jsonschema validation), TypeScript web (Zod), and TypeScript mobile (consumer). Both languages enforce strictly (`additionalProperties: false`); the contract is the moat, not the code. The novelty is that *new maps roll out as configs, not code*. Honest bound: new *games* require config plus per-title detector tuning, not pure swap.

5. **Activation-event chain under on-device-only constraints — telemetry novelty.** Measuring < 5min activation without sending video frames or audio across the wire requires telemetry carrying only timestamps and event names — never frame data, never voice durations. The novelty is that activation *can* be measured at all under privacy-by-construction, and that the telemetry contract IS the privacy contract.

### Market Context & Competitive Landscape

Per brief web research and detail pack, the relevant competitors and their positioning:

| Competitor | Category | Where they overlap with Warden | Where they DON'T |
|------------|----------|--------------------------------|------------------|
| Insights.gg | Cloud video coaching | Video review for competitive players | Requires upload; no on-device path; multi-title via cloud-CV not config |
| CoachNow | Cloud sports coaching | Voice-annotated video review | Built for physical sports; not gaming-native; cloud-pipeline cost basis |
| Mobalytics, Blitz, Porofessor | Desktop overlay companions | Coaching-adjacent for FPS/MOBA | Sits next to the game (overlay), not the footage; freemium-with-premium model conditions free-tier expectations (Risk #3 — superseded by no-free-tier decision) |
| Leetify | Server-side replay analysis | Tactical analysis | Single-title (CS2); demo-file-based, not screen-recording-based; no other titles supported |
| Generic video editors (CapCut, InShot) | Mobile video editing | Manual clip-and-share | No auto-slice; no minimap-aware ROI; no game-specific anything |
| Onform, CoachNow (physical sports) | Mobile coaching for physical sports | Mobile + voice annotations | Physical sports only; no game-publisher-ToS adjacency; no on-device CV pipeline |

**Headroom per industry research (carried verbatim from brief).** Category-level esports coaching is ~$2.8B in 2025 → ~$9.6B by 2034 (CAGR ~14.7% per industry research). The *coaching software / tooling* slice Warden actually plays in is materially smaller and more honest as a TAM than the headline figure, but the underlying buyer segment (amateur / semi-competitive) is the largest by volume and the named B2C beachhead.

**FR/BE EVA After-h beachhead.** ~300+ active teams; word-of-mouth dominant acquisition. Brief explicitly notes that the headline TAM and the beachhead size are different orders of magnitude — the PRD must not conflate them, and `bmad-sprint-planning` must not size V1 against the headline number.

### Validation Approach

Each innovation needs measurable evidence to validate the claim or surface failure early. Mapped per innovation:

| # | Innovation | What validates? | What refutes? | Measurement |
|---|-----------|-----------------|---------------|-------------|
| 1 | On-device CV pipeline | Performance floor met on reference device per architecture spike (Risk #2 escalation); accuracy floors met (≥95% map ID, round-boundary TBD per Section 2); JSI binding ships as real binding | Reference-device performance below floor; accuracy below floor on unseen test set; JSI binding fails to ship as real binding (V1 launch blocker) | Architecture-published performance number on reference device; `hash_validator` regression suite; CI test for JSI-binding-not-stub |
| 2 | Reader-App moat | Build-time CI gate passes on every V1 mobile build (zero monetization-surface artifacts, including transitive deps); App Store / Play Store reviews accept the Reader-App posture without forcing IAP | CI gate fails on mainline; store reviewer rejection forcing IAP; competitor copies the pattern within 6 months at lower friction | CI gate green-rate on mainline; first store review outcome; competitor monitoring (V2 deferred but worth tracking) |
| 3 | Discord-native distribution | J5 inline-playback works on Discord without app install; Coupon → Retained ≥10% post-trial (Section 2) | Discord changes preview behavior to require app install; Coupon → Retained < 10% (signals funnel doesn't convert curiosity) | Manual J5 verification at V1 launch; ongoing Stripe coupon-redemption tracking |
| 4 | Cross-language schema pipeline | Both schema validators (Zod + jsonschema) green on every V1 build; J10 developer journey runs end-to-end without manual schema patching; new map added via config-only path | Schema drift between web and tooling; J10 requires manual schema edits; new map requires code changes beyond config | CI green on both schema validators; J10 manual run at V1 launch + one additional map added pre-V2 |
| 5 | Activation-event-chain telemetry | Firebase Analytics events (`activation_timer_started`, `activation_timer_completed`) emitted on every J1 / J2 path; J4 dual-T1 instrumentation distinguishes coach vs active-player paths; zero frame/audio data in telemetry payload | Telemetry events not emitted reliably; T1 fires on share-sheet open instead of dispatch; payload contains forbidden fields | Telemetry-presence audit on V1 builds; payload schema validation; on-device sampling |

### Risk Mitigation

Innovation-specific fallback ladders not covered in Section 5's Risk Mitigations table. Each innovation has a *graceful-degradation path that preserves the moat*; the explicit anti-pattern is "fall back to cloud" (which would break the structural moat).

- **Innovation #1 (on-device CV) — fallback ladder.** If reference-device performance falls below floor: (a) lower auto-slice frame-sampling rate (longer auto-slice but still on-device); (b) drop Minimap+HUD overlay rendering on weak hardware (graceful UI degradation per J3); (c) defer JSI binding to V2 and ship V1 with tested-via-injection stub limited to manual-clip path only — V1 launch slip but moat preserved. **Anti-pattern:** moving CV to cloud. That breaks Differentiator #3 (on-device privacy + structurally lower marginal cost) and is not a permitted fallback.

- **Innovation #2 (Reader-App moat) — store-policy fallback.** If Apple/Google reviewer forces IAP: (a) Android-first V1 (current scope already iOS-deferred); (b) contest Apple ruling via Reader-App appeal process; (c) worst case — iOS V2 ships with a different monetization model OR Warden remains Android-only indefinitely. **Anti-pattern:** capitulating to 30% fee. That breaks the price-competitive positioning and forces a 30% revenue haircut on every paying coach.

- **Innovation #3 (Discord-native distribution) — distribution-rail fallback.** If Discord changes inline-playback behavior, share path defaults to OS share sheet → alternate apps (Messages, Drive, WhatsApp, etc.). Risk #7 from brief is already addressed: Warden has no Discord-API dependency, only an OS-share-sheet target preference. **Anti-pattern:** integrating with Discord API to "guarantee" inline playback. That introduces vendor risk Warden currently does not have.

- **Innovation #4 (cross-language schema pipeline) — schema-evolution fallback.** If schema validators diverge mid-V1: lock the schema at V1 launch (no config evolution until V2); accept manual schema-version coordination. Item 7 in brownfield triage (V1: add `schema_version: 1`) pre-mitigates this. **Anti-pattern:** dropping one validator (e.g., remove jsonschema from tooling). The cross-language nature IS the moat.

- **Innovation #5 (activation telemetry) — measurability fallback.** If on-device-only telemetry proves insufficient (e.g., Firebase Analytics throttling drops events), fallback is to add server-side activation inference from Stripe webhook event timing + first Firestore read of `users/{uid}` post-checkout. This adds a measurement layer without sending video data — the privacy contract holds, but the telemetry is less precise. **Anti-pattern:** sending frame data or voice samples in telemetry payloads. That breaks the on-device-only privacy contract regardless of measurability gain.

## Per-Surface Specific Requirements

This section documents project-type-specific technical requirements per surface. Driven by the CSV `key_questions` and `required_sections` for each project_type. Skip sections per CSV are honored: mobile skips desktop_features + cli_commands; web skips native_features + cli_commands; tooling skips visual_design + ux_principles + touch_interactions.

### Mobile (mobile_app) Specific Requirements

**Project-Type Overview.** Cross-platform mobile app via Expo / React Native; Android-first V1; iOS Phase 2 (deferred per brief). Login-only Reader-App architecture with no monetization surface. On-device-only video processing pipeline. Voice annotation. Cinema Mode review experience.

**Platform Requirements.**
- **Cross-platform via Expo / React Native** with Expo SDK (version pinned by Expo init; not separately bound).
- **V1 platform target: Android only.** iOS Phase 2 — deferred until (a) Apple license validated, (b) FFmpeg-kit fork (or successor) iOS support confirmed working per architecture, (c) Reader-App posture validated against Apple App Review per Innovation #2 fallback ladder.
- **Reference device target:** TBD per architecture pre-PRD spike (brief Risk #2 escalation). Reference device floor binds the on-device CV ceiling. PRD inherits the spike result; V1 launch criteria includes spike completion.
- **Screen sizes supported:** 5.5"–6.7"+ (per UX distillate adaptive layout); reference device Poco X5 (6.67").
- **Orientation:** no orientation lock (per UX distillate); landscape and portrait both supported with adaptive layouts.

**Device Permissions / Capabilities.**
- **File system access** — read-only access to device gallery / recordings folder for session import. Write access to app sandbox for clip output and MMKV state.
- **Microphone access** — required for voice annotation recording (3 slots: before / during / after).
- **Storage** — app sandbox + shared storage for clip output. No full-storage permission required.
- **Background processing (Android Foreground Service)** — required for export-during-background and auto-save through interruption (J2). Choice between `expo-config-plugin` vs `expo-task-manager` — architecture-owned; **decision binds before Sprint 3 commits** (brownfield triage item 6).
- **No camera permission** — Warden does NOT record game footage on the user's behalf (Section 5 screen-recording-policy boundary). Capture is import-only.
- **No location, contacts, or biometric permissions** — none required.
- **No push notification permission** — out of V1 scope (engagement re-prompts are anti-pattern per UX distillate emotional design; "review is play not work").

**Offline Mode (load-bearing).**
- **Full offline review** during 30-day offline-grace window. App fully usable while disconnected: Card View, Cinema Mode, view-mode toggle, clip creation, voice recording, export to OS share sheet (J9 train journey).
- **30-day MMKV-cached entitlement** validates offline. Day-31 force re-auth on next foreground.
- **No background sync requirement** — offline state is the steady state for J9; no need for background reconnection logic. App re-fetches entitlement on next foreground when online.
- **Offline export** writes to local sandbox; OS share sheet handles offline target gracefully (queues for next connectivity OR user picks an offline-capable share target).

**Push Strategy (V1: NONE).**
- V1 ships with **no push notification implementation**. Deliberate.
- **Rationale:** brief emotional design rejects "fake urgency, countdown timers, guilt-trip on cancel" — push notifications are the engagement-reprompt anti-pattern Warden explicitly rejects. The product is summoned (coach opens app to review), not pushed.
- **No FCM / APNS integration in V1.** If push is added in V2, the architectural gate is: only transactional pushes (e.g., subscription renewal reminder if PRD adds one), never engagement pushes ("you haven't reviewed in 3 days").

**Store Compliance (Reader-App posture).**
- Already covered in Section 5 (Compliance & Regulatory > App Store Reader-App policy). Restated for project-type completeness:
  - Mobile builds contain zero monetization-surface artifacts (CI-gated, signaling-tier, transitive-dep scan included).
  - Login-only against Stripe-issued credentials (the entitlement source is web).
  - Reviewability posture: "Stripe via web; mobile has no store-billable transaction."
- **Google Play V1 review-readiness checklist** required before submission; location TBD (likely `apps/mobile/RELEASE.md`).

**Skipped per CSV (mobile_app skip_sections):** `desktop_features` (no desktop port in V1; V3 vision item), `cli_commands` (mobile is GUI-only; tooling owns CLI surface).

### Web (web_app) Specific Requirements

**Project-Type Overview.** Next.js 16 marketing + Stripe portal under `apps/web`. Three routes (Landing, Pricing, Dashboard). Stripe Checkout + Customer Portal as full-page redirects. Webhook-driven `users/{uid}` writes (server-only). Direction A "Clean Minimal" UX. English UI with FR-locked hero.

**SPA or MPA?** Hybrid:
- **Landing (`/`)** — SSR + cached. Optimized for first-paint and Discord-card preview.
- **Pricing (`/pricing`)** — client-interactive (auth modal, Stripe Checkout redirect). SSR-rendered shell with client-side interactivity.
- **Dashboard (`/dashboard`)** — protected SPA-flavored route. Server-side auth check + fresh client-side Firestore reads (no `onSnapshot` per legacy UX distillate rejected-alternative).

**Browser Matrix.**
- **Modern browsers only.** Chrome/Edge ≥ last 2 major; Firefox ≥ last 2 major; Safari ≥ 15. No IE11. No Opera Mini.
- **Mobile + desktop.** Mobile is the dominant screen for first-time visitors (Discord coupon link from phone); desktop secondary.
- **Breakpoints (only two):** mobile (default, no prefix) + `md:` (768px+). No tablet-specific layout per UX distillate.

**Responsive Design.**
- **Mobile-first** layout per UX distillate. Stacked cards on mobile; side-by-side on desktop.
- **Touch targets ≥ 44×44px** on mobile (`min-h-11 min-w-11`).
- **Max content width 1024px** centered; page padding 16px mobile / 32px desktop.

**Performance Targets.**
- **First Contentful Paint:** ≤ 1.5s on 4G mobile (Lighthouse target).
- **Largest Contentful Paint:** ≤ 2.5s on 4G mobile.
- **Cumulative Layout Shift:** ≤ 0.1.
- **Time to Interactive on Pricing:** ≤ 3s (the auth modal + Stripe Checkout redirect must feel snappy — first-time users came from a Discord link, attention is fragile).
- **Vercel Edge / CDN delivery** for landing assets; dashboard data fresh from Firestore (no client-cache-first).

**SEO Strategy.**
- **Landing (`/`)** — full SEO target. Meta tags (title, description), Open Graph (Discord card preview is THE channel-relevant preview surface), Twitter Card. Sitemap + robots.txt.
- **Pricing** — partial SEO (Open Graph for shareability; not aggressively keyword-targeted).
- **Dashboard** — `noindex`; protected user data.
- **No JS-required content on landing** — fallback to SSR HTML for crawlers and Discord's preview fetcher.

**Accessibility Level (WCAG 2.1 Level A).**
- Per UX distillate: color contrast AA; keyboard nav (Radix primitives default); 2px orange focus-visible outline; semantic HTML (`<nav>`, `<main>`, `<footer>`, `<h1-3>`, `<button>`); labeled inputs; status badges with text+color (not color-only); `prefers-reduced-motion` respected; skip-to-content link; alt text on logo.
- **Testing strategy:** Browser DevTools contrast check; manual keyboard tab-through; Chrome device mode + real phone; `npx lighthouse` accessibility in CI; VoiceOver pass before launch. Full audit deferred post-MVP.

**Real-time? NO.**
- No WebSocket or `onSnapshot` listeners. Webhook-driven async sufficient; DB is source of truth refreshed on dashboard load.
- This is a DELIBERATE constraint — adding real-time would inflate Firebase reads, complicate rules surface, and provide no user-visible benefit (subscription state changes are minute-grain at best).

**Skipped per CSV (web_app skip_sections):** `native_features` (no native bridge — Stripe is full-page redirect, not embedded), `cli_commands` (tooling owns CLI surface).

### Tooling (cli_tool) Specific Requirements

**Project-Type Overview.** Python ≥3.11 CLI suite under `apps/tooling`. uv-managed workspace member. Five user-facing tools (`game_detector`, `frame_labeler`, `map_config_generator`/`hash_comparator`, `hash_validator`, `warden_analyzer`) plus diagnostic tools (`image_inspector`, `bsd_roi_debugger`, `points_state_detector`). TUI launcher (`questionary`) over argparse-based CLIs.

**Command Structure.**
- **Each tool is a standalone CLI script** in `tools/` (or sub-package `tools/<tool>/` with `__main__.py` + `app.py` + helpers).
- **Argparse-based** with consistent conventions: positional `video`, `-o/--output-dir`, `-c/--config` (default `config/config.yaml`), `--threshold`, `--profile`, `--roi`. Mutually-exclusive groups for input modes.
- **Single entry-point TUI launcher** (`wardentooling.py` at project root) wraps the CLIs via subprocess (`subprocess.run([sys.executable, ...])`) for streamed output and to avoid tkinter side-effects.
- **`sys.path.insert`** pattern for cross-module imports (`utils.*`).

**Output Formats.**
- **JSON:** `map_config.json` (cross-language schema-validated; canonical artifact), `rounds.json` (warden_analyzer output), `accuracy_report.json` (hash_validator output), `inspector_log.jsonl` (image_inspector logs).
- **PNG:** frame extracts (`{timestamp}_{type}_{seqnum}.png` from BSD; `{counter:03d}_{type}.png` from labeled output; preview canvases from hash_comparator with `--preview`).
- **YAML:** `config/config.yaml` (configuration; user-editable; loaded via `utils/config.py:load_config()`).
- **No proprietary formats.** All outputs are interoperable with downstream Python / TypeScript consumers.

**Config Method.**
- **YAML-first** (`config/config.yaml`); CLI args override config (`arg if arg is not None else config.get(...)`).
- **"None = feature disabled" convention** for optional pipeline params (e.g., `text_anchor_width`, `threshold_hash`) — backward compat free.
- **No environment-variable config** — CLI/YAML only. Avoids shell-state bleed into pipeline runs.

**Scripting Support.**
- **Both interactive and scriptable.** TUI launcher for interactive workflow (`questionary`-based; requires TTY; silent failure on pipe/redirect — known risk). Each underlying tool callable directly via argparse for scripting.
- **No `--no-tui` headless flag** in V1 (deferred per tooling distillate; would mirror underlying tool args for scripting).
- **Last-run persistence** (`.warden_last_run.json`) supports re-run-with-same-args after successful exit; gitignored.
- **Exit codes** — propagated from underlying tool subprocess to TUI launcher; saved-only-on-success persistence.

**Schema Validation Integration (V1-load-bearing per Innovation #4).**
- **`map_config.json` strictly validated** by `jsonschema` on tooling side (runtime / CI). Cross-language counterpart on web side (Zod, build-time).
- **`schema_version: 1` field added at next regeneration** (brownfield triage item 7; reclassified V1 per Step 5 elicitation refinement).

**Skipped per CSV (cli_tool skip_sections):** `visual_design` (CLI is text-only; tkinter diagnostic tools are out of CLI scope), `ux_principles` (CLI ergonomics covered under command-structure), `touch_interactions` (no touch surface).

### Cross-Surface Implementation Considerations

Implementation considerations that span surfaces are already covered earlier in the PRD; pointer-only here to avoid duplication:
- **Reader-App build-time enforcement** — Section 5 (Compliance & Regulatory).
- **Cross-language schema enforcement** — Section 5 (Technical Constraints) + Section 6 Innovation #4.
- **30-day offline auth-cache + entitlement state machine** — Section 2 (Technical Success).
- **Performance floor (escalated to architecture pre-PRD spike)** — Section 2 + Section 5.
- **Brownfield triage backlog dispositions** — Section 5 (Risk Mitigations).
- **Cross-language contracts location (`packages/contracts/`)** — escalated to architecture for confirmation.

## MVP Strategy & Scoping Risks

### MVP Strategy & Philosophy

**MVP Approach: Experience MVP** — the < 5min activation experience IS the validation, not the feature count. Warden's V1 is not a *problem-solving* MVP (the problem is widely understood — coaches juggle laptops + notepads + editors), nor a *platform* MVP (extensibility comes in V3 with multi-title), nor a *revenue* MVP (revenue scales with WoM, not feature breadth). It is an *experience* MVP: the validation question is **"does the on-device, sub-5min, voice-annotated tactical-clip experience actually delight Coach Thomas?"** Everything else — billing, web portal, tooling pipeline — is in service of putting that experience in front of paying coaches.

**MVP rationale (why this V1 and not smaller).** Three structural commitments make a smaller V1 architecturally infeasible:

1. **Reader-App contract is all-or-nothing.** Mobile cannot ship without the web Stripe portal — there is no IAP fallback. Web is V1 because mobile cannot exist alone.
2. **On-device CV is all-or-nothing for activation.** Auto-slicing IS the < 5min activation moment. Skipping auto-slicing reduces V1 to a manual-clip tool, which doesn't differentiate from generic video editors (anti-pattern per Section 6 competitive landscape).
3. **`map_config.json` is all-or-nothing for accuracy.** Tooling V1 must include the regression-validation pipeline (`hash_validator`) because below-floor accuracy ships broken activation experiences (Section 2 Risk #5).

These three force V1 scope to span all three surfaces. There is no "MVP-1 mobile only" path that ships a working product.

**Resource requirements.** Solo dev (Stephane). Firebase + Stripe + Vercel + Expo simplify backend / infra to a near-zero ops burden. The architecture pre-PRD spike (brief Risk #2 escalation) is the highest-leverage time investment before V1 commits, because the spike binds the reference-device floor that the entire activation experience depends on.

### MVP Feature Set (V1)

**Core user journeys supported in V1:** J1 (first-time activation), J2 (steady-state with interruption), J3 (CV failure modes), J4 (Active Player solo), J5 (Discord-inline-playable), J6 (Passive→Active conversion), J7 (payment failure recovery), J8 (cancellation), J9 (offline-grace), J10 (developer regenerates map_config). All ten journeys are V1.

**Must-have capabilities:** see Section 3 (Product Scope > MVP — Minimum Viable Product) and Section 7 (Per-Surface Specific Requirements). Pointer-only to avoid duplication; the Section 3 list is authoritative.

**Out-of-scope user journeys (V1 explicitly):** Admin / Operations (no admin UI; coupon management via Stripe dashboard); Support (manual via support email); API consumer (no external API). Documented in Section 4 (User Journeys > Out-of-scope journeys).

### Post-MVP Features

**V2 (Growth) — already documented in Section 3.** Pointer to Section 3 (Product Scope > Growth Features) for the full list. Highlights:
- Discord OAuth + coupon admin UI + custom analytics dashboard (web)
- OCR scores/kills + stats per map + advanced ROI composition + vertical export (mobile)
- Review-import mode (closes J4 partial-support gap)
- Export queue with background encoding (replaces V1's encode-immediately-then-share UX)

**V3 (Vision) — already documented in Section 3.** Pointer to Section 3 (Product Scope > Vision) for the full list. Highlights:
- Broader tactical-FPS coaching companion (CS2 / Valorant / R6 — config + per-title detector tuning)
- Referral system + full French localization + iOS + Desktop
- Discord stream group review

### Risk Mitigation Strategy (Scoping-Specific)

These risks are SCOPE risks — what could push V1 to slip or misfire. Distinct from product risks (Section 5).

**Technical risks (what could push V1 to slip):**
- **OpenCV JSI binding ships as stub-not-real.** V1-load-bearing per Section 2 + Section 6 Innovation #1. Mitigation: architecture's pre-PRD spike (Risk #2) includes JSI binding feasibility validation; if spike returns "binding cannot ship in V1 timeline," fallback per Innovation #1 ladder (drop auto-slice from V1; manual-clip-only V1; auto-slice deferred to V2). This is a scope-flexible fallback, not a launch slip.
- **Firebase v12 RN auth migration takes longer than estimated.** Brownfield triage item 5; V1-blocking. Mitigation: architecture plans the migration sequence early in Sprint 3; if migration risk surfaces late, the fallback is to ship V1 on the current Firebase v11 line and migrate in V1.1 — but this depends on Firebase v12 *not* dropping the symbol entirely before V1 ships (the forcing function).
- **Performance floor from architecture spike below acceptable threshold.** Mitigation: Innovation #1 fallback ladder (lower frame-sampling rate, drop Minimap+HUD overlay on weak hardware, JSI deferral). All preserve the moat.

**Market risks (what could push V1 to misfire even if technically successful):**
- **Demand evidence not captured before launch.** Section 2 demands interview count + waitlist depth + WTP validation. Mitigation: capture during Phase 6 / Phase 7 prep — explicit demand-evidence sprint before V1 commit. If evidence is weak (e.g., < 5 coach interviews validate the workflow change), the right move is to delay V1 launch and run more validation, NOT to launch and hope.
- **Coupon → Retained < 10%.** WoM-driven Discord-distribution validator. Mitigation: post-V1 rapid-iteration on landing copy + coupon presentation; if the metric stays below 10% after 3 months, re-baseline pricing positioning (Decision #12 deferred-revisit clause kicks in).
- **Competitor enters the niche during V1.** Section 6 Innovation #1 names a defensibility clock; the lead time IS the asset. Mitigation: ship V1 quickly and reach the Discord-distribution flywheel before any fast-follower can rebuild the on-device pipeline. Maintenance-surface concentration (Risk #8) is the inverse — if V1 takes too long, we lose the lead.

**Resource risks (what could push V1 to slip from solo-dev capacity angle):**
- **Solo dev capacity constraint.** Brief explicitly notes "RESOURCE: solo dev — ultra-lean MVP." Mitigation: aggressive scope discipline — V1 is locked at the Section 3 list; V2 deferrals are not negotiable; brownfield triage items 4 (Vitest) and 7 (`schema_version`) were deliberately positioned to keep solo-dev capacity focused on load-bearing work.
- **Maintenance surface concentration (brief Risk #8).** Three apps + Stripe webhooks + Firestore rules + Expo build matrix + Python tooling — the brief warns this may discover four products instead of one. Mitigation: explicit maintenance budget thinking owned by `bmad-sprint-planning` (escalated). PRD requires sprint planning explicitly model maintenance per surface, not lump it.
- **Sprint 2.5 disposition adds coordination cost.** Mitigation: per-story conflict audit before completion (refined in Section 5); flagged conflicts re-scope into Sprint 3 cleanly.

## Functional Requirements

This section is the **capability contract** for Warden V1. Every downstream artifact (UX design, architecture, epics, stories, tests) traces back here. **If a capability is missing from this list, it will not exist in V1.**

**ID scheme.** FRs are surface-prefixed (`mobile-`, `web-`, `tooling-`, `cross-`) and capability-area-grouped. The prefix indicates which deploy unit owns the implementation; `cross-` indicates a binding requirement that spans surfaces and is not owned by any single deploy unit.

**Traceability.** Each FR notes the journey (J1–J10) or PRD section that revealed it. FRs without a journey trace are derived from Section 5 / 6 / 7 constraints.

**Altitude.** FRs state WHAT capability exists, not HOW it is implemented. Performance numbers, UI specifics, and technology choices are NFRs (Section 10) or implementation details (architecture).

### Mobile (`apps/mobile`)

#### Authentication & Entitlement

- **mobile-AUTH-001:** User can sign in to the mobile app using Google or email/password credentials issued via the web Stripe flow. *(J1, J6)*
- **mobile-AUTH-002:** Mobile validates active entitlement against `users/{uid}.status` from Firestore on first foreground after sign-in, and refreshes on app foreground after a Stripe Customer Portal round-trip. *(J1, J7)*
- **mobile-AUTH-003:** Mobile rejects login (and presents a "subscription required" screen with deep-link to web Customer Portal) for any entitlement state other than `paid` or `offline-grace ≤30d`. *(J8; Section 2 no-free-tier)*
- **mobile-AUTH-004:** Mobile maintains entitlement validity for 30 days after last successful Firestore read; on day 31, forces re-auth on next foreground. *(J9)*
- **mobile-AUTH-005:** Mobile preserves user-generated session data (clips, voice annotations, MMKV state) across entitlement-state transitions, including lapse → resubscribe restoration. *(J8)*
- **mobile-AUTH-006:** Mobile presents a payment-failure warning banner with deep-link to Stripe Customer Portal when entitlement state is `payment-failed`. *(J7)*

#### Session Import & Auto-Slicing

- **mobile-IMPORT-001:** User can import a recorded gameplay video file from the device's gallery or file system. *(J1, J6)*
- **mobile-IMPORT-002:** Mobile rejects unsupported codec / container formats with a clear, actionable error. *(brief codec-unsupported risk)*
- **mobile-AUTO-SLICE-001:** Mobile auto-slices an imported session into per-round Cards using on-device round-boundary detection. *(J1, J6) (load-bearing on OpenCV JSI binding shipping as real binding)*
- **mobile-AUTO-SLICE-002:** Mobile auto-identifies the map for each round using on-device perceptual hashing against `map_config.json`. *(J1, J6) (load-bearing on OpenCV JSI binding)*
- **mobile-AUTO-SLICE-003:** Mobile marks `map_name = "unknown"` when map identification confidence is below the recognition threshold; navigation and Cinema Mode remain available. *(J3)*
- **mobile-AUTO-SLICE-004:** Mobile auto-removes lobby footage from the Card View. *(J1)*

#### Card View & Triage

- **mobile-CARD-001:** User can view all auto-sliced rounds as Cards in a grid (Card View) with adaptive column count by screen size.
- **mobile-CARD-002:** User can sort Cards by temporal (default), orange biggest win, blue biggest win, or closest map; sort persists across sessions. *(UX distillate; score-based sorts gracefully degrade to temporal until OCR ships in V2)*
- **mobile-CARD-003:** User can tap a Card to open Cinema Mode for that round.
- **mobile-CARD-004:** Cold-start Card View offers "Resume last review" or "Import new session"; never blank state. *(UX distillate)*
- **mobile-CARD-005:** Auto-slice-missed rounds remain accessible via the Cinema Mode timeline (no Card required) so the user can manually create clips for them. *(J3)*

#### Cinema Mode

- **mobile-CINEMA-001:** User can review a round in Cinema Mode (immersive video player with reveal-on-tap controls auto-hiding after inactivity). *(J1, J4)*
- **mobile-CINEMA-002:** User can switch view modes among Full / Minimap / Minimap+HUD via a top-level segmented control AND via a double-tap gesture on the top-left of the screen. *(J1, J4)*
- **mobile-CINEMA-003:** Mobile defaults Cinema Mode to Full view when the round's `map_name` is "unknown" (no minimap ROI available). *(J3)*
- **mobile-CINEMA-004:** Mobile persists the last-used view-mode preference. *(J4)*
- **mobile-CINEMA-005:** User can navigate to next / previous round via explicit Next / Previous buttons. *(UX distillate — swipe rejected to avoid timeline-scrub conflict)*

#### Clip Creation & Voice Annotation

- **mobile-CLIP-001:** User can create a 30-second clip region centered on the current Cinema Mode playback position, with bracket-handle refinement controls. *(J1)*
- **mobile-CLIP-002:** User can manually create a clip from any point in the Cinema Mode timeline, not requiring an auto-sliced Card. *(J3)*
- **mobile-CLIP-003:** User can record a voice annotation in any of three slots — before, during, or after the clip — independently and optionally; silent clips skip all voice segments. *(J1, J2, J5)*
- **mobile-CLIP-004:** User can re-record (overwrite) a voice slot after recording. *(J2)*
- **mobile-CLIP-005:** User can preview a clip with voice annotations before exporting.

#### Export & Share

- **mobile-EXPORT-001:** User can export a clip as a standalone MP4 file via on-device FFmpeg encode (no cloud encode path exists). *(J1; Section 5 on-device-only)*
- **mobile-EXPORT-002:** Mobile offers two encode quality tiers (Mobile and HD).
- **mobile-EXPORT-003:** Mobile dispatches the exported MP4 via the OS share sheet on encode completion. *(J1)*
- **mobile-EXPORT-004:** Exported MP4 is a vanilla H.264/AAC container compatible with Discord's inline preview pane (and equivalent inline-preview targets in other share-receivers). *(J5 — load-bearing for distribution moat)*

#### Auto-save & Crash Recovery

- **mobile-AUTOSAVE-001:** Mobile silently auto-saves clip-creation state (region, voice annotations, in-progress recording) without user-visible prompts. *(J2)*
- **mobile-AUTOSAVE-002:** Mobile resumes Cinema Mode at the exact frame, with clip region and any in-progress voice annotation preserved, after the app is backgrounded, closed, or crashed. *(J2)*

### Web (`apps/web`)

#### Landing & Pricing

- **web-LANDING-001:** Web serves a marketing landing page (`/`) with the FR-locked hero tagline (*"Progresser plus vite en investissant moins de temps."*) and a single primary CTA leading to `/pricing`. *(J1, J6)*
- **web-LANDING-002:** Landing renders SSR HTML for crawlers and Discord card-preview fetchers (no JS-required content for Open Graph / Twitter Card metadata). *(Section 7)*
- **web-PRICING-001:** Web serves a pricing page (`/pricing`) with two plan cards (€7.99/mo, €79.90/yr) and a Stripe coupon URL parameter that auto-applies coupons from Discord links. *(J1, J6)*
- **web-PRICING-002:** Pricing page presents an authentication modal (Google + Email/Password) before initiating Stripe Checkout. *(J1, J6)*

#### Authentication & Checkout

- **web-AUTH-001:** User can sign in or register on web via Google OAuth or email/password through Firebase Auth. *(J1, J6)*
- **web-CHECKOUT-001:** Web redirects authenticated users to Stripe Checkout (full-page, Stripe-hosted) with the selected plan and any auto-applied coupon, with French deferred-billing copy ("*Vous ne serez pas débité avant le [date]*"). *(J1, J6; Section 5 PCI-offloaded)*
- **web-CHECKOUT-002:** Web returns the user to `/dashboard?success=1` upon Checkout completion, with status badge reflecting the new entitlement. *(J1)*

#### Dashboard

- **web-DASHBOARD-001:** Web serves a protected `/dashboard` route (server-side auth check + fresh client-side Firestore reads; **no `onSnapshot`**) showing the user's email, plan, status badge, next payment date, and a "Manage Subscription" deep-link to Stripe Customer Portal. *(J1, J7, J8)*
- **web-DASHBOARD-002:** Dashboard presents a payment-failure warning banner with "Update payment method" deep-link when entitlement state is `payment-failed`. *(J7)*
- **web-DASHBOARD-003:** Dashboard presents a "Canceling" status badge and "Resubscribe" CTA when subscription is cancel-at-period-end. *(J8)*
- **web-DASHBOARD-004:** Dashboard cancellation flow presents a confirmation dialog ("access until [date]") with no exit survey and no guilt-trip CTA. *(J8 anti-dark-pattern policy)*
- **web-DASHBOARD-005:** Dashboard presents a "No active subscription" empty state with link to `/pricing` when user has no subscription. *(UX distillate)*

#### Webhook Processing

- **web-WEBHOOK-001:** Web ingests Stripe webhooks (`invoice.payment_succeeded`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `checkout.session.completed`) via a server-only endpoint with Stripe signature verification. *(J1, J7, J8)*
- **web-WEBHOOK-002:** Webhook handlers are dual-strategy idempotent: event-ID deduplication via `stripe_events/{event_id}` document existence check AND business-state observation (re-applying the same event to an already-correct state is a no-op). *(Section 5 Technical Constraints)*
- **web-WEBHOOK-003:** Webhook handlers write `users/{uid}` from server only; client writes are denied by Firestore Security Rules. *(Section 2 Reader-App; Section 5 brownfield triage item 2)*

#### Analytics

- **web-ANALYTICS-001:** Web emits Firebase Analytics events for the funnel stages: Visit, CheckoutStart, CheckoutComplete, Coupon-applied, Coupon-Retained-past-deferred-billing. *(Section 2 Web funnel; Section 6 Validation Approach)*

### Tooling (`apps/tooling`)

#### Round Detection & Frame Extraction

- **tooling-ROUND-DETECT-001:** Developer can run round-boundary detection on a recorded video (BSD or `game_detector`) and produce per-round PNG outputs (start, end, score frames). *(J10)*
- **tooling-ROUND-DETECT-002:** Round detection emits a miss-report listing missed-end / missed-start windows for manual inspection. *(tooling distillate)*

#### Frame Labeling

- **tooling-LABEL-001:** Developer can label score-frames into per-map directories via `frame_labeler`; co-export of paired start/end frames is automatic. *(J10)*
- **tooling-LABEL-002:** Frame labeler imports `MAP_LABELS` (14 canonical maps) from `tools/frame_labeler.py:19-34` as the single source of truth. *(Section 5 Maps reconciliation)*

#### Hash Generation & Map Config

- **tooling-HASH-001:** Developer can run `hash_comparator` (or `map_config_generator`) on labeled per-map frames and emit `map_config.json` with per-map reference hashes. *(J10)*
- **tooling-HASH-002:** Emitted `map_config.json` includes `schema_version: 1` and the pipeline parameters (`text_anchor_width`, `threshold_hash`, `recognition_threshold`) needed to reproduce the hashes at validation time. *(Section 5 brownfield triage item 7; tooling distillate parity fix)*

#### Hash Validation

- **tooling-VALIDATE-001:** Developer can run `hash_validator` on labeled directories against `map_config.json` and produce a per-map accuracy report (`accuracy_report.json`). *(J10)*
- **tooling-VALIDATE-002:** Hash validator reuses pipeline parameters from `map_config.json` (not from `config.yaml`) to guarantee generation/validation alignment. *(tooling distillate parity fix)*

#### End-to-End Pipeline

- **tooling-WARDEN-001:** Developer can run `warden_analyzer` end-to-end on a video and `map_config.json` to produce score frames + `rounds.json` (per-round map identification + timers). *(tooling distillate Tool 5)*

#### TUI Launcher

- **tooling-TUI-001:** Developer can launch any tool interactively via `wardentooling.py` TUI launcher. *(J10)*
- **tooling-TUI-002:** TUI launcher supports re-run-with-same-args after successful exit (via `.warden_last_run.json`). *(tooling distillate)*

#### Schema Validation

- **tooling-SCHEMA-001:** Tooling validates emitted `map_config.json` against `contracts/map-config.schema.json` (jsonschema, strict — `additionalProperties: false`) at runtime / CI. *(Section 5 cross-language schema; Section 6 Innovation #4)*

### Cross-Surface (binding requirements)

#### Entitlement State Machine

- **cross-ENTITLEMENT-001:** All surfaces (mobile, web) consume the same six-state entitlement model: `paid` / `lapsed` / `offline-grace ≤30d` / `payment-failed` / `multi-device` / `signed-out`. State semantics are defined in Section 2; transition rules and triggering events are owned by architecture. *(J7, J8, J9)*
- **cross-ENTITLEMENT-002:** Web is the sole writer of `users/{uid}` entitlement fields (server-only, via Stripe webhooks); mobile reads but never writes. *(Section 5)*

#### Activation Event Chain Telemetry

- **cross-ACTIVATION-001:** Mobile emits `activation_timer_started` (T0) on auth-state-change → `paid` and `activation_timer_completed` (T1) on share-sheet confirmed-dispatch (coach path) OR Cinema Mode opened with view-mode toggled at least once (active-player path). *(Section 2 dual-T1; J1, J4)*
- **cross-ACTIVATION-002:** Activation telemetry payloads carry only timestamps and event names — never frame data, voice durations, or raw audio. *(Section 5 on-device-only privacy contract)*

#### Schema Contract Conformance

- **cross-SCHEMA-001:** `map-config.schema.json` is a first-class repo artifact under `packages/contracts/` and is enforced strictly (`additionalProperties: false`) on web (Zod, build-time) AND tooling (jsonschema, runtime / CI). *(Section 5; Section 6 Innovation #4)*
- **cross-SCHEMA-002:** `user-doc.schema.json` schema duplication is resolved via a single canonical schema (resolution path escalated to architecture per brief Decision #1). *(Section 5 brownfield triage; brief Decision #1)*

#### Reader-App Build Gate

- **cross-READER-APP-001:** Mobile build artifacts contain zero monetization-surface artifacts. CI gates: direct-import bans (`react-native-iap`, `expo-in-app-purchases`, Stripe Mobile SDK), transitive-dependency scan (`pnpm ls --depth=Infinity` reports zero entries for banned packages), pricing-string bans (€7.99, €79.90, "subscribe", "buy", "monthly", "yearly", and locale equivalents in source and i18n bundles). Gate is signaling-tier defense-in-depth, not absolute prevention; intentional bypass is a code-review responsibility. *(Section 5 Reader-App)*

#### map_config.json Runtime Delivery

- **cross-MAP-CONFIG-DELIVERY-001:** Mobile consumes `map_config.json` at runtime for on-device map identification. **Delivery mechanism (Firestore-fetched vs Metro-bundled vs hybrid) is moat-shaping per brief Decision #2 — escalated to architecture for resolution. PRD does not pre-decide.** *(Section 5; Section 6 Innovation #4 honest bound)*

## Non-Functional Requirements

This section specifies **how well** Warden V1 must perform. NFRs are testable quality attributes; FRs are testable capabilities. Where an NFR target is already named elsewhere (Section 2 accuracy floors, Section 5 GDPR/PCI postures, Section 7 web perf targets), this section consolidates rather than duplicates — but every quality attribute relevant to Warden V1 has at least one NFR ID here.

**ID scheme.** NFRs are prefixed by category (`PERF-`, `SEC-`, `REL-`, `A11Y-`, `PRIV-`, `OBS-`, `I18N-`) with surface qualifier in parentheses where applicable.

**Categories explicitly skipped (no requirement bloat):**
- **Scalability** — V1 is bounded at ~20–100 paying coaches; Firebase reads scale linearly with paying users (not footage volume — Section 6 Innovation #3). Webhook latency target is folded into PERF-008. No horizontal-scaling concerns at V1 scale.
- **Integration** — already covered in Section 5 Integration Requirements table; pointer-only.
- **Portability** — covered per-surface in Section 7.

### Performance

- **PERF-001 (cross):** Activation timer (T1 − T0) ≤ 300 seconds (5 minutes) for the J1 first-time-coach journey, measured per `cross-ACTIVATION-001`. *(Section 2)*
- **PERF-002 (mobile):** Auto-slice processing time ≤ 5% of source video duration on the architecture-bound reference device (e.g., 1h20 source → ≤ 4 minutes auto-slice). The brief's J1 implies ~90s for 1h20 = ~2%; the 5% floor sets V1 acceptance with reference-device-specific tuning by architecture.
- **PERF-003 (mobile):** View-mode toggle (Full / Minimap / Minimap+HUD) completes in ≤ 100ms — no player swap; crop/style change on the same video source. *(legacy mobile distillate NFR2)*
- **PERF-004 (mobile):** Cinema Mode cold-start (Card tap → first frame visible) ≤ 1.5s on the reference device. *(Load-bearing for the < 5min activation budget — slow Cinema Mode startup blows the timer.)*
- **PERF-005 (mobile):** Clip export encode time ≤ 2× clip duration for Mobile-quality tier on the reference device (e.g., 30s clip → ≤ 60s encode). HD-quality tier may exceed; surface progress indication per FR `mobile-EXPORT-002`.
- **PERF-006 (web):** Landing page First Contentful Paint ≤ 1.5s on 4G mobile (Lighthouse target). *(Section 7)*
- **PERF-007 (web):** Largest Contentful Paint ≤ 2.5s on 4G mobile; Cumulative Layout Shift ≤ 0.1; Time-to-Interactive on `/pricing` ≤ 3s. *(Section 7)*
- **PERF-008 (web):** Webhook handler end-to-end latency (signature verification → Firestore write → 200 response) ≤ 1s p95 under nominal load. *(Section 5 Integration table — webhook delays >1h indicate fault)*
- **PERF-009 (tooling):** BSD round-detection processing time scales linearly with source video duration; multi-hour videos process within 1× source duration on developer-class hardware. *(tooling distillate — round segmentation must not be pipeline bottleneck)*
- **PERF-010 (mobile):** Reference-device performance floor — TBD per architecture pre-PRD spike (Risk #2 escalation). PRD inherits the architecture-published number; V1 launch is gated on the spike's completion. *(Section 2, Section 5)*

### Security

- **SEC-001 (web):** Stripe webhook endpoints verify the Stripe signature header on every incoming request before processing payload. Requests without valid signatures rejected with 400. *(Section 5; FR `web-WEBHOOK-001`)*
- **SEC-002 (cross):** All writes to Firestore `users/{uid}` come from the web server (firebase-admin); client writes are denied by Firestore Security Rules at the rule layer. *(FR `web-WEBHOOK-003`, `cross-ENTITLEMENT-002`)*
- **SEC-003 (web):** Firestore Security Rules are deployed to production before V1 launch. *(Section 5 brownfield triage item 2 — V1-blocking)*
- **SEC-004 (mobile):** No card data, payment credentials, or Stripe Mobile SDK code paths exist in any mobile build artifact. *(Section 5 PCI-offloaded; FR `cross-READER-APP-001`)*
- **SEC-005 (web):** Authentication tokens handled per Firebase Auth best practices; secure HttpOnly cookies for session persistence on dashboard route. *(legacy web distillate)*
- **SEC-006 (cross):** Stripe webhook handlers are dual-strategy idempotent: event-ID dedup AND business-state observation. Re-applying the same event is a no-op. *(FR `web-WEBHOOK-002`)*
- **SEC-007 (mobile):** No third-party SDK in mobile builds may transmit user content (video frames, audio, voice annotations) to any third-party server. The on-device-only contract is asserted at the dependency-allowlist level (architecture maintains the allowlist). *(Section 5 on-device-only)*

### Reliability

- **REL-001 (mobile):** Mobile session data (Card View state, Cinema Mode position, in-progress clips, recorded voice annotations) survives app crash, force-close, OS-killed, or device restart with no data loss within the active editing session. *(J2; FR `mobile-AUTOSAVE-001/002`)*
- **REL-002 (mobile):** Mobile remains fully functional offline for 30 days post last successful Firestore read. *(J9; FR `mobile-AUTH-004`)*
- **REL-003 (web):** Stripe webhook delivery delays tolerated up to 1 hour without manual intervention; >1h indicates a webhook-processing fault and pages oncall (oncall mechanism TBD per architecture/sprint-planning). *(Section 5 Integration table)*
- **REL-004 (cross):** Entitlement state transitions are eventually consistent; a Stripe-side state change reaches mobile within 5 minutes of webhook receipt under nominal conditions. *(J7 recovery time)*
- **REL-005 (tooling):** Tool outputs are deterministic — running the same tool twice on the same input produces byte-identical output (or fails identically). *(tooling distillate; `hash_validator` regression suite depends on this)*
- **REL-006 (mobile):** Map identification accuracy ≥ 95% on a held-out test set; round-boundary detection accuracy ≥ TBD% (target set by architecture spike). Below-floor behavior is graceful degradation per FR `mobile-AUTO-SLICE-003` and J3, not blocking error. *(Section 2 accuracy floors)*

### Accessibility

- **A11Y-001 (web):** Web meets WCAG 2.1 Level A. Color contrast meets AA (text-primary ~16:1, text-secondary ~5.5:1, orange ~4.8:1). *(Section 7 + UX distillate)*
- **A11Y-002 (web):** Keyboard navigation works on all interactive elements; 2px orange focus-visible outline. Skip-to-content link present. *(Section 7)*
- **A11Y-003 (web):** Status badges, error states, warning banners use text + color (not color-only) for state indication. *(Section 7)*
- **A11Y-004 (web):** Web respects `prefers-reduced-motion` user preference. *(Section 7)*
- **A11Y-005 (mobile):** Mobile soft white #F0F0F0 on bg #101014 contrast ratio ~17:1 (exceeds AAA for body text); touch targets minimum 44×44px. *(legacy UX distillate)*
- **A11Y-006 (mobile):** Mobile state indicators (recording, payment-failed banner, lapsed screen) use shape/icon/content change as primary signal — never color alone. *(legacy UX distillate)*

### Privacy

- **PRIV-001 (cross):** No video frames, audio frames, voice annotations, or any derived video data (clips, thumbnails, OCR'd text in V2) cross any wire to a Warden-controlled server. The on-device-only contract is structural. *(Section 5)*
- **PRIV-002 (mobile):** Mobile telemetry payloads (Firebase Analytics) carry only timestamps, event names, and entitlement-state markers — never frame data, voice durations, or raw audio. *(Section 5; FR `cross-ACTIVATION-002`)*
- **PRIV-003 (mobile):** User can delete a clip from local storage; deletion removes the clip's MP4, voice annotations, and any cached intermediate data (frame extracts, encode artifacts). *(Section 5 GDPR subject rights auto-satisfied via local deletion)*
- **PRIV-004 (web):** Stripe webhook payloads logged on Warden side contain only Stripe IDs (`customer`, `subscription`, `invoice`) — never card primitives. *(Section 5 PCI-offloaded)*
- **PRIV-005 (cross):** Voice annotations of third parties (voice that names or describes other players) are the recording user's controller responsibility; Warden does not detect, filter, or anonymize speech-content. *(Section 5 GDPR consent posture)*

### Observability

- **OBS-001 (mobile):** Mobile emits Firebase Analytics events for activation chain (T0, T1) on every J1 / J2 / J4 path. *(FR `cross-ACTIVATION-001`)*
- **OBS-002 (web):** Web emits Firebase Analytics events for funnel stages (Visit / CheckoutStart / CheckoutComplete / Coupon-applied / Coupon-Retained-past-deferred-billing). *(FR `web-ANALYTICS-001`)*
- **OBS-003 (mobile):** Mobile crash reports (if implemented via a crash-reporting SDK like Sentry / Crashlytics) MUST NOT include user content (frames, voice, clip metadata beyond IDs). The on-device-only contract supersedes telemetry verbosity. *(Section 5; PRIV-001)*
- **OBS-004 (web):** Webhook processing emits structured logs (JSON) with event-ID, event-type, processing-time, success/failure status — NO card or PII data. *(Section 5)*

### Internationalization & Localization

- **I18N-001 (mobile):** Mobile UI is French-locked for V1 (no language picker; copy ships in French). *(brief; legacy mobile distillate)*
- **I18N-002 (web):** Web UI is English-locked for V1 EXCEPT the FR-locked hero tagline (*"Progresser plus vite en investissant moins de temps."*) and deferred-billing copy (*"Vous ne serez pas débité avant le [date]"*), preserved verbatim in French. Full French web localization deferred to V3. *(brief; Section 3 V3 Vision)*
- **I18N-003 (mobile):** Mobile error messages, status banners, and system text use French copy that matches the rest of the UI (no English fallthroughs). *(legacy mobile distillate)*

