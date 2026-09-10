# PromptaFlow

<p align="center">
  <img src="./docs/images/promptaflow-banner.png" alt="PromptaFlow — 本地 Agent 工作流 Runtime" width="100%">
</p>

**简体中文** | [English](./README.md)

PromptaFlow 把一个目标变成持久、可检查的 Agent 工作流。描述你想完成的工作，让 Agent
生成静态 Workflow DSL，检查并发布，然后通过已安装的 Agent CLI 或当前对话执行它。

## 功能

- 根据自然语言要求生成、修改和复用工作流。
- 先校验静态 Workflow DSL，再由可信编译器编译成 LangGraph，不直接执行 Agent 生成的程序。
- 在已注册的 Agent CLI 上运行步骤，支持分支、条件、重试、审批和其他人工中断。
- 持久保存工作流版本、运行进度、控制台输出和生成的 Artifact，随时可以检查。
- 通过浏览器工作台、HTTP API、MCP 工具和五张 MCP App 卡片使用同一套工作流。
- 按 Workspace 隔离执行状态，同时在本机共享已发布的工作流库和可复用源码模板。

## 架构与实现

固定在 `127.0.0.1:8848` 的本地 **Hub** 是统一入口。它选择 Workspace，并把 MCP、API
和 UI 流量路由到该 Workspace 的 **Control Runtime**；Control Runtime 持有图状态、权限和
作为唯一操作依据的 `allowed_commands[]`。每个 Runtime 通过带鉴权的 **Execution Worker**
运行 Agent CLI 等可信 Handler。工作流定义编译为 LangGraph，持久状态保存在
`~/.promptaflow/projects/`。

```text
Agent App / 浏览器 / API
           │
           ▼
 Hub :8848（MCP Gateway）
           │
           ▼
 Workspace Control Runtime ──► Execution Workers ──► Agent CLI / Handler
           │
           └── LangGraph 状态、运行记录与 Artifact
```

## 从 Orbit 升级

本项目原名 Orbit,这次改名是彻底切断:Orbit 安装留下的任何东西都不会被读取、转换或迁移。

- 状态目录是 `~/.promptaflow`。已有的 `~/.orbit` 永远不会被打开——其中的项目、Hub
  注册表、工作区和工作流库都不会带过来,首次运行看起来就是一次全新安装。
- 项目内状态在 `<project>/.promptaflow`。已有的 `<project>/.orbit` 原样留着,包括
  其中的 worktree。
- 发行名是 `promptaflow`,命令是 `promptaflow`(简写 `paf`),MCP server 名为
  `promptaflow`——因此所有工具的全限定名从 `mcp__orbit__*` 变为 `mcp__promptaflow__*`,
  另有两个卡片工具改名为 `open_promptaflow_dashboard` 和 `open_promptaflow_goals`。
  请重新连接每一个 Agent App 并重装插件;Orbit 时期缓存的工具列表解析不到。
- PyPI 上的 `orbit-runtime` 不再更新。安装本项目前请先
  `uv tool uninstall orbit-runtime`。

工作区通过在各项目里重新跑一次 goal 来重新注册。旧目录留着或删掉都随你,这边不会去读它们。

## 安装

