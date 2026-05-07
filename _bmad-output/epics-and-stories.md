---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
status: complete
completedAt: '2026-05-08'
project: Warden_monorepo
project_name: 'Warden_monorepo'
user_name: 'Stephane'
date: '2026-05-07'
workflowType: 'epics-and-stories'
status: in_progress
outputPathOverride: '_bmad-output/epics-and-stories.md'
inputDocuments:
  - _bmad-output/prd.md
  - _bmad-output/architecture.md
  - _bmad-output/ux-design.md
  - _bmad-output/product-brief.md
  - _bmad-output/product-brief-distillate.md
  - _bmad-output/legacy/distillate/01-product-strategy.md
  - _bmad-output/legacy/distillate/07-epics-and-sprint-state.md
  - _bmad-output/legacy/distillate/08-open-questions-and-risks.md
  - docs/source-tree-analysis.md
  - docs/component-inventory-mobile.md
  - docs/component-inventory-web.md
documentCounts:
  prds: 1
  architectures: 1
  uxDesigns: 1
  briefs: 1
  briefDistillates: 1
  legacyDistillates: 3
  asBuiltDocs: 3
extractionCounts:
  functionalRequirements: 69
  nonFunctionalRequirements: 41
  additionalRequirementsArchitecture: 22
  uxDesignRequirements: 18
  escalatedDecisionsToResolve: 10
prdLockedConstraints:
  - reader_app_contract_structural
  - no_free_tier_positioning
  - on_device_only_video_processing
  - thirty_day_offline_auth_cache
  - six_state_entitlement_model
  - activation_event_chain_t0_t1
  - cross_language_schema_enforcement
  - stripe_dual_strategy_idempotency
  - android_first_v1
  - no_push_notifications_v1
  - fourteen_canonical_maps
  - euro_799_7990_pricing
  - fr_list_binding_capability_contract
escalatedDecisions:
  - decision_es_1_sprint_3_epic_boundaries
  - decision_es_2_pre_prd_performance_spike_sequencing
  - decision_es_3_sprint_2_5_per_story_conflict_audit
  - decision_es_4_story_dependencies_and_ordering
  - decision_es_5_acceptance_criteria_format
  - decision_es_6_test_ownership_per_story
  - decision_es_7_v1_launch_gate_composition
  - decision_es_8_v2_v3_backlog_seeding
  - decision_es_9_story_estimation_discipline
  - decision_es_10_maintenance_budget_per_surface
---

# Warden_monorepo — Epic and Story Breakdown

## Overview

This document provides the complete epic and story breakdown for **Warden_monorepo**, decomposing the binding capability contract from the PRD, the architecture-bound implementation locations and decisions, and the UX-design Sprint-3 implementation surface into implementable stories.

**Locked source documents (do not re-litigate):**

