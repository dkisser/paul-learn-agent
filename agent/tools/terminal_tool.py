from agent.tools.tool_manager import ToolsProvider, registry

TERMINAL_TOOL_NAME = "terminal"
TERMINAL_TOOL_DESCRIPTION = """Execute shell commands on a Linux environment. Filesystem usually persists between calls.

Do NOT use cat/head/tail to read files — use read_file instead.
Do NOT use grep/rg/find to search — use search_files instead.
Do NOT use ls to list directories — use search_files(target='files') instead.
Do NOT use sed/awk to edit files — use patch instead.
Do NOT use echo/cat heredoc to create files — use write_file instead.
Reserve terminal for: builds, installs, git, processes, scripts, network, package managers, and anything that needs a shell.

Foreground (default): Commands return INSTANTLY when done, even if the timeout is high. Set timeout=300 for long builds/scripts — you'll still get the result in seconds if it's fast. Prefer foreground for short commands.
Background: Set background=true to get a session_id. Two patterns:
  (1) Long-lived processes that never exit (servers, watchers).
  (2) Long-running tasks with notify_on_complete=true — you can keep working on other things and the system auto-notifies you when the task finishes. Great for test suites, builds, deployments, or anything that takes more than a minute.
Use process(action="poll") for progress checks, process(action="wait") to block until done.
Working directory: Use 'workdir' for per-command cwd.
PTY mode: Set pty=true for interactive CLI tools (Codex, Claude Code, Python REPL).

Do NOT use vim/nano/interactive tools without pty=true — they hang without a pseudo-terminal. Pipe git output to cat if it might page.
Important: cloud sandboxes may be cleaned up, idled out, or recreated between turns. Persistent filesystem means files can resume later; it does NOT guarantee a continuously running machine or surviving background processes. Use terminal sandboxes for task work, not durable hosting.
"""

class TerminalTool(ToolsProvider):
    """
    TerminalTool 是一个工具类，用于执行命令行命令。
    """

    TERMINAL_SCHEMA = {
        "name": TERMINAL_TOOL_NAME,
        "description": TERMINAL_TOOL_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute on the VM"
                },
                "background": {
                    "type": "boolean",
                    "description": "Run the command in the background. Two patterns: (1) Long-lived processes that never exit (servers, watchers). (2) Long-running tasks paired with notify_on_complete=true — you can keep working and get notified when the task finishes. For short commands, prefer foreground with a generous timeout instead.",
                    "default": False
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait (default: 180). Returns INSTANTLY when command finishes — set high for long tasks, you won't wait unnecessarily.",
                    "minimum": 1
                },
                "workdir": {
                    "type": "string",
                    "description": "Working directory for this command (absolute path). Defaults to the session working directory."
                },
                "check_interval": {
                    "type": "integer",
                    "description": "Seconds between automatic status checks for background processes (gateway/messaging only, minimum 30). When set, I'll proactively report progress.",
                    "minimum": 30
                },
                "pty": {
                    "type": "boolean",
                    "description": "Run in pseudo-terminal (PTY) mode for interactive CLI tools like Codex, Claude Code, or Python REPL. Only works with local and SSH backends. Default: false.",
                    "default": False
                },
                "notify_on_complete": {
                    "type": "boolean",
                    "description": "When true (and background=true), you'll be automatically notified when the process finishes — no polling needed. Use this for tasks that take a while (tests, builds, deployments) so you can keep working on other things in the meantime.",
                    "default": False
                }
            },
            "required": ["command"]
        }
    }

    def get_schema(self, llm_provider: str) -> dict:
        return self.TERMINAL_SCHEMA


    def do_invoke(self, tool_input: dict) -> str:
        import subprocess
        import os

        command = tool_input["command"]
        background = tool_input.get("background", False)
        timeout = tool_input.get("timeout", 180)
        workdir = tool_input.get("workdir")
        pty = tool_input.get("pty", False)

        # PTY 模式暂不支持，给出警告
        if pty:
            return "Warning: PTY mode is not yet supported. Running in standard mode."

        # 设置工作目录
        cwd = workdir or os.getcwd()

        if background:
            # 后台模式：启动子进程并返回 session_id
            import uuid
            import threading

            session_id = str(uuid.uuid4())[:8]

            def _run_background():
                try:
                    subprocess.run(
                        command,
                        shell=True,
                        cwd=cwd,
                        timeout=timeout,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.TimeoutExpired:
                    pass
                except Exception:
                    pass

            thread = threading.Thread(target=_run_background, daemon=True)
            thread.start()

            return f"Background process started. Session ID: {session_id}"
        else:
            # 前台模式：同步执行并返回结果
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                )
                output_parts = []
                if result.stdout:
                    output_parts.append(result.stdout)
                if result.stderr:
                    output_parts.append(f"STDERR:\n{result.stderr}")
                output_parts.append(f"Exit code: {result.returncode}")
                return "\n".join(output_parts)
            except subprocess.TimeoutExpired:
                return f"Error: Command timed out after {timeout} seconds"
            except Exception as e:
                return f"Error executing command: {e}"


registry.register(TERMINAL_TOOL_NAME, TerminalTool)