// twilioRoutes.js
import { Router } from 'express';
import twilio from 'twilio';
import {TwilioService} from '../utils/twilioService.js';
import { validateSharedAccess } from '../middleware/validateShared.js';
import express from 'express';
import firestore from '../services/db/firestore.js';

import streamTextToSpeech from '../utils/tts.js';
import axios from 'axios';
const router = express.Router();
const { twiml: { VoiceResponse } } = twilio;
const PYTHON_API_URL = "https://app.homosapieus.com"

function determineCommunicationType(req) {
  // Detect communication type based on request body or headers
  if (req.body.isWeb === 'true' || req.body.phoneNumber) return 'web';
  if (req.body.From && req.body.From.startsWith('whatsapp:')) return 'whatsapp';
  if (req.body.SpeechResult || req.body.CallSid) return 'voice';
  return 'sms'; // Default to SMS if unsure
}

function cleanPhoneNumber(from) {
  return from.replace('whatsapp:', '').replace(/^\+1/, '');
}

// function cleanPhoneNumber(from) {
//   return from.replace('web:', '').replace('whatsapp:', '').replace(/^\+1/, ''); // MODIFIED
// }

async function determineOrganizationId(req) {
  // Placeholder: Determine organization based on Twilio number or other logic
  // For example, map Twilio numbers to organizations in Firestore
  return '618f87b2-aea0-402c-a355-338cb1f6fbf0'; // Replace with actual logic
  // return "6ba2c375-2c49-45a0-b46d-34a41096d665"

}

async function getDefaultAssistantId(organizationId) {
  // Fetch assistants for the organization and find one marked as default
  const snapshot = await firestore.db.collection('assistants')
    .where('organization_id', '==', organizationId)
    .where('category', '==', 'Pregnancy test') // Assuming 'category' field marks default
    .limit(1)
    .get();
  console.log('[ASSISTANT SNAP SHOT]', snapshot)
  if (snapshot.empty) return null;
  return snapshot.docs[0].id;
}


async function createPatientViaPython(phoneNumber, assistantId, organizationId) {
  const response = await fetch(`${PYTHON_API_URL}/api/public/patients`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phone: phoneNumber,
      first_name: '',
      last_name: '',
      gender: '',
      date_of_birth: '', // Changed from null to empty string
      organization_id: organizationId
    }),
  });
  if (!response.ok) throw new Error('Failed to create patient');
  return await response.json();
}

function getAssistantRoute(communicationType, assistantId, isUserInitiated) {
  let baseRoute;
  switch (communicationType) {
    case 'whatsapp':
      baseRoute = `/api/assistants/${assistantId}/whatsapp/incoming`;
      break;
    case 'sms':
      baseRoute = `/api/assistants/${assistantId}/sms/incoming`;
      break;
    case 'voice':
      baseRoute = `/api/assistants/${assistantId}/voice/incoming`;
      break;
    case 'web':
      baseRoute = `/api/assistants/${assistantId}/web/incoming`;
      break;
    default:
      throw new Error('Unknown communication type');
  }
  
  return `${baseRoute}?is_user_initiated=${isUserInitiated}`;
}
router.post('/assistants/twilio/router', express.urlencoded({ extended: true }), async (req, res) => {
  console.log('--- Twilio Router Request Received ---');
  console.log('Request Body:', JSON.stringify(req.body));
  
  const from = req.body.From; // Phone number of the caller/sender
  console.log('From:', from);
  
  const communicationType = determineCommunicationType(req); // Custom function to detect type
  console.log('Communication Type:', communicationType);

  try {
    // Step 1: Extract phone number and clean it
    const phoneNumber = cleanPhoneNumber(from); // Remove prefixes like "whatsapp:" or "+1"
    console.log('Cleaned Phone Number:', phoneNumber);

    // Step 2: Determine the organization (if applicable)
    const organizationId = await determineOrganizationId(req); // Placeholder for your logic
    console.log('Organization ID:', organizationId);

    // Step 3: Check for existing patient phone mapping
    console.log('Querying patient_phone_mappings for:', phoneNumber);
    const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
      .where('phoneNumber', '==', phoneNumber)
      .limit(1)
      .get();

    console.log('Mapping query returned empty?', mappingSnapshot.empty);
    
    let assistantId;
    let patientId;


    const now = new Date();
    const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000);
    let isUserInitiated = true;

    const notificationSnapshot = await firestore.db.collection('patient_notifications')
      .where('phoneNumber', '==', phoneNumber)
      .where('sentAt', '>=', fiveMinutesAgo.toISOString())
      .where('status', '==', 'sent')
      .orderBy('sentAt', 'desc')
      .limit(1)
      .get();
      console.log('NOTIFICATION SNAPSHOT', notificationSnapshot);
      console.log('NOTIFICATION SNAPSHOT EMPTY?', notificationSnapshot.empty);
      if (!notificationSnapshot.empty) {
        const notificationData = notificationSnapshot.docs[0].data();
        console.log('NOTIFICATION DATA:', JSON.stringify(notificationData, null, 2));
        console.log('Has surveyQuestions?', !!notificationData.surveyQuestions);
        if (notificationData.surveyQuestions) {
          console.log('surveyQuestions length:', notificationData.surveyQuestions.length);
        }
      }
        if (!notificationSnapshot.empty) 
      {
        const notification = notificationSnapshot.docs[0].data();
        // If it has survey questions, it's a notification we should respond to
        if (notification.surveyQuestions && notification.surveyQuestions.length > 0) {
            assistantId = notification.assistantId;
            patientId = notification.patientId;
            console.log(`Found survey notification (ID: ${notification.id}) with ${notification.surveyQuestions.length} questions`);
            isUserInitiated = false;
        } else if (!notification.surveyQuestions || notification.surveyQuestions.length === 0) {
            // Handle non-survey notifications
            assistantId = notification.assistantId;
            patientId = notification.patientId;
            console.log(`Found regular notification (ID: ${notification.id})`);
            isUserInitiated = false;
        }

      } else {

        isUserInitiated = true;
        if (!mappingSnapshot.empty) {
          // Existing patient found
          const mapping = mappingSnapshot.docs[0].data();
          assistantId = mapping.assistantId;
          patientId = mapping.patientId;
          console.log(`Found existing mapping for ${phoneNumber}:`);
          console.log('Assistant ID:', assistantId);
          console.log('Patient ID:', patientId);
        } else {
          // New patient: Assign default assistant and create records
          console.log('No existing mapping found, getting default assistant');
          assistantId = await getDefaultAssistantId(organizationId);
          console.log('Default Assistant ID:', assistantId);
          
          if (!assistantId) {
            console.error('No default assistant found for organization:', organizationId);
            throw new Error('No default assistant found for organization');
          }

          // Create new patient via Python API
          console.log('Creating new patient via Python API');
          // const patientResponse = await createPatientViaPython(phoneNumber, assistantId);
          const patientResponse = await createPatientViaPython(phoneNumber, assistantId, organizationId);
          patientId = patientResponse.id;
          console.log('New Patient Created:', patientId);
          console.log(`[TWILIO ROUTER] New Patient Created for ${phoneNumber}: patientId=${patientId}, timestamp=${new Date().toISOString()}, response=${JSON.stringify(patientResponse)}`);

          // Create patient phone mapping
          console.log('Creating new patient_phone_mapping');
          const newMapping = {
            phoneNumber,
            patientId,
            assistantId,
            pregnancyTest:false, 
            createdAt: new Date().toISOString(),
          };
          console.log('New Mapping Data:', newMapping);
          
          await firestore.db.collection('patient_phone_mappings').doc().set(newMapping);
          console.log(`Created new patient and mapping for ${phoneNumber}: Assistant ${assistantId}`);
        }
      }
    // Step 4: Forward to assistant-specific route
    // const targetUrl = getAssistantRoute(communicationType, assistantId);
    const targetUrl = getAssistantRoute(communicationType, assistantId, isUserInitiated);
    console.log(`Routing ${communicationType} from ${phoneNumber} to ${targetUrl}`);
    
    console.log('Redirecting with status 307 to:', targetUrl);
    res.redirect(307, targetUrl); // 307 preserves POST method and body

  } catch (error) {
    console.error('Error in router:', error);
    console.error('Error details:', error.message);
    console.error('Error stack:', error.stack);
    
    console.log('Sending empty TwiML response due to error');
    res.type('text/xml');
    res.send(new twilio.twiml.MessagingResponse().toString());
  }
});



// router.post('/shared/:shareId/voice/incoming', validateSharedAccess, async (req, res) => {
//   const { shareId } = req.params;
//   const twilioService = new TwilioService();
//   const { From } = req.body;
//   const share = req.shareData;
//   let patientId = null;
//   const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
//     .where('phoneNumber', '==', From)
//     .limit(1)
//     .get();
//   if (!mappingSnapshot.empty) {
//     patientId = mappingSnapshot.docs[0].data().patientId;
//   }
//   // const twimlResponse = await twilioService.handleIncomingCall(shareId);
//   const twimlResponse = await twilioService.handleIncomingCall(shareId, From, { patientId });
  
//   res.type('text/xml');
//   res.send(twimlResponse);
// });
router.post('/shared/:shareId/voice/incoming', validateSharedAccess, async (req, res) => {
  const { shareId } = req.params;
  const twilioService = new TwilioService();
  const { From } = req.body;
  const share = req.shareData;
  
  // Check for patient mapping
  let patientId = null;
  const phoneNumber = From.replace(/^\+1/, '');
  
  const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
    .where('phoneNumber', '==', phoneNumber)
    .limit(1)
    .get();
    
  if (!mappingSnapshot.empty) {
    patientId = mappingSnapshot.docs[0].data().patientId;
  }
  
  const twimlResponse = await twilioService.handleIncomingCall(shareId, From, { patientId });
  
  res.type('text/xml');
  res.send(twimlResponse);
});
// router.post(
//     '/shared/:shareId/voice/transcription',
//     validateSharedAccess,
//     express.urlencoded({ extended: true }),
//     async (req, res) => {
//       const { shareId } = req.params;
//       const { sessionId } = req.query;
//       const transcriptionText = req.body.SpeechResult || ''; // Get speech result directly
  
//       console.log('Speech recognition result:', transcriptionText);
  
//       if (!transcriptionText.trim()) {
//         console.warn('No speech detected:', { shareId, sessionId });
//         const twiml = new VoiceResponse();
  
//         const share = await firestore.getShareLink(shareId);
//         const voiceName = share.voiceName || 'en-US-Wavenet-D';
//         console.log('VOICE NAME, TRanscription route', voiceName)
//         // Use TTS for the error message
//         const errorTtsUrl = `${process.env.API_URL}/api/shared/${shareId}/chat/audio?text=${encodeURIComponent('I couldn\'t hear what you said. Please try again.')}&language=en&voiceName=en-US-Wavenet-D`;
//         twiml.play(errorTtsUrl);
  
//         // Re-gather input
//         twiml.gather({
//           input: 'speech',
//           action: `/api/shared/${shareId}/voice/transcription?sessionId=${sessionId}`,
//           speechTimeout: 'auto',
//           language: 'en-GB'
//         });
  
//         res.type('text/xml');
//         return res.send(twiml.toString());
//       }
  
//       const twilioService = new TwilioService();
//       const ttsAudioUrl = await twilioService.handleTranscription(shareId, sessionId, transcriptionText);
  
//       const twiml = new VoiceResponse();
//       twiml.play(ttsAudioUrl); // Play the custom TTS audio
  
