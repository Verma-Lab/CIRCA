// backend/src/routes/slack-events.js
// COMPLETE CODE EXAMPLE: This file shows how to:
// 1) Receive Slack events (user messages) via Event Subscriptions
// 2) Map Slack team/user to your assistant (via Firestore 'integrations' collection)
// 3) Forward each Slack message into the same logic used by /shared/:shareId/chat
// 4) Post the AI's response back to Slack

import express from 'express';
import axios from 'axios';
import firestore from '../services/db/firestore.js'; 
// If your /shared/:shareId/chat logic is in the same server, we'll call it internally.
// Otherwise, you might import the functions directly. For example:
import dotenv from 'dotenv';
dotenv.config();

const router = express.Router();

/*
    1) Slack must be configured with "Event Subscriptions" → "Request URL" = 
       e.g. https://your-api.com/api/slack/events

    2) Under "Subscribe to bot events," add:
       - message.im (for direct messages)
       - app_mention (if you want #channel mentions)
    
    3) Slack will POST an "event_callback" JSON here whenever user messages the bot.
    4) We'll parse the text, find which assistant is connected, call the AI logic,
       then post the response back.
*/

// Slack demands a quick verification challenge the first time you add the URL
router.post('/events', async (req, res) => {
  // 1) Handle Slack's "challenge" request
  if (req.body.type === 'url_verification') {
    // Slack is verifying your endpoint. Just return the challenge token.
    return res.send(req.body.challenge);
  }

  // 2) Otherwise, it's an event_callback
  if (req.body.type === 'event_callback') {
    const event = req.body.event || {};

    // Slack often sends multiple event types. We'll only handle a "message" from a user.
    // Also skip if it's a bot posting, to avoid loops (bot_id present).
    if (
      event.type === 'message' &&
      !event.bot_id && 
      event.text
    ) {
      const userMessage = event.text;           // The user's message content
      const channelId = event.channel;          // Where we need to post back
      const teamId = req.body.team_id;          // The Slack workspace/team ID
      const userId = event.user;                // The Slack user ID who typed the message

      try {
        // 3) Find which assistant is connected to this Slack workspace (teamId)
        //    We stored workspaceId = team.id from OAuth in 'integrations'.
        //    So let's query "integrations" by platform='slack' AND workspaceId=teamId
        const integrationSnap = await firestore.db.collection('integrations')
          .where('platform', '==', 'slack')
          .where('workspaceId', '==', teamId)
          .where('status', '==', 'active')
          .limit(1)
          .get();

        if (integrationSnap.empty) {
          // No matching assistant. Possibly not integrated or was disconnected.
          // We can politely respond or ignore. For now, let's respond with an error.
          await postSlackMessage({
            token: null, // we don't have a valid token
            channel: channelId,
            text: "No active Slack integration found for this workspace."
          });
          return res.sendStatus(200);
        }

        // We have an integration doc => The connected assistant
        const integrationDoc = integrationSnap.docs[0];
        const integrationData = integrationDoc.data();
        const { assistantId, accessToken } = integrationData;
        
        // 4) We must call the same logic as /shared/:shareId/chat
        //    However, your "shared chat" route requires a shareId in the URL.
        //    You have 2 main approaches:
        //      (a) Store a fixed shareId in the integration doc
        //      (b) Directly call the underlying AI logic. 
        //    Below, we'll show approach (a) if we assume you store shareId in "integrationData.settings.shareId"

        const shareId = integrationData.settings?.shareId;
        if (!shareId) {
          // If you never saved a shareId, you'll need to store/lookup it differently
          await postSlackMessage({
            token: accessToken,
            channel: channelId,
            text: "No shareId found in this Slack integration. Cannot route message to assistant."
          });
          return res.sendStatus(200);
        }

        // 5) We'll call your /shared/:shareId/chat endpoint internally, sending the user's Slack text
        //    so that the same appointment + AI logic runs. We'll pass sessionId = userId so context is kept.
        const backendUrl = `${process.env.API_URL || 'http://localhost:3003'}/api/shared/${shareId}/chat`;

        // We do a POST, passing { message, sessionId }
        // (If your shared route needs an auth token, supply it accordingly.)
        const aiResponse = await axios.post(backendUrl, {
          message: userMessage,
          sessionId: userId,
          language: 'en'
        });
        
        // The AI's text is aiResponse.data.content
        const replyText = aiResponse.data.content || '(No response)';
        
        // 6) Now post that AI reply back to Slack in the same channel (DM or public)
        await postSlackMessage({
          token: accessToken,
          channel: channelId,
          text: replyText
        });

      } catch (err) {
        console.error('Slack event processing error:', err);
        // Optionally post an error message back
      }
    }
    // Slack needs a 200 quickly
    return res.sendStatus(200);
  }

  // If we get here, just return 200
  return res.sendStatus(200);
});

/**
 * Helper function to post a message to Slack using the Bot Token
 */
async function postSlackMessage({ token, channel, text }) {
  if (!token) {
    console.log('No valid Slack token provided. Cannot post message.');
    return;
  }
  try {
    await axios.post('https://slack.com/api/chat.postMessage', {
      channel,
      text
    }, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
  } catch (error) {
    console.error('Error posting Slack message:', error.response?.data || error.message);
  }
}

export default router;

/* ---------------------------------------------------------------------------
   ADDITIONAL NOTES:

   1) You must add an "Event Subscription" in your Slack App settings:
      - App's "Event Subscriptions" → turn "On"
      - Request URL = https://your-api.com/api/slack/events  (points to this route)
      - Under "Subscribe to bot events," add "message.im" for direct messages,
        "app_mention" for channel mentions, etc.
      - Reinstall the Slack app so it has the new event permissions.

   2) Your 'integrationData.settings.shareId' approach:
      - When you create the Slack integration in 'createIntegration()',
        you can store { shareId: 'abc123' } in settings if you want each
        assistant to have a stable shareId. For example:

        await firestore.createIntegration({
          assistantId,
          platform: 'slack',
          workspaceId: slackTeamId,
          accessToken: access_token,
          settings: {
            teamName: slackTeamName,
            botUserId: bot_user_id,
            shareId: 'SHARE_ID_FOR_THIS_ASSISTANT'
          }
        });

   3) If you do NOT want to store shareId, you can store only 'assistantId'
      and bypass your /shared route by calling the same AI logic directly.

   4) In backend/src/index.js, mount this route:
      import slackEvents from './routes/slack-events.js';
      app.use('/api/slack', slackEvents);

   5) Now Slack's event requests will arrive at POST /api/slack/events,
      your code above will parse them, call your /shared route, and
      respond to Slack with the AI's message.
--------------------------------------------------------------------------- */
