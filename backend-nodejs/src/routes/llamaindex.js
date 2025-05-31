// backend/src/routes/llamaindex.js
import express from 'express';
import axios from 'axios';
import multer from 'multer';
import path from 'path';

const router = express.Router();

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, 'uploads/');
  },
  filename: function (req, file, cb) {
    cb(null, Date.now() + path.extname(file.originalname));
  }
});

const upload = multer({ storage: storage });

// Configuration for Python FastAPI service
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:8000';

// Create Index Endpoint
router.post('/llamaindex/create', upload.array('files'), async (req, res) => {
  try {
    const { indexType, indexParams } = req.body;
    
    // Process uploaded files
    const userInputs = req.files.map(file => ({
      type: 'local_file',
      payload: file.path,
      columns: req.body.columns ? JSON.parse(req.body.columns) : undefined,
      row_range: req.body.row_range
    }));

    // Add any raw text inputs if provided
    if (req.body.rawText) {
      userInputs.push({
        type: 'raw_text',
        payload: req.body.rawText
      });
    }

    const response = await axios.post(`${PYTHON_SERVICE_URL}/api/create_index`, {
      index_type: indexType,
      index_params: JSON.parse(indexParams),
      user_inputs: userInputs
    });

    res.json(response.data);
  } catch (error) {
    console.error('Error creating index:', error);
    res.status(500).json({
      error: 'Failed to create index',
      details: error.message
    });
  }
});

// Query Index Endpoint
router.post('/llamaindex/query', async (req, res) => {
  try {
    const { indexId, queryParams } = req.body;

    const response = await axios.post(`${PYTHON_SERVICE_URL}/api/query_index`, {
      index_id: indexId,
      query_params: queryParams
    });

    res.json(response.data);
  } catch (error) {
    console.error('Error querying index:', error);
    res.status(500).json({
      error: 'Failed to query index',
      details: error.message
    });
  }
});

// Health Check Endpoint
router.get('/llamaindex/health', async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON_SERVICE_URL}/health`);
    res.json(response.data);
  } catch (error) {
    res.status(503).json({
      status: 'unavailable',
      error: 'Python service is not responding'
    });
  }
});

export default router;