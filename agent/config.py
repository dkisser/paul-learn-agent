import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env from project root
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


class LLMConfig(BaseModel):
    model_config = {"populate_by_name": True}

    provider: str = Field(default="deepseek", alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")

    # Anthropic
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514", alias="ANTHROPIC_MODEL"
    )
    anthropic_base_url: str | None = Field(default=None, alias="ANTHROPIC_BASE_URL")

    # Agent root path
    workspace_path: str = Field(default="./", alias="WORKSPACE_PATH")


def get_config() -> LLMConfig:
    return LLMConfig.model_validate(os.environ)
