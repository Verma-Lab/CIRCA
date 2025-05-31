// test-firestore.js
import { Firestore } from '@google-cloud/firestore';
import dotenv from 'dotenv';
dotenv.config();


console.log('Project ID:', process.env.GOOGLE_CLOUD_PROJECT_ID);
console.log('Key Path:', process.env.GOOGLE_CLOUD_KEY_PATH);

const firestore = new Firestore({
  projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
  keyFilename: process.env.GOOGLE_CLOUD_KEY_PATH
});

async function listCollections() {
  try {
    console.log('Attempting to list collections...');
    const collections = await firestore.listCollections();
    console.log('Collections found:', collections.length);
    collections.forEach(collection => {
      console.log('- Collection:', collection.id);
    });
  } catch (error) {
    console.error('Error listing collections:', error);
  }
}

listCollections();