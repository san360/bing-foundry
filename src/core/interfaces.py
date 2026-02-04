"""
Abstract interfaces for the Bing Foundry application.

These interfaces define contracts that implementations must follow,
enabling dependency inversion and testability.
"""
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
from core.models import (
    CompanyRiskRequest,
    AnalysisResponse,
    SearchConfig,
    MarketConfig,
)


class ISearchService(ABC):
    """Interface for search services."""
    
    @abstractmethod
    async def search(
        self,
        query: str,
        config: SearchConfig
    ) -> AnalysisResponse:
        """Perform a search with the given configuration."""
        pass


class IAgentService(ABC):
    """Interface for AI agent management."""
    
    @abstractmethod
    async def create_agent(
        self,
        name: str,
        instructions: str,
        tools: list,
    ) -> str:
        """Create an agent and return its identifier."""
        pass
    
    @abstractmethod
    async def delete_agent(self, agent_id: str) -> None:
        """Delete an agent."""
        pass
    
    @abstractmethod
    async def run_agent(
        self,
        agent_id: str,
        prompt: str,
    ) -> AnalysisResponse:
        """Run an agent with the given prompt."""
        pass


class IRiskAnalyzer(ABC):
    """Interface for risk analysis."""
    
    @abstractmethod
    async def analyze(
        self,
        request: CompanyRiskRequest
    ) -> AnalysisResponse:
        """Analyze company risk based on the request."""
        pass
    
    @abstractmethod
    async def analyze_streaming(
        self,
        request: CompanyRiskRequest
    ) -> AsyncIterator[str]:
        """Analyze company risk with streaming response."""
        pass


class IScenarioExecutor(ABC):
    """Interface for scenario execution."""
    
    @abstractmethod
    async def execute(
        self,
        request: CompanyRiskRequest
    ) -> AnalysisResponse:
        """Execute the scenario and return analysis response."""
        pass
    
    @abstractmethod
    def get_configuration_info(
        self,
        config: SearchConfig
    ) -> dict:
        """Get information about how the scenario is configured."""
        pass


class IAzureClientFactory(ABC):
    """Interface for Azure client creation."""
    
    @abstractmethod
    def get_project_client(self):
        """Get AI Project client."""
        pass
    
    @abstractmethod
    def get_openai_client(self):
        """Get OpenAI client."""
        pass
    
    @abstractmethod
    def get_bing_connection_id(self) -> str:
        """Get Bing connection ID."""
        pass
