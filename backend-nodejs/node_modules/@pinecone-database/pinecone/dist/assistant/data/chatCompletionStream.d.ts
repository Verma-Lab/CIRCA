import type { PineconeConfiguration } from '../../data';
import { ChatStream } from '../../utils';
import { AsstDataOperationsProvider } from './asstDataOperationsProvider';
import type { ChatOptions, StreamedChatCompletionResponse } from './types';
export declare const chatCompletionStream: (assistantName: string, apiProvider: AsstDataOperationsProvider, config: PineconeConfiguration) => (options: ChatOptions) => Promise<ChatStream<StreamedChatCompletionResponse>>;
