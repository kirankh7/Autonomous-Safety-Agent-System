# Elevator Pitch Script (90 seconds, optional)

Record separately from the main video. About 190 words at a steady pace.

An autonomous vehicle only knows what its own sensors can see. In fog, it can't see a stopped truck 500 metres ahead, but another vehicle can. My project is a shared safety intelligence layer for a fleet. Four agents in one LangGraph workflow analyse each hazard report, verify it with transparent confidence rules, alert only the vehicles heading toward it, and remember what they learn in a vector database. In the demo, one report starts at 0.50, a second vehicle confirms it to 0.70, and clear reports resolve it. If vehicles disagree for two minutes, it escalates to a human operator. In a benchmark of four coordination setups, my hybrid design had zero false warnings and matched the most thorough setup on all 25 decisions. The code is in my public GitHub repo.
