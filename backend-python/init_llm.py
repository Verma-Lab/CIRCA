import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from llama_index.core import Settings
# Import necessary types for the LLM abstract class
from llama_index.core.llms import LLM, CompletionResponse, CompletionResponseGen, ChatMessage, ChatResponse, ChatResponseGen, MessageRole
from typing import Sequence, Any
import asyncio # Import asyncio for async operations

class LLaMA3_1LLM(LLM):
    def __init__(self, model, tokenizer, **kwargs: Any):
        # Always call the super constructor with kwargs
        super().__init__(**kwargs)
        self.model = model
        self.tokenizer = tokenizer

    # Helper method to convert LlamaIndex messages to LLaMA 3.1 prompt format
    def _messages_to_prompt(self, messages: Sequence[ChatMessage]) -> str:
        # Convert LlamaIndex ChatMessage to HuggingFace chat format
        hf_messages = []
        for message in messages:
            # LlamaIndex's ChatMessage.role maps directly to HuggingFace's expected role names
            # Ensure the role is converted to string for HuggingFace's template
            hf_messages.append({"role": message.role.value, "content": message.content})
        
        # Apply the tokenizer's chat template
        # add_generation_prompt=True ensures the final assistant turn is primed.
        # This is crucial for models like LLaMA-3.1 to generate a response correctly.
        return self.tokenizer.apply_chat_template(hf_messages, tokenize=False, add_generation_prompt=True)

    # --- Synchronous Completion Methods (must be named 'complete') ---
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device) # Ensure tensor is on correct device
        outputs = self.model.generate(**inputs, max_new_tokens=512, **kwargs)
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return CompletionResponse(text=text)

    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        # Note: model.generate in HuggingFace often returns the full sequence or an iterator depending on flags.
        # For true token-by-token streaming, you might need specific `stream=True` or `return_iterator=True`
        # with models that support it and then process new tokens.
        # As a fallback or if model.generate returns full text:
        outputs = self.model.generate(**inputs, max_new_tokens=512, **kwargs)
        full_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Simulate streaming by yielding character by character
        for char in full_text:
            yield CompletionResponse(text=char, delta=char)

    # --- Synchronous Chat Methods (must be named 'chat') ---
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        prompt = self._messages_to_prompt(messages)
        # Call the public complete method
        response = self.complete(prompt, **kwargs) 
        return ChatResponse(
            message=ChatMessage(role=MessageRole.ASSISTANT, content=response.text)
        )

    def stream_chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponseGen:
        prompt = self._messages_to_prompt(messages)
        # Call the public stream_complete method
        completion_gen = self.stream_complete(prompt, **kwargs)
        
        # Convert CompletionResponseGen to ChatResponseGen
        for response_chunk in completion_gen:
            yield ChatResponse(
                message=ChatMessage(role=MessageRole.ASSISTANT, content=response_chunk.delta or ""),
                delta=response_chunk.delta,
            )

    # --- Asynchronous Completion Methods (must be named 'acomplete') ---
    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        # Run the synchronous complete method in a separate thread to avoid blocking the event loop
        return await asyncio.to_thread(self.complete, prompt, **kwargs)

    async def astream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        # For true asynchronous streaming, model.generate would ideally be non-blocking.
        # Since HuggingFace's generate is blocking, we run it in a thread and then
        # asynchronously yield chunks.
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = await asyncio.to_thread(self.model.generate, **inputs, max_new_tokens=512, **kwargs)
        full_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        for char in full_text:
            yield CompletionResponse(text=char, delta=char)
            await asyncio.sleep(0.0001) # Yield control back to the event loop

    # --- Asynchronous Chat Methods (must be named 'achat') ---
    async def achat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        # Run the synchronous chat method in a separate thread
        return await asyncio.to_thread(self.chat, messages, **kwargs)

    async def astream_chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponseGen:
        prompt = self._messages_to_prompt(messages)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = await asyncio.to_thread(self.model.generate, **inputs, max_new_tokens=512, **kwargs)
        full_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        for char in full_text:
            yield ChatResponse(
                message=ChatMessage(role=MessageRole.ASSISTANT, content=char),
                delta=char,
            )
            await asyncio.sleep(0.0001) # Yield control back to the event loop

    @property
    def metadata(self):
        return {"model_name": "LLaMA-3.1-8B"}

def initialize_llm():
    model_path = "/home/hritvik/persistent/models/llama-3.1-8b"
         
    # Check if the model directory exists
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model directory {model_path} does not exist. Please download the LLaMA 3.1 8B model first.")
         
    # Load tokenizer and model from local directory only
    try:
        tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                local_files_only=True
            )
        model = AutoModelForCausalLM.from_pretrained(
                model_path,
                local_files_only=True,
                torch_dtype=torch.float16,
                device_map="auto"
            )
    except Exception as e:
        raise RuntimeError(f"Failed to load model from {model_path}: {str(e)}")

    # Create and set the LLM instance
    llm = LLaMA3_1LLM(model, tokenizer)
    # This line correctly sets the LlamaIndex global LLM to your custom LLaMA 3.1 model.
    Settings.llm = llm

    return model, tokenizer

# Initialize the LLM when the script is imported
# This line will be executed when main.py imports init_llm.
model, tokenizer = initialize_llm()