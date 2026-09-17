// Story 12.4c (AC6 / AC9) — the TypeScript port of Tool 12's `scoring.py`.
//
// Fire bits in, three classifier verdicts out. PURE: no native calls, no I/O, no
// state. The native side (`WardenSessionAnalyzer`) evaluates the rules and hands
// back one hex row per keyframe plus the rule index; everything above the bits
// lives here, in the layer that owns the product semantics and has a test
// framework (AC0b).
//
// 🔴 THE THREE CLASSIFIERS USE THREE DIFFERENT FORMULAS. This is `scoring.py`'s
// own headline warning, and it exists because the sprint-change proposal got it
// wrong ("Tool 9 sums raw weighted" — true of the map-ID classifier ONLY).
// Implementing one formula everywhere "silently breaks two of the three accuracy
// numbers":
//
//   HUD-version   fires / n_hud            normalized, unweighted        thr 0.5
//   in_match      fires / n_im             normalized, unweighted, then
//                                          HARD-BINARY (never "unknown")  thr 0.5
//   map-ID        sum(effective_weight     RAW, UNNORMALIZED              thr =
//                     x fired)                                  identification_threshold
//
// 🔴 A DEGENERACY THAT IS REPRODUCED, NOT FIXED. All 134 shipped rules carry
// `weight = 1.0` / `weight_override = null`, so the map-ID "weighted aggregate"
// reduces to a plain COUNT of fired zones. Against an unnormalized sum with
// threshold 0.6, any map with >= 1 fired zone clears it — so map-ID is
// effectively `argmax(fired_count)` and the threshold is near-inert.
// `scoring.py` reproduces this as-is and says "that is 9.16's call". It is not
// this story's call either: port the behaviour, log the observation, do not
// repair it here.
//
// WHAT WAS DROPPED FROM THE PYTHON, AND WHY: `score_from_fires` takes `folder`
// and `hud_dir`, which gate in_match/map commitment on the LABELED CORPUS's
// ground-truth directories. On the video path Tool 12 itself passes both as
// `None` — every frame is same-HUD by construction and every frame gets a map
// score — so the gate is corpus-only and has no meaning on a device. Its
// absence is stated here rather than silently carried as dead parameters.

/** `hud_version` | `in_match` | `map` — selects which formula a fire feeds. */
export type RuleKind = "hud_version" | "in_match" | "map";

/**
 * One texel of the packed rules -> the zone it came from.
 *
 * 🔴 AGGREGATE BY `refs`, NEVER BY POSITIONAL ARITHMETIC. The canonical texel
 * order is hud_version zones, then in_match, then map zones in config order, and
 * assuming that shape instead of reading it is the transpose 12.2 lost a full
 * parity run to — it "produced plausible-looking detections from garbage" and
 * passed both the LUT byte-check and the render-target self-test.
 */
export interface RuleRef {
  texel: number;
  /** The normalized HUD version, `"in_match"`, or a map slug. */
  owningClass: string;
  zoneId: string;
  kind: RuleKind;
  effectiveWeight: number;
}

/** Tool 9's game-state defaults (`roi_detection_tester.py`). */
export const HUD_THRESHOLD = 0.5;
export const IN_MATCH_THRESHOLD = 0.5;

/** The literal every classifier uses for "no commitment". */
export const UNKNOWN = "unknown";

export interface ClassifierShape {
  hudVersion: string;
  nHudZones: number;
  nInMatchZones: number;
  mapZoneCounts: Record<string, number>;
  identificationThreshold: number;
}

export interface FrameScores {
  predHud: string;
  hudConf: number;
  /** `"in_match"` | `"not_in_match"`, or `"unknown"` ONLY when n_im == 0. */
  predInMatch: string;
  inMatchConf: number;
  predMap: string;
  mapConf: number;
  /** Map slug -> RAW weighted aggregate, in config order. */
  mapScores: Record<string, number>;
}

/**
 * Hex fire bits -> booleans. 4 bits per char, **LSB first**.
 *
 * The packing is `WardenEngineBench.bitsToHex`'s, which `pc_reference.py` and
 * `video_oracle.py` already speak — so a device dump, the PC oracle and this
 * function are one format and a parity comparison is a diff rather than a
 * translation. LSB-first is not a convention worth changing for aesthetics:
 * three producers and two consumers agree on it.
 */
