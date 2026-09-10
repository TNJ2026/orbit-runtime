# PromptaFlow for DeepSeek Harness

This directory is the installable Host Profile Bundle for `deepseek-harness`.
PromptaFlow Runtime stays an independent process. The `PromptaFlowGateway` discovers the
`paf serve` instance published for the normalized Workspace, starts one on a
free port when none exists, performs the capability handshake, and communicates
with it only through HTTP MCP. A Runtime started this way remains available
after the panel or Harness Profile closes.

## Prerequisites

- Install `promptaflow` so the executable is on the Harness Host's `PATH`.
Opening `/promptaflow` starts PromptaFlow for the Harness Workspace when necessary. You may
still start it independently to choose additional `paf serve` options.

By default the Gateway discovers ownership records below `~/.promptaflow`. If PromptaFlow
uses a database outside that tree, set `PROMPTAFLOW_RUNTIME_ROOT` for the Harness
Profile to the directory containing the Runtime ownership record. The same
setting works on macOS, Linux and Windows; no platform-specific socket path is
required. Set `PROMPTAFLOW_RUNTIME_ROOT` when ownership records live elsewhere.

Install this directory into the target Harness Web Profile with one command:

`dsh plugin --profile web add /absolute/path/to/promptaflow/integrations/deepseek-harness`

Then restart that Profile. Remove it with
`dsh plugin --profile web remove @promptaflow/dsh`. Client code uses the
bundle's same-origin Host API; it never receives the Runtime endpoint, child
process handle, actor header, or PromptaFlow loopback credentials.

Maintainers can verify install, Host/Web startup, HTTP readiness and clean
removal in an isolated temporary Profile with `npm run smoke:profile`. `dsh
plugin` forwards to `pnpm` in the Profile directory, so that smoke needs `pnpm`
on `PATH` as well as the launcher. Set `DSH_BIN` only when the Harness launcher
is not named `dsh` on `PATH`. To test the exact release artifact, set
`DSH_BUNDLE_SPEC` to an absolute `.tgz` path.

## Compatibility

| Component | Supported range |
| --- | --- |
| PromptaFlow Runtime | Any version implementing `promptaflow-harness/2` |
| PromptaFlow integration protocol | `promptaflow-harness/2` |
| Harness packages | `>=0.1.2-rc.1 <0.2.0` (alpha prereleases are not supported) |
| Verified Harness launcher | `0.1.2-rc.1` |
| React | `^18.2.0` |
| Node.js | `>=22` (verified with Harness bundled Node.js 26) |

The Runtime ownership, scoped identity, real HTTP MCP process E2E, TypeScript
build and package surface run in CI on Linux, macOS and Windows. The Profile
install/start/remove smoke additionally requires a locally installed `dsh`
launcher and is exposed as the maintainer command above.

The Gateway refuses an incompatible PromptaFlow integration protocol during startup.
Runtime codecs also reject malformed core DTOs before they reach the Client.
When an MCP transport fails, the cached endpoint is discarded; the next Bridge
poll or tool call reruns discovery, allowing `paf serve` to restart on a new
port without restarting Harness.

## Upgrade and rollback

Before upgrading, install the new bundle, rebuild the Profile, and restart it.
The independent PromptaFlow Runtime can remain running when its protocol is compatible.
Verify the PromptaFlow Settings row reports connected and open one historical Run.

To roll back, stop the Profile, reinstall the previous bundle version, rebuild,
and restart. Rollback does not require deleting the Runtime database.

## Current boundary

The Host exposes Runtime/Run inspection, Steps, Graph, Edges, cursor-based
output, bounded Artifact content, and command execution. Commands are accepted
only after the Host re-reads the Run and matches the requested command and
revision against PromptaFlow's current `allowed_commands[]`.

This bundle contributes a resident PromptaFlow panel to the Harness shell overlay. It
folds down to a badge that says whether anything is running and opens to the
Runtime's own four pages — Goal, Workflows, History, Agents: what is running,
what could, what did, and who by. `/promptaflow` takes no argument and folds it either
way.
The panel can be docked to the side or detached and dragged, and remembers
which between browser sessions.

It deliberately stops there. Graphs, Artifacts and Workflow authoring are drawn
by PromptaFlow's own Runtime UI, which the panel opens in a new tab rather than
redrawing — a second drawing of them here would be a second answer to the same
question, and the bundle carries a test that fails if one starts to appear. Colours come from the shell's
`--dsw-alias-*` tokens, so the panel follows the Harness theme rather than
holding an opinion about it.

Selecting a Workflow in the panel writes an invocation sentence such as
`使用工作流「事故报告处理流程」执行：` into the active conversation draft.
The person adds the goal and submits it there, so the Agent owns the Run and
the panel can report its progress. The full definition and graph remain
available from PromptaFlow's own UI.

Opening a Run gives it the whole panel — the way back is a control at the top —
and opening a step shows that step's output. A Run's detail does not fit beside
its siblings at panel width: expanding one inline pushed the rest of the list
out, which is the same as losing it. Nothing
below the first level is fetched until a row is expanded, and following stops
when there is nothing left to follow.

A Run can be cancelled, an interrupted one continued, and a step waiting on a
person ruled on, all from the panel. Every mutation carries the revision the
panel was displaying and is refused if PromptaFlow has moved past it — a button that
quietly acted on a newer Run than the one being read would be worse than one
that fails.

