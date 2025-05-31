// backend/src/services/storage/cloudStorage.js
'use strict';

import { Storage } from '@google-cloud/storage';
import { v4 as uuidv4 } from 'uuid';
import dotenv from 'dotenv'
dotenv.config()

class CloudStorageService {
  constructor() {
    this.storage = new Storage({
      keyFilename: process.env.GOOGLE_CLOUD_KEY_PATH,
      projectId: process.env.GOOGLE_CLOUD_PROJECT_ID
    });
    this.bucketName = process.env.GOOGLE_CLOUD_BUCKET;
    this.bucket = this.storage.bucket(this.bucketName);
  }

  // Upload files (PDFs, documents, etc.)
  async uploadFile(file, userId) {
    try {
      const fileId = uuidv4();
      const fileName = `documents/${userId}/${fileId}-${file.originalname}`;
      const blob = this.bucket.file(fileName);

      const blobStream = blob.createWriteStream({
        metadata: {
          contentType: file.mimetype
        }
      });

      return new Promise((resolve, reject) => {
        blobStream.on('error', reject);
        blobStream.on('finish', async () => {
          resolve({
            fileId,
            fileName,
            publicUrl: `https://storage.googleapis.com/${this.bucketName}/${fileName}`
          });
        });
        blobStream.end(file.buffer);
      });
    } catch (error) {
      console.error('File upload error:', error);
      throw error;
    }
  }
  async uploadImage(file, subfolder = 'avatars') {
    try {
      const fileId = uuidv4();
      const fileName = `${subfolder}/${fileId}-${file.originalname}`;
      const blob = this.bucket.file(fileName);

      const blobStream = blob.createWriteStream({
        metadata: {
          contentType: file.mimetype
        }
      });

      return new Promise((resolve, reject) => {
        blobStream.on('error', reject);

        blobStream.on('finish', async () => {
          // Generate a signed URL that expires 1 year from now
          const [signedUrl] = await blob.getSignedUrl({
            action: 'read',
            expires: Date.now() + 365 * 24 * 60 * 60 * 1000 // 1 year
          });

          resolve({
            fileId,
            fileName,
            publicUrl: signedUrl // This is a time-limited URL
          });
        });

        blobStream.end(file.buffer);
      });
    } catch (error) {
      console.error('File upload error:', error);
      throw error;
    }
  }


  async deleteFile(fileName) {
    try {
      await this.bucket.file(fileName).delete();
    } catch (error) {
      console.error('File deletion error:', error);
      throw error;
    }
  }

  async getFileContent(fileName) {
    try {
      const [content] = await this.bucket.file(fileName).download();
      return content;
    } catch (error) {
      console.error('File download error:', error);
      throw error;
    }
  }
}

export default new CloudStorageService();
