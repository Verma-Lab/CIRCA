// services/workflow/integrationHandlers.js
import { google } from 'googleapis';
import firestore from '../db/firestore.js';

class IntegrationHandlers {
  constructor() {
    this.oauth2Client = new google.auth.OAuth2(
      process.env.GOOGLE_CLIENT_ID,
      process.env.GOOGLE_CLIENT_SECRET,
      `${process.env.API_URL}/api/docs-sheets/auth/callback`
    );
  }

  async setupIntegrationAuth(userId) {
    const userDoc = await firestore.db.collection('users').doc(userId).get();
    const userData = userDoc.data();

    if (!userData?.googleSheetsToken) {
      throw new Error('Google integration not configured');
    }

    this.oauth2Client.setCredentials(userData.googleSheetsToken);
    return this.oauth2Client;
  }

  // Handle Google Sheets integration
  async handleGoogleSheets(userId, stepResult, config) {
    await this.setupIntegrationAuth(userId);
    const sheets = google.sheets({ version: 'v4', auth: this.oauth2Client });
    
    // If we want to read from a sheet and inject that into step input
    // we won't have stepResult yet, or we do it separately. 
    // But let's keep it here if you want to unify logic.
    // 
    // For final step updates: 
    // If we want to create a new sheet or update existing, do these.
    // console.log("RECEIVED CONFIG FROM FRONTEND", config.mode)
    if (config.mode === 'create_new') {
      // create new sheet
      const spreadsheet = await this.createSheet(sheets, {
        title: `Workflow Result - ${new Date().toISOString()}`,
        data: this.formatDataForSheets(stepResult)
      });
      return { sheetId: spreadsheet.spreadsheetId };
    }
    else if (config.mode === 'fetch_and_use') {
      // read from existing sheet and return the data
      const sheetData = await this.getSheetData(sheets, {
        spreadsheetId: config.sheetId,
        range: config.range || 'A:Z'
      });
    //   console.log('FETCH AND USE')
    //   console.log(sheetData)
      return { readData: sheetData };

    }
    else {
      // default to "update existing" or "select_existing"
      await this.updateSheet(sheets, {
        spreadsheetId: config.sheetId,
        range: config.range || 'A1',
        data: this.formatDataForSheets(stepResult)
      });
      return { updated: true };
    }
  }
  // READ data from a given sheet
  async getSheetData(sheets, { spreadsheetId, range }) {
    const response = await sheets.spreadsheets.values.get({
      spreadsheetId,
      range
    });
    
    const rows = response.data.values || [];
    
    // Transform 2D array into Firestore-compatible format
    if (rows.length > 0) {
      const headers = rows[0];
      const transformedData = rows.slice(1).map(row => {
        const rowObject = {};
        headers.forEach((header, index) => {
          // Replace spaces and special characters in header names
          const cleanHeader = header.replace(/[^a-zA-Z0-9]/g, '_');
          rowObject[cleanHeader] = row[index] || null;
        });
        return rowObject;
      });
      console.log('RETERIVED DATA')
      console.log(transformedData, headers)
      return {
        headers: headers,
        data: transformedData
      };
    }
    
    return {
      headers: [],
      data: []
    };
  }


  // CREATE new sheet
  async createSheet(sheets, { title, data }) {
    const response = await sheets.spreadsheets.create({
      requestBody: {
        properties: { title },
        sheets: [{
          data: [{
            startRow: 0,
            startColumn: 0,
            rowData: data.map(row => ({
              values: row.map(cell => ({
                userEnteredValue: { stringValue: String(cell) }
              }))
            }))
          }]
        }]
      }
    });
    return response.data;
  }

  // UPDATE existing sheet
  async updateSheet(sheets, { spreadsheetId, range, data }) {
    await sheets.spreadsheets.values.update({
      spreadsheetId,
      range,
      valueInputOption: 'RAW',
      requestBody: { values: data }
    });
  }

  formatDataForSheets(stepResult) {
    if (!stepResult) return [['No step result']];
  
    let content = '';
    
    // Get the raw content
    if (typeof stepResult === 'string') {
      content = stepResult;
    } else if (stepResult.raw) {
      content = stepResult.raw;
    } else {
      return [[JSON.stringify(stepResult)]];
    }
  
    // Clean up the content and split into lines
    const lines = content
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0);
  
    // Process pipe-delimited format
    if (lines.some(line => line.includes('|'))) {
      return lines
        .filter(line => line.includes('|')) // Keep only lines with pipes
        .map(line => 
          line
            .split('|')
            .map(cell => cell.trim())
            .filter(cell => cell.length > 0) // Remove empty cells from start/end
            .map(cell => 
              cell
                .replace(/^[-\s]+$/, '') // Remove separator lines
                .replace(/^\*\*|\*\*$/g, '') // Remove any bold markers
                .trim()
            )
        )
        .filter(row => 
          row.length > 0 && 
          !row.every(cell => cell === '' || cell.match(/^[-\s]+$/)) // Remove empty rows or separator rows
        );
    }
    
