"""
Configuration module for Company Risk Analysis Agent
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AzureConfig:
    """Azure AI Foundry configuration"""
    project_endpoint: str
    model_deployment_name: str
    bing_connection_name: str
    
    @classmethod
    def from_env(cls) -> "AzureConfig":
        """Load configuration from environment variables"""
        return cls(
            project_endpoint=os.environ.get("AZURE_AI_PROJECT_ENDPOINT", ""),
            model_deployment_name=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
            bing_connection_name=os.environ.get("BING_PROJECT_CONNECTION_NAME", ""),
        )


@dataclass
class MarketConfig:
    """Bing Search Market Configuration"""
    code: str
    display_name: str
    language: str
    country: str
    
    
# Predefined market configurations for testing
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
    "No Market (Default)": None,  # Test default behavior
}


# Risk categories to analyze
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
