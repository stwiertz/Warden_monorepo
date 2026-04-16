# Sprint Change Proposal — 2026-04-16

**Trigger:** Epic 4 Retrospective (2026-04-16)
**Scope classification:** Moderate — backlog reorganization affecting Epic 5 + new Epic 7
**Status:** Approved and applied

## Section 1: Issue Summary

Two planning changes emerged from the Epic 4 retrospective:

1. **Epic 5 scope reduction (portal-first):** Stripe best-practices consultation revealed that Stories 5.2 (Payment History), 5.3 (Upgrade monthly→yearly), and 5.4 (Cancel Subscription) duplicate functionality Stripe Customer Portal provides natively. Root directed: "delegate to Stripe everything I can." This eliminates ~2 stories of custom UI development while delivering identical user capabilities.

2. **Launch-readiness epic (Epic 7):** Three retro items carried unresolved from Epics 2–3 (Firestore rules deployment, Firebase auth E2E, PlanCta hydration fix) need a dedicated epic with first-class priority rather than perpetual deferral. Combined with Root's desire for a guided payment lifecycle walkthrough and Stripe production activation (external dependency: company number).

## Section 2: Impact Analysis

### Epic Impact

| Epic | Impact | Details |
|------|--------|---------|
| Epic 4 | None | Complete (3/3 stories done) |
| Epic 5 | Major scope revision | Reduced from 5 stories to 3 (portal-first approach) |
| Epic 6 | None | Legal/compliance scope unchanged |
| Epic 7 | New | Launch readiness — absorbs carried retro items + production verification |

### Story Impact

**Removed stories:**
- ~~5.2: Payment History~~ → delegated to Stripe Customer Portal
- ~~5.3: Upgrade from Monthly to Yearly Plan~~ → delegated to Stripe Customer Portal
- ~~5.4: Cancel Subscription~~ → delegated to Stripe Customer Portal

**Revised stories:**
- 5.1: Dashboard with Account & Subscription Overview — added "no `onSnapshot`" constraint
- 5.2 (new): Stripe Customer Portal Integration — server-side portal session creation, "Manage Subscription" button, return URL
- 5.3 (new): Payment Failure Warning Banner — `past_due` and `canceled` state banners with CTAs

**New stories (Epic 7):**
- 7.1: Firestore Security Rules Deployment
- 7.2: Firebase Auth E2E & PlanCta Hydration Fix
- 7.3: Guided Payment Flow E2E Testing
- 7.4: Stripe Production Activation & Go-Live

### Artifact Impact

| Artifact | Changes |
|----------|---------|
| epics.md | Epic 5 revised (3 stories), Epic 7 added (4 stories), FR coverage map updated |
| sprint-status.yaml | Epic 5 story keys updated, Epic 7 entries added |
| PRD | No changes — all FRs still delivered (FR17–19 via portal) |
| Architecture | No changes — portal simplifies dashboard; architecture doc updates deferred to implementation |

## Section 3: Recommended Approach

**Selected: Direct Adjustment**

- Epic 5 is in backlog — no implemented code affected
- Changes are purely planning artifact edits
- Portal-first approach reduces scope by ~2 stories while delivering all FRs
- Epic 7 formalizes carried debt into a planned epic with clear stories
- Zero risk, significant simplification

## Section 4: Detailed Changes Applied

### epics.md
- Epic 5 header updated with "(Portal-First)" suffix and approach description
- Stories 5.2–5.4 replaced with new 5.2 (Portal Integration) and 5.3 (Warning Banner)
- FR coverage map annotations added for FR17, FR18, FR19 (via Stripe Customer Portal)
- Epic 7 section added with 4 stories (7.1–7.4)
- Epic 7 listed in epic summary section

### sprint-status.yaml
- Epic 5 story keys updated to match revised stories
- Epic 7 entries added with all 4 stories in backlog

## Section 5: Implementation Handoff

**Scope:** Moderate — backlog reorganization applied directly by SM

**Changes applied by:** SM (this workflow execution)
**No further handoff required** — artifacts are updated and ready for story creation when Epic 5 begins.

**Next steps:**
1. Begin Epic 5 with Story 5.1 (dashboard overview) when ready
2. Configure Stripe Customer Portal in Stripe Dashboard before Story 5.2
3. Diagnose Vitest parallelism flake before Epic 5 starts (action item from retro)
4. Root to obtain company number before Epic 7, Story 7.4
