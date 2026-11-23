# Recording Runbook (a script drives its own Chrome window, no Claude on screen)

Narration: `video-narration-script.md`. Elevator pitch: `elevator-pitch-script.md` (record separately).

## Before every take (2 minutes)

1. Backend and frontend running:
   - `cd autonomous-vehicle-agent && source .venv/bin/activate && uvicorn backend.main:app --port 8000`
   - `cd autonomous-vehicle-agent/frontend && npm run dev`
2. Ollama running (`ollama serve`) with the model pulled (`ollama pull qwen2.5:7b`, already done).
3. Run `./scripts/prepare_recording.sh` from `autonomous-vehicle-agent/`. It resets memory to 20 incidents,
   clears the playground, and loads the model onto the GPU. (It replaces the **Reset All Memory** button, so you
   never hit its browser confirm box.)
4. Start the demo script in a terminal on a second screen:
   `python scripts/record_demo.py`
   It opens its own clean Chrome window (no extension, no "controlled by automated software" bar, no
   bookmarks) with a visible yellow cursor. The sidebar must say **LLM: ollama local (qwen2.5:7b)**; it prints this.
5. Start your screen recording on that Chrome window (a window or region capture, not the whole desktop).
6. Have the GitHub repo open in a second tab of your normal Chrome for the last section.

## How a take works

The terminal prints each section's title, then waits. **You narrate; press Enter and the script does the
clicking** for that section, with 2-6 second pauses so viewers can read the screen. After the section, keep
talking until you've finished the narration, then press Enter for the next one.
Use `--auto` to run straight through with fixed pauses (about 9 minutes), if you want to narrate over it.

| # | Time | Section the script runs |
|---|---|---|
| 1 | 0:00-0:50 | Project home page: the animation plays once, then the Fleet Dashboard opens |
| 2 | 0:50-3:00 | Fog scenario, 7 steps, scrolls to show signals and messages |
| 3 | 3:00-4:30 | Agent Activity: cursor moves along the graph, then the trace |
| 4 | 4:30-5:10 | Reset, flooding, 1 report, cursor on "HISTORY +0.15" |
| 5 | 5:10-6:00 | Reset, conflicting reports, cursor on "ESCALATED" |
| 6 | 6:00-6:50 | Research Assistant: 2 suggested questions |
| 7 | 6:50-7:50 | Dashboard: Run benchmark, cursor on the table |
| 8 | 7:50-9:00 | Nothing to click. You switch to the GitHub tab |

## Lessons from the dry run (so they don't repeat)

- The script waits for each step to finish before it clicks again, so no clicks are dropped.
- **Reset Scenario** between scenarios. It keeps the 20 seed incidents plus anything learned.
- Fog adds a learned incident, so the header shows 21 afterwards. That's expected.
- Do **not** use the Playground before Research. Random traffic changes which hazard the questions refer to.
  If you want to show it, do it last, after "Reset playground", and never before the Research section.
- Use short Research questions. Longer questions give long answers that are hard to read aloud.
- Agent Activity looks empty if you open it before running a scenario. That's why fog comes first.
- The agent signal strip and message list are below the first screen on the simulation page. Scroll down a
  little to show them, then scroll back up.
- The benchmark table is at the bottom of the dashboard, so scroll down after clicking Run benchmark.

## If something goes wrong mid-take

- Stumble in your narration: keep going, you can cut it in editing. Pause for 3 seconds before repeating the line.
- Page looks odd: click **Reset Scenario** and replay that segment. Don't use **Reset All Memory** while recording.
- A Research answer looks off: ask the question again or pick another suggested one. Say nothing about the wording.
- Answers suddenly look plain: Ollama stopped and the app fell back to rules. Run `ollama serve`, then
  `./scripts/prepare_recording.sh`.
- Starting over: run `./scripts/prepare_recording.sh` again, Cmd+R, and restart from segment 1.

## Submission checklist

- [ ] Repo is public and the README renders
- [ ] Video is 8-10 minutes and shows or names the GitHub repo clearly
- [ ] Video uploaded to Canvas with the report (PDF or DOCX)
- [ ] Report and video describe the same architecture and results
- [ ] (Optional) 90-second pitch recorded separately
