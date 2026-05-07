---
title: 'Anchor-Based Map Name Sub-ROI for Hash Comparator'
slug: 'map-name-anchor-subroi'
created: '2026-03-19'
status: 'Implementation Complete'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['python3.8+', 'opencv>=4.8', 'numpy', 'imagehash>=4.2']
files_to_modify: ['utils/image.py', 'tools/hash_comparator.py', 'config/config.yaml']
code_patterns: ['ROI at 1920x1080 reference resolution', 'scale_roi() for proportional scaling', 'config-driven via YAML', 'build_canvases() pipeline in hash_comparator.py', 'HSV white detection: sat_max=12 val_min=230', 'None param = feature disabled (backward compat)']
test_patterns: ['none established']
---

# Tech-Spec: Anchor-Based Map Name Sub-ROI for Hash Comparator

**Created:** 2026-03-19

## Overview

### Problem Statement

Le ROI `map_name_hud` (x=827, y=81, w=267, h=22 @1080p) couvre toute la zone texte du HUD. Selon le contexte de jeu, le texte affiché est soit uniquement le nom de la carte (ex. "Silva"), soit le nom suivi d'un suffixe de contexte (" - BO3" ou " - BO5"). Ce suffixe est inclus dans le hash perceptuel, ce qui peut produire des hashes différents pour la même carte selon le contexte — source de collisions ou de faux négatifs lors de l'identification.

### Solution

Avant de hasher, scanner le ROI colonne par colonne pour localiser le premier pixel blanc (ancre de début du texte). Extraire un sous-ROI de largeur fixe (52px @1080p, configurable) à partir de cette ancre — cette largeur couvre le nom le plus court (Silva/Ceres) sans inclure le suffixe " - BO3" / " - BO5". Si aucun pixel blanc n'est trouvé (frame incorrecte ou trop lumineuse), la frame est ignorée sans erreur.

### Scope

**In Scope:**
- Nouvelle fonction `find_text_anchor()` dans `utils/image.py` — scan colonne par colonne, retourne le x du premier pixel blanc (ou -1 si non trouvé)
- Modification de `build_canvases()` dans `tools/hash_comparator.py` pour utiliser l'ancre et extraire le sous-ROI de largeur `text_anchor_width`
- Threading du paramètre à travers `run_comparison()` et `main()`
- Ajout de `text_anchor_width: 52` dans `config.yaml` sous `map_identification` (en pixels @1080p)
- Skip silencieux de la frame si ancre non trouvée
- `tile_cols` appliqué au sous-ROI résultant (comportement inchangé)

**Out of Scope:**
- `tools/map_config_generator.py` (outil legacy, non modifié)
- Autres zones ROI (minimap, kda, points, etc.)
- Modification de la logique de tiling elle-même

## Context for Development

### Codebase Patterns

- ROI définie à résolution de référence 1920×1080, scalée au runtime via `utils/image.scale_roi()`
- `build_canvases()` dans `tools/hash_comparator.py` orchestre : downscale → scale_roi → extract_roi → to_grayscale → tile_into_canvas
- `has_white_pixels()` dans `utils/image.py` utilise HSV (`sat_max=12, val_min=230`) — même seuils à réutiliser pour le scan colonne
- Config-driven : tous paramètres dans `config/config.yaml`, chargés via `utils/config.load_config()`
- `text_anchor_width` exprimé en pixels @1080p (référence), à scaler comme le ROI parent
- Pattern `None` = feature désactivée pour backward compat — pas de changement de comportement si paramètre absent

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `utils/image.py` | Ajouter `find_text_anchor()` après `has_white_pixels()` (après ligne 164) |
| `tools/hash_comparator.py` | Modifier `build_canvases()` (ligne 175), `run_comparison()` (ligne 262), `main()` |
| `config/config.yaml` | Ajouter `text_anchor_width: 52` sous `map_identification` après `tile_cols` (ligne 146) |

### Technical Decisions

