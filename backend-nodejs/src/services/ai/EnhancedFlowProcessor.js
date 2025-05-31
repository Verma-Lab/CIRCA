import { Firestore } from '@google-cloud/firestore';
import SmartTagger from './TagingAndStoring.js';

class EnhancedFlowProcessor {
    constructor(geminiService, firestore, vectors, userId) {
        this.gemini = geminiService;
        this.firestore = firestore;
        this.vectors = vectors;
        this.userId = userId; // Store userId
        this.smartTagger = new SmartTagger(geminiService, userId); // Pass userId to SmartTagger

    }

    findStartingNode(nodes) {
        return Promise.resolve(nodes.find(n => n.data.nodeType === 'starting'));
    }
    
    // Helper method to get current node
    getCurrentNode(currentNodeId, nodes) {
        return Promise.resolve(nodes.find(n => n.id === currentNodeId));
    }
    getExpectedInput(node) {
        console.log('getExpectedInput called');
        if (!node) return 'None';
        
        switch (node.type) {
            case 'fieldSetterNode':
                return `Field input for: ${node.data.fieldName}`;
            case 'dialogueNode':
                return 'Selection from available options';
            case 'responseNode':
                return 'Free form response';
            default:
                return 'None';
        }
    }

    async processNodeByType(node, message, sessionId, assistant, context, sessionData) {
        const handlers = {
            dialogueNode: this.handleDialogueNode.bind(this),
            scriptNode: this.handleScriptNode.bind(this),
            fieldSetterNode: this.handleFieldSetterNode.bind(this),
            callTransferNode: this.handleCallTransferNode.bind(this),
            responseNode: this.handleResponseNode.bind(this)
        };
    
        const handler = handlers[node.type];
        if (!handler) {
            throw new Error(`Unknown node type: ${node.type}`);
        }
    
        return await handler(node, message, sessionId, assistant, context);
    }
    
    // Helper method to update session state
    async updateSessionState(sessionId, updates) {
        return this.firestore.db
            .collection('chat_sessions')
            .doc(sessionId)
            .set(updates, { merge: true });
    }
    async buildParallelContext(message, sessionId, assistant) {
        const tasks = [
            this.getVectorContext(message, assistant.id),
            this.getPreviousMessages(sessionId),
            this.getAssistantInstructions(assistant)
        ];
    
        const [vectorResults, previousMessages, instructions] = await Promise.all(tasks);
    
        return {
            vectors: vectorResults,
            previousMessages,
            instructions
        };
    }
    
    // Helper method to get assistant instructions
    async getAssistantInstructions(assistant) {
        return Promise.resolve(assistant.instructions || []);
    }
    getAvailableFunctions(node) {
        console.log('getAvailableFunctions called');
        if (!node?.data?.functions) return 'None';
        return node.data.functions.map(f => f.content).join(', ');
    }

    async updateSessionState(sessionId, updates) {
        console.log('updateSessionState called');
        const sessionRef = this.firestore.db
            .collection('chat_sessions')
            .doc(sessionId);
            
        await sessionRef.set(updates, { merge: true });
    }

    async getCurrentOrStartingNode(sessionId, assistant) {
        console.log('getCurrentOrStartingNode called');
        const session = await this.firestore.db
            .collection('chat_sessions')
            .doc(sessionId)
            .get();
        
        const sessionData = session.data() || {};
        
        // If there's a current node, return it
        if (sessionData.currentNodeId) {
            return assistant.flowData.nodes.find(n => n.id === sessionData.currentNodeId);
        }
        
        // Otherwise return the starting node
        return assistant.flowData.nodes.find(n => n.data.nodeType === 'starting');
    }

    async getPreviousMessages(sessionId, limit = 10) {
        console.log('getPreviousMessages called');
        try {
            // Use the existing composite index
            console.log('SESSION ID', sessionId)
            const messagesRef = this.firestore.db
                .collection('shared_chat_messages')
                .where('sessionId', '==', sessionId)
                .orderBy('createdAt', 'asc') // Using existing ascending index
            
            const snapshot = await messagesRef.get();
            const messages = [];
            
            snapshot.forEach(doc => {
                const data = doc.data();
                messages.push({
                    role: data.role,
                    content: data.content
                });
            });
    
            // Since messages are in ascending order, slice from the end to get last 'limit' messages
            const lastMessages = messages.slice(Math.max(messages.length - limit, 0));
            
            console.log("GOT MESSAGES")
            console.log(lastMessages)
            return lastMessages;
        } catch (error) {
            console.log('Error in getPreviousMessages:', error);
            return []; // Return empty array if error
        }
    }

    // async processMessage(message, sessionId, assistant, context = {}) {
    //     console.log('processMessage called');
    //     try {
    //         const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    //     const session = await sessionRef.get();
    //     const sessionData = session.data() || {};

        
    //     // For first interaction, start with the node that has nodeType: 'starting'
    //     if (!sessionData.currentNodeId && !sessionData.started) {
    //         const startingNode = assistant.flowData.nodes.find(n => n.data.nodeType === 'starting');
    //         if (startingNode) {
    //             return await this.processNode(startingNode, message, sessionId, assistant, context);
    //         }
    //     }
    //         // 1. Classify the message with error handling
    //         let classification;
    //         try {
    //             classification = await this.classifyMessage(message, sessionId, assistant);
    //             console.log('CLASSIFICATION Type')
    //             console.log(classification)
    //         } catch (error) {
    //             // Removed console.error
    //             classification = {
    //                 type: 'node_flow',
    //                 returnToNode: false,
    //                 currentNodeId: null,
    //                 reasoning: 'Default due to classification error'
    //             };
    //         }
            
    //         if (classification.type === 'qa_flow') {
    //             // Handle QA flow with error handling
    //             try {
    //                 const qaResponse = await this.processQAFlow(message, sessionId, assistant, context);
                    
    //                 if (classification.returnToNode) {
    //                     // qaResponse.content += "\n\nNow, let's return to our previous conversation. ";
                        
    //                     const returnNode = assistant.flowData.nodes.find(n => 
    //                         n.id === classification.currentNodeId
    //                     );
    //                     if (returnNode) {
    //                         const nodeResponse = await this.processNode(
    //                             returnNode, 
    //                             message , // Use original message instead of null
    //                             sessionId, 
    //                             assistant, 
    //                             context
    //                         );
    //                         qaResponse.content += nodeResponse.content;
    //                         qaResponse.complete = false;
    //                     }
    //                 }
                    
    //                 return qaResponse;
    //             } catch (error) {
    //                 // Removed console.error
    //                 // Fallback to node flow if QA processing fails
    //                 classification.type = 'node_flow';
    //             }
    //         }
    
    //         // Process as normal node flow
    //         const currentNode = await this.getCurrentOrStartingNode(sessionId, assistant);
    //         return await this.processNode(currentNode, message, sessionId, assistant, context);
    //     } catch (error) {
    //         // Removed console.error
    //         return {
    //             content: "I apologize, but I'm having trouble processing your message. Could you please try again?",
    //             complete: false
    //         };
    //     }
    // }
    async processMessage(message, sessionId, assistant, context = {}) {
        console.log('processMessage called');
        try {
            // Parallel execution of session fetch and getting starting node
            const [sessionDoc, startingNode] = await Promise.all([
                this.firestore.db.collection('chat_sessions').doc(sessionId).get(),
                this.findStartingNode(assistant.flowData.nodes)
            ]);
    
            const sessionData = sessionDoc.data() || {};
    
            // First interaction check
            if (!sessionData.currentNodeId && !sessionData.started) {
                if (startingNode) {
                    return await this.processNode(startingNode, message, sessionId, assistant, context);
                }
            }
    
            // Parallel fetch of current node and enhanced context
            const [currentNode, enhancedContext] = await Promise.all([
                this.getCurrentNode(sessionData.currentNodeId, assistant.flowData.nodes),
                this.buildParallelContext(message, sessionId, assistant)
            ]);
    
            return await this.processNode(currentNode, message, sessionId, assistant, {
                ...context,
                ...enhancedContext
            });
        } catch (error) {
            console.error('Error in processMessage:', error);
            return {
                content: "I apologize, but I'm having trouble processing your message. Could you please try again?",
                complete: false
            };
        }
    }
    
    // async processMessage(message, sessionId, assistant, context = {}) {
    //     console.log('processMessage called');
    //     try {
    //         const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    //         const session = await sessionRef.get();
    //         const sessionData = session.data() || {};

    //         // For first interaction, start with the node that has nodeType: 'starting'
    //         if (!sessionData.currentNodeId && !sessionData.started) {
    //             const startingNode = assistant.flowData.nodes.find(n => n.data.nodeType === 'starting');
    //             if (startingNode) {
    //                 return await this.processNode(startingNode, message, sessionId, assistant, context);
    //             }
    //         }

    //         // Get current node and process directly
    //         const currentNode = await this.getCurrentOrStartingNode(sessionId, assistant);
    //         return await this.processNode(currentNode, message, sessionId, assistant, context);
    //     } catch (error) {
    //         return {
    //             content: "I apologize, but I'm having trouble processing your message. Could you please try again?",
    //             complete: false
    //         };
    //     }
    // }
  
    async classifyMessage(message, sessionId, assistant) {
        console.log('classifyMessage called');
        // 1. Get current session state and context
        const sessionRef = await this.firestore.db.collection('chat_sessions').doc(sessionId);
        const session = await sessionRef.get();
        const sessionData = session.data() || {};
        
        // 2. Get current node if exists
        let currentNode = null;
        let currentNodeContext = null;
        if (sessionData.currentNodeId) {
            currentNode = assistant.flowData.nodes.find(n => n.id === sessionData.currentNodeId);
            if (currentNode) {
                currentNodeContext = {
                    type: currentNode.type,
                    message: currentNode.data.message,
                    functions: currentNode.data.functions,
                    expectedInput: currentNode.data.fieldName // for field setter nodes
                };
            }
        }
        // 3. Get the last message sent by the node (the response the user is replying to)
        const previousMessages = await this.getPreviousMessages(sessionId, 2); // Get the last message
        const lastNodeResponse = previousMessages.find(msg => msg.role === 'assistant')?.content || 'None';
        console.log('CLASSIFY')
        console.log( message,
            currentNode?.type || 'None',
            currentNode?.data?.message || 'None',
            lastNodeResponse ,
            this.getExpectedInput(currentNode) ,
            this.getAvailableFunctions(currentNode)
        )
        // 4. Analyze with chain of thought
        const prompt = `
        <thinking>
        Analyze this user message in the context of the current conversation flow:
    
        User Message: "${message}"
        Current Node Type: ${currentNode?.type || 'None'}
        Current Node Message: ${currentNode?.data?.message || 'None'}
        Last Node Response: "${lastNodeResponse}" 
        Expected Input: ${this.getExpectedInput(currentNode)}
        Available Functions: ${this.getAvailableFunctions(currentNode)}

        Step-by-step analysis:
        1. Is this message directly related to the current node's context?
        2. Is this a valid response to what we're asking?
        3. Is this a tangential question that needs to be answered before continuing?
        4. Should we handle this as out-of-flow QA and then return to the flow?
        5. Does the user's message ${message} match or align or indirect answer with the current node's  ${currentNode?.data?.message || 'None'} or the ${lastNodeResponse} response sent by the node?
        </thinking>
    
        <reflection>
        Based on the analysis:
        - Direct Response: Would this message satisfy the current node's requirements?
        - QA Need: Does this require additional information before proceeding?
        - Message Match: Does the user's message match or align with the current node's message or the last response sent by the node?
        - Classify as "node_flow" if the message is:
            * A direct answer to the question
            * A request for clarification about the current topic
            * An indirect response that's still topically relevant
        - Only classify as "qa_flow" if ALL of these are true:
            - Message is completely unrelated to current node's question
            - Message is a pure information-seeking question
            - Message doesn't relate to any Available Functions
            - Message doesn't match Expected Input format
            - Message doesn't try to answer the current node's question at all
            - Message is clearly off-topic from current conversation
        - Flow State: Should we maintain the current node state while handling this?
        </reflection>
    
        <reward>
        Score confidence of classification (0.0-1.0)
        </reward>
    
        Return ONLY a JSON object in this exact format without any additional text:
        {
            "type": "node_flow" or "qa_flow",
            "returnToNode": true or false,
            "currentNodeId": "${currentNode?.id || null}",  // Pass the actual current node ID
            "reasoning": "explanation of decision"
        }
        `;
    
        // Use generateFlowProcessor instead of analyzeIntent
        const response = await this.gemini.generateFlowProcessor(prompt, [], {
            maxTokens: 200,
            temperature: 0.3
        });
    
        try {
            // Clean up the response content to remove any markdown formatting
            let cleanedContent = response.content.trim();
            if (cleanedContent.startsWith('```json')) {
                cleanedContent = cleanedContent.replace('```json', '').replace('```', '');
            }
            
            // Parse the cleaned JSON
            const classification = JSON.parse(cleanedContent);
            
            // Validate the classification object
            if (!classification.type || !('returnToNode' in classification)) {
                // Removed console.log
                return {
                    type: 'node_flow',
                    returnToNode: false,
                    currentNodeId: currentNode?.id,
                    reasoning: 'Default classification due to invalid response'
                };
            }
    
            if (classification.type === 'qa_flow' && classification.returnToNode) {
                classification.currentNodeId = currentNode?.id || null;  // Set actual node ID
            }
            // Save state if needed
            if (classification.type === 'qa_flow' && classification.returnToNode) {
                await sessionRef.set({
                    returnToNodeId: currentNode.id,  // Use actual node ID here too
                    qaInProgress: true
                }, { merge: true });
            }
    
            return classification;
        } catch (error) {
            // Removed console.error
            // Default fallback
            return {
                type: 'node_flow',
                returnToNode: false,
                currentNodeId: currentNode?.id,
                reasoning: 'Fallback classification due to parsing error'
            };
        }
    }

