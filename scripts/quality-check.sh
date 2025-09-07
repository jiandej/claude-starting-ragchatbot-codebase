#!/bin/bash
set -e

echo "🚀 Running complete quality checks..."

# Format code first
./scripts/format.sh

# Run linting
./scripts/lint.sh

# Run tests
./scripts/test.sh

echo "🎉 All quality checks passed!"