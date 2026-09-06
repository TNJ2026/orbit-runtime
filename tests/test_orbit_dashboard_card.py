"""The dashboard MCP App card, driven by a real browser.

The card talks to its host through `window.openai.callTool`, so a stub host
that answers the six tools it is allowed to call is enough to drive the whole
surface: which tab it opens on, what History shows, and what a row opens.

playwright is a test-only dependency. The suite skips when it is missing
rather than failing, so a plain checkout still runs green.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised by the skip
    sync_playwright = None

from orbit.web.mcp_app import ORBIT_DASHBOARD_HTML


WORKFLOWS = [
    {
        "workflow_id": "workflow:draft", "name": "起草 · 人工审核",
        "description": "Draft, review, rework", "node_count": 4, "latest_version": 3,
    },
    {
        "workflow_id": "workflow:linear", "name": "Linear",
        "description": "", "node_count": 2, "latest_version": 1,
    },
]

AGENTS = [
    {"name": "agent.claude", "version": "2.1.260", "attempt_count": 12, "failed_count": 1},
    {"name": "agent.codex", "version": "0.9.0", "attempt_count": 3, "failed_count": 0},
]

APPROVAL_INTERRUPT = {
    "value": {
        "config": {"task_kind": "approval"},
        "output_ports": [{"name": "result"}],
    },
}


def at(days_ago: float, hour: int = 9, minute: int = 30) -> str:
    """A timestamp the browser reads back as today, yesterday, or before.

    Dated from the clock rather than written down, because the day headings
    the card prints are relative to the day the test runs on.
    """

    stamp = datetime.now(timezone.utc).astimezone() - timedelta(days=days_ago)
    return stamp.replace(
        hour=hour, minute=minute, second=0, microsecond=0,
    ).isoformat()


ARTIFACT = "langgraph_artifact:2be8a856459b5af310c70e9f7fe8119da6a1aaabab190f74354151edcbcda694"


def run(run_id, *, status, goal, workflow_id="workflow:draft",
        created_at, updated_at, interrupts=(), result=None, error=None):
    return {
        "run_id": run_id, "status": status, "goal": goal,
        "workflow_id": workflow_id, "created_at": created_at,
        "updated_at": updated_at, "artifact_count": 0,
        "interrupts": list(interrupts), "result": result, "error": error,
    }


@unittest.skipUnless(sync_playwright, "playwright is not installed")
class DashboardCardTests(unittest.TestCase):
    """One browser for the class; a page, and its stub host, per test."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def open(self, *, runs=(), jobs=(), locale="zh-CN", steps=(), height=None,
             artifact=None, content=""):
        """The card, with a host that answers exactly the tools it may call.

        `now` is fixed by the fixtures rather than the clock: the day headings
        say "today" and "yesterday", so the runs have to be dated relative to
        the machine running the test.
        """

        context = self.browser.new_context(
            locale=locale,
            **({"viewport": {"width": 460, "height": height}} if height else {}),
        )
        self.addCleanup(context.close)
        answers = {
            "list_runs": {"runs": list(runs)},
            "list_workflows": {"workflows": WORKFLOWS},
            "list_authoring_jobs": {"jobs": list(jobs)},
            "list_agents": {"agents": AGENTS},
            "get_run_steps": {"steps": list(steps)},
            "read_artifact": {"artifact": dict(artifact or {})},
            "read_artifact_content": {"encoding": "utf-8", "content": content},
            "get_workflow_definition": {
                "workflow_id": "workflow:draft", "name": "起草 · 人工审核",
                "latest_version": 3, "description": "Draft, review, rework",
                "nodes": [
                    {"node_id": "draft", "kind": "action", "handler": "agent.claude"},
                    {"node_id": "review", "kind": "human"},
                ],
            },
        }
        context.add_init_script(
            "window.__calls = [];\n"
            f"const answers = {json.dumps(answers)};\n"
            "window.openai = { callTool: async (name, args) => {\n"
            "  window.__calls.push(name);\n"
            "  return { structuredContent: answers[name] };\n"
            "} };"
        )
        page = context.new_page()
        page.route(
            "https://orbit.test/card.html",
            lambda route: route.fulfill(
                status=200, content_type="text/html; charset=utf-8",
                body=ORBIT_DASHBOARD_HTML,
            ),
        )
        page.goto("https://orbit.test/card.html")
        page.wait_for_selector("#tabs .tab[aria-selected='true']")
        return page

    def tabs(self, page):
        return page.eval_on_selector_all(
            "#tabs .tab", "nodes => nodes.map(node => node.textContent)"
        )

    def selected(self, page):
        return page.eval_on_selector(
            "#tabs .tab[aria-selected='true']", "node => node.dataset.tab"
        )

    # -- the navigation itself --------------------------------------------

    def test_three_tabs_and_a_create_button_at_the_end(self) -> None:
        page = self.open()
        self.assertEqual(["工作流", "历史记录", "Agents"], self.tabs(page))
        self.assertEqual("创建工作流", page.text_content("#createWorkflow"))
        # The create button is the last thing in the row, past the tabs.
        self.assertEqual(
            "createWorkflow",
            page.eval_on_selector("#tabs", "node => node.lastElementChild.id"),
        )
        self.assertNotIn(
            "createWorkflow",
            page.eval_on_selector_all(
                "#tabs .tab", "nodes => nodes.map(node => node.id)"
            ),
        )

    def test_it_opens_on_workflows_when_nothing_has_run(self) -> None:
        page = self.open()
        self.assertEqual("workflows", self.selected(page))
        self.assertIn("起草 · 人工审核", page.text_content("#card"))

    def test_adding_an_agent_is_offered_under_the_list(self) -> None:
        """After the Agents already registered, not above them."""

        page = self.open()
        page.click("#tabAgents")
        page.wait_for_selector(".agentRow")
        self.assertEqual("添加 Agent", page.text_content("#card .actions .action"))
        self.assertEqual(
            ["agentRow", "agentRow", "actions"],
            page.eval_on_selector_all(
                "#card > *", "nodes => nodes.map(node => node.className)"
            ),
        )

    def test_each_tab_switches_the_card_in_place(self) -> None:
        page = self.open()
        page.click("#tabAgents")
        page.wait_for_selector(".agentRow")
        self.assertEqual("agents", self.selected(page))
        self.assertIn("claude", page.text_content("#card"))

        page.click("#tabHistory")
        page.wait_for_selector(".empty")
        self.assertEqual("history", self.selected(page))
        self.assertIn("当前项目还没有目标执行记录。", page.text_content("#card"))

        page.click("#tabWorkflows")
        page.wait_for_selector(".rowItem .row")
        self.assertEqual("workflows", self.selected(page))

    def test_every_tab_is_the_same_height(self) -> None:
        """Including a History with nothing in it yet.

        The card used to be as tall as its content between a minimum and a
        maximum, so this one view was 220px shorter than the others and
        switching to it moved the tabs the reader had just pressed.
        """

        page = self.open()
        heights = {}
        for tab in ("#tabWorkflows", "#tabHistory", "#tabAgents"):
            page.click(tab)
            page.wait_for_timeout(200)
            if tab == "#tabHistory":
                # The view this is about: nothing in it, and the same height.
                self.assertEqual(
                    "当前项目还没有目标执行记录。", page.text_content(".empty")
                )
            heights[tab] = page.eval_on_selector(
                "#card", "node => node.getBoundingClientRect().height"
            )
        self.assertEqual(1, len(set(heights.values())), heights)

    def test_hovering_a_button_tints_it_in_its_own_colour(self) -> None:
        """A rounded wash, not an underline — and red where the button is red.

        The tint is `color-mix(currentColor 10%)`, so 拒绝 cannot end up
        washed in the accent, and neither can drift if either colour changes.
        """

        runs = [run("run:live", status="interrupted", goal="起草说明文档",
                    created_at=at(0), updated_at=at(0),
                    interrupts=[APPROVAL_INTERRUPT])]
        page = self.open(runs=runs, steps=[
            {"node_id": "review", "label": "审核", "status": "waiting"},
        ])
        page.wait_for_selector(".actions .action")
        seen = {}
        for index, label in enumerate(page.eval_on_selector_all(
            ".actions .action", "nodes => nodes.map(node => node.textContent)"
        )):
            button = page.locator(".actions .action").nth(index)
            self.assertEqual(
                "rgba(0, 0, 0, 0)",
                button.evaluate("node => getComputedStyle(node).backgroundColor"),
            )
            button.hover()
            page.wait_for_timeout(120)
            seen[label] = button.evaluate(
                """node => {
                  const s = getComputedStyle(node);
                  return [s.backgroundColor, s.borderRadius, s.textDecorationLine];
                }"""
            )
        for label, (background, radius, decoration) in seen.items():
            with self.subTest(label=label):
                self.assertNotIn(background, ("rgba(0, 0, 0, 0)", "transparent"))
                self.assertEqual("8px", radius)
                self.assertEqual("none", decoration)
        # 拒绝 washes red where 批准 washes accent — which is the whole
        # point of tinting with `currentColor` rather than a fixed value.
        self.assertNotEqual(seen["拒绝"][0], seen["批准"][0])

    def test_the_host_never_has_to_scroll_the_whole_card(self) -> None:
        """Two scrollbars, one inside the other, is the thing to avoid.

        This card's document carries a tab bar and a subtitle the other cards
        do not, so it was 60px taller than they were and overflowed frames
        they fitted. It fits any frame now: the card shrinks into what the
        chrome leaves, and only the list scrolls.
        """

        runs = [run(f"run:{i}", status="completed", goal=f"目标 {i}",
                    created_at=at(0), updated_at=at(0)) for i in range(30)]
        # 720 is the frame the host actually gives, measured in Codex.
        for height in (420, 600, 720, 900):
            page = self.open(runs=runs, height=height)
            page.click("#tabHistory")
            page.wait_for_selector(".historyRow")
            outer, card = page.evaluate(
                """() => [
                  document.documentElement.scrollHeight
                    > document.documentElement.clientHeight,
                  Math.round(
                    document.getElementById('card').getBoundingClientRect().height),
                ]"""
            )
            with self.subTest(height=height):
                self.assertFalse(outer, f"the document overflowed a {height}px frame")
                # Capped where there is room, shrunk where there is not.
                self.assertLessEqual(card, 600)
                self.assertGreater(card, 0)
                self.assertTrue(
                    page.eval_on_selector(
                        "#card", "node => node.scrollHeight > node.clientHeight"
                    ),
                    "the list itself should be what scrolls",
                )

    def test_a_frame_too_short_to_fit_gets_its_scrollbar_back(self) -> None:
        """Below 360px the card would be a sliver, so stop fitting.

        `.card` has no floor: it shrinks with the frame, and at 150px it
        measured 12px — an outer scrollbar suppressed and nothing readable
        left behind it. Handing the document back to the host is worse than
        fitting and better than that.
        """

        runs = [run(f"run:{i}", status="completed", goal=f"目标 {i}",
                    created_at=at(0), updated_at=at(0)) for i in range(30)]
        for height, fits in ((400, True), (360, True), (340, False), (200, False)):
            page = self.open(runs=runs, height=height)
            page.click("#tabHistory")
            page.wait_for_selector(".historyRow")
            measured = page.evaluate(
                """() => ({
                  outer: document.documentElement.scrollHeight
                         > document.documentElement.clientHeight,
                  card: Math.round(
                    document.getElementById('card').getBoundingClientRect().height),
                })"""
            )
            with self.subTest(height=height):
                self.assertEqual(not fits, measured["outer"])
                if fits:
                    # Shrunk into the frame, and still worth looking at.
                    self.assertLess(measured["card"], height)
                    self.assertGreaterEqual(measured["card"], 200)
                else:
                    # Full height, and the host scrolls to reach it.
                    self.assertEqual(600, measured["card"])

    def test_a_row_never_runs_past_the_card_s_content_edge(self) -> None:
        """Whatever the scrollbar takes, the rows end where the content does.

        The reserved width itself cannot be checked here: this browser is
        headless and headless Chromium draws no scrollbar, so it reports a
        gutter of 0 whether or not one would exist on screen. What it can
        check is the invariant that matters either way — a row ends at the
        card's content edge, so it is laid out beside the bar rather than
        under it. That the width is reserved at all, and only while there is
        a bar, is measured in a headed browser and pinned as CSS in
        `test_every_card_keeps_its_scrollbar`.
        """

        GEOMETRY = """(selector) => {
          const card = document.getElementById('card');
          const border = parseFloat(getComputedStyle(card).borderRightWidth);
          const gutter = card.offsetWidth - card.clientWidth - 2 * border;
          const row = document.querySelector(selector);
          return {
            scrolls: card.scrollHeight > card.clientHeight,
            under: Math.round(row.getBoundingClientRect().right
              - (card.getBoundingClientRect().right - border - gutter)),
          };
        }"""

        runs = [run(f"run:{i}", status="completed", goal=f"目标 {i}",
                    created_at=at(0), updated_at=at(0)) for i in range(30)]
        page = self.open(runs=runs, height=720)
        page.click("#tabHistory")
        page.wait_for_selector(".historyRow")
        overflowing = page.evaluate(GEOMETRY, ".historyRow")
        self.assertTrue(overflowing["scrolls"], "thirty runs should overflow the card")
        self.assertEqual(0, overflowing["under"])

        page = self.open(height=720)
        page.click("#tabHistory")
        page.wait_for_selector(".empty")
        self.assertFalse(page.evaluate(GEOMETRY, ".empty")["scrolls"])

    def test_a_workflow_row_highlights_to_its_own_edge(self) -> None:
        """Including the part of it under 新目标.

        The list used to be a two-column grid, so the highlight covered the
        text column and stopped at the button's — 72px of the row stayed
        white while the pointer was on it.
        """

        page = self.open()
        page.wait_for_selector(".rowItem .row")
        page.hover(".rowItem:nth-child(2) .row")
        page.wait_for_timeout(150)
        measured = page.evaluate(
            """() => {
              const item = document.querySelectorAll('.rowItem')[1];
              const row = item.querySelector('.row');
              const button = item.querySelector('.rowAction');
              return {
                gap: Math.round(item.getBoundingClientRect().right
                     - row.getBoundingClientRect().right),
                painted: getComputedStyle(row).backgroundColor,
                reaches_button: Math.round(row.getBoundingClientRect().right)
                  >= Math.round(button.getBoundingClientRect().right),
              };
            }"""
        )
        self.assertEqual(0, measured["gap"])
        self.assertTrue(measured["reaches_button"])
        self.assertNotIn(measured["painted"], ("rgba(0, 0, 0, 0)", "transparent"))

    # -- history ----------------------------------------------------------

    def test_history_groups_goals_by_day_the_way_the_full_ui_does(self) -> None:
        runs = [
            run("run:a", status="completed", goal="翻译这段内容",
                created_at=at(0, 9), updated_at=at(0, 10)),
            run("run:b", status="failed", goal="检查 README",
                workflow_id="workflow:linear",
                created_at=at(1, 15), updated_at=at(1, 16)),
        ]
        page = self.open(runs=runs)
        page.click("#tabHistory")
        page.wait_for_selector(".historyRow")

        self.assertEqual(
            ["今天", "昨天"],
            page.eval_on_selector_all(
                ".historyDate", "nodes => nodes.map(node => node.textContent)"
            ),
        )
        titles = page.eval_on_selector_all(
            ".historyRow .name", "nodes => nodes.map(node => node.textContent)"
        )
        self.assertEqual(["翻译这段内容", "检查 README"], titles)
        # Workflow name, time of day, and how long it took — the same three
        # facts, in the same order, as the full UI's history row.
        meta = page.text_content(".historyRow .meta")
        self.assertIn("起草 · 人工审核", meta)
        self.assertIn("1 小时", meta)
        self.assertEqual(
            ["已完成", "失败"],
            page.eval_on_selector_all(
                ".historyRow .pill", "nodes => nodes.map(node => node.textContent)"
            ),
        )

    def test_a_finished_run_says_how_it_went(self) -> None:
        """Every result shape this Runtime produces, read the Harness's way.

        The outcome in words leads, because a reader asking "did it work" was
        being answered with whatever the terminal step emitted — for a run
        that wrote a file, a 64-character hash.
        """

        cases = [
            ("a small markdown file is the answer, so it is shown",
             {"artifact_id": ARTIFACT}, None,
             {"content_type": "text/markdown", "size_bytes": 120},
             ["Finished", "# The answer"], ["2be8a856"]),
            ("a large file is a door, so it is named",
             {"artifact_id": ARTIFACT}, None,
             {"content_type": "application/pdf", "size_bytes": 900000},
             ["Finished", "2be8a856459b…"], ["# The answer"]),
            ("a single string field is the string",
             {"text": "It found three problems."}, None, None,
             ["Finished", "It found three problems."], ["{"]),
            ("anything else is its JSON",
             {"decision": "approve", "value": None}, None, None,
             ["Finished", '"decision": "approve"'], []),
            ("a failure names why",
             None, "RuntimeError: workspace access could not be provisioned", None,
             ["Why it failed", "Failed", "workspace access"], ["Result"]),
        ]
        for label, result, error, artifact, expected, absent in cases:
            with self.subTest(case=label):
                runs = [run("run:a", status="failed" if error else "completed",
                            goal="翻译这段内容", created_at=at(0), updated_at=at(0),
                            result=result, error=error)]
                page = self.open(runs=runs, locale="en-US", artifact=artifact,
                                 content="# The answer",
                                 steps=[{"node_id": "a", "label": "Step",
                                         "status": "succeeded"}])
                page.click("#tabHistory")
                page.click(".historyRow")
                page.wait_for_selector(".resultBlock")
                text = page.text_content(".resultBlock")
                for wanted in expected:
                    self.assertIn(wanted, text)
                for unwanted in absent:
                    self.assertNotIn(unwanted, text)

    def test_a_running_run_is_promised_no_outcome(self) -> None:
        """An empty block promising one is worse than no block."""

        runs = [run("run:live", status="interrupted", goal="起草说明文档",
                    created_at=at(0), updated_at=at(0),
                    interrupts=[APPROVAL_INTERRUPT])]
        page = self.open(runs=runs, steps=[
            {"node_id": "review", "label": "审核", "status": "waiting"},
        ])
        page.wait_for_selector(".steps")
        self.assertEqual(0, page.eval_on_selector_all("#card .resultBlock", "n => n.length"))

    def test_a_finished_run_is_offered_no_actions_at_all(self) -> None:
        """Not an empty action row either — the row is not drawn."""

        runs = [run("run:a", status="completed", goal="翻译这段内容",
                    created_at=at(0), updated_at=at(0))]
        page = self.open(runs=runs, steps=[
            {"node_id": "draft", "label": "起草", "status": "succeeded"},
        ])
        page.click("#tabHistory")
        page.click(".historyRow")
        page.wait_for_selector(".steps")
        self.assertEqual(0, page.eval_on_selector_all("#card .actions", "n => n.length"))
        self.assertEqual(0, page.eval_on_selector_all("#card .action", "n => n.length"))

    def test_a_history_row_opens_that_run_and_comes_back(self) -> None:
        runs = [run("run:a", status="completed", goal="翻译这段内容",
                    created_at=at(0), updated_at=at(0))]
        steps = [
            {"node_id": "draft", "label": "起草", "status": "succeeded"},
            {"node_id": "review", "label": "审核", "status": "succeeded"},
        ]
        page = self.open(runs=runs, steps=steps)
        page.click("#tabHistory")
        page.click(".historyRow")
        page.wait_for_selector(".steps")
        self.assertIn("翻译这段内容", page.text_content(".goal"))
        self.assertIn("起草", page.text_content(".steps"))
        # History stays the selected tab while one of its runs is open.
        self.assertEqual("history", self.selected(page))

        # The way out is the same chevron the workflow card uses, big
        # enough to be a control rather than punctuation.
        self.assertEqual("‹", page.text_content(".back"))
        self.assertEqual(
            "24px",
            page.eval_on_selector(".back", "node => getComputedStyle(node).fontSize"),
        )
        page.click(".back")
        page.wait_for_selector(".historyRow")
        self.assertEqual("history", self.selected(page))

    # -- what the card was for --------------------------------------------

    def test_a_waiting_run_is_what_the_card_opens_on(self) -> None:
        """The reason to open Orbit is the goal that needs an answer."""

        runs = [run("run:live", status="interrupted", goal="起草说明文档",
                    created_at=at(0), updated_at=at(0),
                    interrupts=[APPROVAL_INTERRUPT])]
        steps = [
            {"node_id": "draft", "label": "起草", "status": "succeeded"},
            {"node_id": "review", "label": "审核", "status": "waiting"},
        ]
        page = self.open(runs=runs, steps=steps)
        page.wait_for_selector(".notice")
        self.assertEqual("history", self.selected(page))
        self.assertIn("起草说明文档", page.text_content(".goal"))
        self.assertEqual(
            ["批准", "拒绝"],
            page.eval_on_selector_all(
                ".actions .action", "nodes => nodes.map(node => node.textContent)"
            ),
        )

    def test_generation_in_flight_is_named_above_the_workflow_list(self) -> None:
        page = self.open(jobs=[{
            "job_id": "job:1", "status": "running", "prompt": "写一个审批工作流",
        }])
        page.wait_for_selector(".authoringStrip")
        self.assertEqual("workflows", self.selected(page))
        self.assertIn("正在生成工作流", page.text_content(".authoringStrip"))
        self.assertIn("写一个审批工作流", page.text_content(".authoringStrip"))

    def test_it_reads_english_from_the_host_locale(self) -> None:
        page = self.open(locale="en-US")
        self.assertEqual(["Workflows", "History", "Agents"], self.tabs(page))
        self.assertEqual("Create workflow", page.text_content("#createWorkflow"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
