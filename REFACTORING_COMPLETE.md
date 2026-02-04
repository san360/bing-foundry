# Refactored Architecture - Bing Foundry

## Overview

This codebase has been refactored following **SOLID principles** with the goal of:
- **Single Responsibility**: Each module has one clear purpose
- Files under **200 lines** for maintainability
- **High cohesion, low coupling**
- Easy to test, extend, and understand

## Architecture

```
src/
├── core/                          # Domain models & interfaces (~70 lines each)
│   ├── models.py                  # Data models and DTOs
│   └── interfaces.py              # Abstract interfaces
│
├── infrastructure/                # Infrastructure concerns (~100-150 lines each)
│   ├── config.py                  # Configuration management
│   ├── azure_client.py            # Azure client factory
│   └── tracing.py                 # OpenTelemetry setup
│
├── services/                      # Business logic layer (~100-150 lines each)
│   ├── bing_tool_builder.py      # Bing tool configuration
│   ├── agent_service.py           # Agent lifecycle management
│   └── risk_analyzer.py           # Risk analysis & prompts
│
├── scenarios/                     # Scenario implementations (~100-150 lines each)
│   ├── base.py                    # Base scenario class
│   ├── scenario1_direct.py        # Direct agent with Bing
│   ├── scenario2_mcp_agent.py     # MCP agent-to-agent
│   └── scenario3_mcp_rest.py      # Agent with MCP tool
│
└── ui/                            # Streamlit UI (<150 lines each)
    ├── app.py                     # Main entry point (~80 lines)
    ├── components/
    │   └── sidebar.py             # Sidebar component
    └── pages/
        ├── scenario1.py           # Scenario 1 UI
        ├── scenario2.py           # Scenario 2 UI
        ├── scenario3.py           # Scenario 3 UI
        └── documentation.py       # Documentation page
```

## Key Improvements

### Before Refactoring
- ❌ `app.py`: 1789 lines (everything mixed together)
- ❌ No clear separation of concerns
- ❌ Hard to test individual components
- ❌ Difficult to add new features

### After Refactoring
- ✅ Largest file: ~150 lines
- ✅ Clear separation: Core → Services → Scenarios → UI
- ✅ Easy to unit test each layer
- ✅ New scenarios can be added by implementing `IScenarioExecutor`

## Three Scenarios

### Scenario 1: Direct Agent
```python
from scenarios import DirectAgentScenario

scenario = DirectAgentScenario(client_factory, risk_analyzer, model_name)
response = await scenario.execute(request)
```

**Flow:** User → AI Agent (Bing Tool attached) → Bing API

### Scenario 2: MCP Agent-to-Agent
```python
from scenarios import MCPAgentScenario

scenario = MCPAgentScenario(client_factory, risk_analyzer, mcp_url)
response = await scenario.execute(request)
```

**Flow:** User → MCP Server → Agent 2 (Bing Tool) → Bing API

### Scenario 3: MCP REST API
```python
from scenarios import MCPRestAPIScenario

scenario = MCPRestAPIScenario(client_factory, risk_analyzer, model_name, mcp_url)
response = await scenario.execute(request)
```

**Flow:** User → Agent (MCP Tool) → MCP Server → Bing REST API

## Design Patterns Used

1. **Factory Pattern**: `AzureClientFactory`, `BingToolBuilder`
2. **Strategy Pattern**: Different scenario implementations
3. **Dependency Injection**: Services injected into scenarios
4. **Template Method**: `BaseScenario` defines common flow
5. **Interface Segregation**: Specific interfaces for different concerns

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export AZURE_AI_PROJECT_ENDPOINT="https://your-project.api.azureml.ms"
export AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4o"
export BING_PROJECT_CONNECTION_NAME="your-bing-connection"

# Run refactored UI
streamlit run src/ui/app.py
```

## Testing

Each layer can be tested independently:

```python
# Test core models
from core.models import CompanyRiskRequest, SearchConfig

# Test services
from services import BingToolBuilder, RiskAnalyzer

# Test scenarios (with mocked dependencies)
from scenarios import DirectAgentScenario
```

## Adding New Scenarios

To add a new scenario:

1. Create a new file in `src/scenarios/`
2. Inherit from `BaseScenario`
3. Implement `execute()` method
4. Add UI page in `src/ui/pages/`

```python
class MyNewScenario(BaseScenario):
    async def execute(self, request: CompanyRiskRequest) -> AnalysisResponse:
        # Your implementation
        pass
```

## Migration Notes

- Old `app.py` is still in `src/` for reference
- New entry point: `src/ui/app.py`
- Old imports still work but should be updated
- Backward compatible with existing `.env` files

## File Size Summary

All files respect the <200 lines constraint:

- `core/models.py`: ~70 lines
- `core/interfaces.py`: ~100 lines
- `infrastructure/config.py`: ~110 lines
- `infrastructure/azure_client.py`: ~90 lines
- `infrastructure/tracing.py`: ~110 lines
- `services/bing_tool_builder.py`: ~80 lines
- `services/agent_service.py`: ~140 lines
- `services/risk_analyzer.py`: ~195 lines
- `scenarios/scenario1_direct.py`: ~140 lines
- `scenarios/scenario2_mcp_agent.py`: ~120 lines
- `scenarios/scenario3_mcp_rest.py`: ~145 lines
- `ui/app.py`: ~85 lines
- UI pages: ~100-140 lines each

## Benefits Achieved

✅ **Maintainability**: Each file has a single, clear purpose  
✅ **Readability**: Easy to find and understand code  
✅ **Testability**: Each component can be tested in isolation  
✅ **Extensibility**: New features can be added without modifying existing code  
✅ **Reusability**: Services are shared across scenarios  

## Next Steps

- [ ] Add unit tests for each service
- [ ] Add integration tests for scenarios
- [ ] Refactor MCP server with same principles
- [ ] Add dependency injection container
- [ ] Add logging decorators
