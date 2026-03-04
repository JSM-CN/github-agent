"""Local filesystem tools for working with local projects."""

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml


class LocalProjectClient:
    """Client for working with local project directories."""

    def __init__(self, project_path: str | Path):
        """Initialize local project client.

        Args:
            project_path: Path to the local project directory
        """
        self.project_path = Path(project_path).resolve()
        if not self.project_path.exists():
            raise ValueError(f"Project path does not exist: {self.project_path}")

    def get_project_structure(self) -> dict[str, Any]:
        """Get a structured overview of the local project.

        Returns:
            Structured project information
        """
        files_by_type: dict[str, list[str]] = {}
        directories: list[str] = []
        total_files = 0
        total_size = 0

        # Walk the directory tree
        for root, dirs, files in os.walk(self.project_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", "venv", ".venv", "build", "dist")
            ]

            rel_root = os.path.relpath(root, self.project_path)
            if rel_root != ".":
                directories.append(rel_root)

            for file in files:
                if file.startswith("."):
                    continue

                total_files += 1
                file_path = os.path.join(rel_root, file) if rel_root != "." else file

                # Get file size
                try:
                    full_path = os.path.join(root, file)
                    total_size += os.path.getsize(full_path)
                except OSError:
                    pass

                # Categorize by extension
                ext = file.rsplit(".", 1)[-1] if "." in file else "no_extension"
                if ext not in files_by_type:
                    files_by_type[ext] = []
                files_by_type[ext].append(file_path)

        # Get project name
        project_name = self.project_path.name

        # Try to detect language from files
        language = self._detect_language(files_by_type)

        # Try to read project metadata
        description = self._get_project_description()

        return {
            "name": project_name,
            "description": description,
            "language": language,
            "path": str(self.project_path),
            "total_files": total_files,
            "total_size": total_size,
            "directories": directories[:50],
            "files_by_type": files_by_type,
        }

    def _detect_language(self, files_by_type: dict[str, list[str]]) -> str:
        """Detect primary programming language.

        Args:
            files_by_type: Files categorized by extension

        Returns:
            Detected language name
        """
        lang_map = {
            "py": "Python",
            "js": "JavaScript",
            "ts": "TypeScript",
            "java": "Java",
            "go": "Go",
            "rs": "Rust",
            "rb": "Ruby",
            "php": "PHP",
            "cpp": "C++",
            "c": "C",
            "cs": "C#",
            "swift": "Swift",
            "kt": "Kotlin",
        }

        # Count files per language
        lang_counts: dict[str, int] = {}
        for ext, files in files_by_type.items():
            lang = lang_map.get(ext, "Unknown")
            lang_counts[lang] = lang_counts.get(lang, 0) + len(files)

        if lang_counts:
            return max(lang_counts, key=lang_counts.get)
        return "Unknown"

    def _get_project_description(self) -> str:
        """Try to get project description from README or package files.

        Returns:
            Project description
        """
        # Try README
        for readme_name in ["README.md", "README.rst", "README.txt", "readme.md"]:
            readme_path = self.project_path / readme_name
            if readme_path.exists():
                content = readme_path.read_text(encoding="utf-8")
                # Return first 500 chars
                return content[:500]

        # Try package.json
        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                import json

                data = json.loads(package_json.read_text())
                return data.get("description", "")
            except (json.JSONDecodeError, KeyError):
                pass

        # Try pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                # Simple extraction - look for description
                for line in content.split("\n"):
                    if "description" in line.lower():
                        parts = line.split("=")
                        if len(parts) == 2:
                            return parts[1].strip().strip('"\'')
            except Exception:
                pass

        return ""

    def read_file(self, file_path: str) -> str:
        """Read a file from the project.

        Args:
            file_path: Relative path to the file

        Returns:
            File content

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        full_path = self.project_path / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return full_path.read_text(encoding="utf-8")

    def write_file(self, file_path: str, content: str) -> Path:
        """Write a file to the project.

        Args:
            file_path: Relative path to the file
            content: File content

        Returns:
            Path to the written file
        """
        full_path = self.project_path / file_path

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        full_path.write_text(content, encoding="utf-8")
        return full_path

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the project.

        Args:
            file_path: Relative path to the file

        Returns:
            True if deleted successfully
        """
        full_path = self.project_path / file_path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists.

        Args:
            file_path: Relative path to the file

        Returns:
            True if file exists
        """
        return (self.project_path / file_path).exists()

    def list_files(
        self,
        pattern: str = "*",
        directory: str | None = None,
    ) -> list[str]:
        """List files matching a pattern.

        Args:
            pattern: Glob pattern to match
            directory: Subdirectory to search in (optional)

        Returns:
            List of relative file paths
        """
        search_path = self.project_path / directory if directory else self.project_path
        files = []
        for path in search_path.rglob(pattern):
            if path.is_file():
                rel_path = path.relative_to(self.project_path)
                files.append(str(rel_path))
        return files

    def get_readme(self) -> str:
        """Get README content.

        Returns:
            README content or empty string
        """
        for readme_name in ["README.md", "README.rst", "README.txt"]:
            readme_path = self.project_path / readme_name
            if readme_path.exists():
                return readme_path.read_text(encoding="utf-8")
        return ""

    def get_issues_from_file(self, issues_file: str = "ISSUES.md") -> list[dict[str, Any]]:
        """Get issues from a local issues file.

        Args:
            issues_file: Name of the issues file

        Returns:
            List of issue dictionaries
        """
        issues_path = self.project_path / issues_file
        if not issues_path.exists():
            return []

        content = issues_path.read_text(encoding="utf-8")
        issues = []

        # Parse markdown-style issues
        # Expected format: ## Issue: Title\nDescription
        import re

        pattern = r"##\s*(?:Issue|#)\s*[:\s]*(.+?)(?:\n|$)(.*?)(?=##|$)"
        matches = re.findall(pattern, content, re.DOTALL)

        for i, (title, body) in enumerate(matches, 1):
            issues.append(
                {
                    "number": i,
                    "title": title.strip(),
                    "body": body.strip(),
                }
            )

        return issues


class LocalGitClient:
    """Client for git operations on local repositories."""

    def __init__(self, project_path: str | Path):
        """Initialize local git client.

        Args:
            project_path: Path to the local git repository
        """
        self.project_path = Path(project_path).resolve()
        self.git_dir = self.project_path / ".git"

    def is_git_repo(self) -> bool:
        """Check if the directory is a git repository.

        Returns:
            True if it's a git repository
        """
        return self.git_dir.exists()

    def _run_git(self, *args: str, check: bool = True) -> str:
        """Run a git command.

        Args:
            *args: Git command arguments
            check: Raise exception on failure

        Returns:
            Command output

        Raises:
            subprocess.CalledProcessError: If command fails and check=True
        """
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.project_path,
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout.strip()

    def get_current_branch(self) -> str:
        """Get the current branch name.

        Returns:
            Current branch name
        """
        if not self.is_git_repo():
            return ""
        return self._run_git("rev-parse", "--abbrev-ref", "HEAD")

    def get_status(self) -> dict[str, Any]:
        """Get repository status.

        Returns:
            Status dictionary with staged, unstaged, untracked files
        """
        if not self.is_git_repo():
            return {"is_repo": False}

        # Get porcelain status
        status_output = self._run_git("status", "--porcelain")

        staged = []
        unstaged = []
        untracked = []

        for line in status_output.split("\n"):
            if not line:
                continue

            index_status = line[0]
            work_tree_status = line[1] if len(line) > 1 else " "
            file_path = line[3:] if len(line) > 2 else ""

            if index_status in ("M", "A", "D", "R"):
                staged.append({"status": index_status, "file": file_path})
            elif work_tree_status in ("M", "D"):
                unstaged.append({"status": work_tree_status, "file": file_path})
            elif index_status == "?":
                untracked.append(file_path)

        return {
            "is_repo": True,
            "branch": self.get_current_branch(),
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "is_clean": not (staged or unstaged or untracked),
        }

    def create_branch(self, branch_name: str) -> bool:
        """Create and checkout a new branch.

        Args:
            branch_name: Name for the new branch

        Returns:
            True if successful
        """
        if not self.is_git_repo():
            return False
        try:
            self._run_git("checkout", "-b", branch_name)
            return True
        except subprocess.CalledProcessError:
            return False

    def checkout_branch(self, branch_name: str) -> bool:
        """Checkout an existing branch.

        Args:
            branch_name: Branch to checkout

        Returns:
            True if successful
        """
        if not self.is_git_repo():
            return False
        try:
            self._run_git("checkout", branch_name)
            return True
        except subprocess.CalledProcessError:
            return False

    def add_files(self, *file_paths: str) -> bool:
        """Stage files for commit.

        Args:
            *file_paths: Files to stage

        Returns:
            True if successful
        """
        if not self.is_git_repo():
            return False
        try:
            self._run_git("add", *file_paths)
            return True
        except subprocess.CalledProcessError:
            return False

    def add_all(self) -> bool:
        """Stage all changes.

        Returns:
            True if successful
        """
        if not self.is_git_repo():
            return False
        try:
            self._run_git("add", "-A")
            return True
        except subprocess.CalledProcessError:
            return False

    def commit(self, message: str) -> bool:
        """Create a commit with staged changes.

        Args:
            message: Commit message

        Returns:
            True if successful
        """
        if not self.is_git_repo():
            return False
        try:
            self._run_git("commit", "-m", message)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_log(self, limit: int = 10) -> list[dict[str, str]]:
        """Get recent commit history.

        Args:
            limit: Maximum number of commits

        Returns:
            List of commit dictionaries
        """
        if not self.is_git_repo():
            return []

        log_format = "%H|%h|%s|%an|%ad"
        log_output = self._run_git(
            "log",
            f"--pretty=format:{log_format}",
            "--date=short",
            f"-{limit}",
        )

        commits = []
        for line in log_output.split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                commits.append(
                    {
                        "hash": parts[0],
                        "short_hash": parts[1],
                        "message": parts[2],
                        "author": parts[3],
                        "date": parts[4],
                    }
                )

        return commits

    def get_diff(self, staged: bool = False) -> str:
        """Get diff of changes.

        Args:
            staged: Show staged changes only

        Returns:
            Diff output
        """
        if not self.is_git_repo():
            return ""

        args = ["diff"]
        if staged:
            args.append("--staged")
        return self._run_git(*args)

    def has_remote(self, remote_name: str = "origin") -> bool:
        """Check if remote exists.

        Args:
            remote_name: Name of the remote

        Returns:
            True if remote exists
        """
        if not self.is_git_repo():
            return False
        try:
            output = self._run_git("remote")
            return remote_name in output.split("\n")
        except subprocess.CalledProcessError:
            return False

    def push(
        self,
        remote_name: str = "origin",
        branch: str | None = None,
        set_upstream: bool = False,
    ) -> bool:
        """Push to remote.

        Args:
            remote_name: Name of the remote
            branch: Branch to push (current if None)
            set_upstream: Set upstream for the branch

        Returns:
            True if successful
        """
        if not self.is_git_repo():
            return False

        args = ["push", remote_name]
        if branch:
            args.append(branch)
        if set_upstream:
            args.insert(1, "-u")

        try:
            self._run_git(*args)
            return True
        except subprocess.CalledProcessError:
            return False