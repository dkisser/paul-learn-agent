import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from agent.config import get_config
from agent.llm.provider import ProviderRegistry
from agent.prompt_builder import TOOL_USE_ENFORCEMENT_GUIDANCE
from agent.tools.todo_tool import TodoStore
from agent.tools.tool_manager import registry

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PROMPT_PATH = _PROJECT_ROOT / "resources" / "prompt" / "Research.txt"
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


class Agent:

    def __init__(
        self,
        max_turn: int = 20,
        tools=None,
        system_prompt: str = "",
    ):
        if tools is None:
            tools = _DEFAULT_TOOLS
        self.max_turn = max_turn
        self.system_prompt = system_prompt
        self.tools = tools
        self.current_turn = 0
        self.messages = []
        self.todo_store = TodoStore()

        #register tools
        self.tool_register()

    def tool_register(self):
        _modules = [
            "agent.tools.file_tool",
            "agent.tools.terminal_tool",
            "agent.tools.todo_tool",
        ]
        import importlib
        for mod_name in _modules:
            try:
                importlib.import_module(mod_name)
            except Exception as e:
                logger.warning("Could not import tool module %s: %s", mod_name, e)

    def _invoke_llm(self, messages) -> Decision:
        provider = ProviderRegistry.get(get_config().provider)
        decision = provider.complete(messages)
        self.current_turn += 1
        return decision

    def _invoke_tool(self, tool_name: str, tool_input: str) -> str:
        tool = registry.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool.invoke(tool_input, self.todo_store)

    def _build_system_prompt(
            self,
            enforce_tool_use: bool = False
    ):
        if not enforce_tool_use:
            return self.system_prompt
        else:
            return self.system_prompt + "\n" + TOOL_USE_ENFORCEMENT_GUIDANCE

    def _build_input(self, input: str) -> list:
        return [
            {"role": "system", "content": self._build_system_prompt(True)},
            {"role": "user", "content": input},
        ]


    def invoke(self, input: str):
        messages = self._build_input(input)
        self.messages = [*self.messages, *messages]
        while True:

            decision = self._invoke_llm(self.messages)

            # append to conversation history
            if decision.tool_calls:
                # 有 tool calls 时，assistant 消息需包含 tool_calls 字段
                self.messages.append({
                    "role": "assistant",
                    "content": decision.message,
                    "tool_calls": decision.tool_calls,
                })
            else:
                self.messages.append({"role": "assistant", "content": decision.message})

            if not decision.next_step == "tool_use":
                return {
                    "messages": self.messages,
                    "todo_store": self.todo_store
                }

            # tool_use
            for tool in decision.tool_calls:
                fn = tool['function']
                tool_result = self._invoke_tool(fn['name'], fn['arguments'])
                # 从 decision.tool_calls 中获取对应的 tool_call_id
                self._append_tool_result(decision, fn['name'], tool_result)

    def _append_tool_result(self, decision: Decision, tool_name, tool_result: str):
        tool_call_id = ""
        for tc in decision.tool_calls:
            if tc["function"]["name"] == tool_name:
                tool_call_id = tc["id"]
                break
        self.messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": tool_result}
        )
