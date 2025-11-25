#!/usr/bin/env bash

# Script to run tests and check coverage

set -e

echo "Running tests with coverage..."

# Check if we're in a poetry environment
if command -v poetry &> /dev/null; then
    echo "Using Poetry..."
    poetry run pytest -v --cov=bot --cov-branch --cov-report=term-missing --cov-report=html
elif [ -f ".venv/bin/pytest" ]; then
    echo "Using .venv..."
    .venv/bin/pytest -v --cov=bot --cov-branch --cov-report=term-missing --cov-report=html
else
    echo "Using system Python..."
    python -m pytest -v --cov=bot --cov-branch --cov-report=term-missing --cov-report=html
fi

echo ""
echo "Coverage report generated in htmlcov/index.html"