# Capstone Checkpoint 4.1: Tree-of-Thought Integration Plan

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas

## 1. Is ToT Appropriate?

**Decision: no. Tree-of-Thought (ToT) would make this agent slower and less predictable without making it more accurate.**

ToT helps when a problem has many possible paths and the model must explore and compare them before answering, as in puzzles, planning, or creative writing. I looked at whether my agent has a problem like that. It does not, for four reasons.

1. **The hard part is missing evidence, not missing reasoning.** The agent decides whether a hazard report is real and which vehicles to warn. When it is unsure, more thinking does not help. What helps is a new observation. The agent already handles this by asking approaching vehicles to report what they see. One new report settles the question more reliably than any number of reasoning branches.
2. **There are only a few possible decisions.** Every report leads to one of four actions: verified alert, caution advisory, wait and request observations, or resolve. The confidence score and thresholds from Checkpoint 3.1 choose among them. With only four outcomes and a clear rule, there is no tree worth exploring.
3. **Speed matters.** In the fog example, Vehicle C is 550 m away at 90 km/h, about 22 seconds from the hazard. A ToT search with 3 branches and 3 levels needs many LLM calls and can take several seconds. The current rule-based path decides in milliseconds.
4. **Safety decisions must be repeatable and explainable.** The same reports should always produce the same alert. ToT relies on an LLM to generate and score branches, and those scores can vary from run to run. The current design records a simple score trace (for example, "0.50 + 0.20 confirmation = 0.70, verified alert"), so an operator can audit any decision.

## 2. Where I Considered Using ToT

The one place ToT looked useful is **conflicting reports**. For example, in fog, Vehicle A reports a stopped truck at 3,500 m, Vehicle B reports debris at 3,580 m, and Vehicle C reports "road clear." Several explanations fit: the truck shed its load, there are two hazards, A misclassified debris, or the road has been cleared.

ToT would explore these explanations internally. My design handles the conflict without it:

- Each report adjusts confidence by a fixed rule: +0.20 for a confirmation, −0.30 for "road clear."
- Mixed evidence lands in the **caution band (0.40–0.60)**, so approaching vehicles still get a caution advisory and an observation request.
- The **safety exception** means a high-severity hazard in visibility under 200 m always gets at least a caution advisory.
- A hazard is resolved only after **two independent "clear" reports**, so one conflicting report cannot cancel a warning.
- The next vehicle to pass the spot provides real evidence, and confidence moves up or down accordingly.

I did find one weakness: reports are matched to an event only within 50 m, so the debris report 80 m away opens a separate event. The fix is a simple rule, not ToT: related hazard types, such as a stopped truck and debris, can be matched within 150 m.

## 3. The Reasoning Approach That Fits Best

**ReAct with a verifier and a feedback loop**, the design from Checkpoint 2.1, already built in the prototype with LangGraph.

- **ReAct (Reason → Act → Observe):** each agent reasons about the report, calls a tool (event lookup, along-road distance, past-incident retrieval), and uses the result to decide the next step.
- **Verifier:** confidence rules check every hazard before an alert is sent.
- **Feedback loop (Reflexion style):** vehicles that receive alerts report whether the hazard was really there. Those outcomes are saved to long-term memory and used for future reports.

**Workflow:**

1. Vehicle report arrives.
2. **Hazard Analysis Agent** classifies the hazard, places it on the road, and matches it to existing events.
3. **Research & Memory Agent** retrieves similar past incidents for new hazards.
4. **Verification Agent** applies the confidence rules and picks one of the four actions.
5. **Alert Agent** warns only the vehicles approaching the hazard, or requests observations when unsure.
6. **Research & Memory Agent** saves the outcome to memory.

There is no ToT step in this workflow. Uncertainty is handled at steps 4 and 5 by asking for more evidence.

## 4. Why This Works Better Than ToT

| | ToT | ReAct + verifier + feedback |
|---|---|---|
| How uncertainty is handled | Explores more reasoning branches | Collects a new observation from a vehicle |
| Time per decision | Seconds (many LLM calls) | Milliseconds (rules and tools) |
| Cost | Many LLM calls per report | Few or none on the alert path |
| Same input → same output | Not guaranteed | Yes |
| Explaining a decision | Long tree of branches | Short score trace with evidence IDs |

ToT improves accuracy when the right answer can be reached by thinking harder. In my project, the right answer comes from the road, so the agent should act and observe rather than deliberate.

## 5. Risk and Mitigation

**Risk:** without exploring alternatives, the agent may commit too early to a wrong interpretation, for example by treating a real hazard as cleared after one "road clear" report.

**Mitigation:** the agent never makes a final decision on weak evidence. Mixed evidence keeps a caution advisory active, one "clear" report cannot resolve a hazard on its own, observation requests gather new evidence, and events that stay conflicting for more than 2 minutes are escalated to a human fleet operator. I will test this with the existing `false_report` and `road_cleared` scenarios and a new conflicting-reports scenario.

## 6. When ToT Could Be Added Later

ToT may be useful outside the real-time alert path, where speed does not matter. One example is the Research Assistant planning a multi-step investigation for an operator, such as "Why do false alarms keep happening on Segment 14?" If I add it there, CrewAI could define separate generator and critic agents, LangChain could control the search, and MCP could share state between branches. For the safety-critical alert path, I am deliberately keeping a simple, fast, and predictable design.

## References

- Yao, S., et al. (2023). *Tree of Thoughts: Deliberate Problem Solving with Large Language Models.* NeurIPS 2023. arXiv:2305.10601.
- Yao, S., et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models.* ICLR 2023. arXiv:2210.03629.
- Shinn, N., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366.
- Cobbe, K., et al. (2021). *Training Verifiers to Solve Math Word Problems.* arXiv:2110.14168.
