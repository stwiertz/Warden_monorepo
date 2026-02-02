---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
status: 'complete'
completedAt: '2026-01-30'
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
| `nativewind` + `tailwindcss` | Styling | Utility classes Tailwind, design tokens config-driven |
| `react-native-reusables` | UI components | Composants standard (cards, sheets, dialogs) -- copy-paste ownership |

### Risk Alert: ffmpeg-kit-react-native Deprecated

`ffmpeg-kit-react-native` a été officiellement retiré en janvier 2025 (repo archivé juin 2025). Options viables :
1. Fork communautaire (jdarshan5/ffmpeg-kit-react-native) + config plugin Expo
2. Build local FFmpegKit + custom config plugin
3. Module natif custom via Expo Modules API wrappant FFmpeg directement

**Décision à prendre au Step 4.**

**Note:** L'initialisation du projet avec cette commande sera la première story d'implémentation.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data locale, FFmpeg strategy, OpenCV integration, Video playback, Audio recording, Auth

**Important Decisions (Shape Architecture):**
- Build & deploy pipeline, cross-platform strategy

**Deferred Decisions (Post-MVP):**
- iOS-specific optimizations, analytics, advanced monitoring
- Export queue background encoding (Option 3 UX spec) -- architecture supports evolution via isolated `exportPipeline.ts`, extensible Zustand store (`clipQueue` state), et foreground service Android réutilisable
- OCR extraction de scores (peuple `score_orange`/`score_blue` dans `map_segments`) -- active les tris Card View par score
- Multi-view clip export (switch POV/minimap dans un même clip exporté) -- nécessite multi-segment FFmpeg encoding

### Data Architecture

| Décision | Choix | Rationale |
|----------|-------|-----------|
| **Données structurées** | SQLite via `expo-sqlite` | Sessions, clips, commentaires metadata -- relations nécessaires |
| **Données rapides** | MMKV (`react-native-mmkv`) | Prefs, cache auth, état session -- auto-save 30s (NFR6) instantané |
| **Fichiers audio** | Filesystem local | Commentaires vocaux .m4a stockés en fichiers, référencés par SQLite |
| **Approche** | Hybride MMKV + SQLite | MMKV pour la vitesse (state persistence), SQLite pour la structure |

### FFmpeg Strategy

| Décision | Choix | Rationale |
|----------|-------|-----------|
| **Lib MVP** | Fork `jdarshan5/ffmpeg-kit-react-native` | Drop-in replacement de la lib deprecated, API connue |
| **Intégration Expo** | Config plugin custom | Injection des dépendances natives via `expo prebuild` |
| **Plan B** | Module natif custom via Expo Modules API | Si le fork devient instable, migration vers wrapper natif direct |
| **Risque** | ffmpeg-kit-react-native deprecated jan 2025 | Fork communautaire actif, surveillance nécessaire |

### OpenCV Integration

| Décision | Choix | Rationale |
|----------|-------|-----------|
| **Lib** | `react-native-fast-opencv` | JSI/C++, cross-platform Android+iOS, API TypeScript |
| **Usage** | Template matching basse résolution sur keyframes | Détection écrans de fin de carte |
| **Avantage** | Pas de code natif custom | Un seul code C++ partagé, pas de Kotlin/Swift à écrire |

### Video Playback & Audio

| Décision | Choix | Rationale |
|----------|-------|-----------|
| **Video player** | `expo-av` | Intégré Expo, UI 100% custom (timeline, boutons, toggle) |
| **Audio recording** | `expo-av` (Audio.Recording) | Même lib, enregistrement AAC/.m4a |
| **Format audio** | AAC (.m4a) | Compatible pipeline FFmpeg -- mux sans ré-encoding |
| **Toggle POV/Minimap** | Changement de style/crop sur même source | Pas de changement de player, juste crop ROI = < 100ms (NFR2) |
| **Modèle voix** | 3 slots par clip : before / during / after | Aligné avec UX spec -- coach peut commenter avant, pendant, et après le clip |
| **Export multi-segment** | FFmpeg concat : still frame + clip vidéo + frozen frame + still frame | Chaque segment optionnel, clips silencieux sautent tous les segments voix |

