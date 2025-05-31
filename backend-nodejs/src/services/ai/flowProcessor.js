import { Firestore } from '@google-cloud/firestore';

class FlowProcessor {
  constructor(geminiService, firestore, vectors) {
    this.gemini = geminiService;
    this.firestore = firestore;
    this.vectors = vectors;
  }


  async processNode(node, message, sessionId, assistant, context = {}) {
    console.log('Processing Node:', node.id);
    console.log('Node Type:', node.type);
    console.log('Message:', message);
    console.log('Node Data:', node.data);
  
    const nodeData = node.data;
    if (!nodeData) {
      console.error('No data found for node:', node.id);
      return { content: 'Error processing node', complete: false };
    }
  
    // Ensure message is never null for Response Node
    let processedMessage = message;
    // Generate embeddings using the processed message
    const relevantVectors = await this.getVectorContext(
      processedMessage || nodeData.message,
      assistant.id
    );
  
    const fullContext = await this.buildContext(
      relevantVectors,
      assistant,
      context.previousMessages || []
    );
  

    let result;
    switch (node.type) {
      case 'dialogueNode':
        result = await this.handleDialogueNode({ ...node, message: nodeData.message, functions: nodeData.functions }, processedMessage, sessionId, assistant, fullContext);
        break;
      case 'scriptNode':
        result = await this.handleScriptNode({ ...node, message: nodeData.message }, processedMessage, sessionId, assistant, fullContext);
        break;
      case 'fieldSetterNode':
        result = await this.handleFieldSetterNode({ ...node, message: nodeData.message, fieldName: nodeData.fieldName }, processedMessage, sessionId, assistant, fullContext);
        break;
      case 'callTransferNode':
        result = await this.handleCallTransferNode({ ...node, message: nodeData.message, fieldName: nodeData.fieldName }, processedMessage, sessionId, assistant, fullContext);
        break;
      case 'responseNode':
        result = await this.handleResponseNode({ ...node, message: nodeData.message }, processedMessage, sessionId, assistant, fullContext);
        break;
      default:
        throw new Error(`Unknown node type: ${node.type}`);
    }
  
    console.log('PROCESS NODE');
    console.log(result.complete, !result.nextNode);
  
    // If no next node is found, return to the leading node
    if (result.complete && !result.nextNode) {
      const leadingNode = assistant.flowData.nodes.find(n => n.data.nodeType === 'leading');
      if (leadingNode) {
        // Update session state to indicate we're waiting for user input
        const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
        await sessionRef.set({
          currentNodeId: leadingNode.id,
          started: true,
          awaitingResponse: true, // Wait for user input
        }, { merge: true });
  
        // Process the leading node's message explicitly
        const leadingNodeResponse = await this.processNode(leadingNode, null, sessionId, assistant, context);
  
        // Return the combined response
        return {
          content: `${result.content}\n\n${leadingNodeResponse.content}`,
          complete: false,
          nextNode: leadingNode.id,
        };
      }
    }
  
    return result;
  }

  async handleDialogueNode(node, message, sessionId, assistant, context) {
    const sessionRef = await this.firestore.db.collection('chat_sessions').doc(sessionId);
    const session = await sessionRef.get();
    const sessionData = session.data() || {};
    // const isLeadingNode = node.data.nodeType === 'leading';

    if (!sessionData.started) {
      // First time hitting this node - generate initial response using node's message
      const response = await this.processWorkflowInstruction(node.data.message, context);
      const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);

  
      // Save state that we're waiting for user response
      await sessionRef.set({
        currentNodeId: node.id,
        started: true,
        awaitingResponse: hasOutgoingEdges,
        functions: node.data.functions,
      }, { merge: true });
  
      return {
        content: response,
        complete: !hasOutgoingEdges,
        nextNode: null, // No next node if there are no outgoing edges

      };
    }
  
