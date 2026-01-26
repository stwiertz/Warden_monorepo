# Synthèse Brainstorming - Warden

**Date:** 2026-01-26
**Techniques utilisées:** Role Playing, First Principles Thinking, SCAMPER Method

---

## Vision Produit

> **Warden** = Application mobile de review de matchs EVA After-h qui **augmente le coach** (sans le remplacer) via le découpage automatique par carte et la vue tactique minimap.

---

## Personas Validés

| Persona | Description | Relation à Warden |
|---------|-------------|-------------------|
| Coach | Crée les reviews, power user | A l'app, paye l'abonnement |
| Joueur Passif | Reçoit des clips | Pas besoin de l'app, influenceur d'achat |
| Joueur Actif | Regarde aussi les sessions, importe les reviews | A l'app, potentiel payant |

---

## Core Différenciateur (MVP)

### 1. Découpage Automatique par Carte
- Détection écran noir (transitions)
- Template matching (identification carte)
- Suppression lobby automatique
- Timeline segmentée façon "épisodes Netflix"

### 2. Vue Minimap (ROI Composition)
- Templates ROI pré-définis par carte
- Minimap centrée + killfeed + barres de vie
- Toggle POV / Minimap en un tap
- Le clip exporté = la vue custom

---

## Features MVP (V1)

| Feature | Description | Priorité |
|---------|-------------|----------|
| Découpage auto | Détection cartes par écran noir + template | Core |
| Vue Minimap | Composition ROI fixe par carte | Core |
| Commentaires vocaux | Enregistrer avant/pendant/après clip | Core |
| Emoji flags | Marqueurs rapides (fire, fail, question, idea) | High |
| Export clip standalone | Vidéo autonome lisible partout | Core |
| Export manifeste | Fichier léger pour joueur actif avec app | High |
| Navigation playlist | Précédent / Suivant | High |
| Toggle POV/Minimap | Bouton switch de vue | Core |
| Mode épisodes | Vue par carte (Netflix-style) | High |
| Mode highlights | Vue sections commentées uniquement | High |
| Vitesse lecture | 1x / 1.5x / 2x avec pause auto sur commentaires | Medium |
| Export direct ou batch | Choix du workflow | Medium |
| Notification fin montage | Alerte quand clips prêts | Medium |

---

## Features V2 (Post-MVP)

| Feature | Description |
|---------|-------------|
| OCR Scores/Kills | Extraction automatique killfeed, scores, timer |
| Stats par carte | Victoire/défaite, score final, captures |
| Export vertical | Format 9:16 pour stories/TikTok |
| Custom ROI (Desktop) | Templates personnalisés par le coach |

---

## Roadmap Mobile vers Desktop

**Mobile (V1)**
- Créer l'HABITUDE
- Friction minimale
- Sessions 5-10 min
- On-device simple

**Desktop (V2+)**
- PROFESSIONALISER
- Plus de customisation
- Analyses avancées
- Plus de compute

---

## Modèle Économique

| Principe | Détail |
|----------|--------|
| Coûts fixes > variables | Tout on-device, pas de cloud scaling |
| Upload = ennemi | Vidéo ne quitte jamais le téléphone |
| Coach = client payant | L'app est pour le créateur de review |
| Passif = influenceur | Voit la valeur, pousse le budget équipe |

---

## Workflow Utilisateur

### Coach
1. Download vidéo (YouTube/autre)
2. Import dans Warden
3. Découpage auto en épisodes
4. Regarde carte par carte
5. Toggle POV / Minimap
6. Flag moments (emoji)
7. Enregistre vocaux (avant/pendant/après)
8. Export direct OU batch
9. Notification "clips prêts"
10. Envoie via Discord/WhatsApp

### Joueur Passif
- Reçoit clip
- Regarde (any device)
- Répond (emoji/texte)

---

## Principes Clés

| Principe | Implication |
|----------|-------------|
| Le coach EST l'IA | Augmenter, pas remplacer |
| Habit first, pro later | Mobile simple puis Desktop avancé |
| Pas de lock-in joueur | Clips lisibles sans app |
| Sessions fragmentées | UX optimisée pour 5-10 min |
| Template > OCR | Performance on-device |
| YAGNI | Pas de features "au cas où" |

---

## Dual Mode Export

### Mode A: Export en Direct
- Je marque un moment + vocal
- Je tape "Exporter" - Clip généré immédiatement
- Je l'envoie tout de suite
- Pour: feedback urgent, un seul moment à partager

### Mode B: Export Batch (fin de session)
- Je marque plein de moments pendant la review
- À la fin: "Générer tous les clips"
- Montage en background - Notification
- Pour: review complète, plusieurs clips d'un coup

---

## Dual Mode Réception (Joueur Actif)

### Mode 1: Clips Standalone
- Clips individuels (~20 sec, jusqu'à 2 min)
- Exportables & partageables (WhatsApp, Discord...)
- Lisibles sur N'IMPORTE QUEL device
- Voix intégrée dans le fichier vidéo

### Mode 2: Review Globale Importable
- Fichier "manifeste" (timestamps + refs vocaux)
- Le joueur DOIT avoir la vidéo dans Warden
- Navigation intelligente entre clips
- Vidéo se PAUSE pendant les vocaux "pause"
- Option: voir que les clips OU la vidéo complète enrichie

---

## Insights First Principles

1. Vidéo = source de vérité factuelle
2. Carte (~10 min) = unité naturelle
3. Mobile now, Desktop later
4. **LE COACH EST L'IA** - Augmenter, pas remplacer
5. Coûts fixes > variables
6. Upload = ennemi
7. Feedback = exemple concret
8. **Habit first, pro later** - Stratégie adoption
9. Sessions fragmentées (5-10 min)
10. **Core = Découpage + Vue Minimap** - Différenciateur
11. Template > OCR - Performance