    async processQAFlow(message, sessionId, assistant, context) {
        console.log('processQAFlow called');
        // 1. Fetch context from multiple sources in parallel
        const [vectorResults, previousMessages] = await Promise.all([
            this.getVectorContext(message, assistant.id),
            this.getPreviousMessages(sessionId)
        ]);

        // 2. Build enhanced context
        const enhancedContext = await this.buildEnhancedContext({
            vectors: vectorResults,
            previousMessages,
            assistant
        });

        // 3. Generate response using geminiSharedResponse
        const response = await this.gemini.generateSharedResponse(message, enhancedContext, {
            maxTokens: 1000,
            category: assistant.category,
            language: 'en',
            tone: 'professional',
            responseStyle: 'detailed',
            complexityLevel: 'intermediate',
            interactionStyle: 'collaborative'
        });
        console.log('SHARED RESPONSE FROM QA')
        console.log(response)
        // 4. Update session state
        await this.updateSessionState(sessionId, {
            lastMessage: message,
            lastResponse: response.content,
            isQAFlow: true
        });

        return {
            content: response.content,
            complete: false
        };
    }

    async buildEnhancedContext({ vectors, previousMessages, assistant }) {
        console.log('buildEnhancedContext called');
        const context = [];

        // Add assistant instructions
        if (assistant.instructions) {
            context.push({
                role: 'system',
                content: `Instructions: ${assistant.instructions}`
            });
        }

        // Add vector search results
        vectors.forEach(vec => {
            if (vec.metadata?.content) {
                context.push({
                    role: 'system',
                    content: `Content from ${vec.metadata.name}: ${vec.metadata.content}`
                });
            }
        });

        // Add previous messages
        previousMessages.forEach(msg => {
            context.push(msg);
        });

        return context;
    }
    async processNode(node, message, sessionId, assistant, context = {}) {
        console.log('processNode called');
        console.log(node)
        if (!node?.data) {
            return { content: 'Error processing node', complete: false };
        }
    
        try {
            // Parallel execution of initial tasks
            const [
                sessionDoc,
                relevantVectors,
                previousMessages
            ] = await Promise.all([
                this.firestore.db.collection('chat_sessions').doc(sessionId).get(),
                this.getVectorContext(message || node.data.message, assistant.id),
                this.getPreviousMessages(sessionId)
            ]);
    
            const sessionData = sessionDoc.data() || {};
    
            // Non-blocking smart tagger execution
            if (message) {
                this.smartTagger.processNodeData(node, message, sessionId, assistant)
                    .catch(error => console.error('Error in smart trigger processing:', error));
            }
    
            // Build enhanced context in parallel with other operations
            const enhancedContext = await this.buildEnhancedContext({
                vectors: relevantVectors,
                previousMessages,
                assistant
            });
    
            // Process node based on type with optimized handlers
            const result = await this.processNodeByType(
                node,
                message,
                sessionId,
                assistant,
                enhancedContext,
                sessionData
            );
    
            // Handle completion and next node logic
            if (result.complete && !result.nextNode) {
                const leadingNode = assistant.flowData.nodes.find(n => n.data.nodeType === 'leading');
                if (leadingNode) {
                    // Parallel update of session state and processing of leading node
                    const [leadingNodeResponse] = await Promise.all([
                        this.processNode(leadingNode, null, sessionId, assistant, context),
                        this.updateSessionState(sessionId, {
                            currentNodeId: leadingNode.id,
                            started: true,
                            awaitingResponse: true
                        })
                    ]);
    
                    return {
                        content: `${result.content}\n\n${leadingNodeResponse.content}`,
                        complete: false,
                        nextNode: leadingNode.id
                    };
                }
            }
    
            return result;
        } catch (error) {
            console.error('Error in processNode:', error);
            return { content: 'Error processing node', complete: false };
        }
    }
    

    // async processNode(node, message, sessionId, assistant, context = {}) {
    //     console.log('processNode called');
    //     console.log('Processing Node:', node.id);
    //     console.log('Node Type:', node.type);
    //     console.log('Message:', message);
    //     console.log('Node Data:', node.data);
      
    //     // if (message) {
    //     //     await this.smartTagger.processNodeData(node, message, sessionId);
    //     // }
    //     // Execute smartTagger in a non-blocking way
    //     if (message) {
    //         this.smartTagger.processNodeData(node, message, sessionId)
    //         .catch(error => {
    //             console.error('Error in smart trigger processing:', error);
    //         });
    //     }
    //     const nodeData = node.data;
    //     if (!nodeData) {
    //         // Removed console.error
    //         return { content: 'Error processing node', complete: false };
    //     }
      
    //     // Ensure message is never null for Response Node
    //     let processedMessage = message;
    //     // Generate embeddings using the processed message
    //     const relevantVectors = await this.getVectorContext(
    //         processedMessage || nodeData.message,
    //         assistant.id
    //     );

    //     const fullContext = await this.buildEnhancedContext({
    //         vectors: relevantVectors,
    //         previousMessages: context.previousMessages || [],
    //         assistant
    //     });

    //     let result;
    //     switch (node.type) {
    //         case 'dialogueNode':
    //             result = await this.handleDialogueNode({ ...node, message: nodeData.message, functions: nodeData.functions }, processedMessage, sessionId, assistant, fullContext);
    //             break;
    //         case 'scriptNode':
    //             result = await this.handleScriptNode({ ...node, message: nodeData.message }, processedMessage, sessionId, assistant, fullContext);
    //             break;
    //         case 'fieldSetterNode':
    //             result = await this.handleFieldSetterNode({ ...node, message: nodeData.message, fieldName: nodeData.fieldName }, processedMessage, sessionId, assistant, fullContext);
    //             break;
    //         case 'callTransferNode':
    //             result = await this.handleCallTransferNode({ ...node, message: nodeData.message, fieldName: nodeData.fieldName }, processedMessage, sessionId, assistant, fullContext);
    //             break;
    //         case 'responseNode':
    //             result = await this.handleResponseNode({ ...node, message: nodeData.message }, processedMessage, sessionId, assistant, fullContext);
    //             break;
    //         default:
    //             throw new Error(`Unknown node type: ${node.type}`);
    //     }

    //     // Removed existing console logs

    //     // If no next node is found, return to the leading node
    //     if (result.complete && !result.nextNode) {
    //         const leadingNode = assistant.flowData.nodes.find(n => n.data.nodeType === 'leading');
    //         if (leadingNode) {
    //             // Update session state to indicate we're waiting for user input
    //             const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    //             await sessionRef.set({
    //                 currentNodeId: leadingNode.id,
    //                 started: true,
    //                 awaitingResponse: true, // Wait for user input
    //             }, { merge: true });
        
    //             // Process the leading node's message explicitly
    //             const leadingNodeResponse = await this.processNode(leadingNode, null, sessionId, assistant, context);
        
    //             // Return the combined response
    //             return {
    //                 content: `${result.content}\n\n${leadingNodeResponse.content}`,
    //                 complete: false,
    //                 nextNode: leadingNode.id,
    //             };
    //         }
    //     }
      
    //     return result;
    // }

   

