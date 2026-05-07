---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - docs/planning-artifacts/prd.md
  - docs/planning-artifacts/architecture.md
  - docs/planning-artifacts/ux-design-specification.md
workflowType: 'epics'
project_name: 'Warden'
date: 2026-02-02
---

# Warden - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Warden, decomposing the 33 functional requirements, 12 non-functional requirements, and additional architecture/UX requirements into 6 user-value-driven epics with implementable stories.

Each epic delivers standalone user value. Stories within an epic have no forward dependencies -- each story can be completed using only previous stories' output.

## Requirements Inventory

### Functional Requirements

**Video Import & Management**
- **FR1:** Coach can import MP4 video files from device storage
- **FR2:** Coach can view list of imported sessions
- **FR3:** Coach can delete an imported session
- **FR4:** System validates video format at import and displays error if incompatible

**Video Processing**
- **FR5:** System can automatically detect black screen timestamps using keyframe analysis
- **FR6:** System can identify map end screen timestamps using template matching
- **FR7:** System can determine time ranges for each map/round based on detected timestamps
- **FR8:** System can identify and mark lobby segments as excluded from navigation
- **FR9:** System can process 1h20 video in background mode
- **FR10:** System can resume processing if interrupted

**Video Playback & Navigation**
- **FR11:** Coach can navigate between maps using episode-style interface (UI-based on time ranges)
- **FR12:** Coach can play/pause video at any point within allowed time ranges
- **FR13:** Coach can seek within a map segment (time range)
- **FR14:** Coach can toggle between POV view and Minimap view instantly
- **FR15:** Coach can view minimap as cropped ROI from source video

**Audio Commentary**
- **FR16:** Coach can record voice comment before a clip segment
- **FR17:** Coach can record voice comment during playback (overlay)
- **FR18:** Coach can record voice comment after a clip segment
- **FR19:** Coach can delete a recorded comment
- **FR20:** Coach can preview clip with comments before export

**Clip Export**
- **FR21:** Coach can select start/end points for a clip within a map
- **FR22:** Coach can export clip in Mobile quality (720p, fast)
- **FR23:** Coach can export clip in HD quality (source resolution)
- **FR24:** System exports clip as standalone video with embedded audio commentary
- **FR25:** Exported clip is playable without Warden app installed

**Session Persistence**
- **FR26:** System saves session state automatically (current position, comments, clips in progress)
- **FR27:** Coach can resume session exactly where left off
- **FR28:** System persists state across app restarts and device reboots

**User Authentication & Subscription**
- **FR29:** User can log in with Firebase account
- **FR30:** System validates subscription status on login
- **FR31:** System caches auth locally for offline use after initial login
- **FR32:** System periodically re-validates subscription when online
- **FR33:** Non-subscribed users see login screen only (no pricing, no subscribe CTA)

### NonFunctional Requirements

**Performance**
- **NFR1:** Video analysis of 1h20 completes in < 2 minutes (Poco X5 reference)
- **NFR2:** Toggle POV/Minimap in < 100ms
- **NFR3:** Export clip Mobile quality in < 30 seconds per minute of clip
- **NFR4:** UI remains responsive during background processing
- **NFR5:** RAM usage < 2GB during processing

**Reliability**
- **NFR6:** Session state saved every 30 seconds
- **NFR7:** Automatic resume after crash/kill
- **NFR8:** Voice recordings persisted immediately
- **NFR9:** Auth cache valid 30 days offline

**Security**
- **NFR10:** Auth via Firebase (OAuth 2.0)
- **NFR11:** Automatic token refresh
- **NFR12:** No user data stored server-side (privacy by design)

### Additional Requirements

**From Architecture:**
- Starter template: `npx create-expo-app@latest Warden --template blank-typescript` (Epic 1 Story 1)
- Feature-based project structure with 7 feature domains mapped to FR groups
- Hybrid data layer: MMKV (fast state) + SQLite (structured data) + filesystem (audio files)
- FFmpeg via community fork `jdarshan5/ffmpeg-kit-react-native` with Expo config plugin
- OpenCV via `react-native-fast-opencv` (JSI/C++ bindings)
- Video playback via `expo-av` with 100% custom UI
- Zustand stores per feature with MMKV persist middleware
- Service boundaries: shared services as sole access points to native libs
- SQLite schema: sessions, map_segments, clip_exports, audio_comments tables
- Export pipeline: FFmpeg concat multi-segment (still frames + clip video + audio overlay)

**From UX Design:**
- Two-layer architecture: Card View (episode triage) + Cinema Mode (immersive review)
- Dark-first, game-adjacent aesthetic with NativeWind/Tailwind design tokens
- Reveal-on-tap controls in Cinema Mode, auto-hide after 4s inactivity
- Double-tap top-left as power-user minimap toggle shortcut
- Portrait: persistent controls below video. Landscape: overlay controls on tap
- 30-second default clip region centered on current playback position with draggable handles
- Voice recording 3-slot model: before (still frame), during (clip playback + frozen overflow), after (still frame)
- Processing screen with progress bar and rotating tips during auto-slice
- Cold start: two paths -- "Resume last review" or "Import new session"
- Card View sorting: temporal, orange biggest win, blue biggest win, closest map
- Toast feedback (bottom, non-blocking), modal for critical errors
- Minimum 44x44px touch targets, WCAG AA color contrast

