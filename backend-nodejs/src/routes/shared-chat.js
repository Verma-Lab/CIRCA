// backend/src/routes/shared-chat.js
import express from 'express';
import { validateSharedAccess } from '../middleware/validateShared.js';
import firestore from '../services/db/firestore.js';
import geminiService from '../services/ai/gemini.js';
import vectors from '../services/storage/vectors.js';
import { Firestore } from '@google-cloud/firestore';
import axios from 'axios';
import * as chrono from 'chrono-node';
import { google } from 'googleapis';
import FlowProcessor from '../services/ai/flowProcessor.js';
import EnhancedFlowProcessor from '../services/ai/EnhancedFlowProcessor.js';
import streamTextToSpeech from '../utils/tts.js'; // Import the TTS utility
import textToSpeech from '@google-cloud/text-to-speech';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { verifyToken } from '../middleware/auth.js';  // Adjust path as needed
import jwt from 'jsonwebtoken';
import {TwilioService} from '../utils/twilioService.js';
import { v4 as uuidv4 } from 'uuid';

// const PYTHON_API_URL = "http://localhost:8000"
const PYTHON_API_URL = "https://app.homosapieus.com"
// const PYTHON_API_URL = "https://0139-2601-47-4a82-47f0-c925-8a6c-e19e-e217.ngrok-free.app"
const PYTHON_SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7";

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
const client = new textToSpeech.TextToSpeechClient();

const oauth2Client = new google.auth.OAuth2(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
  process.env.GOOGLE_REDIRECT_URI
);
const gemini = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY);

import { ContextProcessor } from '../utils/contextProcessor.js';
const router = express.Router();

// async function generateEmbedding(gemini, text) {
//   try {
//     console.log(text)
//     const embeddingModel = gemini.getGenerativeModel({ model: "embedding-001" });
//     const result = await embeddingModel.embedContent(text);
//     console.log("Genearted Embeddings", result)
//     return result.embedding;
//   } catch (error) {
//     console.error('Error generating embedding:', error);
//     return null;
//   }
// }
// async function storeEmbeddingInBackground(firestore, sessionId, userId, content, role) {
//   try {
//     const embedding = await generateEmbedding(gemini, content);
//     console.log('Generating Embeddings')
//     console.log(embedding, content)
//     if (embedding) {
//       await firestore.db.collection('shared_chat_embeddings').add({
//         sessionId,
//         userId, 
//         content,
//         role,
//         embedding,
//         createdAt: new Date()
//       });
//     }
//   } catch (error) {
//     console.error('Error storing embedding:', error);
//   }
// }
async function generateEmbedding(gemini, text) {
  try {
    // Handle case where text is an object with content property
    if (typeof text === 'object' && text !== null && text.content) {
      text = text.content;
    }
    
    // Ensure text is a valid string
    if (!text || typeof text !== 'string') {
      console.log('Invalid content for embedding:', text);
      return null;
    }

    console.log("Sending to embedding API:", text);
    const embeddingModel = gemini.getGenerativeModel({ model: "embedding-001" });
    const result = await embeddingModel.embedContent(text);
    // console.log("Generated Embeddings", result);
    return result.embedding;
  } catch (error) {
    console.error('Error generating embedding:', error);
    return null;
  }
}

async function storeEmbeddingInBackground(firestore, sessionId, userId, content, role) {
  try {
    console.log('Generating Embeddings');
    const embedding = await generateEmbedding(gemini, content);
    console.log(embedding, content);
    
    if (embedding) {
      // Store the content as string if it was an object
      const contentToStore = typeof content === 'object' && content.content 
        ? content.content 
        : content;
        
      await firestore.db.collection('shared_chat_embeddings').add({
        sessionId,
        userId, 
        content: contentToStore,
        role,
        embedding,
        createdAt: new Date()
      });
    }
  } catch (error) {
    console.error('Error storing embedding:', error);
  }
}
// Handle chat messages through shared link
// router.post('/shared/:shareId/chat', validateSharedAccess, async (req, res) => {
//   try {
//       const { shareId } = req.params;
//       const { message, sessionId } = req.body;
//       const shareData = req.shareData;

//       if (!message?.trim()) {
//           return res.status(400).json({ error: 'Message is required' });
//       }

//       if (!sessionId) {
//           return res.status(400).json({ error: 'Session ID is required' });
//       }

//       // Get assistant data using the firestore service
//       const assistant = await firestore.getAssistant(shareData.assistantId);
//       if (!assistant) {
//           return res.status(404).json({ error: 'Assistant not found' });
//       }

//       // Generate embedding for semantic search
//       const messageEmbedding = await geminiService.generateEmbeddings(message);

//       // Search for relevant context from the vector store - including all document types
//       const relevantVectors = await vectors.searchVectors(messageEmbedding, 5, {
//           assistantId: shareData.assistantId,
//           type: ['instructions', 'document'],  // 'document' type includes all classified content
//           includeMetadata: true
//       });

//       // Build the context array for the AI response
//       const context = [];
      
//       // Add base instructions if they exist
//       if (assistant.instructions) {
//           context.push({
//               role: 'system',
//               content: `Instructions: ${assistant.instructions}`
//           });
//       }

//       // Add relevant document content to context with type information
//       relevantVectors.forEach((vec) => {
//           if (vec.metadata?.content) {
//               let contentType = vec.metadata.contentType || vec.metadata.type || 'Document';
//               contentType = contentType.charAt(0).toUpperCase() + contentType.slice(1);

//               context.push({
//                   role: 'system',
//                   content: `${contentType} content from ${vec.metadata.name}: ${vec.metadata.content}`,
//                   metadata: vec.metadata.classification ? {
//                       type: vec.metadata.classification.primary.type,
//                       confidence: vec.metadata.classification.primary.confidence
//                   } : null
//               });
//           }
//       });

//       // Add the user's message to context
//       context.push({
//           role: 'user',
//           content: message,
//       });

//       // Generate AI response with enhanced context
//       const response = await geminiService.generateResponse(message, context, {
//           maxTokens: 1000,
//           category: assistant.category,
//           systemPrompt: "Use the provided context to give accurate and relevant responses based on the available information."
//       });

//       // Use the firestore service to save both messages in a transaction
//       await firestore.runTransaction(async (transaction) => {
//           // Save user message
//           const savedUserMessage = await firestore.saveSharedChatMessage({
//               shareId,
//               sessionId,
//               assistantId: shareData.assistantId,
//               role: 'user',
//               content: message,
//               createdAt: new Date()
//           });

//           // Save assistant message with enhanced context information
//           const savedAssistantMessage = await firestore.saveSharedChatMessage({
//               shareId,
//               assistantId: shareData.assistantId,
//               role: 'assistant',
//               sessionId,
//               content: response.content,
//               createdAt: new Date(),
//               contextUsed: relevantVectors.map(vec => ({
//                   id: vec.id,
//                   type: vec.metadata.contentType || vec.metadata.type,
//                   similarity: vec.similarity,
//                   classification: vec.metadata.classification
//               }))
//           });

//           return {
//               userMessage: savedUserMessage,
//               assistantMessage: savedAssistantMessage
//           };
//       });

//       // Send enhanced response back to client
//       res.json({
//           content: response.content,
//           context: {
//               used: relevantVectors.length > 0,
//               count: relevantVectors.length,
//               documents: relevantVectors.map(vec => ({
//                   name: vec.metadata.name,
//                   type: vec.metadata.contentType || vec.metadata.type,
//                   similarity: vec.similarity,
//                   classification: vec.metadata.classification,
//                   topics: vec.metadata.classification?.topics || []
//               })),
//               averageSimilarity: relevantVectors.length > 0
//                   ? relevantVectors.reduce((acc, vec) => acc + vec.similarity, 0) / relevantVectors.length
//                   : 0
//           }
//       });

//   } catch (error) {
//       console.error('Shared chat error:', error);
//       res.status(500).json({
//           error: 'Failed to process message',
//           details: error.message
//       });
//   }
// });

// router.post('/shared/:shareId/chat', validateSharedAccess, async (req, res) => {
//   try {
//     const { shareId } = req.params;
//     const { message, sessionId, language = 'en' } = req.body;
//     const shareData = req.shareData;
//     const previousMessages = await firestore.getSharedChatHistory(shareId, sessionId);

//     if (!message?.trim()) {
//       return res.status(400).json({ error: 'Message is required' });
//     }

//     if (!sessionId) {
//       return res.status(400).json({ error: 'Session ID is required' });
//     }

//     // Get assistant data
//     const assistant = await firestore.getAssistant(shareData.assistantId);
//     if (!assistant) {
//       return res.status(404).json({ error: 'Assistant not found' });
//     }

//     // Check for pending requests first
//     const pendingRequest = await firestore.db.collection('pending_requests')
//       .where('shareId', '==', shareId)
//       .where('status', 'in', ['awaiting_datetime', 'awaiting_contact'])
//       .get();

//     if (!pendingRequest.empty) {
//       const requestData = pendingRequest.docs[0].data();
      
//       if (requestData.status === 'awaiting_datetime') {
//         // Update the request with time and change status
//         await pendingRequest.docs[0].ref.update({
//           status: 'awaiting_contact',
//           timeInfo: message
//         });

//         const response = {
//           content: 'Please provide your contact information (email or phone number) so we can confirm your appointment.'
//         };

//         await saveMessages(shareId, sessionId, shareData.assistantId, message, response, []);
//         return res.json({
//           content: response.content,
//           requiresNotification: true
//         });
//       } else if (requestData.status === 'awaiting_contact') {
//         // Create the final notification with all information
//         await firestore.db.collection('assistant_notifications').add({
//           assistantId: shareData.assistantId,
//           type: requestData.type,
//           message: `${requestData.originalMessage} at ${requestData.timeInfo}`,
//           contactInfo: message,
//           priority: requestData.priority,
//           timeInfo: requestData.timeInfo,
//           status: 'unread',
//           createdAt: Firestore.FieldValue.serverTimestamp()
//         });

//         await pendingRequest.docs[0].ref.update({
//           status: 'completed',
//           contactInfo: message
//         });

//         const response = {
//           content: `Thank you! Your appointment has been scheduled for ${requestData.timeInfo} and we'll contact you at ${message}`
//         };

//         await saveMessages(shareId, sessionId, shareData.assistantId, message, response, []);
//         return res.json({
//           content: response.content,
//           requiresNotification: true
//         });
//       }
//     }

//     // If no pending request, analyze the new message
//     try {
//       let messageAnalysis = await geminiService.analyzeMessageIntent(message);
//       console.log('Message analysis:', messageAnalysis);

//       if (messageAnalysis.type === 'appointment_request' || messageAnalysis.type === 'schedule_change') {
//         // Create a pending request for date/time
//         await firestore.db.collection('pending_requests').add({
//           shareId,
//           assistantId: shareData.assistantId,
//           originalMessage: message,
//           type: messageAnalysis.type,
//           priority: messageAnalysis.priority,
//           status: 'awaiting_datetime',
//           timestamp: Firestore.FieldValue.serverTimestamp()
//         });

//         const response = {
//           content: 'Please specify the date and time for your appointment.'
//         };

//         await saveMessages(shareId, sessionId, shareData.assistantId, message, response, []);
//         return res.json({
//           content: response.content,
//           requiresNotification: true
//         });
//       } else if (messageAnalysis.requiresNotification) {
//         // Handle other types of notifications
//         await firestore.db.collection('assistant_notifications').add({
//           assistantId: shareData.assistantId,
//           type: messageAnalysis.type,
//           message: message,
//           priority: messageAnalysis.priority,
//           timeInfo: messageAnalysis.detectedInfo?.timeRelated || null,
//           personName: messageAnalysis.detectedInfo?.personName || null,
//           actionType: messageAnalysis.detectedInfo?.actionType || null,
//           status: 'unread',
//           createdAt: Firestore.FieldValue.serverTimestamp()
//         });

//         const response = {
//           content: `Your notification has been sent successfully. ${messageAnalysis.type === 'absence_notification' ? 'Your absence has been recorded.' : 'The relevant person will be notified.'}`
//         };

//         await saveMessages(shareId, sessionId, shareData.assistantId, message, response, []);
//         return res.json({
//           content: response.content,
//           requiresNotification: true
//         });
//       }
//     } catch (intentError) {
//       console.error('Intent analysis error:', intentError);
//     }

//     // Your existing code for handling non-notification messages
//     let relevantVectors = [];
//     try {
//       const messageEmbedding = await geminiService.generateEmbeddings(message);
//       relevantVectors = await vectors.searchVectors(messageEmbedding, 5, {
//         assistantId: shareData.assistantId,
//         type: ['instructions', 'document'],
//         includeMetadata: true
//       });
//     } catch (vectorError) {
//       console.error('Vector search error:', vectorError);
//     }

//     // Build context array with truncation
//     const context = [];
//     if (assistant.instructions) {
//       context.push({
//         role: 'system',
//         content: `Instructions: ${assistant.instructions.slice(0, 1000)}`, // Truncate long instructions
//         createdAt: new Date()
//       });
//     }

//     // Add truncated relevant vectors
//     relevantVectors.forEach((vec) => {
//       if (vec.metadata?.content) {
//         let contentType = vec.metadata.contentType || vec.metadata.type || 'Document';
//         contentType = contentType.charAt(0).toUpperCase() + contentType.slice(1);
//         context.push({
//           role: 'system',
//           content: `${contentType} content from ${vec.metadata.name}: ${vec.metadata.content.slice(0, 500)}`, // Truncate content
//           metadata: vec.metadata.classification ? {
//             type: vec.metadata.classification.primary.type,
//             confidence: vec.metadata.classification.primary.confidence
//           } : null,
//           createdAt: new Date()
//         });
//       }
//     });

//     // Add only recent messages to prevent context overflow
//     const recentMessages = previousMessages.slice(-5); // Keep only last 5 messages
//     recentMessages.forEach(msg => {
//       context.push({
//         role: msg.role,
//         content: msg.content,
//         createdAt: msg.createdAt || new Date(),
//       });
//     });

//     context.push({
//       role: 'user',
//       content: message,
//       createdAt: new Date()
//     });

//     // Generate response with retry logic for RECITATION error
//     let response;
//     try {
//       response = await geminiService.generateResponse(message, context, {
//         maxTokens: 1000,
//         category: assistant.category,
//         language,
//         systemPrompt: "Provide concise, relevant responses based on the available context while maintaining conversation flow."
//       });
//     } catch (error) {
//       if (error.message.includes('RECITATION')) {
//         console.log('Retrying with reduced context due to RECITATION error');
//         // Retry with minimal context
//         const reducedContext = [
//           {
//             role: 'system',
//             content: assistant.instructions ? `Instructions: ${assistant.instructions.slice(0, 500)}` : '',
//             createdAt: new Date()
//           },
//           {
//             role: 'user',
//             content: message,
//             createdAt: new Date()
//           }
//         ];
        
//         response = await geminiService.generateResponse(message, reducedContext, {
//           maxTokens: 1000,
//           category: assistant.category,
//           language,
//           systemPrompt: "Provide a direct response to the message."
//         });
//       } else {
//         throw error;
//       }
//     }

//     // Save messages
//     await saveMessages(shareId, sessionId, shareData.assistantId, message, {
//       ...response,
//       language
//     }, relevantVectors);

//     console.log('Language:', language);

//     // Send response
//     return res.json({
//       content: response.content,
//       language: response.language,
//       context: {
//         used: relevantVectors.length > 0,
//         count: relevantVectors.length,
//         documents: relevantVectors.map(vec => ({
//           name: vec.metadata.name,
//           type: vec.metadata.contentType || vec.metadata.type,
//           similarity: vec.similarity,
//           classification: vec.metadata.classification,
//           topics: vec.metadata.classification?.topics || []
//         })),
//         averageSimilarity: relevantVectors.length > 0
//           ? relevantVectors.reduce((acc, vec) => acc + vec.similarity, 0) / relevantVectors.length
//           : 0
//       },
//       requiresNotification: false
//     });

//   } catch (error) {
//     console.error('Shared chat error:', error);
//     return res.status(500).json({
//       error: 'Failed to process message',
//       details: error.message
//     });
//   }
// });


//Version 2
// Utility: checks the user’s Google tokens, calls freebusy for [start,end], returns { isSlotAvailable, error }

