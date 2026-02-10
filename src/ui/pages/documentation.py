"""
Documentation page for the application.
"""
import streamlit as st


def render_documentation():
    """Render the documentation tab."""
    st.header("📖 Documentation")

    # Overview Section
    st.markdown("""
    ## 🏗️ Architecture Overview

    This application demonstrates **five scenarios** for using Bing Grounding with Azure AI Foundry Agents.
    Each scenario explores different architectural patterns for integrating real-time web search into AI agents.
    """)

    # High-level architecture diagram
    st.code("""
                     ┌─────────────────────────────────────────────┐
                     │           Azure AI Foundry                  │
  ┌──────┐    ┌──────────────┐    ┌──────────┐    ┌─────────────┐  │
  │ User │───>│ Streamlit App│───>│ AI Agent │───>│  Bing       │  │
  └──────┘    └──────────────┘    └──────────┘    │  Grounding  │  │
                                       │          │  API        │  │
                                       ▼          └─────────────┘  │
                                  ┌──────────┐         ▲           │
                                  │MCP Server│─────────┘           │
                                  └──────────┘                     │
                                                                   │
                     └─────────────────────────────────────────────┘
    """, language=None)

    # Scenario 1
    st.markdown("---")
    st.subheader("📌 Scenario 1: Direct Agent with Bing Tool")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("""
        **Architecture:** `User → Agent (Bing Tool Attached) → Bing API → Results`

        The simplest pattern where the Bing Grounding tool is directly attached to the agent at creation time.

        **How it works:**
        1. User submits a company analysis request
        2. App creates/reuses an agent with Bing grounding tool attached
        3. Agent searches using the native Bing grounding capability
        4. Citations returned as URL annotations in response

        **Key Characteristics:**
        - ✅ Lowest latency
        - ✅ Simplest implementation
        - ⚠️ Market configured at tool creation time (not runtime)
        """)

    with col2:
        st.code("""
  User      Streamlit App    Direct Agent     Bing API
   │             │                │               │
   │ company+mkt │                │               │
   │────────────>│                │               │
   │             │ Create agent   │               │
   │             │ w/ Bing tool   │               │
   │             │───────────────>│               │
   │             │                │ Grounded      │
   │             │                │ search        │
   │             │                │──────────────>│
   │             │                │ Results +     │
   │             │                │ citations     │
   │             │                │<──────────────│
   │             │ Analysis       │               │
   │             │<───────────────│               │
   │ Risk report │                │               │
   │<────────────│                │               │
        """, language=None)

    # Scenario 2
    st.markdown("---")
    st.subheader("📌 Scenario 2: Two-Agent Pattern via MCP Server")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("""
        **Architecture:** `User → Orchestrator Agent → MCP Tool → Worker Agent (Bing) → Results`

        An orchestrator agent delegates search to ephemeral worker agents created via MCP.

        **How it works:**
        1. Orchestrator agent receives analysis request
        2. Orchestrator calls MCP tool `create_and_run_bing_agent`
        3. MCP server creates a Worker Agent with market-specific Bing tool
        4. Worker executes search and returns results
        5. MCP server deletes the worker agent (ephemeral)
        6. Results flow back through orchestrator

        **Key Characteristics:**
        - ✅ Dynamic market configuration at runtime
        - ✅ Isolated worker agents per request
        - ⚠️ Higher latency (agent creation overhead)
        """)

    with col2:
        st.code("""
  User     Orchestrator    MCP Server     Worker Agent    Bing API
   │           │               │               │             │
   │ request   │               │               │             │
   │──────────>│               │               │             │
   │           │ create_and_   │               │             │
   │           │ run_bing_agent│               │             │
   │           │──────────────>│               │             │
   │           │               │ Create agent  │             │
   │           │               │──────────────>│             │
   │           │               │               │ Grounded    │
   │           │               │               │ search      │
   │           │               │               │────────────>│
   │           │               │               │ Results     │
   │           │               │               │<────────────│
   │           │               │ Search results│             │
   │           │               │<──────────────│             │
   │           │               │ Delete worker │             │
   │           │ JSON response │               │             │
   │           │<──────────────│               │             │
   │ Report    │               │               │             │
   │<──────────│               │               │             │
        """, language=None)

    # Scenario 3
    st.markdown("---")
    st.subheader("📌 Scenario 3: Agent → MCP Tool → REST API")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("""
        **Architecture:** `User → Agent (MCP Tool) → MCP Server → Bing REST API → Results`

        Agent uses MCP tool that directly calls the Bing Grounding REST API without creating nested agents.

        **How it works:**
        1. Agent with MCP tool receives request
        2. Agent calls `bing_search_rest_api` MCP tool with market parameter
        3. MCP server makes direct POST to `/openai/responses` with `bing_grounding` tool
        4. REST API returns grounded results with citations
        5. MCP server formats and returns results

        **Key Characteristics:**
        - ✅ Direct REST API access (no nested agents)
        - ✅ Full control: count, freshness, setLang parameters
        - ✅ Citations extracted from REST response
        """)

    with col2:
        st.code("""
  User       MCP Agent      MCP Server     Bing REST API
   │             │               │               │
   │ search+mkt  │               │               │
   │────────────>│               │               │
   │             │ bing_search_  │               │
   │             │ rest_api      │               │
   │             │──────────────>│               │
   │             │               │ POST /openai/ │
   │             │               │ responses     │
   │             │               │──────────────>│
   │             │               │ JSON+citations│
   │             │               │<──────────────│
   │             │ Formatted     │               │
   │             │<──────────────│               │
   │ Analysis    │               │               │
   │<────────────│               │               │
        """, language=None)

    # Scenario 4
    st.markdown("---")
    st.subheader("📌 Scenario 4: Multi-Market Sequential Search")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("""
        **Architecture:** `User → Agent → MCP Tool (called N times) → Aggregated Results`

        Single agent makes multiple sequential tool calls for different markets.

        **How it works:**
        1. User selects multiple markets (e.g., en-US, de-DE, ja-JP)
        2. Agent receives prompt instructing N separate tool calls
        3. Agent calls MCP tool sequentially for each market
        4. Agent aggregates results and provides cross-market analysis

        **Key Characteristics:**
        - ✅ Simple single-agent approach
        - ⚠️ Sequential execution (slower for many markets)
        - ⚠️ All-or-nothing failure mode
        - 📊 Best for 2-3 markets
        """)

    with col2:
        st.code("""
  User     MultiMarket Agent   MCP Server    Bing REST API
   │             │                 │               │
   │ multi-mkt   │                 │               │
   │────────────>│                 │               │
   │             │                 │               │
   │             │  ┌── Loop: for each market ──┐  │
   │             │  │ bing_search_rest_api      │  │
   │             │──│────────────────>│          │  │
   │             │  │                │ REST call │  │
   │             │  │                │─────────────>│
   │             │  │                │ Results   │  │
   │             │  │                │<─────────────│
   │             │  │ JSON+citations │          │  │
   │             │<─│────────────────│          │  │
   │             │  └───────────────────────────┘  │
   │             │                 │               │
   │             │ Aggregate       │               │
   │ Cross-mkt   │                 │               │
   │ report      │                 │               │
   │<────────────│                 │               │
        """, language=None)

    # Scenario 5
    st.markdown("---")
    st.subheader("📌 Scenario 5: Workflow-Based Parallel Multi-Market")

    st.markdown("""
    **Architecture:** `User → Dispatcher → Parallel Searches → Aggregator → Analysis Agent → Results`

    Structured workflow with parallel execution and dedicated analysis phase.

    **Workflow Stages:**
    1. **Stage 1 - Dispatch:** Split request into parallel market tasks
    2. **Stage 2 - Parallel Search:** Execute all markets concurrently (90s timeout each)
    3. **Stage 3 - Aggregation:** Collect results, handle failures gracefully
    4. **Stage 4 - Analysis:** Dedicated agent synthesizes cross-market findings

    **Key Characteristics:**
    - ✅ **3-5x faster** than sequential (parallel execution)
    - ✅ Per-market timeout handling (90s default)
    - ✅ Graceful degradation on failures
    - ✅ Dedicated analysis agent (no tools, pure synthesis)
    - 📊 Best for production multi-market research
    """)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.caption("**Workflow Stages**")
        st.code("""
  ┌─────────────────────────────────┐
  │  User Request + Markets         │
  └───────────────┬─────────────────┘
                  │
                  ▼
  ┌─────────────────────────────────┐
  │  Stage 1: Market Dispatcher     │
  └───┬───────────┬─────────────┬───┘
      │           │             │
      ▼           ▼             ▼
  ┌─────────┐ ┌─────────┐ ┌─────────┐
  │ en-US   │ │ de-DE   │ │ ja-JP   │
  │ Search  │ │ Search  │ │ Search  │
  └────┬────┘ └────┬────┘ └────┬────┘
       │           │           │
       └─────┬─────┘───────────┘
             ▼
  ┌─────────────────────────────────┐
  │  Stage 3: Result Aggregator     │
  └───────────────┬─────────────────┘
                  │
                  ▼
  ┌─────────────────────────────────┐
  │  Stage 4: Analysis Agent        │
  └───────────────┬─────────────────┘
                  │
                  ▼
  ┌─────────────────────────────────┐
  │  Final Report                   │
  └─────────────────────────────────┘
        """, language=None)

    with col2:
        st.caption("**Sequence Flow**")
        st.code("""
  User     Dispatcher   Search Agents  Aggregator   Analyzer
   │           │              │             │           │
   │ request   │              │             │           │
   │──────────>│              │             │           │
   │           │              │             │           │
   │           │── Parallel ──│             │           │
   │           │  en-US       │             │           │
   │           │─────────────>│             │           │
   │           │  de-DE       │             │           │
   │           │─────────────>│             │           │
   │           │  ja-JP       │             │           │
   │           │─────────────>│             │           │
   │           │              │             │           │
   │           │              │  Results    │           │
   │           │              │────────────>│           │
   │           │              │             │ Merge +   │
   │           │              │             │ failures  │
   │           │              │             │ findings  │
   │           │              │             │──────────>│
   │           │              │             │           │
   │           │              │             │  Synthesis│
   │ Final     │              │             │           │
   │ report    │              │             │           │
   │<──────────│──────────────│─────────────│───────────│
        """, language=None)

    # Comparison Table
    st.markdown("---")
    st.subheader("📊 Scenario Comparison")

    st.markdown("""
    | Feature | Scenario 1 | Scenario 2 | Scenario 3 | Scenario 4 | Scenario 5 |
    |---------|:----------:|:----------:|:----------:|:----------:|:----------:|
    | **Pattern** | Direct | Two-Agent | MCP REST | Multi-Market | Workflow |
    | **Markets** | Single | Single | Single | Multiple | Multiple |
    | **Execution** | Sync | Sync | Sync | Sequential | **Parallel** |
    | **Timeout Handling** | Basic | Basic | Basic | Limited | **Per-market** |
    | **Failure Mode** | All-or-nothing | All-or-nothing | All-or-nothing | All-or-nothing | **Graceful** |
    | **Latency** | ⚡ Lowest | Medium | Medium | High | **Fast** |
    | **Complexity** | Low | Medium | Medium | Medium | High |
    """)

    # Architecture Decision Flow
    st.markdown("---")
    st.subheader("🧭 Choosing the Right Scenario")

    st.code("""
  How many markets?
  │
  ├── Single ── Need runtime market config?
  │               │
  │               ├── No ──> Scenario 1: Direct Agent
  │               │
  │               └── Yes ── Need fine-grained API control?
  │                            │
  │                            ├── No ──> Scenario 2: Two-Agent MCP
  │                            │
  │                            └── Yes ─> Scenario 3: MCP REST API
  │
  └── Multiple ── Performance requirements?
                    │
                    ├── 2-3 markets ──> Scenario 4: Sequential
                    │
                    └── 4+ markets ──> Scenario 5: Workflow Parallel
    """, language=None)

    # Module Structure
    st.markdown("---")
    st.subheader("📁 Module Structure")

    st.code("""
  src/
  ├── core/                          (Domain Models)
  │   ├── models.py
  │   └── interfaces.py
  │
  ├── infrastructure/                (Azure Clients)
  │   ├── azure_client.py
  │   ├── config.py
  │   └── tracing.py
  │
  ├── services/                      (Business Logic)
  │   ├── agent_service.py
  │   └── risk_analyzer.py
  │
  ├── scenarios/                     (Implementations)
  │   ├── base.py
  │   ├── scenario1_direct.py
  │   ├── scenario2_mcp_agent.py
  │   ├── scenario3_mcp_rest.py
  │   ├── scenario4_multi_market.py
  │   └── scenario5_workflow.py
  │
  └── ui/                            (Streamlit UI)
      ├── app.py
      └── pages/

  Dependencies:
    ui/ ──> scenarios/ ──> services/ ──> infrastructure/ ──> core/
                  └──────────────────────────────────────────>│
    """, language=None)

    # SOLID Principles
    st.markdown("---")
    st.subheader("🏛️ SOLID Principles Applied")

    st.markdown("""
    - **Single Responsibility**: Each scenario file handles one integration pattern
    - **Open/Closed**: New scenarios extend `BaseScenario` without modifying existing code
    - **Liskov Substitution**: All scenarios implement the same `execute()` interface
    - **Interface Segregation**: Separate interfaces for client factory, risk analysis
    - **Dependency Inversion**: Scenarios depend on `IAzureClientFactory` abstraction
    """)

    st.code("""
  ┌─────────────────────────────┐     ┌──────────────────────────┐
  │      BaseScenario           │     │  IAzureClientFactory     │
  │─────────────────────────────│     │──────────────────────────│
  │ + execute(request)          │     │ + create_client()        │
  │   -> AnalysisResponse       │     │   -> AIProjectClient     │
  └──────────────┬──────────────┘     └──────────────────────────┘
                 │                               ▲
       ┌─────────┼──────────┬────────────┐       │
       │         │          │            │       │
       ▼         ▼          ▼            ▼       │ uses
  ┌─────────┐┌────────┐┌─────────┐┌──────────┐  │
  │ Direct  ││  MCP   ││ MCPRest ││MultiMkt  │──┘
  │ Agent   ││ Agent  ││  API    ││Workflow  │
  │ Scenario││Scenario││Scenario ││Scenario  │
  └─────────┘└────────┘└─────────┘└──────────┘
    """, language=None)

    # Citation Handling
    st.markdown("---")
    st.subheader("🔗 Citation Handling")

    st.markdown("""
    Citations are extracted from two sources depending on the scenario:

    **1. URL Annotations (Scenario 1 - Direct Bing Grounding)**
    ```python
    # Citations in response.output[].content[].annotations[]
    for annotation in content.annotations:
        if hasattr(annotation, 'url'):
            citations.append(Citation(url=annotation.url, title=annotation.title))
    ```

    **2. MCP Tool JSON Response (Scenarios 2-5)**
    ```python
    # Citations embedded in JSON response from MCP tool
    data = json.loads(content.text)
    for cit in data.get('citations', []):
        citations.append(Citation(url=cit['url'], title=cit['title']))
    ```
    """)

    st.code("""
  Scenario 1:                        Scenarios 2-5:
  Agent Response                     MCP Tool Response
       │                                  │
       ▼                                  ▼
  URL Annotations                    JSON Payload
       │                                  │
       ▼                                  ▼
  Citations List                     Citations List
       │                                  │
       └──────────────┬───────────────────┘
                      ▼
            Rendered as clickable links
    """, language=None)

    # Running the Application
    st.markdown("---")
    st.subheader("🚀 Running the Application")

    st.code("""
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export AZURE_AI_PROJECT_ENDPOINT="https://your-project.services.ai.azure.com"
export AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4o"
export BING_PROJECT_CONNECTION_NAME="your-bing-connection"
export MCP_SERVER_URL="https://your-mcp-server.azurewebsites.net/mcp"

# Run the app
streamlit run src/ui/app.py
    """, language="bash")
