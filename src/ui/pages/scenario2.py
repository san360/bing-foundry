"""
Scenario 2 UI page: Two-Agent Pattern via MCP.
"""
import sys
from pathlib import Path

# Add src to path (go up from pages -> ui -> src)
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import streamlit as st
import asyncio
import datetime
from infrastructure import AzureConfig, AzureClientFactory, MCPConfig, MARKET_OPTIONS
from services import RiskAnalyzer
from scenarios import MCPAgentScenario
from core.models import CompanyRiskRequest, SearchConfig, RiskCategory, ScenarioType


def render_scenario2(config: AzureConfig):
    """Render Scenario 2: Two-Agent Pattern via MCP."""
    st.header("🔗 Scenario 2: Two-Agent Pattern via MCP")
    
    st.markdown("""
    **Architecture:** Orchestrator Agent → MCP Tool → Worker Agent (ephemeral)

    **Key:** Worker Agents are ephemeral - created per-request and deleted after use.
    """)

    with st.expander("📐 View Workflow Architecture", expanded=False):
        st.code("""
  User        Streamlit App    Orchestrator     MCP Server      Worker Agent     Bing API
   │               │               │               │                │              │
   │ company+mkt   │               │               │                │              │
   │──────────────>│               │               │                │              │
   │               │ risk request  │               │                │              │
   │               │──────────────>│               │                │              │
   │               │               │ create_and_   │                │              │
   │               │               │ run_bing_agent│                │              │
   │               │               │──────────────>│                │              │
   │               │               │               │ Create agent   │              │
   │               │               │               │───────────────>│              │
   │               │               │               │                │ Grounded     │
   │               │               │               │                │ search       │
   │               │               │               │                │─────────────>│
   │               │               │               │                │ Results      │
   │               │               │               │                │<─────────────│
   │               │               │               │ Search results │              │
   │               │               │               │<───────────────│              │
   │               │               │               │ Delete worker  │              │
   │               │               │ JSON+citations│                │              │
   │               │               │<──────────────│                │              │
   │               │ Final analysis│               │                │              │
   │               │<──────────────│               │                │              │
   │ Risk report   │               │               │                │              │
   │<──────────────│               │               │                │              │
        """, language=None)

        st.markdown("""
**Flow:**
1. **Orchestrator Agent (Agent 1)** receives the request
2. Orchestrator calls MCP tool `create_and_run_bing_agent` with market config
3. MCP Server creates **Worker Agent (Agent 2)** with specified market
4. Worker Agent executes Bing-grounded search
5. MCP Server **deletes** Worker Agent after getting results
6. Results flow back through Orchestrator to User
        """)

    st.divider()
    
    # MCP Configuration
    mcp_config = MCPConfig.from_env()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        mcp_url = st.text_input(
            "MCP Server URL",
            value=mcp_config.server_url,
            help="URL of the MCP server"
        )
    
    # Input form
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company_name = st.text_input(
            "Company Name",
            placeholder="Enter company name",
            key="mcp_company"
        )
    
    with col_b:
        market_selection = st.selectbox(
            "Market/Region",
            options=list(MARKET_OPTIONS.keys()),
            index=0,
            key="mcp_market"
        )
    
    market_code = None
    market_config = MARKET_OPTIONS.get(market_selection)
    if market_config:
        market_code = market_config.code
    
    # Run button
    if st.button(
        "🔍 Run Two-Agent Analysis",
        type="primary",
        disabled=not company_name,
        use_container_width=True
    ):
        run_scenario2_analysis(config, mcp_url, company_name, market_code)
    
    # Display results
    if st.session_state.mcp_results:
        st.divider()
        st.subheader("📊 Two-Agent Pattern Results")
        
        for i, result in enumerate(reversed(st.session_state.mcp_results)):
            with st.expander(
                f"[Two-Agent] {result['company']} | {result['timestamp']}",
                expanded=(i == 0)
            ):
                # Agent Information
                st.caption("**🤖 Orchestrator Agent (Agent 1 - Persistent):**")
                orc_col1, orc_col2 = st.columns(2)
                with orc_col1:
                    st.metric("Orchestrator Name", result.get('orchestrator_agent_name', 'BingFoundry-Orchestrator'))
                    if result.get('orchestrator_agent_id'):
                        st.code(result['orchestrator_agent_id'], language=None)
                with orc_col2:
                    st.metric("Orchestrator Version", result.get('orchestrator_agent_version', 'N/A'))

                # MCP Server Info
                st.caption("**🔧 MCP Server (Creates Worker Agents):**")
                st.info(f"MCP URL: {result.get('mcp_url', 'N/A')}")
                st.caption("ℹ️ Worker Agents are created, used, and deleted by the MCP Server automatically")
                
                st.markdown("---")
                st.caption("**📍 Route:** Orchestrator Agent → MCP Tool → Worker Agent (Bing) → Bing API → Delete Worker")
                st.markdown("---")
                st.markdown(result.get('response', 'No response'))


def run_scenario2_analysis(
    config: AzureConfig,
    mcp_url: str,
    company_name: str,
    market: str
):
    """Run Scenario 2 analysis."""
    with st.spinner(f"Calling MCP Server for {company_name}..."):
        try:
            async def do_analysis():
                client_factory = AzureClientFactory(config)
                risk_analyzer = RiskAnalyzer()
                scenario = MCPAgentScenario(
                    client_factory,
                    risk_analyzer,
                    mcp_url
                )
                
                request = CompanyRiskRequest(
                    company_name=company_name,
                    search_config=SearchConfig(market=market),
                    scenario_type=ScenarioType.MCP_AGENT_TO_AGENT
                )
                
                return await scenario.execute(request)
            
            response = asyncio.run(do_analysis())
            
            st.session_state.mcp_results.append({
                "company": company_name,
                "market": market,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "response": response.text,
                "orchestrator_agent_id": response.metadata.get("orchestrator_agent_id"),
                "orchestrator_agent_name": response.metadata.get("orchestrator_agent_name"),
                "orchestrator_agent_version": response.metadata.get("orchestrator_agent_version"),
                "mcp_url": response.metadata.get("mcp_url"),
            })
            
            st.success(f"✅ MCP Analysis complete")
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)
