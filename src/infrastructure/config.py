"""
Configuration module for Bing Foundry.

Centralizes all configuration loading and validation.
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
from core.models import MarketConfig

load_dotenv()


@dataclass
class AzureConfig:
    """Azure AI Foundry configuration."""
    project_endpoint: str
    model_deployment_name: str
    bing_connection_name: str
    
    @classmethod
    def from_env(cls) -> "AzureConfig":
        """Load configuration from environment variables."""
        return cls(
            project_endpoint=os.environ.get("AZURE_AI_PROJECT_ENDPOINT", ""),
            model_deployment_name=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
            bing_connection_name=os.environ.get("BING_PROJECT_CONNECTION_NAME", ""),
        )
    
    def is_valid(self) -> tuple[bool, str]:
        """Validate the configuration."""
        missing = []
        if not self.project_endpoint:
            missing.append("AZURE_AI_PROJECT_ENDPOINT")
        if not self.model_deployment_name:
            missing.append("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        if not self.bing_connection_name:
            missing.append("BING_PROJECT_CONNECTION_NAME")
        
        if missing:
            return False, f"Missing environment variables: {', '.join(missing)}"
        return True, "Configuration valid"


@dataclass
class MCPConfig:
    """MCP Server configuration."""
    server_url: str
    server_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Load MCP configuration from environment."""
        return cls(
            server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp"),
            server_key=os.getenv("MCP_SERVER_KEY", ""),
        )


# Predefined market configurations
MARKET_OPTIONS = {
    "Switzerland (German)": MarketConfig(
        code="de-CH",
        display_name="Switzerland (German)",
        language="de",
        country="CH"
    ),
    "Switzerland (French)": MarketConfig(
        code="fr-CH",
        display_name="Switzerland (French)",
        language="fr",
        country="CH"
    ),
    "United States": MarketConfig(
        code="en-US",
        display_name="United States",
        language="en",
        country="US"
    ),
    "Germany": MarketConfig(
        code="de-DE",
        display_name="Germany",
        language="de",
        country="DE"
    ),
    "United Kingdom": MarketConfig(
        code="en-GB",
        display_name="United Kingdom",
        language="en",
        country="GB"
    ),
    "No Market (Default)": None,
}

# Risk categories
RISK_CATEGORIES = [
    "Child Labor",
    "Environmental Violations",
    "Fraud & Financial Crimes",
    "Workplace Safety Issues",
    "Data Privacy Breaches",
    "Product Safety Recalls",
    "Bribery & Corruption",
    "Human Rights Violations",
    "Antitrust & Competition Issues",
    "Regulatory Non-Compliance",
]
