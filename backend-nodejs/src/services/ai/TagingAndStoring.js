import { google } from 'googleapis';
import { Firestore } from '@google-cloud/firestore';
import { GoogleGenerativeAI } from '@google/generative-ai';

class SmartTagger {
  constructor(geminiService, userId) {
    this.gemini = geminiService;
    this.userId = userId;
    this.firestore = new Firestore({
      ignoreUndefinedProperties: true // Add this option
    });
    this.genAI= new GoogleGenerativeAI(process.env.GOOGLE_API_KEY);
    this.oauth2Client = new google.auth.OAuth2(
      process.env.GOOGLE_CLIENT_ID,
      process.env.GOOGLE_CLIENT_SECRET,
      `${process.env.API_URL}/api/docs-sheets/auth/callback`
    );
  }

  async generateEmbedding(text) {
    try {
      const embeddingModel = this.genAI.getGenerativeModel({ model: "embedding-001" });
      const results = await embeddingModel.embedContent(text);
      return results.embedding;
    } catch (error) {
      console.error('Error generating embedding:', error);
      throw error;
    }
  }
  async storeWithEmbeddings(collectionName, data, sessionId) {
    try {
      const textForEmbedding = this.prepareTextForEmbedding(data);
      let embedding = null;
      
      try {
        embedding = await this.generateEmbedding(textForEmbedding);
      } catch (embeddingError) {
        console.error('Error generating embedding:', embeddingError);
      }

      // Store main data in original location without embedding
      const docRef = this.firestore
        .collection('users')
        .doc(this.userId)
        .collection('sessions')
        .doc(sessionId)
        .collection(collectionName)
        .doc();

      const documentData = {
        ...data,
        timestamp: new Date(),
        sessionId
      };

      await docRef.set(documentData);

      // If we have an embedding, store it in sheet_embeddings collection
      if (embedding) {
        await this.firestore.collection('sheet_embeddings').doc(docRef.id).set({
          userId: this.userId,
          sessionId: sessionId,
          collectionType: collectionName,  // 'fields', 'context', or 'kpis'
          documentId: docRef.id,
          embedding: embedding,
          timestamp: new Date()
        });
      }

      return docRef.id;
    } catch (error) {
      console.error(`Error in storage for ${collectionName}:`, error);
      throw error;
    }
  }


    // Helper method to prepare text for embedding based on data type
    prepareTextForEmbedding(data) {
      if (data.fieldName && data.fieldValue) {
        return `${data.fieldName}: ${data.fieldValue}`;
      } else if (data.userIntent) {
        return `${data.userIntent} ${data.topics?.join(' ')} ${data.entities?.join(' ')}`;
      } else if (data.kpiName) {
        return `${data.category} ${data.kpiName} ${data.evidence}`;
      }
      return JSON.stringify(data);
    }
  
  async initializeSheetsClient() {
    const userDoc = await this.firestore.collection('users').doc(this.userId).get();
    const userData = userDoc.data();

    if (!userData?.googleSheetsToken) {
      throw new Error('Google Sheets not connected');
    }

    this.oauth2Client.setCredentials(userData.googleSheetsToken);
    this.sheets = google.sheets({ version: 'v4', auth: this.oauth2Client });
  }

  async processNodeData(node, message, sessionId, assistant) {
    console.log('👉 Processing node data for session:', sessionId);

    try {
      await this.initializeSheetsClient();

      // Run all analysis tasks in parallel, passing along the assistant where needed
      const tasks = [
        this.processFieldData(node, message, sessionId, assistant),
        this.processContextData(node, message, sessionId, assistant),
        this.processKPIData(message, node.response, assistant, sessionId)
      ];

      Promise.all(tasks).catch(error => {
        console.error('Error in background processing:', error);
      });
    } catch (error) {
      console.error('Error initializing sheets client:', error);
    }
  }

