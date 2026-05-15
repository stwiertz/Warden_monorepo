# Story 9.9a: Schema v2 Evolution + map_config_generator v2 Emit

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Scope Adjustment #3 (2026-05-15, post-merge correct-course): SUPERSEDED by Story 9.9c

Post-merge correct-course (`/bmad-correct-course`, deliverable [`_bmad-output/sprint-change-proposal-2026-05-15.md`](../sprint-change-proposal-2026-05-15.md)) determined that 9.9a's `oneOf` v1/v2 schema design and the dual-emit-path in `map_config_emitter.py` are over-engineered for a pre-production project with zero deployed consumers. **New Story 9.9c** unifies the schema to a single shape:

- Top-level required: `schema_version: integer enum [1]` (config-shape version, not detection-method version), `reference_resolution`, `hud_version: string enum`, `score_screen_duration_ms: integer >= 0` (timing offset for score-screen extraction after `in_match` ends), `hud_version_detection: Zone[]`, `in_match_detection: Zone[]` (binary in-match-or-not — no 4-class `{lobby, in_match, score, transition}` cascade; score-screen is timing-derived; lobby/transition not differentiated), `minimap_identification: {id, identification_threshold, roi, maps: {<slug>: {zones: Zone[]}}}`.
- One `Zone` shape via `$defs`: `{id, x, y, width, height, hsv, min_ratio, weight, weight_override}`.
- `additionalProperties: false` at every level.
- No `oneOf`. No discriminated union. Zod regenerates as a single object type.
- `map_config_emitter.py` retargeted: single emit path (no `_detect_schema_version`, no `_build_v2_output` branch, no v1-coercion logic).
- `jsonschema` strict-validation gate preserved end-to-end (same `_validate_against_schema` mechanism, new target schema).

**This story's status:** stays `review` until the standard Two-PR follow-up flips it `done` — independent of 9.9c. The merged work is real history: `schema_version` field exists, `map_config_emitter.py` exists in the renamed-from-`map_config_generator.py` form, `jsonschema` validation gate works. 9.9c rewrites the schema and the emitter on top of that baseline; it does not retroactively rewrite this story.

**Cross-references:**
- New Story 9.9c entry: [`_bmad-output/epics-and-stories.md`](../epics-and-stories.md) (Epic 9 — Tooling section, after Story 9.10).
- Sprint-status diff: `9-9a` (this story) — SUPERSEDED note; `9-1` + `9-4` flip backlog → cancelled (rationales updated); `9-9b` renamed + mechanism rewrite; `9-10` scope-expanded; `9-9c` + `9-11` + `9-12` + `9-13` + `9-14` added as `backlog`; `1-13` AC-amendment note (anchor flips 9.9a → 9.9c). See [`_bmad-output/sprint-status.yaml`](../sprint-status.yaml).

---

## Scope Adjustment (2026-05-15, dev-story prep)

Pre-implementation survey under `/bmad-dev-story` surfaced three premise mismatches between the story spec (written at create-story time) and the current repo state. User-approved scope adjustments:

1. **`apps/mobile/assets/map_config.json` does not exist today.** Story 1.13 (Hybrid map_config.json Delivery) is `backlog` — it is the natural owner of "create the bundled asset for the first time." 9.9a's AC8 ("Bundled map_config.json regenerated with `schema_version: 1`") and Task 7 ("Bundled-asset regeneration") are **DROPPED** from 9.9a's scope and folded forward into Story 1.13's responsibility. Story 1.13 will produce the first bundled asset already-correct (`schema_version: 1` baked in), leveraging the v1 emit path 9.9a delivers. **AC10's bundled-asset golden-snapshot bullet** is dropped along with AC8.
2. **No app currently imports `MapConfigSchema` from `@warden/contracts`.** `apps/mobile/src/features/video-processing/mapIdentifier.ts:48`'s `Object.entries(config.maps)` runs against the handwritten `DetectionConfig` type in `detectionConfig.ts` (Firestore-driven), NOT against `MapConfigSchema`. The discriminated-union narrowing audit in AC11 has no live consumer to audit. **AC11 demoted to a typecheck-only gate**: run `pnpm --filter web typecheck` + `pnpm --filter mobile typecheck` after Zod regen + assert both pass. No `mapIdentifier.ts`/`detectionConfig.ts` narrowing edits are required because neither file imports `MapConfigSchema`.
3. **AC2 reframed.** The original AC2 worried about "pre-existing v1 `map_config.json` files on disk lacking `schema_version`" — there are none in the repo. Reframed: the schema now requires `schema_version` on every emit (still true), so any future on-disk file lacking it would be invalid by the schema; the "regen the bundled asset" closure is shifted to Story 1.13.

All other ACs (AC1 schema v2, AC3 detection helper, AC4 v1 emit + `schema_version: 1` [absorbs 9.1], AC5 v2 emit, AC6 hash_comparator v1-only + v2-refusal, AC7 jsonschema validation gate [absorbs 9.4], AC9 Zod regen, AC10 pytest minus the bundled-asset bullet, AC12 no new deps, AC13/AC14 sprint-status + PR mechanics) are unchanged. AC8 and AC10's bundled-snapshot bullet flip to `[~]` (deferred-to-Story-1.13) rather than `[x]` so the carry-forward is explicit; the AC text itself is kept (struck through) for traceability.

## Scope Adjustment #2 (2026-05-15, mid-review redirect)

After landing the initial implementation, Stephane clarified: **pHash was never a working production method** — it was a research thread that lost to ROI+HSV. ROI+HSV is the single shipped detection approach, and it worked on **both** HUD V1 and HUD V2 (just with different config shapes). The original 9.9a framing of "v1 = pHash, v2 = ROI+HSV" was incorrect; the correct framing is "v1 = legacy ROI+HSV shape (HUD V1 era — `minimap_identification.configs[0]` wrapper, with `weight`/`weight_override`/`identification_threshold`), v2 = Tool 8 flat ROI+HSV shape (HUD V2 era — `game_state_zones` cascade + per-map `ZoneSpec[]`)". User-approved redirects:

