"""
Scenario 3: Agent → MCP Tool → REST API.

User → AI Agent (with MCP Tool) → MCP Server → Bing REST API
"""
import logging
from typing import Optional
from scenarios.base import BaseScenario
from core.models import CompanyRiskRequest, AnalysisResponse
from core.interfaces import IAzureClientFactory
from services import RiskAnalyzer

logger = logging.getLogger(__name__)


class MCPRestAPIScenario(BaseScenario):
    """
    Scenario 3: Agent with MCP tool that calls REST API.
    
    Agent has MCP tool attached, which calls Bing REST API directly.
    """
    
    def __init__(
        self,
        client_factory: IAzureClientFactory,
        risk_analyzer: RiskAnalyzer,
        model_name: str,
        mcp_url: str,
    ):
        """
        Initialize the MCP REST API scenario.
        
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
        request: CompanyRiskRequest
    ) -> AnalysisResponse:
        """
        Execute Scenario 3: Agent with MCP tool calling REST API.
        
        Creates an agent with an MCP tool that calls the Bing REST API.
        """
        logger.info(f"Executing Scenario 3 for {request.company_name}")
        
        project_client = self.client_factory.get_project_client()
        openai_client = self.client_factory.get_openai_client()
        
        from azure.ai.projects.models import PromptAgentDefinition, MCPTool
        
        # Create MCP Tool pointing to our server
        mcp_tool = MCPTool(
            server_label="bing_rest_api_mcp",
            server_url=self.mcp_url,
            require_approval="never",
            allowed_tools=["bing_search_rest_api", "analyze_company_risk_rest_api"],
        )
        
        logger.info(f"Created MCP Tool pointing to: {self.mcp_url}")
        
        # Create agent with MCP tool
        agent = project_client.agents.create_version(
            agent_name="CompanyRiskAnalyst-MCP",
            definition=PromptAgentDefinition(
                model=self.model_name,
                instructions=f"""You are a company risk analysis assistant. 
You have access to an MCP tool that can search the web using Bing.

When asked to analyze a company, use the available MCP tools to search for:
- Recent news and controversies
- Legal issues and lawsuits  
- Regulatory violations
- ESG concerns

Always include the market parameter '{request.search_config.market or "en-US"}' in your searches.

Provide a comprehensive risk assessment based on the search results.""",
                tools=[mcp_tool],
            ),
            description="Agent with custom MCP tool for Bing REST API search",
        )
        
        logger.info(f"Created agent: {agent.id}, {agent.name}")
        
        try:
            # Build the query
            query = self.risk_analyzer.get_analysis_prompt(request)
            
            # Call the agent
            response = openai_client.responses.create(
                input=query,
                extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
            )
            
            logger.info("Got response from agent with MCP tool")
            
            # Extract citations
            citations = []
            if hasattr(response, 'output') and response.output:
                for output_item in response.output:
                    if hasattr(output_item, 'content'):
                        for content in output_item.content:
                            if hasattr(content, 'annotations'):
                                for annotation in content.annotations:
                                    if hasattr(annotation, 'url'):
                                        from core.models import Citation
                                        citations.append(Citation(
                                            url=annotation.url,
                                            title=getattr(annotation, 'title', annotation.url),
                                        ))
            
            return AnalysisResponse(
                text=response.output_text if hasattr(response, 'output_text') else str(response),
                citations=citations,
                market_used=request.search_config.market,
                metadata={
                    "scenario": "mcp_rest_api",
                    "agent_id": agent.id,
                    "mcp_url": self.mcp_url,
                }
            )
        
        finally:
            # Clean up agent
            project_client.agents.delete_version(
                agent_name=agent.name,
                agent_version=agent.version,
            )
            logger.info(f"Deleted agent: {agent.name}")
