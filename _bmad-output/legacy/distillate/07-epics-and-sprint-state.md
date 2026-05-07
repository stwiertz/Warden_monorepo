> This section consolidates epics + stories + current sprint state across all three apps. Story prefixes will become `mobile-` / `web-` / `tooling-` / `cross-` in unified epics. Part 7 of 8 of the Warden legacy distillate.

## Authority Rules (Sprint Change Proposals Override Original PRD/Epics)
- Mobile: sprint-change-proposal-2026-05-05 = APPROVED + APPLIED (Incremental Mode); ~50 edits across PRD/epics/architecture/UX/4 stories/1 historical doc; pure documentation reconciliation; NO code changes; NO data migration (pre-production); MVP scope unchanged (all 33 FRs + 4 journeys preserved); methodology change invisible to user-facing value. PRE-PIVOT methodology mentions are historical/superseded
- Web: sprint-change-proposal-2026-04-16 supersedes original Epic 5 stories (5.2/5.3/5.4 removed in favor of Stripe Customer Portal). PRD unchanged — all FRs still delivered. Where original PRD/epics show custom payment-history/upgrade/cancel UI, Sprint Change Proposal supersedes.
- Tooling: project-sprint.md tracks 4 original tools but actual implementation diverged; sprint tracker not updated to reflect actual state — many "Not Started" tools have working implementations; spec-level statuses are more accurate.

## Mobile Epic Structure (7 epics — last updated Sprint 2.5)
- **Epic 1 — Project Setup & User Authentication**
  - Story 1.1 init Expo project — DONE
  - Story 1.2 nav + design system — DONE
  - Story 1.3 data layer (MMKV+SQLite) — DONE
  - Story 1.4 Firebase login screen (Reader App) — DONE
  - Story 1.5 subscription validation + offline cache — DONE/ready-for-dev
  - Covers FR29-33; Reader App login UI per UX spec
  - Status: essentially complete
- **Epic 2 — Video Import & Auto-Slice Processing**
  - Story 2.1 import MP4 + format validation — DONE
  - Story 2.2 FFmpeg integration + keyframe extraction — IN-PROGRESS; 3 minor edits applied (downstream consumer redirect to 7.5, supersession note in dev notes, testing approach updated to gameDetector+mapIdentifier seam); UNAFFECTED by methodology pivot, continues toward review (device-side smoke tests + RAM measurement)
  - ~~Story 2.3 black-screen detector~~ — SUPERSEDED by 7.5 (banner added, sprint-status YAML updated, never started — no rollback needed)
  - ~~Story 2.4 OpenCV template matcher~~ — SUPERSEDED by 7.5 (banner added, never started)
  - Story 2.5 segment video into map episodes — ready-for-dev, MAJOR REWRITE applied — now CONSUMES 7.5 output (gameDetector + mapIdentifier); 7 ACs (was 6); new AC4 for unknown-map handling (`map_name = 'unknown'`, segment remains navigable); tasks reference GameDetectorEvent + MapIdentificationResult types; explicitly does NOT re-implement detector logic
  - Story 2.6 background processing + crash recovery — ready-for-dev, 1 minor dev note edit (template matching → gameDetector+mapIdentifier perf target wording)
  - Story 2.7 session list + management — ready-for-dev, unchanged
  - Covers FR1-4, 7-10 (FR5/6 moved to Epic 7)
- **Epic 3 — Video Playback & Episode Navigation**
  - Story 3.1 Card View grid — not_started, unchanged
  - Story 3.2 Cinema Mode + reveal-on-tap — not_started, unchanged
  - Story 3.3 timeline scrubber — not_started, unchanged
  - Story 3.4 Next/Previous/Maps nav — not_started, unchanged
  - ~~Story 3.5 minimap toggle~~ — SUPERSEDED by 7.3 (precedent before Sprint 2.5)
  - Story 3.6 Card View sorting — not_started, unchanged
  - Covers FR11-15
- **Epic 4 — Clip Creation & Voice Commentary**
  - Stories 4.1-4.6: 4.1 clip region selector + bracket handles, 4.2 before voice, 4.3 during voice + freeze-frame overflow, 4.4 after voice, 4.5 clip preview with assembled voice, 4.6 delete + re-record
  - All not_started
  - Covers FR16-21
