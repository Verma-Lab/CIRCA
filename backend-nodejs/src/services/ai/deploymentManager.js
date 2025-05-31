// // backend/src/services/ai/deploymentManager.js
import geminiService from './gemini.js';
import vectorStorage from '../storage/vectors.js';
import { queueDocumentProcessing, queueTrainingJob } from '../queue/jobs.js';
import firestore from '../db/firestore.js';

// services/ai/deploymentManager.js
// services/ai/deploymentManager.js
class DeploymentManager {
    async deployAssistant(assistantId) {
      try {
        // 1. Create deployment session
        const sessionRef = await firestore.db.collection('deployment_sessions').doc();
        const sessionId = sessionRef.id;
 
        // Get assistant data
        const assistant = await firestore.db.collection('assistants').doc(assistantId).get();
        const assistantData = assistant.data();
  
        // Update assistant with current deployment session
        await firestore.db.collection('assistants').doc(assistantId).update({
          currentDeploymentSession: sessionId,
          deploymentStatus: 'deploying'
      });
        await sessionRef.set({
          assistantId,
          status: 'initializing',
          startedAt: new Date(),
          progress: 0,
          updatedAt: new Date()
        });
  
        // 2. Update assistant status
        await sessionRef.update({
            status: 'storing_vectors',
            progress: 50,
            updatedAt: new Date()
          });
          
         
        // 3. Real deployment process
        try {
          // Step 1: Initialize and analyze content
          await sessionRef.update({
            status: 'analyzing',
            progress: 25,
            updatedAt: new Date()
          });
  
                
        // Generate embeddings for assistant instructions
        console.log('Generating embeddings for instructions:', {
            instructionsLength: assistantData.instructions?.length
        });
        
        const instructionsEmbedding = await geminiService.generateEmbeddings(assistantData.instructions);
        
        console.log('Generated embeddings:', {
            embeddingType: typeof instructionsEmbedding,
            isArray: Array.isArray(instructionsEmbedding),
            length: instructionsEmbedding?.length
        });
        
        // Validate embeddings
        if (!instructionsEmbedding || !Array.isArray(instructionsEmbedding)) {
            throw new Error('Invalid embeddings generated');
        }
        
        // Store vectors with validation
        await sessionRef.update({
            status: 'storing_vectors',
            progress: 50,
            updatedAt: new Date()
        });
        
       
        
        const vectorResult = await vectorStorage.storeVectors([instructionsEmbedding], {
            assistantId,
            type: 'instructions',
            name: assistantData.name,
            content: assistantData.instructions,  // Add this line
            createdAt: new Date()
          });
        console.log('Vector storage result:', vectorResult);
        
          // Step 3: Train with Gemini
          await sessionRef.update({
            status: 'training',
            progress: 75,
            updatedAt: new Date()
          });
  
          const trainingResult = await geminiService.trainAssistant({
            id: assistantId,
            instructions: assistantData.instructions,
            name: assistantData.name
          }, []);
  
          // Step 4: Complete deployment
          await Promise.all([
            sessionRef.update({
              status: 'completed',
              progress: 100,
              completedAt: new Date(),
              updatedAt: new Date(),
              modelInfo: {
                type: 'gemini',
                version: 'flash-1.5',
                trainedAt: new Date()
              }
            }),
            firestore.db.collection('assistants').doc(assistantId).update({
              deploymentStatus: 'deployed',
              lastDeployedAt: new Date(),
              currentDeploymentSession: null,
              modelInfo: {
                type: 'gemini',
                version: 'flash-1.5',
                trainedAt: new Date()
              }
            })
          ]);
  
          return {
            sessionId,
            status: 'completed',
            progress: 100
          };
  
        } catch (error) {
          // Handle deployment failure
          await Promise.all([
            sessionRef.update({
              status: 'failed',
              error: error.message,
              updatedAt: new Date()
            }),
            firestore.db.collection('assistants').doc(assistantId).update({
              deploymentStatus: 'failed',
              error: error.message,
              currentDeploymentSession: null
            })
          ]);
          throw error;
        }
  
      } catch (error) {
        console.error('Deployment error:', error);
        throw new Error(`Failed to deploy assistant: ${error.message}`);
      }
    }
  
    async getDeploymentStatus(assistantId) {
      try {
        const assistant = await firestore.db.collection('assistants').doc(assistantId).get();
        const assistantData = assistant.data();
  
        if (!assistantData.currentDeploymentSession) {
          return {
            status: assistantData.deploymentStatus || 'not_deployed',
            progress: assistantData.deploymentStatus === 'deployed' ? 100 : 0
          };
        }
  
        const session = await firestore.db
          .collection('deployment_sessions')
          .doc(assistantData.currentDeploymentSession)
          .get();
  
        return session.data();
      } catch (error) {
        console.error('Status check error:', error);
        throw new Error('Failed to check deployment status');
      }
    }
  }

export default new DeploymentManager();