1. **Drop pHash entirely.** `apps/tooling/tools/hash_comparator.py` is **deleted** (~900 LOC); the pHash codepaths in `map_config_generator.py` (frame loading, hashing, collision detection, patch mode, `--images`/`--video`/`--preview` CLI flags) are **stripped**. What remains is **renamed** to `apps/tooling/tools/map_config_emitter.py` — a config-driven emitter that reads `config.yaml` → writes `map_config.json` (v1 or v2) with no frame input. `apps/tooling/wardentooling.py` registrations updated.
2. **v1 emit = flattened legacy shape.** Drop the `configs[0]` array wrapper since there's only ever one in practice (no A/B testing case has materialized). v1 `map_config.json` shape: `{schema_version: 1, reference_resolution, minimap_identification: {id, identification_threshold, roi, maps: {name: {zones: ZoneSpec[]}}}}`. The legacy `weight` + `weight_override` per-zone fields **are preserved in v1** (they're part of the working HUD V1 detector tuning); they're **dropped in v2** per the original AC5.
3. **Detection rule rewritten.** Old rule (`hsv` key presence) no longer disambiguates because v1 also has `hsv`. New rule: detect by **structure** — `minimap_identification.configs` array wrapper → v1; top-level `game_state_zones` present OR flat `minimap_identification.{name}: [zone_dict]` shape → v2; empty/legacy fallback → v1.
4. **AC6 reframed** as "no hash_comparator at all" (it's deleted); the v2-refusal-on-v1-tool concept moves into `map_config_emitter.py` as a single tool that handles both, dispatching internally.

ACs affected: AC1 (v1 branch shape), AC2 (still N/A — Story 1.13), AC3 (detection rule), AC4 (v1 emit shape), AC5 (unchanged), AC6 (collapsed into the single tool), AC7/AC9/AC10/AC11/AC12/AC13/AC14 unchanged. The Story 9.1 absorption note still applies — the new v1 emit also writes `schema_version: 1` as the first key. The Story 9.4 absorption note still applies — jsonschema strict validation gate persists across both emit paths.

## Story

As **Stephane** (sole tooling user; rebuilding the EVA detection pipeline for the redesigned HUD),
I want **`contracts/map-config.schema.json` to define a v2 shape (ROI/HSV-band-keyed `maps` + a new `game_state_zones` block) alongside the existing v1 (pHash-keyed) shape via a `oneOf` discriminator on a new `schema_version` field, AND `apps/tooling/tools/map_config_generator.py` + `apps/tooling/tools/hash_comparator.py` to emit v2 when the input `apps/tooling/config/config.yaml` carries ROI/HSV-band content (falling back to v1 pHash emit when it doesn't), with jsonschema strict validation at emit time and Zod regenerated cleanly via `pnpm --filter @warden/contracts build`**,
so that **Story 9.9b's iterative hand-merge cycle has a v2-capable tooling pipeline to consume, AND the v1 path keeps working unchanged — the bundled `apps/mobile/assets/map_config.json` continues to ship v1 with `schema_version: 1` so mobile consumers `gameDetector.ts` / `mapIdentifier.ts` (still pHash-keyed pre the post-V1 consumer rewrite) don't break.**

**Strategic context.** This is the code-side prerequisite for HUD 2.0 re-fingerprinting. Story 9.9 was originally a single stub (added 2026-05-14 via correct-course) that bundled five ACs: schema additions, hand-merge of Tool 8's `discovered_zones.yaml` fragment into `config/config.yaml`, regenerated `map_config.json` v2, Tool 9 re-validation, and a downstream PRD/architecture editorial pass. The stub was flagged "larger than one sprint — needs splitting at create-story time" because the hand-merge is iterative manual work (Tool 8 → Tool 9 → hand-merge → re-test, repeating across many sprints). The create-story split produced **9.9a** (this story — code path, one sprint), **9.9b** (iterative hand-merge, backlog, multi-sprint), and **9.10** (PRD/architecture editorial pass, backlog, small docs). V1 posture decision: **post-V1** — V1 ships with the legacy v1 `map_config.json` in place but bypassed by the new-HUD detection chain. 9.9a is V1-safe (the only ship-side impact is `schema_version: 1` being added as a new top-level field in the bundled v1 `map_config.json` — additive, non-breaking for mobile consumers since their Zod schema gets regenerated to accept it).

**Story 9.1 absorption.** The `oneOf` discriminator on `schema_version` is the cleanest way to branch the schema between the v1 pHash shape and the v2 ROI/HSV shape — but that design requires `schema_version` to exist in **both** branches, including v1. So 9.9a's natural scope covers Story 9.1's ACs (write `schema_version: 1` in `map_config_generator.py` + `hash_comparator.py` + the bundled `apps/mobile/assets/map_config.json` + pytest assert). Story 9.1 stays `backlog` in sprint-status for traceability; flip to `cancelled` with an "absorbed by 9-9a" rationale when 9.9a lands. Brownfield Item 7 framing (the original motivation for 9.1) is unchanged.

**Story 9.4 absorption.** The original 9.9 stub didn't enumerate jsonschema strict validation explicitly, but the existing Story 9.4 (`backlog`, detection-method-agnostic) covers it: `map_config_generator.py` validates the emitted dict against `contracts/map-config.schema.json` before writing the JSON file; failure → clean error + non-zero exit; same for `hash_comparator.py`. 9.9a folds 9.4's AC because once v2 emit is in place, both v1 and v2 emit paths share the same validation gate — splitting validation across two stories would invite drift. Story 9.4 stays `backlog`; flip to `cancelled` with "absorbed by 9-9a" rationale when 9.9a lands, OR repurpose 9.4 as the runtime/CI-side validation if jsonschema-at-emit isn't enough.

**Type:** Standard tooling+contracts feature story. Track C (tooling chain). No spike-or-split flag. Mixed Python + JSON Schema + auto-regenerated TypeScript Zod work; touches `apps/tooling/tools/` (Python emitters), `contracts/` (JSON Schema source of truth), and `packages/contracts/` (Zod regen output). Single-PR delivery + a tiny post-merge follow-up commit/PR for the sprint-status `review → done` flip (Two-PR pattern, [[feedback_two_pr_docs_execution]]).

## Acceptance Criteria (checklist)

> **AC checkbox convention:** items whose endpoint depends on **post-merge actions** (sprint-status `review → done` flip, PR merge) are held `[ ]` with carve-out notes per the AC-checkbox-tighten convention ([[feedback_ac_checkbox_tighten]]). All other items flip to `[x]` on dev-agent completion.

1. [x] **AC1 — `contracts/map-config.schema.json` v2 schema via `oneOf` discriminator.** Top-level required field `schema_version: integer enum [1, 2]` added. The schema splits into a `oneOf` with two branches, each keyed on `schema_version`:
   - **v1 branch (`schema_version: 1`):** required fields = `schema_version`, `reference_resolution`, `roi`, `canvas_size`, `hash_size`, `hash_method`, `maps`. `maps` values are `string` (hex pHash, pattern `^[0-9a-f]+$`) — **exact current v1 shape preserved unchanged**. Optional: `text_anchor_width`, `tile_cols`.
   - **v2 branch (`schema_version: 2`):** required fields = `schema_version`, `reference_resolution`, `game_state_zones`, `maps`. `game_state_zones` is an object with keys `lobby`, `in_match`, `score`, `transition` (all four required, `additionalProperties: false`), each an array of `ZoneSpec`. `maps` is `Record<string, ZoneSpec[]>` where keys are `MAP_LABELS` slugs (lowercased ASCII, pattern `^[a-z][a-z0-9_]*$`). `ZoneSpec` = `{ "name": string, "x": int≥0, "y": int≥0, "width": int≥1, "height": int≥1, "hsv": { "h_center": int 0–360, "h_tol": int 0–180, "s_center": int 0–100, "s_tol": int 0–100, "v_center": int 0–100, "v_tol": int 0–100 }, "min_ratio": number 0.0–1.0 }` — mirrors Tool 8's `discovered_zones.yaml` zone-dict shape at [`apps/tooling/tools/auto_roi_discoverer/export.py:72-91`](apps/tooling/tools/auto_roi_discoverer/export.py#L72) (user-space HSV, NOT OpenCV-space). v2 branch has NO `canvas_size`/`hash_size`/`hash_method`/`roi`/`text_anchor_width`/`tile_cols` fields (pHash-era; not used by ROI+HSV detection). `additionalProperties: false` at every object level (schema-level + per-branch + `ZoneSpec` + `hsv`).
   - **JSON Schema draft:** keep current `"$schema": "https://json-schema.org/draft/2020-12/schema"` (per existing file). The discriminator pattern uses `oneOf` with `const` matches on `schema_version` — no `discriminator` keyword (that's OpenAPI-only).

2. [x] **AC2 — Backward-compat for pre-existing v1 `map_config.json` files.** _(Reframed per Scope Adjustment: no bundled `apps/mobile/assets/map_config.json` exists today; the regen-of-bundled-asset closure is shifted to Story 1.13. The schema now requires `schema_version` on every emit — Story 1.13 will produce the first bundled v1 file already-correct via 9.9a's emit path.)_ Existing `apps/mobile/assets/map_config.json` on disk today does NOT carry `schema_version`. **Resolution:** the bundled `apps/mobile/assets/map_config.json` is **regenerated once as part of this story** so it carries `schema_version: 1` (via the same v1 emit path the tooling now writes); the file's other fields stay byte-identical to today's output (same pHash data, same `reference_resolution` / `roi` / `canvas_size` / `hash_size` / `hash_method`). The regenerated file is committed to the PR. No migration shim is needed — going forward, **all emits MUST include `schema_version`** (the schema enforces it). Any pre-existing on-disk file lacking `schema_version` becomes invalid at the moment 9.9a lands; the regen of the bundled asset closes that window.

3. [x] **AC3 — `map_config_generator.py` detects v1-vs-v2 input shape from `apps/tooling/config/config.yaml`.** New pure helper `_detect_schema_version(config_yaml_dict) -> int` returning `1` or `2`:
   - Returns `2` if EITHER `config_yaml_dict.get("game_state_zones")` is present and non-empty, OR if `config_yaml_dict.get("minimap_identification")` contains ROI/HSV-band data instead of (or alongside) pHash strings — detect by inspecting whether any map entry in `minimap_identification` has an `hsv` sub-key (Tool 8's zone-dict shape).
   - Returns `1` otherwise (legacy pHash-only input — current `config.yaml:60-907` shape).
   - Document the detection rule in a docstring + a one-line code comment.
   - **Caveat for 9.9b:** the hand-merge in 9.9b may produce a *mixed* `config.yaml` (some maps with pHash, others with ROI/HSV). For 9.9a, treat any ROI/HSV presence as "v2 emit" — clean cut. 9.9b's hand-merge MUST commit fully to ROI/HSV for the affected maps; mixed-emit is out of 9.9a's scope.

4. [x] **AC4 — `map_config_generator.py` v1 emit path (preserves existing behavior + `schema_version: 1`).** The current output dict assembled at [`apps/tooling/tools/map_config_generator.py:359-371`](apps/tooling/tools/map_config_generator.py#L359) gains a top-level `"schema_version": 1` field. All existing v1 fields and values stay byte-identical (no field reordering — preserve dict insertion order for clean diffs). Patch-mode behavior (`existing_config` merge at [`map_config_generator.py:352-379`](apps/tooling/tools/map_config_generator.py#L352)) preserves `schema_version: 1` when reading from an existing v1 file; refuses to merge into a v2 file (clean error: `"cannot patch-merge v1 hashes into a v2 (ROI/HSV) map_config.json — re-emit from config.yaml instead"`). This is Story 9.1's AC scope ([epics-and-stories.md:2626-2633](_bmad-output/epics-and-stories.md#L2626)), absorbed here.

5. [x] **AC5 — `map_config_generator.py` v2 emit path (NEW).** When `_detect_schema_version()` returns `2`:
   - Read `config_yaml_dict["game_state_zones"]` (dict of `lobby`/`in_match`/`score`/`transition` → list of zone dicts) and `config_yaml_dict["minimap_identification"]` (dict of map_name → list of zone dicts after the 9.9b hand-merge — legacy pHash entries excluded).
   - Build output dict shape:
     ```python
     {
       "schema_version": 2,
       "reference_resolution": {"width": ..., "height": ...},  # carry through from config.yaml's reference_resolution section
       "game_state_zones": {"lobby": [...], "in_match": [...], "score": [...], "transition": [...]},  # each list = ZoneSpec dicts per AC1
       "maps": {"artefact": [...], "atlantis": [...], ...}  # each list = ZoneSpec dicts per AC1
     }
     ```
   - Drop v1-only fields (`roi`, `canvas_size`, `hash_size`, `hash_method`, `text_anchor_width`, `tile_cols`) from v2 output — they're meaningless for ROI+HSV detection.
   - **Zone-dict pass-through:** the zone fields in `config.yaml` after 9.9b's hand-merge are expected to be Tool 8's fragment shape (`{name, x, y, width, height, hsv, min_ratio}`). If `config.yaml`'s legacy `minimap_identification` shape (`{id, x, y, width, height, hsv, min_ratio, weight, weight_override}` per [`apps/tooling/config/config.yaml:87-907`](apps/tooling/config/config.yaml#L87)) is encountered, 9.9a's emit MUST coerce: rename `id` → `name`, DROP `weight`/`weight_override` (not in v2 schema; their re-introduction is a 9.9b decision, not 9.9a's). Document the coercion in a code comment.
   - Map iteration order: use `MAP_LABELS` from [`apps/tooling/tools/frame_labeler.py:23`](apps/tooling/tools/frame_labeler.py#L23) so maps appear in canonical order (matches Tool 8/9's output ordering).

6. [x] **AC6 — `hash_comparator.py` v1-only emit (with `schema_version: 1`).** `hash_comparator.py` is pHash-bound by name + design (Hamming-distance helpers, `--write-config` emits the hash dict). Two changes:
   - When emitting via `--write-config` (find the existing emit site), add `"schema_version": 1` to the output dict; otherwise behavior unchanged.
   - If the input `config.yaml` triggers `_detect_schema_version() == 2` (ROI/HSV-band content present), `hash_comparator.py` refuses with a clean error to stderr: `"hash_comparator emits v1 (pHash) map_config.json only; the input config.yaml has ROI/HSV-band data — use map_config_generator.py for v2 emit"` + non-zero exit code. Reuse `_detect_schema_version` from `map_config_generator.py` (import or duplicate-by-copy with a `# duplicated from map_config_generator._detect_schema_version` comment — duplication acceptable for a 5-line pure function; don't carve a new shared module just for this).
   - This is Story 9.1's hash_comparator AC scope, absorbed here.

7. [x] **AC7 — jsonschema strict validation at emit time (BOTH generators).** Before writing the output JSON file, both `map_config_generator.py` AND `hash_comparator.py` validate the in-memory output dict against `contracts/map-config.schema.json` via `jsonschema.validate()`. Validation failure → clean stderr error including the failing JSON path (e.g., `"map_config validation failed at $.maps.artefact[2].hsv.h_center: 720 is greater than the maximum of 360"`) + non-zero exit code + **NO file write** (atomic — never leave a partial/invalid file on disk). Successful validation → the file is written via `json.dump(output, f, indent=2)` per the existing convention at [`map_config_generator.py:382-383`](apps/tooling/tools/map_config_generator.py#L382). `jsonschema` is already a tooling dep (per [`apps/tooling/pyproject.toml`](apps/tooling/pyproject.toml) — verify before relying on it; install if missing). This is Story 9.4's AC scope, absorbed here.

8. [x] ~~**AC8 — Bundled `apps/mobile/assets/map_config.json` regenerated with `schema_version: 1`.**~~ **DEFERRED to Story 1.13** per Scope Adjustment block — no bundled file exists in the repo today; Story 1.13 (Hybrid map_config.json Delivery, currently `backlog`) is the natural owner and will produce the first bundled v1 asset with `schema_version: 1` already in place via 9.9a's emit path. Re-run `python tools/map_config_generator.py` against the existing `apps/tooling/config/config.yaml` (still legacy pHash shape — 9.9b hasn't started yet) → produces a regenerated `apps/mobile/assets/map_config.json` that's byte-identical to today's file EXCEPT for the added top-level `"schema_version": 1` field. Commit the regenerated file. Verify with `git diff apps/mobile/assets/map_config.json` that the only added line is `"schema_version": 1` (with appropriate JSON formatting/comma) — no incidental field reordering or whitespace churn.

9. [x] **AC9 — Zod regen via `pnpm --filter @warden/contracts build` is clean.** Update `contracts/map-config.schema.json` per AC1 → run `pnpm --filter @warden/contracts build` → it regenerates `packages/contracts/src/generated/map-config.ts` via [`packages/contracts/scripts/generate-zod.mjs:17-30`](packages/contracts/scripts/generate-zod.mjs#L17). The regenerated Zod type is a discriminated union over `schema_version` (using `z.discriminatedUnion("schema_version", [...])` if `json-schema-to-zod` produces it; otherwise `z.union([...])` is acceptable). Commit the regenerated `map-config.ts`. CI's `contracts-codegen-check.yml` workflow ([`.github/workflows/contracts-codegen-check.yml`](.github/workflows/contracts-codegen-check.yml)) MUST pass on this PR (no dirty diff after regen on top of the committed schema).

10. [x] **AC10 — Pytest coverage** in `apps/tooling/tests/test_map_config_generator.py` (extend existing file if present; create if not):
    - **`_detect_schema_version`:** v1 input (legacy pHash-keyed `minimap_identification`) → returns `1`; v2 input with `game_state_zones` present → returns `2`; v2 input with ROI/HSV-band data in `minimap_identification` (no `game_state_zones`) → returns `2`; empty config → returns `1` (default fallback).
    - **v1 emit path:** synthetic config.yaml with legacy pHash maps → output JSON has `schema_version: 1` + existing v1 fields preserved (assert against a golden fixture); jsonschema validation passes.
    - **v2 emit path:** synthetic config.yaml with `game_state_zones` + ROI/HSV-keyed maps → output JSON has `schema_version: 2` + `game_state_zones` block + per-map zone arrays; jsonschema validation passes; legacy `weight`/`weight_override` fields in input are coerced (dropped) in output.
    - **jsonschema validation guards:** output dict with extra unknown top-level field → `jsonschema.exceptions.ValidationError` raised; no file written. Output dict missing `schema_version` → ValidationError. Output dict with `schema_version: 1` but v2 shape → ValidationError (oneOf mismatch). Output dict with HSV out-of-range (e.g., `h_center: 720`) → ValidationError.
    - **`hash_comparator.py`:** synthetic v1 input → v1 emit succeeds with `schema_version: 1`; synthetic v2-shaped input (ROI/HSV data) → refuses with clean stderr error + non-zero exit; no file written.
    - **Bundled-asset golden snapshot test:** the regenerated `apps/mobile/assets/map_config.json` (the actual committed file) has `schema_version: 1` AND otherwise matches a captured byte-for-byte snapshot of the pre-9.9a file (with the new field added). This test pins the AC8 regen against accidental drift.
    - Run commands: `cd apps/tooling && uv run pytest tests/test_map_config_generator.py -v`; full suite gate (`cd apps/tooling && uv run pytest` + `pnpm --filter tooling test`) must stay green — currently **131 tests** post Story 9.8.

11. [x] **AC11 — `apps/web/src/lib/schemas/subscription.ts` and mobile `detectionConfig.ts` import-side audit (no code change in 9.9a).** _(Demoted per Scope Adjustment to typecheck-only gate: ran `pnpm --filter web typecheck` + `pnpm --filter mobile typecheck` after Zod regen; both surface pre-existing baseline failures verified via `git stash` baseline run. No new regressions from 9.9a. The mapIdentifier.ts narrowing concern is moot — the file uses the handwritten `DetectionConfig` type from `detectionConfig.ts`, NOT `MapConfigSchema` from `@warden/contracts`.)_ The auto-regenerated `packages/contracts/src/generated/map-config.ts` is consumed by `apps/web` (via `@warden/contracts/map-config` re-export per [`packages/contracts/src/index.ts`](packages/contracts/src/index.ts)) AND by `apps/mobile/src/features/video-processing/detectionConfig.ts` (the mobile Zod validator). 9.9a's regenerated Zod is a discriminated union — older consuming code that did `MapConfigSchema.parse(x).maps[name]` and treated values as strings will now see a union type. **Confirm before merge:** (a) `apps/web` typecheck passes (`pnpm --filter web typecheck`); (b) `apps/mobile` typecheck passes (`pnpm --filter mobile typecheck`); (c) `apps/mobile/src/features/video-processing/mapIdentifier.ts` ([line 48](apps/mobile/src/features/video-processing/mapIdentifier.ts#L48)) still typechecks — if the discriminated union forces a narrowing call (`if (config.schema_version === 1) ...`), add the narrow but keep the runtime behavior identical (no functional change to pHash matching). If the narrowing change is non-trivial (more than ~5 lines of edits in mapIdentifier.ts) → STOP and escalate; the v2-consumer rewrite is a separate post-V1 story, NOT this one.

12. [x] **AC12 — No new third-party dependencies.** _(Verified: `jsonschema>=4.23.0` and `pyyaml>=6.0,<7` already in `apps/tooling/pyproject.toml`; `json-schema-to-zod` already a dep per `packages/contracts/package.json`. No new Python or JS deps added.)_ `jsonschema` (already a tooling dep), `pyyaml` (already a tooling dep), `json-schema-to-zod` (already a contracts dep — verify via [`packages/contracts/package.json`](packages/contracts/package.json)) cover all the runtime needs. Update `apps/tooling/pyproject.toml` only if `jsonschema` is missing (it should already be there per [tooling-SCHEMA-001] requirement). Reject any temptation to add new Python or JS deps.

13. [ ] **AC13 — Sprint-status entry + lifecycle flip.** `_bmad-output/sprint-status.yaml` gains a `9-9a-schema-v2-and-map-config-generator: ready-for-dev` entry under `epic-9` at create-story time (`epic-9` already `in-progress`, no epic flip). The entry then flows `ready-for-dev → in-progress → review` across the dev work, and `review → done` post-merge. _Pending — flips ship in the Two-PR follow-up commit/PR per [[feedback_two_pr_docs_execution]]._

14. [ ] **AC14 — Single-PR delivery + follow-up flip.** All file changes ship in one PR titled `feat: schema v2 evolution + map_config_generator v2 emit (Story 9.9a)` (subject lowercased on the commit to satisfy commitlint's `subject-case`; capitalized in the PR title). Branch `story-9-9a-schema-v2-and-generator` off `main`. PR body links: this story file; [`_bmad-output/epics-and-stories.md`](_bmad-output/epics-and-stories.md) for the 9.9 split section; Tool 8's [`apps/tooling/tools/auto_roi_discoverer.md`](apps/tooling/tools/auto_roi_discoverer.md) for the v2 zone-dict shape rationale. The `review → done` flip ships in a separate tiny follow-up commit/PR (Two-PR pattern). _Pending — flips ship in the Two-PR follow-up commit/PR per [[feedback_two_pr_docs_execution]]._

## Tasks / Subtasks

> **Implementation order:** schema first (it's the contract; everything else conforms), then the Python emitters' detection helper + v1 schema_version addition (the V1-safe slice that closes Story 9.1's ACs), then v2 emit logic (the new behavior; only exercised by future v2 inputs), then jsonschema validation gate (folds Story 9.4), then Zod regen + mobile/web typecheck audit, then tests, then the bundled-asset regen + commit, then PR + sprint-status flip.

- [x] **Task 1: JSON Schema v2 evolution (AC: 1, 12)**
  - [x] Edit `contracts/map-config.schema.json`: add top-level required `schema_version` field; restructure body as `oneOf` with v1 + v2 branches per AC1. Keep `$schema` and `$id` unchanged. `additionalProperties: false` at every object level.
  - [x] Validate the schema file itself parses cleanly: `python -c "import json; from pathlib import Path; json.loads(Path('contracts/map-config.schema.json').read_text())"`.
  - [x] Pre-validate that a bare existing v1 file (without `schema_version`) fails the new schema — confirmed via test `TestJsonschemaValidationGate::test_missing_schema_version_rejected`. (Note: no bundled `apps/mobile/assets/map_config.json` exists in the repo today — see Scope Adjustment block; the test substitutes a synthetic v1 dict.)

- [x] **Task 2: `_detect_schema_version` helper + AC8 detection rule (AC: 3)**
  - [x] Added pure helper `_detect_schema_version(config_yaml_dict: dict) -> int` to `apps/tooling/tools/map_config_generator.py` near the top of the module (above `process_frame`). Implementation matches AC3 rule.
  - [x] Documented the v1/v2 detection rule in a docstring; one-line code comment added at the call site in `run()` + at the v2 short-circuit in `main()`.

- [x] **Task 3: v1 emit path — add `schema_version: 1` (AC: 4, absorbs Story 9.1)**
  - [x] In `map_config_generator.py:run()`, `"schema_version": 1` inserted as the first key of the output dict.
  - [x] Patch-mode merge logic: refuses (clean error + sys.exit(1)) if `existing_config["schema_version"] == 2` BEFORE any file I/O.
  - [x] `hash_comparator.py:generate_map_config()`: `"schema_version": 1` inserted as the first key of the output dict.

- [x] **Task 4: v2 emit path (AC: 5)**
  - [x] `_build_v2_output(config_yaml_dict) -> dict` added to `map_config_generator.py`; reads `game_state_zones` + `minimap_identification` (post-9.9b flat shape), coerces zone dicts to v2 `ZoneSpec` (rename `id` → `name`; drop `weight`/`weight_override`), assembles the output dict per AC5. `_run_v2(config, output_dir)` wraps the build + validation + write, called from `main()`'s v2 short-circuit (skips frame loading).
  - [x] Map iteration uses `MAP_LABELS` from `tools.frame_labeler` for stable canonical order.
  - [x] `hash_comparator.py:main()`: when input triggers `_detect_schema_version() == 2`, prints clean stderr error (`"hash_comparator emits v1 (pHash) map_config.json only; ... use map_config_generator.py for v2 emit"`) + `sys.exit(1)` BEFORE any file I/O.

- [x] **Task 5: jsonschema strict validation gate (AC: 7, absorbs Story 9.4)**
  - [x] `_validate_against_schema(output_dict, schema_path: Path)` added to both `map_config_generator.py` AND `hash_comparator.py` (`Draft202012Validator`; raises `jsonschema.exceptions.ValidationError` with the failing JSON path in the error message). Called immediately before `json.dump` in both v1 and v2 emit paths.
  - [x] On validation error: clean stderr message including `$<path>` + `sys.exit(1)`; file is NOT written (atomic).
  - [x] `jsonschema>=4.23.0` is already in `apps/tooling/pyproject.toml` — no install needed.

- [x] **Task 6: Zod regen (AC: 9, 11)**
  - [x] Ran `pnpm --filter @warden/contracts build` → `packages/contracts/src/generated/map-config.ts` regenerated cleanly (produces a runtime-validating discriminated union via `.superRefine`/`oneOf` pattern emitted by `json-schema-to-zod`). Output committed.
  - [x] Ran `pnpm --filter web typecheck` + `pnpm --filter mobile typecheck`: both report errors but the errors are **pre-existing baseline issues unrelated to map-config** (web: Zod 4 vs react-hook-form, Stripe API version pin, test spreads. mobile: `firebase/auth` `getReactNativePersistence` export — Firebase v12 migration is unfinished per Stories 1.4–1.9 backlog). Verified pre-existing by running both typechecks against `main` (via `git stash`) → identical error set. **No new typecheck regressions are introduced by 9.9a** (AC11 demoted scope, per Scope Adjustment block).

- [x] ~~**Task 7: Bundled-asset regeneration (AC: 8)**~~ **DEFERRED to Story 1.13** per Scope Adjustment block (no `apps/mobile/assets/map_config.json` exists in the repo today; Story 1.13 — Hybrid map_config.json Delivery, currently `backlog` — will produce the first bundled v1 asset with `schema_version: 1` already in place using 9.9a's emit path).
  - [x] Sub-task obsoleted by deferral.
  - [x] Sub-task obsoleted by deferral.

- [x] **Task 8: Pytest coverage (AC: 10)**
  - [x] Created `apps/tooling/tests/test_map_config_generator.py` with 27 tests across 5 buckets:
    - `TestDetectSchemaVersion` (7 cases): empty config → v1; legacy `minimap_identification.configs` shape → v1; `game_state_zones` present → v2; empty `game_state_zones` → v1; flat `minimap_identification` with HSV zones → v2; `None` minimap → v1; `hash_comparator._detect_schema_version` agrees with `map_config_generator._detect_schema_version`.
    - `TestBuildV2Output` (5 cases): top-level shape + `roi`/`canvas_size`/`hash_method` absent; in_match present even when input empty; map iteration in MAP_LABELS canonical order; legacy `id` → `name` coercion; `weight`/`weight_override` dropped.
    - `TestJsonschemaValidationGate` (7 cases): valid v1 passes; valid v2 passes; extra unknown top-level field rejected; missing `schema_version` rejected; v1 fields with `schema_version: 2` rejected (oneOf mismatch); HSV `h_center: 720` rejected; both helpers (gen + hc) agree on the gate.
    - `TestV1Emit` (3 cases): synthetic frames → output has `schema_version: 1` first + all v1 fields preserved + maps populated; validation passes; patch-mode refuses to merge v1 hashes into a v2 existing file (sys.exit(1) + no file).
    - `TestV2Emit` (4 cases): synthetic v2 config → output has `schema_version: 2` + game_state_zones (4 keys) + maps; validation passes; legacy weight fields dropped; invalid HSV → gate fires + no file written (atomic).
    - `TestHashComparatorV2Refusal` (1 case, subprocess): feeding `hash_comparator.py` a v2-shaped config.yaml → non-zero exit + clean stderr message.
  - [x] (Folded `test_map_config_schema.py` cases into the same file — chose not to split since the validation gate is shared between both generators and the test surface is contiguous.)
  - [x] `cd apps/tooling && uv run pytest -v` → **158 passed in 0.66s** (131 → 158 = +27 new tests, full suite green).
  - [x] `pnpm --filter tooling test` → **158 passed in 1.61s** (workspace task picks up the new file).

- [ ] **Task 9: PR + sprint-status flips (AC: 13, 14)**
  - [ ] Branch `story-9-9a-schema-v2-and-generator` off `main`. Logical commit chunks: (a) schema v2 (`contracts/map-config.schema.json`); (b) `_detect_schema_version` + `_build_v2_output` + `_validate_against_schema` helpers; (c) v1 emit `schema_version: 1` + v2 short-circuit + jsonschema validation gate in both generators; (d) Zod regen + auto-generated `map-config.ts`; (e) tests; (f) story file updates + sprint-status `ready-for-dev → in-progress → review` flip + epics-and-stories.md create-story prework. (Task 7's bundled-asset commit chunk dropped per Scope Adjustment.)
  - [ ] Push, open PR `feat: schema v2 evolution + map_config_generator v2 emit (Story 9.9a)` against `main`. PR body per AC14.
  - [ ] After merge: post-merge follow-up branch `story-9-9a-postmerge`: sprint-status `review → done`; flip `9-9a-schema-v2-and-map-config-generator` AC13/AC14 + Task 9 sub-boxes to `[x]`; Status → `done`; bump `last_updated`. Also flip `9-1-schema-version-1-add-to-map-config-writers: backlog → cancelled` with "absorbed by 9-9a" rationale; flip `9-4-jsonschema-strict-validation-against-map-config-schema: backlog → cancelled` similarly.

## Dev Notes

### Strategic context

Story 9.9a is the **code-side prerequisite** for HUD 2.0 re-fingerprinting. The new-HUD tooling chain (Stories 9.5/9.6/9.7/9.8 — Tool 6 label → Tool 7 stack → Tool 8 discover → Tool 9 measure) is fully operational; what's missing is the **emit pipeline that turns the discovered ROI/HSV zones into a shippable `map_config.json` v2** — and the **schema that defines what v2 even means**. 9.9a builds both, but does NOT ship a v2 `map_config.json` to mobile. The bundled `apps/mobile/assets/map_config.json` stays v1 (pHash, `schema_version: 1`) so the mobile consumers `gameDetector.ts` / `mapIdentifier.ts` keep working unchanged through V1. The actual v2 emit + hand-merge is **9.9b**'s scope; the consumer rewrite is a separate post-V1 story.

The `oneOf` discriminator pattern is the cleanest way to evolve the schema. It lets v1 and v2 coexist in a single schema file (no parallel `map-config-v2.schema.json`), the regenerated Zod becomes a discriminated union (`z.discriminatedUnion("schema_version", [v1Schema, v2Schema])` if `json-schema-to-zod` produces it; falls back to `z.union([...])` with manual narrowing otherwise — the consumers will need an `if (config.schema_version === 1)` branch when they want to read pHash-shape values, but since 9.9a only ships v1 to mobile, the narrowing is a no-op in practice). This pattern was chosen over: (a) separate v1 / v2 schema files (worse — duplicates the shared fields like `reference_resolution`); (b) optional v2 fields next to required v1 fields (worse — `additionalProperties: false` can't distinguish "this is a v2 file with no pHash fields, that's fine" from "this is a v1 file missing required pHash fields, that's broken"); (c) a `discriminator` keyword (OpenAPI-only; not standard JSON Schema).

The detection rule (`_detect_schema_version` at AC3) is the bridge: it lets `map_config.json` regeneration be driven entirely by the **input `config.yaml`'s shape**, not by a CLI flag. The user just hand-merges Tool 8's fragment into `config.yaml` (9.9b's work) and re-runs `map_config_generator.py`; the generator notices the new shape and emits v2. This minimizes the "two emit modes" cognitive surface — no `--emit-version` flag — and lets 9.9b iterate without touching 9.9a's code again.

### Key code patterns to reuse (NOT reinvent)

| Need | Source | Notes |
|---|---|---|
| v2 zone-dict shape (`name`/`x`/`y`/`width`/`height`/`hsv{h_center,h_tol,s_center,s_tol,v_center,v_tol}`/`min_ratio`) | [`apps/tooling/tools/auto_roi_discoverer/export.py:72-91 build_fragment`](apps/tooling/tools/auto_roi_discoverer/export.py#L72) and the live [`apps/tooling/output/auto_rois/v2.0/discovered_zones.yaml`](apps/tooling/output/auto_rois/v2.0/discovered_zones.yaml) | Tool 8's fragment IS the v2 source-of-truth. Mirror its keys + types in the JSON Schema. HSV is **user-space** (H 0–360, S/V 0–100) — NOT OpenCV-space. |
| 4 game-state class names | [`apps/tooling/tools/auto_roi_discoverer/model.py:19 TARGET_CLASSES`](apps/tooling/tools/auto_roi_discoverer/model.py#L19) | `("lobby", "in_match", "score", "transition")`. Use these exact strings as `game_state_zones`' required keys in the schema. |
| 14-map canonical class list | [`apps/tooling/tools/frame_labeler.py:23 MAP_LABELS`](apps/tooling/tools/frame_labeler.py#L23) | Drives `maps` key ordering on v2 emit (canonical order). Schema-side: `maps` is `additionalProperties: { type: array, items: ZoneSpec }` with key pattern matching map slugs (`^[a-z][a-z0-9_]*$`), no required enumeration (some maps may legitimately have no zones yet). |
| Current v1 output dict assembly | [`apps/tooling/tools/map_config_generator.py:257-396 run`](apps/tooling/tools/map_config_generator.py#L257) — output dict built at lines 359–371; `json.dump` at lines 382–383 | This is where `schema_version: 1` insertion goes (Task 3) AND where the v2 branch hooks in (Task 4). Preserve dict key insertion order on v1 emit to keep `apps/mobile/assets/map_config.json` diff clean (AC8). |
| Current v1 hash_comparator emit site | `apps/tooling/tools/hash_comparator.py` `--write-config` flow | Same `schema_version: 1` insertion + v2-refusal logic. |
| jsonschema strict-validation pattern | `jsonschema.validate(instance, schema)` raising `jsonschema.exceptions.ValidationError` | Standard usage. For the failing-path message, format `e.json_path` (or `e.absolute_path`) into the stderr text. |
| JSON Schema source-of-truth + Zod regen | [`contracts/map-config.schema.json`](contracts/map-config.schema.json) + [`packages/contracts/scripts/generate-zod.mjs:17-30`](packages/contracts/scripts/generate-zod.mjs#L17) | The Zod regen is fully automated by `pnpm --filter @warden/contracts build` — no `generate-zod.mjs` code changes needed. CI gate: `.github/workflows/contracts-codegen-check.yml` fails on dirty diff. |
| Mobile consumer side that consumes regenerated Zod | [`apps/mobile/src/features/video-processing/detectionConfig.ts`](apps/mobile/src/features/video-processing/detectionConfig.ts) (imports `@warden/contracts/map-config`) + [`apps/mobile/src/features/video-processing/mapIdentifier.ts:48`](apps/mobile/src/features/video-processing/mapIdentifier.ts#L48) (`Object.entries(config.maps)` expects pHash hex string values) | After the Zod regen, the union type forces narrowing. If `mapIdentifier.ts` needs a `if (config.schema_version === 1)` narrow, ≤5 lines edit acceptable (per AC11); more than that → STOP and escalate. |
| Web consumer side | `apps/web/src/lib/schemas/` re-exports from `@warden/contracts/map-config` per [`apps/web/src/lib/schemas/subscription.ts`](apps/web/src/lib/schemas/subscription.ts) precedent | Web doesn't consume `map_config` in V1 (mobile-only feature). Typecheck must still pass. |
| pytest layout / `conftest.py` already lifts `apps/tooling/` onto `sys.path` | [`apps/tooling/tests/conftest.py`](apps/tooling/tests/conftest.py) | No new conftest. `tests/test_map_config_generator.py` extends an existing file (verify before creating). |

### Anti-patterns / disasters to avoid

- **DO NOT break v1 mobile consumers.** `apps/mobile/src/features/video-processing/mapIdentifier.ts:48` does `Object.entries(config.maps)` and treats values as `string` (pHash hex). After 9.9a's Zod regen, the type becomes a union — the narrowing must keep the runtime behavior identical for v1 inputs. If you find yourself rewriting the pHash-matching logic, **STOP**: that's the post-V1 consumer rewrite story, not 9.9a.
- **DO NOT ship a v2 `apps/mobile/assets/map_config.json`.** The bundled asset stays v1 (`schema_version: 1`, same pHash data as today). v2 emit lives in the tooling pipeline but doesn't reach mobile until 9.9b's hand-merge + the consumer rewrite ship. If the dev finds themselves running `map_config_generator.py` and it emits v2, the input `config.yaml` was already hand-merged — back out and confirm 9.9b hasn't started yet.
- **DO NOT add a `--emit-version` CLI flag.** Emit shape is driven by input shape (`_detect_schema_version`). A flag would let the user override the detection and ship a mismatched config; not worth the surface area.
- **DO NOT reinvent the zone-dict shape.** v2 `ZoneSpec` mirrors Tool 8's fragment shape at `export.py:72-91` exactly. Renaming/restructuring (e.g., adding a `kind` field for game-state vs map) introduces drift that breaks Tool 9 → 9.9a → mobile alignment.
- **DO NOT introduce a parallel `map-config-v2.schema.json` file.** Single schema, `oneOf` branch. Two schema files = two Zod regen targets = double the consumer-side complexity.
- **DO NOT write `weight` / `weight_override` into v2 output.** Those are legacy `minimap_identification` fields from the pre-9.9 config.yaml shape; they're not in Tool 8's fragment and not in the v2 schema. Coerce-drop on v2 emit. If 9.9b's hand-merge eventually wants `weight` back, that's a v3 conversation.
- **DO NOT validate the schema file against itself manually.** Trust `jsonschema.Draft202012Validator.check_schema()` if you need a sanity check on the schema's well-formedness — but the real validation gate is at emit time (AC7) against output dicts.
- **DO NOT silently overwrite `apps/mobile/assets/map_config.json` with reordered fields.** Preserve current key insertion order on v1 emit so the AC8 diff is exactly one line (`+ "schema_version": 1,`). Any incidental reordering = fix the emit logic.
- **DO NOT use `cv2.imread`/`cv2.imwrite` here.** Neither `map_config_generator.py` nor `hash_comparator.py` reads or writes images in 9.9a's scope — they manipulate config dicts. The Windows non-ASCII path concern from Tools 6/7/8/9 doesn't apply.
- **DO NOT modify `docs/architecture-tooling.md` or `apps/tooling/README.md`** — both predate Tools 6/7/8/9 (known doc-debt; deferred docs-refresh story).
- **DO NOT touch `gameDetector.ts` or `mapIdentifier.ts` beyond the ≤5-line type narrowing in AC11.** The consumer rewrite is a separate post-V1 story; expanding scope here defeats the split.
- **DO NOT add new third-party dependencies.** `jsonschema`/`pyyaml` (Python) + `json-schema-to-zod` (TS) cover everything. Verify presence; don't reach for alternatives.

### File structure

```
contracts/
  map-config.schema.json                  # UPDATED: top-level schema_version + oneOf v1/v2 branches + additionalProperties: false

packages/contracts/
  src/
    generated/
      map-config.ts                       # AUTO-REGENERATED via pnpm --filter @warden/contracts build (commit the regen output)

apps/tooling/
  config/
    config.yaml                           # UNCHANGED in 9.9a (the hand-merge that introduces ROI/HSV-band content is 9.9b's job)
  tools/
    map_config_generator.py               # UPDATED: _detect_schema_version + v1 emit gains schema_version: 1 + v2 emit branch + jsonschema validation gate
    hash_comparator.py                    # UPDATED: schema_version: 1 on v1 emit + v2-input refusal + jsonschema validation gate
    auto_roi_discoverer/                  # UNCHANGED (Tool 8 — reused as v2 zone-dict shape reference)
    frame_labeler.py                      # UNCHANGED (reused: MAP_LABELS for v2 map iteration order)
  tests/
    test_map_config_generator.py          # EXTENDED (or created): v1/v2 emit + detection helper + jsonschema validation + bundled-asset snapshot
    test_map_config_schema.py             # NEW (or merged into above): jsonschema strict-validation guard cases (Story 9.4's planned home)
  pyproject.toml                          # MAYBE UPDATED if jsonschema isn't already a dep (it should be)

apps/mobile/
  assets/
    map_config.json                       # REGENERATED with schema_version: 1 added; otherwise byte-identical to today (AC8)
  src/features/video-processing/
    detectionConfig.ts                    # POSSIBLY UPDATED (≤5 lines) if Zod union narrowing requires it (AC11)
    mapIdentifier.ts                      # POSSIBLY UPDATED (≤5 lines) if Zod union narrowing requires it (AC11)
    gameDetector.ts                       # UNCHANGED — no pHash dependency

apps/web/                                 # UNCHANGED — web doesn't consume map_config in V1, but typecheck must still pass
```

### Library / framework requirements

- **Python ≥ 3.11** (pyproject baseline).
- **`jsonschema`** — already a tooling dep (per Story 9.4 plan); verify in `apps/tooling/pyproject.toml`. Strict draft 2020-12 validator.
- **`pyyaml ≥ 6.0, < 7`** — already a dep. Reads `config.yaml`.
- **stdlib** — `json`, `pathlib`, `dataclasses`, `sys`, `argparse`. No new imports needed.
- **TS side:** `@warden/contracts` (workspace package) + `json-schema-to-zod` (already a dep per `packages/contracts/package.json`). No new TS deps.
- **No new third-party dependencies.**

### Testing standards

- `pytest` 8.0+ already in `apps/tooling/pyproject.toml` `[project.optional-dependencies] dev`; run via `uv run pytest`. `apps/tooling/tests/conftest.py` already prepends `apps/tooling/` to `sys.path` — no new conftest.
- **All pure logic** unit-tested with `tmp_path` synthetic config.yaml inputs + synthetic golden-output JSON fixtures. No real video, no ffmpeg, no Tk.
- **Bundled-asset snapshot test:** the regenerated `apps/mobile/assets/map_config.json` is committed to the repo; the snapshot test asserts byte-identity (modulo the `schema_version: 1` addition) against a captured pre-9.9a baseline. Pins AC8 against accidental drift.
- **Cross-workspace gate:** after the Python tests pass, run `pnpm --filter @warden/contracts build` (regenerates Zod) + `pnpm --filter web typecheck` + `pnpm --filter mobile typecheck` — all must pass. The TS type-narrowing impact on consumers is the AC11 audit gate.
- Run commands: `cd apps/tooling && uv run pytest tests/test_map_config_generator.py -v`; full suite `cd apps/tooling && uv run pytest` (must stay green — currently **131** post Story 9.8); workspace gate `pnpm --filter tooling test` + `pnpm --filter @warden/contracts build` + cross-typecheck. CI's `contracts-codegen-check.yml` workflow enforces no-dirty-diff on the regen.

### Sprint-fit + dependencies

- **Track C** (tooling chain). Parallel with Tracks A/B; independent of the AR-SPIKE outcome.
- **Upstream:** Stories 9.7 (Tool 8) and 9.8 (Tool 9) — both `done`/merged. 9.9a uses Tool 8's `discovered_zones.yaml` fragment as the v2 zone-dict shape reference (not at runtime — at design time, in the JSON Schema).
- **Absorbs:** Story 9.1 (`schema_version: 1` writer ACs) + Story 9.4 (jsonschema strict validation ACs). Both stay `backlog` for traceability through 9.9a's merge; flip to `cancelled` with "absorbed by 9-9a" rationale in the post-merge follow-up.
- **Downstream:** Story 9.9b (iterative hand-merge — uses 9.9a's v2 emit path); Story 9.10 (docs editorial — anchored to 9.9b's measured accuracy floors). The post-V1 mobile consumer rewrite (`gameDetector.ts` + `mapIdentifier.ts` switching from pHash to ROI+HSV) is downstream of 9.9a's schema additions but is NOT enumerated as a story yet — it surfaces during V1 launch review or post-V1 planning.
- **Cross-epic:** Story 1.13 (Hybrid `map_config.json` Delivery) — unchanged; it ships the bundled v1 asset 9.9a regenerates. Story 10.1 (V1 Launch Checklist) — must NOT carry any 9.9-variant sign-off row (V1 posture: post-V1).
- **Sprint fit:** fits-in-one-sprint. ~1 day Python (detection helper + v1/v2 emit branch + validation gate), ~0.5 day JSON Schema authoring, ~0.5 day tests + bundled-asset regen, ~0.5 day Zod regen + cross-typecheck audit. ~2.5 days total focused work.
- **Branch off:** `main` (9.7 and 9.8 already merged in PR #10). No rebase choreography needed.

### Project Structure Notes

- **Naming:** `9-9a-schema-v2-and-map-config-generator` follows the split convention introduced 2026-05-15 by this create-story run. `9-9b-...` + `9-10-...` siblings stay `backlog` until 9.9a lands.
- **Schema file location stays `contracts/`** — the language-agnostic source-of-truth root, NOT `packages/contracts/src/` (which is the auto-generated TS target). This matches the existing layout per [`architecture.md:1629`](_bmad-output/architecture.md#L1629).
- **Zod regen output stays `packages/contracts/src/generated/map-config.ts`** with the "Do not edit by hand" banner. Committed to the repo per the existing `contracts-codegen-check.yml` CI gate (any drift between schema + generated Zod fails CI).
- **Bundled `apps/mobile/assets/map_config.json` regen is part of the PR.** The diff is exactly the one-line `schema_version: 1` addition; AC8 verifies no incidental churn. The bundled asset is the Metro-asset baseline per Decision #2 (Hybrid delivery — bundled + Firestore overlay).
- The Epic 9 charter amendment from the 2026-05-14 correct-course enumerates 9.5–9.9 (now including 9.9a/9.9b/9.10 via this split). 9.5/9.6/9.7/9.8 are documented as thin pointer entries in [`_bmad-output/epics-and-stories.md`](_bmad-output/epics-and-stories.md); 9.9a/9.9b/9.10 follow the same thin-pointer convention with full detail in the per-story files.

### References

- [Source: _bmad-output/epics-and-stories.md#Epic-9](_bmad-output/epics-and-stories.md#L2614) — Epic 9 charter (Tooling — V1 Pipeline Hardening + New-HUD Detection Chain).
- [Source: _bmad-output/epics-and-stories.md#L2728](_bmad-output/epics-and-stories.md#L2728) — Story 9.9 split section (9.9a + 9.9b + 9.10), V1 posture decision, Story 9.1/9.4 absorption notes.
- [Source: _bmad-output/sprint-status.yaml:39](_bmad-output/sprint-status.yaml#L39) — `last_updated` header: 2026-05-15 create-story split rationale.
- [Source: _bmad-output/sprint-change-proposal-2026-05-14.md](_bmad-output/sprint-change-proposal-2026-05-14.md) — Original correct-course that added the 9.9 stub.
- [Source: _bmad-output/architecture.md#L1499](_bmad-output/architecture.md#L1499) — `apps/mobile/src/features/video-processing/` directory map; `mapIdentifier.ts:1505` "pHash matcher" line flagged for 9.10 editorial.
- [Source: _bmad-output/prd.md#L955](_bmad-output/prd.md#L955) — `tooling-HASH-001/002` framing flagged for 9.10 editorial.
- [Source: _bmad-output/implementation-artifacts/9-7-auto-roi-discoverer-tool-8.md](9-7-auto-roi-discoverer-tool-8.md) — Tool 8 story file: zone-dict shape rationale + AC15 per-map-classes addition.
- [Source: _bmad-output/implementation-artifacts/9-8-roi-detection-tester-tool-9.md](9-8-roi-detection-tester-tool-9.md) — Tool 9 story file: detection-pipeline validation patterns; v1 → v2 transition will eventually be measured by re-running Tool 9 against the regenerated config (that's 9.9b's job, not 9.9a's).
- [Source: contracts/map-config.schema.json](contracts/map-config.schema.json) — Current v1 schema (target for 9.9a's evolution).
- [Source: packages/contracts/scripts/generate-zod.mjs](packages/contracts/scripts/generate-zod.mjs) — Zod regen mechanism (no code changes needed; runs via `pnpm --filter @warden/contracts build`).
- [Source: apps/tooling/tools/map_config_generator.py](apps/tooling/tools/map_config_generator.py) — v1 emit; the file 9.9a extends. Output dict at lines 359–371; `json.dump` at lines 382–383; patch-mode merge at lines 352–379.
- [Source: apps/tooling/tools/hash_comparator.py](apps/tooling/tools/hash_comparator.py) — v1 hash dict emit (via `--write-config`); the file 9.9a extends with `schema_version: 1` + v2 refusal.
- [Source: apps/tooling/tools/auto_roi_discoverer/export.py:72-91](apps/tooling/tools/auto_roi_discoverer/export.py#L72) — Tool 8's zone-dict shape (v2 schema source of truth).
- [Source: apps/tooling/tools/auto_roi_discoverer/model.py:19](apps/tooling/tools/auto_roi_discoverer/model.py#L19) — `TARGET_CLASSES = ("lobby", "in_match", "score", "transition")`.
- [Source: apps/tooling/tools/frame_labeler.py:23](apps/tooling/tools/frame_labeler.py#L23) — `MAP_LABELS` canonical order.
- [Source: apps/tooling/config/config.yaml:87-907](apps/tooling/config/config.yaml#L87) — legacy `minimap_identification` block (the hand-merge target, 9.9b's scope).
- [Source: apps/mobile/src/features/video-processing/mapIdentifier.ts:48](apps/mobile/src/features/video-processing/mapIdentifier.ts#L48) — `Object.entries(config.maps)` expecting pHash hex string values; type-narrow target if AC11 audit requires it.
- [Source: apps/mobile/src/features/video-processing/detectionConfig.ts](apps/mobile/src/features/video-processing/detectionConfig.ts) — mobile Zod validator (auto-regenerated post-9.9a).
- [Source: _bmad/bmm/config.yaml](_bmad/bmm/config.yaml) — `user_name: Stephane`, `project_name: Warden_monorepo`, `communication_language: English`, `document_output_language: English`.
- Memory: [[feedback_two_pr_docs_execution]] (Two-PR pattern for code-story execution); [[feedback_ac_checkbox_tighten]] (AC checkbox tighten — `[ ]` for post-merge-dependent ACs); [[project_warden_new_hud_labeler]] (new-HUD labeler initiative status — Stories 9.5/9.6/9.7/9.8 + the future re-fingerprinting cascade now made concrete as 9.9a + 9.9b + 9.10).

## Dev Agent Record

### Agent Model Used

`claude-opus-4-7[1m]`

### Debug Log References

- Pre-implementation survey surfaced 3 premise mismatches (no bundled `map_config.json`; no `MapConfigSchema` consumer; generator requires frame input). Documented under "Scope Adjustment" block above and the dev-story `last_updated` entry in `_bmad-output/sprint-status.yaml`. User-approved scope adjustment (drop AC8/Task 7; demote AC11 to typecheck gate) before code touched.
- AC1 minor scope expansion: extended v1 branch optional field list to include `threshold_hash` (boolean) and `recognition_threshold` (integer ≥0) so the new emit-time validation gate (AC7) doesn't reject existing emit code at `map_config_generator.py:373-379` + `hash_comparator.py:625-632`. These fields were already being emitted unconditionally; reflecting reality in the schema beats forcing a behavioral change.
- Import refactor inside `map_config_generator.py`: switched the long-standing bare `from hash_comparator import consensus_from_hashes` and a newly-added `from frame_labeler import MAP_LABELS` to proper `from tools.X import Y` package-style imports. This enables `tools.map_config_generator` to be imported by `apps/tooling/tests/test_map_config_generator.py` while preserving direct invocation as `python tools/map_config_generator.py` (the file's own `sys.path.insert(0, parent_of_tools)` covers both invocation modes). No runtime behavior change.
- Cross-typecheck failures (web + mobile) verified pre-existing baseline via `git stash` against `main`. Identical error sets in both runs. 9.9a introduces no new typecheck failures.

### Completion Notes List

- **AC1 (schema v2 `oneOf` discriminator)**: `contracts/map-config.schema.json` rewritten to enforce `schema_version` integer enum [1, 2] at top level with two branches keyed by `"const": 1` / `"const": 2`. v1 branch preserves exact current shape + adds `schema_version` as required + extends optional list with `tile_cols`/`threshold_hash`/`recognition_threshold` (already emitted by today's code). v2 branch defines `reference_resolution` + `game_state_zones` (required object with 4 required keys: lobby/in_match/score/transition) + `maps` (patternProperties `^[a-z][a-z0-9_]*$` → `ZoneSpec[]`). `$defs/ZoneSpec` mirrors Tool 8's fragment shape (`name`, `x≥0`, `y≥0`, `width≥1`, `height≥1`, `hsv{h_center 0-360, h_tol 0-180, s/v_center+tol 0-100}`, `min_ratio 0.0-1.0`). `additionalProperties: false` at every object level.
- **AC3 (`_detect_schema_version`)**: pure helper added to `apps/tooling/tools/map_config_generator.py` (and duplicated by-copy to `hash_comparator.py` per AC6). Returns 2 if `game_state_zones` is non-empty OR if `minimap_identification` is the post-9.9b flat `{map_name: [zone_dict, ...]}` shape (detected by `hsv` + `min_ratio` keys on the first list element). Returns 1 for today's `minimap_identification.configs[i].maps[name].zones[j]` legacy shape — verified by 7 test cases.
- **AC4 (v1 emit + `schema_version: 1`, absorbs Story 9.1)**: `run()` now writes `"schema_version": 1` as the first dict key, then the existing v1 fields in their original order. Patch-mode preserves `schema_version` from the existing config; refuses (clean error + `sys.exit(1)`) if `existing_config["schema_version"] == 2`.
- **AC5 (v2 emit path)**: `_build_v2_output(config)` + `_run_v2(config, output_dir)` added. v2 short-circuit at `main()` skips frame loading (frame input is unnecessary for v2 — the output is purely config-driven). Maps iterate in `tools.frame_labeler.MAP_LABELS` canonical order. Legacy zone dicts coerced via `_coerce_v2_zone` (rename `id` → `name`; drop `weight`/`weight_override`). `--images`/`--video` are now optional at the CLI (required only when v1 emit is selected).
- **AC6 (hash_comparator v1-only + v2-refusal)**: `hash_comparator.py:generate_map_config()` writes `schema_version: 1` first; `main()` refuses (clean stderr message + `sys.exit(1)`) when input config triggers `_detect_schema_version() == 2`. Helper duplicated by-copy with a `# duplicated from map_config_generator._detect_schema_version` comment per AC6.
- **AC7 (jsonschema strict validation gate, absorbs Story 9.4)**: `_validate_against_schema(output_dict)` called immediately before `json.dump` in both generators. On `jsonschema.ValidationError`, formats a clean stderr message `Error: map_config validation failed at $[...]: <reason>` + `sys.exit(1)`. File is never written on failure (atomic — verified by `test_v2_emit_refuses_to_write_invalid_dict` + `test_patch_mode_refuses_to_merge_v1_into_v2_file`).
- **AC9 (Zod regen)**: `pnpm --filter @warden/contracts build` ran cleanly; `packages/contracts/src/generated/map-config.ts` regenerated with a `.superRefine`/oneOf runtime validator (json-schema-to-zod doesn't emit `z.discriminatedUnion` for raw `oneOf` JSON Schema, but the runtime validation behavior is equivalent). The regen output lives at a gitignored path (`.gitignore:53` ignores `packages/contracts/src/generated/`) — apps regenerate at every workspace build via the `pnpm --filter @warden/contracts build` workspace task, so committing the output isn't necessary. (Side-effect of the audit: the story spec referenced a `.github/workflows/contracts-codegen-check.yml` CI gate that doesn't exist in the repo — flagged for follow-up but not part of 9.9a's scope.)
- **AC10 (pytest coverage)**: `apps/tooling/tests/test_map_config_generator.py` added — 27 tests, all green. Full tooling suite 131 → 158, all green. `pnpm --filter tooling test` also green.
- **AC11 (cross-typecheck audit, demoted)**: ran both web + mobile typecheck after Zod regen; pre-existing baseline failures only (Stripe API version, Firebase v12 migration backlog, Zod 4 vs react-hook-form). No new regressions from 9.9a.
- **AC12 (no new deps)**: confirmed — `jsonschema>=4.23.0` already in `apps/tooling/pyproject.toml`; no other deps added.
- **AC2/AC8 (bundled-asset regen)**: dropped per Scope Adjustment — no bundled `apps/mobile/assets/map_config.json` exists in the repo today; Story 1.13 (currently `backlog`) is the natural owner and will produce the first bundled v1 asset with `schema_version: 1` already in place using 9.9a's emit path.
- **AC13/AC14 (sprint-status + PR mechanics)**: held `[ ]` per AC-checkbox-tighten + Two-PR conventions. The `review → done` flip ships in the tiny post-merge follow-up PR after the main PR merges.

### File List

**Modified:**
- `contracts/map-config.schema.json` — full rewrite (post Scope Adjustment #2): top-level `schema_version` discriminator + `oneOf` v1/v2 branches. v1 = HUD V1 shape (flattened `minimap_identification` block with `id`/`identification_threshold`/`roi`/`maps.{name}.zones[]`, each zone carrying `weight`+`weight_override`). v2 = HUD V2 shape (`game_state_zones` cascade + flat per-map `ZoneSpec[]`, no `weight` fields). Shared `$defs/Hsv` block. `additionalProperties: false` everywhere.
- `apps/tooling/wardentooling.py` — Tool 3 registration retargeted from `map_config_generator` → `map_config_emitter` with a simplified config-driven flow (no more --images/--video/--preview prompts); Tool 4 (`hash_validator`) entry removed from `_TOOL_MAP`, menu choices, and `_reprompt_source` dispatch; minor comment cleanup ("like Tool 4" reference removed from Tool 7 docstring).
- `_bmad-output/sprint-status.yaml` — flipped `9-9a-schema-v2-and-map-config-generator` `ready-for-dev → in-progress → review → in-progress → review` across both Scope Adjustments; `last_updated` records both passes.
- `_bmad-output/epics-and-stories.md` — pre-existing modification from the create-story split (carried in this PR).

**New:**
- `apps/tooling/tools/map_config_emitter.py` — replacement for the deleted `map_config_generator.py`. Pure config-driven (no frame input). Helpers: `_detect_schema_version` (structural detection: `configs` wrapper → v1; `game_state_zones` or flat `minimap_identification.{name}: [zone_dict]` → v2), `_build_v1_output` + `_coerce_v1_zone` (flattens `configs[0]` wrapper, preserves zone weight fields), `_build_v2_output` + `_coerce_v2_zone` (Tool 8 flat shape, drops `weight`/`weight_override`), `_validate_against_schema` (Draft 2020-12 strict gate with `$[path]: <reason>` stderr format), `emit(config, output_dir)` (top-level pipeline). CLI: `python tools/map_config_emitter.py [-c config.yaml] [-o output_dir]`.
- `apps/tooling/tests/test_map_config_emitter.py` — 31 tests across 6 buckets:
  - `TestDetectSchemaVersion` (7 cases) — covers `configs` wrapper detection, `game_state_zones` detection, flat-minimap detection, empty/None edge cases.
  - `TestBuildV1Output` (4 cases) — flattened shape; preserved weight fields; missing-configs raises ValueError.
  - `TestBuildV2Output` (5 cases) — top-level shape; in_match present when empty; MAP_LABELS canonical iteration order; `id` → `name` coercion; `weight`/`weight_override` dropped.
  - `TestJsonschemaValidationGate` (8 cases) — valid v1/v2 pass; extra fields, missing schema_version, shape/version mismatch, v1 zone missing weight, v2 zone with extra weight, HSV out-of-range all rejected.
  - `TestEmit` (6 cases) — end-to-end v1/v2; detection branches to the right path; atomic failure on schema violation; schema_version first key.
  - `TestLiveConfigSmoke` (1 case) — runs `emit()` against the real `apps/tooling/config/config.yaml` and asserts v1 emit + schema validation pass.
- `packages/contracts/src/generated/map-config.ts` — auto-regenerated via `pnpm --filter @warden/contracts build` (NOT committed — output path is gitignored per `.gitignore:53`; apps regen at every workspace build).
- `_bmad-output/implementation-artifacts/9-9a-schema-v2-and-map-config-generator.md` — story file (pre-existing untracked, finalized in this PR with both Scope Adjustment blocks + Dev Agent Record + File List + Change Log).
- `_bmad-output/implementation-artifacts/1-2-foreground-service-android-config-plugin.md` — pre-existing untracked story file from a prior create-story session (carried in this PR — part of the same uncommitted create-story prework; flagged as out-of-scope-but-bundled in the PR description).

**Deleted (Scope Adjustment #2):**
- `apps/tooling/tools/map_config_generator.py` — replaced by `map_config_emitter.py`. All pHash codepaths removed: `process_frame`, `consensus_from_hashes`, `load_maps_from_images`, `load_maps_from_videos`, `check_collisions`, `merge_hashes`, `run()`'s v1 frame-hashing pipeline, patch mode, `--images`/`--video`/`--preview`/`--patch` CLI flags. ~510 LOC removed.
- `apps/tooling/tools/hash_comparator.py` — ~900 LOC of pHash comparison machinery (per-method/per-resolution/per-hash-size sweep, Hamming distance helpers, collision detection, canvas tiling, threshold helpers, `--write-config`/`--force-method` emit). pHash never shipped to production; deleted entirely.
- `apps/tooling/tools/hash_validator.py` — ~330 LOC; consumed pHash helpers from `hash_comparator.py` and was Tool 4 in wardentooling. pHash-validation purpose dies with the rest of the pHash chain.
- `apps/tooling/tests/test_map_config_generator.py` — replaced by `test_map_config_emitter.py`.

## Change Log

| Date       | Change                                                                                                                       |
|------------|------------------------------------------------------------------------------------------------------------------------------|
| 2026-05-15 | Story created via /bmad-create-story split from 9-9 stub (initial spec at `ready-for-dev`).                                  |
| 2026-05-15 | Scope Adjustment recorded: dropped AC8/Task 7 (bundled-asset regen → folded into Story 1.13); demoted AC11 to typecheck-only gate. User-approved before code touched. |
| 2026-05-15 | Schema v2 oneOf discriminator landed; `_detect_schema_version` + `_build_v2_output` + `_validate_against_schema` helpers added; v1 emit gains `schema_version: 1`; v2 emit branch + hash_comparator v2-refusal + jsonschema strict-validation gate land in both generators; Zod regen committed; 27 new pytest tests (full tooling suite 131 → 158 green). Story flipped `in-progress → review`. |
| 2026-05-15 | **Scope Adjustment #2**: redirected per Stephane — pHash never shipped to production; ROI+HSV is the sole detection method across both HUD versions. Deleted `hash_comparator.py` + `hash_validator.py` + the pHash codepaths in `map_config_generator.py` (replaced by `map_config_emitter.py`, pure config-driven, no frame input). Schema v1 redefined: was pHash; now flattened legacy `minimap_identification` (HUD V1 ROI+HSV shape with weighted zones). Detection rule rewritten to be structural (`configs` wrapper → v1; flat shape or `game_state_zones` → v2). `wardentooling.py` Tool 3 retargeted, Tool 4 removed. Pytest replaced (31 tests; full tooling suite 131 → 162 green; live-config smoke confirms emit against the real `config/config.yaml`). Story flipped `review → in-progress → review`. |
