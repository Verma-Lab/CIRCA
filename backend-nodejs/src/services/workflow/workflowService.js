// backend/src/services/ai/workflowService.js

import firestore from '../../services/db/firestore.js';

class WorkflowService {
  /**
   * Create a new workflow for a given assistant
   * @param {string} assistantId 
   * @param {Object} workflowData 
   *   e.g. { name: "Some Workflow", steps: [...] }
   */
  async createWorkflow(assistantId, workflowData) {
    const workflowRef = firestore.db.collection('workflows').doc();
    const payload = {
      assistantId,
      name: workflowData.name || 'Untitled Workflow',
      steps: workflowData.steps || [],
      createdAt: new Date(),
      updatedAt: new Date()
    };
    await workflowRef.set(payload);
    return { id: workflowRef.id, ...payload };
  }

  /**
   * Fetch multiple workflows belonging to an assistant
   * @param {string} assistantId 
   */
  async getWorkflows(assistantId) {
    const snapshot = await firestore.db
      .collection('workflows')
      .where('assistantId', '==', assistantId)
      .orderBy('createdAt', 'desc')
      .get();
    return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
  }

  /**
   * Fetch a single workflow by ID
   * @param {string} workflowId 
   */
  async getWorkflow(workflowId) {
    const doc = await firestore.db.collection('workflows').doc(workflowId).get();
    if (!doc.exists) return null;
    return { id: doc.id, ...doc.data() };
  }

  /**
   * Update a workflow by ID
   * @param {string} workflowId 
   * @param {Object} updates 
   */
  async updateWorkflow(workflowId, updates) {
    const workflowRef = firestore.db.collection('workflows').doc(workflowId);
    updates.updatedAt = new Date();
    await workflowRef.update(updates);
    // Return updated doc
    const updatedDoc = await workflowRef.get();
    return { id: workflowId, ...updatedDoc.data() };
  }

  /**
   * Delete a workflow by ID
   * @param {string} workflowId 
   */
  async deleteWorkflow(workflowId) {
    await firestore.db.collection('workflows').doc(workflowId).delete();
    return true;
  }
}

export default new WorkflowService();