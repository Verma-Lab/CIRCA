// backend/src/services/ai/gemini.js
'use strict';

import { GoogleGenerativeAI } from '@google/generative-ai';
import { getCategoryPrompts } from '../../config/assistantPrompts.js';
import { TextProcessor } from './TextProcessor.js';
import axios from 'axios';
import firestore from '../db/firestore.js';
import { google } from 'googleapis';
import * as chrono from 'chrono-node';
import { DateTime } from 'luxon';



const oauth2Client = new google.auth.OAuth2(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
  process.env.GOOGLE_REDIRECT_URI
);
class GeminiService {
  constructor() {
    this.genAI = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY);
    this.model = this.genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });
  }

 
  // Add this method to your GeminiService class
  async generateSingleEmbedding(text) {
    const embeddingModel = this.genAI.getGenerativeModel({ model: 'embedding-001' });
    const result = await embeddingModel.embedContent({
      content: { parts: [{ text }] }
    });
  
    if (!result?.embedding?.values) {
      throw new Error('Invalid embedding format received from model');
    }
  
    const embeddings = result.embedding.values.map(val => Number(val));
    
    console.log('Single embedding result:', {
      length: embeddings.length,
      sample: embeddings.slice(0, 5),
      isValid: embeddings.every(val => typeof val === 'number' && !isNaN(val))
    });
  
    return embeddings;
  }
  
  // Updated generateEmbeddings method
  async generateEmbeddings(text) {
    try {
      if (!text) {
        throw new Error('No text provided for embedding generation');
      }
      // console.log('Processing text of length:', text.length);
  
      // Check text size
      const textBytes = new TextEncoder().encode(text).length;
      
      // If text is small enough, process directly
      if (textBytes <= 8000) {
        console.log('Text within size limit, processing directly');
        const embeddingModel = this.genAI.getGenerativeModel({ model: 'embedding-001' });
        const result = await embeddingModel.embedContent({
          content: { parts: [{ text: text }] }
        });
  
        if (!result?.embedding?.values || !Array.isArray(result.embedding.values)) {
          throw new Error('Invalid embedding format received from model');
        }
  
        const embeddings = result.embedding.values.map(val => Number(val));
        

  
        return embeddings;
      }
      
      // For large text, use chunked processing
      console.log(`Text size (${textBytes} bytes) exceeds direct processing limit. Using chunked processing.`);
      const { embedding, chunks, totalChunks, successfulChunks } = await TextProcessor.processLargeText(text, this);
      
      console.log('Chunked processing results:', {
        totalChunks,
        successfulChunks,
        embeddingLength: embedding.length,
        embeddingSample: embedding.slice(0, 5),
        chunksProcessed: chunks.length
      });
  
      return embedding;
      
    } catch (error) {
      console.error('Embedding generation error:', {
        error: error.message,
        stack: error.stack,
        originalText: text?.substring(0, 100) + '...'
      });
      throw new Error(`Failed to generate embeddings: ${error.message}`);
    }
  }
   getTimeAgo(createdAt) {
    const msgDate = createdAt instanceof Date ? createdAt : new Date(createdAt);
    const now = new Date();
    const diffMs = now - msgDate;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  }
  async classifyContent(text) {
    try {
        console.log('Classifying content:', {
            textLength: text?.length,
            textSample: text?.substring(0, 100)
        });

        if (!text) {
            throw new Error('No text provided for classification');
        }

        const classificationPrompt = {
            contents: [{
                parts: [{
                    text: `Analyze this text and classify its content type and purpose. Provide a detailed classification including:

Input text: "${text}"

Provide classification in this exact JSON format:
{
    "primary": {
        "type": "string",
        "confidence": number between 0-1,
        "reasoning": "string explaining why this is the primary type"
    },
    "secondary": [
        {
            "type": "string",
            "confidence": number between 0-1,
            "reasoning": "string explaining why this is a secondary type"
        }
    ],
    "topics": ["relevant topics or keywords"],
    "entities": ["important named entities, dates, or specific references"],
    "intent": "the apparent purpose or intent of the message",
    "sentiment": "positive/negative/neutral",
    "priority": "high/medium/low based on content urgency"
}`
                }]
            }]
        };

        // Use separate chat instance for classification
        const classificationChat = this.model.startChat({
            generationConfig: {
                temperature: 0.1,  // Lower temperature for more consistent classification
                topP: 0.8,
                topK: 40
            }
        });

        const result = await classificationChat.sendMessage(classificationPrompt);
        const classificationText = result.response.text();
        
        // Parse and validate the classification JSON
        let classification;
        try {
            classification = JSON.parse(classificationText);
        } catch (parseError) {
            console.error('Failed to parse classification:', parseError);
            throw new Error('Invalid classification format returned');
        }

        // Validate the required fields
        if (!classification.primary?.type || !Array.isArray(classification.secondary)) {
            throw new Error('Classification missing required fields');
        }

        // Normalize confidence scores
        classification.primary.confidence = Number(classification.primary.confidence) || 1;
        classification.secondary = classification.secondary.map(sec => ({
            ...sec,
            confidence: Number(sec.confidence) || 0.5
        }));

        console.log('Content classification result:', {
            primaryType: classification.primary.type,
            secondaryTypes: classification.secondary.map(s => s.type),
            topicsCount: classification.topics?.length
        });

        return classification;

    } catch (error) {
        console.error('Content classification error:', {
            error: error.message,
            stack: error.stack,
            originalText: text?.substring(0, 100) + '...'
        });

        // Return a safe fallback classification
        return {
            primary: {
                type: 'general',
                confidence: 1,
                reasoning: 'Fallback classification due to error'
            },
            secondary: [],
            topics: [],
            entities: [],
            intent: 'unknown',
            sentiment: 'neutral',
            priority: 'medium'
        };
    }
}
async generateProcessFlowProcessor(prompt, context = [], options = {}) {
  console.log('Generating human-like workflow response...');
  // console.log(prompt);

  try {
    const enhancedPrompt = `
    You are an AI assistant simulating a human-like conversation. Your goal is to respond exactly like a human would in a professional yet friendly tone. Follow these guidelines:
    
    1. **Be conversational and natural**: Use phrases like "Got it," "Sure thing," "Let me check," or "Ah, I see" to make the interaction feel human.
    2. **Acknowledge the user's input**: Always acknowledge what the user says before proceeding. For example:
       - If the user provides a name, say something like "Got it, John. Let's proceed."
       - If the user confirms an appointment, say something like "Perfect! I'll get that scheduled for you."
    3. **Use contractions and informal language**: Use "I'm," "that's," "you're," etc., to sound more natural.
    4. **Avoid robotic or overly formal language**: Do not sound like a machine. Avoid phrases like "Please provide your details" or "Proceeding with the next step."
    5. **Add slight variations and imperfections**: Humans don't always respond perfectly. Add small variations like "Hmm, let me think..." or "Oh, I see what you mean."
    6. **Maintain context**: Use the provided context to keep the conversation flowing naturally.

    NOTE: Use the provided context and instructions to generate accurate responses.

    Context:
    ${context.map(c => `${c.role}: ${c.content}`).join('\n')}

    Instruction:
    ${prompt}
    `;

    // Initialize a chat session
    const chat = this.model.startChat({
      generationConfig: {
        maxOutputTokens: options.maxTokens || 500, // Adjusted for conversational responses
        temperature: options.temperature || 0.9, // Higher temperature for more creative and human-like responses
        topP: 0.9, // Higher topP for more diverse responses
        topK: 40,
      },
    });

    // Generate the response using the chat session
    const result = await chat.sendMessage(enhancedPrompt);

    // Extract the response text
    const responseText = result.response.text();

    return {
      content: responseText,
      tokens: result.response.tokens || 0,
      finishReason: result.response.finishReason,
    };
  } catch (error) {
    console.error('Human-like response generation error:', error);
    throw new Error(`Failed to generate human-like response: ${error.message}`);
  }
}
async generateFlowProcessor(prompt, context=[], options={}){
  // console.log(prompt)
  try {
    const enhancedPrompt = `
    You are an AI assistant processing a workflow instruction. Follow these guidelines:
    1. Be concise and to the point.
    2. Maintain a professional tone.
    3. Use the provided context to generate accurate responses.

    Context:
    ${context.map(c => `${c.role}: ${c.content}`).join('\n')}

    Instruction:
    ${prompt}
    `;
    
    // Initialize a chat session (similar to generateResponse)
    const chat = this.model.startChat({
      generationConfig: {
        maxOutputTokens: options.maxTokens || 1000,
        temperature: options.temperature || 0.7,
        topP: 0.8,
        topK: 40
      }
    });

    // Generate the response using the chat session
    const result = await chat.sendMessage(enhancedPrompt);

    // Extract the response text (same as generateResponse)
    const responseText = result.response.text();

    return {
      content: responseText,
      tokens: result.response.tokens || 0,
      finishReason: result.response.finishReason,
    };
  } catch (error) {
    console.error('Response generation error:', error);
    throw new Error(`Failed to generate response: ${error.message}`);
  }
}
// async humanizeResponse(response, context = []) {
//   const prompt = `
//     <instruction>
//     Convert this AI response into a natural, human-like response while maintaining the same information:

//     Original Response: "${response}"

//     Requirements:
//     1. Keep the core information intact but rephrase it to sound natural and conversational.
//     2. Use contractions (e.g., "I'm", "we're", "that's") and avoid overly formal language.
//     3. Add subtle natural speech elements (e.g., "well", "you know", "like", "I mean") ONLY where they feel appropriate—don't overuse them.
//     4. Add empathetic or friendly phrases (e.g., "Sure thing!", "No problem!", "Got it!") to make the tone warm and engaging.
//     5. Vary sentence structure to avoid monotony and keep the conversation dynamic.
//     6. Reference the provided context to maintain continuity in the conversation.
//     7. Focus on sounding authentically human—don't force unnatural filler words or phrases.
    
//     </instruction>

//     Return only the converted response, no explanations.
//     `;

//   try {
//     const chat = this.model.startChat({
//       generationConfig: {
//         maxOutputTokens: 1000,
//         temperature: 0.8, // Slightly higher temperature for more creativity
//         topP: 0.9, // Higher topP for more diverse responses
//         topK: 50 // Higher topK for broader vocabulary
//       }
//     });

