# Story 0.1: Conduct Per-Story Conflict Audit for Sprint 2.5 In-Flight Mobile Work

Status: review

<!-- Validation is optional. Run validate-create-story before dev-story for a quality check. -->

## Story

As **Stephane** (solo developer running unified Sprint 3 planning),
I want **a per-story conflict-audit table for the 10 in-flight legacy mobile Sprint 2.5 stories**,
So that **each story's disposition is binding (`complete-as-legacy` / `re-scope-into-Sprint-3-with-new-AC` / `drop`) before Sprint 3 commits scope.**

**Type:** Planning artifact — produces a markdown table, not code. No tests, no app changes.

**Why this is G0 (the gate that blocks Sprint 3 merges):** Sprint Plan §2 Gate G0 — until Story 0.2 closes, **no Sprint 3 story may merge to `main`**. Story 0.1 produces the binding audit table that Story 0.2 then executes. Errors here (a wrong disposition, a missed PRD conflict, a free-tier path slipping through under legacy AC) cascade into Sprint 3 as merge-time rework or post-merge debt.

## Acceptance Criteria (checklist)

1. [x] Audit file created at `_bmad-output/sprint-2.5-conflict-audit.md` (UTF-8, LF or CRLF — match repo convention).
2. [x] Audit file contains exactly **10 rows** — one per legacy Sprint 2.5 mobile story: **2.2, 2.5, 2.6, 2.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6**. Stories 2.1 (`done`), 2.3 / 2.4 (`superseded`), and 3.5 (`superseded`) are explicitly **excluded** — they are not in-flight.
3. [x] Each row includes all seven required columns: `story_id`, `legacy_AC_summary`, `unified_PRD_conflict` (yes/no), `conflict_specifics` (free-text — populated only when `unified_PRD_conflict = yes`), `disposition` (one of: `complete-as-legacy` | `re-scope-into-Sprint-3-with-new-AC` | `drop`), `target_epic` (Sprint 3 epic the new AC lands in — populated only when disposition is `re-scope-into-Sprint-3-with-new-AC`), `responsible_owner` (defaults to `Stephane` for solo-dev project unless rationale given otherwise).
4. [x] **Audit Rule A applied:** Any story whose AC implies a free-tier or pre-no-free-tier flow MUST be marked `re-scope-into-Sprint-3-with-new-AC` or `drop`. It MUST NOT be marked `complete-as-legacy`. (PRD §2 "No-free-tier positioning" + Section 5 Reader-App contract.)
5. [x] **Audit Rule B applied:** Any story whose AC contradicts a locked PRD constraint MUST be re-scoped or dropped. The locked constraints are: (a) Reader-App contract (no monetization surface in mobile build artifacts), (b) on-device-only video / audio processing (no frames or voice cross any wire), (c) six-state entitlement model (`paid` / `lapsed` / `offline-grace ≤30d` / `payment-failed` / `multi-device` / `signed-out`), (d) 14-canonical-maps single-source from `tools/frame_labeler.py:19-34` (`MAP_LABELS`), (e) 3-value `view_mode` (Full / Minimap / Minimap+HUD — no 2-value `pov` literals), (f) dual-T1 activation telemetry (T1-coach via export-pipeline confirmed-dispatch; T1-active-player via Cinema Mode first view-mode toggle).
6. [x] **Audit Rule C applied:** Stories whose AC is wholly compatible with the unified PRD MUST be marked `complete-as-legacy` and ship under their existing AC — no rewrite, no AC modification.
7. [x] **Live-status verification done:** For each of the 10 stories, the auditor read the actual `Status:` line in `_bmad-output/legacy/mobile/stories/<n>.md` (not the status in `_bmad-output/epics-and-stories.md` Implementation Notes — the epics file is known-stale: it claims 7.4 = ready-for-dev but the story file shows `done`, and 7.5 = ready-for-dev but the file shows `in-progress`). The actual file status is recorded inline in the audit row's `legacy_AC_summary` column.
8. [x] **Each disposition is justified.** Where `unified_PRD_conflict = yes`, the `conflict_specifics` cell names the specific PRD section / constraint that conflicts (cite by section number, FR ID, or NFR ID). Where the disposition is `drop`, the rationale is recorded inline.
9. [x] **Sprint-3 epic targets are concrete.** Where disposition is `re-scope-into-Sprint-3-with-new-AC`, the `target_epic` cell names a specific epic from Sprint 3 (Epic 1 / Epic 2 / Epic 3 / Epic 5 / Epic 6 / Epic 7) that the new AC will land in — referencing the epic's purpose-fit rather than guessing. _(Vacuous: 0/10 rows have this disposition.)_
10. [x] Audit file ends with a **"Summary counts"** section listing: total rows = 10; `complete-as-legacy` count = N; `re-scope-into-Sprint-3-with-new-AC` count = N; `drop` count = N. (Sum equals 10.)
11. [x] Audit file ends with a **"Sprint 3 merge-block status"** statement: "Until Story 0.2 executes these dispositions and is marked `done`, no Sprint 3 story may merge to `main` per Sprint Plan §2 Gate G0." (Verbatim — this is the visible gate sign.)
12. [~] Audit file is committed in a single PR titled `docs: Sprint 2.5 per-story conflict audit (Story 0.1)`. PR body links to this story file and to Sprint Plan §2 Gate G0. _(Branch `sprint-2-5-conflict-audit` is pushed with the commit at the AC12-mandated title; the GitHub web-UI PR creation step is left to Stephane because `gh` CLI is not installed on this machine. Title + body to paste are recorded in Completion Notes.)_