    async handleScriptNode(node, message, sessionId, assistant, context) {
        console.log('handleScriptNode called');
        const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
        const session = await sessionRef.get();
        const sessionData = session.data() || {};
        const response = await this.processWorkflowInstruction(node.data.message, context, message);

        console.log('RESPONSE FROM PROCESS WORKFLOW')
        console.log(response)
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
                    content: response.content,
                    complete: true, // Mark as complete
                    nextNode: null, // No next node
                };
            }
    
            // Check if there is a "Next Steps" function
            const nextStepsFunction = node.data.functions.find(f => f.type === 'nextSteps');
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
                    const nextNodeResponse = await this.processNode(nextNode, message, sessionId, assistant, context);
    
                    // Combine responses from both nodes
                    const combinedResponse = `${response}\n\n${nextNodeResponse.content}`;
                    console.log('COMBINED RESPONSE')
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
                content: response.content,
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
                    content: response.content,
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
                return await this.processNode(nextNode, message, sessionId, assistant, context);
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
            content: response.content,
            complete: false,
        };
    }

    // async handleFieldSetterNode(node, message, sessionId, assistant, context) {
    //     console.log('handleFieldSetterNode called');
    //     const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    //     const session = await sessionRef.get();
    //     const sessionData = session.data() || {};
    
    //     const isLeadingNode = node.data.nodeType === 'leading';
    
    //     if (!sessionData.started) {
    //         const prompt = `
    //     You are assisting a user in ordering or booking something or filling the details. Based on the user's previous message and the current node's instructions, generate a response to collect the required information.

    //     User's previous message: "${message}"
    //     Node instruction: "${node.data.message}"
    //     Field to collect: "${node.data.fieldName}"

    //     Guidelines for your response:
    //     1. Ask the user to provide the ${node.data.fieldName}.
    //     2. Be concise and professional.
    //     3. Reference the user's previous message if relevant.
    //     4. Do not ask for additional information unless explicitly required by the node.

    //     Generate ONLY the response to collect the ${node.data.fieldName}.


    //     `;
    //         const response = await this.gemini.generateFlowProcessor(prompt, context, {
    //                         maxTokens: 1000,
    //                         temperature: 0.7,
    //                     });
                
    //         const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
    //         // Save state that we're waiting for user response
    //         await sessionRef.set({
    //             currentNodeId: node.id,
    //             started: true,
    //             awaitingResponse: hasOutgoingEdges, // Wait for user input
    //             fieldToSet: node.data.fieldName,
    //         }, { merge: true });
    
    //         return { 
    //             content: response.content,  
    //             complete: !hasOutgoingEdges, // Mark as complete if there are no outgoing edges
    //             nextNode: null, 
    //         };
    //     }
    
    //     if (sessionData.awaitingResponse && message) {
    //         const validationResult = await this.validateFieldValue(
    //             sessionData.fieldToSet,
    //             message,
    //             context
    //         );
    
    //         await sessionRef.set({
    //             [`fields.${sessionData.fieldToSet}`]: validationResult,
    //         }, { merge: true });
    
    //         const flow = assistant.flowData;
    //         const edge = flow.edges.find(e => e.source === node.id && e.sourceHandle === `${node.id}-right`);
    
    //         if (edge) {
    //             const nextNode = flow.nodes.find(n => n.id === edge.target);
    
    //             // Update session state
    //             await sessionRef.set({
    //                 currentNodeId: nextNode.id,
    //                 started: false,
    //                 awaitingResponse: true, // Wait for user input
    //             }, { merge: true });
    
    //             // Process the next node
    //             return await this.processNode(nextNode, message, sessionId, assistant, context);
    //         }
    //     }
    //     const response = await this.processWorkflowInstruction(node.data.message, context, message);

    //     return {
    //         content: response,
    //         complete: false,
    //     };
    // }
    async handleDialogueNode(node, message, sessionId, assistant, context) {
        console.log('handleDialogueNode called');
        const sessionRef = await this.firestore.db.collection('chat_sessions').doc(sessionId);
        const session = await sessionRef.get();
        const sessionData = session.data() || {};
    
        if (!sessionData.started) {
            // First time hitting this node - generate initial response using node's message
            const response = await this.processWorkflowInstruction(node.data.message, context, message);
            const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
            await sessionRef.set({
                currentNodeId: node.id,
                started: true,
                awaitingResponse: hasOutgoingEdges,
                functions: node.data.functions,
            }, { merge: true });
        
            return {
                content: response,
                complete: !hasOutgoingEdges,
                nextNode: null,
            };
        }
      
        if (sessionData.awaitingResponse && message) {
            // Match user's response against functions
            const matchedFunction = await this.matchUserResponseToFunction(
                message,
                node.data.functions,
                context,
                sessionId
            );
            console.log('matched function')
            console.log(matchedFunction)
            
            if (!matchedFunction) {
                // If no matching function found, use shared response like response node
                const response = await this.gemini.generateSharedResponse(message, context, {
                    maxTokens: 1000,
                    category: assistant.category,
                    language: 'en',
                    tone: 'professional',
                    responseStyle: 'detailed',
                    complexityLevel: 'intermediate',
                    interactionStyle: 'collaborative',
                });
    
                // Stay in current node
                await sessionRef.set({
                    currentNodeId: node.id,
                    started: true,
                    awaitingResponse: true,
                }, { merge: true });
    
                return {
                    content: response.content,
                    complete: false,
                    nextNode: null,
                };
            }
        
            // Find corresponding function ID
            const functionObj = node.data.functions.find(f => 
                f.content.toLowerCase().trim() === matchedFunction.toLowerCase().trim()
            );
        
            // If function matched, proceed with normal flow
            const flow = assistant.flowData;
            const sourceHandle = `function-${node.id}-${functionObj.id}`;
            const edge = flow.edges.find(e => 
                e.source === node.id && 
                e.sourceHandle === sourceHandle
            );
        
            if (edge) {
                const nextNode = flow.nodes.find(n => n.id === edge.target);
        
                await sessionRef.set({
                    currentNodeId: nextNode.id,
                    started: false,
                    awaitingResponse: true,
                }, { merge: true });
        
                return await this.processNode(nextNode, message, sessionId, assistant, context);
            }
        }
    
        const response = await this.processWorkflowInstruction(node.data.message, context, message);
    
        return {
            content: response,
            complete: false,
        };
    }
    async handleFieldSetterNode(node, message, sessionId, assistant, context) {
        console.log('handleFieldSetterNode called');
        const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
        const session = await sessionRef.get();
        const sessionData = session.data() || {};
    
        if (!sessionData.started) {
            // First time hitting this node - generate initial field collection prompt
            const response = await this.processWorkflowInstruction(node.data.message, context, message);
            const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
            await sessionRef.set({
                currentNodeId: node.id,
                started: true,
                awaitingResponse: hasOutgoingEdges,
                fieldToSet: node.data.fieldName,
            }, { merge: true });
    
            return { 
                content: response,
                complete: !hasOutgoingEdges,
                nextNode: null,
            };
        }
    
        if (sessionData.awaitingResponse && message) {
            // Try to validate the field value first
            const validationResponse = await this.matchFieldInput(
                message,
                sessionData.fieldToSet,
                node.data.message,
                context,
                sessionId
            );
    
            if (!validationResponse.value) {
                // If no valid field value found, handle as QA or invalid input
                // const response = await this.gemini.generateSharedResponse(message, context, {
                //     maxTokens: 1000,
                //     category: assistant.category,
                //     language: 'en',
                //     tone: 'professional',
                //     responseStyle: 'detailed',
                //     complexityLevel: 'intermediate',
                //     interactionStyle: 'collaborative',
                // });
    
                // Combine QA response with original field request
                const nodeResponse = await this.processWorkflowInstruction(node.data.message, context, message);
    
                // Stay in current node
                await sessionRef.set({
                    currentNodeId: node.id,
                    started: true,
                    awaitingResponse: true,
                }, { merge: true });
    
                return {
                    content: `${nodeResponse}`,
                    complete: false,
                    nextNode: null,
                };
            }
    
            // Valid field value provided - save and proceed
            await sessionRef.set({
                [`fields.${sessionData.fieldToSet}`]: validationResponse.value,
            }, { merge: true });
    
            const flow = assistant.flowData;
            const edge = flow.edges.find(e => e.source === node.id && e.sourceHandle === `${node.id}-right`);
    
            if (edge) {
                const nextNode = flow.nodes.find(n => n.id === edge.target);
    
                await sessionRef.set({
                    currentNodeId: nextNode.id,
                    started: false,
                    awaitingResponse: true,
                }, { merge: true });
    
                return await this.processNode(nextNode, message, sessionId, assistant, context);
            }
        }
    
        const response = await this.processWorkflowInstruction(node.data.message, context, message);
    
        return {
            content: response,
            complete: false,
        };
    }
    
    async matchFieldInput(message, fieldName, nodeMessage, context, sessionId) {
        console.log('matchFieldInput called');
        
        const previousMessages = await this.getPreviousMessages(sessionId, 2);
        const lastAIResponse = previousMessages.find(msg => msg.role === 'assistant')?.content || 'None';
    
        const prompt = `
        <thinking>
        We have the following context:
        Last AI Response: "${lastAIResponse}"
        User's Message: "${message}"
        Field to Collect: "${fieldName}"
        Node Message: "${nodeMessage}"
    
        Step-by-step:
        1. Is the user providing a value for the ${fieldName} field?
        2. Can we extract a valid value for this field type?
        3. Is the format appropriate for this field type?
    
        Rules for field types:
        - "date": YYYY-MM-DD format
        - "time": HH:MM format
        - "email": valid email format
        - "phone": standardized phone format
        - Other fields: Extract relevant text
    
        Return exactly one line with either:
        - The extracted and formatted value if valid
        - "no_match" if no valid value found
        </thinking>
        `;
    
        const response = await this.gemini.generateFlowProcessor(prompt, context, {
            maxTokens: 200,
            temperature: 0.3
        });
    
        const matchedValue = response.content.trim();
        return {
            value: matchedValue === "no_match" ? null : matchedValue
        };
    }
    async handleCallTransferNode(node, message, sessionId, assistant, context) {
        console.log('handleCallTransferNode called');
        const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
        const session = await sessionRef.get();
        const sessionData = session.data() || {};
    
        const isLeadingNode = node.data.nodeType === 'leading';
    
        if (!sessionData.started) {
            const response = await this.processWorkflowInstruction(node.data.message, context, message);

            const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
            // Save state that we're waiting for user response
            await sessionRef.set({
                currentNodeId: node.id,
                started: true,
                awaitingResponse: hasOutgoingEdges, // Wait for user input
            }, { merge: true });
    
            return { 
                content: response, 
                complete: !hasOutgoingEdges, // Mark as complete if there are no outgoing edges
                nextNode: null,  
            };
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

    // async handleResponseNode(node, message, sessionId, assistant, context) {
    //     console.log('handleResponseNode called');
    //     const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    //     const session = await sessionRef.get();
    //     const sessionData = session.data() || {};
    
    //     // If the session hasn't started, generate the initial response
    //     if (!sessionData.started) {
    //         const response = await this.gemini.generateFlowProcessor(node.data.message, context, {
    //             maxTokens: 1000,
    //             temperature: 0.7,
    //         });
    
    //         // Check if there are any outgoing edges
    //         const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
    //         if (!hasOutgoingEdges) {
    //             // If no outgoing edges, mark as complete
    //             await sessionRef.set({
    //                 currentNodeId: node.id,
    //                 started: true,
    //                 awaitingResponse: true, // No need to wait for user input
    //             }, { merge: true });
    
    //             return {
    //                 content: response.content,
    //                 complete: true, // Mark as complete
    //                 nextNode: null, // No next node
    //             };
    //         }
    
    //         // If there are outgoing edges, wait for user response
    //         await sessionRef.set({
    //             currentNodeId: node.id,
    //             started: true,
    //             awaitingResponse: true, // Wait for user input
    //         }, { merge: true });
    
    //         return {
    //             content: response.content,
    //             complete: false, // Wait for user input
    //             nextNode: null,
    //         };
    //     }
    
    //     // If the session is awaiting a user response and a message is provided
    //     if (sessionData.awaitingResponse && message) {
    //         // Generate a response using the user's message
    //         const response = await this.gemini.generateSharedResponse(message, context, {
    //             maxTokens: 1000,
    //             category: assistant.category,
    //             language: 'en', // Default language
    //             tone: 'professional', // Default tone
    //             responseStyle: 'detailed', // Default response style
    //             complexityLevel: 'intermediate', // Default complexity level
    //             interactionStyle: 'collaborative', // Default interaction style
    //         });
    //         console.log('SHARED RESPONSE FROM DB')
    //         console.log(response)
    //         // Check if there are any outgoing edges
    //         const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
    //         if (!hasOutgoingEdges) {
    //             // If no outgoing edges, mark as complete
    //             await sessionRef.set({
    //                 currentNodeId: node.id,
    //                 started: true,
    //                 awaitingResponse: true, // No need to wait for user input
    //             }, { merge: true });
    
    //             return {
    //                 content: response.content,
    //                 complete: true, // Mark as complete
    //                 nextNode: null, // No next node
    //             };
    //         }
    
    //         // If there are outgoing edges, proceed to the next node
    //         const flow = assistant.flowData;
    //         const edge = flow.edges.find(e => e.source === node.id);
    //         const nextNode = edge ? flow.nodes.find(n => n.id === edge.target) : null;

    //         if (edge) {
    //             const nextNode = flow.nodes.find(n => n.id === edge.target);
    
    //             // Update session state to move to the next node
    //             await sessionRef.set({
    //                 currentNodeId: nextNode.id,
    //                 started: false,
    //                 awaitingResponse: true, // Wait for user input at the next node
    //             }, { merge: true });
    
    //             // Process the next node
    //             const nextNodeResponse = await this.processNode(nextNode, message, sessionId, assistant, context);
    
    //             // Return the combined response
    //             return {
    //                 content: `${response.content}\n\n${nextNodeResponse.content}`,
    //                 complete: false, // Mark as incomplete to continue the flow
    //                 nextNode: nextNode.id, // Move to the next node
    //             };
    //         }
    //     }
    
    //     // Default fallback response
    //     return {
    //         content: "This is the end of the flow.",
    //         complete: true, // Mark as complete
    //         nextNode: null, // No next node
    //     };
    // }
    // async handleResponseNode(node, message, sessionId, assistant, context) {
    //     console.log('handleResponseNode called');
    //     const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
    //     const session = await sessionRef.get();
    //     const sessionData = session.data() || {};
    
    //     // If the session hasn't started, generate the initial response
    //     if (!sessionData.started) {
    //         const response = await this.gemini.generateFlowProcessor(node.data.message, context, {
    //             maxTokens: 1000,
    //             temperature: 0.7,
    //         });
    
    //         await sessionRef.set({
    //             currentNodeId: node.id,
    //             started: true,
    //             awaitingResponse: true,
    //             responseStep: 'initial',
    //             triggers: node.data.triggers || []
    //         }, { merge: true });
    
    //         return {
    //             content: response.content,
    //             complete: false,
    //             nextNode: null,
    //         };
    //     }
    
    //     // If waiting for first response, get shared response
    //     if (sessionData.responseStep === 'initial' && message) {
    //         const response = await this.gemini.generateSharedResponse(message, context, {
    //             maxTokens: 1000,
    //             category: assistant.category,
    //             language: 'en',
    //             tone: 'professional',
    //             responseStyle: 'detailed',
    //             complexityLevel: 'intermediate',
    //             interactionStyle: 'collaborative',
    //         });
    //         console.log('SHARED RESPONSE FROM RESPONSE NODE', response)
    //         // Update state to wait for trigger matching
    //         await sessionRef.set({
    //             responseStep: 'awaiting_trigger'
    //         }, { merge: true });
    
    //         return {
    //             content: response.content,
    //             complete: false,
    //             nextNode: null,
    //         };
    //     }
    
    //     // If we got shared response and waiting for trigger match
    //     if (sessionData.responseStep === 'awaiting_trigger' && message) {
    //         // Match user's response against triggers
    //         const matchedTrigger = await this.matchUserResponseToFunction(
    //             message,
    //             node.data.triggers,
    //             context
    //         );
    
    //         // Find corresponding trigger
    //         const triggerObj = node.data.triggers.find(t => 
    //             t.content.toLowerCase().trim() === matchedTrigger.toLowerCase().trim()
    //         );
    
    //         if (triggerObj) {
    //             const flow = assistant.flowData;
    //             const sourceHandle = `trigger-${node.id}-${triggerObj.id}`;
    //             const edge = flow.edges.find(e => 
    //                 e.source === node.id && 
    //                 e.sourceHandle === sourceHandle
    //             );
    
    //             if (edge) {
    //                 const nextNode = flow.nodes.find(n => n.id === edge.target);
    
    //                 // Update session state
    //                 await sessionRef.set({
    //                     currentNodeId: nextNode.id,
    //                     started: false,
    //                     awaitingResponse: true,
    //                     responseStep: 'initial'
    //                 }, { merge: true });
    
    //                 // Process next node
    //                 return await this.processNode(nextNode, message, sessionId, assistant, context);
    //             }
    //         }
    
    //         return {
    //             content: "I couldn't quite understand that. Could you please try again with one of the available options?",
    //             complete: false,
    //             nextNode: null,
    //         };
    //     }
    
    //     return {
    //         content: "I'm waiting for your response.",
    //         complete: false,
    //         nextNode: null,
    //     };
    // }
    async handleResponseNode(node, message, sessionId, assistant, context) {
        console.log('handleResponseNode called');
        const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
        const session = await sessionRef.get();
        const sessionData = session.data() || {};
    
        // If the session hasn't started, generate the initial response
        if (!sessionData.started) {
            const response = await this.gemini.generateFlowProcessor(node.data.message, context, {
                maxTokens: 1000,
                temperature: 0.7,
            });
    
            await sessionRef.set({
                currentNodeId: node.id,
                started: true,
                awaitingResponse: true,
                responseStep: 'initial',
                triggers: node.data.triggers || []
            }, { merge: true });
    
            return {
                content: response.content,
                complete: false,
                nextNode: null,
            };
        }
    
        // If waiting for first response, get shared response
        if (sessionData.responseStep === 'initial' && message) {
            const response = await this.gemini.generateSharedResponse(message, context, {
                maxTokens: 1000,
                category: assistant.category,
                language: 'en',
                tone: 'professional',
                responseStyle: 'detailed',
                complexityLevel: 'intermediate',
                interactionStyle: 'collaborative',
            });
            console.log('SHARED RESPONSE FROM RESPONSE NODE', response);
    
            // Update state to wait for trigger matching
            await sessionRef.set({
                responseStep: 'awaiting_trigger'
            }, { merge: true });
    
            return {
                content: response.content,
                complete: false,
                nextNode: null,
            };
        }
    
        // If we got shared response and waiting for trigger match
        if (sessionData.responseStep === 'awaiting_trigger' && message) {
            // Match user's response against triggers
            const matchedTrigger = await this.matchUserResponseToTrigger(
                message,
                node.data.triggers,
                context, 
                sessionId
            );
    
            if (!matchedTrigger) {
                // If no trigger matches, call getSharedResponse again with the user's message
                const response = await this.gemini.generateSharedResponse(message, context, {
                    maxTokens: 1000,
                    category: assistant.category,
                    language: 'en',
                    tone: 'professional',
                    responseStyle: 'detailed',
                    complexityLevel: 'intermediate',
                    interactionStyle: 'collaborative',
                });
    
                // Stay in the same state and wait for another user response
                return {
                    content: response.content,
                    complete: false,
                    nextNode: null,
                };
            }
    
            // Find corresponding trigger
            const triggerObj = node.data.triggers.find(t => 
                t.content.toLowerCase().trim() === matchedTrigger.toLowerCase().trim()
            );
    
            if (triggerObj) {
                const flow = assistant.flowData;
                const sourceHandle = `trigger-${node.id}-${triggerObj.id}`;
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
                        responseStep: 'initial'
                    }, { merge: true });
                    
                    
                    // Process next node
                    return await this.processNode(nextNode, message, sessionId, assistant, context);
                }
            }
    
            // If no edge is found, call getSharedResponse again
            const response = await this.gemini.generateSharedResponse(message, context, {
                maxTokens: 1000,
                category: assistant.category,
                language: 'en',
                tone: 'professional',
                responseStyle: 'detailed',
                complexityLevel: 'intermediate',
                interactionStyle: 'collaborative',
            });
    
            return {
                content: response.content,
                complete: false,
                nextNode: null,
            };
        }
    
        // Default fallback response
        return {
            content: "I'm waiting for your response.",
            complete: false,
            nextNode: null,
        };
    }
    async matchUserResponseToTrigger(userMessage, triggers, context, sessionId) {
        console.log('matchUserResponseToTrigger called');
        

        const previousMessages = await this.getPreviousMessages(sessionId, 2);
        const lastAIResponse = previousMessages.find(msg => msg.role === 'assistant')?.content || 'None';
        console.log('PREVIOUS MESSAGES', previousMessages)
        console.log('LAST AI', lastAIResponse)
        const prompt = `
        <thinking>
        We have the following conversation context:
        Last AI Response: "${lastAIResponse}"
        User's Message: "${userMessage}"
        
        We also have these possible triggers:
        ${triggers.map(t => `- "${t.content}"`).join('\n')}
        
        We want to check if the user's message semantically corresponds to any of these trigger texts.
        
        Step-by-step:
        1. Interpret the user message: what is the user intending or expressing?
        2. Compare that intent with each trigger.
        3. If one trigger best matches the user's intent, return that trigger text exactly.
        4. If none apply, return "no_match".
        5. Output must be exactly one line with either the trigger text or "no_match".
        </thinking>
        `;
    
        const response = await this.gemini.generateFlowProcessor(prompt, context, {
            maxTokens: 200,
            temperature: 0.3, // Lower temperature for more precise matching
        });
    
        const matchedTrigger = response.content.trim();
        console.log(matchedTrigger)
        return matchedTrigger === "no_match" ? null : matchedTrigger;
    }
    async matchUserResponseToFunction(userMessage, functions, context, sessionId) {
        console.log('matchUserResponseToFunction called');
        
        const previousMessages = await this.getPreviousMessages(sessionId, 2);
        const lastAIResponse = previousMessages.find(msg => msg.role === 'assistant')?.content || 'None';
        console.log('PREVIOUS MESSAGES', previousMessages);
        console.log('LAST AI', lastAIResponse);
    
        const prompt = `
        <thinking>
        We have the following conversation context:
        Last AI Response: "${lastAIResponse}"
        User's Message: "${userMessage}"
        
        We also have these possible functions:
        ${functions.map(f => `- "${f.content}"`).join('\n')}
        
        We want to check if the user's message semantically corresponds to any of these function options.
        
        Step-by-step:
        1. What is the user's primary intent in their message?
        2. Does this intent EXACTLY match any of our available functions?
        3. Be very strict - only match if the user is clearly choosing one of these options
        4. If asking a question or making a request that doesn't match any function, return "no_match"
        5. If the message is ambiguous or could mean multiple things, return "no_match"
        
        Guidelines:
        - Return "no_match" if the user is:
          * Asking a question
          * Making a request not in the functions
          * Providing information not related to functions
          * Being ambiguous
        - Only match a function if the user is clearly selecting that option
        
        Return exactly one line with either the matching function text or "no_match"
        </thinking>
        `;
    
        const response = await this.gemini.generateFlowProcessor(prompt, context, {
            maxTokens: 200,
            temperature: 0.3
        });
    
        const matchedFunction = response.content.trim();
        return matchedFunction === "no_match" ? null : matchedFunction;
    }

    async processWorkflowInstruction(instruction, context, userMessage = null) {
        console.log('processWorkflowInstruction called');
        const prompt = `
            Process this workflow instruction and generate an appropriate response:
            "${instruction}"
    
            ${userMessage ? `User's message: "${userMessage}"` : ''}
    
            Context:
            ${context.map(c => `${c.role}: ${c.content}`).join('\n')}
    
            Guidelines for your response:
            1. Do not start with greetings like "Hi there," "Hello," or "Hey." until specifically asked in the instruction or in context.
            2. Be concise and to the point.
            3. Maintain a professional yet conversational tone.
            4. If there's a user message, reference it in your response appropriately.
            5. Use conversational phrases like "Hmm," "Ah, I see," or "Let me think about that" to make the interaction more human-like.
        `;
        
        const response = await this.gemini.generateProcessFlowProcessor(prompt, context, {
            maxTokens: 500,
            temperature: 0.7,
        });
        return response.content;
    }

    // async validateFieldValue(fieldName, value, context) {
    //     console.log('validateFieldValue called');
    //     const prompt = `
    //     Extract the required information from the user's message based on the field name:
    //     Field: ${fieldName}
    //     Value: "${value}"
      
    //     Context:
    //     ${context.map(c => `${c.role}: ${c.content}`).join('\n')}
      
    //     Based on the field name, extract the following:
    //     - For "date": Extract a date.
    //     - For "time": Extract a time.
    //     - For "email": Extract an email address.
    //     - For "phone": Extract a phone number.
    //     - For other fields: Extract the relevant information.
      
    //     Return only the extracted value as a plain text response.
    //     `;
    //     const response = await this.gemini.generateFlowProcessor(prompt, context, {
    //         maxTokens: 300,
    //         temperature: 0.5,
    //     });
      
    //     // Return the extracted value directly
    //     return response.content.trim();
    // }
    async validateFieldValue(fieldName, message, context, sessionId) {
        console.log('validateFieldValue called');
        
        // Get previous messages for context
        const previousMessages = await this.getPreviousMessages(sessionId, 2);
        const lastNodeResponse = previousMessages.find(msg => msg.role === 'assistant')?.content || 'None';
    
        const prompt = `
        <thinking>
        Analyze this user message in the context of field collection:
    
        User Message: "${message}"
        Field to Collect: "${fieldName}"
        Last Node Response: "${lastNodeResponse}"
        Current Date: ${new Date().toISOString().split('T')[0]}
    
        Step-by-step analysis:
        1. Is the user's message attempting to provide the requested ${fieldName}?
        2. Does the message contain extractable information for ${fieldName}?
        3. Is this a tangential question unrelated to providing the ${fieldName}?
        4. Should we handle this as a QA response instead of field collection?
    
        First, determine if this is a field response or needs QA handling.
        Then, if it's a field response, extract the appropriate value.
        </thinking>
    
        Return ONLY a JSON object in this exact format:
        {
            "type": "field_collection" or "qa_flow",
            "value": "extracted value if field_collection, null if qa_flow",
            "confidence": 0.0-1.0,
            "reasoning": "brief explanation of decision"
        }
        `;
    
        const response = await this.gemini.generateFlowProcessor(prompt, context, {
            maxTokens: 200,
            temperature: 0.3
        });
    
        try {
            // Clean up the response content
            let cleanedContent = response.content.trim();
            if (cleanedContent.startsWith('```json')) {
                cleanedContent = cleanedContent.replace('```json', '').replace('```', '');
            }
            
            const analysis = JSON.parse(cleanedContent);
    
            if (analysis.type === 'qa_flow') {
                // Handle as QA flow
                const qaResponse = await this.gemini.generateSharedResponse(message, context, {
                    maxTokens: 1000,
                    category: 'general',
                    language: 'en',
                    tone: 'professional',
                    responseStyle: 'detailed',
                    complexityLevel: 'intermediate',
                    interactionStyle: 'collaborative'
                });
    
                return {
                    type: 'qa_flow',
                    response: qaResponse.content,
                    value: null
                };
            }
    
            // For field collection, validate the extracted value
            if (analysis.type === 'field_collection' && analysis.value) {
                // Additional validation based on field type
                const validationPrompt = `
                Validate and format this extracted value for the field type:
                Field: ${fieldName}
                Value: "${analysis.value}"
    
                Rules for date and time fields:
                - Handle natural language expressions (e.g., "next Monday", "tomorrow", "next week")
                - Handle combined date-time fields (e.g., "next Monday 6pm", "tomorrow at 3:00")
                - For standalone dates: format as YYYY-MM-DD
                - For standalone times: format as HH:MM (24-hour)
                - For combined date-time: format as "YYYY-MM-DD HH:MM"
                
                Rules for other fields:
                - For "email": Must be a valid email address
                - For "phone": Must be a valid phone number format
                - For "name": Must be a proper name format
                
                Context:
                - Current date: ${new Date().toISOString().split('T')[0]}
                - Reference time: ${new Date().toTimeString().split(' ')[0]}
    
                First, determine if this is a valid date/time expression.
                Then format it according to the rules above.
                Return ONLY the validated and formatted value, or "invalid" if validation fails.
                `;
    
                const validationResponse = await this.gemini.generateFlowProcessor(validationPrompt, [], {
                    maxTokens: 100,
                    temperature: 0.1
                });
    
                const validatedValue = validationResponse.content.trim();
                
                if (validatedValue === 'invalid') {
                    return {
                        type: 'field_collection',
                        value: null,
                        error: 'Invalid format'
                    };
                }
    
                return {
                    type: 'field_collection',
                    value: validatedValue
                };
            }
    
            // Fallback for any other cases
            return {
                type: 'field_collection',
                value: null,
                error: 'Unable to extract value'
            };
    
        } catch (error) {
            console.error('Error in validateFieldValue:', error);
            return {
                type: 'field_collection',
                value: null,
                error: 'Processing error'
            };
        }
    }
    async getVectorContext(message, assistantId) {
        console.log('getVectorContext called');
        const messageEmbedding = await this.gemini.generateEmbeddings(message);
        return await this.vectors.searchVectors(messageEmbedding, 5, {
            assistantId,
            type: ['instructions', 'document'],
            includeMetadata: true,
        });
    }
}

