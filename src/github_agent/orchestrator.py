"""Orchestrator for coordinating the multi-agent workflow."""

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from github_agent.agents import CodeGenerationAgent, GitHubOperatorAgent, RepoUnderstandingAgent
from github_agent.config import get_settings
from github_agent.models import AgentResponse, ProjectAnalysis, PullRequestResult, WorkflowState
from github_agent.tools import ClaudeClient, GitHubClient
from github_agent.utils import generate_request_id


class WorkflowOrchestrator:
    """Orchestrates the multi-agent workflow execution."""

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        github_token: str | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            anthropic_api_key: Anthropic API key (optional, uses settings)
            github_token: GitHub token (optional, uses settings)
        """
        settings = get_settings()
        self.anthropic_api_key = anthropic_api_key or settings.anthropic_api_key
        self.github_token = github_token or settings.github_token

        # Initialize clients
        self.claude_client = ClaudeClient(self.anthropic_api_key)
        self.github_client = GitHubClient(self.github_token)

        # Initialize agents
        self.repo_agent = RepoUnderstandingAgent(self.claude_client, self.github_client)
        self.code_agent = CodeGenerationAgent(self.claude_client, self.github_client)
        self.github_agent = GitHubOperatorAgent(self.claude_client, self.github_client)

        self.console = Console()

    async def run_workflow(
        self,
        prd_content: str,
        repo_url: str,
        target_branch: str = "main",
        max_changes: int = 3,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> WorkflowState:
        """Run the complete workflow.

        Args:
            prd_content: Product requirements document content
            repo_url: GitHub repository URL
            target_branch: Target branch for PR
            max_changes: Maximum number of changes to generate
            dry_run: If True, don't create actual PR
            verbose: Show detailed output

        Returns:
            Final workflow state
        """
        # Initialize state
        state = WorkflowState(
            request_id=generate_request_id(),
            prd_content=prd_content,
            repo_url=repo_url,
            target_branch=target_branch,
            status="started",
        )

        self.console.print(
            Panel(
                f"[bold green]Starting GitHub Agent Workflow[/bold green]\n\n"
                f"Request ID: {state.request_id}\n"
                f"Repository: {repo_url}\n"
                f"Target Branch: {target_branch}\n"
                f"Dry Run: {dry_run}",
                title="GitHub Agent",
                border_style="blue",
            )
        )

        try:
            # Phase 1: Analysis
            state.status = "analyzing"
            self._print_phase("Phase 1: Repository & PRD Analysis")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                task = progress.add_task("Analyzing...", total=100)

                analysis = await self.repo_agent.execute(
                    input_data=prd_content,
                    repo_url=repo_url,
                    branch=target_branch,
                )
                state.analysis = analysis
                progress.update(task, completed=100)

            self._display_analysis(analysis)

            # Check if we should proceed
            if analysis.feasibility.value == "not_feasible":
                state.status = "rejected"
                state.error = "Project analysis determined implementation is not feasible"
                self.console.print("[red]Implementation not feasible based on analysis[/red]")
                return state

            # Phase 2: Code Generation
            state.status = "generating"
            self._print_phase("Phase 2: Code Generation")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                task = progress.add_task("Generating code...", total=100)

                generated_code = await self.code_agent.execute(
                    input_data=analysis,
                    repo_url=repo_url,
                    branch=target_branch,
                    max_changes=max_changes,
                )
                state.generated_code = generated_code
                progress.update(task, completed=100)

            self._display_generated_code(generated_code)

            if not generated_code.changes:
                state.status = "no_changes"
                self.console.print("[yellow]No code changes were generated[/yellow]")
                return state

            # Phase 3: Create PR
            state.status = "creating_pr"
            self._print_phase("Phase 3: Creating Pull Request")

            pr_result = await self.github_agent.execute(
                input_data=generated_code,
                repo_url=repo_url,
                base_branch=target_branch,
                dry_run=dry_run,
            )
            state.pr_result = pr_result

            if pr_result.success:
                state.status = "completed"
                self._display_pr_result(pr_result, dry_run)
            else:
                state.status = "failed"
                state.error = pr_result.error or "Unknown error"
                self.console.print(f"[red]Failed to create PR: {pr_result.error}[/red]")

        except Exception as e:
            state.status = "error"
            state.error = str(e)
            self.console.print(f"[red]Error: {e}[/red]")
            if verbose:
                self.console.print_exception()

        return state

    def _print_phase(self, title: str) -> None:
        """Print a phase header.

        Args:
            title: Phase title
        """
        self.console.print(f"\n[bold cyan]▶ {title}[/bold cyan]\n")

    def _display_analysis(self, analysis: ProjectAnalysis) -> None:
        """Display analysis results.

        Args:
            analysis: Project analysis to display
        """
        # Feasibility
        feas_color = {
            "feasible": "green",
            "partially_feasible": "yellow",
            "not_feasible": "red",
        }.get(analysis.feasibility.value, "white")

        self.console.print(
            f"[bold]Feasibility:[/bold] [{feas_color}]{analysis.feasibility.value}[/{feas_color}]"
        )

        # Risks
        if analysis.risks:
            self.console.print("\n[bold]Risks Identified:[/bold]")
            for risk in analysis.risks:
                self.console.print(f"  ⚠️  {risk}")

        # Improvements table
        if analysis.improvements:
            table = Table(title="Improvement Suggestions")
            table.add_column("Module", style="cyan")
            table.add_column("Suggestion", style="white")
            table.add_column("Priority", style="magenta")

            for imp in analysis.improvements:
                priority_style = {"high": "red", "medium": "yellow", "low": "green"}.get(
                    imp.priority.value, "white"
                )
                table.add_row(
                    imp.module[:30],
                    imp.suggestion[:50] + ("..." if len(imp.suggestion) > 50 else ""),
                    f"[{priority_style}]{imp.priority.value}[/{priority_style}]",
                )

            self.console.print(table)

    def _display_generated_code(self, generated_code: "github_agent.models.GeneratedCode") -> None:
        """Display generated code summary.

        Args:
            generated_code: Generated code to display
        """
        self.console.print(f"\n[bold]Generated {len(generated_code.changes)} file changes[/bold]")

        for change in generated_code.changes:
            self.console.print(f"  📄 {change.file_path} ({change.change_type})")
            if change.description:
                self.console.print(f"      {change.description}")

        self.console.print(f"\n[bold]Commit Message:[/bold]")
        self.console.print(f"  {generated_code.commit_message[:100]}...")

    def _display_pr_result(self, result: PullRequestResult, dry_run: bool) -> None:
        """Display PR result.

        Args:
            result: Pull request result
            dry_run: Whether this was a dry run
        """
        if dry_run:
            self.console.print(
                Panel(
                    f"[yellow]DRY RUN - No actual PR created[/yellow]\n\n"
                    f"Branch: {result.branch_name}\n"
                    f"Changes: Ready to commit",
                    title="Dry Run Complete",
                    border_style="yellow",
                )
            )
        else:
            self.console.print(
                Panel(
                    f"[green]✓ Pull Request Created Successfully[/green]\n\n"
                    f"PR URL: {result.pr_url}\n"
                    f"PR Number: #{result.pr_number}\n"
                    f"Branch: {result.branch_name}",
                    title="Success",
                    border_style="green",
                )
            )

    async def analyze_only(
        self,
        prd_content: str,
        repo_url: str,
        branch: str = "main",
    ) -> ProjectAnalysis:
        """Run only the analysis phase.

        Args:
            prd_content: PRD content
            repo_url: Repository URL
            branch: Branch to analyze

        Returns:
            Project analysis
        """
        self._print_phase("Analyzing Repository and PRD")

        analysis = await self.repo_agent.execute(
            input_data=prd_content,
            repo_url=repo_url,
            branch=branch,
        )

        self._display_analysis(analysis)
        return analysis

    async def generate_only(
        self,
        analysis: ProjectAnalysis,
        repo_url: str,
        branch: str = "main",
        max_changes: int = 3,
    ) -> "github_agent.models.GeneratedCode":
        """Run only the code generation phase.

        Args:
            analysis: Project analysis
            repo_url: Repository URL
            branch: Branch to use
            max_changes: Maximum changes to generate

        Returns:
            Generated code
        """
        self._print_phase("Generating Code")

        generated = await self.code_agent.execute(
            input_data=analysis,
            repo_url=repo_url,
            branch=branch,
            max_changes=max_changes,
        )

        self._display_generated_code(generated)
        return generated


# Import for type hints
import github_agent.models