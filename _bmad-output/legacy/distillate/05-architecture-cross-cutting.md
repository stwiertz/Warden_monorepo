> This section covers cross-cutting architectural concerns that span all three apps. Most important reference for the unified architect agent. Part 5 of 8 of the Warden legacy distillate.

## `map_config.json` Pipeline (Tooling → Mobile)
- Producer: `apps/tooling/tools/map_config_generator.py` (legacy) and `apps/tooling/tools/hash_comparator.py` (newer; coexists with legacy, not unified to avoid breaking legacy path)
- Default output path: `output/map_config.json`; written via `json.dump(..., indent=2)`
- Purpose: portable map-identification fingerprint config consumed by mobile (mobile cannot run OpenCV training); 64-bit perceptual hash (pHash) of map-name text ROI per map
- Generation triggered manually via `wardentooling.py` → "Tool 3 — Generate Map Config" or `hash_comparator.py` direct
- Consumers (legacy):
  - `apps/tooling/tools/warden_analyzer.py` (Tool 5) reads `output/map_config.json` (default) for inline map ID via `predict_map(canvas, ref_hashes, hash_size, method, shift_tolerance)` from `hash_validator.py`
  - `apps/tooling/tools/match_preview` reads it for per-segment map ID
  - `apps/tooling/tools/hash_validator.py` (Tool 4) reads it for accuracy regression testing
  - `apps/mobile` (Warden RN): consumed by `src/features/video-processing/detectionConfig.ts` (schema + validator), `detectionConfigService.ts` (Firestore fetch + MMKV cache + singleflight), `detectionConfigBootstrap.ts` (startup wiring + offline-first-launch gate); used by gameDetector + mapIdentifier + blackScreenDetector

### `map_config.json` Schema (canonical fields)
- Top-level fields written:
  - `roi: {x, y, width, height}` — HUD map-name region at 1920×1080 reference (originally `x:827, y:79, w:264, h:22`, tunable)
  - `canvas_size: int` — square canvas size (typically 64)
  - `hash_size: int` — typically 8 (→ 64-bit hash) or 16 (→ 256-bit)
  - `hash_method: string` — `'dhash'` | `'ahash'` | `'phash'` (operational default `dhash` due to pHash cross-video inconsistency)
  - `tile_cols: int`
  - `maps: {map_name: hex_hash_string}` — per-map reference hash
  - `reference_resolution` — echo (added later)
  - `text_anchor_width: int` — written only when truthy/non-zero/non-None
  - `threshold_hash: bool` — written only when True
  - `recognition_threshold: int` — scaled value persisted at generation; formula `round(base_threshold * (hash_size/8)**2)`; e.g. 8→10, 12→22, 16→40
  - `shift_tolerance: int` — Hamming-shift tolerance (=2)
- Field NOT stored: processing resolution at which hashes were computed (known gap — silent mismatch risk if Tool 3 re-run at non-default resolution; deferred enhancement)
- Backward compat: `.get("text_anchor_width")` → None and `.get("threshold_hash", False)` → False reproduce pre-change validator behaviour

### Schema Validation
- Legacy state: NOT formally enforced — JSON shape is implicit, defined by producer + replicated in consumer reads; no JSON Schema document or runtime validator in legacy tooling repo
- Monorepo target: `contracts/map-config.schema.json` is the unified schema location going forward (cross-app contract for tooling↔mobile↔web); legacy validation is best-effort/by convention only
- Validation in unified architecture: `jsonschema` Python (tooling) + Zod TS (mobile) via `json-schema-to-zod` codegen
- OPEN QUESTION: schema-version field strategy — sidecar (`<video>.matches.json`) uses `schema_version: 1` but `map_config.json` has no version field; unified architect must decide

### `map_config.json` Runtime Delivery to Mobile — OPEN QUESTION
- Legacy mobile architecture: Firestore-fetched at runtime + MMKV cache (`detection.config` key) + bundled default config shipped with app as final fallback; tunable without app redeploy; Story 7.4 lands as no-op shim until Story 7.5 consumes it; config version checked, stale caches refreshed on next online launch
- Alternative under consideration: bundled-as-Metro-asset (ships with app, requires release to update)
- DECISION REQUIRED in unified architecture: Firestore-fetched (legacy mobile preference, allows config tuning without app release) vs bundled Metro asset (simpler, no online dep) vs hybrid
- Firestore path implications: must work offline (MMKV cache + bundled fallback); first-launch gate for online config fetch; config staleness policy

### `map_config.json` Cross-Subsystem Field Reads
- BSD reads ROI/threshold per map (uses `roi_zones` config section, sibling of map_config)
- game-detector reads hash refs + HUD config
- warden_analyzer reads `roi`, `canvas_size`, `hash_size`, `hash_method`, `tile_cols`, `text_anchor_width`, `threshold_hash`, `recognition_threshold`, `maps`, `shift_tolerance`
- hash_validator reads same fields, plus needs matching `--resolution` flag (resolution gap)
- mobile (legacy `isPaid`-based world): mapIdentifier reads hash refs + ROI; gameDetector reads HUD config; minimap geometry from minimap_identification.configs[] (separate config section, see below)

