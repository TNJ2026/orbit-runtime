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
draws Orbit's cards. Pick your host below; everything after the host sections
is the same wherever you connect from.

| Host | How it reaches Orbit | Registers as | Draws the card |
| --- | --- | --- | --- |
| Codex app | bundled plugin, stdio proxy → Hub | `codex-app` | yes |
| WorkBuddy | custom connector, HTTP straight at the Hub | `orbit`, and `workbuddy-third-party:custom-mcp:orbit` | yes |
| DeepSeek Harness | Host Profile Bundle with its own Gateway and panel | per-Session `harness:session:*` actor | its own panel |
| Any other MCP App | stdio proxy | its own stable name | host-dependent |

A client name may not shadow a discovered CLI. The Runtime finds installed
CLIs as the Agents `codex`, `claude` and others, so an App registering as one
of those is refused rather than renamed — which is what the `-app` suffix is
for.

### Codex app

Download `orbit-marketplace-<version>.zip` from the matching GitHub Release,
then run:

```bash
unzip orbit-marketplace-<version>.zip
codex plugin marketplace add ./orbit-marketplace
codex plugin add orbit@orbit-local
```

Alternatively, install it from the Codex plugin UI after adding the extracted
Marketplace directory:

1. Open **Plugins** in the Codex app.
2. Find **Orbit** under **Orbit Local** and select **Install**.
3. Start a new Codex task so the installed Skill and MCP tools are loaded.
4. Open the project that should own the workflow Runtime.
5. Ask Codex: `Open Orbit`.

The plugin ships the MCP proxy, and the plugin host sets
`ORBIT_AGENT_APP_WORKSPACE` to the open project. The proxy registers that
workspace with the loopback Hub on port 8848 and uses its workspace-scoped MCP
URL; the Hub starts or discovers a dynamic-port Runtime for it. Orbit requires
an explicit project directory and never uses an incidental process working
directory — in a projectless chat it uses `ORBIT_DEFAULT_WORKSPACE` when
configured, otherwise `~/.orbit/workspaces/default`.

Opening Orbit starts or reuses the Runtime and opens the native dashboard
beside the conversation. It is display-only: it does not register this App as
a writer and does not begin listening for authoring work. Ask for that
explicitly, and Codex calls `wait_authoring_request(client="codex-app")` —
under Codex a pending call sits beside a person who can keep working, and it
is renewed while the task is active. Ending the task removes `codex-app`; the
Runtime keeps running.

Select **Stop Orbit** beside the Refresh button and confirm to stop the
Runtime, workers, timers, MCP endpoint, and event connections for the project.

### WorkBuddy

There is no plugin and no proxy. Add a custom connector pointing straight at
the Hub over HTTP:

```text
http://127.0.0.1:8848/mcp
```

No credentials: the Hub is on loopback, and a loopback caller is already the
operator. WorkBuddy speaks Streamable HTTP
(`accept: application/json, text/event-stream`) and negotiates protocol
`2025-11-25` against Orbit's `2025-06-18`, which it accepts. It also opens a
GET on the endpoint looking for a server-initiated stream; the `405` it gets
back is the answer, not a fault.

Do not use `orbit mcp` here. Its stdio transport is the shape WorkBuddy's own
documentation describes, but the process it starts wants the project database
a running Hub or `orbit serve` already owns, and exits with
`Runtime database is already owned` rather than sharing.

WorkBuddy mounts Orbit's cards, and each mounted card opens its own MCP
session and calls the tools it needs — so a conversation holding six cards is
making six sets of those calls. One tool accounts for this: `list_workflows`
draws the catalogue as a card and answers in prose with a count, so read a
catalogue with `inspect_workflows` instead whenever the answer is yours to
work out rather than a person's to look at. The same pair exists as
`get_workflow_definition` and `inspect_workflow_definition`.

### DeepSeek Harness

`integrations/deepseek-harness` is an installable Host Profile Bundle. Install
it into a Harness Web Profile and restart that Profile:

