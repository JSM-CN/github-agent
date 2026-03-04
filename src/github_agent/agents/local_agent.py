"""Agent for working with local projects."""

import json
from pathlib import Path
from typing import Any

from github_agent.agents.base import BaseAgent
from github_agent.models import CodeChange, GeneratedCode, Improvement, ProjectAnalysis
from github_agent.tools.claude import ClaudeClient
from github_agent.tools.local import LocalGitClient, LocalProjectClient


class LocalProjectAgent(BaseAgent[str, ProjectAnalysis]):
    """Agent for analyzing and modifying local projects."""

    SYSTEM_PROMPT = """You are an expert software architect and developer. Your task is to analyze a local project directory along with product requirements to:

1. **Feasibility Assessment**: Evaluate whether the requested changes can be implemented.
2. **Risk Identification**: Identify potential risks and challenges.
3. **Improvement Suggestions**: Provide actionable improvement suggestions.

When analyzing local projects:
- Examine the file structure and code patterns
- Identify the programming language and framework
- Look for existing tests and documentation
- Consider the project's architecture

Be practical and provide concrete, actionable suggestions."""


class LocalCodeAgent(BaseAgent[ProjectAnalysis, GeneratedCode]):
    """Agent for generating code changes for local projects."""

    SYSTEM_PROMPT = """You are an expert software engineer. Generate code changes for a local project based on the analysis and improvement suggestions.

Guidelines:
1. Follow existing code style and patterns
2. Generate complete, working code
3. Include necessary imports and dependencies
4. Add appropriate error handling
5. Consider backward compatibility

Generate changes that are ready to apply directly to the files."""


