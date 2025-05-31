// backend/src/models/assistant.js
'use strict';

import { Firestore } from '@google-cloud/firestore';
import { v4 as uuidv4 } from 'uuid';

class Assistant {
  constructor(db) {
    this.collection = db.collection('assistants');
  }

  async create(data) {
    const id = uuidv4();
    const assistant = {
      id,
      userId: data.userId,
      organization_id: data.organization_id, // Add organization_id field
      name: data.name,
      description: data.description || '',
      type: data.type,
      assistantType: data.assistantType || 'private', // Default to 'private' if not provided
      status: data.status || 'inactive',
      maxTokens: data.maxTokens || 1000,
      temperature: data.temperature || 0.7,
      knowledgeBase: data.knowledgeBase || [],
      lastTrainedAt: data.lastTrainedAt || null,
      error: data.error || null,
      survey_id: data.survey_id || null,

       // Add new customization fields
       customization: {
        avatar: data.customization?.avatar || null,
        bio: data.customization?.bio || null,
        expertise: data.customization?.expertise || [],
        experience: data.customization?.experience || null,
        voiceType: data.customization?.voiceType || null,
        socialLinks: data.customization?.socialLinks || {
          twitter: null,
          linkedin: null,
          github: null,
          website: null
        },

          // Add KPI settings structure
          kpiConfig: data.assistantType === 'representative' ? {
            categories: data.kpiSettings?.categories || {},
            activeKPIs: data.kpiSettings?.activeKPIs || {},
            metrics: {}, // Will store actual KPI metrics
            lastUpdated: null
          } : null,
    

         // Include flowData in the assistant document
      flowData: data.flowData || null, // Add flowData field

        voice: data.customization?.voice || null,
        profession: data.customization?.profession || null
      },

      createdAt: Firestore.FieldValue.serverTimestamp(),
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };

    await this.collection.doc(id).set(assistant);
    return assistant;
  }


  async findById(id) {
    const doc = await this.collection.doc(id).get();
    return doc.exists ? { id: doc.id, ...doc.data() } : null;
  }

  async update(id, data) {
    const updates = {
      ...data,
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };
    await this.collection.doc(id).update(updates);
    return this.findById(id);
  }
  async updateKPIMetrics(id, metrics) {
    const updates = {
      'kpiConfig.metrics': metrics,
      'kpiConfig.lastUpdated': Firestore.FieldValue.serverTimestamp()
    };
    await this.collection.doc(id).update(updates);
    return this.findById(id);
  }
}
export { Assistant };
