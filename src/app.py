"""
Company Risk Analysis Application - Streamlit UI

This application demonstrates:
1. Scenario 1: Direct Agent with Bing Tool - User → Agent (Bing Tool)
2. Scenario 2: Agent-to-Agent via MCP - User → Agent 1 → MCP Server (Agent 2 with Bing)
3. How to test Bing Grounding market parameter behavior
4. Comparing results with different market configurations
"""
import os
import sys
import asyncio
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv

from config import AzureConfig, MARKET_OPTIONS, RISK_CATEGORIES
from agent import CompanyRiskAgent, get_company_risk_analysis_prompt

# Load environment variables
load_dotenv()

# MCP Server Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
MCP_SERVER_KEY = os.getenv("MCP_SERVER_KEY", "")


def init_session_state():
    """Initialize session state variables"""
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = []
    if "mcp_results" not in st.session_state:
        st.session_state.mcp_results = []
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "config_valid" not in st.session_state:
        st.session_state.config_valid = False
    if "mcp_connected" not in st.session_state:
        st.session_state.mcp_connected = False


def validate_config(config: AzureConfig) -> tuple[bool, str]:
    """Validate the Azure configuration"""
    missing = []
    if not config.project_endpoint:
        missing.append("AZURE_AI_PROJECT_ENDPOINT")
    if not config.model_deployment_name:
        missing.append("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    if not config.bing_connection_name:
        missing.append("BING_PROJECT_CONNECTION_NAME")
    
    if missing:
        return False, f"Missing environment variables: {', '.join(missing)}"
    return True, "Configuration valid"


def render_sidebar():
    """Render the sidebar with configuration and information"""
    with st.sidebar:
        st.title("⚙️ Configuration")
        
        # Load and validate config
        config = AzureConfig.from_env()
        is_valid, message = validate_config(config)
        st.session_state.config_valid = is_valid
        
        if is_valid:
            st.success("✅ Configuration loaded")
            with st.expander("Connection Details"):
                st.text(f"Endpoint: {config.project_endpoint[:50]}...")
                st.text(f"Model: {config.model_deployment_name}")
                st.text(f"Bing Connection: {config.bing_connection_name}")
        else:
            st.error(f"❌ {message}")
            st.info("Please create a .env file with the required variables")
            
        st.divider()
        
        # Market Parameter Documentation
        st.subheader("📚 Market Parameter Info")
        
        with st.expander("Where is Market Configured?", expanded=True):
            st.markdown("""
            **Key Finding:** The `market` parameter is configured at the 
            **TOOL level**, specifically in `BingGroundingSearchConfiguration`.
            
            ```python
            BingGroundingSearchConfiguration(
                project_connection_id=conn_id,
                market="de-CH",  # <-- HERE!
                count=10,
                freshness="Month"
            )
            ```
            
            **NOT** at the agent creation level!
            """)
            
        with st.expander("Can Market be Set at Runtime?"):
            st.markdown("""
            **YES!** You have two options:
            
            1. **Create tools dynamically** with different market 
               configurations per request
               
            2. **Create multiple agents** each with a different 
               pre-configured market
               
            This app demonstrates option 1: creating tools with 
            the market parameter at runtime.
            """)
            
        with st.expander("Default Behavior (No Market)"):
            st.markdown("""
            If `market` is **not specified**:
            
            - Bing uses internal mapping based on request origin
            - Results may vary based on Azure region
            - For consistent results, **always specify market**
            
            Select "No Market (Default)" in the dropdown to test 
            this behavior.
            """)
            
        st.divider()
        
        # Risk Categories Reference
        st.subheader("📋 Risk Categories Analyzed")
        for cat in RISK_CATEGORIES:
            st.caption(f"• {cat}")
            
        return config


def render_main_content(config: AzureConfig):
    """Render the main application content"""
    st.title("🏢 Company Risk Analysis")
    st.markdown("*Insurance Due Diligence with Bing Grounding*")
    
    # Two-column layout for inputs
    col1, col2 = st.columns([2, 1])
    
    with col1:
        company_name = st.text_input(
            "Company Name",
            placeholder="Enter company name (e.g., 'Nestlé', 'Credit Suisse')",
            help="Enter the full or common name of the company to analyze"
        )
        
    with col2:
        market_selection = st.selectbox(
            "Market/Region",
            options=list(MARKET_OPTIONS.keys()),
            index=0,
            help="Select the market for Bing search results. This tests the 'market' parameter behavior."
        )
        
    # Advanced options
    with st.expander("🔧 Advanced Search Options"):
        col_a, col_b = st.columns(2)
        with col_a:
            result_count = st.slider(
                "Number of Results",
                min_value=5,
                max_value=50,
                value=10,
                help="Number of Bing search results to return (max 50)"
            )
        with col_b:
            freshness = st.selectbox(
                "Freshness Filter",
                options=["Day", "Week", "Month"],
                index=2,
                help="How recent should the search results be?"
            )
    
    # Show the prompt that will be used
    st.subheader("📝 Pre-baked Prompt")
    
    market_code = None
    market_config = MARKET_OPTIONS.get(market_selection)
    if market_config:
        market_code = market_config.code
        
    prompt = get_company_risk_analysis_prompt(company_name or "[Company Name]", market_code)
    
    with st.expander("View Full Prompt", expanded=False):
        st.code(prompt, language="markdown")
        
    # Tool configuration display
    st.subheader("🔧 Bing Tool Configuration")
    
    tool_config_col1, tool_config_col2 = st.columns(2)
    
    with tool_config_col1:
        st.metric(
            "Market Parameter",
            market_code if market_code else "NOT SET (Default)",
            delta="Explicit" if market_code else "Implicit",
            delta_color="normal" if market_code else "off"
        )
        
    with tool_config_col2:
        st.metric("Results Count", result_count)
        
    st.info(f"""
    **Configuration Location:** `BingGroundingSearchConfiguration`
    
    The market parameter `{market_code or 'null'}` will be passed to:
    ```python
    BingGroundingSearchConfiguration(
        project_connection_id=connection_id,
        {"market='" + market_code + "'," if market_code else "# market NOT specified - using Bing's default"}
        count={result_count},
        freshness='{freshness}'
    )
    ```
    """)
    
    # Run Analysis Button
    st.divider()
    
    run_disabled = not st.session_state.config_valid or not company_name
    
    if st.button(
        "🔍 Run Risk Analysis",
        type="primary",
        disabled=run_disabled,
        use_container_width=True
    ):
        if company_name:
            run_analysis(config, company_name, market_code, result_count, freshness)
            
    if run_disabled and not company_name:
        st.warning("Please enter a company name to analyze")
        
    # Display results
    if st.session_state.analysis_results:
        st.divider()
        st.subheader("📊 Analysis Results")
        
        for i, result in enumerate(reversed(st.session_state.analysis_results)):
            with st.expander(
                f"Analysis: {result['company']} | Market: {result['market'] or 'Default'} | {result['timestamp']}",
                expanded=(i == 0)
            ):
                # Tool config used
                st.caption("**Tool Configuration Used:**")
                st.json(result['tool_config'])
                
                # Analysis text
                st.markdown("---")
                st.markdown(result['text'])
                
                # Citations
                if result['citations']:
                    st.markdown("---")
                    st.caption("**Sources:**")
                    for citation in result['citations']:
                        st.markdown(f"- [{citation.get('title', citation['url'])}]({citation['url']})")


def run_analysis(config: AzureConfig, company_name: str, market: str, count: int, freshness: str):
    """Run the company risk analysis"""
    import datetime
    
    with st.spinner(f"Analyzing {company_name}... This may take a minute."):
        try:
            # Create agent
            agent = CompanyRiskAgent(
                project_endpoint=config.project_endpoint,
                model_deployment_name=config.model_deployment_name,
                bing_connection_name=config.bing_connection_name,
            )
            
            # Generate prompt
            prompt = get_company_risk_analysis_prompt(company_name, market)
            
            # Run analysis (using asyncio)
            async def do_analysis():
                return await agent.analyze_company(
                    prompt=prompt,
                    market=market,
                    count=count,
                    freshness=freshness,
                )
                
            response = asyncio.run(do_analysis())
            
            # Store result
            st.session_state.analysis_results.append({
                "company": company_name,
                "market": market,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "text": response.text,
                "citations": response.citations,
                "tool_config": response.tool_configuration,
            })
            
            st.success(f"✅ Analysis complete for {company_name}")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error during analysis: {str(e)}")
            st.exception(e)


def render_comparison_tab():
    """Render the market comparison tab"""
    st.header("📊 Market Comparison Test")
    
    st.markdown("""
    This tab allows you to run the **same search** with **different market settings**
    to compare how results differ based on the `market` parameter.
    """)
    
    company_for_comparison = st.text_input(
        "Company to Compare",
        placeholder="Enter company name",
        key="comparison_company"
    )
    
    markets_to_compare = st.multiselect(
        "Select Markets to Compare",
        options=list(MARKET_OPTIONS.keys()),
        default=["Switzerland (German)", "United States", "No Market (Default)"],
        help="Select 2-4 markets to compare"
    )
    
    if st.button("Run Comparison", disabled=not company_for_comparison or len(markets_to_compare) < 2):
        st.info("Comparison feature would run the analysis for each selected market and show side-by-side results.")
        st.warning("Note: This is a demonstration. Full implementation would require multiple API calls.")
        
        # Show what the configuration would look like for each
        for market_name in markets_to_compare:
            market_config = MARKET_OPTIONS.get(market_name)
            market_code = market_config.code if market_config else None
            
            with st.expander(f"Configuration for: {market_name}"):
                st.code(f"""
BingGroundingSearchConfiguration(
    project_connection_id="<your-connection-id>",
    {"market='" + market_code + "'," if market_code else "# market NOT specified"}
    count=10,
    freshness='Month'
)
                """, language="python")


def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="Company Risk Analysis - Bing Grounding PoC",
        page_icon="🏢",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    init_session_state()
    
    # Render sidebar and get config
    config = render_sidebar()
    
    # Create tabs - NEW: Added Scenario tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Scenario 1: Direct Agent", 
        "🔗 Scenario 2: Agent → MCP Agent",
        "📊 Market Comparison", 
        "📖 Documentation"
    ])
    
    with tab1:
        render_direct_agent_scenario(config)
        
    with tab2:
        render_mcp_agent_scenario(config)
        
    with tab3:
        render_comparison_tab()
        
    with tab4:
        render_documentation_tab()


