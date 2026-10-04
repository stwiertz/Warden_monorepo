# Story 1.13: Hybrid map-config delivery — bundled per-HUD baseline + post-auth Firestore overlay (kills the first-launch gate)

Status: done

<!-- Created 2026-10-04 by /bmad-create-story 1.13 (claude-opus-5-5). Trigger: Story 12.4d's V1 BLOCKER
     (deferred-work.md:315, apps/mobile/bench/12-4d/REPORT.md §7). Epic text: epics-and-stories.md:1023-1050,
     amendments 2026-05-15 + 2026-07-16 (both forks resolved here, in one pass). -->

## Story

As **Stephane**,
I want **the app to always analyse video with the Metro-bundled per-HUD `map_config.<hud>.json`, upgraded — after sign-in, in the background, never blocking — by a revision-gated Firestore overlay at `detection_config/latest` that carries each config as exact JSON text**,
so that **video processing can never again be blocked by a Firestore read (offline, permission-denied, missing doc or bad upload all fall back to the bundle), and new map zones can still ship between Play Store releases without corrupting the map order the native packer depends on.**

## Why now (the trigger)

On 2026-10-04 Story 12.4d's device runs could not start processing on a **connected** phone: *"Initial setup requires internet — open the app once while online."* The chain:

```
App.tsx:42  bootstrapDetectionConfig()            ← at MOUNT, before auth resolves
  → detectionConfigService.getDetectionConfig()   ← reads v1 pHash doc detection_config/latest
  → Firestore PERMISSION_DENIED                   ← apps/web/firestore.rules allows only users/{uid}
  → every non-malformed failure → OfflineFirstLaunchError   ← mislabelled
  → MMKV flag detection.offlineFirstLaunchBlocked
  → useVideoProcessing.ts:52-67 refuses to start
```

…and the 12.4c pipeline **does not read that document at all** — detection runs on the bundled `apps/mobile/assets/detection/map_config.v2.json` via `mapConfig.ts`. Three defects (wrong rules, wrong timing, wrong label) gate the product on a config nothing consumes. [Source: deferred-work.md:315; bench/12-4d/REPORT.md:180-200]

## Kickoff decisions (made at create-story; Stephane may override before dev — see Questions)

| # | Fork | Decision | One-line rationale |
|---|------|----------|--------------------|
| D1 | Per-HUD files vs manifest (amendment 2026-05-15, SCP-2026-05-15:376) | **Per-HUD files + a TypeScript registry module as the manifest** (`bundledMapConfigs.ts`). **No JSON manifest file.** | Metro resolves only *static* `require`/`import`; a JSON manifest naming file paths cannot be resolved at runtime, so the "manifest" must be code anyway. The emitter already writes one `map_config.<hud>.json` per HUD (`map_config_emitter.py:144`). Do NOT confuse with the tooling zone-fragment `apps/tooling/output/zones/v2/manifest.json` (an emitter input, unrelated). |
| D2 | Overlay shape + the ORDER TRAP | **One doc `detection_config/latest` = an envelope** `{envelope_version: 1, revision, configs: {<hud>: {config_json: "<exact emitted text>", sha256}}}`, mastered as `contracts/detection-config-envelope.schema.json`. | Firestore does not preserve map-key order; `WardenRulePacker.orderedMapNames` recovers map order from the raw JSON **text** (12.2 lost a parity run to a permutation). A string field carries order byte-for-byte. Single doc keeps the `detection_config/latest` path that 1.14/1.15/1.16 and architecture.md:1023-1025 already name. The `revision` lives in the envelope because the unified config schema has `additionalProperties: false` and no `version` field — the old "gated by `version`" (architecture.md:392) cannot apply to the config itself. |
| D3 | v1 service: delete or rewrite | **Delete** `detectionConfig.ts`, `detectionConfigService.ts`, `detectionConfigBootstrap.ts` + their 3 suites; **new** `mapConfigOverlay.ts` re-implements the proven parts (singleflight, MMKV memo, discard-corrupt-cache). | The v1 shape (`roi_zones`/`thresholds`/`maps: slug→pHash`) has zero consumers since 12.4c (only a comment in `mapIdentifier.ts:5`). Rewriting in place would keep a misleading name, the `version`-on-config model and ~20 tests of a dead shape. Same Firestore path, new payload. |
| D4 | Real HUD selection BEFORE `analyzeSession` (12.4c review D2, deferred-work.md:309) | **OUT of scope — re-homed.** | Only one HUD config exists (v2); the schema enum is `v1`/`v2` and there is no v1 labelled data, so there is nothing to choose between. Real selection needs a native HUD-zones pre-pass over sampled keyframes — engine work, not delivery work. `resolveSessionHudVersion` stays as the post-hoc check. Home: the first story that bundles a second HUD's config. |
| D5 | When the Firestore read happens | **After auth only**: triggered when `useAuthStore` gains a non-null user (not at mount, not under `EXPO_PUBLIC_AUTH_BYPASS`), fire-and-forget, never awaited by processing. | Architecture Decision #2/#7 already say "mobile reads only after auth (post-T0)" (architecture.md:398, :539); the rule 1.14 writes is `request.auth != null`. Processing reads the cache synchronously and never waits on the network. |

## Acceptance Criteria

> Checkbox convention: an AC whose endpoint depends on a device run or a post-merge action stays `[ ]` (device checks batch to the Epic 1 close-out pass).

