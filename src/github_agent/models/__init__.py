"""Data models for the GitHub Agent system."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Priority(str, Enum):
    """Priority levels for improvements."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Feasibility(str, Enum):
    """Feasibility assessment levels."""

    FEASIBLE = "feasible"
    PARTIALLY_FEASIBLE = "partially_feasible"
    NOT_FEASIBLE = "not_feasible"


class Improvement(BaseModel):
    """A single improvement suggestion."""

    module: str = Field(description="Module or component name")
    suggestion: str = Field(description="The improvement suggestion")
    priority: Priority = Field(description="Priority level")
    rationale: str = Field(default="", description="Why this improvement matters")


class ProjectAnalysis(BaseModel):
    """Result of PRD and repo analysis."""

    feasibility: Feasibility = Field(description="Overall feasibility assessment")
    risks: list[str] = Field(default_factory=list, description="Identified risks")
    improvements: list[Improvement] = Field(
        default_factory=list, description="Improvement suggestions"
    )
    project_structure: dict[str, Any] = Field(
        default_factory=dict, description="Analyzed project structure"
    )
    summary: str = Field(default="", description="Brief summary of the analysis")


class CodeChange(BaseModel):
    """A code change to be applied."""

    file_path: str = Field(description="Path to the file to modify")
    change_type: str = Field(description="Type of change: create, modify, delete")
    content: str = Field(description="New content or patch")
    description: str = Field(description="Description of the change")


class GeneratedCode(BaseModel):
    """Result of code generation."""

    changes: list[CodeChange] = Field(default_factory=list, description="List of code changes")
    commit_message: str = Field(description="Git commit message")
    pr_title: str = Field(description="Pull request title")
    pr_description: str = Field(description="Pull request description")
    test_instructions: str = Field(
        default="", description="Instructions for testing the changes"
    )


class PullRequestResult(BaseModel):
    """Result of PR creation."""

    success: bool = Field(description="Whether PR was created successfully")
    pr_url: str | None = Field(default=None, description="URL of the created PR")
    pr_number: int | None = Field(default=None, description="PR number")
    branch_name: str | None = Field(default=None, description="Branch name used")
    error: str | None = Field(default=None, description="Error message if failed")


class WorkflowState(BaseModel):
    """State of the workflow execution."""

    request_id: str = Field(description="Unique request identifier")
    prd_content: str = Field(description="Product requirements document content")
    repo_url: str = Field(description="GitHub repository URL")
    target_branch: str = Field(default="main", description="Target branch for PR")
    analysis: ProjectAnalysis | None = Field(default=None, description="Project analysis result")
    generated_code: GeneratedCode | None = Field(
        default=None, description="Generated code result"
    )
    pr_result: PullRequestResult | None = Field(
        default=None, description="PR creation result"
    )
    status: str = Field(default="pending", description="Current workflow status")
    error: str | None = Field(default=None, description="Error message if any")


class AgentRequest(BaseModel):
    """Request model for the API."""

    prd_content: str = Field(description="Product requirements document content")
    repo_url: str = Field(description="GitHub repository URL (e.g., https://github.com/owner/repo)")
    target_branch: str = Field(default="main", description="Target branch for PR")
    github_token: str | None = Field(
        default=None, description="GitHub personal access token (optional, can use env var)"
    )
    anthropic_api_key: str | None = Field(
        default=None, description="Anthropic API key (optional, can use env var)"
    )


class AgentResponse(BaseModel):
    """Response model for the API."""

    request_id: str = Field(description="Unique request identifier")
    status: str = Field(description="Workflow status")
    message: str = Field(description="Human-readable status message")
    analysis: ProjectAnalysis | None = Field(
        default=None, description="Project analysis if completed"
    )
    pr_result: PullRequestResult | None = Field(
        default=None, description="PR result if completed"
    )
    error: str | None = Field(default=None, description="Error message if any")