def render_direct_agent_scenario(config: AzureConfig):
    """Render Scenario 1: Direct Agent with Bing Tool"""
    st.header("🎯 Scenario 1: Direct Agent with Bing Tool")
    
    st.info("""
    **Architecture:** User → AI Agent (with Bing Grounding Tool attached directly)
    
    In this scenario, the Bing tool is attached directly to the agent. The market parameter 
    is configured in `BingGroundingSearchConfiguration` when creating the tool.
    """)
    
    # Show architecture diagram
    with st.expander("📊 Architecture Diagram", expanded=False):
        st.code("""
┌─────────────┐      ┌───────────────────────────────────────┐
│             │      │         AI Foundry Agent              │
│    User     │─────►│  ┌─────────────────────────────────┐  │
│   (You)     │      │  │     Bing Grounding Tool         │  │
│             │      │  │   market="en-US" / "de-DE"      │  │
└─────────────┘      │  └─────────────────────────────────┘  │
                     └───────────────────────────────────────┘
        """, language="text")
    
    render_main_content(config)


def render_mcp_agent_scenario(config: AzureConfig):
    """Render Scenario 2: Agent calling another Agent via MCP"""
    st.header("🔗 Scenario 2: Agent → MCP Server (Another Agent)")
    
    st.info("""
    **Architecture:** User → Agent 1 (Orchestrator) → MCP Server → Agent 2 (Bing Tool)
    
    In this scenario, Agent 1 (without Bing tool) calls an MCP server that hosts Agent 2 
    (with Bing tool). The market parameter flows from Agent 1 through the MCP tool call.
    """)
    
    # Show architecture diagram
    with st.expander("📊 Architecture Diagram", expanded=True):
        st.code("""
┌─────────────┐    ┌───────────────────┐    ┌────────────────────────────────┐
│             │    │    Agent 1        │    │        MCP Server              │
│    User     │───►│  (Orchestrator)   │───►│  ┌──────────────────────────┐  │
│   (You)     │    │                   │    │  │      Agent 2             │  │
│             │    │  - Has MCP Tool   │MCP │  │  (Bing Grounding Tool)   │  │
│  "Analyze   │    │  - Passes market  │───►│  │  market=<from Agent 1>  │  │
│   Tesla     │    │    to MCP call    │    │  └──────────────────────────┘  │
│   de-DE"    │    │                   │    │                                │
└─────────────┘    └───────────────────┘    └────────────────────────────────┘
        """, language="text")
    
    st.divider()
    
    # MCP Server Configuration
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🔌 MCP Server Configuration")
        
        mcp_url = st.text_input(
            "MCP Server URL",
            value=MCP_SERVER_URL,
            help="URL of the MCP server (local Docker or Azure Functions)"
        )
        
        mcp_key = st.text_input(
            "MCP Server Key (optional)",
            value=MCP_SERVER_KEY,
            type="password",
            help="x-functions-key for Azure Functions MCP server"
        )
        
    with col2:
        st.subheader("🔍 Connection Test")
        if st.button("Test MCP Connection"):
            with st.spinner("Testing connection..."):
                success, message = test_mcp_connection(mcp_url, mcp_key)
                if success:
                    st.success(message)
                    st.session_state.mcp_connected = True
                else:
                    st.error(message)
                    st.session_state.mcp_connected = False
    
    st.divider()
    
    # Analysis inputs
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        company_name = st.text_input(
            "Company Name",
            placeholder="Enter company name (e.g., 'Tesla', 'Volkswagen')",
            key="mcp_company",
            help="This will be sent to Agent 1, which forwards to MCP Server"
        )
        
    with col_b:
        market_selection = st.selectbox(
            "Market/Region (passed to MCP)",
            options=list(MARKET_OPTIONS.keys()),
            index=0,
            key="mcp_market",
            help="This market parameter will flow: Agent 1 → MCP Tool → Agent 2 → Bing"
        )
    
    # Risk category selection
    risk_category = st.selectbox(
        "Risk Category",
        options=["all", "litigation", "labor_practices", "environmental", "financial", "regulatory", "reputation"],
        index=0,
        key="mcp_risk_category",
        help="Category of risk to analyze"
    )
    
    # Show the MCP tool call that will be made
    st.subheader("📝 MCP Tool Call Preview")
    
    market_code = None
    market_config = MARKET_OPTIONS.get(market_selection)
    if market_config:
        market_code = market_config.code
    
    mcp_call_preview = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": "analyze_company_risk",
            "arguments": {
                "company_name": company_name or "<company_name>",
                "risk_category": risk_category,
                "market": market_code or "en-US"
            }
        }
    }
    
    with st.expander("View MCP Tool Call JSON", expanded=False):
        st.json(mcp_call_preview)
        
    st.info(f"""
    **Data Flow:**
    1. User enters company "{company_name or '<company>'}" with market `{market_code or 'en-US'}`
    2. Agent 1 recognizes need for Bing search, calls MCP tool
    3. MCP Server receives: `analyze_company_risk(company="{company_name or '<company>'}", market="{market_code or 'en-US'}")`
    4. Agent 2 (in MCP Server) creates Bing tool with `market="{market_code or 'en-US'}"`
    5. Results flow back through the chain
    """)
    
    st.divider()
    
    # Run buttons
    col_run1, col_run2 = st.columns(2)
    
    with col_run1:
        if st.button(
            "🔍 Run via MCP (Agent → Agent)",
            type="primary",
            disabled=not company_name,
            use_container_width=True
        ):
            run_mcp_analysis(mcp_url, mcp_key, company_name, risk_category, market_code)
    
    with col_run2:
        if st.button(
            "🔄 Run via Direct Agent (Comparison)",
            disabled=not company_name or not st.session_state.config_valid,
            use_container_width=True
        ):
            run_analysis(config, company_name, market_code, 10, "Month")
    
    # Display MCP results
    if st.session_state.mcp_results:
        st.divider()
        st.subheader("📊 MCP Analysis Results")
        
        for i, result in enumerate(reversed(st.session_state.mcp_results)):
            with st.expander(
                f"[MCP] {result['company']} | Market: {result['market']} | {result['timestamp']}",
                expanded=(i == 0)
            ):
                st.caption("**Route:** User → Agent 1 → MCP Server → Agent 2 (Bing)")
                
                # MCP call details
                st.caption("**MCP Tool Called:**")
                st.code(f"""
Tool: {result.get('tool_name', 'analyze_company_risk')}
Arguments:
  company_name: "{result['company']}"
  risk_category: "{result.get('risk_category', 'all')}"
  market: "{result['market']}"
                """)
                
                # Results
                st.markdown("---")
                if isinstance(result.get('response'), dict):
                    st.json(result['response'])
                else:
                    st.markdown(result.get('response', 'No response'))


