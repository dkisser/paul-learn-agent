from typing import List, Dict

from agent.tools.tool_manager import ToolsProvider, registry
import json

VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


class TodoStore:

    """

        round_since_update: 连续多少轮过去了，模型还没有更新这份计划。(用于提醒模型去更新计划)
        items的每个数据结构如下：
            - id: 任务唯一标识
            - content: 当前任务的内容
            - status: pending | in_progress | completed | cancelled

    """
    def __init__(self):
        self.items: List[Dict[str, str]] = []
        self.rounds_since_update: int = 0

    def write (self, todos: List[Dict[str, str]], merge: bool = False):
        """
        Write todos. Returns the full current list after writing.

        Args:
            todos: list of {id, content, status} dicts
            merge: if False, replace the entire list. If True, update
                   existing items by id and append new ones.

        """

        if not merge:
            self.items = todos
            return self.items

        existing = {item["id"]: item for item in self.items}

        for todo in todos:
            item_id = todo['id']
            if not item_id:
                continue

            if item_id not in existing:
                self.items.append(todo)
            else:
                item = existing[item_id]
                item["content"] = todo["content"]
                item["status"] = todo["status"]

        return self.items

    def read(self):
        """
            deep copy of data
        """
        return {
            "items": [item.copy() for item in self.items],
            "rounds_since_update": self.rounds_since_update
        }


class TodoTool(ToolsProvider):

    TODO_SCHEMA = {
        "name": "todo",
        "description": (
            "Manage your task list for the current session. Use for complex tasks "
            "with 3+ steps or when the user provides multiple tasks. "
            "Call with no parameters to read the current list.\n\n"
            "Writing:\n"
            "- Provide 'todos' array to create/update items\n"
            "- merge=false (default): replace the entire list with a fresh plan\n"
            "- merge=true: update existing items by id, add any new ones\n\n"
            "Each item: {id: string, content: string, "
            "status: pending|in_progress|completed|cancelled}\n"
            "List order is priority. Only ONE item in_progress at a time.\n"
            "Mark items completed immediately when done. If something fails, "
            "cancel it and add a revised item.\n\n"
            "Always returns the full current list."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "Task items to write. Omit to read current list.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique item identifier"
                            },
                            "content": {
                                "type": "string",
                                "description": "Task description"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed", "cancelled"],
                                "description": "Current status"
                            }
                        },
                        "required": ["id", "content", "status"]
                    }
                },
                "merge": {
                    "type": "boolean",
                    "description": (
                        "true: update existing items by id, add new ones. "
                        "false (default): replace the entire list."
                    ),
                    "default": False
                }
            },
            "required": []
        }
    }


    def get_schema(self, llm_provider: str) -> dict:
        return self.TODO_SCHEMA

    def do_invoke(self, tool_input: dict, **kwargs) -> str:
        todo_store = kwargs.get("todo_store")
        if todo_store is None:
            raise ValueError("todo_store is required")
        todo_store.write(tool_input.get("todos", []), tool_input.get("merge", False))
        return json.dumps(todo_store.read(), ensure_ascii=False)

registry.register("todo", TodoTool)