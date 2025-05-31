// services/ai/qwen/service.js
import { VertexAI } from '@google-cloud/vertexai';
import firestore from '../../db/firestore.js';
import cloudStorage from '../../storage/cloudStorage.js';
import { JobServiceClient, EndpointServiceClient } from '@google-cloud/aiplatform';

class QwenService {
    // constructor() {
    //     // For endpoints, predictions, etc.
    //     this.vertexai = new VertexAI({
    //         project: process.env.GOOGLE_CLOUD_PROJECT_ID,
    //         location: process.env.GOOGLE_CLOUD_REGION || 'us-east1'  // Set default region
    //     });
    
        
    //     // For creating custom jobs
    //     this.jobServiceClient = new JobServiceClient();
    
    //     this.bucketName = process.env.GOOGLE_CLOUD_BUCKET;
    //     // this.baseModelPath = `us-east1-docker.pkg.dev/${process.env.GOOGLE_CLOUD_PROJECT_ID}/slmmodelrepo/qwen-base:latest`;
    //     this.baseModelPath = `us-east1-docker.pkg.dev/${process.env.GOOGLE_CLOUD_PROJECT_ID}/slmmodelrepo/qwen-base@sha256:4febf8d91ca58ab414dd10fe276e058e01a0b697419f794714faf6799c554350`;
    //   }
    constructor() {
        const region = process.env.GOOGLE_CLOUD_REGION || 'us-east1';
        const apiEndpoint = `${region}-aiplatform.googleapis.com`;
    
        this.vertexai = new VertexAI({
            project: process.env.GOOGLE_CLOUD_PROJECT_ID,
            location: region
        });
    
        // For creating custom jobs
        this.jobServiceClient = new JobServiceClient({
            apiEndpoint,
            projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
            keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS // Add this
        });
    
         // Client for managing endpoints
         this.endpointServiceClient = new EndpointServiceClient({
            apiEndpoint,
            projectId: process.env.GOOGLE_CLOUD_PROJECT_ID
        });
        // Debug logging
        console.log('Initialized VertexAI with config:', {
            region,
            projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
            apiEndpoint,
            bucketName: this.bucketName
        });
    
        this.bucketName = process.env.GOOGLE_CLOUD_BUCKET;
        // this.baseModelPath = `us-east1-docker.pkg.dev/${process.env.GOOGLE_CLOUD_PROJECT_ID}/slmmodelrepo/qwen-base@sha256:4febf8d91ca58ab414dd10fe276e058e01a0b697419f794714faf6799c554350`;
        this.baseModelPath = `us-east1-docker.pkg.dev/op8imize/slmmodelrepo/qwen-base:latest`;
         // URL for the slm-serving container
         this.inferenceUrl = process.env.SLM_SERVING_URL || "https://slm-serving-container/predict";


    }
    getInferenceUrl() {
        return this.inferenceUrl;
    }


