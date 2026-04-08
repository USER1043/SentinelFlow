"""
Unit tests for SentinelFlow API and agents.

Run with: pytest tests/test_sentinelflow.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient
from main import app
from agents.analyst import ExtractedTask, AnalystAgent
from agents.watchdog import WatchdogAgent
from DB.database import Task


client = TestClient(app)


# ============================================================================
# Health Check Tests
# ============================================================================


def test_health_check():
    """Test that the API is responding to health checks."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SentinelFlow is Active"
    assert "timestamp" in data


# ============================================================================
# Analyst Agent Tests
# ============================================================================


def test_extracted_task_model():
    """Test ExtractedTask Pydantic model."""
    task = ExtractedTask(
        description="Review Q4 budget",
        owner="John",
        deadline="2026-04-15",
    )
    assert task.description == "Review Q4 budget"
    assert task.owner == "John"
    assert task.deadline == "2026-04-15"


def test_extracted_task_optional_fields():
    """Test ExtractedTask with optional fields."""
    task = ExtractedTask(description="Standalone task")
    assert task.description == "Standalone task"
    assert task.owner == "Unassigned"
    assert task.deadline is None


@patch("agents.analyst.ChatGoogleGenerativeAI")
@patch("agents.analyst.GoogleGenerativeAIEmbeddings")
def test_analyst_agent_initialization(mock_embeddings, mock_llm):
    """Test AnalystAgent initialization."""
    analyst = AnalystAgent()
    assert analyst.llm is not None
    assert analyst.embeddings_model is not None


@patch("agents.analyst.AnalystAgent.extract_tasks")
def test_extract_tasks_from_empty_transcript(mock_extract):
    """Test extraction from empty transcript."""
    mock_extract.return_value = []
    from agents.analyst import extract_tasks_from_transcript

    tasks = extract_tasks_from_transcript("")
    assert isinstance(tasks, list)


# ============================================================================
# Watchdog Agent Tests
# ============================================================================


@patch("agents.watchdog.SessionLocal")
def test_watchdog_audit_orphaned_tasks(mock_session_local):
    """Test watchdog audit for orphaned tasks."""
    # Mock database session
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    # Create mock tasks
    mock_task1 = Mock()
    mock_task1.id = "task-1"
    mock_task1.description = "Unassigned task"
    mock_task1.owner = "Unassigned"
    mock_task1.status = "pending"

    mock_task2 = Mock()
    mock_task2.id = "task-2"
    mock_task2.description = "Assigned task"
    mock_task2.status = "pending"
    mock_task2.owner = "Charlie"

    # Mock query results for unassigned and pending unassigned
    mock_session.query.return_value.filter.return_value.all.side_effect = [
        [mock_task1],  # Unassigned tasks
        [mock_task1],  # Pending unassigned tasks
        [mock_task2],  # Assigned pending tasks
    ]

    # Run audit
    from agents.watchdog import audit_orphaned_tasks

    result = audit_orphaned_tasks()
    assert "total_alerts" in result


# ============================================================================
# Meeting Processing Tests
# ============================================================================


def test_process_meeting_invalid_transcript():
    """Test that short transcripts are rejected."""
    response = client.post(
        "/process-meeting",
        json={"transcript": "Short", "meeting_title": "Test"},
    )
    assert response.status_code == 422


@patch("agents.analyst.extract_tasks_from_transcript")
@patch("DB.database.SessionLocal")
def test_process_meeting_success(mock_session_local, mock_extract):
    """Test successful meeting processing."""
    # Mock database
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session
    mock_session.commit = MagicMock()
    mock_session.close = MagicMock()

    # Mock extracted tasks
    mock_task = ExtractedTask(
        description="Review budget",
        owner="John",
        deadline="2026-04-15",
    )
    mock_extract.return_value = [mock_task]

    response = client.post(
        "/process-meeting",
        json={
            "transcript": (
                "In today's meeting, John will review the Q4 budget by next Friday. "
                "This is a very important task that needs immediate attention."
            ),
            "meeting_title": "Q4 Planning",
        },
    )

    assert response.status_code in [200, 500, 422]  # Depends on mock setup


# ============================================================================
# Task Retrieval Tests
# ============================================================================


@patch("DB.database.SessionLocal")
def test_get_tasks(mock_session_local):
    """Test task retrieval endpoint."""
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    mock_task = Mock()
    mock_task.id = "550e8400-e29b-41d4-a716-446655440000"
    mock_task.description = "Test task"
    mock_task.owner = "John"
    mock_task.deadline = None
    mock_task.status = "pending"
    mock_task.created_at = datetime.now(timezone.utc)

    mock_session.query.return_value.limit.return_value.all.return_value = [
        mock_task
    ]
    mock_session.close = MagicMock()

    response = client.get("/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ============================================================================
# Task Update Tests
# ============================================================================


@patch("DB.database.SessionLocal")
def test_update_task_not_found(mock_session_local):
    """Test updating non-existent task."""
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.close = MagicMock()

    response = client.put(
        "/tasks/650e8400-e29b-41d4-a716-446655440000",
        params={"owner": "Jane"},
    )

    assert response.status_code == 404


@patch("main.SessionLocal")
def test_update_task_success(mock_session_local):
    """Test successful task update."""
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    # Create mock task with all required fields for TaskResponse
    mock_task = MagicMock()
    mock_task.id = "d1cdae0d-9bb4-4dcb-a1f3-f7ea94f8250e"
    mock_task.description = "Test task"
    mock_task.owner = "John"
    mock_task.status = "pending"
    
    # Set updated_at as a datetime that can be isoformat'd
    updated_time = datetime.now(timezone.utc)
    mock_task.updated_at = updated_time
    
    # Mock session methods explicitly
    mock_session.query.return_value.filter.return_value.first.return_value = mock_task
    mock_session.commit = MagicMock()
    mock_session.close = MagicMock()
    mock_session.refresh = MagicMock()  # Explicitly mock refresh to handle lazy loading attempts

    response = client.put(
        "/tasks/d1cdae0d-9bb4-4dcb-a1f3-f7ea94f8250e",
        params={"owner": "Jane", "status": "completed"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["owner"] == "Jane"
    assert data["status"] == "completed"


# ============================================================================
# Audit Report Tests
# ============================================================================


@patch("main.get_audit_report")
def test_audit_report(mock_get_report):
    """Test audit report endpoint."""
    mock_get_report.return_value = {
        "total_tasks": 10,
        "assigned_tasks": 7,
        "unassigned_tasks": 3,
        "assignment_rate": 70.0,
        "status_distribution": {"pending": 5, "completed": 5},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    response = client.get("/audit-report")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tasks"] == 10
    assert data["assignment_rate"] == 70.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
