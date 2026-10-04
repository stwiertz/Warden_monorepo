// Story 1.13 AC1 — the bundled map-config REGISTRY (the per-HUD "manifest").
//
// One entry per HUD version, each a STATIC import of the emitter's
// `map_config.<hud_version>.json` copied into `assets/detection/`. This module
// IS the manifest: Metro resolves only static `import`/`require`, so a JSON
// manifest naming file paths could not be resolved at runtime (kickoff D1).
// Not to be confused with the tooling zone-fragment
// `apps/tooling/output/zones/v2/manifest.json` (an emitter input, unrelated).
//
// The bundle is the floor: it exists on first launch, offline, before any
// Firestore call, and processing never waits for anything else. The post-auth
// Firestore overlay (`mapConfigOverlay.ts`) can only REPLACE an entry here when
// its envelope `revision` is strictly greater than BUNDLED_MAP_CONFIG_REVISION.
//
// 🔴 BUMP BUNDLED_MAP_CONFIG_REVISION BY HAND WHENEVER ANY BUNDLED CONFIG FILE
// CHANGES. Otherwise an older overlay already cached on a device (same or lower
// revision number, older zones) would keep overriding the newer bundle an app
// update just shipped. Operator rule for uploads (Story 1.16): next overlay
// revision = max(current Firestore revision, shipped bundled revision) + 1.
//
// Adding a HUD: copy the emitter output to `assets/detection/map_config.<hud>.json`,
// add one line below, bump the revision. The key must equal the file's
// normalised `hud_version` — `listMapConfigCandidates()` throws otherwise.

import bundledV2 from "../../../assets/detection/map_config.v2.json";

/** HUD version -> the parsed bundled config module (validated at the seam). */
export const BUNDLED_MAP_CONFIGS: Readonly<Record<string, unknown>> = {
  v2: bundledV2,
};

/** The HUD a session runs with until real HUD selection exists (deferred, D4). */
export const DEFAULT_HUD_VERSION = "v2";

/** Revision of the bundled set. Integer; bump by hand when a bundled file changes. */
export const BUNDLED_MAP_CONFIG_REVISION = 1;
