import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

import openai

from agent.config import get_config
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
        else:
            skills = "\n".join(
                [
                    f" - {skill['name']}: {skill['description']}"
                    for skill in self.skill_store.skill_list()
                ]
            )
            skill_guidance = SKILL_ENFORCEMENT_GUIDANCE.format(SKILLS=skills)
            return (
                self.system_prompt
                + "\n"
                + TOOL_USE_ENFORCEMENT_GUIDANCE
                + "\n"
                + skill_guidance
            )

    def _build_input(self, input: str) -> list:
        return [
            {"role": "system", "content": self._build_system_prompt(True)},
            {"role": "user", "content": input},
        ]

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
                decision = self._invoke_llm(self.messages)
            except Exception as e:
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
                # 从 decision.tool_calls 中获取对应的 tool_call_id
                self._append_tool_result(decision, fn["name"], tool_result)

    def _append_tool_result(self, decision: Decision, tool_name, tool_result: str):
        tool_call_id = ""
        for tc in decision.tool_calls:
            if tc["function"]["name"] == tool_name:
                tool_call_id = tc["id"]
                break
        self.messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": tool_result}
        )
