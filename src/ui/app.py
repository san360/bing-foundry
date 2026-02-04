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

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

# CRITICAL: Must be first Streamlit command
st.set_page_config(
    page_title="Company Risk Analysis - Bing Grounding PoC",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment and setup tracing
from dotenv import load_dotenv
load_dotenv()

from infrastructure import setup_tracing
tracing_enabled = setup_tracing()

# Import UI components
from ui.components.sidebar import render_sidebar
from ui.pages.scenario1 import render_scenario1
from ui.pages.scenario2 import render_scenario2
from ui.pages.scenario3 import render_scenario3
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
    if "config_valid" not in st.session_state:
        st.session_state.config_valid = False
    if "mcp_connected" not in st.session_state:
        st.session_state.mcp_connected = False


def main():
    """Main application entry point."""
    logger.info("Starting application...")
    
    # Initialize session state
    init_session_state()
    
    # Render sidebar and get config
    config = render_sidebar()
    
    # Main content area with tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Scenario 1: Direct Agent",
        "🔗 Scenario 2: MCP Agent→Agent",
        "🌐 Scenario 3: Agent→MCP→REST",
        "📖 Documentation"
    ])
    
    with tab1:
        render_scenario1(config)
    
    with tab2:
        render_scenario2(config)
    
    with tab3:
        render_scenario3(config)
    
    with tab4:
        render_documentation()


if __name__ == "__main__":
    main()