export function hexToFires(hex: string, nRules: number): boolean[] {
  const expectedChars = Math.ceil(nRules / 4);
  if (hex.length !== expectedChars) {
    throw new Error(
      `fire bits are ${hex.length} hex chars but ${nRules} rules need ` +
        `${expectedChars}. A truncated row would silently clear the trailing ` +
        "rules, which reads as 'those zones never fire'."
    );
  }
  const out: boolean[] = new Array(nRules);
  for (let i = 0; i < nRules; i++) {
    const nibble = Number.parseInt(hex[i >> 2], 16);
    if (Number.isNaN(nibble)) {
      throw new Error(`fire bits contain a non-hex character at ${i >> 2}`);
    }
    out[i] = (nibble & (1 << (i & 3))) !== 0;
  }
  return out;
}

/**
 * Tool 9's `_argmax_with_threshold`, ported verbatim (it is "frozen for Story
 * 9.13's contract pin — keep verbatim").
 *
 * Argmax gated by `threshold`. Tie-break: more zones wins (more evidence), then
 * the natural `orderedClasses` order. Below threshold -> `"unknown"`. A score of
 * exactly 0 is ALWAYS `"unknown"` even when the threshold is also 0 — no zone
 * fired, so there is nothing to predict from. Ties use a relative/absolute
 * closeness test rather than exact float equality so the tie-break is
 * deterministic across float environments.
 */
export function argmaxWithThreshold(
  scores: Record<string, number>,
  opts: {
    threshold: number;
    orderedClasses: readonly string[];
    zoneCounts: Record<string, number>;
  }
): { label: string; score: number } {
  const entries = Object.entries(scores);
  if (entries.length === 0) return { label: UNKNOWN, score: 0 };
  let maxScore = -Infinity;
  for (const [, value] of entries) if (value > maxScore) maxScore = value;
  if (maxScore <= 0) return { label: UNKNOWN, score: maxScore };
  if (maxScore < opts.threshold) return { label: UNKNOWN, score: maxScore };

  // math.isclose(rel_tol=1e-9, abs_tol=1e-12).
  const tied = entries
    .filter(([, value]) => isClose(value, maxScore))
    .map(([label]) => label);
  if (tied.length === 1) return { label: tied[0], score: maxScore };

  // 🔴 ONE DELIBERATE DIVERGENCE FROM THE PYTHON, and it is a divergence from a
  // CRASH. Python does `-list(ordered_classes).index(c)`, which raises
  // ValueError for a class outside the vocabulary — a config carrying a map slug
  // that `labels.py` does not know would kill Tool 9. On a device that must not
  // be fatal (REL-006: graceful degradation), and a bare `indexOf` returning -1
  // would make an UNKNOWN slug beat every known one on a tie. Unknown slugs
  // therefore sort LAST, deterministically.
  const orderKey = (label: string): number => {
    const idx = opts.orderedClasses.indexOf(label);
    return -(idx < 0 ? opts.orderedClasses.length : idx);
  };
  let best = tied[0];
  let bestKey: [number, number] = [opts.zoneCounts[best] ?? 0, orderKey(best)];
  for (const candidate of tied.slice(1)) {
    const key: [number, number] = [
      opts.zoneCounts[candidate] ?? 0,
      orderKey(candidate),
    ];
    if (key[0] > bestKey[0] || (key[0] === bestKey[0] && key[1] > bestKey[1])) {
      best = candidate;
      bestKey = key;
    }
  }
  return { label: best, score: maxScore };
}

function isClose(a: number, b: number): boolean {
  return Math.abs(a - b) <= Math.max(1e-9 * Math.max(Math.abs(a), Math.abs(b)), 1e-12);
}

/**
 * The 14 canonical map labels, in Tool 9's order.
 *
 * 🔴 PINNED TO `apps/tooling/tools/common/labels.py` AND MECHANICALLY ASSERTED —
 * `mapIdentifier.test.ts` reads that Python off disk and compares, the same
 * cross-language contract-guard pattern the `BENCH_MODES` lockstep uses. The
 * ORDER is load-bearing, not decorative: it is `_argmax_with_threshold`'s
 * secondary tie-break, so a re-ordering here changes which map a tie resolves to
 * while every individual score stays correct.
 *
 * `bastion` has no corpus and no config entry yet and is deliberately present:
 * the list is the label vocabulary, not the configured maps.
 */
