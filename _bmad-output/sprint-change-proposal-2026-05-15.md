# Sprint Change Proposal — Schema Unification + Tooling Consolidation

**Date:** 2026-05-15
**Author:** Stephane (via `/bmad-correct-course`)
**Triggering context:** Story 9.9a merged (`890fa01 feat: schema v2 evolution + map_config_emitter`). Post-merge, two coupled refactors surfaced: (1) the `oneOf` v1/v2 schema branching is over-engineered for a pre-production project with zero deployed consumers; (2) the `apps/tooling/tools/` directory has accumulated ~12 tools but the actual operator workflow is 6 steps, so the toolchain has drift relative to use.
**Mode:** Batch (full proposal delivered in one pass; user briefed the analysis before invoking the skill).
**Posture:** Pre-production, no backward-compat constraints. Clean cuts over compatibility shims. Toolchain mirrors workflow with no incidental tools.

**Revision note (2026-05-15, mid-approval):** Original draft modeled game-state as a 4-class ROI cascade (`lobby` / `in_match` / `score` / `transition`). User clarified that only **in-match-or-not** needs ROI detection: score-screen is derived from a known timing offset after `in_match` ends, and lobby/transition don't need to be differentiated from each other. Schema collapsed accordingly: `game_state_zones: {4 keys}` → `in_match_detection: Zone[]` + a top-level `score_screen_duration_ms: int`. Tool 9's 4-way game-state classifier collapses to binary. Tool 6 labeler stays unchanged (4-folder labeling still produces useful training data — lobby/score/transition folders all map to `in_match=false` ground truth). Affected sections: Section 1 schema example, Section 2 artifact conflicts (`contracts/map-config.schema.json` row), Story 9.9c target shape + AC1, Story 9.12 modes table, Story 9.13 pipeline stages, Story 9.14 scope.

---

## Section 1 — Issue Summary

### Problem 1: Schema over-engineering

Story 9.9a shipped a JSON Schema with a `oneOf` discriminator on `schema_version`, branching v1 (legacy ROI+HSV with `configs[0]` wrapper + `weight`/`weight_override`) and v2 (Tool 8 flat ROI+HSV with `game_state_zones` cascade). The branch design assumed v1 needed structural preservation for an existing mobile consumer.

**Reality:**
- No `apps/mobile/assets/map_config.json` exists on disk (Story 1.13 still `backlog`).
- No mobile code imports `MapConfigSchema` from `@warden/contracts`. `apps/mobile/src/features/video-processing/mapIdentifier.ts:48` runs against the handwritten `DetectionConfig` type, not the auto-generated Zod.
- The "v1 path" is therefore a phantom. Carrying it costs schema complexity, doubled emit paths in `map_config_emitter.py`, and discriminated-union narrowing in every future consumer.

### Problem 2: Toolchain drift

The user's actual operator workflow has 6 steps. The current `apps/tooling/tools/` directory has 12 files/packages, several of which are dead or duplicative:

**The 6-step workflow:**

| # | Step | Current tool | Target tool |
|---|------|--------------|-------------|
| 1 | Label frames per HUD version | `video_timeline_labeler.py` | **KEEP** |
| 2 | Pick ROI+HSV to differentiate HUD versions | (nothing) | `zone_picker.py` (NEW) |
| 3 | Pick ROI+HSV for in-match-or-not detection | `auto_roi_discoverer/` + `minimap_zone_selector/` | `zone_picker.py` (NEW) |
| 4 | Pick ROI+HSV weighted per-map ID | `auto_roi_discoverer/` + `minimap_zone_selector/` | `zone_picker.py` (NEW) |
| 5 | Test detection on labeled PNGs | `roi_detection_tester.py` | **KEEP + refit** |
| 6 | Test detection on a video end-to-end | (nothing) | `video_test.py` (NEW) |

Score-screen is timing-derived (not ROI-detected) — a known offset after `in_match` ends. Lobby and transition don't need to be differentiated from each other. The unified schema reflects this: one `in_match_detection: Zone[]` block + a top-level `score_screen_duration_ms: int` field.

Plus the emit step: `map_config_emitter.py` assembles + validates the JSON.

**Retire list (9 files/packages; all dead or superseded):**

| File | Reason to retire |
|---|---|
| `auto_roi_discoverer/` | Auto-suggest layer didn't produce good-enough zones in practice. Manual picker wins. Git history preserves the code. |
| `minimap_zone_selector/` | Predecessor of Tool 8; same job. Folds into `zone_picker.py`. |
| `overlay_stack_analyzer.py` | Variance/heatmap signal folds into `zone_picker.py` as an in-tool preprocessing helper. |
| `game_detector.py` | Tool 1 — black-screen detection. Replaced by game-state zones. |
| `black_screen_detector.py` | Same era as `game_detector.py`. Stateless game-state detection supersedes. |
| `bsd_roi_debugger.py` | Debugger for `black_screen_detector.py`; obsolete when target is. |
| `frame_labeler.py` | Tool 2 — frame labeler. Tool 6 (`video_timeline_labeler.py`) supersedes. |
| `warden_analyzer.py` | Tool 5. Story 9.2 (its real-footage AC validation) already cancelled; HUD 2.0 footage breaks its legacy ROIs anyway. |
| `points_state_detector.py` | Legacy; dead. |

### Evidence

