"""
Azure client factory and management.

Provides centralized Azure client creation and connection management.
"""
import logging
from typing import Optional
from azure.identity import (
    AzureCliCredential,
    VisualStudioCodeCredential,
    EnvironmentCredential,
    ManagedIdentityCredential,
    ChainedTokenCredential,
)
from azure.ai.projects import AIProjectClient
from core.interfaces import IAzureClientFactory
from infrastructure.config import AzureConfig

logger = logging.getLogger(__name__)


class AzureClientFactory(IAzureClientFactory):
    """Factory for creating and managing Azure clients."""
    
    def __init__(self, config: AzureConfig):
        """
        Initialize the factory.
        
        Args:
            config: Azure configuration
        """
        self.config = config
        self._credential: Optional[ChainedTokenCredential] = None
        self._project_client: Optional[AIProjectClient] = None
        self._openai_client = None
        self._bing_connection_id: Optional[str] = None
    
    def _ensure_credential(self) -> ChainedTokenCredential:
        """Get or create credential chain."""
        if self._credential is None:
            self._credential = ChainedTokenCredential(
                EnvironmentCredential(),
                AzureCliCredential(),
                VisualStudioCodeCredential(),
                ManagedIdentityCredential(),
            )
        return self._credential
    
    def get_project_client(self) -> AIProjectClient:
        """Get AI Project client."""
        if self._project_client is None:
            credential = self._ensure_credential()
            self._project_client = AIProjectClient(
                endpoint=self.config.project_endpoint,
                credential=credential,
            )
            logger.info("Created AI Project client")
        return self._project_client
    
    def get_openai_client(self):
        """Get OpenAI client from project."""
        if self._openai_client is None:
            project_client = self.get_project_client()
            self._openai_client = project_client.get_openai_client()
            logger.info("Created OpenAI client")
        return self._openai_client
    
    def get_bing_connection_id(self) -> str:
        """Get Bing connection ID."""
        if self._bing_connection_id is None:
            project_client = self.get_project_client()
            bing_connection = project_client.connections.get(
                self.config.bing_connection_name
            )
            self._bing_connection_id = bing_connection.id
            logger.info(f"Retrieved Bing connection ID")
        return self._bing_connection_id
    
    def close(self):
        """Close all clients and credentials."""
        if self._project_client:
            self._project_client.close()
        if self._credential:
            self._credential.close()
        logger.info("Closed Azure clients")
