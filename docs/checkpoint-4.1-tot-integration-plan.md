# Capstone Checkpoint 4.1: Tree-of-Thought Integration Plan

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas

## 1. Is ToT Appropriate?

**Decision: yes, but only in one place: resolving conflicting reports.**

Most reports have one obvious meaning, and the Checkpoint 3.1 confidence rules handle them in milliseconds. Running ToT on every report would add delay for no accuracy gain. ToT helps when **several nearby reports disagree**, so that more than one explanation fits the evidence and each explanation leads to a different alert.

## 2. Where ToT Is Used

**Workflow location:** a new **Conflict Resolution** step between the Hazard Analysis Agent and the Verification Agent. It runs only when reports within 200 m and 3 minutes disagree on hazard type or presence, or when a report matches more than one active event.

**Example.** On ROAD-01 in fog, Vehicle A reports a stopped truck at 3,500 m. Forty seconds later, Vehicle B reports debris at 3,580 m. Twenty seconds after that, Vehicle C reports "road clear" at 3,500 m.

**Why linear chain-of-thought fails here:**

- **Premature commitment.** Today, `find_matching_hazards()` greedily uses a 50 m radius. B is 80 m away, so it opens a separate debris event. C's "clear" then lowers the truck's confidence by 0.3. Once made, those choices are never revisited.
- **High branching.** At least four explanations fit: (H1) the truck shed its load, so this is one event spread over 80 m; (H2) there are two separate hazards; (H3) A misclassified debris as a truck; (H4) the hazard has been cleared. Each one alerts different vehicles with different messages.
- **Constraint complexity.** Each explanation must satisfy geometry, lane, timing, source reliability, and the safety exception at once. A single chain may find a violation only after it has acted.

## 3. ToT Structure

- **Thought:** a structured, partial *world hypothesis*, i.e. a JSON object (not free text) describing which reports belong to which event, what each event is, and what to do about it.
- **Node:** one hypothesis state plus its score and the evidence IDs it explains. The root holds the conflicting reports and active events.
- **Branch:** one alternative choice at a level, such as "B joins A's event" versus "B is a new event."
- **Depth:** three fixed levels:
  1. **Association:** which reports belong to which event (merge, split, or discard as false).
  2. **Interpretation:** each event's type and state (present, moved, misclassified, or cleared).
  3. **Action plan:** alert level per event (from the 3.1 thresholds) and which vehicles receive it.
- **Branching factor:** up to 4 children per node. **Depth limit:** 3.
- **Termination:** stop when depth 3 is reached, when the best leaf scores ≥ 0.80 and leads the runner-up by ≥ 0.10 (early stop), or when the budget runs out. The controller then outputs the best complete action plan.

## 4. Search and Evaluation Strategy

**Primary strategy: beam search (width k = 3).** BFS keeps every node (4 + 16 + 64 = 84 nodes), too many for a sub-second budget. DFS commits to one line of reasoning, which is the same premature-commitment problem I am trying to fix. Monte Carlo sampling adds randomness to safety decisions that need to be reproducible. Beam search keeps a few competing explanations alive at each level, with a fixed cost of at most 4 + 12 + 12 = 28 nodes.

**Evaluation is in two stages:**

1. **Hard constraint checks (deterministic tools; any failure sets the score to 0):** along-road distance and carriageway from the geospatial tool; physical plausibility (for example, a stopped truck cannot move 300 m in 20 s); time window; and the **safety exception**, meaning a plan may never give less than a caution advisory for a high-severity hazard in visibility under 200 m.
2. **Soft rubric (0–1 weighted score):**

| Criterion | Weight | Source |
|---|---|---|
| Evidence coverage: share of reports the hypothesis explains | 0.30 | Heuristic |
| Source reliability agreement | 0.25 | Long-term memory |
| Historical prior from similar incidents (±0.15 cap from 3.1) | 0.15 | RAG / ChromaDB |
| Parsimony: fewer events and fewer "false report" claims | 0.10 | Heuristic |
| Critic plausibility judgement | 0.20 | LLM critic |

