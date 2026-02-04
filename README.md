# Company Risk Analysis Agent - Bing Grounding PoC

This proof-of-concept application demonstrates Azure AI Foundry Agent with Bing Search grounding for comprehensive company risk analysis from an insurance perspective.

## 🎯 Purpose

The application analyzes companies for:
- General company details and background
- Involvement in litigations
- Negative news coverage (child labor, environmental issues, etc.)
- Overall risk profile assessment

## 🏗️ Five Scenarios for Bing Grounding Integration

This PoC demonstrates **five different architectures** for integrating Bing Grounding with AI Agents:

---

### Scenario 1: Direct Agent with Bing Tool

**Architecture**: User → Agent (Bing Tool Attached) → Bing API → Results

The simplest pattern where the Bing Grounding tool is directly attached to the agent at creation time.

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant App as 🖥️ Streamlit App
    participant Agent as 🤖 BingFoundry-DirectAgent
    participant Bing as 🌐 Bing Grounding API
    
    U->>App: Enter company name<br/>Select market (e.g., de-DE)
    App->>App: Create BingGroundingTool<br/>with market="de-DE"
    App->>Agent: Create/Get Agent with<br/>Bing tool attached
    Agent->>Bing: Search with grounding
    Bing-->>Agent: Grounded results + citations
    Agent-->>App: Analysis response
    App-->>U: Risk analysis with<br/>URL citations
```

**Key Characteristics:**
- Market configured at tool creation time
- Single agent with native Bing grounding
- Citations returned as URL annotations
- Best for: Simple single-market searches

---

### Scenario 2: Two-Agent Pattern via MCP Server

**Architecture**: User → Orchestrator Agent → MCP Tool → Worker Agent (with Bing) → Results

An orchestrator agent delegates search to ephemeral worker agents via MCP.

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant App as 🖥️ Streamlit App
    participant Orch as 🤖 Orchestrator Agent
    participant MCP as 🔌 MCP Server
    participant Worker as 🤖 Worker Agent
    participant Bing as 🌐 Bing API
    
    U->>App: Analyze "Tesla" in de-DE market
    App->>Orch: Risk analysis request
    Orch->>MCP: create_and_run_bing_agent<br/>(company, market="de-DE")
    MCP->>Worker: Create ephemeral agent<br/>with market-specific Bing tool
    Worker->>Bing: Grounded search
    Bing-->>Worker: Results + citations
    Worker-->>MCP: Search results
    MCP->>MCP: Delete worker agent
    MCP-->>Orch: JSON response with citations
    Orch-->>App: Final analysis
    App-->>U: Risk report with sources
```

**Key Characteristics:**
- Dynamic market configuration at runtime
- Worker agents created/deleted per request
- Two-tier agent architecture
- Best for: Dynamic market selection, isolated searches

---

### Scenario 3: Agent → MCP Tool → REST API

**Architecture**: User → Agent (MCP Tool) → MCP Server → Bing REST API → Results

Agent uses MCP tool that directly calls the Bing Grounding REST API.

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant App as 🖥️ Streamlit App
    participant Agent as 🤖 BingFoundry-MCPAgent
    participant MCP as 🔌 MCP Server
    participant REST as 🌐 Bing REST API
    
    U->>App: Search request with market
    App->>Agent: Invoke with MCP tool
    Agent->>MCP: bing_search_rest_api<br/>(query, market="ja-JP")
    MCP->>REST: POST /openai/responses<br/>with bing_grounding tool
    REST-->>MCP: JSON response with<br/>output_text + citations
    MCP-->>Agent: Formatted results
    Agent-->>App: Analysis with citations
    App-->>U: Risk analysis
```

**Key Characteristics:**
- Direct REST API call (no nested agents)
- Citations extracted from REST response
- Configurable count, freshness, setLang
- Best for: Fine-grained control over search parameters

---

### Scenario 4: Multi-Market Sequential Search

**Architecture**: User → Agent → MCP Tool (called N times) → Aggregated Results

Single agent makes multiple sequential tool calls for different markets.

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant App as 🖥️ Streamlit App
    participant Agent as 🤖 BingFoundry-MultiMarket
    participant MCP as 🔌 MCP Server
    participant Bing as 🌐 Bing REST API
    
    U->>App: Analyze across en-US, de-DE, ja-JP
    App->>Agent: Multi-market request
    
    loop For each market (sequential)
        Agent->>MCP: bing_search_rest_api<br/>(query, market=X)
        MCP->>Bing: REST API call
        Bing-->>MCP: Market-specific results
        MCP-->>Agent: JSON with citations
    end
    
    Agent->>Agent: Aggregate all<br/>market results
    Agent-->>App: Cross-market analysis
    App-->>U: Comparative report<br/>with all citations
```