def test_mcp_connection(url: str, key: str = None) -> tuple[bool, str]:
    """Test connection to MCP server"""
    try:
        headers = {"Content-Type": "application/json"}
        if key:
            headers["x-functions-key"] = key
        
        # Send initialize request
        response = requests.post(
            url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": "test",
                "method": "initialize"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            server_info = data.get("result", {}).get("serverInfo", {})
            return True, f"✅ Connected to {server_info.get('name', 'MCP Server')} v{server_info.get('version', '?')}"
        else:
            return False, f"❌ HTTP {response.status_code}: {response.text[:100]}"
            
    except requests.exceptions.ConnectionError:
        return False, "❌ Connection failed. Is the MCP server running?"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"


def run_mcp_analysis(url: str, key: str, company_name: str, risk_category: str, market: str):
    """Run analysis via MCP server"""
    import datetime
    
    with st.spinner(f"Calling MCP Server for {company_name}..."):
        try:
            headers = {"Content-Type": "application/json"}
            if key:
                headers["x-functions-key"] = key
            
            # Call the analyze_company_risk tool via MCP
            response = requests.post(
                url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "tools/call",
                    "params": {
                        "name": "analyze_company_risk",
                        "arguments": {
                            "company_name": company_name,
                            "risk_category": risk_category,
                            "market": market or "en-US"
                        }
                    }
                },
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                result_content = data.get("result", {}).get("content", [])
                
                # Extract text from response
                response_text = ""
                for content in result_content:
                    if content.get("type") == "text":
                        response_text = content.get("text", "")
                        try:
                            response_text = json.loads(response_text)
                        except:
                            pass
                
                st.session_state.mcp_results.append({
                    "company": company_name,
                    "market": market or "en-US",
                    "risk_category": risk_category,
                    "tool_name": "analyze_company_risk",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "response": response_text,
                })
                
                st.success(f"✅ MCP Analysis complete for {company_name}")
                st.rerun()
            else:
                st.error(f"❌ MCP Error: HTTP {response.status_code}")
                st.code(response.text)
                
        except Exception as e:
            st.error(f"❌ Error calling MCP Server: {str(e)}")
            st.exception(e)


def render_documentation_tab():
    """Render the documentation tab"""
    st.header("📖 Documentation")
        
    # Scenario comparison
    st.subheader("🔄 Scenario Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### Scenario 1: Direct Agent
        
        **Architecture:**
        ```
        User → Agent (Bing Tool)
        ```
        
        **Pros:**
        - Simpler architecture
        - Lower latency (one agent)
        - Direct control over tool config
        
        **Cons:**
        - Tool config must be at agent creation
        - Less flexible for multi-tool scenarios
        
        **Best For:**
        - Single-purpose agents
        - Direct Bing search needs
        """)
        
    with col2:
        st.markdown("""
        ### Scenario 2: Agent → MCP Agent
        
        **Architecture:**
        ```
        User → Agent 1 → MCP Server → Agent 2 (Bing)
        ```
        
        **Pros:**
        - Decoupled architecture
        - MCP tools can be reused
        - Market passed at runtime
        - Multiple agents can share MCP server
        
        **Cons:**
        - Higher latency (two agents)
        - More infrastructure to manage
        
        **Best For:**
        - Multi-agent systems
        - Shared tool infrastructure
        """)
    
    st.divider()
    
    st.subheader("📊 Market Parameter Flow")
    
    st.markdown("""
    ### How Market Flows in Each Scenario
    
    #### Scenario 1 (Direct)
    ```python
    # Market set at tool creation time
    bing_tool = BingGroundingTool(
        bing_grounding_search=BingGroundingSearchConfiguration(
            connection_id=connection_id,
            market="de-DE",  # ← Set here
        )
    )
    agent = create_agent(tools=bing_tool)
    ```
    
    #### Scenario 2 (MCP)
    ```python
    # Agent 1: User's request includes market preference
    user_request = "Analyze Tesla using German market (de-DE)"
    
    # Agent 1 extracts market and calls MCP tool
    mcp_tool_call = {
        "name": "analyze_company_risk",
        "arguments": {
            "company_name": "Tesla",
            "market": "de-DE"  # ← Passed to MCP
        }
    }
    
    # MCP Server (Agent 2) receives market and creates tool dynamically
    bing_tool = BingGroundingTool(
        bing_grounding_search=BingGroundingSearchConfiguration(
            connection_id=connection_id,
            market=arguments["market"],  # ← From MCP call
        )
    )
    ```
    """)
    
    st.divider()
    
    st.markdown("""
    ## Understanding the Market Parameter in Bing Grounding
    
    ### Configuration Location
    
    The `market` parameter is configured in `BingGroundingSearchConfiguration`, which is part of 
    `BingGroundingSearchToolParameters` when creating a `BingGroundingAgentTool`.
    
    ```python
    from azure.ai.projects.models import (
        BingGroundingAgentTool,
        BingGroundingSearchToolParameters,
        BingGroundingSearchConfiguration,
    )
    
    # Market is specified HERE - at the tool configuration level
    bing_tool = BingGroundingAgentTool(
        bing_grounding=BingGroundingSearchToolParameters(
            search_configurations=[
                BingGroundingSearchConfiguration(
                    project_connection_id=connection_id,
                    market="de-CH",  # <-- MARKET PARAMETER
                    count=10,
                    freshness="Month",
                    set_lang="de"  # Optional: UI language
                )
            ]
        )
    )
    ```
    
    ### Key Points
    
    1. **NOT at Agent Level**: The market is not specified when creating the agent itself, 
       but when configuring the Bing tool.
       
    2. **Runtime Configuration**: Since tools are passed to agents at creation, you can 
       create agents dynamically with different market configurations.
       
    3. **Per-Request Markets**: By creating agents on-demand with specific tool configs, 
       you can vary the market per request.
       
    4. **Default Behavior**: If market is omitted, Bing uses internal mapping based on 
       request origin. This may lead to inconsistent results.
    
    ### Market Code Format
    
    Markets use the format: `<language>-<country/region>`
    
    | Market | Code |
    |--------|------|
    | Switzerland (German) | `de-CH` |
    | Switzerland (French) | `fr-CH` |
    | Germany | `de-DE` |
    | United States | `en-US` |
    | United Kingdom | `en-GB` |
    
    See [Bing Market Codes](https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/reference/market-codes) 
    for the complete list.
    
    ### REST API Example
    
    In REST API calls, the market is specified in the tool configuration:
    
    ```json
    {
      "tools": [
        {
          "type": "bing_grounding",
          "bing_grounding": {
            "search_configurations": [
              {
                "project_connection_id": "<connection-id>",
                "count": 10,
                "market": "de-CH",
                "set_lang": "de",
                "freshness": "Month"
              }
            ]
          }
        }
      ]
    }
    ```
    """)
