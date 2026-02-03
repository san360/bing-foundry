"""
MCP Server for Bing Grounding Search - Azure Functions Implementation

This MCP server wraps the Bing Grounding functionality and exposes it as tools
that can be used by AI agents. The market parameter can be passed at runtime
to customize search results by region.

Deployment Options:
1. Azure Functions (this file) - Production-ready, serverless
2. Local Docker container - Development/testing
3. Azure Container Apps - Full container control
"""

import json
import logging
import os
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Configuration
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")
BING_CONNECTION_NAME = os.getenv("BING_CONNECTION_NAME", "")

# Supported market codes for Bing Search
SUPPORTED_MARKETS = [
    "en-US", "en-GB", "en-AU", "en-CA", "en-IN",
    "de-DE", "fr-FR", "es-ES", "it-IT", "pt-BR",
    "ja-JP", "ko-KR", "zh-CN", "zh-TW",
    "nl-NL", "pl-PL", "ru-RU", "sv-SE", "tr-TR",
    "ar-SA", "hi-IN", "th-TH", "vi-VN"
]


class ToolProperty:
    """Defines a property for an MCP tool."""
    
    def __init__(self, property_name: str, property_type: str, description: str, required: bool = True):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description
        self.required = required
    
    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }


# Define tool properties for the Bing search tool
bing_search_properties = [
    ToolProperty(
        "query",
        "string",
        "The search query to send to Bing. Should be a clear, specific question or topic."
    ),
    ToolProperty(
        "market",
        "string",
        f"The market/region code for localized results (e.g., 'en-US', 'de-DE', 'ja-JP'). "
        f"Supported markets: {', '.join(SUPPORTED_MARKETS[:10])}... Default is 'en-US'."
    ),
]

company_risk_analysis_properties = [
    ToolProperty(
        "company_name",
        "string",
        "The name of the company to analyze for risks."
    ),
    ToolProperty(
        "risk_category",
        "string",
        "The risk category to focus on: 'litigation', 'labor_practices', 'environmental', "
        "'financial', 'regulatory', 'reputation', or 'all' for comprehensive analysis."
    ),
    ToolProperty(
        "market",
        "string",
        "The market/region code for localized news and results (e.g., 'en-US', 'de-DE'). "
        "Use the market where the company primarily operates."
    ),
]

list_markets_properties = []

# Convert to JSON for MCP tool registration
bing_search_props_json = json.dumps([p.to_dict() for p in bing_search_properties])
company_risk_props_json = json.dumps([p.to_dict() for p in company_risk_analysis_properties])
list_markets_props_json = json.dumps([p.to_dict() for p in list_markets_properties])


def get_ai_project_client():
    """Get authenticated AI Project client."""
    if not PROJECT_ENDPOINT:
        raise ValueError("PROJECT_ENDPOINT environment variable not set")
    
    credential = DefaultAzureCredential()
    return AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential
    )


def perform_bing_search(query: str, market: str = "en-US") -> dict:
    """
    Perform a Bing grounded search using the AI Foundry agent.
    
    Args:
        query: The search query
        market: The market code for localized results
    
    Returns:
        Search results as a dictionary
    """
    try:
        # Validate market
        if market not in SUPPORTED_MARKETS:
            market = "en-US"
            logging.warning(f"Invalid market code, defaulting to en-US")
        
        client = get_ai_project_client()
        agents_client = client.agents
        
        # Create Bing grounding tool with the specified market
        from azure.ai.agents.models import BingGroundingTool, BingGroundingSearchConfiguration
        
        bing_tool = BingGroundingTool(
            bing_grounding_search=BingGroundingSearchConfiguration(
                connection_id=BING_CONNECTION_NAME,
                market=market
            )
        )
        
        # Create a temporary agent for this search
        agent = agents_client.create_agent(
            model=os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
            name="bing-search-agent",
            instructions="You are a search assistant. Perform web searches and return comprehensive, factual results.",
            tools=bing_tool.definitions
        )
        
        try:
            # Create thread and run the search
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
            
            # Get the response
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
            # Clean up agent
            agents_client.delete_agent(agent.id)
            
    except Exception as e:
        logging.error(f"Bing search error: {e}")
        return {
            "query": query,
            "market": market,
            "status": "error",
            "error": str(e)
        }


