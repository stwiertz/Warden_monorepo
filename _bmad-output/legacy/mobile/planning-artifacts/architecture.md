---
stepsCompleted: [1, 2]
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