### Authentication & Security

| Décision | Choix | Rationale |
|----------|-------|-----------|
| **Auth SDK** | Firebase JS SDK (modular v9+) | Cross-platform natif, pas de module natif supplémentaire |
| **Modèle** | Reader App (0% commission stores) | Login only dans l'app, paiement web Stripe |
| **Offline** | Cache auth local MMKV, 30j validité (NFR9) | Processing 100% offline après premier login |
| **Validation abo** | Au login + périodique si online | Check `user.isPaid` via Firebase |

### UI Components & Styling

| Décision | Choix | Rationale |
|----------|-------|-----------|
| **Composants UI** | React Native Reusables (shadcn/ui pour RN) | Modèle copy-paste, ownership total, dark theme intégré, pas de Material Design |
| **Styling** | NativeWind (Tailwind CSS pour RN) | Utility classes, design tokens via config, itération rapide |
| **Theming** | Dark-first, tokens configurables | Un seul `tailwind.config.ts` définit palette, spacing, typographie |
| **Composants standard** | Cards, sheets, dialogs, buttons via React Native Reusables | Themés avec tokens dark + accent orange |
| **Composants custom** | Video player, minimap, clip creation, voice recorder, timeline | Construits sur mesure -- différenciateur produit, aucune lib ne les couvre |

**Dépendances additionnelles :**

| Package | Usage | Raison |
|---------|-------|--------|
| `nativewind` | Utility classes Tailwind pour RN | Styling cohérent, config-driven |
| `tailwindcss` | Système de tokens et config | Design tokens centralisés |
| `react-native-reusables` | Composants UI de base | Cards, sheets, dialogs, buttons -- ownership total |

**Note :** NativeWind nécessite un plugin Babel + config plugin Expo. Impact sur le pipeline de build.

### Infrastructure & Deployment

| Décision | Choix | Rationale |
|----------|-------|-----------|
| **Build** | EAS Build (cloud Expo) | Standard Expo, pas de CI/CD custom |
| **Distribution** | EAS Submit | Soumission directe aux stores |
| **Environnements** | 3 : development, preview, production | Dev-client / test interne / stores |
| **Target MVP** | Android (Play Store) | iOS Phase 2, mais toutes décisions cross-platform ready |

### Cross-Platform Strategy

| Aspect | Android (MVP) | iOS (Phase 2) |
|--------|---------------|---------------|
| Expo | natif | natif |
| React Navigation | natif | natif |
| Zustand | JS pur | JS pur |
| expo-av | natif | natif |
| Firebase JS SDK | JS pur | JS pur |
| FFmpeg (fork) | natif Android | natif iOS (supporté par le fork) |
| react-native-fast-opencv | JSI/C++ partagé | JSI/C++ partagé |
| MMKV | natif | natif |
| expo-sqlite | natif | natif |
| NativeWind | JS + Babel plugin | JS + Babel plugin |
| React Native Reusables | JS pur | JS pur |

**Seule action supplémentaire pour iOS :** Tester le build et valider les config plugins FFmpeg côté iOS.

### Decision Impact Analysis

**Implementation Sequence:**
1. Init projet Expo + TypeScript
2. Setup NativeWind + React Native Reusables + design tokens (tailwind.config.ts)
3. Setup navigation (React Navigation) + state (Zustand)
4. Setup data layer (MMKV + SQLite + schema)
5. Intégration FFmpeg (fork + config plugin)
6. Intégration OpenCV (react-native-fast-opencv)
7. Video player (expo-av) + UI custom Cinema Mode
8. Audio recording (expo-av) -- modèle 3 slots (before/during/after)
9. Auth Firebase + validation abo
10. Pipeline export (FFmpeg concat multi-segment : still frames + clip vidéo + audio overlay)

