"""Drive the dashboard through the video script in its own Chrome window, so you can screen-record it.

No browser extension is involved, so nothing on screen says an AI is controlling the page.
You narrate; the script does the clicking, with a visible cursor and calm pauses.

    python scripts/record_demo.py              # waits for Enter before each section (you narrate, then continue)
    python scripts/record_demo.py --auto       # runs straight through with fixed pauses
    python scripts/record_demo.py --headless --fast --auto    # selector check only (no window)

Run ./scripts/prepare_recording.sh first. Needs the backend (8000) and frontend (5173) running.
"""
import argparse
import sys
import time

from playwright.sync_api import sync_playwright

URL = "http://localhost:5173"

CURSOR_JS = """
(() => {
  const dot = document.createElement('div');
  dot.style.cssText = 'position:fixed;z-index:2147483647;width:22px;height:22px;margin:-11px 0 0 -11px;' +
    'border-radius:50%;background:rgba(255,200,0,.55);border:2px solid #ffc800;pointer-events:none;' +
    'transition:transform .08s;left:-50px;top:-50px';
  const add = () => document.body && document.body.appendChild(dot);
  document.body ? add() : document.addEventListener('DOMContentLoaded', add);
  addEventListener('mousemove', e => { dot.style.left = e.clientX + 'px'; dot.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', () => dot.style.transform = 'scale(.6)', true);
  addEventListener('mouseup', () => dot.style.transform = 'scale(1)', true);
})();
"""


class Demo:
    def __init__(self, page, fast: bool, auto: bool):
        self.page, self.fast, self.auto = page, fast, auto

    def pause(self, seconds: float) -> None:
        time.sleep(0.05 if self.fast else seconds)

    def move_to(self, locator) -> tuple[float, float]:
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(x, y, steps=4 if self.fast else 30)
        return x, y

    def click(self, locator, after: float = 1.0) -> None:
        self.move_to(locator)
        self.pause(0.4)
        locator.click()
        self.pause(after)

    def hover(self, locator, after: float = 1.2) -> None:
        self.move_to(locator)
        self.pause(after)

    def next_step(self, after: float = 3.0) -> None:
        button = self.page.get_by_role("button", name="Next Step")
        self.click(button, after=0.2)
        # the button is disabled while the agents (and the local model) are working
        self.page.wait_for_function(
            "() => [...document.querySelectorAll('button')].find(b => b.textContent.includes('Next Step'))"
            " && ![...document.querySelectorAll('button')].find(b => b.textContent.includes('Next Step')).disabled"
            " || document.body.innerText.includes('complete')", timeout=90000)
        self.pause(after)

    def scroll(self, pixels: int, after: float = 1.0) -> None:
        self.page.mouse.wheel(0, pixels)
        self.pause(after)

    def nav(self, label: str) -> None:
        self.click(self.page.get_by_text(label, exact=True).first, after=1.5)

    def card(self, title: str) -> None:
        self.click(self.page.get_by_role("button").filter(has_text=title).first, after=1.0)

    def section(self, number: int, title: str, say: str, hold: float) -> None:
        print(f"\n=== {number}. {title} ===\n    Say: {say}")
        if self.auto:
            self.pause(hold)
        else:
            input("    Start narrating, then press Enter here to run this section... ")


