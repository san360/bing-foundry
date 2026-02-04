"""
Scenario 2: Agent → MCP Server → Agent.

User → MCP Server → Agent 2 (with Bing Tool)
"""
import logging
import json
import httpx
from scenarios.base import BaseScenario
from core.models import CompanyRiskRequest, AnalysisResponse, Citation
from core.interfaces import IAzureClientFactory
from services import RiskAnalyzer

logger = logging.getLogger(__name__)


class MCPAgentScenario(BaseScenario):
    """
    Scenario 2: Agent calling another agent via MCP server.
    
    Market parameter flows through MCP tool arguments.
    """
    
    def __init__(
        self,
        client_factory: IAzureClientFactory,
        risk_analyzer: RiskAnalyzer,
        mcp_url: str,
        mcp_key: str = "",
    ):
        """
        Initialize the MCP agent scenario.
        
        Args:
            client_factory: Azure client factory
            risk_analyzer: Risk analysis service
            mcp_url: MCP server URL
            mcp_key: MCP server authentication key (optional)
        """
        super().__init__(client_factory, risk_analyzer)
        self.mcp_url = mcp_url
        self.mcp_key = mcp_key
    
    async def execute(
        self,
        request: CompanyRiskRequest
    ) -> AnalysisResponse:
        """
        Execute Scenario 2: Call MCP server with analyze_company_risk tool.
        
        The MCP server creates an agent with the specified market.
        """
        logger.info(f"Executing Scenario 2 for {request.company_name} via MCP")
        
        headers = {"Content-Type": "application/json"}
        if self.mcp_key:
            headers["x-functions-key"] = self.mcp_key
        
        # Build MCP request
        mcp_request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {
                "name": "analyze_company_risk",
                "arguments": {
                    "company_name": request.company_name,
                    "risk_category": request.risk_category.value,
                    "market": request.search_config.market or "en-US"
                }
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.mcp_url,
                headers=headers,
                json=mcp_request
            )
            
            if response.status_code != 200:
                raise Exception(f"MCP error: HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            result_content = data.get("result", {}).get("content", [])
            
            # Extract text and agent info from response
            response_text = ""
            agent_info = {}
            
            for content in result_content:
                if content.get("type") == "text":
                    response_text = content.get("text", "")
                    try:
                        # Try to parse as JSON if it's a structured response
                        parsed = json.loads(response_text)
                        if isinstance(parsed, dict):
                            # Extract agent information from MCP response
                            if "agent_id" in parsed:
                                agent_info["agent_id"] = parsed["agent_id"]
                            if "agent_name" in parsed:
                                agent_info["agent_name"] = parsed["agent_name"]
                            if "agent_version" in parsed:
                                agent_info["agent_version"] = parsed["agent_version"]
                            
                            if "search_results" in parsed:
                                search_results = parsed["search_results"]
                                if "results" in search_results:
                                    response_text = search_results["results"][0].get("content", "")
                    except:
                        pass
            
            logger.info(f"✅ Scenario 2 complete via MCP")
            if agent_info:
                logger.info(f"   Agent created by MCP: {agent_info.get('agent_name', 'unknown')} (v{agent_info.get('agent_version', '?')})")
            
            return AnalysisResponse(
                text=response_text,
                citations=[],  # MCP response may not include structured citations
                market_used=request.search_config.market,
                metadata={
                    "scenario": "mcp_agent_to_agent",
                    "mcp_url": self.mcp_url,
                    "risk_category": request.risk_category.value,
                    **agent_info,  # Include agent info from MCP
                }
            )
