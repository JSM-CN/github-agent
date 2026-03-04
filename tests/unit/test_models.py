"""Tests for data models."""

import pytest
from pydantic import ValidationError

from github_agent.models import (
    AgentRequest,
    AgentResponse,
    CodeChange,
    Feasibility,
    GeneratedCode,
    Improvement,
    Priority,
    ProjectAnalysis,
    PullRequestResult,
    WorkflowState,
)


def test_priority_enum():
    """Test Priority enum values."""
    assert Priority.HIGH.value == "high"
    assert Priority.MEDIUM.value == "medium"
    assert Priority.LOW.value == "low"


def test_feasibility_enum():
    """Test Feasibility enum values."""
    assert Feasibility.FEASIBLE.value == "feasible"
    assert Feasibility.PARTIALLY_FEASIBLE.value == "partially_feasible"
    assert Feasibility.NOT_FEASIBLE.value == "not_feasible"


def test_improvement_model():
    """Test Improvement model."""
    imp = Improvement(
        module="Authentication",
        suggestion="Add OAuth support",
        priority=Priority.HIGH,
        rationale="Security improvement",
    )

    assert imp.module == "Authentication"
    assert imp.priority == Priority.HIGH


def test_improvement_default_rationale():
    """Test Improvement with default rationale."""
    imp = Improvement(
        module="Test",
        suggestion="Test suggestion",
        priority=Priority.LOW,
    )

    assert imp.rationale == ""


def test_code_change_model():
    """Test CodeChange model."""
    change = CodeChange(
        file_path="src/main.py",
        change_type="modify",
        content="print('hello')",
        description="Add hello print",
    )

    assert change.file_path == "src/main.py"
    assert change.change_type == "modify"


def test_project_analysis_model():
    """Test ProjectAnalysis model."""
    analysis = ProjectAnalysis(
        feasibility=Feasibility.FEASIBLE,
        risks=["Risk 1", "Risk 2"],
        improvements=[
            Improvement(module="M1", suggestion="S1", priority=Priority.HIGH),
        ],
        summary="Test analysis",
    )

    assert analysis.feasibility == Feasibility.FEASIBLE
    assert len(analysis.risks) == 2
    assert len(analysis.improvements) == 1


def test_generated_code_model():
    """Test GeneratedCode model."""
    code = GeneratedCode(
        changes=[
            CodeChange(
                file_path="test.py",
                change_type="create",
                content="# test",
                description="Test file",
            ),
        ],
        commit_message="Add test",
        pr_title="Test PR",
        pr_description="Test description",
    )

    assert len(code.changes) == 1
    assert code.commit_message == "Add test"


def test_pull_request_result_success():
    """Test PullRequestResult for success."""
    result = PullRequestResult(
        success=True,
        pr_url="https://github.com/owner/repo/pull/1",
        pr_number=1,
        branch_name="feature/test",
    )

    assert result.success
    assert result.error is None


def test_pull_request_result_failure():
    """Test PullRequestResult for failure."""
    result = PullRequestResult(
        success=False,
        branch_name="feature/test",
        error="Network error",
    )

    assert not result.success
    assert result.error == "Network error"


def test_workflow_state_model():
    """Test WorkflowState model."""
    state = WorkflowState(
        request_id="req_123",
        prd_content="# PRD\nTest content",
        repo_url="https://github.com/owner/repo",
        target_branch="main",
    )

    assert state.request_id == "req_123"
    assert state.status == "pending"
    assert state.analysis is None


def test_agent_request_model():
    """Test AgentRequest model."""
    request = AgentRequest(
        prd_content="Test PRD",
        repo_url="https://github.com/owner/repo",
        target_branch="develop",
    )

    assert request.prd_content == "Test PRD"
    assert request.target_branch == "develop"
    assert request.github_token is None


def test_agent_response_model():
    """Test AgentResponse model."""
    response = AgentResponse(
        request_id="req_123",
        status="completed",
        message="Done",
    )

    assert response.status == "completed"
    assert response.error is None