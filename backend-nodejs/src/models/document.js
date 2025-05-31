// backend/src/models/document.js
'use strict';

import { Firestore } from '@google-cloud/firestore';
import { v4 as uuidv4 } from 'uuid';

class Document {
  constructor(db) {
    this.collection = db.collection('documents');
  }

  async create(data) {
    const id = uuidv4();
    const document = {
      id,
      userId: data.userId,
      name: data.name,
      type: data.type,
      size: data.size,
      status: data.status || 'pending',
      vectorIds: data.vectorIds || [],
      error: data.error || null,
      createdAt: Firestore.FieldValue.serverTimestamp(),
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };

    await this.collection.doc(id).set(document);
    return document;
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
}

export { Document };
