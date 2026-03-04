"""Configuration management for GitHub Agent."""

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    CUSTOM = "custom"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    openai_api_key: str = Field(default="", description="OpenAI API key (or compatible)")
    github_token: str = Field(default="", description="GitHub personal access token")

    # LLM Provider Configuration
    llm_provider: str = Field(
        default="anthropic",
        description="LLM provider: anthropic, openai, qwen, deepseek, custom",
    )
    default_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Default model to use",
    )
    llm_base_url: str = Field(
        default="",
        description="Base URL for LLM API (for custom/self-hosted models)",
    )

    # GitHub Configuration
    github_base_url: str = Field(
        default="https://api.github.com", description="GitHub API base URL"
    )

    # Generation Parameters
    max_tokens: int = Field(default=4096, description="Maximum tokens for responses")
    temperature: float = Field(default=0.7, description="Temperature for generation")

    # Workflow Configuration
    default_target_branch: str = Field(default="main", description="Default target branch")
    branch_prefix: str = Field(
        default="auto-pr", description="Prefix for auto-generated branches"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    @property
    def provider(self) -> LLMProvider:
        """Get the LLM provider enum."""
        return LLMProvider(self.llm_provider.lower())

    @property
    def is_configured(self) -> bool:
        """Check if required API keys are configured."""
        if self.provider == LLMProvider.ANTHROPIC:
            return bool(self.anthropic_api_key and self.github_token)
        else:
            # For OpenAI-compatible providers, use openai_api_key
            return bool(self.openai_api_key or self.anthropic_api_key)

    def get_api_key(self) -> str:
        """Get the appropriate API key for the current provider."""
        if self.provider == LLMProvider.ANTHROPIC:
            return self.anthropic_api_key
        return self.openai_api_key or self.anthropic_api_key

    def get_base_url(self) -> str | None:
        """Get the base URL for the current provider."""
        if self.llm_base_url:
            return self.llm_base_url

        # Default base URLs for different providers
        if self.provider == LLMProvider.QWEN:
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        elif self.provider == LLMProvider.DEEPSEEK:
            return "https://api.deepseek.com/v1"
        return None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()