//       // Continue the conversation with another gather
//       twiml.gather({
//         input: 'speech',
//         action: `/api/shared/${shareId}/voice/transcription?sessionId=${sessionId}`,
//         speechTimeout: 'auto',
//         language: 'en-GB'
//       });
  
//       res.type('text/xml');
//       res.send(twiml.toString());
//     }
//   );

router.post(
  '/shared/:shareId/voice/transcription',
  validateSharedAccess,
  express.urlencoded({ extended: true }),
  async (req, res) => {
    const { shareId } = req.params;
    const { sessionId, callId } = req.query;
    const transcriptionText = req.body.SpeechResult || '';

    console.log('Speech recognition result:', transcriptionText);

    if (!transcriptionText.trim()) {
      console.warn('No speech detected:', { shareId, sessionId });
      const twiml = new VoiceResponse();

      const share = await firestore.getShareLink(shareId);
      const voiceName = share.voiceName || 'en-US-Wavenet-D';
      console.log('VOICE NAME, Transcription route', voiceName)
      
      // Use TTS for the error message
      const errorTtsUrl = `${process.env.API_URL}/api/shared/${shareId}/chat/audio?text=${encodeURIComponent('I couldn\'t hear what you said. Please try again.')}&language=en&voiceName=${voiceName}`;
      twiml.play(errorTtsUrl);

      // Re-gather input
      twiml.gather({
        input: 'speech',
        action: `/api/shared/${shareId}/voice/transcription?sessionId=${sessionId}&callId=${callId}`,
        speechTimeout: 'auto',
        language: 'en-GB'
      });

      res.type('text/xml');
      return res.send(twiml.toString());
    }

    const twilioService = new TwilioService();
    const ttsAudioUrl = await twilioService.handleTranscription(shareId, sessionId, transcriptionText, callId);

    const twiml = new VoiceResponse();
    twiml.play(ttsAudioUrl); // Play the custom TTS audio

    // Continue the conversation with another gather
    twiml.gather({
      input: 'speech',
      action: `/api/shared/${shareId}/voice/transcription?sessionId=${sessionId}&callId=${callId}`,
      speechTimeout: 'auto',
      language: 'en-GB'
    });

    res.type('text/xml');
    res.send(twiml.toString());
  }
);

router.post('/shared/:shareId/voice/call', validateSharedAccess, async (req, res) => {
  try {
    const { shareId } = req.params;
    const { phoneNumber } = req.body;
    
    const twilioService = new TwilioService();
    const callSid = await twilioService.makeOutboundCall(phoneNumber, shareId);
    
    res.json({ success: true, callSid });
  } catch (error) {
    console.error('Error initiating call:', error);
    res.status(500).json({ error: 'Failed to initiate call' });
  }
});

// router.post('/assistants/:assistantId/voice/incoming', 
//   express.urlencoded({ extended: true }),
//   async (req, res) => {
//     const { assistantId } = req.params;
//     const { From } = req.body;
//     console.log('Headers:', req.headers);
//     console.log('Body:', req.body);
//     if (!From) {
//       console.error('Missing From parameter in incoming call request', { assistantId, reqBody: req.body });
//       const twiml = new VoiceResponse();
//       twiml.say('Sorry, an error occurred. Please try again.');
//       res.type('text/xml');
//       return res.send(twiml.toString());
//     }
//     try {
//       // Get the assistant to find the primary voice share
//       const assistant = await firestore.getAssistant(assistantId);
      
//       if (!assistant) {
//         console.error('Assistant not found:', assistantId);
//         const twiml = new VoiceResponse();
//         twiml.say('Sorry, this assistant is not available.');
//         res.type('text/xml');
//         return res.send(twiml.toString());
//       }
  
//       // Get the primary voice shareId
//       const primaryShareId = assistant.voiceShareId;
      
//       if (!primaryShareId) {
//         console.error('No primary voice share set for assistant:', assistantId);
//         const twiml = new VoiceResponse();
//         twiml.say('Sorry, this assistant is not configured for voice calls.');
//         res.type('text/xml');
//         return res.send(twiml.toString());
//       }
  
//       // Verify the share exists and is active
//       const shareSnapshot = await firestore.db.collection('shared_links')
//         .where('shareId', '==', primaryShareId)
//         .where('isActive', '==', true)
//         .limit(1)
//         .get();
  
//       if (shareSnapshot.empty) {
//         console.error('Primary voice share not found or inactive:', primaryShareId);
//         const twiml = new VoiceResponse();
//         twiml.say('Sorry, this voice service is currently unavailable.');
//         res.type('text/xml');
//         return res.send(twiml.toString());
//       }
//       let patientId = null;
//       const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
//       .where('phoneNumber', '==', From)
//       .limit(1)
//       .get();

//     if (!mappingSnapshot.empty) {
//       patientId = mappingSnapshot.docs[0].data().patientId;
//     }
  
