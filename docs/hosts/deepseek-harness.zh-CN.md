# 在 DeepSeek Harness 中使用 PromptaFlow

**简体中文** | [English](./deepseek-harness.md) · [宿主](./README.zh-CN.md) · [PromptaFlow](../../README.zh-CN.md)

| | |
| --- | --- |
| 接入方式 | 带自有 Gateway 的 Host Profile Bundle |
| 注册名 | 按 Session 的 `harness:session:*` actor |
| 是否绘制 PromptaFlow 卡片 | 否 —— 它画自己的面板 |
| MCP 工具 profile | `harness`，完整工具面的子集 |

## 从仓库安装

`integrations/deepseek-harness` 是可安装的 Host Profile Bundle。安装后，PromptaFlow Runtime
仍是独立的本地进程，Harness Web Profile 则获得 PromptaFlow 面板和工具。

### 使用简单提示词安装

把下面这句话交给能够读取公开仓库并运行本地命令的 DeepSeek Harness Agent：

```text
请安装这个仓库中的 PromptaFlow DeepSeek Harness 集成：https://github.com/TNJ2026/promptaflow
```

Agent 应从仓库的宿主索引找到本文，并执行下面的步骤。它必须在重启当前 Harness Profile
之前停下，提醒你完成重启。

如果 checkout 已经在本地，请把它作为 Harness Workspace 打开，或提供它的绝对路径，然后粘贴：

```text
请从当前本地仓库安装 PromptaFlow DeepSeek Harness 集成。不要重新 clone；保留所有本地修改，安装本地 Runtime 和 Harness Bundle、验证 Profile 配置，然后在必须重启 Harness Web Profile 之前停止并提醒我。
```

重启 Profile 后，打开一个由真实目录支持的 Workspace，并执行 `/promptaflow` 验证常驻面板。

### 1. 检查前置条件

- Git 和 `uv`。
- PromptaFlow Runtime 需要 Python 3.10 或更高版本。
- 集成 Bundle 需要 Node.js 22 或更高版本。
- 可用的 `dsh` 命令，以及名为 `web` 的 Harness Web Profile。

修改 Profile 前先检查：

```bash
git --version
uv --version
node --version
dsh --version
```

### 2. 把 PromptaFlow 克隆到稳定目录

```bash
git clone https://github.com/TNJ2026/promptaflow.git /绝对路径/稳定目录/promptaflow
cd /绝对路径/稳定目录/promptaflow
```

如果仓库已经存在，更新前先检查本地修改，不要丢弃未提交工作；干净的 checkout 可使用
`git pull --ff-only` 更新。

### 3. 安装 PromptaFlow Runtime

```bash
uv tool install /绝对路径/稳定目录/promptaflow
uv tool update-shell
paf --version
```

如果执行 `uv tool update-shell` 后仍暂时找不到 `paf`，请打开一个新终端。

### 4. 添加 Harness Bundle

替换已有 Bundle 前先停止正在运行的 Web Profile，然后执行：

```bash
dsh plugin --profile web add /绝对路径/稳定目录/promptaflow/integrations/deepseek-harness
dsh --profile web --dump-config
```

输出的 Profile 配置中必须包含 `@promptaflow/dsh`，其来源路径应指向上面使用的
checkout。

### 5. 重启并验证

1. 重启 Harness Web Profile。
2. 打开一个由真实目录支持的 Workspace。
3. 执行 `/promptaflow`。
4. 确认 PromptaFlow 面板出现，且 Settings 行显示 **connected**。
5. 打开一个历史 Run，或让 Agent 列出 PromptaFlow 工作流，验证 Host 到 Runtime 的链路。

打开 `/promptaflow` 时，必要则为该 Harness Workspace 启动 PromptaFlow；这样启动的 Runtime 在面板或
Profile 关闭后依然存活。Gateway 默认在 `~/.promptaflow` 下寻找归属记录——如果 Runtime 数据库
在别处，为该 Profile 设置 `PROMPTAFLOW_RUNTIME_ROOT`。PromptaFlow CLI 对该数据库持有一把非阻塞的
归属锁，并在归属记录里公布自己的 Workspace 和 MCP 端点；Harness 从不持有这把锁，也不
制造第二个写入者。

