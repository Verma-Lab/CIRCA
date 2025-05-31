import type { ChatCompletionModel } from '../../pinecone-generated-ts-fetch/assistant_data';
import { AsstDataOperationsProvider } from './asstDataOperationsProvider';
import type { ChatOptions } from './types';
export declare const chatCompletion: (assistantName: string, apiProvider: AsstDataOperationsProvider) => (options: ChatOptions) => Promise<ChatCompletionModel>;
