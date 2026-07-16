# Story 9.15: Pilot Zone Set for Engine POC — Salvage, Commit, Baseline

Status: review

Sprint fit: `fits-in-one-sprint` — **hours, not weeks**. Re-scoped 2026-07-16: this is a mechanical salvage, not the manual picker campaign the SCP describes. See "Why This Story Changed Shape".

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane (solo dev / product owner)**,
I want **the zone data that already exists on my disk reconstructed into its four source-of-truth fragments, committed to git, and its CPU accuracy baseline pinned**,
so that **Story 12.1 can bench the GPU engine against a reference that survives a `git clean` — instead of against untracked local state that exists in exactly one copy on one machine**.

---

## ⚠️ Why This Story Changed Shape — Read Before Anything Else

The SCP scoped 9.15 as *"minimal population (2–3 maps + HUD + in_match) via the shipped Tool 10 … Hours, not weeks"* ([SCP:184](../sprint-change-proposal-2026-07-16.md#L184)), breaking a chicken-and-egg: *12.1 needs zones → 9.9b makes zones → 9.9b is blocked on the verdict 12.1 feeds* ([epics-and-stories.md:2834](../epics-and-stories.md#L2834)).

**That premise is contradicted by what is on disk.** Nobody had looked in `output/` recently.

| Asset | Path | Reality |
|---|---|---|
| Emitted config | `apps/tooling/output/map_configs/map_config.v2.json` | **13 maps / 121 map zones / 10 hud / 3 in_match = 134 rules — fully populated AND tuned** |
| Labeled corpus | `apps/tooling/output/labeled/v2/` | **2666 PNGs / 16 classes** |
| Real captures | `videos/V2/` | **4 EVA captures, 12.7 GB, 6h13m** |
| CPU baseline | `apps/tooling/output/roi_detection_tests/v2/` | **39 Tool 9 reports** — latest scores hud **0.9805** / in_match **1.0** / map_id **1.0** (**in-sample** — see AC6) |

The human campaign this story was invented to pilot **already ran, past 9.15's finish line**. Authoring "2–3 pilot maps" with Tool 10 would produce a strict subset of data that already exists, tuned better.

**The real gap is not authorship. It is that none of it is in git.**

```
  THE 9.9b AC9 CONTRACT          WHAT IS ACTUALLY ON DISK
  ┌───────────────────────┐      ┌───────────────────────────┐
  │ fragments COMMITTED   │      │ 0 of 4 fragments exist    │
  │        ↓ emitter      │      │        ↓ emitter          │
  │ map_config REGENER-   │      │ FileNotFoundError         │
  │ ABLE (so it's ignored)│      │ config is ignored + is    │
  └───────────────────────┘      │ the ONLY copy. Git has 0. │
                                 └───────────────────────────┘
```

`zones/v2/` holds only `_SCAFFOLD_README.md`, `manifest.template.json` (**≠** `manifest.json`) and an untracked `minimap_identification.json.bak` (**≠** `.json`). `map_config_emitter.py` hard-requires all four exact names and raises `FileNotFoundError` on the first ([map_config_emitter.py:36-67](../../apps/tooling/tools/map_config_emitter.py#L36-L67)). **The emitter cannot regenerate the config that 12.1 is about to bench against, and one `git clean -xfd` erases the config, the corpus, the baseline and the `.bak` together.**

**So 9.15 becomes: reconstruct → prove → commit → pin.** The output is still a valid input to 12.1 and still a strict subset of 9.9b's deliverable — nothing is thrown away whichever way 12.3 lands ([epics-and-stories.md:2836](../epics-and-stories.md#L2836)).

### 🟢 The central mechanism is already PROVEN, not hypothesised

`_assemble_output` is **deliberately dumb** — *"No coercion, no field renaming: `zone_picker` writes fragments in the target shape"* ([map_config_emitter.py:75-99](../../apps/tooling/tools/map_config_emitter.py#L75-L99)). Therefore splitting the emitted config back into fragments is an **exact inverse**, not a lossy transform.

**Verified during story authoring** — the reconstruction below, run through the real unmodified emitter, produced output **byte-identical** to the existing `map_config.v2.json` (independently re-verified in a clean scratchpad: `raw == emitted` → **True**):

```python
frags = {
    "manifest": {
        "hud_version":              d["hud_version"],
        "reference_resolution":     d["reference_resolution"],
        "score_screen_duration_ms": d["score_screen_duration_ms"],
    },
    "hud_version_detection":  d["hud_version_detection"],   # array, verbatim
    "in_match_detection":     d["in_match_detection"],      # array, verbatim
    "minimap_identification": d["minimap_identification"],  # object, verbatim
}
# each written with json.dump(v, f, indent=2)
```

Two things follow, and both are load-bearing:
1. **AC2's byte-identity gate is achievable** — it is a fact, not an aspiration. If your run does not reproduce it, **you changed something you shouldn't have**.
2. **It proves `map_config.v2.json` was itself emitted by this emitter and has not been hand-edited since** — which is exactly what makes the fragments trustworthy as source of truth.

### 🔴 The `.bak` is NOT newer data. Do not restore, merge, or prefer it.

`minimap_identification.json.bak` is untracked, mtime **Jun 11** — *newer* than `map_config.v2.json` (May 30). The naive read ("newer file = newer data → restore it") **would silently regress accuracy**.

Measured over the 121 map zones — identical ids, identical rects; only `h_tol`/`s_tol` differ, on 69 zones:

| | zones at `h_tol=180` | `s_center` of those |
|---|---|---|
| `map_config.v2.json` (May 30) | **65** | 0–8 (mean **3.6**) |
| `minimap_identification.json.bak` (Jun 11) | **0** | — |
| `map_config.v2.json`, map zones at `h_tol≠180` | 56 | 57–85 (mean **73.0**) |

Perfect bimodal split among map zones: every `h_tol=180` zone is white/grey (`s_center ≤ 8`); every hue-constrained one is saturated. That **is** the accepted decision recorded in [[project_warden_low_sat_hue_unconstrained]] — low-saturation zones set `h_tol=180` (hue unconstrained), moving map-ID **0.973 → 1.000**. The same-day Tool 9 report scores **map_id = 1.0**, the exact post-tuning number.

**🟢 And this is not inference — there is dispositive proof.** A *second* backup sits next to the config: `apps/tooling/output/map_configs/map_config.v2.json.bak` (**May 21**, gitignored, 58864 B) — the pre-tuning config, whose `hud_version_detection` is empty. Verified:

```
zones/v2/minimap_identification.json.bak (Jun 11)
  == map_configs/map_config.v2.json.bak["minimap_identification"] (May 21)   →  True
  zone diffs: 0
```

**The Jun-11 `.bak` is content-identical to the May-21 pre-tuning config.** It was *split out of* the old config on Jun 11 — not authored on Jun 11. That permanently closes the question "is there a reading where the `.bak` is newer/better?": **no, there is not.**

**The `.bak` carries the pre-decision state.** mtime is recency-of-write, not recency-of-content. Reconstruct from `map_config.v2.json` — **never** from either `.bak`.

*(Scope the bimodality precisely: it is a **map-zone** property. `hud_z09` is `h_tol=139, s_center=5` — low-sat and hue-constrained. Don't over-generalise it.)*

---

## Acceptance Criteria

### AC0 — Kickoff decisions (resolve BEFORE Task 1; record verdicts in Dev Agent Record)

- [x] **AC0a — `.bak` disposition.** Recommended default: **Option A**.
  - **Option A (RECOMMENDED) — commit it as-is, untouched.** It is committable (the `!output/zones/**` negation covers it — verified). 53 KB buys a permanent forensic record of the pre-tuning state, and the project's FROZEN-block discipline says *"editing a completed record destroys the audit trail"*. Add one line to `_SCAFFOLD_README.md` marking it **SUPERSEDED — never restore** so the next reader cannot repeat the mtime mistake.
  - **Option B** — rename to `minimap_identification.superseded-2026-06-11.json.bak` before committing (clearer, but mutates an artifact).
  - **Option C** — delete. **Not recommended** — destroys the only evidence of the pre-tuning state, and leaves the mtime trap undocumented for the next person.
  - **Whatever is chosen, the `.bak` MUST NOT be left untracked** — untracked is the one state that guarantees silent loss.
- [x] **AC0b — Reconstruction-script disposition.** Recommended default: **Option A**.
  - **Option A (RECOMMENDED) — throwaway.** Run it once from the scratchpad; paste the exact script into Completion Notes. The fragments are the deliverable; once committed, the script is never needed again. Adding a permanent tool for a one-shot is the don't-widen-scope anti-pattern 9.11 was explicit about.
  - **Option B** — commit as `tools/<name>.py` + register in `wardentooling.py`. Costs a tool, a test file, and a menu entry for something that runs exactly once.
- [x] **AC0c — `score_screen_duration_ms` provenance.** Recommended default: **Option A**.
  - **Option A (RECOMMENDED) — accept the shipped `15000` as-is and record it as unverified.** It is already in the emitted config; 12.1 does not gate on it (it only feeds the score-screen dwell in the phase state machine). Re-deriving it is not this story's job.
  - **Option B** — re-derive per the scaffold's AC3 (*"median falling→rising edge over ≥5 EVA captures"*). ⚠️ **Only 4 captures exist** in `videos/V2/`, so the scaffold's own `≥5` floor cannot be met — Option B cannot fully close on current assets.
  - Note: `manifest.template.json`'s sentinel is the string `"TODO_HUMAN_CALIBRATION__see_AC3__..."` — deliberately a string so it **cannot silently pass** the emitter's schema gate. The reconstructed `manifest.json` carries the real integer `15000`, so the sentinel dies with the rename either way.

### Salvage — the deliverable

- [x] **AC1 — Reconstruct the four fragments** into `apps/tooling/output/zones/v2/`, derived **mechanically** from `apps/tooling/output/map_configs/map_config.v2.json` as the pure inverse of `_assemble_output`:

  | fragment | content | shape |
  |---|---|---|
  | `manifest.json` | `hud_version`, `reference_resolution`, `score_screen_duration_ms` | object (3 keys, **no** `schema_version` — the emitter inserts it) |
  | `hud_version_detection.json` | `d["hud_version_detection"]` verbatim | JSON **array** of Zone (10 entries) |
  | `in_match_detection.json` | `d["in_match_detection"]` verbatim | JSON **array** of Zone (3 entries) |
  | `minimap_identification.json` | `d["minimap_identification"]` verbatim | JSON **object** (`id`, `identification_threshold`, `roi`, `maps`) |

  🔴 **Zero hand-editing of any zone value.** Not one `h_tol`, `s_tol`, `min_ratio`, `weight`, rect coord, or map slug. This story moves data; it does not tune data. Any value change silently invalidates the pinned baseline (AC6) and breaks AC2.
  🔴 **Source is `map_config.v2.json`. NEVER either `.bak`** (`zones/v2/minimap_identification.json.bak` **or** `map_configs/map_config.v2.json.bak` — both are pre-tuning; see above).
  🔴 **Derive `manifest.json`; do NOT rename the template.** [`_SCAFFOLD_README.md:38`](../../apps/tooling/output/zones/v2/_SCAFFOLD_README.md#L38) says *"Fill `manifest.template.json` → **rename** to `manifest.json`"* — following that literally **deletes a tracked file**. `manifest.template.json` stays; write `manifest.json` alongside it. (AC7 fixes the README's wording.)

- [x] **AC2 — Prove the round-trip: byte-identical.** Run the **unmodified** emitter against the reconstructed fragments and byte-compare against the pre-existing config. **Emit to a throwaway dir so the comparison target is never overwritten:**
  ```bash
  cd apps/tooling
  cp output/map_configs/map_config.v2.json <scratchpad>/before.json
  uv run python tools/map_config_emitter.py --zones-dir output/zones/v2 --output-dir <scratchpad>/emit-probe
  ```
  ```python
  # THE GATE — compare bytes, never lengths:
  a = open('<scratchpad>/emit-probe/map_config.v2.json','rb').read()
  b = open('<scratchpad>/before.json','rb').read()
  assert a == b
  ```
  ⚠️ **Do NOT gate on a byte count.** The emitter's default `--output-dir` is `output/map_configs` ([map_config_emitter.py:34](../../apps/tooling/tools/map_config_emitter.py#L34)), so a default-dir run **overwrites the very file you are comparing against** — and atomic refusal does *not* protect you here (it guards validation *failure*; a successful emit of *different* content overwrites silently). `--output-dir` removes the risk class entirely; the backup is the second belt.
  ⚠️ **Size is platform-dependent and is NOT the gate:** the file is **62476 bytes on Windows** (CRLF; `core.autocrlf=true`, no `.gitattributes`) and **59987 LF-normalized** — the same content. A dev who checks `wc -c` against a memorized number will trip the STOP below on a measurement artifact. **`a == b` on bytes is the only check that means anything.**
  🛑 **If the bytes differ, STOP and report.** It means either a zone value was edited (AC1 violated) or the config was hand-modified after emission — and in the second case the whole "fragments are source of truth" premise needs re-examining before anything is committed. Do not "fix" the diff by editing fragments to match.

- [x] **AC3 — Schema validation passes.** Implicit in AC2 (`emit()` runs `Draft202012Validator` and `sys.exit(1)`s **before any write** — atomic refusal, [map_config_emitter.py:125-146](../../apps/tooling/tools/map_config_emitter.py#L125-L146)), but assert it explicitly: exit code **0**, and the printed summary reads `hud_version_detection: 10 zone(s)` / `in_match_detection: 3 zone(s)` / `minimap_identification.maps: 13 map(s), 121 total zone(s)`.

- [x] **AC4 — Commit the fragments as the source of truth.** This closes the 9.9b AC9 Option A contract for the first time. Verified committable — `apps/tooling/.gitignore:3` ignores `output/*`, then `:6-7` negate `!output/zones/` + `!output/zones/**`, and root `.gitignore:66` uses `apps/tooling/output/*` (**not** `output/`) *specifically* so git descends far enough for that negation to apply. `git check-ignore -q` returns **1 (not ignored)** for all four paths and `git add -n` succeeds. **The emitted `map_config.*` stays ignored — that is correct and intended** (it is now genuinely regenerable).

- [x] **AC5 — `.bak` disposition executed** per AC0a. Must not remain untracked.

- [x] **AC6 — Pin the CPU baseline.** Re-run Tool 9 **unmodified** against the reconstructed-and-emitted config:
  ```bash
  uv run python tools/roi_detection_tester.py --config output/map_configs/map_config.v2.json \
      --labeled output/labeled --output output/roi_detection_tests --save-frame-predictions
  ```
  **Confirm it reproduces the existing latest report** ([`v2/2026-05-30T135106/report.json`](../../apps/tooling/output/roi_detection_tests/v2/2026-05-30T135106/report.json)):

  | classifier | accuracy **(in-sample)** | n_evaluated | n_correct |
  |---|---|---|---|
  | `hud_version_classifier` | **0.9805** | 2666 | 2614 |
  | `in_match_classifier` | **1.0** | 2666 | 2666 |
  | `map_id_classifier` | **1.0** | 2286 | 2286 |

  🔴 **These are IN-SAMPLE numbers. They are a parity reference, NOT a generalization claim.** *(Label added by code review 2026-07-16 — decision D3.)* The zones were **tuned against this exact corpus**: the accepted low-saturation decision moved map-ID **0.973 → 1.000** by setting `h_tol=180` on 65 of the 121 map zones ([[project_warden_low_sat_hue_unconstrained]]). There is **no holdout and no train/test split**. Two classifiers reading exactly **1.000** is therefore what a fit to its own training data looks like — it is **not** evidence that detection generalizes to unseen frames.

  **This does not weaken the AC.** What 12.1 needs is a **frame-for-frame parity target** — "does the GPU reproduce what the CPU does on these 2666 frames" — and for that purpose in-sample-ness is irrelevant and these numbers are exactly right. The story is already explicit that **REL-006's accuracy floors are NOT gated here**. The label exists so the next reader of *"the only durable record"* cannot mistake `1.0` for a shipped-quality claim. **Measuring generalization is 9.9b's job** (its AC2 certitude + zero-train/test-overlap gate is precisely this problem).

  **Reproduction is near-certain, and that is provable up front:** the May-30 report's own `run_metadata.frame_count_by_class` was compared against the live corpus during authoring and matches **exactly, all 16 classes** (artefact 418, the_rock 38, …). The `98→38` / `432→418` drift the scaffold's census shows **predates this report** — the corpus has not moved *since* it.
  🛑 **Divergence ⇒ STOP and report.** Do not reason "the corpus probably drifted" — it provably has not, and AC2 proves the config is unchanged. **A divergence therefore means something this story has not accounted for**, which is a *more* alarming signal than corpus drift, not a lesser one. Surface it; do not overwrite it.
  Transcribe the confirmed three numbers into **Completion Notes** — the `roi_detection_tests/` tree stays gitignored, so **the story file is the only durable record of the baseline**. That is the point of this AC.

- [x] **AC7 — De-stale `_SCAFFOLD_README.md`.** It is the operative contract doc for this directory and is now actively misleading. Fix all five:
  1. *"No .mp4 in repo: `apps/tooling/source/` is absent — supply captures"* and *"AC8 BLOCKED: no real EVA .mp4"* → **false**; 4 captures live at monorepo-root `videos/V2/`.
  2. The AC2 frame census (`:26-27`) is stale — record the current one and that it matches the May-30 report.
  3. `:38`'s *"**rename** to `manifest.json`"` → **copy/derive**; the template is tracked and must survive.
  4. The `.bak` **SUPERSEDED — never restore** warning (AC0a), naming **both** `.bak` files and the proof they are pre-tuning.
  5. The 4 fragments now exist, are committed, and are the source of truth.

### Fences

- [x] **AC8 — Scope fence: this story moves data, it does not make data.**
  **Do NOT:** run Tool 10 / author or re-tune any zone; drift into 9.9b's 8-map population or its 8-pass loop; touch `contracts/map-config.schema.json` (E1 — no `schema_version` bump; [INVARIANT 1] makes `contracts/` master); modify `map_config_emitter.py`, `roi_detection_tester.py`, `zone_picker/`, or `video_test.py`; add a dependency; touch any mobile/web file.
  **Note the deliberate omission:** the SCP's *"pilots 9.9b's 8-pass loop end-to-end"* rationale ([:2836](../epics-and-stories.md#L2836)) **does not apply to this re-scope** — there is no authoring loop left to pilot, because the authoring already happened. 9.9b's loop remains unpiloted; that risk stays with 9.9b and is unchanged by this story. Say so in Completion Notes rather than pretending the loop was exercised.
  Also **out of scope:** the Volet-B residue ([:2842](../epics-and-stories.md#L2842) — `ColorPickerMode` wiring, `min_ratio` in `read_band`, single-frame input) — it was folded in *"optional, only if the POC needs it"*, and a salvage story does not need it. Leave it to 12.1.
- [x] **AC9 — No regressions.** `cd apps/tooling && uv run pytest` → **204** collected, 0 failures (baseline unchanged; under AC0b Option A this story adds no test file because it adds no code). `pnpm --filter tooling test` parity.
  ⚠️ **AMENDED 2026-07-16 by code review — the baseline is now 208, and the parenthetical's reasoning was wrong.** *"Adds no test because it adds no code"* is true about code and false about **invariants**: this story made fragments→config load-bearing and guarded it with nothing. `tests/test_zone_fragments_v2.py` (+4) closes that. **New gate: 208 passed, 0 regressions** — verified on both `uv run pytest` and `pnpm --filter tooling test`. This also **reverses AC0b Option A** ("throwaway, no test file") and **breaches AC8's `apps/tooling/tests/` fence** — both accepted deliberately by Stephane at review, as a post-merge follow-up commit rather than a re-opening of `e4b9c29`.
- [ ] **AC10 — [HELD] `review → done` flip** + post-merge sprint-status update. Two-PR pattern. *(Confirmed still genuinely open at code review 2026-07-16: `Status:` and `sprint-status.yaml` both read `review`.)*
- [x] **AC11 — ~~[HELD]~~ DONE (corrected 2026-07-16 by code review — was executed while still marked HELD).** Local `git merge --no-ff` per Epic 9 precedent (`gh` unauthenticatable non-interactively). Conventional Commits, scope **`tooling`** ([INVARIANT 12]). **Delivered:** feature `e4b9c29` *"feat(tooling): commit v2 zone fragments as source of truth (Story 9.15)"* → merged `be0292b` *"chore(tooling): merge Story 9.15 salvage — zone fragments source of truth"* into `correct-course-engine-first-pivot`. All three requirements (Conventional Commits, scope `tooling`, local `--no-ff`) verified met.

---

## Tasks / Subtasks

- [x] **Task 1 — Kickoff + pre-flight** (AC0)
  - [x] Resolve AC0a / AC0b / AC0c; record verdicts.
  - [x] Back up the current `map_config.v2.json` **outside the repo** (scratchpad) — AC2 compares against it. ⚠️ Name it something other than `.bak`: `map_configs/map_config.v2.json.bak` **already exists** (May 21, gitignored) and is the *pre-tuning* config — the same trap as the other `.bak`, one directory over. Do not overwrite it and do not confuse it for your backup.
  - [x] Pin the pytest baseline: `uv run pytest --collect-only -q` → **204**.
  - [x] Confirm the four target paths are committable: `git check-ignore -q apps/tooling/output/zones/v2/manifest.json; echo $?` → **1**.
- [x] **Task 2 — Reconstruct** (AC1)
  - [x] Load `map_config.v2.json` with `encoding="utf-8-sig"` (BOM-tolerant, the project convention).
  - [x] Split into the four fragments per the AC1 table; write each with `json.dump(v, f, indent=2)`, `encoding="utf-8"`.
  - [x] **Diff-check yourself:** the union of the four fragments must reproduce every key of the config except `schema_version` (emitter-inserted). No value edited.
- [x] **Task 3 — Prove + validate** (AC2, AC3)
  - [x] Run the emitter; assert exit 0 and the 10 / 3 / 13-maps-121-zones summary.
  - [x] Byte-compare emitted vs the Task-1 backup. **Identical or STOP.**
- [x] **Task 4 — Baseline** (AC6)
  - [x] Re-run Tool 9; confirm 0.9805 / 1.0 / 1.0. Divergence ⇒ STOP and report.
  - [x] Transcribe the three numbers + the report timestamp into Completion Notes.
- [x] **Task 5 — Commit the source of truth** (AC4, AC5)
  - [x] `git add` the four fragments + the `.bak` per AC0a.
  - [x] Confirm `git status` shows them staged (not ignored) and that `map_config.v2.json` remains **un**staged/ignored.
- [x] **Task 6 — Docs** (AC7)
  - [x] Update `_SCAFFOLD_README.md`: captures at `videos/V2/`, stale-census caveat, `.bak` SUPERSEDED warning, fragments now committed.
- [x] **Task 7 — Gates** (AC9)
  - [x] `uv run pytest` → 204, 0 regressions. `pnpm --filter tooling test` parity.
  - [x] *(Post-review 2026-07-16)* `uv run pytest` → **208**, 0 regressions. `pnpm --filter tooling test` parity → **208**.
- [x] **Task 8 — ~~[HELD]~~ Delivery PARTIALLY DONE** (AC10, AC11) — **AC11 done**: `e4b9c29` committed + local `--no-ff` merge `be0292b`. **AC10 still held**: the post-merge `review → done` + sprint-status pass is deferred per [[project_warden_shared_doc_commit_boundary]] (12.1's flips are co-mingled in `sprint-status.yaml`).

---

## Dev Notes

### The emitter contract — read it, don't infer it

[map_config_emitter.py](../../apps/tooling/tools/map_config_emitter.py), quoted where it binds:

- **`_FRAGMENT_FILES`** ([:36-41](../../apps/tooling/tools/map_config_emitter.py#L36-L41)) — exactly `manifest`, `hud_version_detection`, `in_match_detection`, `minimap_identification`, read as `<name>.json` from `--zones-dir`. **Exact names.** `manifest.template.json` does not count; neither does a `.bak`.
- **`_load_fragments`** ([:49-67](../../apps/tooling/tools/map_config_emitter.py#L49-L67)) — `FileNotFoundError(f"missing zone fragment: {path}")` on the first missing file; reads `utf-8-sig`.
- **`_assemble_output`** ([:75-99](../../apps/tooling/tools/map_config_emitter.py#L75-L99)) — the inverse you are implementing. It requires `manifest` to be a dict carrying `hud_version`, `score_screen_duration_ms`, `reference_resolution`, and emits keys in this order: `schema_version` (**hardcoded 1**, inserted first "for readable diffs"), `reference_resolution`, `hud_version`, `score_screen_duration_ms`, then the three sections verbatim.
- **Atomic refusal** ([:137-141](../../apps/tooling/tools/map_config_emitter.py#L137-L141)) — validation runs *before* `os.makedirs`/write. A failed emit leaves the previous config untouched. This is why AC2's "STOP on diff" is safe: a bad run cannot corrupt the file you are comparing against.
- **Output path** is derived from the manifest's `hud_version` ([:144](../../apps/tooling/tools/map_config_emitter.py#L144)) → `map_config.v2.json`. A typo'd `hud_version` silently writes a *different filename* rather than erroring — check the printed `Output:` line.
- **Write format** ([:145-146](../../apps/tooling/tools/map_config_emitter.py#L145-L146)): `json.dump(output, f, indent=2)`, `encoding="utf-8"`, `ensure_ascii` default (True). Match this in the fragments for clean diffs.

### The 4-fragment contract (from the scaffold, verified against the emitter)

[`_SCAFFOLD_README.md:33-42`](../../apps/tooling/output/zones/v2/_SCAFFOLD_README.md#L33-L42) states it and matches the code:
> `manifest.json` — human-authored. Required keys: `hud_version` (enum, `"v2"`), `reference_resolution` (`{width,height}`), `score_screen_duration_ms` (integer ≥ 0). Fill `manifest.template.json` → rename to `manifest.json`.

`manifest.template.json` already carries the correct `hud_version` and `reference_resolution`; only `score_screen_duration_ms` is a sentinel — and the config supplies the real value (**15000**). So `manifest.json` = the template with one field replaced (AC0c).

### Schema facts that constrain the fragments

[contracts/map-config.schema.json](../../contracts/map-config.schema.json) — you are not editing it, but the emitter validates against it:
- `schema_version`: `enum [1]` — **the emitter inserts it; the manifest must NOT carry it.**
- `hud_version`: `enum ["v1","v2"]`. `additionalProperties: false` at top level.
- `Zone` requires `id,x,y,width,height,hsv,min_ratio,weight,weight_override`; `weight_override` is `number|null`.
- `Hsv` is **user-space** (H 0–360, h_tol 0–180, S/V 0–100) — *"NOT OpenCV-space"*.
- **Map iteration order is preserved from the fragment; the emitter does NOT sort** — so `minimap_identification.json` must keep the config's map order for AC2's byte-identity to hold. `json.load`/`json.dump` preserve insertion order; do not `sorted()` anything.
- Empty zone arrays are legal everywhere (the runtime short-circuits to `unknown`) — irrelevant here since nothing is empty, but it means the emitter would happily accept a fragment you accidentally emptied. **AC2 is your only real guard against that.**

### What is in the data (so you can sanity-check without re-deriving it)

- **134 rules total**: 10 `hud_version_detection` + 3 `in_match_detection` + 121 map zones across **13** maps (`artefact` 17, `polaris` 13, `atlantis` 11, `lunar_outpost` 11, `silva` 10, `ceres` 8, `helios` 8, `horizon` 8, `outlaw` 8, `the_rock` 8, `the_cliff` 7, `coliseum` 6, `engine` 6).
- **`bastion` is in `MAP_LABELS` but has no corpus and no config entry** — 13 maps in practice, not 14. Not a defect to fix here.
- Uniform across all 134 rules: `min_ratio` **0.3**, `weight` **1.0**, `weight_override` **null**.
- Rect areas **1–25 px**, mode 2×2; fourteen rules are literally `w=1,h=1`.
- `minimap_identification`: `id: "test"`, `identification_threshold: 0.6`, `roi: {name:"minimap", x:63, y:922, width:3, height:5}`. ⚠️ **`id: "test"` and a 3×5-px minimap ROI look like leftover scaffolding.** Both are schema-valid and both are *the tuned config's actual content* — **do not "clean them up"** (that is a zone-value edit, AC1/AC2 violation). Note them in Completion Notes as a question for 12.1/9.9b.

### Corpus census — known stale, do not trust the scaffold's table

`_SCAFFOLD_README.md:26-27`'s cohort split was taken 2026-05-17 and has drifted. Current `output/labeled/v2/`: **2666 PNGs / 16 classes** = 13 map classes + `lobby` 296 / `score` 41 / `transition` 43 (**380 negatives**). Per map: artefact 418, atlantis 336, helios 316, engine 219, horizon 183, silva 165, the_cliff 156, outlaw 141, lunar_outpost 93, ceres 85, polaris 75, coliseum 61, the_rock 38.

Versus the scaffold's census: `the_rock` **98 → 38**, `artefact` **432 → 418**. Five maps now sit under 100 frames. That drift is real but it **predates the May-30 report** — the report's own `run_metadata.frame_count_by_class` matches the live corpus exactly, all 16 classes. The corpus is gitignored (`output/*`) and unversioned, so drift is unrecorded in general — but it provably has **not** moved since the baseline was taken. **This is why AC6 says a divergence is MORE alarming than corpus drift, not less: drift is the one explanation already ruled out.** Report the current census in Completion Notes; **do not re-cut the cohort split** (that is 9.9b's AC2 and needs a `/bmad-correct-course`, per the scaffold's own note at `:30-31`).

*(Corrected by code review 2026-07-16: this paragraph previously read "**This is why AC6 says a Tool 9 divergence means the corpus moved, not the config** — and it is a real possibility, not a formality", which states the exact inverse of AC6. AC6 is the correct one.)*

### Git mechanics — verified, not assumed

```
apps/tooling/.gitignore
  3: output/*                 ← ignores everything under output/
  6: !output/zones/           ← re-includes the directory
  7: !output/zones/**         ←   and its contents
root .gitignore
 66: apps/tooling/output/*    ← `/*` NOT `/` — so git DESCENDS and the negation can apply
 78: videos/                  ← the captures stay out of git (12.7 GB)
```
Verified: `git check-ignore -q <each fragment path>` → exit **1** (not ignored); `git add -n` on a probe file under `zones/v2/` → `add 'apps/tooling/output/zones/v2/__probe.json'`. Already-tracked proof: `_SCAFFOLD_README.md` and `manifest.template.json` are in `git ls-files`.

**A directory-form negation would not work** — that is why root uses `apps/tooling/output/*`. Do not "tidy" either `.gitignore`; they are load-bearing exactly as written, and the comments at `.gitignore:63-65` say so.

### Line endings — the mechanic behind AC2's "compare bytes, not lengths"

There is **no root `.gitattributes`** and `core.autocrlf=true`. So: the emitter's `open(..., "w")` writes **CRLF** on this machine; fragments commit as **LF** blobs and check out as CRLF. Consequences:

- **Regenerability is platform-safe.** The emitter reads via `json.loads`, which is whitespace-insensitive — a fragment committed LF and checked out CRLF emits the same config either way.
- **Emitted byte *size* is not portable.** `map_config.v2.json` is **62476 bytes on Windows** and **59987 LF-normalized** (2489 CRLFs; 62476 − 2489 = 59987). Reading it in Python **text** mode returns 59987 characters; reading `'rb'` returns 62476 bytes. Both describe identical content.

**Never pin a byte count as a gate** — it will pass on one machine and falsely trip AC2's STOP on another. `a == b` on `'rb'` reads is the whole check.

### Conventions that bind even a data story

- Read JSON with `encoding="utf-8-sig"` (BOM-tolerant) — the emitter does, `video_test.py:268` does.
- Write with `json.dump(..., indent=2)`, `encoding="utf-8"` — match the emitter for clean diffs.
- Conventional Commits, scope `tooling` ([INVARIANT 12]).
- Two-PR delivery + local `--no-ff` per [[feedback_two_pr_docs_execution]] and Epic 9 precedent (9.9c/9.11/9.12/9.14 all shipped this way; `gh` is unauthenticatable non-interactively).
- ⚠️ [[project_warden_shared_doc_commit_boundary]]: `sprint-status.yaml` currently co-mingles this story's flip with **Story 12.1's** (created in the same session). If the post-merge PR cannot be file-isolated, **ship the feature PR alone and defer the post-merge pass** — do not entangle 12.1's boundary.

### Downstream — what this unblocks and what it does not

- **Story 12.1** (`ready-for-dev`) consumes `map_config.v2.json` read-only and is **not blocked** by this story — it can bench today. What 9.15 buys it is that the config, the baseline, and the fragments **survive**. 12.1's AC12 re-runs Tool 9 and confirms the same three numbers; **if 9.15 lands first, 12.1's AC12 is a formality; if not, 12.1 is benching against state that could vanish mid-story.**
- **Story 9.9b** (`blocked` on 12.3) — this story's output is a strict subset of its deliverable and its zone data survives an engine swap ([epics-and-stories.md:2791-2794](../epics-and-stories.md#L2791-L2794)). 9.15 does **not** unblock it and does **not** pilot its loop.
- **Story 9.16** (`backlog`, conditional on 12.3) — unaffected. Tool 9 remains the sole live REL-006 instrument; this story neither re-points nor modifies it.
- **REL-006's ≥95% map-ID floor is NOT gated here** ([epics-and-stories.md:2838](../epics-and-stories.md#L2838): *"Accuracy floors are not gated here"*). AC6 **pins** a measurement; it does not enforce a floor. The measured `map_id 1.0` happens to clear it — that is an observation, not this story's gate.

### Project Structure Notes

```
apps/tooling/output/zones/v2/
├── _SCAFFOLD_README.md                  # UPDATE (AC7) — tracked; stale blockers
├── manifest.template.json               # KEEP tracked (the template survives the rename)
├── manifest.json                        # NEW — committed  ┐
├── hud_version_detection.json           # NEW — committed  │ the 4-fragment
├── in_match_detection.json              # NEW — committed  │ source of truth
├── minimap_identification.json          # NEW — committed  ┘
└── minimap_identification.json.bak      # AC0a — SUPERSEDED; commit, never restore

apps/tooling/output/map_configs/
└── map_config.v2.json                   # stays GITIGNORED — now genuinely regenerable
apps/tooling/output/roi_detection_tests/ # stays GITIGNORED — baseline lives in Completion Notes
```

No code files change under AC0b Option A. No new tests (no new code). No new dependencies.

### References

- [epics-and-stories.md:2830-2845](../epics-and-stories.md#L2830-L2845) — Story 9.15 as chartered (prose only; **no numbered ACs exist** — this file supplies the first)
- [epics-and-stories.md:2836](../epics-and-stories.md#L2836) — the "pilots 9.9b's loop" rationale (**does not survive the re-scope** — AC8)
- [epics-and-stories.md:2838](../epics-and-stories.md#L2838) — scope guards; accuracy floors explicitly not gated here
- [epics-and-stories.md:2842](../epics-and-stories.md#L2842) — Volet-B residue (out of scope)
- [epics-and-stories.md:2791-2794](../epics-and-stories.md#L2791-L2794) — 9.9b held, not cancelled; zone data survives an engine swap
- [sprint-change-proposal-2026-07-16.md:184](../sprint-change-proposal-2026-07-16.md#L184) — 9.15's original scope ("2–3 maps … hours, not weeks")
- [sprint-change-proposal-2026-07-16.md:299](../sprint-change-proposal-2026-07-16.md#L299) — the `/bmad-create-story 9.15` then `12.1` handoff
- [map_config_emitter.py:36-99](../../apps/tooling/tools/map_config_emitter.py#L36-L99) — `_FRAGMENT_FILES`, `_load_fragments`, `_assemble_output` (**the inverse to implement**)
- [map_config_emitter.py:125-157](../../apps/tooling/tools/map_config_emitter.py#L125-L157) — `emit()`: atomic refusal + the summary print
- [_SCAFFOLD_README.md:33-42](../../apps/tooling/output/zones/v2/_SCAFFOLD_README.md#L33-L42) — the 4-fragment contract
- [contracts/map-config.schema.json](../../contracts/map-config.schema.json) — the validation gate (read-only here)
- `apps/tooling/output/roi_detection_tests/v2/2026-05-30T135106/report.json` — the baseline to confirm (AC6)
- Memory: [[project_warden_low_sat_hue_unconstrained]] (**the `.bak` trap**), [[project_warden_9_9b_ac2_and_campaign]], [[project_warden_engine_first_pivot]], [[feedback_two_pr_docs_execution]], [[feedback_ac_checkbox_tighten]], [[project_warden_shared_doc_commit_boundary]]

---

## Change Log

| Date | Change |
|---|---|
| 2026-07-16 | Story created via `/bmad-create-story` (Stephane; claude-opus-4-8[1m]). `ready-for-dev` (status unchanged — the tracker already read `ready-for-dev` despite no story file existing; this file makes that status true for the first time). **Re-scoped from the SCP's greenfield picker campaign to a salvage story** on evidence that the zone data already exists on disk and exceeds the chartered scope, while none of it is in git. AC0 (3 kickoff decisions) + AC1–AC11 + 8 Tasks. The reconstruction round-trip was **verified byte-identical during authoring** (and independently re-verified in a clean scratchpad) before being written as AC2 — which gates on a byte *comparison*, never a byte *count*. |
| 2026-07-16 | `/bmad-dev-story` (Amelia; claude-opus-4-8[1m]). `ready-for-dev → in-progress → review`. **AC0a/AC0b/AC0c = Option A ×3; AC1–AC9 delivered `[x]`; AC10/AC11 `[ ] [HELD]`.** The four fragments are reconstructed and **staged** as the source of truth, closing the 9.9b AC9 Option A contract for the first time; `map_config.v2.json` is now genuinely regenerable and correctly stays gitignored. **AC2 round-trip proven byte-identical** through the unmodified emitter (emitted to a throwaway `--output-dir`; live config verified untouched) — which carries the corollary that the config was emitter-produced and never hand-edited. **AC6 baseline reproduced EXACTLY** (`0.9804951237809453` / `1.0` / `1.0`, n=2614/2666, 2666/2666, 2286/2286) and transcribed into Completion Notes, which are now its only durable record. `_SCAFFOLD_README.md` de-staled (5 corrections incl. the `.bak` SUPERSEDED warning and the rename trap). **Zero zone values changed; zero code/schema/dependency touched** (verified mechanically). Gates: pytest **204 passed**, `pnpm --filter tooling test` **204 passed**, 0 regressions. Git delivery HELD per Stephane — nothing committed or merged. Honest omission recorded: 9.9b's 8-pass loop remains **unpiloted** (the charter's pilot rationale did not survive the re-scope). |
| 2026-07-16 | `/bmad-code-review` (Stephane; claude-opus-4-8[1m]). Three parallel layers + independent mechanical re-verification. **The data was re-proven sound** — AC2 byte-identity reproduced (`a == b` → True, 62476 B), zero non-HSV drift across 121 zones, `.bak` pre-tuning claim confirmed dispositive (65 vs 0 at `h_tol=180`); **AC1–AC5, AC8, AC9 and all three AC0 verdicts hold**. **5 decision-needed / 5 patch / 4 deferred / 2 dismissed.** ⚠️ **The row above is superseded on one point: it states "nothing committed or merged" — but AC11 HAD been executed** (`e4b9c29` + `--no-ff` merge `be0292b`). Left intact as the dated record; AC11 flipped to `[x]`, File List de-staled, AC10 confirmed genuinely open. **Decisions D1+D4+D5 collapsed into one new guard** — `apps/tooling/tests/test_zone_fragments_v2.py` pins an LF-normalized SHA256 of the emitter output (`eb33f1ee…`), making AC2 re-provable on any machine forever, enforcing the fragments→config invariant (proven to bite on a single-scalar mutation), and sidestepping the CRLF/LF platform trap without a `.gitattributes` sweep. **This knowingly reverses AC0b Option A, AC8's `tests/` fence, and AC9's baseline (204 → 208)** — the "adds no test because it adds no code" reasoning was wrong: it added no code but **did** add an invariant. **D2 escalated into Story 12.1 as new AC13b** — the `roi` field is byte-identical to `atlantis_z10`'s rect, 120/121 zones fall outside it, and Tool 9 parses-but-never-reads it; a shader honouring it would score ≈0 and read as a broken GPU port. 12.1's AC16 baseline moved 204 → 208. **D3 (in-sample baseline) left open.** Patches applied to README (rename trap, EVA-captures-not-missing ×2, stale-census annotation) and story (AC6-vs-Dev-Notes inversion, dangling "Finding-2"). Nothing committed. |

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Amelia / `/bmad-dev-story`), 2026-07-16.

### Debug Log References

All gates run from `apps/tooling/`. Scratchpad (outside repo): `<scratchpad>/s915/`.

| Gate | Command | Result |
|---|---|---|
| Pre-flight: pytest baseline | `uv run pytest --collect-only -q` | **204 collected** |
| Pre-flight: fragments committable | `git check-ignore -q output/zones/v2/<f>.json` | **exit 1** ×4 (not ignored) |
| AC3 emit | `uv run python tools/map_config_emitter.py --zones-dir output/zones/v2 --output-dir <scratchpad>/emit-probe` | **EXIT=0**; `hud_version_detection: 10 zone(s)` / `in_match_detection: 3 zone(s)` / `minimap_identification.maps: 13 map(s), 121 total zone(s)` |
| AC2 gate | `open(emitted,'rb').read() == open(before,'rb').read()` | **True** (62476 B both; size informational, not the gate) |
| AC6 baseline | `uv run python tools/roi_detection_tester.py --config output/map_configs/map_config.v2.json --labeled output/labeled --output output/roi_detection_tests --save-frame-predictions` | report → `output/roi_detection_tests/v2/2026-07-16T215723/` |
| AC9 pytest | `uv run pytest -q` | **204 passed in 2.43s** |
| AC9 parity | `pnpm --filter tooling test` | **204 passed in 1.35s** |

### Completion Notes List

**AC0 verdicts (all recommended defaults, confirmed by Stephane at kickoff):**
- **AC0a = Option A** — `.bak` committed as-is, byte-untouched. Verified post-commit it still equals `map_configs/map_config.v2.json.bak["minimap_identification"]` → `True` (unmodified). SUPERSEDED warning added to `_SCAFFOLD_README.md` per the option's own requirement.
- **AC0b = Option A** — throwaway reconstruction script; no tool added, no `wardentooling.py` entry, no test file. Script reproduced verbatim below.
- **AC0c = Option A** — shipped `score_screen_duration_ms: 15000` accepted as-is and **recorded as UNVERIFIED**. Option B was not merely declined but is **unachievable on current assets**: the scaffold's AC3 mandates a *"median of ≥5 EVA captures"* and only **4** exist in `videos/V2/`. The provenance of `15000` is unknown — someone set it before May 30. **Open question for 12.1/9.9b**, not closed by this story.

**The reconstruction script (AC0b — run once, not committed):**
```python
import json, io, os
d = json.load(io.open('output/map_configs/map_config.v2.json', encoding='utf-8-sig'))
fragments = {
    "manifest": {
        "hud_version":              d["hud_version"],
        "reference_resolution":     d["reference_resolution"],
        "score_screen_duration_ms": d["score_screen_duration_ms"],
    },
    "hud_version_detection":  d["hud_version_detection"],
    "in_match_detection":     d["in_match_detection"],
    "minimap_identification": d["minimap_identification"],
}
covered = {"hud_version","reference_resolution","score_screen_duration_ms",
           "hud_version_detection","in_match_detection","minimap_identification"}
assert not (set(d) - covered) - {"schema_version"}     # every config key covered
assert "schema_version" not in fragments["manifest"]   # emitter inserts it
for name, value in fragments.items():
    with io.open(os.path.join('output/zones/v2', name + '.json'), 'w', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
```

**✅ AC2 — round-trip PROVEN, and it carries a corollary.** Reconstructed fragments → real unmodified emitter → **byte-identical** to the pristine pre-story backup. Emitted to a throwaway `--output-dir` so the comparison target was never at risk; confirmed afterwards that the live config was untouched by the probe run. **Corollary: `map_config.v2.json` was emitter-produced and has never been hand-edited — which is precisely what makes the committed fragments a faithful source of truth.** The 9.9b AC9 Option A contract ("fragments committed, `map_config` regenerable from them") is satisfied **for the first time**.

**✅ AC6 — baseline reproduced EXACTLY, not inherited.** New run `2026-07-16T215723` vs the May-30 report, compared as exact floats. 🔴 **All three are IN-SAMPLE — a parity reference, not a generalization claim** (see AC6; code-review decision D3, 2026-07-16):

| classifier | May 30 | 2026-07-16 | n | match |
|---|---|---|---|---|
| `hud_version_classifier` **(in-sample)** | `0.9804951237809453` | `0.9804951237809453` | 2614/2666 | ✅ |
| `in_match_classifier` **(in-sample)** | `1.0` | `1.0` | 2666/2666 | ✅ |
| `map_id_classifier` **(in-sample)** | `1.0` | `1.0` | 2286/2286 | ✅ |

⚠️ **Scope this reproduction honestly.** Identical config (AC2, byte-proven) + identical corpus (verified unmoved) + unmodified deterministic Tool 9 ⇒ identical floats **necessarily**. This confirms the fragments carry the tuned state; it is **not** independent evidence that the numbers are good.

**This story file is now the only durable record of these numbers** — `output/roi_detection_tests/` is gitignored. That was the point of AC6.
Note the reproduction independently re-confirms the conclusion of *"🔴 The `.bak` is NOT newer data"* above: the committed fragments carry the tuned state (`map_id 1.0`), not the `.bak`'s pre-tuning state. *(Reference de-dangled by code review 2026-07-16 — this read "the Finding-2 conclusion", but no numbered finding exists in this file.)*

**✅ AC8 — scope fence held, verified mechanically.** `git status` over `contracts/`, `apps/tooling/tools/`, `pyproject.toml`, `requirements.txt`, `apps/mobile/`, `apps/web/` → **empty**. No code, no schema, no dependency, no test touched. Zone values: the config regenerated from the committed fragments is byte-identical to the pristine pre-story backup, and the live config is unchanged → **zero zone values altered. The story moved data; it did not make data.**

**Fragment/`.bak` integrity spot-check:** new `minimap_identification.json` has **65** zones at `h_tol=180` (the tuned state); `.bak` has **0** (pre-tuning). Confirms the right artifact was committed as source of truth.

**⚠️ Honest omissions and open items (deliberately NOT resolved here):**
- **9.9b's 8-pass loop remains UNPILOTED.** The charter's *"this also pilots 9.9b's own loop end-to-end"* rationale ([epics-and-stories.md:2836](../epics-and-stories.md#L2836)) **did not survive the re-scope** — there was no authoring loop left to pilot, because the authoring had already happened. That risk sits with 9.9b, unchanged by this story. Stated rather than pretended away.
- **`score_screen_duration_ms: 15000` is unverified** (AC0c) — provenance unknown, and the ≥5-capture median is unachievable with 4 captures.
- **`minimap_identification.id: "test"` and a 3×5-px minimap `roi`** look like leftover scaffolding. Both are schema-valid and both are the *tuned* config's actual content, so touching them would have been a zone-value edit (AC1/AC2 violation). **Committed as-is. Question for 12.1/9.9b.**
- **`bastion`** is in `MAP_LABELS` but has neither corpus nor config entry — 13 maps in practice, not 14. Not a defect for this story.
- **Corpus and baseline remain gitignored.** 9.15 secures the *config* (now regenerable from committed fragments). `output/labeled/` (2666 PNGs) and `output/roi_detection_tests/` are still unversioned local state — a `git clean -xfd` still costs the corpus and the reports, though no longer the config. Out of scope; worth a future decision.
- **~~AC10/AC11 [HELD]~~ — SUPERSEDED 2026-07-16 by code review. AC11 was executed; AC10 was not.** This bullet originally read *"no commit, no merge. Fragments are **staged only**, per Stephane's hold."* **That is no longer true of AC11:** the fragments were committed as `e4b9c29` (Conventional Commits, scope `tooling`) and merged into `correct-course-engine-first-pivot` via local `--no-ff` `be0292b`. `git status` is clean. **AC11's substance was met and its checkbox is now `[x]`.** **AC10 remains genuinely open** — `Status:` and `sprint-status.yaml` both still read `review`, so the `review → done` flip has not happened. ⚠️ Still live: `sprint-status.yaml` co-mingles this story's flips with Story 12.1's from the same session ([[project_warden_shared_doc_commit_boundary]]) — ship the feature PR alone and defer the post-merge pass if it cannot be file-isolated.

**What this unblocks:** Story 12.1's AC12 (*"re-run Tool 9 and confirm 0.9805/1.0/1.0"* — **in-sample parity target**, see AC6) is now a **formality** — the numbers are pinned here and just reproduced on demand. 12.1 can bench against a reference that survives a `git clean`. **9.9b is NOT unblocked** (still `blocked` on 12.3); Tool 9 is NOT re-pointed (9.16 owns that).

### File List

Corrected 2026-07-16 by code review: statuses read `staged` and included a file this commit does not contain. Actual delivery = **`e4b9c29`** (7 files), merged **`be0292b`**.

| Status | Path |
|---|---|
| NEW (committed `e4b9c29`) | `apps/tooling/output/zones/v2/manifest.json` |
| NEW (committed `e4b9c29`) | `apps/tooling/output/zones/v2/hud_version_detection.json` |
| NEW (committed `e4b9c29`) | `apps/tooling/output/zones/v2/in_match_detection.json` |
| NEW (committed `e4b9c29`) | `apps/tooling/output/zones/v2/minimap_identification.json` |
| NEW (committed `e4b9c29`) | `apps/tooling/output/zones/v2/minimap_identification.json.bak` (AC0a — pre-existing file, now tracked; content untouched) |
| MODIFIED (committed `e4b9c29`) | `apps/tooling/output/zones/v2/_SCAFFOLD_README.md` (AC7 — de-staled; further corrected by code review) |
| MODIFIED (committed `e4b9c29`) | `_bmad-output/implementation-artifacts/9-15-pilot-zone-set-for-engine-poc.md` (this file) |
| ~~MODIFIED~~ **NOT IN THIS COMMIT** | `_bmad-output/sprint-status.yaml` — the flips shipped **separately as `79fa831`**, not as part of `e4b9c29`. Listed here in error. |

**Added post-merge by code review (2026-07-16), NOT part of `e4b9c29`:**

| Status | Path |
|---|---|
| NEW | `apps/tooling/tests/test_zone_fragments_v2.py` — the fragments→config regression guard (review decisions D1/D4/D5). **Reverses AC0b Option A, AC8's `tests/` fence, and AC9's `204` baseline (now 208).** Ships as a follow-up commit. |

**Not modified (AC8 fence):** no file under `contracts/`, `apps/tooling/tools/`, `apps/tooling/utils/`, `apps/tooling/tests/`, `apps/mobile/`, `apps/web/`; no manifest; no dependency.
**Not committed (gitignored, correctly):** `apps/tooling/output/map_configs/map_config.v2.json` — now genuinely regenerable via `uv run python tools/map_config_emitter.py --zones-dir output/zones/v2`.

### Review Findings

`/bmad-code-review` 2026-07-16 (claude-opus-4-8[1m]). Three parallel layers (Blind Hunter / Edge Case Hunter / Acceptance Auditor) + independent mechanical re-verification of every data claim. **5 decision-needed, 5 patch, 4 deferred, 2 dismissed.**

**🟢 Independently re-verified as genuinely met — the data is sound.** Re-ran the unmodified emitter to a throwaway dir: exit 0, summary `10 / 3 / 13 map(s), 121 total zone(s)`, and **`a == b` → True (62476 B both)** against the live config. Every fragment `==` its config section (all 6 keys, no uncovered key). `.bak` = 0 zones at `h_tol=180` vs the live fragment's **65**, and `.bak == map_config.v2.json.bak["minimap_identification"]` → **True** — the pre-tuning claim is dispositive, and the *right* artifact was committed as source of truth. All 5 fragments + the `.bak` tracked; `map_config.v2.json` still ignored; `manifest.template.json` survived. pytest **204 passed, 0 failures**. AC1/AC2/AC3/AC4/AC5/AC8/AC9 and all three AC0 verdicts hold. **AC1's "zero hand-editing" is confirmed mechanically: zero non-HSV drift across all 121 zones.**

> ### ✅ Decisions resolved 2026-07-16 (Stephane) — D1, D4, D5 collapsed into one guard; D2 escalated into 12.1
>
> **D1 + D4 + D5 → RESOLVED by a single new test: [`apps/tooling/tests/test_zone_fragments_v2.py`](../../apps/tooling/tests/test_zone_fragments_v2.py).** It runs the unmodified emitter against the committed fragments and asserts an **LF-normalized SHA256** (`eb33f1ee…`, over 59987 B) plus the 10/3/13/121 shape. One file, three decisions:
> - **D1** — AC2 is now re-provable on any machine, forever. The vanished comparison target is reduced to 32 bytes that survive a `git clean`. *(Declined: committing the 58 KB `map_config.v2.json.bak` — marginal forensics once the digest is pinned and the fragment `.bak` is tracked.)*
> - **D4** — the fragments→config invariant is enforced. **Proven to bite:** mutating one scalar (`artefact_z00` `h_tol` 11→10, 1 of 121 zones) fails the digest test while the shape tests still pass.
> - **D5** — LF-normalizing the digest makes the gate platform-independent **without** a `.gitattributes` renormalization sweep. The CRLF/LF asymmetry remains (Windows 62476 B / Linux 59987 B) but no longer gates anything.
>
> **⚠️ This reverses three of 9.15's own ACs and they need amending:** **AC0b** (Option A "throwaway — no test file"), **AC8** (fence: *"no file under `apps/tooling/tests/`"*), and **AC9** (baseline `204` → **208 passed, 0 regressions**). 9.15 is already merged, so this lands as a **follow-up commit**, not part of its delivery. The reasoning that failed: *"adds no test because it adds no code"* — it added no code but it **did** add an invariant.
>
> **D2 → ESCALATED, not fixed.** Data is untouchable here (a zone-value edit breaks AC1/AC2 and the new guard). Instead the CPU's *behaviour* is now binding on the shader as **[12-1 AC13b](12-1-pc-poc-gpu-megashader-bench.md)** — *"the shader MUST IGNORE `minimap_identification.roi`"* — filed under AC13 (*"Tool 9 is the gate"*) with the full evidence chain. 12.1's *"caveat — not to fix"* note was amended to say it was underrated, and its AC16 baseline moved 204 → 208. The data fix stays with 9.9b.
>
> **D3 → RESOLVED, Option (a): label the numbers *in-sample / parity-reference only*.** Applied at **all six** sites the numbers travel to, so the caveat cannot separate from the figure: AC6's table (source of the claim, with the full reasoning), the Completion Notes table, the "Why This Story Changed Shape" asset table, the "What this unblocks" note, [`_SCAFFOLD_README.md`](../../apps/tooling/output/zones/v2/_SCAFFOLD_README.md) (the copy nearest the data), and **[12-1 AC12](12-1-pc-poc-gpu-megashader-bench.md)** (the copy that gets *used*). Framing: the numbers are **correct and unchanged** — 69 of 121 zones were tuned against this corpus and there is no holdout, so `1.000` ×2 is a fit to its own training data, not proof of generalization. That is **fine for 12.1**, whose question is GPU-vs-CPU frame parity, and the 12.1 label ties it to AC14's existing "a PC number is never a mobile number" discipline as its accuracy-side analogue. **Generalization stays 9.9b's job** (its AC2 certitude + zero-overlap gate). *(Declined: (b) cut a holdout — that is 9.9b's scope and would re-open a merged story.)*

- [x] **[Review][Decision] Every "PROVEN" claim rests on a gitignored artifact — the proofs cannot survive the `git clean` this story exists to survive.** AC2's comparison target (`map_configs/map_config.v2.json`), AC6's corpus (`output/labeled/`, 2666 PNGs) and the `.bak`'s *"dispositive proof"* (`map_configs/map_config.v2.json.bak`) are **all three gitignored and none is in this commit**. A fresh clone can regenerate the config but can never re-verify byte-identity, re-run the baseline, or re-confirm that the `.bak` is pre-tuning. Sharpest form: AC0a commits the `.bak` *"for the audit trail"*, but the `.bak` is merely **split out of** `map_config.v2.json.bak` — so the story **preserves the derivative and leaves the original it is evidence of to the next `git clean`**. The audit-trail argument argues for committing the other file. Options: (a) also commit `map_config.v2.json.bak` (58 KB, closes the forensic gap); (b) commit an expected-hash/expected-config fixture so AC2 is re-provable; (c) accept as one-machine proofs and record it. `[blind+edge]`
- [x] **[Review][Decision] `minimap_identification.roi` is a stray copy of `atlantis_z10`'s rect — inert today, but a live trap for 12.1.** `roi = {"name":"minimap","x":63,"y":922,"width":3,"height":5}` is **byte-identical to `atlantis_z10`**; **120 of 121 zones fall outside it** (zone range x 8–606, y 741–1061 vs an ROI spanning x 63–66, y 922–927) — the only zone inside is the one it was copied from. Verified why this scores 1.0 anyway: `minimap_roi` is parsed into a dataclass field at [roi_detection_tester.py:440](../../apps/tooling/tools/roi_detection_tester.py#L440) and **never read** — the field is dead in the CPU path. That is exactly the danger: **12.1 is about to build a GPU mega-shader from this config, and a shader that honours `roi` semantics would crop away 120/121 zones and diverge catastrophically from a CPU baseline that silently ignores it.** The story defers it as *"a question for 12.1/9.9b"* and [12-1:233](12-1-pc-poc-gpu-megashader-bench.md#L233) files it as a *"data-quality caveat (not to fix)"* — both underrate it. Same bucket: `id: "test"`. Cannot be fixed here (a zone-value edit breaks AC1/AC2), so the call is how loudly to hand it to 12.1. `[blind, verified+extended in review]`
- [x] **[Review][Decision] The pinned baseline is an in-sample fit and nothing says so.** **RESOLVED 2026-07-16 — Option (a) applied at all 6 sites (see the resolution block above).** The low-sat decision *"moved map-ID 0.973 → 1.000"* tuned **69 of 121 zones against this corpus**; AC6 then pins `map_id 1.0` (2286/2286) and `in_match 1.0` (2666/2666) **measured on that same corpus** as *"the CPU accuracy baseline"*. No holdout, no split, no mention of either in 441 lines. `in_match` reaches 1.0 on 2666 frames using three patches of 3×1/3×2 px, all `h_tol=180`, `s_center` 6/7/7 — i.e. "bright and grey". Partially mitigated (the story is explicit that REL-006 floors are **not** gated here, and for 12.1's actual use — GPU-vs-CPU frame parity — in-sample-ness is irrelevant). But this file is *"the only durable record"*, and a bare `1.0` in it will be read as generalization. Options: (a) label the three numbers **in-sample / parity-reference only**; (b) cut a holdout under 9.9b; (c) accept. `[blind]`
- [x] **[Review][Decision] The fragments→config invariant is now load-bearing and nothing enforces it.** AC9 reasons *"this story adds no test file **because it adds no code**"* — but it adds an **invariant**. The AC2 round-trip was a throwaway script (AC0b Option A). A future `zone_picker` session, a merge, or a hand-edit can silently break regenerability and no gate will notice. AC0b Option A was your explicit call, so revisiting it is yours: (a) add one pytest that emits from the committed fragments and asserts the shape/counts; (b) accept, unguarded. `[blind]`
- [x] **[Review][Decision] No `.gitattributes` — AC2's byte gate passes only on Windows.** The emitter writes text-mode (`newline=None`) at [map_config_emitter.py:145](../../apps/tooling/tools/map_config_emitter.py#L145); `core.autocrlf=true`, no `.gitattributes` anywhere. Committed artifact = **62476 B / 2489 CRLF**; the same fragments on Linux/macOS emit **59987 B**. The story diagnoses this precisely and then leaves it. Content round-trip is safe on both platforms (`utf-8-sig` + universal newlines collapse CRLF before `json.loads`) and nothing hashes or size-gates the config, so blast radius is the gate itself. Blind notes AC8's fence enumerates code/schema/deps and never mentions `.gitattributes`. Options: (a) add `*.json text eol=lf` **scoped to `output/zones/`** (repo-wide risks renormalization churn); (b) accept as Windows-bound. `[edge+blind]`
- [x] **[Review][Patch] Story file misdescribes its own delivery state — AC11 was executed while marked `[HELD]`** [9-15-pilot-zone-set-for-engine-poc.md:346,421,429-433] — `e4b9c29` + `--no-ff` merge `be0292b` exist and `git status` is clean, yet the file still says *"Git delivery HELD — **nothing committed or merged**"*, *"Fragments are **staged only**"*, and the File List marks all five `NEW (staged)`. Compounding: AC0a records a *"Verified **post-commit**"* check inside a story that claims no commit happened. AC11's substance (Conventional Commits, scope `tooling`, local `--no-ff`) was met — the defect is that the only durable record is wrong about the delivery it records. AC10 is correctly still open (sprint-status and `Status:` both read `review`).
- [x] **[Review][Patch] AC7 items 1–3 landed as annotation, not correction — the false text survives verbatim in the copy-pasteable runbook** [_SCAFFOLD_README.md:66-68,78,89-90,106] — the commit prepended a 42-line corrections block and deleted exactly **one** line. Still present: `:78` *"Fill `manifest.template.json` → **rename** to `manifest.json`"* (the exact line AC7.3 names, and following it deletes a tracked file); `:89-90` *"No .mp4 in repo: `apps/tooling/source/` is absent"*; `:106` *"AC8 — end-to-end smoke (**BLOCKED: no real EVA .mp4 in repo**)"*; `:66-68` the stale census. AC7 says *"now actively misleading — **fix** all five"* and AC1 says *"(AC7 **fixes the README's wording**)"*. Per-item: **1, 2, 3 = stated-not-fixed; 4 and 5 = fully met.** Mitigation is real (banner sits above the runbook, labeled *"Corrections to the stale text below"*).
- [x] **[Review][Patch] AC6 and Dev Notes give directly opposite instructions on corpus drift** [9-15-pilot-zone-set-for-engine-poc.md:171,263] — AC6: *"Do not reason 'the corpus probably drifted' — **it provably has not**"*. Dev Notes, 90 lines later: *"**This is why AC6 says a Tool 9 divergence means the corpus moved, not the config** — and it is **a real possibility, not a formality**."* Dev Notes states the exact inverse of what AC6 says.
- [x] **[Review][Patch] File List names a file this commit does not contain** [9-15-pilot-zone-set-for-engine-poc.md:436] — `_bmad-output/sprint-status.yaml` is listed MODIFIED but is absent from `e4b9c29` (7 files, none of them sprint-status); the flip shipped separately as `79fa831`.
- [x] **[Review][Patch] README census self-contradiction + dangling finding reference** [_SCAFFOLD_README.md:41,68] — the new header says `lobby 296 / score 41 / transition 43` (**380** negatives) while the untouched block below still reads `296+41+44 = **381**`. Separately, Completion Notes cite *"the **Finding-2** conclusion"* but no numbered finding exists in this file.
- [x] **[Review][Defer] `manifest.template.json` hardcodes `hud_version: "v2"` — copying it to scaffold v3 silently overwrites the tuned v2 config** [map_config_emitter.py:144] — the emitter derives the output filename purely from the manifest's `hud_version` and never cross-checks it against the `--zones-dir` basename. Atomic refusal does not catch it (`"v2"` is schema-valid), and the story's own AC2 note flags that *"a successful emit of different content overwrites silently"*. Pre-existing; AC8 fences the emitter. — deferred, pre-existing
- [x] **[Review][Defer] `score_screen_duration_ms: 15000` ships as source of truth carrying no in-band marker of its unverifiability** [manifest.json:7] — admitted UNVERIFIED with unknown provenance, and Option B is unachievable (needs ≥5 captures, 4 exist). JSON has no comments, so the caveat lives only in a story file in a different tree; the next reader of `manifest.json` sees a confident round number. AC0c Option A was the accepted call. — deferred, pre-existing
- [x] **[Review][Defer] Four `s_tol`-only zones are unexplained by the story's own narrative** [minimap_identification.json] — verified: of the 69 zones differing from the `.bak`, **65 are `h_tol`-only and 4 are `s_tol`-only**, all on `the_cliff` (`the_cliff_z03/z04` `10→14`, `z05` `9→13`, `z06` `12→16`) — a uniform **+4** bump. The whole `.bak`-is-pre-tuning argument rests on the `h_tol=180` decision, which explains 65 of 69. The remaining 4 are a magic delta inside the artifact being blessed as source of truth. Disclosed by the story (*"only h_tol/s_tol differ, on 69 zones"*) but never explained. Pre-existing tuning artifact, not caused by this change. — deferred, pre-existing
- [x] **[Review][Defer] All five committed JSON files lack a trailing newline** [output/zones/v2/*.json] — a consequence of `json.dump(value, f, indent=2)`; every future diff of these tracked files will carry a spurious last-line change, in a story that justifies `indent=2` specifically as *"match the emitter **for clean diffs**"*. Defensible (it does match the emitter byte-for-byte) and safely fixable (fragment whitespace cannot affect the emitted config). — deferred, pre-existing

**Dismissed as noise (2):** (1) Blind Hunter's *"AC4 is `[x]` but nothing was committed"* — an artifact of its blindness; the commit did land, so AC4/AC5 are genuinely met, and the stale prose is captured in the Patch above. (2) *"The `manifest.template.json` sentinel does not die"* — AC0c's *"dies with the rename either way"* clause is indeed wrong reasoning (AC1 forbids the rename), but the outcome is inert: [zone_picker/fragments.py:186-189](../../apps/tooling/tools/zone_picker/fragments.py#L186-L189) and the emitter read four **exact** names, so the template can never be picked over `manifest.json`.

**Verified-and-clean (no finding):** `.gitignore` negation holds for every committed path incl. the `.bak` (`git check-ignore -v --no-index`); no glob reaches the `.bak` (config globs are `map_config.*.json` / `map_config.v*.json`, both `.json`-suffixed); `schema_version` correctly absent and injected at [map_config_emitter.py:92](../../apps/tooling/tools/map_config_emitter.py#L92); `zone_picker`'s `_ordered_maps` re-order is a **no-op** against the committed fragment, so a future picker session won't produce a spurious diff; both config consumers guard the empty-glob fresh-clone path ([roi_detection_tester.py:137](../../apps/tooling/tools/roi_detection_tester.py#L137), [video_test.py:191](../../apps/tooling/tools/video_test.py#L191)).
