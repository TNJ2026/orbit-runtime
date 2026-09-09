# 在 WorkBuddy 中使用 PromptaFlow

**简体中文** | [English](./workbuddy.md) · [宿主](./README.zh-CN.md) · [PromptaFlow](../../README.zh-CN.md)

| | |
| --- | --- |
| 接入方式 | 自定义连接器，HTTP 直连 Hub |
| 注册名 | `promptaflow`，以及 `workbuddy-third-party:custom-mcp:promptaflow` |
| 是否绘制 PromptaFlow 卡片 | 是 |
| 事件工具 | Runtime 的 `list_runtime_events` |

## 从仓库配置连接器

WorkBuddy 没有专用插件，也没有 Proxy。PromptaFlow 在本地运行，WorkBuddy 通过自定义 HTTP MCP
连接器直连它的回环 Hub。

### 使用简单提示词配置

把下面这句话交给能够读取公开仓库并运行本地命令的 WorkBuddy Agent：

```text
请从这个仓库为 WorkBuddy 配置 PromptaFlow 连接器：https://github.com/TNJ2026/promptaflow
```

Agent 应通过仓库的宿主索引找到本文，安装并启动 PromptaFlow、检查端点，然后引导你完成它无法
代替操作的连接器设置。

### 1. 检查前置条件

- Git 和 `uv`。
- Python 3.10 或更高版本。
- 支持自定义 Streamable HTTP MCP 连接器的 WorkBuddy 版本。
- 使用仓库启动脚本时需要 Bash；Windows 请使用 Git Bash 或 Agent 能找到的其他 Bash。

### 2. 克隆并安装 PromptaFlow

把 checkout 保存在稳定目录：

```bash
git clone https://github.com/TNJ2026/promptaflow.git /绝对路径/稳定目录/promptaflow
uv tool install /绝对路径/稳定目录/promptaflow
uv tool update-shell
promptaflow --version
```

如果 checkout 已存在，请先检查并保留本地修改。干净的 checkout 可用 `git pull --ff-only`
更新，再运行 `uv tool install --force /绝对路径/稳定目录/promptaflow` 刷新已安装工具。

### 3. 为目标项目启动 PromptaFlow

把需要拥有 Runtime 的项目路径交给仓库启动脚本：

```bash
/绝对路径/稳定目录/promptaflow/start-promptaflow.sh /绝对路径/目标项目
```

然后检查发现结果：

```bash
promptaflow runtimes --json
```

打开 `http://127.0.0.1:8848/ui`，其中应列出目标 Workspace。请保留该 checkout，因为启动
脚本和 Agent App manifest 都属于本安装的一部分。

### 4. 添加 WorkBuddy 连接器

在 WorkBuddy 中打开连接器或 MCP 设置，添加自定义 Streamable HTTP 连接器。不同版本的
界面名称可能略有差异，请填写以下值：

| 字段 | 值 |
| --- | --- |
| 名称 | `promptaflow` |
| MCP URL | `http://127.0.0.1:8848/mcp` |
| 传输方式 | Streamable HTTP |
| 认证 | 无 |

保存连接器，并为目标 Agent 或对话启用它。不要配置远程 URL：PromptaFlow Hub 有意只监听回环
地址。

### 5. 验证连接

1. 确认 WorkBuddy 显示 `promptaflow` 连接器提供的工具。
2. 让它调用 `list_workspaces`。
3. 如果返回多个 Workspace，用 `select_workspace` 选择目标项；绝不要猜路径。
4. 让它显示 PromptaFlow 工作流或打开 PromptaFlow，确认卡片能够渲染。

不需要凭据：Hub 只在回环地址上，而回环上的调用方本来就是操作者。WorkBuddy 使用
Streamable HTTP（`accept: application/json, text/event-stream`），以协议
`2025-11-25` 与 PromptaFlow 的 `2025-06-18` 协商并接受。它还会对该端点发起一个 GET
以寻找服务端推流；返回的 `405` 是**答案**，不是故障。

