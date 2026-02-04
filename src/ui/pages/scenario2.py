"""
Scenario 2 UI page: MCP Agent to Agent.
"""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import streamlit as st
import asyncio
import datetime
from src.infrastructure import AzureConfig, AzureClientFactory, MCPConfig, MARKET_OPTIONS
from src.services import RiskAnalyzer
from src.scenarios import MCPAgentScenario
from src.core.models import CompanyRiskRequest, SearchConfig, RiskCategory, ScenarioType


def render_scenario2(config: AzureConfig):
    """Render Scenario 2: MCP Agent to Agent."""
    st.header("🔗 Scenario 2: Agent → MCP Server → Agent")
    
    st.markdown("""
    **Architecture:** User → MCP Server → Agent 2 (with Bing Tool)
    
    Market parameter flows through MCP tool arguments.
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
        "🔍 Run via MCP",
        type="primary",
        disabled=not company_name,
        use_container_width=True
    ):
        run_scenario2_analysis(config, mcp_url, company_name, market_code)
    
    # Display results
    if st.session_state.mcp_results:
        st.divider()
        st.subheader("📊 MCP Results")
        
        for i, result in enumerate(reversed(st.session_state.mcp_results)):
            with st.expander(
                f"[MCP] {result['company']} | {result['timestamp']}",
                expanded=(i == 0)
            ):
                # Agent Information (created by MCP server)
                if result.get('agent_name'):
                    st.caption("**🤖 Agent Information (Created by MCP Server):**")
                    agent_col1, agent_col2, agent_col3 = st.columns(3)
                    with agent_col1:
                        st.metric("Agent Name", result.get('agent_name', 'N/A'))
                    with agent_col2:
                        st.metric("Version", result.get('agent_version', 'N/A'))
                    with agent_col3:
                        st.metric("Agent ID", result.get('agent_id', 'N/A')[:8] + '...' if result.get('agent_id') else 'N/A')
                    st.markdown("---")
                
                st.caption("**📍 Route:** User → MCP Server → Agent 2 (with Bing Tool) → Bing API")
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
                "agent_id": response.metadata.get("agent_id"),
                "agent_name": response.metadata.get("agent_name"),
                "agent_version": response.metadata.get("agent_version"),
            })
            
            st.success(f"✅ MCP Analysis complete")
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)
