from pathlib import Path

from agent.agent import Agent

_PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    # system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    agent = Agent(system_prompt="""
    You are a helpful research agent.What you need is to find and thinking then answer
    """)

    question = "今天北京的天气怎样？"
    print(f"User: {question}")
    res = agent.invoke(question)
    print(f"AI: {res}")


if __name__ == "__main__":
    main()
