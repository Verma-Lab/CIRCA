// backend/src/routes/shared-links.js
import express from 'express';
import { verifyToken, checkResourceOwnership } from '../middleware/auth.js';
import firestore from '../services/db/firestore.js';
import { nanoid } from 'nanoid';
const router = express.Router();

// Create a new shared link
router.get('/assistants/:assistantId/shares', verifyToken, async (req, res) => {
    try {
      const { assistantId } = req.params;
      const userId = req.user.id;  // This comes from the verifyToken middleware
  
      // Get the assistant to check ownership
      const assistant = await firestore.getAssistant(assistantId);
      
      console.log('Assistant:', assistant);  // Debug log
      console.log('Request user:', req.user);  // Debug log
  
      // Check if assistant exists and user owns it
      if (!assistant) {
        return res.status(404).json({ error: 'Assistant not found' });
      }
  
      // If the assistant doesn't have a userId field, let's add it
      if (!assistant.userId) {
        await firestore.updateAssistant(assistantId, {
          userId: userId
        });
      }
  
      // Get all shares for this assistant
      const shares = await firestore.db.collection('shared_links')
        .where('assistantId', '==', assistantId)
        .get();
  
      const sharesList = [];
      shares.forEach(doc => {
        sharesList.push({
          id: doc.id,
          ...doc.data()
        });
      });
  
      res.json(sharesList);
  
    } catch (error) {
      console.error('Error fetching shares:', error);
      res.status(500).json({ error: 'Failed to fetch shares' });
    }
  });
  
  // Create a new shared link
  // router.post('/assistants/:assistantId/share', verifyToken, async (req, res) => {
  //   try {
  //     const { assistantId } = req.params;
  //     const userId = req.user.id;
  
  //     // Add debug logging
  //     console.log('Creating share link for assistant:', assistantId);
  //     console.log('User ID:', userId);
  
  //     // Get the assistant
  //     const assistant = await firestore.getAssistant(assistantId);
      
  //     if (!assistant) {
  //       console.log('Assistant not found:', assistantId);
  //       return res.status(404).json({ error: 'Assistant not found' });
  //     }
  
  //     console.log('Found assistant:', assistant);
  
  //     // If the assistant doesn't have a userId, update it
  //     if (!assistant.userId) {
  //       await firestore.updateAssistant(assistantId, {
  //         userId: userId
  //       });
  //       console.log('Updated assistant with userId:', userId);
  //     }
  
  //     // Generate a unique share ID
  //     const shareId = nanoid(16);
  //     console.log('Generated shareId:', shareId);
      
  //     // Create the share record
  //     const shareData = {
  //       shareId,
  //       assistantId,
  //       userId: userId,
  //       createdAt: new Date(),
  //       isActive: true,
  //       accessCount: 0,
  //       lastAccessed: null
  //     };
  
  //     const share = await firestore.createShareLink(shareData);
  //     console.log('Created share link:', share);
  
  //     res.status(201).json({
  //       id: share.id,
  //       ...shareData
  //     });
  
  //   } catch (error) {
  //     console.error('Error creating share:', error);
  //     res.status(500).json({ error: 'Failed to create share link' });
  //   }
  // });
  // Update the createShareLink route in shared-links.js
