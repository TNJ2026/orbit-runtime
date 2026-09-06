# Orbit in the Codex app

[简体中文](./codex-app.zh-CN.md) | **English** · [Hosts](./README.md) · [Orbit](../../README.md)

| | |
| --- | --- |
| Reaches Orbit through | the bundled plugin's stdio proxy → the loopback Hub |
| Registers as | `codex-app` |
| Draws Orbit's cards | yes |
| Event tools | the proxy's `wait_app_event`, `list_app_events`, `ack_app_event` |

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

## How the pieces fit

The Hub on 8848 is the public MCP Gateway, not a transparent proxy. It owns
the MCP protocol lifecycle and the App resources; the workspace Runtimes
behind it expose a private Agent-tool backend and stay authoritative for tool
permissions, workflow state and `allowed_commands[]`. Each production
workspace Runtime also starts an authenticated local Execution Worker that
holds the real Handler adapters, so the Control Runtime compiles and advances
LangGraph while Handler invocation and cancellation cross that private
boundary.

Port 8848 belongs to the Hub. Workspace Runtimes take discovered dynamic
ports and stay isolated from one another.

## Holding a listening call

Opening Orbit registers nothing. `wait_authoring_request` parks the task
until someone presses Generate in the Orbit UI, so hold it only when that is
what was asked for. Under Codex the pending call sits beside a person who can
keep working, which is why it is renewed automatically while the task lives.

To be available as a writer without claiming work, `register_authoring_client`
marks the same address present for ten minutes and is renewed by calling it
again.

## Recovery on the first turn

The MCP server's initialization instructions carry the rule: on the first user
turn of each conversation, call `list_delegations` once with its default
statuses. Say nothing when it is empty; when it is not, say what can be
resumed and ask before continuing or reconciling. An `unknown` delegation is
never executed again. See
[delegating a goal to the conversation](../../README.md#delegating-a-goal-to-the-conversation).

## If nothing can reach Orbit

Start the Hub by hand and open the workspace URL it prints:

```bash
./start-orbit.sh /absolute/path/to/project
```
