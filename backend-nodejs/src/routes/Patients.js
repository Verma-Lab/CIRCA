import express from 'express';
import firestore from '../services/db/firestore.js';
import { TwilioService } from '../utils/twilioService.js';
import { v4 as uuidv4 } from 'uuid';
import cron from 'node-cron'; // Add this import at the top

const router = express.Router();


// Add this scheduler at the top level of your file
const notificationScheduler = cron.schedule('*/2 * * * *', 
    async () => {
    console.log('Running scheduled notification check:', new Date().toISOString());
    
    try {
      // Get all scheduled notifications where:
      // 1. They have a scheduledFor time
      // 2. That time is in the past
      // 3. They haven't been sent yet (sentAt is null)
      const now = new Date().toISOString();
      const scheduledNotificationsSnapshot = await firestore.db.collection('patient_notifications')
        .where('scheduledFor', '<=', now)
        .where('sentAt', '==', null)
        .where('status', '==', 'scheduled')
        .limit(50) // Process in batches of 50
        .get();
      
      if (scheduledNotificationsSnapshot.empty) {
        console.log('No scheduled notifications to send');
        return;
      }
      
      console.log(`Found ${scheduledNotificationsSnapshot.size} scheduled notifications to send`);
      
      // Process each notification that needs to be sent
      const twilioService = new TwilioService();
      const sendPromises = scheduledNotificationsSnapshot.docs.map(async (doc) => {
        const notification = doc.data();
        console.log(`Processing scheduled notification: ${doc.id}`, notification);
        
        try {
          // Get the patient phone number
          const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
            .where('patientId', '==', notification.patientId)
            .limit(1)
            .get();
          
          if (mappingSnapshot.empty) {
            console.error(`Patient ${notification.patientId} does not have a phone number configured`);
            
            // Mark as failed
            await firestore.db.collection('patient_notifications').doc(doc.id).update({
              status: 'failed',
              failureReason: 'Patient does not have a phone number configured',
              failedAt: new Date().toISOString()
            });
            
            return;
          }
          
          const phoneMapping = mappingSnapshot.docs[0].data();
          const phoneNumber = phoneMapping.phoneNumber;
          
          // Create a unique session ID for this notification
          const sessionId = `notification_${doc.id}_${Date.now()}`;
          const assistantId = notification.assistantId || ''

          // Send the message via Twilio
          if (notification.messageType === 'whatsapp') {
            await twilioService.sendWhatsAppMessage(
              `whatsapp:+1${phoneNumber}`,
              `${notification.title}\n\n${notification.message}`,
              null,
              sessionId,
              notification.assistantId,
              notification.patientId
            );
          } else {
            await twilioService.sendSmsMessage(
              `+1${phoneNumber}`,
              `${notification.title}\n\n${notification.message}`,
              null,
              sessionId,
              notification.assistantId,
              notification.patientId
            );
          }
          
          // Save the message to chat_sessions for history
          await firestore.db.collection('chat_sessions').doc(sessionId).set({
            sessionId,
            assistantId: notification.assistantId,
            patientId: notification.patientId,
            phoneNumber,
            type: notification.messageType === 'whatsapp' ? 'whatsapp' : 'sms',
            lastActivity: new Date(),
            notificationId: doc.id,
            isNotification: true,
            scheduledNotification: true,
            surveyQuestions: notification.surveyQuestions || [], // Add this
          });
          
          // Update notification as sent
          await firestore.db.collection('patient_notifications').doc(doc.id).update({
            sentAt: new Date().toISOString(),
            status: 'sent',
            sessionId,
            phoneNumber
          });
          
          console.log(`Successfully sent scheduled notification: ${doc.id}`);
        } catch (error) {
          console.error(`Error sending scheduled notification ${doc.id}:`, error);
          
          // Mark as failed
          await firestore.db.collection('patient_notifications').doc(doc.id).update({
            status: 'failed',
            failureReason: error.message || 'Unknown error',
            failedAt: new Date().toISOString()
          });
        }
      });
      
      await Promise.all(sendPromises);
      console.log('Completed processing scheduled notifications');
    } catch (error) {
      console.error('Error in notification scheduler:', error);
    }
  },
{
  timezone: 'America/New_York', // Replace with your desired timezone
}

);
  
  // Start the scheduler
