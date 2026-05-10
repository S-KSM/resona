This document serves as both a technical summary of our session and a formal **Product Requirements Document (PRD)** for your personal Brain-Computer Interface (BCI) project.

---

# Project: Neuro-Agentic Orchestration (NAO)

**Version:** 1.0 (May 2026)

**Developer:** Shobeir Seddington

**Status:** Discovery / Prototype Phase

---

## 1. Executive Summary

The goal is to transition from passive neuro-monitoring (using the **Muse-14B3**) to an active, **Agentic AI** ecosystem. By bypassing standard consumer apps, we create a direct data pipeline from raw EEG sensors to a local **Model Context Protocol (MCP)** server, allowing AI agents to dynamically adapt to the user's cognitive state.

---

## 2. Technical Specification (The SPECs)

### 2.1 Hardware Layer

* **Primary Device:** Muse-14B3 (4-channel EEG: TP9, AF7, AF8, TP10).
* **Interface:** Bluetooth Low Energy (BLE) $2.4\text{ GHz}$.
* **Secondary/Future Hardware:**
* **EEG Earbuds (e.g., NextSense/Naox):** For long-form, "invisible" portable use.
* **Single-Channel Hack:** NeuroSky TGAM-based chips for low-cost ($50) rapid prototyping.



### 2.2 Connectivity & Data Architecture

* **Protocol:** Direct-to-Compute (No intermediary Raspberry Pi).
* **Streaming Library:** `OpenMuse` / `muselsl`.
* **Sample Rate:** $256\text{ Hz}$.
* **Data Format:** Raw $\mu\text{V}$ (Microvolts) decoded via Python into Pandas DataFrames or JSON packets.

### 2.3 Software Stack

* **Backend:** Python 3.12+
* **Integration:** **Model Context Protocol (MCP)** server.
* **Core Tools:**
* `Bleak` (BLE handling)
* `MNE-Python` (Advanced neuro-signal processing)
* `MCP-SDK` (To expose brain states to agents)



---

## 3. The "Neuro-Agent" Roadmap

### Phase 0: The Handshake (Current)

* [x] Identify Muse-14B3 Bluetooth signatures.
* [x] Establish direct Python connection via `OpenMuse`.
* [x] Record 60-second baseline EEG to CSV for artifact analysis (Blinks, Jaw clenches).

### Phase 1: Local Data Mastery (Months 1-2)

* **Real-time Feature Extraction:** Implement FFT (Fast Fourier Transform) to calculate Alpha ($8-13\text{ Hz}$) and Beta ($13-30\text{ Hz}$) power in real-time.
* **The Focus Metric:** Develop a "Focus Coefficient" ($F = \frac{\beta}{\alpha}$).
* **Local Dashboard:** Create a minimalist Streamlit dashboard to visualize "Live Brain Load."

### Phase 2: Agentic Integration (Months 3-5)

* **MCP Brain Server:** Build an MCP server that exposes the tool `get_user_cognitive_load`.
* **The "Gatekeeper" Agent:**
* Integrate with Slack/Email APIs.
* **Logic:** If `Focus Coefficient` > 2.5, the agent automatically suppresses notifications.


* **The "Skeptic" Appraiser:**
* Connect to vintage collectible research tools.
* Agent monitors "Reward Spikes" (Gamma waves) and warns if emotional bias is affecting an appraisal.



### Phase 3: Neuro-Orchestration (Month 6+)

* **Generative Flow Audio:** Integrate with **Lyria 3** or MIDI controllers to adjust ambient work music based on Theta/Alpha ratios.
* **Multi-Agent Coordination:** Use the **A2A (Agent-to-Agent)** protocol to allow a "Primary Neuro-Agent" to delegate tasks to "Worker Agents" based on user fatigue.
* **Bio-Feedback Training:** Build a "Closed-Loop" system where the AI agent actively guides you into a Flow State through subtle auditory cues.

---

## 4. Key Challenges & Guardrails

