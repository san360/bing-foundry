@description('AI Services account name')
param aiServicesName string

@description('Project name')
param projectName string

@description('Location for the project')
param location string

@description('Bing connection name')
param bingConnectionName string

@description('Bing resource ID')
param bingResourceId string

@description('Bing API key')
@secure()
param bingApiKey string

@description('Application Insights resource ID')
param appInsightsResourceId string = ''

@description('Application Insights connection string')
@secure()
param appInsightsConnectionString string = ''

// Reference existing AI Services account
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
}

// Create AI Foundry Project
resource aiFoundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServices
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Company Risk Analysis Project'
  }
}

// Create Bing Grounding Connection
resource bingConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: aiServices
  name: bingConnectionName
  properties: {
    category: 'ApiKey'
    target: 'https://api.bing.microsoft.com/'
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: bingApiKey
    }
    metadata: {
      ApiType: 'Azure'
      Type: 'bing_grounding'
      ResourceId: bingResourceId
    }
  }
  dependsOn: [aiFoundryProject]
}

// Create Application Insights Connection (for Tracing)
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = if (!empty(appInsightsConnectionString)) {
  parent: aiServices
  name: 'appinsights-tracing'
  properties: {
    category: 'ApiKey'
    target: appInsightsResourceId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: appInsightsConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      Type: 'application_insights'
      ResourceId: appInsightsResourceId
    }
  }
  dependsOn: [aiFoundryProject]
}

@description('Project name')
output projectName string = aiFoundryProject.name

@description('Connection name')
output connectionName string = bingConnection.name

@description('Project endpoint')
output projectEndpoint string = 'https://${aiServicesName}.services.ai.azure.com/api/projects/${projectName}'