  async processFieldData(node, message, sessionId, assistant) {
    try {
      const fieldValue = await this.extractFieldValue(node.data.fieldName, message);
      if (!fieldValue) {
        console.warn('No field value extracted for:', node.data.fieldName);
        return;
      }

      const fieldData = [
        new Date().toISOString(),
        node.data.fieldName,
        fieldValue,
        node.id,
        'manual_input'
      ];

      const EmbeddingfieldData = {
        timestamp: new Date().toISOString(),
        fieldName: node.data.fieldName,
        fieldValue: fieldValue,
        nodeId: node.id,
        source: 'manual_input'
      };
      const firestorePromise = this.storeWithEmbeddings('fields', EmbeddingfieldData, sessionId);

      const response = await this.appendToSheet(sessionId, 'fields', fieldData, assistant);

      Promise.all([firestorePromise])
      .catch(error => console.error('Background processing error:', error));

      console.log('Field data written successfully:', response.data);
    } catch (error) {
      console.error('Error in processFieldData:', error);
      throw error;
    }
  }

  async processContextData(node, message, sessionId, assistant) {
    try {
      const contextData = await this.extractConversationContext(message, node);

      const firestorePromise = this.storeWithEmbeddings('context', contextData, sessionId);
      Promise.all([firestorePromise])
        .catch(error => console.error('Background processing error:', error));



      const contextRow = [
        new Date().toISOString(),
        node.id,
        node.type,
        contextData.userIntent,
        contextData.topics.join(', '),
        contextData.entities.join(', '),
        contextData.sentiment,
        contextData.urgency
      ];

      
      await this.appendToSheet(sessionId, 'context', contextRow, assistant);

      // Process additional fields
      try {
        const additionalFields = await this.extractAdditionalFields(message, contextData);

        
        if (additionalFields && additionalFields.length > 0) {
          for (const field of additionalFields) {

            await this.storeWithEmbeddings('additional_fields', field, sessionId);

            const additionalFieldRow = [
              new Date().toISOString(),
              field.type,
              field.value,
              node.id,
              'context_extracted'
            ];
            await this.appendToSheet(sessionId, 'fields', additionalFieldRow, assistant);
          }
        }
      } catch (error) {
        console.error('Error processing additional fields:', error);
      }
    } catch (error) {
      console.error('Error in processContextData:', error);
      return;
    }
  }

//   async processKPIData(message, response, assistant, sessionId) {
//     // Only process KPIs for representative assistants with KPI configuration
//     if (assistant?.assistantType !== 'representative' || !assistant.kpiConfig?.categories) {
//       return;
//     }

//     try {
//       const activeKPIs = this.extractActiveKPIs(assistant.kpiConfig);
//       if (activeKPIs.length === 0) return;

//       // Single prompt to analyze KPI measurements
//       const prompt = `
// Analyze this conversation exchange for KPI measurements:

// User Message: "${message}"
// Assistant Response: "${response}"

// Active KPIs to measure:
// ${activeKPIs.map(kpi => `
// - ${kpi.name} (${kpi.category})
//   Description: ${kpi.description}
//   Type: ${kpi.metricType}
//   Target: ${kpi.target}
// `).join('\n')}

// Provide analysis in JSON format with:
// 1. KPI measurements where confidence > 0.7

// Return format:
// {
//     "kpi_measurements": [{
//         "kpiId": "string",
//         "value": number,
//         "confidence": number,
//         "evidence": "string"
//     }]
// }
//       `;

//       const analysisResponse = await this.gemini.generateFlowProcessor(prompt, [], {
//         maxTokens: 500,
//         temperature: 0.3
//       });

//       const analysis = JSON.parse(analysisResponse.content.trim());
//       const kpiMeasurements = analysis.kpi_measurements.filter(m => m.confidence > 0.7);

//       for (const measurement of kpiMeasurements) {
//         const kpi = activeKPIs.find(k => k.id === measurement.kpiId);
//         if (!kpi) continue;

//         const kpiRow = [
//           new Date().toISOString(),
//           kpi.category,
//           kpi.name,
//           measurement.value,
//           measurement.confidence,
//           measurement.evidence,
//           sessionId
//         ];

//         await this.appendToSheet(sessionId, 'kpis', kpiRow, assistant);
//       }
//     } catch (error) {
//       console.error('Error processing KPI data:', error);
//     }
//   }
async processKPIData(message, response, assistant, sessionId) {
    if (assistant?.assistantType !== 'representative' || !assistant.kpiConfig?.categories) {
      return;
    }
  
    try {
      const activeKPIs = this.extractActiveKPIs(assistant.kpiConfig);

      if (activeKPIs.length === 0) return;
      console.log('USER MESSAGE')
      console.log(response, message)
      // Improved prompt with clearer instructions and examples
      const prompt = `
      Analyze this conversation exchange for specific KPI measurements:

      User Message: "${message}"
      Assistant Response: "${response}"

      Active KPIs to measure (analyze each carefully):
      ${activeKPIs.map(kpi => `
      - ${kpi.name} (ID: ${kpi.id})
        Category: ${kpi.category}
        Description: ${kpi.description}
        Type: ${kpi.metricType}
        Target: ${kpi.target}
      `).join('\n')}

      Instructions:
      1. For each KPI, carefully analyze the conversation to find relevant measurements
      2. For percentage metrics: Extract direct percentages or calculate from counts
      3. For number metrics: Look for specific counts, quantities, or numerical values
      4. For customer experience: Analyze sentiment and convert to numerical scores
      5. Even subtle indicators should be considered if confidence is high

      Example measurements:
      - If customer expresses satisfaction: CSAT score can be measured
      - If resolution is mentioned: FCR rate can be assessed
      - If multiple interactions are referenced: Retention rate can be calculated
      - If sales/revenue is discussed: Revenue impact can be measured

      Return a JSON object with measurements where you have high confidence (>0.7):
      {
          "kpi_measurements": [{
              "kpiId": "match with exact ID from above",
              "value": number (no symbols like $ or %),
              "confidence": number between 0.7 and 1.0,
              "evidence": "exact quote or clear reasoning from conversation"
          }]
      }

      If no measurements can be confidently made, return empty array but ALWAYS maintain valid JSON structure.
      `;

      const analysisResponse = await this.gemini.generateFlowProcessor(prompt, [], {
        maxTokens: 1000,  // Increased token limit
        temperature: 0.3
      });
      console.log(analysisResponse)
      // Clean and parse response
      const cleanedContent = analysisResponse.content
        .replace(/```json\n?/g, '')
        .replace(/```\n?/g, '')
        .trim();
  
      const analysis = JSON.parse(cleanedContent);
      const kpiMeasurements = analysis.kpi_measurements.filter(m => m.confidence > 0.7);
  
      // Log for debugging
      console.log('KPI Analysis Results:', {
        totalMeasurements: kpiMeasurements.length,
        measurements: kpiMeasurements
      });

      for (const measurement of kpiMeasurements) {
        const kpi = activeKPIs.find(k => k.id === measurement.kpiId);
        if (!kpi) {
          console.log('No matching KPI found for:', measurement.kpiId);
          continue;
        }
  
        const kpiRow = [
          new Date().toISOString(),
          kpi.category,
          kpi.name,
          measurement.value,
          measurement.confidence,
          measurement.evidence,
          sessionId
        ];
  
        const kpiData = {
          timestamp: new Date().toISOString(),
          category: kpi.category,
          kpiName: kpi.name,
          value: measurement.value,
          confidence: measurement.confidence,
          evidence: measurement.evidence,
          sessionId
        };
         
        Promise.all([
          this.storeWithEmbeddings('kpis', kpiData, sessionId),
        ]).catch(error => console.error('KPI measurement processing error:', error));
   

        await this.appendToSheet(sessionId, 'kpis', kpiRow, assistant);
      }
    } catch (error) {
      console.error('Error processing KPI data:', error);
      console.error('Error details:', error.message);
    }
}
  extractActiveKPIs(kpiConfig) {
    const activeKPIs = [];
    Object.entries(kpiConfig.categories).forEach(([category, kpis]) => {
      kpis.forEach(kpi => {
        if (kpi.enabled) {
          activeKPIs.push({
            id: kpi.id,
            category,
            name: kpi.name,
            description: kpi.description,
            metricType: kpi.metricType,
            target: kpi.target
          });
        }
      });
    });
    return activeKPIs;
  }

