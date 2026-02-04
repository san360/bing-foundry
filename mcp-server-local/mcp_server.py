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

# Configure logging - Reduce verbose HTTP/Azure logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence noisy loggers
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline').setLevel(logging.ERROR)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)

# Configuration - Support both naming conventions
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("PROJECT_ENDPOINT", "")
BING_CONNECTION_NAME = os.getenv("BING_PROJECT_CONNECTION_NAME") or os.getenv("BING_CONNECTION_NAME", "")
MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")

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
    return AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential
    )


async def perform_bing_search(query: str, market: str = "en-US") -> dict:
    """
    Perform a Bing grounded search using the AI Foundry agent.
    """
    try:
        tracer = get_tracer()
        if market not in SUPPORTED_MARKETS:
            market = "en-US"
            logger.warning(f"Invalid market code, defaulting to en-US")
        
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
                instructions=(
                    "You are a search assistant. Perform web searches and return comprehensive, factual results."
                ),
                tools=[bing_tool],
            ),
            description="Bing search agent for MCP server",
        )
        
        logger.info(f"✅ MCP: Created agent {agent.name} (v{agent.version}) for market={market}")

        try:
            response = openai_client.responses.create(
                tool_choice="required",
                input=query,
                extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
            )

            result = {
                "query": query,
                "market": market,
                "status": "completed",
                "agent_id": agent.id,
                "agent_name": agent.name,
                "agent_version": agent.version,
                "results": [],
            }

            if response.output_text:
                result["results"].append({"content": response.output_text})

            return result
        finally:
            client.agents.delete_version(
                agent_name=agent.name,
                agent_version=agent.version,
            )
            logger.info(f"🗑️  MCP: Cleaned up agent {agent.name}")
            if span_cm:
                span_cm.__exit__(None, None, None)
            
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
    tracer = get_tracer()
    span_cm = (
        tracer.start_as_current_span(
            "mcp.analyze_company_risk",
            attributes={
                "mcp.company_name": company_name,
                "mcp.risk_category": risk_category,
                "mcp.market": market,
            },
        )
        if tracer
        else None
    )
    if span_cm:
        span_cm.__enter__()

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
    finally:
        if span_cm:
            span_cm.__exit__(None, None, None)


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
    finally:
        if span_cm:
            span_cm.__exit__(None, None, None)


async def main():
    """Run the MCP server."""
    logger.info("Starting Bing Grounding MCP Server...")
    logger.info(f"Project Endpoint: {PROJECT_ENDPOINT[:50]}..." if PROJECT_ENDPOINT else "PROJECT_ENDPOINT not set")
    setup_tracing()
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
