# Capstone Checkpoint 3.1: RAG and Retrieval Design Integration

**Project:** Autonomous Vehicle Intercommunication Safety Agent System
**Author:** Kiran Haridas

## 1. Retrieval Decision

**Decision: retrieval is required, but only for unstructured knowledge, and it stays out of the real-time alert path.**

Most of what the agent knows is structured and found by exact keys: active events by segment and direction, along-road distance, source reliability, and segment history. Semantic search is the wrong tool here: a flood at a *different* underpass is semantically similar but irrelevant, and a vehicle 22 seconds away needs fast, reproducible decisions. These stay as database and geospatial queries, and severity per hazard type comes from a fixed table based on FHWA and NWS guidance.

Retrieval fills two gaps where exact keys fail:

1. **Cold start.** A new or rarely travelled segment has no history. Semantic search over incident narratives finds similar situations elsewhere (e.g., "low-lying underpass, heavy rain, standing water").
2. **Operator questions.** A fleet manager asks, "Why did we alert on Segment 31 last night?" This is a natural-language question over free-text logs, the core of the Research Assistant role.

## 2. Integration

- **External data sources (public or synthetic):** NHTSA Standing General Order crash narratives for automated vehicles, synthetic incident logs, and the 2.1 lessons store.
- **Pipeline:** a dense retriever in the style of DPR (Karpukhin et al., 2020) embeds queries and chunks with a sentence encoder (all-MiniLM-L6-v2) into a FAISS index. At query time, the agent applies a **metadata pre-filter** (hazard type, road feature, weather), then ranks the remaining chunks by similarity.
- **Memory tiers:** as in MemGPT (Packer et al., 2024), the context window holds only the live event and the top-k retrieved chunks, while the full history stays in external storage.
- **When it runs:** only when a segment has no structured history or an operator asks a question. Once a segment has three resolved events of its own, its own history replaces retrieval.

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

Retrieval can also lower confidence: if similar past debris reports were mostly false, a single new report drops to 0.35, so the agent sends no alert and requests observations.

**Operator example.** Without retrieval, the model invents a plausible explanation for an alert. With retrieval, it answers from the event's own records (reports, score trace, outcome) and cites them.

## 5. Key Design Choices

- **Segmentation:** one incident narrative, closed-event summary, or lesson per chunk, since splitting would separate cause from outcome. Longer narratives are split into 100-word blocks, as in DPR. Following DPR's practice of prepending the article title, each chunk is prefixed with a header (e.g., `Flooding | Underpass | Heavy rain [SEP] …`) so the embedding captures context.
- **Metadata on every chunk:** hazard type, road feature, weather, segment ID, date, source, and outcome (confirmed or false).
- **Cold-start scoring: top 3, pure relevance, one vote per incident.** This is a narrow, precision-critical query, the case where the MMR lab recommends favoring relevance. Retrieved chunks are collapsed by incident ID, so five vehicles describing one flood count as one +0.05, not three.
- **Operator questions: top 5 with MMR (λ = 0.5, from 20 candidates).** Questions like "what hazards recur in fog?" are broad and multi-faceted, so MMR (Carbonell & Goldstein, 1998) avoids five near-identical fog reports and covers distinct hazard types.
- **Similarity threshold** (e.g., cosine ≥ 0.75): a weak match returns nothing rather than noise.

## 6. Failure Mode: Misleading Analogues

Retrieved cases may read as similar but differ in what matters: "water across lanes" could retrieve a water-main break on a dry day, or a report from an underpass since rebuilt. Trusted blindly, these distort confidence. The design manages this in five ways:

1. **Pre-filtering** on hazard type, road feature, and weather happens *before* similarity ranking.
2. **Recency weighting** of older records.
3. **A ±0.15 cap:** a single "no hazard" report (−0.3) outweighs the full retrieval boost.
4. **Retrieval never creates an event**; a live vehicle report is always required.
5. **Logged chunk IDs** on every alert, so operators can audit bad analogues.

## References

- Carbonell, J., & Goldstein, J. (1998). *The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries.* SIGIR 1998.
- Karpukhin, V., et al. (2020). *Dense Passage Retrieval for Open-Domain Question Answering.* EMNLP 2020.
- Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020. arXiv:2005.11401.
- Packer, C., et al. (2024). *MemGPT: Towards LLMs as Operating Systems.* arXiv:2310.08560.
- NHTSA. *Standing General Order on Crash Reporting.* https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting
- FHWA. *Traffic Incident Management.* https://ops.fhwa.dot.gov/tim/
- National Weather Service. *Turn Around Don't Drown.* https://www.weather.gov/safety/flood-turn-around-dont-drown
