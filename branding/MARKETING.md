# Resona — Marketing Plan

Living doc. Created 2026-05-09. Owner: Shobeir.

---

## TL;DR

Resona is the first **privacy-first brain-state interface for AI agents**: a Muse headband + a Mac app that lets your AI tools (Claude, Cursor, Notion AI, your own MCP agents) know when you're focused and adapt. Notifications hush. The Coach speaks slower. The Skeptic stops second-guessing your flow state.

**We sell:** a downloadable Mac app + an open MCP server. Hardware (Muse-14B3) is bring-your-own.

**The wedge:** macOS notification suppression that actually works because it knows your beta/alpha ratio, not your calendar.

---

## Positioning

> *Calm productivity tools have been guessing for 30 years. Resona stops guessing.*

| Axis | Position |
|---|---|
| Category | Brain-Computer Interface for AI agents (new category — we are defining it) |
| Adjacent to | Calm, Headspace (mindfulness); Focus@Will (audio); Brain.fm; Muse (hardware); Notion AI / Claude (LLM agents) |
| Crucial difference | We don't *coach* the user. We coach the user's **agents**. |
| Privacy stance | Local-only EEG processing. Raw µV never leaves the Mac. *This is the marketing.* |

**One-sentence pitch:** *Resona reads your focus state from a Muse headband, locally, and tells your AI agents when to back off.*

---

## Audience tiers

### Tier 1 — Indie hacker / power user (launch wedge)
- **Who:** Developers, writers, designers who already own a Muse-2 or Muse S, already pay for Cursor/Claude, already complain about notification noise.
- **Pain:** AI tools are too eager. Slack pings interrupt deep work. They've tried Focus modes; they're crude.
- **Hook:** "Your Mac already knows when you're typing. Now it knows when you're *thinking*."
- **Channels:** Hacker News (Show HN), Twitter/X (BCI + AI dev community), Lobste.rs, Reddit r/Mac r/biohacking r/LocalLLaMA, Cursor Discord.

### Tier 2 — Quantified self / biohacker
- **Who:** Owns Oura, Whoop, eight-sleep, Muse. Tracks HRV. Wants their stack to *do* something with the data.
- **Pain:** Data without action.
- **Hook:** "Other wearables tell you about your day. Resona changes it."
- **Channels:** r/QuantifiedSelf, Andrew Huberman-adjacent newsletters, biohacker podcasts.

### Tier 3 — Therapeutic / accessibility (slow burn, high impact)
- **Who:** ADHD adults, post-concussion recovery, knowledge workers with attention disorders, OTs and coaches who work with them.
- **Pain:** Generic productivity advice doesn't account for variable cognitive states.
- **Hook:** "Your tools, on your terms — even on bad-attention days."
- **Channels:** ADHD subreddits, ADDA newsletter, podcasts (How to ADHD), partner with one or two well-respected ADHD coaches who'll demo it.
- **Caveat:** **Not a medical device.** We never claim diagnosis or treatment. Copy reviewed for FDA/FTC compliance language before publishing to this audience.

### Tier 4 — Enterprise (later)
- Knowledge work teams, deep-work-as-a-service. Phase 3+. Don't lead with this.

---

## Messaging hierarchy

### Headline tier
- **Your mind, in tune.** *(brand)*
- **The agent that knows when not to interrupt.** *(feature)*
- **A brain-computer interface for the rest of your stack.** *(category)*

### Body claims (in order of credibility)
1. **Local-only.** Raw EEG never leaves your Mac. Only labels — `deeply_focused`, `engaged`, `neutral`, `resting`, `uncertain` — cross any boundary.
2. **Sub-500 ms** sensor-to-agent latency. Feels live, not laggy.
3. **MCP-native.** Any agent that speaks Model Context Protocol can read your state. Works with Claude Desktop today.
4. **Personal calibration.** Two-minute eyes-open / eyes-closed cycle teaches it *your* baseline — not a population average.
5. **Artifact-aware.** Blinks, jaw clenches, bad contact get flagged as `uncertain`. Agents are told: *don't act on noisy signal.*

