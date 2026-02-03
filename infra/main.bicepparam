using './main.bicep'

param workloadName = 'companyrisk'
param environment = 'dev'
param location = 'eastus2'
param tags = {
  workload: 'companyrisk'
  environment: 'dev'
  purpose: 'bing-grounding-poc'
  createdBy: 'azd'
  SecurityControl: 'Ignore'
}
param projectName = 'companyrisk-project'
param bingConnectionName = 'bing-grounding'
