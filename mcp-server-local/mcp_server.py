"""
Local MCP Server for Bing Grounding Search

This is a standalone MCP server that can be run locally or in a Docker container.
It uses the official MCP Python SDK and provides Bing grounding search tools
with runtime market parameter configuration.

Usage:
  Local (stdio): python mcp_server.py
  Docker: docker run -p 8000:8000 bing-mcp-server
"""

import asyncio
import json
import logging
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")
BING_CONNECTION_NAME = os.getenv("BING_CONNECTION_NAME", "")
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")

# Supported markets
SUPPORTED_MARKETS = [
    "en-US", "en-GB", "en-AU", "en-CA", "en-IN",
    "de-DE", "fr-FR", "es-ES", "it-IT", "pt-BR",
    "ja-JP", "ko-KR", "zh-CN", "zh-TW",
    "nl-NL", "pl-PL", "ru-RU", "sv-SE", "tr-TR",
    "ar-SA", "hi-IN", "th-TH", "vi-VN"
]

# Create MCP server instance
server = Server("bing-grounding-mcp")


def get_ai_project_client() -> AIProjectClient:
    """Get authenticated AI Project client."""
    if not PROJECT_ENDPOINT:
        raise ValueError("PROJECT_ENDPOINT environment variable not set")
    
    credential = DefaultAzureCredential()
    return AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential
    )


async def perform_bing_search(query: str, market: str = "en-US") -> dict:
    """
    Perform a Bing grounded search using the AI Foundry agent.
    """
    try:
        if market not in SUPPORTED_MARKETS:
            market = "en-US"
            logger.warning(f"Invalid market code, defaulting to en-US")
        
        client = get_ai_project_client()
        agents_client = client.agents
        
        from azure.ai.agents.models import BingGroundingTool, BingGroundingSearchConfiguration
        
        bing_tool = BingGroundingTool(
            bing_grounding_search=BingGroundingSearchConfiguration(
                connection_id=BING_CONNECTION_NAME,
                market=market
            )
        )
        
        agent = agents_client.create_agent(
            model=MODEL_DEPLOYMENT_NAME,
            name="bing-search-agent",
            instructions="You are a search assistant. Perform web searches and return comprehensive, factual results.",
            tools=bing_tool.definitions
        )
        
        try:
            thread = agents_client.threads.create()
            
            agents_client.messages.create(
                thread_id=thread.id,
                role="user",
                content=query
            )
            
            run = agents_client.runs.create_and_process(
                thread_id=thread.id,
                agent_id=agent.id
            )
            
            messages = agents_client.messages.list(thread_id=thread.id)
            
            result = {
                "query": query,
                "market": market,
                "status": run.status,
                "results": []
            }
            
            for msg in messages:
                if msg.role == "assistant" and msg.text_messages:
                    for text_msg in msg.text_messages:
                        result["results"].append({
                            "content": text_msg.text.value,
                            "annotations": [
                                {
                                    "type": getattr(ann, "type", "unknown"),
                                    "url": getattr(ann, "url", None),
                                    "title": getattr(ann, "title", None)
                                }
                                for ann in getattr(text_msg.text, "annotations", [])
                            ]
                        })
            
            return result
            
        finally:
            agents_client.delete_agent(agent.id)
            
    except Exception as e:
        logger.error(f"Bing search error: {e}")
        return {
            "query": query,
            "market": market,
            "status": "error",
            "error": str(e)
        }


async def analyze_company_risk(company_name: str, risk_category: str, market: str = "en-US") -> dict:
    """Analyze company risks using Bing grounded search."""
    queries = {
        "litigation": f"{company_name} lawsuits legal cases court filings settlements",
        "labor_practices": f"{company_name} labor violations employee complaints working conditions child labor",
        "environmental": f"{company_name} environmental violations pollution sustainability ESG",
        "financial": f"{company_name} financial risks debt credit rating bankruptcy concerns",
        "regulatory": f"{company_name} regulatory violations fines compliance issues investigations",
        "reputation": f"{company_name} scandals controversies negative news reputation issues",
        "all": f"{company_name} risks controversies legal issues ESG concerns"
    }
    
    query = queries.get(risk_category, queries["all"])
    
    try:
        search_result = await perform_bing_search(query, market)
        
        return {
            "company": company_name,
            "risk_category": risk_category,
            "market": market,
            "query_used": query,
            "search_results": search_result
        }
    except Exception as e:
        return {
            "company": company_name,
            "risk_category": risk_category,
            "market": market,
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# MCP Tool Definitions
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return [
        Tool(
            name="bing_grounded_search",
            description=(
                "Perform a Bing web search with grounding. Returns factual, sourced information "
                "from the web. Use the 'market' parameter to get region-specific results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to send to Bing. Should be a clear, specific question or topic."
                    },
                    "market": {
                        "type": "string",
                        "description": f"The market/region code for localized results (e.g., 'en-US', 'de-DE'). Default: 'en-US'",
                        "default": "en-US",
                        "enum": SUPPORTED_MARKETS
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="analyze_company_risk",
            description=(
                "Analyze a company for various risk factors from an insurance perspective. "
                "Searches for litigation history, labor practices, environmental issues, "
                "financial risks, regulatory compliance, and reputation concerns."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The name of the company to analyze for risks."
                    },
                    "risk_category": {
                        "type": "string",
                        "description": "The risk category to focus on.",
                        "enum": ["litigation", "labor_practices", "environmental", "financial", "regulatory", "reputation", "all"],
                        "default": "all"
                    },
                    "market": {
                        "type": "string",
                        "description": "The market/region code for localized results. Use the market where the company primarily operates.",
                        "default": "en-US",
                        "enum": SUPPORTED_MARKETS
                    }
                },
                "required": ["company_name"]
            }
        ),
        Tool(
            name="list_supported_markets",
            description="List all supported market codes for Bing search with their descriptions.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    try:
        if name == "bing_grounded_search":
            query = arguments.get("query", "")
            market = arguments.get("market", "en-US")
            
            if not query:
                return [TextContent(type="text", text=json.dumps({"error": "Query parameter is required"}))]
            
            result = await perform_bing_search(query, market)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "analyze_company_risk":
            company_name = arguments.get("company_name", "")
            risk_category = arguments.get("risk_category", "all")
            market = arguments.get("market", "en-US")
            
            if not company_name:
                return [TextContent(type="text", text=json.dumps({"error": "company_name parameter is required"}))]
            
            result = await analyze_company_risk(company_name, risk_category, market)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "list_supported_markets":
            market_info = {
                "markets": [
                    {"code": code, "description": desc}
                    for code, desc in [
                        ("en-US", "English - United States"),
                        ("en-GB", "English - United Kingdom"),
                        ("en-AU", "English - Australia"),
                        ("de-DE", "German - Germany"),
                        ("fr-FR", "French - France"),
                        ("es-ES", "Spanish - Spain"),
                        ("ja-JP", "Japanese - Japan"),
                        ("zh-CN", "Chinese - China"),
                        # ... add more as needed
                    ]
                ],
                "default": "en-US",
                "total_supported": len(SUPPORTED_MARKETS)
            }
            return [TextContent(type="text", text=json.dumps(market_info, indent=2))]
        
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    """Run the MCP server."""
    logger.info("Starting Bing Grounding MCP Server...")
    logger.info(f"Project Endpoint: {PROJECT_ENDPOINT[:50]}..." if PROJECT_ENDPOINT else "PROJECT_ENDPOINT not set")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
