"""GitHub API tools for repository operations."""

import json
import os
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from github_agent.config import get_settings
from github_agent.utils import parse_github_url


class GitHubClient:
    """GitHub API client for repository operations."""

    def __init__(self, token: str | None = None):
        """Initialize GitHub client.

        Args:
            token: GitHub personal access token (optional, uses settings if not provided)
        """
        settings = get_settings()
        self.token = token or settings.github_token
        self.base_url = settings.github_base_url
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        # Support proxy from environment variables
        self.proxy = None
        http_proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if http_proxy:
            # 确保代理地址有协议前缀
            if not http_proxy.startswith("http://") and not http_proxy.startswith("https://"):
                http_proxy = f"http://{http_proxy}"
            self.proxy = http_proxy

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Make an authenticated request to GitHub API.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for httpx

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(
                method, url, headers=self.headers, timeout=30.0, **kwargs
            )
            if response.status_code >= 400:
                # 打印错误详情以便调试
                try:
                    error_detail = response.json()
                    print(f"GitHub API Error ({response.status_code}): {error_detail}")
                except:
                    print(f"GitHub API Error ({response.status_code}): {response.text}")
            response.raise_for_status()
            return response.json()  # type: ignore

    async def get_repo_info(self, repo_url: str) -> dict[str, Any]:
        """Get repository information.

        Args:
            repo_url: GitHub repository URL

        Returns:
            Repository information dictionary
        """
        owner, repo = parse_github_url(repo_url)
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def get_repo_contents(
        self, repo_url: str, path: str = "", ref: str | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Get repository file/directory contents.

        Args:
            repo_url: GitHub repository URL
            path: Path to file or directory
            ref: Git reference (branch, tag, commit)

        Returns:
            File/directory contents
        """
        owner, repo = parse_github_url(repo_url)
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        if ref:
            endpoint += f"?ref={ref}"
        return await self._request("GET", endpoint)

    async def get_readme(self, repo_url: str, ref: str | None = None) -> str:
        """Get repository README content.

        Args:
            repo_url: GitHub repository URL
            ref: Git reference (branch, tag, commit)

        Returns:
            README content as string
        """
        owner, repo = parse_github_url(repo_url)
        endpoint = f"/repos/{owner}/{repo}/readme"
        if ref:
            endpoint += f"?ref={ref}"

        import base64

        data = await self._request("GET", endpoint)
        if isinstance(data, dict) and "content" in data:
            content = data["content"]
            # GitHub returns base64 encoded content
            return base64.b64decode(content).decode("utf-8")
        return ""

    async def get_file_content(
        self, repo_url: str, file_path: str, ref: str | None = None
    ) -> str:
        """Get specific file content from repository.

        Args:
            repo_url: GitHub repository URL
            file_path: Path to the file
            ref: Git reference (branch, tag, commit)

        Returns:
            File content as string
        """
        owner, repo = parse_github_url(repo_url)
        endpoint = f"/repos/{owner}/{repo}/contents/{file_path}"
        if ref:
            endpoint += f"?ref={ref}"

        import base64

        data = await self._request("GET", endpoint)
        if isinstance(data, dict) and "content" in data:
            content = data["content"]
            return base64.b64decode(content).decode("utf-8")
        return ""

    async def list_tree(
        self, repo_url: str, branch: str = "main", recursive: bool = True
    ) -> list[dict[str, Any]]:
        """List repository file tree.

        Args:
            repo_url: GitHub repository URL
            branch: Branch name
            recursive: Whether to list recursively

        Returns:
            List of file tree entries
        """
        owner, repo = parse_github_url(repo_url)

        # First get the branch's commit SHA
        ref_data = await self._request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        commit_sha = ref_data["object"]["sha"]

        # Get the tree
        tree_url = f"/repos/{owner}/{repo}/git/trees/{commit_sha}"
        if recursive:
            tree_url += "?recursive=1"

        tree_data = await self._request("GET", tree_url)
        return tree_data.get("tree", [])

    async def get_issues(
        self,
        repo_url: str,
        state: str = "open",
        labels: list[str] | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Get repository issues.

        Args:
            repo_url: GitHub repository URL
            state: Issue state ('open', 'closed', 'all')
            labels: Filter by labels
            limit: Maximum number of issues to return

        Returns:
            List of issues
        """
        owner, repo = parse_github_url(repo_url)
        endpoint = f"/repos/{owner}/{repo}/issues?state={state}&per_page={limit}"
        if labels:
            endpoint += f"&labels={','.join(labels)}"

        return await self._request("GET", endpoint)  # type: ignore

    async def create_branch(
        self, repo_url: str, branch_name: str, base_branch: str = "main"
    ) -> dict[str, Any]:
        """Create a new branch in the repository.

        Args:
            repo_url: GitHub repository URL
            branch_name: Name for the new branch
            base_branch: Base branch to create from

        Returns:
            Created branch reference data
        """
        owner, repo = parse_github_url(repo_url)

        # Get the SHA of the base branch
        ref_data = await self._request(
            "GET", f"/repos/{owner}/{repo}/git/ref/heads/{base_branch}"
        )
        sha = ref_data["object"]["sha"]

        # Create the new branch
        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )

    async def create_file(
        self,
        repo_url: str,
        file_path: str,
        content: str,
        message: str,
        branch: str,
    ) -> dict[str, Any]:
        """Create a new file in the repository.

        Args:
            repo_url: GitHub repository URL
            file_path: Path where to create the file
            content: File content
            message: Commit message
            branch: Branch name

        Returns:
            Created file data
        """
        owner, repo = parse_github_url(repo_url)

        import base64

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        return await self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{file_path}",
            json={
                "message": message,
                "content": encoded_content,
                "branch": branch,
            },
        )

    async def update_file(
        self,
        repo_url: str,
        file_path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing file in the repository.

        Args:
            repo_url: GitHub repository URL
            file_path: Path to the file
            content: New file content
            message: Commit message
            branch: Branch name
            sha: File SHA (will be fetched if not provided)

        Returns:
            Updated file data
        """
        owner, repo = parse_github_url(repo_url)

        import base64

        # Get SHA if not provided
        if not sha:
            file_data = await self._request(
                "GET", f"/repos/{owner}/{repo}/contents/{file_path}?ref={branch}"
            )
            if isinstance(file_data, dict):
                sha = file_data.get("sha")
            else:
                raise ValueError(f"Could not get SHA for file: {file_path}")

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        return await self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{file_path}",
            json={
                "message": message,
                "content": encoded_content,
                "sha": sha,
                "branch": branch,
            },
        )

    async def create_pull_request(
        self,
        repo_url: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> dict[str, Any]:
        """Create a pull request.

        Args:
            repo_url: GitHub repository URL
            title: PR title
            body: PR description
            head_branch: Source branch
            base_branch: Target branch

        Returns:
            Created pull request data
        """
        owner, repo = parse_github_url(repo_url)

        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
            },
        )

    async def get_repo_structure(self, repo_url: str, branch: str = "main") -> dict[str, Any]:
        """Get a structured overview of the repository.

        Args:
            repo_url: GitHub repository URL
            branch: Branch to analyze

        Returns:
            Structured repository information
        """
        # Get repo info
        repo_info = await self.get_repo_info(repo_url)

        # Get file tree
        tree = await self.list_tree(repo_url, branch, recursive=True)

        # Analyze structure
        files_by_type: dict[str, list[str]] = {}
        directories: set[str] = set()
        total_files = 0
        total_size = 0

        for entry in tree:
            if entry["type"] == "tree":
                directories.add(entry["path"])
            else:
                total_files += 1
                total_size += entry.get("size", 0)

                # Categorize by extension
                path = entry["path"]
                ext = path.rsplit(".", 1)[-1] if "." in path else "no_extension"
                if ext not in files_by_type:
                    files_by_type[ext] = []
                files_by_type[ext].append(path)

        return {
            "name": repo_info.get("name", ""),
            "description": repo_info.get("description", ""),
            "language": repo_info.get("language", ""),
            "stars": repo_info.get("stargazers_count", 0),
            "forks": repo_info.get("forks_count", 0),
            "topics": repo_info.get("topics", []),
            "total_files": total_files,
            "total_size": total_size,
            "directories": sorted(directories)[:50],  # Limit to 50 directories
            "files_by_type": files_by_type,
            "branch": branch,
        }

    async def search_similar_repos(
        self, query: str, language: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Search for similar repositories on GitHub.

        Args:
            query: Search query
            language: Filter by programming language
            limit: Maximum number of results

        Returns:
            List of similar repositories
        """
        search_query = query
        if language:
            search_query += f" language:{language}"

        endpoint = f"/search/repositories?q={search_query}&sort=stars&order=desc&per_page={limit}"
        result = await self._request("GET", endpoint)

        items = result.get("items", [])
        return [
            {
                "full_name": repo.get("full_name", ""),
                "description": repo.get("description", ""),
                "stars": repo.get("stargazers_count", 0),
                "url": repo.get("html_url", ""),
                "language": repo.get("language", ""),
            }
            for repo in items
        ]