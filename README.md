# PromptaFlow

<p align="center">
  <img src="./docs/images/promptaflow-banner.png" alt="PromptaFlow — Local Agent Workflow Runtime" width="100%">
</p>

[简体中文](./README.zh-CN.md) | **English**

PromptaFlow is a local, durable LangGraph workflow Runtime for Agent Apps. A stable
Hub routes API, Web UI, workflow authoring, and MCP traffic to one managed
Runtime process per Workspace. Project data is stored under `~/.promptaflow/projects/`.

It is reached today from the **Codex app**, from **WorkBuddy**, from the
**DeepSeek Harness** panel, and from any other MCP-capable App — each through
its own front door, all against the same Runtime. Agent steps normally fork an
installed CLI; they can instead be delegated to the conversation that started
the run, which needs no CLI at all.

## Install the CLI

PromptaFlow requires Python 3.10 or newer and
[uv](https://docs.astral.sh/uv/).

```bash
uv tool install promptaflow      # or: pipx install promptaflow
uv tool update-shell
```

To work from source:

```bash
git clone https://github.com/TNJ2026/promptaflow.git
cd promptaflow
uv sync --extra dev
uv run promptaflow serve
```

On Windows, native PowerShell launchers work without Git Bash. The start script
registers the current workspace; restart and stop act on the Hub and every
Workspace Runtime they discover:

```bat
start-promptaflow.cmd
restart-promptaflow.cmd
stop-promptaflow.cmd
```

The `.cmd` entry points run directly from PowerShell, Command Prompt, or
Explorer without changing the machine's PowerShell execution policy. Use
`restart-promptaflow.cmd -DryRun` or `stop-promptaflow.cmd -DryRun` to inspect the
processes they would handle without stopping anything.

Pass a path to start another workspace:

```bat
start-promptaflow.cmd "D:\Develop\your-project"
```

The UI is available at `http://127.0.0.1:8848/ui`. That page lists the
Workspace Runtimes running on this machine and links into each one's UI; it
starts nothing, so a Workspace whose Runtime is not up does not appear there.

There is one UI, one catalog and one published Workflow library. A Workflow
names the Agents its author chose and runs on them wherever they exist.

A published Workflow pins the exact Handler build it was compiled against, and
for an Agent that build is its CLI version — so a Workflow written on another
machine, or one whose CLI has since been upgraded, names something that is not
here. A step with nowhere to go is carried to an Agent that is, and as little
as possible: to the same Agent's installed build where there is one, and only
failing that to whichever Agent this Runtime is talking to. A step whose Agent
*is* installed is never moved, so a Workflow that deliberately uses two Agents
keeps using two.

Which Agent stands in for a missing one follows the most recent MCP client to
introduce itself, and stays that Agent while none is connected. Where nothing
can be named the published binding stands and the compiler says whether it
resolves, exactly as it would if this fallback did not exist.

The published definition is never rewritten; the substituted graph is stored
with the run, so a finished run still names the Agent that actually executed
it after the connected Agent has changed.

## Hosts

PromptaFlow is one Runtime with several front doors. Each host reaches it
differently, registers under its own client name, and differs in whether it
draws PromptaFlow's cards. **[Each has its own page.](./docs/hosts/README.md)**

| Host | How it reaches PromptaFlow | Registers as | Draws the card |
| --- | --- | --- | --- |
| [Codex app](./docs/hosts/codex-app.md) | bundled plugin, stdio proxy → Hub | `codex-app` | yes |
| [WorkBuddy](./docs/hosts/workbuddy.md) | custom connector, HTTP straight at the Hub | `promptaflow`, and `workbuddy-third-party:custom-mcp:promptaflow` | yes |
| [DeepSeek Harness](./docs/hosts/deepseek-harness.md) | Host Profile Bundle with its own Gateway and panel | per-Session `harness:session:*` actor | its own panel |
| [Any other MCP App](./docs/hosts/other-apps.md) | stdio proxy | its own stable name | host-dependent |

A client name may not shadow a discovered CLI. The Runtime finds installed
CLIs as the Agents `codex`, `claude` and others, so an App registering as one
of those is refused rather than renamed — which is what the `-app` suffix is
for.

PromptaFlow also ships five small pages a host can draw beside the conversation
— **[the cards](./docs/cards.md)** — which tool opens each, and why one
sometimes looks stale after an upgrade.

Everything below is the same wherever you connect from.

## Run a goal

1. Open **Goal**.
2. Select a published workflow, or describe one and let an Agent write it.
3. Enter the goal and start it.
4. Follow step progress in the workspace or inspect completed runs in
   **History**.

PromptaFlow can also be operated through MCP with `list_runs`, `inspect_run`,
`start_run`, and `cancel_run`. Clients must follow the Runtime's
`allowed_commands[]`; do not construct mutation URLs.

## Delegating a goal to the conversation

Ordinarily every Agent step forks the CLI it names. `execution_mode` offers
the other arrangement: run the whole Workflow, but have the conversation that
started it do the Agent work.

```text
start_run(workflow_id=..., goal=..., execution_mode="current_app")
```

The Runtime rebinds each `agent.*` node in that Run to the `app.delegate`
Handler with `target: run_initiator`, and leaves the published definition
alone — ports, edges, mappings, back edges, conditions and instructions are
untouched, so nothing has to be rewritten to rename `prompt` to `task`. The
substituted graph is stored with the Run, so a finished Run still names what
actually executed it. Parallel branches are included, and no CLI has to be
installed for any of it.

This mode always returns asynchronously. Following the Run means working the
queue:

- `claim_delegation` leases the oldest queued delegation for this session and
  returns the request; execute it in the conversation.
- `renew_delegation` keeps the lease alive and reports cancellation.
- `checkpoint_delegation` records the latest safe resume point and renews the
  lease in one step.
- `complete_delegation` submits the result — or an error.

The queue is actor-scoped, so another conversation cannot pick up this one's
work. It is also the idempotency boundary: one deterministic delegation id can
be claimed at most once, and a lease that expires becomes `unknown` rather
than being handed to a second Agent. `reconcile_delegation` records a human
verdict for an `unknown` one; it never retries or rewrites the original
attempt, because the attempt may well have happened.

Because Runs outlive conversations, every supported host checks for resumable
work on the first user turn of a conversation: one `list_delegations` call
with its default statuses, silence when it is empty, and a question to the
user when it is not. A still-leased delegation owned by the same stable worker
may continue from its checkpoint after renewing the lease.

`app.delegate` can also be written into a Workflow directly, rather than
reached through `execution_mode`. Its input port is named `task` rather than
`prompt`, and `config.target` must be `run_initiator`. Two constraints come
from what an App can produce: the node has to be an `action` whose single
output is `result`, and an artifact output has to accept `text/*` or
`application/json`. `harness.subagent` is the neighbouring Handler for
Harness-managed subagent Providers, where the provider is named in the
delegation request rather than fixed in the registry.

## Runs, events and output

Runtime events can be consumed with `wait_app_event`, `list_app_events`, and
`ack_app_event`. These three are the stdio proxy's own, so they are there for
the Codex app and for any App connected the same way, and not for a host that
speaks to the Hub directly — the Runtime's own event tool is
`list_runtime_events`. `event_type` is `langgraph_run.<status>` for a run's state
changes and `langgraph_node.<outcome>` for one Handler attempt, which also
carries `node_id` and `attempt_id`. Node events come from Handlers with an
attempt journal — the ones whose execution is an effect that must not repeat —
so a replayed superstep announces nothing. Treat events as hints and re-read
the referenced Run before acting.

A run executes inside the request that starts it. `POST /api/v1/langgraph-runs`
with `"wait": false` returns as soon as the run exists, and executes it in the
background — what the UI asks for, so the page can watch a goal it started.
Everything that decides whether the run may exist has already happened either
way; what waiting buys is being told how it ended.

One goal runs at a time, per actor: starting a second
while one is `running`, `waiting` or `interrupted` is refused with
`active_goal_exists`, and the refusal names the run holding the slot so a
client can go to it. Cancelling or finishing releases it.

Runs are kept until you say otherwise. `/api/v1/ops/status` reports what the
engine is holding, and `create_app(run_retention_days=N)` forgets runs that
ended more than N days ago — whole ones, since a run without its console or
its checkpoints describes itself wrongly. A run waiting on a person, or one
whose Handler ended `unknown`, is never forgotten.

What a run's Handlers printed is read from
`GET /api/v1/langgraph-runs/{run_id}/output?after=<chunk_id>`, which needs the
sensitive scope. It is a console, not a log: bounded per attempt and per
stream, written outside every transaction, and never something a replay reads.

## CLI quick reference

```bash
promptaflow serve
promptaflow serve --project-root /absolute/path/to/project
promptaflow hub register /absolute/path/to/project --no-agent-project-access
promptaflow --version
promptaflow runtimes --json                     # which Runtimes are up, and where
promptaflow mcp
promptaflow mcp --project-root /absolute/path/to/project
promptaflow run list
promptaflow run inspect <run_id>
promptaflow workflow validate <file> --catalog <catalog.json>
promptaflow workflow publish <file> --catalog <catalog.json> --expected-version <n>
```

`promptaflow serve` is the unified entry point: it reuses or starts the Hub on
`127.0.0.1:8848`, registers the current Workspace, and waits for the Hub-managed
Runtime to become ready. It no longer exposes a standalone Runtime mode. Runtime state and Artifacts are
project-scoped; published Workflow definitions are host-wide and visible from
every Workspace. The Hub also owns reusable Workflow source templates and
aggregates Agent statistics from live Workspace Runtimes.

## Codex plugin distribution

PromptaFlow is distributed as a repository/personal Marketplace plugin. It is not
submitted to the universal public Plugins Directory.
See the [complete Codex app installation guide](./docs/hosts/codex-app.md),
including the one-line prompt that lets Codex install it from this repository.

Each GitHub Release includes a Marketplace ZIP, a standalone Codex plugin ZIP,
the Python wheel and source distribution, and the DeepSeek Harness bundle.
Download and extract `promptaflow-marketplace-<version>.zip`, then register its root
directory and install PromptaFlow:

```bash
unzip promptaflow-marketplace-<version>.zip
codex plugin marketplace add ./promptaflow-marketplace
codex plugin add promptaflow@promptaflow-local
codex plugin list
```

Keep the extracted `promptaflow-marketplace` directory in a stable location: the
configured Marketplace source refers to it. To update, download and extract the
new release, replace the previous directory, then run:

```bash
codex plugin add promptaflow@promptaflow-local
```

Fully quit and reopen the ChatGPT desktop app, then start a new task so Codex
loads the updated plugin metadata and skills.

## Development

```bash
uv sync --extra dev
.venv/bin/python -m unittest discover -s tests
node --test tests/ui/client_modules.test.mjs
```

Build the Python package with:

```bash
uv build
python scripts/build-marketplace-release.py \
  --version 0.6.0-alpha \
  --output dist/promptaflow-marketplace-0.6.0-alpha.zip \
  --plugin-output dist/promptaflow-plugin-0.6.0-alpha.zip
```

Pushing a full SemVer tag such as `v0.6.0-alpha` runs the Release workflow. It
verifies that the version without `v` matches `src/promptaflow/__init__.py`, runs the
tests, and uploads all distribution assets to a GitHub pre-release. The same workflow
can be started manually for an existing tag; repeated runs replace its uploaded
assets. PyPI publishing is opt-in on a manual run and requires a configured Trusted
Publisher; normal tag releases remain GitHub-only.
