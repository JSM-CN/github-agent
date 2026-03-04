"""Utility functions for GitHub Agent."""

import re
import uuid
from datetime import datetime


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


def generate_branch_name(prefix: str, description: str) -> str:
    """Generate a branch name from a description.

    Args:
        prefix: Branch name prefix
        description: Description to derive branch name from

    Returns:
        A sanitized branch name
    """
    # Clean and sanitize the description
    clean_desc = re.sub(r"[^a-zA-Z0-9\s-]", "", description.lower())
    clean_desc = re.sub(r"\s+", "-", clean_desc.strip())
    clean_desc = clean_desc[:50]  # Limit length

    # Add timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    return f"{prefix}/{clean_desc}-{timestamp}"


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse GitHub URL to extract owner and repo name.

    Args:
        url: GitHub repository URL

    Returns:
        Tuple of (owner, repo_name)

    Raises:
        ValueError: If URL is not a valid GitHub URL
    """
    patterns = [
        r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"github\.com/([^/]+)/([^/]+)/?$",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            owner = match.group(1)
            repo = match.group(2).replace(".git", "")
            return owner, repo

    raise ValueError(f"Invalid GitHub URL: {url}")


def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to a maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."