- **Seuils HSV** : `sat_max=12, val_min=230` — identiques à `has_white_pixels()`, validés pour le texte blanc sur fond sombre semi-transparent
- **52px @1080p** : largeur mesurée empiriquement sur les noms les plus courts (Silva, Ceres). Scalée proportionnellement : `scaled_w = max(1, int(text_anchor_width * (fh / REF_HEIGHT)))` — même pattern que `scale_roi()`
- **Fallback = skip** : frame discardée (`continue`) si `find_text_anchor()` retourne -1. Pas de fallback sur le ROI complet — comportement explicitement exclu
- **Scan sur BGR** : `find_text_anchor()` reçoit le crop BGR (avant `to_grayscale()`), converti en HSV en interne — même pattern que `has_white_pixels()`
- **`tile_cols` inchangé** : appliqué sur le sous-ROI de 52px (à 720p ≈ 34px), la config existante reste valide
- **Backward compat** : `text_anchor_width=None` dans les fonctions Python = feature désactivée. Si absent du config → `None` (comportement ancien, ROI complet)
- **Clamping du sous-ROI** : si `anchor_x + scaled_w > cropped.shape[1]`, utiliser `cropped.shape[1]` comme borne droite (ne pas skip — le nom est là, juste tronqué à droite)

## Implementation Plan

### Tasks

- [x] Task 1: Ajouter `find_text_anchor()` dans `utils/image.py`
  - File: `utils/image.py`
  - Action: Insérer la fonction suivante après `has_white_pixels()` (après ligne 164) :
    ```python
    def find_text_anchor(bgr_crop, sat_max=12, val_min=230):
        """Scan the crop left-to-right and return the x of the first column containing a white pixel.

        A pixel is considered white if its HSV saturation <= sat_max and value >= val_min.

        Args:
            bgr_crop: BGR numpy array (height, width, 3).
            sat_max: Maximum saturation (0-255) for a pixel to count as white.
            val_min: Minimum value (0-255) for a pixel to count as white.

        Returns:
            int: x index of the first column with at least one white pixel, or -1 if none found.
        """
        if bgr_crop.ndim != 3 or bgr_crop.shape[2] != 3:
            return -1
        if bgr_crop.shape[0] == 0 or bgr_crop.shape[1] == 0:
            return -1
        hsv = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        for col_x in range(bgr_crop.shape[1]):
            if np.any((sat[:, col_x] <= sat_max) & (val[:, col_x] >= val_min)):
                return col_x
        return -1
    ```
  - Notes: Pas de nouvelles dépendances (cv2 et numpy déjà importés). Retourne -1 si crop invalide, vide, ou sans pixel blanc.

- [x] Task 2: Ajouter `text_anchor_width` dans `config/config.yaml`
  - File: `config/config.yaml`
  - Action: Insérer après `tile_cols: 3` (ligne 146) :
    ```yaml
      # Width in pixels @reference resolution (1920x1080) of the sub-ROI to hash,
      # anchored to the first white pixel column found in the ROI.
      # Set to 0 or omit to disable anchor cropping (use full ROI).
      text_anchor_width: 52
    ```
  - Notes: Valeur à 1080p — sera scalée proportionnellement dans `build_canvases()`. 52px couvre Silva et Ceres (noms les plus courts mesurés empiriquement).

- [x] Task 3: Modifier `build_canvases()` dans `tools/hash_comparator.py`
  - File: `tools/hash_comparator.py`
  - Action 1: Ajouter `text_anchor_width=None` à la signature (ligne 175) et à la docstring.
  - Action 2: Ajouter l'import de `find_text_anchor` dans la ligne d'import de `utils/image` (ligne 39) :
    ```python
    from utils.image import downscale, extract_roi, find_text_anchor, scale_roi, to_grayscale
    ```
  - Action 3: Insérer le bloc d'ancrage après `extract_roi()` (ligne 209) et avant `to_grayscale()` (ligne 213) :
    ```python
        if text_anchor_width:
            scaled_anchor_w = max(1, int(text_anchor_width * (fh / REF_HEIGHT)))
            anchor_x = find_text_anchor(cropped)
            if anchor_x == -1:
                print(
                    f"  Warning: No text anchor found in {fname}, skipping",
                    file=sys.stderr,
                )
                continue
            right = min(anchor_x + scaled_anchor_w, cropped.shape[1])
            cropped = cropped[:, anchor_x:right]
    ```
  - Notes: `fh` est déjà disponible à ce point (ligne 197 : `fh, fw = frame.shape[:2]`). Le clamping `min(...)` évite un out-of-bounds si l'ancre est proche du bord droit.

