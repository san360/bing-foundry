# Refactoring Plan - Bing Foundry

## Current Issues Identified

### app.py (1789 lines) - Severely Violates SRP
- **Issues:**
  - Single file handling UI, business logic, API calls, and MCP integration
  - Multiple scenarios mixed together
  - Hard to read and maintain
  - Difficult to test individual components

### company_risk_agent.py (432 lines) - Good but can improve
- **Issues:**
  - Mixes agent management with search logic
  - Could be split into smaller, focused classes
  - Some methods are too long

### mcp_server.py & mcp_server_http.py - Code duplication
- **Issues:**
  - Significant code duplication between stdio and HTTP versions
  - Mix of concerns (server, search, tracing)

## SOLID Principles to Apply

1. **Single Responsibility Principle (SRP)**
   - Each class/module should have ONE reason to change
   - Separate UI, business logic, data access, infrastructure

2. **Open/Closed Principle (OCP)**
   - Use interfaces/abstractions for extensibility
   - Use strategy pattern for different scenarios

3. **Liskov Substitution Principle (LSP)**
   - Use base classes for common behavior
   - Ensure derived classes can replace base classes

4. **Interface Segregation Principle (ISP)**
   - Create specific interfaces for different clients
   - Don't force clients to depend on unused methods

5. **Dependency Inversion Principle (DIP)**
   - Depend on abstractions, not concrete implementations
   - Use dependency injection

## New Architecture

```
src/
├── core/                           # Core domain logic
│   ├── __init__.py
│   ├── models.py                   # Data models (<100 lines)
│   └── interfaces.py               # Abstract interfaces (<100 lines)
│
├── services/                       # Business logic layer
│   ├── __init__.py
│   ├── search_service.py           # Bing search orchestration (<150 lines)
│   ├── agent_service.py            # Agent lifecycle management (<150 lines)
│   └── risk_analyzer.py            # Risk analysis logic (<150 lines)
│
├── scenarios/                      # Scenario implementations
│   ├── __init__.py
│   ├── base.py                     # Base scenario class (<100 lines)
│   ├── scenario1_direct.py         # Direct agent with Bing (<150 lines)
│   ├── scenario2_mcp_agent.py      # Agent→MCP→Agent (<150 lines)
│   └── scenario3_mcp_rest.py       # Agent→MCP→REST (<150 lines)
│
├── infrastructure/                 # Infrastructure concerns
│   ├── __init__.py
│   ├── azure_client.py             # Azure client management (<150 lines)
│   ├── tracing.py                  # OpenTelemetry setup (<100 lines)
│   └── config.py                   # Configuration (moved from root) (<100 lines)
│
├── ui/                             # Streamlit UI layer
│   ├── __init__.py
│   ├── app.py                      # Main entry point (<100 lines)
│   ├── components/                 # Reusable UI components
│   │   ├── __init__.py
│   │   ├── sidebar.py              # Sidebar component (<150 lines)
│   │   ├── scenario_tabs.py        # Tab rendering (<150 lines)
│   │   └── results_display.py      # Results display (<150 lines)
│   └── pages/                      # Page-specific logic
│       ├── __init__.py
│       ├── scenario1.py            # Scenario 1 UI (<150 lines)
│       ├── scenario2.py            # Scenario 2 UI (<150 lines)
│       ├── scenario3.py            # Scenario 3 UI (<150 lines)
│       └── documentation.py        # Documentation tab (<150 lines)
│
└── agent/                          # Agent-specific logic (refactored)
    ├── __init__.py
    ├── agent_factory.py            # Factory for creating agents (<100 lines)
    ├── bing_tool_builder.py        # Bing tool configuration (<100 lines)
    └── prompts.py                  # Prompts (already good) (<200 lines)

mcp-server/
├── app/                            # MCP server application
│   ├── __init__.py
│   ├── server.py                   # Main MCP server logic (<150 lines)
│   ├── tools/                      # MCP tool implementations
│   │   ├── __init__.py
│   │   ├── base_tool.py            # Base tool class (<100 lines)
│   │   ├── bing_search_tool.py     # Bing search tool (<150 lines)
│   │   └── risk_analysis_tool.py   # Risk analysis tool (<150 lines)
│   └── transports/                 # Transport implementations
│       ├── __init__.py
│       ├── stdio_transport.py      # STDIO transport (<100 lines)
│       └── http_transport.py       # HTTP transport (<150 lines)
│
└── shared/                         # Shared utilities
    ├── __init__.py
    ├── azure_utils.py              # Azure utilities (<150 lines)
    └── tracing_utils.py            # Tracing utilities (<100 lines)
```

## Refactoring Steps

### Phase 1: Core & Infrastructure (Foundation)
1. Create `core/models.py` - Data models
2. Create `core/interfaces.py` - Abstract interfaces
3. Create `infrastructure/config.py` - Move config
4. Create `infrastructure/azure_client.py` - Azure client wrapper
5. Create `infrastructure/tracing.py` - Tracing setup

### Phase 2: Services Layer
6. Create `services/search_service.py` - Search orchestration
7. Create `services/agent_service.py` - Agent management
8. Create `services/risk_analyzer.py` - Risk analysis logic

### Phase 3: Scenarios
9. Create `scenarios/base.py` - Base scenario interface
10. Create `scenarios/scenario1_direct.py` - Scenario 1
11. Create `scenarios/scenario2_mcp_agent.py` - Scenario 2
12. Create `scenarios/scenario3_mcp_rest.py` - Scenario 3

### Phase 4: UI Layer
13. Create `ui/app.py` - Main entry
14. Create `ui/components/` - Reusable components
15. Create `ui/pages/` - Page-specific logic

### Phase 5: MCP Server
16. Refactor MCP server with shared base
17. Separate transport layers

### Phase 6: Agent Module
18. Refactor agent module into smaller pieces

## Design Patterns to Apply

1. **Factory Pattern** - For creating agents and tools
2. **Strategy Pattern** - For different scenario implementations
3. **Dependency Injection** - For testability
4. **Repository Pattern** - For data access (if needed)
5. **Template Method** - For common scenario flow

## Benefits After Refactoring

1. **Maintainability**: Each file < 200 lines, single responsibility
2. **Testability**: Easy to unit test individual components
3. **Readability**: Clear separation of concerns
4. **Extensibility**: Easy to add new scenarios or features
5. **Reusability**: Common code shared across scenarios

## Testing Strategy

1. Unit tests for each service
2. Integration tests for each scenario
3. End-to-end tests for UI flows
