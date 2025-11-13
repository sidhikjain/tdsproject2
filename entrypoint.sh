#!/bin/bash
set -e

echo "Installing Playwright browsers..."
playwright install chromium
playwright install-deps chromium

echo "Starting FastAPI application..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