    if (sessionData.awaitingResponse && message) {
      // Match user's response against functions
      const matchedFunction = await this.matchUserResponseToFunction(
        message,
        node.data.functions,
        context
      );
  
      // Find corresponding function ID
      const functionObj = node.data.functions.find(f => 
        f.content.toLowerCase().trim() === matchedFunction.toLowerCase().trim()
      );
  
      if (!functionObj) {
        return {
          content: "I couldn't quite understand that. Could you please try again with one of the available options?",
          complete: false,
        };
      }
  
      // Find the next node based on matched function
      const flow = assistant.flowData;
      const sourceHandle = `function-${node.id}-${functionObj.id}`;
      const edge = flow.edges.find(e => 
        e.source === node.id && 
        e.sourceHandle === sourceHandle
      );
  
      if (edge) {
        const nextNode = flow.nodes.find(n => n.id === edge.target);
  
        // Update session state
        await sessionRef.set({
          currentNodeId: nextNode.id,
          started: false,
          awaitingResponse: true,
        }, { merge: true });
  
        // Process the next node
        const nextNodeResponse = await this.processNode(nextNode, null, sessionId, assistant, context);
  
        return {
          content: nextNodeResponse.content,
          complete: nextNodeResponse.complete,
          nextNode: nextNode.id,
        };
      }
    }
    const response = await this.processWorkflowInstruction(node.data.message, context);
    return {
      content: response,
      complete: false,
    };
  }
  async handleScriptNode(node, message, sessionId, assistant, context) {
    console.log('SCRIPT NODE HITTED')
    const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    const session = await sessionRef.get();
    const sessionData = session.data() || {};
    const response = await this.processWorkflowInstruction(node.data.message, context);

    if (!sessionData.started) {
      // Generate response based on script instruction
  
      // Check if there are any outgoing edges
      const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
  
      if (!hasOutgoingEdges) {
        // If no outgoing edges, mark as complete
        await sessionRef.set({
          currentNodeId: node.id,
          started: true,
          awaitingResponse: false, // No need to wait for user input
        }, { merge: true });
  
        return {
          content: response,
          complete: true, // Mark as complete
          nextNode: null, // No next node
        };
      }
  
      // Check if there is a "Next Steps" function
      const nextStepsFunction = node.data.functions.find(f => f.type === 'nextSteps');
      console.log("NEXT STEP FUNCTION")
      console.log(nextStepsFunction)
      if (nextStepsFunction) {
          // If "Next Steps (Direct)" function exists, proceed directly to the next node
          const flow = assistant.flowData;
          const edge = flow.edges.find(e => e.source === node.id);
  
          if (edge) {
            const nextNode = flow.nodes.find(n => n.id === edge.target);
  
            // Update session state to move to the next node
            await sessionRef.set({
              currentNodeId: nextNode.id,
              started: false,
              awaitingResponse: true, // Wait for user input at the next node
            }, { merge: true });
  
            // Process the next node and get its response
            const nextNodeResponse = await this.processNode(nextNode, null, sessionId, assistant, context);
  
            // Combine responses from both nodes
            const combinedResponse = `${response}\n\n${nextNodeResponse.content}`;
  
            return {
              content: combinedResponse, // Combined response from both nodes
              complete: false, // Mark as incomplete to continue the flow
              nextNode: nextNode.id, // Move to the next node
            };
          }
      }
  
      // If no "Next Steps" function, wait for user response
      await sessionRef.set({
        currentNodeId: node.id,
        started: true,
        awaitingResponse: true, // Wait for user input
        functions: node.data.functions,
      }, { merge: true });
  
      return {
        content: response,
        complete: false, // Wait for user input
        nextNode: null,
      };
    }
  
    if (sessionData.awaitingResponse && message) {
      // If the node is waiting for user input, match the user's response to available functions
      const matchedFunction = await this.matchUserResponseToFunction(
        message,
        node.data.functions,
        context
      );
  
      // Find corresponding function
      const functionObj = node.data.functions.find(f => 
        f.content.toLowerCase().trim() === matchedFunction.toLowerCase().trim()
      );
  
      if (!functionObj) {
        return {
          content: response,
          complete: true,
        };
      }
  
      // Find the next node based on matched function
      const flow = assistant.flowData;
      const sourceHandle = `function-${node.id}-${functionObj.id}`;
      const edge = flow.edges.find(e => 
        e.source === node.id && 
        e.sourceHandle === sourceHandle
      );
  
      if (edge) {
        const nextNode = flow.nodes.find(n => n.id === edge.target);
  
        // Update session state
        await sessionRef.set({
          currentNodeId: nextNode.id,
          started: false,
          awaitingResponse: true, // Wait for user input at the next node
        }, { merge: true });
  
        // Process the next node
        const nextNodeResponse = await this.processNode(nextNode, null, sessionId, assistant, context);
  
        return {
          content: nextNodeResponse.content,
          complete: nextNodeResponse.complete,
          nextNode: nextNode.id,
        };
      }
    }
  
    // If no outgoing edges, mark as complete
    const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    if (!hasOutgoingEdges) {
      return {
        content: "This is the end of the flow.",
        complete: true, // Mark as complete
        nextNode: null, // No next node
      };
    }
  
  
    return {
      content: response,
      complete: false,
    };
  }

  async handleFieldSetterNode(node, message, sessionId, assistant, context) {
    const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    const session = await sessionRef.get();
    const sessionData = session.data() || {};
  
    const isLeadingNode = node.data.nodeType === 'leading';

    if (!sessionData.started) {
      const response = await this.processWorkflowInstruction(node.data.message, context);
      const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);

      // Save state that we're waiting for user response
      await sessionRef.set({
        currentNodeId: node.id,
        started: true,
        awaitingResponse: hasOutgoingEdges, // Wait for user input
        fieldToSet: node.data.fieldName,
      }, { merge: true });
  
      return { content: response,  
        complete: !hasOutgoingEdges, // Mark as complete if there are no outgoing edges
        nextNode: null, };
    }
  
    if (sessionData.awaitingResponse && message) {
      const validationResult = await this.validateFieldValue(
        sessionData.fieldToSet,
        message,
        context
      );
  
      // if (!validationResult.isValid) {
      //   return { content: validationResult.reason, complete: false };
      // }
  
      await sessionRef.set({
        [`fields.${sessionData.fieldToSet}`]: validationResult,
      }, { merge: true });
  
      const flow = assistant.flowData;
      const edge = flow.edges.find(e => e.source === node.id && e.sourceHandle === `${node.id}-right`);
  
      if (edge) {
        const nextNode = flow.nodes.find(n => n.id === edge.target);
  
        // Update session state
        await sessionRef.set({
          currentNodeId: nextNode.id,
          started: false,
          awaitingResponse: true, // Wait for user input
        }, { merge: true });
  
        // Process the next node
        return await this.processNode(nextNode, null, sessionId, assistant, context);
      }
    }
    const response = await this.processWorkflowInstruction(node.data.message, context);

    return {
      content: response,
      complete: false,
    };
  }

  async handleCallTransferNode(node, message, sessionId, assistant, context) {
    const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    const session = await sessionRef.get();
    const sessionData = session.data() || {};
  
    const isLeadingNode = node.data.nodeType === 'leading';

    if (!sessionData.started) {
      const response = await this.processWorkflowInstruction(node.data.message, context);
      const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);

      // Save state that we're waiting for user response
      await sessionRef.set({
        currentNodeId: node.id,
        started: true,
        awaitingResponse: hasOutgoingEdges, // Wait for user input
      }, { merge: true });
  
      return { content: response, 
        complete: !hasOutgoingEdges, // Mark as complete if there are no outgoing edges
        nextNode: null,  };
    }
  
    if (sessionData.awaitingResponse && message) {
      // Create transfer notification
      await this.firestore.db.collection('assistant_notifications').add({
        assistantId: assistant.id,
        type: 'call_transfer',
        message: node.data.message,
        sessionId,
        status: 'pending',
        createdAt: Firestore.FieldValue.serverTimestamp(),
      });
  
      const flow = assistant.flowData;
      const edge = flow.edges.find(e => e.source === node.id);
  
      if (edge) {
        const nextNode = flow.nodes.find(n => n.id === edge.target);
  
        // Update session state
        await sessionRef.set({
          currentNodeId: nextNode.id,
          started: false,
          awaitingResponse: true, // Wait for user input
        }, { merge: true });
  
        // Process the next node
        const nextNodeResponse = await this.processNode(nextNode, null, sessionId, assistant, context);
  
        return {
          content: nextNodeResponse.content,
          complete: nextNodeResponse.complete,
          nextNode: nextNode.id,
        };
      }
    }

    return {
      content: "Thank you for your patience. I am transferring you to one of our agents now.",
      complete: true,
    };
  }
  async handleResponseNode(node, message, sessionId, assistant, context) {
    console.log("Response Node");
    console.log("Message:", message);
  
    const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    const session = await sessionRef.get();
    const sessionData = session.data() || {};
  
    // If the session hasn't started, generate the initial response
    if (!sessionData.started) {
      const response = await this.gemini.generateFlowProcessor(node.data.message, context, {
        maxTokens: 1000,
        temperature: 0.7,
      });
  
      console.log('RESPONSE FROM FLOW PROCESSOR');
      console.log(response);
  
      // Check if there are any outgoing edges
      const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
  
      if (!hasOutgoingEdges) {
        // If no outgoing edges, mark as complete
        await sessionRef.set({
          currentNodeId: node.id,
          started: true,
          awaitingResponse: false, // No need to wait for user input
        }, { merge: true });
  
        return {
          content: response.content,
          complete: true, // Mark as complete
          nextNode: null, // No next node
        };
      }
  
      // If there are outgoing edges, wait for user response
      await sessionRef.set({
        currentNodeId: node.id,
        started: true,
        awaitingResponse: true, // Wait for user input
      }, { merge: true });
  
      return {
        content: response.content,
        complete: false, // Wait for user input
        nextNode: null,
      };
    }
  
    // If the session is awaiting a user response and a message is provided
    if (sessionData.awaitingResponse && message) {
      // Generate a response using the user's message
      const response = await this.gemini.generateSharedResponse(message, context, {
        maxTokens: 1000,
        category: assistant.category,
        language: 'en', // Default language
        tone: 'professional', // Default tone
        responseStyle: 'detailed', // Default response style
        complexityLevel: 'intermediate', // Default complexity level
        interactionStyle: 'collaborative', // Default interaction style
      });
  
      console.log('RESPONSE FROM SHARED RESPONSE');
      console.log(response);
  
      // Check if there are any outgoing edges
      const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
  
      if (!hasOutgoingEdges) {
        // If no outgoing edges, mark as complete
        await sessionRef.set({
          currentNodeId: node.id,
          started: true,
          awaitingResponse: false, // No need to wait for user input
        }, { merge: true });
  
        return {
          content: response.content,
          complete: true, // Mark as complete
          nextNode: null, // No next node
        };
      }
  
      // If there are outgoing edges, proceed to the next node
      const flow = assistant.flowData;
      const edge = flow.edges.find(e => e.source === node.id);
  
      if (edge) {
        const nextNode = flow.nodes.find(n => n.id === edge.target);
  
        // Update session state to move to the next node
        await sessionRef.set({
          currentNodeId: nextNode.id,
          started: false,
          awaitingResponse: true, // Wait for user input at the next node
        }, { merge: true });
  
        // Process the next node
        const nextNodeResponse = await this.processNode(nextNode, null, sessionId, assistant, context);
  
        // Return the combined response
        return {
          content: `${response.content}\n\n${nextNodeResponse.content}`,
          complete: false, // Mark as incomplete to continue the flow
          nextNode: nextNode.id, // Move to the next node
        };
      }
    }
  
    // Default fallback response
    return {
      content: "This is the end of the flow.",
      complete: true, // Mark as complete
      nextNode: null, // No next node
    };
  }
  async matchUserResponseToFunction(userMessage, functions, context) {
    const prompt = `
    Analyze this user message and determine which function it matches best.

    User message: "${userMessage}"

    Available functions:
    ${functions.map(f => `- ${f.content}`).join('\n')}

    Return the function name that best matches the user's intent.
    `;
    console.log('Matching User Response')
    console.log(prompt)
    const response = await this.gemini.generateFlowProcessor(prompt, context, {
      maxTokens: 200,
      temperature: 0.3, // Lower temperature for more precise matching
    });
    console.log('Reciving Matching User Response')
    console.log(response.content)

    return response.content.trim();
  }

  async processWorkflowInstruction(instruction, context) {
    const prompt = `
    Process this workflow instruction and generate an appropriate response:
    "${instruction}"

    Context:
    ${context.map(c => `${c.role}: ${c.content}`).join('\n')}

     Guidelines for your response:
  1. Do not start with greetings like "Hi there," "Hello," or "Hey." untill specifically asked in the instruction or in context. 
  2. Be concise and to the point.
  3. Maintain a professional yet conversational tone.
  4. Use conversational phrases like "Hmm," "Ah, I see," or "Let me think about that" to make the interaction more human-like.
  `;
    console.log('Processing Workflow instructions')
    // console.log(prompt)
    const response = await this.gemini.generateProcessFlowProcessor(prompt, context, {
      maxTokens: 500,
      temperature: 0.7,
    });
    console.log('Reciving Processing Workflow instructions')
    // console.log(response.content)
    return response.content;
  }

  async validateFieldValue(fieldName, value, context) {
    const prompt = `
    Extract the required information from the user's message based on the field name:
    Field: ${fieldName}
    Value: "${value}"
  
    Context:
    ${context.map(c => `${c.role}: ${c.content}`).join('\n')}
  
    Based on the field name, extract the following:
    - For "date": Extract a date.
    - For "time": Extract a time.
    - For "email": Extract an email address.
    - For "phone": Extract a phone number.
    - For other fields: Extract the relevant information.
  
    Return only the extracted value as a plain text response.
    `;
    console.log('Extracting field value');
    console.log(prompt);
  
    const response = await this.gemini.generateFlowProcessor(prompt, context, {
      maxTokens: 300,
      temperature: 0.5,
    });
  
    console.log("Receiving extracted field value");
    console.log(response.content);
  
    // Return the extracted value directly
    return response.content.trim();
  }
  async getVectorContext(message, assistantId) {
    const messageEmbedding = await this.gemini.generateEmbeddings(message);
    return await this.vectors.searchVectors(messageEmbedding, 5, {
      assistantId,
      type: ['instructions', 'document'],
      includeMetadata: true,
    });
  }

  async buildContext(vectors, assistant, previousMessages) {
    const context = [];

    if (assistant.instructions) {
      context.push({
        role: 'system',
        content: `Instructions: ${assistant.instructions}`,
      });
    }

    vectors.forEach((vec) => {
      if (vec.metadata?.content) {
        context.push({
          role: 'system',
          content: `Content from ${vec.metadata.name}: ${vec.metadata.content}`,
        });
      }
    });

    previousMessages.forEach((msg) => {
      context.push(msg);
    });

    return context;
  }
}

export default FlowProcessor;