// backend/src/routes/analytics.js
import express from 'express';
import { Firestore } from '@google-cloud/firestore';

const router = express.Router();
const firestore = new Firestore();

// Get assistant usage analytics
router.get('/assistants/:assistantId', async (req, res) => {
  try {
    const { assistantId } = req.params;
    const { period = '7d' } = req.query;

    // Calculate start date based on period
    const startDate = new Date();
    switch (period) {
      case '24h':
        startDate.setHours(startDate.getHours() - 24);
        break;
      case '7d':
        startDate.setDate(startDate.getDate() - 7);
        break;
      case '30d':
        startDate.setDate(startDate.getDate() - 30);
        break;
      default:
        startDate.setDate(startDate.getDate() - 7);
    }

    // Get usage data
    const usageSnapshot = await firestore
      .collection('assistant_usage')
      .where('assistantId', '==', assistantId)
      .where('timestamp', '>=', startDate)
      .orderBy('timestamp', 'asc')
      .get();

    const usageData = [];
    usageSnapshot.forEach(doc => {
      usageData.push(doc.data());
    });

    // Get error logs
    const errorSnapshot = await firestore
      .collection('error_logs')
      .where('assistantId', '==', assistantId)
      .where('timestamp', '>=', startDate)
      .orderBy('timestamp', 'desc')
      .limit(100)
      .get();

    const errorLogs = [];
    errorSnapshot.forEach(doc => {
      errorLogs.push(doc.data());
    });

    // Calculate metrics
    const metrics = {
      totalQueries: usageData.reduce((sum, data) => sum + data.queryCount, 0),
      averageResponseTime: usageData.reduce((sum, data) => sum + data.averageResponseTime, 0) / usageData.length || 0,
      successRate: (usageData.reduce((sum, data) => sum + data.successCount, 0) / 
                   usageData.reduce((sum, data) => sum + data.queryCount, 0)) * 100 || 0,
      errorCount: errorLogs.length
    };

    res.json({
      metrics,
      usageData,
      errorLogs
    });
  } catch (error) {
    console.error('Error fetching analytics:', error);
    res.status(500).json({ error: 'Failed to fetch analytics' });
  }
});

// Log assistant usage
router.post('/log/:assistantId', async (req, res) => {
  try {
    const { assistantId } = req.params;
    const { 
      queryCount = 1,
      responseTime,
      success = true,
      error = null
    } = req.body;

    // Log usage
    const usageRef = firestore.collection('assistant_usage').doc();
    await usageRef.set({
      id: usageRef.id,
      assistantId,
      queryCount,
      responseTime,
      success,
      timestamp: Firestore.FieldValue.serverTimestamp()
    });

    // Log error if present
    if (error) {
      const errorRef = firestore.collection('error_logs').doc();
      await errorRef.set({
        id: errorRef.id,
        assistantId,
        error,
        timestamp: Firestore.FieldValue.serverTimestamp()
      });
    }

    // Update assistant stats
    await firestore.collection('assistants').doc(assistantId).update({
      queryCount: Firestore.FieldValue.increment(queryCount),
      lastUsed: Firestore.FieldValue.serverTimestamp()
    });

    res.json({ message: 'Usage logged successfully' });
  } catch (error) {
    console.error('Error logging usage:', error);
    res.status(500).json({ error: 'Failed to log usage' });
  }
});

// Get overall platform analytics
router.get('/platform', async (req, res) => {
  try {
    const { period = '7d' } = req.query;
    const startDate = new Date();
    
    switch (period) {
      case '24h':
        startDate.setHours(startDate.getHours() - 24);
        break;
      case '7d':
        startDate.setDate(startDate.getDate() - 7);
        break;
      case '30d':
        startDate.setDate(startDate.getDate() - 30);
        break;
    }

    // Get platform-wide stats
    const [assistantsSnapshot, usageSnapshot] = await Promise.all([
      firestore.collection('assistants').get(),
      firestore.collection('assistant_usage')
        .where('timestamp', '>=', startDate)
        .get()
    ]);

    const platformMetrics = {
      totalAssistants: assistantsSnapshot.size,
      activeAssistants: 0,
      totalQueries: 0,
      averageResponseTime: 0,
      successRate: 0
    };

    // Calculate active assistants and aggregate metrics
    const usageData = [];
    usageSnapshot.forEach(doc => {
      const data = doc.data();
      usageData.push(data);
      platformMetrics.totalQueries += data.queryCount;
      platformMetrics.averageResponseTime += data.responseTime;
    });

    platformMetrics.averageResponseTime /= usageData.length || 1;
    platformMetrics.successRate = (usageData.filter(d => d.success).length / usageData.length) * 100 || 0;

    // Count active assistants (used in the period)
    const activeAssistants = new Set(usageData.map(d => d.assistantId));
    platformMetrics.activeAssistants = activeAssistants.size;

    res.json({
      metrics: platformMetrics,
      period
    });
  } catch (error) {
    console.error('Error fetching platform analytics:', error);
    res.status(500).json({ error: 'Failed to fetch platform analytics' });
  }
});

export default router;