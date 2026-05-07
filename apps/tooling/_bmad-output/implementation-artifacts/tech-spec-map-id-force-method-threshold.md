---
title: 'Map ID Pipeline — Force Method & Threshold Calibration'
slug: 'map-id-force-method-threshold'
created: '2026-03-27'
status: 'Completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3', 'imagehash', 'OpenCV', 'argparse', 'JSON']
files_to_modify:
  - 'tools/hash_comparator.py'
  - 'tools/warden_analyzer.py'
  - 'config/config.yaml'
code_patterns:
  - 'CLI args override config.yaml values (pattern already used for threshold_hash, shift_tolerance, etc.)'
  - 'map_config.json stores hash_method, hash_size, canvas_size — all generated params travel with the hashes'
  - 'warden_analyzer.py reads runtime params from config.yaml, structural params from map_config.json'
  - 'select_best_combination() returns (roi_name, resolution, method) tuple used by generate_map_config()'
test_patterns: ['No test suite — manual CLI validation']
---

# Tech-Spec: Map ID Pipeline — Force Method & Threshold Calibration

**Created:** 2026-03-27

## Overview

### Problem Statement

The map identification pipeline has two calibration mismatches that cause runtime failures:

1. **Method auto-selection optimizes for wrong metric.** `hash_comparator.py` recommends the hash method with the highest pairwise minimum distance across training frames (`select_best_combination()`). This favors `phash` at `hash_size=16` (min=92 vs dhash min=76), but phash is cross-video inconsistent — the same map (`the_cliff`) hashed to dist=0 with dhash vs dist=90 with phash on a different video source. There is no way to force or prefer a specific method for `map_config.json` output.

2. **`recognition_threshold` is not tied to `hash_size`.** The threshold is a fixed value in `config.yaml` (`recognition_threshold: 10`), calibrated for 64-bit hashes (`hash_size=8`). When `hash_size` increases to 16 (256-bit), Hamming distances scale ~4x but the threshold doesn't, causing all maps to be flagged as `unrecognized`. The threshold is read from `config.yaml` at runtime (`warden_analyzer.py:125`) and never stored in `map_config.json` alongside the hashes it was calibrated for.

### Solution

1. Add `--force-method` CLI flag and `preferred_method` config param to `hash_comparator.py`. When set, bypass `select_best_combination()` for the map_config output decision and use the forced method instead. The comparison report still runs all methods.

2. Store a scaled `recognition_threshold` in `map_config.json` at generation time. Scale formula: `round(base_threshold * (hash_size / 8) ** 2)`. At runtime, `warden_analyzer.py` reads threshold from `map_config.json` first; if absent, falls back to `config.yaml` with a warning.

### Scope

**In Scope:**
- `hash_comparator.py`: `--force-method` CLI arg, `preferred_method` config read, write `recognition_threshold` to `map_config.json`
- `warden_analyzer.py`: read `recognition_threshold` from `map_config.json`, fallback + warning
- `config/config.yaml`: add `preferred_method` field under `map_identification`

**Out of Scope:**
- Changing hashing algorithms
- UI or TUI changes
- Adding new ROIs
- Modifying `hash_validator.py` or `map_config_generator.py`

---

## Context for Development

### Codebase Patterns

- **CLI overrides config:** Every tunable param in `hash_comparator.py` follows this pattern: `arg_value if arg_value is not None else config.get("key", default)`. The new `--force-method` flag should follow the same pattern, reading `preferred_method` from `config["map_identification"]` as the config-level default.
- **map_config.json is the hash's source of truth:** `canvas_size`, `hash_size`, `hash_method`, `tile_cols`, `roi` are all written by `generate_map_config()` and read back by `warden_analyzer.py`. `recognition_threshold` must join this set.
- **select_best_combination() selects globally:** It iterates all `(roi, resolution, method)` combos and picks the one with highest `stats["min"]`. When forcing a method, we need the best `(roi, resolution)` for that method specifically, then use the forced method instead.
- **warden_analyzer.py line 124-125 is the exact injection point** for threshold: `mi = config["map_identification"]` / `recognition_threshold = mi.get("recognition_threshold", 10)`. The new logic checks `map_config.get("recognition_threshold")` first.
- **Existing warning pattern:** `warden_analyzer.py:180-185` already emits a stderr warning for `threshold_hash` mismatch. The missing-threshold warning should follow the same style.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/hash_comparator.py` | Generates map_config.json; contains `select_best_combination()` (L461), `generate_map_config()` (L531), `main()` argparse (L589) |
| `tools/warden_analyzer.py` | Runtime analyzer; reads threshold at L124-125, reads map_config fields at L130-132 |
| `config/config.yaml` | `map_identification` block: `hash_size`, `recognition_threshold`, `hash_methods`, `preferred_method` (to add) |

### Technical Decisions

- **Scaling formula:** `round(recognition_threshold * (hash_size / 8) ** 2)`. Examples: hash_size=8→10, hash_size=12→22, hash_size=16→40. The base `recognition_threshold` is always read from `config.yaml` at generation time so the user retains control of the base calibration.
- **Force method override scope:** `--force-method` overrides only the method written to `map_config.json`. The comparison report still runs and shows all methods. This preserves the diagnostic value of the tool.
- **Preferred method in config:** `preferred_method: dhash` (string, optional). Empty/null = auto-select (current behavior). CLI `--force-method` takes precedence over config `preferred_method`.
- **Fallback behavior:** If `recognition_threshold` is absent from `map_config.json` (old files), `warden_analyzer.py` falls back to `config.yaml` value and prints a warning to stderr.

---

## Implementation Plan

### Tasks

#### Task 1 — Add `preferred_method` to `config/config.yaml`

**File:** `config/config.yaml`

Add `preferred_method: dhash` under `map_identification`, at the same indentation level as `hash_methods` and other `map_identification` fields (2-space indent). Place it directly below the `hash_methods` line.

```yaml
  # Preferred hash method for map_config.json output.
  # Overrides auto-selection from hash_comparator.py comparison results.
  # Set to null or omit to use auto-selection. CLI --force-method takes precedence.
  preferred_method: dhash
