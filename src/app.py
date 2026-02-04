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
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv

# CRITICAL: st.set_page_config() must be the first Streamlit command
# It must be called before any other st.* functions
st.set_page_config(
    page_title="Company Risk Analysis - Bing Grounding PoC",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables first
load_dotenv()

# Initialize OpenTelemetry tracing with Azure Monitor
def setup_tracing():
    """Configure OpenTelemetry tracing with Azure Monitor using Foundry project telemetry"""
    try:
        # Avoid re-initializing tracing on Streamlit reruns
        if os.environ.get("OTEL_CONFIGURED") == "true":
            logger.info("Tracing already configured; skipping re-initialization")
            return True

        from azure.ai.projects import AIProjectClient
        from azure.identity import (
            AzureCliCredential,
            VisualStudioCodeCredential,
            EnvironmentCredential,
            ManagedIdentityCredential,
            ChainedTokenCredential,
        )
        from azure.monitor.opentelemetry import configure_azure_monitor
        from azure.core.settings import settings
        
        # Get connection string from Foundry project
        project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
        if not project_endpoint:
            logger.warning("AZURE_AI_PROJECT_ENDPOINT not set - tracing disabled")
            return False
        
        credential = ChainedTokenCredential(
            EnvironmentCredential(),
            AzureCliCredential(),
            VisualStudioCodeCredential(),
            ManagedIdentityCredential(),
        )
        project_client = AIProjectClient(
            credential=credential,
            endpoint=project_endpoint,
        )
        
        # Get Application Insights connection string from the project
        connection_string = project_client.telemetry.get_application_insights_connection_string()
        
        if not connection_string:
            logger.warning("No Application Insights connected to project - tracing disabled")
            return False
        
        logger.info(f"Retrieved Application Insights connection string from project")
        
        # Enable content recording for debugging (disable in production)
        # This captures prompts and responses in traces
        os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"
        
        # Enable Azure SDK tracing with OpenTelemetry
        settings.tracing_implementation = "opentelemetry"
        
        # Configure Azure Monitor with Application Insights
        configure_azure_monitor(
            connection_string=connection_string,
            enable_live_metrics=True
        )
        
        # Instrument OpenAI SDK for tracing
        try:
            from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
            if os.environ.get("OTEL_OPENAI_INSTRUMENTED") != "true":
                OpenAIInstrumentor().instrument()
                os.environ["OTEL_OPENAI_INSTRUMENTED"] = "true"
                logger.info("OpenAI SDK instrumentation enabled")
            else:
                logger.info("OpenAI SDK already instrumented; skipping")
        except ImportError as e:
            logger.warning(
                f"opentelemetry-instrumentation-openai-v2 not installed - OpenAI calls won't be traced: {e}"
            )
        
        os.environ["OTEL_CONFIGURED"] = "true"
        logger.info("OpenTelemetry tracing configured successfully")
        return True
    except ImportError as e:
        logger.warning(f"Tracing packages not installed: {e}")
        return False
    except Exception as e:
        import traceback
        logger.warning(f"Failed to configure tracing: {e}")
        logger.debug(f"Tracing setup traceback: {traceback.format_exc()}")
        return False

# Initialize tracing early
tracing_enabled = setup_tracing()

logger.info("Loading configuration modules...")
from config import AzureConfig, MARKET_OPTIONS, RISK_CATEGORIES
from agent import CompanyRiskAgent, get_company_risk_analysis_prompt
logger.info("Configuration modules loaded successfully")

logger.info(f"Environment loaded. Project endpoint: {os.getenv('AZURE_AI_PROJECT_ENDPOINT', 'NOT SET')[:50]}...")
logger.info(f"Tracing enabled: {tracing_enabled}")

# MCP Server Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
MCP_SERVER_KEY = os.getenv("MCP_SERVER_KEY", "")


def render_mermaid(mermaid_code: str, height: int = 400):
    """Render a Mermaid diagram using streamlit components"""
    import base64
    
    # Clean up the mermaid code
    mermaid_code = mermaid_code.strip()
    
    # Encode the mermaid code for the URL
    graphbytes = mermaid_code.encode("utf-8")
    base64_bytes = base64.b64encode(graphbytes)
    base64_string = base64_bytes.decode("ascii")
    
    # Use mermaid.ink service to render the diagram
    img_url = f"https://mermaid.ink/img/{base64_string}"
    
    st.image(img_url, use_container_width=True)


def init_session_state():
    """Initialize session state variables"""
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = []
    if "mcp_results" not in st.session_state:
        st.session_state.mcp_results = []
    if "rest_api_results" not in st.session_state:
        st.session_state.rest_api_results = []
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
                logger.info(f"Starting analysis for company: {company_name}, market: {market}")
                try:
                    result = await agent.analyze_company(
                        prompt=prompt,
                        market=market,
                        count=count,
                        freshness=freshness,
                    )
                    logger.info(f"Analysis completed successfully for {company_name}")
                    return result
                except Exception as e:
                    import traceback
                    logger.error(f"Error in do_analysis for {company_name}: {str(e)}")
                    logger.error(f"Full traceback:\n{traceback.format_exc()}")
                    raise
                
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
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"❌ Error during analysis for {company_name}: {str(e)}")
            logger.error(f"Full exception traceback:\n{error_trace}")
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
    logger.info("Initializing session state...")
    init_session_state()
    logger.info("Session state initialized")
    
    # Render sidebar and get config
    logger.info("Rendering sidebar...")
    config = render_sidebar()
    logger.info(f"Sidebar rendered. Config valid: {st.session_state.config_valid}")
    
    # Create tabs - NEW: Added Scenario 3 tab
    logger.info("Creating application tabs...")
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 Scenario 1: Direct Agent", 
        "🔗 Scenario 2: Agent → MCP Agent",
        "🌐 Scenario 3: MCP → REST API",
        "📊 Market Comparison", 
        "📖 Documentation"
    ])
    
    with tab1:
        render_direct_agent_scenario(config)
        
    with tab2:
        render_mcp_agent_scenario(config)
    
    with tab3:
        render_rest_api_scenario(config)
        
    with tab4:
        render_comparison_tab()
        
    with tab5:
        render_documentation_tab()


