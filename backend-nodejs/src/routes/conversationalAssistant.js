// routes/conversationalAssistant.js
import express from 'express';
import { verifyToken } from '../middleware/auth.js';
import { Firestore } from '@google-cloud/firestore';
import { Storage } from '@google-cloud/storage';
import geminiService from '../services/ai/gemini.js';
import RAGService from '../services/ai/TellePhonAi/tellephonAiRag.js'
import multer from 'multer';

const router = express.Router();
// const firestore = new Firestore();
const firestore = new Firestore({
  projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
  keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  databaseId: 'circa'  // Explicitly specify the database name
});
const storage = new Storage();
const BUCKET_NAME = 'circa-ai';

// Representative creation instructions
// Representative creation instructions
const REPRESENTATIVE_CREATION_INSTRUCTIONS = `You are assisting in creating an AI representative. Collect all required information through natural conversation. Ask questions one at a time and wait for user responses.

Key Information to Collect:

1. Basic Information:
   - Name of the representative 
   - Description of what the representative does (One Line Description of what hritvik Does)
   - Category (Healthcare, Legal, Education, Finance, or Custom)
   - Instructions for what he will do/ around 4 to 5 points at max. 

2. KPI Configuration (for each category):
   Track KPIs across these standard categories or create custom ones:
   a) Customer Interaction:
      - CSAT Score
      - NPS
      - Sentiment Analysis
   b) Performance Metrics:
      - Response Time
      - Resolution Rate
      - Handle Time
   c) Product Feedback:
      - Feature Requests
      - Bug Reports
      - Usability Feedback
   d) Business Impact:
      - Conversion Rate
      - Retention Rate
      - Revenue Impact

   From users apart from previous APIs ask if they want to remove previous KPIs given in (a), (b), (c), (d) or want to add more. 
   For each KPI, collect:
   - KPI name
   - Description
   - Metric type (percentage, number, currency, time)
   - Target value

3. Workflow/Flow Builder Data:
   - Collect information about desired conversation flows, decision points, and logic branches.
   - Gather response templates for different scenarios.
   - Additionally, capture the complete flow builder configuration as follows:
       * Provide an array called "nodes". Each node should be a JSON object that includes:
           - "id": a unique identifier for the node.
           - "nodeType": the type of node (e.g., dialogueNode, fieldSetterNode, callTransferNode, responseNode, etc.).
           - "message" or "heading" (if applicable) along with any additional properties (such as "functions", "fieldName", "position", etc.).
       * Provide an array called "edges". Each edge should be a JSON object that includes:
           - "source": the id of the source node.
           - "target": the id of the target node.
           - Optionally, any additional connection metadata (such as edge type or descriptive details).

4. Training Data:
   - Ask about any documents or files for training.
   - Determine types of content needed for the knowledge base.

Maintain conversation naturally and professionally while collecting all required information.`;

// Message classification prompt
const CLASSIFICATION_PROMPT = `Analyze the following message and classify its intent. 
RESPOND ONLY WITH THE JSON OBJECT, NO OTHER TEXT OR EXPLANATION.
The response must be a valid JSON object containing:
{
  "type": "create_representative" | "general_query" | "other",
  "confidence": 0-1 score,
  "details": {
    "stage": "initial" | "in_progress" | "complete",
    "collected_info": {} // Any information extracted from the message
  }
}

DO NOT include any explanatory text, markdown formatting, or code blocks. Return ONLY the JSON object.`;

