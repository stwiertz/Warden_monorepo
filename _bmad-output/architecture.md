---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
lastStep: 8
status: complete
completedAt: '2026-05-07'
workflowType: 'architecture'
project_name: 'Warden_monorepo'
user_name: 'Stephane'
date: '2026-05-07'
inputDocuments:
  - _bmad-output/prd.md
  - _bmad-output/product-brief.md
  - _bmad-output/product-brief-distillate.md
  - _bmad-output/legacy/distillate/05-architecture-cross-cutting.md
  - _bmad-output/legacy/distillate/02-mobile.md
  - _bmad-output/legacy/distillate/03-web.md
  - _bmad-output/legacy/distillate/04-tooling.md
  - _bmad-output/legacy/distillate/08-open-questions-and-risks.md
  - docs/architecture-mobile.md
  - docs/architecture-web.md
  - docs/architecture-tooling.md
  - docs/architecture-shared.md
  - docs/integration-architecture.md
  - docs/data-models-mobile.md
  - docs/data-models-web.md
  - docs/data-models-shared.md
  - docs/api-contracts-web.md
  - docs/source-tree-analysis.md
  - docs/component-inventory-mobile.md
  - docs/component-inventory-web.md
  - docs/deployment-guide.md
  - docs/development-guide.md
documentCounts:
  prds: 1
  briefs: 1
  briefDistillates: 1
  legacyDistillates: 5
  asBuiltDocs: 14
  projectContext: 0
project: Warden_monorepo
outputPathOverride: '_bmad-output/architecture.md'
prdLineCount: 1073
prdSurfaces: [mobile, web, tooling]
prdRequirementPrefixes: [mobile, web, tooling, cross]
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
prdEscalatedDecisions:
  - decision_1_users_uid_schema_reconciliation
  - decision_2_map_config_runtime_delivery_moat_shaping
  - decision_3_shared_firebase_project_assertion_and_ci_guard
  - decision_6_apps_web_wiring_to_warden_contracts_user_doc
  - decision_7_firestore_rules_coverage_for_detection_config_and_stripe_events
  - decision_8_detection_config_latest_ownership
  - decision_9_status_enum_trialing_handling
brownfieldItemsForArchitecture:
  - stripe_api_pin_review_2026_03_25_to_2026_04_22_dahlia
  - firebase_v12_rn_auth_migration_target_react_native_firebase
  - foreground_service_android_plugin_choice
  - firestore_rules_prod_deploy_v1_blocking
loadBearingFirstTask:
  name: pre_prd_performance_spike
  description: Reference-device performance floor for on-device CV pipeline (FFmpeg I-frame extract + OpenCV pHash + map ID + round-boundary detection) AND OpenCV JSI binding viability validation; PRD inherits the published PERF-010 number; V1 launch criteria gated on spike completion
  fallbackLadder:
    - lower_frame_sampling_rate
    - drop_minimap_hud_on_weak_hardware
    - defer_jsi_to_v2_manual_clip_only_v1
  forbiddenFallback: fall_back_to_cloud_breaks_innovation_1
---

# Architecture Decision Document — Warden_monorepo

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (55 total, surface-prefixed).** Mobile owns 33 FRs across 8 clusters (auth & entitlement, session import & auto-slicing, card view & triage, cinema mode, clip creation & voice annotation, export & share, auto-save & crash recovery). Web owns 13 FRs across 5 clusters (landing & pricing, authentication & checkout, dashboard, webhook processing, analytics). Tooling owns 13 FRs across 6 clusters (round detection & frame extraction, frame labeling, hash generation & map config, hash validation, end-to-end pipeline, TUI launcher, schema validation). The cross-surface category contributes 6 FRs across 5 clusters (entitlement state machine, activation event chain telemetry, schema contract conformance, reader-app build gate, map_config.json runtime delivery).

The FRs that drive the most architectural surface area:

