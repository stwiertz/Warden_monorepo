# Story 9.10: PRD/Architecture Editorial Pass for ROI+HSV Pivot

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane** (post-9.9b, holding the unified-schema toolchain on `main` plus empirically-measured per-classifier accuracy floors),
I want **the forward-facing prose in `prd.md`, `architecture.md`, and `epics-and-stories.md` scrubbed of the superseded pHash / `oneOf` / v1-v2-branching framing and re-anchored to the shipped ROI+HSV-band unified-schema reality — with the measured accuracy floors from Story 9.9b cited where the docs make accuracy claims — WITHOUT rewriting any frozen historical-traceability record (cancelled-story ACs, the SUPERSEDED 9.9a block, the preserved original 9.9 stub)**,
so that **the next engineer (or future Stephane) reading the PRD/architecture/epics no longer encounters detection-pipeline prose that contradicts the code on disk, the documents describe one detection method / one config shape / multiple HUD versions, and the audit trail of *why* the pivot happened stays intact in the deliberately-frozen historical sections.**

**Strategic context.** This is a **pure documentation-editorial** story — zero code, zero schema, zero tests. It is the *last* story in the new-HUD initiative's documentation debt: Stories 9.9c (schema unified, `done` — commit `9b9d4af`), 9.11–9.14 (toolchain consolidation), and 9.9b (empirical zone population + measured floors) change the *reality*; this story makes the *planning docs* match it. The work is surgical text editing across three large markdown files, governed by a hard scope boundary: **forward-facing prose is in-scope; historical-traceability records are frozen.** Crossing that boundary destroys the audit trail that explains the pivot. Full pivot rationale lives in [`_bmad-output/sprint-change-proposal-2026-05-15.md`](../sprint-change-proposal-2026-05-15.md) and the Epic 9 charter amendments ([`epics-and-stories.md:2616-2628`](../epics-and-stories.md#L2616)).

**Why this story exists separately.** Extracted 2026-05-15 from the cancelled Story 9.9 stub's AC4 (the "editorial cleanup" tail of the original monolithic 9.9), then scope-expanded the same day by `/bmad-correct-course` to also scrub `oneOf` / v1-v2 prose introduced by the (now-superseded) 9.9a design. Kept standalone because docs-editorial work has a different review surface than code and a different dependency gate (it can only cite accuracy numbers that 9.9b has actually produced).

**The two-cohort structure (read this before estimating).** The deliverable splits cleanly into two cohorts with different unblock conditions:

- **Cohort A — Prose scrub (UNBLOCKED NOW).** Re-anchoring stale pHash/`oneOf`/v1-v2 framing and the `map_config_generator.py → map_config_emitter.py` rename in *forward-facing* prose. The canonical correct framing already exists on `main` (9.9c is `done`). This cohort does **not** depend on 9.9b.
- **Cohort B — Accuracy-floor citations (GATED on 9.9b).** Anywhere the docs assert a map-identification accuracy number, cite 9.9b's *measured* per-classifier floors instead of the legacy "≥95%" placeholder framing. This cohort **cannot** complete until Story 9.9b reports floors (it is `ready-for-dev`, itself blocked on 9.9c→9.11→9.12/9.14→9.13).