// Updated classification function with enhanced context awareness
async function classifyMessageChainOfThought(message, conversationContext = []) {
    // Extract relevant system messages and last 3 user/assistant exchanges
    const recentContext = conversationContext.slice(-8).filter(msg => 
      msg.role === 'user' || 
      msg.role === 'assistant' ||
      (msg.role === 'system' && (msg.type === 'stage' || msg.type === 'collected_data'))
    );
  
    // Build enriched conversation snippet with system states
    const conversationSnippet = recentContext
      .map(msg => {
        if (msg.role === 'system') {
          if (msg.type === 'stage') {
            return `[SYSTEM STATE] Current creation stage: ${msg.stage}`;
          }
          if (msg.type === 'collected_data') {
            return `[SYSTEM DATA] Collected information: ${JSON.stringify(msg.data)}`;
          }
        }
        return `${msg.role.toUpperCase()}: ${msg.content || ''}`;
      })
      .join('\n');
  
    // Enhanced chain-of-thought prompt
    const prompt = `
  <thinking>
  Analyze this conversation context and new message to determine intent:
  
  Recent Context:
  ${conversationSnippet}
  
  New Message: "${message}"
  
  Step-by-Step Analysis:
  1. Analayze the user Message Throughly
    - Is new message a direct answer to assistant's last question?
    - check if user is asking to create representative, assistant or an agent or voice agent or A.I Agent
    → If yes: High confidence 'create_representative'
    - Check message for creation-related keywords
    - Look for intent to start new representative creation
  
  4. Fallback Analysis:
     - General question about existing features? → 'general_query'
     - Unrelated topic? → 'other'
  
  Confidence Scoring:
  - 0.95 if clear continuation of existing flow
  - 0.8-0.9 if new creation request
  - 0.7-0.8 if ambiguous
  - <0.7 for general queries
  </thinking>
  
  <response-format>
  {
    "type": "create_representative" | "general_query" | "other",
    "confidence": ${Math.random().toFixed(1)}, // Replace with actual calculation
    "details": {
      "stage": "initial" | "in_progress" | "complete",
      "collected_info": {} // Any extracted fields
    }
  }
  </response-format>
  
  <rules>
  1. Favor 'create_representative' if any active creation context exists
  2. Assume message continues current flow unless clearly unrelated
  3. Extract partial info even from incomplete responses
  </rules>`;
  
    // Call LLM and parse response
    const classificationRaw = await geminiService.generateResponse(
        prompt,
        [],
        { maxTokens: 400, temperature: 0.2 }
    );

   // Add robust parsing and fallback logic
   let parsedResult;
   try {
       // 1. Remove all code block markers and trim whitespace
       let cleanedContent = classificationRaw.content
           .replace(/```json|```/g, '')
           .trim();

       // 2. Handle cases where response includes "json" prefix
       cleanedContent = cleanedContent.replace(/^json\s*/i, '');

       // 3. Find first valid JSON object
       const jsonStart = cleanedContent.indexOf('{');
       const jsonEnd = cleanedContent.lastIndexOf('}') + 1;
       
       if (jsonStart === -1 || jsonEnd === 0) {
           throw new Error('No JSON structure found');
       }

       const jsonString = cleanedContent.slice(jsonStart, jsonEnd);
       
       // 4. Fix common formatting issues
       const repairedJson = jsonString
           // Remove trailing commas
           .replace(/,\s*}/g, '}')
           .replace(/,\s*]/g, ']')
           // Fix missing quotes
           .replace(/(\w+):/g, '"$1":')
           // Convert single quotes to double
           .replace(/'/g, '"');

       parsedResult = JSON.parse(repairedJson);
   } catch (error) {
       console.error('Classification parse error:', error);
       console.error('Original response content:', classificationRaw.content);
       
       // If we have creation context, force create_representative type
       const hasCreationContext = conversationSnippet.includes('create_representative') || 
           conversationSnippet.includes('SYSTEM STATE');

       parsedResult = {
           type: hasCreationContext ? 'create_representative' : 'general_query',
           confidence: hasCreationContext ? 0.95 : 0.8,
           details: {
               stage: hasCreationContext ? 'in_progress' : 'initial',
               collected_info: extractPartialInfo(message)
           }
       };
   }

   // Context-based validation
   const hasCreationContext = conversationSnippet.includes('create_representative') || 
       conversationSnippet.includes('SYSTEM STATE');

   if (hasCreationContext && parsedResult.type !== 'create_representative') {
       return {
           type: 'create_representative',
           confidence: 0.95,
           details: {
               stage: 'in_progress',
               collected_info: extractPartialInfo(message)
           }
       };
   }

   // Validate JSON structure
   if (!parsedResult.type || !parsedResult.details) {
       return {
           type: 'create_representative',
           confidence: 0.9,
           details: {
               stage: 'in_progress',
               collected_info: extractPartialInfo(message)
           }
       };
   }

   return parsedResult;
}

// Helper function remains the same
function extractPartialInfo(message) {
   if (message.length > 15 && message.split(' ').length > 3) {
       return { possible_description: message };
   }
   return { possible_name: message };
}
  
