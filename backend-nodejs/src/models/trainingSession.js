// models/trainingSession.js
'use strict';

import { Firestore } from '@google-cloud/firestore';
import { v4 as uuidv4 } from 'uuid';

class TrainingSession {
  constructor(db) {
    this.collection = db.collection('training_sessions');
  }

  async create(data) {
    const id = uuidv4();
    const session = {
      id,
      assistantId: data.assistantId,
      modelType: data.modelType,
      status: 'initializing',
      progress: 0,
      jobId: data.jobId || null,
      vertexConfig: {
        jobName: data.jobName,
        modelPath: data.modelPath,
        endpointId: data.endpointId
      },
      error: null,
      startedAt: Firestore.FieldValue.serverTimestamp(),
      createdAt: Firestore.FieldValue.serverTimestamp(),
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };

    await this.collection.doc(id).set(session);
    return session;
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

  async getActiveSession(assistantId) {
    const snapshot = await this.collection
      .where('assistantId', '==', assistantId)
      .where('status', 'in', ['initializing', 'training', 'deploying'])
      .limit(1)
      .get();

    return !snapshot.empty ? { id: snapshot.docs[0].id, ...snapshot.docs[0].data() } : null;
  }
}

export { TrainingSession };