## Tasks / Subtasks

> **Workflow shape:** This is a manual-review task. The dev agent does **not** generate dispositions automatically — the agent **reads** each legacy story, **applies** the audit rules, and **records** the disposition with cited rationale. The output is a markdown table, not code.

- [x] **Task 1: Read the live status of all 10 legacy Sprint 2.5 mobile stories (AC: 2, 7)**
  - [x] Open and skim `_bmad-output/legacy/mobile/stories/2.2.md` — record actual `Status:` value, AC summary, and any conflict signal (free-tier wording, monetization-surface wording, server-side video paths, 2-value `view_mode` literals, hard-coded map list outside `MAP_LABELS`, telemetry payload with frame/voice fields).
  - [x] Repeat for `2.5.md`, `2.6.md`, `2.7.md`, `7.1.md`, `7.2.md`, `7.3.md`, `7.4.md`, `7.5.md`, `7.6.md`.
  - [x] **Do NOT trust** the status values in `_bmad-output/epics-and-stories.md` Implementation Notes for Epic 0 — that file is known-stale (lists 7.4 as `ready-for-dev` when the story file says `done`; lists 7.5 as `ready-for-dev` when the story file says `in-progress`). The legacy story file's `Status:` line is authoritative.
- [x] **Task 2: Apply audit rules per story (AC: 4, 5, 6, 8, 9)**
  - [x] For each of the 10 stories, walk Audit Rules A → B → C in that order. The **first rule that fires** determines the disposition. (A and B force `re-scope` or `drop`; C only applies if neither A nor B fired.)
  - [x] Record the disposition + the cited PRD section / FR ID / NFR ID that triggered the rule.
  - [x] If `re-scope-into-Sprint-3-with-new-AC`, name the target Sprint 3 epic and a one-sentence sketch of the new AC direction (the actual rewrite happens in Story 0.2, not here — but 0.1 must point Story 0.2 at the right epic). _(Vacuous: 0/10 rows have this disposition.)_
