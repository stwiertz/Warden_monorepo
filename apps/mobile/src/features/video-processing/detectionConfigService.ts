// Detection config fetch + MMKV cache.
//
// Pipeline (per Story 7.4 ACs):
//  - getDetectionConfig(): returns cached config when fresh/offline, fetches
//    from Firestore otherwise. Stale-while-revalidate: when a cache exists,
//    the cached value is returned synchronously and a background refresh is
//    kicked off only if the remote `version` is greater.
//  - refreshDetectionConfig(): forces a full Firestore fetch, returns true
//    if the cache was updated (remote.version > cached.version OR no cache).
//  - On any failure, the existing cached value is preserved and the error
//    is logged. A failure with no cache is surfaced via the
//    `OfflineFirstLaunchError` (network/not-found) or
//    `MalformedRemoteConfigError` (validation throw — document exists but is
//    schema-invalid) so callers can disambiguate the user-facing copy.
//
// The Firestore document is `detection_config/latest` (single-doc collection,
// see Dev Notes in 7.4). Storage key follows MMKV convention: `detection.config`.
//
// Concurrency: getDetectionConfig, refreshDetectionConfig, and backgroundRefresh
// each guard their network path with a singleflight in-flight promise so that
// concurrent callers (e.g. multiple per-frame detector reads in Story 7.5)
// share a single Firestore round-trip and a single cache write.

import { doc, getDoc, getFirestore } from "firebase/firestore";
import { app } from "../auth/firebaseConfig";
import { storage } from "../../shared/services/storage";
import {
  validateDetectionConfig,
  type DetectionConfig,
} from "./detectionConfig";

export const DETECTION_CONFIG_STORAGE_KEY = "detection.config";
export const DETECTION_CONFIG_DOC_PATH = "detection_config/latest";

export const OFFLINE_FIRST_LAUNCH_MESSAGE =
  "Initial setup requires internet — open the app once while online.";

interface CachedDetectionConfig {
  config: DetectionConfig;
  fetchedAt: number;
}

export class OfflineFirstLaunchError extends Error {
  constructor() {
    super(OFFLINE_FIRST_LAUNCH_MESSAGE);
    this.name = "OfflineFirstLaunchError";
  }
}

export class MalformedRemoteConfigError extends Error {
  constructor(public readonly cause: Error) {
    super(`Detection config payload is malformed: ${cause.message}`);
    this.name = "MalformedRemoteConfigError";
  }
}

// Module-level memoization so per-frame reads in Story 7.5's hot path don't
// re-parse JSON or re-validate. `memoCache === null` means "not loaded yet";
// `memoCache.result === undefined` means "loaded and confirmed empty/invalid".
// The memo is invalidated by writeCache (which then re-populates it from the
// just-written value) and by __clearDetectionConfigCacheForTests.
let memoCache: { result: CachedDetectionConfig | undefined } | null = null;

function readCache(): CachedDetectionConfig | undefined {
  if (memoCache !== null) return memoCache.result;

  const raw = storage.getObject<CachedDetectionConfig>(
    DETECTION_CONFIG_STORAGE_KEY
  );
  if (!raw || typeof raw !== "object") {
    memoCache = { result: undefined };
    return undefined;
  }
  try {
    const config = validateDetectionConfig(raw.config);
    const fetchedAt = typeof raw.fetchedAt === "number" ? raw.fetchedAt : 0;
    const result: CachedDetectionConfig = { config, fetchedAt };
    memoCache = { result };
    return result;
  } catch (err) {
    // Cached payload no longer matches the schema (corrupted MMKV write,
    // or schema migration after an app update). Discard so we behave as a
    // cache-miss rather than handing a typed-but-invalid object to consumers.
    console.warn(
      "[detectionConfig] cached config failed validation, discarding",
      err
    );
    storage.delete(DETECTION_CONFIG_STORAGE_KEY);
    memoCache = { result: undefined };
    return undefined;
  }
}

function writeCache(config: DetectionConfig): void {
  const payload: CachedDetectionConfig = {
    config,
    fetchedAt: Date.now(),
  };
  storage.setObject(DETECTION_CONFIG_STORAGE_KEY, payload);
  // Refresh memo with the just-written, freshly validated value so the next
  // read is free.
  memoCache = { result: payload };
}