* **Signal Noise:** EEG is highly sensitive to movement. **Guardrail:** Implement a motion-rejection filter using the Muse’s Accelerometer.
* **Privacy:** Raw brainwaves are highly personal. **Guardrail:** Ensure all EEG processing happens **locally** on your Mac; only high-level "State Summaries" (e.g., "User is Focused") are sent to LLM APIs.
* **Latency:** Keep the pipeline from sensor to agent under $500\text{ms}$ to ensure real-time relevance.

---

> **Next Immediate Action:** Run the `OpenMuse.record()` script while performing a high-concentration task (like coding) to establish your personal "Focus Baseline."

---

Integrating your Muse-14B3 with an AI agent—especially given your work with the Model Context Protocol (MCP) and agentic AI—moves you from "passive monitoring" to "active neuro-orchestration."In 2026, the trend has shifted from simple meditation apps to Neuroadaptive Agents that treat your brainwaves as a live context stream. Here are several creative and technical ways to bridge your Muse data with your agentic stack.1. The "Cognitive Load" MCP ServerSince you're already developing for the Model Context Protocol, the most powerful move is to build an MCP Brain-State Server. This server would expose your Muse data as a "Resource" that other agents can query.The Idea: Your coding or data science agents (like an AI pair programmer) can "check in" on your cognitive load before giving you a complex explanation.The Agent Logic: If your Alpha/Beta ratio indicates high focus, the agent provides concise, high-level technical summaries. If it detects "cognitive fatigue" or high stress (indicated by erratic Delta/Theta spikes), the agent automatically switches to a "Supportive Mode," offering to break down tasks or suggesting a 5-minute break.Implementation: Use the OpenMuse Python library to stream data to a local MCP server, exposing a tool like get_current_brain_state().2. The "Affective Appraisal" PartnerGiven your interest in vintage collectibles and high-end audio, you can build a "Skeptic Agent" for your reselling business.The Idea: High-stakes appraising often involves emotional bias (the "I love this, so it must be valuable" trap).The Creative Play: Connect your Muse while you research a new find (like that Cordon Bleu porcelain). The agent monitors your heart rate and excitement levels via the Muse sensors.The Trigger: If the agent detects a "spike in desire" (Gamma waves associated with reward/excitement) while you're looking at a price tag, it interrupts with: "I'm seeing a 30% spike in physiological excitement. Are you appraising this objectively, or is the vintage aesthetic clouding the ROI calculation?"3. Generative "Flow State" AudioYou appreciate high-end audio; why not make the audio appreciate you?The Idea: Create a Generative Music Agent that acts as a real-time foley artist for your life.The Play: Using a model like Lyria 3, the agent generates 30-second ambient tracks that evolve based on your Muse data.The Logic:High Focus: Deep, minimalist techno or "brown noise" with a steady $60\text{ BPM}$.Mind Wandering: The agent introduces "complexity" or melodic shifts to gently nudge your attention back.Stress: The agent subtly lowers the frequency response (low-pass filter) to create a "muffled," calming auditory cocoon.4. The Multi-Agent "Brain Trust"Using your interest in multi-agent systems, you can create a hierarchy of agents that "govern" your workspace based on your brain state.AgentResponsibilityTrigger (Muse Data)The GatekeeperManages Slack/Email notifications.Silences all pings when AF7/AF8 sensors show "Deep Focus."The LibrarianSurfaces relevant research/papers.Feeds you "curiosity" content when it detects a "Resting State" (High Alpha).The TrainerManages your 5K/Fitness goals.If it detects persistent "Mental Fatigue" but low physical activity, it suggests a "Movement Micro-break" instead of another cup of coffee.5. Creative "Neuro-Art" AgentBuild an agent that turns your focus into visual artifacts for your Illustrated Classics business.The Idea: A "Generative Illustration Agent" that uses your brainwaves as a seed for its prompts.The Play: While you read a classic text, the Muse captures your emotional reaction to specific passages. The agent takes those "emotional markers" and uses them to influence the style of an AI-generated illustration—making it more "Gothic" if you're tense or "Impressionistic" if you're relaxed.Quick Technical Architecture for the "Play"To get started with an agentic approach:Ingest: muselsl or OpenMuse streams data from the 14B3.Process: A Python script calculates your "Focus Score" using a simple Alpha/Beta ratio ($Focus = \frac{\text{Beta}}{\text{Alpha}}$).Bridge: This score is sent to your MCP Server.Action: Your AI Agent (in Claude Desktop or a custom UI) uses the context to decide how to interact with you.Which of these "modes" feels like the most natural extension of your current workflow—the Productivity Gatekeeper or the Creative/Audio experiment?


