#!/bin/bash
set -e

echo "🧪 Running tests..."

echo "🔬 Running pytest..."
cd backend
uv run pytest tests/ -v --tb=short

echo "✅ Tests complete!"