import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from llama_index.core import Settings
# Import necessary types for the LLM abstract class
from llama_index.core.llms import LLM, CompletionResponse, CompletionResponseGen, ChatMessage, ChatResponse, ChatResponseGen, MessageRole
from typing import Sequence, Any
import asyncio
from pydantic import PrivateAttr # <-- Import PrivateAttr

class LLaMA3_1LLM(LLM):
    # Declare internal model and tokenizer as PrivateAttr.
    # This tells Pydantic that these are not part of the model's data fields
    # and should not be validated or serialized in the usual Pydantic way.
    _model: AutoModelForCausalLM = PrivateAttr()
    _tokenizer: AutoTokenizer = PrivateAttr()

    def __init__(self, model: AutoModelForCausalLM, tokenizer: AutoTokenizer, **kwargs: Any):
        # Always call the parent constructor first, passing any relevant kwargs.
        # This initializes the Pydantic BaseModel part of the LLM.
        super().__init__(**kwargs) 
        # Assign to the private attributes after the super().__init__() call.
        self._model = model
        self._tokenizer = tokenizer

    # You can optionally add properties to access them more cleanly,
    # or just use `self._model` and `self._tokenizer` directly in your methods.
    @property
    def model(self):
        return self._model

    @property
    def tokenizer(self):
        return self._tokenizer

    # Helper method to convert LlamaIndex messages to LLaMA 3.1 prompt format
    def _messages_to_prompt(self, messages: Sequence[ChatMessage]) -> str:
        hf_messages = []
        for message in messages:
            hf_messages.append({"role": message.role.value, "content": message.content})
        
        # Access the tokenizer via the property (or self._tokenizer directly)
        return self.tokenizer.apply_chat_template(hf_messages, tokenize=False, add_generation_prompt=True)

    # --- Synchronous Completion Methods (must be named 'complete') ---
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        # Access the tokenizer and model via the properties (or self._tokenizer, self._model directly)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device) # Ensure tensor is on correct device
        outputs = self.model.generate(**inputs, max_new_tokens=512, **kwargs)
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return CompletionResponse(text=text)

    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(**inputs, max_new_tokens=512, **kwargs)
        full_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
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