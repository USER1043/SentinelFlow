# SentinelFlow - AlloyDB Setup Guide

This guide helps you configure SentinelFlow to connect to your existing AlloyDB instance in Google Cloud.

## 📋 Prerequisites

- ✅ AlloyDB instance already deployed in Google Cloud
- ✅ Google Cloud service account with AlloyDB permissions (implicit via Application Default Credentials)
- ✅ Database credentials (username, password)
- ✅ Python 3.10 or higher
- ✅ `uv` or `pip` package manager
- ✅ `gcloud` CLI installed and authenticated

## 🔍 Finding Your AlloyDB Connection Details

### 1. Get Your AlloyDB Instance Information

```bash
# In Google Cloud Console, go to AlloyDB → Select your cluster
# You'll see the instance details like:
# - Project ID: my-project
# - Region: us-central1
# - Cluster: my-cluster
# - Instance: my-instance
```

### 2. Your Connection Format

SentinelFlow uses the format: **`project_id:region:instance`**

Example:
```
my-project:us-central1:my-instance
```

## ⚙️ Configuration Steps

### Step 1: Authenticate with Google Cloud (ADC)

SentinelFlow uses **Application Default Credentials (ADC)**, which means you don't need to manage service account keys manually.

First, authenticate your terminal:

```bash
# Login with your Google Cloud account
gcloud auth application-default login

# This creates ADC credentials at ~/.config/gcloud/application_default_credentials.json
# SentinelFlow will automatically use these credentials
```

### Step 2: Copy Environment Template

```bash
cp .env.example .env
```

### Step 3: Fill in Your AlloyDB Credentials

Edit `.env` and fill in your values:

```bash
# Your AlloyDB instance connection string
INSTANCE_CONNECTION_NAME=my-project:us-central1:my-instance

# Your Google Cloud Project ID
PROJECT_ID=my-project

# Database credentials
DB_USER=postgres
DB_PASS=your_database_password
DB_NAME=sentinelflow

# Optional: API port (default 8080)
PORT=8080

# Optional: Enable SQL logging (true/false)
SQL_ECHO=false

# Note: Authentication uses Application Default Credentials (ADC)
# Set via: gcloud auth application-default login
```

### Step 4: Prepare the Database

#### 4a. Enable pgvector Extension

Connect to your AlloyDB instance and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

If you're using `cloud-sql-proxy`:

```bash
# Terminal 1: Start the proxy
cloud-sql-proxy projects/my-project/locations/us-central1/clusters/my-cluster/instances/my-instance --port 5432

# Terminal 2: Connect and enable pgvector
psql -h localhost -U postgres -d sentinelflow -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 4b: Create Database (if needed)

```bash
cloud-sql-proxy projects/my-project/locations/us-central1/clusters/my-cluster/instances/my-instance --port 5432 &
createdb -h localhost -U postgres sentinelflow
```

### Step 5: Install Dependencies

```bash
# With uv (recommended)
uv venv
source .venv/bin/activate
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 6: Verify Configuration

```bash
# Run the verification script
python verify_config.py
```

You should see:
```
✓ INSTANCE_CONNECTION_NAME
✓ PROJECT_ID
✓ DB_USER
✓ DB_PASS
✓ DB_NAME
```

## 🚀 Start SentinelFlow

```bash
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8080
```

## 🧪 Test Your Setup

### 1. Health Check

```bash
curl http://localhost:8080/
```

Response:
```json
{
  "status": "SentinelFlow is Active",
  "timestamp": "2026-04-08T..."
}
```

### 2. Process a Meeting

```bash
curl -X POST http://localhost:8080/process-meeting \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "John will handle the Q4 budget review by Friday. Sarah needs to prepare the marketing materials.",
    "meeting_title": "Q4 Planning"
  }'
```

### 3. Check Audit Report

```bash
curl http://localhost:8080/audit-report
```

## 🔧 Troubleshooting

### ADC Not Configured

```bash
# Verify ADC is set up
gcloud auth application-default print-access-token

# If this fails, run:
gcloud auth application-default login
```

### Connection Refused

```bash
# Verify AlloyDB instance is running
gcloud alloydb instances describe my-instance \
  --cluster=my-cluster \
  --region=us-central1

# Check if pgvector extension is installed
# Connect with cloud-sql-proxy and run:
# \dx
```

### Authentication Error (No Permissions)

```bash
# Verify service account has correct permissions
gcloud projects get-iam-policy my-project \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:SERVICE_ACCOUNT_EMAIL"

# Required roles for the authenticated account (from gcloud auth list):
# - alloydb.client (to connect to AlloyDB)
# - aiplatform.user (to use Vertex AI)

# If you're using a service account instead of personal credentials:
gcloud auth activate-service-account --key-file=/path/to/key.json
gcloud auth application-default login
```

### Connection String Format

The application automatically converts your format to the full format:

Input: `project_id:region:instance`

Converts to: `projects/project_id/locations/region/clusters/alloydb/instances/instance`

**Note:** If your cluster name is not "alloydb", you'll need to provide the full connection string instead.

### pgvector Not Found

If you get "pgvector extension not found" error:

```bash
# Connect to your instance
cloud-sql-proxy INSTANCE_CONNECTION_NAME --port 5432 &
psql -h localhost -U postgres

# Run in PostgreSQL
CREATE EXTENSION IF NOT EXISTS vector;
```

## 📝 Example .env File

```bash
# Complete example
INSTANCE_CONNECTION_NAME=my-project:us-central1:my-instance
PROJECT_ID=my-project
DB_USER=postgres
DB_PASS=SecurePassword123!
DB_NAME=sentinelflow
PORT=8080
SQL_ECHO=false

# Note: Authentication uses Application Default Credentials (ADC)
# Ensure you've run: gcloud auth application-default login
```

## 🌐 API Documentation

Once running, access:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## 📊 Next Steps

1. **Process Meetings**
   - Send transcripts via `/process-meeting` endpoint
   - Tasks are automatically extracted and saved

2. **Monitor Tasks**
   - Check `/tasks` endpoint for task lists
   - Use `/audit-report` for task health metrics

3. **Deploy to Production**
   - See `DEPLOYMENT.md` for Cloud Run deployment
   - Use Docker: `docker build -t sentinelflow .`

## 🆘 Getting Help

- Ensure `gcloud auth application-default login` has been run
- Check `.env` file is correctly filled
- Run `python verify_config.py`
- Enable `SQL_ECHO=true` for debugging
- Check logs in terminal
- Verify service account has required IAM roles

## 📚 Additional Resources

- [AlloyDB Documentation](https://cloud.google.com/alloydb/docs)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Google Cloud AlloyDB Connector](https://github.com/GoogleCloudPlatform/alloydb-python-connector)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

**Your AlloyDB instance is now ready to use with SentinelFlow!** 🎉
