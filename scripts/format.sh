#!/bin/bash
set -e

echo "🔧 Running code formatting..."

echo "📦 Running Black..."
uv run black backend/ main.py

echo "📝 Running isort..."
uv run isort backend/ main.py

echo "✅ Code formatting complete!"