# ERSELMETZ AI CORPORATION
# Local-first Docker image — Python application only.
# Ollama runs on the Windows host; SQLite data is persisted via a bind mount.

# --------------------------------------------------------------------------- #
# Stage: runtime
# --------------------------------------------------------------------------- #
FROM python:3.14-slim

# Keeps Python output unbuffered so logs reach the terminal immediately.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source only — .venv/, .git/, and other dev artefacts are
# excluded by .dockerignore.
COPY app/ ./app/

# The projects/ directory is mounted at runtime (see compose.yaml).
# Create it here so the image has the expected path even without the mount.
RUN mkdir -p projects

# Default entry point matches `python -m app.main`.
CMD ["python", "-m", "app.main"]
