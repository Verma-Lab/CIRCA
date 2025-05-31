// backend/src/routes/assistants.js
// backend/src/routes/assistants.js
import express from 'express';
import multer from 'multer';
import { Firestore } from '@google-cloud/firestore';
import { Storage } from '@google-cloud/storage';
import geminiService from '../services/ai/gemini.js';
import vectors from '../services/storage/vectors.js';
import { verifyToken } from '../middleware/auth.js';
import { checkLimits } from '../middleware/checkLimit.js';
import axios from 'axios';
import * as chrono from 'chrono-node';
import { DateTime } from 'luxon';
import Papa from 'papaparse'
import firestoreService from '../services/db/firestore.js';
import { getGoogleDocContent, getGoogleSheetContent, getGoogleFileName } from './googleoffice.js';
// backend/src/routes/assistants.js
import { google } from 'googleapis';
import mammoth from 'mammoth';
import path, { parse } from 'path';
import fs from 'fs';
import { createRequire } from 'module';
import jwt from 'jsonwebtoken';
// const PYTHON_API_URL = "http://localhost:8000"
const PYTHON_API_URL = "https://app.homosapieus.com"

// const PYTHON_API_URL = "https://0139-2601-47-4a82-47f0-c925-8a6c-e19e-e217.ngrok-free.app"
const PYTHON_SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"

async function generatePythonToken(userId) {
  // Fetch username from Firestore (or your user storage)
  const userRef = firestore.collection('users').doc(userId);
  const userDoc = await userRef.get();
  if (!userDoc.exists) {
    throw new Error(`User not found for userId: ${userId}`);
  }
  // console.log(userDoc.data())
  const username = userDoc.data().name; // Adjust field name based on your schema

  console.log('Fetched username:', username);

  const payload = {
    sub: username,
    exp: Math.floor(Date.now() / 1000) + 3600 // 1 hour expiration
  };
  const token = jwt.sign(payload, PYTHON_SECRET_KEY, { algorithm: 'HS256' });
  return token;
}

const require = createRequire(import.meta.url);
const pdfParse = require('pdf-parse');
const router = express.Router();
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
const uploadCustomization = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => {
      cb(null, 'uploads/');
    },
    filename: (req, file, cb) => {
      cb(null, Date.now() + '-' + file.originalname);
    }
  })
}).fields([
  { name: 'files', maxCount: 10 },  // For document files
  { name: 'avatar', maxCount: 1 },  // For avatar
  { name: 'voice', maxCount: 1 }    // For voice
]);
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


