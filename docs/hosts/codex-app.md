# PromptaFlow in the Codex app

[简体中文](./codex-app.zh-CN.md) | **English** · [Hosts](./README.md) · [PromptaFlow](../../README.md)

| | |
| --- | --- |
| Reaches PromptaFlow through | the bundled plugin's stdio proxy → the loopback Hub |
| Registers as | `codex-app` |
| Draws PromptaFlow's cards | yes |
| Event tools | the proxy's `wait_app_event`, `list_app_events`, `ack_app_event` |

## Install the repository/personal plugin

PromptaFlow is distributed through a local Marketplace archive attached to each
[GitHub Release](https://github.com/TNJ2026/orbit/releases). Installing this
archive registers it for the current user only; it does not publish PromptaFlow to
the public Plugins Directory.

### Install with a Codex prompt

Paste the following prompt into a Codex task. Codex will read the maintained
instructions from this repository instead of depending on installation steps
copied into the prompt. It may ask for approval before downloading the release
or writing the user-level plugin configuration.

```text
Install the PromptaFlow Codex plugin from https://github.com/TNJ2026/orbit.
```

For a specific release, add its exact version to the prompt, for example:
`Install PromptaFlow 0.4.0`.

### 1. Check the prerequisites

Install these before continuing:

- The Codex desktop app and its `codex` CLI. Confirm the plugin commands are
  available with `codex plugin --help`.
- `uv`, which creates and maintains the Python environment used by PromptaFlow.
- Bash. macOS and Linux include it; on Windows, use Git Bash or another Bash
  installation visible to Codex.

### 2. Download and extract the Marketplace

Download `orbit-marketplace-<version>.zip` from the matching release. Extract
it into a stable directory: Codex keeps this directory as the Marketplace
source, so do not leave it in a temporary download directory.

On macOS or Linux:

```bash
mkdir -p "$HOME/.local/share/orbit-codex"
unzip orbit-marketplace-<version>.zip -d "$HOME/.local/share/orbit-codex"
```

On Windows PowerShell:

```powershell
$installRoot = Join-Path $env:LOCALAPPDATA "PromptaFlow\Codex"
New-Item -ItemType Directory -Force -Path $installRoot
Expand-Archive -Path .\orbit-marketplace-<version>.zip -DestinationPath $installRoot -Force
```

The extracted Marketplace root must contain all of these paths:

```text
orbit-marketplace/
├── .agents/plugins/marketplace.json
└── plugins/orbit/
    ├── .codex-plugin/plugin.json
    ├── .mcp.json
    ├── start-promptaflow.sh
    └── skills/orbit/SKILL.md
```

If extraction creates an additional directory level, use the inner
`orbit-marketplace` directory in the next step.

### 3. Register the Marketplace

Pass the absolute extracted Marketplace path to Codex.

On macOS or Linux:

```bash
codex plugin marketplace add "$HOME/.local/share/orbit-codex/orbit-marketplace"
codex plugin marketplace list
```

On Windows PowerShell:

```powershell
codex plugin marketplace add (Join-Path $installRoot "orbit-marketplace")
codex plugin marketplace list
```

The list should include a Marketplace named `orbit-local` whose root is the
directory added above. If another `orbit-local` entry points elsewhere, remove
that stale source with `codex plugin marketplace remove orbit-local`, then add
the intended directory again.

### 4. Install PromptaFlow

Install from the CLI:

```bash
codex plugin add orbit@orbit-local
codex plugin list --marketplace orbit-local
```

The list should show `orbit` as installed and enabled. Alternatively, after
registering the Marketplace:

1. Open **Plugins** in the Codex app.
2. Select the **PromptaFlow Local** source.
3. Find **PromptaFlow** and select **Install**.

### 5. Restart Codex and open PromptaFlow

1. Fully quit the Codex desktop app; closing only its window is not enough.
2. Reopen Codex and start a new task so the installed Skill and MCP tools load.
3. Open the project that should own the workflow Runtime.
4. Ask Codex: `Open PromptaFlow`.
5. Confirm that the PromptaFlow workspace opens beside the conversation.

The first start may take longer because `uv` must create the plugin's virtual
environment and install its locked Python dependencies.

### Upgrade an existing installation

1. Download the new `orbit-marketplace-<version>.zip`.
2. Fully quit Codex.
3. Back up or remove the old extracted `orbit-marketplace` directory, then
   extract the new archive at the same path. Do not merge it over old files.
4. Reinstall and verify the plugin:

   ```bash
   codex plugin add orbit@orbit-local
   codex plugin list --marketplace orbit-local
   ```

5. Reopen Codex and start a new task.

If the Marketplace path changes, remove `orbit-local`, add the new absolute
path, and then reinstall PromptaFlow.

### Remove the installation

```bash
codex plugin remove orbit@orbit-local
codex plugin marketplace remove orbit-local
```

After those commands succeed, the extracted Marketplace directory can be
deleted. Fully restart Codex to clear the plugin from new tasks.

### Installation troubleshooting

- **Marketplace not found:** run `codex plugin marketplace list` and verify the
  registered root directly contains `.agents/plugins/marketplace.json`.
- **PromptaFlow is absent:** run `codex plugin list --available --json` and confirm
  `orbit` is available from `orbit-local`, then repeat the install command.
- **`bash` not found:** install Bash and ensure it is visible in the environment
  used to launch Codex.
- **No virtualenv or `uv` executable:** install `uv`, then restart Codex so its
  environment sees the executable.
- **Old instructions or tools remain:** fully quit Codex and create a new task
  after reopening it; an existing task does not reload plugin metadata.

The plugin ships the MCP proxy, and the plugin host sets
`ORBIT_AGENT_APP_WORKSPACE` to the open project. The proxy registers that
workspace with the loopback Hub on port 8848 and uses its workspace-scoped MCP
URL; the Hub starts or discovers a dynamic-port Runtime for it. PromptaFlow requires
an explicit project directory and never uses an incidental process working
directory — in a projectless chat it uses `ORBIT_DEFAULT_WORKSPACE` when
configured, otherwise `~/.promptaflow/workspaces/default`.

Opening PromptaFlow starts or reuses the Runtime and opens the native workspace card
beside the conversation. It is display-only: it does not register this App as
a writer and does not begin listening for authoring work. Ask for that
explicitly, and Codex calls `wait_authoring_request(client="codex-app")` —
under Codex a pending call sits beside a person who can keep working, and it
is renewed while the task is active. Ending the task removes `codex-app`; the
Runtime keeps running.

Select **Stop PromptaFlow** beside the Refresh button and confirm to stop the
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

Opening PromptaFlow registers nothing. `wait_authoring_request` parks the task
until someone presses Generate in the PromptaFlow UI, so hold it only when that is
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

## If nothing can reach PromptaFlow

Start the Hub by hand and open the workspace URL it prints:

```bash
./start-promptaflow.sh /absolute/path/to/project
```
