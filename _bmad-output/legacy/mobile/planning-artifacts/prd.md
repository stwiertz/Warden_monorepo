---
stepsCompleted: [step-01-init, step-02-discovery, step-03-success, step-04-journeys, step-05-domain, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish]
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
| Découpage auto | Détection des transitions de jeu (game-state KDA/HSV) + identification de la carte (pHash) |
| Vue Minimap | ROI fixe par carte |
| Commentaires vocaux | Avant/pendant/après clip |
| Export clip standalone | Vidéo autonome lisible partout |
| Navigation épisodes | Mode Netflix par carte |
| Toggle vue de clip | Switch instantané entre Full / Minimap / Minimap+HUD |
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
| **2. Game state detection** | Détecteur KDA/HSV (machine d'état 2 ou 3 états) sur keyframes — identifie game-on / game-off / between-round |
| **3. Map identification** | pHash 64-bit comparé aux empreintes de cartes (config Firestore) |
| **4. Detection config** | Fetch Firestore + cache MMKV avec fallback offline |
| **5. Output** | Timestamps + nom de carte par segment (pas de re-encoding) |
| **6. Mode** | Background processing, notification progress |

### Dépendances Techniques

| Lib | Usage |
|-----|-------|
| **FFmpeg** | Keyframe extraction, demux/mux, export final |
| **OpenCV (react-native-fast-opencv)** | Game state detection (HSV color space analysis), pHash computation pour map identification |
| **Firestore** | Detection config remote (ROIs, thresholds, map hashes) |

### Risques & Mitigations

| Risque | Mitigation |
|--------|------------|
| Process tué en background | Sauvegarder état, permettre reprise |
| Keyframe spacing variable | Tolérance sur détection transitions, fallback long-GOP black-screen detector |
| Carte non identifiée (pHash mismatch) | Segment marqué `unknown_map`, navigation Card View toujours fonctionnelle |
| Detection config Firestore inaccessible | Cache MMKV utilisé, fallback configuration empaquetée par défaut |
| Codec non supporté | Valider format à l'import, message clair si incompatible |

## Mobile App Specific Requirements

### Platform Requirements

| Aspect | Spécification |
|--------|---------------|
| **Framework** | React Native |
| **MVP Platform** | Android (test phase) |
| **V2 Platform** | iOS (après license Apple) |
| **Min Android** | API 24+ (Android 7.0) |

### Tech Stack

| Composant | Technologie |
|-----------|-------------|
| **App** | React Native |
| **Video Processing** | `ffmpeg-kit-react-native` (fork `jdarshan5/ffmpeg-kit-react-native`) |
| **Computer Vision** | `react-native-fast-opencv` (HSV game-state detection + pHash) |
| **Detection Config** | Firestore (Firebase) + MMKV cache |
| **Auth** | Firebase Auth |
| **Backend** | Firebase |
| **Web** | NextJS |
| **Paiements** | Stripe |

### Device Permissions

| Permission | Usage | Obligatoire |
|------------|-------|-------------|
| `READ_EXTERNAL_STORAGE` | Accès vidéos locales | Oui |
| `RECORD_AUDIO` | Commentaires vocaux | Oui |
| `FOREGROUND_SERVICE` | Background processing | Oui |
| `INTERNET` | Auth Firebase + validation abo | Oui |

### Auth & Subscription Flow

```
[Web NextJS + Stripe] → Paiement → Stripe webhook → Firebase (user.isPaid = true)
                                                          ↓
[App React Native] ← Firebase Auth ← Login ← User lance l'app
                                                          ↓
                                    App vérifie user.isPaid → Unlock features
```

### Offline Mode

| Scénario | Comportement |
|----------|--------------|
| **Première connexion** | Login Firebase requis |
| **Sessions suivantes** | Cache auth local, fonctionne offline |
| **Vérification abo** | Au login + périodique si online |
| **Processing vidéo** | 100% offline |

### Store Compliance - Reader App Model

| Aspect | Approche |
|--------|----------|
| **Modèle** | Reader App (Netflix-style) |
| **Monétisation** | 100% externe (web + Stripe) |
| **Dans l'app** | Login only, aucune mention paiement/prix |
| **Commission stores** | 0% |

| Règle | Application |
|-------|-------------|
| Pas d'IAP | Aucun achat in-app |
| Pas de lien paiement | Pas de bouton "S'abonner" |
| Pas de prix | Aucune mention tarifaire |
| Login only | Écran connexion Firebase uniquement |

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

| Aspect | Décision |
|--------|----------|
| **Approche** | Problem-solving MVP avec path to revenue |
| **Cible** | 20 coachs payants en 3 mois |
| **Principe** | Lean mais fonctionnel, valeur immédiate |

### MVP Feature Set (Phase 1)

**Journeys Supportés :**

| Journey | Support MVP |
|---------|-------------|
| J1 - Coach Happy Path | ✅ Complet |
| J2 - Coach Interruption | ✅ Complet |
| J3 - Joueur Passif | ✅ Complet |
| J4 - Joueur Actif | ⚠️ Partiel (pas de mode review import) |

**Must-Have Capabilities :**

| Feature | Status MVP |
|---------|------------|
| Découpage auto (game state + pHash map ID) | ✅ |
| Vue Minimap (ROI) | ✅ |
| Commentaires vocaux | ✅ |
| Export clip standalone | ✅ |
| Navigation épisodes | ✅ |
| Toggle vue de clip (Full / Minimap / Minimap+HUD) | ✅ |
| Qualité export (Mobile + HD) | ✅ |
| Auth Firebase + paywall | ✅ |

### Post-MVP Features

**Phase 2 (Growth) :**
- OCR scores/kills automatique
- Stats par carte
- Composition ROI avancée
- Mode review import (joueur actif)
- Export vertical (stories)
- iOS release

**Phase 3 (Expansion) :**
- Custom ROI templates (Desktop)
- Pick & Ban tool
- Stream Discord review groupe
- Analyse avancée Desktop

### Risk Mitigation Strategy

| Type | Risque | Mitigation |
|------|--------|------------|
| **Technical** | Perf FFmpeg/OpenCV mobile | Prototypage PC d'abord, puis portage mobile (validé via R&D 2026-04 sur méthodologie KDA/HSV + pHash) |
| **Technical** | Bridge React Native | Native modules si overhead trop élevé |
| **Market** | Niche petite | Valider 20 early adopters, coupons beta |
| **Resource** | Dev solo | MVP ultra lean, Firebase simplifie backend |

## Functional Requirements

### Video Import & Management

- **FR1:** Coach can import MP4 video files from device storage
- **FR2:** Coach can view list of imported sessions
- **FR3:** Coach can delete an imported session
- **FR4:** System validates video format at import and displays error if incompatible

### Video Processing

- **FR5:** System can automatically detect game-state transitions (game-on / game-off / between-round) in match recordings via on-device keyframe analysis
- **FR6:** System can identify which map is being played in each game segment
- **FR7:** System can determine time ranges for each map/round based on detected transitions
- **FR8:** System can identify and mark lobby segments as excluded from navigation
- **FR9:** System can process 1h20 video in background mode
- **FR10:** System can resume processing if interrupted

### Video Playback & Navigation

- **FR11:** Coach can navigate between maps using episode-style interface (UI-based on time ranges)
- **FR12:** Coach can play/pause video at any point within allowed time ranges
- **FR13:** Coach can seek within a map segment (time range)
- **FR14:** Coach can toggle the clip view mode instantly between Full, Minimap, and Minimap+HUD
- **FR15:** Coach can view the minimap as a cropped ROI from the source video, optionally overlaid with KDA + Score HUD elements (Minimap+HUD mode)

### Audio Commentary

- **FR16:** Coach can record voice comment before a clip segment
- **FR17:** Coach can record voice comment during playback (overlay)
- **FR18:** Coach can record voice comment after a clip segment
- **FR19:** Coach can delete a recorded comment
- **FR20:** Coach can preview clip with comments before export

### Clip Export

- **FR21:** Coach can select start/end points for a clip within a map
- **FR22:** Coach can export clip in Mobile quality (720p, fast)
- **FR23:** Coach can export clip in HD quality (source resolution)
- **FR24:** System exports clip as standalone video with embedded audio commentary
- **FR25:** Exported clip is playable without Warden app installed

### Session Persistence

- **FR26:** System saves session state automatically (current position, comments, clips in progress)
- **FR27:** Coach can resume session exactly where left off
- **FR28:** System persists state across app restarts and device reboots

### User Authentication & Subscription

- **FR29:** User can log in with Firebase account
- **FR30:** System validates subscription status on login
- **FR31:** System caches auth locally for offline use after initial login
- **FR32:** System periodically re-validates subscription when online
- **FR33:** Non-subscribed users see login screen only (no pricing, no subscribe CTA)

## Non-Functional Requirements

### Performance

| NFR | Cible | Contexte |
|-----|-------|----------|
| **NFR1** | Analyse vidéo 1h20 complète en < 2 minutes | Poco X5 référence |
| **NFR2** | Toggle POV/Minimap en < 100ms | UX critique |
| **NFR3** | Export clip Mobile en < 30 secondes par minute de clip | Best effort FFmpeg |
| **NFR4** | UI reste responsive pendant processing background | Pas de freeze |
| **NFR5** | RAM usage < 2GB pendant processing | Contrainte device |

### Reliability

| NFR | Cible | Contexte |
|-----|-------|----------|
| **NFR6** | Session state sauvegardé toutes les 30 secondes | Pas de perte de travail |
| **NFR7** | Reprise automatique après crash/kill | Background processing |
| **NFR8** | Commentaires vocaux persistés immédiatement | Pas de perte audio |
| **NFR9** | Auth cache valide 30 jours offline | Usage sans réseau |

### Security

| NFR | Cible | Contexte |
|-----|-------|----------|
| **NFR10** | Auth via Firebase (OAuth 2.0) | Standard sécurisé |
| **NFR11** | Token refresh automatique | Session seamless |
| **NFR12** | Pas de données utilisateur stockées côté serveur | Privacy by design |

