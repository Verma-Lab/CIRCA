import express from 'express';
import { verifyToken } from '../middleware/auth.js';
import { google } from 'googleapis';
import { Firestore } from '@google-cloud/firestore';
import crypto from 'crypto';

const router = express.Router();
// const firestore = new Firestore();
const firestore = new Firestore({
  projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
  keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  databaseId: 'circa'  // Explicitly specify the database name
});

// Store for temporary state parameters
const stateStore = new Map();

// Gmail OAuth configuration
const oauth2Client = new google.auth.OAuth2(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
  `${process.env.API_URL}/api/gmail/auth/callback`
);

// Get Gmail integration status
router.get('/status', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const userDoc = await firestore.collection('users').doc(userId).get();
    const userData = userDoc.data();

    const status = {
      gmail: Boolean(userData?.gmailToken)
    };

    res.json(status);
  } catch (error) {
    console.error('Error getting Gmail status:', error);
    res.status(500).json({ error: 'Failed to get Gmail status' });
  }
});

// Connect Gmail
router.get('/auth', verifyToken, (req, res) => {
  try {
    const state = crypto.randomBytes(16).toString('hex');
    
    stateStore.set(state, {
      userId: req.user.id,
      timestamp: Date.now()
    });

    // Clean up old state entries
    for (const [key, value] of stateStore.entries()) {
      if (Date.now() - value.timestamp > 5 * 60 * 1000) {
        stateStore.delete(key);
      }
    }

    const authUrl = oauth2Client.generateAuthUrl({
      access_type: 'offline',
      scope: [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify'
      ],
      state: state,
      prompt: 'consent'
    });
    res.json({ url: authUrl });
  } catch (error) {
    console.error('Error generating auth URL:', error);
    res.status(500).json({ error: 'Failed to generate authorization URL' });
  }
});

// Gmail OAuth callback
router.get('/auth/callback', async (req, res) => {
  try {
    const { code, state } = req.query;

    if (!state || !stateStore.has(state)) {
      throw new Error('Invalid state parameter');
    }

    const { userId } = stateStore.get(state);
    stateStore.delete(state);

    const { tokens } = await oauth2Client.getToken(code);
    
    await firestore.collection('users').doc(userId).update({
      gmailToken: tokens,
      gmailConnected: true,
      lastUpdated: new Date().toISOString()
    });

    res.redirect(`${process.env.FRONTEND_URL}/dashboard?gmail=connected`);
  } catch (error) {
    console.error('Gmail auth error:', error);
    res.redirect(`${process.env.FRONTEND_URL}/dashboard?gmail=error&message=${encodeURIComponent(error.message)}`);
  }
});

// List emails
router.get('/messages', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const userDoc = await firestore.collection('users').doc(userId).get();
    const userData = userDoc.data();

    if (!userData?.gmailToken) {
      return res.status(401).json({ error: 'Gmail not connected' });
    }

    oauth2Client.setCredentials(userData.gmailToken);
    const gmail = google.gmail({ version: 'v1', auth: oauth2Client });

    const response = await gmail.users.messages.list({
      userId: 'me',
      maxResults: 10
    });

    // Fetch full message details for each message
    const messages = await Promise.all(
      response.data.messages.map(async (message) => {
        const fullMessage = await gmail.users.messages.get({
          userId: 'me',
          id: message.id
        });
        return fullMessage.data;
      })
    );

    res.json(messages);
  } catch (error) {
    console.error('Error fetching emails:', error);
    res.status(500).json({ error: 'Failed to fetch emails' });
  }
});

// Send email
router.post('/send', verifyToken, async (req, res) => {
    try {
      const { to, subject, message } = req.body;
      
      if (!to || !subject || !message) {
        return res.status(400).json({ 
          error: 'Missing required fields',
          details: 'To, subject, and message are required'
        });
      }
  
      const userId = req.user.id;
      const userDoc = await firestore.collection('users').doc(userId).get();
      const userData = userDoc.data();
  
      if (!userData?.gmailToken) {
        return res.status(401).json({ 
          error: 'Gmail not connected',
          details: 'Please connect your Gmail account in settings'
        });
      }
  
      // Check if token is expired and refresh if needed
      if (userData.gmailToken.expiry_date < Date.now()) {
        oauth2Client.setCredentials(userData.gmailToken);
        const { tokens } = await oauth2Client.refreshToken(userData.gmailToken.refresh_token);
        
        // Update token in database
        await firestore.collection('users').doc(userId).update({
          gmailToken: tokens,
          lastUpdated: new Date().toISOString()
        });
        
        oauth2Client.setCredentials(tokens);
      } else {
        oauth2Client.setCredentials(userData.gmailToken);
      }
  
      const gmail = google.gmail({ version: 'v1', auth: oauth2Client });
  
      // Create email in RFC 822 format
      const utf8Subject = `=?utf-8?B?${Buffer.from(subject).toString('base64')}?=`;
      const messageParts = [
        'Content-Type: text/html; charset=utf-8',
        'MIME-Version: 1.0',
        `To: ${to}`,
        `Subject: ${utf8Subject}`,
        '',
        message
      ];
      
      const encodedMessage = Buffer.from(messageParts.join('\n'))
        .toString('base64')
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');
  
      // Send the email
      const response = await gmail.users.messages.send({
        userId: 'me',
        requestBody: {
          raw: encodedMessage
        }
      });
  
      // Log success and return response
      console.log('Email sent successfully:', response.data);
      res.json({
        success: true,
        messageId: response.data.id
      });
  
    } catch (error) {
      console.error('Error sending email:', error);
      
      // Handle different types of errors
      if (error.code === 401) {
        res.status(401).json({
          error: 'Authentication failed',
          details: 'Please reconnect your Gmail account'
        });
      } else if (error.code === 403) {
        res.status(403).json({
          error: 'Permission denied',
          details: 'Email sending permission not granted'
        });
      } else {
        res.status(500).json({
          error: 'Failed to send email',
          details: error.message
        });
      }
    }
  });

export default router;