# Sprint Change Proposal — 2026-05-14

**Sprint:** Sprint 3 (post-consolidation V1 push)
**Project:** Warden_monorepo
**Raised by:** Stephane (solo dev)
**Workflow:** `bmad-correct-course` (incremental mode)
**Scope classification:** Minor (docs-only — no code touched, no in-progress work disturbed)
**Status:** Approved 2026-05-14 — applied to repo same day

---

## 1. Issue Summary

EVA shipped a HUD redesign ("HUD 2.0"). The legacy detection stack (`apps/tooling/tools/warden_analyzer.py`, `apps/mobile/src/features/video-processing/gameDetector.ts`, `apps/mobile/src/features/video-processing/mapIdentifier.ts`) keys off legacy-HUD-1.0 ROIs in `config/config.yaml`, which no longer fire on HUD 2.0 footage — `gameDetector` returns false-negatives and `mapIdentifier` returns null on all current real footage.

In response, Stories 9.5–9.8 (Tools 6/7/8/9 — Video Timeline Labeler → Overlay Stack Analyzer → Auto ROI Discoverer → ROI Detection Tester) were added post-planning between 2026-05-09 and 2026-05-13. They build a HUD-version-aware labeled dataset, mine ROI/HSV-band signatures, and validate per-frame detection against those signatures. With 9.5–9.8 all `done`/`review`, the new-HUD detection path is operational.

**Trigger for this correct-course:** with the new-HUD chain shipped, the legacy-detection-bound Stories 9.2 (validate `warden_analyzer` against real footage at ≥95% accuracy) and 9.3 (regenerate reference pHashes for 4 awaiting-hash maps) are no longer viable as specified, and the broader hash-based map identification approach is being replaced by ROI+HSV-band detection. Epic 9's charter (which enumerates 9.1–9.4 only) is also out of date — a long-standing "doc-debt" carried in every 9.5–9.8 sprint-status entry.

**Issue type:** Technical limitation surfaced by adjacent work + scope evolution from a parallel initiative.

---

## 2. Impact Analysis

### Epic impact

- **Epic 9 charter** — currently enumerates 9.1–9.4 only; needs amendment to acknowledge 9.5–9.8 (already shipped) and 9.9 (added by this correct-course).
- **Story 9.1** — keep. Detection-method-agnostic. Motivation note added: `schema_version: 1` is now also the v1 baseline so the v2 ROI/HSV-band partition (Story 9.9, post-V1) can land cleanly.
- **Story 9.2** — cancel. Validates the legacy detector against real footage; real footage is HUD 2.0 where legacy ROIs don't fire. Tool 9 (Story 9.8 — DONE) is the new-HUD analogue.
- **Story 9.3** — cancel. Hash-based map identification is being replaced wholesale by ROI+HSV-band detection. Reference-hash regeneration is structurally moot, not deferred. Work folds into Story 9.9.
- **Story 9.4** — keep. Detection-method-agnostic. Schema itself will need to evolve in v2 (ROI/HSV-band fields), but that's a Story 9.9 concern, not 9.4.
- **Story 9.9 (NEW)** — backlog stub. Hand-merge Tool 8's `discovered_zones.{json,yaml}` fragment into `config/config.yaml` + regenerate `apps/mobile/assets/map_config.json` with `schema_version: 2` (ROI/HSV-band schema). Out of V1 scope; larger than one sprint — needs splitting at create-story time.

### Cross-epic impact

- **Story 1.13** (Hybrid `map_config.json` Delivery) — unchanged; still depends on 9.1 only.
- **Story 10.1** (V1 Launch Checklist Deliverable, not yet created) — must NOT include a "9.2 sign-off" row; flagged in `_bmad-output/epics-and-stories.md` follow-ups.
- **Stories 5.x / 6.x / 7.x** (mobile cascade) — orthogonal. The mobile auto-slice path consumes a bundled `map_config.json`; whether that artifact is v1 or v2 is decided at 9.9 closure and doesn't gate mobile feature work.

### Artifact impact (PRD / Architecture / UX)

