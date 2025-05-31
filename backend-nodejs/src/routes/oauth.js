// backend/src/routes/oauth.js
import express from 'express';
import axios from 'axios';
import firestore from '../services/db/firestore.js';
import { verifyToken } from '../middleware/auth.js'; 

const router = express.Router();

// Slack OAuth Configuration
const SLACK_CLIENT_ID = process.env.SLACK_CLIENT_ID;
const SLACK_CLIENT_SECRET = process.env.SLACK_CLIENT_SECRET;
const SLACK_REDIRECT_URI = process.env.SLACK_REDIRECT_URI;

// Microsoft Teams OAuth Configuration
const TEAMS_CLIENT_ID = process.env.TEAMS_CLIENT_ID;
const TEAMS_CLIENT_SECRET = process.env.TEAMS_CLIENT_SECRET;
const TEAMS_REDIRECT_URI = process.env.TEAMS_REDIRECT_URI;

/**
 * POST /slack/connect
 * This endpoint returns the Slack auth URL. 
 * The frontend uses it to redirect the user to Slack.
 */
router.post('/slack/connect', verifyToken, (req, res) => {
    const { assistantId } = req.body;
    if (!assistantId) {
      return res.status(400).json({ error: 'Assistant ID is required' });
    }
  
    // We'll encode the assistantId in state
    const state = Buffer.from(JSON.stringify({ assistantId })).toString('base64');
  
    // Build the Slack OAuth URL
    const authUrl = `https://slack.com/oauth/v2/authorize?client_id=${SLACK_CLIENT_ID}` +
      `&scope=chat:write,channels:read,im:write,im:read,app_mentions:read` +
      `&redirect_uri=${SLACK_REDIRECT_URI}` +
      `&state=${state}`;
  
    // Return it to the client in JSON so client can do `window.location.href = authUrl`
    return res.json({ authUrl });
  });
  
  /**
   * GET /slack/callback
   * Slack redirects here with ?code=... and ?state=...
   * We'll exchange the code for an access token, store in Firestore.
   */
  router.get('/slack/callback', async (req, res) => {
    try {
      const { code, state } = req.query;
      if (!code || !state) {
        return res.status(400).send('Invalid Slack OAuth callback');
      }
  
      // Decode the state to retrieve assistantId
      const { assistantId } = JSON.parse(Buffer.from(state, 'base64').toString());
  
      // Exchange code -> token
      const tokenResponse = await axios.post('https://slack.com/api/oauth.v2.access', null, {
        params: {
          client_id: SLACK_CLIENT_ID,
          client_secret: SLACK_CLIENT_SECRET,
          code,
          redirect_uri: SLACK_REDIRECT_URI
        }
      });
      const data = tokenResponse.data;
  
      // Slack response typically has { ok, access_token, team, bot_user_id, ... }
      if (!data.ok) {
        console.error('Slack OAuth error data:', data);
        return res.redirect(`${process.env.FRONTEND_URL}/dashboard/integrations?status=error&platform=slack`);
      }
  
      const { access_token, team, bot_user_id } = data;
  
      // Create or update the Integration record in Firestore
      await firestore.createIntegration({
        // The function you have in FirestoreService
        assistantId: assistantId,
        platform: 'slack',
        workspaceId: team?.id,
        accessToken: access_token,
        botId: bot_user_id,
        settings: {
          teamName: team?.name,
          botUserId: bot_user_id
        }
        // userId might be necessary if you want to store the user who connected Slack
      });
  
      // Redirect user back to your UI
      res.redirect(`${process.env.FRONTEND_URL}/dashboard/integrations?status=success&platform=slack`);
    } catch (error) {
      console.error('Slack OAuth callback error:', error);
      return res.redirect(`${process.env.FRONTEND_URL}/dashboard/integrations?status=error&platform=slack`);
    }
  });
  
  /**
   * POST /slack/disconnect
   * This route sets the integration status to 'inactive' 
   * so the user effectively disconnects Slack from that assistant
   */
  router.post('/slack/disconnect', verifyToken, async (req, res) => {
    try {
      const { assistantId } = req.body;
      if (!assistantId) {
        return res.status(400).json({ error: 'Assistant ID is required' });
      }
  
      // Find the Slack integration for this assistant
      // E.g. fetch the doc from `integrations` where assistantId = ? and platform = 'slack'
      const slackIntegrations = await firestore.db.collection('integrations')
        .where('assistantId', '==', assistantId)
        .where('platform', '==', 'slack')
        .where('status', '==', 'active')
        .get();
  
      if (slackIntegrations.empty) {
        return res.status(404).json({ error: 'No active Slack integration found for this assistant' });
      }
  
      // Mark them as 'inactive'
      const batch = firestore.db.batch();
      slackIntegrations.forEach(doc => {
        batch.update(doc.ref, { status: 'inactive', updatedAt: new Date() });
      });
      await batch.commit();
  
      return res.json({ message: 'Slack disconnected successfully' });
    } catch (err) {
      console.error('Error disconnecting Slack:', err);
      res.status(500).json({ error: 'Failed to disconnect Slack' });
    }
  });

// Initiate Microsoft Teams OAuth
router.get('/teams', async (req, res) => {
  const { assistantId } = req.query;
  if (!assistantId) {
    return res.status(400).json({ error: 'Assistant ID is required' });
  }

  const state = Buffer.from(JSON.stringify({ assistantId })).toString('base64');

  const authUrl = `https://login.microsoftonline.com/common/oauth2/v2.0/authorize` +
    `?client_id=${TEAMS_CLIENT_ID}` +
    `&response_type=code` +
    `&redirect_uri=${TEAMS_REDIRECT_URI}` +
    `&scope=offline_access Chat.ReadWrite ChatMessage.Send` +
    `&state=${state}`;

  res.redirect(authUrl);
});

// Microsoft Teams OAuth Callback
router.get('/teams/callback', async (req, res) => {
  const { code, state } = req.query;

  try {
    // Decode state to get assistantId
    const { assistantId } = JSON.parse(Buffer.from(state, 'base64').toString());

    // Exchange code for access token
    const response = await axios.post('https://login.microsoftonline.com/common/oauth2/v2.0/token', null, {
      params: {
        client_id: TEAMS_CLIENT_ID,
        client_secret: TEAMS_CLIENT_SECRET,
        code,
        redirect_uri: TEAMS_REDIRECT_URI,
        grant_type: 'authorization_code'
      }
    });

    const { access_token, refresh_token } = response.data;

    // Get Teams/tenant info
    const teamsInfo = await axios.get('https://graph.microsoft.com/v1.0/me', {
      headers: { Authorization: `Bearer ${access_token}` }
    });

    // Save integration details
    await firestore.createIntegration({
      assistantId,
      platform: 'teams',
      workspaceId: teamsInfo.data.id,
      accessToken: access_token,
      refreshToken: refresh_token,
      settings: {
        tenantId: teamsInfo.data.id,
        userName: teamsInfo.data.displayName
      }
    });

    res.redirect(`${process.env.FRONTEND_URL}/dashboard/integrations?status=success&platform=teams`);
  } catch (error) {
    console.error('Teams OAuth error:', error);
    res.redirect(`${process.env.FRONTEND_URL}/dashboard/integrations?status=error&platform=teams`);
  }
});

export default router;