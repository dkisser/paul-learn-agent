from agent.agent import Agent


def test_agent_loop_main():
    agent = Agent(system_prompt="""
        You are a helpful research agent.What you need is to find and thinking then answer
        """)

    question = "今天北京的天气怎样？"
    print(f"User: {question}")
    res = agent.invoke(question)
    print(f"AI: {res}")


def test_file_tool():
    from rich.console import Console
    from rich.json import JSON

    console = Console()

    agent = Agent(system_prompt="""
            You are a helpful coding agent.
            """)

    question = "帮我在桌面写个关于排序函数的对比和测试的demo"
    print(f"User: {question}")
    res = agent.invoke(question)
    console.print("[bold green]AI:[/bold green]")
    for msg in res:
        console.print(f"[dim]role: {msg['role']}[/dim]")
        if msg.get("tool_calls"):
            console.print(JSON.from_data(msg["tool_calls"], indent=2))
        elif msg.get("content"):
            console.print(msg["content"])
        console.print()

def test_terminal_tool():
    from rich.console import Console
    from rich.json import JSON

    console = Console()

    agent = Agent(system_prompt="""
            You are a helpful coding agent.
            """)

    question = "帮我安装一下ripgrep"
    print(f"User: {question}")
    res = agent.invoke(question)
    console.print("[bold green]AI:[/bold green]")
    for msg in res:
        console.print(f"[dim]role: {msg['role']}[/dim]")
        if msg.get("tool_calls"):
            console.print(JSON.from_data(msg["tool_calls"], indent=2))
        elif msg.get("content"):
            console.print(msg["content"])
        console.print()