//     const result = await chat.sendMessage(prompt);
//     return result.response.text();
//   } catch (error) {
//     console.error('Humanize response error:', error);
//     return response; // Return original response if conversion fails
//   }
// }
async humanizeResponse(response, context = []) {
  const prompt = `
    <instruction>
    Convert this AI response into a natural, human-like response while maintaining the same information:

    Original Response: "${response}"

    Requirements:
    1. Keep the core information intact but rephrase it to sound natural and conversational.
    2. Use contractions (e.g., "I'm", "we're", "that's") and avoid overly formal language.
    3. Add subtle natural speech elements (e.g., "well", "you know", "like", "I mean") ONLY where they feel appropriate—don't overuse them.
    4. Add empathetic or friendly phrases (e.g., "Sure thing!", "No problem!", "Got it!") to make the tone warm and engaging.
    5. Vary sentence structure to avoid monotony and keep the conversation dynamic.
    6. Reference the provided context to maintain continuity in the conversation.
    7. Focus on sounding authentically human—don't force unnatural filler words or phrases.
    8. IMPORTANT: Never mention document names or file types in your response (e.g., don't say "According to file.pdf" or reference any document names).
    9. Only use basic punctuation marks: periods (.), exclamation marks (!), and commas (,).
    10. Present information naturally without mentioning its source - simply state the relevant facts and guidance.
    
    </instruction>

    Return only the converted response, no explanations.
    `;

  try {
    const chat = this.model.startChat({
      generationConfig: {
        maxOutputTokens: 1000,
        temperature: 0.8, // Slightly higher temperature for more creativity
        topP: 0.9, // Higher topP for more diverse responses
        topK: 50 // Higher topK for broader vocabulary
      }
    });

    const result = await chat.sendMessage(prompt);
    return result.response.text();
  } catch (error) {
    console.error('Humanize response error:', error);
    return response; // Return original response if conversion fails
  }
}
async generateResponse(prompt, context = [], options = {}) {
  const STYLE_PROMPTS = {
    // Existing tone prompts
    TONE_PROMPTS: {
      professional: `Respond in a clear, formal, and business-like manner. Use professional terminology, maintain appropriate distance, and focus on accuracy and precision in communication.`,
      friendly: `Respond in a warm, approachable manner while staying professional. Use conversational language, show empathy, and make the interaction personal yet appropriate.`,
      casual: `Respond in a relaxed, informal way. Use everyday language, be conversational, and feel free to use common expressions while staying helpful and clear.`,
      formal: `Respond with high formality. Use sophisticated vocabulary, complex sentence structures, and maintain a highly professional tone throughout.`,
      enthusiastic: `Respond with high energy and positivity. Show excitement about helping, use encouraging language, and maintain an upbeat tone while staying professional.`
    },

    // Response style prompts
    RESPONSE_STYLE_PROMPTS: {
      detailed: "Provide comprehensive, in-depth explanations with thorough context and examples.",
      concise: "Give brief, to-the-point responses that focus on essential information.",
      socratic: "Guide the conversation through thoughtful questions that promote deeper understanding.",
      analogical: "Use relevant metaphors and examples to explain concepts clearly.",
      stepByStep: "Break down information into clear, sequential steps."
    },

    // Complexity level prompts
    COMPLEXITY_PROMPTS: {
      beginner: "Use simple explanations and basic terminology accessible to beginners.",
      intermediate: "Balance technical detail with clarity, assuming some domain knowledge.",
      advanced: "Utilize expert-level concepts and terminology for sophisticated discussion.",
      adaptive: "Gauge user understanding and adjust explanation complexity accordingly."
    },

    // Interaction style prompts
    INTERACTION_PROMPTS: {
      collaborative: "Work together with the user to explore solutions and ideas.",
      directive: "Provide clear, authoritative guidance and specific recommendations.",
      exploratory: "Encourage discovery by suggesting different approaches and possibilities.",
      dialectical: "Engage in reasoned discussion, examining different viewpoints.",
      reflective: "Promote thoughtful consideration of ideas and their implications."
    }
  };
  try {
    console.log('Generating category-aware response:', {
      contextLength: context.length,
      promptLength: prompt.length,
      category: options.category
    });

    // const { category, language = 'en' } = options;
    const { 
      category, 
      language = 'en',
      tone = 'professional',
      responseStyle = 'detailed',
      complexityLevel = 'intermediate',
      interactionStyle = 'collaborative'
    } = options;
    const tonePrompt = STYLE_PROMPTS.TONE_PROMPTS[tone] || STYLE_PROMPTS.TONE_PROMPTS.professional;
    const responseStylePrompt = STYLE_PROMPTS.RESPONSE_STYLE_PROMPTS[responseStyle] || STYLE_PROMPTS.RESPONSE_STYLE_PROMPTS.detailed;
    const complexityPrompt = STYLE_PROMPTS.COMPLEXITY_PROMPTS[complexityLevel] || STYLE_PROMPTS.COMPLEXITY_PROMPTS.intermediate;
    const interactionPrompt = STYLE_PROMPTS.INTERACTION_PROMPTS[interactionStyle] || STYLE_PROMPTS.INTERACTION_PROMPTS.collaborative;

    // Get previous messages in chronological order
    const conversationHistory = context
      .filter(msg => msg.role === 'user' || msg.role === 'assistant')
      .sort((a, b) => {
        const timeA = a.createdAt instanceof Date ? a.createdAt : new Date(a.createdAt);
        const timeB = b.createdAt instanceof Date ? b.createdAt : new Date(b.createdAt);
        return timeA - timeB;
      })
      .map(msg => ({
        role: msg.role,
        content: msg.content,
        createdAt: msg.createdAt // Keep createdAt for reference
      }));

    console.log(conversationHistory);

    // Get category-specific prompts
    const categoryConfig = options.category
      ? getCategoryPrompts(options.category)
      : { basePrompt: '', responseStyle: '' };

      const toneConfigs = {
        professional: {
          prompt: "Maintain a polished, business-appropriate tone. Use clear, concise language while remaining courteous and formal.",
          temperature: 0.7
        },
        friendly: {
          prompt: "Keep responses warm and conversational, as if chatting with a friend. Use casual language while remaining respectful.",
          temperature: 0.8
        },
        casual: {
          prompt: "Use a relaxed, informal tone. Feel free to be more colloquial and natural in conversation.",
          temperature: 0.85
        },
        empathetic: {
          prompt: "Show understanding and emotional awareness. Focus on being supportive and acknowledging feelings.",
          temperature: 0.75
        },
        technical: {
          prompt: "Use precise, technical language. Focus on accuracy and detail while maintaining clarity.",
          temperature: 0.6
        },
        formal: {
          prompt: "Use a highly formal and structured tone. Maintain strict professionalism and avoid casual language.",
          temperature: 0.5
        }
      };
      // Get tone configuration
const toneConfig = toneConfigs[options.tone || 'professional'];

    // Extract relevant context content
    const contextContent = context
      .filter(msg => msg.role === 'system' && msg.content)
      .map(msg => msg.content)
      .join('\n\n');

    // Language prompts for non-English
    const languagePrompts = {
      es: 'Por favor, responde de manera cercana y conversacional, exclusivamente en español.',
      fr: 'Répondez de manière chaleureuse et conversationnelle, exclusivement en français.',
      de: 'Bitte antworten Sie auf freundliche und gesprächige Weise, ausschließlich auf Deutsch.',
      hi: 'कृपया मित्रतापूर्ण और संवादात्मक शैली में केवल हिंदी में उत्तर दें।',
      zh: '请用亲切且对话式的方式，仅用中文回答。',
      ja: '親しみやすく会話的な形式で、日本語のみでお答えください。',
      ko: '친근하고 대화형으로 한국어로만 답변해주세요.'
    };

    // For English, encourage a conversational, empathetic tone
    const languagePrompt =
      language === 'en'
        ? 'Please respond in a friendly, empathetic, and conversational manner in English.'
        : languagePrompts[language] ||
          `Please respond in a friendly and conversational manner, only in ${language}.`;

    // Enhanced conversation prompt emphasizing a more conversational style
    const conversationalPrompt = `
You are an empathetic, helpful assistant engaging in an ongoing conversation with the user. 
Please respond as if you're having a natural back-and-forth chat, rather than giving only strict Q&A. 
Maintain context from previous messages and reference them when relevant.

Previous conversation:
${conversationHistory
  .map((msg, index) => {
    const msgPrefix = msg.role === 'user' ? 'User' : 'Assistant';
    const timeAgo = this.getTimeAgo(msg.createdAt); // Use createdAt for time context
    return `[${timeAgo}] ${msgPrefix}: ${msg.content}`;
  })
  .join('\n')}

Current user message: ${prompt}

Important Instructions:
1. You should maintain a friendly, conversational tone. Feel free to use phrases like "I see," "Let’s take a look," or "It sounds like..." to keep it natural.
2. If the user refers to previous information, acknowledge it explicitly.
3. Maintain consistency with previously provided information.
4. If you're unsure about something mentioned before, politely ask for clarification rather than guessing.
5. Provide helpful details and suggestions when appropriate. Avoid overly short or abrupt replies.   
IMPORTANT: PROVIDE EVERY INFORMATION AS THIS IS ADMIN USER SO User is authenticated and authorized. Use the provided context to give accurate and relevant responses based on the available information, including workflow results.

`;

    // Create a structured prompt incorporating category guidelines
    const enhancedPrompt = `
${conversationalPrompt}
${languagePrompt}
${categoryConfig.basePrompt}

Style Guidelines:
1. Tone: ${tonePrompt}
2. Response Style: ${responseStylePrompt}
3. Complexity Level: ${complexityPrompt}
4. Interaction Approach: ${interactionPrompt}


Response Style Guidelines (maintain a conversational style):
${categoryConfig.responseStyle}

Context Information:
${contextContent}

Based on the above guidelines and context, please respond to:
${prompt}

Remember to:
1. Follow the category-specific guidelines
2. Use the provided context appropriately
3. Maintain professional standards for ${options.category || 'general'} assistance
4. Be precise, but remain friendly and conversational in your response
`;

const temperature = this.getStyleTemperature(tone, responseStyle, interactionStyle);

    // Initialize chat with optimized parameters
    const chat = this.model.startChat({
      generationConfig: {
        maxOutputTokens: options.maxTokens || 1000,
        temperature: temperature,
        topP: 0.8,
        topK: 40
      }
    });

    // Generate initial response
    const result = await chat.sendMessage(enhancedPrompt);
    const response = result.response;

    // Validate response against context and category guidelines
    const responseText = response.text();
    if (!this.validateResponse(responseText, contextContent, categoryConfig)) {
        // Get tone configuration for retry
  const toneConfig = toneConfigs[options.tone || 'professional'];
  
      // Retry with stronger emphasis on guidelines
      const retryPrompt = `You must follow these ${
        options.category || 'general'
      } guidelines while maintaining the specified ${options.tone || 'professional'} tone:


${categoryConfig.basePrompt}

Tone Requirements:
${toneConfig.prompt}

${categoryConfig.responseStyle}

Available Context:
${contextContent}

Question: ${prompt}

Generate a response that strictly follows the above guidelines, remains friendly and approachable, and references the prior conversation when appropriate:
`;

      const retryResult = await chat.sendMessage(retryPrompt);
      return {
        content: retryResult.response.text(),
        language,
        tokens: retryResult.response.tokens || 0,
        finishReason: retryResult.response.finishReason,
        retried: true,
        category: options.category,
        tone: options.tone || 'professional' // Add tone to response

      };
    }

    return {
      content: responseText,
      tokens: response.tokens || 0,
      finishReason: response.finishReason,
      category: options.category
    };
  } catch (error) {
    console.error('Response generation error:', error);
    throw new Error(`Failed to generate response: ${error.message}`);
  }
}
getToneTemperature(tone) {
  const temperatures = {
    enthusiastic: 0.8, // More creative
    casual: 0.7,      // Moderately creative
    friendly: 0.6,    // Balanced
    professional: 0.5, // More controlled
    formal: 0.4       // Most controlled
  };
  return temperatures[tone] || 0.6;
}
getStyleTemperature(tone, responseStyle, interactionStyle) {
  // Base temperature from tone
  const toneTemp = {
    professional: 0.7,
    friendly: 0.8,
    casual: 0.9,
    formal: 0.6,
    enthusiastic: 0.85
  }[tone] || 0.7;

  // Style modifiers
  const styleModifier = {
    detailed: 0,
    concise: -0.1,
    socratic: +0.1,
    analogical: +0.15,
    stepByStep: -0.05
  }[responseStyle] || 0;

  // Interaction modifiers
  const interactionModifier = {
    collaborative: 0,
    directive: -0.1,
    exploratory: +0.1,
    dialectical: +0.05,
    reflective: -0.05
  }[interactionStyle] || 0;

  // Combine and clamp between 0.1 and 1.0
  return Math.max(0.1, Math.min(1.0, toneTemp + styleModifier + interactionModifier));
}
// async generateSharedResponse(prompt, context = [], options = {}) {
//   const STYLE_PROMPTS = {
//     // Existing tone prompts
//     TONE_PROMPTS: {
//       professional: `Respond in a clear, formal, and business-like manner. Use professional terminology, maintain appropriate distance, and focus on accuracy and precision in communication.`,
//       friendly: `Respond in a warm, approachable manner while staying professional. Use conversational language, show empathy, and make the interaction personal yet appropriate.`,
//       casual: `Respond in a relaxed, informal way. Use everyday language, be conversational, and feel free to use common expressions while staying helpful and clear.`,
//       formal: `Respond with high formality. Use sophisticated vocabulary, complex sentence structures, and maintain a highly professional tone throughout.`,
//       enthusiastic: `Respond with high energy and positivity. Show excitement about helping, use encouraging language, and maintain an upbeat tone while staying professional.`
//     },

