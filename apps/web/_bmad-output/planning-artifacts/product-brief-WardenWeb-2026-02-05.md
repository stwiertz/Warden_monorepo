---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: ['_bmad/brainstorming/brainstorming-session-2026-02-05.md']
date: 2026-02-05
author: Developer
workflow_completed: true
---

# Product Brief: WardenWeb

## Executive Summary

Warden is a mobile video review app built specifically for EVA After-h coaches that transforms paid training sessions into accelerated learning opportunities — like a "Double XP" bonus for team development. By auto-slicing hour-long sessions into map-based episodes, offering a unique tactical minimap view, and enabling voice-first commentary from the couch, Warden eliminates the friction that causes coaches to abandon review entirely.

WardenWeb serves as the subscription management portal ("Reader App" model), enabling coaches to subscribe via Stripe while bypassing app store fees, and providing a professional web presence for Discord-based marketing and word-of-mouth discovery.

**Tagline:** _Progresser plus vite en investissant moins de temps_ (Progress faster by investing less time)

---

## Core Vision

### Problem Statement

EVA After-h sessions are paid experiences, yet without structured review, teams "play" without truly "training" — relying on raw experience to progress, which is slow and frustrating. The same mistakes repeat match after match.

### Problem Impact

Coaches currently face an impossible workflow:

- Juggling multiple tools (video player + notes + editing software)
- Generic editing software is complex and overkill for the task
- YouTube clips lack tactical context (no minimap view)
- EVA Battle Plan has upload delays, token costs, and underutilized stats
- **The review process is so heavy that coaches abandon it entirely**

### Why Existing Solutions Fall Short

EVA Battle Plan (primary competitor) requires cloud uploads with delays, charges tokens per analysis, and provides stats that go underutilized. Generic video editing tools are overkill for a coach who just wants to create quick clips with commentary after work.

### Proposed Solution

Warden processes replays entirely on-device with EVA-specific optimizations:

- **Auto-slice by map** — Black screen detection + template matching splits 1h20 sessions in under 2 minutes
- **Unique Minimap View** — Toggle instantly between POV and tactical overhead (no competitor offers this)
- **Voice-first commentary** — Record before, during, and after clips from the couch
- **Standalone clip export** — Players receive MP4s via Discord/WhatsApp without installing any app
- **100% on-device** — No uploads, no cloud costs, works completely offline

### Key Differentiators

| Feature           | Why It Matters                                            |
| ----------------- | --------------------------------------------------------- |
| EVA-Specialized   | Pre-configured templates and detection for EVA After-h    |
| Minimap Mode      | Unique tactical overhead view — no competitor offers this |
| 100% On-Device    | No uploads, fixed costs, works offline                    |
| Voice-First       | Minimal friction for a tired coach on the couch           |
| Standalone Export | Players don't need the app to receive feedback            |

---

## Target Users

### Primary Users

#### The Coach — Thomas, 26

**Profile:**
Thomas is an EVA After-h coach who plays weekly sessions with his team. After work, he reviews the recorded gameplay from his couch, wanting to create quick clips with commentary to share with his players. He's tired of juggling generic video editors and abandoned complex solutions like EVA Battle Plan.

**Context & Motivation:**

- Reviews sessions after work, typically tired and relaxing
- Wants lightweight, EVA-specific workflow with minimal friction
- Needs to create clips quickly and share via Discord/WhatsApp
- Values his time — won't tolerate heavy setup or per-use costs

**Current Pain:**

- Generic editing tools are overkill
- EVA Battle Plan requires uploads, tokens, waiting
- Process is so heavy he often skips review entirely

**Success Vision:**
"I can slice my 1h20 session into maps, jump to the round we lost, record my voice-over, and send a clip to the team — all in under 10 minutes from my couch."

---

### Secondary Users

#### Passive Player

**Profile:**
Team members who receive clips from their coach. They watch MP4s shared via Discord/WhatsApp without installing any app.

**WardenWeb Interaction:**

- May visit the landing page out of curiosity
- Sees the value proposition and considers becoming an Active Player
- **Conversion opportunity** — passive recipients can become paying subscribers

#### Active Player

**Profile:**
Players who want to self-analyze their gameplay and develop their own coaching skills. May have converted from Passive Player after seeing valuable clips from their coach.

**WardenWeb Interaction:**

- Subscribes individually (no team billing)
- Manages own account and payment
- Uses the minimap view to develop tactical understanding

---

### User Journeys (WardenWeb)

#### Coach Discovery & Subscription Journey

