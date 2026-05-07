# Component Inventory — apps/mobile

Catalogues UI surfaces for the Expo/RN app. Two layers:

1. **Reusable design-system primitives** under [`src/shared/components/`](../apps/mobile/src/shared/components/).
2. **Feature-owned screens** under [`src/features/<slice>/`](../apps/mobile/src/features/).

Mobile uses **NativeWind 4** (Tailwind classes on RN) for styling, plus a custom HUD design system under `src/shared/components/hud/`.

## Shared — design-system primitives

[src/shared/components/](../apps/mobile/src/shared/components/)

| Component                                                                 | Purpose                            | Notes |
| ------------------------------------------------------------------------- | ---------------------------------- | ----- |
| [Button](../apps/mobile/src/shared/components/Button.tsx)                 | Generic button                     |       |
| [Card](../apps/mobile/src/shared/components/Card.tsx)                     | Generic card container             |       |
| [LoadingSpinner](../apps/mobile/src/shared/components/LoadingSpinner.tsx) | Indeterminate spinner              |       |
| [Toast](../apps/mobile/src/shared/components/Toast.tsx)                   | Lightweight transient notification |       |
| `index.ts`                                                                | Barrel re-exports                  |       |

### HUD atoms — [src/shared/components/hud/](../apps/mobile/src/shared/components/hud/)

A custom HUD-style design system used by feature screens (matches the legacy `warden-mocks` JSX/HTML mockups).

| Atom         | File                                                                          | Role                                           |
| ------------ | ----------------------------------------------------------------------------- | ---------------------------------------------- |
| Screen       | [Screen.tsx](../apps/mobile/src/shared/components/hud/Screen.tsx)             | Top-level page wrapper with HUD chrome         |
| HudBracket   | [HudBracket.tsx](../apps/mobile/src/shared/components/hud/HudBracket.tsx)     | Bracket-style frame for sections               |
| CornerTick   | [CornerTick.tsx](../apps/mobile/src/shared/components/hud/CornerTick.tsx)     | Corner ornament for HudBracket                 |
| Stamp        | [Stamp.tsx](../apps/mobile/src/shared/components/hud/Stamp.tsx)               | Decorative stamp/seal                          |
| Marks        | [Marks.tsx](../apps/mobile/src/shared/components/hud/Marks.tsx)               | Tick-mark decorators                           |
| Field        | [Field.tsx](../apps/mobile/src/shared/components/hud/Field.tsx)               | Input/label field with HUD styling             |
| CircleBtn    | [CircleBtn.tsx](../apps/mobile/src/shared/components/hud/CircleBtn.tsx)       | Circular icon button                           |
| EngageButton | [EngageButton.tsx](../apps/mobile/src/shared/components/hud/EngageButton.tsx) | Primary call-to-action button                  |
| Icon         | [Icon.tsx](../apps/mobile/src/shared/components/hud/Icon.tsx)                 | Icon wrapper                                   |
| MapArt       | [MapArt.tsx](../apps/mobile/src/shared/components/hud/MapArt.tsx)             | Per-map artwork                                |
| Timeline     | [Timeline.tsx](../apps/mobile/src/shared/components/hud/Timeline.tsx)         | Scrubbable timeline (used in Cinema/Clip mode) |
| `tokens.ts`  | [tokens.ts](../apps/mobile/src/shared/components/hud/tokens.ts)               | Design tokens (colours, font sizes, spacing)   |
| `index.ts`   | barrel                                                                        |                                                |

These are all leaf-level RN components with no internal state beyond presentational. Stateful logic stays in feature folders.

## Features — screens

| Feature          | Screen            | File                                                                                                                | Role                                                                                  |
| ---------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| auth             | LoginScreen       | [features/auth/LoginScreen.tsx](../apps/mobile/src/features/auth/LoginScreen.tsx)                                   | Email/password + Google sign-in form. Reads `useAuthStore` for `isLoading` / `error`. |
| (root)           | HomeScreen        | [app/screens/HomeScreen.tsx](../apps/mobile/src/app/screens/HomeScreen.tsx)                                         | Post-auth landing — entry to Session list / new import.                               |
| session          | SessionList       | [features/session/SessionList.tsx](../apps/mobile/src/features/session/SessionList.tsx)                             | List of `sessions` rows.                                                              |
| session          | CardViewScreen    | [features/session/CardViewScreen.tsx](../apps/mobile/src/features/session/CardViewScreen.tsx)                       | Per-segment thumbnails ("cards") with sort options.                                   |
| video-processing | ProcessingScreen  | [features/video-processing/ProcessingScreen.tsx](../apps/mobile/src/features/video-processing/ProcessingScreen.tsx) | Pipeline progress UI; route param `{ sessionId }`.                                    |
| video-playback   | CinemaModeScreen  | [features/video-playback/CinemaModeScreen.tsx](../apps/mobile/src/features/video-playback/CinemaModeScreen.tsx)     | Full-clip review mode.                                                                |
| clip-export      | ClipModeScreen    | [features/clip-export/ClipModeScreen.tsx](../apps/mobile/src/features/clip-export/ClipModeScreen.tsx)               | Clip definition (in/out trim).                                                        |
| clip-export      | ExportShareScreen | [features/clip-export/ExportShareScreen.tsx](../apps/mobile/src/features/clip-export/ExportShareScreen.tsx)         | Export-quality selection + share handoff.                                             |

