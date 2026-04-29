# 工具系统设计

## 架构设计

工具系统采用 **Protocol 抽象 + 注册表** 的模式，结构清晰、易于扩展：

```
agent/tools/
├── tool_manager.py    # ToolsProvider Protocol（定义接口）+ ToolsRegistry（全局注册表）
├── terminal_tool.py   # 终端执行工具
├── file_tool.py       # 文件读写搜索工具（read_file / write_file / search_files）
└── todo_tool.py       # 任务管理工具（todo，含 TodoStore 状态追踪）
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

### Todo（任务管理）

用于管理当前会话的任务列表，适合 3 步以上的复杂任务或多步骤工作流。

| 参数 | 类型 | 说明 |
|------|------|------|
| `todos` | array | 任务项数组，每项包含 `id`（唯一标识）、`content`（任务描述）、`status`（状态）。省略此参数表示读取当前列表 |
| `merge` | boolean | `false`（默认）：替换整个任务列表；`true`：按 id 更新已有项并追加新项 |

**任务状态：** `pending` → `in_progress` → `completed` / `cancelled`

**设计理念：** 引导 LLM 在处理复杂任务时主动维护任务计划，同一时刻只有一个 `in_progress` 项。完成即标记，失败则取消并添加修订项。调用时始终返回完整的当前列表，方便 LLM 感知全局进度。
