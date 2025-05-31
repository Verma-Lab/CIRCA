// backend/src/services/db/firestore.js

import { Firestore } from '@google-cloud/firestore';
import dotenv from 'dotenv'
dotenv.config()
class FirestoreService {
    // constructor() {
    //     // Initialize with existing service account credentials
    //     const credentials = {
    //       projectId: "op8imize",
    //       client_email: "op8imizecloud@op8imize.iam.gserviceaccount.com",
    //       private_key: process.env.GOOGLE_CLOUD_PRIVATE_KEY// Your private key
    //     };
    
    //     this.db = new Firestore({
    //       ...credentials,
    //       ignoreUndefinedProperties: true, // Add this for better error handling
    //       preferRest: true // Use REST API instead of gRPC
    //     });
    //   }
    constructor() {
      // Use environment variables for project configuration
      this.db = new Firestore({
        projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
        keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
        ignoreUndefinedProperties: true,
        databaseId:process.env.DATABASEID || 'circa',
        preferRest: true
      });
      
      console.log('Firestore initialized with:', {
        projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
        keyFile: process.env.GOOGLE_APPLICATION_CREDENTIALS
      });
  }
        getPlanLimits(plan) {
          return {
            free: {
              maxAssistants: -1,
              monthlyInteractions: 100,
              trainingSessions: 10,
              documents: 10, 
              models:1
            },
            pro: {
              maxAssistants: -1,
              monthlyInteractions: -1,
              trainingSessions: 50,
              documents: 20, 
              models:3

            },
            business: {
              maxAssistants: -1,
              monthlyInteractions: -1,
              trainingSessions: -1,
              models:-1
            }
          }[plan];
        }
      // Add these to your FirestoreService class
  async getUserAssistantCount(userId) {
    const snapshot = await this.db.collection('assistants')
      .where('userId', '==', userId)
      .count()
      .get();
    return snapshot.data().count;
  }

  async getMonthlyInteractions(userId) {
    const monthStart = new Date();
    monthStart.setDate(1);
    monthStart.setHours(0, 0, 0, 0);

    const snapshot = await this.db.collection('chat_messages')
      .where('userId', '==', userId)
      .where('createdAt', '>=', monthStart)
      .count()
      .get();
    return snapshot.data().count;
  }

  async incrementUserUsage(userId, metric) {
    const userRef = this.db.collection('users').doc(userId);
    await userRef.update({
      [`usage.${metric}`]: Firestore.FieldValue.increment(1)
    });
  }

  async checkUserLimit(userId, metric) {
    const user = await this.getUser(userId);
    const currentUsage = user.usage[metric];
    const limit = user.limits[metric];
    return limit === -1 || currentUsage < limit;
  }
  async getUserDocumentCount(userId) {
    try{
      const snapshot = await this.db.collection('documents')
      .where('userId', '==', userId)
      .count()
      .get();
      return snapshot.data().count;

    }catch(err){
      console.log(err)
      return err

    }

  }
  // Add this new function to get document limit based on user's plan
async getUserDocumentLimit(userId) {
  try {
    const user = await this.getUser(userId);
    if (!user) {
      throw new Error('User not found');
    }
    const planLimits = this.getPlanLimits(user.plan);
    return planLimits.documents;
  } catch(err) {
    console.log(err);
    throw err;
  }
}

      // Test the connection
      async testConnection() {
        try {
          // Try to write to a test collection
          const testRef = this.db.collection('test').doc('connection-test');
          await testRef.set({
            timestamp: Firestore.FieldValue.serverTimestamp(),
            test: true
          });
          
          // Try to read it back
          const doc = await testRef.get();
          if (!doc.exists) {
            throw new Error('Test document not found');
          }
    
          // Clean up
          await testRef.delete();
          
          console.log('Firestore connection test successful');
          return true;
        } catch (error) {
          console.error('Firestore connection test failed:', error);
          throw error;
        }
      }

    async testConnection() {
        try {
          const testDoc = this.db.collection('test').doc('connection-test');
          await testDoc.set({ timestamp: new Date() });
          await testDoc.delete();
          return true;
        } catch (error) {
          console.error('Firestore connection test failed:', error);
          return false;
        }
      }
    
