# Methode de detection par ROI -- Warden-tooling

> Document technique destine au workflow BMAD de l'application Warden.
> Decrit le systeme de detection des transitions de manches (start/end),
> la capture des ecrans de score, et l'identification des maps.

## 1. Vue d'ensemble

Le pipeline de detection repose sur l'analyse de **Regions d'Interet (ROI)** definies a une resolution de reference de **1920x1080**. Ces ROI sont automatiquement mises a l'echelle proportionnellement a la resolution de traitement (720p par defaut).

Deux detecteurs complementaires exploitent ces ROI :

| Detecteur | Fichier | ROI utilisees | Methode |
|-----------|---------|---------------|---------|
| **Black Screen Detector** | `tools/black_screen_detector.py` | `minimap`, `vertical`, `team_bar` | Luminosite (niveaux de gris) |
| **Game Detector** | `tools/game_detector.py` | `kda`, `notkda` | Pixels blancs (HSV) |

---

## 2. Definition des ROI

Toutes les ROI sont definies dans `config/config.yaml` (section `roi_zones`) aux coordonnees de la resolution de reference 1920x1080.

### 2.1 ROI de detection des transitions (Black Screen Detector)

```
  minimap:  (104, 0)    234x38    -- Zone de la minimap en haut a gauche
  vertical: (104, 0)    22x264    -- Bande verticale gauche de la minimap
  team_bar: (430, 1015) 1060x65   -- Barre d'equipe en bas de l'ecran
```

**minimap** et **vertical** sont les deux ROI primaires. Elles couvrent la zone de la minimap du HUD. En jeu, cette zone affiche la carte. En ecran de chargement ou de transition, elle est entierement noire.

**team_bar** est utilisee uniquement dans le mode deux passes (videos a GOP > 2s). Elle detecte la presence de couleurs d'equipe saturees (orange/bleu).

### 2.2 ROI KDA et notKDA (Game Detector)

```
  kda:      (1197, 1000) 10x16    -- Zone d'affichage du KDA (kills/deaths/assists)
  notkda:   (1215, 1000) 18x16    -- Zone adjacente au KDA pour validation du HUD
```

**kda** est une petite zone en bas a droite de l'ecran ou le texte blanc du compteur KDA apparait pendant le jeu. Le texte est blanc (faible saturation, haute valeur).

**notkda** est la zone immediatement a droite du KDA. Elle sert de garde-fou : en jeu, cette zone est relativement sombre (luminosite grise 22-68). Sur l'ecran de score, toute cette zone devient bien plus lumineuse (136+). Cela permet de distinguer un etat "en jeu" d'un ecran de score.

### 2.3 ROI auxiliaires

```
  map_name:     (827, 79)  264x22   -- Nom de la map affiche dans le HUD
  points:       (956, 42)  6x15     -- Score/points dans le HUD
  personnalbar: (648, 990) 12x20    -- Barre personnelle (reserve future)
```

### 2.4 Mise a l'echelle

Les coordonnees sont converties de la resolution de reference vers la resolution de traitement via un facteur d'echelle :

```
scale_factor = target_height / reference_height   (ex: 720 / 1080 = 0.667)

new_x      = int(roi.x * scale_factor)
new_y      = int(roi.y * scale_factor)
new_width  = max(1, int(roi.width * scale_factor))
new_height = max(1, int(roi.height * scale_factor))
```

Voir `utils/image.py`, fonction `scale_roi()`.

---

## 3. Detection des starts et ends de manches

### 3.1 Methode 1 : Black Screen Detector (luminosite)

#### Principe

Le jeu EVA affiche un **ecran noir** (loading screen) entre chaque manche. Le detecteur repere ces transitions noir <-> non-noir sur les ROI `minimap` et `vertical`.

#### Machine a etats (3 etats)

```
                    premiere transition
  [undetermined] ──────────────────────────> [waiting_for_end]
        │                                          │
        │ premiere transition                      │ non-noir -> noir
        ▼                                          ▼
  [waiting_for_start] <────────────────── detection END
        │
        │ noir -> non-noir (confirme)
        ▼
  [waiting_for_end]  ← detection START
```

