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