  // Users Collection
  // async createUser(userData) {
  //   const userRef = this.db.collection('users').doc();
  //   await userRef.set({
  //     ...userData,
  //     createdAt: Firestore.FieldValue.serverTimestamp()
  //   });
  //   return { id: userRef.id, ...userData };
  // }
  async createUser(userData) {
    const userRef = this.db.collection('users').doc();
    const userWithPlan = {
      ...userData,
      plan: userData.plan || 'free',
      usage: {
        assistants: 0,
        interactions: 0,
        trainingSessions: 0,
        documents: 0
      },
      limits: this.getPlanLimits(userData.plan || 'free'),
      // New creator metadata fields
      name: userData.name,
      email: userData.email,
      profession: userData.profession,
      expertise: userData.expertise,
      avatar: userData.avatar,
      bio: userData.bio,
      experience: userData.experience,
      profileCompleted: true,
      createdAt: Firestore.FieldValue.serverTimestamp()
    };
    await userRef.set(userWithPlan);
    return { id: userRef.id, ...userWithPlan };
  }


  async getUser(userId) {
    const doc = await this.db.collection('users').doc(userId).get();
    return doc.exists ? { id: doc.id, ...doc.data() } : null;
  }

  // Assistants Collection
  async createAssistant(assistantData) {
    const assistantRef = this.db.collection('assistants').doc();
    await assistantRef.set({
      ...assistantData,
      createdAt: Firestore.FieldValue.serverTimestamp()
    });
    return { id: assistantRef.id, ...assistantData };
  }

  async getUserAssistants(userId) {
    const snapshot = await this.db.collection('assistants')
      .where('userId', '==', userId)
      .orderBy('createdAt', 'desc')
      .get();
    return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
  }

  // Documents Collection (metadata only)
  async createDocument(documentData) {
    const documentRef = this.db.collection('documents').doc();
    await documentRef.set({
      ...documentData,
      createdAt: Firestore.FieldValue.serverTimestamp()
    });
    return { id: documentRef.id, ...documentData };
  }

  async updateDocument(documentId, updates) {
    const docRef = this.db.collection('documents').doc(documentId);
    await docRef.update({
      ...updates,
      updatedAt: Firestore.FieldValue.serverTimestamp()
    });
  }

  // Chat History Collection
  async saveChatMessage(assistantId, message) {
    const chatRef = this.db.collection('chats').doc();
    await chatRef.set({
      assistantId,
      ...message,
      timestamp: Firestore.FieldValue.serverTimestamp()
    });
    return { id: chatRef.id, ...message };
  }

  async getAssistantChats(assistantId, limit = 100) {
    const snapshot = await this.db.collection('chats')
      .where('assistantId', '==', assistantId)
      .orderBy('timestamp', 'desc')
      .limit(limit)
      .get();
    return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
  }
  // Add to your FirestoreService class

// User methods
async updateUser(userId, updates) {
    const userRef = this.db.collection('users').doc(userId);
    await userRef.update({
      ...updates,
      updatedAt: Firestore.FieldValue.serverTimestamp()
    });
  }
  
  async getUserByEmail(email) {
    const snapshot = await this.db.collection('users')
      .where('email', '==', email)
      .limit(1)
      .get();
    return !snapshot.empty ? { id: snapshot.docs[0].id, ...snapshot.docs[0].data() } : null;
  }
  
  // Assistant methods
  async getAssistant(assistantId) {
    const doc = await this.db.collection('assistants').doc(assistantId).get();
    return doc.exists ? { id: doc.id, ...doc.data() } : null;
  }
  
  async updateAssistant(assistantId, updates) {
    const assistantRef = this.db.collection('assistants').doc(assistantId);
    await assistantRef.update({
      ...updates,
      updatedAt: Firestore.FieldValue.serverTimestamp()
    });
  }
  
  // Document methods
  async getDocument(documentId) {
    const doc = await this.db.collection('documents').doc(documentId).get();
    return doc.exists ? { id: doc.id, ...doc.data() } : null;
  }
  
  async getUserDocuments(userId) {
    const snapshot = await this.db.collection('documents')
      .where('userId', '==', userId)
      .orderBy('createdAt', 'desc')
      .get();
    return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
  }
  
  // Batch operations
  async createBatch() {
    return this.db.batch();
  }
  
