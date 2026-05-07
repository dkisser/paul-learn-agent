from __future__ import annotations

import json

from anthropic import Anthropic

from agent.agent_type import Decision
from agent.config import get_config
from agent.llm.provider import LLMProvider, ProviderRegistry

ANTHROPIC_PROVIDER_NAME = "anthropic"

class AnthropicProvider(LLMProvider):
    """基于 Anthropic SDK 的 provider 实现。

    Anthropic 的消息格式与 OpenAI 不同：
    - system 是独立参数，不在 messages 列表中
    - 需要 max_tokens 参数
    - assistant tool_use 用内容块表示
    - tool result 是 user 消息中的 tool_result 内容块
    normalize() 统一处理这些差异。
    """

    def __init__(self):
        config = get_config()
        self.client = Anthropic(
            api_key=config.anthropic_api_key,
            base_url=config.anthropic_base_url or None,
        )
        self.model = config.anthropic_model

    def normalize(self, messages: list[dict]) -> dict:
        """将内部 OpenAI 格式消息转为 Anthropic 原生格式。

        返回 {"system": str | None, "messages": list[dict]}
        """
        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "user":
                anthropic_messages.append(
                    {"role": "user", "content": msg["content"]}
                )
            elif msg["role"] == "assistant":
                if msg.get("tool_calls"):
                    content_blocks = []
                    text = msg.get("content", "")
                    if text:
                        content_blocks.append({"type": "text", "text": text})
                    for tc in msg["tool_calls"]:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"]),
                        })
                    anthropic_messages.append(
                        {"role": "assistant", "content": content_blocks}
                    )
                else:
                    anthropic_messages.append(
                        {"role": "assistant", "content": msg["content"]}
                    )
            elif msg["role"] == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                content = msg.get("content", "")
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": content,
                        }
                    ],
                })

        return {
            "system": system_msg if system_msg else None,
            "messages": anthropic_messages,
        }

    def complete(self, messages: list[dict], tools=None) -> Decision:
        normalized = self.normalize(messages)
        response = self.client.messages.create(
            model=self.model,
            system=normalized["system"],
            messages=normalized["messages"],
            max_tokens=4096,
        )

        text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input, ensure_ascii=False),
                    }
                })

        next_step = "tool_use" if tool_calls else "done"

        return Decision(
            message=text,
            next_step=next_step,
            tool_calls=tool_calls,
        )


ProviderRegistry.register(ANTHROPIC_PROVIDER_NAME, AnthropicProvider)
