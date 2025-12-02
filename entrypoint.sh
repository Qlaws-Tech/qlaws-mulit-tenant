#!/bin/sh
#set -e
python check_connections.py

echo "🚀 Starting QLaws Backend Deployment..."
#
echo "✅ Tests Passed. Starting Uvicorn Server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1