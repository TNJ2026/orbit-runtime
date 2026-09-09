# PromptaFlow in WorkBuddy

[简体中文](./workbuddy.zh-CN.md) | **English** · [Hosts](./README.md) · [PromptaFlow](../../README.md)

| | |
| --- | --- |
| Reaches PromptaFlow through | a custom connector, HTTP straight at the Hub |
| Registers as | `orbit`, and `workbuddy-third-party:custom-mcp:orbit` |
| Draws PromptaFlow's cards | yes |
| Event tools | the Runtime's `list_runtime_events` |

## Set up the connector from the repository

There is no WorkBuddy plugin and no proxy. PromptaFlow runs locally, and WorkBuddy
connects directly to its loopback Hub with a custom HTTP MCP connector.

### Set up with a simple prompt

Paste this into a WorkBuddy Agent that can read public repositories and run
local commands:

```text
Set up the PromptaFlow connector for WorkBuddy from https://github.com/TNJ2026/promptaflow.
```

The Agent should find this document through the repository's host index,
install and start PromptaFlow, verify the endpoint, then guide you through any
connector-setting action it cannot perform itself.

### 1. Check the prerequisites

- Git and `uv`.
- Python 3.10 or newer.
- A WorkBuddy version that supports custom Streamable HTTP MCP connectors.
- Bash when using the repository launcher. On Windows, use Git Bash or another
  Bash installation available to the Agent.

### 2. Clone and install PromptaFlow

Keep the checkout in a stable location:

```bash
git clone https://github.com/TNJ2026/promptaflow.git /absolute/stable/path/promptaflow
uv tool install /absolute/stable/path/promptaflow
uv tool update-shell
promptaflow --version
```

If the checkout already exists, inspect and preserve local changes. Update a
clean checkout with `git pull --ff-only`, then refresh the installed tool with
`uv tool install --force /absolute/stable/path/promptaflow`.

### 3. Start PromptaFlow for the intended project

Run the repository launcher with the project that should own the Runtime:

```bash
/absolute/stable/path/promptaflow/start-promptaflow.sh /absolute/path/to/project
```

Then verify discovery and open the Hub UI:

```bash
promptaflow runtimes --json
```

Open `http://127.0.0.1:8848/ui`. It should list the intended Workspace. Keep
the checkout in place because its launcher and Agent App manifest are part of
this installation.

### 4. Add the WorkBuddy connector

In WorkBuddy, open its connector or MCP settings and add a custom Streamable
HTTP connector. Labels can vary slightly by WorkBuddy release; use these
values:

| Field | Value |
| --- | --- |
| Name | `PromptaFlow` |
| MCP URL | `http://127.0.0.1:8848/mcp` |
| Transport | Streamable HTTP |
| Authentication | None |

Save and enable the connector for the intended Agent or conversation. Do not
configure a remote URL: PromptaFlow's Hub is intentionally loopback-only.

### 5. Verify the connection

1. Confirm WorkBuddy reports tools for the `PromptaFlow` connector.
2. Ask it to call `list_workspaces`.
3. If more than one Workspace is returned, select the intended one with
   `select_workspace`; never guess a path.
4. Ask to see PromptaFlow workflows or open PromptaFlow and confirm that its card renders.

No credentials are required: the Hub is on loopback, and a loopback caller is
already the operator. WorkBuddy speaks Streamable HTTP
(`accept: application/json, text/event-stream`) and negotiates protocol
`2025-11-25` against PromptaFlow's `2025-06-18`, which it accepts. It also opens a
GET on the endpoint looking for a server-initiated stream; the `405` it gets
back is the answer, not a fault.

Do not use `promptaflow mcp` here. Its stdio transport is the shape WorkBuddy's own
documentation describes, but the process it starts wants the project database
the Hub-managed Runtime already owns, and exits with
`Runtime database is already owned` rather than sharing.

### Upgrade or remove

To upgrade, update a clean checkout, reinstall the tool, and rerun the launcher
for the intended project:

