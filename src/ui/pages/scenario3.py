"""
Scenario 3 UI page: Agent with MCP Tool calling REST API.
"""
import streamlit as st
import asyncio
import datetime
from infrastructure import AzureConfig, AzureClientFactory, MARKET_OPTIONS
from services import RiskAnalyzer
from scenarios import MCPRestAPIScenario
from core.models import CompanyRiskRequest, SearchConfig, ScenarioType


def render_scenario3(config: AzureConfig):
    """Render Scenario 3: Agent → MCP Tool → REST API."""
    st.header("🌐 Scenario 3: Agent → MCP Tool → REST API")
    
    st.markdown("""
    **Architecture:** User → AI Agent (MCP Tool) → MCP Server → Bing REST API
    
    Agent has MCP tool attached, which calls Bing REST API directly.
    """)
    
    st.warning("""
    ⚠️ **Important**: Azure AI Foundry agents need public MCP server URLs.
    Use **devtunnel** or deploy to Azure.
    """)
    
    st.divider()
    
    # MCP URL
    mcp_url = st.text_input(
        "MCP Server URL (must be publicly accessible)",
        value="https://your-tunnel-id.devtunnels.ms/mcp",
        key="s3_mcp_url"
    )
    
    # Input form
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company_name = st.text_input(
            "Company Name",
            placeholder="Enter company name",
            key="s3_company"
        )
    
    with col_b:
        market_selection = st.selectbox(
            "Market/Region",
            options=list(MARKET_OPTIONS.keys()),
            index=0,
            key="s3_market"
        )
    
    market_code = None
    market_config = MARKET_OPTIONS.get(market_selection)
    if market_config:
        market_code = market_config.code
    
    # Run button
    run_disabled = not st.session_state.config_valid or not company_name
    
    if st.button(
        "🤖 Run Agent with MCP Tool",
        type="primary",
        disabled=run_disabled,
        key="s3_run",
        use_container_width=True
    ):
        run_scenario3_analysis(config, mcp_url, company_name, market_code)
    
    # Display results
    if st.session_state.rest_api_results:
        st.divider()
        st.subheader("📊 Results")
        
        for i, result in enumerate(reversed(st.session_state.rest_api_results)):
            with st.expander(
                f"[Agent→MCP→REST] {result['company']} | {result['timestamp']}",
                expanded=(i == 0)
            ):
                st.markdown(result.get('text', 'No response'))
                
                if result.get('citations'):
                    st.markdown("---")
                    st.caption("**Sources:**")
                    for citation in result['citations']:
                        st.markdown(f"- [{citation['title']}]({citation['url']})")


def run_scenario3_analysis(
    config: AzureConfig,
    mcp_url: str,
    company_name: str,
    market: str
):
    """Run Scenario 3 analysis."""
    with st.spinner(f"Creating Agent with MCP Tool for {company_name}..."):
        try:
            async def do_analysis():
                client_factory = AzureClientFactory(config)
                risk_analyzer = RiskAnalyzer()
                scenario = MCPRestAPIScenario(
                    client_factory,
                    risk_analyzer,
                    config.model_deployment_name,
                    mcp_url
                )
                
                request = CompanyRiskRequest(
                    company_name=company_name,
                    search_config=SearchConfig(market=market),
                    scenario_type=ScenarioType.MCP_REST_API
                )
                
                return await scenario.execute(request)
            
            response = asyncio.run(do_analysis())
            
            st.session_state.rest_api_results.append({
                "company": company_name,
                "market": market,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "text": response.text,
                "citations": [{"url": c.url, "title": c.title} for c in response.citations],
                "agent_id": response.metadata.get("agent_id"),
                "mcp_url": mcp_url,
            })
            
            st.success(f"✅ Analysis complete")
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)
