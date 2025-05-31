// services/rag.js
import { Firestore } from '@google-cloud/firestore';
import { cosineSimilarity } from './vectorUtils.js';
// import { generateEmbedding } from './ai/embeddings.js';
import geminiService from '../gemini.js'

const firestore = new Firestore();
const SIMILARITY_THRESHOLD = 0.5;
const MAX_RESULTS = 10;

class RAGService {
    constructor() {
        this.collections = {
            shared_chats: 'shared_chat_embeddings',
            fields: 'fields',
            kpis: 'kpis',
            context: 'context'
        };
    }

    formatContentByType(collectionName, data) {
      try {
          switch (collectionName) {
              case 'fields':
                  return `${data.fieldName || 'Unknown Field'}: ${data.fieldValue || 'No value'} (Source: ${data.source || 'Unknown'}, Node: ${data.nodeId || 'Unknown'})`;
              
              case 'context':
                  return `Type: ${data.nodeType || 'Unknown'}\n` +
                         `Intent: ${data.userIntent || 'Unknown'}\n` +
                         `Topics: ${(data.topics || []).join(', ') || 'None'}\n` +
                         `Entities: ${(data.entities || []).join(', ') || 'None'}\n` +
                         `Sentiment: ${data.sentiment || 'Unknown'}\n` +
                         `Urgency: ${data.urgency || 'Unknown'}\n` +
                         `Node: ${data.nodeId || 'Unknown'}`;
              
              case 'kpis':
                  return `KPI: ${data.kpiName || 'Unknown'}\n` +
                         `Category: ${data.category || 'Unknown'}\n` +
                         `Value: ${data.value || 0}\n` +
                         `Confidence: ${data.confidence || 0}\n` +
                         `Evidence: ${data.evidence || 'None'}`;
              
              default:
                  return data.content || '';
          }
      } catch (error) {
          console.error(`Error formatting content for ${collectionName}:`, error);
          return 'Error formatting content';
      }
  }

  async searchAllCollections(query, userId, sessionId = null) {
    try {
        // Generate embedding for the query
        const queryEmbedding = await geminiService.generateEmbeddings(query);
        console.log('Query Embedding:', queryEmbedding);

        // Search in parallel across all collections
        const [sharedResults, fieldResults, kpiResults, contextResults] = await Promise.all([
            this.searchSharedChats(queryEmbedding, userId),
            this.searchCollection(this.collections.fields, queryEmbedding, userId),
            this.searchCollection(this.collections.kpis, queryEmbedding, userId),
            this.searchCollection(this.collections.context, queryEmbedding, userId)
        ]);

        console.log('Individual results:', {
            sharedResults: sharedResults.length,
            fieldResults: fieldResults.length,
            kpiResults: kpiResults.length,
            contextResults: contextResults.length
        });

        // Combine and sort results by similarity
        const allResults = [...sharedResults, ...fieldResults, ...kpiResults, ...contextResults]
            .sort((a, b) => b.similarity - a.similarity)
            .slice(0, MAX_RESULTS);

        return allResults;
    } catch (error) {
        console.error('Error in searchAllCollections:', error);
        throw error;
    }
}

async searchCollection(collectionName, queryEmbedding, userId) {
  const results = [];

  try {
    console.log(`Searching sheet_embeddings for collection ${collectionName} and user ${userId}`);

    // Query the sheet_embeddings collection directly
    const embeddingsSnapshot = await firestore
      .collection('sheet_embeddings')
      .where('userId', '==', userId)
      .where('collectionType', '==', collectionName)
      .get();

    console.log(`Found ${embeddingsSnapshot.size} embeddings documents`);

    for (const embeddingDoc of embeddingsSnapshot.docs) {
      const embeddingData = embeddingDoc.data();
      
      if (!embeddingData.embedding) {
        console.log(`No embedding found in document ${embeddingDoc.id}`);
        continue;
      }

      // Extract embedding array
      const docEmbedding = Array.isArray(embeddingData.embedding) ? embeddingData.embedding :
                          embeddingData.embedding.values ? embeddingData.embedding.values :
                          Object.values(embeddingData.embedding);

      if (!Array.isArray(docEmbedding)) {
        console.log(`Invalid embedding format in ${embeddingDoc.id}:`, docEmbedding);
        continue;
      }

      const similarity = cosineSimilarity(queryEmbedding, docEmbedding);
      console.log(`Similarity for ${embeddingDoc.id}: ${similarity}`);

      if (similarity >= SIMILARITY_THRESHOLD) {
        // Get the original document data using references stored in embedding document
        const originalDocRef = firestore
          .collection('users')
          .doc(userId)
          .collection('sessions')
          .doc(embeddingData.sessionId)
          .collection(collectionName)
          .doc(embeddingData.documentId);

        const originalDoc = await originalDocRef.get();
        const originalData = originalDoc.data();

        if (originalData) {
          results.push({
            type: collectionName,
            content: this.formatContentByType(collectionName, originalData),
            originalData, // ADD THIS LINE - Critical for plot data
            similarity,
            metadata: {
              id: embeddingData.documentId,
              sessionId: embeddingData.sessionId,
              path: originalDocRef.path,
              timestamp: embeddingData.timestamp?.toDate() || null
            }
          });
        }
      }
    }

    return results;

  } catch (error) {
    console.error(`Error in searchCollection ${collectionName}:`, error);
    return [];
  }
}

async searchSharedChats(queryEmbedding, userId) {
  const results = [];
  
  try {
      // Query shared_chat_embeddings collection
      const snapshot = await firestore
          .collection(this.collections.shared_chats)
          .get();

      console.log(`Found ${snapshot.docs.length} total documents`);

      for (const doc of snapshot.docs) {
          const data = doc.data();
          console.log('Document data:', {
              id: doc.id,
              userId: data.userId,
              hasEmbedding: !!data.embedding,
              content: data.content?.substring(0, 50) // Log first 50 chars of content
          });

          if (!data.embedding || !data.content) continue;

          // Convert embedding from Firestore format to array
          const docEmbedding = Object.values(data.embedding.values || data.embedding);
          
          if (!Array.isArray(docEmbedding)) {
              console.log('Invalid embedding format:', docEmbedding);
              continue;
          }

          const similarity = cosineSimilarity(queryEmbedding, docEmbedding);
          console.log(`Similarity for doc ${doc.id}: ${similarity}`);

          if (similarity >= SIMILARITY_THRESHOLD && data.userId === userId) {
              results.push({
                  type: 'shared_chat',
                  content: data.content,
                  similarity,
                  originalData: data, // ADD THIS LINE - Needed for plots
                  metadata: {
                      sessionId: data.sessionId,
                      timestamp: data.createdAt?.toDate() || null,
                      role: data.role
                  }
              });
          }
      }

      console.log(`Found ${results.length} relevant results for userId ${userId}`);
      return results;

  } catch (error) {
      console.error('Error in searchSharedChats:', error);
      return [];
  }
}