**undetermined** : Etat initial. Le premier frame est enregistre, puis le systeme observe la premiere transition (quelle qu'elle soit) pour determiner dans quel sens evolue le flux.

**waiting_for_end** : Le jeu est en cours. On cherche le moment ou toutes les ROI deviennent noires (= fin de manche).

**waiting_for_start** : Le jeu a fini. On cherche le retour a un ecran non-noir (= debut de la manche suivante).

#### Algorithme de detection par frame

Pour chaque I-frame extraite de la video :

1. **Conversion en niveaux de gris** du frame complet
2. **Extraction des ROI** `minimap` et `vertical` depuis l'image grise
3. **Test de noirceur** : une ROI est "noire" si `mean(pixels) <= brightness_threshold` (defaut: **15**)
4. **Combinaison** : `is_end_loading = true` si TOUTES les ROI de detection sont noires
5. **Logique de transition** selon l'etat courant :
   - **END** : transition de non-noir vers noir → on enregistre le timestamp du frame precedent
   - **START** : transition de noir vers non-noir → necessite `start_confirm_frames` (defaut: **2**) frames consecutifs non-noirs apres avoir vu un ecran de chargement

#### Confirmation du START

Le START a une validation plus stricte que le END :

1. Le systeme doit d'abord voir un ecran de chargement (`minimap` ET `vertical` noirs) → `saw_black_in_wait = true`
2. Ensuite, il faut `start_confirm_frames` frames consecutifs ou les DEUX ROI (`minimap` ET `vertical`) sont individuellement non-noires
3. Le timestamp retenu est celui du **premier** frame confirmant

Cela evite les faux positifs sur les ecrans de lobby qui apparaissent entre la fin d'une manche et le chargement de la suivante.

#### Parametres cles

| Parametre | Valeur | Description |
|-----------|--------|-------------|
| `brightness_threshold` | 15 | Seuil de noirceur (0-255) |
| `skip_duration` | 15.0s | Duree de skip apres un END pour eviter les doublons |
| `start_confirm_frames` | 2 | Frames consecutifs non-noirs pour confirmer un START |
| `pre_end_offset` | 10.0s | Secondes avant le END pour capturer un snapshot pre-fin |

### 3.2 Methode 2 : Game Detector (KDA / notKDA)

#### Principe

Au lieu de detecter les ecrans noirs, ce detecteur identifie la **presence du HUD de jeu** en cherchant du texte blanc dans la zone KDA. C'est une detection positive ("je suis en jeu") plutot que negative ("l'ecran est noir").

#### Machine a etats (2 etats)

```
                 blanc detecte (confirme)
  [not_in_game] ───────────────────────> [in_game]
        ^                                    │
        │       blanc absent (confirme)      │
        └────────────────────────────────────┘
```

#### Algorithme de detection par frame

Pour chaque I-frame :

1. **Extraction de la ROI `kda`** (en BGR, pas de conversion grise)
2. **Detection de pixels blancs** via analyse HSV :
   - Conversion BGR → HSV
   - Un pixel est "blanc" si : `saturation <= 12` ET `valeur >= 230`
   - La zone est "blanche" si le ratio de pixels blancs >= **1%** (`min_ratio: 0.01`)
3. **Si blanc detecte** → verification avec la ROI `notkda` :
   - Conversion de `notkda` en niveaux de gris
   - Calcul de la luminosite moyenne
   - Validation : `luminosite_moyenne < hud_brightness_max` (defaut: **100**)
   - En jeu : la zone `notkda` a une luminosite de 22-68 → **valide**
   - Ecran de score : luminosite de 136+ → **rejete** (pas vraiment "en jeu")

#### Logique de confirmation

- **START** : `start_confirm_frames` (defaut: **2**) frames consecutifs avec blanc detecte
- **END** : `end_confirm_frames` (defaut: **3**) frames consecutifs sans blanc detecte

Le nombre de frames de confirmation pour le END est plus eleve (3 vs 2) pour eviter les faux positifs lors de transitions breves pendant le jeu.

#### Parametres cles

| Parametre | Valeur | Description |
|-----------|--------|-------------|
| `sat_max` | 12 | Saturation max (0-255) pour classifier un pixel comme blanc |
| `val_min` | 230 | Valeur min (0-255) pour classifier un pixel comme blanc |
| `min_ratio` | 0.01 | Fraction min de pixels blancs (1%) |
| `hud_brightness_max` | 100 | Luminosite grise max de la zone `notkda` pour valider le HUD |
| `start_confirm_frames` | 2 | Frames consecutifs avec blanc pour confirmer START |
| `end_confirm_frames` | 3 | Frames consecutifs sans blanc pour confirmer END |

---

## 4. Detection de l'ecran de score

L'ecran de score est capture par le **Game Detector** uniquement, en utilisant un offset temporel apres la derniere frame confirmee "en jeu".

### Algorithme

1. Pendant l'etat `in_game`, chaque frame ou du blanc est detecte dans `kda` met a jour `last_in_game_timestamp`
2. Quand le END est confirme (3 frames sans blanc), le score screen est calcule :
   ```
   score_timestamp = last_in_game_timestamp + score_offset
   ```
   avec `score_offset = 14.5 secondes` par defaut
3. Une frame pleine resolution est extraite a ce timestamp et exportee en PNG

### Pourquoi 14.5 secondes ?

Apres la derniere frame ou le KDA est visible, le jeu transite vers l'ecran de score via une animation. Le delai de 14.5s correspond au temps moyen observe pour que l'ecran de score soit pleinement affiche et lisible.

### Distinction jeu vs ecran de score via notkda

La ROI `notkda` joue un role critique ici. Sans elle, le detecteur confondrait l'ecran de score avec une partie en cours (le texte blanc est present dans les deux cas). La luminosite de `notkda` discrimine les deux :

| Contexte | Luminosite moyenne `notkda` | Classification |
|----------|----------------------------|----------------|
| En jeu (HUD actif) | 22 - 68 | ✓ Valide comme "in_game" |
| Ecran de score | 136+ | ✗ Rejete (pas "in_game") |
| Lobby / menu | Variable | ✗ Rejete (pas de blanc dans `kda`) |

---

## 5. Identification des maps par ROI + HSV

L'identification des maps utilise une approche differente : le **hachage perceptuel** (pHash) sur la ROI `map_name`.

### 5.1 ROI dediee

```
  map_name_hash: (827, 79) 264x22   -- Zone du nom de map dans le HUD
```

Cette ROI capture le texte du nom de la carte affiche en haut de l'ecran pendant le jeu (ex: "Frostbite", "Reactor", etc.).

### 5.2 Pipeline de generation des hash

Le fichier `tools/map_config_generator.py` genere un fichier `map_config.json` contenant le hash perceptuel de chaque map connue.

```
Frame source
    │
    ▼
[1] Extraction de la ROI map_name (264x22 pixels @ 1080p)
    │
    ▼
[2] Conversion en niveaux de gris (BGR → Gray)
    │
    ▼
[3] Redimensionnement sur un canvas fixe de 64x64 pixels
    │
    ▼
[4] Calcul du hash perceptuel (pHash) de 64 bits (hash_size=8 → 8x8 bits)
    │
    ▼
[5] Stockage dans map_config.json : {"map_name": "hash_string"}
```

### 5.3 Identification en temps reel

Pour identifier la map sur un nouveau frame de video :

1. Extraire la ROI `map_name` du frame
2. Appliquer le meme pipeline : grayscale → resize 64x64 → pHash
3. Calculer la **distance de Hamming** entre le hash obtenu et chaque hash stocke dans `map_config.json`
4. La map avec la distance la plus faible est le resultat (si sous le seuil)

### 5.4 Gestion des collisions

Chaque paire de maps est verifiee pour les collisions potentielles. Si la distance de Hamming entre deux maps est inferieure au seuil de collision (`collision_threshold = 12`), un warning est emis car les maps sont trop similaires pour etre distinguees de maniere fiable.

### 5.5 Format de sortie

```json
{
  "reference_resolution": { "width": 1920, "height": 1080 },
  "roi": { "x": 827, "y": 79, "width": 264, "height": 22 },
  "canvas_size": 64,
  "hash_size": 8,
  "maps": {
    "frostbite": "a1b2c3d4e5f6a7b8",
    "reactor": "f1e2d3c4b5a6c7d8"
  }
}
```

### 5.6 Parametres cles

| Parametre | Valeur | Description |
|-----------|--------|-------------|
| `canvas_size` | 64 | Taille du canvas carre pour le hachage |
| `hash_size` | 8 | Dimension du hash (8 → 64 bits) |
| `collision_threshold` | 12 | Distance de Hamming min entre deux maps |

---

## 6. Mode deux passes (videos a long GOP)

Pour les videos dont l'intervalle GOP depasse 2 secondes, le Black Screen Detector utilise un mode adaptatif en deux passes.

### Passe 1 : Prescan rapide

- Parcours de toutes les I-frames via extraction par pipe unique
- Analyse de la ROI `team_bar` pour la **saturation des couleurs d'equipe** :
  - Conversion BGR → HSV
  - Calcul de `mean(saturation)` sur la ROI
  - Si `mean_saturation > 90` → couleurs d'equipe presentes (= en jeu)
- Detection des transitions entre "en jeu" et "hors jeu"
- Collecte de tous les timestamps d'I-frames pour reutilisation

### Passe 2 : Scan cible

- Construction de fenetres de scan autour des transitions detectees : `[transition - 30s, transition + 30s]`
- Fusion des fenetres qui se chevauchent
- Extraction de frames a intervalles de 2 secondes dans chaque fenetre
- Alignement sur l'I-frame la plus proche (tolerance de 0.5s)
- Application de la logique normale de detection par ecrans noirs

Ce mode reduit considerablement le temps de traitement sur les longues videos en concentrant l'analyse sur les zones pertinentes.

---

## 7. Analyse HSV -- Resume des seuils

L'espace colorimetrique HSV (Teinte, Saturation, Valeur) est utilise pour trois types de detection :

### 7.1 Detection de pixels blancs (KDA)

```python
hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
mask = (hsv[:, :, 1] <= sat_max) & (hsv[:, :, 2] >= val_min)
#       saturation <= 12            valeur >= 230
ratio = count_nonzero(mask) / total_pixels
est_blanc = ratio >= 0.01  # au moins 1% de pixels blancs
```

### 7.2 Detection des couleurs d'equipe (team_bar)

```python
hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
mean_saturation = mean(hsv[:, :, 1])  # canal saturation
a_couleur_equipe = mean_saturation > 90
```

### 7.3 Validation HUD (notkda)

```python
gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
luminosite = mean(gray)
est_en_jeu = luminosite < 100    # en jeu: 22-68, score: 136+
```

### 7.4 Couleurs de reference

Definies dans `config/config.yaml` :

| Couleur | H | S | V | Usage |
|---------|---|---|---|-------|
| Orange | 31 | 100 | 91 | Equipe orange |
| Bleu | 214 | 89 | 100 | Equipe bleue |
| Blanc | 0 | 0 | 100 | Texte KDA / HUD |

---

## 8. Schema d'architecture global

```
                    VIDEO SOURCE
                         │
                         ▼
              ┌─────────────────────┐
              │  FFmpeg I-frame     │
              │  extraction         │
              │  (skip_frame nokey) │
              └──────────┬──────────┘
                         │
                    Frame BGR scalee
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌───────────┐   ┌───────────┐   ┌───────────┐
   │ minimap + │   │  kda +    │   │ map_name  │
   │ vertical  │   │  notkda   │   │           │
   │ (Gray)    │   │ (HSV)     │   │ (pHash)   │
   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
         │               │               │
         ▼               ▼               ▼
   Black Screen    Game State       Map Identity
   START / END     START / END      "Frostbite"
                   + SCORE SCREEN   "Reactor"...
```

---

## 9. Fichiers de reference

| Fichier | Role |
|---------|------|
| `config/config.yaml` | Toutes les definitions de ROI, seuils, et parametres |
| `tools/black_screen_detector.py` | Detection start/end par ecrans noirs |
| `tools/game_detector.py` | Detection start/end/score par KDA |
| `tools/map_config_generator.py` | Generation des hash de maps |
| `utils/image.py` | Fonctions d'image : `scale_roi`, `is_black`, `has_white_pixels`, `has_team_color` |
| `utils/video.py` | Extraction de frames via FFmpeg |