**Key Characteristics:**
- Sequential execution (one market at a time)
- Single agent, multiple tool calls
- Prompt-driven market iteration
- Best for: Simple multi-market needs (2-3 markets)

---

### Scenario 5: Workflow-Based Parallel Multi-Market

**Architecture**: User → Dispatcher → Parallel Search Agents → Aggregator → Analysis Agent → Results

Structured workflow with parallel execution and dedicated analysis phase.

```mermaid
flowchart TB
    subgraph Input
        U[👤 User Request]
    end
    
    subgraph "Stage 1: Dispatch"
        D[📤 Market Dispatcher]
    end
    
    subgraph "Stage 2: Parallel Search"
        S1[🔍 en-US Search]
        S2[🔍 de-DE Search]
        S3[🔍 ja-JP Search]
    end
    
    subgraph "Stage 3: Aggregation"
        A[📊 Result Aggregator]
    end
    
    subgraph "Stage 4: Analysis"
        AN[🧠 Analysis Agent]
    end
    
    subgraph Output
        R[📋 Final Report]
    end
    
    U --> D
    D --> S1 & S2 & S3
    S1 & S2 & S3 --> A
    A --> AN
    AN --> R
    
    style S1 fill:#e1f5fe
    style S2 fill:#e1f5fe
    style S3 fill:#e1f5fe
    style A fill:#fff3e0
    style AN fill:#e8f5e9
```

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant App as 🖥️ App
    participant D as 📤 Dispatcher
    participant S as 🔍 Search Agents
    participant A as 📊 Aggregator
    participant AN as 🧠 Analyzer

    U->>App: Multi-market request<br/>(en-US, de-DE, ja-JP)
    App->>D: Stage 1: Dispatch markets
    
    par Parallel Execution
        D->>S: Search en-US
        D->>S: Search de-DE
        D->>S: Search ja-JP
    end
    
    S-->>A: Stage 3: Collect results<br/>(success/timeout/error per market)
    A->>A: Aggregate citations<br/>Handle partial failures
    A->>AN: Stage 4: Market findings
    AN->>AN: Cross-market analysis<br/>(no tools, pure synthesis)
    AN-->>App: Final report
    App-->>U: Comparative analysis<br/>with all citations
```

**Key Characteristics:**
- **3-5x faster** than sequential (parallel execution)
- Per-market timeout handling (90s default)
- Graceful degradation on failures
- Dedicated analysis agent (no tools)
- Best for: Production multi-market research

---

## 📊 Scenario Comparison

| Feature | Scenario 1 | Scenario 2 | Scenario 3 | Scenario 4 | Scenario 5 |
|---------|------------|------------|------------|------------|------------|
| **Pattern** | Direct | Two-Agent | MCP REST | Multi-Market | Workflow |
| **Markets** | Single | Single | Single | Multiple | Multiple |
| **Execution** | Sync | Sync | Sync | Sequential | **Parallel** |
| **Timeout Handling** | Basic | Basic | Basic | Limited | **Per-market** |
| **Failure Mode** | All-or-nothing | All-or-nothing | All-or-nothing | All-or-nothing | **Graceful** |
| **Complexity** | Low | Medium | Medium | Medium | High |
| **Best For** | Simple queries | Dynamic config | REST control | Few markets | Production |

---

## 🔑 Key Technical Investigation: Market Parameter

This PoC specifically investigates how the `market` parameter works with Bing Grounding:

### Where is the Market Parameter Configured?

The `market` parameter is configured **at the tool level**, specifically in the `BingGroundingSearchConfiguration` when creating the Bing grounding tool:

```python
BingGroundingAgentTool(
    bing_grounding=BingGroundingSearchToolParameters(
        search_configurations=[
            BingGroundingSearchConfiguration(
                project_connection_id=connection_id,
                market="de-CH",  # <-- HERE: Configured per search configuration
                count=10,
                freshness="Month"
            )
        ]
    )
)
```

### How to Pass Market Explicitly (User Perspective)

| Scenario | How Market is Passed | When Tool is Configured |
|----------|---------------------|------------------------|
| **Direct Agent** | User selects from dropdown → Code creates tool with that market | At tool creation, before agent runs |
| **MCP Agent** | User selects from dropdown → Market sent as MCP argument | Dynamically when MCP request arrives |

### Default Behavior (No Market Specified)

If `market` is not specified:
- Bing uses an internal mapping based on the request origin
- Results may vary based on the Azure region of deployment
- For consistent results, **always specify the market explicitly**

### Supported Market Values

Examples:
- `en-US` - United States English
- `de-CH` - Switzerland German
- `fr-CH` - Switzerland French
- `de-DE` - Germany German
- `en-GB` - United Kingdom English

See [Bing Market Codes](https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/reference/market-codes) for full list.

## 📁 Project Structure

```
bing-foundry/
├── infra/                          # Infrastructure as Code
│   ├── main.bicep                  # Main Bicep template
│   ├── main.bicepparam             # Parameters file
│   └── modules/                    # Bicep modules
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── company_risk_agent.py   # Main agent logic
│   │   └── prompts.py              # Pre-baked prompts
│   ├── app.py                      # Streamlit UI (4 tabs)
│   └── config.py                   # Configuration
├── mcp-server/                     # MCP Server (Azure Functions)
│   ├── function_app.py             # MCP tools implementation
│   ├── host.json                   # MCP extension config
│   ├── requirements.txt
│   ├── infra/                      # Deployment infrastructure
│   └── README.md                   # MCP server documentation
├── mcp-server-local/               # 🆕 MCP Server (Local/Docker)
│   ├── mcp_server.py               # stdio transport
│   ├── mcp_server_http.py          # HTTP transport
│   ├── Dockerfile                  # Container image
│   └── Dockerfile.http             # HTTP server image
├── .vscode/
│   └── mcp.json                    # 🆕 VS Code MCP configuration
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 Quick Start