export default EnhancedFlowProcessor;

// class EnhancedFlowProcessor {
//     constructor(geminiService, firestore, vectors, userId) {
//         this.gemini = geminiService;
//         this.firestore = firestore;
//         this.vectors = vectors;
//         this.userId = userId;
//         this.smartTagger = new SmartTagger(geminiService, userId);
//     }

//     async processMessage(message, sessionId, assistant, context = {}) {
//         try {
//             // Get conversation history
//             const previousMessages = await this.getPreviousMessages(sessionId);
            
//             // Get vector search results
//             const vectorResults = await this.getVectorContext(message, assistant.id);

//             // Convert flow data to instructions format
//             const flowInstructions = this.convertFlowToInstructions(assistant.flowData);

//             // Build complete context
//             const enhancedContext = await this.buildFullContext({
//                 message,
//                 flowInstructions,
//                 previousMessages,
//                 assistant,
//                 vectorResults
//             });

//             // Generate response with node detection
//             const response = await this.generateResponse(message, enhancedContext);

//             // Process detected node in background
//             if (response.detectedNode) {
//                 this.smartTagger.processNodeData(
//                     assistant.flowData.nodes.find(n => n.id === response.detectedNode),
//                     message,
//                     sessionId
//                 ).catch(console.error);
//             }

