"""Agent module initialization"""
from .company_risk_agent import CompanyRiskAgent, AgentResponse
from .prompts import (
    get_company_risk_analysis_prompt,
    get_focused_search_prompt,
    AGENT_SYSTEM_INSTRUCTION,
)

__all__ = [
    "CompanyRiskAgent",
    "AgentResponse",
    "get_company_risk_analysis_prompt",
    "get_focused_search_prompt",
    "AGENT_SYSTEM_INSTRUCTION",
]
