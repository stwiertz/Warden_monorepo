# Story 9.12: Unified Zone Picker

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane** (operator + sole developer, pre-production, no deployed consumers),
I want **a single interactive Tk tool — `apps/tooling/tools/zone_picker/` — that picks ROI+HSV zones in 3 modes (HUD-version detection, binary in-match detection, per-map weighted ID) operating on the labeled PNG dataset, with `overlay_stack_analyzer`'s variance/heatmap signal folded in as an in-tool preprocessing helper, writing the four zone fragments `map_config_emitter.py` consumes**,
so that **workflow steps #2/#3/#4 collapse into one tool, the auto-discover dead-end is permanently abandoned, and the iterative zone-population work in 9.9b becomes a `zone_picker → emit → test` loop instead of hand-editing YAML.**

## Acceptance Criteria

> Convention: every AC below is `[ ]`. Post-merge / decision-pending ACs are tagged **[HELD]** per [[feedback_ac_checkbox_tighten]] — do not pre-check them.

- [x] **AC1 — Tool exists as a package.** `apps/tooling/tools/zone_picker/` is a Python package (NOT a single file). Decision rationale recorded in Dev Notes → "Single-file vs package decision". Minimum module split: `__init__.py`, `__main__.py` (thin CLI: `def main(argv: list[str] | None = None) -> int`), `app.py` (Tk shell), `modes.py` (the 3 mode panels), `variance.py` (pure-logic preprocessing helper — **Tk-free**), `fragments.py` (pure-logic fragment load/merge/serialize — **Tk-free**). Pure logic MUST be importable without a display so AC8 holds.
- [x] **AC2 — Reuses surviving GUI primitives; no GUI reinvention.** Reuses `tools.image_inspector.canvas.ImageCanvas` (zoom/pan PIL display) and `tools.image_inspector.modes.ROIMode` (drag-select rect in 1920×1080 reference space) + `tools.image_inspector.modes.HSVFilterMode` (HSV range picker with live overlay preview). **There is NO `HSVEditor` class** — it died with the retired `minimap_zone_selector` package (9.11). Do not hunt for it; do not reinvent a canvas or an HSV range widget. If `HSVFilterMode`/`ROIMode` cannot be embedded as-is (they are written for the standalone `InspectorApp`), wrap/adapt them — do not fork their pixel-mask or coordinate math.
- [x] **AC3 — PNG-sequence navigation is in-tool; `VideoPlayer` is correctly N/A.** Input is labeled **PNG sequences** (`apps/tooling/output/labeled/v<hud_version>/<class>/*.png`), not video. `tools.common.video_player.VideoPlayer` is a video-file widget and does **not** apply here — record this as a deliberate verified-negative in Completion Notes (do NOT shoehorn VideoPlayer in). Prev/next stepping over a class's sorted PNG list is implemented in-tool; PNG enumeration MUST use the same sorted `(class, file)` order as `tools.roi_detection_tester.iter_labeled_frames` so the picker and the downstream Tool-9 validator see frames in the same order (mirror the order; do not import Tool 9 to get it).
- [x] **AC4 — Three selectable modes, each writing its declared fragment target.**

  | Mode | Input | Fragment target |
  |---|---|---|
  | HUD-version | Cross-version PNGs: any class from each `labeled/v<hud_version>/` | `hud_version_detection.json` → `Zone[]` |
  | In-match | Positive: pooled `labeled/v<hud>/<MAP_LABELS slug>/`. Negative: pooled `labeled/v<hud>/{lobby,score,transition}/` | `in_match_detection.json` → `Zone[]` |
  | Per-map | `labeled/v<hud>/<map_slug>/` for one of the 14 `MAP_LABELS` | `minimap_identification.json` → `maps.<slug>.zones: Zone[]` |

