"""
Database module for SentinelFlow.

Handles AlloyDB connection using google-cloud-alloydb-connector and defines
SQLAlchemy models for task management with pgvector embeddings support.
"""

import os
from typing import Optional
from datetime import datetime
from uuid import UUID

from google.cloud.alloydbconnector import Connector, IPTypes
from sqlalchemy import create_engine, Column, String, DateTime, Text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector

# Configure the Vector type for 768-dimensional embeddings (text-embedding-004)
EMBEDDING_DIMENSION = 768

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID type that uses CHAR(32) for SQLite and UUID for PostgreSQL."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, UUID):
            return str(value)
        if dialect.name == "postgresql":
            return value
        return value.replace("-", "") if isinstance(value, str) else str(value).replace("-", "")

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return UUID(value) if isinstance(value, str) else value


class Task(Base):
    """
    Task model representing action items extracted from meeting transcripts.
    
    Attributes:
        id: Unique identifier (UUID)
        description: Text description of the task
        owner: Name of the owner/assignee; defaults to "Unassigned" if not provided
        deadline: Optional deadline (ISO format datetime)
        status: Current status (pending, assigned, completed, etc.)
        embedding: 768-dimensional vector embedding for semantic search
    """

    __tablename__ = "tasks"

    id = Column(GUID(), primary_key=True, default=lambda: str(UUID().hex))
    description = Column(Text, nullable=False)
    owner = Column(String(255), default="Unassigned", nullable=False)
    deadline = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Task(id={self.id}, description={self.description[:50]}..., owner={self.owner}, status={self.status})>"


def get_engine():
    """
    Create and return a SQLAlchemy engine configured for AlloyDB.
    
    Uses google-cloud-alloydb-connector with Application Default Credentials (ADC).
    Automatically uses credentials from:
        - gcloud auth application-default login (local development)
        - Attached service account (Cloud Run)
    
    Configuration from environment variables:
        - INSTANCE_CONNECTION_NAME: AlloyDB instance in format 'project_id:region:instance'
        - PROJECT_ID: Google Cloud project ID
        - DB_USER: Database user
        - DB_PASS: Database password
        - DB_NAME: Database name
    
    Returns:
        Engine: Configured SQLAlchemy engine
        
    Raises:
        ValueError: If required environment variables are not set
    """
    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
    project_id = os.getenv("PROJECT_ID")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_name = os.getenv("DB_NAME")

    if not all([instance_connection_name, project_id, db_user, db_pass, db_name]):
        raise ValueError(
            "Missing required environment variables: "
            "INSTANCE_CONNECTION_NAME, PROJECT_ID, DB_USER, DB_PASS, DB_NAME"
        )

    # Convert short format (project_id:region:instance) to full format
    # Full format: projects/{PROJECT_ID}/locations/{REGION}/clusters/{CLUSTER}/instances/{INSTANCE}
    if not instance_connection_name.startswith("projects/"):
        # Parse short format: project_id:region:instance
        parts = instance_connection_name.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid INSTANCE_CONNECTION_NAME format. Expected 'project_id:region:instance', got '{instance_connection_name}'"
            )
        _, region, instance = parts
        # Use a default cluster name or extract from instance if needed
        cluster_name = "alloydb"  # Default cluster name
        instance_connection_name = f"projects/{project_id}/locations/{region}/clusters/{cluster_name}/instances/{instance}"

    connector = Connector()

    def getconn():
        """Create a connection to AlloyDB using the connector."""
        return connector.connect(
            instance_connection_name,
            "pg8000",
            user=db_user,
            password=db_pass,
            db=db_name,
            ip_type=IPTypes.PUBLIC
        )

    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Enable pgvector extension on connection."""
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            dbapi_conn.commit()
        finally:
            cursor.close()

    return engine


def init_database():
    """Initialize the database by creating all tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


# Session factory
engine = init_database()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
