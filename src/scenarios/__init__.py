"""Scenarios module initialization."""
from scenarios.base import BaseScenario
from scenarios.scenario1_direct import DirectAgentScenario
from scenarios.scenario2_mcp_agent import MCPAgentScenario
from scenarios.scenario3_mcp_rest import MCPRestAPIScenario

__all__ = [
    "BaseScenario",
    "DirectAgentScenario",
    "MCPAgentScenario",
    "MCPRestAPIScenario",
]
