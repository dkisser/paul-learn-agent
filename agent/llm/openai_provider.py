import json

from openai import OpenAI

from agent.agent_type import Decision
from agent.config import get_config
from agent.llm.provider import LLMProvider, ProviderRegistry
from agent.tools.tool_manager import registry

OPENAI_PROVIDER_NAME = "openai"

def _build_tools(llm_provider: str):
    tools = registry.available()
    result = []
    for tool_name in tools:
        tool = registry.get(tool_name)
        result.append({
            "type": "function",
            "function": tool.get_schema(llm_provider)
        })
    return result


class OpenAIProvider(LLMProvider):
    """基于 OpenAI SDK 的 provider 实现。"""

    def __init__(self):
        config = get_config()
        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url or None,
        )
        self.model = config.openai_model
        self.tools = _build_tools(OPENAI_PROVIDER_NAME)

    def normalize(self, messages: list[dict]) -> list[dict]:
        """内部已是 OpenAI 格式，直接返回。"""
        return messages

    def complete(self, messages: list[dict]) -> Decision:
        messages = self.normalize(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
        )

        choice = response.choices[0].message
        text = choice.content or ""

        # 提取 tool calls
        tool_calls = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })

        next_step = "tool_use" if tool_calls else "done"

        return Decision(
            message=text,
            next_step=next_step,
            tool_calls=tool_calls,
        )


ProviderRegistry.register(OPENAI_PROVIDER_NAME, OpenAIProvider)
