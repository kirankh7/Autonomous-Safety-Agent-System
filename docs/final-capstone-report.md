# Final Capstone Report: Autonomous Vehicle Intercommunication Safety Agent System

**Author:** Kiran Haridas
**Program:** Carnegie Mellon University, Agentic AI
**Agent option:** Research Assistant
**Public repository:** https://github.com/kirankh7/Autonomous-Safety-Agent-System
**Presentation video (main):** https://youtu.be/obzEvUXOvYQ
**Elevator pitch (optional):** https://www.youtube.com/shorts/_W1MNYxP3tI
**Slide deck:** https://github.com/kirankh7/Autonomous-Safety-Agent-System/blob/main/docs/Final-Presentation-Kiran-Haridas.pptx

## 1. Problem and Intended User

An autonomous vehicle normally decides using only its own sensors. In dense fog, a vehicle cannot see a stopped truck 500 m ahead, even though another vehicle already beside that truck can. This system is a shared safety intelligence layer: it collects hazard reports from a fleet, checks whether they are reliable, and warns the vehicles that need to know. The intended users are fleet operators, who supervise the system and ask it questions, and the vehicles themselves, which receive advisory alerts.

A single LLM prompt is not enough. The system must link reports that arrive at different times, track confidence as evidence builds, decide which vehicles are on the affected path, retract a hazard when the road clears, and remember outcomes. That requires state, tools and a feedback loop, which is why this is an agent system.

## 2. Goal, Scope and Constraints

**Goal:** detect, verify and communicate unexpected road hazards early, with few false alarms and a clear audit trail.

**In scope:** hazard reports from a simulated fleet of eight vehicles, five road segments and seven scenarios; verification; targeted alerts; learning from outcomes; an operator dashboard with a Research Assistant.

**Out of scope and constraints:** all data is synthetic or public and no real vehicle is controlled. Alerts are advisory only. The confidence numbers are demonstration rules, not automotive safety standards. The system must keep working if retrieval or the language model fails.

## 3. Final Architecture

Four agents run as one LangGraph workflow. Each vehicle report is one run through the graph.

1. **Hazard Analysis Agent:** classifies the hazard, converts "500 m ahead" into a road position, and matches it to hazards already tracked (same segment and carriageway, within 50 m, or 150 m for related obstructions).
2. **Verification Agent:** applies the confidence rules and chooses verified alert, caution advisory, wait for evidence, or resolve.
3. **Alert Agent:** finds vehicles on the same road and direction behind the hazard, within 3 km, and sends alerts.
4. **Research & Memory Agent:** retrieves similar past incidents, saves outcomes, and powers the operator chat.

The coordination is a hybrid graph: a sequential fast path, plus a two-way history request and reply between Verification and Research & Memory for new hazards only, and a two-way observation request with the fleet. If retrieval fails, Verification scores on the rules alone, so the vector database can never block a warning. If vehicles disagree for 120 seconds, the hazard escalates to a human fleet operator. Every handoff is a typed message stored in SQLite and shown in the dashboard, and every step writes a reason, action, tool and result trace (ReAct, Yao et al., 2023).

## 4. Design Rationale

- **Rules decide, the LLM explains.** The same reports must always give the same alert, and an operator must be able to audit it. Tree-of-Thought was rejected: there are only four possible actions, so a tree of model-generated branches would be slower and less predictable without being more accurate.
- **Verification before alerting.** Judging a candidate report is easier than generating a correct one (Cobbe et al., 2021), so each report is a candidate scored on independent confirmation.
- **Two-tier memory.** SQLite holds the live situation (short-term) and resolved incidents (long-term). ChromaDB makes incidents searchable by meaning (Packer et al., 2024).
- **Retrieval kept out of the real-time path** except on cold-start segments and operator questions, so it adds history without adding latency risk.

## 5. How the Design Evolved

| Stage | Key refinement |
|---|---|
| Proposal | Defined the problem, users, inputs and the ten agent actions. |
| Agent design | Added the ReAct inner loop, a verifier, a Reflexion-style outcome loop (Shinn et al., 2023), short- and long-term memory, and a safety exception for low visibility. |
| Retrieval | Added RAG with metadata filtering, one chunk per incident, and a confidence rule set. Retrieval only changes scores on cold-start segments. |
| Reasoning | Decided against Tree-of-Thought, keeping a deterministic ReAct and verifier design. |
| Multi-agent | Chose the hybrid graph over a fully sequential or LLM-supervised design, added typed messages, the MCP-style tool registry, escalation and a coordination benchmark. |
| Safety | Added guardrails, evaluation metrics and the human-intervention rules. |
| Final integration | Added a local-LLM option, a Research Assistant with citation checking, and a public project home page. |

## 6. Implementation

