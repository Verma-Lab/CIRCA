

// export default TwilioService;
import twilio from 'twilio';
import streamTextToSpeech from '../utils/tts.js'; // Import your TTS service
import firestore from '../services/db/firestore.js';
import EnhancedFlowProcessor from '../services/ai/EnhancedFlowProcessor.js';
import geminiService from '../services/ai/gemini.js';
import vectors from '../services/storage/vectors.js';

const { twiml: { VoiceResponse } } = twilio;

export class TwilioService {
  constructor() {
    this.client = twilio(
      process.env.TWILIO_ACCOUNT_SID, 
      process.env.TWILIO_AUTH_TOKEN
    );
  }


// async handleIncomingCall(shareId) {
//   const response = new VoiceResponse();
//   const sessionId = `call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

//   const share = await firestore.getShareLink(shareId);
//   const voiceName = share.voiceName || 'en-US-Wavenet-D';
//   const assistant = await firestore.getAssistant(share.assistantId);

//   const flowProcessor = new EnhancedFlowProcessor(geminiService, firestore, vectors, share.userId || share.ownerId);

//   const defaultTriggerMessage = "Hi";
//   const result = await flowProcessor.processMessage(defaultTriggerMessage, sessionId, assistant, { previousMessages: [] });
//   const greetingText = result.content || "Hello, how can I help you today?";

//   // Add this: Save the initial interaction to Firestore
//   await firestore.runTransaction(async (transaction) => {
//     await firestore.saveSharedChatMessage({
//       shareId,
//       sessionId,
//       assistantId: assistant.id,
//       role: 'user',
//       content: defaultTriggerMessage,
//       createdAt: new Date()
//     });
//     await firestore.saveSharedChatMessage({
//       shareId,
//       sessionId,
//       assistantId: assistant.id,
//       role: 'assistant',
//       content: greetingText,
//       createdAt: new Date(),
//       contextUsed: []
//     });
//   });

//   const ttsAudioUrl = `${process.env.API_URL}/api/shared/${shareId}/chat/audio?text=${encodeURIComponent(greetingText)}&language=en&voiceName=${voiceName}`;
//   response.play(ttsAudioUrl);
//   response.gather({
//     input: 'speech',
//     action: `/api/shared/${shareId}/voice/transcription?sessionId=${sessionId}`,
//     speechTimeout: 'auto',
//     language: 'en-GB'
//   });

//   return response.toString();
// }

// async handleTranscription(shareId, sessionId, transcription) {
//   try {
//     if (!transcription?.trim()) {
//       console.warn('Empty transcription received:', { shareId, sessionId, transcription });
//       return 'I couldn\'t hear what you said. Could you please repeat that?';
//     }

//     console.log('Processing transcription:', {
//       shareId,
//       sessionId,
//       transcription,
//       url: `${process.env.API_URL}/api/shared/${shareId}/chat`
//     });

//     const response = await fetch(`${process.env.API_URL}/api/shared/${shareId}/chat`, {
//       method: 'POST',
//       headers: {
//         'Content-Type': 'application/json',
//         'Accept': 'application/json'
//       },
//       body: JSON.stringify({
//         message: transcription.trim(),
//         sessionId: sessionId,
//         language: 'en'
//       })
//     });

//     const data = await response.json();
//     console.log('Chat API Response:', data);

//     if (!response.ok) {
//       throw new Error(`API Error: ${data.error}`);
//     }

//     const share = await firestore.getShareLink(shareId);
//     const assistant = await firestore.getAssistant(share.assistantId);
    
//     // Add this: Save the user response and assistant reply to Firestore
//     await firestore.runTransaction(async (transaction) => {
//       await firestore.saveSharedChatMessage({
//         shareId,
//         sessionId,
//         assistantId: assistant.id,
//         role: 'user',
//         content: transcription.trim(),
//         createdAt: new Date()
//       });
//       await firestore.saveSharedChatMessage({
//         shareId,
//         sessionId,
//         assistantId: assistant.id,
//         role: 'assistant',
//         content: data.content,
//         createdAt: new Date(),
//         contextUsed: []
//       });
//     });

//     const voiceName = share.voiceName || 'en-US-Wavenet-D';
//     console.log('VOICE NAME, TRanscription Call', voiceName);
//     // Generate TTS audio URL for the response
//     const ttsAudioUrl = `${process.env.API_URL}/api/shared/${shareId}/chat/audio?text=${encodeURIComponent(data.content)}&language=en&voiceName=${voiceName}`;
  
//     return ttsAudioUrl; // Return the TTS audio URL instead of plain text
//   } catch (error) {
//     console.error('Transcription handling error:', error);
//     return 'Sorry, I encountered an error processing your request. Please try again.';
//   }
// }

// Modified handleIncomingCall method for TwilioService class
// This creates an active_calls record when a new call comes in
async handleIncomingCall(shareId, phoneNumber = null, options = {}) {
  const { patientId } = options;
  const response = new VoiceResponse();
  const sessionId = `call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  const share = await firestore.getShareLink(shareId);
  const voiceName = share.voiceName || 'en-US-Wavenet-D';
  const assistant = await firestore.getAssistant(share.assistantId);

  // Create a new active call record in Firestore
  const callDocRef = await firestore.db.collection('active_calls').add({
    shareId,
    sessionId,
    assistantId: assistant.id,
    userId: share.userId || share.ownerId,
    phoneNumber: phoneNumber || 'Unknown',
    patientId,
    startTime: new Date(),
    status: 'ai-handling',
    voiceName,
    assistantName: assistant.name || 'AI Assistant',
    assistantType: assistant.category || 'General',
    transcriptionEnabled: true,
    lastActivity: new Date()
  });

  console.log('Created new active call record:', callDocRef.id);

  // Default trigger message for initial greeting
  const defaultTriggerMessage = "Hi";
  
  // Process the message through the shared chat API
  const apiResponse = await fetch(`${process.env.API_URL}/api/shared/${shareId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({
      message: defaultTriggerMessage,
      sessionId: sessionId,
      language: 'en',
      patientId
    })
  });
  
