"""
Scenario 4: Multi-Market Research Agent.

User → AI Agent (with MCP Tool) → MCP Server (called multiple times for different markets) → Aggregated Results

This scenario demonstrates:
- Agent calling the same MCP tool multiple times with different market parameters
- Aggregation of results from multiple markets into a comprehensive analysis
- Parallel market research for global company risk assessment
"""
import logging
from typing import List, Optional
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from infrastructure.tracing import get_tracer
from scenarios.base import BaseScenario
from core.models import CompanyRiskRequest, AnalysisResponse, Citation
from core.interfaces import IAzureClientFactory
from services import RiskAnalyzer

# Get tracer for this module
tracer = get_tracer(__name__)
logger = logging.getLogger(__name__)

# Standard agent name (no market in name)
AGENT_NAME = "BingFoundry-MultiMarket"


class MultiMarketScenario(BaseScenario):
    """
    Scenario 4: Multi-Market Research using MCP tools.
    
    Agent calls MCP tool multiple times for different markets,
    then aggregates results into a comprehensive global analysis.
    """
    
    def __init__(
        self,
        client_factory: IAzureClientFactory,
        risk_analyzer: RiskAnalyzer,
        model_name: str,
        mcp_url: str,
    ):
        """
        Initialize the Multi-Market scenario.
        
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
    ) -> AnalysisResponse:
        """
        Execute Scenario 4: Multi-market research.
        
        Args:
            request: The company risk request
            markets: List of market codes to search (e.g., ['en-US', 'de-DE', 'ja-JP'])
            
        Returns:
            Aggregated analysis response from all markets
        """
        if not markets:
            markets = [request.search_config.market or "en-US"]
        
        with tracer.start_as_current_span(
            "scenario4.multi_market",
            attributes={
                "scenario": "multi_market",
                "company": request.company_name,
                "markets": ",".join(markets),
                "market_count": len(markets),
                "mcp_url": self.mcp_url,
            }
        ) as span:
            logger.info(f"Executing Scenario 4 for {request.company_name}")
            logger.info(f"   Markets to search: {markets}")

            project_client = self.client_factory.get_project_client()
            openai_client = self.client_factory.get_openai_client()

            # Get or create agent (single reusable agent - markets specified in prompt, not agent)
            agent = self._get_or_create_agent(project_client)
            
            span.set_attribute("agent.id", agent.id)
            span.set_attribute("agent.name", agent.name)
            span.set_attribute("agent.version", agent.version)
            
            try:
                # Build the multi-market query
                query = self._build_multi_market_prompt(request, markets)
                
                logger.info(f"📊 Searching {len(markets)} markets for {request.company_name}...")
                
                # Execute - agent will call MCP tool for each market
                response = openai_client.responses.create(
                    input=query,
                    tool_choice="required",
                    extra_body={
                        "agent": {
                            "name": agent.name,
                            "version": agent.version,
                            "type": "agent_reference",
                        }
                    },
                )
                
                logger.info(f"✅ Multi-market analysis complete")
                
                # Extract citations
                citations = self._extract_citations(response)
                span.set_attribute("citations.count", len(citations))
                
                return AnalysisResponse(
                    text=response.output_text if hasattr(response, 'output_text') else str(response),
                    citations=citations,
                    market_used=",".join(markets),
                    metadata={
                        "scenario": "multi_market",
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "agent_version": agent.version,
                        "mcp_url": self.mcp_url,
                        "markets_searched": markets,
                        "market_count": len(markets),
                    }
                )
            
            except Exception as e:
                span.record_exception(e)
                raise
    
    def _get_or_create_agent(self, project_client):
        """
        Get existing agent or create new one.

        The agent is market-independent - it has generic instructions.
        Specific markets are passed at call time via the prompt.
        """
        # Try to find existing agent by name
        try:
            agents = list(project_client.agents.list())
            logger.info(f"Found {len(agents)} agents in project")
            for existing_agent in agents:
                if existing_agent.name == AGENT_NAME:
                    logger.info(f"♻️  Reusing existing agent: {AGENT_NAME} (v{existing_agent.version})")
                    return existing_agent
            logger.info(f"Agent '{AGENT_NAME}' not found in list, will create new")
        except Exception as e:
            logger.warning(f"Could not list agents: {e}")

        # Create new agent with MCP tool
        logger.info(f"Creating new agent: {AGENT_NAME}")
        mcp_tool = MCPTool(
            server_label="bing_multi_market_mcp",
            server_url=self.mcp_url,
            require_approval="never",
            allowed_tools=["bing_search_rest_api"],
        )

        definition = PromptAgentDefinition(
            model=self.model_name,
            instructions="""You are a global company risk analysis assistant specializing in multi-market research.

Your PRIMARY function is to search for company information across MULTIPLE markets/regions using the bing_search_rest_api tool.

CRITICAL BEHAVIOR:
1. When given a list of markets, you MUST call bing_search_rest_api ONCE for EACH market
2. Each tool call uses a different "market" parameter (e.g., "en-US", "de-DE", "ja-JP")
3. You must NOT answer until you have searched ALL requested markets
4. You must NOT use your training data - ONLY use search results
5. After gathering ALL results, provide an aggregated comparative analysis

TOOL USAGE:
- Tool name: bing_search_rest_api
- Required parameter: query (the search query)
- Required parameter: market (the market code like "en-US", "de-DE", etc.)
- Make SEPARATE calls for each market - do NOT try to combine them

Your final analysis should compare and contrast findings across all markets searched.""",
            tools=[mcp_tool],
        )
        
        agent = project_client.agents.create_version(
            agent_name=AGENT_NAME,
            definition=definition,
            description="Multi-market risk analyst using MCP tool for global Bing search",
        )
        
        logger.info(f"✅ Created new multi-market agent: {agent.name} (v{agent.version})")
        return agent
    
    def _build_multi_market_prompt(self, request: CompanyRiskRequest, markets: List[str]) -> str:
        """Build the prompt for multi-market search."""
        base_prompt = self.risk_analyzer.get_analysis_prompt(request)

        # Build explicit tool call instructions for each market
        tool_call_instructions = []
        for i, market in enumerate(markets, 1):
            tool_call_instructions.append(
                f"   {i}. Call bing_search_rest_api with market=\"{market}\" for {market} regional results"
            )
        tool_calls_str = "\n".join(tool_call_instructions)

        return f"""{base_prompt}

=== MANDATORY MULTI-MARKET SEARCH INSTRUCTIONS ===

You MUST search EXACTLY {len(markets)} markets. Make {len(markets)} SEPARATE tool calls:

{tool_calls_str}

CRITICAL REQUIREMENTS:
- You MUST make EXACTLY {len(markets)} tool calls - one for each market listed above
- Each tool call MUST use a DIFFERENT market parameter from the list
- DO NOT skip any markets
- DO NOT combine markets into one call
- DO NOT answer until you have results from ALL {len(markets)} markets

After receiving results from ALL {len(markets)} markets, provide your analysis in this format:

## Market-by-Market Findings
(Summarize key findings from each market separately)

## Cross-Market Patterns
(What themes or concerns appear across multiple markets?)

## Regional Differences
(How is the company perceived differently across regions?)

## Global Risk Assessment
(Overall risk profile based on all {len(markets)} markets)

BEGIN: Make your {len(markets)} tool calls now, starting with market=\"{markets[0]}\"."""
    
    def _extract_citations(self, response) -> List[Citation]:
        """
        Extract citations from response.
        
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