### FR Coverage Map

| FR | Epic | Stories |
|----|------|---------|
| FR1 | Epic 2 | 2.1 |
| FR2 | Epic 2 | 2.7 |
| FR3 | Epic 2 | 2.7 |
| FR4 | Epic 2 | 2.1 |
| FR5 | Epic 7 | 7.5 |
| FR6 | Epic 7 | 7.5 |
| FR7 | Epic 2 | 2.5 |
| FR8 | Epic 2 | 2.5 |
| FR9 | Epic 2 | 2.6 |
| FR10 | Epic 2 | 2.6 |
| FR11 | Epic 3 | 3.1, 3.4 |
| FR12 | Epic 3 | 3.2 |
| FR13 | Epic 3 | 3.3 |
| FR14 | Epic 7 | 7.3 |
| FR15 | Epic 7 | 7.3 |
| FR16 | Epic 4 | 4.2 |
| FR17 | Epic 4 | 4.3 |
| FR18 | Epic 4 | 4.4 |
| FR19 | Epic 4 | 4.6 |
| FR20 | Epic 4 | 4.5 |
| FR21 | Epic 4 | 4.1 |
| FR22 | Epic 5 + Epic 7 | 5.1, 7.6 |
| FR23 | Epic 5 + Epic 7 | 5.1, 7.6 |
| FR24 | Epic 5 + Epic 7 | 5.2, 7.6 |
| FR25 | Epic 5 + Epic 7 | 5.2, 7.6 |
| FR26 | Epic 6 | 6.1 |
| FR27 | Epic 6 | 6.2 |
| FR28 | Epic 6 | 6.3 |
| FR29 | Epic 1 | 1.4 |
| FR30 | Epic 1 | 1.5 |
| FR31 | Epic 1 | 1.5 |
| FR32 | Epic 1 | 1.5 |
| FR33 | Epic 1 | 1.4 |

## Epic List

### Epic 1: Project Setup & User Authentication
Coach can install Warden, log in with a Firebase account, and access the app with subscription validation. Non-subscribed users see the login screen only (Reader App model).
**FRs covered:** FR29, FR30, FR31, FR32, FR33

### Epic 2: Video Import & Auto-Slice Processing
Coach can import a training session video and have it automatically sliced into navigable map episodes with lobby segments excluded -- all processed on-device in background mode. Detection methodology (game-state KDA/HSV + pHash map identification) is delivered by Epic 7 / Story 7.5; Epic 2 owns import, keyframe extraction, segment persistence, and processing UX.
**FRs covered:** FR1, FR2, FR3, FR4, FR7, FR8, FR9, FR10 (FR5 and FR6 owned by Epic 7 / Story 7.5)

### Epic 3: Video Playback & Episode Navigation
Coach can navigate between map episodes in a Card View, enter Cinema Mode for immersive full-screen review, and toggle between POV and full-screen Minimap views instantly.
**FRs covered:** FR11, FR12, FR13, FR14, FR15

### Epic 4: Clip Creation & Voice Commentary
Coach can define clip regions on the timeline, record voice commentary in three slots (before, during, after), and preview the assembled clip before export.
**FRs covered:** FR16, FR17, FR18, FR19, FR20, FR21

### Epic 5: Clip Export & Sharing
Coach can export clips as standalone MP4 videos with embedded voice commentary in configurable quality, and share them to Discord/WhatsApp via OS share sheet.
**FRs covered:** FR22, FR23, FR24, FR25

### Epic 6: Session Persistence & Reliability
Coach can close the app mid-review and resume exactly where left off -- same map, same position, voice comments intact, clips in progress preserved.
**FRs covered:** FR26, FR27, FR28

### Epic 7: ROI Detection Redesign & View Mode Expansion
Replace the originally-planned luminosity black-screen detector + OpenCV template matcher with a KDA/HSV-based Game Detector and pHash Map Identifier driven by a Firestore-hosted detection config. Expand the clip `view_mode` from two values (`pov`, `minimap`) to three (`full`, `minimap`, `minimap_hud`) with a two-level UI toggle and corresponding FFmpeg export recipes. **Inserted via Sprint 2.5 per Proposals 4+6 (approved 2026-04-20)** -- supersedes Stories 2.3, 2.4, and 3.5. Full breakdown below.
**Stories:** 7.1 (schema) -- 7.2 (type) -- 7.3 (view-mode UI) -- 7.4 (remote config) -- 7.5 (detectors) -- 7.6 (export pipeline)
**FRs covered:** FR5, FR6, FR14, FR15, FR22, FR23, FR24, FR25 (jointly with Epic 5 for the export FRs)

---

## Epic 1: Project Setup & User Authentication

Coach can install Warden, log in with a Firebase account, and access the app with subscription validation. This epic scaffolds the project foundation and delivers the first usable screen (login). Non-subscribed users see the login screen only, following the Reader App model (no pricing, no subscribe CTA).