def render_direct_agent_scenario(config: AzureConfig):
    """Render Scenario 1: Direct Agent with Bing Tool"""
    st.header("🎯 Scenario 1: Direct Agent with Bing Tool")
    
    # Architecture explanation with Mermaid
    st.markdown("""
    **Architecture:** User → AI Agent (with Bing Grounding Tool attached directly)
    
    In this scenario, you pass the **market parameter explicitly** when configuring the tool.
    The market dropdown below directly controls the `BingGroundingSearchConfiguration.market` value.
    """)
    
    # Mermaid diagram for Scenario 1
    with st.expander("📊 Architecture Diagram (Mermaid)", expanded=True):
        mermaid_code = """
sequenceDiagram
    participant U as 👤 User
    participant App as 🖥️ Streamlit App
    participant Agent as 🤖 AI Agent
    participant Tool as 🔧 Bing Tool
    participant Bing as 🌐 Bing Search API
    
    U->>App: Enter company + Select market (de-DE)
    App->>App: Create BingGroundingSearchConfiguration<br/>with market="de-DE"
    App->>Agent: Create Agent with Bing Tool
    App->>Agent: Send analysis prompt
    Agent->>Tool: Invoke Bing search
    Tool->>Bing: Search with market=de-DE
    Bing-->>Tool: German-localized results
    Tool-->>Agent: Search results
    Agent-->>App: Analysis response
    App-->>U: Display results
        """
        render_mermaid(mermaid_code, height=420)
        
        st.caption("💡 The market parameter is set **at tool creation time**, before the agent processes the request.")
    
    # Data flow explanation
    st.subheader("🔄 Market Parameter Flow")
    
    col_flow1, col_flow2, col_flow3 = st.columns(3)
    
    with col_flow1:
        st.markdown("""
        **Step 1: User Selection**
        ```
        Market Dropdown → "de-DE"
        ```
        """)
        
    with col_flow2:
        st.markdown("""
        **Step 2: Tool Configuration**
        ```python
        BingGroundingSearchConfiguration(
            market="de-DE",  # From dropdown
            ...
        )
        ```
        """)
        
    with col_flow3:
        st.markdown("""
        **Step 3: Agent Creation**
        ```python
        agent = create_agent(
            tools=[bing_tool]  # Tool has market
        )
        ```
        """)
    
    st.divider()
    
    # Main content with explicit market control
    render_main_content(config)