  async runTransaction(callback) {
    return this.db.runTransaction(callback);
  }
  async createShareLink(shareData) {
    const shareRef = this.db.collection('shared_links').doc();
    await shareRef.set({
      ...shareData,
      createdAt: Firestore.FieldValue.serverTimestamp()
    });
    return { id: shareRef.id, ...shareData };
  }

  async getShareLink(shareId) {
    const snapshot = await this.db.collection('shared_links')
      .where('shareId', '==', shareId)
      .limit(1)
      .get();
    
    if (snapshot.empty) return null;
    return { id: snapshot.docs[0].id, ...snapshot.docs[0].data() };
  }

  async updateShareLink(shareId, updates) {
    const shareSnapshot = await this.db.collection('shared_links')
      .where('shareId', '==', shareId)
      .limit(1)
      .get();
    
    if (shareSnapshot.empty) throw new Error('Share link not found');
    
    const shareDoc = shareSnapshot.docs[0];
    await shareDoc.ref.update({
      ...updates,
      updatedAt: Firestore.FieldValue.serverTimestamp()
    });
  }

  async getAssistantShares(assistantId, ownerId) {
    const snapshot = await this.db.collection('shared_links')
      .where('assistantId', '==', assistantId)
      .where('ownerId', '==', ownerId)
      .orderBy('createdAt', 'desc')
      .get();
    
    return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
  }

  // Shared chat methods
  async saveSharedChatMessage(messageData) {
    try {
      console.log('Saving shared chat message:', messageData);
      const messageRef = this.db.collection('shared_chat_messages').doc();
      
      // Add sessionId to the message data
      const sanitizedData = {
        shareId: messageData.shareId,
        sessionId: messageData.sessionId, // Add this field
        assistantId: messageData.assistantId,
        role: messageData.role,
        content: messageData.content,
        createdAt: Firestore.FieldValue.serverTimestamp(),
        contextUsed: messageData.contextUsed || null, 
        surveyId: messageData.surveyId || null,
        ...(messageData.patientId && { patientId: messageData.patientId }) // Include patientId if provided

      };

      await messageRef.set(sanitizedData);
      
      return {
        id: messageRef.id,
        ...messageData,
        createdAt: new Date()
      };
    } catch (error) {
      console.error('Error saving chat message:', error);
      throw error;
    }
  }

  async getSharedChatHistory(shareId, sessionId, patientId = null) {
    try {
      console.log('Fetching chat history for shareId:', shareId, 'sessionId:', sessionId);
      
      // const snapshot = await this.db.collection('shared_chat_messages')
      //   .where('shareId', '==', shareId)
      //   .where('sessionId', '==', sessionId)
      //   .orderBy('createdAt', 'asc')
      //   .get();
      
        let query = this.db.collection('shared_chat_messages')
  .where('shareId', '==', shareId)
  .where('sessionId', '==', sessionId);
if (patientId) {
  query = query.where('patientId', '==', patientId);
}
const snapshot = await query
  .orderBy('createdAt', 'asc')
  .get();
      const messages = snapshot.docs.map(doc => {
        const data = doc.data();
        return {
          id: doc.id,
          ...data,
          createdAt: data.createdAt?.toDate() || null
        };
      });

      console.log(`Found ${messages.length} messages for session:`, sessionId);
      return messages;
    } catch (error) {
      console.error('Error fetching chat history:', error);
      throw error;
    }
  }

