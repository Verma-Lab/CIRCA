// backend/src/services/patient-data-updater.js
import cron from 'node-cron';
import axios from 'axios';
import firestore from '../services/db/firestore.js';

const PYTHON_API_URL = "https://app.homosapieus.com";
const DEBUG_MODE = true; // Enable detailed logging
const SESSION_FRESHNESS_MINUTES = 5; // Time window for analyzing recent sessions

// Add more visible startup logging
console.log('----------------------------------------');
console.log('[DATA UPDATER] Initializing patient data updater module');

/**
 * Formats a date to EDT (UTC-4) for logging
 * @param {Date} date - The date to format
 * @returns {string} - Formatted date string in EDT
 */
function formatToEDT(date) {
  return date.toLocaleString('en-US', {
    timeZone: 'America/New_York', // EDT is UTC-4
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }) + ' EDT';
}

/**
 * Session analyzer cron job handler
 * Runs every 2 minutes to find and analyze recent chat sessions
 */
async function runSessionAnalyzer() {
  const currentTime = new Date();
  console.log('[DATA UPDATER] Running session analyzer:', formatToEDT(currentTime));
  
  try {
    // Get all unique patient IDs from Firestore
    // console.log('[DATA UPDATER] Finding all unique patients in chat sessions');
    
    // Query Firestore for all sessions with patient IDs
    const sessionsWithPatientsSnapshot = await firestore.db.collection('chat_sessions')
      .where('patientId', '!=', null)
      .get();
    
    if (sessionsWithPatientsSnapshot.empty) {
      console.log('[DATA UPDATER] No sessions with patient IDs found');
      return;
    }
    
    // Extract unique patient IDs
    const patientIds = new Set();
    sessionsWithPatientsSnapshot.forEach(doc => {
      const session = doc.data();
      if (session.patientId) {
        patientIds.add(session.patientId);
      }
    });
    
    // console.log(`[DATA UPDATER] Found ${patientIds.size} unique patients with chat sessions`);
    
    let successCount = 0;
    let errorCount = 0;
    
    // Process each patient
    for (const patientId of patientIds) {
        // console.log(`[DATA UPDATER] Processing patient ${patientId}`);
        
        try {
          // Get the most recent session for this patient
          const patientSessionsSnapshot = await firestore.db.collection('chat_sessions')
            .where('patientId', '==', patientId)
            .orderBy('createdAt', 'desc')
            .limit(2) // Get the last two sessions
            .get();
          
          if (patientSessionsSnapshot.empty) {
            console.log(`[DATA UPDATER] No sessions found for patient ${patientId}`);
            continue;
          }
          
          // Get the most recent session (current session to analyze)
          const sessionDoc = patientSessionsSnapshot.docs[0];
          const sessionId = sessionDoc.id;
          const session = sessionDoc.data();
          const createdAt = session.createdAt?.toDate ? session.createdAt.toDate() : new Date(session.createdAt);
          
          // console.log(`[DATA UPDATER] Found most recent session ${sessionId} for patient ${patientId}`);
          
          // Check if session is within freshness window
          const timeDiffMinutes = (currentTime - createdAt) / (1000 * 60);
          if (timeDiffMinutes > SESSION_FRESHNESS_MINUTES) {
            console.log(`[DATA UPDATER] Skipping analysis for session ${sessionId} (too old)`);
            continue;
          }
          
          // Check for previous session (second-to-last)
          let previousSessionSummary = null;
          let previousSessionDate = null;
          if (patientSessionsSnapshot.docs.length > 1) {
            const prevSessionDoc = patientSessionsSnapshot.docs[1];
            const prevSessionId = prevSessionDoc.id;
            const prevSessionData = prevSessionDoc.data();
            // previousSessionDate = prevSessionData.createdAt?.toDate ? prevSessionData.createdAt.toDate().toISOString().split('T')[0] : null;
            previousSessionDate = prevSessionData.createdAt?.toDate 
                ? formatToEDT(prevSessionData.createdAt.toDate())
                : null;
    
            console.log('PREV SESSION DATE', previousSessionDate)
            // Fetch the summary from patient_session_summaries
            const prevSummarySnapshot = await firestore.db.collection('patient_session_summaries')
              .doc(prevSessionId)
              .get();
            
            if (prevSummarySnapshot.exists) {
              const prevSummaryData = prevSummarySnapshot.data();
              previousSessionSummary = prevSummaryData.summary;
              console.log(`[DATA UPDATER] Found previous session summary for session ${prevSessionId}`);
            } else {
              console.log(`[DATA UPDATER] No summary found for previous session ${prevSessionId}`);
            }
          } else {
            console.log(`[DATA UPDATER] No previous session found for patient ${patientId}`);
          }
          
          // Call the Python API to analyze the session, passing the previous summary if available
          console.log(`[DATA UPDATER] Analyzing session ${sessionId} for patient ${patientId}`);
          const response = await axios.post(`${PYTHON_API_URL}/api/analyze-session`, {
            sessionId: sessionId,
            patientId: patientId,
            previousSessionSummary: previousSessionSummary ,// Add previous summary to request
            previousSessionDate: previousSessionDate // Add previous session date
          });
          
          // Rest of the code remains the same
          if (response.data.status === 'success') {
            const updates = response.data.updates_made;
            const extractedData = response.data.extracted_data;
            console.log('RESPONSE DATA SESSION SUMMARY', response.data.session_summary);
            
            if (response.data.session_summary) {
              try {
                const summaryData = {
                  patientId: patientId,
                  sessionId: sessionId,
                  summary: response.data.session_summary,
                  createdAt: new Date().toISOString(),
                  extractedData: DEBUG_MODE ? extractedData : null,
                  updatesApplied: updates
                };
                
                await firestore.db.collection('patient_session_summaries').doc(sessionId).set(summaryData);
                console.log(`[DATA UPDATER] Stored session summary for session ${sessionId}`);
                
                await firestore.db.collection('chat_sessions').doc(sessionId).update({
                  hasSummary: true,
                  summaryContent: response.data.session_summary,
                  summaryCreatedAt: new Date().toISOString()
                });
              
            } catch (summaryError) {
              console.error(`[DATA UPDATER] Error storing session summary:`, summaryError.message);
            }
          }
          if (DEBUG_MODE) {
            console.log(`[DATA UPDATER] [DEBUG] LLM extracted data:`, JSON.stringify(extractedData, null, 2));
            
            // Show confidence scores to understand why data might not be updating
            if (extractedData.confidence_scores) {
              console.log(`[DATA UPDATER] [DEBUG] Confidence scores:`);
              const scores = extractedData.confidence_scores;
              Object.keys(scores).forEach(key => {
                console.log(`[DATA UPDATER] [DEBUG]   - ${key}: ${scores[key]}/100 (threshold: ${key === 'conditions' || key === 'medications' ? '70' : '75'})`);
              });
            }
            
            // Check if any patient fields were extracted but not updated due to confidence
            if (extractedData.patient_details && !updates.patient_details_updated) {
              console.log(`[DATA UPDATER] [DEBUG] Patient fields not updated because:`);
              const details = extractedData.patient_details;
              Object.keys(details).forEach(key => {
                if (details[key]) {
                  const scoreKey = key.includes('name') ? 'name' : key === 'date_of_birth' ? 'dob' : key;
                  const score = extractedData.confidence_scores[scoreKey] || 0;
                  console.log(`[DATA UPDATER] [DEBUG]   - ${key}: "${details[key]}" (confidence: ${score}/100, needs 75+)`);
                }
              });
            }
          }
          
          console.log(`[DATA UPDATER] Session ${sessionId} analysis complete:`, {
            patient_updated: updates.patient_details_updated,
            conditions_added: updates.medical_conditions_added,
            medications_added: updates.medications_added,
            allergies_added: updates.allergies_added,
            updated_fields: updates.updated_fields
          });
          
          // Update Firestore to mark as analyzed
          try {
            // Use set with merge to handle cases where some fields might not exist
            await firestore.db.collection('chat_sessions').doc(sessionId).set({
              lastDataAnalysis: new Date().toISOString(),
              dataAnalysisStatus: 'success',
              dataAnalysisResults: updates,
              dataAnalysisExtractedData: DEBUG_MODE ? extractedData : null
            }, { merge: true });
            
            console.log(`[DATA UPDATER] Successfully updated Firestore for session ${sessionId}`);
            successCount++;
          } catch (updateError) {
            console.error(`[DATA UPDATER] Error updating Firestore:`, updateError.message);
            errorCount++;
          }
        } else {
          console.error(`[DATA UPDATER] Session ${sessionId} analysis failed: ${response.data.message}`);
          errorCount++;
          
          // Update Firestore with failure status
          try {
            await firestore.db.collection('chat_sessions').doc(sessionId).set({
              lastDataAnalysis: new Date().toISOString(),
              dataAnalysisStatus: 'failed',
              dataAnalysisError: response.data.message
            }, { merge: true });
          } catch (updateError) {
            console.error(`[DATA UPDATER] Error updating Firestore:`, updateError.message);
          }
        }
      } catch (error) {
        console.error(`[DATA UPDATER] Error processing patient ${patientId}:`, error.message);
        errorCount++;
      }
      
      // Add a small delay between patients to avoid overwhelming the API
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    console.log(`[DATA UPDATER] Analysis complete: ${successCount} succeeded, ${errorCount} failed`);
    
  } catch (error) {
    console.error('[DATA UPDATER] Error in session analyzer:', error.message);
    console.error('[DATA UPDATER] Error stack:', error.stack);
  }
}

try {
  // Setup the cron job to run every 2 minutes
  console.log('[DATA UPDATER] Creating cron job (*/2 * * * *)');
  const patientDataUpdater = cron.schedule('*/2 * * * *', runSessionAnalyzer);

  // Start the scheduler
  patientDataUpdater.start();
  console.log('[DATA UPDATER] Patient data updater scheduler started (runs every 2 minutes)');
  console.log('----------------------------------------');
  
  // Run once immediately
  console.log('[DATA UPDATER] Running initial analysis on startup');
  runSessionAnalyzer().catch(error => {
    console.error('[DATA UPDATER] Error in initial analysis:', error.message);
  });
} catch (error) {
  console.error('----------------------------------------');
  console.error('[DATA UPDATER] CRITICAL ERROR initializing cron job:', error.message);
  console.error('[DATA UPDATER] Error stack:', error.stack);
  console.error('----------------------------------------');
}

export default runSessionAnalyzer;