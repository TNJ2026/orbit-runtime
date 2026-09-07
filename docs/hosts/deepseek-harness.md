# Orbit in the DeepSeek Harness

[简体中文](./deepseek-harness.zh-CN.md) | **English** · [Hosts](./README.md) · [Orbit](../../README.md)

| | |
| --- | --- |
| Reaches Orbit through | a Host Profile Bundle with its own Gateway |
| Registers as | a per-Session `harness:session:*` actor |
| Draws Orbit's cards | no — it draws its own panel |
| MCP tool profile | `harness`, a subset of the full surface |

## Install from the repository

`integrations/deepseek-harness` is the installable Host Profile Bundle. This
installation keeps Orbit Runtime as an independent local process and adds the
Orbit panel and tools to the Harness Web Profile.

### Install with a simple prompt

Paste this into a DeepSeek Harness Agent that can read public repositories and
run local commands:

```text
Install the Orbit DeepSeek Harness integration from https://github.com/TNJ2026/orbit.
```

The Agent should find this document from the repository's host index and
follow the steps below. It must stop before restarting the active Harness
Profile and tell you when that restart is required.

### 1. Check the prerequisites

- Git and `uv`.
- Python 3.10 or newer for Orbit Runtime.
- Node.js 22 or newer for the integration bundle.
- A working `dsh` command and a Harness Web Profile named `web`.

Check them before changing the Profile:

```bash
git --version
uv --version
node --version
dsh --version
```

### 2. Clone Orbit into a stable directory

```bash
git clone https://github.com/TNJ2026/orbit.git /absolute/stable/path/orbit
cd /absolute/stable/path/orbit
```

If the repository already exists, inspect its changes before updating it. Do
not discard local work; update a clean checkout with `git pull --ff-only`.

### 3. Install Orbit Runtime

```bash
uv tool install /absolute/stable/path/orbit
uv tool update-shell
orbit --version
```

Open a new terminal if `orbit` is not immediately visible after
`uv tool update-shell`.

### 4. Add the Harness bundle

Stop the active Web Profile before replacing an existing bundle, then run:

```bash
dsh plugin --profile web add /absolute/stable/path/orbit/integrations/deepseek-harness
dsh --profile web --dump-config
```

The dumped Profile configuration must contain
`@orbit-runtime/dsh-orbit`. The source path should resolve to the checkout used
above.

### 5. Restart and verify

1. Restart the Harness Web Profile.
2. Open a workspace backed by a real directory.
3. Run `/orbit`.
4. Confirm the Orbit panel appears and its Settings row reports **connected**.
5. Open one historical Run or ask the Agent to list Orbit workflows to verify
   the Host-to-Runtime path.

Opening `/orbit` starts Orbit for the Harness Workspace when necessary; a
Runtime started this way stays up after the panel or Profile closes. The
Gateway looks for ownership records under `~/.orbit` — set
`ORBIT_RUNTIME_ROOT` for the Profile if the Runtime database lives elsewhere.
The Orbit CLI holds a non-blocking ownership lock on that database and
publishes its Workspace and MCP endpoint in the ownership record; Harness
never owns that lock and never creates a second writer.

### Upgrade, roll back, or remove

For an upgrade, stop the Profile, update the clean checkout, refresh the Runtime
tool, and add the bundle again:

```bash
cd /absolute/stable/path/orbit
git pull --ff-only
uv tool install --force /absolute/stable/path/orbit
dsh plugin --profile web add /absolute/stable/path/orbit/integrations/deepseek-harness
dsh --profile web --dump-config
```

Restart the Profile and repeat the verification above. To roll back, check out
the intended released tag in a clean checkout, reinstall that Runtime and
bundle, then restart. Do not delete the Orbit Runtime database during a bundle
rollback.

Remove only the Harness integration with:

```bash
dsh plugin --profile web remove @orbit-runtime/dsh-orbit
dsh --profile web --dump-config
```

The second command should no longer list the bundle. Removing it does not stop
or delete an independent Orbit Runtime.

| Component | Supported range |
| --- | --- |
| Orbit Runtime | `>=0.4.0 <0.5.0` |
| Orbit integration protocol | `orbit-harness/1` |
| Harness packages | `>=0.1.1-rc.2 <0.2.0` (alpha prereleases are not supported) |
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