//             return {
//                 content: response.content
//             };
//         } catch (error) {
//             console.error('Error in processMessage:', error);
//             return {
//                 content: "I apologize, but I'm having trouble processing your message. Could you please try again?"
//             };
//         }
//     }

//     convertFlowToInstructions(flowData) {
//         const instructions = {
//             flows: {},
//             nodes: {},
//             paths: {}
//         };

//         // Convert nodes to instructions
//         flowData.nodes.forEach(node => {
//             // Store node basic info
//             instructions.nodes[node.id] = {
//                 message: node.data.message,
//                 type: node.type,
//                 fieldName: node.data.fieldName || null,
//                 required: []
//             };

//             // If it's a starting point (dialogue node or marked as starting)
//             if (node.type === 'dialogueNode' || node.data.nodeType === 'starting') {
//                 instructions.flows[node.data.message] = {
//                     startNode: node.id,
//                     description: node.data.message,
//                     nextSteps: []
//                 };
//             }
//         });

//         // Map paths between nodes
//         flowData.edges.forEach(edge => {
//             const sourceNode = flowData.nodes.find(n => n.id === edge.source);
//             const targetNode = flowData.nodes.find(n => n.id === edge.target);

//             if (!instructions.paths[sourceNode.id]) {
//                 instructions.paths[sourceNode.id] = [];
//             }

//             // Get the full path data
//             let pathData = {
//                 source: sourceNode.id,
//                 target: targetNode.id,
//                 message: targetNode.data.message,
//                 type: targetNode.type,
//                 data: targetNode.data
//             };

//             // Add function/trigger info if exists
//             if (edge.sourceHandle) {
//                 const [type, nodeId, functionId] = edge.sourceHandle.split('-');
//                 const functionsList = type === 'function' ? sourceNode.data.functions : sourceNode.data.triggers;
//                 const matchingFunction = functionsList?.find(f => f.id === functionId);
//                 if (matchingFunction) {
//                     pathData.condition = {
//                         type: type,
//                         content: matchingFunction.content,
//                         id: functionId
//                     };
//                 }
//             }

//             // Ensure all data is fully serialized
//             pathData = JSON.parse(JSON.stringify(pathData));
//             instructions.paths[sourceNode.id].push(pathData);
//         });

//         return instructions;
//     }

//     async buildFullContext({ message, flowInstructions, previousMessages, assistant, vectorResults }) {
//         const context = [
//             // System context
//             {
//                 role: 'system',
//                 content: `You are an AI assistant managing conversations following specific flows. Here are the conversation flows available:
//                 ${JSON.stringify(flowInstructions, null, 2)}

//                 Instructions:
//                 1. Maintain natural conversation while following flows
//                 2. When user matches a flow intent, follow that flow's steps
//                 3. Collect required information when needed
//                 4. Handle off-topic questions while maintaining flow context
//                 5. Tag responses that match flow nodes with <node_data> tags

//                 When following a flow node, format your response like:
//                 Your natural response here...
//                 <node_data>{"nodeId": "node_id", "flowState": "starting|continuing|completing"}</node_data>`
//             }
//         ];

//         // Add vector search results
//         vectorResults.forEach(vec => {
//             if (vec.metadata?.content) {
//                 context.push({
//                     role: 'system',
//                     content: `Relevant Information: ${vec.metadata.content}`
//                 });
//             }
//         });

//         // Add assistant instructions if available
//         if (assistant.instructions) {
//             context.push({
//                 role: 'system',
//                 content: `Assistant Instructions: ${assistant.instructions}`
//             });
//         }

//         // Add conversation history
//         context.push(...previousMessages);

//         return context;
//     }

//     async generateResponse(message, context) {
//         // Get last AI response and current state from context
//         const previousMessages = context.filter(msg => msg.role !== 'system');
//         const lastAIResponse = previousMessages.filter(msg => msg.role === 'assistant').pop()?.content || '';
        
//         const prompt = `
//         <thinking>
//         Analyze this user message in the context of the current conversation flow:
    
//         User Message: "${message}"
//         Last AI Response: "${lastAIResponse}"
//         Current Context: ${JSON.stringify(context.slice(-2))}

//         Step-by-step analysis:
//         1. Is this message directly related to any of our flow nodes?
//         2. Is this a valid response to what we're currently discussing?
//         3. Is this a tangential question that needs to be answered before continuing?
//         4. Should we handle this as out-of-flow QA and then return to the flow?
//         5. Does the user's message match or align or indirectly answer with any of our flow steps?
//         </thinking>
    
//         <reflection>
//         Based on the analysis:
//         - Direct Response: Would this message satisfy any flow requirements?
//         - QA Need: Does this require additional information before proceeding?
//         - Message Match: Does the user's message match or align with any flow steps?
//         - Flow State: Should we:
//             * Continue current flow
//             * Start new flow
//             * Handle as QA then return to flow
//             * Pure QA response
//         - Next Step: What's the most appropriate next action?
//         </reflection>
    
//         <action>
//         Based on this analysis:
//         1. If message matches a flow node:
//            Include: <node_data>{"nodeId": "[node id]", "flowState": "continuing|starting|completing", "confidence": 0.0-1.0}</node_data>
//         2. Keep response natural and conversational
//         3. If answering off-topic, maintain flow awareness
//         4. If collecting information, be clear what we need
//         5. If providing QA response, be concise but thorough
//         </action>
//         `;

//         const response = await this.gemini.generateSharedResponse(
//             message,
//             [...context, { role: 'system', content: prompt }],
//             {
//                 maxTokens: 1000,
//                 temperature: 0.7,
//                 topP: 0.8
//             }
//         );

//         // Extract node data if present
//         const nodeMatch = response.content.match(/<node_data>(.+?)<\/node_data>/);
//         const nodeData = nodeMatch ? JSON.parse(nodeMatch[1]) : null;

//         // Clean response
//         const cleanContent = response.content.replace(/<node_data>[\s\S]*?<\/node_data>/g, '').trim();

//         return {
//             content: cleanContent,
//             detectedNode: nodeData?.nodeId
//         };
//     }

//     async getPreviousMessages(sessionId, limit = 10) {
//         try {
//             const messagesRef = this.firestore.db
//                 .collection('shared_chat_messages')
//                 .where('sessionId', '==', sessionId)
//                 .orderBy('createdAt', 'asc');
            
//             const snapshot = await messagesRef.get();
//             return snapshot.docs
//                 .map(doc => ({
//                     role: doc.data().role,
//                     content: doc.data().content
//                 }))
//                 .slice(-limit);
//         } catch (error) {
//             console.error('Error in getPreviousMessages:', error);
//             return [];
//         }
//     }

//     async getVectorContext(message, assistantId) {
//         const messageEmbedding = await this.gemini.generateEmbeddings(message);
//         return await this.vectors.searchVectors(messageEmbedding, 5, {
//             assistantId,
//             type: ['instructions', 'document'],
//             includeMetadata: true
//         });
//     }
// }

// export default EnhancedFlowProcessor;


// import { Firestore } from '@google-cloud/firestore';
// import SmartTagger from './TagingAndStoring.js';

// class EnhancedFlowProcessor {
//     constructor(geminiService, firestore, vectors, userId) {
//         this.gemini = geminiService;
//         this.firestore = firestore;
//         this.vectors = vectors;
//         this.userId = userId; // Store userId
//         this.smartTagger = new SmartTagger(geminiService, userId); // Pass userId to SmartTagger

//     }

//     getExpectedInput(node) {
//         console.log('getExpectedInput called');
//         if (!node) return 'None';
        
//         switch (node.type) {
//             case 'fieldSetterNode':
//                 return `Field input for: ${node.data.fieldName}`;
//             case 'dialogueNode':
//                 return 'Selection from available options';
//             case 'responseNode':
//                 return 'Free form response';
//             default:
//                 return 'None';
//         }
//     }

//     getAvailableFunctions(node) {
//         console.log('getAvailableFunctions called');
//         if (!node?.data?.functions) return 'None';
//         return node.data.functions.map(f => f.content).join(', ');
//     }

//     async updateSessionState(sessionId, updates) {
//         console.log('updateSessionState called');
//         const sessionRef = this.firestore.db
//             .collection('chat_sessions')
//             .doc(sessionId);
            
//         await sessionRef.set(updates, { merge: true });
//     }

//     async getCurrentOrStartingNode(sessionId, assistant) {
//         console.log('getCurrentOrStartingNode called');
//         const session = await this.firestore.db
//             .collection('chat_sessions')
//             .doc(sessionId)
//             .get();
        
//         const sessionData = session.data() || {};
        
//         // If there's a current node, return it
//         if (sessionData.currentNodeId) {
//             return assistant.flowData.nodes.find(n => n.id === sessionData.currentNodeId);
//         }
        
//         // Otherwise return the starting node
//         return assistant.flowData.nodes.find(n => n.data.nodeType === 'starting');
//     }

//     async getPreviousMessages(sessionId, limit = 10) {
//         console.log('getPreviousMessages called');
//         try {
//             // Use the existing composite index
//             console.log('SESSION ID', sessionId)
//             const messagesRef = this.firestore.db
//                 .collection('shared_chat_messages')
//                 .where('sessionId', '==', sessionId)
//                 .orderBy('createdAt', 'asc') // Using existing ascending index
            
//             const snapshot = await messagesRef.get();
//             const messages = [];
            
//             snapshot.forEach(doc => {
//                 const data = doc.data();
//                 messages.push({
//                     role: data.role,
//                     content: data.content
//                 });
//             });
    
//             // Since messages are in ascending order, slice from the end to get last 'limit' messages
//             const lastMessages = messages.slice(Math.max(messages.length - limit, 0));
            
//             console.log("GOT MESSAGES")
//             console.log(lastMessages)
//             return lastMessages;
//         } catch (error) {
//             console.log('Error in getPreviousMessages:', error);
//             return []; // Return empty array if error
//         }
//     }

//     async processMessage(message, sessionId, assistant, context = {}) {
//         console.log('processMessage called');
//         try {
//             const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
//         const session = await sessionRef.get();
//         const sessionData = session.data() || {};

        
//         // For first interaction, start with the node that has nodeType: 'starting'
//         if (!sessionData.currentNodeId && !sessionData.started) {
//             const startingNode = assistant.flowData.nodes.find(n => n.data.nodeType === 'starting');
//             if (startingNode) {
//                 return await this.processNode(startingNode, message, sessionId, assistant, context);
//             }
//         }
//             // 1. Classify the message with error handling
//             let classification;
//             try {
//                 classification = await this.classifyMessage(message, sessionId, assistant);
//                 console.log('CLASSIFICATION Type')
//                 console.log(classification)
//             } catch (error) {
//                 // Removed console.error
//                 classification = {
//                     type: 'node_flow',
//                     returnToNode: false,
//                     currentNodeId: null,
//                     reasoning: 'Default due to classification error'
//                 };
//             }
            
//             if (classification.type === 'qa_flow') {
//                 // Handle QA flow with error handling
//                 try {
//                     const qaResponse = await this.processQAFlow(message, sessionId, assistant, context);
                    
//                     if (classification.returnToNode) {
//                         // qaResponse.content += "\n\nNow, let's return to our previous conversation. ";
                        