def analyze_company_risk(company_name: str, risk_category: str, market: str = "en-US") -> dict:
    """
    Analyze company risks using Bing grounded search.
    
    Args:
        company_name: Name of the company
        risk_category: Category of risk to analyze
        market: Market code for localized results
    
    Returns:
        Risk analysis results
    """
    # Build specialized queries based on risk category
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
        search_result = perform_bing_search(query, market)
        
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
# MCP Tool Trigger Functions
# ============================================================================

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="bing_grounded_search",
    description="Perform a Bing web search with grounding. Returns factual, sourced information "
                "from the web. Use the 'market' parameter to get region-specific results.",
    toolProperties=bing_search_props_json,
)
def bing_grounded_search(context) -> str:
    """
    MCP Tool: Perform a Bing grounded search.
    
    This tool wraps the Bing Grounding capability and allows the market
    parameter to be specified at runtime for region-specific results.
    """
    try:
        content = json.loads(context)
        args = content.get("arguments", {})
        
        query = args.get("query", "")
        market = args.get("market", "en-US")
        
        if not query:
            return json.dumps({"error": "Query parameter is required"})
        
        logging.info(f"Bing search: query='{query}', market='{market}'")
        
        result = perform_bing_search(query, market)
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logging.error(f"bing_grounded_search error: {e}")
        return json.dumps({"error": str(e)})


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="analyze_company_risk",
    description="Analyze a company for various risk factors from an insurance perspective. "
                "Searches for litigation history, labor practices, environmental issues, "
                "financial risks, regulatory compliance, and reputation concerns.",
    toolProperties=company_risk_props_json,
)
def analyze_company_risk_tool(context) -> str:
    """
    MCP Tool: Analyze company risks using Bing grounded search.
    
    This tool is designed for insurance risk assessment, searching for
    various risk categories specific to a company.
    """
    try:
        content = json.loads(context)
        args = content.get("arguments", {})
        
        company_name = args.get("company_name", "")
        risk_category = args.get("risk_category", "all")
        market = args.get("market", "en-US")
        
        if not company_name:
            return json.dumps({"error": "company_name parameter is required"})
        
        logging.info(f"Company risk analysis: company='{company_name}', "
                    f"category='{risk_category}', market='{market}'")
        
        result = analyze_company_risk(company_name, risk_category, market)
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logging.error(f"analyze_company_risk_tool error: {e}")
        return json.dumps({"error": str(e)})


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_supported_markets",
    description="List all supported market codes for Bing search. Use this to discover "
                "available markets for region-specific search results.",
    toolProperties=list_markets_props_json,
)
def list_supported_markets(context) -> str:
    """
    MCP Tool: List all supported market codes.
    """
    market_info = {
        "markets": [
            {"code": "en-US", "description": "English - United States"},
            {"code": "en-GB", "description": "English - United Kingdom"},
            {"code": "en-AU", "description": "English - Australia"},
            {"code": "en-CA", "description": "English - Canada"},
            {"code": "en-IN", "description": "English - India"},
            {"code": "de-DE", "description": "German - Germany"},
            {"code": "fr-FR", "description": "French - France"},
            {"code": "es-ES", "description": "Spanish - Spain"},
            {"code": "it-IT", "description": "Italian - Italy"},
            {"code": "pt-BR", "description": "Portuguese - Brazil"},
            {"code": "ja-JP", "description": "Japanese - Japan"},
            {"code": "ko-KR", "description": "Korean - South Korea"},
            {"code": "zh-CN", "description": "Chinese - China"},
            {"code": "zh-TW", "description": "Chinese - Taiwan"},
            {"code": "nl-NL", "description": "Dutch - Netherlands"},
            {"code": "pl-PL", "description": "Polish - Poland"},
            {"code": "ru-RU", "description": "Russian - Russia"},
            {"code": "sv-SE", "description": "Swedish - Sweden"},
            {"code": "tr-TR", "description": "Turkish - Turkey"},
            {"code": "ar-SA", "description": "Arabic - Saudi Arabia"},
            {"code": "hi-IN", "description": "Hindi - India"},
            {"code": "th-TH", "description": "Thai - Thailand"},
            {"code": "vi-VN", "description": "Vietnamese - Vietnam"},
        ],
        "default": "en-US",
        "note": "The market parameter affects the language and regional relevance of search results."
    }
    return json.dumps(market_info, indent=2)