- **Epic 5 — Clip Export & Sharing**
  - Stories 5.1-5.4: 5.1 export pipeline + quality options (Mobile/HD), 5.2 multi-segment assembly with voice overlay, 5.3 OS share sheet via Expo Sharing, 5.4 export progress modal
  - All not_started
  - Covers FR22-25 (jointly with Epic 7)
- **Epic 6 — Session Persistence & Reliability**
  - Stories 6.1-6.3: 6.1 auto-save 30s, 6.2 resume exactly, 6.3 persist across restarts/reboots/crashes
  - All not_started
  - Covers FR26-28
- **Epic 7 — ROI Detection Redesign & View Mode Expansion (NEWLY EXPANDED Sprint 2.5)**
  - Story 7.1 SQLite view_mode CHECK 2-value→3-value migration + `pov`→`full` row migrate (ships same PR as 7.2) — ready-for-dev
  - Story 7.2 ClipExport.view_mode TS union update + audit `'pov'` literals (same PR as 7.1) — ready-for-dev
  - Story 7.3 view-mode toggle UI + HudToggle + Zustand+MMKV persistence (SUPERSEDES 3.5) — ready-for-dev
  - Story 7.4 remote DetectionConfig service Firestore + MMKV cache + bundled fallback (no-op shim until 7.5) — ready-for-dev
  - Story 7.5 replace detectors: gameDetector (KDA/HSV) + mapIdentifier (pHash) + blackScreenDetector refactored to long-GOP fallback + delete templateMatcher.ts + delete map-templates assets (SUPERSEDES 2.3 and 2.4) — ready-for-dev; cosmetic file-path fix (`pipeline.ts` → `processingPipeline.ts`)
  - Story 7.6 export pipeline 3 view modes via exportRecipes + exportPipeline (SUPERSEDES view-mode portion of 5.1+5.2 which now layer Mobile/HD on top) — ready-for-dev
  - Covers FR5, FR6, FR14, FR15, FR22-25 (joint)

## Mobile Sprint Next Steps (as of 2026-05-05 / mid Sprint 2.5)
- 1: Finish Story 2.2 to review when device available
- 2: Start Sprint 2.5 — 7.4 first (no-op shim), 7.1+7.2 ship same PR, then 7.5
- 3: Resume Sprint 2 closure with 2.5+2.6 consuming 7.5 detectors
- Optional follow-up: ultra-review rewritten Epic 7 in epics.md once Story 7.5 lands (any AC tweaks)

## Web Epic Structure (7 epics — revised Sprint Change 2026-04-16)
- **Epic 1 — Project Foundation & Landing** (FR5/6/7)
  - Story 1.1 Init Next.js + tooling (Prettier, commitlint+husky, .env.example, shadcn init)
  - Story 1.2 Landing page w/ value prop + iOS/Android download links + CTA → /pricing (SSR cached, mobile-first, WCAG-A)
  - Story 1.3 Shared layout (Header w/ home+pricing nav, Footer w/ Privacy/Terms, CookieBanner persisting localStorage choice; conditional Analytics)
- **Epic 2 — Authentication & Identity** (FR1/2/3/4/32/33/34)
  - Story 2.1 Firebase + Google `signInWithPopup` → ID token → /api/auth/session → cookie → /dashboard + AuthContext
  - Story 2.2 Email/Password sign-in + registration (RHF + Zod inline errors)
  - Story 2.3 Sign-out (Firebase signOut + DELETE /api/auth/session + clear context + redirect /)
  - Story 2.4 Route protection middleware + Firestore rules + env-var secrets
- **Epic 3 — Subscription & Checkout** (FR8/9/10/11/12)
  - Story 3.1 Pricing page (2 plan cards, savings, mobile-first, WCAG-A)
  - Story 3.2 Stripe Checkout for monthly+yearly (server-side session, redirect to Stripe, on success create `users/{uid}` doc + redirect /dashboard, prompt sign-in if anon, < 30s)
  - Story 3.3 Coupon support (validate against Stripe, show discount + deferred billing date, error on invalid, can proceed without)
