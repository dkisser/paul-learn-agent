from openai import OpenAI

from agent.agent_type import Decision
from agent.config import get_config
from agent.llm.provider import LLMProvider, ProviderRegistry

_DEFAULT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search data what you need",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query content",
                    }
                },
                "required": ["query"]
            },
        }
    },
]

class OpenAIProvider(LLMProvider):
    """基于 OpenAI SDK 的 provider 实现。"""

    def __init__(self):
        config = get_config()
        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url or None,
        )
        self.model = config.openai_model

    def normalize(self, messages: list[dict]) -> list[dict]:
        """内部已是 OpenAI 格式，直接返回。"""
        return messages

    def complete(self, messages: list[dict]) -> Decision:
        messages = self.normalize(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=_DEFAULT_TOOLS
        )

        choice = response.choices[0].message
        text = choice.content or ""

        # 提取 tool calls
        tool_use = []
        tool_calls = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                tool_use.append(tc.function.name)
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })

        next_step = "tool_use" if tool_use else "done"

        return Decision(
            tool_use=tool_use,
            message=text,
            next_step=next_step,
            tool_calls=tool_calls,
        )


ProviderRegistry.register("openai", OpenAIProvider)
