import * as Crypto from "expo-crypto";
import { getDatabase } from "../../shared/services/database";
import type { MapSegment } from "../../shared/types";
import type { MapSegmentData } from "./types";

function generateId(): string {
  return Crypto.randomUUID();
}

function nowISO(): string {
  return new Date().toISOString();
}

/**
 * Bulk insert map segments for a session.
 */
export async function insertMapSegments(
  sessionId: string,
  segments: MapSegmentData[]
): Promise<MapSegment[]> {
  const db = await getDatabase();
  const now = nowISO();
  const results: MapSegment[] = [];

  for (const seg of segments) {
    const id = generateId();
    await db.runAsync(
      `INSERT INTO map_segments (id, session_id, map_index, start_time_ms, end_time_ms, map_name, result_frame_path, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        id,
        sessionId,
        seg.mapIndex,
        seg.startTimeMs,
        seg.endTimeMs,
        seg.mapName,
        seg.resultFramePath,
        now,
      ]
    );

    results.push({
      id,
      session_id: sessionId,
      map_index: seg.mapIndex,
      start_time_ms: seg.startTimeMs,
      end_time_ms: seg.endTimeMs,
      map_name: seg.mapName,
      result_frame_path: seg.resultFramePath,
      score_orange: null,
      score_blue: null,
      created_at: now,
    });
  }

  return results;
}

/**
 * Get all map segments for a session, ordered by map_index.
 */
export async function getMapSegments(
  sessionId: string
): Promise<MapSegment[]> {
  const db = await getDatabase();
  return db.getAllAsync<MapSegment>(
    "SELECT * FROM map_segments WHERE session_id = ? ORDER BY map_index ASC",
    [sessionId]
  );
}

/**
 * Update the result frame path for a segment.
 */
export async function updateResultFramePath(
  segmentId: string,
  resultFramePath: string
): Promise<void> {
  const db = await getDatabase();
  await db.runAsync(
    "UPDATE map_segments SET result_frame_path = ? WHERE id = ?",
    [resultFramePath, segmentId]
  );
}
