"""
HTTP Transport MCP Server for Bing Grounding

This version runs as an HTTP server that can be deployed to:
- Local Docker container
- Azure Container Apps
- Any container hosting platform

The server exposes Streamable HTTP endpoints as per MCP specification.
"""

import asyncio
import json
import logging
import os
from typing import Any

from aiohttp import web
from mcp.server import Server
from mcp.types import Tool, TextContent

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - Support both naming conventions for flexibility
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("PROJECT_ENDPOINT", "")
BING_CONNECTION_NAME = os.getenv("BING_PROJECT_CONNECTION_NAME") or os.getenv("BING_CONNECTION_NAME", "")
MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")
PORT = int(os.getenv("PORT", "8000"))

# Supported markets
SUPPORTED_MARKETS = [
    "en-US", "en-GB", "en-AU", "en-CA", "en-IN",
    "de-DE", "fr-FR", "es-ES", "it-IT", "pt-BR",
    "ja-JP", "ko-KR", "zh-CN", "zh-TW",
    "nl-NL", "pl-PL", "ru-RU", "sv-SE", "tr-TR",
    "ar-SA", "hi-IN", "th-TH", "vi-VN"
]

# Create MCP server
mcp_server = Server("bing-grounding-mcp")


def get_ai_project_client() -> AIProjectClient:
    """Get authenticated AI Project client."""
    if not PROJECT_ENDPOINT:
        raise ValueError("PROJECT_ENDPOINT environment variable not set")
    
    credential = DefaultAzureCredential()
    return AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)


async def perform_bing_search(query: str, market: str = "en-US") -> dict:
    """Perform a Bing grounded search using AI Foundry."""
    try:
        if market not in SUPPORTED_MARKETS:
            market = "en-US"
        
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
            instructions="You are a search assistant. Return comprehensive, factual results.",
            tools=bing_tool.definitions
        )
        
        try:
            thread = agents_client.threads.create()
            agents_client.messages.create(thread_id=thread.id, role="user", content=query)
            run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
            messages = agents_client.messages.list(thread_id=thread.id)
            
            result = {"query": query, "market": market, "status": run.status, "results": []}
            
            for msg in messages:
                if msg.role == "assistant" and msg.text_messages:
                    for text_msg in msg.text_messages:
                        result["results"].append({"content": text_msg.text.value})
            
            return result
        finally:
            agents_client.delete_agent(agent.id)
            
    except Exception as e:
        logger.error(f"Bing search error: {e}")
        return {"query": query, "market": market, "status": "error", "error": str(e)}


async def analyze_company_risk(company_name: str, risk_category: str, market: str) -> dict:
    """Analyze company risks using Bing grounded search."""
    queries = {
        "litigation": f"{company_name} lawsuits legal cases court filings",
        "labor_practices": f"{company_name} labor violations employee complaints child labor",
        "environmental": f"{company_name} environmental violations pollution ESG",
        "financial": f"{company_name} financial risks debt bankruptcy",
        "regulatory": f"{company_name} regulatory violations fines investigations",
        "reputation": f"{company_name} scandals controversies",
        "all": f"{company_name} risks controversies legal issues"
    }
    
    query = queries.get(risk_category, queries["all"])
    search_result = await perform_bing_search(query, market)
    
    return {
        "company": company_name,
        "risk_category": risk_category,
        "market": market,
        "search_results": search_result
    }


# ============================================================================
# HTTP Handlers for MCP
# ============================================================================

async def handle_initialize(request: web.Request) -> web.Response:
    """Handle MCP initialize request."""
    return web.json_response({
        "protocolVersion": "2024-11-05",
        "serverInfo": {
            "name": "bing-grounding-mcp",
            "version": "1.0.0"
        },
        "capabilities": {
            "tools": {}
        }
    })