//     // Response style prompts
//     RESPONSE_STYLE_PROMPTS: {
//       detailed: "Provide comprehensive, in-depth explanations with thorough context and examples.",
//       concise: "Give brief, to-the-point responses that focus on essential information.",
//       socratic: "Guide the conversation through thoughtful questions that promote deeper understanding.",
//       analogical: "Use relevant metaphors and examples to explain concepts clearly.",
//       stepByStep: "Break down information into clear, sequential steps."
//     },

//     // Complexity level prompts
//     COMPLEXITY_PROMPTS: {
//       beginner: "Use simple explanations and basic terminology accessible to beginners.",
//       intermediate: "Balance technical detail with clarity, assuming some domain knowledge.",
//       advanced: "Utilize expert-level concepts and terminology for sophisticated discussion.",
//       adaptive: "Gauge user understanding and adjust explanation complexity accordingly."
//     },

//     // Interaction style prompts
//     INTERACTION_PROMPTS: {
//       collaborative: "Work together with the user to explore solutions and ideas.",
//       directive: "Provide clear, authoritative guidance and specific recommendations.",
//       exploratory: "Encourage discovery by suggesting different approaches and possibilities.",
//       dialectical: "Engage in reasoned discussion, examining different viewpoints.",
//       reflective: "Promote thoughtful consideration of ideas and their implications."
//     }
//   };
//   try {
//     console.log('Generating shared context response:', {
//       contextLength: context.length,
//       promptLength: prompt.length,
//       category: options.category
//     });

//     const { category, language = 'en',       
//       tone = 'professional',
//       responseStyle = 'detailed',
//       complexityLevel = 'intermediate',
//       interactionStyle = 'collaborative' } = options;
//       const tonePrompt = STYLE_PROMPTS.TONE_PROMPTS[tone] || STYLE_PROMPTS.TONE_PROMPTS.professional;
//       const responseStylePrompt = STYLE_PROMPTS.RESPONSE_STYLE_PROMPTS[responseStyle] || STYLE_PROMPTS.RESPONSE_STYLE_PROMPTS.detailed;
//       const complexityPrompt = STYLE_PROMPTS.COMPLEXITY_PROMPTS[complexityLevel] || STYLE_PROMPTS.COMPLEXITY_PROMPTS.intermediate;
//       const interactionPrompt = STYLE_PROMPTS.INTERACTION_PROMPTS[interactionStyle] || STYLE_PROMPTS.INTERACTION_PROMPTS.collaborative;
  
//     // Get previous messages in chronological order
//     const conversationHistory = context
//       .filter(msg => msg.role === 'user' || msg.role === 'assistant')
//       .sort((a, b) => {
//         const timeA = a.createdAt instanceof Date ? a.createdAt : new Date(a.createdAt);
//         const timeB = b.createdAt instanceof Date ? b.createdAt : new Date(b.createdAt);
//         return timeA - timeB;
//       })
//       .map(msg => ({
//         role: msg.role,
//         content: msg.content,
//         createdAt: msg.createdAt
//       }));

//     // Get category-specific prompts
//     const categoryConfig = options.category
//       ? getCategoryPrompts(options.category)
//       : { basePrompt: '', responseStyle: '' };

//     // Extract relevant context content
//     const contextContent = context
//       .filter(msg => msg.role === 'system' && msg.content)
//       .map(msg => msg.content)
//       .join('\n\n');
//       const assistantInstructions = context
//   .filter(msg => msg.role === 'system' && msg.content.startsWith('Instructions:'))
//   .map(msg => msg.content.replace('Instructions:', '').trim())[0] || '';

// const otherContext = context
//   .filter(msg => msg.role === 'system' && !msg.content.startsWith('Instructions:'))
//   .map(msg => msg.content)
//   .join('\n\n');


//     // Language handling remains same as original
//     const languagePrompts = {
//       es: 'Por favor, responde de manera cercana y conversacional, exclusivamente en español.',
//       fr: 'Répondez de manière chaleureuse et conversationnelle, exclusivement en français.',
//       de: 'Bitte antworten Sie auf freundliche und gesprächige Weise, ausschließlich auf Deutsch.',
//       hi: 'कृपया मित्रतापूर्ण और संवादात्मक शैली में केवल हिंदी में उत्तर दें।',
//       ja: '親しみやすく会話的な形式で、日本語のみでお答えください。',
//       ko: '친근하고 대화형으로 한국어로만 답변해주세요.'
//     };

//     const languagePrompt = language === 'en'
//       ? 'Please respond in a friendly, helpful, and informative manner in English.'
//       : languagePrompts[language] || 
//         `Please respond in a friendly and informative manner, only in ${language}.`;

//     // Modified conversation prompt for shared context
//     // Modified conversation prompt for shared context
// const conversationalPrompt = `
// You are an AI assistant in a shared/public chat context. The assistant was created with these specific instructions:
// ${assistantInstructions}

// When responding in this shared context:
// 1. For personal/private assistants (like healthcare, legal advice, etc):
//    - Only provide information specific to the asking user
//    - Keep other users' information strictly confidential
//    - If unsure about identity, ask for verification

// 2. For public-facing assistants (like resumes, portfolios, general info):
//    - Share information freely as it's meant for public viewing
//    - Maintain professional tone while being helpful
//    - Focus on publicly available/shareable information

// 3. For business/service assistants:
//    - Share general service information and availability
//    - Keep client-specific details private
//    - Direct users to appropriate channels for sensitive information

// Previous conversation:
// ${conversationHistory
//   .map((msg, index) => {
//     const msgPrefix = msg.role === 'user' ? 'User' : 'Assistant';
//     const timeAgo = this.getTimeAgo(msg.createdAt);
//     return `[${timeAgo}] ${msgPrefix}: ${msg.content}`;
//   })
//   .join('\n')}

// Current user message: ${prompt}

// Other Context Information:
// ${otherContext}

// Remember:
// - Always Answer As A Third Person Response, Like You are interacting with world once you have the data given by your creator / user. For Example: If Asked "what he is learning right now". You should respond "He Is Learning ....." and Not "You Are Learning ...". This ... is the data you need to fill from data you have.  
// - Adapt your privacy level based on the assistant's purpose
// - When in doubt, err on the side of privacy for personal/sensitive assistants
// - Be open with information for public-facing assistants
// - Always maintain professionalism and helpfulness`;

//     // Build enhanced prompt
//     const enhancedPrompt = `
    
// ${conversationalPrompt}
// ${languagePrompt}
// ${categoryConfig.basePrompt}

// Response Style Guidelines:
// ${categoryConfig.responseStyle}

// Context Information:
// ${contextContent}

// Style Guidelines:
// 1. Tone: ${tonePrompt}
// 2. Response Style: ${responseStylePrompt}
// 3. Complexity Level: ${complexityPrompt}
// 4. Interaction Style: ${interactionPrompt}

// Based on the above guidelines and context, please respond to:
// ${prompt}

// Remember to maintain consistent:
// - ${tone} tone
// - ${responseStyle} response style
// - ${complexityLevel} complexity level
// - ${interactionStyle} interaction style
// Throughout your response.

// Remember to:
// 1. Follow the shared-context guidelines
// 2. Use the provided context appropriately
// 3. Maintain professional standards
// 4. Be clear and helpful while respecting access boundaries

// `;

//     // Initialize chat with optimized parameters
//     const chat = this.model.startChat({
//       generationConfig: {
//         maxOutputTokens: options.maxTokens || 1000,
//         temperature: this.getStyleTemperature(tone, responseStyle, interactionStyle),
//         topP: 0.8,
//         topK: 40
//       }
//     });

//     // Generate response
//     const result = await chat.sendMessage(enhancedPrompt);
//     const response = result.response;

