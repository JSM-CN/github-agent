"""Module 4: Code Generation Agent.

Generates code changes based on improvement suggestions.
"""

import json

from github_agent.agents.base import BaseAgent
from github_agent.models import CodeChange, GeneratedCode, Improvement, ProjectAnalysis
from github_agent.tools.claude import ClaudeClient
from github_agent.tools.github import GitHubClient


class CodeGenerationAgent(BaseAgent[ProjectAnalysis, GeneratedCode]):
    """Agent for generating code changes from analysis."""

    SYSTEM_PROMPT = """You are an expert software engineer specializing in code generation and refactoring. Your task is to generate code changes based on improvement suggestions.

When generating code:
1. Follow the existing code style and patterns in the repository
2. Ensure backward compatibility where possible
3. Include proper error handling
4. Add type hints if the project uses them
5. Consider edge cases and potential issues

Generate changes that are:
- Minimal and focused (don't over-engineer)
- Well-documented with clear comments
- Following best practices for the language/framework used
- Ready to be committed without further modification

Always provide clear commit messages and PR descriptions that explain:
- What changes were made
- Why they were made
- How to test them"""

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
        github_client: GitHubClient | None = None,
    ):
        """Initialize the code generation agent.

        Args:
            claude_client: Claude API client
            github_client: GitHub API client
        """
        super().__init__(claude_client, github_client)

    @property
    def name(self) -> str:
        return "CodeGenerationAgent"

    @property
    def description(self) -> str:
        return "Generates code changes based on improvement suggestions"

    async def execute(
        self,
        input_data: ProjectAnalysis,
        repo_url: str,
        branch: str = "main",
        max_changes: int = 3,
    ) -> GeneratedCode:
        """Execute code generation.

        Args:
            input_data: Project analysis with improvements
            repo_url: GitHub repository URL
            branch: Branch to base changes on
            max_changes: Maximum number of changes to generate

        Returns:
            GeneratedCode with changes, commit message, and PR info
        """
        self.log(f"Generating code for {len(input_data.improvements)} improvements")

        # Filter to high priority improvements first
        prioritized_improvements = self._prioritize_improvements(
            input_data.improvements, max_changes
        )

        if not prioritized_improvements:
            self.log("No improvements to implement")
            return GeneratedCode(
                changes=[],
                commit_message="No changes generated - no improvements to implement",
                pr_title="No changes",
                pr_description="No improvements were found that require code changes.",
            )

        # Get existing code context for each file we might modify
        existing_files = await self._get_relevant_files(
            repo_url, branch, prioritized_improvements
        )

        # Generate code for each improvement
        all_changes: list[CodeChange] = []
        for improvement in prioritized_improvements:
            self.log(f"Generating code for: {improvement.module}")
            changes = await self._generate_changes_for_improvement(
                improvement=improvement,
                existing_files=existing_files,
                analysis=input_data,
            )
            all_changes.extend(changes)

        # Generate commit message and PR description
        self.log("Generating commit message and PR description")
        commit_message, pr_title, pr_description = self._generate_pr_info(
            all_changes, prioritized_improvements
        )

        self.log(f"Generated {len(all_changes)} file changes")
        return GeneratedCode(
            changes=all_changes,
            commit_message=commit_message,
            pr_title=pr_title,
            pr_description=pr_description,
        )

    def _prioritize_improvements(
        self,
        improvements: list[Improvement],
        max_count: int,
    ) -> list[Improvement]:
        """Prioritize improvements by priority level.

        Args:
            improvements: List of improvements
            max_count: Maximum number to return

        Returns:
            Prioritized list of improvements
        """
        # Sort by priority (high -> medium -> low)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_improvements = sorted(
            improvements,
            key=lambda x: priority_order.get(x.priority.value, 3),
        )
        return sorted_improvements[:max_count]

    async def _get_relevant_files(
        self,
        repo_url: str,
        branch: str,
        improvements: list[Improvement],
    ) -> dict[str, str]:
        """Get content of files relevant to the improvements.

        Args:
            repo_url: GitHub repository URL
            branch: Branch name
            improvements: List of improvements

        Returns:
            Dictionary mapping file paths to their content
        """
        files: dict[str, str] = {}

        for improvement in improvements:
            # Try to find relevant files based on module name
            potential_files = self._guess_file_paths(improvement.module)

            for file_path in potential_files:
                if file_path not in files:
                    try:
                        content = await self.github_client.get_file_content(
                            repo_url, file_path, branch
                        )
                        files[file_path] = content
                        self.log(f"Fetched: {file_path}")
                    except Exception:
                        # File might not exist
                        pass

        return files

    def _guess_file_paths(self, module_name: str) -> list[str]:
        """Guess potential file paths for a module.

        Args:
            module_name: Name of the module

        Returns:
            List of potential file paths
        """
        # Common patterns for different languages
        module_lower = module_name.lower().replace(" ", "_").replace("-", "_")

        patterns = [
            f"src/{module_lower}.py",
            f"src/{module_lower}/__init__.py",
            f"src/{module_lower}/main.py",
            f"lib/{module_lower}.py",
            f"app/{module_lower}.py",
            f"{module_lower}.py",
            f"src/{module_lower}.ts",
            f"src/{module_lower}.js",
            f"src/{module_lower}/index.ts",
            f"src/{module_lower}/index.js",
            f"README.md",
            f"docs/{module_lower}.md",
        ]

        return patterns[:5]  # Limit to 5 potential paths

    async def _generate_changes_for_improvement(
        self,
        improvement: Improvement,
        existing_files: dict[str, str],
        analysis: ProjectAnalysis,
    ) -> list[CodeChange]:
        """Generate code changes for a single improvement.

        Args:
            improvement: The improvement to implement
            existing_files: Dictionary of existing file contents
            analysis: Full project analysis

        Returns:
            List of code changes
        """
        # Build the prompt with context
        context = self._build_generation_context(
            improvement, existing_files, analysis
        )

        # Use Claude to generate the changes
        try:
            # Generate new file content
            prompt = f"""Based on the following improvement suggestion and existing code context, generate the necessary code changes.

Improvement: {improvement.module}
Suggestion: {improvement.suggestion}
Priority: {improvement.priority.value}
Rationale: {improvement.rationale}

{context}

Generate the code changes as JSON with this structure:
{{
    "changes": [
        {{
            "file_path": "path/to/file",
            "change_type": "create|modify",
            "content": "full file content",
            "description": "what changed"
        }}
    ]
}}

Only include files that need to be created or modified. Provide the complete file content, not a diff."""

            response = self.claude_client.generate(
                system_prompt=self.SYSTEM_PROMPT,
                user_message=prompt,
                temperature=0.3,
            )

            # Parse the response
            changes = self._parse_code_changes(response)
            return changes

        except Exception as e:
            self.log(f"Error generating changes: {e}")
            return []

    def _build_generation_context(
        self,
        improvement: Improvement,
        existing_files: dict[str, str],
        analysis: ProjectAnalysis,
    ) -> str:
        """Build context for code generation.

        Args:
            improvement: The improvement
            existing_files: Existing file contents
            analysis: Project analysis

        Returns:
            Context string
        """
        context_parts = [f"Project Summary: {analysis.summary}"]

        if existing_files:
            context_parts.append("\nExisting Relevant Files:")
            for path, content in existing_files.items():
                truncated = content[:2000] if len(content) > 2000 else content
                context_parts.append(f"\n--- {path} ---\n{truncated}")

        return "\n".join(context_parts)

    def _parse_code_changes(self, response: str) -> list[CodeChange]:
        """Parse code changes from LLM response.

        Args:
            response: Raw response text

        Returns:
            List of CodeChange objects
        """
        try:
            # Try to extract JSON from the response
            json_text = response.strip()
            if "```json" in json_text:
                start = json_text.find("```json") + 7
                end = json_text.find("```", start)
                json_text = json_text[start:end].strip()
            elif "```" in json_text:
                start = json_text.find("```") + 3
                end = json_text.find("```", start)
                json_text = json_text[start:end].strip()

            data = json.loads(json_text)
            changes = []

            for change_data in data.get("changes", []):
                change = CodeChange(
                    file_path=change_data.get("file_path", ""),
                    change_type=change_data.get("change_type", "modify"),
                    content=change_data.get("content", ""),
                    description=change_data.get("description", ""),
                )
                changes.append(change)

            return changes

        except json.JSONDecodeError as e:
            self.log(f"Failed to parse JSON response: {e}")
            return []

    def _generate_pr_info(
        self,
        changes: list[CodeChange],
        improvements: list[Improvement],
    ) -> tuple[str, str, str]:
        """Generate commit message, PR title, and description.

        Args:
            changes: List of code changes
            improvements: List of improvements being addressed

        Returns:
            Tuple of (commit_message, pr_title, pr_description)
        """
        if not changes:
            return (
                "No changes",
                "No Changes Required",
                "No code changes were necessary for the suggested improvements.",
            )

        # Generate title based on main improvement
        main_improvement = improvements[0] if improvements else None
        if main_improvement:
            pr_title = f"feat: {main_improvement.module} - {main_improvement.suggestion[:50]}"
        else:
            pr_title = "feat: Automated improvements"

        # Generate commit message
        change_summary = f"{len(changes)} file(s) changed"
        commit_message = f"{pr_title}\n\n{change_summary}"

        # Generate PR description
        pr_description = f"""## Summary

This PR implements the following improvements:

"""
        for imp in improvements:
            pr_description += f"- **{imp.module}**: {imp.suggestion}\n"

        pr_description += f"""

## Changes

| File | Type | Description |
|------|------|-------------|
"""
        for change in changes:
            pr_description += f"| `{change.file_path}` | {change.change_type} | {change.description} |\n"

        pr_description += """

## Test Plan

- [ ] Review the generated code changes
- [ ] Run existing tests to ensure no regressions
- [ ] Add new tests for new functionality
- [ ] Manual testing of changed features

---

🤖 Generated with GitHub Agent"""

        return commit_message, pr_title, pr_description