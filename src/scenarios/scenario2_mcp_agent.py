"""
Scenario 2: Two-Agent Pattern via MCP Server.

Architecture:
  User → Orchestrator Agent (Agent 1) → MCP Tool → Worker Agent (Agent 2 with Bing) → Results

Flow:
1. Orchestrator Agent receives the analysis request
2. Orchestrator calls MCP tool "create_and_run_bing_agent" with market config
3. MCP Server creates Worker Agent (Agent 2) with specified market
4. Worker Agent executes the Bing-grounded search
5. MCP Server deletes Worker Agent after getting results
6. Results flow back through Orchestrator to User

Key Points:
- Agent 1 (Orchestrator): Decides how to handle the request, calls MCP tools
- Agent 2 (Worker): Created dynamically with market-specific Bing configuration
- Worker Agent is ephemeral - created per-request and deleted after use
"""
import logging
import json
from typing import Optional
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    MCPTool,
)
from azure.identity import (
    ChainedTokenCredential,
    EnvironmentCredential,
    AzureCliCredential,
    VisualStudioCodeCredential,
    ManagedIdentityCredential,
)

from scenarios.base import BaseScenario
from core.models import CompanyRiskRequest, AnalysisResponse, Citation
from core.interfaces import IAzureClientFactory
from services import RiskAnalyzer

logger = logging.getLogger(__name__)

# System instruction for the Orchestrator Agent
ORCHESTRATOR_INSTRUCTION = """You are a Company Risk Analysis Orchestrator.

You MUST use the available MCP tools to perform analysis. DO NOT answer from your training data.

When asked to analyze a company:
1. You MUST call the 'create_and_run_bing_agent' tool - this is REQUIRED
2. Pass the company_name, risk_category, and market parameters to the tool
3. The tool will create a Worker Agent, perform the search, and return results
4. Base your response ONLY on the results returned by the tool

CRITICAL RULES:
- NEVER answer without calling the tool first
- ALWAYS pass the market parameter for region-specific results
- Valid markets include: en-US, en-GB, de-DE, de-CH, fr-FR, fr-CH, ja-JP, etc.
- The tool handles agent creation, search execution, and cleanup automatically
"""