router.post('/assistants/:assistantId/share', verifyToken, async (req, res) => {
  try {
    const { assistantId } = req.params;
    const { type = 'chat', tone = 'professional', responseStyle = 'detailed',
      complexityLevel = 'intermediate',
      interactionStyle = 'collaborative', voiceName = null,
      patientId   } = req.body; // Add tone parameter
    const userId = req.user.id;

    console.log('Creating share link for assistant:', assistantId);
    console.log('User ID:', userId);
    console.log('Share type:', type);
    console.log("CHECKING LINK CREATION")
    console.log('VOICE NAME SET', voiceName)
    console.log(tone, responseStyle, complexityLevel, interactionStyle) 
    console.log('PATIENT ID ADDED', patientId)
    const assistant = await firestore.getAssistant(assistantId);
    
    if (!assistant) {
      console.log('Assistant not found:', assistantId);
      return res.status(404).json({ error: 'Assistant not found' });
    }

    console.log('Found assistant:', assistant);

    if (!assistant.userId) {
      await firestore.updateAssistant(assistantId, {
        userId: userId
      });
      console.log('Updated assistant with userId:', userId);
    }

    const shareId = nanoid(16);
    console.log('Generated shareId:', shareId);
    
    const shareData = {
      shareId,
      assistantId,
      userId: userId,
      type: type, // Add type field
      tone: tone, // Add tone to shareData
      responseStyle,
      complexityLevel,
      interactionStyle,
      voiceName,
      patientId, 
      createdAt: new Date(),
      isActive: true,
      accessCount: 0,
      lastAccessed: null
    };

    const share = await firestore.createShareLink(shareData);
    console.log('Created share link:', share);

    res.status(201).json({
      id: share.id,
      ...shareData
    });

  } catch (error) {
    console.error('Error creating share:', error);
    res.status(500).json({ error: 'Failed to create share link' });
  }
});
// Revoke a shared link
router.post('/shares/:shareId/revoke', verifyToken, async (req, res) => {
  try {
    const { shareId } = req.params;
    const userId = req.user.id;

    // Get share data
    const shareSnapshot = await firestore.db.collection('shared_links')
      .where('shareId', '==', shareId)
      .limit(1)
      .get();

    if (shareSnapshot.empty) {
      return res.status(404).json({ error: 'Share link not found' });
    }

    const shareDoc = shareSnapshot.docs[0];
    const shareData = shareDoc.data();

    // Check ownership using userId instead of ownerId
    if (shareData.userId !== userId) {
      return res.status(403).json({ error: 'Not authorized to revoke this share link' });
    }

    // Update share status
    await shareDoc.ref.update({
      isActive: false,
      revokedAt: new Date()
    });

    res.json({ 
      message: 'Share link revoked successfully',
      shareId: shareId
    });
    
  } catch (error) {
    console.error('Error revoking share link:', error);
    res.status(500).json({ error: 'Failed to revoke share link' });
  }
});
// router.get('/shared/:shareId/verify', async (req, res) => {
//     try {
//       const { shareId } = req.params;
//       console.log('Verifying shareId:', shareId);
  
//       // Find the share link
//       const shareSnapshot = await firestore.db.collection('shared_links')
//         .where('shareId', '==', shareId)
//         .where('isActive', '==', true)
//         .limit(1)
//         .get();
  
//       console.log('Share snapshot empty:', shareSnapshot.empty);
  
//       if (shareSnapshot.empty) {
//         console.log('Share link not found or inactive:', shareId);
//         return res.status(404).json({ error: 'Share link not found or inactive' });
//       }
  
//       const shareDoc = shareSnapshot.docs[0];
//       const shareData = shareDoc.data();
//       console.log('Share data:', shareData);
  
//       // Get assistant info
//       const assistantDoc = await firestore.db.collection('assistants')
//         .doc(shareData.assistantId)
//         .get();
  
//       console.log('Assistant exists:', assistantDoc.exists);
  
//       if (!assistantDoc.exists) {
//         console.log('Assistant not found for share:', shareData.assistantId);
//         return res.status(404).json({ error: 'Assistant not found' });
//       }
  
//       // Update access count
//       await shareDoc.ref.update({
//         accessCount: shareData.accessCount + 1,
//         lastAccessed: new Date()
//       });
  