//       // Proceed with existing TwilioService flow using the primary shareId
//       const twilioService = new TwilioService();
//       // const twimlResponse = await twilioService.handleIncomingCall(primaryShareId);
//       const twimlResponse = await twilioService.handleIncomingCall(primaryShareId, null, { patientId });

      
//       res.type('text/xml');
//       res.send(twimlResponse);
//     } catch (error) {
//       console.error('Error handling incoming voice call:', error);
//       const twiml = new VoiceResponse();
//       twiml.say('Sorry, an error occurred. Please try again later.');
//       res.type('text/xml');
//       res.send(twiml.toString());
//     }
//   });
  
  router.post('/assistants/:assistantId/voice/incoming', 
    express.urlencoded({ extended: true }),
    async (req, res) => {
      const { assistantId } = req.params;
      const { From } = req.body;
      
      console.log('Headers:', req.headers);
      console.log('Body:', req.body);
      
      if (!From) {
        console.error('Missing From parameter in incoming call request', { assistantId, reqBody: req.body });
        const twiml = new VoiceResponse();
        twiml.say('Sorry, an error occurred. Please try again.');
        res.type('text/xml');
        return res.send(twiml.toString());
      }
      
      try {
        // Get the assistant to find the primary voice share
        const assistant = await firestore.getAssistant(assistantId);
        
        if (!assistant) {
          console.error('Assistant not found:', assistantId);
          const twiml = new VoiceResponse();
          twiml.say('Sorry, this assistant is not available.');
          res.type('text/xml');
          return res.send(twiml.toString());
        }
    
        // Get the primary voice shareId
        const primaryShareId = assistant.voiceShareId;
        
        if (!primaryShareId) {
          console.error('No primary voice share set for assistant:', assistantId);
          const twiml = new VoiceResponse();
          twiml.say('Sorry, this assistant is not configured for voice calls.');
          res.type('text/xml');
          return res.send(twiml.toString());
        }
    
        // Verify the share exists and is active
        const shareSnapshot = await firestore.db.collection('shared_links')
          .where('shareId', '==', primaryShareId)
          .where('isActive', '==', true)
          .limit(1)
          .get();
    
        if (shareSnapshot.empty) {
          console.error('Primary voice share not found or inactive:', primaryShareId);
          const twiml = new VoiceResponse();
          twiml.say('Sorry, this voice service is currently unavailable.');
          res.type('text/xml');
          return res.send(twiml.toString());
        }
        
        // Check for patient mapping
        let patientId = null;
        const phoneNumber = From.replace(/^\+1/, '');
        
        const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
          .where('phoneNumber', '==', phoneNumber)
          .limit(1)
          .get();
  
        if (!mappingSnapshot.empty) {
          patientId = mappingSnapshot.docs[0].data().patientId;
        }
    
        // Proceed with the TwilioService
        const twilioService = new TwilioService();
        const twimlResponse = await twilioService.handleIncomingCall(primaryShareId, From, { patientId });
        
        res.type('text/xml');
        res.send(twimlResponse);
      } catch (error) {
        console.error('Error handling incoming voice call:', error);
        const twiml = new VoiceResponse();
        twiml.say('Sorry, an error occurred. Please try again later.');
        res.type('text/xml');
        res.send(twiml.toString());
      }
    });
  // Update transcription route to also get primary shareId first
  // router.post(
  //   '/assistants/:assistantId/voice/transcription',
  //   express.urlencoded({ extended: true }),
  //   async (req, res) => {
  //     const { assistantId } = req.params;
  //     const { sessionId } = req.query;
  //     const transcriptionText = req.body.SpeechResult || '';
  
  //     try {
  //       // Get the assistant and primary share
  //       const assistant = await firestore.getAssistant(assistantId);
  //       if (!assistant?.voiceShareId) {
  //         throw new Error('No primary voice share configured');
  //       }
  
  //       const primaryShareId = assistant.voiceShareId;
  
  //       // Verify share is active
  //       const shareSnapshot = await firestore.db.collection('shared_links')
  //         .where('shareId', '==', primaryShareId)
  //         .where('isActive', '==', true)
  //         .limit(1)
  //         .get();
  
  //       if (shareSnapshot.empty) {
  //         throw new Error('Primary voice share not found or inactive');
  //       }
  
  //       console.log('Speech recognition result:', transcriptionText);
  
  //       if (!transcriptionText.trim()) {
  //         console.warn('No speech detected:', { assistantId, sessionId });
  //         const twiml = new VoiceResponse();
          
  //         const errorTtsUrl = `${process.env.API_URL}/api/shared/${primaryShareId}/chat/audio?text=${encodeURIComponent('I couldn\'t hear what you said. Please try again.')}&language=en&voiceName=en-US-Wavenet-D`;
  //         twiml.play(errorTtsUrl);
  
  //         twiml.gather({
  //           input: 'speech',
  //           action: `/api/assistants/${assistantId}/voice/transcription?sessionId=${sessionId}`,
  //           speechTimeout: 'auto',
  //           language: 'en-GB'
  //         });
  
  //         res.type('text/xml');
  //         return res.send(twiml.toString());
  //       }
  
  //       const twilioService = new TwilioService();
  //       const ttsAudioUrl = await twilioService.handleTranscription(primaryShareId, sessionId, transcriptionText);
  
  //       const twiml = new VoiceResponse();
  //       twiml.play(ttsAudioUrl);
  
  //       twiml.gather({
  //         input: 'speech',
  //         action: `/api/assistants/${assistantId}/voice/transcription?sessionId=${sessionId}`,
  //         speechTimeout: 'auto',
  //         language: 'en-GB'
  //       });
  
  //       res.type('text/xml');
  //       res.send(twiml.toString());
  //     } catch (error) {
  //       console.error('Error handling transcription:', error);
  //       const twiml = new VoiceResponse();
  //       twiml.say('Sorry, an error occurred. Please try again later.');
  //       res.type('text/xml');
  //       res.send(twiml.toString());
  //     }
  //   }
  // );
  router.post(
    '/assistants/:assistantId/voice/transcription',
    express.urlencoded({ extended: true }),
    async (req, res) => {
      const { assistantId } = req.params;
      const { sessionId, callId } = req.query;
      const transcriptionText = req.body.SpeechResult || '';
  
      try {
        // Get the assistant and primary share
        const assistant = await firestore.getAssistant(assistantId);
        if (!assistant?.voiceShareId) {
          throw new Error('No primary voice share configured');
        }
  
        const primaryShareId = assistant.voiceShareId;
  
        // Verify share is active
        const shareSnapshot = await firestore.db.collection('shared_links')
          .where('shareId', '==', primaryShareId)
          .where('isActive', '==', true)
          .limit(1)
          .get();
  
        if (shareSnapshot.empty) {
          throw new Error('Primary voice share not found or inactive');
        }
  
        console.log('Speech recognition result:', transcriptionText);
  
        if (!transcriptionText.trim()) {
          console.warn('No speech detected:', { assistantId, sessionId });
          const twiml = new VoiceResponse();
          
          const errorTtsUrl = `${process.env.API_URL}/api/shared/${primaryShareId}/chat/audio?text=${encodeURIComponent('I couldn\'t hear what you said. Please try again.')}&language=en&voiceName=en-US-Wavenet-D`;
          twiml.play(errorTtsUrl);
  
          twiml.gather({
            input: 'speech',
            action: `/api/assistants/${assistantId}/voice/transcription?sessionId=${sessionId}&callId=${callId}`,
            speechTimeout: 'auto',
            language: 'en-GB'
          });
  
          res.type('text/xml');
          return res.send(twiml.toString());
        }
  
        const twilioService = new TwilioService();
        const ttsAudioUrl = await twilioService.handleTranscription(primaryShareId, sessionId, transcriptionText, callId);
  
        const twiml = new VoiceResponse();
        twiml.play(ttsAudioUrl);
  
        twiml.gather({
          input: 'speech',
          action: `/api/assistants/${assistantId}/voice/transcription?sessionId=${sessionId}&callId=${callId}`,
          speechTimeout: 'auto',
          language: 'en-GB'
        });
  
        res.type('text/xml');
        res.send(twiml.toString());
      } catch (error) {
        console.error('Error handling transcription:', error);
        const twiml = new VoiceResponse();
        twiml.say('Sorry, an error occurred. Please try again later.');
        res.type('text/xml');
        res.send(twiml.toString());
      }
    }
  );
  // Update outbound call route
  router.post('/assistants/:assistantId/voice/call', async (req, res) => {
    try {
      const { assistantId } = req.params;
      const { phoneNumber } = req.body;
      
      // Get the assistant and verify primary share
      const assistant = await firestore.getAssistant(assistantId);
      if (!assistant?.voiceShareId) {
        return res.status(400).json({ error: 'No primary voice share configured for this assistant' });
      }
  
      const twilioService = new TwilioService();
      const callSid = await twilioService.makeOutboundCall(phoneNumber, assistant.voiceShareId);
      
      res.json({ success: true, callSid });
    } catch (error) {
      console.error('Error initiating call:', error);
      res.status(500).json({ error: 'Failed to initiate call' });
    }
  });
  

  async function pregnancy_test_completion(phoneNumber, patientId, body, from, primaryShareId, assistant) {
    console.log('→ PREGNANCY TEST: Starting pregnancy test completion function');
    
    const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
      .where('phoneNumber', '==', phoneNumber)
      .where('patientId', '==', patientId)
      .limit(1)
      .get();
    
    if (mappingSnapshot.empty) {
      console.log('→ PREGNANCY TEST: No mapping found');
      return false; // Continue with normal flow
    }
    
    const mappingData = mappingSnapshot.docs[0].data();
    const mappingRef = mappingSnapshot.docs[0].ref;
    
    // Step 1: Check if pregnancy test completed
    if (mappingData.pregnancyTest) {
      console.log('→ PREGNANCY TEST: Already completed, continue normal flow');
      return false; // Continue with normal flow
    }
    
    console.log('→ PREGNANCY TEST: Not completed, starting pregnancy test flow');
    // Get pregnancy test assistant
    const organizationId = '618f87b2-aea0-402c-a355-338cb1f6fbf0';
    const pregnancyTestAssistantId = await getAssistantByCategory(organizationId, 'Pregnancy test');
    
    if (!pregnancyTestAssistantId) {
      console.log('→ PREGNANCY TEST: No pregnancy test assistant found');
      return false; // Continue with normal flow
    }
    
    console.log('→ PREGNANCY TEST: Found pregnancy test assistant:', pregnancyTestAssistantId);
     // Get pregnancy test assistant data
     const pregnancyAssistant = await firestore.getAssistant(pregnancyTestAssistantId);
    
    // Step 3: Create new session with whatsapp_onboarding_...
    // const onboardingSessionId = `whatsapp_onboarding_${phoneNumber}_${Date.now()}`;
    // Check for existing onboarding session first
    const existingOnboardingQuery = await firestore.db.collection('chat_sessions')
      .where('phoneNumber', '==', phoneNumber)
      .where('patientId', '==', patientId)  // ADD THIS LINE
      .where('type', '==', 'whatsapp')
      .where('isOnboarding', '==', true)
      .orderBy('lastActivity', 'desc')
      .limit(1)
      .get();

    let onboardingSessionId;
    let currentSessionData = {}; 
    let messagesShareId; // ADD THIS LINE

    if (!existingOnboardingQuery.empty) {
    // Reuse existing onboarding session
    const existingSessionDoc = existingOnboardingQuery.docs[0]; // ADD THIS LINE
    onboardingSessionId = existingSessionDoc.id; // CHANGE THIS LINE
    currentSessionData = existingSessionDoc.data(); // ADD THIS LINE: Load existing data
    console.log('→ PREGNANCY TEST: Reusing existing onboarding session:', onboardingSessionId);
    console.log(`[PREGNANCY TEST] Reusing session ${onboardingSessionId} with patientId=${currentSessionData.patientId}, input patientId=${patientId}, timestamp=${new Date().toISOString()}`);
    messagesShareId = currentSessionData.shareId; // ADD THIS LINE: Use the shareId from the session
    } else {
    // Create new onboarding session only if none exists
    onboardingSessionId = `whatsapp_onboarding_${phoneNumber}_${Date.now()}`;
    console.log('→ PREGNANCY TEST: Created new onboarding session:', onboardingSessionId);
    console.log(`[PREGNANCY TEST] Creating new session ${onboardingSessionId} with patientId=${patientId}, timestamp=${new Date().toISOString()}`);
    // Create the session document
    messagesShareId = pregnancyAssistant.voiceShareId; 

    await firestore.db.collection('chat_sessions').doc(onboardingSessionId).set({
      sessionId: onboardingSessionId,
      assistantId: pregnancyTestAssistantId,
      phoneNumber: phoneNumber,
      type: 'whatsapp',
      shareId:  pregnancyAssistant.voiceShareId,
      userId: pregnancyAssistant.userId,
      patientId: patientId,
      lastActivity: new Date(),
      createdAt: new Date(),  // ADD THIS
      is_user_initiated: true,
      isOnboarding: true
    });
}
    console.log('→ PREGNANCY TEST: Created onboarding session:', onboardingSessionId);
    
    
    // Update mapping with pregnancy test assistant
    await mappingRef.update({
      assistantId: pregnancyTestAssistantId,
      updatedAt: new Date().toISOString()
    });
    
   
    // Create onboarding session document

    // Get previous messages for onboarding session (should be empty)
    console.log(`Fetching chat history for shareId: ${messagesShareId} sessionId: ${onboardingSessionId}`); // ADD THIS LOG
    const previousMessages = await firestore.getSharedChatHistory(messagesShareId, onboardingSessionId, patientId); // CHANGE THIS LINE
    console.log(`Found ${previousMessages.length} messages for session: ${onboardingSessionId}`); // ADD THIS LOG
    await firestore.db.collection('chat_sessions').doc(onboardingSessionId).update({
      lastActivity: new Date(),
  });
    console.log('→ PREGNANCY TEST: currentSessionData before sending to Python:', currentSessionData); // ADD THIS LOG 
    // Step 4: Call vector chat directly with pregnancy test assistant
    console.log('→ PREGNANCY TEST: Calling vector chat with onboarding session');
    // ADD THIS DEBUG LOG:
    console.log('→ PREGNANCY TEST: Current session data from Firestore:', JSON.stringify(currentSessionData, null, 2));
    console.log('→ PREGNANCY TEST: currentNodeId being sent:', currentSessionData.currentNodeId);

    const vectorPayload = {
      message: body.trim(),
      sessionId: onboardingSessionId,
      patientId: patientId,
      assistantId: currentSessionData.assistantId,
      flow_id: pregnancyAssistant.flowData.id,
      session_data: { 
        isOnboarding: true,
        currentNodeId: currentSessionData.currentNodeId  
      },
      previous_messages: previousMessages
    };
    
    const vectorResponse = await axios.post(`${PYTHON_API_URL}/api/shared/vector_chat`, vectorPayload);
    const vectorData = vectorResponse.data;
    
    console.log('→ PREGNANCY TEST: Vector chat response:', vectorData);
    
    // Only save messages when pregnancy test actually starts (not during onboarding)
    if (vectorData.onboarding_status === 'in_progress' || vectorData.onboarding_status === 'completed') {
      console.log('→ PREGNANCY TEST: Saving messages in onboarding session');
      
      await firestore.saveSharedChatMessage({
        shareId: primaryShareId,
        sessionId: onboardingSessionId,
        assistantId: pregnancyTestAssistantId,
        role: 'user',
        content: body.trim(),
        createdAt: new Date(),
        patientId: patientId,
      });

      await firestore.saveSharedChatMessage({
        shareId: messagesShareId,
        sessionId: onboardingSessionId,
        assistantId: pregnancyTestAssistantId,
        role: 'assistant',
        content: vectorData.content,
        createdAt: new Date(),
        patientId: patientId,
      });
    }
    
    // Update onboarding session with response data
    if (vectorData.state_updates) {
      await firestore.db.collection('chat_sessions').doc(onboardingSessionId).set(vectorData.state_updates, { merge: true });
    }
    // if (vectorData.next_node_id !== undefined) {
    //   await firestore.db.collection('chat_sessions').doc(onboardingSessionId).set({ currentNodeId: vectorData.next_node_id }, { merge: true });
    // }
    console.log('→ PREGNANCY TEST: Received next_node_id:', vectorData.next_node_id);
    if (vectorData.next_node_id !== undefined) {
      await firestore.db.collection('chat_sessions').doc(onboardingSessionId).set(
        { currentNodeId: vectorData.next_node_id },
        { merge: true }
      );
      console.log('→ PREGNANCY TEST: Updated currentNodeId to', vectorData.next_node_id);
    }
    
    console.log('→ PREGNANCY TEST: Saved messages in onboarding session');
    
    // Check if pregnancy test completed
    if (vectorData.onboarding_status === 'completed' && !vectorData.next_node_id) {
      console.log('→ PREGNANCY TEST: Completed! Marking as done and switching to base session');
      
      // Mark pregnancy test as completed
      await mappingRef.update({
        pregnancyTest: true,
        updatedAt: new Date().toISOString()
      });
      
      // Send completion response
      const twilioService = new TwilioService();
      await twilioService.sendWhatsAppMessage(
        from, 
        vectorData.content, 
        messagesShareId, 
        onboardingSessionId, 
        pregnancyTestAssistantId,
        patientId,
        true
      );
      
      console.log('→ PREGNANCY TEST: Sent completion response');
      // Record analytics for pregnancy test completion
      axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
        message: body.trim(),
        response: vectorData.content,
        sessionId: onboardingSessionId,
        timestamp: new Date().toISOString()
      }).then(analyticsResponse => {
        console.log('→ PREGNANCY TEST: Completion analytics recorded successfully:', analyticsResponse.data.analytics_id);
      }).catch(analyticsError => {
        console.error('→ PREGNANCY TEST: Error recording completion analytics:', analyticsError.message);
      });
      const clarificationMessage = "Great Onboarding is complete! Please describe in one word what you are looking for today: symptoms, pregnancy test, pregnancy support, etc.";
      await twilioService.sendWhatsAppMessage(
        from,
        clarificationMessage,
        messagesShareId,
        onboardingSessionId,
        pregnancyTestAssistantId,
        patientId,
        true
      );
      // Record analytics for clarification message
axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
  message: '', // Empty since this is a system-generated follow-up
  response: clarificationMessage,
  sessionId: onboardingSessionId,
  timestamp: new Date().toISOString()
}).then(analyticsResponse => {
  console.log('→ PREGNANCY TEST: Clarification analytics recorded successfully:', analyticsResponse.data.analytics_id);
}).catch(analyticsError => {
  console.error('→ PREGNANCY TEST: Error recording clarification analytics:', analyticsError.message);
});
      
      // Step 5: Now use base session ID and proceed with normal flow
      console.log('→ PREGNANCY TEST: Switching to base session for normal flow');
      return 'completed'; // Special return value indicating completion
    } else {
      // Pregnancy test still in progress
      const twilioService = new TwilioService();
      await twilioService.sendWhatsAppMessage(
        from, 
        vectorData.content, 
        messagesShareId, 
        onboardingSessionId, 
        pregnancyTestAssistantId,
        patientId,
        true
      );
      
      console.log('→ PREGNANCY TEST: Sent in-progress response');
      // Record analytics for in-progress pregnancy test message
      axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
        message: body.trim(),
        response: vectorData.content,
        sessionId: onboardingSessionId,
        timestamp: new Date().toISOString()
      }).then(analyticsResponse => {
        console.log('→ PREGNANCY TEST: In-progress analytics recorded successfully:', analyticsResponse.data.analytics_id);
      }).catch(analyticsError => {
        console.error('→ PREGNANCY TEST: Error recording in-progress analytics:', analyticsError.message);
      });
      return true; // Pregnancy test handled, exit main flow
    }
  }
  
  // Add this helper function
  async function getAssistantByCategory(organizationId, category) {
    try {
      const snapshot = await firestore.db.collection('assistants')
        .where('organization_id', '==', organizationId)
        .where('category', '==', category)
        .where('status', '==', 'active')
        .limit(1)
        .get();
      
      if (!snapshot.empty) {
        return snapshot.docs[0].id;
      }
      
      return null;
    } catch (error) {
      console.error('Error getting assistant by category:', error);
      return null;
    }
  }



//whatsapp messges
// router.post(
//   '/assistants/:assistantId/whatsapp/incoming',
//   express.urlencoded({ extended: true }),
//   async (req, res) => {
//     const { assistantId } = req.params;
//     const from = req.body.From;
//     const body = req.body.Body || '';
    
//     console.log('→ WEBHOOK ENTRY: WhatsApp incoming webhook triggered', {
//       assistantId,
//       timestamp: new Date().toISOString()
//     });
    
//     console.log('→ REQUEST BODY:', JSON.stringify(req.body, null, 2));
    
//     try {
//       console.log('→ STEP 1: Fetching assistant data');
//       const assistant = await firestore.getAssistant(assistantId);
//       if (!assistant) {
//         console.error('→ ERROR: Assistant not found:', assistantId);
//         res.type('text/xml');
//         return res.send(new twilio.twiml.MessagingResponse().toString());
//       }
//       console.log('→ Assistant found:', {
//         id: assistant.id,
//         name: assistant.name,
//         hasFlowData: !!assistant.flowData,
//         hasVoiceShareId: !!assistant.voiceShareId
//       });

//       const primaryShareId = assistant.voiceShareId;
//       if (!primaryShareId) {
//         console.error('→ ERROR: No primary share set for assistant:', assistantId);
//         res.type('text/xml');
//         return res.send(new twilio.twiml.MessagingResponse().toString());
//       }
//       console.log('→ Primary shareId found:', primaryShareId);

//       // const phoneNumber = from.replace('whatsapp:', '');
//       const phoneNumber = from.replace('whatsapp:', '').replace(/^\+1/, '');
//       const baseSessionId = `whatsapp_${phoneNumber.replace(/[^0-9]/g, '')}_${assistantId}`;
//       console.log('→ Generated base sessionId:', baseSessionId);
      
//       // Check for active session
//       let sessionId = baseSessionId;
//       let createNewSession = false;
      
//       try {
//         const sessionQuery = await firestore.db.collection('chat_sessions')
//           .where('assistantId', '==', assistantId)
//           .where('phoneNumber', '==', phoneNumber)
//           .orderBy('lastActivity', 'desc')
//           .limit(1)
//           .get();
        
//         if (!sessionQuery.empty) {
//           const session = sessionQuery.docs[0].data();
//           const lastActivity = session.lastActivity.toDate();
//           const now = new Date();
//           const inactivityTimeSeconds = (now - lastActivity) / 1000;
          
//           console.log(`→ Last activity: ${inactivityTimeSeconds.toFixed(2)} seconds ago`);
          
//           if (inactivityTimeSeconds <= 60) {
//             sessionId = session.sessionId;
//             console.log('→ Reusing active session:', sessionId);
//           } else {
//             createNewSession = true;
//             sessionId = `${baseSessionId}_${Date.now()}`;
//             console.log('→ Creating new session due to inactivity:', sessionId);
//           }
//         } else {
//           createNewSession = true;
//           sessionId = `${baseSessionId}_${Date.now()}`;
//           console.log('→ Creating new session (no previous session):', sessionId);
//         }
//       } catch (sessionCheckError) {
//         console.error('→ Error checking session activity:', sessionCheckError);
//         createNewSession = true;
//         sessionId = `${baseSessionId}_${Date.now()}`;
//       }

//       console.log('→ Using session:', { sessionId, isNewSession: createNewSession });

//       // Update session document
//       await firestore.db.collection('chat_sessions').doc(sessionId).set({
//         assistantId,
//         phoneNumber,
//         lastActivity: new Date(),
//         sessionId
//       }, { merge: true });

//       console.log('→ STEP 2: Checking for patient mapping');
//       let patientId = null;
//       // const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
//       //   .where('phoneNumber', '==', phoneNumber)
//       //   .where('assistantId', '==', assistantId)
//       //   .limit(1)
//       //   .get();
//       const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
//         .where('phoneNumber', '==', phoneNumber)
//         .limit(1)
//         .get();

//       if (!mappingSnapshot.empty) {
//         patientId = mappingSnapshot.docs[0].data().patientId;
//         console.log('→ Found patient mapping:', { patientId });
//       } else {
//         console.log('→ No patient mapping found for this phone number');
//       }

//       console.log('→ WhatsApp message received:', {
//         from,
//         body,
//         assistantId,
//         primaryShareId,
//         sessionId,
//         patientId,
//         isNewSession: createNewSession
//       });

//       console.log('→ STEP 3: Calling chat API');
//       console.log('→ API URL:', `${process.env.API_URL}/api/shared/${primaryShareId}/chat`);
//       console.log('→ API request payload:', {
//         message: body.trim(),
//         sessionId,
//         language: 'en',
//         patientId
//       });
      
//       const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${primaryShareId}/chat`, {
//         method: 'POST',
//         headers: {
//           'Content-Type': 'application/json',
//           'Accept': 'application/json'
//         },
//         body: JSON.stringify({
//           message: body.trim(),
//           sessionId: sessionId,
//           language: 'en',
//           patientId
//         })
//       });
      
//       console.log('→ API response status:', apiResponse.status);
      
//       const data = await apiResponse.json();
//       console.log('→ API response data:', data);
      
//       if (!apiResponse.ok) {
//         throw new Error(`API Error: ${data.error}`);
//       }

//       console.log('→ STEP 4: Saving assistant response to Firestore');
//       // await firestore.saveSharedChatMessage({
//       //   shareId: primaryShareId,
//       //   sessionId,
//       //   assistantId: assistant.id,
//       //   role: 'assistant',
//       //   content: data.content,
//       //   createdAt: new Date(),
//       //   contextUsed: [],
//       //   patientId
//       // });
//       console.log('→ Assistant message saved successfully');

//       console.log('→ STEP 5: Sending WhatsApp response via Twilio');
//       const twilioService = new TwilioService();
      
//       await twilioService.sendWhatsAppMessage(
//         from, 
//         data.content, 
//         primaryShareId, 
//         sessionId, 
//         assistant.id,
//         patientId,
//         true
//       );
//       console.log('→ WhatsApp response sent successfully');

//       console.log('→ STEP 6: Sending TwiML response back to Twilio');
//       const twiml = new twilio.twiml.MessagingResponse();
//       res.type('text/xml');
//       res.send(twiml.toString());
//       console.log('→ WEBHOOK COMPLETE: Response sent to Twilio');
//     } catch (error) {
//       console.error('→ ERROR handling WhatsApp message:', error);
//       console.error('→ Error stack:', error.stack);
//       res.type('text/xml');
//       res.send(new twilio.twiml.MessagingResponse().toString());
//       console.log('→ WEBHOOK ERROR: Empty TwiML response sent to Twilio');
//     }
//   }
// );

// // Messaging service
// router.post(
//   '/assistants/:assistantId/sms/incoming',
//   express.urlencoded({ extended: true }),
//   async (req, res) => {
//     const { assistantId } = req.params;
//     const from = req.body.From;
//     const body = req.body.Body || '';
    
//     console.log('→ WEBHOOK ENTRY: SMS incoming webhook triggered', {
//       assistantId,
//       timestamp: new Date().toISOString()
//     });
    
//     console.log('→ REQUEST BODY:', JSON.stringify(req.body, null, 2));
    
//     try {
//       console.log('→ STEP 1: Fetching assistant data');
//       const assistant = await firestore.getAssistant(assistantId);
//       if (!assistant) {
//         console.error('→ ERROR: Assistant not found:', assistantId);
//         res.type('text/xml');
//         return res.send(new twilio.twiml.MessagingResponse().toString());
//       }
//       console.log('→ Assistant found:', {
//         id: assistant.id,
//         name: assistant.name,
//         hasFlowData: !!assistant.flowData,
//         hasVoiceShareId: !!assistant.voiceShareId
//       });

//       const primaryShareId = assistant.voiceShareId;
//       if (!primaryShareId) {
//         console.error('→ ERROR: No primary share set for assistant:', assistantId);
//         res.type('text/xml');
//         return res.send(new twilio.twiml.MessagingResponse().toString());
//       }
//       console.log('→ Primary shareId found:', primaryShareId);

//       // const phoneNumber = from;
//       const phoneNumber = from.replace(/^\+1/, '');
//       const baseSessionId = `sms_${phoneNumber.replace(/[^0-9]/g, '')}_${assistantId}`;
//       console.log('→ Generated base sessionId:', baseSessionId);
      
//       // Check for active session
//       let sessionId = baseSessionId;
//       let createNewSession = false;
      
//       try {
//         const sessionQuery = await firestore.db.collection('chat_sessions')
//           .where('assistantId', '==', assistantId)
//           .where('phoneNumber', '==', phoneNumber)
//           .orderBy('lastActivity', 'desc')
//           .limit(1)
//           .get();
        
//         if (!sessionQuery.empty) {
//           const session = sessionQuery.docs[0].data();
//           const lastActivity = session.lastActivity.toDate();
//           const now = new Date();
//           const inactivityTimeSeconds = (now - lastActivity) / 1000;
          
//           console.log(`→ Last activity: ${inactivityTimeSeconds.toFixed(2)} seconds ago`);
          
//           if (inactivityTimeSeconds <= 60) {
//             sessionId = session.sessionId;
//             console.log('→ Reusing active session:', sessionId);
//           } else {
//             createNewSession = true;
//             sessionId = `${baseSessionId}_${Date.now()}`;
//             console.log('→ Creating new session due to inactivity:', sessionId);
//           }
//         } else {
//           createNewSession = true;
//           sessionId = `${baseSessionId}_${Date.now()}`;
//           console.log('→ Creating new session (no previous session):', sessionId);
//         }
//       } catch (sessionCheckError) {
//         console.error('→ Error checking session activity:', sessionCheckError);
//         createNewSession = true;
//         sessionId = `${baseSessionId}_${Date.now()}`;
//       }

