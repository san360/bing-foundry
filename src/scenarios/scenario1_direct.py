"""
Scenario 1: Direct Agent with Bing Tool.

User → AI Agent (with Bing Grounding Tool attached directly)

Uses Azure AI Projects SDK New Agents API for versioned agents visible in Foundry portal.
Executes via OpenAI Responses API.
"""
import logging
from typing import Optional
from infrastructure.tracing import get_tracer

# Get tracer for this module (uses OpenTelemetry if available)
tracer = get_tracer(__name__)

from scenarios.base import BaseScenario
from core.models import CompanyRiskRequest, AnalysisResponse
from core.interfaces import IAzureClientFactory
from services import RiskAnalyzer, AgentService, AGENT_SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)


class DirectAgentScenario(BaseScenario):
    """
    Scenario 1: Direct agent with Bing tool.
    
    Market parameter is configured at tool creation time.
    Creates versioned agents visible in Foundry portal.
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
        
        Creates a versioned agent (visible in Foundry portal),
        then executes via OpenAI Responses API.
        
        Tracing is automatically captured via AIAgentsInstrumentor.
        """
        agent_info = None
        
        # Create span for the entire scenario execution
        with tracer.start_as_current_span(
            "scenario1.direct_agent",
            attributes={
                "scenario": "direct_agent",
                "company": request.company_name,
                "market": request.search_config.market or "default",
            }
        ) as span:
            try:
                # Get Bing connection ID
                bing_connection_id = self.client_factory.get_bing_connection_id()
                
                # Generate prompt
                prompt = self.risk_analyzer.get_analysis_prompt(request)
                
                # Create versioned agent with Bing tool (visible in Foundry portal)
                agent_name = f"CompanyRiskAnalyst-{request.search_config.market or 'default'}"
                
                agent_info = self.agent_service.create_agent(
                    name=agent_name,
                    instructions=AGENT_SYSTEM_INSTRUCTION,
                    bing_connection_id=bing_connection_id,
                )
                
                # Add agent info to span for tracing
                span.set_attribute("agent.id", agent_info['agent_id'])
                span.set_attribute("agent.name", agent_info['agent_name'])
                span.set_attribute("agent.version", agent_info.get('agent_version', 'N/A'))
                
                logger.info(f"🔍 Starting analysis for {request.company_name}...")
                logger.info(f"   View in Foundry Portal - Agent: {agent_info['agent_name']} (v{agent_info.get('agent_version', 'N/A')})")
                logger.info(f"   Agent ID: {agent_info['agent_id']}")
                
                # Execute via Responses API
                response = self.agent_service.run_agent_via_responses(
                    agent_name=agent_info['agent_name'],
                    agent_version=agent_info.get('agent_version'),
                    prompt=prompt,
                    tool_choice="required",
                )
                
                logger.info(f"✅ Analysis complete: {len(response.citations)} citations found")
                span.set_attribute("citations.count", len(response.citations))
                
                return AnalysisResponse(
                    text=response.text,
                    citations=response.citations,
                    market_used=request.search_config.market,
                    metadata={
                        "scenario": "direct_agent",
                        "agent_id": agent_info['agent_id'],
                        "agent_name": agent_info['agent_name'],
                        "agent_version": agent_info.get('agent_version'),
                        "market": request.search_config.market or "default",
                    }
                )
            
            except Exception as e:
                logger.error(f"Error in Scenario 1: {e}")
                span.record_exception(e)
                raise
            
            finally:
                # Clean up agent (optional - comment out to keep agents for inspection)
                if agent_info:
                    self.agent_service.delete_agent(agent_info['agent_name'])
