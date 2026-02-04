# devtunnel Setup Guide for Bing Foundry MCP Server

## What is devtunnel?

**devtunnel** is Microsoft's official tunneling tool that exposes your local development server to the internet. It's essential for testing Azure AI Foundry agents with local MCP servers because agents run in Azure and cannot reach `localhost`.

## Why You Need devtunnel for This Project

This project demonstrates three scenarios of integrating Bing Grounding with AI agents:

| Scenario | Architecture | Needs devtunnel? |
|----------|-------------|------------------|
| **Scenario 1** | User → Agent (Bing Tool) | ❌ No - Agent uses Bing directly |
| **Scenario 2** | User → MCP Server → Agent (Bing Tool) | ✅ Yes - If running MCP server locally |
| **Scenario 3** | User → Agent (MCP Tool) → MCP Server → REST API | ✅ Yes - If running MCP server locally |

**Scenarios 2 & 3 require publicly accessible MCP server** because:
- Scenario 2: Your Streamlit app needs to reach the MCP server
- Scenario 3: Azure AI Foundry agent (runs in cloud) needs to reach MCP server

## Quick Setup (5 minutes)

### Step 1: One-Time Setup

```bash
# 1. Login to Azure
devtunnel user login

# 2. Create a persistent tunnel
devtunnel create --allow-anonymous

# 3. Note your tunnel ID (e.g., abc123xyz or puzzled-book-8tv0m2x)

# 4. Add port 8000 to the tunnel
devtunnel port create <tunnel-id> -p 8000
```

**Save your tunnel ID!** You'll reuse it every day.

### Step 2: Daily Usage

Open two terminals:

**Terminal 1 - Start MCP Server:**
```bash
cd /mnt/c/dev/bing-foundry/mcp-server-local
./run-mcp-http-local.sh
```

**Terminal 2 - Start Tunnel:**
```bash
# Use your tunnel ID from step 1
devtunnel host <your-tunnel-id>

# Or if you forgot your ID
devtunnel list
devtunnel host <tunnel-id-from-list>
```

**Output will show two URLs:**
```
Hosting port: 8000
Connect via browser: https://abc123xyz.devtunnels.ms      ← Use this one!
Inspect network traffic: https://abc123xyz-inspect.euw.devtunnels.ms  ← Do NOT use
```

⚠️ **Important:** Always use the **main URL** (without `-inspect`), not the inspect URL!

### Step 3: Test Your Setup

```bash
# Replace with YOUR tunnel URL (without -inspect)
curl https://abc123xyz.devtunnels.ms/health
```

Should return: `{"status": "healthy", "server": "bing-grounding-mcp"}`

## Using devtunnel with Each Scenario

### Scenario 1: Direct Agent with Bing Tool

**No devtunnel needed** - Agent directly uses Bing Grounding API.

**Code Location:** [`src/app.py`](../src/app.py) - `render_direct_agent_scenario()`

**How it works:**
```python
from azure.ai.projects.models import BingGroundingAgentTool
from azure.ai.projects import AIProjectClient

# Create Bing tool with market parameter
bing_tool = BingGroundingAgentTool(
    bing_grounding=BingGroundingSearchToolParameters(
        search_configurations=[
            BingGroundingSearchConfiguration(
                project_connection_id=bing_connection_id,
                market="de-DE",  # Explicit market
                count=10
            )
        ]
    )
)

# Create agent with the tool
agent = project_client.agents.create_agent(
    model="gpt-4o",
    instructions="You are a risk analyst...",
    tools=[bing_tool.definitions[0]]
)

# Run the agent
thread = project_client.agents.create_thread()
message = project_client.agents.create_message(
    thread_id=thread.id,
    role="user",
    content="Analyze risks for Tesla"
)
run = project_client.agents.create_and_process_run(
    thread_id=thread.id,
    agent_id=agent.id
)
```

**No network setup required** - Everything runs in Azure AI Foundry.

---

### Scenario 2: MCP Server → Agent (Bing Tool)

**Requires devtunnel** if MCP server is running locally.

**Code Location:** 
- Streamlit UI: [`src/app.py`](../src/app.py) - `render_mcp_agent_scenario()`
- MCP Server: [`mcp-server-local/mcp_server.py`](../mcp-server-local/mcp_server.py)

**Architecture:**
```
Streamlit App → MCP Server (via devtunnel) → Creates Agent → Uses Bing Tool
```

**How to configure:**

