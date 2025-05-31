// backend/src/routes/voices.js
import express from 'express';
import multer from 'multer';
import fs from 'fs';
import { Firestore } from '@google-cloud/firestore';
import { Storage } from '@google-cloud/storage';
import { verifyToken } from '../middleware/auth.js';

const router = express.Router();
const upload = multer({ dest: 'uploads/' }); // Temporary storage for uploaded files
// const firestore = new Firestore();
const firestore = new Firestore({
  projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
  keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  databaseId: 'circa'  // Explicitly specify the database name
});
const storage = new Storage();

// Set your bucket name (this should match your Google Cloud Storage bucket)
const BUCKET_NAME = process.env.GCLOUD_BUCKET || 'circa-ai';

// POST /api/voices
// Upload a new voice recording
router.post('/voices', verifyToken, upload.single('audio'), async (req, res) => {
  try {
    const userId = req.user.id;
    const { voiceName, transcript } = req.body;
    const file = req.file;

    if (!file) {
      return res.status(400).json({ error: 'No audio file provided' });
    }

    // Create a unique destination path in the bucket
    // Create a unique destination path in the bucket with a forced .wav extension
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const baseName = file.originalname.split('.')[0]; // Remove any existing extension
    const destinationPath = `voices/${userId}/${voiceName}_${timestamp}_${baseName}.wav`;

    // Upload the file to Google Cloud Storage
    await storage.bucket(BUCKET_NAME).upload(file.path, {
      destination: destinationPath,
      metadata: {
        contentType: file.mimetype,
      },
    });

    // Generate a signed URL for reading the file (expires in 7 days)
    const [url] = await storage
      .bucket(BUCKET_NAME)
      .file(destinationPath)
      .getSignedUrl({
        version: 'v4',
        action: 'read',
        expires: Date.now() + 7 * 24 * 60 * 60 * 1000,
      });

    // Store voice metadata in Firestore
    const voiceData = {
      userId,
      voiceName,
      transcript,
      storagePath: destinationPath,
      audioUrl: url,
      createdAt: Firestore.FieldValue.serverTimestamp(),
    };

    const docRef = await firestore.collection('voices').add(voiceData);

    // Clean up the temporary file
    fs.unlinkSync(file.path);

    res.status(201).json({
      id: docRef.id,
      ...voiceData,
      audioUrl: url,
    });
  } catch (error) {
    console.error('Voice upload error:', error);
    res.status(500).json({ error: 'Failed to upload voice' });
  }
});

// DELETE /api/voices/:id
// Delete a voice recording
router.delete('/voices/:id', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const voiceId = req.params.id;
    const docRef = firestore.collection('voices').doc(voiceId);
    const doc = await docRef.get();

    if (!doc.exists) {
      return res.status(404).json({ error: 'Voice not found' });
    }

    const voiceData = doc.data();

    if (voiceData.userId !== userId) {
      return res.status(403).json({ error: 'Unauthorized access' });
    }

    // Delete the audio file from storage
    await storage.bucket(BUCKET_NAME).file(voiceData.storagePath).delete();

    // Delete the Firestore document
    await docRef.delete();

    res.json({ message: 'Voice deleted successfully' });
  } catch (error) {
    console.error('Voice deletion error:', error);
    res.status(500).json({ error: 'Failed to delete voice' });
  }
});

export default router;
