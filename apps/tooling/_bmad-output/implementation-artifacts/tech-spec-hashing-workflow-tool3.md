---
title: 'Hashing Workflow for Map Identification (Tool 3)'
slug: 'hashing-workflow-tool3'
created: '2026-03-18'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['python3.8+', 'imagehash>=4.2', 'opencv>=4.8', 'pillow', 'numpy', 'pyyaml']
files_to_modify: ['tools/hash_comparator.py (new)', 'tools/frame_labeler.py', 'config/config.yaml']
code_patterns: ['modular CLI in tools/', 'shared utils in utils/', 'config-driven via YAML', 'ROI at 1920x1080 reference resolution', 'argparse CLI pattern', 'file-based I/O between tools']
test_patterns: ['none established']
---

# Tech-Spec: Hashing Workflow for Map Identification (Tool 3)

**Created:** 2026-03-18

## Overview

### Problem Statement

On a besoin d'un outil fiable pour identifier les 15 cartes EVA. L'approche pixel-par-pixel décrite dans `description.md` est trop sensible aux changements de background derrière la transparence du HUD. Le `map_config_generator` existe avec pHash mais n'est pas encore utilisé en production. Il faut tester et comparer plusieurs approches de hash (aHash, dHash, pHash) sur différentes ROIs et types de frames pour trouver la combinaison la plus fiable sans collisions — et ainsi gagner confiance avant d'implémenter dans Warden mobile.

### Solution

Un outil (Tool 3) qui :
1. Prend les frames organisées par Tool 2 (start, end, score — pas juste score)
2. Génère les 3 types de hash (aHash, dHash, pHash) sur une ROI configurable
3. Vérifie les collisions inter-map pour chaque type de hash (Hamming Distance)
4. Produit un rapport comparatif + le `map_config.json` final avec le meilleur hash
5. (Optionnel) Teste à différentes résolutions si pertinent pour la qualité du hash

Cela implique aussi une évolution de Tool 2 (Frame Labeler) pour exporter les frames start/end en plus du score, organisées par type et par map.

### Scope

**In Scope:**
- Tool 3 : génération multi-hash (aHash, dHash, pHash), comparaison, détection de collisions
- Modification de Tool 2 : exporter les frames start/end en plus du score, organisées par type et par map
- ROI configurable (HUD map name zone vs score screen zone)
- Rapport comparatif des méthodes de hash avec distances de Hamming
- Sweep de résolution optionnel

**Out of Scope:**
- Implémentation mobile (Warden)
- Approche pixel-par-pixel (description.md originale — remplacée par hashing, trop sensible aux changements de background derrière la transparence)
- Sweep de résolution obligatoire (optionnel uniquement)

## Context for Development

### Codebase Patterns

