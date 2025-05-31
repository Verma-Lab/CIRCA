// backend/src/models/user.js
'use strict';

import { Firestore } from '@google-cloud/firestore';
import { v4 as uuidv4 } from 'uuid';
import bcrypt from 'bcrypt';
import crypto from 'crypto';

class User {
  constructor(db) {
    this.collection = db.collection('users');
  }

  async create(data) {
    const id = uuidv4();
    const hashedPassword = await bcrypt.hash(data.password, 10);
    const apiKey = crypto.randomBytes(32).toString('hex');

    const user = {
      id,
      name: data.name,
      email: data.email,
      password: hashedPassword,
      apiKey,
      organization_id: data.organization_id || null, // Add organization_id field
      status: data.status || 'active',
      createdAt: Firestore.FieldValue.serverTimestamp(),
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };

    await this.collection.doc(id).set(user);
    return user;
  }

  async findById(id) {
    const doc = await this.collection.doc(id).get();
    return doc.exists ? { id: doc.id, ...doc.data() } : null;
  }

  async findByEmail(email) {
    const snapshot = await this.collection
      .where('email', '==', email)
      .limit(1)
      .get();
    
    return !snapshot.empty ? { id: snapshot.docs[0].id, ...snapshot.docs[0].data() } : null;
  }

  async comparePassword(password, hashedPassword) {
    return bcrypt.compare(password, hashedPassword);
  }

  async update(id, data) {
    const updates = {
      ...data,
      updatedAt: Firestore.FieldValue.serverTimestamp()
    };

    if (data.password) {
      updates.password = await bcrypt.hash(data.password, 10);
    }

    await this.collection.doc(id).update(updates);
    return this.findById(id);
  }
}

export { User };