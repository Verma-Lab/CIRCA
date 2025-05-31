// routes/workflow.js
import express from 'express';
import multer from 'multer';
import { verifyToken } from '../middleware/auth.js';
import workflowProcessor from '../services/ai/workflowProcessor.js';
import firestore from '../services/db/firestore.js';
import { createRequire } from 'module';
import integrationHandlers from '../services/workflow/integrationHandlers.js';
import { sheets } from 'googleapis/build/src/apis/sheets/index.js';
import Papa from 'papaparse';  // Add this import

const require = createRequire(import.meta.url);
const pdfParse = require('pdf-parse');
const PDFDocument = require('pdfkit');
const router = express.Router();
const upload = multer({ storage: multer.memoryStorage() });

// Template Management Routes
router.post('/templates', verifyToken, async (req, res) => {
  try {
    const { name, category, steps, assistantId } = req.body;
    const templateData = {
      name,
      category,
      steps,
      assistantId,
      creatorId: req.user.id,
      status: 'active',
      createdAt: new Date()
    };

    const template = await firestore.createWorkflowTemplate(templateData);
    res.json(template);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/templates/:assistantId', verifyToken, async (req, res) => {
  try {
    const { assistantId } = req.params;
    const templates = await firestore.getWorkflowTemplates(assistantId);
    console.log('TEMPLATES')
    console.log(templates)
    res.json(templates);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.put('/templates/:templateId', verifyToken, async (req, res) => {
  try {
    const { templateId } = req.params;
    const updates = {
      ...req.body,
      updatedAt: new Date()
    };

    const template = await firestore.updateTemplate(templateId, updates);
    res.json(template);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.delete('/templates/:templateId', verifyToken, async (req, res) => {
  try {
    const { templateId } = req.params;
    await firestore.updateTemplate(templateId, {
      status: 'deleted',
      deletedAt: new Date()
    });
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Workflow Instance Routes
router.post('/instances', verifyToken, async (req, res) => {
  try {
    const { templateId, assistantId, name } = req.body;
    
    // Get template data
    const template = await firestore.getWorkflowTemplate(templateId);
    if (!template) {
      return res.status(404).json({ error: 'Template not found' });
    }

    // Create workflow instance
    const instanceData = {
      templateId,
      assistantId,
      name,
      userId: req.user.id,
      steps: template.steps,
      status: 'created',
      currentStep: 0,
      createdAt: new Date()
    };

    const instance = await firestore.createWorkflowInstance(instanceData);
    res.json(instance);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/instances/:instanceId', verifyToken, async (req, res) => {
  try {
    const { instanceId } = req.params;
    const [instance, results] = await Promise.all([
      firestore.getWorkflowInstance(instanceId),
      firestore.getWorkflowResults(instanceId)
    ]);

    if (!instance) {
      return res.status(404).json({ error: 'Workflow instance not found' });
    }

    res.json({
      instance,
      results
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Step Processing Routes
// router.post(
//     '/instances/:instanceId/steps/:stepIndex',
//     verifyToken,
//     upload.array('files'),
//     async (req, res) => {
//       try {
//         const { instanceId, stepIndex } = req.params;
//         const { text, textArea } = req.body;
//         const integrations = req.body.integrations ? JSON.parse(req.body.integrations) : [];
//         const files = req.files;
  
//         // Get workflow instance
//         const instance = await firestore.getWorkflowInstance(instanceId);
//         if (!instance) {
//           return res.status(404).json({ error: 'Workflow instance not found' });
//         }
  
//         const stepIdx = parseInt(stepIndex, 10);
  
//         // Instead of strictly requiring stepIdx === currentStep,
//         // allow stepIdx to be at or 1 ahead of currentStep.
//         if (stepIdx < instance.currentStep) {
//           // If user is trying to "redo" an already completed step, decide how to handle:
//           // Option A: Return an error or info message
//           return res.status(400).json({
//             error: 'Step already completed',
//             message: `Cannot process step ${stepIdx}, it is behind the current step ${instance.currentStep}.`,
//           });
  
//           // Option B: Alternatively, ignore it or reprocess. Depends on your business logic.
//         } else if (stepIdx > instance.currentStep) {
//           // If the front-end jumped to the next step without the
//           // backend finishing the previous step, we can auto-advance:
//           // "Automatically complete/advance all intermediate steps."
//           // For a single step difference, for example:
//           if (stepIdx === instance.currentStep + 1) {
//             // Mark the previous step as completed so the instance can move on  
//             await firestore.updateWorkflowStep(instanceId, instance.currentStep, {
//               status: 'completed',
//               completedAt: new Date().toISOString(),
//             });
//           } else {
//             // They skipped more than one step? Decide if you allow that or error out
//             return res.status(400).json({
//               error: 'Step out of sequence',
//               message: `Cannot process step ${stepIdx}. Current step is ${instance.currentStep}, 
//                         and skipping multiple steps is not allowed.`,
//             });
//           }
//         }
  
//         // Now, instance.currentStep might still be old in memory, so re-fetch or handle carefully
//         // After auto-advancing, the instance doc in Firestore should have currentStep = stepIdx
//         // if updateWorkflowStep advanced it. Otherwise, we can forcibly set it, but let's just re-fetch:
//         const updatedInstance = await firestore.getWorkflowInstance(instanceId);
  
//         // Process step
//         const processedFiles = await Promise.all(files.map(async file => {
//             if (file.mimetype === 'application/pdf') {
//               const dataBuffer = file.buffer;
//               console.log(' WE ARE PARSING IT AS A PDF')
//               try {
//                 const pdfData = await pdfParse(dataBuffer);
//                 return {
//                   ...file,
//                   buffer: Buffer.from(pdfData.text),
//                   originalContent: file.buffer,
//                   mimetype: 'text/plain',
//                   parsedPdf: true
//                 };
//               } catch (error) {
//                 console.error('PDF parsing error:', error);
//                 return file; // Return original file if parsing fails
//               }
//             }
//             return file;
//           }));

//         // const result = await workflowProcessor.processWorkflowStep(
//         //   instanceId,
//         //   {
//         //     /* If steps changed, use updatedInstance */
//         //     ...updatedInstance.steps[stepIdx],
//         //     stepIndex: stepIdx,
//         //   },
//         //   {
//         //     files: processedFiles,
//         //     text,
//         //     textArea,
//         //   }
//         // );
//         const result = await workflowProcessor.processStepWithIntegrations(
//           instanceId,
//           {
//             ...updatedInstance.steps[stepIdx],
//             stepIndex: stepIdx,
//             integrations // Pass the integrations configuration
//           },
//           {
//             files: processedFiles,
//             text,
//             textArea,
//             integrations
//           }
//         );
  
//         // Update step status and save results
//         // const [updatedStep, savedResults] = await Promise.all([
//         //   firestore.updateWorkflowStep(instanceId, stepIdx, {
//         //     status: 'completed',
//         //     completedAt: new Date().toISOString(),
//         //     results: result,
//         //   }),
//         //   firestore.saveWorkflowResults({
//         //     instanceId,
//         //     stepIndex: stepIdx,
//         //     outputs: result,
//         //     createdAt: new Date().toISOString(),
//         //   }),
//         // ]);
  
//         // Update step status and save results
//       const [updatedStep, savedResults] = await Promise.all([
//         firestore.updateWorkflowStep(instanceId, stepIdx, {
//           status: 'completed',
//           completedAt: new Date().toISOString(),
//           results: result,
//           integrationResults: result.integrations || [] // Save integration results
//         }),
//         firestore.saveWorkflowResults({
//           instanceId,
//           stepIndex: stepIdx,
//           outputs: result,
//           integrations: result.integrations || [], // Save integration results
//           createdAt: new Date().toISOString()
//         })
//       ]);
//         // Return complete response
//   //       res.json({
//   //         result,
//   //         currentStep: updatedStep.currentStep,
//   //         nextStep:
//   //           stepIdx < updatedInstance.steps.length - 1 ? stepIdx + 1 : null,
//   //         isComplete: stepIdx === updatedInstance.steps.length - 1,
//   //         stepStatus: 'completed',
//   //       });
//   //     } catch (error) {
//   //       console.error('Step processing error:', error);
//   //       res.status(500).json({
//   //         error: error.message,
//   //         details: 'Error processing workflow step',
//   //       });
//   //     }
//   //   }
//   // );
//     // Return complete response
//     res.json({
//       result,
//       currentStep: updatedStep.currentStep,
//       nextStep: stepIdx < updatedInstance.steps.length - 1 ? stepIdx + 1 : null,
//       isComplete: stepIdx === updatedInstance.steps.length - 1,
//       stepStatus: 'completed',
//       integrationResults: result.integrations || []
//     });
//   } catch (error) {
//     console.error('Step processing error:', error);
//     res.status(500).json({
//       error: error.message,
//       details: 'Error processing workflow step'
//     });
//   }
// }
// );

const chunkArray = (array, chunkSize = 1000) => {
  const chunks = [];
  for (let i = 0; i < array.length; i += chunkSize) {
    chunks.push(array.slice(i, i + chunkSize));
  }
  return chunks;
};

// Process large sheets data
async function processLargeSheetData(readResult) {
  if (!readResult?.readData) return null;
  
  const { headers, data } = readResult.readData;
  const MAX_CHUNK_SIZE = 1000; // Process 1000 rows at a time
  
  // Split data into chunks
  const dataChunks = chunkArray(data, MAX_CHUNK_SIZE);
  const processedChunks = [];
  
  // Process each chunk
  for (const chunk of dataChunks) {
    const rows = chunk.map(row => 
      headers.map(header => 
        row[header.replace(/[^a-zA-Z0-9]/g, '_')] || ''
      ).join(',')
    );
    
    const flattened = [headers.join(','), ...rows].join('\n');
    
    processedChunks.push({
      fieldname: 'files',
      originalname: `sheet-data-chunk-${processedChunks.length + 1}.csv`,
      mimetype: 'text/csv',
      buffer: Buffer.from(flattened),
      content: flattened,
      metadata: {
        totalRows: data.length,
        chunkSize: chunk.length,
        chunkNumber: processedChunks.length + 1,
        totalChunks: Math.ceil(data.length / MAX_CHUNK_SIZE)
      }
    });
  }
  
  return processedChunks;
}
// Utility to handle CSV parsing and formatting
const parseCSVContent = (content) => {
  // Remove markdown code blocks if present
  const cleanContent = content.replace(/```csv\n|```/g, '').trim();
  
  // Parse CSV content
  return Papa.parse(cleanContent, {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: true
  });
};

// Convert parsed CSV data to structured format
const convertToStructuredFormat = (parsedData) => {
  if (!parsedData?.data || !Array.isArray(parsedData.data)) return null;

  const headers = parsedData.meta.fields || [];
  const data = parsedData.data.map(row => {
    const cleanRow = {};
    headers.forEach(header => {
      cleanRow[header] = row[header] ?? '';
    });
    return cleanRow;
  });

  return {
    headers,
    data,
    originalFormat: 'csv'
  };
};

// Process workflow results for either table or PDF
const processWorkflowResults = (results) => {
  if (!Array.isArray(results)) return null;

  const processedResults = results.map(result => {
    const outputs = result.outputs || {};
    let content = outputs.raw || '';

    // Parse CSV content if present
    if (content.includes('csv')) {
      const parsedCSV = parseCSVContent(content);
      return {
        ...result,
        structuredData: convertToStructuredFormat(parsedCSV)
      };
    }

    return result;
  });

  return processedResults;
};
router.post(
  '/instances/:instanceId/steps/:stepIndex',
  verifyToken,
  upload.array('files'),
  async (req, res) => {
    try {
      const { instanceId, stepIndex } = req.params;
      const { text, textArea } = req.body;
      const integrations = req.body.integrations ? JSON.parse(req.body.integrations) : [];
      const files = req.files;
      console.log("REQ")
      console.log(req.body)
      // 1) Fetch the instance
      const instance = await firestore.getWorkflowInstance(instanceId);
      if (!instance) {
        return res.status(404).json({ error: 'Workflow instance not found' });
      }
      const stepIdx = parseInt(stepIndex, 10);

      // 2) Enforce step ordering logic
      //   (same as you have above)
      if (stepIdx < instance.currentStep) {
        return res.status(400).json({
          error: 'Step already completed',
          message: `Cannot process step ${stepIdx}, it is behind the current step ${instance.currentStep}.`,
        });
      } else if (stepIdx > instance.currentStep) {
        if (stepIdx === instance.currentStep + 1) {
          // auto-advance
          await firestore.updateWorkflowStep(instanceId, instance.currentStep, {
            status: 'completed',
            completedAt: new Date().toISOString(),
          });
        } else {
          // skipping multiple steps not allowed
          return res.status(400).json({
            error: 'Step out of sequence',
            message: `Cannot process step ${stepIdx}. Current step is ${instance.currentStep}.`,
          });
        }
      }
      const updatedInstance = await firestore.getWorkflowInstance(instanceId);

      // 3) Check for "fetch_and_use" integrations (or any read logic)
      let mergedText = text || '';
      let mergedTextArea = textArea || '';
      let processedFiles = []; // Initialize processedFiles array here
      console.log("INTEGRATIONS", integrations)
      if (integrations && integrations.length > 0) {
        for (const integration of integrations) {
          console.log('INTEGRATION TYPE', integration)
          if (integration.type === 'sheets' && integration.config?.mode === 'fetch_and_use') {
            // read data from that sheet
            const userId = updatedInstance.userId;
            const readResult = await integrationHandlers.handleGoogleSheets(
              userId,
              null, // we pass null for stepResult because we're reading, not writing
              integration.config
            );
            if (readResult?.readData) {
              // Convert the new format back to a string
              const headers = readResult.readData.headers.join(',');
              const rows = readResult.readData.data.map(row => 
                readResult.readData.headers.map(header => 
                  // Replace spaces and special characters to match the cleaned headers
                  row[header.replace(/[^a-zA-Z0-9]/g, '_')] || ''
                ).join(',')
              );
              
              const flattened = [headers, ...rows].join('\n');
                // Create virtual file and add to processedFiles instead of mergedText
                processedFiles.push({
                  fieldname: 'files',
                  originalname: 'sheet-data.csv',
                  mimetype: 'text/csv',
                  buffer: Buffer.from(flattened),
                  content: flattened
                });
        
                console.log("SHEET DATA")
                console.log(flattened)

              // // Append to the text
              // console.log("SHEET DATA")
              // console.log(flattened)
              // mergedText += `\n---\nSheet Data:\n${flattened}`;
            }
          }

          // Handle Google Docs
          if (integration.type === 'docs' && integration.config?.mode === 'fetch_and_use') {
            console.log('HANDLING GOOGLE DOCS')
            const userId = updatedInstance.userId;
            const readResult = await integrationHandlers.handleGoogleDocs(
              userId,
              null, // No stepResult when fetching
              integration.config
            );

            if (readResult?.readData) {
              const flattened = readResult.readData; // Extracted text
              console.log('DOCS PARSED DATA')
              console.log(flattened)
              // Create virtual file and add to processedFiles
              processedFiles.push({
                fieldname: 'files',
                originalname: 'doc-data.txt',
                mimetype: 'text/plain',
                buffer: Buffer.from(flattened),
                content: flattened
              });

              console.log("DOC DATA", flattened);
            }
          }
        }
      }

      // 4) Process PDF files if any
      if (files?.length) {
        const pdfFiles = await Promise.all(files.map(async file => {
          if (file.mimetype === 'application/pdf') {
            const dataBuffer = file.buffer;
            try {
              const pdfData = await pdfParse(dataBuffer);
              return {
                ...file,
                buffer: Buffer.from(pdfData.text),
                originalContent: file.buffer,
                mimetype: 'text/plain',
                parsedPdf: true
              };
            } catch (error) {
              console.error('PDF parsing error:', error);
              return file; // fallback
            }
          }
          return file;
        }));
        processedFiles = [...processedFiles, ...pdfFiles];
      }
    
      // 5) Finally, call the AI processor 
      const result = await workflowProcessor.processStepWithIntegrations(
        instanceId,
        {
          ...updatedInstance.steps[stepIdx],
          stepIndex: stepIdx,
          integrations
        },
        {
          files: processedFiles ,
          text: mergedText,
          textArea: mergedTextArea,
          integrations
        }
      );
      console.log('RESULT TO CREATE TABLE')
      console.log(result)
//       const isFinalStep = (stepIdx === updatedInstance.steps.length - 1);

// if (isFinalStep) {  // Only create sheet if both conditions are true
//     console.log('CREATING STRUCTURED TABLE');
//     const userId = updatedInstance.userId;
    
//     // Process result to structured format
//     const processedResult = processWorkflowResults([result])[0];
    
//     // Create sheet with structured data
//     await integrationHandlers.handleGoogleSheets(
//         userId,
//         processedResult,
//         { mode: 'create_new' }
//     );
// }

      // 6) Update step, save results, return response
      console.log('COMPLETED', stepIndex)
      const [updatedStep, savedResults] = await Promise.all([
        firestore.updateWorkflowStep(instanceId, stepIdx, {
          status: 'completed',
          completedAt: new Date().toISOString(),
          results: result,
          integrationResults: result.integrations || []
        }),
        firestore.saveWorkflowResults({
          instanceId,
          stepIndex: stepIdx,
          outputs: result,
          integrations: result.integrations || [],
          createdAt: new Date().toISOString()
        })
      ]);

      return res.json({
        result,
        currentStep: updatedStep.currentStep,
        nextStep: stepIdx < updatedInstance.steps.length - 1 ? stepIdx + 1 : null,
        isComplete: stepIdx === updatedInstance.steps.length - 1,
        stepStatus: 'completed',
        integrationResults: result.integrations || []
      });
    } catch (error) {
      console.error('Step processing error:', error);
      res.status(500).json({
        error: error.message,
        details: 'Error processing workflow step'
      });
    }
  }
);

// NEW: Dedicated route to fetch results only
router.get('/instances/:instanceId/results', verifyToken, async (req, res) => {
    try {
    const { instanceId } = req.params;
    
    // 1. Fetch the workflow instance so we know how many steps there are 
    const instance = await firestore.getWorkflowInstance(instanceId);
    if (!instance) {
      return res.status(404).json({ error: 'Workflow instance not found' });
    }
    
    // 2. Fetch all saved results from workflow_results in ascending order
    const results = await firestore.getWorkflowResults(instanceId);
    
    // 3. Determine if the workflow is completed or not
    let finalGrade = null;
    if (instance.status === 'completed' && instance.steps?.length) {
      // Last step index
      const lastStepIndex = instance.steps.length - 1;
      // Find final step result
      const finalStepDoc = results.find(
        (r) => r.stepIndex === lastStepIndex
      );
      if (finalStepDoc && finalStepDoc.outputs) {
        // For example, if the final outputs contain a grade or grading data:
        finalGrade = finalStepDoc.outputs;
      }
    }
    
    return res.json({
      instance,
      results,      // All step results 
      finalGrade,   // The final step's outputs (if workflow is completed)
    });
    } catch (error) {
    res.status(500).json({ error: error.message });
    }
    });
// Analytics Routes
router.get('/instances/:instanceId/analytics', verifyToken, async (req, res) => {
  try {
    const { instanceId } = req.params;
    const analytics = await firestore.getWorkflowAnalytics(instanceId);
    res.json(analytics);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Bulk Operations
router.post('/templates/bulk', verifyToken, async (req, res) => {
  try {
    const { templates } = req.body;
    const results = await Promise.all(
      templates.map(template => firestore.createWorkflowTemplate({
        ...template,
        creatorId: req.user.id
      }))
    );
    res.json(results);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// router.get('/results', verifyToken, async (req, res) => {
//     try {
//       const userId = req.user.id;
//       const results = await firestore.getAllWorkflowResults(userId);
//       console.log(results)
//       res.json(results);
//     } catch (error) {
//       res.status(500).json({ error: error.message });
//     }
//   });
router.get('/results', verifyToken, async (req, res) => {
    try {
      const userId = req.user.id;
      const results = await firestore.getAllWorkflowResults(userId);
      
      // Create overview version of results
      const overviewResults = results.map(result => ({
        ...result,
        overview: result.outputs ? summarizeOutput(result.outputs) : 'No output',
      }));
  
      res.json(overviewResults);
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  });
  

  
  // Helper functions
  function summarizeOutput(outputs) {
    if (typeof outputs === 'string') {
      return outputs.length > 100 ? outputs.substring(0, 100) + '...' : outputs;
    }
    if (outputs.raw) {
      return outputs.raw.length > 100 ? outputs.raw.substring(0, 100) + '...' : outputs.raw;
    }
    return 'Output available in download';
  }
  
 
// Enhanced version with better styling
// router.get('/results/:instanceId/download', verifyToken, async (req, res) => {
//     try {
//       const userId = req.user.id;
//       const { instanceId } = req.params;
      
//       const allResults = await firestore.getAllWorkflowResults(userId);
//       const instanceResults = allResults.filter(result => result.instanceId === instanceId);
      
//       if (instanceResults.length === 0) {
//         return res.status(404).json({ error: 'Instance not found' });
//       }
//       console.log('INSTANCE RESULT')
//       console.log(instanceResults)
//       // Create PDF document
//       const doc = new PDFDocument({
//         size: 'A4',
//         margin: 50,
//         bufferPages: true
//       });
  
//       // Set up pipe and headers
//       res.setHeader('Content-Type', 'application/pdf');
//       res.setHeader('Content-Disposition', `attachment; filename=workflow-${instanceId}.pdf`);
//       doc.pipe(res);
  
//       // Add header with title and timestamp
//       doc.fontSize(24)
//          .fillColor('#333')
//          .text(instanceResults[0].workflowName, { align: 'center' })
//          .moveDown(0.5);
  
//       doc.fontSize(12)
//          .fillColor('#666')
//          .text(`Generated on: ${new Date().toLocaleString()}`, { align: 'center' })
//          .moveDown(2);
  
//       const sortedResults = instanceResults.sort((a, b) => a.stepIndex - b.stepIndex);
  
//       sortedResults.forEach((result, stepIndex) => {
//         // Parse the content from the result
//         let content = '';
//         if (result.outputs && result.outputs.raw) {
//           content = result.outputs.raw;
//         } else if (typeof result.outputs === 'string') {
//           try {
//             const parsed = JSON.parse(result.outputs);
//             content = parsed.raw || result.outputs;
//           } catch (e) {
//             content = result.outputs;
//           }
//         } else if (result.result) {
//           content = result.result;
//         }
  
//         // Split content into individual patient records
//         const records = content.split('\n\n').filter(record => record.trim());
  
//         records.forEach((record, recordIndex) => {
//           if (doc.y > 700) doc.addPage();
  
//           const lines = record.split('\n');
//           let isMainHeader = false;
  
//           lines.forEach((line, lineIndex) => {
//             const trimmedLine = line.trim();
            
//             if (!trimmedLine) {
//               doc.moveDown(0.5);
//               return;
//             }
  
//             // Main section headers (wrapped in ** without colon)
//             if (trimmedLine.match(/^\*\*[^:]+\*\*$/)) {
//               isMainHeader = true;
//               doc.fontSize(16)
//                  .fillColor('#2c5282')  // Dark blue for headers
//                  .text(trimmedLine.replace(/\*\*/g, ''))
//                  .moveDown(1);
//             }
//             // Key-value pairs
//             else if (trimmedLine.includes(':')) {
//               const [key, ...valueParts] = trimmedLine.split(':');
//               const value = valueParts.join(':').trim();  // Handle cases where value might contain colons
              
//               // Remove ** from both key and value
//               const cleanKey = key.replace(/\*\*/g, '').trim();
//               const cleanValue = value.replace(/\*\*/g, '').trim();
  
//               // Create a grid-like layout for key-value pairs
//               doc.fontSize(11)
//                  .fillColor('#4a5568')  // Gray for keys
//                  .text(cleanKey + ':', {
//                    continued: true,
//                    width: 150,
//                  })
//                  .fillColor('#000')     // Black for values
//                  .text(' ' + cleanValue, {
//                    width: doc.page.width - 250,
//                  });
  
//               // Add extra space after the last field in a record
//               if (lineIndex === lines.length - 1) {
//                 doc.moveDown(1);
//               }
//             }
//           });
  
//           // Add separator between records (except for the last one)
//           if (recordIndex < records.length - 1) {
//             doc.moveDown(0.5)
//                .strokeColor('#e2e8f0')  // Light gray line
//                .lineWidth(1)
//                .moveTo(50, doc.y)
//                .lineTo(doc.page.width - 50, doc.y)
//                .stroke()
//                .moveDown(1);
//           }
//         });
  
//         // Add separator between steps
//         if (stepIndex < sortedResults.length - 1) {
//           doc.addPage();
//         }
//       });
  
//       // Add page numbers
//       let pages = doc.bufferedPageRange();
//       for (let i = 0; i < pages.count; i++) {
//         doc.switchToPage(i);
        
//         // Add header on each page
//         doc.fontSize(8)
//            .fillColor('#666')
//            .text(
//              instanceResults[0].workflowName,
//              50,
//              20,
//              { align: 'right' }
//            );
  
//         // Add footer with page numbers
//         doc.fontSize(10)
//            .fillColor('#666')
//            .text(
//              `Page ${i + 1} of ${pages.count}`,
//              50,
//              doc.page.height - 30,
//              { align: 'center' }
//            );
//       }
  
//       doc.end();
  
//     } catch (error) {
//       console.error('PDF generation error:', error);
//       res.status(500).json({ error: error.message });
//     }
//   });
router.get('/results/:instanceId/download', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const { instanceId } = req.params;
    
    const allResults = await firestore.getAllWorkflowResults(userId);
    const instanceResults = allResults.filter(result => result.instanceId === instanceId);
    
    if (instanceResults.length === 0) {
      return res.status(404).json({ error: 'Instance not found' });
    }

    // Function to convert pipe-delimited table to key-value format
    function formatTableContent(content) {
      if (!content || !content.includes('|')) {
        return content;
      }

      const lines = content.split('\n').filter(line => line.trim());
      
      // Find the first line with actual data (not separators)
      const headerLineIndex = lines.findIndex(line => 
        line.includes('|') && 
        !line.trim().replace(/[|]/g, '').match(/^[-\s]*$/) // Not a separator line
      );

      if (headerLineIndex === -1) return content;

      // Parse headers from the first data line
      const headers = lines[headerLineIndex]
        .split('|')
        .map(h => h.trim())
        .filter(Boolean); // Remove empty cells

      // Get all data rows (any non-separator line after headers)
      const dataRows = lines.slice(headerLineIndex + 1)
        .filter(line => 
          line.includes('|') && 
          !line.trim().replace(/[|]/g, '').match(/^[-\s]*$/) // Not a separator line
        );

      // Convert each row to key-value format
      return dataRows.map(row => {
        const values = row
          .split('|')
          .map(cell => cell.trim())
          .filter(Boolean); // Remove empty cells

        // Combine headers with values
        return headers.map((header, index) => 
          `${header.replace(/\*\*/g, '')}: ${(values[index] || '').replace(/\*\*/g, '')}`
        ).join('\n');
      }).join('\n\n'); // Separate records with blank lines
    }

    const doc = new PDFDocument({
      size: 'A4',
      margin: 50,
      bufferPages: true
    });

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename=workflow-${instanceId}.pdf`);
    doc.pipe(res);

    doc.fontSize(24)
       .fillColor('#333')
       .text(instanceResults[0].workflowName || 'Workflow Results', { align: 'center' })
       .moveDown(0.5);

    doc.fontSize(12)
       .fillColor('#666')
       .text(`Generated on: ${new Date().toLocaleString()}`, { align: 'center' })
       .moveDown(2);

    const sortedResults = instanceResults.sort((a, b) => a.stepIndex - b.stepIndex);

    sortedResults.forEach((result, stepIndex) => {
      // Parse the content from the result
      let content = '';
      if (result.outputs && result.outputs.raw) {
        content = result.outputs.raw;
      } else if (typeof result.outputs === 'string') {
        try {
          const parsed = JSON.parse(result.outputs);
          content = parsed.raw || result.outputs;
        } catch (e) {
          content = result.outputs;
        }
      } else if (result.result) {
        content = result.result;
      }

      // Convert table format to key-value format
      content = formatTableContent(content);

      // Split content into individual records
      const records = content.split('\n\n').filter(record => record.trim());

      records.forEach((record, recordIndex) => {
        if (doc.y > 700) doc.addPage();

        const lines = record.split('\n');

        lines.forEach((line, lineIndex) => {
          const trimmedLine = line.trim();
          
          if (!trimmedLine) {
            doc.moveDown(0.5);
            return;
          }

          // Handle key-value pairs
          if (trimmedLine.includes(':')) {
            const [key, ...valueParts] = trimmedLine.split(':');
            const value = valueParts.join(':').trim();
            
            doc.fontSize(11)
               .fillColor('#4a5568')
               .text(key.trim() + ':', {
                 continued: true,
                 width: 150,
               })
               .fillColor('#000')
               .text(' ' + value, {
                 width: doc.page.width - 250,
               });

            if (lineIndex === lines.length - 1) {
              doc.moveDown(1);
            }
          }
        });

        if (recordIndex < records.length - 1) {
          doc.moveDown(0.5)
             .strokeColor('#e2e8f0')
             .lineWidth(1)
             .moveTo(50, doc.y)
             .lineTo(doc.page.width - 50, doc.y)
             .stroke()
             .moveDown(1);
        }
      });

      if (stepIndex < sortedResults.length - 1) {
        doc.addPage();
      }
    });

    let pages = doc.bufferedPageRange();
    for (let i = 0; i < pages.count; i++) {
      doc.switchToPage(i);
      
      doc.fontSize(8)
         .fillColor('#666')
         .text(
           instanceResults[0].workflowName || 'Workflow Results',
           50,
           20,
           { align: 'right' }
         );

      doc.fontSize(10)
         .fillColor('#666')
         .text(
           `Page ${i + 1} of ${pages.count}`,
           50,
           doc.page.height - 30,
           { align: 'center' }
         );
    }

    doc.end();

  } catch (error) {
    console.error('PDF generation error:', error);
    if (!res.headersSent) {
      res.status(500).json({ error: error.message });
    }
  }
});
// Add new endpoint for Excel export
router.get('/results/:instanceId/export-excel', verifyToken, async (req, res) => {
  try {
      const userId = req.user.id;
      const { instanceId } = req.params;
      
      const allResults = await firestore.getAllWorkflowResults(userId);
      const instanceResults = allResults.filter(result => result.instanceId === instanceId);
      
      if (instanceResults.length === 0) {
          return res.status(404).json({ error: 'Instance not found' });
      }

      // Get the final result
      const finalResult = instanceResults[instanceResults.length - 1];
      console.log(finalResult.outputs.raw)
      // Process result to structured format
      const processedResult = processWorkflowResults([finalResult])[0];

      console.log('CREATING EXCEL')
      // Create sheet with structured data
      await integrationHandlers.handleGoogleSheets(
          userId,
          finalResult.outputs.raw,
          { mode: 'create_new' }
      );

      res.json({ success: true });
  } catch (error) {
      console.error('Excel export error:', error);
      res.status(500).json({ error: error.message });
  }
});
  // Helper function to extract and format content from result
  function getResultContent(result) {
    if (result.outputs && result.outputs.raw) {
      // Parse markdown content
      const content = result.outputs.raw;
      // Remove markdown formatting for PDF
      return content
        .replace(/\*\*/g, '') // Remove bold markers
        .replace(/\n\n/g, '\n') // Normalize line breaks
        .trim();
    }
    
    if (typeof result.outputs === 'object') {
      return JSON.stringify(result.outputs, null, 2);
    }
    
    if (result.result) {
      return result.result;
    }
  
    return 'No content available';
  }
  
  function formatResultsForDownload(results) {
    try {
      return results
        .sort((a, b) => a.stepIndex - b.stepIndex)
        .map(result => {
          // Handle potentially undefined fields
          const stepIndex = result.stepIndex || 0;
          const workflowName = result.workflowName || 'Unnamed Workflow';
          const timestamp = result.timestamp ? new Date(result.timestamp).toLocaleString() : 'No timestamp';
          
          // Safely handle the output/result
          let output = 'No output available';
          if (result.result) {
            output = result.result;
          } else if (result.outputs) {
            output = typeof result.outputs === 'string' 
              ? result.outputs 
              : JSON.stringify(result.outputs, null, 2);
          }
  
          return `
  === Step ${stepIndex + 1} ===
  Workflow: ${workflowName}
  Timestamp: ${timestamp}
  
  Output:
  ${output}
  
  -------------------
  `;
        }).join('\n');
    } catch (error) {
      console.error('Error in formatResultsForDownload:', error);
      throw error;
    }
  }
export default router;