```

---

#### Task 2 — Add `--force-method` arg and `preferred_method` config read in `hash_comparator.py`

**File:** `tools/hash_comparator.py`

**2a.** In `main()` argparse block, add after the `--methods` arg block (which ends ~L626, before `args = parser.parse_args()` at L666):

```python
parser.add_argument(
    "--force-method",
    metavar="METHOD",
    choices=["ahash", "dhash", "phash"],
    default=None,
    help=(
        "Force a specific method into map_config.json output, bypassing "
        "auto-selection. The comparison report still runs all methods. "
        "(Overrides config preferred_method.)"
    ),
)
```

**2b.** In `main()`, after `map_id = config["map_identification"]` is assigned (~L678 — `map_id` must exist before this line), resolve the forced method:

```python
force_method = args.force_method or map_id.get("preferred_method") or None
```

**2c.** In `main()`, after `best_combo, best_min = select_best_combination(results)` (L756), insert override logic:

```python
if force_method:
    # Find the best (roi, resolution) for the forced method
    forced_combo = None
    forced_min = -1
    for roi_name, res_data in results.items():
        for resolution, method_data in res_data.items():
            if force_method in method_data:
                min_dist = method_data[force_method]["stats"]["min"]
                if min_dist > forced_min:
                    forced_combo = (roi_name, resolution, force_method)
                    forced_min = min_dist
    if forced_combo:
        print(f"  (forced method '{force_method}' — auto-selected: {best_combo[2] if best_combo else 'none'})")
        best_combo = forced_combo
        best_min = forced_min
    else:
        print(
            f"Warning: --force-method '{force_method}' not found in results. "
            "Falling back to auto-selection.",
            file=sys.stderr,
        )
