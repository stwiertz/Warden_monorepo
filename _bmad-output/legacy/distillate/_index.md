---
type: bmad-distillate
sources:
  - "../mobile/planning-artifacts/product-brief-warden-2026-01-26.md"
  - "../mobile/planning-artifacts/prd.md"
  - "../mobile/planning-artifacts/architecture.md"
  - "../mobile/planning-artifacts/ux-design-specification.md"
  - "../mobile/planning-artifacts/epics.md"
  - "../mobile/planning-artifacts/sprint-change-proposal-2026-05-05.md"
  - "../web/planning-artifacts/product-brief-WardenWeb-2026-02-05.md"
  - "../web/planning-artifacts/prd.md"
  - "../web/planning-artifacts/architecture.md"
  - "../web/planning-artifacts/ux-design-specification.md"
  - "../web/planning-artifacts/epics.md"
  - "../web/planning-artifacts/sprint-change-proposal-2026-04-16.md"
  - "../tooling/project-sprint.md"
  - "../tooling/implementation-artifacts/"
downstream_consumer: "unified-bmad-replanning"
created: "2026-05-07"
parts: 8
---

## Orientation
- Distillate consolidates 44 source planning docs across the three Warden sibling repos (legacy `Warden` mobile, legacy `WardenWeb`, legacy `Warden-tooling`) compressed via 5 fan-out intermediates (~35K tokens) into a final split distillate (~8 thematic sections); Act II of the Warden monorepo merge — sole input (with merged code) to unified BMad re-planning
- Three apps in scope: (1) `apps/mobile` — Expo/React Native EVA After-h match-review tool (French, mobile, on-device, offline-first); (2) `apps/web` — Next.js + Stripe subscription portal ("Reader App" model, English UI, French tagline); (3) `apps/tooling` — Python CLI suite that produces `map_config.json` + reference impl for mobile detectors
- Downstream BMad workflows that consume this distillate: `bmad-product-brief` → unified product-brief; `bmad-create-prd` → unified PRD (English; legacy mobile was French); `bmad-create-architecture` (must resolve `users/{uid}` schema split + `map_config.json` runtime delivery); `bmad-create-ux-design`; `bmad-create-epics-and-stories` (story prefixes `mobile-` / `web-` / `tooling-` / `cross-`)
- Authority rule: where mobile and web sprint-change proposals supersede their original PRD/epics, the proposals carry forward; legacy SUPERSEDED items retained as historical context only
- Section files are self-contained — agents can load 1-2 sections rather than reading the whole distillate

## Section Manifest
- `01-product-strategy.md` — unified product positioning, three-app coherence, target users, business KPIs, monetization model (Reader App split web↔mobile), discovery channels
- `02-mobile.md` — Warden mobile app (Expo/RN): FRs/NFRs, stack, schema, detection methodology pivot, Cinema Mode UX, epics, sprint state
- `03-web.md` — WardenWeb (Next.js/Stripe): tech stack, auth+Stripe integration, dashboard, portal-first revision, epics, sprint state
- `04-tooling.md` — Python CLI suite (`apps/tooling`): orchestrator (TUI), pipeline tools (BSD, frame_labeler, hash_comparator, hash_validator, warden_analyzer, game_detector), visualization tools, sprint state
- `05-architecture-cross-cutting.md` — `map_config.json` pipeline (canonical schema target), `users/{uid}` Firestore doc reconciliation, monorepo structure, brownfield issues parked for Phase 6
- `06-ux-design.md` — unified UX direction: mobile Tactical HUD vs web Clean Minimal, design tokens, emotional principles, journeys
- `07-epics-and-sprint-state.md` — consolidated epics across all three apps with current sprint state, prerequisites, blockers, story prefixes
- `08-open-questions-and-risks.md` — unresolved decisions, conflicts, risks, and rejected alternatives carried forward to unified planning

## Cross-cutting items
- `users/{uid}` Firestore document — CONFLICT: mobile reads `isPaid` boolean; web writes `status` / `plan` / `current_period_end` / `stripe_subscription_id` / `stripe_customer_id` / `redeemed_batches` (snake_case to match Stripe payloads). Unified architecture must resolve. Mobile architecture already names `contracts/user-doc.schema.json` as target. See `05-architecture-cross-cutting.md`
- `map_config.json` — produced by `apps/tooling/tools/map_config_generator.py` (legacy) and `tools/hash_comparator.py`; consumed by mobile detection pipeline (gameDetector + mapIdentifier + blackScreenDetector). OPEN QUESTION: runtime delivery to mobile = bundled-as-Metro-asset vs Firestore-fetched. Mobile architecture currently specifies Firestore + MMKV cache + bundled fallback. Unified target schema: `contracts/map-config.schema.json`. See `05-architecture-cross-cutting.md`
- Firebase project SHARED across mobile + web — same Auth, same Firestore, region `europe-west` (GDPR). Auth provider config (apiKey, authDomain, projectId) MUST align between mobile and web env. See `05-architecture-cross-cutting.md`
- Discord-driven discovery (coupon links) flows: web landing → web pricing → web checkout → Firestore write → mobile reads entitlement → mobile unlocks features. See `01-product-strategy.md` + `05-architecture-cross-cutting.md`
- Persona reuse: Coach Thomas (26, EVA coach), Lucas (17 passive→ also web persona at age 22 active), Maxime (22 active player + assistant coach) — same archetypes referenced across mobile + web docs. See `01-product-strategy.md`
- French↔English split: mobile UI = French (coach audience), web UI = English with French tagline; unified PRD will be in English per downstream consumer instruction
- Brownfield issues parked (must address in unified architecture phase): web Stripe API version pin (`2026-03-25.dahlia` vs installed types `2026-04-22.dahlia`), web test-file type errors, web Vitest parallelism flake, web Story 7.2 PlanCta hydration mismatch, mobile `firebase/auth` `getReactNativePersistence` removed in v12. See `05-architecture-cross-cutting.md` + `08-open-questions-and-risks.md`
- Map count discrepancy: project-sprint says 14, map-config-generator spec says 15, frame_labeler `MAP_LABELS` lists 14 (canonical) — 4 maps lack reference hashes (bastion, coliseum, lunar_outpost, the_rock). See `04-tooling.md` + `08-open-questions-and-risks.md`