//                         const returnNode = assistant.flowData.nodes.find(n => 
//                             n.id === classification.currentNodeId
//                         );
//                         if (returnNode) {
//                             const nodeResponse = await this.processNode(
//                                 returnNode, 
//                                 message , // Use original message instead of null
//                                 sessionId, 
//                                 assistant, 
//                                 context
//                             );
//                             qaResponse.content += nodeResponse.content;
//                             qaResponse.complete = false;
//                         }
//                     }
                    
//                     return qaResponse;
//                 } catch (error) {
//                     // Removed console.error
//                     // Fallback to node flow if QA processing fails
//                     classification.type = 'node_flow';
//                 }
//             }
    
//             // Process as normal node flow
//             const currentNode = await this.getCurrentOrStartingNode(sessionId, assistant);
//             return await this.processNode(currentNode, message, sessionId, assistant, context);
//         } catch (error) {
//             // Removed console.error
//             return {
//                 content: "I apologize, but I'm having trouble processing your message. Could you please try again?",
//                 complete: false
//             };
//         }
//     }

//     async classifyMessage(message, sessionId, assistant) {
//         console.log('classifyMessage called');
//         // 1. Get current session state and context
//         const sessionRef = await this.firestore.db.collection('chat_sessions').doc(sessionId);
//         const session = await sessionRef.get();
//         const sessionData = session.data() || {};
        
//         // 2. Get current node if exists
//         let currentNode = null;
//         let currentNodeContext = null;
//         if (sessionData.currentNodeId) {
//             currentNode = assistant.flowData.nodes.find(n => n.id === sessionData.currentNodeId);
//             if (currentNode) {
//                 currentNodeContext = {
//                     type: currentNode.type,
//                     message: currentNode.data.message,
//                     functions: currentNode.data.functions,
//                     expectedInput: currentNode.data.fieldName // for field setter nodes
//                 };
//             }
//         }
//         // 3. Get the last message sent by the node (the response the user is replying to)
//         const previousMessages = await this.getPreviousMessages(sessionId, 2); // Get the last message
//         const lastNodeResponse = previousMessages.find(msg => msg.role === 'assistant')?.content || 'None';
//         console.log('CLASSIFY')
//         console.log( message,
//             currentNode?.type || 'None',
//             currentNode?.data?.message || 'None',
//             lastNodeResponse ,
//             this.getExpectedInput(currentNode) ,
//             this.getAvailableFunctions(currentNode)
//         )
//         // 4. Analyze with chain of thought
//         const prompt = `
//         <thinking>
//         Analyze this user message in the context of the current conversation flow:
    
//         User Message: "${message}"
//         Current Node Type: ${currentNode?.type || 'None'}
//         Current Node Message: ${currentNode?.data?.message || 'None'}
//         Last Node Response: "${lastNodeResponse}" 
//         Expected Input: ${this.getExpectedInput(currentNode)}
//         Available Functions: ${this.getAvailableFunctions(currentNode)}

//         Step-by-step analysis:
//         1. Is this message directly related to the current node's context?
//         2. Is this a valid response to what we're asking?
//         3. Is this a tangential question that needs to be answered before continuing?
//         4. Should we handle this as out-of-flow QA and then return to the flow?
//         5. Does the user's message ${message} match or align or indirect answer with the current node's  ${currentNode?.data?.message || 'None'} or the ${lastNodeResponse} response sent by the node?
//         </thinking>
    
//         <reflection>
//         Based on the analysis:
//         - Direct Response: Would this message satisfy the current node's requirements?
//         - QA Need: Does this require additional information before proceeding?
//         - Message Match: Does the user's message match or align with the current node's message or the last response sent by the node?
//         - Classify as "node_flow" if the message is:
//             * A direct answer to the question
//             * A request for clarification about the current topic
//             * An indirect response that's still topically relevant
//         - Only classify as "qa_flow" if ALL of these are true:
//             - Message is completely unrelated to current node's question
//             - Message is a pure information-seeking question
//             - Message doesn't relate to any Available Functions
//             - Message doesn't match Expected Input format
//             - Message doesn't try to answer the current node's question at all
//             - Message is clearly off-topic from current conversation
//         - Flow State: Should we maintain the current node state while handling this?
//         </reflection>
    
//         <reward>
//         Score confidence of classification (0.0-1.0)
//         </reward>
    
//         Return ONLY a JSON object in this exact format without any additional text:
//         {
//             "type": "node_flow" or "qa_flow",
//             "returnToNode": true or false,
//             "currentNodeId": "${currentNode?.id || null}",  // Pass the actual current node ID
//             "reasoning": "explanation of decision"
//         }
//         `;
    
//         // Use generateFlowProcessor instead of analyzeIntent
//         const response = await this.gemini.generateFlowProcessor(prompt, [], {
//             maxTokens: 200,
//             temperature: 0.3
//         });
    
//         try {
//             // Clean up the response content to remove any markdown formatting
//             let cleanedContent = response.content.trim();
//             if (cleanedContent.startsWith('```json')) {
//                 cleanedContent = cleanedContent.replace('```json', '').replace('```', '');
//             }
            
//             // Parse the cleaned JSON
//             const classification = JSON.parse(cleanedContent);
            
//             // Validate the classification object
//             if (!classification.type || !('returnToNode' in classification)) {
//                 // Removed console.log
//                 return {
//                     type: 'node_flow',
//                     returnToNode: false,
//                     currentNodeId: currentNode?.id,
//                     reasoning: 'Default classification due to invalid response'
//                 };
//             }
    
//             if (classification.type === 'qa_flow' && classification.returnToNode) {
//                 classification.currentNodeId = currentNode?.id || null;  // Set actual node ID
//             }
//             // Save state if needed
//             if (classification.type === 'qa_flow' && classification.returnToNode) {
//                 await sessionRef.set({
//                     returnToNodeId: currentNode.id,  // Use actual node ID here too
//                     qaInProgress: true
//                 }, { merge: true });
//             }
    
//             return classification;
//         } catch (error) {
//             // Removed console.error
//             // Default fallback
//             return {
//                 type: 'node_flow',
//                 returnToNode: false,
//                 currentNodeId: currentNode?.id,
//                 reasoning: 'Fallback classification due to parsing error'
//             };
//         }
//     }

//     async processQAFlow(message, sessionId, assistant, context) {
//         console.log('processQAFlow called');
//         // 1. Fetch context from multiple sources in parallel
//         const [vectorResults, previousMessages] = await Promise.all([
//             this.getVectorContext(message, assistant.id),
//             this.getPreviousMessages(sessionId)
//         ]);

//         // 2. Build enhanced context
//         const enhancedContext = await this.buildEnhancedContext({
//             vectors: vectorResults,
//             previousMessages,
//             assistant
//         });

//         // 3. Generate response using geminiSharedResponse
//         const response = await this.gemini.generateSharedResponse(message, enhancedContext, {
//             maxTokens: 1000,
//             category: assistant.category,
//             language: 'en',
//             tone: 'professional',
//             responseStyle: 'detailed',
//             complexityLevel: 'intermediate',
//             interactionStyle: 'collaborative'
//         });
//         console.log('SHARED RESPONSE FROM QA')
//         console.log(response)
//         // 4. Update session state
//         await this.updateSessionState(sessionId, {
//             lastMessage: message,
//             lastResponse: response.content,
//             isQAFlow: true
//         });

//         return {
//             content: response.content,
//             complete: false
//         };
//     }

//     async buildEnhancedContext({ vectors, previousMessages, assistant }) {
//         console.log('buildEnhancedContext called');
//         const context = [];

//         // Add assistant instructions
//         if (assistant.instructions) {
//             context.push({
//                 role: 'system',
//                 content: `Instructions: ${assistant.instructions}`
//             });
//         }

//         // Add vector search results
//         vectors.forEach(vec => {
//             if (vec.metadata?.content) {
//                 context.push({
//                     role: 'system',
//                     content: `Content from ${vec.metadata.name}: ${vec.metadata.content}`
//                 });
//             }
//         });

//         // Add previous messages
//         previousMessages.forEach(msg => {
//             context.push(msg);
//         });

//         return context;
//     }

//     async processNode(node, message, sessionId, assistant, context = {}) {
//         console.log('processNode called');
//         console.log('Processing Node:', node.id);
//         console.log('Node Type:', node.type);
//         console.log('Message:', message);
//         console.log('Node Data:', node.data);
      
//         // if (message) {
//         //     await this.smartTagger.processNodeData(node, message, sessionId);
//         // }
//         // Execute smartTagger in a non-blocking way
//         if (message) {
//             this.smartTagger.processNodeData(node, message, sessionId)
//             .catch(error => {
//                 console.error('Error in smart trigger processing:', error);
//             });
//         }
//         const nodeData = node.data;
//         if (!nodeData) {
//             // Removed console.error
//             return { content: 'Error processing node', complete: false };
//         }
      
//         // Ensure message is never null for Response Node
//         let processedMessage = message;
//         // Generate embeddings using the processed message
//         const relevantVectors = await this.getVectorContext(
//             processedMessage || nodeData.message,
//             assistant.id
//         );

//         const fullContext = await this.buildEnhancedContext({
//             vectors: relevantVectors,
//             previousMessages: context.previousMessages || [],
//             assistant
//         });

//         let result;
//         switch (node.type) {
//             case 'dialogueNode':
//                 result = await this.handleDialogueNode({ ...node, message: nodeData.message, functions: nodeData.functions }, processedMessage, sessionId, assistant, fullContext);
//                 break;
//             case 'scriptNode':
//                 result = await this.handleScriptNode({ ...node, message: nodeData.message }, processedMessage, sessionId, assistant, fullContext);
//                 break;
//             case 'fieldSetterNode':
//                 result = await this.handleFieldSetterNode({ ...node, message: nodeData.message, fieldName: nodeData.fieldName }, processedMessage, sessionId, assistant, fullContext);
//                 break;
//             case 'callTransferNode':
//                 result = await this.handleCallTransferNode({ ...node, message: nodeData.message, fieldName: nodeData.fieldName }, processedMessage, sessionId, assistant, fullContext);
//                 break;
//             case 'responseNode':
//                 result = await this.handleResponseNode({ ...node, message: nodeData.message }, processedMessage, sessionId, assistant, fullContext);
//                 break;
//             default:
//                 throw new Error(`Unknown node type: ${node.type}`);
//         }

//         // Removed existing console logs

//         // If no next node is found, return to the leading node
//         if (result.complete && !result.nextNode) {
//             const leadingNode = assistant.flowData.nodes.find(n => n.data.nodeType === 'leading');
//             if (leadingNode) {
//                 // Update session state to indicate we're waiting for user input
//                 const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
//                 await sessionRef.set({
//                     currentNodeId: leadingNode.id,
//                     started: true,
//                     awaitingResponse: true, // Wait for user input
//                 }, { merge: true });
        
//                 // Process the leading node's message explicitly
//                 const leadingNodeResponse = await this.processNode(leadingNode, null, sessionId, assistant, context);
        
//                 // Return the combined response
//                 return {
//                     content: `${result.content}\n\n${leadingNodeResponse.content}`,
//                     complete: false,
//                     nextNode: leadingNode.id,
//                 };
//             }
//         }
      
//         return result;
//     }

//     async handleDialogueNode(node, message, sessionId, assistant, context) {
//         console.log('handleDialogueNode called');
//         const sessionRef = await this.firestore.db.collection('chat_sessions').doc(sessionId);
//         const session = await sessionRef.get();
//         const sessionData = session.data() || {};

//         if (!sessionData.started) {
//             // First time hitting this node - generate initial response using node's message
//             const response = await this.processWorkflowInstruction(node.data.message, context, message);

//             const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);

//             // Save state that we're waiting for user response
//             await sessionRef.set({
//                 currentNodeId: node.id,
//                 started: true,
//                 awaitingResponse: hasOutgoingEdges,
//                 functions: node.data.functions,
//             }, { merge: true });
        
//             return {
//                 content: response,
//                 complete: !hasOutgoingEdges,
//                 nextNode: null, // No next node if there are no outgoing edges
//             };
//         }
      
//         if (sessionData.awaitingResponse && message) {
//             // Match user's response against functions
//             const matchedFunction = await this.matchUserResponseToFunction(
//                 message,
//                 node.data.functions,
//                 context
//             );
        
//             // Find corresponding function ID
//             const functionObj = node.data.functions.find(f => 
//                 f.content.toLowerCase().trim() === matchedFunction.toLowerCase().trim()
//             );
        
//             if (!functionObj) {
//                 return {
//                     content: "I couldn't quite understand that. Could you please try again with one of the available options?",
//                     complete: false,
//                 };
//             }
        