async function checkCalendarAvailability(assistantOwnerId, startTime, endTime) {
  const userDoc = await firestore.db.collection('users').doc(assistantOwnerId).get();
  const userData = userDoc.data();
  if (!userData?.googleCalendarToken) {
    return { error: 'Google Calendar not connected' };
  }
  oauth2Client.setCredentials(userData.googleCalendarToken);
  const calendar = google.calendar({ version: 'v3', auth: oauth2Client });

  const freeBusyRes = await calendar.freebusy.query({
    requestBody: {
      timeMin: startTime,
      timeMax: endTime,
      items: [{ id: 'primary' }]
    }
  });

  const busySlots = freeBusyRes.data.calendars?.primary?.busy || [];
  const userStart = new Date(startTime);
  const userEnd = new Date(endTime);

  const isSlotAvailable = !busySlots.some((slot) => {
    const slotStart = new Date(slot.start);
    const slotEnd = new Date(slot.end);
    return userStart < slotEnd && userEnd > slotStart;
  });

  return { isSlotAvailable };
}

// router.post('/shared/:shareId/chat', validateSharedAccess, async (req, res) => {
//   try {
//     const { shareId } = req.params;
//     const { message, sessionId, language = 'en' } = req.body;
//     const shareData = req.shareData;
//     const previousMessages = await firestore.getSharedChatHistory(shareId, sessionId);
//     const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/;
//     const phoneRegex = /[\d\s\-\(\)]{10,}/;
//       // Get share details for tone
//       const shareSnapshot = await firestore.db.collection('shared_links')
//       .where('shareId', '==', shareId)
//       .limit(1)
//       .get();

//     if (shareSnapshot.empty) {
//       return res.status(404).json({ error: 'Share link not found' });
//     }

//     const shareDetails = shareSnapshot.docs[0].data();
// const {
//   tone = 'professional',
//   responseStyle = 'detailed',
//   complexityLevel = 'intermediate',
//   interactionStyle = 'collaborative'
// } = shareDetails;

// console.log('Chat preferences:', {
//   tone,
//   responseStyle,
//   complexityLevel,
//   interactionStyle
// });

//     if (!message?.trim()) {
//       return res.status(400).json({ error: 'Message is required' });
//     }
//     if (!sessionId) {
//       return res.status(400).json({ error: 'Session ID is required' });
//     }

//     // 1. Fetch assistant
//     const assistant = await firestore.getAssistant(shareData.assistantId);
//     if (!assistant) {
//       return res.status(404).json({ error: 'Assistant not found' });
//     }

    
//     // 2. Check if there's a pending request with 'awaiting_confirmation'
//     const pendingSnap = await firestore.db.collection('pending_requests')
//       .where('shareId', '==', shareId)
//       .where('status', '==', 'awaiting_confirmation')
//       .orderBy('timestamp', 'desc')
//       .limit(1)
//       .get();

//     let hasPendingRequest = !pendingSnap.empty;
//     let pendingDoc = null;
//     let pendingData = null;

//     if (hasPendingRequest) {
//       pendingDoc = pendingSnap.docs[0];
//       pendingData = pendingDoc.data(); // e.g. { timeInfo, originalMessage, priority, ... }
//     }

//     const lowerMsg = message.trim().toLowerCase();

//     // 3. If there's a pending request, do confirm/cancel/reschedule
//     if (hasPendingRequest) {
//       const parseResults = chrono.parse(message, new Date(), { forwardDate: true });
//       const mightHaveNewDateTime = parseResults.length > 0;
    
//       // Check for contact info in the message first
//       const emailMatch = message.match(emailRegex);
//       const phoneMatch = message.match(phoneRegex);
      
//       // If we don't have contact info and user provided it, save it
//       if (!pendingData.contactInfo && (emailMatch || phoneMatch)) {
//         const contactInfo = {
//           ...(emailMatch && { email: emailMatch[0].toLowerCase() }),
//           ...(phoneMatch && { phone: phoneMatch[0].replace(/\D/g, '') })
//         };
        
//         await pendingDoc.ref.update({
//           contactInfo,
//           timestamp: Firestore.FieldValue.serverTimestamp()
//         });
    
//         const confirmPrompt = {
//           content: `Thanks! I've saved your contact information. Please reply with "confirm" to send your appointment notification for ${pendingData.timeInfo.formatted}.`,
//           language
//         };
//         await saveMessages(shareId, sessionId, shareData.assistantId, message, confirmPrompt, []);
//         return res.json({ content: confirmPrompt.content });
//       }
    
//       const userConfirmed = /confirm/i.test(lowerMsg);
//       const userCancelled = /cancel/i.test(lowerMsg);
//       let userWantsReschedule = /reschedule/i.test(lowerMsg);
      
//       if (mightHaveNewDateTime) {
//         userWantsReschedule = true;
//       }
    
//       if (userConfirmed) {
//         // Check if we have contact info before confirming
//         if (!pendingData.contactInfo) {
//           const promptContact = {
//             content: `Please provide your email or phone number to confirm the appointment.`,
//             language
//           };
//           await saveMessages(shareId, sessionId, shareData.assistantId, message, promptContact, []);
//           return res.json({ content: promptContact.content });
//         }
    
//         // We have contact info, proceed with confirmation
//         const confirmResponse = {
//           content: `Confirmed! User Is Notified for ${pendingData.timeInfo.formatted}. We'll contact you at ${pendingData.contactInfo.email || pendingData.contactInfo.phone}. Once they confirm the appointment`,
//           language
//         };
    
//         // Create notification
//         await firestore.db.collection('assistant_notifications').add({
//           assistantId: shareData.assistantId,
//           type: 'appointment_request',
//           message: `New appointment request for ${pendingData.timeInfo.formatted}. Contact: ${
//             pendingData.contactInfo.email || pendingData.contactInfo.phone
//           }`,          timeInfo: pendingData.timeInfo,
//           shareId,
//           status: 'unread',
//           createdAt: Firestore.FieldValue.serverTimestamp()
//         });
    
//         await pendingDoc.ref.update({ status: 'confirmed' });
//         await saveMessages(shareId, sessionId, shareData.assistantId, message, confirmResponse, []);
//         return res.json({ content: confirmResponse.content });
//       } 
//        else if (userCancelled) {
//         // cancel
//         const cancelResponse = {
//           content: `No worries, I've canceled that appointment request. Let me know if you need anything else.`,
//           language
//         };
//         await pendingDoc.ref.update({ status: 'canceled' });
//         await saveMessages(shareId, sessionId, shareData.assistantId, message, cancelResponse, []);
//         return res.json({ content: cancelResponse.content });
//       } else if (userWantsReschedule) {
//         if (mightHaveNewDateTime) {
//           // parse new date/time
//           const dateObj = parseResults[0].start.date();
//           if (isNaN(dateObj)) {
//             const clarifyRes = {
//               content: `I couldn't understand the new date/time. For example: "reschedule to December 30 at 4pm."`,
//               language
//             };
//             await saveMessages(shareId, sessionId, shareData.assistantId, message, clarifyRes, []);
//             return res.json({ content: clarifyRes.content });
//           }

//           // check availability
//           const endDateObj = new Date(dateObj);
//           endDateObj.setHours(endDateObj.getHours() + 1);
//           const timeObj = {
//             startTime: dateObj.toISOString(),
//             endTime: endDateObj.toISOString(),
//             formatted: `${dateObj.toLocaleDateString()} at ${dateObj.toLocaleTimeString()}`
//           };

//           try {
//             const { isSlotAvailable, error } = await checkCalendarAvailability(
//               assistant.userId,
//               timeObj.startTime,
//               timeObj.endTime
//             );
//             if (error) {
//               // Update the existing pending request with new time
//               await pendingDoc.ref.update({
//                 timeInfo: timeObj,
//                 originalMessage: message,
//                 timestamp: Firestore.FieldValue.serverTimestamp()
//               });
            
//               const resp = {
//                 content: `I've noted your requested time for ${timeObj.formatted}. Please confirm this new time by replying with "confirm"`,
//                 language
//               };
//               await saveMessages(shareId, sessionId, shareData.assistantId, message, resp, []);
//               return res.json({ content: resp.content });
//             }

//             let conversationResponse;
//             if (isSlotAvailable) {
//               // update pending doc with new time
//               await pendingDoc.ref.update({
//                 timeInfo: timeObj,
//                 originalMessage: message,
//                 timestamp: Firestore.FieldValue.serverTimestamp()
//               });
//               conversationResponse = await geminiService.handleAppointmentConversation(
//                 { requiresNotification: true },
//                 timeObj,
//                 message,
//                 previousMessages,
//                 assistant,
//                 geminiService,
//                 true,
//                 req
//               );
//             } else {
//               conversationResponse = await geminiService.handleAppointmentConversation(
//                 { requiresNotification: false },
//                 timeObj,
//                 message,
//                 previousMessages,
//                 assistant,
//                 geminiService,
//                 false,
//                 req
//               );
//             }

//             await saveMessages(shareId, sessionId, shareData.assistantId, message, {
//               content: conversationResponse.content
//             }, []);
//             return res.json({ content: conversationResponse.content });

//           } catch (err) {
//             console.error('Calendar operation error:', err);
//             const resp = { content: `Error while checking the calendar. Please try again later.` };
//             await saveMessages(shareId, sessionId, shareData.assistantId, message, resp, []);
//             return res.json({ content: resp.content });
//           }
//         } else {
//           // user said "reschedule" w/o new time
//           const reschedRes = {
//             content: `Sure! Please provide the new date/time you'd like, and I'll check availability again.`
//           };
//           await pendingDoc.ref.update({ status: 'reschedule_requested' });
//           await saveMessages(shareId, sessionId, shareData.assistantId, message, reschedRes, []);
//           return res.json({ content: reschedRes.content });
//         }
//       } else {
//         // not sure
//         const unclear = {
//           content: pendingData.contactInfo 
//             ? `For your appointment at ${pendingData.timeInfo.formatted}, please reply with "confirm", "cancel", or "reschedule".`
//             : `For your appointment at ${pendingData.timeInfo.formatted}, please provide your email or phone number.`
//         };
//         await saveMessages(shareId, sessionId, shareData.assistantId, message, unclear, []);
//         return res.json({ content: unclear.content });
//       }
//     }

//     // ------------------------------------------------------
//     // 4. NO pending request => normal scheduling logic
//     // ------------------------------------------------------
//     let messageAnalysis = null;
//     try {
//       messageAnalysis = await geminiService.analyzeMessageIntent(message);
//       console.log('Message analysis:', messageAnalysis);

//       if (
//         messageAnalysis.type === 'appointment_request' ||
//         messageAnalysis.type === 'schedule_change'
//       ) {
//         // parse date/time
//         let timeInfo = messageAnalysis.detectedInfo?.timeRelated;
//         if (!timeInfo) {
//           const parseRes = chrono.parse(message, new Date(), { forwardDate: true });
//           if (parseRes.length > 0) {
//             timeInfo = parseRes[0].text;
//           }
//         }

//         // if no date/time found => ask
//         if (!timeInfo) {
//           const resp = {
//             content: `Could you please specify the date or time for your appointment request?`
//           };
//           await saveMessages(shareId, sessionId, shareData.assistantId, message, resp, []);
//           return res.json({ content: resp.content });
//         }

//         // convert string => Date
//         const chronoResults = chrono.parse(timeInfo, new Date(), { forwardDate: true });
//         let dateObj = null;
//         if (chronoResults.length > 0) {
//           dateObj = chronoResults[0].start.date();
//         } else {
//           dateObj = new Date(timeInfo);
//         }

//         if (isNaN(dateObj)) {
//           const resp = {
//             content: `I couldn't understand that date. Could you try "January 5, 2025 at 2pm"?`
//           };
//           await saveMessages(shareId, sessionId, shareData.assistantId, message, resp, []);
//           return res.json({ content: resp.content });
//         }

//         // Check if user gave a time
//         let userProvidedHour = false;
//         if (
//           chronoResults.length > 0 &&
//           chronoResults[0].start.knownValues.hour !== undefined
//         ) {
//           userProvidedHour = true;
//         }

//         // Build finalTimeObj
//         let finalTimeObj;
//         if (userProvidedHour) {
//           const endDateObj = new Date(dateObj);
//           endDateObj.setHours(endDateObj.getHours() + 1);
//           finalTimeObj = {
//             startTime: dateObj.toISOString(),
//             endTime: endDateObj.toISOString(),
//             formatted: `${dateObj.toLocaleDateString()} at ${dateObj.toLocaleTimeString()}`
//           };

//           // Check availability
//           try {
//             const { isSlotAvailable, error } = await checkCalendarAvailability(
//               assistant.userId,
//               finalTimeObj.startTime,
//               finalTimeObj.endTime
//             );
//             if (error) {
//               // Create new pending request
//               await firestore.db.collection('pending_requests').add({
//                 shareId,
//                 assistantId: shareData.assistantId,
//                 timeInfo: finalTimeObj,
//                 originalMessage: message,
//                 type: 'appointment_request',
//                 status: 'awaiting_confirmation',
//                 priority: messageAnalysis.priority || 'normal',
//                 contactInfo: null,
//                 timestamp: Firestore.FieldValue.serverTimestamp()
//               });
            
//               const resp = {
//                 content: `I can help you schedule an appointment for ${finalTimeObj.formatted}. Please provide your email or phone number so we can contact you about the appointment details.`,
//                 language
//               };
//               await saveMessages(shareId, sessionId, shareData.assistantId, message, resp, []);
//               return res.json({ content: resp.content });
//             }
//             // Let Gemini create a conversation response
//             const conversationResponse = await geminiService.handleAppointmentConversation(
//               messageAnalysis,
//               finalTimeObj,
//               message,
//               previousMessages,
//               assistant,
//               geminiService,
//               isSlotAvailable,
//               req
//             );

//             if (isSlotAvailable) {
//               // create a pending doc => 'awaiting_confirmation'
//               await firestore.db.collection('pending_requests').add({
//                 shareId,
//                 assistantId: shareData.assistantId,
//                 timeInfo: finalTimeObj,
//                 originalMessage: message,
//                 type: 'appointment_request',
//                 status: 'awaiting_confirmation',
//                 priority: messageAnalysis.priority || 'normal',
//                 contactInfo: null,
//                 timestamp: Firestore.FieldValue.serverTimestamp()
//               });
//             }

//             await saveMessages(shareId, sessionId, shareData.assistantId, message, {
//               content: conversationResponse.content
//             }, []);
//             return res.json({ content: conversationResponse.content });

//           } catch (err) {
//             console.error('Calendar error:', err);
//             const resp = {
//               content: `I encountered a calendar error. Please try again later.`
//             };
//             await saveMessages(shareId, sessionId, shareData.assistantId, message, resp, []);
//             return res.json({ content: resp.content });
//           }
//         } else {
//           // user gave only date - ask for time
//           await firestore.db.collection('pending_requests').add({
//             shareId,
//             assistantId: shareData.assistantId,
//             timeInfo: { formatted: dateObj.toLocaleDateString() },
//             originalMessage: message,
//             type: 'appointment_request',
//             status: 'awaiting_confirmation',
//             priority: messageAnalysis.priority || 'normal',
//             date: dateObj.toISOString(),
//             contactInfo: null,
//             timestamp: Firestore.FieldValue.serverTimestamp()
//           });
        
//           const resp = {
//             content: 'Please provide a specific time for your appointment.'
//           };
        
//           await saveMessages(shareId, sessionId, shareData.assistantId, message, resp, []);
//           return res.json({ content: resp.content });
//         }
//       }
//       // else normal flow
//     } catch (intentError) {
//       console.error('Intent analysis error:', intentError);
//       // continue below
//     }

//     // 5. Vector logic for non-scheduling
//     let relevantVectors = [];
//     try {
//       const messageEmbedding = await geminiService.generateEmbeddings(message);
//       relevantVectors = await vectors.searchVectors(messageEmbedding, 5, {
//         assistantId: shareData.assistantId,
//         type: ['instructions', 'document'],
//         includeMetadata: true
//       });
//     } catch (err) {
//       console.error('Vector search error:', err);
//     }

//     // Build context
//     const context = [];
//     if (assistant.instructions) {
//       context.push({
//         role: 'system',
//         content: `Instructions: ${assistant.instructions}`
//       });
//     }
//     relevantVectors.forEach((vec) => {
//       if (vec.metadata?.content) {
//         context.push({
//           role: 'system',
//           content: `Content from ${vec.metadata.name}: ${vec.metadata.content}`
//         });
//       }
//     });
//     previousMessages.forEach((msg) => {
//       context.push({ role: msg.role, content: msg.content });
//     });
//     context.push({ role: 'user', content: message });
//     if (messageAnalysis?.requiresNotification) {
//       // Add email and phone regex matching here
//       const emailMatch = message.match(emailRegex);
//       const phoneMatch = message.match(phoneRegex);
      