  const data = await apiResponse.json();
  
  if (!apiResponse.ok) {
    throw new Error(`API Error: ${data.error}`);
  }
  
  const greetingText = data.content || "Hello, how can I help you today?";

  const ttsAudioUrl = `${process.env.API_URL}/api/shared/${shareId}/chat/audio?text=${encodeURIComponent(greetingText)}&language=en&voiceName=${voiceName}`;
  response.play(ttsAudioUrl);
  response.gather({
    input: 'speech',
    action: `/api/shared/${shareId}/voice/transcription?sessionId=${sessionId}&callId=${callDocRef.id}`,
    speechTimeout: 'auto',
    language: 'en-GB'
  });

  return response.toString();
}
// async handleIncomingCall(shareId, phoneNumber = null, options = {}) {
//   const { patientId } = options;
//   const response = new VoiceResponse();
//   const sessionId = `call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

//   const share = await firestore.getShareLink(shareId);
//   const voiceName = share.voiceName || 'en-US-Wavenet-D';
//   const assistant = await firestore.getAssistant(share.assistantId);

//   const flowProcessor = new EnhancedFlowProcessor(geminiService, firestore, vectors, share.userId || share.ownerId);

//   const defaultTriggerMessage = "Hi";
//   const result = await flowProcessor.processMessage(defaultTriggerMessage, sessionId, assistant, { previousMessages: [] });
//   const greetingText = result.content || "Hello, how can I help you today?";

//   // Add this: Save the initial interaction to Firestore
//   await firestore.runTransaction(async (transaction) => {
//     await firestore.saveSharedChatMessage({
//       shareId,
//       sessionId,
//       assistantId: assistant.id,
//       role: 'user',
//       content: defaultTriggerMessage,
//       createdAt: new Date(), 
//       patientId
//     });
//     await firestore.saveSharedChatMessage({
//       shareId,
//       sessionId,
//       assistantId: assistant.id,
//       role: 'assistant',
//       content: greetingText,
//       createdAt: new Date(),
//       contextUsed: [], 
//       patientId
//     });
//   });

