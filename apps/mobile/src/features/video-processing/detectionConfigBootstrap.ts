// Detection config bootstrap — called once during app startup.
//
// Behaviour:
//  - Calls getDetectionConfig() to populate the MMKV cache. Cache hit and
//    online success both clear the offline-block flag.
//  - Cache miss + network/not-found failure (typically offline-first-launch)
//    sets the offline-block flag so video-processing entry points refuse to
//    start until the user comes online once.
//  - Cache miss + malformed-remote failure does NOT set the offline-block
//    flag — going online won't fix a corrupt remote document, so showing the
//    "open while online" copy would be misleading. The error is logged.
//  - This bootstrap intentionally never throws — it only writes a flag.
//    The UI reads `isVideoProcessingBlocked()` on the processing entry
//    point and renders the error copy from AC 4.
//
// Concurrency: the bootstrap is singleflighted via a module-level promise.
// `getBootstrapPromise()` exposes that promise so consumers (e.g.
// useVideoProcessing) can await bootstrap completion before reading the
// gate, eliminating the TOCTOU race where a fast-tapping user reaches the
// processing entry point before the offline-first-launch flag is set.

import { storage } from "../../shared/services/storage";
import {
  getDetectionConfig,
  MalformedRemoteConfigError,
  OfflineFirstLaunchError,
  OFFLINE_FIRST_LAUNCH_MESSAGE,
} from "./detectionConfigService";

const OFFLINE_FIRST_LAUNCH_FLAG_KEY = "detection.offlineFirstLaunchBlocked";

let bootstrapPromise: Promise<void> | null = null;

export function isVideoProcessingBlocked(): {
  blocked: boolean;
  reason?: string;
} {
  if (storage.getBoolean(OFFLINE_FIRST_LAUNCH_FLAG_KEY) === true) {
    return { blocked: true, reason: OFFLINE_FIRST_LAUNCH_MESSAGE };
  }
  return { blocked: false };
}

/**
 * Run during app startup, after auth resolves. Never throws — sets a
 * flag that the video-processing entry point reads. Singleflighted:
 * a second call before the first completes returns the same promise.
 */
export function bootstrapDetectionConfig(): Promise<void> {
  if (bootstrapPromise) return bootstrapPromise;

  bootstrapPromise = (async () => {
    try {
      await getDetectionConfig();
      storage.delete(OFFLINE_FIRST_LAUNCH_FLAG_KEY);
    } catch (err) {
      if (err instanceof OfflineFirstLaunchError) {
        storage.setBoolean(OFFLINE_FIRST_LAUNCH_FLAG_KEY, true);
      } else if (err instanceof MalformedRemoteConfigError) {
        // Don't set the offline-first-launch flag — the user being online
        // won't help. Log so admin can spot a bad upload to Firestore.
        console.error(
          "[detectionConfigBootstrap] malformed remote config",
          err
        );
      } else {
        console.error("[detectionConfigBootstrap] unexpected error", err);
      }
    }
  })();

  return bootstrapPromise;
}

/**
 * Returns the in-flight bootstrap promise, or null if bootstrap has not been
 * kicked off yet (or has fully resolved and was reset). Consumers that read
 * `isVideoProcessingBlocked()` must await this first to avoid a TOCTOU race
 * with the first-launch-offline flag write.
 */
export function getBootstrapPromise(): Promise<void> | null {
  return bootstrapPromise;
}

export const __testing = {
  OFFLINE_FIRST_LAUNCH_FLAG_KEY,
  OFFLINE_FIRST_LAUNCH_MESSAGE,
  resetBootstrapPromise: (): void => {
    bootstrapPromise = null;
  },
};
