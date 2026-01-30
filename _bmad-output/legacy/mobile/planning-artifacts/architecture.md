---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - docs/planning-artifacts/prd.md
  - docs/planning-artifacts/product-brief-warden-2026-01-26.md
  - docs/planning-artifacts/brainstorming-synthesis-2026-01-26.md
workflowType: 'architecture'
project_name: 'Warden'
date: 2026-01-30
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
33 FRs organisées en 7 domaines architecturaux :

| Domaine | FRs | Implications architecturales |
|---------|-----|------------------------------|
| Import & gestion vidéo | FR1-4 | File system access, format validation, session management |
| Traitement vidéo | FR5-10 | Background processing pipeline, FFmpeg/OpenCV native modules, crash recovery |
| Lecture & navigation | FR11-15 | Video player component, ROI cropping, episode-style UI |
| Commentaires audio | FR16-20 | Audio recording, storage, synchronization avec vidéo |
| Export clips | FR21-25 | Demux/mux pipeline, audio overlay, qualité configurable |
| Persistance session | FR26-28 | Auto-save state, local storage, crash recovery |
| Auth & abonnement | FR29-33 | Firebase Auth, offline cache, subscription validation |

**Non-Functional Requirements:**
12 NFRs qui guident les décisions architecturales :

- **Performance** (NFR1-5) : Analyse 1h20 < 2min, toggle POV/Minimap < 100ms, RAM < 2GB, UI responsive pendant processing
- **Reliability** (NFR6-9) : Sauvegarde auto 30s, reprise après crash, persistance audio immédiate, cache auth 30j
- **Security** (NFR10-12) : Firebase OAuth 2.0, token refresh auto, privacy by design (pas de données serveur)

**Scale & Complexity:**

- Domaine principal : Mobile natif + traitement vidéo on-device
- Niveau de complexité : **Haute** (bridge React Native vers native FFmpeg/OpenCV)
- Composants architecturaux estimés : ~8 modules principaux
- Temps réel : Non requis
- Multi-tenancy : Non

### Technical Constraints & Dependencies

| Contrainte | Impact architectural |
|------------|---------------------|
| 100% on-device processing | Pas de cloud compute, tout passe par le device |
| Device référence Poco X5 (6GB RAM) | Budget RAM ~2GB pour le processing |
| React Native framework | Bridge vers modules natifs FFmpeg/OpenCV |
| Android API 24+ (MVP) | Contraintes de permissions et background services |
| Reader App model | Pas d'IAP, auth/paiement découplés (web Stripe + Firebase) |
| Format MP4 H.264/AAC uniquement | Validation stricte à l'import |

**Dépendances techniques :**
- `ffmpeg-kit-react-native` : Keyframe extraction, demux/mux, export
- OpenCV (native module) : Template matching basse résolution
- Firebase Auth : Authentification et validation abonnement
- NextJS + Stripe : Web payment flow (hors scope app mobile)

### Cross-Cutting Concerns

1. **Gestion mémoire** : Monitoring RAM pendant processing, libération agressive des ressources, keyframes low-res uniquement
2. **Background processing lifecycle** : Foreground service Android, sauvegarde état pour reprise, notification de progression
3. **Error handling & recovery** : Process tué par OS, codec incompatible, template non reconnu, réseau absent
4. **Offline-first** : Cache auth local, processing 100% offline, sync périodique quand réseau disponible
5. **State persistence** : Auto-save 30s, reprise exacte après interruption/crash, commentaires audio persistés immédiatement

## Starter Template Evaluation

### Primary Technology Domain

Application mobile React Native avec traitement vidéo natif on-device.

### Technical Preferences

| Aspect | Choix | Rationale |
|--------|-------|-----------|
| **Framework** | Expo (managed → dev-client) | Simplifie le deploy, support modules natifs via dev-client |
| **Langage** | TypeScript | Type safety essentielle pour un projet de cette complexité |
| **State Management** | Zustand | Léger, simple, adapté au profil junior |
| **Navigation** | React Navigation | Standard React Native, large communauté |
| **Niveau équipe** | Junior | Première app en prod, expérience RN existante |

### Starter Options Considered

| Option | Verdict |
|--------|---------|
| `create-expo-app --template blank-typescript` | **Retenu** - Base propre, pas de magie excessive |
| Obytes Starter | Écarté - Trop de couches pour un premier projet |
| ExpoStarter.com | Écarté - Template payant, opinionated |
| Custom template | Écarté - Overhead inutile |

### Selected Starter: create-expo-app (blank-typescript)

**Rationale:** Pour un profil junior, mieux vaut comprendre chaque brique ajoutée. Le template blank-typescript offre une base propre avec TypeScript configuré, sans abstraction cachée.

**Initialization Command:**

```bash
npx create-expo-app@latest Warden --template blank-typescript
```

**Architectural Decisions Provided by Starter:**

- **Language & Runtime:** TypeScript, Metro bundler
- **Build Tooling:** Expo CLI, EAS Build
- **Config:** app.json / app.config.ts
- **Dev Experience:** Hot reload, Expo DevTools

**Additional Dependencies Required:**

| Package | Usage | Raison |
|---------|-------|--------|
| `expo-dev-client` | Custom dev builds | Nécessaire pour modules natifs FFmpeg/OpenCV |
| `react-navigation` | Navigation | Standard RN |
| `zustand` | State management | Choix utilisateur |
| FFmpeg (fork/custom) | Video processing | Core feature - fork communautaire car ffmpeg-kit-react-native deprecated (jan 2025) |
| OpenCV (native module) | Template matching | Via Expo Modules API |

### Risk Alert: ffmpeg-kit-react-native Deprecated

`ffmpeg-kit-react-native` a été officiellement retiré en janvier 2025 (repo archivé juin 2025). Options viables :
1. Fork communautaire (jdarshan5/ffmpeg-kit-react-native) + config plugin Expo
2. Build local FFmpegKit + custom config plugin
3. Module natif custom via Expo Modules API wrappant FFmpeg directement

**Décision à prendre au Step 4.**

**Note:** L'initialisation du projet avec cette commande sera la première story d'implémentation.