  // getOrCreateSpreadsheet now accepts an optional assistant so that the spreadsheets are named with a prefix
  async getOrCreateSpreadsheet(sessionId, assistant = null) {
    const assistantPrefix = assistant && assistant.id ? `${assistant.id}_` : '';
    const fieldsTitle = `${assistantPrefix}${sessionId}_fields`;
    const contextTitle = `${assistantPrefix}${sessionId}_context`;
    const kpiTitle = `${assistantPrefix}${sessionId}_kpis`;

    const drive = google.drive({ version: 'v3', auth: this.oauth2Client });

    try {
      const [fieldsResponse, contextResponse, kpiResponse] = await Promise.all([
        drive.files.list({
          q: `name='${fieldsTitle}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false`,
          fields: 'files(id)',
          spaces: 'drive'
        }),
        drive.files.list({
          q: `name='${contextTitle}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false`,
          fields: 'files(id)',
          spaces: 'drive'
        }),
        drive.files.list({
          q: `name='${kpiTitle}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false`,
          fields: 'files(id)',
          spaces: 'drive'
        })
      ]);

      let fieldsId, contextId, kpiId;

      // Handle Fields spreadsheet
      if (fieldsResponse.data.files.length > 0) {
        fieldsId = fieldsResponse.data.files[0].id;
        console.log('Found existing fields spreadsheet:', fieldsId);
      } else {
        const createFieldsResponse = await this.sheets.spreadsheets.create({
          requestBody: {
            properties: { title: fieldsTitle },
            sheets: [{
              properties: {
                title: 'Sheet1',
                gridProperties: { rowCount: 1000, columnCount: 10 }
              }
            }]
          }
        });
        fieldsId = createFieldsResponse.data.spreadsheetId;
        console.log('Created new fields spreadsheet:', fieldsId);
        await this.sheets.spreadsheets.values.update({
          spreadsheetId: fieldsId,
          range: 'Sheet1!A1:E1',
          valueInputOption: 'USER_ENTERED',
          requestBody: {
            values: [['Timestamp', 'Field Name', 'Field Value', 'Node ID', 'Source']]
          }
        });
      }

      // Handle Context spreadsheet
      if (contextResponse.data.files.length > 0) {
        contextId = contextResponse.data.files[0].id;
        console.log('Found existing context spreadsheet:', contextId);
      } else {
        const createContextResponse = await this.sheets.spreadsheets.create({
          requestBody: {
            properties: { title: contextTitle },
            sheets: [{
              properties: {
                title: 'Sheet1',
                gridProperties: { rowCount: 1000, columnCount: 10 }
              }
            }]
          }
        });
        contextId = createContextResponse.data.spreadsheetId;
        console.log('Created new context spreadsheet:', contextId);
        await this.sheets.spreadsheets.values.update({
          spreadsheetId: contextId,
          range: 'Sheet1!A1:H1',
          valueInputOption: 'USER_ENTERED',
          requestBody: {
            values: [['Timestamp', 'Node ID', 'Node Type', 'User Intent', 'Topics', 'Entities', 'Sentiment', 'Urgency']]
          }
        });
      }

      // Handle KPIs spreadsheet
      if (kpiResponse.data.files.length > 0) {
        kpiId = kpiResponse.data.files[0].id;
        console.log('Found existing kpis spreadsheet:', kpiId);
      } else {
        const createKpiResponse = await this.sheets.spreadsheets.create({
          requestBody: {
            properties: { title: kpiTitle },
            sheets: [{
              properties: {
                title: 'Sheet1',
                gridProperties: { rowCount: 1000, columnCount: 10 }
              }
            }]
          }
        });
        kpiId = createKpiResponse.data.spreadsheetId;
        console.log('Created new kpis spreadsheet:', kpiId);
        await this.sheets.spreadsheets.values.update({
          spreadsheetId: kpiId,
          range: 'Sheet1!A1:G1',
          valueInputOption: 'USER_ENTERED',
          requestBody: {
            values: [[
              'Timestamp',
              'Category',
              'KPI Name',
              'Value',
              'Confidence',
              'Evidence',
              'Session ID'
            ]]
          }
        });
      }

      return { fieldsId, contextId, kpiId };
    } catch (error) {
      console.error('Error in getOrCreateSpreadsheet:', error);
      throw error;
    }
  }

