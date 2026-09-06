# Orbit in WorkBuddy

[简体中文](./workbuddy.zh-CN.md) | **English** · [Hosts](./README.md) · [Orbit](../../README.md)

| | |
| --- | --- |
| Reaches Orbit through | a custom connector, HTTP straight at the Hub |
| Registers as | `orbit`, and `workbuddy-third-party:custom-mcp:orbit` |
| Draws Orbit's cards | yes |
| Event tools | the Runtime's `list_runtime_events` |

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

## Why it appears under two names

WorkBuddy announces `workbuddy-third-party:custom-mcp:orbit` from the
connector settings and plain `orbit` once the connector is loaded into an
agent, so the same App shows up under two names depending on which of its own
paths made the call. Neither shadows a discovered CLI, so neither is refused —
which is the rule the `-app` suffix exists for, and WorkBuddy is the exception
that shows the rule is about Agents rather than tidiness.

## What mounting the cards costs

Which card each tool opens is in [the cards](../cards.md).

WorkBuddy mounts Orbit's MCP App cards in full: it lists the resources, asks
for `resources/templates/list`, then reads the one the tool named through
`_meta.ui.resourceUri` and draws the card. Two things follow.

Each card fetches its own data. A mounted card opens its own MCP session and
calls the tools it needs — the dashboard card polls `list_runs` and
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
| `Runtime database is already owned` | `orbit mcp` was used. Point the connector at the Hub's HTTP endpoint instead. |
| The connector reports no tools | The Hub is not running. Start it with `./start-orbit.sh /absolute/path/to/project`. |

## Example: a workflow orchestration prompt

Something to paste into the agent that carries the Orbit connector. It is an
example rather than a spec — trim it to the work you actually do — but every
rule in it is one the Runtime will otherwise enforce by refusing you.

````text
You orchestrate work through Orbit, a local workflow Runtime reached over MCP.
You are connected to it as a custom connector; the Runtime is the authority on
what may run and what may change, and you are its client.

## Where you are

Orbit is per-workspace and this connector arrives without one. Call
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