//             // Find the next node based on matched function
//             const flow = assistant.flowData;
//             const sourceHandle = `function-${node.id}-${functionObj.id}`;
//             const edge = flow.edges.find(e => 
//                 e.source === node.id && 
//                 e.sourceHandle === sourceHandle
//             );
        
//             if (edge) {
//                 const nextNode = flow.nodes.find(n => n.id === edge.target);
        
//                 // Update session state
//                 await sessionRef.set({
//                     currentNodeId: nextNode.id,
//                     started: false,
//                     awaitingResponse: true, // Wait for user input at the next node
//                 }, { merge: true });
        
//                 // Process the next node
//                 const nextNodeResponse = await this.processNode(nextNode, message, sessionId, assistant, context);
        
//                 return {
//                     content: nextNodeResponse.content,
//                     complete: nextNodeResponse.complete,
//                     nextNode: nextNode.id,
//                 };
//             }
//         }
//         const response = await this.processWorkflowInstruction(node.data.message, context, message);

    
//         return {
//             content: response,
//             complete: false,
//         };
//     }

//     async handleScriptNode(node, message, sessionId, assistant, context) {
//         console.log('handleScriptNode called');
//         const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
//         const session = await sessionRef.get();
//         const sessionData = session.data() || {};
//         const response = await this.processWorkflowInstruction(node.data.message, context, message);

//         console.log('RESPONSE FROM PROCESS WORKFLOW')
//         console.log(response)
//         if (!sessionData.started) {
//             // Generate response based on script instruction
    
//             // Check if there are any outgoing edges
//             const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
//             if (!hasOutgoingEdges) {
//                 // If no outgoing edges, mark as complete
//                 await sessionRef.set({
//                     currentNodeId: node.id,
//                     started: true,
//                     awaitingResponse: false, // No need to wait for user input
//                 }, { merge: true });
    
//                 return {
//                     content: response.content,
//                     complete: true, // Mark as complete
//                     nextNode: null, // No next node
//                 };
//             }
    
//             // Check if there is a "Next Steps" function
//             const nextStepsFunction = node.data.functions.find(f => f.type === 'nextSteps');
//             if (nextStepsFunction) {
//                 // If "Next Steps (Direct)" function exists, proceed directly to the next node
//                 const flow = assistant.flowData;
//                 const edge = flow.edges.find(e => e.source === node.id);
    
//                 if (edge) {
//                     const nextNode = flow.nodes.find(n => n.id === edge.target);
    
//                     // Update session state to move to the next node
//                     await sessionRef.set({
//                         currentNodeId: nextNode.id,
//                         started: false,
//                         awaitingResponse: true, // Wait for user input at the next node
//                     }, { merge: true });
    
//                     // Process the next node and get its response
//                     const nextNodeResponse = await this.processNode(nextNode, message, sessionId, assistant, context);
    
//                     // Combine responses from both nodes
//                     const combinedResponse = `${response}\n\n${nextNodeResponse.content}`;
//                     console.log('COMBINED RESPONSE')
//                     return {
//                         content: combinedResponse, // Combined response from both nodes
//                         complete: false, // Mark as incomplete to continue the flow
//                         nextNode: nextNode.id, // Move to the next node
//                     };
//                 }
//             }
    
//             // If no "Next Steps" function, wait for user response
//             await sessionRef.set({
//                 currentNodeId: node.id,
//                 started: true,
//                 awaitingResponse: true, // Wait for user input
//                 functions: node.data.functions,
//             }, { merge: true });
    
//             return {
//                 content: response.content,
//                 complete: false, // Wait for user input
//                 nextNode: null,
//             };
//         }
    
//         if (sessionData.awaitingResponse && message) {
//             // If the node is waiting for user input, match the user's response to available functions
//             const matchedFunction = await this.matchUserResponseToFunction(
//                 message,
//                 node.data.functions,
//                 context
//             );
    
//             // Find corresponding function
//             const functionObj = node.data.functions.find(f => 
//                 f.content.toLowerCase().trim() === matchedFunction.toLowerCase().trim()
//             );
    
//             if (!functionObj) {
//                 return {
//                     content: response.content,
//                     complete: true,
//                 };
//             }
    
//             // Find the next node based on matched function
//             const flow = assistant.flowData;
//             const sourceHandle = `function-${node.id}-${functionObj.id}`;
//             const edge = flow.edges.find(e => 
//                 e.source === node.id && 
//                 e.sourceHandle === sourceHandle
//             );
    
//             if (edge) {
//                 const nextNode = flow.nodes.find(n => n.id === edge.target);
    
//                 // Update session state
//                 await sessionRef.set({
//                     currentNodeId: nextNode.id,
//                     started: false,
//                     awaitingResponse: true, // Wait for user input at the next node
//                 }, { merge: true });
    
//                 // Process the next node
//                 return await this.processNode(nextNode, message, sessionId, assistant, context);
//             }
//         }
    
//         // If no outgoing edges, mark as complete
//         const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
//         if (!hasOutgoingEdges) {
//             return {
//                 content: "This is the end of the flow.",
//                 complete: true, // Mark as complete
//                 nextNode: null, // No next node
//             };
//         }
    
//         return {
//             content: response.content,
//             complete: false,
//         };
//     }

//     async handleFieldSetterNode(node, message, sessionId, assistant, context) {
//         console.log('handleFieldSetterNode called');
//         const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
//         const session = await sessionRef.get();
//         const sessionData = session.data() || {};
    
//         const isLeadingNode = node.data.nodeType === 'leading';
    
//         if (!sessionData.started) {
//             const prompt = `
//         You are assisting a user in ordering wine. Based on the user's previous message and the current node's instructions, generate a response to collect the required information.

//         User's previous message: "${message}"
//         Node instruction: "${node.data.message}"
//         Field to collect: "${node.data.fieldName}"

//         Guidelines for your response:
//         1. Ask the user to provide the ${node.data.fieldName}.
//         2. Be concise and professional.
//         3. Reference the user's previous message if relevant.
//         4. Do not ask for additional information unless explicitly required by the node.

//         Generate ONLY the response to collect the ${node.data.fieldName}.


//         `;
//             const response = await this.gemini.generateFlowProcessor(prompt, context, {
//                             maxTokens: 1000,
//                             temperature: 0.7,
//                         });
                
//             const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
//             // Save state that we're waiting for user response
//             await sessionRef.set({
//                 currentNodeId: node.id,
//                 started: true,
//                 awaitingResponse: hasOutgoingEdges, // Wait for user input
//                 fieldToSet: node.data.fieldName,
//             }, { merge: true });
    
//             return { 
//                 content: response.content,  
//                 complete: !hasOutgoingEdges, // Mark as complete if there are no outgoing edges
//                 nextNode: null, 
//             };
//         }
    
//         if (sessionData.awaitingResponse && message) {
//             const validationResult = await this.validateFieldValue(
//                 sessionData.fieldToSet,
//                 message,
//                 context
//             );
    
//             await sessionRef.set({
//                 [`fields.${sessionData.fieldToSet}`]: validationResult,
//             }, { merge: true });
    
//             const flow = assistant.flowData;
//             const edge = flow.edges.find(e => e.source === node.id && e.sourceHandle === `${node.id}-right`);
    
//             if (edge) {
//                 const nextNode = flow.nodes.find(n => n.id === edge.target);
    
//                 // Update session state
//                 await sessionRef.set({
//                     currentNodeId: nextNode.id,
//                     started: false,
//                     awaitingResponse: true, // Wait for user input
//                 }, { merge: true });
    
//                 // Process the next node
//                 return await this.processNode(nextNode, message, sessionId, assistant, context);
//             }
//         }
//         const response = await this.processWorkflowInstruction(node.data.message, context, message);

//         return {
//             content: response,
//             complete: false,
//         };
//     }

//     async handleCallTransferNode(node, message, sessionId, assistant, context) {
//         console.log('handleCallTransferNode called');
//         const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
//         const session = await sessionRef.get();
//         const sessionData = session.data() || {};
    
//         const isLeadingNode = node.data.nodeType === 'leading';
    
//         if (!sessionData.started) {
//             const response = await this.processWorkflowInstruction(node.data.message, context, message);

//             const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
//             // Save state that we're waiting for user response
//             await sessionRef.set({
//                 currentNodeId: node.id,
//                 started: true,
//                 awaitingResponse: hasOutgoingEdges, // Wait for user input
//             }, { merge: true });
    
//             return { 
//                 content: response, 
//                 complete: !hasOutgoingEdges, // Mark as complete if there are no outgoing edges
//                 nextNode: null,  
//             };
//         }
    
//         if (sessionData.awaitingResponse && message) {
//             // Create transfer notification
//             await this.firestore.db.collection('assistant_notifications').add({
//                 assistantId: assistant.id,
//                 type: 'call_transfer',
//                 message: node.data.message,
//                 sessionId,
//                 status: 'pending',
//                 createdAt: Firestore.FieldValue.serverTimestamp(),
//             });
    
//             const flow = assistant.flowData;
//             const edge = flow.edges.find(e => e.source === node.id);
    
//             if (edge) {
//                 const nextNode = flow.nodes.find(n => n.id === edge.target);
    
//                 // Update session state
//                 await sessionRef.set({
//                     currentNodeId: nextNode.id,
//                     started: false,
//                     awaitingResponse: true, // Wait for user input
//                 }, { merge: true });
    
//                 // Process the next node
//                 const nextNodeResponse = await this.processNode(nextNode, null, sessionId, assistant, context);
    
//                 return {
//                     content: nextNodeResponse.content,
//                     complete: nextNodeResponse.complete,
//                     nextNode: nextNode.id,
//                 };
//             }
//         }
    
//         return {
//             content: "Thank you for your patience. I am transferring you to one of our agents now.",
//             complete: true,
//         };
//     }

//     // async handleResponseNode(node, message, sessionId, assistant, context) {
//     //     console.log('handleResponseNode called');
//     //     const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
//     //     const session = await sessionRef.get();
//     //     const sessionData = session.data() || {};
    
//     //     // If the session hasn't started, generate the initial response
//     //     if (!sessionData.started) {
//     //         const response = await this.gemini.generateFlowProcessor(node.data.message, context, {
//     //             maxTokens: 1000,
//     //             temperature: 0.7,
//     //         });
    
//     //         // Check if there are any outgoing edges
//     //         const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
//     //         if (!hasOutgoingEdges) {
//     //             // If no outgoing edges, mark as complete
//     //             await sessionRef.set({
//     //                 currentNodeId: node.id,
//     //                 started: true,
//     //                 awaitingResponse: true, // No need to wait for user input
//     //             }, { merge: true });
    
//     //             return {
//     //                 content: response.content,
//     //                 complete: true, // Mark as complete
//     //                 nextNode: null, // No next node
//     //             };
//     //         }
    
//     //         // If there are outgoing edges, wait for user response
//     //         await sessionRef.set({
//     //             currentNodeId: node.id,
//     //             started: true,
//     //             awaitingResponse: true, // Wait for user input
//     //         }, { merge: true });
    
//     //         return {
//     //             content: response.content,
//     //             complete: false, // Wait for user input
//     //             nextNode: null,
//     //         };
//     //     }
    
//     //     // If the session is awaiting a user response and a message is provided
//     //     if (sessionData.awaitingResponse && message) {
//     //         // Generate a response using the user's message
//     //         const response = await this.gemini.generateSharedResponse(message, context, {
//     //             maxTokens: 1000,
//     //             category: assistant.category,
//     //             language: 'en', // Default language
//     //             tone: 'professional', // Default tone
//     //             responseStyle: 'detailed', // Default response style
//     //             complexityLevel: 'intermediate', // Default complexity level
//     //             interactionStyle: 'collaborative', // Default interaction style
//     //         });
//     //         console.log('SHARED RESPONSE FROM DB')
//     //         console.log(response)
//     //         // Check if there are any outgoing edges
//     //         const hasOutgoingEdges = assistant.flowData.edges.some(edge => edge.source === node.id);
    
//     //         if (!hasOutgoingEdges) {
//     //             // If no outgoing edges, mark as complete
//     //             await sessionRef.set({
//     //                 currentNodeId: node.id,
//     //                 started: true,
//     //                 awaitingResponse: true, // No need to wait for user input
//     //             }, { merge: true });
    
//     //             return {
//     //                 content: response.content,
//     //                 complete: true, // Mark as complete
//     //                 nextNode: null, // No next node
//     //             };
//     //         }
    
//     //         // If there are outgoing edges, proceed to the next node
//     //         const flow = assistant.flowData;
//     //         const edge = flow.edges.find(e => e.source === node.id);
//     //         const nextNode = edge ? flow.nodes.find(n => n.id === edge.target) : null;

//     //         if (edge) {
//     //             const nextNode = flow.nodes.find(n => n.id === edge.target);
    