// Default KPI Settings
const DEFAULT_KPI_SETTINGS = {
  "Customer Interaction": [
    { id: 'csat', name: 'CSAT Score', description: 'Customer satisfaction score', enabled: true },
    { id: 'nps', name: 'NPS', description: 'Net Promoter Score', enabled: true },
    { id: 'sentiment', name: 'Sentiment Analysis', description: 'Customer mood and satisfaction', enabled: true }
  ],
  "Performance Metrics": [
    { id: 'responseTime', name: 'Response Time', description: 'Average response time', enabled: true },
    { id: 'resolutionRate', name: 'Resolution Rate', description: 'First contact resolution rate', enabled: true },
    { id: 'handleTime', name: 'Handle Time', description: 'Average conversation duration', enabled: true }
  ],
  "Product Feedback": [
    { id: 'featureRequests', name: 'Feature Requests', description: 'New feature suggestions tracked', enabled: true },
    { id: 'bugReports', name: 'Bug Reports', description: 'Issues reported by customers', enabled: true },
    { id: 'usability', name: 'Usability Feedback', description: 'User experience feedback', enabled: true }
  ],
  "Business Impact": [
    { id: 'conversion', name: 'Conversion Rate', description: 'Lead to customer conversion', enabled: true },
    { id: 'retention', name: 'Retention Rate', description: 'Customer retention tracking', enabled: true },
    { id: 'revenue', name: 'Revenue Impact', description: 'Revenue generated/saved', enabled: true }
  ]
};

// Function to handle the representative creation flow
const stages = {
    initial: {
      section: 'basic_info',
      required: ['name', 'description', 'category', 'instructions'],
      next: 'kpis'
    },
    kpis: {
      section: 'kpis',
      required: ['kpi_configuration'],
      next: 'workflow'
    },
    workflow: {
      section: 'workflow',
      required: ['flow_data'],
      next: 'training'
    },
    training: {
      section: 'training',
      required: ['training_data'],
      next: 'complete'
    },
    complete: {
        section: 'complete',
        required: [],
        next: null
      }
  };