      async verifySetup() {
        try {
            console.log('Verifying Vertex AI setup...');
            
            // Check project and location
            const parent = `projects/${process.env.GOOGLE_CLOUD_PROJECT_ID}/locations/${process.env.GOOGLE_CLOUD_REGION}`;
            console.log('Checking location:', parent);
            
            // Verify container image
            const imagePath = this.baseModelPath;
            console.log('Verifying container image:', imagePath);
            
            // Test location access
            // const [locations] = await this.jobServiceClient.listLocations({
            //     name: `projects/${process.env.GOOGLE_CLOUD_PROJECT_ID}`
            // });
            
            // console.log('Available locations:', locations.map(l => l.locationId));
            
            return true;
        } catch (error) {
            console.error('Setup verification failed:', error);
            throw error;
        }
    }
      async initializeTraining(assistantId, documents) {
        try {
          // Create training session using helper function
          const sessionData = {
            assistantId,
            modelType: 'qwen',
            modelConfig: {}
          };
          
          const session = await firestore.createTrainingSession(sessionData);
    
          // Update assistant status
          await firestore.updateAssistant(assistantId, {
            currentTrainingSession: session.id,
            status: 'training'
          });
    
          return { sessionId: session.id };
        } catch (error) {
          console.error('Training initialization error:', error);
          throw new Error(`Failed to initialize training: ${error.message}`);
        }
      }

async startTraining(assistantId, sessionId) { 
    try {
        const trainingJobName = `train-assistant-${assistantId}`;
        const outputDir = `gs://${this.bucketName}/model-weights/fine-tuned/${assistantId}`;
        const parent = `projects/${process.env.GOOGLE_CLOUD_PROJECT_ID}/locations/${process.env.GOOGLE_CLOUD_REGION}`;
        const baseModelDir = `gs://${this.bucketName}/model-weights/base`;

        console.log('Starting training with configuration:', {
            parent,
            trainingJobName,
            baseModelPath: this.baseModelPath
        });

        const [trainingJob] = await this.jobServiceClient.createCustomJob({
            parent,
            customJob: {
                displayName: trainingJobName,
                jobSpec: {
                    workerPoolSpecs: [{
                        machineSpec: {
                            machineType: 'n1-standard-8',
                            // acceleratorType: 'NVIDIA_TESLA_T4',
                            // acceleratorCount: 1
                        },
                        replicaCount: 1,
                        containerSpec: {
                            imageUri: this.baseModelPath,
                            // command: [
                            //     "python3",
                            //     "-m",
                            //     "trainer.task"
                            // ],
                            args: [
                                '--training_data_path',
                                `gs://${this.bucketName}/training-artifacts/processed/${assistantId}`,
                                '--output_dir',
                                outputDir,
                                '--base_model_dir',
                                baseModelDir,
                                '--model_name',
                                'Qwen/Qwen2.5-0.5B',
                                '--tokenizer_name',
                                'Qwen/Qwen2.5-0.5B',
                                '--target_modules',
                                'q_proj,v_proj',
                                '--assistant_id',    // Required argument
                                assistantId
                            ],
                            env: [{
                                name: 'GOOGLE_CLOUD_PROJECT',
                                value: process.env.GOOGLE_CLOUD_PROJECT_ID
                            }]
                        }
                    }],
                    baseOutputDirectory: {
                        outputUriPrefix: outputDir
                    }
                }
            }
        });

        console.log('Training job created:', trainingJob);

        await firestore.updateTrainingSession(sessionId, {
            status: 'training',
            jobId: trainingJob.name,
            jobName: trainingJobName,
            progress: 10
        });

        return trainingJob;
    } catch (error) {
        console.error('Training start error details:', {
            message: error.message,
            code: error.code,
            details: error.details,
            stack: error.stack
        });

        if (error.code === 12) {
            console.log('Checking Vertex AI API status and permissions...');
            try {
                const [location] = await this.jobServiceClient.getLocation({
                    name: `projects/${process.env.GOOGLE_CLOUD_PROJECT_ID}/locations/${process.env.GOOGLE_CLOUD_REGION}`
                });
                console.log('Location check successful:', location);
            } catch (locationError) {
                console.error('Location check failed:', locationError);
            }
        }

        await this.handleTrainingError(assistantId, sessionId, error);
        throw error;
    }
}
async predict(assistantId, userInput) {
    try {
        const inferenceEndpoint = `${this.inferenceUrl}/predict`; // Add /predict here
        console.log('Making prediction request to:', inferenceEndpoint);
        
        const response = await fetch(inferenceEndpoint, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                assistantId,
                input: userInput
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Prediction API error:', {
                status: response.status,
                statusText: response.statusText,
                error: errorText
            });
            throw new Error(`Inference error: ${errorText}`);
        }

        const result = await response.json();
        console.log('Prediction result:', result);
        return result;
    } catch (error) {
        console.error('Prediction error details:', {
            message: error.message,
            stack: error.stack
        });
        throw new Error(`Failed to get prediction: ${error.message}`);
    }
}


async handleTrainingError(assistantId, sessionId, error) {
    await Promise.all([
        firestore.updateTrainingSession(sessionId, {
            status: 'failed',
            error: error.message,
            endedAt: new Date()
        }),
        firestore.updateAssistant(assistantId, {
            status: 'failed',
            currentTrainingSession: null,
            error: error.message
        })
    ]);
}

async getTrainingStatus(jobName) {
    try {
        const [job] = await this.jobServiceClient.getCustomJob({ name: jobName });
        
        const isCompleted = job.state === 'JOB_STATE_SUCCEEDED' || 
                         (job.state === 'JOB_STATE_RUNNING' && 
                          this.hasCompletionIndicators(job));

        return {
            status: isCompleted ? 'completed' : job.state.toLowerCase(),
            progress: this.calculateProgress(job.state, job),
            error: job.error
        };
    } catch (error) {
        console.error('Error getting training status:', error);
        throw error;
    }
}
hasCompletionIndicators(job) {
    const outputPath = job.jobSpec?.baseOutputDirectory?.outputUriPrefix;
    return !!outputPath;
}

calculateProgress(state, job) {
    const progressMap = {
        JOB_STATE_QUEUED: 5,
        JOB_STATE_PENDING: 10,
        JOB_STATE_RUNNING: 50,
        JOB_STATE_SUCCEEDED: 100,
        JOB_STATE_FAILED: 0
    };

    if (state === 'JOB_STATE_RUNNING' && this.hasCompletionIndicators(job)) {
        return 100;
    }

    return progressMap[state] || 0;
}
}

export default new QwenService();











