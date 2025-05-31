// services/ai/workflowProcessor.js
import { GoogleGenerativeAI } from '@google/generative-ai';
import firestore from '../db/firestore.js';
import Papa from 'papaparse';  // Add this import

import integrationHandlers from '../workflow/integrationHandlers.js';
class WorkflowProcessor {
  constructor() {
    this.genAI = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY);
    this.model = this.genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });
    // ('WorkflowProcessor initialized.');
  }

  /**
   * Main entry point for processing a workflow step
   */
  async processWorkflowStep(instanceId, stepData, inputs) {
    // (`\n--- Starting workflow processing for Instance ID: ${instanceId} ---`);
    // (`Processing Step Index: ${stepData.stepIndex}, Step Title: "${stepData.title}"`);

    try {
      // Fetch workflow instance
    //   ('Fetching workflow instance data...');
      const instanceData = await this.getWorkflowInstance(instanceId);
      if (!instanceData) throw new Error('Workflow instance not found');
    //   ('Workflow instance data fetched successfully.');

      // Fetch workflow template
    //   ('Fetching workflow template data...');
      const templateData = await this.getWorkflowTemplate(instanceData.templateId);
    //   ('Workflow template data fetched successfully.');

      // Build context
    //   ('Building context for the current step...');
      const context = await this.buildStepContext(
        { ...instanceData, id: instanceId, template: templateData },
        stepData,
        inputs
      );
    //   ('Context built successfully.');

      // Process step
    //   ('Processing the current step using AI...');
      const result = await this.processStep(context);
    //   ('Step processed successfully.');

      // Save results
    //   ('Saving step results to Firestore...');
      // await this.saveStepResults(instanceId, stepData.stepIndex, result);
    //   ('Step results saved successfully.');

    //   (`--- Completed processing for Step "${stepData.title}" ---\n`);
      return result;
    } catch (error) {
      console.error('Workflow processing error:', error);
      throw error;
    }
  }

  /**
   * Fetch workflow instance from Firestore
   */
  async getWorkflowInstance(instanceId) {
    // (`Fetching workflow instance with ID: ${instanceId} from Firestore.`);
    const instanceRef = firestore.db.collection('workflow_instances').doc(instanceId);
    const instanceDoc = await instanceRef.get();
    if (!instanceDoc.exists) {
      console.warn(`Workflow instance with ID: ${instanceId} does not exist.`);
      return null;
    }
    (`Workflow instance with ID: ${instanceId} retrieved.`);
    return instanceDoc.data();
  }

  /**
   * Fetch workflow template from Firestore
   */
  async getWorkflowTemplate(templateId) {
    (`Fetching workflow template with ID: ${templateId} from Firestore.`);
    const templateDoc = await firestore.db.collection('workflow_templates')
      .doc(templateId)
      .get();
    if (!templateDoc.exists) {
      console.warn(`Workflow template with ID: ${templateId} does not exist.`);
      return null;
    }
    (`Workflow template with ID: ${templateId} retrieved.`);
    return templateDoc.data();
  }

  /**
   * Get step specific instructions from template configuration
   */
  getStepSpecificInstructions(context) {
    (`Generating step-specific instructions for Step Index: ${context.currentStep.index}`);
    // Get step configuration from template
    const stepConfig = context.currentStep.config || {};
    const templateConfig = context.template?.stepConfigs?.[context.currentStep.stepIndex] || {};

    // Combine template and step configs, with step config taking precedence
    const instructions = {
      prompt: stepConfig.prompt || templateConfig.prompt || '',
      requirements: stepConfig.requirements || templateConfig.requirements || [],
      outputFormat: stepConfig.outputFormat || templateConfig.outputFormat || {}
    };

    let finalInstructions = '\n\nStep Processing Instructions:';

    // Add custom prompt if provided
    if (instructions.prompt) {
      finalInstructions += `\n${instructions.prompt}`;
    }

    // Add requirements if any
    if (instructions.requirements.length > 0) {
      finalInstructions += '\n\nRequirements:';
      instructions.requirements.forEach(req => {
        finalInstructions += `\n- ${req}`;
      });
    }

    // Add output format if specified
    if (Object.keys(instructions.outputFormat).length > 0) {
      finalInstructions += '\n\nProvide output in this format:';
      finalInstructions += `\n${JSON.stringify(instructions.outputFormat, null, 2)}`;
    } else {
      // Default generic format if none specified
      finalInstructions += `\n\nProvide output in this format:
{
    "analysis": "your detailed analysis",
    "results": {
        "key_points": ["main points identified"],
        "findings": ["specific findings"],
        "recommendations": ["suggested actions"]
    }
}`;
    }

    ('Step-specific instructions generated.');
    return finalInstructions;
  }

  /**
   * Build context for the current step
   */
  async buildStepContext(instanceData, currentStep, inputs) {
    ('Building context for the workflow step...');
    // Get previous results
    ('Fetching previous step results...');
    const previousResults = await this.getPreviousStepResults(
      instanceData.id,
      currentStep.stepIndex
    );
    // console.log("Retrieved previous step(s).")
    // if (previousResults.length >= 0) {
    //   console.log(previousResults);
    // }

    // Process inputs for current step
    ('Processing inputs for the current step...');
    const processedInputs = await this.processInputs(inputs, currentStep.inputs);
    ('Inputs processed successfully.');

    // Build context
    const context = {
      workflowId: instanceData.id,
      workflowName: instanceData.template?.name || 'Custom Workflow',
      category: instanceData.template?.category || 'Custom',
      currentStep: {
        index: currentStep.stepIndex,
        title: currentStep.title,
        inputs: currentStep.inputs,
        description: inputs.text || currentStep.title, // Use text input or fall back to title
        config: currentStep.config || {}
      },
      previousSteps: previousResults,
      providedInputs: processedInputs
    };
    ('Context built.');
    return context;
  }
