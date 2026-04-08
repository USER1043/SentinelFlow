"""
Main FastAPI application for SentinelFlow.

Orchestrates the multi-agent workflow:
1. Analyst Agent: Extracts tasks from meeting transcripts
2. Watchdog Agent: Audits database for orphaned tasks

Provides REST API endpoints for meeting processing and system monitoring.
"""

import os
import logging
from uuid import uuid4, UUID
from typing import List, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from DB.database import SessionLocal, Task, Base, engine, get_db
from agents.analyst import extract_tasks_from_transcript, ExtractedTask
from agents.watchdog import audit_orphaned_tasks, get_audit_report

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan Context Manager
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan: startup and shutdown events.
    
    Startup:
    - Creates all database tables
    - Initializes connections to AlloyDB using Application Default Credentials
    
    Shutdown:
    - Cleans up resources and logs shutdown
    """
    # Startup
    try:
        logger.info("SentinelFlow is starting up...")
        logger.info("Using Application Default Credentials (ADC) for authentication")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("SentinelFlow is shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="SentinelFlow API",
    description="Multi-agent system for transforming meeting transcripts into executed outcomes",
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================================
# Request/Response Models
# ============================================================================


class MeetingTranscript(BaseModel):
    """Request model for meeting processing."""

    transcript: str = Field(
        ..., description="Raw meeting transcript text", min_length=10
    )
    meeting_title: str = Field(
        default="Untitled Meeting", description="Optional meeting title"
    )


class TaskResponse(BaseModel):
    """Response model for extracted task."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    description: str
    owner: str
    deadline: str | None = None
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MeetingProcessingResponse(BaseModel):
    """Response model for meeting processing endpoint."""

    message: str
    tasks_found: int
    tasks: List[TaskResponse]
    timestamp: datetime


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    timestamp: datetime


class AuditReportResponse(BaseModel):
    """Response model for audit report."""

    total_tasks: int
    assigned_tasks: int
    unassigned_tasks: int
    assignment_rate: float
    status_distribution: Dict[str, int]
    timestamp: datetime


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for system monitoring.
    
    Returns:
        HealthResponse with system status
    """
    return HealthResponse(status="SentinelFlow is Active", timestamp=datetime.now(timezone.utc))


@app.post("/process-meeting", response_model=MeetingProcessingResponse)
async def process_meeting(
    payload: MeetingTranscript, background_tasks: BackgroundTasks
):
    """
    Process a meeting transcript and extract action items.
    
    Workflow:
    1. Invokes the Analyst agent to extract structured tasks
    2. Generates vector embeddings for semantic search
    3. Saves tasks to AlloyDB with embeddings
    4. Triggers the Watchdog audit as a background task
    
    Args:
        payload: Meeting transcript and optional metadata
        background_tasks: FastAPI background tasks manager
        
    Returns:
        MeetingProcessingResponse with extracted tasks
        
    Raises:
        HTTPException: If transcript processing fails
    """
    if not payload.transcript or len(payload.transcript.strip()) < 10:
        raise HTTPException(status_code=400, detail="Transcript is too short")

    try:
        logger.info(f"Processing meeting: {payload.meeting_title}")

        # Step 1: Extract tasks using the Analyst agent
        extracted_tasks = extract_tasks_from_transcript(payload.transcript)
        logger.info(f"Extracted {len(extracted_tasks)} tasks from transcript")

        # Step 2: Save tasks to AlloyDB
        db = SessionLocal()
        saved_tasks = []

        try:
            db_task_objects = []
            for extracted_task in extracted_tasks:
                # Create task record with embedding
                db_task = Task(
                    id=str(uuid4()),
                    description=extracted_task.description,
                    owner=extracted_task.owner,
                    deadline=(
                        datetime.fromisoformat(extracted_task.deadline)
                        if extracted_task.deadline
                        else None
                    ),
                    status="pending",
                    embedding=extracted_task.embedding if hasattr(extracted_task, 'embedding') else None,
                )
                db.add(db_task)
                db_task_objects.append(db_task)

            db.commit()
            logger.info(f"Saved {len(db_task_objects)} tasks to AlloyDB")
            
            # Refresh tasks to load database-generated values (created_at, updated_at)
            for db_task in db_task_objects:
                db.refresh(db_task)
                saved_tasks.append(
                    TaskResponse(
                        id=db_task.id,
                        description=db_task.description,
                        owner=db_task.owner,
                        deadline=db_task.deadline.isoformat() if db_task.deadline else None,
                        status=db_task.status,
                        created_at=db_task.created_at,
                    )
                )

        except Exception as e:
            db.rollback()
            logger.error(f"Error saving tasks to database: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to save tasks: {str(e)}"
            )
        finally:
            db.close()

        # Step 3: Trigger Watchdog audit as background task
        background_tasks.add_task(audit_orphaned_tasks)
        logger.info("Watchdog audit scheduled as background task")

        return MeetingProcessingResponse(
            message="Meeting successfully processed",
            tasks_found=len(saved_tasks),
            tasks=saved_tasks,
            timestamp=datetime.now(timezone.utc),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during meeting processing: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/audit-report", response_model=AuditReportResponse)
async def get_audit_report_endpoint():
    """
    Get a comprehensive audit report of all tasks.
    
    Includes statistics on:
    - Total tasks in the system
    - Assignment rates
    - Status distribution
    
    Returns:
        AuditReportResponse with audit statistics
        
    Raises:
        HTTPException: If audit fails
    """
    try:
        logger.info("Generating audit report")
        report = get_audit_report()

        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])

        return AuditReportResponse(**report)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating audit report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks")
async def get_tasks(status: str = None, owner: str = None, limit: int = 100):
    """
    Retrieve tasks from the database with optional filtering.
    
    Args:
        status: Filter by task status (pending, completed, etc.)
        owner: Filter by task owner name
        limit: Maximum number of tasks to return (default 100)
        
    Returns:
        List of tasks matching the filter criteria
    """
    try:
        db = SessionLocal()
        query = db.query(Task)

        if status:
            query = query.filter(Task.status == status)
        if owner:
            query = query.filter(Task.owner == owner)

        tasks = query.limit(limit).all()
        db.close()

        return [
            {
                "id": str(task.id),
                "description": task.description,
                "owner": task.owner,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
            }
            for task in tasks
        ]

    except Exception as e:
        logger.error(f"Error retrieving tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/tasks/{task_id}")
async def update_task(task_id: str, owner: str = None, status: str = None):
    """
    Update a task's owner or status.
    
    Args:
        task_id: UUID of the task to update
        owner: New owner name
        status: New status
        
    Returns:
        Updated task details
        
    Raises:
        HTTPException: If task not found, invalid UUID, or update fails
    """
    try:
        # Validate UUID format
        try:
            UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Task not found")
        
        db = SessionLocal()
        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            db.close()
            raise HTTPException(status_code=404, detail="Task not found")

        if owner:
            task.owner = owner
        if status:
            task.status = status

        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        # Collect all data while session is active
        response_data = {
            "id": str(task.id),
            "description": task.description,
            "owner": task.owner,
            "status": task.status,
            "updated_at": task.updated_at.isoformat(),
        }
        
        db.close()

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Entry Point
# ============================================================================


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8080))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
