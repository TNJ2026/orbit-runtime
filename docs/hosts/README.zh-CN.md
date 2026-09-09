# 宿主

PromptaFlow 是一个 Runtime，但有好几扇前门。每个宿主接入方式不同、注册的客户端名不同，
是否绘制 PromptaFlow 的卡片、能看到哪些工具也不同。这几页之外的东西 —— 运行目标、把目标
委托给对话、事件、输出、CLI —— 无论从哪儿接入都一样，写在
[主 README](../../README.zh-CN.md) 里。卡片本身是什么、每张由哪个工具打开，
见[卡片](../cards.zh-CN.md)。

**简体中文** | [English](./README.md)

| 宿主 | 怎么接到 PromptaFlow | 注册名 | 是否绘制卡片 |
| --- | --- | --- | --- |
| [Codex app](./codex-app.zh-CN.md) | 随插件分发的 stdio Proxy → Hub | `codex-app` | 是 |
| [WorkBuddy](./workbuddy.zh-CN.md) | 自定义连接器，HTTP 直连 Hub | `orbit`，以及 `workbuddy-third-party:custom-mcp:orbit` | 是 |
| [DeepSeek Harness](./deepseek-harness.zh-CN.md) | 带自有 Gateway 与面板的 Host Profile Bundle | 按 Session 的 `harness:session:*` actor | 自己的面板 |
| [其他 MCP App](./other-apps.zh-CN.md) | stdio Proxy | 自己的稳定名称 | 取决于宿主 |

客户端名不得遮蔽已发现的 CLI。Runtime 会把已安装的 CLI 发现为 `codex`、`claude` 等
Agent，所以 App 用其中之一注册会被**直接拒绝**而不是改名 —— `-app` 后缀就是为此存在的。

**被列出不等于被选中。** 已连接的 App 名字**故意**排在已发现的 CLI 之下 —— fork 出来的
CLI 会真的跑，而一个挂起的提问只是等，可能永远没人答 —— 所以 Runtime 不会把任何 App 设为
默认撰写者。请在 UI 的 **Written by** 里自己选那个客户端名。
