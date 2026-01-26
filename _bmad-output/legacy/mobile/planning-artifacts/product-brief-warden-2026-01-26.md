---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - docs/planning-artifacts/brainstorming-synthesis-2026-01-26.md
date: 2026-01-26
author: Mary (Business Analyst)
project_name: Warden
---

# Product Brief: Warden

## Executive Summary

**Warden** est une application mobile qui transforme chaque session de jeu EVA After-h en opportunité d'apprentissage accéléré. Comme un bonus "Double XP" dans les jeux vidéo, Warden permet aux équipes de doubler l'expérience gagnée en jouant - en rendant le processus de review si simple qu'il devient une habitude, pas une corvée.

**Proposition de valeur :** Progresser plus vite en investissant moins de temps.

---

## Core Vision

### Problem Statement

Les sessions EVA After-h sont payantes. Sans review structurée, les équipes "jouent" sans vraiment "s'entraîner" - elles comptent sur l'expérience brute pour progresser, ce qui est lent et frustrant. Les mêmes erreurs se répètent match après match.

### Problem Impact

- **Financier :** Mauvaise rentabilisation des sessions payantes
- **Progression :** Apprentissage lent, courbe de progression plate
- **Émotionnel :** Frustration des joueurs ET des coachs face aux erreurs répétées
- **Engagement :** Risque d'abandon si le sentiment de stagnation persiste

### Why Existing Solutions Fall Short

| Solution | Problème |
|----------|----------|
| Logiciels de montage | Complexes, pas configurés pour EVA, workflow lent |
| YouTube clips | Pas de mode minimap, pas de workflow de review intégré |
| EVA Battle Plan | Cloud = upload long, tokens = coûts variables, stats inutilisées |

**Gap identifié :** Aucun outil n'est spécifiquement conçu pour faciliter la review EVA sur mobile avec un workflow optimisé pour les coachs non-professionnels.

### Proposed Solution

Warden est l'application mobile de review de matchs EVA qui :
- **Découpe automatiquement** les vidéos par carte (détection écran noir + template)
- **Offre une vue Minimap** centrée pour l'analyse tactique
- **Permet des commentaires vocaux** positionnés (avant/pendant/après le clip)
- **Exporte des clips standalone** partageables sur n'importe quel device
- **Fonctionne 100% on-device** - pas d'upload, pas de cloud, pas de tokens

**Le résultat :** Review depuis son canapé en 10 minutes, clips envoyés aux joueurs qui peuvent les regarder immédiatement, sans installer d'app.

### Key Differentiators

| Différenciateur | Avantage |
|-----------------|----------|
| **Spécialisé EVA** | Templates ROI et détection de cartes pré-configurés |
| **Mode Minimap** | Vue tactique unique - personne d'autre ne l'offre |
| **100% On-Device** | Pas d'upload, coûts fixes, fonctionne offline |
| **Voice-First** | Commentaires vocaux = friction minimale pour coach fatigué |
| **Clips Standalone** | Joueurs n'ont pas besoin de l'app pour recevoir le feedback |

---

## Target Users

### Primary User: Le Coach

**Persona: Thomas, 26 ans**
- Coach sportif/kiné de profession
- Joue aux FPS depuis 10 ans, EVA depuis 2 ans
- Expérience de coaching (ex-coach COD)

**Contexte d'usage:**
- Reviews le soir après le travail, sur PC, à la maison
- Sessions de 30-60 minutes quand il a le temps

**Frustrations actuelles:**
- Jongler entre lecteur vidéo + notes + logiciel de montage
- N'utilise que 5% des fonctions des outils génériques
- Processus trop lourd → reviews irrégulières

**Ce qu'il attend de Warden:**
- Workflow unifié et optimisé pour EVA
- Mode Minimap pour l'analyse tactique
- Export de clips rapide avec commentaires vocaux

---

### Secondary User: Le Joueur Passif

**Persona: Lucas, 17 ans**
- Lycéen, joueur compétitif
- Excellents réflexes et aim, suit bien les instructions
- Manque la vision de jeu pour analyser seul

**Rapport au feedback:**
- Pense que progresser = jouer plus
- A besoin qu'on lui MONTRE quoi changer
- Les preuves vidéo éliminent le déni

**Ce qu'il attend de Warden (indirectement):**
- Clips clairs avec contexte vocal du coach
- Pas besoin d'installer d'app
- Feedback actionnable, pas théorique

---

### Secondary User: Le Joueur Actif

**Persona: Maxime, 22 ans**
- Joueur haute division + coach adjoint d'équipes inférieures
- Proactif, cherche à comprendre, pas juste exécuter
- Pipeline: Joueur passif → Actif → Coach

**Usage de Warden:**
- Importe les reviews du coach principal
- Regarde la session complète seul
- Développe sa propre capacité d'analyse

**Ce qu'il attend de Warden:**
- Mode review import avec commentaires coach
- Navigation facile (mode épisodes/highlights)
- Possibilité de revoir plusieurs fois les moments clés

---

### User Journey

**Découverte:**
- Bouche à oreille dans la communauté EVA (Discord)
- Réseau de coachs FR/BE existant
- Coupons offerts aux gagnants de ligue locale mensuelle

**Onboarding:**
- Import vidéo → découpage automatique par carte
- Premier "wow": Mode Minimap révèle la vue tactique
- Premier clip exporté en < 5 minutes

**Adoption:**
- Stratégie "dealer de confort": coupon 1 mois aux champions
- Équipe monte de division, découvre Warden
- Même si redescend, le confort justifie l'abonnement

**Fidélisation:**
- Habitude hebdomadaire de review post-session
- Progression visible des joueurs = validation du coach
- Devient outil indispensable de l'équipe

---

## Success Metrics

### User Success

**Coach (Thomas):**
- Peut faire des reviews confortablement (canapé, mobile)
- Atteint une régularité de 1 review/semaine minimum
- Temps de création d'un clip réduit de 80% vs workflow actuel

**Équipe:**
- Des équipes qui ne communiquaient pas sur leurs games commencent à échanger
- Les joueurs passifs regardent ET répondent aux clips
- Réduction des erreurs répétées match après match

### Business Objectives

| Horizon | Objectif | Indicateur |
|---------|----------|------------|
| 3 mois | Validation MVP | 20 utilisateurs payants |
| 12 mois | Croissance établie | 100 abonnés |
| 12 mois+ | Expansion features | Roadmap communautaire (Pick & Ban, etc.) |

**Pricing:**
- Mensuel: 7€/mois
- Annuel: 70€/an (-17%)

### Key Performance Indicators

| KPI | Cible 3 mois | Cible 12 mois |
|-----|--------------|---------------|
| Coachs payants | 20 | 100 |
| Reviews/semaine/coach | 1+ | 1+ |
| Clips créés/review | 3-5 | 5+ |
| Churn mensuel | <15% | <10% |
| MRR | 140€ | 700€ |

**Leading Indicators:**
- Taux de conversion coupon → abonnement
- Clips partagés par coach/mois
- Temps moyen pour créer premier clip
