import express from 'express';
import deploymentManager from '../services/ai/deploymentManager.js';
import { verifyToken } from '../middleware/auth.js';
import firestore from '../services/db/firestore.js';
const router = express.Router();

// Start deployment
router.post('/assistants/:assistantId/deploy', async (req, res) => {
    try {
        const { assistantId } = req.params;
        console.log('Starting deployment for:', assistantId);

        // Check if assistant exists and get its data
        const assistant = await firestore.db.collection('assistants').doc(assistantId).get();
        if (!assistant.exists) {
            return res.status(404).json({ error: 'Assistant not found' });
        }

        const assistantData = assistant.data();
        console.log('Current assistant data:', {
            deploymentStatus: assistantData.deploymentStatus,
            currentSession: assistantData.currentDeploymentSession,
            indexingStatus: assistantData.indexingStatus
        });

        // Check indexing status
        const indexingStatus = assistantData.indexingStatus?.documents;
        if (indexingStatus === 'in_progress') {
            return res.status(202).json({
                message: 'Document indexing in progress, please try again later',
                status: 'indexing',
                assistantId,
                timestamp: new Date().toISOString()
            });
        } else if (indexingStatus === 'failed') {
            return res.status(500).json({
                error: 'Document indexing failed, cannot deploy',
                details: assistantData.indexingStatus.error,
                timestamp: new Date().toISOString()
            });
        } else if (indexingStatus !== 'completed' && indexingStatus !== 'not_needed') {
            return res.status(400).json({
                error: 'Indexing not initiated or in unknown state',
                timestamp: new Date().toISOString()
            });
        }

        // Check if there's already a deployment in progress
        if (assistantData.deploymentStatus === 'in_progress') {
            return res.status(409).json({
                error: 'Deployment already in progress',
                sessionId: assistantData.currentDeploymentSession,
                timestamp: new Date().toISOString()
            });
        }

        // Start deployment
        const result = await deploymentManager.deployAssistant(assistantId);
        console.log('Deployment initiated:', result);

        res.json({
            sessionId: result.sessionId,
            status: 'initiated',
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        console.error('Deployment error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Get deployment status
router.get('/assistants/:assistantId/deployment-status', async (req, res) => {
    try {
        const { assistantId } = req.params;
        console.log('\nChecking deployment status for:', assistantId);
        
        // Get assistant data
        const assistantDoc = await firestore.db.collection('assistants').doc(assistantId).get();
        if (!assistantDoc.exists) {
            console.log('Assistant not found');
            return res.status(404).json({ error: 'Assistant not found' });
        }
        
        const assistantData = assistantDoc.data();
        console.log('Assistant data:', {
            id: assistantId,
            deploymentStatus: assistantData.deploymentStatus,
            currentSession: assistantData.currentDeploymentSession
        });

        // If no active session, return current status
        if (!assistantData.currentDeploymentSession) {
            const response = {
                status: assistantData.deploymentStatus || 'not_deployed',
                progress: assistantData.deploymentStatus === 'deployed' ? 100 : 0,
                timestamp: new Date().toISOString()
            };
            console.log('Returning status (no session):', response);
            return res.json(response);
        }

        // Get session data
        const sessionDoc = await firestore.db
            .collection('deployment_sessions')
            .doc(assistantData.currentDeploymentSession)
            .get();

        if (!sessionDoc.exists) {
            console.log('Session not found, cleaning up state');
            await firestore.db.collection('assistants').doc(assistantId).update({
                currentDeploymentSession: null,
                deploymentStatus: 'failed'
            });
            
            const response = {
                status: 'failed',
                error: 'Deployment session not found',
                progress: 0,
                timestamp: new Date().toISOString()
            };
            console.log('Returning error status:', response);
            return res.json(response);
        }

        const sessionData = sessionDoc.data();
        console.log('Session data:', sessionData);

        // Check if deployment is complete or failed
        if (sessionData.status === 'completed') {
            console.log('Deployment completed, updating assistant');
            await firestore.db.collection('assistants').doc(assistantId).update({
                deploymentStatus: 'deployed',
                currentDeploymentSession: null,
                lastDeployedAt: new Date()
            });
        }

        // Build full response
        const response = {
            status: sessionData.status,
            progress: sessionData.progress || 0,
            timestamp: new Date().toISOString(),
            error: sessionData.error,
            modelInfo: sessionData.modelInfo
        };

        console.log('Returning status:', response);
        res.json(response);
        
    } catch (error) {
        console.error('Status check error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});
// router.get('/assistants/:assistantId/deployment-status', async (req, res) => {
//     try {
//         const { assistantId } = req.params;
//         console.log('\nChecking deployment status for:', assistantId);
        
//         // Get assistant data
//         const assistantDoc = await firestore.db.collection('assistants').doc(assistantId).get();
//         if (!assistantDoc.exists) {
//             console.log('Assistant not found');
//             return res.status(404).json({ error: 'Assistant not found' });
//         }
        
//         const assistantData = assistantDoc.data();
//         console.log('Assistant data:', {
//             id: assistantId,
//             deploymentStatus: assistantData.deploymentStatus,
//             currentSession: assistantData.currentDeploymentSession
//         });

//         // If no active session, return current status
//         if (!assistantData.currentDeploymentSession) {
//             const response = {
//                 status: assistantData.deploymentStatus || 'not_deployed',
//                 progress: assistantData.deploymentStatus === 'deployed' ? 100 : 0,
//                 timestamp: new Date().toISOString()
//             };
//             console.log('Returning status (no session):', response);
//             return res.json(response);
//         }

//         // Get session data
//         const sessionDoc = await firestore.db
//             .collection('deployment_sessions')
//             .doc(assistantData.currentDeploymentSession)
//             .get();

//         if (!sessionDoc.exists) {
//             console.log('Session not found, cleaning up state');
//             await firestore.db.collection('assistants').doc(assistantId).update({
//                 currentDeploymentSession: null,
//                 deploymentStatus: 'failed'
//             });
            
//             const response = {
//                 status: 'failed',
//                 error: 'Deployment session not found',
//                 progress: 0,
//                 timestamp: new Date().toISOString()
//             };
//             console.log('Returning error status:', response);
//             return res.json(response);
//         }

//         const sessionData = sessionDoc.data();
//         console.log('Session data:', sessionData);

//         // Special handling for Qwen models
//         if (assistantData.modelType === 'qwen' && sessionData.jobId) {
//             const gcpStatus = await qwenService.getTrainingStatus(sessionData.jobId);
//             console.log('GCP training status for Qwen:', gcpStatus);

//             const response = {
//                 status: gcpStatus.status,
//                 progress: gcpStatus.progress || sessionData.progress || 25,
//                 timestamp: new Date().toISOString(),
//                 error: gcpStatus.error,
//                 modelInfo: sessionData.modelInfo
//             };

//             console.log('Returning Qwen status:', response);
//             return res.json(response);
//         }

//         // Original Gemini flow remains unchanged
//         if (sessionData.status === 'completed') {
//             console.log('Deployment completed, updating assistant');
//             await firestore.db.collection('assistants').doc(assistantId).update({
//                 deploymentStatus: 'deployed',
//                 currentDeploymentSession: null,
//                 lastDeployedAt: new Date()
//             });
//         }

//         // Build full response
//         const response = {
//             status: sessionData.status,
//             progress: sessionData.progress || 0,
//             timestamp: new Date().toISOString(),
//             error: sessionData.error,
//             modelInfo: sessionData.modelInfo
//         };

//         console.log('Returning status:', response);
//         res.json(response);
        
//     } catch (error) {
//         console.error('Status check error:', error);
//         res.status(500).json({
//             error: error.message,
//             timestamp: new Date().toISOString()
//         });
//     }
// });
export default router;