1. **Start MCP server and devtunnel** (see Step 2 above)

2. **In Streamlit UI (Scenario 2 tab):**
   - MCP Server URL: `https://abc123xyz.devtunnels.ms/mcp`
   - Click "Test MCP Connection"
   - Select market from dropdown
   - Enter company name
   - Click "Run via MCP (Agent → Agent)"

3. **What happens under the hood:**

```python
# Streamlit sends JSON-RPC request to MCP server
mcp_request = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "analyze_company_risk",
        "arguments": {
            "company_name": "Tesla",
            "market": "de-DE",
            "risk_category": "all"
        }
    }
}

# MCP server (mcp_server.py) receives request
@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "analyze_company_risk":
        # Extract market from arguments
        market = arguments.get("market", "en-US")
        
        # Create Bing tool with that market
        bing_tool = BingGroundingAgentTool(
            bing_grounding=BingGroundingSearchToolParameters(
                search_configurations=[
                    BingGroundingSearchConfiguration(
                        market=market,  # Dynamic from request
                        count=10
                    )
                ]
            )
        )
        
        # Create agent and run analysis
        agent = project_client.agents.create_agent(
            model="gpt-4o",
            tools=[bing_tool.definitions[0]]
        )
        # ... run agent and return results
```

**Key Point:** Market parameter flows: User Selection → MCP Request → Tool Configuration

---

### Scenario 3: Agent (MCP Tool) → MCP Server → REST API

**Requires devtunnel** if MCP server is running locally.

**Code Location:**
- Streamlit UI: [`src/app.py`](../src/app.py) - `render_rest_api_scenario()`
- MCP Server: [`mcp-server-local/mcp_server_http.py`](../mcp-server-local/mcp_server_http.py)

**Architecture:**
```
User → Agent (in Azure, has MCP Tool) → MCP Server (via devtunnel) → Bing REST API
```

**Why devtunnel is critical here:**
- The **agent is created in Azure AI Foundry** (not local)
- Azure agent needs to reach your local MCP server
- `localhost:8000` won't work - needs public URL

**How to configure:**

1. **Start MCP server and devtunnel** (see Step 2 above)

2. **In Streamlit UI (Scenario 3 tab):**
   - MCP Server URL: `https://abc123xyz.devtunnels.ms/mcp`
   - Click "Test MCP Connection"
   - Select market and enter company
   - Click "Run Agent with MCP Tool"

3. **What happens under the hood:**

```python
from azure.ai.projects.models import MCPTool

# Create agent WITH MCP tool attached
agent = project_client.agents.create_agent(
    model="gpt-4o",
    instructions="Use the MCP tools to search for company information...",
    tools=[
        MCPTool(
            server_label="bing_rest_api_mcp",
            server_url="https://abc123xyz.devtunnels.ms/mcp",  # Must be public!
            require_approval="never",
            allowed_tools=[
                "bing_search_rest_api",
                "analyze_company_risk_rest_api"
            ]
        )
    ]
)

# Agent runs in Azure and calls MCP server over internet
thread = project_client.agents.create_thread()
message = project_client.agents.create_message(
    thread_id=thread.id,
    role="user",
    content=f"Analyze risks for Tesla in market de-DE"
)

# Agent decides to call MCP tool
# Azure agent → (HTTPS) → devtunnel → localhost:8000 → MCP server
run = project_client.agents.create_and_process_run(
    thread_id=thread.id,
    agent_id=agent.id
)
```

**MCP Server handles the call** (in `mcp_server_http.py`):

```python
@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "bing_search_rest_api":
        query = arguments["query"]
        market = arguments.get("market", "en-US")
        
        # Call Bing REST API directly (not via agent)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROJECT_ENDPOINT}/openai/v1/responses",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "tools": [{
                        "type": "bing_grounding",
                        "bing_grounding": {
                            "connection_id": bing_connection_id,
                            "market": market  # Pass market to REST API
                        }
                    }],
                    "messages": [{
                        "role": "user",
                        "content": query
                    }]
                }
            )
            
            return response.json()
```

**Key Difference from Scenario 2:**
- Scenario 2: MCP server creates an agent internally
- Scenario 3: Agent exists in Azure with MCP tool, MCP server just calls REST API

---

## Common Commands Reference

```bash
# Login (one-time)
devtunnel user login

# Create new tunnel
devtunnel create --allow-anonymous

# Add port to tunnel
devtunnel port create <tunnel-id> -p 8000

# List your tunnels
devtunnel list

# Host/start tunnel
devtunnel host <tunnel-id>

# Delete tunnel
devtunnel delete <tunnel-id>

# Get help
devtunnel --help
```

