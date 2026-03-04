"""Tests for utility functions."""

import pytest

from github_agent.utils import (
    generate_branch_name,
    generate_request_id,
    parse_github_url,
    truncate_text,
)


def test_generate_request_id():
    """Test request ID generation."""
    id1 = generate_request_id()
    id2 = generate_request_id()

    assert id1.startswith("req_")
    assert id2.startswith("req_")
    assert id1 != id2  # Should be unique


def test_generate_branch_name():
    """Test branch name generation."""
    branch = generate_branch_name("auto-pr", "Add new feature for user authentication")

    assert branch.startswith("auto-pr/")
    assert "add-new-feature" in branch or "add" in branch
    # Should be sanitized
    assert " " not in branch
    assert not any(c in branch for c in "!@#$%^&*()")


def test_generate_branch_name_special_chars():
    """Test branch name with special characters."""
    branch = generate_branch_name("feature", "Fix bug #123: user@example.com")

    assert branch.startswith("feature/")
    assert "#" not in branch
    assert "@" not in branch


def test_parse_github_url_https():
    """Test parsing HTTPS GitHub URL."""
    owner, repo = parse_github_url("https://github.com/anthropics/claude-code")

    assert owner == "anthropics"
    assert repo == "claude-code"


def test_parse_github_url_https_with_git():
    """Test parsing HTTPS GitHub URL with .git suffix."""
    owner, repo = parse_github_url("https://github.com/anthropics/claude-code.git")

    assert owner == "anthropics"
    assert repo == "claude-code"


def test_parse_github_url_ssh():
    """Test parsing SSH GitHub URL."""
    owner, repo = parse_github_url("git@github.com:anthropics/claude-code.git")

    assert owner == "anthropics"
    assert repo == "claude-code"


def test_parse_github_url_invalid():
    """Test parsing invalid URL raises error."""
    with pytest.raises(ValueError):
        parse_github_url("https://gitlab.com/user/repo")

    with pytest.raises(ValueError):
        parse_github_url("not-a-url")


def test_truncate_text_short():
    """Test truncate with short text."""
    text = "Short text"
    result = truncate_text(text, max_length=100)

    assert result == text


def test_truncate_text_long():
    """Test truncate with long text."""
    text = "A" * 1000
    result = truncate_text(text, max_length=100)

    assert len(result) == 100
    assert result.endswith("...")


def test_truncate_text_exact():
    """Test truncate with exact length."""
    text = "A" * 100
    result = truncate_text(text, max_length=100)

    assert result == text