def render_mcp_agent_scenario(config: AzureConfig):
    """Render Scenario 2: Agent calling another Agent via MCP"""
    st.header("🔗 Scenario 2: Agent → MCP Server (Another Agent)")
    
    st.markdown("""
    **Architecture:** User → Agent 1 (Orchestrator) → MCP Server → Agent 2 (Bing Tool)
    
    In this scenario, the **market parameter flows through the entire chain**:
    User Selection → MCP Tool Arguments → Agent 2 Tool Configuration
    """)
    
    # Mermaid diagram for Scenario 2
    with st.expander("📊 Architecture Diagram (Mermaid)", expanded=True):
        mermaid_code = """
sequenceDiagram
    participant U as 👤 User
    participant App as 🖥️ Streamlit App
    participant A1 as 🤖 Agent 1<br/>(Orchestrator)
    participant MCP as 🔌 MCP Server
    participant A2 as 🤖 Agent 2<br/>(Bing Agent)
    participant Bing as 🌐 Bing API
    
    U->>App: Enter company + Select market (de-DE)
    App->>MCP: MCP tools/call<br/>{"name": "analyze_company_risk",<br/>"arguments": {"market": "de-DE"}}
    
    Note over MCP: MCP Server extracts<br/>market from arguments
    
    MCP->>A2: Create Agent with<br/>BingTool(market="de-DE")
    A2->>Bing: Search with market=de-DE
    Bing-->>A2: German-localized results
    A2-->>MCP: Analysis response
    MCP-->>App: MCP result
    App-->>U: Display results
        """
        render_mermaid(mermaid_code, height=420)
        
        st.caption("💡 The market parameter is passed **as an MCP tool argument** and used to dynamically create the Bing tool.")
    
    # Data flow explanation
    st.subheader("🔄 Market Parameter Flow")
    
    col_flow1, col_flow2, col_flow3, col_flow4 = st.columns(4)
    
    with col_flow1:
        st.markdown("""
        **Step 1: User**
        ```
        Dropdown → "de-DE"
        ```
        """)
        
    with col_flow2:
        st.markdown("""
        **Step 2: MCP Call**
        ```json
        {
          "market": "de-DE"
        }
        ```
        """)
        
    with col_flow3:
        st.markdown("""
        **Step 3: MCP Server**
        ```python
        market = args["market"]
        ```
        """)
        
    with col_flow4:
        st.markdown("""
        **Step 4: Bing Tool**
        ```python
        market="de-DE"
        ```
        """)
    
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


