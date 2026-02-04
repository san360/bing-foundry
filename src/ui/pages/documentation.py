"""
Documentation page for the application.
"""
import streamlit as st


def render_documentation():
    """Render the documentation tab."""
    st.header("📖 Documentation")
    
    st.markdown("""
    ## Architecture Overview
    
    This application demonstrates three scenarios for using Bing Grounding with Azure AI:
    
    ### Scenario 1: Direct Agent with Bing Tool
    ```
    User → AI Agent (with Bing Tool directly attached)
    ```
    - Market parameter set at **tool creation time**
    - Simplest approach
    - Lowest latency
    
    ### Scenario 2: Agent → MCP Server → Agent
    ```
    User → MCP Server → Agent 2 (created with Bing Tool)
    ```
    - Market parameter passed as **MCP tool argument**
    - Agent created per request
    - Good for multi-agent systems
    
    ### Scenario 3: Agent → MCP Tool → REST API
    ```
    User → AI Agent (with MCP Tool) → MCP Server → Bing REST API
    ```
    - Market parameter in **MCP tool call**
    - Direct REST API access
    - Full control over API configuration
    
    ## SOLID Principles Applied
    
    This refactored codebase follows SOLID principles:
    
    - **Single Responsibility**: Each module has one clear purpose
    - **Open/Closed**: Extensible through interfaces
    - **Liskov Substitution**: Base classes can be substituted
    - **Interface Segregation**: Specific interfaces for different needs
    - **Dependency Inversion**: Depends on abstractions, not implementations
    
    ## Module Structure
    
    ```
    src/
    ├── core/                  # Domain models & interfaces
    ├── infrastructure/        # Azure clients, config, tracing
    ├── services/              # Business logic
    ├── scenarios/             # Scenario implementations
    └── ui/                    # Streamlit UI
        ├── app.py             # Main entry (<100 lines)
        ├── components/        # Reusable UI components
        └── pages/             # Page-specific logic
    ```
    
    ## Benefits
    
    1. **Maintainability**: All files < 200 lines
    2. **Testability**: Easy to unit test each component
    3. **Readability**: Clear separation of concerns
    4. **Extensibility**: Easy to add new scenarios
    5. **Reusability**: Shared services across scenarios
    
    ## Market Parameter Configuration
    
    The `market` parameter is configured at the **tool level**:
    
    ```python
    BingGroundingSearchConfiguration(
        project_connection_id=conn_id,
        market="de-CH",  # Market specified here
        count=10,
        freshness="Month"
    )
    ```
    
    ## Running the Application
    
    ```bash
    # Install dependencies
    pip install -r requirements.txt
    
    # Set environment variables
    export AZURE_AI_PROJECT_ENDPOINT="..."
    export AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4o"
    export BING_PROJECT_CONNECTION_NAME="..."
    
    # Run the app
    streamlit run src/ui/app.py
    ```
    """)