// Function to handle the representative creation flow
const processCreateRepresentative = async (message, context = []) => {
    // Get current stage and collected data from context
    const currentStage = [...context].reverse().find(msg => msg.type === 'stage')?.stage || 'initial';
    const collectedData = context.find(msg => msg.type === 'collected_data')?.data || {};
  
    console.log(`
      Current stage: ${currentStage}
      Current section: ${stages[currentStage]?.section}
      Previously collected data: ${JSON.stringify(collectedData, null, 2)}
    `);
  
    // Generate conversation prompt
    let prompt = `${REPRESENTATIVE_CREATION_INSTRUCTIONS}
  
  Current stage: ${currentStage}
  Current section: ${stages[currentStage]?.section}
  Previously collected data: ${JSON.stringify(collectedData, null, 2)}
  Previous messages: ${JSON.stringify(
      context
        .filter(msg => msg.role === 'user' || msg.role === 'assistant')
        .map(msg => ({ role: msg.role, content: msg.content })),
      null,
      2
  )}
  User message: ${message}
  
  IMPORTANT: You are in a sequential information collection process. 
  For each stage, collect specific information and then move to the next stage.
  
  Current Requirements for ${stages[currentStage]?.section}:
  ${JSON.stringify(stages[currentStage]?.required)}
  
  Instructions:
  1. Extract relevant information from the user's message for the CURRENT stage only.
  2. If information is complete for the current stage:
     - Move to the next stage.
     - Provide a summary of what was collected.
     - ALWAYS include a specific question to start the next stage.
  3. If the current stage is incomplete:
     - Ask specific questions for the missing required information.
  4. Return in JSON format:
  
  {
    "extracted_info": {
      // For KPI stage, data must be under 'kpi_configuration' field like this:
      // "kpi_configuration": {
      //   "name": "user emotion",
      //   "description": "measures user sentiment",
      //   "metric": "percentage",
      //   "target_value": 80
      // },
    },
    "validation": {
      "isValid": boolean,
      "errors": []
    },
    "next_stage": "${stages[currentStage].next}" // if complete
    "next_question": "Ask SPECIFIC question about missing information for current stage",
    "is_complete": boolean,
    "summary": "If moving to next stage, summarize what was collected"
  }
  
  Remember:
  - Focus on collecting info for the CURRENT stage only.
  - Only move to the next stage when ALL required fields for the current stage are complete.
  - Ask specific questions about any missing required fields.
  - Use previously collected data to avoid asking for information we already have.`;
  
    // Append additional instructions if the current stage is "workflow"
    if (currentStage === 'workflow') {
      prompt += `
  
  IMPORTANT (Workflow Stage):
  Since we are now in the "workflow" stage, please also capture all flow builder details. In addition to the above, provide the workflow configuration as follows:
  
  1. Provide an array called "nodes". Each node should be a JSON object that includes:
     - "id": a unique identifier.
     - "nodeType": the type of node (e.g., dialogueNode, fieldSetterNode, callTransferNode, responseNode, etc.).
     - "message" or "heading" (if applicable) and any additional properties (such as "functions", "fieldName", "position", etc.).
  
  2. Provide an array called "edges". Each edge should be a JSON object that includes:
     - "source": the id of the source node.
     - "target": the id of the target node.
     - Optionally, any other connection metadata.
  
  Ensure that your JSON response follows this structure and clearly provides the complete workflow data.`;
    }
  
    // Call the model and parse the response carefully
    const response = await geminiService.generateResponse(prompt);
    console.log('Process response:', response.content); // Debug log
  
    // 1. Remove code fences
    let cleanedResponse = response.content
      .replace(/```json\n?|\n?```/g, '')
      .trim();
  
    // 2. Extract only the first { ... } block
    const match = cleanedResponse.match(/\{[\s\S]*\}/);
    if (!match) {
      console.error('No valid JSON found in model response:', cleanedResponse);
      throw new Error('No valid JSON found in model response');
    }
  
    // 3. Parse that JSON substring
    cleanedResponse = match[0];
    let result;
    try {
      result = JSON.parse(cleanedResponse);
    } catch (err) {
      console.error('JSON Parse Error:', err);
      console.error('Attempted to parse:', cleanedResponse);
      throw err;
    }
  
    // We now have our structured JSON in `result`
    // Next steps remain the same as your existing code
    if (result.next_stage !== currentStage && result.summary) {
      result.next_question = `${result.summary}\n\n${result.next_question}`;
    }
  
    // Merge previously collected data with the new extracted info
const updatedData = {
    ...collectedData,
    ...result.extracted_info
  };
  
  // Check completeness using the aggregated data
  const isCurrentSectionComplete = stages[currentStage].required.every(field => {
    const value = updatedData[field];
    return value && (
      Array.isArray(value) ? value.length > 0 :
      typeof value === 'object' ? Object.keys(value).length > 0 :
      !!value
    );
  });
  
    // Force stage transition when complete
    if (isCurrentSectionComplete) {
        if (stages[currentStage]) {
          result.next_stage = stages[currentStage].next;
        } else {
          result.next_stage = null;
        }
        // For stages other than 'training', mark as incomplete so that subsequent stages get triggered
        result.is_complete = currentStage === 'training' ? true : false;
    }
    
      
    
    return {
      ...result,
      collected_data: {
        ...collectedData,
        ...result.extracted_info
      },
      is_section_complete: isCurrentSectionComplete,
      is_complete: result.is_complete
    };
  };
  
// Main route for handling messages
// router.post('/message', verifyToken, async (req, res) => {
//     try {
//       const { message, conversationId } = req.body;
//       const userId = req.user.id;
  
//       // Get conversation context
//       const conversationRef = firestore.collection('conversations').doc(conversationId);
//       const conversationDoc = await conversationRef.get();
//       const context = conversationDoc.exists ? conversationDoc.data().messages : [];
//       if (!conversationDoc.exists) {
//         await conversationRef.set({
//           userId: userId,  // Add userId to conversation document
//           messages: [],
//           createdAt: Firestore.FieldValue.serverTimestamp()
//         });
//       }
//       // ----- NEW: Use chain-of-thought classification function -----
//       const classificationResult = await classifyMessageChainOfThought(message, context);
  
//       console.log('Classification result:', classificationResult);
  
