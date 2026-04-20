# Use the Python version we stabilized (3.13)
FROM python:3.13-slim

# 1. Install uv for faster, reliable dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 2. Install system dependencies for AlloyDB/Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Use your lockfile to ensure identical dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# 4. Copy application code
COPY . .

# 5. Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# 6. Final start command
# We use 'uv run' to ensure the virtualenv is active
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]