**不要在这里用 `promptaflow mcp`。** 它的 stdio 传输虽然是 WorkBuddy 自家文档描述的形状，
但它启动的进程要的是 Hub 所管理的 Runtime 已经持有的项目数据库，会以
`Runtime database is already owned` 退出，而不是共享。

### 升级或移除

升级时更新干净的 checkout、重新安装工具，再为目标项目运行启动脚本：

```bash
cd /绝对路径/稳定目录/promptaflow
git pull --ff-only
uv tool install --force /绝对路径/稳定目录/promptaflow
./start-promptaflow.sh /绝对路径/目标项目
```

连接器 URL 不变，因此通常无需修改 WorkBuddy 设置。如果它仍保留旧工具目录，请重新连接
或重启 WorkBuddy。

移除集成时，在 WorkBuddy 中禁用或删除 `PromptaFlow` 自定义连接器。这不会删除 Runtime 数据。
请通过 **停止 PromptaFlow** 控件或你启动的精确 Runtime 进程单独停止 PromptaFlow；不要把删除
`~/.promptaflow` 当成卸载方式。

WorkBuddy 会挂载 PromptaFlow 的卡片，而**每张挂载的卡片都会开自己的 MCP 会话**并调用它需要
的工具——所以一个对话里挂着六张卡，就是六套这样的调用。有一个工具为此做了特别处理：
`list_workflows` 把目录画成卡片，正文只回一个计数，所以当「答案是你要自己算出来的」
而不是「给人看的」时候，请改用 `inspect_workflows` 读目录。
`get_workflow_definition` 和 `inspect_workflow_definition` 是同样的一对。

## 为什么它有两个名字

WorkBuddy 从连接器设置里自报 `workbuddy-third-party:custom-mcp:promptaflow`，而连接器被加载进
某个 agent 之后自报的是朴素的 `promptaflow`，所以同一个 App 会因为「是它自己的哪条路径发起的调用」
而以两个名字出现。两个都不遮蔽已发现的 CLI，所以两个都不会被拒 —— 这正是 `-app` 后缀存在
的那条规则，而 WorkBuddy 是那个说明「规则是关于 Agent 而不是关于整洁」的例外。

## 挂载卡片的代价

每个工具打开哪张卡，见[卡片](../cards.zh-CN.md)。

WorkBuddy 完整地挂载 PromptaFlow 的 MCP App 卡片：列出资源、请求
`resources/templates/list`、再读取工具通过 `_meta.ui.resourceUri` 点名的那一个并绘制。
由此有两个后果。

**每张卡自己取数据。** 挂载的卡片会开自己的 MCP 会话并调用它需要的工具 —— workspace 卡片
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
| `Runtime database is already owned` | 用了 `promptaflow mcp`。把连接器指向 Hub 的 HTTP 端点。 |
| 连接器报告没有工具 | Hub 没在跑。用 `./start-promptaflow.sh /absolute/path/to/project` 启动。 |

## 示例：生成专家的提示词

`promptaflow` 连接器验证可用后，把下面的范文交给 WorkBuddy，即可生成一个可复用的专家，不必在
每次对话中重复编排规则：

```text
请创建一个 WorkBuddy 专家，配置如下：

- 名称：PromptaFlow 工作流编排专家
- 描述：选择并运行本地 PromptaFlow 工作流、跟踪运行、处理人工中断，并安全地接手 Agent 步骤。
- 连接器：启用现有的、名为 PromptaFlow 的自定义 MCP 连接器。

以仓库中的最新指南为唯一依据：
https://github.com/TNJ2026/promptaflow/blob/main/docs/hosts/workbuddy.zh-CN.md

读取其中的「示例：一份工作流编排提示词」一节，把该节代码块中的完整提示词作为专家指令。
保留所有工具名、首轮恢复检查、Workspace 选择、卡片使用规则、allowed_commands 与 revision
检查、中断响应格式和委托规则。不要虚构 PromptaFlow 工具，也不要把安装命令写进专家指令。

如果你不能直接创建专家，请按可直接复制的格式输出准确的「名称、描述、专家指令、已启用
连接器」四项配置。若 PromptaFlow 连接器缺失或未启用，请明确报告，不要静默换成其他连接器。
```

