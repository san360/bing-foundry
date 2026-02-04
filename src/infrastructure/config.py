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
# Reference: https://learn.microsoft.com/en-us/previous-versions/bing/search-apis/bing-web-search/reference/market-codes
MARKET_OPTIONS = {
    # Americas
    "United States (English)": MarketConfig(
        code="en-US",
        display_name="United States (English)",
        language="en",
        country="US"
    ),
    "United States (Spanish)": MarketConfig(
        code="es-US",
        display_name="United States (Spanish)",
        language="es",
        country="US"
    ),
    "Canada (English)": MarketConfig(
        code="en-CA",
        display_name="Canada (English)",
        language="en",
        country="CA"
    ),
    "Canada (French)": MarketConfig(
        code="fr-CA",
        display_name="Canada (French)",
        language="fr",
        country="CA"
    ),
    "Mexico (Spanish)": MarketConfig(
        code="es-MX",
        display_name="Mexico (Spanish)",
        language="es",
        country="MX"
    ),
    "Brazil (Portuguese)": MarketConfig(
        code="pt-BR",
        display_name="Brazil (Portuguese)",
        language="pt",
        country="BR"
    ),
    # Europe
    "United Kingdom (English)": MarketConfig(
        code="en-GB",
        display_name="United Kingdom (English)",
        language="en",
        country="GB"
    ),
    "Germany (German)": MarketConfig(
        code="de-DE",
        display_name="Germany (German)",
        language="de",
        country="DE"
    ),
    "Austria (German)": MarketConfig(
        code="de-AT",
        display_name="Austria (German)",
        language="de",
        country="AT"
    ),
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
    "France (French)": MarketConfig(
        code="fr-FR",
        display_name="France (French)",
        language="fr",
        country="FR"
    ),
    "Spain (Spanish)": MarketConfig(
        code="es-ES",
        display_name="Spain (Spanish)",
        language="es",
        country="ES"
    ),
    "Italy (Italian)": MarketConfig(
        code="it-IT",
        display_name="Italy (Italian)",
        language="it",
        country="IT"
    ),
    "Netherlands (Dutch)": MarketConfig(
        code="nl-NL",
        display_name="Netherlands (Dutch)",
        language="nl",
        country="NL"
    ),
    "Sweden (Swedish)": MarketConfig(
        code="sv-SE",
        display_name="Sweden (Swedish)",
        language="sv",
        country="SE"
    ),
    # Asia Pacific
    "Japan (Japanese)": MarketConfig(
        code="ja-JP",
        display_name="Japan (Japanese)",
        language="ja",
        country="JP"
    ),
    "Korea (Korean)": MarketConfig(
        code="ko-KR",
        display_name="Korea (Korean)",
        language="ko",
        country="KR"
    ),
    "China (Chinese)": MarketConfig(
        code="zh-CN",
        display_name="China (Chinese)",
        language="zh",
        country="CN"
    ),
    "Taiwan (Chinese)": MarketConfig(
        code="zh-TW",
        display_name="Taiwan (Chinese)",
        language="zh",
        country="TW"
    ),
    "Australia (English)": MarketConfig(
        code="en-AU",
        display_name="Australia (English)",
        language="en",
        country="AU"
    ),
    "India (English)": MarketConfig(
        code="en-IN",
        display_name="India (English)",
        language="en",
        country="IN"
    ),
    # Default option
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
