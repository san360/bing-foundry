"""
Agent service for managing AI agent lifecycle.

Uses Azure AI Projects SDK (v2.0.0b3+) New Agents API with versioned agents.
Agents are visible in Foundry portal. Executes via OpenAI Responses API.

Naming Convention: BingFoundry-{descriptor}
- Scenario1: BingFoundry-DirectAgent
- Scenario2: BingFoundry-Orchestrator
- Scenario3: BingFoundry-MCPAgent
- Scenario4: BingFoundry-MultiMarket
- MCP Server: BingFoundry-MCP-SearchAgent, BingFoundry-MCP-WorkerAgent
- Risk Agent: BingFoundry-RiskAgent
"""
import logging
from typing import Optional, List
from azure.ai.projects.models import (
    PromptAgentDefinition,
    BingGroundingAgentTool,
    BingGroundingSearchToolParameters,
    BingGroundingSearchConfiguration,
)
from core.interfaces import IAzureClientFactory
from core.models import AnalysisResponse, Citation

logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing AI agents using Azure AI Projects SDK New Agents API."""
    
    def __init__(self, client_factory: IAzureClientFactory, model_name: str):
        """
        Initialize the agent service.
        
        Args:
            client_factory: Factory for creating Azure clients
            model_name: Model deployment name
        """
        self.client_factory = client_factory
        self.model_name = model_name
        self._cached_agents: dict = {}  # Cache agent info by name
    
    def get_or_create_agent(
        self,
        name: str,
        instructions: str,
        bing_connection_id: str,
        tools: Optional[List] = None,
        description: str = "Company risk analyst with Bing grounding",
    ) -> dict:
        """
        Get existing agent or create a new one if it doesn't exist.
        
        This implements the "get or create" pattern - agents are reused
        instead of being created and deleted each time.
        
        Args:
            name: Agent name (use BingFoundry-{Scenario}-{descriptor} convention)
            instructions: Agent system instructions
            bing_connection_id: Bing connection ID (can be None if tools provided)
            tools: Optional list of tools (if None, creates Bing tool)
            description: Agent description
            
        Returns:
            Dict with agent_id, agent_name, agent_version
        """
        project_client = self.client_factory.get_project_client()
        
        # Check if we have a cached version
        if name in self._cached_agents:
            logger.info(f"♻️  Reusing cached agent: {name}")
            return self._cached_agents[name]
        
        # Try to find existing agent
        try:
            existing_agents = list(project_client.agents.list())
            for agent in existing_agents:
                if agent.name == name:
                    logger.info(f"♻️  Found existing agent: {name} (v{agent.version})")
                    agent_info = {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "agent_version": agent.version,
                    }
                    self._cached_agents[name] = agent_info
                    return agent_info
        except Exception as e:
            logger.debug(f"Could not list agents: {e}")
        
        # Create new agent
        if tools is None:
            # Default to Bing grounding tool
            tools = [
                BingGroundingAgentTool(
                    bing_grounding=BingGroundingSearchToolParameters(
                        search_configurations=[
                            BingGroundingSearchConfiguration(
                                project_connection_id=bing_connection_id
                            )
                        ]
                    )
                )
            ]
        
        definition = PromptAgentDefinition(
            model=self.model_name,
            instructions=instructions,
            tools=tools,
        )
        
        agent = project_client.agents.create_version(
            agent_name=name,
            definition=definition,
            description=description,
        )
        
        logger.info(f"✅ Created new agent: {agent.name} (v{agent.version})")
        logger.info(f"   Agent ID: {agent.id}")
        
        agent_info = {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "agent_version": agent.version,
        }
        self._cached_agents[name] = agent_info
        
        return agent_info
    
    def create_agent(
        self,
        name: str,
        instructions: str,
        bing_connection_id: str,
    ) -> dict:
        """
        Create or reuse a versioned agent with Bing grounding tool.
        
        This is a convenience wrapper around get_or_create_agent.
        """
        return self.get_or_create_agent(
            name=name,
            instructions=instructions,
            bing_connection_id=bing_connection_id,
        )
    
    def run_agent_via_responses(
        self,
        agent_name: str,
        agent_version: Optional[str],
        prompt: str,
        tool_choice: str = "required",
    ) -> AnalysisResponse:
        """
        Run an agent using OpenAI Responses API.
        
        The agent must be created first via create_agent().
        Uses agent reference by name (and optionally version).
        """
        openai_client = self.client_factory.get_openai_client()
        
        # Build agent reference - include version if provided
        agent_ref = {"name": agent_name, "type": "agent_reference"}
        if agent_version:
            agent_ref["version"] = agent_version
        
        logger.info(f"📝 Executing agent {agent_name} (version: {agent_version or 'latest'})")
        
        # Execute via OpenAI Responses API
        response = openai_client.responses.create(
            tool_choice=tool_choice,
            input=prompt,
            extra_body={"agent": agent_ref},
        )
        
        # Extract citations
        citations = self._extract_citations(response)
        
        logger.info(f"✅ Agent execution complete: {len(citations)} citations found")
        
        return AnalysisResponse(
            text=response.output_text,
            citations=citations,
            metadata={
                "agent_name": agent_name,
                "agent_version": agent_version,
            }
        )
    
    def _extract_citations(self, response) -> List[Citation]:
        """Extract citations from agent response."""
        citations = []
        
        if not hasattr(response, 'output'):
            return citations
        
        for item in response.output:
            if not hasattr(item, 'content') or item.content is None:
                continue
            
            for content in item.content:
                if not hasattr(content, 'annotations') or content.annotations is None:
                    continue
                
                for annotation in content.annotations:
                    if hasattr(annotation, 'url'):
                        citations.append(Citation(
                            url=annotation.url,
                            title=getattr(annotation, 'title', ''),
                            start_index=getattr(annotation, 'start_index', None),
                            end_index=getattr(annotation, 'end_index', None),
                        ))
        
        return citations