PromptaFlow 需要 Python 3.10 或更高版本，以及
[uv](https://docs.astral.sh/uv/)。

### 使用提示词安装

把下面这句话发给受支持的 Agent App。Agent 会读取仓库里持续维护的文档，并为当前 App
选择正确的安装方式：

```text
请为当前 App 安装这个仓库中的 PromptaFlow：https://github.com/TNJ2026/promptaflow
```

各 App 的详细文档：

- [Codex app](./docs/hosts/codex-app.zh-CN.md)
- [WorkBuddy](./docs/hosts/workbuddy.zh-CN.md)
- [DeepSeek Harness](./docs/hosts/deepseek-harness.zh-CN.md)

### 从源码运行

```bash
git clone https://github.com/TNJ2026/promptaflow.git
cd promptaflow
uv sync --extra dev
uv run promptaflow serve
```

统一的 `serve` 命令会复用或启动 Hub、注册当前 Workspace，并等待受管 Runtime 就绪。
打开 `http://127.0.0.1:8848/ui` 可以查看正在运行的 Workspace。

Windows 可直接从 PowerShell、CMD 或资源管理器使用原生启动器，而且无需修改 PowerShell
执行策略：

```bat
start-promptaflow.cmd
restart-promptaflow.cmd
stop-promptaflow.cmd
```

需要启动其他 Workspace 时传入路径：

```bat
start-promptaflow.cmd "D:\Develop\your-project"
```

## MCP App 卡片

PromptaFlow 提供五张紧凑的 MCP App 视图。在支持 MCP Apps 的 App 中，调用对应工具时，
卡片会显示在对话旁边。下面的提示词可以直接用自然语言说出，Agent 会把它们映射到工具。

### Workspace

<img src="./docs/images/cards/dashboard.png" alt="PromptaFlow Workspace 卡片" width="560">

- **提示词：**`打开 PromptaFlow。`
- **功能：**在同一张卡中打开目标、工作流、历史记录和 Agents，并显示当前或最近的目标。

### Workflows

<img src="./docs/images/cards/workflows.png" alt="PromptaFlow Workflows 卡片" width="560">

- **提示词：**`显示我的 PromptaFlow 工作流。`
- **功能：**列出已发布的工作流；选择后查看流程图和定义，并可新建目标、修改或删除。

### Workflow generation

<img src="./docs/images/cards/workflow-generation.png" alt="PromptaFlow 工作流生成卡片" width="560">

- **提示词：**`创建一个工作流：拆解并总结文章，然后生成一份简洁的演示文稿。`
- **功能：**启动 Agent 编写流程，显示原始要求、生成进度和最终工作流。

### Goal execution

<img src="./docs/images/cards/goal-execution.png" alt="PromptaFlow 目标执行卡片" width="560">

- **提示词：**`使用文章转演示文稿工作流处理这篇文章。`
- **功能：**启动目标并跟踪每个步骤、需要的人工输入、执行状态和最终结果。

### Goals

<img src="./docs/images/cards/goals.png" alt="PromptaFlow Goals 卡片" width="560">

- **提示词：**`显示我最近的 PromptaFlow 目标。`
- **功能：**列出最近的目标运行及其当前状态，并可进入单次运行详情。

工具映射、卡片行为和缓存刷新方式见[卡片文档](./docs/cards.zh-CN.md)。

## 运行目标

1. 打开 **目标**。
2. 选择已发布的工作流，或者描述一个工作流并让 Agent 创建。
3. 输入目标并启动。
4. 在 Workspace 中跟踪步骤，或在 **历史记录** 中检查已完成的运行。

通过 MCP 使用时，主要工具是 `list_workflows`、`generate_workflow`、`start_run`、
`inspect_run` 和 `cancel_run`。客户端必须使用 Runtime 当前返回的 `allowed_commands[]`，
不得自行构造写操作 URL。

## 委托给当前对话执行

Agent 步骤通常交给工作流指定的 CLI。当系统没有安装 CLI，或希望当前 App 直接完成工作时，
可以用 `execution_mode="current_app"` 启动。PromptaFlow 不改变工作流结构，而是把每个 Agent
步骤排队交给发起运行的对话，并把实际执行图随运行保存。该模式异步执行，支持并行分支，
也支持从 checkpoint 安全恢复。

### 有哪几种触发方式

只能显式指定。没有 CLI 开关，界面上也没有切换项，**更不会因为缺少 CLI 而自动降级**——
运行以哪种模式启动，就一直是哪种模式。

| 方式 | 做法 |
| --- | --- |
| 对 Agent App 直接说 | 在对话里讲清楚即可，内置 skill 会选好工作流并带上该模式 |
| MCP 工具 | `start_run(workflow_id=..., goal=..., execution_mode="current_app")` |
| HTTP API | `POST /api/v1/langgraph-runs`，请求体带 `"execution_mode": "current_app"` |

Agent 步骤指定了你未安装的 CLI 的工作流，默认会被目录过滤掉。为这个模式挑工作流时请用
`ready_only=false` 列出——缺 CLI 正是这个模式要抹平的事情。`inspect_workflow_definition`
也接受 `execution_mode`，可以在启动前先看它在这个模式下编译成什么样。

### 提示词

以该模式启动一次运行：

```text
用 PromptaFlow 执行：<目标原文>。Agent 步骤都由你在当前对话里完成，不要调用 CLI。
```

```text
用工作流 workflow:<id> 执行目标：<目标原文>，委托给当前对话执行。
```

还不确定有没有合适的工作流时，先挑：

```text
列出可以完全在当前对话里跑完的 PromptaFlow 工作流，包括那些我没装 CLI 的。
```

跟进一次已经委托出来的运行：

```text
继续你正在替我执行的 PromptaFlow 运行——领取下一个步骤，做完并汇报产出。
```

对话通过委托工具驱动整个运行：`list_delegations` 查看排队的工作，`claim_delegation`
领取一个步骤，长时间执行期间用 `checkpoint_delegation` 和 `renew_delegation`，
`complete_delegation` 交回结果。领取后未完成的步骤由 `reconcile_delegation` 回收。

## CLI 快速参考

```bash
promptaflow serve
promptaflow serve --project-root /absolute/path/to/project
promptaflow hub register /absolute/path/to/project --no-agent-project-access
promptaflow --version
promptaflow runtimes --json
promptaflow mcp
promptaflow mcp --project-root /absolute/path/to/project
promptaflow run list
promptaflow run inspect <run_id>
promptaflow workflow validate <file> --catalog <catalog.json>
promptaflow workflow publish <file> --catalog <catalog.json> --expected-version <n>
```

## 开发

```bash
uv sync --extra dev
.venv/bin/python -m unittest discover -s tests
node --test tests/ui/client_modules.test.mjs
```

构建 Python 包和插件包：

```bash
uv build
python scripts/build-marketplace-release.py \
  --version 0.6.1-alpha \
  --output dist/promptaflow-marketplace-0.6.1-alpha.zip \
  --plugin-output dist/promptaflow-plugin-0.6.1-alpha.zip
```

推送 `v0.6.1-alpha` 这样的完整 SemVer 标签后，会执行跨平台 Release workflow，并上传
GitHub 分发产物。PyPI 发布只在手动运行 workflow 时按需启用；普通标签发布仍仅发布到 GitHub。