**Cross-Component Dependencies:**
- FFmpeg + OpenCV → Pipeline de traitement vidéo (processing)
- expo-av + FFmpeg → Pipeline export (playback → clip selection → export)
- MMKV + SQLite → State persistence (auto-save session + données structurées)
- Firebase Auth + MMKV → Auth flow (login → cache → offline)

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Code Naming Conventions:**

| Élément | Convention | Exemple |
|---------|-----------|---------|
| Composants React | PascalCase | `VideoPlayer.tsx`, `MapCard.tsx` |
| Fichiers composants | PascalCase | `VideoPlayer.tsx` |
| Hooks custom | camelCase avec `use` prefix | `useSession.ts`, `useVideoProcessing.ts` |
| Fonctions / variables | camelCase | `getSessionData`, `clipDuration` |
| Types / Interfaces | PascalCase, pas de prefix | `Session`, `ClipExportOptions`, `MapSegment` |
| Constants | UPPER_SNAKE_CASE | `MAX_RAM_BUDGET`, `AUTO_SAVE_INTERVAL_MS` |
| Dossiers | kebab-case | `video-processing/`, `clip-export/` |

**Database Naming Conventions (SQLite):**

| Élément | Convention | Exemple |
|---------|-----------|---------|
| Tables | snake_case pluriel | `sessions`, `audio_comments`, `clip_exports` |
| Colonnes | snake_case | `session_id`, `created_at`, `map_index` |
| Foreign keys | `{table_singulier}_id` | `session_id`, `comment_id` |

**MMKV Key Conventions:**

| Élément | Convention | Exemple |
|---------|-----------|---------|
| Keys | dot.notation groupée | `auth.token`, `session.current.position`, `prefs.exportQuality`, `prefs.sortOrder` |

### Structure Patterns

**Organisation par feature :**

```
src/
  features/
    video-import/       # FR1-4
    video-processing/   # FR5-10
    video-playback/     # FR11-15
    audio-commentary/   # FR16-20
    clip-export/        # FR21-25
    session/            # FR26-28 (persistance)
    auth/               # FR29-33
  shared/
    components/         # Composants UI réutilisables
    hooks/              # Hooks partagés
    services/           # FFmpeg, OpenCV, SQLite, MMKV wrappers
    types/              # Types globaux
    utils/              # Fonctions utilitaires
```

**Règles :**
- Chaque feature contient ses propres composants, hooks, types et logique
- Les éléments réutilisés entre features vont dans `shared/`
- Tests co-located : `VideoPlayer.test.tsx` à côté de `VideoPlayer.tsx`

### State Management Patterns (Zustand)

| Règle | Détail |
|-------|--------|
| Un store par feature | `useSessionStore`, `useAuthStore`, `useExportStore` |
| Pas de logique async dans le store | Les stores sont purs, la logique async dans des hooks ou services |
| Persistance via middleware | Zustand `persist` middleware avec MMKV comme storage engine |
| Immutabilité | Toujours retourner un nouvel objet, jamais muter directement |

### Error Handling Patterns

| Contexte | Pattern |
|----------|---------|
| Processing vidéo | Try/catch + sauvegarde état avant crash, reprise possible |
| Import vidéo | Validation format à l'entrée, message clair si incompatible |
| Template matching | Fallback écran noir si template non reconnu |
| Auth réseau | Fallback cache MMKV si réseau absent |
| UI | Pas de crash silencieux -- toast/snackbar pour informer l'utilisateur |

### Enforcement Guidelines

