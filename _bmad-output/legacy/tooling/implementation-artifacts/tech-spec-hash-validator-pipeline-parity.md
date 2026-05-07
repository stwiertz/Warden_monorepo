---
title: 'Hash Validator Pipeline Parity Fix'
slug: 'hash-validator-pipeline-parity'
created: '2026-03-27'
status: 'Completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python', 'OpenCV (cv2)', 'imagehash', 'numpy', 'PIL']
files_to_modify: ['tools/hash_comparator.py', 'tools/map_config_generator.py', 'tools/hash_validator.py']
code_patterns: ['config-driven pipeline params', 'map_config.json as serialized pipeline state', 'build_canvases as shared canvas builder']
test_patterns: ['no test framework — manual validation via hash_validator.py output']
---

# Tech-Spec: Hash Validator Pipeline Parity Fix

**Created:** 2026-03-27

## Overview

### Problem Statement

`hash_validator.py` always passes `text_anchor_width=None` and `threshold_hash=False` to `build_canvases`, but reference hashes in `map_config.json` may have been generated with `text_anchor_width=52` and/or `threshold_hash=True` (from config). The validator hashes a different crop/binarization than was used at generation time — producing near-random distances (300–450 out of 1024 max) and 8% accuracy.

Root cause: Both `text_anchor_width` and `threshold_hash` are read from config at generation time but never written to `map_config.json`, so the validator cannot reproduce the exact pipeline.

### Solution

Store `text_anchor_width` and `threshold_hash` in `map_config.json` at generation time (both generators) so `hash_validator.py` can read them back and pass them to `build_canvases`, reproducing the exact same pipeline used to produce the reference hashes.

### Scope

**In Scope:**
- `tools/hash_comparator.py`: thread `text_anchor_width` and `threshold_hash` into `generate_map_config()` and write both to the output dict
- `tools/map_config_generator.py`: write `text_anchor_width` and `threshold_hash` into the output dict; also preserve both in patch mode alongside the existing `hash_method`/`tile_cols` preservation
- `tools/hash_validator.py`: read `text_anchor_width` and `threshold_hash` from `map_config.json` and pass both to `build_canvases`

**Out of Scope:**
- Multi-hash-size comparison in hash_validator
- Accuracy report format changes
- Any other pipeline parameters

## Context for Development

### Codebase Patterns