def render_rest_api_scenario(config: AzureConfig):
    """Render Scenario 3: Agent with Custom MCP Tool calling Bing REST API"""
    st.header("🌐 Scenario 3: Agent → Custom MCP Tool → Bing REST API")
    
    st.markdown("""
    **Architecture:** User → **AI Agent (with MCP Tool)** → MCP Server → Bing REST API
    
    In this scenario:
    1. We create an **AI Foundry Agent** with a **custom MCP tool** attached
    2. The agent decides when to call the MCP tool based on the user's query
    3. The MCP tool calls the **Bing Grounding REST API directly** (not via another agent)
    4. Results flow back through the agent to the user
    
    This demonstrates the full MCP integration pattern with REST API backend.
    """)
    
    # Important note about network accessibility
    st.warning("""
    ⚠️ **Important**: Azure AI Foundry agents need to connect to MCP servers over the internet.
    
    **For Scenario 3 to work:**
    - ✅ Use **devtunnel** (Microsoft's tool) or ngrok to expose localhost
    - ✅ Deploy your MCP server to Azure (Functions, Container Apps, Web Apps)
    - ❌ `localhost:8000` will NOT work (agent is in Azure, can't reach your machine)
    
    **Quick Test with devtunnel (Recommended):**
    ```bash
    # Create tunnel (one-time setup)
    devtunnel create --allow-anonymous
    devtunnel port create <tunnel-id> -p 8000
    
    # Start tunnel daily
    devtunnel host <tunnel-id>
    
    # Copy the URL shown (NOT the inspect URL): https://tunnel-id.devtunnels.ms/mcp
    ```
    
    📚 See [docs/devtunnel-quick-start.md](../docs/devtunnel-quick-start.md) for complete setup guide with code examples for all scenarios.
    """)
    
    # Mermaid diagram for Scenario 3
    with st.expander("📊 Architecture Diagram (Mermaid)", expanded=True):
        mermaid_code = """
sequenceDiagram
    participant U as 👤 User
    participant App as 🖥️ Streamlit App
    participant Agent as 🤖 AI Agent<br/>(with MCP Tool)
    participant MCP as 🔌 MCP Server
    participant REST as 🌐 Bing REST API
    
    U->>App: Enter company + Select market (de-DE)
    App->>Agent: Create Agent with MCPTool<br/>pointing to MCP Server
    App->>Agent: Send user query
    
    Note over Agent: Agent decides to<br/>call MCP tool
    
    Agent->>MCP: Call bing_search_rest_api tool<br/>{"query": "...", "market": "de-DE"}
    
    Note over MCP: MCP tool calls<br/>REST API directly
    
    MCP->>REST: POST /openai/v1/responses<br/>with bing_grounding config
    REST-->>MCP: Grounded search results
    MCP-->>Agent: Tool response
    Agent-->>App: Agent response with citations
    App-->>U: Display results
        """
        render_mermaid(mermaid_code, height=500)
        
        st.caption("💡 **Key Point**: The Agent has an MCP Tool attached and calls it. The MCP Tool then calls Bing REST API directly.")
    
    # Compare all scenarios
    st.subheader("🔄 Architecture Comparison")
    
    col_s1, col_s2, col_s3 = st.columns(3)
    
    with col_s1:
        st.markdown("""
        **Scenario 1: Direct**
        ```
        User
        └── Agent
            └── Bing Tool (SDK)
                └── Bing API
        ```
        ⚡ Simplest
        """)
    
    with col_s2:
        st.markdown("""
        **Scenario 2: MCP → Agent**
        ```
        User
        └── MCP Server
            └── Agent (created)
                └── Bing Tool
        ```
        🔧 Agent per request
        """)
        
    with col_s3:
        st.markdown("""
        **Scenario 3: Agent → MCP**
        ```
        User
        └── Agent (MCP Tool)
            └── MCP Server
                └── REST API
        ```
        🎯 Custom MCP backend
        """)
    
    st.divider()
    
    # Configuration
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🔌 MCP Server Configuration")
        
        mcp_url = st.text_input(
            "MCP Server URL (must be publicly accessible)",
            value="https://your-tunnel-id.devtunnels.ms/mcp",
            key="s3_mcp_url",
            help="Use devtunnel or Azure-deployed MCP server URL. localhost:8000 will NOT work!"
        )
        
    with col2:
        st.subheader("🔍 Connection Test")
        if st.button("Test MCP Connection", key="s3_test_conn"):
            with st.spinner("Testing connection..."):
                success, message = test_mcp_connection(mcp_url, "")
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    st.divider()
    
    # Analysis inputs
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        company_name = st.text_input(
            "Company Name",
            placeholder="Enter company name (e.g., 'Tesla', 'Volkswagen')",
            key="s3_company",
            help="The agent will use the MCP tool to search for this company"
        )
        
    with col_b:
        market_selection = st.selectbox(
            "Market/Region",
            options=list(MARKET_OPTIONS.keys()),
            index=0,
            key="s3_market",
            help="Market parameter passed to the MCP tool"
        )
    
    # Get market code
    market_code = None
    market_config = MARKET_OPTIONS.get(market_selection)
    if market_config:
        market_code = market_config.code
    
    # Show the agent configuration
    st.subheader("📝 Agent with MCP Tool Configuration")
    
    agent_config = {
        "agent": {
            "model": "gpt-4o",
            "instructions": "You are a risk analysis assistant. Use the available MCP tools to search for company information.",
            "tools": [
                {
                    "type": "mcp",
                    "server_label": "bing-rest-api-mcp",
                    "server_url": mcp_url,
                    "allowed_tools": ["bing_search_rest_api", "analyze_company_risk_rest_api"]
                }
            ]
        },
        "query": f"Analyze risks for {company_name or '<company>'} in the {market_code or 'en-US'} market"
    }
    
    with st.expander("View Agent + MCP Tool Configuration", expanded=False):
        st.json(agent_config)
    
    st.info(f"""
    **Data Flow (Scenario 3):**
    1. Create AI Agent with **MCPTool** pointing to `{mcp_url}`
    2. Send query: "Analyze risks for {company_name or '<company>'}"
    3. Agent decides to call `bing_search_rest_api` MCP tool
    4. MCP Server receives tool call, builds REST API request
    5. REST API executes Bing grounding search
    6. Results flow back: REST API → MCP → Agent → User
    """)
    
    st.divider()
    
    # Run button
    run_disabled = not st.session_state.config_valid or not company_name
    
    if st.button(
        "🤖 Run Agent with MCP Tool (Scenario 3)",
        type="primary",
        disabled=run_disabled,
        key="s3_run",
        use_container_width=True
    ):
        run_agent_with_mcp_tool(config, mcp_url, company_name, market_code)
    
    if run_disabled and not company_name:
        st.warning("Please enter a company name to analyze")
    
    # Display results
    if st.session_state.rest_api_results:
        st.divider()
        st.subheader("📊 Agent + MCP Tool Results (Scenario 3)")
        
        for i, result in enumerate(reversed(st.session_state.rest_api_results)):
            with st.expander(
                f"[Agent→MCP] {result['company']} | Market: {result['market']} | {result['timestamp']}",
                expanded=(i == 0)
            ):
                st.caption("**Route:** User → Agent (MCP Tool) → MCP Server → Bing REST API")
                
                # Show agent info
                if result.get('agent_id'):
                    st.caption(f"**Agent ID:** {result.get('agent_id')}")
                
                # Show MCP tool call
                st.caption("**MCP Tool Called by Agent:**")
                st.code(f"""
MCP Server: {result.get('mcp_url', mcp_url)}
Tool: bing_search_rest_api
Query: "{result.get('query', '')}"
Market: "{result['market']}"
                """)
                
                # Results
                st.markdown("---")
                st.markdown("**Agent Response:**")
                st.markdown(result.get('text', 'No response'))
                
                # Citations
                citations = result.get('citations', [])
                if citations:
                    st.markdown("---")
                    st.caption("**Sources:**")
                    for citation in citations:
                        url = citation.get('url', '')
                        title = citation.get('title', url)
                        st.markdown(f"- [{title}]({url})")


