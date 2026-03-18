---
title: 'Hashing Workflow for Map Identification (Tool 3)'
slug: 'hashing-workflow-tool3'
created: '2026-03-18'
status: 'in-progress'
stepsCompleted: [1]
tech_stack: ['python', 'imagehash', 'opencv', 'pillow']
files_to_modify: []
code_patterns: []
test_patterns: []
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

- Modular CLI Pipeline : chaque tool est un CLI indépendant dans `tools/`
- ROI définie à résolution de référence 1920×1080, scalée au runtime
- Config-driven : tous les paramètres dans `config/config.yaml`
- File-based I/O entre tools (Tool 2 produit les frames labelisées → Tool 3 les consomme)
- `map_config_generator.py` est un précédent direct — utilise pHash sur ROI texte du nom de carte

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/map_config_generator.py` | Implémentation existante pHash — base de référence |
| `tools/frame_labeler.py` | Tool 2 actuel — à modifier pour exporter start/end/score |
| `config/config.yaml` | Configuration centralisée (ROI, paramètres hash) |
| `utils/image.py` | Utilitaires image (grayscale, ROI extraction, downscale) |
| `description.md` | Spec originale Tool 3 (approche pixel — remplacée) |
| `_bmad-output/implementation-artifacts/tech-spec-map-config-generator.md` | Tech spec du map_config_generator |

### Technical Decisions

- **Hashing vs Pixels** : Le hashing est plus robuste aux variations de background derrière les éléments transparents du HUD. L'approche pixel-par-pixel est abandonnée.
- **Multi-hash comparison** : Tester aHash, dHash et pHash permet de choisir la méthode la plus fiable empiriquement.
- **ROI flexible** : Deux stratégies à tester — ROI sur le nom de map dans le HUD (toutes les I-frames) vs ROI sur l'écran de score (plus stable mais dépendant de la détection score).
- **Resolution sweep optionnel** : Pas de gain de performance significatif attendu, mais potentiellement utile pour la qualité du hash.

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