## The panel

Opening a Run gives it the whole panel, with the way back at the top; opening
a step shows that step's output. A Run's detail does not fit beside its
siblings at panel width — expanding one inline pushed the rest of the list
out, which is the same as losing it. Nothing below the first level is fetched
until a row is expanded, and following stops when there is nothing left to
follow.

A Run can be cancelled, an interrupted one continued, and a step waiting on a
person ruled on, all from the panel. Every mutation carries the revision the
panel was displaying and is refused if Orbit has moved past it: a button that
quietly acted on a newer Run than the one being read would be worse than one
that fails.

The panel lists the Workspace's Runs, not the chat's. Every Gateway call
carries a per-Session actor and `list_runs` scopes to its caller by default —
right for the Agent's account of its own work, wrong for a panel standing
beside Orbit's UI, where it showed an empty History next to a Runtime holding
twenty-five Runs. The panel passes `owner: workspace`; the Agent tool keeps
the default.

Polling follows the work: every couple of seconds while a Run is moving, every
fifteen while none is, one round trip per tick carrying only a Session id.

Colours come from the shell's `--dsw-alias-*` tokens, so the panel follows the
Harness theme rather than holding an opinion about it.

## Naming a workflow

Selecting a Workflow in the panel writes an invocation sentence into the
active conversation draft; you add the goal and submit it there, so the Agent
owns the Run. `/orbit-workflows` opens the shell's own picker — the one
`/model` uses — and drops the choice in as a reference chip.

The chip has two faces: you see the name, and the model receives
`workflow:cov-branch（覆盖 A：分支与条件）`, so it never has to resolve a name
back to an id or guess between two that read alike. The bundle also names the
ready Workflows of every bridged Workspace in the model's context, with the
inputs each one needs — which is the mistake it exists to prevent.

Both read one cache filled by the panel's own poll, so nothing asks twice for
something that only changes when a Workflow is published, and a Runtime that
is down leaves the last answer standing rather than emptying the context.

## The Host API

`/plugins/dsh-orbit/api` on the Harness origin offers Run inspection, Steps,
Graph, Edges, cursor-based output, bounded Artifact content and Attachment
import. Every call carries a Workspace and the Host trusts none of them: each
is checked against the Session it claims to belong to, or against the
Workspace registry, before any Gateway call. It never lets a caller reach
Orbit loopback directly, and client code never receives the Runtime endpoint,
child process handle, actor header or Orbit credentials.

Image Artifacts can be imported into Harness Attachment storage once both
Orbit's 2 MiB proxy bound and Harness image admission pass; the Attachment
contract covers PNG, JPEG, WebP and GIF, and other media stays in Orbit.

The diagnostics document carries only Workspace/Session ids, protocol
capabilities, aggregate counts, Gateway counters and Bridge state — never the
MCP endpoint, actor header, raw output, Artifact bytes, task prompts or
credentials.

## Sessions and recovery

The Host attaches one Bridge to every live root Session with a `cwd`,
including Sessions restored during startup. The Bridge derives its cursor and
known Run ids from durable `orbit/run-*` Session events, so a Host restart
resumes without a second cursor database. Session disposal aborts the poller,
and a temporarily unavailable Runtime is retried without blocking the Session
lifecycle.

Harness contributes the first-turn recovery rule to its own system prompt
assembly and exposes Session-bound delegation tools; the worker id is derived
by the integration rather than supplied by the model. See
[delegating a goal to the conversation](../../README.md#delegating-a-goal-to-the-conversation).

## Failure and reconnection

The Gateway refuses an incompatible Orbit integration protocol at startup, and
runtime codecs reject malformed core DTOs before they reach the Client — a
malformed Run, Step, Output or Artifact payload fails at the Gateway boundary
rather than flowing through TypeScript assertions. When an MCP transport
fails, the cached endpoint is discarded and the next Bridge poll or tool call
reruns discovery, so a Hub restart or a new dynamic Workspace Runtime port does
not require restarting Harness.

Maintainers can verify install, Host/Web startup, HTTP readiness and clean
removal in an isolated temporary Profile with `npm run smoke:profile`. Set
`DSH_BIN` when the launcher is not named `dsh` on `PATH`, and `DSH_BUNDLE_SPEC`
to an absolute `.tgz` path to test the exact release artifact.