- Story 9.9a artifact `_bmad-output/implementation-artifacts/9-9a-schema-v2-and-map-config-generator.md` — Scope Adjustment blocks #1 and #2 document the v1-isn't-a-thing realization mid-flight.
- `git log` shows 9.9a deleted `hash_comparator.py` (~900 LOC of pHash code) once Stephane confirmed pHash was never production. Same pattern applies one level up: 9.9a kept v1 as a branch because the schema design landed before the realization that nothing consumes it.
- Tools 6/7/8/9 (Stories 9.5/9.6/9.7/9.8) shipped sequentially and each successor partially overlaps its predecessor's job. The auto-discoverer (Tool 8) was supposed to replace the manual `minimap_zone_selector` but didn't displace it cleanly; both linger on disk.

---

## Section 2 — Impact Analysis

### Epic Impact

**Epic 9 (Tooling)** — deeply impacted. Charter amended; many existing stories affected.

| Story | Current state | New disposition |
|---|---|---|
| 9.1 — `schema_version: 1` writer | `backlog` (absorbed by 9.9a) | **`cancelled`** — superseded by 9.9c (the unified single shape has only `schema_version: 1`, but the absorption rationale changes from "9.9a covered it" to "9.9c reframes schema_version as config-shape-version, not detection-method-version"). |
| 9.2 — warden_analyzer real-footage validation | `cancelled` | **stays `cancelled`**, warden_analyzer.py retired in 9.11 (this proposal). |
| 9.3 — Reference hash regression | `cancelled` | **stays `cancelled`** (pHash codepath already deleted). |
| 9.4 — jsonschema strict validation | `backlog` (absorbed by 9.9a) | **`cancelled`** — absorbed forward into 9.9c (validation gate persists on unified shape). |
| 9.5–9.8 — Tools 6/7/8/9 | `done` / `review` | **9.6, 9.7 partially retire** in 9.11 (Tool 7's variance signal folds into zone_picker; Tool 8's auto-discover deleted). 9.5 + 9.8 keep their code; 9.8 refit in 9.14 (HUD-version add + 4-way game-state collapse to binary in_match). |
| 9.9 — Re-fingerprint config (split parent) | `cancelled` (split stub) | **stays `cancelled`** — split still valid; sub-stories evolve below. |
| 9.9a — Schema v2 + emitter | `review` (merged via PR `890fa01`) | **stays `review` → flip to `done` in the standard Two-PR follow-up. SUPERSEDED note added** pointing to 9.9c. The merged work is real history, not retroactively rewritten. |
| 9.9b — Tool 8 fragment hand-merge | `backlog` | **REFRAMED, stays `backlog`**: the hand-merge target changes from `config.yaml` → `map_config.json`. The mechanism changes from "manually paste discovered_zones.yaml into config.yaml" to "iteratively run zone_picker → emit → video_test until per-class accuracy thresholds are met." Multi-sprint manual work bucket survives; just the toolchain it uses changes. Renamed: **9.9b — Iterative Zone Population for Shipping Configs**. |
| 9.10 — PRD/architecture editorial pass | `backlog` | **stays `backlog`**, scope expanded slightly: editorial pass now also covers references to `oneOf`/v1/v2 framing introduced briefly in 9.9a-era prose. Still anchored to 9.9b's measured accuracy floors. |
| 9.9c — Schema Unification + Emitter Conformance | NEW | Single-shape schema rewrite; `map_config_emitter.py` retargeted; `jsonschema` validation gate preserved. Supersedes 9.9a's `oneOf` design. |
| 9.11 — Retire Legacy Tooling | NEW | Standalone story. One PR deletes the 9 retired files/packages + their `wardentooling.py` registrations + their `.md` docs + their tests. Atomic cut. |
| 9.12 — Unified Zone Picker | NEW | `tools/zone_picker.py` — manual ROI+HSV picker with 3 modes (HUD-version / game-state / per-map weighted). Folds in `overlay_stack_analyzer`'s variance signal. Reuses `image_inspector/`. |
| 9.13 — Video Detection Tester | NEW | `tools/video_test.py` — consumes emitted `map_config.<hud_version>.json`, runs i-frame extraction → HUD version → game state → map ID → score-screen extraction on a real video. |
| 9.14 — ROI Detection Tester Refit for Unified Schema | NEW | Refit `tools/roi_detection_tester.py`: add HUD-version classifier; collapse the 4-way game-state classifier to binary `in_match`-or-not (matching the schema's `in_match_detection: Zone[]` block); keep the per-map classifier unchanged. Labeler stays as-is (binary collapse happens in ground-truth derivation). |

**Epic 1 (Foundations)** — Story 1.13 affected.

- Story 1.13 (Hybrid `map_config.json` Delivery): bundled-asset shape changes from v1 pHash to unified single-shape, and from one file to potentially N files (one per HUD version) — or one manifest pointing at multiple files. AC1/AC3/AC8 need rewriting. Stays `backlog`; charter unchanged. **Owner of resolving "what does V1 ship as the bundled asset" remains 1.13**, but its source-of-truth-schema reference flips from 9.9a → 9.9c.

**Other epics** — no impact. Mobile consumer rewrite of `mapIdentifier.ts` / `gameDetector.ts` (currently not enumerated in any epic) stays out of this proposal's scope; the unified shape just makes that future rewrite cleaner (no discriminated-union narrowing required).

### Artifact Conflicts

| Artifact | Impact |
|---|---|
| `contracts/map-config.schema.json` | Full rewrite under 9.9c. Drop `oneOf`, drop branch-specific required-field lists, add top-level `hud_version: enum`, add `hud_version_detection: Zone[]`, add `in_match_detection: Zone[]`, add top-level `score_screen_duration_ms: int` (timing offset for score-screen extraction after `in_match` ends), reshape `minimap_identification` to `{ id, identification_threshold, roi, maps: { name: { zones: Zone[] } } }`. Single `Zone` definition: `{ id, x, y, width, height, hsv, min_ratio, weight, weight_override }`. `additionalProperties: false` at every level. Top-level `schema_version` stays (renamed semantically: config-shape version, not detection-method version). |
| `packages/contracts/src/generated/map-config.ts` | Auto-regen via `pnpm --filter @warden/contracts build`. The discriminated-union type collapses to a single object type. CI's `contracts-codegen-check.yml` enforces no drift. |
| `apps/tooling/tools/map_config_emitter.py` | Rewritten under 9.9c (or 9.15 — folded into 9.9c per simplification): single emit path, validates against the new schema. The v1/v2 detection helper deleted along with the branch. |
| `apps/tooling/tools/` (9 retired files) | Deleted in 9.11. |
| `apps/tooling/wardentooling.py` | Registrations for the 9 retired tools removed in 9.11; entries for `zone_picker` + `video_test` added in 9.12 + 9.13 respectively. |
| `apps/tooling/config/config.yaml` | Legacy `minimap_identification` block (lines 87–907) becomes pure legacy reference once zone_picker is the authoritative zone source. Can be deleted in 9.11 or left as historical context. **Decision needed at 9.11 time — defer.** |
| `apps/tooling/tests/` | `test_map_config_emitter.py` (or whatever 9.9a's tests are named) rewritten under 9.9c. Retired tools' tests deleted in 9.11. New tests added per 9.12/9.13/9.14. |
| `apps/mobile/src/features/video-processing/` | No code change in this sweep. Mobile consumer rewrite remains a separate post-V1 story (TBD; not enumerated). The unified shape just simplifies the future rewrite. |
| `_bmad-output/epics-and-stories.md` | Epic 9 charter amendment block; new story stubs for 9.9c/9.11/9.12/9.13/9.14; 9.9a marked SUPERSEDED; 9.9b reframed; 9.10 scope-expanded; 9.1/9.4 flipped backlog→cancelled. Story 1.13's ACs updated. |
| `_bmad-output/sprint-status.yaml` | Status flips per the table above; `last_updated` entry summarizing this correct-course. |
| `_bmad-output/prd.md` | No edits in this proposal; 9.10 owns the editorial pass post-9.9b. |
| `_bmad-output/architecture.md` | Same — 9.10 owns. |
| `_bmad-output/ux-design.md` | No impact. |

### Technical Impact

- **No code is touched by this proposal directly** — it's a planning artifact. The dev work happens in 9.9c, 9.11, 9.12, 9.13, 9.14 stories' PRs.
- **Risk on 9.9c**: rewriting the shipped schema means the regenerated Zod type changes in a non-additive way. No deployed consumers means no runtime breakage, but `pnpm --filter web typecheck` + `pnpm --filter mobile typecheck` must stay green. The 9.9a typecheck audit showed neither app actually imports `MapConfigSchema`, so risk is low.
- **Risk on 9.11**: deleting 9 files in one PR is a large diff. Mitigation: each file's import sites are local to `apps/tooling/` (verified via the `wardentooling.py` registry); no cross-package imports.
- **Sequencing risk**: 9.9c should land before 9.12/9.13/9.14 so the new tools target the right schema. 9.11 is independent — can land first, in parallel, or last.

---

## Section 3 — Recommended Approach

**Selected:** Option 1 — Direct Adjustment within Epic 9 (with one Epic 1 amendment for Story 1.13).

**Rationale:**

- Pre-production, no consumers → no rollback or MVP reduction needed. This is in-flight epic re-scope, not a strategic pivot.
- The work is concrete, bounded, and decomposes cleanly into 5 new sprint-sized stories + 3 amendments. No structural unknowns.
- Doing this *now*, before 9.9b's iterative hand-merge work starts in earnest, saves multi-sprint rework. 9.9b under the old toolchain would have meant manual yaml editing across 14 maps + 4 game-state classes; under the new toolchain it's `zone_picker` runs.
- The Two-PR pattern + AC-checkbox-tighten convention scale to this volume — each new story ships as a single PR + a tiny post-merge follow-up.

**Effort estimate:** ~6 sprints if done sequentially. Likely 3–4 sprints with the parallel-safe ordering below.

**Suggested sequencing:**

1. **9.9c** (schema unification + emitter conformance) — must land first; everything downstream conforms to its shape.
2. **9.11** (tool retirement) — independent of 9.9c on the schema side, but should ideally land *before* 9.12/9.13 so the new tools don't import from anything that's about to be deleted. Can run in parallel with 9.9c.
3. **9.12** (`zone_picker`) — depends on 9.9c (writes zones in the new shape) and 9.11 (uses `image_inspector/`, doesn't import retired modules).
4. **9.14** (Tool 9 HUD-version extension) — depends on 9.9c (new schema has `hud_version_detection`). Can run in parallel with 9.12.
5. **9.13** (`video_test`) — depends on 9.9c (consumes emitted `map_config.<hud>.json`) and ideally 9.12 (so video_test has something real to test against). 9.14 nice-to-have prerequisite (so video_test can use the same HUD-version classifier).

**Risk level:** Low. Pre-production posture eliminates the usual cross-environment hazards; each story is self-contained; the schema diff is large but mechanically driven.

---

## Section 4 — Detailed Change Proposals

### 4.1 New Story Stubs (full specs deferred to `/bmad-create-story` per story)

#### Story 9.9c: Schema Unification + Emitter Conformance (single-shape rewrite)

**Status:** `backlog` → flip to `ready-for-dev` when `/bmad-create-story` runs.

**Spec (summary):**

As **Stephane** (pre-production, no deployed consumers),
I want **`contracts/map-config.schema.json` rewritten as a single unified shape (no `oneOf`, no branches) keyed by `hud_version` for runtime config selection, with `map_config_emitter.py` retargeted to emit that shape and a `jsonschema` strict validation gate preserved end-to-end**,
so that **the schema mirrors the actual detection pipeline (one detection method, one config shape, multiple HUD versions selected at runtime), the toolchain becomes O(1) instead of O(branch_count), and every future zone consumer (zone_picker, video_test, the eventual mobile consumer rewrite) targets one type instead of a discriminated union.**

**Target schema shape:**

```json
{
  "schema_version": 1,
  "reference_resolution": { "width": 1920, "height": 1080 },
  "hud_version": "v1" | "v2",
  "score_screen_duration_ms": 12000,

  "hud_version_detection": [Zone, ...],

  "in_match_detection": [Zone, ...],

  "minimap_identification": {
    "id": "...",
    "identification_threshold": 0.x,
    "roi": { ... },
    "maps": {
      "<map_slug>": { "zones": [Zone, ...] }
    }
  }
}
```

Runtime state machine (informative — not encoded in the schema):

- ROI continuously evaluates `in_match_detection` → flips a binary `in_match: bool`.
- On `in_match` falling edge: wait `score_screen_duration_ms` while extracting/buffering frames as the score-screen window.
- After the score-screen window, runtime is in "not-in-match" (lobby OR transition; not differentiated) until the next `in_match` rising edge.
- HUD-version is detected once per session via `hud_version_detection` → selects which `map_config.<hud>.json` applies if multiple are bundled.
- Map-ID is evaluated on `in_match` frames via `minimap_identification` (weighted).

**Unified Zone shape** (used everywhere a zone appears — no variants):

```json
{
  "id": "string",
  "x": int, "y": int, "width": int, "height": int,
  "hsv": { "h_center": int, "h_tol": int, "s_center": int, "s_tol": int, "v_center": int, "v_tol": int },
  "min_ratio": number,
  "weight": number,
  "weight_override": number | null
}
```

**ACs (skeleton; full ACs at create-story time):**

- [ ] AC1 — `contracts/map-config.schema.json` rewritten: no `oneOf`, single object type. `additionalProperties: false` at every level. Top-level required fields: `schema_version`, `reference_resolution`, `hud_version`, `score_screen_duration_ms`, `hud_version_detection`, `in_match_detection`, `minimap_identification`. `in_match_detection` is `Zone[]` (single block, no inner keys — score-screen is timing-derived, lobby/transition don't need separate ROIs). `score_screen_duration_ms` is `integer >= 0`. One `Zone` definition shared via `$defs`. `schema_version` is `integer enum [1]` (forward-evolution slot; not used for branching).
- [ ] AC2 — `apps/tooling/tools/map_config_emitter.py` retargeted: single emit path (no `_detect_schema_version`, no `_build_v2_output` branch, no v1-coercion logic), reads zone fragments from disk, assembles output dict per the unified shape, runs `jsonschema.validate()` against the new schema, writes to `apps/tooling/output/map_configs/v<hud_version>/map_config.json` (or whatever the new convention chooses at create-story time).
- [ ] AC3 — `jsonschema` strict validation gate preserved: failure → clean stderr error including failing JSON path + non-zero exit + no file write (atomic). The mechanism is identical to 9.9a's `_validate_against_schema` helper.
- [ ] AC4 — `pnpm --filter @warden/contracts build` regenerates `packages/contracts/src/generated/map-config.ts` cleanly. The new Zod type is a single object (no `discriminatedUnion`).
- [ ] AC5 — Cross-workspace typecheck gate: `pnpm --filter web typecheck` + `pnpm --filter mobile typecheck` baseline preserved (no new regressions). The 9.9a baseline-failure set still applies.
- [ ] AC6 — Pytest at `apps/tooling/tests/test_map_config_emitter.py` rewritten: emit succeeds on valid synthetic input; validation rejects extra fields, missing `hud_version_detection`, missing `in_match_detection`, missing `score_screen_duration_ms`, HSV out-of-range, negative `score_screen_duration_ms`, etc. The old v1/v2 test buckets are deleted.
- [ ] AC7 — `_bmad-output/sprint-status.yaml`: `9-9c-schema-unification` flows `ready-for-dev → in-progress → review → done`. 9-1 + 9-4 + 9-9a get their `cancelled`/`superseded` rationales updated per Section 4.2 below.
- [ ] AC8 — Single-PR delivery + Two-PR follow-up. PR title: `feat: unify map_config schema to single shape (Story 9.9c)`. Branch off `main`.

**Dependencies:** 9.9a (done — provides the `map_config_emitter.py` baseline being rewritten).

**Sprint fit:** fits-in-one-sprint. Schema rewrite + emitter rewrite + Zod regen + tests + typecheck audit. ~2 days focused work.

**Anti-patterns to flag:**

- Do NOT keep any `oneOf` / `_detect_schema_version` / branch dispatch in the new emitter. Clean cut.
- Do NOT preserve `v1` ↔ `v2` distinction in `schema_version`. The user's posture: `schema_version: 1` is the config-shape version, not the detection-method version. HUD version selection moves to `hud_version` field.
- Do NOT couple to retired tools (`hash_comparator`, `auto_roi_discoverer`, `minimap_zone_selector`) — by the time 9.9c lands, those may be gone via 9.11.

---

#### Story 9.11: Retire Legacy Tooling

**Status:** `backlog`.

**Spec (summary):**

As **Stephane**,
I want **9 retired tool files/packages deleted in one atomic commit, along with their `wardentooling.py` registrations and `.md` docs**,
so that **`apps/tooling/tools/` mirrors the operator workflow with no incidental tools, dead code, or stale docs.**

**Files to delete:**

1. `apps/tooling/tools/auto_roi_discoverer/` (entire package — 9 modules + sibling `.md`)
2. `apps/tooling/tools/minimap_zone_selector/` (entire package)
3. `apps/tooling/tools/overlay_stack_analyzer.py` + `.md`
4. `apps/tooling/tools/game_detector.py`
5. `apps/tooling/tools/black_screen_detector.py`
6. `apps/tooling/tools/bsd_roi_debugger.py`
7. `apps/tooling/tools/frame_labeler.py`
8. `apps/tooling/tools/warden_analyzer.py`
9. `apps/tooling/tools/points_state_detector.py`

**Plus:**

- `apps/tooling/wardentooling.py`: remove all flow-functions, `_TOOL_MAP` entries, `choices_main` branches, `menu_main` branches, and `_reprompt_source` branches referring to any of the above.
- `apps/tooling/tests/`: delete `test_auto_roi_discoverer.py`, `test_overlay_stack_analyzer.py`, `test_minimap_zone_selector*.py` (if present), `test_warden_analyzer*.py` (if present), `test_frame_labeler*.py` (if present), `test_game_detector*.py` (if present), `test_black_screen_detector*.py` (if present), `test_bsd_roi_debugger*.py` (if present), `test_points_state_detector*.py` (if present). Verify each before deleting.

**ACs (skeleton):**

- [ ] AC1 — All 9 files/packages above are deleted from the working tree. `git ls-files apps/tooling/tools/` shows zero matches against the retire list.
- [ ] AC2 — `apps/tooling/wardentooling.py` has no references (string-search) to any retired module name; the TUI menu no longer offers them.
- [ ] AC3 — Retired tools' tests are deleted; `cd apps/tooling && uv run pytest` is green (current count minus the deleted test count).
- [ ] AC4 — `apps/tooling/tools/map_config_emitter.py` (and any other survivor) has no imports of retired modules (`grep -r "from auto_roi_discoverer" apps/tooling/tools/` returns nothing, etc.). If 9.9c hasn't landed yet, this AC may require minor patches to `map_config_emitter.py` to drop transitive imports — coordinate sequencing.
- [ ] AC5 — `apps/tooling/config/config.yaml` decision: keep the legacy `minimap_identification` block (lines 87–907) as historical reference, OR delete it? **Decision deferred to story creation; recommendation: delete it, since it's unreferenced once 9.9c emitter doesn't read from `config.yaml`.**
- [ ] AC6 — Sprint-status flip; AC7 — Single-PR + Two-PR follow-up. PR title: `chore: retire legacy tooling (Story 9.11)`.

**Dependencies:** none structurally; ideally lands after 9.9c (so `map_config_emitter.py` no longer imports retired helpers) OR before 9.12/9.13/9.14 (so new tools don't accidentally import about-to-die modules). The sequence "9.9c → 9.11 → 9.12/9.14/9.13" is safest.

**Sprint fit:** fits-in-one-sprint. Mechanical deletion + import audit + test cleanup. ~1 day.

---

#### Story 9.12: Unified Zone Picker (`tools/zone_picker.py`)

**Status:** `backlog`.

**Spec (summary):**

As **Stephane**,
I want **a single interactive Tk tool that lets me pick ROI+HSV zones in 3 modes — HUD-version detection, in-match-or-not detection, per-map weighted (14+ maps) — operating on labeled PNGs from `apps/tooling/output/labeled/v<hud_version>/<class>/*.png`, with `overlay_stack_analyzer`'s variance/heatmap signal folded in as an in-tool preprocessing helper**,
so that **workflow steps #2/#3/#4 collapse into one tool, the auto-discover dead-end is permanently abandoned, and the picker writes zone fragments that `map_config_emitter.py` can consume.**

**Modes:**

| Mode | Input (positive class / negative class) | Output target |
|---|---|---|
| HUD-version | Cross-version PNGs (any class from each `v<hud_version>/`) | `hud_version_detection: Zone[]` in the v<hud_version> fragment |
| In-match | Positive: any `labeled/v<hud>/<MAP_LABELS_slug>/`. Negative: `labeled/v<hud>/{lobby,score,transition}/` pooled. | `in_match_detection: Zone[]` |
| Per-map | Per-map PNGs (`labeled/v<hud>/<map_slug>/`) | `minimap_identification.maps.<map_slug>.zones: Zone[]`, with `weight` + `weight_override` per zone for 100%-accurate ID |

**ACs (skeleton):**

- [ ] AC1 — `apps/tooling/tools/zone_picker.py` exists. Single-file or single-package — choose at create-story time based on size estimate.
- [ ] AC2 — Reuses `apps/tooling/tools/image_inspector/` primitives (ImageCanvas + HSVEditor) — no GUI reinvention.
- [ ] AC3 — Reuses `apps/tooling/tools/common/video_player.py` if any frame-stepping is required.
- [ ] AC4 — Three modes selectable at startup (CLI flag or menu prompt). Each mode targets one section of the unified `map_config.<hud_version>.json` shape.
- [ ] AC5 — Folds in `overlay_stack_analyzer.py`'s variance/heatmap signal as an in-tool preprocessing helper (compute mean + stddev + Hue-stability heatmap per labeled class on the fly). NO separate Tool 7 needed.
- [ ] AC6 — Writes zone fragments to a structured location (e.g., `apps/tooling/output/zones/v<hud_version>/{hud_version_detection,in_match_detection,minimap_identification}.json`) that `map_config_emitter.py` consumes. Format conforms to the unified `Zone` shape.
- [ ] AC7 — Per-map mode supports `weight` and `weight_override` editing (sliders/numeric inputs). 100%-accurate ID on labeled data is the bar.
- [ ] AC8 — Pytest for pure logic (zone-fragment serialization, variance helper) — no Tk GUI testing per the Tool 6/8 precedent.
- [ ] AC9 — `apps/tooling/wardentooling.py` registers `zone_picker` as a top-level menu entry.
- [ ] AC10–11 — Sprint-status + Single-PR + Two-PR follow-up.

**Dependencies:** 9.9c (target schema shape); 9.11 (retires the predecessors this tool replaces; if 9.11 lands first, 9.12's imports are clean by construction).

**Sprint fit:** fits-in-one-sprint, possibly two. Estimate at create-story time. Likely 3–5 days focused work given the GUI complexity (Tk modes, HSV sliders, variance preprocessing, per-map weight controls).

---

#### Story 9.13: Video Detection Tester (`tools/video_test.py`)

**Status:** `backlog`.

**Spec (summary):**

As **Stephane**,
I want **a single headless tool that consumes an emitted `map_config.<hud_version>.json` and runs the full detection pipeline against an actual video — i-frame extraction → HUD-version selection → game-state classification per frame → map identification → score-screen extraction**,
so that **workflow step #6 has a tool, end-to-end pipeline confidence is bound on real footage, and any zone-config change can be re-validated end-to-end without writing throwaway scripts.**

**ACs (skeleton):**

- [ ] AC1 — `apps/tooling/tools/video_test.py` exists. Single-file shape (like Tool 7/9 precedent). Pure helpers + thin `main(argv) -> int`.
- [ ] AC2 — CLI: `python tools/video_test.py <path/to/video.mp4> [--config path/to/map_config.json] [--output path/to/results.json]`.
- [ ] AC3 — Pipeline stages (in order, each producing intermediate output for inspection):
  - i-frame extraction via `cv2.VideoCapture` + i-frame stride (configurable; default = 1 i-frame per second equivalent)
  - Once per session: HUD-version classification via `hud_version_detection` zones → selects which `map_config.<hud>.json` applies (if multiple are bundled). Held constant for the rest of the run.
  - For each i-frame: binary `in_match` classification via `in_match_detection` zones (argmax_above_threshold over zone-fire ratio, same mechanism as Tool 9).
  - State machine: on `in_match` rising edge → enter `in_match`; on `in_match` falling edge → enter `score_screen` for `score_screen_duration_ms` (frames in this window are flagged for score-screen extraction); after the score window → `not_in_match` (lobby/transition merged; not differentiated) until next rising edge.
  - For frames inside an `in_match` span: map-ID classification via `minimap_identification` (weighted). Hold the most-confident map-ID across the span as the canonical match label.
- [ ] AC4 — Output `results.json` schema: ordered list of `{frame_idx, timestamp_ms, state}` entries where `state ∈ {in_match, score_screen, not_in_match}`, plus one top-level `hud_version` field and a `matches: [{start_frame, end_frame, map_id, confidence}, ...]` list of in-match spans.
- [ ] AC5 — Reuses helpers from Tool 9 (`roi_detection_tester.py`) wherever possible — the per-frame zone-fire logic is shared. NO reinvention.
- [ ] AC6 — Pytest for pure logic (pipeline stage helpers; ordering; i-frame stride math). Manual smoke test against ≥1 real EVA capture.
- [ ] AC7 — `apps/tooling/wardentooling.py` registers `video_test`.
- [ ] AC8–9 — Sprint-status + Single-PR + Two-PR follow-up.

**Dependencies:** 9.9c (target schema); ideally 9.12 (so video_test has populated zone configs to test against) + 9.14 (so the HUD-version classifier is already exercised on labeled PNGs).

**Sprint fit:** fits-in-one-sprint. ~2–3 days focused work.

---

#### Story 9.14: ROI Detection Tester — Refit for Unified Schema (HUD-Version Add + Game-State Collapse to Binary)

**Status:** `backlog`.

**Spec (summary):**

As **Stephane**,
I want **`apps/tooling/tools/roi_detection_tester.py` (Tool 9) refit for the unified schema: add a new HUD-version classifier, collapse the existing 4-way game-state classifier to a binary `in_match`-or-not classifier (matching the schema's `in_match_detection: Zone[]` block), and keep the per-map ID classifier**,
so that **workflow step #5 covers all three runtime classifiers — HUD-version + binary in_match + per-map ID — on labeled data, and Tool 9's outputs match what the runtime pipeline actually does.**

**ACs (skeleton):**

- [ ] AC1 — Tool 9 has three classifiers: (a) HUD-version (NEW); (b) binary `in_match` / `not_in_match` (REPLACES the existing 4-way `{lobby, in_match, score, transition}` classifier); (c) per-map ID (UNCHANGED).
- [ ] AC2 — HUD-version classifier: ground truth = the `v<hud_version>/` parent directory of each labeled frame. Predicted = result of running the `hud_version_detection` zones.
- [ ] AC3 — Binary `in_match` classifier: ground truth = `true` if the frame's folder is in `MAP_LABELS` (any map slug), `false` otherwise (`lobby`/`score`/`transition` folders). Predicted = `in_match_detection` zones argmax_above_threshold. The labeler stays unchanged (still produces 4-folder structure); the binary collapse happens in Tool 9's ground-truth derivation.
- [ ] AC4 — `report.json` schema rewritten: three classifier sections (`hud_version_classifier`, `in_match_classifier`, `map_id_classifier`), each with per-zone TP/FP/FN/TN + confusion matrix + per-class P/R/F1 + top-line accuracy. The old 4-way `game_state_classifier` section is removed (or renamed to `in_match_classifier` with binary confusion).
- [ ] AC5 — `summary.md` rewritten with three classifier sections in canonical order: HUD-version → in_match → map-ID.
- [ ] AC6 — `frame_predictions.csv` (opt-in) column set: `frame_path`, `ground_truth_hud_version`, `predicted_hud_version`, `ground_truth_in_match`, `predicted_in_match`, `ground_truth_map_id`, `predicted_map_id`, plus per-classifier confidence columns.
- [ ] AC7 — Pytest refit: existing 4-way game-state tests deleted / rewritten as binary; new HUD-version tests added; per-map tests preserved as-is. Test count net change documented in the story closure.
- [ ] AC8 — Empty-zones backward-compat: if `hud_version_detection` or `in_match_detection` is empty in the loaded fragment, the corresponding classifier short-circuits to `unknown` for every frame and the section reports `accuracy 0.000 — zones unpopulated`. Mirrors the Tool 9 precedent.
- [ ] AC9 — `_bmad-output/sprint-status.yaml` flip; AC10 — Single-PR + Two-PR follow-up.

**Dependencies:** 9.9c (new schema defines `hud_version_detection` + `in_match_detection`).

**Sprint fit:** fits-in-one-sprint. ~1–2 days focused work (the binary collapse is straightforward; the HUD-version add is small; the report/summary refit is mechanical).

---

### 4.2 Amendments to Existing Stories

#### Amend Story 1.13 — Hybrid `map_config.json` Delivery

Change set (apply when 1.13 reaches `/bmad-create-story`):

- AC1 rewrite: bundled-asset shape changes from "v1 pHash data + `schema_version: 1`" to "unified single shape per 9.9c; one `map_config.<hud_version>.json` per HUD version (or one manifest pointing at multiple files — decide at create-story time)."
- AC3 rewrite: `contracts/map-config.schema.json` reference flips from "schema_version: integer >= 1 as a required field" to "the unified shape per Story 9.9c."
- AC8 rewrite: `validateDetectionConfig` accepts the unified shape; rejection of unknown shapes still falls back to bundled.
- New AC (or insert): document the multi-HUD-version bundling strategy — one file per HUD version vs. one manifest. Recommendation: **manifest + per-HUD files** (bundles `map_config.json` as `{"versions": ["v1", "v2"], "files": {"v1": "map_config.v1.json", "v2": "map_config.v2.json"}}` + the individual files). Defer final decision to create-story.
- Dependencies block: replace `Epic 9 Story 9.1` with `Epic 9 Story 9.9c`.

#### Amend Story 9.9b — Iterative Zone Population for Shipping Configs (renamed)

Change set:

- Rename: `9.9b — Tool 8 Fragment Hand-Merge + Config Regeneration` → `9.9b — Iterative Zone Population for Shipping Configs`.
- Mechanism rewrite: no more `config.yaml` editing or `discovered_zones.yaml` hand-merge. New mechanism: iteratively run `zone_picker` (9.12) → `map_config_emitter` (9.9c) → `video_test` (9.13) and/or `roi_detection_tester` (9.14) → adjust zones → repeat until per-class accuracy thresholds are met.
- Deliverables unchanged at the goal level: a populated `map_config.<hud_version>.json` per shipping HUD version + documented per-class accuracy floors.
- Dependencies block: replace `9.9a` with `9.9c, 9.12, 9.13, 9.14`. Still multi-sprint. Still post-V1.

#### Amend Story 9.10 — PRD/Architecture Editorial Pass for ROI+HSV Pivot

Change set:

- Scope expansion: in addition to the original editorial targets (`tooling-HASH-001/002`, `mapIdentifier.ts pHash matcher` line, `mobile-AUTO-SLICE-002/003` traceability), also scrub any 9.9a-era prose that references the now-superseded `oneOf` / v1-v2 branching framing. Search targets: `epics-and-stories.md` (the 9.9 stub area + Epic 9 charter amendment), `architecture.md` (any schema-versioning references), `prd.md` (no expected hits).
- Dependencies block: anchored to 9.9b's regenerated configs + measured floors. Still small standalone. Still post-V1.

#### Amend Story 9.9a — mark SUPERSEDED

Change set (in the artifact file `_bmad-output/implementation-artifacts/9-9a-schema-v2-and-map-config-generator.md`):

- Add a new top-of-file block: **Scope Adjustment #3 (2026-05-15, post-merge correct-course): SUPERSEDED by Story 9.9c.** The `oneOf` v1/v2 schema design and the dual-emit-path in `map_config_emitter.py` are unified into a single shape under 9.9c. Reasoning: the v1 branch turned out to be a phantom — no consumer exists. The merged work is real history (`schema_version` field exists; `map_config_emitter.py` exists in the renamed-from-`map_config_generator.py` form; `jsonschema` validation gate works); 9.9c rewrites the schema and the emitter on top of that baseline. ACs in this file remain `[x]`/`[~]`/`[ ]` as merged; the underlying code conformance migrates under 9.9c.
- Status: stays `review` until the standard Two-PR follow-up flips it `done`. Don't conflate this with 9.9c's status.

#### Amend Story 9.1 — flip backlog → cancelled

Rationale update: from "absorbed by 9-9a" to "absorbed by 9-9a + reframed by 9-9c (the unified `schema_version: 1` is now the config-shape version, not the detection-method version; the v1-emit-`schema_version:1` mechanism survives but its semantic anchor changed)."

#### Amend Story 9.4 — flip backlog → cancelled

Rationale update: from "absorbed by 9-9a" to "absorbed by 9-9a + carried forward by 9-9c (the `jsonschema` strict validation gate persists on the unified shape; same mechanism, new target schema)."

---

### 4.3 Charter Amendment (`epics-and-stories.md` Epic 9 section)

Insert a new amendment block at the head of the Epic 9 section, alongside the existing 2026-05-14 amendment:

> **Charter amendment 2026-05-15 (correct-course).** Post-9.9a-merge, two coupled refactors landed via `/bmad-correct-course`: (1) the `oneOf` v1/v2 schema branch is collapsed into a single unified shape under new Story 9.9c (zero deployed consumers made the branch design over-engineered); (2) the toolchain consolidates from ~12 files to 4 + 2 libraries — the operator workflow has 6 steps and the tool inventory now matches it 1:1. New stories: 9.9c (schema unification), 9.11 (retire 9 legacy tool files), 9.12 (`zone_picker`), 9.13 (`video_test`), 9.14 (Tool 9 HUD-version extension). 9.9a marked SUPERSEDED. 9.9b reframed (iterative zone population via the new toolchain). 9.10 scope-expanded. 9.1 + 9.4 flip backlog → cancelled. Full rationale: [`sprint-change-proposal-2026-05-15.md`](sprint-change-proposal-2026-05-15.md).

---

### 4.4 Sprint-Status Diff Summary

| Key | Before | After |
|---|---|---|
| `9-1-schema-version-1-add-to-map-config-writers` | `backlog` | `cancelled` (rationale updated) |
| `9-4-jsonschema-strict-validation-against-map-config-schema` | `backlog` | `cancelled` (rationale updated) |
| `9-9a-schema-v2-and-map-config-generator` | `review` | `review` + SUPERSEDED note (Two-PR follow-up still flips to `done` later) |
| `9-9b-tool-8-fragment-hand-merge-and-config-regen` | `backlog` | `backlog` + renamed + mechanism rewrite note |
| `9-10-prd-architecture-editorial-pass-roi-hsv-pivot` | `backlog` | `backlog` + scope-expansion note |
| `9-9c-schema-unification` | — | NEW, `backlog` |
| `9-11-retire-legacy-tooling` | — | NEW, `backlog` |
| `9-12-unified-zone-picker` | — | NEW, `backlog` |
| `9-13-video-detection-tester` | — | NEW, `backlog` |
| `9-14-roi-detection-tester-refit-for-unified-schema` | — | NEW, `backlog` |
| `1-13-hybrid-map-config-delivery-schema-version-1` | `backlog` | `backlog` + AC-amendment note (anchor flips 9.9a→9.9c) |

Epic 9 stays `in-progress`. No epic flips.

---

## Section 5 — Implementation Handoff

**Scope classification:** **Moderate** — backlog reorganization across one epic (+1 cross-epic Story 1.13 amendment) plus 5 new story stubs. No code touched by the correct-course itself; all dev work happens in the new stories' own dev cycles.

**Handoff recipients:**

- **Product Owner / Developer (Stephane, self)** — owns:
  - Approving this proposal.
  - Running `/bmad-create-story` on each new stub (9.9c, 9.11, 9.12, 9.13, 9.14) in the recommended sequence as sprint capacity allows. The brief at the top of this proposal is sufficient seed material for the create-story runs.
  - Running `/bmad-dev-story` on each one when its create-story has produced the full spec.
- **Developer agent (per story dev cycle)** — owns the implementation, tests, Zod regen audit, and Two-PR mechanics per story.

**Editorial admin (this correct-course's own deliverable):**

- This document (`_bmad-output/sprint-change-proposal-2026-05-15.md`).
- Edits to `_bmad-output/sprint-status.yaml` per Section 4.4.
- Edits to `_bmad-output/epics-and-stories.md`: Epic 9 charter amendment block; new stub entries for 9.9c/9.11/9.12/9.13/9.14; SUPERSEDED note on 9.9a; rename + mechanism rewrite on 9.9b; scope-expansion note on 9.10; status flips on 9.1/9.4; AC-amendment note on 1.13.
- Memory updates: extend `memory/project_warden_new_hud_labeler.md` with the consolidation + the new tool names. No other memory touches.

**Success criteria:**

- Sprint Change Proposal landed at `_bmad-output/sprint-change-proposal-2026-05-15.md`. ✓ (this file).
- `_bmad-output/sprint-status.yaml` and `_bmad-output/epics-and-stories.md` reflect the new structure.
- 5 new stories are creatable via `/bmad-create-story` against the new stubs without further correct-course intervention.
- Existing in-flight work (Story 1.2 `ready-for-dev`, Stories 9.5/9.7/9.8 post-merge follow-ups still pending the original Two-PR pattern) is not disturbed.

**Next steps after approval:**

1. Apply the edits in Section 4.4 to `sprint-status.yaml`.
2. Apply the edits in Section 4.3 + the per-story amendments in Section 4.2 to `epics-and-stories.md`.
3. Add the SUPERSEDED note to the 9.9a artifact file.
4. Update memory file `memory/project_warden_new_hud_labeler.md`.
5. Optional: kick off `/bmad-create-story` on 9.9c (the unblocker for everything downstream).