  // Add these methods to your FirestoreService class

// Payment-related methods
async createPaymentRecord(paymentData) {
  try {
    const paymentRef = this.db.collection('user_payments').doc();
    const payment = {
      userId: paymentData.userId,
      orderId: paymentData.orderId,
      paymentId: paymentData.paymentId,
      plan: paymentData.plan,
      amount: paymentData.amount,
      currency: paymentData.currency || 'INR',
      status: paymentData.status,
      paymentMethod: paymentData.paymentMethod || 'razorpay',
      createdAt: Firestore.FieldValue.serverTimestamp(),
      validFrom: paymentData.validFrom || new Date(),
      validUntil: paymentData.validUntil || null,
      metadata: {
        razorpaySignature: paymentData.razorpaySignature,
        ...paymentData.metadata
      }
    };
    
    await paymentRef.set(payment);
    return { id: paymentRef.id, ...payment };
  } catch (error) {
    console.error('Error creating payment record:', error);
    throw error;
  }
}

async getUserPaymentHistory(userId) {
  try {
    const snapshot = await this.db.collection('user_payments')
      .where('userId', '==', userId)
      .orderBy('createdAt', 'desc')
      .get();
      
    return snapshot.docs.map(doc => ({
      id: doc.id,
      ...doc.data(),
      createdAt: doc.data().createdAt?.toDate(),
      validFrom: doc.data().validFrom?.toDate(),
      validUntil: doc.data().validUntil?.toDate()
    }));
  } catch (error) {
    console.error('Error fetching payment history:', error);
    throw error;
  }
}

async getPaymentByOrderId(orderId) {
  try {
    const snapshot = await this.db.collection('user_payments')
      .where('orderId', '==', orderId)
      .limit(1)
      .get();
      
    if (snapshot.empty) return null;
    
    const doc = snapshot.docs[0];
    return {
      id: doc.id,
      ...doc.data(),
      createdAt: doc.data().createdAt?.toDate(),
      validFrom: doc.data().validFrom?.toDate(),
      validUntil: doc.data().validUntil?.toDate()
    };
  } catch (error) {
    console.error('Error fetching payment by order ID:', error);
    throw error;
  }
}

async updatePaymentStatus(paymentId, status, metadata = {}) {
  try {
    const paymentRef = this.db.collection('user_payments').doc(paymentId);
    await paymentRef.update({
      status,
      updatedAt: Firestore.FieldValue.serverTimestamp(),
      ...metadata
    });
  } catch (error) {
    console.error('Error updating payment status:', error);
    throw error;
  }
}

async getCurrentUserPlan(userId) {
  try {
    // Get the latest active payment record
    const snapshot = await this.db.collection('user_payments')
      .where('userId', '==', userId)
      .where('status', '==', 'success')
      .where('validUntil', '>', new Date())
      .orderBy('validUntil', 'desc')
      .limit(1)
      .get();

    if (snapshot.empty) {
      // If no active paid plan, return free
      return { plan: 'free' };
    }

    const doc = snapshot.docs[0];
    return {
      id: doc.id,
      ...doc.data(),
      validFrom: doc.data().validFrom?.toDate(),
      validUntil: doc.data().validUntil?.toDate()
    };
  } catch (error) {
    console.error('Error getting current user plan:', error);
    throw error;
  }
}

// Add these methods to FirestoreService class

// Integration methods
async createIntegration(integrationData) {
  const integrationRef = this.db.collection('integrations').doc();
  const integration = {
    userId: integrationData.userId,
    assistantId: integrationData.assistantId,
    platform: integrationData.platform, // 'slack' or 'teams'
    workspaceId: integrationData.workspaceId,
    accessToken: integrationData.accessToken,
    refreshToken: integrationData.refreshToken,
    botId: integrationData.botId,
    channelId: integrationData.channelId,
    status: 'active',
    settings: integrationData.settings || {},
    createdAt: Firestore.FieldValue.serverTimestamp(),
    lastUsed: Firestore.FieldValue.serverTimestamp()
  };
  
  await integrationRef.set(integration);
  return { id: integrationRef.id, ...integration };
}

async getUserIntegrations(userId) {
  const snapshot = await this.db.collection('integrations')
    .where('userId', '==', userId)
    .where('status', '==', 'active')
    .get();
    
  return snapshot.docs.map(doc => ({
    id: doc.id,
    ...doc.data()
  }));
}

async getAssistantIntegrations(assistantId) {
  const snapshot = await this.db.collection('integrations')
    .where('assistantId', '==', assistantId)
    .where('status', '==', 'active')
    .get();
    
  return snapshot.docs.map(doc => ({
    id: doc.id,
    ...doc.data()
  }));
}

async updateIntegration(integrationId, updates) {
  const integrationRef = this.db.collection('integrations').doc(integrationId);
  await integrationRef.update({
    ...updates,
    updatedAt: Firestore.FieldValue.serverTimestamp()
  });
}

async deleteIntegration(integrationId) {
  await this.db.collection('integrations').doc(integrationId).update({
    status: 'inactive',
    updatedAt: Firestore.FieldValue.serverTimestamp()
  });
}

// Integration messages
async saveIntegrationMessage(messageData) {
  const messageRef = this.db.collection('integration_messages').doc();
  const message = {
    integrationId: messageData.integrationId,
    assistantId: messageData.assistantId,
    platform: messageData.platform,
    channelId: messageData.channelId,
    userId: messageData.userId,
    content: messageData.content,
    role: messageData.role, // 'user' or 'assistant'
    createdAt: Firestore.FieldValue.serverTimestamp()
  };
  
  await messageRef.set(message);
  return { id: messageRef.id, ...message };
}

async getIntegrationMessages(integrationId, limit = 100) {
  const snapshot = await this.db.collection('integration_messages')
    .where('integrationId', '==', integrationId)
    .orderBy('createdAt', 'desc')
    .limit(limit)
    .get();
    
  return snapshot.docs.map(doc => ({
    id: doc.id,
    ...doc.data()
  }));
}
  // Add this to your FirestoreService class
// In firestore.js
async getCreatorByShareId(shareId) {
  try {
    // First get the share link document
    const shareSnapshot = await this.db.collection('shared_links')
      .where('shareId', '==', shareId)
      .limit(1)
      .get();
    
    if (shareSnapshot.empty) return null;
    
    const shareData = shareSnapshot.docs[0].data();
    const userId = shareData.userId || shareData.ownerId;

    // Now get the creator's user document
    const creatorDoc = await this.db.collection('users').doc(userId).get();
    
    if (!creatorDoc.exists) return null;

    const creatorData = creatorDoc.data();
    return {
      name: creatorData.name,
      profession: creatorData.profession || 'AI Assistant Creator',
      expertise: creatorData.expertise || ['AI', 'Machine Learning'],
      avatar: creatorData.avatar || null,
      bio: creatorData.bio || null,
      experience: creatorData.experience || '5+ years',
      email: creatorData.email
    };
  } catch (error) {
    console.error('Error getting creator by share ID:', error);
    return null;
  }
}

// Add to your FirestoreService class
// Workflow Template Methods
async createWorkflowTemplate(templateData) {
  try {
  const templateRef = this.db.collection('workflow_templates').doc();
  const template = {
  category: templateData.category,
  name: templateData.name,
  description: templateData.description,
  creatorId: templateData.creatorId,
  assistantId: templateData.assistantId,
  steps: templateData.steps.map((step, index) => ({
  ...step,
  stepIndex: index,
  createdAt: new Date().toISOString()
  })),
  isCustom: templateData.isCustom || false,
  status: 'active',
  createdAt: new Date().toISOString()
  };
    console.log(template)
    await templateRef.set(template);
    return { id: templateRef.id, ...template };
  } catch (error) {
    console.error('Error creating workflow template:', error);
    throw error;
  }
  }