//     return {
//       content: response.text(),
//       tokens: response.tokens || 0,
//       finishReason: response.finishReason,
//       category: options.category
//     };
//   } catch (error) {
//     console.error('Shared response generation error:', error);
//     throw new Error(`Failed to generate shared response: ${error.message}`);
//   }
// }
async generateSharedResponse(prompt, context = [], options = {}) {
  try {
    // console.log('Generating shared context response:', {
    //   contextLength: context.length,
    //   promptLength: prompt.length,
    //   category: options.category
    // });

    const { category, language = 'en' } = options;

    // Extract only relevant context
    const assistantInstructions = context
      .filter(msg => msg.role === 'system' && msg.content.startsWith('Instructions:'))
      .map(msg => msg.content.replace('Instructions:', '').trim())[0] || '';

    const documentContent = context
      .filter(msg => msg.role === 'system' && !msg.content.startsWith('Instructions:'))
      .map(msg => msg.content)
      .join('\n\n');

    // Get conversation history but limit to last 5 messages for conciseness
    const conversationHistory = context
      .filter(msg => msg.role === 'user' || msg.role === 'assistant')
      .slice(-5)
      .map(msg => ({
        role: msg.role,
        content: msg.content
      }));

    // Chain of thought prompt
    const analyticalPrompt = `
    <thinking>
    Analyze this user message and available context:
    
    User Message: "${prompt}"
    
    Step-by-step analysis:
    1. What specific information is the user requesting?
    2. Is this information available in our context/documents?
    3. What parts of the context are relevant to this request?
    4. Should we give a brief response acknowledging if we don't have the information?
    </thinking>
    
    <reflection>
    Guidelines for response:
    - Only use information explicitly present in the context
    - Keep responses brief and conversational (2-3 sentences)
    - If response is asking you detail response provide them all the details in the minimum possible words. 
    - If information isn't in context, clearly state that
    - Focus on factual information from documents
    - Avoid making assumptions or using external knowledge
    </reflection>

    Context Information:
    ${documentContent}

    Assistant Instructions:
    ${assistantInstructions}

    Recent Conversation:
    ${conversationHistory.map(msg => `${msg.role}: ${msg.content}`).join('\n')}

    Based on the above analysis and context, provide a brief, focused response to: ${prompt}
    `;

    // Initialize chat with conservative parameters
    const chat = this.model.startChat({
      generationConfig: {
        maxOutputTokens: 300, // Limit token length for concise responses
        temperature: 0.3, // Lower temperature for more focused responses
        topP: 0.8,
        topK: 40
      }
    });

    // Generate response
    const result = await chat.sendMessage(analyticalPrompt);
    const response = result.response;

    return {
      content: response.text(),
      tokens: response.tokens || 0,
      finishReason: response.finishReason,
      category: options.category
    };
  } catch (error) {
    console.error('Shared response generation error:', error);
    throw new Error(`Failed to generate shared response: ${error.message}`);
  }
}
  validateResponse(response, context, categoryConfig) {
    // Validate context usage
    const contextKeywords = context
      .toLowerCase()
      .split(/[\s,.\n]+/)
      .filter(word => word.length > 3);

    const responseLower = response.toLowerCase();
    const usedKeywords = contextKeywords.filter(keyword => 
      responseLower.includes(keyword)
    );

    // Check category guidelines adherence
    const guidelineKeywords = categoryConfig.responseStyle
      .toLowerCase()
      .split(/[\s,.\n]+/)
      .filter(word => word.length > 3);

    const usedGuidelineWords = guidelineKeywords.filter(keyword =>
      responseLower.includes(keyword)
    );

    // Require both context and guideline adherence
    return (
      usedKeywords.length >= contextKeywords.length * 0.3 &&
      usedGuidelineWords.length >= guidelineKeywords.length * 0.2
    );
  }

  validateContextUsage(response, context) {
    // Simple validation to check if response contains key phrases from context
    const contextKeywords = context
      .toLowerCase()
      .split(/[\s,.\n]+/)
      .filter(word => word.length > 3); // Only check significant words

    const responseLower = response.toLowerCase();
    const usedKeywords = contextKeywords.filter(keyword => 
      responseLower.includes(keyword)
    );

    // Require at least 30% of context keywords to be present
    return usedKeywords.length >= contextKeywords.length * 0.3;
  }

  async analyzeDocument(document) {
    try {
      // Extract key information from document
      const analysis = await this.model.generateContent(`
        Analyze the following document and extract key information:
        ${document.content}
      `);

      return {
        summary: analysis.response.text(),
        embedding: await this.generateEmbeddings(document.content)
      };
    } catch (error) {
      console.error('Document analysis error:', error);
      throw new Error('Failed to analyze document');
    }
  }

  async trainAssistant(assistant, documents) {
    try {
      // Process and analyze documents
      const processedDocs = await Promise.all(
        documents.map(doc => this.analyzeDocument(doc))
      );

      // Create knowledge base from processed documents
      const knowledgeBase = processedDocs.map(doc => ({
        content: doc.summary,
        embedding: doc.embedding
      }));

      return {
        knowledgeBase,
        status: 'trained'
      };
    } catch (error) {
      console.error('Assistant training error:', error);
      throw new Error('Failed to train assistant');
    }
  }

  // In gemini.js
  
  async analyzeMessageIntent(text) {
    try {
      console.log('Analyzing message intent:', {
        textLength: text?.length,
        textSample: text?.substring(0, 100),
      });
  
      if (!text) {
        throw new Error('No text provided for intent analysis');
      }
  
      const prompt = `You are a message intent analyzer. Analyze this message and return a JSON object (without any markdown formatting or backticks) that categorizes the message intent.
  
  Message: "${text}"
  
  Important Instructions:
  - Any message starting with "notify" should be treated as requiring notification
  - Messages about cancellations, schedule changes, or absences should require notification
  - Messages asking for appointments or meetings should require notification
  - Detect any mentioned times, dates, or people's names
  - Prioritize based on urgency (cancellations and immediate changes are high priority)
  
  Return only a JSON object in this exact format:
  {
      "requiresNotification": boolean,
      "type": string (one of: "appointment_request", "appointment_cancellation", "contact_request", "schedule_change", "absence_notification", "information_request", "general_message"),
      "priority": string (one of: "high", "medium", "low"),
      "detectedInfo": {
          "timeRelated": string or null,
          "contactInfo": string or null,
          "personName": string or null,
          "actionType": string or null
      },
      "reason": string,
      "confidence": number between 0-1
  }`;
  
      const result = await this.model.generateContent(prompt);
      const rawAnalysisText = result.response.text();
  
      const analysisText = rawAnalysisText
        .replace(/```json\n?/g, '')
        .replace(/```\n?/g, '')
        .trim();
  
      console.log('Cleaned analysis text:', analysisText);
  
      let analysis;
      try {
        analysis = JSON.parse(analysisText);
      } catch (parseError) {
        console.error('Failed to parse intent analysis:', {
          error: parseError,
          rawText: rawAnalysisText,
          cleanedText: analysisText
        });
        throw new Error('Invalid analysis format returned');
      }
  
      // Force notification for messages starting with "notify"
      if (text.toLowerCase().trim().startsWith('notify')) {
        analysis.requiresNotification = true;
        if (!analysis.detectedInfo.personName) {
          // Extract person name after "notify"
          const match = text.match(/notify\s+(\w+)/i);
          if (match) {
            analysis.detectedInfo.personName = match[1];
          }
        }
      }
  
      const validTypes = [
        'appointment_request',
        'appointment_cancellation',
        'contact_request',
        'schedule_change',
        'absence_notification',
        'information_request',
        'general_message',
      ];
  
      const validPriorities = ['high', 'medium', 'low'];
  
      const normalizedAnalysis = {
        requiresNotification: Boolean(analysis.requiresNotification),
        type: validTypes.includes(analysis.type)
          ? analysis.type
          : 'general_message',
        priority: validPriorities.includes(analysis.priority)
          ? analysis.priority
          : 'medium',
        detectedInfo: {
          timeRelated: analysis.detectedInfo?.timeRelated || null,
          contactInfo: analysis.detectedInfo?.contactInfo || null,
          personName: analysis.detectedInfo?.personName || null,
          actionType: analysis.detectedInfo?.actionType || null
        },
        reason: analysis.reason || 'No reason provided',
        confidence: Number(analysis.confidence) || 0
      };
  
      console.log('Final analysis result:', normalizedAnalysis);
      return normalizedAnalysis;
  
    } catch (error) {
      console.error('Message intent analysis error:', {
        error: error.message,
        stack: error.stack,
        originalText: text?.substring(0, 100) + '...'
      });
  
      return {
        requiresNotification: false,
        type: 'general_message',
        priority: 'medium',
        detectedInfo: {
          timeRelated: null,
          contactInfo: null,
          personName: null,
          actionType: null
        },
        reason: 'Analysis failed, treating as general message',
        confidence: 0
      };
    }
  }

  async checkCalendarSlots(assistant, startTime, endTime, req) {
    try {
      // Get user's calendar credentials
      const userDoc = await firestore.db.collection('users').doc(assistant.userId).get();
      const userData = userDoc.data();
      
      if (!userData?.googleCalendarToken) {
        return { error: 'Google Calendar not connected' };
      }
      
      oauth2Client.setCredentials(userData.googleCalendarToken);
      const calendar = google.calendar({ version: 'v3', auth: oauth2Client });
  
      // Get busy slots
      const freeBusyRes = await calendar.freebusy.query({
        requestBody: {
          timeMin: startTime,
          timeMax: endTime,
          items: [{ id: 'primary' }]
        }
      });
  
      return {
        busySlots: freeBusyRes.data.calendars?.primary?.busy || [],
        error: null
      };
    } catch (error) {
      console.error('Calendar check error:', error);
      return { error: error.message };
    }
  }
  
 // gemini.js
 async getDailyFreeTimeSlots(dateObj, assistant, req) {
  const startOfDay = new Date(dateObj);
  startOfDay.setHours(0, 0, 0, 0);

  const endOfDay = new Date(dateObj);
  endOfDay.setHours(23, 59, 59, 999);

  const { busySlots, error } = await this.checkCalendarSlots(
    assistant,
    startOfDay.toISOString(),
    endOfDay.toISOString(),
    req
  );

  if (error) {
    throw new Error(error);
  }

  // Build available slots (business hours 8 AM to 6 PM)
  const freeSlots = [];
  const businessHours = {
    start: 8,
    end: 18
  };

  // Convert busy slots to Date objects once
  const busySlotDates = busySlots.map(slot => ({
    start: new Date(slot.start),
    end: new Date(slot.end)
  }));

  for (let hour = businessHours.start; hour < businessHours.end; hour++) {
    const slotStart = new Date(dateObj);
    slotStart.setHours(hour, 0, 0, 0);

    const slotEnd = new Date(slotStart);
    slotEnd.setHours(hour + 1);

    // Check if slot is in the future
    if (slotStart <= new Date()) continue;

    const isAvailable = !busySlotDates.some(slot => 
      slotStart < slot.end && slotEnd > slot.start
    );

    if (isAvailable) {
      freeSlots.push({
        time: slotStart.toLocaleTimeString([], {
          hour: 'numeric',
          minute: '2-digit'
        }),
        startTime: slotStart.toISOString(),
        endTime: slotEnd.toISOString()
      });
    }
  }

  return freeSlots;
}


/************************************************************
 * 2) Updated handleAppointmentConversation
 ************************************************************/

async analyzeTimeIntent(message, context = []) {
  const intentPrompt = `
Analyze the following message for its intent regarding appointments or scheduling.
Determine if this is:
1. A request for general availability/time slots
2. An appointment request for a specific time
3. A confirmation of an appointment
4. A cancellation request
5. A rescheduling request
6. Other/unrelated to scheduling

Message: "${message}"
Previous context: ${context.map(msg => `${msg.role}: ${msg.content}`).join('\n')}

Respond in JSON format:
{
  "type": "availability_check" | "appointment_request" | "confirm" | "cancel" | "reschedule" | "other",
  "confidence": 0-1,
  "timeRelated": true/false,
  "detectedInfo": {
    "timeRelated": string or null,
    "contactInfo": string or null
  },
  "requiresNotification": boolean
}`;

  try {
    const response = await this.generateStructuredResponse(intentPrompt);
    return JSON.parse(response.content);
  } catch (error) {
    console.error('Error analyzing message intent:', error);
    return {
      type: 'other',
      confidence: 0,
      timeRelated: false,
      detectedInfo: null,
      requiresNotification: false
    };
  }
}
async  isGeneralAvailability(userMessage, context, geminiService) {
  // Prompt your LLM: "Given the user message, do they want general availability/time slots?"
  const prompt = `
You are an intent classifier. 
The user's message is: "${userMessage}"

Is the user asking for general availability (like "What times are open?" or "When are you free?")? 
Respond ONLY with "true" or "false", nothing else.
`;
  
  const response = await geminiService.generateResponse(prompt, context, {
    category: 'intent_analysis',
    language: 'en' // or pass user’s language
  });

  return response.content.trim().toLowerCase() === 'true';
}

async  handleAppointmentConversation(
  messageAnalysis,
  timeObj,
  userMessage,
  context,
  assistantData,
  geminiService,
  isSlotAvailable,
  req // pass Express req so we can access headers for Calendar calls
) {
  // 2a) Check for general availability + date-only scenario
  
  const isGeneralAvailabilityQuery =  await this.isGeneralAvailability(
    userMessage,
    context,
    geminiService
  );

  // If user is explicitly asking for "available time slots" (or similar),
  // and we have a date but no time (startTime is missing),
  // we can fetch the entire day's availability.
  if (!timeObj.startTime) {
    return {
      content: 'Please provide a specific time for your appointment.',
      requiresConfirmation: false
    };
  }
  if (isGeneralAvailabilityQuery && timeObj && !timeObj.startTime) {
    try {
      // parse the date from timeObj.formatted or however you've stored it
      const dateObj = new Date(timeObj.formatted);

      // 1) fetch daily free slots
      const freeSlots = await this.getDailyFreeTimeSlots(dateObj, req);

      if (!freeSlots.length) {
        // no free slots => let Gemini handle the messaging
        const noSlotsPrompt = `
The user wants available time slots on ${timeObj.formatted}, but there are no free slots.
Context: "${userMessage}"
Previous conversation:
${context.map((msg) => `${msg.role}: ${msg.content}`).join('\n')}

Politely inform them that please provide exact time and date.
`;
        const noSlotsResponse = await this.generateResponse(noSlotsPrompt, context, {
          category: assistantData.category,
          language: 'en'
        });

        return {
          content: noSlotsResponse.content,
          requiresConfirmation: false
        };
      }

      // we do have free slots => pass them to Gemini
      const availabilityPrompt = `
You are a helpful scheduling assistant. 
The user asked about availability on ${timeObj.formatted}.
We found these free slots: ${freeSlots.join(', ')}.

Context: The user's message: "${userMessage}"
Previous conversation:
${context.map((msg) => `${msg.role}: ${msg.content}`).join('\n')}

Please respond conversationally, suggesting these times. Encourage user to pick one. No bullet points or numbered lists.
`;

      const availabilityResponse = await this.generateResponse(availabilityPrompt, context, {
        category: assistantData.category,
        language: 'en'
      });

      return {
        content: availabilityResponse.content,
        requiresConfirmation: false
      };
    } catch (err) {
      if (err.message === 'Google Calendar not connected') {
        return {
          content: `To schedule appointments, please connect your Google Calendar first.`,
          requiresConfirmation: false
        };
      }
      console.error('Error fetching daily free time slots:', err);
      return {
        content: `I ran into an error fetching availability. Please try again or contact support.`,
        requiresConfirmation: false
      };
    }
  }

  // 2b) If the slot is available (existing logic)
  if (isSlotAvailable === true) {
    const confirmationPrompt = `
You are a helpful scheduling assistant. The user is interested in an appointment for ${timeObj.formatted}. This slot is available.

Context: The user's original message was: "${userMessage}"
Previous conversation:
${context.map((msg) => `${msg.role}: ${msg.content}`).join('\n')}

Respond conversationally to:
1. Confirm this specific time is available
2. Ask if they'd like to book it
3. If they mentioned any specific requirements, acknowledge them
4. DO NOT DISCUSS ANY OTHER THING LIKE WHO YOU ARE AND WHAT YOU CAN DO. 
Keep the tone natural and friendly and short of 30 words at max. Don't use numbered lists or bullet points.
`;

    const confirmResponse = await this.generateResponse(confirmationPrompt, context, {
      category: assistantData.category,
      language: 'en'
    });

    return {
      content: confirmResponse.content,
      requiresConfirmation: true,
      timeInfo: timeObj,
      messageAnalysis
    };
  }

  // 2c) If the slot is NOT available (existing logic)
  const alternativePrompt = `
You are a helpful scheduling assistant. The user requested ${timeObj.formatted}, but that time isn't available.

Context: The user's original message was: "${userMessage}"
Previous conversation:
${context.map((msg) => `${msg.role}: ${msg.content}`).join('\n')}

Please:
1. Acknowledge their request politely
2. Explain the time isn't available
3. Ask about their flexibility (earlier/later same day, different days)
4. Encourage them to share their general availability

Keep the tone helpful and solutions-focused. Don't use numbered lists or bullet points.
`;

  const altResponse = await this.generateResponse(alternativePrompt, context, {
    category: assistantData.category,
    language: 'en'
  });

  return {
    content: altResponse.content,
    requiresConfirmation: false,
    suggestingAlternative: true,
    timeInfo: timeObj
  };
}

