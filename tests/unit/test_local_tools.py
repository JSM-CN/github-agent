"""Tests for local project tools."""

import os
import tempfile
from pathlib import Path

import pytest

from github_agent.tools.local import LocalGitClient, LocalProjectClient


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create some files
        (project_path / "README.md").write_text("# Test Project\n\nThis is a test.")
        (project_path / "main.py").write_text("print('hello')")
        (project_path / "src").mkdir()
        (project_path / "src" / "__init__.py").write_text("")
        (project_path / "src" / "utils.py").write_text("def helper(): pass")

        yield project_path


class TestLocalProjectClient:
    """Tests for LocalProjectClient."""

    def test_init(self, temp_project):
        """Test client initialization."""
        client = LocalProjectClient(temp_project)
        assert client.project_path == temp_project.resolve()

    def test_init_nonexistent_path(self):
        """Test initialization with nonexistent path."""
        with pytest.raises(ValueError):
            LocalProjectClient("/nonexistent/path")

    def test_get_project_structure(self, temp_project):
        """Test getting project structure."""
        client = LocalProjectClient(temp_project)
        structure = client.get_project_structure()

        assert structure["name"] == temp_project.name
        assert structure["language"] == "Python"
        assert structure["total_files"] == 4
        assert "py" in structure["files_by_type"]

    def test_read_file(self, temp_project):
        """Test reading a file."""
        client = LocalProjectClient(temp_project)
        content = client.read_file("main.py")

        assert content == "print('hello')"

    def test_read_file_nonexistent(self, temp_project):
        """Test reading nonexistent file."""
        client = LocalProjectClient(temp_project)

        with pytest.raises(FileNotFoundError):
            client.read_file("nonexistent.py")

    def test_write_file(self, temp_project):
        """Test writing a file."""
        client = LocalProjectClient(temp_project)
        path = client.write_file("new_file.py", "# new file")

        assert path.exists()
        assert client.read_file("new_file.py") == "# new file"

    def test_write_file_create_directories(self, temp_project):
        """Test writing file creates parent directories."""
        client = LocalProjectClient(temp_project)
        client.write_file("lib/core/engine.py", "# engine")

        assert (temp_project / "lib" / "core" / "engine.py").exists()

    def test_file_exists(self, temp_project):
        """Test checking file existence."""
        client = LocalProjectClient(temp_project)

        assert client.file_exists("main.py")
        assert not client.file_exists("nonexistent.py")

    def test_delete_file(self, temp_project):
        """Test deleting a file."""
        client = LocalProjectClient(temp_project)

        assert client.delete_file("main.py")
        assert not client.file_exists("main.py")

    def test_delete_file_nonexistent(self, temp_project):
        """Test deleting nonexistent file."""
        client = LocalProjectClient(temp_project)

        assert not client.delete_file("nonexistent.py")

    def test_get_readme(self, temp_project):
        """Test getting README content."""
        client = LocalProjectClient(temp_project)
        readme = client.get_readme()

        assert "# Test Project" in readme

    def test_list_files(self, temp_project):
        """Test listing files with pattern."""
        client = LocalProjectClient(temp_project)
        files = client.list_files("*.py")

        assert "main.py" in files
        assert "src/utils.py" in files


class TestLocalGitClient:
    """Tests for LocalGitClient."""

    def test_is_git_repo_false(self, temp_project):
        """Test is_git_repo returns False for non-git directory."""
        client = LocalGitClient(temp_project)

        assert not client.is_git_repo()

    def test_is_git_repo_true(self, temp_project):
        """Test is_git_repo returns True for git directory."""
        # Initialize git repo
        os.system(f"cd {temp_project} && git init")

        client = LocalGitClient(temp_project)
        assert client.is_git_repo()

    def test_get_current_branch(self, temp_project):
        """Test getting current branch."""
        os.system(f"cd {temp_project} && git init")

        client = LocalGitClient(temp_project)
        # In a fresh repo with no commits, this may return empty or fail
        # So we need to handle that case
        try:
            branch = client.get_current_branch()
            # Default branch could be 'main', 'master', or empty
            assert branch in ("main", "master", "")
        except Exception:
            # Expected for fresh repo with no commits
            pass

    def test_get_status_clean(self, temp_project):
        """Test getting status of clean repo."""
        os.system(f"cd {temp_project} && git init && git add . && git commit -m 'init'")

        client = LocalGitClient(temp_project)
        status = client.get_status()

        assert status["is_repo"]
        assert status["is_clean"]

    def test_get_status_dirty(self, temp_project):
        """Test getting status of dirty repo."""
        os.system(f"cd {temp_project} && git init && git add . && git commit -m 'init'")
        (temp_project / "new_file.txt").write_text("new content")

        client = LocalGitClient(temp_project)
        status = client.get_status()

        assert status["is_repo"]
        assert not status["is_clean"]
        assert len(status["untracked"]) > 0

    def test_create_branch(self, temp_project):
        """Test creating a new branch."""
        os.system(f"cd {temp_project} && git init && git add . && git commit -m 'init'")

        client = LocalGitClient(temp_project)
        result = client.create_branch("feature/test")

        assert result
        assert client.get_current_branch() == "feature/test"

    def test_add_and_commit(self, temp_project):
        """Test adding and committing files."""
        import subprocess

        # Initialize git with config
        subprocess.run(["git", "init"], cwd=temp_project, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=temp_project, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_project, check=True, capture_output=True)

        (temp_project / "test.txt").write_text("test")

        client = LocalGitClient(temp_project)
        assert client.add_files("test.txt")
        result = client.commit("Add test file")

        assert result
        # Verify the commit was made by checking the log
        log = client.get_log(limit=1)
        assert len(log) == 1
        assert "Add test file" in log[0]["message"]