```
Discord tip / Word-of-mouth
        ↓
Receives coupon link
        ↓
Lands on WardenWeb pricing page
        ↓
Creates account (Google / Email)
        ↓
Enters payment info ("You won't be charged until [date]")
        ↓
Downloads app, tries Warden with coupon period
        ↓
Finds value → Subscription continues
        ↓
Returns to WardenWeb for: billing, upgrade to yearly, redeem new coupon, cancel
```

#### Passive → Active Conversion Journey

```
Receives clip from coach (MP4 via Discord)
        ↓
Impressed by quality / minimap view
        ↓
Visits WardenWeb landing page (curiosity)
        ↓
Understands value proposition
        ↓
Decides to analyze own sessions
        ↓
Subscribes as Active Player
```

---

## Success Metrics

### User Success Metrics (Warden App)

| Metric              | Target       | Why It Matters                    |
| ------------------- | ------------ | --------------------------------- |
| First clip exported | < 5 minutes  | Activation — proves value quickly |
| Reviews per week    | 1+ per coach | Engagement — habitual use         |
| Clips per review    | 3-5          | Depth — meaningful analysis       |

### Business Objectives

| Metric         | Target | Timeframe |
| -------------- | ------ | --------- |
| Paying coaches | 20     | 3 months  |
| Churn rate     | < 15%  | Monthly   |

### WardenWeb Funnel KPIs

| Stage          | Metric                        | Purpose                                           |
| -------------- | ----------------------------- | ------------------------------------------------- |
| **Awareness**  | Landing page visits           | Measures reach of Discord/word-of-mouth marketing |
| **Interest**   | Pricing page views            | Visitors exploring subscription options           |
| **Intent**     | Checkout initiated            | Users who start payment process                   |
| **Drop-off**   | Checkout abandonment rate     | Users who start but don't complete payment        |
| **Conversion** | Coupon → Paid conversion      | Trial users becoming paying subscribers           |
| **Expansion**  | Monthly → Yearly upgrade rate | Users committing long-term                        |

### Key Ratios to Track

- **Visit → Checkout Start**: % of landing page visitors who initiate payment
- **Checkout Start → Complete**: % of payment initiations that succeed
- **Coupon → Retained**: % of coupon users still subscribed after trial ends

---

## MVP Scope

### Core Features (V1)

| Feature                | Description                                                                         | Priority  |
| ---------------------- | ----------------------------------------------------------------------------------- | --------- |
| **Landing Page**       | Value proposition, app description, CTA to pricing                                  | Must have |
| **Pricing + Checkout** | Single page: €7.99/mo or €79.90/yr, Google/Email auth, Stripe payment               | Must have |
| **Account Dashboard**  | Email, next payment date, payment history, upgrade to yearly, redeem coupon, cancel | Must have |
| **Privacy Policy**     | Generated via legal template tool                                                   | Must have |
| **Terms of Service**   | Generated via legal template tool                                                   | Must have |

### Technical Stack (V1)

| Component     | Implementation                                        |
| ------------- | ----------------------------------------------------- |
| **Auth**      | Firebase: Google Sign-In + Email/Password             |
| **Payments**  | Stripe: Monthly €7.99, Yearly €79.90, promotion codes |
| **Webhooks**  | `invoice.paid`, `customer.subscription.deleted`       |
| **Database**  | Firestore: users/{uid}, coupon redemption tracking    |
| **Analytics** | Firebase Analytics (basic funnel tracking)            |

### Out of Scope for MVP

| Feature                    | Reason                                  | Deferred To |
| -------------------------- | --------------------------------------- | ----------- |
| Discord OAuth              | Extra dev work, Google/Email sufficient | V2          |
| Coupon Admin UI            | Stripe dashboard sufficient for beta    | V2          |
| Custom Analytics Dashboard | Firebase Analytics sufficient initially | V2          |
| Team/Group Billing         | Individual subscriptions only for V1    | V2+         |
| Localization               | French tagline only, English UI         | V2          |

### MVP Success Criteria

The MVP is successful when:

- First 20 coaches can subscribe and manage accounts without support intervention
- Coupon → Paid conversion validates the trial model
- Checkout abandonment rate identifies friction points
- No critical payment/auth failures in first 30 days

### Future Vision (V2+)

| Feature               | Value                                                      |
| --------------------- | ---------------------------------------------------------- |
| Discord OAuth         | Meet users where they are (EVA community lives on Discord) |
| Coupon Batch Admin UI | Self-service coupon generation for campaigns               |
| Advanced Analytics    | Custom dashboard for funnel optimization                   |
| Referral System       | Coaches invite coaches, earn free months                   |
| Team Subscriptions    | Coach pays for whole team at discount                      |