    // If not pipe-delimited, return as is
    return [[content]];
  }

    // Handle Google Docs integration
    async handleGoogleDocs(userId, stepResult, config) {
        console.log('Handling Google Docs Integration');
        console.log('Config:', config);
    
        await this.setupIntegrationAuth(userId);
        const docs = google.docs({ version: 'v1', auth: this.oauth2Client });
    
        if (config.mode === 'create_new') {
          const document = await this.createDoc(docs, {
            title: `Workflow Result - ${new Date().toISOString()}`,
            content: this.formatDataForDocs(stepResult)
          });
          return { docId: document.documentId };
        } else if (config.mode === 'fetch_and_use') {
          if (!config.docId) {
            throw new Error('Missing required parameters: documentId');
          }
          const docData = await this.getDocData(docs, {
            documentId: config.docId
          });
          return { readData: docData };
        } else {
          // default to "update existing" or "select_existing"
          if (!config.docId) {
            throw new Error('Missing required parameters: documentId');
          }
          await this.updateDoc(docs, {
            documentId: config.docId,
            content: this.formatDataForDocs(stepResult)
          });
          return { updated: true };
        }
      }
    
      // CREATE new document
      async createDoc(docs, { title, content }) {
        const response = await docs.documents.create({
          requestBody: { title }
        });
    
        await docs.documents.batchUpdate({
          documentId: response.data.documentId,
          requestBody: {
            requests: [{
              insertText: {
                location: { index: 1 },
                text: content
              }
            }]
          }
        });
    
        return response.data;
      }
    
      // UPDATE existing document
      async updateDoc(docs, { documentId, content }) {
        console.log('Updating Document:', documentId);
        console.log('Content to Insert:', content);
    
        if (!documentId) {
          throw new Error('Missing required parameters: documentId');
        }
    
        await docs.documents.batchUpdate({
          documentId,
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
    
      // READ data from a given document
      async getDocData(docs, { documentId }) {
        console.log('Fetching Document Data:', documentId);
    
        if (!documentId) {
          throw new Error('Missing required parameters: documentId');
        }
    
        const response = await docs.documents.get({ documentId });
        const content = response.data.body.content;
    
        // Extract text from the document
        let extractedText = '';
        content.forEach(element => {
          if (element.paragraph) {
            element.paragraph.elements.forEach(elem => {
              if (elem.textRun && elem.textRun.content) {
                extractedText += elem.textRun.content;
              }
            });
            extractedText += '\n'; // Add newline after each paragraph
          }
        });
    
        return extractedText;
      }
    
      // Format data for Docs
      formatDataForDocs(stepResult) {
        if (!stepResult) return 'No step result';
    
        if (typeof stepResult === 'string') {
          return stepResult;
        }
        if (stepResult.structured) {
          return JSON.stringify(stepResult.structured, null, 2);
        }
        return JSON.stringify(stepResult, null, 2);
      }
  // =========================================
  // ============== EMAIL ====================
  // =========================================
//   async handleEmail(userId, stepResult, config) {
//     // 1) We must get the user's doc to check if they have a GMail token
//     const userDoc = await firestore.db.collection('users').doc(userId).get();
//     const userData = userDoc.data();

//     if (!userData?.gmailToken) {
//       throw new Error('Gmail not connected. Please connect your Gmail account first.');
//     }
//     // If token is expired, you might want to refresh it here. (Similar to your /send route logic)
//     console.log("PROCESSING EMAIL")
//     // 2) Prepare OAuth2 client for Gmail
//     const gmailAuth = new google.auth.OAuth2(
//       process.env.GOOGLE_CLIENT_ID,
//       process.env.GOOGLE_CLIENT_SECRET,
//       `${process.env.API_URL}/api/gmail/auth/callback`
//     );
//     gmailAuth.setCredentials(userData.gmailToken);
//     const gmail = google.gmail({ version: 'v1', auth: gmailAuth });

//     // 3) Extract info from config or step result
//     const { recipients, subject, bodyTemplate } = config;
//     if (!recipients) throw new Error('No recipients provided for email integration.');

//     // Optionally embed stepResult data into the body if you want:
//     let finalBody = bodyTemplate || 'No body provided.';
//     // For example, if you want to include the raw step output:
//     // finalBody += `\n\nStep output:\n${JSON.stringify(stepResult, null, 2)}`;

//     // 4) Build raw RFC822 message
//     const utf8Subject = `=?utf-8?B?${Buffer.from(subject || 'No Subject').toString('base64')}?=`;
//     const messageParts = [
//       'Content-Type: text/plain; charset="UTF-8"',
//       'MIME-Version: 1.0',
//       `To: ${recipients}`,
//       `Subject: ${utf8Subject}`,
//       '',
//       finalBody
//     ];
//     const rawMessage = Buffer.from(messageParts.join('\n'))
//       .toString('base64')
//       .replace(/\+/g, '-')
//       .replace(/\//g, '_')
//       .replace(/=+$/, '');

//     // 5) Send email
//     const response = await gmail.users.messages.send({
//       userId: 'me',
//       requestBody: { raw: rawMessage }
//     });

//     return {
//       status: 'Email sent',
//       messageId: response.data.id,
//       recipients,
//       subject
//     };
//   }
// parsePipeTable.js (helper function)
async parsePipeTable(rawText) {
    // Remove markdown code block indicators and trim
    const cleanText = rawText.replace(/```\w*\n?|```/g, '').trim();
  
    // 1) Split by newlines
    const lines = cleanText.split('\n').map(line => line.trim()).filter(Boolean);
  
    // 2) Identify lines that contain '|'
    const tableLines = lines.filter(line => line.includes('|'));
  
    if (tableLines.length < 2) {
      // not a valid table
      return { headers: [], rows: [] };
    }
  
    // 3) The first line is the header row
    const headerLine = tableLines[0];
    // remove leading/trailing pipes
    const headerCells = headerLine.split('|')
      .map(h => h.trim())
      .filter(h => h.length);
  
    // Skip the separator line
    const dataLines = tableLines.slice(2);
  
    // 5) Convert each row into an array of columns
    const rows = dataLines.map(line => {
      const cells = line.split('|')
        .map(c => c.trim())
        .filter(c => c.length);
      return cells;
    });
  
    return {
      headers: headerCells,  // array of header names
      rows                  // array of arrays
    };
  }
async handleEmail(userId, stepResult, config) {
    const userDoc = await firestore.db.collection('users').doc(userId).get();
    const userData = userDoc.data();
    if (!userData?.gmailToken) {
      throw new Error('Gmail not connected. Please connect your Gmail account first.');
    }
  
    // Prepare OAuth2 client for Gmail
    const gmailAuth = new google.auth.OAuth2(
      process.env.GOOGLE_CLIENT_ID,
      process.env.GOOGLE_CLIENT_SECRET,
      `${process.env.API_URL}/api/gmail/auth/callback`
    );
    gmailAuth.setCredentials(userData.gmailToken);
    const gmail = google.gmail({ version: 'v1', auth: gmailAuth });
  
    // 1) Parse the table from stepResult.raw
    const table = await this.parsePipeTable(stepResult.raw || '');
    // e.g. table.headers = ['Invoice Number', 'Patient Name', 'email', ...]
    // e.g. table.rows = [ ['INV-123', 'John Doe', 'john@example.com', ...], ... ]
  
    // Find which column is "email"
    const possibleEmailHeaders = ['email', 'contact', 'email address'];
    const emailColIndex = table.headers.findIndex(header =>
      possibleEmailHeaders.includes(header.trim().toLowerCase())
    );
  
    // 2) If no email column found, either fallback to config.recipients or skip
    if (emailColIndex === -1) {
      // If you want to fallback to config’s recipients:
      if (!config.recipients) {
        throw new Error("No 'email' column found in table and no recipients provided.");
      }
      // Or just send a single email with the entire table. 
      // But let's assume we bail:
      // throw new Error("No 'email' column found in table. Stopping.");
    }
  
    // 3) Loop each row. For each row, if the row[emailColIndex] is a valid email, send an email with that row’s data.
    const results = [];
    for (const row of table.rows) {
      const rowEmail = row[emailColIndex];
      if (!rowEmail || !rowEmail.includes('@')) {
        // No valid email in this row, skip it
        continue;
      }
  
      // Build a row-specific body string
      // e.g. "Invoice Number: INV-123\nPatient Name: John Doe\n..."
      let rowBody = '';
      table.headers.forEach((header, i) => {
        rowBody += `${header}: ${row[i] || ''}\n`;
      });
  
      // You might also merge in user-provided bodyTemplate from config
      // e.g. final rowBody = yourTemplate + rowBody
      let finalBody = config.bodyTemplate
        ? `${config.bodyTemplate}\n\n${rowBody}`
        : rowBody;
  
      // 4) Construct your RFC822 raw message
      const utf8Subject = `=?utf-8?B?${Buffer.from(config.subject || 'No Subject').toString('base64')}?=`;
      const messageParts = [
        'Content-Type: text/plain; charset="UTF-8"',
        'MIME-Version: 1.0',
        `To: ${rowEmail}`,
        `Subject: ${utf8Subject}`,
        '',
        finalBody
      ];
      const rawMessage = Buffer.from(messageParts.join('\n'))
        .toString('base64')
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');
  
      // 5) Send an individual email for this row
      const response = await gmail.users.messages.send({
        userId: 'me',
        requestBody: { raw: rawMessage },
      });
  
      results.push({
        rowEmail,
        messageId: response.data.id,
        status: 'Email sent for that row',
      });
    }
  
    return {
      status: 'All row-specific emails sent',
      totalSent: results.length,
      details: results
    };
  }
  

}

export default new IntegrationHandlers();