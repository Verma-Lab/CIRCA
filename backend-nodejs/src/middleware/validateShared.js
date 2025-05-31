// backend/src/middleware/validateShared.js
import firestore from '../services/db/firestore.js';

export const validateSharedAccess = async (req, res, next) => {
  try {
    console.log('loading chats',  req.params, req.query)

    const { shareId } = req.params;

    // Get share link using your firestore service
    const share = await firestore.getShareLink(shareId);
    
    if (!share || !share.isActive) {
      return res.status(403).json({ error: 'Invalid or revoked share link' });
    }

    // Update access statistics
    await firestore.updateShareLink(shareId, {
      accessCount: share.accessCount + 1,
      lastAccessed: new Date()
    });

    // Add share data to request
    req.shareData = share;
    next();
  } catch (error) {
    console.error('Error validating shared access:', error);
    res.status(500).json({ error: 'Failed to validate access' });
  }
};