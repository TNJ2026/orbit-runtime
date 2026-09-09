# 在 Codex app 中使用 PromptaFlow

**简体中文** | [English](./codex-app.md) · [宿主](./README.zh-CN.md) · [PromptaFlow](../../README.zh-CN.md)

| | |
| --- | --- |
| 接入方式 | 插件自带的 stdio Proxy → 本地 Hub |
| 注册名 | `codex-app` |
| 是否绘制 PromptaFlow 卡片 | 是 |
| 事件工具 | Proxy 的 `wait_app_event`、`list_app_events`、`ack_app_event` |

## 安装仓库/个人插件

PromptaFlow 通过每个 [GitHub Release](https://github.com/TNJ2026/orbit/releases) 附带的本地
Marketplace 压缩包分发。安装后只对当前用户生效，不会把 PromptaFlow 发布到公共 Plugins
Directory。

### 使用提示词安装

把下面的提示词粘贴到一个 Codex 任务中即可。Codex 会读取仓库里持续维护的安装文档，
无需在提示词里重复所有步骤。下载 Release 或写入用户级插件配置之前，Codex 可能会请求
授权。

```text
请安装这个仓库中的 PromptaFlow Codex 插件：https://github.com/TNJ2026/orbit
```

如果要安装指定 Release，在提示词末尾加上明确版本即可，例如：`安装 PromptaFlow 0.4.0`。

### 1. 检查前置条件

继续之前请安装：

- Codex 桌面应用及其 `codex` CLI。运行 `codex plugin --help`，确认插件命令可用。
- `uv`，PromptaFlow 用它创建和维护 Python 环境。
- Bash。macOS 和 Linux 已自带；Windows 请安装 Git Bash 或其他能被 Codex 找到的 Bash。

### 2. 下载并解压 Marketplace

从对应的 Release 下载 `orbit-marketplace-<版本>.zip`。请解压到稳定目录：Codex 会一直把
该目录作为 Marketplace 源，不要把它留在临时下载目录中。

macOS 或 Linux：

```bash
mkdir -p "$HOME/.local/share/orbit-codex"
unzip orbit-marketplace-<版本>.zip -d "$HOME/.local/share/orbit-codex"
```

Windows PowerShell：

```powershell
$installRoot = Join-Path $env:LOCALAPPDATA "PromptaFlow\Codex"
New-Item -ItemType Directory -Force -Path $installRoot
Expand-Archive -Path .\orbit-marketplace-<版本>.zip -DestinationPath $installRoot -Force
```

解压后的 Marketplace 根目录必须包含以下路径：

```text
orbit-marketplace/
├── .agents/plugins/marketplace.json
└── plugins/orbit/
    ├── .codex-plugin/plugin.json
    ├── .mcp.json
    ├── start-promptaflow.sh
    └── skills/orbit/SKILL.md
```

如果解压后多出了一层目录，下一步应使用内层的 `orbit-marketplace` 目录。

### 3. 注册 Marketplace

把解压后 Marketplace 的绝对路径交给 Codex。

macOS 或 Linux：

```bash
codex plugin marketplace add "$HOME/.local/share/orbit-codex/orbit-marketplace"
codex plugin marketplace list
```

Windows PowerShell：

```powershell
codex plugin marketplace add (Join-Path $installRoot "orbit-marketplace")
codex plugin marketplace list
```

列表中应该出现名为 `orbit-local` 的 Marketplace，并指向刚添加的目录。如果已有另一个
`orbit-local` 指向其他位置，请先运行 `codex plugin marketplace remove orbit-local` 删除旧
来源，再添加正确目录。

### 4. 安装 PromptaFlow

通过 CLI 安装：

```bash
codex plugin add orbit@orbit-local
codex plugin list --marketplace orbit-local
```

列表应显示 `orbit` 已安装且已启用。也可以在注册 Marketplace 后通过界面安装：

1. 打开 Codex App 的 **Plugins**。
2. 选择 **PromptaFlow Local** 来源。
3. 找到 **PromptaFlow**，点击 **Install**。

### 5. 重启 Codex 并打开 PromptaFlow

1. 完全退出 Codex 桌面应用；只关闭窗口不够。
2. 重新打开 Codex，并新建任务，让插件的 Skill 和 MCP 工具加载。
3. 打开需要拥有工作流 Runtime 的目标项目。
4. 告诉 Codex：`打开 PromptaFlow`。
5. 确认 PromptaFlow 面板出现在对话旁边。

第一次启动可能较慢，因为 `uv` 需要创建插件虚拟环境并安装锁定的 Python 依赖。

### 升级现有安装

1. 下载新的 `orbit-marketplace-<版本>.zip`。
2. 完全退出 Codex。
3. 备份或删除旧的 `orbit-marketplace` 解压目录，再把新压缩包解压到相同位置。不要直接
   覆盖合并旧文件。
4. 重新安装并检查插件：

   ```bash
   codex plugin add orbit@orbit-local
   codex plugin list --marketplace orbit-local
   ```

5. 重新打开 Codex 并新建任务。

如果 Marketplace 路径发生变化，请先删除 `orbit-local`，添加新的绝对路径，再重新安装
PromptaFlow。

### 移除安装

```bash
codex plugin remove orbit@orbit-local
codex plugin marketplace remove orbit-local
```

命令成功后即可删除解压出的 Marketplace 目录。完全重启 Codex 后，新任务将不再加载该
插件。

### 安装问题排查

- **找不到 Marketplace：**运行 `codex plugin marketplace list`，确认注册的根目录内直接
  包含 `.agents/plugins/marketplace.json`。
- **列表里没有 PromptaFlow：**运行 `codex plugin list --available --json`，确认 `orbit` 可从
  `orbit-local` 获取，然后再次执行安装命令。
- **找不到 `bash`：**安装 Bash，并确保启动 Codex 时使用的环境能够找到它。
- **没有虚拟环境或找不到 `uv`：**安装 `uv`，然后重启 Codex，让新环境识别该程序。
- **仍然看到旧指令或旧工具：**完全退出并重新打开 Codex，再新建任务；已有任务不会重新
  加载插件元数据。

插件自带 MCP Proxy，插件宿主会把 `ORBIT_AGENT_APP_WORKSPACE` 设为当前打开的项目。
Proxy 把这个 workspace 注册到 8848 端口的本地 Hub，并使用它的 workspace 级 MCP
地址；Hub 为该 workspace 启动或发现一个动态端口的 Runtime。PromptaFlow 必须获得明确的
项目目录，绝不会把进程碰巧所在的目录当作项目——没有项目的聊天会使用
`ORBIT_DEFAULT_WORKSPACE`（若已配置），否则用 `~/.promptaflow/workspaces/default`。

「打开 PromptaFlow」会启动或复用 Runtime，并在对话旁打开原生面板。它**只是展示**：不会把
本 App 注册为撰写者，也不会开始监听撰写请求。需要的话请明说，Codex 才会调用
`wait_authoring_request(client="codex-app")`——在 Codex 下，一个挂起的调用旁边的人
仍可继续工作，且任务活跃期间会自动续听。任务结束后 `codex-app` 离线，Runtime 继续运行。

点击刷新按钮右侧的 **停止 PromptaFlow** 并确认，会结束当前项目的 Runtime、Worker、
定时器、MCP 端点和事件连接。

## 各部分怎么拼起来

8848 上的 Hub 是**公开的 MCP 网关，不是透明代理**。它掌管 MCP 协议生命周期和 App 资源；
它背后的 workspace Runtime 暴露的是私有的 Agent 工具后端，并且对工具权限、工作流状态和
`allowed_commands[]` 仍然是权威。生产环境下每个 workspace Runtime 还会启动一个带鉴权的
本地 Execution Worker 来持有真正的 Handler adapter —— 控制面负责编译和推进 LangGraph，
Handler 的调用与取消则跨过那道私有边界。

8848 端口属于 Hub。workspace Runtime 使用发现到的动态端口，彼此隔离。

## 什么时候挂起监听调用

打开 PromptaFlow 不注册任何东西。`wait_authoring_request` 会把任务停在那里，直到有人在 PromptaFlow UI
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
./start-promptaflow.sh /absolute/path/to/project
```
