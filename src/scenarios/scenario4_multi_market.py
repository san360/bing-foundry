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
AGENT_NAME = "BingFoundry-Scenario4-MultiMarket"


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
            
            # Get or create agent (no market in name - single agent for all markets)
            agent = self._get_or_create_agent(project_client, markets)
            
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
    
    def _get_or_create_agent(self, project_client, markets: List[str]):
        """Get existing agent or create new one."""
        # Try to find existing agent
        try:
            agents = list(project_client.agents.list())
            for existing_agent in agents:
                if existing_agent.name == AGENT_NAME:
                    logger.info(f"♻️  Reusing existing agent: {AGENT_NAME} (v{existing_agent.version})")
                    return existing_agent
        except Exception as e:
            logger.debug(f"Could not list agents: {e}")
        
        # Create new agent with MCP tool
        mcp_tool = MCPTool(
            server_label="bing_multi_market_mcp",
            server_url=self.mcp_url,
            require_approval="never",
            allowed_tools=["bing_search_rest_api"],
        )
        
        # Build market list for instructions
        market_list = ", ".join(markets) if markets else "en-US"
        
        definition = PromptAgentDefinition(
            model=self.model_name,
            instructions=f"""You are a global company risk analysis assistant specializing in multi-market research.

Your task is to search for company information across MULTIPLE markets/regions and provide a comprehensive aggregated analysis.

CRITICAL INSTRUCTIONS:
1. You MUST call the bing_search_rest_api tool MULTIPLE times - once for EACH market specified
2. For each tool call, use a DIFFERENT market parameter
3. DO NOT answer from your training data - ONLY use search results
4. After gathering results from ALL markets, provide an AGGREGATED analysis

When searching multiple markets:
- Call the tool with market="en-US" for US results
- Call the tool with market="de-DE" for German results
- Call the tool with market="ja-JP" for Japanese results
- And so on for each requested market

Your analysis should:
- Highlight regional differences in how the company is perceived
- Note any market-specific risks or concerns
- Identify patterns across markets
- Provide a global risk summary

IMPORTANT: You must make SEPARATE tool calls for each market. Do not try to search all markets in one call.""",
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
        
        market_instructions = "\n".join([
            f"- Search in {market} market" for market in markets
        ])
        
        return f"""{base_prompt}

MULTI-MARKET SEARCH REQUIREMENT:
You must search the following markets and aggregate results:
{market_instructions}

For EACH market above:
1. Call the bing_search_rest_api tool with the specific market parameter
2. Collect the search results
3. Note any market-specific findings

After searching ALL markets, provide:
1. **Market-by-Market Summary**: Key findings from each region
2. **Cross-Market Patterns**: Common themes or concerns across regions
3. **Regional Differences**: How the company is perceived differently in each market
4. **Global Risk Assessment**: Overall risk profile based on multi-market research

Remember: Make SEPARATE tool calls for each market - do not combine them."""
    
    def _extract_citations(self, response) -> List[Citation]:
        """Extract citations from response."""
        citations = []
        if hasattr(response, 'output') and response.output:
            for output_item in response.output:
                if hasattr(output_item, 'content'):
                    for content in output_item.content:
                        if hasattr(content, 'annotations'):
                            for annotation in content.annotations:
                                if hasattr(annotation, 'url'):
                                    citations.append(Citation(
                                        url=annotation.url,
                                        title=getattr(annotation, 'title', annotation.url),
                                    ))
        return citations