def run_agent_with_mcp_tool(config: AzureConfig, mcp_url: str, company_name: str, market: str):
    """
    Run Scenario 3: Create an Agent with MCP Tool that calls our custom MCP server.
    
    The MCP server then calls the Bing REST API directly.
    """
    import datetime
    
    with st.spinner(f"Creating Agent with MCP Tool for {company_name}..."):
        try:
            # Run the async agent creation and execution
            async def do_agent_with_mcp():
                from azure.identity import (
                    AzureCliCredential,
                    VisualStudioCodeCredential,
                    EnvironmentCredential,
                    ManagedIdentityCredential,
                    ChainedTokenCredential,
                )
                from azure.ai.projects import AIProjectClient
                from azure.ai.projects.models import PromptAgentDefinition, MCPTool
                
                logger.info(f"Starting Scenario 3: Agent with MCP Tool for {company_name}")
                
                credential = ChainedTokenCredential(
                    EnvironmentCredential(),
                    AzureCliCredential(),
                    VisualStudioCodeCredential(),
                    ManagedIdentityCredential(),
                )
                
                project_client = AIProjectClient(
                    endpoint=config.project_endpoint,
                    credential=credential,
                )
                
                openai_client = project_client.get_openai_client()
                
                # Create MCP Tool pointing to our custom MCP server
                # The MCP server has tools like bing_search_rest_api that call Bing REST API
                mcp_tool = MCPTool(
                    server_label="bing_rest_api_mcp",
                    server_url=mcp_url,
                    require_approval="never",  # Auto-approve for demo
                    allowed_tools=["bing_search_rest_api", "bing_grounded_search", "list_supported_markets"],
                )
                
                logger.info(f"Created MCP Tool pointing to: {mcp_url}")
                
                # Create agent with the MCP tool
                agent = project_client.agents.create_version(
                    agent_name="CompanyRiskAnalyst-MCP",
                    definition=PromptAgentDefinition(
                        model=config.model_deployment_name,
                        instructions=f"""You are a company risk analysis assistant. 
You have access to an MCP tool that can search the web using Bing.

When asked to analyze a company, use the bing_search_rest_api tool to search for:
- Recent news and controversies
- Legal issues and lawsuits  
- Regulatory violations
- ESG concerns

Always include the market parameter '{market or "en-US"}' in your searches for localized results.

Provide a comprehensive risk assessment based on the search results.""",
                        tools=[mcp_tool],
                    ),
                    description="Agent with custom MCP tool for Bing REST API search",
                )
                
                logger.info(f"Created agent: {agent.id}, {agent.name}, version {agent.version}")
                
                try:
                    # Build the query
                    query = f"Search for and analyze any risks, controversies, legal issues, or ESG concerns related to {company_name}. Use the market {market or 'en-US'} for the search."
                    
                    # Call the agent
                    response = openai_client.responses.create(
                        input=query,
                        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
                    )
                    
                    logger.info(f"Got response from agent")
                    
                    # Extract results
                    result = {
                        "company": company_name,
                        "market": market or "en-US",
                        "query": query,
                        "mcp_url": mcp_url,
                        "agent_id": agent.id,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "text": response.output_text if hasattr(response, 'output_text') else str(response),
                        "citations": [],
                    }
                    
                    # Try to extract citations
                    if hasattr(response, 'output') and response.output:
                        for output_item in response.output:
                            if hasattr(output_item, 'content'):
                                for content in output_item.content:
                                    if hasattr(content, 'annotations'):
                                        for annotation in content.annotations:
                                            if hasattr(annotation, 'url'):
                                                result["citations"].append({
                                                    "url": annotation.url,
                                                    "title": getattr(annotation, 'title', annotation.url),
                                                })
                    
                    return result
                    
                finally:
                    # Clean up the agent
                    project_client.agents.delete_version(
                        agent_name=agent.name,
                        agent_version=agent.version,
                    )
                    logger.info(f"Deleted agent: {agent.name}")
            
            # Run the async function
            result = asyncio.run(do_agent_with_mcp())
            
            # Store result
            st.session_state.rest_api_results.append(result)
            
            st.success(f"✅ Agent with MCP Tool completed for {company_name}")
            st.rerun()
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"❌ Error in Scenario 3: {str(e)}")
            logger.error(f"Traceback:\n{error_trace}")
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)