//       res.json({
//         share: {
//           id: shareDoc.id,
//           ...shareData
//         },
//         assistant: {
//           id: assistantDoc.id,
//           name: assistantDoc.data().name,
//           description: assistantDoc.data().description
//         }
//       });
//     } catch (error) {
//       console.error('Share verification error:', error);
//       res.status(500).json({ error: 'Failed to verify share link' });
//     }
//   });
// Update the verification route
router.get('/shared/:shareId/verify', async (req, res) => {
  try {
    const { shareId } = req.params;
    console.log('Verifying shareId:', shareId);

    const shareSnapshot = await firestore.db.collection('shared_links')
      .where('shareId', '==', shareId)
      .where('isActive', '==', true)
      .limit(1)
      .get();

    console.log('Share snapshot empty:', shareSnapshot.empty);

    if (shareSnapshot.empty) {
      console.log('Share link not found or inactive:', shareId);
      return res.status(404).json({ error: 'Share link not found or inactive' });
    }

    const shareDoc = shareSnapshot.docs[0];
    const shareData = shareDoc.data();
    console.log('Share data:', shareData);

    const assistantDoc = await firestore.db.collection('assistants')
      .doc(shareData.assistantId)
      .get();

    console.log('Assistant exists:', assistantDoc.exists);

    if (!assistantDoc.exists) {
      console.log('Assistant not found for share:', shareData.assistantId);
      return res.status(404).json({ error: 'Assistant not found' });
    }

    // Update access count
    await shareDoc.ref.update({
      accessCount: shareData.accessCount + 1,
      lastAccessed: new Date()
    });

    res.json({
      share: {
        id: shareDoc.id,
        type: shareData.type || 'chat', // Include type in response, default to 'chat'
        tone: shareData.tone || 'professional',
        responseStyle: shareData.responseStyle || 'detailed',
        complexityLevel: shareData.complexityLevel || 'intermediate',
        interactionStyle: shareData.interactionStyle || 'collaborative',
        patientId: shareData.patientId || '',
        ...shareData
      },
      assistant: {
        id: assistantDoc.id,
        ...assistantDoc.data() // This will include all assistant data
    }
    });
  } catch (error) {
    console.error('Share verification error:', error);
    res.status(500).json({ error: 'Failed to verify share link' });
  }
});
// Get dashboard analytics for a user's assistants
// router.get('/dashboard/analytics', verifyToken, async (req, res) => {
//   try {
//     const userId = req.user.id; // From verifyToken middleware

//     // First get all assistants for this user
//     const assistantsSnapshot = await firestore.db.collection('assistants')
//       .where('userId', '==', userId)
//       .get();

//     // Get all share data for these assistants
//     const assistantIds = assistantsSnapshot.docs.map(doc => doc.id);
//     const sharesSnapshot = await firestore.db.collection('shared_links')
//       .where('assistantId', 'in', assistantIds)
//       .get();

//     // Create a map to store analytics per assistant
//     const assistantAnalytics = {};

//     // Initialize analytics for each assistant
//     assistantsSnapshot.docs.forEach(doc => {
//       const assistantData = doc.data();
//       assistantAnalytics[doc.id] = {
//         id: doc.id,
//         name: assistantData.name,
//         totalAccess: 0,
//         activeShares: 0,
//         lastAccessed: null,
//         documentCount: assistantData.documentCount || 0,
//         status: assistantData.status || 'draft',
//         shares: []
//       };
//     });

//     // Process share data
//     sharesSnapshot.docs.forEach(doc => {
//       const shareData = doc.data();
//       const analytics = assistantAnalytics[shareData.assistantId];
      
//       if (analytics) {
//         analytics.totalAccess += shareData.accessCount || 0;
//         if (shareData.isActive) {
//           analytics.activeShares++;
//         }
//         if (shareData.lastAccessed) {
//           const lastAccess = shareData.lastAccessed.toDate();
//           if (!analytics.lastAccessed || lastAccess > analytics.lastAccessed) {
//             analytics.lastAccessed = lastAccess;
//           }
//         }
//         // Store share data for timeline analysis
//         analytics.shares.push({
//           id: doc.id,
//           createdAt: shareData.createdAt.toDate(),
//           accessCount: shareData.accessCount || 0,
//           lastAccessed: shareData.lastAccessed ? shareData.lastAccessed.toDate() : null
//         });
//       }
//     });

