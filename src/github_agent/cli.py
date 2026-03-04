"""Command-line interface for GitHub Agent."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from github_agent import __version__
from github_agent.agents.local_agent import LocalWorkflowOrchestrator
from github_agent.config import get_settings
from github_agent.orchestrator import WorkflowOrchestrator
from github_agent.tools.github import GitHubClient
from github_agent.tools.local import LocalGitClient, LocalProjectClient

app = typer.Typer(
    name="github-agent",
    help="Multi-agent system for automated GitHub PR generation from PRD documents",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"github-agent version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", "-v", callback=version_callback, help="Show version"),
    ] = False,
) -> None:
    """GitHub Agent - Multi-agent system for automated PR generation."""
    pass


@app.command()
def run(
    prd_file: Annotated[
        Path,
        typer.Option("--prd", "-p", help="Path to PRD file (markdown or text)"),
    ],
    repo_url: Annotated[
        str,
        typer.Option("--repo", "-r", help="GitHub repository URL"),
    ],
    target_branch: Annotated[
        str,
        typer.Option("--branch", "-b", help="Target branch for PR"),
    ] = "main",
    max_changes: Annotated[
        int,
        typer.Option("--max-changes", "-m", help="Maximum number of changes to generate"),
    ] = 3,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-d", help="Don't create actual PR"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Show detailed output"),
    ] = False,
    anthropic_key: Annotated[
        str | None,
        typer.Option("--anthropic-key", "-k", help="Anthropic API key", envvar="ANTHROPIC_API_KEY"),
    ] = None,
    github_token: Annotated[
        str | None,
        typer.Option("--github-token", "-t", help="GitHub token", envvar="GITHUB_TOKEN"),
    ] = None,
) -> None:
    """Run the complete workflow: analyze PRD, generate code, create PR.

    Example:
        github-agent run -p requirements.md -r https://github.com/owner/repo
    """
    # Validate PRD file
    if not prd_file.exists():
        console.print(f"[red]Error: PRD file not found: {prd_file}[/red]")
        raise typer.Exit(1)

    # Read PRD content
    prd_content = prd_file.read_text(encoding="utf-8")
    console.print(f"[green]Loaded PRD from: {prd_file}[/green]")

    # Check configuration
    settings = get_settings()
    api_key = anthropic_key or settings.anthropic_api_key
    token = github_token or settings.github_token

    if not api_key:
        console.print("[red]Error: Anthropic API key not provided[/red]")
        console.print("Set ANTHROPIC_API_KEY environment variable or use --anthropic-key")
        raise typer.Exit(1)

    if not token:
        console.print("[red]Error: GitHub token not provided[/red]")
        console.print("Set GITHUB_TOKEN environment variable or use --github-token")
        raise typer.Exit(1)

    # Run workflow
    orchestrator = WorkflowOrchestrator(
        anthropic_api_key=api_key,
        github_token=token,
    )

    try:
        state = asyncio.run(
            orchestrator.run_workflow(
                prd_content=prd_content,
                repo_url=repo_url,
                target_branch=target_branch,
                max_changes=max_changes,
                dry_run=dry_run,
                verbose=verbose,
            )
        )

        # Exit with appropriate code
        if state.status == "completed":
            raise typer.Exit(0)
        else:
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(130)


@app.command()
def analyze(
    prd_file: Annotated[
        Path,
        typer.Option("--prd", "-p", help="Path to PRD file"),
    ],
    repo_url: Annotated[
        str,
        typer.Option("--repo", "-r", help="GitHub repository URL"),
    ],
    branch: Annotated[
        str,
        typer.Option("--branch", "-b", help="Branch to analyze"),
    ] = "main",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file for analysis (JSON)"),
    ] = None,
    anthropic_key: Annotated[
        str | None,
        typer.Option("--anthropic-key", "-k", help="Anthropic API key", envvar="ANTHROPIC_API_KEY"),
    ] = None,
    github_token: Annotated[
        str | None,
        typer.Option("--github-token", "-t", help="GitHub token", envvar="GITHUB_TOKEN"),
    ] = None,
) -> None:
    """Run only the analysis phase.

    Example:
        github-agent analyze -p requirements.md -r https://github.com/owner/repo
    """
    if not prd_file.exists():
        console.print(f"[red]Error: PRD file not found: {prd_file}[/red]")
        raise typer.Exit(1)

    prd_content = prd_file.read_text(encoding="utf-8")

    settings = get_settings()
    api_key = anthropic_key or settings.anthropic_api_key
    token = github_token or settings.github_token

    if not api_key or not token:
        console.print("[red]Error: API keys not configured[/red]")
        raise typer.Exit(1)

    orchestrator = WorkflowOrchestrator(
        anthropic_api_key=api_key,
        github_token=token,
    )

    try:
        analysis = asyncio.run(
            orchestrator.analyze_only(
                prd_content=prd_content,
                repo_url=repo_url,
                branch=branch,
            )
        )

        if output:
            import json

            output.write_text(
                json.dumps(analysis.model_dump(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            console.print(f"[green]Analysis saved to: {output}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    console.print("[bold]GitHub Agent Configuration[/bold]\n")

    # LLM Provider settings
    console.print("[cyan]LLM Provider:[/cyan]")
    console.print(f"  Provider: {settings.llm_provider}")
    console.print(f"  Model: {settings.default_model}")
    if settings.llm_base_url:
        console.print(f"  Base URL: {settings.llm_base_url}")

    # API Keys
    console.print("\n[cyan]API Keys:[/cyan]")
    console.print(f"  Anthropic API Key: {'✓ Set' if settings.anthropic_api_key else '✗ Not set'}")
    console.print(f"  OpenAI API Key: {'✓ Set' if settings.openai_api_key else '✗ Not set'}")
    console.print(f"  GitHub Token: {'✓ Set' if settings.github_token else '✗ Not set'}")

    # Other settings
    console.print("\n[cyan]Generation Settings:[/cyan]")
    console.print(f"  Max Tokens: {settings.max_tokens}")
    console.print(f"  Temperature: {settings.temperature}")

    console.print("\n[cyan]Workflow Settings:[/cyan]")
    console.print(f"  Default Branch: {settings.default_target_branch}")
    console.print(f"  Branch Prefix: {settings.branch_prefix}")

    if settings.is_configured:
        console.print("\n[green]✓ Ready to run[/green]")
    else:
        console.print("\n[yellow]⚠ Missing required configuration[/yellow]")
        console.print("  Set ANTHROPIC_API_KEY (for Claude) or OPENAI_API_KEY (for other models)")
        console.print("  Set GITHUB_TOKEN for GitHub operations")


@app.command()
def init(
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help="LLM provider (anthropic, openai, qwen, deepseek)"),
    ] = "anthropic",
    anthropic_key: Annotated[
        str | None,
        typer.Option("--anthropic-key", "-k", help="Anthropic API key"),
    ] = None,
    openai_key: Annotated[
        str | None,
        typer.Option("--openai-key", "-o", help="OpenAI API key (or compatible)"),
    ] = None,
    github_token: Annotated[
        str | None,
        typer.Option("--github-token", "-t", help="GitHub token"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Model name"),
    ] = None,
) -> None:
    """Initialize configuration by creating .env file.

    Examples:
        github-agent init                           # Interactive mode
        github-agent init -p qwen -o your-key       # Use Qwen
        github-agent init -p deepseek -o your-key   # Use DeepSeek
        github-agent init -p anthropic -k your-key  # Use Claude
    """
    env_file = Path(".env")

    if env_file.exists():
        console.print("[yellow].env file already exists[/yellow]")
        overwrite = typer.confirm("Overwrite?")
        if not overwrite:
            raise typer.Exit(0)

    # Set default model based on provider
    default_models = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
        "qwen": "qwen-plus",
        "deepseek": "deepseek-chat",
    }
    default_model = model or default_models.get(provider, "claude-sonnet-4-20250514")

    # Prompt for missing values based on provider
    if provider == "anthropic":
        if not anthropic_key:
            anthropic_key = typer.prompt("Enter your Anthropic API key", hide_input=True)
    else:
        if not openai_key:
            openai_key = typer.prompt("Enter your API key", hide_input=True)

    if not github_token:
        github_token = typer.prompt("Enter your GitHub token (optional, press Enter to skip)", default="", hide_input=True)

    # Build .env content
    env_lines = [
        "# GitHub Agent Configuration",
        "# Generated by 'github-agent init'",
        "",
        f"LLM_PROVIDER={provider}",
        f"DEFAULT_MODEL={default_model}",
    ]

    if provider == "anthropic" and anthropic_key:
        env_lines.append(f"ANTHROPIC_API_KEY={anthropic_key}")
    elif openai_key:
        env_lines.append(f"OPENAI_API_KEY={openai_key}")

    if github_token:
        env_lines.append(f"GITHUB_TOKEN={github_token}")

    env_lines.extend([
        "",
        "# Optional settings",
        "# MAX_TOKENS=4096",
        "# TEMPERATURE=0.7",
        "# LLM_BASE_URL=  # For custom API endpoints",
    ])

    env_file.write_text("\n".join(env_lines) + "\n")
    console.print(f"[green]✓ Created .env file[/green]")
    console.print(f"[dim]Provider: {provider}, Model: {default_model}[/dim]")
    console.print("[dim]Add .env to your .gitignore to keep your keys secure[/dim]")


# ============== Local Project Commands ==============


@app.command()
def local(
    prd_file: Annotated[
        Path,
        typer.Option("--prd", "-p", help="Path to PRD file (markdown or text)"),
    ],
    project_path: Annotated[
        Path,
        typer.Option("--project", "-P", help="Path to local project directory"),
    ] = Path("."),
    max_changes: Annotated[
        int,
        typer.Option("--max-changes", "-m", help="Maximum number of changes to generate"),
    ] = 3,
    create_branch: Annotated[
        bool,
        typer.Option("--branch/--no-branch", help="Create a new git branch"),
    ] = True,
    commit: Annotated[
        bool,
        typer.Option("--commit/--no-commit", help="Commit the changes"),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-d", help="Don't actually write files"),
    ] = False,
    anthropic_key: Annotated[
        str | None,
        typer.Option("--anthropic-key", "-k", help="Anthropic API key", envvar="ANTHROPIC_API_KEY"),
    ] = None,
) -> None:
    """Run workflow on a local project (no GitHub required).

    Analyzes PRD against local project, generates code changes, and applies them.

    Example:
        github-agent local -p requirements.md -P ./my-project
    """
    # Validate inputs
    if not prd_file.exists():
        console.print(f"[red]Error: PRD file not found: {prd_file}[/red]")
        raise typer.Exit(1)

    project_path = project_path.resolve()
    if not project_path.exists():
        console.print(f"[red]Error: Project directory not found: {project_path}[/red]")
        raise typer.Exit(1)

    # Read PRD
    prd_content = prd_file.read_text(encoding="utf-8")
    console.print(f"[green]Loaded PRD from: {prd_file}[/green]")

    # Check API key
    settings = get_settings()
    api_key = anthropic_key or settings.anthropic_api_key

    if not api_key:
        console.print("[red]Error: Anthropic API key not provided[/red]")
        console.print("Set ANTHROPIC_API_KEY environment variable or use --anthropic-key")
        raise typer.Exit(1)

    # Run local workflow
    orchestrator = LocalWorkflowOrchestrator(
        project_path=project_path,
        anthropic_api_key=api_key,
    )

    try:
        result = orchestrator.run_workflow(
            prd_content=prd_content,
            max_changes=max_changes,
            create_branch=create_branch,
            commit=commit,
            dry_run=dry_run,
        )

        if result.get("success"):
            console.print("\n[green]✓ Workflow completed successfully[/green]")
            raise typer.Exit(0)
        else:
            console.print(f"\n[red]✗ Workflow failed: {result.get('error', 'Unknown error')}[/red]")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(130)


@app.command()
def local_analyze(
    prd_file: Annotated[
        Path,
        typer.Option("--prd", "-p", help="Path to PRD file"),
    ],
    project_path: Annotated[
        Path,
        typer.Option("--project", "-P", help="Path to local project directory"),
    ] = Path("."),
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file for analysis (JSON)"),
    ] = None,
    anthropic_key: Annotated[
        str | None,
        typer.Option("--anthropic-key", "-k", help="Anthropic API key", envvar="ANTHROPIC_API_KEY"),
    ] = None,
) -> None:
    """Analyze a local project with PRD (no changes made).

    Example:
        github-agent local-analyze -p requirements.md -P ./my-project -o analysis.json
    """
    if not prd_file.exists():
        console.print(f"[red]Error: PRD file not found: {prd_file}[/red]")
        raise typer.Exit(1)

    project_path = project_path.resolve()
    if not project_path.exists():
        console.print(f"[red]Error: Project directory not found: {project_path}[/red]")
        raise typer.Exit(1)

    prd_content = prd_file.read_text(encoding="utf-8")

    settings = get_settings()
    api_key = anthropic_key or settings.anthropic_api_key

    if not api_key:
        console.print("[red]Error: Anthropic API key not provided[/red]")
        raise typer.Exit(1)

    orchestrator = LocalWorkflowOrchestrator(
        project_path=project_path,
        anthropic_api_key=api_key,
    )

    try:
        analysis = orchestrator.analyze_project(prd_content)

        if output:
            output.write_text(
                json.dumps(analysis.model_dump(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            console.print(f"[green]Analysis saved to: {output}[/green]")
        else:
            # Display summary
            console.print(f"\n[bold]Analysis Summary[/bold]")
            console.print(f"  Feasibility: {analysis.feasibility.value}")
            console.print(f"  Risks: {len(analysis.risks)}")
            console.print(f"  Improvements: {len(analysis.improvements)}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def create_repo(
    project_path: Annotated[
        Path,
        typer.Option("--project", "-P", help="Path to local project directory"),
    ] = Path("."),
    repo_name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Repository name (default: project directory name)"),
    ] = None,
    description: Annotated[
        str,
        typer.Option("--description", "-d", help="Repository description"),
    ] = "",
    private: Annotated[
        bool,
        typer.Option("--private", help="Create private repository"),
    ] = False,
    push: Annotated[
        bool,
        typer.Option("--push", help="Push local code to the new repository"),
    ] = False,
    github_token: Annotated[
        str | None,
        typer.Option("--github-token", "-t", help="GitHub token", envvar="GITHUB_TOKEN"),
    ] = None,
) -> None:
    """Create a new GitHub repository from a local project.

    Creates a GitHub repository and optionally pushes your local code.

    Example:
        github-agent create-repo -P ./my-project --name my-awesome-project --push
    """
    project_path = project_path.resolve()
    if not project_path.exists():
        console.print(f"[red]Error: Project directory not found: {project_path}[/red]")
        raise typer.Exit(1)

    # Check GitHub token
    settings = get_settings()
    token = github_token or settings.github_token

    if not token:
        console.print("[red]Error: GitHub token not provided[/red]")
        console.print("Set GITHUB_TOKEN environment variable or use --github-token")
        raise typer.Exit(1)

    # Get project info
    project_client = LocalProjectClient(project_path)
    git_client = LocalGitClient(project_path)

    structure = project_client.get_project_structure()
    repo_name = repo_name or structure["name"]

    # 处理 description：清理控制字符并限制长度
    raw_description = description or structure.get("description", "")
    if raw_description:
        # 移除控制字符（保留基本空白）
        import re
        raw_description = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', raw_description)
        # 替换多个空白为单个空格
        raw_description = re.sub(r'\s+', ' ', raw_description).strip()
        # 限制长度为 350 字符
        description = raw_description[:350]

    console.print(Panel(
        f"[bold]Creating GitHub Repository[/bold]\n\n"
        f"Project: {project_path}\n"
        f"Repository: {repo_name}\n"
        f"Private: {private}\n"
        f"Push: {push}",
        border_style="blue",
    ))

    # Create repository
    github_client = GitHubClient(token)

    async def _create_repo():
        # Create the repo
        repo_info = await github_client._request(
            "POST",
            "/user/repos",
            json={
                "name": repo_name,
                "description": description,
                "private": private,
                "auto_init": False,  # Don't auto-init, we'll push our own code
            },
        )

        return repo_info

    try:
        repo_info = asyncio.run(_create_repo())
        repo_url = repo_info.get("html_url", "")
        clone_url = repo_info.get("clone_url", "")

        console.print(f"\n[green]✓ Repository created: {repo_url}[/green]")

        # Add remote and push if requested
        if push:
            if not git_client.is_git_repo():
                console.print("[yellow]Local project is not a git repository. Initializing...[/yellow]")
                import subprocess
                subprocess.run(["git", "init"], cwd=project_path, check=True)

            # Add remote
            import subprocess
            try:
                # 检查是否已有 origin，如果有则更新
                if git_client.has_remote("origin"):
                    subprocess.run(
                        ["git", "remote", "set-url", "origin", clone_url],
                        cwd=project_path,
                        check=True,
                    )
                    console.print("  Updated remote: origin")
                else:
                    subprocess.run(
                        ["git", "remote", "add", "origin", clone_url],
                        cwd=project_path,
                        check=True,
                    )
                    console.print("  Added remote: origin")

                # Push
                branch = git_client.get_current_branch() or "main"
                subprocess.run(
                    ["git", "push", "-u", "origin", branch],
                    cwd=project_path,
                    check=True,
                )
                console.print(f"  Pushed to: {branch}")

            except subprocess.CalledProcessError as e:
                console.print(f"[red]Git operation failed: {e}[/red]")

        console.print(f"\n[green]✓ Done! Your repository is ready at: {repo_url}[/green]")

    except Exception as e:
        import traceback
        if "already exists" in str(e).lower():
            console.print(f"[yellow]Repository '{repo_name}' already exists[/yellow]")
        else:
            console.print(f"[red]Error: {e}[/red]")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            raise typer.Exit(1)


@app.command()
def push(
    project_path: Annotated[
        Path,
        typer.Option("--project", "-P", help="Path to local project directory"),
    ] = Path("."),
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch to push (default: current branch)"),
    ] = None,
    set_upstream: Annotated[
        bool,
        typer.Option("-u", "--set-upstream", help="Set upstream for the branch"),
    ] = True,
    github_token: Annotated[
        str | None,
        typer.Option("--github-token", "-t", help="GitHub token", envvar="GITHUB_TOKEN"),
    ] = None,
) -> None:
    """Push local project to GitHub.

    Pushes the current branch to the remote repository.

    Example:
        github-agent push -P ./my-project
    """
    project_path = project_path.resolve()
    git_client = LocalGitClient(project_path)

    if not git_client.is_git_repo():
        console.print("[red]Error: Not a git repository[/red]")
        raise typer.Exit(1)

    if not git_client.has_remote("origin"):
        console.print("[red]Error: No remote 'origin' configured[/red]")
        console.print("Use 'github-agent create-repo' to create a repository first")
        raise typer.Exit(1)

    current_branch = git_client.get_current_branch()
    branch = branch or current_branch

    console.print(f"[bold]Pushing branch '{branch}' to origin...[/bold]")

    if git_client.push("origin", branch, set_upstream):
        console.print(f"[green]✓ Successfully pushed to origin/{branch}[/green]")
    else:
        console.print("[red]✗ Push failed[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()