- **PRD edits this correct-course:** none. Requirements `tooling-WARDEN-001`, `tooling-HASH-001/002`, `tooling-SCHEMA-001` remain valid as-stated; only their V1-validation gates shift. PRD `tooling-HASH-001/002` framing (hash-based map ID) needs a downstream editorial pass once 9.9 ships, but that's not blocking V1.
- **Architecture edits this correct-course:** none. The line at [architecture.md:1505](architecture.md#L1505) describing `mapIdentifier.ts` as "pHash matcher against map_config" needs a downstream editorial pass to reflect the ROI+HSV pivot, but that's a 9.9-time concern. Brownfield Item 7 ([architecture.md:487](architecture.md#L487)) is unchanged — 9.1 still resolves it.
- **UX edits:** N/A. Detection-pipeline tooling has no UX surface.

### Other artifacts

- `sprint-status.yaml` — 9.2/9.3 → `cancelled`; 9.1/9.4 motivation comments; 9.9 → `backlog`; header `last_updated` entry.
- `epics-and-stories.md` — Epic 9 charter amendment; CANCELLED banners on 9.2/9.3; 9.1 motivation update; 9.5–9.9 thin entries.
- `sprint-plan.md` — Track C table edited; Track C-prime added; Inputs line updated.
- Memory entry [project_warden_new_hud_labeler.md] — append 2026-05-14 status block.
- CI / IaC / monitoring: no impact.

---

## 3. Recommended Approach

**Selected: Option 1 — Direct Adjustment (docs-only)**

Effort: **Low.** Risk: **Low.** Three file edits + one new doc + one memory update. No code touched. No in-progress story disturbed (9.1–9.4 are all `backlog`; 9.5–9.8 are `done` or `review`).

**Rationale per story:**

| Story | Disposition | Why |
|---|---|---|
| 9.1 | Keep (motivation updated) | Detection-method-agnostic. `schema_version: 1` is now also the v1 baseline for the v2 partition. |
| 9.2 | Cancel | Validates legacy detector against real footage at ≥95% accuracy; real footage is HUD 2.0 where legacy ROIs don't fire. Tool 9 / Story 9.8 (DONE) is the new-HUD analogue and already validates per-frame. |
| 9.3 | Cancel (not deferred) | Hash-based map identification is being **replaced** by ROI+HSV-band detection (per Stephane 2026-05-14: "i won't use hash to recognise map now it's ROI+ hsv"). Reference-hash regen is structurally moot, not blocked. Work folds into Story 9.9. |
| 9.4 | Keep | jsonschema strict validation is detection-method-agnostic. Schema evolution to ROI/HSV-band fields is a Story 9.9 concern. |
| 9.9 | Add (backlog stub) | Captures the future hand-merge + map_config v2 regen work that 9.3's cancellation displaces. Out of V1 scope; needs splitting at create-story time. |

**Options not selected:**
- Option 2 (Rollback) — N/A; nothing to roll back.
- Option 3 (PRD MVP review) — N/A; MVP is unaffected. V1 launch checklist (Story 10.1, not yet created) loses the "9.2 sign-off" row but no PRD requirement is removed.

---

## 4. Detailed Change Proposals

### Edit 1 — `_bmad-output/sprint-status.yaml`

Flip `9-2-tool-5-warden-analyzer-real-footage-ac-validation: backlog` → `cancelled` (with rationale comment).
Flip `9-3-reference-hash-regression-for-4-awaiting-hash-maps: backlog` → `cancelled` (with rationale comment).
Add motivation comment to `9-1-schema-version-1-add-to-map-config-writers`.
Add motivation comment to `9-4-jsonschema-strict-validation-against-map-config-schema`.
Add `9-9-re-fingerprint-config-for-hud-2-0: backlog` with one-paragraph spec comment.
Prepend new `last_updated` header entry summarizing the correct-course.

### Edit 2 — `_bmad-output/epics-and-stories.md`

Amend Epic 9 goal + add charter-amendment note.
Insert CANCELLED banner above Story 9.2's body.
Insert CANCELLED banner above Story 9.3's body.
Append v2-baseline phrase to Story 9.1's "So that" line.
Append thin pointer entries for Stories 9.5–9.8 + a full skeletal entry for Story 9.9.
Append "Follow-ups flagged by 2026-05-14 correct-course" subsection.

### Edit 3 — `_bmad-output/sprint-plan.md`

Edit Wave 2 Track C table: drop 9.2/9.3 rows, add motivation note to 9.1 row.
Insert "Track C cancellations + additions (2026-05-14 correct-course)" subsection.
Insert "Track C-prime — New-HUD detection chain" subsection with 9.5–9.8 status table.
Update Inputs line at top to reference this proposal doc.

### Edit 4 — Memory: `project_warden_new_hud_labeler.md`

Append a `**Correct-course 2026-05-14:**` block summarizing: 9.2/9.3 cancelled, 9.9 added, Epic 9 charter formally amended, downstream PRD/architecture editorial pass flagged. Cross-link to this proposal doc.

---

## 5. Implementation Handoff

**Scope: Minor.** Executed by the Developer agent (this same workflow run, Step 5).

**Deliverables:**
- This proposal document (`_bmad-output/sprint-change-proposal-2026-05-14.md`).
- 3 file edits per §4 above.
- 1 memory append.

**Success criteria:**
- All 3 file edits land verbatim per Proposals #1–#3.
- This proposal exists at `_bmad-output/sprint-change-proposal-2026-05-14.md`.
- Memory entry `project_warden_new_hud_labeler.md` updated with 2026-05-14 block.
- No PRD / architecture / UX edits in this pass (downstream follow-ups flagged in `epics-and-stories.md` and tracked for the future Story 9.9).

**Out of scope (downstream follow-ups, not blocking V1):**
- PRD `tooling-HASH-001/002` editorial pass to reflect ROI+HSV pivot.
- Architecture line 1505 (`mapIdentifier.ts — pHash matcher`) editorial pass.
- Architecture / PRD `mobile-AUTO-SLICE-002/003` traceability update.
- Story 10.1 V1 launch checklist creation (which must NOT include a "9.2 sign-off" row).
