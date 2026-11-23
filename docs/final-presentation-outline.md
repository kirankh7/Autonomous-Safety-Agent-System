# Final Presentation Outline

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas
**Length:** 10 slides, 8-10 minutes. The live dashboard demo is shown during slides 4 to 7.
**Repository:** https://github.com/kirankh7/Autonomous-Safety-Agent-System

## Slide plan

| # | Slide | Time | Content on the slide | Say (key points) |
|---|---|---|---|---|
| 1 | Title and problem | 0:00-0:50 | Title, name, one picture of a vehicle in fog with a hidden stopped truck 500 m ahead | The vehicle cannot see what another vehicle already sees. A shared safety layer fixes that. Simulation only, advisory only. |
| 2 | Goal, users and scope | 0:50-1:30 | Goal, users (fleet operators, vehicles), in scope, out of scope, constraints | Early, verified, auditable hazard warnings with few false alarms. Synthetic data. Demonstration confidence rules. |
| 3 | Architecture | 1:30-3:00 | The four-agent LangGraph diagram with the history loop and the operator escalation | Why an agent and not one prompt. What each agent does. Hybrid graph, typed messages, failover to rules. |
| 4 | Live demo: fog | 3:00-4:30 | Dashboard, fog scenario | 0.50 caution, 0.70 verified, clear reports drop it to 0.40, then 0.10 resolved, and the outcome is learned. |
| 5 | Memory and retrieval | 4:30-5:15 | Dashboard, flooding scenario, "+0.15 history" signal | ChromaDB RAG changes a decision on a cold-start road: 0.50 to 0.65. Live evidence still outranks history. |
| 6 | Safety and human oversight | 5:15-6:15 | Dashboard, conflicting-reports scenario, escalation alert | Guardrails, no resolve on one clear report, escalation to the operator after 120 s, advisory only. |
| 7 | Research Assistant | 6:15-6:45 | Chat with cited record IDs | Grounded answers, citation check, local Qwen model on the GPU. The LLM explains but never decides. |
| 8 | Evaluation | 6:45-8:00 | Benchmark table (four configurations) | Hybrid: 0 false warnings, 25/25 same decisions, 9 retrieval calls instead of 25, about half the latency. 24 tests pass. |
| 9 | Design evolution and decisions | 8:00-8:40 | Timeline of refinements across the program, plus three decisions | Rules decide, LLM explains (no Tree-of-Thought). Two-tier memory. Typed messages. |
| 10 | Limits, next steps, repository | 8:40-9:30 | Limitations, future work, GitHub URL, README screenshot | Synthetic data, small benchmark, demo thresholds. Public repo with README, setup steps and tests. |

## Checklist before recording

- The slides and the dashboard are both visible during the recording.
- The GitHub URL is on slide 1 or 10 and is spoken aloud.
- The repository is public and its README renders.
- The numbers on the slides match the report (benchmark table, 24 tests, 0.50 / 0.70 / 0.40 / 0.10, 0.65).
- The video is 8-10 minutes and uploaded as unlisted.

## Where the spoken text is

The read-aloud script is `video-narration-script.md`. The click-by-click runbook is `video-recording-runbook.md`.