// async buildStepContext(instanceData, currentStep, inputs) {
//     ('Building context for the workflow step...');
//     // Get previous results
//     ('Fetching previous step results...');
//     const previousResults = await this.getPreviousStepResults(
//         instanceData.id,
//         currentStep.stepIndex
//     );
//     (`Retrieved ${previousResults.length} previous step(s).`);

//     // Process inputs for current step
//     ('Processing inputs for the current step...');
//     const processedInputs = await this.processInputs(inputs, currentStep.inputs);
    
//     // Ensure the step title is included in the context
//     const stepContext = {
//         title: currentStep.title,
//         description: currentStep.description || '',
//         inputText: processedInputs.text || currentStep.title, // Use title as fallback
//         previousStepResults: previousResults
//     };

//     // Build context
//     const context = {
//         workflowId: instanceData.id,
//         workflowName: instanceData.template?.name || 'Custom Workflow',
//         category: instanceData.template?.category || 'Custom',
//         currentStep: {
//             index: currentStep.stepIndex,
//             title: currentStep.title,
//             inputs: currentStep.inputs,
//             description: currentStep.description,
//             config: currentStep.config || {}
//         },
//         previousSteps: previousResults,
//         providedInputs: processedInputs,
//         stepContext: stepContext  // Include the new step context
//     };
//     ('Context built.');
//     return context;
// }
  /**
   * Process inputs for the current step
   */
  async processInputs(providedInputs, stepInputConfig) {
    ('Processing provided inputs based on step configuration...');
    if (!stepInputConfig) {
      stepInputConfig = this.getDefaultInputConfig();
      ('No step input configuration found. Using default configuration.');
    }

    const processed = {};

    if (stepInputConfig['file-upload'] && providedInputs.files?.length) {
      (`Processing ${providedInputs.files.length} file(s) uploaded.`);
      processed.files = await this.processFiles(providedInputs.files);
      ('File processing completed.');
    }

    if (stepInputConfig['text-input'] && providedInputs.text) {
      ('Processing text input.');
      processed.text = providedInputs.text;
      processed.textEmbedding = await this.generateEmbeddings(providedInputs.text);
      ('Text input processed and embeddings generated.');
    }

    if (stepInputConfig['text-area'] && providedInputs.textArea) {
      ('Processing text area input.');
      processed.textArea = providedInputs.textArea;
      processed.textAreaEmbedding = await this.generateEmbeddings(providedInputs.textArea);
      ('Text area input processed and embeddings generated.');
    }

    ('All inputs processed.');
    return processed;
  }

  /**
   * Process files
   */
  async processFiles(files) {
    ('Starting file processing...');
    return Promise.all(files.map(async file => {
      (`Processing file: ${file.originalname}`);
      const content = file.buffer.toString('utf-8');
      const parsedContent = await this.parseFileContent(content, file.mimetype);
      (`File "${file.originalname}" parsed as type "${parsedContent.type}".`);
      const contentEmbedding = await this.generateEmbeddings(content);
      (`Embeddings generated for file "${file.originalname}".`);
      
      return {
        name: file.originalname,
        type: file.mimetype,
        content,
        parsedContent,
        embedding: contentEmbedding
      };
    })).then(results => {
      ('All files processed successfully.');
      return results;
    }).catch(error => {
      console.error('Error during file processing:', error);
      throw error;
    });
  }

  /**
   * Parse file content based on mimetype
   */
  // async parseFileContent(content, mimetype) {
  //   (`Parsing file content with MIME type: ${mimetype}`);
  //   try {
  //     if (mimetype.includes('csv')) {
  //       ('Parsing CSV content.');
  //       const rows = content.split('\n').map(row => row.split(','));
  //       return { type: 'csv', data: rows };
  //     }

  //     if (mimetype.includes('json')) {
  //       ('Parsing JSON content.');
  //       return { type: 'json', data: JSON.parse(content) };
  //     }

  //     if (mimetype === 'text/plain' || mimetype.includes('pdf')) {
  //       ('Parsing plain text content.');
  //       return { type: 'text', data: content };
  //     }

  //     console.warn(`Unknown MIME type: ${mimetype}. Treating as text.`);
  //     return { type: 'unknown', data: content };
  //   } catch (error) {
  //     console.warn('File parsing warning:', error);
  //     return { type: 'text', data: content };
  //   }
  // }
  //workfing with sheet files
  async parseFileContent(content, mimetype) {
    try {
      if (mimetype.includes('csv')) {
        // Use PapaParse for robust CSV parsing
        const results = Papa.parse(content, {
          header: true,
          skipEmptyLines: true,
          dynamicTyping: true,
          fastMode: false,
        });
  
        // Transform into structured data with consistent headers
        const structuredData = results.data.map(row => {
          // Clean and normalize each row
          const cleanedRow = {};
          Object.entries(row).forEach(([key, value]) => {
            const cleanKey = key.trim().replace(/\s+/g, '_');
            cleanedRow[cleanKey] = value;
          });
          return cleanedRow;
        });
  
        // Create a formatted string representation for the AI
        const formattedRows = structuredData.map((row, index) => {
          return Object.entries(row)
            .map(([key, value]) => `${key.replace(/_/g, ' ')}: ${value}`)
            .join('\n');
        }).join('\n\n');
  
        return {
          type: 'structured_data',
          data: structuredData,
          rawText: formattedRows,
          format: 'csv'
        };
      }
  
      if (mimetype === 'text/plain' || mimetype.includes('pdf')) {
        return {
          type: 'text',
          data: content,
          rawText: content,
          format: 'text'
        };
      }
  
      return {
        type: 'unknown',
        data: content,
        rawText: content,
        format: 'text'
      };
    } catch (error) {
      console.error('File parsing error:', error);
      return {
        type: 'text',
        data: content,
        rawText: content,
        format: 'text'
      };
    }
  }
  
  /**
   * Generate embeddings for text content
   */
  async generateEmbeddings(text) {
    ('Generating embeddings for provided text.');
    if (!text) throw new Error('No text provided for embedding generation');

    const textBytes = new TextEncoder().encode(text).length;
    if (textBytes <= 8000) {
      ('Text size is within limit. Generating single embedding.');
      return await this.generateSingleEmbedding(text);
    } else {
      ('Text size exceeds limit. Processing large text.');
      return await this.processLargeText(text);
    }
  }

  /**
   * Generate embedding for a single piece of text
   */
  async generateSingleEmbedding(text) {
    ('Generating single embedding.');
    try {
      const embeddingModel = this.genAI.getGenerativeModel({ model: 'embedding-001' });
      const result = await embeddingModel.embedContent({
        content: { parts: [{ text }] }
      });

      if (!result?.embedding?.values) {
        throw new Error('Invalid embedding format received from model');
      }

      ('Single embedding generated successfully.');
      return result.embedding.values.map(val => Number(val));
    } catch (error) {
      console.error('Embedding generation error:', error);
      throw error;
    }
  }

  /**
   * Process large text in chunks
   */
  async processLargeText(text, options = {}) {
    const { chunkSize = 7500, overlapSize = 500 } = options;
    (`Splitting large text into chunks with chunkSize=${chunkSize} and overlapSize=${overlapSize}.`);
    const chunks = this.splitTextIntoChunks(text, chunkSize, overlapSize);
    (`Text split into ${chunks.length} chunk(s).`);

    ('Generating embeddings for all chunks.');
    const embeddings = await Promise.all(
      chunks.map(chunk => this.generateSingleEmbedding(chunk))
    );
    ('All chunk embeddings generated.');

    ('Combining embeddings.');
    return this.combineEmbeddings(embeddings);
  }

  /**
   * Split text into chunks with overlap
   */
  splitTextIntoChunks(text, chunkSize, overlapSize) {
    ('Splitting text into chunks...');
    const chunks = [];
    let startIndex = 0;

    while (startIndex < text.length) {
      let endIndex = startIndex + chunkSize;

      if (endIndex < text.length) {
        const breakPoints = [
          text.lastIndexOf('. ', endIndex),
          text.lastIndexOf('! ', endIndex),
          text.lastIndexOf('? ', endIndex),
          text.lastIndexOf('\n', endIndex)
        ];

        const validBreakPoints = breakPoints.filter(point =>
          point > startIndex && point < endIndex && point > endIndex - overlapSize
        );

        if (validBreakPoints.length > 0) {
          endIndex = Math.max(...validBreakPoints) + 1;
        }
      }

      const chunk = text.slice(startIndex, endIndex).trim();
      if (chunk.length > 0) {
        chunks.push(chunk);
      }
      startIndex = endIndex - overlapSize;
    }

    (`Text split into ${chunks.length} chunk(s).`);
    return chunks;
  }

  /**
   * Combine multiple embeddings into one
   */
  combineEmbeddings(embeddings) {
    ('Combining multiple embeddings into a single embedding.');
    if (embeddings.length === 0) throw new Error('No embeddings to combine');
    if (embeddings.length === 1) {
      ('Only one embedding present. Returning it directly.');
      return embeddings[0];
    }

    const dimension = embeddings[0].length;
    const combined = new Array(dimension).fill(0);
    const weights = this.calculateEmbeddingWeights(embeddings.length);
    ('Calculated embedding weights:', weights);

    for (let i = 0; i < embeddings.length; i++) {
      for (let j = 0; j < dimension; j++) {
        combined[j] += embeddings[i][j] * weights[i];
      }
    }

    ('Embeddings combined successfully.');
    return combined;
  }

  /**
   * Calculate weights for embedding combination
   */
  calculateEmbeddingWeights(length) {
    ('Calculating weights for embedding combination.');
    const weights = new Array(length).fill(0);
    const center = (length - 1) / 2;

    for (let i = 0; i < length; i++) {
      const distance = Math.abs(i - center);
      weights[i] = 1 - (distance / length) * 0.2;
    }

    const total = weights.reduce((sum, w) => sum + w, 0);
    const normalizedWeights = weights.map(w => w / total);
    ('Normalized weights:', normalizedWeights);
    return normalizedWeights;
  }

  /**
   * Process a single step
   */
  async processStep(context) {
    (`\n--- Processing Step "${context.currentStep.title}" ---`);
    try {
      // Build prompt
      ('Building AI prompt for the current step.');
      const prompt = await this.buildPrompt(context);
      console.log('AI prompt built successfully.');
      if(prompt){
        console.log(prompt)
      }
      // Generate content
      ('Sending prompt to AI model for content generation.');
      const result = await this.model.generateContent({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          temperature: 0.7,
          topP: 0.8,
          topK: 40,
          maxOutputTokens: 2000
        }
      });
      ('Content generated by AI model.');
      // (result.response.text())
      // Process response
      const response = result.response.text();
      console.log('Processing AI response.');
      console.log(response)
      const processedResponse = await this.processResponse(response, context);
      ('AI response processed successfully.');

      (`--- Completed Step "${context.currentStep.title}" ---\n`);
      return processedResponse;
    } catch (error) {
      console.error('Step processing error:', error);
      throw error;
    }
  }

  /**
   * Build prompt for the current step
   */
  // async buildPrompt(context) {
  //   ('Building prompt for AI.');
  //   const template = context.currentStep.config.promptTemplate || this.getDefaultPromptTemplate();
  //   const variables = {
  //     stepTitle: context.currentStep.title,
  //     workflowName: context.workflowName,
  //     category: context.category,
  //     description: context.currentStep.description,
  //     instructions: context.providedInputs.text,
  //     requirements: context.providedInputs.textArea,
  //     previousResults: context.previousSteps.map(step =>
  //       `${step.title}: ${step.result.raw || step.result}`
  //     ).join('\n')
  //   };

  //   let prompt = this.replaceTemplateVariables(template, variables);

  //   if (context.providedInputs.files) {
  //     ('Including provided files in the prompt.');
  //     prompt += '\n\nProvided files:\n';
  //     context.providedInputs.files.forEach(file => {
  //       prompt += `\nFile: ${file.name}\nContent:\n${file.content}\n`;
  //     });
  //   }

  //   if (context.currentStep.config.responseFormat) {
  //     ('Including response format instructions in the prompt.');
  //     prompt += `\n\nProvide response in this exact format:\n${
  //       JSON.stringify(context.currentStep.config.responseFormat, null, 2)
  //     }`;
  //   }

  //   // ('Prompt built:', prompt);
  //   return prompt;
  // }
  async buildPrompt(context) {
    const template = context.currentStep.config.promptTemplate || this.getDefaultPromptTemplate();
    const variables = {
      stepTitle: context.currentStep.title,
      workflowName: context.workflowName,
      category: context.category,
      description: context.currentStep.description,
      instructions: context.providedInputs.text,
      requirements: context.providedInputs.textArea,
      previousResults: context.previousSteps.map(step =>
        `${step.title}: ${step.result.raw || step.result}`
      ).join('\n')
    };
  
    let prompt = this.replaceTemplateVariables(template, variables);
  
    // Handle structured data files specially
    if (context.providedInputs.files) {
      const structuredDataFiles = context.providedInputs.files.filter(
        file => file.parsedContent?.type === 'structured_data'
      );
  
      const otherFiles = context.providedInputs.files.filter(
        file => file.parsedContent?.type !== 'structured_data'
      );
  
      // Add structured data with clear formatting
      if (structuredDataFiles.length > 0) {
        prompt += '\n\nStructured Data:\n';
        structuredDataFiles.forEach(file => {
          const data = file.parsedContent.data;
          
          // Add header section
          prompt += `\nFile: ${file.name}\n`;
          prompt += '---\n';
          
          // Add each record with clear separation
          data.forEach((record, index) => {
            prompt += `Record ${index + 1}:\n`;
            Object.entries(record).forEach(([key, value]) => {
              prompt += `${key.replace(/_/g, ' ')}: ${value}\n`;
            });
            prompt += '---\n';
          });
        });
      }
  
      // Add other files as before
      if (otherFiles.length > 0) {
        prompt += '\n\nAdditional Files:\n';
        otherFiles.forEach(file => {
          prompt += `\nFile: ${file.name}\nContent:\n${file.content}\n`;
        });
      }
    }
  
    return prompt;
  }
  /**
   * Replace template variables in prompt
   */
  replaceTemplateVariables(template, variables) {
    ('Replacing template variables in the prompt.');
    return template.replace(/\${(\w+)}/g, (match, key) =>
      variables[key] !== undefined ? variables[key] : match
    );
  }

  /**
   * Process and structure the response
   */
