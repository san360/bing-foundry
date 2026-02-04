"""
Scenario 5: Workflow-Based Multi-Market Research with Parallel Execution.

Architecture:
    User → Market Dispatcher → Parallel Search Executors → Aggregator → Analysis Agent → Response

This scenario demonstrates:
- Parallel execution of market searches (not sequential like Scenario 4)
- Per-market timeout handling with graceful degradation
- Result aggregation from multiple successful/failed markets
- Dedicated analysis agent for cross-market comparison
- Comprehensive tracing at each workflow stage

Key Benefits over Scenario 4:
- 3-5x faster execution (parallel vs sequential)
- Partial results on failures (graceful degradation)
- Better observability (per-market tracing)
- Predictable timeout behavior
"""
import asyncio
import logging
import time
from typing import List, Optional, Callable
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from infrastructure.tracing import get_tracer
from scenarios.base import BaseScenario
from core.models import (
    CompanyRiskRequest,
    AnalysisResponse,
    Citation,
    SearchConfig,
    MarketSearchResult,
    MarketSearchStatus,
    AggregatedMarketResults,
    WorkflowExecutionMetadata,
)
from core.interfaces import IAzureClientFactory
from services import RiskAnalyzer

# Get tracer for this module
tracer = get_tracer(__name__)
logger = logging.getLogger(__name__)

# Agent names for workflow
SEARCH_AGENT_NAME = "BingFoundry-WorkflowSearch"
ANALYSIS_AGENT_NAME = "BingFoundry-WorkflowAnalyzer"


def _get_agent_version(agent) -> str:
    """
    Safely get the version from an agent object.

    Handles both:
    - AgentDetails (from list()) which has 'versions' (dict with 'latest' key or list)
    - Agent (from create_version()) which has 'version' (string)
    """
    # First try direct version attribute (from create_version)
    if hasattr(agent, 'version') and agent.version:
        ver = agent.version
        # If it's already a string, return it
        if isinstance(ver, str):
            return ver
        # If it's an object/dict with 'version' key
        if hasattr(ver, 'version'):
            return str(ver.version)
        if isinstance(ver, dict) and 'version' in ver:
            return str(ver['version'])
        return str(ver)

    # Try versions attribute (from list())
    elif hasattr(agent, 'versions') and agent.versions:
        versions_data = agent.versions
        
        # Handle dict with 'latest' key (new API format)
        if isinstance(versions_data, dict):
            if 'latest' in versions_data:
                latest = versions_data['latest']
                if isinstance(latest, dict) and 'version' in latest:
                    return str(latest['version'])
                if hasattr(latest, 'version'):
                    return str(latest.version)
            # Check for direct 'version' key in the dict
            if 'version' in versions_data:
                return str(versions_data['version'])
        
        # Handle list of versions (old API format)
        elif isinstance(versions_data, list) and len(versions_data) > 0:
            latest = versions_data[-1]
            # If it's a string, return it
            if isinstance(latest, str):
                return latest
            # If it's an object with version attribute
            if hasattr(latest, 'version'):
                return str(latest.version)
            # If it's a dict with 'version' key
            if isinstance(latest, dict):
                if 'version' in latest:
                    return str(latest['version'])
                # Handle nested 'latest' structure
                if 'latest' in latest and isinstance(latest['latest'], dict):
                    return str(latest['latest'].get('version', 'unknown'))
            return str(latest)

    return "1"  # Default to version 1