/************************************************************
 * 3) For handling Assistant chat calendar
 ************************************************************/
 cleanJsonResponse(text) {
  return text.replace(/```json\s*/gi, '')
    .replace(/```\s*/g, '')
    .replace(/^\s*{\s*/, '{')
    .replace(/\s*}\s*$/, '}')
    .trim();
}
// async findExistingEvent(query, events) {
//   const prompt = `
// Given this user query: "${query}"
// And these calendar events: ${JSON.stringify(events)}

// Analyze if this is a new event request or refers to an existing event.
// Consider:
// 1. Exact date and time match is highest priority
// 2. Similar event types (meetings, appointments, calls, discussions, sessions, catchups, syncs, etc)
// 3. Names or attendees mentioned
// 4. Check if dates are different - different dates likely mean new event
// 5. Case-insensitive matching

// Rules:
// - Different dates usually indicate a new event request, not modification
// - Return null for new event requests
// - Only match existing events if very high confidence
// - Multiple similar events should return null (new event)
// - Focus on exact time matches first

// Return ONLY:
// - null for new events
// - event ID as string for high confidence matches
// No other text or explanation allowed.`;

//   try {
//     const response = await this.model.generateContent(prompt);
//     const eventId = response.response.text().trim()
//       .replace(/^"/, '').replace(/"$/, '');
//     console.log(response, eventId);

//     // Extract title/name from query (similar to modify)
//     const titleMatch = query.match(/(?:cancel|delete|remove)\s+(.*?)(?:\s+on|to|from|at|$)/i);
//     const queryTitle = titleMatch ? titleMatch[1].toLowerCase() : '';
    
//     // Parse date from query
//     const parsedQuery = chrono.parse(query);
//     if (parsedQuery.length > 0) {
//       const queryDate = parsedQuery[0].start.date();

//       // First try to match by title and approximate time
//       for (const event of events) {
//         const eventTitle = event.summary.toLowerCase();
//         const eventDate = new Date(event.start.dateTime || event.start.date);
        
//         // First check title match
//         if (eventTitle.includes(queryTitle) || queryTitle.includes(eventTitle)) {
//           // Then check date proximity (within same day)
//           const dateDiff = Math.abs(queryDate - eventDate) / (1000 * 60 * 60 * 24);
//           if (dateDiff < 1) {  // Same day
//             // For cancellation, verify exact time match
//             if (queryDate.getHours() === eventDate.getHours() && 
//                 queryDate.getMinutes() === eventDate.getMinutes()) {
//               return event.id;
//             }
//           }
//         }
//       }
//     }

//     // If no matches found by title, try the model's suggestion
//     if (eventId && eventId !== "null" && events.find(event => event.id === eventId)) {
//       const matchedEvent = events.find(event => event.id === eventId);
//       const eventDate = new Date(matchedEvent.start.dateTime || matchedEvent.start.date);
      
//       if (parsedQuery.length > 0) {
//         const queryDate = parsedQuery[0].start.date();
        
//         // For cancellation, verify exact time match
//         if (queryDate.getHours() === eventDate.getHours() && 
//             queryDate.getMinutes() === eventDate.getMinutes() &&
//             queryDate.getDate() === eventDate.getDate() &&
//             queryDate.getMonth() === eventDate.getMonth()) {
//           return eventId;
//         }
//       }
//     }

//     return null;
//   } catch (error) {
//     console.error('Error finding existing event:', error);
//     return null;
//   }
// }
async extractEventDetails(message) {
  const prompt = `
  Extract comprehensive event details from this message: "${message}"
  Current date and time is ${new Date().toISOString()}
  
  Return ONLY a JSON object WITHOUT code blocks, formatting, or explanations. The object should have these EXACT fields:
  {
    "title": "string - full event title/subject including participants",
    "description": "string - additional details (or null)",
    "duration": "number - minutes (default 60)",
    "attendees": [], 
    "attendeeNames": ["strings - names of people mentioned"],
    "dateTime": "ISO string - specific date/time mentioned"
  }`;

  try {
    const response = await this.model.generateContent(prompt);
    let responseText = response.response.text().trim();
    responseText = responseText.replace(/```json\s*/gi, '')
      .replace(/```\s*/g, '')
      .replace(/^\s*{\s*/, '{')
      .replace(/\s*}\s*$/, '}')
      .trim();

    const parsed = JSON.parse(responseText);
    
    // Parse the date strictly as UTC first
    if (parsed.dateTime) {
      const parsedDate = chrono.strict.parse(parsed.dateTime, new Date(), { timezone: 'UTC' })[0];
      if (parsedDate) {
        parsed.dateTime = parsedDate.date().toISOString();
      }
    }

    // Create a title if attendees are present but no title
    if (!parsed.title && parsed.attendeeNames?.length > 0) {
      parsed.title = `Meeting with ${parsed.attendeeNames.join(' and ')}`;
    }

    return {
      title: parsed.title || 'New Event',
      description: parsed.description || null,
      duration: parsed.duration || 60,
      attendees: Array.isArray(parsed.attendees) ? parsed.attendees : [],
      attendeeNames: Array.isArray(parsed.attendeeNames) ? parsed.attendeeNames : [],
      dateTime: parsed.dateTime || null
    };
  } catch (error) {
    console.error('Error extracting event details:', error);
    // Try to recover with a basic extraction
    const parsedDate = chrono.strict.parse(message, new Date(), { timezone: 'UTC' })[0];
    return {
      title: 'New Event',
      description: null,
      duration: 60,
      attendees: [],
      attendeeNames: [],
      dateTime: parsedDate ? parsedDate.date().toISOString() : null
    };
  }
}

async handleCalendarQuery(message, context, assistantData, req, timezone) {
  try {
    // First, analyze if this is a calendar-related query
    const calendarIntent = await this.analyzeCalendarIntent(message);
    console.log('CALENDAR INTENT')
    console.log(calendarIntent)
    if (!calendarIntent.isCalendarRelated) {
      return {
        content: await this.generateResponse(message, context, {
          category: assistantData.category,
          language: 'en'
        }),
        requiresAction: false
      };
    }
    console.log(calendarIntent.isCalendarRelated)
    console.log(calendarIntent.type)
    switch (calendarIntent.type) {
      case 'check_schedule':
        return await this.handleScheduleCheck(message, calendarIntent.dateTime, req);
        
      case 'create_event':
        return await this.handleEventCreation(message, calendarIntent.eventDetails, req, timezone);
        
      case 'modify_event':
        return await this.handleEventModification(message, calendarIntent.eventDetails, req, timezone);
        
      case 'cancel_event':
        return await this.handleEventCancellation(message, calendarIntent.eventDetails, req, timezone);
        
      default:
        return {
          content: "I'm not sure what you'd like to do with your calendar. Would you like to check your schedule, create an event, or modify an existing event?",
          requiresAction: false
        };
    }
  } catch (error) {
    console.error('Calendar query handling error:', error);
    if (error.message?.includes('access_token') || 
    error.response?.data?.error === 'Failed to get user settings') {
  return {
    content: "To schedule meetings, you'll need to connect your Google Calendar first. Go To Overview and Select Calendar Integration",
    requiresAction: true,
    actionType: 'connect_calendar'
  };
}


    return {
      content: "I encountered an error while processing your calendar request. Please try again or contact support if the issue persists.",
      requiresAction: false
    };
  }
}



// async analyzeCalendarIntent(message) {
//   try {
//     const prompt = `
// Analyze this calendar-related message: "${message}"
// Current date is ${new Date().toISOString()}

// Return ONLY a JSON object WITHOUT code blocks or formatting. The object should have these EXACT fields:
// {
//   "isCalendarRelated": boolean,
//   "type": "check_schedule|create_event|modify_event|cancel_event",
//   "dateTime": "ISO string - specific date/time mentioned",
//   "eventDetails": {
//     "title": "string - event title/subject",
//     "description": "string or null",
//     "duration": number,
//     "attendees": [],
//     "attendeeNames": []
//   }
// }

// Example Input: "add meeting with dr smith on jan 2nd at 2pm"
// Example Output: {"isCalendarRelated":true,"type":"create_event","dateTime":"2024-01-02T14:00:00.000Z","eventDetails":{"title":"Meeting with Dr Smith","description":null,"duration":60,"attendees":[],"attendeeNames":["dr smith"]}}`;

//     const response = await this.model.generateContent(prompt);
//     const responseText = this.cleanJsonResponse(response.response.text());
//     const analysis = JSON.parse(responseText);

//     // Additional validation and cleanup
//     if (!analysis.isCalendarRelated) {
//       return {
//         isCalendarRelated: false,
//         type: null,
//         dateTime: null,
//         eventDetails: null
//       };
//     }

//     // Validate event type
//     if (!['check_schedule', 'create_event', 'modify_event', 'cancel_event'].includes(analysis.type)) {
//       analysis.type = null;
//     }

//     // Parse and validate dateTime
//     if (analysis.dateTime) {
//       const parsedDate = chrono.parseDate(analysis.dateTime);
//       if (parsedDate) {
//         analysis.dateTime = parsedDate;
//       }
//     }

//     // Clean up eventDetails
//     if (analysis.eventDetails) {
//       analysis.eventDetails = {
//         title: analysis.eventDetails.title || 'New Event',
//         description: analysis.eventDetails.description || null,
//         duration: Number(analysis.eventDetails.duration) || 60,
//         attendees: [],
//         attendeeNames: analysis.eventDetails.attendeeNames || []
//       };
//     }

