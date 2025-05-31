// routes/qwenRoutes.js
import express from 'express';
import qwenService from '../services/ai/qwen/service.js';
import qwenTraining from '../services/ai/qwen/training.js';
import { verifyToken } from '../middleware/auth.js';

const router = express.Router();

// Get training status
router.get('/assistants/:assistantId/qwen-training', async (req, res) => {
    try {
        const { assistantId } = req.params;
        const status = await qwenTraining.getTrainingStatus(assistantId);
        res.json(status);
    } catch (error) {
        console.error('Training status error:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get model endpoints
router.get('/assistants/:assistantId/qwen-endpoints', async (req, res) => {
    try {
        const { assistantId } = req.params;
        const endpoints = await qwenService.listEndpoints(assistantId);
        res.json(endpoints);
    } catch (error) {
        console.error('Endpoints listing error:', error);
        res.status(500).json({ error: error.message });
    }
});

// Ask question to Qwen model
router.post('/assistants/:assistantId/qwen-query', async (req, res) => {
    try {
        const { assistantId } = req.params;
        const { question } = req.body;
        
        const response = await qwenService.predict(assistantId, question);
        res.json(response);
    } catch (error) {
        console.error('Query error:', error);
        res.status(500).json({ error: error.message });
    }
});

export default router;