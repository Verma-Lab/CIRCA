// backend/src/routes/calendar.js
import express from 'express';
import { verifyToken } from '../middleware/auth.js';
import { google } from 'googleapis';
import { Client } from '@microsoft/microsoft-graph-client';
import { getAuthenticatedClient } from '../services/microsoft/auth.js';
import { Firestore } from '@google-cloud/firestore';
import crypto from 'crypto';
import * as chrono from 'chrono-node';
import { DateTime } from 'luxon'; // Import Luxon

const router = express.Router();
// const firestore = new Firestore();
const firestore = new Firestore({
  projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
  keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  databaseId: 'circa'  // Explicitly specify the database name
});

// Store for temporary state parameters
const stateStore = new Map();

// Google Calendar OAuth configuration
const oauth2Client = new google.auth.OAuth2(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
  process.env.GOOGLE_REDIRECT_URI
);

// Get calendar integration status
router.get('/status', verifyToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const userDoc = await firestore.collection('users').doc(userId).get();
    const userData = userDoc.data();

    const status = {
      google: Boolean(userData?.googleCalendarToken),
      microsoft: Boolean(userData?.microsoftCalendarToken)
    };

    res.json(status);
  } catch (error) {
    console.error('Error getting calendar status:', error);
    res.status(500).json({ error: 'Failed to get calendar status' });
  }
});

// Connect Google Calendar
router.get('/auth/google-calendar', verifyToken, (req, res) => {
    try {
      // Generate a unique state parameter
      const state = crypto.randomBytes(16).toString('hex');
      
      // Store the user ID with the state parameter
      stateStore.set(state, {
        userId: req.user.id,
        timestamp: Date.now()
      });
  
      // Clean up old state entries
      for (const [key, value] of stateStore.entries()) {
        if (Date.now() - value.timestamp > 5 * 60 * 1000) { // 5 minutes
          stateStore.delete(key);
        }
      }
  
      const authUrl = oauth2Client.generateAuthUrl({
        access_type: 'offline',
        scope: ['https://www.googleapis.com/auth/calendar'],
        redirect_uri: process.env.GOOGLE_REDIRECT_URI,
        state: state,
        prompt: 'consent'
      });
      res.json({ url: authUrl });
    } catch (error) {
      console.error('Error generating auth URL:', error);
      res.status(500).json({ error: 'Failed to generate authorization URL' });
    }
  });

// Google Calendar OAuth callback
router.get('/auth/google-calendar/callback', async (req, res) => {
    try {
      const { code, state } = req.query;
  
      if (!state || !stateStore.has(state)) {
        throw new Error('Invalid state parameter');
      }
  
      const { userId } = stateStore.get(state);
      stateStore.delete(state); // Clean up used state
  
      const { tokens } = await oauth2Client.getToken(code);
      
      // Store tokens in Firestore
      await firestore.collection('users').doc(userId).update({
        googleCalendarToken: tokens,
        googleCalendarConnected: true,
        lastUpdated: new Date().toISOString()
      });
  
      // Redirect to frontend
      res.redirect(`${process.env.FRONTEND_URL}/dashboard?calendar=connected`);
    } catch (error) {
      console.error('Google Calendar auth error:', error);
      res.redirect(`${process.env.FRONTEND_URL}/dashboard?calendar=error&message=${encodeURIComponent(error.message)}`);
    }
  });
  

// Connect Microsoft Calendar
router.get('/auth/microsoft-calendar', verifyToken, (req, res) => {
  // Generate Microsoft auth URL
  const authUrl = `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?
    client_id=${process.env.MICROSOFT_CLIENT_ID}
    &response_type=code
    &redirect_uri=${process.env.MICROSOFT_REDIRECT_URI}
    &scope=Calendars.ReadWrite`;
  
  res.json({ url: authUrl });
});

// Microsoft Calendar OAuth callback
router.get('/auth/microsoft-calendar/callback', verifyToken, async (req, res) => {
  try {
    const { code } = req.query;
    // Exchange code for tokens using Microsoft Graph API
    const tokens = await getAuthenticatedClient(code);
    
    await firestore.collection('users').doc(req.user.id).update({
      microsoftCalendarToken: tokens,
      microsoftCalendarConnected: true
    });

    res.redirect('/dashboard?calendar=connected');
  } catch (error) {
    console.error('Microsoft Calendar auth error:', error);
    res.redirect('/dashboard?calendar=error');
  }
});