//       console.log('→ Using session:', { sessionId, isNewSession: createNewSession });

//       // Update session document
//       await firestore.db.collection('chat_sessions').doc(sessionId).set({
//         assistantId,
//         phoneNumber,
//         lastActivity: new Date(),
//         sessionId
//       }, { merge: true });

//       console.log('→ STEP 2: Checking for patient mapping');
//       let patientId = null;
//       // const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
//       //   .where('phoneNumber', '==', phoneNumber)
//       //   .where('assistantId', '==', assistantId)
//       //   .limit(1)
//       //   .get();
//       const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
//         .where('phoneNumber', '==', phoneNumber)
//         .limit(1)
//         .get();

//       if (!mappingSnapshot.empty) {
//         patientId = mappingSnapshot.docs[0].data().patientId;
//         console.log('→ Found patient mapping:', { patientId });
//       } else {
//         console.log('→ No patient mapping found for this phone number');
//       }

//       console.log('→ SMS message received:', {
//         from,
//         body,
//         assistantId,
//         primaryShareId,
//         phoneNumber,
//         sessionId,
//         patientId,
//         isNewSession: createNewSession
//       });

//       console.log('→ STEP 3: Calling chat API');
//       console.log('→ API URL:', `${process.env.API_URL}/api/shared/${primaryShareId}/chat`);
//       console.log('→ API request payload:', {
//         message: body.trim(),
//         sessionId,
//         language: 'en',
//         patientId
//       });
      
//       const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${primaryShareId}/chat`, {
//         method: 'POST',
//         headers: {
//           'Content-Type': 'application/json',
//           'Accept': 'application/json'
//         },
//         body: JSON.stringify({
//           message: body.trim(),
//           sessionId: sessionId,
//           language: 'en',
//           patientId
//         })
//       });
      
//       console.log('→ API response status:', apiResponse.status);
      
//       const data = await apiResponse.json();
//       console.log('→ API response data:', data);
      
//       if (!apiResponse.ok) {
//         throw new Error(`API Error: ${data.error}`);
//       }

//       console.log('→ STEP 4: Saving assistant response to Firestore');
//       // await firestore.saveSharedChatMessage({
//       //   shareId: primaryShareId,
//       //   sessionId,
//       //   assistantId: assistant.id,
//       //   role: 'assistant',
//       //   content: data.content,
//       //   createdAt: new Date(),
//       //   contextUsed: [],
//       //   patientId
//       // });
//       console.log('→ Assistant message saved successfully');

//       console.log('→ STEP 5: Sending SMS response via Twilio');
//       const twilioService = new TwilioService();
      
//       await twilioService.sendSmsMessage(
//         from, 
//         data.content, 
//         primaryShareId, 
//         sessionId, 
//         assistant.id,
//         patientId,
//         true
//       );
//       console.log('→ SMS response sent successfully');

//       console.log('→ STEP 6: Sending TwiML response back to Twilio');
//       const twiml = new twilio.twiml.MessagingResponse();
//       res.type('text/xml');
//       res.send(twiml.toString());
//       console.log('→ WEBHOOK COMPLETE: Response sent to Twilio');
//     } catch (error) {
//       console.error('→ ERROR handling SMS message:', error);
//       console.error('→ Error stack:', error.stack);
//       res.type('text/xml');
//       res.send(new twilio.twiml.MessagingResponse().toString());
//       console.log('→ WEBHOOK ERROR: Empty TwiML response sent to Twilio');
//     }
//   }
// );
// Replace the existing /assistants/:assistantId/whatsapp/incoming route
router.post(
  '/assistants/:assistantId/whatsapp/incoming',
  express.urlencoded({ extended: true }),
  async (req, res) => {
    const { assistantId } = req.params;
    const from = req.body.From;
    const body = req.body.Body || '';
    const isUserInitiated = req.query.is_user_initiated === 'true';

    console.log('→ WEBHOOK ENTRY: WhatsApp incoming webhook triggered', {
      assistantId,
      timestamp: new Date().toISOString()
    });
    
    console.log('→ REQUEST BODY:', JSON.stringify(req.body, null, 2));
    
    try {

      console.log('→ STEP 1: Fetching assistant data');
      const assistant = await firestore.getAssistant(assistantId);
      if (!assistant) {
        console.error('→ ERROR: Assistant not found:', assistantId);
        res.type('text/xml');
        return res.send(new twilio.twiml.MessagingResponse().toString());
      }
      console.log('→ Assistant found:', {
        id: assistant.id,
        name: assistant.name,
        hasFlowData: !!assistant.flowData,
        hasVoiceShareId: !!assistant.voiceShareId
      });

      const primaryShareId = assistant.voiceShareId;
      if (!primaryShareId) {
        console.error('→ ERROR: No primary share set for assistant:', assistantId);
        res.type('text/xml');
        return res.send(new twilio.twiml.MessagingResponse().toString());
      }
      console.log('→ Primary shareId found:', primaryShareId);

      const phoneNumber = from.replace('whatsapp:', '').replace(/^\+1/, '');

      console.log('→ STEP 0: Checking for patient mapping');
      let patientId = null;
      const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        .where('phoneNumber', '==', phoneNumber)
        .limit(1)
        .get();

      if (!mappingSnapshot.empty) {
        patientId = mappingSnapshot.docs[0].data().patientId;
        console.log('→ Found patient mapping:', { patientId });
      } else {
        console.log('→ No patient mapping found for this phone number');
      }
      // =================== INSERT PREGNANCY TEST CHECK HERE ===================
      // Step 6: Check pregnancy test at beginning of route
      if (patientId) {
        console.log(`[WHATSAPP ROUTE] Calling pregnancy_test_completion for ${phoneNumber}: patientId=${patientId}, timestamp=${new Date().toISOString()}`);
        const pregnancyResult = await pregnancy_test_completion(phoneNumber, patientId, body, from, primaryShareId, assistant);
        
        if (pregnancyResult === true) {
          // Pregnancy test in progress, exit
          const twiml = new twilio.twiml.MessagingResponse();
          res.type('text/xml');
          res.send(twiml.toString());
          console.log('→ WEBHOOK COMPLETE: Pregnancy test in progress');
          return;
        } else if (pregnancyResult === 'completed') {
          // Pregnancy test just completed, continue with base session for normal flow
          console.log('→ PREGNANCY TEST: Completed, continuing with base session');
          console.log('→ PREGNANCY TEST: Completed, stopping further processing for this message.');
          const twiml = new twilio.twiml.MessagingResponse();
          res.type('text/xml');
          res.send(twiml.toString());
          console.log('→ WEBHOOK COMPLETE: Pregnancy test completed and response sent.');
          return; 
        }
        // If pregnancyResult === false, pregnancy test already completed, continue normal flow
      }



      const baseSessionId = `whatsapp_${phoneNumber.replace(/[^0-9]/g, '')}_${assistantId}`;
      console.log('→ Generated baseSessionId:', baseSessionId);
      
      // Check for active or taken-over session
      let sessionId = baseSessionId;
      let createNewSession = false;
      let sessionData = {};
      
      try {
        // Query 1: Check for taken-over sessions
        console.log('→ Checking for taken-over session');
        const takenOverQuery = await firestore.db.collection('chat_sessions')
          .where('phoneNumber', '==', phoneNumber)
          .where('patientId', '==', patientId)  // ADD THIS LINE
          .where('type', '==', 'whatsapp')
          .where('isOnboarding', '!=', true)  // <-- ADD THIS LINE
          .orderBy('lastActivity', 'desc')
          .limit(1)
          .get();

        // Query 2: Original query for assistant-specific sessions
        console.log('→ Checking for assistant-specific session');
        const assistantQuery = await firestore.db.collection('chat_sessions')
          .where('assistantId', '==', assistantId)
          .where('phoneNumber', '==', phoneNumber)
          .where('patientId', '==', patientId)  // ADD THIS LINE
          .where('type', '==', 'whatsapp')
          .where('isOnboarding', '!=', true)  // <-- ADD THIS LINE
          .orderBy('lastActivity', 'desc')
          .limit(1)
          .get();

        // Determine the most recent session
        let selectedSession = null;
        let takenOverSession = takenOverQuery.empty ? null : takenOverQuery.docs[0].data();
        let assistantSession = assistantQuery.empty ? null : assistantQuery.docs[0].data();

        const now = new Date();
        const TAKEN_OVER_TIMEOUT_SECONDS = 300; // 5 minutes

        if (takenOverSession) {
          const takenOverLastActivity = takenOverSession.lastActivity.toDate();
          const takenOverInactivitySeconds = (now - takenOverLastActivity) / 1000;
          console.log(`→ Taken-over session inactivity: ${takenOverInactivitySeconds.toFixed(2)} seconds`);

          if (takenOverInactivitySeconds <= TAKEN_OVER_TIMEOUT_SECONDS) {
            // Use taken-over session if within 5 minutes
            selectedSession = takenOverSession;
            console.log('→ Selected active taken-over session:', {
              sessionId: selectedSession.sessionId,
              takenOverBy: selectedSession.takenOverBy
            });
          } else {
            console.log('→ Taken-over session expired, checking assistant-specific session');
          }
        }

        if (!selectedSession && assistantSession) {
          const assistantLastActivity = assistantSession.lastActivity.toDate();
          const assistantInactivitySeconds = (now - assistantLastActivity) / 1000;
          console.log(`→ Assistant session inactivity: ${assistantInactivitySeconds.toFixed(2)} seconds`);

          if (assistantInactivitySeconds <= 60) {
            selectedSession = assistantSession;
            console.log('→ Selected active assistant-specific session:', {
              sessionId: selectedSession.sessionId
            });
          }
        }

        if (selectedSession) {
          sessionData = selectedSession;
          sessionId = selectedSession.sessionId;
          console.log('→ Reusing active session:', sessionId);

          // Update lastActivity only for non-taken-over sessions
          if (!sessionData.takenOverBy) {
            await firestore.db.collection('chat_sessions').doc(sessionId).set(
              { lastActivity: new Date() },
              { merge: true }
            );
          }
        } else {
          createNewSession = true;
          sessionId = `${baseSessionId}_${Date.now()}`;
          console.log('→ Creating new session (no active session found):', sessionId);
        }
      } catch (sessionCheckError) {
        console.error('→ Error checking session activity:', sessionCheckError);
        createNewSession = true;
        sessionId = `${baseSessionId}_${Date.now()}`;
      }

      console.log('→ Using session:', { sessionId, isNewSession: createNewSession });

      // console.log('→ STEP 2: Checking for patient mapping');
      // let patientId = null;
      // const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
      //   .where('phoneNumber', '==', phoneNumber)
      //   .limit(1)
      //   .get();

      // if (!mappingSnapshot.empty) {
      //   patientId = mappingSnapshot.docs[0].data().patientId;
      //   console.log('→ Found patient mapping:', { patientId });
      // } else {
      //   console.log('→ No patient mapping found for this phone number');
      // }
      
      // Update session document with all required fields
      await firestore.db.collection('chat_sessions').doc(sessionId).set({
        sessionId,
        assistantId,
        phoneNumber,
        type: 'whatsapp',
        shareId: primaryShareId,
        userId: assistant.userId,
        patientId,
        lastActivity: new Date(),
        is_user_initiated: isUserInitiated, // ADD THIS LINE
        isOnboarding: false // <-- ADD THIS LINE


      }, { merge: true });

      console.log('→ WhatsApp message received:', {
        from,
        body,
        assistantId,
        primaryShareId,
        sessionId,
        patientId,
        isNewSession: createNewSession,
        takenOverBy: sessionData.takenOverBy
      });

      // Check if session is taken over by a doctor
      if (sessionData.takenOverBy) {
        console.log('→ Session is taken over by doctor:', sessionData.takenOverBy);
        
        // Save user message to shared_chat_messages
        await firestore.saveSharedChatMessage({
          shareId: primaryShareId,
          sessionId,
          assistantId: assistant.id,
          role: 'user',
          content: body.trim(),
          createdAt: new Date(),
          patientId,
        });
        console.log('→ Saved user message to shared_chat_messages (session taken over)');

        // Record analytics
        axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
          message: body.trim(),
          response: 'Your message has been received. The doctor will respond shortly.',
          sessionId: sessionId,
          timestamp: new Date().toISOString()
        }).then(analyticsResponse => {
          console.log('Analytics recorded successfully for taken-over message:', analyticsResponse.data.analytics_id);
        }).catch(analyticsError => {
          console.error('Error recording analytics for taken-over message:', analyticsError.message);
        });

        // Send an acknowledgment message to the patient
        const twilioService = new TwilioService();
        await twilioService.sendWhatsAppMessage(
          from,
          'Your message has been received. The doctor will respond shortly.',
          primaryShareId,
          sessionId,
          assistant.id,
          patientId,
          true
        );
        
        console.log('→ Sent acknowledgment message to patient (session is taken over)');
        
        console.log('→ STEP 5: Sending TwiML response back to Twilio');
        const twiml = new twilio.twiml.MessagingResponse();
        res.type('text/xml');
        res.send(twiml.toString());
        console.log('→ WEBHOOK COMPLETE: Response sent to Twilio');
      } else {
        // Process with AI if not taken over
        console.log('→ STEP 3: Calling chat API for AI response');
        console.log('→ API URL:', `${process.env.API_URL}/api/shared/${primaryShareId}/chat`);
        console.log('→ API request payload:', {
          message: body.trim(),
          sessionId,
          language: 'en',
          patientId
        });
        
        const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${primaryShareId}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({
            message: body.trim(),
            sessionId: sessionId,
            language: 'en',
            patientId
          })
        });
        
        console.log('→ API response status:', apiResponse.status);
        
        const data = await apiResponse.json();
        console.log('→ API response data:', data);
        
        if (!apiResponse.ok) {
          throw new Error(`API Error: ${data.error}`);
        }

        console.log('→ STEP 4: Sending WhatsApp response via Twilio');
        const twilioService = new TwilioService();
        
        await twilioService.sendWhatsAppMessage(
          from, 
          data.content, 
          primaryShareId, 
          sessionId, 
          assistant.id,
          patientId,
          true
        );
        console.log('→ WhatsApp response sent successfully');

        console.log('→ STEP 5: Sending TwiML response back to Twilio');
        const twiml = new twilio.twiml.MessagingResponse();
        res.type('text/xml');
        res.send(twiml.toString());
        console.log('→ WEBHOOK COMPLETE: Response sent to Twilio');
      }
    } catch (error) {
      console.error('→ ERROR handling WhatsApp message:', error);
      console.error('→ Error stack:', error.stack);
      res.type('text/xml');
      res.send(new twilio.twiml.MessagingResponse().toString());
      console.log('→ WEBHOOK ERROR: Empty TwiML response sent to Twilio');
    }
  }
);