const generateSignedUrlPreview = async (filePath) => {
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

const generateSignedUrl = async (bucketName, filePath) => {
  const options = {
    version: 'v4',
    action: 'read',
    expires: Date.now() + 15 * 60 * 1000, // 15 minutes
  };

  try {
    const file = storage.bucket(bucketName).file(filePath);
    
    // Check if file exists before generating URL
    const [exists] = await file.exists();
    if (!exists) {
      console.error('File does not exist:', filePath);
      throw new Error('File not found');
    }

    const [url] = await file.getSignedUrl(options);
    console.log('Generated URL for path:', filePath);
    return url;
  } catch (error) {
    console.error('Error generating signed URL:', error);
    throw new Error(`Failed to generate signed URL for ${filePath}: ${error.message}`);
  }
};
// router.post('/', verifyToken, checkLimits,upload.array('files'), async (req, res) => {
//     try {
//         const { name, description, category, instructions } = req.body;
//         const selectedDocuments = JSON.parse(req.body.selectedDocuments || '[]');
//         const userId = req.user.id;
//         const assistantRef = firestore.collection('assistants').doc();
//         console.log('HITTED')
//         await assistantRef.set({
//             id: assistantRef.id,
//             name,
//             description,
//             category,
//             instructions,
//             userId,
//             createdAt: Firestore.FieldValue.serverTimestamp(),
//             status: 'active',
//             documentCount: 0,
//             queryCount: 0,
//             documentIds: selectedDocuments // Add this line to track selected documents
//         });

//         // Process selected documents first
//         if (selectedDocuments && selectedDocuments.length > 0) {
//             console.log('Processing selected documents:', selectedDocuments);
            
//             for (const docId of selectedDocuments) {
//                 const docRef = firestore.collection('documents').doc(docId);
//                 const doc = await docRef.get();
                
//                 if (!doc.exists || doc.data().userId !== userId) {
//                     continue;
//                 }

//                 const docData = doc.data();
                
//                 // Read file from storage
//                 const file = storage.bucket(BUCKET_NAME).file(docData.storagePath);
//                 const [content] = await file.download();
//                 let textContent = '';

//                 // Extract text based on file type
//                 if (docData.type.includes('pdf')) {
//                     const pdfData = await pdfParse(content);
//                     textContent = pdfData.text;
//                 } else if (docData.type.includes('docx')) {
//                     const result = await mammoth.extractRawText({ buffer: content });
//                     textContent = result.value;
//                 } else if (docData.type.includes('text')) {
//                     textContent = content.toString('utf8');
//                 } else if (docData.type.includes('csv')) {
//                     const csvText = content.toString('utf8');
//                     const results = Papa.parse(csvText, {
//                         header: true,
//                         skipEmptyLines: true,
//                         dynamicTyping: true
//                     });
                    
//                     textContent = results.data.map(row => 
//                         Object.entries(row)
//                             .map(([key, value]) => `${key}: ${value}`)
//                             .join(', ')
//                     ).join('\n');
//                 }

//                 // Generate embedding
//                 const embedding = await geminiService.generateEmbeddings(textContent);
                
//                 // Store vector
//                 await vectors.storeVectors([embedding], {
//                     assistantId: assistantRef.id,
//                     type: 'document',
//                     name: docData.name,
//                     content: textContent,
//                     createdAt: new Date(),
//                     docType: docData.type
//                 });

//                 // Update assistant's document count
//                 await assistantRef.update({
//                     documentCount: Firestore.FieldValue.increment(1),
//                 });

//                 // Update document status
//                 await docRef.update({ hasEmbedding: true });
//             }
//         }

  
//       // Process uploaded files
//       if (req.files && req.files.length > 0) {
//         console.log(`Processing ${req.files.length} uploaded files.`);
//         for (const file of req.files) {
//           const filePath = file.path;
//           const fileType = path.extname(file.originalname).toLowerCase();
//           let fileContent = '';
//           console.log(filePath)
//           // Extract text based on file type
//           if (fileType === '.pdf') {
//             const dataBuffer = fs.readFileSync(filePath);
//             const pdfData = await pdfParse(dataBuffer);
//             fileContent = pdfData.text;
            
//             // Store the entire PDF content as one vector to maintain context
//             const embedding = await geminiService.generateEmbeddings(fileContent);
//             await vectors.storeVectors([embedding], {
//               assistantId: assistantRef.id,
//               type: 'document',
//               name: file.originalname,
//               content: fileContent,
//               createdAt: new Date(),
//               docType: 'pdf'
//             });
            
//           } else if (fileType === '.docx') {
//             const data = await mammoth.extractRawText({ path: filePath });
//             fileContent = data.value;
//             // For other document types, use chunking
//             const contentChunks = splitTextIntoChunks(fileContent, 1500);
//             for (const chunk of contentChunks) {
//               const embedding = await geminiService.generateEmbeddings(chunk);
//               await vectors.storeVectors([embedding], {
//                 assistantId: assistantRef.id,
//                 type: 'document',
//                 name: file.originalname,
//                 content: chunk,
//                 createdAt: new Date(),
//                 docType: 'docx'
//               });
//             }
//           } else if (fileType === '.txt') {
//             fileContent = fs.readFileSync(filePath, 'utf8');
//             // For other document types, use chunking
//             const contentChunks = splitTextIntoChunks(fileContent, 1500);
//             for (const chunk of contentChunks) {
//               const embedding = await geminiService.generateEmbeddings(chunk);
//               await vectors.storeVectors([embedding], {
//                 assistantId: assistantRef.id,
//                 type: 'document',
//                 name: file.originalname,
//                 content: chunk,
//                 createdAt: new Date(),
//                 docType: 'txt'
//               });
//             }
//           } else if (fileType === '.csv') {
//             fileContent = fs.readFileSync(filePath, 'utf8');
//             const results = Papa.parse(fileContent, {
//               header: true,
//               skipEmptyLines: true,
//               dynamicTyping: true
//             });
            
//             // Convert CSV rows to text for embedding
//             const csvText = results.data.map(row => 
//               Object.entries(row)
//                 .map(([key, value]) => `${key}: ${value}`)
//                 .join(', ')
//             ).join('\n');
          
//             // Generate embeddings for the CSV content
//             const embedding = await geminiService.generateEmbeddings(csvText);
//             await vectors.storeVectors([embedding], {
//               assistantId: assistantRef.id,
//               type: 'document',
//               name: file.originalname,
//               content: csvText,
//               createdAt: new Date(),
//               docType: 'csv'
//             });
//         }          
//           else {
//             console.warn(`Unsupported file type: ${fileType}`);
//             continue;
//           }
  
//           // Update assistant's document count
//           await assistantRef.update({
//             documentCount: Firestore.FieldValue.increment(1),
//           });
  
//           // Optionally, upload the original file to cloud storage
//           const storagePath = `assistants/${assistantRef.id}/documents/${file.originalname}`;
//           await storage.bucket(BUCKET_NAME).upload(filePath, {
//             destination: storagePath,
//             metadata: {
//               contentType: file.mimetype,
//               metadata: {
//                 size: file.size,  // Add size to metadata
//                 originalName: file.originalname,
//                 uploadTime: new Date().toISOString()
//               }
//             }
//           });
  
//           // Clean up the local file
//           fs.unlinkSync(filePath);
//         }
//       }
  
//       res.status(201).json({ id: assistantRef.id, message: 'Assistant created successfully' });
//     } catch (error) {
//       console.error('Error creating assistant:', error);
//       res.status(500).json({ error: 'Failed to create assistant' });
//     }
// });

router.post('/', verifyToken, checkLimits, 
  upload.fields([
    { name: 'files', maxCount: 10 },
    { name: 'avatar', maxCount: 1 },
    { name: 'voice', maxCount: 1 }
  ]), 
  async (req, res) => {
    try {
      const { name, description, category, instructions, customization, flowData, assistantType,         
        kpiSettings , organization_id, survey_id
      } = req.body;
      const selectedDocuments = JSON.parse(req.body.selectedDocuments || '[]');
      const userId = req.user.id;
      const assistantRef = firestore.collection('assistants').doc();
      const creatorDoc = await firestore.collection('users').doc(userId).get();
      const creatorData = creatorDoc.data();
      const finalOrganizationId = organization_id || userOrganizationId;
      console.log('[ORGANIZATION DATA]', finalOrganizationId)
      console.log('GETTING FLOW DATA')
      console.log(flowData)
      // Parse customization with fallbacks to creator data
      const parsedCustomization = customization ? JSON.parse(customization) : {};
      console.log('PARSED CUSTOMIZATION', parsedCustomization)
      console.log('ADDING [SURVEY DATA]', survey_id)
      // Parse flowData if provided
      const parsedFlowData = flowData ? JSON.parse(flowData) : null;
      if (parsedFlowData && !parsedFlowData.id) {
        parsedFlowData.id = assistantRef.id; // Use the assistant ID for the flow ID
      }

      if (parsedFlowData) {
        try {
          console.log('Indexing flow for optimized chat processing...');
          console.log('PARSED FLOW DATA', parsedFlowData)

          // Call the Python endpoint to index the flow
          await axios.post(`${PYTHON_API_URL}/api/index/flow-knowledge`, parsedFlowData);
          console.log('Flow indexed successfully');
        } catch (indexError) {
          console.error('Failed to index flow:', indexError.message);
          // Don't fail the whole request if indexing fails
        }
      }
      //for the KPI
      console.log('Assistant Type')
      console.log(assistantType)
      const parsedKPISettings = (assistantType === 'representative' && kpiSettings) 
      ? JSON.parse(kpiSettings) 
      : null;
      let avatarUrl = null;

      console.log('KPI Setting', parsedKPISettings)
      if (req.files?.avatar) {
        const avatarFile = req.files.avatar[0];
        
        // Sanitize the filename to remove special characters and spaces
        const sanitizedFilename = avatarFile.originalname
          .replace(/[^a-zA-Z0-9.-]/g, '-')
          .toLowerCase();
          
        const avatarPath = `assistants/${assistantRef.id}/avatar/${sanitizedFilename}`;
        
        try {
          await storage.bucket(BUCKET_NAME).upload(avatarFile.path, {
            destination: avatarPath,
            metadata: {
              contentType: avatarFile.mimetype
            }
          });
          
          console.log("Avatar uploaded to path:", avatarPath);
          
          // Generate signed URL with the same path
          avatarUrl = await generateSignedUrl(BUCKET_NAME, avatarPath);
          console.log('Generated avatar URL:', avatarUrl);
          
          fs.unlinkSync(avatarFile.path);
        } catch (error) {
          console.error('Error handling avatar upload:', error);
          throw error;
        }
      }
      

      let voiceUrl = null;
      if (req.files?.voice) {
          const voiceFile = req.files.voice[0];
          const voicePath = `assistants/${assistantRef.id}/voice/${voiceFile.originalname}`;
          await storage.bucket(BUCKET_NAME).upload(voiceFile.path, {
              destination: voicePath,
              metadata: {
                  contentType: voiceFile.mimetype
              }
          });
          voiceUrl = await generateSignedUrl(BUCKET_NAME, voicePath);
          fs.unlinkSync(voiceFile.path);
      }

      // Construct customization object with fallbacks
      const finalCustomization = {
          avatar: avatarUrl || parsedCustomization?.avatar || creatorData?.avatar || null,
          bio: parsedCustomization?.bio || creatorData?.bio || null,
          expertise: parsedCustomization?.expertise || creatorData?.expertise || [],
          experience: parsedCustomization?.experience || creatorData?.experience || null,
          profession: parsedCustomization?.profession || creatorData?.profession || null,
          voiceType: parsedCustomization?.voiceType || null,
          socialLinks: parsedCustomization?.socialLinks || {
              twitter: null,
              linkedin: null,
              github: null,
              website: null
          },
          voice: voiceUrl || parsedCustomization?.voice || null
      };

      let surveyData = null;
      if (survey_id) {
        try {
          console.log('Fetching survey data for ID:', survey_id);
          const pythonToken = await generatePythonToken(userId);
          console.log('Generated Python token:', pythonToken);

          console.log('Request URL:', `${PYTHON_API_URL}/api/surveys/${survey_id}`);
          console.log('Request headers:', {
            'Authorization': `Bearer ${pythonToken}`,
            'Content-Type': 'application/json'
          });
          
          const surveyResponse = await axios.get(`${PYTHON_API_URL}/api/surveys/${survey_id}`, {
            headers: {
              'Authorization': `Bearer ${pythonToken}`,
              'Content-Type': 'application/json'
            }
          });

          surveyData = surveyResponse.data;
          console.log('Got survey data:', surveyData);
        } catch (surveyError) {
          console.error('Error fetching survey data:', surveyError.message);
          // Still save survey_id even if fetching data fails
        }
      }

      await assistantRef.set({
          id: assistantRef.id,
          name,
          description,
          category,
          instructions,
          userId,
          organization_id: finalOrganizationId, // Add organization_id to the document
          survey_id: survey_id || null,
          survey_data: surveyData || null, // Save survey data
          assistantType, // Include assistantType in the assistant document
          createdAt: Firestore.FieldValue.serverTimestamp(),
          status: 'active',
          documentCount: 0,
          queryCount: 0,
          documentIds: selectedDocuments,
          customization: finalCustomization,
          flowData: parsedFlowData, // Include flow data in the assistant document
          kpiConfig: assistantType === 'representative' ? {
            categories: parsedKPISettings?.categories || {},
            activeKPIs: parsedKPISettings?.activeKPIs || {},
            metrics: {},
            lastUpdated: null
          } : null
      });

      const documentsToIndex = [];
      // Process selected documents first
      if (selectedDocuments && selectedDocuments.length > 0) {
          console.log('Processing selected documents:', selectedDocuments);
          for (const doc of selectedDocuments) {
            let textContent = '';
            if (doc.type === 'docs') {
              textContent = await getGoogleDocContent(doc.id, userId);
            } else if (doc.type === 'sheets') {
              textContent = await getGoogleSheetContent(doc.id, userId);
            } else {
              const docRef = firestore.collection('documents').doc(doc.id);
              const docData = (await docRef.get()).data();
              if (docData && docData.userId === userId) {
                const file = storage.bucket(BUCKET_NAME).file(docData.storagePath);
                const [content] = await file.download();
                if (docData.type.includes('pdf')) {
                  const pdfData = await pdfParse(content);
                  textContent = pdfData.text;
                } else if (docData.type.includes('docx')) {
                  const result = await mammoth.extractRawText({ buffer: content });
                  textContent = result.value;
                } else if (docData.type.includes('text')) {
                  textContent = content.toString('utf8');
                } else if (docData.type.includes('csv')) {
                  const csvText = content.toString('utf8');
                  const results = Papa.parse(csvText, { header: true, skipEmptyLines: true, dynamicTyping: true });
                  textContent = results.data.map(row => 
                    Object.entries(row).map(([key, value]) => `${key}: ${value}`).join(', ')
                  ).join('\n');
                }
              }
            }
            if (textContent) {
              documentsToIndex.push({ id: doc.id, name: doc.name, content: textContent });
            }
          }
        }

      // Process uploaded files
      if (req.files?.files) {
        for (const file of req.files.files) {
          const filePath = file.path;
          const fileType = path.extname(file.originalname).toLowerCase();
          let textContent = '';
          if (fileType === '.pdf') {
            const dataBuffer = fs.readFileSync(filePath);
            const pdfData = await pdfParse(dataBuffer);
            textContent = pdfData.text;
          } else if (fileType === '.docx') {
            const data = await mammoth.extractRawText({ path: filePath });
            textContent = data.value;
          } else if (fileType === '.txt') {
            textContent = fs.readFileSync(filePath, 'utf8');
          } else if (fileType === '.csv') {
            const csvText = fs.readFileSync(filePath, 'utf8');
            const results = Papa.parse(csvText, { header: true, skipEmptyLines: true, dynamicTyping: true });
            textContent = results.data.map(row => 
              Object.entries(row).map(([key, value]) => `${key}: ${value}`).join(', ')
            ).join('\n');
          }
          if (textContent) {
            const documentRef = firestore.collection('documents').doc();
            await documentRef.set({
              id: documentRef.id,
              userId,
              assistantId: assistantRef.id,
              name: file.originalname,
              type: file.mimetype,
              size: file.size,
              storagePath: `assistants/${assistantRef.id}/documents/${file.originalname}`,
              hasEmbedding: true,
              createdAt: Firestore.FieldValue.serverTimestamp()
            });
            documentsToIndex.push({ id: documentRef.id, name: file.originalname, content: textContent });
          }
          fs.unlinkSync(filePath);
        }
      }

      // if (documentsToIndex.length > 0) {
      //   try {
      //     await axios.post(`${PYTHON_API_URL}/api/index/assistant-documents`, {
      //       assistant_id: assistantRef.id,
      //       documents: documentsToIndex
      //     });
      //     console.log('Documents indexed successfully');
      //     await assistantRef.update({
      //       documentCount: documentsToIndex.length,
      //       documentIds: documentsToIndex.map(doc => ({ id: doc.id, name: doc.name, type: 'document', service: 'storage' }))
      //     });
      //   } catch (indexError) {
      //     console.error('Failed to index documents:', indexError.message);
      //   }
      // }
      // Update the assistant document to include document IDs right away
await assistantRef.update({
  documentCount: documentsToIndex.length,
  documentIds: documentsToIndex.map(doc => ({ id: doc.id, name: doc.name, type: 'document', service: 'storage' })),
  indexingStatus: {
    documents: documentsToIndex.length > 0 ? 'in_progress' : 'not_needed',
    startedAt: Firestore.FieldValue.serverTimestamp()
  }
});

// Start document indexing in the background (don't await)
if (documentsToIndex.length > 0) {
  // Fire and forget - don't wait for completion
  await axios.post(`${PYTHON_API_URL}/api/index/assistant-documents`, {
    assistant_id: assistantRef.id,
    documents: documentsToIndex
  })
  .then(() => {
    console.log('Documents indexed successfully');
    return assistantRef.update({
      'indexingStatus.documents': 'completed',
      'indexingStatus.completedAt': Firestore.FieldValue.serverTimestamp()
    });
  })
  .catch((indexError) => {
    console.error('Failed to index documents:', indexError.message);
    return assistantRef.update({
      'indexingStatus.documents': 'failed',
      'indexingStatus.error': indexError.message
    });
  });
}
      res.status(201).json({ 
          id: assistantRef.id, 
          message: 'Assistant created successfully',
          customization: finalCustomization,
          organization_id: finalOrganizationId, // Return the organization_id in the response
          survey_data: surveyData || null, // Include survey data in response
          survey_id: survey_id || null,
          kpiConfig: assistantType === 'representative' ? {
            categories: parsedKPISettings?.categories || {},
            activeKPIs: parsedKPISettings?.activeKPIs || {}
          } : null
      });
    } catch (error) {
      console.error('Error creating assistant:', error);
      res.status(500).json({ error: 'Failed to create assistant' });
    }
});
router.get('/:id/documents/previews', verifyToken, async (req, res) => {
    try {
        const { id } = req.params;
        const userId = req.user.id;

        // Verify assistant ownership
        const assistantRef = firestore.collection('assistants').doc(id);
        const assistant = await assistantRef.get();

        if (!assistant.exists) {
            return res.status(404).json({ error: 'Assistant not found' });
        }

        if (assistant.data().userId !== userId) {
            return res.status(403).json({ error: 'Unauthorized access' });
        }

        const assistantData = assistant.data();
        const selectedDocIds = assistantData.documentIds || [];
        const processedFiles = new Map(); // Track processed files by name
        const documentsToReturn = [];

        // 1. First process uploaded files from storage bucket
        const [files] = await storage.bucket(BUCKET_NAME).getFiles({
            prefix: `assistants/${id}/documents/`,
        });

        for (const file of files) {
            const metadata = await file.getMetadata();
            const fileName = path.basename(file.name).split('_').pop(); // Remove any prefix
            
            // Skip if we already processed this file
            if (processedFiles.has(fileName)) continue;
            
            const fileType = path.extname(fileName).toLowerCase().replace('.', '');
            let previewUrl = '';

            if (fileType === 'pdf' || ['docx', 'doc'].includes(fileType) || fileType === 'txt') {
              console.log('DEBUG ERROR')
              console.log(BUCKET_NAME, file.name)
              previewUrl = await generateSignedUrlPreview(BUCKET_NAME, file.name);
              console.log('Generated preview URL for:', file.name);
            }
            console.log(previewUrl)
            documentsToReturn.push({
                id: file.name, // Use full path as ID
                name: fileName,
                size: metadata[0].size,
                type: fileType,
                previewUrl,
                hasEmbedding: true,
                source: 'storage'
            });

            processedFiles.set(fileName, true);
        }

        // 2. Then process selected documents that weren't found in storage
        for (const docId of selectedDocIds) {
            const docRef = firestore.collection('documents').doc(docId);
            const doc = await docRef.get();
            
            if (!doc.exists) continue;

            const docData = doc.data();
            const fileName = docData.name;

            // Skip if we already have this file
            if (processedFiles.has(fileName)) continue;

            let previewUrl = '';
            if (docData.storagePath) {
                try {
                    previewUrl = await generateSignedUrlPreview(docData.storagePath);
                } catch (error) {
                    console.error('Error generating preview URL:', error);
                }
            }

            documentsToReturn.push({
                id: docId,
                name: fileName,
                size: docData.size || 0,
                type: docData.type,
                previewUrl,
                hasEmbedding: docData.hasEmbedding || true,
                source: 'firestore'
            });

            processedFiles.set(fileName, true);
        }

        // Log the results for debugging
        console.log('Documents found:', {
            total: documentsToReturn.length,
            fromStorage: documentsToReturn.filter(d => d.source === 'storage').length,
            fromFirestore: documentsToReturn.filter(d => d.source === 'firestore').length
        });

        res.json(documentsToReturn);
    } catch (error) {
        console.error('Error fetching document previews:', error);
        res.status(500).json({ error: 'Failed to fetch document previews' });
    }
});
  
  // Utility function to split text into chunks
function splitTextIntoChunks(text, maxLength) {
    const chunks = [];
    let currentChunk = '';
  
    const words = text.split(/\s+/);
    for (const word of words) {
      if ((currentChunk + ' ' + word).length > maxLength) {
        chunks.push(currentChunk);
        currentChunk = word;
      } else {
        currentChunk += ' ' + word;
      }
    }
    if (currentChunk) {
      chunks.push(currentChunk);
    }
    return chunks;
  }
// Get all assistants
// router.get('/', verifyToken, async (req, res) => {
//     try {
//       // The user object is now available as req.user thanks to your middleware
//       const userId = req.user.id;
      
//       // Query assistants with a filter for the current user
//       const assistantsSnapshot = await firestore.collection('assistants')
//         .where('userId', '==', userId)
//         .get();
      
//       const assistants = [];
//       assistantsSnapshot.forEach(doc => {
//         assistants.push({ id: doc.id, ...doc.data() });
//       });
  
//       console.log(`Fetched ${assistants.length} assistants for user ${userId}`);
//       res.json(assistants);
//     } catch (error) {
//       console.error('Error fetching assistants:', error);
//       res.status(500).json({ error: 'Failed to fetch assistants' });
//     }
//   });
  router.get('/', verifyToken, async (req, res) => {
    try {
      // Get the user and their organization ID from auth
      const userId = req.user.id;
      const userDoc = await firestore.collection('users').doc(userId).get();
      const userData = userDoc.data();
      const organizationId = userData?.organization_id;
      console.log('Fetched [ORGANIZATION]', organizationId)
      // If there's no organization ID, fall back to just user-specific assistants
      if (!organizationId) {
        const userAssistantsSnapshot = await firestore.collection('assistants')
          .where('userId', '==', userId)
          .get();
        
        const assistants = [];
        userAssistantsSnapshot.forEach(doc => {
          assistants.push({ id: doc.id, ...doc.data() });
        });
        
        console.log(`Fetched ${assistants.length} personal assistants for user ${userId}`);
        return res.json(assistants);
      }
      
      // With an organization ID, fetch all assistants for this organization
      const orgAssistantsSnapshot = await firestore.collection('assistants')
        .where('organization_id', '==', organizationId)
        .get();
      
      const assistants = [];
      orgAssistantsSnapshot.forEach(doc => {
        const assistant = { id: doc.id, ...doc.data() };
        // Add a flag to indicate if this assistant belongs to the current user
        assistant.isOwner = assistant.userId === userId;
        assistants.push(assistant);
      });
      
      console.log(`Fetched ${assistants.length} organization assistants for org ${organizationId}`);
      res.json(assistants);
      
    } catch (error) {
      console.error('Error fetching assistants:', error);
      res.status(500).json({ error: 'Failed to fetch assistants' });
    }
  });

// router.put('/:id', verifyToken, upload.array('files'), async (req, res) => {
//     try {
//         const { id } = req.params;
//         const userId = req.user.id;
//         const { name, description, category, instructions } = req.body;
//         const assistantRef = firestore.collection('assistants').doc(id);
//         let flowData = null;

//          // Parse flowData if it exists in the request
//          if (req.body.flowData) {
//           try {
//               flowData = JSON.parse(req.body.flowData);
//               console.log('Received flowData:', flowData);
//           } catch (error) {
//               console.error('Error parsing flowData:', error);
//               return res.status(400).json({ error: 'Invalid flowData format' });
//           }
//       }

//         // Verify assistant ownership
//         const assistant = await assistantRef.get();
//         if (!assistant.exists) {
//             return res.status(404).json({ error: 'Assistant not found' });
//         }
//         if (assistant.data().userId !== userId) {
//             return res.status(403).json({ error: 'Unauthorized access' });
//         }

//         // Get current assistant data
//         const currentAssistant = assistant.data();

//         // Parse selected documents from request body
//         let selectedDocuments = [];
//         try {
//             selectedDocuments = JSON.parse(req.body.selectedDocuments || '[]');
//             console.log('Selected documents:', selectedDocuments);
//         } catch (error) {
//             console.error('Error parsing selectedDocuments:', error);
//             return res.status(400).json({ error: 'Invalid selectedDocuments format' });
//         }

//         // Initialize update data
//         const updateData = {
//             updatedAt: Firestore.FieldValue.serverTimestamp()
//         };

//         // Add basic fields if changed
//         if (name) updateData.name = name;
//         if (description) updateData.description = description;
//         if (category) updateData.category = category;
//         if (instructions) updateData.instructions = instructions;
//         if (flowData) updateData.flowData = flowData;

//         // Initialize arrays to track all document IDs
//         let allDocumentIds = [...selectedDocuments]; // Start with selected documents
//         let newDocumentIds = []; // Track newly uploaded documents

//         // 1. Process selected documents first
//         for (const docId of selectedDocuments) {
//             const docRef = firestore.collection('documents').doc(docId);
//             const doc = await docRef.get();
        
//             if (!doc.exists || doc.data().userId !== userId) {
//                 console.warn(`Document ${docId} not found or unauthorized`);
//                 continue;
//             }
        
//             // Always process selected documents to ensure embeddings are up to date
//             try {
//                 const docData = doc.data();
//                 console.log(`Processing selected document: ${docData.name}`);
                
//                 // Get file from storage
//                 const file = storage.bucket(BUCKET_NAME).file(docData.storagePath);
//                 const [content] = await file.download();
//                 let textContent = '';
        
//                 // Extract text based on file type
//                 if (docData.type.includes('pdf')) {
//                     const pdfData = await pdfParse(content);
//                     textContent = pdfData.text;
//                 } else if (docData.type.includes('docx')) {
//                     const result = await mammoth.extractRawText({ buffer: content });
//                     textContent = result.value;
//                 } else if (docData.type.includes('text') || docData.type.includes('txt')) {
//                     textContent = content.toString('utf8');
//                 }
//                 else if (fileType === '.csv') {
//                     // Read the CSV file content
//                     const csvContent = fs.readFileSync(filePath, 'utf8');
                    
//                     // Parse CSV using PapaParse for robust handling
//                     const parsedData = Papa.parse(csvContent, {
//                       header: true,
//                       skipEmptyLines: true,
//                       dynamicTyping: true
//                     });
                  
//                     console.log('CSV Parse Result:', {
//                         rowCount: parseResult.data.length,
//                         headers: parseResult.meta.fields,
//                         sampleRow: parseResult.data[0]
//                     });
//                     // Convert parsed data to text for vector storage
//                     textContent = parsedData.data
//                       .map(row => Object.values(row).join(' '))
//                       .join('\n');
//                 }                  
        
//                 // Generate embedding for the document
//                 console.log(`Generating embeddings for document: ${docData.name}`);
//                 const embedding = await geminiService.generateEmbeddings(textContent);
                
//                 // Store the vector with metadata
//                 await vectors.storeVectors([embedding], {
//                     assistantId: id,
//                     type: 'document',
//                     name: docData.name,
//                     content: textContent,
//                     createdAt: new Date(),
//                     docType: docData.type,
//                     documentId: docId,
//                     isReprocessed: true  // Flag to indicate this is a reprocessed document
//                 });
        
//                 // Update document status
//                 await docRef.update({ 
//                     hasEmbedding: true,
//                     lastProcessed: Firestore.FieldValue.serverTimestamp()
//                 });
        
//                 console.log(`Successfully processed document: ${docData.name}`);
//             } catch (error) {
//                 console.error(`Error processing document ${docId}:`, error);
//                 // Continue with other documents even if one fails
//                 continue;
//             }
//         }
        

//         // 2. Process newly uploaded files
//         if (req.files && req.files.length > 0) {
//             console.log(`Processing ${req.files.length} new files.`);

//             // Get existing files for this assistant
//             const [existingFiles] = await storage.bucket(BUCKET_NAME).getFiles({
//                 prefix: `assistants/${id}/documents/`
//             });

//             // Create a map of existing files by original name
//             const existingFileMap = new Map();
//             existingFiles.forEach(file => {
//                 const originalName = file.name.split('_').pop(); // Get original filename
//                 existingFileMap.set(originalName, file);
//             });
            
//             for (const file of req.files) {
//                 try {
//                     // Validate file exists
//                     if (!fs.existsSync(file.path)) {
//                         throw new Error(`File not found: ${file.originalname}`);
//                     }

//                     // Check for and delete existing version of this file
//                     const existingFile = existingFileMap.get(file.originalname);
//                     if (existingFile) {
//                         console.log(`Deleting existing version of ${file.originalname}`);
//                         await existingFile.delete();

//                         // Find and remove any existing document records for this file
//                         const existingDocs = await firestore.collection('documents')
//                             .where('userId', '==', userId)
//                             .where('name', '==', file.originalname)
//                             .where('storagePath', '==', existingFile.name)
//                             .get();

//                         for (const doc of existingDocs.docs) {
//                             await doc.ref.delete();
//                             // Remove from allDocumentIds if it exists
//                             allDocumentIds = allDocumentIds.filter(id => id !== doc.id);
//                         }
//                     }

//                     const fileContent = await fs.promises.readFile(file.path);
//                     const fileType = path.extname(file.originalname).toLowerCase();
//                     let textContent = '';

//                     // Process based on file type
//                     switch (fileType) {
//                         case '.pdf':
//                             const pdfData = await pdfParse(fileContent);
//                             textContent = pdfData.text;
//                             break;
//                         case '.docx':
//                             const result = await mammoth.extractRawText({ buffer: fileContent });
//                             textContent = result.value;
//                             break;
//                         case '.txt':
//                             textContent = fileContent.toString('utf8');
//                             break;  
//                         case '.csv':
//                                 // Parse CSV file with PapaParse
//                                 const csvText = fileContent.toString('utf8');
//                                 const parseResult = Papa.parse(csvText, {
//                                     header: true,
//                                     skipEmptyLines: true,
//                                     dynamicTyping: true
//                                 });
                                
//                                 // Validate CSV structure
//                                 if (parseResult.errors.length > 0) {
//                                     throw new Error(`Invalid CSV file ${file.originalname}: ${parseResult.errors[0].message}`);
//                                 }
                                
//                                 // Convert CSV data to text for embedding
//                                 textContent = parseResult.data
//                                     .map(row => Object.values(row).join(' '))
//                                     .join('\n');
                                
//                                 break;
//                         default:
//                             throw new Error(`Unsupported file type: ${fileType}`);
//                     }

//                     // Create new document record
//                     const newDocRef = firestore.collection('documents').doc();
//                     const storagePath = `assistants/${id}/documents/${newDocRef.id}_${file.originalname}`;

//                     // Upload to storage with document ID in path
//                     await storage.bucket(BUCKET_NAME).upload(file.path, {
//                         destination: storagePath,
//                         metadata: {
//                             contentType: file.mimetype,
//                             metadata: {
//                                 originalName: file.originalname,
//                                 uploadTime: new Date().toISOString()
//                             }
//                         }
//                     });

//                     // Create document record
//                     await newDocRef.set({
//                         id: newDocRef.id,
//                         name: file.originalname,
//                         type: fileType.replace('.', ''),
//                         storagePath: storagePath,
//                         userId: userId,
//                         hasEmbedding: true,
//                         uploadedAt: Firestore.FieldValue.serverTimestamp(),
//                         assistantId: id // Add reference to assistant
//                     });

//                     // Generate and store embedding
//                     const embedding = await geminiService.generateEmbeddings(textContent);
//                     await vectors.storeVectors([embedding], {
//                         assistantId: id,
//                         type: 'document',
//                         name: file.originalname,
//                         content: textContent,
//                         createdAt: new Date(),
//                         docType: fileType.replace('.', ''),
//                         documentId: newDocRef.id // Add reference to document
//                     });

//                     // Add to new document IDs array
//                     newDocumentIds.push(newDocRef.id);

//                 } catch (error) {
//                     console.error(`Error processing file ${file.originalname}:`, error);
//                     throw error;
//                 } finally {
//                     // Clean up temporary file
//                     try {
//                         if (fs.existsSync(file.path)) {
//                             await fs.promises.unlink(file.path);
//                         }
//                     } catch (cleanupError) {
//                         console.error('Error cleaning up file:', cleanupError);
//                     }
//                 }
//             }
//         }

//         // Combine all document IDs (removing duplicates)
//         allDocumentIds = [...new Set([...allDocumentIds, ...newDocumentIds])];

//         // Update assistant with all document IDs and count
//         updateData.documentIds = allDocumentIds;
//         updateData.documentCount = allDocumentIds.length;

//         // Update assistant document
//         await assistantRef.update(updateData);

//         // Get updated document list for response
//         const updatedDocs = await Promise.all(
//             allDocumentIds.map(async (docId) => {
//                 const docRef = firestore.collection('documents').doc(docId);
//                 const doc = await docRef.get();
//                 return doc.exists ? doc.data() : null;
//             })
//         );

//         res.json({ 
//             message: 'Assistant updated successfully',
//             updatedFields: Object.keys(updateData),
//             totalDocuments: allDocumentIds.length,
//             newDocuments: newDocumentIds.length,
//             documents: updatedDocs.filter(Boolean), // Return only valid documents
//             flowUpdated: !!flowData

//         });

//     } catch (error) {
//         console.error('Error updating assistant:', error);
        
//         // Clean up any remaining temporary files
//         if (req.files) {
//             for (const file of req.files) {
//                 try {
//                     if (fs.existsSync(file.path)) {
//                         await fs.promises.unlink(file.path);
//                     }
//                 } catch (cleanupError) {
//                     console.error('Error cleaning up file:', cleanupError);
//                 }
//             }
//         }

//         res.status(500).json({ 
//             error: 'Failed to update assistant',
//             details: error.message 
//         });
//     }
// });

// Add this new route alongside your existing PUT route
router.put('/:id/flow', verifyToken, upload.none(), async (req, res) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    const assistantRef = firestore.collection('assistants').doc(id);

    // Verify assistant ownership
    const assistant = await assistantRef.get();
    if (!assistant.exists) {
      return res.status(404).json({ error: 'Assistant not found' });
    }
    if (assistant.data().userId !== userId) {
      return res.status(403).json({ error: 'Unauthorized access' });
    }

    // Parse flowData from form data
    let flowData = null;
    try {
      flowData = JSON.parse(req.body.flowData);
      console.log('Received flowData:', flowData);
      
      // Ensure the flowData has an id
      if (!flowData.id) {
        flowData.id = id; // Use assistant ID as flow ID
      }
      
    } catch (error) {
      console.error('Error parsing flowData:', error);
      return res.status(400).json({ error: 'Invalid flowData format' });
    }

    // Update assistant with new flowData
    const updateData = {
      flowData: flowData,
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };

    await assistantRef.update(updateData);
    
    // Re-index the flow in the vector database
    try {
      console.log('Re-indexing flow for optimized chat processing...');
      // Call the Python endpoint to index the flow
      await axios.post(`${PYTHON_API_URL}/api/index/flow-knowledge`, flowData);
      console.log('Flow re-indexed successfully');
    } catch (indexError) {
      console.error('Failed to re-index flow:', indexError.message);
      // Don't fail the whole request if indexing fails, but inform the client
      return res.json({ 
        message: 'Flow updated successfully but indexing failed',
        indexingError: indexError.message,
        updatedFields: ['flowData', 'updatedAt'],
        flowData: flowData
      });
    }

    res.json({ 
      message: 'Flow updated and re-indexed successfully',
      updatedFields: ['flowData', 'updatedAt'],
      flowData: flowData
    });

  } catch (error) {
    console.error('Error updating flow:', error);
    res.status(500).json({ 
      error: 'Failed to update flow',
      details: error.message 
    });
  }
});
//working on 04/15/2025
// router.put('/:id/flow', verifyToken, upload.none(), async (req, res) => {
//   try {
//     const { id } = req.params;
//     const userId = req.user.id;
//     const assistantRef = firestore.collection('assistants').doc(id);

