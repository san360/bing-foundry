"""
Agent service for managing AI agent lifecycle.

Uses Azure AI Projects SDK (v2.0.0b3+) New Agents API with versioned agents.
Agents are visible in Foundry portal. Executes via OpenAI Responses API.
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
        self._agents_created: List[str] = []  # Track agent names for cleanup
    
    def create_agent(
        self,
        name: str,
        instructions: str,
        bing_connection_id: str,
    ) -> dict:
        """
        Create a versioned agent with Bing grounding tool.
        
        Returns dict with agent info for visibility in Foundry portal.
        Uses the New Agents API (create_version) from azure-ai-projects 2.0.0b3+.
        """
        project_client = self.client_factory.get_project_client()
        
        # Create Bing grounding tool using azure.ai.projects.models
        bing_tool = BingGroundingAgentTool(
            bing_grounding=BingGroundingSearchToolParameters(
                search_configurations=[
                    BingGroundingSearchConfiguration(
                        project_connection_id=bing_connection_id
                    )
                ]
            )
        )
        
        # Create agent definition with Bing tool
        definition = PromptAgentDefinition(
            model=self.model_name,
            instructions=instructions,
            tools=[bing_tool],
        )
        
        # Create versioned agent (visible in Foundry portal)
        agent = project_client.agents.create_version(
            agent_name=name,
            definition=definition,
            description="Company risk analyst with Bing grounding",
        )
        
        # Track for cleanup
        self._agents_created.append(agent.name)
        
        logger.info(f"✅ Created Agent Version: {agent.name}")
        logger.info(f"   Agent ID: {agent.id}")
        logger.info(f"   Version: {agent.version}")
        
        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "agent_version": agent.version,
        }
    
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
    
    def delete_agent(self, agent_name: str) -> None:
        """Delete an agent by name."""
        project_client = self.client_factory.get_project_client()
        
        try:
            project_client.agents.delete(name=agent_name)
            logger.info(f"🗑️  Deleted agent: {agent_name}")
            if agent_name in self._agents_created:
                self._agents_created.remove(agent_name)
        except Exception as e:
            logger.error(f"Error deleting agent {agent_name}: {e}")
    
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
    
    def cleanup_all(self):
        """Clean up all created agents."""
        project_client = self.client_factory.get_project_client()
        
        for agent_name in self._agents_created[:]:
            try:
                project_client.agents.delete(name=agent_name)
                logger.info(f"🗑️  Cleaned up agent: {agent_name}")
            except Exception as e:
                logger.error(f"Error cleaning up agent {agent_name}: {e}")
        
        self._agents_created.clear()
