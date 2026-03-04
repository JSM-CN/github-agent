"""LLM client for agent interactions - supports multiple providers."""

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from github_agent.config import LLMProvider, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified LLM client supporting multiple providers."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ):
        """Initialize LLM client.

        Args:
            api_key: API key (optional, uses settings if not provided)
            model: Model name (optional, uses settings if not provided)
            provider: Provider name (optional, uses settings if not provided)
        """
        settings = get_settings()
        self.provider = LLMProvider(provider.lower()) if provider else settings.provider
        self.api_key = api_key or settings.get_api_key()
        self.model = model or settings.default_model
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature
        self.base_url = settings.get_base_url()
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Get or create the appropriate client."""
        if self._client is None:
            if self.provider == LLMProvider.ANTHROPIC:
                import anthropic

                self._client = anthropic.Anthropic(api_key=self.api_key)
            else:
                # OpenAI-compatible providers (OpenAI, Qwen, DeepSeek, etc.)
                import openai

                if self.base_url:
                    self._client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
                else:
                    self._client = openai.OpenAI(api_key=self.api_key)
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a text response.

        Args:
            system_prompt: System prompt for the model
            user_message: User message/input
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Generated text response
        """
        if self.provider == LLMProvider.ANTHROPIC:
            return self._generate_anthropic(system_prompt, user_message, temperature, max_tokens)
        else:
            return self._generate_openai(system_prompt, user_message, temperature, max_tokens)

    def _generate_anthropic(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        """Generate using Anthropic API."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text_content = ""
        for block in message.content:
            if hasattr(block, "text"):
                text_content += block.text
        return text_content

    def _generate_openai(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        """Generate using OpenAI-compatible API."""
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""

    def generate_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Generate a structured response parsed into a Pydantic model.

        Args:
            system_prompt: System prompt for the model
            user_message: User message/input
            response_model: Pydantic model class for the response
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Parsed response as the specified model type
        """
        # Add JSON format instruction to system prompt
        enhanced_prompt = f"""{system_prompt}

IMPORTANT: You must respond with a valid JSON object that matches this schema:
{json.dumps(response_model.model_json_schema(), indent=2)}

Respond ONLY with the JSON object, no additional text."""

        response_text = self.generate(
            system_prompt=enhanced_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Clean up response - extract JSON if wrapped in markdown code blocks
        json_text = response_text.strip()
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            # Remove first and last lines if they're code block markers
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            json_text = "\n".join(lines).strip()

        # Parse and validate the response
        data = json.loads(json_text)
        return response_model.model_validate(data)


# Keep backward compatibility
ClaudeClient = LLMClient