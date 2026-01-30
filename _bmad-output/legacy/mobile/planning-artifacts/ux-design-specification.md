---
stepsCompleted: [1, 2]
inputDocuments:
  - docs/planning-artifacts/product-brief-warden-2026-01-26.md
  - docs/planning-artifacts/prd.md
  - docs/planning-artifacts/brainstorming-synthesis-2026-01-26.md
  - docs/brainstorming/brainstorming-session-2026-01-26.md
  - docs/planning-artifacts/architecture.md
date: 2026-01-30
author: Sally (UX Designer)
project_name: Warden
---

# UX Design Specification Warden

**Author:** Sally (UX Designer)
**Date:** 2026-01-30

---

## Executive Summary

### Project Vision

Warden is a mobile-first match review application for EVA After-h (competitive VR). The core insight: coaches invest money in sessions but lose most learning value because reviewing footage with generic tools is too painful. Warden makes review so frictionless it becomes a habit -- a "Double XP" bonus for real life.

The killer differentiator is **100% on-device processing**: no uploads, no cloud costs, no waiting. Import a 1h20 video, get it auto-sliced into map episodes in under 2 minutes, toggle a tactical minimap view, drop voice comments, and export standalone clips that anyone can watch without installing the app.

### Target Users

| User | Role | Relationship to Warden |
|------|------|----------------------|
| **Thomas (Coach)** | Creates reviews, power user | Pays for subscription. Reviews from his couch after sessions. Needs unified workflow, not 3 different apps. |
| **Lucas (Passive Player)** | Receives clips | Never installs Warden. Gets standalone clips via Discord/WhatsApp. The "proof" that eliminates denial. |
| **Maxime (Active Player)** | Self-reviews + imports coach reviews | Has the app. Pipeline: passive -> active -> future coach. |

### Key Design Challenges

- **Fragmented usage sessions**: Thomas reviews in 5-10 minute bursts from his couch. State persistence and instant resume are critical -- if he loses his work, he won't come back.
- **Voice-first in a visual medium**: Recording comments before/during/after clips while navigating video is a complex interaction that needs to feel effortless, especially for a tired coach.
- **Two views, one mental model**: The POV/Minimap toggle needs to feel like flipping a coin, not switching apps. The coach thinks in tactical terms but watches in first-person.
- **Reader App constraint**: No pricing, no subscribe button in the app. The onboarding must convey value without any commercial friction -- pure utility from first launch.

### Design Opportunities

- **"Netflix for match review"**: The episode-style navigation by map is an immediately understood paradigm. Coaches already think in rounds/maps -- the UI should mirror their mental model perfectly.
- **Zero-install feedback loop**: Standalone clips that play anywhere create a viral loop. Each clip is a mini-advertisement for Warden's value.
- **Progressive complexity**: Start simple (import -> auto-slice -> watch), let coaches discover power features (minimap, voice, batch export) naturally. Don't front-load complexity.