router.post(
  '/assistants/:assistantId/web/incoming',
  express.urlencoded({ extended: true }), // EXACT SAME AS WHATSAPP
  async (req, res) => {
    const { assistantId } = req.params;
    const from = req.body.From;
    const body = req.body.Body || '';
    const isUserInitiated = req.query.is_user_initiated === 'true';

    console.log('→ WEBHOOK ENTRY: Web incoming webhook triggered', {
      assistantId,
      timestamp: new Date().toISOString()
    });
    
    console.log('→ REQUEST BODY:', JSON.stringify(req.body, null, 2));
    
    try {

      console.log('→ STEP 1: Fetching assistant data');
      const assistant = await firestore.getAssistant(assistantId);
      if (!assistant) {
        console.error('→ ERROR: Assistant not found:', assistantId);
        return res.status(404).json({ error: 'Assistant not found' }); // ONLY CHANGE: JSON instead of TwiML
      }
      console.log('→ Assistant found:', {
        id: assistant.id,
        name: assistant.name,
        hasFlowData: !!assistant.flowData,
        hasVoiceShareId: !!assistant.voiceShareId
      });

      const primaryShareId = assistant.voiceShareId;
      if (!primaryShareId) {
        console.error('→ ERROR: No primary share set for assistant:', assistantId);
        return res.status(400).json({ error: 'No primary share set for assistant' }); // ONLY CHANGE: JSON instead of TwiML
      }
      console.log('→ Primary shareId found:', primaryShareId);

      const phoneNumber = from.replace('whatsapp:', '').replace(/^\+1/, ''); // KEEPING EXACT SAME

      console.log('→ STEP 0: Checking for patient mapping');
      let patientId = null;
      const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        .where('phoneNumber', '==', phoneNumber)
        .limit(1)
        .get();

      if (!mappingSnapshot.empty) {
        patientId = mappingSnapshot.docs[0].data().patientId;
        console.log('→ Found patient mapping:', { patientId });
      } else {
        console.log('→ No patient mapping found for this phone number');
      }
      // =================== INSERT PREGNANCY TEST CHECK HERE ===================
      // Step 6: Check pregnancy test at beginning of route
      if (patientId) {
        console.log(`[WEB ROUTE] Calling pregnancy_test_completion for ${phoneNumber}: patientId=${patientId}, timestamp=${new Date().toISOString()}`);
        const pregnancyResult = await pregnancy_test_completion(phoneNumber, patientId, body, from, primaryShareId, assistant);
        
        if (pregnancyResult === true) {
          // Pregnancy test in progress, exit
          console.log('→ WEBHOOK COMPLETE: Pregnancy test in progress');
          return res.json({ content: "" }); // ONLY CHANGE: JSON instead of TwiML
        } else if (pregnancyResult === 'completed') {
          // Pregnancy test just completed, continue with base session for normal flow
          console.log('→ PREGNANCY TEST: Completed, continuing with base session');
          console.log('→ PREGNANCY TEST: Completed, stopping further processing for this message.');
          console.log('→ WEBHOOK COMPLETE: Pregnancy test completed and response sent.');
          return res.json({ content: "" }); // ONLY CHANGE: JSON instead of TwiML
        }
        // If pregnancyResult === false, pregnancy test already completed, continue normal flow
      }



      const baseSessionId = `web_${phoneNumber.replace(/[^0-9]/g, '')}_${assistantId}`; // ONLY CHANGE: 'web' prefix
      console.log('→ Generated baseSessionId:', baseSessionId);
      
      // Check for active or taken-over session
      let sessionId = baseSessionId;
      let createNewSession = false;
      let sessionData = {};
      
      try {
        // Query 1: Check for taken-over sessions
        console.log('→ Checking for taken-over session');
        const takenOverQuery = await firestore.db.collection('chat_sessions')
          .where('phoneNumber', '==', phoneNumber)
          .where('patientId', '==', patientId)  // ADD THIS LINE
          .where('type', '==', 'web') // ONLY CHANGE: 'web' instead of 'whatsapp'
          .where('isOnboarding', '!=', true)  // <-- ADD THIS LINE
          .orderBy('lastActivity', 'desc')
          .limit(1)
          .get();

        // Query 2: Original query for assistant-specific sessions
        console.log('→ Checking for assistant-specific session');
        const assistantQuery = await firestore.db.collection('chat_sessions')
          .where('assistantId', '==', assistantId)
          .where('phoneNumber', '==', phoneNumber)
          .where('patientId', '==', patientId)  // ADD THIS LINE
          .where('type', '==', 'web') // ONLY CHANGE: 'web' instead of 'whatsapp'
          .where('isOnboarding', '!=', true)  // <-- ADD THIS LINE
          .orderBy('lastActivity', 'desc')
          .limit(1)
          .get();

        // Determine the most recent session
        let selectedSession = null;
        let takenOverSession = takenOverQuery.empty ? null : takenOverQuery.docs[0].data();
        let assistantSession = assistantQuery.empty ? null : assistantQuery.docs[0].data();

        const now = new Date();
        const TAKEN_OVER_TIMEOUT_SECONDS = 300; // 5 minutes

        if (takenOverSession) {
          const takenOverLastActivity = takenOverSession.lastActivity.toDate();
          const takenOverInactivitySeconds = (now - takenOverLastActivity) / 1000;
          console.log(`→ Taken-over session inactivity: ${takenOverInactivitySeconds.toFixed(2)} seconds`);

          if (takenOverInactivitySeconds <= TAKEN_OVER_TIMEOUT_SECONDS) {
            // Use taken-over session if within 5 minutes
            selectedSession = takenOverSession;
            console.log('→ Selected active taken-over session:', {
              sessionId: selectedSession.sessionId,
              takenOverBy: selectedSession.takenOverBy
            });
          } else {
            console.log('→ Taken-over session expired, checking assistant-specific session');
          }
        }

        if (!selectedSession && assistantSession) {
          const assistantLastActivity = assistantSession.lastActivity.toDate();
          const assistantInactivitySeconds = (now - assistantLastActivity) / 1000;
          console.log(`→ Assistant session inactivity: ${assistantInactivitySeconds.toFixed(2)} seconds`);

          if (assistantInactivitySeconds <= 60) {
            selectedSession = assistantSession;
            console.log('→ Selected active assistant-specific session:', {
              sessionId: selectedSession.sessionId
            });
          }
        }

        if (selectedSession) {
          sessionData = selectedSession;
          sessionId = selectedSession.sessionId;
          console.log('→ Reusing active session:', sessionId);

          // Update lastActivity only for non-taken-over sessions
          if (!sessionData.takenOverBy) {
            await firestore.db.collection('chat_sessions').doc(sessionId).set(
              { lastActivity: new Date() },
              { merge: true }
            );
          }
        } else {
          createNewSession = true;
          sessionId = `${baseSessionId}_${Date.now()}`;
          console.log('→ Creating new session (no active session found):', sessionId);
        }
      } catch (sessionCheckError) {
        console.error('→ Error checking session activity:', sessionCheckError);
        createNewSession = true;
        sessionId = `${baseSessionId}_${Date.now()}`;
      }

      console.log('→ Using session:', { sessionId, isNewSession: createNewSession });


      // Update session document with all required fields
      await firestore.db.collection('chat_sessions').doc(sessionId).set({
        sessionId,
        assistantId,
        phoneNumber,
        type: 'web', // ONLY CHANGE: 'web' instead of 'whatsapp'
        shareId: primaryShareId,
        userId: assistant.userId,
        patientId,
        lastActivity: new Date(),
        is_user_initiated: isUserInitiated, // ADD THIS LINE
        isOnboarding: false // <-- ADD THIS LINE


      }, { merge: true });

      console.log('→ Web message received:', {
        from,
        body,
        assistantId,
        primaryShareId,
        sessionId,
        patientId,
        isNewSession: createNewSession,
        takenOverBy: sessionData.takenOverBy
      });

      // Check if session is taken over by a doctor
      if (sessionData.takenOverBy) {
        console.log('→ Session is taken over by doctor:', sessionData.takenOverBy);
        
        // Save user message to shared_chat_messages
        await firestore.saveSharedChatMessage({
          shareId: primaryShareId,
          sessionId,
          assistantId: assistant.id,
          role: 'user',
          content: body.trim(),
          createdAt: new Date(),
          patientId,
        });
        console.log('→ Saved user message to shared_chat_messages (session taken over)');

        // Record analytics
        axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
          message: body.trim(),
          response: 'Your message has been received. The doctor will respond shortly.',
          sessionId: sessionId,
          timestamp: new Date().toISOString()
        }).then(analyticsResponse => {
          console.log('Analytics recorded successfully for taken-over message:', analyticsResponse.data.analytics_id);
        }).catch(analyticsError => {
          console.error('Error recording analytics for taken-over message:', analyticsError.message);
        });

        // ONLY CHANGE: Send JSON response instead of Twilio message
        console.log('→ Sent acknowledgment response to patient (session is taken over)');
        console.log('→ STEP 5: Sending JSON response');
        console.log('→ WEBHOOK COMPLETE: Response sent');
        
        return res.json({
          content: 'Your message has been received. The doctor will respond shortly.',
          sessionId: sessionId
        });
      } else {
        // Process with AI if not taken over
        console.log('→ STEP 3: Calling chat API for AI response');
        console.log('→ API URL:', `${process.env.API_URL}/api/shared/${primaryShareId}/chat`);
        console.log('→ API request payload:', {
          message: body.trim(),
          sessionId,
          language: 'en',
          patientId
        });
        
        const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${primaryShareId}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({
            message: body.trim(),
            sessionId: sessionId,
            language: 'en',
            patientId
          })
        });
        
        console.log('→ API response status:', apiResponse.status);
        
        const data = await apiResponse.json();
        console.log('→ API response data:', data);
        
        if (!apiResponse.ok) {
          throw new Error(`API Error: ${data.error}`);
        }

        console.log('→ STEP 4: Sending Web response');
        
        // ONLY CHANGE: Send JSON response instead of Twilio message
        console.log('→ Web response sent successfully');
        console.log('→ STEP 5: Sending JSON response');
        console.log('→ WEBHOOK COMPLETE: Response sent');
        
        return res.json({
          content: data.content,
          sessionId: sessionId
        });
      }
    } catch (error) {
      console.error('→ ERROR handling Web message:', error);
      console.error('→ Error stack:', error.stack);
      console.log('→ WEBHOOK ERROR: Sending error response');
      
      // ONLY CHANGE: Send JSON error instead of TwiML
      return res.status(500).json({ 
        error: 'Failed to process message',
        content: "I'm having trouble processing your message. Please try again."
      });
    }
  }
);