### Supported Maps (canonical 14)
- Single source of truth: `apps/tooling/tools/frame_labeler.py:19-34` — `MAP_LABELS = [horizon, engine, outlaw, ceres, artefact, silva, bastion, polaris, coliseum, the_cliff, helios, atlantis, the_rock, lunar_outpost]`
- Discrepancy: project-sprint.md says 14, map-config-generator spec text says "15 EVA maps", `MAP_LABELS` lists 14 — canonical = 14; minimap-zone-selector and minimap-view-mode import from this list
- 4 maps lack reference hashes in current `map_config.json`: bastion, coliseum, lunar_outpost, the_rock — pending labeled video data
- Adding new map workflow: capture video → Tool 1 frame extraction → Tool 2 frame labeler labels start/end/score per map → Tool 3 regenerates `map_config.json` (incrementally adds new map's hash) → Tool 4 validates accuracy ≥ target → ship config to mobile

### Related: `minimap_identification.configs[]` (separate but related config block)
- Lives in `config/config.yaml` under `minimap_identification.configs[]` (NOT in `map_config.json` itself)
- Versioned list of `{id, roi, identification_threshold, maps:{map_name:{zones:[...]}}}`; supports New/Clone/Delete via id-keyed upsert
- Produced by `tools/minimap_zone_selector` (interactive Tk GUI)
- Hue handling: circular mean (sin/cos→atan2) for wraparound; circular std with `max(R, 1e-9)` guard
- Future: this versioned-zone approach replaces unreliable map-name pHash for runtime map identification — open whether mobile consumes via separate config or merged into `map_config.json`

### `hud_versions[]` (yet another config block)
- Top-level `hud_versions:` key in `config.yaml` (coexists with `roi_zones`; NO migration)
- Each version `{id, shared_rois:{scores, health_left, health_right}, maps:{map_name:{tight_roi, padding_px}}}`
- Padding stored separately so author can revisit slider in later session
- Produced by `tools/minimap_view_mode` (NOT YET IMPLEMENTED, ready-for-dev)
- Consumed by mobile minimap rendering (Stories 7.1-7.3+7.6) — view mode 3-value: Full / Minimap / Minimap+HUD

## `users/{uid}` Firestore Document — CONFLICT REQUIRES RECONCILIATION

### Web Writes (Stripe webhook → Firebase Admin)
- Snake_case fields (matches Stripe webhook payloads, no conversion at boundary):
  - `status`: "active" | "past_due" | "canceled" (and "canceling" used in UI badge for cancel-at-period-end)
  - `plan`: "monthly" | "yearly"
  - `current_period_end`: Firestore Timestamp (converted from Stripe Unix seconds)
  - `stripe_subscription_id`: string
  - `stripe_customer_id`: implicit from webhook payloads (set when invoice.paid creates/updates doc)
  - `redeemed_batches`: array (referenced in naming-convention examples)
- Email: implied via Auth (FR13 displays account email)
- Doc creation: webhook handler creates `users/{uid}` if absent on `invoice.paid` (FR21 / Story 4.2 acceptance)
- Canonical write: `SubscriptionResponse` Zod schema in `src/lib/schemas/{user.ts,subscription.ts,webhook-events.ts}` — referenced as part of webhook validation surface
- Idempotency: dual strategy — (1) event ID dedup stored in Firestore (skip if already processed, return 200); (2) Firestore transactions to check current state before update
- Reliability: 200 response within 5s (NFR14); Firestore syncs within 30s of webhook (NFR16); Stripe API transient failures retried up to 3 attempts (NFR13)

### Mobile Reads
- Mobile reads `user.isPaid` boolean to grant/deny app access (FR30); validated at login + periodically when online (FR32); mobile is read-only
- Subscription check in `src/features/auth/subscriptionService.ts`
- Reader App model means mobile NEVER references plans/prices/Stripe IDs — only the boolean
- 30-day offline cache via MMKV (`auth.token`, `auth.user` keys); NFR9
- First connection requires online login; subsequent sessions use cached auth

### CONFLICT
- **CONFLICT: mobile says `isPaid: boolean`; web writes `status: string` + `plan: string` + `current_period_end: Timestamp` + `stripe_subscription_id: string` + `stripe_customer_id` + `redeemed_batches: array` — unresolved, must reconcile in unified architecture**
- The legacy mobile and legacy web docs were written independently; mobile assumes a derived/computed boolean while web stores rich state
- Mobile architecture already lists `contracts/user-doc.schema.json` as the unified target — but the schema content itself must be decided
- Possible reconciliation paths:
  1. Mobile reads `status === "active"` directly (drop `isPaid`); requires mobile code update
  2. Web webhook also writes `isPaid: boolean` derived from `status` (denormalized convenience field); doubles writes but minimal mobile change
  3. Cloud Function maintains `isPaid` derived field synced from `status`; trigger-based
- DECISION REQUIRED: unified architect must pick one model; both apps must align before unified release
- Unified PRD (English) must capture this resolved schema

### Auth Provider — Same Firebase Project
- Firebase project SHARED between mobile (Warden) and web (WardenWeb) — same Firebase Auth, same Firestore database, same project
- Auth provider config (apiKey, authDomain, projectId) MUST align between web and mobile clients
- Firestore region locked to `europe-west` for GDPR — mobile must use the same project/region
- Mobile uses Firebase JS SDK (modular v9+, no native module); Web uses Firebase JS SDK v12.9.x (client) + Firebase Admin SDK (server)
- Auth providers: Google Sign-In + Email/Password (web supports both via `signInWithPopup` and `signInWithEmailAndPassword`); mobile uses Firebase JS Auth flow
- Session: web uses HttpOnly + Secure + SameSite=Lax cookies (7-day expiry, activity-based refresh); mobile uses MMKV-cached auth (30d offline)
- Firebase Analytics: web conditionally loaded after cookie consent (FR29); mobile config independent (and mobile is offline-first so analytics surface is limited)

### Other Firestore Collections
- `coupon_batches/{batchId}` — coupon redemption tracking; client read-only, writes from Stripe dashboard

### Naming Convention (Cross-System)
- Firestore stores snake_case (matches Stripe webhook payloads → no conversion at boundary)
- Code uses camelCase (TS/React)
- Conversion via Zod `.transform()` in `src/lib/firebase/`
- Date formats: Firestore=Timestamp; Stripe=Unix seconds; JSON API responses=ISO 8601; UI=`Intl.DateTimeFormat` (no date library)

## Reader App Compliance Model (cross-app architectural constraint)
- 100% external monetization (web NextJS + Stripe) — 0% store commission
- Mobile app contains: login screen only — no IAP, no subscribe button, no pricing, no payment links, no plan names (FR33)
- Login → check Firebase `user.isPaid` (or resolved equivalent) → unlock or block
- Reader App = Netflix-style precedent
- Architectural implication: mobile NEVER imports Stripe SDK, NEVER references Stripe IDs/plans; web is sole writer to subscription state; mobile is sole reader

## Brownfield Issues Parked for Phase 6 Triage
### Web
- Stripe API version pin mismatch: code pins `"2026-03-25.dahlia"` while installed `@stripe/stripe-js` types are `"2026-04-22.dahlia"` — type-level inconsistency to resolve
- Test-file type errors (unspecified location)
- PlanCta hydration mismatch (`disabled={null}` vs `disabled={true}`) — known issue, scheduled in web Story 7.2
- Carried retro debt: Firestore security rules not yet deployed to production (web Story 7.1), Firebase auth E2E not fully verified (web Story 7.2)
- Vitest parallelism flake (action item from Epic 4 retro)

### Mobile
- `firebase/auth` `getReactNativePersistence` removed in v12 — must adapt mobile auth persistence approach
- Lib versions not pinned (Expo manages compatibility, fixed at init)
- Foreground Service Android: config plugin vs `expo-task-manager` — to evaluate

### Tooling
- No automated test framework — all validation manual via Tool 4 reports + visual `--preview` inspection
- `map_config.json` does not persist generation resolution — silent mismatch risk if Tool 3 re-run at non-default resolution
- HUD-brightness threshold (`hud_brightness_max`) is global; future map with bright HUD background near KDA could trigger false-end detections
- KDA ROI vulnerable to prolonged occlusion (extended killcam, victory cinematics)

## Monorepo Structure (already locked)
- pnpm workspaces + Turborepo
- `.npmrc` `node-linker=hoisted` (Metro can't traverse pnpm's nested store)
- `apps/` directory:
  - `apps/mobile` — Expo/React Native (legacy `Warden`)
  - `apps/web` — Next.js (legacy `WardenWeb`)
  - `apps/tooling` — Python CLI (legacy `Warden-tooling`); joins as Python workspace member via uv
- `packages/` directory:
  - `packages/contracts` — `map-config.schema.json`, `user-doc.schema.json` (cross-app contracts)
  - `packages/tsconfig` — shared TypeScript config
  - `packages/eslint-config` — shared ESLint config
- BMad install at `_bmad/`; output at `_bmad-output/`
- This distillate lives at `_bmad-output/legacy/distillate/`
- Phase status: Phase 4 complete (mobile import + Expo + Metro wiring verified); current commits show monorepo merge mostly done
- Acts:
  - Act I: monorepo skeleton + apps imported (web phase 2, tooling phase 3, mobile phase 4) — DONE
  - Act II: unified BMad re-planning (THIS DISTILLATE FEEDS INTO IT)
  - Phase 6 (parked): brownfield issue triage

## Cross-App Data Flow at Runtime
- Marketing/discovery: Discord coupon link → web Landing → web Pricing → web Auth modal → Stripe Checkout (Stripe-hosted page) → Stripe webhook → Firebase Admin writes `users/{uid}` to Firestore (status=active, plan, current_period_end, stripe_subscription_id, etc.)
- Mobile entitlement: app launches → Firebase Auth login (online required first time) → reads `users/{uid}` → checks isPaid (or resolved equivalent) → unlocks features → caches in MMKV (30d offline)
- Detection config: tooling produces `map_config.json` (manual / on-demand) → uploaded to Firestore (or bundled — open question) → mobile fetches at startup → cached in MMKV `detection.config` → consumed by gameDetector + mapIdentifier + blackScreenDetector
- Clip distribution: mobile exports standalone MP4 → OS Share Sheet → Discord/WhatsApp inline playback → recipient watches without app install (web/mobile loop ends here, no analytics on share recipients)
- Subscription management: web Customer Portal handles history/upgrade/cancel/payment-method updates → Stripe webhook updates `users/{uid}` → mobile reads on next dashboard load (or app launch)

## Cross-Cutting Naming & Convention Decisions
- Firestore: snake_case fields (matches Stripe payloads); code-side camelCase via Zod transforms in web; mobile reads must align
- Mobile DB (SQLite): snake_case plural tables, snake_case cols, `{table_singular}_id` FKs
- Mobile MMKV: dot-notation keys (`auth.token`, `prefs.viewMode`, `detection.config`)
- Tooling: ROI coords stored at fixed reference resolution 1920×1080 (NOT normalized 0.0-1.0); rationale = consistency with rest of codebase
- API response shape (web): success `{ data: { ... } }`; error `{ error: { code: "ERR_CODE", message: "..." } }`
- French↔English: mobile UI = French; web UI = English with French tagline; unified PRD = English (for downstream BMad agents); mobile PRD originally French, sprint-change-proposal-2026-05-05 + post-pivot edits in English are AUTHORITATIVE for current state

## Open Questions Surfaced for Unified Architecture
- `users/{uid}` schema reconciliation (CONFLICT — see above)
- `map_config.json` runtime delivery to mobile (Firestore vs bundled vs hybrid — see above)
- `map_config.json` schema-version field strategy (sidecar uses `schema_version: 1`, main config has no version field)
- `minimap_identification.configs[]` and `hud_versions[]` runtime delivery (currently in `config.yaml`, not in `map_config.json`) — should they be merged into the unified config artifact, or stay separate?
- Persisting generation resolution into `map_config.json`
- `bsd_roi_debugger.py` per-video output subfolder convention
- Future "new source" extension for non-video Tool 2/Tool 3 inputs in TUI launcher
- Foreground Service Android: Expo config plugin vs `expo-task-manager`
- iOS Phase 2: validate FFmpeg fork config plugin works on iOS build
- Auto-detection vs manual map selection in minimap-view-mode (currently manual; auto deferred to match-preview)

## Risks Carried into Unified Planning
- HIGH (mobile): ffmpeg-kit-react-native deprecated Jan 2025 / archived June 2025 — community fork `jdarshan5` actively monitored, Plan B = custom native module via Expo Modules API
- HIGH (web): Stripe webhook sync data integrity — mitigated by idempotent handlers + signature verification + retry; resolved via Epic 4 dual-strategy idempotency (already shipped)
- MEDIUM: Process killed by Android OS in background — foreground service notification, save state, resumable from checkpoint
- MEDIUM: Foreground Service Android config — additional Expo config plugin or `expo-task-manager` evaluation
- MEDIUM: `users/{uid}` schema split — must resolve before unified mobile↔web release; risk of subscription state desync
- MEDIUM: `map_config.json` schema drift — without unified contract validation, tooling output and mobile consumer can drift
- LOW: Keyframe spacing variable — long-GOP black-screen detector fallback
- LOW: Map not identified by pHash — mark `map_name='unknown'`, navigation still works
- LOW: Detection config Firestore unreachable — MMKV cache, then bundled default config
- LOW: Codec unsupported at import — strict validation + clear error
- MARKET: niche size — validate 20 early-adopter coupons in 3mo
- RESOURCE: solo dev — ultra-lean MVP, Firebase simplifies backend
- TECHNICAL: React Native bridge perf — native modules if overhead too high
- TECHNICAL: FFmpeg/OpenCV mobile perf — PC prototype first (validated via R&D 2026-04 on KDA/HSV + pHash methodology)