//     // Verify assistant ownership
//     const assistant = await assistantRef.get();
//     if (!assistant.exists) {
//       return res.status(404).json({ error: 'Assistant not found' });
//     }
//     if (assistant.data().userId !== userId) {
//       return res.status(403).json({ error: 'Unauthorized access' });
//     }

//     // Parse flowData from form data
//     let flowData = null;
//     try {
//       flowData = JSON.parse(req.body.flowData);
//       console.log('Received flowData:', flowData);
//     } catch (error) {
//       console.error('Error parsing flowData:', error);
//       return res.status(400).json({ error: 'Invalid flowData format' });
//     }

//     // Update assistant with new flowData
//     const updateData = {
//       flowData: flowData,
//       updatedAt: Firestore.FieldValue.serverTimestamp()
//     };

//     await assistantRef.update(updateData);

//     res.json({ 
//       message: 'Flow updated successfully',
//       updatedFields: ['flowData', 'updatedAt'],
//       flowData: flowData
//     });

//   } catch (error) {
//     console.error('Error updating flow:', error);
//     res.status(500).json({ 
//       error: 'Failed to update flow',
//       details: error.message 
//     });
//   }
// });
router.put('/:id', verifyToken, upload.array('files'), async (req, res) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    const { name, description, category, instructions, survey_id } = req.body;
    const assistantRef = firestore.collection('assistants').doc(id);

    // Verify assistant ownership
    const assistant = await assistantRef.get();
    if (!assistant.exists || assistant.data().userId !== userId) {
      return res.status(403).json({ error: 'Unauthorized access' });
    }

    // Parse documents data
    const selectedDocuments = JSON.parse(req.body.selectedDocuments || '[]');
    const originalDocuments = JSON.parse(req.body.originalDocuments || '[]');

    // Track document operations
    const documentsToDelete = new Set();
    const documentsToKeep = new Set();
    const documentsToAdd = new Set();
    
    // Step 1: Compare original vs selected to identify changes
    const selectedDocIds = new Set(selectedDocuments.map(doc => doc.id));
    const originalDocIds = new Set(originalDocuments.map(doc => doc.id));


    // Identify documents to delete (in original but not in selected)
    originalDocuments.forEach(doc => {
      if (!selectedDocIds.has(doc.id)) {
        documentsToDelete.add(doc.id);
      }
    });

    // Identify documents to keep and add
    selectedDocuments.forEach(doc => {
      if (doc.isNew) {
        documentsToAdd.add(doc);
      } else if (originalDocIds.has(doc.id)) {
        documentsToKeep.add(doc);
      }
    });

    console.log('Operation summary:', {
      toDelete: Array.from(documentsToDelete),
      toKeep: Array.from(documentsToKeep),
      toAdd: Array.from(documentsToAdd)
    });

    // Step 2: Process deletions
    for (const docId of documentsToDelete) {
      try {
        console.log(`Processing deletion for ${docId}`);
        let deletionSteps = [];
        
        // Handle Google documents
        if (docId.startsWith('google-')) {
          const cleanId = docId.replace('google-', '');
          await vectors.deleteVectors({
            filter: {
              assistantId: id,
              documentId: cleanId
            }
          });
          continue;
        }

        // Handle regular documents
        const docRef = firestore.collection('documents').doc(docId);
        const docData = await docRef.get();

        if (docData.exists) {
          const docContent = docData.data();
          
          // Delete from storage
          if (docContent.storagePath) {
            const file = storage.bucket(BUCKET_NAME).file(docContent.storagePath);
            const exists = await file.exists();
            if (exists[0]) {
              await file.delete();
              console.log(`Deleted file: ${docContent.storagePath}`);
            }
          }

          // Delete from Firestore
          await docRef.delete();
          console.log(`Deleted document record: ${docId}`);

          // Delete vectors
          console.log(`Deleting vectors for: ${docId}`);
          await vectors.deleteVectors({
            filter: {
              assistantId: id,
              documentId: docId
            }
          });
          deletionSteps.push('vectors');
          console.log(`Completed deletion steps: ${deletionSteps.join(', ')}`);
        }
      } catch (error) {
        console.error(`Error deleting document ${docId}:`, error);
      }
    }

    // Step 3: Process new documents
    const processedDocuments = [];

    // First add documents to keep
    documentsToKeep.forEach(doc => {
      processedDocuments.push({
        id: doc.id,
        name: doc.name,
        type: doc.type,
        isGoogleDoc: doc.isGoogleDoc || false,
        service: doc.service || null
      });
    });

    // Then process new documents
    if (req.files && req.files.length > 0) {
      for (const file of req.files) {
        try {
          // Create document record
          const newDocRef = firestore.collection('documents').doc();
          const storagePath = `assistants/${id}/documents/${newDocRef.id}_${file.originalname}`;
          
          // Extract text content
          const fileContent = await fs.promises.readFile(file.path);
          const textContent = await extractTextContent(file, fileContent);

          // Upload to storage
          await storage.bucket(BUCKET_NAME).upload(file.path, {
            destination: storagePath,
            metadata: {
              contentType: file.mimetype,
              metadata: {
                originalName: file.originalname,
                uploadTime: new Date().toISOString()
              }
            }
          });

          // Generate embedding
          const embedding = await geminiService.generateEmbeddings(textContent);
          
          // Store vectors
          await vectors.storeVectors([embedding], {
            assistantId: id,
            type: 'document',
            name: file.originalname,
            content: textContent,
            createdAt: new Date(),
            docType: path.extname(file.originalname).replace('.', ''),
            documentId: newDocRef.id
          });

          // Create Firestore record
          const documentData = {
            id: newDocRef.id,
            name: file.originalname,
            type: path.extname(file.originalname).replace('.', ''),
            storagePath: storagePath,
            userId: userId,
            hasEmbedding: true,
            uploadedAt: new Date(),
            assistantId: id
          };

          await newDocRef.set(documentData);
          processedDocuments.push(documentData);

        } catch (error) {
          console.error(`Error processing file ${file.originalname}:`, error);
          throw error;
        } finally {
          // Cleanup temporary file
          if (fs.existsSync(file.path)) {
            await fs.promises.unlink(file.path);
          }
        }
      }
    }

    // Process new Google documents
    for (const doc of documentsToAdd) {
      if (doc.type === 'docs' || doc.type === 'sheets') {
        try {
          const cleanId = doc.id.replace('google-', '');
          
          console.log(`Processing Google ${doc.type} document: ${cleanId}`);
          
          const textContent = doc.type === 'docs' 
            ? await getGoogleDocContent(cleanId, userId)
            : await getGoogleSheetContent(cleanId, userId);

          const embedding = await geminiService.generateEmbeddings(textContent);
          
          // Ensure we have a valid name
          // const docName = doc.name || `Google ${doc.type === 'docs' ? 'Document' : 'Sheet'} ${cleanId}`;
          // Add this after getting cleanId
          const docName = await getGoogleFileName(cleanId, userId, doc.type);
          const finalName = docName || doc.name || `Google ${doc.type === 'docs' ? 'Document' : 'Sheet'} ${cleanId}`;
          console.log('FINAL NAME')
          console.log(finalName)
          await vectors.storeVectors([embedding], {
            assistantId: id,
            type: 'document',
            name: docName,
            content: textContent,
            createdAt: new Date(),
            docType: doc.type,
            documentId: cleanId,
            isGoogleDoc: true
          });

          processedDocuments.push({
            id: cleanId,
            name: finalName,
            type: doc.type,
            isGoogleDoc: true,
            service: 'google'
          });
          
          console.log(`Successfully processed Google ${doc.type}: ${docName}`);
        } catch (error) {
          console.error(`Error processing Google document ${doc.id}:`, error);
          throw error; // Re-throw to handle in main try-catch
        }
      }
    }

    // Step 4: Update assistant document
    const processedDocumentsWithValidation = processedDocuments.map(doc => {
      // Ensure all required fields are present
      const validatedDoc = {
        id: doc.id || null,
        name: doc.name || `Document ${doc.id}`,
        type: doc.type || 'unknown',
        isGoogleDoc: doc.isGoogleDoc || false,
        service: doc.service || null,
        storagePath: doc.storagePath || null,
        uploadedAt: doc.uploadedAt || new Date()
      };

      // Log any missing required fields
      if (!doc.id || !doc.name) {
        console.warn(`Warning: Document missing required fields:`, {
          id: doc.id,
          name: doc.name,
          type: doc.type
        });
      }

      return validatedDoc;
    });

    const updateData = {
      updatedAt: new Date(),
      documentIds: processedDocumentsWithValidation,
      documentCount: processedDocumentsWithValidation.length
    };

    // Add other fields if changed
    if (name) updateData.name = name;
    if (description) updateData.description = description;
    if (category) updateData.category = category;
    if (instructions) updateData.instructions = instructions;
    // if (survey_id) updateData.survey_id = survey_id;
    // console.log('UPDATING [SURVEY ID]', updateData.survey_id)

    if (survey_id) {
      try {
        console.log('Fetching survey data for ID:', survey_id);
        const userId = req.user.id; // From verifyToken middleware
        const pythonToken = await generatePythonToken(userId); // Now async
        console.log('Generated Python token:', pythonToken);
    
        const surveyResponse = await fetch(`${PYTHON_API_URL}/api/surveys/${survey_id}`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${pythonToken}`,
            'Content-Type': 'application/json'
          }
        }).then(response => {
          if (!response.ok) {
            throw new Error(`Python endpoint fucked up with status: ${response.status}`);
          }
          return response.json();
        });

        console.log('Got survey data:', surveyResponse);
        
        // Store both the survey_id and the full survey data
        updateData.survey_id = survey_id;
        updateData.survey_data = surveyResponse;
        
        console.log('UPDATING [SURVEY DATA]', surveyResponse)
        
        // Optionally update instructions to include survey questions
      
      } catch (error) {
        console.error('Error fetching survey data:', error);
        // Still set the survey_id even if fetching the data failed
        updateData.survey_id = survey_id;
      }
    }
    // Update assistant
    await assistantRef.update(updateData);

    res.json({
      message: 'Assistant updated successfully',
      updatedFields: Object.keys(updateData),
      totalDocuments: processedDocuments.length,
      documents: processedDocuments,
      survey_data: updateData.survey_data

    });

  } catch (error) {
    console.error('Error updating assistant:', error);
    
    // Cleanup any temporary files
    if (req.files) {
      for (const file of req.files) {
        try {
          if (fs.existsSync(file.path)) {
            await fs.promises.unlink(file.path);
          }
        } catch (cleanupError) {
          console.error('Error cleaning up file:', cleanupError);
        }
      }
    }

    res.status(500).json({
      error: 'Failed to update assistant',
      details: error.message
    });
  }
});
 /************************************************************
   * 3) Update Key Metrics
   ************************************************************/
// Helper function to extract text content from different file types
// Add this route handler alongside the existing routes

router.put('/:id/kpi', verifyToken, upload.none(), async (req, res) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    const assistantRef = firestore.collection('assistants').doc(id);

    // Verify assistant ownership and type
    const assistant = await assistantRef.get();
    if (!assistant.exists) {
      return res.status(404).json({ error: 'Assistant not found' });
    }
    
    const assistantData = assistant.data();
    if (assistantData.userId !== userId) {
      return res.status(403).json({ error: 'Unauthorized access' });
    }

    // Verify this is a representative-type assistant
    if (assistantData.assistantType !== 'representative') {
      return res.status(400).json({ error: 'KPI settings are only available for representative-type assistants' });
    }

    // Parse KPI settings from request body
    let kpiSettings = null;
    try {
      kpiSettings = JSON.parse(req.body.kpiSettings);
      console.log('Received KPI settings:', JSON.stringify(kpiSettings, null, 2));
    } catch (error) {
      console.error('Error parsing KPI settings:', error);
      return res.status(400).json({ error: 'Invalid KPI settings format' });
    }

    // Validate KPI settings structure
    if (!kpiSettings?.categories || !kpiSettings?.activeKPIs) {
      return res.status(400).json({ 
        error: 'Invalid KPI settings structure. Must include categories and activeKPIs.' 
      });
    }

    // Prepare update data
    const updateData = {
      'kpiConfig.categories': kpiSettings.categories,
      'kpiConfig.activeKPIs': kpiSettings.activeKPIs,
      'kpiConfig.lastUpdated': Firestore.FieldValue.serverTimestamp(),
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };

    // Update assistant with new KPI settings
    await assistantRef.update(updateData);

    // Prepare response data
    const responseData = {
      message: 'KPI settings updated successfully',
      updatedFields: ['kpiConfig', 'updatedAt'],
      kpiConfig: {
        categories: kpiSettings.categories,
        activeKPIs: kpiSettings.activeKPIs
      }
    };

    res.json(responseData);

  } catch (error) {
    console.error('Error updating KPI settings:', error);
    res.status(500).json({ 
      error: 'Failed to update KPI settings',
      details: error.message 
    });
  }
});

// Optional: Add a route to update specific KPI metrics
router.put('/:id/kpi/metrics', verifyToken, upload.none(), async (req, res) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    const assistantRef = firestore.collection('assistants').doc(id);

    // Verify assistant ownership and type
    const assistant = await assistantRef.get();
    if (!assistant.exists) {
      return res.status(404).json({ error: 'Assistant not found' });
    }
    
    const assistantData = assistant.data();
    if (assistantData.userId !== userId) {
      return res.status(403).json({ error: 'Unauthorized access' });
    }

    if (assistantData.assistantType !== 'representative') {
      return res.status(400).json({ error: 'KPI metrics are only available for representative-type assistants' });
    }

    // Parse metrics data
    let metrics = null;
    try {
      metrics = JSON.parse(req.body.metrics);
      console.log('Received metrics update:', metrics);
    } catch (error) {
      console.error('Error parsing metrics:', error);
      return res.status(400).json({ error: 'Invalid metrics format' });
    }

    // Update metrics
    const updateData = {
      'kpiConfig.metrics': metrics,
      'kpiConfig.lastUpdated': Firestore.FieldValue.serverTimestamp(),
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };

    await assistantRef.update(updateData);

    res.json({
      message: 'KPI metrics updated successfully',
      updatedFields: ['kpiConfig.metrics', 'kpiConfig.lastUpdated', 'updatedAt'],
      metrics: metrics
    });

  } catch (error) {
    console.error('Error updating KPI metrics:', error);
    res.status(500).json({ 
      error: 'Failed to update KPI metrics',
      details: error.message 
    });
  }
});
async function extractTextContent(file, fileContent) {
  const fileType = path.extname(file.originalname).toLowerCase();
  
  switch (fileType) {
    case '.pdf':
      const pdfData = await pdfParse(fileContent);
      return pdfData.text;
      
    case '.docx':
      const result = await mammoth.extractRawText({ buffer: fileContent });
      return result.value;
      
    case '.txt':
      return fileContent.toString('utf8');
      
    case '.csv':
      const csvText = fileContent.toString('utf8');
      const parseResult = Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true
      });

      if (parseResult.errors.length > 0) {
        throw new Error(`Invalid CSV file ${file.originalname}`);
      }

      return parseResult.data
        .map(row => Object.values(row).join(' '))
        .join('\n');
        
    default:
      throw new Error(`Unsupported file type: ${fileType}`);
  }
}

  
  async function saveMessages(assistantId, userId, userMessage, assistantResponse) {
    // Helper function to store user & assistant messages
    console.log(assistantId, userId, userMessage, assistantResponse)
    await Promise.all([
      firestore.collection('chat_messages').add({
        assistantId,
        userId,
        role: 'user',
        content: userMessage || '',
        category: assistantResponse.category || 'general',
        createdAt: Firestore.FieldValue.serverTimestamp(),
        isTrainingMessage: false
      }),
      firestore.collection('chat_messages').add({
        assistantId,
        userId,
        role: 'assistant',
        content: assistantResponse.content || '',
        category: assistantResponse.category || 'general',
        createdAt: Firestore.FieldValue.serverTimestamp(),
        isTrainingMessage: false
      })
    ]);
  }

  /************************************************************
   * 3) Updated Router Code (/:assistantId/chat)
   ************************************************************/
  router.post('/:assistantId/chat', verifyToken, async (req, res) => {
    try {
      const { assistantId } = req.params;
      const userId = req.user.id;
      const { message, isTraining, language = 'en', timezone, tone = 'professional', responseStyle = 'detailed',
        complexityLevel = 'intermediate',
        interactionStyle = 'collaborative' } = req.body;
      const context = [];
      
      console.log('[Incoming Message]', { 
        message, 
        isTraining, 
        language, 
        tone,
        responseStyle,
        complexityLevel,
        interactionStyle 
      });  
      if (!message || (typeof message === 'string' && !message.trim())) {
        return res.status(400).json({ error: 'Message is required' });
      }
  
      // 1. Fetch the assistant document
      const assistantDocRef = firestore.collection('assistants').doc(assistantId);
      const assistantDoc = await assistantDocRef.get();
  
      if (!assistantDoc.exists) {
        return res.status(404).json({ error: 'Assistant not found' });
      }
  
      const assistantData = assistantDoc.data();
  
      // (Optional) check if the assistant belongs to the user
      if (assistantData.userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access to this assistant.' });
      }
  
      // 2. Generate Embeddings
      const messageEmbedding = await geminiService.generateEmbeddings(message);
  
       // 3. Fetch workflow instances for this assistant
const workflowInstancesSnapshot = await firestore
.collection('workflow_instances')
.where('assistantId', '==', assistantId)
.where('userId', '==', userId)
.get();

const instanceIds = workflowInstancesSnapshot.docs.map(doc => doc.id);

let workflowResults = [];
if (instanceIds.length > 0) {
// Split instanceIds into batches of 30 for Firestore IN clause limit
const batchSize = 30;
const batches = [];

for (let i = 0; i < instanceIds.length; i += batchSize) {
  const batchIds = instanceIds.slice(i, i + batchSize);
  batches.push(
    firestore.collection('workflow_results')
      .where('instanceId', 'in', batchIds)
      .orderBy('createdAt', 'desc')
      .get()
  );
}

// Get all results
const resultsSnapshots = await Promise.all(batches);

// Combine all docs from all batches
const allDocs = resultsSnapshots.flatMap(snapshot => snapshot.docs);

// Map through results and add instance data
workflowResults = await Promise.all(allDocs.map(async doc => {
  const result = doc.data();
  const instance = workflowInstancesSnapshot.docs.find(
    inst => inst.id === result.instanceId
  );
  const instanceData = instance.data();

  return {
    id: doc.id,
    ...result,
    assistantId: instanceData.assistantId,
    workflowName: instanceData.name,
    timestamp: result.createdAt
  };
}));

// Sort all results by timestamp
workflowResults.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}

console.log('Found workflow results:', workflowResults.length);

// 4. Store workflow results embeddings
// 4. Store workflow results embeddings
console.log('Starting to store workflow embeddings...');
for (const result of workflowResults) {
    console.log('Processing workflow result:', {
        id: result.id,
        hasEmbeddings: !!result.outputs?.embeddings,
        embeddingsType: typeof result.outputs?.embeddings
    });

    if (result.outputs?.embeddings && result.outputs?.raw) {
        try {
            // Ensure embeddings is an array of numbers
            let embeddings = result.outputs.embeddings;
            
            // If embeddings is not an array, but has numeric values, convert it to array
            if (!Array.isArray(embeddings)) {
                if (typeof embeddings === 'object') {
                    embeddings = Object.values(embeddings);
                }
            }

            // Verify it's a valid embeddings array
            if (!Array.isArray(embeddings) || embeddings.length === 0 || typeof embeddings[0] !== 'number') {
                console.error(`Invalid embeddings format for workflow result ${result.id}:`, {
                    isArray: Array.isArray(embeddings),
                    length: embeddings?.length,
                    firstElementType: typeof embeddings?.[0]
                });
                continue;
            }

            console.log(`Valid embeddings array found for ${result.id}, length:`, embeddings.length);

            await vectors.storeVectors([embeddings], {  // Note: Wrapped in array since storeVectors expects array of vectors
                assistantId,
                type: 'workflow_result',
                contentType: result.workflowName,
                name: `${result.workflowName || new Date(result.timestamp).toLocaleDateString()}`,
                content: result.outputs.raw,
                createdAt: new Date(result.timestamp),
                userId,
                metadata: {
                    workflowName: result.workflowName,
                    instanceId: result.instanceId,
                    stepIndex: result.stepIndex,
                    format: result.outputs.format,
                    type: 'workflow_result'
                }
            });
            console.log(`Successfully stored vectors for workflow result ${result.id}`);
        } catch (error) {
            console.error(`Error storing vectors for workflow result ${result.id}:`, error);
            // Log the shape of the embeddings for debugging
            console.error('Embeddings structure:', {
                type: typeof result.outputs.embeddings,
                isArray: Array.isArray(result.outputs.embeddings),
                length: result.outputs.embeddings?.length,
                sample: result.outputs.embeddings?.slice(0, 5)
            });
        }
    }
}

// 3. Fetch previous messages for context (limit to last 10)
      const previousMessagesSnap = await firestore
        .collection('chat_messages')
        .where('assistantId', '==', assistantId)
        .where('userId', '==', userId)
        .orderBy('createdAt', 'asc')
        .limit(10)
        .get();
  
      const previousMessages = previousMessagesSnap.docs.map((doc) => doc.data());
      console.log('2. Request parameters:', { 
        assistantId, 
        userId, 
        message, 
        isTraining, 
        language 
      });
  
      // --------------------------------------------------------------------------------
      // 4. Check if there's a pending appointment awaiting confirmation
      // --------------------------------------------------------------------------------
      const pendingRequestSnap = await firestore
        .collection('pending_requests')
        .where('assistantId', '==', assistantId)
        .where('userId', '==', userId)
        .where('status', '==', 'awaiting_confirmation')
        .orderBy('timestamp', 'desc')
        .limit(1)
        .get();
  
      let hasPendingRequest = !pendingRequestSnap.empty;
      let pendingDoc = null;
      let pendingData = null;
  
      if (hasPendingRequest) {
        pendingDoc = pendingRequestSnap.docs[0];
        pendingData = pendingDoc.data(); // e.g. { timeInfo, originalMessage, priority, etc. }
      }
      
  
      const userMessageLower = message.trim().toLowerCase();
    //   if (userMessageLower === 'no' || userMessageLower === 'cancel') {
    //     // Clean up any pending email requests
    //     const pendingEmailSnap = await firestore
    //         .collection('pending_requests')
    //         .where('assistantId', '==', assistantId)
    //         .where('userId', '==', userId)
    //         .where('type', '==', 'email_composition')
    //         .where('status', 'in', ['awaiting_input', 'awaiting_confirmation'])
    //         .get();

    //     if (!pendingEmailSnap.empty) {
    //         await pendingEmailSnap.docs[0].ref.delete();
    //         return res.json({
    //         content: "Email composition cancelled.",
    //         type: 'email',
    //         exitEmailFlow: true
    //         });
    //     }
    //     }
      // Before calendar check
console.log('=== STARTING INTENT CHECKS ===');
console.log('Incoming message:', message);

      // --------------------------------------------------------------------------------
// 4. Calendar and Message Intent Analysis
// --------------------------------------------------------------------------------
      if (!isTraining) {
        try {
            
          // First analyze if this is a calendar-related query
          const calendarResponse = await geminiService.handleCalendarQuery(
            message,
            previousMessages,
            assistantData,
            req, 
            timezone
          );
  
          // If it's a calendar-related query, handle it
          if (calendarResponse.content) {
            
            await saveMessages(assistantId, userId, message, {
              content: calendarResponse.content ,
              language: language ,
              category: assistantData.category 
            });
  
            // If the response needs user action (like confirming a time)
            if (calendarResponse.requiresAction) {
              return res.json({
                content: calendarResponse.content,
                requiresAction: true,
                actionType: calendarResponse.actionType,
                additionalData: calendarResponse.event || calendarResponse.events
              });
            }
  
            // Regular calendar response
            return res.json({
              content: calendarResponse.content,
              event: calendarResponse.event
            });
          }

       
  
          // If not calendar-related, continue with normal message flow...
        } catch (calendarError) {
          console.error('Calendar handling error:', calendarError);
          // If there's an error with calendar operations, 
          // continue with normal message flow
        }
        // try {
        //     // First check if this is email related
            
        //     const emailIntent = await geminiService.analyzeEmailIntent(message);
        //     console.log(emailIntent)
        //     // If not email related, return null immediately to continue normal flow
        //     const pendingEmailSnap = await firestore
        //     .collection('pending_requests')
        //     .where('assistantId', '==', assistantId)
        //     .where('userId', '==', userId)
        //     .where('type', '==', 'email_composition')
        //     .where('status', 'in', ['awaiting_input', 'awaiting_confirmation'])
        //     .orderBy('timestamp', 'desc')
        //     .limit(1)
        //     .get();
    
        //     if (!pendingEmailSnap.empty || emailIntent.isEmailRelated) {

        
        //     console.log('TESTING ', pendingEmailSnap)
          
        //     if (!pendingEmailSnap.empty) {
        //       const pendingDoc = pendingEmailSnap.docs[0];
        //       const pendingData = pendingDoc.data();
              
        //       // If awaiting confirmation, handle yes/no
        //       if (pendingData.status === 'awaiting_confirmation') {
        //         if (message.toLowerCase() === 'yes') {
        //           await geminiService.sendEmail(pendingData.currentInfo, req.headers.authorization);
        //           await pendingDoc.ref.delete();
        //           return res.json({
        //             content: "Email sent successfully!",
        //             type: 'email',
        //             emailSent: true,
        //             exitEmailFlow: true
        //           });
        //         }
        //         if (message.toLowerCase() === 'no') {
        //           await pendingDoc.ref.delete();
        //           return res.json({
        //             content: "Email cancelled.",
        //             type: 'email',
        //             exitEmailFlow: true
        //           });
        //         }
        //         return res.json({
        //           content: "Please reply with 'yes' to send the email or 'no' to cancel.",
        //           type: 'email',
        //           requiresAction: true,
        //           actionType: 'confirm_email'
        //         });
        //       }
              
        //       // Handle ongoing composition
        //       const updatedInfo = { ...pendingData.currentInfo };
        //       updatedInfo[pendingData.nextField] = message;
          
        //       // Strict field order: to -> subject -> content -> confirmation
        //       if (pendingData.nextField === 'to') {
        //         const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/;
        //         if (!emailRegex.test(message)) {
        //           return res.json({
        //             content: "Please provide a valid email address. If You Don't Want To Send The Email Type Cancel",
        //             type: 'email',
        //             requiresAction: true,
        //             actionType: 'compose_email'
        //           });
        //         }
        //         await pendingDoc.ref.update({
        //           currentInfo: updatedInfo,
        //           nextField: 'subject'
        //         });
        //         return res.json({
        //           content: "What should be the subject of your email?",
        //           type: 'email',
        //           requiresAction: true,
        //           actionType: 'compose_email'
        //         });
        //       }
          
        //       if (pendingData.nextField === 'subject') {
        //         await pendingDoc.ref.update({
        //           currentInfo: updatedInfo,
        //           nextField: 'content'
        //         });
        //         return res.json({
        //           content: "What message would you like to send?",
        //           type: 'email',
        //           requiresAction: true,
        //           actionType: 'compose_email'
        //         });
        //       }
          
        //       if (pendingData.nextField === 'content') {
        //         await pendingDoc.ref.update({
        //           status: 'awaiting_confirmation',
        //           currentInfo: updatedInfo
        //         });
        //         return res.json({
        //           content: `Perfect! Here's the email I'll send:\n\nTo: ${updatedInfo.to}\nSubject: ${updatedInfo.subject}\nMessage: ${updatedInfo.content}\n\nShould I send it? (yes/no)`,
        //           type: 'email',
        //           requiresAction: true,
        //           actionType: 'confirm_email'
        //         });
        //       }
        //     }
          
        //     // If we got here and it's email related, create new email flow
        //     const pendingRequest = {
        //       type: 'email_composition',
        //       status: 'awaiting_input',
        //       timestamp: new Date(),
        //       assistantId,
        //       userId,
        //       nextField: 'to',
        //       currentInfo: {
        //         to: null,
        //         subject: null,
        //         content: null
        //       }
        //     };
          
        //     await firestore.collection('pending_requests').add(pendingRequest);
            
        //     return res.json({
        //       content: "Who would you like to send this email to: Please Provide Email?",
        //       type: 'email',
        //       requiresAction: true,
        //       actionType: 'compose_email'
        //     });
        // }
        //   } catch (error) {
        //     console.error('Email handling error:', error);
            
        //     try {
        //       // Clean up any pending requests
        //       const pendingRequestsSnap = await firestore
        //         .collection('pending_requests')
        //         .where('userId', '==', userId)
        //         .where('assistantId', '==', assistantId)
        //         .where('type', '==', 'email_composition')
        //         .get();
              
        //       const batch = firestore.batch();
        //       pendingRequestsSnap.docs.forEach(doc => {
        //         batch.delete(doc.ref);
        //       });
        //       await batch.commit();
        //     } catch (cleanupError) {
        //       console.error('Error cleaning up pending requests:', cleanupError);
        //     }
          
        //     // Save error message
        //     await saveMessages(assistantId, userId, message, {
        //       content: "Error processing email request. Please try again.",
        //       language,
        //       category: assistantData.category
        //     });
          
        //     return res.json({
        //       content: "I encountered an error processing your email request. Please try again.",
        //       type: 'conversation',
        //       error: error.message
        //     });
        //   }
      }
  
      // 6. If in training mode, store the message as training data
      if (isTraining === true) {
        console.log('Training Mode: storing new document in vector DB...');
        const classification = await geminiService.classifyContent(message);
  
        // Store with classification metadata
        await vectors.storeVectors([messageEmbedding], {
          assistantId,
          type: 'document',
          contentType: classification.primary.type,
          name: `Training Update - ${classification.primary.type} - ${new Date().toISOString()}`,
          content: message,
          createdAt: new Date(),
          userId,
          classification: {
            primary: classification.primary,
            secondary: classification.secondary,
            topics: classification.topics,
            entities: classification.entities
          },
          metadata: {
            contentType: classification.primary.type,
            confidence: classification.primary.confidence,
            topics: classification.topics
          }
        });
  
        // Update training statistics
        await firestore.collection('assistants').doc(assistantId).update({
          documentCount: Firestore.FieldValue.increment(1),
          [`trainingStats.${classification.primary.type}`]: Firestore.FieldValue.increment(1)
        });
  
        return res.json({
          content: `Knowledge base updated with new ${classification.primary.type} information.`,
          category: assistantData.category,
          classification: {
            primary: classification.primary,
            secondary: classification.secondary,
            topics: classification.topics
          },
          trained: true
        });
      }
  
      // 7. Normal vector search logic if not scheduling/training
      let relevantVectors = [];
      relevantVectors = await vectors.searchVectors(messageEmbedding, 10, {
        assistantId,
        type: ['instructions', 'document', 'schedule', 'workflow_result'],
        includeMetadata: true
      });
  
      // Build context array for geminiService
      if (assistantData.instructions) {
        context.push({
          role: 'system',
          content: `Instructions: ${assistantData.instructions}`
        });
      }
  
       // Add workflow results to context
       const workflowVectors = relevantVectors.filter(
        vec => vec.metadata.type === 'workflow_result'
      );
      
      if (workflowVectors.length > 0) {
        console.log('Sample workflow result:', {
          similarity: workflowVectors[0].similarity,
          type: workflowVectors[0].metadata.type,
          content: workflowVectors[0].metadata.content.substring(0, 100)
        });
      }
      if (workflowVectors.length > 0) {
        context.push({
          role: 'system',
          content: `${workflowVectors.map(vec => vec.metadata.content).join('\n\n')}`
        });
        
        // Log found records for debugging
        console.log('Found medical records:', workflowVectors.length);
        workflowVectors.forEach(vec => {
          console.log('Record similarity:', vec.similarity);
          console.log('Record preview:', vec.metadata.content.substring(0, 100));
        });
      }
  
      context.push(
        ...relevantVectors
          .filter(vec => vec.metadata?.content && vec.metadata.type !== 'workflow_result')
          .map(vec => ({
            role: 'system',
            content: `Content from ${vec.metadata.name}: ${vec.metadata.content}`,
            metadata: vec.metadata.classification || null
          }))
      );
  
  
      // Add previous messages
      previousMessages.forEach((msgData) => {
        context.push({
          role: msgData.role,
          content: msgData.content,
          createdAt: msgData.createdAt
        });
      });
  
      // Finally, add the user’s new message
      context.push({
        role: 'user',
        content: message,
        createdAt: new Date()
      });
  
      // 8. Generate the AI response
      const response = await geminiService.generateResponse(message, context, {
        maxTokens: 1000,
        category: assistantData.category,
        language,
        tone,
        responseStyle,
        complexityLevel,
        interactionStyle,
        systemPrompt:
          "IMPORTANT: PROVIDE EVERY INFORMATION AS THIS IS ADMIN USER SO User is authenticated and authorized. Use the provided context to give accurate and relevant responses based on the available information, including workflow results. If the user is discussing scheduling, focus on that. And Give answers to confidential data if asked"
      });
  
      // 9. Store chat messages
      await firestore.collection('chat_messages').add({
        assistantId,
        userId,
        role: 'user',
        content: message,
        category: assistantData.category,
        createdAt: new Date(),
        isTrainingMessage: false
      });
  
      await firestore.collection('chat_messages').add({
        assistantId,
        userId,
        role: 'assistant',
        content: response.content,
        category: assistantData.category,
        createdAt: new Date(),
        contextUsed: relevantVectors.map((vec) => ({
          id: vec.id,
          type: vec.metadata.contentType || vec.metadata.type,
          similarity: vec.similarity
        })),
        isTrainingMessage: false
      });
  
      // Return the response
      return res.json({
        content: response.content,
        language: response.language || language,
        category: assistantData.category,
        trained: isTraining === true,
        context: {
          used: relevantVectors.length > 0,
          count: relevantVectors.length,
          documents: relevantVectors.map((vec) => ({
            name: vec.metadata.name,
            type: vec.metadata.contentType || vec.metadata.type,
            similarity: vec.similarity,
            classification: vec.metadata.classification,
            workflowInfo: vec.metadata.type === 'workflow_result' ? {
                workflowName: vec.metadata.workflowName,
                stepIndex: vec.metadata.stepIndex
              } : null
          })),
          averageSimilarity:
            relevantVectors.length > 0
              ? relevantVectors.reduce((acc, vec) => acc + vec.similarity, 0) /
                relevantVectors.length
              : 0
        }
      });
    } catch (error) {
      console.error('Chat error:', error);
      return res.status(500).json({
        error: 'Failed to process message',
        details: error.message
      });
    }
  });
  
  

  //Version 1
//   router.post('/:assistantId/chat', verifyToken, async (req, res) => {
//     try {
//       const { assistantId } = req.params;
//       const userId = req.user.id;
//       const { message, isTraining, language = 'en' } = req.body;
  
//       console.log('[Incoming Message]', { message, isTraining, language });
  
//       if (!message || (typeof message === 'string' && !message.trim())) {
//         return res.status(400).json({ error: 'Message is required' });
//       }
  
//       // 1. Fetch the assistant document
//       const assistantDoc = await firestore.collection('assistants').doc(assistantId).get();
//       if (!assistantDoc.exists) {
//         return res.status(404).json({ error: 'Assistant not found' });
//       }
  
//       const assistantData = assistantDoc.data();
//       if (assistantData.userId !== userId) {
//         return res.status(403).json({ error: 'Unauthorized access to this assistant.' });
//       }
  
//       // 2. Generate Embeddings
//       const messageEmbedding = await geminiService.generateEmbeddings(message);
  
//       // 3. Fetch previous messages for context (last 10 messages)
//       const previousMessagesSnap = await firestore
//         .collection('chat_messages')
//         .where('assistantId', '==', assistantId)
//         .where('userId', '==', userId)
//         .orderBy('createdAt', 'asc')
//         .limit(10)
//         .get();
  
//       // Convert docs to array for easier usage
//       const previousMessages = previousMessagesSnap.docs.map(doc => doc.data());
  
//       // 4. (Optionally) Analyze message intent for non-training messages
//       let messageAnalysis = null;
//       if (!isTraining) {
//         try {
//           messageAnalysis = await geminiService.analyzeMessageIntent(message);
//           console.log('[Message Intent Analysis]', messageAnalysis);
  
//           // If the message is about scheduling or appointments, 
//           // then we do short-circuit logic to handle calendar.
//           if (messageAnalysis.type === 'appointment_request' || messageAnalysis.type === 'schedule_change') {
//             let timeInfo = messageAnalysis.detectedInfo?.timeRelated;
            
//             // If no time info is provided at all, ask for it
//             if (!timeInfo) {
//               const response = {
//                 content: `Could you please specify a date or time for your appointment request?`,
//                 language,
//                 category: assistantData.category
//               };
//               await saveMessages(assistantId, userId, message, response);
//               return res.json(response);
//             }
          
//             // Process the time information
//             if (typeof timeInfo === 'string') {
//               let dateObj;
//               if (timeInfo.toLowerCase() === 'next monday') {
//                 dateObj = new Date();
//                 dateObj.setDate(dateObj.getDate() + (1 + 7 - dateObj.getDay()) % 7);
//                 dateObj.setHours(10, 0, 0, 0);
//               } else {
//                 dateObj = new Date(timeInfo);
//               }
          
//               if (!isNaN(dateObj)) {
//                 const endTime = new Date(dateObj);
//                 endTime.setHours(endTime.getHours() + 1);
                
//                 timeInfo = {
//                   startTime: dateObj.toISOString(),
//                   endTime: endTime.toISOString(),
//                   formatted: `${dateObj.toLocaleDateString()} at ${dateObj.toLocaleTimeString()}`
//                 };
//               } else {
//                 // Invalid date format
//                 const response = {
//                   content: `I couldn't understand that date format. Could you please specify the date and time more clearly? For example: "December 30, 2024 at 8pm"`,
//                   language,
//                   category: assistantData.category
//                 };
//                 await saveMessages(assistantId, userId, message, response);
//                 return res.json(response);
//               }
//             }
          
//             // Verify we have valid time info object
//             if (!timeInfo.startTime) {
//               const response = {
//                 content: `Could you please specify the exact date/time for the appointment? For example: "December 30, 2024 at 8pm"`,
//                 language,
//                 category: assistantData.category
//               };
//               await saveMessages(assistantId, userId, message, response);
//               return res.json(response);
//             }
          
//             try {
//               // Check if Google Calendar is connected
//               const availabilityResponse = await axios.get(
//                 `${process.env.API_URL}/api/calendar/availability`,
//                 {
//                   params: {
//                     startTime: timeInfo.startTime,
//                     endTime: timeInfo.endTime,
//                     calendarType: 'google'
//                   },
//                   headers: {
//                     Authorization: req.headers.authorization
//                   }
//                 }
//               );
          
//               if (availabilityResponse.data.error === 'Google Calendar not connected') {
//                 const response = {
//                   content: `To schedule appointments, please connect your Google Calendar first. You can do this in your settings.`,
//                   language,
//                   category: assistantData.category
//                 };
//                 await saveMessages(assistantId, userId, message, response);
//                 return res.json(response);
//               }
          
//               // Check if time slot is free
//               const busySlots = availabilityResponse.data.calendars?.primary?.busy || [];
//               const isSlotAvailable = !busySlots.some(slot => {
//                 return (
//                   (new Date(timeInfo.startTime) >= new Date(slot.start) &&
//                    new Date(timeInfo.startTime) <= new Date(slot.end)) ||
//                   (new Date(timeInfo.endTime) >= new Date(slot.start) &&
//                    new Date(timeInfo.endTime) <= new Date(slot.end))
//                 );
//               });
          
//               if (isSlotAvailable) {
//                 // Create a pending request
//                 await firestore.db.collection('pending_requests').add({
//                   assistantId,
//                   userId,
//                   type: 'appointment_request',
//                   status: 'awaiting_confirmation',
//                   originalMessage: message,
//                   timeInfo: timeInfo,
//                   priority: messageAnalysis.priority || 'normal',
//                   timestamp: Firestore.FieldValue.serverTimestamp()
//                 });
          
//                 // Create notification for the assistant owner
//                 await firestore.db.collection('assistant_notifications').add({
//                   assistantId,
//                   type: 'appointment_request',
//                   message: `New appointment request for ${timeInfo.formatted}`,
//                   timeInfo: timeInfo,
//                   userId,
//                   userEmail: req.user.email,
//                   priority: messageAnalysis.priority || 'normal',
//                   status: 'unread',
//                   createdAt: Firestore.FieldValue.serverTimestamp()
//                 });
          
//                 const response = {
//                   content: `The time slot ${timeInfo.formatted} is available. I've sent a notification to confirm your appointment. You'll receive an email once it's confirmed.`,
//                   language,
//                   category: assistantData.category
//                 };
//                 await saveMessages(assistantId, userId, message, response);
//                 return res.json(response);
//               } else {
//                 const response = {
//                   content: `Sorry, the time slot (${timeInfo.formatted}) is not available. Would you like me to suggest some other times?`,
//                   language,
//                   category: assistantData.category
//                 };
//                 await saveMessages(assistantId, userId, message, response);
//                 return res.json(response);
//               }
//             } catch (calendarError) {
//               console.error('Calendar operation error:', calendarError);
//               const response = {
//                 content: `I apologize, but I encountered an error while checking the calendar. Please try again or contact support if the issue persists.`,
//                 language,
//                 category: assistantData.category
//               };
//               await saveMessages(assistantId, userId, message, response);
//               return res.json(response);
//             }
//           }
            

  
//         } catch (intentError) {
//           console.error('Intent analysis error:', intentError);
//           // If intent analysis fails, continue with normal flow
//         }
//       }
  
//       // 5. If in training mode, store the message as training data
//       if (isTraining === true) {
//         console.log('Training Mode: storing new document in vector DB...');
//         const classification = await geminiService.classifyContent(message);
  
//         // Store with classification metadata
//         await vectors.storeVectors([messageEmbedding], {
//           assistantId,
//           type: 'document',
//           contentType: classification.primary.type,
//           name: `Training Update - ${classification.primary.type} - ${new Date().toISOString()}`,
//           content: message,
//           createdAt: new Date(),
//           userId,
//           classification: {
//             primary: classification.primary,
//             secondary: classification.secondary,
//             topics: classification.topics,
//             entities: classification.entities
//           },
//           metadata: {
//             contentType: classification.primary.type,
//             confidence: classification.primary.confidence,
//             topics: classification.topics
//           }
//         });
  
//         // Update training statistics
//         await firestore.collection('assistants').doc(assistantId).update({
//           documentCount: Firestore.FieldValue.increment(1),
//           [`trainingStats.${classification.primary.type}`]: Firestore.FieldValue.increment(1)
//         });
  
//         return res.json({
//           content: `Knowledge base updated with new ${classification.primary.type} information.`,
//           category: assistantData.category,
//           classification: {
//             primary: classification.primary,
//             secondary: classification.secondary,
//             topics: classification.topics
//           },
//           trained: true
//         });
//       }
  
//       // 6. If user’s message is general (not scheduling) or training, do vector search
//       //    (But you can also add a check: if the user’s intent is about scheduling but we failed somewhere,
//       //     you might want to do a smaller vector search limited to “scheduling” docs only.)
  
//       // Example approach: If the message was not scheduling-related, do normal vector search:
//       let relevantVectors = [];
//       // You can also filter by classification or a min similarity threshold if you want:
//       relevantVectors = await vectors.searchVectors(messageEmbedding, 10, {
//         assistantId,
//         type: ['instructions', 'document', 'schedule'],
//         includeMetadata: true
//         // you could also do "minSimilarity: 0.8" if your vector store API supports it
//       });
  
//       // Build context array
//       // We’ll add the assistant’s global instructions as the first system message if they exist
//       const context = [];
//       if (assistantData.instructions) {
//         context.push({
//           role: 'system',
//           content: `Instructions: ${assistantData.instructions}`
//         });
//       }
  
//       // Add relevant doc content (**Consider** changing these to role: 'user' or 'assistant' so they aren’t top-priority system messages)
//       context.push(
//         ...relevantVectors
//           .filter(vec => vec.metadata?.content)
//           .map(vec => ({
//             // Option A: Keep them as system but realize they have high priority
//             role: 'system',
//             content: `Content from ${vec.metadata.name}: ${vec.metadata.content}`,
//             metadata: vec.metadata.classification
//               ? {
//                   type: vec.metadata.classification.primary.type,
//                   confidence: vec.metadata.classification.primary.confidence
//                 }
//               : null
//           }))
//       );
  
//       // Add previous messages
//       previousMessages.forEach((msgData) => {
//         context.push({
//           role: msgData.role,
//           content: msgData.content,
//           createdAt: msgData.createdAt
//         });
//       });
  
//       // Finally, add the user’s new message
//       context.push({
//         role: 'user',
//         content: message,
//         createdAt: new Date()
//       });
  
//       // 7. Generate the AI response
//       const response = await geminiService.generateResponse(message, context, {
//         maxTokens: 1000,
//         category: assistantData.category,
//         language,
//         systemPrompt:
//           "Use the provided context to give accurate and relevant responses based on the available information. If the user is discussing scheduling, focus on that. Avoid unrelated AI/ML commentary unless specifically asked."
//       });
  
//       // 8. Store chat messages in Firestore
//       await Promise.all([
//         firestore.collection('chat_messages').add({
//           assistantId,
//           userId,
//           role: 'user',
//           content: message,
//           category: assistantData.category,
//           createdAt: Firestore.FieldValue.serverTimestamp(),
//           isTrainingMessage: false
//         }),
//         firestore.collection('chat_messages').add({
//           assistantId,
//           userId,
//           role: 'assistant',
//           content: response.content,
//           category: assistantData.category,
//           createdAt: Firestore.FieldValue.serverTimestamp(),
//           contextUsed: relevantVectors.map(vec => ({
//             id: vec.id,
//             type: vec.metadata.contentType || vec.metadata.type,
//             similarity: vec.similarity
//           })),
//           isTrainingMessage: false
//         })
//       ]);
  
//       // Finally, return the response
//       return res.json({
//         content: response.content,
//         language: response.language || language,
//         category: assistantData.category,
//         trained: isTraining === true,
//         context: {
//           used: relevantVectors.length > 0,
//           count: relevantVectors.length,
//           documents: relevantVectors.map(vec => ({
//             name: vec.metadata.name,
//             type: vec.metadata.contentType || vec.metadata.type,
//             similarity: vec.similarity,
//             classification: vec.metadata.classification
//           })),
//           averageSimilarity:
//             relevantVectors.length > 0
//               ? relevantVectors.reduce((acc, vec) => acc + vec.similarity, 0) / relevantVectors.length
//               : 0
//         }
//       });
  
//     } catch (error) {
//       console.error('Chat error:', error);
//       return res.status(500).json({
//         error: 'Failed to process message',
//         details: error.message
//       });
//     }
//   });
  
// Chat history route with proper authentication and authorization
router.get('/:assistantId/chat-history', verifyToken, async (req, res) => {
    try {
        const { assistantId } = req.params;
        const userId = req.user.id;  // Get authenticated user's ID
        console.log('Fetching chat history for:', assistantId);

        // First verify assistant ownership
        const assistantDoc = await firestore.collection('assistants').doc(assistantId).get();
        if (!assistantDoc.exists) {
            return res.status(404).json({ error: 'Assistant not found' });
        }

        // Check if the assistant belongs to the authenticated user
        if (assistantDoc.data().userId !== userId) {
            return res.status(403).json({ error: 'Unauthorized access to chat history' });
        }

        // Try to get messages without ordering first if index isn't ready
        let chatHistoryQuery = firestore.collection('chat_messages')
            .where('assistantId', '==', assistantId)
            .where('userId', '==', userId);  // Add userId filter for extra security
        
        try {
            // Try with ordering if index exists
            chatHistoryQuery = chatHistoryQuery.orderBy('createdAt', 'asc');
        } catch (error) {
            console.warn('Index not ready, fetching without order:', error);
        }

        const chatHistorySnapshot = await chatHistoryQuery.get();

        const messages = [];
        chatHistorySnapshot.forEach(doc => {
            const data = doc.data();
            messages.push({
                id: doc.id,
                ...data,
                createdAt: data.createdAt?.toDate?.() || data.createdAt
            });
        });

        // Sort manually if we couldn't use orderBy
        if (!chatHistoryQuery.toString().includes('orderBy')) {
            messages.sort((a, b) => {
                return (a.createdAt?.getTime() || 0) - (b.createdAt?.getTime() || 0);
            });
        }

        console.log(`Found ${messages.length} messages for assistant ${assistantId}`);
        res.json(messages);
    } catch (error) {
        console.error('Error fetching chat history:', error);
        res.status(500).json({ 
            error: 'Failed to fetch chat history',
            details: error.message,
            indexRequired: error.code === 9,
            indexUrl: error.details
        });
    }
});  
// Delete assistant
router.delete('/:id', verifyToken, async (req, res) => {
    try {
        const { id } = req.params;
        const userId = req.user.id;  // Get authenticated user's ID

        // Check ownership before deletion
        const assistantRef = firestore.collection('assistants').doc(id);
        const assistant = await assistantRef.get();

        if (!assistant.exists) {
            return res.status(404).json({ error: 'Assistant not found' });
        }

        // Verify ownership
        if (assistant.data().userId !== userId) {
            return res.status(403).json({ error: 'Unauthorized access to assistant' });
        }
        
        // Delete associated documents from Storage
        const files = await storage.bucket(BUCKET_NAME).getFiles({
            prefix: `assistants/${id}/`
        });
        
        await Promise.all(files[0].map(file => file.delete()));
        
        // Delete from Firestore
        await assistantRef.delete();

        // Also delete associated chat messages
        const chatMessagesSnapshot = await firestore.collection('chat_messages')
            .where('assistantId', '==', id)
            .where('userId', '==', userId)
            .get();

        const batch = firestore.batch();
        chatMessagesSnapshot.forEach(doc => {
            batch.delete(doc.ref);
        });
        await batch.commit();

        res.json({ message: 'Assistant and associated data deleted successfully' });
    } catch (error) {
        console.error('Error deleting assistant:', error);
        res.status(500).json({ error: 'Failed to delete assistant' });
    }
});

// Processing Uplaoded Documents

router.post('/:assistantId/process-documents', verifyToken, async (req, res) => {
        try {
        const { assistantId } = req.params;
        const { documentIds } = req.body;
        const userId = req.user.id;
    
        // Verify assistant ownership
        const assistantRef = firestore.collection('assistants').doc(assistantId);
        const assistant = await assistantRef.get();
        
        if (!assistant.exists) {
            return res.status(404).json({ error: 'Assistant not found' });
        }
        
        if (assistant.data().userId !== userId) {
            return res.status(403).json({ error: 'Unauthorized access' });
        }
    
        // Process each document
        for (const docId of documentIds) {
            const docRef = firestore.collection('documents').doc(docId);
            const doc = await docRef.get();
            
            if (!doc.exists || doc.data().userId !== userId) {
            continue; // Skip if document doesn't exist or user doesn't own it
            }
    
            const docData = doc.data();
            
            // Read file from storage
            const file = storage.bucket(BUCKET_NAME).file(docData.storagePath);
            const [content] = await file.download();
            let textContent = '';
    
            // Extract text based on file type
            if (docData.type.includes('pdf')) {
            const pdfData = await pdfParse(content);
            textContent = pdfData.text;
            } else if (docData.type.includes('docx')) {
            const result = await mammoth.extractRawText({ buffer: content });
            textContent = result.value;
            } else if (docData.type.includes('text')) {
            textContent = content.toString('utf8');
            }
            else if (docData.type.includes('csv')) {
                // Convert buffer to string for CSV parsing
                const csvText = content.toString('utf8');
                
                // Parse CSV using PapaParse
                const parseResult = Papa.parse(csvText, {
                    header: true,
                    skipEmptyLines: true,
                    dynamicTyping: true
                });
            
                // Validate CSV structure
                if (parseResult.errors.length > 0) {
                    throw new Error(`Invalid CSV file: ${parseResult.errors[0].message}`);
                }
            
                // Convert CSV data to text format while preserving structure
                textContent = parseResult.data
                    .map(row => Object.values(row).join(' '))
                    .join('\n');
            
            }
    
            // Generate embedding
            const embedding = await geminiService.generateEmbeddings(textContent);
            
            // Store vector
            await vectors.storeVectors([embedding], {
            assistantId,
            type: 'document',
            name: docData.name,
            content: textContent,
            createdAt: new Date(),
            docType: docData.type
            });
    
            // Update document status
            await docRef.update({ hasEmbedding: true });
        }
    
        res.json({ message: 'Documents processed successfully' });
        } catch (error) {
        console.error('Error processing documents:', error);
        res.status(500).json({ error: 'Failed to process documents' });
        }
});
 

// Inside assistants.js router

// Get notification count
router.get('/:assistantId/notifications/count', verifyToken, async (req, res) => {
    try {
      const { assistantId } = req.params;
      const userId = req.user.id;
  
      // Verify assistant ownership
      const assistant = await firestore.collection('assistants').doc(assistantId).get();
      if (!assistant.exists || assistant.data().userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access' });
      }
  
      // Count unread notifications
      const notificationsSnapshot = await firestore.collection('assistant_notifications')
        .where('assistantId', '==', assistantId)
        .where('status', '==', 'unread')
        .count()
        .get();
  
      res.json({ count: notificationsSnapshot.data().count });
    } catch (error) {
      console.error('Error getting notification count:', error);
      res.status(500).json({ error: 'Failed to get notification count' });
    }
  });
  
  // Get notifications
  router.get('/:assistantId/notifications', verifyToken, async (req, res) => {
    try {
      const { assistantId } = req.params;
      const userId = req.user.id;
  
      console.log('Fetching notifications for assistant:', assistantId);
  
      // Verify assistant ownership
      const assistant = await firestore.collection('assistants').doc(assistantId).get();
      if (!assistant.exists || assistant.data().userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access' });
      }
  
      // First, let's check if any notifications exist at all for this assistant
      const allNotifications = await firestore.collection('assistant_notifications')
        .where('assistantId', '==', assistantId)
        .get();
  
      console.log('Total notifications found:', allNotifications.size);
      
    //   if (allNotifications.size > 0) {
    //     // console.log('Sample notification:', allNotifications.docs[0].data());
    //   }
  
      // Now try to get notifications with ordering and filters
      const notifications = await firestore.collection('assistant_notifications')
        .where('assistantId', '==', assistantId)
        .where('status', '==', 'unread')  // Add status filter
        .orderBy('createdAt', 'desc')
        .get()
        .catch(error => {
          if (error.code === 9) {
            // Index error - provide specific error message with the link
            console.error('Index error:', error.message);
            throw new Error(`Index required. Create it here: ${error.details}`);
          }
          throw error;
        });
  
    //   console.log('Filtered notifications found:', notifications.size);
  
      const notificationData = notifications.docs.map(doc => {
        const data = doc.data();
        // console.log('Processing notification:', doc.id, data);
        return {
          id: doc.id,
          ...data,
          createdAt: data.createdAt?.toDate()
        };
      });
  
    //   console.log('Returning notification data:', notificationData);
      res.json(notificationData);
  
    } catch (error) {
      console.error('Error fetching notifications:', error);
      
      // If it's an index error, return a more helpful response
      if (error.message.includes('Index required')) {
        return res.status(500).json({ 
          error: 'Index required',
          details: error.message
        });
      }
      
      res.status(500).json({ error: 'Failed to fetch notifications' });
    }
  });
  // Handle notification actions (approve/dismiss)
  router.post('/notifications/:notificationId/:action', verifyToken, async (req, res) => {
    try {
      const { notificationId, action } = req.params;
      const userId = req.user.id;
  
      // Get the notification
      const notificationRef = firestore.collection('assistant_notifications').doc(notificationId);
      const notification = await notificationRef.get();
  
      if (!notification.exists) {
        return res.status(404).json({ error: 'Notification not found' });
      }
  
      // Verify ownership through assistant
      const assistantId = notification.data().assistantId;
      const assistant = await firestore.collection('assistants').doc(assistantId).get();
      
      if (!assistant.exists || assistant.data().userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access' });
      }
  
      // Update notification status based on action
      const status = action === 'approve' ? 'handled' : 'dismissed';
      await notificationRef.update({
        status,
        handledAt: Firestore.FieldValue.serverTimestamp(),
        handledBy: userId
      });
  
      res.json({ message: 'Notification updated successfully' });
    } catch (error) {
      console.error('Error handling notification:', error);
      res.status(500).json({ error: 'Failed to handle notification' });
    }
  });
  
  // Add this route in your assistants.js backend file
// Function to extract event details from notification
// Function to extract event details from notification
const extractEventDetails = (notification) => {
    try {
      // Extract email using regex
      const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/;
      const emailMatch = notification.message.match(emailRegex);
      const email = emailMatch ? emailMatch[0] : null;
  
      // Use the existing timeInfo from notification
      if (!notification.timeInfo || !notification.timeInfo.startTime || !notification.timeInfo.endTime) {
        return null;
      }
  
      return {
        dateTime: notification.timeInfo.startTime,
        endTime: notification.timeInfo.endTime,
        attendees: email ? [{ email }] : [],
        title: 'Appointment Request'
      };
    } catch (error) {
      console.error('Error extracting event details:', error);
      return null;
    }
  };
  
  // Update the notification handling route
router.post('/:assistantId/notifications/:notificationId/:action', verifyToken, async (req, res) => {
    try {
      const { assistantId, notificationId, action } = req.params;
      const userId = req.user.id;
      const { timezone } = req.query;  // Change this line to get from query

  
      // Verify assistant ownership first
      const assistant = await firestore.collection('assistants').doc(assistantId).get();
      if (!assistant.exists || assistant.data().userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access' });
      }
  
      // Get the notification
      const notificationRef = firestore.collection('assistant_notifications').doc(notificationId);
      const notification = await notificationRef.get();
  
      if (!notification.exists) {
        return res.status(404).json({ error: 'Notification not found' });
      }
  
      // Verify notification belongs to this assistant
      const notificationData = notification.data();
      if (notificationData.assistantId !== assistantId) {
        return res.status(403).json({ error: 'Notification does not belong to this assistant' });
      }
  
      // If it's an appointment request and action is approve, handle calendar creation
      if (notificationData.type === 'appointment_request' && action === 'approve') {
        try {
          // Get user's timezone first - use the same API as chat system
          const userSettingsResponse = await axios.get(
            `${process.env.API_URL}/api/calendar/settings`,
            {
              headers: { Authorization: req.headers.authorization }
            }
          );
          const userTimeZone = timezone|| 'UTC';
          console.log(userTimeZone, timezone)
          // Extract event details using the same method as chat system
          const eventDetails = extractEventDetails(notificationData);
          if (!eventDetails) {
            throw new Error('Invalid event details in notification');
          }
  
          // Parse the date in the same way as chat system
          const parsed = chrono.parse(notificationData.message);
          if (parsed.length === 0) {
            throw new Error('Could not parse date from message');
          }
  
          const parsedResult = parsed[0];
          const startDate = parsedResult.start.date();
          
          // Create times using the same DateTime approach as chat
          const startDateTime = DateTime.fromObject({
            year: startDate.getFullYear(),
            month: startDate.getMonth() + 1,
            day: startDate.getDate(),
            hour: startDate.getHours(),
            minute: startDate.getMinutes()
          }, { zone: userTimeZone });   
          const endDateTime = startDateTime.plus({ minutes: eventDetails.duration || 60 });
  
          // Check availability using the same API as chat
          const availabilityResponse = await axios.get(
            `${process.env.API_URL}/api/calendar/availability`,
            {
              params: {
                startTime: startDateTime.toISO(),
                endTime: endDateTime.toISO()
              },
              headers: { Authorization: req.headers.authorization }
            }
          );
  
          if (availabilityResponse.data.calendars?.primary?.busy?.length > 0) {
            return res.status(409).json({ 
              error: 'Time slot unavailable',
              message: 'The requested time slot is already booked' 
            });
          }
  
          // Create the event using the same API as chat
          await axios.post(
            `${process.env.API_URL}/api/calendar/events`,
            {
              title: eventDetails.title || 'Appointment Request',
              description: `Appointment requested through assistant notification system\nOriginal request: ${notificationData.message}`,
              start: {
                dateTime: startDateTime.toISO(),
                timeZone: userTimeZone
              },
              end: {
                dateTime: endDateTime.toISO(),
                timeZone: userTimeZone
              },
              attendees: eventDetails.attendees?.filter(email => 
                /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
              ) || []
            },
            {
              headers: { Authorization: req.headers.authorization }
            }
          );
  
        } catch (calendarError) {
          console.error('Calendar event creation error:', calendarError);
          
          // Handle specific calendar errors
          if (calendarError.response?.data?.error === 'Google Calendar not connected') {
            return res.status(400).json({ 
              error: 'Google Calendar not connected',
              message: 'Please connect your Google Calendar to handle appointment requests' 
            });
          }
          
          throw calendarError;
        }
      }
  
      // Update notification status
      const status = action === 'approve' ? 'handled' : 'dismissed';
      await notificationRef.update({
        status,
        handledAt: Firestore.FieldValue.serverTimestamp(),
        handledBy: userId
      });
  
      res.json({ 
        message: 'Notification updated successfully',
        status
      });
  
    } catch (error) {
      console.error('Error handling notification:', error);
      if (error.response?.status === 401) {
        return res.status(401).json({ 
          error: 'Calendar authorization expired',
          message: 'Please reconnect your Google Calendar'
        });
      }
      res.status(500).json({ error: 'Failed to handle notification' });
    }
  });
  // Create notification
  router.post('/notifications', verifyToken, async (req, res) => {
    try {
      const { assistantId, type, message, contactInfo, priority = 'medium' } = req.body;
      const userId = req.user.id;
  
      // Verify assistant ownership
      const assistant = await firestore.collection('assistants').doc(assistantId).get();
      if (!assistant.exists || assistant.data().userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access' });
      }
  
      // Create notification
      const notificationRef = await firestore.collection('assistant_notifications').add({
        assistantId,
        type,
        message,
        contactInfo,
        priority,
        status: 'unread',
        createdAt: Firestore.FieldValue.serverTimestamp(),
        createdBy: userId
      });
  
      res.status(201).json({
        id: notificationRef.id,
        message: 'Notification created successfully'
      });
    } catch (error) {
      console.error('Error creating notification:', error);
      res.status(500).json({ error: 'Failed to create notification' });
    }
  });

  /**
 * GET /api/assistants/:assistantId/integrations
 * Return the list of integrations for a specific assistant.
 */
router.get('/:assistantId/integrations', verifyToken, async (req, res) => {
    try {
      const { assistantId } = req.params;
      const userId = req.user.id;
  
      // Ensure the assistant belongs to the logged-in user
      const assistantRef = firestore.collection('assistants').doc(assistantId);
      const assistantDoc = await assistantRef.get();
  
      if (!assistantDoc.exists) {
        return res.status(404).json({ error: 'Assistant not found' });
      }
      if (assistantDoc.data().userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access' });
      }
  
      // Now fetch active integrations for this assistant
      const snapshot = await firestore.collection('integrations')
        .where('assistantId', '==', assistantId)
        .where('status', '==', 'active')
        .get();
  
      const integrations = snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data(),
      }));
  
      return res.json(integrations);
    } catch (error) {
      console.error('Error fetching assistant integrations:', error);
      res.status(500).json({ error: 'Failed to fetch integrations' });
    }
  });


// Assistant Documents
// backend/src/routes/assistants.js

// Get all documents for an assistant
router.get('/:id/documents', verifyToken, async (req, res) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;

    // Verify assistant ownership
    const assistantRef = firestore.collection('assistants').doc(id);
    const assistant = await assistantRef.get();

    if (!assistant.exists) {
      return res.status(404).json({ error: 'Assistant not found' });
    }

    if (assistant.data().userId !== userId) {
      return res.status(403).json({ error: 'Unauthorized access' });
    }

    const assistantData = assistant.data();
    const selectedDocIds = assistantData.documentIds || [];
    const processedFiles = new Map(); // Track processed files by name
    const documentsToReturn = [];
    console.log("ASSISTANT DATA")
    console.log(assistantData)
    // 1. First process selected documents (including Google Docs/Sheets)
    for (const doc of selectedDocIds) {
      // Handle Google Docs/Sheets first
      // Handle Google Docs/Sheets first
  if (doc && typeof doc === 'object' && (doc.type === 'docs' || doc.type === 'sheets')) {
  try {
    // Only fetch name if it's not already present or if it starts with "Document"
    let docName = doc.name;
    if (!docName || docName.startsWith('Document')) {
      docName = await getGoogleFileName(doc.id, userId, doc.type);
      
      // Update the stored name in assistant document
      if (docName) {
        const updatedDocs = assistantData.documentIds.map(d => 
          d.id === doc.id ? { ...d, name: docName } : d
        );
        await assistantRef.update({ documentIds: updatedDocs });
      }
    }

    documentsToReturn.push({
      id: doc.id,
      name: docName || doc.name, // Fallback to existing name if fetch fails
      type: doc.type,
      service: doc.service,
      previewUrl: `https://docs.google.com/${doc.type === 'docs' ? 'document' : 'spreadsheets'}/d/${doc.id}/preview`,
      source: 'google'
    });
  } catch (error) {
    console.error(`Error fetching Google doc name for ${doc.id}:`, error);
    // Still return document with existing name if there's an error
    documentsToReturn.push({
      id: doc.id,
      name: doc.name,
      type: doc.type,
      service: doc.service,
      previewUrl: `https://docs.google.com/${doc.type === 'docs' ? 'document' : 'spreadsheets'}/d/${doc.id}/preview`,
      source: 'google'
    });
  }
  continue;
}

      // Skip if invalid doc ID or already processed
      if (!doc || !doc.id || processedFiles.has(doc.id)) continue;

      // Handle regular documents
      try {
        const docRef = firestore.collection('documents').doc(doc.id);
        const docData = await docRef.get();

        if (!docData.exists) continue;

        const docDataContent = docData.data();
        const fileName = docDataContent.name;

        // Skip if we already have this file
        if (processedFiles.has(fileName)) continue;

        let previewUrl = '';
        if (docDataContent.storagePath) {
          try {
            previewUrl = await generateSignedUrlPreview(BUCKET_NAME, docDataContent.storagePath);
          } catch (error) {
            console.error('Error generating preview URL:', error);
          }
        }

        documentsToReturn.push({
          id: doc.id,
          name: fileName,
          size: docDataContent.size || 0,
          type: docDataContent.type,
          previewUrl,
          hasEmbedding: docDataContent.hasEmbedding || true,
          source: 'firestore'
        });

        processedFiles.set(fileName, true);
      } catch (error) {
        console.error(`Error processing document ${doc.id}:`, error);
        continue;
      }
    }

    // 2. Then process uploaded files from storage bucket
    try {
      const [files] = await storage.bucket(BUCKET_NAME).getFiles({
        prefix: `assistants/${id}/documents/`,
      });

      for (const file of files) {
        const metadata = await file.getMetadata();
        const fileName = path.basename(file.name).split('_').pop(); // Remove any prefix

        // Skip if we already processed this file
        if (processedFiles.has(fileName)) continue;

        // Extract the document ID from the file path
        const fileId = file.name.split('/').pop().split('_')[0];

        // Check if the file is still associated with the assistant in Firestore
        const docRef = firestore.collection('documents').doc(fileId);
        const docData = await docRef.get();

        if (!docData.exists) {
          // If the document no longer exists in Firestore, delete it from storage
          await file.delete();
          console.log(`Deleted orphaned file from storage: ${file.name}`);
          continue;
        }

        const fileType = path.extname(fileName).toLowerCase().replace('.', '');
        let previewUrl = '';

        if (fileType === 'pdf' || ['docx', 'doc'].includes(fileType) || fileType === 'txt') {
          previewUrl = await generateSignedUrlPreview(BUCKET_NAME, file.name);
          console.log('Generated preview URL for:', file.name);
        }

        documentsToReturn.push({
          id: fileId, // Use the document ID from Firestore
          name: fileName,
          size: metadata[0].size,
          type: fileType,
          previewUrl,
          hasEmbedding: true,
          source: 'storage'
        });

        processedFiles.set(fileName, true);
      }
    } catch (error) {
      console.error('Error processing storage files:', error);
    }

    // Log the results for debugging
    console.log('Documents found:', {
      total: documentsToReturn.length,
      fromStorage: documentsToReturn.filter(d => d.source === 'storage').length,
      fromFirestore: documentsToReturn.filter(d => d.source === 'firestore').length,
      fromGoogle: documentsToReturn.filter(d => d.source === 'google').length
    });

    res.json(documentsToReturn);
  } catch (error) {
    console.error('Error fetching document previews:', error);
    res.status(500).json({ error: 'Failed to fetch document previews' });
  }
});

