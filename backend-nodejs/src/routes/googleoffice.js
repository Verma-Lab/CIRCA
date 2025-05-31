// backend/src/routes/docsAndSheets.js
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

// OAuth configuration
const oauth2Client = new google.auth.OAuth2(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
  `${process.env.API_URL}/api/docs-sheets/auth/callback`
);

export const getGoogleFileName = async (fileId, userId, type) => {
  const userDoc = await firestore.collection('users').doc(userId).get();
  const userData = userDoc.data();

  if (!userData?.googleDocsToken) {
    throw new Error('Google Docs not connected');
  }

  oauth2Client.setCredentials(userData.googleDocsToken);

  if (type === 'docs') {
    const docs = google.docs({ version: 'v1', auth: oauth2Client });
    const response = await docs.documents.get({ documentId: fileId });
    return response.data.title;
  } else if (type === 'sheets') {
    const sheets = google.sheets({ version: 'v4', auth: oauth2Client });
    const response = await sheets.spreadsheets.get({
      spreadsheetId: fileId,
      fields: 'properties.title'
    });
    return response.data.properties.title;
  }

  return null;
};
export const getGoogleDocContent = async (docId, userId) => {
  const userDoc = await firestore.collection('users').doc(userId).get();
  const userData = userDoc.data();

  if (!userData?.googleDocsToken) {
    throw new Error('Google Docs not connected');
  }

  oauth2Client.setCredentials(userData.googleDocsToken);
  const docs = google.docs({ version: 'v1', auth: oauth2Client });

  const doc = await docs.documents.get({ documentId: docId });
  return doc.data.body.content
    .map(item => item.paragraph?.elements?.map(elem => elem.textRun?.content).join('') || '')
    .join('\n');
};

export const getGoogleSheetContent = async (sheetId, userId) => {
  const userDoc = await firestore.collection('users').doc(userId).get();
  const userData = userDoc.data();

  if (!userData?.googleSheetsToken) {
    throw new Error('Google Sheets not connected');
  }

  oauth2Client.setCredentials(userData.googleSheetsToken);
  const sheets = google.sheets({ version: 'v4', auth: oauth2Client });

  const sheet = await sheets.spreadsheets.values.get({
    spreadsheetId: sheetId,
    range: 'A1:Z1000', // Adjust the range as needed
  });

  return sheet.data.values
    .map(row => row.join(', '))
    .join('\n');
};
// Get integration status
router.get('/status', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const userDoc = await firestore.collection('users').doc(userId).get();
    const userData = userDoc.data();

    const status = {
      docs: Boolean(userData?.googleDocsToken),
      sheets: Boolean(userData?.googleSheetsToken)
    };

    res.json(status);
  } catch (error) {
    console.error('Error getting Docs/Sheets status:', error);
    res.status(500).json({ error: 'Failed to get status' });
  }
});

// Connect Google Docs & Sheets
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
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',  // Full access to read and write
        
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

// OAuth callback
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
      googleDocsToken: tokens,
      googleSheetsToken: tokens,
      docsAndSheetsConnected: true,
      lastUpdated: new Date().toISOString()
    });

    res.redirect(`${process.env.FRONTEND_URL}/dashboard?docsSheets=connected`);
  } catch (error) {
    console.error('Docs/Sheets auth error:', error);
    res.redirect(`${process.env.FRONTEND_URL}/dashboard?docsSheets=error&message=${encodeURIComponent(error.message)}`);
  }
});

// List Google Docs
router.get('/docs/list', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const userDoc = await firestore.collection('users').doc(userId).get();
    const userData = userDoc.data();

    if (!userData?.googleDocsToken) {
      return res.status(401).json({ error: 'Google Docs not connected' });
    }

    oauth2Client.setCredentials(userData.googleDocsToken);
    const drive = google.drive({ version: 'v3', auth: oauth2Client });

    const response = await drive.files.list({
      q: "mimeType='application/vnd.google-apps.document'",
      fields: 'files(id, name, createdTime, modifiedTime)',
      orderBy: 'modifiedTime desc'
    });
    console.log(response.data.files)
    res.json(response.data.files);
  } catch (error) {
    console.error('Error listing docs:', error);
    res.status(500).json({ error: 'Failed to list documents' });
  }
});

