targetScope = 'subscription'

metadata name = 'AI Foundry Agent with Bing Grounding'
metadata description = 'Deploys AI Foundry with Bing Search grounding for company risk analysis'

// ============================================================================
// PARAMETERS
// ============================================================================

@description('Name of the project/workload')
param workloadName string = 'companyrisk'

@description('Environment (dev, test, prod)')
param environment string = 'dev'

@description('Primary location for resources')
param location string = 'eastus2'

@description('Tags for all resources')
param tags object = {
  workload: workloadName
  environment: environment
  purpose: 'bing-grounding-poc'
  SecurityControl: 'Ignore'
}

@description('Project name for AI Foundry')
param projectName string = 'companyrisk-project'

@description('Bing connection name')
param bingConnectionName string = 'bing-grounding'

// ============================================================================
// VARIABLES
// ============================================================================

var resourceGroupName = 'rg-${workloadName}-${environment}'
var uniqueSuffix = uniqueString(subscription().subscriptionId, resourceGroupName, location)
var aiServicesName = 'ai-${workloadName}-${uniqueSuffix}'
var bingResourceName = 'bing-${workloadName}-${uniqueSuffix}'
var logAnalyticsName = 'law-${workloadName}-${uniqueSuffix}'
var storageAccountName = 'st${take(replace(workloadName, '-', ''), 10)}${take(uniqueSuffix, 8)}'
var appInsightsName = 'appi-${workloadName}-${uniqueSuffix}'

// ============================================================================
// RESOURCE GROUP
// ============================================================================

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// ============================================================================
// LOG ANALYTICS WORKSPACE
// ============================================================================

module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.15.0' = {
  scope: rg
  name: 'logAnalyticsDeployment'
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
    skuName: 'PerGB2018'
    dataRetention: 30
  }
}

// ============================================================================
// APPLICATION INSIGHTS (for Tracing)
// ============================================================================

module appInsights 'br/public:avm/res/insights/component:0.5.0' = {
  scope: rg
  name: 'appInsightsDeployment'
  params: {
    name: appInsightsName
    location: location
    tags: tags
    workspaceResourceId: logAnalytics.outputs.resourceId
    kind: 'web'
    applicationType: 'web'
  }
}

// ============================================================================
// STORAGE ACCOUNT (for AI Services)
// ============================================================================

module storageAccount 'br/public:avm/res/storage/storage-account:0.31.0' = {
  scope: rg
  name: 'storageAccountDeployment'
  params: {
    name: storageAccountName
    location: location
    tags: tags
    skuName: 'Standard_LRS'
    kind: 'StorageV2'
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Enabled'
  }
}

// ============================================================================
// BING GROUNDING RESOURCE
// ============================================================================

module bingGrounding 'modules/bing-grounding.bicep' = {
  scope: rg
  name: 'bingGroundingDeployment'
  params: {
    name: bingResourceName
    location: 'global'
    tags: tags
  }
}

// ============================================================================
// AI SERVICES ACCOUNT (Microsoft Foundry)
// ============================================================================

module aiServices 'br/public:avm/res/cognitive-services/account:0.14.1' = {
  scope: rg
  name: 'aiServicesDeployment'
  params: {
    name: aiServicesName
    kind: 'AIServices'
    location: location
    tags: tags
    sku: 'S0'
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true  // Enable project management for AI Foundry
    managedIdentities: {
      systemAssigned: true
    }
    // Deploy GPT-4o model
    deployments: [
      {
        name: 'gpt-4o'
        model: {
          format: 'OpenAI'
          name: 'gpt-4o'
          version: '2024-11-20'
        }
        sku: {
          name: 'Standard'
          capacity: 30
        }
      }
    ]
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalytics.outputs.resourceId
        logCategoriesAndGroups: [
          {
            category: 'RequestResponse'
          }
          {
            category: 'Audit'
          }
        ]
        metricCategories: [
          {
            category: 'AllMetrics'
          }
        ]
      }
    ]
  }
}

// ============================================================================
// AI FOUNDRY PROJECT AND BING CONNECTION
// ============================================================================

module aiFoundryProject 'modules/ai-foundry-project.bicep' = {
  scope: rg
  name: 'aiFoundryProjectDeployment'
  params: {
    aiServicesName: aiServicesName
    projectName: projectName
    location: location
    bingConnectionName: bingConnectionName
    bingResourceId: bingGrounding.outputs.resourceId
    bingApiKey: bingGrounding.outputs.apiKey
    appInsightsResourceId: appInsights.outputs.resourceId
    appInsightsConnectionString: appInsights.outputs.connectionString
  }
  dependsOn: [aiServices, bingGrounding, appInsights]
}

// ============================================================================
// OUTPUTS
// ============================================================================

@description('Resource group name')
output resourceGroupName string = rg.name

@description('AI Services account name')
output aiServicesName string = aiServices.outputs.name

@description('AI Services endpoint')
output aiServicesEndpoint string = aiServices.outputs.endpoint

@description('Bing Grounding resource name')
output bingResourceName string = bingGrounding.outputs.name

@description('Bing Grounding resource ID')
output bingResourceId string = bingGrounding.outputs.resourceId

@description('Model deployment name')
output modelDeploymentName string = 'gpt-4o'

@description('Storage account name')
output storageAccountName string = storageAccount.outputs.name

@description('Project name')
output projectName string = projectName

@description('Bing connection name')
output bingConnectionName string = bingConnectionName

@description('Project endpoint URL')
output projectEndpoint string = aiFoundryProject.outputs.projectEndpoint

@description('Full Bing connection ID')
output bingConnectionId string = '/subscriptions/${subscription().subscriptionId}/resourceGroups/${rg.name}/providers/Microsoft.CognitiveServices/accounts/${aiServicesName}/projects/${projectName}/connections/${bingConnectionName}'

@description('Application Insights name')
output appInsightsName string = appInsights.outputs.name

@description('Application Insights connection string')
output appInsightsConnectionString string = appInsights.outputs.connectionString
