---
title: 'Hashing Workflow for Map Identification (Tool 3)'
slug: 'hashing-workflow-tool3'
created: '2026-03-18'
status: 'in-progress'
stepsCompleted: [1, 2]
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

{tasks}

### Acceptance Criteria

{acceptance_criteria}

## Additional Context

### Dependencies

{dependencies}

### Testing Strategy

{testing_strategy}

### Notes

{notes}
