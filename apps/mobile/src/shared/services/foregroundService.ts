// Story 1.2 (BF-5) — JS wrapper for the Android foreground service bridge.
//
// Exposes a typed, platform-guarded start/stop surface over the native
// `WardenProcessing` module (apps/mobile/plugins/with-foreground-service.js →
// WardenProcessingModule.kt). The foreground service keeps the JS context
// alive while `runProcessingPipeline` runs in the background (J2).
//
// Guarantees this wrapper provides so callers (processingPipeline.ts) stay clean:
//   - iOS no-op: all functions early-return on non-Android.
//   - Native-module-missing swallow: in jest (and any build where the native
//     module isn't linked) the calls resolve silently with a __DEV__ warning,
//     so the existing test surface never sees the bridge.
//   - POST_NOTIFICATIONS just-in-time request (Android 13+) fired on start,
//     WITHOUT gating the service start on the dialog — the pipeline must never
//     block on user interaction (AC9).
//   - Owner token: the latest start(sessionId) owns the singleton service;
//     stop(sessionId) from a stale owner is a no-op, so a finishing pipeline
//     cannot strip J2 protection from a newer concurrent run.
//   - stop never rejects: a native stop failure is swallowed — a rejection
//     thrown from the pipeline's `finally` would mask the real pipeline error
//     (or fail a run whose session is already "ready").
//
// iOS Phase 2: BGTaskScheduler + state checkpointing (architecture.md:881).
// No iOS implementation in this story — iOS gets this early-return + the TODO.

import { NativeModules, PermissionsAndroid, Platform } from "react-native";

interface WardenProcessingNative {
  start(sessionId: string): Promise<void>;
  updateStage(stage: string): Promise<void>;
  stop(): Promise<void>;
}

const native = NativeModules.WardenProcessing as
  | WardenProcessingNative
  | undefined;

// The sessionId of the pipeline that most recently started the (singleton)
// service. Lives in JS because the JS pipeline is the only entity that can
// stop the service in normal operation; a fresh JS context starts at null,
// which is what makes the launch reconciliation below safe.
let activeOwner: string | null = null;

function warnMissing(action: string): void {
  if (__DEV__) {
    console.warn(
      `[foregroundService] native module WardenProcessing not found; ${action} is a no-op ` +
        "(expected in jest / non-Android / un-prebuilt builds)."
    );
  }
}

/**
 * Request POST_NOTIFICATIONS at runtime on Android 13+ (API 33). Declaring it
 * in the manifest is necessary but not sufficient. If the user denies, the FGS
 * still runs — only the notification's visibility is lost — so we never block
 * the pipeline on the result.
 */
async function ensureNotificationPermission(): Promise<void> {
  if (Platform.OS !== "android") return;
  if (typeof Platform.Version === "number" && Platform.Version < 33) return;
  try {
    const granted = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS
    );
    if (granted !== PermissionsAndroid.RESULTS.GRANTED && __DEV__) {
      console.warn(
        "[foregroundService] POST_NOTIFICATIONS not granted; the foreground " +
          "service runs but its notification will be invisible. Re-grant via " +
          "Android Settings → Notifications."
      );
    }
  } catch (err) {
    if (__DEV__) {
      console.warn("[foregroundService] POST_NOTIFICATIONS request failed", err);
    }
  }
}

/**
 * Start the Android foreground service for `sessionId`. No-op on iOS. Safe to
 * call when the native module is absent (resolves with a __DEV__ warning).
 * Takes ownership of the singleton service: a later start for another session
 * repoints the owner token, and stale stops are then ignored.
 */
export async function startForegroundService(sessionId: string): Promise<void> {
  if (Platform.OS !== "android") return;
  // Fire-and-forget: the FGS itself does not require POST_NOTIFICATIONS (only
  // the notification's visibility does), so the start must not wait on the
  // user answering the permission dialog (AC9 — never block the pipeline).
  void ensureNotificationPermission();
  // Claim ownership before the native call so the caller's finally-stop still
  // reaches the native side even when start() itself rejects mid-flight.
  activeOwner = sessionId;
  if (!native) {
    warnMissing("startForegroundService");
    return;
  }
  await native.start(sessionId);
}

/**
 * Push the current pipeline stage to the running service so its notification
 * text updates. The Kotlin side maps the stage key to French copy. No-op on
 * iOS / missing module. Best-effort: NEVER throws or rejects — the pipeline
 * calls this fire-and-forget, and a failed notification update must never
 * affect processing. `stage` is a ProcessingStage key (e.g. "keyframes");
 * unknown values fall back to "Préparation…" on the native side.
 */
export async function updateForegroundServiceStage(
  stage: string
): Promise<void> {
  if (Platform.OS !== "android") return;
  if (!native) return; // start() already warned about the missing module.
  try {
    await native.updateStage(stage);
  } catch (err) {
    if (__DEV__) {
      console.warn(
        "[foregroundService] updateStage failed (best-effort, ignored)",
        err
      );
    }
  }
}

/**
 * Stop the Android foreground service. No-op on iOS / missing module. NEVER
 * rejects — a native stop failure is logged and swallowed, so the call is
 * always safe in a `finally` (a rejection there would mask the pipeline's
 * real error, or fail a run whose session is already "ready").
 *
 * `owner`: pass the sessionId that was given to startForegroundService. If a
 * newer pipeline has since taken ownership of the singleton service, the
 * stale stop is skipped so it cannot strip the newer run's J2 protection.
 * Omit to force-stop regardless of owner (launch reconciliation).
 */
export async function stopForegroundService(owner?: string): Promise<void> {
  if (Platform.OS !== "android") return;
  if (owner !== undefined && activeOwner !== null && owner !== activeOwner) {
    return; // a newer pipeline owns the service — not ours to stop
  }
  activeOwner = null;
  if (!native) {
    warnMissing("stopForegroundService");
    return;
  }
  try {
    await native.stop();
  } catch (err) {
    if (__DEV__) {
      console.warn(
        "[foregroundService] stop failed (swallowed — a finally-thrown " +
          "rejection would mask the pipeline's real outcome)",
        err
      );
    }
  }
}

/**
 * Clear any orphaned foreground service at JS startup. If a previous JS
 * context died without running its finally-stop (JS crash, dev reload, OS
 * process kill), the sticky "Analyse en cours…" notification would otherwise
 * survive with no owner left to stop it. Called once from App mount, before
 * any pipeline can start; best-effort.
 */
export async function reconcileForegroundServiceAtLaunch(): Promise<void> {
  if (Platform.OS !== "android") return;
  if (!native) return;
  await stopForegroundService(); // no owner argument — force-stop
}