- **Epic 4 — Webhook Processing** (FR21/22/23/24) — COMPLETE 3/3
  - Story 4.1 Stripe webhook endpoint w/ signature verify (constructEvent, 400 on fail, event-id dedup in Firestore, 200 < 5s)
  - Story 4.2 Process invoice.paid (Firestore txn, set status=active/plan/current_period_end/stripe_subscription_id, create doc if missing, sync < 30s, retry 3x)
  - Story 4.3 Process subscription.deleted (status=canceled) + payment_failed (status=past_due) — both transactional, both return 200 even on permanent error
- **Epic 5 — Dashboard & Subscription Management (Portal-First)** (FR13-20+25) — REVISED 3 stories
  - Story 5.1 Dashboard overview (email + plan + status badge + next payment date; Skeletons; load-once from Firestore, NO onSnapshot; < 2s)
  - Story 5.2 Stripe Customer Portal Integration (server creates portal session, "Manage Subscription" button → portal handles history/upgrade/cancel/card-update, return URL /dashboard, webhooks update Firestore on changes; ALSO adds "Dashboard" header link for signed-in users — fulfils deferred nav from 1.3)
  - Story 5.3 Payment Failure Warning Banner (past_due warning + Update-payment CTA; canceled info banner + Resubscribe CTA; status read from `users/{uid}` no real-time)
- **Epic 6 — Legal/Compliance/Analytics** (FR26/27/28/29/30/31) — note FR28+29 implemented in Story 1.3
  - Story 6.1 Privacy + Terms pages (static cached, footer-linked)
  - Story 6.2 Account deletion process (instructions in settings/privacy + support runbook for cascading delete)
