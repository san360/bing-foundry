"""
Company Risk Analysis Agent using Azure AI Foundry with Bing Grounding

This module demonstrates:
1. How to configure the Bing grounding tool with the 'market' parameter
2. The difference between specifying market vs. using defaults
3. Runtime configuration of the market parameter
"""
import os
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator, Any
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    BingGroundingAgentTool,
    BingGroundingSearchToolParameters,
    BingGroundingSearchConfiguration,
)

from .prompts import AGENT_SYSTEM_INSTRUCTION


@dataclass
class AgentResponse:
    """Response from the agent"""
    text: str
    citations: list[dict] = field(default_factory=list)
    raw_response: Any = None
    market_used: Optional[str] = None
    tool_configuration: dict = field(default_factory=dict)


class CompanyRiskAgent:
    """
    Company Risk Analysis Agent with Bing Grounding
    
    This agent demonstrates how to:
    - Configure Bing grounding with different market parameters
    - Pass market at runtime vs. agent creation time
    - Handle default behavior when no market is specified
    
    KEY INSIGHT: The 'market' parameter is configured in BingGroundingSearchConfiguration,
    NOT at the agent level. This means you can:
    1. Create different tool configurations for different markets
    2. Dynamically create agents with market-specific tools at runtime
    """
    
    def __init__(
        self,
        project_endpoint: str,
        model_deployment_name: str,
        bing_connection_name: str,
    ):
        """
        Initialize the Company Risk Agent.
        
        Args:
            project_endpoint: Azure AI Project endpoint URL
            model_deployment_name: Name of the deployed model (e.g., 'gpt-4o')
            bing_connection_name: Name of the Bing connection in the project
        """
        self.project_endpoint = project_endpoint
        self.model_deployment_name = model_deployment_name
        self.bing_connection_name = bing_connection_name
        
        self._credential = None
        self._project_client = None
        self._openai_client = None
        self._bing_connection_id = None
        
    async def _ensure_initialized(self):
        """Ensure clients are initialized"""
        if self._project_client is None:
            self._credential = DefaultAzureCredential()
            self._project_client = AIProjectClient(
                endpoint=self.project_endpoint,
                credential=self._credential,
            )
            self._openai_client = self._project_client.get_openai_client()
            
            # Get Bing connection ID
            bing_connection = self._project_client.connections.get(
                self.bing_connection_name
            )
            self._bing_connection_id = bing_connection.id
            
    def _create_bing_tool(
        self,
        market: Optional[str] = None,
        count: int = 10,
        freshness: str = "Month",
        set_lang: Optional[str] = None,
    ) -> BingGroundingAgentTool:
        """
        Create a Bing grounding tool with specific configuration.
        
        THIS IS WHERE THE MARKET PARAMETER IS CONFIGURED!
        
        The market parameter is part of the search configuration, not the agent.
        This allows for runtime configuration by creating tools dynamically.
        
        Args:
            market: Market code (e.g., 'de-CH', 'en-US'). 
                    If None, Bing uses default based on request origin.
            count: Number of search results (default 10, max 50)
            freshness: Time filter - 'Day', 'Week', 'Month', or date range
            set_lang: UI language code (e.g., 'en', 'de')
            
        Returns:
            Configured BingGroundingAgentTool
        """
        # Build the search configuration
        # NOTE: This is where you control market-specific behavior!
        config_params = {
            "project_connection_id": self._bing_connection_id,
            "count": count,
            "freshness": freshness,
        }
        
        # Only add market if specified - this tests default behavior
        if market is not None:
            config_params["market"] = market
            
        # Only add set_lang if specified
        if set_lang is not None:
            config_params["set_lang"] = set_lang
            
        search_config = BingGroundingSearchConfiguration(**config_params)
        
        return BingGroundingAgentTool(
            bing_grounding=BingGroundingSearchToolParameters(
                search_configurations=[search_config]
            )
        )
        
    def get_tool_configuration_info(
        self,
        market: Optional[str] = None,
        count: int = 10,
        freshness: str = "Month",
    ) -> dict:
        """
        Get information about how the tool would be configured.
        Useful for displaying in the UI.
        
        Args:
            market: Market code or None for default
            count: Number of results
            freshness: Freshness filter
            
        Returns:
            Dictionary describing the configuration
        """
        return {
            "market": market if market else "DEFAULT (determined by Bing based on request origin)",
            "count": count,
            "freshness": freshness,
            "connection_name": self.bing_connection_name,
            "configuration_location": "BingGroundingSearchConfiguration",
            "note": (
                "The market parameter is set at the TOOL level, not agent level. "
                "This means each search configuration can have a different market."
            ),
        }
        
    async def analyze_company(
        self,
        prompt: str,
        market: Optional[str] = None,
        count: int = 10,
        freshness: str = "Month",
    ) -> AgentResponse:
        """
        Analyze a company using Bing-grounded search.
        
        DEMONSTRATES: Runtime market configuration
        
        The market parameter is passed here and used to create a tool
        with the appropriate configuration. This allows different 
        searches to use different markets without creating multiple agents.
        
        Args:
            prompt: The analysis prompt
            market: Market code (e.g., 'de-CH'). None uses Bing's default.
            count: Number of search results
            freshness: Freshness filter
            
        Returns:
            AgentResponse with analysis results
        """
        await self._ensure_initialized()
        
        # Create tool with specified market configuration
        # THIS IS THE KEY: Market is set per-tool, per-request!
        bing_tool = self._create_bing_tool(
            market=market,
            count=count,
            freshness=freshness,
        )
        
        # Create agent with this specific tool configuration
        agent = self._project_client.agents.create_version(
            agent_name=f"CompanyRiskAnalyst-{market or 'default'}",
            definition=PromptAgentDefinition(
                model=self.model_deployment_name,
                instructions=AGENT_SYSTEM_INSTRUCTION,
                tools=[bing_tool],
            ),
            description="Company risk analysis agent with Bing grounding",
        )
        
        try:
            # Execute the analysis
            response = self._openai_client.responses.create(
                tool_choice="required",  # Force use of Bing tool
                input=prompt,
                extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
            )
            
            # Extract citations
            citations = []
            for item in response.output:
                if hasattr(item, 'content'):
                    for content in item.content:
                        if hasattr(content, 'annotations'):
                            for annotation in content.annotations:
                                if hasattr(annotation, 'url'):
                                    citations.append({
                                        "url": annotation.url,
                                        "title": getattr(annotation, 'title', ''),
                                        "start_index": getattr(annotation, 'start_index', 0),
                                        "end_index": getattr(annotation, 'end_index', 0),
                                    })
            
            return AgentResponse(
                text=response.output_text,
                citations=citations,
                raw_response=response,
                market_used=market,
                tool_configuration=self.get_tool_configuration_info(market, count, freshness),
            )
            
        finally:
            # Clean up the agent version
            self._project_client.agents.delete_version(
                agent_name=agent.name, 
                agent_version=agent.version
            )
            
    async def analyze_company_streaming(
        self,
        prompt: str,
        market: Optional[str] = None,
        count: int = 10,
        freshness: str = "Month",
    ) -> AsyncIterator[str]:
        """
        Analyze a company with streaming response.
        
        Args:
            prompt: The analysis prompt
            market: Market code (e.g., 'de-CH'). None uses Bing's default.
            count: Number of search results
            freshness: Freshness filter
            
        Yields:
            Text chunks as they arrive
        """
        await self._ensure_initialized()
        
        # Create tool with specified market configuration
        bing_tool = self._create_bing_tool(
            market=market,
            count=count,
            freshness=freshness,
        )
        
        # Create agent
        agent = self._project_client.agents.create_version(
            agent_name=f"CompanyRiskAnalyst-Stream-{market or 'default'}",
            definition=PromptAgentDefinition(
                model=self.model_deployment_name,
                instructions=AGENT_SYSTEM_INSTRUCTION,
                tools=[bing_tool],
            ),
        )
        
        try:
            # Stream the response
            stream_response = self._openai_client.responses.create(
                stream=True,
                tool_choice="required",
                input=prompt,
                extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
            )
            
            for event in stream_response:
                if event.type == "response.output_text.delta":
                    yield event.delta
                elif event.type == "response.output_item.done":
                    # Yield citations at the end
                    if event.item.type == "message":
                        item = event.item
                        if item.content and len(item.content) > 0:
                            last_content = item.content[-1]
                            if hasattr(last_content, 'annotations'):
                                for annotation in last_content.annotations:
                                    if annotation.type == "url_citation":
                                        yield f"\n[Source: {annotation.url}]"
                                        
        finally:
            # Clean up
            self._project_client.agents.delete_version(
                agent_name=agent.name,
                agent_version=agent.version
            )
            
    async def close(self):
        """Close the client connections"""
        if self._project_client:
            self._project_client.close()
        if self._credential:
            self._credential.close()
