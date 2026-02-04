# Dynamic Market Configuration for Bing Grounding (Azure AI Foundry)

## Summary
The `market` parameter is part of the **Bing grounding tool configuration**, not a per‑request runtime override. To change `market` dynamically, you **create a new tool configuration** (and typically a new agent version) with the desired `market`, then execute the request and optionally delete the agent version to keep agents ephemeral.

## Evidence from Microsoft docs

### 1) Bing grounding tool optional parameters
Microsoft documents `market` as an **optional parameter on the Bing grounding tool configuration**. This indicates the value is applied when the tool is configured.

- https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/bing-tools?view=foundry#optional-parameters

### 2) Python SDK model fields
The Python SDK model exposes `market` as a field on `BingGroundingSearchConfiguration`, which is used to build the tool configuration. This further indicates it is configured at tool creation time.

- https://learn.microsoft.com/en-us/python/api/azure-ai-projects/azure.ai.projects.models.binggroundingsearchconfiguration?view=azure-python-preview

## Practical pattern (dynamic market)
1. Read `market` from user input.
2. Build a `BingGroundingSearchConfiguration(market=...)`.
3. Create a Bing grounding tool with that configuration.
4. Create an agent (or agent version) with that tool.
5. Execute the request.
6. Optionally delete the agent version (ephemeral behavior).

This matches the agent creation flow shown in Microsoft docs and samples.

## Related sample references
- Foundry samples (Bicep): https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/45-basic-agent-bing
- Azure SDK JS samples (agent tools): https://github.com/Azure/azure-sdk-for-js/tree/main/sdk/ai/ai-projects/samples/v2-beta/javascript/agents/tools