//       // Create notification for non-appointment requests that need notification
//       await firestore.db.collection('assistant_notifications').add({
//         assistantId: shareData.assistantId,
//         type: messageAnalysis.type,
//         message: message,
//         priority: messageAnalysis.priority || 'normal',
//         timeInfo: messageAnalysis.detectedInfo?.timeRelated || null,
//         personName: messageAnalysis.detectedInfo?.personName || null,
//         actionType: messageAnalysis.detectedInfo?.actionType || null,
//         contactInfo: emailMatch ? emailMatch[0] : (phoneMatch ? phoneMatch[0] : null),
//         status: 'unread',
//         shareId,
//         createdAt: Firestore.FieldValue.serverTimestamp()
//       });
//     }
//     // Normal AI response
//     const response = await geminiService.generateSharedResponse(message, context, {
//       maxTokens: 1000,
//       category: assistant.category,
//       language,
//       tone,
//       responseStyle,
//       complexityLevel,
//       interactionStyle,
//       systemPrompt: 'Use the provided context to give accurate and relevant responses based on the available information. Maintain conversation context.'
//     });

//     await saveMessages(shareId, sessionId, shareData.assistantId, message, response, relevantVectors);
//     return res.json({
//       content: response.content,
//       requiresNotification: false
//     });
//   } catch (error) {
//     console.error('Shared chat error:', error);
//     return res.status(500).json({
//       error: 'Failed to process message',
//       details: error.message
//     });
//   }
// });
// Modified route in backend/src/routes/shared-chat.js
// In shared-chat.js - keep only this route
// In shared-chat.js
// Route should be '/api/share/:shareId/creator'
// router.post('/shared/:shareId/chat', validateSharedAccess, async (req, res) => {
//   try {
//     const { shareId } = req.params;
//     const { message, sessionId, language = 'en' } = req.body;
//     const shareData = req.shareData;

//     if (!message?.trim()) return res.status(400).json({ error: 'Message is required' });
//     if (!sessionId) return res.status(400).json({ error: 'Session ID is required' });

//     // Initialize services
//     const flowProcessor = new FlowProcessor(geminiService, firestore, vectors);
//     const assistant = await firestore.getAssistant(shareData.assistantId);
//     if (!assistant) return res.status(404).json({ error: 'Assistant not found' });

//     // Get chat preferences
//     const shareSnapshot = await firestore.db.collection('shared_links')
//       .where('shareId', '==', shareId)
//       .limit(1)
//       .get();
//     if (shareSnapshot.empty) return res.status(404).json({ error: 'Share link not found' });

//     const shareDetails = shareSnapshot.docs[0].data();
//     const {
//       tone = 'professional',
//       responseStyle = 'detailed',
//       complexityLevel = 'intermediate',
//       interactionStyle = 'collaborative'
//     } = shareDetails;

//     // Get session state and previous messages
//     const sessionRef = await firestore.db.collection('chat_sessions').doc(sessionId);
//     const session = await sessionRef.get();
//     const sessionData = session.data() || {};
//     const previousMessages = await firestore.getSharedChatHistory(shareId, sessionId);

//     // If we have a current node, continue flow processing
//     if (sessionData.currentNodeId) {
//       console.log('Currently in here')
//       console.log(sessionData.currentNodeId)
//       const currentNode = assistant.flowData.nodes.find(n => n.id === sessionData.currentNodeId);
//       if (currentNode) {
//         if (sessionData.awaitingResponse && !message) {
//           return res.status(400).json({ error: 'Response required to continue flow' });
//         }
//         const flowResponse = await flowProcessor.processNode(
//           currentNode,
//           message,
//           sessionId,
//           assistant,
//           { previousMessages }
//         );

//         await saveMessages(shareId, sessionId, shareData.assistantId, message, {
//           content: flowResponse.content
//         }, []);

//         if (flowResponse.requiresTransfer) {
//           return res.json({
//             content: flowResponse.content,
//             requiresTransfer: true
//           });
//         }

//         return res.json({ content: flowResponse.content });
//       }
//     }

//     // Start new flow if no current node
//     console.log('ASSISTANT FLOW DATA')
//     console.log(assistant.flowData)
//     // const startNode = assistant.flowData.nodes.find(n => n.id === 'node_2');
//     const startNode = assistant.flowData.nodes.find(n => n.data.nodeType === 'starting');
//     if (startNode) {
//       console.log('STARTING WITH START NODE')
//       const flowResponse = await flowProcessor.processNode(
//         startNode,
//         message,
//         sessionId,
//         assistant,
//         { previousMessages }
//       );

//       await saveMessages(shareId, sessionId, shareData.assistantId, message, {
//         content: flowResponse.content
//       }, []);

//       return res.json({ content: flowResponse.content });
//     }

//     // Fallback to regular chat if no flow defined
//     const relevantVectors = await vectors.searchVectors(
//       await geminiService.generateEmbeddings(message),
//       5,
//       {
//         assistantId: shareData.assistantId,
//         type: ['instructions', 'document'],
//         includeMetadata: true
//       }
//     );

//     const context = buildContext(assistant, relevantVectors, previousMessages, message);
//     const response = await geminiService.generateSharedResponse(message, context, {
//       maxTokens: 1000,
//       category: assistant.category,
//       language,
//       tone,
//       responseStyle,
//       complexityLevel,
//       interactionStyle
//     });

//     await saveMessages(shareId, sessionId, shareData.assistantId, message, response, relevantVectors);
//     return res.json({ content: response.content });

//   } catch (error) {
//     console.error('Shared chat error:', error);
//     return res.status(500).json({
//       error: 'Failed to process message',
//       details: error.message
//     });
//   }
// });

// Add these new routes to handle session analytics exports

// Get a list of all sessions with analytics data
router.get('/shared/analytics/sessions', async (req, res) => {
  try {
    // Call the Python API to get a list of all sessions with analytics
    const response = await axios.get(`${PYTHON_API_URL}/api/session-analytics`);
    return res.json(response.data);
  } catch (error) {
    console.error('Error fetching session analytics:', error);
    return res.status(500).json({
      error: 'Failed to fetch session analytics',
      details: error.message
    });
  }
});

// Get analytics data for a specific session
router.get('/shared/analytics/sessions/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    
    // Call the Python API to get analytics for this session
    const response = await axios.get(`${PYTHON_API_URL}/api/session-analytics/${sessionId}`);
    return res.json(response.data);
  } catch (error) {
    console.error('Error fetching session analytics:', error);
    return res.status(500).json({
      error: 'Failed to fetch session analytics',
      details: error.message
    });
  }
});