### 1. Prerequisites

- Azure subscription with Owner/Contributor access
- Azure CLI installed and logged in (`az login`)
- Python 3.10+
- Azure Developer CLI (azd) installed
- Git installed

### 2. Clone the Repository

```bash
git clone https://github.com/san360/bing-foundry.git
cd bing-foundry
```

### 3. Create Virtual Environment

**Windows (PowerShell):**
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Verify activation (should show .venv path)
Get-Command python | Select-Object Source
```

**Windows (Command Prompt):**
```cmd
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Verify activation
which python
```

### 4. Deploy Infrastructure (Azure AI Foundry)

```bash
cd infra
azd up
```

This deploys to **Azure AI Foundry (Microsoft Foundry)**:
- AI Services account (`AIServices` kind) with GPT-4o deployment
- Grounding with Bing Search resource (`Microsoft.Bing/accounts`)
- Log Analytics Workspace for monitoring
- Storage Account for AI services

### 5. Create Bing Connection in AI Foundry Portal

1. Go to [Azure AI Foundry Portal](https://ai.azure.com)
2. Navigate to your project
3. Go to **Settings** → **Connections**
4. Click **+ New connection**
5. Select **Grounding with Bing Search**
6. Select your deployed Bing resource
7. Name the connection (e.g., `bing-grounding`)
8. Note the connection name for the next step

### 6. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your values:
# - AZURE_AI_PROJECT_ENDPOINT: From AI Foundry portal (Project overview)
# - BING_PROJECT_CONNECTION_NAME: The connection name from step 5
```

