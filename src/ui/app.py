"""
Main Streamlit application entry point (REFACTORED).

This is a simplified entry point that delegates to specialized modules.
"""
import os
import sys
import logging
from pathlib import Path

# Configure logging - Reduce verbose HTTP/Azure logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Silence noisy loggers
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline').setLevel(logging.ERROR)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)
logging.getLogger('azure.monitor.opentelemetry.exporter').setLevel(logging.WARNING)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

# CRITICAL: Must be first Streamlit command
st.set_page_config(
    page_title="Company Risk Analysis - Bing Grounding PoC",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide sidebar completely with CSS
st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarCollapsedControl"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# Load environment and setup tracing
from dotenv import load_dotenv
load_dotenv()

from infrastructure import setup_tracing, AzureConfig
tracing_enabled = setup_tracing()

# Import UI components
from ui.pages.scenario1 import render_scenario1
from ui.pages.scenario2 import render_scenario2
from ui.pages.scenario3 import render_scenario3
from ui.pages.scenario4 import render_scenario4
from ui.pages.scenario5 import render_scenario5
from ui.pages.documentation import render_documentation

logger.info(f"Tracing enabled: {tracing_enabled}")


def init_session_state():
    """Initialize session state variables."""
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = []
    if "mcp_results" not in st.session_state:
        st.session_state.mcp_results = []
    if "rest_api_results" not in st.session_state:
        st.session_state.rest_api_results = []
    if "multi_market_results" not in st.session_state:
        st.session_state.multi_market_results = []
    if "workflow_results" not in st.session_state:
        st.session_state.workflow_results = []
    if "config_valid" not in st.session_state:
        st.session_state.config_valid = False
    if "mcp_connected" not in st.session_state:
        st.session_state.mcp_connected = False


def load_config() -> AzureConfig:
    """Load configuration from environment and validate."""
    config = AzureConfig.from_env()
    is_valid, message = config.is_valid()
    st.session_state.config_valid = is_valid

    if not is_valid:
        st.error(f"⚠️ Configuration Error: {message}")
        st.info("Please ensure your .env file has the required variables.")

    return config


def main():
    """Main application entry point."""
    logger.info("Starting application...")

    # Initialize session state
    init_session_state()
    logger.info("Session state initialized")

    # Load config directly (no sidebar)
    config = load_config()
    logger.info("Configuration loaded")

    # Main content area with tabs
    logger.info("Creating tabs...")
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🎯 Scenario 1: Direct Agent",
        "🔗 Scenario 2: Two-Agent",
        "🌐 Scenario 3: MCP REST",
        "🌍 Scenario 4: Multi-Market",
        "⚡ Scenario 5: Workflow",
        "📖 Documentation"
    ])

    logger.info("Rendering tab content...")
    with tab1:
        render_scenario1(config)

    with tab2:
        render_scenario2(config)

    with tab3:
        render_scenario3(config)

    with tab4:
        render_scenario4(config)

    with tab5:
        render_scenario5(config)

    with tab6:
        render_documentation()

    logger.info("Application rendering complete")


if __name__ == "__main__":
    main()