// router.post(
//   '/assistants/:assistantId/whatsapp/incoming',
//   express.urlencoded({ extended: true }),
//   async (req, res) => {
//     const { assistantId } = req.params;
//     const from = req.body.From;
//     const body = req.body.Body || '';
    
//     console.log('→ WEBHOOK ENTRY: WhatsApp incoming webhook triggered', {
//       assistantId,
//       timestamp: new Date().toISOString()
//     });
    
//     console.log('→ REQUEST BODY:', JSON.stringify(req.body, null, 2));
    
//     try {
//       console.log('→ STEP 1: Fetching assistant data');
//       const assistant = await firestore.getAssistant(assistantId);
//       if (!assistant) {
//         console.error('→ ERROR: Assistant not found:', assistantId);
//         res.type('text/xml');
//         return res.send(new twilio.twiml.MessagingResponse().toString());
//       }
//       console.log('→ Assistant found:', {
//         id: assistant.id,
//         name: assistant.name,
//         hasFlowData: !!assistant.flowData,
//         hasVoiceShareId: !!assistant.voiceShareId
//       });

//       const primaryShareId = assistant.voiceShareId;
//       if (!primaryShareId) {
//         console.error('→ ERROR: No primary share set for assistant:', assistantId);
//         res.type('text/xml');
//         return res.send(new twilio.twiml.MessagingResponse().toString());
//       }
//       console.log('→ Primary shareId found:', primaryShareId);

//       const phoneNumber = from.replace('whatsapp:', '').replace(/^\+1/, '');
//       const baseSessionId = `whatsapp_${phoneNumber.replace(/[^0-9]/g, '')}_${assistantId}`;
//       console.log('→ Generated base sessionId:', baseSessionId);
      
//       // Check for active session
//       let sessionId = baseSessionId;
//       let createNewSession = false;
      
//       try {
        
//         const sessionQuery = await firestore.db.collection('chat_sessions')
//           .where('assistantId', '==', assistantId)
//           .where('phoneNumber', '==', phoneNumber)
//           .where('type', '==', 'whatsapp')
//           .orderBy('lastActivity', 'desc')
//           .limit(1)
//           .get();
        
//         if (!sessionQuery.empty) {
//           const session = sessionQuery.docs[0].data();
//           const lastActivity = session.lastActivity.toDate();
//           const now = new Date();
//           const inactivityTimeSeconds = (now - lastActivity) / 1000;
          
//           console.log(`→ Last activity: ${inactivityTimeSeconds.toFixed(2)} seconds ago`);
          
//           if (inactivityTimeSeconds <= 60) {
//             sessionId = session.sessionId;
//             console.log('→ Reusing active session:', sessionId);
//           } else {
//             createNewSession = true;
//             sessionId = `${baseSessionId}_${Date.now()}`;
//             console.log('→ Creating new session due to inactivity:', sessionId);
//           }
//         } else {
//           createNewSession = true;
//           sessionId = `${baseSessionId}_${Date.now()}`;
//           console.log('→ Creating new session (no previous session):', sessionId);
//         }
//       } catch (sessionCheckError) {
//         console.error('→ Error checking session activity:', sessionCheckError);
//         createNewSession = true;
//         sessionId = `${baseSessionId}_${Date.now()}`;
//       }

//       console.log('→ Using session:', { sessionId, isNewSession: createNewSession });

//       console.log('→ STEP 2: Checking for patient mapping');
//       let patientId = null;
//       const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
//         .where('phoneNumber', '==', phoneNumber)
//         .limit(1)
//         .get();

//       if (!mappingSnapshot.empty) {
//         patientId = mappingSnapshot.docs[0].data().patientId;
//         console.log('→ Found patient mapping:', { patientId });
//       } else {
//         console.log('→ No patient mapping found for this phone number');
//       }

//       // Get existing session data if available
//       const sessionRef = firestore.db.collection('chat_sessions').doc(sessionId);
//       const sessionDoc = await sessionRef.get();
//       const sessionData = sessionDoc.exists ? sessionDoc.data() : {};
      
//       // Save user message to shared_chat_messages
//       // await firestore.saveSharedChatMessage({
//       //   shareId: primaryShareId,
//       //   sessionId,
//       //   assistantId: assistant.id,
//       //   role: 'user',
//       //   content: body.trim(),
//       //   createdAt: new Date(),
//       //   patientId,
//       // });
//       if (sessionData.takenOverBy) {
//         await firestore.saveSharedChatMessage({
//           shareId: primaryShareId,
//           sessionId,
//           assistantId: assistant.id,
//           role: 'user',
//           content: body.trim(),
//           createdAt: new Date(),
//           patientId,
//         });
//         console.log('→ Saved user message to shared_chat_messages (session taken over)');

//         axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
//           message: body.trim(),
//           response: 'Your message has been received. The doctor will respond shortly.',
//           sessionId: sessionId,
//           timestamp: new Date().toISOString()
//         }).then(analyticsResponse => {
//           console.log('Analytics recorded successfully for taken-over message:', analyticsResponse.data.analytics_id);
//         }).catch(analyticsError => {
//           console.error('Error recording analytics for taken-over message:', analyticsError.message);
//           // Non-critical, so we just log the error
//         });
      
//       }

      

//       // Update session document with all required fields
//       await sessionRef.set({
//         sessionId,
//         assistantId,
//         phoneNumber,
//         type: 'whatsapp',
//         shareId: primaryShareId,
//         userId: assistant.userId,
//         patientId,
//         lastActivity: new Date(),
//       }, { merge: true });

//       console.log('→ WhatsApp message received:', {
//         from,
//         body,
//         assistantId,
//         primaryShareId,
//         sessionId,
//         patientId,
//         isNewSession: createNewSession,
//         takenOverBy: sessionData.takenOverBy
//       });

//       // Check if session is taken over by a doctor
//       if (sessionData.takenOverBy) {
//         console.log('→ Session is taken over by doctor:', sessionData.takenOverBy);
        
//         // Send an acknowledgment message to the patient
//         const twilioService = new TwilioService();
//         await twilioService.sendWhatsAppMessage(
//           from,
//           'Your message has been received. The doctor will respond shortly.',
//           primaryShareId,
//           sessionId,
//           assistant.id,
//           patientId,
//           true
//         );
        
//         console.log('→ Sent acknowledgment message to patient (session is taken over)');
//       } else {
//         // Process with AI if not taken over
//         console.log('→ STEP 3: Calling chat API for AI response');
//         console.log('→ API URL:', `${process.env.API_URL}/api/shared/${primaryShareId}/chat`);
//         console.log('→ API request payload:', {
//           message: body.trim(),
//           sessionId,
//           language: 'en',
//           patientId
//         });
        
//         const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${primaryShareId}/chat`, {
//           method: 'POST',
//           headers: {
//             'Content-Type': 'application/json',
//             'Accept': 'application/json'
//           },
//           body: JSON.stringify({
//             message: body.trim(),
//             sessionId: sessionId,
//             language: 'en',
//             patientId
//           })
//         });
        
//         console.log('→ API response status:', apiResponse.status);
        
//         const data = await apiResponse.json();
//         console.log('→ API response data:', data);
        
//         if (!apiResponse.ok) {
//           throw new Error(`API Error: ${data.error}`);
//         }

//         console.log('→ STEP 4: Sending WhatsApp response via Twilio');
//         const twilioService = new TwilioService();
        
//         await twilioService.sendWhatsAppMessage(
//           from, 
//           data.content, 
//           primaryShareId, 
//           sessionId, 
//           assistant.id,
//           patientId,
//           true
//         );
//         console.log('→ WhatsApp response sent successfully');
//       }

//       console.log('→ STEP 5: Sending TwiML response back to Twilio');
//       const twiml = new twilio.twiml.MessagingResponse();
//       res.type('text/xml');
//       res.send(twiml.toString());
//       console.log('→ WEBHOOK COMPLETE: Response sent to Twilio');
//     } catch (error) {
//       console.error('→ ERROR handling WhatsApp message:', error);
//       console.error('→ Error stack:', error.stack);
//       res.type('text/xml');
//       res.send(new twilio.twiml.MessagingResponse().toString());
//       console.log('→ WEBHOOK ERROR: Empty TwiML response sent to Twilio');
//     }
//   }
// );