//     // Calculate overall statistics
//     const overallStats = {
//       totalAssistants: assistantIds.length,
//       totalAccess: 0,
//       activeAssistants: 0,
//       totalShares: sharesSnapshot.size,
//       assistantStats: Object.values(assistantAnalytics).map(assistant => ({
//         id: assistant.id,
//         name: assistant.name,
//         accessCount: assistant.totalAccess,
//         activeShares: assistant.activeShares,
//         documentCount: assistant.documentCount,
//         status: assistant.status
//       })),
//       // Add timeline data for the chart
//       timelineData: Object.values(assistantAnalytics).map(assistant => {
//         // Sort shares by date and aggregate access counts
//         const sortedShares = assistant.shares.sort((a, b) => 
//           a.createdAt.getTime() - b.createdAt.getTime()
//         );
        
//         // Create timeline points
//         return {
//           assistantId: assistant.id,
//           assistantName: assistant.name,
//           timeline: sortedShares.map(share => ({
//             date: share.createdAt.toISOString().split('T')[0],
//             accessCount: share.accessCount
//           }))
//         };
//       })
//     };

//     // Calculate total stats
//     overallStats.totalAccess = Object.values(assistantAnalytics)
//       .reduce((sum, assistant) => sum + assistant.totalAccess, 0);
    
//     overallStats.activeAssistants = Object.values(assistantAnalytics)
//       .filter(assistant => assistant.status === 'deployed').length;

//     res.json(overallStats);

//   } catch (error) {
//     console.error('Error fetching dashboard analytics:', error);
//     res.status(500).json({ error: 'Failed to fetch dashboard analytics' });
//   }
// });
// Modified dashboard analytics route
router.get('/dashboard/analytics', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // First get all assistants for this user
    const assistantsSnapshot = await firestore.db.collection('assistants')
      .where('userId', '==', userId)
      .get();

    const assistantIds = assistantsSnapshot.docs.map(doc => doc.id);

    // Initialize analytics map
    const assistantAnalytics = {};
    assistantsSnapshot.docs.forEach(doc => {
      const assistantData = doc.data();
      assistantAnalytics[doc.id] = {
        id: doc.id,
        name: assistantData.name,
        totalAccess: 0,
        activeShares: 0,
        lastAccessed: null,
        documentCount: assistantData.documentCount || 0,
        status: assistantData.status || 'draft',
        shares: []
      };
    });

    // Process shares in batches of 30
    for (let i = 0; i < assistantIds.length; i += 30) {
      const batchIds = assistantIds.slice(i, i + 30);
      const batchSharesSnapshot = await firestore.db.collection('shared_links')
        .where('assistantId', 'in', batchIds)
        .get();

      // Process share data for this batch
      batchSharesSnapshot.docs.forEach(doc => {
        const shareData = doc.data();
        const analytics = assistantAnalytics[shareData.assistantId];
        
        if (analytics) {
          analytics.totalAccess += shareData.accessCount || 0;
          if (shareData.isActive) {
            analytics.activeShares++;
          }
          if (shareData.lastAccessed) {
            const lastAccess = shareData.lastAccessed.toDate();
            if (!analytics.lastAccessed || lastAccess > analytics.lastAccessed) {
              analytics.lastAccessed = lastAccess;
            }
          }
          analytics.shares.push({
            id: doc.id,
            createdAt: shareData.createdAt.toDate(),
            accessCount: shareData.accessCount || 0,
            lastAccessed: shareData.lastAccessed ? shareData.lastAccessed.toDate() : null
          });
        }
      });
    }

    // Calculate overall statistics
    const overallStats = {
      totalAssistants: assistantIds.length,
      totalAccess: 0,
      activeAssistants: 0,
      totalShares: 0,
      assistantStats: Object.values(assistantAnalytics).map(assistant => ({
        id: assistant.id,
        name: assistant.name,
        accessCount: assistant.totalAccess,
        activeShares: assistant.activeShares,
        documentCount: assistant.documentCount,
        status: assistant.status
      })),
      timelineData: Object.values(assistantAnalytics).map(assistant => {
        const sortedShares = assistant.shares.sort((a, b) => 
          a.createdAt.getTime() - b.createdAt.getTime()
        );
        
        return {
          assistantId: assistant.id,
          assistantName: assistant.name,
          timeline: sortedShares.map(share => ({
            date: share.createdAt.toISOString().split('T')[0],
            accessCount: share.accessCount
          }))
        };
      })
    };

    // Calculate total stats
    overallStats.totalAccess = Object.values(assistantAnalytics)
      .reduce((sum, assistant) => sum + assistant.totalAccess, 0);
    
    overallStats.activeAssistants = Object.values(assistantAnalytics)
      .filter(assistant => assistant.status === 'deployed').length;

    overallStats.totalShares = Object.values(assistantAnalytics)
      .reduce((sum, assistant) => sum + assistant.shares.length, 0);

    res.json(overallStats);

  } catch (error) {
    console.error('Error fetching dashboard analytics:', error);
    res.status(500).json({ error: 'Failed to fetch dashboard analytics' });
  }
});

