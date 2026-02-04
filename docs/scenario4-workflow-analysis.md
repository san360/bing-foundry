# Scenario 4 Workflow-Based Architecture Analysis

## Executive Summary

This document analyzes the feasibility and implementation approach for using **Azure AI Foundry Workflows** (via the Microsoft Agent Framework) to resolve timeout issues in Scenario 4's multi-market research functionality. The proposed solution replaces the current sequential prompt-driven approach with a structured workflow that executes market-specific searches in parallel, then consolidates results.

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Problem Statement](#2-problem-statement)
3. [Microsoft Agent Framework Overview](#3-microsoft-agent-framework-overview)
4. [Proposed Workflow Architecture](#4-proposed-workflow-architecture)
5. [Implementation Approaches](#5-implementation-approaches)
6. [Technical Design](#6-technical-design)
7. [Comparison: Current vs Workflow Approach](#7-comparison-current-vs-workflow-approach)
8. [Risk Assessment](#8-risk-assessment)
9. [Implementation Recommendations](#9-implementation-recommendations)
10. [Appendix](#appendix)

---

## 1. Current State Analysis

### 1.1 How Scenario 4 Works Today

Scenario 4 (`src/scenarios/scenario4_multi_market.py`) implements a **single reusable agent** that makes multiple MCP tool calls with different market parameters:

```
User Input → AI Agent (BingFoundry-MultiMarket)
    → MCP Tool Call (market 1)
    → MCP Tool Call (market 2)
    → MCP Tool Call (market N)
    → Aggregate Results
    → Final Response
```

**Key Characteristics:**

| Aspect | Current Implementation |
|--------|----------------------|
| Agent Name | `BingFoundry-MultiMarket` |
| Market Specification | Prompt-based (embedded in user query) |
| Tool Calls | Sequential, one per market |
| HTTP Timeout | 120 seconds per REST API call |
| Overall Timeout | NOT SET (potential issue) |
| Execution Control | Agent-driven (AI decides how many calls) |

### 1.2 Current Code Flow

```python
# From scenario4_multi_market.py

async def execute(self, request, markets=None):
    # 1. Build prompt with explicit market instructions
    query = self._build_multi_market_prompt(request, markets)

    # 2. Single agent call - agent decides to call tool N times
    response = openai_client.responses.create(
        input=query,
        tool_choice="required",
        extra_body={"agent": {...}}
    )

    # 3. Extract citations from aggregated response
    citations = self._extract_citations(response)
```

**The Prompt-Driven Loop Pattern:**

```python
def _build_multi_market_prompt(self, request, markets):
    """Agent is instructed to make N separate tool calls"""
    return f"""
    You MUST search EXACTLY {len(markets)} markets.
    Make {len(markets)} SEPARATE tool calls:
       1. Call bing_search_rest_api with market="en-US"
       2. Call bing_search_rest_api with market="de-DE"
       3. Call bing_search_rest_api with market="ja-JP"
    ...
    """
```

### 1.3 How Scenario 3 Works (Reference Pattern)

Scenario 3 (`src/scenarios/scenario3_mcp_rest.py`) demonstrates a simpler single-market pattern that works reliably:

```
User → AI Agent (BingFoundry-MCPAgent)
    → MCP Tool (bing_search_rest_api)
    → Bing REST API
    → Results
```

**Key Success Factors:**
- Single market per request
- Single tool invocation
- Predictable execution time (~15-30 seconds)
- No timeout issues

---

## 2. Problem Statement

### 2.1 Timeout Issues in Scenario 4

When executing multi-market searches, users experience timeout errors due to:

#### A. Cumulative Execution Time

| Markets | Avg Time per Market | Total Sequential Time | Risk Level |
|---------|--------------------|-----------------------|------------|
| 3 | 30-40 sec | 90-120 sec | Medium |
| 5 | 30-40 sec | 150-200 sec | High |
| 7+ | 30-40 sec | 210+ sec | Critical |

#### B. Timeout Configuration Gaps

```
┌──────────────────────────────────────────────────────────────┐
│                    TIMEOUT BOUNDARIES                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  MCP Server HTTP Client: 120 seconds per call                │
│  │                                                           │
│  ├─→ Azure REST API: No explicit timeout set                 │
│  │                                                           │
│  └─→ Agent Response Creation: No timeout wrapper             │
│                                                              │
│  Streamlit UI: Browser connection timeout (~5-10 minutes)    │
│                                                              │
│  ⚠️ NO OVERALL TIMEOUT on execute() method                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### C. Root Causes

1. **Sequential Execution**: Agent processes markets one-by-one, not in parallel
2. **No Progress Feedback**: User sees no intermediate status during long operations
3. **All-or-Nothing**: Single failure can timeout entire operation
4. **Agent Unpredictability**: AI model may not follow exact N-call instructions
5. **No Retry Logic**: Failed market searches cause full operation failure

### 2.2 User Impact

- UI appears frozen during multi-market searches
- Inconsistent behavior with 5+ markets
- No visibility into which markets completed
- Wasted compute when operation times out near completion

---

## 3. Microsoft Agent Framework Overview

### 3.1 What is the Agent Framework?

Microsoft Agent Framework is an **open-source SDK** for building multi-agent systems with structured orchestration:

```bash
pip install agent-framework --pre
```

**Core Capabilities:**

| Feature | Description |
|---------|-------------|
| **Sequential Execution** | Run agents/tasks one after another |
| **Concurrent Execution** | Run multiple agents/tasks in parallel |
| **Graph-Based Workflows** | Model complex agent interactions |
| **Checkpointing** | Save/resume long-running processes |
| **Composability** | Nest workflows within workflows |
| **Hand-off Patterns** | Transfer tasks between agents |

### 3.2 Key Concepts

#### Executors
Processing units that receive input messages, perform tasks, and produce output messages.

```python
# Conceptual example
class MarketSearchExecutor:
    async def execute(self, market: str, query: str) -> SearchResult:
        # Call Bing search for specific market
        return await bing_search(query, market=market)
```

#### Edges
Connections between executors that determine message flow and can include routing conditions.

```python
# Edge definition (conceptual)
workflow.add_edge(
    source="market_splitter",
    target="market_search_executor",
    condition=lambda msg: msg.market in SUPPORTED_MARKETS
)
```

#### Workflows
Directed graphs of executors and edges that define complete orchestration patterns.

```
              ┌─────────────────┐
              │  Input Request  │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │ Market Splitter │  (Splits into N parallel paths)
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
    │Market 1 │   │Market 2 │   │Market 3 │   (Parallel Execution)
    │ Search  │   │ Search  │   │ Search  │
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
         └─────────────┼─────────────┘
                       │
              ┌────────▼────────┐
              │   Aggregator    │  (Consolidates results)
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │ Analysis Agent  │  (Generates final report)
              └─────────────────┘
```

### 3.3 Integration with Azure AI Foundry

The Agent Framework integrates with the Foundry SDK:

```python
from agent_framework import Workflow, Executor
from azure.ai.projects import AIProjectClient

# Framework uses Foundry's project endpoint
endpoint = "https://<resource>.services.ai.azure.com/api/projects/<project>"

# Executors can call Foundry agents
class FoundryAgentExecutor(Executor):
    async def execute(self, input):
        response = await self.foundry_client.responses.create(...)
        return response
```

---

## 4. Proposed Workflow Architecture

### 4.1 High-Level Design

Replace the current prompt-driven sequential approach with a **structured workflow** that orchestrates market-specific searches in parallel:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW-BASED MULTI-MARKET SEARCH                   │
└─────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────────────┐
                         │   CompanyRiskRequest │
                         │   + List[markets]    │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   Market Dispatcher  │
                         │   (Split by market)  │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
    ┌─────────▼─────────┐ ┌────────▼────────┐ ┌─────────▼─────────┐
    │ Market Search     │ │ Market Search   │ │ Market Search     │
    │ Executor (en-US)  │ │ Executor (de-DE)│ │ Executor (ja-JP)  │
    │                   │ │                 │ │                   │
    │ Uses Scenario 3   │ │ Uses Scenario 3 │ │ Uses Scenario 3   │
    │ pattern (single   │ │ pattern (single │ │ pattern (single   │
    │ market MCP call)  │ │ market MCP call)│ │ market MCP call)  │
    └─────────┬─────────┘ └────────┬────────┘ └─────────┬─────────┘
              │                    │                    │
              │         PARALLEL EXECUTION              │
              │         (with individual timeouts)      │
              │                    │                    │
    ┌─────────▼─────────┐ ┌────────▼────────┐ ┌────────▼─────────┐
    │ MarketResult      │ │ MarketResult    │ │ MarketResult     │
    │ - text            │ │ - text          │ │ - text           │
    │ - citations       │ │ - citations     │ │ - citations      │
    │ - market          │ │ - market        │ │ - market         │
    │ - status          │ │ - status        │ │ - status         │
    └─────────┬─────────┘ └────────┬────────┘ └────────┬─────────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Result Aggregator │
                        │   (Merge results,   │
                        │    handle failures) │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Analysis Agent    │
                        │   (BingFoundry-     │
                        │    MultiMarket)     │
                        │                     │
                        │   Generates cross-  │
                        │   market comparison │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   AnalysisResponse  │
                        │   - Combined text   │
                        │   - All citations   │
                        │   - Market metadata │
                        └─────────────────────┘
```

### 4.2 Key Design Decisions

#### Decision 1: Reuse Scenario 3 Pattern for Individual Searches

Each market search uses the proven Scenario 3 pattern:
- Single market per call
- Predictable timeout (30-40 seconds)
- Reliable MCP tool execution

#### Decision 2: Parallel Execution with Timeout per Market

```python
# Each market search has its own timeout
async def search_market(market: str, query: str, timeout: int = 60):
    try:
        async with asyncio.timeout(timeout):
            return await scenario3_executor.execute(query, market)
    except asyncio.TimeoutError:
        return MarketResult(market=market, status="timeout", text="")
```

#### Decision 3: Graceful Degradation

- If some markets fail, continue with successful ones
- Report partial results with clear failure indicators
- User sees which markets completed vs failed

#### Decision 4: Final Analysis via Dedicated Agent

A separate agent receives all market results and generates the cross-market analysis:
- Input: Concatenated results from all markets
- Output: Structured comparative analysis
- No tool calls required (analysis only)

---

## 5. Implementation Approaches

### 5.1 Approach A: Full Agent Framework Integration

Use the Microsoft Agent Framework for complete workflow orchestration.

**Pros:**
- Official Microsoft solution
- Built-in checkpointing, error handling
- Scalable for complex workflows
- Clear separation of concerns

**Cons:**
- Additional dependency (`agent-framework`)
- Learning curve for new SDK
- Still in preview (`--pre` flag)
- May add complexity for this use case

**Code Structure:**

```python
from agent_framework import Workflow, Executor, Edge

class MarketSearchWorkflow:
    def __init__(self):
        self.workflow = Workflow()

        # Add executors
        self.workflow.add_executor("dispatcher", MarketDispatcher())
        self.workflow.add_executor("search", MarketSearchExecutor())
        self.workflow.add_executor("aggregator", ResultAggregator())
        self.workflow.add_executor("analyzer", AnalysisAgent())

        # Define edges
        self.workflow.add_edge("dispatcher", "search", fan_out=True)
        self.workflow.add_edge("search", "aggregator", fan_in=True)
        self.workflow.add_edge("aggregator", "analyzer")
```

### 5.2 Approach B: Native asyncio Workflow

Implement workflow logic using Python's native asyncio without additional frameworks.

**Pros:**
- No new dependencies
- Full control over execution
- Simpler for this specific use case
- Leverages existing codebase patterns

**Cons:**
- Manual implementation of orchestration
- No built-in checkpointing
- Less reusable for other workflows

**Code Structure:**

```python
import asyncio
from scenarios.scenario3_mcp_rest import MCPRestAPIScenario

class WorkflowMultiMarketScenario:
    async def execute(self, request, markets):
        # Phase 1: Dispatch parallel searches
        search_tasks = [
            self._search_market(request, market)
            for market in markets
        ]

        # Phase 2: Execute in parallel with individual timeouts
        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Phase 3: Aggregate successful results
        aggregated = self._aggregate_results(results, markets)

        # Phase 4: Generate cross-market analysis
        analysis = await self._generate_analysis(aggregated)

        return analysis
```

### 5.3 Approach C: Hybrid - Foundry Agents with asyncio Orchestration

Combine Azure AI Foundry agents with asyncio orchestration, maintaining compatibility with existing patterns.

**Pros:**
- Uses existing Scenario 3 code
- Maintains Foundry portal visibility
- Minimal new dependencies
- Production-ready pattern

**Cons:**
- Manual orchestration code
- Agent management overhead

**Recommended Approach: This provides the best balance of reliability, maintainability, and integration with the existing codebase.**

---

## 6. Technical Design

### 6.1 New Data Models

```python
# Add to src/core/models.py

@dataclass
class MarketSearchResult:
    """Result from a single market search."""
    market: str
    status: Literal["success", "timeout", "error"]
    text: str
    citations: List[Citation]
    execution_time_ms: int
    error_message: Optional[str] = None

@dataclass
class AggregatedMarketResults:
    """Consolidated results from all markets."""
    successful_markets: List[str]
    failed_markets: List[str]
    results: List[MarketSearchResult]
    total_citations: List[Citation]

@dataclass
class WorkflowExecutionMetadata:
    """Metadata about workflow execution."""
    total_markets: int
    successful_count: int
    failed_count: int
    total_execution_time_ms: int
    parallel_execution: bool
```

### 6.2 New Scenario Implementation

```python
# src/scenarios/scenario4_workflow.py

import asyncio
from typing import List
from dataclasses import dataclass

from .base import BaseScenario
from .scenario3_mcp_rest import MCPRestAPIScenario
from core.models import (
    CompanyRiskRequest,
    AnalysisResponse,
    MarketSearchResult,
    AggregatedMarketResults,
)


class WorkflowMultiMarketScenario(BaseScenario):
    """
    Workflow-based multi-market research using parallel execution.

    This scenario orchestrates multiple market searches in parallel,
    then aggregates results and generates a cross-market analysis.

    Architecture:
        1. Market Dispatcher: Splits request into market-specific tasks
        2. Market Search (parallel): Executes Scenario 3 pattern per market
        3. Aggregator: Consolidates results, handles failures
        4. Analysis Agent: Generates comparative insights
    """

    MARKET_TIMEOUT_SECONDS = 90  # Per-market timeout
    OVERALL_TIMEOUT_SECONDS = 300  # 5 minutes total

    def __init__(self, client_factory, risk_analyzer, mcp_url: str):
        super().__init__(client_factory, risk_analyzer)
        self.mcp_url = mcp_url
        self._search_scenario = MCPRestAPIScenario(
            client_factory, risk_analyzer, mcp_url
        )

    async def execute(
        self,
        request: CompanyRiskRequest,
        markets: List[str]
    ) -> AnalysisResponse:
        """Execute multi-market workflow."""

        with tracer.start_as_current_span(
            "scenario4.workflow",
            attributes={
                "company": request.company_name,
                "markets": ",".join(markets),
                "market_count": len(markets),
            }
        ) as span:

            # Phase 1: Parallel market searches
            market_results = await self._execute_parallel_searches(
                request, markets
            )

            # Phase 2: Aggregate results
            aggregated = self._aggregate_results(market_results, markets)

            span.set_attribute(
                "successful_markets",
                len(aggregated.successful_markets)
            )
            span.set_attribute(
                "failed_markets",
                len(aggregated.failed_markets)
            )

            # Phase 3: Generate cross-market analysis
            analysis = await self._generate_cross_market_analysis(
                request, aggregated
            )

            return analysis

    async def _execute_parallel_searches(
        self,
        request: CompanyRiskRequest,
        markets: List[str],
    ) -> List[MarketSearchResult]:
        """Execute searches for all markets in parallel."""

        tasks = [
            self._search_single_market(request, market)
            for market in markets
        ]

        # Execute all in parallel with overall timeout
        try:
            async with asyncio.timeout(self.OVERALL_TIMEOUT_SECONDS):
                results = await asyncio.gather(
                    *tasks,
                    return_exceptions=True
                )
        except asyncio.TimeoutError:
            logger.error("Overall workflow timeout exceeded")
            # Return partial results
            results = [
                MarketSearchResult(
                    market=m,
                    status="timeout",
                    text="",
                    citations=[],
                    execution_time_ms=0
                )
                for m in markets
            ]

        return self._process_gather_results(results, markets)

    async def _search_single_market(
        self,
        request: CompanyRiskRequest,
        market: str,
    ) -> MarketSearchResult:
        """Search a single market with timeout protection."""

        start_time = time.time()

        try:
            async with asyncio.timeout(self.MARKET_TIMEOUT_SECONDS):
                # Create market-specific request
                market_request = CompanyRiskRequest(
                    company_name=request.company_name,
                    risk_category=request.risk_category,
                    search_config=SearchConfig(market=market),
                    scenario_type=ScenarioType.MCP_REST_API,
                )

                # Use Scenario 3 pattern for single market
                result = await self._search_scenario.execute(market_request)

                execution_time = int((time.time() - start_time) * 1000)

                return MarketSearchResult(
                    market=market,
                    status="success",
                    text=result.text,
                    citations=result.citations,
                    execution_time_ms=execution_time,
                )

        except asyncio.TimeoutError:
            logger.warning(f"Timeout searching market: {market}")
            return MarketSearchResult(
                market=market,
                status="timeout",
                text="",
                citations=[],
                execution_time_ms=self.MARKET_TIMEOUT_SECONDS * 1000,
                error_message="Search timed out",
            )

        except Exception as e:
            logger.error(f"Error searching market {market}: {e}")
            return MarketSearchResult(
                market=market,
                status="error",
                text="",
                citations=[],
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )

    def _aggregate_results(
        self,
        results: List[MarketSearchResult],
        markets: List[str],
    ) -> AggregatedMarketResults:
        """Aggregate results from all markets."""

        successful = [r for r in results if r.status == "success"]
        failed = [r for r in results if r.status != "success"]

        all_citations = []
        for result in successful:
            all_citations.extend(result.citations)

        return AggregatedMarketResults(
            successful_markets=[r.market for r in successful],
            failed_markets=[r.market for r in failed],
            results=results,
            total_citations=all_citations,
        )

    async def _generate_cross_market_analysis(
        self,
        request: CompanyRiskRequest,
        aggregated: AggregatedMarketResults,
    ) -> AnalysisResponse:
        """Generate cross-market comparative analysis."""

        # Build context from all market results
        market_context = self._build_market_context(aggregated)

        # Create analysis prompt
        analysis_prompt = f"""
You are analyzing company risk information gathered from multiple markets.

## Company: {request.company_name}

## Markets Searched Successfully: {', '.join(aggregated.successful_markets)}
## Markets Failed: {', '.join(aggregated.failed_markets) or 'None'}

## Market-Specific Findings:

{market_context}

## Your Task:

Based on the above market-specific findings, provide:

1. **Market-by-Market Summary**: Key findings from each market
2. **Cross-Market Patterns**: Common themes across regions
3. **Regional Differences**: Important variations between markets
4. **Global Risk Assessment**: Overall risk profile considering all markets

Note: Some markets may have failed to return results. Focus your analysis
on the successful markets and note any gaps in coverage.
"""

        # Use existing agent to generate analysis
        # This agent does NOT need to make tool calls - just analysis
        response = await self._generate_analysis_response(analysis_prompt)

        return AnalysisResponse(
            text=response.text,
            citations=aggregated.total_citations,
            market_used=",".join(aggregated.successful_markets),
            metadata={
                "workflow": "parallel_multi_market",
                "total_markets": len(aggregated.results),
                "successful_markets": len(aggregated.successful_markets),
                "failed_markets": len(aggregated.failed_markets),
                "market_results": [
                    {
                        "market": r.market,
                        "status": r.status,
                        "execution_time_ms": r.execution_time_ms,
                    }
                    for r in aggregated.results
                ],
            },
        )

    def _build_market_context(
        self,
        aggregated: AggregatedMarketResults
    ) -> str:
        """Build context string from market results."""

        context_parts = []

        for result in aggregated.results:
            if result.status == "success":
                context_parts.append(f"""
### {result.market}
{result.text}

Citations: {len(result.citations)} sources
Execution Time: {result.execution_time_ms}ms
""")
            else:
                context_parts.append(f"""
### {result.market}
Status: {result.status}
Error: {result.error_message or 'Unknown error'}
""")

        return "\n".join(context_parts)
```

### 6.3 UI Integration

```python
# Updates to src/ui/pages/scenario4.py

async def run_workflow_analysis(company_name, markets, mcp_url):
    """Run the workflow-based multi-market analysis."""

    # Show progress indicator
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Initialize scenario
    scenario = WorkflowMultiMarketScenario(
        client_factory=client_factory,
        risk_analyzer=risk_analyzer,
        mcp_url=mcp_url,
    )

    # Execute with progress updates
    status_text.text(f"Searching {len(markets)} markets in parallel...")

    try:
        result = await scenario.execute(request, markets)

        # Display results
        st.success(
            f"Completed: {result.metadata['successful_markets']} markets successful, "
            f"{result.metadata['failed_markets']} failed"
        )

        # Show market-by-market status
        with st.expander("Market Search Status"):
            for market_result in result.metadata['market_results']:
                icon = "✅" if market_result['status'] == 'success' else "❌"
                st.write(
                    f"{icon} {market_result['market']}: "
                    f"{market_result['status']} "
                    f"({market_result['execution_time_ms']}ms)"
                )

        # Display analysis
        st.markdown(result.text)

        # Display citations
        if result.citations:
            with st.expander(f"Citations ({len(result.citations)})"):
                for citation in result.citations:
                    st.markdown(f"- [{citation.title}]({citation.url})")

    except Exception as e:
        st.error(f"Workflow error: {e}")
```

### 6.4 Configuration Updates

```python
# Add to src/infrastructure/config.py

@dataclass
class WorkflowConfig:
    """Configuration for workflow execution."""

    # Per-market timeout in seconds
    market_timeout_seconds: int = 90

    # Overall workflow timeout in seconds
    overall_timeout_seconds: int = 300

    # Maximum concurrent market searches
    max_concurrent_searches: int = 10

    # Whether to continue on partial failures
    allow_partial_results: bool = True

    # Minimum successful markets required
    min_successful_markets: int = 1

    @classmethod
    def from_env(cls) -> "WorkflowConfig":
        return cls(
            market_timeout_seconds=int(
                os.getenv("WORKFLOW_MARKET_TIMEOUT", "90")
            ),
            overall_timeout_seconds=int(
                os.getenv("WORKFLOW_OVERALL_TIMEOUT", "300")
            ),
            max_concurrent_searches=int(
                os.getenv("WORKFLOW_MAX_CONCURRENT", "10")
            ),
            allow_partial_results=os.getenv(
                "WORKFLOW_ALLOW_PARTIAL", "true"
            ).lower() == "true",
            min_successful_markets=int(
                os.getenv("WORKFLOW_MIN_SUCCESS", "1")
            ),
        )
```

---

## 7. Comparison: Current vs Workflow Approach

### 7.1 Execution Time Comparison

| Scenario | 3 Markets | 5 Markets | 7 Markets |
|----------|-----------|-----------|-----------|
| **Current (Sequential)** | ~120 sec | ~200 sec | ~280 sec |
| **Workflow (Parallel)** | ~45 sec | ~50 sec | ~55 sec |
| **Improvement** | 2.7x | 4x | 5x |

*Assumes 35-40 seconds average per market search*

### 7.2 Failure Handling Comparison

| Aspect | Current | Workflow |
|--------|---------|----------|
| Single market failure | Entire operation may fail | Other markets continue |
| Timeout behavior | All-or-nothing | Per-market isolation |
| User feedback | None until complete | Progress + partial results |
| Retry capability | Must retry all | Can retry failed markets only |

### 7.3 Resource Utilization

| Resource | Current | Workflow |
|----------|---------|----------|
| Agent instances | 1 (makes N calls) | 1 orchestrator + N search tasks |
| MCP connections | Sequential | Parallel (up to max_concurrent) |
| Memory usage | Lower | Higher (concurrent results) |
| Network efficiency | Poor (idle waits) | Better (parallel requests) |

### 7.4 Observability Comparison

| Aspect | Current | Workflow |
|--------|---------|----------|
| Trace granularity | Single span | Per-market spans |
| Failure attribution | Unclear | Market-specific |
| Performance metrics | Total time only | Per-market breakdown |
| Debug capability | Limited | Detailed per-market logs |

---

## 8. Risk Assessment

### 8.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MCP server overload from parallel calls | Medium | Medium | Implement max_concurrent_searches limit |
| Memory pressure from holding N results | Low | Low | Stream results if needed |
| Inconsistent agent behavior | Low | Medium | Separate analysis from search |
| Azure throttling | Medium | High | Add exponential backoff |

### 8.2 Implementation Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing Scenario 4 | Low | High | Keep old implementation, add new |
| Agent Framework instability (preview) | Medium | Medium | Use native asyncio approach |
| Complex testing requirements | Medium | Medium | Unit test each component |

### 8.3 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Higher compute costs (parallel execution) | High | Low | Monitor and set limits |
| Complex debugging | Medium | Medium | Enhanced logging and tracing |
| Increased MCP server load | High | Medium | Horizontal scaling |

---

## 9. Implementation Recommendations

### 9.1 Recommended Approach

**Use Approach C: Hybrid Foundry Agents with asyncio Orchestration**

Rationale:
- Minimizes new dependencies
- Reuses proven Scenario 3 code
- Maintains Foundry portal visibility
- Production-ready patterns
- Incremental migration path

### 9.2 Implementation Phases

#### Phase 1: Core Workflow Engine (1 sprint)
- Implement `WorkflowMultiMarketScenario` class
- Add new data models
- Create parallel execution logic
- Add per-market timeout handling

#### Phase 2: Result Aggregation (0.5 sprint)
- Implement result merging logic
- Handle partial failures gracefully
- Build market context for analysis

#### Phase 3: Analysis Agent (0.5 sprint)
- Create dedicated analysis agent (no tools)
- Implement cross-market comparison prompt
- Generate structured output format

#### Phase 4: UI Integration (0.5 sprint)
- Add progress indicators
- Display per-market status
- Show partial results on failure

#### Phase 5: Testing & Validation (1 sprint)
- Unit tests for each component
- Integration tests with MCP server
- Performance benchmarking
- Timeout scenario testing

### 9.3 Migration Strategy

1. **Preserve Current Implementation**: Keep `scenario4_multi_market.py` as-is
2. **Add New Implementation**: Create `scenario4_workflow.py` alongside
3. **UI Toggle**: Add option to switch between approaches
4. **Gradual Rollout**: Default to current, allow opt-in to workflow
5. **Validation Period**: Monitor both approaches in production
6. **Full Migration**: Once validated, make workflow the default

### 9.4 Success Criteria

| Metric | Target |
|--------|--------|
| 5-market search time | < 60 seconds |
| 7-market search time | < 90 seconds |
| Partial failure handling | 80%+ markets succeed → show results |
| User feedback | Progress visible within 5 seconds |
| Error attribution | Market-specific failure tracking |

---

## Appendix

### A. Supported Markets Reference

From `mcp_server_http.py`:

```python
SUPPORTED_MARKETS = [
    # Americas
    "en-US", "es-US", "en-CA", "fr-CA", "es-MX", "pt-BR",
    "es-AR", "es-CL", "es-CO", "es-PE", "es-VE",

    # Europe
    "en-GB", "de-DE", "de-AT", "de-CH", "fr-FR", "fr-BE",
    "fr-CH", "es-ES", "it-IT", "nl-NL", "nl-BE", "pl-PL",
    "ru-RU", "sv-SE", "da-DK", "fi-FI", "no-NO", "tr-TR",

    # Asia Pacific
    "ja-JP", "ko-KR", "zh-CN", "zh-TW", "zh-HK",
    "en-AU", "en-NZ", "en-IN", "en-PH", "en-MY", "en-ID",

    # Middle East & Africa
    "ar-SA", "en-ZA",
]
```

### B. Error Codes Reference

| Error Code | Description | Handling |
|------------|-------------|----------|
| `MARKET_TIMEOUT` | Single market search exceeded timeout | Mark market as failed, continue others |
| `WORKFLOW_TIMEOUT` | Overall workflow exceeded timeout | Return partial results |
| `MCP_ERROR` | MCP server communication error | Retry with backoff |
| `AGENT_ERROR` | Agent execution error | Log and mark as failed |
| `AGGREGATION_ERROR` | Result merging failed | Return raw results |

### C. Microsoft Agent Framework Resources

- Documentation: https://learn.microsoft.com/en-us/agent-framework/
- Python Samples: https://github.com/microsoft/agent-framework/tree/main/python/samples
- Installation: `pip install agent-framework --pre`

### D. Related Files in Codebase

| File | Purpose |
|------|---------|
| `src/scenarios/scenario4_multi_market.py` | Current implementation |
| `src/scenarios/scenario3_mcp_rest.py` | Single-market pattern to reuse |
| `src/core/models.py` | Data models (extend here) |
| `src/infrastructure/config.py` | Configuration (add workflow config) |
| `src/ui/pages/scenario4.py` | UI page (update for workflow) |
| `mcp-server-local/mcp_server_http.py` | MCP server (no changes needed) |

---

## Document Information

| Attribute | Value |
|-----------|-------|
| Created | 2026-02-04 |
| Author | AI Analysis |
| Version | 1.0 |
| Status | Draft - Pending Review |
| Related Issues | Scenario 4 timeout errors |

---

*This document provides a comprehensive analysis of implementing workflow-based architecture for Scenario 4. Proceed with implementation after review and approval.*
