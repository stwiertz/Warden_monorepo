---
stepsCompleted: [step-01-document-discovery, step-02-prd-analysis, step-03-epic-coverage-validation, step-04-ux-alignment, step-05-epic-quality-review, step-06-final-assessment]
status: complete
completedAt: '2026-05-09'
assessor: Claude (bmad-check-implementation-readiness skill)
verdict: READY_WITH_MINOR_AMENDMENTS
filesAssessed:
  prd: _bmad-output/prd.md
  architecture: _bmad-output/architecture.md
  ux: _bmad-output/ux-design.md
  epicsAndStories: _bmad-output/epics-and-stories.md
supportingContext:
  - _bmad-output/product-brief.md
  - _bmad-output/product-brief-distillate.md
  - _bmad-output/legacy/distillate/
  - docs/
---

# Implementation Readiness Assessment Report

**Date:** 2026-05-09
**Project:** Warden_monorepo

## Document Inventory

| Type | File | Status |
|---|---|---|
| PRD | `_bmad-output/prd.md` | found |
| Architecture | `_bmad-output/architecture.md` | found |
| UX Design | `_bmad-output/ux-design.md` | found |
| Epics & Stories | `_bmad-output/epics-and-stories.md` | found |
| Product Brief (input) | `_bmad-output/product-brief.md` (+ distillate) | found |

**Note on layout:** Phase-6 unified docs live flat under `_bmad-output/`, not under the configured `planning-artifacts/` subdirectory. No duplicates, no missing required documents.

## PRD Analysis

### Functional Requirements (68 FRs total)

**Mobile (`apps/mobile`) — 32 FRs**

*Authentication & Entitlement (6)*
- mobile-AUTH-001: Sign in via Google or email/password (creds issued by web Stripe flow). *(J1, J6)*
- mobile-AUTH-002: Validate active entitlement on first foreground + on resume from Stripe Customer Portal round-trip. *(J1, J7)*
- mobile-AUTH-003: Reject login (show "subscription required" + deep-link) for any state ≠ `paid`/`offline-grace ≤30d`. *(J8)*
- mobile-AUTH-004: 30-day MMKV entitlement cache; force re-auth on day 31. *(J9)*
- mobile-AUTH-005: Preserve user-generated session data across entitlement transitions (lapse → resubscribe). *(J8)*
- mobile-AUTH-006: Payment-failure warning banner + deep-link when state is `payment-failed`. *(J7)*

*Session Import & Auto-Slicing (6)*
- mobile-IMPORT-001: Import recorded gameplay video from gallery/file system. *(J1, J6)*
- mobile-IMPORT-002: Reject unsupported codec/container with actionable error.
- mobile-AUTO-SLICE-001: Auto-slice into per-round Cards via on-device round-boundary detection. **Load-bearing on JSI.** *(J1, J6)*
- mobile-AUTO-SLICE-002: Auto-identify map per round via on-device perceptual hash vs `map_config.json`. **Load-bearing on JSI.** *(J1, J6)*
- mobile-AUTO-SLICE-003: Mark `map_name = "unknown"` below recognition threshold; navigation/Cinema still work. *(J3)*
- mobile-AUTO-SLICE-004: Auto-remove lobby footage from Card View. *(J1)*

*Card View & Triage (5)*
- mobile-CARD-001: Grid of Cards with adaptive column count.
- mobile-CARD-002: Sort temporal/orange-win/blue-win/closest-map; persist across sessions.
- mobile-CARD-003: Tap Card → Cinema Mode for that round.
- mobile-CARD-004: Cold-start offers "Resume last review" or "Import new session"; never blank.
- mobile-CARD-005: Auto-slice-missed rounds reachable via Cinema Mode timeline. *(J3)*

*Cinema Mode (5)*
- mobile-CINEMA-001: Immersive video player; reveal-on-tap controls; auto-hide. *(J1, J4)*
- mobile-CINEMA-002: View-mode switch (Full/Minimap/Minimap+HUD) via segmented control AND double-tap top-left. *(J1, J4)*
- mobile-CINEMA-003: Default view = Full when `map_name = "unknown"`. *(J3)*
- mobile-CINEMA-004: Persist last-used view-mode preference. *(J4)*
- mobile-CINEMA-005: Next/Previous round buttons (no swipe — UX rejects swipe to avoid scrub conflict).

*Clip Creation & Voice Annotation (5)*
- mobile-CLIP-001: 30-second clip region centered on playback position; bracket-handle refinement. *(J1)*
- mobile-CLIP-002: Manual clip creation from any timeline point (no Card required). *(J3)*
- mobile-CLIP-003: 3-slot voice annotation (before/during/after) — independent and optional. *(J1, J2, J5)*
- mobile-CLIP-004: Re-record (overwrite) voice slot. *(J2)*
- mobile-CLIP-005: Preview clip with voice annotations before exporting.

*Export & Share (4)*
- mobile-EXPORT-001: On-device FFmpeg encode → standalone MP4 (no cloud encode path). *(J1)*
- mobile-EXPORT-002: Two encode tiers (Mobile, HD).
- mobile-EXPORT-003: OS share sheet dispatch on encode completion. *(J1)*
- mobile-EXPORT-004: MP4 = vanilla H.264/AAC, Discord-inline-playable. *(J5 — distribution moat)*

*Auto-save & Crash Recovery (2)*
- mobile-AUTOSAVE-001: Silent auto-save of clip-creation state. *(J2)*
- mobile-AUTOSAVE-002: Resume Cinema Mode at exact frame; preserve clip region + in-progress voice. *(J2)*

**Web (`apps/web`) — 16 FRs**

*Landing & Pricing (4)*
- web-LANDING-001: Landing `/` with FR-locked hero + single CTA → `/pricing`.
- web-LANDING-002: SSR HTML for crawlers + Discord card preview.
- web-PRICING-001: `/pricing` with 2 plan cards (€7.99/mo, €79.90/yr) + Stripe coupon URL param.
- web-PRICING-002: Auth modal (Google + Email/Password) before Checkout.

*Authentication & Checkout (3)*
- web-AUTH-001: Sign-in/register via Google OAuth or email/password through Firebase Auth.
- web-CHECKOUT-001: Stripe Checkout full-page redirect with selected plan + coupon + FR deferred-billing copy.
- web-CHECKOUT-002: Return to `/dashboard?success=1` with status badge.

*Dashboard (5)*
- web-DASHBOARD-001: Protected `/dashboard` (server-side auth + fresh client Firestore reads, no `onSnapshot`); shows email, plan, status badge, next payment, "Manage Subscription" deep-link.
- web-DASHBOARD-002: Payment-failure warning banner + "Update payment method" deep-link.
- web-DASHBOARD-003: "Canceling" badge + "Resubscribe" CTA when cancel-at-period-end.
- web-DASHBOARD-004: Cancellation confirmation dialog — no exit survey, no guilt-trip.
- web-DASHBOARD-005: "No active subscription" empty state with link to `/pricing`.

*Webhook Processing (3)*
- web-WEBHOOK-001: Ingest Stripe webhooks (`invoice.payment_succeeded/failed`, `customer.subscription.updated/deleted`, `checkout.session.completed`) with signature verification.
- web-WEBHOOK-002: Dual-strategy idempotency (event-ID dedup + business-state observation).
- web-WEBHOOK-003: Server-only `users/{uid}` writes; client writes denied by Firestore Security Rules.

*Analytics (1)*
- web-ANALYTICS-001: Firebase Analytics for Visit / CheckoutStart / CheckoutComplete / Coupon-applied / Coupon-Retained-past-deferred-billing.

**Tooling (`apps/tooling`) — 12 FRs**

