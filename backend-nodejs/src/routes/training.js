// backend/src/routes/training.js
import express from 'express';
import { Firestore } from '@google-cloud/firestore';
import { VertexAI } from '@google-cloud/vertexai';
import { Storage } from '@google-cloud/storage';

const router = express.Router();
// const firestore = new Firestore();
const firestore = new Firestore({
  projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
  keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  databaseId: 'circa'  // Explicitly specify the database name
});
const vertexai = new VertexAI();
const storage = new Storage();
const BUCKET_NAME = 'ai-assistant-assets';

// Start training process
router.post('/:assistantId/start', async (req, res) => {
  try {
    const { assistantId } = req.params;
    const { modelConfig } = req.body;

    // Create training session
    const sessionRef = firestore.collection('training_sessions').doc();
    await sessionRef.set({
      id: sessionRef.id,
      assistantId,
      status: 'initializing',
      progress: 0,
      startedAt: Firestore.FieldValue.serverTimestamp(),
      modelConfig,
      error: null
    });

    // Get all documents for this assistant
    const documentsSnapshot = await firestore
      .collection('documents')
      .where('assistantId', '==', assistantId)
      .get();

    // Create batch processor for documents
    const batch = firestore.batch();
    documentsSnapshot.forEach(doc => {
      const docRef = firestore.collection('training_queue').doc();
      batch.set(docRef, {
        documentId: doc.id,
        sessionId: sessionRef.id,
        status: 'pending',
        createdAt: Firestore.FieldValue.serverTimestamp()
      });
    });

    await batch.commit();

    // Update assistant status
    await firestore.collection('assistants').doc(assistantId).update({
      trainingStatus: 'in_progress',
      currentTrainingSession: sessionRef.id
    });

    res.json({
      sessionId: sessionRef.id,
      message: 'Training started successfully'
    });
  } catch (error) {
    console.error('Error starting training:', error);
    res.status(500).json({ error: 'Failed to start training' });
  }
});

// Get training status
router.get('/:assistantId/status', async (req, res) => {
  try {
    const { assistantId } = req.params;
    
    const assistant = await firestore.collection('assistants').doc(assistantId).get();
    const { currentTrainingSession } = assistant.data();

    if (!currentTrainingSession) {
      return res.json({ status: 'no_training' });
    }

    const session = await firestore
      .collection('training_sessions')
      .doc(currentTrainingSession)
      .get();

    res.json(session.data());
  } catch (error) {
    console.error('Error fetching training status:', error);
    res.status(500).json({ error: 'Failed to fetch training status' });
  }
});

// Stop training process
router.post('/:assistantId/stop', async (req, res) => {
  try {
    const { assistantId } = req.params;
    
    const assistant = await firestore.collection('assistants').doc(assistantId).get();
    const { currentTrainingSession } = assistant.data();

    if (!currentTrainingSession) {
      return res.status(400).json({ error: 'No active training session' });
    }

    // Update session status
    await firestore.collection('training_sessions').doc(currentTrainingSession).update({
      status: 'stopped',
      stoppedAt: Firestore.FieldValue.serverTimestamp()
    });

    // Update assistant status
    await firestore.collection('assistants').doc(assistantId).update({
      trainingStatus: 'stopped',
      currentTrainingSession: null
    });

    // Clear training queue
    const queueSnapshot = await firestore
      .collection('training_queue')
      .where('sessionId', '==', currentTrainingSession)
      .where('status', '==', 'pending')
      .get();

    const batch = firestore.batch();
    queueSnapshot.forEach(doc => {
      batch.delete(doc.ref);
    });

    await batch.commit();

    res.json({ message: 'Training stopped successfully' });
  } catch (error) {
    console.error('Error stopping training:', error);
    res.status(500).json({ error: 'Failed to stop training' });
  }
});

export default router;