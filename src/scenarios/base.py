"""
Base class for scenario executors.

Provides common functionality for all scenarios.
"""
import logging
from abc import abstractmethod
from typing import AsyncIterator
from core.interfaces import IScenarioExecutor, IAzureClientFactory
from core.models import CompanyRiskRequest, AnalysisResponse, SearchConfig
from services import RiskAnalyzer

logger = logging.getLogger(__name__)


class BaseScenario(IScenarioExecutor):
    """Base class for all scenario implementations."""
    
    def __init__(
        self,
        client_factory: IAzureClientFactory,
        risk_analyzer: RiskAnalyzer,
    ):
        """
        Initialize the base scenario.
        
        Args:
            client_factory: Factory for creating Azure clients
            risk_analyzer: Risk analysis service
        """
        self.client_factory = client_factory
        self.risk_analyzer = risk_analyzer
    
    @abstractmethod
    async def execute(
        self,
        request: CompanyRiskRequest
    ) -> AnalysisResponse:
        """Execute the scenario and return analysis response."""
        pass
    
    def get_configuration_info(self, config: SearchConfig) -> dict:
        """Get information about how the scenario is configured."""
        return {
            "market": config.market if config.market else "DEFAULT",
            "count": config.count,
            "freshness": config.freshness,
            "set_lang": config.set_lang,
        }
    
    async def execute_streaming(
        self,
        request: CompanyRiskRequest
    ) -> AsyncIterator[str]:
        """Execute with streaming response (optional override)."""
        # Default implementation: yield full response
        response = await self.execute(request)
        yield response.text
