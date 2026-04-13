import pytest
import time
import threading

from agent.tools.terminal_tool import TerminalTool


@pytest.fixture
def terminal():
    return TerminalTool()


class TestTerminalToolForeground:
    def test_simple_command(self, terminal):
        result = terminal.invoke({"command": "echo hello"})
        assert "hello" in result
        assert "Exit code: 0" in result

    def test_command_with_stderr(self, terminal):
        result = terminal.invoke({"command": "python -c \"import sys; print('out'); print('err', file=sys.stderr)\""})
        assert "out" in result
        assert "err" in result
        assert "STDERR:" in result
        assert "Exit code: 0" in result

    def test_nonzero_exit_code(self, terminal):
        result = terminal.invoke({"command": "python -c \"exit(42)\""})
        assert "Exit code: 42" in result

    def test_command_timeout(self, terminal):
        result = terminal.invoke({"command": "sleep 10", "timeout": 1})
        assert "timed out" in result

    def test_command_with_workdir(self, terminal, tmp_path):
        result = terminal.invoke({"command": "pwd", "workdir": str(tmp_path)})
        assert str(tmp_path) in result

    def test_chained_commands(self, terminal):
        result = terminal.invoke({"command": "echo foo && echo bar"})
        assert "foo" in result
        assert "bar" in result

    def test_invalid_command(self, terminal):
        # 命令本身合法，只是执行会报错（比如不存在的命令）
        result = terminal.invoke({"command": "nonexistent_command_xyz_123"})
        assert "Exit code:" in result


class TestTerminalToolBackground:
    def test_background_returns_session_id(self, terminal):
        result = terminal.invoke({"command": "sleep 2", "background": True})
        assert "Background process started" in result
        assert "Session ID:" in result

    def test_background_process_actually_runs(self, terminal, tmp_path):
        """验证后台进程确实在执行：写一个标记文件"""
        marker = tmp_path / "bg_done"
        cmd = f"python -c \"import time; time.sleep(0.5); open('{marker}', 'w').close()\""
        result = terminal.invoke({"command": cmd, "background": True})
        assert "Background process started" in result

        # 等待后台进程完成
        time.sleep(1.0)
        assert marker.exists()


class TestTerminalToolSchema:
    def test_schema_has_required_fields(self, terminal):
        schema = terminal.get_schema("")
        props = schema["parameters"]["properties"]
        assert "command" in props
        assert "background" in props
        assert "timeout" in props
        assert "workdir" in props
        assert "command" in schema["parameters"]["required"]
