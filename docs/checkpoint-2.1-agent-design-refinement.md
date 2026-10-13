# Capstone Checkpoint 2.1: Agent Design Refinement

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas

## Refined Agent Concept

The agent is a shared safety intelligence layer for a fleet of autonomous vehicles. **Its task is to turn individual vehicle hazard reports into verified, location-specific alerts for vehicles that cannot yet see the hazard.** For example, a car in dense fog needs to know about a stopped truck 500 m ahead.

- **Inputs:** vehicle reports (hazard type, GPS, heading, speed, camera frames), weather and visibility data, and road map data.
- **Output:** a structured alert (hazard type, location, distance along the road, severity, confidence) sent only to vehicles on an affected path, plus updates when the hazard is confirmed or cleared.

The agent is **advisory**; each vehicle's driving system makes its own control decisions. Below, each capability is justified by a limitation from this module's readings.

## 1. Reasoning Loop

The agent uses a **ReAct loop (Thought → Action → Observation)**, extended with a **verifier** (Cobbe et al., 2021) and a **Reflexion feedback loop** (Shinn et al., 2023).

**Inner loop (per incoming report).** Consider the fog scenario:

- **Thought:** "Vehicle A reports a stopped vehicle in fog. Does this match an existing event?"
- **Action:** Query active events on the same road segment and direction.
- **Observation:** Vehicle B reported a stopped vehicle 30 m away, 60 seconds ago.
- **Thought:** "Two independent, consistent reports. Verify before alerting."
- **Action:** Run the verifier, then query vehicles approaching the segment.
- **Observation:** Confidence 0.86. Vehicle C is 550 m upstream at 90 km/h (~22 seconds away).
- **Action:** Send a structured alert to Vehicle C.

Each Thought uses step-by-step reasoning, which Kojima et al. (2022) show improves multi-step reasoning (GSM8K: 10.4% to 40.7%). But a single chain cannot correct itself; it can "veer off-course" unrecoverably (Cobbe et al.). Observations change the next step: an empty lookup creates an *unverified* event instead of an alert, and a "road clear" report lowers confidence.

**Verification step.** Cobbe et al. show that *judging* a candidate is easier than *generating* a correct one. Here, each vehicle report is a candidate, scored on agreement across independent vehicles, location and timing plausibility, and weather. Only verified events trigger alerts. The exception: in low visibility, a high-severity hazard triggers a low-confidence advisory, because a missed hazard costs more than a false alarm.

**Outer loop (feedback).** Following Reflexion's Actor–Evaluator–Self-Reflection structure, alerted vehicles act as the **Evaluator**, reporting whether the hazard was present and correctly located. Self-reflection turns each outcome into a stored lesson, such as "single-sensor debris reports on Segment 14 in heavy rain were false 3 of 4 times."

**Stopping conditions.** An event's loop ends when "road clear" reports resolve it, it expires without new reports, or it is escalated to a human fleet operator.

## 2. Memory Requirements

The agent needs **both** types of memory, mirroring Reflexion's design.

**Short-term memory** is the current trajectory (report, retrieved events, tool outputs, thoughts) plus the **active hazard registry**: each open event's location, type, confidence, reports, and alerts sent. This memory lets the agent link a report at time *t* to a report 60 seconds later, and prevents duplicate alerts.
*When it applies:* it is read and written on every loop step. Each event's entry lasts only while the event is active (minutes to hours).

**Long-term memory** stores **source reliability scores** (how often each vehicle or sensor type was later confirmed), **hazard history by road segment**, and **reflective lessons** from alert outcomes. Reflexion caps this at 1–3 entries; a fleet needs more, so this design uses a database queried by location.
*When it applies:* it is **read** during verification, to weigh a report by its source and location history. It is **written** in the outer loop, after feedback shows whether an alert was correct. It persists across events and days.

## 3. Tool Usage

| Tool | When Used | Limitation Addressed |
|---|---|---|
| Vision model | A report includes camera frames | Perception |
| Event store / memory query | Every new report, to find matching events | Retrieval |
| Geospatial engine (map-matching, along-road distance) | Matching reports and choosing which vehicles to alert | Computation and grounding |
| Weather / visibility API | During verification and severity assessment | Grounding in current conditions |
| Verifier / confidence scorer | Before any alert is issued | Reliable evaluation |
| Alert dispatch service | Once an event passes verification | Acting on the environment |

**Key example: geospatial computation.** Cobbe et al. found models "frequently fail to accurately perform calculations" and fixed this with a calculator tool. Hazard relevance is similar: a vehicle 500 m away in a straight line may be on an overpass or the opposite carriageway. The geospatial tool computes along-road distance and direction, so the model never estimates geometry itself.

## 4. Improvement Over a Prompt-Only Approach

Reflexion reports a specific failure mode: a ReAct-only agent "thinks that it has possession of an item but does not actually have the item," plateauing at 22% hallucination. A prompt-only safety agent fails the same way:

> Vehicle A reports a stopped truck in fog. A prompt-only model, even with "Let's think step by step," reasons plausibly and alerts. Forty seconds later, Vehicle B's report arrives as a new prompt with no record of the first, producing a duplicate alert. Guessing distance from raw coordinates, it alerts a vehicle on the opposite carriageway. After the truck is towed, it has no basis to retract the alert.

Each added capability resolves part of this failure:

| Capability | Prompt-Only Failure | How It Improves Reliability |
|---|---|---|
| ReAct loop | One-shot answer, never grounded | Each decision follows a real observation; "road clear" reports lower confidence |
| Verifier | Acts on any plausible report | Requires corroboration before alerting, reducing false alarms |
| Short-term memory | Duplicate alerts; reports never linked | Merges reports into one tracked event |
| Long-term memory | Repeats past mistakes | Weighs sources by track record; applies stored lessons |
| Geospatial tool | Guesses distance; wrong vehicles alerted | Exact along-road distance; only at-risk vehicles alerted |
| Feedback loop | Stale alerts never retracted | Hazards are confirmed or resolved as new reports arrive |

One caution: Reflexion depends on evaluator quality, and Cobbe et al. found verifiers can be fooled. The evaluator is therefore grounded in **real vehicle observations**, not the model's self-assessment.

## References

- Cobbe, K., et al. (2021). *Training Verifiers to Solve Math Word Problems.* arXiv:2110.14168.
- Kojima, T., et al. (2022). *Large Language Models are Zero-Shot Reasoners.* NeurIPS 2022. arXiv:2205.11916.
- Shinn, N., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366.
