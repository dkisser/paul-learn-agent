# 工具系统设计

## 架构设计

工具系统采用 **Protocol 抽象 + 注册表** 的模式，结构清晰、易于扩展：

```
agent/tools/
├── tool_manager.py    # ToolsProvider Protocol（定义接口）+ ToolsRegistry（全局注册表）
├── terminal_tool.py   # 终端执行工具
├── file_tool.py       # 文件读写搜索工具（read_file / write_file / search_files）
├── todo_tool.py       # 任务管理工具（todo，含 TodoStore 状态追踪）
└── delegate_tool.py   # 任务委派工具（delegate_task，支持单任务/批量并行子 Agent）
```

**核心概念：**

- `ToolsProvider` — 所有工具必须实现的协议，包含 `get_schema()`（工具描述，用于 LLM 理解）、`invoke()`（统一入口）、`do_invoke()`（具体逻辑）
- `ToolsRegistry` — 全局注册表，通过 `registry.register(name, ToolClass)` 注册，`registry.get(name)` 获取
- Agent 启动时自动 import 工具模块完成注册，LLM 根据 schema 自主决定调用哪个工具

## 工具列表

### Terminal（终端执行）

| 参数 | 类型 | 说明 |
|------|------|------|
| `command` | string | 要执行的命令（必填） |
| `background` | boolean | 后台运行，返回 session_id，适合长时任务或常驻进程 |
| `timeout` | integer | 超时时间（秒，默认 180），命令完成即返回，不会干等 |
| `workdir` | string | 临时工作目录 |
| `pty` | boolean | 伪终端模式，适合交互式 CLI（待实现） |
| `notify_on_complete` | boolean | 后台任务完成后自动通知 |

**设计理念：** 引导 LLM 将文件操作委托给专用工具（`read_file`、`write_file`、`search_files`），终端仅保留给构建、安装、git、网络等真正需要 shell 能力的场景。

### File 工具集

| 工具 | 功能 | 关键特性 |
|------|------|----------|
| `read_file` | 读取文件内容 | 带行号输出（`LINE_NUM\|CONTENT` 格式），支持 `offset`/`limit` 分页读取大文件，自动检测不存在的文件 |
| `write_file` | 写入/覆盖文件 | 自动创建父目录，写入前自动备份原文件为 `.bak` |
| `search_files` | 搜索文件内容或按名查找 | ripgrep 优先、grep 兜底；支持 `target='content'` 内容搜索和 `target='files'` 文件名搜索；支持 `output_mode`（完整匹配/仅文件列表/计数）和 `context` 上下文行 |

### Delegate（任务委派）

通过 `delegate_task` 工具将子任务分发给独立的子 Agent 执行，支持单任务和批量并行两种模式。子 Agent 拥有独立的对话、终端会话和工具集，完成后返回摘要结果。

**适用场景：**
- 需要推理的子任务（调试、代码审查、研究综合）
- 会占用大量上下文的中间数据任务
- 并行独立工作流（同时研究 A 和 B）

**不适用场景：**
- 无需推理的机械化多步操作 → 直接用 `execute_code`
- 单次工具调用即可解决 → 直接调用
- 需要用户交互的任务 → 子 Agent 无法使用 `clarify`

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | string | 子 Agent 要完成的目标。描述要具体且自包含，子 Agent 不知道父 Agent 的对话历史 |
| `context` | string | 背景信息：文件路径、错误消息、项目结构、约束条件。信息越具体，子 Agent 表现越好 |
| `toolsets` | array[string] | 为子 Agent 启用的工具集。默认继承父 Agent 的工具集。常见组合：`['terminal', 'file']`（代码工作）、`['web']`（研究）、`['terminal', 'file', 'web']`（全栈任务） |
| `tasks` | array | **批量模式**：最多 3 个任务并行执行。每个任务包含 `goal`（必填）、`context`、`toolsets`。提供此参数时忽略顶层 `goal`/`context`/`toolsets` |
| `max_iterations` | integer | 每个子 Agent 的最大工具调用轮数（默认 50），简单任务可设更低 |

**调用方式 — 单任务模式：**

```json
{
  "name": "delegate_task",
  "arguments": {
    "goal": "Review the authentication flow in agent/agent.py for potential security issues",
    "context": "The project uses JWT tokens stored in .env. Focus on token validation and expiration handling.",
    "toolsets": ["terminal", "file"],
    "max_iterations": 30
  }
}
```

**调用方式 — 批量并行模式（最多 3 个）：**

