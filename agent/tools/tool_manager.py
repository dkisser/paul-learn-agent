from typing import runtime_checkable, Protocol


def normalize_input(tool_input) -> dict:
    """对输入进行预处理，比如将字符串转换为字典"""
    # 如果tool_input是字符串，需要反序列换成一个 dict
    if isinstance(tool_input, str):
        import json
        return json.loads(tool_input)

    return tool_input


@runtime_checkable
class ToolsProvider(Protocol):
    """所有 Tools provider 都必须实现的协议"""
    def get_schema(self, llm_provider: str) -> dict:
        """获取不同provider下的工具定义
        (LLM不同，注册的tool格式也会不同，默认使用GPT的方式)"""
        ...

    def invoke(self, tool_input: dict, **kwargs) -> str:
        """调用工具"""
        try:
            input = normalize_input(tool_input)
        except Exception:
            return f"JSON Serialize Failed,invalid input. You must use json"
        return self.do_invoke(input, **kwargs)

    def do_invoke(self, tool_input: dict, **kwargs) -> str:
        """工具具体实现"""
        ...


class ToolsRegistry:
    """全局工具注册表，按名称映射到工具类"""

    _tools: dict[str, type[ToolsProvider]] = {}

    @classmethod
    def register(cls, name: str, tool_class: type[ToolsProvider]) -> None:
        cls._tools[name] = tool_class

    @classmethod
    def get(cls, name: str) -> ToolsProvider:
        if name not in cls._tools:
            available = list(cls._tools.keys())
            raise ValueError(
                f"Unknown tool: {name!r}. Available: {available}"
            )
        return cls._tools[name]()

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._tools.keys())

registry = ToolsRegistry()

import re

# 受保护的操作系统路径（前缀匹配）
_PROTECTED_PATHS = [
    " /sys", " /proc", " /boot", " /dev", " /etc", " /usr",
    " /var/lib/docker", " /run/docker", " /etc/docker",
    "C:\\", "D:\\", "E:\\", "F:\\", "G:\\", "H:\\",
]

# 危险删除命令的正则模式
_DANGEROUS_DELETE_RE = re.compile(
    r"\brm\s+(?:-[a-z]*[rf][a-z]*\s+)+"  # rm -rf, rm -rfv, rm -r -f
    r"|\brm\s+-[rf]\s+-[rf]\b"  # rm -r -f（分开选项）
    r"|\brm\s+--recursive\b",  # rm --recursive
    re.IGNORECASE,
)

# 终端写入操作检测
_REDIRECT_RE = re.compile(r"[^\"\']>\s*(\S+)")
_TEE_RE = re.compile(r"\btee\b")
_DD_WRITE_RE = re.compile(r"\bdd\b.*\bof=")


def _is_dangerous_delete(command: str) -> bool:
    return bool(_DANGEROUS_DELETE_RE.search(command))


def _touches_protected_path(command: str) -> bool:
    for p in _PROTECTED_PATHS:
        if p in command:
            # /dev/null 是安全的空设备，允许操作
            if p == " /dev" and "/dev/null" in command:
                continue
            return True
    # 根目录本身作为参数（如 "rm -rf /", "chmod 777 /"）
    if re.search(r'\s/\s*$|\s/\s', command):
        return True
    return False


def _is_write_command(command: str) -> bool:
    match = _REDIRECT_RE.search(command)
    if match and match.group(1) != "/dev/null":
        return True
    if _TEE_RE.search(command):
        return True
    if _DD_WRITE_RE.search(command):
        return True
    return False



def _is_root_delete(command: str) -> bool:
    """检测是否在删除根目录下的文件或目录（如 rm /file, rmdir /dir/subdir）。"""
    # 删除类命令：rm, rmdir, unlink
    if not re.search(r"\b(rm|rmdir|unlink)\b", command):
        return False
    # 目标在根目录下（/ 后跟非斜杠字符开头的路径，然后空格或行尾）
    return bool(re.search(r"\s/[^/\s][^\s]*(?:\s|$)", command))

def check_tool_permission(tool_name: str, tool_input) -> dict:
    """
    检查工具调用权限。

    规则优先级：
        1. deny rules（危险命令、操作系统路径）
        2. ask rules（写入操作）
        3. fallback (allow)

    :return: {"behavior": "allow" | "deny" | "ask", "reason": "Why this decision was made"}
    """
    input_json = normalize_input(tool_input)

    # deny rules
    if tool_name == "terminal":
        command = input_json.get("command", "")
        if _is_dangerous_delete(command):
            return {"behavior": "deny", "reason": f"Dangerous delete command detected: {command}"}
        if _touches_protected_path(command):
            return {"behavior": "deny", "reason": f"Command touches protected system path: {command}"}
        if _is_root_delete(command):
            return {"behavior": "deny", "reason": f"Delete operation on root directory detected: {command}"}
        if _is_write_command(command):
            return {"behavior": "ask", "reason": f"Write operation detected in terminal: {command}"}
        if re.search(r"\bsudo\b", command):
            return {"behavior": "ask", "reason": f"Sudo command detected: {command}"}

    # ask rules
    if tool_name == "write_file":
        path = input_json.get("path", "")
        return {"behavior": "ask", "reason": f"Write file operation: {path}"}

    # fallback
    return {"behavior": "allow", "reason": "No restrictions apply"}