// In your backend routes
router.get('/assistants/:assistantId/chat-analytics', verifyToken, async (req, res) => {
  try {
    const { assistantId } = req.params;
    const userId = req.user.id;

    // Get all chat messages for this assistant
    const messagesSnapshot = await firestore.db.collection('chat_messages')
      .where('assistantId', '==', assistantId)
      .get();

    // Process messages to extract words and their frequencies
    const words = {};
    const stopWords = new Set(['the', 'is', 'at', 'which', 'on', 'the', 'a', 'an', 'and', 'or', 'but']); // Add more as needed

    messagesSnapshot.forEach(doc => {
      const message = doc.data();
      if (message.content) {
        const tokens = message.content.toLowerCase()
          .split(/\W+/)
          .filter(word => 
            word.length > 2 && 
            !stopWords.has(word) &&
            !word.match(/^\d+$/)
          );

        tokens.forEach(word => {
          words[word] = (words[word] || 0) + 1;
        });
      }
    });

    // Convert to format needed for word cloud
    const wordCloudData = Object.entries(words).map(([text, value]) => ({
      text,
      value
    }));

    res.json(wordCloudData);
  } catch (error) {
    console.error('Error generating chat analytics:', error);
    res.status(500).json({ error: 'Failed to generate chat analytics' });
  }
});
// Add or update this route in your shared-links.js file

router.post('/assistants/:assistantId/primary-voice-share', verifyToken, async (req, res) => {
  try {
    const { assistantId } = req.params;
    const { shareId } = req.body;
    const userId = req.user.id;

    // 1) Get the assistant
    const assistant = await firestore.getAssistant(assistantId);
    if (!assistant) {
      return res.status(404).json({ error: 'Assistant not found' });
    }

    // 2) Verify ownership
    if (assistant.userId !== userId) {
      return res.status(403).json({ error: 'Not authorized to modify this assistant' });
    }

    // 3) Verify that the share exists and belongs to this assistant
    const shareSnap = await firestore.db.collection('shared_links')
      .where('shareId', '==', shareId)
      .where('assistantId', '==', assistantId)
      .limit(1)
      .get();

    if (shareSnap.empty) {
      return res.status(400).json({ 
        error: 'Share not found or does not belong to this assistant' 
      });
    }

    // 4) Update the assistant with the new primary voice share
    await firestore.updateAssistant(assistantId, { 
      voiceShareId: shareId 
    });

    // 5) Return success response
    return res.json({ 
      success: true, 
      voiceShareId: shareId,
      message: 'Primary voice share updated successfully'
    });

  } catch (error) {
    console.error('Error setting primary voice share:', error);
    return res.status(500).json({ 
      error: 'Failed to set primary voice share' 
    });
  }
});

export default router;