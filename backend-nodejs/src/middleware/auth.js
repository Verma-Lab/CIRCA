// backend/src/middleware/auth.js

import jwt from 'jsonwebtoken';
import firestore from '../services/db/firestore.js';

export const verifyToken = async (req, res, next) => {
  try {
    const token = req.headers.authorization?.split(' ')[1];
    
    if (!token) {
      return res.status(401).json({ error: 'No token provided' });
    }

    try {
      // Verify the token
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      
      // Get user data
      const userDoc = await firestore.db.collection('users').doc(decoded.userId).get();
      
      if (!userDoc.exists) {
        return res.status(401).json({ error: 'User not found' });
      }

      // Add user data to request object
      req.user = {
        id: userDoc.id,
        ...userDoc.data(),
        password: undefined // Remove sensitive data
      };

      next();
    } catch (error) {
      if (error.name === 'JsonWebTokenError') {
        return res.status(401).json({ error: 'Invalid token' });
      }
      if (error.name === 'TokenExpiredError') {
        return res.status(401).json({ error: 'Token expired' });
      }
      throw error;
    }
  } catch (error) {
    console.error('Auth middleware error:', error);
    res.status(500).json({ error: 'Authentication failed' });
  }
};

// Optional: Add resource ownership verification
export const checkResourceOwnership = (resourceType) => {
  return async (req, res, next) => {
    try {
      const userId = req.user.id;
      const resourceId = req.params[`${resourceType}Id`];

      const resourceDoc = await firestore.db.collection(resourceType)
        .doc(resourceId)
        .get();

      if (!resourceDoc.exists) {
        return res.status(404).json({ error: `${resourceType} not found` });
      }

      if (resourceDoc.data().userId !== userId) {
        return res.status(403).json({ error: 'Unauthorized access to resource' });
      }

      // Add the resource data to the request
      req[resourceType] = {
        id: resourceDoc.id,
        ...resourceDoc.data()
      };

      next();
    } catch (error) {
      console.error('Resource ownership check failed:', error);
      res.status(500).json({ error: 'Failed to verify resource ownership' });
    }
  };
};