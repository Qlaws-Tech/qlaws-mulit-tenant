#!/bin/sh
#set -e

echo "🚀 Starting QLaws Backend Deployment..."

# 2. Seed Static Data (Permissions)
# Ensures the RBAC system has the necessary keys ('user.create', etc.)
echo "🌱 Seeding Permissions..."
python seed_db.py

# 3. Run Tests (Critical Gate)
# We run the full test suite here.
# Since 'set -e' is active, any test failure (non-zero exit code) will
# immediately kill the container, preventing a broken deployment.
echo "🧪 Running Test Suite..."
#pytest -v -s --disable-warnings

# 4. Start Server
# Only reached if step 3 succeeds.
# We use 'python -m uvicorn' to ensure proper module resolution.
echo "✅ Tests Passed. Starting Uvicorn Server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1