// Replace the existing /assistants/:assistantId/sms/incoming route
router.post(
  '/assistants/:assistantId/sms/incoming',
  express.urlencoded({ extended: true }),
  async (req, res) => {
    const { assistantId } = req.params;
    const from = req.body.From;
    const body = req.body.Body || '';
    
    console.log('→ WEBHOOK ENTRY: SMS incoming webhook triggered', {
      assistantId,
      timestamp: new Date().toISOString()
    });
    
    console.log('→ REQUEST BODY:', JSON.stringify(req.body, null, 2));
    
    try {
      console.log('→ STEP 1: Fetching assistant data');
      const assistant = await firestore.getAssistant(assistantId);
      if (!assistant) {
        console.error('→ ERROR: Assistant not found:', assistantId);
        res.type('text/xml');
        return res.send(new twilio.twiml.MessagingResponse().toString());
      }
      console.log('→ Assistant found:', {
        id: assistant.id,
        name: assistant.name,
        hasFlowData: !!assistant.flowData,
        hasVoiceShareId: !!assistant.voiceShareId
      });

      const primaryShareId = assistant.voiceShareId;
      if (!primaryShareId) {
        console.error('→ ERROR: No primary share set for assistant:', assistantId);
        res.type('text/xml');
        return res.send(new twilio.twiml.MessagingResponse().toString());
      }
      console.log('→ Primary shareId found:', primaryShareId);

      const phoneNumber = from.replace(/^\+1/, '');
      const baseSessionId = `sms_${phoneNumber.replace(/[^0-9]/g, '')}_${assistantId}`;
      console.log('→ Generated base sessionId:', baseSessionId);
      
      // Check for active session
      let sessionId = baseSessionId;
      let createNewSession = false;
      
      try {
        const sessionQuery = await firestore.db.collection('chat_sessions')
          .where('assistantId', '==', assistantId)
          .where('phoneNumber', '==', phoneNumber)
          .where('type', '==', 'sms')
          .orderBy('lastActivity', 'desc')
          .limit(1)
          .get();
        
        if (!sessionQuery.empty) {
          const session = sessionQuery.docs[0].data();
          const lastActivity = session.lastActivity.toDate();
          const now = new Date();
          const inactivityTimeSeconds = (now - lastActivity) / 1000;
          
          console.log(`→ Last activity: ${inactivityTimeSeconds.toFixed(2)} seconds ago`);
          
          if (inactivityTimeSeconds <= 60) {
            sessionId = session.sessionId;
            console.log('→ Reusing active session:', sessionId);
          } else {
            createNewSession = true;
            sessionId = `${baseSessionId}_${Date.now()}`;
            console.log('→ Creating new session due to inactivity:', sessionId);
          }
        } else {
          createNewSession = true;
          sessionId = `${baseSessionId}_${Date.now()}`;
          console.log('→ Creating new session (no previous session):', sessionId);
        }
      } catch (sessionCheckError) {
        console.error('→ Error checking session activity:', sessionCheckError);
        createNewSession = true;
        sessionId = `${baseSessionId}_${Date.now()}`;
      }

      console.log('→ Using session:', { sessionId, isNewSession: createNewSession });

      console.log('→ STEP 2: Checking for patient mapping');
      let patientId = null;
      const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        .where('phoneNumber', '==', phoneNumber)
        .limit(1)
        .get();

      if (!mappingSnapshot.empty) {
        patientId = mappingSnapshot.docs[0].data().patientId;
        console.log('→ Found patient mapping:', { patientId });
      } else {
        console.log('→ No patient mapping found for this phone number');
      }

      // Get existing session data if available
      const sessionRef = firestore.db.collection('chat_sessions').doc(sessionId);
      const sessionDoc = await sessionRef.get();
      const sessionData = sessionDoc.exists ? sessionDoc.data() : {};
      
      // Save user message to shared_chat_messages
      // await firestore.saveSharedChatMessage({
      //   shareId: primaryShareId,
      //   sessionId,
      //   assistantId: assistant.id,
      //   role: 'user',
      //   content: body.trim(),
      //   createdAt: new Date(),
      //   patientId,
      // });

      if (sessionData.takenOverBy) {
        await firestore.saveSharedChatMessage({
          shareId: primaryShareId,
          sessionId,
          assistantId: assistant.id,
          role: 'user',
          content: body.trim(),
          createdAt: new Date(),
          patientId,
        });
        console.log('→ Saved user message to shared_chat_messages (session taken over)');

        // Non-blocking call to analyze the message
      axios.post(`${PYTHON_API_URL}/api/analyze-message`, {
        message: body.trim(),
        response: 'Your message has been received. The doctor will respond shortly.',
        sessionId: sessionId,
        timestamp: new Date().toISOString()
      }).then(analyticsResponse => {
        console.log('Analytics recorded successfully for taken-over message:', analyticsResponse.data.analytics_id);
      }).catch(analyticsError => {
        console.error('Error recording analytics for taken-over message:', analyticsError.message);
        // Non-critical, so we just log the error
      });
      }
      // Update session document with all required fields
      await sessionRef.set({
        sessionId,
        assistantId,
        phoneNumber,
        type: 'sms',
        shareId: primaryShareId,
        userId: assistant.userId,
        patientId,
        lastActivity: new Date(),
      }, { merge: true });

      console.log('→ SMS message received:', {
        from,
        body,
        assistantId,
        primaryShareId,
        sessionId,
        patientId,
        isNewSession: createNewSession,
        takenOverBy: sessionData.takenOverBy
      });

      // Check if session is taken over by a doctor
      if (sessionData.takenOverBy) {
        console.log('→ Session is taken over by doctor:', sessionData.takenOverBy);
        
        // Send an acknowledgment message to the patient
        const twilioService = new TwilioService();
        await twilioService.sendSmsMessage(
          from,
          'Your message has been received. The doctor will respond shortly.',
          primaryShareId,
          sessionId,
          assistant.id,
          patientId,
          true
        );
        
        console.log('→ Sent acknowledgment message to patient (session is taken over)');
      } else {
        // Process with AI if not taken over
        console.log('→ STEP 3: Calling chat API for AI response');
        console.log('→ API URL:', `${process.env.API_URL}/api/shared/${primaryShareId}/chat`);
        console.log('→ API request payload:', {
          message: body.trim(),
          sessionId,
          language: 'en',
          patientId
        });
        
        const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${primaryShareId}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({
            message: body.trim(),
            sessionId: sessionId,
            language: 'en',
            patientId
          })
        });
        
        console.log('→ API response status:', apiResponse.status);
        
        const data = await apiResponse.json();
        console.log('→ API response data:', data);
        
        if (!apiResponse.ok) {
          throw new Error(`API Error: ${data.error}`);
        }

        console.log('→ STEP 4: Sending SMS response via Twilio');
        const twilioService = new TwilioService();
        
        await twilioService.sendSmsMessage(
          from, 
          data.content, 
          primaryShareId, 
          sessionId, 
          assistant.id,
          patientId,
          true
        );
        console.log('→ SMS response sent successfully');
      }

      console.log('→ STEP 5: Sending TwiML response back to Twilio');
      const twiml = new twilio.twiml.MessagingResponse();
      res.type('text/xml');
      res.send(twiml.toString());
      console.log('→ WEBHOOK COMPLETE: Response sent to Twilio');
    } catch (error) {
      console.error('→ ERROR handling SMS message:', error);
      console.error('→ Error stack:', error.stack);
      res.type('text/xml');
      res.send(new twilio.twiml.MessagingResponse().toString());
      console.log('→ WEBHOOK ERROR: Empty TwiML response sent to Twilio');
    }
  }
);
// Direct shared link WhatsApp handler
// router.post(
//   '/shared/:shareId/whatsapp/incoming',
//   validateSharedAccess,
//   express.urlencoded({ extended: true }),
//   async (req, res) => {
//     const { shareId } = req.params;
//     const from = req.body.From;
//     const body = req.body.Body || '';
    
//     try {
//       // Get the share data
//       const share = await firestore.getShareLink(shareId);
//       if (!share) {
//         throw new Error('Share not found');
//       }
      
//       const assistant = await firestore.getAssistant(share.assistantId);
//       if (!assistant) {
//         throw new Error('Assistant not found');
//       }
      
//       // Create a consistent session ID based on the phone number
//       const phoneNumber = from.replace('whatsapp:', '');
//       const sessionId = `whatsapp_${phoneNumber.replace(/[^0-9]/g, '')}_${shareId}`;
      
//       console.log('WhatsApp message received (shared link):', {
//         from,
//         body,
//         shareId,
//         sessionId
//       });
      
//       // Save the user message to Firestore first
//       await firestore.saveSharedChatMessage({
//         shareId,
//         sessionId,
//         assistantId: share.assistantId,
//         role: 'user',
//         content: body.trim(),
//         createdAt: new Date()
//       });
      
//       // Process the message through your existing API
//       const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${shareId}/chat`, {
//         method: 'POST',
//         headers: {
//           'Content-Type': 'application/json',
//           'Accept': 'application/json'
//         },
//         body: JSON.stringify({
//           message: body.trim(),
//           sessionId: sessionId,
//           language: 'en'
//         })
//       });
      
//       const data = await apiResponse.json();
      
//       if (!apiResponse.ok) {
//         throw new Error(`API Error: ${data.error}`);
//       }
      
//       // Save the assistant's response to Firestore
//       await firestore.saveSharedChatMessage({
//         shareId,
//         sessionId,
//         assistantId: share.assistantId,
//         role: 'assistant',
//         content: data.content,
//         createdAt: new Date(),
//         contextUsed: []
//       });
      
//       // Send the response back via WhatsApp
//       const twilioService = new TwilioService();
//       await twilioService.sendWhatsAppMessage(from, data.content);
      
//       // Respond to Twilio with empty TwiML
//       const twiml = new twilio.twiml.MessagingResponse();
//       res.type('text/xml');
//       res.send(twiml.toString());
//     } catch (error) {
//       console.error('Error handling WhatsApp message (shared link):', error);
//       res.type('text/xml');
//       res.send(new twilio.twiml.MessagingResponse().toString());
//     }
//   }
// );
router.post(
  '/shared/:shareId/whatsapp/incoming',
  validateSharedAccess,
  express.urlencoded({ extended: true }),
  async (req, res) => {
    const { shareId } = req.params;
    const from = req.body.From;
    const body = req.body.Body || '';
    
    try {
      const share = await firestore.getShareLink(shareId);
      if (!share) {
        throw new Error('Share not found');
      }

      const assistant = await firestore.getAssistant(share.assistantId);
      if (!assistant) {
        throw new Error('Assistant not found');
      }

      const phoneNumber = from.replace('whatsapp:', '');
      const sessionId = `whatsapp_${phoneNumber.replace(/[^0-9]/g, '')}_${shareId}`;

      let patientId = null;
      const mappingSnapshot = await firestore.db.collection('patient_phone_mappings')
        .where('phoneNumber', '==', phoneNumber)
        .limit(1)
        .get();

      if (!mappingSnapshot.empty) {
        patientId = mappingSnapshot.docs[0].data().patientId;
        console.log('Found patient mapping:', { patientId });

      }

      console.log('WhatsApp message received (shared link):', {
        from,
        body,
        shareId,
        sessionId,
        patientId
      });

      await firestore.saveSharedChatMessage({
        shareId,
        sessionId,
        assistantId: share.assistantId,
        role: 'user',
        content: body.trim(),
        createdAt: new Date(),
        patientId
      });

      const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${shareId}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          message: body.trim(),
          sessionId: sessionId,
          language: 'en',
          patientId
        })
      });

      const data = await apiResponse.json();
      if (!apiResponse.ok) {
        throw new Error(`API Error: ${data.error}`);
      }

      await firestore.saveSharedChatMessage({
        shareId,
        sessionId,
        assistantId: share.assistantId,
        role: 'assistant',
        content: data.content,
        createdAt: new Date(),
        contextUsed: [],
        patientId
      });

      const twilioService = new TwilioService();
      await twilioService.sendWhatsAppMessage(from, data.content, shareId, sessionId, share.assistantId);

      const twiml = new twilio.twiml.MessagingResponse();
      res.type('text/xml');
      res.send(twiml.toString());
    } catch (error) {
      console.error('Error handling WhatsApp message (shared link):', error);
      res.type('text/xml');
      res.send(new twilio.twiml.MessagingResponse().toString());
    }
  }
);

export default router;