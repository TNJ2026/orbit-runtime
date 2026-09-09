# Hosts

PromptaFlow is one Runtime with several front doors. Each host reaches it
differently, registers under its own client name, and differs in whether it
draws PromptaFlow's cards and which tools it can see. Everything outside these
pages — running a goal, delegating one to the conversation, events, output,
the CLI — is the same wherever you connect from, and lives in the
[main README](../../README.md). What the cards themselves are, and which
tool opens each, is in [the cards](../cards.md).

[简体中文](./README.zh-CN.md) | **English**

| Host | How it reaches PromptaFlow | Registers as | Draws the card |
| --- | --- | --- | --- |
| [Codex app](./codex-app.md) | bundled plugin, stdio proxy → Hub | `codex-app` | yes |
| [WorkBuddy](./workbuddy.md) | custom connector, HTTP straight at the Hub | `promptaflow`, and `workbuddy-third-party:custom-mcp:promptaflow` | yes |
| [DeepSeek Harness](./deepseek-harness.md) | Host Profile Bundle with its own Gateway and panel | per-Session `harness:session:*` actor | its own panel |
| [Any other MCP App](./other-apps.md) | stdio proxy | its own stable name | host-dependent |

A client name may not shadow a discovered CLI. The Runtime finds installed
CLIs as the Agents `codex`, `claude` and others, so an App registering as one
of those is refused rather than renamed — which is what the `-app` suffix is
for.

Being listed is not being selected. Connected App names sit underneath the
discovered CLIs deliberately — a forked CLI runs, while a parked prompt only
waits and may never be answered — so the Runtime names no App as its default
writer. Pick the client name in the UI's **Written by** field.