### Story 1.1: Initialize Expo Project from Starter Template

As a developer,
I want to scaffold the Warden project using the blank-typescript Expo template,
So that I have a clean, working foundation with TypeScript configured for all subsequent development.

**Acceptance Criteria:**

**Given** no existing project code
**When** the project is initialized with `npx create-expo-app@latest Warden --template blank-typescript`
**Then** the project builds and runs on Android emulator without errors
**And** TypeScript compilation succeeds with strict mode enabled
**And** the project structure follows the architecture document's directory layout (`src/features/`, `src/shared/`, `src/app/`)
**And** `.gitignore` covers node_modules, android/, ios/, .expo/, .env

### Story 1.2: Set Up Navigation and Design System

As a developer,
I want to configure React Navigation, NativeWind with Tailwind design tokens, and React Native Reusables components,
So that all subsequent screens have a consistent dark-first game-adjacent aesthetic and navigation framework.

**Acceptance Criteria:**

**Given** a scaffolded Expo project (Story 1.1)
**When** navigation and styling dependencies are installed and configured
**Then** React Navigation is configured with a root stack navigator
**And** NativeWind is configured with Tailwind design tokens matching the UX spec (background #101014, surface #1A1A1E, accent #FF6B00, text primary #F0F0F0, text secondary #8B8F96)
**And** React Native Reusables base components (Button, Card, Dialog, Toast) are copied into the project and themed with dark tokens
**And** typography tokens are configured (heading 20sp, subheading 16sp, body 14sp, caption 12sp)
**And** minimum touch target size is set to 44x44px in the design system

### Story 1.3: Set Up Data Layer (MMKV + SQLite)

As a developer,
I want to configure MMKV for fast key-value storage and SQLite for structured data,
So that the app has a hybrid persistence layer ready for auth caching, session data, and state persistence.

**Acceptance Criteria:**

**Given** a project with navigation and styling configured (Story 1.2)
**When** MMKV and expo-sqlite are installed and configured
**Then** MMKV instance is initialized with a storage service wrapper in `src/shared/services/storage.ts`
**And** SQLite database is initialized with a database service in `src/shared/services/database.ts`
**And** the `sessions` table is created following the schema from the architecture document
**And** MMKV keys follow dot-notation convention (`auth.token`, `auth.user`, `prefs.*`)
**And** Zustand persist middleware is configured to use MMKV as the storage engine

### Story 1.4: Implement Firebase Login Screen

As a user,
I want to see a login screen where I can sign in with my Firebase account,
So that I can authenticate and access the app.

**Acceptance Criteria:**

**Given** the app is launched and the user is not authenticated
**When** the login screen is displayed
**Then** the user sees email and password input fields and a "Sign in" button
**And** no pricing information, subscription CTA, or payment links are displayed (Reader App model, FR33)
**And** the screen uses the dark-first design system with accent color
**And** error feedback is shown via toast for invalid credentials
**And** successful login navigates to the home screen

### Story 1.5: Implement Subscription Validation and Offline Auth Cache

As a subscribed user,
I want my subscription status validated on login and cached locally for offline use,
So that I can use the app offline after initial authentication for up to 30 days.

**Acceptance Criteria:**

**Given** a user has logged in successfully (Story 1.4)
**When** the login completes
**Then** the system checks `user.isPaid` via Firebase and grants or denies access accordingly (FR30)
**And** auth token and subscription status are cached in MMKV (FR31)
**And** cached auth remains valid for 30 days without network (NFR9)
**And** when the app is online, subscription status is re-validated periodically (FR32)
**And** token refresh happens automatically without user intervention (NFR11)
**And** non-subscribed users are shown only the login screen with no access to app features (FR33)

---

## Epic 2: Video Import & Auto-Slice Processing

Coach can import a training session video and have it automatically sliced into navigable map episodes. The processing pipeline extracts keyframes (Story 2.2), consumes detection output from Epic 7 / Story 7.5 (game-state KDA/HSV + pHash map identification), segments the video into rounds with lobby excluded (Story 2.5), and runs in background mode with crash recovery (Story 2.6) -- all on-device.

Stories 2.3 and 2.4 (the original luminosity black-screen detector and OpenCV template matcher) are SUPERSEDED by Story 7.5 per Proposals 4+6 approved 2026-04-20.

### Story 2.1: Import MP4 Video from Device Storage

As a coach,
I want to import an MP4 video file from my device storage,
So that I can begin reviewing my training session.

**Acceptance Criteria:**

**Given** the coach is on the home screen
**When** the coach taps the import button
**Then** the device file picker opens filtered to video files
**And** the selected file is validated as MP4 (H.264/AAC) format (FR4)
**And** if the format is incompatible, a critical error dialog is shown with a clear message (FR4)
**And** if valid, a new session record is created in SQLite with status `importing`
**And** the video file is referenced in-place (not copied) per architecture spec
**And** the coach is navigated to the processing screen

### Story 2.2: Integrate FFmpeg and Extract Keyframes

As a developer,
I want to integrate the FFmpeg community fork with an Expo config plugin and implement keyframe extraction,
So that the processing pipeline can analyze video frames without decoding the full video.

**Acceptance Criteria:**

**Given** an imported video session (Story 2.1)
**When** keyframe extraction is triggered
**Then** FFmpeg (`jdarshan5/ffmpeg-kit-react-native`) is integrated via a custom Expo config plugin (`plugins/with-ffmpeg.js`)
**And** keyframes are extracted using `-skip_frame nokey` at low resolution to minimize RAM usage (NFR5)
**And** extracted keyframe images are stored in a temporary directory
**And** the FFmpeg service wrapper is located at `src/shared/services/ffmpeg.ts`
**And** RAM usage during extraction stays under 2GB (NFR5)

### Story 2.3: Detect Black Screen Timestamps -- SUPERSEDED

> **⚠ SUPERSEDED by Story 7.5** per Proposals 4+6 (approved 2026-04-20). The standalone luminosity-based black-screen detector is replaced by the KDA/HSV `gameDetector` + 3-state long-GOP `blackScreenDetector` fallback delivered together in Story 7.5. Original acceptance criteria preserved in [docs/stories/2.3.md](../stories/2.3.md) for historical reference.

### Story 2.4: Detect Map End Screens via Template Matching -- SUPERSEDED

> **⚠ SUPERSEDED by Story 7.5** per Proposals 4+6 (approved 2026-04-20). Template matching against bundled map assets is replaced by the pHash-based `mapIdentifier` (64-bit perceptual hash) in Story 7.5; `templateMatcher.ts` and `assets/images/map-templates/` are deleted as part of 7.5. The OpenCV service wrapper at `src/shared/services/opencv.ts` is retained but its purpose shifts to HSV color analysis + pHash computation. Original acceptance criteria preserved in [docs/stories/2.4.md](../stories/2.4.md) for historical reference.

### Story 2.5: Segment Video into Map Episodes

As a system,
I want to consume detection output from Story 7.5 (game-state transitions + map identification) and combine it into navigable map episodes,
So that the coach can navigate the session as distinct rounds/maps.

**Acceptance Criteria:**

**Given** detection output from Story 7.5 (game-on/game-off transitions from `gameDetector` + map identification from `mapIdentifier`)
**When** segmentation runs
**Then** the system determines start/end time ranges for each map/round (FR7)
**And** lobby and between-round segments are identified and marked as excluded from navigation (FR8)
**And** each segment is stored in the `map_segments` SQLite table with session_id, map_index, start_time_ms, end_time_ms, and map_name (from pHash mapIdentifier)
**And** segments where `mapIdentifier` returns no match are stored with `map_name = 'unknown'` but remain navigable
**And** the result frame path is extracted and stored for each segment (scoreboard screenshot for Card View)
**And** the session status is updated to `ready` in SQLite
**And** the pipeline is orchestrated by `src/features/video-processing/processingPipeline.ts`

### Story 2.6: Background Processing with Progress and Crash Recovery

As a coach,
I want video processing to run in the background with a progress indicator,
So that I can see processing status and resume if interrupted.

**Acceptance Criteria:**

**Given** video processing is triggered after import (Story 2.1)
**When** processing begins
**Then** a full-screen processing screen is shown with a progress bar and percentage
**And** rotating tips cycle every 5-8 seconds (per UX spec)
**And** processing runs via Android foreground service with notification (FR9, NFR4)
**And** the UI remains responsive during processing (NFR4)
**And** processing of a 1h20 video completes in < 2 minutes on Poco X5 reference device (NFR1)
**And** if the process is killed or interrupted, state is saved and processing can resume from the last checkpoint (FR10, NFR7)
**And** on completion, the coach is auto-navigated to the Card View

### Story 2.7: Session List and Management

As a coach,
I want to view my imported sessions and delete sessions I no longer need,
So that I can manage my review library.

**Acceptance Criteria:**

**Given** the coach is on the home screen
**When** sessions exist in the database
**Then** the coach sees a list of imported sessions with name and status (FR2)
**And** the coach can delete a session, which removes the session record and associated map_segments, clip_exports, and audio_comments from SQLite (FR3)
**And** deleting a session does not delete the source video file from device storage
**And** the cold start screen shows two paths: "Resume last review" or "Import new session" (per UX spec)
**And** if no sessions exist, a single prominent button says "Import your first training session"

---

## Epic 3: Video Playback & Episode Navigation

Coach can navigate between map episodes in a Card View with result frame thumbnails, enter Cinema Mode for immersive full-screen review, and toggle the view mode (Full / Minimap / Minimap+HUD) instantly. This epic delivers the core review experience. The view-mode toggle UI and Zustand store come from Epic 7 / Story 7.3; this epic wires them into Cinema Mode.

### Story 3.1: Card View with Episode Grid

As a coach,
I want to see my session's map episodes as a visual card grid with result frame thumbnails,
So that I can quickly triage which rounds to review first.

**Acceptance Criteria:**

**Given** a processed session with map segments (Epic 2)
**When** the coach opens the session
**Then** a Card View is displayed as a responsive grid (1 column on small phones, 2 columns on standard/large)
**And** each card shows the map result frame thumbnail, map name, and map index (FR11)
**And** cards are displayed in temporal order by default
**And** tapping a card enters Cinema Mode for that episode
**And** the grid uses React Native Reusables Card components themed with dark tokens and orange accent shadows

### Story 3.2: Cinema Mode Video Player with Controls

As a coach,
I want a full-screen immersive video player with reveal-on-tap controls,
So that I can review footage without UI distractions.

**Acceptance Criteria:**

**Given** the coach has entered Cinema Mode from Card View (Story 3.1)
**When** the video player loads
**Then** the video fills 100% of the screen by default with no visible controls (FR12)
**And** tapping the video reveals controls overlay with semi-transparent dark background
**And** controls auto-hide after 4 seconds of inactivity
**And** controls include play/pause button
**And** in portrait orientation, controls are persistent below the video (not overlaid)
**And** in landscape orientation, controls are revealed on tap
**And** the video player uses `expo-av` with fully custom UI
**And** the player is located at `src/features/video-playback/VideoPlayer.tsx`

### Story 3.3: Timeline Scrubber with Episode-Scoped Seek

As a coach,
I want to scrub through the timeline to seek within the current map episode,
So that I can quickly find specific moments in a round.

**Acceptance Criteria:**

**Given** the coach is in Cinema Mode with controls visible (Story 3.2)
**When** the coach drags the timeline scrubber
**Then** the video seeks to the corresponding position within the current map segment (FR13)
**And** seeking is constrained to the current episode's start/end time range
**And** the timeline shows the full episode duration with a playback position indicator
**And** the scrubber is located at `src/features/video-playback/PlayerControls.tsx`

### Story 3.4: Episode Navigation (Next/Previous/Maps)

As a coach,
I want buttons to navigate between map episodes and return to Card View,
So that I can move through rounds without leaving Cinema Mode unnecessarily.

**Acceptance Criteria:**

**Given** the coach is in Cinema Mode with controls visible (Story 3.2)
**When** the coach taps navigation buttons
**Then** "Next" button loads the next episode in the current sort order (FR11)
**And** "Previous" button loads the previous episode in the current sort order
**And** "Maps" button returns to the Card View
**And** navigation uses explicit buttons (no swipe gestures, to avoid conflicts with timeline scrubbing)
**And** the navigator is located at `src/features/video-playback/EpisodeNavigator.tsx`

### Story 3.5: Full-Screen Minimap Toggle (POV / Minimap) -- SUPERSEDED

> **⚠ SUPERSEDED by Story 7.3** per Proposals 4+6 (approved 2026-04-20). The two-value POV/Minimap toggle is replaced by a three-value toggle (Full / Minimap / Minimap+HUD). The Cinema Mode wiring still happens in Sprint 3, but the toggle components and Zustand store come from Story 7.3 (Sprint 2.5). FR14 and FR15 are now owned by Story 7.3.

### Story 3.6: Card View Sorting

As a coach,
I want to sort the episode cards by different criteria,
So that I can prioritize the most important rounds to review first.

**Acceptance Criteria:**

**Given** the coach is on the Card View (Story 3.1)
**When** the coach selects a sort option from the dropdown
**Then** the grid reorders by the selected criteria
**And** available sort options are: Temporal order (default), Orange biggest win, Blue biggest win, Closest map
**And** the selected sort order also determines next/previous episode order in Cinema Mode
**And** the sort selection persists across sessions via MMKV (`prefs.sortOrder`)
**And** sorting by score requires data from `map_segments.score_orange` / `score_blue` (gracefully degrades if OCR not yet available -- falls back to temporal)

---

## Epic 4: Clip Creation & Voice Commentary

Coach can define clip regions on the timeline, record voice commentary in three optional slots (before, during, after), and preview the assembled clip. This is the defining Warden experience -- where raw footage transforms into coaching feedback.

### Story 4.1: Clip Region Selector with Draggable Handles

As a coach,
I want to define a clip region on the timeline by tapping "clip" and adjusting drag handles,
So that I can select the exact moment I want to share with my team.

**Acceptance Criteria:**

**Given** the coach is in Cinema Mode (Epic 3)
**When** the coach taps the "clip" button in the controls overlay
**Then** a 30-second clip region appears centered on the current playback position (FR21)
**And** the clip region is visually highlighted on the timeline with orange bracket handles
**And** the coach can drag start and end handles to adjust clip boundaries
**And** a clip_exports record is created in SQLite with status `defining`
**And** the clip bottom sheet slides up, showing clip controls, without covering more than 40% of screen
**And** the coach can cancel clip creation by dragging the bottom sheet down

### Story 4.2: Voice Recording - "Before" Slot

As a coach,
I want to record a voice comment that plays before the clip starts,
So that I can provide context before showing the play.

**Acceptance Criteria:**

**Given** a clip region is defined (Story 4.1)
**When** the coach taps the "before" button in the clip creation sheet
**Then** the screen shows the first frame of the clip as a still image (FR16)
**And** a blinking mic icon with red dot indicates recording is active
**And** tap-to-start, tap-to-stop recording control
**And** audio is recorded in AAC (.m4a) format via `expo-av`
**And** the audio file is persisted immediately to filesystem (NFR8)
**And** an audio_comments record is created in SQLite with slot `before` and the file path
**And** after recording, the waveform is displayed in the clip creation sheet

### Story 4.3: Voice Recording - "During" Slot

As a coach,
I want to record a voice comment that plays over the clip video,
So that I can narrate what's happening as the play unfolds.

**Acceptance Criteria:**

**Given** a clip region is defined (Story 4.1)
**When** the coach taps the "on clip" button in the clip creation sheet
**Then** a countdown begins, then the clip plays back while recording audio (FR17)
**And** a blinking mic icon with red dot indicates recording is active
**And** if the coach keeps talking past the clip end, the last frame freezes while audio continues recording
**And** tap-to-stop ends the recording
**And** audio is recorded in AAC (.m4a) format and persisted immediately (NFR8)
**And** an audio_comments record is created in SQLite with slot `during` and the file path

### Story 4.4: Voice Recording - "After" Slot

As a coach,
I want to record a voice comment that plays after the clip ends,
So that I can summarize or give instructions after showing the play.

**Acceptance Criteria:**

**Given** a clip region is defined (Story 4.1)
**When** the coach taps the "after" button in the clip creation sheet
**Then** the screen shows the last frame of the clip as a still image (FR18)
**And** a blinking mic icon with red dot indicates recording is active
**And** tap-to-start, tap-to-stop recording control
**And** audio is recorded in AAC (.m4a) format and persisted immediately (NFR8)
**And** an audio_comments record is created in SQLite with slot `after` and the file path

### Story 4.5: Clip Preview with Voice Commentary

As a coach,
I want to preview my clip with all recorded voice commentary before exporting,
So that I can verify the clip conveys the right message.

**Acceptance Criteria:**

**Given** a clip with one or more voice recordings (Stories 4.2-4.4)
**When** the coach taps "preview" in the clip creation sheet
**Then** the assembled clip plays in sequence: [before voice + still frame] → [clip video + during voice] → [frozen frame + during voice overflow] → [after voice + still frame] (FR20)
**And** segments without voice recordings are skipped (silent clips play video only)
**And** the preview matches what the exported clip will look like
**And** the coach can replay the preview

### Story 4.6: Delete and Re-Record Voice Comments

As a coach,
I want to delete a recorded voice comment and re-record it,
So that I can correct mistakes without recreating the entire clip.

**Acceptance Criteria:**

**Given** a clip with one or more voice recordings (Stories 4.2-4.4)
**When** the coach taps the delete icon on a voice recording in the clip creation sheet
**Then** the audio file is deleted from filesystem (FR19)
**And** the audio_comments record is removed from SQLite
**And** the voice slot becomes available for re-recording
**And** other voice slots on the same clip are not affected

---

## Epic 5: Clip Export & Sharing

Coach can export clips as standalone MP4 videos with embedded voice commentary in Mobile (720p) or HD (source resolution) quality, and share them to Discord/WhatsApp via the OS share sheet. Exported clips are playable without installing Warden. The view-mode-aware FFmpeg recipes (Full / Minimap / Minimap+HUD) come from Epic 7 / Story 7.6; this epic adds the quality-tier plumbing on top.

### Story 5.1: Export Pipeline with Quality Options

As a coach,
I want to export my clip in Mobile quality (720p, fast) or HD quality (source resolution),
So that I can choose between quick sharing and high-quality archival.

**Acceptance Criteria:**

**Given** a clip is defined and optionally has voice commentary (Epic 4)
**When** the coach selects export quality and confirms export
**Then** the clip_exports record status updates to `exporting`
**And** the export dialog presents two quality options: Mobile (720p) and HD (source resolution) (FR22, FR23)
**And** the selected quality is stored in `clip_exports.export_quality`
**And** the FFmpeg export pipeline demuxes the video segment from the source file at the selected quality
**And** export of Mobile quality completes in < 30 seconds per minute of clip (NFR3)

### Story 5.2: Assemble Multi-Segment Clip with Voice Overlay

As a system,
I want to assemble the final exported clip with voice commentary segments overlaid,
So that the exported video is a standalone, self-contained MP4 with embedded audio.

**Acceptance Criteria:**

**Given** a video segment exported at the selected quality (Story 5.1)
**When** the assembly pipeline runs
**Then** the FFmpeg concat pipeline assembles: [before voice + still frame] → [clip video + during voice] → [frozen frame + during voice overflow] → [after voice + still frame] (FR24)
**And** all segments are optional -- silent clips contain only the video segment
**And** the output is a standard MP4 (H.264/AAC) file playable on any device without Warden (FR25)
**And** the clip_exports record status updates to `ready` and `file_path` is set
**And** the pipeline is located at `src/features/clip-export/exportPipeline.ts`

### Story 5.3: Share Exported Clip via OS Share Sheet

As a coach,
I want to share my exported clip directly to Discord, WhatsApp, or other apps,
So that my team receives the feedback instantly.

**Acceptance Criteria:**

**Given** a clip has been exported successfully (Story 5.2)
**When** the export completes
**Then** the OS share sheet opens automatically with the exported MP4 file
**And** the coach can select any installed app to share to (Discord, WhatsApp, etc.)
**And** after sharing, the clip_exports status updates to `shared`
**And** the coach is returned to Cinema Mode at the exact playback position (momentum, not celebration)
**And** sharing uses Expo Sharing API

### Story 5.4: Export Progress Indication

As a coach,
I want to see export progress while my clip is being processed,
So that I know the export is working and how long to wait.

**Acceptance Criteria:**

**Given** an export is in progress (Story 5.1)
**When** the export pipeline is running
**Then** a modal overlay shows "Preparing clip..." with a progress bar and percentage
**And** the coach cannot navigate away until export completes or cancels
**And** cancel option is available to abort the export
**And** on completion, the share sheet opens automatically (Story 5.3)
**And** on failure, an error toast is shown: "Export failed -- try again"

---

## Epic 6: Session Persistence & Reliability

Coach can close the app mid-review and resume exactly where left off -- same map, same position, same sort order, voice comments intact, clips in progress preserved. State persists across app restarts, device reboots, and crash recovery.

### Story 6.1: Auto-Save Session State Every 30 Seconds

As a system,
I want to automatically save the coach's review state every 30 seconds,
So that minimal work is lost if the app is interrupted.

**Acceptance Criteria:**

**Given** the coach is actively reviewing a session (Epics 3-5)
**When** 30 seconds have elapsed since the last save
**Then** the system persists current state to MMKV (FR26, NFR6):
  - Current session ID
  - Current map/episode index
  - Playback position (timestamp)
  - Active view mode (POV or Minimap)
  - Sort order selection
  - Any clip in progress (defining/locked status and boundaries)
**And** the auto-save operates silently with no UI indication
**And** the auto-save service is located at `src/features/session/autoSaveService.ts`

### Story 6.2: Resume Session Exactly Where Left Off

As a coach,
I want to resume my review session exactly where I left off,
So that interruptions don't break my review flow.

**Acceptance Criteria:**

**Given** the coach has a previously saved session state (Story 6.1)
**When** the coach opens the app and selects "Resume last review"
**Then** the app restores the exact map/episode and playback position (FR27)
**And** the view mode (POV/Minimap) is restored
**And** the sort order is restored
**And** any clips in progress with their voice recordings are intact
**And** the coach can continue reviewing as if never interrupted

### Story 6.3: Persist State Across App Restarts and Reboots

As a coach,
I want my review state to survive app restarts, force closes, and device reboots,
So that I can trust Warden to never lose my work.

**Acceptance Criteria:**

**Given** a saved session state in MMKV (Story 6.1) and structured data in SQLite
**When** the app is force-closed, the device is rebooted, or the app crashes
**Then** on next launch, the cold start screen offers "Resume last review" with the saved session (FR28)
**And** all SQLite data (sessions, map_segments, clip_exports, audio_comments) survives restart
**And** all MMKV cached state survives restart
**And** all audio files on filesystem survive restart
**And** if the previous session was mid-processing, processing resumes from the last checkpoint (NFR7)

---

## Epic 7: ROI Detection Redesign & View Mode Expansion

Replace the originally-planned luminosity black-screen detector + OpenCV template matcher with a KDA/HSV-based game-state detector and a pHash-based map identifier, driven by a Firestore-hosted detection config with MMKV cache + offline fallback. Simultaneously expand the clip `view_mode` data model from two values (`pov`, `minimap`) to three (`full`, `minimap`, `minimap_hud`) with a two-level UI toggle and corresponding FFmpeg export recipes.

**Inserted into the plan via Sprint 2.5 per Proposals 4+6 (approved 2026-04-20).** This epic supersedes Stories 2.3, 2.4, and 3.5 from the original Epic 2/3 breakdown.

### Story 7.1: Update clip_exports.view_mode SQLite Schema

As a developer,
I want to update the `clip_exports.view_mode` CHECK constraint to accept three values,
So that the data model supports Full / Minimap / Minimap+HUD export variants.

**Acceptance Criteria:**

**Given** the existing SQLite schema with `view_mode CHECK(view_mode IN ('pov', 'minimap'))`
**When** Story 7.1 lands
**Then** the CHECK constraint is updated to `view_mode IN ('full', 'minimap', 'minimap_hud')`
**And** existing rows with `view_mode = 'pov'` are migrated to `view_mode = 'full'`
**And** the schema version is bumped and migration is idempotent + reversible
**And** Story 7.1 ships in the same PR as Story 7.2 (data + type alignment)

### Story 7.2: Update ClipExport.view_mode TypeScript Type

As a developer,
I want to update the TypeScript `ViewMode` union type to match the new SQLite CHECK constraint,
So that the type system enforces the same three values across the codebase.

**Acceptance Criteria:**

**Given** the existing `ClipExport.view_mode: 'pov' | 'minimap'` union
**When** Story 7.2 lands
**Then** the union becomes `'full' | 'minimap' | 'minimap_hud'`
**And** a named `ViewMode` type alias is exported from `src/features/clip-export/types.ts`
**And** the codebase is audited for `'pov'` literal occurrences and migrated
**And** Story 7.2 ships in the same PR as Story 7.1

### Story 7.3: View Mode Toggle UI (Full / Minimap / Minimap+HUD)

As a coach,
I want a two-level toggle in Cinema Mode (top-level Full/Minimap and a HUD overlay sub-toggle),
So that I can switch between three view modes -- Full, Minimap, Minimap+HUD -- instantly.

**Acceptance Criteria:**

**Given** the coach is in Cinema Mode with controls visible
**When** the coach taps the view-mode toggle
**Then** the view switches to the selected mode (FR14, FR15)
**And** the toggle completes in < 100ms (NFR2) via crop/overlay style change on the same video source
**And** the HudToggle is only active when the top-level toggle is set to `minimap`
**And** the selected `viewMode` and `minimapHud` preferences persist via Zustand + MMKV (`prefs.viewMode`, `prefs.minimapHud`)
**And** the components are located at `src/features/video-playback/ViewModeToggle.tsx` and `src/features/video-playback/HudToggle.tsx`
**And** Story 7.3 SUPERSEDES Story 3.5 from the original Epic 3 breakdown

### Story 7.4: Remote Detection Config with MMKV Cache

As a developer,
I want detection parameters (ROIs, thresholds, map pHash fingerprints) to be served from Firestore with a local MMKV cache and offline fallback,
So that detection accuracy can be tuned without app updates and the app still works offline.

**Acceptance Criteria:**

**Given** the app is online and a `DetectionConfig` document exists in Firestore
**When** the app launches or processing starts
**Then** the latest config is fetched from Firestore and cached in MMKV under `detection.config`
**And** if Firestore is unreachable, the cached MMKV config is used
**And** if no MMKV cache exists, a bundled default config (shipped with the app) is used
**And** config version is checked and stale caches are refreshed on next online launch
**And** the config schema includes ROI definitions, KDA/HSV thresholds, and map pHash fingerprints
**And** the service is located at `src/features/video-processing/detectionConfig.ts`
**And** Story 7.4 lands as a no-op shim until Story 7.5 consumes the config

### Story 7.5: Replace Detectors (Game Detector + pHash Map Identifier)

As a system,
I want a new `gameDetector` (KDA/HSV-based 2-state machine) and `mapIdentifier` (pHash-based) replacing the original luminosity black-screen detector and OpenCV template matcher,
So that game-state transitions and map identification are accurate enough to power Sprint 2/3 segmentation and navigation.

**Acceptance Criteria:**

**Given** keyframes extracted from a session video (Story 2.2) and detection config (Story 7.4)
**When** detection runs
**Then** `gameDetector.ts` (KDA/HSV 2-state machine) flags game-on / game-off transitions on each keyframe (FR5)
**And** `mapIdentifier.ts` computes a 64-bit pHash from each game-on keyframe and matches it against config-supplied fingerprints to identify the map (FR6)
**And** the original `blackScreenDetector` is refactored to a 3-state long-GOP fallback only -- invoked when `gameDetector` is uncertain due to keyframe gaps
**And** `templateMatcher.ts` and `assets/images/map-templates/` are deleted from the codebase
**And** the OpenCV service wrapper (`src/shared/services/opencv.ts`) is retained but its purpose shifts to HSV analysis + pHash computation
**And** detection output (transitions + map identification) is consumed by Story 2.5 segmentation
**And** Story 7.5 SUPERSEDES Stories 2.3 and 2.4 from the original Epic 2 breakdown

### Story 7.6: Export Pipeline for 3 View Modes

As a developer,
I want FFmpeg recipes for the three view modes (Full / Minimap / Minimap+HUD) plus a shared export-pipeline orchestrator,
So that Sprint 5 quality-tier plumbing (Stories 5.1, 5.2) layers cleanly on top.

**Acceptance Criteria:**

**Given** a clip definition with `view_mode` set to one of `full | minimap | minimap_hud` (Stories 7.1, 7.2)
**When** export runs
**Then** `exportRecipes.ts` provides three FFmpeg recipe builders:
  - `full`: no crop, source resolution
  - `minimap`: crop to map ROI from detection config
  - `minimap_hud`: minimap crop + KDA + Score overlays drawn from `map_segments` data
**And** `exportPipeline.ts` orchestrates: select recipe by view_mode -> demux -> process -> mux with audio overlays
**And** the recipes are tested headless via FFmpeg dry-run (no full encode in tests)
**And** Story 7.6 SUPERSEDES the view-mode-aware export portion of Stories 5.1 and 5.2; those stories now layer Mobile/HD quality tiers on top of Story 7.6's recipes
**And** the modules are located at `src/features/clip-export/exportRecipes.ts` and `src/features/clip-export/exportPipeline.ts`
