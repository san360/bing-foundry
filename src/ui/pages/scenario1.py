"""
Scenario 1 UI page: Direct Agent with Bing Tool.
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
from src.infrastructure import AzureConfig, AzureClientFactory, MARKET_OPTIONS
from src.services import RiskAnalyzer
from src.scenarios import DirectAgentScenario
from src.core.models import CompanyRiskRequest, SearchConfig, RiskCategory, ScenarioType


def render_scenario1(config: AzureConfig):
    """Render Scenario 1: Direct Agent with Bing Tool."""
    st.header("🎯 Scenario 1: Direct Agent with Bing Tool")
    
    st.markdown("""
    **Architecture:** User → AI Agent (with Bing Grounding Tool attached directly)
    
    In this scenario, the **market parameter** is configured when creating the tool.
    """)
    
    st.divider()
    
    # Input form
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
            help="Select the market for Bing search results"
        )
    
    # Advanced options
    with st.expander("🔧 Advanced Options"):
        col_a, col_b = st.columns(2)
        with col_a:
            result_count = st.slider(
                "Number of Results",
                min_value=5,
                max_value=50,
                value=10
            )
        with col_b:
            freshness = st.selectbox(
                "Freshness Filter",
                options=["Day", "Week", "Month"],
                index=2
            )
    
    # Get market code
    market_code = None
    market_config = MARKET_OPTIONS.get(market_selection)
    if market_config:
        market_code = market_config.code
    
    # Show configuration
    st.subheader("🔧 Configuration")
    st.info(f"""
    **Market:** `{market_code or 'DEFAULT (Bing determines)'}`  
    **Count:** {result_count}  
    **Freshness:** {freshness}
    
    This configuration will be used when creating the `BingGroundingSearchConfiguration`.
    """)
    
    # Run button
    run_disabled = not st.session_state.config_valid or not company_name
    
    if st.button(
        "🔍 Run Risk Analysis",
        type="primary",
        disabled=run_disabled,
        use_container_width=True
    ):
        run_scenario1_analysis(config, company_name, market_code, result_count, freshness)
    
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
                # Agent Information
                st.caption("**🤖 Agent Information:**")
                agent_col1, agent_col2, agent_col3 = st.columns(3)
                with agent_col1:
                    st.metric("Agent Name", result.get('agent_name', 'N/A'))
                with agent_col2:
                    st.metric("Version", result.get('agent_version', 'N/A'))
                with agent_col3:
                    st.metric("Agent ID", result.get('agent_id', 'N/A')[:8] + '...' if result.get('agent_id') else 'N/A')
                
                st.markdown("---")
                st.caption("**🔧 Tool Configuration:**")
                st.json(result['tool_config'])
                st.markdown("---")
                st.markdown(result['text'])
                
                if result['citations']:
                    st.markdown("---")
                    st.caption("**Sources:**")
                    for citation in result['citations']:
                        st.markdown(f"- [{citation.get('title', citation['url'])}]({citation['url']})")


def run_scenario1_analysis(
    config: AzureConfig,
    company_name: str,
    market: str,
    count: int,
    freshness: str
):
    """Run Scenario 1 analysis."""
    with st.spinner(f"Analyzing {company_name}..."):
        try:
            async def do_analysis():
                client_factory = AzureClientFactory(config)
                risk_analyzer = RiskAnalyzer()
                scenario = DirectAgentScenario(
                    client_factory,
                    risk_analyzer,
                    config.model_deployment_name
                )
                
                request = CompanyRiskRequest(
                    company_name=company_name,
                    search_config=SearchConfig(
                        market=market,
                        count=count,
                        freshness=freshness
                    ),
                    scenario_type=ScenarioType.DIRECT_AGENT
                )
                
                return await scenario.execute(request)
            
            response = asyncio.run(do_analysis())
            
            # Store result
            st.session_state.analysis_results.append({
                "company": company_name,
                "market": market,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "text": response.text,
                "citations": [{"url": c.url, "title": c.title} for c in response.citations],
                "tool_config": response.metadata.get("tool_config", {}),
                "agent_id": response.metadata.get("agent_id"),
                "agent_name": response.metadata.get("agent_name"),
                "agent_version": response.metadata.get("agent_version"),
            })
            
            st.success(f"✅ Analysis complete for {company_name}")
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)
