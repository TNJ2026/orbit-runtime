# 在 Codex app 中使用 Orbit

**简体中文** | [English](./codex-app.md) · [宿主](./README.zh-CN.md) · [Orbit](../../README.zh-CN.md)

| | |
| --- | --- |
| 接入方式 | 插件自带的 stdio Proxy → 本地 Hub |
| 注册名 | `codex-app` |
| 是否绘制 Orbit 卡片 | 是 |
| 事件工具 | Proxy 的 `wait_app_event`、`list_app_events`、`ack_app_event` |

从对应的 GitHub Release 下载 `orbit-marketplace-<版本>.zip`，然后执行：

```bash
unzip orbit-marketplace-<版本>.zip
codex plugin marketplace add ./orbit-marketplace
codex plugin add orbit@orbit-local
```

也可以先添加解压后的 Marketplace 目录，再从 Codex 插件界面安装：

1. 打开 Codex App 的 **Plugins**。
2. 在 **Orbit Local** 中找到 **Orbit**，点击 **Install**。
3. 新建一个 Codex 任务，让新安装的 Skill 和 MCP 工具生效。
4. 打开需要运行工作流的目标项目。
5. 告诉 Codex：`打开 Orbit`。

插件自带 MCP Proxy，插件宿主会把 `ORBIT_AGENT_APP_WORKSPACE` 设为当前打开的项目。
Proxy 把这个 workspace 注册到 8848 端口的本地 Hub，并使用它的 workspace 级 MCP
地址；Hub 为该 workspace 启动或发现一个动态端口的 Runtime。Orbit 必须获得明确的
项目目录，绝不会把进程碰巧所在的目录当作项目——没有项目的聊天会使用
`ORBIT_DEFAULT_WORKSPACE`（若已配置），否则用 `~/.orbit/workspaces/default`。

「打开 Orbit」会启动或复用 Runtime，并在对话旁打开原生面板。它**只是展示**：不会把
本 App 注册为撰写者，也不会开始监听撰写请求。需要的话请明说，Codex 才会调用
`wait_authoring_request(client="codex-app")`——在 Codex 下，一个挂起的调用旁边的人
仍可继续工作，且任务活跃期间会自动续听。任务结束后 `codex-app` 离线，Runtime 继续运行。

点击刷新按钮右侧的 **停止 Orbit** 并确认，会结束当前项目的 Runtime、Worker、
定时器、MCP 端点和事件连接。

## 各部分怎么拼起来

8848 上的 Hub 是**公开的 MCP 网关，不是透明代理**。它掌管 MCP 协议生命周期和 App 资源；
它背后的 workspace Runtime 暴露的是私有的 Agent 工具后端，并且对工具权限、工作流状态和
`allowed_commands[]` 仍然是权威。生产环境下每个 workspace Runtime 还会启动一个带鉴权的
本地 Execution Worker 来持有真正的 Handler adapter —— 控制面负责编译和推进 LangGraph，
Handler 的调用与取消则跨过那道私有边界。

8848 端口属于 Hub。workspace Runtime 使用发现到的动态端口，彼此隔离。

## 什么时候挂起监听调用

打开 Orbit 不注册任何东西。`wait_authoring_request` 会把任务停在那里，直到有人在 Orbit UI
里点「生成」——所以只在这确实是被要求的事情时才挂起它。在 Codex 下，挂起的调用旁边的人
仍然可以继续工作，这也是它在任务存活期间会自动续听的原因。

如果只想「可被选为撰写者」而不认领工作，`register_authoring_client` 把同一个地址标记为
在线十分钟，再调一次即可续期。

## 对话第一轮的恢复检查

规则写在 MCP 服务器的初始化指令里：每个对话的第一个用户轮次，用默认状态调用一次
`list_delegations`。空的就闭嘴；非空就说明有什么可以恢复，并在继续或裁决之前先问。
`unknown` 的委托**永不重跑**。参见
[把目标委托给当前对话执行](../../README.zh-CN.md#把目标委托给当前对话执行)。

## 什么都连不上时

手动启动 Hub，然后打开它打印的 workspace 地址：

```bash
./start-orbit.sh /absolute/path/to/project
```