- tooling-ROUND-DETECT-001: Round-boundary detection (BSD or `game_detector`) → per-round PNGs (start/end/score). *(J10)*
- tooling-ROUND-DETECT-002: Miss-report listing missed-end / missed-start windows.
- tooling-LABEL-001: Frame labeler — score frames into per-map dirs; co-export paired start/end frames. *(J10)*
- tooling-LABEL-002: `MAP_LABELS` (14 canonical maps) imported from `tools/frame_labeler.py:19-34`.
- tooling-HASH-001: `hash_comparator`/`map_config_generator` → `map_config.json` with per-map reference hashes. *(J10)*
- tooling-HASH-002: Emitted `map_config.json` includes `schema_version: 1` + pipeline params (`text_anchor_width`, `threshold_hash`, `recognition_threshold`).
- tooling-VALIDATE-001: `hash_validator` → `accuracy_report.json`. *(J10)*
- tooling-VALIDATE-002: `hash_validator` reuses pipeline params from `map_config.json` (not `config.yaml`).
- tooling-WARDEN-001: `warden_analyzer` end-to-end → score frames + `rounds.json`.
- tooling-TUI-001: TUI launcher (`wardentooling.py`) for interactive workflow.
- tooling-TUI-002: TUI re-run-with-same-args (via `.warden_last_run.json`).
- tooling-SCHEMA-001: jsonschema validation of `map_config.json` against `contracts/map-config.schema.json` strict.

**Cross-Surface — 8 FRs**

- cross-ENTITLEMENT-001: All surfaces consume the same six-state entitlement model.
- cross-ENTITLEMENT-002: Web is sole writer of `users/{uid}` entitlement; mobile reads only.
- cross-ACTIVATION-001: Mobile emits `activation_timer_started` (T0) + `activation_timer_completed` (T1, dual: share-dispatch OR Cinema+view-mode-toggled).
- cross-ACTIVATION-002: Activation telemetry payloads = timestamps + event names only (no frame/audio data).
- cross-SCHEMA-001: `map-config.schema.json` first-class under `packages/contracts/`; strict on web (Zod build-time) AND tooling (jsonschema runtime/CI).
- cross-SCHEMA-002: `user-doc.schema.json` duplication resolved via single canonical schema (escalated to architecture).
- cross-READER-APP-001: Mobile build artifacts contain zero monetization-surface artifacts (CI-gated import + transitive-dep + string scans).
- cross-MAP-CONFIG-DELIVERY-001: Mobile consumes `map_config.json` at runtime. **Delivery mechanism (Firestore vs Metro vs hybrid) escalated to architecture.**

### Non-Functional Requirements (41 NFRs total)

**Performance (10)** — PERF-001 (activation ≤300s), PERF-002 (auto-slice ≤5% of source), PERF-003 (view-mode toggle ≤100ms), PERF-004 (Cinema cold-start ≤1.5s), PERF-005 (clip encode ≤2× duration Mobile-tier), PERF-006 (web FCP ≤1.5s), PERF-007 (LCP ≤2.5s, CLS ≤0.1, TTI ≤3s), PERF-008 (webhook p95 ≤1s), PERF-009 (BSD ≤1× source duration), PERF-010 (reference-device floor — TBD per architecture spike).

**Security (7)** — SEC-001 (webhook signature verification), SEC-002 (server-only Firestore writes via rules), SEC-003 (Firestore rules deployed pre-V1 — V1-blocking), SEC-004 (no card data in mobile builds), SEC-005 (Firebase Auth best practices, HttpOnly cookies on dashboard), SEC-006 (dual-strategy idempotency), SEC-007 (mobile dependency allowlist enforces no-content-transmission).

**Reliability (6)** — REL-001 (mobile session survives crash/force-close/restart), REL-002 (30-day offline functionality), REL-003 (webhook delays ≤1h tolerated), REL-004 (entitlement transitions reach mobile within 5min), REL-005 (deterministic tooling outputs), REL-006 (map ID accuracy ≥95% on unseen; round-boundary TBD).

**Accessibility (6)** — A11Y-001 (web WCAG 2.1 A; AA contrast), A11Y-002 (keyboard nav + 2px focus + skip link), A11Y-003 (text+color status indicators on web), A11Y-004 (web `prefers-reduced-motion`), A11Y-005 (mobile contrast ~17:1; touch targets ≥44px), A11Y-006 (mobile shape/icon as primary state signal — never color alone).

**Privacy (5)** — PRIV-001 (no video/audio/voice/derived data crosses any wire to Warden server), PRIV-002 (mobile telemetry: timestamps + event names + entitlement markers only), PRIV-003 (local clip deletion removes MP4 + voice + intermediates — GDPR auto-satisfied), PRIV-004 (Stripe webhook logs: Stripe IDs only, no card primitives), PRIV-005 (third-party voice = recording-user controller responsibility).

**Observability (4)** — OBS-001 (mobile activation chain telemetry), OBS-002 (web funnel telemetry), OBS-003 (mobile crash reports exclude user content), OBS-004 (web webhook structured logs — no PII).

**Internationalization (3)** — I18N-001 (mobile FR-locked V1, no language picker), I18N-002 (web English-locked V1 except FR-locked hero + deferred-billing copy), I18N-003 (mobile error/status text in French — no English fallthroughs).

### Additional Requirements / Constraints

**V1-load-bearing technical milestones (Section 2 Technical Success):**
1. OpenCV JSI binding ships as **real binding** (not tested-via-injection stub).
2. Cross-language schema-contract conformance.
3. Stripe webhook idempotency regression coverage.
4. Reader-App contract — zero monetization-surface artifacts in any mobile build.
5. 30-day offline auth-cache.

