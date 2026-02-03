@description('Name of the Bing Grounding resource')
param name string

@description('Location for the resource (should be global for Bing)')
param location string = 'global'

@description('Tags for the resource')
param tags object = {}

// Bing Grounding Search Resource
// Note: You must first register the Microsoft.Bing provider in your subscription
// az provider register --namespace 'Microsoft.Bing'

resource bingGrounding 'Microsoft.Bing/accounts@2020-06-10' = {
  name: name
  location: location
  tags: tags
  kind: 'Bing.Grounding.Search'
  sku: {
    name: 'G1'
  }
}

@description('Resource ID of the Bing Grounding resource')
output resourceId string = bingGrounding.id

@description('Name of the Bing Grounding resource')
output name string = bingGrounding.name
