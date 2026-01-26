---
stepsCompleted: [step-01-init, step-02-discovery, step-03-success, step-04-journeys, step-05-domain]
inputDocuments:
  - docs/planning-artifacts/product-brief-warden-2026-01-26.md
  - docs/brainstorming/brainstorming-session-2026-01-26.md
  - docs/planning-artifacts/brainstorming-synthesis-2026-01-26.md
workflowType: 'prd'
date: 2026-01-26
author: PM
project_name: Warden
briefCount: 1
researchCount: 0
brainstormingCount: 2
projectDocsCount: 0
classification:
  projectType: mobile_app
  domain: general
  domainComplexity: low
  technicalComplexity: high
  projectContext: greenfield
---

# Product Requirements Document - Warden

**Author:** PM
**Date:** 2026-01-26

## Success Criteria

### User Success

| Critère | Mesure | Cible |
|---------|--------|-------|
| Confort de review | Coach peut reviewer depuis son canapé | Mobile-first UX |
| Régularité | Reviews par semaine par coach | ≥ 1 |
| Gain de temps | Réduction vs workflow actuel | -50% |
| Engagement équipe | Équipes qui échangent sur leurs games | Qualitatif |
| Réception feedback | Joueurs passifs regardent ET répondent | Qualitatif |

### Business Success

| Horizon | Métrique | Cible |
|---------|----------|-------|
| 3 mois | Coachs payants | 20 |
| 3 mois | MRR | 140€ |
| 12 mois | Abonnés | 100 |
| 12 mois | MRR | 700€ |
| Ongoing | Churn mensuel | <15% → <10% |

### Technical Success

| Critère | Cible | Note |
|---------|-------|------|
| Découpage 1h20 | < 2 minutes | Core perf target |
| Suppression lobby | Automatique | ~10% vidéo économisé |
| Export clip | Qualité configurable | HD (lent) vs Mobile (rapide) |
| Pipeline export | Demux → process → mux | Voice overlay + ROI crop |
| Device référence | Poco X5 | Snapdragon 695, 6GB RAM |
| Traitement | 100% on-device | Pas de cloud |

### Export Quality Options

| Mode | Résolution | Use case |
|------|------------|----------|
| **Mobile** | 720p ou moins | Export rapide, partage Discord/WhatsApp |
| **HD** | Qualité source | Archivage, partage YouTube |

## Product Scope

### MVP - Minimum Viable Product

| Feature | Description |
|---------|-------------|
| Découpage auto | Détection écran noir + template matching |
| Vue Minimap | ROI fixe par carte |
| Commentaires vocaux | Avant/pendant/après clip |
| Export clip standalone | Vidéo autonome lisible partout |
| Navigation épisodes | Mode Netflix par carte |
| Toggle POV/Minimap | Switch instantané |
| Qualité export | Choix Mobile (rapide) / HD (qualité) |

### Growth Features (Post-MVP)

- OCR scores/kills automatique
- Stats par carte (victoire/défaite, score final)
- Composition ROI avancée (minimap + killfeed + vie)
- Mode review import (pour joueur actif)
- Export vertical (format stories/TikTok)

### Vision (Future)

- Custom ROI templates (Desktop)
- Pick & Ban tool
- Stream Discord pour review groupe
- Analyse avancée Desktop

## User Journeys

### Journey 1: Coach Thomas - Première Review Complète

**Opening Scene:**
Thomas rentre chez lui après une session EVA frustrante. Son équipe a encore perdu 3 rounds sur des erreurs de positionnement. Il s'affale dans son canapé, épuisé, mais il sait que sans review ces erreurs vont se répéter.

**Rising Action:**
Il ouvre Warden sur son téléphone. Import de la vidéo (1h20). En 90 secondes, l'app a découpé la session en 8 cartes, le lobby supprimé automatiquement. Il navigue comme sur Netflix, tombe sur LE round problématique.

**Climax:**
Toggle vers la vue Minimap. Là, tout devient clair : Lucas était complètement hors position, le flanc était ouvert. Thomas appuie sur "commentaire", dit simplement "Lucas, regarde ta position ici, tu laisses le flanc droit ouvert". Export en qualité Mobile.

