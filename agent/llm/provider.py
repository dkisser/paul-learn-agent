from __future__ import annotations

from typing import Protocol, runtime_checkable

from agent.agent_type import Decision


@runtime_checkable
class LLMProvider(Protocol):
    """所有 LLM provider 必须实现的协议。

    内部消息统一使用 OpenAI 格式：
        [{"role": "system"|"user"|"assistant"|"tool", ...}]

    每个 provider 在 complete() 开始时调用 normalize() 转换为自身格式。
    """

    def normalize(self, messages: list[dict]) -> list[dict]:
        """将内部消息格式转换为 provider 原生格式。"""
        ...

    def complete(self, messages: list[dict], tools=None) -> Decision:
        """向 LLM 发送消息并返回标准化的 Decision。
        :param tools:
        """
        ...


class ProviderRegistry:
    """全局 provider 注册表，按名称映射到 provider 类。"""

    _providers: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]) -> None:
        cls._providers[name] = provider_class

    @classmethod
    def get(cls, name: str) -> LLMProvider:
        if name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: {name!r}. Available: {available}"
            )
        return cls._providers[name]()

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._providers.keys())
