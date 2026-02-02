import * as Crypto from "expo-crypto";
import { getDatabase } from "../../shared/services/database";
import type { Session } from "../../shared/types";

function generateId(): string {
  return Crypto.randomUUID();
}

function nowISO(): string {
  return new Date().toISOString();
}

export async function createSession(
  videoFilePath: string,
  name?: string
): Promise<Session> {
  const db = await getDatabase();
  const id = generateId();
  const now = nowISO();

  await db.runAsync(
    `INSERT INTO sessions (id, video_file_path, name, status, created_at, updated_at)
     VALUES (?, ?, ?, 'importing', ?, ?)`,
    [id, videoFilePath, name ?? null, now, now]
  );

  return {
    id,
    video_file_path: videoFilePath,
    name: name ?? null,
    duration_ms: null,
    status: "importing",
    created_at: now,
    updated_at: now,
  };
}

export async function getSession(id: string): Promise<Session | null> {
  const db = await getDatabase();
  const row = await db.getFirstAsync<Session>(
    "SELECT * FROM sessions WHERE id = ?",
    [id]
  );
  return row ?? null;
}

export async function getAllSessions(): Promise<Session[]> {
  const db = await getDatabase();
  return db.getAllAsync<Session>(
    "SELECT * FROM sessions ORDER BY created_at DESC"
  );
}

export async function updateSessionStatus(
  id: string,
  status: Session["status"]
): Promise<void> {
  const db = await getDatabase();
  await db.runAsync(
    "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
    [status, nowISO(), id]
  );
}

export async function deleteSession(id: string): Promise<void> {
  const db = await getDatabase();
  // CASCADE will delete map_segments, clip_exports, audio_comments
  await db.runAsync("DELETE FROM sessions WHERE id = ?", [id]);
}
