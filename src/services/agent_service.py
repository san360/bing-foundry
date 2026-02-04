"""
Agent service for managing AI agent lifecycle.

Handles creation, deletion, and execution of AI Foundry agents.
"""
import logging
from typing import Optional, List
from azure.ai.projects.models import PromptAgentDefinition
from core.interfaces import IAgentService, IAzureClientFactory
from core.models import AnalysisResponse, Citation

logger = logging.getLogger(__name__)


class AgentService(IAgentService):
    """Service for managing AI agents."""
    
    def __init__(self, client_factory: IAzureClientFactory, model_name: str):
        """
        Initialize the agent service.
        
        Args:
            client_factory: Factory for creating Azure clients
            model_name: Model deployment name
        """
        self.client_factory = client_factory
        self.model_name = model_name
        self._agents_created: List[tuple[str, str]] = []  # (name, version)
    
    async def create_agent(
        self,
        name: str,
        instructions: str,
        tools: list,
    ) -> str:
        """Create an agent and return its identifier."""
        project_client = self.client_factory.get_project_client()
        
        agent = project_client.agents.create_version(
            agent_name=name,
            definition=PromptAgentDefinition(
                model=self.model_name,
                instructions=instructions,
                tools=tools,
            ),
            description=f"Agent: {name}",
        )
        
        # Track for cleanup
        self._agents_created.append((agent.name, agent.version))
        
        logger.info(f"Created agent: {agent.name} v{agent.version}")
        return agent.id
    
    async def delete_agent(self, agent_id: str) -> None:
        """Delete an agent by finding it in tracked agents."""
        project_client = self.client_factory.get_project_client()
        
        # Find the agent in our tracked list
        for name, version in self._agents_created:
            try:
                project_client.agents.delete_version(
                    agent_name=name,
                    agent_version=version
                )
                logger.info(f"Deleted agent: {name} v{version}")
                self._agents_created.remove((name, version))
                break
            except Exception as e:
                logger.error(f"Error deleting agent {name}: {e}")
    
    async def run_agent(
        self,
        agent_name: str,
        agent_version: str,
        prompt: str,
        tool_choice: str = "required",
    ) -> AnalysisResponse:
        """Run an agent with the given prompt."""
        openai_client = self.client_factory.get_openai_client()
        
        response = openai_client.responses.create(
            tool_choice=tool_choice,
            input=prompt,
            extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
        )
        
        # Extract citations
        citations = self._extract_citations(response)
        
        logger.info(f"Agent {agent_name} completed with {len(citations)} citations")
        
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
    
    def cleanup_all(self):
        """Clean up all created agents."""
        project_client = self.client_factory.get_project_client()
        
        for name, version in self._agents_created[:]:
            try:
                project_client.agents.delete_version(
                    agent_name=name,
                    agent_version=version
                )
                logger.info(f"Cleaned up agent: {name} v{version}")
            except Exception as e:
                logger.error(f"Error cleaning up agent {name}: {e}")
        
        self._agents_created.clear()
