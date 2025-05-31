// First, let's create a new database schema for managing shared access
// backend/src/models/sharedAccess.js
import { Firestore } from '@google-cloud/firestore';
const firestore = new Firestore();

// Utility function to generate a unique share ID
const generateShareId = () => {
  return 'share_' + Math.random().toString(36).substr(2, 9);
};

// Create a new shared access record
const createSharedAccess = async (assistantId, createdBy) => {
  const shareId = generateShareId();
  const sharedAccessRef = firestore.collection('shared_access').doc(shareId);
  
  await sharedAccessRef.set({
    shareId,
    assistantId,
    createdBy,
    createdAt: Firestore.FieldValue.serverTimestamp(),
    isActive: true,
    lastAccessedAt: null
  });
  
  return shareId;
};

// Verify if a share link is valid and active
const verifySharedAccess = async (shareId) => {
  const accessDoc = await firestore.collection('shared_access').doc(shareId).get();
  
  if (!accessDoc.exists) {
    throw new Error('Share link not found');
  }
  
  const accessData = accessDoc.data();
  if (!accessData.isActive) {
    throw new Error('Share link has been revoked');
  }
  
  // Update last accessed timestamp
  await accessDoc.ref.update({
    lastAccessedAt: Firestore.FieldValue.serverTimestamp()
  });
  
  return accessData;
};

// Revoke shared access
const revokeSharedAccess = async (shareId, userId) => {
  const accessDoc = await firestore.collection('shared_access').doc(shareId).get();
  
  if (!accessDoc.exists) {
    throw new Error('Share link not found');
  }
  
  const accessData = accessDoc.data();
  if (accessData.createdBy !== userId) {
    throw new Error('Unauthorized to revoke this share link');
  }
  
  await accessDoc.ref.update({
    isActive: false,
    revokedAt: Firestore.FieldValue.serverTimestamp()
  });
};

// Get all shared access for an assistant
const getSharedAccess = async (assistantId, userId) => {
  const snapshot = await firestore.collection('shared_access')
    .where('assistantId', '==', assistantId)
    .where('createdBy', '==', userId)
    .get();
    
  const shares = [];
  snapshot.forEach(doc => {
    shares.push({
      id: doc.id,
      ...doc.data()
    });
  });
  
  return shares;
};

export {
  createSharedAccess,
  verifySharedAccess,
  revokeSharedAccess,
  getSharedAccess
};
