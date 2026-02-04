"""
Bing tool builder for creating configured Bing grounding tools.

Handles the creation of BingGroundingAgentTool with proper configuration.
"""
import logging
from typing import Optional
from azure.ai.projects.models import (
    BingGroundingAgentTool,
    BingGroundingSearchToolParameters,
    BingGroundingSearchConfiguration,
)
from core.models import SearchConfig

logger = logging.getLogger(__name__)


class BingToolBuilder:
    """Builder for creating Bing grounding tools with configuration."""
    
    def __init__(self, bing_connection_id: str):
        """
        Initialize the builder.
        
        Args:
            bing_connection_id: The Bing connection ID from Azure
        """
        self.bing_connection_id = bing_connection_id
    
    def build(self, config: SearchConfig) -> BingGroundingAgentTool:
        """
        Build a Bing grounding tool with the given configuration.
        
        Args:
            config: Search configuration
            
        Returns:
            Configured BingGroundingAgentTool
        """
        config_params = {
            "project_connection_id": self.bing_connection_id,
            "count": config.count,
            "freshness": config.freshness,
        }
        
        # Only add market if specified
        if config.market is not None:
            config_params["market"] = config.market
        
        # Only add set_lang if specified
        if config.set_lang is not None:
            config_params["set_lang"] = config.set_lang
        
        search_config = BingGroundingSearchConfiguration(**config_params)
        
        logger.debug(f"Created Bing tool config: market={config.market}, count={config.count}")
        
        return BingGroundingAgentTool(
            bing_grounding=BingGroundingSearchToolParameters(
                search_configurations=[search_config]
            )
        )
    
    def get_config_info(self, config: SearchConfig) -> dict:
        """
        Get information about the tool configuration.
        
        Args:
            config: Search configuration
            
        Returns:
            Dictionary describing the configuration
        """
        return {
            "market": config.market if config.market else "DEFAULT (Bing determines)",
            "count": config.count,
            "freshness": config.freshness,
            "set_lang": config.set_lang,
            "connection_id": self.bing_connection_id,
            "configuration_location": "BingGroundingSearchConfiguration",
        }
