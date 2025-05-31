// services/ai/qwen/endpoints.js
import { VertexAI } from '@google-cloud/vertexai';
import firestore from '../../db/firestore.js';
import qwenUtils from './utils.js';

class QwenEndpointManager {
  constructor() {
    this.vertexai = new VertexAI({
      project: process.env.GOOGLE_CLOUD_PROJECT_ID,
      location: process.env.GOOGLE_CLOUD_REGION
    });
  }

  async createEndpoint(assistantId) {
    try {
      const endpointDisplayName = `qwen-assistant-${assistantId}`;
      
      // Create endpoint in Vertex AI
      const endpoint = await this.vertexai.endpoints.create({
        displayName: endpointDisplayName,
        description: `Endpoint for Qwen assistant ${assistantId}`,
        location: process.env.VERTEX_AI_LOCATION
      });

      // Get active model weight
      const activeWeight = await firestore.getActiveModelWeight(assistantId);
      if (!activeWeight) {
        throw new Error('No active model weights found');
      }

      // Create endpoint record using helper function
      await firestore.createModelEndpoint({
        assistantId,
        modelType: 'qwen',
        endpointId: endpoint.name,
        status: 'creating',
        modelPath: activeWeight.path,
        version: activeWeight.version
      });

      return endpoint;
    } catch (error) {
      console.error('Endpoint creation error:', error);
      throw new Error(`Failed to create endpoint: ${error.message}`);
    }
  }

  async deployModel(endpointId, modelPath) {
    try {
      const endpoint = await this.vertexai.endpoints.get(endpointId);

      // Validate model weights before deployment
      const weightsExist = await qwenUtils.validateModelWeights(modelPath);
      if (!weightsExist) {
        throw new Error('Model weights not found');
      }

      const deployedModel = await endpoint.deploy({
        modelUri: modelPath,
        machineType: 'n1-standard-4',
        minReplicaCount: 1,
        maxReplicaCount: 1,
        acceleratorType: 'NVIDIA_TESLA_T4',
        acceleratorCount: 1
      });

      // Update endpoint status using helper function
      await firestore.updateModelEndpoint(endpointId, {
        status: 'deployed',
        deployedAt: new Date(),
        modelPath
      });

      return deployedModel;
    } catch (error) {
      console.error('Model deployment error:', error);
      // Update endpoint status to failed
      await firestore.updateModelEndpoint(endpointId, {
        status: 'failed',
        error: error.message
      });
      throw new Error(`Failed to deploy model: ${error.message}`);
    }
  }

  async getEndpoint(endpointId) {
    try {
      return await this.vertexai.endpoints.get(endpointId);
    } catch (error) {
      console.error('Get endpoint error:', error);
      throw new Error(`Failed to get endpoint: ${error.message}`);
    }
  }

  async deleteEndpoint(endpointId) {
    try {
      // First, get endpoint data
      const endpointData = await firestore.getModelEndpoint(endpointId);
      if (!endpointData) {
        throw new Error('Endpoint not found');
      }

      // Delete from Vertex AI
      await this.vertexai.endpoints.delete(endpointId);
      
      // Update endpoint status to deleted
      await firestore.updateModelEndpoint(endpointId, {
        status: 'deleted',
        deletedAt: new Date()
      });

      // Update assistant if this was its active endpoint
      if (endpointData.assistantId) {
        const assistant = await firestore.getAssistant(endpointData.assistantId);
        if (assistant?.modelConfig?.endpointId === endpointId) {
          await firestore.updateAssistant(endpointData.assistantId, {
            modelConfig: {
              ...assistant.modelConfig,
              endpointId: null
            }
          });
        }
      }
    } catch (error) {
      console.error('Delete endpoint error:', error);
      throw new Error(`Failed to delete endpoint: ${error.message}`);
    }
  }

  async listEndpoints(assistantId) {
    try {
      // Get all endpoints for this assistant using helper function
      const endpoints = await firestore.getModelEndpoints(assistantId);
      
      // Enrich with Vertex AI data
      const enrichedEndpoints = await Promise.all(
        endpoints.map(async (endpoint) => {
          try {
            const vertexEndpoint = await this.vertexai.endpoints.get(endpoint.endpointId);
            return {
              ...endpoint,
              vertexStatus: vertexEndpoint.state,
              deployedModels: vertexEndpoint.deployedModels
            };
          } catch (error) {
            console.warn(`Failed to get Vertex AI data for endpoint ${endpoint.endpointId}:`, error);
            return endpoint;
          }
        })
      );

      return enrichedEndpoints;
    } catch (error) {
      console.error('List endpoints error:', error);
      throw new Error(`Failed to list endpoints: ${error.message}`);
    }
  }

  async predict(endpointId, input) {
    try {
      // Get endpoint data
      const endpointData = await firestore.getModelEndpoint(endpointId);
      if (!endpointData || endpointData.status !== 'deployed') {
        throw new Error('Endpoint not ready for predictions');
      }

      // Get Vertex AI endpoint
      const endpoint = await this.getEndpoint(endpointId);
      
      // Make prediction
      const prediction = await endpoint.predict({
        instances: [{ input }]
      });

      // Log prediction attempt (optional)
      await firestore.createPredictionLog({
        endpointId,
        assistantId: endpointData.assistantId,
        status: 'success',
        timestamp: new Date()
      });

      return prediction;
    } catch (error) {
      console.error('Prediction error:', error);
      // Log failed prediction attempt (optional)
      if (endpointId) {
        await firestore.createPredictionLog({
          endpointId,
          status: 'failed',
          error: error.message,
          timestamp: new Date()
        });
      }
      throw new Error(`Failed to get prediction: ${error.message}`);
    }
  }

  // Additional helper methods
  async isEndpointHealthy(endpointId) {
    try {
      const endpoint = await this.getEndpoint(endpointId);
      return endpoint.state === 'DEPLOYED' && endpoint.deployedModels?.length > 0;
    } catch (error) {
      return false;
    }
  }
}

export default new QwenEndpointManager();