  // Now appendToSheet takes an extra assistant parameter so that it can pass it to getOrCreateSpreadsheet
  async appendToSheet(sessionId, sheetName, rowData, assistant = null) {
    try {
      const { fieldsId, contextId, kpiId } = await this.getOrCreateSpreadsheet(sessionId, assistant);
      let spreadsheetId;
      if (sheetName === 'fields') {
        spreadsheetId = fieldsId;
      } else if (sheetName === 'context') {
        spreadsheetId = contextId;
      } else if (sheetName === 'kpis') {
        spreadsheetId = kpiId;
      } else {
        throw new Error(`Invalid sheet name: ${sheetName}`);
      }

      const formattedData = this.formatRowData(rowData);

      // Get current data to calculate the next available row (assuming 'Sheet1')
      const currentData = await this.sheets.spreadsheets.values.get({
        spreadsheetId,
        range: 'Sheet1!A:Z'
      });
      const nextRow = (currentData.data.values?.length || 0) + 1;

      const response = await this.sheets.spreadsheets.values.update({
        spreadsheetId,
        range: `Sheet1!A${nextRow}`,
        valueInputOption: 'USER_ENTERED',
        requestBody: {
          values: [formattedData]
        }
      });

      console.log(`👉 Successfully wrote to ${sheetName}:`, {
        updatedRange: response.data.updatedRange,
        updatedRows: response.data.updatedRows
      });

      return response;
    } catch (error) {
      console.error(`Error writing to ${sheetName}:`, error);
      throw error;
    }
  }

