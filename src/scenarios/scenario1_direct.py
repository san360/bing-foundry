"""
Scenario 1: Direct Agent with Bing Tool.

User → AI Agent (with Bing Grounding Tool attached directly)
"""
import logging
from typing import Optional
try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None

from scenarios.base import BaseScenario
from core.models import CompanyRiskRequest, AnalysisResponse
from core.interfaces import IAzureClientFactory
from services import RiskAnalyzer, BingToolBuilder, AgentService, AGENT_SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)


class DirectAgentScenario(BaseScenario):
    """
    Scenario 1: Direct agent with Bing tool.
    
    Market parameter is configured at tool creation time.
    """
    
    def __init__(
        self,
        client_factory: IAzureClientFactory,
        risk_analyzer: RiskAnalyzer,
        model_name: str,
    ):
        """
        Initialize the direct agent scenario.
        
        Args:
            client_factory: Azure client factory
            risk_analyzer: Risk analysis service
            model_name: Model deployment name
        """
        super().__init__(client_factory, risk_analyzer)
        self.model_name = model_name
        self.agent_service = AgentService(client_factory, model_name)
    
    async def execute(
        self,
        request: CompanyRiskRequest
    ) -> AnalysisResponse:
        """
        Execute Scenario 1: Direct agent with Bing tool.
        
        The market parameter is set at tool creation time.
        """
        span_context = None
        if tracer:
            span_context = tracer.start_as_current_span(
                "scenario1.direct_agent",
                attributes={
                    "scenario": "direct_agent",
                    "company": request.company_name,
                    "market": request.search_config.market or "default",
                }
            )
        
        try:
            if span_context:
                span_context.__enter__()
            
            # Build Bing tool with market configuration
            bing_connection_id = self.client_factory.get_bing_connection_id()
            tool_builder = BingToolBuilder(bing_connection_id)
            bing_tool = tool_builder.build(request.search_config)
            
            # Generate prompt
            prompt = self.risk_analyzer.get_analysis_prompt(request)
            
            # Create agent with Bing tool
            agent_name = f"CompanyRiskAnalyst-{request.search_config.market or 'default'}"
            
            project_client = self.client_factory.get_project_client()
            openai_client = self.client_factory.get_openai_client()
            
            from azure.ai.projects.models import PromptAgentDefinition
            
            agent = project_client.agents.create_version(
                agent_name=agent_name,
                definition=PromptAgentDefinition(
                    model=self.model_name,
                    instructions=AGENT_SYSTEM_INSTRUCTION,
                    tools=[bing_tool],
                ),
                description="Company risk analysis agent with Bing grounding",
            )
            
            try:
                # Execute the analysis
                logger.info(f"Executing Scenario 1 for {request.company_name}")
                
                response = openai_client.responses.create(
                    tool_choice="required",
                    input=prompt,
                    extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
                )
                
                # Extract citations
                citations = self.agent_service._extract_citations(response)
                
                logger.info(f"Scenario 1 complete: {len(citations)} citations")
                
                return AnalysisResponse(
                    text=response.output_text,
                    citations=citations,
                    market_used=request.search_config.market,
                    metadata={
                        "scenario": "direct_agent",
                        "agent_name": agent.name,
                        "tool_config": tool_builder.get_config_info(request.search_config),
                    }
                )
            
            finally:
                # Clean up agent
                project_client.agents.delete_version(
                    agent_name=agent.name,
                    agent_version=agent.version
                )
        
        except Exception as e:
            logger.error(f"Error in Scenario 1: {e}")
            if tracer and span_context:
                current_span = trace.get_current_span()
                current_span.record_exception(e)
                current_span.set_status(trace.StatusCode.ERROR, str(e))
            raise
        
        finally:
            if span_context:
                span_context.__exit__(None, None, None)
