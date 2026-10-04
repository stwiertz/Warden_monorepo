// Story 1.13 AC5 / AC8 / AC10 — the post-auth Firestore OVERLAY for map configs.
//
// The app always analyses with a config it already has: the Metro-bundled
// `bundledMapConfigs.ts` entries, or an overlay cached by an earlier refresh.
// This module is the only thing that talks to Firestore about configs, and it
// is fire-and-forget: `refreshMapConfigOverlay()` is called once a real user is
// signed in (App.tsx), is never awaited by processing, and NEVER throws. Every
// failure — offline, permission-denied (today's rules, until 1.14/1.15), a
// missing document, a bad upload — is logged once and leaves the bundle/cache
// in charge. There is no first-launch gate any more.
//
// The document is `detection_config/latest`, shaped by
// `contracts/detection-config-envelope.schema.json`:
//   { envelope_version: 1, revision, configs: { <hud>: { config_json, sha256 } } }
//
// 🔴 THE ORDER TRAP. Each config arrives as its exact emitted JSON TEXT, and
// that text becomes the candidate's `rawJson` VERBATIM (see mapConfig.ts). The
// native packer recovers `minimap_identification.maps` order — every map
// rule's texel index — by scanning that text, and Firestore maps do not keep
// key order. A config delivered as a nested Firestore map (e.g. a naive upload
// of the bare file) fails the envelope contract and is rejected, never
// accepted-and-reordered.
//
// Integrity: `sha256` (UTF-8 bytes of `config_json`) is checked here, at write
// time. The synchronous read path in mapConfig.ts re-validates the cached
// envelope and every config against the contract but does not re-hash (that
// would need an async digest on a sync seam); MMKV corruption that survives
// JSON + schema validation is not a realistic failure.
//
// Code review 2026-10-04 (Stephane): D1 — the envelope tolerates HUD keys
// this build does not know; each is dropped as `unknown-hud` and the known
// entries still apply, so adding a HUD never blinds older apps. D2 — an entry
// the native packer would throw on is dropped as `native-invalid`
// (mapConfigNativePreconditions.ts mirrors WardenRulePacker.kt's `require`s).
//
// The MMKV cache lives in
// `mapConfigOverlayCache.ts`, so the synchronous seam can read it without
// importing Firebase.
//
// Reuses the proven parts of the deleted v1 `detectionConfigService.ts`:
// singleflight, memoised cache read, discard-corrupt-cache.

import firestore from "@react-native-firebase/firestore";
import { DetectionConfigEnvelopeSchema, MapConfigSchema } from "@warden/contracts";
import * as Crypto from "expo-crypto";

import { storage } from "../../shared/services/storage";
import { BUNDLED_MAP_CONFIG_REVISION } from "./bundledMapConfigs";
import { nativeConfigProblem } from "./mapConfigNativePreconditions";
import {
  __resetMapConfigOverlayCacheForTests,
  readCachedOverlay,
  writeCachedOverlay,
  type DetectionConfigEnvelope,
} from "./mapConfigOverlayCache";

const OVERLAY_COLLECTION = "detection_config";
const OVERLAY_DOC_ID = "latest";

export type { DetectionConfigEnvelope };

/**
 * AC8 — MMKV keys of the deleted v1 apparatus (Story 7.4's `detection.config`
 * cache and the first-launch gate flag). Deleted once at module init — App.tsx
 * imports this module, so that is app start. Idempotent.
 */
export const LEGACY_DETECTION_STORAGE_KEYS = [
  "detection.config",
  "detection.offlineFirstLaunchBlocked",
] as const;
for (const key of LEGACY_DETECTION_STORAGE_KEYS) storage.delete(key);

export type OverlayRefreshReason =
  /** A newer envelope with at least one valid entry was cached. */
  | "updated"
  /** Firestore rules deny the read (expected until Stories 1.14 + 1.15). */
  | "permission-denied"
  /** Offline / Firestore unreachable. */
  | "unavailable"
  /** `detection_config/latest` does not exist. */
  | "not-found"
  /** Any other Firestore failure (logged with its code), or an error with no code (a bug, not the network). */
  | "error"
  /** The document is not a valid envelope (v1 doc, nested-object config, unknown `envelope_version`, …). */
  | "malformed-envelope"
  /** The envelope was newer but every entry failed its checks. */
  | "malformed-entry"
  /** `revision` is not above the cached overlay or the shipped bundle. */
  | "not-newer";