  async getWorkflowTemplates(assistantId) {
    try {
    const snapshot = await this.db.collection('workflow_templates')
    .where('assistantId', '==', assistantId)
    .where('status', '==', 'active')
    .orderBy('createdAt', 'desc')
    .get();
    
      return snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
      }));
    } catch (error) {
      console.error('Error fetching workflow templates:', error);
      throw error;
    }
    }

// Workflow Instance Methods
async createWorkflowInstance(instanceData) {
  try {
  const instanceRef = this.db.collection('workflow_instances').doc();
  const instance = {
  templateId: instanceData.templateId,
  assistantId: instanceData.assistantId,
  userId: instanceData.userId,
  name: instanceData.name,
  currentStep: 0,
  status: 'active',
  steps: instanceData.steps.map((step, index) => ({
  ...step,
  stepIndex: index,
  status: index === 0 ? 'current' : 'pending',
  results: null,
  startedAt: null,
  completedAt: null
  })),
  createdAt: new Date().toISOString(),
  lastUpdated: new Date().toISOString()
  };
  
    await instanceRef.set(instance);
    return { id: instanceRef.id, ...instance };
  } catch (error) {
    console.error('Error creating workflow instance:', error);
    throw error;
  }
  }

  async updateWorkflowStep(instanceId, stepIndex, updateData) {
    try {
      const instanceRef = this.db.collection('workflow_instances').doc(instanceId);
      
      // Get current instance data
      const instance = await instanceRef.get();
      if (!instance.exists) {
        throw new Error('Workflow instance not found');
      }
  
      const instanceData = instance.data();
      const steps = [...instanceData.steps];
      
      // Validate step index
      if (stepIndex !== instanceData.currentStep) {
        throw new Error(`Cannot update step ${stepIndex}. Current step is ${instanceData.currentStep}`);
      }
      
      // Update specific step
      steps[stepIndex] = {
        ...steps[stepIndex],
        ...updateData,
        lastUpdated: new Date().toISOString()
      };
  
      // If step is completed, move to next step
      let nextStep = stepIndex;
      let newStatus = instanceData.status;
      
      if (updateData.status === 'completed' && stepIndex < steps.length - 1) {
        nextStep = stepIndex + 1;
        steps[nextStep].status = 'current';
        steps[nextStep].startedAt = new Date().toISOString();
      } else if (updateData.status === 'completed' && stepIndex === steps.length - 1) {
        newStatus = 'completed';
      }
  
      // Create update object
      const updateObj = {
        steps,
        currentStep: nextStep,
        lastUpdated: new Date().toISOString(),
        status: newStatus
      };
  
      // Update instance with await
      await instanceRef.update(updateObj);
  
      // Return updated instance data
      return {
        id: instanceId,
        currentStep: nextStep,
        steps,
        status: newStatus
      };
    } catch (error) {
      console.error('Error updating workflow step:', error);
      throw error;
    }
  }