//   async processResponse(response, context) {
//     ('Structuring AI response.');
//     try {
//       if (context.currentStep.config.expectStructuredResponse) {
//         ('Expecting structured JSON response. Parsing response.');
//         const structured = JSON.parse(response);
//         ('Structured response parsed successfully.');
//         return { raw: response, structured, format: 'json' };
//       }
//       ('Expecting plain text response.');
//       return { raw: response, format: 'text' };
//     } catch (error) {
//       console.warn('Failed to parse response as JSON. Returning as plain text.');
//       return { raw: response, format: 'text' };
//     }
//   }
async processResponse(response, context) {
    ('Structuring AI response.');
    try {
      // Get embeddings from context if they exist
      const embeddings = context.providedInputs?.textEmbedding || 
                        context.providedInputs?.textAreaEmbedding ||
                        (context.providedInputs?.files?.[0]?.embedding) || [];
      // (embeddings)
      if (context.currentStep.config.expectStructuredResponse) {
        ('Expecting structured JSON response. Parsing response.');
        const structured = JSON.parse(response);
        ('Structured response parsed successfully.');
        return { raw: response, structured, format: 'json', embeddings };
      }
      ('Expecting plain text response.');
      return { raw: response, format: 'text', embeddings };
    } catch (error) {
      console.warn('Failed to parse response as JSON. Returning as plain text.');
      return { raw: response, format: 'text', embeddings: [] };
    }
}
  /**
   * Get previous step results
   */
  async getPreviousStepResults(instanceId, currentStepIndex) {
    ('Retrieving previous step results from Firestore.');
    const results = await firestore.db.collection('workflow_results')
      .where('instanceId', '==', instanceId)
      .where('stepIndex', '<', currentStepIndex)
      .orderBy('stepIndex')
      .get();

    // (`Found ${results.docs.length} previous step result(s).`);
    // console.log('GET PREVIOUS STEP RESULT')
    // console.log(results)
    return results.docs.map(doc => {
      const data = doc.data();
      return {
        stepIndex: data.stepIndex,
        title: data.title || '',
        result: data.outputs || data.result || ''
      };
    });
  }

  /**
   * Save step results to Firestore
   */
  async saveStepResults(instanceId, stepIndex, result) {
    (`Saving results for Step Index: ${stepIndex} to Firestore.`);
    
    const batch = firestore.db.batch();

    const resultRef = firestore.db.collection('workflow_results').doc();
    batch.set(resultRef, {
      instanceId,
      stepIndex,
      outputs: result,
      timestamp: new Date(),
    //   embeddings: result.embeddings
    });
    ('Step result document prepared for saving.');

    const instanceRef = firestore.db.collection('workflow_instances').doc(instanceId);
    batch.update(instanceRef, {
      lastCompletedStep: stepIndex,
      lastUpdated: new Date()
    });
    ('Workflow instance document prepared for updating.');

    try {
      await batch.commit();
      ('Step results saved and workflow instance updated successfully.');
    } catch (error) {
      console.error('Error saving step results to Firestore:', error);
      throw error;
    }
  }

  /**
   * Get default input configuration
   */
  getDefaultInputConfig() {
    ('Retrieving default input configuration.');
    return {
      'file-upload': false,
      'text-input': false,
      'text-area': false,
      'confirmation': false,
      'download': false
    };
  }

  /**
   * Get default prompt template
   */
  getDefaultPromptTemplate() {
    ('Retrieving default prompt template.');
    return `You are an AI assistant processing step "\${stepTitle}" of the \${workflowName} workflow.
  IMPORTANT: You must only use the exact values provided in the input data. Never Change the CURRENCY or the UNITS UNTILL EXPLICTLY ASKS. Each response must contain only the specific values found in the source data or calculations based on those exact values.
  
  NOTE: If the provided data (such as from a spreadsheet) contains multiple rows, you must handle each row. Do not omit or skip any row unless explicitly instructed.
  
  Current task: \${description}
  
  Instructions: \${instructions}
  Additional requirements: \${requirements}
  
  
  Previous steps results:
  \${previousResults}
  
  NOTE: IN THE OUTPUT PROVIDE THE STRUCTURED TABLE FORMAT RESPONSE WITH PROPER HEADERS AND DATA.
  NOTE: OUTPUT TABLE PRESERVE THE ORIGINAL TABLE CONTACT DETAILS LIKE EMAIL Or CONTACT NUMBER AND NAME THEM 'email' OR 'contact number'.
  Execute the task directly and provide results in the requested format. Do not explain steps or process.`;
  }
  
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

  // Add this method to your WorkflowProcessor class
