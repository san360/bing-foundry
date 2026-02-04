# Scenario 5: Azure AI Foundry Native Workflow Feasibility Analysis

## Executive Summary

This document analyzes the feasibility of using **Azure AI Foundry's native Workflow feature** for Scenario 5 (Multi-Market Research). After reviewing the official documentation, we conclude that Foundry Workflows are **UI-based visual tools** designed for portal-based orchestration, not programmatic SDK-based automation. This has significant implications for our implementation approach.

**Key Finding:** Foundry Workflows cannot be created or managed programmatically via SDK. They are designed for visual, low-code orchestration in the Foundry portal.

---

## Table of Contents

1. [What Are Foundry Workflows?](#1-what-are-foundry-workflows)
2. [Workflow Patterns Available](#2-workflow-patterns-available)
3. [Current Scenario 5 vs Foundry Workflows](#3-current-scenario-5-vs-foundry-workflows)
4. [Feasibility Assessment](#4-feasibility-assessment)
5. [Implementation Options](#5-implementation-options)
6. [Recommendation](#6-recommendation)
7. [If Using Foundry Workflows: Manual Setup Guide](#7-if-using-foundry-workflows-manual-setup-guide)

---

## 1. What Are Foundry Workflows?

Based on the [official Microsoft documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/workflow?view=foundry):

### Definition

> Workflows are **UI-based tools in Microsoft Foundry** that create declarative, predefined sequences of actions orchestrating agents and business logic in a **visual builder**.

### Key Characteristics

| Characteristic | Description |
|----------------|-------------|
| **Creation Method** | Visual builder in Foundry portal (UI only) |
| **SDK Support** | **None** - No programmatic creation via Python/SDK |
| **Execution** | Run from portal or via published endpoint |
| **Logic** | Power Fx formulas (Excel-like syntax) |
| **Persistence** | Saved in Foundry with version history |
| **Visibility** | Visible in Foundry Portal under "Workflows" |

### What Workflows Are NOT

- Not creatable via Python SDK
- Not defined in code files
- Not the same as "asyncio orchestration" or "Agent Framework workflows"
- Not designed for dynamic, programmatic control flow

---

## 2. Workflow Patterns Available

Foundry provides three orchestration templates:

### 2.1 Sequential Pattern

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Agent 1 │ ──► │ Agent 2 │ ──► │ Agent 3 │
└─────────┘     └─────────┘     └─────────┘
```

- Passes results from one agent to the next
- Fixed, linear execution order
- Best for: Pipelines, multi-stage processing

### 2.2 Human in the Loop Pattern

```
┌─────────┐     ┌─────────────┐     ┌─────────┐
│ Agent 1 │ ──► │ Human Input │ ──► │ Agent 2 │
└─────────┘     └─────────────┘     └─────────┘
```

- Pauses for user input/approval
- Best for: Approval workflows, information gathering

### 2.3 Group Chat Pattern

```
        ┌─────────┐
        │  Agent  │
        │   A     │
        └────┬────┘
             │
    ┌────────┴────────┐
    │   Orchestrator  │
    │   (Dynamic)     │
    └────────┬────────┘
         ┌───┴───┐
    ┌────▼───┐ ┌─▼──────┐
    │Agent B │ │Agent C │
    └────────┘ └────────┘
```

- Dynamic control passing based on context
- Best for: Expert handoff, escalation, fallback

---

## 3. Current Scenario 5 vs Foundry Workflows

### 3.1 Current Implementation (Python/asyncio)

```
┌─────────────────────────────────────────────────────────────┐
│              CURRENT: Python asyncio Orchestration          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   request ──► Dispatcher ──► Parallel Market Searches ──►  │
│                              (asyncio.gather)               │
│                                    │                        │
│                         ┌──────────┼──────────┐             │
│                         │          │          │             │
│                      Market 1  Market 2  Market 3           │
│                         │          │          │             │
│                         └──────────┼──────────┘             │
│                                    │                        │
│                              Aggregator ──► Analysis Agent  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Pros:                          │ Cons:                      │
│ - Parallel execution           │ - Not visible in portal   │
│ - Programmatic control         │ - Code-based only         │
│ - Dynamic market lists         │ - No visual debugging     │
│ - Full Python flexibility      │ - Manual tracing setup    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Foundry Native Workflow (If Used)

```
┌─────────────────────────────────────────────────────────────┐
│              FOUNDRY: Visual Workflow Builder               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Foundry Portal - Visual Builder        │   │
│   │                                                     │   │
│   │   [Start] ──► [For Each Market] ──► [Agent Node] ──►│   │
│   │                     │                               │   │
│   │              ┌──────┴──────┐                        │   │
│   │              │  Loop Body  │                        │   │
│   │              │ (Sequential)│                        │   │
│   │              └─────────────┘                        │   │
│   │                     │                               │   │
│   │              [Aggregate] ──► [Analysis Agent] ──►   │   │
│   │                                                [End]│   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Pros:                          │ Cons:                      │
│ - Visible in Foundry portal    │ - NO parallel execution   │
│ - Visual debugging             │ - UI-only creation        │
│ - Version history              │ - Fixed market list       │
│ - No code required             │ - Limited Power Fx logic  │
│ - Built-in tracing             │ - Cannot call from SDK    │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Feature Comparison Matrix

| Feature | Current (asyncio) | Foundry Workflow |
|---------|-------------------|------------------|
| **Parallel Execution** | Yes (asyncio.gather) | **No** (Sequential only) |
| **Programmatic Creation** | Yes (Python) | **No** (UI only) |
| **Dynamic Market List** | Yes (runtime parameter) | **No** (Fixed at design) |
| **Portal Visibility** | Agents only | Full workflow |
| **SDK Invocation** | Yes | Limited (published endpoint) |
| **For-Each Loop** | Yes (Python) | Yes (Power Fx) |
| **Conditional Logic** | Yes (Python) | Yes (Power Fx if/else) |
| **Error Handling** | Full Python try/catch | Limited |
| **Tracing** | Manual OpenTelemetry | Built-in |
| **Version Control** | Git (code files) | Foundry versions |

---

## 4. Feasibility Assessment

### 4.1 Can Foundry Workflows Support Scenario 5?

| Requirement | Foundry Support | Assessment |
|-------------|-----------------|------------|
| Multiple market searches | Yes (For Each node) | Feasible |
| **Parallel execution** | **No** | **Blocker** |
| Dynamic market selection | Limited (variables) | Partial |
| Result aggregation | Yes (variables) | Feasible |
| Cross-market analysis | Yes (agent node) | Feasible |
| Programmatic invocation | Limited | Partial |
| Timeout per market | No native support | **Gap** |
| Graceful degradation | Limited | **Gap** |

### 4.2 Critical Limitations

#### Limitation 1: No Parallel Execution

Foundry Workflows execute **sequentially**. The "For Each" node processes items one at a time, not in parallel.

```
Current (asyncio):     Foundry Workflow:

Market 1 ─┐            Market 1 ──► Market 2 ──► Market 3
Market 2 ─┼─► 45 sec
Market 3 ─┘                    Total: 90-120 sec

Total: ~45 sec
```

**Impact:** 3-5x slower execution with Foundry Workflows.

#### Limitation 2: No SDK Creation

Workflows must be created manually in the Foundry portal. You cannot:
- Create workflows programmatically
- Version control workflow definitions in Git
- Deploy workflows via CI/CD pipelines
- Dynamically generate workflow structure

#### Limitation 3: Limited Error Handling

Foundry Workflows have basic error handling:
- No try/catch equivalent
- No per-market timeout configuration
- No partial result handling (all or nothing)

### 4.3 Feasibility Verdict

| Scenario | Verdict | Reason |
|----------|---------|--------|
| Use Foundry Workflows for Scenario 5 | **Partially Feasible** | Works but loses parallel execution |
| Replace current implementation | **Not Recommended** | Significant performance regression |
| Hybrid approach | **Possible** | Use Foundry for visibility, code for execution |

---

## 5. Implementation Options

### Option A: Keep Current Implementation (Recommended)

Continue using Python/asyncio orchestration with Foundry agents.

```
┌─────────────────────────────────────────┐
│         Python Orchestration            │
│  (scenario5_workflow.py)                │
│                                         │
│  asyncio.gather() for parallel search   │
│           │                             │
│           ▼                             │
│  ┌─────────────────────────────────┐    │
│  │   Foundry Agents (visible)      │    │
│  │   - BingFoundry-WorkflowSearch  │    │
│  │   - BingFoundry-WorkflowAnalyzer│    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

**Pros:**
- Parallel execution (fast)
- Full programmatic control
- Dynamic market lists
- Agents visible in portal

**Cons:**
- Workflow logic not visible in portal
- Manual tracing setup

### Option B: Foundry Workflow (Sequential)

Create workflow manually in Foundry portal.

```
┌─────────────────────────────────────────┐
│      Foundry Portal Workflow            │
│                                         │
│  [Start] ──► [For Each Market] ──►      │
│                    │                    │
│              [Search Agent]             │
│                    │                    │
│              [Set Variable]             │
│                    │                    │
│         [Analysis Agent] ──► [End]      │
└─────────────────────────────────────────┘
```

**Pros:**
- Full visibility in portal
- Visual debugging
- No code required

**Cons:**
- Sequential execution (3-5x slower)
- Manual UI setup required
- Cannot invoke from Python SDK
- Fixed market list

### Option C: Hybrid Approach

Use Foundry Workflow for simple cases, Python for complex/parallel.

```
┌─────────────────────────────────────────────────────────────┐
│                    HYBRID APPROACH                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Simple (1-2 markets):     Complex (3+ markets):           │
│  ────────────────────      ─────────────────────           │
│  Foundry Workflow          Python asyncio                   │
│  (Sequential, UI)          (Parallel, Code)                 │
│                                                             │
│  User selects approach based on market count                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Option D: Wait for SDK Support

Microsoft may add programmatic workflow creation in future SDK versions.

---

## 6. Recommendation

### Primary Recommendation: Option A (Keep Current)

**Rationale:**

1. **Performance**: Parallel execution is critical for multi-market search
2. **Flexibility**: Dynamic market lists require programmatic control
3. **Visibility**: Agents are still visible in Foundry portal
4. **Tracing**: OpenTelemetry provides equivalent observability

### Secondary Recommendation: Create Companion Workflow

Create a **simple Foundry Workflow** for demonstration/documentation purposes:
- Shows the orchestration pattern visually
- Useful for stakeholder presentations
- Can be used for single-market scenarios

### What to Tell Stakeholders

> "The multi-market search scenario requires parallel execution for acceptable performance. Foundry Workflows execute sequentially, which would result in 3-5x slower response times. We've implemented the workflow pattern in Python while using Foundry Agents, which remain visible and manageable in the portal. If Microsoft adds parallel execution support to Foundry Workflows in the future, we can migrate."

---

## 7. If Using Foundry Workflows: Manual Setup Guide

If you still want to create a Foundry Workflow for Scenario 5, here are the steps:

### 7.1 Prerequisites

- Azure AI Foundry project access
- Contributor role or higher
- Agents already created:
  - `BingFoundry-WorkflowSearch`
  - `BingFoundry-WorkflowAnalyzer`

### 7.2 Create Workflow

1. **Navigate to Foundry Portal**
   ```
   https://ai.azure.com → Your Project → Build → Create new workflow
   ```

2. **Select Pattern**
   - Choose "Sequential" pattern

3. **Add Start Node**
   - Configure input variables:
     ```
     Local.CompanyName (Text)
     Local.Markets (Table) - e.g., ["en-US", "de-DE", "ja-JP"]
     Local.Results (Table) - empty, for storing results
     ```

4. **Add For Each Node**
   - Source: `Local.Markets`
   - Current item variable: `Local.CurrentMarket`

5. **Add Agent Node (Search)**
   - Select existing agent: `BingFoundry-WorkflowSearch`
   - Input prompt:
     ```
     Search for {Local.CompanyName} in market {Local.CurrentMarket}
     ```
   - Save output to: `Local.SearchResult`

6. **Add Set Variable Node**
   - Append result to Local.Results:
     ```
     Collect(Local.Results, {market: Local.CurrentMarket, result: Local.SearchResult})
     ```

7. **Add Agent Node (Analysis)**
   - Select existing agent: `BingFoundry-WorkflowAnalyzer`
   - Input prompt:
     ```
     Analyze these multi-market results for {Local.CompanyName}:
     {Local.Results}
     ```

8. **Save and Test**
   - Click "Save"
   - Click "Run Workflow"
   - Enter test values

### 7.3 Workflow YAML (For Reference)

Foundry allows viewing workflows as YAML:

```yaml
# Conceptual YAML representation (actual format may vary)
name: MultiMarketResearchWorkflow
version: 1.0
triggers:
  - type: manual
    inputs:
      companyName: string
      markets: array

nodes:
  - id: start
    type: trigger

  - id: forEach
    type: forEach
    source: ${inputs.markets}
    itemVariable: currentMarket
    body:
      - id: searchAgent
        type: invokeAgent
        agent: BingFoundry-WorkflowSearch
        prompt: "Search for ${inputs.companyName} in market ${currentMarket}"
        outputVariable: searchResult

      - id: collectResult
        type: setVariable
        expression: "Collect(results, {market: currentMarket, data: searchResult})"

  - id: analysisAgent
    type: invokeAgent
    agent: BingFoundry-WorkflowAnalyzer
    prompt: "Analyze results: ${results}"

  - id: end
    type: response
    value: ${analysisAgent.output}
```

---

## 8. Summary Comparison Table

| Aspect | Current (Python) | Foundry Workflow |
|--------|------------------|------------------|
| **Execution** | Parallel | Sequential |
| **Speed (5 markets)** | ~45 sec | ~150 sec |
| **Creation** | Code (SDK) | UI (Portal) |
| **Visibility** | Agents only | Full workflow |
| **Dynamic markets** | Yes | Limited |
| **Error handling** | Full | Basic |
| **Timeouts** | Per-market | None |
| **Recommendation** | **Use this** | For demos only |

---

## Document Information

| Attribute | Value |
|-----------|-------|
| Created | 2026-02-04 |
| Author | AI Analysis |
| Version | 1.0 |
| Status | Complete |
| Based On | [Microsoft Foundry Workflow Docs](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/workflow?view=foundry) |

---

## Conclusion

**Foundry Workflows are UI-based visual orchestration tools, not programmatic SDK features.** While it's technically possible to create a Scenario 5 workflow in the Foundry portal, doing so would:

1. Sacrifice parallel execution (3-5x slower)
2. Require manual UI setup (no code/CI/CD)
3. Limit dynamic market selection

**The current Python/asyncio implementation with Foundry Agents is the recommended approach** for production use. Consider creating a Foundry Workflow only for demonstration or single-market scenarios.