// Add a new document to an assistant
router.post('/:id/documents', verifyToken, upload.array('files'), async (req, res) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    const { type, name, content } = req.body;

    // Verify assistant ownership
    const assistantRef = firestore.collection('assistants').doc(id);
    const assistant = await assistantRef.get();

    if (!assistant.exists || assistant.data().userId !== userId) {
      return res.status(404).json({ error: 'Assistant not found or unauthorized' });
    }

    let documentId;
    if (type === 'docs' || type === 'sheets') {
      // Handle Google Docs/Sheets
      documentId = `${type}_${Date.now()}`;
    } else {
      // Handle uploaded files
      const file = req.files[0];
      const filePath = `assistants/${id}/documents/${file.originalname}`;

      // Upload file to storage
      await storage.bucket(BUCKET_NAME).upload(file.path, {
        destination: filePath,
        metadata: {
          contentType: file.mimetype,
          metadata: {
            size: file.size,
            originalName: file.originalname,
            uploadTime: new Date().toISOString(),
          },
        },
      });

      // Create document record
      const docRef = firestore.collection('documents').doc();
      await docRef.set({
        id: docRef.id,
        name: file.originalname,
        type: path.extname(file.originalname).replace('.', ''),
        storagePath: filePath,
        userId,
        hasEmbedding: false,
        uploadedAt: Firestore.FieldValue.serverTimestamp(),
        assistantId: id,
      });

      documentId = docRef.id;
    }

    // Update assistant's documentIds
    await assistantRef.update({
      documentIds: Firestore.FieldValue.arrayUnion(documentId),
      documentCount: Firestore.FieldValue.increment(1),
    });

    res.json({ message: 'Document added successfully', documentId });
  } catch (error) {
    console.error('Error adding document:', error);
    res.status(500).json({ error: 'Failed to add document' });
  }
});