// Workflow Results Methods
async saveWorkflowResults(resultData) {
  try {
  const resultRef = this.db.collection('workflow_results').doc();
  const result = {
  instanceId: resultData.instanceId,
  stepIndex: resultData.stepIndex,
  outputs: resultData.outputs,
  metadata: resultData.metadata || {},
  createdAt: new Date().toISOString()
  };
  
    await resultRef.set(result);
    return { id: resultRef.id, ...result };
  } catch (error) {
    console.error('Error saving workflow results:', error);
    throw error;
  }
  }

  async getWorkflowResults(instanceId) {
    try {
    const snapshot = await this.db.collection('workflow_results')
    .where('instanceId', '==', instanceId)
    .orderBy('createdAt', 'asc')
    .get();
    
      return snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
      }));
    } catch (error) {
      console.error('Error fetching workflow results:', error);
      throw error;
    }
    }

// Workflow Analytics Methods
async saveWorkflowAnalytics(analyticsData) {
  try {
  const analyticsRef = this.db.collection('workflow_analytics').doc();
  const analytics = {
  instanceId: analyticsData.instanceId,
  templateId: analyticsData.templateId,
  assistantId: analyticsData.assistantId,
  userId: analyticsData.userId,
  completionTime: analyticsData.completionTime,
  stepMetrics: analyticsData.stepMetrics,
  createdAt:new Date().toISOString()
  };
  
    await analyticsRef.set(analytics);
    return { id: analyticsRef.id, ...analytics };
  } catch (error) {
    console.error('Error saving workflow analytics:', error);
    throw error;
  }
  }
  async getWorkflowTemplate(templateId) {
    try {
    const doc = await this.db.collection('workflow_templates').doc(templateId).get();
    if (!doc.exists) {
    return null;
    }
    return { id: doc.id, ...doc.data() };
    } catch (error) {
    console.error('Error getting workflow template by ID:', error);
    throw error;
    }
    }
    async getWorkflowInstance(instanceId) {
      try {
      const doc = await this.db.collection('workflow_instances').doc(instanceId).get();
      if (!doc.exists) {
      return null;
      }
      return { id: doc.id, ...doc.data() };
      } catch (error) {
      console.error('Error getting workflow instance by ID:', error);
      throw error;
      }
      }
      async updateTemplate(templateId, updates) {
        try {
        const templateRef = this.db.collection('workflow_templates').doc(templateId);
        await templateRef.update({ ...updates });
        
          // Return updated doc
          const updatedDoc = await templateRef.get();
          return { id: templateId, ...updatedDoc.data() };
        } catch (error) {
          console.error('Error updating workflow template:', error);
          throw error;
        }
        }
        // Add this method to your FirestoreService class
        async getAllWorkflowResults(userId) {
          try {
            // First get all instances for this user
            const instancesSnapshot = await this.db.collection('workflow_instances')
              .where('userId', '==', userId)
              .get();
        
            const instanceIds = instancesSnapshot.docs.map(doc => doc.id);
            
            if (instanceIds.length === 0) {
              return [];
            }
        
            // Split instanceIds into batches of 30 and fetch results
            const batchSize = 30;
            const batches = [];
            for (let i = 0; i < instanceIds.length; i += batchSize) {
              const batchIds = instanceIds.slice(i, i + batchSize);
              batches.push(
                this.db.collection('workflow_results')
                  .where('instanceId', 'in', batchIds)
                  .orderBy('createdAt', 'desc')
                  .get()
              );
            }
        
            // Get all results
            const resultsSnapshots = await Promise.all(batches);
            
            // Combine all docs from all batches
            const allDocs = resultsSnapshots.flatMap(snapshot => snapshot.docs);
            
            // Map through results and add instance data - keeping exact same format
            const results = await Promise.all(allDocs.map(async doc => {
              const result = doc.data();
              const instance = instancesSnapshot.docs.find(
                inst => inst.id === result.instanceId
              );
              const instanceData = instance.data();
        
              return {
                id: doc.id,
                ...result,
                assistantId: instanceData.assistantId,
                workflowName: instanceData.name, // Add workflow name from instance
                timestamp: result.createdAt
              };
            }));
        
            // Sort all results by createdAt to maintain order
            results.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        
            return results;
          } catch (error) {
            console.error('Error fetching all workflow results:', error);
            throw error;
          }
        }

