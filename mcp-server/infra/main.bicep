// ============================================================================
// Azure Functions MCP Server Infrastructure
// Deploys Azure Functions with MCP extension for Bing Grounding
// ============================================================================

targetScope = 'resourceGroup'

@description('The base name for all resources')
param baseName string = 'bingmcp'

@description('Location for all resources')
param location string = resourceGroup().location

@description('AI Foundry Project Endpoint')
@secure()
param projectEndpoint string

@description('Bing Connection Name in AI Foundry')
param bingConnectionName string

@description('Model deployment name')
param modelDeploymentName string = 'gpt-4o'

// ============================================================================
// Variables
// ============================================================================

var functionAppName = '${baseName}-func-${uniqueString(resourceGroup().id)}'
var storageAccountName = '${baseName}st${uniqueString(resourceGroup().id)}'
var appServicePlanName = '${baseName}-asp'
var appInsightsName = '${baseName}-appins'
var logAnalyticsName = '${baseName}-logs'

// ============================================================================
// Log Analytics Workspace
// ============================================================================

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ============================================================================
// Application Insights
// ============================================================================

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ============================================================================
// Storage Account (for Azure Functions)
// ============================================================================

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

// ============================================================================
// App Service Plan (Flex Consumption)
// ============================================================================

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  sku: {
    tier: 'FlexConsumption'
    name: 'FC1'
  }
  kind: 'functionapp'
  properties: {
    reserved: true
  }
}

// ============================================================================
// Function App with MCP Extension
// ============================================================================

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'PYTHON|3.11'
      cors: {
        allowedOrigins: [
          'https://portal.azure.com'
          'https://ai.azure.com'
        ]
      }
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'PROJECT_ENDPOINT'
          value: projectEndpoint
        }
        {
          name: 'BING_CONNECTION_NAME'
          value: bingConnectionName
        }
        {
          name: 'MODEL_DEPLOYMENT_NAME'
          value: modelDeploymentName
        }
      ]
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================

output functionAppName string = functionApp.name
output functionAppHostname string = functionApp.properties.defaultHostName
output mcpEndpoint string = 'https://${functionApp.properties.defaultHostName}/runtime/webhooks/mcp'
output mcpSseEndpoint string = 'https://${functionApp.properties.defaultHostName}/runtime/webhooks/mcp/sse'
output principalId string = functionApp.identity.principalId
