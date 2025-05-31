// datamigration.cjs
import admin from 'firebase-admin';
import fs from 'fs';
// Load service account keys
const sourceServiceAccountRaw = fs.readFileSync('/Users/hritvik/persistbackend/op8imize-58b8c4ee316b.json', 'utf8');
const destServiceAccountRaw = fs.readFileSync('/Users/hritvik/persistbackend/vermalab-gemini-psom-e3ea-b93f97927cc3.json', 'utf8');

const sourceServiceAccount = JSON.parse(sourceServiceAccountRaw);
const destServiceAccount = JSON.parse(destServiceAccountRaw);

console.log('Source project:', sourceServiceAccount.project_id);
console.log('Destination project:', destServiceAccount.project_id);

// Initialize source Firestore with default database
const sourceApp = admin.initializeApp({
  credential: admin.credential.cert(sourceServiceAccount)
}, 'source');
const sourceDb = sourceApp.firestore();

// Initialize destination Firestore with circa database
const destApp = admin.initializeApp({
  credential: admin.credential.cert(destServiceAccount)
}, 'destination');

// Get Firestore with explicit database ID
const destDb = destApp.firestore();
destDb.settings({
  ignoreUndefinedProperties: true,
  preferRest: true,
  databaseId: 'circa'  // Explicitly set to 'circa'
});

console.log("Initialized source and destination databases");


console.log("Initialized source and destination databases");

// Update the migrateCollection function
async function migrateCollection(collectionName) {
    console.log(`Migrating collection: ${collectionName}`);
    
    try {
      // Get all documents from source collection
      const snapshot = await sourceDb.collection(collectionName).get();
      
      if (snapshot.empty) {
        console.log(`Collection ${collectionName} is empty.`);
        return 0;
      }
      
      console.log(`Found ${snapshot.size} documents in ${collectionName}`);
      
      // Adjust batch size based on collection size
      // Use smaller batches for large collections
      let batchSize = 200;
      if (snapshot.size > 1000) {
        batchSize = 50;  // Very small batches for very large collections
        console.log(`Large collection detected, reducing batch size to ${batchSize}`);
      } else if (snapshot.size > 500) {
        batchSize = 100;  // Smaller batches for large collections
        console.log(`Medium collection detected, reducing batch size to ${batchSize}`);
      }
      
      let totalCount = 0;
      
      // Process documents in smaller chunks
      for (let i = 0; i < snapshot.docs.length; i += batchSize) {
        const batch = destDb.batch();
        const chunk = snapshot.docs.slice(i, i + batchSize);
        let docsInBatch = 0;
        
        for (const doc of chunk) {
          try {
            const data = doc.data();
            
            // Skip very large documents
            const dataSize = JSON.stringify(data).length;
            if (dataSize > 500000) { // ~500KB
              console.log(`Skipping large document ${doc.id} (${dataSize} bytes)`);
              continue;
            }
            
            // Clean the data to remove any problematic fields
            const cleanData = JSON.parse(JSON.stringify(data));
            
            const destRef = destDb.collection(collectionName).doc(doc.id);
            batch.set(destRef, cleanData);
            docsInBatch++;
          } catch (docError) {
            console.error(`Error processing document ${doc.id}:`, docError);
            // Continue with other documents
          }
        }
        
        // Commit batch if there are documents to write
        if (docsInBatch > 0) {
          try {
            await batch.commit();
            totalCount += docsInBatch;
            console.log(`Committed batch of ${docsInBatch} documents (${i+1}-${i+chunk.length} of ${snapshot.size})`);
          } catch (batchError) {
            console.error(`Error committing batch: ${batchError.message}`);
            
            // If transaction too big error, try with smaller batch
            if (batchError.message.includes('Transaction too big') && docsInBatch > 5) {
              console.log(`Trying with an even smaller batch size for this chunk...`);
              // Process this chunk with an individual write for each document
              for (const doc of chunk) {
                try {
                  const data = doc.data();
                  const cleanData = JSON.parse(JSON.stringify(data));
                  await destDb.collection(collectionName).doc(doc.id).set(cleanData);
                  totalCount++;
                  console.log(`Individually wrote document ${doc.id}`);
                } catch (individualError) {
                  console.error(`Error writing individual document ${doc.id}:`, individualError);
                }
              }
            }
          }
        }
        
        // Add a small delay between batches to avoid overloading
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      
      console.log(`Finished migrating ${totalCount} documents in ${collectionName}`);
      return totalCount;
    } catch (error) {
      console.error(`Error in collection ${collectionName}:`, error);
      return 0;
    }
  }
// Main migration function
async function migrateAll() {
  try {
    console.log('Starting migration...');
    
    // Get list of collections from source
    console.log('Fetching source collections...');
    const collections = await sourceDb.listCollections();
    
    if (collections.length === 0) {
      console.log('No collections found in source database.');
      return;
    }
    
    console.log(`Found ${collections.length} collections to migrate.`);
    let totalDocs = 0;
    
    // Migrate each collection
    for (const collection of collections) {
      try {
        console.log(`Starting migration of collection: ${collection.id}`);
        const count = await migrateCollection(collection.id);
        totalDocs += count;
      } catch (collectionError) {
        console.error(`Error migrating collection ${collection.id}:`, collectionError);
        // Continue with other collections
      }
    }
    
    console.log(`Migration completed successfully! Migrated ${totalDocs} documents in total.`);
  } catch (error) {
    console.error('Migration failed:', error);
    
    // More detailed error information
    if (error.stack) {
      console.error('Error stack:', error.stack);
    }
  }
}

// Run the migration
migrateAll();