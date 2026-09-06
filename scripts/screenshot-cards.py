#!/usr/bin/env python3
"""Render each MCP App card to docs/images/cards/ for the documentation.

The cards are driven by fixture data, not by this machine's Runtime. Two
reasons. A screenshot of a real catalogue carries whatever that operator was
working on into the repository, and a screenshot of live data is different
every time it is taken, so the diff of a regenerated image says nothing about
whether the card changed.

Run it after changing a card:

    .venv/bin/python scripts/screenshot-cards.py

Needs playwright with chromium installed (`pip install -e '.[dev]'` plus
`playwright install chromium`).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orbit.web import mcp_app  # noqa: E402

OUT = ROOT / "docs/images/cards"

# A fixed day, so a card that prints "today" prints the same thing on every
# machine that regenerates these.
DAY = "2026-03-11"


def at(day: str, time: str) -> str:
    return f"{day}T{time}:00+00:00"


WORKFLOWS = [
    {"workflow_id": "workflow:draft-review", "name": "Draft · review · rework",
     "description": "An Agent drafts, a person reviews; a rejection carries its"
                    " reason back for one more pass.",
     "node_count": 6, "latest_version": 3},
    {"workflow_id": "workflow:incident", "name": "Incident report",
     "description": "", "node_count": 15, "latest_version": 5},
    {"workflow_id": "workflow:translate", "name": "Translate to English",
     "description": "", "node_count": 2, "latest_version": 1},
    {"workflow_id": "workflow:release-notes", "name": "Release notes",
     "description": "", "node_count": 8, "latest_version": 2},
    {"workflow_id": "workflow:triage", "name": "Inbox triage",
     "description": "", "node_count": 4, "latest_version": 1},
]

RUNS = [
    {"run_id": "run:0091", "status": "interrupted", "goal": "Draft the migration note for the storage change",
     "workflow_id": "workflow:draft-review", "created_at": at(DAY, "09:12"),
     "updated_at": at(DAY, "09:18"), "artifact_count": 1,
     "interrupts": [{"value": {"config": {"task_kind": "approval"},
                               "output_ports": [{"name": "result"}]}}]},
    {"run_id": "run:0090", "status": "completed", "goal": "Translate the release announcement",
     "workflow_id": "workflow:translate", "created_at": at(DAY, "08:40"),
     "updated_at": at(DAY, "08:41"), "artifact_count": 1, "interrupts": []},
    {"run_id": "run:0089", "status": "failed", "goal": "Summarise yesterday's incident",
     "workflow_id": "workflow:incident", "created_at": at(DAY, "08:02"),
     "updated_at": at(DAY, "08:05"), "artifact_count": 0, "interrupts": []},
    {"run_id": "run:0088", "status": "completed", "goal": "Draft release notes for 0.4.0",
     "workflow_id": "workflow:release-notes", "created_at": at(DAY, "07:30"),
     "updated_at": at(DAY, "07:52"), "artifact_count": 2, "interrupts": []},
    {"run_id": "run:0087", "status": "cancelled", "goal": "Triage the overnight inbox",
     "workflow_id": "workflow:triage", "created_at": at(DAY, "07:05"),
     "updated_at": at(DAY, "07:09"), "artifact_count": 0, "interrupts": []},
]

ANSWERS = {
    "list_workflows": {"workflows": WORKFLOWS},
    "list_runs": {"runs": RUNS},
    "list_agents": {"agents": [
        {"name": "agent.claude", "version": "2.1.260", "attempt_count": 128, "failed_count": 1},
        {"name": "agent.codex", "version": "0.147.0", "attempt_count": 94, "failed_count": 0},
        {"name": "agent.opencode", "version": "1.18.16", "attempt_count": 41, "failed_count": 2},
        {"name": "agent.kimi", "version": "0.37.2", "attempt_count": 0, "failed_count": 0},
    ]},
    "list_authoring_jobs": {"jobs": [
        {"job_id": "job:0007", "status": "running",
         "prompt": "A workflow that drafts a changelog, has a person review it,"
                   " and reworks it once if rejected."},
    ]},
    "get_run_steps": {"steps": [
        {"node_id": "draft", "label": "Draft the note", "status": "succeeded"},
        {"node_id": "review", "label": "Human review", "status": "waiting"},
        {"node_id": "publish", "label": "Record the verdict", "status": "not_reached"},
    ]},
    "get_workflow_definition": {
        "workflow_id": "workflow:draft-review", "name": "Draft · review · rework",
        "description": "An Agent drafts, a person reviews; a rejection carries its"
                       " reason back for one more pass.",
        "latest_version": 3,
        "nodes": [
            {"node_id": "draft", "kind": "action", "handler": "agent.claude"},
            {"node_id": "review", "kind": "human"},
            {"node_id": "route", "kind": "decision"},
            {"node_id": "rework", "kind": "action", "handler": "agent.claude"},
        ],
    },
}

# One shot per card. `setup` runs after load, before the shot. The height is
# a starting frame only — each shot is refitted to its own content below.
SHOTS = [
    ("dashboard", mcp_app.ORBIT_DASHBOARD_HTML, 700,
     lambda page: (page.click("#tabHistory"), page.wait_for_selector(".historyRow"))),
    ("workflows", mcp_app.ORBIT_WORKFLOWS_HTML, 700,
     lambda page: page.wait_for_selector(".rowItem")),
    ("workflow-generation", mcp_app.ORBIT_AUTHORING_HTML, 700, None),
    ("goal-execution", mcp_app.ORBIT_RUN_HTML, 700, None),
    ("goals", mcp_app.ORBIT_GOALS_HTML, 700,
     lambda page: page.wait_for_selector(".goalRow")),
]

# What the card would like to be, given what it holds. A card shrinks into the
# frame it is given, so shooting every card in one tall frame leaves the short
# ones sitting in a field of empty card. Ask each one what it needs, reframe,
# and shoot that — capped where the card itself caps, so a long list is still
# shown as the scrolling list it is.
FIT = """() => {
  const card = document.getElementById('card');
  const chrome = document.body.getBoundingClientRect().height
    - card.getBoundingClientRect().height;
  // Its children, not `scrollHeight`: two of these cards are a fixed height,
  // and a fixed-height box that is not overflowing reports its own height as
  // its scroll height — so asking that way says 600 for a card holding five
  // rows, and refits nothing.
  const content = [...card.children].reduce(
    (total, child) => total + child.getBoundingClientRect().height, 0);
  const cap = parseFloat(getComputedStyle(document.documentElement)
    .getPropertyValue('--card-height')) || 600;
  return Math.ceil(chrome + Math.min(Math.max(content, 80), cap));
}"""


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    initial = (
        f"const answers = {json.dumps(ANSWERS)};\n"
        "window.openai = { callTool: async (name) =>"
        " ({ structuredContent: answers[name] || {} }) };\n"
        # The cards print "today" and "just now" against the clock. Pin it so a
        # regenerated image differs only where the card did.
        f"const FIXED = new Date('{DAY}T09:20:00Z').getTime();\n"
        "const RealDate = Date;\n"
        "window.Date = class extends RealDate {\n"
        "  constructor(...args) { super(...(args.length ? args : [FIXED])); }\n"
        "  static now() { return FIXED; }\n"
        "};\n"
        "window.Date.parse = RealDate.parse; window.Date.UTC = RealDate.UTC;\n"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, html, height, setup in SHOTS:
            context = browser.new_context(
                locale="en-US", color_scheme="light",
                viewport={"width": 720, "height": height}, device_scale_factor=2,
            )
            context.add_init_script(initial)
            page = context.new_page()
            page.route("https://orbit.docs/card.html", lambda route, _=None, body=html:
                       route.fulfill(status=200, content_type="text/html; charset=utf-8",
                                     body=body))
            page.goto("https://orbit.docs/card.html")
            page.wait_for_selector("#card")
            if setup:
                setup(page)
            page.wait_for_timeout(500)
            page.set_viewport_size({"width": 720, "height": page.evaluate(FIT)})
            page.wait_for_timeout(400)
            target = OUT / f"{name}.png"
            page.screenshot(path=str(target))
            print(f"{target.relative_to(ROOT)}  {target.stat().st_size // 1024} KiB")
            context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
