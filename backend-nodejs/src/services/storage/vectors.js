// backend/src/services/storage/vectors.js
'use strict';

import { VertexAI } from '@google-cloud/vertexai';
import firestore from '../db/firestore.js';
class VectorStorageService {
    constructor() {
      this.vertexai = new VertexAI({
        project: process.env.GOOGLE_CLOUD_PROJECT_ID,
        location: process.env.GOOGLE_CLOUD_REGION
      });
      this.indexId = process.env.VECTOR_INDEX_ID;
      this.vectorsCollection = 'assistant_vectors';
      console.log('VectorStorageService initialized with collection:', this.vectorsCollection);
    }

  // services/storage/vectors.js
async storeVectors(vectors, metadata = {}) {
    try {
      console.log('Starting vector storage operation:', {
        vectorsInput: {
          type: typeof vectors,
          isArray: Array.isArray(vectors),
          length: vectors?.length,
          firstVectorType: vectors?.[0] ? typeof vectors[0] : 'undefined',
          firstVectorLength: vectors?.[0]?.length
        },
        metadata
      });
  
      // Input validation
      if (!vectors || !Array.isArray(vectors)) {
        throw new Error('Vectors must be an array');
      }
  
      if (vectors.length === 0) {
        throw new Error('No vectors provided for storage');
      }
  
      // Validate each vector
      vectors.forEach((vector, index) => {
        if (!Array.isArray(vector)) {
          throw new Error(`Vector at index ${index} is not an array`);
        }
        if (!vector.length) {
          throw new Error(`Vector at index ${index} is empty`);
        }
        if (!vector.every(val => typeof val === 'number' && !isNaN(val))) {
          throw new Error(`Vector at index ${index} contains invalid values`);
        }
      });
  
      const batch = firestore.db.batch();
      const vectorRefs = [];
  
      console.log('Processing vectors for storage...');
      vectors.forEach((vector, i) => {
        const vectorRef = firestore.db.collection(this.vectorsCollection).doc();
        vectorRefs.push(vectorRef.id);
  
        const docData = {
          vector: vector,
          metadata: {
            assistantId: metadata.assistantId,
            type: metadata.type,
            chunk: i,
            createdAt: new Date(),
            dimensions: vector.length,
            ...metadata
          }
        };
  
        console.log(`Preparing vector ${i + 1}/${vectors.length}:`, {
          refId: vectorRef.id,
          metadata: docData.metadata,
          vectorLength: vector.length,
          vectorSample: vector.slice(0, 3)
        });
  
        batch.set(vectorRef, docData);
      });
  
      console.log('Committing batch write to Firestore...');
      await batch.commit();
      
      console.log('Successfully stored vectors:', {
        count: vectors.length,
        refs: vectorRefs
      });
  
      return {
        vectorIds: vectorRefs,
        count: vectors.length
      };
    } catch (error) {
      console.error('Vector storage error:', {
        error: error.message,
        stack: error.stack,
        metadata
      });
      throw new Error(`Failed to store vectors: ${error.message}`);
    }
  }

//   async searchVectors(queryVector, limit = 5, filter = {}) {
//     try {
//       console.log('Searching vectors with filters:', filter);
//       let query = firestore.db.collection(this.vectorsCollection);

//       // Apply filters
//       if (filter.assistantId) {
//         query = query.where('metadata.assistantId', '==', filter.assistantId);
//       }
      
//       // Handle array of types
//       if (filter.type) {
//         if (Array.isArray(filter.type)) {
//           query = query.where('metadata.type', 'in', filter.type);
//         } else {
//           query = query.where('metadata.type', '==', filter.type);
//         }
//       }

//       const snapshot = await query.get();
      
//       console.log(`Initial query found ${snapshot.size} vectors`);
      
//       if (snapshot.empty) {
//         console.log('No vectors found with initial query');
//         return [];
//       }

//       // Debug log each document
//       snapshot.docs.forEach((doc, index) => {
//         const data = doc.data();
//         console.log(`Vector ${index + 1} details:`, {
//           id: doc.id,
//           metadata: {
//             assistantId: data.metadata?.assistantId,
//             type: data.metadata?.type,
//             name: data.metadata?.name
//           },
//           hasVector: !!data.vector,
//           vectorLength: data.vector?.length,
//           contentPreview: data.metadata?.content?.substring(0, 100)
//         });
//       });

//       // Get all vectors and calculate similarities
//       const vectors = [];
//       for (const doc of snapshot.docs) {
//         const data = doc.data();
//         const vectorData = data.vector;

//         if (!Array.isArray(vectorData)) {
//           console.warn(`Invalid vector data for doc ${doc.id}:`, {
//             vectorType: typeof vectorData,
//             data: vectorData
//           });
//           continue;
//         }

//         if (vectorData.length !== queryVector.length) {
//           console.warn(`Vector length mismatch for doc ${doc.id}:`, {
//             storedLength: vectorData.length,
//             queryLength: queryVector.length
//           });
//           continue;
//         }

//         const similarity = this.cosineSimilarity(queryVector, vectorData);
        
//         vectors.push({
//           id: doc.id,
//           similarity,
//           metadata: data.metadata
//         });
//       }

//       // Sort by similarity and take top results
//       const results = vectors
//         .sort((a, b) => b.similarity - a.similarity)
//         .slice(0, limit);

//       console.log('Search results:', {
//         totalFound: vectors.length,
//         returningTop: results.length,
//         topResult: results[0] ? {
//           id: results[0].id,
//           similarity: results[0].similarity,
//           metadata: {
//             type: results[0].metadata.type,
//             name: results[0].metadata.name
//           }
//         } : null
//       });

//       return results;
//     } catch (error) {
//       console.error('Vector search error:', {
//         error: error.message,
//         stack: error.stack,
//         filter
//       });
//       throw new Error(`Failed to search vectors: ${error.message}`);
//     }
// }
// async searchVectors(queryVector, limit = 5, filter = {}) {
//   try {
//     // console.log('Searching vectors with enhanced similarity threshold:', filter);
//     let query = firestore.db.collection(this.vectorsCollection);

//     // Apply base filters
//     if (filter.assistantId) {
//       query = query.where('metadata.assistantId', '==', filter.assistantId);
//     }

//     // Enhanced type filtering
//     if (filter.type) {
//       if (Array.isArray(filter.type)) {
//         query = query.where('metadata.type', 'in', filter.type);
//       } else {
//         query = query.where('metadata.type', '==', filter.type);
//       }
//     }

//     const snapshot = await query.get();
//     console.log(`Found ${snapshot.size} initial vectors`);

//     // Process vectors with enhanced similarity calculation
//     const vectors = [];
//     for (const doc of snapshot.docs) {
//       const data = doc.data();
//       const vectorData = data.vector;

//       if (!this.validateVector(vectorData, queryVector)) {
//         continue;
//       }

//       // Calculate similarity with improved precision
//       const similarity = this.enhancedCosineSimilarity(queryVector, vectorData);
      
//       // Only include results above meaningful similarity threshold
//       if (similarity > 0.6) { // Adjust this threshold based on your needs
//         vectors.push({
//           id: doc.id,
//           similarity,
//           metadata: {
//             ...data.metadata,
//             matchScore: similarity.toFixed(4)
//           }
//         });
//       }
//     }

//     // Sort by similarity and take top results
//     const results = vectors
//       .sort((a, b) => b.similarity - a.similarity)
//       .slice(0, limit);

//     console.log('Enhanced search results:', {
//       totalCandidates: vectors.length,
//       qualifiedResults: results.length,
//       topMatch: results[0] ? {
//         similarity: results[0].similarity,
//         content: results[0].metadata.content?.substring(0, 100)
//       } : null
//     });

//     return results;
//   } catch (error) {
//     console.error('Vector search error:', error);
//     throw new Error(`Enhanced vector search failed: ${error.message}`);
//   }
// }
async searchVectors(queryVector, limit = 5, filter = {}) {
  try {
    let query = firestore.db.collection(this.vectorsCollection);

    // Apply base filters
    if (filter.assistantId) {
      query = query.where('metadata.assistantId', '==', filter.assistantId);
    }

    if (filter.type) {
      if (Array.isArray(filter.type)) {
        query = query.where('metadata.type', 'in', filter.type);
      } else {
        query = query.where('metadata.type', '==', filter.type);
      }
    }

    const snapshot = await query.get();
    console.log(`Found ${snapshot.size} initial vectors`);

    // Process all vectors first
    const vectors = [];
    for (const doc of snapshot.docs) {
      const data = doc.data();
      const vectorData = data.vector;

      if (!this.validateVector(vectorData, queryVector)) {
        continue;
      }

      const similarity = this.enhancedCosineSimilarity(queryVector, vectorData);
      
      // Store all results with their similarities
      vectors.push({
        id: doc.id,
        similarity,
        metadata: {
          ...data.metadata,
          matchScore: similarity.toFixed(4)
        }
      });
    }

    // Sort by similarity
    const sortedVectors = vectors.sort((a, b) => b.similarity - a.similarity);

    // Dynamic threshold based on the top results
    let results = [];
    if (sortedVectors.length > 0) {
      const topSimilarity = sortedVectors[0].similarity;
      const dynamicThreshold = Math.max(0.3, topSimilarity * 0.7); // 70% of top similarity or minimum 0.3

      results = sortedVectors
        .filter(v => v.similarity >= dynamicThreshold)
        .slice(0, limit);
    }

    console.log('Enhanced search results:', {
      totalCandidates: vectors.length,
      qualifiedResults: results.length,
      topMatch: results[0] ? {
        similarity: results[0].similarity,
        content: results[0].metadata.content?.substring(0, 100)
      } : null
    });

    return results;
  } catch (error) {
    console.error('Vector search error:', error);
    throw new Error(`Enhanced vector search failed: ${error.message}`);
  }
}
  buildFilter(filter) {
    const conditions = [];
    
    if (filter.userId) {
      conditions.push(`metadata.userId = "${filter.userId}"`);
    }
    
    if (filter.documentId) {
      conditions.push(`metadata.documentId = "${filter.documentId}"`);
    }

    return conditions.length > 0 ? conditions.join(' AND ') : undefined;
  }