### 升级、回滚或移除

升级时停止 Profile，更新干净的 checkout，刷新 Runtime 工具，再次添加 Bundle：

```bash
cd /绝对路径/稳定目录/promptaflow
git pull --ff-only
uv tool install --force /绝对路径/稳定目录/promptaflow
dsh plugin --profile web add /绝对路径/稳定目录/promptaflow/integrations/deepseek-harness
dsh --profile web --dump-config
```

重启 Profile 后重复上面的验证。需要回滚时，在干净 checkout 中切换到目标 Release 标签，
重新安装该版本的 Runtime 和 Bundle，再重启 Profile。回滚 Bundle 不需要删除 PromptaFlow Runtime
数据库。

仅移除 Harness 集成：

```bash
dsh plugin --profile web remove @promptaflow/dsh
dsh --profile web --dump-config
```

第二条命令不应再列出该 Bundle。移除集成不会停止或删除独立运行的 PromptaFlow Runtime。

| 组件 | 支持范围 |
| --- | --- |
| PromptaFlow Runtime | 实现 `promptaflow-harness/2` 协议的任意版本 |
| PromptaFlow 集成协议 | `promptaflow-harness/2` |
| Harness 包 | `>=0.1.1-rc.2 <0.2.0`（不支持 alpha 预发布版本） |
| React | `^18.2.0` |
| Node.js | `>=22` |

这个 bundle 在 Harness 外壳浮层里常驻一个面板。它可以折成一个徽标，只说「有没有东西
在跑」，展开则是 Runtime 自己的四个页面——目标、工作流、历史、Agents。面板可停靠也可
拆出拖动，并记住你选的哪种。流程图、Artifact 和工作流撰写**不在这里重画**：面板会打开
PromptaFlow 自己的 UI。

**Run 由对 Agent 说话来启动，不从面板启动。** Agent 拥有一组有界的原生工具——
`promptaflow_list_workflows`、`promptaflow_list_runs`、`promptaflow_inspect_run`、`promptaflow_start_run`、
`promptaflow_cancel_run`、`promptaflow_resume_run`——所以「用 CSV 清洗流跑一下今天的导出」就是全部
接口。模型从不提供端点、actor、幂等键或变更版本号：Host 从工具运行上下文推导 Workspace
与 Session、自己生成幂等键，并在 cancel 或 resume 前重新读取 `allowed_commands[]`。
`/promptaflow-workflows` 会打开外壳自己的选择弹窗，把选中的工作流作为引用 chip 放进草稿。

面板**故意没有启动按钮**。面板自己启动的 Run，是 Agent 一无所知的 Run——事后无法汇报，
也无法从它接着往下做。

Harness 用 `harness` 这个 MCP 工具 profile 运行 Runtime，它是完整工具面的一个子集。
Harness **不执行** PromptaFlow 的工作流节点：Agent 发现、CLI 凭据、沙箱、进程清理、重试语义
和副作用，全部仍归 Runtime 所有。PromptaFlow 只接受来自回环、只在 `/mcp` 上、且只在
`harness:session:*` 下的 `x-promptaflow-actor` 头。

## 面板

打开一个 Run 会占据整个面板，返回的入口在顶部；打开一个步骤则显示该步骤的输出。在面板
宽度下，一个 Run 的详情放不进它兄弟节点旁边 —— 就地展开会把列表里其余的挤出去，那等于
把它们弄丢了。第一层以下的数据在展开之前不取，没有可跟的东西时就停止跟随。

Run 可以取消、被中断的可以继续、等待人工的步骤可以在面板里裁决。**每一次变更都带上面板
当时显示的 revision**，如果 PromptaFlow 已经往前走了就会被拒绝：一个悄悄作用在比你正在读的更新
的 Run 上的按钮，比一个会失败的按钮更糟。