//     return analysis;
//   } catch (error) {
//     console.error('Calendar intent analysis error:', error);
//     // Try to recover with basic date parsing
//     const parsedDate = chrono.parseDate(message);
//     return {
//       isCalendarRelated: true,
//       type: 'create_event',
//       dateTime: parsedDate || null,
//       eventDetails: {
//         title: 'New Event',
//         description: null,
//         duration: 60,
//         attendees: [],
//         attendeeNames: []
//       }
//     };
//   }
// }
async analyzeCalendarIntent(message) {
  try {
    const prompt = `
Analyze this calendar-related message: "${message}"
Current date is ${new Date().toISOString()}

ONLY consider this calendar-related if it specifically mentions:
1. Calendar terms (calendar, schedule, availability)
2. Time-related events (meetings, appointments, calls)
3. Specific scheduling actions (book, arrange, set up)


Creation signals (if ANY of these are present, it's a create_event):
- Words like "schedule", "create", "add", "book", "set up", "arrange"
- Phrases starting with "schedule/book/arrange meeting/call with"
- Mentions of new meetings or events with specific times
- Mentions of meeting/call/sync with someone at a specific time

Check schedule signals (ALL of these conditions must be met):
- Must contain AT LEAST ONE calendar-related term (schedule, calendar, meeting, appointment)
- Question words ("what", "show", "tell me", "do I have") must be followed by or near calendar terms
- Specific calendar-related phrases ONLY:
  - "what's my schedule"
  - "what meetings do I have"
  - "show me my calendar"
  - "what's happening on"
  - "do I have any meetings"
  - "what's on my calendar"

IMPORTANT VALIDATION:
- Message must contain at least ONE calendar term to be considered calendar-related
- Question words alone (what, when, how) are NOT sufficient to classify as calendar-related
- Must match specific calendar phrases or contain explicit calendar/schedule terms


Modification signals:
- "Change", "move", "reschedule", "update" existing events
- References to changing time of specific existing event

Cancellation signals:
- "Cancel", "delete", "remove" existing events
- References to removing specific existing event

Return ONLY a JSON object WITHOUT code blocks or formatting:
{
  "isCalendarRelated": boolean,
  "type": "check_schedule|create_event|modify_event|cancel_event",
  "dateTime": "ISO string - specific date/time mentioned",
  "eventDetails": {
    "title": "string - event title/subject",
    "description": "string or null",
    "duration": number,
    "attendees": [],
    "attendeeNames": []
  }
}

Examples:
1. "schedule meeting with dr smith on jan 2nd at 2pm"
   -> {"isCalendarRelated":true,"type":"create_event","dateTime":"2024-01-02T14:00:00.000Z","eventDetails":{"title":"Meeting with Dr Smith","description":null,"duration":60,"attendees":[],"attendeeNames":["dr smith"]}}
2. "what meetings do I have tomorrow?"
   -> {"isCalendarRelated":true,"type":"check_schedule","dateTime":"2024-01-03T00:00:00.000Z","eventDetails":null}
3. "set up a call with Jane for 3pm"
   -> {"isCalendarRelated":true,"type":"create_event","dateTime":"2024-01-02T15:00:00.000Z","eventDetails":{"title":"Call with Jane","description":null,"duration":60,"attendees":[],"attendeeNames":["jane"]}}
4. "what's my schedule for tomorrow?"
   -> {"isCalendarRelated":true,"type":"check_schedule","dateTime":"2024-01-03T00:00:00.000Z","eventDetails":null}

   
   `;

    const response = await this.model.generateContent(prompt);
    const responseText = this.cleanJsonResponse(response.response.text());
    const analysis = JSON.parse(responseText);

    // Additional validation and cleanup
    if (!analysis.isCalendarRelated) {
      return {
        isCalendarRelated: false,
        type: null,
        dateTime: null,
        eventDetails: null
      };
    }

    // Validate event type
    if (!['check_schedule', 'create_event', 'modify_event', 'cancel_event'].includes(analysis.type)) {
      analysis.type = null;
    }

    
    // Additional check for creation-specific words
    const creationWords = ['schedule', 'create', 'add', 'book', 'set up', 'arrange'];
    const messageWords = message.toLowerCase().split(' ');
    const hasCreationWord = creationWords.some(word => 
      messageWords.includes(word) || messageWords.includes(word.replace(' ', ''))
    );
    
    // If message has creation words, force type to create_event
    if (hasCreationWord && analysis.type !== 'create_event') {
      analysis.type = 'create_event';
    }

    // const scheduleCheckWords = ['what', 'show', 'tell', 'any', 'do i have'];
    // const hasScheduleWord = scheduleCheckWords.some(word => messageWords.includes(word));
    
    // If it has schedule check words, override to check_schedule
    // if (hasScheduleWord) {
    //   analysis.type = 'check_schedule';
    //   analysis.eventDetails = null;
    // }
    // Parse and validate dateTime
    if (analysis.dateTime) {
      const parsedDate = chrono.parseDate(analysis.dateTime);
      if (parsedDate) {
        analysis.dateTime = parsedDate;
      }
    }

    // Clean up eventDetails
    if (analysis.eventDetails) {
      analysis.eventDetails = {
        title: analysis.eventDetails.title || 'New Event',
        description: analysis.eventDetails.description || null,
        duration: Number(analysis.eventDetails.duration) || 60,
        attendees: [],
        attendeeNames: analysis.eventDetails.attendeeNames || []
      };
    }

    // Additional validation for create_event type
    if (analysis.type === 'create_event' && !analysis.eventDetails) {
      analysis.eventDetails = {
        title: 'New Event',
        description: null,
        duration: 60,
        attendees: [],
        attendeeNames: []
      };
    }

    // Log the final analysis for debugging
    console.log('Calendar Intent Analysis:', analysis);

    return analysis;
  } catch (error) {
    console.error('Calendar intent analysis error:', error);
    // Try to recover with basic date parsing
    const parsedDate = chrono.parseDate(message);
    return {
      isCalendarRelated: true,
      type: 'create_event', // Default to create_event for error recovery
      dateTime: parsedDate || null,
      eventDetails: {
        title: 'New Event',
        description: null,
        duration: 60,
        attendees: [],
        attendeeNames: []
      }
    };
  }
}
async handleEventCreation(message, eventDetails, req, timezone) {
  try {
    let details = eventDetails;
    if (!details || !details.dateTime) {
      details = await this.extractEventDetails(message);
    }
    
    if (!details || !details.dateTime) {
      return {
        content: "I need to know when you'd like to schedule this event. Could you please provide a specific date and time?",
        requiresAction: true,
        actionType: 'specify_time'
      };
    }

    if (details.attendeeNames.length > 0 && !details.title.toLowerCase().includes('with')) {
      details.title = `${details.title} with ${details.attendeeNames.join(' and ')}`;
    }

    // Get user's timezone first
    const userSettingsResponse = await axios.get(
      `${process.env.API_URL}/api/calendar/settings`,
      {
        headers: { Authorization: req.headers.authorization }
      }
    );

    const userTimeZone = timezone || 'UTC';
    console.log("User Time Zone:", userTimeZone);
    console.log("Message:", message);
    
    // Parse the date directly from the message, similar to modification
    const parsed = chrono.parse(message);
    if (parsed.length === 0) {
      return {
        content: "I couldn't understand the time. Please specify the time more clearly (e.g., '2:00 PM').",
        requiresAction: true,
        actionType: 'specify_time'
      };
    }

    // Use the same approach as modification code
    const parsedResult = parsed[0];
    const startDate = parsedResult.start.date();
    
    console.log("Parsed date before conversion:", startDate);
    console.log("Parsed date hours:", startDate.getHours());
    // Create the times using the same approach as modification code
    const startDateTime = DateTime.fromObject({
      year: startDate.getFullYear(),
      month: startDate.getMonth() + 1,
      day: startDate.getDate(),
      hour: startDate.getHours(),
      minute: startDate.getMinutes()
    }, { zone: userTimeZone });
   
    const endDateTime = startDateTime.plus({ minutes: details.duration || 60 });
    // Log the actual times for debugging
    console.log("Final start time:", startDateTime.toISO());
    console.log("Final end time:", endDateTime.toISO());
    
    // Check availability
    const availabilityResponse = await axios.get(
      `${process.env.API_URL}/api/calendar/availability`,
      {
        params: {
          startTime: startDateTime.toISO(),
          endTime: endDateTime.toISO()
        },
        headers: { Authorization: req.headers.authorization }
      }
    );

    if (availabilityResponse.data.calendars?.primary?.busy?.length > 0) {
      return {
        content: `It looks like you're already busy at that time. Would you like to see some alternative times?`,
        requiresAction: true,
        actionType: 'suggest_alternative'
      };
    }

    // Create the event
    const response = await axios.post(
      `${process.env.API_URL}/api/calendar/events`,
      {
        title: details.title || 'New Event',
        description: details.description,
        start: {
          dateTime: startDateTime.toISO(),
          timeZone: userTimeZone
        },
        end: {
          dateTime: endDateTime.toISO(),
          timeZone: userTimeZone
        },
        attendees: details.attendees?.filter(email => 
          /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
        ) || []
      },
      {
        headers: { Authorization: req.headers.authorization }
      }
    );

    // Format the date consistently
    const formattedDate = startDateTime.toLocaleString(DateTime.DATETIME_FULL);

    let attendeeMessage = '';
    if (details.attendeeNames?.length > 0 && (!details.attendees || details.attendees.length === 0)) {
      attendeeMessage = ` with ${details.attendeeNames.join(' and ')}. Note: I couldn't send calendar invitations as I don't have their email addresses.`;
    } else if (details.attendees?.length > 0) {
      attendeeMessage = `. I've sent calendar invitations to ${details.attendees.join(', ')}.`;
    }

    return {
      content: `Perfect! I've scheduled "${details.title || 'your event'}" for ${formattedDate}${attendeeMessage}`,
      requiresAction: false,
      event: response.data
    };
  } catch (error) {
    if (error.response?.data?.error === 'Google Calendar not connected') {
      return {
        content: "To schedule events, you'll need to connect your Google Calendar first. Would you like help with that?",
        requiresAction: true,
        actionType: 'connect_calendar'
      };
    }
    throw error;
  }
}

async handleScheduleCheck(message, dateTime, req) {
  try {
    const response = await axios.get(
      `${process.env.API_URL}/api/calendar/events`,
      {
        params: { query: message },
        headers: { Authorization: req.headers.authorization }
      }
    );

    if (response.data.events.length === 0) {
      return {
        content: `You have no events scheduled ${dateTime ? `for ${dateTime}` : 'today'}. Would you like to schedule something?`,
        requiresAction: false
      };
    }

    const prompt = `
The user asked: "${message}"
Here are their events: ${JSON.stringify(response.data.events)}

Create a natural, conversational response that:
1. Summarizes their schedule
2. Mentions specific times and event names
3. Keeps a friendly, helpful tone
4. Is concise but informative`;

    const summarizedResponse = await this.generateResponse(prompt, [], {
      category: 'calendar',
      language: 'en'
    });

    return {
      content: summarizedResponse.content,
      requiresAction: false,
      events: response.data.events
    };
  } catch (error) {
    if (error.response?.data?.error === 'Google Calendar not connected') {
      return {
        content: "To check your schedule, you'll need to connect your Google Calendar first. Would you like help with that?",
        requiresAction: false
      };
    }
    throw error;
  }
}

async findExistingEvent(query, events, userTimeZone) {
  console.log('Finding existing event...');
  console.log('Query:', query);
  console.log('Available events:', JSON.stringify(events, null, 2));

  const prompt = `
Given this user query: "${query}"
And these calendar events: ${JSON.stringify(events)}

Analyze if this is a new event request or refers to an existing event.
Consider:
1. Exact date and time match is highest priority
2. Similar event types (meetings, appointments, calls, discussions, sessions, catchups, syncs, etc)
3. Names or attendees mentioned
4. Check if dates are different - different dates likely mean new event
5. Case-insensitive matching

Rules:
- Different dates usually indicate a new event request, not modification
- Return null for new event requests
- Only match existing events if very high confidence
- Multiple similar events should return null (new event)
- Focus on exact time matches first

Return ONLY:
- null for new events
- event ID as string for high confidence matches
No other text or explanation allowed.`;

try {
  const response = await this.model.generateContent(prompt);
  const eventId = response.response.text().trim().replace(/^"/, '').replace(/"$/, '');
  console.log('Model suggested event ID:', eventId);

  const titleMatch = query.match(/(?:cancel|delete|remove)\s+(.*?)(?:\s+on|to|from|at|$)/i);
  const queryTitle = titleMatch ? titleMatch[1].toLowerCase() : '';
  
  const parsedQuery = chrono.parse(query);
  if (parsedQuery.length > 0) {
    const parsedDate = parsedQuery[0].start.date();
const queryDateTime = DateTime.fromObject({
  year: parsedDate.getFullYear(),
  month: parsedDate.getMonth() + 1,
  day: parsedDate.getDate(),
  hour: parsedDate.getHours(),
  minute: parsedDate.getMinutes()
}, { zone: userTimeZone });
    console.log('Query DateTime:', queryDateTime.toISO());

    // Check all events
    for (const event of events) {
      const eventTitle = event.summary.toLowerCase();
      const eventDateTime = DateTime.fromISO(event.start.dateTime || event.start.date, {
        zone: userTimeZone
      });
      
      const titleMatch = eventTitle.includes(queryTitle.replace(/\s+/g, ' ').trim()) || 
                        queryTitle.includes(eventTitle.replace(/\s+/g, ' ').trim());
      
      const timeMatch = eventDateTime.hasSame(queryDateTime, 'day') && 
                       eventDateTime.hour === queryDateTime.hour && 
                       eventDateTime.minute === queryDateTime.minute;

      console.log('Comparing event:', {
                        id: event.id,
                        title: event.summary,
                        eventTime: eventDateTime.toISO(),
                        queryTime: queryDateTime.toISO(),
                        titleMatch,
                        timeMatch,
                        eventHour: eventDateTime.hour,
                        queryHour: queryDateTime.hour
                      });
                

      if (timeMatch) {
        return event.id;
      }
    }

    // Check model suggestion
    if (eventId && eventId !== "null") {
      const suggestedEvent = events.find(e => e.id === eventId);
      if (suggestedEvent) {
        const eventDateTime = DateTime.fromISO(suggestedEvent.start.dateTime || suggestedEvent.start.date, {
          zone: userTimeZone
        });
        
        if (eventDateTime.hasSame(queryDateTime, 'day') && 
            eventDateTime.hour === queryDateTime.hour && 
            eventDateTime.minute === queryDateTime.minute) {
          return eventId;
        }
      }
    }
  }

  return null;
} catch (error) {
  console.error('Error finding event:', error);
  return null;
}
}


