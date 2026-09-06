# 从其他支持 MCP 的 App 使用 Orbit

**简体中文** | [English](./other-apps.md) · [宿主](./README.zh-CN.md) · [Orbit](../../README.zh-CN.md)

| | |
| --- | --- |
| 接入方式 | Orbit 的 stdio Proxy |
| 注册名 | 自己的稳定名称 |
| 是否绘制 Orbit 卡片 | 取决于宿主 |
| 事件工具 | Proxy 的 `wait_app_event`、`list_app_events`、`ack_app_event` |

通过 Orbit 的 stdio Proxy 连接。根据目标 App 的 MCP 配置格式调整以下示例：

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

Proxy 请求本地 Hub 注册这个绝对 workspace 路径，它自己不写 Hub 注册表。它的事件收件箱
默认放在该 workspace 的 `.orbit/agent-apps/` 目录下，所以被沙箱限制的 App 只需要对选定
的 workspace 有写权限。要放到别处，显式设置 `AGENT_APP_STATE_DIR`。

App 必须保持下面的调用处于等待状态，才会被 Orbit 识别为当前在线 Agent：

```text
wait_authoring_request(client="claude-desktop", timeout_seconds=300)
```

Orbit 随后显示 `app:claude-desktop`。仅连接 MCP 不会注册在线 App——是这个等待调用让它
可被寻址。被请求撰写 Workflow 的 App 用 `submit_authoring_response` 提交 DSL，并通过
`get_authoring_job` 处理编译反馈。

**被列出不等于被选中。** 已连接的 App 名字**故意**排在已发现的 CLI 之下——fork 出来的
CLI 会真的跑，而一个挂起的提问只是等，可能永远没人答——所以 Runtime 不会把任何 App 设为
默认撰写者。请在 UI 的 **Written by** 里自己选那个客户端名。

## 对话第一轮的恢复检查

Run 的寿命长于对话，所以在每个对话的第一个用户轮次检查有没有可恢复的工作：用默认状态调用
一次 `list_delegations`，空则不说话，非空则在继续或裁决之前先问。`unknown` 的委托**永不重跑**。
参见 [把目标委托给当前对话执行](../../README.zh-CN.md#把目标委托给当前对话执行)。

## 卡片会不会出现

五张卡分别是什么，见[卡片](../cards.zh-CN.md)。

Orbit 把它的面板作为 MCP App 发布（MCP Apps 扩展，SEP-1865）：资源的 mime type 是
`text/html;profile=mcp-app`，并通过 `_meta.ui.resourceUri` 绑定到工具上。这里没有任何
宿主相关的东西 —— 实现了 MCP Apps 的宿主会把卡片挂进沙箱 iframe，没实现的则只显示工具
返回的 JSON。

卡片自己完成 MCP Apps 握手，所以挂载它的宿主拿到的是一张能用的卡，而不是一张卡在「连接中」
的卡。但也有宿主被观察到**只取资源却不挂载**，所以请看实际发生了什么：如果卡片没出现，
就说出来并提供完整 UI，而不要悄悄开第二个界面。
