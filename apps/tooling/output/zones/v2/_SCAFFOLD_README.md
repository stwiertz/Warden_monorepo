# Story 9.9b — v2 zone-population campaign starter

**Status:** scaffolded by the dev-story pre-flight (2026-05-17). The agent-doable surface
is done; everything below this line is the **manual human campaign** (interactive Tk +
video calibration + visual iteration). Story stays `ready-for-dev` until the human loop runs.

## Verified pre-flight facts (AC1 — all deps `done` on `main`)

| Dep | Merge SHA |
|---|---|
| 9.9c schema-unification | `9b9d4af` |
| 9.11 retire-legacy-tooling | `aca0906` |
| 9.12 unified-zone-picker | `54724ed` (postmerge `546e467`) |
| 9.13 video-detection-tester | `0bc66c6` (postmerge `68c6ff7`) |
| 9.14 roi-detection-tester-refit | `2e0bf24` (feat `3704d88`) |

## AC2 — operative interpretation (Stephane, 2026-05-17)

The raw frame-count floors (`score ≥ 200`, `transition ≥ 50`, `≥10 maps @ ≥100`) are **not**
the gate. Post-9.14 the game-state classifier is **binary `in_match`**, so `lobby+score+transition`
pool into one negative class (296+41+44 = **381** neg vs ~2.6k pos — ample). The real gate is
**estimate certitude + zero train/test overlap**, which bites per-map:

| Cohort | Clean non-overlapping held-out feasible? |
|---|---|
| 8 maps: artefact 432, atlantis 337, helios 317, engine 220, horizon 187, silva 165, the_cliff 156, outlaw 141 | ✅ in-scope this campaign |
| 5 maps: the_rock 98, lunar_outpost 93, ceres 85, polaris 75, coliseum 61 | ❌ backfill via Story 9.5/Tool 6 OR document small-sample variance per AC6 |
| binary `in_match` (pooled 381 / ~2.6k) | ✅ no per-subclass concern |

> A formal AC2 text edit is a `/bmad-correct-course`, not a dev-story change. This file +
> the story Change Log record the operative interpretation only.

## The 4-fragment contract (verified against emitter + schema on `main`)

`apps/tooling/output/zones/v2/` must contain exactly:
- `manifest.json` — human-authored. Required keys: `hud_version` (enum, `"v2"`),
  `reference_resolution` (`{width,height}`), `score_screen_duration_ms` (integer ≥ 0).
  Fill `manifest.template.json` → rename to `manifest.json`. The `score_screen_duration_ms`
  sentinel is intentionally a string so it CANNOT silently pass the AC3 dry-run.
- `hud_version_detection.json` — `zone_picker` HUD-version mode output (JSON array of Zone).
- `in_match_detection.json` — `zone_picker` in-match mode output.
- `minimap_identification.json` — `zone_picker` per-map mode output (merged across maps).

## Runbook (commands verified to exist on `main`)

```bash
cd apps/tooling

# AC3 — score-screen calibration: open >=5 EVA captures, median falling->rising edge ms.
#        (No .mp4 in repo: apps/tooling/source/ is absent — supply captures.)

# AC3 dry-run (manifest alone, 3 empty fragments) — must exit 0:
uv run python tools/map_config_emitter.py --zones-dir output/zones/v2

# AC4 — zone_picker (interactive Tk), 3 modes -> the 3 fragment files:
uv run python -m tools.zone_picker            # see --help for mode flags

# AC5 — emit + validate after every pass:
uv run python tools/map_config_emitter.py --zones-dir output/zones/v2

# AC6 — measure (held-out per AC6: last 20 frames/map by filename sort, >100-frame maps):
uv run python tools/roi_detection_tester.py --config output/map_configs/map_config.v2.json \
    --labeled output/labeled --output output/roi_detection_tests
# Floors: HUD-version >=99% (single-HUD -> short-circuits), in_match >=97%, per-map >=95% (REL-006).

# AC8 — end-to-end smoke (BLOCKED: no real EVA .mp4 in repo; backfill apps/tooling/source/):
uv run python tools/video_test.py <video.mp4> --config output/map_configs/map_config.v2.json
```

Loop AC4→AC5→AC6 up to the 8-pass ceiling; log every pass in the story's Completion Notes
iteration table. Then Task 6/7 (commit fragments, sprint-status flips, Two-PR follow-up).