```

---

#### Task 3 — Write `recognition_threshold` into `map_config.json` in `generate_map_config()`

**File:** `tools/hash_comparator.py`

**3a.** Add `recognition_threshold_base` parameter to `generate_map_config()` signature (L531):

```python
def generate_map_config(results, best_combo, config, output_dir, tile_cols=1, recognition_threshold_base=10):
```

**3b.** Inside `generate_map_config()`, before the `output = { ... }` dict literal, explicitly assign `hash_size` and compute the scaled threshold. Note: `hash_size` is NOT pre-assigned as a local variable in the current function body — add these two lines immediately before the `output = {` line:

```python
hash_size = config["map_identification"]["hash_size"]
scaled_threshold = round(recognition_threshold_base * (hash_size / 8) ** 2)
```

Then add to the `output` dict:

```python
"recognition_threshold": scaled_threshold,
```

**Note:** Tasks 3a and 3c are tightly coupled — both must be implemented together. Doing 3a without 3c leaves the new parameter at its default (10) regardless of config.

**3c.** In `main()`, pass `recognition_threshold_base` when calling `generate_map_config()` (L769):

```python
generate_map_config(
    results, best_combo, config, output_dir,
    tile_cols=tile_cols,
    recognition_threshold_base=map_id.get("recognition_threshold", 10),
)
```

---

#### Task 4 — Read `recognition_threshold` from `map_config.json` in `warden_analyzer.py`

**File:** `tools/warden_analyzer.py`

This change is inside the `run()` function (defined at L97), not at module level. Replace lines 124-125 inside `run()`:

```python
mi = config["map_identification"]
recognition_threshold = mi.get("recognition_threshold", 10)
```

With:

```python
mi = config["map_identification"]
if "recognition_threshold" in map_config:
    recognition_threshold = map_config["recognition_threshold"]
else:
    recognition_threshold = mi.get("recognition_threshold", 10)
    print(
        f"Warning: recognition_threshold not found in map_config.json — "
        f"using config.yaml value ({recognition_threshold}). "
        "Regenerate map_config.json with hash_comparator.py for a calibrated threshold.",
        file=sys.stderr,
    )
```

#### Task 4b — Update log output in `warden_analyzer.py` to show threshold source

**File:** `tools/warden_analyzer.py`

At lines 177-179, the existing log output prints `recognition_threshold=...`. Update this line to include the source so it's clear during debugging whether the value came from `map_config.json` or fell back to `config.yaml`:

```python
threshold_source = "map_config" if "recognition_threshold" in map_config else "config.yaml"
print(f"Config: recognition_threshold={recognition_threshold} (from {threshold_source}), "
      f"shift_tolerance={shift_tolerance}, score_offset={score_offset}s, "
      f"threshold_hash={threshold_hash}")
```

Replace the existing single-line `print(f"Config: recognition_threshold=...")` at L177.

---

### Acceptance Criteria

**AC1 — Force method via CLI**
- Given `hash_comparator.py` run with `--force-method dhash`
- When comparison completes and phash would have been auto-selected
- Then `map_config.json` contains `"hash_method": "dhash"` and the report still contains all method results

**AC2 — Force method via config**
- Given `config.yaml` has `preferred_method: dhash` and no `--force-method` flag
- When `hash_comparator.py` runs
- Then `map_config.json` contains `"hash_method": "dhash"`

**AC3 — CLI takes precedence over config**
- Given `config.yaml` has `preferred_method: ahash` and `--force-method dhash` is passed
- When `hash_comparator.py` runs
- Then `map_config.json` contains `"hash_method": "dhash"` (CLI wins)

**AC4 — Threshold written to map_config**
- Given `config.yaml` has `recognition_threshold: 10` and `hash_size: 8`
- When `hash_comparator.py` runs
- Then `map_config.json` contains `"recognition_threshold": 10`

- Given `config.yaml` has `recognition_threshold: 10` and `hash_size: 16`
- When `hash_comparator.py` runs
- Then `map_config.json` contains `"recognition_threshold": 40`

- Given `config.yaml` has `recognition_threshold: 10` and `hash_size: 12`
- When `hash_comparator.py` runs
- Then `map_config.json` contains `"recognition_threshold": 22`

**AC5 — Runtime reads threshold from map_config**
- Given `map_config.json` contains `"recognition_threshold": 40`
- When `warden_analyzer.py` runs
- Then it uses threshold=40 and no warning is printed

**AC6 — Runtime fallback warning for old map_config files**
- Given `map_config.json` does NOT contain `recognition_threshold`
- When `warden_analyzer.py` runs
- Then it uses config.yaml value and prints a warning to stderr containing "Regenerate map_config.json"

---

## Additional Context

### Dependencies

No new Python dependencies. All changes are to existing files using existing imports.

### Testing Strategy

Manual CLI validation (no test suite in project):

1. Generate `map_config.json` with `--force-method dhash` and verify JSON contains `"hash_method": "dhash"` and `"recognition_threshold": <scaled>`.
2. Run `warden_analyzer.py` with the new map_config and confirm maps are recognized (dist < threshold).
3. Run `warden_analyzer.py` with an old map_config (no threshold field) and confirm warning is printed to stderr.
4. Verify `hash_size=8` → threshold=10, `hash_size=16` → threshold=40 in generated map_config.

## Review Notes
- Adversarial review completed
- Findings: 12 total, 6 fixed, 6 skipped (noise/low)
- Resolution approach: auto-fix
- Fixed: F-01 (tie-break parity), F-06 (threshold_source set once), F-07 (VALID_METHODS constant), F-08 (stderr for override notice), F-09 (clearer warning), F-10 (print scaled threshold)

---

### Notes

- **Terminology:** `recognition_threshold_base` = the raw value from `config.yaml` (user-controlled). `recognition_threshold` (no suffix) = the scaled value written to `map_config.json` and used at runtime. Keep this distinction consistent in code and commit messages.
- `generate_map_config()` does not pre-assign `hash_size` as a local variable — Task 3b explicitly adds that assignment before the `output` dict to make the scaling step self-contained.
- The `print(f"  (forced method...")` line in Task 2c uses 2-space indent to visually match the existing recommendation output block at L759-763 in `hash_comparator.py` (`print(f"Recommendation: {method} on ROI ...")`).
- Old `map_config.json` files (pre-this-change) will trigger the AC6 fallback warning — no migration needed, just regenerate.