export type OverlayEntryProblem =
  /**
   * A HUD key this app's contract does not know (a HUD added after this build).
   * Dropped on its own; the known entries still apply (code-review D1).
   */
  | "unknown-hud"
  /** Schema-valid, but the native packer would throw on it (code-review D2). */
  | "native-invalid"
  | "sha256-mismatch"
  | "not-json"
  | "schema-invalid"
  | "hud-mismatch";

export interface DroppedOverlayEntry {
  hudVersion: string;
  problem: OverlayEntryProblem;
  detail: string;
}

export interface OverlayRefreshResult {
  reason: OverlayRefreshReason;
  /** The remote envelope's revision, when one was read. */
  revision?: number;
  /** Firestore error code, when the failure came from Firestore. */
  code?: string;
  /**
   * For `malformed-envelope` only: an `envelope_version` this app does not know
   * (a future envelope shape) vs any other invalid document.
   */
  envelopeProblem?: "unknown-envelope-version" | "invalid";
  /** Entries dropped from an otherwise-usable envelope (per-HUD fallback). */
  droppedEntries: DroppedOverlayEntry[];
}

// ---------------------------------------------------------------------------
// Refresh (network) — post-auth, fire-and-forget, never throws
// ---------------------------------------------------------------------------

function firestoreCode(err: unknown): string | undefined {
  const code = (err as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : undefined;
}

function reasonForFirestoreError(code: string | undefined): OverlayRefreshReason {
  switch (code?.replace(/^firestore\//, "")) {
    case "permission-denied":
    case "unauthenticated":
      return "permission-denied";
    case "not-found":
      return "not-found";
    // No code at all is not the network (RNFB tags every native Firestore
    // failure with a `firestore/*` code): it is a bug, and must not be logged
    // as "offline" (Story 1.13 code review).
    case "unavailable":
    case "deadline-exceeded":
      return "unavailable";
    default:
      return "error";
  }
}

/**
 * The HUD versions this build's contract knows (the map-config `hud_version`
 * enum). The envelope tolerates other keys (code-review D1) so that adding a
 * HUD does not make older apps reject the whole document; they are dropped here.
 */
export const KNOWN_HUD_VERSIONS: readonly string[] = MapConfigSchema.shape.hud_version.options;

export function isKnownHud(hud: string): boolean {
  return KNOWN_HUD_VERSIONS.includes(hud);
}

async function checkEntry(
  hudVersion: string,
  entry: { config_json: string; sha256: string }
): Promise<DroppedOverlayEntry | null> {
  const digest = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    entry.config_json
  );
  if (digest.toLowerCase() !== entry.sha256) {
    return { hudVersion, problem: "sha256-mismatch", detail: `expected ${entry.sha256}, got ${digest}` };
  }
  let config: unknown;
  try {
    config = JSON.parse(entry.config_json);
  } catch (err) {
    return { hudVersion, problem: "not-json", detail: err instanceof Error ? err.message : String(err) };
  }
  const parsed = MapConfigSchema.safeParse(config);
  if (!parsed.success) {
    const detail = parsed.error.issues
      .slice(0, 3)
      .map((i) => `${i.path.join(".") || "<root>"}: ${i.message}`)
      .join("; ");
    return { hudVersion, problem: "schema-invalid", detail };
  }
  // Both sides are constrained to the schema's `hud_version` enum, which is
  // already in normalised form, so an exact compare is the normalised compare.
  if (parsed.data.hud_version !== hudVersion) {
    return {
      hudVersion,
      problem: "hud-mismatch",
      detail: `entry key ${hudVersion} carries hud_version ${parsed.data.hud_version}`,
    };
  }
  const nativeProblem = nativeConfigProblem(entry.config_json, parsed.data);
  if (nativeProblem) {
    return { hudVersion, problem: "native-invalid", detail: nativeProblem };
  }
  return null;
}

async function doRefresh(): Promise<OverlayRefreshResult> {
  let data: unknown;
  try {
    const snap = await firestore().collection(OVERLAY_COLLECTION).doc(OVERLAY_DOC_ID).get();
    if (!snap.exists()) {
      console.warn("[map-config] overlay refresh: detection_config/latest does not exist; using bundled/cached config");
      return { reason: "not-found", droppedEntries: [] };
    }
    data = snap.data();
  } catch (err) {
    const code = firestoreCode(err);
    const reason = reasonForFirestoreError(code);
    console.warn(
      `[map-config] overlay refresh failed (${reason}${code ? `, code=${code}` : ""}); using bundled/cached config`,
      err instanceof Error ? err.message : err
    );
    return { reason, code, droppedEntries: [] };
  }

  const parsed = DetectionConfigEnvelopeSchema.safeParse(data);
  const configs = parsed.success ? parsed.data.configs : undefined;
  if (!parsed.success || !configs || Object.keys(configs).length === 0) {
    const detail = parsed.success
      ? "configs is empty"
      : parsed.error.issues
          .slice(0, 3)
          .map((i) => `${i.path.join(".") || "<root>"}: ${i.message}`)
          .join("; ");
    const version = (data as { envelope_version?: unknown } | null | undefined)?.envelope_version;
    const envelopeProblem =
      typeof version === "number" && version !== 1 ? "unknown-envelope-version" : "invalid";
    console.warn(
      `[map-config] overlay refresh: malformed envelope (${envelopeProblem}: ${detail}); using bundled/cached config`
    );
    return { reason: "malformed-envelope", envelopeProblem, droppedEntries: [] };
  }

  const { revision } = parsed.data;
  const floor = Math.max(readCachedOverlay()?.revision ?? 0, BUNDLED_MAP_CONFIG_REVISION);
  if (revision <= floor) {
    console.warn(`[map-config] overlay refresh: revision ${revision} is not newer than ${floor}; nothing to do`);
    return { reason: "not-newer", revision, droppedEntries: [] };
  }

  const surviving: DetectionConfigEnvelope["configs"] = {};
  const droppedEntries: DroppedOverlayEntry[] = [];
  for (const [hud, entry] of Object.entries(configs)) {
    if (!entry) continue;
    if (!isKnownHud(hud)) {
      droppedEntries.push({
        hudVersion: hud,
        problem: "unknown-hud",
        detail: `this build knows only ${KNOWN_HUD_VERSIONS.join(", ")}`,
      });
      continue;
    }
    const dropped = await checkEntry(hud, entry);
    if (dropped) droppedEntries.push(dropped);
    else surviving[hud as keyof typeof surviving] = entry;
  }
  if (droppedEntries.length > 0) {
    console.warn(
      `[map-config] overlay revision ${revision}: dropped ${droppedEntries
        .map((d) => `${d.hudVersion} (${d.problem}: ${d.detail})`)
        .join(", ")}`
    );
  }
  if (Object.keys(surviving).length === 0) {
    return { reason: "malformed-entry", revision, droppedEntries };
  }

  // Re-check the floor: a concurrent write cannot happen (singleflight), but
  // the cache can have been discarded/replaced by the read path meanwhile.
  const latestFloor = Math.max(readCachedOverlay()?.revision ?? 0, BUNDLED_MAP_CONFIG_REVISION);
  if (revision <= latestFloor) {
    return { reason: "not-newer", revision, droppedEntries };
  }
  writeCachedOverlay({ envelope_version: parsed.data.envelope_version, revision, configs: surviving });
  console.log(
    `[map-config] overlay revision ${revision} cached (${Object.keys(surviving).join(", ")}); applies from the next session`
  );
  return { reason: "updated", revision, droppedEntries };
}

let inflight: Promise<OverlayRefreshResult> | null = null;

/**
 * Read `detection_config/latest`, validate it, and cache it if newer.
 * Singleflighted; never throws; never awaited by processing.
 */
export function refreshMapConfigOverlay(): Promise<OverlayRefreshResult> {
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      return await doRefresh();
    } catch (err) {
      // Defensive: everything above already maps its failures. A bug here
      // must still not surface to the user or reject a fire-and-forget call.
      console.warn("[map-config] overlay refresh crashed; using bundled/cached config", err);
      return { reason: "error" as const, droppedEntries: [] };
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}

/** Test seam: forget the in-flight promise, the memo and the stored overlay. */
export function __resetMapConfigOverlayForTests(): void {
  inflight = null;
  __resetMapConfigOverlayCacheForTests();
}