    async buildContext(results, query) {
        // Sort by similarity and recency
        const scoredResults = results.map(result => ({
            ...result,
            score: this.calculateRelevanceScore(result, query)
        })).sort((a, b) => b.score - a.score);

        // Group by type for better organization
        const groupedResults = this.groupResultsByType(scoredResults);

        // Build structured context with metadata
        let contextSections = [];
        
        for (const [type, items] of Object.entries(groupedResults)) {
            const section = this.formatContextSection(type, items);
            contextSections.push(section);
        }

        // Add metadata about sources
        const sourcesSummary = this.generateSourcesSummary(groupedResults);

        return {
            context: contextSections.join('\n\n'),
            sourcesSummary,
            relevantSources: scoredResults.length,
            topSimilarity: scoredResults[0]?.similarity || 0
        };
    }

    calculateRelevanceScore(result, query) {
        const RECENCY_WEIGHT = 0.3;
        const SIMILARITY_WEIGHT = 0.7;

        // Calculate recency score (higher for more recent items)
        const timestamp = result.metadata.timestamp?.getTime() || Date.now();
        const age = (Date.now() - timestamp) / (1000 * 60 * 60 * 24); // age in days
        const recencyScore = Math.exp(-age / 30); // exponential decay over 30 days

        // Combine similarity and recency
        return (result.similarity * SIMILARITY_WEIGHT) + (recencyScore * RECENCY_WEIGHT);
    }

    groupResultsByType(results) {
        return results.reduce((groups, result) => {
            const type = result.type;
            if (!groups[type]) {
                groups[type] = [];
            }
            groups[type].push(result);
            return groups;
        }, {});
    }

    formatContextSection(type, items) {
        const typeHeader = `=== ${type.toUpperCase()} CONTEXT ===`;
        const formattedItems = items.map(item => {
            const metadata = this.formatMetadata(item.metadata);
            return `[Relevance: ${item.score.toFixed(2)}]${metadata}\n${item.content}`;
        }).join('\n\n');

        return `${typeHeader}\n${formattedItems}`;
    }

    formatMetadata(metadata) {
        const parts = [];
        if (metadata.sessionId) parts.push(`Session: ${metadata.sessionId}`);
        if (metadata.timestamp) parts.push(`Time: ${metadata.timestamp.toISOString()}`);
        return parts.length ? ` (${parts.join(' | ')})` : '';
    }

