// backend/src/routes/documents.js
import express from 'express';
import multer from 'multer';
import { Firestore } from '@google-cloud/firestore';
import { Storage } from '@google-cloud/storage';
import geminiService from '../services/ai/gemini.js';
import vectors from '../services/storage/vectors.js';
import { verifyToken } from '../middleware/auth.js';

import mammoth from 'mammoth';
import path from 'path';
import fs from 'fs';
import { createRequire } from 'module';
import { checkLimits } from '../middleware/checkLimit.js';
const require = createRequire(import.meta.url);
const pdfParse = require('pdf-parse');
const router = express.Router();
// const firestore = new Firestore();
const firestore = new Firestore({
  projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
  keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  databaseId: 'circa'  // Explicitly specify the database name
});
const storage = new Storage();
const BUCKET_NAME = 'circa-ai';
// Create new assistant
// Configure multer storage (you can adjust as needed)

const upload = multer({ dest: 'uploads/' });
const isValidPDF = async (filePath) => {
    try {
        const dataBuffer = fs.readFileSync(filePath);
        // Try to verify PDF header
        const header = dataBuffer.slice(0, 5).toString();
        if (!header.startsWith('%PDF-')) {
            return false;
        }
        
        // Attempt to parse with pdf-parse with a timeout
        await pdfParse(dataBuffer, {
            max: 1, // Only try to parse first page to validate
            timeout: 5000 // 5 second timeout
        });
        return true;
    } catch (error) {
        console.error('PDF validation error:', error);
        return false;
    }
};

const getFileTypeFromBuffer = (buffer) => {
    // Check file signatures
    if (buffer.slice(0, 4).toString('hex') === '25504446') return 'pdf';
    if (buffer.slice(0, 2).toString('hex') === '504b') return 'docx';
    return 'unknown';
};


const generateSignedUrl = async (filePath) => {
    const options = {
      version: 'v4',
      action: 'read',
      expires: Date.now() + 15 * 60 * 1000, // 15 minutes
    };
  
    try {
      const [url] = await storage
        .bucket(BUCKET_NAME)
        .file(filePath)
        .getSignedUrl(options);
      return url;
    } catch (error) {
      console.error('Error generating signed URL:', error);
      throw new Error('Failed to generate signed URL');
    }
  };

router.post('/documents', verifyToken, checkLimits, upload.single('file'), async (req, res) => {
    try {
      const file = req.file;
      const userId = req.user.id;
      const metadata = JSON.parse(req.body.metadata || '{}');
  
      // Validate file
      if (!file) {
        return res.status(400).json({ error: 'No file provided' });
      }
  
      // Check file size (10MB limit)
      if (file.size > 10 * 1024 * 1024) {
        return res.status(400).json({ error: 'File size exceeds 10MB limit' });
      }
  
      // Upload to cloud storage
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const destinationPath = `documents/${userId}/${timestamp}_${file.originalname}`;
      
      await storage.bucket(BUCKET_NAME).upload(file.path, {
        destination: destinationPath,
        metadata: {
          contentType: file.mimetype,
        },
      });
  
      // Generate signed URL for download
      const [url] = await storage
        .bucket(BUCKET_NAME)
        .file(destinationPath)
        .getSignedUrl({
          version: 'v4',
          action: 'read',
          expires: Date.now() + 7 * 24 * 60 * 60 * 1000, // URL expires in 7 days
        });
  
      // Store document metadata in Firestore
      const docRef = await firestore.collection('documents').add({
        userId,
        name: file.originalname,
        type: file.mimetype,
        size: file.size,
        folder: metadata.folder || 'all',
        storagePath: destinationPath,
        downloadUrl: url,
        uploadedAt: Firestore.FieldValue.serverTimestamp(),
        hasEmbedding: false,
      });
  
      // Clean up local file
      fs.unlinkSync(file.path);
  
      res.status(201).json({
        id: docRef.id,
        name: file.originalname,
        type: file.mimetype,
        size: file.size,
        downloadUrl: url,
        folder: metadata.folder || 'all',
        uploadedAt: new Date(),
      });
    } catch (error) {
      console.error('Document upload error:', error);
      res.status(500).json({ error: 'Failed to upload document' });
    }
  });
  
  // Get all documents
  router.get('/documents', verifyToken, async (req, res) => {
    try {
      const userId = req.user.id;
      const { folder = 'all' } = req.query;
  
      let query = firestore.collection('documents')
        .where('userId', '==', userId);
      
      if (folder !== 'all') {
        query = query.where('folder', '==', folder);
      }
  
      // Remove the orderBy temporarily until index is created
      const snapshot = await query.get();
      
      
      const documents = [];
      for (const doc of snapshot.docs) {
        const data = doc.data();
        const file = storage.bucket(BUCKET_NAME).file(data.storagePath);
        const [metadata] = await file.getMetadata();
        const size = metadata?.size || metadata?.metadata?.size || 0;
  
        console.log(metadata)
        // Refresh signed URL if needed
        const [url] = await storage
          .bucket(BUCKET_NAME)
          .file(data.storagePath)
          .getSignedUrl({
            version: 'v4',
            action: 'read',
            expires: Date.now() + 7 * 24 * 60 * 60 * 1000,
          });
  
        documents.push({
          id: doc.id,
          ...data,
          size: parseInt(size), // Convert size to number
          downloadUrl: url,
          uploadedAt: data.uploadedAt?.toDate(),
        });
      }
  
      // Sort in memory instead
      documents.sort((a, b) => {
        const dateA = a.uploadedAt ? new Date(a.uploadedAt) : new Date(0);
        const dateB = b.uploadedAt ? new Date(b.uploadedAt) : new Date(0);
        return dateB - dateA; // descending order
      });
  
      res.json(documents);
    } catch (error) {
      console.error('Error fetching documents:', error);
      res.status(500).json({ error: 'Failed to fetch documents' });
    }
  });
  
  // Delete document
  router.delete('/documents/:id', verifyToken, async (req, res) => {
    try {
      const { id } = req.params;
      const userId = req.user.id;
  
      // Get document data
      const docRef = firestore.collection('documents').doc(id);
      const doc = await docRef.get();
  
      if (!doc.exists) {
        return res.status(404).json({ error: 'Document not found' });
      }
  
      const docData = doc.data();
      if (docData.userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access' });
      }
  
      // Delete from storage
      await storage.bucket(BUCKET_NAME).file(docData.storagePath).delete();
  
      // Delete from Firestore
      await docRef.delete();
      const userRef = firestore.collection('users').doc(userId);
      await userRef.update({
        'usage.documents': Firestore.FieldValue.increment(-1)
      });

      res.json({ message: 'Document deleted successfully' });
    } catch (error) {
      console.error('Error deleting document:', error);
      res.status(500).json({ error: 'Failed to delete document' });
    }
  });
  
  // Get documents available for assistant creation
  router.get('/documents/available', verifyToken, async (req, res) => {
    try {
      const userId = req.user.id;
      
      const snapshot = await firestore
        .collection('documents')
        .where('userId', '==', userId)
        .orderBy('uploadedAt', 'desc')
        .get();
  
      const documents = [];
      for (const doc of snapshot.docs) {
        const data = doc.data();
        documents.push({
          id: doc.id,
          name: data.name,
          type: data.type,
          size: data.size,
          hasEmbedding: data.hasEmbedding || false,
          uploadedAt: data.uploadedAt?.toDate(),
        });
      }
  
      res.json(documents);
    } catch (error) {
      console.error('Error fetching available documents:', error);
      res.status(500).json({ error: 'Failed to fetch available documents' });
    }
  });

  
export default router;