**Who evaluates:** tool checks run first, so the LLM critic only sees physically possible branches. Following Cobbe et al. (2021), judging is easier than generating, but verifiers can be fooled, so the critic is grounded by tools.

**Pruning:** discard any branch that fails a hard check or scores < 0.40, then keep the top 3.

**Tie-breaking (scores within 0.05):** (1) prefer the more cautious plan, because a missed hazard costs more than a false alarm; (2) then prefer fewer events; (3) then let the critic rerank the tied pair.

**Failure conditions:** if every branch is pruned, or the budget runs out with no complete plan, the system falls back to the existing linear rules, sends at least a caution advisory, and flags the event for a human fleet operator.

**Compute, latency, and cost limits:** 1.5 s and 12 LLM calls per conflict. Levels 1 and 3 are generated by rules; the LLM generates only level 2 interpretations, and critic calls run in parallel. Meanwhile the deterministic path still sends its provisional advisory, so ToT never delays a warning; it only refines one.

## 5. Mapping ToT Roles to Tools

| ToT role | Tool | Why |
|---|---|---|
| **Thought generator**: "Hypothesis Agent" proposes children | **CrewAI** agent with its own role, goal, and output schema | Role separation means the generator cannot grade its own ideas. |
| **Critic / evaluator**: "Safety Critic Agent" plus tool checks | **CrewAI** agent for plausibility; **LangChain** tools wrap `distance_ahead()`, `find_approaching_vehicles()`, `retrieve_similar_incidents()` | An independent critic, calling the same geometry functions the production path uses. |
| **Controller / decision maker** | **LangChain** (LCEL `RunnableParallel` for expanding and scoring a level; runs as a node inside the existing LangGraph) | Selection, pruning, and budgets are testable code, not LLM output. |
| **Memory / state manager** | **MCP** server (`tot-state`) exposing `create_node`, `get_frontier`, `prune`, and `get_path`, plus the event store as a resource | CrewAI and LangChain share one tree through one protocol, so branch state never diverges; parent IDs let the Research Assistant explain the path later. |

## 6. Updated Architecture

```
Vehicle report
     │
     ▼
Hazard Analysis Agent ──(no conflict)──────────────────────────────┐
     │ conflict trigger                                            │
     ▼                                                             │
┌─────────── Conflict Resolution (ToT, ≤1.5 s) ───────────┐        │
│ LangChain controller (beam k=3, depth 3)                │        │
│   ├─ CrewAI Hypothesis Agent → children                 │        │
│   ├─ Tool checks (geometry, time, safety exception)     │        │
│   ├─ CrewAI Safety Critic → rubric score                │        │
│   └─ prune / select ◄──► MCP tot-state server           │        │
└──────────────┬──────────────────────────────────────────┘        │
               │ best plan (or fallback + operator flag)           │
               ▼                                                   ▼
        Research & Memory Agent (RAG) ──► Verification Agent ──► Alert Agent ──► Memory update
                                                                  (logs ToT path)
```

## 7. Risk and Mitigation

**Risk: weak evaluation signals prune the correct branch.** In fog, the true hazard often has the least evidence, such as one report from a low-reliability sensor. The rubric could rank "H4: cleared" above "H1: truck present" and drop the real hazard.

**Mitigation: a protected safety slot.** The beam always keeps the highest-severity "hazard present" branch that passes the hard checks, as a fourth slot outside k = 3, even if it scores below 0.40. If it does not win, it still keeps a caution advisory active until a second independent "clear" report arrives (the 3.1 resolution rule). I will test this with the `false_report` and `road_cleared` scenarios plus a new conflicting-reports scenario, checking that ToT never resolves a hazard that is actually present.

## References

- Yao, S., et al. (2023). *Tree of Thoughts: Deliberate Problem Solving with Large Language Models.* NeurIPS 2023. arXiv:2305.10601.
- Cobbe, K., et al. (2021). *Training Verifiers to Solve Math Word Problems.* arXiv:2110.14168.
- Wei, J., et al. (2022). *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models.* NeurIPS 2022. arXiv:2201.11903.