```json
{
  "name": "delegate_task",
  "arguments": {
    "tasks": [
      {
        "goal": "Search for all TODO comments in the codebase",
        "toolsets": ["terminal", "file"]
      },
      {
        "goal": "Check if there are any unused imports in the project",
        "toolsets": ["terminal", "file"]
      }
    ]
  }
}
```

**返回结果（JSON 数组，每项对应一个任务）：**

```json
[
  {
    "task_index": 0,
    "status": "completed",
    "summary": "发现 3 处安全隐患：1) token 未验证过期时间...",
    "api_calls": 12,
    "duration_seconds": 45.32,
    "exit_reason": "completed",
    "tool_trace": [
      {
        "tool": "read_file",
        "args_bytes": 52,
        "result_bytes": 1024,
        "status": "ok"
      }
    ]
  }
]
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_index` | integer | 任务序号，与输入数组顺序一致 |
| `status` | string | `completed`（有摘要）、`failed`（无响应）、`error`（异常）、`interrupted` |
| `summary` | string | 子 Agent 的最终摘要，说明做了什么、发现了什么、创建/修改了哪些文件、遇到的问题 |
| `api_calls` | integer | 子 Agent 消耗的 API 调用次数 |
| `duration_seconds` | float | 子 Agent 执行耗时（秒） |
| `exit_reason` | string | `completed`（正常完成）、`max_iterations`（达到最大轮数）、`interrupted` |
| `tool_trace` | array | 工具调用追踪，记录每次工具调用的名称、参数大小、结果大小和状态 |
| `error` | string | 仅在 `status` 为 `failed` 或 `error` 时出现，描述错误原因 |

**注意事项：**
- 子 Agent **没有** 父 Agent 的对话记忆，所有相关信息需通过 `context` 传入
- 子 Agent **不能调用**：`delegate_task`、`clarify`、`memory`、`send_message`、`execute_code`
- 每个子 Agent 拥有独立的终端会话（独立工作目录和状态）
- 批量模式下结果数组始终按输入顺序排序

### Todo（任务管理）

用于管理当前会话的任务列表，适合 3 步以上的复杂任务或多步骤工作流。

| 参数 | 类型 | 说明 |
|------|------|------|
| `todos` | array | 任务项数组，每项包含 `id`（唯一标识）、`content`（任务描述）、`status`（状态）。省略此参数表示读取当前列表 |
| `merge` | boolean | `false`（默认）：替换整个任务列表；`true`：按 id 更新已有项并追加新项 |

**任务状态：** `pending` → `in_progress` → `completed` / `cancelled`

**设计理念：** 引导 LLM 在处理复杂任务时主动维护任务计划，同一时刻只有一个 `in_progress` 项。完成即标记，失败则取消并添加修订项。调用时始终返回完整的当前列表，方便 LLM 感知全局进度。

### Skill（技能管理）

技能系统允许 Agent 加载和使用预定义的知识模板。每个技能是一个包含 `SKILL.md` 的目录，可附带 `references/`、`templates/`、`assets/`、`scripts/` 等子目录存放关联文件。

**技能目录结构：**

```
skills/
├── web-scraping/              # 技能目录名
│   ├── SKILL.md               # 技能主文件（必须），包含 frontmatter 元数据和正文
│   ├── references/
│   │   └── api-reference.md   # 参考文档
│   ├── templates/
│   │   └── request-template.py # 代码模板
│   ├── assets/
│   │   └── demo.png           # 图片等资源
│   └── scripts/
│       └── setup.sh           # 辅助脚本
```

**SKILL.md frontmatter 格式：**

```yaml
---
name: web-scraping
description: Web 数据抓取技能，用于从网页中提取结构化数据
related_skills:
  - data-processing
  - http-client
---

技能正文内容...
```

| 工具 | 功能 | 参数 |
|------|------|------|
| `skills_list` | 列出所有可用技能 | `category`（可选）— 按分类过滤 |
| `skill_view` | 查看技能详情或关联文件 | `name`（必填）— 技能名称；`file_path`（可选）— 关联文件路径，如 `references/api.md` |

**skill_view 返回内容：**
- 首次调用（不传 `file_path`）：返回技能的元数据（name、description、related_skills）、正文内容、关联文件列表
- 再次调用（传入 `file_path`）：返回指定关联文件的内容

**设计理念：** 将常见任务的专业知识封装为可复用的技能卡片，Agent 在处理特定领域任务时自主加载相关技能，提升执行质量。技能与工具解耦，工具负责"怎么做"，技能负责"做什么"。
