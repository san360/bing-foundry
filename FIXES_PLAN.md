# Analysis and Implementation Plan

## Issues Identified

### 1. Scenario 3 - Two Tools Configured ❌
**Current:** `allowed_tools=["bing_search_rest_api", "analyze_company_risk_rest_api"]`
**Expected:** Only ONE tool wrapping Bing REST API

**Root Cause:** Line 62 in scenario3_mcp_rest.py has two tools configured
**Fix:** Keep only `bing_search_rest_api` (the direct REST API wrapper)

### 2. Scenario 2 - Agent Creation Unclear
**Current:** MCP server creates an agent inside the tool call
**Issue:** Not visible to user when/how many agents are created

**Root Cause:** Agent creation happens inside MCP server (mcp_server.py)
**Fix:** 
- Add logging to show agent creation in MCP server
- Return agent_id in metadata to Streamlit UI

### 3. Verbose Logging - HTTP Requests
**Current:** aiohttp logs every HTTP request at INFO level
**Issues:**
- MCP server logs every HTTP request
- Too much noise in logs

**Fix:**
- Set aiohttp logger to WARNING level
- Reduce Azure SDK logging
- Keep only key business logic logs

### 4. Missing Agent/Thread ID Display
**Current:** No agent ID or thread ID shown in UI
**Fix:** Display for all scenarios:
- Scenario 1: Agent name, version
- Scenario 2: Agent ID created in MCP server
- Scenario 3: Agent ID, thread ID

## Implementation Steps

### Step 1: Fix Scenario 3 - Single Tool Only
- Remove `analyze_company_risk_rest_api` from allowed_tools
- Keep only `bing_search_rest_api`

### Step 2: Add Agent ID Logging to MCP Server
- Update mcp_server.py and mcp_server_http.py
- Log when agent is created
- Return agent_id in response

### Step 3: Reduce Verbose Logging
- Set aiohttp to WARNING
- Set azure libraries to WARNING
- Set httpx to WARNING
- Keep application logic at INFO

### Step 4: Display Agent/Thread IDs in UI
- Update all scenario UI pages
- Show agent_id, agent_name, version
- Show thread_id if available
- Format nicely in expander

### Step 5: Update Scenario Implementations
- Ensure all scenarios capture agent metadata
- Return in AnalysisResponse metadata