async processStepWithIntegrations(instanceId, stepData, inputs) {
  try {
    console.log("processStepWithIntegrations")
    console.log(stepData, inputs)
    // First process the step normally
    const result = await this.processWorkflowStep(instanceId, stepData, inputs);
    console.log('RESULT')
    console.log(result)
    // Get workflow instance for user ID and integration config
    const instance = await this.getWorkflowInstance(instanceId);
    
    // Check for integrations in step data
    if (stepData.integrations?.length > 0) {
      // Process each integration
      const integrationPromises = stepData.integrations.map(async (integration) => {
        try {
          switch (integration.type) {
            case 'sheets':
              console.log("HITTING")
              return await integrationHandlers.handleGoogleSheets(
                instance.userId,
                result,
                integration.config
              );
            
            case 'docs':
              return await integrationHandlers.handleGoogleDocs(
                instance.userId,
                result,
                integration.config
              );
            case 'email': {
                let emailsFromTable = [];
                try {
                  const table = await this.parsePipeTable(result.raw);
                  
                  const possibleEmailHeaders = ['email', 'contact', 'email address'];
                  let emailColumnIndex = -1;
                  
                  table.headers.forEach((header, idx) => {
                    const lower = header.trim().toLowerCase();
                    if (possibleEmailHeaders.includes(lower)) {
                      emailColumnIndex = idx;
                    }
                  });
                  
                  if (emailColumnIndex !== -1) {
                    emailsFromTable = table.rows
                      .map(row => row[emailColumnIndex])
                      .filter(cell => cell && cell.includes('@'));
                  }
                } catch (err) {
                  console.warn('Could not parse table for emails:', err);
                }
              
                // Prepare the email config object with all required properties
                const emailConfig = {
                  recipients: integration.config.recipients || '', // Keep existing recipients from config
                  subject: integration.config.subject || 'Generated Report',
                  bodyTemplate: integration.config.bodyTemplate || result.raw // Use result as body if no template
                };
              
                // If we found emails in the table, add them to recipients
                if (emailsFromTable.length > 0) {
                  const allRecipients = [
                    ...(emailConfig.recipients ? emailConfig.recipients.split(',') : []),
                    ...emailsFromTable
                  ];
                  emailConfig.recipients = [...new Set(allRecipients)].join(',');
                }
              
                // Validate required fields
                if (!emailConfig.recipients) {
                  throw new Error('No recipients specified for email integration');
                }
                console.log('EMAIL RECIPIENETS')
                console.log(emailConfig)
                return await integrationHandlers.handleEmail(
                  instance.userId, // Pass the userId from instance
                  result,         // Pass the full step result
                  emailConfig     // Pass our prepared config with all required fields
                );
              }
              //OTher integration types here
            
            default:
              console.warn(`Unknown integration type: ${integration.type}`);
              return null;
          }
          
        } catch (integrationError) {
          console.error(`Integration error for ${integration.type}:`, integrationError);
          // Store integration error but don't fail the whole step
          await this.saveIntegrationError(instanceId, stepData.stepIndex, integration, integrationError);
          return null;
        }
      });

      // Wait for all integrations to complete
      const integrationResults = await Promise.allSettled(integrationPromises);
      
      // Add integration results to step result
      result.integrations = integrationResults.map((r, idx) => ({
        type: stepData.integrations[idx].type,
        status: r.status,
        result: r.status === 'fulfilled' ? r.value : r.reason.message
      }));
    }
    console.log('RESULT TO STORE')
    console.log(result)
    await this.saveStepResults(instanceId, stepData.stepIndex, result);

    return result;
  } catch (error) {
    console.error('Error processing step with integrations:', error);
    throw error;
  }
}

