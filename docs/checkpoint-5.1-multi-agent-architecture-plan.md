# Capstone Checkpoint 5.1: Multi-Agent Architecture and Coordination Plan

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas
**Code:** https://github.com/kirankh7/Autonomous-Safety-Agent-System

## 1. Problem and Why Multiple Agents

The system turns hazard reports from a simulated fleet into verified alerts for vehicles that cannot yet see the hazard, such as a car in fog 500 m behind a stopped truck. Each report needs four different jobs: locate it, judge whether it is real, decide who to warn, and remember the outcome. A single agent would mix these jobs in one prompt and one state, so an error in one (a weak retrieval result) could silently change another (who gets alerted). Separate agents give each job its own tools and trace, so every decision can be checked.

## 2. Number of Agents and Roles

**Four agents.** I grouped the ten actions from my proposal by the data each one needs. Actions that share data stay together; actions that must check each other are split.

| Agent | Responsibility | Tools |
|---|---|---|
| 1. Hazard Analysis | Classify the report, place it on the road, match it to a tracked event | `find_matching_hazards`, `get_vehicle_reports` |
| 2. Verification | Score the evidence with the confidence rules and choose one of four actions | `verify_hazard` |
| 3. Alert | Find vehicles approaching on the same carriageway; send alerts or observation requests | `find_approaching_vehicles`, `send_mock_alert` |
| 4. Research & Memory | Retrieve similar past incidents, store outcomes, answer operator questions | `retrieve_similar_incidents`, `update_hazard_memory` |

Verification is separate from Hazard Analysis on purpose: judging a candidate is a different job from producing it (Cobbe et al., 2021). I stopped at four. A separate "Locator" or "Weather" agent would only pass data along, adding messages without adding a decision. Li et al. (2024) gain accuracy from more agents through voting, but my rules are deterministic, so extra voters would return the same answer.

## 3. Coordination Strategy

**Hybrid, graph-based (LangGraph).** The main path is sequential, like an assembly line: Analysis → Verification → Alert → Memory. Conditional edges make it a graph. A road-clear report with nothing to clear goes straight to Memory. A new hazard triggers a loop from Verification to Research & Memory and back before scoring, while updates to known hazards skip retrieval. There is no LLM supervisor: routing depends only on state, so the same reports always take the same path.

## 4. Communication

Agents share one typed state and send explicit messages (sender, receiver, kind, protocol) that are logged and shown on the dashboard.

- **One-way handoffs** on the fast path (`new_hazard`, `decision`, `alerts_sent`), with no waiting.
- **Two-way request/reply** only where validation is needed. Verification sends `history_request`, and Research & Memory replies with a capped adjustment (±0.15). The second two-way loop is with the fleet: a vehicle answers an observation request with its next report, which Hazard Analysis links back to the request.
- **No brainstorming.** Checkpoint 4.1 showed that exploring alternatives adds latency without improving a four-outcome decision.

All tools are called through one MCP-style interface (`call_tool`) that validates arguments and counts calls.

## 5. Trade-offs

I benchmarked four configurations on my seven scenarios (25 reports):

| Configuration | Retrieval calls | ms / report | False warnings | Same decisions as hybrid |
|---|---|---|---|---|
| Hybrid graph (chosen) | 9 | 26 | 0 | 25/25 |
| One-way only (no history request) | 0 | 8 | 1 | 20/25 |
| Fixed sequential (every agent, every report) | 25 | 47 | 0 | 25/25 |
| Single pass, no verifier | 0 | 12 | 1 | 12/25 |

- **Two-way vs. one-way:** skipping the history request is 3× faster but changes 5 decisions, including a caution advisory for a false radar report. The two-way step stays, but only for new hazards.
- **Reliability vs. latency:** dropping verification sent a verified alert for that false report, so the verifier stays.
- **Complexity vs. overhead:** a fixed pipeline is simpler but nearly triples retrieval calls for identical decisions.
- **Failure handling:** if retrieval fails, Verification scores on the rules alone. If vehicles keep disagreeing for 2 minutes, the agents stop asking and escalate to a human operator.

## 6. Scalability

Messages grow with the number of reports, not with the square of the number of agents, because only one agent pair talks two-way. Hazards never span road segments, so reports on different segments can later be processed in parallel. The prototype runs them one at a time. New tools join the registry without changing agent code, and operator questions run outside the alert path.

## References

- Cobbe, K., et al. (2021). *Training Verifiers to Solve Math Word Problems.* arXiv:2110.14168.
- Li, J., et al. (2024). *More Agents Is All You Need.* arXiv:2402.05120.
- LangChain (2024). *Benchmarking Multi-Agent Architectures.* blog.langchain.com.
- *Which LLM Multi-Agent Protocol to Choose?* arXiv:2510.17149.
- Yao, S., et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models.* ICLR 2023.
