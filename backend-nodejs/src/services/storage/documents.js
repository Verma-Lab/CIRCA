// backend/src/services/storage/documents.js
'use strict';

import { Storage } from '@google-cloud/storage';
import { v4 as uuidv4 } from 'uuid';

class DocumentStorageService {
  constructor() {
    this.storage = new Storage({
      keyFilename: process.env.GOOGLE_CLOUD_KEY_PATH,
      projectId: process.env.GOOGLE_CLOUD_PROJECT_ID
    });
    this.bucketName = process.env.GOOGLE_CLOUD_BUCKET;
    this.bucket = this.storage.bucket(this.bucketName);
  }

  async uploadDocument(file, metadata = {}) {
    try {
      const fileName = `${uuidv4()}-${file.originalname}`;
      const blob = this.bucket.file(fileName);

      // Create write stream
      const blobStream = blob.createWriteStream({
        metadata: {
          contentType: file.mimetype,
          metadata: {
            originalName: file.originalname,
            userId: metadata.userId,
            ...metadata
          }
        }
      });

      return new Promise((resolve, reject) => {
        blobStream.on('error', (error) => reject(error));
        blobStream.on('finish', async () => {
          // Make the file public
          await blob.makePublic();
          
          resolve({
            fileName,
            publicUrl: `https://storage.googleapis.com/${this.bucketName}/${fileName}`
          });
        });

        blobStream.end(file.buffer);
      });
    } catch (error) {
      console.error('Document upload error:', error);
      throw new Error('Failed to upload document');
    }
  }

  async deleteDocument(fileName) {
    try {
      await this.bucket.file(fileName).delete();
    } catch (error) {
      console.error('Document deletion error:', error);
      throw new Error('Failed to delete document');
    }
  }

  async getDocumentContent(fileName) {
    try {
      const file = this.bucket.file(fileName);
      const [content] = await file.download();
      return content;
    } catch (error) {
      console.error('Document retrieval error:', error);
      throw new Error('Failed to retrieve document');
    }
  }
}

export default new DocumentStorageService();