// Add this helper method
async saveIntegrationError(instanceId, stepIndex, integration, error) {
  try {
    await firestore.collection('workflow_integration_errors').add({
      instanceId,
      stepIndex,
      integrationType: integration.type,
      error: error.message,
      timestamp: new Date(),
      integration
    });
  } catch (dbError) {
    console.error('Error saving integration error:', dbError);
  }
}
}

export default new WorkflowProcessor();


// services/ai/workflowProcessor.js

// import { GoogleGenerativeAI } from '@google/generative-ai';
// import firestore from '../db/firestore.js';

// class WorkflowProcessor {
//   constructor() {
//     this.genAI = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY);
//     this.model = this.genAI.getGenerativeModel({ model: 'gemini-pro' });
//   }

//   /**
//    * Main entry point for processing a workflow step
//    */
//   async processWorkflowStep(instanceId, stepData, inputs) {
//     try {
//       // Fetch workflow instance
//       const instanceData = await this.getWorkflowInstance(instanceId);
//       if (!instanceData) throw new Error('Workflow instance not found');

//       // Fetch workflow template
//       const templateData = await this.getWorkflowTemplate(instanceData.templateId);
      
//       // Build context
//       const context = await this.buildStepContext(
//         { ...instanceData, id: instanceId, template: templateData },
//         stepData,
//         inputs
//       );

