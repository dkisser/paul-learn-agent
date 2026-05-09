from typing import Any
from rich.console import Console
from rich.json import JSON
from agent.agent import Agent

console = Console()


def test_agent_loop_main():
    agent = Agent(
        system_prompt="""
        You are a helpful research agent.What you need is to find and thinking then answer
        """
    )

    question = "今天北京的天气怎样？"
    print(f"Task: {question}")
    res = agent.invoke(question).get("messages", [])
    print(f"Response: {res}")


def test_file_tool():

    agent = Agent(
        system_prompt="""
            You are a helpful coding agent.
            """
    )

    question = "帮我在桌面写个关于排序函数的对比和测试的demo"
    print(f"Task: {question}")
    res = agent.invoke(question).get("messages", [])
    print_result(res)


def test_terminal_tool():

    agent = Agent(
        system_prompt="""
            You are a helpful coding agent.
            """
    )

    question = "帮我安装一下ripgrep"
    print(f"Task: {question}")
    res = agent.invoke(question).get("messages", [])
    print_result(res)


def print_result(res: list[Any]):
    console.print("[bold green]Response:[/bold green]")
    for msg in res:
        console.print(f"[dim]role: {msg['role']}[/dim]")
        if msg.get("tool_calls"):
            console.print(f"Assistant: {msg['content']}", markup=False)
            console.print("Tool_Calls: ", JSON.from_data(msg["tool_calls"], indent=5))
        elif msg.get("content"):
            console.print(f"Assistant: {msg['content']}", markup=False)
        console.print()


def test_todo_tool():
    agent = Agent(
        system_prompt="""
            You are a helpful Travel Planning agent.
            """
    )

    question = "这周末我想从杭州出发去巴厘岛玩，有哪些好玩的景点，一个人怎么玩？机票、酒店、景点的路线帮我规划下比较经济的路线"
    print(f"Task: {question}")
    res = agent.invoke(question)
    messages = res.get("messages", [])
    print_result(messages)
    todo_store = res.get("todo_store")
    console.print(
        "Todo list", JSON.from_data(todo_store.read() if todo_store else {}, indent=2)
    )


def test_delegate_tool():
    agent = Agent(
        system_prompt="""
            You are a helpful Travel Planning agent.
            """
    )

    question = "这周末我想从杭州出发去巴厘岛玩，有哪些好玩的景点，一个人怎么玩？机票、酒店、景点的路线使用subagent帮我规划下比较经济的路线"
    print(f"Task: {question}")
    res = agent.invoke(question)
    messages = res.get("messages", [])
    print_result(messages)
    todo_store = res.get("todo_store")
    console.print(
        "Todo list", JSON.from_data(todo_store.read() if todo_store else {}, indent=2)
    )


def test_skill_tool():
    agent = Agent(
        system_prompt="""
                You are a helpful Coding agent.
                """,
        custom_skill_path="/Users/wenchen/workspace/py_project/paul-learn-agent/tests",
    )

    question = "帮我在写个排序算法，使用python，放在桌面。"
    print(f"Task: {question}")
    res = agent.invoke(question)
    messages = res.get("messages", [])
    print_result(messages)
    todo_store = res.get("todo_store")
    console.print(
        "Todo list", JSON.from_data(todo_store.read() if todo_store else {}, indent=2)
    )


def test_compression():
    agent = Agent(
        system_prompt="""
            You are a helpful Travel Planning agent.
            """
    )

    question = "这周末我想从杭州出发去巴厘岛玩，有哪些好玩的景点，一个人怎么玩？机票、酒店、景点的路线帮我规划下比较经济的路线。需要详细点，我完全不知道出入境手续，当地旅游注意事项等等，出个详细的攻略，越详细越好！！然后，你还需要规划下，从巴厘岛去法国的7天经济单人旅游路线，越详细越好。接着你还需要规划，从法国到美国的7天经济游，包括路线、酒店、机票。最后，我需要你帮我找找从美国回杭州的航班信息"
    print(f"Task: {question}")
    res = agent.invoke(question)
    messages = res.get("messages", [])
    print_result(messages)
    todo_store = res.get("todo_store")
    console.print(
        "Todo list", JSON.from_data(todo_store.read() if todo_store else {}, indent=2)
    )