def render_documentation_tab():
    """Render the documentation tab"""
    st.header("📖 Documentation")
    
    # Main architecture comparison with Mermaid
    st.subheader("🏗️ Architecture Comparison")
    
    st.markdown("""
### Scenario 1: Direct Agent with Bing Tool
    """)
    mermaid_s1 = """
flowchart LR
    subgraph User["👤 User Interface"]
        A[Company Input] --> B[Market Dropdown]
    end
    
    subgraph App["🖥️ Application"]
        C[Create Tool Config<br/>market from dropdown]
        D[Create Agent<br/>with Bing Tool]
    end
    
    subgraph Agent["🤖 AI Foundry Agent"]
        E[GPT-4o Model]
        F[Bing Tool<br/>market=user_selection]
    end
    
    subgraph Bing["🌐 Bing Search"]
        G[Search API<br/>market-localized]
    end
    
    B --> C --> D --> E
    E --> F --> G
    G --> E --> App --> User
    
    style B fill:#90EE90
    style F fill:#90EE90
    """
    render_mermaid(mermaid_s1, height=420)

    st.markdown("""
### Scenario 2: Agent → MCP Server (Agent-to-Agent)
    """)
    mermaid_s2 = """
flowchart LR
    subgraph User["👤 User Interface"]
        A[Company Input] --> B[Market Dropdown]
    end
    
    subgraph App["🖥️ Application"]
        C[Build MCP Call<br/>market in arguments]
    end
    
    subgraph MCP["🔌 MCP Server"]
        D[Receive MCP Request]
        E[Extract market<br/>from arguments]
        F[Create Bing Tool<br/>with market]
        G[🤖 Agent 2]
    end
    
    subgraph Bing["🌐 Bing Search"]
        H[Search API<br/>market-localized]
    end
    
    B --> C -->|"market: de-DE"| D --> E --> F --> G --> H
    H --> G --> MCP --> App --> User
    
    style B fill:#90EE90
    style E fill:#90EE90
    style F fill:#90EE90
    """
    render_mermaid(mermaid_s2, height=420)
    
    st.markdown("""
### Scenario 3: MCP Tool → Bing REST API (Direct)
    """)
    mermaid_s3 = """
flowchart LR
    subgraph User["👤 User Interface"]
        A[Company Input] --> B[Market Dropdown]
    end
    
    subgraph App["🖥️ Application"]
        C[Build MCP Call<br/>with REST API tool]
    end
    
    subgraph MCP["🔌 MCP Server"]
        D[Receive MCP Request]
        E[Build REST API<br/>request payload]
        F[bing_grounding<br/>tool config]
    end
    
    subgraph REST["🌐 REST API"]
        G[POST /openai/responses]
        H[Bing Grounding<br/>Search]
    end
    
    B --> C -->|"market: de-DE"| D --> E --> F --> G --> H
    H --> G --> MCP --> App --> User
    
    style B fill:#FFD700
    style E fill:#FFD700
    style F fill:#FFD700
    style G fill:#FFD700
    """
    render_mermaid(mermaid_s3, height=420)
    
    st.divider()
    
    # Scenario comparison table
    st.subheader("🔄 Scenario Comparison")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### Scenario 1: Direct Agent
        
        | Aspect | Detail |
        |--------|--------|
        | **Architecture** | User → Agent (Bing Tool) |
        | **Market Config** | At tool creation time |
        | **Latency** | Low (single agent) |
        | **Complexity** | Simple |
        
        **Market Parameter Flow:**
        ```
        User Dropdown → Tool Config → Bing API
        ```
        
        **Best For:**
        - Single-purpose agents
        - Direct Bing search needs
        - Lower latency requirements
        """)
        
    with col2:
        st.markdown("""
        ### Scenario 2: Agent → MCP Agent
        
        | Aspect | Detail |
        |--------|--------|
        | **Architecture** | User → MCP → Agent (Bing) |
        | **Market Config** | As MCP argument |
        | **Latency** | Higher (MCP + agent) |
        | **Complexity** | Moderate |
        
        **Market Parameter Flow:**
        ```
        User Dropdown → MCP Args → Tool Config → Bing
        ```
        
        **Best For:**
        - Multi-agent systems
        - Shared tool infrastructure
        - Decoupled architectures
        """)
    
    with col3:
        st.markdown("""
        ### Scenario 3: Agent → MCP → REST
        
        | Aspect | Detail |
        |--------|--------|
        | **Architecture** | User → Agent (MCP Tool) → REST |
        | **Market Config** | Via MCP tool |
        | **Latency** | Moderate (agent + MCP) |
        | **Complexity** | Advanced |
        
        **Market Parameter Flow:**
        ```
        User → Agent → MCP Tool → REST API
        ```
        
        **Best For:**
        - Custom MCP backends
        - Direct REST API control
        - Full agent + MCP integration
        """)
    
    st.divider()
    
    # Market parameter flow detail
    st.subheader("📊 Market Parameter Flow (Detailed)")
    
    st.markdown("""