//     //             // Update session state to move to the next node
//     //             await sessionRef.set({
//     //                 currentNodeId: nextNode.id,
//     //                 started: false,
//     //                 awaitingResponse: true, // Wait for user input at the next node
//     //             }, { merge: true });
    
//     //             // Process the next node
//     //             const nextNodeResponse = await this.processNode(nextNode, message, sessionId, assistant, context);
    
//     //             // Return the combined response
//     //             return {
//     //                 content: `${response.content}\n\n${nextNodeResponse.content}`,
//     //                 complete: false, // Mark as incomplete to continue the flow
//     //                 nextNode: nextNode.id, // Move to the next node
//     //             };
//     //         }
//     //     }
    
//     //     // Default fallback response
//     //     return {
//     //         content: "This is the end of the flow.",
//     //         complete: true, // Mark as complete
//     //         nextNode: null, // No next node
//     //     };
//     // }
//     // async handleResponseNode(node, message, sessionId, assistant, context) {
//     //     console.log('handleResponseNode called');
//     //     const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
//     //     const session = await sessionRef.get();
//     //     const sessionData = session.data() || {};
    
//     //     // If the session hasn't started, generate the initial response
//     //     if (!sessionData.started) {
//     //         const response = await this.gemini.generateFlowProcessor(node.data.message, context, {
//     //             maxTokens: 1000,
//     //             temperature: 0.7,
//     //         });
    
//     //         await sessionRef.set({
//     //             currentNodeId: node.id,
//     //             started: true,
//     //             awaitingResponse: true,
//     //             responseStep: 'initial',
//     //             triggers: node.data.triggers || []
//     //         }, { merge: true });
    
//     //         return {
//     //             content: response.content,
//     //             complete: false,
//     //             nextNode: null,
//     //         };
//     //     }
    
//     //     // If waiting for first response, get shared response
//     //     if (sessionData.responseStep === 'initial' && message) {
//     //         const response = await this.gemini.generateSharedResponse(message, context, {
//     //             maxTokens: 1000,
//     //             category: assistant.category,
//     //             language: 'en',
//     //             tone: 'professional',
//     //             responseStyle: 'detailed',
//     //             complexityLevel: 'intermediate',
//     //             interactionStyle: 'collaborative',
//     //         });
//     //         console.log('SHARED RESPONSE FROM RESPONSE NODE', response)
//     //         // Update state to wait for trigger matching
//     //         await sessionRef.set({
//     //             responseStep: 'awaiting_trigger'
//     //         }, { merge: true });
    
//     //         return {
//     //             content: response.content,
//     //             complete: false,
//     //             nextNode: null,
//     //         };
//     //     }
    
//     //     // If we got shared response and waiting for trigger match
//     //     if (sessionData.responseStep === 'awaiting_trigger' && message) {
//     //         // Match user's response against triggers
//     //         const matchedTrigger = await this.matchUserResponseToFunction(
//     //             message,
//     //             node.data.triggers,
//     //             context
//     //         );
    
//     //         // Find corresponding trigger
//     //         const triggerObj = node.data.triggers.find(t => 
//     //             t.content.toLowerCase().trim() === matchedTrigger.toLowerCase().trim()
//     //         );
    
//     //         if (triggerObj) {
//     //             const flow = assistant.flowData;
//     //             const sourceHandle = `trigger-${node.id}-${triggerObj.id}`;
//     //             const edge = flow.edges.find(e => 
//     //                 e.source === node.id && 
//     //                 e.sourceHandle === sourceHandle
//     //             );
    
//     //             if (edge) {
//     //                 const nextNode = flow.nodes.find(n => n.id === edge.target);
    
//     //                 // Update session state
//     //                 await sessionRef.set({
//     //                     currentNodeId: nextNode.id,
//     //                     started: false,
//     //                     awaitingResponse: true,
//     //                     responseStep: 'initial'
//     //                 }, { merge: true });
    
//     //                 // Process next node
//     //                 return await this.processNode(nextNode, message, sessionId, assistant, context);
//     //             }
//     //         }
    
//     //         return {
//     //             content: "I couldn't quite understand that. Could you please try again with one of the available options?",
//     //             complete: false,
//     //             nextNode: null,
//     //         };
//     //     }
    
//     //     return {
//     //         content: "I'm waiting for your response.",
//     //         complete: false,
//     //         nextNode: null,
//     //     };
//     // }
//     async handleResponseNode(node, message, sessionId, assistant, context) {
//         console.log('handleResponseNode called');
//         const sessionRef = this.firestore.db.collection('chat_sessions').doc(sessionId);
//         const session = await sessionRef.get();
//         const sessionData = session.data() || {};
    
//         // If the session hasn't started, generate the initial response
//         if (!sessionData.started) {
//             const response = await this.gemini.generateFlowProcessor(node.data.message, context, {
//                 maxTokens: 1000,
//                 temperature: 0.7,
//             });
    
//             await sessionRef.set({
//                 currentNodeId: node.id,
//                 started: true,
//                 awaitingResponse: true,
//                 responseStep: 'initial',
//                 triggers: node.data.triggers || []
//             }, { merge: true });
    
//             return {
//                 content: response.content,
//                 complete: false,
//                 nextNode: null,
//             };
//         }
    
//         // If waiting for first response, get shared response
//         if (sessionData.responseStep === 'initial' && message) {
//             const response = await this.gemini.generateSharedResponse(message, context, {
//                 maxTokens: 1000,
//                 category: assistant.category,
//                 language: 'en',
//                 tone: 'professional',
//                 responseStyle: 'detailed',
//                 complexityLevel: 'intermediate',
//                 interactionStyle: 'collaborative',
//             });
//             console.log('SHARED RESPONSE FROM RESPONSE NODE', response);
    
//             // Update state to wait for trigger matching
//             await sessionRef.set({
//                 responseStep: 'awaiting_trigger'
//             }, { merge: true });
    
//             return {
//                 content: response.content,
//                 complete: false,
//                 nextNode: null,
//             };
//         }
    
//         // If we got shared response and waiting for trigger match
//         if (sessionData.responseStep === 'awaiting_trigger' && message) {
//             // Match user's response against triggers
//             const matchedTrigger = await this.matchUserResponseToTrigger(
//                 message,
//                 node.data.triggers,
//                 context, 
//                 sessionId
//             );
    
//             if (!matchedTrigger) {
//                 // If no trigger matches, call getSharedResponse again with the user's message
//                 const response = await this.gemini.generateSharedResponse(message, context, {
//                     maxTokens: 1000,
//                     category: assistant.category,
//                     language: 'en',
//                     tone: 'professional',
//                     responseStyle: 'detailed',
//                     complexityLevel: 'intermediate',
//                     interactionStyle: 'collaborative',
//                 });
    
//                 // Stay in the same state and wait for another user response
//                 return {
//                     content: response.content,
//                     complete: false,
//                     nextNode: null,
//                 };
//             }
    
//             // Find corresponding trigger
//             const triggerObj = node.data.triggers.find(t => 
//                 t.content.toLowerCase().trim() === matchedTrigger.toLowerCase().trim()
//             );
    
//             if (triggerObj) {
//                 const flow = assistant.flowData;
//                 const sourceHandle = `trigger-${node.id}-${triggerObj.id}`;
//                 const edge = flow.edges.find(e => 
//                     e.source === node.id && 
//                     e.sourceHandle === sourceHandle
//                 );
    
//                 if (edge) {
//                     const nextNode = flow.nodes.find(n => n.id === edge.target);
    
//                     // Update session state
//                     await sessionRef.set({
//                         currentNodeId: nextNode.id,
//                         started: false,
//                         awaitingResponse: true,
//                         responseStep: 'initial'
//                     }, { merge: true });
                    
                    
//                     // Process next node
//                     return await this.processNode(nextNode, message, sessionId, assistant, context);
//                 }
//             }
    
//             // If no edge is found, call getSharedResponse again
//             const response = await this.gemini.generateSharedResponse(message, context, {
//                 maxTokens: 1000,
//                 category: assistant.category,
//                 language: 'en',
//                 tone: 'professional',
//                 responseStyle: 'detailed',
//                 complexityLevel: 'intermediate',
//                 interactionStyle: 'collaborative',
//             });
    
//             return {
//                 content: response.content,
//                 complete: false,
//                 nextNode: null,
//             };
//         }
    
//         // Default fallback response
//         return {
//             content: "I'm waiting for your response.",
//             complete: false,
//             nextNode: null,
//         };
//     }
//     async matchUserResponseToTrigger(userMessage, triggers, context, sessionId) {
//         console.log('matchUserResponseToTrigger called');
        

//         const previousMessages = await this.getPreviousMessages(sessionId, 2);
//         const lastAIResponse = previousMessages.find(msg => msg.role === 'assistant')?.content || 'None';
//         console.log('PREVIOUS MESSAGES', previousMessages)
//         console.log('LAST AI', lastAIResponse)
//         const prompt = `
//         <thinking>
//         We have the following conversation context:
//         Last AI Response: "${lastAIResponse}"
//         User's Message: "${userMessage}"
        
//         We also have these possible triggers:
//         ${triggers.map(t => `- "${t.content}"`).join('\n')}
        
//         We want to check if the user's message semantically corresponds to any of these trigger texts.
        
//         Step-by-step:
//         1. Interpret the user message: what is the user intending or expressing?
//         2. Compare that intent with each trigger.
//         3. If one trigger best matches the user's intent, return that trigger text exactly.
//         4. If none apply, return "no_match".
//         5. Output must be exactly one line with either the trigger text or "no_match".
//         </thinking>
//         `;
    
//         const response = await this.gemini.generateFlowProcessor(prompt, context, {
//             maxTokens: 200,
//             temperature: 0.3, // Lower temperature for more precise matching
//         });
    
//         const matchedTrigger = response.content.trim();
//         console.log(matchedTrigger)
//         return matchedTrigger === "no_match" ? null : matchedTrigger;
//     }
//     async matchUserResponseToFunction(userMessage, functions, context) {
//         console.log('matchUserResponseToFunction called');
//         const prompt = `
//         Analyze this user message and determine which function it matches best.
    
//         User message: "${userMessage}"
    
//         Available functions:
//         ${functions.map(f => `- ${f.content}`).join('\n')}
    
//         Return the function name that best matches the user's intent.
//         `;
//         const response = await this.gemini.generateFlowProcessor(prompt, context, {
//             maxTokens: 200,
//             temperature: 0.3, // Lower temperature for more precise matching
//         });
    
//         return response.content.trim();
//     }

//     async processWorkflowInstruction(instruction, context, userMessage = null) {
//         console.log('processWorkflowInstruction called');
//         const prompt = `
//             Process this workflow instruction and generate an appropriate response:
//             "${instruction}"
    
//             ${userMessage ? `User's message: "${userMessage}"` : ''}
    
//             Context:
//             ${context.map(c => `${c.role}: ${c.content}`).join('\n')}
    
//             Guidelines for your response:
//             1. Do not start with greetings like "Hi there," "Hello," or "Hey." until specifically asked in the instruction or in context.
//             2. Be concise and to the point.
//             3. Maintain a professional yet conversational tone.
//             4. If there's a user message, reference it in your response appropriately.
//             5. Use conversational phrases like "Hmm," "Ah, I see," or "Let me think about that" to make the interaction more human-like.
//         `;
        
//         const response = await this.gemini.generateProcessFlowProcessor(prompt, context, {
//             maxTokens: 500,
//             temperature: 0.7,
//         });
//         return response.content;
//     }

//     async validateFieldValue(fieldName, value, context) {
//         console.log('validateFieldValue called');
//         const prompt = `
//         Extract the required information from the user's message based on the field name:
//         Field: ${fieldName}
//         Value: "${value}"
      
//         Context:
//         ${context.map(c => `${c.role}: ${c.content}`).join('\n')}
      
//         Based on the field name, extract the following:
//         - For "date": Extract a date.
//         - For "time": Extract a time.
//         - For "email": Extract an email address.
//         - For "phone": Extract a phone number.
//         - For other fields: Extract the relevant information.
      
//         Return only the extracted value as a plain text response.
//         `;
//         const response = await this.gemini.generateFlowProcessor(prompt, context, {
//             maxTokens: 300,
//             temperature: 0.5,
//         });
      
//         // Return the extracted value directly
//         return response.content.trim();
//     }

//     async getVectorContext(message, assistantId) {
//         console.log('getVectorContext called');
//         const messageEmbedding = await this.gemini.generateEmbeddings(message);
//         return await this.vectors.searchVectors(messageEmbedding, 5, {
//             assistantId,
//             type: ['instructions', 'document'],
//             includeMetadata: true,
//         });
//     }
// }

// export default EnhancedFlowProcessor;