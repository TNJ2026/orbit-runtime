# The cards

[简体中文](./cards.zh-CN.md) | **English** · [Hosts](./hosts/README.md) · [Orbit](../README.md)

Orbit ships five small pages that a host can draw beside the conversation.
They are MCP Apps (the MCP Apps extension, SEP-1865): each is published as an
MCP resource with the mime type `text/html;profile=mcp-app`, and each is bound
to the tool that opens it through `_meta.ui.resourceUri`.

## How to open one

Call the tool. There is no separate "open the card" call — the card is the
tool's `_meta`, so a host that implements MCP Apps mounts it in a sandboxed
iframe when the tool answers, and a host that does not shows only the JSON the
tool returned. Whether anything is drawn is the host's decision, not Orbit's,
so treat the visible surface as a separate question from the call.

| Call this | and this card appears | showing |
| --- | --- | --- |
| `open_orbit_dashboard` | Orbit dashboard | the workspace: workflows, history, agents |
| `list_workflows` | Orbit workflows | the published catalogue |
| `get_workflow_definition` | Orbit workflows | the same card, opened on one workflow |
| `generate_workflow` | Orbit workflow generation | one authoring job's progress and result |
| `start_run` | Orbit goal execution | that run's steps, attention state and result |
| `open_orbit_goals` | Orbit goals | recent goal runs and their status |

Pick the card from the intent rather than opening the dashboard first: a
request to see the workflows is `list_workflows`, and a request to run a goal
is `start_run`. Opening Orbit itself is `open_orbit_dashboard`.

## What each one is

![The Orbit dashboard card, on its History tab](./images/cards/dashboard.png)

**Orbit dashboard.** Four tabs — Goal, Workflows, History, Agents — with
**Create workflow** at the end of the tab row.

Goal is what the card opens on: everything still running, or the goal that ran
last when nothing is, with its steps, whatever it still offers to do, and its
outcome. A goal reaching its end is the moment its result matters most, so a
finished one holds the page until the next one starts rather than vanishing
into an empty screen. With nothing ever run, the page says so.

History is the same project's goal runs, all of them, grouped by day; opening
one shows the same thing the Goal page shows for a single run.

![The Orbit workflows card](./images/cards/workflows.png)

**Orbit workflows.** The published catalogue, with **New goal** on each row.
Selecting a row switches the same card to that workflow's detail — the graph,
the definition list, and **New goal**, **Modify**, **Delete** — rather than
opening a second card.

![The workflow generation card](./images/cards/workflow-generation.png)

**Orbit workflow generation.** One authoring job: queued, generating,
generated or failed, with the requirement it was given.

![The goal execution card](./images/cards/goal-execution.png)

**Orbit goal execution.** One run: its steps, whether a person is needed, and
its result.

![The goals card](./images/cards/goals.png)

**Orbit goals.** Recent runs and their current status, as a list.

Every card follows the host's locale — its labels, its empty states and the
prompts it sends back. The host's own language wins when it sends one, and the
browser's is the guess until it does; a card repaints when the host changes
it mid-session.

## Cards are views, not authority

A card's actions send intent back to the conversation; they do not mutate the
Runtime. When someone presses Approve, the card asks the Agent to submit the
declared output object — and the Agent must re-read the run, use its current
`interrupt_id`, `revision` and `allowed_commands[]`, and never construct a
mutation URL. The full browser UI at `/ui` owns catalogues, history, graphs,
logs and workflow management; a card shows the task that currently matters.

## Why a card sometimes looks stale

Hosts cache MCP App resources by URI. Every card's URI carries a version —
`ui://orbit/current-task-v45.html`, `ui://orbit/workflows-v22.html` — and
changing a card means publishing it under a new one, because a host that has
already fetched the old URI will keep rendering the previous document.

The consequence for a user is small but real: **after upgrading Orbit, start a
new conversation.** A session that has already mounted a card keeps the copy
it fetched.

## Regenerating these images

```bash
.venv/bin/python scripts/screenshot-cards.py
```

The screenshots are driven by fixture data in that script rather than by a
running Runtime, for two reasons: a picture of a real catalogue carries
whatever its operator was working on into the repository, and a picture of
live data differs every time it is taken, so the diff of a regenerated image
would say nothing about whether the card changed. The clock is pinned too, so
"just now" and "Today" mean the same thing on every machine.

Each shot is refitted to what its card actually holds before it is taken —
capped where the card caps, so a list longer than the card is still shown as
the scrolling list it is.