//       let response;
//       // If we detect create_representative with sufficient confidence
//       if (classificationResult.type === 'create_representative' && classificationResult.confidence > 0.7) {
//         // Process creation flow
//         const result = await processCreateRepresentative(message, context);
//         console.log(result)
//         if (result.is_complete) {
//           // If representative creation is done, store final data
//           const assistantData = {
//             name: result.collected_data.name,
//             description: result.collected_data.description,
//             category: result.collected_data.category,
//             instructions: result.collected_data.instructions,
//             customization: {
//               bio: result.collected_data.bio || '',
//               expertise: result.collected_data.expertise || '',
//               experience: result.collected_data.experience || '',
//               profession: result.collected_data.profession || '',
//               voiceType: result.collected_data.voiceType || '',
//               socialLinks: result.collected_data.socialLinks || {}
//             },
//             assistantType: 'representative',
//             kpiConfig: {
//             categories: result.collected_data.kpi_configuration || DEFAULT_KPI_SETTINGS,
//             activeKPIs: {},
//               metrics: {},
//               lastUpdated: null
//             },
//             flowData: result.collected_data.flow_data || null
//         };
          
  
//           // Create new assistant doc
//           const assistantRef = firestore.collection('assistants').doc();
//           await assistantRef.set({
//             ...assistantData,
//             id: assistantRef.id,
//             userId,
//             createdAt: Firestore.FieldValue.serverTimestamp(),
//             status: 'active',
//             documentCount: 0,
//             queryCount: 0
//           });
  
//           response = {
//             type: 'create_representative_complete',
//             message: `Great! I've created your representative named ${assistantData.name}. You can now find it in your assistants dashboard.`,
//             assistantId: assistantRef.id
//           };
//         } else {
//           // Not complete yet, keep collecting
//           response = {
//             type: 'create_representative_progress',
//             message: result.next_question,
//             stage: result.next_stage
//           };
//         }
  
//         // Update conversation context with user message + system updates
//         await conversationRef.set({
//             userId: userId,  // Maintain userId on updates
//             messages: context
//               // Remove old stage and collected_data messages
//               .filter(msg => msg.type !== 'stage' && msg.type !== 'collected_data')
//               .concat([
//                 { role: 'user', content: message, type: 'message' },
//                 { role: 'system', type: 'stage', stage: result.next_stage },
//                 { role: 'system', type: 'collected_data', data: result.collected_data }
//               ])
//           }, { merge: true });
//       } else {
//         // Otherwise handle as a general or "other" type of conversation
//         // Here, you might do a normal LLM-based answer, or pass it to a knowledge base
//         const aiResponse = await geminiService.generateResponse(message, context);
//         response = {
//           type: 'general_response',
//           message: aiResponse.content || aiResponse // adjust based on your geminiService
//         };
//       }
  
//       res.json(response);
  
//     } catch (error) {
//       console.error('Error in message processing:', error);
//       res.status(500).json({ error: 'Failed to process message' });
//     }
//   });
// router.post('/message', verifyToken, async (req, res) => {
//     try {
//       const { message, conversationId } = req.body;
//       const userId = req.user.id;
  
//       // Get conversation context
//       const conversationRef = firestore.collection('conversations').doc(conversationId);
//       const conversationDoc = await conversationRef.get();
//       const context = conversationDoc.exists ? conversationDoc.data().messages : [];
//       if (!conversationDoc.exists) {
//         await conversationRef.set({
//           userId: userId,
//           messages: [],
//           createdAt: Firestore.FieldValue.serverTimestamp()
//         });
//       }
  
//       // Use your classification function as before
//       const classificationResult = await classifyMessageChainOfThought(message, context);
//       console.log('Classification result:', classificationResult);
  
//       let response;
//       // When the intent is to create a representative, simply instruct the frontend to open the modal.
//       if (classificationResult.type === 'create_representative' && classificationResult.confidence > 0.7) {
//         response = {
//           type: 'open_representative_modal',
//           message: "Have you created the agent or representaive from the modal is there anything else i can help you with."
//         };
  