```bash
cd /absolute/stable/path/promptaflow
git pull --ff-only
uv tool install --force /absolute/stable/path/promptaflow
./start-promptaflow.sh /absolute/path/to/project
```

The connector URL does not change, so WorkBuddy normally needs no connector
edit. Reconnect or restart WorkBuddy if it retains an old tool catalogue.

To remove the integration, disable or delete the `PromptaFlow` custom connector in
WorkBuddy. That does not delete Runtime data. Stop PromptaFlow separately with the
**Stop PromptaFlow** control or through the exact Runtime process you started; do not
delete `~/.promptaflow` as an uninstall shortcut.

WorkBuddy mounts PromptaFlow's cards, and each mounted card opens its own MCP
session and calls the tools it needs — so a conversation holding six cards is
making six sets of those calls. One tool accounts for this: `list_workflows`
draws the catalogue as a card and answers in prose with a count, so read a
catalogue with `inspect_workflows` instead whenever the answer is yours to
work out rather than a person's to look at. The same pair exists as
`get_workflow_definition` and `inspect_workflow_definition`.

## Why it appears under two names

WorkBuddy announces `workbuddy-third-party:custom-mcp:orbit` from the
connector settings and plain `orbit` once the connector is loaded into an
agent, so the same App shows up under two names depending on which of its own
paths made the call. Neither shadows a discovered CLI, so neither is refused —
which is the rule the `-app` suffix exists for, and WorkBuddy is the exception
that shows the rule is about Agents rather than tidiness.

## What mounting the cards costs

Which card each tool opens is in [the cards](../cards.md).

WorkBuddy mounts PromptaFlow's MCP App cards in full: it lists the resources, asks
for `resources/templates/list`, then reads the one the tool named through
`_meta.ui.resourceUri` and draws the card. Two things follow.

Each card fetches its own data. A mounted card opens its own MCP session and
calls the tools it needs — the workspace card polls `list_runs` and
`list_authoring_jobs` — so a conversation holding six cards is making six sets
of those calls, and a tool that mounts a card per item will fill the
transcript.

And the text a tool returns is read by the model, not only by the host.
Shortening every card-bound tool's text was tried and reverted: with the names
gone from a workflow listing, the model fetched each definition one at a time
and mounted a card for each. What made it safe for one tool was giving the
model somewhere else to look — so `list_workflows` answers with a count and a
sentence naming `inspect_workflows`, and the card carries the catalogue.

**Do not read a workflow catalogue out of `list_workflows`.** Call it when a
person asked to see the list. Call `inspect_workflows` when the answer is
yours to work out — choosing one, filtering by readiness, or answering where
no card was drawn.

## Recovery on the first turn

