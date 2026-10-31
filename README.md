# ForgeCLI

**终端里的 AI 编程工作台。**

在项目目录中阅读代码、规划修改、编辑文件和运行命令。ForgeCLI 将模型对话、工具执行、权限审批与任务协作放在同一个工作台中，支持 Anthropic、OpenAI 和兼容接口。

基于 Python 与 Textual 构建，提供终端界面、本机浏览器界面和脚本调用入口。

## 能做什么

| 能力 | 用途 |
| --- | --- |
| 代码与命令工具 | 读取、搜索、编辑文件，运行命令并查看执行结果 |
| 规划与权限审批 | 先讨论方案，再按所选权限模式执行操作 |
| 会话与项目记忆 | 恢复对话、压缩上下文，加载项目指令 |
| Agent 与任务协作 | 分配子任务，查看后台任务与团队进度 |
| MCP、Skills 与 Hooks | 接入外部工具，扩展工作流程 |
| Git worktree | 将修改任务放入独立工作目录 |

## 快速开始

需要 Python **3.11+** 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。使用 worktree 功能还需要 Git。下载源码后，在项目根目录执行：

```shell
uv sync --locked
```

Windows PowerShell：

```powershell
Copy-Item .forgecli/config.yaml.example .forgecli/config.yaml
$env:ANTHROPIC_API_KEY = "替换为你的密钥"
```

macOS / Linux：

```shell
cp .forgecli/config.yaml.example .forgecli/config.yaml
export ANTHROPIC_API_KEY="替换为你的密钥"
```

编辑 `.forgecli/config.yaml`，选择你的账户可用的模型及服务地址，然后启动：

```shell
uv run forgecli
```

配置中的 `api_key` 留空时读取对应的 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`；非空时使用配置值。程序不会自动读取 `.env`。模型服务需要自行配置，调用费用由相应服务商收取。

## 三种使用方式

交互工作台：

```shell
uv run forgecli
uv run forgecli --mode plan
```

直接运行一个任务，或将事件作为 NDJSON 交给脚本处理：

```shell
uv run forgecli -p "介绍当前项目的结构"
uv run forgecli -p "检查项目中的待办事项" --output-format stream-json
```

本机浏览器界面：

```shell
uv run forgecli --remote
```

打开终端打印的完整链接。链接含本次进程的访问令牌，重启后需要使用新链接；浏览器模式仅供本机访问。页面将模型输出显示为文本与代码块。

## 项目配置

- `.forgecli/config.yaml`：模型、权限模式和可选服务。
- `FORGECLI.md`：项目约定与工作说明。
- `.forgecli/skills/`、`.forgecli/agents/`、`.forgecli/commands/`：项目扩展。
- `FORGECLI_MCP_LOADING`、`FORGECLI_REMOTE_MEMORY_DIR`：MCP 加载策略与记忆目录覆盖设置。

MCP 默认关闭。配置示例提供启用方式；使用 stdio 服务前，需要安装相应命令的运行环境。HTTP 服务请填写最终端点地址，客户端不会自动跟随重定向。

## 权限与运行边界

默认模式会请求确认需要审批的操作。`-p` 模式无法进行人工审批，会拒绝仍需确认的请求；受控的文件编辑任务可使用 `--mode acceptEdits`。`--mode bypassPermissions` 会跳过审批，请仅用于你明确控制的环境。

系统沙箱和外部终端后端取决于运行平台。Windows 不提供 Linux/macOS 的操作系统沙箱；命令执行使用系统 shell。有关本地数据、外部工具和漏洞报告，见 [SECURITY.md](SECURITY.md)。

## 开发与验证

```shell
uv run --locked pytest -q
uv build
uv run --locked python scripts/check_dist.py
```

默认测试使用模拟模型，不需要服务密钥。真实模型集成测试需显式设置 `FORGECLI_TEST_API_KEY`。打包检查会验证归档内容，并在独立环境安装 wheel，检查命令、模块入口和资源文件。

GitHub Actions 已配置 Windows / Linux 的 Python 3.11、3.14，以及 macOS 的 Python 3.14 检查；实际运行结果以仓库 Actions 为准。已配置 Dependabot 依赖更新。

开发约定见 [CONTRIBUTING.md](CONTRIBUTING.md)，功能变更见 [CHANGELOG.md](CHANGELOG.md)。

## 维护者

[ytinyx](https://github.com/ytinyx) · [ytiny163@163.com](mailto:ytiny163@163.com)
