import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any

from agent.agent import Agent
from agent.config import get_config
from agent.tools.tool_manager import ToolsProvider, registry


MAX_CONCURRENT_CHILDREN = 3


class DelegateTool(ToolsProvider):
    DELEGATE_TASK_SCHEMA = {
        "name": "delegate_task",
        "description": (
            "Spawn one or more subagents to work on tasks in isolated contexts. "
            "Each subagent gets its own conversation, terminal session, and toolset. "
            "Only the final summary is returned -- intermediate tool results "
            "never enter your context window.\n\n"
            "TWO MODES (one of 'goal' or 'tasks' is required):\n"
            "1. Single task: provide 'goal' (+ optional context, toolsets)\n"
            "2. Batch (parallel): provide 'tasks' array with up to 3 items. "
            "All run concurrently and results are returned together.\n\n"
            "WHEN TO USE delegate_task:\n"
            "- Reasoning-heavy subtasks (debugging, code review, research synthesis)\n"
            "- Tasks that would flood your context with intermediate data\n"
            "- Parallel independent workstreams (research A and B simultaneously)\n\n"
            "WHEN NOT TO USE (use these instead):\n"
            "- Mechanical multi-step work with no reasoning needed -> use execute_code\n"
            "- Single tool call -> just call the tool directly\n"
            "- Tasks needing user interaction -> subagents cannot use clarify\n\n"
            "IMPORTANT:\n"
            "- Subagents have NO memory of your conversation. Pass all relevant "
            "info (file paths, error messages, constraints) via the 'context' field.\n"
            "- Subagents CANNOT call: delegate_task, clarify, memory, send_message, "
            "execute_code.\n"
            "- Each subagent gets its own terminal session (separate working directory and state).\n"
            "- Results are always returned as an array, one entry per task."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": (
                        "What the subagent should accomplish. Be specific and "
                        "self-contained -- the subagent knows nothing about your "
                        "conversation history."
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Background information the subagent needs: file paths, "
                        "error messages, project structure, constraints. The more "
                        "specific you are, the better the subagent performs."
                    ),
                },
                "toolsets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Toolsets to enable for this subagent. "
                        "Default: inherits your enabled toolsets. "
                        "Common patterns: ['terminal', 'file'] for code work, "
                        "['web'] for research, ['terminal', 'file', 'web'] for "
                        "full-stack tasks."
                    ),
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string", "description": "Task goal"},
                            "context": {
                                "type": "string",
                                "description": "Task-specific context",
                            },
                            "toolsets": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Toolsets for this specific task. Use 'web' for network access, 'terminal' for shell.",
                            },
                        },
                        "required": ["goal"],
                    },
                    "maxItems": 3,
                    "description": (
                        "Batch mode: up to 3 tasks to run in parallel. Each gets "
                        "its own subagent with isolated context and terminal session. "
                        "When provided, top-level goal/context/toolsets are ignored."
                    ),
                },
                "max_iterations": {
                    "type": "integer",
                    "description": (
                        "Max tool-calling turns per subagent (default: 50). "
                        "Only set lower for simple tasks."
                    ),
                },
            },
            "required": [],
        },
    }

    def get_schema(self, llm_provider: str) -> dict:
        return self.DELEGATE_TASK_SCHEMA

    def do_invoke(self, tool_input: dict, **kwargs) -> str:
        goal = tool_input.get("goal", "")
        context = tool_input.get("context")
        toolsets = tool_input.get("toolsets")
        tasks = tool_input.get("tasks", [])
        max_iterations = tool_input.get("max_iterations", 50)
        final_tasks = []
        if not tasks:
            final_tasks.append(
                {
                    "goal": goal,
                    "context": context,
                    "toolsets": toolsets,
                }
            )
        else:
            final_tasks = tasks

        results = []
        n_tasks = len(final_tasks)
        if len(final_tasks) == 1:
            result = self._invoke_delegate_task(0, final_tasks[0], max_iterations)
            return json.dumps([result], ensure_ascii=False)
        else:
            # 批量执行模式
            # Batch -- run in parallel with per-task progress lines
            completed_count = 0
            task_labels = [t["goal"][:40] for t in final_tasks]

            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CHILDREN) as executor:
                futures = {}
                for i, child in enumerate(final_tasks):
                    future = executor.submit(
                        self._invoke_delegate_task(i, child, max_iterations),
                    )
                    futures[future] = i

                for future in as_completed(futures):
                    try:
                        entry = future.result()
                    except Exception as exc:
                        idx = futures[future]
                        entry = {
                            "task_index": idx,
                            "status": "error",
                            "summary": None,
                            "error": str(exc),
                            "api_calls": 0,
                            "duration_seconds": 0,
                        }
                    results.append(entry)
                    completed_count += 1

                    # Print per-task completion line above the spinner
                    idx = entry["task_index"]
                    label = (
                        task_labels[idx] if idx < len(task_labels) else f"Task {idx}"
                    )
                    dur = entry.get("duration_seconds", 0)
                    status = entry.get("status", "?")
                    icon = "✓" if status == "completed" else "✗"
                    completion_line = f"{icon} [{idx + 1}/{n_tasks}] {label}  ({dur}s)"
                    print(f"  {completion_line}")

            # Sort by task_index so results match input order
            results.sort(key=lambda r: r["task_index"])
            return json.dumps(results, ensure_ascii=False)

    def _invoke_delegate_task(
        self, task_index: int, task: dict, max_iterations: int
    ) -> Dict[str, Any]:
        task_start = time.monotonic()
        goal = task.get("goal", "")
        if not goal:
            raise ValueError("goal is required")
        context = task.get("context")
        toolsets = task.get("toolsets")
        system_prompt = self._build_child_system_prompt(
            goal, context, workspace_path=get_config().workspace_path
        )
        agent = Agent(
            system_prompt=system_prompt, tools=toolsets, max_turn=max_iterations
        )
        result = agent.invoke(goal)
        return self._build_child_result(task_index, result, task_start)

    def _build_child_result(
        self, task_index: int, result, task_start
    ) -> Dict[str, Any]:
        duration = round(time.monotonic() - task_start, 2)
        summary = result.get("final_response") or ""
        completed = result.get("completed", False)
        interrupted = result.get("interrupted", False)
        api_calls = result.get("api_calls", 0)

        if interrupted:
            status = "interrupted"
        elif summary:
            # A summary means the subagent produced usable output.
            # exit_reason ("completed" vs "max_iterations") already
            # tells the parent *how* the task ended.
            status = "completed"
        else:
            status = "failed"

        # Build tool trace from conversation messages (already in memory).
        # Uses tool_call_id to correctly pair parallel tool calls with results.
        tool_trace: list[Dict[str, Any]] = []
        trace_by_id: Dict[str, Dict[str, Any]] = {}
        messages = result.get("messages") or []
        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                if msg.get("role") == "assistant":
                    for tc in msg.get("tool_calls") or []:
                        fn = tc.get("function", {})
                        entry_t = {
                            "tool": fn.get("name", "unknown"),
                            "args_bytes": len(fn.get("arguments", "")),
                        }
                        tool_trace.append(entry_t)
                        tc_id = tc.get("id")
                        if tc_id:
                            trace_by_id[tc_id] = entry_t
                elif msg.get("role") == "tool":
                    content = msg.get("content", "")
                    is_error = bool(content and "error" in content[:80].lower())
                    result_meta = {
                        "result_bytes": len(content),
                        "status": "error" if is_error else "ok",
                    }
                    # Match by tool_call_id for parallel calls
                    tc_id = msg.get("tool_call_id")
                    target = trace_by_id.get(tc_id) if tc_id else None
                    if target is not None:
                        target.update(result_meta)
                    elif tool_trace:
                        # Fallback for messages without tool_call_id
                        tool_trace[-1].update(result_meta)

        # Determine exit reason
        if interrupted:
            exit_reason = "interrupted"
        elif completed:
            exit_reason = "completed"
        else:
            exit_reason = "max_iterations"

        entry: Dict[str, Any] = {
            "task_index": task_index,
            "status": status,
            "summary": summary,
            "api_calls": api_calls,
            "duration_seconds": duration,
            "exit_reason": exit_reason,
            "tool_trace": tool_trace,
        }
        if status == "failed":
            entry["error"] = result.get("error", "Subagent did not produce a response.")

        # todo debug
        print(entry)
        return entry

    def _build_child_system_prompt(
        selft,
        goal: str,
        context: Optional[str] = None,
        *,
        workspace_path: Optional[str] = None,
    ) -> str:
        """Build a focused system prompt for a child agent."""
        parts = [
            "You are a focused subagent working on a specific delegated task.",
            "",
            f"YOUR TASK:\n{goal}",
        ]
        if context and context.strip():
            parts.append(f"\nCONTEXT:\n{context}")
        if workspace_path and str(workspace_path).strip():
            parts.append(
                "\nWORKSPACE PATH:\n"
                f"{workspace_path}\n"
                "Use this exact path for local repository/workdir operations unless the task explicitly says otherwise."
            )
        parts.append(
            "\nComplete this task using the tools available to you. "
            "When finished, provide a clear, concise summary of:\n"
            "- What you did\n"
            "- What you found or accomplished\n"
            "- Any files you created or modified\n"
            "- Any issues encountered\n\n"
            "Important workspace rule: Never assume a repository lives at /workspace/... or any other container-style path unless the task/context explicitly gives that path. "
            "If no exact local path is provided, discover it first before issuing git/workdir-specific commands.\n\n"
            "Be thorough but concise -- your response is returned to the "
            "parent agent as a summary."
        )
        return "\n".join(parts)


registry.register("delegate_task", DelegateTool)
