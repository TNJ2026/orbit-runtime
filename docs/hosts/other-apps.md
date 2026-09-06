# Orbit from any other MCP-capable App

[简体中文](./other-apps.zh-CN.md) | **English** · [Hosts](./README.md) · [Orbit](../../README.md)

| | |
| --- | --- |
| Reaches Orbit through | Orbit's stdio proxy |
| Registers as | its own stable name |
| Draws Orbit's cards | host-dependent |
| Event tools | the proxy's `wait_app_event`, `list_app_events`, `ack_app_event` |

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

## Recovery on the first turn

Runs outlive conversations, so check for resumable work on the first user turn
of each conversation: call `list_delegations` once with its default statuses,
say nothing when it is empty, and ask before continuing or reconciling when it
is not. An `unknown` delegation is never executed again. See
[delegating a goal to the conversation](../../README.md#delegating-a-goal-to-the-conversation).

## Whether the card appears

What the five cards are is in [the cards](../cards.md).

Orbit publishes its dashboard as an MCP App (the MCP Apps extension,
SEP-1865): the resource carries the mime type `text/html;profile=mcp-app` and
is bound to the tool through `_meta.ui.resourceUri`. There is nothing
host-specific in that — a host implementing MCP Apps mounts the card in a
sandboxed iframe, and one that does not shows only the JSON the tool returned.

The card performs the MCP Apps handshake itself, so a host that mounts it gets
a working card rather than one stuck connecting. Hosts have been reported to
fetch the resource without mounting it, so look at what actually happened: if
the card did not appear, say so and offer the full UI rather than silently
opening a second surface.
