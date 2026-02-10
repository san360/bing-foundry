"""
Scenario 4 UI page: Multi-Market Research Agent.
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
from infrastructure import AzureConfig, AzureClientFactory, MARKET_OPTIONS
from services import RiskAnalyzer
from scenarios.scenario4_multi_market import MultiMarketScenario
from core.models import CompanyRiskRequest, SearchConfig, ScenarioType


def render_scenario4(config: AzureConfig):
    """Render Scenario 4: Multi-Market Research."""
    st.header("🌍 Scenario 4: Multi-Market Research")
    
    st.markdown("""
    **Architecture:** User → AI Agent → MCP Tool (called for EACH market) → Aggregated Results

    Agent calls the MCP tool multiple times with different market parameters,
    then aggregates results into a comprehensive global analysis.
    """)

    with st.expander("📐 View Workflow Architecture", expanded=False):
        st.code("""
  User        Streamlit App     MultiMarket Agent    MCP Server      Bing REST API
   │               │                  │                  │                │
   │ en-US,de-DE,  │                  │                  │                │
   │ ja-JP         │                  │                  │                │
   │──────────────>│                  │                  │                │
   │               │ multi-market req │                  │                │
   │               │─────────────────>│                  │                │
   │               │                  │                  │                │
   │               │                  │  ┌─── Loop: for each market ───┐ │
   │               │                  │  │ bing_search_rest_api        │ │
   │               │                  │──│───────────────>│            │ │
   │               │                  │  │                │ REST call  │ │
   │               │                  │  │                │───────────>│ │
   │               │                  │  │                │ Results    │ │
   │               │                  │  │                │<───────────│ │
   │               │                  │  │ JSON+citations │            │ │
   │               │                  │<─│────────────────│            │ │
   │               │                  │  └────────────────────────────-┘ │
   │               │                  │                  │                │
   │               │                  │ Aggregate results│                │
   │               │ Cross-market     │                  │                │
   │               │<─────────────────│                  │                │
   │ Comparative   │                  │                  │                │
   │ report        │                  │                  │                │
   │<──────────────│                  │                  │                │
        """, language=None)

        st.markdown("""
