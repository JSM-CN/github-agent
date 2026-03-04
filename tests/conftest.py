"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_anthropic_key(monkeypatch):
    """Set mock Anthropic API key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-12345")


@pytest.fixture
def mock_github_token(monkeypatch):
    """Set mock GitHub token."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_12345")