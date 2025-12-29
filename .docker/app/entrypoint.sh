#!/bin/bash
set -e

# Ensure PATH includes user-installed packages
export PATH="/root/.local/bin:$PATH"
export PYTHONPATH="/root/.local/lib/python3.11/site-packages:$PYTHONPATH"

# Проверяем наличие venv в монтированном volume
if [ -f "/app/venv/bin/python" ]; then
    echo "Using Python from mounted venv: /app/venv/bin/python"
    exec /app/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
else
    echo "Using Python from Docker image with installed packages"
    # Use system Python with correct PYTHONPATH to access installed packages
    exec /usr/local/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
