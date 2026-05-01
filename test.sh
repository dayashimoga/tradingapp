#!/bin/bash
# test.sh - Run tests with coverage inside Docker securely

echo "Running tests in ephemeral Docker container..."
docker run --rm -v "$(pwd):/app" -w /app python:3.12-slim bash -c "pip install -e .[dashboard,alerts] pytest pytest-asyncio pytest-cov aiosqlite && pytest --cov=src --cov-report=term-missing"