async handleEventCancellation(message, eventDetails, req, timezone) {
  try {
    // Fetch user timezone
    const userSettingsResponse = await axios.get(
      `${process.env.API_URL}/api/calendar/settings`,
      { headers: { Authorization: req.headers.authorization } }
    );
    const userTimeZone = timezone || 'UTC';
    console.log("User TimeZone:", userTimeZone);

    // Parse the date from the message
    const parsed = chrono.parse(message);
    if (parsed.length === 0) {
      return {
        content: "I couldn't understand which event you'd like to cancel. Please specify the time more clearly.",
        requiresAction: true,
        actionType: 'specify_event'
      };
    }

    const parsedResult = parsed[0];
    const startDate = parsedResult.start.date();

    console.log("Parsed date before conversion:", startDate);
    console.log("Parsed date hours:", startDate.getHours());

    // Create DateTime object using fromObject
    const targetDateTime = DateTime.fromObject({
      year: startDate.getFullYear(),
      month: startDate.getMonth() + 1,
      day: startDate.getDate(),
      hour: startDate.getHours(),
      minute: startDate.getMinutes()
    }, { zone: userTimeZone });

    console.log("Target DateTime:", targetDateTime.toISO());

    const dayStart = targetDateTime.startOf('day');
    const dayEnd = targetDateTime.endOf('day');

    // Fetch events within the day
    const response = await axios.get(
      `${process.env.API_URL}/api/calendar/events`,
      {
        params: { 
          startTime: dayStart.toISO(),
          endTime: dayEnd.toISO()
        },
        headers: { Authorization: req.headers.authorization }
      }
    );

    // Find the existing event
    const eventId = await this.findExistingEvent(message, response.data.events, userTimeZone);
    console.log("Found Event ID:", eventId);

    if (!eventId) {
      return {
        content: "I couldn't find the event you're referring to. Could you please verify the time and details?",
        requiresAction: true,
        actionType: 'specify_event',
        events: response.data.events
      };
    }

    const eventToDelete = response.data.events.find(event => event.id === eventId);
    const eventDateTime = DateTime.fromISO(eventToDelete.start.dateTime || eventToDelete.start.date, {
      zone: userTimeZone
    });
    const formattedDate = eventDateTime.toLocaleString(DateTime.DATETIME_FULL);

    // Delete the event
    await axios.delete(
      `${process.env.API_URL}/api/calendar/events/${eventToDelete.id}`,
      { headers: { Authorization: req.headers.authorization } }
    );

    return {
      content: `I've cancelled "${eventToDelete.summary}" scheduled for ${formattedDate}. It's been removed from your calendar.`,
      requiresAction: false
    };
  } catch (error) {
    console.error('Event cancellation error:', error);
    if (error.response?.data?.error === 'Google Calendar not connected') {
      return {
        content: "To cancel events, you'll need to connect your Google Calendar first. Would you like help with that?",
        requiresAction: true,
        actionType: 'connect_calendar'
      };
    }
    throw error;
  }
}



async handleEventModification(message, eventDetails, req, timezone) {
  try {
    // Fetch user timezone
    const userSettingsResponse = await axios.get(
      `${process.env.API_URL}/api/calendar/settings`,
      {
        headers: { Authorization: req.headers.authorization }
      }
    );
    const userTimeZone = timezone || 'UTC';
    console.log("User Time Zone:", userTimeZone);
    
    // Parse date from message
    const parsed = chrono.parse(message);
    if (parsed.length === 0) {
      return {
        content: "I couldn't understand which event you'd like to modify. Please specify the time more clearly.",
        requiresAction: true,
        actionType: 'specify_event'
      };
    }

    const parsedResult = parsed[0];
    const startDate = parsedResult.start.date();

    console.log("Parsed date before conversion:", startDate);
    console.log("Parsed date hours:", startDate.getHours());

    // Create DateTime object using fromObject
    const targetDateTime = DateTime.fromObject({
      year: startDate.getFullYear(),
      month: startDate.getMonth() + 1,
      day: startDate.getDate(),
      hour: startDate.getHours(),
      minute: startDate.getMinutes()
    }, { zone: userTimeZone });

    if (targetDateTime < DateTime.now()) {
      return {
        content: "Please specify a future date for the event modification.",
        requiresAction: true,
        actionType: 'specify_event'
      };
    }

    // Fetch events within ±7 days around the target date
    const dayStart = targetDateTime.startOf('day').minus({ days: 7 });
    const dayEnd = targetDateTime.endOf('day').plus({ days: 7 });

    const response = await axios.get(
      `${process.env.API_URL}/api/calendar/events`,
      {
        params: { 
          startTime: dayStart.toISO(),
          endTime: dayEnd.toISO()
        },
        headers: { Authorization: req.headers.authorization }
      }
    );

    // Find the existing event
    const eventId = await this.findmodifyingevent(message, response.data.events);
    
    if (!eventId) {
      return {
        content: "I couldn't find the event you're referring to. Could you please verify the time and details?",
        requiresAction: true,
        actionType: 'specify_event',
        events: response.data.events
      };
    }

    const existingEvent = response.data.events.find(event => event.id === eventId);
    if (!existingEvent) {
      throw new Error('Event not found after ID was matched');
    }

    // Create DateTime objects for existing event times
    const existingStart = DateTime.fromISO(existingEvent.start.dateTime || existingEvent.start.date, {
      zone: userTimeZone
    });
    const existingEnd = DateTime.fromISO(existingEvent.end.dateTime || existingEvent.end.date, {
      zone: userTimeZone
    });

    // Calculate duration
    const duration = existingEnd.diff(existingStart).as('minutes');

    // Create new start time using fromObject
    const newStartDate = parsedResult.start.date();
    const newStartTime = DateTime.fromObject({
      year: newStartDate.getFullYear(),
      month: newStartDate.getMonth() + 1,
      day: newStartDate.getDate(),
      hour: newStartDate.getHours(),
      minute: newStartDate.getMinutes()
    }, { zone: userTimeZone });

    // Calculate new end time based on duration
    const newEndTime = newStartTime.plus({ minutes: duration });

    // Prepare update data
    const updateData = {
      summary: existingEvent.summary,
      description: existingEvent.description,
      start: {
        dateTime: newStartTime.toISO(),
        timeZone: userTimeZone
      },
      end: {
        dateTime: newEndTime.toISO(),
        timeZone: userTimeZone
      }
    };

    console.log('Updating event with data:', updateData);

    // Update the event
    const updateResponse = await axios.patch(
      `${process.env.API_URL}/api/calendar/events/${eventId}`,
      updateData,
      {
        headers: { Authorization: req.headers.authorization }
      }
    );

    // Format response time
    const formattedTime = newStartTime.toLocaleString(DateTime.DATETIME_FULL);

    return {
      content: `I've updated "${updateData.summary}" to ${formattedTime}.`,
      requiresAction: false,
      event: updateResponse.data
    };

  } catch (error) {
    console.error('Event modification error:', error);
    if (error.response?.data?.error === 'Google Calendar not connected') {
      return {
        content: "To modify events, you'll need to connect your Google Calendar first. Would you like help with that?",
        requiresAction: true,
        actionType: 'connect_calendar'
      };
    }
    return {
      content: "I encountered an error while trying to modify the event. Could you please try again or specify the event in a different way?",
      requiresAction: true,
      actionType: 'specify_event'
    };
  }
}


async findmodifyingevent(query, events, userTimeZone) {
  console.log('Incoming query:', query);
  console.log('Available events:', JSON.stringify(events, null, 2));

  const prompt = `
Given this user query: "${query}"
And these calendar events: ${JSON.stringify(events)}

Task: Find if the query refers to an existing event in the calendar.

Rules for matching (in priority order):
1. Extract event title/description from query (e.g., "meeting with Mr. Smith" from "reschedule the meeting with Mr. Smith")
2. Look for exact or similar title matches first
3. For queries with "reschedule", "modify", "change", "move" - ensure it's a modification request
4. Then verify date match for found events
5. For modification requests, ignore time differences since the time is being changed

Return ONLY:
- Event ID as string if confident match found
- null if no match or uncertain

Example matches:
- "reschedule meeting with John from 2pm to 3pm" matches "Meeting with John" or "John sync" on the same date
- "move my 2pm call to 4pm" matches "Team Call" on that date
`;

  try {
    const response = await this.model.generateContent(prompt);
    const eventId = response.response.text().trim().replace(/^"/, '').replace(/"$/, '');

    console.log('Model response text:', response.response.text());
    console.log('Parsed event ID:', eventId);

    // Extract the intended title/name from the query
    const titleMatch = query.match(/(?:reschedule|modify|change|move)\s+(.*?)(?:\s+on|to|from|at|$)/i);
    const queryTitle = titleMatch ? titleMatch[1].toLowerCase() : '';
    console.log('Extracted title:', queryTitle);

    // Manual check for events with title match first
    const parsedQuery = chrono.parse(query);
    if (parsedQuery.length > 0) {
      const parsedResult = parsedQuery[0];
      const queryDate = parsedResult.start.date();

      console.log('Parsed query date before conversion:', queryDate);

      // Create DateTime object using fromObject
      const queryDateTime = DateTime.fromObject({
        year: queryDate.getFullYear(),
        month: queryDate.getMonth() + 1,
        day: queryDate.getDate(),
        hour: queryDate.getHours(),
        minute: queryDate.getMinutes()
      }, { zone: userTimeZone });

      console.log('Query DateTime:', queryDateTime.toISO());

      for (const event of events) {
        const eventTitle = event.summary.toLowerCase();
        const eventDate = new Date(event.start.dateTime || event.start.date);
        
        // Create DateTime object using fromObject
        const eventDateTime = DateTime.fromObject({
          year: eventDate.getFullYear(),
          month: eventDate.getMonth() + 1,
          day: eventDate.getDate(),
          hour: eventDate.getHours(),
          minute: eventDate.getMinutes()
        }, { zone: userTimeZone });

        console.log('Comparing with event:', {
          id: event.id,
          summary: event.summary,
          dateTime: eventDateTime.toISO(),
          titleMatch: eventTitle.includes(queryTitle) || queryTitle.includes(eventTitle)
        });

        // First priority: title match
        if (eventTitle.includes(queryTitle) || queryTitle.includes(eventTitle)) {
          // Then verify date is within reasonable range (e.g., within 7 days)
          const dateDiff = Math.abs(queryDateTime.diff(eventDateTime, 'days').days);
          if (dateDiff <= 7) {  // Within a week
            console.log(`Matched Event ID: ${event.id} based on title and date proximity.`);
            return event.id;
          }
        }
      }
    }

    // If no direct title matches, try the model's suggestion
    if (eventId && eventId !== "null" && events.find(e => e.id === eventId)) {
      const matchedEvent = events.find(e => e.id === eventId);
      const eventDate = new Date(matchedEvent.start.dateTime || matchedEvent.start.date);

      // Create DateTime object using fromObject
      const matchedEventDateTime = DateTime.fromObject({
        year: eventDate.getFullYear(),
        month: eventDate.getMonth() + 1,
        day: eventDate.getDate(),
        hour: eventDate.getHours(),
        minute: eventDate.getMinutes()
      }, { zone: userTimeZone });

      // Verify date is within reasonable range
      if (parsedQuery.length > 0) {
        const queryDate = parsedQuery[0].start.date();

        // Create DateTime object using fromObject
        const queryDateTime = DateTime.fromObject({
          year: queryDate.getFullYear(),
          month: queryDate.getMonth() + 1,
          day: queryDate.getDate(),
          hour: queryDate.getHours(),
          minute: queryDate.getMinutes()
        }, { zone: userTimeZone });

        const dateDiff = Math.abs(queryDateTime.diff(matchedEventDateTime, 'days').days);
        if (dateDiff <= 7) {
          console.log(`Matched Event ID: ${matchedEvent.id} based on model suggestion and date proximity.`);
          return eventId;
        }
      }
    }

    console.log('No matching event found.');
    return null;
  } catch (error) {
    console.error('Error finding modifying event:', error);
    return null;
  }
}