//         // Optionally update conversation context with system info
//         await conversationRef.set({
//           userId: userId,
//           messages: context.concat([
//             { role: 'user', content: message, type: 'message' },
//             { role: 'system', type: 'open_modal', message: response.message }
//           ])
//         }, { merge: true });
//       } else {
//         // RAG-enhanced response generation
//         // 1. Search across all collections
//         // console.log("USER ID",)
//         const relevantResults = await RAGService.searchAllCollections(message, userId);
//         console.log('Search All Collections', relevantResults)
//         // 2. Generate enhanced prompt with context
//         const enhancedPrompt = await RAGService.generatePromptWithContext(message, relevantResults);
//         console.log("conversation prompt", enhancedPrompt)
//         // 3. Generate response using the enhanced prompt
//         const aiResponse = await geminiService.generateResponse(enhancedPrompt, context);

        
//         response = {
//             type: 'general_response',
//             message: aiResponse.content || aiResponse,
//             context: relevantResults.length > 0 ? {
//                 sourcesUsed: relevantResults.map(r => ({
//                     type: r.type,
//                     similarity: r.similarity,
//                     timestamp: r.metadata.timestamp
//                 }))
//             } : null
//         };

//         // Store conversation as before
//         await conversationRef.set({
//             userId: userId,
//             messages: context.concat([
//                 { role: 'user', content: message, type: 'message' },
//                 { role: 'assistant', content: response.message, type: 'message' }
//             ])
//         }, { merge: true });
//     }

//     res.json(response);
//     } catch (error) {
//       console.error('Error in message processing:', error);
//       res.status(500).json({ error: 'Failed to process message' });
//     }
//   });

router.post('/message', verifyToken, async (req, res) => {
    try {
      const { message, conversationId } = req.body;
      const userId = req.user.id;
  
      const conversationRef = firestore.collection('conversations').doc(conversationId);
      const conversationDoc = await conversationRef.get();
      const context = conversationDoc.exists ? conversationDoc.data().messages : [];
  
      if (!conversationDoc.exists) {
        await conversationRef.set({
          userId,
          messages: [],
          createdAt: Firestore.FieldValue.serverTimestamp()
        });
      }
  
      const classificationResult = await classifyMessageChainOfThought(message, context);
      console.log('Classification result:', classificationResult);
  
      if (classificationResult.type === 'create_representative' && classificationResult.confidence > 0.7) {
        const response = {
          type: 'open_representative_modal',
          message: "Have you created the agent or representative from the modal? Is there anything else I can help you with."
        };
  
        await conversationRef.set({
          userId: userId,
          messages: context.concat([
            { role: 'user', content: message, type: 'message' },
            { role: 'system', type: 'open_modal', message: response.message }
          ])
        }, { merge: true });
  
        return res.json(response);
      }
  
      // Process RAG response
      const relevantResults = await RAGService.searchAllCollections(message, userId);
      const enhancedPrompt = await RAGService.generatePromptWithContext(message, relevantResults);
      const aiResponse = await geminiService.generateResponse(enhancedPrompt, context);
  
      // Plot processing
      const plotSpecs = [];
      const plotData = [];
      const plotRegex = /```plot([\s\S]*?)```/g;
      let cleanMessage = aiResponse.content;
      let match;
      console.log('AI RESPONSE');
      console.log(aiResponse.content);
      while (match = plotRegex.exec(aiResponse.content)) {
        try {
          // Remove any inline comments (//...) from the plot spec string.
          const cleanSpecStr = match[1].replace(/\/\/.*(\n|$)/g, '');
          const spec = JSON.parse(cleanSpecStr);
          plotSpecs.push(spec);
          cleanMessage = cleanMessage.replace(match[0], '');
      
          let processedData;
          let labels;
          let datasetLabel = spec.title || `${spec.yField} vs ${spec.xField}`;
      
          // If the spec provides xField and yField as arrays, use them directly.
          if (Array.isArray(spec.xField) && Array.isArray(spec.yField)) {
            processedData = spec.xField.map((label, i) => ({
              x: label,
              y: spec.yField[i] !== undefined ? spec.yField[i] : 0
            }));
            labels = spec.xField;
          } else {
            const filteredData = relevantResults
              .filter(r => r.type === spec.dataSource)
              .map(r => r.originalData)
              .filter(d => Object.entries(spec.filters || {}).every(([key, value]) =>
                d[key]?.toString().toLowerCase() === value.toLowerCase()
              ));
      
            if (filteredData.length > 0) {
              switch (spec.aggregation) {
                case 'average':
                  processedData = [{
                    x: spec.xField,
                    y: filteredData.reduce((sum, d) => sum + parseFloat(d[spec.yField]), 0) / filteredData.length
                  }];
                  break;
                case 'sum':
                  processedData = [{
                    x: spec.xField,
                    y: filteredData.reduce((sum, d) => sum + parseFloat(d[spec.yField]), 0)
                  }];
                  break;
                case 'count':
                  processedData = [{
                    x: spec.xField,
                    y: filteredData.length
                  }];
                  break;
                default:
                  processedData = filteredData.map(d => ({
                    x: d[spec.xField],
                    y: parseFloat(d[spec.yField]),
                    raw: d
                  }));
              }
              // Filter out undefined labels
              labels = [...new Set(filteredData.map(d => d[spec.xField]).filter(label => label !== undefined))];
            }
          }
          console.log('PLOT DATA')
          console.log(plotData)
          // Only add the plot if both processedData and labels exist and labels is non-empty
          if (processedData && labels && labels.length > 0) {
            plotData.push({
              spec,
              data: processedData,
              labels,
              datasetLabel
            });
          }
        } catch (error) {
          console.error('Error processing plot spec:', error);
        }
      }
      
  
      // Update conversation context
      const newMessages = [
        ...context,
        { role: 'user', content: message, type: 'message' },
        { role: 'assistant', content: cleanMessage.trim(), type: 'message', plots: plotData }
      ];
  
      await conversationRef.update({ messages: newMessages });
  
      // Response with plot data
      res.json({
        type: 'response',
        message: cleanMessage.trim(),
        plots: plotData.map(p => ({
          type: p.spec.type,
          title: p.spec.title,
          data: {
            labels: p.labels,
            datasets: [{
              label: p.datasetLabel,
              data: p.data,
              backgroundColor: getChartColor(p.spec.type),
              borderColor: getBorderColor(p.spec.type),
              borderWidth: 2
            }]
          },
          options: {
            scales: {
              x: { title: { display: true, text: p.spec.xField } },
              y: { title: { display: true, text: p.spec.yField } }
            }
          }
        })),
        context: relevantResults.length > 0 ? {
          sources: relevantResults.map(r => r.type),
          topSimilarity: Math.max(...relevantResults.map(r => r.similarity))
        } : null
      });
  
    } catch (error) {
      console.error('Error processing message:', error);
      res.status(500).json({ error: 'Failed to process message', details: error.message });
    }
  });
  
  
  // Color helper functions
  const getChartColor = (type) => {
    return chartColors[type]?.bg || chartColors.default.bg;
  };
  
  const getBorderColor = (type) => {
    return chartColors[type]?.border || chartColors.default.border;
  };
  
  const chartColors = {
    line: { bg: 'rgba(54, 162, 235, 0.2)', border: 'rgba(54, 162, 235, 1)' },
    bar: { bg: 'rgba(255, 99, 132, 0.2)', border: 'rgba(255, 99, 132, 1)' },
    pie: { bg: ['#ff6384', '#36a2eb', '#cc65fe', '#ffce56'], border: '#fff' },
    default: { bg: 'rgba(75, 192, 192, 0.2)', border: 'rgba(75, 192, 192, 1)' }
  };
