"""
Scenario 5 UI page: Workflow-Based Multi-Market Research with Parallel Execution.
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
from scenarios.scenario5_workflow import WorkflowMultiMarketScenario
from core.models import CompanyRiskRequest, SearchConfig, ScenarioType


def render_scenario5(config: AzureConfig):
    """Render Scenario 5: Workflow-Based Multi-Market Research."""
    st.header("⚡ Scenario 5: Workflow Multi-Market (Parallel)")

    st.markdown("""
    **Architecture:** User → Market Dispatcher → Parallel Search Executors → Aggregator → Analysis Agent → Response

    This workflow-based scenario executes market searches **in parallel** for faster results and better reliability.
    """)

    # Key benefits callout
    col_benefit1, col_benefit2, col_benefit3 = st.columns(3)
    with col_benefit1:
        st.success("**⚡ 3-5x Faster**\nParallel execution")
    with col_benefit2:
        st.success("**🛡️ Fault Tolerant**\nPartial results on failures")
    with col_benefit3:
        st.success("**📊 Better Tracing**\nPer-market visibility")

    st.divider()

    # Architecture diagram
    with st.expander("📐 View Workflow Architecture", expanded=False):
        st.code("""
┌─────────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW-BASED MULTI-MARKET SEARCH                   │
└─────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────────────┐
                         │   CompanyRiskRequest │
                         │   + List[markets]    │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   Market Dispatcher  │  Stage 1
                         │   (Split by market)  │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
    ┌─────────▼─────────┐ ┌────────▼────────┐ ┌─────────▼─────────┐
    │ Market Search     │ │ Market Search   │ │ Market Search     │
    │ (en-US)           │ │ (de-DE)         │ │ (ja-JP)           │  Stage 2
    │                   │ │                 │ │                   │  PARALLEL
    │ 90s timeout each  │ │ 90s timeout     │ │ 90s timeout       │
    └─────────┬─────────┘ └────────┬────────┘ └─────────┬─────────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Result Aggregator │  Stage 3
                        │   (Merge + handle   │
                        │    failures)        │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Analysis Agent    │  Stage 4
                        │   (Cross-market     │
                        │    comparison)      │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   AnalysisResponse  │
                        └─────────────────────┘
        """, language=None)

    st.divider()

    # MCP URL
    mcp_url = st.text_input(
        "MCP Server URL (must be publicly accessible)",
        value="https://your-tunnel-id.devtunnels.ms/mcp",
        key="s5_mcp_url",
        help="The MCP server URL for Bing search. Must be publicly accessible (e.g., via devtunnel)."
    )

    # Input form
    company_name = st.text_input(
        "Company Name",
        placeholder="Enter company name (e.g., Microsoft, Tesla, Siemens)",
        key="s5_company"
    )

    # Multi-select for markets
    st.subheader("🗺️ Select Markets to Research (Parallel Execution)")

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
            key="s5_americas",
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
            key="s5_europe",
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
            key="s5_apac",
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

    # Show selected markets summary with timing estimate
    if selected_market_codes:
        # Estimate: ~45-60 seconds for parallel (regardless of count up to 10)
        estimated_time = "45-60 seconds" if len(selected_market_codes) <= 10 else f"~{(len(selected_market_codes) // 10 + 1) * 60} seconds"
        st.success(f"**Selected Markets ({len(selected_market_codes)}):** {', '.join(selected_market_codes)}")
        st.info(f"⚡ **Estimated Time:** {estimated_time} (parallel execution)")
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
        f"⚡ Run Workflow ({len(selected_market_codes)} markets in parallel)",
        type="primary",
        disabled=run_disabled,
        key="s5_run",
        use_container_width=True
    ):
        run_scenario5_workflow(config, mcp_url, company_name, selected_market_codes)

    # Display results
    if st.session_state.get('workflow_results'):
        st.divider()
        st.subheader("📊 Workflow Results")

        for i, result in enumerate(reversed(st.session_state.workflow_results)):
            markets_str = ", ".join(result.get('successful_markets', []))
            failed_str = ", ".join(result.get('failed_markets', []))

            # Build expander title with status
            success_count = result.get('successful_count', 0)
            fail_count = result.get('failed_count', 0)
            status_emoji = "✅" if fail_count == 0 else "⚠️" if success_count > 0 else "❌"

            with st.expander(
                f"{status_emoji} [Workflow] {result['company']} | {success_count}/{success_count + fail_count} markets | {result['timestamp']}",
                expanded=(i == 0)
            ):
                # Workflow execution summary
                st.caption("**⚡ Workflow Execution Summary:**")

                exec_col1, exec_col2, exec_col3, exec_col4 = st.columns(4)
                with exec_col1:
                    st.metric("Total Markets", result.get('total_markets', 0))
                with exec_col2:
                    st.metric("Successful", result.get('successful_count', 0), delta=None)
                with exec_col3:
                    st.metric("Failed", result.get('failed_count', 0),
                             delta=None if result.get('failed_count', 0) == 0 else f"-{result.get('failed_count', 0)}",
                             delta_color="inverse")
                with exec_col4:
                    exec_time_sec = result.get('execution_time_ms', 0) / 1000
                    st.metric("Execution Time", f"{exec_time_sec:.1f}s")

                # Market results details
                st.markdown("---")
                st.caption("**📍 Per-Market Results:**")

                market_results = result.get('market_results', [])
                if market_results:
                    # Create columns for market results
                    cols = st.columns(min(len(market_results), 4))
                    for idx, mr in enumerate(market_results):
                        col_idx = idx % 4
                        with cols[col_idx]:
                            status = mr.get('status', 'unknown')
                            if status == 'success':
                                icon = "✅"
                                color = "green"
                            elif status == 'timeout':
                                icon = "⏰"
                                color = "orange"
                            else:
                                icon = "❌"
                                color = "red"

                            st.markdown(f"""
                            **{icon} {mr.get('market', 'N/A')}**
                            - Status: {status}
                            - Time: {mr.get('execution_time_ms', 0)}ms
                            - Citations: {mr.get('citation_count', 0)}
                            """)

                            if mr.get('error'):
                                st.caption(f"Error: {mr.get('error')[:50]}...")

                # Successful/Failed markets summary
                st.markdown("---")
                if markets_str:
                    st.success(f"**✅ Successful Markets:** {markets_str}")
                if failed_str:
                    st.error(f"**❌ Failed Markets:** {failed_str}")

                st.caption("**📍 Route:** Dispatcher → Parallel Searches → Aggregator → Analysis Agent")
                st.markdown("---")

                # Analysis results
                st.subheader("📝 Cross-Market Analysis")
                st.markdown(result.get('text', 'No response'))

                # Citations
                if result.get('citations'):
                    st.markdown("---")
                    st.caption(f"**Sources ({len(result['citations'])} citations from all markets):**")
                    for citation in result['citations'][:20]:  # Limit to 20
                        st.markdown(f"- [{citation['title']}]({citation['url']})")
                    if len(result['citations']) > 20:
                        st.caption(f"... and {len(result['citations']) - 20} more")


def run_scenario5_workflow(
    config: AzureConfig,
    mcp_url: str,
    company_name: str,
    markets: list
):
    """Run Scenario 5 workflow-based multi-market analysis."""

    # Create placeholders for progress updates
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    market_status_placeholder = st.empty()

    # Track progress
    progress_data = {
        "current": 0,
        "total": len(markets),
        "message": "Initializing workflow...",
        "market_statuses": {m: "pending" for m in markets}
    }

    def update_progress(message: str, current: int, total: int):
        """Callback to update progress display."""
        progress_data["message"] = message
        progress_data["current"] = current
        progress_data["total"] = total

    with st.spinner(f"⚡ Running workflow for {company_name} across {len(markets)} markets..."):
        # Show progress bar
        progress_bar = progress_placeholder.progress(0, text="Initializing workflow...")

        try:
            async def do_workflow():
                client_factory = AzureClientFactory(config)
                risk_analyzer = RiskAnalyzer()
                scenario = WorkflowMultiMarketScenario(
                    client_factory,
                    risk_analyzer,
                    config.model_deployment_name,
                    mcp_url
                )

                request = CompanyRiskRequest(
                    company_name=company_name,
                    search_config=SearchConfig(market=markets[0] if markets else "en-US"),
                    scenario_type=ScenarioType.WORKFLOW_MULTI_MARKET
                )

                return await scenario.execute(request, markets=markets, progress_callback=update_progress)

            response = asyncio.run(do_workflow())

            # Update progress to complete
            progress_placeholder.progress(100, text="Workflow complete!")

            # Initialize results list if needed
            if 'workflow_results' not in st.session_state:
                st.session_state.workflow_results = []

            # Extract workflow metadata
            workflow_exec = response.metadata.get('workflow_execution', {})
            market_results = response.metadata.get('market_results', [])

            st.session_state.workflow_results.append({
                "company": company_name,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "text": response.text,
                "citations": [{"url": c.url, "title": c.title} for c in response.citations],
                "successful_markets": response.metadata.get('successful_markets', []),
                "failed_markets": response.metadata.get('failed_markets', []),
                "total_markets": workflow_exec.get('total_markets', len(markets)),
                "successful_count": workflow_exec.get('successful_count', 0),
                "failed_count": workflow_exec.get('failed_count', 0),
                "execution_time_ms": workflow_exec.get('total_execution_time_ms', 0),
                "market_results": market_results,
                "mcp_url": mcp_url,
            })

            # Show success message
            success_count = workflow_exec.get('successful_count', 0)
            fail_count = workflow_exec.get('failed_count', 0)
            exec_time = workflow_exec.get('total_execution_time_ms', 0) / 1000

            if fail_count == 0:
                st.success(f"✅ Workflow complete! {success_count} markets searched in {exec_time:.1f}s")
            else:
                st.warning(f"⚠️ Workflow complete with partial results: {success_count} succeeded, {fail_count} failed ({exec_time:.1f}s)")

            st.rerun()

        except Exception as e:
            progress_placeholder.empty()
            st.error(f"❌ Workflow Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