- [x] **AC5 — Variance/heatmap preprocessing folded in (no separate Tool 7).** Per selected class, the tool computes on the fly (single pass, frames already loaded): per-pixel **mean** (BGR), **stddev** (BGR, `clip(0,255)→uint8` — NOT min-max normalized), and a **Hue-stability** view. The S+V-only false-colour heatmap (`COLORMAP_JET` over min-max-normalized `std_hsv_lin[...,1:].mean(axis=2)` — Hue excluded by design) is displayable as a canvas overlay/toggle. Algorithm is **ported verbatim** from the recovered `overlay_stack_analyzer.py` (Welford + circular-Hue accumulators — see Dev Notes → "Recovered variance algorithm"). Do NOT invent a new stddev metric; do NOT linear-stddev the Hue channel.
- [x] **AC6 — Band auto-seed from a picked ROI.** After the operator drags an ROI, the tool proposes an `HsvBand` via the recovered `derive_band_for_rect` math (circular-Hue mean/std + ordinary S/V, quadrature-combine across-pixel spread + across-frame temporal stddev, `tol_k = 1.5`, floors `_MIN_H_TOL=10` user°, `_MIN_SV_TOL=5`). The operator can then adjust via the HSV editor. Seeding is a starting point, not a final answer.
- [x] **AC7 — In-tool fire feedback (fast loop, not the gate).** For the active mode, the tool shows the live per-zone fire ratio via `tools.common.zones.band_inrange_ratio` on the current class's mean image (and, for per-map mode, the aggregate weighted score vs `identification_threshold`). The authoritative accuracy gate is Tool 9 (9.14) / `video_test` (9.13) downstream — keep the in-tool readout to a fire-ratio / aggregate-score panel; do **not** rebuild confusion matrices here (scope guard against the two-sprint risk).
- [x] **AC8 — Per-map mode supports `weight` + `weight_override` editing.** Numeric inputs/sliders for per-zone `weight` (number ≥ 0) and `weight_override` (number ≥ 0 **or** `null` — NOT a boolean; the unified schema rejects booleans). 100%-accurate per-map ID on the labeled set is the operator's bar, supported by AC7's aggregate readout.
- [x] **AC9 — Fragment write is merge-safe (anti-clobber).** On startup the tool loads any existing fragments in the target `--zones-dir`; on save it writes **all four** files back so a per-map run never wipes `in_match_detection.json` etc. Untouched fragments are preserved verbatim; never-yet-populated fragments are scaffolded schema-valid-empty (`[]` for the two arrays; `{id, identification_threshold, roi, maps:{}}` for minimap; `manifest.json` from the operator prompt). Zone `id`s are stable and meaningful (e.g. `hud_z00`, `inmatch_z00`, `<slug>_z00`); `maps` is written in `MAP_LABELS` order (the emitter preserves insertion order — the picker owns stable ordering).
- [x] **AC10 — Emitter round-trip green.** Fragments written by the tool pass `python apps/tooling/tools/map_config_emitter.py --zones-dir apps/tooling/output/zones/v<hud_version>` end-to-end (jsonschema gate green, `map_config.<hud_version>.json` emitted). This is the real contract test — the picker's output is only correct if the unchanged emitter accepts it.
- [x] **AC11 — Pytest for pure logic only; no Tk in tests.** `apps/tooling/tests/test_zone_picker.py` covers `fragments.py` (load existing / merge-not-clobber / schema-valid-empty scaffold / stable id + MAP_LABELS ordering / round-trips through `map_config_emitter._load_fragments` + `_assemble_output` + `_validate_against_schema`) and `variance.py` (Welford mean/stddev correctness on a synthetic stack; circular-Hue wrap correctness — e.g. hues {179,0} → near-zero circular std, not ~90). NO Tk/GUI instantiation in tests (Tool 6/8/9 precedent; `conftest.py` is a sys.path shim only — no fixtures). Synthetic `tmp_path` data only — no real dataset/video/`config.yaml`.
- [x] **AC12 — `wardentooling.py` registers the tool.** New top-level menu entry following the `flow_tool6`/`flow_tool9` template: a `flow_zone_picker()` collecting `--hud-version`, `--labeled-dir`, `--zones-dir`, a `_TOOL_MAP` entry, a `choices_main` entry, a `menu_main` branch, and a `_reprompt_source` branch. Label house-style is `Tool N — …`; the next free number is **10** (Tools 7/8 gaps are intentional per 9.11 — do not renumber Tool 9). Package invocation: `python -m tools.zone_picker …` (mirror `image_inspector`'s `__main__.py` pattern; the existing `run_tool()` arg-list shape in `wardentooling.py` may need a `-m`-aware branch — note any adaptation in Completion Notes).
- [ ] **AC13 [HELD]** — Test suite green: `cd apps/tooling && uv run pytest -q` passes at `108 + <new test count>`; `pnpm --filter tooling test` matches. No regression to the 108 baseline (Story 9.11 post-merge). `python -m tools.zone_picker --help` and `python wardentooling.py` (menu renders the new entry, no exception) smoke clean.
- [ ] **AC14 [HELD]** — `_bmad-output/sprint-status.yaml`: `9-12-unified-zone-picker` flows `ready-for-dev → in-progress → review → done`; `last_updated` updated. epic-9 stays `in-progress`.
- [ ] **AC15 [HELD]** — Single-PR delivery + Two-PR follow-up per [[feedback_two_pr_docs_execution]] + 9.9c/9.11 precedent. `gh` is unauthenticatable non-interactively → deliver via local `git merge --no-ff story-9-12-unified-zone-picker → main`; the `review → done` flip + post-merge box closures land via a second `--no-ff` follow-up branch (`story-9-12-postmerge`). Main PR/commit title: `feat: unified zone picker (Story 9.12)`.

## Tasks / Subtasks

- [x] **Task 1: Pre-flight + dependency gate (AC: 10, 13)**
  - [x] Confirm 9.9c `done` (`9b9d4af`) and 9.11 `done` (`aca0906`) are on `main` — schema + emitter + `tools/common/` are the stable contract surface. `git log --oneline -3`.
  - [x] Record baseline: `cd apps/tooling && uv run pytest -q` → **108 passed** (the 9.11 post-merge baseline). Pin the number for AC13's delta.
  - [x] Read the live contract surface, do not trust this story's quotes blindly: `contracts/map-config.schema.json` (`$defs.Zone`, `$defs.Hsv`, `$defs.Rect`, `$defs.MapEntry`, top-level required), `apps/tooling/tools/map_config_emitter.py` (`_FRAGMENT_FILES`, `_load_fragments`, `_assemble_output`), `apps/tooling/tests/test_map_config_emitter.py` (`_make_zone`/`_make_manifest`/`_make_minimap`/`_write_fragments` — the canonical fragment shape).
- [x] **Task 2: Package scaffold + pure-logic core (AC: 1, 9, 11)**
  - [x] Create `apps/tooling/tools/zone_picker/{__init__,__main__,app,modes,variance,fragments}.py`.
  - [x] `fragments.py` (Tk-free): `load_existing(zones_dir) -> dict` (tolerates missing files → scaffold); `scaffold_empty(manifest) -> dict`; `set_zone_list(fragments, target, zones)`; `set_map_zones(fragments, slug, zones)`; `write_all(zones_dir, fragments)` (writes all 4 JSON files, `indent=2`, `encoding="utf-8"`, `maps` in `MAP_LABELS` order, stable zone ids). A Zone serializer producing exactly the 9 schema keys (`id,x,y,width,height,hsv{6},min_ratio,weight,weight_override`) from a `(Rect, HsvBand, weight, weight_override)` tuple.
  - [x] `__main__.py`: argparse `--hud-version {v1,v2}` (required), `--labeled-dir` (default `tools.common.labeled_dataset.default_labeled_dir()`), `--zones-dir` (default `apps/tooling/output/zones/v<hud_version>/`), `--mode {hud,in_match,per_map}` optional; `main(argv) -> int`; non-zero exit on bad args before any Tk import.
- [x] **Task 3: Variance preprocessing helper (AC: 5, 6, 11)**
  - [x] `variance.py` (Tk-free): port `_welford_init/update/finalize`, `_circ_hue_init/update/finalize`, `_normalize_uint8`, the per-frame fold loop, `most_stable_hsv`/`stability_percentiles`, and `derive_band_for_rect` (+ `circular_mean_cv`/`circular_std_cv`) **verbatim** from the recovered `overlay_stack_analyzer.py` / `auto_roi_discoverer` blobs in Dev Notes. Single pass (frames loaded once per class — drop the original two-pass re-read).
  - [x] Expose `class_stats(frames: list[np.ndarray]) -> ClassStats` returning `mean_bgr, stddev_bgr, mean_hsv, std_hsv` (Hue channels = circular results) + `heatmap_bgr` (S+V JET) + `derive_band(rect) -> HsvBand`.
- [x] **Task 4: Tk app shell + mode router (AC: 1, 2, 3, 4)**
  - [x] `app.py`: top-level window; mode selector (radio/menu for HUD-version / In-match / Per-map); class/map selector; embed `ImageCanvas`; prev/next PNG stepper over the active class's sorted PNG list (sorted `(class,file)` mirroring `iter_labeled_frames`); mean/stddev/heatmap/raw toggle.
  - [x] `modes.py`: three panel controllers. Each declares its input pooling (per AC4 table) + its fragment target. Reuse `ROIMode` for rect drag (1920×1080 ref space) and `HSVFilterMode` for HSV band preview; adapt their `InspectorApp` coupling without forking their mask/coordinate math.
- [x] **Task 5: Band editing + fire feedback + per-map weights (AC: 6, 7, 8)**
  - [x] On ROI commit → call `variance.derive_band(rect)` → populate the HSV editor with the seeded band (user space H 0–360 / S,V 0–100; tol h 0–180 / s,v 0–100).
  - [x] Live fire readout: `tools.common.zones.band_inrange_ratio(band, rect, mean_bgr)` for the active class; per-map mode adds the aggregate weighted score vs `identification_threshold`. Reuse `band_inrange_ratio`, `hsv_user_to_cv`, `tol_h_user_to_cv`, `tol_sv_user_to_cv` from `tools.common.zones` — zero reimplementation of the hue-wrap math.
  - [x] Per-map: per-zone `weight` (≥0) + `weight_override` (≥0 or `null`) numeric controls.
- [x] **Task 6: Merge-safe save + emitter round-trip (AC: 9, 10)**
  - [x] Save: `fragments.load_existing(zones_dir)` → mutate only the active mode's target → `fragments.write_all`. Prompt once for `manifest.json` fields the picker can't infer (`hud_version` from `--hud-version`; `score_screen_duration_ms`; `reference_resolution` default `{1920,1080}` = `ROIMode.REF_W/REF_H`).
  - [x] Round-trip: after save, run `map_config_emitter` on the zones-dir (subprocess or import `emit`); surface the jsonschema error verbatim on failure. Manual verification step documented in Completion Notes.
- [x] **Task 7: wardentooling registration + pure-logic tests (AC: 11, 12, 13)**
  - [x] Add `flow_zone_picker()`, `_TOOL_MAP`, `choices_main`, `menu_main`, `_reprompt_source` entries (template = `flow_tool6`/`flow_tool9`). Verify `python -c "import wardentooling"` clean and the TUI renders the new entry.
  - [x] `apps/tooling/tests/test_zone_picker.py`: pure-logic only (AC11 list). `cd apps/tooling && uv run pytest -q` green at `108 + N`; `pnpm --filter tooling test` matches; `python -m tools.zone_picker --help` clean.
- [ ] **Task 8: Story closure + PR + sprint-status (AC: 13, 14, 15)** **[HELD]**
  - [ ] Flip ACs/Tasks `[x]`; Status → `done` via Two-PR follow-up. Local `--no-ff` delivery; second `--no-ff` follow-up for `review → done` + post-merge boxes. Sprint-status lifecycle flips. epic-9 stays `in-progress`.

## Dev Notes

### Strategic context (read this first)

- **This is a GUI tool, but its testable contract is the four JSON fragments**, consumed by the *unchanged* `map_config_emitter.py`. The emitter is the validation gate (it runs `jsonschema.validate()` against `contracts/map-config.schema.json`). The picker is correct iff the emitter accepts its output (AC10). Do **not** import-and-monkeypatch the emitter; treat it as a black-box contract.
- **Downstream**: 9.9b (Iterative Zone Population) is the operator using this tool in a `zone_picker → emit → video_test/Tool9 → adjust → repeat` loop. 9.13/9.14 are the test tools. 9.12 unblocks the 9.9b dep chain alongside 9.13/9.14.
- **Pre-production posture**: no backward-compat constraints; no consumers. Clean implementation over shims.

### Single-file vs package decision (AC1) — DECIDED: package

Spec said "decide at create-story by size." **Package** (`tools/zone_picker/`), because: 3 distinct Tk mode panels + variance/Welford preprocessing + band auto-seed + merge-safe fragment serializer + Tk shell + reused-primitive adapters ≈ 900–1500 LOC, and AC11 forbids Tk in tests — a package cleanly isolates `variance.py` + `fragments.py` (pure, Tk-free, unit-tested) from `app.py`/`modes.py` (GUI). `image_inspector/` is the in-repo precedent for a Tk tool as a package with `__main__.py`. (`video_timeline_labeler.py` is single-file but is one screen with no pure-logic/GUI split pressure — not the right precedent here.)

### Reuse map (anti-reinvention — exact symbols)

| Need | Reuse (exact) | Path |
|---|---|---|
| Zoom/pan image canvas | `ImageCanvas` | `tools/image_inspector/canvas.py:7` |
| Drag-select rect (1920×1080 ref) | `ROIMode` (`REF_W,REF_H=1920,1080`) | `tools/image_inspector/modes.py:234` |
| HSV range pick + overlay preview | `HSVFilterMode` | `tools/image_inspector/modes.py:79` |
| Rect / HSV band model | `Rect`, `HsvBand` | `tools/common/zones.py` |
| Zone-fire test (hue-wrap `cv2.inRange`) | `band_inrange_ratio` | `tools/common/zones.py` |
| User↔CV HSV scale | `hsv_user_to_cv`, `tol_h_user_to_cv`, `tol_sv_user_to_cv` | `tools/common/zones.py` |
| Map slugs / display names | `MAP_LABELS`, `LABEL_DISPLAY` | `tools/common/labels.py` |
| Non-map class names | `TARGET_CLASSES = ("lobby","in_match","score","transition")` | `tools/common/zones.py` |
| Labeled-dir root | `default_labeled_dir()` | `tools/common/labeled_dataset.py` |
| Sorted PNG iteration order (mirror, don't import) | `iter_labeled_frames` order: sorted `(class, file)` | `tools/roi_detection_tester.py` |

**Disasters to prevent:**
- **`HSVEditor` does not exist.** It was in the retired `minimap_zone_selector` (deleted by 9.11, commit `0c1c656`). The spec's AC2 wording ("ImageCanvas + HSVEditor") is stale — corrected in AC2. Use `HSVFilterMode`.
- **`VideoPlayer` is wrong here.** It is a *video-file* widget; input is PNG sequences. Verified-negative — don't force it (AC3).
- **`config.yaml` is gone.** Its legacy `minimap_identification` block was deleted by 9.11 (commit `c232924`). The picker reads labeled PNGs and writes `output/zones/` fragments — it never touches `config.yaml`. There is no `config.yaml` zone source anymore.
- **Don't import retired modules.** `auto_roi_discoverer/`, `minimap_zone_selector/`, `overlay_stack_analyzer.py`, `frame_labeler.py`, `game_detector.py` etc. are deleted. Their useful math is *ported into `variance.py`*, not imported.
- **Don't reimplement `band_inrange_ratio`.** The hue-wrap three-case split (full-circle / wrap `bitwise_or` / normal) lives in `tools/common/zones.py`. Centers convert via `hsv_user_to_cv` (`%180`); tolerances via `tol_h_user_to_cv` (clamped `[0,90]`, **never modded**). Confusing the two silently collapses wide bands.

### The exact contract — fragment files (verbatim from `map_config_emitter.py`)

Emitter reads exactly 4 files from `--zones-dir` (`_FRAGMENT_FILES = ("manifest","hud_version_detection","in_match_detection","minimap_identification")`), each `<name>.json`, `encoding="utf-8-sig"`:

- `manifest.json` → `{ "hud_version": "v1"|"v2", "score_screen_duration_ms": int≥0, "reference_resolution": {"width": int≥1, "height": int≥1} }`. Operator-supplied (the picker cannot infer these from PNGs). `reference_resolution` default `{1920,1080}`.
- `hud_version_detection.json` → JSON array of Zone (empty `[]` is schema-valid).
- `in_match_detection.json` → JSON array of Zone (empty `[]` valid).
- `minimap_identification.json` → `{ "id": str≥1 (use "test"), "identification_threshold": number∈[0,1], "roi": {"name": str≥1, "x":int≥0,"y":int≥0,"width":int≥1,"height":int≥1}, "maps": { "<slug>": {"zones":[Zone,...]} } }`. `maps` keys MUST match `^[a-z][a-z0-9_]*$` (all 14 `MAP_LABELS` comply). Empty `zones:[]` per map is valid (not-yet-fingerprinted).

**Zone object — exactly these 9 keys, `additionalProperties:false`, all required:**
```json
{ "id": "str≥1", "x": int≥0, "y": int≥0, "width": int≥1, "height": int≥1,
  "hsv": { "h_center":0-360,"h_tol":0-180,"s_center":0-100,"s_tol":0-100,"v_center":0-100,"v_tol":0-100 },
  "min_ratio": number∈[0,1], "weight": number≥0, "weight_override": number≥0 | null }
```
HSV is **user space** (NOT OpenCV). `weight_override` is `number|null` — **never boolean** (pre-9.9c boolean shape is explicitly rejected by the schema and a test). `HsvBand.hsv_dict()` already emits the 6-key `hsv` sub-dict. `_assemble_output` does **no coercion** — the picker must write the final shape exactly; the jsonschema gate is the only enforcement point and refuses atomically (no partial file on failure).

`map_config_emitter` writes `apps/tooling/output/map_configs/map_config.<hud_version>.json` (filename from `manifest.hud_version`). Default zones-dir convention: `apps/tooling/output/zones/v<hud_version>/`. Default labeled input: `apps/tooling/output/labeled/v<hud_version>/<class>/*.png`.

### Recovered variance algorithm (port verbatim into `variance.py`)

From `overlay_stack_analyzer.py` @ commit `ba6b326` (last form before 9.11 deletion `0c1c656`):

```python
_HUE_CV_TO_RAD = 2.0 * np.pi / 180.0

def _welford_init(shape):  return (0, np.zeros(shape, np.float64), np.zeros(shape, np.float64))
def _welford_update(state, x):
    n, mean, m2 = state; n += 1
    delta = x - mean; mean = mean + delta / n; delta2 = x - mean
    return (n, mean, m2 + delta * delta2)
def _welford_finalize(state):
    n, mean, m2 = state
    if n == 0: raise ValueError("count 0")
    return mean, np.sqrt(np.maximum(m2 / n, 0.0))   # population stddev

def _circ_hue_init(shape): return (0, np.zeros(shape, np.float64), np.zeros(shape, np.float64))
def _circ_hue_update(state, hue_cv):
    n, s, c = state
    a = np.asarray(hue_cv, np.float64) * _HUE_CV_TO_RAD
    return (n + 1, s + np.sin(a), c + np.cos(a))
def _circ_hue_finalize(state):
    n, s, c = state
    if n == 0: raise ValueError("count 0")
    ms, mc = s / n, c / n
    R = np.sqrt(ms**2 + mc**2)
    mean_cv = ((np.degrees(np.arctan2(ms, mc)) % 360.0) / 2.0) % 180.0
    R_cl = np.where(R >= 1.0 - 1e-9, 1.0, np.maximum(R, 1e-9))
    inner = np.maximum(-2.0 * np.log(R_cl), 0.0)
    std_cv = np.clip(np.degrees(np.sqrt(inner)) / 2.0, 0.0, 90.0)
    return mean_cv, std_cv
```
Per-class fold (single pass — frames already in memory): for each frame `f`: `bgr=_welford_update(bgr, f.astype(f64))`; `hsv=cv2.cvtColor(f,COLOR_BGR2HSV)`; `hsv_lin=_welford_update(hsv_lin, hsv.astype(f64))`; `hue=_circ_hue_update(hue, hsv[:,:,0])`. Finalize → `mean_hsv[:,:,0]=hue_mean_cv`, `std_hsv[:,:,0]=hue_std_cv` (channels 1/2 = linear S/V). Heatmap = `cv2.applyColorMap(_normalize_uint8(std_hsv_lin[...,1:].mean(axis=2)), cv2.COLORMAP_JET)` (S+V only — Hue excluded). `stddev.png` view = `clip(stddev_bgr,0,255).astype(uint8)` (NOT normalized). Dark stddev = stable HUD chrome = ROI candidate.

Band auto-seed (port from `auto_roi_discoverer/discoverer.py` @ `0c1c656^`): `derive_band_for_rect(rect, mean_hsv, std_hsv, tol_k=1.5)` — Hue via `circular_mean_cv`/`circular_std_cv`, across-pixel spread ⊕ across-frame temporal stddev in quadrature (`math.hypot`), S/V via plain mean/std, scale user-space, floors `_MIN_H_TOL=10`, `_MIN_SV_TOL=5`. Full recovered source is in the agent reconstruction recorded in the create-story analysis — re-fetch with `git show 0c1c656^:apps/tooling/tools/auto_roi_discoverer/discoverer.py` if needed; `git show ba6b326:apps/tooling/tools/overlay_stack_analyzer.py` for the full Tool 7 source.

### Library / framework requirements

`apps/tooling/pyproject.toml`: `requires-python = ">=3.11"`; deps `opencv-python>=4.8,<5`, `numpy>=1.24,<2`, `pyyaml>=6.0,<7`, `jsonschema>=4.23.0`, `questionary>=2.0,<3`; dev `pytest>=8.0`. **No new dependencies.** `tkinter` is stdlib (not in pyproject — fine, image_inspector already relies on it). PIL/Pillow is used by `image_inspector` (transitively present) — reuse via `ImageCanvas`; do not add Pillow to pyproject unless an import audit shows it genuinely missing (note in Completion Notes if so). Test runner: `cd apps/tooling && uv run pytest`; cross-workspace `pnpm --filter tooling test` from repo root. No lint gate exists. `conftest.py` is a sys.path shim with no fixtures.

### Previous-story intelligence (9.11 / 9.9c)

- **9.11 (`aca0906`, done):** relocated shared primitives to `tools/common/{labels,zones,labeled_dataset,video_player}.py`; deleted the 9 retired tools incl. `overlay_stack_analyzer.py` + `auto_roi_discoverer/` + `minimap_zone_selector/`; deleted `config.yaml`'s `minimap_identification` block; pytest baseline now **108**. wardentooling kept the Tool 7/8 numbering gap (Tool 9 not renumbered) — follow that house style; next free number is **10**. `run_tool()` arg-list shape + `_TOOL_MAP`/`_reprompt_source` are the registration touchpoints.
- **9.9c (`9b9d4af`, done):** rewrote `contracts/map-config.schema.json` to the single unified shape and retargeted `map_config_emitter.py` to `--zones-dir` fragment input + `_assemble_output` + preserved `_validate_against_schema` gate. `test_map_config_emitter.py` is the canonical fragment-shape reference (`_make_zone`/`_make_manifest`/`_make_minimap`/`_write_fragments`). `hud_version` enum is `["v1","v2"]` (string, NOT "v2.0"); `schema_version` is fixed `enum:[1]`.
- **Delivery pattern (both):** `gh` unauthenticatable non-interactively → local `git merge --no-ff <story-branch> → main` + a second `--no-ff` post-merge follow-up for the `review→done` flip. Mirror this (AC15) per [[feedback_two_pr_docs_execution]].

### Sprint fit & dependencies

- **Dependencies satisfied:** 9.9c `done` (`9b9d4af`) + 9.11 `done` (`aca0906`) on `main`. Fully unblocked. Downstream: 9.9b (blocked on 9.9c/9.11/9.12/9.13/9.14), 9.13, 9.14.
- **Estimate: fits-in-one-sprint at the high end (~4–5 focused days).** Two-sprint risk lives entirely in AC7's in-tool feedback if it grows toward Tool-9-style confusion matrices — AC7 explicitly fences it to a fire-ratio/aggregate-score readout. Keep that fence. The variance + band-seed + band-fire math is *ported/reused, not invented* (largest de-risk).

### Project Structure Notes

- New package `apps/tooling/tools/zone_picker/` (sibling of `image_inspector/`, `common/`). Output fragments under `apps/tooling/output/zones/v<hud_version>/` (gitignore posture for `output/` is a 9.9b concern — AC9 of 9.9b owns the commit-location decision; 9.12 only writes there).
- Tool numbering is cosmetic; gaps are tolerated (9.11 precedent). `maps` insertion order = `MAP_LABELS` order (emitter does not sort — picker owns it).
- No conflicts with the unified project structure. No code outside `apps/tooling/` is touched (no `apps/mobile`, no `apps/web`, no `contracts/`).

### References

- [Story 9.12 stub — epics-and-stories.md](../epics-and-stories.md) (`### Story 9.12: Unified Zone Picker`)
- [Sprint Change Proposal 2026-05-15 §9.12](../sprint-change-proposal-2026-05-15.md) (full spec, modes table, workflow steps #2/#3/#4)
- [contracts/map-config.schema.json](../../contracts/map-config.schema.json) — `$defs.Zone/Hsv/Rect/MapEntry`, top-level required
- [apps/tooling/tools/map_config_emitter.py](../../apps/tooling/tools/map_config_emitter.py) — `_FRAGMENT_FILES`, `_load_fragments`, `_assemble_output`
- [apps/tooling/tests/test_map_config_emitter.py](../../apps/tooling/tests/test_map_config_emitter.py) — canonical fragment fixtures
- [apps/tooling/tools/common/zones.py](../../apps/tooling/tools/common/zones.py) — `Rect`, `HsvBand`, `band_inrange_ratio`, scale helpers
- [apps/tooling/tools/common/labels.py](../../apps/tooling/tools/common/labels.py) — `MAP_LABELS`, `LABEL_DISPLAY`
- [apps/tooling/tools/image_inspector/canvas.py](../../apps/tooling/tools/image_inspector/canvas.py) — `ImageCanvas`
- [apps/tooling/tools/image_inspector/modes.py](../../apps/tooling/tools/image_inspector/modes.py) — `HSVFilterMode`, `ROIMode`
- [apps/tooling/tools/roi_detection_tester.py](../../apps/tooling/tools/roi_detection_tester.py) — `iter_labeled_frames` sorted order to mirror
- [apps/tooling/wardentooling.py](../../apps/tooling/wardentooling.py) — `flow_tool6`/`flow_tool9` registration template
- Recovered source: `git show ba6b326:apps/tooling/tools/overlay_stack_analyzer.py`; `git show 0c1c656^:apps/tooling/tools/auto_roi_discoverer/discoverer.py` (and `validator.py`, `model.py`)
- [Story 9.11](9-11-retire-legacy-tooling.md), [Story 9.9c](9-9c-schema-unification.md) — precedents
- Memory: [[project_warden_new_hud_labeler]], [[feedback_ac_checkbox_tighten]], [[feedback_two_pr_docs_execution]]

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (Amelia, /bmad-dev-story)

### Debug Log References

- `cd apps/tooling && uv run pytest -q` → **132 passed** (108 Story-9.11 baseline + 24 new `test_zone_picker.py`); 0 regressions.
- `pnpm --filter tooling test` → **132 passed** (matches apps/tooling exactly — AC13 cross-workspace parity).
- `python -m tools.zone_picker --help` → clean usage; `--hud-version v9` → argparse error exit **before** any tkinter import (AC1/AC11 display-free rejection verified).
- `python -c "import wardentooling"` → clean; `zone_picker` present in `_TOOL_MAP`, "Tool 10 — Unified Zone Picker" label registered.
- `git cat-file -t 9b9d4af` / `aca0906` → both `commit` (9.9c + 9.11 deps confirmed on `main`).

### Completion Notes List

- **AC1 (package decision):** package `apps/tooling/tools/zone_picker/` with the mandated split — `__init__.py`, `__main__.py` (thin CLI `main(argv)->int`), `app.py` (Tk shell), `modes.py` (3 mode descriptors + reused-primitive adapters), `variance.py` (Tk-free), `fragments.py` (Tk-free). Pure logic imports + the full pure-logic suite run with no display.
- **AC2 (no GUI reinvention):** `ImageCanvas` reused verbatim. `ROIMode`/`HSVFilterMode` are written for the standalone `InspectorApp`; adapted via `modes._InspectorShim` (supplies `toolbar`/`set_status`/`last_pick_hsv`/`image_path`) + minimal subclasses: `CapturingROIMode._add_roi` calls `super()._add_roi` then reads `_rois[-1]` + reuses `_to_ref` (zero coordinate-math fork); `SeedableHSVFilterMode` adds `seed_band`/`read_band` around the existing entry StringVars without touching the `cv2.inRange` overlay math in `_apply`. **`HSVEditor` confirmed nonexistent** (died with `minimap_zone_selector`, 9.11) — not hunted.
- **AC3 (VideoPlayer verified-negative):** `tools.common.video_player.VideoPlayer` is a **video-file** widget; input here is PNG sequences → deliberately NOT used. PNG stepping is in-tool (`app._step`). Enumeration order is mirrored from `roi_detection_tester.iter_labeled_frames` — `sorted(os.listdir(version_dir))` over class dirs × `sorted(glob('*.png'))` within (`modes.pooled_pngs`) — **without importing Tool 9** (mirrored, not coupled).
- **AC5/AC6 (ported, not invented):** `variance.py` Welford + circular-Hue accumulators are byte-for-byte from `overlay_stack_analyzer.py @ ba6b326`; `derive_band_for_rect`/`circular_mean_cv`/`circular_std_cv` byte-for-byte from `auto_roi_discoverer/discoverer.py @ 0c1c656^` (its `DiscoverParams.tol_k`/`min_ratio` flattened to plain args; the only other delta is a single-pass fold since frames are already in memory — the original two-pass PNG re-read was a batch memory concern that doesn't apply). Heatmap = `COLORMAP_JET` over min-max-normalized S+V stddev only (Hue excluded). `stddev` view = `clip(0,255)` (NOT normalized).
- **AC9 (anti-clobber):** `fragments.load_existing` reads whatever exists (`utf-8-sig`, BOM-tolerant like the emitter), scaffolds the rest; `write_all` always emits all four files (`json indent=2`, `utf-8` — same shape `test_map_config_emitter._write_fragments` writes) with `maps` re-ordered into `MAP_LABELS` order and stable position-derived ids (`hud_z00`/`inmatch_z00`/`<slug>_z00`). A per-map session that never touches the array fragments round-trips them byte-identical (locked by `TestMergeNotClobber`).
- **Schema-clamp note:** the emitter does **no** coercion; `serialize_zone` clamps every field into its schema range before disk — notably `h_tol`→`[0,180]` (the recovered band-seed can overshoot) and a stray boolean `weight_override`→`null` (the unified schema + a 9.9c test reject the pre-9.9c boolean shape). HSV centers/tols emitted as schema integers (`HsvBand.__post_init__` already int-coerces).
- **AC10:** `app._emit_roundtrip` shells the **unchanged** emitter (`tools/map_config_emitter.py --zones-dir …`, `parents[1]` resolution verified) as a black-box gate, surfacing its stderr verbatim on failure. `TestEmitterRoundTrip` proves picker-written fragments pass `_load_fragments`+`_assemble_output`+`_validate_against_schema` and `emit()` end-to-end.
- **AC12 (run_tool adaptation):** **none needed** — `run_tool()` already does `[sys.executable] + args`, so the `["-m","tools.zone_picker",…]` arg-list (mirroring `flow_dev_image_inspector`'s existing `-m` pattern) works as-is. Registered as **Tool 10** (Tools 7/8 gaps preserved per 9.11; Tool 9 not renumbered).
- **AC13/AC14/AC15 [HELD]:** the *technical* content of AC13 is verified green now (132 = 108+24, `pnpm` parity, smokes clean) but the box stays `[ ]` per its `[HELD]` tag — the "no regression on **post-merge** `main`" gate + sprint-status `review→done` + post-merge box-flips land via the `story-9-12-postmerge` Two-PR follow-up, consistent with 9.9c/9.11 precedent and [[feedback_two_pr_docs_execution]].
- No new dependencies (tkinter stdlib; PIL/cv2/numpy already present via image_inspector/Tool 9). No code outside `apps/tooling/` touched.

### File List

- `apps/tooling/tools/zone_picker/__init__.py` (new)
- `apps/tooling/tools/zone_picker/__main__.py` (new)
- `apps/tooling/tools/zone_picker/fragments.py` (new — Tk-free)
- `apps/tooling/tools/zone_picker/variance.py` (new — Tk-free)
- `apps/tooling/tools/zone_picker/modes.py` (new)
- `apps/tooling/tools/zone_picker/app.py` (new — Tk shell)
- `apps/tooling/tests/test_zone_picker.py` (new — 24 pure-logic tests)
- `apps/tooling/wardentooling.py` (modified — `flow_zone_picker` + `_TOOL_MAP`/`choices_main`/`menu_main`/`_reprompt_source` Tool 10 entries)
- `_bmad-output/implementation-artifacts/9-12-unified-zone-picker.md` (modified — checkboxes, Dev Agent Record, Status)
- `_bmad-output/sprint-status.yaml` (modified — `9-12` lifecycle + `last_updated`)

### Change Log

- 2026-05-16 → 2026-05-17 — /bmad-dev-story 9.12 (Amelia): implemented the Unified Zone Picker package (Tasks 1–7). AC1–AC12 + Tasks 1–7 `[x]`; AC13/14/15 + Task 8 `[ ] [HELD]` for the Two-PR post-merge follow-up. apps/tooling pytest 108 → 132 (+24, 0 regressions); `pnpm --filter tooling test` 132 parity. Status `in-progress → review`. Delivered via local `git merge --no-ff story-9-12-unified-zone-picker → main` (`gh` unauthenticatable non-interactively — 9.9c/9.11 precedent); `review → done` + post-merge box-flips deferred to `story-9-12-postmerge`.
