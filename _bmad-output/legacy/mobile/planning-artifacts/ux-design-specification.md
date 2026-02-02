---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
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

## Design System Foundation

### Design System Choice

**React Native Reusables** (shadcn/ui for React Native) with **NativeWind** (Tailwind CSS for React Native).

Copy-paste component architecture -- components live in the project, not in node_modules. Full ownership, full customization capability.

### Rationale for Selection

- **Dark theme built-in** -- aligns with the "review is play, not work" game-adjacent aesthetic
- **NativeWind / Tailwind utility classes** -- fast iteration, consistent spacing/color tokens
- **Free, open source, active community** -- no licensing constraints, community-driven improvements
- **Copy-paste ownership model** -- no dependency lock-in, components are yours to modify
- **Standard UI components covered** -- buttons, sheets, dialogs, cards, navigation handled out of the box
- **Not Material Design** -- avoids the "Google productivity app" look that conflicts with game-adjacent aesthetic

### Implementation Approach

**Two-tier component strategy:**

| Tier | Scope | Approach |
|------|-------|----------|
| **Standard UI** | Buttons, modals, navigation, lists, cards, forms | React Native Reusables components, themed with custom dark tokens |
| **Custom Core** | Video player, minimap view, POV/minimap toggle, clip creation flow, voice recording, timeline scrubber | Fully custom-built -- this is the product differentiator, no library covers it |

### Customization Strategy

- **Design tokens**: Define dark-first color palette, spacing scale, and typography through NativeWind/Tailwind config
- **Standard components**: Use React Native Reusables defaults, customize theming to match game-adjacent aesthetic
- **Custom components**: Build video player, minimap, clip creation from scratch -- these are the core product and deserve dedicated engineering
- **Progressive customization**: Start with library defaults for non-core UI, refine as the product matures

## Defining Core Experience

### The Defining Interaction

> **"Clip the play, say what happened, send it to the team."**

When a coach describes Warden: "I can make proper review clips on my phone -- I can finally focus on the minimap full-screen, just tap to clip, record my voice if I want, and send it. Done."

The defining experience is **clip creation from minimap mode**. This is what users will describe to friends, what makes them feel productive, and what no other tool provides.

### User Mental Model

Thomas approaches Warden as a **video editing tool** -- not a social app, not a messaging tool. He's cutting footage, marking moments, adding commentary. The UI should respect this mental model:

- **Timeline-centric**: The video timeline is the primary workspace, like a simplified video editor
- **Non-destructive editing**: Clips are selections from the source, not permanent cuts
- **Export-oriented**: The goal is producing artifacts (clips) to share externally
- **Tool, not platform**: Warden produces content that lives elsewhere (Discord, WhatsApp)

**Current workaround**: No dedicated tool exists. Coaches either don't review at all, or try to use generic video players where the minimap is too small to focus on. Feedback stays verbal and ephemeral.

### Success Criteria

| Criteria | Metric |
|----------|--------|
| Clip creation speed | Tap -> 30-second default clip appears -> adjust boundaries -> done. Under 10 seconds to define a clip. |
| Voice feels optional | Adding voice is a clear but non-mandatory step. Silent clips are first-class exports. |
| Minimap readability | Tactical view is full-screen, giving the coach the ability to focus on it. Player positions and movements are clear. |
| Success moment | Thomas has succeeded when the clip is **sent to the team**. Sharing is the finish line, not saving. |
| Resume confidence | Returning to an in-progress review picks up exactly where he left off. |

### Novel UX Patterns

**Established patterns (zero learning curve):**
- Video timeline scrubbing (YouTube)
- Boundary handles for clip selection (every video editor)
- Share sheet for export (OS-native)
- Dark, content-first layout (Discord)

**Novel patterns (Warden-defined):**
- **Full-screen minimap toggle**: No other tool gives full-screen focus to the minimap on mobile. One tap switches between POV and tactical overhead. The icon must be self-explanatory.
- **Auto-generated 30-second clip**: Tap to create a clip with default 30s duration at current position. Drag handles to adjust. Lowers the commitment barrier -- you're refining, not creating from scratch.
- **Voice-over-clip recording**: Scoped to clip creation only. After defining clip boundaries, optional voice recording step. Not a separate feature -- part of the clip flow.

