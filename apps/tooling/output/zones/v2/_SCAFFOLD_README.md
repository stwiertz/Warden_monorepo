# Story 9.9b — v2 zone-population campaign starter

**Status:** scaffolded by the dev-story pre-flight (2026-05-17). The agent-doable surface
is done; everything below this line is the **manual human campaign** (interactive Tk +
video calibration + visual iteration).

> ## ⚠️ UPDATED 2026-07-16 (Story 9.15 — salvage) — READ BEFORE USING THIS FILE
>
> **The 4 fragments now EXIST and are COMMITTED.** `manifest.json`,
> `hud_version_detection.json`, `in_match_detection.json` and `minimap_identification.json`
> are in git and are the **source of truth**. They were reconstructed from the already-tuned
> `output/map_configs/map_config.v2.json` and proven byte-identical through the unchanged
> emitter (Story 9.15 AC2). `map_config.*` stays gitignored — it is now genuinely regenerable:
> ```bash
> uv run python tools/map_config_emitter.py --zones-dir output/zones/v2
> ```
> Populated content: **13 maps / 121 map zones + 10 hud + 3 in_match = 134 rules.**
> Measured (Story 9.15 AC6, reproduced exactly): HUD-version **0.9805** · in_match **1.0** · map-ID **1.0**.
>
> **🔴 The two `.bak` files are SUPERSEDED PRE-TUNING data. NEVER restore them.**
> `minimap_identification.json.bak` (mtime Jun 11) and `map_configs/map_config.v2.json.bak`
> (May 21) are **content-identical to each other** — the former was split out of the latter,
> so its *newer mtime is recency-of-write, not recency-of-content*. They carry **0** zones at
> `h_tol=180` where the live fragment carries **65** — i.e. they predate the accepted
> low-saturation decision (white/grey zones set `h_tol=180`, hue unconstrained) that moved
> map-ID **0.973 → 1.000**. Restoring either **regresses accuracy**. They are kept committed
> for the audit trail only.
>
> **🔴 Do NOT rename `manifest.template.json`.** The "rename" instruction below is wrong —
> the template is a **tracked file** and renaming deletes it. `manifest.json` is derived
> *alongside* it. The template's `score_screen_duration_ms` sentinel is resolved: the live
> value is **15000** (accepted as-is; recorded as unverified — the ≥5-capture median in AC3
> was never performed, and only **4** captures exist).
>
> **Corrections to the stale text below:**
> - *"No .mp4 in repo / AC8 BLOCKED: no real EVA .mp4"* → **FALSE.** Four real EVA captures
>   live at **monorepo-root `videos/V2/`** (12.7 GB, 6h13m), not `apps/tooling/source/`.
> - The AC2 frame census below is **stale** (it predates corpus drift). The live corpus is
>   **2666 PNGs / 16 classes**: artefact 418, atlantis 336, helios 316, engine 219, horizon 183,
>   silva 165, the_cliff 156, outlaw 141, lunar_outpost 93, ceres 85, polaris 75, coliseum 61,
>   the_rock 38, + lobby 296 / score 41 / transition 43. Five maps now sit under 100 frames
>   (`the_rock` 98→38, `artefact` 432→418). This census **matches the 2026-05-30 Tool 9 report
>   exactly** — the corpus has not moved since. Re-cutting the cohort split is a
>   `/bmad-correct-course`, not a dev-story change (see the note under AC2).
> - `bastion` is in `MAP_LABELS` but has **no corpus and no config entry** — 13 maps in practice.

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