**Tous les agents AI DOIVENT :**
- Suivre les conventions de nommage strictement (PascalCase composants, camelCase fonctions, snake_case DB)
- Placer le code dans la feature appropriée, jamais dans `shared/` sauf si réutilisé par 2+ features
- Créer les tests co-located avec le code source
- Utiliser Zustand stores purs (pas d'async dans le store)
- Gérer les erreurs explicitement (pas de catch vide, pas de crash silencieux)

**Anti-Patterns à éviter :**
- Mutation directe du state Zustand
- Logique métier dans les composants UI (extraire dans hooks/services)
- Import circulaires entre features
- Fichiers "fourre-tout" (`utils.ts` géant, `helpers.ts` sans scope)
- Accès direct à SQLite/MMKV depuis les composants (passer par les services)

## Project Structure & Boundaries

### Complete Project Directory Structure

```
Warden/
├── app.config.ts                        # Config Expo dynamique
├── package.json
├── tsconfig.json
├── eas.json                             # Config EAS Build (dev/preview/prod)
├── tailwind.config.ts                  # Design tokens : palette dark, spacing, typographie
├── .gitignore
├── .env.example
├── plugins/
│   └── with-ffmpeg.js                   # Config plugin Expo pour FFmpeg fork
├── assets/
│   ├── images/
│   │   └── map-templates/               # Templates de fin de carte pour OpenCV matching
│   └── fonts/
├── src/
│   ├── app/                             # Entry point & navigation
│   │   ├── _layout.tsx                  # Root layout (React Navigation)
│   │   ├── index.tsx                    # Home / session list
│   │   └── session/
│   │       ├── [id].tsx                 # Session review screen
│   │       └── export.tsx               # Export screen
│   ├── features/
│   │   ├── video-import/                # FR1-4 : Import & gestion vidéo
│   │   │   ├── VideoImportScreen.tsx
│   │   │   ├── useVideoImport.ts
│   │   │   ├── videoImportService.ts
│   │   │   └── types.ts
│   │   ├── video-processing/            # FR5-10 : Traitement vidéo
│   │   │   ├── useVideoProcessing.ts
│   │   │   ├── processingPipeline.ts        # Orchestration keyframes → détection → segments
│   │   │   ├── blackScreenDetector.ts       # Analyse luminosité keyframes
│   │   │   ├── templateMatcher.ts           # OpenCV template matching
│   │   │   ├── processingNotification.ts    # Foreground service notification
│   │   │   └── types.ts
│   │   ├── video-playback/              # FR11-15 : Lecture & navigation
│   │   │   ├── VideoPlayer.tsx              # Player expo-av + UI custom
│   │   │   ├── PlayerControls.tsx           # Play/pause, seek, timeline
│   │   │   ├── MinimapView.tsx              # ROI crop view
│   │   │   ├── EpisodeNavigator.tsx         # Navigation Netflix-style par carte
│   │   │   ├── usePlayback.ts
│   │   │   └── types.ts
│   │   ├── audio-commentary/            # FR16-20 : Commentaires vocaux
│   │   │   ├── AudioRecorder.tsx
│   │   │   ├── CommentaryTimeline.tsx
│   │   │   ├── useAudioRecording.ts
│   │   │   ├── audioCommentService.ts
│   │   │   └── types.ts
│   │   ├── clip-export/                 # FR21-25 : Export clips
│   │   │   ├── ExportOptions.tsx
│   │   │   ├── ExportProgress.tsx
│   │   │   ├── useClipExport.ts
│   │   │   ├── exportPipeline.ts            # FFmpeg demux → process → mux
│   │   │   └── types.ts
│   │   ├── session/                     # FR26-28 : Persistance session
│   │   │   ├── useSessionStore.ts           # Zustand store + persist MMKV
│   │   │   ├── sessionRepository.ts         # SQLite CRUD sessions
│   │   │   ├── autoSaveService.ts           # Auto-save 30s
│   │   │   └── types.ts
│   │   └── auth/                        # FR29-33 : Auth & abonnement
│   │       ├── LoginScreen.tsx
│   │       ├── useAuthStore.ts              # Zustand store + persist MMKV
│   │       ├── authService.ts               # Firebase JS SDK
│   │       ├── subscriptionService.ts       # Validation isPaid
│   │       └── types.ts
│   └── shared/
│       ├── components/
│       │   ├── Button.tsx
│       │   ├── Toast.tsx
│       │   └── LoadingSpinner.tsx
│       ├── hooks/
│       │   └── usePermissions.ts
│       ├── services/
│       │   ├── ffmpeg.ts                    # Wrapper FFmpeg fork API
│       │   ├── opencv.ts                    # Wrapper react-native-fast-opencv
│       │   ├── database.ts                  # Init & migrations SQLite
│       │   └── storage.ts                   # MMKV instance & helpers
│       ├── types/
│       │   └── index.ts                     # Types globaux (Session, MapSegment, etc.)
│       └── utils/
│           ├── fileSystem.ts
│           └── formatters.ts
```

### Architectural Boundaries

**Service Boundaries :**
- `shared/services/ffmpeg.ts` et `shared/services/opencv.ts` sont les seuls points d'accès aux libs natives -- les features ne les importent jamais directement
- `shared/services/database.ts` et `shared/services/storage.ts` encapsulent tout accès SQLite/MMKV
- Chaque feature expose ses fonctionnalités via ses hooks (`useVideoProcessing`, `useClipExport`, etc.)

**Component Boundaries :**
- Les features ne s'importent pas entre elles directement
- La communication inter-features passe par les Zustand stores (état partagé) ou les services partagés
- Les screens (`src/app/`) orchestrent les features en composant leurs hooks et composants

**Data Boundaries :**
- SQLite : `sessions`, `audio_comments`, `clip_exports`, `map_segments` (données structurées)
- MMKV : `auth.*`, `session.current.*`, `prefs.*` (état rapide, cache)
- Filesystem : fichiers vidéo source (in-place, pas de copie), fichiers audio .m4a (commentaires)

### SQLite Schema

```sql
-- Sessions de review importées
sessions (
  id              TEXT PRIMARY KEY,
  video_file_path TEXT NOT NULL,
  name            TEXT,
  duration_ms     INTEGER,
  status          TEXT CHECK(status IN ('importing', 'processing', 'ready', 'error')),
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
)

-- Segments de carte détectés par le processing pipeline
map_segments (
  id                TEXT PRIMARY KEY,
  session_id        TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  map_index         INTEGER NOT NULL,
  start_time_ms     INTEGER NOT NULL,
  end_time_ms       INTEGER NOT NULL,
  map_name          TEXT,
  result_frame_path TEXT,          -- chemin vers screenshot scoreboard extrait
  score_orange      INTEGER,      -- nullable, extraction OCR post-MVP
  score_blue        INTEGER,      -- nullable, extraction OCR post-MVP
  created_at        TEXT NOT NULL
)

-- Clips créés par le coach
clip_exports (
  id              TEXT PRIMARY KEY,
  session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  map_segment_id  TEXT NOT NULL REFERENCES map_segments(id) ON DELETE CASCADE,
  start_time_ms   INTEGER NOT NULL,
  end_time_ms     INTEGER NOT NULL,
  view_mode       TEXT CHECK(view_mode IN ('pov', 'minimap')) NOT NULL,
  status          TEXT CHECK(status IN ('defining', 'locked', 'exporting', 'ready', 'shared')) NOT NULL,
  export_quality  TEXT CHECK(export_quality IN ('mobile', 'hd')),
  file_path       TEXT,           -- NULL jusqu'à export terminé
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
)

-- Commentaires audio -- modèle 3 slots (before/during/after) par clip
audio_comments (
  id              TEXT PRIMARY KEY,
  clip_export_id  TEXT NOT NULL REFERENCES clip_exports(id) ON DELETE CASCADE,
  slot            TEXT CHECK(slot IN ('before', 'during', 'after')) NOT NULL,
  file_path       TEXT NOT NULL,
  duration_ms     INTEGER NOT NULL,
  created_at      TEXT NOT NULL
)
```

**Notes schema :**
- `result_frame_path` : extrait à la fin du processing pipeline (dernière frame avant écran noir)
- `score_orange` / `score_blue` : NULL en MVP, peuplés quand OCR implémenté (post-MVP)
- Tri Card View : temporal order disponible immédiatement, tris par score disponibles quand OCR activé
- `clip_exports.status` : suit le lifecycle clip (defining → locked → exporting → ready → shared)
- `audio_comments` : 0 à 3 enregistrements par clip, un par slot. Clips silencieux n'ont aucun audio_comment.
- Export MP4 assemblé : `[before + still frame] → [clip vidéo + during voice] → [frozen frame + overflow during] → [after + still frame]` -- tous segments optionnels

### Requirements to Structure Mapping

| Feature | FRs | Fichiers clés |
|---------|-----|---------------|
| video-import | FR1-4 | `videoImportService.ts` (validation format, accès fichier) |
| video-processing | FR5-10 | `processingPipeline.ts` (orchestration), `blackScreenDetector.ts`, `templateMatcher.ts` |
| video-playback | FR11-15 | `VideoPlayer.tsx` (expo-av), `MinimapView.tsx` (ROI crop), `EpisodeNavigator.tsx` |
| audio-commentary | FR16-20 | `AudioRecorder.tsx` (expo-av recording), `audioCommentService.ts` (persistence) |
| clip-export | FR21-25 | `exportPipeline.ts` (FFmpeg demux/mux + audio overlay) |
| session | FR26-28 | `useSessionStore.ts` (Zustand+MMKV), `sessionRepository.ts` (SQLite) |
| auth | FR29-33 | `authService.ts` (Firebase JS), `subscriptionService.ts` (isPaid check) |

### Data Flow

```
Import MP4 → Processing Pipeline → [keyframes → black screen detect → template match] → MapSegments
                                                                                            ↓
                                                                              Session stored (SQLite)
                                                                                            ↓
                                                                              Playback (expo-av)
                                                                                    ↓           ↓
                                                                               POV view    Minimap (ROI)
                                                                                    ↓
                                                                           Audio commentary (expo-av)
                                                                                    ↓
                                                                           Clip export (FFmpeg mux)
                                                                                    ↓
                                                                           Standalone MP4 → Share
```

### External Integrations

| Service | Point d'intégration | Fichier |
|---------|---------------------|---------|
| Firebase Auth | Login + validation abo | `auth/authService.ts` |
| Firebase Firestore | Check `user.isPaid` | `auth/subscriptionService.ts` |
| Filesystem Android | Import vidéo, stockage audio | `shared/services/ffmpeg.ts`, `shared/utils/fileSystem.ts` |
| Share API | Partage clips exportés | `clip-export/` (via Expo Sharing) |

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility :**
Toutes les technologies choisies sont compatibles entre elles :
- Expo dev-client supporte les modules natifs (FFmpeg fork, react-native-fast-opencv, MMKV)
- expo-av (playback + recording) et FFmpeg (processing + export) ont des responsabilités distinctes sans conflit
- Zustand + MMKV persist middleware fonctionne nativement
- Firebase JS SDK (modular) fonctionne avec Expo sans module natif additionnel
- Toutes les libs sont cross-platform (Android + iOS ready)
- NativeWind (Babel plugin) + React Native Reusables compatibles avec Expo dev-client
- UX spec (design system, voice 3-slot, clip lifecycle, Card View sorting) alignée avec les décisions architecturales

**Pattern Consistency :**
- Conventions de nommage cohérentes à travers tous les layers (code, DB, storage)
- Organisation par feature alignée avec les 7 domaines FR du PRD
- Boundaries claires : services partagés comme seuls points d'accès aux libs natives

**Structure Alignment :**
- La structure projet reflète exactement les décisions architecturales
- Chaque feature map directement à un groupe de FRs
- Les integration points (services partagés) sont bien positionnés

### Requirements Coverage

**Functional Requirements : 33/33 couverts**

| Domaine | FRs | Feature | Statut |
|---------|-----|---------|--------|
| Import & gestion vidéo | FR1-4 | video-import | Couvert |
| Traitement vidéo | FR5-10 | video-processing | Couvert |
| Lecture & navigation | FR11-15 | video-playback | Couvert |
| Commentaires vocaux | FR16-20 | audio-commentary | Couvert |
| Export clips | FR21-25 | clip-export | Couvert |
| Persistance session | FR26-28 | session | Couvert |
| Auth & abonnement | FR29-33 | auth | Couvert |

**Non-Functional Requirements : 12/12 couverts**

| NFR | Cible | Solution architecturale |
|-----|-------|------------------------|
| NFR1 | Analyse < 2min | FFmpeg keyframes low-res + OpenCV template matching |
| NFR2 | Toggle < 100ms | Crop style change sur même source expo-av |
| NFR3 | Export rapide | FFmpeg mux, qualité configurable (720p/source) |
| NFR4 | UI responsive | Foreground service Android, processing séparé |
| NFR5 | RAM < 2GB | Keyframes low-res, traitement séquentiel |
| NFR6 | Save 30s | MMKV auto-save via autoSaveService |
| NFR7 | Reprise crash | State persistence MMKV + processingPipeline resumable |
| NFR8 | Audio immédiat | expo-av persist immédiat filesystem |
| NFR9 | Cache auth 30j | MMKV cache offline |
| NFR10-12 | Security | Firebase OAuth 2.0, privacy by design |

### Gap Analysis

**Aucun gap critique identifié.**

**Points d'attention (non bloquants) :**

| # | Point | Impact | Résolution |
|---|-------|--------|------------|
| 1 | Versions libs non spécifiées | Faible | Fixées à l'init projet, Expo gère la compatibilité |
| 2 | ~~Schema SQLite non défini~~ | ~~Faible~~ | **Résolu** -- schema défini dans section "SQLite Schema" (sessions, map_segments, clip_exports, audio_comments) |
| 3 | Templates carte OpenCV | Moyen | Images de référence à capturer, stockées dans `assets/images/map-templates/` |
| 4 | Foreground Service Android | Moyen | Config plugin Expo additionnel ou `expo-task-manager` à évaluer |

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Contexte projet analysé en profondeur
- [x] Scale et complexité évalués
- [x] Contraintes techniques identifiées
- [x] Cross-cutting concerns mappés

**Architectural Decisions**
- [x] Décisions critiques documentées (data, FFmpeg, OpenCV, playback, audio, auth)
- [x] Stack technique entièrement spécifié
- [x] Patterns d'intégration définis
- [x] Considérations de performance adressées
- [x] Stratégie cross-platform définie

**Implementation Patterns**
- [x] Conventions de nommage établies (code, DB, MMKV)
- [x] Patterns de structure définis (feature-based)
- [x] Patterns de state management spécifiés (Zustand)
- [x] Patterns d'error handling documentés

**Project Structure**
- [x] Structure de répertoires complète définie
- [x] Boundaries de composants établies
- [x] Points d'intégration mappés
- [x] Mapping features → FRs complet

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** Haute

**Forces clés :**
- Stack 100% cross-platform ready (Android MVP, iOS Phase 2 sans refactoring)
- Organisation par feature claire, chaque FR mappé à un fichier
- Services partagés comme seule couche d'accès aux libs natives (facile à remplacer si une lib change)
- Patterns simples adaptés au profil junior

**Axes d'amélioration future :**
- Schema SQLite détaillé (lors de l'implémentation)
- Stratégie de tests plus détaillée (unit, integration, E2E)
- Monitoring/analytics pour le suivi en production
- Gestion des mises à jour du schema DB (migrations)