    generateSourcesSummary(groupedResults) {
        const summary = [];
        for (const [type, items] of Object.entries(groupedResults)) {
            summary.push({
                type,
                count: items.length,
                averageSimilarity: this.calculateAverageSimilarity(items),
                timeRange: this.getTimeRange(items)
            });
        }
        return summary;
    }

    calculateAverageSimilarity(items) {
        return items.reduce((sum, item) => sum + item.similarity, 0) / items.length;
    }

    getTimeRange(items) {
        const timestamps = items
            .map(item => item.metadata.timestamp)
            .filter(Boolean)
            .map(ts => ts.getTime());

        if (timestamps.length === 0) return null;

        return {
            oldest: new Date(Math.min(...timestamps)),
            newest: new Date(Math.max(...timestamps))
        };
    }


    async generatePromptWithContext(query, results) {
      const { context, sourcesSummary, relevantSources, topSimilarity } = await this.buildContext(results, query);
      
      // Calculate additional quality metrics
      const sourceTypes = sourcesSummary.map(s => s.type);
      const avgSimilarity = sourcesSummary.reduce((sum, s) => sum + s.averageSimilarity, 0) / sourcesSummary.length;
      const timeRange = this.getOverallTimeRange(sourcesSummary);
      console.log('RESULTS INSIDE PROMPT')
      console.log(results)
      return `
  You are a senior data analyst using this structured reasoning framework:
  
  1. **Query Analysis**
     - Primary question: "${query}"
     - Detected entities: [AUTO_DETECT]
     - Analysis type required: [TREND|DIAGNOSTIC|PREDICTIVE|PRESCRIPTIVE]
  
  2. **Source Evaluation**
     ${sourcesSummary.map(s => `
     - ${s.type.toUpperCase()} SOURCES:
       • Items: ${s.count}
       • Avg. Confidence: ${s.averageSimilarity.toFixed(2)}
       • Time Range: ${s.timeRange.oldest.toISOString().split('T')[0]} to ${s.timeRange.newest.toISOString().split('T')[0]}
     `).join('\n')}
     - REMEMBER IN HERE DO NOT SITE SOURCE STORAGE NAME LIKE 'SHARED_CHAT" OR  Something like this. 
  
  3. **Analytical Guidelines**
     - Required confidence threshold: ≥${SIMILARITY_THRESHOLD}
     - Top match confidence: ${topSimilarity.toFixed(2)}
     - Cross-validate across ${sourceTypes.length} data domains
  
  4. **Contextual Data**
     ${context.split('\n').map(line => `   • ${line}`).join('\n')}
  
  5. **Response Framework**
     **Required sections:**
     A. Executive Summary (≤3 bullet points)
     B. Methodology:
        - Used sources: ${sourceTypes.join(', ')}
        - Analysis techniques: [REGRESSION|CLUSTERING|TREND_ANALYSIS]
        - Confidence markers: [LOW|MED|HIGH]
     C. Quantitative Insights:
        - When visualization is needed, include:
           \`\`\`plot
        {
          "type": "line|bar|pie",
          "title": "Clear Chart Title",
          "dataSource": "kpis|fields|context|shared_chat",
          "xField": "fieldName|timestamp|category (numeric array)",
          "yField": "value|confidence|count (numberic array)",
          "aggregation": "sum|average|count (numeric value)",
          "filters": {
            "category": "optional-filter"
          }
        }
        \`\`\`
        EXAMPLE: 
        \`\`\`plot
        {
          "type": "bar",
          "title": "Customer Satisfaction by Category",
          "dataSource": "kpis",
          "xField": "[10, 20, 30],
          "yField": "[20, 50, 100]",
          "aggregation": "average"
        }
        \`\`\`
          
     D. Actionable Recommendations:
        - Priority matrix: [IMPACT vs EFFORT]
        - Risk assessment: [LOW/MED/HIGH]
  
  6. **Validation Checks**
     - [ ] Cross-source consistency
     - [ ] Temporal relevance
     - [ ] Statistical significance
     - [ ] Business impact alignment
  
  Format plots as JSON code blocks between \`\`\`plot and \`\`\` tags
  Begin response with "🧠 Analysis Chain:" and follow the numbered framework exactly. Highlight uncertainties using [⚠️ LOW CONFIDENCE] tags.`;
  
}
  
  // Add helper method to calculate overall time range
  getOverallTimeRange(sourcesSummary) {
      const allDates = sourcesSummary.flatMap(s => 
          [s.timeRange.oldest.getTime(), s.timeRange.newest.getTime()]
      );
      return {
          oldest: new Date(Math.min(...allDates)),
          newest: new Date(Math.max(...allDates))
      };
  }
}

export default new RAGService();