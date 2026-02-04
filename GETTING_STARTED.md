# Getting Started - Bing Foundry Company Risk Analysis

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/Mac
# OR
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Azure AI Foundry Configuration
AZURE_AI_PROJECT_ENDPOINT="https://your-project.services.ai.azure.com"
AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4o"
BING_PROJECT_CONNECTION_NAME="your-bing-connection-name"

# Optional: MCP Server Configuration (for Scenario 2 & 3)
MCP_SERVER_URL="http://localhost:8000/mcp"
```

### 3. Run the Application

```bash
# ✅ CORRECT: Run the refactored UI
streamlit run src/ui/app.py
```

**The application will open in your browser at `http://localhost:8501`**

---

## Architecture Overview

The application has been refactored following SOLID principles:

```
src/
├── ui/
│   ├── app.py              # ✅ Main entry point (103 lines)
│   ├── components/         # Reusable UI components
│   └── pages/              # Scenario-specific pages
│       ├── scenario1.py    # Direct Agent
│       ├── scenario2.py    # MCP Agent-to-Agent
│       ├── scenario3.py    # Agent with MCP Tool
│       └── documentation.py
│
├── core/                   # Domain models & interfaces
├── infrastructure/         # Azure clients, config, tracing
├── services/              # Business logic
└── scenarios/             # Scenario implementations
```

---

## Three Scenarios

### Scenario 1: Direct Agent with Bing Tool
```
User → AI Agent (Bing Tool) → Bing API
```
- Simplest approach
- Market parameter set at tool creation
- Lowest latency

### Scenario 2: MCP Agent-to-Agent
```
User → MCP Server → Agent 2 (Bing Tool) → Bing API
```
- Market parameter passed as MCP argument
- Agent created by MCP server
- Good for multi-agent systems

### Scenario 3: Agent with MCP Tool → REST API
```
User → AI Agent (MCP Tool) → MCP Server → Bing REST API
```
- Single MCP tool wrapping REST API
- Agent created by Streamlit
- Full control over API calls

---

## Running MCP Server (for Scenarios 2 & 3)

### Local HTTP Server

```bash
cd mcp-server-local
./run-mcp-http-local.sh
```

The MCP server will start on `http://localhost:8000`

### Using devtunnel (for Scenario 3)

Scenario 3 requires a publicly accessible MCP server:

```bash
# Install devtunnel
# See: https://learn.microsoft.com/azure/developer/dev-tunnels/get-started

# Create tunnel
devtunnel create --allow-anonymous

# Start tunnel
devtunnel host <tunnel-id>

# Use the URL in Scenario 3: https://<tunnel-id>.devtunnels.ms/mcp
```

---

## Troubleshooting

### Issue: `streamlit: command not found`
**Solution:** Make sure you activated the virtual environment and installed dependencies

### Issue: Missing environment variables
**Solution:** Create `.env` file with required variables (see step 2)

### Issue: MCP Server connection failed (Scenario 2/3)
**Solution:** 
- Check MCP server is running: `./run-mcp-http-local.sh`
- Verify URL in `.env` or UI matches server address
- For Scenario 3, use devtunnel for public access

### Issue: Azure authentication failed
**Solution:** Run `az login` to authenticate with Azure CLI

---

## Key Features

✅ **Clean Logs:** No verbose HTTP headers  
✅ **Agent Visibility:** See agent ID, name, version  
✅ **Single MCP Tool:** Scenario 3 uses one tool only  
✅ **SOLID Architecture:** All files < 200 lines  
✅ **Three Scenarios:** Compare different approaches  

---

## Documentation

- [README.md](README.md) - Full project documentation
- [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md) - Recent improvements
- [FIXES_PLAN.md](FIXES_PLAN.md) - Analysis and fixes applied
- [docs/devtunnel-quick-start.md](docs/devtunnel-quick-start.md) - devtunnel setup

---

## Need Help?

- Check logs in terminal for error messages
- Verify all environment variables are set
- Ensure Azure resources are properly configured
- Review documentation files listed above
