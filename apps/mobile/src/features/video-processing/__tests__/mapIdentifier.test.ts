// Story 12.4c — per-span map identification, and the cross-language label pin.
//
// Story 7.5's suite tested `createMapIdentifier` (DCT pHash + Hamming against
// `DetectionConfig.maps`). That path is gone; see mapIdentifier.ts's header.

import fs from "fs";
import path from "path";

import { aggregateSpanScores, identifySpanMap, MAP_LABELS } from "../mapIdentifier";

describe("aggregateSpanScores", () => {
  const perFrame = [
    { artefact: 3, atlantis: 0 },
    { artefact: 4, atlantis: 1 },
    { artefact: 0, atlantis: 5 },
    { artefact: 2, atlantis: 0 },
  ];

  it("sums the per-frame aggregates over the span's frames only", () => {
    expect(aggregateSpanScores(perFrame, 1, 2)).toEqual({
      artefact: 4,
      atlantis: 6,
    });
  });

  it("includes both endpoints", () => {
    expect(aggregateSpanScores(perFrame, 0, 0)).toEqual({ artefact: 3, atlantis: 0 });
    expect(aggregateSpanScores(perFrame, 0, 3).artefact).toBe(9);
  });

  it("survives a span that runs past the end of the frame list", () => {
    // A span is cut from the same list it aggregates over, so this cannot
    // happen today — but silently reading `undefined.entries` if it ever did
    // would crash a 73-minute run at the last segment.
    expect(aggregateSpanScores(perFrame, 3, 99)).toEqual({ artefact: 2, atlantis: 0 });
  });
});

describe("identifySpanMap", () => {
  const cfg = { identificationThreshold: 0.6 };

  it("picks the highest aggregate", () => {
    expect(identifySpanMap({ artefact: 4, atlantis: 17 }, cfg)).toEqual({
      mapName: "atlantis",
      confidence: 17,
      scores: { artefact: 4, atlantis: 17 },
    });
  });

  it("returns unknown below the identification threshold", () => {
    // mobile-AUTO-SLICE-003: below the recognition threshold the segment is
    // `unknown` — spelled `null` on this surface — and navigation stays
    // available. NOT an error, and NOT the nearest class (E4).
    const id = identifySpanMap({ artefact: 0.4 }, cfg);
    expect(id.mapName).toBeNull();
    expect(id.confidence).toBe(0.4);
  });

  it("returns unknown when nothing fired at all, whatever the threshold", () => {
    expect(identifySpanMap({ artefact: 0, atlantis: 0 }, cfg).mapName).toBeNull();
    expect(
      identifySpanMap({ artefact: 0 }, { identificationThreshold: 0 }).mapName
    ).toBeNull();
  });

  it("returns unknown for an empty aggregate", () => {
    expect(identifySpanMap({}, cfg).mapName).toBeNull();
  });

  it("breaks a tie by CONFIG order — the first key wins", () => {
    // Tool 12's `_run_video` uses Python's `max()`, which returns the first
    // maximal key in dict (config) order. This is deliberately a DIFFERENT
    // tie-break from the per-frame classifier's (zone count, then MAP_LABELS
    // order) — reproducing one of them twice would change the other's answers.
    expect(identifySpanMap({ the_rock: 8, artefact: 8 }, cfg).mapName).toBe(
      "the_rock"
    );
  });
});

describe("MAP_LABELS — the cross-language pin", () => {
  // The same pattern the BENCH_MODES lockstep uses: jest cannot run Python, but
  // it can hold the two sides of a contract together. The ORDER is load-bearing
  // (it is `_argmax_with_threshold`'s secondary tie-break), so a re-ordering in
  // either language must fail here rather than quietly relabel a tied segment.
  const labelsPy = path.join(
    __dirname,
    "..",
    "..",
    "..",
    "..",
    "..",
    "tooling",
    "tools",
    "common",
    "labels.py"
  );

  it("matches tools/common/labels.py exactly, including order", () => {
    const source = fs.readFileSync(labelsPy, "utf8");
    const block = source.match(/MAP_LABELS\s*=\s*\[([\s\S]*?)\]/);
    expect(block).not.toBeNull();
    const fromPython = Array.from(block![1].matchAll(/"([a-z0-9_]+)"/g)).map(
      (m) => m[1]
    );
    expect(fromPython).toHaveLength(14);
    expect(MAP_LABELS).toEqual(fromPython);
  });

  it("includes bastion, which has no config entry yet", () => {
    // The list is the label VOCABULARY, not the configured maps: the shipped
    // v2 config carries 13 maps. Dropping bastion here would shift every later
    // label's index and change tie-breaks.
    expect(MAP_LABELS).toContain("bastion");
  });
});
