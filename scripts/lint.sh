#!/bin/bash
set -e

echo "🔍 Running code quality checks..."

echo "📋 Running Flake8..."
uv run flake8 backend/ main.py --statistics

echo "🎯 Running Black (check only)..."
uv run black --check backend/ main.py

echo "📑 Running isort (check only)..."
uv run isort --check-only backend/ main.py

echo "✅ Code quality checks complete!"