  formatRowData(rowData) {
    return rowData.map(cell => {
      if (cell instanceof Date) {
        return cell.toISOString();
      }
      if (Array.isArray(cell)) {
        return cell.join(', ');
      }
      if (typeof cell === 'object' && cell !== null) {
        return JSON.stringify(cell);
      }
      return cell?.toString() || '';
    });
  }

  async extractAdditionalFields(message, contextData) {
    const prompt = `
Extract any important information from this message that could be useful for order processing.

Message: "${message}"
Context: ${JSON.stringify(contextData)}

Look for:
1. Addresses (shipping, billing, etc.)
2. Names (customer name, recipient name)
3. Email addresses
4. Alternative phone numbers
5. Additional order details
6. Special instructions
7. Payment information (exclude sensitive details)
8. Delivery preferences

Return a JSON array of found fields, each with 'type' and 'value'. 
Only include fields that are actually present and clearly identifiable.
Return empty array if no fields found.

Example format:
[
    {"type": "shipping_address", "value": "123 Main St"},
    {"type": "customer_name", "value": "John Doe"}
]
    `;
    
    const response = await this.gemini.generateFlowProcessor(prompt, [], {
      maxTokens: 200,
      temperature: 0.3
    });
    
    try {
      const cleanedContent = response.content
        .replace(/```json\n?/g, '')
        .replace(/```\n?/g, '')
        .trim();
      const fields = JSON.parse(cleanedContent);
      return fields.filter(field => field.type && field.value && field.type !== 'phone_number');
    } catch (error) {
      console.error('Error parsing additional fields:', error);
      return [];
    }
  }