- `mobile-AUTO-SLICE-001/002` depend on OpenCV JSI binding shipping as a real binding; currently a tested-via-injection stub (`apps/mobile/src/shared/services/opencv.ts` `loadFrameFromPath` throws). This is the single largest V1 technical risk and is the principal trigger for the architecture's load-bearing first task — the pre-PRD performance spike.
- `cross-ENTITLEMENT-001` defines a six-state model whose transitions and triggering events are architecture-owned; payment-failed grace duration is parameterized; day-31 offline-cache expiry behavior is crisp.
- `cross-MAP-CONFIG-DELIVERY-001` explicitly defers to architecture (Decision #2; moat-shaping — Firestore-fetched preserves the "ship new maps without a release" lever, Metro-bundled fully closes the device for privacy).
- `cross-SCHEMA-001/002` fix `packages/contracts/` as the binding mechanism; web wiring (Decision #6) and `user-doc` schema reconciliation (Decision #1) close the remaining gaps.
- `cross-READER-APP-001` mandates a CI gate spanning direct-import bans, transitive-dependency scan, pricing-string bans, and i18n bundle scan; signaling-tier, not absolute prevention.
- `cross-ACTIVATION-001/002` requires dual-T1 instrumentation (coach path = OS share-sheet confirmed-dispatch; active-player path = Cinema Mode opened with view-mode toggled at least once) under an on-device-only telemetry contract — payloads carry only timestamps and event names.
- `web-WEBHOOK-002` requires dual-strategy idempotency (event-ID dedup via `stripe_events/{event_id}` + business-state observation) — already implemented per Epic 4; architecture documents the precise contract and surfaces regression-coverage requirements.
- `mobile-AUTH-004` makes the 30-day MMKV-cached entitlement structural, not incidental.

**Non-Functional Requirements (41 total).** Ten performance NFRs, seven security, six reliability, six accessibility, five privacy, four observability, three i18n. The PERF category contains the architecture's most load-bearing item:

- **PERF-010 (mobile)** — reference-device performance floor; TBD pending the architecture pre-PRD spike; gates V1 launch criteria.
- **PERF-002** — auto-slice ≤ 5% of source duration on the reference device sets the on-device CV ceiling and drives the Innovation #1 fallback ladder when measured against the spike outcome.
- **PERF-003** — view-mode toggle ≤ 100 ms forces a "no player swap" rendering pattern (crop/style change on the same `expo-av` source).
- **PERF-004** — Cinema Mode cold-start ≤ 1.5 s is load-bearing for the < 5 min activation budget; slow Cinema Mode startup blows the activation timer.
- **PERF-005** — clip export ≤ 2× clip duration (Mobile-tier) sets the FFmpeg encode ceiling and constrains the export pipeline.
- **PERF-008** — webhook handler ≤ 1 s p95 is already met by the current implementation but architecture inherits the regression-coverage requirement.
- **REL-002** — 30-day offline functionality drives the SQLite (durable rows) + MMKV (cache + checkpoints) split-storage pattern.
- **REL-006** — map ID ≥ 95% on an unseen test set drives a regression-suite gate before any new `map_config.json` ships (`tooling-VALIDATE-001` is the implementation hook).
- **SEC-002/003** — server-only `users/{uid}` writes (firebase-admin bypasses rules); rules deployed to production before V1 launch (V1-blocking; brownfield item 2).
- **SEC-007** — third-party SDK allowlist asserts the on-device-only contract at the dependency level; architecture maintains the allowlist.
- **PRIV-001/002** — the on-device-only contract is architecturally structural, not a configuration toggle that can be flipped under load.

**Scale & complexity:**

- Primary domain: **multi-surface mobile-first product** (`mobile_app` primary, `web_app` + `cli_tool` secondary).
- Complexity level: **high architectural-coordination** — NOT regulatory (`regulatoryComplexity: low`; no FDA/HIPAA/PCI/KYC/AML/DO-178C/FedRAMP).
- Complexity drivers: three-surface coherence enforced via two cross-language contracts and one shared Firebase project; OpenCV JSI binding load-bearing V1 (currently a stub); Reader-App architecture as a structural commitment propagating through every entitlement and monetization decision.
- Estimated architectural components: ~14 across the three surfaces — mobile (auth/entitlement gate, video import, processing pipeline orchestrator, detection-config cache, FFmpeg service, OpenCV/JSI service, Cinema Mode/playback, clip export, voice annotation, auto-save & crash recovery, navigation shell), web (Stripe-Checkout surface, Stripe-webhook ingestor, dashboard data layer, auth/session-cookie surface), tooling (Python pipeline + cross-language schema validation), and shared (`packages/contracts/`, `firestore.rules`, the Firebase project itself).
- Project context: **brownfield** — three pre-merged apps (`apps/mobile`, `apps/web`, `apps/tooling`) with full git history; 7-item brownfield triage backlog; in-flight Sprint 2.5 mobile stories disposed as complete-as-legacy after per-story audit.

### Technical Constraints & Dependencies

**Locked by PRD (architecture must enforce, not re-litigate):**

- **Reader-App contract structural.** Mobile login-only with zero monetization surface; build-time CI gate signaling-tier defense-in-depth; transitive-dep scan (`pnpm ls --depth=Infinity`) required.
- **No-free-tier positioning.** Mobile is paid-only; entitlement states `lapsed` and `signed-out` make the app unusable; only `offline-grace ≤ 30 d` is a soft state.
- **On-device-only video processing.** No video frames, audio frames, voice annotations, or derived video data may cross any wire to a Warden-controlled server. Activation telemetry carries only timestamps and event names. "Fall back to cloud" is explicitly forbidden per Innovation #1.
- **30-day offline auth-cache.** Mobile maintains entitlement validity for 30 days post last successful Firestore read; day-31 forces re-auth on next foreground.
- **Six-state entitlement model** (paid / lapsed / offline-grace ≤ 30 d / payment-failed / multi-device / signed-out). State semantics locked in PRD; transitions and triggering events are architecture's to define.
- **Activation event chain anchors.** T0 = mobile auth-state-change → `paid`. T1-coach = OS share-sheet confirmed-dispatch (not share-sheet open). T1-active-player = Cinema Mode opened with view-mode toggled at least once.
- **Cross-language schema enforcement.** `map-config.schema.json` strictly enforced (`additionalProperties: false`) on web (Zod, build-time) AND tooling (jsonschema, runtime / CI). Both contracts are first-class repo artifacts under `packages/contracts/`.
- **Stripe webhook dual-strategy idempotency.** Event-ID dedup via `stripe_events/{event_id}` Firestore document existence check + business-state observation. Already implemented per Epic 4; architecture documents the precise contract.
- **Android-first V1.** iOS deferred to Phase 2 until Apple license validated, FFmpeg-kit iOS support confirmed, and Reader-App posture validated against Apple App Review.
- **No push notifications V1.** No FCM, no APNS. Engagement-pushes are anti-pattern per UX distillate emotional design.
- **14 canonical maps.** Sourced from `apps/tooling/tools/frame_labeler.py:19-34` `MAP_LABELS`. The 15-map reference in legacy `map_config_generator.py` spec is stale.
- **Pricing.** €7.99/mo, €79.90/yr; PCI offloaded to Stripe Checkout; webhook payloads carry only Stripe IDs.

**Brownfield triage (architecture-owned dispositions):**

- Stripe API pin review — 2026-03-25.dahlia → 2026-04-22.dahlia delta; PRD default-to-bump pending architecture changelog review.
- Firebase v12 RN auth migration — target `@react-native-firebase/*` per PRD Decision #5; architecture plans the migration sequence and regression-test scope for the entitlement state machine.
- Foreground Service Android — choose `expo-config-plugin` vs `expo-task-manager`; decision binds before Sprint 3 commits.
- Firestore Security Rules deploy to prod — V1-blocking per PRD; architecture confirms deploy mechanism and rule coverage (Decision #7 extends coverage to `detection_config/*` and `stripe_events/*`).

**Existing-code constraints to preserve (architecture must not regress):**

- `import * as self from './webhooks'` self-namespace pattern in `apps/web/src/lib/stripe/webhooks.ts` — required so `vi.spyOn(webhooksModule, 'handleX')` intercepts intra-module calls. Direct calls bypass the spy due to ESM local-binding resolution. Stories 4.2/4.3 rely on this; do not refactor away.
- Stripe dahlia API webhook event nesting — `parent.subscription_details.subscription`, not the older top-level `invoice.subscription`. Reflected in `apps/web/src/lib/schemas/webhook-events.ts`.
- `firebase_uid` and `plan_id` metadata MUST be present on Stripe Checkout Session AND Subscription (via `subscription_data.metadata`) — webhook handler errors when missing.
- Webhook routing-failure response is **200** with `{routingError: true}` to stop Stripe retries; failed events sit in `stripe_events/{event_id}` for manual replay.
- `.npmrc` `node-linker=hoisted` is REQUIRED — Metro's `disableHierarchicalLookup` cannot traverse pnpm's nested `.pnpm/` store. Do not change without re-validating Expo bundling.
- `packages/contracts/src/index.ts` uses bare imports (no `.js` extensions) — Metro can't do TS-ESM `.js → .ts` mapping.
- `react-native-mmkv` pinned to v3 — v4 needs Nitro Modules (RN 0.83+); v4 on RN 0.81 silently boot-crashes via JSI binding registration failure.
- `EXPO_PUBLIC_AUTH_BYPASS` env var must be unset/false in any release build; injects a fake authed user and skips Firebase auth + subscription checks entirely (development-only).

### Cross-Cutting Concerns Identified

These concerns recur across every architectural decision and define the binding surface between the three deploy units:

1. **Cross-language schema-driven binding (`packages/contracts/`).** JSON Schema is the master at `contracts/{map-config,user-doc}.schema.json`. Zod is auto-generated for the TS surface via `packages/contracts/scripts/generate-zod.mjs`; Python validates directly via `jsonschema`. Architecture confirms the contracts package layout and decides `user-doc` reconciliation (Decision #1).
2. **Single Firebase project + region (europe-west).** Apparent from env conventions but not asserted in code today. Decision #3 escalates assertion + CI guard.
3. **Entitlement state machine.** Web is the sole writer of `users/{uid}` entitlement fields (server-only via Stripe webhooks); mobile reads only. Transition latency target: webhook-driven Stripe-side state change reaches mobile within 5 min under nominal conditions (REL-004). Tolerated webhook delay: ≤ 1 h before paging; > 1 h indicates a webhook-processing fault.
4. **Activation telemetry under privacy-by-construction.** Firebase Analytics events (`activation_timer_started`, `activation_timer_completed`) carry only timestamps and event names; never frame data, voice durations, or raw audio.
5. **Reader-App CI gate.** Build-time, signaling-tier defense-in-depth: direct-import bans, transitive-dependency scan, pricing-string scan (€7.99, €79.90, "subscribe", "buy", "monthly", "yearly", and locale equivalents), and i18n-bundle scan. Architecture places the gate in CI and defines the allowlist.
6. **30-day offline-grace.** Only soft state in the entitlement machine. SQLite (durable rows) + MMKV (cache + checkpoints) split-storage pattern is the implementation surface; architecture confirms the cache-revalidation contract and day-31 expiry semantics.
7. **Brownfield reconciliation.** 7 items, 4 architecture-planned (Stripe pin, Firebase v12 RN auth, Foreground Service plugin, firestore.rules prod deploy); 3 disposed by PRD (Vitest serial-mode workaround, `schema_version: 1` field add, in-flight Sprint 2.5 complete-as-legacy after audit).
8. **`map_config.json` runtime delivery (Decision #2 — moat-shaping).** Firestore-fetched preserves the "ship new maps without a release" lever; Metro-bundled fully closes the device for the privacy claim. Both moats cannot fully coexist; architecture's choice dims one. Hybrid is on the table. PRD does not pre-decide.

## Starter Template Evaluation

### Project context: brownfield — starter selections are historical

Three pre-existing apps were imported into the monorepo with full git history under `apps/{mobile,web,tooling}`. Starter-template selection is therefore **not a forward-looking decision** for this architecture run; it is a record of what each surface inherits from its initial scaffolding plus the active bias against re-init. The PRD's Sprint 2.5 disposition (complete-as-legacy after per-story audit) and the Phase 4 monorepo-import acceptance binding both rule out a re-scaffolding pass.

This section captures (a) what each app got from its starter, (b) decisions architecture must respect because they trace back to the starter, and (c) the rejected-alternatives audit trail (preserved verbatim from the legacy distillates so the rationale is not lost).

### `apps/mobile` — `create-expo-app` blank-typescript template

**Initialization (legacy, already committed):**

```bash
npx create-expo-app@latest Warden --template blank-typescript
```

**What the starter chose for us:**

- **Language & runtime:** TypeScript strict; Expo SDK 54 (pinned in `apps/mobile/package.json`); React Native 0.81.5; React 19.1; `newArchEnabled: true` in `app.json`.
- **Bundler:** Metro, configured with `disableHierarchicalLookup` and `watchFolders=root` for monorepo support. `.npmrc` `node-linker=hoisted` is required because Metro cannot traverse pnpm's nested `.pnpm/` store.
- **Project structure:** `App.tsx` + `index.ts` entry; thin app shell at `src/app/`; feature-sliced layout at `src/features/<slice>/`; cross-cutting primitives at `src/shared/`. Tests co-located with source (`__tests__/` next to subjects).
- **Testing:** jest + jest-expo preset; `transformIgnorePatterns` widened for ESM RN deps.
- **Configuration files:** `app.json` (Expo), `babel.config.js`, `metro.config.js`, `tsconfig.json` (extends `@warden/tsconfig/react-native.json`).

**Architectural decisions added on top of the starter (not from it):**

- NativeWind 4 + Tailwind for styling (`tailwind.config.ts`, `global.css`); explicit choice over Material Design.
- Zustand 5 + zustand/middleware persist with MMKV adapter for state management.
- React Navigation v7 native-stack for navigation.
- expo-sqlite for durable rows + react-native-mmkv (v3 pinned) for KV cache.
- `@wokcito/ffmpeg-kit-react-native` (community fork) auto-linked via RN autolinking; FFmpeg-kit 6.1.4 native AAR, 16-kb page-aligned for Android 15+.
- Firebase JS SDK v12 + `@react-native-google-signin/google-signin` v14 (Web client ID flow).
- Custom HUD design system under `src/shared/components/hud/` (~12 atoms; matches the legacy `warden-mocks` JSX/HTML mockups).

**Starter-related debt architecture must address:**

- **No mobile ESLint config.** `apps/mobile/package.json` `lint` script is an echo placeholder. Phase 7 wires `@warden/eslint-config` through. Architecture surfaces this in cross-cutting source-tree section.
- **`getReactNativePersistence` removed in Firebase v12.** `apps/mobile/src/features/auth/firebaseConfig.ts` imports a relocated/removed symbol. Brownfield item 5 — PRD-resolved disposition: migrate to `@react-native-firebase/*` per Decision #5; architecture plans the sequence in the brownfield-migration section.
- **`EXPO_PUBLIC_AUTH_BYPASS`** dev-mode short-circuit must be hard-disabled for release builds. Architecture surfaces this in the CI gate spec.
- **OpenCV JSI binding stub.** `loadFrameFromPath` throws; tests inject synthetic `FrameLoader`s. V1-load-bearing per Innovation #1; the architecture's pre-PRD performance spike binds whether the binding can ship as a real binding within V1 timeline.

**Rejected alternatives at init (preserved from legacy distillate, not re-elicited):**

- **Obytes / ExpoStarter / custom init templates** — overhead, opinionated, paid → chose `create-expo-app blank-typescript` for minimum-friction start.
- **Material Design styling** — productivity-app look, off-brand for video review → chose NativeWind + React Native Reusables (shadcn/ui for RN) themed dark + accent orange.

### `apps/web` — `create-next-app` minimal

**Initialization (legacy, already committed):**

```bash
npx create-next-app@latest wardenweb --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"
```

**What the starter chose for us:**

- **Framework:** Next.js 16.2.2 with App Router, src/ directory, Turbopack stable default, TypeScript strict, `@/*` import alias (currently `^/src`).
- **Styling:** Tailwind CSS v4 (via `@tailwindcss/postcss`).
- **Linting:** ESLint flat config (`eslint.config.mjs` at the web root; not yet importing `@warden/eslint-config`).
- **Project structure:** `src/app/` for App Router routes; `src/components/` feature folders; `src/lib/` for utilities & Firebase/Stripe clients; `src/contexts/` + `src/hooks/`.
- **TypeScript config:** extends `@warden/tsconfig/next.json` (jsx=preserve, Next plugin).

**Architectural decisions added on top of the starter (not from it):**

- shadcn/ui 4 (Base UI primitives) generated into `src/components/ui/` (NOT a runtime package import; copy-paste ownership). Seven primitives in use today (Button, Card, Dialog, Input, Badge, Alert, Skeleton).
- Firebase 12 client SDK + Firebase Admin 13 (server-only via env-keyed service account; lazy-initialized behind a `Proxy` in `src/lib/firebase/admin.ts`).
- Stripe 22 SDK with API version pinned `2026-03-25.dahlia` (architecture reviews bump to `2026-04-22.dahlia` in Brownfield Item 1 disposition).
- Zod 4 (`'zod/v4'` import path) + react-hook-form for form validation.
- React Context for auth state (deliberate NO global state library — no Redux, no Zustand, no React Query).
- Vitest 4 + jsdom + @testing-library/react for unit/component tests; Playwright reserved for E2E (not yet wired in monorepo CI).
- Conventional Commits via husky + commitlint at the monorepo root.
- All API route handlers export `runtime = 'nodejs'` (firebase-admin and Stripe SDK both need Node).

**Starter-related debt architecture must address:**

- **`apps/web/AGENTS.md` warns "This is NOT the Next.js you know."** Next.js 16 has breaking changes from older training data; AI agents (and the architect) must read `node_modules/next/dist/docs/` rather than rely on prior knowledge of older Next versions. Architecture inherits this: any source-tree or pattern doc that contradicts Next 16's actual behavior must defer to the installed Next docs.
- **`next.config.ts` is empty** (defaults). Phase 6 candidate to add image domains, headers, etc. as needed; not V1-blocking.
- **Stripe API version pin drift** vs installed `@stripe` types — Brownfield Item 1 (PRD-disposed: default-to-bump pending architecture changelog review).
- **`apps/web/src/lib/schemas/subscription.ts`** redeclares its own `subscriptionResponseSchema` instead of importing `@warden/contracts/user-doc` — Decision #6 closes this.

**Rejected alternatives at init (preserved from legacy distillate, not re-elicited):**

- **SaaS boilerplates** (Divjoy / Makerkit / supastarter) — paid $100–400+, excessive features (team billing/admin/email), opinionated non-standard patterns harder for AI agents to navigate → chose `create-next-app` minimal for AI-agent-friendly conventions.
- **Custom payment forms** — Stripe Checkout (full-page redirect) more trusted, handles edge cases → chose Stripe-hosted Checkout.
- **Custom payment-history / upgrade / cancel UI** — duplicates Stripe Customer Portal → delegated to Customer Portal per Sprint Change Proposal 2026-04-16.
- **WebSocket / Firestore `onSnapshot` real-time** — webhook-driven async sufficient; DB is source of truth refreshed on dashboard load → no real-time wiring.
- **Light/corporate SaaS aesthetic** — feels out of place for gaming audience → chose dark theme.

### `apps/tooling` — argparse-based CLI, no boilerplate

**Initialization (legacy, no scaffolding tool used):**

There is no Python starter analog to `create-expo-app` or `create-next-app` for this tooling shape. The codebase grew organically from a single-file CLI into ~10 user-facing/dev tools with shared `utils/`. Module layout (modular CLI scripts under `tools/` + shared helpers under `utils/` + YAML config in `config/`) is a hand-rolled convention captured in `apps/tooling/README.md`.

**What's locked from the as-built state:**

- **Language & runtime:** Python ≥ 3.11 per `apps/tooling/pyproject.toml` `requires-python`.
- **Package manager:** uv (joins root `pyproject.toml` `[tool.uv.workspace] members`).
- **Core deps:** `opencv-python>=4.8,<5`, `numpy>=1.24,<2`, `imagehash>=4.2,<5`, `pyyaml>=6.0,<7`, `questionary>=2.0,<3`, `jsonschema>=4.23.0`.
- **Test framework:** pytest (uv-managed; `pnpm --filter tooling test` shells to `uv run pytest`).
- **CLI library:** argparse (NOT Typer / click — chosen for minimal-deps and stable-stdlib posture).
- **TUI:** questionary (terminal-native; `select`, `text`, `confirm`, `checkbox` primitives).
- **No mypy or ruff yet.** `apps/tooling/package.json` `typecheck` and `lint` scripts are placeholder echoes. Phase 7 wires.

**Starter-related debt architecture must address:**

- **No automated test framework discipline** — pytest is wired but coverage is sparse; tools are manually validated via Tool 4 (`hash_validator`) reports + visual `--preview` inspection. Architecture surfaces this in the test-strategy section but does not block V1 on it.
- **`map_config.json` schema-version field absent** — Brownfield Item 7 (PRD-disposed: add `schema_version: 1` at next regeneration).

**Rejected alternatives at init (preserved from legacy distillate, not re-elicited):**

- **PyQt** — overkill 75–150 MB GPL → chose tkinter (stdlib, zero-install) for diagnostic GUIs.
- **OpenCV highgui** — no toolbar/text inputs → chose tkinter.
- **Dear PyGui** — no built-in image viewer + GPU req → chose tkinter.
- **Typer / click** — additional dep + opinionated patterns → chose argparse for stdlib stability.

### Monorepo-level scaffolding (already locked)

- pnpm workspaces + Turborepo (TS task graph) + uv workspace (Python).
- Root `package.json` declares `engines.node ≥ 20`, `packageManager: pnpm@9.12.0`.
- `.husky/` pre-commit (Prettier on staged files) + commit-msg (commitlint Conventional Commits).
- `.prettierrc` `endOfLine: auto`; `.prettierignore` excludes `apps/mobile/**` (legacy formatting; not yet modernized) and `apps/tooling/**` (Python — not Prettier's concern).
- `turbo.json` task graph: `build`, `typecheck`, `test`, `lint`, `dev` (dev not cached, persistent).
- BMad install at `_bmad/`; output at `_bmad-output/`.

### Selection summary

**No new starter selected.** The architecture inherits three frozen scaffolding choices and the monorepo skeleton built on top of them. Architecture's job is to:

1. Respect existing-code constraints captured in the Project Context section above.
2. Plan the brownfield migration sequences in the Decisions section (Stripe pin, Firebase v12 RN auth, Foreground Service plugin, firestore.rules prod deploy).
3. Decide what the existing scaffolding does NOT close — `packages/contracts/` wiring (Decision #6), `firestore.rules` coverage (Decision #7), single-Firebase-project assertion (Decision #3), and the seven other escalated decisions.

**Note:** Because the apps are already initialized, "project initialization" is NOT a Phase-7 implementation story. The Phase-7 sprint plan starts from the brownfield migration and decision-binding work documented in subsequent sections of this architecture doc.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical (block V1 implementation):**

- **Decision #1** — `users/{uid}` Firestore schema reconciliation (mobile already migrated; close legacy `isPaid` carrier).
- **Decision #2** — `map_config.json` runtime delivery (moat-shaping).
- **Decision #3** — Shared Firebase project + CI guard.
- **Decision #6** — Wire `apps/web` to `@warden/contracts/user-doc`.
- **Decision #7** — `firestore.rules` coverage extended; deploy to prod (V1-blocking).
- **Decision #8** — `detection_config/latest` ownership.
- **Decision #9** — `status` enum trialing handling.
- **Brownfield Item 5** — Firebase v12 RN auth migration to `@react-native-firebase/*` (forcing function).
- **Brownfield Item 6** — Foreground Service Android plugin choice (binds before Sprint 3).
- **Pre-PRD performance spike** — binds NFR PERF-010; gates V1 launch criteria.

**Important (shape architecture, not blocking):**

- **Brownfield Item 1** — Stripe API pin review (default-to-bump per PRD).
- Reader-App CI gate spec (`cross-READER-APP-001`).
- Stripe webhook idempotency contract documentation (already implemented; doc + regression coverage).
- Activation telemetry contract (`cross-ACTIVATION-001/002`).
- Six-state entitlement state machine — transitions and triggering events.

**Deferred (V2 / explicit):**

- iOS support (Phase 2 — gated on Apple license + FFmpeg-kit iOS validation + Reader-App posture against App Review).
- `next.config.ts` headers/image-domains polish (post-V1).
- Custom analytics dashboard (V2 per PRD).
- `--no-tui` headless flag for tooling (V2 per tooling distillate).

### Data Architecture

#### Decision #1 — `users/{uid}` Firestore schema reconciliation [RESOLVED]

**Choice:** **(a) Drop legacy `isPaid` from the contract.** Mobile reads `status` + `current_period_end` directly via `isSubscriptionPaid()` (already implemented in `apps/mobile/src/features/auth/subscriptionService.ts`).

**Rationale:**

- Mobile has already migrated. The `subscriptionService.checkSubscription()` path returns `status ∈ {active, trialing}` AND `current_period_end > now` as paid.
- The cached `useAuthStore.user.isPaid` is a derived TS field on `AuthUser`, NOT a Firestore field — it is computed at the time of last successful Firestore read and persisted in MMKV. Architecture preserves this offline-fallback pattern (see Frontend Architecture section).
- Option (b) — write `isPaid` from web webhook — doubles writes for zero benefit.
- Option (c) — Cloud Function syncing derived `isPaid` — adds operational surface for zero product benefit.

**Schema action:**

- Edit `contracts/user-doc.schema.json`: remove the optional `isPaid` field; tighten `additionalProperties: true → false`; add formal `created_at` and `updated_at` slots (currently rely on `additionalProperties: true` permissiveness — see Decision #1 sub-decision below).
- Re-run `pnpm --filter @warden/contracts build` to regenerate Zod.
- Update `apps/mobile/.env.example` to remove the legacy `users/{uid}.isPaid` documentation comment.

**Sub-decision: tighten `additionalProperties` from `true` to `false`?**

**Yes**, but only after `created_at` and `updated_at` are formally added to the schema as optional `string` fields (Firestore Timestamps are serialized as `{seconds, nanoseconds}` over the JS SDK; the wire shape used by the contract is already abstracted via `subscriptionResponseSchema`'s number projection). The strict mode catches future drift; the explicit `created_at` / `updated_at` slots remove the only legitimate tolerance the lax mode provided.

**Cascading implications:**

- Decision #6 closes once the contract is tightened.
- Decision #9 — see below.
- Sprint 3 story: "Tighten `user-doc.schema.json`; remove `isPaid`; regen contracts; update mobile `.env.example` documentation."

#### Decision #2 — `map_config.json` runtime delivery [RESOLVED]

**Choice:** **(c) Hybrid — bundle `map_config.json` as a Metro asset under `apps/mobile/assets/`, retain Firestore overlay at `detection_config/latest` via version-gated stale-while-revalidate.** Bundled is the always-available baseline; Firestore is the live-update channel.

**Rationale:**

- **Honest moat framing.** The on-device-only privacy contract (PRD PRIV-001) covers VIDEO frames, audio frames, voice annotations, and derived video data. Map fingerprints (per-map hashes computed from training videos by the tooling pipeline) are NOT video data. Firestore-fetching the config does not violate the locked privacy contract.
- **First-launch offline works.** Today the legacy mobile architecture throws `OfflineFirstLaunchError` when no MMKV cache + offline. Hybrid eliminates this — the bundled config is always available. The legacy distillate already mentioned a "bundled default config shipped with app as final fallback"; `docs/architecture-mobile.md` had fallen out of sync. Architecture closes the gap by formalizing the bundled-default.
- **V3 expansion lever preserved.** Adding a 15th map post-V1 is an OTA via Firestore overlay — no Play Store release required. The brief's "tooling expansion moat" claim survives.
- **Fully-closed-device claim is dimmed but architecture is honest about it.** The PRD-locked privacy claim is "no video frames or derived video data on any wire." Architecture publicly positions the hybrid: "Map fingerprints (the config that says 'this hash means horizon') ship with the app and update via Firestore when online; videos never leave the phone." This is what the PRD actually says — the moat that's "dimmed" is one the PRD never asserted.

**Implementation:**

- `apps/mobile/assets/map_config.json` — committed binary; regenerated by `apps/tooling/tools/map_config_generator.py`; updated alongside any release.
- `detectionConfigBootstrap.ts` reads bundled asset on first launch (eliminates the no-cache + offline error path).
- `detectionConfigService.ts` stale-while-revalidate path stays — Firestore overlay is checked when online; cache update gated by `version` field.
- Bundled config carries `schema_version: 1` (closes Brownfield Item 7).
- The sticky `OfflineFirstLaunchError` path is removed; `MalformedRemoteConfigError` stays (as a fallback to bundled when remote payload schema-fails).

**Cascading implications:**

- Decision #7 — `firestore.rules` for `detection_config/*` no longer needs to support unauthenticated bootstrap reads; mobile reads only after auth (post-T0).
- Decision #8 — bundled is the baseline; Firestore is the OTA channel; ownership of `detection_config/latest` becomes a manual operator action (see below).
- `docs/architecture-mobile.md` updates: replace "throws `OfflineFirstLaunchError`" with "falls back to bundled `map_config.json` from app asset bundle."

#### Decision #6 — Wire `apps/web` to `@warden/contracts/user-doc` [RESOLVED]

**Choice:** **YES.** Replace `apps/web/src/lib/schemas/subscription.ts:subscriptionResponseSchema` with an import from `@warden/contracts/user-doc`.

**Rationale:**

- Single source of truth for the wire schema. Decision #1 tightens `user-doc.schema.json`; Decision #6 wires web to consume the tightened schema.
- The contract's wire shape (`current_period_end?: number` Unix seconds) already matches what `GET /api/subscription` projects from the in-Firestore `Timestamp` (`data.current_period_end?.seconds ?? null`).
- Eliminates the brownfield-flagged "schema diverges from `@warden/contracts/user-doc`" debt item.

**Implementation:**

- `apps/web/src/lib/schemas/subscription.ts` becomes a one-liner: `export { UserDocSchema as subscriptionResponseSchema } from '@warden/contracts/user-doc';`
- All call sites — `apps/web/src/app/api/subscription/route.ts`, `apps/web/src/hooks/useSubscription.ts` — keep their imports unchanged (the named export is preserved).
- Existing tests under `apps/web/src/lib/schemas/__tests__/` validate the contract surface still parses webhook handler outputs.
- Sprint 3 story: "Wire `apps/web` to `@warden/contracts/user-doc`; remove redeclared schema; verify Vitest suite passes."

**Cascading implications:**

- Decision #1 must land first (tightens the contract).
- Decision #9 must land first OR concurrently (the contract's `status` enum scope is settled before web imports).

#### Decision #8 — `detection_config/latest` ownership [RESOLVED]

**Choice:** **(a) Manual / out-of-band for V1.** The tooling emits `map_config.json`; the operator (Stephane) uploads to `detection_config/latest` via Firebase CLI when an OTA update between releases is needed.

**Rationale:**

- Decision #2 hybrid changes the urgency: the bundled config is the always-available baseline, so the Firestore overlay is **only** for OTA updates between Play Store releases. The frequency is low (new maps post-V1).
- Option (b) — wire to web-admin — requires a V2 admin UI dependency. PRD defers admin UI to V2; pulling it forward to V1 fights scope discipline.
- Option (c) — tooling-emit (Python writes Firestore directly) — adds prod-write capability to a developer-CLI lab. The tooling lives on Stephane's workstation; granting it Firebase Admin credentials for prod writes inverts the "tooling is a lab" principle. The cleaner separation is: tooling produces the artifact; operator uploads.

**Implementation:**

- Document the upload command in `docs/deployment-guide.md`:

  ```bash
  firebase firestore:set detection_config/latest \
    apps/mobile/assets/map_config.json \
    --project <project-id>
  ```

- Phase-7 follow-up: a `pnpm tooling:deploy-config` script that wraps the upload (still manual trigger, scriptable). Out of V1 scope.

**Cascading implications:**

- Decision #7 — `firestore.rules` for `detection_config/*` keeps `allow write: if false` (only firebase-admin / CLI can write).
- Sprint 3 acceptance: the upload procedure is documented and the V1 release ships with a known-good `map_config.json` payload at `detection_config/latest`.

#### Decision #9 — `status` enum trialing handling [RESOLVED]

**Choice:** **(b) Map `trialing` to `active` at the webhook handler.** Add `customer.subscription.updated` as a defensive event handler. Contract enum stays `'active' | 'past_due' | 'canceled'`.

**Rationale:**

- The six-state entitlement model is locked by PRD. Adding a seventh state expands the surface for zero product benefit — the user-facing experience of `trialing` and `active` is identical (full app access + "active" badge + activation timer fires on T0).
- Stripe's `subscription.status === 'trialing'` happens when a coupon with a Stripe-trial period is configured. Warden's coupon flow uses **deferred-billing copy** ("Vous ne serez pas débité avant le [date]") which Stripe may implement as a `trialing` status depending on coupon definition. Defensive handling is required.
- Web webhook handler today does NOT subscribe to `customer.subscription.updated` (only `invoice.paid`, `invoice.payment_failed`, `customer.subscription.deleted`). If a coupon redemption produces a `trialing` subscription, no webhook fires until the trial converts (`invoice.paid` at trial end) — which is too late for the activation timer.
- Mobile already tolerates `trialing` (`isSubscriptionPaid()` accepts `status ∈ {active, trialing}`) — defense-in-depth survives the migration.

**Implementation:**

- Add `customer.subscription.updated` event subscription in Stripe Dashboard (manual, one-time per environment; documented in `docs/deployment-guide.md`).
- Extend `apps/web/src/lib/stripe/webhooks.ts:routeEvent`:

  ```ts
  case 'customer.subscription.updated':
    return self.handleSubscriptionUpdated(event);
  ```

- New handler `handleSubscriptionUpdated(event)`:
  - Validate via new Zod schema in `webhook-events.ts` (mirror existing dahlia `parent.subscription_details.subscription` nesting).
  - If `subscription.status === 'trialing'`, write `users/{firebase_uid}` `{ status: 'active', plan, current_period_end: trial_end_as_Timestamp, stripe_subscription_id, stripe_customer_id, updated_at: serverTimestamp() }`.
  - If `subscription.status === 'active'`, write the same shape with `current_period_end` from the next-billing date.
  - If `subscription.status === 'past_due'`, write `{ status: 'past_due', updated_at: serverTimestamp() }` (mirrors `handlePaymentFailed`).
  - If `subscription.status === 'canceled'`, no-op (let `customer.subscription.deleted` handle it).
- Mobile-side change: NONE. `isSubscriptionPaid()` already tolerates `trialing` belt-and-suspenders.
- Tests: extend `apps/web/src/lib/stripe/__tests__/webhooks.test.ts` with a `customer.subscription.updated` trialing→active case; preserve the self-namespace import pattern (vi.spyOn requirement).

**Cascading implications:**

- Decision #1 / #6 — the contract's `status` enum stays a strict three-value subset; web's local schema replaces with the contract import.
- Stripe Dashboard subscription-event configuration is now wider; documented in deployment guide.
- The `apps/web/AGENTS.md` test invariant ("self-namespace pattern is required for `vi.spyOn`") survives — the new handler is added inside `webhooks.ts`, called via `self.handleSubscriptionUpdated(event)`.

#### Brownfield Item 7 — `map_config.json` `schema_version` [RESOLVED]

PRD-disposed; architecture confirms the implementation hook:

- `apps/tooling/tools/map_config_generator.py` and `apps/tooling/tools/hash_comparator.py` write `schema_version: 1` at the next regeneration.
- `contracts/map-config.schema.json` adds `schema_version: integer >= 1` as a required field; tighten `additionalProperties: false` survives.
- Re-run `pnpm --filter @warden/contracts build`; regenerated TS Zod surface now requires `schema_version`.
- Mobile's `validateDetectionConfig` (and the bundled-config validator from Decision #2) accepts `schema_version: 1` only for V1; rejection of unknown versions is graceful (falls back to bundled `map_config.json` from the asset bundle).
- Sprint 3 story: "Add `schema_version: 1` to all `map_config.json` writers; bump contract; regen Zod; commit regenerated `map_config.json` payload alongside the schema bump."

### Authentication & Security

#### Decision #3 — Shared Firebase project + CI guard [RESOLVED]

**Choice:** **(c) ONE shared Firebase project + CI-asserted config alignment.**

**Rationale:**

- The cross-surface entitlement contract (web writes `users/{uid}`, mobile reads) requires the shared project. There is no viable two-project path that doesn't bring sync code into scope.
- Region: `europe-west` (GDPR-locked by `apps/web` legacy config).
- "Apparent yes" from env conventions becomes "asserted in CI" — drift is then mechanically caught.

**Implementation:**

- Per-app `.env.example` files keep their `*_FIREBASE_PROJECT_ID` declarations (architecture does NOT introduce a shared-config file because env vars are per-app).
- Phase-7 CI job in `.github/workflows/ci.yml` (file does not exist yet; this is the canonical place to add it):

  ```yaml
  - name: Assert shared Firebase project
    run: |
      WEB_ID=$(grep -E '^NEXT_PUBLIC_FIREBASE_PROJECT_ID' apps/web/.env.example | cut -d= -f2)
      MOBILE_ID=$(grep -E '^EXPO_PUBLIC_FIREBASE_PROJECT_ID' apps/mobile/.env.example | cut -d= -f2)
      if [ "$WEB_ID" != "$MOBILE_ID" ]; then
        echo "Firebase project ID drift: web=$WEB_ID mobile=$MOBILE_ID"; exit 1;
      fi
  ```

- Architecture asserts: any drift between `apps/web/.env.example:NEXT_PUBLIC_FIREBASE_PROJECT_ID` and `apps/mobile/.env.example:EXPO_PUBLIC_FIREBASE_PROJECT_ID` is a CI failure.
- The actual deployed env vars (Vercel + EAS Build) must point to the SAME project ID; the `.env.example` files are the codified contract.

**Cascading implications:**

- The CI job is a pre-V1 nice-to-have (the assertion is true today by manual convention); becomes V1.1-blocking once Phase 7 wires CI.

#### Decision #7 — `firestore.rules` coverage extended + V1-blocking deploy [RESOLVED]

**Choice:** Extend coverage to `detection_config/{docId}` (signed-in read; deny client write) and `stripe_events/{eventId}` (deny client read+write). Deploy to prod before V1 launch (Brownfield Item 2).

**Rationale:**

- Today's rules (`apps/web/firestore.rules`) cover only `users/{uid}` (owner read; deny client write); everything else falls under wildcard deny. Mobile's `detection_config/latest` read currently fails this rule set — but mobile reads work in the dev environment, suggesting either the rules aren't deployed or they were deployed against a different revision. Architecture resolves the conflict by writing the explicit coverage and deploying.
- `stripe_events/*` is server-only (firebase-admin bypasses rules); no client should ever touch it. Explicit deny is defense-in-depth.
- After Decision #2 hybrid, mobile reads `detection_config/latest` only after auth (post-T0) — so the `auth != null` rule is sufficient (no anonymous read needed for bootstrap).

**Implementation:**

`apps/web/firestore.rules` becomes:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // users/{uid} — owner read only; server (firebase-admin) writes via webhooks
    match /users/{userId} {
      allow read:  if request.auth != null && request.auth.uid == userId;
      allow write: if false;
    }

    // detection_config — any authenticated user reads; server-only writes
    match /detection_config/{docId} {
      allow read:  if request.auth != null;
      allow write: if false;
    }

    // stripe_events — server-only; no client access at all
    match /stripe_events/{eventId} {
      allow read, write: if false;
    }

    // catch-all deny
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

V1-blocking deploy:

```bash
cd apps/web && firebase deploy --only firestore:rules --project <project-id>
```

Phase-7 CI workflow `.github/workflows/deploy-firestore-rules.yml` triggers on push to `main` affecting `apps/web/firestore.rules`. Out of V1 scope — V1 deploy is one-time manual.

**Cascading implications:**

- Resolves Brownfield Item 2 (V1-blocking).
- Sprint 3 acceptance: rules deployed to prod; manual smoke test validates mobile reads `detection_config/latest` post-auth and the Firebase Console emulator suite shows the new rules.

#### Reader-App CI gate spec (`cross-READER-APP-001`) [SPECIFIED]

The PRD locks the requirement; architecture specifies the implementation:

**Gate location:** `.github/workflows/ci.yml` (Phase 7) AND a pre-commit hook addition (`apps/mobile/scripts/reader-app-gate.sh`) that runs the same scan.

**Banned direct imports** (regex over `apps/mobile/**/*.{ts,tsx,js,jsx}` with comments stripped):

- `from\s+['"]react-native-iap['"]`
- `from\s+['"]expo-in-app-purchases['"]`
- `from\s+['"]@stripe/stripe-react-native['"]` (Stripe Mobile SDK)
- `from\s+['"]@stripe/stripe-js['"]` (Stripe Web SDK — would not link on RN but ban anyway)

**Banned transitive deps** (`pnpm ls --filter mobile --depth=Infinity` parsed for):

- `react-native-iap`
- `expo-in-app-purchases`
- `@stripe/stripe-react-native`

**Banned strings** (regex over `apps/mobile/src/**/*.{ts,tsx,js,jsx,json}` AND `apps/mobile/assets/i18n/**` if/when i18n bundles exist):

- `€7\.99`, `€79\.90`, `7\.99\s*€`, `79\.90\s*€`
- Case-insensitive: `\b(subscribe|s'?abonner|abonnement|monthly|yearly|mensuel|annuel|buy|acheter)\b`
- Plan-picker UI component imports (lint rule maintained in `@warden/eslint-config`):
  - `@/components/checkout/PlanCard`
  - `@/components/checkout/PlanCta`
  - `@/components/checkout/CouponInput`

**Gate behavior:** Any match fails CI with the matched line + path. Defense-in-depth — does NOT defend against intentional bypass (per PRD signaling-tier framing). Documented in `apps/mobile/RELEASE.md` (file to be created in Sprint 3).

**Allowlist mechanism:** None. There is no legitimate reason any of these imports/strings should appear in mobile artifacts. If a future need arises (e.g., "subscribe to channel" in a context unrelated to monetization), update the regex to be more specific rather than allowlisting.

**Cascading implications:**

- Sprint 3 story: "Implement Reader-App CI gate (script + GitHub Actions workflow); document in `apps/mobile/RELEASE.md`; verify gate passes on the current `apps/mobile` tree."

#### Brownfield Item 5 — Firebase v12 RN auth migration sequence [PLANNED]

Target locked by PRD: `@react-native-firebase/*`. Architecture publishes the migration sequence.

**Migration scope:**

- `apps/mobile/src/features/auth/firebaseConfig.ts` — replace Firebase JS SDK init with RN Firebase auto-config (consumes `google-services.json` (Android) and — Phase 2 — `GoogleService-Info.plist` (iOS)).
- `apps/mobile/src/features/auth/authService.ts` — replace `signInWithEmailAndPassword(auth, ...)` with `auth().signInWithEmailAndPassword(...)`. `onAuthStateChanged(auth, fn)` → `auth().onAuthStateChanged(fn)`. Persistence is automatic in `@react-native-firebase/auth` (Keychain/Keystore-backed); the `getReactNativePersistence` symbol is no longer needed (resolves the forcing-function deprecation).
- `apps/mobile/src/features/auth/subscriptionService.ts` — replace `getDoc(doc(db, 'users', uid))` with `firestore().collection('users').doc(uid).get()`.
- `apps/mobile/src/features/video-processing/detectionConfigService.ts` — same Firestore-API switch.
- `apps/mobile/src/features/auth/useAuthStore.ts` — no change (MMKV persist via Zustand middleware unchanged).

**Sequence (Sprint 3 stories, all V1-blocking):**

1. **Story 3.A — Add deps + prebuild.** Add `@react-native-firebase/app`, `@react-native-firebase/auth`, `@react-native-firebase/firestore`. Run `expo prebuild`. Validate Android build still produces a working bundle (`pnpm --filter mobile exec expo export --platform android` — Phase 4 acceptance smoke test).
2. **Story 3.B — Migrate `firebaseConfig.ts`.** Replace JS SDK init. Smoke test login flow (email/password + Google) on a dev build.
3. **Story 3.C — Migrate `authService.ts`.** Replace `signInWithEmailAndPassword`, `signOut`, `onAuthStateChanged`. Run `pnpm --filter mobile test`; verify all jest tests pass with synthetic FrameLoader injections still working.
4. **Story 3.D — Migrate `subscriptionService.ts`.** Replace Firestore reads. Run all 6 entitlement-state regression tests (one per state) — this is the load-bearing regression scope.
5. **Story 3.E — Migrate `detectionConfigService.ts`.** Replace Firestore reads. Validate stale-while-revalidate cache still works; singleflight semantics preserved (3 inflight gates: initial / background / forced).
6. **Story 3.F — End-to-end manual test.** All 10 PRD journeys (J1–J10) on Android dev build. Sign-off binds Sprint 3.

**Risk fallback:** If migration over-runs Sprint 3, the bail-out is to ship V1 on the current Firebase v11 line. This is conditional on Firebase v12 NOT dropping `getReactNativePersistence` entirely before V1 ships (the forcing function). Current pinned firebase version: `^12.8.0` — minor bumps may drop the symbol. Risk mitigation: pin firebase to a known-safe minor (e.g., `12.8.0` exactly, no `^`) until Story 3.A lands, and monitor the Firebase v12 changelog for the symbol's removal.

**Brownfield Item 2 — `firestore.rules` prod deploy [V1-BLOCKING]:**

Resolved by Decision #7 implementation; deploy command documented above; Sprint 3 acceptance binds.

### API & Communication Patterns

#### Stripe webhook idempotency contract [DOCUMENTED]

Already implemented per `apps/web/src/lib/stripe/webhooks.ts` Epic 4. Architecture binds the contract:

**Strategy 1 — Event-ID dedup:**

- On every webhook, `runTransaction` reads `stripe_events/{event.id}`; if it exists, return `200 { duplicate: true }` and short-circuit.
- Otherwise, create the doc inside the same transaction with `{event_id, event_type, received_at, api_version, livemode}`.
- The transaction makes the dedupe check + create atomic.

**Strategy 2 — Business-state observation:**

- `handleInvoicePaid`: writes are merge writes; re-applying the same event to an already-`active` `users/{uid}` is a no-op-equivalent (same fields, server-stamped `updated_at` differs only by clock).
- `handleSubscriptionDeleted`: explicit no-op if `status` is already `canceled`.
- `handlePaymentFailed`: explicit no-op if `status` is already `past_due` OR `canceled`.
- `handleSubscriptionUpdated` (Decision #9 addition): same merge-write idempotency; trialing→active transitions are a single-write merge.

**Routing failure:** Returns `200 { routingError: true }` to stop Stripe retries; the event sits in `stripe_events/{event.id}` for manual replay via Stripe Dashboard → Webhooks → Events → Resend.

**Existing-code constraints (preserve):**

- `import * as self from './webhooks'` — DO NOT refactor away. `vi.spyOn(webhooksModule, 'handleX')` requires the self-namespace for ESM local-binding interception. Stories 4.2/4.3 rely on this.
- `firebase_uid` and `plan_id` metadata MUST be present on Checkout Session AND Subscription metadata. Webhook handlers throw on missing — this is the orphaned-subscription detection path.
- `parent.subscription_details.subscription` nesting — dahlia API; do not regress to top-level `invoice.subscription`.

**Regression coverage requirement:** PRD-mandated. Sprint 3 story: "Add Vitest cases for each idempotency strategy (event-ID dedup; merge-write business-state observation; routing-failure 200 response). Cover the new `customer.subscription.updated` handler from Decision #9."

#### Brownfield Item 1 — Stripe API pin review [DEFAULT-TO-BUMP]

**Choice:** **Bump from `2026-03-25.dahlia` → `2026-04-22.dahlia`** to match installed `@stripe` types.

**Rationale:**

- Within the dahlia release line, version increments are incremental patches. Major events (e.g., `invoice.subscription` → `parent.subscription_details.subscription`) happened at the codename boundary, not within the codename.
- Architecture-web doc identifies no concrete breaking change between the two pinned dates.
- The `*.test.ts` errors (spread args, implicit any) are TypeScript drift symptoms — bumping the runtime to match the types resolves them.
- PRD default-to-bump per Decision #4 disposition.

**Implementation:**

- `apps/web/src/lib/stripe/server.ts:STRIPE_API_VERSION` bump pin to `2026-04-22.dahlia`.
- Re-run `pnpm --filter web typecheck` — fix any remaining TS errors in `*.test.ts` files (spread args, implicit `any`).
- Re-run full Vitest suite — all webhook event schemas in `webhook-events.ts` must still parse.
- Stripe Dashboard webhook endpoint configured to `2026-04-22.dahlia` (manual operator action; documented in `docs/deployment-guide.md`).

**Verification step (build into the story):**

- Read the Stripe API changelog for the inter-version delta as part of the Sprint 3 story's research task.
- If any concrete breaking change surfaces, fall back to **freeze pin** at `2026-03-25.dahlia` and downgrade installed types to match (this is the explicit fallback per PRD Decision #4 disposition).

**Sprint 3 story:** "Bump Stripe API pin; verify changelog; fix TS test errors; validate webhook event schemas."

#### Activation telemetry contract (`cross-ACTIVATION-001/002`) [SPECIFIED]

PRD locks the anchors; architecture specifies the implementation:

**Events emitted:**

- `activation_timer_started` — fired on mobile auth-state-change → `paid` (T0). Payload: `{ elapsed_seconds: 0, t0_at: <ISO 8601 timestamp> }`. NEVER carries device-identifying info (no IMEI, no Android ID, no install-time random IDs beyond Firebase Analytics's own anonymous instance ID).
- `activation_timer_completed` — fired on T1. Payload: `{ elapsed_seconds: <T1−T0>, t1_at: <ISO 8601 timestamp>, t1_path: 'coach' | 'active_player' }`.

**T1 trigger conditions (dual-T1 from PRD):**

- **`t1_path: 'coach'`** — fired on `expo-sharing` (or equivalent) successful share-intent dispatch. NOT share-sheet open. Coach can cancel the share sheet; only confirmed-dispatch counts.
- **`t1_path: 'active_player'`** — fired on Cinema Mode opened with view-mode toggled at least once (the legacy "Active Player solo path" — J4 path).
- Mutually exclusive per session: whichever fires first wins. If coach exports a clip then later toggles view-mode in Cinema Mode (no export), only the first event is counted.

**Forbidden payload fields (asserted at the FirebaseAnalytics wrapper level):**

- `frame_data`, `frame_url`, `frame_*` — anything frame-shaped
- `voice_*`, `audio_*`, `recording_*` — anything voice/audio-shaped
- `video_*` — anything video-shaped
- `clip_id` — clip metadata is per-device only; no need to cross the wire

**Implementation hook:**

- `apps/mobile/src/features/auth/authService.ts` emits `activation_timer_started` from the `mapFirebaseUser` path when the user transitions into the `paid` state.
- `apps/mobile/src/features/clip-export/exportPipeline.ts` (or equivalent post-share callback) emits `activation_timer_completed` with `t1_path: 'coach'` on `expo-sharing` resolved-success.
- `apps/mobile/src/features/video-playback/CinemaModeScreen.tsx` emits `activation_timer_completed` with `t1_path: 'active_player'` on first view-mode toggle within the Cinema session.
- A thin telemetry wrapper at `apps/mobile/src/shared/services/analytics.ts` enforces the payload allowlist (REJECTS unknown keys at runtime; logs warning in dev, throws in tests).
- Sprint 3 story: "Implement activation telemetry contract; payload allowlist enforced at wrapper level; tests assert no forbidden fields ever reach the FirebaseAnalytics SDK."

### Frontend Architecture

#### Six-state entitlement state machine — transitions and triggering events [SPECIFIED]

PRD locks state semantics; architecture specifies transitions and triggers:

```
                                  +-----------------+
              ┌──────────────────►│   signed-out    │◄──────────────────┐
              │                   +-----------------+                   │
              │                            │                             │
              │ logout                     │ signIn (success)            │ user.delete
              │                            │ + entitlement.checked       │
              │                            ▼                             │
+-------------+--------+      +-----------------------+      +----------+--------+
│   payment-failed     │◄─────│         paid          │─────►│      lapsed       │
+----------------------+      +-----------------------+      +-------------------+
              │                  │       ▲       │
              │ portal-update    │       │       │ subscription.deleted (status:canceled)
              │ → invoice.paid   │       │       │ OR current_period_end < now
              ▼                  │       │       ▼
       returns to paid           │       │  unusable-screen
                                 │       │
              ┌──────────────────┘       └──────────────┐
              │                                          │
              ▼                                          │
+-------------+--------+                                │
│   offline-grace ≤30d │◄─────soft state; full app─────┘
+----------------------+      (cached entitlement)
```

**Triggering events (cause → effect):**

| Event | Source | New state | Notes |
|-------|--------|-----------|-------|
| `signIn(emailPassword)` | mobile `authService.login` | depends on `users/{uid}.status` read | If read succeeds: `paid` / `payment-failed` / `lapsed` / `signed-out` per `isSubscriptionPaid()`. If read fails AND no MMKV cache: stays at `signed-out` (retry path). |
| `signIn(google)` | mobile googleSignInService | same as emailPassword | Web client ID flow via `@react-native-google-signin`. |
| `onAuthStateChanged → user` | Firebase Auth | per Firestore read | First read primes MMKV cache + `cachedAt` timestamp. |
| `onAuthStateChanged → null` | Firebase Auth | `signed-out` | Clears MMKV auth-store. |
| `subscription periodic re-validation` | mobile subscriptionService 60-min interval | per Firestore read | Same `isSubscriptionPaid()` logic. |
| `app foreground` after Customer Portal round-trip | mobile App.tsx focus listener | per Firestore read | Re-fetches `users/{uid}` immediately on resume. |
| `Firestore read fails` (network/permission) | mobile subscriptionService catch | falls back to MMKV-cached `user.isPaid` flag | If `cachedAt < 30 days ago` AND `cached.isPaid === true` → `offline-grace ≤30d`. If `cachedAt ≥ 30 days ago` → `signed-out` (force re-auth). |
| `users/{uid}.status === 'past_due'` (mobile read) | webhook → Firestore → mobile read | `payment-failed` | UI shows warning banner + portal deep-link. App stays usable for `paymentFailedGracePeriodMs` (default 7 days; configurable). |
| `paymentFailedGracePeriodMs` exceeded with status still `past_due` | mobile timer | `lapsed` | Architecture-set grace duration (see sub-decision below). |
| `users/{uid}.status === 'canceled'` (mobile read) | webhook → Firestore → mobile read | `lapsed` | UI shows "subscription required" + portal deep-link. App is unusable. |
| `users/{uid}` doc absent (mobile read) | mobile read returns null | `signed-out` | Force re-auth — likely an orphan auth user without a subscription. |
| `paid → resubscribe (after lapse)` | webhook `invoice.paid` → mobile re-read on foreground | `paid` | Session data preserved per `mobile-AUTH-005`. |
| `multi-device` observation | architecture: NOT ENFORCED in V1 | always `paid` if entitlement is paid | PRD: entitlement is per-user, not per-device. No multi-device kick-out. |
| `day 31 of MMKV cache` | mobile cache-age check on foreground | `signed-out` | Force re-auth on next foreground. |

**Sub-decision: `paymentFailedGracePeriodMs` default**

**Choice: 7 days** (matches Stripe Smart Retries cadence — Stripe retries failed invoices over ~7 days before marking the subscription `past_due → canceled`).

**Rationale:** Aligns the mobile soft-state grace with Stripe's own retry window. After 7 days, if the customer hasn't updated payment, Stripe transitions to `canceled` via `customer.subscription.deleted` → mobile reads `lapsed`. Configurable via a `paymentFailedGracePeriodMs` env var (`EXPO_PUBLIC_PAYMENT_FAILED_GRACE_MS=604800000`) for ops tuning post-launch.

**Implementation:**

- State derivation lives in `apps/mobile/src/features/auth/subscriptionService.ts:deriveEntitlementState(userDoc, cacheMeta)`. Returns one of the six string literals.
- Pure function — testable; one test per state per row in the table above.
- The MMKV cache stores `{user: AuthUser, isAuthenticated, cachedAt: number}` (via the partialized `useAuthStore` persist) — `cachedAt` is the source of truth for offline-grace age.
- Sprint 3 story: "Implement `deriveEntitlementState`; cover all 6 states with unit tests; wire `payment-failed` warning banner; wire `lapsed` 'subscription required' screen; verify J7, J8, J9 manually."

**Cascading implications:**

- The webhook handler must continue to write `users/{uid}.status === 'past_due'` on `invoice.payment_failed` (already implemented).
- The mobile `payment-failed` UI banner reads the warning from `subscriptionService.deriveEntitlementState` — the source-of-truth single function.
- The 30-day offline-grace day-31 expiry is implemented as a check on `cachedAt` at every foreground wake, not as a scheduled timer (no setTimeout — survives app backgrounding without scheduling concerns).

#### Brownfield Item 6 — Foreground Service Android plugin choice [RESOLVED]

**Choice:** **(a) Custom `expo-config-plugin` injecting an Android Foreground Service.**

**Rationale:**

- The processing pipeline is JS-based (`processingPipeline.ts` orchestrates FFmpeg subprocess + OpenCV JSI calls). It must run in the **main JS context**.
- `expo-task-manager` runs JS in a separate headless context — but the FFmpeg/OpenCV JSI bindings cannot be shared across the headless context boundary. Cross-context state is fragile and would require a fundamental redesign of the processing pipeline.
- Custom `expo-config-plugin` injects native Android service-launching code into the prebuild output (`AndroidManifest.xml` foreground-service permissions + a foreground service class). The service hosts the main JS context for processing duration with a sticky notification.
- This matches the legacy mobile distillate's "Foreground Service Android keeps UI responsive while processing in background."

**Implementation:**

- `apps/mobile/plugins/with-foreground-service.js` — Expo config plugin. Modifies `AndroidManifest.xml` to declare `<service android:name=".WardenProcessingService" android:foregroundServiceType="dataSync"/>` and adds `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_DATA_SYNC` permissions.
- `apps/mobile/android/app/src/main/java/team/warden/mobile/WardenProcessingService.kt` (generated post-`expo prebuild`) — sticky notification "Analyse en cours…" with progress percentage from MMKV `processing.<sessionId>.stage`.
- `apps/mobile/src/features/video-processing/processingPipeline.ts` calls into the service via a JSI bridge module to start/stop the foreground state.
- Notification channel: `processing` (low importance — non-disruptive).
- Service lifecycle: started on `runProcessingPipeline` entry; stopped on pipeline completion or error (regardless of pipeline outcome — never leak the service).

**Sprint 3 story:** "Implement `with-foreground-service` config plugin; wire pipeline start/stop; manual test J2 (interruption + resume) on Android dev build with Battery Optimization both enabled and disabled."

**Cascading implications:**

- Decision binds before Sprint 3 commits per PRD.
- iOS Phase 2 architecturally requires a different binding strategy (`BGTaskScheduler` background-fetch tasks with state checkpointing); architecture defers iOS foreground-task design to Phase 2 readiness review.

### Infrastructure & Deployment

#### Pre-PRD performance spike [SPIKE BOUND]

Architecture's load-bearing first deliverable. Binds NFR PERF-010; gates V1 launch.

**Spike scope:**

1. **Build a real OpenCV JSI binding.** Replace the `loadFrameFromPath` stub with a real implementation using `react-native-fast-opencv` (already a dep in `apps/mobile/package.json`; the binding is partially wired but the `loadFrameFromPath` entry point throws). Goal: `loadFrameFromPath(path) → FrameBuffer`.
2. **Run the existing pipeline end-to-end** on the reference device — Poco X5 (Snapdragon 695, 6 GB RAM, 6.67"; Android 13). Source: a 1h20 reference EVA After-h video (architecture-team-supplied; not committed to repo).
3. **Measure NFRs:**
   - PERF-002 — auto-slice ≤ 5% of source duration (1h20 → ≤ 4 min).
   - PERF-003 — view-mode toggle ≤ 100 ms.
   - PERF-004 — Cinema Mode cold-start ≤ 1.5 s.
   - PERF-005 — clip export ≤ 2× clip duration (Mobile-tier; 30 s clip → ≤ 60 s encode).
4. **Bind PERF-010** with the measured number for the reference device.
5. **Validate accuracy floors:**
   - Map ID accuracy ≥ 95% on an unseen test set (the legacy `hash_validator` regression suite is the measurement tool; see `apps/tooling/tools/hash_validator.py`).
   - Round-boundary detection ≥ TBD% (PRD's TBD; spike sets the floor — anchored to the legacy tooling target "100% black-screen-transition detection with 0 false positives" and allowing the floor to be set lower if the on-device port shows real-world degradation).

**Spike outcomes & ladder:**

| Outcome | Ladder rung | Implication |
|---------|-------------|-------------|
| **Pass** — all 4 PERF NFRs met on reference device with real JSI binding | None — V1 launches with auto-slice on | PRD inherits the measured PERF-010 number; round-boundary accuracy floor binds as measured. |
| **Partial fail** — PERF-002 or PERF-005 over budget by < 50% | Rung 1: lower auto-slice frame-sampling rate | Re-measure; if pass, V1 launches with reduced sampling rate documented as architectural constraint. PRD `mobile-AUTO-SLICE-001` adds a "with reduced sampling on weak hardware" clause. |
| **Partial fail** — PERF-003 or PERF-004 over budget | Rung 2: drop Minimap+HUD overlay rendering on weak hardware (gated by device profile) | View modes degrade to Full + Minimap (no HUD overlay). PRD `mobile-CINEMA-002` adds a graceful-degradation clause: device-profile-gated. |
| **Hard fail** — JSI binding does not ship as real binding within V1 timeline | Rung 3: defer auto-slice to V2; V1 ships manual-clip-only | `mobile-AUTO-SLICE-*` FRs become V2; `mobile-CARD-*` graceful-degradation: card view hides auto-sliced rounds, exposes timeline-only manual-clip flow. PRD activation timer T1-coach via manual-clip path becomes the only path. **V1 launches.** |
| **FORBIDDEN** — fall back to cloud CV | NEVER | Breaks Innovation #1 (privacy + lower marginal cost). Architecture asserts this is forbidden regardless of spike outcome. |

**Spike deliverable artifact:** `_bmad-output/architecture-spike-perf-floor.md` — a separate file (not in this overview architecture document; the spike report is detailed enough to warrant its own artifact). Carries the measured numbers, the device profile, the ladder-rung verdict, and the regression-test fixtures used.

**Spike timing:** First Sprint 3 work item, before any other Sprint 3 stories commit. Spike completion gates the rest of Sprint 3 scope finalization.

**Cascading implications:**

- All Sprint 3 mobile story scope depends on the spike outcome.
- PRD NFR PERF-010 is inherited from spike result; PRD updates post-spike.
- The OpenCV JSI binding spec lands in this architecture doc's Implementation Patterns section (next step) once the spike confirms the binding shape.

#### iOS Phase 2 deferral [LOCKED — DEFERRED]

PRD-locked: V1 is Android-only. iOS gates:

1. Apple Developer License validated (admin / legal action).
2. FFmpeg-kit-react-native fork (`jdarshan5`) iOS support confirmed (currently focused on Android maintenance; Plan B per brief is a custom native module via Expo Modules API).
3. Reader-App posture validated against Apple App Review (the structural test — `cross-READER-APP-001` CI gate must pass an actual review).

**iOS Phase 2 architectural readiness deliverables (post-V1):**

- Expo prebuild iOS validation; FFmpeg-kit iOS link smoke test.
- Foreground-service equivalent (iOS uses `BGTaskScheduler` + state checkpointing — different design than Android Foreground Service).
- App Review submission rehearsal.

**V1 architecture asserts:** all mobile decisions (codebase, data layer, native module choice, Foreground Service plugin, JSI binding) are **cross-platform-ready**. No Android-only patterns introduced. iOS Phase 2 work is glue — not refactor.

#### CI/CD additions [PHASE-7 BACKLOG, V1-ENABLEMENT]

The repo has no `.github/workflows/` today. Architecture asserts the following workflows for V1 readiness (V1-blocking subset called out):

| Workflow | Trigger | V1-blocking? | Notes |
|----------|---------|--------------|-------|
| `ci.yml` (lint + typecheck + test + format) | PR + push | No (manual locally) | Reads `pnpm typecheck && pnpm test && pnpm format:check`. Includes Reader-App gate (Decision #7 spec) and shared-Firebase-project assertion (Decision #3). |
| `deploy-firestore-rules.yml` | push to main affecting `apps/web/firestore.rules` | No (V1 deploy is one-time manual; Brownfield Item 2) | Auto-deploys via `firebase deploy --only firestore:rules`. Becomes blocking post-V1.1. |
| `deploy-web.yml` | push to main affecting `apps/web/**` | No (Vercel auto-detects) | Belt-and-suspenders for Vercel-hosted web. |
| `mobile-build.yml` | manual | No | `expo prebuild` + `expo export` smoke (Phase 4 acceptance regression). |
| `contracts-codegen-check.yml` | PR touching `contracts/**` | No | Runs `pnpm contracts:build` and fails if `packages/contracts/src/generated/*` is dirty (catches forgotten regenerations). Becomes blocking post-V1.1. |
| Reader-App gate (in `ci.yml`) | every PR + push | YES (V1-blocking) | Per Decision #7 spec. |

**V1-blocking V0 alternatives (until CI lands):**

- Reader-App gate: pre-commit hook (`apps/mobile/scripts/reader-app-gate.sh`) runs the same scan; engaged via `.husky/pre-commit`. Enforced manually until CI takes over.
- Shared Firebase project assertion: README + deployment guide documents the convention; manual verification at deploy time.

### Decision Impact Analysis

**Implementation sequence (Sprint 3 — V1):**

1. **Pre-PRD performance spike** (gates everything else; binds PERF-010).
2. **Foreground Service config plugin** (Brownfield Item 6 — binds before Sprint 3 commits).
3. **Firebase v12 RN auth migration** (Brownfield Item 5 — Stories 3.A → 3.F; load-bearing for entitlement state machine).
4. **Decision #1 + Decision #6 + Decision #9** as a coordinated triple — schema tighten → wire web → trialing handler. One PR per step but the triple lands together.
5. **Decision #2 (hybrid `map_config.json`) + Brownfield Item 7 (`schema_version`)** — bundled asset + schema bump regenerated together.
6. **Decision #7 (firestore.rules extended) + Brownfield Item 2 (prod deploy)** — V1-blocking deploy.
7. **Decision #8 (manual operator action)** — documented; no code change.
8. **Brownfield Item 1 (Stripe API pin bump)** — independent; can land in parallel with the Firebase migration.
9. **Activation telemetry contract + Reader-App CI gate** — implemented in Sprint 3; gate engages on Sprint 3 PRs.
10. **Six-state entitlement state machine** (`deriveEntitlementState`) — depends on Decision #1/#6/#9 landed.

**Cross-component dependencies:**

- **Decision #2 hybrid** unblocks **Decision #7 firestore.rules** (mobile reads `detection_config/latest` post-auth, not at bootstrap — `auth != null` rule is sufficient).
- **Decision #1 schema tighten** unblocks **Decision #6 wire web to contract** unblocks **Decision #9 trialing in webhook**.
- **Brownfield Item 5 Firebase migration** must land before the **six-state entitlement machine** can be tested end-to-end (the migration touches `subscriptionService.ts` which `deriveEntitlementState` lives in).
- **Pre-PRD performance spike outcome** binds PERF-010 and dictates whether the auto-slice FRs ship in V1 or defer to V2 (Innovation #1 ladder rung 3).

**What this section does NOT decide (deferred to Implementation Patterns step):**

- The OpenCV JSI binding's detailed API surface — set by the spike.
- The detection pipeline's checkpoint resume semantics — already in `processingPipeline.ts`; documented in next step.
- The contracts codegen pipeline's exact CI hooks — Phase-7 backlog item.
- The Mobile/Web shared design-token strategy — out of architecture's scope; UX design (Phase 6 step 4) handles it.

## Implementation Patterns & Consistency Rules

These patterns prevent AI agents working on different surfaces (or different parts of the same surface) from making divergent choices that would conflict at integration time. Each pattern is marked **[LOCKED]** (already in the codebase; must preserve) or **[NEW]** (set by this architecture; introduced in step 4 or here).

The three surfaces have **deliberately different conventions** in some areas because they target different runtimes (Python tooling, Next.js web, Expo/RN mobile). Cross-surface invariants are called out explicitly. When an agent is working in one surface, the surface-local convention wins; when crossing surfaces (contracts, Firestore, telemetry), the cross-surface invariant wins.

### Naming Patterns

#### Database / Persistence Naming

**Firestore (cross-surface persistence) [LOCKED]:**
- Collection names: `users`, `stripe_events`, `detection_config` — lowercase plural snake_case. (Note: `detection_config` is a single-doc collection by convention; doc id is `latest`.)
- Document field names: **snake_case** to match Stripe webhook payloads (no conversion at the boundary). Example: `current_period_end`, `stripe_subscription_id`, `created_at`, `updated_at`.
- Document IDs: Firebase Auth UID for `users/{uid}`; Stripe event ID for `stripe_events/{event_id}`; literal string `latest` for `detection_config/latest`.
- Reason snake_case in Firestore (despite TS being camelCase): Stripe payloads are snake_case; converting at the boundary would create three places where field names exist (Stripe → wire-decoded → Firestore-stored). Keeping snake_case in Firestore eliminates one transform.

**Mobile SQLite [LOCKED]:**
- Table names: snake_case plural — `sessions`, `map_segments`, `clip_exports`, `audio_comments`.
- Column names: snake_case singular — `session_id`, `start_time_ms`, `created_at`.
- Foreign-key columns: `{referenced_table_singular}_id` — `session_id`, `map_segment_id`, `clip_export_id`. Reason: matches the convention so a reader can infer the referenced table from the column name without consulting the schema.
- Indexes: `idx_{table}_{column}` — `idx_map_segments_session`, `idx_clip_exports_segment`. Located alongside their table definitions in `apps/mobile/src/shared/services/database.ts`.
- Schema migrations: bump version + idempotent + reversible per Story 7.1 convention. `PRAGMA foreign_keys = ON` is set globally; `journal_mode = WAL` for performance.

**Mobile MMKV [LOCKED]:**
- Key convention: **dot-notation, grouped by feature** — `auth.token`, `auth.user`, `prefs.viewMode`, `prefs.minimapHud`, `prefs.exportQuality`, `prefs.sortOrder`, `detection.config`.
- Processing pipeline checkpoints: `processing.<sessionId>.<field>` — e.g., `processing.<sid>.events`, `processing.<sid>.gameSegments`, `processing.<sid>.mapIdentifications`, `processing.<sid>.duration`, `processing.<sid>.segmentIds`, `processing.<sid>.segmentData`, `processing.<sid>.stage`. Cleared on success.
- Zustand-persisted store keys: `auth-store`, `session-store` (Zustand `persist` middleware default name → MMKV key). NOT dot-notation — Zustand owns these.
- `<sessionId>` MUST match the regex `/^[a-zA-Z0-9_-]+$/` (the path-traversal hardening from `apps/mobile/src/shared/services/ffmpeg.ts:assertSafeSessionId`). Same regex enforced anywhere a session ID becomes part of a filesystem path or storage key.

**Web (no SQL store) [LOCKED]:**
- All persistence via Firestore (above).
- Sessions: opaque Firebase Admin sessionCookie (no second persistence layer); revocation via `verifySessionCookie(cookie, true)`.

#### Code Naming

**Mobile (TypeScript) [LOCKED]:**
- Components: `PascalCase.tsx` (e.g., `LoginScreen.tsx`, `CardViewScreen.tsx`, `Button.tsx`).
- Modules / hooks / services: `camelCase.ts` (e.g., `authService.ts`, `useAuthStore.ts`, `processingPipeline.ts`).
- Folders: `kebab-case` (e.g., `audio-commentary/`, `video-processing/`, `clip-export/`).
- Domain types: `PascalCase` exported from `src/shared/types/index.ts` (e.g., `Session`, `MapSegment`, `ClipExport`, `AudioComment`, `ViewMode`). Match SQL columns 1:1 — **no DTO mapping layer**; the persistence shape IS the domain type. (Note: this differs from the web side, which transforms via Zod at the boundary.)
- Hook naming: `use<Concern>` (e.g., `useAuth`, `useVideoImport`, `useSessionStore`).
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `DETECTION_CONFIG_DOC_PATH`, `DETECTION_CONFIG_STORAGE_KEY`).

**Web (TypeScript) [LOCKED]:**
- Components: `PascalCase.tsx` (e.g., `SubscriptionCard.tsx`, `EmailSignInForm.tsx`, `Header.tsx`).
- Utility modules in `lib/`: `kebab-case.ts` (e.g., `lib/stripe/server.ts`, `lib/pricing/plans.ts`, `lib/firebase/admin.ts`).
- Folders: feature folders `kebab-case/` (e.g., `auth/`, `checkout/`, `dashboard/`); shadcn primitives lowercase `ui/` with `kebab-case.tsx` filenames matching shadcn's default.
- Hooks: `useAuth`, `useSubscription` — `use<Concern>`.
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `STRIPE_PLANS`, `AUTH_COOKIE_NAME`).
- Server-only modules MUST start with `import 'server-only';` so accidental client imports fail the build.
- Zod schemas: `<noun>Schema` exported as `subscriptionResponseSchema`, `invoicePaidSchema`, `subscriptionDeletedSchema`. Imports use `'zod/v4'` (the v4 candidate path), NOT `'zod'`.

**Tooling (Python) [LOCKED]:**
- Files: `snake_case.py` (e.g., `map_config_generator.py`, `hash_validator.py`, `frame_labeler.py`).
- Functions / variables: `snake_case` (e.g., `consensus_from_hashes`, `load_maps_from_videos`, `text_anchor_width`).
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `MAP_LABELS`, `IMAGE_EXTENSIONS`).
- Classes: `PascalCase` (rare — most modules are stateless pure functions; the only stateful classes are tkinter GUI apps like `InspectorApp(tk.Tk)`).
- Module entry pattern: `run()` for core logic returning results + `main()` for CLI entry parsing args. Tools are runnable both as scripts and via `python -m tools.<name>`.

**Cross-surface contract field names [NEW]:**
- The `contracts/*.schema.json` files use **snake_case** for all fields (matching Firestore + Python conventions).
- Auto-generated Zod (`packages/contracts/src/generated/*.ts`) preserves snake_case key names — TS callers that want camelCase MUST transform explicitly via Zod `.transform()` at the boundary.
- The legacy `apps/web/src/lib/firebase/` directory contains Zod `.transform()` helpers that convert snake_case Firestore reads into camelCase TS objects. After Decision #6 lands, web's `useSubscription` hook continues to receive camelCase (transform happens at the API boundary, not at the contract).

#### API Naming

**Web HTTP routes [LOCKED]:**
- Path segments: `kebab-case` (e.g., `/api/auth/session`, `/api/checkout/coupon`, `/api/checkout/session`, `/api/subscription/portal`, `/api/webhooks/stripe`).
- Path-parameter format: Next.js convention `[id]` (none used in V1 — all routes are flat).
- HTTP methods: standard semantics. `POST /api/auth/session` creates; `DELETE /api/auth/session` destroys.
- Request body: JSON; field names **camelCase** at the wire boundary (e.g., `{idToken, planId, couponCode}`). Transformation to snake_case happens server-side when writing to Firestore.
- Response body: JSON envelope (see Format Patterns below).

**Cross-surface event naming [NEW]:**
- Firebase Analytics events: `snake_case` (e.g., `activation_timer_started`, `activation_timer_completed`).
- Stripe webhook event types: dot-namespaced lowercase per Stripe's convention (e.g., `invoice.paid`, `customer.subscription.deleted`, `customer.subscription.updated`, `invoice.payment_failed`). Don't rename or alias.

### Structure Patterns

**Project Organization [LOCKED]:**
- Mobile: **feature-sliced** — `src/features/<slice>/` one folder per epic-level concern; cross-cutting primitives in `src/shared/`. Features NEVER import other features; cross-feature communication goes through Zustand stores or `src/shared/services/`.
- Web: **App Router + component feature folders** — `src/app/` for routes (URL ≡ folder), `src/components/<feature>/` for UI feature folders, `src/lib/<concern>/` for utilities & external clients.
- Tooling: each tool standalone in `tools/<tool>.py` OR sub-package `tools/<tool>/` with `__main__.py` + `app.py` + helpers; shared helpers in `utils/<concern>.py`; shared interactive widgets in `tools/common/`.
- **No mobile→tooling code path. No web→tooling code path.** Tooling is a CLI lab, not a runtime dependency. The only artifact that crosses is `map_config.json` (the cross-language contract).

**Test Co-location [LOCKED]:**
- Mobile: `src/features/<slice>/__tests__/<subject>.test.ts` — co-located `__tests__` directory next to the subject's source.
- Web: `<subject>.test.ts(x)` next to `<subject>.ts(x)` — co-located file.
- Tooling: `tests/` at the package root with fixtures under `tests/fixtures/`.
- Reason for the difference: jest-expo expects `__tests__/` directories (Jest's default discovery); Vitest finds `*.test.ts(x)` files anywhere via glob. Neither convention crosses surface boundaries; agents must use the right one for the surface.

**Configuration File Organization [LOCKED]:**
- Per-app config files at the app root: `apps/<app>/{tsconfig.json, package.json, eslint.config.mjs, .env.example, ...}`.
- Tooling YAML config: `apps/tooling/config/config.yaml` (single source of tunable params); CLI args override config (`arg if arg is not None else config.get(...)`).
- Mobile Expo config: `apps/mobile/app.json` (Expo-managed) + `apps/mobile/plugins/` for config plugins.
- Web Next.js config: `apps/web/next.config.ts` (currently empty defaults).
- Monorepo root: `package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `turbo.json`, `commitlint.config.ts`, `.prettierrc`, `.prettierignore`, `.npmrc`.

**Static Asset Organization [LOCKED]:**
- Mobile: `apps/mobile/assets/` — icons, splashes, fonts. **NEW: `apps/mobile/assets/map_config.json`** lands here per Decision #2 hybrid (bundled-as-Metro-asset baseline).
- Web: `apps/web/public/` — Next.js convention.
- Tooling: outputs land in `apps/tooling/output/<video_stem>/` per the video-named-output-subfolders convention.

**Documentation Placement [LOCKED]:**
- Architecture / overview docs: repo root `docs/` (this directory; created Phase 5b).
- Per-app legacy docs: `apps/<app>/docs/` for app-specific developer docs that legacy callers may still consume (`apps/tooling/docs/` notably; `apps/web/AGENTS.md` for the load-bearing Next 16 warning).
- BMad planning artifacts: `_bmad-output/`.
- Architecture-spike artifacts (e.g., the pre-PRD performance spike report): `_bmad-output/architecture-spike-<topic>.md`.

### Format Patterns

#### Wire Formats

**Web HTTP envelope [LOCKED]:**

```jsonc
// Success
{ "data": <object | null> }

// Error
{ "error": { "code": "<UPPER_SNAKE>", "message": "<human readable>" } }
```

Standard error codes (from `docs/api-contracts-web.md`): `INVALID_REQUEST`, `INVALID_TOKEN`, `INVALID_SIGNATURE`, `UNAUTHENTICATED` / `NO_SESSION` / `SESSION_EXPIRED` / `SESSION_REVOKED` / `UNAUTHORIZED`, `MISSING_STRIPE_PRICE_ID`, `COUPON_INVALID`, `COUPON_LOOKUP_FAILED`, `CHECKOUT_FAILED`, `WEBHOOK_NOT_CONFIGURED`, `NO_CUSTOMER`, `PORTAL_SESSION_FAILED`, `SUBSCRIPTION_FETCH_FAILED`. Don't introduce new codes without a corresponding entry in `docs/api-contracts-web.md`.

**HTTP status codes [LOCKED]:**
- `200` — success (including `{duplicate: true}` and `{routingError: true}` from the webhook handler, which return 200 to stop Stripe retries).
- `400` — validation failures (Zod schema fail) and signature failures (`INVALID_SIGNATURE`).
- `401` — auth failures (any `UnauthorizedError` subtype).
- `404` — `NO_CUSTOMER` only (user doc missing OR `stripe_customer_id` missing). Note: `GET /api/subscription` returns `200 { data: null }` when the user doc is missing, NOT 404 — by design.
- `500` — server-side errors (`COUPON_LOOKUP_FAILED`, `CHECKOUT_FAILED`, `PORTAL_SESSION_FAILED`, `SUBSCRIPTION_FETCH_FAILED`, `WEBHOOK_NOT_CONFIGURED`).

**Date / time formats [LOCKED]:**
- Firestore: `Timestamp` (Firestore SDK type — `{seconds, nanoseconds}` over the JS SDK).
- Stripe: Unix seconds (integer).
- Wire (JSON API responses): `number` (Unix seconds) — see `subscriptionResponseSchema.current_period_end: number`.
- UI: `Intl.DateTimeFormat` (no date library — chosen to keep the bundle small per legacy WardenWeb decision).
- Mobile SQLite: ISO 8601 strings (`created_at`, `updated_at` columns).
- Server logs: ISO 8601 strings.

**JSON field naming at boundaries [LOCKED]:**
- Stripe ↔ Firestore: snake_case (no transform at the boundary).
- Firestore ↔ Web TS: snake_case in Firestore; transformed to camelCase via Zod `.transform()` at the boundary (helpers in `apps/web/src/lib/firebase/`).
- Web TS ↔ wire (HTTP responses): the wire envelope is camelCase (e.g., `{ data: { status, plan, current_period_end, stripe_customer_id, stripe_subscription_id } }`). Note: `current_period_end` and `stripe_*` keep snake_case at the wire because the schema (and downstream contract) define them that way. Use Zod `.transform()` to camelCase only inside the React components if needed; the `useSubscription` hook returns the snake_case shape today.
- Web TS ↔ Tooling-emitted contracts (`map_config.json`): snake_case at the JSON; auto-generated Zod preserves snake_case key names; consumer transforms if it wants camelCase.
- Mobile TS ↔ SQLite: snake_case in both layers (no transform — domain types ARE the persistence shape).

**Boolean / null representations [LOCKED]:**
- TS / JSON: `true` / `false` / `null`. Never `1` / `0` for booleans. Never `""` / `0` for "absent" — use `null` or omit the key.
- Python (tooling): `True` / `False` / `None`. JSON outputs match TS conventions.
- Firestore: `true` / `false` / absent (omitted keys vs. explicit `null`). Webhook handlers MUST omit fields rather than write `null` to keep merge writes clean.

#### Cross-Language Contract Conventions [NEW]

- JSON Schema is the master at `contracts/<schema>.schema.json`. Edit ONLY here; never edit `packages/contracts/src/generated/*.ts` directly.
- Re-run `pnpm --filter @warden/contracts build` after schema edits.
- Commit schema + regenerated TS together so reviewers see the contract bump and the consumer-visible diff in one PR.
- Validation in Python: `jsonschema` against the JSON Schema. Validation in TS: the auto-generated Zod schemas.
- Strict mode: `additionalProperties: false` on `map-config.schema.json` (locked); `user-doc.schema.json` becomes strict per Decision #1 after `created_at` / `updated_at` are formally added.

### Communication Patterns

#### Inter-Service Communication

**Mobile → Firebase Auth [LOCKED]:**
- Path: `apps/mobile/src/features/auth/firebaseConfig.ts` initializes (post-migration: `@react-native-firebase/auth`); `authService.ts` orchestrates login/logout/listenToAuthChanges; `subscriptionService.ts` reads `users/{uid}` after auth-state-change.
- Auth tokens: stored automatically by `@react-native-firebase/auth` post-migration (Keychain/Keystore); persistence is automatic. PRE-migration: legacy `getReactNativePersistence` symbol — superseded.
- Periodic re-validation: 60 min interval (`subscriptionService.startPeriodicRevalidation`).

**Mobile → Firestore reads [LOCKED]:**
- `users/{uid}` — read on auth-state-change, periodic revalidation, and app-foreground after Stripe portal round-trip. Network failures fall back to MMKV-cached `user.isPaid` per the entitlement state machine (Decision: 30-day offline-grace; day-31 force re-auth).
- `detection_config/latest` — read post-auth via stale-while-revalidate cache (`detectionConfigService.ts`). Three singleflights guard `inflightInitialFetch`, `inflightBackgroundRefresh`, `inflightForcedRefresh`.

**Web → Firestore writes [LOCKED]:**
- ONLY via firebase-admin (server-side bypassing rules). Client writes denied at the rules layer (Decision #7).
- Webhook handlers use `runTransaction` for the dedupe + write atomicity (Strategy 1 idempotency).
- Merge writes (NOT replace writes) — server-stamped `updated_at` differs only by clock for re-applied events (Strategy 2 idempotency).

**Stripe → Web webhooks [LOCKED]:**
- Endpoint: `POST /api/webhooks/stripe`.
- Body: raw text (NOT JSON-parsed by framework; `request.text()` so signature check operates on bytes).
- Signature verification via `stripe.webhooks.constructEvent` with `STRIPE_WEBHOOK_SECRET`.
- Subscribed events (Stripe Dashboard config): `invoice.paid`, `customer.subscription.deleted`, `customer.subscription.updated` (added per Decision #9), `invoice.payment_failed`.
- Idempotency: Strategy 1 (event-ID dedup at `stripe_events/{event.id}`) + Strategy 2 (business-state observation merge writes).
- Routing failure → 200 `{routingError: true}` (stops Stripe retries; manual replay via Dashboard).
- Required metadata: `firebase_uid` + `plan_id` on Checkout Session AND Subscription. Handlers throw on missing.

#### State Management Patterns

**Mobile state stores [LOCKED]:**
- One Zustand store per feature with `persist` middleware + MMKV adapter.
- Stores expose: state shape, `set*` actions, `reset` action. NO async logic in stores — async lives in hooks/services.
- Partialize what's persisted to MMKV (e.g., `useAuthStore` partializes to `{user, isAuthenticated, cachedAt}` only; transient `isLoading` stays in-memory).
- Cross-store coordination via shared services (`shared/services/{database,ffmpeg,opencv,storage}.ts`), NOT direct store imports.
- When a store needs Firestore data: a hook in the feature folder calls the feature's service module; the service calls Firestore; the hook commits to the store.

**Web state [LOCKED]:**
- React Context for auth state ONLY (`AuthContext` provides `{user, loading, error}` from Firebase `onAuthStateChanged`).
- Per-page hooks for data fetching (`useSubscription` fetches `/api/subscription` once on mount, parses with Zod, returns `{subscription, loading, error}`).
- NO global state library. NO Redux. NO Zustand. NO React Query. — deliberate per legacy.
- Cancellation flag on closures to avoid setting state after unmount.

**Tooling state [LOCKED]:**
- Stateless pure functions (np in → np out) for shared utils.
- Tk-based interactive tools are the only stateful UI (`InspectorApp(tk.Tk)`, `MinimapZoneSelectorApp(tk.Tk)`, `MinimapViewModeApp(tk.Tk)`).
- TUI launcher (`wardentooling.py`) persists last-run args at `.warden_last_run.json` (gitignored).

#### Telemetry Patterns

**Activation telemetry payload allowlist [NEW — see Decision #9 / `cross-ACTIVATION-002`]:**
- Wrapper at `apps/mobile/src/shared/services/analytics.ts` enforces the allowlist.
- Permitted fields: `elapsed_seconds`, `t0_at` (ISO 8601), `t1_at` (ISO 8601), `t1_path: 'coach' | 'active_player'`.
- Banned field-name regexes (rejected at runtime; throws in tests, warns in dev): `frame_*`, `voice_*`, `audio_*`, `recording_*`, `video_*`, `clip_id`.
- Architecture asserts: any new analytics event going through this wrapper MUST declare its payload schema; unknown keys fail.

**Crash reporting (Sentry/Crashlytics if added in V2) [NEW]:**
- MUST exclude user content (frames, voice, clip metadata beyond opaque IDs).
- Stack traces and source mapping permitted.
- The on-device-only contract supersedes telemetry verbosity (per `OBS-003`).

**Web webhook structured logs [LOCKED]:**
- JSON shape: `{event_id, event_type, processing_time_ms, status: 'success' | 'duplicate' | 'routing_error', error?: string}`.
- NO card primitives or PII in logs — only Stripe IDs (`customer`, `subscription`, `invoice`).

### Process Patterns

#### Error Handling

**Web [LOCKED]:**
- Typed error class `UnauthorizedError` with codes (`NO_SESSION`, `SESSION_EXPIRED`, `SESSION_REVOKED`, `UNAUTHORIZED`).
- `withAuth(handler)` wraps route handlers — catches `UnauthorizedError` and returns the standard 401 envelope.
- Other errors caught at route level, mapped to envelope codes from the API-contracts list.
- Webhook routing-failure response is **200** (per idempotency contract — stops Stripe retries).

**Mobile [LOCKED]:**
- `formatAuthError(firebaseError)` maps Firebase Auth error codes to friendly French messages.
- Network failures in `subscriptionService.checkSubscription` → fall back to MMKV-cached `user.isPaid` (NOT log out the user). Distinct from auth failures, which DO log out.
- Pipeline errors caught at stage boundary in `processingPipeline.ts`; checkpoint stays so user can retry. Session status flips to `error`.
- Codec-unsupported errors at import: clear toast with French message; session NOT created.

**Tooling [LOCKED]:**
- stderr for warnings + clean exit codes (0 = success; nonzero = error).
- TUI launcher saves last-run args ONLY on success (returncode 0).
- `imagehash.hex_to_hash` failures wrapped in try/except with clear "map_config corruption" message.
- BSD/game_detector "0 transitions" → clean exit (no crash); user warned.

#### Loading States

**Mobile [LOCKED]:**
- Short processing → inline progress (e.g., import → import progress bar).
- Long processing → full-screen progress + rotating tips every 5–8 s ("Double tap top left to switch to minimap"; "Drag clip handles to adjust"; etc.).
- Crash recovery: silent auto-save (NO user-visible prompt at save time; resume is implicit on next launch).

**Web [LOCKED]:**
- shadcn `<Skeleton />` inline while data loads.
- No per-route `loading.tsx` files in App Router (Next 16 supports them — team hasn't standardized; future polish item).
- Auth modal pattern: lazy auth — don't ask sign-in until user picks plan; modal overlays on `/pricing`.

#### Authentication Flow

**Web [LOCKED]:**
- Browser signs in via Firebase client SDK.
- Client `POST /api/auth/session` with `{idToken}`.
- Server verifies ID token via `adminAuth.verifyIdToken` → creates session cookie via `adminAuth.createSessionCookie(idToken, {expiresIn: 7*24*60*60*1000})`.
- Cookie attrs: `httpOnly; sameSite=lax; secure (prod); path=/; maxAge=604800`.
- Server-side authed reads/writes use `requireSession()` → `adminAuth.verifySessionCookie(cookie, true)` (the `true` enables revocation check).

**Mobile [LOCKED — post-Decision #5 migration]:**
- `auth().signInWithEmailAndPassword(email, password)` OR `auth().signInWithCredential(googleCredential)` (via `@react-native-google-signin`).
- `auth().onAuthStateChanged(fn)` registered at app boot in `App.tsx`.
- On auth-state-change → user: `mapFirebaseUser` calls `subscriptionService.checkSubscription` → updates `useAuthStore`.
- On auth-state-change → null: clears `useAuthStore`.
- Persistence: automatic via `@react-native-firebase/auth` (Keychain/Keystore-backed).

#### Validation Timing

**Web [LOCKED]:**
- Form input validation: client-side via react-hook-form + Zod schemas at submit time.
- API request validation: server-side Zod parse at handler entry (rejects with `400 INVALID_REQUEST` envelope on failure).
- Webhook validation: server-side Zod parse on the verified Stripe event payload (post-signature-check).
- Cross-language contract validation: build-time codegen (Zod from JSON Schema) + per-call Zod parse in handlers.

**Mobile [LOCKED]:**
- DocumentPicker import: MIME / extension validation at pick time (`videoImportService.validateImport`).
- Detection config: schema validation on every read (cache or remote); invalid payloads silently discarded (`validateDetectionConfig`).
- SQLite inserts: TypeScript type discipline at the call site; runtime validation NOT performed (the domain type IS the persistence shape).

**Tooling [LOCKED]:**
- CLI args validated by argparse at entry.
- YAML config loaded via `utils/config.py:load_config()`; missing keys default via `config.get(...)`.
- Output JSON validated against contracts via `jsonschema` (per Decision #2 / `cross-SCHEMA-001`).

### Cross-Surface Invariants (mandatory for all AI agents)

These rules cross surface boundaries; an agent making the wrong call here breaks integration.

**[INVARIANT 1] Schemas are master at `contracts/`.**
- Edit ONLY `contracts/<schema>.schema.json`. Never edit `packages/contracts/src/generated/*.ts` directly.
- Re-run `pnpm --filter @warden/contracts build` after schema edits.
- Commit schema + regenerated TS together.

**[INVARIANT 2] Web is the sole writer of `users/{uid}`.**
- All `users/{uid}` writes go through `apps/web/src/lib/stripe/webhooks.ts` server-side via firebase-admin.
- Mobile NEVER writes `users/{uid}`. Read-only.
- Client writes denied at the rules layer (Decision #7).

**[INVARIANT 3] On-device-only video processing.**
- No video frames, audio frames, voice annotations, or derived video data in any HTTP request, Firestore write, log line, or telemetry payload.
- Activation telemetry wrapper enforces the allowlist; agents MUST use the wrapper, not call FirebaseAnalytics SDK directly.
- Crash reports MUST NOT include user content.

**[INVARIANT 4] Self-namespace import in `apps/web/src/lib/stripe/webhooks.ts`.**
- Pattern: `import * as self from './webhooks';` then `self.handleX(event)`.
- DO NOT refactor away. `vi.spyOn(webhooksModule, 'handleX')` requires the self-namespace for ESM local-binding interception. Stories 4.2/4.3 rely on this.

**[INVARIANT 5] Stripe metadata required.**
- Every Checkout Session creates BOTH `metadata.firebase_uid` + `metadata.plan_id` AND `subscription_data.metadata.firebase_uid` + `subscription_data.metadata.plan_id`.
- Webhook handler throws on missing metadata — orphan-subscription detection.

**[INVARIANT 6] Stripe dahlia API event nesting.**
- `parent.subscription_details.subscription` (NOT the older top-level `invoice.subscription`).
- Reflected in `apps/web/src/lib/schemas/webhook-events.ts`. Don't regress.

**[INVARIANT 7] Reader-App banned imports / strings (mobile only).**
- See Decision #7 spec. Banned direct imports: `react-native-iap`, `expo-in-app-purchases`, `@stripe/stripe-react-native`, `@stripe/stripe-js`.
- Banned strings: pricing copy + plan-picker component imports.
- CI gate enforces at build-time AND pre-commit hook checks at commit-time.

**[INVARIANT 8] `EXPO_PUBLIC_AUTH_BYPASS` MUST be false / unset in release builds.**
- Dev-mode short-circuit; injects fake `{uid: 'dev-bypass-user', isPaid: true}`.
- Reader-App CI gate scans for this var being `'true'` in release configs and fails the build.

**[INVARIANT 9] `.npmrc` `node-linker=hoisted` is required.**
- Metro `disableHierarchicalLookup` cannot traverse pnpm's nested `.pnpm/` store.
- Agents MUST NOT change this; mobile bundles will silently break.

**[INVARIANT 10] `react-native-mmkv` pinned to v3.**
- v4 needs Nitro Modules (RN 0.83+). v4 on RN 0.81 silently boot-crashes via JSI binding registration failure.
- Pin survives until RN is upgraded; the upgrade is an explicit cross-cutting concern, not an agent decision.

**[INVARIANT 11] Workspace deps via `workspace:*`.**
- `@warden/contracts`, `@warden/tsconfig`, `@warden/eslint-config` referenced as `"workspace:*"` in app `package.json`.
- Don't pin to a version; use `workspace:*`.

**[INVARIANT 12] Conventional Commits.**
- Enforced via husky + commitlint at root.
- Format: `<type>(<scope>): <subject>`.
- Scopes: `mobile`, `web`, `tooling`, `contracts`, `infra`, `auth`, `checkout`, `dashboard`, `webhooks`, `landing`, `legal`.
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.

### Surface-Local Conventions (don't apply across surfaces)

These conventions are **deliberately different** between surfaces because the runtime / framework / language differs. Agents working in one surface use the surface-local convention; cross-surface contracts use the cross-surface invariants above.

| Concern | Mobile | Web | Tooling |
|---------|--------|-----|---------|
| Domain type ↔ persistence | snake_case both layers (no DTO) | Zod `.transform()` at boundary | snake_case both layers |
| Test framework | jest + jest-expo | vitest + jsdom + RTL | pytest |
| Test file location | `__tests__/` directory | co-located `.test.ts(x)` | `tests/` package root |
| Form library | n/a | react-hook-form + Zod | n/a |
| State management | Zustand per feature | React Context auth only | stateless pure functions |
| ESLint | none yet (`echo` placeholder) | flat config | none yet (Phase 7 ruff) |
| Bundler | Metro | Turbopack | n/a (Python) |
| Native module access | `src/shared/services/` only | n/a | n/a |
| Background work | Foreground Service plugin (Decision #6) | n/a | n/a |

### Pattern Examples

**Good — mobile feature slice:**

```
src/features/clip-export/
├── ClipModeScreen.tsx          # screen
├── ExportShareScreen.tsx       # screen
├── exportPipeline.ts           # service
├── exportRecipes.ts            # service
├── useClipExport.ts            # hook
├── types.ts                    # local types
└── __tests__/
    ├── exportPipeline.test.ts
    └── useClipExport.test.ts
```

Imports inside this slice: only `src/shared/*`, other modules within this slice, and external packages. NEVER imports from `src/features/audio-commentary/` or any other feature.

**Good — web webhook handler:**

```ts
// apps/web/src/lib/stripe/webhooks.ts

import * as self from './webhooks'; // [INVARIANT 4]

export async function routeEvent(event: Stripe.Event) {
  switch (event.type) {
    case 'invoice.paid':
      return self.handleInvoicePaid(event);
    case 'customer.subscription.deleted':
      return self.handleSubscriptionDeleted(event);
    case 'customer.subscription.updated':
      return self.handleSubscriptionUpdated(event); // [Decision #9]
    case 'invoice.payment_failed':
      return self.handlePaymentFailed(event);
    default:
      console.log('unhandled event type', event.type);
      return { handled: false };
  }
}
```

**Good — telemetry wrapper:**

```ts
// apps/mobile/src/shared/services/analytics.ts

const ALLOWLIST = ['elapsed_seconds', 't0_at', 't1_at', 't1_path'] as const;

export function logActivationEvent(
  name: 'activation_timer_started' | 'activation_timer_completed',
  payload: Record<string, unknown>
) {
  for (const key of Object.keys(payload)) {
    if (!ALLOWLIST.includes(key as typeof ALLOWLIST[number])) {
      if (__DEV__) console.warn(`Banned analytics field: ${key}`);
      else throw new Error(`Banned analytics field: ${key}`);
    }
  }
  firebaseAnalytics.logEvent(name, payload);
}
```

**Anti-pattern — features importing features:**

```ts
// apps/mobile/src/features/clip-export/ClipModeScreen.tsx

// WRONG
import { useAudioRecording } from '../audio-commentary/useAudioRecording';
```

The right path: cross-feature comm via Zustand store or `src/shared/services/`. If `clip-export` needs audio data, the audio data lives in a shared store (e.g., `useSessionStore.audioComments`) populated by `audio-commentary`, and `clip-export` reads from the store.

**Anti-pattern — direct Firestore writes from web client:**

```ts
// apps/web/src/components/dashboard/SubscriptionCard.tsx

// WRONG
await firestoreClient.collection('users').doc(uid).update({ status: 'canceled' });
```

The right path: client never writes `users/{uid}` ([INVARIANT 2]). Cancel goes through `POST /api/subscription/portal` → Stripe Customer Portal → `customer.subscription.deleted` webhook → server-side write.

**Anti-pattern — analytics with frame data:**

```ts
// apps/mobile/src/features/video-processing/processingPipeline.ts

// WRONG
firebaseAnalytics.logEvent('detection_failed', { frame_url: 'file:///...' });
```

The right path: telemetry wrapper rejects `frame_url` ([INVARIANT 3]). If telemetry about detection failure is needed, log only timestamps and event names.

### Enforcement Guidelines

**All AI agents MUST:**

- Read `docs/architecture-{mobile,web,tooling,shared}.md` for surface-local conventions before writing code on that surface.
- Read this section's [INVARIANT 1–12] before making any cross-surface change.
- Run `pnpm typecheck && pnpm test` locally before pushing (no CI yet — Phase 7).
- Run the Reader-App pre-commit gate before committing mobile changes (`apps/mobile/scripts/reader-app-gate.sh`).
- Re-run `pnpm --filter @warden/contracts build` after editing `contracts/*.schema.json`.

**Pattern enforcement mechanisms (current + Phase-7):**

- **Today (V0):** Conventional Commits via husky + commitlint; Prettier on staged files; Reader-App pre-commit hook.
- **Phase 7 (V1.1):** GitHub Actions `ci.yml` runs typecheck + tests + Reader-App gate + shared-Firebase-project assertion + contracts-codegen-check.

**Process for updating patterns:**

- Cross-surface invariant changes: PR amends this architecture doc + bumps relevant docs + touches relevant docs/architecture-*.md.
- Surface-local convention changes: PR amends `docs/architecture-<surface>.md` only.
- New cross-surface patterns surface in this section as new [INVARIANT N] entries; agents discover them by re-reading.

## Project Structure & Boundaries

### Complete Project Directory Structure

The as-built monorepo tree, annotated with files introduced by the decisions in step 4. **`[NEW]`** marks files this architecture introduces; everything else is already in the working tree per `docs/source-tree-analysis.md`.

```
Warden_monorepo/
├── apps/
│   ├── mobile/                                              Part: mobile (Expo / React Native, package "mobile")
│   │   ├── App.tsx                                          Entry — fonts, AuthBypass branch, listeners
│   │   ├── index.ts                                         Expo registration
│   │   ├── app.json                                         Expo config (Android pkg team.warden.mobile, newArchEnabled)
│   │   ├── metro.config.js                                  Monorepo Metro: watchFolders=root, disableHierarchicalLookup
│   │   ├── babel.config.js                                  Babel preset
│   │   ├── global.css                                       NativeWind global stylesheet
│   │   ├── tailwind.config.ts                               NativeWind / Tailwind config
│   │   ├── tsconfig.json                                    Extends @warden/tsconfig/react-native.json
│   │   ├── package.json                                     "mobile" — Expo SDK 54, RN 0.81, Firebase 12, NativeWind 4
│   │   ├── RELEASE.md                                       [NEW] Reader-App release-readiness checklist (Decision #7)
│   │   ├── scripts/
│   │   │   └── reader-app-gate.sh                           [NEW] Reader-App pre-commit + CI gate (Decision #7 spec)
│   │   ├── plugins/
│   │   │   ├── with-ffmpeg.js                               FFmpeg-kit Expo config plugin (legacy, retained)
│   │   │   └── with-foreground-service.js                   [NEW] Foreground Service Android plugin (Decision: Brownfield Item 6)
│   │   ├── assets/                                          App icons, splashes, fonts
│   │   │   └── map_config.json                              [NEW] Bundled-as-Metro-asset baseline (Decision #2 hybrid)
│   │   └── src/
│   │       ├── app/                                         App shell — minimal navigation + screen composition
│   │       │   ├── RootNavigator.tsx                        Auth-gated stack: Login | (Home + Processing)
│   │       │   └── screens/HomeScreen.tsx
│   │       ├── features/                                    Vertical slices — one folder per epic-level concern
│   │       │   ├── auth/                                    Firebase Auth + entitlement gate (Zustand+MMKV)
│   │       │   │   ├── LoginScreen.tsx
│   │       │   │   ├── firebaseConfig.ts                    Migrated to @react-native-firebase/* per Brownfield Item 5
│   │       │   │   ├── authService.ts                       login/logout/listenToAuthChanges + emit T0 telemetry
│   │       │   │   ├── googleSignInService.ts
│   │       │   │   ├── subscriptionService.ts               isSubscriptionPaid + deriveEntitlementState [NEW]
│   │       │   │   ├── useAuthStore.ts                      Zustand+MMKV partialized {user,isAuthenticated,cachedAt}
│   │       │   │   ├── EntitlementBanner.tsx                [NEW per UX-DR1] payment-failed banner + Customer Portal deep-link (Story 3.2; mobile-AUTH-006)
│   │       │   │   ├── SubscriptionRequiredScreen.tsx       [NEW per UX-DR2] full-screen lapsed-state with Customer Portal deep-link (Story 3.3; mobile-AUTH-003)
│   │       │   │   ├── OfflineIndicator.tsx                 [NEW per UX-DR3] offline-grace ≤30d visual chip (Story 3.4; mobile-AUTH-004 visual)
│   │       │   │   └── __tests__/
│   │       │   │       ├── deriveEntitlementState.test.ts   [NEW] One test per state (paid/lapsed/offline-grace/payment-failed/multi-device/signed-out)
│   │       │   │       ├── EntitlementBanner.test.tsx      [NEW per UX-DR1] Banner render + CTA + state-clear assertions
│   │       │   │       ├── SubscriptionRequiredScreen.test.tsx [NEW per UX-DR2] Lapsed screen render + data-preservation contract
│   │       │   │       ├── OfflineIndicator.test.tsx       [NEW per UX-DR3] Offline-grace visual + day-29 escalation
│   │       │   │       └── subscriptionService.test.ts
│   │       │   ├── audio-commentary/                        Voice annotation (Story 6 — Sprint 3)
│   │       │   │   ├── AudioRecorder.tsx
│   │       │   │   ├── CommentaryTimeline.tsx
│   │       │   │   ├── useAudioRecording.ts
│   │       │   │   ├── audioCommentService.ts
│   │       │   │   └── types.ts
│   │       │   ├── clip-export/                             Clip mode + export pipeline + share sheet
│   │       │   │   ├── ClipModeScreen.tsx
│   │       │   │   ├── ExportShareScreen.tsx
│   │       │   │   ├── exportPipeline.ts                    Emits T1-coach telemetry on share-confirmed
│   │       │   │   ├── exportRecipes.ts                     Per view-mode FFmpeg recipe (Full / Minimap / Minimap+HUD)
│   │       │   │   ├── useClipExport.ts                     Adds autoSaveClipState (Story 7.1; mobile-AUTOSAVE-001)
│   │       │   │   ├── clipDeletion.ts                      [NEW per AR-12] Cascade delete: MP4 + .m4a + MMKV processing.* + SQLite via CASCADE (Story 6.9; PRIV-003)
│   │       │   │   └── types.ts
│   │       │   ├── session/                                 Session list + repository + Card View
│   │       │   │   ├── SessionList.tsx
│   │       │   │   ├── CardViewScreen.tsx
│   │       │   │   ├── sessionRepository.ts                 SQLite CRUD over `sessions`
│   │       │   │   └── useSessionStore.ts                   Zustand+MMKV
│   │       │   ├── video-import/                            DocumentPicker → MP4 validation → SQLite session
│   │       │   │   ├── VideoImportScreen.tsx
│   │       │   │   ├── videoImportService.ts
│   │       │   │   ├── useVideoImport.ts
│   │       │   │   └── types.ts
│   │       │   ├── video-playback/                          Cinema mode
│   │       │   │   ├── CinemaModeScreen.tsx                 Emits T1-active-player telemetry on first view-mode toggle
│   │       │   │   ├── PlayerControls.tsx
│   │       │   │   ├── MinimapView.tsx                      ROI crop on same expo-av source (PERF-003 ≤100ms)
│   │       │   │   ├── EpisodeNavigator.tsx
│   │       │   │   ├── ViewModeToggle.tsx
│   │       │   │   ├── HudToggle.tsx
│   │       │   │   └── usePlayback.ts
│   │       │   └── video-processing/                        Detection pipeline (FFmpeg → game/black-screen → maps)
│   │       │       ├── ProcessingScreen.tsx
│   │       │       ├── processingPipeline.ts                4-stage MMKV checkpointing orchestrator
│   │       │       ├── detectionConfig.ts                   Zod schema + validateDetectionConfig
│   │       │       ├── detectionConfigService.ts            Stale-while-revalidate (bundled fallback per Decision #2)
│   │       │       ├── detectionConfigBootstrap.ts          Reads bundled asset on first launch (Decision #2)
│   │       │       ├── blackScreenDetector.ts               Long-GOP fallback (2-pass team-bar saturation)
│   │       │       ├── gameDetector.ts                      Short-GOP KDA/HSV detector
│   │       │       ├── mapIdentifier.ts                     pHash matcher against map_config
│   │       │       ├── segmentation.ts                      START/END pair → MapSegment timeline
│   │       │       ├── segmentRepository.ts                 SQLite map_segments writer
│   │       │       └── useVideoProcessing.ts
│   │       ├── shared/                                      Cross-feature primitives
│   │       │   ├── components/
│   │       │   │   ├── Button.tsx, Card.tsx, LoadingSpinner.tsx, Toast.tsx
│   │       │   │   └── hud/                                 Custom HUD design system (~12 atoms; matches warden-mocks)
│   │       │   │       ├── Screen.tsx, HudBracket.tsx, CornerTick.tsx, Stamp.tsx, Marks.tsx
│   │       │   │       ├── Field.tsx, CircleBtn.tsx, EngageButton.tsx, Icon.tsx, MapArt.tsx, Timeline.tsx
│   │       │   │       └── tokens.ts
│   │       │   ├── hooks/
│   │       │   ├── services/                                Native bridges (sole entry points to native libs)
│   │       │   │   ├── analytics.ts                         [NEW] Telemetry wrapper with payload allowlist (Decision #9 / Invariant 3)
│   │       │   │   ├── errorReporting.ts                    [NEW per UX-DR5] mailto formatter → support@warden.team; manual fallback for OBS-003 (Story 8.2; FU-1)
│   │       │   │   ├── database.ts                          expo-sqlite singleton
│   │       │   │   ├── ffmpeg.ts                            FFmpeg-kit wrapper + assertSafeSessionId
│   │       │   │   ├── opencv.ts                            JSI binding (post-spike: real binding; pre-spike: stub throws)
│   │       │   │   └── storage.ts                           react-native-mmkv typed wrapper + Zustand StateStorage adapter
│   │       │   ├── types/index.ts                           Domain types: Session, MapSegment, ClipExport, AudioComment
│   │       │   └── utils/
│   │       └── __tests__/                                   App-level tests
│   │
│   ├── web/                                                 Part: web (Next.js, package "web")
│   │   ├── next.config.ts                                   Empty defaults
│   │   ├── firebase.json                                    Firestore rules deploy config
│   │   ├── firestore.rules                                  Updated per Decision #7 (extended coverage)
│   │   ├── eslint.config.mjs                                Web ESLint flat config
│   │   ├── postcss.config.mjs
│   │   ├── components.json                                  shadcn/ui registry config
│   │   ├── vitest.config.ts
│   │   ├── vitest.setup.ts
│   │   ├── tsconfig.json                                    Extends @warden/tsconfig/next.json
│   │   ├── package.json                                     "web" — Next.js 16.2.2, Stripe 22 (pin → 2026-04-22.dahlia per Item 1), Firebase admin 13
│   │   ├── AGENTS.md                                        ⚠ "This is NOT the Next.js you know"
│   │   ├── public/
│   │   └── src/
│   │       ├── app/                                         App Router
│   │       │   ├── layout.tsx                               Root — fonts, AuthProvider, body wrapper
│   │       │   ├── page.tsx                                 Marketing landing
│   │       │   ├── auth/sign-in/page.tsx
│   │       │   ├── pricing/page.tsx
│   │       │   ├── dashboard/
│   │       │   │   ├── layout.tsx                           Auth gate via requireSession
│   │       │   │   └── page.tsx
│   │       │   └── api/
│   │       │       ├── auth/session/route.ts                POST/DELETE — session cookie lifecycle
│   │       │       ├── checkout/coupon/route.ts             POST — preview coupon
│   │       │       ├── checkout/session/route.ts            POST — create Stripe Checkout
│   │       │       ├── subscription/route.ts                GET — read users/{uid}
│   │       │       ├── subscription/portal/route.ts         POST — Stripe billing portal
│   │       │       └── webhooks/stripe/route.ts             POST — Stripe webhook ingress (incl. customer.subscription.updated per Decision #9)
│   │       ├── components/
│   │       │   ├── auth/                                    SignInForm, GoogleSignInButton, SignOutButton, RegistrationForm
│   │       │   │   └── PasswordResetForm.tsx                [NEW per UX-DR11] Firebase sendPasswordResetEmail inline form (Story 4.4; FU-5; web-AUTH-001)
│   │       │   ├── checkout/                                PlanCard, PlanCta, CouponInput, CheckoutContext
│   │       │   ├── dashboard/                               SubscriptionCard
│   │       │   │   ├── PaymentWarning.tsx                   [NEW per UX-DR8] past_due banner composition from Alert+Button (Story 3.5; web-DASHBOARD-002)
│   │       │   │   ├── CancelDialog.tsx                     [NEW per UX-DR9] anti-dark-pattern cancellation dialog from Dialog+Button (Story 4.5; web-DASHBOARD-004)
│   │       │   │   └── EmptySubscription.tsx                [NEW per UX-DR10] "No active subscription" empty state with /pricing link (Story 4.6; web-DASHBOARD-005)
│   │       │   ├── layout/                                  Header, HeaderAuthActions, Footer (with mailto:support@warden.team per UX-DR15), CookieBanner
│   │       │   └── ui/                                      shadcn/ui primitives (button, card, input, alert, dialog, badge, skeleton, cta-class)
│   │       ├── contexts/AuthContext.tsx                     Firebase onAuthStateChanged → React context
│   │       ├── hooks/{useAuth.ts, useSubscription.ts}
│   │       ├── lib/
│   │       │   ├── env.ts
│   │       │   ├── utils.ts                                 cn() = clsx + tailwind-merge
│   │       │   ├── firebase/{admin,client,auth,session,analytics,errors}.ts
│   │       │   ├── stripe/
│   │       │   │   ├── server.ts                            API pin → 2026-04-22.dahlia per Brownfield Item 1
│   │       │   │   ├── webhooks.ts                          Self-namespace pattern [INVARIANT 4]; handleSubscriptionUpdated [NEW per Decision #9]
│   │       │   │   └── coupons.ts
│   │       │   ├── pricing/{plans,discount}.ts
│   │       │   └── schemas/
│   │       │       ├── auth.ts
│   │       │       ├── subscription.ts                      Re-exports @warden/contracts/user-doc per Decision #6
│   │       │       └── webhook-events.ts                    Adds subscriptionUpdatedSchema [NEW per Decision #9]
│   │       └── fonts/
│   │
│   └── tooling/                                             Part: tooling (Python CLI, package "tooling")
│       ├── wardentooling.py                                 TUI launcher (questionary)
│       ├── pyproject.toml                                   warden-tooling — opencv, numpy, imagehash, pyyaml, questionary, jsonschema
│       ├── package.json                                     Thin Turborepo wrapper
│       ├── requirements.txt                                 Pinned deps (pip parallel to uv)
│       ├── README.md
│       ├── description.md
│       ├── config/config.yaml                               All tunables — ROI zones, thresholds, HSV bands, 14 map fingerprints
│       ├── tools/
│       │   ├── black_screen_detector.py                     Tool 1 reference impl
│       │   ├── frame_labeler.py                             Tool 2 — manual labeling helper (MAP_LABELS source of truth)
│       │   ├── map_config_generator.py                      Tool 3 — emits map_config.json (writes schema_version: 1 per Item 7)
│       │   ├── hash_validator.py                            Tool 4 — accuracy reporter (REL-006 regression suite)
│       │   ├── warden_analyzer.py                           Tool 5 — full-pipeline analyzer
│       │   ├── game_detector.py
│       │   ├── points_state_detector.py                     Dev tool
│       │   ├── bsd_roi_debugger.py                          Dev tool
│       │   ├── hash_comparator.py                           Hamming-distance helpers (writes schema_version: 1)
│       │   ├── common/video_player.py
│       │   ├── image_inspector/                             Dev GUI module
│       │   └── minimap_zone_selector/                       Dev GUI for HSV zone calibration
│       ├── utils/{config.py, format.py, image.py, video.py}
│       ├── tests/
│       │   └── fixtures/
│       └── docs/                                            Pre-existing per-app docs (legacy reference)
│
├── packages/
│   ├── contracts/                                           @warden/contracts — TS Zod surface
│   │   ├── package.json                                     ESM, exports ./, ./map-config, ./user-doc
│   │   ├── tsconfig.json
│   │   ├── scripts/generate-zod.mjs                         JSON Schema → Zod codegen
│   │   └── src/
│   │       ├── index.ts                                     Re-exports (NO .js extensions per Metro constraint)
│   │       └── generated/
│   │           ├── map-config.ts                            AUTO-GENERATED (banner: "Do not edit by hand")
│   │           └── user-doc.ts                              AUTO-GENERATED — strict per Decision #1 post-tighten
│   ├── tsconfig/                                            @warden/tsconfig
│   │   ├── package.json
│   │   ├── base.json                                        strict + noUncheckedIndexedAccess + Bundler resolution
│   │   ├── next.json                                        Web (extends base)
│   │   └── react-native.json                                Mobile + contracts (extends base)
│   └── eslint-config/                                       @warden/eslint-config
│       ├── package.json
│       └── index.js                                         Flat config baseline
│
├── contracts/                                               Language-agnostic JSON Schema (cross-language source of truth)
│   ├── map-config.schema.json                               Strict; adds schema_version per Item 7
│   └── user-doc.schema.json                                 Strict per Decision #1 (additionalProperties: false post-tighten)
│
├── _bmad/                                                   BMad install (v6.6.0)
├── _bmad-output/                                            Planning surface
│   ├── product-brief.md                                     Phase 6 step 1
│   ├── product-brief-distillate.md                          Phase 6 step 1 detail
│   ├── prd.md                                               Phase 6 step 2
│   ├── architecture.md                                      Phase 6 step 3 — THIS DOCUMENT
│   ├── architecture-spike-perf-floor.md                     [NEW] Pre-PRD performance spike report (Decision: load-bearing first task)
│   └── legacy/                                              Pre-merge planning preserved per app
│
├── docs/                                                    Phase 5b output (as-built code docs) — kept current
│   ├── architecture-{mobile,web,tooling,shared}.md
│   ├── integration-architecture.md
│   ├── data-models-{mobile,web,shared}.md
│   ├── api-contracts-web.md
│   ├── source-tree-analysis.md
│   ├── component-inventory-{mobile,web}.md
│   ├── deployment-guide.md
│   ├── development-guide.md
│   ├── project-overview.md
│   └── index.md
│
├── .github/                                                 [NEW — Phase 7 backlog]
│   └── workflows/
│       ├── ci.yml                                           [NEW] typecheck + test + Reader-App gate + shared-Firebase-project assertion
│       ├── deploy-firestore-rules.yml                       [NEW] Auto-deploy on push to main affecting apps/web/firestore.rules
│       └── contracts-codegen-check.yml                      [NEW] Fail PRs where pnpm contracts:build produces dirty diffs
│
├── .husky/                                                  Pre-commit + commit-msg hooks (commitlint)
├── commitlint.config.ts                                     Conventional commits enforcement
├── .prettierrc                                              endOfLine: auto (Windows-friendly)
├── .prettierignore                                          Excludes apps/mobile/** + apps/tooling/**
├── .npmrc                                                   node-linker=hoisted (REQUIRED for Expo/Metro [INVARIANT 9])
├── pnpm-workspace.yaml                                      apps/* + packages/*
├── pyproject.toml                                           Root Python — [tool.uv.workspace] members=apps/tooling
├── turbo.json                                               Task graph: build/typecheck/test/lint/dev
├── package.json                                             Root TS — turbo, prettier, husky, commitlint
└── README.md                                                Surfaces overview + get-started
```

### FR-to-Structure Mapping

Every FR in the PRD has a binding implementation location. Where multiple files share an FR, the **primary owner** is listed first.

#### Mobile FRs (33)

**Authentication & Entitlement (`mobile-AUTH-001..006`):**
- `apps/mobile/src/features/auth/LoginScreen.tsx` — `mobile-AUTH-001` (sign-in UI).
- `apps/mobile/src/features/auth/authService.ts` — `mobile-AUTH-001/002` (login orchestration; emits T0 telemetry on transition to `paid`).
- `apps/mobile/src/features/auth/subscriptionService.ts` — `mobile-AUTH-002/003/004/005/006` (entitlement validation, `deriveEntitlementState`, periodic re-validation, foreground re-fetch).
- `apps/mobile/src/features/auth/useAuthStore.ts` — `mobile-AUTH-004` (30-day MMKV cache; partialized persist).
- `apps/mobile/src/app/RootNavigator.tsx` — `mobile-AUTH-003` (renders `Login` vs `Home + Processing` per `isAuthenticated`).
- Lapsed/payment-failed UI banners — `apps/mobile/src/features/auth/EntitlementBanner.tsx` (NEW, Sprint 3).

**Session Import & Auto-Slicing (`mobile-IMPORT-001/002`, `mobile-AUTO-SLICE-001..004`):**
- `apps/mobile/src/features/video-import/videoImportService.ts` — `mobile-IMPORT-001/002` (DocumentPicker + MP4 validation + session insert).
- `apps/mobile/src/features/video-processing/processingPipeline.ts` — orchestrator (4-stage MMKV checkpointing).
- `apps/mobile/src/features/video-processing/gameDetector.ts` — `mobile-AUTO-SLICE-001` (round-boundary KDA/HSV detector; short-GOP path).
- `apps/mobile/src/features/video-processing/blackScreenDetector.ts` — `mobile-AUTO-SLICE-001` (long-GOP fallback; 2-pass team-bar saturation).
- `apps/mobile/src/features/video-processing/mapIdentifier.ts` — `mobile-AUTO-SLICE-002/003` (pHash matching; `unknown` fallback).
- `apps/mobile/src/features/video-processing/segmentation.ts` — pair events into segments; lobby exclusion `mobile-AUTO-SLICE-004`.
- `apps/mobile/plugins/with-foreground-service.js` — keeps pipeline alive in background (Decision: Brownfield Item 6).

**Card View & Triage (`mobile-CARD-001..005`):**
- `apps/mobile/src/features/session/CardViewScreen.tsx` — `mobile-CARD-001/003/004` (grid layout, tap → Cinema, cold-start state).
- `apps/mobile/src/features/session/useSessionStore.ts` — `mobile-CARD-002` (sort persistence via `prefs.sortOrder`).
- `mobile-CARD-005` (auto-slice-missed rounds via timeline) — handled in `apps/mobile/src/features/video-playback/CinemaModeScreen.tsx` (timeline-only manual-clip flow).

**Cinema Mode (`mobile-CINEMA-001..005`):**
- `apps/mobile/src/features/video-playback/CinemaModeScreen.tsx` — `mobile-CINEMA-001/003/005` (immersive review, view-mode default to `Full` for unknown maps, Next/Prev buttons).
- `apps/mobile/src/features/video-playback/ViewModeToggle.tsx` + `MinimapView.tsx` — `mobile-CINEMA-002` (segmented control + double-tap gesture; PERF-003 ≤100 ms).
- `apps/mobile/src/features/session/useSessionStore.ts` — `mobile-CINEMA-004` (view-mode persistence via `prefs.viewMode` + `prefs.minimapHud`).
- T1-active-player telemetry emit on first view-mode toggle: `apps/mobile/src/features/video-playback/CinemaModeScreen.tsx` (Decision #9 / `cross-ACTIVATION-001`).

**Clip Creation & Voice Annotation (`mobile-CLIP-001..005`):**
- `apps/mobile/src/features/clip-export/ClipModeScreen.tsx` — `mobile-CLIP-001/002` (30-second region + bracket handles + manual clip from any timeline point).
- `apps/mobile/src/features/audio-commentary/AudioRecorder.tsx` + `useAudioRecording.ts` — `mobile-CLIP-003/004` (3-slot voice + re-record).
- `apps/mobile/src/features/clip-export/ExportShareScreen.tsx` — `mobile-CLIP-005` (preview before export).

**Export & Share (`mobile-EXPORT-001..004`):**
- `apps/mobile/src/features/clip-export/exportPipeline.ts` — `mobile-EXPORT-001/002` (FFmpeg encode; tier selection).
- `apps/mobile/src/features/clip-export/exportRecipes.ts` — per view-mode FFmpeg recipe.
- `apps/mobile/src/shared/services/ffmpeg.ts` — FFmpeg-kit wrapper + `assertSafeSessionId`.
- OS share dispatch: `apps/mobile/src/features/clip-export/ExportShareScreen.tsx` via `expo-sharing` — `mobile-EXPORT-003/004`.
- T1-coach telemetry emit on confirmed-dispatch: `exportPipeline.ts` post-share callback (`cross-ACTIVATION-001`).

**Auto-save & Crash Recovery (`mobile-AUTOSAVE-001/002`):**
- `apps/mobile/src/features/video-processing/processingPipeline.ts` — MMKV checkpoints `processing.<sid>.<field>`.
- Clip-creation auto-save: `apps/mobile/src/features/clip-export/useClipExport.ts` (NEW, Sprint 3 — silent persistence per `mobile-AUTOSAVE-001`).
- Resume on launch: `App.tsx` reads `useSessionStore.currentSessionId` + restores Cinema Mode position via `useSessionStore.playbackPositionMs`.

#### Web FRs (13)

**Landing & Pricing (`web-LANDING-001/002`, `web-PRICING-001/002`):**
- `apps/web/src/app/page.tsx` — `web-LANDING-001/002` (FR-locked hero; SSR HTML for crawlers + Discord card preview).
- `apps/web/src/app/pricing/page.tsx` + `apps/web/src/components/checkout/PlanCard.tsx` + `PlanCta.tsx` + `CouponInput.tsx` — `web-PRICING-001`.
- Auth modal pattern: `apps/web/src/components/auth/EmailSignInForm.tsx` + `GoogleSignInButton.tsx` overlaid on `/pricing` — `web-PRICING-002`.

**Authentication & Checkout (`web-AUTH-001`, `web-CHECKOUT-001/002`):**
- `apps/web/src/app/auth/sign-in/page.tsx` + `apps/web/src/components/auth/*` — `web-AUTH-001`.
- `apps/web/src/lib/firebase/client.ts` + `apps/web/src/contexts/AuthContext.tsx` — Firebase Auth client integration.
- `apps/web/src/app/api/auth/session/route.ts` — session cookie creation/destruction.
- `apps/web/src/app/api/checkout/session/route.ts` — `web-CHECKOUT-001` (Stripe Checkout creation + deferred-billing copy + metadata).
- Success redirect handled by Stripe Checkout `success_url`; landing handler in `apps/web/src/app/dashboard/page.tsx` reads `?checkout=success` query param — `web-CHECKOUT-002`.

**Dashboard (`web-DASHBOARD-001..005`):**
- `apps/web/src/app/dashboard/page.tsx` + `layout.tsx` — `web-DASHBOARD-001` (protected route; `requireSession`).
- `apps/web/src/components/dashboard/SubscriptionCard.tsx` — status badge + plan + next-payment-date + Manage Subscription deep-link.
- `apps/web/src/hooks/useSubscription.ts` — fetches `/api/subscription`; parses with Zod from `@warden/contracts/user-doc` (Decision #6).
- Payment-failure warning: `apps/web/src/components/dashboard/SubscriptionCard.tsx` reads `subscription.status === 'past_due'` — `web-DASHBOARD-002`.
- Cancel-at-period-end UI + Resubscribe CTA: `SubscriptionCard.tsx` reads cancellation flag — `web-DASHBOARD-003`.
- Cancellation confirmation dialog (no exit survey): `apps/web/src/components/dashboard/CancelDialog.tsx` (NEW, Sprint 3) — `web-DASHBOARD-004`.
- "No active subscription" empty state: `SubscriptionCard.tsx` when `data === null` — `web-DASHBOARD-005`.

**Webhook Processing (`web-WEBHOOK-001..003`):**
- `apps/web/src/app/api/webhooks/stripe/route.ts` — `web-WEBHOOK-001` (signature verification; routing).
- `apps/web/src/lib/stripe/webhooks.ts` — `web-WEBHOOK-002` (dual-strategy idempotency; self-namespace pattern; handleSubscriptionUpdated per Decision #9).
- `apps/web/firestore.rules` — `web-WEBHOOK-003` (deny client writes to `users/{uid}`; Decision #7 extends coverage).

**Analytics (`web-ANALYTICS-001`):**
- `apps/web/src/lib/firebase/analytics.ts` — Firebase Analytics conditional load (post cookie-consent).
- Funnel events (Visit, CheckoutStart, CheckoutComplete, Coupon-applied, Coupon-Retained-past-deferred-billing) — emitted from `apps/web/src/components/checkout/PlanCta.tsx` + `apps/web/src/app/dashboard/page.tsx`.

#### Tooling FRs (13)

**Round Detection & Frame Extraction (`tooling-ROUND-DETECT-001/002`):**
- `apps/tooling/tools/black_screen_detector.py` — `tooling-ROUND-DETECT-001/002` (BSD with miss-report).
- `apps/tooling/tools/game_detector.py` — KDA/HSV alternative.

**Frame Labeling (`tooling-LABEL-001/002`):**
- `apps/tooling/tools/frame_labeler.py` — `tooling-LABEL-001/002` (per-map labeling; MAP_LABELS source of truth at `frame_labeler.py:19-34`).

**Hash Generation & Map Config (`tooling-HASH-001/002`):**
- `apps/tooling/tools/map_config_generator.py` — `tooling-HASH-001` (map_config.json emit; writes `schema_version: 1` per Brownfield Item 7).
- `apps/tooling/tools/hash_comparator.py` — `tooling-HASH-002` (consensus hash; pipeline params persisted).

**Hash Validation (`tooling-VALIDATE-001/002`):**
- `apps/tooling/tools/hash_validator.py` — `tooling-VALIDATE-001/002` (accuracy report; pipeline-param parity from `map_config.json`).

**End-to-End Pipeline (`tooling-WARDEN-001`):**
- `apps/tooling/tools/warden_analyzer.py` — `tooling-WARDEN-001` (full pipeline; rounds.json emit).

**TUI Launcher (`tooling-TUI-001/002`):**
- `apps/tooling/wardentooling.py` — `tooling-TUI-001/002` (TUI launcher; `.warden_last_run.json` re-run support).

**Schema Validation (`tooling-SCHEMA-001`):**
- `apps/tooling/tools/map_config_generator.py` calls `jsonschema` against `contracts/map-config.schema.json` — `tooling-SCHEMA-001`.

#### Cross-Surface FRs (6)

**Entitlement State Machine (`cross-ENTITLEMENT-001/002`):**
- `apps/mobile/src/features/auth/subscriptionService.ts:deriveEntitlementState` — `cross-ENTITLEMENT-001` (six-state derivation; per Frontend Architecture step 4).
- `apps/web/src/lib/stripe/webhooks.ts` + `apps/web/firestore.rules` — `cross-ENTITLEMENT-002` (web sole writer; client writes denied).

**Activation Telemetry (`cross-ACTIVATION-001/002`):**
- `apps/mobile/src/shared/services/analytics.ts` — wrapper enforcing payload allowlist (per Decision #9 / step 5 patterns).
- T0 emit: `apps/mobile/src/features/auth/authService.ts`.
- T1-coach emit: `apps/mobile/src/features/clip-export/exportPipeline.ts`.
- T1-active-player emit: `apps/mobile/src/features/video-playback/CinemaModeScreen.tsx`.

**Schema Contract Conformance (`cross-SCHEMA-001/002`):**
- `contracts/map-config.schema.json` + `contracts/user-doc.schema.json` — masters.
- `packages/contracts/scripts/generate-zod.mjs` — TS codegen.
- `packages/contracts/src/generated/{map-config,user-doc}.ts` — auto-generated.
- Tooling validation: `apps/tooling/tools/map_config_generator.py` (`jsonschema`).
- Web validation: `apps/web/src/lib/schemas/subscription.ts` (re-exports `@warden/contracts/user-doc` per Decision #6) + `webhook-events.ts`.
- Mobile validation: `apps/mobile/src/features/video-processing/detectionConfig.ts` (`validateDetectionConfig`).

**Reader-App Build Gate (`cross-READER-APP-001`):**
- `apps/mobile/scripts/reader-app-gate.sh` — pre-commit + CI gate (Decision #7 spec).
- `.github/workflows/ci.yml` — CI invocation (Phase 7 backlog).
- `apps/mobile/RELEASE.md` — release-readiness checklist.

**`map_config.json` Runtime Delivery (`cross-MAP-CONFIG-DELIVERY-001`):**
- `apps/mobile/assets/map_config.json` — bundled baseline (Decision #2).
- `apps/mobile/src/features/video-processing/detectionConfigBootstrap.ts` — reads bundled on first launch.
- `apps/mobile/src/features/video-processing/detectionConfigService.ts` — Firestore overlay via stale-while-revalidate.

### Architectural Boundaries

#### Surface Boundaries

The three surfaces (`apps/mobile`, `apps/web`, `apps/tooling`) are **independent deploy units**. Boundaries:

```
                  packages/contracts (cross-language schemas — both directions)
                            ▲                ▲                ▲
                            │                │                │
         ┌──────────────────┘                │                └──────────────────┐
         │                                   │                                   │
         ▼                                   ▼                                   ▼
+------------------+                +------------------+                +------------------+
│   apps/mobile    │                │    apps/web      │                │   apps/tooling   │
│  (Android V1)    │◄──────────────►│   (Next.js 16)   │                │  (Python CLI)    │
│                  │  Firestore     │                  │                │                  │
│   reads only     │  (users/{uid}, │  writes only     │  emits         │   emits          │
│                  │  detection_    │  via firebase-   │  contracts     │   map_config.json│
│                  │  config/latest)│  admin           │  (read-only)   │                  │
+------------------+                +------------------+                +------------------+
       │                                    │                                    │
       │ shares Firebase project            │ Stripe Checkout + Customer Portal  │
       │ (Decision #3)                      │ + webhooks                         │
       ▼                                    ▼                                    │
+------------------+                +------------------+                         │
│   Firebase       │                │    Stripe        │                         │
│   (auth +        │                │   (payment +     │                         │
│   Firestore EU)  │                │   subscription)  │                         │
+------------------+                +------------------+                         │
                                                                                 ▼
                                                             [no production runtime —
                                                              tooling lives on operator workstation]
```

**Cross-surface invariants** govern these boundaries (steps 4 + 5 enumerate):

- Web is the **sole writer** of `users/{uid}` (Invariant 2).
- Mobile is **read-only** to Firestore.
- Tooling has **no production runtime path** — it emits files (cross-language contracts) that are consumed by humans (commit to repo / upload to Firestore).
- The **schema** in `packages/contracts/` is the binding mechanism — drift is a CI failure (per Phase-7 `contracts-codegen-check.yml`).

#### Component Boundaries (within `apps/mobile`)

```
src/app/                  (only navigation + screen composition; no domain logic)
   │
   ▼
src/features/<slice>/     (vertical slices; never import other features)
   │
   ├── components (.tsx)            ← can import from src/shared/
   ├── services / repositories (.ts) ← can import from src/shared/services/
   ├── stores (Zustand)              ← can import from src/shared/services/storage.ts
   ├── hooks (use*.ts)               ← orchestrate components, services, stores
   └── __tests__/                    ← co-located
   │
   ▼
src/shared/               (cross-feature primitives; no feature imports)
   ├── components/        (presentational; no Firestore/SQLite/MMKV imports)
   ├── services/          (sole entry to native modules — opencv, ffmpeg, database, storage)
   └── types/             (domain types matching SQL columns)
```

**Rules:**

- `src/features/<a>` MUST NOT import from `src/features/<b>`. Cross-feature data flows through Zustand stores or `src/shared/services/`.
- `src/shared/components/` MUST NOT import any Firestore/SQLite/MMKV symbols. Presentational only.
- Native module access is restricted to `src/shared/services/{ffmpeg,opencv,database,storage}.ts`. NO feature directly imports `react-native-mmkv` or `expo-sqlite` — they go through the wrapper.

#### Component Boundaries (within `apps/web`)

```
src/app/                          (Next.js App Router)
   │
   ├── pages (.tsx)               ← can import from src/components/, src/lib/, src/hooks/
   └── api/.../route.ts           ← server-only; can import from src/lib/{firebase,stripe,schemas}
   │
   ▼
src/components/<feature>/         (UI components grouped by feature)
   │
   ├── *.tsx                      ← can import from src/components/ui/ (shadcn primitives)
   │                              ← can import from src/lib/ (utils, schemas, firebase clients)
   │                              ← can import from src/hooks/ (useAuth, useSubscription)
   │                              ← can import from src/contexts/AuthContext
   └── *.test.tsx                 ← co-located
   │
   ▼
src/components/ui/                (shadcn primitives; presentational)
src/lib/                          (utilities + external clients)
src/contexts/                     (auth context)
src/hooks/                        (data fetching hooks)
```

**Rules:**

- Server-only modules (`src/lib/firebase/admin.ts`, `src/lib/stripe/server.ts`, `src/lib/firebase/session.ts`) MUST start with `import 'server-only';`.
- Client components must include `'use client';` directive at the top.
- `src/app/api/.../route.ts` MUST export `runtime = 'nodejs'` (firebase-admin and Stripe SDK both require Node).
- `src/components/checkout/` (PlanCard, PlanCta, CouponInput) is BANNED from being imported by `apps/mobile` — Reader-App gate per Invariant 7.

#### Component Boundaries (within `apps/tooling`)

```
wardentooling.py                          (TUI launcher; subprocess.run([sys.executable, ...]))
   │
   ▼
tools/<tool>.py  OR  tools/<tool>/        (each tool standalone CLI)
   │
   ├── argparse                           ← CLI entry
   ├── run() / main()                     ← split: core logic + CLI parser
   ├── imports utils.* via sys.path.insert
   └── imports tools.frame_labeler MAP_LABELS  ← shared single source of truth
   │
   ▼
utils/<concern>.py                        (stateless pure functions; np in → np out)
config/config.yaml                        (single source of tunable params)
```

**Rules:**

- Tools never import each other's `app.py` files (each is a CLI app).
- Tools share state only via files (PNGs, JSON, YAML).
- The TUI launcher invokes tools via `subprocess.run([sys.executable, ...], cwd=PROJECT_ROOT)`, NOT via direct Python imports — avoids tkinter import side-effects.

### Integration Points

The integration map from `docs/integration-architecture.md` is the definitive reference. Architecture-relevant integration points (annotated with decisions from step 4):

| # | From | To | Mechanism | Decision-relevant note |
|---|------|----|-----------|-----------------------|
| 1 | `apps/web` | Stripe | HTTPS (Stripe SDK) | API pin → 2026-04-22.dahlia per Brownfield Item 1 |
| 2 | Stripe | `apps/web` | HTTPS POST webhook | Subscriptions: invoice.paid, customer.subscription.deleted, customer.subscription.updated (Decision #9), invoice.payment_failed |
| 3 | `apps/web` | Firestore | firebase-admin (server) | Sole writer of users/{uid}, stripe_events/{event_id} |
| 4 | `apps/web` (browser) | Firebase Auth | firebase client SDK | ID token traded for httpOnly session cookie |
| 5 | `apps/web` (browser) | `apps/web` (route handlers) | HTTP same origin | Session cookie carries auth |
| 6 | `apps/mobile` | Firebase Auth | `@react-native-firebase/auth` (post Item 5 migration) | Native module — Keychain/Keystore-backed persistence |
| 7 | `apps/mobile` | Firestore | `@react-native-firebase/firestore` (post Item 5) | Reads only — users/{uid}, detection_config/latest |
| 8 | `apps/mobile` | Firestore (detection_config) | Stale-while-revalidate | Bundled baseline per Decision #2; Firestore overlay only |
| 9 | `apps/tooling` | filesystem | local files | Emits map_config.json (writes schema_version: 1 per Item 7) |
| 10 | `apps/tooling` → operator → Firestore | Manual upload (Decision #8) | firebase CLI | OTA channel between releases |
| 11 | `packages/contracts` | `apps/web` | TS package import | Wired per Decision #6 |
| 12 | `packages/contracts` | `apps/mobile` | TS package import | Already wired |
| 13 | `apps/tooling` | `contracts/` | filesystem read (Python jsonschema) | Per `tooling-SCHEMA-001` |
| 14 | `apps/mobile` | OS Share Sheet | expo-sharing | T1-coach telemetry on confirmed-dispatch |
| 15 | `apps/mobile` | Firebase Analytics | telemetry wrapper (Invariant 3) | Payload allowlist enforced; on-device-only contract |

### Development Workflow Integration

**Development server commands [LOCKED]:**

```sh
# Web dev server
pnpm --filter web dev               # next dev on http://localhost:3000

# Mobile dev server
pnpm --filter mobile start          # expo start (Metro)
pnpm --filter mobile android        # expo run:android (needs dev client)

# Tooling — run a single CLI directly OR via TUI
uv run python apps/tooling/wardentooling.py
uv run python apps/tooling/tools/map_config_generator.py --images <maps_dir>

# Shared codegen (after editing contracts/*.schema.json)
pnpm --filter @warden/contracts build
```

**Build process per surface [LOCKED]:**

```sh
# Web production build
pnpm --filter web build       # next build → .next/

# Mobile Android release bundle (Phase 4 acceptance smoke test)
pnpm --filter mobile exec expo export --platform android   # Hermes bundle ≈5.22 MB
pnpm --filter mobile exec expo prebuild                    # generate native android/
# Then drop into android/ for ./gradlew :app:bundleRelease

# Tooling — no build artifact; outputs are JSON
# Shared contracts — codegen step
pnpm --filter @warden/contracts build
```

**Cross-surface CI (Phase 7) [NEW]:**

```sh
# .github/workflows/ci.yml on every PR + push
pnpm install
uv sync
pnpm typecheck                      # Turbo task — all workspaces
pnpm test                           # Vitest (web) + jest (mobile) + pytest (tooling)
pnpm format:check                   # Prettier
apps/mobile/scripts/reader-app-gate.sh   # Reader-App gate per Invariant 7
# shared-Firebase-project assertion (Decision #3) — inline shell check
# contracts-codegen-check (separate workflow on contracts/** PRs)
```

**Deployment structure [LOCKED]:**

- Web: Vercel auto-detect on push to `main` (no `deploy-web.yml` required; belt-and-suspenders option).
- Firestore rules: `firebase deploy --only firestore:rules` from `apps/web/`. Phase 7 wires `deploy-firestore-rules.yml`.
- Stripe webhook config: manual via Stripe Dashboard; subscribed events list per Decision #9.
- Mobile: manual via Expo prebuild + Android Studio bundleRelease + Google Play Console upload. EAS not configured in V1.
- Tooling: not deployed; runs on operator workstation.
- `map_config.json` Firestore overlay: manual via `firebase firestore:set` per Decision #8 — between Play Store releases for OTA map updates.

### File Organization Patterns Summary

| Concern | Location | Convention |
|---------|----------|------------|
| Source code | `apps/<app>/src/` (TS) or `apps/tooling/{tools,utils}/` (Python) | Per-surface conventions per step 5 |
| Tests | Mobile: `__tests__/`; Web: co-located `.test.ts(x)`; Tooling: `tests/` | Test framework dictates location |
| Config | App roots: `tsconfig.json`, `package.json`, `eslint.config.mjs`, `.env.example` | Per app; root-level for monorepo tooling |
| Static assets | Mobile: `apps/mobile/assets/` (incl. NEW `map_config.json`); Web: `apps/web/public/`; Tooling: `output/` | Per app |
| Documentation | Repo root `docs/` (architecture); per-app `apps/<app>/docs/` (legacy) | `docs/index.md` is the entry point |
| BMad artifacts | `_bmad-output/` (planning); `_bmad-output/legacy/` (pre-merge) | Phase outputs land here |
| Scripts | App scripts: `apps/<app>/scripts/`; root: `package.json` scripts | Reader-App gate at `apps/mobile/scripts/reader-app-gate.sh` |
| CI/CD | `.github/workflows/` (Phase 7) | Per surface + cross-surface gates |
| Contracts | `contracts/*.schema.json` (master) + `packages/contracts/src/generated/` (Zod) | JSON Schema is master; Zod is generated |

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**

All decisions land in a compatible dependency order. The coordinated triples (Decision #1/#6/#9, Decision #2/#7/#8) close together; Brownfield Item 5 (Firebase v12 RN auth migration) is sequencing-blocking for the entitlement state-machine end-to-end test but compatible with Decision #3 (shared Firebase project — `@react-native-firebase` reads project ID from `google-services.json`, which encodes the same project ID as the web client config). The Foreground Service custom config plugin (Brownfield Item 6) is compatible with the OpenCV JSI binding (post-spike): the foreground service hosts the main JS context where the JSI binding lives, avoiding the cross-context state issues `expo-task-manager` would introduce.

The Innovation #1 fallback ladder (spike rung 3 = manual-clip-only V1) is explicitly acknowledged in PRD section 6 as a conditional FR adjustment, not a coherence break — if the spike forces it, the PRD's `mobile-AUTO-SLICE-*` FRs become V2-deferred and the activation timer T1-coach via manual-clip path becomes the only path. Architecture asserts this is a permitted graceful degradation, not a launch slip.

**Pattern Consistency:**

The naming-convention divergence between surfaces (snake_case in Firestore + Python tooling; camelCase wire boundary on web; snake_case mobile-internal because domain types ARE the persistence shape) is deliberate per step 5 and is captured in the surface-local-vs-cross-surface invariants table. Cross-surface contracts (`packages/contracts/`) are snake_case at the JSON Schema layer; auto-generated Zod preserves field names; consumers transform if they want camelCase. No naming conflicts at runtime.

The privacy contract is enforced at three layers: (1) the on-device-only invariant ([INVARIANT 3]); (2) the activation telemetry payload allowlist (Decision #9 / step 5 wrapper); (3) the third-party SDK allowlist (SEC-007). Each layer reinforces the others.

The Reader-App contract is enforced at three layers: (1) build-time CI gate ([INVARIANT 7]); (2) pre-commit hook (`apps/mobile/scripts/reader-app-gate.sh`); (3) `EXPO_PUBLIC_AUTH_BYPASS` deny in release configs ([INVARIANT 8]). Defense in depth — signaling tier, not absolute prevention.

**Structure Alignment:**

Every one of the 55 FRs has a primary owner file mapped in the FR-to-structure section of step 6. The boundaries (features-don't-import-features, web-sole-writer, contracts-cross-language, native-modules-only-via-shared-services) are codified as INVARIANTs and are mechanically enforceable via lint rules + the Reader-App gate. The complete project tree (step 6) accounts for all decisions in step 4 — every NEW file is marked and traceable to a specific decision.

### Requirements Coverage Validation ✅

**Functional Requirements Coverage (55 / 55):**

- Mobile (33/33): all auth-entitlement, import, auto-slice, card-view, cinema-mode, clip-creation, voice-annotation, export-share, autosave-recovery FRs mapped to specific files in `apps/mobile/src/features/*` per step 6.
- Web (13/13): all landing, pricing, auth-checkout, dashboard, webhook, analytics FRs mapped to specific files in `apps/web/src/{app,components,lib}/*`.
- Tooling (13/13): all round-detection, label, hash, validate, warden-analyzer, TUI, schema FRs mapped to `apps/tooling/tools/*`.
- Cross-surface (6/6): entitlement-machine, activation-telemetry, schema-conformance, reader-app-gate, map-config-delivery FRs mapped to specific cross-surface implementation surfaces.

**Non-Functional Requirements Coverage (41 / 41):**

- **Performance (10/10):** PERF-001 (activation timer ≤300s) covered by `cross-ACTIVATION-001` telemetry contract. PERF-002/003/004/005 (mobile timing budgets) covered by spike + "no player swap" view-mode pattern + 4-stage MMKV-checkpointed pipeline. PERF-006/007 (web LCP/FCP/TTI) already met by current implementation; architecture inherits regression-coverage requirement. PERF-008 (webhook ≤1s p95) already met. PERF-009 (tooling linear scaling) covered by reference implementation. **PERF-010 (mobile reference-device floor): TBD pending spike — architecture's load-bearing first deliverable.**
- **Security (7/7):** SEC-001/002/003/006 covered by webhook signature verification + Decision #7 firestore.rules + dual-strategy idempotency contract. SEC-004 (no Stripe Mobile SDK) covered by Reader-App gate ([INVARIANT 7]). SEC-005 (HttpOnly cookie persistence) [LOCKED]. SEC-007 (third-party SDK allowlist) covered by Reader-App gate's transitive-dep scan + the shared-services native-module-access pattern.
- **Reliability (6/6):** REL-001 covered by AUTOSAVE FRs + MMKV checkpoint pattern. REL-002 (30-day offline) covered by entitlement state machine `offline-grace` state + Decision #2 hybrid `map_config.json`. REL-003 (webhook delivery delay tolerance) covered by `stripe_events/` manual-replay path. REL-004 (entitlement transition latency) covered by webhook → Firestore → mobile foreground re-fetch cycle. REL-005 (tooling determinism) covered by stateless-pure-function pattern. REL-006 (accuracy floors) covered by `hash_validator` regression suite + `tooling-VALIDATE-001`.
- **Accessibility (6/6):** A11Y-001/002/003/004 (web WCAG 2.1 A) [LOCKED] from existing implementation. A11Y-005/006 (mobile contrast + state indicators) covered by HUD design tokens; architecture defers deeper specs to UX design (Phase 6 step 4).
- **Privacy (5/5):** PRIV-001/002 covered by on-device-only invariant + activation telemetry allowlist. PRIV-004 (no card primitives in logs) covered by structured-logs pattern + PCI-offloaded boundary. PRIV-005 (third-party voice consent) handled by PRD as out-of-scope for technical enforcement. PRIV-003 (clip deletion cascade) — see Gap Analysis (Important Gap #2): architecture introduces `clipDeletion.ts` cascade in Sprint 3.
- **Observability (4/4):** OBS-001/002 covered by activation telemetry + funnel events. OBS-003 covered by [INVARIANT 3] (no user content in crash reports). OBS-004 covered by structured-logs JSON pattern.
- **Internationalization (3/3):** I18N-001/002/003 (FR-locked mobile, EN-with-FR-hero web) [LOCKED] from existing implementation; architecture preserves.

### Implementation Readiness Validation ✅

**Decision Completeness:** all seven escalated decisions resolved; all four brownfield architecture-owned items resolved; the load-bearing pre-PRD performance spike is queued as Sprint 3 first work item with explicit ladder fallbacks.

**Structure Completeness:** project tree complete (every file location accounted for, including NEW files introduced by step-4 decisions); component boundaries codified; integration points mapped; FR-to-structure mapping covers all 55 FRs.

**Pattern Completeness:** 12 cross-surface invariants + surface-local conventions table + concrete examples + anti-patterns. Naming, structure, format, communication, process patterns all covered. CI enforcement specified (Phase 7 backlog) with V0 fallback to local + pre-commit hooks.

### Gap Analysis Results

**Critical Gaps: 0.** No decisions block V1 implementation start.

**Important Gaps (Sprint 3 should address):**

1. **Pre-PRD performance spike not yet executed.** Architecture's load-bearing first deliverable; V1 launch criteria depend on outcome. Spike is queued; this is not a missing decision — it is a queued work item. PERF-010 stays TBD until spike publishes the measured floor.

2. **PRIV-003 clip deletion cascade — implementation hook not deeply specified.** Architecture decides: clip deletion uses SQLite CASCADE for row deletion (already present in schema) + a new `apps/mobile/src/features/clip-export/clipDeletion.ts` service that, on `mobile-CLIP-005` deletion, walks `audio_comments.file_path` + `clip_exports.file_path` + clears `processing.<sessionId>.*` MMKV keys for the parent session, and removes filesystem entries via `expo-file-system.deleteAsync`. Sprint 3 story: "Implement clipDeletion.ts cascade; verify per-PRIV-003 (no orphaned MP4/.m4a after delete)."

3. **V1 crash reporting SDK decision.** PRD does not mandate; step 5 mentioned Sentry/Crashlytics hypothetically as V2. **Architecture decides: V1 ships with NO crash reporting SDK.** Rationale: reduces attack surface (third-party SDK not in the dependency allowlist; aligns with `cross-READER-APP-001` transitive-dep scan posture); saves bundle weight on the reference Poco X5 device; PRD's user base is the FR/BE EVA After-h beachhead with direct Discord channel for incident reporting. Stack traces in dev mode + manual user reports are sufficient for V1. V2 may add Sentry once user volume justifies the operational cost; if added, MUST exclude user content per [INVARIANT 3] / OBS-003.

4. **Sprint 3 work-stream parallelization explicit.** The pre-PRD performance spike gates the rest of Sprint 3 mobile scope, but other work streams can run in parallel:
   - **Spike** (gating) — first work item; binds PERF-010 + ladder rung.
   - **Brownfield Item 5** (Firebase v12 RN auth migration; Stories 3.A → 3.F) — gates the entitlement-state-machine end-to-end test (Story 3.D). Can start once Story 3.A (deps + prebuild) verified.
   - **Foreground Service plugin** (Brownfield Item 6) — independent of spike; can land in parallel.
   - **Brownfield Item 1** (Stripe API pin bump) — independent of mobile work; can land any time in Sprint 3.
   - **Decision #1/#6/#9 triple** (schema tighten + web wire + trialing handler) — independent of mobile spike; web stories can run in parallel with mobile work.
   - **Decision #2/#7** (hybrid `map_config.json` + firestore.rules deploy) — depends on Decision #1 (contract bump) and Brownfield Item 7 (`schema_version`).
   - **Reader-App CI gate** (Decision #7 spec implementation) — independent; can land in parallel.
   - **Activation telemetry contract** — depends on Brownfield Item 5 (post-Firebase-migration).

**Minor Gaps (V1.1 polish, not V1 blockers):**

5. **Mobile ESLint config** — placeholder echo; `@warden/eslint-config` exists but mobile doesn't consume. Phase 7 wires.
6. **Tooling mypy + ruff** — placeholder echos; Phase 7 wires.
7. **CI workflows in `.github/workflows/`** — Phase 7 wires; V0 fallback is local + pre-commit hooks.
8. **EAS Build for mobile** — manual today (`expo prebuild` + Android Studio bundleRelease + Google Play Console upload); Phase 7 candidate.
9. **Per-route `loading.tsx` in web App Router** — currently inline `<Skeleton />`; Next 16 supports per-route loading boundaries; future polish.
10. **Mobile A11Y-005/006 deeper specs** — touch targets + no-color-only state indicators covered by HUD design tokens; UX design (Phase 6 step 4) owns the deeper specification.

### Validation Issues Addressed

| Gap | Resolution | Sprint disposition |
|-----|------------|-------------------|
| Important Gap #1 (spike not executed) | Already queued as Sprint 3 first work item | Sprint 3 |
| Important Gap #2 (clip deletion cascade) | Architecture-decided: `clipDeletion.ts` service + SQLite CASCADE + filesystem cleanup | Sprint 3 |
| Important Gap #3 (V1 crash reporting) | Architecture-decided: NO crash reporting SDK in V1 | Documented; no V1 work |
| Important Gap #4 (Sprint 3 parallelization) | Architecture documents work-stream dependency map (above) | Sprint planning consumes |
| Minor Gaps #5-#10 | Phase 7 backlog | Post-V1 |

### Architecture Completeness Checklist

**Requirements Analysis**

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (high architectural-coordination, NOT regulatory)
- [x] Technical constraints identified (locked PRD constraints + brownfield triage)
- [x] Cross-cutting concerns mapped (8 cross-cutting concerns identified)

**Architectural Decisions**

- [x] Critical decisions documented with versions (all 7 escalated decisions resolved + 4 brownfield items planned)
- [x] Technology stack fully specified (per step 3 starter inheritance + step 4 brownfield migration plan)
- [x] Integration patterns defined (15 integration points cataloged with decision-relevant notes)
- [x] Performance considerations addressed (10 PERF NFRs covered; PERF-010 spike-bound)

**Implementation Patterns**

- [x] Naming conventions established (cross-surface invariants + surface-local table)
- [x] Structure patterns defined (feature-sliced mobile, App-Router web, modular CLI tooling)
- [x] Communication patterns specified (Stripe webhook contract, telemetry allowlist, contract codegen flow)
- [x] Process patterns documented (error handling per surface, loading states, auth flow, validation timing)

**Project Structure**

- [x] Complete directory structure defined (annotated tree with NEW markers)
- [x] Component boundaries established (per-surface boundary diagrams + cross-surface integration map)
- [x] Integration points mapped (15-row integration table with decision annotations)
- [x] Requirements to structure mapping complete (all 55 FRs mapped to primary owner files)

### Architecture Readiness Assessment

**Overall Status:** **READY WITH MINOR GAPS** (architecture supports V1 implementation start; the pre-PRD performance spike is the sole remaining work item that gates Sprint 3 mobile scope finalization; all other Important Gaps have decided resolutions queued as Sprint 3 stories; Minor Gaps are V1.1 polish).

**Confidence Level:** **High.** The decision set is coherent, every requirement is traced to an implementation surface, the brownfield reconciliation is planned in dependency order, and the spike-first work sequence binds the only remaining unknown (reference-device performance floor) before Sprint 3 commits scope.

**Key Strengths:**

- **Brownfield-honest:** the architecture inherits frozen scaffolding choices and reconciles seven cross-cutting decisions without re-litigating PRD locks.
- **Privacy contract enforced at three layers:** on-device-only invariant + activation telemetry allowlist + third-party SDK allowlist. Defense in depth.
- **Reader-App contract enforced at three layers:** build-time CI gate + pre-commit hook + dev-bypass-env-var deny. Signaling tier, not absolute prevention — matches PRD intent.
- **Cross-language schema-driven binding** is the moat mechanism: JSON Schema master + auto-generated Zod + Python `jsonschema` validation. Drift is mechanically caught.
- **Innovation #1 fallback ladder** is explicit and pre-decided — the spike's worst-case outcome (manual-clip-only V1) is a graceful degradation, not a launch slip.
- **FR list is binding;** every architectural decision traces back to one or more FRs; every FR has a primary owner file in the project structure.

**Areas for Future Enhancement:**

- **Phase 7 CI/CD wiring** — `.github/workflows/`, mobile ESLint, tooling mypy + ruff, EAS Build, contracts-codegen-check.
- **iOS Phase 2** — gated on Apple license + FFmpeg-kit iOS support + Reader-App posture against App Review. Architecture asserts cross-platform-ready V1; iOS is glue work.
- **V2 features** per PRD section 3 (Discord OAuth, coupon admin UI, custom analytics dashboard, OCR scores/kills, etc.) — out of V1 architecture scope.
- **V3 vision** per PRD (broader tactical-FPS expansion, referral system, full FR localization, desktop) — long-arc; tooling moat compounds here.

### Implementation Handoff

**AI Agent Guidelines (V1 implementation):**

- **Read first:** PRD (`_bmad-output/prd.md`), this architecture doc, and the surface-relevant `docs/architecture-<surface>.md`. The 12 cross-surface invariants are mandatory; the surface-local conventions are surface-specific.
- **FR-to-structure mapping** (step 6) is the lookup table — given an FR, find the primary owner file. Add new files only when an FR has no existing owner.
- **Stripe webhook handler** (`apps/web/src/lib/stripe/webhooks.ts`) requires the self-namespace import pattern — DO NOT refactor away ([INVARIANT 4]).
- **Mobile native modules** (FFmpeg, OpenCV, MMKV, SQLite) are accessed ONLY via `apps/mobile/src/shared/services/*.ts`. NO feature directly imports these.
- **Schema edits** go through `contracts/<schema>.schema.json` only; re-run `pnpm --filter @warden/contracts build` and commit both schema + regenerated TS.
- **Run before push:** `pnpm typecheck && pnpm test && pnpm format:check`. Mobile changes also run `apps/mobile/scripts/reader-app-gate.sh`.

**First Implementation Priority (Sprint 3 ordering):**

1. **Pre-PRD performance spike** (architecture-led; gates everything else; binds PERF-010 + Innovation #1 ladder rung). Deliverable: `_bmad-output/architecture-spike-perf-floor.md`.
2. **In parallel with spike:** Foreground Service config plugin (Brownfield Item 6); Brownfield Item 1 Stripe API pin bump; Reader-App CI gate (Decision #7 spec).
3. **Post-spike:** Firebase v12 RN auth migration (Stories 3.A → 3.F per Brownfield Item 5 sequence); Decision #1/#6/#9 triple (schema tighten + web wire + trialing handler).
4. **After Brownfield Item 5 lands:** Six-state entitlement state machine (`deriveEntitlementState`); activation telemetry contract; clip-deletion cascade (Important Gap #2 resolution).
5. **V1-blocking deploy:** Decision #2 hybrid `map_config.json` + Brownfield Item 7 `schema_version` + Decision #7 firestore.rules prod deploy + Decision #8 documented manual upload.

**Out of architecture scope:**

- UX design (Phase 6 step 4 — `bmad-create-ux-design`) owns: detailed component visual design, interaction states, mobile A11Y-005/006 deeper specs, copy decks (FR-locked hero verbatim; deferred-billing copy verbatim).
- Epic/story planning (Phase 6 step 5 — `bmad-create-epics-and-stories`) owns: breaking the Sprint 3 work-stream map above into discrete epics + stories with acceptance criteria.
- Sprint planning (Phase 6 step 6 — `bmad-sprint-planning`) owns: assigning stories to sprints; modeling solo-dev capacity; per-surface maintenance budget per brief Risk #8.
- Implementation (Phase 7) owns: writing the code per the architecture's spec.
