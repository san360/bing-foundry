#!/bin/bash
# =============================================================================
# Bing Grounding MCP Server (stdio) - Local Run Script
# =============================================================================
# Usage:
#   ./run-mcp-stdio.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate venv if present
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
  source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Load environment variables from .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/.env"
  set +a
else
  echo "⚠️  .env not found at $PROJECT_ROOT/.env"
  echo "   Please create it or set AZURE_AI_PROJECT_ENDPOINT and BING_PROJECT_CONNECTION_NAME."
fi

python "$SCRIPT_DIR/mcp_server.py"