async def handle_list_tools(request: web.Request) -> web.Response:
    """Handle MCP tools/list request."""
    tools = [
        {
            "name": "bing_grounded_search",
            "description": "Perform a Bing web search with grounding. Use 'market' for region-specific results.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "market": {"type": "string", "description": "Market code (e.g., 'en-US')", "default": "en-US"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "analyze_company_risk",
            "description": "Analyze a company for risk factors from an insurance perspective.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Company name to analyze"},
                    "risk_category": {
                        "type": "string",
                        "enum": ["litigation", "labor_practices", "environmental", "financial", "regulatory", "reputation", "all"],
                        "default": "all"
                    },
                    "market": {"type": "string", "default": "en-US"}
                },
                "required": ["company_name"]
            }
        },
        {
            "name": "list_supported_markets",
            "description": "List all supported market codes for Bing search.",
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        }
    ]
    
    return web.json_response({"tools": tools})


async def handle_call_tool(request: web.Request) -> web.Response:
    """Handle MCP tools/call request."""
    try:
        data = await request.json()
        params = data.get("params", {})
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        logger.info(f"Tool call: {name} with args: {arguments}")
        
        if name == "bing_grounded_search":
            query = arguments.get("query", "")
            market = arguments.get("market", "en-US")
            
            if not query:
                return web.json_response({"error": "Query is required"}, status=400)
            
            result = await perform_bing_search(query, market)
            return web.json_response({"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        
        elif name == "analyze_company_risk":
            company_name = arguments.get("company_name", "")
            risk_category = arguments.get("risk_category", "all")
            market = arguments.get("market", "en-US")
            
            if not company_name:
                return web.json_response({"error": "company_name is required"}, status=400)
            
            result = await analyze_company_risk(company_name, risk_category, market)
            return web.json_response({"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        
        elif name == "list_supported_markets":
            markets = [{"code": m, "description": m} for m in SUPPORTED_MARKETS]
            return web.json_response({"content": [{"type": "text", "text": json.dumps({"markets": markets}, indent=2)}]})
        
        else:
            return web.json_response({"error": f"Unknown tool: {name}"}, status=404)
    
    except Exception as e:
        logger.error(f"Error handling tool call: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_mcp(request: web.Request) -> web.Response:
    """Main MCP endpoint handler - routes JSON-RPC requests."""
    try:
        data = await request.json()
        method = data.get("method", "")
        request_id = data.get("id", "1")
        
        logger.info(f"MCP request: {method}")
        
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "bing-grounding-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            }
        elif method == "tools/list":
            tools = [
                {
                    "name": "bing_grounded_search",
                    "description": "Perform a Bing web search with grounding.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "market": {"type": "string", "default": "en-US"}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "analyze_company_risk",
                    "description": "Analyze company risks for insurance assessment.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "company_name": {"type": "string"},
                            "risk_category": {"type": "string", "default": "all"},
                            "market": {"type": "string", "default": "en-US"}
                        },
                        "required": ["company_name"]
                    }
                },
                {
                    "name": "list_supported_markets",
                    "description": "List supported market codes.",
                    "inputSchema": {"type": "object", "properties": {}}
                }
            ]
            result = {"tools": tools}
        elif method == "tools/call":
            params = data.get("params", {})
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            
            if name == "bing_grounded_search":
                search_result = await perform_bing_search(
                    arguments.get("query", ""),
                    arguments.get("market", "en-US")
                )
                result = {"content": [{"type": "text", "text": json.dumps(search_result, indent=2)}]}
            elif name == "analyze_company_risk":
                risk_result = await analyze_company_risk(
                    arguments.get("company_name", ""),
                    arguments.get("risk_category", "all"),
                    arguments.get("market", "en-US")
                )
                result = {"content": [{"type": "text", "text": json.dumps(risk_result, indent=2)}]}
            elif name == "list_supported_markets":
                result = {"content": [{"type": "text", "text": json.dumps({"markets": SUPPORTED_MARKETS})}]}
            else:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"}
                })
        else:
            return web.json_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}
            })
        
        return web.json_response({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        })
        
    except Exception as e:
        logger.error(f"MCP handler error: {e}")
        return web.json_response({
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"code": -32603, "message": str(e)}
        }, status=500)


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "healthy", "server": "bing-grounding-mcp"})


def create_app() -> web.Application:
    """Create and configure the aiohttp application."""
    app = web.Application()
    
    # MCP endpoints
    app.router.add_post("/mcp", handle_mcp)
    app.router.add_get("/health", health_check)
    
    return app


if __name__ == "__main__":
    logger.info(f"Starting Bing Grounding MCP HTTP Server on port {PORT}...")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
