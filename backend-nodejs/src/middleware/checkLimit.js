// backend/src/middleware/checkLimits.js
import firestore from '../services/db/firestore.js';

export const checkLimits = async (req, res, next) => {
  try {
    const userId = req.user.id;
    const user = await firestore.getUser(userId);
    
    switch(req.path) {
      case '/':
        if (req.method === 'POST') {
          const assistantCount = await firestore.getUserAssistantCount(userId);
          console.log(user)
          if (user.limits.maxAssistants !== -1 && assistantCount >= user.limits.maxAssistants) {
            return res.status(403).json({ error: `Assistant limit reached for ${user.plan} plan` });
          }
        }
        break;
        
        case '/documents':
            if (req.method === 'POST') {
                const documentCount = await firestore.getUserDocumentCount(userId);
                console.log('Current document count:', documentCount);
                console.log('User document limit:', user.limits.documents);
                
                // Using user.limits directly like in the assistant case
                if (user.limits.documents !== -1 && documentCount >= user.limits.documents) {
                    return res.status(403).json({ 
                        error: `Document limit reached for ${user.plan} plan`,
                        currentCount: documentCount,
                        limit: user.limits.documents
                    });
                }
                // Increment document usage if check passes
                await firestore.incrementUserUsage(userId, 'documents');
            }
            break;

            default:
                if (req.path.includes('/chat')) {
                  if (!await firestore.checkUserLimit(userId, 'monthlyInteractions')) {
                    return res.status(403).json({ error: `Monthly interaction limit reached` });
                  }
                  // Increment interaction usage if check passes
                  await firestore.incrementUserUsage(userId, 'interactions');
                }
    }
    next();
  } catch (error) {
    res.status(500).json({ error: 'Error checking limits' });
  }
};