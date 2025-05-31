// backend/src/routes/metrics.js
import express from 'express';
import { verifyToken } from '../middleware/auth.js';
import { google } from 'googleapis';
import { Firestore } from '@google-cloud/firestore';

const router = express.Router();
// const firestore = new Firestore();
const firestore = new Firestore({
  projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
  keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  databaseId: 'circa'  // Explicitly specify the database name
});

// Helper function to initialize Google Sheets client
async function initializeSheetsClient(userId) {
  const userDoc = await firestore.collection('users').doc(userId).get();
  const userData = userDoc.data();

  if (!userData?.googleSheetsToken) {
    throw new Error('Google Sheets not connected');
  }

  const oauth2Client = new google.auth.OAuth2(
    process.env.GOOGLE_CLIENT_ID,
    process.env.GOOGLE_CLIENT_SECRET,
    `${process.env.API_URL}/api/docs-sheets/auth/callback`
  );

  oauth2Client.setCredentials(userData.googleSheetsToken);
  return google.sheets({ version: 'v4', auth: oauth2Client });
}

// Get all sheet IDs for an assistant
async function getAssistantSheets(userId, assistantId, sheetType) {
  const sheets = await initializeSheetsClient(userId);
  const drive = google.drive({ version: 'v3', auth: sheets.context._options.auth });

  // Query pattern based on how SmartTagger names the sheets
  const query = `name contains '${assistantId}_' and name contains '_${sheetType}' and mimeType='application/vnd.google-apps.spreadsheet'`;

  const response = await drive.files.list({
    q: query,
    fields: 'files(id, name)',
    spaces: 'drive',
    pageSize: 1000
  });

  return response.data.files;
}

// Get sheet content
async function getSheetContent(sheets, sheetId) {
  try {
    const response = await sheets.spreadsheets.values.get({
      spreadsheetId: sheetId,
      range: 'Sheet1!A:Z'
    });

    if (!response.data.values || response.data.values.length < 2) {
      return [];
    }

    const headers = response.data.values[0];
    return response.data.values.slice(1).map(row => {
      const obj = {};
      headers.forEach((header, index) => {
        obj[header] = row[index] || null;
      });
      return obj;
    });
  } catch (error) {
    console.error(`Error reading sheet ${sheetId}:`, error);
    return [];
  }
}

// Get metrics for an assistant
router.get('/assistants/:assistantId/metrics/:type', verifyToken, async (req, res) => {
    console.log('API HIT')
  try {
    const { assistantId, type } = req.params;
    const userId = req.user.id;
    
    if (!['fields', 'context', 'kpis'].includes(type)) {
      return res.status(400).json({ error: 'Invalid metric type' });
    }

    const sheets = await initializeSheetsClient(userId);
    const sheetFiles = await getAssistantSheets(userId, assistantId, type);

    // Process all sheets in parallel
    const allData = await Promise.all(
      sheetFiles.map(file => getSheetContent(sheets, file.id))
    );

    // Merge all data
    const mergedData = allData.flat().map(item => {
      // Convert timestamp strings to ISO format if they exist
      if (item.Timestamp) {
        item.timestamp = new Date(item.Timestamp).toISOString();
      }
      return item;
    });

    // Sort by timestamp if available
    const sortedData = mergedData.sort((a, b) => {
      const timeA = a.timestamp || a.Timestamp || '';
      const timeB = b.timestamp || b.Timestamp || '';
      return timeB.localeCompare(timeA);
    });

    res.json(sortedData);
  } catch (error) {
    console.error('Error fetching metrics:', error);
    res.status(500).json({ error: 'Failed to fetch metrics' });
  }
});

export default router;