Rollout decision (single-PR-after-9.9b vs. two-PR Cohort-A-now-then-Cohort-B) is **AC0**, decided at dev-story kickoff. Recommended default: **wait for 9.9b and ship both cohorts in one PR** (the scope-expansion explicitly anchors 9.10 to 9.9b's numbers; a Cohort-A-only PR risks a second editorial pass churning the same paragraphs twice). Cohort A is documented as independently runnable only as a contingency if the 9.9b chain slips badly and the stale prose becomes actively misleading to in-flight work.

**V1 posture.** Out-of-V1-scope at the deliverable level (docs cleanup for a post-V1 pivot; V1 itself ships the legacy pHash config per [`9-9b`](9-9b-iterative-zone-population-for-shipping-configs.md) V1-posture). V1-safe at the code level — **no code, schema, test, or runtime artifact is touched by this story.** Only three planning markdown files + this story file + `sprint-status.yaml`.

**Type:** Documentation-editorial story. Track C (tooling-docs). No spike-or-split flag. Fits-in-one-sprint once unblocked (~1 day of careful text editing + self-review). Dev-story kickoff held until 9.9b reports floors (per AC0 default). Single-PR delivery + tiny post-merge follow-up for the sprint-status `review → done` flip (Two-PR pattern, [[feedback_two_pr_docs_execution]]; local `git merge --no-ff` delivery per the 9.9c precedent — `gh` is not authenticatable non-interactively in this environment).

## Acceptance Criteria

> **AC checkbox convention** ([[feedback_ac_checkbox_tighten]]): every AC below is held `[ ]` at create-story time (no work performed). At dev-story completion, scrub/verify ACs flip `[x]`; ACs whose endpoint depends on **post-merge actions** (sprint-status `review → done`, PR merge) or on **9.9b not-yet-reported data** stay `[ ]` until that condition is met. Annotations below mark which is which.

0. [ ] **AC0 — Rollout decision recorded (decided at dev-story kickoff).** Choose and record in the Change Log one of:
   - **Option A (recommended default): one PR after 9.9b.** Hold dev-story kickoff until Story 9.9b is `done` on `main` with its iteration-log accuracy table populated. Ship Cohort A + Cohort B in a single editorial PR. Rationale: avoids editing the same paragraphs twice; the scope-expansion explicitly anchors this story to 9.9b's empirical numbers.
   - **Option B: two PRs (Cohort A now, Cohort B after 9.9b).** Only if the 9.9b dep chain has slipped far enough that the stale `oneOf`/pHash prose is actively misleading active work. PR 1 ships Cohort A (prose scrub, no accuracy numbers); PR 2 ships Cohort B (accuracy-floor citations) once 9.9b reports. Each PR carries its own Two-PR post-merge follow-up.
   - Record the chosen option, the 9.9b status at decision time, and (if Option A) the 9.9b merge SHA + accuracy-table location.

1. [ ] **AC1 — Scope-boundary attestation written before any edit.** Before touching any file, the dev writes a short "Scope Boundary" subsection in this story's Completion Notes enumerating, by `file:line-range`, every region classified as **FROZEN (historical traceability — DO NOT EDIT)** vs **IN-SCOPE (forward-facing prose)**, using the Editorial Target Manifest (Dev Notes) as the starting point and *verifying current line numbers* (the docs may have shifted since this story was written). FROZEN regions are non-negotiable:
   - Cancelled-story blocks in `epics-and-stories.md`: Story 9.1, 9.2, 9.3, 9.4 sections (their ACs/summaries are the frozen record of *why* they were cancelled).
   - The SUPERSEDED Story 9.9a block in `epics-and-stories.md` (rewriting it erases the rationale for the 9.9c supersession).
   - The cancelled Story 9.9 stub's preserved "original stub" / pre-split content in `epics-and-stories.md` (kept verbatim for traceability per [`sprint-status.yaml:183`](../sprint-status.yaml#L183)).
   - All inline history comments in `sprint-status.yaml` (this story does not edit sprint-status content beyond the AC11 lifecycle key + `last_updated`).
   - The Brownfield-Item-7-as-shipped `[RESOLVED]` framing in `architecture.md` where it documents *what V1 actually ships* (V1 genuinely ships the legacy pHash `map_config.json` with `schema_version: 1`; that is not stale, it is the V1 reality).

2. [ ] **AC2 — PRD named targets re-anchored (Cohort A).** In [`prd.md`](../prd.md):
   - `tooling-HASH-001` ([prd.md:955](../prd.md#L955)) and `tooling-HASH-002` ([prd.md:956](../prd.md#L956)): reframe per the AC4 decision (see AC4) — minimum change is the `map_config_generator` → `map_config_emitter` tool-name correction; full reframe to ROI+HSV/unified-schema is AC4-gated.
   - `mobile-AUTO-SLICE-002` ([prd.md:868](../prd.md#L868)): "on-device perceptual hashing against `map_config.json`" → reframed to ROI+HSV-band zone identification against the per-HUD `map_config.<hud_version>.json`, preserving the `*(J1, J6) (load-bearing on OpenCV JSI binding)*` traceability tag and the `unknown`-fallback contract of `mobile-AUTO-SLICE-003` ([prd.md:869](../prd.md#L869)) — 003's wording stays unless 002's reframe makes it inconsistent.
   - Every reframed sentence still parses as a valid requirement statement (subject + capability + traceability tag); no dangling `*(J10)*` / `*(Section …)*` citations left orphaned.

3. [ ] **AC3 — Architecture named targets re-anchored (Cohort A).** In [`architecture.md`](../architecture.md):
   - The `mapIdentifier.ts` source-tree line ([architecture.md:1505](../architecture.md#L1505)): `pHash matcher against map_config` → an ROI+HSV-band-identification description consistent with the unified schema (e.g. `ROI+HSV-band map identifier (per-HUD map_config)`). Column alignment of the surrounding ASCII tree is preserved.
   - The `mobile-AUTO-SLICE-002/003` traceability line ([architecture.md:1691](../architecture.md#L1691)): `(pHash matching; `unknown` fallback)` → `(ROI+HSV-band zone matching; `unknown` fallback)` or equivalent; the `mobile-AUTO-SLICE-002/003` ID reference and the surrounding bullet structure are preserved.
   - Forward-facing tool-name references in the source-tree + traceability sections (`map_config_generator.py` where it labels the *current/shipping* emitter — e.g. [architecture.md:1595](../architecture.md#L1595), [architecture.md:1765](../architecture.md#L1765)) → `map_config_emitter.py`. **Do NOT** touch the Brownfield-Item-7 `[RESOLVED]` narrative where it documents the V1-as-shipped path (FROZEN per AC1) — only correct the tool name in forward-looking structural references, and only if the name is genuinely wrong for the post-9.9c reality.
   - Confirm-and-record: the architecture.md scan found **zero** `oneOf` / v1-v2 schema-branching prose (the document predates the 9.9a branching framing). AC3 includes an explicit "verified: no `oneOf`/v1-v2 prose in architecture.md" line in Completion Notes — a *negative* result is still a required deliverable of the scope expansion.

4. [ ] **AC4 — PRD V1-tooling-requirement treatment decided + applied (decided at dev-story kickoff; recommended default = annotate, not destructively reframe).** `tooling-HASH-001/002`, and the broader V1 tooling-requirement prose (`tooling-LABEL-001/002` [prd.md:950-951](../prd.md#L950), `tooling-VALIDATE-001/002` [prd.md:960-961](../prd.md#L960), MVP-scope tool list [prd.md:266](../prd.md#L266), Section 7 tooling overview [prd.md:745](../prd.md#L745), J10 capabilities [prd.md:463](../prd.md#L463), maps-reconciliation [prd.md:596](../prd.md#L596)) describe the **V1-as-shipped** pHash tooling. V1 genuinely ships pHash (per 9.9b V1 posture). Choose at kickoff:
   - **Option A (recommended default): annotate, don't destroy.** Leave the V1-accurate requirement text intact; append a forward-pointer note (e.g. "*Post-V1: superseded by the ROI+HSV-band unified-schema pipeline — see Epic 9 charter amendment 2026-05-15 and Story 9.9c.*") so the requirement still documents V1 reality *and* signals the pivot. Lowest-risk; preserves V1 traceability.
   - **Option B: full reframe.** Rewrite the requirements to the ROI+HSV/unified-schema reality, accepting that the PRD then no longer documents what V1 actually shipped. Only if Stephane explicitly wants the PRD to be forward-state-only.
   - The tool-name correction (`map_config_generator` → `map_config_emitter`) applies under **either** option (it is a factual rename, not a reframe). Record the chosen option in the Change Log; apply consistently across all the FR IDs listed above.

5. [ ] **AC5 — `epics-and-stories.md` forward-facing prose scrubbed (Cohort A), FROZEN regions untouched.** In [`epics-and-stories.md`](../epics-and-stories.md):
   - Epic 9 charter **Goal** line ([epics-and-stories.md:2618](../epics-and-stories.md#L2618)): `enable a future ROI/HSV-band-keyed map_config.json v2` — the "future … v2" framing is stale (the unified shape is shipped, not a future "v2"). Reframe to the unified-schema reality. The two charter **amendment blocks** ([epics-and-stories.md:2620](../epics-and-stories.md#L2620) 2026-05-14, [epics-and-stories.md:2622-2628](../epics-and-stories.md#L2622) 2026-05-15) already describe the unified shape correctly — verify they are consistent post-edit; do not rewrite them (they are themselves the historical amendment record).
   - The Story 9.10 self-description block ([epics-and-stories.md:2767-2770](../epics-and-stories.md#L2767)): update its `**Status:**` line to reflect completion lifecycle if appropriate; the summary may be tightened but its scope-expansion sentence is the record of *this story's* mandate — keep it.
   - The cancelled Story 9.9 stub's forward-pointing follow-up lines that flag *this* editorial work (the "PRD `tooling-HASH-001/002` … needs editorial update" / "Architecture `mapIdentifier.ts` … same" follow-up bullets near [epics-and-stories.md:2823-2824](../epics-and-stories.md#L2823)): mark them resolved-by-9.10 (or strike, per the doc's convention for resolved follow-ups) — these are the *only* lines inside the 9.9-stub region that are in-scope; the rest of that stub is FROZEN per AC1.
   - **Every other pHash/`oneOf`/v1-v2/4-class-cascade/`map_config_generator.py` hit inside the cancelled 9.1/9.2/9.3/9.4 blocks, the SUPERSEDED 9.9a block, and the preserved original-9.9-stub content is FROZEN — DO NOT EDIT.** The subagent inventory flagged ~40 such hits; they are deliberate historical record, not debt.

6. [ ] **AC6 — Accuracy-claim citations re-anchored to 9.9b measured floors (Cohort B; GATED on 9.9b `done`).** Anywhere the in-scope forward-facing prose asserts a map-identification accuracy figure, cite 9.9b's *measured* per-classifier floors (HUD-version / binary in-match / per-map ID) from 9.9b's iteration-log table, not a bare legacy placeholder. Specifically:
   - PRD `REL-006` ([prd.md:1042](../prd.md#L1042)) "Map identification accuracy ≥ 95% on a held-out test set" — retained as the *requirement floor*, but if 9.10's editorial pass adds any "as-measured" prose it cites 9.9b's actual per-HUD-version numbers + the report path under `apps/tooling/output/roi_detection_tests/v<hud>/<timestamp>/`.
   - Any architecture/epics prose that the pivot reframe touches and that makes an accuracy claim cites the same 9.9b source.
   - **If 9.9b is not `done` at dev-story execution time:** this AC holds `[ ]`, Cohort B is deferred per AC0 Option B, and the deferral is flagged in the Change Log. The story does NOT invent placeholder numbers.

7. [ ] **AC7 — No code/schema/test/runtime artifact touched.** `git diff main --stat` shows changes **only** in: `_bmad-output/prd.md`, `_bmad-output/architecture.md`, `_bmad-output/epics-and-stories.md`, `_bmad-output/implementation-artifacts/9-10-prd-architecture-editorial-pass-roi-hsv-pivot.md`, `_bmad-output/sprint-status.yaml`. If `git diff` shows any change under `contracts/`, `apps/`, `packages/`, `_bmad/`, or any `*.py`/`*.ts`/`*.json` schema/test file → STOP; scope violated. No test run is required (no code changed); the green-suite baseline is inherited from `main`.

8. [ ] **AC8 — Internal cross-reference integrity preserved.** Every edited line that contained a `file:line` anchor, an FR/NFR ID, a `*(J…)*`/`*(Section …)*` citation, a `[[memory-link]]`, or a markdown link is left with that reference still valid (IDs not renamed, anchors not broken). If a reframe changes a line such that another doc's `architecture.md#L1505`-style anchor would point at the wrong content, note the now-stale inbound anchor in Completion Notes (do not chase cross-file anchor renumbering — flag only).

9. [ ] **AC9 — Sprint-status entry + lifecycle flip.** [`sprint-status.yaml`](../sprint-status.yaml) `9-10-prd-architecture-editorial-pass-roi-hsv-pivot` flows `ready-for-dev → in-progress → review → done`. The `review → done` flip ships in the tiny post-merge follow-up per [[feedback_two_pr_docs_execution]]. `last_updated` header bumped in both the main commit and the post-merge follow-up. Epic 9 stays `in-progress` (9.10 is not the last Epic 9 story; 9.9b and the 9.11–9.14 chain remain). **HELD `[ ]`** until the post-merge follow-up lands.

10. [ ] **AC10 — Single-PR delivery + Two-PR follow-up.** The editorial change ships in one PR titled `docs: ROI+HSV editorial pass — PRD/architecture/epics (Story 9.10)` (subject lowercased on the commit; capitalized in PR title). Branch `story-9-10-roi-hsv-editorial` off `main`. If `gh` cannot authenticate non-interactively (per the 9.9c precedent), deliver as a local `git merge --no-ff story-9-10-roi-hsv-editorial → main` and record the merge SHA + push range in the Change Log. PR/commit body links: this story file; [`sprint-change-proposal-2026-05-15.md`](../sprint-change-proposal-2026-05-15.md); Story 9.9c's story file (the schema-of-record); Story 9.9b's story file (accuracy-floor source, if Cohort B included). After merge: post-merge follow-up branch `story-9-10-postmerge` flips sprint-status `review → done` + flips AC9/AC10 boxes here. **HELD `[ ]`** until the follow-up lands.

## Tasks / Subtasks

> **Implementation order:** AC0 (rollout decision) and AC1 (scope-boundary attestation) gate everything — do not edit a single character until both are recorded. Cohort A (Tasks 3–5) is the bulk of the work. Cohort B (Task 6) only runs if 9.9b has reported (per AC0).

- [ ] **Task 1: Pre-flight + rollout decision (AC: 0)**
  - [ ] Pull `main`. Confirm 9.9c is `done` on `main` (commit `9b9d4af` per [`sprint-status.yaml:187`](../sprint-status.yaml#L187)) — this is the schema-of-record that defines the *correct* target framing.
  - [ ] Check 9.9b status in `sprint-status.yaml`. Record it. Decide AC0 Option A (one PR after 9.9b — default) vs Option B (two PRs). Write the decision + rationale + 9.9b status/SHA into this story's Change Log.
  - [ ] If Option A and 9.9b is not yet `done`: HALT dev-story here; the story stays `ready-for-dev`/parked until 9.9b reports. (Spec is complete; execution is gated. This is the expected state for some time — the 9.9b chain is multi-sprint.)

- [ ] **Task 2: Scope-boundary attestation (AC: 1)**
  - [ ] Re-grep all three docs for the current line numbers of every region in the Editorial Target Manifest (Dev Notes). The line numbers in this story are as-of-2026-05-16 and **will drift**.
  - [ ] Write the "Scope Boundary" subsection in Completion Notes: a two-column `file:line-range → FROZEN | IN-SCOPE` table. Every cancelled-story block, the SUPERSEDED 9.9a block, the preserved 9.9-stub content, sprint-status history comments, and the Brownfield-Item-7-as-shipped narrative are FROZEN. Get this signed off (self-review) before Task 3.

- [ ] **Task 3: PRD editorial pass (AC: 2, 4, 8)**
  - [ ] Apply the AC4 decision (annotate vs reframe) to `tooling-HASH-001/002` + the broader V1 tooling-requirement set. Default = annotate with a post-V1 forward-pointer; always apply the `map_config_generator → map_config_emitter` factual rename.
  - [ ] Reframe `mobile-AUTO-SLICE-002` per AC2; verify `mobile-AUTO-SLICE-003` stays consistent.
  - [ ] Verify every edited requirement still parses (subject + capability + traceability tag intact). No orphaned `*(J…)*` citations.

- [ ] **Task 4: Architecture editorial pass (AC: 3, 8)**
  - [ ] Edit the `mapIdentifier.ts` source-tree line (≈[1505](../architecture.md#L1505)) and the `mobile-AUTO-SLICE-002/003` traceability line (≈[1691](../architecture.md#L1691)) per AC3. Preserve ASCII-tree column alignment and bullet structure.
  - [ ] Correct forward-looking `map_config_generator.py → map_config_emitter.py` structural references (source-tree ≈[1595](../architecture.md#L1595), traceability ≈[1765](../architecture.md#L1765)); leave the Brownfield-Item-7 V1-as-shipped narrative FROZEN.
  - [ ] Record the explicit negative result: "verified — no `oneOf`/v1-v2 schema-branching prose present in architecture.md" in Completion Notes (AC3 deliverable).

- [ ] **Task 5: epics-and-stories.md editorial pass (AC: 5, 8)**
  - [ ] Reframe the Epic 9 charter **Goal** line (≈[2618](../epics-and-stories.md#L2618)) off the "future … v2" framing onto the unified-schema reality. Leave both charter **amendment blocks** as-is (verify consistency only).
  - [ ] Mark the 9.9-stub forward-pointing "needs editorial update" follow-up bullets (≈[2823-2824](../epics-and-stories.md#L2823)) resolved-by-9.10. These are the ONLY in-scope lines inside the 9.9-stub region.
  - [ ] Update the Story 9.10 self-description `**Status:**` line if appropriate; keep its scope-expansion sentence.
  - [ ] Re-verify: nothing inside the cancelled 9.1/9.2/9.3/9.4 blocks, the SUPERSEDED 9.9a block, or the preserved original-9.9-stub content was edited (diff-audit against the Task 2 FROZEN list).

- [ ] **Task 6: Accuracy-floor citation pass (AC: 6) — Cohort B; only if 9.9b is `done`**
  - [ ] Pull 9.9b's iteration-log accuracy table (per-HUD HUD-version / binary in-match / per-map ID floors) + the Tool-9-refit report directory path.
  - [ ] Where in-scope reframed prose makes an accuracy claim, cite the measured numbers + the report path. Keep PRD `REL-006`'s requirement floor (≥95%) as a requirement; cite as-measured numbers separately.
  - [ ] If 9.9b not `done`: skip; hold AC6 `[ ]`; flag the deferral in the Change Log per AC0 Option B.

- [ ] **Task 7: Self-review + scope-violation audit (AC: 7, 8)**
  - [ ] `git diff main --stat` — confirm ONLY the 5 allowed files changed. Any `apps/`/`contracts/`/`packages/`/`*.py`/`*.ts` change → STOP, revert, the change belongs elsewhere.
  - [ ] `git diff main` full read-through against the Task 2 FROZEN list — zero edits inside any FROZEN region.
  - [ ] Cross-reference integrity check (AC8): FR/NFR IDs unchanged, `*(J…)*` tags intact, markdown/`[[memory]]` links valid, inbound stale anchors flagged (not chased).

- [ ] **Task 8: PR + sprint-status flips (AC: 9, 10)** — runs once
  - [ ] Branch `story-9-10-roi-hsv-editorial` off `main`. Stage: 3 docs + this story file (Completion Notes + Scope Boundary + Change Log + File List) + `sprint-status.yaml` flip `ready-for-dev → in-progress → review` + `last_updated` bump. Commit `docs: ROI+HSV editorial pass — PRD/architecture/epics (Story 9.10)`.
  - [ ] Deliver: open PR if `gh` authenticates; else local `git merge --no-ff → main` + record SHA/push-range (9.9c precedent).
  - [ ] After merge: branch `story-9-10-postmerge` off `main`. Flip sprint-status `review → done` + `last_updated`. Flip AC9/AC10 + Task 8 post-merge sub-boxes `[x]`. Commit `chore: Story 9.10 post-merge follow-up (review -> done)`.

## Dev Notes

### Strategic context — what "correct" looks like (the schema-of-record)

The single source of truth for the *correct* framing is Story 9.9c (`done`, commit `9b9d4af`) and the schema it shipped: [`contracts/map-config.schema.json`](../../contracts/map-config.schema.json). Every reframe in this story must converge on this reality:

- **One detection method:** ROI + HSV-band zone detection. NOT perceptual hashing (pHash), NOT `reference_hash`, NOT Hamming distance.
- **One config shape:** a single unified JSON Schema. NO `oneOf`, NO `discriminator`, NO v1/v2 schema branches, NO dual-emit-path.
- **`schema_version: integer enum [1]`** = the *config-shape* version (a forward-evolution slot). It is **NOT** the detection-method version and **NOT** the HUD version. (This is the single most-confused concept in the stale prose — the old framing used `schema_version` as a v1/v2 detection-method discriminator.)
- **Multiple HUD versions selected at runtime:** top-level `hud_version: string enum ["v1","v2"]`; the runtime picks the matching `map_config.<hud_version>.json` once per session via `hud_version_detection` zones.
- **Game-state is binary:** `in_match_detection: Zone[]` classifies in-match-or-not. Score-screen is **timing-derived** (`score_screen_duration_ms`), NOT a class. Lobby + transition are merged into "not-in-match", NOT differentiated. The old 4-class `{lobby, in_match, score, transition}` cascade is **gone**.
- **Tool rename (factual, landed via 9.9a merge `890fa01`, rewritten by 9.9c):** `apps/tooling/tools/map_config_generator.py` → `apps/tooling/tools/map_config_emitter.py`. It is now fragment-driven (`--zones-dir`), decoupled from `apps/tooling/config/config.yaml`. `hash_comparator.py` no longer co-emits the map config.
- Full per-field schema spec: [`9-9c-schema-unification.md` AC1](9-9c-schema-unification.md). Pivot rationale + 6-step operator workflow: [`sprint-change-proposal-2026-05-15.md`](../sprint-change-proposal-2026-05-15.md).

### THE central anti-pattern / disaster to avoid

**Destroying historical-traceability records while scrubbing stale prose.** The subagent inventories surfaced ~60 stale-prose hits across the three docs. The *majority* are inside deliberately-frozen historical sections. Editing them is a disaster, not a fix:

- **Cancelled stories 9.1 / 9.2 / 9.3 / 9.4** (`epics-and-stories.md`) carry pHash/`schema_version`/tool-name prose *as the record of what was cancelled and why*. Rewriting their ACs to the new reality makes it look like cancelled work was done, and erases the cancellation rationale. **FROZEN.**
- **The SUPERSEDED Story 9.9a block** describes the `oneOf`/v1-v2/dual-emit design *on purpose* — it is the record of what 9.9c superseded and why the supersession was justified. Scrubbing the `oneOf` prose out of the 9.9a block deletes the entire argument for 9.9c's existence. **FROZEN.**
- **The preserved original Story 9.9 stub content** is kept verbatim for traceability per an explicit sprint-status decision ([`sprint-status.yaml:183`](../sprint-status.yaml#L183)). **FROZEN** — except the few forward-pointing "needs editorial update" follow-up bullets that explicitly delegate work to *this* story (those get marked resolved).
- **`architecture.md`'s Brownfield-Item-7 `[RESOLVED]` narrative** documents the V1-as-shipped path. **V1 genuinely ships the legacy pHash `map_config.json` with `schema_version: 1`.** That prose is *accurate for V1*, not stale. The pivot is post-V1. Only correct forward-looking *structural* tool-name references; leave the V1-shipped narrative intact. **FROZEN (as-shipped portions).**

The scope expansion's phrase "scrub any 9.9a-era prose referencing the now-superseded `oneOf`/v1-v2 framing" means **forward-facing** prose that *asserts the current/future state incorrectly* — NOT the historical blocks that *describe the superseded design as history*. When in doubt: if the surrounding section is a cancelled/superseded/preserved-stub block, it is FROZEN. If editing a line would make a historical record *lie about its own history*, do not edit it.

### Other anti-patterns

- **DO NOT touch any code/schema/test artifact.** Zero `.py`, `.ts`, `.json`-schema, test, or `wardentooling.py` edits. If a doc edit seems to "require" a code change to be consistent, the doc is describing a future state — annotate it as future, do not implement anything. (AC7.)
- **DO NOT invent accuracy numbers.** Cohort B cites *measured* 9.9b floors only. If 9.9b hasn't reported, defer Cohort B (AC0 Option B / AC6) — never write a plausible-looking placeholder figure.
- **DO NOT rename FR/NFR IDs.** `tooling-HASH-001`, `mobile-AUTO-SLICE-002`, `REL-006`, `J10` etc. are stable identifiers other docs/anchors point at. Reframe the *prose body*, keep the *ID and its citation tag*. (AC8.)
- **DO NOT chase cross-file anchor renumbering.** Reframing a line may shift `architecture.md#L1505`-style inbound anchors elsewhere. Flag stale inbound anchors in Completion Notes; do not open a renumbering rabbit-hole across the corpus. (AC8.)
- **DO NOT do a blanket pHash purge.** The scope is: (a) the explicitly-named targets, (b) forward-facing `oneOf`/v1-v2 prose, (c) the factual tool rename in forward-looking references. It is *not* "delete every occurrence of the word pHash." V1 ships pHash; cancelled stories document pHash; both are correct in their context.
- **DO NOT break the markdown.** ASCII source-trees in `architecture.md` are column-aligned; preserve alignment. Requirement bullets have a strict `**ID:** prose *(citation)*` shape; preserve it.
- **DO NOT widen scope to "fix" the docs generally.** This is the ROI+HSV pivot editorial pass, not a general copy-edit. Out-of-pivot typos/awkwardness are out of scope.

### Editorial Target Manifest

> Line numbers are **as-of-2026-05-16** and WILL drift — Task 2 re-greps and re-anchors. Grouped by file. **F** = FROZEN (do not edit), **S** = in-scope, **S\*** = in-scope but AC4-decision-gated.

**`_bmad-output/prd.md`** (~1073 lines):

| Line(s) | Content | Class | Action |
|---|---|---|---|
| 955 `tooling-HASH-001` | `hash_comparator` (or `map_config_generator`) … per-map reference hashes | S\* | AC4 decision; always fix tool name |
| 956 `tooling-HASH-002` | emitted `map_config.json` includes `schema_version: 1` + pHash pipeline params | S\* | AC4 decision; `schema_version` meaning note |
| 868 `mobile-AUTO-SLICE-002` | "on-device perceptual hashing against `map_config.json`" | S | Reframe to ROI+HSV-band (AC2) |
| 869 `mobile-AUTO-SLICE-003` | `unknown` fallback below recognition threshold | S | Verify-consistent only |
| 950-951 `tooling-LABEL-001/002` | `frame_labeler` (retired by 9.11) as active capability | S\* | AC4 decision (annotate post-V1) |
| 960-961 `tooling-VALIDATE-001/002` | `hash_validator` pipeline-param reuse | S\* | AC4 decision (annotate post-V1) |
| 266 | MVP-scope 5-tool list (`map_config_generator`, …) | S\* | AC4 decision; tool name |
| 463 | J10 capabilities (`tooling-HASH-COMPARATOR`, `tooling-MAP-CONFIG-EMIT`) | S\* | AC4 decision |
| 596 | maps-reconciliation (legacy `map_config_generator.py` spec stale) | S\* | AC4 decision; tool name |
| 745 | Section 7 tooling overview (old tool names) | S\* | AC4 decision; tool name |
| 1042 `REL-006` | "Map identification accuracy ≥ 95% held-out" | S (Cohort B) | Keep req floor; cite 9.9b measured (AC6) |

**`_bmad-output/architecture.md`** (~2196 lines):

| Line(s) | Content | Class | Action |
|---|---|---|---|
| 1505 | `mapIdentifier.ts  pHash matcher against map_config` | S | Reframe to ROI+HSV (AC3); keep tree alignment |
| 1691 | `mapIdentifier.ts — mobile-AUTO-SLICE-002/003 (pHash matching; unknown fallback)` | S | Reframe to ROI+HSV (AC3) |
| 1595 | source-tree `map_config_generator.py … (writes schema_version: 1 per Item 7)` | S | Tool name → emitter (forward-looking) |
| 1765 | traceability `map_config_generator.py — tooling-HASH-001` | S | Tool name → emitter (forward-looking) |
| 389 | Decision #2 `regenerated by map_config_generator.py` | S | Tool name → emitter (forward-looking) |
| 288, 392, 487-495, 1630, 1948, 2096, 2188 | Brownfield-Item-7 / `schema_version: 1` as-V1-shipped narrative | F | FROZEN — V1 reality, not stale |
| (whole file) | `oneOf` / v1-v2 schema-branching prose | — | **NONE present** — record negative result (AC3) |

**`_bmad-output/epics-and-stories.md`** (~3197 lines):

| Line(s) | Content | Class | Action |
|---|---|---|---|
| 2618 | Epic 9 charter Goal: "enable a *future* ROI/HSV-band-keyed `map_config.json` *v2*" | S | Reframe off "future…v2" (AC5) |
| 2620 | Charter amendment 2026-05-14 block | F | Historical amendment record — verify only |
| 2622-2628 | Charter amendment 2026-05-15 block (already correct) | F | Historical amendment record — verify only |
| 2630-2674 (approx) | Cancelled Story 9.1 / 9.2 / (9.3 / 9.4) blocks | F | FROZEN — cancellation record |
| 9.3 / 9.4 cancelled blocks | pHash regression / jsonschema cancelled ACs | F | FROZEN |
| 9.9a SUPERSEDED block | `oneOf`/v1-v2/dual-emit design-as-history | F | FROZEN — supersession rationale |
| 2742-2766 (approx) | Cancelled 9.9 stub + preserved original-stub content | F | FROZEN (per [`sprint-status.yaml:183`](../sprint-status.yaml#L183)) |
| ~2823-2824 | 9.9-stub forward-pointing "needs editorial update" follow-up bullets | S | Mark resolved-by-9.10 (only in-scope lines in the stub region) |
| 2767-2770 | Story 9.10 self-description block | S | Status line + light tighten; keep scope sentence |
| Story 1.13 ACs (≈1005-1022) | anchor already flipped 9.9a→9.9c (2026-05-15) | F | Verify only — already amended, do not re-edit |

> The exact cancelled-block / SUPERSEDED-block / preserved-stub line ranges MUST be re-derived in Task 2 (they shift). The Task 2 attestation is the authoritative FROZEN map for the dev run; this manifest is the starting point.

### Library / framework requirements

- **None.** No dependencies, no build, no test runner. Pure markdown editing. The only tools needed are file read/edit + `git diff` + grep for line-number re-anchoring. `apps/tooling/pyproject.toml` / `packages/contracts/package.json` are NOT touched and need no verification (no code path).

### Testing standards

- **No automated tests** — this story produces zero code. The "test" is the AC7 scope-violation audit (`git diff main --stat` shows only the 5 allowed files) + the AC1/Task-2 FROZEN-region diff-audit + the AC8 cross-reference integrity check. These are the success criteria.
- **The inherited green-suite baseline is unchanged** — because no code/test/schema file is touched, the `apps/tooling` pytest suite and `pnpm --filter tooling test` remain at their `main` count by construction. Do NOT run them; running them proves nothing this story changed. (If a code file *did* change, that itself is the AC7 failure signal.)
- **Self-review is the review.** Docs-editorial has no executable oracle; the dev's diff-audit against the Task 2 FROZEN map + the cross-reference integrity pass is the quality gate. A second human (Stephane) reviews the PR diff before merge.

### Sprint-fit + dependencies

- **Track C** (tooling-docs). Parallel-safe with all other tracks; independent of the AR-SPIKE.
- **Hard upstream (schema-of-record):** Story 9.9c — `done` on `main` (commit `9b9d4af`, [`sprint-status.yaml:187`](../sprint-status.yaml#L187)). This is what makes Cohort A unblocked: the *correct* framing exists on disk.
- **Hard upstream (Cohort B data):** Story 9.9b (`9-9b-iterative-zone-population-for-shipping-configs`) — `ready-for-dev`, itself blocked on 9.9c→9.11→9.12/9.14→9.13. 9.9b's measured accuracy floors are the only thing AC6/Cohort B can cite. Per AC0 default (Option A), the *whole* story waits for 9.9b to avoid double-editing.
- **Downstream:** none. 9.10 is a documentation terminus; nothing consumes it.
- **Sequencing:** the new-HUD initiative critical path is 9.9c (done) → 9.11 → 9.12/9.14 → 9.13 → 9.9b → **9.10**. 9.10 is effectively the *last* documentation step after the *last* data step.
- **Sprint fit:** **fits-in-one-sprint once unblocked** — ~1 day: ~½ day Cohort A surgical edits + Task-2 attestation, ~¼ day Cohort B citations (if 9.9b reported), ~¼ day self-review/scope-audit/PR. The long pole is *waiting for 9.9b*, not the editing itself.
- **Branch off:** `main`. `story-9-10-roi-hsv-editorial` (main PR), `story-9-10-postmerge` (Two-PR follow-up). Local `--no-ff` merge delivery if `gh` non-interactive auth fails (9.9c precedent — see [`sprint-status.yaml:187`](../sprint-status.yaml#L187)).
- **epic-9 stays `in-progress`** through this story (9.9b + the 9.11–9.14 chain are still open; 9.10 is not the epic terminus).

### Project structure notes

- **Naming:** sprint-status key `9-10-prd-architecture-editorial-pass-roi-hsv-pivot`; story file `_bmad-output/implementation-artifacts/9-10-prd-architecture-editorial-pass-roi-hsv-pivot.md`. Continues the Epic 9 suffix convention.
- **The three target docs live at `_bmad-output/` root**, NOT under `_bmad-output/planning-artifacts/` (the path the BMM config nominally points at — `planning_artifacts: {project-root}/_bmad-output/planning-artifacts`). The actual files are `_bmad-output/prd.md`, `_bmad-output/architecture.md`, `_bmad-output/epics-and-stories.md`. Do not create the `planning-artifacts/` directory or move files; edit in place.
- **Two-PR + local-merge delivery** per [[feedback_two_pr_docs_execution]] and the 9.9c precedent (recent commits `ae1aa4e`/`0854701` `chore: story 9.9c post-merge follow-up (review -> done)` show the exact follow-up shape).
- **AC checkbox discipline** per [[feedback_ac_checkbox_tighten]]: post-merge-/9.9b-dependent ACs (AC6 if Cohort B deferred, AC9, AC10) stay `[ ]` past dev-completion.
- **The scope expansion is itself recorded** in [`sprint-status.yaml:186`](../sprint-status.yaml#L186) and the Epic 9 charter amendment 2026-05-15 ([epics-and-stories.md:2628](../epics-and-stories.md#L2628), "9.10 scope-expanded slightly (scrub `oneOf`/v1-v2 prose too)"). Those entries are themselves FROZEN history — this story implements the mandate they record, it does not rewrite them.

### References

- [Source: _bmad-output/implementation-artifacts/9-9c-schema-unification.md#AC1](9-9c-schema-unification.md) — the schema-of-record; the canonical correct framing every reframe converges on (single unified shape, `schema_version` = config-shape version, binary `in_match_detection`, `hud_version` runtime selection, `map_config_emitter.py` rename).
- [Source: _bmad-output/implementation-artifacts/9-9b-iterative-zone-population-for-shipping-configs.md](9-9b-iterative-zone-population-for-shipping-configs.md) — Cohort B accuracy-floor source (iteration-log per-classifier table); AC6 anchor; downstream-of relationship recorded in 9.9b's Sprint-fit section.
- [Source: _bmad-output/sprint-change-proposal-2026-05-15.md](../sprint-change-proposal-2026-05-15.md) — full schema-unification + tooling-consolidation rationale; §4 covers 9.9b/9.9c/9.10; the authoritative "why the pivot" narrative the editorial pass re-anchors prose toward.
- [Source: _bmad-output/epics-and-stories.md:2616-2628](../epics-and-stories.md#L2616) — Epic 9 charter + the two amendment blocks (2026-05-14 / 2026-05-15); charter Goal line 2618 is the in-scope reframe target; amendment blocks are FROZEN historical record.
- [Source: _bmad-output/epics-and-stories.md:2767-2770](../epics-and-stories.md#L2767) — Story 9.10 self-description + the scope-expansion sentence (this story's mandate).
- [Source: _bmad-output/sprint-status.yaml:186](../sprint-status.yaml#L186) — 9.10 entry: original targets (`tooling-HASH-001/002`, `mapIdentifier.ts` line, `mobile-AUTO-SLICE-002/003`) + the 2026-05-15 scope expansion (scrub `oneOf`/v1-v2 prose).
- [Source: _bmad-output/sprint-status.yaml:183](../sprint-status.yaml#L183) — the explicit decision that the original 9.9 stub content is preserved verbatim for traceability (the FROZEN-region basis for AC1/AC5).
- [Source: _bmad-output/sprint-status.yaml:187](../sprint-status.yaml#L187) — 9.9c `done` (commit `9b9d4af`) + the local `--no-ff` delivery precedent (`gh` non-interactive auth failure) AC10 follows.
- [Source: _bmad-output/prd.md:955-956](../prd.md#L955) — `tooling-HASH-001/002` (primary named AC2/AC4 target).
- [Source: _bmad-output/prd.md:868-869](../prd.md#L868) — `mobile-AUTO-SLICE-002/003` (named AC2 target).
- [Source: _bmad-output/prd.md:1042](../prd.md#L1042) — `REL-006` map-ID accuracy floor (AC6 / Cohort B anchor).
- [Source: _bmad-output/architecture.md:1505](../architecture.md#L1505) — `mapIdentifier.ts` "pHash matcher" source-tree line (named AC3 target).
- [Source: _bmad-output/architecture.md:1691](../architecture.md#L1691) — `mobile-AUTO-SLICE-002/003` traceability "pHash matching" line (named AC3 target).
- [Source: contracts/map-config.schema.json](../../contracts/map-config.schema.json) — the shipped unified schema (post-9.9c); the on-disk reality the docs must stop contradicting.
- Memory: [[project_warden_new_hud_labeler]] (new-HUD initiative — Epic 9 schema-unification + tooling-consolidation context; 9.9c supersedes 9.9a's `oneOf`); [[feedback_two_pr_docs_execution]] (Two-PR pattern for BMad docs-only stories); [[feedback_ac_checkbox_tighten]] (hold `[ ]` for post-merge-/data-dependent ACs).

## Dev Agent Record

### Agent Model Used

_(populated at dev-story kickoff)_

### Debug Log References

_(populated during dev-story — Task 2 line-number re-anchoring notes go here)_

### Completion Notes List

_(populated at dev-story finalization — MUST include: the AC1 "Scope Boundary" FROZEN|IN-SCOPE table; the AC3 explicit negative result for architecture.md `oneOf`; the AC4 annotate-vs-reframe decision; the AC8 flagged stale inbound anchors; Cohort B inclusion/deferral status)_

### File List

_(populated at dev-story finalization — expected: prd.md, architecture.md, epics-and-stories.md, this story file, sprint-status.yaml; NOTHING else)_

### Change Log

| Date       | Change                                                                                                       |
|------------|--------------------------------------------------------------------------------------------------------------|
| 2026-05-16 | Story created via /bmad-create-story (Stephane). Spec finalized at `ready-for-dev` with 11 ACs (AC0 rollout decision + AC1 scope-boundary attestation gate + AC2/AC3/AC5 Cohort-A prose scrub + AC4 PRD-V1-treatment decision + AC6 Cohort-B accuracy citations gated on 9.9b + AC7 no-code invariant + AC8 cross-ref integrity + AC9/AC10 sprint-status lifecycle & Two-PR follow-up), 8 Tasks, Dev Notes (schema-of-record framing, the central historical-traceability-destruction anti-pattern, Editorial Target Manifest with FROZEN/IN-SCOPE classification across all 3 docs, sprint-fit + dependencies, project-structure notes, references). Two-cohort structure: Cohort A (prose scrub) unblocked by 9.9c `done`; Cohort B (accuracy citations) gated on 9.9b. Dev-cycle kickoff held until 9.9b reports per AC0 default Option A. All 11 ACs held `[ ]` per [[feedback_ac_checkbox_tighten]] (every endpoint depends on upstream completion, the AC0/AC4 kickoff decisions, or post-merge admin). Subagent inventories of all 3 docs incorporated into the Manifest; key finding — architecture.md contains ZERO `oneOf`/v1-v2 prose (scope-expansion's architecture target is a verify-and-record-negative, not an edit); ~60 stale-prose hits exist but the majority are inside deliberately-FROZEN cancelled-story / SUPERSEDED-9.9a / preserved-9.9-stub blocks. epic-9 stays `in-progress`. No code/docs touched in this skill run beyond this story file. |
