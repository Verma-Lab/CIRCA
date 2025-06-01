import os
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig # Added BitsAndBytesConfig
import torch
from llama_index.core import Settings
# Import necessary types for the LLM abstract class
from llama_index.core.llms import LLM, CompletionResponse, CompletionResponseGen, ChatMessage, ChatResponse, ChatResponseGen, MessageRole
from typing import Sequence, Any
import asyncio
from pydantic import PrivateAttr # <-- Import PrivateAttr
import logging # Added logging

# Set up logging for this module
logger = logging.getLogger(__name__)
# Ensure logging is configured to show INFO level messages if it's not done globally in main.py
# If main.py already has basicConfig, this might not be strictly necessary here,
# but it's good for standalone testing or if main.py only logs WARNING/ERROR.
# logging.basicConfig(level=logging.INFO) # This line might be redundant if main.py already calls it.

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
        
        # Log the device where the model is loaded
        if hasattr(self._model, 'device'):
            logger.info(f"LLaMA3_1LLM instance created. Model device: {self._model.device}")
        else:
            logger.info("LLaMA3_1LLM instance created. Model device attribute not found.")

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
            # LlamaIndex's ChatMessage.role maps directly to HuggingFace's expected role names
            # Ensure the role is converted to string for HuggingFace's template
            hf_messages.append({"role": message.role.value, "content": message.content})
        
        # Apply the tokenizer's chat template
        # add_generation_prompt=True ensures the final assistant turn is primed.
        # This is crucial for models like LLaMA-3.1 to generate a response correctly.
        return self.tokenizer.apply_chat_template(hf_messages, tokenize=False, add_generation_prompt=True)

    # --- Synchronous Completion Methods (must be named 'complete') ---
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        # Access the tokenizer and model via the properties (or self._tokenizer, self._model directly)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device) # Ensure tensor is on correct device
        logger.debug(f"Running synchronous complete on device: {self.model.device} for input tensors")
        outputs = self.model.generate(**inputs, max_new_tokens=512, **kwargs)
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return CompletionResponse(text=text)

    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        logger.debug(f"Running synchronous stream_complete on device: {self.model.device} for input tensors")
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
        # The challenge with async streaming from a sync `model.generate` is that `model.generate` is blocking.
        # The best way to handle this without complex producer-consumer queues is to run the *entire*
        # synchronous generator in a thread and then await its results.
        # However, `asyncio.to_thread` expects a callable returning a single value, not a generator directly
        # that it can iterate over asynchronously.
        # A simple approach for `_astream_complete` if `_stream_complete` produces chunks is to:
        
        # 1. Run the blocking `model.generate` operation in a thread to get the full text.
        # 2. Then, asynchronously yield character by character.
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
    logger.info("Starting LLM initialization...")
    model_path = "/home/hritvik/persistent/models/llama-3.1-8b"
         
    # Check if the model directory exists
    if not os.path.exists(model_path):
        logger.error(f"Model directory {model_path} does not exist. Please download the LLaMA 3.1 8B model first.")
        raise FileNotFoundError(f"Model directory {model_path} does not exist. Please download the LLaMA 3.1 8B model first.")
         
    # Add thorough CUDA checks here
    if torch.cuda.is_available():
        logger.info(f"CUDA is available! Detected {torch.cuda.device_count()} GPU(s).")
        if torch.cuda.device_count() > 0:
            logger.info(f"Current CUDA device: {torch.cuda.current_device()} ({torch.cuda.get_device_name(torch.cuda.current_device())})")
        logger.info(f"PyTorch CUDA version: {torch.version.cuda}")
    else:
        logger.warning("CUDA is NOT available. Model will likely load on CPU. Check NVIDIA drivers, CUDA Toolkit, and PyTorch installation.")
        # Optionally, you could exit or raise an error if GPU is mandatory
        # raise RuntimeError("GPU is required but CUDA is not available.")
    
    # Load tokenizer and model from local directory only
    try:
        logger.info(f"Loading tokenizer from {model_path}...")
        tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                local_files_only=True
            )
        
        logger.info(f"Loading model from {model_path} with device_map='auto' and torch_dtype=torch.float16...")
        
        # --- Optional: Quantization for smaller GPUs ---
        # If your GPU has less than ~16GB VRAM, you might need to enable 4-bit quantization.
        # Make sure you have `bitsandbytes` and `accelerate` installed:
        # pip install bitsandbytes accelerate
        # quantization_config = BitsAndBytesConfig(
        #     load_in_4bit=True,
        #     bnb_4bit_quant_type="nf4",
        #     bnb_4bit_compute_dtype=torch.float16,
        #     bnb_4bit_use_double_quant=True,
        # )
        
        model = AutoModelForCausalLM.from_pretrained(
                model_path,
                local_files_only=True,
                torch_dtype=torch.float16, # This is good for VRAM efficiency if enough VRAM
                device_map="auto", # This should put it on GPU if available and sufficient VRAM
                # quantization_config=quantization_config # Uncomment this if you need 4-bit quantization
            )
        logger.info(f"Model loaded successfully! Model is on device: {model.device}")
    except Exception as e:
        logger.critical(f"Failed to load model from {model_path}: {str(e)}", exc_info=True)
        raise RuntimeError(f"Failed to load model from {model_path}: {str(e)}")

    # Create and set the LLM instance
    llm = LLaMA3_1LLM(model, tokenizer)
    # This line correctly sets the LlamaIndex global LLM to your custom LLaMA 3.1 model.
    Settings.llm = llm
    logger.info("LLM initialization complete and set in LlamaIndex Settings.")

    return model, tokenizer

# # Initialize the LLM when the script is imported
# # This line will be executed when main.py imports init_llm.
# logger.info("Calling initialize_llm() at init_llm.py module import time.")
# model, tokenizer = initialize_llm()