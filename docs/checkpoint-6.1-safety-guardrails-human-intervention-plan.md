# Capstone Checkpoint 6.1: Safety Guardrails and Human Intervention Plan

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas
**Code:** https://github.com/kirankh7/Autonomous-Safety-Agent-System

## 1. Purpose and Risks

Four agents turn hazard reports from a simulated fleet into alerts for vehicles that cannot yet see the hazard, such as a car in fog 500 m behind a stopped truck. The system is advisory only: it warns, it never steers. The risks follow the three sources of agent error from the module (task input, execution history, environment observations):

- **Bad input:** a false or malformed report (for example, radar-only "debris") becomes a false alarm.
- **Overconfidence:** one report is treated as proof, or a stale hazard keeps alerting.
- **Missed warning:** strict rules hold back a real hazard in low visibility.
- **Ungrounded answers:** the LLM Research Assistant invents incidents when an operator asks "why".
- **Unresolved conflict:** vehicles disagree and the agents keep looping.

## 2. Guardrails

| Stage | Guardrail |
|---|---|
| Input | Unknown vehicles and road segments are rejected; free-text hazards are mapped to six known types |
| Reasoning | Fixed confidence rules (start 0.50, +0.20 independent confirmation, −0.30 clear); retrieved history capped at ±0.15 so memory cannot decide alone; one vehicle cannot confirm itself |
| Output | Only four actions (verified alert, caution, wait and request observations, resolve); fixed alert templates; hazards expire with no reports |
| Safety floor | A high-severity hazard in visibility under 200 m always gets at least a caution |
| Sources | Every record ID the Research Assistant cites is checked against what its tools returned; unmatched IDs are flagged |
| Tool access | Tools go through one registry that validates arguments; the LLM gets read-only tools and cannot send alerts or change confidence |
| Monitoring | Every agent step, tool call, and message is logged and shown on the dashboard |

## 3. Evaluation Metrics

I measure these with `backend/benchmark.py` on seven labelled synthetic scenarios (25 reports):

| Metric | Current result |
|---|---|
| False verified alerts (hazard not real) | 0 |
| False warnings (alert or caution, hazard not real) | 0 |
| Real-hazard scenarios that warned approaching traffic | 6/6 |
| Escalation rate | 1 of 7 scenarios (the conflict case only) |
| Fallback success | retrieval failure → rules alone, alerting continues |
| Latency | 39 ms per report |
| Groundedness | unverified citations in operator answers (target 0) |

Removing the verifier, as in the lab's ablation method, produced 1 false alert and no escalation. This is the evidence that this guardrail is worth its cost.

## 4. When a Human Must Intervene

- **Persistent conflict:** two or more vehicles confirm and one reports clear for over 120 s. The hazard escalates to the fleet operator.
- **Ungrounded answer:** the Research Assistant cites a record its tools never returned, so the operator must check before relying on it.
- **Out-of-policy action:** anything beyond an advisory (closing a road, contacting emergency services) is always the operator's decision.
- **Degraded system:** retrieval or the LLM is down for a long time, so the operator is told the agents are running on rules only.

## 5. How the Pieces Work Together

Guardrails stop most errors where they enter. Logging makes every decision traceable. The benchmark checks that the guardrails actually help. Escalation catches what the rules cannot settle. As in Lab 6.2, the monitor does not need to be perfect. It only needs to send the few hard cases to a human so that human attention stays affordable.

## 6. Trade-offs

- **Autonomy vs. oversight:** routine hazards run without a human, and only real conflicts escalate. Escalating every caution would cause alert fatigue.
- **Reliability vs. sensitivity:** the 0.60 alert threshold limits false alarms, and the low-visibility floor accepts some extra cautions so that a real hazard is not missed.
- **Rules vs. LLM:** deterministic rules are fast and auditable. LLMs only explain decisions, never make them.
- **Efficiency:** guardrails add little cost (39 ms per report).

## 7. Real-World Deployment

Decisions can be repeated and audited, the system fails safe (rules keep running if retrieval fails), its outputs stay advisory, and humans own every high-impact or disputed decision. A real deployment would add a larger labelled scenario set and an NLI-based groundedness check, because the lab showed that word-overlap checks miss contradictions.

## References

- Cobbe, K., et al. (2021). *Training Verifiers to Solve Math Word Problems.* arXiv:2110.14168.
- Kutasov, J., et al. (2025). *SHADE-Arena: Evaluating Sabotage and Monitoring in LLM Agents.* arXiv:2506.15740.
- Baker, B., et al. (2025). *Monitoring Reasoning Models for Misbehavior.* arXiv:2503.11926.
- Korbak, T., et al. (2025). *Chain of Thought Monitorability.* arXiv:2507.11473.
- Course Lab 6.1: *Guardrailing Hallucinations and Overconfidence in Agent Outputs* (three-source framework, ablation).
