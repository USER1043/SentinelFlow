# SentinelFlow

A multi-agent system for the Gen AI Academy hackathon that transforms meeting transcripts into executed outcomes using LangChain, Vertex AI, and AlloyDB.

## Architecture

### Multi-Agent Components

1. **Analyst Agent** (`agents/analyst.py`)
   - Extracts structured action items from meeting transcripts
   - Uses LangChain with Vertex AI (Gemini 1.5 Pro)
   - Generates 768-dimensional vector embeddings for semantic search
   - Outputs: `ExtractedTask` objects with description, owner, deadline, and embeddings

2. **Watchdog Agent** (`agents/watchdog.py`)
   - Proactively audits the database for orphaned tasks
   - Identifies tasks with null owners or pending status
   - Generates alert logs for immediate attention
   - Provides audit reports on task health metrics

3. **FastAPI Orchestrator** (`main.py`)
   - REST API for meeting transcript ingestion
   - Coordinates Analyst agent execution
   - Manages task persistence in AlloyDB
   - Schedules background Watchdog audits

### Database Layer (`DB/database.py`)

- **AlloyDB Connection**: Uses `google-cloud-alloydb-connector` for secure, IAM-based connections
- **Task Model**: SQLAlchemy ORM with pgvector support
  - `id`: UUID primary key
  - `description`: Task text
  - `owner`: Optional assignee
  - `deadline`: Optional ISO datetime
  - `status`: Current state (pending, assigned, completed)
  - `embedding`: 768-dimensional vector (text-embedding-004)
  - `created_at`, `updated_at`: Timestamps

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Google Cloud project with AlloyDB instance
- Service account with AlloyDB connection permissions (for ADC)

### Authentication via Application Default Credentials

SentinelFlow uses **Application Default Credentials (ADC)** for authentication:

**Local Development:**
```bash
gcloud auth application-default login
```

**Cloud Run / Production:**
- Automatically uses the attached service account

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# AlloyDB Configuration (use format: project_id:region:instance)
INSTANCE_CONNECTION_NAME=my-project:us-central1:my-instance
PROJECT_ID=my-project
DB_USER=postgres
DB_PASS=your_secure_password
DB_NAME=sentinelflow

# Optional Settings
PORT=8080
SQL_ECHO=false

# Note: GOOGLE_APPLICATION_CREDENTIALS is not needed!
# Authentication uses Application Default Credentials (ADC)
```

### Installation

```bash
# Authenticate via ADC (local development)
gcloud auth application-default login

# Install dependencies with uv
uv sync

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

## Running the Application

```bash
# Development server (uses ADC automatically)
python main.py

# Production with Uvicorn
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
```

The API will be available at `http://localhost:8080`

## API Endpoints

### 1. **Health Check**
```http
GET /
```
Returns system status and timestamp.

### 2. **Process Meeting** (Primary Endpoint)
```http
POST /process-meeting
Content-Type: application/json

{
  "transcript": "In today's meeting, John will handle the Q4 budget review by next Friday. Sara needs to prepare the marketing materials.",
  "meeting_title": "Q4 Planning Sync"
}
```

**Response:**
```json
{
  "message": "Meeting successfully processed",
  "tasks_found": 2,
  "tasks": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "description": "Handle Q4 budget review",
      "owner": "John",
      "deadline": "2026-04-15T00:00:00",
      "status": "pending",
      "created_at": "2026-04-08T10:30:00"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "description": "Prepare marketing materials",
      "owner": "Sara",
      "deadline": null,
      "status": "pending",
      "created_at": "2026-04-08T10:30:00"
    }
  ],
  "timestamp": "2026-04-08T10:30:00"
}
```

### 3. **Get Audit Report**
```http
GET /audit-report
```

Returns comprehensive task health metrics including assignment rates and status distribution.

### 4. **List Tasks**
```http
GET /tasks?status=pending&owner=John&limit=50
```

Filter and retrieve tasks by status, owner, or limit.

### 5. **Update Task**
```http
PUT /tasks/{task_id}?owner=Jane&status=completed
```

Update task owner or status.

## Workflow Example

1. **Meeting Ingestion**
   ```python
   # POST /process-meeting with transcript
   ```

2. **Analyst Processing**
   - Gemini 1.5 Pro extracts action items
   - Embeddings generated via text-embedding-004
   - Tasks structured as `ExtractedTask` objects

3. **Database Persistence**
   - Tasks saved to AlloyDB with 768-dim embeddings
   - Status set to "pending" by default

4. **Watchdog Auditing** (Background Task)
   - Scans for orphaned tasks (owner=null)
   - Scans for pending tasks
   - Logs alerts: `WATCHDOG ALERT: Action item [X] is currently unassigned!`

## Technical Implementation Details

### Task Extraction with LangChain

```python
from agents.analyst import extract_tasks_from_transcript

transcript = "..."
tasks = extract_tasks_from_transcript(transcript)
# Returns: List[ExtractedTask] with embeddings
```

### Watchdog Audit

```python
from agents.watchdog import audit_orphaned_tasks, get_audit_report

# Trigger audit
results = audit_orphaned_tasks()

# Get audit metrics
report = get_audit_report()
```

### Database Operations

```python
from DB.database import SessionLocal, Task

db = SessionLocal()
task = db.query(Task).filter(Task.status == "pending").first()
task.owner = "Jane"
db.commit()
db.close()
```

## Error Handling

All endpoints include comprehensive error handling:

- **400**: Invalid request (e.g., short transcript)
- **404**: Resource not found (e.g., task ID doesn't exist)
- **500**: Server errors with descriptive messages

## Logging

The application logs all important events:

- Startup/shutdown
- Meeting processing
- Task extraction counts
- Database operations
- Watchdog alerts

Enable detailed logging by setting `SQL_ECHO=true` in `.env`.

## Performance Considerations

- **Vector Embeddings**: Generated asynchronously for scalability
- **Background Tasks**: Watchdog audits run as non-blocking background tasks
- **Database Indexing**: Consider indexing `status` and `owner` columns for frequent queries
- **Connection Pooling**: AlloyDB connector handles connection pooling automatically

## Production Deployment

1. Set up proper CORS if exposing to frontend
2. Implement authentication/authorization
3. Use production-grade database with replicas
4. Enable SQL query logging and monitoring
5. Set up external alerting (Slack, email, PagerDuty)
6. Configure rate limiting for API endpoints
7. Use horizontal scaling with multiple workers

## Future Enhancements

- Semantic search using task embeddings
- Real-time Slack/email notifications from Watchdog
- Task status lifecycle management
- Integration with calendar systems for deadline management
- Advanced filtering via vector similarity
- Audit trail and compliance reporting

## Support

For issues or questions, refer to the LangChain and Vertex AI documentation:
- [LangChain Documentation](https://python.langchain.com/)
- [Vertex AI Python SDK](https://cloud.google.com/python/docs/reference/aiplatform/latest)
- [AlloyDB Documentation](https://cloud.google.com/alloydb/docs)

## License

MIT License - See LICENSE file for details
