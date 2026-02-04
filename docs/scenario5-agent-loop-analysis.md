# Scenario 5: Agent Loop Pattern Analysis

## Executive Summary

This document analyzes using the **Agent Loop** (also called "Agentic Loop") pattern for Scenario 5's multi-market research. The agent loop is a fundamental pattern where an agent iteratively calls tools, processes results, and continues until the task is complete.

**Key Insight:** The agent loop pattern is already partially used in Scenario 4. We can enhance it for Scenario 5 using the Threads/Runs API for better control and visibility.

---

## Table of Contents

1. [What is the Agent Loop Pattern?](#1-what-is-the-agent-loop-pattern)
2. [Agent Loop Approaches in Azure AI Foundry](#2-agent-loop-approaches-in-azure-ai-foundry)
3. [Scenario 5 Agent Loop Design](#3-scenario-5-agent-loop-design)
4. [Implementation Options](#4-implementation-options)
5. [Comparison with Current Approach](#5-comparison-with-current-approach)
6. [Recommendation](#6-recommendation)

---

## 1. What is the Agent Loop Pattern?

### Definition

The **Agent Loop** (or **Agentic Loop**) is a pattern where an AI agent:

1. Receives a task/prompt
2. Decides which tool(s) to call
3. Executes tool call(s)
4. Processes results
5. Decides if more tool calls are needed
6. Repeats steps 2-5 until task is complete
7. Returns final response

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT LOOP PATTERN                       │
└─────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   Prompt     │
    │   (Task)     │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │    Agent     │◄──────────────────────┐
    │   Reasoning  │                       │
    └──────┬───────┘                       │
           │                               │
           ▼                               │
    ┌──────────────┐     No more needed    │
    │ Tool Call    │───────────────────────┼──► Final Response
    │  Needed?     │                       │
    └──────┬───────┘                       │
           │ Yes                           │
           ▼                               │
    ┌──────────────┐                       │
    │ Execute Tool │                       │
    │    Call      │                       │
    └──────┬───────┘                       │
           │                               │
           ▼                               │
    ┌──────────────┐                       │
    │   Process    │───────────────────────┘
    │   Results    │
    └──────────────┘
```

### Key Characteristics

| Characteristic | Description |
|----------------|-------------|
| **Autonomy** | Agent decides what tools to call and when |
| **Iteration** | Agent can make multiple tool calls per task |
| **Server-side** | Loop runs on Azure (not in your code) |
| **Natural completion** | Agent determines when task is done |

---

## 2. Agent Loop Approaches in Azure AI Foundry

### 2.1 Responses API (Current Approach)

Used in Scenarios 3 and 4. Single call that handles the loop internally.

```python
# Current approach - single call
response = openai_client.responses.create(
    input=query,
    tool_choice="required",
    extra_body={"agent": {...}}
)
```

**How it works:**
- You make ONE API call
- Azure runs the agent loop internally
- Agent makes tool calls as needed
- Returns final aggregated response

**Pros:** Simple, one API call
**Cons:** No visibility into intermediate steps, no control over loop

### 2.2 Threads/Runs API (Enhanced Control)

More explicit control over the agent loop with visibility into each step.

```python
# Threads/Runs approach - explicit loop control
from azure.ai.projects import AIProjectClient

# 1. Create thread (conversation session)
thread = project_client.agents.threads.create()

# 2. Add message to thread
message = project_client.agents.messages.create(
    thread_id=thread.id,
    role="user",
    content="Search for Microsoft in en-US, de-DE, ja-JP markets"
)

# 3. Create run (starts agent loop)
run = project_client.agents.runs.create(
    thread_id=thread.id,
    agent_id=agent.id
)

# 4. Poll run status (observe the loop)
while run.status in ["queued", "in_progress", "requires_action"]:
    time.sleep(1)
    run = project_client.agents.runs.retrieve(
        thread_id=thread.id,
        run_id=run.id
    )

    # Handle tool calls if needed
    if run.status == "requires_action":
        # Agent is waiting for tool results
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        # Process tool calls...

# 5. Get final messages
messages = project_client.agents.messages.list(thread_id=thread.id)
```

**Pros:** Full visibility, can intercept tool calls, can add messages mid-loop
**Cons:** More complex, more API calls

### 2.3 create_and_process (Simplified Loop)

Convenience method that handles polling automatically.

```python
# Simplified - SDK handles the loop
run = project_client.agents.runs.create_and_process(
    thread_id=thread.id,
    agent_id=agent.id
)
# Returns when complete
```

---

## 3. Scenario 5 Agent Loop Design

### 3.1 Single Agent, Multiple Market Tool Calls

Use ONE agent that loops through markets via tool calls:

```
┌─────────────────────────────────────────────────────────────┐
│            AGENT LOOP FOR MULTI-MARKET SEARCH               │
└─────────────────────────────────────────────────────────────┘

    User: "Analyze Microsoft risk in en-US, de-DE, ja-JP"
                          │
                          ▼
    ┌──────────────────────────────────────────────────────┐
    │              AGENT LOOP (Server-Side)                │
    │                                                      │
    │   Iteration 1:                                       │
    │   └─► Agent thinks: "I need to search en-US first"   │
    │   └─► Tool call: bing_search(market="en-US")         │
    │   └─► Result: [US market data]                       │
    │                                                      │
    │   Iteration 2:                                       │
    │   └─► Agent thinks: "Now search de-DE"               │
    │   └─► Tool call: bing_search(market="de-DE")         │
    │   └─► Result: [German market data]                   │
    │                                                      │
    │   Iteration 3:                                       │
    │   └─► Agent thinks: "Finally search ja-JP"           │
    │   └─► Tool call: bing_search(market="ja-JP")         │
    │   └─► Result: [Japanese market data]                 │
    │                                                      │
    │   Iteration 4:                                       │
    │   └─► Agent thinks: "I have all data, now analyze"   │
    │   └─► No tool call - generate final response         │
    │                                                      │
    └──────────────────────────────────────────────────────┘
                          │
                          ▼
    Final Response: "Cross-market analysis of Microsoft..."
```

### 3.2 Thread-Based Approach for Markets

Use a thread where we add market requests incrementally:

```
┌─────────────────────────────────────────────────────────────┐
│          THREAD-BASED MULTI-MARKET APPROACH                 │
└─────────────────────────────────────────────────────────────┘

    Thread Created
         │
         ├─► Message 1: "Search Microsoft in en-US market"
         │   └─► Run 1 → Agent searches → Response 1
         │
         ├─► Message 2: "Now search de-DE market"
         │   └─► Run 2 → Agent searches → Response 2
         │
         ├─► Message 3: "Now search ja-JP market"
         │   └─► Run 3 → Agent searches → Response 3
         │
         └─► Message 4: "Consolidate all results above"
             └─► Run 4 → Agent analyzes → Final Response
```

**Advantage:** Each market search is a separate run with its own timeout.

---

## 4. Implementation Options

### Option A: Enhanced Single-Agent Loop (Recommended)

Keep the current Responses API but improve prompt engineering.

```python
class AgentLoopMultiMarketScenario:
    """Use single agent with improved loop control."""

    async def execute(self, request, markets):
        agent = self._get_or_create_agent(project_client)

        # Enhanced prompt that guides the agent loop
        prompt = f"""
        You are researching {request.company_name} across multiple markets.

        REQUIRED ACTIONS (execute in order):
        1. Call bing_search_rest_api with market="en-US"
        2. Call bing_search_rest_api with market="de-DE"
        3. Call bing_search_rest_api with market="ja-JP"

        After ALL searches complete, provide cross-market analysis.

        IMPORTANT:
        - Make ONE tool call at a time
        - Wait for each result before the next call
        - Do NOT skip any market
        - Do NOT use training data - only search results
        """

        response = openai_client.responses.create(
            input=prompt,
            tool_choice="required",
            extra_body={"agent": {...}}
        )

        return response
```

### Option B: Threads/Runs with Per-Market Control

Use threads for explicit market-by-market execution.

```python
class ThreadBasedMultiMarketScenario:
    """Use threads for explicit control over market searches."""

    async def execute(self, request, markets):
        project_client = self.client_factory.get_project_client()
        agent = self._get_or_create_agent(project_client)

        # Create thread for this session
        thread = project_client.agents.threads.create()

        market_results = []

        # Run agent for each market
        for market in markets:
            # Add market-specific message
            project_client.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Search for {request.company_name} risks in {market} market using bing_search_rest_api tool."
            )

            # Execute run with timeout
            try:
                run = project_client.agents.runs.create_and_process(
                    thread_id=thread.id,
                    agent_id=agent.id,
                    timeout=90  # Per-market timeout
                )
                market_results.append({
                    "market": market,
                    "status": "success",
                    "run_id": run.id
                })
            except TimeoutError:
                market_results.append({
                    "market": market,
                    "status": "timeout"
                })

        # Final consolidation message
        project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content="Now provide a comprehensive cross-market analysis based on all the search results above."
        )

        final_run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent.id
        )

        # Get all messages
        messages = project_client.agents.messages.list(thread_id=thread.id)

        return self._build_response(messages, market_results)
```

### Option C: Hybrid - Parallel Threads per Market

Create multiple threads (one per market) and run in parallel.

```python
class ParallelThreadsScenario:
    """Run separate threads for each market in parallel."""

    async def execute(self, request, markets):
        agent = self._get_or_create_agent(project_client)

        # Create parallel tasks for each market
        async def search_market(market):
            thread = project_client.agents.threads.create()

            project_client.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Search for {request.company_name} in {market}"
            )

            run = await asyncio.to_thread(
                project_client.agents.runs.create_and_process,
                thread_id=thread.id,
                agent_id=agent.id
            )

            messages = project_client.agents.messages.list(thread_id=thread.id)
            return {"market": market, "messages": messages}

        # Run all markets in parallel
        results = await asyncio.gather(*[
            search_market(m) for m in markets
        ], return_exceptions=True)

        # Consolidation in separate thread
        consolidation_thread = project_client.agents.threads.create()
        # ... add results and get final analysis
```

---

## 5. Comparison with Current Approach

| Aspect | Current (Scenario 5) | Option A (Single Loop) | Option B (Threads) | Option C (Parallel Threads) |
|--------|----------------------|------------------------|--------------------|-----------------------------|
| **Execution** | Parallel (asyncio) | Sequential (agent) | Sequential | Parallel |
| **Control** | Python code | Agent decides | Explicit per-market | Explicit per-market |
| **Visibility** | Custom tracing | Agent tracing | Thread/Run history | Thread/Run history |
| **Timeout** | Per-market | Overall only | Per-market | Per-market |
| **Complexity** | Medium | Low | Medium | High |
| **Speed (5 markets)** | ~45 sec | ~150 sec | ~150 sec | ~45 sec |
| **Foundry Integration** | Agents only | Agents only | Full (threads visible) | Full (threads visible) |

---

## 6. Recommendation

### For Production: Keep Current + Add Thread Visibility

Enhance the current parallel implementation with optional thread logging:

```python
class WorkflowMultiMarketScenario:
    """Enhanced scenario with thread-based visibility."""

    async def execute(self, request, markets, use_threads=False):
        if use_threads:
            # Use Option C for full Foundry visibility
            return await self._execute_with_threads(request, markets)
        else:
            # Use current parallel asyncio for speed
            return await self._execute_parallel(request, markets)
```

### For Simplicity: Option A (Single Agent Loop)

If you want simpler code and don't need parallel execution:

```python
# Simplest approach - let the agent loop
response = openai_client.responses.create(
    input=f"Search {company} in markets: {markets}. Make one tool call per market.",
    tool_choice="required",
    extra_body={"agent": {...}}
)
```

### Summary Decision Matrix

| Priority | Recommended Approach |
|----------|---------------------|
| **Speed** | Current (parallel asyncio) |
| **Simplicity** | Option A (single agent loop) |
| **Visibility** | Option B (threads/runs) |
| **Speed + Visibility** | Option C (parallel threads) |

---

## Code Example: Option A Implementation

Here's how to simplify Scenario 5 using the pure agent loop pattern:

```python
"""
Scenario 5 Alternative: Pure Agent Loop Pattern

This uses the native agent loop - the agent decides how to iterate
through markets based on instructions.
"""

class AgentLoopMultiMarketScenario(BaseScenario):
    """
    Multi-market search using native agent loop.

    The agent internally loops through markets, making
    one tool call at a time until all markets are searched.
    """

    AGENT_NAME = "BingFoundry-AgentLoop"

    async def execute(self, request, markets):
        project_client = self.client_factory.get_project_client()
        openai_client = self.client_factory.get_openai_client()

        agent = self._get_or_create_agent(project_client)

        # Build prompt that guides the agent loop
        market_instructions = "\n".join([
            f"{i+1}. Call bing_search_rest_api with market=\"{m}\""
            for i, m in enumerate(markets)
        ])

        prompt = f"""
# Multi-Market Company Risk Research

## Company: {request.company_name}

## Your Task
Search for risk information about {request.company_name} in {len(markets)} different markets.

## Required Tool Calls (IN THIS ORDER):
{market_instructions}

## Instructions
1. Make ONE tool call at a time
2. Wait for each result before proceeding
3. After ALL {len(markets)} searches are complete, analyze the results
4. Provide a cross-market comparative analysis

## Output Format
After gathering all results, structure your response as:

### Market-by-Market Findings
[Summary for each market]

### Cross-Market Patterns
[Common themes across regions]

### Regional Differences
[Important variations between markets]

### Global Risk Assessment
[Overall risk profile]

IMPORTANT: Do NOT use your training data. Base analysis ONLY on search results.
"""

        with tracer.start_as_current_span("scenario5.agent_loop"):
            response = openai_client.responses.create(
                input=prompt,
                tool_choice="required",
                extra_body={
                    "agent": {
                        "name": agent.name,
                        "version": _get_agent_version(agent),
                        "type": "agent_reference",
                    }
                }
            )

        return self._build_response(response)
```

---

## Document Information

| Attribute | Value |
|-----------|-------|
| Created | 2026-02-04 |
| Author | AI Analysis |
| Version | 1.0 |
| Status | Complete |

---

## Conclusion

The **Agent Loop** pattern is a valid approach for Scenario 5. The key trade-off is:

- **Agent Loop (Sequential)**: Simpler code, agent manages iteration, but slower
- **Current (Parallel asyncio)**: Faster execution, more control, but more complex

**Recommendation:** Keep the current parallel implementation for production performance, but consider adding the Threads/Runs API for better Foundry portal visibility when debugging is needed.
