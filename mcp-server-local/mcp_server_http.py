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

import httpx
from azure.identity import (
    DefaultAzureCredential,
    AzureCliCredential,
    VisualStudioCodeCredential,
    EnvironmentCredential,
    ManagedIdentityCredential,
    ChainedTokenCredential,
)
from azure.ai.projects import AIProjectClient
from azure.core.credentials import AccessToken

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
logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline').setLevel(logging.ERROR)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)

# Configuration - Support both naming conventions for flexibility
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("PROJECT_ENDPOINT", "")
BING_CONNECTION_NAME = os.getenv("BING_PROJECT_CONNECTION_NAME") or os.getenv("BING_CONNECTION_NAME", "")
MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")
PORT = int(os.getenv("PORT", "8000"))
# API version for Foundry Project REST API
API_VERSION = os.getenv("API_VERSION", "2025-11-15-preview")

# Cache for credentials and connection info
_cached_credential = None
_cached_bing_connection_id = None
_cached_token: AccessToken = None

# Supported Bing market codes (from Microsoft documentation)
# Reference: https://learn.microsoft.com/en-us/previous-versions/bing/search-apis/bing-web-search/reference/market-codes
SUPPORTED_MARKETS = [
    # Americas
    "en-US",  # United States (English)
    "es-US",  # United States (Spanish)
    "en-CA",  # Canada (English)
    "fr-CA",  # Canada (French)
    "es-MX",  # Mexico (Spanish)
    "pt-BR",  # Brazil (Portuguese)
    "es-AR",  # Argentina (Spanish)
    "es-CL",  # Chile (Spanish)
    # Europe
    "en-GB",  # United Kingdom (English)
    "de-DE",  # Germany (German)
    "de-AT",  # Austria (German)
    "de-CH",  # Switzerland (German)
    "fr-FR",  # France (French)
    "fr-BE",  # Belgium (French)
    "fr-CH",  # Switzerland (French)
    "es-ES",  # Spain (Spanish)
    "it-IT",  # Italy (Italian)
    "nl-NL",  # Netherlands (Dutch)
    "nl-BE",  # Belgium (Dutch)
    "pl-PL",  # Poland (Polish)
    "ru-RU",  # Russia (Russian)
    "sv-SE",  # Sweden (Swedish)
    "da-DK",  # Denmark (Danish)
    "fi-FI",  # Finland (Finnish)
    "no-NO",  # Norway (Norwegian)
    "tr-TR",  # Turkey (Turkish)
    # Asia Pacific
    "ja-JP",  # Japan (Japanese)
    "ko-KR",  # Korea (Korean)
    "zh-CN",  # China (Chinese Simplified)
    "zh-TW",  # Taiwan (Chinese Traditional)
    "zh-HK",  # Hong Kong (Chinese Traditional)
    "en-AU",  # Australia (English)
    "en-NZ",  # New Zealand (English)
    "en-IN",  # India (English)
    "en-PH",  # Philippines (English)
    "en-MY",  # Malaysia (English)
    "en-ID",  # Indonesia (English)
    "en-ZA",  # South Africa (English)
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

        # Standard naming: BingFoundry-MCP-SearchAgent (no market in name)
        agent_name = "BingFoundry-MCP-SearchAgent"

        # Try to find existing agent
        agent = None
        try:
            agents = list(client.agents.list())
            logger.info(f"Found {len(agents)} agents in project")
            for existing_agent in agents:
                if existing_agent.name == agent_name:
                    logger.info(f"♻️  Reusing existing search agent: {agent_name} (v{existing_agent.version})")
                    agent = existing_agent
                    break
            if agent is None:
                logger.info(f"Agent '{agent_name}' not found, will create new")
        except Exception as e:
            logger.warning(f"Could not list agents: {e}")
        
        # Create new agent if not found
        if agent is None:
            agent = client.agents.create_version(
                agent_name=agent_name,
                definition=PromptAgentDefinition(
                    model=MODEL_DEPLOYMENT_NAME,
                    instructions="You are a search assistant. Return comprehensive, factual results. You MUST use the Bing tool.",
                    tools=[bing_tool],
                ),
                description="Bing search agent for MCP server",
            )
            logger.info(f"✅ Created new search agent: {agent.name}")

        response = openai_client.responses.create(
            tool_choice="required",
            input=query,
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )

        result = {"query": query, "market": market, "status": "completed", "results": []}
        if response.output_text:
            result["results"].append({"content": response.output_text})

        if span_cm:
            span_cm.__exit__(None, None, None)
            
        return result
            
    except Exception as e:
        logger.error(f"Bing search error: {e}")
        return {"query": query, "market": market, "status": "error", "error": str(e)}


def _get_credential():
    """Get or create cached credential."""
    global _cached_credential
    if _cached_credential is None:
        _cached_credential = ChainedTokenCredential(
            EnvironmentCredential(),
            AzureCliCredential(),
            VisualStudioCodeCredential(),
            ManagedIdentityCredential(),
        )
    return _cached_credential


def _get_access_token() -> str:
    """Get or refresh access token for Azure AI Foundry."""
    global _cached_token
    import time
    
    # Check if we need a new token (expired or will expire in 5 minutes)
    if _cached_token is None or _cached_token.expires_on < time.time() + 300:
        credential = _get_credential()
        _cached_token = credential.get_token("https://ai.azure.com/.default")
    return _cached_token.token


def _get_bing_connection_id() -> str:
    """Get or cache the Bing connection ID."""
    global _cached_bing_connection_id
    if _cached_bing_connection_id is None:
        client = get_ai_project_client()
        bing_connection = client.connections.get(BING_CONNECTION_NAME)
        _cached_bing_connection_id = bing_connection.id
        logger.info(f"Cached Bing connection ID: {_cached_bing_connection_id}")
    return _cached_bing_connection_id


async def perform_bing_search_rest_api(
    query: str,
    market: str = "en-US",
    count: int = 7,
    freshness: str = "Month",
    set_lang: str = "en"
) -> dict:
    """
    Perform a Bing grounded search using the REST API directly.
    
    This is Scenario 3: MCP Tool calling Bing REST API directly without creating an agent.
    
    REST API endpoint: POST {PROJECT_ENDPOINT}/openai/responses?api-version={API_VERSION}
    
    Args:
        query: The search query
        market: Market code (e.g., 'en-US', 'de-DE')
        count: Number of search results (1-50, default 7)
        freshness: Time filter - 'Day', 'Week', 'Month', or date range
        set_lang: UI language code
        
    Returns:
        Dictionary with search results, citations, and metadata
    """
    tracer = get_tracer()
    span_cm = None
    
    try:
        if market not in SUPPORTED_MARKETS:
            market = "en-US"
            logger.warning(f"Invalid market code, defaulting to en-US")
        
        if tracer:
            span_cm = tracer.start_as_current_span(
                "mcp.bing_search_rest_api",
                attributes={
                    "mcp.market": market,
                    "mcp.query_length": len(query),
                    "mcp.method": "rest_api",
                    "mcp.count": count,
                    "mcp.freshness": freshness,
                },
            )
            span_cm.__enter__()
        
        # Get connection ID and access token
        bing_connection_id = _get_bing_connection_id()
        access_token = _get_access_token()
        
        # Build the REST API request for Foundry Project endpoint
        # Reference: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/bing-tools?pivots=rest
        # Note: For Foundry Project endpoints, use /openai/responses with api-version
        # (The /openai/v1/ path is only for Azure OpenAI resource endpoints)
        url = f"{PROJECT_ENDPOINT}/openai/responses?api-version={API_VERSION}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        
        # Build the request payload with bing_grounding tool
        payload = {
            "model": MODEL_DEPLOYMENT_NAME,
            "input": query,
            "tool_choice": "required",
            "tools": [
                {
                    "type": "bing_grounding",
                    "bing_grounding": {
                        "search_configurations": [
                            {
                                "project_connection_id": bing_connection_id,
                                "count": count,
                                "market": market,
                                "set_lang": set_lang,
                                "freshness": freshness.lower() if freshness in ["Day", "Week", "Month"] else freshness,
                            }
                        ]
                    }
                }
            ]
        }
        
        logger.info(f"Calling Bing REST API: {url}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Make the REST API call
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Bing REST API error: HTTP {response.status_code} - {error_text}")
                return {
                    "query": query,
                    "market": market,
                    "method": "rest_api",
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {error_text[:500]}",
                }
            
            data = response.json()
            logger.debug(f"REST API Response: {json.dumps(data, indent=2)[:1000]}...")
        
        # Extract results from the response
        result = {
            "query": query,
            "market": market,
            "method": "rest_api",
            "status": "completed",
            "api_version": API_VERSION,
            "response_id": data.get("id", ""),
            "model": data.get("model", MODEL_DEPLOYMENT_NAME),
            "results": [],
            "citations": [],
        }
        
        # Extract output text
        output_text = data.get("output_text", "")
        if not output_text:
            # Try to extract from output array
            for output_item in data.get("output", []):
                if output_item.get("type") == "message":
                    for content in output_item.get("content", []):
                        if content.get("type") == "output_text":
                            output_text = content.get("text", "")
                            # Extract citations from annotations
                            for annotation in content.get("annotations", []):
                                if annotation.get("type") == "url_citation":
                                    result["citations"].append({
                                        "url": annotation.get("url", ""),
                                        "title": annotation.get("title", ""),
                                        "start_index": annotation.get("start_index"),
                                        "end_index": annotation.get("end_index"),
                                    })
        
        if output_text:
            result["results"].append({"content": output_text})
        
        # Add usage information if available
        if "usage" in data:
            result["usage"] = data["usage"]
        
        return result
        
    except Exception as e:
        logger.error(f"Bing REST API search error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "query": query,
            "market": market,
            "method": "rest_api",
            "status": "error",
            "error": str(e),
        }
    finally:
        if span_cm:
            span_cm.__exit__(None, None, None)


async def analyze_company_risk_rest_api(
    company_name: str,
    risk_category: str,
    market: str = "en-US",
    count: int = 7,
    freshness: str = "Month"
) -> dict:
    """
    Analyze company risks using Bing REST API directly (Scenario 3).
    
    This demonstrates calling the Bing grounding REST API without creating an agent.
    """
    queries = {
        "litigation": f"{company_name} lawsuits legal cases court filings recent news",
        "labor_practices": f"{company_name} labor violations employee complaints child labor workplace issues",
        "environmental": f"{company_name} environmental violations pollution ESG sustainability issues",
        "financial": f"{company_name} financial risks debt bankruptcy credit rating concerns",
        "regulatory": f"{company_name} regulatory violations fines investigations compliance issues",
        "reputation": f"{company_name} scandals controversies negative press reputational risks",
        "all": f"{company_name} risks controversies legal issues regulatory violations ESG concerns"
    }
    
    query = queries.get(risk_category, queries["all"])
    search_result = await perform_bing_search_rest_api(query, market, count, freshness)
    
    return {
        "company": company_name,
        "risk_category": risk_category,
        "market": market,
        "method": "rest_api",
        "search_results": search_result
    }


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


async def create_and_run_bing_agent(
    company_name: str,
    risk_category: str,
    market: str = "en-US",
    count: int = 10,
    freshness: str = "Month"
) -> dict:
    """
    Create a Worker Agent with Bing tool, run search, and delete the agent.
    
    This is the key function for Scenario 2's Two-Agent Pattern:
    - Creates an ephemeral Worker Agent (Agent 2) with market-specific Bing config
    - Executes the search query
    - Deletes the Worker Agent after getting results
    
    Args:
        company_name: Company to analyze
        risk_category: Type of risk analysis
        market: Bing market code (e.g., 'en-US', 'de-DE')
        count: Number of search results
        freshness: Time filter ('Day', 'Week', 'Month')
        
    Returns:
        Dict with agent info, search results, and confirmation of cleanup
    """
    tracer = get_tracer()
    span_cm = None
    
    if tracer:
        span_cm = tracer.start_as_current_span(
            "mcp.create_and_run_bing_agent",
            attributes={
                "mcp.company": company_name,
                "mcp.risk_category": risk_category,
                "mcp.market": market,
                "mcp.count": count,
                "mcp.freshness": freshness,
            },
        )
        span_cm.__enter__()
    
    client = None
    agent = None
    
    try:
        # Build the risk-specific query
        queries = {
            "litigation": f"{company_name} lawsuits legal cases court filings",
            "labor_practices": f"{company_name} labor violations employee complaints child labor",
            "environmental": f"{company_name} environmental violations pollution ESG",
            "financial": f"{company_name} financial risks debt bankruptcy",
            "regulatory": f"{company_name} regulatory violations fines investigations",
            "reputation": f"{company_name} scandals controversies",
            "all": f"{company_name} risks controversies legal issues financial regulatory"
        }
        query = queries.get(risk_category, queries["all"])
        
        # Validate market
        if market not in SUPPORTED_MARKETS:
            market = "en-US"
        
        logger.info(f"🤖 Creating Worker Agent for {company_name} (market: {market})")
        
        # Get AI Project client
        client = get_ai_project_client()
        openai_client = client.get_openai_client()
        
        # Get Bing connection
        from azure.ai.projects.models import (
            PromptAgentDefinition,
            BingGroundingAgentTool,
            BingGroundingSearchConfiguration,
            BingGroundingSearchToolParameters,
        )
        
        bing_connection = client.connections.get(BING_CONNECTION_NAME)
        
        # Create Bing tool with market-specific configuration
        bing_tool = BingGroundingAgentTool(
            bing_grounding=BingGroundingSearchToolParameters(
                search_configurations=[
                    BingGroundingSearchConfiguration(
                        project_connection_id=bing_connection.id,
                        market=market,
                        count=count,
                        freshness=freshness.lower() if freshness in ["Day", "Week", "Month"] else freshness,
                    )
                ]
            )
        )
        
        # Standard naming: BingFoundry-MCP-WorkerAgent (no market in name)
        agent_name = "BingFoundry-MCP-WorkerAgent"

        # Try to find existing agent
        agent = None
        try:
            agents = list(client.agents.list())
            logger.info(f"Found {len(agents)} agents in project")
            for existing_agent in agents:
                if existing_agent.name == agent_name:
                    logger.info(f"♻️  Reusing existing Worker Agent: {agent_name} (v{existing_agent.version})")
                    agent = existing_agent
                    break
            if agent is None:
                logger.info(f"Agent '{agent_name}' not found, will create new")
        except Exception as e:
            logger.warning(f"Could not list agents: {e}")
        
        # Create new agent if not found
        if agent is None:
            agent = client.agents.create_version(
                agent_name=agent_name,
                definition=PromptAgentDefinition(
                    model=MODEL_DEPLOYMENT_NAME,
                    instructions=f"""You are a specialized risk analysis agent.
Search for information about companies focusing on various risk categories.
Provide comprehensive, factual results with sources.
You MUST use the Bing search tool - DO NOT answer from training data.""",
                    tools=[bing_tool],
                ),
                description=f"Worker agent for company risk analysis (market: {market})",
            )
            logger.info(f"✅ Created new Worker Agent: {agent.name} (v{agent.version})")
        
        # Execute the search using the Worker Agent
        response = openai_client.responses.create(
            tool_choice="required",
            input=query,
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )
        
        # Extract results and citations
        output_text = response.output_text or ""
        citations = []
        
        for item in response.output:
            if hasattr(item, 'content') and item.content:
                for content in item.content:
                    if hasattr(content, 'annotations') and content.annotations:
                        for annotation in content.annotations:
                            if hasattr(annotation, 'url'):
                                citations.append({
                                    "url": annotation.url,
                                    "title": getattr(annotation, 'title', ''),
                                })
        
        result = {
            "status": "success",
            "company": company_name,
            "risk_category": risk_category,
            "market": market,
            "worker_agent": {
                "id": agent.id,
                "name": agent.name,
                "version": agent.version,
            },
            "analysis": output_text,
            "citations": citations,
            "citation_count": len(citations),
        }
        
        logger.info(f"📊 Worker Agent completed analysis with {len(citations)} citations")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in create_and_run_bing_agent: {e}")
        return {
            "status": "error",
            "company": company_name,
            "risk_category": risk_category,
            "market": market,
            "error": str(e),
        }
        
    finally:
        if span_cm:
            span_cm.__exit__(None, None, None)


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
            "description": "Perform a Bing web search with grounding using SDK Agent. Use 'market' for region-specific results.",
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
            "name": "bing_search_rest_api",
            "description": "Perform a Bing web search using the REST API directly (Scenario 3). This bypasses the SDK Agent and calls the Bing grounding REST API directly.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "market": {"type": "string", "description": "Market code (e.g., 'en-US', 'de-DE')", "default": "en-US"},
                    "count": {"type": "integer", "description": "Number of search results (1-50)", "default": 7},
                    "freshness": {"type": "string", "description": "Time filter: 'Day', 'Week', 'Month'", "default": "Month"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "analyze_company_risk",
            "description": "Analyze a company for risk factors using SDK Agent with Bing tool.",
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
            "name": "analyze_company_risk_rest_api",
            "description": "Analyze a company for risk factors using Bing REST API directly (Scenario 3). This bypasses the SDK Agent.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Company name to analyze"},
                    "risk_category": {
                        "type": "string",
                        "enum": ["litigation", "labor_practices", "environmental", "financial", "regulatory", "reputation", "all"],
                        "default": "all"
                    },
                    "market": {"type": "string", "description": "Market code (e.g., 'en-US', 'de-DE')", "default": "en-US"},
                    "count": {"type": "integer", "description": "Number of search results (1-50)", "default": 7},
                    "freshness": {"type": "string", "description": "Time filter: 'Day', 'Week', 'Month'", "default": "Month"}
                },
                "required": ["company_name"]
            }
        },
        {
            "name": "create_and_run_bing_agent",
            "description": "Create an ephemeral Worker Agent with Bing tool, run risk analysis, and delete the agent. This implements the Two-Agent Pattern for Scenario 2.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Company name to analyze"},
                    "risk_category": {
                        "type": "string",
                        "enum": ["litigation", "labor_practices", "environmental", "financial", "regulatory", "reputation", "all"],
                        "default": "all"
                    },
                    "market": {"type": "string", "description": "Bing market code (e.g., 'en-US', 'de-DE')", "default": "en-US"},
                    "count": {"type": "integer", "description": "Number of search results (1-50)", "default": 10},
                    "freshness": {"type": "string", "description": "Time filter: 'Day', 'Week', 'Month'", "default": "Month"}
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
        
        elif name == "bing_search_rest_api":
            # Scenario 3: Direct REST API call
            query = arguments.get("query", "")
            market = arguments.get("market", "en-US")
            count = arguments.get("count", 7)
            freshness = arguments.get("freshness", "Month")
            
            if not query:
                return web.json_response({"error": "Query is required"}, status=400)
            
            result = await perform_bing_search_rest_api(query, market, count, freshness)
            return web.json_response({"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        
        elif name == "analyze_company_risk":
            company_name = arguments.get("company_name", "")
            risk_category = arguments.get("risk_category", "all")
            market = arguments.get("market", "en-US")
            
            if not company_name:
                return web.json_response({"error": "company_name is required"}, status=400)
            
            result = await analyze_company_risk(company_name, risk_category, market)
            return web.json_response({"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        
        elif name == "analyze_company_risk_rest_api":
            # Scenario 3: Company risk analysis using REST API directly
            company_name = arguments.get("company_name", "")
            risk_category = arguments.get("risk_category", "all")
            market = arguments.get("market", "en-US")
            count = arguments.get("count", 7)
            freshness = arguments.get("freshness", "Month")
            
            if not company_name:
                return web.json_response({"error": "company_name is required"}, status=400)
            
            result = await analyze_company_risk_rest_api(company_name, risk_category, market, count, freshness)
            return web.json_response({"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        
        elif name == "create_and_run_bing_agent":
            # Scenario 2: Two-Agent Pattern - Create Worker Agent, run search, delete agent
            company_name = arguments.get("company_name", "")
            risk_category = arguments.get("risk_category", "all")
            market = arguments.get("market", "en-US")
            count = arguments.get("count", 10)
            freshness = arguments.get("freshness", "Month")
            
            if not company_name:
                return web.json_response({"error": "company_name is required"}, status=400)
            
            result = await create_and_run_bing_agent(company_name, risk_category, market, count, freshness)
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
                    "description": "Perform a Bing web search with grounding using SDK Agent.",
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
                    "name": "bing_search_rest_api",
                    "description": "Perform a Bing web search using REST API directly (Scenario 3).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "market": {"type": "string", "default": "en-US"},
                            "count": {"type": "integer", "default": 7},
                            "freshness": {"type": "string", "default": "Month"}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "analyze_company_risk",
                    "description": "Analyze company risks using SDK Agent with Bing tool.",
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
                    "name": "analyze_company_risk_rest_api",
                    "description": "Analyze company risks using Bing REST API directly (Scenario 3).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "company_name": {"type": "string"},
                            "risk_category": {"type": "string", "default": "all"},
                            "market": {"type": "string", "default": "en-US"},
                            "count": {"type": "integer", "default": 7},
                            "freshness": {"type": "string", "default": "Month"}
                        },
                        "required": ["company_name"]
                    }
                },
                {
                    "name": "create_and_run_bing_agent",
                    "description": "Create ephemeral Worker Agent with Bing tool, run search, delete agent (Scenario 2 Two-Agent Pattern).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "company_name": {"type": "string"},
                            "risk_category": {"type": "string", "default": "all"},
                            "market": {"type": "string", "default": "en-US"},
                            "count": {"type": "integer", "default": 10},
                            "freshness": {"type": "string", "default": "Month"}
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
                elif name == "bing_search_rest_api":
                    # Scenario 3: Direct REST API call
                    search_result = await perform_bing_search_rest_api(
                        arguments.get("query", ""),
                        arguments.get("market", "en-US"),
                        arguments.get("count", 7),
                        arguments.get("freshness", "Month")
                    )
                    result = {"content": [{"type": "text", "text": json.dumps(search_result, indent=2)}]}
                elif name == "analyze_company_risk":
                    risk_result = await analyze_company_risk(
                        arguments.get("company_name", ""),
                        arguments.get("risk_category", "all"),
                        arguments.get("market", "en-US")
                    )
                    result = {"content": [{"type": "text", "text": json.dumps(risk_result, indent=2)}]}
                elif name == "analyze_company_risk_rest_api":
                    # Scenario 3: Company risk analysis using REST API directly
                    risk_result = await analyze_company_risk_rest_api(
                        arguments.get("company_name", ""),
                        arguments.get("risk_category", "all"),
                        arguments.get("market", "en-US"),
                        arguments.get("count", 7),
                        arguments.get("freshness", "Month")
                    )
                    result = {"content": [{"type": "text", "text": json.dumps(risk_result, indent=2)}]}
                elif name == "create_and_run_bing_agent":
                    # Scenario 2: Two-Agent Pattern - Create Worker Agent, run, delete
                    agent_result = await create_and_run_bing_agent(
                        arguments.get("company_name", ""),
                        arguments.get("risk_category", "all"),
                        arguments.get("market", "en-US"),
                        arguments.get("count", 10),
                        arguments.get("freshness", "Month")
                    )
                    result = {"content": [{"type": "text", "text": json.dumps(agent_result, indent=2)}]}
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
