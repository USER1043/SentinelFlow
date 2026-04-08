"""
Example usage of SentinelFlow API and agents.

This script demonstrates:
1. Direct agent usage (without API)
2. Meeting transcript processing
3. Task extraction and embedding
4. Watchdog auditing

Run with: python examples/demo.py
"""

import os
from datetime import datetime
from agents.analyst import extract_tasks_from_transcript, get_analyst
from agents.watchdog import WatchdogAgent, get_audit_report
from DB.database import SessionLocal, Task, get_engine
import uuid

# ============================================================================
# Example 1: Extract Tasks from a Meeting Transcript
# ============================================================================


def example_extract_tasks():
    """Demonstrate task extraction from a meeting transcript."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Extract Tasks from Meeting Transcript")
    print("=" * 70)

    transcript = """
    During today's product planning meeting, we discussed the following:
    
    1. Sarah will prepare the market research report by March 31st.
    2. The engineering team needs to complete the API documentation.
    3. Mike should schedule follow-ups with key stakeholders by end of week.
    4. We need to finalize the pricing strategy - currently unassigned.
    5. Jennifer will lead the user testing phase starting next Monday.
    """

    print("\nTranscript:")
    print(transcript)

    print("\nExtracting tasks...")
    # Note: This requires Vertex AI credentials
    try:
        tasks = extract_tasks_from_transcript(transcript)

        print(f"\n✓ Extracted {len(tasks)} tasks:\n")
        for i, task in enumerate(tasks, 1):
            print(f"  {i}. {task.description}")
            if task.owner:
                print(f"     Owner: {task.owner}")
            if task.deadline:
                print(f"     Deadline: {task.deadline}")
            if hasattr(task, "embedding") and task.embedding:
                print(f"     Embedding: {len(task.embedding)}-dimensional vector")
            print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print(
            "  Note: Ensure GOOGLE_APPLICATION_CREDENTIALS is set for Vertex AI access"
        )


# ============================================================================
# Example 2: Save Tasks to Database
# ============================================================================


def example_save_tasks():
    """Demonstrate saving tasks to the database."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Save Tasks to Database")
    print("=" * 70)

    db = SessionLocal()

    try:
        # Create sample tasks
        sample_tasks = [
            {
                "description": "Finalize Q2 budget proposal",
                "owner": "Sarah",
                "status": "pending",
            },
            {
                "description": "Conduct user interviews",
                "owner": None,  # Orphaned task
                "status": "pending",
            },
            {
                "description": "Update documentation",
                "owner": "Mike",
                "status": "in_progress",
            },
        ]

        print(f"\nSaving {len(sample_tasks)} tasks to database...\n")

        for task_data in sample_tasks:
            task = Task(
                id=str(uuid.uuid4()),
                description=task_data["description"],
                owner=task_data["owner"],
                status=task_data["status"],
            )
            db.add(task)
            print(f"  + {task.description}")
            if task.owner:
                print(f"    Owner: {task.owner}")
            else:
                print(f"    Owner: (unassigned)")
            print()

        db.commit()
        print(f"✓ All tasks saved successfully")

    except Exception as e:
        db.rollback()
        print(f"✗ Error saving tasks: {e}")
    finally:
        db.close()


# ============================================================================
# Example 3: Query Tasks from Database
# ============================================================================


def example_query_tasks():
    """Demonstrate querying tasks from the database."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Query Tasks from Database")
    print("=" * 70)

    db = SessionLocal()

    try:
        # Count total tasks
        total = db.query(Task).count()
        print(f"\nTotal tasks in database: {total}")

        # Query by status
        pending = db.query(Task).filter(Task.status == "pending").count()
        print(f"Pending tasks: {pending}")

        # Query orphaned tasks
        orphaned = db.query(Task).filter(Task.owner == None).count()
        print(f"Unassigned tasks: {orphaned}")

        # List all tasks
        print("\nAll tasks:")
        for task in db.query(Task).limit(10).all():
            print(f"  • {task.description}")
            print(f"    Status: {task.status}")
            print(f"    Owner: {task.owner or '(unassigned)'}")
            print(f"    Created: {task.created_at}")
            print()

    except Exception as e:
        print(f"✗ Error querying tasks: {e}")
    finally:
        db.close()


# ============================================================================
# Example 4: Run Watchdog Audit
# ============================================================================


def example_watchdog_audit():
    """Demonstrate the Watchdog audit functionality."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Watchdog Audit")
    print("=" * 70)

    try:
        with WatchdogAgent() as watchdog:
            print("\n🔍 Running watchdog audit...\n")
            results = watchdog.audit_orphaned_tasks()

            print(
                f"Orphaned tasks (no owner): {len(results['orphaned_tasks'])}"
            )
            for task in results["orphaned_tasks"]:
                print(f"  ⚠ {task.description}")

            print(f"\nPending tasks: {len(results['pending_tasks'])}")
            for task in results["pending_tasks"]:
                print(f"  ⏳ {task.description}")

            print(f"\nTotal alerts generated: {results['total_alerts']}")

            print("\n" + "-" * 70)
            print("Generating audit report...\n")

            report = watchdog.generate_audit_report()
            print(f"Total tasks: {report.get('total_tasks', 0)}")
            print(f"Assigned tasks: {report.get('assigned_tasks', 0)}")
            print(f"Unassigned tasks: {report.get('unassigned_tasks', 0)}")
            print(
                f"Assignment rate: {report.get('assignment_rate', 0):.1f}%"
            )

            if "status_distribution" in report:
                print("\nStatus distribution:")
                for status, count in report["status_distribution"].items():
                    print(f"  • {status}: {count}")

    except Exception as e:
        print(f"✗ Error running audit: {e}")


# ============================================================================
# Example 5: Update Task Status
# ============================================================================


def example_update_task():
    """Demonstrate updating task status."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Update Task Status")
    print("=" * 70)

    db = SessionLocal()

    try:
        # Get first unassigned task
        task = db.query(Task).filter(Task.owner == None).first()

        if task:
            print(f"\nFound unassigned task: {task.description}")
            print(f"Current status: {task.status}")

            # Update the task
            print("\nUpdating task...")
            task.owner = "John Doe"
            task.status = "in_progress"
            db.commit()

            print(f"✓ Task updated successfully!")
            print(f"  New owner: {task.owner}")
            print(f"  New status: {task.status}")
        else:
            print("\nNo unassigned tasks found in database")

    except Exception as e:
        db.rollback()
        print(f"✗ Error updating task: {e}")
    finally:
        db.close()


# ============================================================================
# Main Demo Runner
# ============================================================================


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("SentinelFlow - Agent Demonstration")
    print("=" * 70)

    print("\nNote: Some examples require database and Vertex AI setup.")
    print("Set GOOGLE_APPLICATION_CREDENTIALS and database environment variables.\n")

    # Check environment
    required_env_vars = [
        "INSTANCE_CONNECTION_NAME",
        "DB_USER",
        "DB_PASS",
        "DB_NAME",
    ]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        print(f"⚠ Missing environment variables: {', '.join(missing_vars)}")
        print("Database examples will be skipped.\n")

    try:
        # Run examples
        if not missing_vars:
            example_extract_tasks()
            example_save_tasks()
            example_query_tasks()
            example_watchdog_audit()
            example_update_task()
        else:
            print("✗ Skipping examples due to missing configuration.")
            print("Please set up environment variables and try again.")

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")

    print("\n" + "=" * 70)
    print("Demo completed")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
