# Data Models — apps/mobile

Two stores: **expo-sqlite** (durable rows) + **react-native-mmkv** (KV cache + checkpoints + state-persistence). Plus consumed-only **Firestore** documents.

## SQLite — `warden.db`

Defined and initialised in [src/shared/services/database.ts](../apps/mobile/src/shared/services/database.ts). Pragmas: `journal_mode = WAL`, `foreign_keys = ON`. Schema initialised on first `getDatabase()` call (singleton).

Domain types in [src/shared/types/index.ts](../apps/mobile/src/shared/types/index.ts) match the SQL columns 1:1 (snake_case in both layers).

### `sessions`

A session = an imported video file under analysis.

| Column            | Type    | Constraints                                                           |
| ----------------- | ------- | --------------------------------------------------------------------- |
| `id`              | TEXT    | PRIMARY KEY (UUID via `expo-crypto`)                                  |
| `video_file_path` | TEXT    | NOT NULL                                                              |
| `name`            | TEXT    | nullable (defaults to filename without `.mp4` if user didn't specify) |
| `duration_ms`     | INTEGER | nullable (filled in by FFmpeg probe during processing)                |
| `status`          | TEXT    | NOT NULL, CHECK(`importing`, `processing`, `ready`, `error`)          |
| `created_at`      | TEXT    | NOT NULL (ISO 8601)                                                   |
| `updated_at`      | TEXT    | NOT NULL (ISO 8601)                                                   |

**Lifecycle:**

- `importing` (created by [videoImportService.pickAndImportVideo](../apps/mobile/src/features/video-import/videoImportService.ts))
- → `processing` (set at the start of `runProcessingPipeline`)
- → `ready` (after stage 4 completes) **or** `error` (caught at any stage; checkpoint stays so user can retry)

CRUD lives in [features/session/sessionRepository.ts](../apps/mobile/src/features/session/sessionRepository.ts) — `createSession`, `getSession`, `getAllSessions`, `updateSessionStatus`, `deleteSession` (cascades).

### `map_segments`

One row per detected round in a session. Created in bulk by [features/video-processing/segmentRepository.insertMapSegments](../apps/mobile/src/features/video-processing/segmentRepository.ts).

| Column              | Type    | Constraints                                                         |
| ------------------- | ------- | ------------------------------------------------------------------- |
| `id`                | TEXT    | PRIMARY KEY (UUID)                                                  |
| `session_id`        | TEXT    | NOT NULL, REFERENCES `sessions(id)` ON DELETE CASCADE               |
| `map_index`         | INTEGER | NOT NULL — 0-based ordinal within the session                       |
| `start_time_ms`     | INTEGER | NOT NULL                                                            |
| `end_time_ms`       | INTEGER | NOT NULL                                                            |
| `map_name`          | TEXT    | nullable when pHash had no fingerprint within `collision_threshold` |
| `result_frame_path` | TEXT    | nullable until stage 4 (results) extracts the score-screen thumb    |
| `score_orange`      | INTEGER | nullable — score parsing not yet implemented                        |
| `score_blue`        | INTEGER | nullable — same                                                     |
| `created_at`        | TEXT    | NOT NULL                                                            |

Index: `idx_map_segments_session ON map_segments(session_id)`.

`updateResultFramePath(segmentId, path)` is called per segment after `extractFrameAt` succeeds — see [processingPipeline.ts](../apps/mobile/src/features/video-processing/processingPipeline.ts).

### `clip_exports`

User-defined clips of a `map_segments` row, with view mode and export quality.

| Column           | Type    | Constraints                                                           |
| ---------------- | ------- | --------------------------------------------------------------------- |
| `id`             | TEXT    | PRIMARY KEY                                                           |
| `session_id`     | TEXT    | NOT NULL, REFERENCES `sessions(id)` ON DELETE CASCADE                 |
| `map_segment_id` | TEXT    | NOT NULL, REFERENCES `map_segments(id)` ON DELETE CASCADE             |
| `start_time_ms`  | INTEGER | NOT NULL                                                              |
| `end_time_ms`    | INTEGER | NOT NULL                                                              |
| `view_mode`      | TEXT    | NOT NULL, CHECK(`pov`, `minimap`)                                     |
| `status`         | TEXT    | NOT NULL, CHECK(`defining`, `locked`, `exporting`, `ready`, `shared`) |
| `export_quality` | TEXT    | nullable, CHECK(`mobile`, `hd`) — null until export starts            |
| `file_path`      | TEXT    | nullable until export completes                                       |
| `created_at`     | TEXT    | NOT NULL                                                              |
| `updated_at`     | TEXT    | NOT NULL                                                              |

Indexes: `idx_clip_exports_session ON clip_exports(session_id)`, `idx_clip_exports_segment ON clip_exports(map_segment_id)`.

### `audio_comments`

Coach voice-over slots per clip.

| Column           | Type    | Constraints                                               |
| ---------------- | ------- | --------------------------------------------------------- |
| `id`             | TEXT    | PRIMARY KEY                                               |
| `clip_export_id` | TEXT    | NOT NULL, REFERENCES `clip_exports(id)` ON DELETE CASCADE |
| `slot`           | TEXT    | NOT NULL, CHECK(`before`, `during`, `after`)              |
| `file_path`      | TEXT    | NOT NULL                                                  |
| `duration_ms`    | INTEGER | NOT NULL                                                  |
| `created_at`     | TEXT    | NOT NULL                                                  |

Index: `idx_audio_comments_clip ON audio_comments(clip_export_id)`.

## Cascade summary

```
sessions (delete cascades)
├── map_segments (delete cascades)
│   └── clip_exports (delete cascades)
│       └── audio_comments
└── clip_exports also references sessions directly (CASCADE), in case of orphaning
```

`deleteSession(id)` issues a single `DELETE FROM sessions WHERE id = ?` — `PRAGMA foreign_keys = ON` plus `ON DELETE CASCADE` does the rest.

## MMKV — react-native-mmkv

Singleton: `new MMKV({ id: 'warden-storage' })` in [src/shared/services/storage.ts](../apps/mobile/src/shared/services/storage.ts). Typed wrapper exposes `getString`, `setString`, `getNumber`, `setNumber`, `getBoolean`, `setBoolean`, `getObject<T>`, `setObject<T>`, `delete`, `clearAll`. Plus a Zustand `StateStorage` adapter `zustandMMKVStorage`.

Pin policy: **stays on v3** — v4 needs Nitro Modules, whose 0.33.x line targets RN 0.83 and crashes silently on RN 0.81 (boot-time TypeError on `new MMKV()` because the JSI binding fails to register). Re-evaluate when upgrading React Native.

### Key conventions

Dot-notation, grouped by feature.

| Key                                         | Type   | Source                                                                                                       | Purpose                                                                                                                                                              |
| ------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `auth-store`                                | object | zustand persist ([useAuthStore.ts](../apps/mobile/src/features/auth/useAuthStore.ts))                        | Partialized: `{user, isAuthenticated, cachedAt}`. 30-day TTL invalidates on rehydration.                                                                             |
| `session-store`                             | object | zustand persist ([useSessionStore.ts](../apps/mobile/src/features/session/useSessionStore.ts))               | `{currentSessionId, currentEpisodeIndex, playbackPositionMs, viewMode, sortOrder}`.                                                                                  |
| `processing.<sessionId>.stage`              | string | [processingPipeline.ts](../apps/mobile/src/features/video-processing/processingPipeline.ts) `saveCheckpoint` | Last fully-completed stage: `keyframes` / `detection` / `segmentation` / `results`. Cleared on success.                                                              |
| `processing.<sessionId>.events`             | object | pipeline detection stage                                                                                     | `GameDetectorEvent[]`                                                                                                                                                |
| `processing.<sessionId>.gameSegments`       | object | pipeline detection stage                                                                                     | `GameSegmentTimeline[]`                                                                                                                                              |
| `processing.<sessionId>.mapIdentifications` | object | pipeline detection stage                                                                                     | `MapIdentificationResult[]`                                                                                                                                          |
| `processing.<sessionId>.duration`           | number | pipeline detection / results                                                                                 | Video duration cached for results-stage clamp                                                                                                                        |
| `processing.<sessionId>.segmentIds`         | object | pipeline segmentation stage                                                                                  | `string[]` of saved row ids — used to update `result_frame_path` per segment in stage 4                                                                              |
| `processing.<sessionId>.segmentData`        | object | pipeline segmentation stage                                                                                  | `MapSegmentData[]` mirror for resume                                                                                                                                 |
| `detection.config`                          | object | [detectionConfigService.ts](../apps/mobile/src/features/video-processing/detectionConfigService.ts)          | `{config: DetectionConfig, fetchedAt: number}` — local cache of Firestore `detection_config/latest`. Validated on every read; invalid payloads are deleted silently. |

Reserved-but-unused per the inline comment in `storage.ts`: `auth.token`, `auth.user`, `auth.expiresAt`, `prefs.sortOrder`, `prefs.exportQuality`. (Some of these are subsumed by zustand-persisted stores.)

## Firestore (read-only from mobile)

### `users/{uid}`

Read in [features/auth/subscriptionService.ts](../apps/mobile/src/features/auth/subscriptionService.ts).

The shape used by mobile (from inline comment + code):

```ts
{
  status: 'active' | 'trialing' | 'canceled' | 'past_due' | 'incomplete' | ...,
  current_period_end: Timestamp,
  plan?: 'monthly' | 'yearly',
  stripe_customer_id?: string,
  stripe_subscription_id?: string,
  created_at?: Timestamp,
  updated_at?: Timestamp
}
```

`isSubscriptionPaid(data)` returns true iff:

- `status` is in `['active', 'trialing']`, AND
- `current_period_end` is a Firestore `Timestamp` AND `current_period_end.toMillis() > Date.now()`.

Network failures fall back to the cached `useAuthStore.user.isPaid` rather than logging the user out.

The schema is governed by [contracts/user-doc.schema.json](../contracts/user-doc.schema.json) (with `additionalProperties: true` to tolerate the legacy `isPaid` field).

### `detection_config/latest`

Single-doc collection. Path constant: `DETECTION_CONFIG_DOC_PATH = 'detection_config/latest'`. MMKV cache key: `DETECTION_CONFIG_STORAGE_KEY = 'detection.config'`.

Shape (validated by `validateDetectionConfig` — schema not co-located here; see legacy distillate `05-architecture-cross-cutting.md` for the full DetectionConfig schema). Includes:

- `version` (number — drives stale-while-revalidate)
- `reference_resolution`
- `roi_zones` — named rectangles (`team_bar`, `kda`, `notkda`, `points`, `map_name`, `vertical`, `minimap`, `personnalbar`)
- pHash params (`canvas_size`, `hash_size`, `hash_method`, `text_anchor_width`, `tile_cols`, `shift_tolerance`)
- `maps` — `{ [mapName]: hexHash }` (the same fingerprints emitted by `apps/tooling`)
- HSV bands for colour detection

`detection_config/latest` and the tooling-emitted `map_config.json` are sibling artefacts — Phase 6 must decide whether mobile fetches via Firestore (current) or bundles `map_config.json` as a Metro asset.

## Type vs. row alignment

The type definitions in [src/shared/types/index.ts](../apps/mobile/src/shared/types/index.ts) follow `snake_case` to match SQL columns directly. Repositories return rows verbatim. There is **no DTO mapping layer** — domain types ARE the persistence shape. This is deliberate (the app is small enough that an extra mapping layer is overkill), but means future Firestore-write paths must consciously translate to whatever shape Firestore expects.

## What's not modeled here

- Coach profiles / multi-coach support — out of scope for current sprint.
- Sharing / collab metadata — `clip_exports.status = 'shared'` exists but no peer-side data model.
- Detection config history — only `latest` is consulted; the version counter is the only audit trail.
