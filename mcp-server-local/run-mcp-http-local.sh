#!/bin/bash
# =============================================================================
# Bing Grounding MCP Server (HTTP) - Local Run Script (no Docker)
# =============================================================================
# Usage:
#   ./run-mcp-http-local.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Ensure PATH has common locations for az
export PATH="$PATH:/usr/local/bin:/usr/bin:/bin"

echo "👤 Running as: $(whoami)"
echo "🔎 az path: $(command -v az || echo 'not found')"

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

# Validate az availability
if ! command -v az >/dev/null 2>&1; then
  echo "❌ Azure CLI not found on PATH. Install Azure CLI or use service principal env vars."
  exit 1
fi

# Optional: show current account (if logged in)
az account show >/dev/null 2>&1 || echo "⚠️  az login required"

python "$SCRIPT_DIR/mcp_server_http.py"
