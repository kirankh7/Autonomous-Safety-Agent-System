# Capstone Checkpoint 2.1: Agent Design Refinement

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas

In Checkpoint 1.1, I proposed an agent that acts as a shared safety intelligence layer for a fleet of autonomous vehicles. This refinement makes its reasoning, memory, and tool use explicit, justifying each choice by a limitation identified in this module's readings.

## 1. Reasoning Loop

The agent uses a **ReAct-style loop (Thought → Action → Observation)**. Two additions draw on the readings: a **verification step** (Cobbe et al., 2021) and a **Reflexion-style feedback loop** (Shinn et al., 2023).

**Inner loop (per incoming report).** Consider the fog scenario:

- **Thought:** "Vehicle A reports a stopped vehicle in low visibility. Does this match an existing event?"
- **Action:** Query the active-event store for hazards on the same road segment and direction of travel.
- **Observation:** Vehicle B reported a stopped vehicle 30 m away, 60 seconds ago.
- **Thought:** "Two independent, consistent reports. Verify before alerting."
- **Action:** Run the verifier, then query vehicles approaching the segment.
- **Observation:** Verifier confidence is 0.86. Vehicle C is 550 m upstream at 90 km/h, roughly 22 seconds away.
- **Action:** Send a structured alert to Vehicle C.

Each Thought uses step-by-step reasoning, which Kojima et al. (2022) show substantially improves multi-step reasoning (GSM8K accuracy from 10.4% to 40.7%). However, a single chain cannot correct itself: solutions that "veer off-course quickly become unrecoverable" (Cobbe et al.). Observations ground each step. An empty lookup creates a new *unverified* event instead of an alert. A "road clear" report lowers confidence instead of raising it.

**Verification step.** Cobbe et al. show that *judging* a candidate is easier than *generating* a correct one, and that ranking many candidates with a verifier works better than trusting one output. Here, each vehicle report is a candidate hypothesis, scored on agreement across independent vehicles, plausibility of location and timing, and weather context. Only verified events trigger alerts. One exception follows the cost asymmetry: in low visibility, a high-severity hazard triggers a low-confidence advisory, because a missed hazard costs more than a false alarm.

**Outer loop (feedback).** Following Reflexion's Actor–Evaluator–Self-Reflection structure, vehicles that receive an alert later act as the **Evaluator**. They report whether the hazard was present and whether the location was accurate. A self-reflection step turns each outcome into a stored lesson. For example: "single-sensor debris reports on Segment 14 in heavy rain were false 3 of 4 times." Future cycles use these lessons. The agent remains **advisory**; each vehicle's driving system makes its own control decisions.

## 2. Memory Requirements

The agent needs **both** types of memory, mirroring Reflexion's design.

**Short-term memory** is the current trajectory: the triggering report, retrieved events, tool outputs, and intermediate thoughts. It also holds the **active hazard registry**, meaning each open event's location, type, confidence, contributing reports, and alerts sent. This memory lets the agent link a report at time *t* to a report 60 seconds later, and prevents duplicate alerts.

**Long-term memory** stores **source reliability scores** (how often each vehicle or sensor type was later confirmed), **hazard history by road segment**, and **reflective lessons** from alert outcomes. Reflexion caps long-term memory at 1–3 entries and recommends databases as future work. A fleet produces far more experience, so this design uses a database and retrieves only entries relevant to the current location.

## 3. Tool Usage

| Tool | Limitation Addressed |
|---|---|
| Geospatial engine (map-matching, along-road distance, bearing) | Computation and grounding |
| Event store / memory query | Retrieval |
| Vision model for camera frames | Perception |
| Weather / visibility API | Grounding in current conditions |
| Verifier / confidence scorer | Reliable evaluation |
| Alert dispatch service | Acting on the environment |

**Key example: geospatial computation.** Cobbe et al. found that models "frequently fail to accurately perform calculations," even when fine-tuned. They fixed this with a calculator tool. Hazard relevance is similar. "500 m ahead" only matters if the hazard is on the same road and direction of travel. A vehicle 500 m away in a straight line may be on an overpass or the opposite carriageway. The geospatial tool map-matches GPS points and computes along-road distance, so the model never estimates geometry itself.

## 4. Improvement Over a Prompt-Only Approach

Reflexion reports a specific failure mode: a ReAct-only agent "thinks that it has possession of an item but does not actually have the item." Without memory, it settles at a 22% hallucination rate with no recovery. A prompt-only safety agent has the same failure, but with hazards:

> Vehicle A reports a stopped truck in fog. A prompt-only model, even with "Let's think step by step," produces a plausible chain of reasoning and issues an alert. Forty seconds later, Vehicle B's report arrives as a new prompt. The model has no record of the first, so it issues a duplicate alert. It also estimates distances from raw coordinates and alerts a vehicle on the opposite carriageway. After the truck is towed, the model still believes the hazard exists and has no basis to retract the alert.

The refined design resolves each part of this failure:
- The **active hazard registry** merges the reports into one event.
- The **verifier** requires corroboration before alerting.
- **Geospatial tools** target only vehicles on the affected path.
- The **feedback loop** treats "road clear" reports as observations, lowering confidence until the event is resolved.
- **Reflective long-term memory** avoids repeating past false alerts.

One caution shapes the design: Reflexion depends on evaluator quality, and Cobbe et al. found heavy search can surface "adversarial solutions that fool the verifier." The evaluator is therefore grounded in **real vehicle observations**, not the model's self-assessment.

## References

- Cobbe, K., et al. (2021). *Training Verifiers to Solve Math Word Problems.* arXiv:2110.14168.
- Kojima, T., et al. (2022). *Large Language Models are Zero-Shot Reasoners.* NeurIPS 2022. arXiv:2205.11916.
- Shinn, N., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366.
