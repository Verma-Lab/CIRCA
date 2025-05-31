// services/ai/qwen/utils.js
import { Storage } from '@google-cloud/storage';

class QwenUtils {
  constructor() {
    this.storage = new Storage();
    this.bucketName = process.env.GOOGLE_CLOUD_BUCKET;
  }

  async validateModelWeights(weightPath) {
    try {
      const file = this.storage.bucket(this.bucketName).file(weightPath);
      const [exists] = await file.exists();
      return exists;
    } catch (error) {
      console.error('Weight validation error:', error);
      return false;
    }
  }

  async copyWeights(sourceWeightPath, destWeightPath) {
    try {
      const sourceBucket = this.storage.bucket(this.bucketName);
      const sourceFile = sourceBucket.file(sourceWeightPath);
      const destFile = sourceBucket.file(destWeightPath);

      await sourceFile.copy(destFile);
      return true;
    } catch (error) {
      console.error('Weight copy error:', error);
      throw new Error(`Failed to copy weights: ${error.message}`);
    }
  }

  generateModelPath(assistantId, version) {
    return `model-weights/fine-tuned/${assistantId}/v${version}`;
  }

  generateTrainingPath(assistantId) {
    return `training-artifacts/processed/${assistantId}`;
  }

  async cleanupOldWeights(assistantId, keepVersions = 2) {
    try {
      const prefix = `model-weights/fine-tuned/${assistantId}/`;
      const [files] = await this.storage.bucket(this.bucketName).getFiles({ prefix });
      
      // Sort files by creation time
      const sortedFiles = files.sort((a, b) => {
        return new Date(b.metadata.timeCreated) - new Date(a.metadata.timeCreated);
      });

      // Keep the most recent versions
      const filesToDelete = sortedFiles.slice(keepVersions);
      
      // Delete old versions
      await Promise.all(filesToDelete.map(file => file.delete()));
      
      return {
        kept: keepVersions,
        deleted: filesToDelete.length
      };
    } catch (error) {
      console.error('Cleanup error:', error);
      throw new Error(`Failed to cleanup old weights: ${error.message}`);
    }
  }

//   async validateTrainingData(assistantId) {
//     try {
//       const prefix = this.generateTrainingPath(assistantId);
//       const [files] = await this.storage.bucket(this.bucketName).getFiles({ prefix });
      
//       return {
//         isValid: files.length > 0,
//         fileCount: files.length
//       };
//     } catch (error) {
//       console.error('Data validation error:', error);
//       return {
//         isValid: false,
//         error: error.message
//       };
//     }
//   }
async validateTrainingData(assistantId) {
    try {
      const prefix = this.generateTrainingPath(assistantId);
      console.log('Validating training data with prefix:', prefix);
      
      const [files] = await this.storage.bucket(this.bucketName).getFiles({ prefix });
      console.log('Found files:', files.map(f => f.name));
      
      // Add more detailed validation
      const isValid = files.some(file => file.name.endsWith('.jsonl'));
      
      const validationResult = {
        isValid,
        fileCount: files.length,
        files: files.map(f => f.name),
        path: prefix
      };
      
      console.log('Validation result:', validationResult);
      return validationResult;
      
    } catch (error) {
      console.error('Data validation error:', error);
      return {
        isValid: false,
        error: error.message,
        path: this.generateTrainingPath(assistantId)
      };
    }
  }
}
// if (assistantData.modelType === 'qwen') {
      //   try {
      //     // Use Qwen's predict function
      //     console.log('Using Qwen prediction service');
      //     const qwenResponse = await qwenService.predict(assistantId, message);

      //     // Store chat messages
      //     await firestore.collection('chat_messages').add({
      //       assistantId,
      //       userId,
      //       role: 'user',
      //       content: message,
      //       category: assistantData.category,
      //       createdAt: new Date(),
      //       isTrainingMessage: false
      //     });

      //     await firestore.collection('chat_messages').add({
      //       assistantId,
      //       userId,
      //       role: 'assistant',
      //       content: qwenResponse.content || qwenResponse.text || qwenResponse.response,
      //       category: assistantData.category,
      //       createdAt: new Date(),
      //       isTrainingMessage: false
      //     });

      //     return res.json({
      //       content: qwenResponse.content || qwenResponse.text || qwenResponse.response,
      //       language: language,
      //       category: assistantData.category,
      //       trained: isTraining === true
      //     });
      //   } catch (qwenError) {
      //     console.error('Qwen prediction error:', qwenError);
      //     throw new Error(`Qwen prediction failed: ${qwenError.message}`);
      //   }
      // }
export default new QwenUtils();