### What we will not claim
- We will not claim it makes you smarter.
- We will not claim productivity gains in %. (We don't have the study.)
- We will not claim it's medical, therapeutic, or diagnostic.
- We will not claim it works without a Muse headband.

---

## Launch sequence

### Phase A — Soft launch (T-0 to T+30 days)
1. **Landing page** at `resona.app` (or `resona.brain` / `useresona.com`): mark + tagline + 60-sec loop video of the menu-bar indicator changing as the user reads / opens Slack. Email capture. No payment.
2. **Open-source the MCP server** on GitHub. README leads with the privacy invariant. Lots of GIFs of the dashboard.
3. **Show HN post.** Title: *"Show HN: Resona — local EEG → MCP server so your AI agents know when you're focused"*. Anchor in the dev community first.
4. **Twitter/X thread** with a 30-second screencap: notification arrives → Gatekeeper sees `deeply_focused` → silenced → user surfaces from focus → Gatekeeper releases queued notifications. The before/after is the demo.
5. **Direct DM 20 indie hackers** with a Muse who post about flow/focus.

### Phase B — First paid users (T+30 to T+90)
1. **Mac app v1.0** on the website (Sparkle auto-update, not Mac App Store yet — App Store rejects raw HRV/EEG access patterns; revisit).
2. **Pricing:** $7/mo or $60/yr. Free 14-day trial. Free forever for the open-source MCP server (sells the Mac app, not the protocol).
3. **First 100 users get lifetime $60.** Founder pricing — one-time, never reopened.
4. **Cursor / Raycast integration writeups.** Concrete: "Add Resona to Cursor in 3 minutes." Each integration is a separate post, separate audience.

### Phase C — Earned media (T+90 to T+180)
1. **Pitch list (in priority order):**
   - Stratechery — Ben Thompson covers ambient computing & agents.
   - Hacker News (front page — already from Phase A if it lands).
   - The Verge / 404 Media — privacy-first AI tool angle.
   - Andrew Huberman — long-shot, but the "your stack reads your state" framing fits.
   - Lex Fridman — BCI + AI agents intersection.
   - Latent Space podcast — AI dev tooling audience.
   - Kara Swisher — privacy/agent skeptic; useful counterweight.
2. **Two long-form posts on our blog**:
   - *"What I learned shipping a brain-computer interface from my apartment"* — narrative, vulnerable, technical-enough.
   - *"Why we don't process your EEG in the cloud"* — specifically rebuts the inevitable "but what if you just sent it to OpenAI" question.

### Phase D — Slow burn / community
1. **Discord** with channels for `#protocol` (MCP server hackers), `#hardware` (Muse pairing issues), `#use-cases` (people sharing custom agents).
2. **Monthly demo day** — users show off custom agents they've wired to Resona's MCP. (Skeptic agent, audio biofeedback, etc.) Promotes the platform aspect.
3. **"Resona Recipe" series** — short videos: "Make your Cursor agent stop suggesting refactors when you're in flow" / "Auto-DND your Slack on focus" / "Pause Spotify ads at the focus inflection."

---

## Channels and budget (first 6 months)

| Channel | Spend | Goal | Measure |
|---|---|---|---|
| Landing page (Vercel) | $0 + domain | Email list 1k | Signups |
| Open-source GH | $0 | 500 stars | Stars + forks |
| Show HN | $0 | Front page | Comments + signups |
| Twitter/X | $0 (organic) | 5 viral threads | Impressions + replies |
| Sponsored newsletters | $1500 (Latent Space, Why Try AI, ADDitude tier-3) | 3 placements | Click-through to landing |
| Podcast pitching | $0 (founder-led) | 3 appearances | Mentions + signups |
| Discord | $0 | 200 members | DAU, agent recipes shared |
| YouTube demo channel | $200 (mic + lights, founder-recorded) | 6 videos at 5k+ views each | Subs + tutorial completion |
| **Total cash** | **~$1700** | — | — |

We are deliberately not running paid ads in Phase A/B. The product is too novel; a $5 CAC ad won't beat a Show HN that explains it correctly.

---

## Metrics that matter

### Leading indicators (week 1–4)
- Email signups on landing page
- GH stars on the MCP repo
- HN comment depth (engagement, not just upvotes)

### Activation (when a user installs)
- **% who pair a Muse within 24 hours of install** — biggest funnel cliff. If <40%, the pairing UX is broken.
- **% who complete calibration** — without it, labels are noise. Must be >80% of paired users.
- **% who connect at least one MCP client (Claude Desktop, custom)** — the moment of value.

### Retention
- **D7 retention** of users who completed calibration.
- **Sessions per week with `engaged` or `deeply_focused` time > 5 min** — proxy for "the device is part of their workday."

### Revenue (Phase B+)
- Trial → paid conversion. Target: 8% (high for productivity SaaS but realistic given the hardware investment they've already made).
- Annual vs monthly mix. Annual is healthier given the deep-work positioning — these are not impulsive buyers.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Muse-14B3 supply / Muse company drama | Multi-source: build for Muse 2 / Muse S as well. Stream protocol abstracts the device. |
| "BCI" sounds spooky → trust ceiling | Privacy refrain everywhere. Open-source the MCP server. Publish a security writeup. |
| App Store rejects EEG-derived APIs | Stay direct-distribution + Sparkle auto-update for v1. Reapply once we have a usage track record. |
| FDA / FTC creep if therapeutic users adopt it | Hard line: never claim treatment. Disclaimer in app + on landing. Lawyer-review tier-3 copy. |
| Apple ships their own focus-detection (Watch HRV → Focus modes) | Our moat: we're MCP-native and we expose state to *any* agent, not just Apple's. Lean harder into agent integration. |
| Users without Muse churn | The free MCP server + a "synthetic mode" demo lets non-owners try the integration shape before buying hardware. |

---

## 30/60/90

**30 days:** landing page live, MCP server public on GitHub, Show HN posted, 1k email signups, 500 stars.
**60 days:** Mac app v1.0 in beta, 100 paid lifetime founders, first podcast appearance recorded.
**90 days:** v1.0 public, 500 paying users, Discord at 200 members, two integration writeups (Cursor, Raycast), one piece of earned media.

---

## Open marketing decisions

- [ ] Domain: `resona.app` vs `useresona.com` vs `resona.brain` (.brain TLD is interesting but discoverability cost)
- [ ] Logo lockup on dark vs light primary — currently mark assumes light bg. Need both.
- [ ] Whether to make a 60-sec hero video before launch, or ship the landing page minimal and add the video after first signups.
- [ ] Affiliate / referral program — likely yes for the calm-productivity creator economy, but not in Phase A.
