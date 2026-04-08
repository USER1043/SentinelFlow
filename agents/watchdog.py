"""
Watchdog Agent module for SentinelFlow.

Proactively audits the database for orphaned tasks and generates alerts
for action items that need attention.
"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from DB.database import Task, SessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WatchdogAgent:
    """
    Watchdog agent for monitoring and alerting on unassigned tasks.
    
    Proactively audits the database for:
    - Tasks with owner="Unassigned" (no one has taken responsibility)
    - Pending tasks that remain unassigned (high-risk items requiring escalation)
    
    Alerts are triggered only for critical situations (pending + unassigned),
    not for assigned tasks that are still in progress.
    """

    def __init__(self, db_session: Session = None):
        """
        Initialize the Watchdog agent.
        
        Args:
            db_session: Optional database session. If not provided, creates a new one.
        """
        self.db_session = db_session
        self.should_cleanup = db_session is None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup database session if needed."""
        if self.should_cleanup and self.db_session:
            self.db_session.close()

    def audit_orphaned_tasks(self) -> Dict[str, Any]:
        """
        Query the database for unassigned and pending tasks.
        
        Identifies high-risk tasks where:
        - owner is "Unassigned" (no one has taken responsibility)
        - status is 'pending' and owner is "Unassigned"
        
        Returns:
            Dictionary containing:
                - unassigned_tasks: List of tasks with owner="Unassigned"
                - pending_unassigned_tasks: List of pending tasks without an owner
                - total_alerts: Total number of critical alerts generated
        """
        if self.db_session is None:
            self.db_session = SessionLocal()

        try:
            # Query for unassigned tasks (owner is "Unassigned")
            unassigned_tasks = (
                self.db_session.query(Task).filter(Task.owner == "Unassigned").all()
            )

            # Query for pending tasks that are unassigned (highest priority)
            pending_unassigned_tasks = (
                self.db_session.query(Task)
                .filter(Task.status == "pending", Task.owner == "Unassigned")
                .all()
            )

            # Generate alerts for high-risk unassigned pending tasks
            alert_count = 0

            for task in pending_unassigned_tasks:
                self._generate_alert(
                    task_id=str(task.id),
                    task_description=task.description,
                    alert_type="CRITICAL_UNASSIGNED",
                    details=f"High-risk unassigned task detected",
                )
                alert_count += 1

            # Log info for assigned pending tasks (no alert)
            assigned_pending_tasks = (
                self.db_session.query(Task)
                .filter(Task.status == "pending", Task.owner != "Unassigned")
                .all()
            )
            for task in assigned_pending_tasks:
                logger.info(
                    f"Watchdog: Task '{task.description}' is pending but assigned to {task.owner}."
                )

            return {
                "unassigned_tasks": unassigned_tasks,
                "pending_unassigned_tasks": pending_unassigned_tasks,
                "total_alerts": alert_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error during unassigned task audit: {e}")
            return {
                "unassigned_tasks": [],
                "pending_unassigned_tasks": [],
                "total_alerts": 0,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _generate_alert(
        self, task_id: str, task_description: str, alert_type: str, details: str
    ):
        """
        Generate and log a watchdog alert.
        
        This is a mock implementation. In production, this would:
        - Send alerts to external services (Slack, email, etc.)
        - Create incidents in ticketing systems
        - Trigger escalation workflows
        
        Args:
            task_id: UUID of the task
            task_description: Description of the task
            alert_type: Type of alert (UNASSIGNED, PENDING, OVERDUE, etc.)
            details: Additional details about the alert
        """
        alert_message = (
            f"WATCHDOG ALERT: Action item [{task_description}] is currently {details}! "
            f"(Task ID: {task_id}, Type: {alert_type})"
        )

        logger.warning(alert_message)

        # Mock alert implementations - in production, uncomment and implement these
        # self._send_slack_notification(alert_message)
        # self._send_email_notification(alert_message)
        # self._create_incident_ticket(task_id, alert_type, details)

    def generate_audit_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive audit report of all tasks.
        
        Returns:
            Dictionary containing task statistics and health metrics
        """
        if self.db_session is None:
            self.db_session = SessionLocal()

        try:
            total_tasks = self.db_session.query(Task).count()
            assigned_tasks = (
                self.db_session.query(Task).filter(Task.owner != "Unassigned").count()
            )
            unassigned_tasks = (
                self.db_session.query(Task).filter(Task.owner == "Unassigned").count()
            )

            status_counts = {}
            for task in self.db_session.query(Task).all():
                status_counts[task.status] = status_counts.get(task.status, 0) + 1

            return {
                "total_tasks": total_tasks,
                "assigned_tasks": assigned_tasks,
                "unassigned_tasks": unassigned_tasks,
                "assignment_rate": (
                    (assigned_tasks / total_tasks * 100) if total_tasks > 0 else 0
                ),
                "status_distribution": status_counts,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating audit report: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


def audit_orphaned_tasks() -> Dict[str, Any]:
    """
    Standalone function to audit orphaned tasks.
    
    This function is designed to be called as a FastAPI BackgroundTask.
    
    Returns:
        Dictionary containing audit results
    """
    with WatchdogAgent() as watchdog:
        return watchdog.audit_orphaned_tasks()


def get_audit_report() -> Dict[str, Any]:
    """
    Standalone function to generate an audit report.
    
    Returns:
        Dictionary containing audit report statistics
    """
    with WatchdogAgent() as watchdog:
        return watchdog.generate_audit_report()