### Experience Mechanics

**1. Initiation -- Creating a clip:**
- Thomas is watching an episode in minimap or POV mode
- He sees a moment worth clipping
- He taps "clip" (or a scissors icon / clip creation button)
- A **30-second clip region** appears centered on the current playback position
- Boundary handles are visible and draggable

**2. Interaction -- Refining the clip:**
- Drag start/end handles to adjust clip boundaries
- Scrub within the clip to preview
- Toggle between POV and minimap to decide which view to export
- Optionally tap "add voice" to record commentary over the clip
- Voice recording plays back the clip while recording the coach's audio

**3. Feedback -- Knowing it's working:**
- Clip region is visually highlighted on the timeline
- Preview plays the exact clip content (what you see is what gets exported)
- Voice waveform appears if audio is recorded
- No ambiguity about what will be exported

**4. Completion -- The finish line:**
- Tap share -> OS share sheet opens -> send to Discord/WhatsApp/etc.
- Success = clip is sent to the team. Thomas has done his part.
- After sharing, return to the timeline at the exact playback position. Flow continues -- momentum, not celebration.

## Visual Design Foundation

### Color System

**Architecture: Config-driven color tokens.** All colors defined in a single configuration file so the entire palette can be swapped without touching component code.

**Base palette (starting point -- swappable via config):**