//   // Create a new active call record in Firestore
//   const callDocRef = await firestore.db.collection('active_calls').add({
//     shareId,
//     sessionId,
//     assistantId: assistant.id,
//     userId: share.userId || share.ownerId,
//     phoneNumber: phoneNumber || 'Unknown',
//     patientId, // Store patientId
//     startTime: new Date(),
//     status: 'ai-handling',
//     voiceName,
//     assistantName: assistant.name || 'AI Assistant',
//     assistantType: assistant.category || 'General',
//     transcriptionEnabled: true,
//     lastActivity: new Date()
//   });

//   console.log('Created new active call record:', callDocRef.id);

//   const ttsAudioUrl = `${process.env.API_URL}/api/shared/${shareId}/chat/audio?text=${encodeURIComponent(greetingText)}&language=en&voiceName=${voiceName}`;
//   response.play(ttsAudioUrl);
//   response.gather({
//     input: 'speech',
//     action: `/api/shared/${shareId}/voice/transcription?sessionId=${sessionId}&callId=${callDocRef.id}`,
//     speechTimeout: 'auto',
//     language: 'en-GB'
//   });

//   return response.toString();
// }

// Also modify handleTranscription to update the call record with new voice inputs
async handleTranscription(shareId, sessionId, transcription, callId = null) {
  try {
    if (!transcription?.trim()) {
      console.warn('Empty transcription received:', { shareId, sessionId, transcription });
      return 'I couldn\'t hear what you said. Could you please repeat that?';
    }

    console.log('Processing transcription:', {
      shareId,
      sessionId,
      transcription,
      callId,
      url: `${process.env.API_URL}/api/shared/${shareId}/chat`
    });

    // Get patientId from active_calls if available
    let patientId = null;
    if (callId) {
      const callDoc = await firestore.db.collection('active_calls').doc(callId).get();
      if (callDoc.exists) {
        patientId = callDoc.data().patientId || null;
        await callDoc.ref.update({ lastActivity: new Date() });
      }
    }

    const response = await fetch(`${process.env.API_URL}/api/shared/${shareId}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        message: transcription.trim(),
        sessionId: sessionId,
        language: 'en',
        patientId
      })
    });

    const data = await response.json();
    console.log('Chat API Response:', data);

    if (!response.ok) {
      throw new Error(`API Error: ${data.error}`);
    }

    const share = await firestore.getShareLink(shareId);
    const voiceName = share.voiceName || 'en-US-Wavenet-D';
    
    // Generate TTS audio URL for the response
    const ttsAudioUrl = `${process.env.API_URL}/api/shared/${shareId}/chat/audio?text=${encodeURIComponent(data.content)}&language=en&voiceName=${voiceName}`;
  
    return ttsAudioUrl;
  } catch (error) {
    console.error('Transcription handling error:', error);
    return 'Sorry, I encountered an error processing your request. Please try again.';
  }
}
// async handleTranscription(shareId, sessionId, transcription, callId = null) {
//   try {
//     if (!transcription?.trim()) {
//       console.warn('Empty transcription received:', { shareId, sessionId, transcription });
//       return 'I couldn\'t hear what you said. Could you please repeat that?';
//     }

//     console.log('Processing transcription:', {
//       shareId,
//       sessionId,
//       transcription,
//       callId,
//       url: `${process.env.API_URL}/api/shared/${shareId}/chat`
//     });

//     let patientId = null;
//       if (callId) {
//         const callDoc = await firestore.db.collection('active_calls').doc(callId).get();
//         if (callDoc.exists) {
//           patientId = callDoc.data().patientId || null;
//           await callDoc.ref.update({ lastActivity: new Date() });
//         }
//       }
//     // If we have a callId, update the call's lastActivity timestamp
//     // if (callId) {
//     //   await firestore.db.collection('active_calls').doc(callId).update({
//     //     lastActivity: new Date()
//     //   });
//     // }

//     const response = await fetch(`${process.env.API_URL}/api/shared/${shareId}/chat`, {
//       method: 'POST',
//       headers: {
//         'Content-Type': 'application/json',
//         'Accept': 'application/json'
//       },
//       body: JSON.stringify({
//         message: transcription.trim(),
//         sessionId: sessionId,
//         language: 'en', 
//         patientId
//       })
//     });

//     const data = await response.json();
//     console.log('Chat API Response:', data);

//     if (!response.ok) {
//       throw new Error(`API Error: ${data.error}`);
//     }

//     const share = await firestore.getShareLink(shareId);
//     const assistant = await firestore.getAssistant(share.assistantId);
    
//     // Add this: Save the user response and assistant reply to Firestore
//     await firestore.runTransaction(async (transaction) => {
//       await firestore.saveSharedChatMessage({
//         shareId,
//         sessionId,
//         assistantId: assistant.id,
//         role: 'user',
//         content: transcription.trim(),
//         createdAt: new Date(),
//         patientId
//       });
//       await firestore.saveSharedChatMessage({
//         shareId,
//         sessionId,
//         assistantId: assistant.id,
//         role: 'assistant',
//         content: data.content,
//         createdAt: new Date(),
//         contextUsed: [],
//         patientId
//       });
//     });

//     const voiceName = share.voiceName || 'en-US-Wavenet-D';
//     console.log('VOICE NAME, TRanscription Call', voiceName);
//     // Generate TTS audio URL for the response
//     const ttsAudioUrl = `${process.env.API_URL}/api/shared/${shareId}/chat/audio?text=${encodeURIComponent(data.content)}&language=en&voiceName=${voiceName}`;
  
//     return ttsAudioUrl; // Return the TTS audio URL instead of plain text
//   } catch (error) {
//     console.error('Transcription handling error:', error);
//     return 'Sorry, I encountered an error processing your request. Please try again.';
//   }
// }

async makeOutboundCall(phoneNumber, shareId) {
    try {
      // Verify we have a Twilio phone number configured
      if (!process.env.TWILIO_PHONE_NUMBER) {
        throw new Error('TWILIO_PHONE_NUMBER environment variable is not configured');
      }
  
      // Get the share to check if it has a custom phone number
      const share = await firestore.getShareLink(shareId);
      const fromNumber = share?.phoneNumber || process.env.TWILIO_PHONE_NUMBER;
  
      // Create the call with the from number explicitly set
      const call = await this.client.calls.create({
        url: `${process.env.API_URL}/api/shared/${shareId}/voice/incoming`,
        to: phoneNumber,
        from: fromNumber,
        statusCallback: `${process.env.API_URL}/api/shared/${shareId}/voice/status`, // Optional: for tracking call status
        statusCallbackEvent: ['initiated', 'ringing', 'answered', 'completed'], // Optional: events to track
      });
  
      console.log('Outbound call initiated:', {
        callSid: call.sid,
        to: phoneNumber,
        from: fromNumber,
        shareId: shareId
      });
  
      return call.sid;
    } catch (error) {
      console.error('Error making outbound call:', error);
      throw error;
    }
  }

// Add this method to your TwilioService class
async sendWhatsAppMessage(to, message, shareId, sessionId, assistantId, patientId = null, skipSave = false) {
  
  try {
    // Use TWILIO_WHATSAPP_NUMBER if available, otherwise fall back to TWILIO_PHONE_NUMBER
    const whatsappNumber = '+14155238886'
    
    if (!whatsappNumber) {
      throw new Error('Neither TWILIO_WHATSAPP_NUMBER nor TWILIO_PHONE_NUMBER is configured');
    }
    
    // Ensure phone numbers are in proper WhatsApp format
    const fromNumber = whatsappNumber.startsWith('whatsapp:') 
      ? whatsappNumber 
      : `whatsapp:${whatsappNumber}`;
      
    const toNumber = to.startsWith('whatsapp:') ? to : `whatsapp:${to}`;
    
    // Send message via Twilio
    const result = await this.client.messages.create({
      body: message,
      from: fromNumber,
      to: toNumber
    });
    
    // Save the WhatsApp message to Firestore if shareId, sessionId, and assistantId are provided
    if (!skipSave && shareId && sessionId && assistantId) {
      await firestore.saveSharedChatMessage({
        shareId,
        sessionId,
        assistantId,
        role: 'assistant',
        content: message,
        createdAt: new Date(),
        contextUsed: [], 
        patientId // Add this
      });
    }
    
    console.log('WhatsApp message sent:', {
      messageId: result.sid,
      to: toNumber,
      from: fromNumber
    });
    
    return result.sid;
  } catch (error) {
    console.error('Error sending WhatsApp message:', error);
    throw error;
  }
}
async sendSmsMessage(to, message, shareId, sessionId, assistantId, patientId = null, skipSave = false) {
  try {
    console.log('→ TwilioService.sendSmsMessage called:', {
      to,
      messageLength: message.length,
      shareId,
      sessionId,
      assistantId
    });
    
    // Use your regular SMS number - not WhatsApp
    const smsNumber = process.env.TWILIO_PHONE_NUMBER;
    
    if (!smsNumber) {
      throw new Error('TWILIO_PHONE_NUMBER environment variable is not configured');
    }
    
    // Don't add WhatsApp prefix for SMS numbers
    const toNumber = to.startsWith('whatsapp:') ? to.replace('whatsapp:', '') : to;
    
    console.log('→ Sending SMS via Twilio:', {
      from: smsNumber,
      to: toNumber,
      messagePreview: message.substring(0, 30) + (message.length > 30 ? '...' : '')
    });
    
    // Send message via Twilio
    const result = await this.client.messages.create({
      body: message,
      from: smsNumber,
      to: toNumber
    });
    
    // Save the message to Firestore
    if (!skipSave && shareId && sessionId && assistantId) {
      await firestore.saveSharedChatMessage({
        shareId,
        sessionId,
        assistantId,
        role: 'assistant',
        content: message,
        createdAt: new Date(),
        contextUsed: [],
        patientId
      });
    }
    
    console.log('SMS message sent:', {
      messageId: result.sid,
      to: toNumber,
      from: smsNumber
    });
    
    return result.sid;
  } catch (error) {
    console.error('→ ERROR sending SMS message:', error);
    console.error('→ Error stack:', error.stack);
    throw error;
  }
}
async sendAudioToCall(callSid, audioUrl) {
  try {
    // Create a TwiML response to play the audio
    const response = new VoiceResponse();
    response.play(audioUrl);
    
    // Update the call with the new TwiML
    await this.client.calls(callSid).update({
      twiml: response.toString()
    });
    
    console.log('Audio sent to call:', {
      callSid,
      audioUrl
    });
    
    return true;
  } catch (error) {
    console.error('Error sending audio to call:', error);
    throw error;
  }
}

// Method to end a call
async endCall(callSid) {
  try {
    // Hang up the call
    await this.client.calls(callSid).update({
      status: 'completed'
    });
    
    console.log('Call ended:', callSid);
    return true;
  } catch (error) {
    console.error('Error ending call:', error);
    throw error;
  }
}

// Method to update call transcription settings
async updateCallTranscription(callSid, enabled) {
  try {
    // For now, we'll just log the change
    // In a real implementation, you might need to update the call's Gather settings
    console.log(`Transcription for call ${callSid} set to ${enabled ? 'enabled' : 'disabled'}`);
    
    // Return true to indicate success (even though we're not doing anything yet)
    return true;
  } catch (error) {
    console.error('Error updating call transcription:', error);
    throw error;
  }
}

// Method to send an operator message to a call
async sendOperatorMessage(callSid, message) {
  try {
    // Create a TwiML response to say the message
    const response = new VoiceResponse();
    response.say({
      voice: 'Polly.Joanna', // Using Amazon Polly voice, can be changed
      language: 'en-US'
    }, `Operator: ${message}`);
    
    // Update the call with the new TwiML
    await this.client.calls(callSid).update({
      twiml: response.toString()
    });
    
    console.log('Operator message sent to call:', {
      callSid,
      message
    });
    
    return true;
  } catch (error) {
    console.error('Error sending operator message:', error);
    throw error;
  }
}

}

export default TwilioService;