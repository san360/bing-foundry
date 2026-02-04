"""
Core data models for the Bing Foundry application.

These models represent the domain entities and DTOs used across the application.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class RiskCategory(Enum):
    """Risk categories for company analysis."""
    LITIGATION = "litigation"
    LABOR_PRACTICES = "labor_practices"
    ENVIRONMENTAL = "environmental"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    REPUTATION = "reputation"
    ALL = "all"


class ScenarioType(Enum):
    """Available scenario types."""
    DIRECT_AGENT = "direct_agent"
    MCP_AGENT_TO_AGENT = "mcp_agent_to_agent"
    MCP_REST_API = "mcp_rest_api"


@dataclass
class MarketConfig:
    """Bing Search Market Configuration."""
    code: str
    display_name: str
    language: str
    country: str


@dataclass
class SearchConfig:
    """Configuration for Bing search requests."""
    market: Optional[str] = "en-US"
    count: int = 10
    freshness: str = "Month"
    set_lang: Optional[str] = None


@dataclass
class Citation:
    """Citation from search results."""
    url: str
    title: str
    start_index: Optional[int] = None
    end_index: Optional[int] = None


@dataclass
class AnalysisResponse:
    """Response from company risk analysis."""
    text: str
    citations: List[Citation] = field(default_factory=list)
    market_used: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanyRiskRequest:
    """Request for company risk analysis."""
    company_name: str
    risk_category: RiskCategory = RiskCategory.ALL
    search_config: SearchConfig = field(default_factory=SearchConfig)
    scenario_type: ScenarioType = ScenarioType.DIRECT_AGENT


@dataclass
class AnalysisResult:
    """Result of a company analysis (for UI display)."""
    company: str
    market: Optional[str]
    timestamp: str
    text: str
    citations: List[Dict[str, Any]]
    tool_config: Dict[str, Any]
    scenario_type: ScenarioType
