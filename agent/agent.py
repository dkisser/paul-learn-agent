import json
import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

import openai

from agent.config import get_config
from agent.context_compressor import ContextCompressor, estimate_messages_tokens_rough
from agent.llm.provider import ProviderRegistry
from agent.prompt_builder import (
    TOOL_USE_ENFORCEMENT_GUIDANCE,
    SKILL_ENFORCEMENT_GUIDANCE,
)
from agent.tools.skills_tool import SkillsStore
from agent.tools.todo_tool import TodoStore
from agent.tools.tool_manager import registry

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


@dataclass
class AgentStatus(Enum):
    PENDING = auto()
    HUMAN_IN_LOOP = auto()
    EXECUTING = auto()


@dataclass
class AgentState:
    turn: int
    status: AgentStatus


from agent.agent_type import Decision


def tool_register():
    _modules = [
        "agent.tools.file_tool",
        "agent.tools.terminal_tool",
        "agent.tools.todo_tool",
        "agent.tools.delegate_tool",
        "agent.tools.skills_tool",
    ]
    import importlib

    for mod_name in _modules:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            logger.warning("Could not import tool module %s: %s", mod_name, e)


def _build_tools(llm_provider: str, tool_names: list[str] = None):
    tools = registry.available()
    result = []
    for tool_name in tools:
        if tool_names and tool_name not in tool_names:
            continue
        tool = registry.get(tool_name)
        result.append({"type": "function", "function": tool.get_schema(llm_provider)})
    return result


class Agent:
    def __init__(
        self,
        max_turn: int = 20,
        tools=None,
        system_prompt: str = "",
        workspace_path: str = None,
        custom_skill_path: str = None,
    ):

        # register tools
        tool_register()

        self.max_turn = max_turn
        self.system_prompt = system_prompt
        self.tools = _build_tools(get_config().provider, tools)
        self.current_turn = 0
        self.messages = []
        self.todo_store = TodoStore()
        self.workspace_path = workspace_path or get_config().workspace_path
        self.custom_skill_path = custom_skill_path
        self.skill_store = SkillsStore(
            workspace_path=custom_skill_path or self.workspace_path
        )
        self.cnotext_compressor = ContextCompressor(provider=get_config().provider)

    def _invoke_llm(self, messages) -> Decision:
        provider = ProviderRegistry.get(get_config().provider)
        decision = provider.complete(messages, self.tools)
        self.current_turn += 1
        return decision

    @staticmethod
    def _is_retryable_error(e: Exception) -> bool:
        """判断异常是否可重试（服务端繁忙/限流/连接问题）。"""
        # OpenAI SDK 的 HTTP 状态码异常
        if hasattr(e, "status_code"):
            code = e.status_code
            # 429 限流、500 服务端错误、502 网关错误、503 服务不可用、504 网关超时
            return code in (429, 500, 502, 503, 504)
        # 连接和超时错误
        if isinstance(e, (openai.APIConnectionError, openai.APITimeoutError)):
            return True
        return False

    def _invoke_tool(self, tool_name: str, tool_input: str) -> str:
        tool = registry.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        params = {
            "todo_store": self.todo_store,
            "skill_store": self.skill_store,
        }
        return tool.invoke(tool_input, **params)

    def _build_system_prompt(self, enforce_tool_use: bool = False):
        if not enforce_tool_use:
            return self.system_prompt

        skill_list = self.skill_store.skill_list()
        parts = [self.system_prompt, TOOL_USE_ENFORCEMENT_GUIDANCE]

        if skill_list:
            skills = "\n".join(
                f" - {skill['name']}: {skill['description']}" for skill in skill_list
            )
            parts.append(SKILL_ENFORCEMENT_GUIDANCE.format(SKILLS=skills))

        return "\n".join(parts)

    def _build_input(self, input: str) -> list:
        return [
            {"role": "system", "content": self._build_system_prompt(True)},
            {"role": "user", "content": input},
        ]

    def _normalize_messages(self, messages):
        """合并连续的同角色消息，避免 API 报错。"""
        if not messages:
            return messages

        normalized = [messages[0]]
        for msg in messages[1:]:
            last = normalized[-1]
            # 合并连续的 user 消息
            if msg.get("role") == "user" and last.get("role") == "user":
                last["content"] = f"{last.get('content', '')}\n{msg.get('content', '')}"
                continue
            # 合并连续的 assistant 消息（都不含 tool_calls）
            if (
                msg.get("role") == "assistant"
                and last.get("role") == "assistant"
                and not msg.get("tool_calls")
                and not last.get("tool_calls")
            ):
                last["content"] = f"{last.get('content', '')}\n{msg.get('content', '')}"
                continue
            normalized.append(msg)
        return normalized

    def invoke(self, input: str):
        messages = self._build_input(input)
        self.messages = [*self.messages, *messages]
        while True:
            # max turn check
            if self.current_turn >= self.max_turn:
                return {
                    "messages": self.messages,
                    "todo_store": self.todo_store,
                    "final_response": "Maximum turn exceeded",
                    "completed": False,
                    "interrupted": False,
                    "api_calls": len(
                        [m for m in self.messages if m.get("role") == "tool"]
                    ),
                }

            try:
                normalized_messages = self._normalize_messages(self.messages)
                self.messages = self._compact(self.messages, normalized_messages)
                decision = self._invoke_llm(self.messages)
            except Exception as e:
                logger.error("LLM call failed, messages: %s", json.dumps(self.messages, ensure_ascii=False))
                if self._is_retryable_error(e):
                    logger.warning(
                        "LLM call failed with retryable error: %s. Retrying in 5s...", e
                    )
                    time.sleep(5)
                    continue
                raise

            # append to conversation history
            assistant_msg: dict = {
                "role": "assistant",
                "content": decision.message,
            }
            if decision.reasoning_content:
                assistant_msg["reasoning_content"] = decision.reasoning_content
            if decision.tool_calls:
                assistant_msg["tool_calls"] = decision.tool_calls
            self.messages.append(assistant_msg)

            if not decision.next_step == "tool_use":
                return {
                    "messages": self.messages,
                    "todo_store": self.todo_store,
                    "skill_store": self.skill_store,
                    "final_response": self.messages[-1].get("content"),
                    "completed": True,
                    "interrupted": False,
                    "api_calls": len(
                        [m for m in self.messages if m.get("role") == "tool"]
                    ),
                }

            # tool_use
            for tool in decision.tool_calls:
                fn = tool["function"]
                tool_result = self._invoke_tool(fn["name"], fn["arguments"])
                self._append_tool_result(tool["id"], tool_result)

    def _compact(self, messages: list, normalized_messages: list):
        _compressor = self.cnotext_compressor
        if _compressor.threshold_tokens > 0:
            # todo 暂时不在每次请求结束之后做token统计并缓存，后面优化
            if _compressor.last_prompt_tokens > 0:
                _real_tokens = (
                        _compressor.last_prompt_tokens
                        + _compressor.last_completion_tokens
                )
            else:
                _real_tokens = estimate_messages_tokens_rough(messages)

            if _compressor.should_compress(_real_tokens):
                return _compressor.compress(
                    normalized_messages
                )
        return messages

    def _append_tool_result(self, tool_call_id: str, tool_result: str):
        self.messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": tool_result}
        )
