# Paul Learn Agent

> 一个娱乐性质的个人学习项目，主要目的是自己动手实现一个 AI Agent Harness。

## 简介

这是一个轻量级的 Python AI Agent 框架，支持多 LLM 提供商（OpenAI、Anthropic、Ollama），具备工具调用能力。Agent 可以接收用户问题，自主决定是否调用工具获取更多信息，并给出最终回答。

**⚠️ 本项目为学习/娱乐用途，不适合生产环境使用。**

## 特性

- **多 LLM 提供商**: 通过 `.env` 配置即可切换 OpenAI / Anthropic / Ollama
- **Provider 抽象**: 基于 Protocol 的干净抽象，易于扩展新的 LLM 后端
- **工具调用循环**: 内置 ReAct 风格的 tool-use 循环，自动迭代直到得出答案
- **消息格式转换**: 内部统一使用 OpenAI 格式消息，各 Provider 负责适配转换

## 项目结构

```
.
├── main.py                 # 入口文件
├── agent/
│   ├── agent.py            # 核心 Agent 类，包含对话循环和工具调用逻辑
│   ├── agent_type.py       # Decision 数据类定义
│   ├── config.py           # LLMConfig 配置模型（基于 pydantic）
│   ├── llm/
│   │   ├── provider.py     # LLMProvider Protocol 和 ProviderRegistry
│   │   ├── openai_provider.py    # OpenAI SDK 实现
│   │   └── anthropic_provider.py # Anthropic SDK 实现
│   └── tools/
│       ├── tool_manager.py     # ToolsProvider Protocol + ToolsRegistry 注册表
│       ├── terminal_tool.py    # 终端执行工具（前台/后台/超时/PTY）
│       └── file_tool.py        # 文件工具（read_file / write_file / search_files）
├── resources/prompt/       # 提示词资源
├── pyproject.toml          # 项目依赖（uv 管理）
└── .env                    # 环境变量（需自行创建）
```

## 快速开始

### 1. 安装依赖

本项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖：

```bash
uv sync
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# 选择 LLM 提供商
LLM_PROVIDER=openai

# OpenAI 配置
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o

# 或 Anthropic 配置
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your-api-key
# ANTHROPIC_MODEL=claude-sonnet-4-6

# 或 Ollama 配置（尚未实现 Provider）
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3
```

### 3. 运行

```bash
uv run python main.py
```

## 当前状态

- [x] 多 LLM 提供商支持（OpenAI / Anthropic）
- [x] Provider 注册机制
- [x] 工具调用决策循环
- [x] 基础工具实现（Terminal / 文件读写搜索）
- [ ] Ollama Provider 实现（配置已就绪，Provider 待实现）
- [ ] 更多交互方式

## Tag 列表

本项目通过 git tag 标记学习过程中的各个里程碑。每个 tag 代表一个独立的学习阶段，功能从零开始逐步叠加。

| Tag | 说明 |
|-----|------|
| [`agent-loop`](#) | 实现 Agent 自我循环能力。仅包含最核心的 agent loop，目标是理解 Agent 如何通过循环自主决策、持续交互。 |
| [`base_tool`](#) | 实现基础工具集，包含工具抽象层和具体工具实现。详见下方「工具系统」章节。 |

> 未来新增的 tag 会继续在这里记录，每个 tag 都是独立的学习节点。

## 工具系统

### 架构设计

工具系统采用 **Protocol 抽象 + 注册表** 的模式，结构清晰、易于扩展：

```
agent/tools/
├── tool_manager.py    # ToolsProvider Protocol（定义接口）+ ToolsRegistry（全局注册表）
├── terminal_tool.py   # 终端执行工具
└── file_tool.py       # 文件读写搜索工具（read_file / write_file / search_files）
```

**核心概念：**

- `ToolsProvider` — 所有工具必须实现的协议，包含 `get_schema()`（工具描述，用于 LLM 理解）、`invoke()`（统一入口）、`do_invoke()`（具体逻辑）
- `ToolsRegistry` — 全局注册表，通过 `registry.register(name, ToolClass)` 注册，`registry.get(name)` 获取
- Agent 启动时自动 import 工具模块完成注册，LLM 根据 schema 自主决定调用哪个工具

### 工具列表

#### Terminal（终端执行）

| 参数 | 类型 | 说明 |
|------|------|------|
| `command` | string | 要执行的命令（必填） |
| `background` | boolean | 后台运行，返回 session_id，适合长时任务或常驻进程 |
| `timeout` | integer | 超时时间（秒，默认 180），命令完成即返回，不会干等 |
| `workdir` | string | 临时工作目录 |
| `pty` | boolean | 伪终端模式，适合交互式 CLI（待实现） |
| `notify_on_complete` | boolean | 后台任务完成后自动通知 |

**设计理念：** 引导 LLM 将文件操作委托给专用工具（`read_file`、`write_file`、`search_files`），终端仅保留给构建、安装、git、网络等真正需要 shell 能力的场景。

#### File 工具集

| 工具 | 功能 | 关键特性 |
|------|------|----------|
| `read_file` | 读取文件内容 | 带行号输出（`LINE_NUM\|CONTENT` 格式），支持 `offset`/`limit` 分页读取大文件，自动检测不存在的文件 |
| `write_file` | 写入/覆盖文件 | 自动创建父目录，写入前自动备份原文件为 `.bak` |
| `search_files` | 搜索文件内容或按名查找 | ripgrep 优先、grep 兜底；支持 `target='content'` 内容搜索和 `target='files'` 文件名搜索；支持 `output_mode`（完整匹配/仅文件列表/计数）和 `context` 上下文行 |

## 技术栈

- Python 3.12+
