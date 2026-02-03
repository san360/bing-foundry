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

from azure.identity import (
    DefaultAzureCredential,
    AzureCliCredential,
    VisualStudioCodeCredential,
    EnvironmentCredential,
    ManagedIdentityCredential,
    ChainedTokenCredential,
)
from azure.ai.projects import AIProjectClient

# OpenTelemetry tracing
try:
    from opentelemetry import trace
except ImportError:
    trace = None

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


def setup_tracing() -> None:
    """Configure OpenTelemetry tracing for MCP server."""
    if os.environ.get("OTEL_CONFIGURED") == "true":
        return

    if not PROJECT_ENDPOINT:
        logger.warning("PROJECT_ENDPOINT not set - tracing disabled")
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from azure.core.settings import settings

        credential = ChainedTokenCredential(
            EnvironmentCredential(),
            AzureCliCredential(),
            VisualStudioCodeCredential(),
            ManagedIdentityCredential(),
        )
        project_client = AIProjectClient(
            credential=credential,
            endpoint=PROJECT_ENDPOINT,
        )

        connection_string = project_client.telemetry.get_application_insights_connection_string()
        if not connection_string:
            logger.warning("No Application Insights connected to project - tracing disabled")
            return

        os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

        settings.tracing_implementation = "opentelemetry"
        configure_azure_monitor(connection_string=connection_string, enable_live_metrics=True)

        try:
            from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
            if os.environ.get("OTEL_OPENAI_INSTRUMENTED") != "true":
                OpenAIInstrumentor().instrument()
                os.environ["OTEL_OPENAI_INSTRUMENTED"] = "true"
        except ImportError as e:
            logger.warning(
                f"opentelemetry-instrumentation-openai-v2 not installed - OpenAI calls won't be traced: {e}"
            )

        os.environ["OTEL_CONFIGURED"] = "true"
        logger.info("OpenTelemetry tracing configured for MCP server")
    except Exception as e:
        logger.warning(f"Failed to configure tracing for MCP server: {e}")


def get_tracer():
    if trace is None:
        return None
    return trace.get_tracer("mcp-server")


def get_ai_project_client() -> AIProjectClient:
    """Get authenticated AI Project client."""
    if not PROJECT_ENDPOINT:
        raise ValueError("PROJECT_ENDPOINT environment variable not set")

    # Prefer local dev credentials to avoid noisy DefaultAzureCredential errors
    credential = ChainedTokenCredential(
        EnvironmentCredential(),
        AzureCliCredential(),
        VisualStudioCodeCredential(),
        ManagedIdentityCredential(),
    )
    return AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)


async def perform_bing_search(query: str, market: str = "en-US") -> dict:
    """Perform a Bing grounded search using AI Foundry."""
    try:
        tracer = get_tracer()
        if market not in SUPPORTED_MARKETS:
            market = "en-US"

        span_cm = (
            tracer.start_as_current_span(
                "mcp.bing_grounded_search",
                attributes={
                    "mcp.market": market,
                    "mcp.query_length": len(query),
                },
            )
            if tracer
            else None
        )
        if span_cm:
            span_cm.__enter__()
        
        client = get_ai_project_client()
        openai_client = client.get_openai_client()

        from azure.ai.projects.models import (
            PromptAgentDefinition,
            BingGroundingAgentTool,
            BingGroundingSearchConfiguration,
            BingGroundingSearchToolParameters,
        )

        # Resolve connection ID from name
        bing_connection = client.connections.get(BING_CONNECTION_NAME)

        bing_tool = BingGroundingAgentTool(
            bing_grounding=BingGroundingSearchToolParameters(
                search_configurations=[
                    BingGroundingSearchConfiguration(
                        project_connection_id=bing_connection.id,
                        market=market,
                    )
                ]
            )
        )

        agent = client.agents.create_version(
            agent_name=f"bing-search-agent-{market}",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions="You are a search assistant. Return comprehensive, factual results.",
                tools=[bing_tool],
            ),
            description="Bing search agent for MCP server",
        )

        try:
            response = openai_client.responses.create(
                tool_choice="required",
                input=query,
                extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
            )

            result = {"query": query, "market": market, "status": "completed", "results": []}
            if response.output_text:
                result["results"].append({"content": response.output_text})

            return result
        finally:
            client.agents.delete_version(
                agent_name=agent.name,
                agent_version=agent.version,
            )
            if span_cm:
                span_cm.__exit__(None, None, None)
            
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
        tracer = get_tracer()
        span_cm = (
            tracer.start_as_current_span(
                "mcp.tool_call",
                attributes={
                    "mcp.tool_name": name,
                },
            )
            if tracer
            else None
        )
        if span_cm:
            span_cm.__enter__()
        
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
    finally:
        if 'span_cm' in locals() and span_cm:
            span_cm.__exit__(None, None, None)


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
            tracer = get_tracer()
            span_cm = (
                tracer.start_as_current_span(
                    "mcp.tool_call",
                    attributes={
                        "mcp.tool_name": name,
                    },
                )
                if tracer
                else None
            )
            if span_cm:
                span_cm.__enter__()
            
            try:
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
            finally:
                if span_cm:
                    span_cm.__exit__(None, None, None)
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
    setup_tracing()
    app = web.Application()
    
    # MCP endpoints
    app.router.add_post("/mcp", handle_mcp)
    app.router.add_get("/health", health_check)
    
    return app


if __name__ == "__main__":
    logger.info(f"Starting Bing Grounding MCP HTTP Server on port {PORT}...")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
