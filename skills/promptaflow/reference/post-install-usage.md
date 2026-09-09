# Post-install usage handoff

Use this reference after successfully installing or reinstalling PromptaFlow. Report
the verified installed version and enabled state first. Complete every
Agent-executable refresh step before asking the user to act; do not give the
user validation, reinstall, verification, or Runtime-stop commands that the
Agent can execute. Only at the Host reload boundary should the final response
ask the user to fully quit and reopen Codex and start a new task so the new
plugin skills and MCP tools are loaded. Include the relevant host guide below
in that final handoff. If the host was not specified, include Codex, DeepSeek
Harness, and WorkBuddy.

Only Codex installs the Codex plugin. DeepSeek Harness uses its Host Profile
Bundle, and WorkBuddy uses a custom Streamable HTTP connector. Do not imply that
installing the Codex plugin configures either of those hosts.

## PromptaFlow MCP App card catalogue

Codex and WorkBuddy render these five PromptaFlow cards. The command is the tool whose
response carries the card; there is no separate open-card command.

| Card | Function | Command or tool | Copyable Chinese prompt |
| --- | --- | --- | --- |
| PromptaFlow workspace | Goals, workflows, history, Agents, live progress, and attention state in one workspace view | `open_orbit_dashboard` | `打开 PromptaFlow` |
| PromptaFlow workflows | Published workflow catalogue; selecting an item shows its graph and definition in the same card | `list_workflows`; `get_workflow_definition` opens the same card at one workflow | `显示所有 PromptaFlow 工作流` / `打开工作流 workflow:<id>` |
| PromptaFlow workflow generation | One workflow authoring job's queue, generation, validation, publication, and result state | `generate_workflow` | `生成一个“开发—评审—测试—提交代码”的 PromptaFlow 工作流` |
| PromptaFlow goal execution | One Run's steps, attention state, human interruption, and final result | `start_run` | `用工作流 workflow:<id> 执行目标：<目标原文>` |
| PromptaFlow goals | Recent goal Runs and their current statuses | `open_orbit_goals` | `打开 PromptaFlow 目标列表` |

Cards are views, not authority. A card action sends intent back to the Agent;
the Agent must re-read current state and obey `allowed_commands[]`, current
revision, and confirmation requirements. Use `inspect_workflows` and
`inspect_workflow_definition` for model-side selection or filtering because
those tools intentionally do not mount cards.

## Codex

Codex renders all five MCP App cards above beside the conversation. After
installation, fully quit Codex, reopen it, open the intended project, and start
a new task.

| Intent | Tool sequence | Copyable Chinese prompt |
| --- | --- | --- |
| Open the full workspace card | `open_orbit_dashboard` | `打开 PromptaFlow` |
| Show published workflows | `list_workflows` | `显示 PromptaFlow 工作流列表` |
| Inspect one workflow in the same card | `get_workflow_definition` | `打开工作流 workflow:<id>` |
| Generate a workflow from chat | `register_authoring_client(client="codex-app")`, then `generate_workflow` | `注册为当前项目的 Agent，并生成一个用于 <用途> 的工作流` |
| Listen for Generate clicks from the full UI | `wait_authoring_request(client="codex-app")`; answer with `submit_authoring_response` | `现在监听 PromptaFlow 的工作流生成请求` |
| Modify a published workflow | `modify_workflow`, then poll `get_authoring_job` | `把工作流 workflow:<id> 修改为：<修改要求>` |
| Run a goal | Resolve with `inspect_workflow_definition`, then `start_run` | `用工作流 workflow:<id> 执行目标：<目标原文>` |
| Show recent goals | `open_orbit_goals` | `打开 PromptaFlow 目标列表` |
| Resume delegated work on the first turn | `list_delegations`; ask before continuing when non-empty | `检查是否有可恢复的 PromptaFlow 委托` |

Opening PromptaFlow is display-only. It does not register `codex-app` or start an
authoring listener unless the user explicitly asks.