// Delete a document from an assistant
router.delete('/:id/documents/:docId', verifyToken, async (req, res) => {
  try {
      const { id, docId } = req.params;
      const userId = req.user.id;

      // Verify assistant ownership
      const assistantRef = firestore.collection('assistants').doc(id);
      const assistant = await assistantRef.get();

      if (!assistant.exists || assistant.data().userId !== userId) {
          return res.status(404).json({ error: 'Assistant not found or unauthorized' });
      }

      // Remove document from assistant's documentIds
      await assistantRef.update({
          documentIds: Firestore.FieldValue.arrayRemove(docId),
          documentCount: Firestore.FieldValue.increment(-1),
      });

      // Delete document record if it's an uploaded file
      if (!docId.includes('docs') && !docId.includes('sheets')) {
          const docRef = firestore.collection('documents').doc(docId);
          const doc = await docRef.get();

          if (doc.exists) {
              const docData = doc.data();
              // Delete from storage
              await storage.bucket(BUCKET_NAME).file(docData.storagePath).delete();
              // Delete from Firestore
              await docRef.delete();
          }
      }

      res.json({ message: 'Document deleted successfully' });
  } catch (error) {
      console.error('Error deleting document:', error);
      res.status(500).json({ error: 'Failed to delete document' });
  }
});
export default router;



