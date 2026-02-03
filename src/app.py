"""
Company Risk Analysis Application - Streamlit UI

This application demonstrates:
1. How to test Bing Grounding market parameter behavior
2. Comparing results with different market configurations
3. Understanding where market is configured (tool level, not agent level)
"""
import os
import sys
import asyncio
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv

from config import AzureConfig, MARKET_OPTIONS, RISK_CATEGORIES
from agent import CompanyRiskAgent, get_company_risk_analysis_prompt

# Load environment variables
load_dotenv()


def init_session_state():
    """Initialize session state variables"""
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = []
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "config_valid" not in st.session_state:
        st.session_state.config_valid = False


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
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Analysis", "📊 Market Comparison", "📖 Documentation"])
    
    with tab1:
        render_main_content(config)
        
    with tab2:
        render_comparison_tab()
        
    with tab3:
        st.header("📖 Market Parameter Documentation")
        
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


if __name__ == "__main__":
    main()