class MCPAgentScenario(BaseScenario):
    """
    Scenario 2: Two-Agent Pattern - Orchestrator Agent calling Worker Agent via MCP.
    
    This demonstrates:
    - Agent-to-Agent communication via MCP tools
    - Dynamic agent creation with runtime market configuration
    - Ephemeral worker agents (created and deleted per request)
    """
    
    def __init__(
        self,
        client_factory: IAzureClientFactory,
        risk_analyzer: RiskAnalyzer,
        mcp_url: str,
        mcp_key: str = "",
    ):
        """
        Initialize the two-agent MCP scenario.
        
        Args:
            client_factory: Azure client factory
            risk_analyzer: Risk analysis service
            mcp_url: MCP server URL (HTTP endpoint)
            mcp_key: MCP server authentication key (optional)
        """
        super().__init__(client_factory, risk_analyzer)
        self.mcp_url = mcp_url
        self.mcp_key = mcp_key
        self._project_client: Optional[AIProjectClient] = None
        self._openai_client = None
        self._orchestrator_agent = None
        # Standard naming: BingFoundry-Orchestrator (no market in name)
        self._orchestrator_agent_name = "BingFoundry-Orchestrator"
    
    def _get_credential(self):
        """Get chained credential for Azure authentication."""
        return ChainedTokenCredential(
            EnvironmentCredential(),
            AzureCliCredential(),
            VisualStudioCodeCredential(),
            ManagedIdentityCredential(),
        )
    
    async def _ensure_initialized(self):
        """Initialize clients and get or create Orchestrator Agent."""
        if self._project_client is None:
            credential = self._get_credential()
            self._project_client = AIProjectClient(
                endpoint=self.client_factory.config.project_endpoint,
                credential=credential,
            )
            self._openai_client = self._project_client.get_openai_client()
            
            # Get or create the Orchestrator Agent with MCP tool
            await self._get_or_create_orchestrator_agent()
    
    async def _get_or_create_orchestrator_agent(self):
        """Get existing Orchestrator Agent or create a new one."""
        # Check if agent already exists
        try:
            agents = list(self._project_client.agents.list())
            logger.info(f"Found {len(agents)} agents in project")
            for agent in agents:
                if agent.name == self._orchestrator_agent_name:
                    logger.info(f"♻️  Reusing existing Orchestrator Agent: {agent.name} (v{agent.version})")
                    self._orchestrator_agent = agent
                    return
            logger.info(f"Agent '{self._orchestrator_agent_name}' not found in list, will create new")
        except Exception as e:
            logger.warning(f"Could not list agents: {e}")

        # Create new Orchestrator Agent
        await self._create_orchestrator_agent()
    
    async def _create_orchestrator_agent(self):
        """Create the Orchestrator Agent with MCP Server tool."""
        logger.info(f"🤖 Creating Orchestrator Agent: {self._orchestrator_agent_name}")
        
        # Configure MCP Server as a tool for the Orchestrator
        # This allows Agent 1 to call MCP tools that create Agent 2
        # Reference: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/custom-code-interpreter
        mcp_tool = MCPTool(
            server_label="bing_mcp_server",  # Must be alphanumeric and underscores only
            server_url=self.mcp_url,
            require_approval="never",
            allowed_tools=["create_and_run_bing_agent", "analyze_company_risk"],
        )
        
        self._orchestrator_agent = self._project_client.agents.create_version(
            agent_name=self._orchestrator_agent_name,
            definition=PromptAgentDefinition(
                model=self.client_factory.config.model_deployment_name,
                instructions=ORCHESTRATOR_INSTRUCTION,
                tools=[mcp_tool],
            ),
            description="Orchestrator agent that coordinates risk analysis via MCP tools",
        )
        
        logger.info(
            f"✅ Orchestrator Agent created: {self._orchestrator_agent.name} "
            f"(id: {self._orchestrator_agent.id}, version: {self._orchestrator_agent.version})"
        )
    
    async def execute(
        self,
        request: CompanyRiskRequest
    ) -> AnalysisResponse:
        """
        Execute Scenario 2: Two-Agent Pattern.
        
        1. Orchestrator Agent receives the request
        2. Orchestrator calls MCP tool to create Worker Agent with market config
        3. Worker Agent performs Bing-grounded search
        4. Worker Agent is deleted by MCP server
        5. Results returned through Orchestrator
        """
        logger.info(f"🚀 Scenario 2: Two-Agent Pattern for {request.company_name}")
        logger.info(f"   Market: {request.search_config.market or 'default'}")
        
        await self._ensure_initialized()
        
        # Build the prompt for the Orchestrator Agent
        market = request.search_config.market or "en-US"
        orchestrator_prompt = f"""Analyze the company "{request.company_name}" for {request.risk_category.value} risks.

Use the create_and_run_bing_agent tool with the following parameters:
- company_name: {request.company_name}
- risk_category: {request.risk_category.value}
- market: {market}

The market parameter is important - it ensures the search uses the {market} regional Bing index.
"""
        
        logger.info(f"📤 Sending request to Orchestrator Agent...")
        
        # Call the Orchestrator Agent
        response = self._openai_client.responses.create(
            tool_choice="required",  # Force the agent to use MCP tool
            input=orchestrator_prompt,
            extra_body={
                "agent": {
                    "name": self._orchestrator_agent.name,
                    "type": "agent_reference"
                }
            },
        )
        
        logger.info(f"✅ Orchestrator Agent responded")
        
        # Extract response text and citations
        response_text = response.output_text or ""
        citations = []
        
        for item in response.output:
            if hasattr(item, 'content') and item.content:
                for content in item.content:
                    if hasattr(content, 'annotations') and content.annotations:
                        for annotation in content.annotations:
                            if hasattr(annotation, 'url'):
                                citations.append(Citation(
                                    url=annotation.url,
                                    title=getattr(annotation, 'title', ''),
                                    snippet=getattr(annotation, 'snippet', ''),
                                ))
        
        return AnalysisResponse(
            text=response_text,
            citations=citations,
            market_used=market,
            metadata={
                "scenario": "two_agent_mcp",
                "orchestrator_agent_id": self._orchestrator_agent.id,
                "orchestrator_agent_name": self._orchestrator_agent.name,
                "orchestrator_agent_version": self._orchestrator_agent.version,
                "mcp_url": self.mcp_url,
                "risk_category": request.risk_category.value,
                "pattern": "Orchestrator Agent → MCP Tool → Worker Agent",
            }
        )

