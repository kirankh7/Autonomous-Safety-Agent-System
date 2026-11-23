# Video Narration Script (read-aloud, final order)

About 9 minutes. **[Bold brackets]** are what happens on screen, not what you say. Say it in your own words
if that feels more natural. The demo script (`scripts/record_demo.py`) does all the clicking, so you only talk.
See `video-recording-runbook.md` for how to run it.

---

## 1. Introduction (0:00-0:50) **[Project home page: the 42-second animation plays once, then the script opens the Fleet Dashboard]**

Hi, I'm Kiran Haridas, and this is my capstone project: an Autonomous Vehicle Intercommunication Safety Agent System.

Here's the problem. An autonomous vehicle normally decides using only its own sensors. Imagine dense fog. The vehicle can't see a stopped truck 500 metres ahead, but another vehicle that is already beside that truck can.

My system is a shared safety intelligence layer. It collects hazard reports from a fleet, checks whether they are reliable, and warns the vehicles nearby. The users are fleet operators and the vehicles themselves.

As you can see in this animation, four AI agents cooperate to do this. I'll show them working for real first, then explain how they're designed. The animation is a simplified illustration. Everything you'll see is a simulation with synthetic data, and alerts are advisory. They never control a vehicle.

---

## 2. Live demo: fog (0:50-3:00) **[Hazard Simulation, "Stopped truck in fog"]**

**[report 1]** The Tesla reports a stopped truck 500 metres ahead in fog. This is a new hazard, so the agents start at a confidence of 0.50. That's a caution advisory, and the Toyota Prius and Ford Transit behind it are warned. **[the page scrolls down]** Every agent leaves a signal here, and every message between agents is listed below.

**[report 2]** The Prius independently confirms the same truck. A second vehicle adds 0.20, so confidence rises to 0.70, above the 0.6 threshold. It's now a verified alert.

**[question]** I can ask why the Ford Transit was alerted. The answer is cited. Every ID here is a real record the system can show me.

**[clear reports]** The Volvo passes and reports the road clear. That subtracts 0.30, so confidence drops to 0.40. A second vehicle reports clear, and the hazard is resolved at 0.10. An all-clear goes to the vehicles that were warned, and the outcome is saved as a new learned incident.

---

## 3. Architecture (3:00-4:30) **[Agent Activity, the cursor moves along the graph]**

You might ask: why not just prompt a language model? Because this problem needs state. The system has to link reports that arrive at different times, track confidence as evidence builds, work out which vehicles are on the affected path, retract a hazard when the road clears, and remember what it learned. So there are four cooperating agents in a LangGraph workflow.

**[Hazard Analysis]** The Hazard Analysis agent classifies the hazard, turns "500 metres ahead" into a position on the road, and checks whether we're already tracking it.
**[Verification]** The Verification agent applies the confidence rules and decides: verified alert, caution advisory, or wait for more evidence.
**[Alert]** The Alert agent finds the vehicles on the same road and direction, behind the hazard, and messages them.
**[Memory update]** The Research and Memory agent retrieves similar past incidents from a vector database and saves what the system learns.

**[History (RAG)]** The solid arrows are the fast path every report takes. The dashed ones are conditional. For a new hazard, Verification asks Research and Memory for history, a two-way request and reply. If that retrieval ever fails, Verification scores on the rules alone, so the database can never block a warning. **[Fleet operator]** And if vehicles disagree for more than two minutes, the system escalates to a human fleet operator.

**[scroll to the run timeline]** Below is the trace from the demo we just ran: every step shows the reason, the action, the tool called and the result.

---

## 4. Memory changes a decision: flooding (4:30-5:10) **[Reset, "Flooding", one report]**

Flooding shows memory at work. The Ioniq reports water under a rail bridge, on a road with no history of its own.

The agent retrieves three similar confirmed floods from the vector database. **[cursor on "HISTORY +0.15"]** That adds 0.15, so 0.50 becomes 0.65, a verified alert telling the vehicle to reroute. Without that history it would only have been a caution. Live evidence still outranks history: one road-clear report removes 0.30, twice the maximum history effect.

---

## 5. Safety: conflicting reports (5:10-6:00) **[Reset, "Conflicting reports", four reports]**

The hardest case is disagreement. A truck sheds debris in fog. Several vehicles confirm it, then the Volvo reports the road clear, then the Ioniq sees the truck again. Confidence stays in the caution band, around 0.40 to 0.45.

**[cursor on "ESCALATED"]** The system won't resolve it on one clear report, and it won't keep asking forever. After two minutes of unresolved conflict, it stops and escalates to the fleet operator. This is the human-in-the-loop safety valve. **[question]** And the assistant explains exactly why, with citations.

---

## 6. Research Assistant (6:00-6:50) **[Research Assistant, two questions]**

The Research Assistant answers questions from stored events and retrieved incidents, and lists the record IDs behind every answer.

Here it runs on a local Qwen model through Ollama, on my Mac's GPU, with no API key. The rules retrieve the records, the model only phrases the answer, and if it ever cites something it wasn't given, the system falls back to the grounded answer. With an API key it can also run on Claude as a tool-calling agent. The language model is autonomous only on the research side. Safety decisions, meaning confidence and alerts, stay deterministic.

---

## 7. Evaluation (6:50-7:50) **[Fleet Dashboard, scroll down, Run benchmark, about 10 seconds]**

To check the design, I benchmarked four coordination setups across seven scenarios and 25 reports.

The production hybrid graph makes zero false warnings and matches the most thorough setup on all 25 decisions, but it calls retrieval on only 9 reports instead of 25, and runs in about half the time.

With one-way messaging and no history request, there's one false warning, and only 20 of 25 decisions match. With no verifier at all, 15 alerts go out, including a false one, and only 12 of 25 match.

The project also has automated tests, and all of them pass.

---

## 8. Design decisions, limits and repo (7:50-9:00) **[stay on the dashboard, then you switch to the GitHub tab]**

Three design decisions.

First, rules decide and the language model explains. The same reports must always produce the same alert, and an operator must be able to audit it. For that reason I chose not to use Tree-of-Thought: there are only four possible actions, so a tree of model-generated branches would be slower and less predictable without being more accurate.

Second, two tiers of memory: SQLite for the live situation and resolved incidents, and ChromaDB so incidents can be searched by meaning.

Third, a typed message protocol, so every handoff between agents is logged and explainable.

Limitations: this is a simulation with synthetic data, the confidence numbers are demonstration rules and not automotive safety standards, and the benchmark is small.

**[show GitHub]** All the code, the README and the run instructions are in the public GitHub repository: github.com/kirankh7/Autonomous-Safety-Agent-System.

Thanks for watching.