// Create new Google Doc
// POST /api/integrations/docs/create
router.post('/docs/create', verifyToken, async (req, res) => {
  try {
    const { title, content } = req.body;
    const userId = req.user.id;
    const userDoc = await firestore.db.collection('users').doc(userId).get();
    const userData = userDoc.data();

    if (!userData?.googleDocsToken) {
      return res.status(401).json({ error: 'Google Docs not connected' });
    }

    integrationHandlers.oauth2Client.setCredentials(userData.googleDocsToken);
    const docs = google.docs({ version: 'v1', auth: integrationHandlers.oauth2Client });
    const drive = google.drive({ version: 'v3', auth: integrationHandlers.oauth2Client });

    const fileMetadata = {
      name: title,
      mimeType: 'application/vnd.google-apps.document',
    };
    
    const file = await drive.files.create({
      requestBody: fileMetadata,
      fields: 'id'
    });

    if (content) {
      await docs.documents.batchUpdate({
        documentId: file.data.id,
        requestBody: {
          requests: [{
            insertText: {
              location: { index: 1 },
              text: content
            }
          }]
        }
      });
    }

    res.json(file.data);
  } catch (error) {
    console.error('Error creating document:', error);
    res.status(500).json({ error: 'Failed to create document' });
  }
});
// PUT /api/integrations/docs/:docId
router.put('/docs/:docId', verifyToken, async (req, res) => {
  try {
    const { docId } = req.params;
    const { content } = req.body;
    const userId = req.user.id;
    const userDoc = await firestore.db.collection('users').doc(userId).get();
    const userData = userDoc.data();

    if (!userData?.googleDocsToken) {
      return res.status(401).json({ error: 'Google Docs not connected' });
    }

    integrationHandlers.oauth2Client.setCredentials(userData.googleDocsToken);
    const docs = google.docs({ version: 'v1', auth: integrationHandlers.oauth2Client });

    await docs.documents.batchUpdate({
      documentId: docId,
      requestBody: {
        requests: [{
          insertText: {
            location: { index: 1 },
            text: content
          }
        }]
      }
    });

    res.json({ updated: true });
  } catch (error) {
    console.error('Error updating document:', error);
    res.status(500).json({ error: 'Failed to update document' });
  }
});


// List Google Sheets
router.get('/sheets/list', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const userDoc = await firestore.collection('users').doc(userId).get();
    const userData = userDoc.data();

    if (!userData?.googleSheetsToken) {
      return res.status(401).json({ error: 'Google Sheets not connected' });
    }

    oauth2Client.setCredentials(userData.googleSheetsToken);
    const drive = google.drive({ version: 'v3', auth: oauth2Client });

    const response = await drive.files.list({
      q: "mimeType='application/vnd.google-apps.spreadsheet'",
      fields: 'files(id, name, createdTime, modifiedTime)',
      orderBy: 'modifiedTime desc',
      spaces: 'drive',
      pageSize: 100,  // Increase page size to get more results
      includeItemsFromAllDrives: true,
      supportsAllDrives: true
    });
    console.log(response.data.files)
    res.json(response.data.files);
  } catch (error) {
    console.error('Error listing sheets:', error);
    res.status(500).json({ error: 'Failed to list spreadsheets' });
  }
});
// List Google Docs
router.get('/docs/list', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const userDoc = await firestore.collection('users').doc(userId).get();
    const userData = userDoc.data();

    // Ensure user has a valid Google Docs token
    if (!userData?.googleDocsToken) {
      return res.status(401).json({ error: 'Google Docs not connected' });
    }

    // Set OAuth credentials
    oauth2Client.setCredentials(userData.googleDocsToken);
    const drive = google.drive({ version: 'v3', auth: oauth2Client });

    // Fetch Google Docs
    const response = await drive.files.list({
      q: "mimeType='application/vnd.google-apps.document'",
      fields: 'files(id, name, createdTime, modifiedTime)',
      orderBy: 'modifiedTime desc',
      spaces: 'drive',
      pageSize: 100,
      includeItemsFromAllDrives: true,
      supportsAllDrives: true
    });

    console.log(response.data.files);
    res.json(response.data.files);
  } catch (error) {
    console.error('Error listing docs:', error);
    res.status(500).json({ error: 'Failed to list documents' });
  }
});


// Create new Google Sheet
router.post('/sheets/create', verifyToken, async (req, res) => {
  try {
    const { title, data } = req.body;
    const userId = req.user.id;
    const userDoc = await firestore.collection('users').doc(userId).get();
    const userData = userDoc.data();

    if (!userData?.googleSheetsToken) {
      return res.status(401).json({ error: 'Google Sheets not connected' });
    }

    oauth2Client.setCredentials(userData.googleSheetsToken);
    const sheets = google.sheets({ version: 'v4', auth: oauth2Client });
    const drive = google.drive({ version: 'v3', auth: oauth2Client });

    const fileMetadata = {
      name: title,
      mimeType: 'application/vnd.google-apps.spreadsheet',
    };
    
    const file = await drive.files.create({
      requestBody: fileMetadata,
      fields: 'id'
    });

    if (data) {
      await sheets.spreadsheets.values.update({
        spreadsheetId: file.data.id,
        range: 'A1',
        valueInputOption: 'RAW',
        requestBody: {
          values: data
        }
      });
    }

    res.json(file.data);
  } catch (error) {
    console.error('Error creating spreadsheet:', error);
    res.status(500).json({ error: 'Failed to create spreadsheet' });
  }
});

export default router;