---
stepsCompleted: [1, 2, 3]
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

## Core User Experience

### Defining Experience

The core loop is: **Navigate to round -> Review with minimap -> Create clip with voice -> Share.** Every design decision orbits this sequence. The product's value is realized when a coach exports a minimap clip with voice commentary -- that artifact is what makes Warden irreplaceable.

The core action is **clip creation with minimap + voice**. This is where raw footage transforms into coaching feedback. Everything before it (import, auto-slice, navigation) is setup; everything after it (export, share) is delivery. The clip creation moment is the product.

### Platform Strategy

- **React Native, Android-first**, touch-based mobile app
- **100% on-device processing** -- no network dependency for core functionality
- **No orientation lock** -- landscape is the optimal review workflow, but portrait must be fully functional (couch usage = unpredictable grip)
- **Offline-first architecture** -- videos live on device, exports are local files shared through OS share sheet
- **Reader experience via standalone clips** -- no app install needed for recipients (Lucas persona)

### Effortless Interactions

| Interaction | Design Goal |
|------------|------------|
| Auto-slicing | Invisible. User imports a video, sees episodes. No configuration, no "processing" modal to stare at. The result just appears. |
| Episode navigation | Netflix-style. Maps/rounds are immediately browsable. The coach's mental model (round 1, round 2...) IS the navigation model. |
| Minimap toggle | **Explicit, self-explanatory icon.** Not an abstract symbol -- the icon should visually suggest "tactical overhead view." One tap, instant switch. No animation delay. |
| Voice recording | Scoped to clip creation flow only. Not a floating button. Coach selects a moment -> creates clip -> records voice. Linear, predictable. |
| State persistence | Invisible. Close the app mid-review, come back tomorrow, everything is exactly where you left it. Zero friction resume. |

### Critical Success Moments

1. **The "aha" moment (first-time):** Coach toggles to minimap mode, sees the tactical overhead of a play, records a voice comment, exports the clip -- and realizes "THIS is what I can send my players." The minimap + voice clip is the product's proof of value.
2. **The share moment:** The exported clip plays on any device without Warden installed. The player watches it on Discord/WhatsApp and actually *understands* the feedback. No more "rewatch minute 47."
3. **The resume moment:** Coach closes mid-session, reopens hours later, everything is intact. Trust is built through reliability.

### Experience Principles

1. **The clip is the product.** Every feature exists to make minimap + voice clips easy to create and share. If a feature doesn't serve this, question it.
2. **Mirror the coach's mental model.** Rounds/maps as episodes. Tactical view as default analysis mode. Voice as natural coaching language. Don't make Thomas learn a new way to think.
3. **Invisible infrastructure.** Auto-slicing, on-device processing, state persistence -- the user never sees the machinery. They see results.
4. **Progressive revelation.** Import -> auto-slice -> watch works on day one. Minimap, voice clips, batch export reveal themselves through natural exploration.
5. **No orientation, no friction.** Work in any grip, any position. The couch is our design lab.