  async extractFieldValue(fieldName, message) {
    const prompt = `
Extract the specific value for the field "${fieldName}" from this message: "${message}"

Rules for extraction:
1. For phone numbers: Extract only digits and common phone number symbols (+-())
2. For emails: Extract the complete email address
3. For dates: Extract in ISO format (YYYY-MM-DD)
4. For names: Extract full name
5. For general fields: Extract the most relevant value

Return only the extracted value, nothing else.
    `;
        
    const response = await this.gemini.generateFlowProcessor(prompt, [], {
      maxTokens: 100,
      temperature: 0.1
    });
        
    return response.content.trim();
  }

  async extractConversationContext(message, node) {
    const prompt = `
Analyze this conversation snippet and extract key information:

Node Type: ${node.type}
Node Message: ${node.data?.message || 'N/A'}
User Message: "${message}"

Extract and provide the following in JSON format:
1. "userIntent": Main intent or purpose of the user's message
2. "topics": Array of main topics discussed
3. "entities": Key entities mentioned (names, products, services, etc.)
4. "sentiment": Overall sentiment (positive, negative, neutral)
5. "urgency": Level of urgency (high, medium, low)

Return only valid JSON without any markdown formatting or code blocks.
    `;
        
    const response = await this.gemini.generateFlowProcessor(prompt, [], {
      maxTokens: 200,
      temperature: 0.3
    });
        
    try {
      const cleanedContent = response.content
        .replace(/```json\n?/g, '')
        .replace(/```\n?/g, '')
        .trim();
      const contextInfo = JSON.parse(cleanedContent);
      return {
        timestamp: new Date().toISOString(),
        nodeId: node.id,
        nodeType: node.type,
        ...contextInfo
      };
    } catch (error) {
      console.error('Error parsing context info:', error);
      return {
        timestamp: new Date().toISOString(),
        nodeId: node.id,
        nodeType: node.type,
        error: 'Failed to parse context'
      };
    }
  }

     async appendToCSV(filePath, data) {
        try {
            console.log('👉 Attempting to write to:', filePath);
            console.log('👉 Data to write:', data);
            
            let existingData = [];
            
            if (await fs.pathExists(filePath)) {
                console.log('👉 File exists, reading existing data');
                const fileContent = await fs.readFile(filePath, 'utf8');
                existingData = Papa.parse(fileContent, { header: true }).data;
            } else {
                console.log('👉 File does not exist, will create new');
            }
            
            existingData.push(data);
            const csv = Papa.unparse(existingData);
            await fs.writeFile(filePath, csv, 'utf8');
            console.log('👉 Successfully wrote to file');
            
        } catch (error) {
            console.error('👉 Error managing CSV:', filePath, error);
        }
    }

    async getSessionData(sessionId) {
        try {
            const fieldsPath = path.join('./session_data', sessionId, 'fields.csv');
            const contextPath = path.join('./session_data', sessionId, 'context.csv');
            
            const [fields, context] = await Promise.all([
                fs.pathExists(fieldsPath) ? 
                    fs.readFile(fieldsPath, 'utf8').then(content => 
                        Papa.parse(content, { header: true }).data
                    ) : [],
                fs.pathExists(contextPath) ? 
                    fs.readFile(contextPath, 'utf8').then(content => 
                        Papa.parse(content, { header: true }).data
                    ) : []
            ]);

            return { fields, context };
        } catch (error) {
            console.error('Error getting session data:', error);
            return { fields: [], context: [] };
        }
    }
}

export default SmartTagger;
