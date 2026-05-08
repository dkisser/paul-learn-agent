from dataclasses import dataclass, field


@dataclass
class Decision:
    message: str = ""
    next_step: str = "done"
    tool_calls: list = field(default_factory=list)
    reasoning_content: str = ""
