"""
Scenario 3: Agent → MCP Tool → REST API.

User → AI Agent (with MCP Tool) → MCP Server → Bing REST API

Uses Azure AI Projects SDK New Agents API for versioned agents visible in Foundry portal.
Executes via OpenAI Responses API.
"""
import logging
from typing import Optional
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from infrastructure.tracing import get_tracer
from scenarios.base import BaseScenario
from core.models import CompanyRiskRequest, AnalysisResponse, Citation
from core.interfaces import IAzureClientFactory
from services import RiskAnalyzer

# Get tracer for this module
tracer = get_tracer(__name__)
logger = logging.getLogger(__name__)


class MCPRestAPIScenario(BaseScenario):
    """
    Scenario 3: Agent with MCP tool that calls REST API.
    
    Agent has MCP tool attached, which calls Bing REST API directly.
    Creates versioned agents visible in Foundry portal.
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
        
        Creates a versioned agent (visible in Foundry portal),
        then executes via OpenAI Responses API.
        
        Tracing is automatically captured via AIAgentsInstrumentor.
        """
        # Create span for the entire scenario
        with tracer.start_as_current_span(
            "scenario3.mcp_rest_api",
            attributes={
                "scenario": "mcp_rest_api",
                "company": request.company_name,
                "market": request.search_config.market or "default",
                "mcp_url": self.mcp_url,
            }
        ) as span:
            logger.info(f"Executing Scenario 3 for {request.company_name}")
            
            project_client = self.client_factory.get_project_client()
            openai_client = self.client_factory.get_openai_client()
            
            # Create MCP Tool pointing to our server
            mcp_tool = MCPTool(
                server_label="bing_rest_api_mcp",
                server_url=self.mcp_url,
                require_approval="never",
                allowed_tools=["bing_search_rest_api"],
            )
            
            logger.info(f"✅ Created MCP Tool with REST API wrapper: {self.mcp_url}")
            
            # Create agent definition with MCP tool
            definition = PromptAgentDefinition(
                model=self.model_name,
                instructions=f"""You are a company risk analysis assistant.
You MUST use the available MCP tools to search for information. DO NOT answer from your training data.

When asked to analyze a company:
1. ALWAYS call the bing_search_rest_api tool to get current information
2. Use market parameter '{request.search_config.market or "en-US"}' for regional results
3. Search for: recent news, legal issues, regulatory violations, ESG concerns
4. Base your analysis ONLY on the search results returned by the tool

IMPORTANT: You must call the tool for EVERY request. Never skip the tool call.""",
                tools=[mcp_tool],
            )
            
            # Create versioned agent (visible in Foundry portal)
            agent_name = "CompanyRiskAnalyst-MCP"
            agent = project_client.agents.create_version(
                agent_name=agent_name,
                definition=definition,
                description="Company risk analyst using MCP tool for Bing search",
            )
            
            # Add agent info to span for tracing
            span.set_attribute("agent.id", agent.id)
            span.set_attribute("agent.name", agent.name)
            span.set_attribute("agent.version", agent.version)
            
            logger.info(f"✅ Created Agent: {agent.name} (version: {agent.version})")
            logger.info(f"   Agent ID: {agent.id}")
            logger.info(f"   View in Foundry Portal!")
            
            try:
                # Build the query
                query = self.risk_analyzer.get_analysis_prompt(request)
                
                # Execute via OpenAI Responses API using agent reference
                # tool_choice="required" forces the agent to use the MCP tool
                response = openai_client.responses.create(
                    input=query,
                    tool_choice="required",  # MUST use the MCP tool
                    extra_body={
                        "agent": {
                            "name": agent.name,
                            "version": agent.version,
                            "type": "agent_reference",
                        }
                    },
                )
                
                logger.info(f"✅ Received response from agent {agent.name}")
                
                # Extract citations
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
                
                span.set_attribute("citations.count", len(citations))
                
                return AnalysisResponse(
                    text=response.output_text if hasattr(response, 'output_text') else str(response),
                    citations=citations,
                    market_used=request.search_config.market,
                    metadata={
                        "scenario": "mcp_rest_api",
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "agent_version": agent.version,
                        "mcp_url": self.mcp_url,
                    }
                )
            
            except Exception as e:
                span.record_exception(e)
                raise
            
            finally:
                # Clean up agent (optional - comment out to keep for inspection)
                # NOTE: Commented out to keep agents visible in Foundry portal for inspection
                # project_client.agents.delete_version(
                #     agent_name=agent.name,
                #     agent_version=agent.version
                # )
                # logger.info(f"🗑️  Cleaned up agent: {agent.name}")
                pass
