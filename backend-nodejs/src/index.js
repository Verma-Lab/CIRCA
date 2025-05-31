// backend/src/index.js
'use strict';

import express from 'express';
import cors from 'cors';
import morgan from 'morgan';
import dotenv from 'dotenv';
import authRoutes from './routes/auth.js';
import assistantRoutes from './routes/assistant.js';
import documentRoutes from './routes/documents.js';
import deploymentRoutes from './routes/deployment.js';  // Add this
import sharedLinks from './routes/shared-link.js';
import sharedChat from './routes/shared-chat.js';
import calendarRoutes from './routes/calendar.js';
import paymentRoutes from './routes/payments.js'
import oauth from './routes/oauth.js'
import slackEvents from './routes/slack-events.js'
import workflowRoutes from './routes/workflowRoutes.js';
import gmailRoutes from './routes/gmail.js';
import docsAndSheetsRoutes from './routes/googleoffice.js'
import qwenRoutes from './routes/qwenRoutes.js';
import voiceRoutes from './routes/voices.js';  // Import voices routes
import twilioRoute from './routes/twilioRoutes.js'
import contactRoutes from './routes/contact.js';
import metricsRouter from './routes/metrics.js';
import conversationalAssistantRouter from './routes/conversationalAssistant.js';
import llamaindexRoutes from './routes/llamaindex.js';
import patientRoutes from './routes/Patients.js';
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3003;
const allowedOrigins = [
  'https://www.smynk.com',
  'https://smynk.com',
  'https://smynk-frontend.onrender.com', // Add your Render domain
  'http://localhost:3000',  // For local development
  'http://localhost:3001',  // For local development
  'https://www.tellephon.com', 
  'https://tellephon.com', 
  'https://smynk-frontend.vercel.app',
    'https://0139-2601-47-4a82-47f0-c925-8a6c-e19e-e217.ngrok-free.app',
  'https://fa51-2601-47-4a82-47f0-c925-8a6c-e19e-e217.ngrok-free.app',
  'https://disease-frontend.vercel.app',
  'https://www.homosapieus.com',
  'https://homosapieus.com',
];

//Cors Configuration
app.use(cors({
  origin: function(origin, callback) {
    // Allow requests with no origin (like mobile apps or curl requests)
    if (!origin) return callback(null, true);
    
    if (allowedOrigins.indexOf(origin) === -1) {
      const msg = 'The CORS policy for this site does not allow access from the specified Origin.';
      return callback(new Error(msg), false);
    }
    return callback(null, true);
  },
  credentials: true,  // Allow credentials (cookies, authorization headers, etc.)
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'Cache-Control', 'Pragma']
}));

// Middleware
app.use(express.json());
app.use(morgan('dev'));

// Routes
app.use('/api', qwenRoutes);
app.use('/api/auth', authRoutes);
app.use('/api/assistants', assistantRoutes);
app.use('/api/documents', documentRoutes);
app.use('/api', deploymentRoutes);  // Add this - note we're using '/api' as base path
app.use('/api', sharedLinks); // This will handle /api/assistants/:assistantId/share endpoints
app.use('/api', sharedChat);  // This will handle /api/shared/:shareId/chat endpoints
app.use('/api', documentRoutes)
app.use('/api/calendar', calendarRoutes);
app.use('/api/payments', paymentRoutes);
app.use('/api/integrations', oauth)
app.use('/api/slack', slackEvents)
app.use('/api/workflows', workflowRoutes);
app.use('/api/gmail', gmailRoutes);
app.use('/api/docs-sheets', docsAndSheetsRoutes);
app.use('/api', voiceRoutes);  // Use the voices routes
app.use('/api', twilioRoute)
app.use('/api', contactRoutes);
app.use('/api', metricsRouter);
app.use('/api/conversation', conversationalAssistantRouter);
app.use('/api', llamaindexRoutes);
app.use('/api', patientRoutes);


// ADD THIS SECTION HERE
try {
  console.log('----------------------------------------');
  console.log('Initializing patient data updater service...');
  import('./routes/patient-data-updater.js')
    .then(() => {
      console.log('Patient data updater service initialized');
      console.log('----------------------------------------');
    })
    .catch(error => {
      console.error('Error initializing patient data updater service:', error);
      console.error('----------------------------------------');
    });
} catch (error) {
  console.error('----------------------------------------');
  console.error('Critical error loading patient data updater:', error);
  console.error('----------------------------------------');
}

//health Check
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});
// Error handling
app.use((err, req, res, next) => {
  console.error(err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal Server Error'
  });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});