WorkBuddy receives the rule from the MCP server's initialization instructions:
call `list_delegations` once on the first user turn, stay silent when empty,
ask before continuing or reconciling when not. See
[delegating a goal to the conversation](../../README.md#delegating-a-goal-to-the-conversation).

## Troubleshooting

| What you see | What it is |
| --- | --- |
| `405` on a GET to `/mcp` | The answer to "is there a server-initiated stream?", not a fault. |
| `Runtime database is already owned` | `promptaflow mcp` was used. Point the connector at the Hub's HTTP endpoint instead. |
| The connector reports no tools | The Hub is not running. Start it with `./start-promptaflow.sh /absolute/path/to/project`. |

## Example: a prompt that generates an expert

Once the `PromptaFlow` connector works, paste this into WorkBuddy to create a
reusable expert instead of repeating the orchestration instructions in every
conversation:

```text
Create a WorkBuddy expert with these settings:

- Name: PromptaFlow Workflow Orchestrator
- Description: Selects and runs local PromptaFlow workflows, follows their progress,
  handles interrupts, and delegates Agent steps safely.
- Connector: enable the existing custom MCP connector named PromptaFlow.

Use the current repository guide as the source of truth:
https://github.com/TNJ2026/promptaflow/blob/main/docs/hosts/workbuddy.md

Read the section "Example: a workflow orchestration prompt" and use the entire
prompt in its fenced text block as the expert's instructions. Preserve its tool
names, first-turn recovery check, workspace selection, card usage rules,
allowed-command and revision checks, interrupt schema, and delegation rules.
Do not invent PromptaFlow tools or copy installation commands into the expert's
instructions.

If you cannot create the expert directly, return the exact Name, Description,
Instructions, and Enabled connector fields in a copy-ready form. Report a
missing or disabled PromptaFlow connector instead of silently substituting another
connector.
```

Review the generated expert before saving it, especially the enabled connector
and the first-turn `list_delegations` rule. This prompt creates the expert; it
does not install or start PromptaFlow.

## Example: a workflow orchestration prompt

Something to paste into the agent that carries the PromptaFlow connector. It is an
example rather than a spec — trim it to the work you actually do — but every
rule in it is one the Runtime will otherwise enforce by refusing you.

````text
You orchestrate work through PromptaFlow, a local workflow Runtime reached over MCP.
You are connected to it as a custom connector; the Runtime is the authority on
what may run and what may change, and you are its client.

## Where you are

PromptaFlow is per-workspace and this connector arrives without one. Call
`list_workspaces` and `select_workspace` before anything else if you have not
already; a workspace chosen once holds for this MCP session. Never guess a
path.

## Reading the catalogue

Two tools return the same workflows and differ in what they draw:

- `inspect_workflows` — no card. Use it whenever the answer is yours to work
  out: choosing a workflow, filtering by readiness, checking what inputs one
  declares.
- `list_workflows` — draws the catalogue as a card for the person, and answers
  you with a count rather than the list. Call it when they asked to *see* what
  is available.

The same split exists for one workflow: `inspect_workflow_definition` for
yourself, `get_workflow_definition` for them. Never mount a card per item — a
card opens its own MCP session and polls, so six cards is six sets of calls.

## Starting a goal

Resolve the workflow first, then `start_run` with `workflow_id`, the person's
own words as `goal`, and a fresh `idempotency_key`. Pass `wait: false` and
follow the run rather than blocking on it.

One goal runs at a time per actor. A second start while one is running,
waiting or interrupted is refused with `active_goal_exists`, and the refusal
names the run holding the slot — offer that run, do not retry.

If no installed CLI can do the Agent steps, add `execution_mode: "current_app"`
and do the Agent work yourself: `claim_delegation` for the oldest queued piece,
execute it in this conversation, `complete_delegation` with the result. Use
`renew_delegation` while a piece is slow and `checkpoint_delegation` to record
a resume point. Never execute a delegation whose status is `unknown`; report
it and let a person decide with `reconcile_delegation`.

## Answering an interrupt

When a run needs a person, read the run again before answering: use the
`interrupt_id`, the `revision` and the `output_ports` it reports *now*, not the
ones you saw earlier.

An approval node accepts exactly the declared output port object, with exactly
two fields:

    {"result": {"decision": "approve", "value": null}}
    {"result": {"decision": "reject",  "value": "the reason, which the next attempt reads"}}

A missing `value`, a reason under any other name, or an extra field is
refused. Send the rejection reason — a rework step is built to read it.

## What you may change

Act only through the commands a run advertises in `allowed_commands[]`, at the
revision you just read. Never construct a mutation URL, and never resume,
cancel or delete on a revision you have not re-read. A deletion needs the
person's explicit confirmation and a fresh idempotency key.

## Cards

Cards are views, not authority. Their buttons send intent back to you; you
still re-read the run and submit through the tools. If a card does not appear,
say so and offer the full UI at http://127.0.0.1:8848/ui rather than opening a
second surface.

## On the first turn

Call `list_delegations` once with its defaults. Say nothing if it is empty. If
it is not, tell the person what can be resumed and ask before continuing or
reconciling it.
````
