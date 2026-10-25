# Capstone Checkpoint 3.1: RAG and Retrieval Design Integration

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas

## 1. Retrieval Decision

**Decision: retrieval is required, but only for unstructured knowledge, and it stays out of the real-time alert path.**

Most of what the agent knows is structured and found by exact keys: active events by road segment and direction, along-road distance, source reliability by vehicle ID, and hazard history by segment. Semantic search is the wrong tool here: a flood at a *different* underpass is semantically similar but irrelevant, and a vehicle 550 m away at 90 km/h is about 22 seconds out, so decisions must be fast and reproducible. These lookups stay as database and geospatial queries. Severity and recommended action per hazard type come from a fixed table built from public FHWA and NWS guidance.

Retrieval fills two gaps where exact keys fail:

1. **Cold start.** A newly added or rarely travelled segment has no history, so the structured lookup returns nothing. Semantic search over past incident narratives finds similar situations elsewhere (e.g., "low-lying underpass, heavy rain, standing water").
2. **Operator questions.** A fleet manager asks, "Why did we alert on Segment 31 last night?" This is a natural-language question over free-text logs, the core of the Research Assistant role.

## 2. Integration

- **External data sources (public or synthetic):** NHTSA Standing General Order crash reports, which include free-text narratives of incidents involving automated driving systems; synthetic incident logs; and the reflective lessons store from Checkpoint 2.1.
- **Pipeline:** documents are chunked and embedded with a sentence-embedding model, then stored in a local vector database (e.g., Chroma) with metadata. At query time, the agent first applies a **metadata pre-filter** (hazard type, road feature, weather), then ranks the remaining chunks by cosine similarity.
- **When it runs:** only if the structured history lookup returns no events for the segment, or when an operator asks a question. Once a segment has three or more resolved events of its own, its own history replaces retrieval.

## 3. Confidence Rule Set

Following Checkpoint 1.1 feedback, the feedback loop is now a numeric rule set, with retrieval as one bounded input.

| Rule | Effect |
|---|---|
| New report | Starts at 0.5, adjusted by source reliability |
| Independent confirmation (within 50 m along-road, same direction, within 2 min) | +0.2 |
| A passing vehicle reports no hazard | −0.3 |
| Each retrieved similar incident where the hazard was confirmed | +0.05 (max +0.15) |
| Each retrieved similar incident that was a false report | −0.05 (max −0.15) |
| No new reports for 15 minutes | Event expires |

**Actions:** at **≥ 0.6**, send an alert. At **0.4–0.6**, send a caution advisory and request observations from approaching vehicles. Below **0.4**, send no alert and request more observations. Below **0.2**, or after two "clear" reports, resolve the event. The 2.1 safety exception remains: a high-severity hazard in visibility under 200 m always receives at least a caution advisory.

## 4. How Retrieval Changes the Output

**Cold-start example.** At night in heavy rain, Vehicle D reports "water across both lanes under the rail bridge" on Segment 31, which has no recorded history.

| Step | Without retrieval | With retrieval |
|---|---|---|
| Starting score | 0.5 | 0.5 |
| Retrieval | — | Top 3 incidents (filtered to flooding, underpass, rain) were all confirmed: +0.15 |
| Final score | 0.5 | 0.65 |
| Output | Caution advisory: "possible water, slow down" | **Alert:** flooding at underpass, high severity, recommended action "reroute," citing the three incident IDs |

Retrieval also lowers confidence. If the retrieved similar debris reports were mostly false single-sensor detections, a single new report drops to 0.35. The agent sends no alert and requests observations from approaching vehicles.

**Operator example.** Without retrieval, the model invents a plausible explanation for an alert. With retrieval, it answers from the event's own records (reports, score trace, outcome) and cites them.

## 5. Key Design Choices

- **Segmentation:** one incident narrative, closed-event summary, or lesson per chunk, since splitting would separate cause from outcome. Narratives longer than about 300 tokens are split by paragraph with a 50-token overlap, and each chunk keeps its incident ID.
- **Metadata on every chunk:** hazard type, road feature, weather, segment ID, date, source, and outcome (confirmed or false).
- **Number of results:** top 3 for cold-start scoring, which matches the ±0.15 cap at 0.05 each. Top 5 for operator questions, where completeness matters more. A minimum similarity threshold (e.g., cosine ≥ 0.75) means a weak match returns nothing rather than noise.

## 6. Failure Mode: Misleading Analogues

The main risk is retrieving cases that read as similar but differ in what matters. For example, "water across lanes" could retrieve a water-main break on a dry day, or an outdated report from an underpass that has since been rebuilt. If trusted, these could inflate or suppress confidence.

The design manages this in five ways:

1. **Pre-filtering** on hazard type, road feature, and weather happens *before* similarity ranking.
2. **Recency weighting** down-weights older records.
3. **A hard cap** of ±0.15 means retrieval can shift a decision but never outweigh live evidence. A single "no hazard" report (−0.3) outweighs the full retrieval boost.
4. **Retrieval never creates an event**; a live vehicle report is always required.
5. **Every alert logs the retrieved chunk IDs**, so operators can audit and correct bad analogues.

## References

- Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020. arXiv:2005.11401.
- NHTSA. *Standing General Order on Crash Reporting.* https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting
- FHWA. *Traffic Incident Management.* https://ops.fhwa.dot.gov/tim/
- National Weather Service. *Turn Around Don't Drown.* https://www.weather.gov/safety/flood-turn-around-dont-drown
