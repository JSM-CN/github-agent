"""Base agent class for all agents."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from github_agent.tools.claude import ClaudeClient
from github_agent.tools.github import GitHubClient

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class BaseAgent(ABC, Generic[InputType, OutputType]):
    """Base class for all agents in the system."""

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
        github_client: GitHubClient | None = None,
    ):
        """Initialize the base agent.

        Args:
            claude_client: Claude API client
            github_client: GitHub API client
        """
        self.claude_client = claude_client or ClaudeClient()
        self.github_client = github_client or GitHubClient()

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for logging and identification."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Agent description."""
        pass

    @abstractmethod
    async def execute(self, input_data: InputType) -> OutputType:
        """Execute the agent's main logic.

        Args:
            input_data: Input data for the agent

        Returns:
            Output data from the agent
        """
        pass

    def log(self, message: str) -> None:
        """Log a message with the agent name.

        Args:
            message: Message to log
        """
        from rich.console import Console

        console = Console()
        console.print(f"[bold blue][{self.name}][/bold blue] {message}")