notificationScheduler.start();
console.log('Notification scheduler started');

  
router.post('/patients/:patientId/assign-phone', async (req, res) => {
  try {
    const { patientId } = req.params;
    const { phoneNumber, assistantId } = req.body;

    if (!phoneNumber) {
      return res.status(400).json({ error: 'phoneNumber and assistantId are required' });
    }

    await firestore.db.collection('patient_phone_mappings').doc().set({
      phoneNumber,
      patientId,
      assistantId:assistantId||'',
      createdAt: new Date().toISOString()
    });

    res.json({ success: true });
  } catch (error) {
    console.error('Error assigning phone number:', error);
    res.status(500).json({ error: 'Failed to assign phone number' });
  }
});
router.get('/patients/:patientId/phone-mapping', async (req, res) => {
    try {
      const { patientId } = req.params;
      const snapshot = await firestore.db.collection('patient_phone_mappings')
        .where('patientId', '==', patientId)
        .limit(1)
        .get();
      if (snapshot.empty) {
        return res.json({});
      }
      const mapping = snapshot.docs[0].data();
      res.json(mapping);
    } catch (error) {
      console.error('Error fetching phone mapping:', error);
      res.status(500).json({ error: 'Failed to fetch phone mapping' });
    }
  });

 
  router.get('/patients/:patientId/notifications', async (req, res) => {
    try {
      const { patientId } = req.params;
      
      const snapshot = await firestore.db.collection('patient_notifications')
        .where('patientId', '==', patientId)
        .orderBy('createdAt', 'desc')
        .get();
      
      if (snapshot.empty) {
        return res.json([]);
      }
      
      const notifications = snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
      }));
      
      res.json(notifications);
    } catch (error) {
      console.error('Error fetching notifications:', error);
      res.status(500).json({ error: 'Failed to fetch notifications' });
    }
  });
  
  // Get notification count
  router.get('/patients/:patientId/notifications/count', async (req, res) => {
    try {
      const { patientId } = req.params;
      
      const snapshot = await firestore.db.collection('patient_notifications')
        .where('patientId', '==', patientId)
        .count()
        .get();
      
      const count = snapshot.data().count;
      
      res.json({ count });
    } catch (error) {
      console.error('Error fetching notification count:', error);
      res.status(500).json({ error: 'Failed to fetch notification count' });
    }
  });
  
  // Create a new notification
  router.post('/patients/:patientId/notifications', async (req, res) => {
    try {
      const { patientId } = req.params;
      const { title, message, scheduledFor, messageType, assistantId, surveyQuestions } = req.body;
      
      if (!title || !message) {
        return res.status(400).json({ error: 'Title and message are required' });
      }
      
      // Check if patient exists and has a phone number
      const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        .where('patientId', '==', patientId)
        .limit(1)
        .get();
      
      if (mappingSnapshot.empty) {
        return res.status(400).json({ error: 'Patient does not have a phone number configured' });
      }
      
      const phoneMapping = mappingSnapshot.docs[0].data();
      const phoneNumber = phoneMapping.phoneNumber;
      
      // Get default assistant for the patient if available
      let effectiveAssistantId = assistantId || null;
      if (!effectiveAssistantId) {
        const assistantSnapshot = await firestore.db.collection('assistants')
          .where('category', '==', 'default')
          .limit(1)
          .get();
        if (!assistantSnapshot.empty) {
          effectiveAssistantId = assistantSnapshot.docs[0].id;
        }
      }
      
      // Create notification document
      const notificationId = uuidv4();
      const notification = {
        id: notificationId,
        patientId,
        phoneNumber, // Add phoneNumber
        title,
        message,
        createdAt: new Date().toISOString(),
        scheduledFor: scheduledFor || null,
        messageType: messageType || 'whatsapp',
        sentAt: null,
        status: scheduledFor ? 'scheduled' : 'pending',
        assistantId: effectiveAssistantId,
        surveyQuestions: surveyQuestions || [], // Add this 
      };
      
      await firestore.db.collection('patient_notifications').doc(notificationId).set(notification);
      
      // If not scheduled for later, send immediately
      if (!scheduledFor) {
        const twilioService = new TwilioService();
        
        // Create a unique session ID for this notification
        const sessionId = `notification_${notificationId}_${Date.now()}`;
        
        if (messageType === 'whatsapp') {
          await twilioService.sendWhatsAppMessage(
            `whatsapp:+1${phoneNumber}`,
            `${title}\n\n${message}`, // Include title in the message
            null, // shareId (we're not using shares for notifications)
            sessionId,
            effectiveAssistantId,
            patientId
          );
        } else {
          await twilioService.sendSmsMessage(
            `+1${phoneNumber}`,
            `${title}\n\n${message}`, // Include title in the message
            null, // shareId (we're not using shares for notifications)
            sessionId,
            effectiveAssistantId,
            patientId
          );
        }
        
        // Save the message to chat_sessions for history
        await firestore.db.collection('chat_sessions').doc(sessionId).set({
          sessionId,
          assistantId: effectiveAssistantId,
          patientId,
          phoneNumber,
          type: messageType === 'whatsapp' ? 'whatsapp' : 'sms',
          lastActivity: new Date(),
          notificationId,
          isNotification: true,
          surveyQuestions: surveyQuestions || [], // Add this
        });
        
        // Update notification as sent
        await firestore.db.collection('patient_notifications').doc(notificationId).update({
          sentAt: new Date().toISOString(),
          status: 'sent',
          sessionId
        });
        
        notification.sentAt = new Date().toISOString();
        notification.status = 'sent';
        notification.sessionId = sessionId;
      }
      
      res.status(201).json(notification);
    } catch (error) {
      console.error('Error creating notification:', error);
      res.status(500).json({ error: 'Failed to create notification' });
    }
  });
  
  // Update a notification
  router.put('/patients/:patientId/notifications/:notificationId', async (req, res) => {
    try {
      const { patientId, notificationId } = req.params;
    //   const { title, message, scheduledFor, messageType, assistantId } = req.body;
      const { title, message, scheduledFor, messageType, assistantId, surveyQuestions } = req.body;
      
      const notificationRef = firestore.db.collection('patient_notifications').doc(notificationId);
      const notificationDoc = await notificationRef.get();
      
      if (!notificationDoc.exists) {
        return res.status(404).json({ error: 'Notification not found' });
      }
      
      const notification = notificationDoc.data();
      
      // Can't update already sent notifications
      if (notification.sentAt) {
        return res.status(400).json({ error: 'Cannot update a notification that has already been sent' });
      }
      
      const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
      .where('patientId', '==', patientId)
      .limit(1)
      .get();

    if (mappingSnapshot.empty) {
      return res.status(400).json({ error: 'Patient does not have a phone number configured' });
    }
    const phoneNumber = mappingSnapshot.docs[0].data().phoneNumber;
      // Update notification
      const updatedNotification = {
        title: title || notification.title,
        message: message || notification.message,
        scheduledFor: scheduledFor !== undefined ? scheduledFor : notification.scheduledFor,
        messageType: messageType || notification.messageType,
        assistantId: assistantId || notification.assistantId,
        updatedAt: new Date().toISOString(),
        surveyQuestions: surveyQuestions !== undefined ? surveyQuestions : notification.surveyQuestions || [], // Add this
        phoneNumber, // Preserve phoneNumber
        status: scheduledFor ? 'scheduled' : 'pending'
      };
      
      await notificationRef.update(updatedNotification);
      
      res.json({
        id: notificationId,
        ...notification,
        ...updatedNotification
      });
    } catch (error) {
      console.error('Error updating notification:', error);
      res.status(500).json({ error: 'Failed to update notification' });
    }
  });
  
  // Delete a notification
  router.delete('/patients/:patientId/notifications/:notificationId', async (req, res) => {
    try {
      const { patientId, notificationId } = req.params;
      
      const notificationRef = firestore.db.collection('patient_notifications').doc(notificationId);
      const notificationDoc = await notificationRef.get();
      
      if (!notificationDoc.exists) {
        return res.status(404).json({ error: 'Notification not found' });
      }
      
      await notificationRef.delete();
      
      res.json({ success: true });
    } catch (error) {
      console.error('Error deleting notification:', error);
      res.status(500).json({ error: 'Failed to delete notification' });
    }
  });
  
  // Send a notification immediately
  router.post('/patients/:patientId/notifications/:notificationId/send', async (req, res) => {
    try {
      const { patientId, notificationId } = req.params;
      const { messageType } = req.body || {};
      
      // Get notification
      const notificationRef = firestore.db.collection('patient_notifications').doc(notificationId);
      const notificationDoc = await notificationRef.get();
      
      if (!notificationDoc.exists) {
        return res.status(404).json({ error: 'Notification not found' });
      }
      
      const notification = notificationDoc.data();
      
      // Can't send already sent notifications
      if (notification.sentAt) {
        return res.status(400).json({ error: 'Notification has already been sent' });
      }
      
      // Get patient phone number
      const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        .where('patientId', '==', patientId)
        .limit(1)
        .get();
      
      if (mappingSnapshot.empty) {
        return res.status(400).json({ error: 'Patient does not have a phone number configured' });
      }
      
      const phoneMapping = mappingSnapshot.docs[0].data();
      const phoneNumber = phoneMapping.phoneNumber;
      
      // Get or use existing assistantId
      let assistantId = notification.assistantId || phoneMapping.assistantId;
      if (!assistantId) {
        // Try to find a default assistant
        const assistantSnapshot = await firestore.db.collection('assistants')
          .where('category', '==', 'default')
          .limit(1)
          .get();
        
        if (!assistantSnapshot.empty) {
          assistantId = assistantSnapshot.docs[0].id;
        }
      }
      
      // Create a unique session ID for this notification
      const sessionId = `notification_${notificationId}_${Date.now()}`;
      
      // Send message via Twilio
      const twilioService = new TwilioService();
      const finalMessageType = messageType || notification.messageType || 'whatsapp';
      
      if (finalMessageType === 'whatsapp') {
        await twilioService.sendWhatsAppMessage(
          `whatsapp:+1${phoneNumber}`,
          `${notification.title}\n\n${notification.message}`, // Include title in the message
          null, // shareId (we're not using shares for notifications)
          sessionId,
          assistantId,
          patientId
        );
      } else {
        await twilioService.sendSmsMessage(
          `+1${phoneNumber}`,
          `${notification.title}\n\n${notification.message}`, // Include title in the message
          null, // shareId (we're not using shares for notifications)
          sessionId,
          assistantId,
          patientId
        );
      }
      
      // Save the message to chat_sessions for history
      await firestore.db.collection('chat_sessions').doc(sessionId).set({
        sessionId,
        assistantId,
        patientId,
        phoneNumber,
        type: finalMessageType === 'whatsapp' ? 'whatsapp' : 'sms',
        lastActivity: new Date(),
        notificationId,
        isNotification: true,
        surveyQuestions: notification.surveyQuestions || [], // Add this
      });
      
      // Update notification as sent
      await notificationRef.update({
        sentAt: new Date().toISOString(),
        status: 'sent',
        messageType: finalMessageType,
        sessionId, 
        phoneNumber
      });
      
      res.json({
        id: notificationId,
        ...notification,
        sentAt: new Date().toISOString(),
        status: 'sent',
        messageType: finalMessageType,
        sessionId
      });
    } catch (error) {
      console.error('Error sending notification:', error);
      res.status(500).json({ error: 'Failed to send notification' });
    }
  
  });
  
  // Get notification status
  router.get('/patients/:patientId/notifications/:notificationId/status', async (req, res) => {
    try {
      const { patientId, notificationId } = req.params;
      
      const notificationRef = firestore.db.collection('patient_notifications').doc(notificationId);
      const notificationDoc = await notificationRef.get();
      
      if (!notificationDoc.exists) {
        return res.status(404).json({ error: 'Notification not found' });
      }
      
      const notification = notificationDoc.data();
      
      // Return the status and related info
      res.json({
        id: notificationId,
        status: notification.status,
        scheduledFor: notification.scheduledFor,
        sentAt: notification.sentAt,
        failedAt: notification.failedAt,
        failureReason: notification.failureReason
      });
    } catch (error) {
      console.error('Error fetching notification status:', error);
      res.status(500).json({ error: 'Failed to fetch notification status' });
    }
  });
  

  router.get('/patients/survey-responses/:surveyId', async (req, res) => {
    try {
      const { surveyId } = req.params;
      
      // Query all shared_chat_messages with this surveyId
      const messagesSnapshot = await firestore.db.collection('shared_chat_messages')
        .where('surveyId', '==', surveyId)
        .get();
      
      if (messagesSnapshot.empty) {
        return res.json({ patients: [] });
      }
      
      // Group messages by patientId
      const patientResponses = {};
      
      messagesSnapshot.forEach(doc => {
        const message = doc.data();
        if (!message.patientId) return;
        
        const patientId = message.patientId;
        
        if (!patientResponses[patientId]) {
          patientResponses[patientId] = {
            patientId,
            sessions: {}
          };
        }
        
        // Group by sessionId
        const sessionId = message.sessionId;
        if (!patientResponses[patientId].sessions[sessionId]) {
          patientResponses[patientId].sessions[sessionId] = {
            sessionId,
            messages: []
          };
        }
        
        patientResponses[patientId].sessions[sessionId].messages.push(message);
      });
      
      // Get patient details for each patientId
      const patients = [];
      
      for (const patientId in patientResponses) {
        try {
          const patientDoc = await firestore.db.collection('patients').doc(patientId).get();
          let patientData = { id: patientId, first_name: 'Unknown', last_name: 'Patient' };
          
          if (patientDoc.exists) {
            const data = patientDoc.data();
            patientData = {
              id: patientId,
              first_name: data.first_name || 'Unknown',
              last_name: data.last_name || 'Patient',
              gender: data.gender,
              date_of_birth: data.date_of_birth,
              mrn: data.mrn
            };
          }
          
          // Process sessions to extract question-answer pairs
          const sessionsArray = [];
          for (const sessionId in patientResponses[patientId].sessions) {
            const session = patientResponses[patientId].sessions[sessionId];
            
            // Sort messages by timestamp
            session.messages.sort((a, b) => {
              const timeA = a.createdAt?._seconds || new Date(a.createdAt).getTime() / 1000;
              const timeB = b.createdAt?._seconds || new Date(b.createdAt).getTime() / 1000;
              return timeA - timeB;
            });
            
            // Extract question-answer pairs
            const responses = [];
            for (let i = 0; i < session.messages.length - 1; i++) {
              const currMsg = session.messages[i];
              const nextMsg = session.messages[i + 1];
              
              if (currMsg.role === 'assistant' && nextMsg.role === 'user') {
                // Extract question text from assistant message
                let question = currMsg.content;
                
                if (question.includes('Please answer this survey question:')) {
                  const questionMatch = question.match(/Please answer this survey question: (.+?)(?:\nOptions:|$)/);
                  const extractedQuestion = questionMatch ? questionMatch[1].trim() : question;
                  
                  responses.push({
                    question: extractedQuestion,
                    answer: nextMsg.content,
                    timestamp: nextMsg.createdAt
                  });
                }
              }
            }
            
            if (responses.length > 0) {
              sessionsArray.push({
                sessionId,
                timestamp: session.messages[0]?.createdAt,
                responses
              });
            }
          }
          
          // Sort sessions by timestamp, most recent first
          sessionsArray.sort((a, b) => {
            const timeA = a.timestamp?._seconds || new Date(a.timestamp).getTime() / 1000;
            const timeB = b.timestamp?._seconds || new Date(b.timestamp).getTime() / 1000;
            return timeB - timeA;
          });
          
          patients.push({
            ...patientData,
            sessions: sessionsArray
          });
        } catch (error) {
          console.error(`Error fetching patient data for ${patientId}:`, error);
        }
      }
      console.log('RESPONSES', patients)
      return res.json({ patients });
      
    } catch (error) {
      console.error('Error fetching survey responses:', error);
      return res.status(500).json({ 
        error: 'Failed to fetch survey responses',
        details: error.message
      });
    }
  });

  // Get session summary for a specific patient and session