// Get calendar availability
router.get('/availability', verifyToken, async (req, res) => {
    try {
      const { date, startTime, endTime, calendarType = 'google' } = req.query;
      const userId = req.user.id;
      const userDoc = await firestore.collection('users').doc(userId).get();
      const userData = userDoc.data();
  
      if (calendarType === 'google') {
        if (!userData?.googleCalendarToken) {
          return res.status(401).json({ error: 'Google Calendar not connected' });
        }
  
        oauth2Client.setCredentials(userData.googleCalendarToken);
        const calendar = google.calendar({ version: 'v3', auth: oauth2Client });
  
        // Handle both date-only and start/end time scenarios
        let timeMin, timeMax;
        
        if (startTime && endTime) {
          // If specific start and end times are provided
          timeMin = new Date(startTime);
          timeMax = new Date(endTime);
        } else if (date) {
          // If only date is provided, check full day
          timeMin = new Date(date);
          timeMax = new Date(date);
          timeMax.setHours(23, 59, 59);
        } else {
          // Default to current day if no date/time specified
          timeMin = new Date();
          timeMax = new Date();
          timeMax.setHours(23, 59, 59);
        }
  
        console.log('Checking availability for:', {
          timeMin: timeMin.toISOString(),
          timeMax: timeMax.toISOString()
        });
  
        const response = await calendar.freebusy.query({
          requestBody: {
            timeMin: timeMin.toISOString(),
            timeMax: timeMax.toISOString(),
            items: [{ id: 'primary' }]
          }
        });
  
        res.json(response.data);
      } else if (calendarType === 'microsoft') {
        if (!userData?.microsoftCalendarToken) {
          return res.status(401).json({ error: 'Microsoft Calendar not connected' });
        }
  
        const client = Client.init({
          authProvider: (done) => {
            done(null, userData.microsoftCalendarToken.accessToken);
          }
        });
  
        const response = await client
          .api('/me/calendar/getSchedule')
          .post({
            schedules: ['primary'],
            startTime: { dateTime: new Date(date).toISOString() },
            endTime: { dateTime: new Date(new Date(date).setHours(23, 59, 59)).toISOString() }
          });
  
        res.json(response);
      }
    } catch (error) {
      console.error('Error getting calendar availability:', error);
      res.status(500).json({ error: 'Failed to get calendar availability', details: error.message });
    }
  });

// Schedule calendar event
// Get calendar events

router.get('/events', verifyToken, async (req, res) => {
    try {
      const { date, startTime, endTime, query } = req.query;
      const userId = req.user.id;
      const userDoc = await firestore.collection('users').doc(userId).get();
      const userData = userDoc.data();
  
      if (!userData?.googleCalendarToken) {
        return res.status(401).json({ error: 'Google Calendar not connected' });
      }
  
      oauth2Client.setCredentials(userData.googleCalendarToken);
      const calendar = google.calendar({ version: 'v3', auth: oauth2Client });
  
      // Handle natural language date queries
      let timeMin, timeMax;
      
      if (query) {
        // Parse natural language query
        const parsedDate = chrono.parse(query);
        if (parsedDate.length > 0) {
          const startDate = parsedDate[0].start.date();
          timeMin = new Date(startDate);
          timeMin.setHours(0, 0, 0, 0);
          
          timeMax = new Date(startDate);
          timeMax.setHours(23, 59, 59, 999);
        }
      } else if (startTime && endTime) {
        timeMin = new Date(startTime);
        timeMax = new Date(endTime);
      } else if (date) {
        timeMin = new Date(date);
        timeMin.setHours(0, 0, 0, 0);
        timeMax = new Date(date);
        timeMax.setHours(23, 59, 59, 999);
      } else {
        // Default to current day
        timeMin = new Date();
        timeMin.setHours(0, 0, 0, 0);
        timeMax = new Date();
        timeMax.setHours(23, 59, 59, 999);
      }
  
      const response = await calendar.events.list({
        calendarId: 'primary',
        timeMin: timeMin.toISOString(),
        timeMax: timeMax.toISOString(),
        orderBy: 'startTime',
        singleEvents: true
      });
  
      res.json({
        events: response.data.items,
        timeMin: timeMin.toISOString(),
        timeMax: timeMax.toISOString()
      });
    } catch (error) {
      console.error('Error getting calendar events:', error);
      res.status(500).json({ error: 'Failed to get calendar events', details: error.message });
    }
  });
  router.patch('/events/:eventId', verifyToken, async (req, res) => {
    try {
      const { eventId } = req.params;
      const { title, description, start, end, attendees } = req.body; // Expect start and end as objects
      const userId = req.user.id;
      const userDoc = await firestore.collection('users').doc(userId).get();
      const userData = userDoc.data();
  
      if (!userData?.googleCalendarToken) {
        return res.status(401).json({ error: 'Google Calendar not connected' });
      }
  
      oauth2Client.setCredentials(userData.googleCalendarToken);
      const calendar = google.calendar({ version: 'v3', auth: oauth2Client });
  
      // Get existing event
      const existingEvent = await calendar.events.get({
        calendarId: 'primary',
        eventId: eventId
      });
  
      // Update event with new details while preserving existing ones
      const updatedEvent = {
        ...existingEvent.data,
        summary: title || existingEvent.data.summary,
        description: description || existingEvent.data.description,
        start: start
          ? {
              dateTime: DateTime.fromISO(start.dateTime, { zone: start.timeZone }).toISO(),
              timeZone: start.timeZone
            }
          : existingEvent.data.start,
        end: end
          ? {
              dateTime: DateTime.fromISO(end.dateTime, { zone: end.timeZone }).toISO(),
              timeZone: end.timeZone
            }
          : existingEvent.data.end,
        attendees: attendees ? attendees.map(email => ({ email })) : existingEvent.data.attendees
      };
  
      console.log('Updating event with data:', updatedEvent);
  
      const response = await calendar.events.update({
        calendarId: 'primary',
        eventId: eventId,
        requestBody: updatedEvent,
        sendUpdates: 'all'
      });
  
      console.log('Update response:', response.data);
  
      res.json(response.data);
    } catch (error) {
      console.error('Error updating calendar event:', error);
      res.status(500).json({ error: 'Failed to update event', details: error.message });
    }
  });
  router.delete('/events/:eventId', verifyToken, async (req, res) => {
    try {
      const { eventId } = req.params;
      const userId = req.user.id;
      const userDoc = await firestore.collection('users').doc(userId).get();
      const userData = userDoc.data();
  
      if (!userData?.googleCalendarToken) {
        return res.status(401).json({ error: 'Google Calendar not connected' });
      }
  
      oauth2Client.setCredentials(userData.googleCalendarToken);
      const calendar = google.calendar({ version: 'v3', auth: oauth2Client });
  
      await calendar.events.delete({
        calendarId: 'primary',
        eventId: eventId
      });
  
      res.json({ message: 'Event deleted successfully' });
    } catch (error) {
      console.error('Error deleting calendar event:', error);
      res.status(500).json({ error: 'Failed to delete event', details: error.message });
    }
  });