- Modular CLI Pipeline : chaque tool est un CLI indépendant dans `tools/`, avec `argparse`
- ROI définie à résolution de référence 1920×1080, scalée au runtime via `utils/image.scale_roi()`
- Config-driven : tous les paramètres dans `config/config.yaml`, chargés via `utils/config.load_config()`
- File-based I/O entre tools : Tool 1 exporte des frames PNG nommées `*start*`, `*end*`, `*score*` → Tool 2 les labellise dans `<output>/labeled/<map_name>/` → Tool 3 les consomme
- Pattern d'import : `sys.path.insert(0, ...)` pour accéder à `utils/` depuis `tools/`
- `imagehash` library : supporte `ahash()`, `dhash()`, `phash()` — toutes retournent un `ImageHash` avec opérateur `-` pour la Hamming Distance

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/map_config_generator.py` | Implémentation existante pHash — pattern de référence pour le pipeline crop→grayscale→canvas→hash |
| `tools/frame_labeler.py` | Tool 2 — filtre actuellement `*score*.png` uniquement (ligne 57), à étendre pour `*start*` et `*end*` |
| `config/config.yaml` | Config centralisée — section `map_identification` existante avec ROI `map_name_hash` |
| `utils/image.py` | `extract_roi()`, `scale_roi()`, `to_grayscale()`, `downscale()` — réutilisables sans modification |
| `utils/video.py` | `extract_iframes_scaled()`, `get_video_info()` — si input vidéo nécessaire |
| `utils/config.py` | `load_config()` — chargement YAML standard |

### Technical Decisions

- **Hashing vs Pixels** : Le hashing est plus robuste aux variations de background derrière les éléments transparents du HUD. L'approche pixel-par-pixel est abandonnée.
- **Nouveau fichier `tools/hash_comparator.py`** : Tool 3 sera un outil séparé du `map_config_generator.py`. Il pourra réutiliser les mêmes utils mais aura sa propre logique de comparaison multi-hash.
- **Multi-hash comparison** : Tester aHash, dHash et pHash via `imagehash.ahash()`, `imagehash.dhash()`, `imagehash.phash()`. Toutes retournent un `ImageHash` compatible avec l'opérateur `-` (Hamming Distance).
- **ROI flexible** : Deux stratégies à tester — ROI sur le nom de map dans le HUD (toutes les I-frames) vs ROI sur l'écran de score (plus stable mais dépendant de la détection score). Les deux ROIs seront définies dans `config.yaml`.
- **Tool 2 étendu** : `frame_labeler.py` doit supporter les frames `*start*`, `*end*` en plus de `*score*`, pour fournir les données d'entrée à Tool 3 sur tous les types de frames.
- **Resolution sweep optionnel** : Pas de gain de performance significatif attendu, mais potentiellement utile pour la qualité du hash. Paramètre CLI optionnel.
- **Pas de tests formels** : Aucun framework de test n'est établi dans le projet. La validation se fait via Tool 4 (accuracy reports).

## Implementation Plan

### Tasks

- [x] Task 1: Extend Frame Labeler to support start/end frame types
  - File: `tools/frame_labeler.py`
  - Action: Replace `find_score_images()` with a generic `find_frame_images()` that accepts a `--type` CLI arg (`score`, `start`, `end`, `all`). Default to `all` to find `*score*`, `*start*`, and `*end*` PNG files. Update the `argparse` section to add `--type` flag.
  - Notes: The labeled output structure stays `<output>/labeled/<map_name>/` — the frame type is preserved in the filename (e.g. `07m12s_start_001.png`). No change to the GUI itself.

- [x] Task 2: Add score screen ROI to config
  - File: `config/config.yaml`
  - Action: Add a second ROI entry under `map_identification` for the score screen zone. Add a `hash_methods` list and optional `resolutions` list.
  - Notes: New config structure:
    ```yaml
    map_identification:
      rois:
        - name: map_name_hud
          x: 827
          y: 79
          width: 264
          height: 22
        - name: score_screen_map
          x: TBD
          y: TBD
          width: TBD
          height: TBD
      canvas_size: 64
      hash_size: 8
      hash_methods: [ahash, dhash, phash]
      collision_threshold: 12
      resolutions: []  # optional, e.g. [1080, 720, 540, 360]
    ```
  - Notes: The score screen ROI coordinates need to be determined by the user using the image inspector tool. `resolutions: []` means no sweep (use source resolution only).

- [x] Task 3: Create `tools/hash_comparator.py` — core structure and CLI
  - File: `tools/hash_comparator.py` (new)
  - Action: Create new CLI tool with `argparse`. Arguments:
    - `--images DIR` (required) — path to labeled directory (`<output>/labeled/`) with `<map_name>/` subdirectories
    - `--roi NAME` — which ROI to use from config (default: all configured ROIs)
    - `--methods` — which hash methods to test (default: all from config)
    - `--resolutions` — optional resolution sweep list (overrides config)
    - `--preview` — write processed canvas images for visual inspection
    - `-o, --output-dir` — output directory
    - `-c, --config` — config file path
  - Notes: Follow `map_config_generator.py` patterns: same import style, `sys.path.insert`, `load_config()`, etc.

- [x] Task 4: Implement multi-hash generation logic
  - File: `tools/hash_comparator.py`
  - Action: Implement core functions:
    - `compute_hash(canvas, hash_size, method)` — dispatches to `imagehash.ahash()`, `imagehash.dhash()`, or `imagehash.phash()` based on method string
    - `process_map_frames(map_dir, roi, canvas_size)` — loads all frames from a map subdirectory, crops ROI, converts to grayscale, resizes to canvas, returns list of canvases
    - `generate_hashes(map_canvases, hash_size, methods)` — for each map and each method, compute hash on each frame. Use the **median hash** (most common hash across frames) as the representative hash for that map+method combo.
  - Notes: Using median/mode hash across multiple frames per map increases robustness vs single-frame approach of `map_config_generator.py`.

- [x] Task 5: Implement collision detection and comparison report
  - File: `tools/hash_comparator.py`
  - Action: Implement:
    - `check_collisions(hash_dict, threshold)` — reuse pattern from `map_config_generator.py`. For each method, compute all pairwise Hamming Distances. Flag collisions below threshold.
    - `generate_report(results, output_dir)` — produce a `hash_comparison_report.json` with:
      - Per method: all pairwise distances, min/max/mean distance, collision count, collision pairs
      - Per ROI (if multiple): same breakdown
      - Recommendation: which method+ROI has the best separation (highest minimum distance)
    - Print a human-readable summary to stdout
  - Notes: The report is the key deliverable — it tells the user which hash method and ROI to use.

- [x] Task 6: Implement optional resolution sweep
  - File: `tools/hash_comparator.py`
  - Action: If `--resolutions` is provided or `resolutions` is non-empty in config, repeat the hash generation at each resolution (downscale frames before ROI extraction using `utils/image.downscale()`). Include resolution as a dimension in the report.
  - Notes: Optional feature. When not specified, use frames at source resolution only.

- [x] Task 7: Generate `map_config.json` output
  - File: `tools/hash_comparator.py`
  - Action: After comparison, generate a `map_config.json` using the best-performing method+ROI combination. Format matches existing `map_config_generator.py` output for compatibility:
    ```json
    {
      "reference_resolution": {"width": 1920, "height": 1080},
      "roi": {"x": 827, "y": 79, "width": 264, "height": 22},
      "canvas_size": 64,
      "hash_size": 8,
      "hash_method": "phash",
      "maps": {"frostbite": "a1b2c3d4e5f6a7b8", ...}
    }
    ```
  - Notes: Adds `hash_method` field compared to existing format. The best method is auto-selected based on highest minimum pairwise distance.

### Acceptance Criteria

- [x] AC 1: Given a labeled directory with start/end/score frames for 14 maps, when running `python tools/hash_comparator.py --images path/to/labeled`, then the tool generates hashes for all 3 methods (aHash, dHash, pHash) on the default ROI and prints a comparison summary.
- [x] AC 2: Given a labeled directory, when running with `--roi map_name_hud`, then only the HUD map name ROI is used for hashing.
- [x] AC 3: Given 14 maps with distinct visual characteristics, when computing pairwise Hamming Distances, then at least one hash method produces zero collisions (min distance >= collision_threshold).
- [x] AC 4: Given the comparison results, when the tool completes, then a `hash_comparison_report.json` is written with per-method pairwise distances, collision counts, and a recommendation.
- [x] AC 5: Given the comparison results, when the tool completes, then a `map_config.json` is written using the best-performing method.
- [x] AC 6: Given `--preview` flag, when running the tool, then processed canvas images are written to the output directory for visual inspection.
- [x] AC 7: Given the Frame Labeler with `--type start`, when scanning a source directory, then only `*start*.png` files are displayed for labeling.
- [x] AC 8: Given an invalid `--images` path or empty labeled directory, when running the tool, then a clear error message is printed and the process exits with non-zero code.
- [x] AC 9: Given `--resolutions 1080,720,360`, when running the tool, then the report includes hash comparisons at each resolution and identifies the optimal resolution.

## Additional Context

### Dependencies

- **imagehash >= 4.2** — already in `requirements.txt`. Provides `ahash()`, `dhash()`, `phash()`.
- **Pillow** — installed transitively via imagehash. Required for `Image.fromarray()`.
- **OpenCV >= 4.8** — already in `requirements.txt`. Used for `cv2.resize()`, `cv2.imread()`.
- **NumPy** — already in `requirements.txt`.
- **Tool 2 labeled data** — Tool 3 consumes the output of Frame Labeler. At least a few frames per map must be labeled before running Tool 3.
- **Score screen ROI coordinates** — need to be determined by the user via the image inspector tool before Task 2 can be fully completed. Use placeholder `TBD` values initially.

### Testing Strategy

- **Manual validation**: Run `hash_comparator.py` on the existing labeled data and verify the report makes sense.
- **Visual inspection**: Use `--preview` to verify ROI extraction and canvas processing are correct.
- **Collision check**: The primary test is that at least one method produces zero collisions across all 14 maps.
- **Cross-validation with map_config_generator**: Run both tools on the same data and verify pHash results match.
- **Tool 4 (future)**: Full accuracy validation will be handled by Tool 4 (Validator) which is out of scope for this spec.

### Notes

- **14 maps, not 15**: The `frame_labeler.py` lists 14 maps. `description.md` mentions 15 — the discrepancy should be clarified but doesn't affect the tool design.
- **Median hash strategy**: Using the most common hash across multiple frames per map is more robust than single-frame hashing. If frames within a map produce different hashes, this indicates instability for that ROI — useful diagnostic info.
- **map_config_generator.py coexistence**: The new `hash_comparator.py` does not replace `map_config_generator.py`. They can coexist. Once a best method is validated, `map_config_generator.py` could be updated to use that method, but that's out of scope.
- **Future consideration**: If no hash method achieves zero collisions on any single ROI, a multi-ROI composite approach (combining hashes from different ROIs) could be explored. Out of scope for this spec.

## Review Notes

- Adversarial review completed (2026-03-19)
- Findings: 12 total, 3 fixed, 9 skipped (noise/design choice/already handled)
- Resolution approach: auto-fix
- F5 fixed: `build_canvases` no longer uses `src_h` for downscale gating — always calls `downscale()` which handles the no-upscale case, fixing correctness for mixed-resolution inputs
- F8 fixed: `generate_map_config` now safely handles `None` roi_entry with a warning instead of AttributeError
- F2 fixed: `find_frame_images` globs changed to `*_score*.png` / `*_start*.png` / `*_end*.png` (underscore prefix) to reduce false matches
