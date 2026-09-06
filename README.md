# Orbit

[简体中文](./README.zh-CN.md) | **English**

Orbit is a local, durable LangGraph workflow Runtime for Agent Apps. It combines
the Runtime, API, Web UI, durable timers, workflow authoring, and MCP integration
in one process. Project data is stored under `~/.orbit/projects/`.

It is reached today from the **Codex app**, from **WorkBuddy**, from the
**DeepSeek Harness** panel, and from any other MCP-capable App — each through
its own front door, all against the same Runtime. Agent steps normally fork an
installed CLI; they can instead be delegated to the conversation that started
the run, which needs no CLI at all.

## Install the CLI

Orbit requires Python 3.10 or newer and
[uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/TNJ2026/orbit.git
uv tool update-shell
```

To work from source:

```bash
git clone https://github.com/TNJ2026/orbit.git
cd orbit
uv sync --extra dev
uv run orbit serve
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

Orbit is one Runtime with several front doors. Each host reaches it
differently, registers under its own client name, and differs in whether it
draws Orbit's cards. **[Each has its own page.](./docs/hosts/README.md)**

| Host | How it reaches Orbit | Registers as | Draws the card |
| --- | --- | --- | --- |
| [Codex app](./docs/hosts/codex-app.md) | bundled plugin, stdio proxy → Hub | `codex-app` | yes |
| [WorkBuddy](./docs/hosts/workbuddy.md) | custom connector, HTTP straight at the Hub | `orbit`, and `workbuddy-third-party:custom-mcp:orbit` | yes |
| [DeepSeek Harness](./docs/hosts/deepseek-harness.md) | Host Profile Bundle with its own Gateway and panel | per-Session `harness:session:*` actor | its own panel |
| [Any other MCP App](./docs/hosts/other-apps.md) | stdio proxy | its own stable name | host-dependent |

A client name may not shadow a discovered CLI. The Runtime finds installed
CLIs as the Agents `codex`, `claude` and others, so an App registering as one
of those is refused rather than renamed — which is what the `-app` suffix is
for.

Everything below is the same wherever you connect from.

## Run a goal

1. Open **Goal**.
2. Select a published workflow, or describe one and let an Agent write it.
3. Enter the goal and start it.
4. Follow step progress in the workspace or inspect completed runs in
   **History**.

Orbit can also be operated through MCP with `list_runs`, `inspect_run`,
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
orbit serve
orbit serve --agent-project-access        # let workspace_access nodes reach the project
orbit serve --mcp-tool-profile harness    # the subset the Harness bundle uses
orbit --version
orbit runtimes --json                     # which Runtimes are up, and where
orbit mcp
orbit mcp --project-root /absolute/path/to/project
orbit run list
orbit run inspect <run_id>
orbit workflow validate <file> --catalog <catalog.json>
orbit workflow publish <file> --catalog <catalog.json> --expected-version <n>
```

`orbit serve` binds to `127.0.0.1` by default. Runtime state and Artifacts are
project-scoped; published Workflow definitions are host-wide and visible from
every Workspace. The Hub also owns reusable Workflow source templates and
aggregates Agent statistics from live Workspace Runtimes.

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
  --version 0.4.0 \
  --output dist/orbit-marketplace-0.4.0.zip
```

Pushing a tag such as `v0.4.0` runs the Release workflow, verifies that the tag
matches `src/orbit/__init__.py`, runs the tests, and uploads the wheel, source
distribution, and local Marketplace ZIP to the GitHub Release.