// In your calendar.js route, update the events endpoint:
// Add this new route for getting user settings
router.get('/settings', verifyToken, async (req, res) => {
    try {
      const userId = req.user.id;
      const userDoc = await firestore.collection('users').doc(userId).get();
      const userData = userDoc.data();
  
      oauth2Client.setCredentials(userData.googleCalendarToken);
      const calendar = google.calendar({ version: 'v3', auth: oauth2Client });
      
      const timeZoneResponse = await calendar.settings.get({
        setting: 'timezone'
      });
  
      res.json({
        timeZone: timeZoneResponse.data.value
      });
    } catch (error) {
      console.error('Error getting user settings:', error);
      res.status(500).json({ error: 'Failed to get user settings' });
    }
  });
  
  // Update the event creation route
  router.post('/events', verifyToken, async (req, res) => {
    try {
      const { title, description, start, end, attendees } = req.body;
      
      console.log('Creating calendar event with details:', {
        title,
        description,
        start,
        end,
        attendees
      });
  
      const userId = req.user.id;
      const userDoc = await firestore.collection('users').doc(userId).get();
      const userData = userDoc.data();
  
      if (!userData?.googleCalendarToken) {
        console.log('Google Calendar not connected for user:', userId);
        return res.status(401).json({ error: 'Google Calendar not connected' });
      }
  
      if (!start?.dateTime || !end?.dateTime || !start?.timeZone || !end?.timeZone) {
        console.log('Missing required fields:', { start, end });
        return res.status(400).json({
          error: 'Missing required fields',
          details: 'start and end must include dateTime and timeZone'
        });
      }
  
      oauth2Client.setCredentials(userData.googleCalendarToken);
      const calendar = google.calendar({ version: 'v3', auth: oauth2Client });
  
      const event = {
        summary: title || 'Appointment',
        description: description || '',
        start: {
          dateTime: start.dateTime,  // Don't do additional conversion
          timeZone: start.timeZone
        },
        end: {
          dateTime: end.dateTime,  // Don't do additional conversion
          timeZone: end.timeZone
        },
        attendees: attendees?.map(email => ({ email })) || []
      };
  
      console.log('Sending event creation request:', event);
  
      const response = await calendar.events.insert({
        calendarId: 'primary',
        requestBody: event,
        sendUpdates: 'all'
      });
  
      console.log('Event created successfully:', response.data);
      res.json(response.data);
    } catch (error) {
      console.error('Error creating calendar event:', {
        error: error.message,
        stack: error.stack,
        response: error.response?.data
      });
      
      res.status(500).json({
        error: 'Failed to schedule calendar event',
        details: error.message
      });
    }
  });
export default router;