// Story 1.13 AC5 / AC6 / AC8 — the MMKV cache of the map-config overlay.
//
// Split from `mapConfigOverlay.ts` so the synchronous seam (`mapConfig.ts`) can
// read the cache WITHOUT importing Firebase: the seam never touches the
// network, and its import graph now says so. `mapConfigOverlay.ts` is the only
// writer (after a validated, newer Firestore read).
//
// Stored under `detection.mapConfigOverlay` as the envelope's JSON text
// (`storage.setString`); each `config_json` inside it is a string and therefore
// round-trips byte for byte — the map-order carrier survives the cache.

import { DetectionConfigEnvelopeSchema } from "@warden/contracts";
import type { z } from "zod";

import { storage } from "../../shared/services/storage";

export type DetectionConfigEnvelope = z.infer<typeof DetectionConfigEnvelopeSchema>;

export const MAP_CONFIG_OVERLAY_STORAGE_KEY = "detection.mapConfigOverlay";

/** `null` = not loaded yet; `{ envelope: undefined }` = loaded, nothing valid. */
let memo: { envelope: DetectionConfigEnvelope | undefined } | null = null;
let generation = 0;

/**
 * Bumped on every cache write/delete so mapConfig.ts can drop its memoised
 * candidate list. A session that already captured its candidate keeps it.
 */
export function getOverlayCacheGeneration(): number {
  return generation;
}

/**
 * The cached overlay envelope, validated against the envelope contract, or
 * `undefined`. A stored value that no longer parses or validates (corrupted
 * write, contract tightened by an app update) is deleted and ignored.
 */
export function readCachedOverlay(): DetectionConfigEnvelope | undefined {
  if (memo !== null) return memo.envelope;
  const raw = storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY);
  if (raw === undefined) {
    memo = { envelope: undefined };
    return undefined;
  }
  let parsed: ReturnType<typeof DetectionConfigEnvelopeSchema.safeParse>;
  try {
    parsed = DetectionConfigEnvelopeSchema.safeParse(JSON.parse(raw));
  } catch {
    parsed = { success: false } as typeof parsed;
  }
  if (!parsed.success) {
    console.warn("[map-config] cached overlay failed validation, discarding it");
    discardCachedOverlay();
    return undefined;
  }
  memo = { envelope: parsed.data };
  return parsed.data;
}

/** Delete the cached overlay (e.g. an entry failed re-validation on read). */
export function discardCachedOverlay(): void {
  storage.delete(MAP_CONFIG_OVERLAY_STORAGE_KEY);
  memo = { envelope: undefined };
  generation++;
}

export function writeCachedOverlay(envelope: DetectionConfigEnvelope): void {
  // The envelope is stored as JSON text; each `config_json` inside it is a
  // string and round-trips byte for byte.
  storage.setString(MAP_CONFIG_OVERLAY_STORAGE_KEY, JSON.stringify(envelope));
  memo = { envelope };
  generation++;
}

/** Test seam: forget the memo and the stored overlay. */
export function __resetMapConfigOverlayCacheForTests(): void {
  storage.delete(MAP_CONFIG_OVERLAY_STORAGE_KEY);
  memo = null;
  generation++;
}