## Troubleshooting

### "devtunnel: command not found"

Install it:
```bash
# Windows
winget install Microsoft.devtunnel

# Or download from:
# https://aka.ms/devtunnels/download
```

### "User not authenticated"

Run:
```bash
devtunnel user login
```

### HTTP 401 Error in UI

**Problem:** You're using the **inspect URL** instead of the main URL.

**Fix:** Remove `-inspect` from the URL:
- ❌ Wrong: `https://abc123-8000-inspect.euw.devtunnels.ms/mcp`
- ✅ Correct: `https://abc123-8000.euw.devtunnels.ms/mcp`

The inspect URL is for monitoring only, not for actual connections.

### Connection Refused / Timeout

1. **Check MCP server is running:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy"}
   ```

2. **Check tunnel is active:**
   ```bash
   devtunnel list
   # Should show "Ready" status
   ```

3. **Test tunnel endpoint:**
   ```bash
   curl https://your-tunnel-id.devtunnels.ms/health
   # Should return same as localhost
   ```

4. **Check port configuration:**
   ```bash
   devtunnel port list <tunnel-id>
   # Should show port 8000
   ```

### Tunnel Not Forwarding

If port 8000 wasn't added during creation:

```bash
# Add port to existing tunnel
devtunnel port create <tunnel-id> -p 8000

# Then host it
devtunnel host <tunnel-id>
```

### Port Already in Use

If port 8000 is already in use:
```bash
# Stop existing MCP server
pkill -f mcp_server_http

# Restart
cd /mnt/c/dev/bing-foundry/mcp-server-local
./run-mcp-http-local.sh
```

## Tips & Best Practices

✅ **Save your tunnel ID** - Write it down for daily reuse  
✅ **Keep both terminals open** - MCP server AND devtunnel must run  
✅ **Use main URL, not inspect** - Inspect URL is for monitoring only  
✅ **Test connection first** - Use "Test MCP Connection" button before analysis  
✅ **Same URL across sessions** - Your devtunnel URL is persistent  

## Security for Production

For production deployments, don't use `--allow-anonymous`:

```bash
# Create authenticated tunnel
devtunnel create --allow-user

# Add port
devtunnel port create <tunnel-id> -p 8000

# Grant access to specific users (optional)
devtunnel access create <tunnel-id> --anonymous false
```

For production, consider:
- **Azure Functions** - Deploy MCP server as serverless function
- **Azure Container Apps** - Deploy MCP server as container
- **Azure Web Apps** - Deploy as web application

See deployment guides:
- Functions: [`mcp-server/README.md`](../mcp-server/README.md)
- Container Apps: [`mcp-server-local/Dockerfile`](../mcp-server-local/Dockerfile)

## Comparison: Local Development vs Production

| Feature | devtunnel (Local) | Azure Functions | Azure Container Apps |
|---------|-------------------|-----------------|----------------------|
| **Cost** | Free | ~$5/month | ~$15-30/month |
| **Setup Time** | 5 minutes | 15 minutes | 20 minutes |
| **Persistence** | Requires laptop on | Always available | Always available |
| **Performance** | Depends on internet | Fast | Fast |
| **Best For** | Development/Testing | Production - low traffic | Production - any traffic |

## Next Steps

Once devtunnel is working:

1. ✅ **Test all three scenarios:**
   - Scenario 1: Direct agent (no devtunnel needed)
   - Scenario 2: MCP → Agent pattern
   - Scenario 3: Agent → MCP pattern

2. ✅ **Compare results** across different markets (en-US, de-DE, etc.)

3. ✅ **Try different companies** and risk categories

4. 🚀 **Deploy to production** when ready (see deployment guides)

## Related Documentation

- **Main README:** [`README.md`](../README.md) - Project overview
- **MCP Server (Stdio):** [`mcp-server-local/mcp_server.py`](../mcp-server-local/mcp_server.py) - Scenario 2
- **MCP Server (HTTP):** [`mcp-server-local/mcp_server_http.py`](../mcp-server-local/mcp_server_http.py) - Scenario 3
- **Azure Functions Deployment:** [`mcp-server/README.md`](../mcp-server/README.md)
- **Bing Grounding Market Tracing:** [`docs/bing-grounding-market-tracing.md`](bing-grounding-market-tracing.md)
