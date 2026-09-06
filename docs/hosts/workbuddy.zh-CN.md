# 在 WorkBuddy 中使用 Orbit

**简体中文** | [English](./workbuddy.md) · [宿主](./README.zh-CN.md) · [Orbit](../../README.zh-CN.md)

| | |
| --- | --- |
| 接入方式 | 自定义连接器，HTTP 直连 Hub |
| 注册名 | `orbit`，以及 `workbuddy-third-party:custom-mcp:orbit` |
| 是否绘制 Orbit 卡片 | 是 |
| 事件工具 | Runtime 的 `list_runtime_events` |

没有插件，也没有 Proxy。添加一个自定义连接器，直接指向 Hub 的 HTTP 地址：

```text
http://127.0.0.1:8848/mcp
```

不需要凭据：Hub 只在回环地址上，而回环上的调用方本来就是操作者。WorkBuddy 使用
Streamable HTTP（`accept: application/json, text/event-stream`），以协议
`2025-11-25` 与 Orbit 的 `2025-06-18` 协商并接受。它还会对该端点发起一个 GET
以寻找服务端推流；返回的 `405` 是**答案**，不是故障。

**不要在这里用 `orbit mcp`。** 它的 stdio 传输虽然是 WorkBuddy 自家文档描述的形状，
但它启动的进程要的是运行中的 Hub 或 `orbit serve` 已经持有的项目数据库，会以
`Runtime database is already owned` 退出，而不是共享。

WorkBuddy 会挂载 Orbit 的卡片，而**每张挂载的卡片都会开自己的 MCP 会话**并调用它需要
的工具——所以一个对话里挂着六张卡，就是六套这样的调用。有一个工具为此做了特别处理：
`list_workflows` 把目录画成卡片，正文只回一个计数，所以当「答案是你要自己算出来的」
而不是「给人看的」时候，请改用 `inspect_workflows` 读目录。
`get_workflow_definition` 和 `inspect_workflow_definition` 是同样的一对。

## 为什么它有两个名字

WorkBuddy 从连接器设置里自报 `workbuddy-third-party:custom-mcp:orbit`，而连接器被加载进
某个 agent 之后自报的是朴素的 `orbit`，所以同一个 App 会因为「是它自己的哪条路径发起的调用」
而以两个名字出现。两个都不遮蔽已发现的 CLI，所以两个都不会被拒 —— 这正是 `-app` 后缀存在
的那条规则，而 WorkBuddy 是那个说明「规则是关于 Agent 而不是关于整洁」的例外。

## 挂载卡片的代价

WorkBuddy 完整地挂载 Orbit 的 MCP App 卡片：列出资源、请求
`resources/templates/list`、再读取工具通过 `_meta.ui.resourceUri` 点名的那一个并绘制。
由此有两个后果。

**每张卡自己取数据。** 挂载的卡片会开自己的 MCP 会话并调用它需要的工具 —— dashboard 卡片
会轮询 `list_runs` 和 `list_authoring_jobs` —— 所以一个对话里挂着六张卡，就是六套这样的
调用；一个「每个条目挂一张卡」的工具会把整个记录塞满。

**工具返回的正文是给模型读的，不只是给宿主画的。** 曾经把所有绑卡工具的正文都缩短，
结果被回滚了：工作流列表里没有名字之后，模型开始一个一个去取定义，每取一个挂一张卡。
让其中一个工具敢这么做的前提，是给模型另一个去处 —— 所以 `list_workflows` 只回一个计数
和一句「用 `inspect_workflows`」，目录由卡片承载。

**不要从 `list_workflows` 里读工作流目录。** 人要求看列表时才调它；当答案是你自己要算出来
的（挑一个、按就绪状态过滤、或者宿主根本没画卡片）时，调 `inspect_workflows`。

## 对话第一轮的恢复检查

WorkBuddy 从 MCP 服务器的初始化指令里收到这条规则：第一个用户轮次调用一次
`list_delegations`，空则不说话，非空则在继续或裁决前先问。参见
[把目标委托给当前对话执行](../../README.zh-CN.md#把目标委托给当前对话执行)。

## 排查

| 你看到的 | 它是什么 |
| --- | --- |
| 对 `/mcp` 发 GET 得到 `405` | 这是「有没有服务端推流」这个问题的**答案**，不是故障。 |
| `Runtime database is already owned` | 用了 `orbit mcp`。把连接器指向 Hub 的 HTTP 端点。 |
| 连接器报告没有工具 | Hub 没在跑。用 `./start-orbit.sh /absolute/path/to/project` 启动。 |