async function fetchRemoteConfig(): Promise<DetectionConfig> {
  const db = getFirestore(app);
  const ref = doc(db, DETECTION_CONFIG_DOC_PATH);
  const snap = await getDoc(ref);
  if (!snap.exists()) {
    throw new Error(
      `DetectionConfig: Firestore document ${DETECTION_CONFIG_DOC_PATH} does not exist`
    );
  }
  try {
    return validateDetectionConfig(snap.data());
  } catch (err) {
    throw new MalformedRemoteConfigError(
      err instanceof Error ? err : new Error(String(err))
    );
  }
}

let inflightInitialFetch: Promise<DetectionConfig> | null = null;
let inflightBackgroundRefresh: Promise<void> | null = null;
let inflightForcedRefresh: Promise<boolean> | null = null;

/**
 * Get the active detection config. Stale-while-revalidate:
 *   - cache present + online: return cache, refresh in background only when
 *     the remote version is greater.
 *   - cache present + offline: return cache (any fetch error is logged).
 *   - no cache + online + valid payload: fetch synchronously, cache, return.
 *   - no cache + offline (or document missing): throws OfflineFirstLaunchError.
 *   - no cache + malformed remote: throws MalformedRemoteConfigError so the
 *     bootstrap can avoid the misleading "open while online" copy.
 *
 * Background refresh errors are logged but never propagated — the cache is
 * the source of truth for the running session. Concurrent callers share a
 * single in-flight fetch via singleflight.
 */
export async function getDetectionConfig(): Promise<DetectionConfig> {
  const cached = readCache();

  if (cached) {
    void backgroundRefresh(cached.config.version);
    return cached.config;
  }

  if (inflightInitialFetch) return inflightInitialFetch;

  inflightInitialFetch = (async () => {
    try {
      const config = await fetchRemoteConfig();
      writeCache(config);
      return config;
    } catch (err) {
      console.error("[detectionConfig] initial fetch failed", err);
      if (err instanceof MalformedRemoteConfigError) throw err;
      throw new OfflineFirstLaunchError();
    } finally {
      inflightInitialFetch = null;
    }
  })();

  return inflightInitialFetch;
}

async function backgroundRefresh(cachedVersion: number): Promise<void> {
  if (inflightBackgroundRefresh) return inflightBackgroundRefresh;

  inflightBackgroundRefresh = (async () => {
    try {
      const remote = await fetchRemoteConfig();
      if (remote.version > cachedVersion) {
        writeCache(remote);
      }
    } catch (err) {
      console.warn("[detectionConfig] background refresh failed", err);
    } finally {
      inflightBackgroundRefresh = null;
    }
  })();

  return inflightBackgroundRefresh;
}

/**
 * Force a Firestore fetch. Returns true if the cache was updated (remote
 * version > cached version, or no cache existed). On failure, keeps the
 * existing cache and returns false. Singleflighted: concurrent callers
 * share the same fetch.
 */
export async function refreshDetectionConfig(): Promise<boolean> {
  if (inflightForcedRefresh) return inflightForcedRefresh;

  inflightForcedRefresh = (async () => {
    const cached = readCache();
    try {
      const remote = await fetchRemoteConfig();
      if (!cached || remote.version > cached.config.version) {
        writeCache(remote);
        return true;
      }
      return false;
    } catch (err) {
      console.warn("[detectionConfig] forced refresh failed", err);
      return false;
    } finally {
      inflightForcedRefresh = null;
    }
  })();

  return inflightForcedRefresh;
}

/**
 * Synchronous accessor for callers that already know a config has been
 * loaded into the cache (e.g. detectors invoked after app startup gated on
 * getDetectionConfig). Returns undefined when no cache is present or when
 * the cached payload no longer matches the schema, so callers can fall back
 * to their own defaults — used by the Task 4 shim in blackScreenDetector.ts
 * until Story 7.5 fully wires this through.
 */
export function getCachedDetectionConfig(): DetectionConfig | undefined {
  return readCache()?.config;
}

/**
 * Test-only — clears the cache + memo + resets singleflight state. Not
 * exported through the feature barrel.
 */
export function __clearDetectionConfigCacheForTests(): void {
  storage.delete(DETECTION_CONFIG_STORAGE_KEY);
  memoCache = null;
  inflightInitialFetch = null;
  inflightBackgroundRefresh = null;
  inflightForcedRefresh = null;
}
