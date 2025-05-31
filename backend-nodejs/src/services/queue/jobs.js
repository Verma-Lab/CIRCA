// backend/src/services/queue/jobs.js
'use strict';

import Bull from 'bull';
import geminiService from '../ai/gemini.js';
import qwenService from '../ai/qwen/service.js';
import documentStorage from '../storage/documents.js';
import vectorStorage from '../storage/vectors.js';

// Create queues
const documentQueue = new Bull('document-processing');
const trainingQueue = new Bull('assistant-training');

// Document processing job
documentQueue.process(async (job) => {
  const { documentId, userId } = job.data;

  try {
    // Update progress
    await job.progress(10);
    
    // Get document content
    const document = await documentStorage.getDocumentContent(documentId);
    await job.progress(30);

    // Analyze document
    const analysis = await geminiService.analyzeDocument({
      content: document.toString()
    });
    await job.progress(60);

    // Store vectors
    const vectorIds = await vectorStorage.storeVectors(analysis.embedding, {
      documentId,
      userId
    });
    await job.progress(90);

    // Update document status
    await Document.update(
      { status: 'processed', vectorIds },
      { where: { id: documentId } }
    );

    return { status: 'success', vectorIds };
  } catch (error) {
    console.error('Document processing error:', error);
    // Update document status to failed
    await Document.update(
      { status: 'failed', error: error.message },
      { where: { id: documentId } }
    );
    throw error;
  }
});

// Assistant training job
trainingQueue.process(async (job) => {
  const { assistantId, userId, documents } = job.data;

  try {
    // Update progress
    await job.progress(10);

    // Get assistant
    const assistant = await Assistant.findOne({
      where: { id: assistantId, userId }
    });

    if (!assistant) {
      throw new Error('Assistant not found');
    }

    // Update status to training
    await assistant.update({ status: 'training' });
    await job.progress(20);

    // Train assistant
    const result = await geminiService.trainAssistant(assistant, documents);
    await job.progress(70);

    // Store training results
    await assistant.update({
      status: 'active',
      knowledgeBase: result.knowledgeBase,
      lastTrainedAt: new Date()
    });
    await job.progress(100);

    return { status: 'success' };
  } catch (error) {
    console.error('Assistant training error:', error);
    // Update assistant status to failed
    await Assistant.update(
      { status: 'failed', error: error.message },
      { where: { id: assistantId } }
    );
    throw error;
  }
});

// Job management functions
export const queueDocumentProcessing = async (documentId, userId) => {
  return documentQueue.add({ documentId, userId }, {
    attempts: 3,
    backoff: {
      type: 'exponential',
      delay: 1000
    }
  });
};

export const queueTrainingJob = async (data) => {
  return trainingQueue.add(data, {
    attempts: 2,
    backoff: {
      type: 'exponential',
      delay: 2000
    }
  });
};