- [x] Task 4: Threader `text_anchor_width` à travers `run_comparison()`
  - File: `tools/hash_comparator.py`
  - Action: Ajouter `text_anchor_width=None` à la signature de `run_comparison()` (ligne 262) et à sa docstring. Passer `text_anchor_width=text_anchor_width` dans l'appel à `build_canvases()` (ligne 310).

- [x] Task 5: Lire `text_anchor_width` depuis le config dans `main()` et passer à `run_comparison()`
  - File: `tools/hash_comparator.py`
  - Action 1: Ajouter après la ligne qui lit `tile_cols` (ligne 621) :
    ```python
    text_anchor_width = map_id.get("text_anchor_width") or None
    ```
  - Action 2: Ajouter dans le bloc print de résumé :
    ```python
    print(f"  Anchor width: {text_anchor_width or 'disabled'}px @1080p")
    ```
  - Action 3: Passer `text_anchor_width=text_anchor_width` dans l'appel à `run_comparison()` (ligne 641).

### Acceptance Criteria

- [x] AC 1: Given une frame avec le texte du nom de carte visible dans le ROI HUD, when `build_canvases()` est appelé avec `text_anchor_width=52`, then le canvas est construit depuis un sous-ROI de `max(1, int(52 * fh/1080))` pixels de large commençant à la première colonne avec pixel blanc.

- [x] AC 2: Given des frames de la même carte labellisées avec et sans suffixe " - BO3" dans le texte HUD, when hashées avec anchor activé (`text_anchor_width=52`), then les hashes représentatifs sont identiques (Hamming Distance = 0) ou restent en dessous du `collision_threshold`.

- [x] AC 3: Given une frame sans pixel blanc dans le ROI (écran noir, transition, frame incorrecte), when `build_canvases()` est appelé avec `text_anchor_width` activé, then la frame est skippée (avertissement stderr, non incluse dans les canvases), sans crash.

- [x] AC 4: Given `text_anchor_width` absent du config ou mis à 0, when le pipeline tourne, then le comportement est identique à l'implémentation précédente (ROI complet hashé, aucune colonne scannée).

- [x] AC 5: Given `text_anchor_width: 52` dans `config.yaml`, when `main()` s'exécute, then la valeur 52 est affichée dans le résumé CLI et passée jusqu'à `build_canvases()`.

- [x] AC 6: Given une frame où la première colonne blanche est à moins de 52px du bord droit du ROI (ancre proche du bord), when le sous-ROI est extrait, then `cropped[:, anchor_x : min(anchor_x + scaled_w, cropped.shape[1])]` est utilisé — pas d'IndexError, pas de skip.

## Additional Context

### Dependencies

- Pas de nouvelles dépendances Python — cv2 et numpy déjà importés dans `utils/image.py`
- `find_text_anchor` doit être importé dans `tools/hash_comparator.py` (ajout à l'import existant ligne 39)

### Testing Strategy

Pas de framework de test établi. Tests manuels recommandés :
1. Lancer `hash_comparator.py --images output/labeled/ --preview -o output/` avec `text_anchor_width: 52` activé
2. Inspecter les canvases preview pour vérifier que seul le nom est inclus (pas le suffixe)
3. Comparer le rapport avant/après pour valider que les min distances restent stables ou améliorées
4. Tester avec une frame de black screen pour vérifier le skip silencieux (warning stderr, pas de crash)

### Notes

- À 720p (processing), 52px @1080p → `int(52 * 720/1080)` = 34px. Le canvas final est de toute façon resizé à 64×64 via `tile_into_canvas`.
- Si `text_anchor_width` est configuré mais que toutes les frames d'une carte sont skippées (ancre jamais trouvée), `representative_hash()` reçoit une liste vide → `None` → la carte est exclue du rapport avec le warning existant "No valid canvases".
- Future consideration : exposer `sat_max`/`val_min` du scan dans le config si les seuils s'avèrent insuffisants pour d'autres cartes ou conditions d'éclairage.

## Review Notes

- Adversarial review completed (2026-03-19)
- Findings: 12 total, 3 fixed, 9 skipped (noise/design choice/future consideration)
- Resolution approach: auto-fix
- F5 fixed: `find_text_anchor` vectorisée avec `np.where` au lieu d'une boucle Python colonne par colonne
- F10 fixed: print statement `"Anchor width"` corrigé — n'affiche plus `"disabledpx @1080p"`
- F11 fixed: validation ajoutée — skip si le crop ancré est < 2px de large (hash dégénéré)