router.get('/patients/session-summary/:patientId/:sessionId', async (req, res) => {
    try {
      const { patientId, sessionId } = req.params;
  
      // Validate parameters
      if (!patientId || !sessionId) {
        return res.status(400).json({ error: 'patientId and sessionId are required' });
      }
  
      // Fetch session summary from patient_session_summaries
      const summaryDoc = await firestore.db
        .collection('patient_session_summaries')
        .doc(sessionId)
        .get();
  
      if (!summaryDoc.exists) {
        return res.status(404).json({ error: 'Session summary not found' });
      }
  
      const summaryData = summaryDoc.data();
  
      // Verify the patientId matches
      if (summaryData.patientId !== patientId) {
        return res.status(403).json({ error: 'Session does not belong to this patient' });
      }
  
      // Return the summary data
      res.json({
        sessionId: summaryData.sessionId,
        patientId: summaryData.patientId,
        summary: summaryData.summary,
        createdAt: summaryData.createdAt,
        extractedData: summaryData.extractedData || null,
        updatesApplied: summaryData.updatesApplied || null,
      });
    } catch (error) {
      console.error(`Error fetching session summary for session ${req.params.sessionId}:`, error);
      res.status(500).json({ error: 'Failed to fetch session summary', details: error.message });
    }
  });
export default router;
