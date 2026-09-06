# Orbit

**简体中文** | [English](./README.md)

Orbit 是面向 Agent App 的本地持久化 LangGraph 工作流 Runtime。Runtime、API、Web UI、
持久化定时器、工作流编写和 MCP 接入都运行在同一个进程中。项目数据保存在
`~/.orbit/projects/`。

目前可以从 **Codex app**、**WorkBuddy**、**DeepSeek Harness** 面板，以及任何其他
支持 MCP 的 App 接入——各走各的前门，面对的是同一个 Runtime。Agent 步骤通常 fork
一个已安装的 CLI；也可以改为委托给启动这次 run 的那个对话，那样一个 CLI 都不需要。

## 安装 CLI

需要 Python 3.10 或更高版本，以及 [uv](https://docs.astral.sh/uv/)。

```bash
uv tool install git+https://github.com/TNJ2026/orbit.git
uv tool update-shell
```

从源码运行：

```bash
git clone https://github.com/TNJ2026/orbit.git
cd orbit
uv sync --extra dev
uv run orbit serve
```

UI 地址为 `http://127.0.0.1:8848/ui`。这个页面列出本机正在运行的 Workspace Runtime
并链接进各自的 UI；它**不启动任何东西**，所以 Runtime 没起来的 Workspace 不会出现在那里。

只有一个 UI、一个目录、一个已发布 Workflow 库。工作流点名哪些 Agent，就在这些
Agent 存在的地方用它们。

已发布的工作流钉住的是编译时那个精确的 Handler 构建，而 Agent 的构建就是它的 CLI
版本——所以在别的机器上写的工作流、或者 CLI 升级过之后，它点名的东西可能不在这里。
无处可去的步骤会被送到一个在的 Agent 上，且尽可能少动：优先送到同一个 Agent 已安装
的构建，实在不行才送到本 Runtime 正在对话的那个 Agent。**点名的 Agent 在，就绝不
移动**——所以刻意用两个 Agent 的工作流仍然用两个。

顶替缺席 Agent 的那一个，取自最近一个自报家门的 MCP 客户端；在没有任何客户端连接时，
它保持不变。无从点名时，已发布的绑定原样成立，由编译器说它解不解得开——和这条回退
不存在时完全一样。

已发布的定义**从不被改写**；替换后的图随 run 一起保存，所以在已连接的 Agent 变化之后，
跑完的 run 说的仍然是「当时真正执行它的那个 Agent」。

## 宿主

Orbit 是一个 Runtime，但有好几扇前门。每个宿主接入方式不同、注册的客户端名不同，
是否绘制 Orbit 的卡片也不同。下面按宿主分节；宿主之后的内容，无论从哪儿接入都一样。

| 宿主 | 怎么接到 Orbit | 注册名 | 是否绘制卡片 |
| --- | --- | --- | --- |
| Codex app | 随插件分发的 stdio Proxy → Hub | `codex-app` | 是 |
| WorkBuddy | 自定义连接器，HTTP 直连 Hub | `orbit`，以及 `workbuddy-third-party:custom-mcp:orbit` | 是 |
| DeepSeek Harness | 带自有 Gateway 与面板的 Host Profile Bundle | 按 Session 的 `harness:session:*` actor | 自己的面板 |
| 其他 MCP App | stdio Proxy | 自己的稳定名称 | 取决于宿主 |

客户端名不得遮蔽已发现的 CLI。Runtime 会把已安装的 CLI 发现为 `codex`、`claude`
等 Agent，所以 App 用其中之一注册会被**直接拒绝**而不是改名——`-app` 后缀就是为此存在的。

### Codex app

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

### WorkBuddy

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

### DeepSeek Harness

`integrations/deepseek-harness` 是一个可安装的 Host Profile Bundle。装进目标
Harness Web Profile 并重启该 Profile：

```bash
dsh plugin --profile web add /absolute/path/to/orbit/integrations/deepseek-harness
```

卸载用 `dsh plugin --profile web remove @orbit-runtime/dsh-orbit`。

需要先安装 `orbit`，使可执行文件在 Harness Host 的 `PATH` 上。打开 `/orbit` 时，
必要则为该 Harness Workspace 启动 Orbit；这样启动的 Runtime 在面板或 Profile 关闭后
依然存活。Gateway 默认在 `~/.orbit` 下寻找归属记录——如果 Runtime 数据库在别处，
为该 Profile 设置 `ORBIT_RUNTIME_ROOT`。Orbit CLI 对该数据库持有一把非阻塞的归属锁，
并在归属记录里公布自己的 Workspace 和 MCP 端点；Harness 从不持有这把锁，也从不制造
第二个写入者。

| 组件 | 支持范围 |
| --- | --- |
| Orbit Runtime | `>=0.4.0 <0.5.0` |
| Orbit 集成协议 | `orbit-harness/1` |
| Harness 包 | `>=0.1.1-rc.2 <0.2.0` |
| React | `^18.2.0` |
| Node.js | `>=22` |

这个 bundle 在 Harness 外壳浮层里常驻一个面板。它可以折成一个徽标，只说「有没有东西
在跑」，展开则是 Runtime 自己的四个页面——目标、工作流、历史、Agents。面板可停靠也可
拆出拖动，并记住你选的哪种。流程图、Artifact 和工作流撰写**不在这里重画**：面板会打开
Orbit 自己的 UI。

**Run 由对 Agent 说话来启动，不从面板启动。** Agent 拥有一组有界的原生工具——
`orbit_list_workflows`、`orbit_list_runs`、`orbit_inspect_run`、`orbit_start_run`、
`orbit_cancel_run`、`orbit_resume_run`——所以「用 CSV 清洗流跑一下今天的导出」就是全部
接口。模型从不提供端点、actor、幂等键或变更版本号：Host 从工具运行上下文推导 Workspace
与 Session、自己生成幂等键，并在 cancel 或 resume 前重新读取 `allowed_commands[]`。
`/orbit-workflows` 会打开外壳自己的选择弹窗，把选中的工作流作为引用 chip 放进草稿。

面板**故意没有启动按钮**。面板自己启动的 Run，是 Agent 一无所知的 Run——事后无法汇报，
也无法从它接着往下做。

Harness 用 `harness` 这个 MCP 工具 profile 运行 Runtime，它是完整工具面的一个子集。
Harness **不执行** Orbit 的工作流节点：Agent 发现、CLI 凭据、沙箱、进程清理、重试语义
和副作用，全部仍归 Runtime 所有。Orbit 只接受来自回环、只在 `/mcp` 上、且只在
`harness:session:*` 下的 `x-orbit-actor` 头。

### 其他支持 MCP 的 Agent App

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

## 运行目标

1. 打开 **目标** 页面。
2. 选择一个已发布的 Workflow，或者描述一个、让 Agent 写出来。
3. 输入目标并启动。
4. 在工作台查看每一步进度，或在 **历史** 中检查已完成的运行。

也可以通过 MCP 使用 `list_runs`、`inspect_run`、`start_run` 和 `cancel_run`。
客户端必须遵循 Runtime 返回的 `allowed_commands[]`，不要自行拼接写操作 URL。

## 把目标委托给当前对话执行

通常每个 Agent 步骤都会 fork 它点名的那个 CLI。`execution_mode` 提供另一种安排：
整个工作流照跑，但 Agent 的活儿交给**启动这次 run 的那个对话**去做。

```text
start_run(workflow_id=..., goal=..., execution_mode="current_app")
```

Runtime 会把这次 run 里每个 `agent.*` 节点改绑到 `app.delegate` Handler，
`target` 为 `run_initiator`，并且**不动已发布的定义**——端口、边、映射、回边、条件和
提示词原样保留，不必为了把 `prompt` 改名成 `task` 而重写任何东西。替换后的图随 run
一起保存，所以跑完的 run 说的仍然是「实际执行它的是什么」。并行分支同样包含在内，
整个过程不需要安装任何 CLI。

这个模式**总是异步返回**。跟进这次 run 就是处理队列：

- `claim_delegation` 为本会话租约最早排队的那条委托并返回请求；在对话里把它执行掉。
- `renew_delegation` 续租，并观察是否已被取消。
- `checkpoint_delegation` 记录最新的安全恢复点，并在同一步里续租。
- `complete_delegation` 提交结果——或者错误。

队列按 actor 隔离，所以别的对话拿不走这个对话的活。它同时也是**幂等边界**：一个确定性的
delegation id 最多只能被认领一次；租约过期后会变成 `unknown`，而不是交给第二个 Agent。
`reconcile_delegation` 为 `unknown` 的那条记录一个人工裁决，它**从不重试、也不改写**原来
那次尝试——因为那次尝试很可能真的发生过。

因为 run 的寿命长于对话，每个受支持的宿主都会在**对话的第一个用户轮次**检查有没有可恢复
的工作：用默认状态调一次 `list_delegations`，空的就闭嘴，非空就告诉用户并询问。一条仍在
租约中、且属于同一个稳定 worker 的委托，可以在续租后从它的 checkpoint 继续。

`app.delegate` 也可以**直接写进工作流**，而不必经由 `execution_mode`。它的输入端口叫
`task` 而不是 `prompt`，`config.target` 必须是 `run_initiator`。有两条约束来自「App 能
产出什么」：节点必须是 `action` 且唯一输出为 `result`；如果输出是 artifact，它必须接受
`text/*` 或 `application/json`。旁边的 `harness.subagent` 是给 Harness 托管的 Subagent
Provider 用的，那里的 provider 写在委托请求里，而不是固定在注册表中。

## Run、事件与输出

Runtime 事件可通过 `wait_app_event`、`list_app_events` 和 `ack_app_event` 处理。
这三个是 **stdio Proxy 自己的工具**，所以 Codex app 以及用同样方式接入的 App 有它们，
而直接和 Hub 对话的宿主没有——Runtime 自己的事件工具是 `list_runtime_events`。
`event_type` 为 `langgraph_run.<status>`（run 状态变化）或
`langgraph_node.<outcome>`（单次 Handler 尝试，另带 `node_id` 和 `attempt_id`）。
节点事件只来自带尝试日志的 Handler —— 即那些执行本身是不可重复的外部效果的 —— 所以
重放的 superstep 不会产生事件。
事件只是提示，执行操作前应重新读取对应 Run。

run 在启动它的那个请求里执行。`POST /api/v1/langgraph-runs` 带 `"wait": false`
时，run 一创建就返回，执行放到后台 —— UI 用的就是这条，页面才能看着自己启动的目标。
两种方式下"这个 run 能不能存在"都已经判定完毕；等待换来的只是知道它**怎么结束的**。

每个 actor 同时只跑一个目标：当已有 `running`、`waiting` 或
`interrupted` 的 run 时，再启动会以 `active_goal_exists` 拒绝，并在拒绝里带上占用
该槽位的 run，客户端可以直接跳过去。取消或结束即释放。

run 默认永久保留。`/api/v1/ops/status` 报告引擎占用的容量；
`create_app(run_retention_days=N)` 会忘掉结束超过 N 天的 run —— 按**整个 run**
删除，因为缺了控制台或 checkpoint 的 run 会错误地描述自己。等待人工输入的 run、
以及 Handler 以 `unknown` 结束的 run，永远不会被忘掉。

Handler 进程打印的内容通过
`GET /api/v1/langgraph-runs/{run_id}/output?after=<chunk_id>` 读取，需要 sensitive
scope。它是控制台而非日志：按尝试和流分别限量、写在所有事务之外，且永远不参与重放。

## CLI 快速参考

```bash
orbit serve
orbit serve --agent-project-access        # 允许 workspace_access 节点读到项目
orbit serve --mcp-tool-profile harness    # Harness bundle 用的那个工具子集
orbit --version
orbit runtimes --json                     # 哪些 Runtime 在跑、在哪
orbit mcp
orbit mcp --project-root /absolute/path/to/project
orbit run list
orbit run inspect <run_id>
orbit workflow validate <file> --catalog <catalog.json>
orbit workflow publish <file> --catalog <catalog.json> --expected-version <n>
```

`orbit serve` 默认只绑定 `127.0.0.1`。多 Workspace 时，Agent CLI、Workflow 源码模板
和已发布 Workflow 全局共用；运行历史、人工任务、Artifact 及其他执行状态仍按 Workspace
隔离。Hub 还持有可复用的 Workflow 源码模板，并聚合在线 Workspace Runtime 的 Agent 统计。

## 开发

```bash
uv sync --extra dev
.venv/bin/python -m unittest discover -s tests
node --test tests/ui/client_modules.test.mjs
```

构建 Python 包：

```bash
uv build
python scripts/build-marketplace-release.py \
  --version 0.4.0 \
  --output dist/orbit-marketplace-0.4.0.zip
```

推送 `v0.4.0` 这样的标签后，Release workflow 会检查标签与
`src/orbit/__init__.py` 的版本是否一致、运行测试，并把 wheel、源码包和本地
Marketplace ZIP 一起上传到 GitHub Release。
