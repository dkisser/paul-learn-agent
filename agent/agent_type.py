from dataclasses import dataclass, field


@dataclass
class Decision:
    tool_use: list = field(default_factory=list)
    message: str = ""
    next_step: str = "done"
    tool_calls: list = field(default_factory=list)
