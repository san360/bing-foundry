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
}

// ============================================================================
// VARIABLES
// ============================================================================

var resourceGroupName = 'rg-${workloadName}-${environment}'
var uniqueSuffix = uniqueString(subscription().subscriptionId, resourceGroupName, location)
var aiServicesName = 'ai-${workloadName}-${uniqueSuffix}'
var bingResourceName = 'bing-${workloadName}-${uniqueSuffix}'
var logAnalyticsName = 'law-${workloadName}-${uniqueSuffix}'
var storageAccountName = 'st${take(replace(workloadName, '-', ''), 10)}${take(uniqueSuffix, 8)}'

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

@description('Bing connection ID format')
output bingConnectionIdFormat string = '/subscriptions/${subscription().subscriptionId}/resourceGroups/${rg.name}/providers/Microsoft.CognitiveServices/accounts/${aiServicesName}/projects/<PROJECT_NAME>/connections/<CONNECTION_NAME>'