## Feature non-components (logic)

For each feature, services / repositories / stores / hooks. Listed here because they tend to come up alongside component review.

### auth — [features/auth/](../apps/mobile/src/features/auth/)

| File                     | Type          | Role                                                 |
| ------------------------ | ------------- | ---------------------------------------------------- |
| `firebaseConfig.ts`      | module        | App init + AsyncStorage persistence wrapper          |
| `authService.ts`         | module        | login/logout/listenToAuthChanges + `formatAuthError` |
| `googleSignInService.ts` | module        | Google sign-in configure + sign-in flow              |
| `subscriptionService.ts` | module        | `users/{uid}` read + 60-min revalidation             |
| `useAuthStore.ts`        | Zustand store | Auth state + 30-day MMKV persist                     |
| `LoginScreen.tsx`        | screen        | UI for email/password + Google                       |

### session — [features/session/](../apps/mobile/src/features/session/)

| File                                    | Type          | Role                                                                    |
| --------------------------------------- | ------------- | ----------------------------------------------------------------------- |
| `sessionRepository.ts`                  | module        | CRUD over `sessions` SQLite                                             |
| `useSessionStore.ts`                    | Zustand store | Current session UI state (episode index, playback pos, view mode, sort) |
| `SessionList.tsx`, `CardViewScreen.tsx` | screens       |                                                                         |

### video-import — [features/video-import/](../apps/mobile/src/features/video-import/)

| File                    | Type   | Role                                                         |
| ----------------------- | ------ | ------------------------------------------------------------ |
| `videoImportService.ts` | module | DocumentPicker + MIME/extension validation + `createSession` |
| `useVideoImport.ts`     | hook   | Wraps `pickAndImportVideo` + result state                    |
| `types.ts`              | types  | `ValidationError`, `ImportOutcome`                           |

### video-processing — [features/video-processing/](../apps/mobile/src/features/video-processing/)

| File                          | Type   | Role                                                                                                                    |
| ----------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------- |
| `processingPipeline.ts`       | module | 4-stage orchestrator with MMKV checkpoints (see [architecture-mobile.md](./architecture-mobile.md))                     |
| `detectionConfig.ts`          | module | Schema + `validateDetectionConfig`                                                                                      |
| `detectionConfigService.ts`   | module | Stale-while-revalidate Firestore cache                                                                                  |
| `detectionConfigBootstrap.ts` | module | App-boot detection-config primer                                                                                        |
| `gameDetector.ts`             | module | KDA/HSV detector — short-GOP path                                                                                       |
| `blackScreenDetector.ts`      | module | Black-screen detector — long-GOP fallback (2-pass)                                                                      |
| `mapIdentifier.ts`            | module | pHash matching against `maps`                                                                                           |
| `segmentation.ts`             | module | START/END pairing + `buildMapSegments`                                                                                  |
| `segmentRepository.ts`        | module | SQLite `map_segments` writer                                                                                            |
| `useVideoProcessing.ts`       | hook   | Pipeline launch + progress callback wiring                                                                              |
| `types.ts`                    | types  | `ProcessingStage`, `KeyframeInfo`, `GameDetectorEvent`, `MapIdentificationResult`, `MapSegmentData`, `ProgressCallback` |
| `ProcessingScreen.tsx`        | screen |                                                                                                                         |

### clip-export, video-playback, audio-commentary

Limited to screens (and any internal helpers not enumerated). All stateful logic that crosses screen boundaries goes through `useSessionStore` or feature-local hooks.

## Navigation

[src/app/RootNavigator.tsx](../apps/mobile/src/app/RootNavigator.tsx) — single `@react-navigation/native-stack`, auth-gated:

```ts
RootStackParamList = {
  Login: undefined,
  Home: undefined,
  Processing: { sessionId: string },
}
```

When `useAuthStore.isAuthenticated === true` → renders `Home` + `Processing`. When false → renders `Login` only.

Stack screen options: `headerShown: false`, dark backdrop `#101014`, `animation: 'fade'`.

The other screens (CardView, Cinema, ClipMode, ExportShare) **do not appear in `RootStackParamList`** as of this snapshot. They're either reached via in-screen navigation (e.g. tabs) or pending stack registration. Verify before adding a deep link to any of them.

## What's not yet inventoried

- Modal patterns, toast positioning, error boundary placement — investigate when/if regression coverage demands it.
- `audio-commentary/` subfolder is empty as of this scan (per directory listing). Story 6 work pending.

## Conventions

- Filename casing: `PascalCase.tsx` for components/screens, `camelCase.ts` for modules/hooks.
- One folder per feature; tests live in `__tests__/` next to subjects.
- Atoms in `shared/components/` and `shared/components/hud/` are presentational only — no Firestore / SQLite / MMKV imports.
- `tokens.ts` is the single source of truth for HUD colours/spacing — components consume via Tailwind classes that reference NativeWind theme + raw token usage.