// Export session analytics to Excel
router.get('/shared/analytics/sessions/:sessionId/export', async (req, res) => {
  try {
    const { sessionId } = req.params;
    
    // Call the Python API to export analytics for this session
    const response = await axios.get(`${PYTHON_API_URL}/api/export-session-analytics/${sessionId}`, {
      responseType: 'arraybuffer'  // Important for handling binary data
    });
    
    // Set the appropriate headers for Excel file download
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename=session_analytics_${sessionId}.xlsx`);
    
    // Send the Excel file data
    return res.send(Buffer.from(response.data));
  } catch (error) {
    console.error('Error exporting session analytics:', error);
    return res.status(500).json({
      error: 'Failed to export session analytics',
      details: error.message
    });
  }
});

// Add these new routes to your existing Node.js backend

// Get aggregated session data (including total duration) for a specific patient
// Get aggregated session data (including total duration) for a specific patient
router.get('/shared/analytics/patient/:patientId/aggregate', verifyToken, async (req, res) => {
  try {
    const { patientId } = req.params;
    const userId = req.user.id;
    
    console.log(`Session analytics aggregation requested for patient ${patientId}`);

    // Verify user access
    const userDoc = await firestore.db.collection('users').doc(userId).get();
    if (!userDoc.exists) {
      return res.status(403).json({ error: 'Access denied: User not authorized' });
    }

    // First approach: Get patient sessions directly from the chat_sessions collection
    const sessionsSnapshot = await firestore.db.collection('chat_sessions')
      .where('patientId', '==', patientId)
      .get();
    
    // Extract session IDs
    const sessionIds = [];
    sessionsSnapshot.forEach(doc => {
      sessionIds.push(doc.id);
    });
    
    console.log(`Extracted session IDs for patient ${patientId}:`, sessionIds);
    
    if (sessionIds.length === 0) {
      console.log(`No sessions found for patient ${patientId}`);
      return res.json({
        totalSessions: 0,
        totalDuration: 0,
        totalMessages: 0,
        totalPositive: 0,
        totalNeutral: 0, 
        totalNegative: 0,
        totalHighUrgency: 0,
        totalMediumUrgency: 0,
        totalLowUrgency: 0,
        topIntents: {},
        topTopics: {},
        sessionAnalytics: []
      });
    }

    // Get all analytics data directly from Python API endpoint for each session
    let totalDuration = 0;
    let totalMessages = 0;
    let totalPositive = 0;
    let totalNeutral = 0;
    let totalNegative = 0;
    let totalHighUrgency = 0;
    let totalMediumUrgency = 0;
    let totalLowUrgency = 0;
    const sessionAnalytics = [];
    const intentsCount = {};
    const topicsCount = {};

    // Process each session ID
    for (const sessionId of sessionIds) {
      try {
        const response = await axios.get(`${PYTHON_API_URL}/api/session-analytics/${sessionId}`);
        const sessionData = response.data;
        console.log('SESSION ANALYTICS', sessionData);
        
        if (sessionData) {
          totalDuration += sessionData.duration_seconds || 0;
          totalMessages += sessionData.message_count || 0;
          
          // Add sentiment counts directly
          if (sessionData.sentiment_distribution) {
            totalPositive += sessionData.sentiment_distribution.positive || 0;
            totalNeutral += sessionData.sentiment_distribution.neutral || 0;
            totalNegative += sessionData.sentiment_distribution.negative || 0;
          }
          
          // Add urgency counts directly
          if (sessionData.urgency_distribution) {
            totalHighUrgency += sessionData.urgency_distribution.high || 0;
            totalMediumUrgency += sessionData.urgency_distribution.medium || 0;
            totalLowUrgency += sessionData.urgency_distribution.low || 0;
          }
          
          // Count intents
          if (sessionData.intent_distribution) {
            Object.entries(sessionData.intent_distribution).forEach(([intent, count]) => {
              intentsCount[intent] = (intentsCount[intent] || 0) + count;
            });
          }
          
          // Count topics
          if (sessionData.topic_distribution) {
            Object.entries(sessionData.topic_distribution).forEach(([topic, count]) => {
              topicsCount[topic] = (topicsCount[topic] || 0) + count;
            });
          }
          
          sessionAnalytics.push({
            sessionId,
            duration: sessionData.duration_seconds || 0,
            messageCount: sessionData.message_count || 0,
            startTime: sessionData.start_time,
            endTime: sessionData.end_time
          });
        }
      } catch (error) {
        console.error(`Error fetching analytics for session ${sessionId}:`, error.message);
        // Continue to the next session if there's an error
      }
    }
    
    // Sort intents and topics by count
    const topIntents = Object.entries(intentsCount)
      .sort((a, b) => b[1] - a[1])
      .reduce((obj, [key, value]) => {
        obj[key] = value;
        return obj;
      }, {});
      
    const topTopics = Object.entries(topicsCount)
      .sort((a, b) => b[1] - a[1])
      .reduce((obj, [key, value]) => {
        obj[key] = value;
        return obj;
      }, {});
    
    console.log(`Aggregates for patient ${patientId}:`, { 
      totalDuration, 
      totalPositive,
      totalNeutral,
      totalNegative,
      totalHighUrgency,
      totalMediumUrgency,
      totalLowUrgency
    });
    
    // Return the aggregated data
    res.json({
      totalSessions: sessionIds.length,
      totalDuration,
      totalMessages,
      totalPositive,
      totalNeutral, 
      totalNegative,
      totalHighUrgency,
      totalMediumUrgency,
      totalLowUrgency,
      topIntents,
      topTopics,
      sessionAnalytics
    });
  } catch (error) {
    console.error('Error aggregating patient session data:', error);
    res.status(500).json({
      error: 'Failed to aggregate session data',
      details: error.message
    });
  }
});

// Get aggregated session data for all patients (for the Sessions page)
router.get('/shared/analytics/all-patients/aggregate', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Verify user access
    const userDoc = await firestore.db.collection('users').doc(userId).get();
    if (!userDoc.exists) {
      return res.status(403).json({ error: 'Access denied: User not authorized' });
    }

    // Get all patients
    const patientsSnapshot = await firestore.db.collection('patients').get();
    if (patientsSnapshot.empty) {
      return res.json([]);
    }

    // For each patient, get their session aggregate data
    const patientAggregates = await Promise.all(
      patientsSnapshot.docs.map(async (patientDoc) => {
        const patientId = patientDoc.id;
        const patientData = patientDoc.data();
        
        // Get all sessions for this patient
        const sessionsSnapshot = await firestore.db.collection('chat_sessions')
          .where('patientId', '==', patientId)
          .get();
        
        // Calculate total sessions
        const totalSessions = sessionsSnapshot.size;
        
        if (totalSessions === 0) {
          return {
            patientId,
            patientData,
            totalSessions: 0,
            totalDuration: 0,
            totalMessages: 0
          };
        }
        
        // Collect session IDs
        const sessionIds = sessionsSnapshot.docs.map(doc => doc.id);
        
        // Get analytics for each session
        let totalDuration = 0;
        let totalMessages = 0;
        
        // Process each session
        for (const sessionId of sessionIds) {
          try {
            const response = await axios.get(`${PYTHON_API_URL}/api/session-analytics/${sessionId}`);
            if (response.data) {
              totalDuration += response.data.duration_seconds || 0;
              totalMessages += response.data.message_count || 0;
            }
          } catch (error) {
            console.error(`Error fetching analytics for session ${sessionId}:`, error.message);
            // Continue with next session
          }
        }
        
        return {
          patientId,
          patientData,
          totalSessions,
          totalDuration,
          totalMessages
        };
      })
    );
    
    res.json(patientAggregates);
  } catch (error) {
    console.error('Error aggregating all patients session data:', error);
    res.status(500).json({
      error: 'Failed to aggregate session data',
      details: error.message
    });
  }
});


async function translateToLanguage(text, targetLanguage) {
  if (targetLanguage === 'en') return text;
  try {
    const response = await axios.post(`${PYTHON_API_URL}/api/translate-to-language`, {
      text,
      target_language: targetLanguage
    });
    return response.data.translated_text || text;
  } catch (error) {
    console.error('Translation to target language failed:', error.message);
    return text;
  }
}
async function markOnboardingComplete(phoneNumber, patientId) {
  const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
    .where('phoneNumber', '==', phoneNumber)
    .where('patientId', '==', patientId)
    .limit(1)
    .get();
  
  if (!mappingSnapshot.empty) {
    const mappingDoc = mappingSnapshot.docs[0];
    await mappingDoc.ref.update({ onboardingComplete: true });
    console.log(`Marked onboarding complete for phone ${phoneNumber}`);
  }
}

async function handleNotificationNode(notificationData, shareData, patientId) {
  try {
    const notificationId = uuidv4();
    const notification = {
      id: notificationId,
      patientId,
      title: notificationData.title || '',
      message: notificationData.message,
      createdAt: new Date().toISOString(),
      scheduledFor: notificationData.scheduled_for || null,
      messageType: notificationData.notification_type, // 'whatsapp' or 'sms' from the backend
      sentAt: null,
      status: notificationData.scheduled_for ? 'scheduled' : 'pending',
      assistantId: notificationData.assistant_id || shareData.assistantId,
      surveyQuestions: notificationData.survey_questions || []
    };

    // Save the notification to Firestore
    await firestore.db.collection('patient_notifications').doc(notificationId).set(notification);

    // If not scheduled for later, send immediately
    if (!notificationData.scheduled_for) {
      const twilioService = new TwilioService();
      const sessionId = `notification_${notificationId}_${Date.now()}`;

      // Get patient's phone number
      const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        .where('patientId', '==', patientId)
        .limit(1)
        .get();

      if (mappingSnapshot.empty) {
        throw new Error('Patient does not have a phone number configured');
      }

      const phoneNumber = mappingSnapshot.docs[0].data().phoneNumber;
      const messageContent = notificationData.content || notificationData.message;
      
      // Use the notification_type from the backend to determine how to send
      if (notificationData.notification_type === 'whatsapp') {
        await twilioService.sendWhatsAppMessage(
          `whatsapp:+1${phoneNumber}`,
          messageContent,
          null, // mediaUrl
          sessionId,
          notificationData.assistant_id || shareData.assistantId,
          patientId
        );
      } else if (notificationData.notification_type === 'sms') {
        await twilioService.sendSmsMessage(
          `+1${phoneNumber}`,
          messageContent,
          null, // mediaUrl
          sessionId,
          notificationData.assistant_id || shareData.assistantId,
          patientId
        );
      } else {
        throw new Error(`Unsupported notification type: ${notificationData.notification_type}`);
      }

      // Save the message to chat_sessions for history
      await firestore.db.collection('chat_sessions').doc(sessionId).set({
        sessionId,
        assistantId: notificationData.assistant_id || shareData.assistantId,
        patientId,
        phoneNumber,
        type: notificationData.notification_type, // 'whatsapp' or 'sms'
        lastActivity: new Date(),
        notificationId,
        isNotification: true,
        surveyQuestions: notificationData.survey_questions || []
      });

      // Update notification as sent
      await firestore.db.collection('patient_notifications').doc(notificationId).update({
        sentAt: new Date().toISOString(),
        status: 'sent',
        sessionId,
        phoneNumber
      });
    }

    return {
      success: true,
      notificationId,
      status: notificationData.scheduled_for ? 'scheduled' : 'sent',
      scheduledFor: notificationData.scheduled_for || null
    };
  } catch (error) {
    console.error('Error handling notification node:', error);
    throw error;
  }
}

async function handleNotificationSurveyResponse({
  notification,
  message,
  sessionId,
  sessionRef,
  sessionData,
  shareId,
  shareData,
  patientId,
  isInitialMessage = false,
}) {
  let surveyState = sessionData.surveyState || {
    notificationId: notification.id,
    currentQuestionIndex: 0,
    surveyQuestions: notification.surveyQuestions,
  };

  const currentQuestionIndex = surveyState.currentQuestionIndex;
  const surveyQuestions = surveyState.surveyQuestions;

  // Handle first user message or unstarted survey
  if (!sessionData.surveyStarted && currentQuestionIndex < surveyQuestions.length) {
    const currentQuestion = surveyQuestions[currentQuestionIndex];
    let responseContent = `Please answer this survey question: ${currentQuestion.text}`;
    if (currentQuestion.options?.length > 0) {
      responseContent += `\nOptions: ${currentQuestion.options.join(', ')}`;
    }

    await saveMessages(
      shareId,
      shareData.userId || shareData.ownerId,
      sessionId,
      shareData.assistantId,
      null,
      { content: responseContent },
      [],
      patientId,
      null
    );

    await sessionRef.set(
      {
        surveyState,
        surveyStarted: true,
        surveyCompleted: false,
        lastActivity: new Date(),
      },
      { merge: true }
    );

    // Record analytics
    await axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
      message: null,
      response: responseContent,
      sessionId,
      timestamp: new Date().toISOString(),
    }).catch((error) => {
      console.error('Error recording survey analytics:', error.message);
    });

    return responseContent;
  }

  // Handle user response (only if survey has started and not initial message)
  if (message?.trim() && sessionData.surveyStarted && currentQuestionIndex < surveyQuestions.length && !isInitialMessage) {
    const currentQuestion = surveyQuestions[currentQuestionIndex];
    // Save response to patient_survey_responses
    await firestore.db.collection('patient_survey_responses').doc().set({
      patientId: patientId || null,
      notificationId: notification.id,
      question: currentQuestion.text,
      answer: message,
      timestamp: new Date().toISOString(),
      sessionId,
    });

    // Save user response and confirmation
    await saveMessages(
      shareId,
      shareData.userId || shareData.ownerId,
      sessionId,
      shareData.assistantId,
      message,
      { content: '' }, // Empty content to avoid TypeError
            [],
      patientId,
      null
    );

    // Move to next question or complete
    if (currentQuestionIndex + 1 < surveyQuestions.length) {
      const nextQuestion = surveyQuestions[currentQuestionIndex + 1];
      let responseContent = `Please answer this survey question: ${nextQuestion.text}`;
      if (nextQuestion.options?.length > 0) {
        responseContent += `\nOptions: ${nextQuestion.options.join(', ')}`;
      }

      // Save next question separately (without user message)
      await saveMessages(
        shareId,
        shareData.userId || shareData.ownerId,
        sessionId,
        shareData.assistantId,
        null, // No user message
        { content: responseContent },
        [],
        patientId,
        null
      );

      await sessionRef.set(
        {
          surveyState: {
            ...surveyState,
            currentQuestionIndex: currentQuestionIndex + 1,
          },
          lastActivity: new Date(),
        },
        { merge: true }
      );

      // Record analytics
      await axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
        message,
        response: responseContent,
        sessionId,
        timestamp: new Date().toISOString(),
      }).catch((error) => {
        console.error('Error recording survey analytics:', error.message);
      });

      return responseContent;
    } else {
      // Survey completed
      const completionMessage = 'Thank you for completing the survey!';
      await saveMessages(
        shareId,
        shareData.userId || shareData.ownerId,
        sessionId,
        shareData.assistantId,
        null,
        { content: completionMessage },
        [],
        patientId,
        null
      );

      await sessionRef.set(
        {
          surveyState: null,
          surveyCompleted: true,
          surveyStarted: false,
          lastActivity: new Date(),
        },
        { merge: true }
      );

      // Record analytics
      await axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
        message,
        response: completionMessage,
        sessionId,
        timestamp: new Date().toISOString(),
      }).catch((error) => {
        console.error('Error recording survey analytics:', error.message);
      });

      return completionMessage;
    }
  } else if (currentQuestionIndex < surveyQuestions.length) {
    // Resend current question if no valid response
    const currentQuestion = surveyQuestions[currentQuestionIndex];
    let responseContent = `Please answer this survey question: ${currentQuestion.text}`;
    if (currentQuestion.options?.length > 0) {
      responseContent += `\nOptions: ${currentQuestion.options.join(', ')}`;
    }

    await saveMessages(
      shareId,
      shareData.userId || shareData.ownerId,
      sessionId,
      shareData.assistantId,
      null, // No user message
       { content: responseContent },
      [],
      patientId,
      null
    );

    // Record analytics
    await axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
      message,
      response: responseContent,
      sessionId,
      timestamp: new Date().toISOString(),
    }).catch((error) => {
      console.error('Error recording survey analytics:', error.message);
    });

    return responseContent;
  }

  return null; // No action needed if survey is complete
}

// =============================================
// Intent Classification Function for Shared Chat Route
// =============================================

async function classifyIntentAndGetAssistant(message, organizationId, currentAssistantId, patientId, sessionData) {
  console.log('[INTENT] Starting intent classification...');
  
  try {
    // First, get all available categories for this organization
    const availableCategories = await getAvailableAssistantCategories(organizationId);
    
    console.log(`[INTENT] Available categories for org ${organizationId}: ${availableCategories.join(', ')}`);
    
    if (availableCategories.length <= 1) {
      console.log('[INTENT] Only one category available, skipping classification');
      return {
        assistantId: currentAssistantId,
        flowId: null, // Will be set by caller
        switched: false,
        category: 'default'
      };
    }

    // Call Python API to classify intent with actual available categories
    const intentResponse = await axios.post(`${PYTHON_API_URL}/api/classify-intent`, {
      message: message,
      organization_id: organizationId,
      current_assistant_id: currentAssistantId,
      available_categories: availableCategories
    });
    
    const selectedCategory = intentResponse.data.selected_category;
    const shouldSwitch = intentResponse.data.should_switch;
    
    console.log(`[INTENT] Classified as: ${selectedCategory}, should switch: ${shouldSwitch}`);
    
    if (shouldSwitch && selectedCategory !== 'default') {
      // Find assistant with this category in the organization
      const categoryAssistantId = await getAssistantByCategory(organizationId, selectedCategory);
      
      if (categoryAssistantId) {
        const newAssistant = await firestore.getAssistant(categoryAssistantId);
        if (newAssistant && newAssistant.flowData) {
          console.log(`[INTENT] Switching to ${selectedCategory} assistant: ${categoryAssistantId}`);
          
          // Update the patient phone mapping with the specialized assistant
          if (patientId && sessionData.phoneNumber) {
            try {
              await firestore.db.collection('patient_phone_mappings')
                .where('phoneNumber', '==', sessionData.phoneNumber)
                .where('patientId', '==', patientId)
                .get()
                .then(snapshot => {
                  if (!snapshot.empty) {
                    snapshot.docs[0].ref.update({ 
                      assistantId: categoryAssistantId,
                      updatedAt: new Date().toISOString(),
                      switchedReason: `intent_classification_${selectedCategory}`
                    });
                  }
                });
              console.log(`[INTENT] Updated patient mapping to use ${selectedCategory} assistant`);
            } catch (mappingError) {
              console.error('[INTENT] Failed to update patient mapping:', mappingError.message);
            }
          }
          
          return {
            assistantId: categoryAssistantId,
            flowId: newAssistant.flowData.id,
            switched: true,
            category: selectedCategory,
            assistant: newAssistant
          };
        }
      } else {
        console.log(`[INTENT] No assistant found for category '${selectedCategory}', using default`);
      }
    }
    
    // No switch needed or failed to switch
    return {
      assistantId: currentAssistantId,
      flowId: null, // Will be set by caller
      switched: false,
      category: selectedCategory || 'default'
    };
    
  } catch (intentError) {
    console.error('[INTENT] Intent classification failed:', intentError.message);
    return {
      assistantId: currentAssistantId,
      flowId: null,
      switched: false,
      category: 'default',
      error: intentError.message
    };
  }
}

// =============================================
// Helper Functions (add these to your shared chat route file)
// =============================================

async function getAvailableAssistantCategories(organizationId) {
  console.log(`[CATEGORIES] Getting available categories for org: ${organizationId}`);
  
  try {
    const snapshot = await firestore.db.collection('assistants')
      .where('organization_id', '==', organizationId)
      .where('status', '==', 'active')
      .get();
    
    if (snapshot.empty) {
      console.log(`[CATEGORIES] No active assistants found for org: ${organizationId}`);
      return ['default'];
    }
    
    const categories = new Set();
    
    snapshot.docs.forEach(doc => {
      const assistantData = doc.data();
      const category = (assistantData.category || 'default').toLowerCase().trim();
      categories.add(category);
    });
    
    const availableCategories = Array.from(categories);
    
    // Ensure 'default' is always available
    if (!availableCategories.includes('default')) {
      availableCategories.push('default');
    }
    
    console.log(`[CATEGORIES] Found categories: ${availableCategories.join(', ')}`);
    return availableCategories;
    
  } catch (error) {
    console.error(`[CATEGORIES] Error getting categories: ${error.message}`);
    return ['default']; // Fallback
  }
}

async function getAssistantByCategory(organizationId, category) {
  console.log(`[ASSISTANT LOOKUP] Looking for category: '${category}' in org: ${organizationId}`);
  
  try {
    const snapshot = await firestore.db.collection('assistants')
      .where('organization_id', '==', organizationId)
      .where('status', '==', 'active')
      .get();
    
    if (snapshot.empty) {
      console.log(`[ASSISTANT LOOKUP] No active assistants found for org: ${organizationId}`);
      return null;
    }
    
    // Find assistant with matching category (case-insensitive)
    const targetCategory = category.toLowerCase();
    let matchingAssistant = null;
    
    snapshot.docs.forEach(doc => {
      const assistantData = doc.data();
      const assistantCategory = (assistantData.category || '').toLowerCase();
      
      if (assistantCategory === targetCategory) {
        matchingAssistant = doc.id;
        console.log(`[ASSISTANT LOOKUP] Found exact match: ${doc.id} for category: ${category}`);
      }
    });
    
    // If no exact match, try partial matches
    if (!matchingAssistant && targetCategory !== 'default') {
      snapshot.docs.forEach(doc => {
        const assistantData = doc.data();
        const assistantCategory = (assistantData.category || '').toLowerCase();
        
        if (assistantCategory.includes(targetCategory) || targetCategory.includes(assistantCategory)) {
          matchingAssistant = doc.id;
          console.log(`[ASSISTANT LOOKUP] Found partial match: ${doc.id} for category: ${category}`);
        }
      });
    }
    
    // If still no match, return default assistant
    if (!matchingAssistant) {
      snapshot.docs.forEach(doc => {
        const assistantData = doc.data();
        const assistantCategory = (assistantData.category || '').toLowerCase();
        
        if (assistantCategory === 'default') {
          matchingAssistant = doc.id;
          console.log(`[ASSISTANT LOOKUP] Using default assistant: ${doc.id}`);
        }
      });
    }
    
    return matchingAssistant;
    
  } catch (error) {
    console.error(`[ASSISTANT LOOKUP] Error finding assistant: ${error.message}`);
    return null;
  }
}


router.post('/shared/:shareId/chat', validateSharedAccess, async (req, res) => {
  try {
    const { shareId } = req.params;
    // const {  sessionId, language = 'en', patientId } = req.body;
    const {  sessionId, language: sessionLanguage = 'en', patientId } = req.body; // MODIFIED
    var message = req.body.message;
    const shareData = req.shareData;
    console.log('Patient [SHARED CHAT]', patientId)
    // Validate input
    if (!message?.trim()) return res.status(400).json({ error: 'Message is required' });
    if (!sessionId) return res.status(400).json({ error: 'Session ID is required' });
    
    // Get session data
    const sessionRef = await firestore.db.collection('chat_sessions').doc(sessionId);
    const session = await sessionRef.get();
    const sessionData = session.data() || {};
    const isUserInitiated = sessionData.is_user_initiated || false;
    const previousMessages = await firestore.getSharedChatHistory(shareId, sessionId, patientId);
    const isFirstMessage = previousMessages.filter(msg => msg.role === 'user').length === 0;

    console.log(['SESSION DATA'],sessionData)

    //Ususal Share chat route called from the twilio route. 
    // Get user's preferred language from session data
    let userLanguage = sessionData.preferredLanguage || 'en';
    
    try {
      const translationResponse = await axios.post(`${PYTHON_API_URL}/api/translate-to-english`, {
        text: message
      });
      
      // Only update language preference if:
      // 1. We don't have one yet, or
      // 2. The detected language is not 'same' (special marker)
      if (!sessionData.preferredLanguage && 
          translationResponse.data.detected_language !== 'same') {
        userLanguage = translationResponse.data.detected_language || 'en';
        await sessionRef.set({ preferredLanguage: userLanguage }, { merge: true });
        console.log('Setting preferred language to:', userLanguage);
      }
      
      // Store original message for reference
      const originalMessage = message;
      
      // Use translated message for processing
      message = translationResponse.data.translated_text;
      
      console.log(`Translated user message: "${originalMessage}" -> "${message}"`);
    } catch (translationError) {
      console.error('Translation failed:', translationError.message);
    } 
    console.log('[INTENT CLASSIFICATION]', isUserInitiated, isFirstMessage)
      
    if (isUserInitiated && isFirstMessage) {
      console.log('[INTENT] User-initiated first message, checking intent...');
      
      if (message.trim().toLowerCase() === 'hi') {
        // User just said "hi" - ask them to describe what they're looking for
        console.log('[INTENT] User said hi, asking for clarification');
        
        const clarificationMessage = "Hi! Please describe in one word what you are looking for today: symptoms, pregnancy test, pregnancy support, etc.";
        
        // Save the clarification message and return early
        // await saveMessages(
        //   shareId,
        //   shareData.userId || shareData.ownerId,
        //   sessionId,
        //   shareData.assistantId,
        //   message,
        //   { content: clarificationMessage },
        //   [],
        //   patientId,
        //   null
        // );
        
        const translatedContent = await translateToLanguage(clarificationMessage, userLanguage);
        return res.json({ content: translatedContent });
      } else {
        // User provided actual intent in first message - classify it
        console.log('[INTENT] User provided intent in first message, classifying...');
        
        // Get organization ID from patient mapping
        let organizationId = '9d493c7f-7d30-4a04-b9b7-1d34ce25cec4';
        // if (sessionData.phoneNumber) {
        //   try {
        //     const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        //       .where('phoneNumber', '==', sessionData.phoneNumber)
        //       .limit(1)
        //       .get();
            
        //     if (!mappingSnapshot.empty) {
        //       const mappingData = mappingSnapshot.docs[0].data();
        //       if (mappingData.assistantId) {
        //         const mappingAssistant = await firestore.getAssistant(mappingData.assistantId);
        //         if (mappingAssistant && mappingAssistant.organization_id) {
        //           organizationId = mappingAssistant.organization_id;
        //         }
        //       }
        //     }
        //   } catch (mappingError) {
        //     console.error('Error getting organization from patient mapping:', mappingError.message);
        //   }
        // }
        
        if (organizationId) {
          try {
            const intentResult = await classifyIntentAndGetAssistant(
              message,
              organizationId,
              shareData.assistantId,
              patientId,
              sessionData
            );
            
            if (intentResult.switched) {
              shareData.assistantId = intentResult.assistantId;
              console.log(`[INTENT] Switched to ${intentResult.category} assistant: ${intentResult.assistantId}`);
            }
          } catch (intentError) {
            console.error('[INTENT] Intent classification failed:', intentError.message);
          }
        }
      }
    } 

    else if (isUserInitiated && previousMessages.filter(msg => msg.role === 'user').length === 1) {
      // Second message after "hi" - classify intent
      const firstUserMessage = previousMessages.filter(msg => msg.role === 'user')[0];
      if (firstUserMessage && firstUserMessage.content.trim().toLowerCase() === 'hi') {
        console.log('[INTENT] Second message after hi, classifying intent...');
        
        // Same classification logic
        let organizationId = '9d493c7f-7d30-4a04-b9b7-1d34ce25cec4'
        
        // if (sessionData.phoneNumber) {
        //   try {
        //     const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        //       .where('phoneNumber', '==', sessionData.phoneNumber)
        //       .limit(1)
        //       .get();
            
        //     if (!mappingSnapshot.empty) {
        //       const mappingData = mappingSnapshot.docs[0].data();
        //       if (mappingData.assistantId) {
        //         const mappingAssistant = await firestore.getAssistant(mappingData.assistantId);
        //         if (mappingAssistant && mappingAssistant.organization_id) {
        //           organizationId = mappingAssistant.organization_id;
        //         }
        //       }
        //     }
        //   } catch (mappingError) {
        //     console.error('Error getting organization from patient mapping:', mappingError.message);
        //   }
        // }
        
        if (organizationId) {
          try {
            const intentResult = await classifyIntentAndGetAssistant(
              message,
              organizationId,
              shareData.assistantId,
              patientId,
              sessionData
            );
            
            if (intentResult.switched) {
              shareData.assistantId = intentResult.assistantId;
              console.log(`[INTENT] Switched to ${intentResult.category} assistant: ${intentResult.assistantId}`);
            }
          } catch (intentError) {
            console.error('[INTENT] Intent classification failed:', intentError.message);
          }
        }
      }
    }

    if (sessionData.phoneNumber) {
      // Check for recent notification with surveyQuestions (Doctors Sending Notifications to the user for the survey questions)
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
      const notificationSnapshot = await firestore.db.collection('patient_notifications')
          .where('phoneNumber', '==', sessionData.phoneNumber)
          .where('sentAt', '>=', fiveMinutesAgo)
          .where('status', '==', 'sent')
          .where('surveyQuestions', '!=', [])
          .orderBy('sentAt', 'desc')
          .limit(1)
          .get();
      // console.log('Notification SNAPSHOT', notificationSnapshot)
      if (!notificationSnapshot.empty && !sessionData.surveyCompleted) {
          const notification = notificationSnapshot.docs[0].data();
          console.log(`Processing survey response for notification: ${notification.id}`);
          console.log('QUERYING NOTIFICATIONS FOR PHONE:', sessionData.phoneNumber);
          console.log('QUERYING SENT AT AFTER:', fiveMinutesAgo);
        
          // Check if this is the first user message
          const previousMessages = await firestore.getSharedChatHistory(shareId, sessionId, patientId);
          const userMessages = previousMessages.filter(msg => msg.role === 'user');
          const isFirstMessage = userMessages.length === 0 && !sessionData.surveyStarted;
    
          const responseContent = await handleNotificationSurveyResponse({
            notification,
            message,
            sessionId,
            sessionRef,
            sessionData,
            shareId,
            shareData,
            patientId,
            isInitialMessage: isFirstMessage, // Pass flag for first message
          });
          console.log('NOTIFICATION SNAPSHOT EMPTY?', notificationSnapshot.empty);

          if (responseContent) {
            const translatedContent = await translateToLanguage(responseContent, userLanguage);
            return res.json({ content: translatedContent });
          }
          // If no responseContent, survey is complete; proceed to regular processing
        }
      }
    
    // Get assistant data
    const assistant = await firestore.getAssistant(shareData.assistantId);
    console.log('STARTED TALING WITH ASSISTANT ID', assistant)
    if (!assistant) {
      return res.status(404).json({ error: 'Assistant not found' });
    }
    if (assistant.flowData && !assistant.flowData.id) {
      console.log('Adding missing flow ID');
      assistant.flowData.id = assistant.id; // Use assistant ID as flow ID
      
      // Optionally update the assistant document
      await firestore.db.collection('assistants').doc(assistant.id).update({
        'flowData.id': assistant.id
      });
    }
    const flowInstructions = assistant.flowInstructions || null;
    const instructionType = assistant.instructionType || 'generated';
    console.log('Flow instructions available:', !!flowInstructions);

    console.log('Indexing flow with ID:', assistant.flowData.id);
    console.log('Flow structure contains nodes:', assistant.flowData.nodes?.length || 0);

    // Get session data
    // const sessionRef = await firestore.db.collection('chat_sessions').doc(sessionId);
    // const session = await sessionRef.get();
    // const sessionData = session.data() || {};
    // console.log('[SESSION DATA]', sessionData)
    
    // Get previous messages
    // const previousMessages = await firestore.getSharedChatHistory(shareId, sessionId, );
  
    let patientHistory = null;
    if (patientId) {
      try {
        console.log('Fetching patient session history for', patientId);
        const summariesSnapshot = await firestore.db.collection('patient_session_summaries')
          .where('patientId', '==', patientId)
          .orderBy('createdAt', 'desc')
          .limit(1)
          .get();
        
        if (!summariesSnapshot.empty) {
          patientHistory = summariesSnapshot.docs[0].data();
          console.log('Found patient history summary, length:', 
            patientHistory.summary?.length || 0);
        } else {
          console.log('No patient history summaries found');
        }
      } catch (historyError) {
        console.error('Error fetching patient history:', historyError.message);
        // Non-critical, continue without history
      }
    }
    // Handle survey node from flowData
    let surveyQuestionaire = [];
    let surveyNodeId = null;
    let surveyId = null;
    let currentNode = null;
    if (sessionData.currentNodeId) {
      currentNode = assistant.flowData.nodes.find(node => node.id === sessionData.currentNodeId);
      console.log("[NODE TYPE]", currentNode)
      if (currentNode && currentNode.type === 'surveyNode' && currentNode.data.surveyData && currentNode.data.surveyData.questions) {
        // surveyQuestionaire = currentNode.data.surveyData.questions;
        surveyQuestionaire = currentNode.data.surveyData.questions.slice(1);
        surveyNodeId = currentNode.id;
        surveyId = currentNode.data.surveyData.id;
        console.log('Found survey node:', surveyNodeId, 'with questions:', surveyQuestionaire);
        // const surveyResponses = sessionData.survey_responses || [];
        // const userMessageCount = surveyResponses.length;
        // if (userMessageCount === currentNode.data.surveyData.questions.length - 1){
        //   const fullSurveyQuestions = currentNode.data.surveyData.questions
        //   const lastQuestion = fullSurveyQuestions[userMessageCount];
        //   surveyResponses.push({ question: lastQuestion.text, answer: message });
        //   await sessionRef.set(
        //     {
        //       survey_responses: surveyResponses,
        //       survey_questions_length: fullSurveyQuestions.length,
        //       currentNodeId: surveyNodeId,
        //     },
        //     { merge: true }
        //   );

        //   // Save the user's message to Firestore
        //   await saveMessages(
        //     shareId,
        //     shareData.userId || shareData.ownerId,
        //     sessionId,
        //     shareData.assistantId,
        //     message,
        //     { content: 'Survey completed' },
        //     [],
        //     patientId
        //   );

        //   // Record analytics for the last answer
        //   axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
        //     message: message,
        //     response: 'Survey completed',
        //     sessionId: sessionId,
        //     timestamp: new Date().toISOString(),
        //   })
        //     .then((analyticsResponse) => {
        //       console.log('Survey analytics recorded successfully:', analyticsResponse.data.analytics_id);
        //     })
        //     .catch((analyticsError) => {
        //       console.error('Error recording survey analytics:', analyticsError.message);
        //     });

        //   // Override message to "completed" for vector_chat
        //   const pythonMessage = "completed";
        //   message = pythonMessage;
        //   console.log('Last survey question answered, sending "completed" to Python endpoint');
  
        // }
      }
    

    }

    if (surveyQuestionaire.length > 0) {
      const userMessageCount = sessionData.survey_responses ? sessionData.survey_responses.length : 0;
      
      if (userMessageCount < surveyQuestionaire.length) {
        // Process survey question
        const surveyQuestion = surveyQuestionaire[userMessageCount];
        let responseContent = `Please answer this survey question: ${surveyQuestion.text}`;

        // Append options if available
        if (surveyQuestion.options && surveyQuestion.options.length > 0) {
          responseContent += `\nOptions: ${surveyQuestion.options.join(', ')}`;
        }

        // Save user's message and survey question response
        const surveyResponses = sessionData.survey_responses || [];
        surveyResponses.push({ question: surveyQuestion.text, answer: message });
        await sessionRef.set({ survey_responses: surveyResponses, currentNodeId: surveyNodeId }, { merge: true });
        // Save survey response to patient_survey_responses collection
       
        await saveMessages(
          shareId,
          shareData.userId || shareData.ownerId,
          sessionId,
          shareData.assistantId,
          message,
          { content: responseContent },
          [],
          patientId,
          surveyId // Pass surveyNodeId
        );

        // Record analytics
        axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
          message: message,
          response: responseContent,
          sessionId: sessionId,
          timestamp: new Date().toISOString()
        }).then(analyticsResponse => {
          console.log('Survey analytics recorded successfully:', analyticsResponse.data.analytics_id);
        }).catch(analyticsError => {
          console.error('Error recording survey analytics:', analyticsError.message);
        });

        const translatedContent = await translateToLanguage(responseContent, userLanguage);
        return res.json({ content: translatedContent });
        // return res.json({ content: responseContent });
      } 
      else {
        // Survey completed, update session data and call Python with "completed" message
        await sessionRef.set({
          survey_questions_length: surveyQuestionaire.length,
          survey_responses: sessionData.survey_responses || [],
          currentNodeId: surveyNodeId // Keep currentNodeId for Python to handle triggers
        }, { merge: true });

        // Override message to "completed" for Python endpoint
        // message = "completed";
        const surveyResponses = sessionData.survey_responses || [];
        const fullQuestions = currentNode.data.surveyData.questions; // Full question list
        const lastQuestionIndex = surveyQuestionaire.length; // Index in full list (accounts for .slice(1))
        const lastQuestion = fullQuestions[lastQuestionIndex]; // Get last question
        await saveMessages(
          shareId,
          shareData.userId || shareData.ownerId,
          sessionId,
          shareData.assistantId,
          message,
          { content: 'lastQuestion' },
          [],
          patientId,
          null
        );
        const pythonMessage = "completed";
        message = pythonMessage; 
        console.log('Survey completed, sending "completed" to Python endpoint');
      }
    }


    // Handle survey questionnaire
    let surveyQuestions = [];
    if (assistant.survey_id && assistant.survey_data) {
      surveyQuestions = assistant.survey_data.questions || [];
      console.log('Using stored survey questions:', surveyQuestions);
    }

    if (surveyQuestions.length > 0) {
      const userMessageCount = previousMessages.filter(msg => msg.role === 'user').length;
      if (userMessageCount < surveyQuestions.length) {
        const surveyQuestion = surveyQuestions[userMessageCount];
        let responseContent = `Please answer this survey question: ${surveyQuestion.text}`;

        // Append options for multiple_choice or rating questions
        if ((surveyQuestion.type === 'multiple_choice' || surveyQuestion.type === 'rating') && surveyQuestion.options?.length > 0) {
          responseContent += `\nOptions: ${surveyQuestion.options.join(', ')}`;
        }
        
        // Save survey response to patient_survey_responses collection
        const surveyResponseRef = firestore.db.collection('patient_survey_responses').doc();
        await surveyResponseRef.set({
          patientId: patientId,
          surveyId: assistant.survey_id, // Use assistant's survey_id
          question: surveyQuestion.text,
          answer: message,
          timestamp: new Date().toISOString(),
          sessionId: sessionId
        });
        // Save both the user's message and the survey question response
        await saveMessages(
          shareId,
          shareData.userId || shareData.ownerId,
          sessionId,
          shareData.assistantId,
          message,
          { content: responseContent },
          [],
          patientId, 
          assistant.survey_id,

        );
        axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
          message: message,
          response: responseContent,
          sessionId: sessionId,
          timestamp: new Date().toISOString()
        }).then(analyticsResponse => {
          console.log('Survey analytics recorded successfully:', analyticsResponse.data.analytics_id);
        }).catch(analyticsError => {
          console.error('Error recording survey analytics:', analyticsError.message);
          // Non-critical, so we just log the error
        });
        const translatedContent = await translateToLanguage(responseContent, userLanguage);
        return res.json({ content: translatedContent });
        // return res.json({ content: responseContent });
      }
      else
        sessionData.survey_questions_length = surveyQuestions.length
        sessionData.user_message_count = userMessageCount
      
    }
        
    // Check if the flow has been indexed
    let flowIndexed = false;
    try {
      const indexStatusResponse = await axios.get(`${PYTHON_API_URL}/api/flow-index/${assistant.flowData.id}`);
      flowIndexed = indexStatusResponse.data.indexed;
      
      if (!flowIndexed) {
        console.log('Flow not indexed, indexing now...');
        await axios.post(`${PYTHON_API_URL}/api/index/flow-knowledge`, assistant.flowData);
        flowIndexed = true;
      }
    } catch (indexError) {
      console.error('Error checking index status:', indexError.message);
      // Proceed with standard flow processor if indexing check fails
    }

    if (flowIndexed) {

      // Use the vector-based chat endpoint for faster processing
      try {
        console.log('VECTOR CHAT SESSION DATA', sessionData)
        const onboardingPayload =  {
          message,
          sessionId,
          patientId,
          assistantId:assistant.id,
          flow_id: assistant.flowData.id,
          session_data: sessionData,
          previous_messages: previousMessages
        };
        
         if (patientHistory && patientHistory.summary) {
          onboardingPayload.patient_history = patientHistory.summary;
          console.log('Including patient history in request');
        }
        const vectorResponse = await axios.post(`${PYTHON_API_URL}/api/shared/vector_chat`,onboardingPayload);
        // const onboardingPayload = {
        //   message,
        //   sessionId,
        //   patientId,
        //   assistantId: assistant.id,
        //   flow_id: assistant.flowData.id,
        //   instruction_type: instructionType,
        //   session_data: sessionData,
        //   previous_messages: previousMessages
        // };
        
        // // Include patient history if available
        // if (patientHistory && patientHistory.summary) {
        //   onboardingPayload.patient_history = patientHistory.summary;
        //   console.log('Including patient history in request');
        // }
        // const onboardingResponse = await axios.post(`${PYTHON_API_URL}/api/patient_onboarding`, onboardingPayload);
        // const responseData = onboardingResponse.data;
        
        let responseData = vectorResponse.data;
        
        console.log('RESPONSE DATA FROM PYTHON', responseData);
        
        // Handle notification node if present in the response
        if (responseData.node_type === 'notificationNode') {
          try {
            const notificationResult = await handleNotificationNode(
              {
                message: responseData.message,
                notification_type: responseData.notification_type,
                title: responseData.title,
                schedule_type: responseData.schedule_type,
                scheduled_for: responseData.scheduled_for,
                assistant_id: responseData.assistant_id,
                survey_questions: responseData.survey_questions || []
              },
              shareData,
              patientId
            );
            
            // Update the response to indicate notification was processed
            responseData = {
              ...responseData,
              content: "Notification has been sent successfully.",
              notification_processed: true
            };
            
          } catch (error) {
            console.error('Error processing notification node:', error);
            responseData = {
              ...responseData,
              content: "There was an error processing the notification.",
              error: error.message
            };
          }
        }
        // Update session state with the state updates from Python
        if (responseData.state_updates) {
          await sessionRef.set(responseData.state_updates, { merge: true });
        }
        if (responseData.onboarding_status){
          await sessionRef.set({ onboardingStatus: responseData.onboarding_status }, { merge: true });
        }
        let isSurveyNode = false; // Track survey node processing

        // Update nextNodeId if provided
        await sessionRef.set({ currentNodeId: responseData.next_node_id }, { merge: true });

        if (responseData.next_node_id) {
          
          let surveyId = null; // Track surveyId for session storage  
          // NEW CODE: Check if the next node is a survey node
          const nextNode = assistant.flowData.nodes.find(node => node.id === responseData.next_node_id);
          if (nextNode && nextNode.type === 'surveyNode' && nextNode.data.surveyData && nextNode.data.surveyData.questions) {
            // Directly start the survey by immediately returning the first question
            isSurveyNode = true;
            const surveyQuestionaire = nextNode.data.surveyData.questions;
            const surveyQuestion = surveyQuestionaire[0];
            // const surveyId = nextNode.data.surveyData.id;
            surveyId = nextNode.data.surveyData.id; // Set surveyId
            console.log("NEXT NODE", nextNode.data)
            let responseContent = `Please answer this survey question: ${surveyQuestion.text}`;
                       
            // Append options if available
            if (surveyQuestion.options && surveyQuestion.options.length > 0) {
              responseContent += `\nOptions: ${surveyQuestion.options.join(', ')}`;
            }
            
            
            console.log("EXECUTING THE SURVEY", responseContent)
            // Initialize survey_responses array with empty first response
            
            await sessionRef.set({ 
              survey_responses: [], 
              currentNodeId: responseData.next_node_id 
            }, { merge: true });
            
            // Save the survey question as a new message
            // await saveMessages(
            //   shareId,
            //   shareData.userId || shareData.ownerId,
            //   sessionId,
            //   shareData.assistantId,
            //   message,
            //   { content: responseContent },
            //   [],
            //   patientId
            // );
            
            await saveMessages(
              shareId,
              shareData.userId || shareData.ownerId,
              sessionId,
              shareData.assistantId,
              message, // Original user message that led to this survey
              { content: responseContent }, // Survey question prompt
              [],
              patientId,
              surveyId // Pass surveyId
            );
            // Override the response to the user
            responseData.content = responseContent;
          }
        }
        

        // Save message to Firestore
        if (!isSurveyNode) {
          await saveMessages(
            shareId, 
            shareData.userId || shareData.ownerId,
            sessionId, 
            shareData.assistantId, 
            message, 
            { content: responseData.content }, 
            [], 
            patientId,
            null, // No surveyId
            responseData.onboarding_status // <--- CHANGE THIS LINE

          );
        }
        
        axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
          message: message,
          response: responseData.content,
          sessionId: sessionId,
          timestamp: new Date().toISOString()
        }).then(analyticsResponse => {
          console.log('Analytics recorded successfully:', analyticsResponse.data.analytics_id);
        }).catch(analyticsError => {
          console.error('Error recording analytics:', analyticsError.message);
          // Non-critical, so we just log the error
        });
        const translatedContent = await translateToLanguage(responseData.content, userLanguage);

        return res.json({ content: translatedContent });
        // return res.json({ content: responseData.content });
      } catch (vectorError) {
        console.error('Vector chat error:', vectorError.message);
        // Fall back to standard processor
      }
    }



    // // Fallback: use the standard flow processor
    // console.log('Using standard flow processor');
    // const flowProcessor = new EnhancedFlowProcessor(geminiService, firestore, vectors, shareData.userId || shareData.ownerId);
    
    // const response = await flowProcessor.processMessage(
    //   message,
    //   sessionId,
    //   assistant,
    //   { previousMessages }
    // );
    
    // Save message
    
    // await saveMessages(
    //   shareId, 
    //   sessionId, 
    //   shareData.assistantId, 
    //   message, 
    //   { content: response.content }, 
    //   []
    // );
    // return res.json({ content: response.content });
    
  } catch (error) {
    console.error('Shared chat error:', error);
    return res.status(500).json({
      error: 'Failed to process message',
      details: error.message
    });
  }
});

// GET /shared/patient/:patientId/chat-sessions - Fetch all sessions and history for a patient
router.get('/shared/patient/:patientId/chat-sessions', verifyToken, async (req, res) => {
  try {
    const { patientId } = req.params;
    const userId = req.user.id; // From verifyToken

    // Verify user access (e.g., doctor)
    const userDoc = await firestore.db.collection('users').doc(userId).get();
    if (!userDoc.exists || !userDoc.data().is_doctor) {
      return res.status(403).json({ error: 'Access denied: User is not a doctor' });
    }

    // Query chat_sessions by patientId
    const sessionsSnapshot = await firestore.db.collection('chat_sessions')
      .where('patientId', '==', patientId)
      .get();

    if (sessionsSnapshot.empty) {
      return res.status(200).json({ sessions: [], message: 'No chat sessions found' });
    }

    const sessions = [];
    for (const doc of sessionsSnapshot.docs) {
      const sessionData = doc.data();
      const { sessionId, shareId, assistantId, createdAt } = sessionData;

      // Fetch chat history using existing function
      // const messages = await firestore.getSharedChatHistory(shareId, sessionId);
      const messages = await firestore.getSharedChatHistory(shareId, sessionId, patientId);

      sessions.push({
        sessionId,
        shareId,
        assistantId,
        createdAt: createdAt ? createdAt.toDate() : new Date(),
        messages: messages.map(msg => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          createdAt: msg.createdAt ? msg.createdAt.toDate() : new Date(),
        })),
      });
    }

    res.json({ sessions });
  } catch (error) {
    console.error('Error fetching patient chat sessions:', error);
    res.status(500).json({
      error: 'Failed to fetch chat sessions',
      details: error.message,
    });
  }
});
//Current Final Working 04/15/2025
// router.post('/shared/:shareId/chat', validateSharedAccess, async (req, res) => {
//   try {
//       const { shareId } = req.params;
//       const { message, sessionId, language = 'en' } = req.body;
//       const shareData = req.shareData;

//       // Validate input
//       if (!message?.trim()) return res.status(400).json({ error: 'Message is required' });
//       if (!sessionId) return res.status(400).json({ error: 'Session ID is required' });

//       // Parallelize database calls
//       const [shareLink, assistant, shareSnapshot] = await Promise.all([
//           firestore.getShareLink(shareId),
//           firestore.getAssistant(shareData.assistantId),
//           firestore.db.collection('shared_links').where('shareId', '==', shareId).limit(1).get(),
//       ]);

//       if (!assistant) return res.status(404).json({ error: 'Assistant not found' });
//       if (shareSnapshot.empty) return res.status(404).json({ error: 'Share link not found' });

//       const shareDetails = shareSnapshot.docs[0].data();
//       const previousMessages = await firestore.getSharedChatHistory(shareId, sessionId);

//       // Initialize enhanced processor
//       const flowProcessor = new EnhancedFlowProcessor(geminiService, firestore, vectors, shareLink.userId || shareLink.ownerId);

//       // Process message using enhanced processor
//       const response = await flowProcessor.processMessage(
//           message,
//           sessionId,
//           assistant,
//           { previousMessages }
//       );

//       // Humanize the response
//       // const humanizedContent = await geminiService.humanizeResponse(response.content, previousMessages);
//       res.json({ content: response.content });
//       // Save the interaction (non-blocking)
//       saveMessages(shareId, shareLink.userId, sessionId, shareData.assistantId, message, { content: response.content }, []).catch(err => console.error('Error saving messages:', err));

//       // return res.json({ content: humanizedContent });

//   } catch (error) {
//       console.error('Shared chat error:', error);
//       return res.status(500).json({
//           error: 'Failed to process message',
//           details: error.message
//       });
//   }
// });

function buildContext(assistant, vectors, previousMessages, message) {
  const context = [];
  
  if (assistant.instructions) {
    context.push({
      role: 'system',
      content: `Instructions: ${assistant.instructions}`
    });
  }

  vectors.forEach(vec => {
    if (vec.metadata?.content) {
      context.push({
        role: 'system',
        content: `Content from ${vec.metadata.name}: ${vec.metadata.content}`
      });
    }
  });

  previousMessages.forEach(msg => {
    context.push({ role: msg.role, content: msg.content });
  });

  context.push({ role: 'user', content: message });
  return context;
}
// New endpoint for streaming TTS audio

// Endpoint to list available voices
router.get('/shared/voices', async (req, res) => {
  try {
    const [result] = await client.listVoices({});
    const voices = result.voices.map(voice => ({
      name: voice.name,
      languageCode: voice.languageCodes[0], // Use the first language code
      ssmlGender: voice.ssmlGender,
    }));
    res.json(voices);
  } catch (error) {
    console.error('Error listing voices:', error);
    res.status(500).json({ error: 'Failed to fetch voices' });
  }
});
router.get('/shared/:shareId/chat/audio', validateSharedAccess, async (req, res) => {
  try {
    const { text, language = 'en', voiceName } = req.query; // Use query parameters
    if (!text?.trim()) return res.status(400).json({ error: 'Text is required' });

    // Stream the TTS audio
    await streamTextToSpeech(text, language, res, voiceName);
  } catch (error) {
    console.error('TTS streaming error:', error);
    return res.status(500).json({
      error: 'Failed to stream TTS audio',
      details: error.message
    });
  }
});
router.post('/shared/:shareId/chat/audio', validateSharedAccess, async (req, res) => {
  try {
    const { text, language = 'en', voiceName } = req.body;
    if (!text?.trim()) return res.status(400).json({ error: 'Text is required' });

    // Stream the TTS audio
    await streamTextToSpeech(text, language, res, voiceName);
  } catch (error) {
    console.error('TTS streaming error:', error);
    return res.status(500).json({
      error: 'Failed to stream TTS audio',
      details: error.message
    });
  }
});
router.get('/share/:shareId/creator', async (req, res) => {
  try {
    const { shareId } = req.params;
    console.log('Received request for shareId:', shareId); // Debug log

    // Get share link first
    const shareLink = await firestore.getShareLink(shareId);
    console.log('Share link data:', shareLink); // Debug log
    
    if (!shareLink) {
      return res.status(404).json({ error: 'Share link not found' });
    }

    // Get creator using userId/ownerId from share link
    const userId = shareLink.userId || shareLink.ownerId;
    const creator = await firestore.getUser(userId);
    console.log('Creator data:', creator); // Debug log

    if (!creator) {
      return res.status(404).json({ error: 'Creator not found' });
    }

    // Return formatted creator info
    res.json({
      creator: {
        name: creator.name,
        profession: creator.profession || 'AI Assistant Creator',
        expertise: creator.expertise || ['AI', 'Machine Learning'],
        avatar: creator.avatar || null,
        bio: creator.bio || null,
        experience: creator.experience || '5+ years',
        email: creator.email
      }
    });
  } catch (error) {
    console.error('Error in /share/:shareId/creator:', error);
    res.status(500).json({ error: 'Failed to fetch creator info' });
  }
});

async function saveMessages(shareId, userId, sessionId, assistantId, userMessage, response, relevantVectors = [], patientId = null, surveyId = null) {
  // First save messages in transaction
  await firestore.runTransaction(async (transaction) => {
    await firestore.saveSharedChatMessage({
      shareId,
      sessionId,
      assistantId,
      role: 'user',
      content: userMessage,
      createdAt: new Date(),
      patientId,
      surveyId: surveyId || null // Include surveyId if provided
    });

    await firestore.saveSharedChatMessage({
      shareId,
      assistantId,
      role: 'assistant',
      sessionId,
      content: response.content,
      createdAt: new Date(),
      contextUsed: Array.isArray(relevantVectors) ? relevantVectors.map(vec => ({
        id: vec.id,
        type: vec.metadata.contentType || vec.metadata.type,
        similarity: vec.similarity,
        classification: vec.metadata.classification
      })) : [],
      patientId,
      surveyId: surveyId || null // Include surveyId if provided
    });

        // Update or create chat_sessions document with patientId
    const sessionRef = firestore.db.collection('chat_sessions').doc(sessionId);
    await sessionRef.set({
      sessionId,
      shareId,
      assistantId,
      userId,
      surveyId: surveyId || null, // Store surveyId in session if provided
      patientId: patientId || null, // Store patientId
      createdAt: new Date(),
      updatedAt: new Date(),
    }, { merge: true });
  });
  
  
  console.log('STORING USER ID', userId);
  // Process embeddings in background
  Promise.all([
    storeEmbeddingInBackground(firestore, sessionId, userId, userMessage, 'user'),
    storeEmbeddingInBackground(firestore, sessionId, userId, response.content, 'assistant')
  ]).catch(error => {
    console.error('Background embedding processing error:', error);
  });
}
//current working as of 04/15/2025
// async function saveMessages(shareId, userId, sessionId, assistantId, userMessage, response, relevantVectors) {
//   // First save messages in transaction
//   await firestore.runTransaction(async (transaction) => {
//     await firestore.saveSharedChatMessage({
//       shareId,
//       sessionId,
//       assistantId,
//       role: 'user',
//       content: userMessage,
//       createdAt: new Date()
//     });

//     await firestore.saveSharedChatMessage({
//       shareId,
//       assistantId,
//       role: 'assistant',
//       sessionId,
//       content: response.content,
//       createdAt: new Date(),
//       contextUsed: relevantVectors.map(vec => ({
//         id: vec.id,
//         type: vec.metadata.contentType || vec.metadata.type,
//         similarity: vec.similarity,
//         classification: vec.metadata.classification
//       }))
//     });
//   });
//   console.log('STORING USER ID', userId)
//   // Process embeddings in background
//   Promise.all([
//     storeEmbeddingInBackground(firestore, sessionId, userId, userMessage, 'user'),
//     storeEmbeddingInBackground(firestore, sessionId, userId, response.content, 'assistant')
//   ]).catch(error => {
//     console.error('Background embedding processing error:', error);
//   });
// }


// async function saveMessages(shareId, sessionId, assistantId, userMessage, response, relevantVectors) {
//   await firestore.runTransaction(async (transaction) => {
//     await firestore.saveSharedChatMessage({
//       shareId,
//       sessionId,
//       assistantId,
//       role: 'user',
//       content: userMessage,
//       createdAt: new Date()
//     });

//     await firestore.saveSharedChatMessage({
//       shareId,
//       assistantId,
//       role: 'assistant',
//       sessionId,
//       content: response.content,
//       createdAt: new Date(),
//       contextUsed: relevantVectors.map(vec => ({
//         id: vec.id,
//         type: vec.metadata.contentType || vec.metadata.type,
//         similarity: vec.similarity,
//         classification: vec.metadata.classification
//       }))
//     });
//   });
// }

// Get chat history for shared link
router.get('/shared/:shareId/chat-history', validateSharedAccess, async (req, res) => {

    try {
      console.log('loading chats',  req.params, req.query)
      const { shareId } = req.params;
      // const { sessionId } = req.query; // Get sessionId from query parameters
      const { sessionId, patientId } = req.query;
      console.log('loading chats',  sessionId, patientId)
      if (!sessionId) {
        return res.status(400).json({ error: 'Session ID is required' });
      }
      // Use the firestore service to get chat history
      // const messages = await firestore.getSharedChatHistory(shareId, sessionId);
      console.log('loading chats')

      const messages = await firestore.getSharedChatHistory(shareId, sessionId, patientId);

      res.json(messages);
    } catch (error) {
      console.error('Error fetching shared chat history:', error);
      res.status(500).json({ error: 'Failed to fetch chat history' });
    }
  });

  router.get('/shared/patient/:patientId/session/:sessionId', verifyToken, async (req, res) => {
    try {
      console.log('fetching session data');
      const { patientId, sessionId } = req.params;
      const userId = req.user.id;
      console.log('FETCHING [SESSION DATA]', patientId, sessionId)
      // Verify user access
      const userDoc = await firestore.db.collection('users').doc(userId).get();
      if (!userDoc.exists) {
        return res.status(403).json({ error: 'Access denied: User is not a doctor' });
      }
  
      // Fetch session
      const sessionDoc = await firestore.db.collection('chat_sessions')
        .doc(sessionId)
        .get();
      if (!sessionDoc.exists || sessionDoc.data().patientId !== patientId) {
        return res.status(404).json({ error: 'Session not found or not associated with patient' });
      }
  
      // Fetch messages
      // const messages = await firestore.getSharedChatHistory(sessionDoc.data().shareId, sessionId, patientId);
      const messagesSnapshot = await firestore.db.collection('shared_chat_messages')
      .where('sessionId', '==', sessionId)
      .where('patientId', '==', patientId)
      .orderBy('createdAt', 'asc')
      .get();
      
      const messages = messagesSnapshot.docs.map(doc => ({
        id: doc.id,
        role: doc.data().role,
        content: doc.data().content,
        createdAt: doc.data().createdAt instanceof Firestore.Timestamp
          ? doc.data().createdAt.toDate()
          : doc.data().createdAt instanceof Date
          ? doc.data().createdAt
          : new Date(),
      }));
      res.json({
        sessionId,
        shareId: sessionDoc.data().shareId,
        assistantId: sessionDoc.data().assistantId,
        createdAt: sessionDoc.data().createdAt instanceof Firestore.Timestamp
          ? sessionDoc.data().createdAt.toDate()
          : sessionDoc.data().createdAt || new Date(),
        messages,
      });
    } catch (error) {
      console.error('Error fetching patient session:', error);
      res.status(500).json({ error: 'Failed to fetch session', details: error.message });
    }
  });
  // New route - different from your existing one

router.get('/shared/patient/:patientId/sessions', verifyToken, async (req, res) => {
  try {
    const { patientId } = req.params;
    const userId = req.user.id;

    // Verify the user is a doctor
    const userDoc = await firestore.db.collection('users').doc(userId).get();
    if (!userDoc.exists) {
      return res.status(403).json({ error: 'Access denied: User is not a doctor' });
    }

    // Query for all sessions that belong to this patient
    const sessionsSnapshot = await firestore.db.collection('chat_sessions')
      .where('patientId', '==', patientId)
      .orderBy('createdAt', 'desc')
      .get();

    if (sessionsSnapshot.empty) {
      return res.json([]);
    }

    // Fetch message counts for each session
    const sessions = await Promise.all(sessionsSnapshot.docs.map(async doc => {
      const data = doc.data();
      const messagesSnapshot = await firestore.db.collection('shared_chat_messages')
        .where('sessionId', '==', doc.id)
        .where('patientId', '==', patientId)
        .get();
      const messageCount = messagesSnapshot.size;

      return {
        sessionId: doc.id,
        shareId: data.shareId,
        assistantId: data.assistantId,
        assistantName: data.assistantName || 'Assistant',
        createdAt: data.createdAt instanceof Firestore.Timestamp
          ? data.createdAt.toDate()
          : data.createdAt || new Date(),
        messageCount, // Add message count
      };
    }));

    res.json(sessions);
  } catch (error) {
    console.error('Error fetching patient sessions:', error);
    res.status(500).json({ error: 'Failed to fetch sessions' });
  }
});
  router.get('/calls/active', verifyToken, async (req, res) => {
    try {
      // Get the user ID from the authenticated request
      console.log(req.user)
      const userId = req.user.id;
      
      // Query active calls from Firestore where the user is the owner of the assistant
      const callsSnapshot = await firestore.db.collection('active_calls')
        .where('userId', '==', userId)
        .orderBy('startTime', 'desc')
        .get();
      
      const activeCalls = [];
      callsSnapshot.forEach(doc => {
        activeCalls.push({
          id: doc.id,
          ...doc.data()
        });
      });
      
      return res.json(activeCalls);
    } catch (error) {
      console.error('Error fetching active calls:', error);
      return res.status(500).json({
        error: 'Failed to fetch active calls',
        details: error.message
      });
    }
  });
  
  // Get specific call
  router.get('/calls/:callId',verifyToken, async (req, res) => {
    try {
      const { callId } = req.params;
      
      // Get call from Firestore
      const callDoc = await firestore.db.collection('active_calls').doc(callId).get();
      
      if (!callDoc.exists) {
        return res.status(404).json({ error: 'Call not found' });
      }
      
      // Check if the user has access to this call
      const call = callDoc.data();
      
      if (call.userId !== req.user.id) {
        return res.status(403).json({ error: 'Access denied to this call' });
      }
      
      return res.json({
        id: callDoc.id,
        ...call
      });
    } catch (error) {
      console.error('Error fetching call:', error);
      return res.status(500).json({
        error: 'Failed to fetch call',
        details: error.message
      });
    }
  });
  
  // Take over a call
  router.post('/calls/:callId/takeover', verifyToken,  async (req, res) => {
    try {
      const { callId } = req.params;
      const operatorId = req.user.id;
      const operatorName = req.user.name || 'Operator';
      
      // Get call from Firestore
      const callRef = firestore.db.collection('active_calls').doc(callId);
      const callDoc = await callRef.get();
      
      if (!callDoc.exists) {
        return res.status(404).json({ error: 'Call not found' });
      }
      
      // Check if the call can be taken over
      const call = callDoc.data();
      
      if (call.status !== 'ai-handling') {
        return res.status(400).json({ 
          error: 'This call is already being handled by an operator' 
        });
      }
      
      // Get the share ID associated with this call
      const shareId = call.shareId;
      if (!shareId) {
        return res.status(400).json({ error: 'No share ID associated with this call' });
      }
      
      // Update the call status
      await callRef.update({
        status: 'human-operator',
        operatorId,
        operatorName,
        takenOverAt: new Date()
      });
      
      // Log the takeover event
      await firestore.db.collection('call_events').add({
        callId,
        type: 'operator_takeover',
        operatorId,
        operatorName,
        timestamp: new Date(),
        shareId
      });
      
      // Notify the caller that an operator has taken over
      const twilioService = new TwilioService();
      try {
        const sessionId = call.sessionId;
        const assistantId = call.assistantId;
        
        // Send a message via TTS to inform the caller
        await twilioService.sendWhatsAppMessage(
          call.phoneNumber,
          `An operator has joined the conversation. They will assist you directly.`,
          shareId,
          sessionId,
          assistantId
        );
      } catch (twilioError) {
        console.error('Error sending takeover notification:', twilioError);
        // Continue with the takeover even if notification fails
      }
      
      return res.json({ 
        success: true,
        message: 'Call successfully taken over' 
      });
    } catch (error) {
      console.error('Error taking over call:', error);
      return res.status(500).json({
        error: 'Failed to take over call',
        details: error.message
      });
    }
  });
  
  // Get call messages/transcript
  router.get('/calls/:callId/messages', async (req, res) => {
    try {
      const { callId } = req.params;
      
      // Check if call exists and user has access
      const callDoc = await firestore.db.collection('active_calls').doc(callId).get();
      
      if (!callDoc.exists) {
        return res.status(404).json({ error: 'Call not found' });
      }
      
      const call = callDoc.data();
      if (call.userId !== req.user.id && call.operatorId !== req.user.id) {
        return res.status(403).json({ error: 'Access denied to this call' });
      }
      
      // Get messages from shared chat history
      const messagesSnapshot = await firestore.db.collection('shared_chat_messages')
        .where('sessionId', '==', call.sessionId)
        .orderBy('createdAt', 'asc')
        .get();
      
      const messages = [];
      messagesSnapshot.forEach(doc => {
        const msgData = doc.data();
        messages.push({
          id: doc.id,
          content: msgData.content,
          role: msgData.role === 'user' ? 'caller' : 'ai',
          timestamp: msgData.createdAt.toDate(),
          sessionId: msgData.sessionId
        });
      });
      
      // Also get any operator messages
      const operatorMessagesSnapshot = await firestore.db.collection('call_messages')
        .where('callId', '==', callId)
        .orderBy('timestamp', 'asc')
        .get();
      
      operatorMessagesSnapshot.forEach(doc => {
        const msgData = doc.data();
        messages.push({
          id: doc.id,
          content: msgData.content,
          role: 'operator',
          sender: msgData.operatorName,
          timestamp: msgData.timestamp.toDate(),
          operatorId: msgData.operatorId
        });
      });
      
      // Sort all messages by timestamp
      messages.sort((a, b) => a.timestamp - b.timestamp);
      
      return res.json(messages);
    } catch (error) {
      console.error('Error fetching call messages:', error);
      return res.status(500).json({
        error: 'Failed to fetch call messages',
        details: error.message
      });
    }
  });
  
  // Send a message in a call
  router.post('/calls/:callId/messages', async (req, res) => {
    try {
      const { callId } = req.params;
      const { content } = req.body;
      const operatorId = req.user.id;
      const operatorName = req.user.name || 'Operator';
      
      if (!content) {
        return res.status(400).json({ error: 'Message content is required' });
      }
      
      // Check if call exists and user has access
      const callDoc = await firestore.db.collection('active_calls').doc(callId).get();
      
      if (!callDoc.exists) {
        return res.status(404).json({ error: 'Call not found' });
      }
      
      const call = callDoc.data();
      if (call.status !== 'human-operator' || call.operatorId !== req.user.id) {
        return res.status(403).json({ error: 'Only the active operator can send messages' });
      }
      
      // Create new message in the call_messages collection
      const messageRef = await firestore.db.collection('call_messages').add({
        callId,
        content,
        role: 'operator',
        operatorId,
        operatorName,
        timestamp: new Date()
      });
      
      // Get the new message to return
      const newMessageDoc = await messageRef.get();
      
      // Update the call's lastActivity timestamp
      await firestore.db.collection('active_calls').doc(callId).update({
        lastActivity: new Date()
      });
      
      // Send the message to the caller using TTS via Twilio
      const twilioService = new TwilioService();
      try {
        const voiceName = call.voiceName || 'en-US-Wavenet-D';
        
        // Generate TTS audio URL for the operator's message
        const ttsAudioUrl = `${process.env.API_URL}/api/shared/${call.shareId}/chat/audio?text=${encodeURIComponent(content)}&language=en&voiceName=${voiceName}`;
        
        // Use Twilio to play this audio to the caller
        await twilioService.sendAudioToCall(call.twilioCallSid, ttsAudioUrl);
      } catch (twilioError) {
        console.error('Error sending audio message via Twilio:', twilioError);
        // Continue with saving the message even if the audio fails
      }
      
      return res.json({
        id: newMessageDoc.id,
        ...newMessageDoc.data(),
        timestamp: newMessageDoc.data().timestamp.toDate()
      });
    } catch (error) {
      console.error('Error sending call message:', error);
      return res.status(500).json({
        error: 'Failed to send message',
        details: error.message
      });
    }
  });
  
  // Toggle transcription
  router.post('/calls/:callId/transcription', async (req, res) => {
    try {
      const { callId } = req.params;
      const { enabled } = req.body;
      
      if (enabled === undefined) {
        return res.status(400).json({ error: 'Enabled status is required' });
      }
      
      // Check if call exists and user has access
      const callRef = firestore.db.collection('active_calls').doc(callId);
      const callDoc = await callRef.get();
      
      if (!callDoc.exists) {
        return res.status(404).json({ error: 'Call not found' });
      }
      
      const call = callDoc.data();
      if (call.status !== 'human-operator' || call.operatorId !== req.user.id) {
        return res.status(403).json({ error: 'Only the active operator can change transcription settings' });
      }
      
      // Update transcription settings
      await callRef.update({
        transcriptionEnabled: Boolean(enabled),
        updatedAt: new Date()
      });
      
      // Update Twilio call settings
      const twilioService = new TwilioService();
      try {
        await twilioService.updateCallTranscription(call.twilioCallSid, Boolean(enabled));
      } catch (twilioError) {
        console.error('Error updating Twilio transcription:', twilioError);
        // Continue with updating the DB record even if Twilio update fails
      }
      
      return res.json({ 
        success: true,
        transcriptionEnabled: Boolean(enabled)
      });
    } catch (error) {
      console.error('Error toggling transcription:', error);
      return res.status(500).json({
        error: 'Failed to toggle transcription',
        details: error.message
      });
    }
  });
  
  // End a call
  router.post('/calls/:callId/end', async (req, res) => {
    try {
      const { callId } = req.params;
      const operatorId = req.user.id;
      
      // Check if call exists and user has access
      const callRef = firestore.db.collection('active_calls').doc(callId);
      const callDoc = await callRef.get();
      
      if (!callDoc.exists) {
        return res.status(404).json({ error: 'Call not found' });
      }
      
      const call = callDoc.data();
      if (call.status !== 'human-operator' || call.operatorId !== req.user.id) {
        return res.status(403).json({ error: 'Only the active operator can end this call' });
      }
      
      // End the call in Twilio
      const twilioService = new TwilioService();
      try {
        await twilioService.endCall(call.twilioCallSid);
      } catch (twilioError) {
        console.error('Error ending call in Twilio:', twilioError);
        // Continue with updating the DB record even if Twilio call fails
      }
      
      // Update call status
      await callRef.update({
        status: 'ended',
        endTime: new Date(),
        endedBy: 'operator',
        endedById: operatorId
      });
      
      // Log the end event
      await firestore.db.collection('call_events').add({
        callId,
        type: 'call_ended',
        operatorId,
        timestamp: new Date(),
        shareId: call.shareId
      });
      
      return res.json({ 
        success: true,
        message: 'Call ended successfully' 
      });
    } catch (error) {
      console.error('Error ending call:', error);
      return res.status(500).json({
        error: 'Failed to end call',
        details: error.message
      });
    }
  });
  

  //whatsapp or sms call takeover
  // Add these routes after existing routes in shared-chat.js

// GET /sessions/active - List active WhatsApp and SMS sessions for the doctor
// Timezone-agnostic route for active sessions
// Final fix for active sessions route
// Final route that shows ALL active sessions regardless of takeover status
// Modified route to return only most recent WhatsApp and SMS sessions for each patient
router.get('/shared/patient/:patientId/active-sessions', verifyToken, async (req, res) => {
  try {
    const { patientId } = req.params;
    
    // Get all recent sessions for this patient
    const allSessionsSnapshot = await firestore.db.collection('chat_sessions')
      .where('patientId', '==', patientId)
      .orderBy('lastActivity', 'desc') // Most recent first
      .get();

    console.log(`Found ${allSessionsSnapshot.size} total sessions for patient ${patientId}`);
    
    // We'll find the most recent WhatsApp and SMS sessions
    let mostRecentWhatsApp = null;
    let mostRecentSMS = null;
    
    allSessionsSnapshot.forEach(doc => {
      const data = doc.data();
      const sessionId = doc.id;
      
      // Determine session type
      let type = data.type;
      if (!type) {
        if (sessionId.startsWith('whatsapp_')) {
          type = 'whatsapp';
        } else if (sessionId.startsWith('sms_')) {
          type = 'sms';
        } else {
          type = 'unknown';
        }
      }
      
      // Skip if not WhatsApp or SMS
      if (type !== 'whatsapp' && type !== 'sms') {
        return;
      }
      
      // Convert lastActivity to a JS Date
      let lastActivityDate;
      if (data.lastActivity) {
        if (data.lastActivity.toDate) {
          lastActivityDate = data.lastActivity.toDate();
        } else if (data.lastActivity.seconds) {
          lastActivityDate = new Date(data.lastActivity.seconds * 1000);
        } else if (data.lastActivity instanceof Date) {
          lastActivityDate = data.lastActivity;
        } else {
          lastActivityDate = new Date();
        }
      } else {
        lastActivityDate = new Date();
      }
      
      // Create session object
      const sessionObj = {
        sessionId: doc.id,
        type,
        phoneNumber: data.phoneNumber || 'Unknown',
        patientId: data.patientId || null,
        lastActivity: lastActivityDate,
        assistantId: data.assistantId,
        takenOverBy: data.takenOverBy || null,
        takenOverAt: data.takenOverAt ? 
          (data.takenOverAt.toDate ? data.takenOverAt.toDate() : new Date(data.takenOverAt)) : 
          null,
        userId: data.userId || null,
        shareId: data.shareId || null
      };
      
      // Keep only the most recent session for each type
      if (type === 'whatsapp' && (!mostRecentWhatsApp || lastActivityDate > mostRecentWhatsApp.lastActivity)) {
        mostRecentWhatsApp = sessionObj;
      } else if (type === 'sms' && (!mostRecentSMS || lastActivityDate > mostRecentSMS.lastActivity)) {
        mostRecentSMS = sessionObj;
      }
    });
    
    // Combine the results
    const mostRecentSessions = [];
    if (mostRecentWhatsApp) mostRecentSessions.push(mostRecentWhatsApp);
    if (mostRecentSMS) mostRecentSessions.push(mostRecentSMS);
    
    console.log(`Returning ${mostRecentSessions.length} most recent sessions for patient ${patientId}`);
    res.json(mostRecentSessions);
  } catch (error) {
    console.error(`Error fetching active sessions for patient:`, error);
    res.status(500).json({ error: 'Failed to fetch active sessions' });
  }
});

router.get('/shared/sessions/active', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const cutoffTime = new Date(Date.now() - 10 * 60 * 1000); // Last 10 minutes

    console.log('Looking for active sessions for user ID:', userId);

    // First approach: Get assistants owned by this user
    const assistantsSnapshot = await firestore.db.collection('assistants')
      .where('userId', '==', userId)
      .get();
    
    const assistantIds = [];
    assistantsSnapshot.forEach(doc => {
      assistantIds.push(doc.id);
    });
    
    console.log('Found assistants owned by user:', assistantIds);

    // If no assistants found, try looking directly for sessions with this userId
    let sessionsSnapshot;
    let queriesRun = [];
    
    if (assistantIds.length > 0) {
      // Query for sessions with these assistantIds
      console.log('Searching for sessions with assistantIds:', assistantIds);
      sessionsSnapshot = await firestore.db.collection('chat_sessions')
        .where('assistantId', 'in', assistantIds)
        .where('lastActivity', '>', cutoffTime)
        .get();
      queriesRun.push('by assistantId');
    } else {
      sessionsSnapshot = { empty: true, docs: [] };
    }
    
    // Also look for sessions directly owned by this user
    console.log('Searching for sessions with userId:', userId);
    const userSessionsSnapshot = await firestore.db.collection('chat_sessions')
      .where('userId', '==', userId)
      .where('lastActivity', '>', cutoffTime)
      .get();
    queriesRun.push('by userId');
    
    // Combine the results
    const allDocs = [...sessionsSnapshot.docs, ...userSessionsSnapshot.docs];
    const uniqueSessionIds = new Set();
    const activeSessions = [];
    
    // Process and filter the sessions
    for (const doc of allDocs) {
      const data = doc.data();
      const sessionId = doc.id;
      
      // Skip if we've already processed this session
      if (uniqueSessionIds.has(sessionId)) continue;
      uniqueSessionIds.add(sessionId);
      
      // Check if it's a WhatsApp or SMS session based on sessionId pattern or type field
      const isWhatsAppOrSMS = 
        (data.type === 'whatsapp' || data.type === 'sms') ||
        (data.sessionId?.startsWith('whatsapp_') || data.sessionId?.startsWith('sms_')) ||
        (sessionId.startsWith('whatsapp_') || sessionId.startsWith('sms_'));
      
      // Check if it's not taken over
      const notTakenOver = data.takenOverBy === null || data.takenOverBy === undefined;
      
      if (isWhatsAppOrSMS && notTakenOver) {
        // Determine type from sessionId if not explicitly set
        let type = data.type;
        if (!type) {
          if (data.sessionId?.startsWith('whatsapp_') || sessionId.startsWith('whatsapp_')) {
            type = 'whatsapp';
          } else if (data.sessionId?.startsWith('sms_') || sessionId.startsWith('sms_')) {
            type = 'sms';
          } else {
            type = 'unknown';
          }
        }
        
        activeSessions.push({
          sessionId: sessionId,
          type: type,
          phoneNumber: data.phoneNumber || 'Unknown',
          patientId: data.patientId || null,
          lastActivity: data.lastActivity.toDate(),
          assistantId: data.assistantId,
        });
      }
    }

    console.log(`Found ${activeSessions.length} active sessions using queries: ${queriesRun.join(', ')}`);
    
    if (activeSessions.length === 0) {
      // Debug: List a few recent sessions regardless of type/takeover status
      console.log('Performing fallback query to check for recent sessions');
      const recentSessionsSnapshot = await firestore.db.collection('chat_sessions')
        .orderBy('lastActivity', 'desc')
        .limit(5)
        .get();
      
      if (!recentSessionsSnapshot.empty) {
        console.log('Recent sessions found:');
        recentSessionsSnapshot.forEach(doc => {
          const data = doc.data();
          console.log({
            sessionId: doc.id,
            type: data.type || 'not set',
            phoneNumber: data.phoneNumber || 'not set',
            lastActivity: data.lastActivity ? data.lastActivity.toDate() : 'not set',
            assistantId: data.assistantId || 'not set',
            userId: data.userId || 'not set',
            takenOverBy: data.takenOverBy || 'not set'
          });
        });
      } else {
        console.log('No recent sessions found at all');
      }
    }

    res.json(activeSessions);
  } catch (error) {
    console.error('Error fetching active sessions:', error);
    res.status(500).json({ error: 'Failed to fetch active sessions' });
  }
});

// POST /sessions/:sessionId/takeover - Doctor takes over a session
// Modified takeover route that works with inferred session types and doesn't check userId
// Modified takeover route that allows re-takeover of already taken over sessions
router.post('/shared/sessions/:sessionId/takeover', verifyToken, async (req, res) => {
  try {
    const { sessionId } = req.params;
    const userId = req.user.id;

    console.log(`Attempting to take over session ${sessionId} by user ${userId}`);

    const sessionRef = firestore.db.collection('chat_sessions').doc(sessionId);
    const sessionDoc = await sessionRef.get();
    if (!sessionDoc.exists) {
      console.log(`Session ${sessionId} not found`);
      return res.status(404).json({ error: 'Session not found' });
    }
    
    const session = sessionDoc.data();
    console.log(`Session data:`, {
      sessionId,
      phoneNumber: session.phoneNumber,
      patientId: session.patientId,
      type: session.type,
      userId: session.userId,
      takenOverBy: session.takenOverBy
    });
    
        // Check if the session is within the 5-minute window
        const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
        let lastActivityDate;
        if (session.lastActivity) {
          if (session.lastActivity.toDate) {
            lastActivityDate = session.lastActivity.toDate();
          } else if (session.lastActivity.seconds) {
            lastActivityDate = new Date(session.lastActivity.seconds * 1000);
          } else if (session.lastActivity instanceof Date) {
            lastActivityDate = session.lastActivity;
          } else {
            lastActivityDate = new Date();
          }
        } else {
          lastActivityDate = new Date();
        }
        
        const isWithinFiveMinutes = lastActivityDate >= fiveMinutesAgo;
        console.log(`Session lastActivity: ${lastActivityDate}, Five-minute cutoff: ${fiveMinutesAgo}`);
        console.log(`Session is within 5-minute window: ${isWithinFiveMinutes}`);
        
        if (!isWithinFiveMinutes) {
          console.log(`Session ${sessionId} is older than 5 minutes`);
          return res.status(403).json({ error: 'Session is too old for takeover (older than 5 minutes)' });
        }
        
    // Determine session type if not explicitly set
    let sessionType = session.type;
    if (!sessionType) {
      if (sessionId.startsWith('whatsapp_')) {
        sessionType = 'whatsapp';
      } else if (sessionId.startsWith('sms_')) {
        sessionType = 'sms';
      } else {
        sessionType = 'unknown';
      }
    }
    
    console.log(`Inferred session type: ${sessionType}`);
    
    // Check if valid WhatsApp/SMS session
    if (sessionType !== 'whatsapp' && sessionType !== 'sms') {
      console.log(`Session ${sessionId} is not a WhatsApp or SMS session`);
      return res.status(403).json({ error: 'Not a valid takeover session' });
    }
    
    // Allow re-taking over if the same doctor is doing it
    if (session.takenOverBy && session.takenOverBy !== userId) {
      console.log(`Session ${sessionId} already taken over by different user: ${session.takenOverBy}`);
      return res.status(400).json({ error: 'Session already taken over by another doctor' });
    }
    
    // Even if already taken over by this doctor, update the timestamp
    await sessionRef.update({
      takenOverBy: userId,
      takenOverAt: new Date(),
      lastActivity: new Date(), // Update lastActivity to keep it current
      type: sessionType // Explicitly set the type field
    });

    console.log(`Session ${sessionId} taken over successfully by ${userId}`);
    res.json({ 
      success: true,
      sessionId,
      sessionType,
      wasAlreadyTakenOver: !!session.takenOverBy
    });
  } catch (error) {
    console.error('Error taking over session:', error);
    res.status(500).json({ error: 'Failed to take over session' });
  }
});

// POST /sessions/:sessionId/respond - Doctor sends a manual response
router.post('/shared/sessions/:sessionId/respond', verifyToken, async (req, res) => {
  try {
    const { sessionId } = req.params;
    const { message } = req.body;
    const userId = req.user.id;

    if (!message?.trim()) {
      return res.status(400).json({ error: 'Message is required' });
    }

    const sessionRef = firestore.db.collection('chat_sessions').doc(sessionId);
    const sessionDoc = await sessionRef.get();
    if (!sessionDoc.exists) {
      return res.status(404).json({ error: 'Session not found' });
    }
    const session = sessionDoc.data();
    if (session.takenOverBy !== userId) {
      return res.status(403).json({ error: 'Not authorized' });
    }

    const twilioService = new TwilioService();
    if (session.type === 'whatsapp') {
      await twilioService.sendWhatsAppMessage(
        `whatsapp:${session.phoneNumber}`,
        message,
        session.shareId,
        sessionId,
        session.assistantId,
        session.patientId,
        true // skipSave
      );
    } else if (session.type === 'sms') {
      await twilioService.sendSmsMessage(
        session.phoneNumber,
        message,
        session.shareId,
        sessionId,
        session.assistantId,
        session.patientId,
        true
      );
    }

    // Save the operator's message
    await firestore.saveSharedChatMessage({
      shareId: session.shareId,
      sessionId,
      assistantId: session.assistantId,
      role: 'operator',
      content: message,
      createdAt: new Date(),
      patientId: session.patientId || null,
    });

    // Update lastActivity
    await sessionRef.update({ lastActivity: new Date() });

    res.json({ success: true });
  } catch (error) {
    console.error('Error sending response:', error);
    res.status(500).json({ error: 'Failed to send response' });
  }
});

// Add this route to your shared-chat.js file

// POST /shared/sessions/new - Start a new doctor-initiated patient session
// Updated route that doesn't require an assistant for doctor-initiated chats
router.post('/shared/sessions/new', verifyToken, async (req, res) => {
  try {
    console.log('→ ROUTE HIT: /shared/sessions/new'); 
    console.log('→ Request body:', req.body);
    console.log('→ Request user:', req.user);
    
    const { patientId, messageType = 'whatsapp', patientName, phoneNumber } = req.body;
    console.log('→ Extracted patientId:', patientId);
    console.log('→ Extracted messageType:', messageType);
    console.log('→ Extracted patientName:', patientName);
    console.log('→ Extracted phoneNumber:', phoneNumber);
    
    const userId = req.user.id;
    console.log('→ Extracted userId:', userId);

    // Validate inputs
    if (!patientId) {
      console.log('→ ERROR: Patient ID is required');
      return res.status(400).json({ error: 'Patient ID is required' });
    }

    if (!phoneNumber) {
      console.log('→ ERROR: Phone number is required');
      return res.status(400).json({ error: 'Phone number is required' });
    }

    if (messageType !== 'whatsapp' && messageType !== 'sms') {
      console.log('→ ERROR: Invalid message type:', messageType);
      return res.status(400).json({ error: 'Message type must be "whatsapp" or "sms"' });
    }

    // Try to find an assistant for this user - but it's optional
    console.log('→ Checking if user has an active assistant (optional)');
    const assistantsSnapshot = await firestore.db.collection('assistants')
      .where('userId', '==', userId)
      .where('isActive', '==', true)
      .limit(1)
      .get();

    let assistantId, shareId;
    
    // If an assistant exists, use its ID and share ID
    if (!assistantsSnapshot.empty) {
      const assistant = assistantsSnapshot.docs[0].data();
      assistantId = assistantsSnapshot.docs[0].id;
      console.log('→ Found assistant with ID:', assistantId);
      
      if (assistant.voiceShareId) {
        shareId = assistant.voiceShareId;
        console.log('→ Using assistant shareId:', shareId);
      } else {
        // Generate a temporary shareId
        shareId = 'doc-' + userId.substring(0, 8) + '-' + Date.now();
        console.log('→ Assistant has no voice share, creating temporary shareId:', shareId);
      }
    } else {
      // Generate temporary IDs if no assistant found
      assistantId = 'doc-' + userId.substring(0, 8);
      shareId = 'share-' + userId.substring(0, 8) + '-' + Date.now();
      console.log('→ No active assistant found, using generated IDs');
      console.log('→ Generated assistantId:', assistantId);
      console.log('→ Generated shareId:', shareId);
    }

    // Format phone number removing non-numeric chars
    const formattedPhoneNumber = phoneNumber.replace(/[^0-9]/g, '');
    console.log('→ Formatted phone number:', formattedPhoneNumber);

    // Create session ID in the same format as in the webhook routes
    // This is CRITICAL for the webhooks to recognize this as the same session
    const baseSessionId = `${messageType}_${formattedPhoneNumber}_${assistantId}`;
    const sessionId = `${baseSessionId}_${Date.now()}`;
    console.log('→ Generated sessionId:', sessionId);

    // Create the session document with proper takeover flags
    console.log('→ Creating chat session in Firestore');
    await firestore.db.collection('chat_sessions').doc(sessionId).set({
      sessionId,
      type: messageType,
      phoneNumber: formattedPhoneNumber,
      patientId,
      assistantId,
      shareId,
      userId,
      createdAt: new Date(),
      lastActivity: new Date(),
      takenOverBy: userId, // CRITICAL - this must be set for takeover
      takenOverAt: new Date(), // CRITICAL - this must be set for takeover
      isActive: true,
      createdByDoctor: true
    });
    console.log('→ Chat session created successfully with takenOverBy:', userId);

    // Create initial system message
    const displayName = patientName || `Patient ${patientId}`;
    console.log('→ Patient display name:', displayName);
    
    console.log('→ Creating initial system message');
    await firestore.saveSharedChatMessage({
      shareId,
      sessionId,
      assistantId,
      role: 'system',
      content: `Doctor-initiated conversation with ${displayName}`,
      createdAt: new Date(),
      patientId
    });
    console.log('→ Initial system message created successfully');

    // Return the session info
    console.log('→ Returning success response');
    res.json({
      success: true,
      sessionId,
      shareId,
      assistantId,
      phoneNumber: formattedPhoneNumber,
      patientId,
      messageType,
      takenOverBy: userId // Include this in the response
    });
    
  } catch (error) {
    console.error('→ ERROR: Exception in route handler:', error);
    console.error('→ Error stack:', error.stack);
    res.status(500).json({
      error: 'Failed to create new session',
      details: error.message
    });
  }
});

// Update the existing route to support doctor-initiated messages
// This enhances the existing respondToSession route to handle first message logic
router.post('/shared/doctorsessions/:sessionId/respond', verifyToken, async (req, res) => {
  try {
    const { sessionId } = req.params;
    const { message } = req.body;
    const userId = req.user.id;

    if (!message?.trim()) {
      return res.status(400).json({ error: 'Message is required' });
    }

    const sessionRef = firestore.db.collection('chat_sessions').doc(sessionId);
    const sessionDoc = await sessionRef.get();
    
    if (!sessionDoc.exists) {
      return res.status(404).json({ error: 'Session not found' });
    }
    
    const session = sessionDoc.data();
    
    if (session.takenOverBy !== userId) {
      return res.status(403).json({ error: 'Not authorized to respond to this session' });
    }

    const twilioService = new TwilioService();
    
    // Check if this is the first message in a doctor-initiated conversation
    const messagesSnapshot = await firestore.db.collection('shared_chat_messages')
      .where('sessionId', '==', sessionId)
      .where('role', 'in', ['user', 'assistant', 'operator'])
      .limit(2)
      .get();
    
    // If only the system welcome message exists, this is the first real message
    const isFirstMessage = messagesSnapshot.size <= 1;
    
    // For the first message in a doctor-initiated conversation, 
    // we need to add some context about who is messaging
    let messageToSend = message;
    if (isFirstMessage && session.createdByDoctor) {
      // Get doctor name for personalization
      const doctorDoc = await firestore.db.collection('users').doc(userId).get();
      let doctorName = 'Your doctor';
      
      if (doctorDoc.exists) {
        const doctorData = doctorDoc.data();
        if (doctorData.name) {
          doctorName = doctorData.name;
        }
      }
      
      // Add a greeting prefix if this is the first message
      messageToSend = `This is ${doctorName}. ${message}`;
    }

    // Send the message via appropriate channel
    if (session.type === 'whatsapp') {
      await twilioService.sendWhatsAppMessage(
        `whatsapp:${session.phoneNumber}`,
        messageToSend,
        session.shareId,
        sessionId,
        session.assistantId,
        session.patientId,
        true // skipSave parameter
      );
    } else if (session.type === 'sms') {
      await twilioService.sendSmsMessage(
        session.phoneNumber,
        messageToSend,
        session.shareId,
        sessionId,
        session.assistantId,
        session.patientId,
        true // skipSave parameter
      );
    }

    // Save the operator's message to the database
    await firestore.saveSharedChatMessage({
      shareId: session.shareId,
      sessionId,
      assistantId: session.assistantId,
      role: 'operator',
      content: message, // Save the original message without the greeting prefix
      createdAt: new Date(),
      patientId: session.patientId || null,
    });

    // Update lastActivity
    await sessionRef.update({ lastActivity: new Date() });

    res.json({ success: true });
  } catch (error) {
    console.error('Error sending response:', error);
    res.status(500).json({ error: 'Failed to send response' });
  }
});
export default router;


