#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${APP_PORT:-8000}" \
  --reload \
  --reload-exclude "data/vector_store/*" \
  --reload-exclude "data/docs/*" \
  --reload-exclude "test_docs/*"
