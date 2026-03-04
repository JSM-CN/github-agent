"""Module 1: Product & Repo Understanding Agent.

Analyzes PRD documents and GitHub repositories to generate insights.
"""

import json

from github_agent.agents.base import BaseAgent
from github_agent.models import ProjectAnalysis
from github_agent.tools.claude import ClaudeClient
from github_agent.tools.github import GitHubClient


class RepoUnderstandingAgent(BaseAgent[str, ProjectAnalysis]):
    """Agent for understanding product requirements and repository structure."""

    SYSTEM_PROMPT = """You are an expert software architect and product analyst. Your task is to analyze a product requirements document (PRD) along with a GitHub repository to provide:

1. **Feasibility Assessment**: Evaluate whether the requested changes can be implemented given the current codebase.
2. **Risk Identification**: Identify potential risks, technical debt, and challenges.
3. **Improvement Suggestions**: Provide actionable improvement suggestions with priorities.

When analyzing, consider:
- Code architecture and patterns used
- Existing functionality and how new features integrate
- Potential breaking changes
- Testing requirements
- Documentation needs

Be thorough but concise. Focus on actionable insights."""

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
        github_client: GitHubClient | None = None,
    ):
        """Initialize the repo understanding agent.

        Args:
            claude_client: Claude API client
            github_client: GitHub API client
        """
        super().__init__(claude_client, github_client)

    @property
    def name(self) -> str:
        return "RepoUnderstandingAgent"

    @property
    def description(self) -> str:
        return "Analyzes PRD documents and repository structure to generate insights"

    async def execute(
        self,
        input_data: str,
        repo_url: str,
        branch: str = "main",
    ) -> ProjectAnalysis:
        """Execute the analysis.

        Args:
            input_data: PRD content
            repo_url: GitHub repository URL
            branch: Branch to analyze

        Returns:
            ProjectAnalysis with feasibility, risks, and improvements
        """
        self.log(f"Analyzing repository: {repo_url}")

        # Gather repository information
        self.log("Fetching repository structure...")
        structure = await self.github_client.get_repo_structure(repo_url, branch)

        self.log("Fetching README...")
        readme = await self.github_client.get_readme(repo_url, branch)

        self.log("Fetching recent issues...")
        issues = await self.github_client.get_issues(repo_url, state="open", limit=10)

        # Build context for analysis
        context = self._build_analysis_context(
            prd=input_data,
            structure=structure,
            readme=readme,
            issues=issues,
        )

        # Generate analysis using Claude
        self.log("Generating analysis with Claude...")
        analysis = self.claude_client.generate_structured(
            system_prompt=self.SYSTEM_PROMPT,
            user_message=context,
            response_model=ProjectAnalysis,
            temperature=0.3,  # Lower temperature for more consistent analysis
        )

        # Add project structure to analysis
        analysis.project_structure = structure

        self.log(f"Analysis complete. Feasibility: {analysis.feasibility.value}")
        return analysis

    def _build_analysis_context(
        self,
        prd: str,
        structure: dict,
        readme: str,
        issues: list[dict],
    ) -> str:
        """Build the context string for analysis.

        Args:
            prd: PRD content
            structure: Repository structure
            readme: README content
            issues: List of open issues

        Returns:
            Formatted context string
        """
        # Format structure info
        structure_info = json.dumps(structure, indent=2, ensure_ascii=False)

        # Format issues
        issues_info = ""
        if issues:
            issues_info = "\n\nOpen Issues:\n"
            for issue in issues[:5]:
                issues_info += f"- #{issue.get('number', '?')}: {issue.get('title', 'N/A')}\n"

        # Combine all context
        context = f"""# Product Requirements Document (PRD)

{prd}

---

# Repository Structure

{structure_info}

---

# README Content

{readme[:3000]}  # Truncate to avoid token limits

---
{issues_info}
"""
        return context