**Finding your Project Endpoint:**
1. Go to [Azure AI Foundry Portal](https://ai.azure.com)
2. Select your project
3. Go to **Overview**
4. Copy the **Project endpoint** URL

### 7. Install Dependencies

```bash
# Ensure virtual environment is activated!
pip install -r requirements.txt
```

### 8. Run the Application

```bash
streamlit run src/ui/app.py
```

The application will open in your browser at `http://localhost:8501`

### 9. Deactivate Virtual Environment (when done)

```bash
deactivate
```

---

## 🔌 Running MCP Server (for Scenarios 2-5)

The MCP server is required for Scenarios 2, 3, 4, and 5. Choose one of the following options:

### Option A: Local HTTP Server (Recommended for Development)

```bash
cd mcp-server-local
./run-mcp-http-local.sh
```

The MCP server will start on `http://localhost:8000/mcp`

### Option B: Using devtunnel (Required for Remote/Cloud Access)

For scenarios requiring a publicly accessible MCP server:

```bash
# Install devtunnel
# See: https://learn.microsoft.com/azure/developer/dev-tunnels/get-started

# Create and host tunnel
devtunnel create --allow-anonymous
devtunnel port create <tunnel-id> -p 8000
devtunnel host <tunnel-id>

# Use the URL: https://<tunnel-id>.devtunnels.ms/mcp
```

### Option C: Docker

```bash
cd mcp-server-local
docker build -f Dockerfile.http -t bing-mcp-server .
docker run -p 8000:8000 --env-file .env bing-mcp-server
```

---

## 🔧 Troubleshooting

### Issue: `streamlit: command not found`
**Solution:** Make sure you activated the virtual environment and installed dependencies:
```bash
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Issue: Missing environment variables
**Solution:** Create `.env` file with required variables:
```bash
AZURE_AI_PROJECT_ENDPOINT="https://your-project.services.ai.azure.com"
AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4o"
BING_PROJECT_CONNECTION_NAME="your-bing-connection-name"
MCP_SERVER_URL="http://localhost:8000/mcp"
```

### Issue: MCP Server connection failed (Scenarios 2-5)
**Solution:** 
1. Check MCP server is running: `./run-mcp-http-local.sh`
2. Verify URL in UI matches server address
3. For remote access, use devtunnel

### Issue: Azure authentication failed
**Solution:** Run `az login` to authenticate with Azure CLI

### Issue: Agent not found (404 error)
**Solution:** The agent may have been deleted. Restart the app to create a new agent.

### Issue: No citations returned
**Solution:** Ensure the MCP server is returning citations in the expected format. Check MCP server logs.

---

## 🧪 Testing Market Parameter Behavior

The UI allows you to:
1. Enter a company name
2. Select a market (Switzerland, US, Germany, or "No Market")
3. View the pre-baked prompt
4. See how results differ based on market selection
5. Compare behavior with/without market specification

## 🏗️ Architecture: Azure AI Foundry Deployment

This solution uses **Azure AI Foundry** (formerly Azure AI Studio) for agent deployment:

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure AI Foundry                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────────────────┐    │
│  │  AI Services    │    │  Bing Grounding Resource    │    │
│  │  (AIServices)   │◄───│  (Microsoft.Bing/accounts)  │    │
│  │                 │    │                             │    │
│  │  - GPT-4o Model │    │  - Grounding.Search         │    │
│  │  - Agent API    │    │  - Market Configuration     │    │
│  └────────┬────────┘    └─────────────────────────────┘    │
│           │                         ▲                       │
│           │     Connection          │                       │
│           └─────────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Streamlit App       │
              │   (Python Client)     │
              │                       │
              │  - AIProjectClient    │
              │  - Agent Creation     │
              │  - Tool Configuration │
              └───────────────────────┘
```

**Key Components:**
- **AIServices Account**: Provides the GPT-4o model and Agent Service API
- **Bing Grounding Resource**: Enables real-time web search grounding
- **Project Connection**: Links Bing resource to AI Foundry project
- **Python SDK**: `azure-ai-projects` for agent interaction

## 📚 References

- [Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [Bing Grounding Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/bing-tools)
- [Market Codes Reference](https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/reference/market-codes)
- [Azure AI Foundry Agents](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/)
- [AI Projects Python SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-projects-readme)

---

## 🔌 MCP Server Integration

This project includes an **MCP (Model Context Protocol) server** that wraps the Bing Grounding functionality as reusable tools. This allows AI agents (like GitHub Copilot) to use Bing search with custom market parameters.

### Why MCP?

- **Standardized Interface**: MCP provides a protocol for AI agents to discover and use tools
- **Runtime Flexibility**: Pass market parameter at invocation time
- **Multiple Deployment Options**: Local, Docker, or Azure Functions

### Deployment Options

| Option | Transport | Use Case | Endpoint |
|--------|-----------|----------|----------|
| **Azure Functions** | HTTP Streamable | Production | `/runtime/webhooks/mcp` |
| **Local Docker** | HTTP | Development | `localhost:8000/mcp` |
| **Local Python** | stdio | VS Code testing | N/A (stdin/stdout) |
| **Azure Container Apps** | HTTP | Full control | Custom endpoint |

### Quick Start - Azure Functions

```bash
cd mcp-server
azd up
```

### Quick Start - Local Docker

```bash
cd mcp-server-local
docker build -f Dockerfile.http -t bing-mcp-server .
docker run -p 8000:8000 --env-file .env bing-mcp-server
```

### VS Code Integration

Configure in `.vscode/mcp.json` to use with GitHub Copilot:

```json
{
    "servers": {
        "bing-mcp": {
            "type": "http",
            "url": "https://<function-app>.azurewebsites.net/runtime/webhooks/mcp",
            "headers": {
                "x-functions-key": "<your-mcp-extension-key>"
            }
        }
    }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `bing_grounded_search` | Web search with market parameter |
| `analyze_company_risk` | Insurance risk analysis by category |
| `list_supported_markets` | List available market codes |

**Example Usage in Copilot:**
```
@workspace Search for "Tesla lawsuits 2024" using market de-DE with the Bing tool
```

For detailed MCP documentation, see [mcp-server/README.md](mcp-server/README.md).

---

## 📜 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