- [x] **Task 3: Compose the audit table (AC: 1, 3)**
  - [x] Create `_bmad-output/sprint-2.5-conflict-audit.md` with the structure shown in Dev Notes "Audit file template".
  - [x] Populate one row per story; the order is **2.2, 2.5, 2.6, 2.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6** (matches the epics file's enumeration).
- [x] **Task 4: Add summary + gate-block statement (AC: 10, 11)**
  - [x] Add the "Summary counts" section.
  - [x] Add the verbatim "Sprint 3 merge-block status" statement.
- [~] **Task 5: Commit + open PR (AC: 12)** — branch + commit + push complete; PR-create step deferred to Stephane (no `gh` CLI on host).
  - [x] `git checkout -b sprint-2-5-conflict-audit`.
  - [x] `git add _bmad-output/sprint-2.5-conflict-audit.md _bmad-output/implementation-artifacts/0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work.md _bmad-output/sprint-status.yaml`.
  - [x] Commit with message: `docs: Sprint 2.5 per-story conflict audit (Story 0.1)`.
  - [x] Push branch to `origin`.
  - [ ] Open PR targeting `main` (Stephane via GitHub web UI). PR body MUST link to this story file and to Sprint Plan §2 Gate G0.

## Dev Notes

### What this story is — and is NOT

- ✅ **IS:** A planning-artifact story. Output = one markdown file. Manual review by Stephane is the verification step (per epic 0.1 acceptance: "Manual review by Stephane against unified PRD §3 / §5 / §9 / §10 sections").
- ❌ **IS NOT:** A code-writing story. No app changes. No tests. No mobile/web/tooling source files are touched. No `apps/mobile/**` files are modified by 0.1.
- ❌ **IS NOT:** Story 0.2. Story 0.1 produces the audit *plan*; Story 0.2 *executes* the plan (legacy story files get final-completion notes for `complete-as-legacy` rows, new AC entries get added to target epics for `re-scope` rows, and `drop` rows get archived with rationale).

### Audit file template

The dev agent should structure `_bmad-output/sprint-2.5-conflict-audit.md` like this (markdown table; pipe-separated; row per legacy story):

```markdown
# Sprint 2.5 Per-Story Conflict Audit

**Generated:** <ISO 8601 date>
**Author:** Stephane
**Source story:** `_bmad-output/implementation-artifacts/0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work.md`
**PRD reference:** `_bmad-output/prd.md` (§2 No-free-tier; §5 Reader-App + on-device-only; §9 entitlement; §10 telemetry)
**Sprint plan reference:** `_bmad-output/sprint-plan.md` §2 Gate G0

## Audit Rules Applied

- **Rule A:** Free-tier or pre-no-free-tier flow → re-scope or drop.
- **Rule B:** Contradicts locked PRD constraint (Reader-App / on-device-only / six-state entitlement / 14-canonical-maps / 3-value view_mode / dual-T1 telemetry) → re-scope or drop.
- **Rule C:** Wholly compatible with unified PRD → complete-as-legacy.

## Audit Table

| story_id | legacy_AC_summary (incl. live status) | unified_PRD_conflict | conflict_specifics | disposition | target_epic | responsible_owner |
|---|---|---|---|---|---|---|
| 2.2 | … (status: in-progress; …) | yes/no | … | … | … | Stephane |
| 2.5 | … (status: …) | … | … | … | … | … |
| 2.6 | … |
| 2.7 | … |
| 7.1 | … |
| 7.2 | … |
| 7.3 | … |
| 7.4 | … |
| 7.5 | … |
| 7.6 | … |

## Summary counts

- Total rows: 10
- complete-as-legacy: N
- re-scope-into-Sprint-3-with-new-AC: N
- drop: N

## Sprint 3 merge-block status

Until Story 0.2 executes these dispositions and is marked `done`, no Sprint 3 story may merge to `main` per Sprint Plan §2 Gate G0.
```

### The 10 legacy stories — read paths and known signals

All paths are under `_bmad-output/legacy/mobile/stories/`. The "known signal" column is **a heuristic prior, not a binding disposition**. The dev agent MUST read each file and apply the audit rules independently — the priors are starting hypotheses, not conclusions.

| story_id | legacy story file | live status (verified 2026-05-09) | known signal (prior) |
|---|---|---|---|
| 2.2 | `2.2.md` — FFmpeg + keyframe extraction | `in-progress` | Likely `complete-as-legacy`. AC is sandbox + device-side keyframe extraction. No free-tier wording. No monetization surface. On-device-only by construction (FFmpeg encode runs locally). 3 minor edits already applied per epics file note. **Verify:** AC3/4/6 device-side checks remain pending — disposition does not require they be re-done; legacy AC is unchanged. |
| 2.5 | `2.5.md` — segment video into map episodes | `ready-for-dev` | Likely `complete-as-legacy`. Already rewritten to consume 7.5's `gameDetector` + `mapIdentifier` types; AC4 explicitly handles `unknown-map`. Aligns with PRD-locked 14-canonical-maps + on-device-only. **Verify:** map-identification path uses pHash-against-`map_config.json` (not server lookup). |
| 2.6 | `2.6.md` — background processing + crash recovery | `ready-for-dev` | Likely `complete-as-legacy`. Background processing wording aligns with Foreground Service plan (Epic 1 Story 1.2 BF-5). **Verify:** no IAP / pricing / plan-picker wording; no telemetry payload that includes frame data. |
| 2.7 | `2.7.md` — session list + management | `ready-for-dev` | Likely `complete-as-legacy`. Session-management UI is local. **Verify:** no monetization surface; deletion path foreshadows AR-12 cascade (Epic 6 Story 6.9) but does not need to implement it. |
| 7.1 | `7.1.md` — SQLite `view_mode` CHECK 2-value → 3-value migration | `ready-for-dev` | Likely `complete-as-legacy`. Already a 3-value migration aligned with Full / Minimap / Minimap+HUD. Ships same PR as 7.2. **Verify:** target enum is exactly Full / Minimap / Minimap+HUD; no `pov` literal survives. |
| 7.2 | `7.2.md` — `ClipExport.view_mode` TypeScript type | `ready-for-dev` | Likely `complete-as-legacy`. Same PR as 7.1. **Verify:** TS union is exactly the 3-value set; legacy `'pov'` literals audited out. |
| 7.3 | `7.3.md` — view-mode toggle UI + `HudToggle` + Zustand+MMKV persistence | `ready-for-dev` | Likely `complete-as-legacy`. Supersedes legacy 3.5. Aligns with PERF-003 ≤100ms and `mobile-CINEMA-002` 3-value control. **Verify:** unknown-map default-to-Full path is present (`mobile-CINEMA-003`); HUD toggle state persists per `prefs.viewMode` + `prefs.minimapHud`. |
| 7.4 | `7.4.md` — DetectionConfig service no-op shim | **`done`** (epics file is stale — story file is authoritative) | Likely `complete-as-legacy` with no further work. Already merged. Disposition row exists for completeness. **Verify:** `Status: done` in file. If `done`, the audit row records "complete-as-legacy (already merged; no further work)". |
| 7.5 | `7.5.md` — `gameDetector` + pHash `mapIdentifier` + `blackScreenDetector` long-GOP refactor + delete `templateMatcher.ts` + delete map-templates assets | **`in-progress`** (epics file is stale) | Likely `complete-as-legacy`. The detector replacement aligns with PRD's on-device-only + KDA/HSV + pHash methodology. **Verify:** the deletion of `templateMatcher.ts` + `assets/images/map-templates/` is part of the AC and survives intact; `MAP_LABELS` is sourced from contracts (post-Epic 1 AR-4) or from a single canonical place. |
| 7.6 | `7.6.md` — export pipeline 3 view modes via `exportRecipes` + `exportPipeline` | `ready-for-dev` | Likely `complete-as-legacy`. Supersedes view-mode portion of legacy 5.1+5.2 (which Sprint 3 Epic 6 builds on). **Verify:** export pipeline is on-device-only (FFmpeg local encode); no cloud-encode path; voice annotation overlay does not transmit audio data. |

### How to apply the audit rules in practice

For each legacy story, the agent walks the rules **in order** and stops at the first match:

**Rule A check (free-tier):** Search the story file for `free-tier`, `try-before-buy`, `freemium`, `IAP`, `in-app purchase`, `plan picker`, `pricing` (in mobile UI context). If any hit signals the AC is built around a free path or includes a monetization surface in mobile → disposition = `re-scope-into-Sprint-3-with-new-AC` (or `drop` if the story has no V1-relevant carry-forward).

**Rule B check (locked PRD constraint contradiction):**
- **B.1 Reader-App:** AC mentions IAP, RN-IAP, Stripe SDK *in mobile*, plan picker *in mobile*, pricing UI *in mobile*, or any Tier-1 monetization-surface dep → re-scope/drop.
- **B.2 On-device-only:** AC ships video frames or voice audio off-device (e.g., upload to Warden server, cloud encode, server-side template matching, server-side OCR) → re-scope/drop.
- **B.3 Six-state entitlement:** AC implements a 2-state or 3-state entitlement (e.g., paid/free, paid/lapsed only) without `payment-failed` + `offline-grace` + `multi-device` + `signed-out` → re-scope/drop. (Most Sprint 2.5 mobile stories will not touch entitlement and pass this trivially.)
- **B.4 14-canonical-maps:** AC hard-codes a map list outside `MAP_LABELS` (legacy `tools/frame_labeler.py:19-34`) or includes a 15th map without going through Epic 9's regeneration pipeline → re-scope/drop.
- **B.5 3-value view_mode:** AC uses `'pov'` literal, 2-value enum, or any `view_mode` shape that is not exactly Full / Minimap / Minimap+HUD → re-scope/drop. (Stories 7.1 and 7.2 *resolve* this — they should pass; legacy stories *predating* the 3-value migration would fail.)
- **B.6 Dual-T1 telemetry:** AC emits a telemetry event whose payload includes frame data, voice durations, raw audio, or any field outside `{elapsed_seconds, t0_at, t1_at, t1_path: 'coach' | 'active_player'}` → re-scope/drop.

**Rule C (compatible) — applies only if A and B did not fire:**
- AC is wholly compatible with the unified PRD → `complete-as-legacy`.
- The story's existing AC is **not** rewritten; the story ships under its existing AC.

### Realistic disposition expectations (heuristic, not binding)

Given the priors above, the audit is **likely** to produce mostly `complete-as-legacy` rows: the Sprint 2.5 mobile work was already aligned to the methodology pivot (sprint-change-proposal-2026-05-05) that produced the 3-value `view_mode`, the 7.5 detector replacement, and the 7.4 DetectionConfig shim. The dev agent should be alert to — but not surprised by — this. **However:** the agent must not skip the per-story read because the priors look favorable. A 5-minute read-and-cite is the deliverable; the priors are not the deliverable.

If the agent finds **zero** conflicts across all 10 stories, the agent must explicitly state in the audit's "Summary counts" section that 10/10 stories pass Rule C, and Stephane will manually verify before signing off. (Reviewer skepticism: "did the agent skip the read and rubber-stamp ten rows?" — counter-evidence is the per-story `legacy_AC_summary` cell, which must include a substantive AC summary, not "no conflicts found".)

### What to NOT do

- **Do not** re-read or modify any file under `apps/mobile/`, `apps/web/`, `apps/tooling/`. This story produces a planning artifact; it does not touch source code.
- **Do not** modify any of the 10 legacy story files under `_bmad-output/legacy/mobile/stories/`. Story 0.2 adds disposition tags to those files; Story 0.1 only reads them.
- **Do not** add new AC entries to `_bmad-output/epics-and-stories.md`. Story 0.2 does that for `re-scope` rows.
- **Do not** invent new dispositions beyond the three options. The taxonomy is fixed: `complete-as-legacy` | `re-scope-into-Sprint-3-with-new-AC` | `drop`.
- **Do not** treat the epics file's "Implementation Notes" status claims as authoritative. The story file's `Status:` line is the source of truth (the epics file is stale on at least 7.4 and 7.5).

### Project Structure Notes

- **Output location** for the audit table: `_bmad-output/sprint-2.5-conflict-audit.md` (project root `_bmad-output/`, not `_bmad-output/implementation-artifacts/`). The story 0.1 AC explicitly names this path.
- **Story file location** (this file): `_bmad-output/implementation-artifacts/0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work.md` per `sprint-status.yaml`'s `story_location: _bmad-output/implementation-artifacts`.
- **Legacy story read path**: `_bmad-output/legacy/mobile/stories/<n>.md` (the legacy mobile repo's stories directory was preserved verbatim under `_bmad-output/legacy/mobile/` during monorepo consolidation).
- **No conflicts** with unified project structure — this story produces an output in `_bmad-output/`, the planning-artifact bucket. It does not introduce new source-tree paths.

### Testing standards summary

**No code tests.** Verification is manual review by Stephane against unified PRD §3 / §5 / §9 / §10 (epic 0.1 acceptance verbatim).

The "test plan" for this story is the auditor's read-and-cite discipline:
- Each row's `legacy_AC_summary` cell substantively summarizes the legacy AC (not a placeholder like "see file").
- Each row's `unified_PRD_conflict` cell is `yes` or `no` (binary).
- Where `yes`: `conflict_specifics` cites a PRD section / FR ID / NFR ID.
- Where disposition is `re-scope-into-Sprint-3-with-new-AC`: `target_epic` is concrete (Epic 1 / 2 / 3 / 5 / 6 / 7).

### References

- [Source: _bmad-output/epics-and-stories.md#Story 0.1 (lines 694–713)] — original story acceptance criteria + dependencies + sprint fit.
- [Source: _bmad-output/epics-and-stories.md#Decision #ES-3 — Sprint 2.5 Per-Story Conflict Audit] — RESOLVED; Epic 0 owns the audit table as its discrete deliverable.
- [Source: _bmad-output/sprint-plan.md#Gate G0 — Sprint 2.5 Closure (blocks Sprint 3 merge)] — the merge gate this story unblocks.
- [Source: _bmad-output/prd.md#Section 2 No-free-tier positioning (line 164)] — Audit Rule A's anchor.
- [Source: _bmad-output/prd.md#Section 5 Reader-App contract (lines 114, 202, 508–514)] — Audit Rule B.1's anchor.
- [Source: _bmad-output/prd.md#Section 5 On-device-only (lines 138, 202, 500, 533, 663, 1033)] — Audit Rule B.2's anchor.
- [Source: _bmad-output/prd.md#cross-ENTITLEMENT-001 (line 980)] — six-state entitlement; Audit Rule B.3's anchor.
- [Source: _bmad-output/prd.md#tooling-LABEL-002 (line 951)] — 14-canonical-maps `MAP_LABELS` single source; Audit Rule B.4's anchor.
- [Source: _bmad-output/prd.md#mobile-CINEMA-002 / mobile-CINEMA-004 (lines 883, 885)] — 3-value `view_mode`; Audit Rule B.5's anchor.
- [Source: _bmad-output/prd.md#cross-ACTIVATION-001 / cross-ACTIVATION-002 (lines 985–986)] — dual-T1 telemetry payload schema; Audit Rule B.6's anchor.
- [Source: _bmad-output/legacy/distillate/07-epics-and-sprint-state.md (lines 17–53)] — legacy mobile Sprint 2.5 story summaries (cross-check; story files are authoritative on status).
- [Source: _bmad-output/architecture.md (lines 131, 178, 185)] — confirms "in-flight Sprint 2.5 mobile stories disposed as complete-as-legacy after per-story audit" is the architecture-level expectation.

### Previous-Story Intelligence

This is the **first story in Epic 0** and the **first story of Sprint 3**. There is no previous story to inherit from in this sprint.

The relevant historical context is the **methodology pivot** (sprint-change-proposal-2026-05-05) that landed the 3-value `view_mode`, the 7.5 detector replacement, and the 7.4 DetectionConfig shim — these reshaped the Sprint 2.5 in-flight stories to align with the unified PRD methodology *before* the unified PRD existed. The dev agent should not be surprised to find most Sprint 2.5 stories already align with PRD constraints; that is the deliberate outcome of the pre-merge sprint-change-proposal.

### Git intelligence

Recent monorepo commits (Phase 6 of consolidation):

```
0ce3954 docs: add Sprint 3 plan + status tracker (phase 6 step 7)
5968ef9 docs: add implementation readiness report + apply 3 amendments (phase 6 step 6)
dd5b8bd docs: add unified UX design (phase 6 step 4)
410ee84 docs: add unified architecture (phase 6 step 3)
3b7b302 docs: add unified PRD (phase 6 step 2)
```

**Pattern:** Phase 6 has been a documentation-only chain (PRD → architecture → UX → readiness → sprint plan + status tracker). Story 0.1 continues the docs-only convention for Phase 6 step 8 (or equivalent). No code changes expected from this story.

### Latest tech / library notes

**Not applicable.** Story 0.1 produces a markdown table; no library or framework version is in scope. The auditor uses a markdown editor and `git`. (If the agent wants to mechanically grep the legacy stories for trigger words like `IAP`, `pov`, `free-tier`, `frame_data`, etc., it can use `grep`/`rg` — but this is a tool choice, not a tech decision.)

### Project-context reference

There is no `project-context.md` in this repo (the bmad-create-story workflow looks for one but none is present). The persistent context is:
- The 3 legacy repos (Warden / Warden-tooling / WardenWeb) are merged under `apps/{mobile,web,tooling}` with full git history preserved.
- `_bmad-output/` holds the unified planning artifacts (PRD, architecture, UX, epics, sprint plan + status, this story).
- `_bmad-output/legacy/` holds pre-merge artifacts copied verbatim during consolidation — this is where the 10 Sprint 2.5 mobile story files live.

## Dev Agent Record

### Agent Model Used

Amelia (BMM dev agent) — Claude Opus 4.7 (`claude-opus-4-7[1m]`)

### Debug Log References

- Read all 10 legacy mobile story files in `_bmad-output/legacy/mobile/stories/` (`2.2.md`, `2.5.md`, `2.6.md`, `2.7.md`, `7.1.md`, `7.2.md`, `7.3.md`, `7.4.md`, `7.5.md`, `7.6.md`) — each fully, not just the `Status:` line — to substantively populate the `legacy_AC_summary` column. Read in parallel via 10 concurrent Read calls.
- Status divergence between epics file and story files **confirmed** for both 7.4 (epics file: `ready-for-dev`; file: `done`) and 7.5 (epics file: `ready-for-dev`; file: `in-progress`). Story-file values are recorded in the audit and are authoritative per AC 7.
- Audit rule walk: applied A → B → C per story. Zero stories tripped Rule A. Zero stories tripped any of B.1 / B.2 / B.3 / B.4 / B.5 / B.6 — the methodology pivot (sprint-change-proposal-2026-05-05, commit `f5d9be1`) had already pre-aligned the in-flight Sprint 2.5 work to the unified PRD constraints. All 10 stories landed under Rule C.
- Per AC9 vacuity: 0 rows are `re-scope-into-Sprint-3-with-new-AC`, so the `target_epic` discipline is unexercised. AC9 is satisfied vacuously; this is noted inline in the AC checklist.

### Completion Notes List

- **Audit composed and validated against ACs 1–11.** AC 12 (commit + PR) is the next-and-final step; pending Stephane's go-ahead before the agent runs git operations on shared infrastructure.
- **Disposition outcome:** 10 / 10 `complete-as-legacy`. This is the prior the story's own Dev Notes flagged as "likely" — and the per-story read confirms it rather than skipping to it. Reviewer-skepticism counter-evidence is the per-row `legacy_AC_summary` cell, which carries a substantive AC summary (not "no conflicts found").
- **Story 7.5 native-binding follow-up noted, not blocking.** Story 7.5's open Review Follow-up (`react-native-fast-opencv` wiring for `loadFrameFromPath`) is mentioned in the audit row for traceability, but it does not change 7.5's disposition — that work is Sprint 3 Epic 1 Story 1.1 (AR-spike) territory, not a 0.1 audit concern.
- **Story 2.2 device-bound ACs noted, not blocking.** 2.2's ACs 3 / 4 / 6 (smoke test on Poco X5, peak RAM < 2 GB, boot regression) require physical hardware not available in this agent's sandbox. They are flagged in the audit row's status summary; disposition is unaffected (story is `complete-as-legacy` once handoff smoke test runs locally — the audit captures the legacy AC, not the dev-handoff status).
- **Files modified by 0.1:** the audit file (created), this story file (Tasks/Subtasks checkboxes + Dev Agent Record + File List + Change Log + Status), and `sprint-status.yaml` (status flip on `0-1-…`). No legacy story files modified — Story 0.2 owns the disposition tags on those.
- **Definition-of-Done check:** Tasks 1-4 fully complete. Task 5 partial — branch `sprint-2-5-conflict-audit` is pushed to `origin` with the AC12-mandated commit title; only the GitHub-web-UI PR-create click remains, and it's Stephane's because the host has no `gh` CLI. The PR title + body to paste are below under "PR title and body to file".

#### PR title and body to file

**Title (paste verbatim):**

```
docs: Sprint 2.5 per-story conflict audit (Story 0.1)
```

**Body (paste verbatim — Markdown):**

```markdown
## Summary

Closes Story 0.1 (Sprint 3 Epic 0). Adds the per-story conflict audit table for the 10 in-flight legacy Sprint 2.5 mobile stories. **Outcome: 10 / 10 → `complete-as-legacy`** — the 2026-05-05 sprint-change-proposal had already pre-aligned this work to the unified PRD methodology.

This PR is the **G0 gate evidence**: Story 0.2 will execute the dispositions; Sprint 3 stories cannot merge to `main` until 0.2 is `done`.

## Files

- `_bmad-output/sprint-2.5-conflict-audit.md` — the audit table (the deliverable)
- `_bmad-output/implementation-artifacts/0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work.md` — story spec with Tasks/Subtasks marked, Dev Agent Record, File List, Change Log; Status flipped to `review`
- `_bmad-output/sprint-status.yaml` — `0-1-…` flipped `ready-for-dev` → `in-progress` → `review`

## References

- Story spec: [`_bmad-output/implementation-artifacts/0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work.md`](../blob/main/_bmad-output/implementation-artifacts/0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work.md)
- Sprint Plan §2 Gate G0: [`_bmad-output/sprint-plan.md#gate-g0`](../blob/main/_bmad-output/sprint-plan.md)
- Audit deliverable: [`_bmad-output/sprint-2.5-conflict-audit.md`](../blob/main/_bmad-output/sprint-2.5-conflict-audit.md)
```

After the PR is opened, mark this story's AC 12 + Task 5 final subtask `[x]` and add the PR URL alongside this note (commit message: `docs: 0.1 — record PR URL post-merge`).

### File List

- `_bmad-output/sprint-2.5-conflict-audit.md` — **CREATED** (the audit deliverable)
- `_bmad-output/implementation-artifacts/0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work.md` — **UPDATED** (Tasks/Subtasks checkboxes 1-4 marked `[x]`; Task 5 left `[ ]` pending git ops; AC checklist 1-11 marked `[x]`; AC 12 left `[ ]` pending PR; Dev Agent Record / File List / Change Log populated; Status flipped to `review` on PR-merge; AC 12 closes with the PR URL once filed)
- `_bmad-output/sprint-status.yaml` — **UPDATED** (`0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work` status flipped `ready-for-dev` → `in-progress` → `review` on completion of Task 5)

## Change Log

| Date       | Change                                                                                                | Author |
|------------|-------------------------------------------------------------------------------------------------------|--------|
| 2026-05-09 | Sprint 2.5 per-story conflict audit composed; 10 / 10 dispositions = `complete-as-legacy`; ACs 1-11 met; AC 12 (commit + PR) pending Stephane's authorization | Amelia |