- **Epic 7 — Launch Readiness** (NEW per Sprint Change Proposal)
  - Story 7.1 Firestore Security Rules deployment (carried Epic 2 retro #1)
  - Story 7.2 Firebase Auth E2E + PlanCta hydration fix `disabled={null}` vs `disabled={true}` (carried Epic 2 retro #2 + Epic 3 retro #4)
  - Story 7.3 Guided Payment Flow E2E walkthrough (Root-led: signup → monthly checkout → dashboard verify → simulated payment failure → past_due banner → portal fix → active → upgrade yearly → portal cancel → canceled persists)
  - Story 7.4 Stripe Production Activation & Go-Live (BLOCKED by external dependency: company number from Root; live keys, webhook secret, DNS, Vercel prod, security review checklist)

## Web Sprint State (as of 2026-04-16)
- Done: Epic 4 (3/3 stories complete)
- In flight / Backlog: Epic 5 (3 revised stories — 5.1 next), Epic 7 (4 stories in backlog)
- Epic 5 prerequisite: configure Stripe Customer Portal in Stripe Dashboard before Story 5.2 (plan switching, cancellation, payment-method updates, branding, return URL)
- Epic 7.4 prerequisite: Root provides company number (external blocker)
- Action item from Epic 4 retro: diagnose Vitest parallelism flake before Epic 5 starts

## Tooling Sprint State (project-sprint.md — note tracker ≠ reality in places)
- **Tool 1 — Black Screen Detector**: Not Started (per tracker); BUT well-iterated reference impl exists in code — sprint tracker not updated
- **Tool 2 — Frame Labeling**: Done (full GUI, scope expanded from manual to full GUI); grouped-export spec completed
- **Tool 3 — Discriminating Pixel Finder**: Not Started (per tracker); BUT actual implementation evolved into hash_comparator + map_config_generator — original "Pixel Finder" superseded by hashing approach; sprint tracker not updated
- **Tool 4 — Validation & Accuracy Testing**: Not Started (per tracker); BUT `hash_validator.py` exists and is functional
- **Spec-level statuses (more accurate than project-sprint tracker)**:
  - warden-tui-launcher: Completed
  - map-config-generator: completed
  - warden-round-analyzer (Tool 5): Implementation Complete (AC unchecked — validation pending real-footage testing)
  - warden-image-inspector: completed
  - minimap-zone-selector: completed
  - frame-labeler-grouped-export: completed
  - video-named-output-subfolders: completed
  - minimap-view-mode: ready-for-dev (Tasks 1–8 all unchecked, AC all unchecked)
  - match-preview: in-progress (Step 1 of 4 only — DEFERRED/WIP)

## Pipeline Goal Success Criteria (Tooling Sprint)
- 100% black-screen transition detection with 0 false positives (target validated via Tool 4)
- 100% map ID on training set
- ≥95% (target 100%) on unseen test set
- Reproducibility across sessions/players
- All validated via Tool 4 reports

## Cross-App Story Prefixes (recommended for unified epics)
- `mobile-` — mobile-only stories (e.g. mobile-2.2 FFmpeg integration)
- `web-` — web-only stories (e.g. web-5.2 Stripe Customer Portal)
- `tooling-` — tooling-only stories (e.g. tooling-Tool5 warden_analyzer validation)
- `cross-` — multi-app stories (e.g. cross-users-uid-schema-reconciliation, cross-map-config-contract, cross-firebase-project-shared-config, cross-monorepo-pnpm-turborepo-setup)

## Likely Cross-Cutting Stories for Unified Re-planning
- cross-users-uid-schema: reconcile mobile `isPaid` boolean vs web rich schema (`status`/`plan`/`stripe_*`) → write `contracts/user-doc.schema.json` + update both apps
- cross-map-config-contract: write `contracts/map-config.schema.json` + add jsonschema validation in tooling + Zod codegen for mobile
- cross-map-config-runtime-delivery: decide Firestore vs bundled vs hybrid; implement chosen path in mobile + tooling upload step
- cross-firebase-project-shared-config: extract Firebase config (apiKey/authDomain/projectId) into shared package or env var convention; ensure mobile + web align
- cross-monorepo-config: pnpm workspaces + Turborepo + .npmrc node-linker=hoisted (already done — verify)
- cross-bmad-replan: feed this distillate into bmad-product-brief → bmad-create-prd → bmad-create-architecture → bmad-create-ux-design → bmad-create-epics-and-stories
- mobile-firebase-auth-v12-migration: address `getReactNativePersistence` removal in Firebase v12 (brownfield)
- web-stripe-api-version-pin: align code pin (`2026-03-25.dahlia`) with installed types (`2026-04-22.dahlia`) (brownfield)
- web-vitest-parallelism-flake: diagnose + fix (brownfield, Epic 4 retro action item)
- web-story-7.1: deploy Firestore Security Rules to production (carried debt)
- web-story-7.2: PlanCta hydration mismatch + Firebase Auth E2E (carried debt)
- web-story-7.4: Stripe Production Activation (blocked on company number)
- tooling-map-config-resolution-persist: store generation resolution in `map_config.json` (brownfield)
- tooling-bsd-debugger-output-subfolder: adopt per-video output subfolder convention (deferred)
- tooling-tui-launcher-non-video-source: extend "new source" prompt to non-video Tool 2/Tool 3 inputs (future)
- tooling-match-preview-completion: complete Step 3-4 of match-preview (WIP, deferred)
- tooling-minimap-view-mode-impl: implement minimap-view-mode (ready-for-dev, not yet started)
- tooling-warden-analyzer-validation: validate warden_analyzer Tool 5 against real-footage test set (AC unchecked)

## SUPERSEDED / Deprecated Items (historical context only)
- Mobile Story 2.3 (black-screen detector original methodology): SUPERSEDED by 7.5; never started; no rollback
- Mobile Story 2.4 (OpenCV template matcher): SUPERSEDED by 7.5; never started; no rollback
- Mobile Story 3.5 (minimap toggle 2-value): SUPERSEDED by 7.3 (3-value Full/Minimap/Minimap+HUD)
- Mobile pre-pivot detection methodology (luminosity black-screen + template matching against `assets/images/map-templates/`): SUPERSEDED by KDA/HSV + pHash; `templateMatcher.ts` + map-templates assets to be deleted in Story 7.5
- Web Story 5.2 (custom Payment History UI): REMOVED — delegated to Stripe Customer Portal
- Web Story 5.3 (custom Upgrade Monthly→Yearly UI): REMOVED — delegated to Stripe Customer Portal
- Web Story 5.4 (custom Cancel Subscription UI): REMOVED — delegated to Stripe Customer Portal
- Tooling original "Tool 3 Discriminating Pixel Finder" (per-pixel comparison): SUPERSEDED by hash-based map_config_generator + later HSV-zone based minimap_zone_selector — sprint tracker not updated to reflect actual implementation path
- Tooling `points_state_detector.py`: SUPERSEDED by `game_detector.py` (kept as fallback/reference; eventual move to `tools/legacy/` deferred)
