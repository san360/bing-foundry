"""Scenarios module initialization."""
from scenarios.base import BaseScenario
from scenarios.scenario1_direct import DirectAgentScenario
from scenarios.scenario2_mcp_agent import MCPAgentScenario
from scenarios.scenario3_mcp_rest import MCPRestAPIScenario
from scenarios.scenario4_multi_market import MultiMarketScenario

__all__ = [
    "BaseScenario",
    "DirectAgentScenario",
    "MCPAgentScenario",
    "MCPRestAPIScenario",
    "MultiMarketScenario",
]
