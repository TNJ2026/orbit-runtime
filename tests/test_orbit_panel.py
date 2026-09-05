"""Contract tests for the compact Orbit current-task MCP App."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

from orbit.web import mcp_app
from orbit.web.mcp_app import (
    ORBIT_AUTHORING_HTML,
    ORBIT_AUTHORING_URI,
    ORBIT_DASHBOARD_HTML,
    ORBIT_DASHBOARD_URI,
    ORBIT_GOALS_HTML,
    ORBIT_GOALS_URI,
    ORBIT_MCP_APP_RESOURCES,
    ORBIT_RUN_HTML,
    ORBIT_RUN_URI,
    ORBIT_WORKFLOWS_HTML,
    ORBIT_WORKFLOWS_URI,
)

# The template before its placeholders are filled in, so a test can ask
# whether the shared sheet is composed in rather than copied out.
ORBIT_DASHBOARD_HTML_SOURCE = (
    Path(mcp_app.__file__).read_text(encoding="utf-8")
)


class CurrentTaskCardTests(unittest.TestCase):
    def test_it_keeps_current_task_as_the_default_resource(self) -> None:
        self.assertEqual("ui://orbit/current-task-v38.html", ORBIT_DASHBOARD_URI)
        self.assertEqual(ORBIT_DASHBOARD_URI, ORBIT_MCP_APP_RESOURCES[0]["uri"])

    def test_it_publishes_dedicated_cards(self) -> None:
        self.assertEqual(
            {
                ORBIT_DASHBOARD_URI, ORBIT_WORKFLOWS_URI,
                ORBIT_AUTHORING_URI, ORBIT_RUN_URI,
                ORBIT_GOALS_URI,
            },
            {item["uri"] for item in ORBIT_MCP_APP_RESOURCES},
        )

    def test_every_card_uses_the_full_ui_logo_image(self) -> None:
        for html in (
            ORBIT_DASHBOARD_HTML, ORBIT_WORKFLOWS_HTML,
            ORBIT_AUTHORING_HTML, ORBIT_RUN_HTML, ORBIT_GOALS_HTML,
        ):
            with self.subTest():
                self.assertIn('<img class="mark"', html)
                self.assertIn("data:image/svg+xml", html)
                self.assertNotIn('<span class="mark">O</span>', html)

    def test_it_reads_current_task_and_embedded_workflow_views(self) -> None:
        calls = set(re.findall(r"callTool\('([a-z_]+)'", ORBIT_DASHBOARD_HTML))
        self.assertEqual(
            {
                "list_runs", "list_authoring_jobs", "get_run_steps",
                "list_workflows", "get_workflow_definition", "list_agents",
            },
            calls,
        )
        for absent in ("read_run_output", "read_authoring_output"):
            self.assertNotIn(absent, ORBIT_DASHBOARD_HTML)

    def test_workflow_selection_switches_views_inside_the_card(self) -> None:
        for marker in (
            'data-tab="workflows"', "showWorkflows", "showWorkflowDetail",
            "callTool('list_workflows'", "callTool('get_workflow_definition'",
            "data-back-view", "renderWorkflowList", "renderWorkflowDetail",
        ):
            self.assertIn(marker, ORBIT_DASHBOARD_HTML)

    def test_agents_switches_to_a_list_inside_the_dashboard_card(self) -> None:
        for marker in (
            'data-tab="agents"', "showAgents", "renderAgents",
            "callTool('list_agents'", 'class="agentRow"',
            "currentTab === 'agents'", "data-back-view",
        ):
            self.assertIn(marker, ORBIT_DASHBOARD_HTML)

    def test_add_agent_uses_the_host_aware_prompt_editor(self) -> None:
        for marker in (
            "addAgent: 'Add Agent'", "addAgent: '添加 Agent'",
            "promptAddAgent: '给Orbit添加Agent cli：'",
            "card.innerHTML = `${rows || `<div class=\"empty\">${esc(t().noAgents)}</div>`}${add}`",
            'data-prompt="${esc(t().promptAddAgent)}"',
            "button.addEventListener('click', () => dispatchPrompt(button))",
            "dispatchPromptValue(button.dataset.prompt",
            "hostProvidesPromptEditor()",
            "dialog.id='promptEditorDialog'",
        ):
            self.assertIn(marker, ORBIT_DASHBOARD_HTML)
        for absent in ("window.prompt", "data-add-agent-form", "data-add-agent-input"):
            self.assertNotIn(absent, ORBIT_DASHBOARD_HTML)

    def test_embedded_workflow_list_offers_new_goal_directly(self) -> None:
        for marker in (
            'class="workflowChoice"', "workflowGoal", "t().newGoal",
            "使用工作流「${name}」（${workflow.workflow_id}）执行：",
        ):
            self.assertIn(marker, ORBIT_DASHBOARD_HTML)

    def test_the_dashboard_is_painted_by_the_shared_card_theme(self) -> None:
        """One theme for every card, not a second copy of it here.

        This card carried its own palette, its own `body`, its own `.action`
        and its own tab bar — a full restatement of `_CARD_STYLE` that had
        already drifted from it (`.action.danger` was filled here and text
        elsewhere). It is built on the shared sheet now and adds only what is
        its own, so a colour can be changed in one place and a reader
        comparing two cards is comparing one stylesheet.
        """

        self.assertIn("__CARD_STYLE__", ORBIT_DASHBOARD_HTML_SOURCE)
        self.assertIn('"__CARD_STYLE__", _CARD_STYLE,', ORBIT_DASHBOARD_HTML_SOURCE)
        # Declared once, by the shared sheet.
        self.assertEqual(1, ORBIT_DASHBOARD_HTML.count("--accent:"))
        self.assertEqual(1, ORBIT_DASHBOARD_HTML.count(".action.primary"))
        self.assertEqual(1, ORBIT_DASHBOARD_HTML.count("body{margin:0"))
        for restated in (
            "--bg: light-dark", ".action { min-height", ".action.danger {",
            "@keyframes pulse {", "--faint",
        ):
            self.assertNotIn(restated, ORBIT_DASHBOARD_HTML)
        # And the shared vocabulary is used rather than renamed: rows are
        # `.row`, a title is `.name`, a secondary line is `.meta`.
        for shared in ('class="row" type="button" data-workflow-id=',
                       'class="name"', 'class="meta"', 'class="card"',
                       'class="tabs" role="tablist"', 'id="refresh" class="icon"'):
            self.assertIn(shared, ORBIT_DASHBOARD_HTML)

    def test_it_contains_no_administration_surface(self) -> None:
        """Tabs are navigation, not administration.

        This used to forbid the three tab ids outright, back when any tab at
        all was the shape an administration surface would have arrived in.
        The card now navigates by tab, so what is worth forbidding is the
        thing itself: deleting a Workflow, editing one in place, or reading a
        step's output — each of which belongs to the full UI.
        """

        for absent in (
            "workflowDelete", "deleteWorkflow",
            "workflowGenerator", "authoringConsole", "stepOutput",
        ):
            self.assertNotIn(absent, ORBIT_DASHBOARD_HTML)

    def test_it_shows_steps_and_attention_without_a_progress_bar(self) -> None:
        for marker in (
            "waitingNotice", 'class="steps"', "step.status === 'waiting'",
        ):
            self.assertIn(marker, ORBIT_DASHBOARD_HTML)
        for absent in (
            'class="progress"', "progressText", "Math.round", "DONE_STEPS",
        ):
            self.assertNotIn(absent, ORBIT_DASHBOARD_HTML)

    def test_history_is_a_tab_in_the_card_and_not_a_link_out(self) -> None:
        """The run list the full UI shows, in the card, for this project.

        History used to be a button that asked the host to open
        `#/history` in a browser. It is a tab now, built on the same three
        facts per row as the full UI's list — Workflow name, time of day,
        elapsed — and grouped under the same day headings.
        """

        for marker in (
            'data-tab="history"', "showHistory", "renderHistory", "historyRow",
            "callTool('list_runs'", "function dayKey(value)", "function dayLabel(value)",
            "function runDuration(run)", 'class="historyDay"', "data-run-id",
            "showRun(button.dataset.runId)",
        ):
            self.assertIn(marker, ORBIT_DASHBOARD_HTML)
        for absent in (
            "promptHistory", "127.0.0.1:8848/ui/#/history",
            "idleActions", "renderIdle", "renderRecentRun",
        ):
            self.assertNotIn(absent, ORBIT_DASHBOARD_HTML)

    def test_a_history_row_opens_the_run_it_names(self) -> None:
        run = ORBIT_DASHBOARD_HTML.split("async function showRun(runId,known) {", 1)[1]
        run = run.split("function refresh()", 1)[0]
        for marker in (
            "callTool('get_run_steps'", "renderRun(run,steps)",
            # A run the list no longer carries goes back to the list.
            "if (!run) return showHistory(runs)",
        ):
            self.assertIn(marker, run)

    def test_goal_run_card_paints_an_initial_failure_as_running(self) -> None:
        """A synchronous failed start must not make the card open as failed."""

        for marker in (
            "firstPaint&&run?.run_id&&run.status==='failed'",
            "draw({...run,status:'running'},[])",
            "timer=setTimeout(refresh,2000)",
        ):
            self.assertIn(marker, ORBIT_RUN_HTML)

    def test_goal_run_card_keeps_a_rejected_start_as_its_own_error(self) -> None:
        for marker in (
            "function failureMessage(value)",
            "if(failure){clearTimeout(timer)",
            "value?.run_id||failureMessage(value)",
        ):
            self.assertIn(marker, ORBIT_RUN_HTML)

    def test_stale_tasks_do_not_decide_which_tab_opens(self) -> None:
        """What the card opens on, and what it does not reopen.

        A run still going — or waiting on a person — is the reason the card
        was opened, so History leads and that run is already open in it. A
        run that merely finished recently leaves History selected without
        opening anything. Older than that decides nothing, and the first
        screen is the one that starts something.
        """

        start = ORBIT_DASHBOARD_HTML.split("async function start() {", 1)[1]
        start = start.split("bridge = mcpBridge()", 1)[0]
        for marker in (
            "const active = runs.find(run => !TERMINAL.has(run.status))",
            "if (active) return showRun(active.run_id,runs)",
            "if (runs.some(run => isRecent(run))) return showHistory(runs)",
            "return showWorkflows()",
        ):
            self.assertIn(marker, start)
        self.assertIn("RECENT_TASK_MS = 5 * 60 * 60 * 1000", ORBIT_DASHBOARD_HTML)
        self.assertNotIn("promptStart", ORBIT_DASHBOARD_HTML)

    def test_create_workflow_sits_beside_the_tabs_not_among_them(self) -> None:
        tabs = ORBIT_DASHBOARD_HTML.split('<nav id="tabs"', 1)[1].split("</nav>", 1)[0]
        self.assertLess(tabs.index('data-tab="workflows"'), tabs.index('data-tab="history"'))
        self.assertLess(tabs.index('data-tab="history"'), tabs.index('data-tab="agents"'))
        # Last in the row, and not a tab: it creates rather than navigates.
        self.assertLess(tabs.index('data-tab="agents"'), tabs.index('id="createWorkflow"'))
        self.assertNotIn('id="createWorkflow" type="button" role="tab"', tabs)
        self.assertIn("#createWorkflow { margin-left: auto; }", ORBIT_DASHBOARD_HTML)
        self.assertIn(
            "createButton.dataset.prompt = t().promptCreateWorkflow;",
            ORBIT_DASHBOARD_HTML,
        )

    def test_generation_in_flight_is_a_strip_above_the_workflow_list(self) -> None:
        strip = ORBIT_DASHBOARD_HTML.split("function authoringStrip(job) {", 1)[1]
        strip = strip.split("function renderWorkflowList", 1)[0]
        for marker in ("t().authoring", "t().authoringDone", "t().authoringFailed"):
            self.assertIn(marker, strip)
        self.assertIn(
            "card.innerHTML = `${authoringStrip(job)}${rows ||", ORBIT_DASHBOARD_HTML,
        )
        # Progress belongs to the generation card; this one only says it runs.
        self.assertNotIn("callTool('get_authoring_job'", ORBIT_DASHBOARD_HTML)

    def test_suggested_actions_return_to_the_conversation(self) -> None:
        self.assertIn("'ui/message'", ORBIT_DASHBOARD_HTML)
        self.assertIn("sendFollowUpMessage", ORBIT_DASHBOARD_HTML)
        for prompt in (
            "promptHandle", "promptCancel", "promptExplain",
            "promptCreateWorkflow", "promptOpen",
        ):
            self.assertIn(prompt, ORBIT_DASHBOARD_HTML)

    def test_approval_buttons_send_explicit_decisions_to_the_agent(self) -> None:
        for marker in (
            "promptApproval: (run,decision)",
            "t().promptApproval(run,'approve')",
            "t().promptApproval(run,'reject')",
            "current interrupt_id, revision, allowed_commands, and output_ports",
            "decision=\"${decision}\" and value=null",
            "当前的 interrupt_id、revision、allowed_commands 和 output_ports",
        ):
            self.assertIn(marker, ORBIT_DASHBOARD_HTML)
        self.assertNotIn("callTool('resume_run'", ORBIT_DASHBOARD_HTML)

    def test_buttons_are_labels_and_the_card_is_a_frame(self) -> None:
        """No filled rectangles, and no fill behind them either.

        Every offer used to arrive as a filled or outlined button, so a card
        of four suggestions read as a form to fill in rather than a list of
        things a person could do. And the card painted `--soft` behind all of
        it, which every section then had to paint `--bg` back over to look
        like a divider. The accent alone now says "this is something you can
        do", the card is a frame, and the sections are lines.

        Checked on all five cards because they share one sheet, which is the
        only reason this can be one rule rather than five.
        """

        for html in (
            ORBIT_DASHBOARD_HTML, ORBIT_WORKFLOWS_HTML,
            ORBIT_AUTHORING_HTML, ORBIT_RUN_HTML, ORBIT_GOALS_HTML,
        ):
            with self.subTest():
                self.assertIn(
                    ".action{padding:7px 0;border:0;color:var(--accent);"
                    "background:transparent;cursor:pointer;font-weight:620}",
                    html,
                )
                # Main or not, an offer is the same colour.
                self.assertIn(".action.primary{color:var(--accent)}", html)
                # Destructive stays a warning rather than joining them.
                self.assertIn(".action.danger{color:var(--bad)}", html)
                # The frame has a border and a radius and no fill of its
                # own; read from the rule rather than from what follows it,
                # so adding a property to `.card` cannot quietly pass.
                rule = html.split(".card{", 1)[1].split("}", 1)[0]
                self.assertIn("border:1px solid var(--line)", rule)
                self.assertNotIn("background:", rule)
                self.assertIn(
                    ".back{width:30px;height:30px;border:0;color:var(--accent);"
                    "background:transparent;cursor:pointer}",
                    html,
                )
                for chrome in (
                    ".action.primary{border-color:transparent;color:#fff",
                    "border-radius:12px;background:var(--soft)",
                    "border:1px solid var(--line);border-radius:8px;color:var(--text)",
                    "color:var(--muted);background:var(--soft);cursor:pointer}.card",
                ):
                    self.assertNotIn(chrome, html)

    def test_a_view_head_is_defined_once_for_every_card(self) -> None:
        """Both cards with a detail view had drawn their own.

        They had already drifted apart in the padding, and would have drifted
        again the moment one of them restyled its way back out of a card.
        """

        for html in (ORBIT_DASHBOARD_HTML, ORBIT_WORKFLOWS_HTML):
            with self.subTest():
                self.assertEqual(1, html.count(".viewHead{"))
                self.assertEqual(0, html.count(".viewHead {"))
                self.assertEqual(1, html.count(".viewTitle{"))
                self.assertEqual(0, html.count(".viewTitle {"))

    def test_it_does_not_request_a_large_display_surface(self) -> None:
        self.assertNotIn("request-display-mode", ORBIT_DASHBOARD_HTML)
        self.assertNotIn("fullscreen", ORBIT_DASHBOARD_HTML)

    def test_it_has_no_direct_mutation_path(self) -> None:
        self.assertNotIn("start_run", ORBIT_DASHBOARD_HTML)
        self.assertNotIn("cancel_run", ORBIT_DASHBOARD_HTML)
        self.assertNotIn("resume_run", ORBIT_DASHBOARD_HTML)
        self.assertNotIn("await fetch(", ORBIT_DASHBOARD_HTML)

    def test_it_supports_chinese_and_english(self) -> None:
        self.assertIn("'en-US'", ORBIT_DASHBOARD_HTML)
        self.assertIn("'zh-CN'", ORBIT_DASHBOARD_HTML)


class DedicatedCardTests(unittest.TestCase):
    def test_goals_card_lists_runs_without_embedding_the_browser_ui(self) -> None:
        self.assertIn("callTool('list_runs',{limit:100})", ORBIT_GOALS_HTML)
        self.assertIn("data-run-id", ORBIT_GOALS_HTML)
        self.assertIn("目标执行卡片", ORBIT_GOALS_HTML)
        self.assertNotIn("<iframe", ORBIT_GOALS_HTML)
        self.assertNotIn("127.0.0.1:8848/ui", ORBIT_GOALS_HTML)

    def test_workflow_list_contains_only_catalog_calls(self) -> None:
        self.assertIn("callTool('list_workflows'", ORBIT_WORKFLOWS_HTML)
        self.assertNotIn("list_runs", ORBIT_WORKFLOWS_HTML)
        self.assertNotIn("list_authoring_jobs", ORBIT_WORKFLOWS_HTML)

    def test_workflow_list_items_offer_the_same_new_goal_prompt(self) -> None:
        """Same offer, same prompt, and now the same button.

        The list's 新目标 used to be a neutral pill of its own while the
        workflow's card offered the accent one. Two looks for one action read
        as two different actions, so the list uses `.action.primary` and the
        class it keeps only says where in the row it sits.
        """

        for marker in (
            'class="action primary listGoal"', 'data-goal-id="${esc(w.workflow_id)}"',
            'data-goal-name="${esc(w.name||w.workflow_id)}"',
            "event.stopPropagation()",
            "使用工作流「${b.dataset.goalName}」（${b.dataset.goalId}）执行：",
            ".listGoal { position: absolute; top: 50%; right: 12px;"
            " transform: translateY(-50%); }",
        ):
            self.assertIn(marker, ORBIT_WORKFLOWS_HTML)
        # Nothing left that repaints it away from the shared button.
        for absent in ("light-dark(#e5e5e8, #303034)", ".listGoal:hover"):
            self.assertNotIn(absent, ORBIT_WORKFLOWS_HTML)

    def test_workflow_item_switches_to_detail_inside_the_list_card(self) -> None:
        for marker in (
            "b.onclick=()=>openDetail(b.dataset.openId)",
            "callTool('get_workflow_definition',{workflow_id:workflowId})",
            "function drawDetail(w)", 'id="workflowBack"',
            "document.getElementById('workflowBack').onclick=showList",
            "else if(value?.workflow_id){current=value;drawDetail(current)}",
        ):
            self.assertIn(marker, ORBIT_WORKFLOWS_HTML)
        self.assertNotIn("使用工作流详情卡片展示", ORBIT_WORKFLOWS_HTML)

    def test_workflow_detail_returns_mutations_to_chat(self) -> None:
        self.assertIn("get_workflow_definition", ORBIT_WORKFLOWS_HTML)
        for label in ("新目标", "修改", "删除"):
            self.assertIn(label, ORBIT_WORKFLOWS_HTML)
        self.assertIn(
            'data-prompt="使用工作流「${esc(w.name||w.workflow_id)}」（${esc(w.workflow_id)}）执行："',
            ORBIT_WORKFLOWS_HTML,
        )
        self.assertIn(
            'data-prompt="按照下面的要求修改工作流「${esc(w.name||w.workflow_id)}」（${esc(w.workflow_id)}）："',
            ORBIT_WORKFLOWS_HTML,
        )
        self.assertNotIn("callTool('start_run'", ORBIT_WORKFLOWS_HTML)
        self.assertNotIn("callTool('delete", ORBIT_WORKFLOWS_HTML)

    def test_workflow_delete_requires_card_confirmation_then_returns_to_chat(self) -> None:
        for marker in (
            'id="deleteWorkflowDialog"', "showModal()", "确认删除工作流？",
            'id="cancelDeleteWorkflow"', 'id="confirmDeleteWorkflow"',
            "我确认删除工作流", "重新读取其最新版本", "新的幂等键",
            "bindDeleteConfirmation(w)",
        ):
            self.assertIn(marker, ORBIT_WORKFLOWS_HTML)
        self.assertNotIn("callTool('delete_workflow'", ORBIT_WORKFLOWS_HTML)

    def test_workflow_detail_uses_the_bundled_xyflow_viewer(self) -> None:
        for marker in (
            "OrbitWorkflowGraph", "OrbitWorkflowGraph.mount",
            'data-workflow-graph aria-label="Workflow graph"',
            "react-flow__controls", "react-flow__background",
        ):
            self.assertIn(marker, ORBIT_WORKFLOWS_HTML)
        for absent in ('class="graphEdge', "function bindGraph()", "forceSimulation"):
            self.assertNotIn(absent, ORBIT_WORKFLOWS_HTML)

    def test_workflow_detail_embeds_assets_without_remote_runtime_dependencies(self) -> None:
        self.assertNotRegex(ORBIT_WORKFLOWS_HTML, r'<script[^>]+src=')
        self.assertNotRegex(ORBIT_WORKFLOWS_HTML, r'<link[^>]+href=')
        self.assertRegex(ORBIT_WORKFLOWS_HTML, r"(?:const|var) OrbitWorkflowGraph=")

    def test_workflow_detail_defaults_to_graph_and_tabs_to_definitions(self) -> None:
        for marker in (
            'role="tablist"', 'id="workflowGraphTab"',
            'aria-selected="true" aria-controls="workflowGraphPanel"',
            'id="workflowDefinitionTab"', 'aria-controls="workflowDefinitionPanel"',
            'id="workflowDefinitionPanel" class="detailPanel definition" role="tabpanel"',
            "function bindTabs()", "ArrowLeft", "ArrowRight", "Home", "End",
        ):
            self.assertIn(marker, ORBIT_WORKFLOWS_HTML)
        self.assertIn(
            'id="workflowDefinitionPanel" class="detailPanel definition" role="tabpanel" '
            'aria-labelledby="workflowDefinitionTab" hidden',
            ORBIT_WORKFLOWS_HTML,
        )
        self.assertIn('.tab[aria-selected="true"]::after{background:var(--accent)}', ORBIT_WORKFLOWS_HTML)
        self.assertNotIn('.tab[aria-selected="true"]{color:var(--text);background:', ORBIT_WORKFLOWS_HTML)

    def test_workflow_list_and_detail_share_a_stable_card_height(self) -> None:
        self.assertIn(
            "#card.workflowList, #card.workflowDetail { height: var(--card-height); }",
            ORBIT_WORKFLOWS_HTML,
        )
        self.assertNotIn("--workflow-card-height", ORBIT_WORKFLOWS_HTML)
        self.assertIn("card.className='card workflowList'", ORBIT_WORKFLOWS_HTML)
        self.assertIn("card.className='card workflowDetail'", ORBIT_WORKFLOWS_HTML)
        self.assertIn(
            "#card.workflowDetail .detailPanel { flex: 1 1 auto; height: auto; min-height: 0; }",
            ORBIT_WORKFLOWS_HTML,
        )

    def test_dashboard_height_is_one_height_for_every_tab(self) -> None:
        """A minimum and a maximum is not a height.

        The card was as tall as whatever the open tab held, between 420 and
        640, so switching to a History with nothing in it yet shrank the card
        by 220px and moved the tabs the reader had just pressed. One height,
        and the tall lists still scroll inside it.
        """

        self.assertIn(
            "#card { height: var(--card-height); margin-top: 12px; }",
            ORBIT_DASHBOARD_HTML,
        )
        for absent in ("min-height: var(--dashboard", "max-height: var(--dashboard"):
            self.assertNotIn(absent, ORBIT_DASHBOARD_HTML)
        # Tall enough to hold the prompt editor it opens over itself.
        self.assertIn(".promptEditorInput { display: block; width: 100%; min-height: 132px;", ORBIT_DASHBOARD_HTML)

    def test_cards_receive_late_codex_tool_output(self) -> None:
        self.assertIn("openai:set_globals", ORBIT_WORKFLOWS_HTML)
        self.assertIn("globals.toolOutput", ORBIT_WORKFLOWS_HTML)
        self.assertIn("publishToolResult", ORBIT_WORKFLOWS_HTML)
        self.assertIn(".detailPanel{height:420px;overflow:hidden}", ORBIT_WORKFLOWS_HTML)
        self.assertIn(".detailPanel.definition{overflow-y:auto}", ORBIT_WORKFLOWS_HTML)

    def test_workflow_graph_supports_zoom_and_horizontal_pan(self) -> None:
        for marker in (
            "react-flow__controls-button", "react-flow__controls-zoomin",
            "react-flow__controls-zoomout", "react-flow__controls-fitview",
            "panOnScroll", "Horizontal", "maxZoom", "minZoom",
        ):
            self.assertIn(marker, ORBIT_WORKFLOWS_HTML)

    def test_workflow_graph_tracks_the_codex_host_theme(self) -> None:
        for marker in (
            "host-context-changed", "applyHostContext", "currentTheme()",
            "document.documentElement.style.colorScheme=theme",
        ):
            self.assertIn(marker, ORBIT_WORKFLOWS_HTML)

    def test_workflow_detail_uses_the_host_background(self) -> None:
        self.assertIn("--host-canvas: light-dark(#ffffff, #151515)", ORBIT_WORKFLOWS_HTML)
        self.assertIn("html, body, main", ORBIT_WORKFLOWS_HTML)
        self.assertIn("background: var(--host-canvas) !important", ORBIT_WORKFLOWS_HTML)
        self.assertIn(
            ".card, .tabs, .actions, .workflowGraphMount, .mcp-xyflow-viewer",
            ORBIT_WORKFLOWS_HTML,
        )
        self.assertIn("background: transparent !important", ORBIT_WORKFLOWS_HTML)

    def test_definition_items_expand_to_show_node_details(self) -> None:
        for marker in (
            "definitionItemToggle", 'aria-expanded="false"',
            "bindDefinitionItems()", "n.handler", "n.prompt",
        ):
            self.assertIn(marker, ORBIT_WORKFLOWS_HTML)

    def test_authoring_card_is_scoped_to_authoring(self) -> None:
        for marker in ("get_authoring_job", "list_authoring_jobs", "Publish workflow"):
            self.assertIn(marker, ORBIT_AUTHORING_HTML)
        self.assertNotIn("list_runs", ORBIT_AUTHORING_HTML)

    def test_run_card_is_scoped_to_one_run_and_its_result(self) -> None:
        for marker in ("inspect_run", "get_run_steps", "read_artifact_content"):
            self.assertIn(marker, ORBIT_RUN_HTML)
        self.assertNotIn("list_authoring_jobs", ORBIT_RUN_HTML)

    def test_run_card_labels_its_result(self) -> None:
        self.assertIn('<h2 class="resultTitle">执行结果</h2>', ORBIT_RUN_HTML)
        self.assertIn(".resultTitle{margin:0 0 6px", ORBIT_RUN_HTML)

    def test_run_card_clamps_the_goal_and_has_no_progress_bar(self) -> None:
        for marker in (
            "-webkit-line-clamp: 3", "-webkit-box-orient: vertical",
            'class="goal"', 'class="steps"',
        ):
            self.assertIn(marker, ORBIT_RUN_HTML)
        for absent in ('class="progress"', "Math.round", "steps.length} steps"):
            self.assertNotIn(absent, ORBIT_RUN_HTML)

    def test_run_card_uses_content_height_up_to_a_600px_maximum(self) -> None:
        """The ceiling is the shared one; only the scroll behaviour is local."""

        for marker in (
            "--card-height:600px",
            "max-height:var(--card-height)",
            "#card.goalRun { overscroll-behavior: contain; }",
            "card.className='card goalRun'",
        ):
            self.assertIn(marker, ORBIT_RUN_HTML)
        self.assertNotIn("--goal-run-card-max-height", ORBIT_RUN_HTML)

    def test_every_card_stops_at_the_same_height(self) -> None:
        """A card with no ceiling grows with its data.

        The goal list reads a hundred runs and had no maximum at all, so it
        was three times the height of the cards beside it and the host had to
        give it a frame to match. One ceiling, declared once, and the lists
        that exceed it scroll inside their own frame.
        """

        for html in (
            ORBIT_DASHBOARD_HTML, ORBIT_WORKFLOWS_HTML,
            ORBIT_AUTHORING_HTML, ORBIT_RUN_HTML, ORBIT_GOALS_HTML,
        ):
            with self.subTest():
                self.assertEqual(1, html.count("--card-height:600px"))
                rule = html.split(".card{", 1)[1].split("}", 1)[0]
                self.assertIn("max-height:var(--card-height)", rule)
                self.assertIn("overflow:hidden auto", rule)
                # It may shrink to fit the frame; it never grows to fill it.
                self.assertIn("flex:0 1 auto;min-height:0", rule)
                # No card carries a ceiling of its own any more.
                for private in ("--workflow-card-height", "--goal-run-card-max-height",
                                "--dashboard-card-height", "--dashboard-card-min-height"):
                    self.assertNotIn(private, html)

    def test_the_document_fits_the_frame_the_host_gives_it(self) -> None:
        """Otherwise the host wraps the whole card in a scrollbar of its own.

        The dashboard's document is 60px taller than the other cards — a tab
        bar and a line under the title they do not have — so at a frame that
        fitted them it was the one card with an outer scrollbar around it and
        an inner one beside it. `main` is capped at the viewport and the card
        shrinks into what the chrome leaves; the scrolling stays inside the
        list, where it already was.
        """

        for html in (
            ORBIT_DASHBOARD_HTML, ORBIT_WORKFLOWS_HTML,
            ORBIT_AUTHORING_HTML, ORBIT_RUN_HTML, ORBIT_GOALS_HTML,
        ):
            with self.subTest():
                self.assertIn(
                    "main{padding:16px;display:flex;flex-direction:column;"
                    "max-height:100vh;max-height:100dvh}",
                    html,
                )
                # The chrome is not what gets squeezed.
                self.assertIn("margin-bottom:14px;flex:none}", html)
        self.assertIn("#tabs { align-items: center; flex: none;", ORBIT_DASHBOARD_HTML)

    def test_every_card_keeps_its_scrollbar(self) -> None:
        """A bar that is there before you need it, and stays after.

        The platform default on macOS is an overlay scrollbar: no width,
        visible only while a finger is moving. A list gave no sign that it
        continued, and the content shifted sideways the moment the bar
        arrived. `scrollbar-gutter: stable` buys the column once, for every
        card, whether or not that card scrolls today.

        Both mechanisms are written because no engine reads both: current
        Chromium honours the standard properties and ignores the WebKit
        pseudo-elements outright, and WebKit has only ever had those.
        """

        for html in (
            ORBIT_DASHBOARD_HTML, ORBIT_WORKFLOWS_HTML,
            ORBIT_AUTHORING_HTML, ORBIT_RUN_HTML, ORBIT_GOALS_HTML,
        ):
            with self.subTest():
                self.assertIn("scrollbar-gutter:stable;scrollbar-width:thin;", html)
                self.assertIn(
                    "scrollbar-color:color-mix(in srgb,var(--muted) 40%,transparent)"
                    " transparent}",
                    html,
                )
                self.assertIn(".card::-webkit-scrollbar{width:11px}", html)
                self.assertIn(
                    ".card::-webkit-scrollbar-thumb{border:3px solid transparent;"
                    "border-radius:999px;\n    background:color-mix(in srgb,"
                    "var(--muted) 40%,transparent);background-clip:content-box}",
                    html,
                )
                # `--line` is 33 levels off white; it could not be seen.
                self.assertNotIn("scrollbar-color:var(--line)", html)

    def test_the_goal_list_second_line_reads_as_a_second_line(self) -> None:
        """`--faint` was never declared on any card.

        An undefined custom property makes the declaration invalid at
        computed-value time, so `.goalMeta` inherited the row's colour and
        printed in the same ink as the title above it.
        """

        self.assertIn(".goalMeta { margin-top: 5px; color: var(--muted);", ORBIT_GOALS_HTML)
        for html in (
            ORBIT_DASHBOARD_HTML, ORBIT_WORKFLOWS_HTML,
            ORBIT_AUTHORING_HTML, ORBIT_RUN_HTML, ORBIT_GOALS_HTML,
        ):
            with self.subTest():
                self.assertNotIn("var(--faint)", html)


if __name__ == "__main__":
    unittest.main()