The backend uses Python, FastAPI and LangGraph. Agents call eight tools through one MCP-style `call_tool()` interface that validates arguments and wraps failures. Memory uses SQLite; RAG uses ChromaDB with all-MiniLM-L6-v2 embeddings (cosine similarity, metadata filter inside the query, MMR for broad questions), with a FAISS and TF-IDF fallback. The frontend is React, Vite, TypeScript, Tailwind, Recharts and Leaflet. The Research Assistant runs in rule-based mode by default, on a local Qwen 2.5 7B model through Ollama (on the Apple GPU), or on Claude as an optional tool-calling agent. In every mode, a citation check rejects any record ID the system did not provide.

## 7. Evaluation Criteria

The design was judged on: (1) false warnings and false alerts, (2) agreement with the most thorough configuration, (3) cost per report (retrieval calls and milliseconds), (4) correct handling of conflict, and (5) grounded, auditable answers.

## 8. Results, Strengths and Limitations

A benchmark runs all seven scenarios (25 reports) under four coordination setups in a temporary database. Latency is measured on this machine.

| Configuration | RAG calls | ms/report | False warnings | Escalations | Same decisions |
|---|---|---|---|---|---|
| Hybrid (production) | 9 | ~25 | 0 | 1 | 25/25 |
| One-way (no history request) | 0 | ~9 | 1 | 1 | 20/25 |
| Sequential (every agent, every report) | 25 | ~48 | 0 | 1 | 25/25 |
| Single pass (no verifier) | 0 | ~12 | 1 | 0 | 12/25 |

Other results: in the flooding scenario, three retrieved past floods raise confidence from 0.50 to 0.65, turning a caution into a verified alert. In the fog scenario, confidence moves 0.50, 0.70, 0.40 and then 0.10 as reports arrive, and the outcome is learned (a replay then starts at 0.55). The conflicting-reports scenario escalates to the operator. 24 automated tests pass. With the local model, all 12 built-in scenario questions were answered in about 2 seconds with no fallbacks.

**Strengths:** the hybrid design matches the thorough setup at about half the cost, decisions are repeatable and traceable, and failures degrade to rules.

**Limitations:** the data is synthetic, the benchmark is small (25 reports), and the confidence thresholds are demonstration values. A 7B local model was unreliable as a tool-calling agent in testing: it timed out, looped, and cited records it never retrieved. That mode is off by default, and the local model only phrases answers from rule-selected records.

## 9. Safety, Reliability and Human Oversight

Guardrails check input, constrain decisions and verify outputs. A report needs independent confirmation before a verified alert; one clear report cannot resolve a hazard on its own; a high-severity hazard in visibility under 200 m always receives at least a caution; and a vehicle never receives the same message type twice. Anything beyond an advisory, such as closing a road, is always the operator's decision. A human is brought in on persistent conflict, an ungrounded answer, or a degraded system. Tools are read-only for the language model, which cannot send alerts or change confidence.

## 10. Future Improvements

Test on a larger labelled scenario set, add an NLI-based groundedness check, use real public crash narratives for retrieval, calibrate thresholds from outcomes, and study a larger local model for tool calling.

## 11. Repository

The public repository contains the README with architecture, setup and usage, the backend and dashboard code, the synthetic data, tests, the benchmark, and design documents for each stage.

## 12. Presentation, Videos and Slides

**Presentation video (required, 8-10 minutes):** https://youtu.be/obzEvUXOvYQ. This is a NotebookLM-generated version of the project presentation.

**Summary:** The presentation explains an Autonomous Vehicle Intercommunication Safety Agent System, in which four cooperating agents verify hazard reports from a simulated fleet, warn the vehicles that need it, and learn from outcomes. It covers the hybrid LangGraph architecture and key design decisions, the evaluation results (the production design matches the most thorough setup with zero false warnings at about half the cost), the safety and human-oversight design, the limitations, and the public GitHub repository.

**Elevator pitch (optional, ungraded, 90 seconds):** https://www.youtube.com/shorts/_W1MNYxP3tI

**Slide deck (10 slides):** https://github.com/kirankh7/Autonomous-Safety-Agent-System/blob/main/docs/Final-Presentation-Kiran-Haridas.pptx. The deck uses screenshots of the running dashboard. Its slides are:

| # | Slide | Main point |
|---|---|---|
| 1 | Title and problem | A shared safety layer so a vehicle can use what another vehicle sees |
| 2 | Goal, users and scope | Early, verified, auditable warnings with few false alarms |
| 3 | Architecture | Four agents in one LangGraph workflow, with a history loop and escalation |
| 4 | Live demo: fog | Confidence 0.50, 0.70, 0.40, then 0.10 resolved |
| 5 | Memory changes a decision | Retrieved history lifts a flooding report from 0.50 to 0.65 |
| 6 | Safety and human oversight | Guardrails and escalation to the fleet operator |
| 7 | Research Assistant | Cited, grounded answers from a local Qwen model |
| 8 | Evaluation | Hybrid: 0 false warnings and 25/25 same decisions |
| 9 | Design evolution and decisions | Rules decide, the LLM explains; two-tier memory; typed messages |
| 10 | Limits, next steps and repository | Public GitHub repository with README, code and tests |
