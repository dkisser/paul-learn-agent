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
│   └── llm/
│       ├── provider.py     # LLMProvider Protocol 和 ProviderRegistry
│       ├── openai_provider.py    # OpenAI SDK 实现
│       └── anthropic_provider.py # Anthropic SDK 实现
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
- [ ] Ollama Provider 实现（配置已就绪，Provider 待实现）
- [ ] 实际工具实现（目前为 stub）
- [ ] 更多交互方式

## Tag 列表

本项目通过 git tag 标记学习过程中的各个里程碑。每个 tag 代表一个独立的学习阶段，功能从零开始逐步叠加。

| Tag | 说明 |
|-----|------|
| [`agent-loop`](#) | 实现 Agent 自我循环能力。仅包含最核心的 agent loop，目标是理解 Agent 如何通过循环自主决策、持续交互。 |

> 未来新增的 tag 会继续在这里记录，每个 tag 都是独立的学习节点。

## 技术栈

- Python 3.12+