## DeepSeek Harness

DeepSeek Harness renders **no PromptaFlow MCP App cards**. It installs a Host Profile
Bundle and renders its own resident PromptaFlow panel instead. Describe the following
as Harness native surfaces, never as the five MCP cards.

| Harness surface or function | Command or native tool | Copyable Chinese prompt |
| --- | --- | --- |
| Open or focus the resident PromptaFlow panel | `/orbit` | `打开 PromptaFlow 面板` |
| Open the workflow picker and insert a workflow reference chip | `/orbit-workflows` | `选择一个 PromptaFlow 工作流` |
| List workflows for the Agent | `orbit_list_workflows` | `列出当前 Workspace 的 PromptaFlow 工作流` |
| List Runs | `orbit_list_runs` | `列出我最近的 PromptaFlow 运行` |
| Inspect one Run | `orbit_inspect_run` | `查看 PromptaFlow 运行 run:<id>` |
| Start a Run | `orbit_start_run` | `用工作流 workflow:<id> 执行目标：<目标原文>` |
| Cancel a Run | `orbit_cancel_run` after re-reading current state | `取消 PromptaFlow 运行 run:<id>` |
| Resume an interrupted Run | `orbit_resume_run` with current revision and declared output | `继续 PromptaFlow 运行 run:<id>，审批结果为通过` |

The resident panel contains Goals, Workflows, History, and Agents pages. It can
inspect steps and outputs and handle cancel, resume, and human decisions, but it
deliberately has no Start button: Runs start through the Agent so the Agent can
follow and report them. Workflow graphs, Artifacts, and authoring open PromptaFlow's
full browser UI rather than being redrawn in the panel.

Harness installation prompt:

```text
请安装这个仓库中的 PromptaFlow DeepSeek Harness 集成：https://github.com/TNJ2026/orbit
```

## WorkBuddy

WorkBuddy renders all five MCP App cards in the catalogue. It has no PromptaFlow
plugin or stdio proxy; configure a custom Streamable HTTP connector named
`PromptaFlow` at `http://127.0.0.1:8848/mcp` with no authentication.

| Intent | Tool sequence | Copyable Chinese prompt |
| --- | --- | --- |
| Select the project workspace | `list_workspaces`, then `select_workspace` | `列出 PromptaFlow Workspaces，并选择 <项目名或绝对路径>` |
| Open the workspace card | `open_orbit_dashboard` | `打开 PromptaFlow` |
| Show workflows as a card | `list_workflows` | `显示 PromptaFlow 工作流列表` |
| Select or filter workflows without mounting a card | `inspect_workflows` | `找出所有可以直接启动目标的 PromptaFlow 工作流` |
| Open one workflow in the workflow card | `get_workflow_definition` | `打开工作流 workflow:<id>` |
| Generate a workflow | Register a unique WorkBuddy client name, then `generate_workflow` | `注册当前 WorkBuddy 为工作流编写 Agent，并生成一个用于 <用途> 的工作流` |
| Run and follow a goal | `start_run`, then `inspect_run` and Run detail tools | `用工作流 workflow:<id> 执行目标：<目标原文>` |
| Show recent goals | `open_orbit_goals` | `打开 PromptaFlow 目标列表` |
| Handle current-App Agent steps | `claim_delegation`, `renew_delegation`, `checkpoint_delegation`, `complete_delegation` | `使用 current_app 模式运行，并在本对话中处理所有 Agent 步骤` |

WorkBuddy may register as `orbit` or
`workbuddy-third-party:custom-mcp:orbit`; use the stable name the active
connector reports and never shadow a discovered CLI. Each mounted card opens
its own MCP session, so mount a card only when the user asked to see it.

WorkBuddy connector setup prompt:

```text
请从这个仓库为 WorkBuddy 配置 PromptaFlow 连接器：https://github.com/TNJ2026/orbit
```
