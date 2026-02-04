"""
Sidebar component for configuration display.
"""
import streamlit as st
from infrastructure import AzureConfig, MARKET_OPTIONS, RISK_CATEGORIES


def render_sidebar() -> AzureConfig:
    """Render the sidebar with configuration and information."""
    with st.sidebar:
        st.title("⚙️ Configuration")
        
        # Load and validate config
        config = AzureConfig.from_env()
        is_valid, message = config.is_valid()
        st.session_state.config_valid = is_valid
        
        if is_valid:
            st.success("✅ Configuration loaded")
            with st.expander("Connection Details"):
                st.text(f"Endpoint: {config.project_endpoint[:50]}...")
                st.text(f"Model: {config.model_deployment_name}")
                st.text(f"Bing Connection: {config.bing_connection_name}")
        else:
            st.error(f"❌ {message}")
            st.info("Please create a .env file with the required variables")
        
        st.divider()
        
        # Market Parameter Documentation
        st.subheader("📚 Market Parameter Info")
        
        with st.expander("Where is Market Configured?"):
            st.markdown("""
            **Key Finding:** The `market` parameter is configured at the 
            **TOOL level**, specifically in `BingGroundingSearchConfiguration`.
            
            ```python
            BingGroundingSearchConfiguration(
                project_connection_id=conn_id,
                market="de-CH",  # <-- HERE!
                count=10,
                freshness="Month"
            )
            ```
            """)
        
        st.divider()
        
        # Risk Categories Reference
        st.subheader("📋 Risk Categories")
        for cat in RISK_CATEGORIES:
            st.caption(f"• {cat}")
        
        return config
