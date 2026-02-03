// Azure deployment parameters for MCP Server

using './main.bicep'

param baseName = 'bingmcp'
param location = 'eastus2'
param projectEndpoint = ''  // Set via environment variable
param bingConnectionName = ''  // Set via environment variable
param modelDeploymentName = 'gpt-4o'