//       // Process step
//       const result = await this.processStep(context);

//       // Save results
//       await this.saveStepResults(instanceId, stepData.stepIndex, result);

//       return result;
//     } catch (error) {
//       console.error('Workflow processing error:', error);
//       throw error;
//     }
//   }

//   /**
//    * Fetch workflow instance from Firestore
//    */
//   async getWorkflowInstance(instanceId) {
//     const instanceRef = await firestore.db.collection('workflow_instances').doc(instanceId);
//     const instanceDoc = await instanceRef.get();
//     return instanceDoc.data();
//   }

//   /**
//    * Fetch workflow template from Firestore
//    */
//   async getWorkflowTemplate(templateId) {
//     const templateDoc = await firestore.db.collection('workflow_templates')
//       .doc(templateId)
//       .get();
//     return templateDoc.data();
//   }

//   /**
//  * Get step specific instructions from template configuration
//  */
// getStepSpecificInstructions(context) {
//     // Get step configuration from template
//     const stepConfig = context.currentStep.config || {};
//     const templateConfig = context.template?.stepConfigs?.[context.currentStep.stepIndex] || {};

//     // Combine template and step configs, with step config taking precedence
//     const instructions = {
//         prompt: stepConfig.prompt || templateConfig.prompt || '',
//         requirements: stepConfig.requirements || templateConfig.requirements || [],
//         outputFormat: stepConfig.outputFormat || templateConfig.outputFormat || {}
//     };

//     let finalInstructions = '\n\nStep Processing Instructions:';

//     // Add custom prompt if provided
//     if (instructions.prompt) {
//         finalInstructions += `\n${instructions.prompt}`;
//     }

//     // Add requirements if any
//     if (instructions.requirements.length > 0) {
//         finalInstructions += '\n\nRequirements:';
//         instructions.requirements.forEach(req => {
//             finalInstructions += `\n- ${req}`;
//         });
//     }

//     // Add output format if specified
//     if (Object.keys(instructions.outputFormat).length > 0) {
//         finalInstructions += '\n\nProvide output in this format:';
//         finalInstructions += `\n${JSON.stringify(instructions.outputFormat, null, 2)}`;
//     } else {
//         // Default generic format if none specified
//         finalInstructions += `\n\nProvide output in this format:
// {
//     "analysis": "your detailed analysis",
//     "results": {
//         "key_points": ["main points identified"],
//         "findings": ["specific findings"],
//         "recommendations": ["suggested actions"]
//     }
// }`;
//     }

//     return finalInstructions;
// }
//   /**
//    * Build context for the current step
//    */
//   async buildStepContext(instanceData, currentStep, inputs) {
//     // Get previous results
//     const previousResults = await this.getPreviousStepResults(
//       instanceData.id,
//       currentStep.stepIndex
//     );

//     // Process inputs for current step
//     const processedInputs = await this.processInputs(inputs, currentStep.inputs);

//     // Build context
//     return {
//       workflowId: instanceData.id,
//       workflowName: instanceData.template?.name || 'Custom Workflow',
//       category: instanceData.template?.category || 'Custom',
//       currentStep: {
//         index: currentStep.stepIndex,
//         title: currentStep.title,
//         inputs: currentStep.inputs,
//         description: currentStep.description,
//         config: currentStep.config || {}
//       },
//       previousSteps: previousResults,
//       providedInputs: processedInputs
//     };
//   }

//   /**
//    * Process inputs for the current step
//    */
//   async processInputs(providedInputs, stepInputConfig) {
//     if (!stepInputConfig) {
//       stepInputConfig = this.getDefaultInputConfig();
//     }

//     const processed = {};

//     if (stepInputConfig['file-upload'] && providedInputs.files?.length) {
//       processed.files = await this.processFiles(providedInputs.files);
//     }

//     if (stepInputConfig['text-input'] && providedInputs.text) {
//       processed.text = providedInputs.text;
//       processed.textEmbedding = await this.generateEmbeddings(providedInputs.text);
//     }

//     if (stepInputConfig['text-area'] && providedInputs.textArea) {
//       processed.textArea = providedInputs.textArea;
//       processed.textAreaEmbedding = await this.generateEmbeddings(providedInputs.textArea);
//     }

//     return processed;
//   }

//   /**
//    * Process files
//    */
//   async processFiles(files) {
//     return Promise.all(files.map(async file => {
//       const content = file.buffer.toString('utf-8');
//       const parsedContent = await this.parseFileContent(content, file.mimetype);
//       const contentEmbedding = await this.generateEmbeddings(content);

//       return {
//         name: file.originalname,
//         type: file.mimetype,
//         content,
//         parsedContent,
//         embedding: contentEmbedding
//       };
//     }));
//   }

//   /**
//    * Parse file content based on mimetype
//    */
//   async parseFileContent(content, mimetype) {
//     try {
//       if (mimetype.includes('csv')) {
//         const rows = content.split('\n').map(row => row.split(','));
//         return { type: 'csv', data: rows };
//       }
      
//       if (mimetype.includes('json')) {
//         return { type: 'json', data: JSON.parse(content) };
//       }

//       if (mimetype === 'text/plain' || mimetype.includes('pdf')) {
//         return { type: 'text', data: content };
//       }
      
//       return { type: 'unknown', data: content };
//     } catch (error) {
//       console.warn('File parsing warning:', error);
//       return { type: 'text', data: content };
//     }
//   }

//   /**
//    * Generate embeddings for text content
//    */
//   async generateEmbeddings(text) {
//     if (!text) throw new Error('No text provided for embedding generation');