保存前请检查生成结果，尤其是已启用的连接器，以及首轮调用 `list_delegations` 的规则。这段
提示词只负责生成专家，不负责安装或启动 PromptaFlow。

## 示例：一份工作流编排提示词

可以直接粘进那个挂着 PromptaFlow 连接器的 agent。这是**示例不是规范** —— 按你实际要做的事
裁剪它 —— 但里面每一条规则，Runtime 都会用「拒绝你」的方式来执行。

````text
你通过 PromptaFlow 编排工作。PromptaFlow 是一个通过 MCP 接入的本地工作流 Runtime，你以自定义
连接器的身份连着它。**什么能跑、什么能改，由 Runtime 说了算，你是它的客户端。**

## 你在哪儿

PromptaFlow 按 workspace 划分，而这个连接器接进来时并不带 workspace。如果还没选过，先调
`list_workspaces` 和 `select_workspace`；选定后在本 MCP 会话内一直有效。**绝不要猜路径。**

## 读目录

有两个工具返回同一批工作流，区别在于画不画卡片：

- `inspect_workflows` —— 不画卡。**答案要由你自己算出来时用它**：挑一个工作流、
  按就绪状态过滤、看它声明了哪些输入。
- `list_workflows` —— 把目录画成卡片给人看，回给你的只是一个计数而不是列表。
  **对方明确说「看看有哪些」时才调它。**

单个工作流也是同一组区分：给自己看用 `inspect_workflow_definition`，给人看用
`get_workflow_definition`。**绝不要一个条目挂一张卡** —— 每张卡会开自己的 MCP 会话并
轮询，六张卡就是六套调用。

## 启动目标

先把工作流定下来，再 `start_run`：带 `workflow_id`、把**对方自己的原话**作为 `goal`、
一个新的 `idempotency_key`。传 `wait: false`，然后去跟进这次 run，而不是卡在那儿等。

**每个 actor 同时只跑一个目标。** 已有 running / waiting / interrupted 的 run 时再启动会
以 `active_goal_exists` 被拒，拒绝里会带上占着槽位的那个 run —— 把那个 run 指给对方，
不要重试。

如果没有已安装的 CLI 能承担 Agent 步骤，就加上 `execution_mode: "current_app"`，由你自己
来做 Agent 的活：`claim_delegation` 领最早排队的那件，在本对话里执行，然后
`complete_delegation` 交结果。慢的时候用 `renew_delegation` 续租，用
`checkpoint_delegation` 记录恢复点。**状态为 `unknown` 的委托绝不重跑** —— 报出来，
让人用 `reconcile_delegation` 定夺。

## 回应中断

run 需要人处理时，**回答前重新读一次这个 run**：用它**此刻**报告的 `interrupt_id`、
`revision` 和 `output_ports`，不是你之前看到的那些。

审批节点只接受已声明的输出端口对象，且**只有两个字段**：

    {"result": {"decision": "approve", "value": null}}
    {"result": {"decision": "reject",  "value": "原因，下一次尝试会读它"}}

缺 `value`、把原因放在别的字段名下、或者多带一个字段，都会被拒。**拒绝时要写原因** ——
返工步骤就是为读它而建的。

## 你能改什么

只能通过 run 在 `allowed_commands[]` 里公布的命令去操作，并且用**你刚读到的那个
revision**。绝不自行拼接写操作 URL；绝不在没重新读过的 revision 上 resume、cancel 或
delete。删除需要对方**明确确认**，外加一个新的幂等键。

## 卡片

**卡片是视图，不是权限。** 上面的按钮只是把意图送回给你；你仍然要重新读 run 并通过工具
提交。如果卡片没出现，就说出来，并提供完整 UI（http://127.0.0.1:8848/ui），不要另开
一个界面。

## 每个对话的第一轮

用默认参数调一次 `list_delegations`。空的就什么都别说。非空就告诉对方有什么可以恢复，
并在继续或裁决之前先问。
````