### Sequence Diagram: How Market Flows in Each Scenario
    """)
    mermaid_seq1 = """
sequenceDiagram
    box Scenario 1: Direct Agent
        participant U1 as 👤 User
        participant A1 as 🖥️ App
        participant T1 as 🔧 Bing Tool
        participant B1 as 🌐 Bing API
    end
    
    U1->>A1: Select market="de-DE"
    A1->>A1: BingGroundingSearchConfiguration(market="de-DE")
    A1->>T1: Create tool with config
    T1->>B1: Search (market=de-DE)
    B1-->>U1: German results
    
    Note over U1,B1: Market is set at TOOL CREATION
    """
    render_mermaid(mermaid_seq1, height=360)

    mermaid_seq2 = """
sequenceDiagram
    box Scenario 2: Agent → MCP Agent
        participant U2 as 👤 User
        participant A2 as 🖥️ App
        participant M2 as 🔌 MCP Server
        participant T2 as 🔧 Bing Tool
        participant B2 as 🌐 Bing API
    end
    
    U2->>A2: Select market="de-DE"
    A2->>M2: MCP call: {arguments: {market: "de-DE"}}
    M2->>M2: Extract market from arguments
    M2->>T2: BingGroundingSearchConfiguration(market=args.market)
    T2->>B2: Search (market=de-DE)
    B2-->>U2: German results
    
    Note over U2,B2: Market is PASSED AS ARGUMENT then used at tool creation
    """
    render_mermaid(mermaid_seq2, height=360)
    
    mermaid_seq3 = """