  async deleteVectors(filter) {
    try {
      let query = firestore.db.collection(this.vectorsCollection);

      if (filter.assistantId) {
        query = query.where('metadata.assistantId', '==', filter.assistantId);
      }
      if (filter.type) {
        query = query.where('metadata.type', '==', filter.type);
      }

      const snapshot = await query.get();
      
      const batch = firestore.db.batch();
      snapshot.docs.forEach(doc => {
        batch.delete(doc.ref);
      });

      await batch.commit();
    } catch (error) {
      console.error('Vector deletion error:', error);
      throw new Error('Failed to delete vectors');
    }
  }

  validateVector(storedVector, queryVector) {
    if (!Array.isArray(storedVector) || !Array.isArray(queryVector)) {
      console.warn('Invalid vector format detected');
      return false;
    }
    if (storedVector.length !== queryVector.length) {
      console.warn(`Vector dimension mismatch: ${storedVector.length} vs ${queryVector.length}`);
      return false;
    }
    if (!storedVector.every(val => typeof val === 'number' && !isNaN(val))) {
      console.warn('Vector contains invalid values');
      return false;
    }
    return true;
  }

// enhancedCosineSimilarity(vecA, vecB) {
//   // Normalize vectors first
//   const normalizedA = this.normalizeVector(vecA);
//   const normalizedB = this.normalizeVector(vecB);
  
//   // Calculate dot product of normalized vectors
//   const dotProduct = normalizedA.reduce((sum, a, i) => sum + a * normalizedB[i], 0);
  
//   // Handle numerical precision
//   return Math.max(0, Math.min(1, dotProduct));
// }
enhancedCosineSimilarity(vecA, vecB) {
  const normalizedA = this.normalizeVector(vecA);
  const normalizedB = this.normalizeVector(vecB);
  
  // Use weighted dot product to emphasize key dimensions
  const dotProduct = normalizedA.reduce((sum, a, i) => {
    // Give more weight to higher-valued components
    const weight = Math.abs(a) > 0.5 ? 1.2 : 1;
    return sum + (a * normalizedB[i] * weight);
  }, 0);
  
  // Normalize the result to [0,1] range with softer boundaries
  return Math.max(0, Math.min(1, (dotProduct + 1) / 2));
}
normalizeVector(vector) {
  const magnitude = Math.sqrt(vector.reduce((sum, val) => sum + val * val, 0));
  return magnitude === 0 ? vector : vector.map(val => val / magnitude);
}
  // Helper method for vector similarity
  cosineSimilarity(vecA, vecB) {
    if (!Array.isArray(vecA) || !Array.isArray(vecB)) {
      throw new Error('Both vecA and vecB must be arrays');
    }
    if (vecA.length !== vecB.length) {
      throw new Error(`Vector lengths do not match: vecA is ${vecA.length}, vecB is ${vecB.length}`);
    }
  
    const dotProduct = vecA.reduce((sum, a, i) => sum + a * vecB[i], 0);
    const magnitudeA = Math.sqrt(vecA.reduce((sum, a) => sum + a * a, 0));
    const magnitudeB = Math.sqrt(vecB.reduce((sum, b) => sum + b * b, 0));
    if (magnitudeA === 0 || magnitudeB === 0) {
      return 0;
    }
    return dotProduct / (magnitudeA * magnitudeB);
  }
}

export default new VectorStorageService();