| Token | Role | Starting Value |
|-------|------|---------------|
| `background` | Primary background | Very dark with subtle cool tint (~#101014) |
| `surface` | Cards, elevated surfaces | Slightly lighter dark (~#1A1A1E) |
| `surfaceElevated` | Modals, sheets | (~#242428) |
| `textPrimary` | Main text | Soft white (~#F0F0F0) |
| `textSecondary` | Subdued text, labels | Muted gray (~#8B8F96) |
| `accent` | Shadows, separators, highlights | Bright orange (~#FF6B00) |
| `accentSubtle` | Faint accent glow, borders | Low-opacity orange (~#FF6B0020) |
| `success` | Clip exported, share complete | Green (~#22C55E) |
| `error` | Failures, warnings, recording dot | Red (~#EF4444) |

**Orange usage philosophy:** Accent color is for **separation and emphasis**, not fills. Orange shadows behind elevated elements, orange tint on active separators, subtle orange glow on selected states. Dark-first with orange as a signature whisper, not a shout.

**Config file approach:** Single source of truth (`theme.config.ts` or equivalent in NativeWind/Tailwind config) -- change the accent color once, the whole app updates.

### Typography System

**System defaults -- platform native:**
- **Android**: Roboto
- **iOS**: SF Pro

**Type scale (minimal):**

| Token | Use | Size |
|-------|-----|------|
| `heading` | Screen titles, episode names | 20sp |
| `subheading` | Section labels, metadata | 16sp |
| `body` | Descriptions, timestamps | 14sp |
| `caption` | Subtle labels, secondary info | 12sp |

Soft white text on dark backgrounds. No thin font weights -- minimum medium weight for readability on OLED screens.

### Spacing & Layout Foundation

**Minimal chrome, reveal-on-tap philosophy:**
- Video takes 100% of screen real estate by default
- Controls appear on tap, auto-hide after inactivity (YouTube fullscreen model)
- No persistent toolbars during playback
- **Double-tap top-left**: Power-user shortcut to toggle minimap/POV (like YouTube double-tap left/right for 10s skip)

**Spacing base unit:** 4px
- Small gap: 4px | Medium gap: 8px | Large gap: 16px | Section gap: 24px

**Layout principles:**
- Content-first: video fills the screen, UI gets out of the way
- Overlay controls: semi-transparent dark background behind revealed controls
- Touch targets: minimum 44x44px for all interactive elements
- Edge margins: 16px safe zone from screen edges

### Accessibility Considerations

**Softened contrast for eye comfort:** Soft white (#F0F0F0) on dark background (#101014) provides ~17:1 contrast ratio (WCAG AAA) without the eye strain of pure white on pure black -- important for late-night couch usage.

**No color-only state indicators -- every state has a shape, icon, or content change as primary signal:**

| State | Primary Indicator | Color Reinforcement |
|-------|------------------|-------------------|
| Clip selected on timeline | Visible **bracket handles** at start/end (draggable shape) | Orange highlight on selected region |
| Minimap mode active | **Video content itself changes** (POV vs tactical overhead) -- self-evident | N/A -- no color indicator needed |
| Voice recording active | **Blinking mic icon + red dot** (animation + icon change) | Red color reinforces but blink + icon are primary |
| Controls visible/hidden | Controls **appear/disappear** on tap | Semi-transparent overlay background |

**Additional accessibility:**
- 44x44px minimum touch targets
- Respect system font size preferences
- Double-tap minimap shortcut has visible button alternative in controls overlay

## Design Direction Decision

### Design Directions Explored

Four layout directions were evaluated:
- **A: Cinema Mode** -- fully immersive, no navigation structure
- **B: Editor Lite** -- persistent timeline, editor feel
- **C: Card Flow** -- browse-then-dive with episode cards + Cinema Mode for review
- **D: Hybrid** -- simple list shell around Cinema Mode

### Chosen Direction

**Direction C: Card Flow + Cinema Mode** -- selected for its natural triage capability and clear separation between navigation and review.

**Two-layer architecture:**

| Layer | Purpose | UX Model |
|-------|---------|----------|
| **Card View (Home)** | Episode triage -- scan results, prioritize which maps to review | Netflix-style grid with map result frames as thumbnails |
| **Cinema Mode (Review)** | Immersive review -- full-screen video, reveal-on-tap controls | YouTube fullscreen with Warden-specific clip creation |

### Card View Details

**Episode cards show:**
- Map result frame as thumbnail (scoreboard/outcome screenshot)
- Map name
- Additional metadata if extractable without performance cost (duration, score, etc.)

**Sorting options (triage-first navigation):**
- **Orange biggest win** -- maps where orange team dominated
- **Blue biggest win** -- maps where blue team dominated
- **Closest map** -- tightest scores, most likely to have critical plays
- **Temporal order** -- chronological (default)

Sorting reorders the card grid AND sets the next/previous episode order within Cinema Mode.

### Cinema Mode Details

**Navigation within Cinema Mode (explicit buttons, no swipe gestures):**
- **Next button** -- go to next episode (follows current sort order)
- **Previous button** -- go to previous episode
- **Maps button** -- return to card view to pick a different episode

**Rationale for buttons over swipe:** Swipe gestures conflict with video scrubbing and timeline interaction. Explicit buttons eliminate accidental navigation and are unambiguous.

**Controls (reveal-on-tap):**
- Video fills 100% of screen by default
- Tap to reveal: play/pause, timeline, minimap toggle, clip button, next/previous/maps navigation
- Double-tap top-left: power-user minimap toggle shortcut
- Auto-hide after inactivity

### Design Rationale

- Card View enables **triage** -- coaches with limited time can prioritize the most important maps first
- Sorting by outcome transforms navigation from "what happened first" to "what matters most"
- Cinema Mode preserves immersion -- once you're reviewing, the video owns the screen
- Button-based navigation prevents gesture conflicts with video controls
- Clear separation: browsing is browsing, reviewing is reviewing -- no hybrid state

### Implementation Approach

- Card View: React Native Reusables card components, themed with dark tokens + orange accent shadows
- Cinema Mode: Fully custom video player with reveal-on-tap overlay system
- Sort state persists across sessions (part of state persistence design)
- Navigation order in Cinema Mode follows the active sort -- next/previous respects the sorted sequence

## User Journey Flows

### Journey 1: Coach Full Review (Thomas)

```
Cold Start → [Resume last / Import new]
                        ↓ (Import new)
         File picker → Processing indicator (auto-slice)
                        ↓ (auto-slice complete)
         Card View: Episode grid with result frames
         [Sort: Orange win / Blue win / Closest / Temporal]
                        ↓ (tap a card)
         Cinema Mode: Full-screen POV playback
         [Tap → reveal controls]
         [Double-tap top-left → minimap shortcut]
                        ↓ (tap clip button)
         30s clip region on timeline → drag handles to adjust
                        ↓ (optional: tap add voice)
         Voice recording over clip playback
                        ↓ (tap export/confirm)
         ┌─────────────────────────────────────────┐
         │ MVP (Option 1): Processing screen,      │
         │ Thomas waits, then share sheet opens     │
         │                                          │
         │ Goal (Option 3): Clip queues for         │
         │ background encoding, Thomas keeps        │
         │ reviewing. Share when ready.             │
         └─────────────────────────────────────────┘
                        ↓ (after share)
         Return to Cinema Mode → next clip
```

**Export processing UX (two-phase design):**

| Phase | Behavior | User Experience |
|-------|----------|----------------|
| **MVP (Option 1)** | Export encodes immediately, Thomas waits | "Preparing clip..." with progress indicator. Share sheet opens when done. Simple, linear. |
| **Goal (Option 3)** | Export queues for background encoding while Thomas keeps reviewing | Subtle clip queue indicator in controls overlay (e.g., "2 ready, 1 processing"). Share from queue when clips are done. |

**Design for upgrade path:** The clip creation flow is identical in both options. The only difference is what happens after "confirm clip" -- wait or continue. UX designed so transitioning from Option 1 to Option 3 requires no UI changes to the clip creation flow itself.

### Journey 2: Interrupted Session (Thomas)

```
Thomas closes app mid-review
         ↓ (hours later)
Cold Start → [Resume last review] / [Import new]
         ↓ (Resume)
Cinema Mode: exact map, exact playback position
Clips in progress preserved, voice recordings intact
         ↓
Continues as if never interrupted
```

**State that persists:**
- Current map/episode and playback position
- Sort order selection
- Any clip definitions in progress (timestamps + voice)
- Export queue status (MVP: n/a. Goal: pending clips resume encoding)

### Journey 3: Passive Player (Lucas)

```
Discord/WhatsApp notification → shared clip in channel
         ↓ (tap)
Inline video playback (no app needed)
         ↓
Full-screen minimap + coach voice plays
Lucas sees his positioning, hears the explanation
         ↓
No install, no account, just understanding
```

**No Warden UX involved.** This journey lives entirely in Discord/WhatsApp. The exported clip must be a standard video file that plays inline on any platform. Warden's UX responsibility ends at the share sheet.

### Journey 4: Active Player Self-Review (Maxime)

```
Cold Start → [Import new]
         ↓
File picker → Processing → Card View
         ↓ (tap a card)
Cinema Mode: toggles between POV and Minimap
         ↓
Watches, analyzes, learns patterns
Can create clips to share with teammates if desired
```

**Identical to coach journey, export is optional.** The value for Maxime is the auto-slicing + full-screen minimap as a convenience tool for personal analysis.

### Journey Patterns

| Pattern | Description |
|---------|-------------|
| **Cold start choice** | Always two clear paths: resume or import new. No blank state. |
| **Card View as hub** | Entry point for all review activity. Triage, sort, pick. |
| **Cinema Mode as workspace** | Full-screen immersion. All review and clip creation happens here. |
| **Export as culmination** | Clip export is the finish line. Share = success. |
| **State persistence everywhere** | Every journey assumes interruption is normal. Nothing is lost. |

### Flow Optimization Principles

1. **Minimum taps to value**: Import -> auto-slice -> tap card -> watching. Four steps from "I have a video" to "I'm reviewing."
2. **Export doesn't break flow**: Whether MVP (wait) or Goal (background), after exporting Thomas is back at the same timeline position, ready for the next clip.
3. **No dead ends**: Every screen has a clear "what's next" action. Card View -> Cinema Mode -> Clip -> Share -> back to Cinema Mode.
4. **Journeys are subsets, not separate flows**: Maxime's journey is Thomas's without export. Lucas's journey is outside the app entirely. One UI serves all users.

## Component Strategy

### Design System Components (React Native Reusables)

| Component | Usage in Warden |
|-----------|----------------|
| **Card** | Episode cards in Card View (themed with dark tokens + orange accent shadow) |
| **Button / IconButton** | All action buttons (clip, share, export, navigation) |
| **Bottom Sheet** | Clip creation panel, voice recording panel, export progress |
| **Dialog** | Confirmations, error messages |
| **Progress** | Export encoding progress bar |
| **Dropdown** | Sort order selection in Card View |
| **Text** | All typography via themed text components |

### Custom Components

#### Video Player (Cinema Mode)

**Purpose:** Full-screen video playback with reveal-on-tap controls overlay. Core workspace for all review activity.

**Content:** Source video (POV or Minimap ROI crop), playback controls, timeline
**Actions:** Play/pause, seek, toggle minimap/POV, create clip, navigate episodes
**States:**
- Clean (video only, no UI)
- Controls visible (tap to reveal, auto-hide after inactivity)
- Clip creation active (timeline shows clip region + handles)
- Voice recording active (blinking mic + red dot)

**Gestures:**
- Single tap: toggle controls overlay
- Double-tap top-left: minimap/POV toggle (power-user shortcut)

#### Timeline Scrubber

**Purpose:** Episode-aware video timeline with playback position and clip region display.

**Content:** Full episode duration, playback position indicator, clip region highlight
**Actions:** Seek by drag, scrub preview
**States:**
- Default (playback position only)
- Clip active (orange highlighted region with bracket handles)

#### Clip Region Selector

**Purpose:** Define clip boundaries on the timeline for export.

**Content:** 30-second default region centered on current playback position
**Actions:** Drag start/end bracket handles to adjust boundaries
**States:**
- Defining (handles visible, region adjustable)
- Locked (boundaries confirmed, ready for voice or export)

**Behavior:** Tap "clip" -> 30s region appears -> drag to refine -> confirm.

#### Voice Recorder

**Purpose:** Record voice commentary over a clip in three optional slots.

**Slots:**

| Slot | Trigger | Visual during recording | Exported result |
|------|---------|------------------------|----------------|
| **Before clip** | Tap "before" | Still frame (first frame of clip) + blinking mic + red dot | Audio over still frame, plays before clip video |
| **During clip** | Tap "on clip" -> countdown -> clip plays | Clip video playing + blinking mic + red dot. If coach keeps talking past clip end, **last frame freezes** while audio continues. | Audio overlaid on clip video + frozen last frame extension |
| **After clip** | Tap "after" | Still frame (last frame of clip) + blinking mic + red dot | Audio over still frame, plays after "during" voice ends |

**Recording control:** Tap to start, **tap to stop**. No auto-stop, no silence detection. Coach controls when he's done.

**All three slots available on same clip.** Coach can use any combination: just "during", all three, or none (silent clip).

**Exported clip structure:**
```
[Before voice + still frame] → [Clip video + during voice] → [Frozen frame + during voice overflow] → [After voice + still frame]
```
All segments optional. Silent clips skip all voice segments.

#### Episode Card

**Purpose:** Display a map/round in the Card View grid with result frame for triage.

**Content:** Static result frame thumbnail (extracted during auto-slice), map name, optional metadata (if performance allows)
**Actions:** Tap to enter Cinema Mode for that episode
**States:**
- Default (dark surface, result frame thumbnail)

#### Sort Dropdown

**Purpose:** Control episode ordering in Card View.

**Content:** Four sort options: Orange biggest win, Blue biggest win, Closest map, Temporal order
**Component:** Standard dropdown input (React Native Reusables, themed)
**Behavior:** Selection reorders Card View grid AND sets next/previous order in Cinema Mode

#### Export Progress

**Purpose:** Show clip encoding status.

**States (MVP - Option 1):**
- Processing: "Preparing clip..." + progress bar
- Complete: share sheet opens automatically

**States (Goal - Option 3):**
- Queue indicator in controls overlay: "2 ready, 1 processing"
- Tap queue to see list, share individual clips when ready

### Component Implementation Strategy

**Phase 1 -- MVP Core (minimum to complete Journey 1):**

| Priority | Component | Rationale |
|----------|-----------|-----------|
| 1 | Video Player | Can't review without it |
| 2 | Timeline Scrubber | Can't navigate within episodes |
| 3 | Episode Card + Card View | Can't select which map to review |
| 4 | Clip Region Selector | Can't create clips |
| 5 | Voice Recorder | Can't add commentary |
| 6 | Export Progress (Option 1) | Can't export clips |
| 7 | Sort Dropdown | Triage capability |

**Phase 2 -- Enhancement:**

| Component | Rationale |
|-----------|-----------|
| Export Queue (Option 3) | Background encoding for momentum |

## UX Consistency Patterns

### Feedback Patterns

| Type | Pattern | Behavior |
|------|---------|----------|
| **Success** | Subtle toast, bottom of screen | Auto-dismiss after 3s. No blocking. Example: "Clip shared" with green accent. |
| **Minor error** | Toast with error styling | Auto-dismiss after 5s. Example: "Export failed -- try again." Red accent. |
| **Critical error** | Modal dialog, blocks UI | Requires user action to dismiss. Example: "Incompatible video format -- only MP4 (H.264) is supported." |
| **Processing (short)** | Inline progress bar | Export encoding: progress bar with percentage. No navigation away until complete (MVP). |
| **Processing (long)** | Full-screen progress with tips | Auto-slice processing: progress bar + rotating tips about app features. |

**Toast rules:**
- Always bottom of screen (doesn't interfere with video controls at top)
- Never stacks -- new toast replaces previous
- Tappable to dismiss early
- No action buttons in toasts -- keep them informational only

### Processing Screen (Auto-Slice)

**During video processing (up to 2 minutes):**
- Full-screen dark background with progress bar and percentage
- Rotating tips cycle every 5-8 seconds:
  - "Double tap the top left corner to instantly switch to minimap mode"
  - "Drag the clip handles to adjust your clip boundaries"
  - "Add voice before, during, or after your clip"
  - "Sort maps by closest score to find the most important rounds"
  - "Your review progress is saved automatically -- pick up where you left off"
- No user action possible during processing -- this is a wait screen
- On completion: auto-navigates to Card View with episodes ready

### Navigation Patterns

| Context | Pattern |
|---------|---------|
| **Cold start** | Two clear paths: "Resume last review" / "Import new session". Always present. |
| **Card View → Cinema Mode** | Tap card, full-screen transition |
| **Cinema Mode → Card View** | "Maps" button in controls overlay |
| **Cinema Mode → Next/Previous** | Explicit buttons in controls overlay, follows sort order |
| **Cinema Mode → Clip creation** | "Clip" button in controls overlay, bottom sheet slides up |
| **Clip creation → Export** | Confirm button in clip bottom sheet |
| **Export → Cinema Mode** | Auto-return to timeline position after share (MVP: after encoding + share) |

**Navigation principle:** Every screen has exactly one "back" path and one or more "forward" paths. No ambiguity, no dead ends.

### Overlay & Bottom Sheet Patterns

| Element | Behavior |
|---------|----------|
| **Controls overlay** | Tap to show, auto-hide after 4s inactivity. Semi-transparent dark background. All Cinema Mode controls live here. |
| **Clip creation sheet** | Bottom sheet, slides up over video. Video stays visible above. Contains: clip handles, voice slot buttons (before/on clip/after), confirm/cancel. |
| **Voice recording overlay** | Replaces clip creation sheet during recording. Shows blinking mic + red dot, clip preview (still frame or playing video depending on slot), tap-to-stop target. |
| **Export progress (MVP)** | Modal overlay, centered. Progress bar + percentage. Cannot dismiss until complete or cancel. |

**Bottom sheet rules:**
- Never covers more than 40% of screen -- video stays visible
- Drag down to dismiss (cancel action)
- Dark surface color with orange accent separator at top

### Loading & Empty States

| State | Visual |
|-------|--------|
| **First launch (no sessions)** | Dark screen with single prominent button: "Import your first training session." |
| **No sessions after deletion** | Same: "Import your last training session." |
| **Auto-slice processing** | Progress bar + rotating tips (see Processing Screen above) |
| **Export encoding (MVP)** | Modal progress bar with percentage |
| **Video loading** | Spinner centered on black background, transitions to video playback when ready |

**Empty state principle:** Always one clear action. Never a blank screen with no guidance.

### Gesture Patterns

| Gesture | Context | Action |
|---------|---------|--------|
| **Single tap** | Cinema Mode (video area) | Toggle controls overlay visibility |
| **Double-tap top-left** | Cinema Mode | Toggle minimap/POV (power-user shortcut) |
| **Drag horizontal** | Timeline scrubber | Seek within episode |
| **Drag handles** | Clip region on timeline | Adjust clip start/end boundaries |
| **Drag down** | Bottom sheet | Dismiss / cancel action |
| **Tap** | Card View (episode card) | Enter Cinema Mode for that episode |

**Gesture principle:** No hidden gestures required for core functionality. Every gesture has a button equivalent. Gestures are shortcuts, not the only path.

## Responsive Design & Accessibility

### Orientation-Adaptive Layout

| Orientation | Video | Controls | Rationale |
|-------------|-------|----------|-----------|
| **Landscape** | Fills 100% of screen | Reveal-on-tap overlay, auto-hide after 4s | Maximum immersion, video dominates |
| **Portrait** | Fills width, positioned at top | **Persistent below the video** -- always visible, NOT overlaid on video | Vertical space available, no reason to hide controls |

**Portrait layout structure:**
```
┌─────────────────────┐
│                     │
│   Video (full width)│
│                     │
├─────────────────────┤
│ Timeline scrubber   │
│ Controls: play/pause│
│ minimap toggle,     │
│ clip, next/prev/maps│
└─────────────────────┘
```

**Landscape layout structure:**
```
┌─────────────────────────────────────┐
│                                     │
│           Video (fullscreen)        │
│                                     │
│    [controls overlay on tap]        │
│                                     │
└─────────────────────────────────────┘
```

Portrait is the more **control-accessible** mode -- everything visible at all times. Landscape is the more **immersive** mode. Both are valid workflows depending on how Thomas is holding his phone.

### Screen Size Variance

| Aspect | Approach |
|--------|----------|
| **Small phones (5.5")** | Card View: single column grid. Cinema Mode: same layout, controls slightly more compact. |
| **Standard phones (6.0-6.4")** | Card View: 2-column grid. Cinema Mode: standard layout. |
| **Large phones (6.5"+)** | Card View: 2-column grid with more metadata visible. Cinema Mode: more breathing room for controls. |

**Scaling rules:**
- Touch targets: always minimum 44x44px regardless of screen size
- Video: always fills available width
- Episode cards: responsive grid, 1 or 2 columns based on width
- Font sizes: respect system font size preferences, minimum body size 14sp

### Accessibility Strategy

**Target: WCAG AA compliance** where applicable to a mobile video review tool.

**What we implement:**

| Area | Implementation |
|------|---------------|
| **Color contrast** | Soft white (#F0F0F0) on dark (#101014) = ~17:1 ratio (exceeds AA 4.5:1). Secondary text (#8B8F96) on dark = ~7:1 (exceeds AA). |
| **Touch targets** | Minimum 44x44px on all interactive elements |
| **No color-only indicators** | All states communicated via shape, icon, or content change (see Visual Design Foundation) |
| **System font scaling** | Respect Android/iOS accessibility font size preferences |
| **Motion sensitivity** | No essential information conveyed through animation alone. Blinking mic uses icon + color, not animation alone. |

**What we intentionally skip:**

| Area | Rationale |
|------|-----------|
| **Screen reader support (TalkBack/VoiceOver)** | Product is inherently visual -- reviewing video footage of VR matches. Screen reader labels provide no meaningful value for this use case. |
| **Audio descriptions** | Video content is user-generated match footage. No audio description possible or meaningful. |
| **Keyboard navigation** | Mobile-only app, no external keyboard use case. |

### Testing Strategy

| Test Type | Approach |
|-----------|----------|
| **Orientation** | Test all screens in both portrait and landscape. Verify controls layout adapts correctly. |
| **Screen sizes** | Test on reference device (Poco X5, 6.67"), small phone (5.5"), and large phone (6.7"+). |
| **Contrast** | Verify all text/background combinations meet WCAG AA (4.5:1 normal text, 3:1 large text). |
| **Touch targets** | Verify 44x44px minimum on all interactive elements, especially timeline handles and overlay controls. |
| **Font scaling** | Test with system font size set to largest -- verify no text truncation or layout breakage. |

### V2 Enhancement: Multi-View Clip Export

**Future capability:** Allow switching between POV and minimap mode *within a single clip export*. The coach could show "here's what you saw" (POV) then cut to "here's what was actually happening" (minimap) in one exported video. This requires multi-segment encoding with view switching at defined timestamps -- deferred to V2 due to FFmpeg complexity.
