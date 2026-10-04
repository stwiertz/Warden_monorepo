// Story 1.13 code review, decision D2 (Stephane, 2026-10-04): the NATIVE
// packer's preconditions, mirrored in TS so that a REMOTE config the native
// side would reject is dropped when it is received (and when it is read back
// from the cache), not discovered by every session failing on it.
//
// MapConfigSchema checks shape. The native packer
// (`apps/mobile/plugins/kotlin/WardenRulePacker.kt`, `WardenSessionAnalyzer.kt`)
// then throws on four things the schema cannot see:
//
//   1. `orderedMapNames` (WardenRulePacker.kt:267-316) recovers map order by
//      scanning the raw TEXT. It `require`s a `"minimap_identification"`
//      literal (:268-269), a `"maps"` literal after it (:270-271), exactly one
//      such literal after it (:272-278), an `{` after it (:279), and a
//      terminated object (:315). It then takes each direct-child key verbatim:
//      no unescaping, so `"the_cliff"` arrives as `the_cliff`.
//   2. `iterZones` (:241-246) looks each scanned name up with
//      `maps.getJSONObject(name).getJSONArray("zones")`. A scanned name that is
//      not a key of the parsed `maps` (an escaped key) throws. A slug listed
//      twice in the text appears twice in the scan while the parsed object
//      (last value wins, in both org.json and JSON.parse) holds it once, so the
//      rule list drifts from the TS side's. The check below is therefore "the
//      scanned names equal `Object.keys(maps)`, same order, no duplicates".
//   3. `packRules` (:335-338): at most MAX_RULES = 150 (:21) rules in total,
//      counting HUD, in-match and map zones.
//   4. `packRules` (:350-361): each zone, clamped by `clampRect` (:199-205) to
//      the frame, covers at most MAX_RECT_TEXELS = 4096 (:30) pixels. The frame
//      is the config's `reference_resolution` (WardenSessionAnalyzer.kt:74-81).
//
// No Kotlin change: this file follows the native code. If a `require` is added
// to or changed in WardenRulePacker.kt, change this file with it.

import type { MapConfig } from "./mapConfig";

/** WardenRulePacker.kt:21 */
export const NATIVE_MAX_RULES = 150;
/** WardenRulePacker.kt:30 */
export const NATIVE_MAX_RECT_TEXELS = 4096;

/** WardenRulePacker.kt:267-316, `orderedMapNames`, ported 1:1. Throws as the Kotlin does. */
export function nativeOrderedMapNames(rawJson: string): string[] {
  const section = rawJson.indexOf('"minimap_identification"');
  if (section < 0) throw new Error("config has no minimap_identification");
  const anchor = rawJson.indexOf('"maps"', section);
  if (anchor < 0) throw new Error("config has no minimap_identification.maps");
  if (rawJson.indexOf('"maps"', anchor + 1) >= 0) {
    throw new Error(
      'the literal "maps" appears more than once after "minimap_identification"'
    );
  }
  const open = rawJson.indexOf("{", anchor);
  if (open < 0) throw new Error("malformed maps object");
  const names: string[] = [];
  let depth = 0;
  let inString = false;
  let escaped = false;
  let pendingKeyStart = -1;
  for (let i = open; i < rawJson.length; i++) {
    const c = rawJson[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (c === "\\") escaped = true;
      else if (c === '"') {
        inString = false;
        if (depth === 1 && pendingKeyStart >= 0) {
          let j = i + 1;
          // Kotlin Char.isWhitespace(); JSON only allows these four.
          while (j < rawJson.length && /\s/.test(rawJson[j])) j++;
          if (j < rawJson.length && rawJson[j] === ":") {
            names.push(rawJson.substring(pendingKeyStart, i));
          }
        }
        pendingKeyStart = -1;
      }
    } else if (c === '"') {
      inString = true;
      escaped = false;
      pendingKeyStart = i + 1;
    } else if (c === "{") {
      depth++;
    } else if (c === "}") {
      depth--;
      if (depth === 0) return names;
    }
  }
  throw new Error("unterminated maps object in config");
}

/** WardenRulePacker.kt:199-205, `clampRect`: [x, y, w, h] fully inside the frame. */
function clampRect(
  x: number,
  y: number,
  w: number,
  h: number,
  frameW: number,
  frameH: number
): [number, number, number, number] {
  const xStart = Math.max(0, Math.min(x, frameW));
  const yStart = Math.max(0, Math.min(y, frameH));
  const xEnd = Math.max(xStart, Math.min(x + w, frameW));
  const yEnd = Math.max(yStart, Math.min(y + h, frameH));
  return [xStart, yStart, xEnd - xStart, yEnd - yStart];
}

/**
 * `null` when the native packer would accept this (schema-valid) config,
 * otherwise the reason it would throw.
 */
export function nativeConfigProblem(rawJson: string, config: MapConfig): string | null {
  // 1 + 2 — the text scan, and its agreement with the parsed object.
  let scanned: string[];
  try {
    scanned = nativeOrderedMapNames(rawJson);
  } catch (err) {
    return `map-order scan: ${err instanceof Error ? err.message : String(err)}`;
  }
  const parsedNames = Object.keys(config.minimap_identification.maps);
  const dup = scanned.find((n, i) => scanned.indexOf(n) !== i);
  if (dup !== undefined) return `map slug "${dup}" appears more than once in the text`;
  const unknown = scanned.find((n) => !Object.prototype.hasOwnProperty.call(config.minimap_identification.maps, n));
  if (unknown !== undefined) {
    return `map key ${JSON.stringify(unknown)} as written in the text is not a key of the parsed maps (escaped key?)`;
  }
  if (scanned.length !== parsedNames.length || scanned.some((n, i) => n !== parsedNames[i])) {
    return "map order scanned from the text differs from the parsed maps";
  }

  // 3 — the rule count.
  const zones = [
    ...config.hud_version_detection,
    ...config.in_match_detection,
    ...scanned.flatMap((name) => config.minimap_identification.maps[name]?.zones ?? []),
  ];
  if (zones.length > NATIVE_MAX_RULES) {
    return `config carries ${zones.length} rules but the native rules texture is ${NATIVE_MAX_RULES} wide`;
  }

  // 4 — the per-zone texel cap, after clamping to reference_resolution.
  const { width: frameW, height: frameH } = config.reference_resolution;
  for (const z of zones) {
    const r = clampRect(z.x, z.y, z.width, z.height, frameW, frameH);
    const area = r[2] * r[3];
    if (area > NATIVE_MAX_RECT_TEXELS) {
      return `zone ${z.id} clamps to ${r[2]}x${r[3]} = ${area} px, above MAX_RECT_TEXELS=${NATIVE_MAX_RECT_TEXELS}`;
    }
  }
  return null;
}