export const MAP_LABELS: readonly string[] = [
  "artefact",
  "atlantis",
  "bastion",
  "ceres",
  "coliseum",
  "engine",
  "helios",
  "horizon",
  "lunar_outpost",
  "outlaw",
  "polaris",
  "silva",
  "the_cliff",
  "the_rock",
];

/**
 * One keyframe's fire bits -> the three classifier verdicts.
 *
 * `fires` may be the hex row from the native side or an already-decoded boolean
 * array; the hex form is what crosses the bridge and what the fixtures hold.
 */
export function scoreFromFires(
  fires: string | readonly boolean[],
  refs: readonly RuleRef[],
  cfg: ClassifierShape,
  opts: { hudThreshold?: number; inMatchThreshold?: number } = {}
): FrameScores {
  const bits =
    typeof fires === "string" ? hexToFires(fires, refs.length) : fires;
  if (bits.length !== refs.length) {
    throw new Error(
      `got ${bits.length} fires for ${refs.length} rules — texel order would be ` +
        "misaligned"
    );
  }
  const hudThreshold = opts.hudThreshold ?? HUD_THRESHOLD;
  const inMatchThreshold = opts.inMatchThreshold ?? IN_MATCH_THRESHOLD;

  // --- HUD-version: normalized, unweighted. Evaluated on EVERY frame.
  const hudScores: Record<string, number> = {};
  if (cfg.nHudZones > 0) {
    let hudFires = 0;
    for (let i = 0; i < refs.length; i++) {
      if (bits[i] && refs[i].kind === "hud_version") hudFires++;
    }
    hudScores[cfg.hudVersion] = hudFires / cfg.nHudZones;
  }
  const hud = argmaxWithThreshold(hudScores, {
    threshold: hudThreshold,
    orderedClasses: [cfg.hudVersion],
    zoneCounts: { [cfg.hudVersion]: cfg.nHudZones },
  });

  // --- in_match: normalized, unweighted, then HARD-BINARY.
  //
  // 🔴 NEVER "unknown" unless there are no zones at all. This is the classifier
  // that drives the phase machine, and it is why "doubt" has no upstream unknown
  // to inherit — doubt is introduced downstream, in gameDetector.ts.
  let predInMatch: string;
  let inMatchConf: number;
  if (cfg.nInMatchZones === 0) {
    predInMatch = UNKNOWN;
    inMatchConf = 0;
  } else {
    let imFires = 0;
    for (let i = 0; i < refs.length; i++) {
      if (bits[i] && refs[i].kind === "in_match") imFires++;
    }
    const ratio = imFires / cfg.nInMatchZones;
    inMatchConf = ratio;
    predInMatch =
      ratio > 0 && ratio >= inMatchThreshold ? "in_match" : "not_in_match";
  }

  // --- map-ID: RAW weighted aggregate, UNNORMALIZED.
  const agg: Record<string, number> = {};
  for (let i = 0; i < refs.length; i++) {
    const ref = refs[i];
    if (ref.kind !== "map") continue;
    agg[ref.owningClass] =
      (agg[ref.owningClass] ?? 0) + (bits[i] ? ref.effectiveWeight : 0);
  }
  const mapScores: Record<string, number> = {};
  // Config order, and only maps that HAVE zones: a map with an empty zone list
  // is not-yet-fingerprinted, and scoring it at 0 would make it a tie candidate.
  for (const [slug, count] of Object.entries(cfg.mapZoneCounts)) {
    if (count === 0) continue;
    mapScores[slug] = agg[slug] ?? 0;
  }
  const map = argmaxWithThreshold(mapScores, {
    threshold: cfg.identificationThreshold,
    orderedClasses: MAP_LABELS,
    zoneCounts: cfg.mapZoneCounts,
  });

  return {
    predHud: hud.label,
    hudConf: hud.score,
    predInMatch,
    inMatchConf,
    predMap: map.label,
    mapConf: map.score,
    mapScores,
  };
}