- **PRD** (`_bmad-output/prd.md`, 1073 lines, 2026-05-07): 69 functional requirements (33 mobile + 16 web + 12 tooling + 8 cross-surface), 41 non-functional requirements, J1–J10 user journeys all V1, six-state entitlement model, activation event chain T0/T1 + dual-T1 paths, Reader-App contract structural, no-free-tier positioning, brownfield triage backlog dispositions, in-flight Sprint 2.5 disposition, persona reconciliation (Coach Thomas / Active Player Maxime / Passive Player Lucas), maps reconciliation 14 canonical, performance floor escalated to architecture pre-PRD spike.
- **Architecture** (`_bmad-output/architecture.md`, 2183 lines, 2026-05-07): FR-to-structure mapping for all 69 FRs binding implementation locations; 12 cross-surface invariants; six-state entitlement state machine transitions and triggering events with `paymentFailedGracePeriodMs: 7d` default; Reader-App CI gate spec with banned imports/strings; activation telemetry contract with payload field allowlist + wrapper enforcement; Cinema Mode "no player swap" PERF-003 ≤100 ms; Foreground Service Android plugin choice (custom expo-config-plugin with sticky notification "Analyse en cours…"); Stripe API pin bump default-to-bump from `2026-03-25.dahlia` to `2026-04-22.dahlia`; firestore.rules prod deploy V1-blocking; `schema_version: 1` add at next regeneration; `map_config.json` hybrid delivery (bundled-as-Metro-asset baseline + Firestore stale-while-revalidate); Firebase v12 RN auth migration sequence Stories 3.A–3.F.
- **UX Design** (`_bmad-output/ux-design.md`, 2071 lines, 2026-05-07): all 14 escalated UX decisions resolved; all 8 follow-ups locked (FU-1 support email = `support@warden.team`, FU-2 Discord = `https://discord.gg/DpDEyBZw`, FU-3 accent reconciled to `#FF6B00` for both surfaces with web retune, FU-4 Reader-App banlist regex narrowed to verb forms only with mobile copy "Gérer mon abonnement" / "Abonnement requis" locked, FU-5 password reset ships V1 via Firebase `sendPasswordResetEmail` inline form, FU-6 bracket bounds 5–60s, FU-7 tip cadence 6s, FU-8 web-side token cascade); full mobile French copy deck + web English copy deck; A11Y-005/006 audits passing; six-state entitlement visual treatments; manual-clip-from-timeline first-class V1 path (Decision #UX-14); 18-item Sprint-3 implementation surface enumerated at §6.5.
- **Legacy distillate** (`_bmad-output/legacy/distillate/07-epics-and-sprint-state.md`, 157 lines): pre-merge sprint state across 3 legacy repos; in-flight Sprint 2.5 mobile stories with their AC; Sprint 3 backlog as planned pre-monorepo; legacy epic boundaries and story sequencing.
- **As-built code state** (`docs/source-tree-analysis.md`, `docs/component-inventory-mobile.md`, `docs/component-inventory-web.md`): every NEW story-introduced component and every CHANGED file reconciles with this catalog.

## Requirements Inventory

### Functional Requirements

#### Mobile (`apps/mobile`) — 33 FRs

**Authentication & Entitlement**

- **mobile-AUTH-001:** User can sign in to the mobile app using Google or email/password credentials issued via the web Stripe flow. *(J1, J6)*
- **mobile-AUTH-002:** Mobile validates active entitlement against `users/{uid}.status` from Firestore on first foreground after sign-in, and refreshes on app foreground after a Stripe Customer Portal round-trip. *(J1, J7)*
- **mobile-AUTH-003:** Mobile rejects login (and presents a "subscription required" screen with deep-link to web Customer Portal) for any entitlement state other than `paid` or `offline-grace ≤30d`. *(J8)*
- **mobile-AUTH-004:** Mobile maintains entitlement validity for 30 days after last successful Firestore read; on day 31, forces re-auth on next foreground. *(J9)*
- **mobile-AUTH-005:** Mobile preserves user-generated session data across entitlement-state transitions, including lapse → resubscribe restoration. *(J8)*
- **mobile-AUTH-006:** Mobile presents a payment-failure warning banner with deep-link to Stripe Customer Portal when entitlement state is `payment-failed`. *(J7)*

**Session Import & Auto-Slicing**

- **mobile-IMPORT-001:** User can import a recorded gameplay video file from the device's gallery or file system. *(J1, J6)*
- **mobile-IMPORT-002:** Mobile rejects unsupported codec / container formats with a clear, actionable error.
- **mobile-AUTO-SLICE-001:** Mobile auto-slices an imported session into per-round Cards using on-device round-boundary detection. *(load-bearing on OpenCV JSI binding shipping as real binding)*
- **mobile-AUTO-SLICE-002:** Mobile auto-identifies the map for each round using on-device perceptual hashing against `map_config.json`. *(load-bearing on OpenCV JSI binding)*
- **mobile-AUTO-SLICE-003:** Mobile marks `map_name = "unknown"` when map identification confidence is below the recognition threshold; navigation and Cinema Mode remain available. *(J3)*
- **mobile-AUTO-SLICE-004:** Mobile auto-removes lobby footage from the Card View. *(J1)*

**Card View & Triage**

- **mobile-CARD-001:** User can view all auto-sliced rounds as Cards in a grid (Card View) with adaptive column count by screen size.
- **mobile-CARD-002:** User can sort Cards by temporal (default), orange biggest win, blue biggest win, or closest map; sort persists across sessions.
- **mobile-CARD-003:** User can tap a Card to open Cinema Mode for that round.
- **mobile-CARD-004:** Cold-start Card View offers "Resume last review" or "Import new session"; never blank state.
- **mobile-CARD-005:** Auto-slice-missed rounds remain accessible via the Cinema Mode timeline (no Card required) so the user can manually create clips for them. *(J3; UX Decision #UX-14 promotes this to first-class V1 nav)*

**Cinema Mode**

- **mobile-CINEMA-001:** User can review a round in Cinema Mode (immersive video player with reveal-on-tap controls auto-hiding after inactivity).
- **mobile-CINEMA-002:** User can switch view modes among Full / Minimap / Minimap+HUD via a top-level segmented control AND via a double-tap gesture on the top-left of the screen. *(PERF-003 ≤100 ms — no player swap; crop/style change on same expo-av source)*
- **mobile-CINEMA-003:** Mobile defaults Cinema Mode to Full view when the round's `map_name` is "unknown" (no minimap ROI available). *(J3)*
- **mobile-CINEMA-004:** Mobile persists the last-used view-mode preference. *(J4)*
- **mobile-CINEMA-005:** User can navigate to next / previous round via explicit Next / Previous buttons (no swipe — conflicts with timeline scrub).

**Clip Creation & Voice Annotation**

- **mobile-CLIP-001:** User can create a 30-second clip region centered on the current Cinema Mode playback position, with bracket-handle refinement controls. *(FU-6: bracket bounds min 5s, max 60s)*
- **mobile-CLIP-002:** User can manually create a clip from any point in the Cinema Mode timeline, not requiring an auto-sliced Card. *(J3)*
- **mobile-CLIP-003:** User can record a voice annotation in any of three slots — before, during, or after the clip — independently and optionally; silent clips skip all voice segments.
- **mobile-CLIP-004:** User can re-record (overwrite) a voice slot after recording. *(J2)*
- **mobile-CLIP-005:** User can preview a clip with voice annotations before exporting.

**Export & Share**

- **mobile-EXPORT-001:** User can export a clip as a standalone MP4 file via on-device FFmpeg encode (no cloud encode path exists).
- **mobile-EXPORT-002:** Mobile offers two encode quality tiers (Mobile and HD).
- **mobile-EXPORT-003:** Mobile dispatches the exported MP4 via the OS share sheet on encode completion. *(J1)*
- **mobile-EXPORT-004:** Exported MP4 is a vanilla H.264/AAC container compatible with Discord's inline preview pane. *(J5 — distribution moat)*

**Auto-save & Crash Recovery**

- **mobile-AUTOSAVE-001:** Mobile silently auto-saves clip-creation state without user-visible prompts. *(J2)*
- **mobile-AUTOSAVE-002:** Mobile resumes Cinema Mode at the exact frame, with clip region and any in-progress voice annotation preserved, after the app is backgrounded, closed, or crashed. *(J2)*

#### Web (`apps/web`) — 16 FRs

**Landing & Pricing**

- **web-LANDING-001:** Web serves a marketing landing page (`/`) with the FR-locked hero tagline (*"Progresser plus vite en investissant moins de temps."*) and a single primary CTA leading to `/pricing`.
- **web-LANDING-002:** Landing renders SSR HTML for crawlers and Discord card-preview fetchers (no JS-required content for Open Graph / Twitter Card metadata).
- **web-PRICING-001:** Web serves a pricing page (`/pricing`) with two plan cards (€7.99/mo, €79.90/yr) and a Stripe coupon URL parameter that auto-applies coupons from Discord links.
- **web-PRICING-002:** Pricing page presents an authentication modal (Google + Email/Password) before initiating Stripe Checkout.

**Authentication & Checkout**

- **web-AUTH-001:** User can sign in or register on web via Google OAuth or email/password through Firebase Auth. *(FU-5: password reset ships V1 via Firebase `sendPasswordResetEmail` inline form)*
- **web-CHECKOUT-001:** Web redirects authenticated users to Stripe Checkout (full-page, Stripe-hosted) with the selected plan and any auto-applied coupon, with French deferred-billing copy ("*Vous ne serez pas débité avant le [date]*").
- **web-CHECKOUT-002:** Web returns the user to `/dashboard?success=1` upon Checkout completion, with status badge reflecting the new entitlement.

**Dashboard**

- **web-DASHBOARD-001:** Web serves a protected `/dashboard` route (server-side auth check + fresh client-side Firestore reads; **no `onSnapshot`**) showing the user's email, plan, status badge, next payment date, and a "Manage Subscription" deep-link to Stripe Customer Portal.
- **web-DASHBOARD-002:** Dashboard presents a payment-failure warning banner with "Update payment method" deep-link when entitlement state is `payment-failed`. *(J7)*
- **web-DASHBOARD-003:** Dashboard presents a "Canceling" status badge and "Resubscribe" CTA when subscription is cancel-at-period-end. *(J8)*
- **web-DASHBOARD-004:** Dashboard cancellation flow presents a confirmation dialog ("access until [date]") with no exit survey and no guilt-trip CTA. *(J8 anti-dark-pattern policy)*
- **web-DASHBOARD-005:** Dashboard presents a "No active subscription" empty state with link to `/pricing` when user has no subscription.

**Webhook Processing**

- **web-WEBHOOK-001:** Web ingests Stripe webhooks (`invoice.payment_succeeded`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `checkout.session.completed`) via a server-only endpoint with Stripe signature verification.
- **web-WEBHOOK-002:** Webhook handlers are dual-strategy idempotent: event-ID deduplication via `stripe_events/{event_id}` document existence check AND business-state observation.
- **web-WEBHOOK-003:** Webhook handlers write `users/{uid}` from server only; client writes are denied by Firestore Security Rules.

**Analytics**

- **web-ANALYTICS-001:** Web emits Firebase Analytics events for the funnel stages: Visit, CheckoutStart, CheckoutComplete, Coupon-applied, Coupon-Retained-past-deferred-billing.

#### Tooling (`apps/tooling`) — 12 FRs

**Round Detection & Frame Extraction**

- **tooling-ROUND-DETECT-001:** Developer can run round-boundary detection on a recorded video (BSD or `game_detector`) and produce per-round PNG outputs (start, end, score frames). *(J10)*
- **tooling-ROUND-DETECT-002:** Round detection emits a miss-report listing missed-end / missed-start windows for manual inspection.

**Frame Labeling**

- **tooling-LABEL-001:** Developer can label score-frames into per-map directories via `frame_labeler`; co-export of paired start/end frames is automatic. *(J10)*
- **tooling-LABEL-002:** Frame labeler imports `MAP_LABELS` (14 canonical maps) from `tools/frame_labeler.py:19-34` as the single source of truth.

**Hash Generation & Map Config**

- **tooling-HASH-001:** Developer can run `hash_comparator` (or `map_config_generator`) on labeled per-map frames and emit `map_config.json` with per-map reference hashes. *(J10)*
- **tooling-HASH-002:** Emitted `map_config.json` includes `schema_version: 1` and the pipeline parameters needed to reproduce the hashes at validation time.

**Hash Validation**

- **tooling-VALIDATE-001:** Developer can run `hash_validator` on labeled directories against `map_config.json` and produce a per-map accuracy report (`accuracy_report.json`). *(J10; REL-006 regression suite)*
- **tooling-VALIDATE-002:** Hash validator reuses pipeline parameters from `map_config.json` (not from `config.yaml`) to guarantee generation/validation alignment.

**End-to-End Pipeline**

- **tooling-WARDEN-001:** Developer can run `warden_analyzer` end-to-end on a video and `map_config.json` to produce score frames + `rounds.json`.

**TUI Launcher**

- **tooling-TUI-001:** Developer can launch any tool interactively via `wardentooling.py` TUI launcher. *(J10)*
- **tooling-TUI-002:** TUI launcher supports re-run-with-same-args after successful exit (via `.warden_last_run.json`).

**Schema Validation**

- **tooling-SCHEMA-001:** Tooling validates emitted `map_config.json` against `contracts/map-config.schema.json` (`jsonschema`, strict — `additionalProperties: false`) at runtime / CI.

#### Cross-Surface (binding requirements) — 8 FRs

**Entitlement State Machine**

- **cross-ENTITLEMENT-001:** All surfaces (mobile, web) consume the same six-state entitlement model: `paid` / `lapsed` / `offline-grace ≤30d` / `payment-failed` / `multi-device` / `signed-out`. State semantics are PRD-defined; transition rules and triggering events are architecture-bound.
- **cross-ENTITLEMENT-002:** Web is the sole writer of `users/{uid}` entitlement fields (server-only, via Stripe webhooks); mobile reads but never writes. *([INVARIANT 2])*

**Activation Event Chain Telemetry**

- **cross-ACTIVATION-001:** Mobile emits `activation_timer_started` (T0) on auth-state-change → `paid` and `activation_timer_completed` (T1) on share-sheet confirmed-dispatch (coach path) OR Cinema Mode opened with view-mode toggled at least once (active-player path). *(dual-T1; J1, J4)*
- **cross-ACTIVATION-002:** Activation telemetry payloads carry only timestamps and event names — never frame data, voice durations, or raw audio. *(on-device-only privacy contract; payload allowlist enforced at wrapper level)*

**Schema Contract Conformance**

- **cross-SCHEMA-001:** `map-config.schema.json` is a first-class repo artifact under `packages/contracts/` and is enforced strictly (`additionalProperties: false`) on web (Zod, build-time) AND tooling (`jsonschema`, runtime / CI).
- **cross-SCHEMA-002:** `user-doc.schema.json` schema duplication is resolved via a single canonical schema under `packages/contracts/`. *(architecture Decision #1 + Decision #6 close the gap)*

**Reader-App Build Gate**

- **cross-READER-APP-001:** Mobile build artifacts contain zero monetization-surface artifacts. CI gates: direct-import bans (`react-native-iap`, `expo-in-app-purchases`, `@stripe/stripe-react-native`, `@stripe/stripe-js`), transitive-dependency scan via `pnpm ls --depth=Infinity`, banned strings (€7.99, €79.90, "subscribe", "s'abonner", "abonnez-vous", "monthly", "yearly", "mensuel", "annuel", "buy", "acheter") with the noun "abonnement" PERMITTED in entitlement-state UI labels per FU-4. Banned plan-picker imports include `@/components/checkout/{PlanCard,PlanCta,CouponInput}`. Defense-in-depth signaling tier — does not defend against intentional bypass.

**`map_config.json` Runtime Delivery**

- **cross-MAP-CONFIG-DELIVERY-001:** Mobile consumes `map_config.json` at runtime for on-device map identification. Hybrid delivery: bundled-as-Metro-asset baseline at `apps/mobile/assets/map_config.json` (always-available; eliminates the no-cache + offline first-launch error) + Firestore stale-while-revalidate overlay at `detection_config/latest` (OTA channel between Play Store releases per Decision #2 + Decision #8 manual operator action).

### NonFunctional Requirements

#### Performance — 10 NFRs

- **PERF-001 (cross):** Activation timer (T1 − T0) ≤ 300 seconds for the J1 first-time-coach journey.
- **PERF-002 (mobile):** Auto-slice processing time ≤ 5% of source video duration on the architecture-bound reference device.
- **PERF-003 (mobile):** View-mode toggle ≤ 100 ms — no player swap; crop/style change on the same `expo-av` source.
- **PERF-004 (mobile):** Cinema Mode cold-start (Card tap → first frame visible) ≤ 1.5 s on the reference device.
- **PERF-005 (mobile):** Clip export encode time ≤ 2× clip duration for Mobile-quality tier on the reference device.
- **PERF-006 (web):** Landing page First Contentful Paint ≤ 1.5 s on 4G mobile (Lighthouse target).
- **PERF-007 (web):** LCP ≤ 2.5 s on 4G mobile; CLS ≤ 0.1; TTI on `/pricing` ≤ 3 s.
- **PERF-008 (web):** Webhook handler end-to-end latency ≤ 1 s p95 under nominal load.
- **PERF-009 (tooling):** BSD round-detection processes within 1× source duration on developer-class hardware.
- **PERF-010 (mobile):** Reference-device performance floor — TBD per architecture pre-PRD spike. **V1 launch is gated on the spike's completion.** Spike artifact: `_bmad-output/architecture-spike-perf-floor.md`.

#### Security — 7 NFRs

- **SEC-001 (web):** Stripe webhook endpoints verify the Stripe signature header on every incoming request before processing payload.
- **SEC-002 (cross):** All writes to Firestore `users/{uid}` come from the web server (firebase-admin); client writes denied at the rule layer.
- **SEC-003 (web):** Firestore Security Rules are deployed to production before V1 launch. *(brownfield item 2 — V1-blocking)*
- **SEC-004 (mobile):** No card data, payment credentials, or Stripe Mobile SDK code paths exist in any mobile build artifact.
- **SEC-005 (web):** Authentication tokens handled per Firebase Auth best practices; secure HttpOnly cookies for session persistence on dashboard route.
- **SEC-006 (cross):** Stripe webhook handlers are dual-strategy idempotent: event-ID dedup AND business-state observation.
- **SEC-007 (mobile):** No third-party SDK in mobile builds may transmit user content (video frames, audio, voice annotations) to any third-party server.

#### Reliability — 6 NFRs

- **REL-001 (mobile):** Mobile session data survives app crash, force-close, OS-killed, or device restart with no data loss within the active editing session.
- **REL-002 (mobile):** Mobile remains fully functional offline for 30 days post last successful Firestore read.
- **REL-003 (web):** Stripe webhook delivery delays tolerated up to 1 hour without manual intervention.
- **REL-004 (cross):** Entitlement state transitions are eventually consistent; a Stripe-side state change reaches mobile within 5 minutes of webhook receipt under nominal conditions.
- **REL-005 (tooling):** Tool outputs are deterministic — running the same tool twice on the same input produces byte-identical output (or fails identically).
- **REL-006 (mobile):** Map identification accuracy ≥ 95% on a held-out test set; round-boundary detection ≥ TBD% (set by architecture spike). Below-floor behavior is graceful degradation, not blocking error.

#### Accessibility — 6 NFRs

- **A11Y-001 (web):** Web meets WCAG 2.1 Level A. Color contrast meets AA (text-primary ~16:1, text-secondary ~5.5:1, orange ~4.8:1; **token bump #FF6B00 must pass contrast re-verification per FU-3**).
- **A11Y-002 (web):** Keyboard navigation on all interactive elements; 2px orange focus-visible outline; skip-to-content link.
- **A11Y-003 (web):** Status badges, error states, warning banners use text + color (not color-only).
- **A11Y-004 (web):** Web respects `prefers-reduced-motion`.
- **A11Y-005 (mobile):** Mobile soft white #F0F0F0 on bg #101014 contrast ratio ~17:1; touch targets minimum 44×44 px.
- **A11Y-006 (mobile):** Mobile state indicators (recording, payment-failed banner, lapsed screen) use shape/icon/content change as primary signal — never color alone.

#### Privacy — 5 NFRs

- **PRIV-001 (cross):** No video frames, audio frames, voice annotations, or any derived video data cross any wire to a Warden-controlled server.
- **PRIV-002 (mobile):** Mobile telemetry payloads carry only timestamps, event names, and entitlement-state markers.
- **PRIV-003 (mobile):** User can delete a clip from local storage; deletion removes the clip's MP4, voice annotations, and any cached intermediate data via `clipDeletion.ts` cascade (Important Gap #2 from architecture).
- **PRIV-004 (web):** Stripe webhook payloads logged on Warden side contain only Stripe IDs.
- **PRIV-005 (cross):** Voice annotations of third parties are the recording user's controller responsibility; Warden does not detect/filter/anonymize speech-content.

#### Observability — 4 NFRs

- **OBS-001 (mobile):** Mobile emits Firebase Analytics events for activation chain (T0, T1) on every J1 / J2 / J4 path.
- **OBS-002 (web):** Web emits Firebase Analytics events for funnel stages.
- **OBS-003 (mobile):** Mobile crash reports (if any) MUST NOT include user content. *(V1 ships with NO crash reporting SDK per architecture Important Gap #3; manual user reports via `support@warden.team` mailto formatter — UX-DR FU-1)*
- **OBS-004 (web):** Webhook processing emits structured logs (JSON) — NO card or PII data.

#### Internationalization & Localization — 3 NFRs

- **I18N-001 (mobile):** Mobile UI is French-locked for V1 (no language picker; copy ships in French).
- **I18N-002 (web):** Web UI is English-locked for V1 EXCEPT FR-locked hero tagline + deferred-billing copy ("Vous ne serez pas débité avant le [date]") + savings copy ("économisez 2 mois") preserved verbatim.
- **I18N-003 (mobile):** Mobile error messages, status banners, and system text use French copy that matches the rest of the UI.

### Additional Requirements (from Architecture)

These are V1 work items that do not have a numbered FR but are architecturally bound and binding for Sprint 3. They route to specific stories in the same way FRs do.

#### Brownfield Triage Backlog Dispositions (PRD-bound, architecture-routed)

- **BF-1 — Stripe API pin bump.** Bump `apps/web/src/lib/stripe/server.ts:STRIPE_API_VERSION` from `2026-03-25.dahlia` to `2026-04-22.dahlia`; verify changelog; fix TS test errors; validate webhook event schemas. *(default-to-bump per Decision #4)*
- **BF-2 — Firestore Security Rules production deploy.** Deploy `apps/web/firestore.rules` (extended per Decision #7) to prod via `firebase deploy --only firestore:rules`. **V1-blocking** (SEC-003).
- **BF-3 — Firebase v12 RN auth migration to `@react-native-firebase/*`.** Architecture-bound sequence: Story 3.A (deps + prebuild) → 3.B (firebaseConfig) → 3.C (authService) → 3.D (subscriptionService — load-bearing for entitlement-state regression) → 3.E (detectionConfigService) → 3.F (E2E manual test of all 10 PRD journeys). **V1-blocking.**
- **BF-4 — Vitest parallelism flake.** V1 CI workaround: serial mode for V1 commits. V2 backlog for proper fix.
- **BF-5 — Foreground Service Android plugin.** Custom `expo-config-plugin` injecting Android Foreground Service with sticky notification "Analyse en cours…". *(architecture Brownfield Item 6 RESOLVED)*
- **BF-6 — `map_config.json` `schema_version: 1` add.** Tooling writers (`map_config_generator.py`, `hash_comparator.py`) emit `schema_version: 1`; contract `map-config.schema.json` requires it; mobile `validateDetectionConfig` accepts only V1.

#### Architecture Decisions (V1-bound deliverables)

- **AR-1 — `users/{uid}` schema reconciliation (Decision #1).** Edit `contracts/user-doc.schema.json`: remove optional `isPaid`; add formal `created_at` / `updated_at`; tighten `additionalProperties: true → false`; regen Zod via `pnpm --filter @warden/contracts build`; remove legacy `users/{uid}.isPaid` documentation comment from `apps/mobile/.env.example`.
- **AR-2 — Wire `apps/web` to `@warden/contracts/user-doc` (Decision #6).** Replace `apps/web/src/lib/schemas/subscription.ts:subscriptionResponseSchema` with `export { UserDocSchema as subscriptionResponseSchema } from '@warden/contracts/user-doc';`. *(depends on AR-1)*
- **AR-3 — `customer.subscription.updated` defensive handler (Decision #9).** Add Stripe Dashboard event subscription; extend `apps/web/src/lib/stripe/webhooks.ts:routeEvent` with `case 'customer.subscription.updated': return self.handleSubscriptionUpdated(event);`; new handler maps `trialing` → `active`; new Zod schema in `webhook-events.ts`; tests preserve self-namespace `vi.spyOn` pattern. *(depends on AR-1, AR-2)*
- **AR-4 — Hybrid `map_config.json` runtime delivery (Decision #2).** Commit `apps/mobile/assets/map_config.json` as Metro-bundled baseline; rewrite `detectionConfigBootstrap.ts` to read bundled asset on first launch (eliminates `OfflineFirstLaunchError`); `detectionConfigService.ts` retains stale-while-revalidate Firestore overlay; bundled config carries `schema_version: 1`; replace docs reference to `OfflineFirstLaunchError` with bundled fallback.
- **AR-5 — Shared Firebase project + CI guard (Decision #3).** CI assertion in `.github/workflows/ci.yml` that `apps/web/.env.example:NEXT_PUBLIC_FIREBASE_PROJECT_ID` and `apps/mobile/.env.example:EXPO_PUBLIC_FIREBASE_PROJECT_ID` match.
- **AR-6 — Firestore rules coverage extended (Decision #7).** `apps/web/firestore.rules` covers `users/{uid}` (owner read; deny client write), `detection_config/{docId}` (signed-in read; deny client write), `stripe_events/{eventId}` (deny all client). Catch-all deny.
- **AR-7 — `detection_config/latest` ownership = manual operator action (Decision #8).** Document `firebase firestore:set detection_config/latest apps/mobile/assets/map_config.json --project <project-id>` in `docs/deployment-guide.md`. No code change.
- **AR-8 — Reader-App CI gate spec (Decision #7 + UX FU-4).** Implement `apps/mobile/scripts/reader-app-gate.sh` (pre-commit hook + CI invocation): banned direct imports, banned transitive deps, banned strings (regex narrowed per FU-4 to verb forms only — noun "abonnement" permitted in entitlement labels); document in `apps/mobile/RELEASE.md`; verify gate passes on current `apps/mobile` tree.
- **AR-9 — Stripe webhook idempotency regression coverage.** Add Vitest cases for each idempotency strategy (event-ID dedup; merge-write business-state observation; routing-failure 200 response); cover the new `customer.subscription.updated` handler.
- **AR-10 — Activation telemetry contract implementation (`cross-ACTIVATION-001/002`).** Implement `apps/mobile/src/shared/services/analytics.ts` wrapper enforcing payload allowlist (`elapsed_seconds`, `t0_at`, `t1_at`, `t1_path: 'coach' | 'active_player'`); REJECT unknown keys at runtime (warn in dev, throw in tests); T0 emit in `authService.ts`; T1-coach emit in `exportPipeline.ts` post-share callback; T1-active-player emit in `CinemaModeScreen.tsx` on first view-mode toggle; tests assert no forbidden fields ever reach the FirebaseAnalytics SDK.
- **AR-11 — Six-state `deriveEntitlementState` implementation.** Pure function in `apps/mobile/src/features/auth/subscriptionService.ts:deriveEntitlementState(userDoc, cacheMeta)`; one unit test per state; `paymentFailedGracePeriodMs` default 7 days (configurable via `EXPO_PUBLIC_PAYMENT_FAILED_GRACE_MS`); wire `payment-failed` banner + `lapsed` "subscription required" screen.
- **AR-12 — `clipDeletion.ts` cascade (PRIV-003 Important Gap #2).** New service at `apps/mobile/src/features/clip-export/clipDeletion.ts` walks `audio_comments.file_path` + `clip_exports.file_path` + clears `processing.<sessionId>.*` MMKV keys + removes filesystem entries via `expo-file-system.deleteAsync`. SQLite CASCADE already in schema.

#### V1-Blocking Architecture Spike

- **AR-SPIKE — Pre-PRD performance spike.** Architecture's load-bearing first deliverable. Build a real OpenCV JSI binding (replace `loadFrameFromPath` stub with `react-native-fast-opencv` binding); run pipeline end-to-end on Poco X5 reference device; measure PERF-002/003/004/005; bind PERF-010; validate accuracy floors (map ID ≥ 95%, round-boundary ≥ TBD%). Outcome ladder: pass / partial-fail rung 1 (lower frame-sampling) / rung 2 (drop Minimap+HUD on weak hardware) / rung 3 (defer auto-slice to V2; manual-clip-only V1). FORBIDDEN: cloud fallback. Deliverable artifact: `_bmad-output/architecture-spike-perf-floor.md`.

#### CI/CD Additions (Phase 7 backlog, V1-enablement subset)

- **CI-1 — `ci.yml` workflow** (V0 fallback: local + pre-commit hooks): typecheck + test + Reader-App gate (V1-blocking) + shared-Firebase-project assertion + format check.
- **CI-2 — `deploy-firestore-rules.yml` workflow** (V0 fallback: one-time manual deploy per BF-2): auto-deploy on push to main affecting `apps/web/firestore.rules`.
- **CI-3 — `contracts-codegen-check.yml` workflow** (V0 fallback: dev re-runs `pnpm --filter @warden/contracts build`): fail PRs where regenerated TS is dirty.

#### Cross-Surface Invariants (12 — agents must respect)

[INVARIANT 1] Schemas master at `contracts/`. [INVARIANT 2] Web sole writer of `users/{uid}`. [INVARIANT 3] On-device-only video processing. [INVARIANT 4] Self-namespace import in `apps/web/src/lib/stripe/webhooks.ts`. [INVARIANT 5] Stripe metadata `firebase_uid` + `plan_id` on Checkout Session AND Subscription. [INVARIANT 6] Stripe dahlia API event nesting `parent.subscription_details.subscription`. [INVARIANT 7] Reader-App banned imports / strings (mobile only). [INVARIANT 8] `EXPO_PUBLIC_AUTH_BYPASS` MUST be false / unset in release builds. [INVARIANT 9] `.npmrc` `node-linker=hoisted` required. [INVARIANT 10] `react-native-mmkv` pinned to v3. [INVARIANT 11] Workspace deps via `workspace:*`. [INVARIANT 12] Conventional Commits via husky + commitlint with scopes `mobile/web/tooling/contracts/infra/auth/checkout/dashboard/webhooks/landing/legal`.

### UX Design Requirements

These are NEW components, NEW copy bundles, and TOKEN/REGEX changes that emerged from the UX spec (`_bmad-output/ux-design.md` §6.5) and need Sprint-3 stories. **The 14 UX decisions and 8 UX follow-up resolutions are LOCKED — story acceptance criteria reference §sections of the UX spec but do not re-derive the design.**

#### Mobile UX Surface (7 items)

- **UX-DR1 (mobile):** New component `apps/mobile/src/features/auth/EntitlementBanner.tsx` — payment-failure warning banner with deep-link to Stripe Customer Portal; visual state per UX §2.5; covers `mobile-AUTH-006`.
- **UX-DR2 (mobile):** New component `apps/mobile/src/features/auth/SubscriptionRequiredScreen.tsx` — "Abonnement requis" lapsed-state screen with deep-link to web Customer Portal; visual state per UX §2.5; covers `mobile-AUTH-003`.
- **UX-DR3 (mobile):** Optional small composition `apps/mobile/src/features/auth/OfflineIndicator.tsx` (or inline in HomeScreen) — offline-grace visual signal; covers `mobile-AUTH-004` visual layer.
- **UX-DR4 (mobile):** French i18n bundle at `apps/mobile/assets/i18n/fr.json` — strings from UX §4.1 (~150 strings); covers `I18N-001/003`. Bundle MUST be scanned by Reader-App gate (no banned strings except FU-4-permitted noun "abonnement" in entitlement labels).
- **UX-DR5 (mobile):** New shared service `apps/mobile/src/shared/services/errorReporting.ts` — mailto formatter targeting `support@warden.team` (FU-1); covers `OBS-003` manual fallback.
- **UX-DR6 (mobile):** Account bottom-sheet `Aide` section linking `support@warden.team` (FU-1) + `https://discord.gg/DpDEyBZw` (FU-2); covers `OBS-003` + community channel.
- **UX-DR7 (mobile):** Top-bar Cards/Timeline view-mode toggle in `CardViewScreen.tsx` for Decision #UX-14 manual-clip-from-timeline first-class V1 path; covers `mobile-CARD-005`.

#### Web UX Surface (8 items)

- **UX-DR8 (web):** New component `apps/web/src/components/dashboard/PaymentWarning.tsx` (composition from `Alert` + `Button`) — past_due banner; covers `web-DASHBOARD-002`.
- **UX-DR9 (web):** New component `apps/web/src/components/dashboard/CancelDialog.tsx` (composition from `Dialog` + `Button`) — cancellation confirmation dialog with "access until [date]"; **NO exit survey, NO guilt-trip CTA** per anti-dark-pattern policy; covers `web-DASHBOARD-004`.
- **UX-DR10 (web):** New component `apps/web/src/components/dashboard/EmptySubscription.tsx` (or inline in `/dashboard/page.tsx`) — "No active subscription" empty state with link to `/pricing`; covers `web-DASHBOARD-005`.
- **UX-DR11 (web):** New component `apps/web/src/components/auth/PasswordResetForm.tsx` (composition inside auth modal) — Firebase `sendPasswordResetEmail` inline form per FU-5; covers `web-AUTH-001` password reset path.
- **UX-DR12 (web):** Edit `apps/web/src/app/auth/sign-in/page.tsx` — handle `?passwordReset=1` query param success banner per FU-5; covers `web-AUTH-001`.
- **UX-DR13 (web):** New static asset `apps/web/public/og/landing.jpg` — Open Graph card 1200×630, ≤200 KB, sRGB, uses `#FF6B00` accent (FU-3); covers `web-LANDING-002`.
- **UX-DR14 (web):** Edit `apps/web/src/app/layout.tsx` — Open Graph + Twitter Card metadata additions and route-specific overrides; covers `web-LANDING-002`.
- **UX-DR15 (web):** Edit footer (`apps/web/src/components/layout/Footer.tsx`) — add "Get help" link → `mailto:support@warden.team` (FU-1); covers `OBS-003` web-side.

#### Token / Regex / Architecture Amendments (3 items)

- **UX-DR16 (web tokens):** Bump `apps/web/src/app/globals.css` and `apps/web/tailwind.config.ts` — `accent` from `#E8731A` to `#FF6B00` and `accent-hover` from `#F28A2E` to `#FF8533` per FU-3; **A11Y-001 contrast verification re-runs after bump.**
- **UX-DR17 (architecture amendment — Reader-App gate regex narrowing):** Edit `.github/workflows/ci.yml` + `apps/mobile/scripts/reader-app-gate.sh` — narrow banned-string regex from `\babonnement\b` to verb forms `\b(s'?abonner|abonnez-vous)\b` per FU-4; mobile copy "Gérer mon abonnement" / "Abonnement requis" LOCKED and explicitly permitted in entitlement-state UI labels; covers `cross-READER-APP-001`.
- **UX-DR18 (web copy):** English copy strings from UX §4.2 embedded inline (no i18n bundle for V1) including FR-verbatim insertions: hero "Progresser plus vite en investissant moins de temps.", deferred-billing "Vous ne serez pas débité avant le [date]", savings "économisez 2 mois". Covers `I18N-002`.

### FR Coverage Map

This map traces every FR, NFR, architecture work item (AR), brownfield disposition (BF), CI/CD addition (CI), and UX design requirement (UX-DR) to its primary epic. Multi-epic mappings indicate the FR is realized across more than one work stream (e.g., FR exposed in Epic 1 contract; consumed in Epic 5 feature; verified in Epic 10 launch gate).

#### Mobile FR Coverage

| FR | Epic(s) | Notes |
|---|---|---|
| mobile-AUTH-001 | Epic 3 | Sign-in UI; entitlement gate post-Firebase-v12-RN-auth migration (Epic 1 BF-3) |
| mobile-AUTH-002 | Epic 3 | Entitlement validation + foreground re-fetch via `subscriptionService.checkSubscription` |
| mobile-AUTH-003 | Epic 3 | Lapsed-state "subscription required" screen (UX-DR2 SubscriptionRequiredScreen.tsx) |
| mobile-AUTH-004 | Epic 3 | 30-day MMKV-cached entitlement; UX-DR3 OfflineIndicator |
| mobile-AUTH-005 | Epic 3 | Session-data preservation across lapse → resubscribe |
| mobile-AUTH-006 | Epic 3 | Payment-failure banner (UX-DR1 EntitlementBanner.tsx) |
| mobile-IMPORT-001 | Epic 0 | Sprint 2.5 Story 2.1 DONE; verified-as-legacy in conflict audit |
| mobile-IMPORT-002 | Epic 0 | Sprint 2.5 Story 2.1 DONE |
| mobile-AUTO-SLICE-001 | Epic 1, Epic 0 | Spike binds whether ships V1 (rung-3 fallback = manual-clip-only); Sprint 2.5 Story 7.5 ready-for-dev as legacy implementation |
| mobile-AUTO-SLICE-002 | Epic 1, Epic 0 | Spike-gated; Sprint 2.5 Story 7.5 mapIdentifier |
| mobile-AUTO-SLICE-003 | Epic 0 | Sprint 2.5 Story 2.5 unknown-map handling |
| mobile-AUTO-SLICE-004 | Epic 0 | Sprint 2.5 Story 7.5 segmentation lobby exclusion |
| mobile-CARD-001 | Epic 5 | Card View grid with adaptive columns |
| mobile-CARD-002 | Epic 5 | Sort persistence via `prefs.sortOrder` |
| mobile-CARD-003 | Epic 5 | Card → Cinema Mode tap |
| mobile-CARD-004 | Epic 5 | Cold-start state; "Resume last review" / "Import new session" |
| mobile-CARD-005 | Epic 5 | Manual-clip-from-timeline first-class V1 path; UX-DR7 Cards/Timeline toggle (Decision #UX-14) |
| mobile-CINEMA-001 | Epic 5 | Cinema Mode immersive review |
| mobile-CINEMA-002 | Epic 5 | View-mode toggle ≤100 ms (PERF-003 no-player-swap) |
| mobile-CINEMA-003 | Epic 5 | Default Full view for `unknown` map |
| mobile-CINEMA-004 | Epic 5 | View-mode preference persisted via `prefs.viewMode` |
| mobile-CINEMA-005 | Epic 5 | Next/Previous explicit buttons (no swipe) |
| mobile-CLIP-001 | Epic 6 | 30-second clip + bracket handles (FU-6 bounds 5–60s) |
| mobile-CLIP-002 | Epic 6 | Manual clip from any timeline point |
| mobile-CLIP-003 | Epic 6 | 3-slot voice (before/during/after) |
| mobile-CLIP-004 | Epic 6 | Voice slot re-record |
| mobile-CLIP-005 | Epic 6 | Clip preview with assembled voice |
| mobile-EXPORT-001 | Epic 6 | On-device FFmpeg encode (no cloud path) |
| mobile-EXPORT-002 | Epic 6 | Mobile/HD encode tiers |
| mobile-EXPORT-003 | Epic 6 | OS share sheet dispatch (T1-coach telemetry emit point — wired in Epic 2) |
| mobile-EXPORT-004 | Epic 6 | Discord-inline-playable H.264/AAC contract (J5 distribution moat) |
| mobile-AUTOSAVE-001 | Epic 7 | Silent auto-save without prompts |
| mobile-AUTOSAVE-002 | Epic 7 | Resume Cinema Mode at exact frame |

#### Web FR Coverage

| FR | Epic(s) | Notes |
|---|---|---|
| web-LANDING-001 | Epic 4 | FR-locked hero + single CTA |
| web-LANDING-002 | Epic 4 | SSR HTML for crawlers; UX-DR13 OG image + UX-DR14 layout meta |
| web-PRICING-001 | Epic 4 | 2 plan cards + Stripe coupon URL param (carry-forward from legacy Web Stories 3.1 + 3.3) |
| web-PRICING-002 | Epic 4 | Auth modal before Stripe Checkout (carry-forward from legacy Web Story 3.2) |
| web-AUTH-001 | Epic 4 | Google + Email/Password Firebase Auth; UX-DR11 PasswordResetForm + UX-DR12 sign-in `?passwordReset=1` query handler (FU-5) |
| web-CHECKOUT-001 | Epic 4 | Stripe-hosted Checkout + deferred-billing copy verbatim |
| web-CHECKOUT-002 | Epic 4 | `/dashboard?success=1` return path |
| web-DASHBOARD-001 | Epic 4 | Protected route; `requireSession`; fresh Firestore reads (no `onSnapshot`) |
| web-DASHBOARD-002 | Epic 3 | Payment-failure banner; UX-DR8 PaymentWarning.tsx composition |
| web-DASHBOARD-003 | Epic 3 | Canceling status + Resubscribe CTA |
| web-DASHBOARD-004 | Epic 4 | Cancellation confirmation dialog; UX-DR9 CancelDialog.tsx (anti-dark-pattern: NO survey, NO guilt-trip) |
| web-DASHBOARD-005 | Epic 4 | "No active subscription" empty state; UX-DR10 EmptySubscription.tsx |
| web-WEBHOOK-001 | Epic 1 | Carry-forward (legacy Web Epic 4 COMPLETE); AR-3 adds `customer.subscription.updated` event |
| web-WEBHOOK-002 | Epic 1 | Dual-strategy idempotency; AR-9 regression coverage |
| web-WEBHOOK-003 | Epic 1 | AR-6 firestore.rules deny client writes; BF-2 prod deploy |
| web-ANALYTICS-001 | Epic 4 | Funnel: Visit / CheckoutStart / CheckoutComplete / Coupon-applied / Coupon-Retained |

#### Tooling FR Coverage

| FR | Epic(s) | Notes |
|---|---|---|
| tooling-ROUND-DETECT-001 | Epic 9 | BSD + game_detector reference impls (legacy distillate: working) |
| tooling-ROUND-DETECT-002 | Epic 9 | Miss-report on detected gaps |
| tooling-LABEL-001 | Epic 9 | frame_labeler GUI (legacy: DONE) |
| tooling-LABEL-002 | Epic 9 | MAP_LABELS source-of-truth at frame_labeler.py:19-34 (14 canonical maps) |
| tooling-HASH-001 | Epic 9 | hash_comparator + map_config_generator emit map_config.json |
| tooling-HASH-002 | Epic 9 | BF-6 schema_version: 1 + pipeline params persisted |
| tooling-VALIDATE-001 | Epic 9 | hash_validator accuracy report (REL-006 regression suite) |
| tooling-VALIDATE-002 | Epic 9 | Pipeline-param parity from map_config.json (not config.yaml) |
| tooling-WARDEN-001 | Epic 9 | warden_analyzer Tool 5 — implementation complete; AC validation against real-footage test set |
| tooling-TUI-001 | Epic 9 | wardentooling.py launcher (legacy: COMPLETE) |
| tooling-TUI-002 | Epic 9 | .warden_last_run.json re-run (legacy: COMPLETE) |
| tooling-SCHEMA-001 | Epic 9, Epic 1 | jsonschema strict; `additionalProperties: false`; Epic 1 wires contract regen via `pnpm --filter @warden/contracts build` |

#### Cross-Surface FR Coverage

| FR | Epic(s) | Notes |
|---|---|---|
| cross-ENTITLEMENT-001 | Epic 3 | Six-state model; AR-11 `deriveEntitlementState` pure function; one test per state |
| cross-ENTITLEMENT-002 | Epic 1 | Web sole writer; [INVARIANT 2]; AR-6 firestore.rules deny client writes |
| cross-ACTIVATION-001 | Epic 2 | T0 + dual-T1 emit (coach via exportPipeline; active-player via CinemaModeScreen) |
| cross-ACTIVATION-002 | Epic 2 | AR-10 telemetry wrapper payload allowlist |
| cross-SCHEMA-001 | Epic 1 | map-config.schema.json strict; web (Zod) + tooling (jsonschema) enforced |
| cross-SCHEMA-002 | Epic 1 | user-doc.schema.json reconciliation per Decision #1; AR-1 + AR-2 close gap |
| cross-READER-APP-001 | Epic 2 | AR-8 CI gate spec; UX-DR17 regex narrowed per FU-4 |
| cross-MAP-CONFIG-DELIVERY-001 | Epic 1 | AR-4 hybrid (bundled-as-Metro-asset baseline + Firestore overlay) |

#### NFR Coverage

| NFR | Epic(s) | Notes |
|---|---|---|
| PERF-001 | Epic 2, Epic 10 | Telemetry instrument; post-launch verification on reference device |
| PERF-002 | Epic 1 | Spike measures auto-slice ≤5% of source duration |
| PERF-003 | Epic 1, Epic 5 | Spike validates ≤100 ms; Epic 5 implementation enforces no-player-swap pattern |
| PERF-004 | Epic 1, Epic 5 | Spike validates Cinema Mode cold-start ≤1.5 s |
| PERF-005 | Epic 1, Epic 6 | Spike validates clip-export ≤2× clip duration on Mobile-tier |
| PERF-006 | Epic 4 | Web FCP ≤1.5 s (already met by current legacy implementation; regression coverage) |
| PERF-007 | Epic 4 | Web LCP ≤2.5 s; CLS ≤0.1; TTI ≤3 s |
| PERF-008 | Epic 1 | Webhook ≤1 s p95 (already met; AR-9 regression coverage) |
| PERF-009 | Epic 9 | Tooling BSD linear scaling |
| PERF-010 | Epic 1 | AR-SPIKE binds the floor; **V1 launch gated** |
| SEC-001 | Epic 1 | Stripe signature verification (already implemented; AR-9 regression) |
| SEC-002 | Epic 1 | Server-only writes via firebase-admin; AR-6 rules layer |
| SEC-003 | Epic 1 | BF-2 firestore.rules prod deploy; **V1-blocking** |
| SEC-004 | Epic 2 | Reader-App gate prevents Stripe Mobile SDK |
| SEC-005 | Epic 4 | Firebase Auth httpOnly session cookie [LOCKED legacy] |
| SEC-006 | Epic 1 | Dual-strategy idempotency; AR-9 regression |
| SEC-007 | Epic 2 | Reader-App transitive-dep scan asserts SDK allowlist |
| REL-001 | Epic 7 | Auto-save + crash recovery |
| REL-002 | Epic 3, Epic 7 | Offline-grace state; auto-save offline-capable |
| REL-003 | Epic 1 | Webhook-delivery delay tolerance ≤1 h (already met) |
| REL-004 | Epic 3 | Foreground re-fetch on app resume |
| REL-005 | Epic 9 | Tooling determinism (stateless pure functions) |
| REL-006 | Epic 1, Epic 9 | Spike validates accuracy floors; tooling-VALIDATE-001 regression suite |
| A11Y-001 | Epic 4 | Web WCAG 2.1 A; **#FF6B00 contrast re-verify after UX-DR16 token bump** |
| A11Y-002 | Epic 4 | Keyboard nav + 2px focus outline + skip-to-content [LOCKED legacy] |
| A11Y-003 | Epic 4 | Status badges with text + color (not color-only) |
| A11Y-004 | Epic 4 | `prefers-reduced-motion` |
| A11Y-005 | Epic 5, Epic 7 | Mobile contrast; touch targets ≥44 px |
| A11Y-006 | Epic 5, Epic 7 | Non-color signal catalog (recording, banner, lapsed screen) |
| PRIV-001 | Epic 2 | On-device-only contract via [INVARIANT 3] + telemetry allowlist |
| PRIV-002 | Epic 2 | Telemetry payload allowlist enforced at wrapper |
| PRIV-003 | Epic 6 | AR-12 clipDeletion.ts cascade |
| PRIV-004 | Epic 1 | Structured logs contain only Stripe IDs (already implemented) |
| PRIV-005 | Epic 8 | FR copy does NOT prompt for "anonymize voice" — UX inheritance |
| OBS-001 | Epic 2 | Mobile T0 + dual-T1 emission |
| OBS-002 | Epic 4 | Web funnel events |
| OBS-003 | Epic 2, Epic 8 | No user content in crash; manual fallback via mailto (UX-DR5) |
| OBS-004 | Epic 1 | Webhook structured logs |
| I18N-001 | Epic 8 | UX-DR4 FR i18n bundle ~150 strings |
| I18N-002 | Epic 4 | UX-DR18 web English copy with FR-verbatim insertions |
| I18N-003 | Epic 8 | FR error messages match rest of UI |

#### Architecture Decisions (AR), Brownfield (BF), CI/CD, UX-DR Coverage

| Item | Epic(s) | Notes |
|---|---|---|
| AR-SPIKE | Epic 1 | **Load-bearing first deliverable; gates V1 launch** |
| AR-1 (user-doc.schema reconcile) | Epic 1 | Decision #1 |
| AR-2 (web wire to contract) | Epic 1 | Decision #6; depends on AR-1 |
| AR-3 (trialing handler) | Epic 1 | Decision #9; depends on AR-1, AR-2 |
| AR-4 (hybrid map_config) | Epic 1 | Decision #2 |
| AR-5 (shared Firebase project + CI guard) | Epic 1 | Decision #3 |
| AR-6 (firestore.rules coverage extended) | Epic 1 | Decision #7 |
| AR-7 (detection_config/latest manual ops) | Epic 1 | Decision #8 — documentation deliverable |
| AR-8 (Reader-App CI gate spec) | Epic 2 | Decision #7 spec |
| AR-9 (webhook idempotency regression) | Epic 1 | Per architecture documented contract |
| AR-10 (activation telemetry contract) | Epic 2 | Wrapper + dual-T1 emission |
| AR-11 (deriveEntitlementState pure fn) | Epic 3 | One test per state |
| AR-12 (clipDeletion.ts cascade) | Epic 6 | Important Gap #2 PRIV-003 |
| BF-1 (Stripe API pin bump) | Epic 1 | Default-to-bump per Decision #4 |
| BF-2 (firestore.rules prod deploy) | Epic 1 | **V1-blocking** |
| BF-3 (Firebase v12 RN auth migration) | Epic 1 | **V1-blocking**; Stories 3.A → 3.F sequence; gates Epic 3 entitlement E2E test |
| BF-4 (Vitest serial workaround) | Epic 1 | V1 CI workaround; V2 backlog for proper fix |
| BF-5 (Foreground Service plugin) | Epic 1 | Custom expo-config-plugin; binds before Sprint 3 mobile feature work |
| BF-6 (schema_version: 1 add) | Epic 1, Epic 9 | Tooling emits; contract requires; mobile validates V1 only |
| CI-1 (ci.yml) | Epic 1 | V0 = local + pre-commit; V1.1 = full GitHub Actions |
| CI-2 (deploy-firestore-rules.yml) | Epic 10 | Post-V1 polish; V0 = manual deploy per BF-2 |
| CI-3 (contracts-codegen-check.yml) | Epic 1 | V0 = dev re-runs `pnpm contracts:build` |
| UX-DR1 (EntitlementBanner.tsx) | Epic 3 | mobile-AUTH-006 |
| UX-DR2 (SubscriptionRequiredScreen.tsx) | Epic 3 | mobile-AUTH-003 |
| UX-DR3 (OfflineIndicator) | Epic 3 | mobile-AUTH-004 visual |
| UX-DR4 (FR i18n bundle) | Epic 8 | I18N-001/003; ~150 strings |
| UX-DR5 (errorReporting.ts) | Epic 8 | OBS-003 manual fallback |
| UX-DR6 (Account Aide section) | Epic 8 | Support email + Discord |
| UX-DR7 (Cards/Timeline toggle) | Epic 5 | mobile-CARD-005; Decision #UX-14 |
| UX-DR8 (PaymentWarning.tsx web) | Epic 3 | web-DASHBOARD-002 |
| UX-DR9 (CancelDialog.tsx) | Epic 4 | web-DASHBOARD-004; anti-dark-pattern |
| UX-DR10 (EmptySubscription.tsx) | Epic 4 | web-DASHBOARD-005 |
| UX-DR11 (PasswordResetForm.tsx) | Epic 4 | FU-5 |
| UX-DR12 (sign-in `?passwordReset=1` query) | Epic 4 | FU-5 |
| UX-DR13 (OG image asset) | Epic 4 | web-LANDING-002 |
| UX-DR14 (layout meta) | Epic 4 | web-LANDING-002 |
| UX-DR15 (footer help link) | Epic 4 | OBS-003 web-side |
| UX-DR16 (web token bump #FF6B00) | Epic 4 | FU-3; A11Y-001 contrast re-verify |
| UX-DR17 (Reader-App regex narrow) | Epic 2 | FU-4; mobile copy "Gérer mon abonnement" / "Abonnement requis" LOCKED |
| UX-DR18 (web English copy + FR insertions) | Epic 4 | I18N-002 |

## Epic List

### Epic 0: Sprint 2.5 Closure & Conflict Audit

**Type:** Transition gate (NOT a Sprint 3 V1 epic; pre-V1 deliverable that gates Sprint 3 commit)
**User outcome:** Sprint 2.5 in-flight legacy mobile work either lands cleanly under existing AC ("complete-as-legacy") or is re-scoped into Sprint 3 with new AC. After Epic 0, Sprint 3 starts from a clean baseline with no in-flight pre-merge stories blocking unified planning.
**FRs covered (verified-as-legacy or re-scoped):** mobile-IMPORT-001/002, mobile-AUTO-SLICE-001/002/003/004
**Resolves Decision #ES-3** (Sprint 2.5 per-story conflict audit table is the discrete deliverable owned by this epic).
**Implementation notes:** Per-story conflict audit table covering legacy mobile Sprint 2.5 stories: 2.2 FFmpeg integration (in-progress; 3 minor edits applied), 2.5 segment video into map episodes (ready-for-dev; consumes 7.5 output), 2.6 background processing + crash recovery (ready-for-dev), 2.7 session list + management (ready-for-dev), 7.1 SQLite view_mode 2-value→3-value migration (ready-for-dev), 7.2 ClipExport view_mode TS union (ready-for-dev), 7.3 view-mode toggle UI + HudToggle + Zustand+MMKV persistence (ready-for-dev), 7.4 remote DetectionConfig service no-op shim (ready-for-dev), 7.5 detector replacement gameDetector + mapIdentifier + blackScreenDetector refactor (ready-for-dev), 7.6 export pipeline 3 view modes (ready-for-dev). For each: PRD-conflict finding (yes/no) + disposition (complete-as-legacy / re-scope-into-Sprint-3-with-new-AC / drop). No story implying free-tier or pre-no-free-tier flow ships under legacy AC.

### Epic 1: Foundations — V1-Blocking Spike, Brownfield Reconciliation & Cross-Language Contracts

**Type:** Foundation (V1-launch-blocking; sequencing-critical; user value is enabling — every later epic depends on this)
**User outcome:** Solo developer (Stephane) and downstream AI agents can ship feature work on a foundation where the OpenCV JSI binding is real (or the V2 deferral is decided), the Firebase v12 RN auth migration is complete, the contract package single-sources `users/{uid}` and `map_config.json` schemas, the Foreground Service plugin keeps mobile pipeline alive across interruptions, Stripe webhooks have regression-covered idempotency, Firestore rules deny client writes in production, and the hybrid `map_config.json` delivery eliminates the first-launch-offline error path.
**FRs covered:** web-WEBHOOK-001/002/003 (regression coverage; trialing handler addition), cross-SCHEMA-001/002, cross-MAP-CONFIG-DELIVERY-001, cross-ENTITLEMENT-002 (web-sole-writer rule layer), cross-AUTO-SLICE-001/002 (spike-gated)
**NFRs covered:** PERF-002/003/004/005/008/010, REL-003/006, SEC-001/002/003/006, OBS-004, PRIV-004
**Architecture work items:** AR-SPIKE, AR-1, AR-2, AR-3, AR-4, AR-5, AR-6, AR-7, AR-9
**Brownfield triage:** BF-1, BF-2, BF-3 (Stories 3.A–3.F), BF-4, BF-5, BF-6 (cross-cut with Epic 9)
**CI/CD:** CI-1 (V0 fallback = local + pre-commit), CI-3 (V0 fallback = dev re-runs)
**Implementation notes:** Sequencing per architecture's Decision Impact Analysis: (1) AR-SPIKE first — gates everything else; ladder fallback rungs determine downstream story shape; (2) BF-5 Foreground Service plugin in parallel with spike; (3) BF-1 Stripe pin bump in parallel; (4) AR-1 + AR-2 + AR-3 coordinated triple (one PR per step, land together); (5) AR-4 + BF-6 schema_version regenerated together; (6) AR-6 + BF-2 firestore rules extended + prod-deployed; (7) BF-3 Stories 3.A → 3.F migration sequence (gates Epic 3 entitlement E2E test at Story 3.D); (8) AR-9 webhook idempotency regression coverage. **V1 launch is gated on AR-SPIKE completion + BF-2 prod deploy + BF-3 Story 3.F sign-off.**

### Epic 2: Reader-App Build Gate & Activation Telemetry Contract

**Type:** Cross-surface contracts (V1-blocking; signaling-tier defense-in-depth + privacy-by-construction telemetry)
**User outcome:** Mobile build artifacts cannot accidentally drift into containing monetization-surface code (the structural Reader-App posture against App Store / Play Store policy is mechanically reinforced); activation telemetry can measure < 5min activation under the on-device-only privacy contract without ever sending video frames or voice durations across the wire.
**FRs covered:** cross-READER-APP-001, cross-ACTIVATION-001/002
**NFRs covered:** PERF-001 (instrument), SEC-004, SEC-007, PRIV-001, PRIV-002, OBS-001, OBS-003 (no user content in crash reports)
**Architecture work items:** AR-8, AR-10
**UX design requirements:** UX-DR17 (regex narrowed to verb forms only per FU-4)
**Implementation notes:** Reader-App gate ships as `apps/mobile/scripts/reader-app-gate.sh` engaged via `.husky/pre-commit` AND included in `ci.yml` (Phase-7 backlog). Gate scans direct imports, transitive deps via `pnpm ls --depth=Infinity`, and banned strings using narrowed regex `\b(s'?abonner|abonnez-vous)\b` per FU-4 (the noun "abonnement" is permitted in entitlement-state UI labels per locked mobile copy "Gérer mon abonnement" / "Abonnement requis"). Activation telemetry wrapper at `apps/mobile/src/shared/services/analytics.ts` enforces payload allowlist `{elapsed_seconds, t0_at, t1_at, t1_path: 'coach' | 'active_player'}` — REJECTS unknown keys (warns in dev, throws in tests). T0 emit lives in `authService.ts` mapFirebaseUser; T1-coach emit lives in `exportPipeline.ts` post-share callback; T1-active-player emit lives in `CinemaModeScreen.tsx` on first view-mode toggle (mutually-exclusive per session — first-fire wins).

### Epic 3: Six-State Entitlement — State Machine, UI Banners & Lapsed Screen

**Type:** Cross-surface user value (trust + correctness across edge states)
**User outcome:** Coach Thomas (and Active Player Maxime) experiences correct entitlement behavior across all six states (paid / lapsed / offline-grace ≤30d / payment-failed / multi-device / signed-out): the app is fully usable while paid, gracefully degrades for offline-grace, banners on payment-failed (with portal deep-link), shows "subscription required" on lapsed, never loses session data on lapse → resubscribe (J7 + J8 + J9 happy paths). Web dashboard reflects the same states via PaymentWarning + Canceling badge + Resubscribe CTA.
**FRs covered:** mobile-AUTH-001/002/003/004/005/006, web-DASHBOARD-002/003, cross-ENTITLEMENT-001
**NFRs covered:** REL-002 (offline-grace), REL-004 (transition latency)
**Architecture work items:** AR-11 (`deriveEntitlementState` + 6-state regression tests; `paymentFailedGracePeriodMs: 7d` default)
**UX design requirements:** UX-DR1 (EntitlementBanner.tsx), UX-DR2 (SubscriptionRequiredScreen.tsx), UX-DR3 (OfflineIndicator), UX-DR8 (PaymentWarning.tsx web composition)
**Dependencies:** Epic 1 (BF-3 Firebase v12 RN auth Story 3.D must land first — `subscriptionService.ts` lives there) + Epic 1 (AR-1/AR-2/AR-3 contract triple — `users/{uid}` schema is single-sourced)
**Implementation notes:** `deriveEntitlementState(userDoc, cacheMeta)` is pure-function — testable; one unit test per state per row in architecture's transition table. Mobile-side payment-failed grace duration configurable via `EXPO_PUBLIC_PAYMENT_FAILED_GRACE_MS=604800000`. Day-31 offline-cache expiry checked on every foreground wake (no setTimeout — survives backgrounding without scheduling concerns). Multi-device state is NOT enforced (entitlement is per-user, not per-device).

### Epic 4: Web — Subscribe & Manage Funnel

**Type:** Web user value (Discord-coupon-link → checkout → dashboard funnel; Coupon → Retained validator)
**User outcome:** Coach Thomas and Active-Player Lucas can land on the marketing landing from a Discord link, hit the FR-locked French hero, scroll briefly, click Pricing, see the coupon auto-apply with deferred-billing French copy, auth via Google or email/password (with V1 password-reset path via Firebase `sendPasswordResetEmail`), redirect to Stripe Checkout, complete in under 60 seconds, return to dashboard with success state, manage subscription via Stripe Customer Portal deep-link, see clean cancel-then-resubscribe flow without dark patterns. Discord card preview renders correctly with #FF6B00 accent OG image. Web English copy preserves FR-verbatim insertions where locked.
**FRs covered:** web-LANDING-001/002, web-PRICING-001/002, web-AUTH-001 (with FU-5 password reset), web-CHECKOUT-001/002, web-DASHBOARD-001/004/005, web-ANALYTICS-001
**NFRs covered:** PERF-006/007, A11Y-001/002/003/004 (token re-verify), I18N-002, SEC-005, OBS-002
**UX design requirements:** UX-DR9 (CancelDialog.tsx — anti-dark-pattern), UX-DR10 (EmptySubscription.tsx), UX-DR11 (PasswordResetForm.tsx), UX-DR12 (sign-in `?passwordReset=1` query handler), UX-DR13 (OG image asset 1200×630 ≤200 KB sRGB), UX-DR14 (layout.tsx Open Graph + Twitter Card meta), UX-DR15 (footer "Get help" link → mailto:support@warden.team), UX-DR16 (web token bump #FF6B00 + accent-hover #FF8533), UX-DR18 (English copy with FR-verbatim insertions)
**Dependencies:** Epic 1 (web-WEBHOOK trialing handler + AR-2 contract wire) for entitlement reads to be schema-aligned with mobile
**Implementation notes:** Most legacy web epics are already complete (legacy Web Epic 1 Project Foundation + Epic 2 Authentication + Epic 3 Subscription/Checkout + Epic 4 Webhook Processing all DONE); legacy Web Epic 5 Sprint Change 2026-04-16 Stories 5.1 + 5.2 + 5.3 carry forward. Epic 4 deltas are: FU-5 password reset path (UX-DR11/12 are NEW), UX-DR9 CancelDialog with anti-dark-pattern policy (no exit survey, no guilt-trip), UX-DR10 EmptySubscription, UX-DR13/14 Open Graph assets, UX-DR15 footer help link, UX-DR16 token bump (must re-verify A11Y-001 contrast post-bump), UX-DR18 English copy embedding the FR-verbatim insertions. Stripe Customer Portal handles all billing self-service per legacy Sprint Change 2026-04-16 — no custom payment-history / upgrade / cancel UI ships in Warden web.

### Epic 5: Mobile — Card View, Cinema Mode & Manual Clip from Timeline

**Type:** Mobile user value (review experience; first half of the activation < 5min budget)
**User outcome:** After Card View opens with auto-sliced rounds (or manual-clip-from-timeline path if AR-SPIKE returned rung-3), Coach Thomas taps a Card and lands in Cinema Mode under 1.5s. He toggles between Full / Minimap / Minimap+HUD with sub-100ms latency (no player swap), navigates next/previous rounds explicitly. He can sort Cards temporally (default) or by score (stub-degraded until V2 OCR). Active-Player Maxime opens Cinema Mode and toggles view-mode at least once — T1-active-player telemetry fires (per Epic 2).
**FRs covered:** mobile-CARD-001/002/003/004/005, mobile-CINEMA-001/002/003/004/005
**NFRs covered:** PERF-003 (≤100 ms toggle), PERF-004 (cold-start ≤1.5 s), A11Y-005 (touch targets), A11Y-006 (state indicators)
**UX design requirements:** UX-DR7 (Cards/Timeline top-bar toggle in CardViewScreen for Decision #UX-14 manual-clip path)
**Dependencies:** Epic 1 (AR-SPIKE outcome dictates whether Card View auto-population works or degrades to manual-clip-only path) + Epic 2 (T1-active-player telemetry hook in CinemaModeScreen)
**Implementation notes:** ViewModeToggle.tsx + MinimapView.tsx implement crop/style change on the same `expo-av` source — no second player instantiation, no source swap. View-mode preference persists via `prefs.viewMode` + `prefs.minimapHud` MMKV keys. Cinema Mode default is Full when `map_name === 'unknown'` (no minimap ROI available) per `mobile-CINEMA-003`. Cards/Timeline top-bar toggle in CardViewScreen exposes the timeline view directly without going through Cinema Mode for the manual-clip-from-any-point flow per Decision #UX-14 (rung-3 fallback ready). Auto-slice-missed rounds (per `mobile-CARD-005`) accessible via the timeline.

### Epic 6: Mobile — Clip Creation, Voice & Export-Share

**Type:** Mobile user value (artifact production; second half of activation < 5min; T1-coach completion)
**User outcome:** Coach Thomas creates a 30-second clip region with bracket handles (5–60s bounds per FU-6) on a flank rotation, records voice annotation in any of 3 slots (before/during/after; can re-record), previews the clip with assembled voice, picks Mobile or HD encode tier, exports — encode runs ≤2× clip duration on Mobile-tier, OS share-sheet dispatches to Discord. T1-coach telemetry fires on confirmed-dispatch (per Epic 2). Discord renders the MP4 inline (J5 distribution moat — Lucas watches without installing the app). Stephane can delete a clip and Warden cleans up MP4 + voice files + intermediate cache.
**FRs covered:** mobile-CLIP-001/002/003/004/005, mobile-EXPORT-001/002/003/004
**NFRs covered:** PERF-005 (encode ≤2× clip duration), PRIV-003 (clipDeletion cascade), SEC-007 (no third-party SDK transmits user content)
**Architecture work items:** AR-12 (clipDeletion.ts cascade — Important Gap #2)
**Dependencies:** Epic 1 (AR-SPIKE confirms FFmpeg encode budget) + Epic 2 (T1-coach telemetry hook in exportPipeline) + Epic 5 (Cinema Mode is the platform on top of which clip mode opens)
**Implementation notes:** Bracket-handle bounds locked to 5s minimum (re-record-voice is feasible in the 5–30s tail of a clip per UX), 60s maximum (J3 implies ≤30s typical; 60s ceiling for edge cases like complex tactical sequences). Voice slots: independently optional; silent clips skip all voice segments per `mobile-CLIP-003`. AR-12 cascade walks `audio_comments.file_path` + `clip_exports.file_path` + clears `processing.<sessionId>.*` MMKV keys + removes filesystem entries via `expo-file-system.deleteAsync`. Discord-inline-playable contract is vanilla H.264/AAC; no Warden-specific container or codec.

### Epic 7: Mobile — Auto-save & Crash Recovery

**Type:** Mobile user value (trust through invisible reliability)
**User outcome:** Coach Thomas closes the app mid-clip during the J2 daughter-interrupts scenario and reopens 2 hours later — Cinema Mode resumes at the exact frame, half-recorded voice annotation preserved, clip region with bracket handles intact. He listens back to his half-thought, taps "during" again to overwrite, finishes the export. The interruption cost is the actual interruption time, not the work lost. Across crashes, force-closes, OS-killed states, and device restarts, no data is lost within the active editing session. Offline-mode (J9 train ride) works identically to online for review + export-with-share-queue.
**FRs covered:** mobile-AUTOSAVE-001/002
**NFRs covered:** REL-001 (data survives crash/force-close/OS-killed/restart), REL-002 (offline 30 days), A11Y-006 (state indicators non-color)
**Implementation notes:** `processingPipeline.ts` 4-stage MMKV-checkpointed orchestrator already exists (legacy Sprint 2.5). NEW work: clip-creation auto-save in `useClipExport.ts` (silent persistence per `mobile-AUTOSAVE-001` — no user-visible prompt at save time; resume is implicit on next launch). On launch, App.tsx reads `useSessionStore.currentSessionId` and restores Cinema Mode position via `useSessionStore.playbackPositionMs`. The interruption-handles-correctly story spans the Foreground Service plugin (Epic 1 BF-5) — the service hosts the main JS context for processing duration; clip-creation auto-save engages even when the service is not running (Cinema Mode + clip mode are foreground UI work, not pipeline work).

### Epic 8: Mobile — French i18n, Help & Manual Error Reporting

**Type:** Mobile user value (localization + support path; OBS-003 manual fallback in absence of crash-reporting SDK)
**User outcome:** Coach Thomas (and Maxime) experiences the entire mobile app in French — every banner, every error toast, every state label, every confirmation dialog. When something goes wrong (a session fails to import, an export errors out, a state Stephane needs to flag), the user can tap "Aide" in the account bottom-sheet, sees `support@warden.team` and `https://discord.gg/DpDEyBZw`, and can either email or join the Discord — the app pre-formats a mailto with relevant context (session ID, crash timestamp, error code if any) without including any user content (frames / voice / clip metadata beyond IDs).
**FRs covered:** I18N-001, I18N-003
**NFRs covered:** OBS-003 (manual fallback path), PRIV-005 (FR copy does NOT prompt for "anonymize voice" — UX inheritance)
**UX design requirements:** UX-DR4 (FR i18n bundle ~150 strings from UX §4.1), UX-DR5 (errorReporting.ts mailto formatter), UX-DR6 (Account bottom-sheet Aide section)
**Implementation notes:** i18n bundle at `apps/mobile/assets/i18n/fr.json` — bundle MUST be scanned by Reader-App gate (no banned strings); the noun "abonnement" is explicitly permitted in entitlement labels per UX FU-4 lock ("Gérer mon abonnement", "Abonnement requis"); verb forms (`s'abonner`, `abonnez-vous`) MUST NOT appear. errorReporting.ts mailto-target is `support@warden.team` (FU-1); body pre-fill includes app version + Android version + session ID + ISO 8601 timestamp + last-known-error + locale, NEVER frame data / voice durations / clip metadata. Account bottom-sheet Aide section links both support email AND Discord per FU-1 + FU-2.

### Epic 9: Tooling — V1 Pipeline Hardening

**Type:** Operator user value (Stephane regenerates `map_config.json` end-to-end on a new map without code changes; J10 validated)
**User outcome:** Stephane (or future contributor) can add a 15th map (or re-validate existing 14 canonical maps) end-to-end via the Python tooling pipeline: BSD round detection → frame labeling → hash generation → schema-strict validation → accuracy report. The output `map_config.json` carries `schema_version: 1`; the cross-language schema (jsonschema on tooling, Zod on web/mobile) catches drift mechanically; below-floor accuracy (<95% on unseen) is reported transparently before publication.
**FRs covered:** tooling-ROUND-DETECT-001/002, tooling-LABEL-001/002, tooling-HASH-001/002, tooling-VALIDATE-001/002, tooling-WARDEN-001, tooling-TUI-001/002, tooling-SCHEMA-001
**NFRs covered:** PERF-009 (BSD linear scaling), REL-005 (deterministic outputs), REL-006 (≥95% accuracy on unseen)
**Brownfield triage:** BF-6 (schema_version: 1 add at next regeneration — cross-cut with Epic 1)
**Implementation notes:** Most tooling FRs are LEGACY-COMPLETE per the legacy distillate Sprint State — the unified V1 work consolidates them under a single epic to (1) verify they pass current AC, (2) add `schema_version: 1` to the writers (`map_config_generator.py`, `hash_comparator.py`), (3) regenerate `map_config.json` and commit alongside the schema bump (`pnpm --filter @warden/contracts build` regenerates Zod), (4) ensure `tooling-VALIDATE-001` regression suite covers the 14 canonical maps (4 maps still awaiting reference hashes per legacy: bastion, coliseum, lunar_outpost, the_rock). Tool 5 `warden_analyzer` AC validation against real-footage test set is the load-bearing remaining tooling work (legacy distillate: "Implementation Complete (AC unchecked — validation pending real-footage testing)").

### Epic 10: V1 Launch Readiness

**Type:** V1 launch gate (sequencing-final; resolves Decision #ES-7)
**User outcome:** V1 ships. The launch checklist is closed: pre-PRD performance spike has published `_bmad-output/architecture-spike-perf-floor.md`, Firestore Security Rules are deployed to production, Firebase v12 RN auth migration Story 3.F E2E sign-off of all 10 PRD journeys (J1–J10) is complete on Android dev build, Reader-App CI gate is green on mainline (signaling-tier defense-in-depth verified), [INVARIANT 8] EXPO_PUBLIC_AUTH_BYPASS deny in release configs is verified, ToS-monitoring tracker exists with one entry for EVA After-h. Stripe Production Activation (legacy Web Story 7.4) unblocks once company number is provided by Root.
**FRs covered:** *(launch-readiness gate — no new FRs; verifies all V1 FRs are in green state)*
**NFRs covered:** PERF-001 (post-launch verification on reference device), all SEC NFRs (production-deployed)
**CI/CD:** CI-2 (deploy-firestore-rules.yml — post-V1 polish; V0 = manual deploy already done in Epic 1 BF-2)
**Resolves Decision #ES-7** (V1 launch gate composition with story-traceable rows).
**Implementation notes:** This epic is a **deliverable manifest**, not a feature epic. Stories within Epic 10 are launch-checklist rows, each with a clear pass/fail gate and a responsible owner. Demand evidence capture (PRD §2: ≥ TBD coach interviews + waitlist depth + WTP validations) is PRD-mandated to capture before launch but is non-V1-blocking — sprint planning surfaces it as a parallel demand-evidence sprint. The Stripe Production Activation external dependency (Root provides company number) is a known-blocker carryover from legacy Web Story 7.4; if it doesn't unblock, launch slips on this single line item (no architectural fix; only operational unblocker).

---

**Total epics: 11** (Epic 0 transition gate + Epic 1 foundation + Epic 2 cross-surface contracts + Epics 3–9 user-value + Epic 10 launch gate).

**Resolved decisions in this step:**
- **Decision #ES-1 (Sprint 3 epic boundaries):** RESOLVED with the 11-epic structure above. Epic 0 is the Sprint 2.5 closure transition gate. Epic 1 is the V1-blocking foundation (architecture spike + brownfield + cross-language contracts + cross-surface invariants). Epic 2 lands the Reader-App build gate and the activation telemetry contract (separated from Epic 1 because both are surface-cross-cutting contracts that other epics consume — Epic 3 needs telemetry hooks; Epic 5 + 6 emit telemetry through the wrapper). Epic 3 lands the cross-surface six-state entitlement (mobile UI banners + web dashboard reflection); the user's example "Epic-4-Entitlement" maps here. Epic 4 is the web subscribe-and-manage funnel (consolidates legacy web Epic 1/2/3/5 carry-forward + UX-Sprint-3 web surface — token bump, OG card, password reset, cancel dialog). Epics 5/6/7/8 split mobile by user-value cluster (review / clip-and-export / reliability / localization-and-support) per the principle of feature-folder boundary rather than lumping into a single "mobile-UX-Sprint-3-Surface" epic. Epic 9 consolidates tooling. Epic 10 is launch readiness.
- **Decision #ES-3 (Sprint 2.5 per-story conflict audit):** RESOLVED — Epic 0 owns the audit table as its discrete deliverable. Per-story disposition rows for legacy mobile Sprint 2.5 stories 2.2 / 2.5 / 2.6 / 2.7 / 7.1 / 7.2 / 7.3 / 7.4 / 7.5 / 7.6.
- **Decision #ES-7 (V1 launch gate composition):** PARTIALLY RESOLVED — Epic 10 is the launch-checklist epic; explicit story-traceable rows will be enumerated in Step 3 (story creation).

## Story-Level Conventions

**Acceptance Criteria format (Decision #ES-5 RESOLVED):** Hybrid — Gherkin Given-When-Then for behavior-driven stories (most user-facing flows); explicit checklist for infrastructure stories (CI gate, regex narrow, token bump, schema_version add, etc.). Both formats live alongside each other; the choice is per-story based on whether the deliverable is "the user can…" (Gherkin) or "the artifact exists with these properties…" (checklist).

**Test ownership (Decision #ES-6 RESOLVED):** Each story declares which tests it adds, where they live, and what they cover. Test framework per surface (architecture-bound):
- Mobile: jest + jest-expo, co-located `__tests__/<subject>.test.ts(x)`
- Web: vitest + jsdom + @testing-library/react, co-located `<subject>.test.ts(x)`
- Tooling: pytest at `apps/tooling/tests/` with fixtures under `apps/tooling/tests/fixtures/`

**Sprint-fit gate (Decision #ES-9 RESOLVED):** No numeric estimates. Binary gate per story: `fits-in-one-sprint` (default; assumes solo-dev capacity) or `needs-spike-or-split` (flagged with reason). Story 1.1 (AR-SPIKE pre-PRD performance spike) is the only `needs-spike-or-split` story by design — its outcome dictates downstream story shape.

**Story-dependency conventions (Decision #ES-4 RESOLVED):** Each story declares prior-stories-only dependencies (no forward references). Cross-epic dependencies are explicit. Within an epic, stories are ordered such that later stories may depend on earlier ones but never the reverse.

---

## Epic 0: Sprint 2.5 Closure & Conflict Audit

**Goal:** Sprint 2.5 in-flight legacy mobile work either lands cleanly under existing AC ("complete-as-legacy") or is re-scoped into Sprint 3 with new AC. Sprint 3 starts from a clean baseline.

### Story 0.1: Conduct Per-Story Conflict Audit for Sprint 2.5 In-Flight Mobile Work

As **Stephane** (solo developer running unified Sprint 3 planning),
I want **a per-story conflict-audit table for the 10 in-flight legacy mobile Sprint 2.5 stories**,
So that **each story's disposition is binding (complete-as-legacy / re-scope-into-Sprint-3 / drop) before Sprint 3 commits scope.**

**Acceptance Criteria (checklist):**

- [ ] Audit table at `_bmad-output/sprint-2.5-conflict-audit.md` with one row per legacy Sprint 2.5 story: 2.2 (FFmpeg integration; in-progress), 2.5 (segment video; ready-for-dev), 2.6 (background processing + crash recovery; ready-for-dev), 2.7 (session list + management; ready-for-dev), 7.1 (SQLite view_mode 2-value→3-value; ready-for-dev), 7.2 (ClipExport view_mode TS union; ready-for-dev), 7.3 (view-mode toggle UI; ready-for-dev), 7.4 (DetectionConfig service no-op shim; ready-for-dev), 7.5 (detector replacement; ready-for-dev), 7.6 (export pipeline 3 view modes; ready-for-dev).
- [ ] Each row has columns: `story_id`, `legacy_AC_summary`, `unified_PRD_conflict` (yes/no), `conflict_specifics` (if yes — which PRD constraint conflicts: free-tier / pre-no-free-tier / Reader-App contract / etc.), `disposition` (complete-as-legacy | re-scope-into-Sprint-3-with-new-AC | drop), `target_epic` (if re-scoped: which Sprint 3 epic the new AC lands in), `responsible_owner`.
- [ ] **Audit rule applied:** Any story implying a free-tier or pre-no-free-tier flow conflicts with the unified PRD and MUST be re-scoped, not completed under legacy AC.
- [ ] Audit rule applied: Any story whose AC contradicts a locked PRD constraint (Reader-App contract structural, on-device-only video processing, six-state entitlement model, 14-canonical-maps reconciliation) is re-scoped or dropped.
- [ ] Audit rule applied: Stories whose AC is wholly compatible with the unified PRD ship as complete-as-legacy under existing AC; no rewrite.
- [ ] Audit gates Sprint 3 commit: until 0.1 is signed off, Sprint 3 stories CANNOT be merged.

**Tests:** No code tests (audit is a planning artifact). Manual review by Stephane against unified PRD §3 / §5 / §9 / §10 sections.

**Dependencies:** None (this is Epic 0 — runs first).

**Sprint fit:** fits-in-one-sprint.

### Story 0.2: Execute Sprint 2.5 Per-Story Dispositions

As **Stephane**,
I want **each Sprint 2.5 story disposition from Story 0.1 executed end-to-end**,
So that **complete-as-legacy stories merge through their existing AC, re-scoped stories have new AC entries in their target epic, and dropped stories are formally archived with rationale.**

**Acceptance Criteria (checklist):**

- [ ] For each row in Story 0.1's audit table marked `complete-as-legacy`: legacy story file (under `apps/mobile/docs/stories/` or wherever it lives) is updated with a final completion note ("complete-as-legacy under unified Sprint 3 audit 2026-05-07; AC unchanged"); the story's PR merges through the existing AC.
- [ ] For each row marked `re-scope-into-Sprint-3-with-new-AC`: a new story is added to the target epic in this document (`_bmad-output/epics-and-stories.md`) with new AC reflecting the unified PRD constraint; the legacy story file is annotated as superseded with a pointer to the new story ID.
- [ ] For each row marked `drop`: the legacy story file is annotated as dropped with rationale and a pointer to the rationale source (PRD section / architecture decision / etc.).
- [ ] No legacy Sprint 2.5 story remains in `ready-for-dev` or `in-progress` state without a disposition tag after this story closes.

**Tests:** No code tests. Manual verification: `git log` shows disposition annotations; new AC stories appear in their target epics.

**Dependencies:** Story 0.1.

**Sprint fit:** fits-in-one-sprint.

---

## Epic 1: Foundations — V1-Blocking Spike, Brownfield Reconciliation & Cross-Language Contracts

**Goal:** All V1-launch-blocking foundation work is complete and verified: pre-PRD performance spike published with measured PERF-010 floor and Innovation #1 ladder rung; Firebase v12 RN auth migration signed off end-to-end; user-doc + map-config contracts single-sourced and strict; Foreground Service plugin keeps mobile pipeline alive; Stripe webhook idempotency regression-covered; Firestore rules deployed to production with extended coverage.

### Story 1.1: Pre-PRD Performance Spike (AR-SPIKE) — Resolves Decision #ES-2

As **Stephane**,
I want **the OpenCV JSI binding shipped as a real binding (not the current `loadFrameFromPath` stub) on the Poco X5 reference device, with measured PERF-002/003/004/005 numbers and validated map-ID and round-boundary accuracy floors**,
So that **PERF-010 is bound, the Innovation #1 ladder rung is determined, and Sprint 3 mobile story scope can finalize against the spike outcome.**

**Acceptance Criteria (checklist; this is an architecture-led spike, not a feature story):**

- [ ] `apps/mobile/src/shared/services/opencv.ts` — `loadFrameFromPath(path)` returns a real `FrameBuffer` (no longer throws). Implementation uses `react-native-fast-opencv` JSI binding (already a dep in `apps/mobile/package.json`).
- [ ] Reference device: Poco X5 (Snapdragon 695, 6 GB RAM, 6.67"; Android 13). Source: a 1h20 reference EVA After-h video (architecture-team-supplied; not committed to repo).
- [ ] Measured: PERF-002 — auto-slice ≤ 5% of source duration (1h20 → ≤ 4 min).
- [ ] Measured: PERF-003 — view-mode toggle ≤ 100 ms (no player swap; crop/style change on same `expo-av` source).
- [ ] Measured: PERF-004 — Cinema Mode cold-start ≤ 1.5 s.
- [ ] Measured: PERF-005 — clip export ≤ 2× clip duration (Mobile-tier; 30 s clip → ≤ 60 s encode).
- [ ] Validated: map ID accuracy ≥ 95% on an unseen test set (via legacy `apps/tooling/tools/hash_validator.py` regression suite).
- [ ] Validated: round-boundary detection floor (anchored to legacy tooling target "100% black-screen-transition detection with 0 false positives"; on-device port may degrade — spike sets the floor).
- [ ] Spike-outcome ladder rung determined: **pass** (V1 ships with auto-slice on, PRD inherits measured PERF-010) | **partial-fail rung 1** (lower frame-sampling rate; PRD adds "with reduced sampling on weak hardware" clause to `mobile-AUTO-SLICE-001`) | **partial-fail rung 2** (drop Minimap+HUD overlay on weak hardware; PRD adds device-profile-gated clause to `mobile-CINEMA-002`) | **hard fail rung 3** (defer auto-slice to V2; V1 ships manual-clip-only via Decision #UX-14 path).
- [ ] **FORBIDDEN ladder outcome (asserted):** cloud fallback. Breaks Innovation #1 (privacy + lower marginal cost). NOT a permitted rung regardless of measured numbers.
- [ ] Deliverable: `_bmad-output/architecture-spike-perf-floor.md` published with measured numbers, device profile, ladder rung verdict, regression-test fixtures used, V1 implication summary.
- [ ] PRD updated post-spike: PERF-010 inherits the published number; conditional FR clauses added per ladder rung outcome (if applicable).
- [ ] Sprint 3 story-scope finalization gated on this story's completion (Stories 1.4–1.18, 5.x, 6.x all consume the outcome).

**Tests:** No automated tests in this story (the spike IS the test; produces fixtures for downstream regression suites). Architecture-published `architecture-spike-perf-floor.md` is the artifact.

**Dependencies:** None (this is Epic 1 first story; gates everything else in Sprint 3).

**Sprint fit:** **needs-spike-or-split** — by design, this IS the spike. If spike returns rung 3, downstream story estimates change materially (mobile-AUTO-SLICE-* FRs become V2-deferred; mobile review surface re-orients around manual-clip-from-timeline). All other Sprint 3 stories assume pass / rung 1 / rung 2 outcomes; rung 3 triggers a Sprint 3 re-scope.

### Story 1.2: Foreground Service Android Config Plugin (BF-5)

As **Stephane**,
I want **a custom `expo-config-plugin` injecting an Android Foreground Service that hosts the main JS context for the duration of the processing pipeline**,
So that **the J2 interruption + resume scenario works on Android — the pipeline survives backgrounding without OS-killing the JS context, and FFmpeg/OpenCV JSI bindings remain usable across foreground/background transitions.**

**Acceptance Criteria (checklist):**

- [ ] `apps/mobile/plugins/with-foreground-service.js` — Expo config plugin modifies `AndroidManifest.xml` to declare `<service android:name=".WardenProcessingService" android:foregroundServiceType="dataSync"/>` and adds `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_DATA_SYNC` permissions.
- [ ] `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt` (generated post-`expo prebuild`) — sticky notification "Analyse en cours…" with progress percentage from MMKV `processing.<sessionId>.stage`.
- [ ] `apps/mobile/src/features/video-processing/processingPipeline.ts` calls into the service via a JSI bridge module to start/stop the foreground state.
- [ ] Notification channel: `processing` (low importance — non-disruptive).
- [ ] Service lifecycle: started on `runProcessingPipeline` entry; stopped on pipeline completion or error (regardless of pipeline outcome — never leak the service).
- [ ] Manual test: J2 (interruption + resume) on Android dev build with Battery Optimization both enabled and disabled. Pipeline resumes from MMKV checkpoint after backgrounding.
- [ ] iOS Phase 2 readiness asserted: architecture asserts cross-platform-readiness; `BGTaskScheduler` design deferred to iOS Phase 2.

**Tests:** No automated tests for the native service (manual J2 verification on dev build is the regression). `processingPipeline.ts` unit tests at `apps/mobile/src/features/video-processing/__tests__/processingPipeline.test.ts` cover the start/stop service-bridge calls via mock.

**Dependencies:** None (independent of spike; can land in parallel).

**Sprint fit:** fits-in-one-sprint.

### Story 1.3: Stripe API Pin Bump 2026-03-25.dahlia → 2026-04-22.dahlia (BF-1)

As **Stephane**,
I want **the Stripe API version pin bumped to match installed `@stripe` types**,
So that **Vitest test-file type errors (spread args, implicit any) resolve and webhook event schemas continue to parse against the dahlia API line.**

**Acceptance Criteria (checklist):**

- [ ] `apps/web/src/lib/stripe/server.ts:STRIPE_API_VERSION` bumped to `2026-04-22.dahlia`.
- [ ] Stripe API changelog reviewed for the inter-version delta: any concrete breaking change identified is documented; if a breaking change surfaces, FALLBACK is to freeze pin at `2026-03-25.dahlia` and downgrade installed types (per PRD Decision #4 disposition).
- [ ] `pnpm --filter web typecheck` passes — all `*.test.ts` TS errors fixed (spread args, implicit `any`).
- [ ] `pnpm --filter web test` passes — full Vitest suite green; webhook event schemas in `webhook-events.ts` parse against the new API version.
- [ ] Stripe Dashboard webhook endpoint configured to `2026-04-22.dahlia` (operator action; documented in `docs/deployment-guide.md`).

**Tests:** Existing Vitest suite at `apps/web/src/lib/stripe/__tests__/webhooks.test.ts` validates webhook event schemas still parse. No new tests needed (regression coverage by existing suite).

**Dependencies:** None (independent; can land in parallel with spike + Firebase migration).

**Sprint fit:** fits-in-one-sprint.

### Story 1.4: Firebase v12 RN Auth Migration — Add Deps + Prebuild (Story 3.A)

As **Stephane**,
I want **`@react-native-firebase/app`, `@react-native-firebase/auth`, `@react-native-firebase/firestore` added to `apps/mobile/package.json` and `expo prebuild` run cleanly**,
So that **the migration from Firebase JS SDK v12 to RN Firebase native modules can proceed (the JS SDK's `getReactNativePersistence` symbol is the V1-blocking forcing function).**

**Acceptance Criteria (checklist):**

- [ ] `apps/mobile/package.json` adds `@react-native-firebase/app`, `@react-native-firebase/auth`, `@react-native-firebase/firestore` at versions compatible with RN 0.81 / Expo SDK 54.
- [ ] `pnpm install` succeeds; `.npmrc` `node-linker=hoisted` ([INVARIANT 9]) preserved.
- [ ] `pnpm --filter mobile exec expo prebuild` succeeds; native `android/` directory regenerated.
- [ ] `pnpm --filter mobile exec expo export --platform android` succeeds (Hermes bundle ≈ 5.22 MB; Phase 4 acceptance smoke test).
- [ ] `google-services.json` placed at `apps/mobile/android/app/google-services.json` (or equivalent Expo-managed location); contains the same Firebase project ID as web's `apps/web/.env.example` per [INVARIANT 2] / Decision #3.
- [ ] No code changes to `firebaseConfig.ts` / `authService.ts` / `subscriptionService.ts` yet — those land in Stories 1.5/1.6/1.7.

**Tests:** Smoke build verification only. No new automated tests in this story (auth code paths still use legacy v12 JS SDK at this point).

**Dependencies:** None within Epic 1 (spike is parallel; this can start once 1.1 spike has a binding choice on whether real JSI binding ships).

**Sprint fit:** fits-in-one-sprint.

### Story 1.5: Firebase v12 RN Auth Migration — Migrate firebaseConfig.ts (Story 3.B)

As **Stephane**,
I want **`apps/mobile/src/features/auth/firebaseConfig.ts` rewritten to use `@react-native-firebase/auth` auto-config from `google-services.json`**,
So that **the legacy v12 JS SDK init (which uses the now-removed `getReactNativePersistence` symbol) is replaced with the native-module-backed init that handles Keychain/Keystore persistence automatically.**

**Acceptance Criteria (checklist):**

- [ ] `apps/mobile/src/features/auth/firebaseConfig.ts` no longer imports from `firebase/auth` or `firebase/app`. New imports: `@react-native-firebase/app`, `@react-native-firebase/auth`.
- [ ] Persistence is automatic (Keychain on iOS Phase 2; Keystore on Android V1) — no explicit `getReactNativePersistence` call.
- [ ] Login flow smoke-tested on dev build: email/password sign-in succeeds; Google sign-in via `@react-native-google-signin/google-signin` v14 succeeds.
- [ ] `EXPO_PUBLIC_AUTH_BYPASS=false` (or unset) in dev `.env.local` produces actual Firebase auth; `EXPO_PUBLIC_AUTH_BYPASS=true` short-circuits per legacy dev path ([INVARIANT 8]).
- [ ] No regression: app boot still proceeds to LoginScreen on cold start.

**Tests:** Manual smoke test on dev build (auth code paths require native module). Existing jest tests under `apps/mobile/src/features/auth/__tests__/` still pass (any imports of legacy `firebaseConfig` are updated to mock the new module path).

**Dependencies:** Story 1.4.

**Sprint fit:** fits-in-one-sprint.

### Story 1.6: Firebase v12 RN Auth Migration — Migrate authService.ts (Story 3.C)

As **Stephane**,
I want **`apps/mobile/src/features/auth/authService.ts` rewritten to use `@react-native-firebase/auth` API surface (`auth().signInWithEmailAndPassword`, `auth().onAuthStateChanged`, `auth().signOut`)**,
So that **all auth orchestration uses the native module surface, not the legacy v12 JS SDK.**

**Acceptance Criteria (checklist):**

- [ ] `signInWithEmailAndPassword(auth, email, password)` → `auth().signInWithEmailAndPassword(email, password)`.
- [ ] `signInWithCredential(auth, credential)` → `auth().signInWithCredential(credential)` (Google sign-in path).
- [ ] `signOut(auth)` → `auth().signOut()`.
- [ ] `onAuthStateChanged(auth, fn)` → `auth().onAuthStateChanged(fn)`.
- [ ] `mapFirebaseUser` continues to call `subscriptionService.checkSubscription` and emit T0 telemetry (when telemetry wrapper from Epic 2 lands; for now, T0 emit is a TODO comment).
- [ ] All existing jest tests at `apps/mobile/src/features/auth/__tests__/authService.test.ts` pass with mocks updated to `@react-native-firebase/auth`.
- [ ] Manual smoke test: sign-in / sign-out / persistence-across-cold-restart all work.

**Tests:** Updated jest tests at `apps/mobile/src/features/auth/__tests__/authService.test.ts` mock `@react-native-firebase/auth` and assert call sequences. Mocks set up via `jest.mock('@react-native-firebase/auth', () => ({...}))`.

**Dependencies:** Story 1.5.

**Sprint fit:** fits-in-one-sprint.

### Story 1.7: Firebase v12 RN Auth Migration — Migrate subscriptionService.ts (Story 3.D)

As **Stephane**,
I want **`apps/mobile/src/features/auth/subscriptionService.ts` rewritten to use `@react-native-firebase/firestore` reads**,
So that **all entitlement reads (`users/{uid}.status`, `current_period_end`) come from the native module — load-bearing for the six-state entitlement state machine in Epic 3.**

**Acceptance Criteria (checklist):**

- [ ] `getDoc(doc(db, 'users', uid))` → `firestore().collection('users').doc(uid).get()`.
- [ ] `isSubscriptionPaid(userDoc)` continues to accept `status ∈ {active, trialing}` AND `current_period_end > now` as paid (preserved from legacy; defense-in-depth for Decision #9 trialing handling).
- [ ] Periodic re-validation (60-min interval) preserved: `subscriptionService.startPeriodicRevalidation`.
- [ ] Network failures fall back to MMKV-cached `useAuthStore.user.isPaid` per `mobile-AUTH-004` 30-day offline-grace.
- [ ] **Six-state entitlement regression test scaffolding added at `apps/mobile/src/features/auth/__tests__/deriveEntitlementState.test.ts`** — one test per state (paid / lapsed / offline-grace ≤30d / payment-failed / multi-device / signed-out). Stub `deriveEntitlementState` at this story; full implementation lands in Story 3.1 (Epic 3).

**Tests:** Updated jest tests at `apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts` mock `@react-native-firebase/firestore`. New test file `deriveEntitlementState.test.ts` scaffolded with one `describe` block per entitlement state (assertions filled in Story 3.1).

**Dependencies:** Story 1.6.

**Sprint fit:** fits-in-one-sprint.

### Story 1.8: Firebase v12 RN Auth Migration — Migrate detectionConfigService.ts (Story 3.E)

As **Stephane**,
I want **`apps/mobile/src/features/video-processing/detectionConfigService.ts` rewritten to use `@react-native-firebase/firestore` reads**,
So that **the stale-while-revalidate `detection_config/latest` read uses the native module; singleflight semantics (3 inflight gates: initial / background / forced) preserved.**

**Acceptance Criteria (checklist):**

- [ ] `getDoc(doc(db, 'detection_config', 'latest'))` → `firestore().collection('detection_config').doc('latest').get()`.
- [ ] Three singleflight inflight gates preserved: `inflightInitialFetch`, `inflightBackgroundRefresh`, `inflightForcedRefresh`.
- [ ] Schema validation via `validateDetectionConfig` (Zod) preserved; invalid payloads silently discarded; bundled fallback engaged per Decision #2 (Story 1.13 implements bundled-asset path).
- [ ] Manual smoke test: stale-while-revalidate cycle works post-migration (cache miss → Firestore read → cache populate → next read returns cache; background refresh after cache age threshold).

**Tests:** Updated jest tests at `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts` mock `@react-native-firebase/firestore`; assert singleflight semantics + cache TTL behavior.

**Dependencies:** Story 1.7.

**Sprint fit:** fits-in-one-sprint.

### Story 1.9: Firebase v12 RN Auth Migration — End-to-End Manual Test of All 10 PRD Journeys (Story 3.F)

As **Stephane**,
I want **all 10 PRD journeys (J1–J10) manually validated end-to-end on Android dev build post-migration**,
So that **Sprint 3 binds with confidence that the entitlement state machine, auto-slice, Cinema Mode, clip export, and offline-grace all work post-migration — V1-blocking sign-off gate per architecture.**

**Acceptance Criteria (checklist):**

- [ ] J1 (Coach Thomas first-time activation cross-surface happy path) verified on dev build: web checkout → mobile install → mobile sign-in → import → auto-slice → Card View → Cinema Mode → clip → voice → export → share. T0 + T1-coach telemetry events fire (pre-Epic-2 wrapper: emit raw `firebaseAnalytics.logEvent` calls; Epic 2 wraps).
- [ ] J2 (steady-state with interruption + auto-save) verified: backgrounding mid-clip → reopen → exact-frame resume + voice annotation preserved.
- [ ] J3 (CV failure modes — unknown map + missed round) verified: graceful degradation; navigation works.
- [ ] J4 (Active Player solo path — no export, view-mode toggle) verified: T1-active-player path emits.
- [ ] J5 (Discord-inline-playable MP4) verified: exported MP4 plays inline in Discord without app install.
- [ ] J6 (Passive→Active conversion) verified: same flow as J1 with different persona narrative.
- [ ] J7 (payment failure recovery) verified: webhook → status `past_due` → mobile banner → Customer Portal → status `active` → banner clears.
- [ ] J8 (cancellation) verified: web cancel → confirmation dialog (no exit survey) → status `canceling` → period end → status `canceled` → mobile lapsed screen → resubscribe → restore session data.
- [ ] J9 (offline-grace 30 days) verified: airplane-mode → app fully usable → sign back online → state cleared.
- [ ] J10 (developer regenerates map_config.json) verified via tooling pipeline (Epic 9).
- [ ] Sign-off note in `_bmad-output/architecture-spike-perf-floor.md` (or a separate `_bmad-output/v1-launch-readiness-checklist.md` artifact in Epic 10) records the J1–J10 verdict per journey.

**Tests:** Manual journey verification only. No new automated tests (E2E test framework wiring is V2 backlog per legacy distillate).

**Dependencies:** Stories 1.4–1.8.

**Sprint fit:** fits-in-one-sprint (large but bounded; one focused day of E2E verification on dev build).

### Story 1.10: user-doc.schema.json Tighten + Reconcile (AR-1, Decision #1)

As **Stephane**,
I want **`contracts/user-doc.schema.json` cleaned up: drop legacy `isPaid`, add formal `created_at` / `updated_at`, tighten `additionalProperties: true → false`**,
So that **the `users/{uid}` Firestore wire-shape contract is the single source of truth across web (Zod) and mobile (read-only) — no schema drift possible at runtime.**

**Acceptance Criteria (checklist):**

- [ ] `contracts/user-doc.schema.json` removes optional `isPaid` field.
- [ ] `contracts/user-doc.schema.json` adds optional `created_at: string` and `updated_at: string` formal slots.
- [ ] `contracts/user-doc.schema.json` sets `additionalProperties: false`.
- [ ] `pnpm --filter @warden/contracts build` regenerates `packages/contracts/src/generated/user-doc.ts` (Zod surface).
- [ ] `apps/mobile/.env.example` legacy `users/{uid}.isPaid` documentation comment removed.
- [ ] Web `apps/web/src/lib/firebase/` Zod `.transform()` helpers continue to convert snake_case Firestore reads to camelCase TS objects for `useSubscription` consumers; transformation unchanged.
- [ ] Mobile `useAuthStore.user.isPaid` continues to be a derived TS field (computed at last-Firestore-read time, persisted in MMKV) — NOT a Firestore field. Legacy offline-fallback pattern preserved.

**Tests:** New Vitest test at `apps/web/src/lib/schemas/__tests__/user-doc-strict.test.ts` asserts the regenerated Zod schema rejects payloads with unknown keys (validates `additionalProperties: false`). Mobile jest test at `apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts` updated to assert `isPaid` is not in the wire schema (only computed locally).

**Dependencies:** None (independent of spike + Firebase migration).

**Sprint fit:** fits-in-one-sprint.

### Story 1.11: Wire apps/web to @warden/contracts/user-doc (AR-2, Decision #6)

As **Stephane**,
I want **`apps/web/src/lib/schemas/subscription.ts` to re-export the contract's `UserDocSchema` instead of redeclaring `subscriptionResponseSchema`**,
So that **the brownfield-flagged "schema diverges from `@warden/contracts/user-doc`" debt is closed and any future contract bump propagates to web consumers via `pnpm --filter @warden/contracts build`.**

**Acceptance Criteria (checklist):**

- [ ] `apps/web/src/lib/schemas/subscription.ts` becomes a one-liner: `export { UserDocSchema as subscriptionResponseSchema } from '@warden/contracts/user-doc';`
- [ ] All call sites preserved: `apps/web/src/app/api/subscription/route.ts`, `apps/web/src/hooks/useSubscription.ts` keep their imports unchanged (named export `subscriptionResponseSchema` is preserved).
- [ ] `pnpm --filter web typecheck` passes.
- [ ] `pnpm --filter web test` passes — existing tests at `apps/web/src/lib/schemas/__tests__/` validate the contract surface still parses webhook handler outputs.

**Tests:** Existing `apps/web/src/lib/schemas/__tests__/subscription.test.ts` regresses against the new import. No new tests.

**Dependencies:** Story 1.10.

**Sprint fit:** fits-in-one-sprint.

### Story 1.12: customer.subscription.updated Defensive Handler (AR-3, Decision #9)

As **Stephane**,
I want **a `handleSubscriptionUpdated` event handler added to `apps/web/src/lib/stripe/webhooks.ts` that maps Stripe `trialing` → `active`**,
So that **when a coupon redemption produces a Stripe `trialing` subscription, the webhook fires immediately (rather than waiting for the trial-end `invoice.paid`) and the activation timer can fire on T0 without delay.**

**Acceptance Criteria (checklist):**

- [ ] `apps/web/src/lib/stripe/webhooks.ts:routeEvent` switch adds `case 'customer.subscription.updated': return self.handleSubscriptionUpdated(event);` (using the self-namespace pattern per [INVARIANT 4]).
- [ ] New `handleSubscriptionUpdated(event)`:
  - Validate via new Zod schema in `apps/web/src/lib/schemas/webhook-events.ts:subscriptionUpdatedSchema` (mirror existing dahlia `parent.subscription_details.subscription` nesting).
  - If `subscription.status === 'trialing'`: write `users/{firebase_uid}` `{ status: 'active', plan, current_period_end: trial_end_as_Timestamp, stripe_subscription_id, stripe_customer_id, updated_at: serverTimestamp() }`.
  - If `subscription.status === 'active'`: write the same shape with `current_period_end` from the next-billing date.
  - If `subscription.status === 'past_due'`: write `{ status: 'past_due', updated_at: serverTimestamp() }`.
  - If `subscription.status === 'canceled'`: no-op (let `customer.subscription.deleted` handle it).
- [ ] Stripe Dashboard configured to fire `customer.subscription.updated` events (operator action; documented in `docs/deployment-guide.md`).
- [ ] Vitest test at `apps/web/src/lib/stripe/__tests__/webhooks.test.ts` covers the trialing → active transition; preserves the self-namespace `vi.spyOn(webhooksModule, 'handleSubscriptionUpdated')` pattern.

**Tests:** New Vitest cases at `apps/web/src/lib/stripe/__tests__/webhooks.test.ts` for the trialing → active handler. Self-namespace pattern preserved.

**Dependencies:** Stories 1.10, 1.11.

**Sprint fit:** fits-in-one-sprint.

### Story 1.13: Hybrid map_config.json Delivery + schema_version: 1 (AR-4 + BF-6)

As **Stephane**,
I want **`apps/mobile/assets/map_config.json` committed as a Metro-bundled baseline AND `detectionConfigBootstrap.ts` rewritten to read the bundled asset on first launch**,
So that **the no-cache + offline first-launch error path is eliminated, the bundled config is always available, and Firestore overlay updates via stale-while-revalidate work between Play Store releases.**

**Acceptance Criteria (checklist):**

- [ ] `apps/mobile/assets/map_config.json` committed; matches the latest `apps/tooling/tools/map_config_generator.py` output; carries `schema_version: 1`.
- [ ] `apps/tooling/tools/map_config_generator.py` and `apps/tooling/tools/hash_comparator.py` write `schema_version: 1` at next regeneration (BF-6 hook in tooling).
- [ ] `contracts/map-config.schema.json` adds `schema_version: integer >= 1` as a required field; `additionalProperties: false` preserved.
- [ ] `pnpm --filter @warden/contracts build` regenerates `packages/contracts/src/generated/map-config.ts` (Zod requires `schema_version`).
- [ ] `apps/mobile/src/features/video-processing/detectionConfigBootstrap.ts` reads bundled asset on first launch via Metro asset import.
- [ ] `apps/mobile/src/features/video-processing/detectionConfigService.ts` retains stale-while-revalidate Firestore overlay; bundled config falls back when Firestore overlay is malformed (`MalformedRemoteConfigError` path preserved).
- [ ] `OfflineFirstLaunchError` sticky path REMOVED; `docs/architecture-mobile.md` updated: "falls back to bundled `map_config.json` from app asset bundle."
- [ ] Mobile `validateDetectionConfig` accepts `schema_version: 1` only for V1; rejection of unknown versions falls back to bundled.

**Tests:** Updated jest tests at `apps/mobile/src/features/video-processing/__tests__/detectionConfigBootstrap.test.ts` cover bundled-asset read on cold start. Updated jest tests at `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts` cover the bundled fallback when remote payload schema-fails. Tooling pytest at `apps/tooling/tests/test_map_config_generator.py` asserts `schema_version: 1` is in the emitted output.

**Dependencies:** Stories 1.10 (contract regeneration pipeline) + Epic 9 Story 9.1 (tooling emit) — but for V1, this story bundles both sides into one PR (the schema bump + the regenerated map_config.json + the mobile bundled-asset wire-up).

**Sprint fit:** fits-in-one-sprint.

### Story 1.14: Firestore Rules Coverage Extended (AR-6, Decision #7)

As **Stephane**,
I want **`apps/web/firestore.rules` rewritten to cover `users/{uid}` (owner read; deny client write), `detection_config/{docId}` (signed-in read; deny client write), and `stripe_events/{eventId}` (deny all client) with a catch-all deny**,
So that **the Reader-App contract is reinforced at the rules layer ([INVARIANT 2]), the `detection_config` overlay is auth-gated, and `stripe_events` is server-only.**

**Acceptance Criteria (checklist):**

- [ ] `apps/web/firestore.rules` matches the architecture spec exactly:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read:  if request.auth != null && request.auth.uid == userId;
      allow write: if false;
    }
    match /detection_config/{docId} {
      allow read:  if request.auth != null;
      allow write: if false;
    }
    match /stripe_events/{eventId} {
      allow read, write: if false;
    }
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```
- [ ] Local Firebase Emulator suite verifies the rules: signed-in user can read own `users/{uid}`; signed-in user can read `detection_config/latest`; client cannot write any path.
- [ ] No code change needed in webhook handlers (firebase-admin bypasses rules already).

**Tests:** Local Firebase Emulator test suite (manual; not yet wired into `pnpm --filter web test`). Documented in `apps/web/firestore.rules.test.md` (V2 candidate for automated rule testing).

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

### Story 1.15: Firestore Rules Production Deploy (BF-2)

As **Stephane**,
I want **`apps/web/firestore.rules` deployed to the production Firebase project**,
So that **production enforces the extended coverage and Reader-App posture is mechanically reinforced (V1-blocking per SEC-003).**

**Acceptance Criteria (checklist):**

- [ ] Run `cd apps/web && firebase deploy --only firestore:rules --project <production-project-id>`.
- [ ] Firebase Console verifies the deployed rules match the file at the time of deploy.
- [ ] Smoke test: anonymous client cannot read `users/{any}` (returns permission-denied); signed-in client can read own `users/{uid}` but not other users'; signed-in client can read `detection_config/latest`; no client can write any path.
- [ ] Sign-off note added to V1 launch checklist (Epic 10 deliverable): "firestore.rules deployed to prod 2026-XX-XX; smoke test green."

**Tests:** Manual smoke test against production project (operator action). No automated tests (production deploys aren't testable in CI without elevated credentials).

**Dependencies:** Story 1.14.

**Sprint fit:** fits-in-one-sprint.

### Story 1.16: detection_config/latest Operator Documentation + Shared Firebase Project Documentation (AR-5 + AR-7 + Decision #3 + Decision #8)

As **Stephane**,
I want **`docs/deployment-guide.md` updated with: (a) the `detection_config/latest` manual upload command for OTA map updates between releases, (b) the shared Firebase project convention asserting that web's `NEXT_PUBLIC_FIREBASE_PROJECT_ID` and mobile's `EXPO_PUBLIC_FIREBASE_PROJECT_ID` MUST match**,
So that **operator actions are documented and the shared-project convention is codified before CI assertion lands in V1.1.**

**Acceptance Criteria (checklist):**

- [ ] `docs/deployment-guide.md` adds a section "OTA map_config.json updates between releases" with the upload command:
```bash
firebase firestore:set detection_config/latest \
  apps/mobile/assets/map_config.json \
  --project <project-id>
```
- [ ] `docs/deployment-guide.md` adds a section "Shared Firebase project convention (Decision #3)" asserting that web's `NEXT_PUBLIC_FIREBASE_PROJECT_ID` and mobile's `EXPO_PUBLIC_FIREBASE_PROJECT_ID` MUST match — both `.env.example` files contain the same project ID; both Vercel and EAS Build env vars resolve to the same Firebase project.
- [ ] `docs/deployment-guide.md` adds a section "Stripe Dashboard event subscription configuration" listing the events Warden's webhook subscribes to: `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated` (Decision #9), `customer.subscription.deleted`.
- [ ] V1.1 Phase-7 backlog: CI assertion in `.github/workflows/ci.yml` enforces the shared-project convention mechanically (V1 ships with documentation-only enforcement).

**Tests:** No code tests (documentation deliverable). Manual review for accuracy.

**Dependencies:** Story 1.13 (the upload command references the bundled-asset path).

**Sprint fit:** fits-in-one-sprint.

### Story 1.17: Webhook Idempotency Regression Coverage (AR-9)

As **Stephane**,
I want **Vitest cases added at `apps/web/src/lib/stripe/__tests__/webhooks.test.ts` covering each idempotency strategy: event-ID dedup, merge-write business-state observation, and routing-failure 200 response — including the new `customer.subscription.updated` handler from Story 1.12**,
So that **the dual-strategy idempotency contract has regression coverage and any future change to webhook routing is mechanically verified.**

**Acceptance Criteria (checklist):**

- [ ] Test case: event-ID dedup. Re-applying the same event (same `event.id`) returns `200 { duplicate: true }` and short-circuits via `runTransaction` check on `stripe_events/{event.id}`.
- [ ] Test case: business-state observation merge writes. `handleInvoicePaid` re-applied to an already-`active` `users/{uid}` is a no-op-equivalent (same fields, server-stamped `updated_at` differs only by clock).
- [ ] Test case: `handleSubscriptionDeleted` no-op when `status` is already `canceled`.
- [ ] Test case: `handlePaymentFailed` no-op when `status` is already `past_due` OR `canceled`.
- [ ] Test case: `handleSubscriptionUpdated` no-op when `status === 'canceled'` (let `customer.subscription.deleted` handle it).
- [ ] Test case: routing failure for an unsubscribed event type returns `200 { routingError: true }` (stops Stripe retries).
- [ ] All tests preserve the self-namespace `vi.spyOn(webhooksModule, 'handleX')` pattern per [INVARIANT 4].

**Tests:** This story IS the test-add story.

**Dependencies:** Story 1.12.

**Sprint fit:** fits-in-one-sprint.

### Story 1.18: Vitest Serial-Mode V1 CI Workaround (BF-4)

As **Stephane**,
I want **Vitest configured to run in serial mode for V1 commits (workaround for the documented parallelism flake)**,
So that **CI passes reliably without fixing the underlying flake (V2 backlog item).**

**Acceptance Criteria (checklist):**

- [ ] `apps/web/vitest.config.ts` adds `pool: 'forks'` and `poolOptions: { forks: { singleFork: true } }` (or equivalent serial-mode config per current Vitest 4 API).
- [ ] `pnpm --filter web test` passes locally (serial mode);  the parallelism flake from legacy Web Epic 4 retro is mechanically avoided.
- [ ] V2 backlog entry created in this document's V2 backlog seed section: "Diagnose Vitest parallelism flake; restore parallel mode."

**Tests:** No new tests; this story changes test runner config.

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

---

## Epic 2: Reader-App Build Gate & Activation Telemetry Contract

**Goal:** Mobile build artifacts cannot accidentally drift into containing monetization-surface code; activation telemetry under privacy-by-construction emits T0 + dual-T1 with payload allowlist enforced at wrapper level.

### Story 2.1: Reader-App CI Gate Implementation

As **Stephane**,
I want **`apps/mobile/scripts/reader-app-gate.sh` and a CI workflow invocation that scan `apps/mobile/**/*.{ts,tsx,js,jsx}` and `apps/mobile/assets/i18n/**` for direct-import bans, transitive-dep bans (via `pnpm ls --depth=Infinity`), and banned strings (regex narrowed per FU-4 to verb forms only)**,
So that **the Reader-App posture against App Store / Play Store policy is mechanically reinforced at signaling-tier defense-in-depth, propagating through every entitlement and monetization decision.**

**Acceptance Criteria (checklist):**

- [ ] `apps/mobile/scripts/reader-app-gate.sh` script exists and is executable.
- [ ] Banned direct-import regexes: `from\s+['"]react-native-iap['"]`, `from\s+['"]expo-in-app-purchases['"]`, `from\s+['"]@stripe/stripe-react-native['"]`, `from\s+['"]@stripe/stripe-js['"]`. Match anywhere in `apps/mobile/src/**/*.{ts,tsx,js,jsx}`.
- [ ] Banned plan-picker imports: `@/components/checkout/PlanCard`, `@/components/checkout/PlanCta`, `@/components/checkout/CouponInput`. (These live under `apps/web/src/components/checkout/` and MUST NOT be imported by mobile.)
- [ ] Banned transitive deps via `pnpm ls --filter mobile --depth=Infinity` (parsed): zero entries for `react-native-iap`, `expo-in-app-purchases`, `@stripe/stripe-react-native`.
- [ ] Banned string regexes (case-insensitive; narrowed per FU-4):
  - `€7\.99`, `€79\.90`, `7\.99\s*€`, `79\.90\s*€`
  - `\b(subscribe|s'?abonner|abonnez-vous|monthly|yearly|mensuel|annuel|buy|acheter)\b`
  - **The noun "abonnement" is PERMITTED** in entitlement-state UI labels per FU-4 (mobile copy "Gérer mon abonnement" / "Abonnement requis" LOCKED). The regex MUST NOT match the bare noun `\babonnement\b`; it matches only the verb forms `s'?abonner` and `abonnez-vous`.
- [ ] Gate behavior: any match fails CI with the matched line + path + filename. No allowlist mechanism (per architecture spec).
- [ ] `EXPO_PUBLIC_AUTH_BYPASS=true` in any release-config file fails the gate ([INVARIANT 8]).
- [ ] Gate engaged via `.husky/pre-commit` (mobile-only commits run the gate locally before push).
- [ ] V0 fallback (until Phase-7 CI lands): pre-commit hook is the only enforcement; manual run of `apps/mobile/scripts/reader-app-gate.sh` documented in `apps/mobile/RELEASE.md`.
- [ ] **Gate verifies on current `apps/mobile/` tree:** zero matches. (If matches surface, fix before merging this story.)

**Tests:** Self-test: script exits with non-zero code when run against a synthetic file containing one of the banned patterns. Test fixtures at `apps/mobile/scripts/__tests__/reader-app-gate-fixtures/` (small `.ts` files with each banned pattern).

**Dependencies:** None within Epic 2; cross-epic depends on Story 1.4 (RN auth migration in progress — gate scans must pass against the migrated `firebaseConfig.ts`).

**Sprint fit:** fits-in-one-sprint.

### Story 2.2: Activation Telemetry Wrapper + Payload Allowlist

As **Stephane**,
I want **`apps/mobile/src/shared/services/analytics.ts` enforcing a payload allowlist at runtime: permitted fields `{elapsed_seconds, t0_at, t1_at, t1_path: 'coach' | 'active_player'}`; banned regexes `frame_*`, `voice_*`, `audio_*`, `recording_*`, `video_*`, `clip_id`**,
So that **no telemetry call can accidentally leak frame data, voice durations, or video metadata across the wire (privacy-by-construction per [INVARIANT 3] + PRIV-001/002).**

**Acceptance Criteria (Gherkin):**

**Given** a developer calls `logActivationEvent('activation_timer_started', {elapsed_seconds: 0, t0_at: '2026-05-07T12:00:00Z'})`
**When** the wrapper invokes Firebase Analytics
**Then** the event reaches the SDK with the payload `{elapsed_seconds: 0, t0_at: '2026-05-07T12:00:00Z'}`
**And** no warning or error is raised.

**Given** a developer calls `logActivationEvent('activation_timer_started', {elapsed_seconds: 0, frame_url: 'file:///foo.png'})`
**When** the wrapper invokes the validation step
**Then** in **dev** mode (`__DEV__ === true`), `console.warn('Banned analytics field: frame_url')` is logged AND the call still reaches Firebase Analytics with the full payload (warns but proceeds — non-blocking in dev for fast iteration)
**And** in **test** mode (`process.env.NODE_ENV === 'test'`), the call THROWS an error preventing the test from passing
**And** in **production** mode, the call THROWS preventing the SDK call.

**Given** the wrapper is called with an unknown event name (not in `'activation_timer_started' | 'activation_timer_completed'`)
**When** the type system is consulted
**Then** TypeScript rejects the call at compile time (the wrapper's type signature constrains event names).

**Tests:** New jest test at `apps/mobile/src/shared/services/__tests__/analytics.test.ts`:
- Test: permitted payload reaches SDK unchanged.
- Test: banned key throws in test mode.
- Test: banned key warns in dev mode (mocked `__DEV__`).
- Test: banned key throws in prod mode.
- Test: each banned regex (`frame_*`, `voice_*`, `audio_*`, `recording_*`, `video_*`, `clip_id`) is rejected.

**Dependencies:** Story 2.1 (the gate is signaling-tier; wrapper is the runtime tier — both reinforce the same contract at different layers).

**Sprint fit:** fits-in-one-sprint.

### Story 2.3: T0 Emission in authService.ts on Auth-State-Change → Paid

As **Coach Thomas** (or **Active Player Maxime**),
I want **the activation timer to start (T0 fires) the moment my mobile sign-in confirms an active subscription**,
So that **the < 5min activation budget begins counting from the J1-defined moment (mobile auth-state-change → `paid`), not from app launch or pre-checkout funnel.**

**Acceptance Criteria (Gherkin):**

**Given** a user signs in successfully via email/password or Google
**And** `subscriptionService.checkSubscription` returns `status: 'active'` (or `trialing` with `current_period_end > now`)
**When** `mapFirebaseUser` in `authService.ts` updates `useAuthStore.user.isPaid = true`
**Then** the wrapper `logActivationEvent('activation_timer_started', { elapsed_seconds: 0, t0_at: <ISO8601 now> })` is invoked
**And** the T0 timestamp is persisted to MMKV at `auth.t0_at` for later T1 elapsed-seconds calculation.

**Given** a user signs in but is in `lapsed` or `signed-out` state (no `paid`)
**When** the auth-state-change fires
**Then** T0 is NOT emitted (the activation chain only starts for paid users per PRD §2 — no-free-tier).

**Given** a user is already signed in (T0 previously emitted; `auth.t0_at` exists in MMKV)
**When** the user re-opens the app
**Then** T0 is NOT re-emitted (one T0 per session-from-signed-out-state).

**Tests:** New jest test at `apps/mobile/src/features/auth/__tests__/authService.test.ts` (extension):
- Test: T0 emits on first auth-state-change → paid.
- Test: T0 does not emit on auth-state-change → lapsed.
- Test: T0 does not re-emit on subsequent auth-state-change → paid within same session.

**Dependencies:** Story 2.2 (wrapper); Story 1.6 (authService.ts migrated to RN Firebase auth).

**Sprint fit:** fits-in-one-sprint.

### Story 2.4: T1-Coach Emission in exportPipeline.ts on Confirmed-Dispatch

As **Coach Thomas**,
I want **the activation timer to complete (T1 fires) the moment the OS share-sheet confirms dispatch of my exported clip — NOT when the share-sheet opens**,
So that **the J1 activation moment is bound to the artifact-actually-shipped event (Discord receives the clip), not to the user's intention to share.**

**Acceptance Criteria (Gherkin):**

**Given** a coach has exported a clip (encode complete; OS share-sheet open)
**And** the user confirms the share target (e.g., taps "Discord" and sends)
**When** `expo-sharing` resolves with success
**Then** the wrapper `logActivationEvent('activation_timer_completed', { elapsed_seconds: <T1-T0>, t1_at: <ISO8601 now>, t1_path: 'coach' })` is invoked
**And** the MMKV flag `auth.t1_emitted = true` prevents subsequent T1 emissions in the same session (per PRD §2 dual-T1 mutually exclusive).

**Given** a coach opens the share-sheet but cancels (taps outside the sheet, presses back)
**When** `expo-sharing` resolves with cancellation
**Then** T1 is NOT emitted (only confirmed-dispatch counts per PRD §2).

**Given** a session in which `auth.t1_emitted === true` (either coach or active-player path already fired)
**When** the coach exports another clip and shares again
**Then** T1 is NOT re-emitted (one T1 per session).

**Tests:** New jest test at `apps/mobile/src/features/clip-export/__tests__/exportPipeline.test.ts`:
- Test: T1-coach emits on `expo-sharing` resolved-success.
- Test: T1-coach does not emit on cancellation.
- Test: T1-coach does not re-emit if `auth.t1_emitted === true`.

**Dependencies:** Story 2.2 (wrapper); Story 2.3 (T0 emit must precede T1 in time; the elapsed-seconds calculation uses the persisted `auth.t0_at`).

**Sprint fit:** fits-in-one-sprint.

### Story 2.5: T1-Active-Player Emission in CinemaModeScreen.tsx on First View-Mode Toggle

As **Active Player Maxime**,
I want **the activation timer to complete (T1 fires) the moment I toggle Cinema Mode view-mode for the first time in my session — even if I never export**,
So that **PRD's J4 dual-T1 instrumentation distinguishes the active-player solo path from the coach path; the < 5min activation budget applies to me too, but bound to engagement, not artifact production.**

**Acceptance Criteria (Gherkin):**

**Given** an active-player has opened Cinema Mode on a round
**And** has not yet exported any clip in this session (`auth.t1_emitted === false`)
**When** they toggle the view-mode for the first time (Full → Minimap, Full → Minimap+HUD, Minimap → Minimap+HUD, etc.)
**Then** the wrapper `logActivationEvent('activation_timer_completed', { elapsed_seconds: <T1-T0>, t1_at: <ISO8601 now>, t1_path: 'active_player' })` is invoked
**And** `auth.t1_emitted = true` is persisted to MMKV.

**Given** a coach has already triggered T1-coach in this session (`auth.t1_emitted === true`)
**When** the user later toggles view-mode in Cinema Mode
**Then** T1-active-player is NOT emitted (per PRD §2 dual-T1 mutually exclusive — first-fire wins).

**Given** an active-player toggles view-mode multiple times in the same session
**When** the second and subsequent toggles fire
**Then** only the FIRST toggle emits T1-active-player; subsequent toggles do not re-emit.

**Tests:** New jest test at `apps/mobile/src/features/video-playback/__tests__/CinemaModeScreen.test.tsx`:
- Test: T1-active-player emits on first view-mode toggle (when `auth.t1_emitted === false`).
- Test: T1-active-player does not emit if T1-coach previously fired.
- Test: T1-active-player does not re-emit on subsequent toggles.

**Dependencies:** Story 2.2 (wrapper); Story 2.3 (T0 + elapsed calculation); cross-epic depends on Epic 5 Story 5.5 (view-mode toggle UI exists; this story wires the telemetry hook into it).

**Sprint fit:** fits-in-one-sprint.

### Story 2.6: EXPO_PUBLIC_AUTH_BYPASS Deny in Release Configs ([INVARIANT 8])

As **Stephane**,
I want **the Reader-App gate (Story 2.1) extended to scan release-config files for `EXPO_PUBLIC_AUTH_BYPASS=true` and fail CI if found**,
So that **dev-mode bypass cannot accidentally ship in a release build (the bypass injects a fake `{uid: 'dev-bypass-user', isPaid: true}` and skips Firebase auth entirely — catastrophic if shipped).**

**Acceptance Criteria (checklist):**

- [ ] `apps/mobile/scripts/reader-app-gate.sh` extends to scan: `apps/mobile/.env.production`, `apps/mobile/eas.json` (release profiles only — not dev/preview), and any `app.config.js`/`app.json` `extra` fields.
- [ ] Banned pattern: `EXPO_PUBLIC_AUTH_BYPASS\s*=\s*['"]?true['"]?` (case-sensitive; matches both `=true` and `="true"`).
- [ ] If pattern is found in any release config, gate fails CI with the matched line + path.
- [ ] `apps/mobile/RELEASE.md` updated: section "Release-build verification" documents that this scan runs as part of the gate.

**Tests:** Extension to Story 2.1 test fixtures: `apps/mobile/scripts/__tests__/reader-app-gate-fixtures/release-config-bypass.json` triggers a gate failure.

**Dependencies:** Story 2.1.

**Sprint fit:** fits-in-one-sprint.

---

## Epic 3: Six-State Entitlement — State Machine, UI Banners & Lapsed Screen

**Goal:** All six entitlement states (`paid` / `lapsed` / `offline-grace ≤30d` / `payment-failed` / `multi-device` / `signed-out`) are derived by a pure function; mobile + web UI surfaces reflect each state with the locked treatment from UX §2.5.

### Story 3.1: deriveEntitlementState Pure Function + 6-State Regression Tests (AR-11)

As **Stephane**,
I want **`apps/mobile/src/features/auth/subscriptionService.ts:deriveEntitlementState(userDoc, cacheMeta)` implemented as a pure function returning one of six string literals**,
So that **the entitlement state machine has a single source of truth, every state has a unit test, and the state derivation is testable in isolation from React + Firebase.**

**Acceptance Criteria (Gherkin per state):**

**Given** `userDoc.status === 'active' || 'trialing'` AND `userDoc.current_period_end > now`
**When** `deriveEntitlementState(userDoc, cacheMeta)` is invoked
**Then** the function returns `'paid'`.

**Given** `userDoc.status === 'canceled'` OR `userDoc.current_period_end < now`
**When** `deriveEntitlementState(userDoc, cacheMeta)` is invoked
**Then** the function returns `'lapsed'`.

**Given** `userDoc` is null/undefined (Firestore read failed) AND `cacheMeta.isPaid === true` AND `cacheMeta.cachedAt > now - 30 days`
**When** `deriveEntitlementState(userDoc, cacheMeta)` is invoked
**Then** the function returns `'offline-grace ≤30d'`.

**Given** `userDoc` is null/undefined AND `cacheMeta.cachedAt < now - 30 days` (or no cache exists)
**When** `deriveEntitlementState(userDoc, cacheMeta)` is invoked
**Then** the function returns `'signed-out'` (force re-auth on next foreground).

**Given** `userDoc.status === 'past_due'` AND time-since-status-flipped-to-past_due `< paymentFailedGracePeriodMs (default 7 days)`
**When** `deriveEntitlementState(userDoc, cacheMeta)` is invoked
**Then** the function returns `'payment-failed'`.

**Given** `userDoc.status === 'past_due'` AND time-since-status-flipped-to-past_due `≥ paymentFailedGracePeriodMs`
**When** `deriveEntitlementState(userDoc, cacheMeta)` is invoked
**Then** the function returns `'lapsed'`.

**Given** the same `users/{uid}` is observed across multiple device installations (multi-device case)
**When** `deriveEntitlementState(userDoc, cacheMeta)` is invoked on either device
**Then** the function returns `'paid'` if entitlement is paid (multi-device is NOT enforced per PRD; entitlement is per-user, not per-device).

**Given** no auth token is present (`userDoc` argument is the sentinel `null` AND `cacheMeta.isAuthenticated === false`)
**When** `deriveEntitlementState(userDoc, cacheMeta)` is invoked
**Then** the function returns `'signed-out'`.

**Tests:** New jest test file at `apps/mobile/src/features/auth/__tests__/deriveEntitlementState.test.ts` (scaffolded in Story 1.7; filled here):
- One `describe` block per state, with the Gherkin scenarios above as `it()` cases.
- Edge cases: `userDoc.current_period_end` exactly at `now`; `cacheMeta.cachedAt` exactly at the 30-day boundary; `paymentFailedGracePeriodMs` env override path.

**Dependencies:** Story 1.7 (subscriptionService.ts migrated; test scaffold exists).

**Sprint fit:** fits-in-one-sprint.

### Story 3.2: EntitlementBanner.tsx for Payment-Failed (UX-DR1, mobile-AUTH-006)

As **Coach Thomas**,
I want **a banner at the top of the home screen when my subscription is in `payment-failed` state, with copy "Mise à jour du moyen de paiement nécessaire" and a CTA "Mettre à jour" that deep-links to Stripe Customer Portal**,
So that **I can recover from a card-decline within 7 days of grace without losing access to the app mid-review-session (J7 happy path).**

**Acceptance Criteria (Gherkin):**

**Given** a coach signs in successfully
**And** `deriveEntitlementState` returns `'payment-failed'`
**When** the home screen renders
**Then** `<EntitlementBanner state="payment-failed" />` displays with:
- Background: warning amber (per UX §2.5 token spec)
- Icon: `AlertTriangle` (or equivalent shape — A11Y-006: shape primary, color secondary)
- Body: "Mise à jour du moyen de paiement nécessaire"
- CTA: "Mettre à jour" (button) opening Customer Portal via `Linking.openURL(<portal-deep-link-from-subscriptionService>)`.

**Given** the banner is displayed
**When** the user taps the CTA and returns to the app
**Then** the home screen re-fetches `users/{uid}` (foreground re-fetch per `mobile-AUTH-002`)
**And** if `status === 'active'` post-update, the banner clears
**And** if still `past_due`, the banner remains.

**Given** the user is in any state other than `'payment-failed'`
**When** the home screen renders
**Then** `<EntitlementBanner />` does NOT render (or returns null).

**Tests:** New jest test at `apps/mobile/src/features/auth/__tests__/EntitlementBanner.test.tsx`:
- Test: renders for `payment-failed` state with locked French copy.
- Test: does not render for any other state.
- Test: CTA tap calls `Linking.openURL`.

**Dependencies:** Story 3.1 (deriveEntitlementState).

**Sprint fit:** fits-in-one-sprint.

### Story 3.3: SubscriptionRequiredScreen.tsx for Lapsed (UX-DR2, mobile-AUTH-003)

As **Coach Thomas** (post-cancellation, J8) or any user whose subscription has lapsed,
I want **a full-screen state showing "Abonnement requis" with copy explaining the situation and a CTA "Reprendre mon abonnement" that deep-links to Stripe Customer Portal**,
So that **lapsed-state UI is unambiguous, my session data is preserved (per `mobile-AUTH-005`), and I can resubscribe without re-installing.**

**Acceptance Criteria (Gherkin):**

**Given** a user signs in
**And** `deriveEntitlementState` returns `'lapsed'`
**When** post-sign-in navigation runs
**Then** `<SubscriptionRequiredScreen />` is rendered (NOT the home screen) with:
- Title: "Abonnement requis" (LOCKED per UX FU-4)
- Body: explanation copy from UX §4.1 (locked French copy)
- CTA primary: "Reprendre mon abonnement" → opens Customer Portal via `Linking.openURL`
- CTA secondary: "Se déconnecter" → clears auth + returns to LoginScreen.

**Given** `<SubscriptionRequiredScreen />` is rendered
**When** the user taps "Reprendre mon abonnement" and returns to the app
**Then** the entitlement re-fetches; if `status === 'active'` post-update, navigation to home screen proceeds (per `mobile-AUTH-002` foreground re-fetch + Story 3.1 derivation).

**Given** session data exists in SQLite + MMKV from before the lapse
**When** `<SubscriptionRequiredScreen />` is displayed
**Then** the data is preserved (NOT deleted) per `mobile-AUTH-005` — restorable on resubscribe.

**Tests:** New jest test at `apps/mobile/src/features/auth/__tests__/SubscriptionRequiredScreen.test.tsx`:
- Test: renders for `lapsed` state with locked French copy "Abonnement requis".
- Test: CTA "Reprendre mon abonnement" opens Customer Portal.
- Test: CTA "Se déconnecter" calls `signOut`.
- Test: SQLite + MMKV data is NOT cleared on lapsed-state render (preservation contract).

**Dependencies:** Story 3.1.

**Sprint fit:** fits-in-one-sprint.

### Story 3.4: OfflineIndicator for Offline-Grace (UX-DR3, mobile-AUTH-004 visual)

As **Coach Thomas on the J9 train**,
I want **a small visual signal in the home screen header when I'm in `offline-grace ≤30d` state**,
So that **I'm aware the entitlement is locally-validated (cached), can still review and export clips, and won't be surprised on day 31 when re-auth is forced.**

**Acceptance Criteria (Gherkin):**

**Given** the user signs in
**And** `deriveEntitlementState` returns `'offline-grace ≤30d'`
**When** the home screen renders
**Then** an offline indicator appears in the header (small badge or icon — composition is up to UX/dev; can live inline in HomeScreen if not extracted)
- Tooltip / accessible label: "Mode hors-ligne — entitlement en cache local"
- The app remains fully usable (Card View, Cinema Mode, view-mode toggle, clip creation, voice recording, OS share-sheet).

**Given** the cache age approaches the 30-day boundary (e.g., cachedAt was 28 days ago)
**When** the indicator renders
**Then** the indicator copy may include the cache age (e.g., "Cache: 28 j") — UX choice; not strictly required.

**Given** the user transitions from `offline-grace ≤30d` to `paid` (back online; Firestore read succeeds)
**When** `deriveEntitlementState` re-runs on foreground
**Then** the indicator clears.

**Tests:** New jest test at `apps/mobile/src/features/auth/__tests__/OfflineIndicator.test.tsx` (or inline in `HomeScreen.test.tsx` if not extracted).

**Dependencies:** Story 3.1.

**Sprint fit:** fits-in-one-sprint.

### Story 3.5: PaymentWarning.tsx Web Composition (UX-DR8, web-DASHBOARD-002)

As **Coach Thomas using web dashboard**,
I want **a warning banner on `/dashboard` when my subscription is `past_due`, with an "Update payment method" CTA deep-linking to Stripe Customer Portal**,
So that **I can recover from a card-decline from web (mirror of mobile EntitlementBanner; J7).**

**Acceptance Criteria (Gherkin):**

**Given** a user lands on `/dashboard`
**And** `useSubscription` returns `{status: 'past_due', ...}`
**When** the dashboard renders
**Then** `<PaymentWarning />` displays at the top of the SubscriptionCard area with:
- shadcn `<Alert variant="warning">` (or equivalent)
- Body: English copy with FR-verbatim insertions where locked (per UX §4.2)
- CTA: shadcn `<Button>` "Update payment method" → POSTs to `/api/subscription/portal` → redirects to Stripe Customer Portal.

**Given** the user is in any other status
**When** `/dashboard` renders
**Then** `<PaymentWarning />` does NOT render.

**Tests:** New Vitest test at `apps/web/src/components/dashboard/PaymentWarning.test.tsx`:
- Test: renders for `past_due` status.
- Test: does not render for `active` / `canceled` / null statuses.
- Test: CTA POSTs to `/api/subscription/portal` and follows redirect.

**Dependencies:** None within Epic 3 (web SubscriptionCard already exists per legacy distillate).

**Sprint fit:** fits-in-one-sprint.

### Story 3.6: Canceling Status Badge + Resubscribe CTA (web-DASHBOARD-003)

As **Coach Thomas mid-cancellation (J8)**,
I want **`/dashboard` to display a "Canceling" status badge in amber and a "Resubscribe" CTA when my subscription is cancel-at-period-end**,
So that **I can change my mind during the period and reverse the cancellation.**

**Acceptance Criteria (Gherkin):**

**Given** the user has canceled at period-end (Stripe `cancel_at_period_end: true`; status still `active`)
**And** `useSubscription` returns the `cancel_at_period_end` flag
**When** the dashboard renders
**Then** the SubscriptionCard status badge shows "Canceling" in amber (text + color per A11Y-003 "not color-only")
**And** a "Resubscribe" CTA is displayed → POSTs to `/api/subscription/portal` → Customer Portal handles re-activation.

**Given** the period-end has arrived (Stripe `customer.subscription.deleted` fires; status flips to `canceled`)
**When** the dashboard renders
**Then** the badge displays "Canceled" (lapsed state UI; sees EmptySubscription per Story 4.6).

**Tests:** Updated Vitest test at `apps/web/src/components/dashboard/__tests__/SubscriptionCard.test.tsx`:
- Test: "Canceling" badge + "Resubscribe" CTA when `cancel_at_period_end === true`.
- Test: "Canceled" UI when status is `canceled`.

**Dependencies:** None (legacy SubscriptionCard already exists; this story extends it).

**Sprint fit:** fits-in-one-sprint.

### Story 3.7: Mobile Login (mobile-AUTH-001) Entitlement Gate

As **Coach Thomas / Active Player Maxime / Passive→Active Lucas**,
I want **the mobile LoginScreen to accept Google or email/password credentials issued via the web Stripe flow**,
So that **I can sign in to the mobile app with the same credentials I used on web (and resubscribe via web if needed; J1 + J6 happy paths).**

**Acceptance Criteria (Gherkin):**

**Given** a user has registered on web (via `/auth/sign-in` or `/pricing` auth modal)
**And** has completed Stripe Checkout with subscription status `active`
**When** the user opens the mobile app
**Then** the LoginScreen renders with:
- Title: locked FR copy from UX §4.1
- Email + password inputs
- "Se connecter" button
- "Continuer avec Google" button (via `@react-native-google-signin/google-signin` v14)
- "Mot de passe oublié" link (deep-links to web `/auth/sign-in?passwordReset=1` per FU-5).

**Given** the user enters valid credentials
**When** they tap "Se connecter"
**Then** `auth().signInWithEmailAndPassword(email, password)` is called
**And** on success, `mapFirebaseUser` runs `subscriptionService.checkSubscription`
**And** `deriveEntitlementState` returns `'paid'` → navigate to home screen
**And** T0 telemetry fires (via Story 2.3 wiring).

**Given** the user enters invalid credentials
**When** they tap "Se connecter"
**Then** Firebase Auth error is caught
**And** `formatAuthError(firebaseError)` returns a friendly French message ("Identifiants incorrects" or similar from UX §4.1)
**And** the message displays as an inline error on LoginScreen.

**Given** Google sign-in succeeds and entitlement is non-paid (lapsed / signed-out)
**When** post-sign-in navigation runs
**Then** `<SubscriptionRequiredScreen />` (Story 3.3) renders instead of home screen.

**Tests:** Updated jest tests at `apps/mobile/src/features/auth/__tests__/LoginScreen.test.tsx`:
- Test: email/password sign-in success → home navigation.
- Test: email/password sign-in failure → friendly French error.
- Test: Google sign-in success → home navigation (paid) or SubscriptionRequiredScreen (lapsed).
- Test: "Mot de passe oublié" link opens web `/auth/sign-in?passwordReset=1`.

**Dependencies:** Stories 1.5/1.6 (RN auth migration); Story 3.3 (SubscriptionRequiredScreen).

**Sprint fit:** fits-in-one-sprint.

### Story 3.8: Mobile Foreground Re-Fetch After Stripe Customer Portal Round-Trip (mobile-AUTH-002)

As **Coach Thomas after updating my payment method on Stripe Customer Portal**,
I want **the mobile app to re-fetch `users/{uid}` immediately when I return to the app**,
So that **the EntitlementBanner clears (or the app navigates from SubscriptionRequiredScreen to home) within seconds — not at the next 60-min periodic re-validation cycle.**

**Acceptance Criteria (Gherkin):**

**Given** the app is foregrounded (via `AppState` listener in `App.tsx`)
**When** the user returns from Customer Portal (or any external app)
**Then** `subscriptionService.checkSubscription(useAuthStore.user.uid)` is invoked immediately
**And** `useAuthStore` is updated with the fresh `userDoc`
**And** `deriveEntitlementState` re-runs.

**Given** the entitlement state changed (e.g., `payment-failed → paid` post-payment-update)
**When** `deriveEntitlementState` returns the new state
**Then** the affected UI re-renders (banner clears; SubscriptionRequiredScreen → home transition; etc.).

**Tests:** New jest test at `apps/mobile/__tests__/App.test.tsx` (or `apps/mobile/src/app/__tests__/RootNavigator.test.tsx`): mocks `AppState` listener; asserts `subscriptionService.checkSubscription` is called on foreground transition.

**Dependencies:** Stories 1.7 (subscriptionService.ts migrated); 3.1 (deriveEntitlementState).

**Sprint fit:** fits-in-one-sprint.

### Story 3.9: 30-Day MMKV-Cached Entitlement + Day-31 Expiry (mobile-AUTH-004)

As **Coach Thomas on the J9 train (no Wi-Fi, spotty cellular)**,
I want **the app fully usable while disconnected for up to 30 days post last successful Firestore read; on day 31, force re-auth on next foreground**,
So that **offline review works as a steady state (J9), and the cache cannot be exploited indefinitely (privacy + entitlement-correctness floor).**

**Acceptance Criteria (Gherkin):**

**Given** the user has successfully signed in within the last 30 days (`useAuthStore.cachedAt` within 30 days)
**And** the device is offline (Firestore read fails)
**When** the app foregrounds and `subscriptionService.checkSubscription` runs
**Then** the read failure is caught
**And** `deriveEntitlementState(null, cacheMeta)` returns `'offline-grace ≤30d'`
**And** the app remains fully usable.

**Given** `useAuthStore.cachedAt < now - 30 days`
**When** the app foregrounds
**Then** `deriveEntitlementState(null, cacheMeta)` returns `'signed-out'`
**And** the user is redirected to LoginScreen for re-auth (forced re-auth on next foreground).

**Given** `useAuthStore.cachedAt < now - 30 days` AND the device IS online
**When** the app foregrounds and Firestore read succeeds
**Then** the cache refreshes (`cachedAt = now`); user remains signed in.

**Tests:** Updated jest test at `apps/mobile/src/features/auth/__tests__/deriveEntitlementState.test.ts`: edge cases at the 30-day boundary (cachedAt = exactly 30 days; cachedAt = 30 days + 1 millisecond).

**Dependencies:** Story 3.1.

**Sprint fit:** fits-in-one-sprint.

### Story 3.10: Session-Data Preservation Across Lapse → Resubscribe (mobile-AUTH-005)

As **Coach Thomas resubscribing 3 weeks after canceling (J8)**,
I want **my SQLite + MMKV session data (clips, voice annotations, view-mode preferences, in-progress recording state) preserved across the lapsed → paid transition**,
So that **resubscribing restores my exact state and I can resume reviewing without re-importing.**

**Acceptance Criteria (Gherkin):**

**Given** the user is in `lapsed` state (post-cancellation period-end)
**And** SQLite contains `sessions`, `map_segments`, `clip_exports`, `audio_comments` rows from before the lapse
**And** MMKV contains `auth.user`, `auth.cachedAt`, `prefs.viewMode`, `prefs.minimapHud`, `processing.<sessionId>.*` checkpoints
**When** `<SubscriptionRequiredScreen />` is displayed
**Then** NONE of the SQLite or MMKV data is cleared.

**Given** the user resubscribes via Customer Portal
**And** webhook fires; mobile foreground re-fetch returns `paid`
**When** the app navigates from SubscriptionRequiredScreen to home screen
**Then** the home screen renders with the prior session list intact (Card View shows past sessions; Cinema Mode resumes if `useSessionStore.currentSessionId` was set).

**Given** the user signs out explicitly (CTA "Se déconnecter" on SubscriptionRequiredScreen or via account bottom-sheet)
**When** the sign-out runs
**Then** `useAuthStore` clears (auth + cachedAt); but session data (SQLite + `prefs.*` MMKV) is NOT cleared (a future re-sign-in with the same `uid` restores access).

**Tests:** New jest test at `apps/mobile/__tests__/lapse-resubscribe.test.ts`: simulates lapsed → resubscribe transitions; asserts session data preservation.

**Dependencies:** Stories 3.1, 3.3.

**Sprint fit:** fits-in-one-sprint.

---

## Epic 4: Web — Subscribe & Manage Funnel

**Goal:** The Discord-coupon-link → checkout → dashboard funnel works end-to-end with the FU-3 token bump, FU-5 password reset, FU-locked anti-dark-pattern cancel flow, OG card preview, and FR-verbatim insertions in English copy.

### Story 4.1: Web Token Bump #FF6B00 + Accent-Hover #FF8533 + A11Y-001 Contrast Re-Verify (UX-DR16, FU-3)

As **Stephane**,
I want **the web accent token bumped from `#E8731A` to `#FF6B00` and accent-hover from `#F28A2E` to `#FF8533` in `apps/web/src/app/globals.css` and `apps/web/tailwind.config.ts`, with A11Y-001 contrast re-verified across all surfaces**,
So that **the cross-surface accent reconciliation per FU-3 is locked at `#FF6B00` (mobile + web both anchor here) and the OG image asset (Story 4.2) renders against a consistent brand color.**

**Acceptance Criteria (checklist):**

- [ ] `apps/web/src/app/globals.css`: `--accent: #FF6B00;` (replacing `#E8731A`); `--accent-hover: #FF8533;` (replacing `#F28A2E`).
- [ ] `apps/web/tailwind.config.ts`: same bumps in the theme `colors.accent` config.
- [ ] Browser DevTools contrast check on key surfaces: orange-on-dark-bg, orange-on-card, button-default, button-hover. Each surface's contrast ratio recorded in `_bmad-output/web-contrast-audit-2026-XX-XX.md` (or appended to V1 launch readiness checklist in Epic 10).
- [ ] All checked ratios meet WCAG AA (text-primary ~16:1, text-secondary ~5.5:1, orange ~4.8:1 — values from PRD A11Y-001).
- [ ] If any ratio falls below AA: token NOT bumped to that value; alternative shade picked (e.g., `#E2630B` or `#F26A00`); FU-3 reconciliation re-opened.
- [ ] No regression: `pnpm --filter web build` succeeds; `npx lighthouse` accessibility score remains ≥ baseline.

**Tests:** Manual contrast verification (DevTools + manual ratio calc). No automated tests.

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

### Story 4.2: OG Image Asset + Layout Meta (UX-DR13 + UX-DR14, web-LANDING-002)

As **Coach Thomas seeing the Discord card preview when a coupon link is shared**,
I want **the Discord (and Twitter, etc.) preview to show a 1200×630 OG image with the FR-locked hero tagline overlaid on a #FF6B00 accent background, and accurate meta (title, description, og:image, twitter:card)**,
So that **the J5 distribution moat is reinforced — the Discord preview is itself a brand surface; passive players (Lucas) see Warden every time a clip's coupon link is shared.**

**Acceptance Criteria (checklist):**

- [ ] `apps/web/public/og/landing.jpg` created: 1200×630, sRGB color space, file size ≤ 200 KB, uses `#FF6B00` as primary accent (per FU-3 reconciliation).
- [ ] Image content per UX §3.4 (locked composition): hero tagline "Progresser plus vite en investissant moins de temps." + Warden wordmark + minimal accent border.
- [ ] `apps/web/src/app/layout.tsx` adds Open Graph + Twitter Card meta in the root metadata export:
```ts
export const metadata = {
  title: 'Warden — Coaching companion mobile pour joueurs compétitifs',
  description: '...',
  openGraph: { images: ['/og/landing.jpg'], ... },
  twitter: { card: 'summary_large_image', images: ['/og/landing.jpg'], ... }
};
```
- [ ] Per-route overrides supported (e.g., `/pricing` page can override the OG image with a pricing-specific asset; not in V1 scope but architecture is ready).
- [ ] Discord card preview tested manually: paste `https://warden.team/` (or staging URL) into a Discord channel; preview renders with the new OG image.
- [ ] `apps/web/public/og/.gitkeep` (or the image file) committed to the repo.

**Tests:** Manual Discord preview + Twitter card validator (twitter.com/share validator). No automated tests.

**Dependencies:** Story 4.1 (token bump completed; accent color in OG image matches site).

**Sprint fit:** fits-in-one-sprint.

### Story 4.3: Footer "Get help" Link → mailto:support@warden.team (UX-DR15, OBS-003 web-side)

As **a user who needs help on the web surface**,
I want **a "Get help" link in the footer that opens a mailto draft to support@warden.team**,
So that **manual error reporting from web mirrors the mobile path (UX-DR5) and the support contact is consistent across surfaces.**

**Acceptance Criteria (Gherkin):**

**Given** any web page rendered (landing, pricing, dashboard, sign-in, etc.)
**When** the user scrolls to the footer
**Then** `<Footer />` displays a "Get help" link (English copy from UX §4.2.7)
**And** the link `href` is `mailto:support@warden.team` (LOCKED per FU-1)
**And** the link is keyboard-accessible (focusable; 2px orange focus-visible outline per A11Y-002).

**Tests:** Updated Vitest test at `apps/web/src/components/layout/__tests__/Footer.test.tsx`: asserts the "Get help" link `href` is `mailto:support@warden.team`.

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

### Story 4.4: PasswordResetForm.tsx + sign-in ?passwordReset=1 Query Handler (UX-DR11 + UX-DR12, FU-5)

As **Coach Thomas who forgot my password**,
I want **a password-reset form inside the auth modal on `/auth/sign-in` that sends a reset email via Firebase `sendPasswordResetEmail`, and a success banner on the sign-in page when I return via the reset link**,
So that **password recovery is V1-supported (FU-5) without requiring me to email support manually.**

**Acceptance Criteria (Gherkin):**

**Given** a user is on `/auth/sign-in` (or `/pricing` auth modal — same component)
**When** they tap "Forgot password?" (English copy from UX §4.2.3) (or the FR insertion equivalent on mobile deep-link return)
**Then** `<PasswordResetForm />` renders within the auth modal
- Email input
- "Send reset link" button
- Cancel / back-to-sign-in link.

**Given** the user enters a valid email
**When** they tap "Send reset link"
**Then** `firebase.auth.sendPasswordResetEmail(auth, email)` is invoked
**And** on success, a confirmation message displays: "Reset link sent. Check your email."
**And** the modal closes after 3 seconds (or on user-tap-to-dismiss).

**Given** the user enters an invalid email format
**When** they tap "Send reset link"
**Then** Zod validation rejects with an inline error.

**Given** the user clicks the reset link in their email
**And** completes the Firebase password reset flow
**And** is redirected to `/auth/sign-in?passwordReset=1`
**When** the sign-in page renders
**Then** a success banner displays: "Password reset successful. Sign in with your new password."
**And** the banner is dismissible.

**Tests:** New Vitest tests at `apps/web/src/components/auth/__tests__/PasswordResetForm.test.tsx` and `apps/web/src/app/auth/sign-in/__tests__/page.test.tsx`:
- Test: form submits with valid email; mocked `sendPasswordResetEmail` is called.
- Test: invalid email surfaces Zod error.
- Test: `?passwordReset=1` query renders success banner; banner dismisses.

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

### Story 4.5: CancelDialog.tsx — Anti-Dark-Pattern (UX-DR9, web-DASHBOARD-004)

As **Coach Thomas wanting to cancel my subscription (J8)**,
I want **a cancellation confirmation dialog that shows "access until [date]" with NO exit survey, NO guilt-trip CTA, and NO dark-pattern friction — clean confirm or cancel**,
So that **the cancellation flow respects the anti-dark-pattern policy from UX §6.3 (PRD-locked) and routes me to Stripe Customer Portal for the actual cancellation operation.**

**Acceptance Criteria (Gherkin):**

**Given** the user is on `/dashboard` with an active subscription
**When** they tap "Manage subscription" → "Cancel subscription" (in Stripe Customer Portal — but this dialog is a Warden-side pre-confirmation)
**Then** `<CancelDialog />` renders with:
- shadcn `<Dialog>` modal
- Title: "Cancel subscription?" (English copy from UX §4.2)
- Body: "You'll have access until [date]" — `[date]` = `current_period_end` formatted via `Intl.DateTimeFormat`
- CTA primary: "Continue to Stripe" → POSTs to `/api/subscription/portal` → redirects to Customer Portal
- CTA secondary: "Keep subscription" → closes the dialog
- **NO exit survey** (no "Why are you canceling?" form)
- **NO guilt-trip CTA** (no "Wait, here's a discount" or "Are you SURE you want to lose all your saved sessions?")
- **NO fake urgency** (no countdown timers, no "Limited time" copy).

**Given** the user taps "Continue to Stripe"
**When** the redirect to Customer Portal completes
**Then** the actual cancellation operation happens at Stripe (Stripe sets `cancel_at_period_end: true`)
**And** webhook fires → `users/{uid}` updates → dashboard re-renders with "Canceling" badge (Story 3.6).

**Given** the user taps "Keep subscription"
**When** the dialog closes
**Then** no cancellation occurs; subscription remains active.

**Tests:** New Vitest test at `apps/web/src/components/dashboard/__tests__/CancelDialog.test.tsx`:
- Test: dialog renders with locked English copy.
- Test: "Continue to Stripe" CTA POSTs to `/api/subscription/portal`.
- Test: "Keep subscription" closes dialog.
- Test: NO exit-survey form fields are present in the dialog DOM.
- Test: NO discount-offer or guilt-trip text matches anti-pattern keyword list (e.g., "discount", "wait", "are you sure").

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

### Story 4.6: EmptySubscription.tsx (UX-DR10, web-DASHBOARD-005)

As **a signed-in user without an active subscription (post-cancellation period-end OR never-subscribed-but-signed-in)**,
I want **`/dashboard` to render an empty-state component with a clear path to `/pricing`**,
So that **I'm not staring at a blank page and the resubscribe / first-subscription path is unambiguous.**

**Acceptance Criteria (Gherkin):**

**Given** the user is signed in
**And** `useSubscription` returns `null` (no `users/{uid}` doc) OR `{status: 'canceled', ...}`
**When** `/dashboard` renders
**Then** `<EmptySubscription />` displays with:
- shadcn `<Card>` centered
- Title: "No active subscription" (English copy from UX §4.2)
- Body: short explanation
- CTA: shadcn `<Button>` "View plans" → `<Link href="/pricing">`.

**Given** the user is signed in with `status === 'active'`
**When** `/dashboard` renders
**Then** `<EmptySubscription />` does NOT render; SubscriptionCard renders normally.

**Tests:** New Vitest test at `apps/web/src/components/dashboard/__tests__/EmptySubscription.test.tsx`:
- Test: renders for null subscription.
- Test: renders for canceled subscription.
- Test: does not render for active subscription.
- Test: CTA navigates to `/pricing`.

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

### Story 4.7: Web English Copy with FR-Verbatim Insertions Embedded Inline (UX-DR18, I18N-002)

As **Coach Thomas / Active Player Maxime browsing the web surface**,
I want **English UI throughout EXCEPT the FR-locked hero tagline ("Progresser plus vite en investissant moins de temps."), deferred-billing copy ("Vous ne serez pas débité avant le [date]"), and savings copy ("économisez 2 mois") preserved verbatim in French**,
So that **the FR-verbatim insertions remain the marketing brand voice while the rest of the web surface reaches an English-language audience (full FR localization is V3).**

**Acceptance Criteria (Gherkin):**

**Given** any web page rendered
**When** the user inspects the rendered text
**Then** all UI copy matches UX §4.2 (English) embedded inline as JSX strings (no i18n bundle for V1 per UX §6.5)
**And** the three FR-verbatim insertions are present:
- Hero on `/`: "Progresser plus vite en investissant moins de temps." (LOCKED)
- Deferred-billing on `/pricing` and `/checkout/*`: "Vous ne serez pas débité avant le [date]" (LOCKED)
- Savings copy on `/pricing` plan card: "économisez 2 mois" (LOCKED).

**Given** an internationalization scan
**When** searching for these three exact strings in `apps/web/src/`
**Then** each string appears exactly once (or as many times as required by render context — e.g., hero may appear once on landing + once in OG meta).

**Tests:** New Vitest snapshot test at `apps/web/src/__tests__/copy-verbatim-fr.test.tsx`: renders landing + pricing + checkout flows; asserts the three verbatim FR insertions appear as locked.

**Dependencies:** Story 4.1 (token bump) — if any copy is rendered against the bumped accent and contrast fails, copy may need adjustment (unlikely but possible).

**Sprint fit:** fits-in-one-sprint.

### Story 4.8: Web Funnel Analytics Events (web-ANALYTICS-001)

As **Stephane**,
I want **Firebase Analytics events emitted for the funnel stages: Visit, CheckoutStart, CheckoutComplete, Coupon-applied, Coupon-Retained-past-deferred-billing**,
So that **the WoM-driven Discord-distribution flow is measurable and the Coupon → Retained ≥ 10% target (PRD §2) is verifiable.**

**Acceptance Criteria (Gherkin):**

**Given** a user lands on `/`
**When** the page renders post-cookie-consent (per legacy Web Story 1.3 CookieBanner)
**Then** `firebaseAnalytics.logEvent('Visit', { route: '/' })` is called.

**Given** a user lands on `/pricing` and clicks a plan card CTA
**When** the auth modal opens (or proceeds directly to Stripe Checkout if signed in)
**Then** `firebaseAnalytics.logEvent('CheckoutStart', { plan: '<monthly|yearly>', coupon_applied: <bool> })` is called.

**Given** a user returns from Stripe Checkout to `/dashboard?success=1`
**When** the dashboard renders the success state
**Then** `firebaseAnalytics.logEvent('CheckoutComplete', { plan: '<monthly|yearly>' })` is called.

**Given** a coupon URL param is present on `/pricing` (e.g., `/pricing?coupon=DISCORD2026`)
**When** the page renders and the coupon validates against Stripe
**Then** `firebaseAnalytics.logEvent('Coupon-applied', { coupon_id: '<id>' })` is called.

**Given** a user has redeemed a coupon AND remained subscribed past the deferred-billing date (Stripe `invoice.paid` fires post-trial-end)
**When** the webhook handler processes the `invoice.paid` event
**Then** server-side log emits `firebaseAnalytics.logEvent('Coupon-Retained-past-deferred-billing', { coupon_id: '<id>', uid: '<firebase_uid>' })` (via the firebase-admin Analytics path; or a server-emitted custom event sink).

**Tests:** New Vitest tests at `apps/web/src/components/checkout/__tests__/PlanCta.test.tsx` (Visit + CheckoutStart events) and `apps/web/src/lib/stripe/__tests__/webhooks.test.ts` (Coupon-Retained event extension).

**Dependencies:** Story 1.12 (webhook handler trialing extension — coupon-retained calc depends on `invoice.paid` post-trial path).

**Sprint fit:** fits-in-one-sprint.

---

## Epic 5: Mobile — Card View, Cinema Mode & Manual Clip from Timeline

**Goal:** After Card View opens with auto-sliced rounds (or manual-clip-from-timeline if AR-SPIKE returned rung-3), the coach navigates Cards, opens Cinema Mode, toggles view-mode under 100 ms, navigates rounds explicitly. Active-Player T1 fires on first toggle.

### Story 5.1: CardViewScreen with Adaptive Grid + Sort Persistence (mobile-CARD-001/002/004)

As **Coach Thomas after auto-slice completes**,
I want **a Card View grid with adaptive column count (2 columns on small phones, 3 on larger), sort options (temporal default, orange biggest win, blue biggest win, closest map), and a cold-start state offering "Resume last review" or "Import new session" — never blank**,
So that **I can triage rounds quickly and the cold-start UX is unambiguous.**

**Acceptance Criteria (Gherkin):**

**Given** the user has imported a session and auto-slice completed
**When** they navigate to Card View
**Then** all auto-sliced rounds render as Cards in a grid
**And** the column count adapts: 2 columns at width ≤ 400 dp; 3 columns at width > 400 dp.

**Given** the user taps a sort option (temporal / orange win / blue win / closest map)
**When** the sort applies
**Then** the Cards re-order
**And** the choice is persisted in MMKV `prefs.sortOrder`
**And** on app restart, the persisted sort is the default.

**Given** the user has no active session OR the most recent session is empty
**When** Card View renders
**Then** the cold-start state displays:
- "Reprendre la dernière revue" (if `useSessionStore.currentSessionId` exists)
- "Importer une nouvelle session" (always)
- NEVER a blank screen.

**Given** score-based sorts (orange biggest win, blue biggest win) are selected
**When** sorting runs
**Then** sort gracefully degrades to temporal until OCR ships in V2 (cards rendered in temporal order with a small notice "Score-based sort awaiting OCR support").

**Tests:** New jest tests at `apps/mobile/src/features/session/__tests__/CardViewScreen.test.tsx`:
- Test: adaptive column count by width.
- Test: sort persistence via MMKV.
- Test: cold-start state when session list is empty.
- Test: score-based sort graceful degradation.

**Dependencies:** Epic 0 Story 0.2 (Sprint 2.5 detector replacement Story 7.5 in mobile-AUTO-SLICE-* lands — Card View consumes detector output); Epic 1 spike outcome (rung-1/2: Card View auto-populates; rung-3: Card View shows manual-clip-from-timeline path only).

**Sprint fit:** fits-in-one-sprint.

### Story 5.2: Card → Cinema Mode Tap Navigation (mobile-CARD-003)

As **Coach Thomas browsing Card View**,
I want **tapping a Card to open Cinema Mode for that round**,
So that **the review flow is one-tap from triage to immersive review.**

**Acceptance Criteria (Gherkin):**

**Given** the user is on Card View with auto-sliced rounds
**When** they tap a Card
**Then** Cinema Mode opens at the round's start timestamp
**And** the round's `map_name` is loaded (or defaults to Full view if `unknown`)
**And** Cinema Mode cold-start completes within PERF-004 budget (≤ 1.5 s).

**Tests:** New jest test at `apps/mobile/src/features/session/__tests__/CardViewScreen.test.tsx`: tap a Card; assert navigation to CinemaModeScreen with correct round ID.

**Dependencies:** Story 5.1; Story 5.4 (CinemaModeScreen).

**Sprint fit:** fits-in-one-sprint.

### Story 5.3: Cards/Timeline Top-Bar Toggle + Manual Clip from Timeline (UX-DR7, mobile-CARD-005, Decision #UX-14)

As **Coach Thomas on a session with auto-slice-missed rounds (or after AR-SPIKE rung-3 with manual-clip-only V1)**,
I want **a top-bar Cards/Timeline view-mode toggle in CardViewScreen that lets me switch between Card grid and a continuous Timeline view, where I can manually create clips from any point not auto-sliced**,
So that **auto-slice-missed rounds remain accessible, and the manual-clip-from-timeline path is first-class V1 navigation per UX Decision #UX-14.**

**Acceptance Criteria (Gherkin):**

**Given** the user is on CardViewScreen
**When** the top bar renders
**Then** a Cards/Timeline toggle is visible (segmented control or equivalent)
**And** "Cards" is the default selection
**And** tapping "Timeline" switches to the timeline view.

**Given** the user is in Timeline view
**When** the timeline renders
**Then** the entire imported session is shown as a scrubbable timeline
**And** auto-sliced rounds are marked as visual segments (overlay)
**And** the user can scrub to any point and tap "Créer un clip ici" (manual-clip-from-timeline)
**And** Cinema Mode opens at that timestamp.

**Given** the spike outcome was rung-3 (manual-clip-only V1; auto-slice deferred to V2)
**When** Card View renders
**Then** the Cards mode is hidden (or empty); Timeline mode is the default and only path
**And** a notice explains "Auto-slice unavailable on this device — please create clips manually from the timeline."

**Tests:** New jest tests at `apps/mobile/src/features/session/__tests__/CardViewScreen.test.tsx`:
- Test: Cards/Timeline toggle renders.
- Test: tapping Timeline switches view.
- Test: timeline displays auto-sliced segments as overlays.
- Test: "Créer un clip ici" opens Cinema Mode at the scrubbed timestamp.
- Test: rung-3 fallback path (auto-slice unavailable).

**Dependencies:** Story 5.1; Story 5.4; Epic 1 Story 1.1 (spike outcome dictates whether Cards mode populates).

**Sprint fit:** fits-in-one-sprint.

### Story 5.4: Cinema Mode Immersive Review with Reveal-on-Tap Controls (mobile-CINEMA-001)

As **Coach Thomas reviewing a round**,
I want **Cinema Mode to be an immersive video player with controls that auto-hide after inactivity and reveal on tap**,
So that **the video is the focus of attention; UI chrome is out of the way unless I need it.**

**Acceptance Criteria (Gherkin):**

**Given** the user enters Cinema Mode
**When** the screen renders
**Then** the video plays
**And** controls (play/pause, scrub bar, view-mode toggle, Next/Previous, clip CTA) are visible for 3 seconds then auto-hide.

**Given** the user taps anywhere on the screen
**When** the tap is detected
**Then** controls reveal
**And** controls re-hide after 3 seconds of inactivity.

**Given** Cinema Mode is opened from Card View
**When** the cold-start runs
**Then** first-frame visible within PERF-004 budget (≤ 1.5 s).

**Tests:** New jest tests at `apps/mobile/src/features/video-playback/__tests__/CinemaModeScreen.test.tsx`:
- Test: controls auto-hide after 3 s.
- Test: tap reveals controls.
- Test: cold-start time within budget (mocked; verified manually on device).

**Dependencies:** Epic 0 Story 0.2 (legacy Sprint 2.5 7.3 view-mode toggle UI lands); Story 1.1 spike (PERF-004 measured).

**Sprint fit:** fits-in-one-sprint.

### Story 5.5: View-Mode Toggle (Full / Minimap / Minimap+HUD) ≤100 ms — No Player Swap (mobile-CINEMA-002, PERF-003)

As **Coach Thomas in Cinema Mode**,
I want **to switch view modes among Full / Minimap / Minimap+HUD via a top-level segmented control AND via a double-tap gesture on the top-left of the screen, with the toggle completing in under 100 ms**,
So that **view-mode switching is fast, gesture-discoverable, and doesn't interrupt video playback (the player does NOT swap; only crop/style changes).**

**Acceptance Criteria (Gherkin):**

**Given** the user is in Cinema Mode
**When** they tap the segmented control "Full" / "Minimap" / "Minimap+HUD"
**Then** the view-mode crops/restyles on the SAME `expo-av` video source
**And** the transition completes in ≤ 100 ms (PERF-003)
**And** the video continues playing without seeking.

**Given** the user double-taps on the top-left of the screen
**When** the gesture is detected
**Then** the view-mode cycles: Full → Minimap → Minimap+HUD → Full → ...
**And** the same ≤ 100 ms transition applies.

**Given** the round's `map_name === 'unknown'`
**When** the user attempts to switch to Minimap or Minimap+HUD
**Then** the toggle gracefully degrades — only Full is selectable; Minimap / Minimap+HUD are disabled with a tooltip "Carte non identifiée" (per `mobile-CINEMA-003`).

**Given** the user toggles view-mode for the first time in a session AND `auth.t1_emitted === false`
**When** the toggle fires
**Then** T1-active-player telemetry emits via Story 2.5 wiring.

**Tests:** New jest tests at `apps/mobile/src/features/video-playback/__tests__/ViewModeToggle.test.tsx`:
- Test: segmented control toggle changes view mode.
- Test: double-tap top-left cycles view modes.
- Test: transition does not swap players (assert `expo-av` ref is the same instance).
- Test: T1-active-player emission on first toggle (mocked telemetry wrapper).
- Test: unknown map disables Minimap / Minimap+HUD options.

**Dependencies:** Stories 5.4, 2.5; Story 1.1 spike (PERF-003 measured); Epic 0 Story 0.2 legacy 7.3 view-mode toggle UI as foundation.

**Sprint fit:** fits-in-one-sprint.

### Story 5.6: Default Full View for Unknown Map (mobile-CINEMA-003)

As **Coach Thomas reviewing a round whose map could not be identified**,
I want **Cinema Mode to default to Full view (no Minimap+HUD ROI available)**,
So that **the round remains reviewable even when auto-identification failed (J3 graceful degradation).**

**Acceptance Criteria (Gherkin):**

**Given** Cinema Mode opens for a round where `map_name === 'unknown'`
**When** the view-mode is computed
**Then** the initial view is Full
**And** the segmented control's Minimap / Minimap+HUD options are visually disabled (gray; not interactable)
**And** the disabled options have an accessible tooltip "Carte non identifiée — bascule désactivée."

**Tests:** Updated jest test at `apps/mobile/src/features/video-playback/__tests__/CinemaModeScreen.test.tsx`: load round with `map_name === 'unknown'`; assert Full default + disabled toggles.

**Dependencies:** Story 5.5.

**Sprint fit:** fits-in-one-sprint.

### Story 5.7: View-Mode Preference Persistence (mobile-CINEMA-004)

As **Active Player Maxime returning to Warden after a previous session where I last used Minimap+HUD view**,
I want **Cinema Mode to default to my last-used view mode when I open a new round**,
So that **my preference is remembered and I don't manually re-toggle every time.**

**Acceptance Criteria (Gherkin):**

**Given** the user has used Minimap+HUD as the last view mode
**And** they exit Cinema Mode and re-enter for a different round (with a known map)
**When** Cinema Mode renders
**Then** the initial view is Minimap+HUD (read from MMKV `prefs.viewMode` + `prefs.minimapHud`).

**Given** the user exits Cinema Mode in Minimap+HUD view
**When** the next round is opened with `map_name === 'unknown'`
**Then** Cinema Mode falls back to Full per Story 5.6 (preference is overridden by graceful degradation).

**Given** the user toggles view mode mid-session
**When** the toggle fires
**Then** MMKV `prefs.viewMode` + `prefs.minimapHud` update immediately.

**Tests:** Updated jest test at `apps/mobile/src/features/video-playback/__tests__/CinemaModeScreen.test.tsx`: persist Minimap+HUD; reload; assert Minimap+HUD default.

**Dependencies:** Story 5.5.

**Sprint fit:** fits-in-one-sprint.

### Story 5.8: Next/Previous Explicit Buttons in Cinema Mode (mobile-CINEMA-005)

As **Coach Thomas reviewing multiple rounds in sequence**,
I want **explicit Next / Previous buttons in Cinema Mode (no swipe gesture — swipe conflicts with timeline scrub)**,
So that **navigation between rounds is discoverable and unambiguous (per legacy UX rejected-alternative: swipe is an anti-pattern here).**

**Acceptance Criteria (Gherkin):**

**Given** the user is in Cinema Mode on round N of M
**When** the controls reveal
**Then** "Next" and "Previous" buttons are visible (with affordance — chevron icons + accessible labels "Round suivant" / "Round précédent")
**And** if N === 1, "Previous" is disabled
**And** if N === M, "Next" is disabled.

**Given** the user taps "Next"
**When** the navigation runs
**Then** Cinema Mode loads round N+1 with view-mode preference applied (Story 5.7).

**Given** the user attempts a swipe gesture on the video
**When** the gesture fires
**Then** it does NOT trigger Next/Previous (swipe is reserved for timeline scrub or ignored; UX FU rejection).

**Tests:** Updated jest test at `apps/mobile/src/features/video-playback/__tests__/EpisodeNavigator.test.tsx`: Next/Previous buttons render; tap navigates; swipe does NOT trigger.

**Dependencies:** Stories 5.4, 5.5.

**Sprint fit:** fits-in-one-sprint.

---

## Epic 6: Mobile — Clip Creation, Voice & Export-Share

**Goal:** Coach Thomas creates a 30-second clip with bracket handles (5–60s bounds), records voice in 3 slots, previews, exports in Mobile/HD tier, OS-share-sheets to Discord with confirmed-dispatch firing T1-coach. Clip deletion cascades cleanly.

### Story 6.1: 30-Second Clip Region with Bracket Handles 5–60s Bounds (mobile-CLIP-001, FU-6)

As **Coach Thomas after scrubbing to a flank rotation**,
I want **to create a 30-second clip region centered on the current playback position, with bracket handles I can drag to extend (max 60s) or shorten (min 5s)**,
So that **the clip is scoped to the moment of interest with the flexibility to capture short reactions or long tactical sequences.**

**Acceptance Criteria (Gherkin):**

**Given** the user is in Cinema Mode at timestamp T
**When** they tap "Créer un clip"
**Then** a 30-second clip region is created centered on T (defaults: T-15s to T+15s, clamped to video bounds)
**And** bracket-handle UI is shown (left handle at start, right handle at end).

**Given** the user drags the right bracket handle outward
**When** the new clip duration would exceed 60s
**Then** the handle clamps at 60s (FU-6 max) and a haptic/visual feedback indicates the bound.

**Given** the user drags either bracket handle inward
**When** the new clip duration would fall below 5s
**Then** the handle clamps at 5s (FU-6 min) and a haptic/visual feedback indicates the bound.

**Given** the user drags a bracket handle past the video boundary (start < 0 or end > duration)
**When** the drag fires
**Then** the handle clamps at the video boundary.

**Tests:** New jest tests at `apps/mobile/src/features/clip-export/__tests__/ClipModeScreen.test.tsx`:
- Test: default clip region is 30s centered on playback position.
- Test: bracket handles clamp at 5s min / 60s max / video bounds.

**Dependencies:** Stories 5.4, 5.5 (Cinema Mode + view-mode toggle).

**Sprint fit:** fits-in-one-sprint.

### Story 6.2: Manual Clip from Any Timeline Point (mobile-CLIP-002)

As **Coach Thomas on a round where auto-slice missed**,
I want **to create a clip from any point in the Cinema Mode timeline, not requiring an auto-sliced Card**,
So that **J3 graceful degradation works — missed rounds remain clip-able from the timeline.**

**Acceptance Criteria (Gherkin):**

**Given** Cinema Mode is open on a round (auto-sliced or manual-from-Timeline-toggle per Story 5.3)
**When** the user scrubs to a point and taps "Créer un clip"
**Then** the clip region is created at that point (not constrained to auto-sliced segment boundaries).

**Given** the user is in Timeline view (Story 5.3) on a session-level scrubber
**When** they tap "Créer un clip ici" at a timestamp not within any auto-sliced segment
**Then** Cinema Mode opens at that timestamp; clip region is creatable per Story 6.1.

**Tests:** Extension to Story 6.1 jest tests: clip creation at non-auto-sliced timestamp.

**Dependencies:** Stories 5.3, 5.4, 6.1.

**Sprint fit:** fits-in-one-sprint.

### Story 6.3: 3-Slot Voice Annotation (Before / During / After) (mobile-CLIP-003)

As **Coach Thomas annotating a clip with my analysis**,
I want **to record voice in any of three slots — before, during, or after the clip — independently and optionally**,
So that **I can frame the clip ("here's what to watch"), narrate during ("Lucas, ton flank…"), or wrap up ("recule de 3 mètres") with the export carrying the layered audio.**

**Acceptance Criteria (Gherkin):**

**Given** the user has a clip region defined
**When** the clip-mode UI renders
**Then** three voice slot UI controls are visible: "Avant" / "Pendant" / "Après"
**And** each slot has a Record button (initially) and a Re-record + Play button after recording.

**Given** the user taps Record on "Pendant"
**When** the microphone permission is granted (or already granted)
**Then** recording starts; the clip plays back during the slot's recording window
**And** stop is automatic at the slot's end OR by tap.

**Given** the user records "Avant" only (skipping "Pendant" and "Après")
**When** export runs
**Then** the exported MP4 includes the "Avant" voice segment timed before the clip; "Pendant" and "Après" are silent (no padding audio added).

**Given** all three slots are skipped (silent clip)
**When** export runs
**Then** the exported MP4 is the visual clip only — no voice tracks.

**Tests:** New jest tests at `apps/mobile/src/features/audio-commentary/__tests__/AudioRecorder.test.tsx` and `apps/mobile/src/features/audio-commentary/__tests__/audioCommentService.test.ts`:
- Test: three slots are independently recordable.
- Test: skipping slots produces silent segments in export.
- Test: microphone permission prompt UX.

**Dependencies:** Story 6.1.

**Sprint fit:** fits-in-one-sprint.

### Story 6.4: Voice Slot Re-Record (mobile-CLIP-004)

As **Coach Thomas mid-recording on J2 (daughter wakes; thought interrupted)**,
I want **to re-record (overwrite) a voice slot after I've already recorded it once**,
So that **the second-attempt voice replaces the first; J2's "euh, donc là Maxime…" half-thought is overwritten cleanly.**

**Acceptance Criteria (Gherkin):**

**Given** a voice slot has been recorded
**When** the user taps Re-record on that slot
**Then** the previous recording is discarded
**And** new recording starts, overwriting the previous file in app sandbox.

**Given** auto-save (Epic 7 Story 7.1) is engaged
**When** the user records, then re-records, then exits the app mid-re-record
**Then** the resume on next launch shows the half-recorded re-record state (per `mobile-AUTOSAVE-002` resume contract).

**Tests:** Updated jest tests at `apps/mobile/src/features/audio-commentary/__tests__/AudioRecorder.test.tsx`: re-record overwrites; auto-save preserves mid-re-record state.

**Dependencies:** Story 6.3; cross-epic Epic 7 Story 7.1 (auto-save underpins the resume guarantee).

**Sprint fit:** fits-in-one-sprint.

### Story 6.5: Clip Preview with Assembled Voice (mobile-CLIP-005)

As **Coach Thomas about to export**,
I want **to preview the clip with assembled voice annotations before encoding**,
So that **I can verify the voice timing + content before committing to the encode + share.**

**Acceptance Criteria (Gherkin):**

**Given** a clip region + at least one voice slot is recorded
**When** the user taps "Prévisualiser"
**Then** the clip plays in-app with voice tracks layered (same audio assembly as the export will produce)
**And** I can replay, pause, scrub.

**Given** the user is satisfied with the preview
**When** they tap "Exporter"
**Then** the export pipeline (Story 6.6) starts.

**Given** the user wants to adjust after preview
**When** they tap "Modifier"
**Then** the clip mode returns; bracket handles + voice slots remain editable.

**Tests:** New jest tests at `apps/mobile/src/features/clip-export/__tests__/ExportShareScreen.test.tsx`: preview audio assembly matches export audio assembly.

**Dependencies:** Stories 6.1, 6.3.

**Sprint fit:** fits-in-one-sprint.

### Story 6.6: Mobile/HD Encode Tier Selection (mobile-EXPORT-001/002)

As **Coach Thomas about to share a clip**,
I want **to choose between Mobile (smaller file, faster encode) and HD (larger file, slower encode) quality tiers**,
So that **I can match the encode to the share context — Mobile for quick Discord shares; HD for archival or larger groups.**

**Acceptance Criteria (Gherkin):**

**Given** preview (Story 6.5) is complete
**When** the export quality picker renders
**Then** two options are visible: "Mobile" (~720p, lower bitrate) and "HD" (~1080p, higher bitrate)
**And** Mobile is the default.

**Given** the user picks Mobile
**When** the encode runs
**Then** FFmpeg-kit encodes the clip + voice + view-mode crop per `exportRecipes.ts`
**And** encode completes within PERF-005 budget (≤ 2× clip duration; e.g., 30 s clip → ≤ 60 s encode).

**Given** the user picks HD
**When** the encode runs
**Then** the encode may exceed PERF-005 (HD tier exemption per PRD)
**And** progress indication is surfaced (per `mobile-EXPORT-002`).

**Given** the encode fails (e.g., FFmpeg returns non-zero exit code)
**When** the error is caught
**Then** a clear French error message displays
**And** the clip-mode state is preserved (user can retry without re-defining the clip).

**Tests:** New jest tests at `apps/mobile/src/features/clip-export/__tests__/exportPipeline.test.ts`:
- Test: Mobile-tier encode within PERF-005 budget (mocked FFmpeg).
- Test: HD-tier encode produces correct recipe.
- Test: encode failure preserves clip-mode state.

**Dependencies:** Stories 6.1, 6.3, 6.5; Story 1.1 spike (PERF-005 measured).

**Sprint fit:** fits-in-one-sprint.

### Story 6.7: OS Share Sheet Dispatch (mobile-EXPORT-003)

As **Coach Thomas after encode completes**,
I want **the exported MP4 dispatched via the OS share sheet so I can pick Discord (or any installed share target)**,
So that **the J1 distribution moment fires (T1-coach telemetry on confirmed-dispatch).**

**Acceptance Criteria (Gherkin):**

**Given** encode completes successfully (Story 6.6)
**When** the post-encode callback runs
**Then** `expo-sharing.shareAsync(<mp4-path>)` is invoked
**And** the OS share sheet opens with the MP4 attached.

**Given** the user picks Discord (or any target)
**When** the share intent confirms dispatch (per `expo-sharing` resolved-success)
**Then** T1-coach telemetry emits (via Story 2.4 wiring)
**And** `clip_exports.exported_at` is persisted to SQLite for resume / re-share.

**Given** the user cancels the share sheet
**When** `expo-sharing` resolves with cancellation
**Then** T1-coach is NOT emitted (per Story 2.4)
**And** the clip remains in app sandbox; user can re-share via `mobile-CLIP-005` preview path.

**Tests:** Updated jest test at `apps/mobile/src/features/clip-export/__tests__/exportPipeline.test.ts`: share-sheet open; confirm dispatch → T1 emit; cancel → no emit.

**Dependencies:** Stories 6.6, 2.4.

**Sprint fit:** fits-in-one-sprint.

### Story 6.8: Discord-Inline-Playable H.264/AAC Contract Verification (mobile-EXPORT-004)

As **Passive Player Lucas receiving a clip on Discord**,
I want **the MP4 to play inline in Discord's preview pane without me installing the Warden app**,
So that **the J5 distribution moat works — distribution IS the product.**

**Acceptance Criteria (checklist):**

- [ ] Exported MP4 container: H.264 video codec + AAC audio codec (vanilla container; no proprietary codec or container).
- [ ] Exported MP4 file extension: `.mp4` (not `.mov` or `.m4v`).
- [ ] Exported MP4 video bitrate: ≤ 2 Mbps (Mobile tier) / ≤ 5 Mbps (HD tier) — keeps file size under Discord's 25 MB free-tier upload limit for typical 30-second clips.
- [ ] Exported MP4 audio bitrate: ≤ 128 kbps (sufficient for voice; not over-spec).
- [ ] Manual J5 verification: paste exported MP4 into a Discord channel; preview pane plays inline without prompting for app install.
- [ ] Manual J5 verification on alternate share targets: Messages (iOS preview, Android preview), Drive (link preview), WhatsApp (inline preview).
- [ ] If preview fails on Discord (e.g., codec mismatch), fall-back: `exportRecipes.ts` is updated to enforce stricter codec params; manual re-test.

**Tests:** Manual J5 verification (no automated tests for OS share sheet behavior). Architectural assertion in `apps/mobile/src/features/clip-export/exportRecipes.ts` documents the codec choices.

**Dependencies:** Stories 6.6, 6.7; Story 1.9 (J1–J10 manual verification).

**Sprint fit:** fits-in-one-sprint.

### Story 6.9: clipDeletion.ts Cascade (AR-12, PRIV-003)

As **Coach Thomas cleaning up a clip I no longer need**,
I want **deletion to cascade through the clip's MP4, voice annotations (`.m4a` files), processing checkpoints in MMKV, and SQLite rows**,
So that **PRIV-003 is honored — local deletion removes all derived data, no orphaned files remain.**

**Acceptance Criteria (Gherkin):**

**Given** the user has a clip with associated voice annotations + MMKV checkpoints + SQLite rows
**When** the user taps "Supprimer ce clip"
**And** confirms the deletion
**Then** the new service `apps/mobile/src/features/clip-export/clipDeletion.ts:deleteClip(clipId)`:
1. Reads `audio_comments.file_path` for each row referencing the clip; calls `expo-file-system.deleteAsync(path)` for each.
2. Reads `clip_exports.file_path`; calls `expo-file-system.deleteAsync(path)`.
3. Clears MMKV keys matching `processing.<sessionId>.*` for the parent session (if no other clips reference it).
4. Calls `clipExportRepository.deleteById(clipId)` — SQLite CASCADE handles `audio_comments` row deletion (foreign key).

**Given** the deletion fails partway (e.g., filesystem deletion fails)
**When** the error is caught
**Then** an error toast surfaces with a friendly French message
**And** the partial deletion is logged (filesystem cleanup may be incomplete; SQLite row may or may not have deleted).

**Given** PRIV-003 verification
**When** the test runs `clipDeletion.deleteClip(clipId)` then queries the filesystem + MMKV + SQLite
**Then** zero orphaned MP4 / `.m4a` files remain
**And** zero MMKV `processing.<sessionId>.*` keys remain (for the affected session)
**And** zero SQLite rows reference the deleted clip.

**Tests:** New jest test at `apps/mobile/src/features/clip-export/__tests__/clipDeletion.test.ts`:
- Test: full cascade — MP4 + voice + MMKV + SQLite all cleaned.
- Test: partial-failure error path.

**Dependencies:** Stories 6.6 (clip creation; SQLite + filesystem state exists).

**Sprint fit:** fits-in-one-sprint.

---

## Epic 7: Mobile — Auto-save & Crash Recovery

**Goal:** No data is lost across crash, force-close, OS-killed, or device-restart within the active editing session. J2 (daughter wakes; reopen 2h later) works without prompts.

### Story 7.1: Silent Auto-save in Clip Mode (mobile-AUTOSAVE-001)

As **Coach Thomas on J2 with a daughter waking up mid-clip**,
I want **clip-creation state (region, voice annotations, in-progress recording) auto-saved silently — no user-visible prompts at save time**,
So that **closing the app mid-clip does not lose work; resume is implicit on next launch.**

**Acceptance Criteria (Gherkin):**

**Given** the user has defined a clip region AND recorded at least one voice slot
**When** the app is backgrounded (foreground → background transition)
**Then** the new service `useClipExport.ts:autoSaveClipState` persists to MMKV:
- `clip-state.<sessionId>.region` (start + end timestamps)
- `clip-state.<sessionId>.voice.before` / `.during` / `.after` (file paths + recording-in-progress flag)
- `clip-state.<sessionId>.viewMode` (current view-mode at clip-creation time).
**And** NO toast / banner / dialog is shown ("silent" per `mobile-AUTOSAVE-001`).

**Given** the user is mid-recording on a voice slot
**When** the app is backgrounded
**Then** the recording is paused gracefully (audio stream stopped; partial `.m4a` file preserved)
**And** `clip-state.<sessionId>.voice.<slot>.inProgress = true` is persisted.

**Given** auto-save has fired
**When** the user explicitly invokes save (no such control exists in V1)
**Then** N/A — there is no explicit save UI. All saves are implicit.

**Tests:** New jest tests at `apps/mobile/src/features/clip-export/__tests__/useClipExport.test.ts`:
- Test: backgrounding triggers autoSaveClipState.
- Test: no toast/banner is shown.
- Test: mid-recording state is preserved.

**Dependencies:** Stories 6.1, 6.3; Epic 1 Story 1.2 (Foreground Service plugin keeps JS context alive).

**Sprint fit:** fits-in-one-sprint.

### Story 7.2: Resume Cinema Mode at Exact Frame (mobile-AUTOSAVE-002)

As **Coach Thomas reopening the app 2 hours after the daughter incident**,
I want **Cinema Mode to resume at the exact frame I left, with the clip region + bracket handles + in-progress voice annotation preserved**,
So that **I can pick up exactly where I left off without re-scrubbing or losing the half-recorded thought.**

**Acceptance Criteria (Gherkin):**

**Given** auto-save fired before app close (Story 7.1)
**When** the user re-opens the app
**Then** `App.tsx` boot reads `useSessionStore.currentSessionId` and the persisted `clip-state.<sessionId>.*` keys
**And** if a clip-state exists, navigation lands on Cinema Mode at the persisted timestamp
**And** the clip region (bracket handles) is restored
**And** any in-progress voice slot recording is shown as "Recording paused — tap to resume" UI.

**Given** the user wants to discard the half-recorded state
**When** they tap "Re-record" on the in-progress slot
**Then** Story 6.4 re-record path engages; previous file is discarded.

**Given** the app was crashed mid-recording (force-close, OS-killed, device-restart)
**When** the next launch boots
**Then** the same resume-from-MMKV path engages
**And** no data is lost (REL-001 contract).

**Tests:** New jest tests at `apps/mobile/__tests__/resume.test.ts`:
- Test: simulate background + resume → Cinema Mode opens at persisted timestamp.
- Test: simulate crash + resume → same.
- Test: simulate device-restart + resume → same.
- Test: half-recorded voice annotation is shown as paused state.

**Dependencies:** Story 7.1.

**Sprint fit:** fits-in-one-sprint.

### Story 7.3: Verify J2 Interruption + Resume E2E

As **Stephane validating the J2 happy path**,
I want **a manual end-to-end verification of J2 (interruption + resume) on Android dev build with both Battery Optimization enabled and disabled**,
So that **the auto-save + Foreground Service combination works under realistic Android conditions.**

**Acceptance Criteria (checklist):**

- [ ] Battery Optimization disabled: J2 scenario runs end-to-end. Background → 2-hour gap → resume → exact-frame restoration + voice-slot preservation. ✓
- [ ] Battery Optimization enabled: J2 scenario runs end-to-end. (Note: Android may aggressively kill backgrounded JS context; Foreground Service mitigates.) ✓ — and if not, document the failure mode + Foreground Service plugin tuning needed.
- [ ] Hard force-close: app force-closed via Recents tray. Re-open within 24 hours. State restored. ✓
- [ ] Device restart: device powered off + on. Re-open. State restored. ✓
- [ ] Sign-off note in V1 launch checklist (Epic 10) records the J2 verdict per scenario.

**Tests:** Manual J2 verification on dev build only (no automated test for backgrounding behavior in CI).

**Dependencies:** Stories 7.1, 7.2; Epic 1 Story 1.2 (Foreground Service plugin).

**Sprint fit:** fits-in-one-sprint.

---

## Epic 8: Mobile — French i18n, Help & Manual Error Reporting

**Goal:** Mobile UI is French-locked end-to-end (~150 strings); Account bottom-sheet Aide section links support@warden.team + Discord; errorReporting.ts mailto formatter supports manual error reporting in absence of a crash-reporting SDK.

### Story 8.1: French i18n Bundle at apps/mobile/assets/i18n/fr.json (UX-DR4, I18N-001/003)

As **Coach Thomas / Active Player Maxime**,
I want **every label, button, banner, error message, and system text in the mobile app rendered in French**,
So that **the FR-only V1 ships with a consistent French experience (no English fallthroughs).**

**Acceptance Criteria (checklist):**

- [ ] `apps/mobile/assets/i18n/fr.json` created with the ~150 strings from UX §4.1 (locked French copy deck).
- [ ] All hardcoded strings in `apps/mobile/src/features/**/*.tsx` and `apps/mobile/src/shared/components/**/*.tsx` are replaced with i18n keys (e.g., `t('login.signInButton')`).
- [ ] An i18n loader is added: minimal lookup function (no need for `i18next` heavy framework — a thin ~30-line lookup with `t(key) → fr.json[key]` suffices for V1; FR-only).
- [ ] **Reader-App gate (Story 2.1) scans the `fr.json` file** and confirms zero banned strings (verb forms only; the noun "abonnement" is permitted in entitlement labels).
- [ ] No English fallthroughs: a CI check (or manual scan) verifies no untranslated English strings remain in user-facing UI (`apps/mobile/src/features/**/*.tsx`).
- [ ] FR-locked entitlement labels: `t('entitlement.bannerTitle.paymentFailed') === 'Mise à jour du moyen de paiement nécessaire'`, `t('entitlement.lapsedScreenTitle') === 'Abonnement requis'`, `t('account.manageSubscription') === 'Gérer mon abonnement'` (LOCKED per FU-4).

**Tests:** New jest tests at `apps/mobile/src/shared/utils/__tests__/i18n.test.ts`:
- Test: lookup function returns correct French string for each key.
- Test: missing key returns the key itself (graceful fallback) — surfaced in dev mode as a warning.
- Test: locked entitlement labels match the FU-4 specification exactly.

**Dependencies:** Story 2.1 (Reader-App gate scans the bundle).

**Sprint fit:** fits-in-one-sprint.

### Story 8.2: errorReporting.ts mailto Formatter (UX-DR5, OBS-003 manual fallback)

As **Coach Thomas hitting an unexpected error in the app**,
I want **a "Signaler un problème" CTA that opens a mailto draft to support@warden.team with relevant context (app version, Android version, session ID, ISO 8601 timestamp, last-known-error, locale) — but NEVER frame data, voice durations, or clip metadata**,
So that **manual error reporting works in the absence of a V1 crash-reporting SDK (per architecture Important Gap #3) without leaking user content (per OBS-003 + PRIV-001).**

**Acceptance Criteria (Gherkin):**

**Given** an error condition is hit (e.g., codec-unsupported import, FFmpeg encode failure, network failure during entitlement re-fetch)
**When** the user taps "Signaler un problème"
**Then** `apps/mobile/src/shared/services/errorReporting.ts:formatErrorMailto(context)` is invoked
**And** a mailto link is opened via `Linking.openURL` with:
- `to=support@warden.team` (LOCKED per FU-1)
- `subject=[Warden] Rapport d'erreur — <last-known-error-code>`
- `body` includes: app version, Android version, session ID (UUID), timestamp (ISO 8601), last-known-error code/message, locale (fr-FR).

**Given** the mailto body is formatted
**When** inspected
**Then** the body contains NONE of: frame_*, voice_*, audio_*, recording_*, video_*, clip metadata beyond opaque session ID.

**Tests:** New jest test at `apps/mobile/src/shared/services/__tests__/errorReporting.test.ts`:
- Test: mailto link contains expected fields (version, OS, session ID, timestamp, error code, locale).
- Test: mailto body does NOT contain banned content patterns.
- Test: `to=support@warden.team` is hardcoded; cannot be overridden by config.

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

### Story 8.3: Account Bottom-Sheet Aide Section (UX-DR6)

As **Coach Thomas wanting help or community discussion**,
I want **the Account bottom-sheet (accessed via account icon in header) to include an Aide section with two CTAs: "Email support" → mailto:support@warden.team and "Discord communauté" → https://discord.gg/DpDEyBZw**,
So that **the support + community paths are discoverable from anywhere in the app.**

**Acceptance Criteria (Gherkin):**

**Given** the user is signed in
**When** they tap the account icon in the header
**Then** a bottom-sheet opens with sections: Compte (email, plan), Préférences (view-mode, sort), Aide (support email, Discord), Action (Se déconnecter).

**Given** the Aide section renders
**When** the user taps "Email support"
**Then** `Linking.openURL('mailto:support@warden.team')` is called.

**Given** the user taps "Discord communauté"
**When** `Linking.openURL('https://discord.gg/DpDEyBZw')` is called
**Then** the OS picks the appropriate app (Discord if installed, browser fallback) — Warden does NOT integrate the Discord API.

**Tests:** New jest test at `apps/mobile/src/features/auth/__tests__/AccountBottomSheet.test.tsx`:
- Test: Aide section renders with both CTAs.
- Test: "Email support" opens mailto with locked email.
- Test: "Discord communauté" opens locked Discord URL.

**Dependencies:** Story 8.1 (i18n bundle for Aide section labels).

**Sprint fit:** fits-in-one-sprint.

---

## Epic 9: Tooling — V1 Pipeline Hardening

**Goal:** J10 (developer regenerates `map_config.json`) verified end-to-end with `schema_version: 1`, jsonschema strict validation, accuracy regression for the 4 awaiting-hash maps, and Tool 5 real-footage AC validation.

### Story 9.1: schema_version: 1 Add to map_config.json Writers (BF-6, tooling-HASH-002)

As **Stephane**,
I want **`apps/tooling/tools/map_config_generator.py` and `apps/tooling/tools/hash_comparator.py` to emit `schema_version: 1` as a top-level field in every regenerated `map_config.json`**,
So that **the cross-language schema evolution mechanism has a backward-compat anchor (BF-6 cheap and load-bearing).**

**Acceptance Criteria (checklist):**

- [ ] `map_config_generator.py` writes `"schema_version": 1` as a top-level field.
- [ ] `hash_comparator.py` (when emitting via `--write-config`) writes the same.
- [ ] Regenerated `map_config.json` (committed to `apps/mobile/assets/map_config.json` per Story 1.13) contains `schema_version: 1`.
- [ ] `apps/tooling/tests/test_map_config_generator.py` asserts `schema_version: 1` is in the emitted output.

**Tests:** Updated pytest at `apps/tooling/tests/test_map_config_generator.py`: emit map_config.json on a fixture; assert `schema_version` field.

**Dependencies:** None within Epic 9; cross-epic supports Story 1.13.

**Sprint fit:** fits-in-one-sprint.

### Story 9.2: Tool 5 warden_analyzer Real-Footage AC Validation (tooling-WARDEN-001)

As **Stephane**,
I want **Tool 5 (`warden_analyzer.py`) validated against a real-footage test set — the legacy distillate flagged "Implementation Complete (AC unchecked — validation pending real-footage testing)"**,
So that **the J10 end-to-end pipeline confidence is bound; Tool 5 produces correct `rounds.json` on real EVA After-h footage.**

**Acceptance Criteria (checklist):**

- [ ] Real-footage test fixture set assembled at `apps/tooling/tests/fixtures/warden-analyzer/` (3–5 representative EVA After-h videos: short / medium / long; mix of map types).
- [ ] `warden_analyzer.py` run on each fixture; output `rounds.json` validated against:
  - Per-round map identification accuracy ≥ 95% on the fixture set.
  - Round-boundary detection ≥ 95% (matches the spike floor).
  - No crashes on edge-case codecs (H.265, unusual containers warn-and-continue).
- [ ] AC checkboxes in legacy `apps/tooling/docs/warden-round-analyzer.md` (or equivalent spec doc) are checked off post-validation.
- [ ] Sign-off note in V1 launch checklist (Epic 10).

**Tests:** New pytest at `apps/tooling/tests/test_warden_analyzer.py`: parameterized over fixture set; asserts accuracy floors.

**Dependencies:** Story 9.1.

**Sprint fit:** fits-in-one-sprint.

### Story 9.3: Reference Hash Regression for 4 Awaiting-Hash Maps

As **Stephane**,
I want **the 4 maps awaiting reference hashes (bastion, coliseum, lunar_outpost, the_rock per legacy distillate technical-debt inventory) to have hashes generated and validated**,
So that **the 14 canonical maps are all production-ready; no map ships with `unknown` due to missing reference data.**

**Acceptance Criteria (checklist):**

- [ ] For each of the 4 maps (bastion, coliseum, lunar_outpost, the_rock): reference video clips assembled (3–5 clips per map per legacy R&D conventions); frames labeled via `frame_labeler.py` into `labeled/<map_name>/`; `hash_comparator.py` regenerates with all 14 maps included.
- [ ] `hash_validator.py` accuracy report: each of the 4 newly-hashed maps reports ≥ 95% on unseen test fixtures.
- [ ] Updated `apps/mobile/assets/map_config.json` re-committed (per Story 1.13).
- [ ] `pnpm --filter @warden/contracts build` regenerates Zod (no schema change; only data change).

**Tests:** New pytest at `apps/tooling/tests/test_map_config_completeness.py`: assert all 14 maps in `MAP_LABELS` have a corresponding reference hash in `map_config.json`.

**Dependencies:** Stories 9.1, 1.13.

**Sprint fit:** fits-in-one-sprint.

### Story 9.4: jsonschema Strict Validation Against contracts/map-config.schema.json (tooling-SCHEMA-001)

As **Stephane**,
I want **`apps/tooling/tools/map_config_generator.py` to validate the emitted `map_config.json` against `contracts/map-config.schema.json` via `jsonschema` (strict; `additionalProperties: false`) before writing**,
So that **drift between the JSON Schema master and the tooling output is mechanically caught at emit-time, not at consumer-runtime.**

**Acceptance Criteria (checklist):**

- [ ] `map_config_generator.py` imports `jsonschema` and validates the in-memory dict against `contracts/map-config.schema.json` before writing the JSON file.
- [ ] If validation fails: clean error message + non-zero exit code; the file is NOT written.
- [ ] If validation succeeds: file written with `schema_version: 1` per Story 9.1.
- [ ] `hash_comparator.py` (when emitting) does the same.
- [ ] `apps/tooling/tests/test_map_config_schema.py` covers: emit valid map_config → passes validation; emit map_config with extra unknown field → fails validation per `additionalProperties: false`.

**Tests:** New pytest at `apps/tooling/tests/test_map_config_schema.py`. Existing pytest fixture at `apps/tooling/tests/fixtures/` provides representative input.

**Dependencies:** Stories 9.1, 1.13.

**Sprint fit:** fits-in-one-sprint.

---

## Epic 10: V1 Launch Readiness

**Goal:** V1 launch checklist closed; all V1-blocking gates verified; ToS-monitoring tracker exists; Stripe Production Activation unblocked (or known-blocker documented).

### Story 10.1: V1 Launch Checklist Deliverable (resolves Decision #ES-7)

As **Stephane preparing to ship V1**,
I want **a comprehensive V1 launch checklist at `_bmad-output/v1-launch-readiness-checklist.md` with story-traceable rows and explicit pass/fail gates per row**,
So that **launch readiness is unambiguous; every V1-blocker has a checkable row; sign-off binds the launch decision.**

**Acceptance Criteria (checklist):**

- [ ] Checklist file at `_bmad-output/v1-launch-readiness-checklist.md` exists with the following rows (each row: gate description, story reference, sign-off owner, status field):

| # | Gate | Story Ref | Owner | Status |
|---|------|-----------|-------|--------|
| L1 | AR-SPIKE published `_bmad-output/architecture-spike-perf-floor.md` with measured PERF-010 + ladder rung verdict | 1.1 | Stephane | TBD |
| L2 | Firebase v12 RN auth migration Story 3.F E2E sign-off of all 10 PRD journeys (J1–J10) | 1.9 | Stephane | TBD |
| L3 | Firestore Security Rules deployed to production | 1.15 | Stephane | TBD |
| L4 | Reader-App CI gate green on mainline (mobile build artifacts contain zero monetization-surface artifacts) | 2.1 | Stephane | TBD |
| L5 | EXPO_PUBLIC_AUTH_BYPASS verified `false`/unset in release configs | 2.6 | Stephane | TBD |
| L6 | Activation telemetry contract operational (T0 + dual-T1 emit verified on dev build) | 2.3 + 2.4 + 2.5 | Stephane | TBD |
| L7 | Six-state entitlement state machine — all 6 state regression tests pass | 3.1 | Stephane | TBD |
| L8 | Web token bump A11Y-001 contrast re-verify pass | 4.1 | Stephane | TBD |
| L9 | Web → Stripe Customer Portal cancel flow (J8) verified end-to-end with anti-dark-pattern policy | 4.5 | Stephane | TBD |
| L10 | OG card preview verified on Discord | 4.2 | Stephane | TBD |
| L11 | Mobile Cinema Mode + view-mode toggle PERF-003 ≤100 ms verified on reference device | 5.5 | Stephane | TBD |
| L12 | Discord-inline-playable MP4 verified on Discord (J5) | 6.8 | Stephane | TBD |
| L13 | clipDeletion cascade verified — zero orphans (PRIV-003) | 6.9 | Stephane | TBD |
| L14 | J2 interruption + resume verified on Android (Battery Optimization both enabled + disabled) | 7.3 | Stephane | TBD |
| L15 | French i18n bundle complete; no English fallthroughs in user-facing UI | 8.1 | Stephane | TBD |
| L16 | Tool 5 warden_analyzer real-footage AC validation pass | 9.2 | Stephane | TBD |
| L17 | All 14 canonical maps have reference hashes in production map_config.json | 9.3 | Stephane | TBD |
| L18 | ToS-monitoring tracker exists with EVA After-h entry | 10.2 | Stephane | TBD |
| L19 | Google Play V1 review-readiness checklist at apps/mobile/RELEASE.md complete | 10.3 | Stephane | TBD |
| L20 | Stripe Production Activation unblocked (company number from Root) | 10.4 | Root + Stephane | TBD |
| L21 | Demand evidence captured pre-V1 (≥ TBD coach interviews; waitlist depth; WTP validations) | 10.5 | Stephane | TBD (non-blocking) |

- [ ] All rows L1–L20 marked PASS or FAIL with date and signature; any FAIL row blocks V1 launch.
- [ ] Row L21 captured but non-V1-blocking per PRD §2 (re-baselining inputs deferred but mandated).

**Tests:** No code tests (this IS the launch-decision artifact). Manual sign-off.

**Dependencies:** All other stories (this is the synthesis epic).

**Sprint fit:** fits-in-one-sprint.

### Story 10.2: ToS-Monitoring Tracker for EVA After-h (PRD §5)

As **Stephane preparing for V1 launch and game-publisher ToS adjacency**,
I want **a ToS-monitoring tracker at `docs/compliance/tos-monitoring.md` with one entry for EVA After-h: current ToS version, screen-recording policy, monetization-around-game policy, last-reviewed date**,
So that **PRD §5 game-publisher ToS obligation is honored — Warden has a record of the ToS posture per supported title.**

**Acceptance Criteria (checklist):**

- [ ] `docs/compliance/tos-monitoring.md` created with one row for EVA After-h:
  - Title: EVA After-h
  - Current ToS version: <version> (date)
  - Screen-recording policy: <permitted/not-permitted/conditional>
  - Monetization-around-game policy: <permitted/conditional>
  - Last-reviewed date: 2026-XX-XX
  - Reviewer: Stephane
- [ ] Tracker structure supports future multi-title for V3 (rows are extensible; schema is consistent).
- [ ] If EVA After-h ToS prohibits screen-recording or monetization-around-game in any way that conflicts with Warden's posture: V1 LAUNCH BLOCKED until reconciled.

**Tests:** No code tests. Manual review.

**Dependencies:** None.

**Sprint fit:** fits-in-one-sprint.

### Story 10.3: Google Play V1 Review-Readiness Checklist (apps/mobile/RELEASE.md)

As **Stephane submitting to Google Play**,
I want **`apps/mobile/RELEASE.md` populated with a comprehensive checklist covering Play Console requirements: privacy policy URL, data safety form, content rating questionnaire, sample app credentials, signing key, target SDK, screenshots, store listing copy**,
So that **Play submission is a checklist exercise, not a discovery exercise.**

**Acceptance Criteria (checklist):**

- [ ] `apps/mobile/RELEASE.md` exists with sections:
  - Pre-submission checklist (privacy policy URL hosted on web; data safety form prepared; content rating answered)
  - Reader-App posture statement (for any reviewer query: "Stripe via web; mobile has no store-billable transaction")
  - Signing key configured (release keystore; backup verified)
  - Target SDK + minSdk verified (per Expo SDK 54 defaults)
  - Screenshots prepared (Card View, Cinema Mode + Minimap+HUD, Clip mode, Export-share)
  - Store listing copy (FR-locked per UX §4.1)
  - Sample app credentials provided (test account on the production Firebase project)
  - First-launch verification: install signed bundle on Poco X5; sign in; auto-slice; export; share — entire J1 path passes on a real release build.

**Tests:** Manual checklist verification. No automated tests.

**Dependencies:** Story 1.9 (J1–J10 verified on dev build); Story 1.15 (firestore.rules in prod).

**Sprint fit:** fits-in-one-sprint.

### Story 10.4: Stripe Production Activation (Legacy Web Story 7.4 Carryover)

As **Stephane preparing live Stripe Checkout**,
I want **Stripe Production Activation completed: live keys, webhook secret, DNS, Vercel prod deploy, security review checklist**,
So that **paying coaches can complete checkout on the production environment (not a test environment).**

**Acceptance Criteria (checklist):**

- [ ] Stripe live keys provisioned in Stripe Dashboard.
- [ ] Vercel prod env vars configured: `STRIPE_SECRET_KEY=sk_live_...`, `STRIPE_PUBLISHABLE_KEY=pk_live_...`, `STRIPE_WEBHOOK_SECRET=whsec_...` (live webhook).
- [ ] Stripe Dashboard webhook endpoint configured to point at production: `https://warden.team/api/webhooks/stripe` (or actual prod URL); subscribed events match Decision #9 list (`invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`).
- [ ] DNS verified: warden.team (or production domain) points to Vercel; SSL/TLS green.
- [ ] Security review checklist (legacy Web Story 7.4 spec): all rows checked.
- [ ] **External blocker:** company number provided by Root (carry-over from legacy distillate). If unblocked, status changes from BLOCKED to PASS.

**Tests:** Manual smoke test on live: complete one test transaction with a real card ($0.50 charge if possible; refund immediately). Webhook fires; dashboard updates.

**Dependencies:** Stories 1.12, 1.15, 1.16; Root provides company number (external).

**Sprint fit:** fits-in-one-sprint conditional on the external unblocker.

### Story 10.5: Demand Evidence Capture Pre-V1 (PRD §2; non-V1-blocking)

As **Stephane validating the WoM-driven Discord-distribution hypothesis pre-V1**,
I want **interview count, waitlist depth, and explicit willingness-to-pay validations captured from EVA After-h coaches**,
So that **the legacy 20-paying-coaches / 100-subscribers reference targets are re-baselined post-V1 with real demand evidence (PRD §2 mandated; non-V1-blocking).**

**Acceptance Criteria (checklist):**

- [ ] Interview count ≥ TBD captured from EVA After-h coaches (target re-baselined post evidence; minimum recommended ≥ 5).
- [ ] Interviews documented at `docs/research/coach-interviews-2026-XX.md` with: coach handle / Discord username, interview date, current workflow description (laptop + notepad + editor pattern verified), willingness-to-pay anchor question response (€7.99/mo ≥ acceptable / not acceptable), waitlist sign-up if interested.
- [ ] Waitlist depth: count of unique Discord handles or emails captured.
- [ ] WTP validations: count of coaches answering "yes" to the €7.99/mo anchor.
- [ ] Re-baselined targets table written into PRD §2 (replaces "Reference — re-baseline pending" rows).
- [ ] **Status: NON-V1-BLOCKING.** PRD demands capture before launch but does not block launch on the metric thresholds. Sprint planning treats reference targets as not-bound until evidence captured.

**Tests:** No code tests. Manual interview process documented.

**Dependencies:** None (parallel to all other stories).

**Sprint fit:** fits-in-one-sprint (parallel to Sprint 3 mobile/web work; can be a parallel demand-evidence sprint).

---

## Resolved Escalated Decisions (ES-1 through ES-10)

The 10 escalated decisions from the user's epics-and-stories briefing are now resolved. Each is summarized below; full details are inline in the relevant epics + stories above.

### Decision #ES-1 — Sprint 3 Epic Boundaries [RESOLVED]

11 epics: Epic 0 (Sprint 2.5 closure transition gate) + Epic 1 (foundations + V1-blocking spike + brownfield + cross-language contracts) + Epic 2 (Reader-App gate + activation telemetry contract) + Epic 3 (six-state entitlement: state machine + UI banners + lapsed screen) + Epic 4 (web subscribe & manage funnel) + Epic 5 (mobile Card View, Cinema Mode + manual-clip-from-timeline) + Epic 6 (mobile clip creation, voice & export-share) + Epic 7 (mobile auto-save & crash recovery) + Epic 8 (mobile French i18n, help & manual error reporting) + Epic 9 (tooling V1 pipeline hardening) + Epic 10 (V1 launch readiness).

Rationale: organize by user value where possible (Epics 3–9); honestly label foundation/contract/launch-readiness epics (Epics 0/1/2/10). The 18-item UX §6.5 surface is split across Epics 3/4/5/6/8 by feature-folder boundary rather than lumped as one technical-layer epic — this aligns with the skill's "do not organize by technical layers" principle.

### Decision #ES-2 — Pre-PRD Performance Spike Sequencing [RESOLVED]

Story 1.1 (AR-SPIKE) is the load-bearing first deliverable. Sprint 3 story-scope finalization gates on its outcome. The spike-outcome ladder (pass / rung-1 lower frame-sampling / rung-2 drop Minimap+HUD on weak HW / rung-3 manual-clip-only V1) explicitly conditions downstream story shape (mobile-AUTO-SLICE-* FRs become V2-deferred under rung-3; CardViewScreen Cards mode hides under rung-3; manual-clip-from-Timeline-toggle becomes the only path). FORBIDDEN: cloud fallback (asserted as anti-pattern regardless of measured numbers).

### Decision #ES-3 — Sprint 2.5 Per-Story Conflict Audit [RESOLVED]

Epic 0 owns the audit. Story 0.1 produces the per-story disposition table (10 rows: 2.2, 2.5, 2.6, 2.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6). Story 0.2 executes the dispositions (complete-as-legacy / re-scope-into-Sprint-3-with-new-AC / drop). Audit gates Sprint 3 commit.

### Decision #ES-4 — Story Dependencies and Ordering [RESOLVED]

Each story declares prior-stories-only dependencies (no forward references). Cross-epic dependencies are explicit. The architecture-bound BF-3 sequence (Stories 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9; Firebase v12 RN auth migration 3.A → 3.F) is preserved. Schema reconciliation triple (1.10 → 1.11 → 1.12; AR-1 → AR-2 → AR-3) lands in dependency order. Reader-App gate (Story 2.1) lands before any new mobile feature compose-time additions (Stories 5.x, 6.x, 7.x, 8.x) so banlist regressions are caught at PR-time. Activation telemetry wrapper (Story 2.2) lands before T0/T1 emission code (2.3, 2.4, 2.5). deriveEntitlementState (Story 3.1) lands before EntitlementBanner (3.2) + SubscriptionRequiredScreen (3.3).

### Decision #ES-5 — Acceptance Criteria Format [RESOLVED]

Hybrid: Gherkin Given-When-Then for behavior-driven user-flow stories (most user-facing flows in Epics 3, 5, 6, 7, 8 + most of Epic 4); explicit checklists for infrastructure stories (most of Epic 0, 1, 2 + most of Epic 9 + all of Epic 10 + token bump 4.1 + OG meta 4.2 + Reader-App regex narrowing). Choice is per-story based on whether the deliverable is "the user can…" (Gherkin) or "the artifact exists with these properties…" (checklist). Both formats live alongside each other.

### Decision #ES-6 — Test Ownership per Story [RESOLVED]

Each story declares which tests it adds, where they live, and what they cover. Test framework per surface (architecture-bound):
- Mobile: jest + jest-expo, co-located `__tests__/<subject>.test.ts(x)`.
- Web: vitest + jsdom + @testing-library/react, co-located `<subject>.test.ts(x)`.
- Tooling: pytest at `apps/tooling/tests/` with fixtures under `apps/tooling/tests/fixtures/`.

Architecture explicitly named: telemetry wrapper allowlist tests (Story 2.2), `deriveEntitlementState` 6-state regression tests (Story 3.1), Stripe webhook idempotency regression tests (Story 1.17). Other stories' test ownership produced inline.

### Decision #ES-7 — V1 Launch Gate Composition [RESOLVED]

Epic 10 Story 10.1 produces the explicit V1 launch checklist with 21 story-traceable rows (L1–L21). Each row has a gate description, story reference, sign-off owner, and status field. Rows L1–L20 are V1-blocking (any FAIL blocks launch); row L21 (demand evidence capture) is non-V1-blocking but PRD-mandated to capture before launch. Stripe Production Activation (L20) is blocked on Root providing the company number (external dependency carried over from legacy Web Story 7.4).

### Decision #ES-8 — V2/V3 Backlog Seeding [RESOLVED]

V2 backlog seeded inline within this document (below). V3 stays as Vision pointers — no story-level seeding.

#### V2 Backlog Seed

(One-line entries per PRD §3 V2 Growth Features, traceable back to the PRD section.)

- V2-1: Discord OAuth (web — adds to Google + Email/Password).
- V2-2: Coupon admin UI (web self-serve; replaces Stripe-dashboard-only management).
- V2-3: Custom analytics dashboard (web — replaces Firebase Analytics).
- V2-4: Team / group billing (web — multi-seat coaches).
- V2-5: Self-serve account deletion (web — replaces V1 manual via support email).
- V2-6: Churn survey on cancellation (web — V1 has no exit survey).
- V2-7: In-dashboard coupon redemption (web — V1 routes coupons through Stripe URL param).
- V2-8: OCR scores / kills (mobile — populates `score_orange` / `score_blue`; enables score-based Card View sorts).
- V2-9: Stats per map (mobile — depends on OCR).
- V2-10: Advanced ROI composition (mobile — minimap + killfeed + life zones).
- V2-11: Vertical export format (mobile — Stories / TikTok format).
- V2-12: Custom ROI templates (cross-surface — desktop-flavored).
- V2-13: Review import mode (mobile — closes J4 partial-support gap).
- V2-14: Pick & Ban tool (cross-surface).
- V2-15: Multi-view clip export (mobile — POV → minimap switch via multi-segment FFmpeg).
- V2-16: Export queue with background encoding (mobile — replaces V1's encode-immediately-then-share).
- V2-17: Diagnose Vitest parallelism flake (web — V1 ships with serial-mode workaround per BF-4).
- V2-18: Crash reporting SDK evaluation (V2 add Sentry/Crashlytics if user volume justifies; MUST exclude user content per [INVARIANT 3] / OBS-003).
- V2-19: CI workflows in `.github/workflows/` (V0 = local + pre-commit; V2 = full GitHub Actions per architecture Phase-7 backlog).
- V2-20: EAS Build for mobile (manual today via `expo prebuild` + Android Studio + Play Console; V2 candidate).
- V2-21: Per-route `loading.tsx` in web App Router (currently inline `<Skeleton />`; future polish).

V3 Vision pointers (no story-level seeding):
- Broader tactical-FPS coaching companion (CS2 / Valorant / R6 — config + per-title detector tuning).
- Referral system (web — "dealer of comfort" growth).
- Full French localization (web UI — V1 is English with FR-locked hero).
- iOS (mobile — Phase 2 after Apple license).
- Desktop (cross-surface — power-user analysis).
- Discord stream group review (cross-surface — Phase 3, Desktop-flavored).

### Decision #ES-9 — Story Estimation Discipline [RESOLVED]

NO numeric estimates. Binary `fits-in-one-sprint` / `needs-spike-or-split` gate per story. Story 1.1 (AR-SPIKE) is the only `needs-spike-or-split` story by design — its outcome dictates downstream story shape. All other 75 stories are flagged `fits-in-one-sprint`. Solo-dev velocity is opaque enough that point-estimating wastes effort; the binary gate forces explicit acknowledgment when a story is not realistically fittable in one focused day.

### Decision #ES-10 — Maintenance Budget per Surface [RESOLVED]

Sprint planning (next phase, `bmad-sprint-planning`) consumes this guidance:

**Maintenance budget contract (placeholder; structure binds, numbers are placeholder pending solo-dev velocity-tracking):**
- **20% of weekly capacity** reserved for cross-surface maintenance backlog (dependency updates, brownfield-debt-decay monitoring, monitoring-alert response, ToS-monitoring tracker updates).
- **80% of weekly capacity** for Sprint 3 V1 stories.

**Per-surface maintenance allocation within the 20%:**
- Mobile: ~40% of maintenance budget (largest surface; FFmpeg-kit fork monitoring; Foreground Service plugin OS-version-related changes; Firebase v12 RN auth minor updates).
- Web: ~30% of maintenance budget (Stripe API version monitoring; Vitest/Vercel/Next.js minor updates).
- Tooling: ~15% of maintenance budget (opencv-python / numpy / pyyaml minor updates; Python version compatibility).
- Cross-cutting (contracts, CI, ops): ~15% of maintenance budget.

**Trigger to re-baseline allocation:** if any single surface consistently over-runs its allocation in 2 consecutive weeks, re-baseline; do NOT lump maintenance into a single bucket (Risk #8 escalation explicitly warns against this).

**Risk #8 (maintenance surface concentration) mitigation explicit:** the brief warns "maintained as one product may discover four." This budget contract structures explicit per-surface allocation rather than aggregating; if maintenance surfaces grow disproportionately on one surface, the structure surfaces it visibly rather than burying it in a global maintenance bucket.

---

## Step 4 Validation Results

### FR Coverage Validation — 69/69 FRs Accounted For

**Mobile (33/33):**
All 33 mobile FRs have story coverage. mobile-AUTH-001..006 in Epic 3 (Stories 3.7, 3.8, 3.3, 3.9, 3.10, 3.2). mobile-IMPORT-001/002 in Epic 0 (legacy Sprint 2.5 Story 2.1 DONE; verified via 0.1 audit). mobile-AUTO-SLICE-001..004 in Epic 0 (Sprint 2.5 Stories 2.5 + 7.5 ready-for-dev) + Epic 1 spike outcome (Story 1.1 dictates whether ships V1). mobile-CARD-001..005 in Epic 5 (Stories 5.1, 5.2, 5.3). mobile-CINEMA-001..005 in Epic 5 (Stories 5.4–5.8). mobile-CLIP-001..005 in Epic 6 (Stories 6.1–6.5). mobile-EXPORT-001..004 in Epic 6 (Stories 6.6–6.8). mobile-AUTOSAVE-001/002 in Epic 7 (Stories 7.1, 7.2).

**Web (16/16) — split between new Sprint 3 stories and legacy carry-forward:**
- **Covered by new Sprint 3 stories (7):** web-LANDING-002 (Story 4.2 OG meta), web-DASHBOARD-002 (Story 3.5), web-DASHBOARD-003 (Story 3.6), web-DASHBOARD-004 (Story 4.5), web-DASHBOARD-005 (Story 4.6), web-WEBHOOK-001 / web-WEBHOOK-002 (Stories 1.12 + 1.17 — legacy COMPLETE; Sprint 3 extends with `customer.subscription.updated` handler + idempotency regression coverage), web-WEBHOOK-003 (Story 1.14 firestore.rules + 1.15 prod deploy), web-ANALYTICS-001 (Story 4.8).
- **Legacy carry-forward — verified via Epic 10 launch checklist L9 + L10 + L20 (9):** web-LANDING-001 (legacy Web Epic 1 Story 1.2 DONE — FR-locked hero on `/`), web-PRICING-001 (legacy Web Epic 3 Stories 3.1 + 3.3 DONE — 2 plan cards + Stripe coupon URL param), web-PRICING-002 (legacy Web Epic 3 Story 3.2 DONE — auth modal before Checkout), web-AUTH-001 (legacy Web Epic 2 Stories 2.1–2.4 DONE — Google + Email/Password Firebase Auth; Sprint 3 Story 4.4 ADDS the FU-5 password-reset path on top), web-CHECKOUT-001 (legacy Web Epic 3 Story 3.2 DONE — Stripe Checkout redirect + deferred-billing copy), web-CHECKOUT-002 (legacy Web Epic 3 Story 3.2 DONE — `/dashboard?success=1` return path), web-DASHBOARD-001 (legacy Web Epic 5 Stories 5.1 + 5.2 DONE per Sprint Change Proposal 2026-04-16 — protected route + status badge + Customer Portal deep-link).
- **Web carry-forward verification posture:** Sprint Change Proposal 2026-04-16 already RESOLVED the Web Epic 5 conflict (custom payment-history / upgrade / cancel UI removed; delegated to Customer Portal). No web-side conflict audit needed in Epic 0 (Decision #ES-3 was scoped to mobile per legacy distillate). Sprint 3 stories TOUCH the carry-forward FRs only with deltas (FU-5 password reset, UX-DR9 cancel dialog, UX-DR10 EmptySubscription, UX-DR13/14 OG card, UX-DR16 token bump, UX-DR18 copy embedding); the underlying FR contracts are unchanged. V1 launch checklist verifies the funnel end-to-end on the production environment.

**Tooling (12/12) — split similarly:**
- **Covered by new Sprint 3 stories (4):** tooling-HASH-002 (Story 9.1 schema_version add), tooling-WARDEN-001 (Story 9.2 Tool 5 real-footage AC validation), tooling-VALIDATE-001 (Story 9.2 + 9.3 four-maps regression), tooling-SCHEMA-001 (Story 9.4 jsonschema strict).
- **Legacy carry-forward — verified via Epic 10 launch checklist L17 + tooling spec-level statuses (8):** tooling-ROUND-DETECT-001 (legacy: working impl exists per legacy distillate Sprint State; sprint tracker not updated to reflect actual state), tooling-ROUND-DETECT-002 (legacy: miss-report functionality in BSD reference impl), tooling-LABEL-001 (legacy: frame_labeler.py DONE; full GUI), tooling-LABEL-002 (legacy: MAP_LABELS source-of-truth at `tools/frame_labeler.py:19-34` LOCKED), tooling-HASH-001 (legacy: hash_comparator + map_config_generator working; Sprint 3 Story 9.1 adds schema_version), tooling-VALIDATE-002 (legacy: hash_validator pipeline-param parity from map_config.json — covered by Story 9.4 strict validation enforcement), tooling-TUI-001 (legacy: warden-tui-launcher Completed), tooling-TUI-002 (legacy: `.warden_last_run.json` re-run support Completed).

**Cross-surface (8/8):** all covered by new Sprint 3 stories — cross-ENTITLEMENT-001 (Story 3.1), cross-ENTITLEMENT-002 (Stories 1.14 + 1.15), cross-ACTIVATION-001 (Stories 2.3 + 2.4 + 2.5), cross-ACTIVATION-002 (Story 2.2), cross-SCHEMA-001 (Stories 1.13 + 9.4), cross-SCHEMA-002 (Stories 1.10 + 1.11), cross-READER-APP-001 (Story 2.1), cross-MAP-CONFIG-DELIVERY-001 (Story 1.13).

**Total: 69/69 FRs accounted for.** No FR is uncovered. The legacy-carry-forward subset is explicitly documented; verification routes through Epic 10 launch checklist + Sprint 3 delta stories that don't regress the carry-forward contracts.

### NFR Coverage Validation — 41/41 NFRs Accounted For

All 41 NFRs map to one or more stories per the FR Coverage Map's NFR section above. Spike-bound NFRs (PERF-002/003/004/005/010, REL-006) are bound by Story 1.1 outcome. Legacy-met NFRs (PERF-006/007/008, REL-003, SEC-005, A11Y-001/002/003/004) are inherited from working web implementation; Sprint 3 only re-verifies post-token-bump (Story 4.1) and ensures no regression. Defense-in-depth NFRs (SEC-001/002/004/006/007, PRIV-001/002, OBS-003) are reinforced at multiple layers (Reader-App gate Story 2.1; telemetry wrapper Story 2.2; firestore.rules Stories 1.14/1.15; webhook idempotency Story 1.17).

### Architecture Implementation Validation

**Starter template setup:** N/A — architecture explicitly states "Project context: brownfield — starter selections are historical." Three pre-existing apps (`apps/mobile`, `apps/web`, `apps/tooling`) imported into the monorepo with full git history. Epic 1 Story 1.1 is NOT "Set up initial project from starter template"; it is the pre-PRD performance spike (the load-bearing first deliverable). This deviation from the skill's default Epic 1 Story 1 expectation is intentional and correct per architecture's brownfield posture.

**Database / entity creation:** Stories create / alter only what they need. Mobile SQLite tables (`sessions`, `map_segments`, `clip_exports`, `audio_comments`) are already-shipped per legacy. The only NEW table-shape change in Sprint 3 is the `view_mode` 2-value → 3-value migration in Sprint 2.5 Story 7.1 (handled in Epic 0 closure as legacy-COMPLETE). No story creates "all tables upfront." `contracts/user-doc.schema.json` is tightened in Story 1.10 (only when needed by Decision #1). `contracts/map-config.schema.json` adds `schema_version` field in Story 1.13 (only when needed by BF-6 + Decision #2).

### Story Quality Validation

**Single dev agent sized?** All 76 stories are flagged `fits-in-one-sprint` except Story 1.1 (AR-SPIKE) which is `needs-spike-or-split` by design (its outcome dictates downstream story shape; the spike IS the unknowable). Story 1.9 (J1–J10 E2E manual test) is large but bounded — one focused day of E2E verification on dev build.

**Clear acceptance criteria?** All 76 stories have AC in either Gherkin Given-When-Then (behavior-driven user flows) or explicit checklist (infrastructure deliverables) per Decision #ES-5 hybrid.

**FR / NFR / UX-DR references?** Every story references the specific FRs / NFRs / UX-DRs / architecture work items (AR-X) / brownfield items (BF-X) / CI items (CI-X) it implements; the FR Coverage Map cross-references back.

**Test ownership declared?** Every story declares which tests it adds, where they live (per-surface co-location convention from architecture step 5), and what they cover. Per Decision #ES-6.

**No forward dependencies?** Validated per epic:
- Epic 0: Story 0.1 → 0.2 (sequential; 0.2 executes 0.1's verdicts).
- Epic 1: Story 1.1 standalone gates downstream; Stories 1.4 → 1.9 sequential per architecture-bound BF-3 sequence; Stories 1.10 → 1.11 → 1.12 sequential per Decision #1/#6/#9 triple; Stories 1.13–1.18 declare correct prior-only deps.
- Epic 2: Story 2.1 → 2.2 → (2.3, 2.4, 2.5 parallel-ish on the wrapper); 2.6 extends 2.1.
- Epic 3: Story 3.1 → (3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10 parallel on derived state).
- Epic 4: 8 stories largely independent; Story 4.4 depends on prior auth modal existing (legacy carry-forward); Story 4.8 cross-epic depends on Story 1.12 (trialing handler).
- Epic 5: 5.1 → 5.2/5.3 → 5.4 → 5.5 → 5.6/5.7/5.8 (each story builds on prior).
- Epic 6: 6.1 → 6.2/6.3/6.4/6.5 → 6.6 → 6.7/6.8 → 6.9.
- Epic 7: 7.1 → 7.2 → 7.3 (verification).
- Epic 8: 8.1 → 8.2/8.3 (parallel after bundle).
- Epic 9: 9.1 → 9.2/9.3/9.4 (parallel after schema_version add).
- Epic 10: all stories parallel (synthesis from prior epics).

**Cross-epic forward-dependency check:** One soft cross-epic reference noted in Story 2.5: "cross-epic depends on Epic 5 Story 5.5 (view-mode toggle UI exists; this story wires the telemetry hook into it)." Resolution: the view-mode toggle UI exists in legacy code (Sprint 2.5 Story 7.3 lands the toggle UI; closed under Epic 0 Story 0.2 as complete-as-legacy). Story 2.5 reads CinemaModeScreen.tsx + ViewModeToggle.tsx and adds a telemetry-emit hook on the existing first-toggle event. PERF-003 ≤100 ms enforcement (Story 5.5) is orthogonal and can land before OR after Story 2.5 without affecting the telemetry hook. **No forward-dependency violation.**

### Epic Structure Validation

**User-value organization?** Yes for Epics 3–9 (each delivers a meaningful user outcome — entitlement trust, web subscribe-and-manage, mobile review experience, mobile clip artifact production, mobile reliability, mobile localization, operator regenerate-config). Honestly labeled foundation/contract/launch for Epics 0/1/2/10 (transition gate / V1-blocking infrastructure / cross-surface contracts / launch checklist).

**File churn check:** Multiple stories touch `apps/mobile/src/features/auth/subscriptionService.ts` across epics (Story 1.7 Epic 1 RN auth migration; Stories 3.1, 3.9 Epic 3 deriveEntitlementState + 30-day cache verification). These are **additive non-conflicting changes** — Epic 1 swaps the wire-format API; Epic 3 adds new exports + tests. Splitting is justified by Epic 1 = foundation (V1-blocking architecture-bound sequence) versus Epic 3 = entitlement-state user value. Consolidation into one epic would force Epic 1's BF-3 sequence to drag the entire entitlement-state UI + UX surface into a single epic, blowing past coherent boundaries.

Multiple stories touch `apps/mobile/src/features/clip-export/exportPipeline.ts` (Story 2.4 T1-coach emit; Stories 6.6/6.7/6.9 encode + share + deletion). Three Epic 6 stories are within one epic (proper incremental progression). Epic 2 Story 2.4 inserts a hook into the post-share callback — a hook addition, not churn.

Multiple stories touch `apps/web/src/components/dashboard/SubscriptionCard.tsx` (Story 3.5 PaymentWarning composition; Story 3.6 Canceling badge). Each adds a distinct conditional UI surface; not churn.

**Conclusion:** No file-churn violations.

### Dependency Validation (Epic Independence)

- **Epic 0** runs first (no prior dependencies; gates Sprint 3 commit per Decision #ES-3).
- **Epic 1** depends on Epic 0 (legacy work disposed before foundation-blocking work commits).
- **Epic 2** depends on Epic 1 (Story 1.4 RN auth deps + Story 1.6 authService for T0 emit).
- **Epic 3** depends on Epic 1 (Story 1.7 subscriptionService migrated; Stories 1.10/1.11/1.12 contract triple).
- **Epic 4** depends on Epic 1 (Story 1.12 trialing handler for entitlement-read alignment); independent of mobile epics — can parallelize.
- **Epic 5** depends on Epic 0 (legacy view-mode toggle UI from Sprint 2.5 Story 7.3); Epic 1 (spike outcome dictates Card View shape per ladder rung); Epic 2 (telemetry wrapper for T1-active-player path).
- **Epic 6** depends on Epic 5 (Cinema Mode platform); Epic 1 (spike for FFmpeg encode budget); Epic 2 (telemetry wrapper for T1-coach path).
- **Epic 7** depends on Epic 6 (clip-creation state to auto-save) + Epic 1 (Foreground Service plugin for JS-context survival).
- **Epic 8** depends on Epic 2 (Reader-App gate scans the i18n bundle); independent otherwise.
- **Epic 9** depends on Epic 1 (Story 1.13 hybrid map_config.json + schema_version regenerated).
- **Epic 10** depends on all other epics (synthesis).

**Each epic delivers complete functionality for its domain.** Epic 2 ships the Reader-App contract + telemetry wrapper independently of whether Epic 5 (Cinema Mode enhancements) lands — the wrapper + gate + T0 emit + share-callback T1-coach are all standalone deliverables. Epic 5 can ship without Epic 6 — Cinema Mode + Card View deliver review value even if clip-creation doesn't land yet (manual-clip-from-Timeline-toggle works as the rung-3 fallback). Epic 8 can ship without Epic 7 — French i18n is value-complete on its own.

**No epic requires a future epic to function.** ✓

### Resolved Decisions Cross-Check

All 10 escalated decisions (#ES-1 through #ES-10) RESOLVED inline. Resolutions are documented in the "Resolved Escalated Decisions" section above + propagated through Story Conventions section (binding for all 76 stories).

### Architecture Step 5 Cross-Surface Invariants — Story-Level Compliance

The 12 cross-surface invariants from architecture are honored across stories:
- **[INVARIANT 1]** schemas master at `contracts/` — Stories 1.10, 1.13 edit ONLY the JSON Schema masters; regen via `pnpm --filter @warden/contracts build`.
- **[INVARIANT 2]** web sole writer of `users/{uid}` — Story 1.14 firestore.rules denies client writes; Story 1.15 production-deploys.
- **[INVARIANT 3]** on-device-only video processing — Story 2.2 wrapper allowlist; Story 8.2 errorReporting bans user content.
- **[INVARIANT 4]** self-namespace import in `apps/web/src/lib/stripe/webhooks.ts` — Stories 1.12, 1.17 preserve the pattern.
- **[INVARIANT 5]** Stripe metadata required — preserved by carry-forward (legacy Web Epic 4 COMPLETE).
- **[INVARIANT 6]** Stripe dahlia API event nesting — Story 1.3 Stripe pin bump preserves; Story 1.12 new schema mirrors `parent.subscription_details.subscription`.
- **[INVARIANT 7]** Reader-App banned imports / strings — Story 2.1 implementation; Story 8.1 i18n bundle scan.
- **[INVARIANT 8]** `EXPO_PUBLIC_AUTH_BYPASS` deny in release — Story 2.6 explicit gate scan.
- **[INVARIANT 9]** `.npmrc` `node-linker=hoisted` — preserved across all stories (legacy lock).
- **[INVARIANT 10]** `react-native-mmkv` v3 pin — preserved (legacy lock).
- **[INVARIANT 11]** workspace deps via `workspace:*` — preserved across all stories.
- **[INVARIANT 12]** Conventional Commits with scopes — UX §6.5 story prefix recommendations align with the scope list (`feat(mobile):`, `feat(dashboard):`, `feat(auth):`, `feat(landing):`, `feat(layout):`, `feat(infra):`).

### Final Readiness Assessment

**Status: READY FOR DEVELOPMENT.**

**Confidence Level: High.**

**Key strengths:**
- Every PRD FR (69) and NFR (41) is accounted for with explicit story coverage or legacy-verified-via-launch-checklist attribution.
- Every architecture decision (AR-1..AR-12, AR-SPIKE), every brownfield triage item (BF-1..BF-6), every CI/CD addition (CI-1..CI-3), every UX design requirement (UX-DR1..UX-DR18) routes to a specific story.
- All 10 escalated decisions resolved inline; rationale documented; not deferred.
- Dependency DAG is acyclic; no forward references; cross-epic dependencies are explicit.
- The 12 cross-surface invariants are honored at story level.
- The 18-item UX §6.5 implementation surface routes to feature-folder boundaries (not lumped as one technical-layer epic).

**Known unknowns (acknowledged):**
- Story 1.1 (AR-SPIKE) outcome conditions downstream story shape (mobile-AUTO-SLICE-* FRs + Card View + Cinema Mode story scope contingent on ladder rung). Sprint 3 commits scope POST-spike.
- Story 10.4 (Stripe Production Activation) is BLOCKED on Root providing company number — external dependency not in Stephane's control.
- Demand evidence (Story 10.5) is non-V1-blocking but PRD-mandated to capture before launch.

**Recommendations for Sprint Planning (next phase, `bmad-sprint-planning`):**
1. Sequence Sprint 3 work-stream parallelization per architecture's Decision Impact Analysis (Story 1.1 spike gates everything; Stories 1.2/1.3 parallel; Decision #1/#6/#9 triple as coordinated PR; etc.).
2. Apply the 80/20 maintenance-vs-V1-stories capacity split per Decision #ES-10.
3. Target Sprint 3 commit only AFTER Epic 0 audit closes (Decision #ES-3).
4. Reserve a parallel demand-evidence sprint for Story 10.5 capture (non-blocking but critical for re-baselining post-V1 reference targets).