def run(args) -> None:
    with sync_playwright() as p:
        launch = dict(
            headless=args.headless,
            args=["--window-size=1500,960", "--window-position=40,30", "--disable-infobars",
                  "--no-default-browser-check", "--hide-crash-restore-bubble"],
            ignore_default_args=["--enable-automation"],  # removes the "controlled by automated software" bar
        )
        try:
            browser = p.chromium.launch(channel="chrome", **launch)
        except Exception:
            browser = p.chromium.launch(**launch)
        context = browser.new_context(viewport={"width": 1440, "height": 810})
        context.add_init_script(CURSOR_JS)
        page = context.new_page()
        d = Demo(page, args.fast, args.auto)

        page.goto(URL + "/#dashboard")
        page.wait_for_selector("text=Fleet Dashboard")
        page.mouse.move(700, 400)
        status = page.locator("text=LLM:").first.inner_text()
        print("Sidebar says:", status.replace("\n", " "))

        d.section(1, "Introduction (project home page, animation plays)", "problem, users, goal", 45)
        page.goto(URL + "/home.html")
        page.wait_for_selector("text=agent.log")
        page.mouse.move(1000, 450)
        d.pause(45)                          # let the 42 s animation play once while you introduce the project
        page.goto(URL + "/#dashboard")
        page.wait_for_selector("text=Fleet Dashboard")
        d.hover(page.get_by_text("Simulated fleet"), 2)

        d.section(2, "Live demo: fog", "0.50 caution -> 0.70 verified -> clear -> resolved", 120)
        d.nav("Hazard Simulation")
        d.card("Stopped truck in fog")
        d.next_step(4)                      # Tesla reports: 0.50 caution
        d.scroll(350, 3)                    # show signals and messages
        d.scroll(-350, 1)
        d.next_step(4)                      # Prius confirms: 0.70 verified
        d.next_step(6)                      # "why was Ford Transit alerted?"
        for _ in range(3):                  # Volvo clear, Ioniq clear, "why resolved?"
            d.next_step(4)

        d.section(3, "Architecture (Agent Activity)", "four agents, hybrid graph, trace", 90)
        d.nav("Agent Activity")
        for node in ("1 · Hazard Analysis", "2 · Verification", "3 · Alert", "4 · Memory update"):
            d.hover(page.get_by_text(node, exact=True).first, 2.5)
        d.hover(page.get_by_text("History (RAG)").first, 3)
        d.hover(page.get_by_text("Fleet operator").first, 3)
        d.scroll(500, 4)
        d.scroll(-500, 1)

        d.section(4, "Memory changes a decision: flooding", "+0.15 history -> verified 0.65", 40)
        d.nav("Hazard Simulation")
        d.click(page.get_by_role("button", name="Reset Scenario"), 1.5)
        d.card("Flooding")
        d.next_step(5)
        d.hover(page.get_by_text("HISTORY +0.15").first, 3)

        d.section(5, "Safety: conflicting reports", "escalation to the fleet operator", 50)
        d.click(page.get_by_role("button", name="Reset Scenario"), 1.5)
        d.card("Conflicting reports")
        for _ in range(3):
            d.next_step(3.5)
        d.next_step(2)                      # step 4: escalation fires
        d.hover(page.get_by_text("ESCALATED").first, 4)
        d.next_step(5)                      # "why was it escalated?"

        d.section(6, "Research Assistant", "local Qwen, grounded and cited", 50)
        d.nav("Research Assistant")
        d.click(page.get_by_text("Why was an alert generated for Ford Transit?"), 1)
        page.wait_for_selector("text=answer mode", timeout=60000)
        d.pause(5)
        d.click(page.get_by_text("What similar incidents happened previously?"), 1)
        page.wait_for_function("() => document.body.innerText.split('answer mode').length > 2", timeout=60000)
        d.pause(5)

        d.section(7, "Evaluation: benchmark", "hybrid vs one-way vs sequential vs no verifier", 60)
        d.nav("Fleet Dashboard")
        d.scroll(2000, 1.5)
        d.click(page.get_by_role("button", name="Run benchmark"), 0.5)
        page.wait_for_selector("text=single_pass", timeout=120000)
        d.scroll(2000, 1)
        d.hover(page.get_by_text("hybrid", exact=True).first, 6)

        d.section(8, "Design decisions, limits and repo", "switch to the GitHub tab yourself", 70)
        print("\nDone. Stop your screen recording after you finish the last section.")
        if not args.auto and not args.headless:
            input("Press Enter to close the browser... ")
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true", help="do not wait for Enter between sections")
    ap.add_argument("--fast", action="store_true", help="skip pauses (for testing selectors)")
    ap.add_argument("--headless", action="store_true", help="no window (for testing)")
    try:
        run(ap.parse_args())
    except KeyboardInterrupt:
        sys.exit(0)