The panel lists the Workspace's Runs, not the chat's. Every call this Gateway
makes carries a per-Session actor, and `list_runs` scopes to its caller by
default — which is right for the Agent's own account of its work and wrong for a
panel standing beside PromptaFlow's UI, where it showed an empty History next to a
Runtime holding twenty-five Runs. It passes `owner: workspace`; the Agent tool
keeps the default.

Polling follows the work: every couple of seconds while a Run is moving, every
fifteen while none is, and one round trip per tick that carries only a Session
id — the Host derives the Workspace itself, for reads and writes alike.

## Starting a Run

By saying so. The Agent has `promptaflow_list_workflows` and `promptaflow_start_run`, so
"run the CSV cleaner over today's export" is the whole interface; the Run
appears in the panel a moment later.

Neither of you has to remember what exists. The bundle names the ready
Workflows of every bridged Workspace in the model's context — with the inputs
each one needs, which is the mistake it exists to prevent — so the Agent can
answer "which of these did you mean" instead of asking what PromptaFlow is. The panel
lists the same catalog below the Runs, for the person doing the asking, and
`/promptaflow-workflows` opens the shell's own popup — the one `/model` uses, with its
search box and empty state — and selecting a Workflow drops it into the draft as
a reference chip: `用 [覆盖 A：分支与条件] 执行：`, for you to finish.

The chip has two faces. You see the name; the model receives
`workflow:cov-branch（覆盖 A：分支与条件）`, so it never has to resolve a name
back to an id or guess between two that read alike.

Not starting it: the Run has to be the Agent's, or it cannot report on it
afterwards or take the next step from it. A popupSelect is also one list and one
pick, with nowhere to put the goal every Workflow here declares an input for.

Both read one cache filled by the panel's own poll, so nothing asks twice for
something that changes when a Workflow is published; a Runtime that is down
leaves the last answer standing rather than emptying the context.

The panel deliberately has no start button. Harness is a place where work is
described to an Agent, and a Run the panel started itself would be a Run the
Agent knows nothing about — it could not tell you how it went, or take the
next step from it. Starting through the Agent keeps the Run in the
conversation that asked for it.

Authoring is elsewhere for a different reason: writing or revising a Workflow
means reading the generated DSL, its compile diagnostics and its diagram, and
that is PromptaFlow's own UI, one press away from the panel's title bar.

The Host API at `/plugins/dsh-promptaflow/api` on the Harness origin remains available
for a caller that wants Run inspection, Steps, Graph, Edges, cursor-based output,
bounded Artifact content, and Attachment import. Every call carries a Workspace,
and the Host trusts none of them: each is checked against the Session it claims
to belong to, or against the Workspace registry, before any Gateway call. It
never lets a caller reach PromptaFlow loopback directly.

Image Artifacts can be imported into Harness Attachment storage after both
PromptaFlow's 2 MiB proxy bound and Harness image admission pass. The current Harness
Attachment contract supports PNG, JPEG, WebP and GIF; other media stays in PromptaFlow.

The diagnostics document contains only Workspace/Session ids, protocol
capabilities, aggregate counts, Gateway counters and Bridge state. It does not
contain the MCP endpoint, actor header, raw output, Artifact bytes, task prompts
or credentials.

The Host automatically attaches one Bridge to every live root Session with a
`cwd`, including Sessions restored during startup. The Bridge derives its
cursor and known Run ids from durable `promptaflow/run-*` Session events, so a Host
restart resumes without a second cursor database. Session disposal aborts the
poller, and a temporarily unavailable Runtime is retried without blocking the
Session lifecycle.

For the `harness` MCP profile, PromptaFlow accepts `x-promptaflow-actor` only from loopback,
only on `/mcp`, and only under `harness:session:*`. This refines the existing
single local-operator identity for event and single-goal isolation; it does not
grant a remote caller or local process any additional scope.

## Agent tools

The Host registers a bounded native Harness tool surface which routes each
execution through the same Workspace-aware MCP Gateway:

- `promptaflow_list_workflows`
- `promptaflow_list_runs`
- `promptaflow_inspect_run`
- `promptaflow_start_run`
- `promptaflow_cancel_run`
- `promptaflow_resume_run`

The model never supplies an endpoint, actor, idempotency key, or mutation
revision. The Host derives Workspace and Session from `ToolRunContext`, creates
idempotency keys, and re-reads `allowed_commands[]` before cancel or resume.
`promptaflow_start_run` always sends `wait: false`; Run progress is projected by the
Session Bridge rather than holding a Harness tool call open.

Every MCP tool call also carries an `promptaflow/workspace` metadata object derived
by the Host from the Harness Workspace registry: its stable Workspace id and
canonical path, plus isolation metadata when available. A Host API caller
supplies a Workspace too, and it is verified against the Session before use, so
PromptaFlow Runtime discovery and execution follow the Harness Workspace rather than a
caller-constructed `cwd:` identity.

The PromptaFlow CLI takes a non-blocking ownership lock for the runtime database and
publishes its Workspace and MCP endpoint in that ownership record. Harness
never owns that lock and never creates a second writer.

## Agent execution boundary

Harness does not execute PromptaFlow workflow nodes and does not call Harness
Subagent Providers on PromptaFlow's behalf. Agent discovery, CLI credentials,
sandboxing, process cleanup, retry semantics and effects remain owned by the
independent PromptaFlow Runtime. Harness is an MCP client and UI projection only.

Core MCP responses cross runtime codecs before reaching Host or Client code.
Malformed Run, Step, Output, or Artifact payloads fail at the Gateway boundary
instead of flowing through TypeScript assertions.