// Get conversation history
router.get('/history/:conversationId', verifyToken, async (req, res) => {
  try {
    const { conversationId } = req.params;
    const userId = req.user.id;

    const conversationRef = firestore.collection('conversations').doc(conversationId);
    const conversation = await conversationRef.get();

    if (!conversation.exists) {
      return res.status(404).json({ error: 'Conversation not found' });
    }

    const conversationData = conversation.data();
    if (conversationData.userId !== userId) {
      return res.status(403).json({ error: 'Unauthorized access' });
    }

    res.json(conversationData.messages);

  } catch (error) {
    console.error('Error fetching conversation history:', error);
    res.status(500).json({ error: 'Failed to fetch conversation history' });
  }
});
router.get('/history', verifyToken, async (req, res) => {
    try {
      const userId = req.user.id;
  
      // Query conversations where userId matches
      const conversationsRef = firestore.collection('conversations')
        .where('userId', '==', userId)
        .orderBy('createdAt', 'desc');
        
      const snapshot = await conversationsRef.get();
      
      const conversations = [];
      snapshot.forEach(doc => {
        conversations.push({
          id: doc.id,
          ...doc.data()
        });
      });
  
      res.json(conversations);
    } catch (error) {
      console.error('Error fetching conversations:', error);
      res.status(500).json({ error: 'Failed to fetch conversations' });
    }
  });
  
export default router;