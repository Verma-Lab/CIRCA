// utils/vectorUtils.js

/**
 * Parse embedding to ensure it's in the correct array format
 */
function parseEmbedding(embedding) {
    if (!embedding) return null;
    
    // If it's already an array, return it
    if (Array.isArray(embedding)) {
        return embedding;
    }
    
    // If it's an object with numeric keys (like Firestore arrays), convert to array
    if (typeof embedding === 'object') {
        const values = Object.values(embedding);
        if (values.every(val => typeof val === 'number')) {
            return values;
        }
    }
    
    return null;
}

/**
 * Calculate cosine similarity between two vectors
 */
export function cosineSimilarity(vec1, vec2) {
    // Parse embeddings to ensure correct format
    const parsedVec1 = parseEmbedding(vec1);
    const parsedVec2 = parseEmbedding(vec2);
    
    // Validate vectors
    if (!parsedVec1 || !parsedVec2 || parsedVec1.length !== parsedVec2.length) {
        console.error('Invalid vectors:', {
            vec1Length: parsedVec1?.length,
            vec2Length: parsedVec2?.length,
            vec1Type: typeof vec1,
            vec2Type: typeof vec2
        });
        return 0; // Return 0 similarity for invalid vectors
    }

    try {
        const dotProduct = parsedVec1.reduce((acc, val, i) => acc + val * parsedVec2[i], 0);
        const norm1 = Math.sqrt(parsedVec1.reduce((acc, val) => acc + val * val, 0));
        const norm2 = Math.sqrt(parsedVec2.reduce((acc, val) => acc + val * val, 0));
        
        if (norm1 === 0 || norm2 === 0) return 0;
        
        return dotProduct / (norm1 * norm2);
    } catch (error) {
        console.error('Error calculating similarity:', error);
        return 0;
    }
}

/**
 * Normalize a vector to unit length
 */
export function normalizeVector(vector) {
    const parsedVector = parseEmbedding(vector);
    if (!parsedVector) return null;

    try {
        const magnitude = Math.sqrt(parsedVector.reduce((acc, val) => acc + val * val, 0));
        if (magnitude === 0) return parsedVector;
        return parsedVector.map(val => val / magnitude);
    } catch (error) {
        console.error('Error normalizing vector:', error);
        return null;
    }
}

/**
 * Check if a vector is valid (array of numbers)
 */
export function isValidVector(vector) {
    const parsedVector = parseEmbedding(vector);
    return !!parsedVector;
}