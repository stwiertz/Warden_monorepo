---
stepsCompleted: [1, 2, 3, 4, 5]
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

## Desired Emotional Response

### Primary Emotional Goals

The dominant emotion is **purposeful immediacy**: "let's see what went wrong" -- not "let me set up a review session." Warden collapses the gap between intent and action. The coach should be *doing the thing* before they've consciously decided to start.

Secondary emotion is **momentum**: after clipping one moment, the feeling should be "that was fast, let me do the next one" rather than "done, I can close this." Review should feel like scrubbing through a match replay in a competitive game -- quick, purposeful, almost addictive.

### Emotional Journey Mapping

| Stage | Current Reality | Warden Emotion |
|-------|----------------|----------------|
| **Post-session** | "I'll review it later" (procrastination) | "Let's see what went wrong" (immediate purpose) |
| **Opening the app** | N/A -- no tool exists that's worth opening | Cold start: clear choice -- resume last review or import new. Background resume: right where you left off. |
| **Watching footage** | Minimap too small on mobile, only notice highlights | Full-screen tactical view makes patterns visible for the first time |
| **Creating a clip** | Doesn't happen -- feedback stays in the coach's head | See it, say it, send it -- one fluid motion |
| **Sharing** | Verbal, ephemeral, forgotten by next session | Persistent artifact that players can rewatch |
| **Receiving a clip (player)** | Passive, no real learning | First time actually *understanding* tactical positioning |

### Micro-Emotions

- **Confidence over confusion**: Every control is self-explanatory. No learning curve anxiety.
- **Momentum over completion**: Each clip done fuels the next one. Not a checklist to finish.
- **Understanding over entertainment**: The minimap transforms "cool moment" viewing into actual tactical comprehension -- for both coach and player.
- **Trust over skepticism**: State persistence builds trust. The app never loses your work.

### Design Implications

| Emotional Goal | UX Design Choice |
|---------------|-----------------|
| Purposeful immediacy | **Cold start**: two clear paths -- resume last review or import new video. No assumptions, no wizard. **Background resume**: instant return to exact position. |
| Momentum | After exporting a clip, return to the timeline at the exact playback position. Don't break flow with success modals. |
| Tactical understanding | Minimap mode must be **full-screen**, not a tiny overlay. This is the core differentiator -- if it's too small, Warden fails like current tools. |
| Tone neutrality | Clip sharing UX is neutral infrastructure. No "send feedback" or "coach your player" framing. Just "share." The coach's voice carries the tone. |
| Review is play, not work | Dark, game-adjacent aesthetic. Review should feel like postgame analysis in an esport, not filling out a form. |
| Anti-chore | Quick interactions, no mandatory fields, no "save before closing" dialogs. |

### Emotional Design Principles

1. **Intent-to-action in seconds.** The gap between "I want to review" and "I am reviewing" must be near-zero. Cold start gives a clear choice, not a blank screen.
2. **Momentum, not milestones.** Never celebrate completion. Feed the next action.
3. **Full-screen tactical = full understanding.** The minimap is only useful if it dominates the screen. Tiny = useless = current reality.
4. **The voice IS the tone.** Warden doesn't frame, label, or categorize feedback. The coach's voice recording carries whatever authority or casualness fits.
5. **Review is play, not work.** The aesthetic and interaction speed should evoke competitive game analysis, not productivity software.

## UX Pattern Analysis & Inspiration

### Inspiring Products Analysis

**Discord (Primary communication habitat)**
- Dark, content-first UI with zero ceremony -- drop media, people see it
- Inline video playback with tap-to-expand
- No onboarding friction for consuming content
- Warden clips will live here -- the export must feel native to this environment (just a video file, instant playback)

**YouTube (Universal video UX baseline)**
- Scrub bar with preview thumbnails -- users expect this for any video
- Chapter markers / timestamp navigation -- maps to Warden's episode concept
- Double-tap to skip forward/back -- muscle memory for video navigation
- Fullscreen toggle that feels instant -- relevant for orientation-flexible design

**No existing tool for minimap review** -- this is significant. There is no reference product for "tactical overhead view of a VR match with voice commentary." The format itself is novel, which means:
- The minimap clip is inherently curiosity-generating in Discord/WhatsApp
- No UX conventions to follow for this specific interaction -- we define them
- The export format IS the viral hook -- no branding or watermark needed

### Transferable UX Patterns

| Source | Pattern | Warden Application |
|--------|---------|-------------------|
| YouTube | Scrub bar with thumbnails | Timeline scrubbing for episode navigation, visual preview of moments |
| YouTube | Chapter markers | Auto-generated episode markers per map/round |
| YouTube | Double-tap skip | Quick skip gesture for navigating within episodes |
| Discord | Dark UI, content-first | Dark theme, minimal chrome, video dominates the screen |
| Discord | Inline media playback | Exported clips must play inline without friction |
| Netflix | Episode grid navigation | Map/round selection as an episode grid -- immediately understood paradigm |
| Esport replays | Tactical overhead view | Full-screen minimap mode -- but Warden owns this pattern since no tool does it for EVA |

### Anti-Patterns to Avoid

- **Tiny overlay minimap** -- this is literally the current failure mode. If the tactical view isn't full-screen, Warden is just another bad review tool.
- **Export friction** -- no "choose format," "set quality," "add title" before sharing. One tap to share, OS share sheet handles the rest.
- **Onboarding tutorials** -- Discord and YouTube never taught users how to watch a video. Warden shouldn't teach users how to watch a clip. The UI must be self-evident.
- **Social features inside the app** -- Discord is the social layer. Warden is a tool. Don't compete with where users already live.
- **Productivity UX language** -- no "projects," "workspaces," "dashboards." This is match review, not project management.

### Design Inspiration Strategy

**Adopt:**
- YouTube's video navigation conventions (scrub, skip, fullscreen) -- zero learning curve
- Discord's dark, content-first aesthetic -- feels like home for the target audience
- Netflix's episode grid mental model -- maps perfectly to rounds/maps

**Invent:**
- Full-screen minimap toggle -- no reference exists, Warden defines this interaction
- Voice-over-clip creation flow -- scoped, linear, unique to Warden
- Auto-sliced episode presentation -- video imported, episodes appear, no configuration

**Avoid:**
- Any UI pattern that feels like productivity software
- Social features that duplicate Discord
- Tiny tactical overlays that repeat the current failure
