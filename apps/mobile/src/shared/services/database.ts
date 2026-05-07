import * as SQLite from "expo-sqlite";

const DATABASE_NAME = "warden.db";

let db: SQLite.SQLiteDatabase | null = null;

export async function getDatabase(): Promise<SQLite.SQLiteDatabase> {
  if (db) return db;
  db = await SQLite.openDatabaseAsync(DATABASE_NAME);
  await initializeSchema(db);
  return db;
}

async function initializeSchema(database: SQLite.SQLiteDatabase): Promise<void> {
  await database.execAsync(`
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS sessions (
      id              TEXT PRIMARY KEY,
      video_file_path TEXT NOT NULL,
      name            TEXT,
      duration_ms     INTEGER,
      status          TEXT CHECK(status IN ('importing', 'processing', 'ready', 'error')) NOT NULL,
      created_at      TEXT NOT NULL,
      updated_at      TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS map_segments (
      id                TEXT PRIMARY KEY,
      session_id        TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
      map_index         INTEGER NOT NULL,
      start_time_ms     INTEGER NOT NULL,
      end_time_ms       INTEGER NOT NULL,
      map_name          TEXT,
      result_frame_path TEXT,
      score_orange      INTEGER,
      score_blue        INTEGER,
      created_at        TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS clip_exports (
      id              TEXT PRIMARY KEY,
      session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
      map_segment_id  TEXT NOT NULL REFERENCES map_segments(id) ON DELETE CASCADE,
      start_time_ms   INTEGER NOT NULL,
      end_time_ms     INTEGER NOT NULL,
      view_mode       TEXT CHECK(view_mode IN ('pov', 'minimap')) NOT NULL,
      status          TEXT CHECK(status IN ('defining', 'locked', 'exporting', 'ready', 'shared')) NOT NULL,
      export_quality  TEXT CHECK(export_quality IN ('mobile', 'hd')),
      file_path       TEXT,
      created_at      TEXT NOT NULL,
      updated_at      TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS audio_comments (
      id              TEXT PRIMARY KEY,
      clip_export_id  TEXT NOT NULL REFERENCES clip_exports(id) ON DELETE CASCADE,
      slot            TEXT CHECK(slot IN ('before', 'during', 'after')) NOT NULL,
      file_path       TEXT NOT NULL,
      duration_ms     INTEGER NOT NULL,
      created_at      TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_map_segments_session ON map_segments(session_id);
    CREATE INDEX IF NOT EXISTS idx_clip_exports_session ON clip_exports(session_id);
    CREATE INDEX IF NOT EXISTS idx_clip_exports_segment ON clip_exports(map_segment_id);
    CREATE INDEX IF NOT EXISTS idx_audio_comments_clip ON audio_comments(clip_export_id);
  `);
}

export async function closeDatabase(): Promise<void> {
  if (db) {
    await db.closeAsync();
    db = null;
  }
}