- [x] **AC1 — Bundled baseline: per-HUD files + TS registry.** New `apps/mobile/src/features/video-processing/bundledMapConfigs.ts` exports `BUNDLED_MAP_CONFIGS` (`{ v2: <static import of assets/detection/map_config.v2.json> }`), `DEFAULT_HUD_VERSION = "v2"` and `BUNDLED_MAP_CONFIG_REVISION = 1` (integer; bumped by hand whenever a bundled config file changes — header comment says so). The asset stays at `apps/mobile/assets/detection/map_config.v2.json` (NOT the epics' original `assets/map_config.json`), byte-identical to `apps/tooling/output/map_configs/map_config.v2.json` (existing drift guard in `mapConfig.test.ts` stays). Loading a registry entry whose key ≠ its config's normalised `hud_version` throws at the seam.
- [x] **AC2 — `schema_version` work: verified already done, not re-done.** Record evidence in Completion Notes: `contracts/map-config.schema.json` requires `schema_version` `enum [1]`; `map_config_emitter.py:92` writes it first; `apps/tooling/tests/test_map_config_emitter.py:198-279` assert it (present, first, 2 rejected); `packages/contracts/src/generated/map-config.ts` requires it; the bundled file has `schema_version: 1`. The original AC1–AC4 tooling/contract items (`map_config_generator.py`, `hash_comparator.py` — both retired by 9.11; Story 9.1 cancelled) are **closed by 9.9a/9.9c/12.4c**. No schema bump; no `hud_version` enum extension (schema:36's flag is answered: no new HUD exists).
- [x] **AC3 — Overlay contract.** New `contracts/detection-config-envelope.schema.json` (draft 2020-12, `additionalProperties: false` at every level): `envelope_version` (int, `enum [1]`), `revision` (int ≥ 1), `configs` (object, `propertyNames` = the map-config `hud_version` enum, ≥ 1 entry; value `{config_json: string minLength 1, sha256: string ^[0-9a-f]{64}$}`). Added to the generator table (`packages/contracts/scripts/generate-zod.mjs:~82`, export `DetectionConfigEnvelopeSchema`), `src/index.ts`, and `package.json` `exports`. `pnpm --filter @warden/contracts build` regenerates it.
- [x] **AC4 — 🔴 ORDER TRAP closed and tested.** A remote candidate's `rawJson` **is** the envelope entry's `config_json` string, verbatim (after its sha256 and schema checks pass). Config data never travels as a nested Firestore map. Tests: (a) a fixture `config_json` whose `minimap_identification.maps` keys are deliberately **non-alphabetical** yields a candidate whose `rawJson` lists the maps in exactly that order and whose `summariseClassifiers().mapZoneCounts` key order matches; (b) a doc whose config arrives as a nested object (no envelope — what a naive `firestore:set` of the file would produce) is **rejected** and the bundled candidate is used; (c) `JSON.parse(rawJson)` deep-equals `candidate.config`.
- [x] **AC5 — Overlay service `mapConfigOverlay.ts`.** `refreshMapConfigOverlay(): Promise<OverlayRefreshResult>` reads `detection_config/latest` via the RNFB v24 namespaced chain (`firestore().collection("detection_config").doc("latest").get()`), validates the envelope (AC3 Zod), and for **each** `configs` entry independently: sha256 of the UTF-8 text (`expo-crypto` `digestStringAsync(SHA256)`) equals `sha256` → `JSON.parse` → `MapConfigSchema` → key equals normalised `hud_version`. Bad entries are dropped with a logged reason; good ones survive. The surviving envelope is cached in MMKV under `detection.mapConfigOverlay` (stored as the envelope JSON string via `storage.setString`) **only if** `revision > cachedRevision` (equal/lower = no write). Singleflighted (one in-flight promise). **Never throws.**
- [x] **AC6 — The seam, widened; nothing else changes.** `listMapConfigCandidates()` stays **synchronous** and returns, ordered by preference: for each HUD, the cached overlay entry (only if overlay `revision > BUNDLED_MAP_CONFIG_REVISION`) then the bundled entry; never empty. A cached overlay that fails re-validation on read (e.g. contract tightened by an app update) is deleted and ignored. `getPrimaryMapConfig()` returns the first candidate whose `hudVersion === DEFAULT_HUD_VERSION`. Memoised; the memo invalidates when `refreshMapConfigOverlay` writes. **`processingPipeline.ts`, `detectionTimeline.ts`, `engineScoring.ts` and the native module are not modified** (the 12.4c contract: "1.13 changes this function and nothing else" — the new modules feed it). A session keeps the candidate it captured at start; an overlay landing mid-session affects only the next session.
- [x] **AC7 — Read timing: post-auth, non-blocking.** `App.tsx` no longer calls anything detection-config related at mount. A `useEffect` keyed on `useAuthStore` user `uid` calls `void refreshMapConfigOverlay()` when a real user is present; skipped when `AUTH_BYPASS` is on. No `await` of it anywhere on the processing path.
- [x] **AC8 — The first-launch gate is GONE.** Deleted: `OfflineFirstLaunchError`, `OFFLINE_FIRST_LAUNCH_MESSAGE`, `isVideoProcessingBlocked`, `getBootstrapPromise`, `bootstrapDetectionConfig`. `useVideoProcessing.ts` starts processing without any config gate. Legacy MMKV keys `detection.config` and `detection.offlineFirstLaunchBlocked` are deleted once at overlay-module init (idempotent). `rg "OfflineFirstLaunch|offlineFirstLaunchBlocked|bootstrapDetectionConfig|DetectionConfig\b" apps/mobile/src apps/mobile/App.tsx` returns nothing (comments included — update `mapIdentifier.ts:5` and `mapIdentifier.test.ts:4`).
- [x] **AC9 — v1 apparatus deleted.** `detectionConfig.ts`, `detectionConfigService.ts`, `detectionConfigBootstrap.ts` and `__tests__/detectionConfig{,Service,Bootstrap}.test.ts` removed. A v1-shaped document currently at `detection_config/latest` (`version`/`roi_zones`/`thresholds`/`maps`) is rejected as `malformed-envelope` and the bundled config is used — tested.
- [x] **AC10 — Every failure falls back to bundled, labelled correctly, silently to the user.** Table-driven test over: `permission-denied`, `unavailable`/network, document missing, malformed envelope, unknown `envelope_version`, sha256 mismatch, `config_json` not JSON, config fails `MapConfigSchema` (incl. `schema_version: 2`), key ≠ `hud_version`, revision not newer. Each returns a distinct `OverlayRefreshResult.reason`, logs once (`console.warn`, with the Firestore error `code` when there is one), leaves any existing valid cache intact, and produces **no** user-visible error. `MalformedRemoteConfigError`'s intent survives as the `malformed-*` reasons (fallback to bundled, architecture.md:394).
- [x] **AC11 — Tooling: envelope builder (no credentials, no network).** New `apps/tooling/tools/detection_config_envelope.py`: `--configs-dir` (default `apps/mobile/assets/detection` — what ships), `--revision N` (required, ≥ 1), `--out` (default `apps/tooling/output/detection_config/latest.json`, gitignored by the existing `output/*`). For each `map_config.<hud>.json`: validate against `contracts/map-config.schema.json`, require filename HUD == content `hud_version` and HUD ∈ the schema enum (closes the path-traversal concern at deferred-work.md:66-67 for this tool), embed the **file text verbatim** as `config_json`, sha256 over the file bytes. Validate the envelope against AC3's schema before writing. Pytest `apps/tooling/tests/test_detection_config_envelope.py`. A small committed fixture envelope (`apps/mobile/src/features/video-processing/__tests__/fixtures/overlay-envelope.json`, produced by this tool from a tiny non-alphabetical config) is consumed by the mobile tests — the cross-language sha256 parity check.
- [x] **AC12 — Docs and planning artefacts amended (dated "AMENDED 2026-10-xx (Story 1.13)" notes, originals kept).** `_bmad-output/architecture.md`: Decision #2 Implementation (:390-394 — path, bootstrap, "gated by `version`" → envelope `revision`), :400, Brownfield Item 7 (:489-495 → "closed by 9.9c"), tree (:1522, :1582-1584), :1774, data-flow rows :1183/:2029-2030. `docs/architecture-mobile.md`: :15, boot sequence :66, map-config section :147-156, replace the v1 cache section :160-175 with the overlay. `docs/data-models-mobile.md` (:122, :155-168), `docs/component-inventory-mobile.md` (:93-95), `docs/data-models-shared.md` (:38, :91). `epics-and-stories.md`: an amendment block on 1.13 pointing here, and one on **1.16** stating its upload artefact is the AC11 envelope (not the bundled file) and that `firebase firestore:set` is not a Firebase CLI command (1.16 picks the real mechanism). `deferred-work.md`: mark the 12.4d V1-blocker item *code side resolved by 1.13; rules = 1.14/1.15*; re-home 12.4c D2 per D4.
- [x] **AC13 — Gates.** `pnpm --filter @warden/contracts build`; mobile `jest` green and `tsc --noEmit` 0 (record suite/test counts vs the 12.4d baseline **21 suites / 243 passed + 10 todo**; expect −3 v1 suites, + overlay suite(s)); `apps/tooling` pytest green (record before/after); web `tsc` 0 and `vitest` 351/351 (contracts index changed).
- [ ] **AC14 — Device checks (deferred to the Epic 1 close-out pass; stays `[ ]`).** On the Poco X5 Pro: (a) fresh install, airplane mode → video processes with the bundled config; (b) signed in, current (deny-all) rules → `permission-denied` logged, video processes; (c) after 1.15 deploys rules and 1.16 uploads an envelope with `revision 2` → overlay cached, next session's `[map-config] source=remote revision=2` log line. Logged in deferred-work.md; does not block review.
- [x] **AC15 — Scope fence** (see Dev Notes › Scope fences). No edits to `apps/web/firestore.rules` (1.14), no deploy (1.15), no `docs/deployment-guide.md` upload section (1.16), no native/Kotlin change, no HUD pre-pass (D4), no `processingPipeline.ts` change.
- [x] **AC16 — `sprint-status.yaml`:** `1-13-…` `ready-for-dev → in-progress → review` with a reason comment; `last_updated` bumped.

## Tasks / Subtasks

- [x] **T1 Baseline** (AC13): run mobile jest + tsc, tooling pytest, web tsc/vitest; record counts in Debug Log.
- [x] **T2 Contract** (AC3): write the envelope schema; add generator entry + index/exports; build; eyeball the generated Zod (`$defs` inlined — no `z.any()`).
- [x] **T3 Tooling builder** (AC11): `detection_config_envelope.py` + pytest; generate the mobile fixture envelope from a tiny hand-written non-alphabetical config (commit both the tiny config and the envelope under `__tests__/fixtures/`).
- [x] **T4 Registry** (AC1): `bundledMapConfigs.ts`; move the bundled import out of `mapConfig.ts` into it.
- [x] **T5 Overlay service** (AC5, AC8 key cleanup, AC10): `mapConfigOverlay.ts` + `__tests__/mapConfigOverlay.test.ts` (RNFB lazy-thunk mock, `expo-crypto` mocked onto `node:crypto` `createHash('sha256')`).
- [x] **T6 Seam** (AC6, AC4): widen `listMapConfigCandidates()`/`getPrimaryMapConfig()`; candidate `source: "bundled" | "remote"` gains `revision`; extend `mapConfig.test.ts` with the order-trap and fallback cases.
- [x] **T7 Retire v1 + gate** (AC8, AC9, AC7): delete the 3 modules + 3 suites; strip the gate from `useVideoProcessing.ts`; replace `App.tsx:23,42` with the post-auth effect.
- [x] **T8 Docs/planning** (AC12).
- [x] **T9 Gates + deferred log** (AC13, AC14): re-run everything; log AC14 in deferred-work.md; sprint-status flip (AC16).

### Review Findings

Code review 2026-10-04 (/bmad-code-review, claude-opus-5-5): Blind Hunter, Edge Case Hunter and Acceptance Auditor, run over the uncommitted working tree on `main` (HEAD `fbc088e`). **2 decision-needed (RESOLVED by Stephane 2026-10-04: D1 → (b), D2 → (a); both applied) · 10 patch (applied) · 9 defer (+1 follow-up from D2(b)) · 13 dismissed.**

The 7 points the dev agent flagged:
- **Cache split:** `mapConfigOverlayCache.ts` is sound. The seam is still the only consumer path. Only App.tsx imports the Firebase-bearing module.
- **Explicit `v1`/`v2` properties:** OK as a mechanism, but see D1 for the forward-compat consequence.
- **No re-hash on read:** OK. MMKV is app-private, and the JSON and both contracts are re-validated on read.
- **AC8 grep residue:** forced by AC8 itself.
- **ORDER TRAP:** verified closed. Remote `rawJson` is `config_json` verbatim through Zod, MMKV `setString` and `remoteCandidates`. It is never re-serialised and never stored as a Firestore map. Native `orderedMapNames` tolerates CRLF and whitespace.
- **Auth timing:** verified. The read runs only once `uid` is set, is skipped under `AUTH_BYPASS`, is called with `void`, never rejects and is never awaited by processing.
- **CRLF:** already logged for 1.16.

- [x] [Review][Decision] **D1 — RESOLVED (Stephane, 2026-10-04): option (b), tolerate unknown HUD keys.** The problem: `configs` was `.strict()`, so an envelope carrying a future HUD key would have been rejected whole by every installed app. What changed:
  - `contracts/detection-config-envelope.schema.json`: `configs.additionalProperties` is now `{$ref ConfigEntry}`. The known `v1`/`v2` stay explicit and strict, and an unknown key passes only if its value is a well-formed entry. The regenerated Zod uses `.catchall(ConfigEntry)`.
  - `mapConfigOverlay.ts` drops each unknown key on its own as `unknown-hud` (`KNOWN_HUD_VERSIONS` comes from `MapConfigSchema.shape.hud_version.options`). `mapConfig.ts` `remoteCandidates` skips unknown keys rather than discarding the cache.
  - Tests: {v2, v3} delivers the v2 update to a v2-only app; an unknown key with a malformed entry still fails the envelope; a known entry with a bad sha256 format still fails; {v3} alone gives `malformed-entry/unknown-hud`; an unknown key in the cache is skipped. In pytest, the contract-agreement test now pins `additionalProperties == {$ref ConfigEntry}`, plus 2 envelope-validation tests.
  - The builder needed no change: it still emits only enum HUDs.
  - The 1.16 amendment (epics) and the overlay section of `docs/architecture-mobile.md` say so.
- [x] [Review][Decision] **D2 — RESOLVED (Stephane, 2026-10-04): option (a) now; option (b) logged as a follow-up.** New `apps/mobile/src/features/video-processing/mapConfigNativePreconditions.ts` mirrors every `require`/`throw` in `apps/mobile/plugins/kotlin/WardenRulePacker.kt`, citing file:line:
  - `orderedMapNames`, ported 1:1 (:267-316): a `"minimap_identification"` literal, a `"maps"` literal after it, only one such literal, a `{`, and a terminated object.
  - The scanned names must equal `Object.keys(maps)` in the same order. This covers a duplicated slug and an escaped key, which make `getJSONObject(name)` throw or the rule count drift (:241-246).
  - `MAX_RULES = 150` (:21, :335-338).
  - `MAX_RECT_TEXELS = 4096` after `clampRect` against `reference_resolution` (:30, :199-205, :350-361; frame = `WardenSessionAnalyzer.kt:74-81`).

  Where it runs: in `checkEntry` (a failure is dropped at receive time as `native-invalid`, logged once, and the bundle stays) and in `remoteCandidates` (a failing cached config is discarded on read). The new suite `__tests__/mapConfigNativePreconditions.test.ts` has 11 tests, one per precondition plus the accept side: the bundled config, the fixture under CRLF and LF, and an off-frame zone whose clamped area is under the cap. Overlay and seam tests were added too. No Kotlin change. Option (b), the pipeline-level fallback, is logged in deferred-work.md as a follow-up story, because AC6/AC15 fence off `processingPipeline.ts`.
- [x] [Review][Patch] An error with no `code` was mapped to `unavailable` (offline), which hid bugs. It now maps to `error`. [mapConfigOverlay.ts `reasonForFirestoreError`]
- [x] [Review][Patch] AC10: `unknown envelope_version` and `malformed envelope` gave identical results, and the distinctness test only checked its own table (its comment was also wrong). Added `envelopeProblem`. The test now derives the discriminators from what the code returns, and all of them (13 rows after D1/D2) must differ. [mapConfigOverlay.ts; __tests__/mapConfigOverlay.test.ts]
- [x] [Review][Patch] `mockCollection`/`mockDoc` were not cleared, so the call assertions could be vacuous. [__tests__/mapConfigOverlay.test.ts beforeEach]
- [x] [Review][Patch] The `jest.doMock` override leaked when an assertion threw. Wrapped in try/finally. [__tests__/mapConfig.test.ts]
- [x] [Review][Patch] Builder: an unreadable config path (e.g. a directory) produced a traceback instead of exit 1. [detection_config_envelope.py `_entry_for_file`; +test]
- [x] [Review][Patch] Builder: the write to `--out` was not atomic, so it could leave a truncated `latest.json`. Now writes a temp file and calls `os.replace`. [detection_config_envelope.py `write_envelope`; +test]
- [x] [Review][Patch] Builder: duplicate object keys (silently last-wins) and NaN/Infinity were accepted. Both are now refused. [detection_config_envelope.py; +2 tests]
- [x] [Review][Patch] Builder: a missing or malformed schema produced a traceback instead of `EnvelopeBuildError`. [detection_config_envelope.py `_load_schema`; +test]
- [x] [Review][Patch] Stale doc references to the deleted v1 modules. [docs/architecture-mobile.md storage table + test-atoms row; docs/integration-architecture.md row 8 + flow-section amendment; _bmad-output/architecture.md `cross-MAP-CONFIG-DELIVERY-001` list]
- [x] [Review][Patch] AC16: the `last_updated:` field still described the create-story flip. [_bmad-output/sprint-status.yaml]
- [x] [Review][Defer] A partly-bad newer revision replaces the whole cache, which loses a good older entry for the HUD whose new entry was dropped. [mapConfigOverlay.ts doRefresh] Deferred: unreachable with one HUD. Home: the first story that bundles a second HUD.
- [x] [Review][Defer] On read, one cached entry failing re-validation discards the whole overlay, while the write path drops per HUD. [mapConfig.ts remoteCandidates] Deferred, same home.
- [x] [Review][Defer] The overlay-only HUD branch is untested. [mapConfig.ts listMapConfigCandidates] Deferred, same home.
- [x] [Review][Defer] Only one refresh runs per `uid` change. Nothing retries on reconnect, foreground or backoff. [App.tsx] Deferred: harmless under the non-blocking contract. Revisit after 1.14/1.15.
- [x] [Review][Defer] The persisted `uid` may rehydrate before native auth restores the session, so a first-read deny would not be retried that launch. [App.tsx; useAuthStore] Deferred to the AC14(c) device check. If it shows up, key the effect on auth-ready.
- [x] [Review][Defer] The `BUNDLED_MAP_CONFIG_REVISION` bump is guarded only by a comment. [bundledMapConfigs.ts] Deferred. Planned guard: a sha-pinning test. Home: the next story that changes a bundled config (9.9b).
- [x] [Review][Defer] The builder accepts a `--revision` at or below the bundled revision. [detection_config_envelope.py] Deferred to 1.16.
- [x] [Review][Defer] sha256 parity is proven only for ASCII text. [__tests__/mapConfigOverlay.test.ts] Deferred to the AC14 device pass.
- [x] [Review][Defer] A session's overlay revision is only logged, not persisted. [mapConfig.ts getPrimaryMapConfig] Deferred. Home: Epic 5/6 session-detail work.

## Dev Notes

### Current state of every file this story touches (read before editing)

- **`mapConfig.ts` (the seam, 12.4c).** `listMapConfigCandidates()` memoises one bundled candidate (`parseCandidate(bundledV2,"bundled",…)`, `rawJson = JSON.stringify(raw)`); `getPrimaryMapConfig()` takes `[0]`; `MalformedMapConfigError` thrown on contract failure (keep — a broken *bundled* config is a broken build and must stay loud); `summariseClassifiers` relies on `Object.entries` insertion order; `assertRefsMatchConfig` checks texel order; `resolveSessionHudVersion` is post-hoc, single-candidate. **Preserve:** all exported signatures used by `processingPipeline.ts:69-72,341-342,393` and `detectionTimeline.ts:39,170`; `__resetMapConfigCacheForTests` (extend it to reset the overlay memo).
- **`detectionConfigService.ts` (245 lines, v1)** — read `detection_config/latest`, MMKV `detection.config` as `setObject`, three singleflights, version-gated SWR, maps all non-malformed failures to `OfflineFirstLaunchError` (the mislabel). **Reuse the patterns, delete the file.**
- **`detectionConfigBootstrap.ts` (91)** — writes/clears `detection.offlineFirstLaunchBlocked`; `getBootstrapPromise` exists only for the TOCTOU guard in the hook. **Delete.**
- **`useVideoProcessing.ts:52-67`** — awaits bootstrap, reads `isVideoProcessingBlocked()`, sets error. **Remove that block only;** the checkpoint/`runProcessingPipeline` flow below stays byte-identical.
- **`App.tsx:23,42`** — import + mount-time call. AUTH_BYPASS branch sets a fake user (`uid: "dev-bypass-user"`) — the post-auth effect must check `AUTH_BYPASS`, not just `uid`, or the bypass user will trigger a doomed read.
- **`shared/services/storage`** — MMKV v3 wrapper: `getString/setString/getObject/setObject/delete`. Use `setString` for the envelope (it already *is* JSON text; avoid re-stringifying).

### 🔴 The order trap, precisely

`org.json.JSONObject` is a HashMap, so `WardenRulePacker.orderedMapNames` scans the raw JSON text to recover `minimap_identification.maps` order; that order is every map rule's texel index. JS objects preserve insertion order for **non-integer-like** string keys — slugs match `^[a-z][a-z0-9_]*$` (schema), so `JSON.parse`/`JSON.stringify` are order-safe here, but Firestore maps are not (keys come back sorted). Hence: config as a **string field**, `rawJson = config_json` verbatim. Do not "normalise" the text (no re-stringify for remote) — the sha256 is over those exact bytes. A nested-object payload must be rejected, never accepted-and-reordered.

### Envelope (the document 1.16 will document)

```json
{
  "envelope_version": 1,
  "revision": 2,
  "configs": {
    "v2": { "config_json": "{\n  \"schema_version\": 1, …}\n", "sha256": "<64 hex>" }
  }
}
```
- `revision` must exceed `BUNDLED_MAP_CONFIG_REVISION` to win — otherwise an app update shipping a newer bundle would be overridden by an older cached overlay. Operator rule (for 1.16): next revision = max(current Firestore revision, shipped bundled revision) + 1.
- Size: bundled v2 is 62,476 bytes; Firestore's 1 MiB doc limit leaves room for ~15 HUD configs. Note it in the schema description.
- `schema_version` "migration": there is only shape 1. An entry with `schema_version` ≠ 1 fails `MapConfigSchema` and is dropped (AC10) — that IS the forward-compat behaviour for old apps meeting a future shape. Write no migration code until a shape 2 exists.

### Failure → behaviour table (AC10)

| Condition | reason | Cache | Session uses |
|---|---|---|---|
| no signed-in user | (not called) | unchanged | cache/bundled |
| `firestore/permission-denied` (today, until 1.15) | `permission-denied` | unchanged | cache/bundled |
| `firestore/unavailable` / offline | `unavailable` | unchanged | cache/bundled |
| doc missing | `not-found` | unchanged | cache/bundled |
| envelope fails Zod (incl. v1 doc, nested-object config) | `malformed-envelope` | unchanged | cache/bundled |
| entry sha mismatch / not JSON / fails schema / key≠hud | `malformed-entry` (per entry) | other entries kept | per-HUD fallback |
| `revision ≤ cached` | `not-newer` | unchanged | cache/bundled |
| success | `updated` | written | remote (next session) |

### Scope fences

- **1.14** — `firestore.rules` `detection_config/{docId}` signed-in read. Until 1.14+1.15 land, every overlay read is `permission-denied` → bundled. That is correct and is exactly why this story unblocks V1 on its own.
- **1.15** — production deploy + smoke test (its "signed-in client can read `detection_config/latest`" check now means "reads an envelope").
- **1.16** — operator upload procedure in `docs/deployment-guide.md`. Its current command (`firebase firestore:set detection_config/latest apps/mobile/assets/map_config.json`, epics:1118-1123, architecture.md:439-440) is wrong twice: wrong artefact (must be the AC11 envelope) and, to our knowledge, not a Firebase CLI command. 1.13 only adds the amendment pointer (AC12).
- **D4 / HUD pre-pass** — not here (see Kickoff D4).
- **Deferred, untouched:** `assertRefsMatchConfig` kind/class-only (deferred-work.md:305); `manifest.template.json` hardcoding `v2` (:147); emitter silent overwrite (:66-67, except this new tool's own filename guard); rules/project binding (:30).
- **Reader-App invariant:** no monetization surface; the overlay read needs auth, not `isPaid`.

### Testing standards

- Jest (`jest-expo` preset). RNFB mock = the lazy-thunk `jest.mock("@react-native-firebase/firestore", …)` pattern from the deleted `detectionConfigService.test.ts:11-29` (copy it before deleting; HOIST NOTE explains why the thunk is required). Firestore errors: reject with `Object.assign(new Error("…"), { code: "firestore/permission-denied" })`.
- `expo-crypto` is a dependency (used by `sessionRepository.ts`/`segmentRepository.ts` for `randomUUID` only); `digestStringAsync` needs an explicit jest mock backed by `node:crypto`.
- Tooling: `cd apps/tooling && uv run pytest`.
- No device test in this story's gate (AC14 batches to epic end).

### Previous-story intelligence (12.4c / 12.4d)

- 12.4c fixed `generate-zod.mjs` to inline `$defs` — keep the new schema `$ref`-free or local-`$ref`-only; remote refs throw by design.
- 12.4c review established `rawJson` as the single carrier of order and added the reparse-equals test (`mapConfig.test.ts:82-96, 250-254`) — extend, don't replace.
- The `mapConfig.test.ts` drift guard passes vacuously when the gitignored tooling output is absent (deferred-work.md:305) — not this story's to fix, but don't rely on it as AC1 evidence; compare bytes explicitly if the output exists.
- 12.4d bypassed the gate locally (`__DEV__ && EXPO_PUBLIC_AUTH_BYPASS`, reverted, never committed) — there is nothing to revert in the tree.
- Recent commits: `5ee936c` (12.4d close), `d96b91e` (12.4c review hardening), `03fe9ca` (12.4c wiring — introduced the bundled asset and the seam). Conventions: work on `main`, commitlint lowercase subject, e.g. `feat(mobile): deliver the map config as bundle plus post-auth overlay (story 1.13)`.

### Project Structure Notes

- New: `contracts/detection-config-envelope.schema.json`, `packages/contracts/src/generated/detection-config-envelope.ts` (generated), `apps/mobile/src/features/video-processing/{bundledMapConfigs,mapConfigOverlay}.ts`, `__tests__/mapConfigOverlay.test.ts`, `__tests__/fixtures/overlay-envelope.json` (+ its tiny source config), `apps/tooling/tools/detection_config_envelope.py`, `apps/tooling/tests/test_detection_config_envelope.py`.
- Variance from architecture: the architecture's `apps/mobile/assets/map_config.json` (single file, :390, :1111, :1522) is superseded by `assets/detection/map_config.<hud>.json` (12.4c) — AC12 amends it.

### References

- Epic/story: `_bmad-output/epics-and-stories.md:1023-1050` (1.13), `:1052-1130` (1.14–1.16).
- Architecture: Decision #2 `architecture.md:377-400`; #7 `:533-586`; #8 `:424-449`; Brownfield Item 7 `:487-495`; naming `:1023-1025`; seam `:1774`.
- SCP-2026-05-15 `:376` (manifest recommendation); SCP-2026-07-16 (one-pass fork resolution).
- Code: `apps/mobile/src/features/video-processing/mapConfig.ts` (header = 12.4c's seam contract), `detectionConfigService.ts`, `detectionConfigBootstrap.ts`, `useVideoProcessing.ts:52-67`, `App.tsx:23,42`; `apps/tooling/tools/map_config_emitter.py:83-95,144`; `contracts/map-config.schema.json`.
- Evidence: `deferred-work.md:305,309,315`; `apps/mobile/bench/12-4d/REPORT.md` §7; 12.4c story AC0c/AC5/D2 (`12-4c-…md:75,88,144`).

## Dev Agent Record

### Agent Model Used

claude-opus-5-5 (/bmad-dev-story 1.13, Amelia), 2026-10-04.

### Kickoff decisions — Stephane's answers to the create-story open questions (2026-10-04, verbatim)

1. Delete the v1 detection-config modules (detectionConfig.ts, detectionConfigService.ts, detectionConfigBootstrap.ts + their 3 suites) outright — YES.
2. One Firestore document `detection_config/latest` holding a `configs` map keyed by HUD version — YES.
3. Keep the sha256 integrity field (expo-crypto) — YES.
4. Story 1.16's upload mechanism: a firebase-admin Node script run with the operator's own credentials, or a Console paste. `firebase firestore:set` is not a real CLI command — note it for 1.16 (amendment note in the epics file), do not build the uploader in 1.13; 1.13 ships only the credential-free envelope builder.
5. Overlay read requires sign-in only (not a paid subscription), matching the rules.
6. Leave whatever v1 document is in production `latest`; new builds ignore the v1 shape, 1.16's upload overwrites it.
7. Real HUD-version selection before analyzeSession → the first story that bundles a second HUD config (record in deferred-work.md).

### Debug Log References

- **T1 baseline (before any change):** contracts build OK; mobile jest **21 suites / 243 passed + 10 todo**; mobile `tsc --noEmit` 0; tooling pytest **305 passed**; web `tsc --noEmit` 0; web vitest **43 files / 351 passed**.
- **After:** contracts build OK (3 schemas generated); mobile jest **19 suites / 252 passed + 10 todo** (−3 v1 suites / −28 v1 tests; +1 suite `mapConfigOverlay.test.ts` 26 tests; `mapConfig.test.ts` 17 → 28 tests); mobile tsc 0; tooling pytest **326 passed** (+21, `test_detection_config_envelope.py`); web tsc 0; web vitest **351/351** (first run, no cold-start timeout); `@warden/contracts` typecheck 0.
- First jest run after wiring the seam: 3 suites failed to load with *"Native module RNFBAppModule not found"* — `mapConfig.ts` imported the overlay module, which imports `@react-native-firebase/firestore`, so every consumer of the seam (pipeline, timeline) pulled Firebase in. Fixed by splitting the MMKV cache into `mapConfigOverlayCache.ts` (see deviations). A second failure: `processingPipeline.test.ts`'s hoisted storage mock was not yet initialised when a module-init side effect (legacy-key cleanup) ran — moved that cleanup into `mapConfigOverlay.ts`, which only App.tsx imports.
- AC1 byte-identity: `cmp apps/tooling/output/map_configs/map_config.v2.json apps/mobile/assets/detection/map_config.v2.json` → identical (output present on this machine, so the drift guard ran non-vacuously); the asset is unchanged vs HEAD.
- AC8 grep `rg "OfflineFirstLaunch|offlineFirstLaunchBlocked|bootstrapDetectionConfig|DetectionConfig\b" apps/mobile/src apps/mobile/App.tsx` → only hits are the legacy key name `detection.offlineFirstLaunchBlocked` in `mapConfigOverlay.ts`'s deletion list and its test (see deviations).

### Completion Notes List

- Create-story 2026-10-04: ultimate context engine analysis completed — comprehensive developer guide created. Kickoff decisions D1–D5 taken at create-story; open questions returned to Stephane.
- **AC2 evidence (schema_version already done, not re-done):** `contracts/map-config.schema.json` requires `schema_version` `{"type":"integer","enum":[1]}` (in `required`); `map_config_emitter.py` `_assemble_output` writes `"schema_version": 1` as the first key; `test_map_config_emitter.py` asserts presence + first-key order (`test_output_has_seven_required_keys_with_schema_version_first`) and rejects missing / `2` (`test_missing_schema_version_rejected`, `test_schema_version_2_rejected`); the generated `packages/contracts/src/generated/map-config.ts` requires it; the bundled file opens with `"schema_version": 1` (`mapConfig.test.ts` asserts it). No schema bump, no `hud_version` enum extension.
- **Contract (AC3):** `contracts/detection-config-envelope.schema.json`, generated as `DetectionConfigEnvelopeSchema` (no `z.any()`; `$defs` inlined; every level `.strict()`).
- **Builder (AC11):** `detection_config_envelope.py` — per file: filename HUD ∈ enum, UTF-8 without BOM, JSON, map-config schema, content `hud_version` == filename HUD; `config_json` = file text verbatim, `sha256` over the bytes; envelope validated before writing; atomic refusal (exit 1, nothing written). The committed fixture `__tests__/fixtures/overlay-envelope.json` (revision 2) was produced by the tool from `__tests__/fixtures/overlay-source/map_config.v2.json` (maps `zeta_map, alpha_map, mu_map`); the mobile suite re-hashes it with node's SHA-256 — the cross-language parity check.
- **Registry (AC1):** `bundledMapConfigs.ts` (`BUNDLED_MAP_CONFIGS = {v2}`, `DEFAULT_HUD_VERSION = "v2"`, `BUNDLED_MAP_CONFIG_REVISION = 1`, header says bump by hand); the static import moved out of `mapConfig.ts`; a key ≠ normalised `hud_version` throws `MalformedMapConfigError` at the seam (tested with `jest.doMock`).
- **Overlay (AC5/AC10):** `refreshMapConfigOverlay()` — RNFB namespaced read, envelope Zod, per-entry sha256 → JSON → `MapConfigSchema` → key == `hud_version`; caches only when `revision > max(cached, BUNDLED_MAP_CONFIG_REVISION)`; singleflighted; never throws (a sync throw from `firestore()` itself resolves as `error`). Reasons: `updated | permission-denied | unavailable | not-found | error | malformed-envelope | malformed-entry | not-newer`, plus per-entry `droppedEntries[].problem` (`sha256-mismatch | not-json | schema-invalid | hud-mismatch`) and the Firestore `code`. Table-driven test over all 10 AC10 conditions (+ a coded/uncoded network split): one `console.warn` each (with the code when there is one), existing cache byte-identical afterwards, session still on the cached remote config.
- **Seam (AC4/AC6):** `listMapConfigCandidates()` stays sync, per HUD: overlay entry (only if revision > bundled) then bundled; memo keyed on the cache generation; a cached overlay failing re-validation (contract, nested-object entry, non-JSON) is deleted and ignored. Remote `rawJson` = `config_json` verbatim; candidates gained `revision`. `getPrimaryMapConfig()` returns the first `DEFAULT_HUD_VERSION` candidate and logs `[map-config] source=… revision=… hud=…` (the AC14c line). `processingPipeline.ts`, `detectionTimeline.ts`, `engineScoring.ts`, native code: untouched. The pipeline captures the candidate once at session start, so a mid-session overlay only affects the next session (tested).
- **Gate + timing (AC7/AC8/AC9):** v1 modules + suites deleted; `useVideoProcessing.ts` gate block removed (rest byte-identical); `App.tsx` mount-time call replaced by an effect on `useAuthStore` `uid`, skipped under `AUTH_BYPASS`; legacy MMKV keys deleted at `mapConfigOverlay.ts` init (tested in an isolated module registry). The v1 production document shape is rejected as `malformed-envelope` (tested).
- **Docs (AC12):** dated "AMENDED 2026-10-04 (Story 1.13)" notes in `architecture.md` (Decision #2 implementation, Decision #7 bullet, :400 docs bullet, Decision #8 upload command, Brownfield Item 7, data-flow row, tree ×2, seam line :1774, integration rows 8 + 10); `docs/architecture-mobile.md` (stack, boot sequence, map-config section, v1 cache section replaced by the overlay with its failure table); `docs/data-models-mobile.md`, `docs/component-inventory-mobile.md`, `docs/data-models-shared.md` (prettier-formatted); `epics-and-stories.md` amendment blocks on 1.13 and 1.16 (envelope artefact; `firebase firestore:set` not a CLI command; firebase-admin script or Console paste per Stephane #4); `deferred-work.md` — 12.4d V1-blocker item marked code-side resolved (rules = 1.14/1.15), 12.4c D2 re-homed, new "Deferred BY Story 1.13" section.
- **AC14** left `[ ]` — logged in deferred-work.md for the Epic 1 close-out pass.
- **Not committed** (per instruction): everything is in the working tree; the v1 deletions are unstaged.

#### Deviations from the story text (for the code review)

1. **Extra module `mapConfigOverlayCache.ts`.** The story names one overlay module. The MMKV cache (read/write/discard, memo, generation counter) is split out so the synchronous seam reads it **without importing Firebase** — otherwise every consumer of `mapConfig.ts` (pipeline, timeline and their suites) loads `@react-native-firebase`, which fails in jest and contradicts "the seam never touches the network". `mapConfigOverlay.ts` holds the refresh and the AC8 legacy-key cleanup.
2. **Envelope `configs` key constraint:** explicit `properties: {v1, v2}` + `additionalProperties: false` + `minProperties: 1` instead of `propertyNames`. `json-schema-to-zod` 2.8.1 ignores `propertyNames` and `minProperties`; explicit properties make the generated Zod enforce the key set. A pytest asserts the key set equals the map-config `hud_version` enum; `minProperties` (enforced by Python `jsonschema`) is re-checked in TS (empty `configs` → `malformed-envelope`).
3. **Not-newer floor** is `max(cachedRevision, BUNDLED_MAP_CONFIG_REVISION)`, not just `cachedRevision` — an overlay the seam would ignore anyway is not written.
4. **AC10 "distinct reason":** the story's own failure table maps four entry failures to `malformed-entry` and unknown `envelope_version` to `malformed-envelope`; distinctness is carried by `droppedEntries[].problem` and `code`. Added an `error` reason for Firestore codes outside the table; errors without a code count as `unavailable`.
5. **AC8's literal grep** cannot return nothing while AC8 also requires deleting `detection.offlineFirstLaunchBlocked`: that key name remains in the deletion list and its test. Every other pattern returns nothing.
6. **Remote entries are not re-hashed on the sync read path** (it would need an async digest); the sha256 is verified when the overlay is written, and the read path re-validates JSON + both contracts.
7. **Line endings:** `config_json` is the file text exactly as checked out; on this Windows `autocrlf` checkout the bundled file is CRLF, so a locally built envelope carries `\r\n`. Harmless (sha is over the same text); logged for 1.16.

### File List

New:
- `contracts/detection-config-envelope.schema.json`
- `apps/mobile/src/features/video-processing/bundledMapConfigs.ts`
- `apps/mobile/src/features/video-processing/mapConfigOverlay.ts`
- `apps/mobile/src/features/video-processing/mapConfigOverlayCache.ts`
- `apps/mobile/src/features/video-processing/__tests__/mapConfigOverlay.test.ts`
- `apps/mobile/src/features/video-processing/__tests__/fixtures/overlay-envelope.json`
- `apps/mobile/src/features/video-processing/__tests__/fixtures/overlay-source/map_config.v2.json`
- `apps/tooling/tools/detection_config_envelope.py`
- `apps/tooling/tests/test_detection_config_envelope.py`
- (generated, gitignored) `packages/contracts/src/generated/detection-config-envelope.ts`

Modified:
- `packages/contracts/scripts/generate-zod.mjs`, `packages/contracts/src/index.ts`, `packages/contracts/package.json`
- `apps/mobile/App.tsx`
- `apps/mobile/src/features/video-processing/mapConfig.ts`
- `apps/mobile/src/features/video-processing/useVideoProcessing.ts`
- `apps/mobile/src/features/video-processing/mapIdentifier.ts` (comment)
- `apps/mobile/src/features/video-processing/__tests__/mapConfig.test.ts`
- `apps/mobile/src/features/video-processing/__tests__/mapIdentifier.test.ts` (comment)
- `apps/mobile/src/features/auth/__tests__/authService.test.ts`, `apps/mobile/src/features/auth/__tests__/subscriptionService.test.ts` (comments pointing at the deleted v1 suite)
- `_bmad-output/architecture.md`, `_bmad-output/epics-and-stories.md`, `_bmad-output/implementation-artifacts/deferred-work.md`, `_bmad-output/sprint-status.yaml`
- `docs/architecture-mobile.md`, `docs/data-models-mobile.md`, `docs/component-inventory-mobile.md`, `docs/data-models-shared.md`
- `_bmad-output/implementation-artifacts/1-13-hybrid-map-config-delivery-schema-version-1.md` (this file)

Deleted:
- `apps/mobile/src/features/video-processing/detectionConfig.ts`
- `apps/mobile/src/features/video-processing/detectionConfigService.ts`
- `apps/mobile/src/features/video-processing/detectionConfigBootstrap.ts`
- `apps/mobile/src/features/video-processing/__tests__/detectionConfig.test.ts`
- `apps/mobile/src/features/video-processing/__tests__/detectionConfigService.test.ts`
- `apps/mobile/src/features/video-processing/__tests__/detectionConfigBootstrap.test.ts`

### Change Log

- 2026-10-04 — Story created (create-story), `ready-for-dev`.
- 2026-10-04 — Implemented (dev-story): bundled per-HUD registry + post-auth Firestore overlay envelope (contract, Zod, Python builder, mobile service + cache, widened seam); v1 detection-config apparatus and the first-launch gate deleted; docs/planning amended; AC14 deferred to the Epic 1 close-out. Status → `review`. Not committed.
- 2026-10-04 — Code review (/bmad-code-review): 10 patches applied, 9 deferred (deferred-work.md), 13 dismissed; 2 decisions returned to Stephane. Gates after patches: contracts build OK; mobile jest 19 suites / 252 passed + 10 todo; mobile tsc 0; tooling pytest 331 (+5); web tsc 0; web vitest 351/351. Not committed.
- 2026-10-04 — Review decisions applied (Stephane): D1 → (b) the envelope tolerates unknown HUD keys, each dropped as `unknown-hud`; D2 → (a) native packer preconditions mirrored in TS (`mapConfigNativePreconditions.ts`), with a failure dropped as `native-invalid`; D2(b) deferred as a follow-up story. Final gates: contracts build OK; mobile jest **20 suites / 270 passed + 10 todo**; mobile tsc 0; tooling pytest **333**; web tsc 0; web vitest 351/351. Zero open decisions → status `review → done`. Not committed.