**Resolution:**
15 minutes après s'être assis, Thomas a envoyé 3 clips sur le Discord de l'équipe. Il peut enfin se détendre. Demain, Lucas saura exactement quoi corriger.

### Journey 2: Coach Thomas - Session Interrompue

**Opening Scene:**
Thomas est en pleine review quand sa copine l'appelle pour dîner. Il pose son téléphone.

**Rising Action:**
2 heures plus tard, il rouvre Warden.

**Climax:**
L'app a gardé son état : même carte, même position dans la vidéo, commentaires en cours sauvegardés.

**Resolution:**
Il reprend exactement où il en était, finit sa review en 5 minutes.

### Journey 3: Joueur Passif Lucas - Réception Clip

**Opening Scene:**
Lucas est au lycée, pause déjeuner. Notification Discord : Thomas a envoyé un clip.

**Rising Action:**
Il clique. Pas d'app à installer, la vidéo se lance directement dans Discord/WhatsApp.

**Climax:**
La voix de Thomas explique : "Regarde ta position ici...". Lucas VOIT son erreur sur la minimap. Impossible de nier.

**Resolution:**
Il répond "Ok compris, je me cale sur toi au prochain round". La prochaine session, il corrige.

### Journey 4: Joueur Actif Maxime - Auto-Review

**Opening Scene:**
Maxime veut progresser plus vite. Il a récupéré la vidéo de session sur son téléphone.

**Rising Action:**
Il importe dans Warden. Découpage auto. Il parcourt les cartes une par une, toggle entre POV et Minimap.

**Climax:**
Sans les commentaires du coach, il doit analyser seul. Mais la vue Minimap lui révèle des patterns qu'il n'avait jamais vus en jouant.

**Resolution:**
Il note mentalement 2-3 points à travailler. Il devient lui-même meilleur analyste, un pas de plus vers le rôle de coach.

### Journey Requirements Summary

| Journey | Capabilities Révélées |
|---------|----------------------|
| J1 - Coach Happy Path | Import vidéo, découpage auto, suppression lobby, navigation épisodes, vue Minimap, commentaires vocaux, export clip, partage externe |
| J2 - Coach Interruption | Persistance état, sauvegarde auto, reprise session |
| J3 - Joueur Passif | Export standalone (pas besoin d'app), audio intégré, format compatible messageries |
| J4 - Joueur Actif | Import vidéo, découpage auto, navigation, toggle POV/Minimap |

## Domain-Specific Requirements

### Contraintes Techniques

| Catégorie | Contrainte | Détail |
|-----------|------------|--------|
| **Device** | Mid-range Android | Poco X5 référence (Snapdragon 695, 6GB RAM) |
| **RAM** | Budget ~2GB max | Keyframes low-res uniquement |
| **Batterie** | Optimisation requise | Traitement léger grâce aux keyframes |

### Format Vidéo

| Aspect | Spécification |
|--------|---------------|
| **Format** | MP4 (H.264/AAC) |
| **Source** | Fichier local sur device |
| **Durée typique** | ~1h20 par session |
| **Gestion** | Lecture in-place, pas de copie |

### Processing Pipeline

| Étape | Technique |
|-------|-----------|
| **1. Keyframe extraction** | FFmpeg `-skip_frame nokey`, basse résolution |
| **2. Détection écran noir** | Analyse luminosité moyenne sur keyframes |
| **3. Template matching** | OpenCV sur écrans de fin de carte (low-res) |
| **4. Output** | Timestamps uniquement (pas de re-encoding) |
| **5. Mode** | Background processing, notification progress |

### Dépendances Techniques

| Lib | Usage |
|-----|-------|
| **FFmpeg** | Keyframe extraction, demux/mux, export final |
| **OpenCV** | Template matching basse-res |

### Risques & Mitigations

| Risque | Mitigation |
|--------|------------|
| Process tué en background | Sauvegarder état, permettre reprise |
| Keyframe spacing variable | Tolérance sur détection transitions |
| Template non reconnu | Fallback écran noir seul + correction manuelle |
| Codec non supporté | Valider format à l'import, message clair si incompatible |