class LocalWorkflowOrchestrator:
    """Orchestrator for working with local projects."""

    SYSTEM_PROMPT = """You are an expert software architect and developer. Your task is to analyze a local project directory along with product requirements to:

1. **Feasibility Assessment**: Evaluate whether the requested changes can be implemented.
2. **Risk Identification**: Identify potential risks and challenges.
3. **Improvement Suggestions**: Provide actionable improvement suggestions.

When analyzing local projects:
- Examine the file structure and code patterns
- Identify the programming language and framework
- Look for existing tests and documentation
- Consider the project's architecture

Be practical and provide concrete, actionable suggestions."""

    CODE_SYSTEM_PROMPT = """You are an expert software engineer. Generate code changes for a local project based on the analysis and improvement suggestions.

Guidelines:
1. Follow existing code style and patterns
2. Generate complete, working code
3. Include necessary imports and dependencies
4. Add appropriate error handling
5. Consider backward compatibility

Generate changes that are ready to apply directly to the files."""

    def __init__(
        self,
        project_path: Path | str,
        anthropic_api_key: str | None = None,
    ):
        """Initialize the local workflow orchestrator.

        Args:
            project_path: Path to the local project
            anthropic_api_key: Anthropic API key
        """
        from github_agent.config import get_settings

        settings = get_settings()
        self.project_path = Path(project_path).resolve()
        self.api_key = anthropic_api_key or settings.anthropic_api_key

        # Initialize clients
        self.claude_client = ClaudeClient(self.api_key)
        self.project_client = LocalProjectClient(self.project_path)
        self.git_client = LocalGitClient(self.project_path)

        # Import console
        from rich.console import Console

        self.console = Console()

    def analyze_project(
        self,
        prd_content: str,
    ) -> ProjectAnalysis:
        """Analyze the local project with PRD.

        Args:
            prd_content: Product requirements document

        Returns:
            Project analysis
        """
        self.console.print("[bold cyan]Analyzing local project...[/bold cyan]")

        # Get project structure
        structure = self.project_client.get_project_structure()

        # Get README
        readme = self.project_client.get_readme()

        # Get issues from local file if exists
        issues = self.project_client.get_issues_from_file()

        # Get git status if available
        git_status = None
        if self.git_client.is_git_repo():
            git_status = self.git_client.get_status()
            self.console.print(f"  Git branch: {git_status['branch']}")
            if not git_status['is_clean']:
                self.console.print("  [yellow]Warning: Working directory has uncommitted changes[/yellow]")

        self.console.print(f"  Project: {structure['name']}")
        self.console.print(f"  Language: {structure['language']}")
        self.console.print(f"  Files: {structure['total_files']}")

        # Build context for analysis
        context = self._build_analysis_context(
            prd=prd_content,
            structure=structure,
            readme=readme,
            issues=issues,
            git_status=git_status,
        )

        # Generate analysis using Claude
        self.console.print("  Generating analysis with Claude...")
        analysis = self.claude_client.generate_structured(
            system_prompt=self.SYSTEM_PROMPT,
            user_message=context,
            response_model=ProjectAnalysis,
            temperature=0.3,
        )

        analysis.project_structure = structure
        return analysis

    def _build_analysis_context(
        self,
        prd: str,
        structure: dict,
        readme: str,
        issues: list[dict],
        git_status: dict | None,
    ) -> str:
        """Build context for analysis."""
        parts = [
            "# Product Requirements Document (PRD)",
            prd,
            "---",
            "# Project Structure",
            json.dumps(structure, indent=2, ensure_ascii=False),
        ]

        if readme:
            parts.extend([
                "---",
                "# README Content",
                readme[:3000],
            ])

        if issues:
            parts.extend([
                "---",
                "# Open Issues",
                json.dumps(issues[:5], indent=2, ensure_ascii=False),
            ])

        if git_status:
            parts.extend([
                "---",
                "# Git Status",
                json.dumps(git_status, indent=2, ensure_ascii=False),
            ])

        return "\n".join(parts)

    def generate_code(
        self,
        analysis: ProjectAnalysis,
        max_changes: int = 3,
    ) -> GeneratedCode:
        """Generate code changes for the local project.

        Args:
            analysis: Project analysis
            max_changes: Maximum number of changes

        Returns:
            Generated code changes
        """
        self.console.print("[bold cyan]Generating code changes...[/bold cyan]")

        # Prioritize improvements
        priority_order = {"high": 0, "medium": 1, "low": 2}
        improvements = sorted(
            analysis.improvements,
            key=lambda x: priority_order.get(x.priority.value, 3),
        )[:max_changes]

        if not improvements:
            return GeneratedCode(
                changes=[],
                commit_message="No changes",
                pr_title="No changes",
                pr_description="No improvements to implement",
            )

        all_changes: list[CodeChange] = []

        for improvement in improvements:
            self.console.print(f"  Processing: {improvement.module}")
            changes = self._generate_improvement_changes(improvement, analysis)
            all_changes.extend(changes)

        # Generate commit info
        commit_message, pr_title, pr_description = self._generate_commit_info(
            all_changes, improvements
        )

        self.console.print(f"  Generated {len(all_changes)} file changes")
        return GeneratedCode(
            changes=all_changes,
            commit_message=commit_message,
            pr_title=pr_title,
            pr_description=pr_description,
        )

    def _generate_improvement_changes(
        self,
        improvement: Improvement,
        analysis: ProjectAnalysis,
    ) -> list[CodeChange]:
        """Generate changes for a single improvement."""
        # Get existing relevant files
        existing_content = {}
        for file_path in self._guess_file_paths(improvement.module):
            try:
                content = self.project_client.read_file(file_path)
                existing_content[file_path] = content
            except FileNotFoundError:
                pass

        # Build prompt
        context = f"""Improvement: {improvement.module}
Suggestion: {improvement.suggestion}
Priority: {improvement.priority.value}

Project Language: {analysis.project_structure.get('language', 'Unknown')}

Existing Files:
{json.dumps({k: v[:1000] + '...' if len(v) > 1000 else v for k, v in existing_content.items()}, indent=2)}
"""
        if analysis.project_structure.get('description'):
            context += f"\nProject Description: {analysis.project_structure['description']}"

        prompt = f"""{context}

Generate code changes as JSON:
{{
    "changes": [
        {{
            "file_path": "relative/path/to/file",
            "change_type": "create|modify",
            "content": "complete file content",
            "description": "what changed"
        }}
    ]
}}

Provide complete file content, not diffs. Only include files that need changes."""

        try:
            response = self.claude_client.generate(
                system_prompt=self.CODE_SYSTEM_PROMPT,
                user_message=prompt,
                temperature=0.3,
            )
            return self._parse_changes(response)
        except Exception as e:
            self.console.print(f"  [red]Error: {e}[/red]")
            return []

    def _guess_file_paths(self, module_name: str) -> list[str]:
        """Guess potential file paths for a module."""
        module_lower = module_name.lower().replace(" ", "_").replace("-", "_")

        # Common patterns
        patterns = [
            f"src/{module_lower}.py",
            f"src/{module_lower}/__init__.py",
            f"lib/{module_lower}.py",
            f"app/{module_lower}.py",
            f"{module_lower}.py",
            f"src/{module_lower}.ts",
            f"src/{module_lower}.js",
            "README.md",
        ]

        # Also check what files actually exist
        existing = []
        for pattern in patterns:
            if self.project_client.file_exists(pattern):
                existing.append(pattern)

        return existing or patterns[:3]

    def _parse_changes(self, response: str) -> list[CodeChange]:
        """Parse code changes from response."""
        try:
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
            for item in data.get("changes", []):
                changes.append(CodeChange(
                    file_path=item.get("file_path", ""),
                    change_type=item.get("change_type", "modify"),
                    content=item.get("content", ""),
                    description=item.get("description", ""),
                ))
            return changes
        except json.JSONDecodeError:
            return []

    def _generate_commit_info(
        self,
        changes: list[CodeChange],
        improvements: list[Improvement],
    ) -> tuple[str, str, str]:
        """Generate commit message and PR info."""
        if not changes:
            return ("No changes", "No Changes", "No changes generated")

        main = improvements[0] if improvements else None
        title = f"feat: {main.module} - {main.suggestion[:50]}" if main else "feat: Local improvements"

        commit_msg = f"{title}\n\n{len(changes)} file(s) changed"

        pr_desc = f"""## Summary

Implemented improvements:

"""
        for imp in improvements:
            pr_desc += f"- **{imp.module}**: {imp.suggestion}\n"

        pr_desc += f"""

## Changes

| File | Type | Description |
|------|------|-------------|
"""
        for change in changes:
            pr_desc += f"| `{change.file_path}` | {change.change_type} | {change.description} |\n"

        return commit_msg, title, pr_desc

    def apply_changes(
        self,
        generated_code: GeneratedCode,
        create_branch: bool = True,
        branch_name: str | None = None,
        commit: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Apply generated changes to the local project.

        Args:
            generated_code: Generated code changes
            create_branch: Create a new git branch
            branch_name: Custom branch name
            commit: Commit the changes
            dry_run: Don't actually write files

        Returns:
            Result dictionary
        """
        self.console.print("[bold cyan]Applying changes to local project...[/bold cyan]")

        result = {
            "success": False,
            "files_written": [],
            "branch_created": None,
            "committed": False,
            "error": None,
        }

        if not generated_code.changes:
            result["error"] = "No changes to apply"
            return result

        if dry_run:
            self.console.print("  [yellow]DRY RUN - Not writing files[/yellow]")
            for change in generated_code.changes:
                self.console.print(f"    Would {change.change_type}: {change.file_path}")
            result["success"] = True
            return result

        try:
            # Create branch if requested
            if create_branch and self.git_client.is_git_repo():
                from github_agent.utils import generate_branch_name

                branch = branch_name or generate_branch_name(
                    "local-pr",
                    generated_code.pr_title,
                )
                if self.git_client.create_branch(branch):
                    result["branch_created"] = branch
                    self.console.print(f"  Created branch: {branch}")

            # Apply file changes
            for change in generated_code.changes:
                self.console.print(f"  Writing: {change.file_path}")
                self.project_client.write_file(change.file_path, change.content)
                result["files_written"].append(change.file_path)

            # Commit if requested
            if commit and self.git_client.is_git_repo():
                self.git_client.add_all()
                if self.git_client.commit(generated_code.commit_message):
                    result["committed"] = True
                    self.console.print("  Changes committed")

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
            self.console.print(f"  [red]Error: {e}[/red]")

        return result

    def run_workflow(
        self,
        prd_content: str,
        max_changes: int = 3,
        create_branch: bool = True,
        commit: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run the complete local workflow.

        Args:
            prd_content: PRD content
            max_changes: Max changes to generate
            create_branch: Create git branch
            commit: Commit changes
            dry_run: Dry run mode

        Returns:
            Workflow result
        """
        from rich.panel import Panel

        self.console.print(Panel(
            f"[bold green]Local Project Workflow[/bold green]\n\n"
            f"Project: {self.project_path}\n"
            f"Max Changes: {max_changes}\n"
            f"Dry Run: {dry_run}",
            title="GitHub Agent - Local Mode",
            border_style="blue",
        ))

        # Phase 1: Analyze
        self.console.print("\n[bold]Phase 1: Analysis[/bold]")
        analysis = self.analyze_project(prd_content)

        # Display analysis
        self._display_analysis(analysis)

        if analysis.feasibility.value == "not_feasible":
            return {"success": False, "error": "Not feasible", "analysis": analysis}

        # Phase 2: Generate
        self.console.print("\n[bold]Phase 2: Code Generation[/bold]")
        generated = self.generate_code(analysis, max_changes)

        if not generated.changes:
            return {"success": False, "error": "No changes generated", "analysis": analysis}

        # Phase 3: Apply
        self.console.print("\n[bold]Phase 3: Apply Changes[/bold]")
        apply_result = self.apply_changes(
            generated,
            create_branch=create_branch,
            commit=commit,
            dry_run=dry_run,
        )

        return {
            "success": apply_result["success"],
            "analysis": analysis,
            "generated_code": generated,
            "apply_result": apply_result,
        }

    def _display_analysis(self, analysis: ProjectAnalysis) -> None:
        """Display analysis results."""
        from rich.table import Table

        feas_color = {
            "feasible": "green",
            "partially_feasible": "yellow",
            "not_feasible": "red",
        }.get(analysis.feasibility.value, "white")

        self.console.print(f"\n  Feasibility: [{feas_color}]{analysis.feasibility.value}[/{feas_color}]")

        if analysis.risks:
            self.console.print("\n  [bold]Risks:[/bold]")
            for risk in analysis.risks:
                self.console.print(f"    ⚠️  {risk}")

        if analysis.improvements:
            table = Table(title="Improvements")
            table.add_column("Module", style="cyan")
            table.add_column("Suggestion", style="white")
            table.add_column("Priority", style="magenta")

            for imp in analysis.improvements:
                p_style = {"high": "red", "medium": "yellow", "low": "green"}.get(
                    imp.priority.value, "white"
                )
                table.add_row(
                    imp.module[:30],
                    imp.suggestion[:40] + ("..." if len(imp.suggestion) > 40 else ""),
                    f"[{p_style}]{imp.priority.value}[/{p_style}]",
                )

            self.console.print(table)