// Training Session methods
async createTrainingSession(sessionData) {
  const sessionRef = this.db.collection('training_sessions').doc();
  const session = {
    assistantId: sessionData.assistantId,
    modelType: sessionData.modelType,
    status: 'initializing',
    progress: 0,
    jobId: sessionData.jobId || null,
    error: null,
    modelConfig: sessionData.modelConfig || {},
    startedAt: Firestore.FieldValue.serverTimestamp(),
    createdAt: Firestore.FieldValue.serverTimestamp()
  };

  await sessionRef.set(session);
  return { id: sessionRef.id, ...session };
}

async updateTrainingSession(sessionId, updates) {
  const sessionRef = this.db.collection('training_sessions').doc(sessionId);
  await sessionRef.update({
    ...updates,
    updatedAt: Firestore.FieldValue.serverTimestamp()
  });
}

// Model Endpoints methods
async createModelEndpoint(endpointData) {
  const endpointRef = this.db.collection('model_endpoints').doc();
  const endpoint = {
    assistantId: endpointData.assistantId,
    modelType: endpointData.modelType,
    status: 'creating',
    endpointId: endpointData.endpointId,
    modelPath: endpointData.modelPath,
    version: endpointData.version,
    createdAt: Firestore.FieldValue.serverTimestamp()
  };

  await endpointRef.set(endpoint);
  return { id: endpointRef.id, ...endpoint };
}

async updateModelEndpoint(endpointId, updates) {
  const endpointRef = this.db.collection('model_endpoints').doc(endpointId);
  await endpointRef.update({
    ...updates,
    updatedAt: Firestore.FieldValue.serverTimestamp()
  });
}

// Model Weights methods
async createModelWeight(weightData) {
  const weightRef = this.db.collection('model_weights').doc();
  const weight = {
    assistantId: weightData.assistantId,
    modelType: weightData.modelType,
    version: weightData.version,
    path: weightData.path,
    status: 'active',
    createdAt: Firestore.FieldValue.serverTimestamp()
  };

  await weightRef.set(weight);
  return { id: weightRef.id, ...weight };
}

async getActiveModelWeight(assistantId) {
  const snapshot = await this.db.collection('model_weights')
    .where('assistantId', '==', assistantId)
    .where('status', '==', 'active')
    .orderBy('createdAt', 'desc')
    .limit(1)
    .get();

  return !snapshot.empty ? { id: snapshot.docs[0].id, ...snapshot.docs[0].data() } : null;
}
async getModelEndpoint(endpointId) {
  const doc = await this.db.collection('model_endpoints').doc(endpointId).get();
  return doc.exists ? { id: doc.id, ...doc.data() } : null;
}

async getModelEndpoints(assistantId) {
  const snapshot = await this.db.collection('model_endpoints')
    .where('assistantId', '==', assistantId)
    .where('status', '!=', 'deleted')
    .get();

  return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
}

async createPredictionLog(logData) {
  const logRef = this.db.collection('prediction_logs').doc();
  await logRef.set({
    ...logData,
    createdAt: Firestore.FieldValue.serverTimestamp()
  });
  return { id: logRef.id, ...logData };
}
        
}



export default new FirestoreService();