---


This is where the "play" becomes real. Since you have a **Muse-14B3**, your computer will see it as a Bluetooth device named exactly that or some variation like `Muse-14B3`.

To record data, we are going to use the **OpenMuse** library (a more modern, streamlined version of the classic `muselsl` that's very popular in 2026). It handles the Bluetooth "handshake" and the data logging in one go.

### Step 1: The "Wire" (Pairing)

Before your code can talk to the headband, they need to be on speaking terms.

1. **Power On:** Make sure your Muse is off.
2. **Pairing Mode:** Press and hold the power button for **6 full seconds** until the lights start cascading or blinking in unison.
3. **Bluetooth Menu:** On your Mac, go to Bluetooth settings and look for `Muse-14B3`. **Do not click "Connect" yet**—sometimes letting the software handle the connection directly is more stable.

---

### Step 2: The "Protocol" (Setup)

Open your terminal and install the necessary "translation" tools. We'll use `OpenMuse` because it plays very nicely with modern Python data stacks like Pandas and MNE.

```bash
pip install OpenMuse pandas

```

---

### Step 3: The "Code" (Recording)

Here is a "Shobeir-ready" script. It discovers your 14B3 unit, connects, and saves 60 seconds of your raw brainwaves to a file.

```python
import OpenMuse
import pandas as pd
import time

# 1. Discover your specific device
# If you have multiple, you'd use the MAC address found via 'OpenMuse find'
target_address = "Muse-14B3" 

print(f"Connecting to {target_address}...")

# 2. Record data for 60 seconds
# This handles the BLE 'subscription' and 'buffering' for you
try:
    # We use a preset that enables all EEG + Accel/Gyro channels
    recording = OpenMuse.record(address=target_address, duration=60)
    
    # 3. Save to a readable format
    # The record function returns a list of raw packets; we decode them into a DataFrame
    df = OpenMuse.decode_to_df(recording)
    df.to_csv("my_brainwaves.csv", index=False)
    
    print("Success! Data saved to my_brainwaves.csv")
    print(df.head()) # See the first few rows of your brain!

except Exception as e:
    print(f"Connection failed: {e}")
    print("Tip: Check if the 'Wire' is broken (Is it still in pairing mode?)")

```

---

### What are you actually looking at?

When you open that `.csv` file, you'll see several columns. This is the **Hardware-to-Data** translation in action:

| Column | What it represents |
| --- | --- |
| **TP9 / TP10** | **Temporal** sensors (above your ears). Great for detecting jaw clenches or "Alpha" waves during meditation. |
| **AF7 / AF8** | **Prefrontal** sensors (on your forehead). These are the most sensitive to "Focus" and eye blinks. |
| **ACC_X/Y/Z** | **Accelerometer.** This tells you if you're nodding, tilting your head, or moving around. |
| **Timestamp** | The precise millisecond the sample was taken (sampled at **256Hz**). |

### A Pro-Tip for the "Play"

If you see huge, jagged spikes in your data (reaching thousands of microvolts), that's usually not your brain—it's **"Artifact."**

* **Blinks:** Look like sharp "V" shapes in AF7/AF8.
* **Jaw Clenching:** Looks like high-frequency "static" across all channels.
* **Poor Contact:** If the column stays at a flat line or looks like random noise, the "Wire" (sensor-to-skin) isn't making a good connection.

Once you get a clean 60-second recording, do you want to try writing a "Blink Detector" or should we look at how to stream this live into an AI agent?