- **map_config.json as pipeline state**: The file already stores `hash_size`, `hash_method`, `tile_cols`, `recognition_threshold` — `text_anchor_width` and `threshold_hash` are natural additions to this set.
- **build_canvases is the shared canvas builder**: Both `hash_comparator.py` (generation) and `hash_validator.py` (validation) call `build_canvases()` from `hash_comparator.py`. Both must pass identical parameters.
- **Config-driven pipeline params**: All pipeline parameters originate from `config/config.yaml` `map_identification` section. `text_anchor_width` is read via `map_id.get("text_anchor_width") or None`; `threshold_hash` is read via `map_id.get("threshold_hash", False)`. Neither is persisted to `map_config.json`.
- **None/0 = disabled convention for `text_anchor_width`**: `None` or `0` means anchor cropping is disabled (full ROI used). Enforced in `build_canvases`.
- **`threshold_hash` is a boolean**: `False` = no binarization (grayscale), `True` = Otsu binarization applied before hashing.
- **Patch mode preservation loop**: In `map_config_generator.py` `run()`, the loop `for key in ("hash_method", "tile_cols"):` preserves specific fields from `existing_config` in patch mode. Both new fields must be added to this loop.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/hash_comparator.py` | Tool 3 — generates `map_config.json` via `generate_map_config()`. Neither `text_anchor_width` nor `threshold_hash` is threaded in or written to output. |
| `tools/map_config_generator.py` | Alternative generator — reads both params from config in `run()` but does not write them to the output dict (lines 350–366) nor preserve them in patch mode (lines 362–365). |
| `tools/hash_validator.py` | Tool 4 — `run_validation()` calls `build_canvases` at lines 165–167 with hardcoded `text_anchor_width=None` and no `threshold_hash`. |
| `config/config.yaml` | Source of truth — `map_identification.text_anchor_width: 52`, `map_identification.threshold_hash: false`. |
| `output/map_config.json` | Output artifact — currently missing both fields. |

### Technical Decisions

- **Omit-if-default**: Write `text_anchor_width` only when truthy (non-zero, non-None). Write `threshold_hash` only when `True`. This keeps configs clean and makes the validator's `.get()` fallback to the disabled/False default safe and unambiguous.
- **Backward compatibility**: `.get("text_anchor_width")` returns `None` (disabled) for old configs; `.get("threshold_hash", False)` returns `False` (no binarization) for old configs. Both match the old validator behavior exactly — no breaking change.
- **`generate_map_config` signature**: Add `text_anchor_width=None` and `threshold_hash=False` parameters. Both values are already in scope in `main()` (lines 743–745 of `hash_comparator.py`).
- **Patch mode conflict resolution**: The current config is authoritative. When patching, the new `text_anchor_width`/`threshold_hash` values (from the current run's config) take precedence over whatever was stored in the existing file. The preserved-fields loop in `map_config_generator.py` only needs to preserve these fields when the new run does NOT recompute them (same as current behavior for `hash_method`/`tile_cols`). Since `run()` always has the live config values, simply writing them to the output dict (unconditionally for `threshold_hash`, conditionally for `text_anchor_width`) is sufficient — the live config wins.

## Implementation Plan

### Tasks

- [x] Task 1: Write `text_anchor_width` and `threshold_hash` to the output dict in `map_config_generator.py`
  - File: `tools/map_config_generator.py`
  - Action: In `run()`, after the `output` dict is built (around lines 350–366), add both fields. `text_anchor_width` is in scope at line 273; `threshold_hash` must be extracted from config in `run()` similarly (e.g. `threshold_hash = map_id_config.get("threshold_hash", False)`). Add after `"maps"`:
    ```python
    if text_anchor_width:
        output["text_anchor_width"] = text_anchor_width
    if threshold_hash:
        output["threshold_hash"] = threshold_hash
    ```
  - Notes: The `output` dict is written via `json.dump` — no other write-path changes needed.

- [x] Task 2: Fix patch mode preservation in `map_config_generator.py`
  - File: `tools/map_config_generator.py`
  - Action: In `run()`, the patch-mode preservation loop (lines 362–365) currently reads:
    ```python
    for key in ("hash_method", "tile_cols"):
        if key in existing_config:
            output[key] = existing_config[key]
    ```
    Extend the tuple to include the new fields:
    ```python
    for key in ("hash_method", "tile_cols", "text_anchor_width", "threshold_hash"):
        if key in existing_config:
            output[key] = existing_config[key]
    ```
  - Notes: This prevents patch mode from silently dropping a `text_anchor_width`/`threshold_hash` that was already stored in the existing config if the current run somehow doesn't rewrite it (e.g. a legacy code path). Since Task 1 always writes from live config first, this loop acts as a safety net for fields present in the existing config but not recomputed.

- [x] Task 3: Thread `text_anchor_width` and `threshold_hash` into `generate_map_config()` in `hash_comparator.py`
  - File: `tools/hash_comparator.py`
  - Action: Add `text_anchor_width=None` and `threshold_hash=False` to the `generate_map_config()` function signature (line 541). Inside the function, after the `"maps"` key in the `output` dict, add:
    ```python
    if text_anchor_width:
        output["text_anchor_width"] = text_anchor_width
    if threshold_hash:
        output["threshold_hash"] = threshold_hash
    ```

- [x] Task 4: Pass both params at the `generate_map_config()` call site in `main()` in `hash_comparator.py`
  - File: `tools/hash_comparator.py`
  - Action: In `main()`, update the `generate_map_config()` call at line 834 to pass both new params. Both variables are already in scope (`text_anchor_width` at line 743, `threshold_hash` at line 745):
    ```python
    generate_map_config(
        results, best_combo, config, output_dir,
        tile_cols=tile_cols,
        text_anchor_width=text_anchor_width,
        threshold_hash=threshold_hash,
        recognition_threshold_base=map_id.get("recognition_threshold", 10),
    )
    ```

- [x] Task 5: Read `text_anchor_width` and `threshold_hash` from `map_config.json` in `hash_validator.py` and pass to `build_canvases`
  - File: `tools/hash_validator.py`
  - Action: In `run_validation()`, after the existing parameter extractions (lines 141–145), add:
    ```python
    text_anchor_width = map_config.get("text_anchor_width") or None
    threshold_hash = map_config.get("threshold_hash", False)
    ```
    Update the `build_canvases` call (lines 165–167) to pass both:
    ```python
    canvases = build_canvases(
        frames, roi_dict, canvas_size, resolution, tile_cols,
        text_anchor_width=text_anchor_width,
        threshold_hash=threshold_hash,
    )
    ```
  - Notes: `run_validation()` already receives `map_config` as a parameter — no signature change needed.

- [x] Task 6: Regenerate `output/map_config.json`
  - File: `output/map_config.json` (artifact, not code)
  - Action: After all code changes are applied, re-run Tool 3 against `labeled/` to produce a new `map_config.json` that contains `text_anchor_width`. The existing file is missing this field and will produce broken validator results until regenerated.
  - Command: Run Tool 3 via `wardentooling.py` → `Tool 3 — Generate Map Config` on `labeled/` directory.

### Acceptance Criteria

- [ ] AC 1: Given `text_anchor_width: 52` in config, when Tool 3 generates `map_config.json`, then the output file contains `"text_anchor_width": 52`.

- [ ] AC 2: Given `threshold_hash: true` in config, when either generator writes `map_config.json`, then the output contains `"threshold_hash": true`. Given `threshold_hash: false`, the key is absent.

- [ ] AC 3: Given `text_anchor_width` is `null`/`0` in config, when either generator writes `map_config.json`, then the `text_anchor_width` key is absent from the output.

- [ ] AC 4: Given a `map_config.json` containing `"text_anchor_width": 52`, when Tool 4 runs, then it passes `text_anchor_width=52` to `build_canvases`.

- [ ] AC 5: Given a legacy `map_config.json` without `text_anchor_width` or `threshold_hash` keys, when Tool 4 runs, then it passes `text_anchor_width=None` and `threshold_hash=False` to `build_canvases` — no error raised, full-ROI grayscale behavior preserved.

- [ ] AC 6: Given `map_config.json` is regenerated with the fix (Task 6), when Tool 4 validates the same `labeled/` data, then overall accuracy is ≥ 80% and mean pairwise distance for correct predictions is ≤ 50.

## Additional Context

### Dependencies

- No new external libraries required.
- `build_canvases` in `hash_comparator.py` already accepts both `text_anchor_width` and `threshold_hash` — no changes to that function.
- `map_config.json` format change is additive — backward compatible via `.get()` with safe defaults.

### Testing Strategy

Manual validation (no test framework exists):

1. Run Tool 3 (`hash_comparator.py`) on `labeled/` with current config (`text_anchor_width: 52`, `threshold_hash: false`) → confirm `text_anchor_width: 52` appears in new `map_config.json` and `threshold_hash` key is absent.
2. Run Tool 4 (`hash_validator.py`) against `labeled/` using the new `map_config.json` → confirm overall accuracy ≥ 80% and mean distance for correct predictions ≤ 50.
3. Backward compat: manually remove `text_anchor_width` from a copy of `map_config.json` and re-run Tool 4 → confirm no error; tool uses full-ROI behavior.
4. Disabled-state generator test: temporarily set `text_anchor_width: 0` in `config/config.yaml`, re-run Tool 3 → confirm `text_anchor_width` key is absent from new `map_config.json`.
5. Patch mode: run Tool 3 in patch mode (`--patch`) against a `map_config.json` that already has `text_anchor_width: 52` → confirm the field is preserved in the output.

### Notes

- **The existing `output/map_config.json` must be regenerated** (Task 6) before Tool 4 produces accurate results. Applying only the code changes without regenerating the config will produce identical broken behavior.
- `threshold_hash` is currently `false` in config, so in practice only `text_anchor_width` will appear in new configs. The `threshold_hash` plumbing is added now to prevent the identical mismatch if it's ever enabled.

## Review Notes

- Adversarial review completed
- Findings: 5 total, 4 fixed, 1 skipped (noise)
- Resolution approach: auto-fix
- Key fix: removed `text_anchor_width`/`threshold_hash` from patch-mode preservation loop in `map_config_generator.py` — live config is now authoritative as intended