```bash
dsh plugin --profile web add /absolute/path/to/orbit/integrations/deepseek-harness
```

Remove it with `dsh plugin --profile web remove @orbit-runtime/dsh-orbit`.

Install `orbit` so the executable is on the Harness Host's `PATH`. Opening
`/orbit` starts Orbit for the Harness Workspace when necessary; a Runtime
started this way stays up after the panel or Profile closes. The Gateway looks
for ownership records under `~/.orbit` — set `ORBIT_RUNTIME_ROOT` if the
Runtime database lives elsewhere. The Orbit CLI holds a non-blocking ownership
lock on that database and publishes its Workspace and MCP endpoint in the
ownership record; Harness never owns that lock and never creates a second
writer.

| Component | Supported range |
| --- | --- |
| Orbit Runtime | `>=0.4.0 <0.5.0` |
| Orbit integration protocol | `orbit-harness/1` |
| Harness packages | `>=0.1.1-rc.2 <0.2.0` |
| React | `^18.2.0` |
| Node.js | `>=22` |

The bundle contributes a resident panel to the Harness shell overlay. It folds
down to a badge saying whether anything is running and opens to the Runtime's
own four pages — Goal, Workflows, History, Agents. It can be docked or
detached, and remembers which. Graphs, Artifacts and Workflow authoring are
not redrawn here: the panel opens Orbit's own UI for those.

Runs are started by asking the Agent, not from the panel. The Agent has a
bounded native tool surface — `orbit_list_workflows`, `orbit_list_runs`,
`orbit_inspect_run`, `orbit_start_run`, `orbit_cancel_run`, `orbit_resume_run`
— so "run the CSV cleaner over today's export" is the whole interface. The
model never supplies an endpoint, actor, idempotency key or mutation revision:
the Host derives Workspace and Session from the tool run context, creates
idempotency keys, and re-reads `allowed_commands[]` before cancel or resume.
`/orbit-workflows` opens the shell's own picker and drops the chosen Workflow
into the draft as a reference chip.

The panel has no start button on purpose. A Run the panel started itself would
be a Run the Agent knows nothing about, and could not report on afterwards or
take the next step from.

Harness runs this Runtime under the `harness` MCP tool profile, a subset of the
full surface. It does not execute Orbit workflow nodes: Agent discovery, CLI
credentials, sandboxing, process cleanup, retry semantics and effects all
remain the Runtime's. Orbit accepts the `x-orbit-actor` header only from
loopback, only on `/mcp`, and only under `harness:session:*`.

### Any other MCP-capable Agent App

Connect through Orbit's stdio proxy. Adapt this example to the App's MCP
configuration format:

```json
{
  "mcpServers": {
    "orbit": {
      "command": "bash",
      "args": ["/absolute/path/to/orbit/start-orbit.sh", "--mcp-proxy"],
      "env": {
        "ORBIT_AGENT_APP_WORKSPACE": "/absolute/path/to/project"
      }
    }
  }
}
```

The proxy asks the loopback Hub to register the absolute workspace path; it
does not write the Hub registry itself. Its event inbox defaults to the
workspace's `.orbit/agent-apps/` directory, so a sandboxed App needs write
access only to the selected workspace. Set `AGENT_APP_STATE_DIR` explicitly to
keep that inbox elsewhere.

For Orbit to recognize it as the connected Agent, the App must keep this call
pending:

```text
wait_authoring_request(client="claude-desktop", timeout_seconds=300)
```

Orbit then shows `app:claude-desktop`. Connecting MCP alone does not register
an online App: the pending call is what makes one addressable. An App asked to
write a Workflow submits the DSL with `submit_authoring_response` and processes
compiler feedback through `get_authoring_job`.

Being listed is not being selected. Connected App names sit underneath the
discovered CLIs deliberately — a forked CLI runs, while a parked prompt only
waits and may never be answered — so the Runtime names no App as its default
writer. Pick the client name in the UI's **Written by** field.

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