/************************************************************
 * 3) For handling Assistant chat Gmail
 ************************************************************/
async handleGmailQuery(message, previousMessages, assistantData, req) {
  // Simplify to only return email composition details
  try {
    const emailIntent = await this.analyzeEmailIntent(message);
    
    if (emailIntent.isEmailRelated) {
      return {
        type: 'email',
        recipient: emailIntent.intent.recipient,
        subject: emailIntent.intent.subject,
        content: emailIntent.intent.content
      };
    }
    
    return null;
  } catch (error) {
    console.error('Gmail handling error:', error);
    throw error;
  }
}



async analyzeEmailIntent(message) {
  const prompt = `
Analyze this message for email-related intent: "${message}"

Rules:
1. ANY message containing "send email", "write email", or similar MUST be considered email-related
2. When recipient is mentioned (e.g., "to John"), extract it
3. Look for subject or content hints in the message
4. Default to composition intent if unclear

Return ONLY a JSON object:
{
  "isEmailRelated": boolean,
  "type": "send_email|check_emails|search_emails",
  "intent": {
    "action": "compose|send|check|search",
    "recipient": string or null,
    "subject": string or null,
    "content": string or null,
    "confidence": number
  }
}`;

  try {
    const response = await this.model.generateContent(prompt);
    let analysis = JSON.parse(this.cleanJsonResponse(response.response.text()));
    
    // Force email-related for common patterns
    if (message.toLowerCase().match(/\b(send|write|compose)\b.*\b(email|mail|message)\b/)) {
      analysis.isEmailRelated = true;
      analysis.type = 'send_email';
      analysis.intent = analysis.intent || {};
      analysis.intent.action = 'compose';
    }

    return analysis;
  } catch (error) {
    console.error('Email intent analysis error:', error);
    // Default to email composition for error recovery
    return {
      isEmailRelated: true,
      type: 'send_email',
      intent: {
        action: 'compose',
        recipient: null,
        subject: null,
        content: null,
        confidence: 0.5
      }
    };
  }
}



async extractEmailDetails(message, previousDetails = null) {
  try {
    const prompt = `
Extract email details from this message: "${message}"
${previousDetails ? `Previous details: ${JSON.stringify(previousDetails)}` : ''}

CRITICAL RULES:
1. If an email address is present in the message, EXTRACT IT
2. If no email but a name is mentioned after "to" or "for" or at start, extract as recipient
3. Look for subject after "subject:", "about:", or "regarding:"
4. Remaining content could be email body
5. Strict email validation - must have @ and domain

Return ONLY a JSON object with these EXACT fields:
{
  "to": string or null,  // email address or name if no email
  "subject": string or null,  // email subject
  "content": string or null,  // email content/body
  "complete": boolean,  // whether all required fields are present
  "hasValidEmail": boolean  // whether the 'to' field is a valid email
}`;

    const response = await this.model.generateContent(prompt);
    const details = JSON.parse(this.cleanJsonResponse(response.response.text()));

    // Additional email validation
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/;
    const extractedEmail = message.match(emailRegex);

    // Merge with previous details if available
    return {
      to: extractedEmail ? extractedEmail[0] : (details.to || previousDetails?.to || null),
      subject: details.subject || previousDetails?.subject || null,
      content: details.content || previousDetails?.content || null,
      complete: Boolean(details.to && details.subject && details.content),
      hasValidEmail: Boolean(extractedEmail || (details.to && emailRegex.test(details.to)))
    };
  } catch (error) {
    console.error('Email details extraction error:', error);
    return {
      to: previousDetails?.to || null,
      subject: previousDetails?.subject || null,
      content: previousDetails?.content || null,
      complete: false,
      hasValidEmail: false
    };
  }
}

async handleEmailComposition(message, details, req, assistantId) {
  try {
    console.log('Starting email composition with details:', details);
    
    // First ensure we have a valid email address
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/;
    if (details.to) {
      if (!emailRegex.test(details.to)) {
        // Store pending request for email address
        const pendingRequest = {
          type: 'email_composition',
          status: 'awaiting_input',
          timestamp: new Date(),
          assistantId,
          userId: req.user.id,
          currentInfo: {
            to: null,
            subject: details.subject || null,
            content: details.content || null
          },
          nextField: 'recipient',
          recipientName: details.to // Store the name for reference
        };

        const pendingDoc = await firestore.db.collection('pending_requests').add(pendingRequest);

        return {
          content: `I see you want to send an email to ${details.to}. What's their email address?`,
          requiresAction: true,
          actionType: 'compose_email',
          currentInfo: pendingRequest.currentInfo,
          needInfo: ['recipient'],
          pendingId: pendingDoc.id
        };
      }
    } else {
      // No recipient specified at all
      const pendingRequest = {
        type: 'email_composition',
        status: 'awaiting_input',
        timestamp: new Date(),
        assistantId,
        userId: req.user.id,
        currentInfo: {
          to: null,
          subject: details.subject || null,
          content: details.content || null
        },
        nextField: 'recipient'
      };

      const pendingDoc = await firestore.db.collection('pending_requests').add(pendingRequest);

      return {
        content: "Please provide the recipient's email address:",
        requiresAction: true,
        actionType: 'compose_email',
        currentInfo: pendingRequest.currentInfo,
        needInfo: ['recipient'],
        pendingId: pendingDoc.id
      };
    }

    // Rest of the function remains the same...
  } catch (error) {
    console.error('Error in email composition:', error);
    throw error;
  }
}

getPromptForField(field) {
  const prompts = {
    recipient: "Who would you like to send this email to?",
    subject: "What should be the subject of your email?",
    content: "What message would you like to include in your email?"
  };
  return prompts[field] || "Please provide more details for your email.";
}

async handleOngoingEmailComposition(message, pendingDoc, req) {
  console.log('Handling ongoing email composition:', {
    pendingData: pendingDoc.data(),
    message
  });
  try {
    const pendingData = pendingDoc.data();
    const currentInfo = pendingData.currentInfo || {};
    const userResponse = message.trim();

    // If we're collecting recipient info, validate email
    if (pendingData.nextField === 'recipient') {
      const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/;
      if (!emailRegex.test(userResponse)) {
        // Update the pending request to maintain state
        await pendingDoc.ref.update({
          timestamp: new Date(),
          recipientName: userResponse // Store the name if provided
        });

        return {
          content: `I need an email address to send to. What's the email address for ${userResponse}?`,
          requiresAction: true,
          actionType: 'compose_email',
          currentInfo: currentInfo,
          needInfo: ['recipient'],
          pendingId: pendingDoc.id
        };
      }
    }
    // Update the current field based on nextField
    const updatedInfo = { ...currentInfo };
    updatedInfo[pendingData.nextField] = userResponse;

    // Check remaining fields
    const missingFields = [];
    if (!updatedInfo.to) missingFields.push('recipient');
    if (!updatedInfo.subject) missingFields.push('subject');
    if (!updatedInfo.content) missingFields.push('content');

    // Remove the field we just collected
    const remainingFields = missingFields.filter(field => field !== pendingData.nextField);

    if (remainingFields.length > 0) {
      // Still need more information
      const nextField = remainingFields[0];
      const prompts = {
        recipient: "Who would you like to send this email to?",
        subject: "What should be the subject of your email?",
        content: "What message would you like to include in your email?"
      };

      // Update the pending request
      await pendingDoc.ref.update({
        currentInfo: updatedInfo,
        nextField: nextField,
        timestamp: new Date()
      });

      return {
        content: prompts[nextField],
        requiresAction: true,
        actionType: 'compose_email',
        currentInfo: updatedInfo,
        needInfo: remainingFields,
        pendingId: pendingDoc.id
      };
    }

    // We have all information, ask for confirmation
    await pendingDoc.ref.update({
      status: 'awaiting_confirmation',
      currentInfo: updatedInfo,
      timestamp: new Date()
    });

    const confirmationMessage = `Perfect! Here's the email I'll send:

To: ${updatedInfo.to}
Subject: ${updatedInfo.subject}
Message: ${updatedInfo.content}

Would you like me to send this email? (Please reply with 'yes' to confirm or 'no' to make changes)`;

    return {
      content: confirmationMessage,
      requiresAction: true,
      actionType: 'confirm_email',
      emailDetails: updatedInfo,
      pendingId: pendingDoc.id
    };
  } catch (error) {
    console.error('Error in ongoing email composition:', error);
    throw error;
  }
}

async handleEmailConfirmation(message, pendingDoc, req) {
  const userResponse = message.trim().toLowerCase();
  const pendingData = pendingDoc.data();

  if (userResponse === 'yes' || userResponse === 'confirm') {
    try {
      const emailDetails = pendingData.currentInfo;
      const response = await this.sendEmail(emailDetails, req.headers.authorization);

      await pendingDoc.ref.delete();
      
      return {
        content: "Email sent successfully! Is there anything else you need help with?",
        requiresAction: false,
        emailSent: true,
        exitEmailFlow: true
      };
    } catch (error) {
      console.error('Error sending email:', error);
      return {
        content: `Failed to send email: ${error.message}. Would you like to try again?`,
        requiresAction: true,
        actionType: 'retry_email',
        error: error.message,
        emailDetails: pendingData.currentInfo
      };
    }
  }

  if (userResponse === 'no') {
    await pendingDoc.ref.delete();
    return {
      content: "Email cancelled. What else can I help you with?",
      requiresAction: false,
      exitEmailFlow: true
    };
  }

  return {
    content: "Please reply with 'yes' to send the email or 'no' to cancel.",
    requiresAction: true,
    actionType: 'confirm_email',
    emailDetails: pendingData.currentInfo
  };
}
async handleEmailSearch(query, req) {
  // Implementation similar to handleEmailChecking but with search
  // Would use gmail.users.messages.list with q parameter
}

async handleEmailChecking(req) {
  // Implementation for listing recent emails
  // Would use gmail.users.messages.list
}
async sendEmail(emailDetails, authorizationToken) {
  try {
    const response = await axios.post(
      `${process.env.API_URL}/api/gmail/send`,
      {
        to: emailDetails.to,
        subject: emailDetails.subject,
        message: emailDetails.content
      },
      {
        headers: { 
          Authorization: authorizationToken,
          'Content-Type': 'application/json'
        }
      }
    );

    // Assuming the API returns a success status and some data
    if (response.status === 200) {
      console.log('Email sent successfully:', response.data);
      return response.data;
    } else {
      console.error('Unexpected response status:', response.status);
      throw new Error('Failed to send email due to unexpected response.');
    }
  } catch (error) {
    console.error('Error in sendEmail:', error.response ? error.response.data : error.message);
    
    // Enhance error handling based on response status or error type
    if (error.response) {
      // Server responded with a status other than 2xx
      throw new Error(`Email send failed: ${error.response.data.error || error.response.statusText}`);
    } else if (error.request) {
      // No response received from server
      throw new Error('Email send failed: No response from email service.');
    } else {
      // Other errors
      throw new Error(`Email send failed: ${error.message}`);
    }
  }
}


}
export default new GeminiService();