# PromptaFlow

<p align="center">
  <img src="./docs/images/promptaflow-banner.png" alt="PromptaFlow — Local Agent Workflow Runtime" width="100%">
</p>

[简体中文](./README.zh-CN.md) | **English**

PromptaFlow turns a goal into a durable, inspectable Agent workflow. Describe the
work you want done, let an Agent generate a static Workflow DSL, review and publish
it, then run it through installed Agent CLIs or the conversation you are already in.

## What it does

- Generates and modifies reusable workflows from natural-language requirements.
- Compiles a validated static Workflow DSL into LangGraph instead of executing
  an Agent-authored program directly.
- Runs steps on registered Agent CLIs, with branches, conditions, retries,
  approvals and other human-in-the-loop interruptions.
- Keeps workflow versions, run progress, console output and generated Artifacts
  durable and inspectable.
- Exposes the same workflows through a browser workspace, HTTP API, MCP tools and
  five MCP App cards.
- Isolates execution state by workspace while sharing the published workflow
  library and reusable source templates across the local machine.

## How it works

A fixed loopback **Hub** on `127.0.0.1:8848` is the front door. It selects a
workspace and routes MCP, API and UI traffic to that workspace's **Control
Runtime**, which owns graph state, authorization and the authoritative
`allowed_commands[]`. Each Runtime uses authenticated **Execution Workers** to run
trusted Handlers such as Agent CLIs. Workflow definitions are compiled to
LangGraph, and durable state is stored under `~/.promptaflow/projects/`.

```text
Agent App / Browser / API
           │
           ▼
 Hub :8848 (MCP Gateway)
           │
           ▼
 Workspace Control Runtime ──► Execution Workers ──► Agent CLIs / Handlers
           │
           └── LangGraph state, runs and Artifacts
```

## Install

PromptaFlow requires Python 3.10 or newer and
[uv](https://docs.astral.sh/uv/).

### Install with a prompt

Paste this into a supported Agent App. The Agent follows the maintained
instructions in the repository and chooses the installation path for the current
App:

```text
Install PromptaFlow for this app from https://github.com/TNJ2026/promptaflow.
```

App-specific instructions:

- [Codex app](./docs/hosts/codex-app.md)
- [WorkBuddy](./docs/hosts/workbuddy.md)
- [DeepSeek Harness](./docs/hosts/deepseek-harness.md)

### Run from source

```bash
git clone https://github.com/TNJ2026/promptaflow.git
cd promptaflow
uv sync --extra dev
uv run promptaflow serve
```

The unified `serve` command reuses or starts the Hub, registers the current
workspace and waits for its managed Runtime to become ready. Open
`http://127.0.0.1:8848/ui` to see running workspaces.

On Windows, the native launchers work from PowerShell, Command Prompt or Explorer
without changing the PowerShell execution policy:

```bat
start-promptaflow.cmd
restart-promptaflow.cmd
stop-promptaflow.cmd
```

Pass a workspace path to the start command when needed:

```bat
start-promptaflow.cmd "D:\Develop\your-project"
```

## MCP App cards

PromptaFlow ships five compact MCP App views. In an App that supports MCP Apps,
calling the associated tool draws the card beside the conversation. The phrases
below are examples you can say naturally; the Agent maps them to the tools.

### Workspace

<img src="./docs/images/cards/dashboard.png" alt="PromptaFlow workspace card" width="560">

- **Try:** `Open PromptaFlow.`
- **Does:** opens the workspace with Goal, Workflows, History and Agents in one
  view, including the current or most recent goal.

### Workflows

<img src="./docs/images/cards/workflows.png" alt="PromptaFlow workflows card" width="560">

- **Try:** `Show my PromptaFlow workflows.`
- **Does:** lists the published catalogue; selecting a workflow shows its graph and
  definition and offers New goal, Modify and Delete actions.

### Workflow generation

<img src="./docs/images/cards/workflow-generation.png" alt="PromptaFlow workflow generation card" width="560">

- **Try:** `Create a workflow that summarizes an article and turns it into a concise presentation.`
- **Does:** starts Agent authoring and shows the requirement, generation progress
  and the resulting workflow.

### Goal execution

<img src="./docs/images/cards/goal-execution.png" alt="PromptaFlow goal execution card" width="560">

- **Try:** `Run the article-to-presentation workflow for this article.`
- **Does:** starts a goal and follows its steps, required human input, status and
  final result.

### Goals

<img src="./docs/images/cards/goals.png" alt="PromptaFlow goals card" width="560">

- **Try:** `Show my recent PromptaFlow goals.`
- **Does:** lists recent goal runs and their current status, with access to each
  run's details.

See [the card guide](./docs/cards.md) for tool mappings, card behavior and cache
refresh details.

## Run a goal

1. Open **Goal**.
2. Select a published workflow, or describe one and let an Agent create it.
3. Enter the goal and start it.
4. Follow the steps in the workspace or inspect the completed run in **History**.

Over MCP, the main tools are `list_workflows`, `generate_workflow`, `start_run`,
`inspect_run` and `cancel_run`. Clients must use the Runtime's current
`allowed_commands[]` instead of constructing mutation URLs.

## Delegate a goal to the current conversation

Agent steps normally run through the CLI named by the workflow. When no CLI is
installed—or when you want the current App to do the work—start the run with
`execution_mode="current_app"`. PromptaFlow keeps the workflow structure intact,
queues each Agent step for the initiating conversation and stores the effective
graph with the run. The mode is asynchronous and supports parallel branches and
resuming safely from a checkpoint.

```text
start_run(workflow_id=..., goal=..., execution_mode="current_app")
```

## CLI quick reference

```bash
promptaflow serve
promptaflow serve --project-root /absolute/path/to/project
promptaflow hub register /absolute/path/to/project --no-agent-project-access
promptaflow --version
promptaflow runtimes --json
promptaflow mcp
promptaflow mcp --project-root /absolute/path/to/project
promptaflow run list
promptaflow run inspect <run_id>
promptaflow workflow validate <file> --catalog <catalog.json>
promptaflow workflow publish <file> --catalog <catalog.json> --expected-version <n>
```

## Development

```bash
uv sync --extra dev
.venv/bin/python -m unittest discover -s tests
node --test tests/ui/client_modules.test.mjs
```

Build the Python and plugin packages:

```bash
uv build
python scripts/build-marketplace-release.py \
  --version 0.6.1-alpha \
  --output dist/promptaflow-marketplace-0.6.1-alpha.zip \
  --plugin-output dist/promptaflow-plugin-0.6.1-alpha.zip
```

Pushing a full SemVer tag such as `v0.6.1-alpha` runs the cross-platform Release
workflow and uploads the GitHub distribution assets. PyPI publishing is opt-in on
a manual workflow run; ordinary tag releases remain GitHub-only.
