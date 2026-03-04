"""Module 6: GitHub Operator Agent.

Handles GitHub operations: creating branches, commits, and pull requests.
"""

from github_agent.agents.base import BaseAgent
from github_agent.models import GeneratedCode, PullRequestResult
from github_agent.tools.claude import ClaudeClient
from github_agent.tools.github import GitHubClient
from github_agent.utils import generate_branch_name, parse_github_url


class GitHubOperatorAgent(BaseAgent[GeneratedCode, PullRequestResult]):
    """Agent for GitHub operations (branches, commits, PRs)."""

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
        github_client: GitHubClient | None = None,
    ):
        """Initialize the GitHub operator agent.

        Args:
            claude_client: Claude API client (not used but required by base)
            github_client: GitHub API client
        """
        super().__init__(claude_client, github_client)

    @property
    def name(self) -> str:
        return "GitHubOperatorAgent"

    @property
    def description(self) -> str:
        return "Creates branches, commits, and pull requests on GitHub"

    async def execute(
        self,
        input_data: GeneratedCode,
        repo_url: str,
        base_branch: str = "main",
        pr_title: str | None = None,
        pr_description: str | None = None,
        dry_run: bool = False,
    ) -> PullRequestResult:
        """Execute GitHub operations to create a PR.

        Args:
            input_data: Generated code changes
            repo_url: GitHub repository URL
            base_branch: Target branch for the PR
            pr_title: Override PR title
            pr_description: Override PR description
            dry_run: If True, don't actually create PR (for testing)

        Returns:
            PullRequestResult with PR URL and details
        """
        if not input_data.changes:
            self.log("No changes to commit")
            return PullRequestResult(
                success=False,
                error="No changes to commit",
            )

        self.log(f"Processing {len(input_data.changes)} file changes")

        # Generate branch name
        branch_name = generate_branch_name(
            prefix="auto-pr",
            description=input_data.pr_title,
        )
        self.log(f"Branch name: {branch_name}")

        if dry_run:
            self.log("[DRY RUN] Would create branch and PR")
            return PullRequestResult(
                success=True,
                branch_name=branch_name,
                pr_url=None,
                pr_number=None,
            )

        try:
            # Step 1: Create branch
            self.log(f"Creating branch '{branch_name}' from '{base_branch}'")
            await self.github_client.create_branch(repo_url, branch_name, base_branch)

            # Step 2: Commit all changes
            for i, change in enumerate(input_data.changes, 1):
                self.log(f"Committing change {i}/{len(input_data.changes)}: {change.file_path}")
                await self._commit_change(repo_url, change, branch_name)

            # Step 3: Create PR
            title = pr_title or input_data.pr_title
            description = pr_description or input_data.pr_description

            self.log("Creating pull request...")
            pr_data = await self.github_client.create_pull_request(
                repo_url=repo_url,
                title=title,
                body=description,
                head_branch=branch_name,
                base_branch=base_branch,
            )

            pr_url = pr_data.get("html_url", "")
            pr_number = pr_data.get("number")

            self.log(f"PR created: {pr_url}")

            return PullRequestResult(
                success=True,
                pr_url=pr_url,
                pr_number=pr_number,
                branch_name=branch_name,
            )

        except Exception as e:
            self.log(f"Error: {e}")
            return PullRequestResult(
                success=False,
                branch_name=branch_name,
                error=str(e),
            )

    async def _commit_change(
        self,
        repo_url: str,
        change: "github_agent.models.CodeChange",
        branch: str,
    ) -> None:
        """Commit a single file change.

        Args:
            repo_url: GitHub repository URL
            change: Code change to commit
            branch: Branch to commit to
        """
        if change.change_type == "create":
            await self.github_client.create_file(
                repo_url=repo_url,
                file_path=change.file_path,
                content=change.content,
                message=f"Create {change.file_path}: {change.description}",
                branch=branch,
            )
        elif change.change_type == "modify":
            await self.github_client.update_file(
                repo_url=repo_url,
                file_path=change.file_path,
                content=change.content,
                message=f"Update {change.file_path}: {change.description}",
                branch=branch,
            )
        elif change.change_type == "delete":
            # Delete is not supported in this implementation
            self.log(f"Warning: Delete operation not implemented for {change.file_path}")

    async def create_branch_only(
        self,
        repo_url: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> bool:
        """Create only a branch without making changes.

        Args:
            repo_url: GitHub repository URL
            branch_name: Name for the new branch
            base_branch: Base branch to create from

        Returns:
            True if successful
        """
        try:
            await self.github_client.create_branch(repo_url, branch_name, base_branch)
            self.log(f"Created branch: {branch_name}")
            return True
        except Exception as e:
            self.log(f"Failed to create branch: {e}")
            return False

    async def check_repo_access(self, repo_url: str) -> bool:
        """Check if we have write access to the repository.

        Args:
            repo_url: GitHub repository URL

        Returns:
            True if we have write access
        """
        try:
            owner, repo = parse_github_url(repo_url)
            # Try to get repo info - will fail if no access
            info = await self.github_client.get_repo_info(repo_url)
            permissions = info.get("permissions", {})
            return permissions.get("push", False)
        except Exception:
            return False


# Import for type hints
import github_agent.models