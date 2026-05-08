# Paul Learn Agent

> 娱乐性质的个人学习项目，自己动手实现 Harness Agent。

## 简介

这是一个轻量级的 Python AI Agent 框架，支持多 LLM 提供商（OpenAI、Anthropic、DeepSeek），具备工具调用能力。Agent 可以接收用户问题，自主决定是否调用工具获取更多信息，并给出最终回答。

**⚠️ 本项目为学习/娱乐用途，不适合生产环境使用。**

**📚 参考项目：**

- 本项目的灵感和架构参考了 [hermes-agent](https://github.com/NousResearch/hermes-agent.git)，在此基础上进行了自己的实现和探索。
- 部分实现参考了 [ShareAI Learn](https://learn.shareai.run/zh/s03/) 中的教程内容。

## 特性

- **多 LLM 提供商**: 通过 `.env` 配置即可切换 OpenAI / Anthropic / DeepSeek
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
│   │   ├── anthropic_provider.py # Anthropic SDK 实现
│   │   └── deepseek_provider.py  # DeepSeek SDK 实现（基于 OpenAI SDK）
│   └── tools/
│       ├── tool_manager.py     # ToolsProvider Protocol + ToolsRegistry 注册表
│       ├── terminal_tool.py    # 终端执行工具（前台/后台/超时/PTY）
│       ├── file_tool.py        # 文件工具（read_file / write_file / search_files）
│       ├── todo_tool.py        # 任务管理工具（待办列表增删改查）
│       ├── delegate_tool.py    # 任务委派工具（delegate_task，支持单任务/批量并行子 Agent）
│       └── skills_tool.py      # 技能管理工具（skills_list / skill_view，加载技能知识）
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
LLM_PROVIDER=deepseek

# DeepSeek 配置（兼容 OpenAI API 格式）
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# 或 OpenAI 配置
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your-api-key
# OPENAI_MODEL=gpt-4o

# 或 Anthropic 配置
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your-api-key
# ANTHROPIC_MODEL=claude-sonnet-4-6
```

### 3. 运行

```bash
uv run python main.py
```

## 当前状态

- [x] 多 LLM 提供商支持（OpenAI / Anthropic / DeepSeek）
- [x] Provider 注册机制
- [x] 工具调用决策循环
- [x] 基础工具实现（Terminal / 文件读写搜索）
- [x] 子 Agent 协作能力（delegate_tool，支持单任务委派和批量并行）
- [x] 技能管理（skills_tool，支持技能列表查看和技能内容加载）
- [ ] 更多交互方式

## Tag 列表

本项目通过 git tag 标记学习过程中的各个里程碑。每个 tag 代表一个独立的学习阶段，功能从零开始逐步叠加。

| Tag | 说明 |
|-----|------|
| [`agent-loop`](#) | 实现 Agent 自我循环能力。仅包含最核心的 agent loop，目标是理解 Agent 如何通过循环自主决策、持续交互。 |
| [`base_tool`](#) | 实现基础工具集，包含工具抽象层和具体工具实现。详见 [工具系统设计文档](docs/tools.md)。 |
| [`todo_tool`](#) | 引入任务管理工具 `todo`，让 Agent 在处理复杂任务时主动维护和追踪任务计划。详见 [工具系统设计文档](docs/tools.md)。 |
| [`delegate_tool`](#) | 引入任务委派工具 `delegate`，支持将子任务分发给子 Agent 执行，实现多 Agent 协作能力。 |
| [`skill_tool`](#) | 添加技能管理系统，支持通过 `skills_tool` 加载和管理预定义技能知识，让 Agent 可以复用结构化技能。 |

> 未来新增的 tag 会继续在这里记录，每个 tag 都是独立的学习节点。

## 工具系统

工具系统采用 Protocol 抽象 + 注册表模式，包含 Terminal、File、Todo、Delegate、Skill 等工具集。详细架构设计和参数说明见 [工具系统设计文档](docs/tools.md)。

## 测试

`tests/` 目录存放了各模块的测试用例，是了解各项功能具体行为的最佳入口。

## 技术栈

- Python 3.12+

## 许可证

本项目采用 [AGPL-3.0](LICENSE) 开源协议。如果你使用了本项目的代码，你的项目也必须以 AGPL-3.0 协议开源。详见 [LICENSE](LICENSE) 文件。