面板列的是 **Workspace 的 Run，不是这个聊天的**。Gateway 的每次调用都带一个按 Session 的
actor，而 `list_runs` 默认按调用者收窄 —— 这对「Agent 陈述自己干过什么」是对的，对「站在
PromptaFlow UI 旁边的面板」是错的：曾经出现过 Runtime 里有二十五个 Run、而面板的历史是空的。
面板传 `owner: workspace`；Agent 工具保持默认。

轮询跟着工作走：有 Run 在动时每两秒一次，都不动时每十五秒一次，每次只发一个带 Session id
的往返。

配色取自外壳的 `--dsw-alias-*` token，所以面板跟随 Harness 的主题，而不是自己有主张。

## 怎么点名一个工作流

在面板里选一个工作流，会把一句调用语写进当前对话草稿；你在那里补上目标并提交，于是 Run
归 Agent 所有。`/promptaflow-workflows` 打开外壳自己的选择弹窗（就是 `/model` 用的那个），
把选择作为**引用 chip** 放进草稿。

这个 chip 有两张面孔：你看到的是名字，模型收到的是
`workflow:cov-branch（覆盖 A：分支与条件）`，所以它永远不必把名字反解成 id，也不必在两个
读起来很像的之间猜。bundle 还会把每个已桥接 Workspace 的**就绪**工作流连同各自需要的输入
一起放进模型上下文 —— 后者正是它要防的那个错误。

两者都读面板自己轮询填的同一份缓存，所以不会为「只在发布工作流时才变」的东西问第二遍；
Runtime 挂了的时候，留在上下文里的是上一个答案，而不是空的。

## Host API

Harness 源上的 `/plugins/dsh-promptaflow/api` 提供 Run 检查、Steps、Graph、Edges、基于游标的
输出、有上限的 Artifact 内容和附件导入。每次调用都带一个 Workspace，而 **Host 一个都不信**：
在任何 Gateway 调用之前，都要对着它声称所属的 Session、或对着 Workspace 注册表校验一遍。
它从不让调用方直接够到 PromptaFlow 的回环地址；客户端代码也永远拿不到 Runtime 端点、子进程句柄、
actor 头或 PromptaFlow 凭据。

图片 Artifact 在同时通过 PromptaFlow 的 2 MiB 代理上限和 Harness 图片准入之后，可以导入 Harness
的附件存储；当前附件契约支持 PNG、JPEG、WebP 和 GIF，其他媒体留在 PromptaFlow。

诊断文档只包含 Workspace/Session id、协议能力、聚合计数、Gateway 计数器和 Bridge 状态 ——
不含 MCP 端点、actor 头、原始输出、Artifact 字节、任务提示词或凭据。

## Session 与恢复

Host 会为每个带 `cwd` 的活跃根 Session 自动挂一个 Bridge，包括启动期间恢复出来的 Session。
Bridge 的游标和已知 Run id 来自持久化的 `promptaflow/run-*` Session 事件，所以 Host 重启后无需
第二个游标数据库即可续上。Session 释放会中止轮询器；Runtime 暂时不可用时会重试，而不会
阻塞 Session 生命周期。

Harness 把第一轮恢复规则贡献进它自己的系统提示词组装，并暴露绑定到 Session 的委托工具；
worker id 由集成推导，而不是由模型提供。参见
[把目标委托给当前对话执行](../../README.zh-CN.md#把目标委托给当前对话执行)。

## 失败与重连

Gateway 在启动时就拒绝不兼容的 PromptaFlow 集成协议；运行时编解码器在 DTO 到达 Client 之前就
拒绝畸形的核心 DTO —— 畸形的 Run、Step、Output 或 Artifact 载荷会在 Gateway 边界失败，
而不是一路穿过 TypeScript 断言。MCP 传输失败时，缓存的端点会被丢弃，下一次 Bridge 轮询或
工具调用会重新发现，因此 Hub 重启或工作区 Runtime 更换动态端口时无需重启 Harness。

维护者可以用 `npm run smoke:profile` 在一个隔离的临时 Profile 里验证安装、Host/Web 启动、
HTTP 就绪和干净卸载。启动器在 `PATH` 上不叫 `dsh` 时设置 `DSH_BIN`；要测试确切的发布产物，
把 `DSH_BUNDLE_SPEC` 设为 `.tgz` 的绝对路径。
