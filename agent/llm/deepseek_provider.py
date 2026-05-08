import openai
from openai import OpenAI

from agent.agent_type import Decision
from agent.config import get_config
from agent.llm.provider import LLMProvider, ProviderRegistry

DEEPSEEK_PROVIDER_NAME = "deepseek"


class DeepSeekProvider(LLMProvider):
    """基于 OpenAI SDK 的 DeepSeek provider 实现。

    DeepSeek API 兼容 OpenAI 格式，但 reasoning 模型要求
    在多轮对话中传回 reasoning_content 字段。
    """

    def __init__(self):
        config = get_config()
        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url or None,
        )
        self.model = config.openai_model

    def normalize(self, messages: list[dict]) -> list[dict]:
        """保留 assistant 消息中的 reasoning_content（DeepSeek reasoning 模型需要）。"""
        normalized = []
        for msg in messages:
            new_msg = dict(msg)
            if msg.get("role") == "assistant" and "reasoning_content" in msg:
                new_msg["reasoning_content"] = msg["reasoning_content"]
            normalized.append(new_msg)
        return normalized

    def complete(self, messages: list[dict], tools=None) -> Decision:
        messages = self.normalize(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )

        # 防御：服务端极端繁忙时 response 可能为 None
        if response is None or not getattr(response, "choices", None):
            raise openai.InternalServerError(
                "Empty response from DeepSeek API (service likely overloaded)",
                response=None,
                body=None,
            )

        choice = response.choices[0].message
        text = choice.content or ""

        # 提取 reasoning_content（DeepSeek reasoning 模型特有）
        reasoning_content = getattr(choice, "reasoning_content", None) or ""

        # 提取 tool calls
        tool_calls = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        next_step = "tool_use" if tool_calls else "done"

        return Decision(
            message=text,
            next_step=next_step,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )


ProviderRegistry.register(DEEPSEEK_PROVIDER_NAME, DeepSeekProvider)