**Note:** Markets are searched **sequentially** - one at a time. For parallel
execution with better fault tolerance, see Scenario 5.
        """)

    st.info("""
    💡 **Key Feature**: Select multiple markets and the agent will search each one separately,
    then provide a comparative analysis across all selected regions.
    """)

    st.divider()
    
    # MCP URL
    mcp_url = st.text_input(
        "MCP Server URL (must be publicly accessible)",
        value="https://your-tunnel-id.devtunnels.ms/mcp",
        key="s4_mcp_url"
    )
    
    # Input form
    company_name = st.text_input(
        "Company Name",
        placeholder="Enter company name (e.g., Microsoft, Tesla, Siemens)",
        key="s4_company"
    )
    
    # Multi-select for markets
    st.subheader("🗺️ Select Markets to Research")
    
    # Group markets by region for better UX
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption("**Americas**")
        americas_markets = {
            k: v for k, v in MARKET_OPTIONS.items() 
            if v and v.country in ["US", "CA", "MX", "BR"]
        }
        selected_americas = st.multiselect(
            "Americas",
            options=list(americas_markets.keys()),
            default=["United States (English)"] if "United States (English)" in americas_markets else [],
            key="s4_americas",
            label_visibility="collapsed"
        )
    
    with col2:
        st.caption("**Europe**")
        europe_markets = {
            k: v for k, v in MARKET_OPTIONS.items()
            if v and v.country in ["GB", "DE", "AT", "CH", "FR", "ES", "IT", "NL", "SE"]
        }
        selected_europe = st.multiselect(
            "Europe",
            options=list(europe_markets.keys()),
            default=[],
            key="s4_europe",
            label_visibility="collapsed"
        )
    
    with col3:
        st.caption("**Asia Pacific**")
        apac_markets = {
            k: v for k, v in MARKET_OPTIONS.items()
            if v and v.country in ["JP", "KR", "CN", "TW", "AU", "IN"]
        }
        selected_apac = st.multiselect(
            "Asia Pacific",
            options=list(apac_markets.keys()),
            default=[],
            key="s4_apac",
            label_visibility="collapsed"
        )
    
    # Combine all selected markets
    all_selected = selected_americas + selected_europe + selected_apac
    
    # Get market codes
    selected_market_codes = []
    for market_name in all_selected:
        market_config = MARKET_OPTIONS.get(market_name)
        if market_config:
            selected_market_codes.append(market_config.code)
    
    # Show selected markets summary
    if selected_market_codes:
        st.success(f"**Selected Markets ({len(selected_market_codes)}):** {', '.join(selected_market_codes)}")
    else:
        st.warning("Please select at least one market to search")
    
    st.divider()
    
    # Run button
    run_disabled = (
        not st.session_state.config_valid or 
        not company_name or 
        len(selected_market_codes) == 0
    )
    
    if st.button(
        f"🔍 Research in {len(selected_market_codes)} Market(s)",
        type="primary",
        disabled=run_disabled,
        key="s4_run",
        use_container_width=True
    ):
        run_scenario4_analysis(config, mcp_url, company_name, selected_market_codes)
    
    # Display results
    if st.session_state.multi_market_results:
        st.divider()
        st.subheader("📊 Multi-Market Results")
        
        for i, result in enumerate(reversed(st.session_state.multi_market_results)):
            markets_str = ", ".join(result.get('markets', []))
            with st.expander(
                f"[Multi-Market] {result['company']} | {len(result.get('markets', []))} markets | {result['timestamp']}",
                expanded=(i == 0)
            ):
                # Agent Information
                st.caption("**🤖 Agent Information:**")
                agent_col1, agent_col2, agent_col3 = st.columns(3)
                with agent_col1:
                    st.metric("Agent Name", result.get('agent_name', 'N/A'))
                with agent_col2:
                    st.metric("Agent Version", result.get('agent_version', 'N/A'))
                with agent_col3:
                    st.metric("Markets Searched", result.get('market_count', 0))
                
                # Markets searched
                st.info(f"**Markets Searched:** {markets_str}")
                
                st.caption("**📍 Route:** User → Agent → MCP Tool (×{count}) → Aggregated Analysis".format(
                    count=result.get('market_count', 0)
                ))
                st.markdown("---")
                
                # Analysis results
                st.markdown(result.get('text', 'No response'))
                
                # Citations
                if result.get('citations'):
                    st.markdown("---")
                    st.caption(f"**Sources ({len(result['citations'])} citations):**")
                    for citation in result['citations'][:20]:  # Limit to 20
                        st.markdown(f"- [{citation['title']}]({citation['url']})")
                    if len(result['citations']) > 20:
                        st.caption(f"... and {len(result['citations']) - 20} more")


def run_scenario4_analysis(
    config: AzureConfig,
    mcp_url: str,
    company_name: str,
    markets: list
):
    """Run Scenario 4 multi-market analysis."""
    with st.spinner(f"Researching {company_name} across {len(markets)} markets..."):
        try:
            async def do_analysis():
                client_factory = AzureClientFactory(config)
                risk_analyzer = RiskAnalyzer()
                scenario = MultiMarketScenario(
                    client_factory,
                    risk_analyzer,
                    config.model_deployment_name,
                    mcp_url
                )
                
                request = CompanyRiskRequest(
                    company_name=company_name,
                    search_config=SearchConfig(market=markets[0] if markets else "en-US"),
                    scenario_type=ScenarioType.MCP_REST_API
                )
                
                return await scenario.execute(request, markets=markets)
            
            response = asyncio.run(do_analysis())
            
            # Initialize results list if needed
            if 'multi_market_results' not in st.session_state:
                st.session_state.multi_market_results = []
            
            st.session_state.multi_market_results.append({
                "company": company_name,
                "markets": markets,
                "market_count": len(markets),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "text": response.text,
                "citations": [{"url": c.url, "title": c.title} for c in response.citations],
                "agent_id": response.metadata.get("agent_id"),
                "agent_name": response.metadata.get("agent_name"),
                "agent_version": response.metadata.get("agent_version"),
                "mcp_url": mcp_url,
            })
            
            st.success(f"✅ Multi-market analysis complete! Searched {len(markets)} markets.")
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