//     const textBytes = new TextEncoder().encode(text).length;
//     return textBytes <= 8000 ? 
//       await this.generateSingleEmbedding(text) : 
//       await this.processLargeText(text);
//   }

//   /**
//    * Generate embedding for a single piece of text
//    */
//   async generateSingleEmbedding(text) {
//     try {
//       const embeddingModel = this.genAI.getGenerativeModel({ model: 'embedding-001' });
//       const result = await embeddingModel.embedContent({
//         content: { parts: [{ text }] }
//       });

//       if (!result?.embedding?.values) {
//         throw new Error('Invalid embedding format received from model');
//       }

//       return result.embedding.values.map(val => Number(val));
//     } catch (error) {
//       console.error('Embedding generation error:', error);
//       throw error;
//     }
//   }

//   /**
//    * Process large text in chunks
//    */
//   async processLargeText(text, options = {}) {
//     const { chunkSize = 7500, overlapSize = 500 } = options;
//     const chunks = this.splitTextIntoChunks(text, chunkSize, overlapSize);
    
//     const embeddings = await Promise.all(
//       chunks.map(chunk => this.generateSingleEmbedding(chunk))
//     );

//     return this.combineEmbeddings(embeddings);
//   }

//   /**
//    * Split text into chunks with overlap
//    */
//   splitTextIntoChunks(text, chunkSize, overlapSize) {
//     const chunks = [];
//     let startIndex = 0;

//     while (startIndex < text.length) {
//       let endIndex = startIndex + chunkSize;
      
//       if (endIndex < text.length) {
//         const breakPoints = [
//           text.lastIndexOf('. ', endIndex),
//           text.lastIndexOf('! ', endIndex),
//           text.lastIndexOf('? ', endIndex),
//           text.lastIndexOf('\n', endIndex)
//         ];

//         const validBreakPoints = breakPoints.filter(point => 
//           point > startIndex && point < endIndex && point > endIndex - overlapSize
//         );

//         if (validBreakPoints.length > 0) {
//           endIndex = Math.max(...validBreakPoints) + 1;
//         }
//       }

//       chunks.push(text.slice(startIndex, endIndex).trim());
//       startIndex = endIndex - overlapSize;
//     }

//     return chunks;
//   }

//   /**
//    * Combine multiple embeddings into one
//    */
//   combineEmbeddings(embeddings) {
//     if (embeddings.length === 0) throw new Error('No embeddings to combine');
//     if (embeddings.length === 1) return embeddings[0];

//     const dimension = embeddings[0].length;
//     const combined = new Array(dimension).fill(0);
//     const weights = this.calculateEmbeddingWeights(embeddings.length);
    
//     for (let i = 0; i < embeddings.length; i++) {
//       for (let j = 0; j < dimension; j++) {
//         combined[j] += embeddings[i][j] * weights[i];
//       }
//     }

//     return combined;
//   }

//   /**
//    * Calculate weights for embedding combination
//    */
//   calculateEmbeddingWeights(length) {
//     const weights = new Array(length).fill(0);
//     const center = (length - 1) / 2;
    
//     for (let i = 0; i < length; i++) {
//       const distance = Math.abs(i - center);
//       weights[i] = 1 - (distance / length) * 0.2;
//     }
    
//     const total = weights.reduce((sum, w) => sum + w, 0);
//     return weights.map(w => w / total);
//   }

//   /**
//    * Process a single step
//    */
//   async processStep(context) {
//     try {
//       // Build prompt
//       const prompt = await this.buildPrompt(context);

//       // Generate content
//       const result = await this.model.generateContent({
//         contents: [{ parts: [{ text: prompt }] }],
//         generationConfig: {
//           temperature: 0.7,
//           topP: 0.8,
//           topK: 40,
//           maxOutputTokens: 2000
//         }
//       });

//       // Process response
//       const response = result.response.text();
//       return await this.processResponse(response, context);
//     } catch (error) {
//       console.error('Step processing error:', error);
//       throw error;
//     }
//   }

//   /**
//    * Build prompt for the current step
//    */
//   async buildPrompt(context) {
//     const template = context.currentStep.config.promptTemplate || this.getDefaultPromptTemplate();
//     const variables = {
//       stepTitle: context.currentStep.title,
//       workflowName: context.workflowName,
//       category: context.category,
//       description: context.currentStep.description,
//       instructions: context.providedInputs.text,
//       requirements: context.providedInputs.textArea,
//       previousResults: context.previousSteps.map(step => 
//         `${step.title}: ${step.result.raw || step.result}`
//       ).join('\n')
//     };

//     let prompt = this.replaceTemplateVariables(template, variables);

//     if (context.providedInputs.files) {
//       prompt += '\n\nProvided files:\n';
//       context.providedInputs.files.forEach(file => {
//         prompt += `\nFile: ${file.name}\nContent:\n${file.content}\n`;
//       });
//     }

//     if (context.currentStep.config.responseFormat) {
//       prompt += `\n\nProvide response in this exact format:\n${
//         JSON.stringify(context.currentStep.config.responseFormat, null, 2)
//       }`;
//     }

//     return prompt;
//   }

//   /**
//    * Replace template variables in prompt
//    */
//   replaceTemplateVariables(template, variables) {
//     return template.replace(/\${(\w+)}/g, (match, key) => 
//       variables[key] !== undefined ? variables[key] : match
//     );
//   }

//   /**
//    * Process and structure the response
//    */
//   async processResponse(response, context) {
//     try {
//       // First try to parse as structured JSON
//       const structured = JSON.parse(response);
      
//       // Enhance the response with metadata
//       const enhancedResponse = {
//         raw: response,
//         structured,
//         format: 'json',
//         metadata: {
//           timestamp: new Date(),
//           stepIndex: context.currentStep.index,
//           stepTitle: context.currentStep.title,
//           workflowProgress: {
//             currentStep: context.currentStep.index + 1,
//             totalStepsCompleted: context.previousSteps.length + 1
//           }
//         },
//         summary: {
//           status: this.determineStepStatus(structured),
//           criticalFindings: this.extractCriticalFindings(structured),
//           actionRequired: this.determineIfActionRequired(structured)
//         }
//       };

