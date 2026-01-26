---
stepsCompleted: [step-01-init, step-02-discovery, step-03-success]
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

