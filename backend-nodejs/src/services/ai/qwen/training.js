// services/ai/qwen/training.js
import { Storage } from '@google-cloud/storage';
import firestore from '../../db/firestore.js';
import qwenService from './service.js';
import qwenUtils from './utils.js';

class QwenTrainingPipeline {
  constructor() {
    this.storage = new Storage();
    this.bucketName = process.env.GOOGLE_CLOUD_BUCKET;
  }

  async startTrainingPipeline(assistantId, documents) {
    try {
      // 1. Initialize training session
      const { sessionId } = await qwenService.initializeTraining(assistantId, documents);
      
      // 2. Prepare training data
      await this.prepareTrainingData(assistantId, documents);
      
      await qwenService.verifySetup();

      // 3. Start training job
      const trainingJob = await qwenService.startTraining(assistantId, sessionId);
      
      // 4. Monitor training progress
      this.monitorTrainingProgress(assistantId, sessionId, trainingJob.name); // Changed from trainingJob.id
      
      return { 
        sessionId, 
        jobId: trainingJob.name 
      };
    } catch (error) {
      console.error('Training pipeline error:', error);
      throw new Error(`Training pipeline failed: ${error.message}`);
    }
  }

async prepareTrainingData(assistantId, documents) {
    try {
      const processedPath = qwenUtils.generateTrainingPath(assistantId);
      const bucket = this.storage.bucket(this.bucketName);
      
      console.log('Preparing training data:', {
        assistantId,
        documentCount: documents.length,
        processedPath
      });
  
      // Process and upload each document
      for (const doc of documents) {
        const processedContent = await this.processDocument(doc);
        const fileName = `${processedPath}/${doc.id}.jsonl`;
        
        console.log('Processing document:', {
          docId: doc.id,
          fileName,
          contentLength: JSON.stringify(processedContent).length
        });
  
        // Ensure the content is properly formatted for JSONL
        const jsonlContent = JSON.stringify(processedContent) + '\n';
        
        // Create write stream with proper options
        await new Promise((resolve, reject) => {
          const file = bucket.file(fileName);
          const stream = file.createWriteStream({
            resumable: false,
            contentType: 'application/jsonl'
          });
          
          stream.on('error', reject);
          stream.on('finish', resolve);
          stream.end(jsonlContent);
        });
      }
  
      // Add delay before validation to ensure files are saved
      await new Promise(resolve => setTimeout(resolve, 1000));
  
      // Validate training data
      const validation = await qwenUtils.validateTrainingData(assistantId);
      console.log('Validation after preparation:', validation);
  
      if (!validation.isValid) {
        throw new Error(`Training data validation failed: ${JSON.stringify(validation)}`);
      }
  
      return processedPath;
    } catch (error) {
      console.error('Data preparation error:', error);
      throw new Error(`Failed to prepare training data: ${error.message}`);
    }
  }
  async processDocument(document) {
    return {
      text: document.content,
      metadata: {
        id: document.id,
        type: document.type
      }
    };
  }


async monitorTrainingProgress(assistantId, sessionId, jobName) {
    try {
        const checkProgress = async () => {
            try {
                const status = await qwenService.getTrainingStatus(jobName);
                
                await firestore.updateTrainingSession(sessionId, {
                    status: status.status.toLowerCase(),
                    progress: status.progress
                });

                if (status.status === 'completed') {
                    await this.handleTrainingSuccess(assistantId, sessionId, jobName);
                } else if (status.status === 'failed') {
                    await this.handleTrainingFailure(assistantId, sessionId, status.error);
                } else {
                    setTimeout(checkProgress, 30000);
                }
            } catch (err) {
                console.error('Progress monitoring error:', err);
                await qwenService.handleTrainingError(assistantId, sessionId, err);
            }
        };

        checkProgress();
    } catch (error) {
        console.error('Progress monitoring setup error:', error);
        await qwenService.handleTrainingError(assistantId, sessionId, error);
    }
}
calculateProgress(status) {
    const progressMap = {
        'JOB_STATE_QUEUED': 10,
        'JOB_STATE_PENDING': 10,
        'JOB_STATE_RUNNING': 50,
        'JOB_STATE_SUCCEEDED': 100,
        'JOB_STATE_FAILED': 0
    };
    return progressMap[status] || 0;
}

  async handleTrainingSuccess(assistantId, sessionId) {
    try {
        await Promise.all([
            firestore.updateAssistant(assistantId, {
                status: 'deployed',
                currentTrainingSession: null,
                modelConfig: {
                    inferenceUrl: qwenService.getInferenceUrl(),
                    trainedAt: new Date()
                }
            }),
            firestore.updateTrainingSession(sessionId, {
                status: 'completed',
                progress: 100
            })
        ]);
    } catch (error) {
        console.error('Success handling error:', error);
        await qwenService.handleTrainingError(assistantId, sessionId, error);
    }
}

async handleTrainingFailure(assistantId, sessionId, error) {
    await qwenService.handleTrainingError(assistantId, sessionId, error);
}
}

export default new QwenTrainingPipeline();


    