**Brownfield triage backlog (Section 5 Risk #4 disposition):**
- V1-blocking: Firestore Security Rules deploy (Story 7.1); Firebase Auth E2E + PlanCta hydration (Story 7.2); Firebase v12 RN auth migration (Decision #5); `schema_version: 1` field at next regeneration.
- Architecture-owned: Stripe API version pin (default-to-bump); Foreground Service Android decision (binds before Sprint 3).
- V2 backlog: Vitest parallelism flake (V1: serial-mode workaround).

**Out-of-scope V1:** Admin/Operations UI; Support workflow tooling; external API consumer; iOS; Discord OAuth; coupon admin UI; OCR; team/group billing; self-serve account deletion; churn survey; vertical/multi-view export; review-import; export queue background encoding.

**Open architecture-escalations (PRD does not pre-decide):**
- Decision #1: `user-doc.schema.json` duplication resolution path.
- Decision #2: `map_config.json` runtime delivery (Firestore vs Metro vs hybrid).
- Reference-device performance floor (PERF-010) — pre-V1 spike.
- Round-boundary detection accuracy floor (REL-006) — TBD by spike.
- Foreground Service Android implementation choice.
- `payment-failed` grace-period duration.
- Crash-reporting SDK choice (OBS-003).
- Oncall mechanism for webhook >1h failures (REL-003).

### PRD Completeness Assessment

The PRD is **dense, well-structured, and traceability-aware**. Strengths:
- Every FR has a journey-trace (J1–J10) or PRD-section anchor.
- Surface-prefixed FR IDs (`mobile-`, `web-`, `tooling-`, `cross-`) make epic mapping mechanical.
- Capability clusters in the Journey Requirements Summary table (lines 477–490) are pre-mapped to FR sections, which dramatically simplifies coverage validation downstream.
- The Reader-App contract, on-device-only contract, and dual-T1 activation telemetry are stated as **structural** (not phased) — clear veto points for any epic that violates them.
- Items deliberately escalated to architecture are flagged in-place, not buried — easy to verify in step 4.

Concerns to carry into coverage validation:
- **Decision #2 (map_config delivery)** is unresolved at PRD; architecture must answer it. If the architecture document does not, this is a step-4 cross-doc gap.
- **PERF-010 (reference-device floor)** is stated as TBD — architecture must publish a number. Same gap risk.
- **REL-006 round-boundary accuracy** is TBD — architecture spike must bind it.
- The **dual-T1 activation telemetry** (cross-ACTIVATION-001) is novel; architecture and stories must both implement the dual path or it lives only on paper.
- **cross-MAP-CONFIG-DELIVERY-001, cross-SCHEMA-002** depend on architecture decisions before any story can be picked up.

**FR count reconciliation:** the PRD has **6 AUTH + 6 IMPORT/SLICE + 5 CARD + 5 CINEMA + 5 CLIP + 4 EXPORT + 2 AUTOSAVE = 33 mobile FRs**. The epics doc's 33-mobile / 16-web / 12-tooling / 8-cross / **69 total** count is correct. NFR total of 41 stands.

## Epic Coverage Validation

### Coverage Matrix (independently verified against PRD §9 + §10)

**Mobile (33/33 FRs covered):**

| FR | Epic / Story | Verdict |
|---|---|---|
| mobile-AUTH-001 | Epic 3 / Story 3.7 (LoginScreen entitlement gate) | ✓ Covered |
| mobile-AUTH-002 | Epic 3 / Story 3.8 (foreground re-fetch) | ✓ Covered |
| mobile-AUTH-003 | Epic 3 / Story 3.3 (SubscriptionRequiredScreen) | ✓ Covered |
| mobile-AUTH-004 | Epic 3 / Story 3.9 (30-day MMKV + day-31 expiry) | ✓ Covered |
| mobile-AUTH-005 | Epic 3 / Story 3.10 (lapse → resubscribe preserves data) | ✓ Covered |
| mobile-AUTH-006 | Epic 3 / Story 3.2 (EntitlementBanner) | ✓ Covered |
| mobile-IMPORT-001/002 | Epic 0 (Sprint 2.5 Story 2.1 — DONE legacy) | ✓ Covered (audit-pending) |
| mobile-AUTO-SLICE-001/002 | Epic 1 spike-gated (Story 1.1) + Epic 0 (legacy 7.5) | ✓ Covered (spike-conditional) |
| mobile-AUTO-SLICE-003 | Epic 0 (Sprint 2.5 Story 2.5 unknown-map) | ✓ Covered |
| mobile-AUTO-SLICE-004 | Epic 0 (legacy 7.5 lobby exclusion) | ✓ Covered |
| mobile-CARD-001/002/004 | Epic 5 / Story 5.1 (adaptive grid + sort persistence + cold-start) | ✓ Covered |
| mobile-CARD-003 | Epic 5 / Story 5.2 (Card→Cinema tap) | ✓ Covered |
| mobile-CARD-005 | Epic 5 / Story 5.3 (Cards/Timeline toggle, UX-DR7) | ✓ Covered |
| mobile-CINEMA-001 | Epic 5 / Story 5.4 (immersive review + reveal-on-tap) | ✓ Covered |
| mobile-CINEMA-002 | Epic 5 / Story 5.5 (view-mode toggle ≤100ms, no player swap) | ✓ Covered |
| mobile-CINEMA-003 | Epic 5 / Story 5.6 (default Full when unknown) | ✓ Covered |
| mobile-CINEMA-004 | Epic 5 / Story 5.7 (view-mode preference persistence) | ✓ Covered |
| mobile-CINEMA-005 | Epic 5 / Story 5.8 (Next/Previous explicit) | ✓ Covered |
| mobile-CLIP-001 | Epic 6 / Story 6.1 (30s clip + bracket 5–60s) | ✓ Covered |
| mobile-CLIP-002 | Epic 6 / Story 6.2 (manual clip from timeline) | ✓ Covered |
| mobile-CLIP-003 | Epic 6 / Story 6.3 (3-slot voice) | ✓ Covered |
| mobile-CLIP-004 | Epic 6 / Story 6.4 (re-record overwrite) | ✓ Covered |
| mobile-CLIP-005 | Epic 6 / Story 6.5 (preview before encode) | ✓ Covered |
| mobile-EXPORT-001/002 | Epic 6 / Story 6.6 (FFmpeg encode + Mobile/HD tiers) | ✓ Covered |
| mobile-EXPORT-003 | Epic 6 / Story 6.7 (OS share-sheet dispatch) | ✓ Covered |
| mobile-EXPORT-004 | Epic 6 / Story 6.8 (H.264/AAC Discord-inline) | ✓ Covered |
| mobile-AUTOSAVE-001 | Epic 7 / Story 7.1 (silent auto-save) | ✓ Covered |
| mobile-AUTOSAVE-002 | Epic 7 / Stories 7.2 + 7.3 (resume + J2 manual E2E) | ✓ Covered |

**Web (16/16 FRs covered):**

| FR | Epic / Story | Verdict |
|---|---|---|
| web-LANDING-001 | Legacy Web Story 1.2 DONE; verified via Epic 10 J1 trace (Story 1.9) | ✓ Covered (legacy) |
| web-LANDING-002 | Epic 4 / Stories 4.2 (OG image) + UX-DR14 layout meta | ✓ Covered |
| web-PRICING-001 | Legacy Web Stories 3.1+3.3 DONE; J1 trace | ✓ Covered (legacy) |
| web-PRICING-002 | Legacy Web Story 3.2 DONE; J1 trace | ✓ Covered (legacy) |
| web-AUTH-001 | Legacy Web Stories 2.1–2.4 DONE + Epic 4 / Story 4.4 (FU-5 password reset) | ✓ Covered |
| web-CHECKOUT-001/002 | Legacy Web Story 3.2 DONE; J1 trace | ✓ Covered (legacy) |
| web-DASHBOARD-001 | Legacy Web Stories 5.1+5.2 DONE per Sprint Change Proposal 2026-04-16 | ✓ Covered (legacy) |
| web-DASHBOARD-002 | Epic 3 / Story 3.5 (PaymentWarning composition) | ✓ Covered |
| web-DASHBOARD-003 | Epic 3 / Story 3.6 (Canceling badge + Resubscribe CTA) | ✓ Covered |
| web-DASHBOARD-004 | Epic 4 / Story 4.5 (CancelDialog anti-dark-pattern) | ✓ Covered |
| web-DASHBOARD-005 | Epic 4 / Story 4.6 (EmptySubscription) | ✓ Covered |
| web-WEBHOOK-001/002 | Epic 1 / Stories 1.12 (trialing handler) + 1.17 (idempotency regression) | ✓ Covered |
| web-WEBHOOK-003 | Epic 1 / Stories 1.14 (firestore.rules) + 1.15 (prod deploy) | ✓ Covered |
| web-ANALYTICS-001 | Epic 4 / Story 4.8 (funnel events + Coupon-Retained server-side) | ✓ Covered |

**Tooling (12/12 FRs covered):**

| FR | Epic / Story | Verdict |
|---|---|---|
| tooling-ROUND-DETECT-001/002 | Epic 9 (legacy reference impls) + Story 9.2 real-footage AC | ✓ Covered (legacy + Sprint 3 hardening) |
| tooling-LABEL-001/002 | Legacy COMPLETE; verified via 14-canonical-maps reconciliation | ✓ Covered (legacy) |
| tooling-HASH-001 | Epic 9 (legacy hash_comparator + map_config_generator) | ✓ Covered (legacy) |
| tooling-HASH-002 | Epic 9 / Story 9.1 (schema_version: 1 add) | ✓ Covered |
| tooling-VALIDATE-001 | Epic 9 / Story 9.3 (4-maps regression) | ✓ Covered |
| tooling-VALIDATE-002 | Epic 9 / Story 9.4 (jsonschema strict; pipeline-param parity) | ✓ Covered |
| tooling-WARDEN-001 | Epic 9 / Story 9.2 (Tool 5 real-footage AC validation) | ✓ Covered |
| tooling-TUI-001/002 | Legacy COMPLETE; verified via J10 path | ✓ Covered (legacy) |
| tooling-SCHEMA-001 | Epic 9 / Story 9.4 (jsonschema strict against contracts) | ✓ Covered |

**Cross-surface (8/8 FRs covered):**

| FR | Epic / Story | Verdict |
|---|---|---|
| cross-ENTITLEMENT-001 | Epic 3 / Story 3.1 (deriveEntitlementState + 6-state regression) | ✓ Covered |
| cross-ENTITLEMENT-002 | Epic 1 / Stories 1.14 + 1.15 (firestore.rules deny + deploy) | ✓ Covered |
| cross-ACTIVATION-001 | Epic 2 / Stories 2.3 (T0) + 2.4 (T1-coach) + 2.5 (T1-active-player) | ✓ Covered |
| cross-ACTIVATION-002 | Epic 2 / Story 2.2 (wrapper allowlist + dev/test/prod modes) | ✓ Covered |
| cross-SCHEMA-001 | Epic 1 / Story 1.13 + Epic 9 / Story 9.4 (Zod build-time + jsonschema runtime) | ✓ Covered |
| cross-SCHEMA-002 | Epic 1 / Stories 1.10 (tighten user-doc) + 1.11 (web wire) + 1.12 (trialing handler) | ✓ Covered |
| cross-READER-APP-001 | Epic 2 / Story 2.1 (gate impl) + 2.6 (release-config bypass scan) + UX-DR17 (regex narrow per FU-4) | ✓ Covered |
| cross-MAP-CONFIG-DELIVERY-001 | Epic 1 / Story 1.13 (hybrid bundled-Metro + Firestore overlay) | ✓ Covered |

### NFR Coverage (41/41)

| Category | Count | Coverage status |
|---|---|---|
| Performance (PERF-001..010) | 10/10 | All routed; PERF-002/003/004/005/010 spike-bound (Story 1.1) |
| Security (SEC-001..007) | 7/7 | All routed; SEC-003 V1-blocking (Story 1.15) |
| Reliability (REL-001..006) | 6/6 | All routed; REL-006 spike-bound + Epic 9 regression |
| Accessibility (A11Y-001..006) | 6/6 | All routed; A11Y-001 contrast re-verify gated by token bump (Story 4.1) |
| Privacy (PRIV-001..005) | 5/5 | All routed; PRIV-003 covered by AR-12 cascade (Story 6.9) |
| Observability (OBS-001..004) | 4/4 | All routed; OBS-003 manual fallback via mailto (Story 8.2) — V1 has no crash SDK |
| Internationalization (I18N-001..003) | 3/3 | All routed; I18N-001/003 via Story 8.1 ~150-string bundle |

### Coverage Statistics

- **Total PRD FRs:** 69 (33 mobile + 16 web + 12 tooling + 8 cross-surface)
- **FRs covered in epics:** 69 (100%)
- **Coverage percentage:** 100%
- **Total PRD NFRs:** 41
- **NFRs covered in epics:** 41 (100%)
- **NFR coverage percentage:** 100%
- **Stories total:** 76 (Epic 0: 2, Epic 1: 18, Epic 2: 6, Epic 3: 10, Epic 4: 8, Epic 5: 8, Epic 6: 9, Epic 7: 3, Epic 8: 3, Epic 9: 4, Epic 10: 5)
- **Architecture work items (AR-1..AR-12 + AR-SPIKE):** all routed
- **Brownfield triage items (BF-1..BF-6):** all routed
- **CI/CD additions (CI-1..CI-3):** all routed (CI-1/3 V0 fallback in Epic 1; CI-2 in Epic 10)
- **UX-DR items (UX-DR1..UX-DR18):** all routed

### Missing Requirements — None Identified

No PRD FR or NFR is uncovered. The legacy-carry-forward subset (web 7 FRs + tooling 8 FRs) is verified transitively via:
1. Sprint Change Proposal 2026-04-16 already RESOLVED the Web Epic 5 conflict (custom UI delegated to Stripe Customer Portal).
2. Epic 1 Story 1.9 (J1–J10 manual E2E test) traces the entire web subscribe-and-manage funnel end-to-end on dev build.
3. Epic 10 Story 10.1 row L9 (J8 cancel flow) and L20 (Stripe Production Activation) verify on production.

### Coverage-validation Findings (gaps and risks worth flagging downstream)

These are not "missing FRs" but verification posture caveats that should not be ignored at sprint commit:

1. **Sprint 2.5 audit not yet executed.** Epic 0 Story 0.1 produces the per-story conflict-audit table, but the table itself does not yet exist as an artifact. Until it does, the disposition of legacy mobile Sprint 2.5 stories 2.2/2.5/2.6/2.7/7.1/7.2/7.3/7.4/7.5/7.6 is unknown. Mobile-IMPORT-* and mobile-AUTO-SLICE-003/004 disposition rests on this audit. **Decision #ES-3 binds Story 0.1 to gate Sprint 3 commit** — alignment is correct, but there is no story-coverage gap yet because the audit hasn't run.

2. **Spike-conditional FRs.** mobile-AUTO-SLICE-001/002 are explicitly conditional on Story 1.1 spike outcome. Under rung-3 (auto-slice deferred to V2), these FRs become V2-deferred and Card View collapses to manual-clip-only — Story 5.3 is engineered for this fallback but **the rung-3 path has not been pre-walked end-to-end for UX coherence in Card View / Cinema Mode**. If rung-3 fires, sprint planning must re-validate that the manual-clip-only V1 still hits the < 5min activation target (PERF-001) — which is non-trivial. Worth flagging to sprint planning as a contingent re-baselining task.

3. **Web carry-forward leans on transitive verification.** 7 web FRs (LANDING-001, PRICING-001/002, AUTH-001 base, CHECKOUT-001/002, DASHBOARD-001) have no Sprint 3 story explicitly testing them; they're verified via Story 1.9 J1 manual E2E + Epic 10 production smoke. After Story 4.1 token bump (#FF6B00) and Story 4.7 copy embedding, **a regression in any landing/pricing/checkout copy or layout would only surface during 1.9 manual run** — not at PR time. Consider adding a Vitest snapshot test for the carry-forward FRs as a hardening measure (post-V1 polish).

4. **Demand evidence (Story 10.5) is non-V1-blocking but PRD-mandated.** PRD §2 explicitly requires interview count + waitlist depth + WTP validation **before V1 launch** — Story 10.5 captures this but the launch checklist marks L21 as "non-blocking." **Latent contradiction:** PRD says "captured before V1 launch"; epics-and-stories says "non-V1-blocking." If launch ships before evidence is captured, sprint planning is ignoring a PRD demand. Worth raising at the next planning gate so the team makes a deliberate trade-off rather than a quiet one.

5. **External blocker on Story 10.4 (Stripe Production Activation).** Carryover from legacy Web Story 7.4 — needs company number from Root. If unblocked, V1 launches; if not, Stripe Checkout cannot go live and V1 is materially incomplete regardless of every other story passing. Track separately as a risk, not a gap.

## UX Alignment Assessment

### UX Document Status

**Found.** `_bmad-output/ux-design.md` (2071 lines, status: complete-locked 2026-05-07).

### UX ↔ PRD Alignment

✅ **Personas inherited verbatim.** Coach Thomas / Active Player Maxime / Passive Player Lucas; UX §1.1 references PRD §4 as bound and does not re-derive.
✅ **Information architecture inherited.** UX §1.2 enumerates 8 mobile screens + 4 web routes — exactly matches PRD §3 MVP + §7 per-surface requirements.
✅ **FR-locked French insertions preserved verbatim** in UX §4.2: hero "*Progresser plus vite en investissant moins de temps.*", deferred-billing "*Vous ne serez pas débité avant le [date]*", savings "*économisez 2 mois*".
✅ **No-free-tier contract honored.** UX §1.7 lists "Reader-App structural contract" + "Pricing positioning (€7.99 / €79.90 — web only)" as PRD-locked / out of UX scope; UX §4.1 mobile copy deck explicitly excludes pricing strings; UX §2.5 lapsed/payment-failed/signed-out copy contains zero euro signs.
✅ **Six-state entitlement model honored.** UX §2.5 designs visual treatment for all six states (`paid` / `lapsed` / `offline-grace ≤30d` / `payment-failed` / `multi-device` / `signed-out`) — semantics unchanged from PRD §2.
✅ **Activation T0/T1 dual-path UI moments confirmed present.** UX §2.1.2 (view-mode toggle for active-player T1) + §4.1.9 (share-sheet for coach T1) — matches PRD `cross-ACTIVATION-001` dual-T1.
✅ **Anti-dark-pattern policy honored.** UX §3.2.3 cancellation dialog explicitly enumerates "NO exit survey, NO guilt-trip, NO double-confirm, NO countdown timer, NO retention offer" — directly aligned with PRD J8.
✅ **14 canonical maps inherited.** UX defers to PRD §5 maps reconciliation + tooling MAP_LABELS.

**No PRD requirement is contradicted by UX. No UX requirement is unsupported by PRD.**

### UX ↔ Architecture Alignment

✅ **Token system aligned to architecture's tiering.** UX §1.6 confirms HUD primitives at `apps/mobile/src/shared/components/hud/` (architecture-bound) + 7 shadcn primitives at `apps/web/src/components/ui/` (architecture-bound).
✅ **Architecture's `paymentFailedGracePeriodMs: 7d` default honored.** UX §2.5.3 references this as the timing for `payment-failed → lapsed` transition.
✅ **Foreground Service plugin notification copy locked at "Analyse en cours…"** (UX §1.3 + §4.1.6) — matches architecture decision in epics-and-stories Story 1.2.
✅ **PERF-003 ≤100ms via no-player-swap pattern.** UX §2.1 explicitly references "crop/style change on the same `expo-av` source per architecture, no player swap."
✅ **JSI binding spike outcome inheritance.** UX §6.3 explicitly accepts "If spike returns rung 3 (no auto-slice), §2.4 manual-clip flow becomes the only V1 clip-creation path; CardView toggle defaults to TIMELINE. UX is shipped-ready for either outcome." — clean ladder-rung accommodation.
✅ **Reader-App regex narrow (FU-4) flows into architecture amendment.** UX §4.1.10 + §6.5 specify the regex change in `.github/workflows/ci.yml` + `apps/mobile/scripts/reader-app-gate.sh` — Epic 2 Story 2.1 + UX-DR17 carry this through.
✅ **Activation telemetry contract.** UX §6.2.3 confirms T1-coach + T1-active-player UI moments are present; architecture's wrapper-allowlist enforcement is unaffected.

**No architecture decision contradicted; no UX requirement unsupported by architecture.**

### UX ↔ Epics-and-Stories Alignment

The epics-and-stories doc routes the UX surface via 18 explicit UX-DR items (UX-DR1..UX-DR18) plus all 8 follow-ups (FU-1..FU-8):

| UX item | Story coverage | Verdict |
|---|---|---|
| UX-DR1 (EntitlementBanner) | Epic 3 / Story 3.2 | ✓ Covered |
| UX-DR2 (SubscriptionRequiredScreen) | Epic 3 / Story 3.3 | ✓ Covered |
| UX-DR3 (OfflineIndicator) | Epic 3 / Story 3.4 | ✓ Covered |
| UX-DR4 (FR i18n bundle ~150 strings) | Epic 8 / Story 8.1 | ✓ Covered |
| UX-DR5 (errorReporting mailto) | Epic 8 / Story 8.2 | ✓ Covered |
| UX-DR6 (Account Aide section) | Epic 8 / Story 8.3 | ✓ Covered |
| UX-DR7 (Cards/Timeline toggle, Decision #UX-14) | Epic 5 / Story 5.3 | ✓ Covered |
| UX-DR8 (PaymentWarning web) | Epic 3 / Story 3.5 | ✓ Covered |
| UX-DR9 (CancelDialog anti-dark-pattern) | Epic 4 / Story 4.5 | ✓ Covered |
| UX-DR10 (EmptySubscription) | Epic 4 / Story 4.6 | ✓ Covered |
| UX-DR11 (PasswordResetForm — FU-5) | Epic 4 / Story 4.4 | ✓ Covered |
| UX-DR12 (sign-in `?passwordReset=1`) | Epic 4 / Story 4.4 | ✓ Covered |
| UX-DR13 (OG image asset 1200×630) | Epic 4 / Story 4.2 | ✓ Covered |
| UX-DR14 (layout.tsx OG/Twitter meta) | Epic 4 / Story 4.2 | ✓ Covered |
| UX-DR15 (Footer "Get help" link — FU-1) | Epic 4 / Story 4.3 | ✓ Covered |
| UX-DR16 (web token bump #FF6B00 — FU-3) | Epic 4 / Story 4.1 | ✓ Covered |
| UX-DR17 (Reader-App regex narrow — FU-4) | Epic 2 / Story 2.1 | ✓ Covered |
| UX-DR18 (web English copy + FR insertions) | Epic 4 / Story 4.7 | ✓ Covered |

All 8 follow-ups (FU-1..FU-8) are explicitly carried into stories (FU-7 tip cadence is the only one that lives as a UX-internal lock without an explicit story; see Warning #1 below).

### Alignment Issues — Minor / Implementation-Detail Gaps

These are not gaps in UX↔PRD↔Architecture coherence; they are **UX implementation details that did not get explicit AC coverage in the corresponding story**. Per epics-and-stories §1 convention, "story acceptance criteria reference §sections of the UX spec but do not re-derive the design" — the dev is expected to read the UX spec alongside the story. This convention is acceptable but means these details are easy to lose during implementation if a dev only reads the AC.

1. **RotatingTip 6s cadence + 5 ordered tip strings** (UX §2.3.2 + §4.1.5; FU-7).
   - **Where it lives:** Story 8.1 (i18n bundle) carries the 5 strings as `PROC.tip_1..5` keys; the ProcessingScreen UI is legacy from Sprint 2.5 Story 7.5 (closed under Epic 0 audit).
   - **Gap:** No story explicitly enumerates "tip cadence = 6s; tips loop in order tip_1 → tip_2 → tip_3 → tip_4 → tip_5". A dev wiring the i18n strings might keep the legacy cadence (whatever that was) or pick a new value.
   - **Severity:** low. Easy to spot in QA; FU-7 is documented in UX §6.4.

2. **Bracket-handle snap-to-round-boundary behavior** (UX §2.1.3).
   - **Where it lives:** Story 6.1 (30-second clip + bracket bounds 5–60s) covers the bracket UI but does not enumerate the "snap to round-boundary within 200ms with `accent-dim` glow" behavior.
   - **Severity:** low–medium. The snap behavior is value-add; a dev who skips it ships a usable clip-region selector that just doesn't snap.

3. **EntitlementBanner `[×]` dismiss-per-foreground-session** (UX §2.5.3).
   - **Where it lives:** Story 3.2 (EntitlementBanner) AC enumerates render conditions + CTA tap + state-clear; does NOT enumerate the dismiss button or per-foreground-session re-display.
   - **Severity:** low–medium. A coach annoyed by a permanent banner is a real UX cost; missing this collapses to "banner persists until state changes" (which actually still meets PRD `mobile-AUTH-006`).

4. **OfflineIndicator day-29/30 escalation** (UX §2.5.2).
   - **Where it lives:** Story 3.4 (OfflineIndicator) AC mentions tooltip / accessible label and "may include cache age" but does not enumerate the 24h-before-expiry border-thickening + color shift.
   - **Severity:** low. The escalation is a courtesy signal; missing it doesn't break the J9 path.

5. **Cinema Mode `[⋮]` Maps-overflow bottom-sheet** (UX §2.1.5).
   - **Where it lives:** Story 5.8 (Next/Previous explicit buttons) does not enumerate the overflow bottom-sheet for sessions with >8 rounds.
   - **Severity:** low. UX flagged this as a quick-jump for long sessions; dev may ship it as part of CinemaModeScreen baseline or skip it.

6. **Cinema Mode long-press-to-pin advanced state** (UX §2.1.1).
   - **Where it lives:** Story 5.4 (Cinema Mode reveal-on-tap) does not enumerate the 600ms long-press-to-pin padlock state.
   - **Severity:** low. Power-user-only; not tied to any FR.

7. **`/privacy` + `/terms` static legal pages** (UX §1.2 names them as routes; no FR enumerates content).
   - **Gap:** PRD §9 web FRs do not include `web-PRIVACY-*` or `web-TERMS-*`. Epics-and-stories doc has no story for creating/maintaining these pages. UX §6.1.3 WCAG audit assumes they exist (`accent` link target).
   - **Where it lives:** Likely already present in legacy web (Cookie banner references them). Not Sprint-3-blocking.
   - **Severity:** low *if* legacy already ships these pages with sufficient content; medium otherwise. Worth confirming during Epic 0 audit or Story 1.9 J1 trace.

8. **Cookie banner has no FR number.** UX §3.4 references "FR web-FR27..29" — these FRs do not exist in PRD §9 web. The cookie banner is a legacy carry-forward (`apps/web/src/components/layout/CookieBanner.tsx`); Story 4.8 (analytics) references it parenthetically but no story owns it as a Sprint-3 deliverable.
   - **Severity:** low. Cookie banner exists in legacy and works; if UX §4.2.7 copy needs updating, that's a delta the team will discover during Story 4.7 (web English copy embedding).

### Warnings

⚠️ **PRD does not number cookie-consent / privacy-page / terms-page as FRs.** UX presumes their existence; epics-and-stories presumes legacy ships them. If GDPR-compliant cookie consent fails Lighthouse / launch review (e.g., for a specific copy issue or a missed `cookie_consent_at` field), there is no FR to escalate against and no Sprint 3 story to amend. Mitigation: Epic 10 launch checklist L21+ should add a row covering cookie banner + privacy/terms pages if they haven't been verified post-token-bump.

⚠️ **AC convention: "reference UX spec, do not re-derive."** This convention is structurally sound for solo dev who can re-read both docs, but introduces the implementation-detail-loss risk above (items 1–6). A code review that doesn't have the UX spec next to the diff will not catch missing snap behavior, missing day-29 escalation, missing long-press-to-pin, etc. Mitigation: the dev story file (when generated by `bmad-create-story` per phase 7) should expand AC inline by quoting the relevant UX §section verbatim.

⚠️ **Decision #UX-14 (manual-clip-from-timeline) is conditional on AR-SPIKE outcome.** UX §6.3 says "UX is shipped-ready for either outcome" — meaning the same `CardViewScreen` toggle handles both rung-1/2 (auto-slice on) and rung-3 (auto-slice off). Story 5.3 (Cards/Timeline toggle) appears to handle both paths. ✓ Verified.

## Epic Quality Review

### Epic Structure — User-Value Focus

| Epic | Type per epics doc | Skill verdict |
|---|---|---|
| Epic 0: Sprint 2.5 Closure & Conflict Audit | Transition gate | 🟡 Not user-value. **Honestly labeled.** Borderline-acceptable: brownfield audit must precede Sprint 3 commit per Decision #ES-3. |
| Epic 1: Foundations | Foundation (V1-launch-blocking; user value = enabling) | 🟡 Foundation epic, not user-value. **Honestly labeled.** Architecture spike + RN auth migration + cross-language contracts cannot ship as a single user-facing feature; bundling them honestly is better than masquerading. |
| Epic 2: Reader-App Build Gate & Activation Telemetry | Cross-surface contracts | 🟡 Cross-surface contracts, not single-surface user-value. **Honestly labeled.** |
| Epic 3: Six-State Entitlement | Cross-surface user value (trust + correctness) | ✅ User-value. Coach experiences correct entitlement behavior across J7/J8/J9. |
| Epic 4: Web — Subscribe & Manage Funnel | Web user value | ✅ User-value. Discord-coupon-link → checkout → dashboard funnel. |
| Epic 5: Mobile — Card View, Cinema Mode, Manual Clip | Mobile user value (review experience) | ✅ User-value. First half of activation < 5min. |
| Epic 6: Mobile — Clip Creation, Voice & Export-Share | Mobile user value (artifact production) | ✅ User-value. Second half of activation; T1-coach completion. |
| Epic 7: Mobile — Auto-save & Crash Recovery | Mobile user value (trust through invisible reliability) | ✅ User-value. J2 interruption-and-resume. |
| Epic 8: Mobile — French i18n, Help & Manual Error Reporting | Mobile user value (localization + support) | ✅ User-value. End-to-end French + manual error path. |
| Epic 9: Tooling — V1 Pipeline Hardening | Operator user value | ✅ User-value (operator persona). J10 developer regenerates map_config end-to-end. |
| Epic 10: V1 Launch Readiness | V1 launch gate | 🟡 Launch gate (deliverable manifest). **Honestly labeled.** |

**Verdict on user-value:** 7 of 11 epics are user-value (Epic 3–9). 4 of 11 (Epic 0/1/2/10) are foundation/contract/launch-gate epics. The skill's red-flag standard is "technical milestone masquerading as user value"; the epics doc avoids this by **explicitly labeling each epic's type** and citing the architectural rationale (Decision #ES-1). The mix is acceptable: a brownfield V1 with mandatory architecture-bound foundation work cannot decompose cleanly into 100% user-value epics without dragging foundation into every user-value epic — which would reduce coherence.

### Epic Independence

Cumulative dependency check (each epic functions on top of prior epics):

- **Epic 0** runs first; no dependencies. ✓
- **Epic 1** depends on Epic 0 closure; otherwise self-contained. ✓
- **Epic 2** depends on Epic 1 (Story 1.4 RN auth + Story 1.6 authService for T0 emit). ✓
- **Epic 3** depends on Epic 1 (Story 1.7 subscriptionService + Stories 1.10/1.11/1.12 contract triple). ✓
- **Epic 4** depends on Epic 1 (Story 1.12 trialing handler) + token bump 4.1 — independent of mobile epics. ✓
- **Epic 5** depends on Epic 0 (legacy view-mode toggle UI) + Epic 1 (spike outcome) + Epic 2 (T1-active-player wrapper). ✓
- **Epic 6** depends on Epic 5 (Cinema Mode platform) + Epic 1 (FFmpeg encode budget) + Epic 2 (T1-coach wrapper). ✓
- **Epic 7** declared as depending on Epic 6 (clip-creation state to auto-save). **See Forward-Dependency Issue #1 below — actual coupling is interleaved, not strict-after.**
- **Epic 8** depends on Epic 2 (Reader-App gate scans i18n bundle); independent otherwise. ✓
- **Epic 9** has bidirectional dependencies with Epic 1: Stories 9.1, 9.2 ship first as 1.13's prerequisite; Story 1.13 then consumes 9.1's writer output; Stories 9.3, 9.4 then depend on 1.13 (regression hashes + strict schema validation against the bundled config). ✓
- **Epic 10** depends on all other epics (synthesis). ✓

**Verdict:** Epic-level independence holds. No epic requires a *future* epic to deliver its named outcome. Two soft issues at story level (below) require attention but do not invalidate epic independence.

### Story Quality Findings

#### Sizing

- 75 of 76 stories flagged `fits-in-one-sprint` per Decision #ES-9 (binary gate, no numeric estimate).
- 1 story flagged `needs-spike-or-split` by design — Story 1.1 (AR-SPIKE pre-PRD performance spike).
- Story 1.9 (J1–J10 manual E2E) is large but bounded — "one focused day of E2E verification on dev build" — accepted.

✓ **Sizing is internally consistent and honestly flagged.**

#### Acceptance Criteria

Per Decision #ES-5 hybrid: Gherkin Given-When-Then for behavior-driven stories (most user flows in Epics 3, 5, 6, 7, 8 + most of Epic 4); explicit checklists for infrastructure stories (Epic 0, 1, 2, 9, 10 + token bump 4.1 + OG meta 4.2 + Reader-App regex narrowing).

Sampled stories (1.1, 2.2, 3.1, 4.5, 5.5, 6.1, 6.6, 6.9, 7.1, 8.1, 9.4) have:
- ✓ Specific, testable AC (no "user can login" vagueness)
- ✓ Error-path coverage (e.g., 6.6 enumerates encode failure preserves clip-mode state)
- ✓ Negative cases (e.g., 2.4 cancel-share does NOT emit T1; 3.1 6-state regression covers each state independently)
- ✓ Test ownership declared per Decision #ES-6 (file path + framework explicit per story)

✓ **AC quality is high.** No vague or non-measurable outcomes spotted.

#### Forward-Dependency Issues

🟠 **Issue #1: Story 6.4 → Story 7.1 interleave breaks the "Epic 7 depends on Epic 6" claim.**

- Epic order claims: Epic 6 fully before Epic 7 (Epic 7 deps include "Epic 6 clip-creation state to auto-save").
- Reality: Story 6.4 (voice slot re-record) declares cross-epic dep on Story 7.1 (auto-save) — meaning Story 7.1 must land **before** Story 6.4, partially within Epic 6's timeline.
- Actual ordering: 6.1 → 6.3 → 7.1 → 6.4 (Story 7.1 inserted between Stories 6.3 and 6.4).
- **Severity:** medium. Acceptable engineering pattern (interleaved sprints) but the docs claim cleaner epic boundaries than reality. Sprint planning must surface this as an explicit interleave so the sprint sequence isn't planned as a strict 0→1→...→9→10 cascade.
- **Recommended remediation:** rephrase Epic 7's dependency description from "depends on Epic 6 (clip-creation state to auto-save)" to "depends on Stories 6.1 + 6.3; Story 7.1 then enables Story 6.4 in Epic 6." OR move Story 7.1 (silent auto-save in clip mode) into Epic 6 since it's clip-mode specific. This decision is one for sprint planning; the readiness report flags it.

🟠 **Issue #2: Story 2.5 dependency declaration is misleading.**

- Story 2.5 (T1-active-player emission) declares "cross-epic depends on Epic 5 Story 5.5 (view-mode toggle UI exists; this story wires the telemetry hook into it)."
- Epic 5 is **after** Epic 2 in the epic order. This reads as a forward dependency.
- Actual situation: the view-mode toggle UI exists in legacy code (Sprint 2.5 Story 7.3, closed under Epic 0 Story 0.2 as complete-as-legacy). Story 2.5 needs the legacy UI, not Story 5.5. Story 5.5 enforces PERF-003 ≤100ms (no-player-swap) on the existing toggle — orthogonal to telemetry emission.
- The epics doc's own validation section (line 2992) acknowledges this: "the view-mode toggle UI exists in legacy code... PERF-003 enforcement (Story 5.5) is orthogonal and can land before OR after Story 2.5 without affecting the telemetry hook."
- **Severity:** low. Docs disagree with themselves — story declares Epic 5 dep, validation says no real Epic 5 dep. Sprint planning will trip over this if reading the story file in isolation.
- **Recommended remediation:** rephrase Story 2.5's dependency from "cross-epic depends on Epic 5 Story 5.5" to "depends on Epic 0 Story 0.2 (legacy view-mode toggle UI shipped via Sprint 2.5 Story 7.3)."

#### Database / Entity Creation Timing

✓ Schema bumps are scoped to specific stories (Story 1.10 user-doc tighten; Story 1.13 map-config `schema_version` add). Mobile SQLite tables (`sessions`, `map_segments`, `clip_exports`, `audio_comments`) are pre-existing legacy. The only NEW schema delta is the `view_mode` 2-value→3-value migration (legacy Sprint 2.5 Story 7.1, closed via Epic 0). **No "create all tables upfront" anti-pattern.**

#### Starter Template

✓ Brownfield project; architecture explicitly states "starter selections are historical." Story 1.1 is the AR-SPIKE, not a project-init story. **Acceptable deviation per architecture's brownfield posture.**

### Architecture ↔ Epics Cross-Document Consistency

This was the user's explicit ask — "stories referencing components the architecture doesn't define." Findings:

🟡 **Internal architecture FR count inconsistency.** Architecture intro (line 98) says "**55 total**" FRs but enumerates 33 mobile + 13 web + 13 tooling + 6 cross-surface = **65** by its own count. PRD has 33 + 16 + 12 + 8 = 69. Architecture's intro section appears to have been written against an earlier PRD draft (web is undercounted by 3 FRs; cross-surface by 2; tooling overcounted by 1). The downstream epics-and-stories doc resolved this using the correct PRD count of 69. **No coverage gap** (architecture's FR-to-Structure mapping section actually covers all FRs by file path), but the intro arithmetic is a documentation artifact worth correcting before the doc is referenced as the binding count.

🟢 **Architecture's directory tree previously omitted 9 NEW components that UX and epics-and-stories specified — RESOLVED in commit `5968ef9` (this PR).** The architecture doc's project tree now annotates all 9 components as `[NEW per UX-DR<n>]`. The original gap analysis is preserved below for traceability:

| Component | UX section | Story | Architecture mention (pre-amendment) |
|---|---|---|---|
| `apps/mobile/src/features/auth/EntitlementBanner.tsx` | UX §1.6 | 3.2 | ✓ Mentioned in FR-to-Structure (line 1684) but was NOT in directory tree (now added) |
| `apps/mobile/src/features/auth/SubscriptionRequiredScreen.tsx` | UX §1.6 | 3.3 | ❌ Not in directory tree; not in FR-to-Structure |
| `apps/mobile/src/features/auth/OfflineIndicator.tsx` | UX §1.6 | 3.4 | ❌ Not in directory tree; not in FR-to-Structure |
| `apps/mobile/src/shared/services/errorReporting.ts` | UX §1.6 / §6.5 | 8.2 | ❌ Not in directory tree; not in FR-to-Structure |
| `apps/web/src/components/dashboard/PaymentWarning.tsx` | UX §6.5 | 3.5 | ❌ Not in directory tree; not in FR-to-Structure |
| `apps/web/src/components/dashboard/EmptySubscription.tsx` | UX §6.5 | 4.6 | ❌ Not in directory tree; not in FR-to-Structure |
| `apps/web/src/components/auth/PasswordResetForm.tsx` | UX §6.5 | 4.4 | ❌ Not in directory tree; not in FR-to-Structure |
| `apps/mobile/src/features/clip-export/clipDeletion.ts` | (UX out of scope) | 6.9 | 🟡 Mentioned in Gap Analysis section as AR-12 / "Important Gap #2" but NOT in directory tree |
| `apps/web/src/components/dashboard/CancelDialog.tsx` | UX §6.5 | 4.5 | ✓ Mentioned in FR-to-Structure (line 1731) but NOT in directory tree |

**Severity (pre-amendment):** medium. None of these were coverage gaps — every component is owned by a specific story with explicit AC and a file path. But the architecture document, which is supposed to be the binding "where do components live" reference, was mildly out-of-sync with the UX (Phase 6 step 4) and epics-and-stories (Phase 6 step 5) outputs.

**Status:** RESOLVED in commit `5968ef9` (shipped in PR #1). The architecture doc's directory tree now annotates all 9 components as `[NEW per UX-DR<n>]` — see `_bmad-output/architecture.md` lines 1456–1564. Architecture-as-binding-reference posture restored.

### Quality Review Summary

- 🔴 **Critical violations:** none.
- 🟠 **Major issues:** 2 forward-dependency declarations need clarification (Story 6.4 → Story 7.1 interleave; Story 2.5 mis-declared Epic 5 dep). ~~Architecture directory tree out-of-sync with UX/epics for 9 NEW components.~~ — RESOLVED in commit `5968ef9` (this PR).
- 🟡 **Minor concerns:** 4 honest-but-non-user-value epics (0/1/2/10 — acceptable per skill convention with rationale documented); ~~architecture FR count typo (55 vs 65 vs 69)~~ — RESOLVED in code-review patch round (now reads 69 in `_bmad-output/architecture.md` line 98); UX implementation details dropped from story AC (catalogued in step 4).

**Best practices compliance for the project as a whole:**

- [x] Most epics deliver user value; foundation/contract/launch epics honestly labeled.
- [x] Each epic functions cumulatively on top of prior epics.
- [x] Stories appropriately sized (binary gate; 75/76 fit-in-one-sprint, 1 spike-by-design).
- [⚠️] Forward-dependency declarations need 2 fixes (low-cost rephrasing).
- [x] Database / schema changes scoped to specific stories.
- [x] Acceptance criteria specific, testable, with error paths.
- [x] FR / NFR / UX-DR / AR / BF / CI traceability complete and bidirectional.

## Summary and Recommendations

### Overall Readiness Status

**READY WITH MINOR AMENDMENTS.**

The PRD, Architecture, UX Design, and Epics-and-Stories documents are internally consistent, structurally sound, and traceably aligned. 100% of FRs (69/69) and NFRs (41/41) are routed to specific stories. All 8 PRD-escalated architecture decisions are resolved. All 14 UX decisions are resolved with all 8 follow-ups locked. The 76-story breakdown across 11 epics is implementable with stated dependencies.

The "minor amendments" qualifier captures three categories of fixable findings (none of which block sprint planning, but all of which should be addressed before or during Sprint 3 commit):

1. **Two forward-dependency declarations need rephrasing** (Story 6.4 ↔ 7.1 interleave; Story 2.5's misleading dep on Story 5.5).
2. **Architecture's project-tree section is out-of-sync with UX/epics** for 9 NEW components (`SubscriptionRequiredScreen.tsx`, `OfflineIndicator.tsx`, `errorReporting.ts`, `PaymentWarning.tsx`, `EmptySubscription.tsx`, `PasswordResetForm.tsx`, `clipDeletion.ts`, `EntitlementBanner.tsx`, `CancelDialog.tsx`).
3. **6 UX implementation details did not get explicit story-AC enumeration** (rotating-tip cadence, bracket snap-to-boundary, banner dismiss behavior, day-29 escalation, Maps overflow, long-press-to-pin) — covered by the "AC references UX spec, does not re-derive" convention but discoverable only by reading both docs.

### Critical Issues Requiring Immediate Action

None. The work is implementation-ready as a pre-condition for sprint planning.

### Important Issues to Address Before / During Sprint 3 Commit

1. **🟠 Resolve Story 6.4 ↔ 7.1 ordering ambiguity.** Either move Story 7.1 (silent auto-save in clip mode) into Epic 6 *before* Story 6.4, OR rephrase Epic 7's dependency from "depends on Epic 6" to "Story 7.1 depends on 6.1 + 6.3; enables 6.4." Sprint planner needs a clean DAG.
2. **🟠 Rephrase Story 2.5's dependency** from "cross-epic depends on Epic 5 Story 5.5" to "depends on Epic 0 Story 0.2 (legacy view-mode toggle UI)." Removes a soft circular reference between Epic 2 and Epic 5.
3. ~~**🟠 Update Architecture project-tree** to add the 9 missing NEW components as `[NEW per UX-DR<n>]` annotations.~~ **DONE** — applied in commit `5968ef9`, shipped in PR #1.
4. **🟡 Decide cookie-banner / privacy / terms scope.** PRD does not number these as FRs, UX presumes legacy ships them, no Sprint-3 story owns them. Add a row to Epic 10 launch checklist verifying their existence and post-token-bump rendering.
5. **🟡 Reconcile demand-evidence non-blocking-vs-mandated tension.** PRD §2 says "captured before V1 launch" but Story 10.5 marks L21 as non-V1-blocking. Sprint planning must pick: gate launch on the metric, or ship V1 without the evidence and accept the PRD-flagged trade-off explicitly.
6. ~~**🟡 Correct Architecture's intro FR count typo** ("55 total" → 69 to match PRD).~~ **DONE** — applied in code-review patch round; `_bmad-output/architecture.md` line 98 now reads "69 total".
7. **🟡 Confirm Sprint 2.5 audit dispositions before Sprint 3 commits.** Decision #ES-3 makes Story 0.1 a gating deliverable; the audit table itself doesn't yet exist. This is on-schedule per the epics doc but worth tracking.

### Latent Risks (informational; not actionable yet)

- **Story 1.1 spike outcome conditions downstream story scope.** Under rung-3 (auto-slice deferred to V2), Card View collapses to manual-clip-only and the < 5min activation target requires re-validation against the new flow. Sprint planning should pre-walk the rung-3 contingency.
- **Story 10.4 Stripe Production Activation** is blocked on Root providing company number. External dependency; if it doesn't unblock, V1 cannot ship Stripe Checkout to production regardless of all other stories passing.
- **Web carry-forward verification leans on Story 1.9 manual J1 trace + Epic 10 production smoke.** No Vitest snapshot tests for legacy-shipping web FRs (LANDING-001, PRICING-001/002, AUTH-001 base, CHECKOUT-001/002, DASHBOARD-001). Post-token-bump regressions would only surface during manual runs. Acceptable for V1; flag as post-V1 hardening.

### Recommended Next Steps

1. **Address the 3 🟠 issues above** in a single architecture-amendments PR (one PR touching `_bmad-output/architecture.md` + `_bmad-output/epics-and-stories.md` for the dep rephrasing). Estimated effort: < 1 day.
2. **Run `bmad-sprint-planning`** (the next BMad phase) to convert the 76 stories into Sprint 3 sequencing. Apply the 80/20 maintenance-vs-V1 capacity split per Decision #ES-10.
3. **Execute Epic 0 Story 0.1** to produce the Sprint 2.5 conflict-audit table — gates Sprint 3 commit per Decision #ES-3.
4. **Kick off Story 1.1 (AR-SPIKE) as the first Sprint 3 work item.** Spike outcome dictates downstream mobile story shape; nothing else in Sprint 3 mobile commits until the spike's `_bmad-output/architecture-spike-perf-floor.md` artifact is published.
5. **Schedule a demand-evidence track in parallel** (Story 10.5) — non-V1-blocking but PRD-mandated. Run as a parallel sprint outside the 76-story Sprint 3 cascade.

### Final Note

This assessment identified **no critical violations**, **2 forward-dependency declarations needing rephrasing**, **1 architecture-document-currency gap (9 components missing from tree)**, **5 implementation-detail gaps in UX↔story AC binding**, and **2 specification-level scope clarifications needed (cookie/privacy/terms FRs; demand-evidence blocking semantics)**. Total: ~10 issues across 4 categories. None block sprint planning. The 3 🟠 items should land before Sprint 3 commits to keep the dependency DAG and architecture reference clean; the 🟡 items can be addressed in-flight.

The Phase-6 BMad chain (steps 1–5) has produced an unusually high-quality artifact set: cross-document traceability is bidirectional and explicit, escalated decisions are resolved at the right level (PRD escalates → architecture decides → UX/epics consume), and the brownfield posture is honestly framed throughout. Solo dev (Stephane) plus AI-agent execution should be able to ship V1 against this plan with the architecture spike outcome as the single load-bearing unknown.

These findings can be used to improve the artifacts or you may choose to proceed as-is.

---

**Assessment date:** 2026-05-09
**Assessor:** Claude (bmad-check-implementation-readiness skill)
**Documents reviewed:** prd.md (1073 lines), architecture.md (2183 lines), ux-design.md (2071 lines), epics-and-stories.md (3067 lines) — 8394 lines total
**Verdict:** READY WITH MINOR AMENDMENTS — proceed to sprint planning after addressing the 3 🟠 items.




