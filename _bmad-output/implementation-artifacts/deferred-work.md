# Deferred Work

Cross-story register of items deliberately deferred — pre-existing issues, out-of-scope findings, and items the team consciously decided to address later.

Each entry: bullet with the finding + brief reason.

---

## Deferred from: code review of 0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work (2026-05-09)

- **AC 11 verbatim sentence not actually verbatim across all artifacts** — `_bmad-output/sprint-plan.md:1100` paraphrases the gate-block sentence (uses `Per Decision #ES-3, Stories 0.1 → 0.2 must close before any Sprint 3 story merges to main`) instead of the AC11-mandated verbatim text. AC 11 only binds the audit file (which does match exactly); sprint plan is reference text. Defer until next sprint-plan touch.
- **Scope-creep: PR #1 bundled unrelated docs work outside Story 0.1's declared File List** — Story 0.1's File List names 3 files; PR diff touches 7 (added: implementation-readiness-report-2026-05-09.md, sprint-plan.md; modified: architecture.md, epics-and-stories.md). Already shipped — flag for sprint retro / process learning, not corrective action.
- **Epics-and-stories file's status divergence on 7.4 / 7.5 persists post-PR** — `_bmad-output/epics-and-stories.md` Epic 0 Implementation Notes still claims 7.4 = `ready-for-dev` (legacy file says `done`) and 7.5 = `ready-for-dev` (legacy file says `in-progress`). The audit calls this stale but ships it stale. Story 0.2 owns the disposition tags on legacy files; epics-file status fixup belongs to a separate cleanup pass.
- **Story 2.7 CASCADE claim not grep-verified against `database.ts`** — Audit row for 2.7 asserts ON DELETE CASCADE for `map_segments` / `clip_exports` / `audio_comments` without a direct grep against `apps/mobile/src/shared/services/database.ts`. Story 0.1 AC explicitly delegates verification to Stephane's manual review step, so this is process-correct — but worth noting if anyone later needs the CASCADE evidence.
- **Audit Rule A negative-find evidence (zero `IAP` / `free-tier` / `cloud-encode` hits) not recorded in Debug Log References** — Story 0.1 Dev Notes describe the trigger-word search as the method; the Debug Log records "read fully" but no grep evidence. Process artifact (would strengthen reviewer-skepticism counter-evidence on a future audit) but not deliverable content.
