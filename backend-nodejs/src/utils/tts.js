// backend/src/utils/tts.js
import textToSpeech from '@google-cloud/text-to-speech';
const client = new textToSpeech.TextToSpeechClient();

// export default async function streamTextToSpeech(
//     text,
//     language = 'en',
//     res,
//     voiceName = null
//   ) {
//     // If a voice name is passed, try to extract the first two segments (e.g. en-US)
//     // from something like: "en-US-Studio-O" => "en-US"
//     let derivedLanguageCode = language; // fallback if we can't parse voiceName
//     if (voiceName) {
//       const maybeMatch = voiceName.match(/^([a-z]{2}-[A-Z]{2})/);
//       if (maybeMatch) {
//         derivedLanguageCode = maybeMatch[1]; 
//         // e.g. "en-US" if voiceName is "en-US-Studio-O"
//       }
//     }
  
//     const request = {
//       input: { text },
//       voice: {
//         languageCode: derivedLanguageCode,
//         name: voiceName || `${language}-Wavenet-D`,
//       },
//       audioConfig: { audioEncoding: 'MP3' },
//     };
  
//     console.log('Voice Request:', request);
  
//     const [response] = await client.synthesizeSpeech(request);
//     const audioContent = response.audioContent;
    
//     res.setHeader('Content-Type', 'audio/mpeg');
//     res.send(audioContent);
//   }
export default async function streamTextToSpeech(
  text,
  language = 'en',
  res,
  voiceName = null
) {
  // If a voice name is passed, try to extract the first two segments (e.g. en-US)
  // from something like: "en-US-Studio-O" => "en-US"
  let derivedLanguageCode = language; // fallback if we can't parse voiceName
  if (voiceName) {
    const maybeMatch = voiceName.match(/^([a-z]{2}-[A-Z]{2})/);
    if (maybeMatch) {
      derivedLanguageCode = maybeMatch[1]; 
      // e.g. "en-US" if voiceName is "en-US-Studio-O"
    }
  }

  const request = {
    input: { text },
    voice: {
      languageCode: derivedLanguageCode,
      name: voiceName || `${language}-Wavenet-D`,
    },
    audioConfig: { audioEncoding: 'MP3' },
  };

  console.log('Voice Request:', request);

  const [response] = await client.synthesizeSpeech(request);
  const audioContent = response.audioContent;
  
  res.setHeader('Content-Type', 'audio/mpeg');
  res.send(audioContent);
}
// import fetch from 'node-fetch';
// import fs from 'fs';
// import FormData from 'form-data';
// import path from 'path';

// export default async function streamTextToSpeech(text, language = 'en', res) {
//     try {
//         console.log('Starting TTS request...');
//         const form = new FormData();
//         form.append('text', text);  // Use the actual text parameter
//         form.append('language', language);
//         form.append('speaker_wav_filename', 'hritvikshort.wav');

//         const response = await fetch('http://localhost:5002/synthesize', {
//             method: 'POST',
//             body: form,
//             headers: {
//                 ...form.getHeaders(),
//             }
//         });

//         console.log('Response status:', response.status);
//         console.log('Response headers:', response.headers);

//         // Track data flow
//         let totalBytes = 0;
//         response.body.on('data', chunk => {
//             totalBytes += chunk.length;
//             console.log(`Received chunk: ${chunk.length} bytes, Total: ${totalBytes} bytes`);
//         });

//         response.body.on('end', () => {
//             console.log(`Total audio data received: ${totalBytes} bytes`);
//         });

//         // Set headers
//         res.setHeader('Content-Type', 'audio/wav');
//         res.setHeader('Cache-Control', 'no-cache');
//         res.setHeader('Accept-Ranges', 'bytes');

//         // Pipe the response
//         response.body.pipe(res);

//     } catch (error) {
//         console.error('Detailed error:', error);
//         res.status(500).send(error.message);
//     }
// }