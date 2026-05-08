from typing import runtime_checkable, Protocol


@runtime_checkable
class ToolsProvider(Protocol):
    """所有 Tools provider 都必须实现的协议"""
    def get_schema(self, llm_provider: str) -> dict:
        """获取不同provider下的工具定义
        (LLM不同，注册的tool格式也会不同，默认使用GPT的方式)"""
        ...

    def normalize_input(self, tool_input) -> dict:
        """对输入进行预处理，比如将字符串转换为字典"""
        # 如果tool_input是字符串，需要反序列换成一个 dict
        if isinstance(tool_input, str):
            import json
            return json.loads(tool_input)

        return tool_input

    def invoke(self, tool_input: dict, **kwargs) -> str:
        """调用工具"""
        try:
            input = self.normalize_input(tool_input)
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