//       return enhancedResponse;
//     } catch (error) {
//       // If parsing fails, create a structured format from the text
//       return this.createStructuredResponse(response, context);
//     }
//   }

//   /**
//    * Get previous step results
//    */
//   async getPreviousStepResults(instanceId, currentStepIndex) {
//     const results = await firestore.db.collection('workflow_results')
//       .where('instanceId', '==', instanceId)
//       .where('stepIndex', '<', currentStepIndex)
//       .orderBy('stepIndex')
//       .get();
    
//     return results.docs.map(doc => {
//       const data = doc.data();
//       return {
//         stepIndex: data.stepIndex,
//         title: data.title || '',
//         result: data.outputs || data.result || ''
//       };
//     });
//   }

//   /**
//    * Save step results to Firestore
//    */
//   async saveStepResults(instanceId, stepIndex, result) {
//     const batch = firestore.db.batch();
    
//     const resultRef = firestore.db.collection('workflow_results').doc();
//     batch.set(resultRef, {
//       instanceId,
//       stepIndex,
//       outputs: result,
//       timestamp: new Date(),
//       embeddings: result.embeddings
//     });
    
//     const instanceRef = firestore.db.collection('workflow_instances').doc(instanceId);
//     batch.update(instanceRef, {
//       lastCompletedStep: stepIndex,
//       lastUpdated: new Date()
//     });
    
//     await batch.commit();
//   }

//   /**
//    * Get default input configuration
//    */
//   getDefaultInputConfig() {
//     return {
//       'file-upload': false,
//       'text-input': false,
//       'text-area': false,
//       'confirmation': false,
//       'download': false
//     };
//   }

//   /**
//    * Get default prompt template
//    */
//   getDefaultPromptTemplate() {
//     return `You are an AI assistant processing step "\${stepTitle}" of the \${workflowName} workflow.

// Current task: \${description}

// Instructions: \${instructions}
// Additional requirements: \${requirements}

// Previous steps results:
// \${previousResults}

// Analyze the task and provide a comprehensive response including:
// 1. Direct execution of the requested task
// 2. Analysis of the current state and implications
// 3. Connection to previous steps if applicable
// 4. Specific recommendations for next steps
// 5. Potential risks or areas needing attention

// Provide your response in the following structured format:
// {
//   "currentOutput": {
//     "result": "Direct result of the requested task",
//     "format": "Format of the result (text, json, etc.)"
//   },
//   "analysis": {
//     "overview": "Brief overview of what was accomplished",
//     "keyFindings": ["List of key findings"],
//     "implications": ["Important implications of these results"]
//   },
//   "context": {
//     "previousStepsImpact": "How this relates to previous steps",
//     "workflowProgress": "Current progress in overall workflow"
//   },
//   "recommendations": {
//     "nextSteps": ["Specific recommended next steps"],
//     "improvements": ["Suggested improvements"],
//     "risks": ["Potential risks to address"]
//   }
// }`;
//   }

//   determineStepStatus(structured) {
//     // Analyze the structured output to determine step status
//     const hasErrors = structured.recommendations?.risks?.length > 0;
//     const hasWarnings = structured.analysis?.implications?.some(imp => 
//       imp.toLowerCase().includes('warning') || imp.toLowerCase().includes('concern')
//     );

//     if (hasErrors) return 'needs_attention';
//     if (hasWarnings) return 'completed_with_warnings';
//     return 'completed_successfully';
//   }
//   extractCriticalFindings(structured) {
//     // Extract critical findings from the response
//     const criticalFindings = [];

//     if (structured.analysis?.keyFindings) {
//       criticalFindings.push(...structured.analysis.keyFindings.filter(finding =>
//         finding.toLowerCase().includes('critical') || 
//         finding.toLowerCase().includes('important') ||
//         finding.toLowerCase().includes('urgent')
//       ));
//     }

//     if (structured.recommendations?.risks) {
//       criticalFindings.push(...structured.recommendations.risks);
//     }

//     return criticalFindings;
//   }
//   determineIfActionRequired(structured) {
//     // Determine if immediate action is required based on the response
//     const hasUrgentRecommendations = structured.recommendations?.nextSteps?.some(step =>
//       step.toLowerCase().includes('immediately') ||
//       step.toLowerCase().includes('urgent') ||
//       step.toLowerCase().includes('required')
//     );

//     const hasHighRisks = structured.recommendations?.risks?.some(risk =>
//       risk.toLowerCase().includes('critical') ||
//       risk.toLowerCase().includes('high') ||
//       risk.toLowerCase().includes('severe')
//     );

//     return hasUrgentRecommendations || hasHighRisks;
//   }
//   async createStructuredResponse(textResponse, context) {
//     // Create a structured format from unstructured text
//     return {
//       raw: textResponse,
//       format: 'text',
//       structured: {
//         currentOutput: {
//           result: textResponse,
//           format: 'text'
//         },
//         analysis: {
//           overview: 'Unstructured text response provided',
//           keyFindings: ['Response was not in expected format'],
//           implications: ['May need to review prompt format']
//         },
//         context: {
//           previousStepsImpact: 'Unable to determine from unstructured response',
//           workflowProgress: `Step ${context.currentStep.index + 1} completed`
//         },
//         recommendations: {
//           nextSteps: ['Review response format requirements'],
//           improvements: ['Ensure prompt specifies structured output format'],
//           risks: ['Unstructured response may impact workflow analysis']
//         }
//       },
//       metadata: {
//         timestamp: new Date(),
//         stepIndex: context.currentStep.index,
//         stepTitle: context.currentStep.title,
//         workflowProgress: {
//           currentStep: context.currentStep.index + 1,
//           totalStepsCompleted: context.previousSteps.length + 1
//         }
//       }
//     };
//   }
// }

// export default new WorkflowProcessor();