sequenceDiagram
    box Scenario 3: Agent → MCP → REST (Direct)
        participant U3 as 👤 User
        participant A3 as 🖥️ App
        participant AG as 🤖 Agent<br/>(MCP Tool)
        participant M3 as 🔌 MCP Server
        participant R3 as 🌐 REST API
    end
    
    U3->>A3: Select market="de-DE"
    A3->>AG: Create Agent with MCPTool
    AG->>M3: Call bing_search_rest_api (market: "de-DE")
    M3->>M3: Build REST payload
    M3->>R3: POST /openai/v1/responses
    R3->>R3: Execute Bing grounding search
    R3-->>M3: JSON response with citations
    M3-->>AG: Tool response
    AG-->>U3: Agent response with results
    
    Note over U3,R3: Agent calls MCP Tool → MCP calls REST API directly
    """
    render_mermaid(mermaid_seq3, height=360)
    
    st.divider()
    
    # Code examples
    st.subheader("💻 Code Examples")
    
    st.markdown("""
### How Market Flows in Each Scenario
    
#### Scenario 1 (Direct) - Market at Tool Creation
```python
# User selects market from dropdown
market = "de-DE"  # From st.selectbox

# Market set at tool creation time - BEFORE agent processes request
bing_tool = BingGroundingTool(
    bing_grounding_search=BingGroundingSearchConfiguration(
        connection_id=connection_id,
        market=market,  # ← EXPLICIT from user selection
        count=10,
        freshness="Month"
    )
)

# Create agent with pre-configured tool
agent = create_agent(
    model="gpt-4o",
    tools=[bing_tool]  # Tool already has market set
)

# Run the agent
response = agent.run(prompt)
```

#### Scenario 2 (MCP) - Market as Tool Argument
```python
# User selects market from dropdown
market = "de-DE"  # From st.selectbox

# Market passed as MCP tool argument
mcp_request = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "analyze_company_risk",
        "arguments": {
            "company_name": "Tesla",
            "market": market  # ← EXPLICIT from user, passed to MCP
        }
    }
}

# MCP Server receives and extracts market
# Then creates tool dynamically with that market
def handle_mcp_call(arguments):
    market = arguments.get("market", "en-US")  # Extract from args
    
    bing_tool = BingGroundingTool(
        bing_grounding_search=BingGroundingSearchConfiguration(
            market=market,  # ← From MCP arguments
        )
    )
    # Create agent and run...
```

#### Scenario 3 (REST API) - Direct API Call (No Agent)
```python
# User selects market from dropdown
market = "de-DE"  # From st.selectbox

# MCP tool receives and makes direct REST API call
# NO AGENT IS CREATED - just a direct HTTP request!

import httpx

# Get access token and connection ID
access_token = credential.get_token("https://ai.azure.com/.default").token
connection_id = project_client.connections.get(bing_connection_name).id

# Build REST API request
url = f"{project_endpoint}/openai/responses?api-version=2025-05-01-preview"
payload = {
    "model": "gpt-4o",
    "input": "Tesla risks controversies legal issues",
    "tool_choice": "required",
    "tools": [
        {
            "type": "bing_grounding",
            "bing_grounding": {
                "search_configurations": [
                    {
                        "project_connection_id": connection_id,
                        "count": 7,
                        "market": market,  # ← Direct in REST payload
                        "freshness": "month"
                    }
                ]
            }
        }
    ]
}

# Make direct REST call - no agent lifecycle!
async with httpx.AsyncClient() as client:
    response = await client.post(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload
    )
    result = response.json()
    # Result contains output_text and citations
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


# Streamlit runs the script top-to-bottom on each interaction
# We only need to call main() once at module level
main()