class WorkflowMultiMarketScenario(BaseScenario):
    """
    Scenario 5: Workflow-based multi-market research using parallel execution.

    This scenario orchestrates multiple market searches in parallel using
    a structured workflow pattern, then aggregates results and generates
    a cross-market analysis.

    Workflow Stages:
        1. Market Dispatcher: Splits request into parallel tasks
        2. Market Search Executors: Execute searches in parallel (reuses Scenario 3 pattern)
        3. Result Aggregator: Consolidates results, handles failures
        4. Analysis Agent: Generates cross-market comparative analysis
    """

    # Configurable timeouts
    MARKET_TIMEOUT_SECONDS = 90   # Per-market timeout
    OVERALL_TIMEOUT_SECONDS = 300  # 5 minutes total workflow timeout
    MAX_CONCURRENT_SEARCHES = 10   # Limit concurrent requests

    def __init__(
        self,
        client_factory: IAzureClientFactory,
        risk_analyzer: RiskAnalyzer,
        model_name: str,
        mcp_url: str,
    ):
        """
        Initialize the Workflow Multi-Market scenario.

        Args:
            client_factory: Azure client factory
            risk_analyzer: Risk analysis service
            model_name: Model deployment name
            mcp_url: MCP server URL
        """
        super().__init__(client_factory, risk_analyzer)
        self.model_name = model_name
        self.mcp_url = mcp_url

    async def execute(
        self,
        request: CompanyRiskRequest,
        markets: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> AnalysisResponse:
        """
        Execute the workflow-based multi-market search.

        Args:
            request: The company risk request
            markets: List of market codes to search (e.g., ['en-US', 'de-DE', 'ja-JP'])
            progress_callback: Optional callback for progress updates (message, current, total)

        Returns:
            Aggregated analysis response from all markets
        """
        if not markets:
            markets = [request.search_config.market or "en-US"]

        workflow_start_time = time.time()

        with tracer.start_as_current_span(
            "scenario5.workflow",
            attributes={
                "scenario": "workflow_multi_market",
                "company": request.company_name,
                "markets": ",".join(markets),
                "market_count": len(markets),
                "mcp_url": self.mcp_url,
                "parallel_execution": True,
            }
        ) as workflow_span:
            logger.info(f"🚀 Starting Workflow Scenario 5 for {request.company_name}")
            logger.info(f"   Markets to search (parallel): {markets}")

            try:
                # ==== STAGE 1: Market Dispatcher ====
                with tracer.start_as_current_span(
                    "scenario5.stage1_dispatch",
                    attributes={"stage": "dispatch", "market_count": len(markets)}
                ):
                    logger.info(f"📤 Stage 1: Dispatching {len(markets)} parallel market searches")
                    if progress_callback:
                        progress_callback("Dispatching market searches...", 0, len(markets))

                # ==== STAGE 2: Parallel Market Search ====
                with tracer.start_as_current_span(
                    "scenario5.stage2_parallel_search",
                    attributes={"stage": "parallel_search", "market_count": len(markets)}
                ) as search_span:
                    logger.info(f"🔍 Stage 2: Executing parallel searches")

                    market_results = await self._execute_parallel_searches(
                        request,
                        markets,
                        progress_callback,
                    )

                    successful_count = sum(1 for r in market_results if r.status == MarketSearchStatus.SUCCESS)
                    search_span.set_attribute("successful_searches", successful_count)
                    search_span.set_attribute("failed_searches", len(markets) - successful_count)

                # ==== STAGE 3: Result Aggregation ====
                with tracer.start_as_current_span(
                    "scenario5.stage3_aggregation",
                    attributes={"stage": "aggregation"}
                ) as agg_span:
                    logger.info(f"📊 Stage 3: Aggregating results")
                    if progress_callback:
                        progress_callback("Aggregating results...", len(markets), len(markets))

                    aggregated = self._aggregate_results(market_results)

                    agg_span.set_attribute("successful_markets", len(aggregated.successful_markets))
                    agg_span.set_attribute("failed_markets", len(aggregated.failed_markets))
                    agg_span.set_attribute("total_citations", len(aggregated.total_citations))

                # ==== STAGE 4: Cross-Market Analysis ====
                with tracer.start_as_current_span(
                    "scenario5.stage4_analysis",
                    attributes={"stage": "analysis"}
                ) as analysis_span:
                    logger.info(f"🧠 Stage 4: Generating cross-market analysis")
                    if progress_callback:
                        progress_callback("Generating cross-market analysis...", len(markets), len(markets))

                    final_response = await self._generate_cross_market_analysis(
                        request,
                        aggregated,
                    )

                    analysis_span.set_attribute("analysis_agent.name", ANALYSIS_AGENT_NAME)

                # Calculate total execution time
                total_time_ms = int((time.time() - workflow_start_time) * 1000)

                # Build workflow metadata
                workflow_metadata = WorkflowExecutionMetadata(
                    total_markets=len(markets),
                    successful_count=len(aggregated.successful_markets),
                    failed_count=len(aggregated.failed_markets),
                    total_execution_time_ms=total_time_ms,
                    parallel_execution=True,
                    market_results=[
                        {
                            "market": r.market,
                            "status": r.status.value,
                            "execution_time_ms": r.execution_time_ms,
                            "citation_count": len(r.citations),
                            "error": r.error_message,
                        }
                        for r in market_results
                    ],
                )

                # Set final span attributes
                workflow_span.set_attribute("total_execution_time_ms", total_time_ms)
                workflow_span.set_attribute("successful_markets", len(aggregated.successful_markets))
                workflow_span.set_attribute("failed_markets", len(aggregated.failed_markets))
                workflow_span.set_attribute("total_citations", len(aggregated.total_citations))

                logger.info(f"✅ Workflow complete in {total_time_ms}ms")
                logger.info(f"   Successful: {len(aggregated.successful_markets)}, Failed: {len(aggregated.failed_markets)}")

                # Return final response with full metadata
                return AnalysisResponse(
                    text=final_response.text,
                    citations=aggregated.total_citations,
                    market_used=",".join(aggregated.successful_markets),
                    metadata={
                        "scenario": "workflow_multi_market",
                        "workflow_execution": {
                            "total_markets": workflow_metadata.total_markets,
                            "successful_count": workflow_metadata.successful_count,
                            "failed_count": workflow_metadata.failed_count,
                            "total_execution_time_ms": workflow_metadata.total_execution_time_ms,
                            "parallel_execution": workflow_metadata.parallel_execution,
                        },
                        "market_results": workflow_metadata.market_results,
                        "successful_markets": aggregated.successful_markets,
                        "failed_markets": aggregated.failed_markets,
                        "mcp_url": self.mcp_url,
                    }
                )

            except Exception as e:
                workflow_span.record_exception(e)
                logger.error(f"❌ Workflow failed: {e}")
                raise

    async def _execute_parallel_searches(
        self,
        request: CompanyRiskRequest,
        markets: List[str],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[MarketSearchResult]:
        """
        Execute searches for all markets in parallel with individual timeouts.

        Uses asyncio.gather with return_exceptions=True to ensure all markets
        are attempted even if some fail.
        """
        # Create search tasks with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_SEARCHES)
        completed_count = 0

        async def search_with_semaphore(market: str) -> MarketSearchResult:
            nonlocal completed_count
            async with semaphore:
                result = await self._search_single_market(request, market)
                completed_count += 1
                if progress_callback:
                    progress_callback(f"Searched {market}", completed_count, len(markets))
                return result

        # Create tasks for all markets
        tasks = [search_with_semaphore(market) for market in markets]

        # Execute all in parallel with overall timeout (Python 3.10 compatible)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.OVERALL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error(f"⏰ Overall workflow timeout ({self.OVERALL_TIMEOUT_SECONDS}s) exceeded")
            # Create timeout results for any incomplete markets
            results = []
            for market in markets:
                results.append(MarketSearchResult(
                    market=market,
                    status=MarketSearchStatus.TIMEOUT,
                    text="",
                    citations=[],
                    execution_time_ms=self.OVERALL_TIMEOUT_SECONDS * 1000,
                    error_message="Overall workflow timeout exceeded",
                ))

        # Process results (convert exceptions to error results)
        processed_results = []
        for i, result in enumerate(results):
            market = markets[i]
            if isinstance(result, Exception):
                logger.error(f"❌ Market {market} failed with exception: {result}")
                processed_results.append(MarketSearchResult(
                    market=market,
                    status=MarketSearchStatus.ERROR,
                    text="",
                    citations=[],
                    execution_time_ms=0,
                    error_message=str(result),
                ))
            elif isinstance(result, MarketSearchResult):
                processed_results.append(result)
            else:
                # Unexpected result type
                processed_results.append(MarketSearchResult(
                    market=market,
                    status=MarketSearchStatus.ERROR,
                    text="",
                    citations=[],
                    execution_time_ms=0,
                    error_message=f"Unexpected result type: {type(result)}",
                ))

        return processed_results

    async def _search_single_market(
        self,
        request: CompanyRiskRequest,
        market: str,
    ) -> MarketSearchResult:
        """
        Search a single market with timeout protection.

        Uses the same MCP tool pattern as Scenario 3, but with individual
        timeout handling and result encapsulation.
        """
        start_time = time.time()

        with tracer.start_as_current_span(
            "scenario5.market_search",
            attributes={
                "market": market,
                "company": request.company_name,
            }
        ) as span:
            try:
                # Define the search operation as an async function
                async def do_search():
                    logger.info(f"   🔎 Searching market: {market}")

                    # Get clients
                    project_client = self.client_factory.get_project_client()
                    openai_client = self.client_factory.get_openai_client()

                    # Get or create search agent
                    agent = self._get_or_create_search_agent(project_client)

                    span.set_attribute("agent.id", agent.id)
                    span.set_attribute("agent.name", agent.name)

                    # Build market-specific query
                    query = self._build_market_query(request, market)

                    # Execute search via agent (run in executor to not block)
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: openai_client.responses.create(
                            input=query,
                            tool_choice="required",
                            extra_body={
                                "agent": {
                                    "name": agent.name,
                                    "version": _get_agent_version(agent),
                                    "type": "agent_reference",
                                }
                            },
                        )
                    )

                    return response, agent

                # Execute with timeout (Python 3.10 compatible)
                response, agent = await asyncio.wait_for(
                    do_search(),
                    timeout=self.MARKET_TIMEOUT_SECONDS
                )

                execution_time_ms = int((time.time() - start_time) * 1000)

                # Extract citations
                citations = self._extract_citations(response)

                # Extract text
                text = response.output_text if hasattr(response, 'output_text') else str(response)

                span.set_attribute("status", "success")
                span.set_attribute("execution_time_ms", execution_time_ms)
                span.set_attribute("citation_count", len(citations))

                logger.info(f"   ✅ Market {market}: {len(citations)} citations in {execution_time_ms}ms")

                return MarketSearchResult(
                    market=market,
                    status=MarketSearchStatus.SUCCESS,
                    text=text,
                    citations=citations,
                    execution_time_ms=execution_time_ms,
                )

            except asyncio.TimeoutError:
                execution_time_ms = int((time.time() - start_time) * 1000)
                span.set_attribute("status", "timeout")
                span.set_attribute("execution_time_ms", execution_time_ms)
                logger.warning(f"   ⏰ Market {market}: Timeout after {execution_time_ms}ms")

                return MarketSearchResult(
                    market=market,
                    status=MarketSearchStatus.TIMEOUT,
                    text="",
                    citations=[],
                    execution_time_ms=execution_time_ms,
                    error_message=f"Search timed out after {self.MARKET_TIMEOUT_SECONDS}s",
                )

            except Exception as e:
                execution_time_ms = int((time.time() - start_time) * 1000)
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                span.record_exception(e)
                logger.error(f"   ❌ Market {market}: Error - {e}")

                return MarketSearchResult(
                    market=market,
                    status=MarketSearchStatus.ERROR,
                    text="",
                    citations=[],
                    execution_time_ms=execution_time_ms,
                    error_message=str(e),
                )

    def _get_or_create_search_agent(self, project_client):
        """Get or create the search agent for individual market searches."""
        # Try to find existing agent
        try:
            agents = list(project_client.agents.list())
            for existing_agent in agents:
                if existing_agent.name == SEARCH_AGENT_NAME:
                    logger.debug(f"♻️  Reusing search agent: {SEARCH_AGENT_NAME}")
                    return existing_agent
        except Exception as e:
            logger.warning(f"Could not list agents: {e}")

        # Create new search agent
        logger.info(f"Creating new search agent: {SEARCH_AGENT_NAME}")

        mcp_tool = MCPTool(
            server_label="bing_workflow_search_mcp",
            server_url=self.mcp_url,
            require_approval="never",
            allowed_tools=["bing_search_rest_api"],
        )

        definition = PromptAgentDefinition(
            model=self.model_name,
            instructions="""You are a company research assistant focused on a SINGLE market.

Your task is to search for company information using the bing_search_rest_api tool with the SPECIFIC market provided.

CRITICAL RULES:
1. You MUST call bing_search_rest_api exactly ONCE with the market specified in the query
2. DO NOT make multiple tool calls
3. DO NOT use your training data - ONLY use search results
4. Return the search results and a brief summary of findings for this market

Focus on: recent news, legal issues, regulatory concerns, financial news, and reputation.""",
            tools=[mcp_tool],
        )

        agent = project_client.agents.create_version(
            agent_name=SEARCH_AGENT_NAME,
            definition=definition,
            description="Workflow search agent for single-market Bing search",
        )

        logger.info(f"✅ Created search agent: {agent.name} (v{_get_agent_version(agent)})")
        return agent

    def _get_or_create_analysis_agent(self, project_client):
        """Get or create the analysis agent for cross-market comparison."""
        # Try to find existing agent
        try:
            agents = list(project_client.agents.list())
            for existing_agent in agents:
                if existing_agent.name == ANALYSIS_AGENT_NAME:
                    logger.debug(f"♻️  Reusing analysis agent: {ANALYSIS_AGENT_NAME}")
                    return existing_agent
        except Exception as e:
            logger.warning(f"Could not list agents: {e}")

        # Create new analysis agent (NO tools - just analysis)
        logger.info(f"Creating new analysis agent: {ANALYSIS_AGENT_NAME}")

        definition = PromptAgentDefinition(
            model=self.model_name,
            instructions="""You are an expert risk analyst specializing in cross-market comparative analysis.

You will receive search results gathered from multiple markets/regions. Your task is to:

1. **Synthesize** the findings from each market
2. **Identify** common patterns and themes across regions
3. **Highlight** regional differences and unique concerns
4. **Assess** the overall global risk profile

Provide a well-structured analysis with clear sections. Be objective and cite specific findings from the market data provided.

IMPORTANT: You are an ANALYSIS agent. Do NOT try to search for more information.
Work ONLY with the market data provided to you.""",
            tools=[],  # No tools - pure analysis
        )

        agent = project_client.agents.create_version(
            agent_name=ANALYSIS_AGENT_NAME,
            definition=definition,
            description="Workflow analysis agent for cross-market comparison",
        )

        logger.info(f"✅ Created analysis agent: {agent.name} (v{_get_agent_version(agent)})")
        return agent

    def _build_market_query(self, request: CompanyRiskRequest, market: str) -> str:
        """Build a query for a specific market search."""
        base_prompt = self.risk_analyzer.get_analysis_prompt(request)

        return f"""{base_prompt}

=== MARKET-SPECIFIC SEARCH ===

You MUST search for information about {request.company_name} in the **{market}** market.

Call the bing_search_rest_api tool with:
- query: relevant search query about {request.company_name}
- market: "{market}"

Make ONE tool call and return the results."""

    def _aggregate_results(
        self,
        market_results: List[MarketSearchResult],
    ) -> AggregatedMarketResults:
        """Aggregate results from all market searches."""
        successful = [r for r in market_results if r.status == MarketSearchStatus.SUCCESS]
        failed = [r for r in market_results if r.status != MarketSearchStatus.SUCCESS]

        # Collect all citations
        all_citations = []
        for result in successful:
            all_citations.extend(result.citations)

        # Calculate total execution time
        total_time = sum(r.execution_time_ms for r in market_results)

        return AggregatedMarketResults(
            successful_markets=[r.market for r in successful],
            failed_markets=[r.market for r in failed],
            results=market_results,
            total_citations=all_citations,
            total_execution_time_ms=total_time,
        )

    async def _generate_cross_market_analysis(
        self,
        request: CompanyRiskRequest,
        aggregated: AggregatedMarketResults,
    ) -> AnalysisResponse:
        """Generate cross-market comparative analysis using dedicated agent."""

        # Build context from all market results
        market_context = self._build_market_context(aggregated)

        # Create analysis prompt
        analysis_prompt = f"""# Cross-Market Risk Analysis Request

## Company: {request.company_name}

## Search Results Summary
- **Successful Markets ({len(aggregated.successful_markets)}):** {', '.join(aggregated.successful_markets) or 'None'}
- **Failed Markets ({len(aggregated.failed_markets)}):** {', '.join(aggregated.failed_markets) or 'None'}
- **Total Citations Found:** {len(aggregated.total_citations)}

## Market-Specific Findings

{market_context}

---

## Your Analysis Task

Based on the market-specific findings above, provide a comprehensive cross-market risk analysis:

### 1. Market-by-Market Summary
Summarize the key findings from each successful market search.

### 2. Cross-Market Patterns
What themes, concerns, or findings appear consistently across multiple markets?

### 3. Regional Differences
How does the company's perception or risk profile vary between regions?

### 4. Global Risk Assessment
Provide an overall risk assessment considering all markets. Rate the risk level and explain.

### 5. Data Gaps
Note any limitations due to failed market searches or missing information.

---

IMPORTANT: Base your analysis ONLY on the search results provided above. Do not use external knowledge."""

        # Get clients and agent
        project_client = self.client_factory.get_project_client()
        openai_client = self.client_factory.get_openai_client()

        # Get or create analysis agent
        agent = self._get_or_create_analysis_agent(project_client)

        # Execute analysis (no tool_choice since agent has no tools)
        response = openai_client.responses.create(
            input=analysis_prompt,
            extra_body={
                "agent": {
                    "name": agent.name,
                    "version": _get_agent_version(agent),
                    "type": "agent_reference",
                }
            },
        )

        text = response.output_text if hasattr(response, 'output_text') else str(response)

        logger.info(f"✅ Cross-market analysis complete")

        return AnalysisResponse(
            text=text,
            citations=[],  # Citations come from aggregated results
            market_used=",".join(aggregated.successful_markets),
            metadata={
                "analysis_agent": agent.name,
                "analysis_agent_version": _get_agent_version(agent),
            }
        )

    def _build_market_context(self, aggregated: AggregatedMarketResults) -> str:
        """Build context string from market results for analysis agent."""
        context_parts = []

        for result in aggregated.results:
            if result.status == MarketSearchStatus.SUCCESS:
                citation_summary = f"({len(result.citations)} sources found)"
                context_parts.append(f"""
### {result.market} - SUCCESS {citation_summary}
**Execution Time:** {result.execution_time_ms}ms

**Findings:**
{result.text}

---
""")
            else:
                context_parts.append(f"""
### {result.market} - {result.status.value.upper()}
**Status:** {result.status.value}
**Error:** {result.error_message or 'Unknown error'}
**Execution Time:** {result.execution_time_ms}ms

*No data available for this market.*

---
""")

        return "\n".join(context_parts)

    def _extract_citations(self, response) -> List[Citation]:
        """
        Extract citations from agent response.
        
        Handles two citation formats:
        1. URL annotations in response output (from Bing grounding tool directly)
        2. Citations embedded in MCP tool JSON responses
        """
        import json
        citations = []
        seen_urls = set()  # Deduplicate citations by URL
        
        if hasattr(response, 'output') and response.output:
            for output_item in response.output:
                # Method 1: Extract from annotations (Bing grounding direct)
                if hasattr(output_item, 'content'):
                    for content in output_item.content:
                        if hasattr(content, 'annotations') and content.annotations:
                            for annotation in content.annotations:
                                if hasattr(annotation, 'url') and annotation.url:
                                    if annotation.url not in seen_urls:
                                        seen_urls.add(annotation.url)
                                        citations.append(Citation(
                                            url=annotation.url,
                                            title=getattr(annotation, 'title', annotation.url),
                                        ))
                        
                        # Method 2: Parse JSON from MCP tool output
                        if hasattr(content, 'text') and content.text:
                            try:
                                # Try to parse as JSON (MCP tool returns JSON)
                                data = json.loads(content.text)
                                
                                # Extract citations from MCP response format
                                if isinstance(data, dict):
                                    # Direct citations array
                                    if 'citations' in data and isinstance(data['citations'], list):
                                        for cit in data['citations']:
                                            url = cit.get('url', '')
                                            if url and url not in seen_urls:
                                                seen_urls.add(url)
                                                citations.append(Citation(
                                                    url=url,
                                                    title=cit.get('title', url),
                                                ))
                                    
                                    # Nested in search_results
                                    if 'search_results' in data and isinstance(data['search_results'], dict):
                                        sr = data['search_results']
                                        if 'citations' in sr and isinstance(sr['citations'], list):
                                            for cit in sr['citations']:
                                                url = cit.get('url', '')
                                                if url and url not in seen_urls:
                                                    seen_urls.add(url)
                                                    citations.append(Citation(
                                                        url=url,
                                                        title=cit.get('title', url),
                                                    ))
                            except (json.JSONDecodeError, TypeError):
                                # Not JSON, skip
                                pass
                
                # Method 3: Check for tool call responses with embedded citations
                if hasattr(output_item, 'type') and output_item.type == 'mcp_call':
                    if hasattr(output_item, 'output') and output_item.output:
                        try:
                            data = json.loads(output_item.output) if isinstance(output_item.output, str) else output_item.output
                            if isinstance(data, dict) and 'citations' in data:
                                for cit in data['citations']:
                                    url = cit.get('url', '')
                                    if url and url not in seen_urls:
                                        seen_urls.add(url)
                                        citations.append(Citation(
                                            url=url,
                                            title=cit.get('title', url),
                                        ))
                        except (json.JSONDecodeError, TypeError):
                            pass
        
        return citations
