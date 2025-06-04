from test import universal_extractor
import json
import os
import uuid
import requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import pytz
import tempfile
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends, Query, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
# Make sure to add this import at the top of the file with other imports
import aiohttp
import uvicorn
import shutil
import traceback
import nest_asyncio
# nest_asyncio.apply()

import pickle
from typing import Generator, AsyncGenerator # <--- ADD THIS LINE
from llama_index.llms.huggingface import HuggingFaceLLM
from llama_index.core.base.llms.types import LLMMetadata, ChatMessage, MessageRole # <--- CHANGED THIS LINE
from llama_index.core.llms import LLM, CompletionResponse, ChatResponse # <--- ADDED ChatResponse here

from llama_index.core.base.llms.types import LLMMetadata
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from google.cloud import storage
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import io
import base64
from weasyprint import HTML
import markdown
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from multiprocessing import cpu_count
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

import concurrent.futures
import re
import time
import hashlib

# Keep all existing imports
from llama_index.core import Document, VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core import StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings
import chromadb
from sentence_transformers import SentenceTransformer
from sentence_transformers.models import Transformer, Pooling
import faiss
import torch
import tqdm
import numpy as np
from transformers import AutoTokenizer, AutoModelForCausalLM, Gemma3ForConditionalGeneration, AutoProcessor, AutoModelForTokenClassification, pipeline
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter
from liquid import Template
from llama_index.llms.gemini import Gemini
from llama_index.llms.openai import OpenAI
from transformers import BitsAndBytesConfig
import logging
# from google import genai
# from google.genai import types
# nest_asyncio.apply()
from google.cloud import aiplatform
        
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")  # Replace with your actual key

HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-VL-32B-Instruct"
HUGGINGFACE_ACCESS_TOKEN = os.environ.get("HUGGINGFACE_ACCESS_TOKEN")
USE_LOCAL_MODEL = True  # Set to False to use Qwen API instead of local Gemma
LOCAL_MODEL_NAME = "google/gemma-3-4b-it"  # Smaller model that can run locally
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")  # Add your actual API key here
gemma_model = None
gemma_tokenizer = None
medical_ner_pipeline = None
MEDICAL_NER_MODEL = "Clinical-AI-Apollo/Medical-NER"


# Constants for medical literature retrieval
PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
PUBMED_FETCH_URL = f"{PUBMED_BASE_URL}efetch.fcgi"
PUBMED_SEARCH_URL = f"{PUBMED_BASE_URL}esearch.fcgi"
PUBMED_SUMMARY_URL = f"{PUBMED_BASE_URL}esummary.fcgi"
MEDICAL_LITERATURE_DIR = "./medical_literature"
MEDICAL_CORPUS_DIR = "./medical_corpus"
DIAGNOSIS_CORPUS_PATH = os.path.join(MEDICAL_CORPUS_DIR, "diagnosis")
RISK_CORPUS_PATH = os.path.join(MEDICAL_CORPUS_DIR, "risk_assessment")



# Create necessary directories
os.makedirs("reports", exist_ok=True)
os.makedirs("ehr_records", exist_ok=True)
os.makedirs("patients", exist_ok=True)
os.makedirs("encounters", exist_ok=True)
os.makedirs("lab_results", exist_ok=True)
os.makedirs("prescriptions", exist_ok=True)

# Initialize database
DATABASE_URL = "sqlite:///./ehr_database.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize GCS client - keep existing configuration
credentials_path = "vermalab-gemini-psom-e3ea-b93f97927cc3.json"  # Replace with your actual path
storage_client = storage.Client.from_service_account_json(credentials_path)
BUCKET_NAME = "circa-ai"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
# genai.configure(api_key=GOOGLE_API_KEY)
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# API Keys - keep existing configuration
XAI_API_KEY = "your-xai-api-key-here"
OPENAI_API_KEY = "your-openai-api-key-here"
os.environ["XAI_API_KEY"] = XAI_API_KEY
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
# Initialize Vertex AI client with your project and endpoint details
aiplatform.init(project="vermalab-gemini-psom-e3ea", location="us-central1")

# Define the endpoint
endpoint = aiplatform.Endpoint(endpoint_name="projects/vermalab-gemini-psom-e3ea/locations/us-central1/endpoints/365720657142480896")

# Custom class to wrap the Vertex AI endpoint as an LLM
# class VertexAIGemmaLLM(LLM): # <--- IMPORTANT: Inherit from LlamaIndex's LLM base class
#     endpoint: aiplatform.Endpoint = Field(exclude=True) # Declare 'endpoint' as a Pydantic field, exclude from serialization
#     model_name: str = Field(default="gemma-vertex-ai") # Declare 'model_name' as a Pydantic field

#     def __init__(self, endpoint: aiplatform.Endpoint, model_name: str = "gemma-vertex-ai", **kwargs: Any): # <--- MODIFIED: added **kwargs
#         # Pass all declared fields to the superclass's __init__
#         super().__init__(
#             endpoint=endpoint,
#             model_name=model_name,
#             **kwargs # Pass any other arguments to the parent LLM class
#         )

#     @property
#     def metadata(self) -> LLMMetadata:
#         """Get LLM metadata."""
#         return LLMMetadata(
#             model_name=self.model_name, # <--- CHANGE from self._model_name to self.model_name
#             is_chat_model=False,
#         )

#     def _get_params(self, **kwargs: Any) -> Dict[str, Any]:
#         """Extract and map common LLM parameters to Vertex AI's expected format."""
#         params = {}
#         # Vertex AI often uses 'max_output_tokens' instead of 'max_tokens'
#         if "max_tokens" in kwargs:
#             params["max_output_tokens"] = kwargs.pop("max_tokens")
#         elif "max_new_tokens" in kwargs: # Support common alternative
#             params["max_output_tokens"] = kwargs.pop("max_new_tokens")
#         if "temperature" in kwargs:
#             params["temperature"] = kwargs.pop("temperature")
#         if "top_k" in kwargs: # Top-k sampling
#             params["top_k"] = kwargs.pop("top_k")
#         if "top_p" in kwargs: # Top-p sampling
#             params["top_p"] = kwargs.pop("top_p")
#         # Add any other parameters your specific Vertex AI endpoint expects
#         # Example: 'candidate_count' for number of responses
#         return params

#     def _predict_raw(self, prompt: str, **kwargs: Any) -> str:
#         """Internal synchronous prediction method that interacts with Vertex AI endpoint."""
#         try:
#             # Prepare the request instances. The key for the prompt depends on the model's input signature.
#             # 'prompt' is common for text generation models.
#             instances = [{"prompt": prompt}]
            
#             # Extract and map parameters
#             parameters = self._get_params(**kwargs)

#             # Call the Vertex AI endpoint
#             response = self.endpoint.predict(instances=instances, parameters=parameters)

#             # Process the response from Vertex AI
#             prediction_data = response.predictions[0] if response.predictions else ""
            
#             # The structure of `response.predictions` can vary.
#             # It might be a string, or a dictionary with a 'text' or 'content' key.
#             if isinstance(prediction_data, dict):
#                 if "text" in prediction_data:
#                     prediction = prediction_data["text"]
#                 elif "content" in prediction_data: # Another common key
#                     prediction = prediction_data["content"]
#                 else:
#                     prediction = str(prediction_data) # Fallback to string conversion
#             elif isinstance(prediction_data, str):
#                 prediction = prediction_data
#             else:
#                 prediction = str(prediction_data) # General fallback if not string or dict

#             return prediction
#         except Exception as e:
#             logger.error(f"Error calling Vertex AI endpoint: {e}")
#             raise # Re-raise the exception to propagate it to LlamaIndex's error handling

#     async def _apredict_raw(self, prompt: str, **kwargs: Any) -> str:
#         """Internal asynchronous prediction method."""
#         # Use asyncio.to_thread to run the synchronous method in a thread pool.
#         # This is suitable if the underlying endpoint.predict is blocking.
#         return await asyncio.to_thread(self._predict_raw, prompt, **kwargs)

#     # LlamaIndex's LLM interface requires `complete` and `acomplete` for text completion.
#     def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
#         """LlamaIndex standard method for text completion."""
#         text = self._predict_raw(prompt, **kwargs)
#         return CompletionResponse(text=text)

#     async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
#         """LlamaIndex standard async method for text completion."""
#         text = await self._apredict_raw(prompt, **kwargs)
#         return CompletionResponse(text=text)
#     def _messages_to_prompt(self, messages: List[ChatMessage]) -> str:
#         """Converts a list of ChatMessage to a single string prompt for a completion model."""
#         prompt_parts = []
#         for message in messages:
#             if message.role == MessageRole.USER:
#                 prompt_parts.append(f"<start_of_turn>user\n{message.content}<end_of_turn>")
#             elif message.role == MessageRole.ASSISTANT:
#                 prompt_parts.append(f"<start_of_turn>model\n{message.content}<end_of_turn>")
#             elif message.role == MessageRole.SYSTEM:
#                 prompt_parts.append(f"<start_of_turn>system\n{message.content}<end_of_turn>")
#             # Add other roles if needed, or default to USER
#         prompt_parts.append(f"<start_of_turn>model\n") # This makes the model respond after the last turn
#         return "\n".join(prompt_parts)
#     # <--- ADD THE FOLLOWING METHOD:
#     def chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
#         """LlamaIndex standard method for chat completion."""
#         prompt = self._messages_to_prompt(messages)
#         response_text = self._predict_raw(prompt, **kwargs)
#         return ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
#     # <--- ADD THE FOLLOWING METHOD:
#     async def achat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
#         """LlamaIndex standard async method for chat completion."""
#         prompt = self._messages_to_prompt(messages)
#         response_text = await self._apredict_raw(prompt, **kwargs)
#         return ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
#     # <--- ADD THE FOLLOWING METHOD:
#     def stream_complete(self, prompt: str, **kwargs: Any) -> Generator[CompletionResponse, None, None]:
#         """LlamaIndex standard method for streaming text completion."""
#         # As Vertex AI endpoint might not stream, simulate by yielding full response.
#         text = self._predict_raw(prompt, **kwargs)
#         yield CompletionResponse(text=text, delta=text)
#     # <--- ADD THE FOLLOWING METHOD:
#     async def astream_complete(self, prompt: str, **kwargs: Any) -> AsyncGenerator[CompletionResponse, None]:
#         """LlamaIndex standard async method for streaming text completion."""
#         text = await self._apredict_raw(prompt, **kwargs)
#         yield CompletionResponse(text=text, delta=text)
#     # <--- ADD THE FOLLOWING METHOD:
#     def stream_chat(self, messages: List[ChatMessage], **kwargs: Any) -> Generator[ChatResponse, None, None]:
#         """LlamaIndex standard method for streaming chat completion."""
#         prompt = self._messages_to_prompt(messages)
#         response_text = self._predict_raw(prompt, **kwargs)
#         yield ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text),
#                            delta=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
#     # <--- ADD THE FOLLOWING METHOD:
#     async def astream_chat(self, messages: List[ChatMessage], **kwargs: Any) -> AsyncGenerator[ChatResponse, None]:
#         """LlamaIndex standard async method for streaming chat completion."""
#         prompt = self._messages_to_prompt(messages)
#         response_text = await self._apredict_raw(prompt, **kwargs)
#         yield ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text),
#                            delta=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
#     # <--- ADD THE FOLLOWING METHOD:
#     async def astream_chat(self, messages: List[ChatMessage], **kwargs: Any) -> AsyncGenerator[ChatResponse, None]:
#         """LlamaIndex standard async method for streaming chat completion."""
#         prompt = self._messages_to_prompt(messages)
#         response_text = await self._apredict_raw(prompt, **kwargs)
#         yield ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text),
#                            delta=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))

class VertexAIGemmaLLM(LLM): 
    endpoint: aiplatform.Endpoint = Field(exclude=True) # Declare 'endpoint' as a Pydantic field, exclude from serialization
    model_name: str = Field(default="gemma-vertex-ai") # Declare 'model_name' as a Pydantic field

    def __init__(self, endpoint: aiplatform.Endpoint, model_name: str = "gemma-vertex-ai", **kwargs: Any): # <--- MODIFIED: added **kwargs
        # Pass all declared fields to the superclass's __init__
        super().__init__(
            endpoint=endpoint,
            model_name=model_name,
            **kwargs # Pass any other arguments to the parent LLM class
        )

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(
            model_name=self.model_name, # <--- CHANGE from self._model_name to self.model_name
            is_chat_model=False,
        )

    def _detect_json_request(self, prompt: str) -> bool:
        """Detect if the prompt is asking for JSON output."""
        json_indicators = [
            "return the response as a json object",
            "return a json",
            "respond with json",
            "output json",
            "format: json",
            "return your analysis as a json object",
            "json format",
            "```json"
        ]
        prompt_lower = prompt.lower()
        return any(indicator in prompt_lower for indicator in json_indicators)

    def _get_params(self, **kwargs: Any) -> Dict[str, Any]:
        """Extract and map common LLM parameters to Vertex AI's expected format."""
        params = {}
        
        # Check if this is a JSON request from the prompt
        is_json_request = kwargs.pop("_is_json_request", False)
        
        # Vertex AI often uses 'max_output_tokens' instead of 'max_tokens'
        if "max_tokens" in kwargs:
            params["max_output_tokens"] = kwargs.pop("max_tokens")
        elif "max_new_tokens" in kwargs: # Support common alternative
            params["max_output_tokens"] = kwargs.pop("max_new_tokens")
        else:
            # Higher limit for JSON responses to avoid truncation
            params["max_output_tokens"] = 2048 if is_json_request else 1024
            
        # Temperature control
        if "temperature" in kwargs:
            params["temperature"] = kwargs.pop("temperature")
        else:
            params["temperature"] = 0.1  # Very low for deterministic outputs
            
        if "top_k" in kwargs: # Top-k sampling
            params["top_k"] = kwargs.pop("top_k")
        else:
            params["top_k"] = 10  # Restrictive top-k
            
        if "top_p" in kwargs: # Top-p sampling
            params["top_p"] = kwargs.pop("top_p")
        else:
            params["top_p"] = 0.8  # More restrictive top-p
            
        # Add stop sequences - but be careful with JSON requests
        if "stop_sequences" in kwargs:
            params["stop_sequences"] = kwargs.pop("stop_sequences")
        elif not is_json_request:
            # Only use aggressive stop sequences for non-JSON requests
            params["stop_sequences"] = [
                "\n\n\n",
                "<end>",
                "</end>",
                "User:",
                "Human:",
                "Assistant:",
                "<start_of_turn>",
                "IMPORTANT:",
                "Instructions:",
                "CRITICAL:"
            ]
        else:
            # For JSON requests, use minimal stop sequences to avoid cutting off the response
            params["stop_sequences"] = [
                "\n\n\n\n",  # 4 newlines instead of 3
                "<start_of_turn>user",  # Only stop at next user turn
            ]
            
        return params

    def _clean_response(self, text: str, original_prompt: str, is_json_request: bool = False) -> str:
        """Clean the response, with special handling for JSON."""
        if not text:
            return text
        
        # For JSON requests, try to extract and fix JSON first
        if is_json_request:
            # Try to find JSON content
            json_start = text.find('{')
            json_end = text.rfind('}')
            
            if json_start != -1:
                if json_end == -1 or json_end < json_start:
                    # JSON is incomplete, try to complete it
                    json_content = text[json_start:]
                    
                    # Count open braces and try to close them
                    open_braces = json_content.count('{') - json_content.count('}')
                    if open_braces > 0:
                        # Check if we're in the middle of a string
                        if json_content.rstrip().endswith('"node'):
                            json_content = json_content + '_1"'  # Complete the node ID
                        
                        # Add missing closing braces
                        json_content += '}' * open_braces
                        
                    return json_content.strip()
                else:
                    # Extract the JSON portion
                    return text[json_start:json_end+1].strip()
        
        # For non-JSON, use the original cleaning logic
        # First, try to extract content after known output markers
        output_markers = [
            "Output:",
            "Response:",
            "Translation:",
            "Answer:",
            "Result:",
            "ISO code:",
            "Language code:",
            # Model turn markers
            "<start_of_turn>model",
            "<end_of_turn>",
        ]
        
        # Find the last occurrence of any output marker
        last_marker_pos = -1
        marker_used = None
        for marker in output_markers:
            pos = text.rfind(marker)
            if pos > last_marker_pos:
                last_marker_pos = pos
                marker_used = marker
        
        if last_marker_pos != -1:
            # Extract content after the marker
            text = text[last_marker_pos + len(marker_used):].strip()
            
            # Find where the actual output ends
            end_markers = [
                "\n\n\n",
                "IMPORTANT:",
                "Instructions:",
                "User message:",
                "Patient Profile",
                "Original Response",
                "<start_of_turn>",
                "NOTE:",
                "CRITICAL:",
                "MUST Format"
            ]
            
            end_pos = len(text)
            for end_marker in end_markers:
                pos = text.find(end_marker)
                if pos != -1 and pos < end_pos:
                    end_pos = pos
            
            text = text[:end_pos].strip()
        
        # Remove any remaining prompt echo at the beginning
        prompt_indicators = [
            "Translate the following",
            "Detect the language",
            "Return ONLY",
            "IMPORTANT:",
            "Task:",
            "Input:",
            "Prompt:",
            "Question:",
            "Instruction:",
            "You are",
            "I need to",
            "Format your response"
        ]
        
        lines = text.split('\n')
        start_line = 0
        for i, line in enumerate(lines):
            if any(indicator in line for indicator in prompt_indicators):
                start_line = i + 1
        
        if start_line > 0 and start_line < len(lines):
            text = '\n'.join(lines[start_line:]).strip()
        
        # Clean up quotes if the entire response is quoted
        if len(text) > 2 and text[0] == text[-1] and text[0] in ['"', "'"]:
            text = text[1:-1]
        
        return text.strip()

    def _format_prompt_for_gemma(self, prompt: str, is_json_request: bool = False) -> str:
        """Format the prompt to maximize Gemma's instruction following."""
        if is_json_request:
            # Special formatting for JSON requests
            formatted_prompt = f"""<start_of_turn>user
            {prompt}

            CRITICAL: Output ONLY valid JSON. Start your response with {{ and end with }}.
            <end_of_turn>
            <start_of_turn>model"""
        else:
                # Standard formatting for other requests
                formatted_prompt = f"""<start_of_turn>user
    {prompt}

    Provide your response below. Output ONLY what was requested, nothing else.
    <end_of_turn>
    <start_of_turn>model
    Output:"""
            
        return formatted_prompt

    def _predict_raw(self, prompt: str, **kwargs: Any) -> str:
        """Internal synchronous prediction method that interacts with Vertex AI endpoint."""
        try:
            # Store original prompt for cleaning
            original_prompt = prompt
            
            # Detect if this is a JSON request
            is_json_request = self._detect_json_request(prompt)
            
            # Format prompt for Gemma
            formatted_prompt = self._format_prompt_for_gemma(prompt, is_json_request)
            
            # Prepare the request instances
            instances = [{"prompt": formatted_prompt}]
            
            # Get parameters with JSON awareness
            kwargs["_is_json_request"] = is_json_request
            parameters = self._get_params(**kwargs)
            
            # Log for debugging
            logger.debug(f"Is JSON request: {is_json_request}")
            logger.debug(f"Formatted prompt: {formatted_prompt[:200]}...")
            logger.debug(f"Parameters: {parameters}")

            # Call the Vertex AI endpoint
            response = self.endpoint.predict(instances=instances, parameters=parameters)

            # Process the response from Vertex AI
            prediction_data = response.predictions[0] if response.predictions else ""
            
            # Extract text from response
            if isinstance(prediction_data, dict):
                if "text" in prediction_data:
                    prediction = prediction_data["text"]
                elif "content" in prediction_data:
                    prediction = prediction_data["content"]
                else:
                    prediction = str(prediction_data)
            elif isinstance(prediction_data, str):
                prediction = prediction_data
            else:
                prediction = str(prediction_data)

            # Log raw response for debugging
            logger.debug(f"Raw prediction: {prediction[:500]}...")

            # Clean the response with JSON awareness
            cleaned_prediction = self._clean_response(prediction, original_prompt, is_json_request)
            
            # For JSON requests, validate and fix if needed
            if is_json_request and cleaned_prediction:
                try:
                    # Try to parse to validate
                    import json
                    json.loads(cleaned_prediction)
                except json.JSONDecodeError as e:
                    logger.debug(f"JSON validation failed: {e}")
                    # Try one more aggressive fix
                    if '"next_node_id"' in cleaned_prediction and cleaned_prediction.count('"') % 2 != 0:
                        # Odd number of quotes, likely missing closing quote
                        cleaned_prediction = cleaned_prediction.rstrip() + '"}'
            
            logger.debug(f"Cleaned prediction: {cleaned_prediction[:200]}...")
            
            return cleaned_prediction
            
        except Exception as e:
            logger.error(f"Error calling Vertex AI endpoint: {e}")
            raise

    async def _apredict_raw(self, prompt: str, **kwargs: Any) -> str:
        """Internal asynchronous prediction method."""
        # Use asyncio.to_thread to run the synchronous method in a thread pool.
        # This is suitable if the underlying endpoint.predict is blocking.
        return await asyncio.to_thread(self._predict_raw, prompt, **kwargs)

    # LlamaIndex's LLM interface requires `complete` and `acomplete` for text completion.
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """LlamaIndex standard method for text completion."""
        text = self._predict_raw(prompt, **kwargs)
        return CompletionResponse(text=text)

    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """LlamaIndex standard async method for text completion."""
        text = await self._apredict_raw(prompt, **kwargs)
        return CompletionResponse(text=text)
        
    def _messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """Converts a list of ChatMessage to a single string prompt for a completion model."""
        prompt_parts = []
        
        # Process messages
        for message in messages:
            if message.role == MessageRole.USER:
                prompt_parts.append(f"<start_of_turn>user\n{message.content}<end_of_turn>")
            elif message.role == MessageRole.ASSISTANT:
                prompt_parts.append(f"<start_of_turn>model\n{message.content}<end_of_turn>")
            elif message.role == MessageRole.SYSTEM:
                # Put system message at the beginning with clear instructions
                system_content = f"System: {message.content}\nFollow the system instructions carefully and provide only the requested output."
                prompt_parts.insert(0, f"<start_of_turn>system\n{system_content}<end_of_turn>")
        
        # Add model turn with output instruction
        prompt_parts.append("<start_of_turn>model\nOutput:")
        
        return "\n".join(prompt_parts)
        
    # <--- ADD THE FOLLOWING METHOD:
    def chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
        """LlamaIndex standard method for chat completion."""
        prompt = self._messages_to_prompt(messages)
        response_text = self._predict_raw(prompt, **kwargs)
        return ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
        
    # <--- ADD THE FOLLOWING METHOD:
    async def achat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
        """LlamaIndex standard async method for chat completion."""
        prompt = self._messages_to_prompt(messages)
        response_text = await self._apredict_raw(prompt, **kwargs)
        return ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
        
    # <--- ADD THE FOLLOWING METHOD:
    def stream_complete(self, prompt: str, **kwargs: Any) -> Generator[CompletionResponse, None, None]:
        """LlamaIndex standard method for streaming text completion."""
        # As Vertex AI endpoint might not stream, simulate by yielding full response.
        text = self._predict_raw(prompt, **kwargs)
        yield CompletionResponse(text=text, delta=text)
        
    # <--- ADD THE FOLLOWING METHOD:
    async def astream_complete(self, prompt: str, **kwargs: Any) -> AsyncGenerator[CompletionResponse, None]:
        """LlamaIndex standard async method for streaming text completion."""
        text = await self._apredict_raw(prompt, **kwargs)
        yield CompletionResponse(text=text, delta=text)
        
    # <--- ADD THE FOLLOWING METHOD:
    def stream_chat(self, messages: List[ChatMessage], **kwargs: Any) -> Generator[ChatResponse, None, None]:
        """LlamaIndex standard method for streaming chat completion."""
        prompt = self._messages_to_prompt(messages)
        response_text = self._predict_raw(prompt, **kwargs)
        yield ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text),
                           delta=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
                           
    # <--- ADD THE FOLLOWING METHOD:
    async def astream_chat(self, messages: List[ChatMessage], **kwargs: Any) -> AsyncGenerator[ChatResponse, None]:
        """LlamaIndex standard async method for streaming chat completion."""
        prompt = self._messages_to_prompt(messages)
        response_text = await self._apredict_raw(prompt, **kwargs)
        yield ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text),
                           delta=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))

# Setting LLMs - keep existing configuration
llm = Gemini(
    model="models/gemini-2.0-flash",
    api_key=GOOGLE_API_KEY,  
)
MODEL_ID = "models/gemini-2.0-flash"  # Latest version as of May 2025
# vecto_chat = genai.GenerativeModel(MODEL_ID)
gemini_model = Gemini(
    model=MODEL_ID,  # Add the "models/" prefix
    api_key=GOOGLE_API_KEY,
    # Optional: Configure "thinking" capabilities 
    thinking_config={"thinking_budget": 8000}  # Adjust as needed
)

openai_llm = OpenAI(model="gpt-3.5-turbo", api_key=OPENAI_API_KEY, logprobs=False, default_headers={})
LLM_MODELS = {
    "Gemini-Pro": llm,
    "Chat Gpt o3-mini": openai_llm,
}

Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
# # Settings.llm = llm
qwen_model = VertexAIGemmaLLM(endpoint)
Settings.llm = qwen_model
# Settings.llm = gemma_llm
test_prompt = "Hello, this is a test prompt. Please respond with a short message."
response = qwen_model.complete(test_prompt)
print(f"Test response: {response.text}")
def test_qwen_configuration():
    """Test function to verify Gemma behaves like Gemini"""
    test_cases = [
        "Translate 'Hello' to Spanish:",
        "Detect the language of this text: 'Bonjour'",
        "What is 2+2?",
    ]
    
    print("Testing Gemma configuration:")
    for i, test_prompt in enumerate(test_cases, 1):
        try:
            response = qwen_model.complete(test_prompt)
            print(f"Test {i}: '{test_prompt}' -> '{response.text}'")
        except Exception as e:
            print(f"Test {i} failed: {e}")

test_qwen_configuration()
# MODEL_PATH = "/home/hritvik/persistent/models/llama-3.1-8b"
# if not torch.cuda.is_available():
#     logger.error("CUDA not available. Cannot proceed without GPU.")
#     raise RuntimeError("CUDA not available. Check GPU setup.")
# logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}") # This line is now correctly showing Tesla T4!

# # Initialize the tokenizer
# try:
#     tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
# except Exception as e:
#     logger.error(f"Failed to load tokenizer: {e}")
#     raise

# # Initialize HuggingFaceLLM for Llama 3.1 8B
# quantization_config = BitsAndBytesConfig(
#     load_in_4bit=True,
#     bnb_4bit_quant_type="nf4", # Recommended 4-bit quantization type
#     bnb_4bit_compute_dtype=torch.bfloat16, # Keep computation in bfloat16 for speed if GPU supports it
#     bnb_4bit_use_double_quant=False, # Usually not needed
# )

# try:
#     llama_llm = HuggingFaceLLM(
#     model_name=MODEL_PATH,
#     tokenizer_name=MODEL_PATH,
#     device_map="auto",
#     model_kwargs={
#         "torch_dtype": torch.bfloat16,
#         "quantization_config": quantization_config,
#     },
#     tokenizer_kwargs={"padding_side": "left"},
#     max_new_tokens=50,  # MUCH SMALLER
#     generate_kwargs={
#         "temperature": 0.1, 
#         "do_sample": True,
#         "pad_token_id": tokenizer.eos_token_id,  # ADD THIS
#         "eos_token_id": tokenizer.eos_token_id,  # ADD THIS
#         "repetition_penalty": 1.2,  # STOP REPETITION
#     },
# )
#     logger.info("Llama 3.1 8B loaded successfully on GPU (quantized)")
# except Exception as e:
#     logger.error(f"Failed to load Llama model: {e}")
#     raise


# test_prompt = "Hello, this is a test prompt. Please respond with a short message."
# response = llama_llm.complete(test_prompt)
# print(f"Test response: {response.text}")

# logger.info("Loading Gemma model locally...")
# gemma_tokenizer = AutoTokenizer.from_pretrained(
#     LOCAL_MODEL_NAME,
#     token=HUGGINGFACE_ACCESS_TOKEN
# )
# gemma_model = Gemma3ForConditionalGeneration.from_pretrained(
#     LOCAL_MODEL_NAME,
#     device_map="auto",
#     torch_dtype=torch.bfloat16,
#     quantization_config=quantization_config,
#     token=HUGGINGFACE_ACCESS_TOKEN,
#     low_cpu_mem_usage=True,
# ).eval()
# logger.info("Gemma 3 4B model loaded successfully!")

# # Wrap in HuggingFaceLLM for LlamaIndex
# gemma_llm = HuggingFaceLLM(
#     model_name=LOCAL_MODEL_NAME,
#     model=gemma_model,
#     tokenizer=gemma_tokenizer,
#     max_new_tokens=200,
#     generate_kwargs={
#         "do_sample": True,      # Stop being a predictable asshole
#         "temperature": 0.7,     # Add some goddamn personality
#         "repetition_penalty": 1.2,  # Quit repeating shit
#         "top_p": 0.9,           # Keep it sensible, motherfucker
#         "top_k": 50,            # Don’t pull random crap
#     }
# )

# Set to Settings.llm
# Settings.llm = gemma_llm
# logger.info("Gemma 3 4B set to Settings.llm successfully!")

# Test model
# start_time = time.time()
# test_prompt = "Translate 'Hello' to Spanish."
# response = gemma_llm.complete(test_prompt)
# logger.info(f"Test response: {response.text}, Time: {time.time() - start_time:.2f} seconds")

# Settings.llm = llama_llm
# Chroma Client - keep existing configuration
chroma_client = chromadb.PersistentClient(path="./chroma_data")

# FastAPI App Setup
app = FastAPI(title="Professional EHR and MedRAG Analysis System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Authentication components
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Global Storage - keep existing configuration
index_storage: Dict[str, Any] = {}
processing_status: Dict[str, Dict[str, Any]] = {}
index_metadata: Dict[str, Dict[str, Any]] = {}
document_index_mapping: Dict[str, str] = {}

# Add new prompt templates for different analysis types
diagnosis_system_prompt = '''You are a clinical diagnostician. Based on the following patient data, relevant medical literature, and web-sourced information, provide a thorough differential diagnosis. Consider the patient's symptoms, medical history, vital signs, lab results, imaging findings, and identified medical entities. Return your response as a JSON formatted string with: 1) "primary_diagnosis" (most likely diagnosis), 2) "differential_diagnoses" (list of other possible diagnoses with brief explanations), 3) "reasoning" (detailed explanation for the primary diagnosis), and 4) "confidence" (percentage estimate for the primary diagnosis).
Patient Data:
{{patient_data}}
Relevant Medical Information:
{{context}}
'''

risk_assessment_system_prompt = '''You are a clinical risk assessment specialist. Based on the following patient data, relevant medical literature, and web-sourced information, provide a comprehensive risk assessment. Evaluate the patient's risk factors for cardiovascular disease, stroke, diabetes complications, and other relevant conditions based on their clinical presentation. Return your response as a JSON formatted string with: 1) "risk_areas" (list of risk categories and their levels: high, moderate, low), 2) "risk_factors" (specific factors contributing to risk), 3) "mitigation_strategies" (recommended interventions), and 4) "follow_up_recommendations" (suggested monitoring and follow-up timeline).
Patient Data:
{{patient_data}}
Relevant Medical Information:
{{context}}
'''
# MedRAG Templates - keep existing configuration
general_cot_system = '''You are a helpful medical expert, and your task is to answer a multi-choice medical question. Please first think step-by-step and then choose the answer from the provided options. Organize your output in a json formatted as Dict{"step_by_step_thinking": Str(explanation), "answer_choice": Str{A/B/C/...}}. Your responses will be used for research purposes only, so please have a definite answer.'''
general_cot = Template(''' Here is the question: {{question}}
Here are the potential choices: {{options}}
Please think step-by-step and generate your output in json: ''')
general_medrag_system = '''You are a helpful medical expert, and your task is to analyze patient data using relevant medical documents. Please think step-by-step and provide a recommendation on whether genetic testing is needed for a potential rare disease. Organize your output in a JSON formatted string with "testing_recommendation" ("recommended" or "not recommended"), "reasoning" (detailed explanation), and "confidence" (percentage estimate).'''
general_medrag = Template(''' Here is the patient's clinical note: {{question}}
Here are relevant medical literatures you can use to assess whether the patient needs genetic testing: {{context}}
Please think step-by-step and generate your output in json with recommendation, reasoning, and confidence: ''')

ehr_system_prompt = '''You are a clinical expert on rare genetic diseases. Based on the following patient data and relevant medical literature, determine if the patient needs genetic testing for a potential undiagnosed rare genetic disease (e.g., Marfan syndrome) or syndrome based on their past and present symptoms and medical history. Provide your reasoning and an estimated confidence level (percentage) that the patient might be suffering from a specific disease. Return your response as a JSON formatted string with three parts: 1) "testing_recommendation" ("recommended" or "not recommended"), 2) "reasoning" (detailed explanation based on clinical summary and literature), and 3) "confidence" (e.g., "80%") indicating the likelihood of the identified condition.
Patient Data:
{{patient_data}}
Relevant Medical Literature:
{{context}}
'''
ehr_prompt = Template(ehr_system_prompt)
diagnosis_prompt = Template(diagnosis_system_prompt)
risk_assessment_prompt = Template(risk_assessment_system_prompt)

# Corpus and retriever configurations - keep existing configuration
corpus_names = {
    "Marfan": ["marfan"]
}

retriever_names = {
    "BM25": ["bm25"],
    "Contriever": ["facebook/contriever"],
    "SPECTER": ["allenai/specter"],
    "MedCPT": ["ncbi/MedCPT-Query-Encoder"],
    "RRF-2": ["bm25", "ncbi/MedCPT-Query-Encoder"],
    "RRF-4": ["bm25", "facebook/contriever", "allenai/specter", "ncbi/MedCPT-Query-Encoder"]
}

# Database models for new EHR components
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_doctor = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    telephone_ai_token = Column(String, nullable=True)
    telephone_ai_user_id = Column(String, nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    role = Column(String, default="staff")  # e.g., "doctor", "administrator", "staff"

class UserPatientAccess(Base):
    __tablename__ = "user_patient_access"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    patient_id = Column(String, ForeignKey("patients.id"), index=True)
    access_level = Column(String)  # "read", "write", "admin"
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, ForeignKey("users.id"))
    access_level = Column(String)  # "read", "write", "admin"

    

class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(String, primary_key=True, index=True)
    mrn = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    date_of_birth = Column(String)
    gender = Column(String)
    address = Column(String)
    phone = Column(String)
    email = Column(String)
    insurance_provider = Column(String)
    insurance_id = Column(String)
    primary_care_provider = Column(String)
    emergency_contact_name = Column(String)
    emergency_contact_phone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)

class Encounter(Base):
    __tablename__ = "encounters"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    provider_id = Column(String, ForeignKey("users.id"))
    encounter_date = Column(DateTime, default=datetime.utcnow)
    encounter_type = Column(String)  # e.g., "Office Visit", "Telehealth", "Emergency"
    chief_complaint = Column(String)
    vital_signs = Column(String, default="{}")  # Store as JSON string
    hpi = Column(String)  # History of Present Illness
    ros = Column(String)  # Review of Systems
    physical_exam = Column(String)
    assessment = Column(String)
    plan = Column(String)
    diagnosis_codes = Column(String)  # ICD-10 codes
    followup_instructions = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MedicalHistory(Base):
    __tablename__ = "medical_histories"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    condition = Column(String)
    onset_date = Column(String)
    status = Column(String)  # "Active", "Resolved", "Chronic"
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FamilyHistory(Base):
    __tablename__ = "family_histories"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    relation = Column(String)  # e.g., "Mother", "Father", "Sibling"
    condition = Column(String)
    onset_age = Column(Integer, nullable=True)
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Medication(Base):
    __tablename__ = "medications"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    name = Column(String)
    dosage = Column(String)
    frequency = Column(String)
    route = Column(String)  # e.g., "Oral", "IV", "Topical"
    start_date = Column(String)
    end_date = Column(String, nullable=True)
    prescriber_id = Column(String, ForeignKey("users.id"))
    indication = Column(String)
    pharmacy_notes = Column(String)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Allergy(Base):
    __tablename__ = "allergies"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    allergen = Column(String)
    reaction = Column(String)
    severity = Column(String)  # "Mild", "Moderate", "Severe"
    onset_date = Column(String)
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LabOrder(Base):
    __tablename__ = "lab_orders"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    provider_id = Column(String, ForeignKey("users.id"))
    order_date = Column(DateTime, default=datetime.utcnow)
    test_name = Column(String)
    test_code = Column(String)
    collection_date = Column(DateTime, nullable=True)
    priority = Column(String, default="Routine")  # "Routine", "STAT", "Urgent"
    status = Column(String, default="Ordered")  # "Ordered", "Collected", "In Progress", "Completed", "Cancelled"
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LabResult(Base):
    __tablename__ = "lab_results"
    
    id = Column(String, primary_key=True, index=True)
    lab_order_id = Column(String, ForeignKey("lab_orders.id"))
    result_date = Column(DateTime, default=datetime.utcnow)
    result_value = Column(String)
    unit = Column(String)
    reference_range = Column(String)
    abnormal_flag = Column(String, nullable=True)  # "High", "Low", "Normal"
    performing_lab = Column(String)
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    encounter_id = Column(String, ForeignKey("encounters.id"), nullable=True)
    analysis_type = Column(String)  # e.g., "Genetic Testing", "Diagnosis Suggestion", "Risk Assessment"
    recommendation = Column(String)
    reasoning = Column(String)
    confidence = Column(String)
    model_used = Column(String)
    analysis_date = Column(DateTime, default=datetime.utcnow)
    reviewed_by_provider = Column(Boolean, default=False)
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=True)
    review_notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class PatientScan(Base):
    __tablename__ = "patient_scans"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    provider_id = Column(String, ForeignKey("users.id"), nullable=True)
    scan_type = Column(String)  # e.g., "X-ray", "ECG", "EKG", "Chest Scan"
    scan_date = Column(DateTime, default=datetime.utcnow)
    description = Column(String)
    file_name = Column(String)
    file_size = Column(Integer)
    storage_url = Column(String)  # GCS URL
    content_type = Column(String)  # MIME type
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MedicalCode(Base):
    __tablename__ = "medical_codes"
    
    id = Column(String, primary_key=True, index=True)
    code = Column(String, index=True)
    type = Column(String)  # "ICD-10" or "CPT"
    description = Column(String)
    category = Column(String)  # For grouping related codes
    common_terms = Column(String)  # Store as JSON string with terms that map to this code
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AutocodeRequest(BaseModel):
    encounter_id: str
    use_llm: bool = True
    update_encounter: bool = False

class AutocodeResponse(BaseModel):
    encounter_id: str
    icd10_codes: List[Dict[str, str]]
    cpt_codes: List[Dict[str, str]]
    formatted_icd10: str
    formatted_cpt: str
    entity_matches: List[str]
    reasoning: Optional[str] = None
    updated: bool = False

class PatientInsights(Base):
    __tablename__ = "patient_insights"
    
    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    insight_type = Column(String)  # "lifestyle", "medication", "screening", "risk"
    insight_text = Column(String)
    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Survey(Base):
    __tablename__ = "surveys"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    questions_count = Column(Integer, default=0)
    responses_count = Column(Integer, default=0)
    organization_id = Column(String, ForeignKey("organizations.id"))
    created_by = Column(String, ForeignKey("users.id"))

class SurveyQuestion(Base):
    __tablename__ = "survey_questions"
    
    id = Column(String, primary_key=True, index=True)
    survey_id = Column(String, ForeignKey("surveys.id"))
    text = Column(String)
    type = Column(String)
    options = Column(String)  # Stored as JSON string
    order = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SurveyCreate(BaseModel):
    title: str
    description: str
    category: str
    questions: List[dict] = []

class SurveyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    questions: Optional[List[dict]] = None  # This needs to accept a list of questions



class QuestionCreate(BaseModel):
    text: str
    type: str
    options: List[str] = []

# class SessionAnalytics(Base):
#     __tablename__ = "session_analytics"
    
#     id = Column(String, primary_key=True, index=True)
#     session_id = Column(String, index=True)
#     timestamp = Column(DateTime, default=datetime.utcnow)
#     message_text = Column(String)  # User's message
#     assistant_response = Column(String)  # AI's response
#     sentiment = Column(String)  # Positive, Negative, Neutral
#     urgency = Column(String)  # High, Medium, Low
#     intent = Column(String)  # User's intent classification
#     topic = Column(String)  # Topic of conversation
#     keywords = Column(String)  # Extracted keywords as JSON
#     session_duration = Column(Integer)  # Duration in seconds
#     word_count = Column(Integer)  # Word count in message
#     response_time = Column(Integer)  # Time to generate response in ms
#     created_at = Column(DateTime, default=datetime.utcnow)
    
class SessionAnalytics(Base):
    __tablename__ = "session_analytics"
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    message_text = Column(String)  # User's message
    assistant_response = Column(String)  # AI's response
    sentiment = Column(String)  # Positive, Negative, Neutral
    urgency = Column(String)  # High, Medium, Low
    intent = Column(String)  # User's intent classification
    topic = Column(String)  # Topic of conversation
    keywords = Column(String)  # Extracted keywords as JSON
    session_duration = Column(Integer)  # Duration in seconds
    word_count = Column(Integer)  # Word count in message
    response_time = Column(Integer)  # Time to generate response in ms
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # New columns for pregnancy-specific analytics
    medical_data = Column(String)  # JSON string for dates, symptoms, measurements
    pregnancy_specific = Column(String)  # JSON string for trimester, risk factors
    emotional_state = Column(String)  # More detailed emotional analysis

# Create all database tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication helpers
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    print(f"DEBUG: Processing token in get_current_user")
    print(f"DEBUG: Token: {token[:20]}...")  # Print just the beginning for security
    
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"PayLoad",payload)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# def user_has_patient_access(db: Session, user_id: str, patient_id: str, required_level: str = "read"):
#     """Check if a user has the required access level to a patient."""
#     # Admins and doctors have access to all patients
#     user = db.query(User).filter(User.id == user_id).first()
    
#     if user and user.is_doctor:
#         return True
        
#     # Check explicit access records
#     access = db.query(UserPatientAccess).filter(
#         UserPatientAccess.user_id == user_id,
#         UserPatientAccess.patient_id == patient_id
#     ).first()
    
#     if not access:
#         return False
        
#     # Check access level
#     if required_level == "read":
#         return access.access_level in ["read", "write", "admin"]
#     elif required_level == "write":
#         return access.access_level in ["write", "admin"]
#     elif required_level == "admin":
#         return access.access_level == "admin"
    
#     return False
class OrganizationCreate(BaseModel):
    name: str
@app.post("/api/organizations", response_model=dict)
async def create_organization(org: OrganizationCreate, db: Session = Depends(get_db)):
    # Check if organization already exists
    existing_org = db.query(Organization).filter(Organization.name == org.name).first()
    if existing_org:
        raise HTTPException(status_code=400, detail="Organization already exists")
    
    db_org = Organization(
        id=str(uuid.uuid4()),
        name=org.name,
        created_at=datetime.utcnow()
    )
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    return {"id": db_org.id, "name": db_org.name}


@app.get("/api/organizations", response_model=List[dict])
async def get_organizations(db: Session = Depends(get_db)):
    orgs = db.query(Organization).all()
    return [{"id": org.id, "name": org.name} for org in orgs]

def user_has_patient_access(db: Session, user_id: str, patient_id: str, required_level: str = "read"):
    user = db.query(User).filter(User.id == user_id).first()
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    
    if not user or not patient:
        return False
    
    # Check organization match first
    if user.organization_id != patient.organization_id:
        return False
    
    # Doctors have access to all patients in their organization
    if user.role == "doctor":
        return True
    
    # Check explicit access for non-doctors
    access = db.query(UserPatientAccess).filter(
        UserPatientAccess.user_id == user_id,
        UserPatientAccess.patient_id == patient_id
    ).first()
    
    if not access:
        return False
    
    access_levels = {"read": ["read", "write", "admin"], "write": ["write", "admin"], "admin": ["admin"]}
    return access.access_level in access_levels.get(required_level, [])


# Keep the CustomizeSentenceTransformer class
class CustomizeSentenceTransformer(SentenceTransformer):
    def _load_auto_model(self, model_name_or_path, *args, **kwargs):
        print("No sentence-transformers model found with name {}. Creating a new one with CLS pooling.".format(model_name_or_path))
        token = kwargs.get('token', None)
        cache_folder = kwargs.get('cache_folder', None)
        revision = kwargs.get('revision', None)
        trust_remote_code = kwargs.get('trust_remote_code', False)
        transformer_model = Transformer(
            model_name_or_path,
            cache_dir=cache_folder,
            model_args={"token": token, "trust_remote_code": trust_remote_code, "revision": revision},
            tokenizer_args={"token": token, "trust_remote_code": trust_remote_code, "revision": revision},
        )
        pooling_model = Pooling(transformer_model.get_word_embedding_dimension(), 'cls')
        return [transformer_model, pooling_model]

# Keep all existing MedRAG functions
def embed(chunk_dir, index_dir, model_name, **kwargs):
    print(f"[EMBEDDING] Starting embedding process with model {model_name}")
    save_dir = os.path.join(index_dir, "embedding")
    if "contriever" in model_name:
        model = SentenceTransformer(model_name, device="cuda" if torch.cuda.is_available() else "cpu")
        print(f"[EMBEDDING] Using contriever model: {model_name} on {'cuda' if torch.cuda.is_available() else 'cpu'}")
    else:
        model = CustomizeSentenceTransformer(model_name, device="cuda" if torch.cuda.is_available() else "cpu")
        print(f"[EMBEDDING] Using custom transformer model: {model_name} on {'cuda' if torch.cuda.is_available() else 'cpu'}")
    model.eval()
    fnames = sorted([fname for fname in os.listdir(chunk_dir) if fname.endswith(".jsonl")])
    print(f"[EMBEDDING] Found {len(fnames)} JSONL files to process")
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        print(f"[EMBEDDING] Created directory: {save_dir}")
    with torch.no_grad():
        for fname in tqdm.tqdm(fnames):
            fpath = os.path.join(chunk_dir, fname)
            save_path = os.path.join(save_dir, fname.replace(".jsonl", ".npy"))
            if os.path.exists(save_path):
                print(f"[EMBEDDING] Skipping {fname} as embedding already exists")
                continue
            if not open(fpath).read().strip():
                print(f"[EMBEDDING] Skipping {fname} as file is empty")
                continue
            texts = [json.loads(item)["contents"] for item in open(fpath).read().strip().split('\n')]
            print(f"[EMBEDDING] Processing {fname} with {len(texts)} text chunks")
            embed_chunks = model.encode(texts, **kwargs)
            np.save(save_path, embed_chunks)
            print(f"[EMBEDDING] Saved embeddings to {save_path}")
        embed_chunks = model.encode([""], **kwargs)
    print(f"[EMBEDDING] Completed embedding process, dimension: {embed_chunks.shape[-1]}")
    return embed_chunks.shape[-1]

def construct_index(index_dir, model_name, h_dim=768):
    print(f"[INDEX] Constructing index for {model_name} with dimension {h_dim}")
    with open(os.path.join(index_dir, "metadatas.jsonl"), 'w') as f:
        f.write("")
    if "specter" in model_name.lower():
        index = faiss.IndexFlatL2(h_dim)
        print(f"[INDEX] Using L2 index for SPECTER")
    else:
        index = faiss.IndexFlatIP(h_dim)
        print(f"[INDEX] Using IP index for {model_name}")
    for fname in tqdm.tqdm(sorted(os.listdir(os.path.join(index_dir, "embedding")))):
        print(f"[INDEX] Processing {fname}")
        curr_embed = np.load(os.path.join(index_dir, "embedding", fname))
        print(f"[INDEX] Loaded embedding of shape {curr_embed.shape}")
        index.add(curr_embed)
        with open(os.path.join(index_dir, "metadatas.jsonl"), 'a+') as f:
            metadata_entries = [json.dumps({'index': i, 'source': fname.replace(".npy", "")}) for i in range(len(curr_embed))]
            f.write("\n".join(metadata_entries) + '\n')
        print(f"[INDEX] Added {len(curr_embed)} vectors to index and updated metadata")
    faiss.write_index(index, os.path.join(index_dir, "faiss.index"))
    print(f"[INDEX] Saved index to {os.path.join(index_dir, 'faiss.index')}")
    return index

class Retriever:
    def __init__(self, retriever_name="ncbi/MedCPT-Query-Encoder", corpus_name="Marfan", db_dir="./corpus", **kwargs):
        print(f"[RETRIEVER] Initializing retriever with {retriever_name} for corpus {corpus_name}")
        self.retriever_name = retriever_name
        self.corpus_name = corpus_name
        self.db_dir = db_dir
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)
            print(f"[RETRIEVER] Created directory: {self.db_dir}")
        self.chunk_dir = os.path.join(self.db_dir, self.corpus_name, "chunk")
        if not os.path.exists(self.chunk_dir):
            os.makedirs(self.chunk_dir)
            print(f"[RETRIEVER] Created chunk directory: {self.chunk_dir}")
        self.index_dir = os.path.join(self.db_dir, self.corpus_name, "index", self.retriever_name.replace("Query-Encoder", "Article-Encoder"))
        if "bm25" in self.retriever_name.lower():
            from pyserini.search.lucene import LuceneSearcher
            print(f"[RETRIEVER] Using BM25 retriever")
            self.metadatas = None
            self.embedding_function = None
            if os.path.exists(self.index_dir):
                print(f"[RETRIEVER] Loading existing BM25 index from {self.index_dir}")
                self.index = LuceneSearcher(os.path.join(self.index_dir))
            else:
                print("[In progress] Building BM25 index for {:s}...".format(self.corpus_name))
                os.system("python -m pyserini.index.lucene --collection JsonCollection --input {:s} --index {:s} --generator DefaultLuceneDocumentGenerator --threads 16".format(self.chunk_dir, self.index_dir))
                self.index = LuceneSearcher(os.path.join(self.index_dir))
                print("[Finished] BM25 index created!")
        else:
            if os.path.exists(os.path.join(self.index_dir, "faiss.index")):
                print(f"[RETRIEVER] Loading existing FAISS index from {self.index_dir}")
                self.index = faiss.read_index(os.path.join(self.index_dir, "faiss.index"))
                print(f"[RETRIEVER] Loaded index with {self.index.ntotal} vectors")
                self.metadatas = [json.loads(line) for line in open(os.path.join(self.index_dir, "metadatas.jsonl")).read().strip().split('\n')]
                print(f"[RETRIEVER] Loaded {len(self.metadatas)} metadata entries")
            else:
                print("[In progress] Embedding the {:s} corpus with {:s}...".format(self.corpus_name, self.retriever_name))
                h_dim = embed(self.chunk_dir, self.index_dir, self.retriever_name.replace("Query-Encoder", "Article-Encoder"), **kwargs)
                self.index = construct_index(self.index_dir, self.retriever_name.replace("Query-Encoder", "Article-Encoder"), h_dim)
                self.metadatas = [json.loads(line) for line in open(os.path.join(self.index_dir, "metadatas.jsonl")).read().strip().split('\n')]
                print(f"[RETRIEVER] Created new index with {len(self.metadatas)} metadata entries")
            if "contriever" in self.retriever_name.lower():
                print(f"[RETRIEVER] Using Contriever embedding model")
                self.embedding_function = SentenceTransformer(self.retriever_name, device="cuda" if torch.cuda.is_available() else "cpu")
            else:
                print(f"[RETRIEVER] Using Custom transformer embedding model")
                self.embedding_function = CustomizeSentenceTransformer(self.retriever_name, device="cuda" if torch.cuda.is_available() else "cpu")
            self.embedding_function.eval()
            print(f"[RETRIEVER] Embedding function initialized")

    def get_relevant_documents(self, question, k=32, id_only=False, **kwargs):
        print(f"[RETRIEVAL] Getting relevant documents for query: '{question[:50]}...' with k={k}")
        assert isinstance(question, str)
        question = [question]
        if "bm25" in self.retriever_name.lower():
            print("[RETRIEVAL] Using BM25 search")
            res_ = [[]]
            hits = self.index.search(question[0], k=k)
            print(f"[RETRIEVAL] BM25 returned {len(hits)} hits")
            res_[0].append(np.array([h.score for h in hits]))
            ids = [h.docid for h in hits]
            indices = [{"source": '_'.join(h.docid.split('_')[:-1]), "index": eval(h.docid.split('_')[-1])} for h in hits]
            print(f"[RETRIEVAL] Processed {len(indices)} indices from BM25 results")
        else:
            print("[RETRIEVAL] Using dense retrieval with embeddings")
            with torch.no_grad():
                query_embed = self.embedding_function.encode(question, **kwargs)
                print(f"[RETRIEVAL] Generated query embedding of shape {query_embed.shape}")
            res_ = self.index.search(query_embed, k=k)
            print(f"[RETRIEVAL] FAISS returned {len(res_[1][0])} results")
            ids = ['_'.join([self.metadatas[i]["source"], str(self.metadatas[i]["index"])]) for i in res_[1][0]]
            indices = [self.metadatas[i] for i in res_[1][0]]
            print(f"[RETRIEVAL] Processed {len(indices)} indices from dense results")
        scores = res_[0][0].tolist()
        if id_only:
            print(f"[RETRIEVAL] Returning {len(ids)} document IDs")
            return [{"id": i} for i in ids], scores
        else:
            texts = self.idx2txt(indices)
            print(f"[RETRIEVAL] Returning {len(texts)} document texts")
            return texts, scores

    def idx2txt(self, indices):
        print(f"[RETRIEVAL] Converting {len(indices)} indices to text")
        def remove_extension(filename):
            if filename[-3:] == "tei":
                return filename
            return os.path.splitext(filename)[0]
        texts = []
        for i in indices:
            source_file = os.path.join(self.chunk_dir, remove_extension(i["source"]) + ".jsonl")
            print(f"[RETRIEVAL] Reading from {source_file}")
            try:
                with open(source_file) as f:
                    content = f.read().strip().split('\n')
                    if i["index"] < len(content):
                        text = json.loads(content[i["index"]])
                        texts.append(text)
                    else:
                        print(f"[RETRIEVAL] WARNING: Index {i['index']} out of range for {source_file} with {len(content)} items")
                        texts.append({"id": "error", "contents": "Index out of range"})
            except Exception as e:
                print(f"[RETRIEVAL] ERROR: Could not read {source_file}: {str(e)}")
                texts.append({"id": "error", "contents": f"Error reading file: {str(e)}"})
        print(f"[RETRIEVAL] Converted {len(texts)} indices to text")
        return texts

class RetrievalSystem:
    def __init__(self, retriever_name="MedCPT", corpus_name="Marfan", db_dir="./corpus"):
        print(f"[RETRIEVAL_SYSTEM] Initializing system with retriever={retriever_name}, corpus={corpus_name}")
        self.retriever_name = retriever_name
        self.corpus_name = corpus_name
        assert self.corpus_name in corpus_names
        assert self.retriever_name in retriever_names
        self.retrievers = []
        for retriever in retriever_names[self.retriever_name]:
            print(f"[RETRIEVAL_SYSTEM] Setting up retriever: {retriever}")
            self.retrievers.append([])
            for corpus in corpus_names[self.corpus_name]:
                print(f"[RETRIEVAL_SYSTEM] Setting up corpus: {corpus}")
                self.retrievers[-1].append(Retriever(retriever, corpus, db_dir))
        print(f"[RETRIEVAL_SYSTEM] Initialized with {len(self.retrievers)} retrievers")

    def retrieve(self, question, k=32, rrf_k=100):
        print(f"[RETRIEVAL_SYSTEM] Retrieving for question: '{question[:50]}...' with k={k}")
        assert isinstance(question, str)
        texts = []
        scores = []
        if "RRF" in self.retriever_name:
            k_ = max(k * 2, 100)
            print(f"[RETRIEVAL_SYSTEM] Using RRF with expanded k={k_}")
        else:
            k_ = k
        for i in range(len(retriever_names[self.retriever_name])):
            retriever_type = retriever_names[self.retriever_name][i]
            print(f"[RETRIEVAL_SYSTEM] Using retriever {i}: {retriever_type}")
            texts.append([])
            scores.append([])
            for j in range(len(corpus_names[self.corpus_name])):
                corpus_type = corpus_names[self.corpus_name][j]
                print(f"[RETRIEVAL_SYSTEM] Using corpus {j}: {corpus_type}")
                t, s = self.retrievers[i][j].get_relevant_documents(question, k=k_)
                texts[-1].append(t)
                scores[-1].append(s)
                print(f"[RETRIEVAL_SYSTEM] Retrieved {len(t)} documents with scores ranging from {min(s) if s else 'N/A'} to {max(s) if s else 'N/A'}")
        merged_texts, merged_scores = self.merge(texts, scores, k=k, rrf_k=rrf_k)
        print(f"[RETRIEVAL_SYSTEM] Merged results: {len(merged_texts)} documents")
        return merged_texts, merged_scores

    def merge(self, texts, scores, k=32, rrf_k=100):
        print(f"[RETRIEVAL_SYSTEM] Merging results with k={k}, rrf_k={rrf_k}")
        RRF_dict = {}
        for i in range(len(retriever_names[self.retriever_name])):
            retriever_type = retriever_names[self.retriever_name][i]
            print(f"[RETRIEVAL_SYSTEM] Merging for retriever {i}: {retriever_type}")
            texts_all, scores_all = None, None
            for j in range(len(corpus_names[self.corpus_name])):
                corpus_type = corpus_names[self.corpus_name][j]
                print(f"[RETRIEVAL_SYSTEM] Merging corpus {j}: {corpus_type}")
                if texts_all is None:
                    texts_all = texts[i][j]
                    scores_all = scores[i][j]
                else:
                    texts_all = texts_all + texts[i][j]
                    scores_all = scores_all + scores[i][j]
                print(f"[RETRIEVAL_SYSTEM] Current merged size: {len(texts_all)} documents")
            if "specter" in retriever_names[self.retriever_name][i].lower():
                print(f"[RETRIEVAL_SYSTEM] Sorting with SPECTER (ascending)")
                sorted_index = np.array(scores_all).argsort()
            else:
                print(f"[RETRIEVAL_SYSTEM] Sorting with {retriever_type} (descending)")
                sorted_index = np.array(scores_all).argsort()[::-1]
            texts[i] = [texts_all[i] for i in sorted_index]
            scores[i] = [scores_all[i] for i in sorted_index]
            print(f"[RETRIEVAL_SYSTEM] Sorted {len(texts[i])} documents")
            for j, item in enumerate(texts[i]):
                if item["id"] in RRF_dict:
                    RRF_dict[item["id"]]["score"] += 1 / (rrf_k + j + 1)
                    RRF_dict[item["id"]]["count"] += 1
                else:
                    RRF_dict[item["id"]] = {
                        "id": item["id"],
                        "contents": item["contents"],
                        "score": 1 / (rrf_k + j + 1),
                        "count": 1
                    }
        print(f"[RETRIEVAL_SYSTEM] RRF dict has {len(RRF_dict)} unique documents")
        RRF_list = sorted(RRF_dict.items(), key=lambda x: x[1]["score"], reverse=True)
        if len(texts) == 1:
            print(f"[RETRIEVAL_SYSTEM] Single retriever, taking top {k} from {len(texts[0])} documents")
            texts = texts[0][:k]
            scores = scores[0][:k]
        else:
            print(f"[RETRIEVAL_SYSTEM] Multiple retrievers, taking top {k} from {len(RRF_list)} RRF-ranked documents")
            texts = [dict((key, item[1][key]) for key in ("id", "contents")) for item in RRF_list[:k]]
            scores = [item[1]["score"] for item in RRF_list[:k]]
        print(f"[RETRIEVAL_SYSTEM] Final merged result: {len(texts)} documents")
        return texts, scores

class MedRAG:
    def __init__(self, llm_name="Gemini-Pro", rag=True, retriever_name="MedCPT", corpus_name="Marfan", db_dir="./corpus", cache_dir=None):
        print(f"[MEDRAG] Initializing with llm={llm_name}, rag={rag}, retriever={retriever_name}, corpus={corpus_name}")
        self.llm_name = llm_name
        self.rag = rag
        self.retriever_name = retriever_name
        self.corpus_name = corpus_name
        self.db_dir = db_dir
        self.cache_dir = cache_dir
        if rag:
            print(f"[MEDRAG] Setting up retrieval system")
            self.retrieval_system = RetrievalSystem(self.retriever_name, self.corpus_name, self.db_dir)
        else:
            print(f"[MEDRAG] No retrieval system needed")
            self.retrieval_system = None
        self.templates = {"cot_system": general_cot_system, "cot_prompt": general_cot,
                          "medrag_system": general_medrag_system, "medrag_prompt": general_medrag}
        if self.llm_name.lower().startswith("openai"):
            self.model = self.llm_name.split('/')[-1]
            if "gpt-3.5" in self.model or "gpt-35" in self.model:
                self.max_length = 16384
                self.context_length = 14500
            elif "gpt-4" in self.model:
                self.max_length = 32768
                self.context_length = 29500
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
            print(f"[MEDRAG] Using OpenAI model {self.model} with max_length={self.max_length}, context_length={self.context_length}")
        else:
            self.max_length = 16384  # Adjusted for Gemini-Pro
            self.context_length = 14500
            self.tokenizer = tiktoken.get_encoding("cl100k_base")  # Default for Gemini
            print(f"[MEDRAG] Using Gemini model with max_length={self.max_length}, context_length={self.context_length}")

    def split(self, question, chunk_size=512):
        print(f"[MEDRAG] Splitting question of length {len(question)} with chunk_size={chunk_size}")
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=50)
        chunks = splitter.split_text(question)
        print(f"[MEDRAG] Split into {len(chunks)} chunks")
        return chunks

    def createMessage(self, question, options=None, k=32, sub_k=None, total_k=None, rrf_k=100, save_dir=None, split=False, curated_note=None):
        print(f"[MEDRAG] Creating message for question: '{question[:50]}...'")
        origin_note = question
        if curated_note:
            print(f"[MEDRAG] Using curated note instead of original")
            question = curated_note
        if options is not None:
            print(f"[MEDRAG] Options provided: {list(options.keys())}")
            options = '\n'.join([key + ". " + options[key] for key in sorted(options.keys())])
        else:
            options = ''
        if split:
            print(f"[MEDRAG] Splitting question")
            sub_questions = self.split(question)
        else:
            sub_questions = [question]
            print(f"[MEDRAG] Using question as is (no splitting)")
        if sub_k is None:
            sub_k = k
        if total_k is not None and len(sub_questions) > 0:
            adjusted_sub_k = min(sub_k, (total_k * 2) // len(sub_questions))
            print(f"[MEDRAG] Adjusted sub_k from {sub_k} to {adjusted_sub_k} based on total_k={total_k} and {len(sub_questions)} questions")
        else:
            adjusted_sub_k = sub_k
        all_contexts = []
        all_retrieved_snippets = []
        all_scores = []
        total_tokens = 0
        seen_documents = {}
        sub_question_results = []
        for idx, sub_question in enumerate(sub_questions):
            print(f"[MEDRAG] Processing sub-question {idx+1}/{len(sub_questions)}: '{sub_question[:50]}...'")
            if self.rag:
                print(f"[MEDRAG] Retrieving documents for sub-question {idx+1}")
                assert self.retrieval_system is not None
                retrieved_snippets, scores = self.retrieval_system.retrieve(sub_question, k=adjusted_sub_k, rrf_k=rrf_k)
                print(f"[MEDRAG] Retrieved {len(retrieved_snippets)} snippets")
                current_snippets = []
                current_scores = []
                current_contexts = []
                for idx, (snippet, score) in enumerate(zip(retrieved_snippets, scores)):
                    doc_content = snippet["contents"]
                    if doc_content in seen_documents:
                        prev_idx, prev_score = seen_documents[doc_content]
                        if score > prev_score:
                            print(f"[MEDRAG] Document already seen but with better score now: {score} > {prev_score}")
                            seen_documents[doc_content] = (len(seen_documents), score)
                    else:
                        print(f"[MEDRAG] New document found with score {score}")
                        seen_documents[doc_content] = (len(seen_documents), score)
                        current_snippets.append(snippet)
                        current_scores.append(score)
                        current_contexts.append(f"Document [{len(seen_documents)-1}]: {doc_content}")
                    if total_k and len(seen_documents) >= total_k:
                        print(f"[MEDRAG] Reached total_k limit of {total_k} documents")
                        break
                if not current_contexts:
                    print(f"[MEDRAG] No contexts found, adding empty string")
                    current_contexts = [""]
                context_text = "\n".join(current_contexts)
                tokens = len(self.tokenizer.encode(context_text))
                print(f"[MEDRAG] Context has {tokens} tokens")
                sub_question_results.append({
                    'contexts': current_contexts,
                    'retrieved_snippets': current_snippets,
                    'scores': current_scores,
                    'tokens': tokens
                })
                total_tokens += tokens
            else:
                print(f"[MEDRAG] No RAG requested, skipping retrieval")
                sub_question_results.append({
                    'contexts': [],
                    'retrieved_snippets': [],
                    'scores': [],
                    'tokens': 0
                })
        if total_tokens > self.context_length and sub_question_results:
            excess_tokens = total_tokens - self.context_length
            tokens_to_reduce_per_question = excess_tokens // len(sub_question_results)
            print(f"[MEDRAG] Total tokens {total_tokens} exceeds limit {self.context_length}, reducing by {tokens_to_reduce_per_question} per question")
            for result in sub_question_results:
                if result['tokens'] > 0:
                    keep_ratio = max(0, (result['tokens'] - tokens_to_reduce_per_question) / result['tokens'])
                    keep_contexts = max(1, int(len(result['contexts']) * keep_ratio))
                    print(f"[MEDRAG] Keeping {keep_contexts}/{len(result['contexts'])} contexts (ratio: {keep_ratio:.2f})")
                    result['contexts'] = result['contexts'][:keep_contexts]
                    result['retrieved_snippets'] = result['retrieved_snippets'][:keep_contexts]
                    result['scores'] = result['scores'][:keep_contexts]
        for result in sub_question_results:
            all_contexts.extend(result['contexts'])
            all_retrieved_snippets.extend(result['retrieved_snippets'])
            all_scores.extend(result['scores'])
        print(f"[MEDRAG] Combined {len(all_contexts)} contexts across all sub-questions")
        combined_context = "\n".join(all_contexts)
        combined_context = self.tokenizer.decode(self.tokenizer.encode(combined_context)[:self.context_length])
        print(f"[MEDRAG] Final context length: {len(self.tokenizer.encode(combined_context))} tokens")
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir)
            print(f"[MEDRAG] Created directory: {save_dir}")
        if not self.rag:
            print(f"[MEDRAG] Creating COT prompt (no RAG)")
            prompt_cot = self.templates["cot_prompt"].render(question=origin_note, options=options)
            messages = [
                {"role": "system", "content": self.templates["cot_system"]},
                {"role": "user", "content": prompt_cot}
            ]
        else:
            print(f"[MEDRAG] Creating MedRAG prompt with context")
            prompt_medrag = self.templates["medrag_prompt"].render(context=combined_context, question=origin_note)
            messages = [
                {"role": "system", "content": self.templates["medrag_system"]},
                {"role": "user", "content": prompt_medrag}
            ]
        if save_dir:
            print(f"[MEDRAG] Saving snippets to {os.path.join(save_dir, 'snippets.json')}")
            with open(os.path.join(save_dir, "snippets.json"), 'w') as f:
                json.dump(all_retrieved_snippets, f, indent=4)
        print(f"[MEDRAG] Message creation complete, returning {len(messages)} messages and {len(all_retrieved_snippets)} snippets")
        return messages, all_retrieved_snippets, all_scores

class MedicalLiteratureManager:
    """Manager for retrieving, processing, and storing medical literature for RAG."""
    
    def __init__(self, literature_dir=MEDICAL_LITERATURE_DIR, corpus_dir=MEDICAL_CORPUS_DIR):
        """Initialize the medical literature manager."""
        self.literature_dir = literature_dir
        self.corpus_dir = corpus_dir
        self.diagnosis_dir = os.path.join(corpus_dir, "diagnosis")
        self.risk_dir = os.path.join(corpus_dir, "risk_assessment")
        
        # Create necessary directories
        os.makedirs(self.literature_dir, exist_ok=True)
        os.makedirs(self.corpus_dir, exist_ok=True)
        os.makedirs(self.diagnosis_dir, exist_ok=True)
        os.makedirs(self.risk_dir, exist_ok=True)
        
        # Initialize Chroma clients for vector storage
        self.diagnosis_chroma = chromadb.PersistentClient(path=os.path.join(self.diagnosis_dir, "chroma"))
        self.risk_chroma = chromadb.PersistentClient(path=os.path.join(self.risk_dir, "chroma"))
        
        # Set up vector stores
        self.diagnosis_vector_store = ChromaVectorStore(chroma_collection=self.diagnosis_chroma.get_or_create_collection("diagnosis_literature"))
        self.risk_vector_store = ChromaVectorStore(chroma_collection=self.risk_chroma.get_or_create_collection("risk_literature"))
        
        # Set up storage contexts
        self.diagnosis_storage_context = StorageContext.from_defaults(vector_store=self.diagnosis_vector_store)
        self.risk_storage_context = StorageContext.from_defaults(vector_store=self.risk_vector_store)
        
        # Indices for retrieval
        self._diagnosis_index = None
        self._risk_index = None
        
        print(f"[MEDICAL_LIT] Initialized MedicalLiteratureManager with literature_dir={literature_dir}, corpus_dir={corpus_dir}")
    
    def retrieve_perplexity_articles(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Retrieve article links from Perplexity AI based on a query."""
        print(f"[MEDICAL_LIT] Retrieving articles from Perplexity AI for query: '{query}'")
        
        # Perplexity API endpoint and headers
        perplexity_url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Construct the prompt for Perplexity to fetch article links
        prompt = f"Provide a list of the top {max_results} articles, webpages, or books related to the following medical query: '{query}'. Return the results in a JSON format with each entry containing 'title' and 'url'. Focus on reputable medical sources such as peer-reviewed journals, medical books, or trusted health websites."
        
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a medical research assistant tasked with finding relevant articles from reputable sources."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4096,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(perplexity_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract the response content
            if "choices" not in data or not data["choices"]:
                print(f"[MEDICAL_LIT] No results returned from Perplexity AI: {data}")
                return []
            
            content = data["choices"][0]["message"]["content"]
            
            # Parse the JSON content
            try:
                articles = json.loads(content)
                if not isinstance(articles, list):
                    articles = articles.get("articles", [])
            except json.JSONDecodeError:
                # If JSON parsing fails, attempt to extract URLs manually
                print(f"[MEDICAL_LIT] Failed to parse JSON from Perplexity response, attempting manual extraction")
                articles = []
                urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', content)
                for idx, url in enumerate(urls[:max_results]):
                    articles.append({
                        "title": f"Article {idx + 1}",
                        "url": url
                    })
            
            print(f"[MEDICAL_LIT] Retrieved {len(articles)} article links from Perplexity AI")
            return articles
            
        except Exception as e:
            print(f"[MEDICAL_LIT] Error retrieving articles from Perplexity AI: {str(e)}")
            return []
    
    def extract_article_content(self, article: Dict[str, str]) -> Dict[str, Any]:
        """Extract full content from an article URL using the universal extractor."""
        url = article.get("url")
        if not url:
            print(f"[MEDICAL_LIT] No URL found for article: {article}")
            return None
        
        print(f"[MEDICAL_LIT] Extracting content from URL: {url}")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Add a delay to avoid rate limiting
                time.sleep(1)  # 1-second delay between requests
                
                # Use the universal_extractor from test.py
                extracted_data = universal_extractor(url)
                
                if "Access Denied" in extracted_data.get("full_text", ""):
                    print(f"[MEDICAL_LIT] Access denied for URL: {url}")
                    return None
                
                metadata = extracted_data.get("metadata", {})
                full_text = extracted_data.get("full_text", "")
                
                article_data = {
                    "title": metadata.get("title", article.get("title", "Unknown Title")),
                    "abstract": full_text[:500],
                    "journal": metadata.get("journal", "Unknown Source"),
                    "year": metadata.get("date", "Unknown Year"),
                    "source": metadata.get("journal", "Perplexity AI"),
                    "url": url,
                    "full_text": full_text
                }
                
                print(f"[MEDICAL_LIT] Successfully extracted content for {article_data['title']}")
                return article_data
                
            except Exception as e:
                if "429 Client Error" in str(e):
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        print(f"[MEDICAL_LIT] Rate limit exceeded for {url}, retrying in {delay} seconds (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"[MEDICAL_LIT] Max retries reached for {url} due to rate limiting")
                        return None
                elif "403 Client Error" in str(e):
                    print(f"[MEDICAL_LIT] Access denied (403) for URL: {url}")
                    return None
                print(f"[MEDICAL_LIT] Error extracting content from {url}: {str(e)}")
                return None
    
    def retrieve_medical_articles(self, entity_groups: Dict[str, List[str]], analysis_type: str = "diagnosis", max_results: int = 50) -> List[Dict[str, Any]]:
        """Retrieve medical articles based on extracted entity groups using Perplexity AI."""
        print(f"[MEDICAL_LIT] Retrieving medical articles for {analysis_type} based on {len(entity_groups)} entity groups")
        
        query_parts = []
        
        if analysis_type == "diagnosis":
            # Build diagnosis-focused query
            if "SIGN_SYMPTOM" in entity_groups:
                symptoms = entity_groups["SIGN_SYMPTOM"][:5]  # Limit to top 5 symptoms
                if symptoms:
                    query_parts.append(" OR ".join([f'"{symptom}"' for symptom in symptoms]))
            
            if "DISEASE_DISORDER" in entity_groups:
                diseases = entity_groups["DISEASE_DISORDER"][:3]  # Limit to top 3 diseases
                if diseases:
                    query_parts.append(" OR ".join([f'"{disease}"' for disease in diseases]))
            
            # Add diagnostic terms
            query_parts.append("diagnosis OR differential diagnosis OR clinical presentation")
            
        elif analysis_type == "risk_assessment":
            # Build risk assessment-focused query
            if "DISEASE_DISORDER" in entity_groups:
                diseases = entity_groups["DISEASE_DISORDER"][:3]
                if diseases:
                    query_parts.append(" OR ".join([f'"{disease}"' for disease in diseases]))
            
            if "SIGN_SYMPTOM" in entity_groups:
                symptoms = entity_groups["SIGN_SYMPTOM"][:3]
                if symptoms:
                    query_parts.append(" OR ".join([f'"{symptom}"' for symptom in symptoms]))
            
            # Add risk assessment terms
            query_parts.append("risk factor OR risk assessment OR prognosis OR prevention")
        
        # Fall back to generic query if no entities found
        if not query_parts:
            if analysis_type == "diagnosis":
                query_parts = ["common diagnosis differential diagnosis clinical presentation"]
            else:
                query_parts = ["common risk factors prevention screening"]
        
        # Create final query
        full_query = " AND ".join([f"({part})" for part in query_parts])
        print(f"[MEDICAL_LIT] Generated query: {full_query}")
        
        # Compute hash for caching
        query_hash = hashlib.md5(full_query.encode()).hexdigest()
        cache_file = os.path.join(self.literature_dir, f"{analysis_type}_{query_hash}.json")
        
        # Check cache
        if os.path.exists(cache_file) and (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))).days < 7:
            print(f"[MEDICAL_LIT] Using cached results from {cache_file}")
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        # Retrieve article links from Perplexity AI
        article_links = self.retrieve_perplexity_articles(full_query, max_results)
        
        # Extract content from each article
        articles = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_article = {executor.submit(self.extract_article_content, article): article for article in article_links}
            for future in future_to_article:
                article_data = future.result()
                if article_data:
                    articles.append(article_data)
        
        # Cache results
        if articles:
            with open(cache_file, 'w') as f:
                json.dump(articles, f, indent=2)
        
        print(f"[MEDICAL_LIT] Retrieved and extracted {len(articles)} articles")
        return articles
    
    def add_articles_to_corpus(self, articles: List[Dict[str, Any]], analysis_type: str = "diagnosis") -> None:
        """Add retrieved articles to the appropriate corpus with vector embeddings."""
        print(f"[MEDICAL_LIT] Adding {len(articles)} articles to {analysis_type} corpus")
        
        if not articles:
            print("[MEDICAL_LIT] No articles to add")
            return
        
        # Choose the appropriate storage context and vector store
        if analysis_type == "diagnosis":
            storage_context = self.diagnosis_storage_context
            vector_store = self.diagnosis_vector_store
            index_ref = "_diagnosis_index"
        else:
            storage_context = self.risk_storage_context
            vector_store = self.risk_vector_store
            index_ref = "_risk_index"
        
        # Get existing document IDs from the vector store to avoid duplicates
        
        existing_ids = set()
        if getattr(self, index_ref) is not None:
            collection_name = "diagnosis_literature" if analysis_type == "diagnosis" else "risk_literature"
            # Access through the chroma client
            collection = self.diagnosis_chroma.get_collection(collection_name) if analysis_type == "diagnosis" else self.risk_chroma.get_collection(collection_name)
            
            existing_docs = collection.get(include=["metadatas"])
            for metadata in existing_docs["metadatas"]:
                if metadata and "url" in metadata:
                    existing_ids.add(metadata["url"])
        
        # Convert articles to documents, skipping duplicates
        documents = []
        for article in articles:
            article_url = article.get("url", "N/A")
            if article_url in existing_ids:
                print(f"[MEDICAL_LIT] Skipping duplicate article: {article['title']} (URL: {article_url})")
                continue
            
            text = f"Title: {article['title']}\n\n"
            text += f"Source: {article['source']}, Year: {article['year']}\n\n"
            text += f"Abstract: {article['abstract']}\n\n"
            text += f"Full Text: {article.get('full_text', article['abstract'])}\n\n"
            text += f"URL: {article_url}"
            
            doc = Document(
                text=text,
                metadata={
                    "title": article['title'],
                    "source": article['source'],
                    "year": article['year'],
                    "url": article_url
                }
            )
            documents.append(doc)
            existing_ids.add(article_url)  # Add to set to prevent duplicates in this batch
        
        if not documents:
            print("[MEDICAL_LIT] No new documents to add after deduplication")
            return
        
        # Create or update the index
        if getattr(self, index_ref) is None:
            print(f"[MEDICAL_LIT] Creating new index for {analysis_type}")
            pipeline = IngestionPipeline(
                transformations=[
                    SentenceSplitter(chunk_size=512, chunk_overlap=50),
                    Settings.embed_model
                ],
                vector_store=vector_store
            )
            nodes = pipeline.run(documents=documents)
            index = VectorStoreIndex(nodes, storage_context=storage_context)
            setattr(self, index_ref, index)
        else:
            print(f"[MEDICAL_LIT] Updating existing index for {analysis_type}")
            index = getattr(self, index_ref)
            for doc in documents:
                index.insert(doc)
        
        print(f"[MEDICAL_LIT] Added {len(documents)} documents to {analysis_type} corpus")
        
    def get_relevant_context(self, query: str, analysis_type: str = "diagnosis", k: int = 5) -> str:
        """Retrieve relevant context from the corpus based on a query."""
        print(f"[MEDICAL_LIT] Retrieving context for query: '{query}' (type: {analysis_type})")
        
        # Choose the appropriate index based on analysis type
        if analysis_type == "diagnosis":
            index = self._diagnosis_index
        else:  # risk_assessment
            index = self._risk_index
        
        if index is None:
            print(f"[MEDICAL_LIT] No index available for {analysis_type}")
            return ""
        
        # Query the index
        retriever = index.as_retriever(similarity_top_k=k)
        nodes = retriever.retrieve(query)
        
        # Format the retrieved context
        context_parts = []
        for idx, node in enumerate(nodes):
            context_parts.append(f"Document [{idx}]: {node.text}")
        
        context = "\n\n".join(context_parts)
        print(f"[MEDICAL_LIT] Retrieved {len(nodes)} relevant documents")
        return context
    
    def process_entity_groups_for_retrieval(self, entity_groups: Dict[str, List[str]], analysis_type: str = "diagnosis") -> str:
        """Process entity groups to create a retrieval query for the vector database."""
        print(f"[MEDICAL_LIT] Processing entity groups for retrieval (type: {analysis_type})")
        
        query_parts = []
        
        if analysis_type == "diagnosis":
            if "SIGN_SYMPTOM" in entity_groups:
                symptoms = entity_groups["SIGN_SYMPTOM"][:5]
                if symptoms:
                    query_parts.extend(symptoms)
            
            if "DISEASE_DISORDER" in entity_groups:
                diseases = entity_groups["DISEASE_DISORDER"][:3]
                if diseases:
                    query_parts.extend(diseases)
            
            query_parts.extend(["diagnosis", "differential diagnosis", "clinical presentation"])
        
        elif analysis_type == "risk_assessment":
            if "DISEASE_DISORDER" in entity_groups:
                diseases = entity_groups["DISEASE_DISORDER"][:3]
                if diseases:
                    query_parts.extend(diseases)
            
            if "SIGN_SYMPTOM" in entity_groups:
                symptoms = entity_groups["SIGN_SYMPTOM"][:3]
                if symptoms:
                    query_parts.extend(symptoms)
            
            query_parts.extend(["risk factor", "risk assessment", "prognosis", "prevention"])
        
        if not query_parts:
            if analysis_type == "diagnosis":
                query_parts = ["diagnosis", "differential diagnosis", "clinical presentation"]
            else:
                query_parts = ["risk factor", "prevention", "screening"]
        
        retrieval_query = " ".join(query_parts)
        print(f"[MEDICAL_LIT] Generated retrieval query: {retrieval_query}")
        return retrieval_query

    def retrieve_relevant_literature(self, query: str, analysis_type: str = "diagnosis", top_k: int = 5) -> List[Any]:
        """Retrieve relevant literature chunks from the vector database."""
        print(f"[MEDICAL_LIT] Retrieving relevant literature for query: '{query}' (type: {analysis_type})")
        
        if analysis_type == "diagnosis":
            index = self._diagnosis_index
        else:
            index = self._risk_index
        
        if index is None:
            print(f"[MEDICAL_LIT] No index available for {analysis_type}")
            return []
        
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)
        
        print(f"[MEDICAL_LIT] Retrieved {len(nodes)} relevant literature chunks")
        return nodes

    def prepare_literature_context(self, relevant_literature: List[Any]) -> str:
        """Format retrieved literature chunks into a context string."""
        if not relevant_literature:
            print("[MEDICAL_LIT] No relevant literature to format")
            return "No relevant medical literature found."
        
        context_parts = []
        for idx, node in enumerate(relevant_literature):
            context_parts.append(f"Document [{idx}]: {node.text}")
        
        context = "\n\n".join(context_parts)
        print(f"[MEDICAL_LIT] Prepared context with {len(context)} characters")
        return context

medical_literature_manager = MedicalLiteratureManager()

class DiseaseDetectionSystem:
    """
    Disease Detection System using a structured medical corpus and LLM-based analysis.
    """
    
    def __init__(self, corpus_dir: str = "./medical_corpus"):
        """
        Initialize the disease detection system.
        
        Args:
            corpus_dir: Directory containing the medical corpus
        """
        self.corpus_dir = corpus_dir
        self.diagnosis_dir = os.path.join(corpus_dir, "diagnosis")
        self.corpus = self._load_corpus()
        print(f"Initialized Disease Detection System with {len(self.corpus)} conditions in corpus")
    
    def _load_corpus(self) -> Dict[str, Dict[str, Any]]:
        """
        Load the medical corpus from the corpus directory.
        
        Returns:
            Dictionary mapping ICD codes to disease definitions
        """
        corpus = {}  # Initialize as a dictionary
        
        # If corpus directory doesn't exist, initialize it with sample data
        if not os.path.exists(self.corpus_dir):
            os.makedirs(self.corpus_dir, exist_ok=True)
            os.makedirs(self.diagnosis_dir, exist_ok=True)
            self._initialize_sample_corpus()
        
        # Load corpus from files
        for filename in os.listdir(self.corpus_dir):
            print(f'[CORPUS] {filename}')
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.corpus_dir, filename), 'r') as f:
                        disease_def = json.load(f)
                        print(f'[DISEASE DEF] {disease_def}')
                        # Store by ICD code for efficient lookup
                        corpus[disease_def["icd_code"]] = disease_def
                except Exception as e:
                    print(f"Error loading corpus file {filename}: {str(e)}")
        
        return corpus

    def _initialize_sample_corpus(self):
        """Create sample corpus with common conditions for testing."""
        # Sample: Congestive Heart Failure
        chf = {
            "disease": "Congestive Heart Failure",
            "icd_code": "I50.9",
            "parameters": {
                "symptoms": [
                    {"name": "dyspnea", "severity": ["mild", "moderate", "severe"], "onset_pattern": ["exertional", "nocturnal", "at rest"]},
                    {"name": "edema", "location": ["lower extremity", "generalized"], "timing": ["evening", "persistent"]},
                    {"name": "fatigue", "pattern": ["with exertion", "persistent"]}
                ],
                "vital_signs": {
                    "blood_pressure": {"high": ">140/90", "low": "<90/60"},
                    "heart_rate": {"high": ">100 bpm", "irregular": True},
                    "respiratory_rate": {"high": ">20 breaths/min"}
                },
                "physical_findings": [
                    "jugular venous distention",
                    "pulmonary rales",
                    "S3 heart sound"
                ],
                "lab_values": {
                    "BNP": {"high": ">100 pg/mL"},
                    "troponin": {"high": ">0.04 ng/mL"}
                },
                "risk_factors": [
                    "hypertension",
                    "coronary artery disease",
                    "diabetes",
                    "previous myocardial infarction"
                ],
                "imaging_findings": {
                    "chest_xray": ["cardiomegaly", "pulmonary congestion"],
                    "echocardiogram": ["reduced ejection fraction", "chamber enlargement"]
                }
            },
            "diagnostic_criteria": {
                "required": ["dyspnea", "BNP > 100 pg/mL"],
                "supportive": ["edema", "rales", "cardiomegaly on imaging"]
            },
            "differential_diagnoses": [
                "pneumonia",
                "COPD exacerbation",
                "pulmonary embolism"
            ]
        }
        
        # Sample: Type 2 Diabetes
        t2dm = {
            "disease": "Type 2 Diabetes Mellitus",
            "icd_code": "E11",
            "parameters": {
                "symptoms": [
                    {"name": "polyuria", "severity": ["mild", "moderate", "severe"]},
                    {"name": "polydipsia", "severity": ["mild", "moderate", "severe"]},
                    {"name": "unexplained weight loss", "severity": ["mild", "moderate", "severe"]},
                    {"name": "fatigue", "pattern": ["persistent"]}
                ],
                "vital_signs": {},
                "physical_findings": [
                    "acanthosis nigricans",
                    "poor wound healing",
                    "peripheral neuropathy"
                ],
                "lab_values": {
                    "fasting glucose": {"high": ">126 mg/dL"},
                    "HbA1c": {"high": ">6.5%"},
                    "random glucose": {"high": ">200 mg/dL"}
                },
                "risk_factors": [
                    "obesity",
                    "family history of diabetes",
                    "sedentary lifestyle",
                    "history of gestational diabetes",
                    "hypertension"
                ],
                "imaging_findings": {}
            },
            "diagnostic_criteria": {
                "required": ["fasting glucose > 126 mg/dL", "HbA1c > 6.5%", "random glucose > 200 mg/dL with symptoms"],
                "supportive": ["polyuria", "polydipsia", "unexplained weight loss"]
            },
            "differential_diagnoses": [
                "type 1 diabetes",
                "LADA (Latent Autoimmune Diabetes in Adults)",
                "medication-induced hyperglycemia"
            ]
        }
        
        # Sample: Community-Acquired Pneumonia
        cap = {
            "disease": "Community-Acquired Pneumonia",
            "icd_code": "J18.9",
            "parameters": {
                "symptoms": [
                    {"name": "cough", "severity": ["mild", "moderate", "severe"], "pattern": ["productive", "non-productive"]},
                    {"name": "fever", "severity": ["low-grade", "high-grade"]},
                    {"name": "dyspnea", "severity": ["mild", "moderate", "severe"]},
                    {"name": "chest pain", "pattern": ["pleuritic", "constant"]}
                ],
                "vital_signs": {
                    "temperature": {"high": ">38°C"},
                    "respiratory_rate": {"high": ">20 breaths/min"},
                    "heart_rate": {"high": ">100 bpm"},
                    "oxygen_saturation": {"low": "<95%"}
                },
                "physical_findings": [
                    "crackles",
                    "bronchial breath sounds",
                    "dullness to percussion",
                    "increased tactile fremitus"
                ],
                "lab_values": {
                    "WBC": {"high": ">11,000/μL", "pattern": "neutrophil predominant"},
                    "CRP": {"high": ">10 mg/L"},
                    "procalcitonin": {"high": ">0.25 ng/mL"}
                },
                "risk_factors": [
                    "advanced age",
                    "smoking",
                    "COPD",
                    "immunosuppression",
                    "alcoholism"
                ],
                "imaging_findings": {
                    "chest_xray": ["infiltrate", "consolidation", "air bronchograms"],
                    "ct_chest": ["ground-glass opacities", "consolidation"]
                }
            },
            "diagnostic_criteria": {
                "required": ["clinical symptoms of pneumonia", "radiographic evidence of infiltrate"],
                "supportive": ["fever", "elevated inflammatory markers", "leukocytosis"]
            },
            "differential_diagnoses": [
                "acute bronchitis",
                "COPD exacerbation",
                "pulmonary embolism",
                "heart failure",
                "lung cancer"
            ]
        }
        
        # Save sample corpus
        with open(os.path.join(self.diagnosis_dir, "chf.json"), 'w') as f:
            json.dump(chf, f, indent=2)
        
        with open(os.path.join(self.diagnosis_dir, "t2dm.json"), 'w') as f:
            json.dump(t2dm, f, indent=2)
            
        with open(os.path.join(self.diagnosis_dir, "cap.json"), 'w') as f:
            json.dump(cap, f, indent=2)
    
    def extract_patient_parameters(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured parameters from patient data in EHR format.
        
        Args:
            patient_data: Dictionary containing patient clinical data
            
        Returns:
            Dictionary with structured parameters extracted from the patient data
        """
        structured_parameters = {
            "symptoms": {},
            "vital_signs": {},
            "physical_findings": [],
            "lab_values": {},
            "risk_factors": [],
            "imaging_findings": {},
            "demographics": {}
        }
        
        # Extract patient demographics
        if "first_name" in patient_data and "last_name" in patient_data:
            structured_parameters["demographics"]["name"] = f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}"
        
        if "date_of_birth" in patient_data:
            structured_parameters["demographics"]["dob"] = patient_data["date_of_birth"]
            # Calculate age if DOB is available
            try:
                dob = datetime.strptime(patient_data["date_of_birth"], "%Y-%m-%d")
                today = datetime.now()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                structured_parameters["demographics"]["age"] = age
            except:
                pass
        
        if "gender" in patient_data:
            structured_parameters["demographics"]["gender"] = patient_data["gender"]
        
        # Extract vitals from encounters
        if "encounter" in patient_data and isinstance(patient_data["encounter"], dict):
            encounter = patient_data["encounter"]
            
            # Extract symptoms from chief complaint and HPI
            if "chief_complaint" in encounter:
                structured_parameters["chief_complaint"] = encounter["chief_complaint"]
            
            if "hpi" in encounter:
                structured_parameters["history_present_illness"] = encounter["hpi"]
            
            # Extract vital signs
            if "vital_signs" in encounter and isinstance(encounter["vital_signs"], dict):
                vitals = encounter["vital_signs"]
                structured_parameters["vital_signs"] = vitals
            
            # Extract physical findings
            if "physical_exam" in encounter:
                structured_parameters["physical_findings"] = encounter["physical_exam"]
            
            # Extract assessment and plan
            if "assessment" in encounter:
                structured_parameters["assessment"] = encounter["assessment"]
            
            if "plan" in encounter:
                structured_parameters["plan"] = encounter["plan"]
                
            # Extract diagnosis codes if available
            if "diagnosis_codes" in encounter:
                structured_parameters["diagnosis_codes"] = encounter["diagnosis_codes"]
        
        # Extract medical history as risk factors
        if "medical_history" in patient_data and isinstance(patient_data["medical_history"], list):
            for condition in patient_data["medical_history"]:
                if isinstance(condition, dict) and "condition" in condition:
                    structured_parameters["risk_factors"].append(condition["condition"])
        
        # Extract lab values
        if "lab_results" in patient_data and isinstance(patient_data["lab_results"], list):
            for lab in patient_data["lab_results"]:
                if isinstance(lab, dict) and "test_name" in lab and "result_value" in lab:
                    structured_parameters["lab_values"][lab["test_name"]] = {
                        "value": lab["result_value"],
                        "unit": lab.get("unit", ""),
                        "reference_range": lab.get("reference_range", ""),
                        "abnormal_flag": lab.get("abnormal_flag", "")
                    }
        
        # Extract imaging findings
        if "scans" in patient_data and isinstance(patient_data["scans"], list):
            for scan in patient_data["scans"]:
                if isinstance(scan, dict) and "scan_type" in scan and "analysis" in scan:
                    scan_type = scan["scan_type"].lower()
                    if "chest" in scan_type or "x-ray" in scan_type:
                        category = "chest_xray"
                    elif "ct" in scan_type:
                        category = "ct_scan"
                    elif "mri" in scan_type:
                        category = "mri"
                    elif "ultrasound" in scan_type:
                        category = "ultrasound"
                    elif "echocardiogram" in scan_type or "echo" in scan_type:
                        category = "echocardiogram"
                    else:
                        category = scan_type
                    
                    if category not in structured_parameters["imaging_findings"]:
                        structured_parameters["imaging_findings"][category] = []
                    
                    structured_parameters["imaging_findings"][category].append(scan["analysis"])
        
        # Extract medications as they might indicate conditions
        if "medications" in patient_data and isinstance(patient_data["medications"], list):
            structured_parameters["medications"] = []
            for medication in patient_data["medications"]:
                if isinstance(medication, dict) and "name" in medication:
                    med_info = {
                        "name": medication["name"]
                    }
                    if "dosage" in medication:
                        med_info["dosage"] = medication["dosage"]
                    if "frequency" in medication:
                        med_info["frequency"] = medication["frequency"]
                    
                    structured_parameters["medications"].append(med_info)
        
        # Extract allergies
        if "allergies" in patient_data and isinstance(patient_data["allergies"], list):
            structured_parameters["allergies"] = []
            for allergy in patient_data["allergies"]:
                if isinstance(allergy, dict) and "allergen" in allergy:
                    structured_parameters["allergies"].append(allergy["allergen"])
        
        return structured_parameters
    
    
    def identify_potential_icd_codes(self, patient_data: Dict[str, Any]) -> List[str]:
        """
        First stage: Use LLM to identify potential ICD-10 codes based on patient data.
        
        Args:
            patient_data: Dictionary containing patient data
            
        Returns:
            List of potential ICD-10 codes
        """
        # Extract structured parameters from patient data
        patient_parameters = self.extract_patient_parameters(patient_data)
        
        # Create prompt for ICD code identification
        prompt = f"""
        You are a clinical coding expert specializing in ICD-10 diagnosis codes. 
        Based on the following patient information, identify the most likely ICD-10 codes that match this patient's presentation.
        
        PATIENT INFORMATION:
        {json.dumps(patient_parameters, indent=2)}
        
        Analyze the patient's symptoms, vital signs, physical findings, lab results, and other clinical data.
        Identify the most likely ICD-10 codes that match this patient's presentation.
        
        Return ONLY a JSON array of ICD-10 codes, like this:
        ["I50.9", "E11", "J18.9"]
        
        Include only the codes themselves, no explanations. Limit to the top 3-5 most relevant codes.
        """
        
        # Get LLM response
        print(f"Sending prompt to LLM for ICD code identification...")
        response = Settings.llm.complete(prompt)
        
        # Process response
        try:
            # Clean up response in case it includes markdown code block formatting
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            # Parse the JSON array
            icd_codes = json.loads(response_text.strip())
            
            if not isinstance(icd_codes, list):
                raise ValueError("Response is not a list of ICD codes")
            
            print(f"Identified potential ICD codes: {icd_codes}")
            return icd_codes
            
        except Exception as e:
            print(f"Error processing LLM response for ICD codes: {str(e)}")
            print(f"Raw response: {response.text}")
            
            # Return empty list on error
            return []
    
    async def detect_diseases_with_icd_codes(self, patient_data: Dict[str, Any], icd_codes: List[str]) -> Dict[str, Any]:
        """
        Second stage: Match patient against specific diseases identified by ICD codes.
        
        Args:
            patient_data: Dictionary containing patient data
            icd_codes: List of ICD-10 codes to match against
            
        Returns:
            Dictionary with detection results
        """
        # Extract structured parameters from patient data
        patient_parameters = self.extract_patient_parameters(patient_data)
        print(f'[DISEASE DETECTION] Patient Parameters {patient_parameters}')

        patient_data_str = json.dumps(patient_parameters, indent=2)
        entity_results = extract_medical_entities(patient_data_str)
        
        # Get literature context using the imported function
        literature_context = await enhanced_literature_retrieval(
            entity_groups=entity_results.get("entity_groups", {}),
            analysis_type="diagnosis"
        )
        # Get relevant diseases from corpus based on ICD codes
        relevant_diseases = []
        for code in icd_codes:
            # Check for exact match first
            print(f'[CODES FOUND] {code}')
            if code in self.corpus:
                relevant_diseases.append(self.corpus[code])
                print(f'[RELEVANT DISEASE] {code}')
            else:
                # Check for partial matches (e.g., I50 matches I50.9)
                for icd_code, disease in self.corpus.items():
                    if code.startswith(icd_code) or icd_code.startswith(code):
                        relevant_diseases.append(disease)
        
        # If no matches found, fall back to a subset of common diseases
        if not relevant_diseases:
            print("No matching diseases found in corpus, using common diseases as fallback")
            relevant_diseases = list(self.corpus.values())[:5]  # First 5 diseases as fallback
        
        # Convert corpus to simplified form for LLM context
        simplified_corpus = []
        for disease in relevant_diseases:
            simplified = {
                "disease": disease["disease"],
                "icd_code": disease["icd_code"],
                "key_symptoms": [symptom["name"] for symptom in disease["parameters"].get("symptoms", [])],
                "key_findings": disease["parameters"].get("physical_findings", []),
                "key_labs": list(disease["parameters"].get("lab_values", {}).keys()),
                "diagnostic_criteria": disease["diagnostic_criteria"],
                "differential_diagnoses": disease["differential_diagnoses"]
            }
            simplified_corpus.append(simplified)
        print(f'[DISEASE DETECTION] Simplified Corpus {simplified_corpus}')
        # Create prompt for LLM for the second stage
        prompt = f"""
You are a clinical diagnostic expert. Based on the following patient information and focused set of potential diseases, evaluate the patient for these specific conditions.

PATIENT INFORMATION:
{json.dumps(patient_parameters, indent=2)}

POTENTIAL DISEASES (FILTERED BY ICD CODES {', '.join(icd_codes)}):
{json.dumps(simplified_corpus, indent=2)}

RELEVANT MEDICAL LITERATURE:
{literature_context}

Analyze the patient's symptoms, vital signs, physical findings, lab results, and other clinical data against these specific diseases.
Identify which of these diseases best match the patient's presentation and provide your clinical reasoning.
Use the provided medical literature to enhance your analysis and reasoning.

Return your response as a JSON object with the following structure:
{{
    "matched_diseases": [
        {{
            "disease": "Name of Disease",
            "icd_code": "ICD-10 Code",
            "probability": 85,
            "reasoning": "Clinical reasoning explaining why this disease matches"
        }}
    ],
    "differential_diagnoses": [
        {{
            "disease": "Name of Disease",
            "icd_code": "ICD-10 Code",
            "probability": 60,
            "reasoning": "Brief explanation"
        }}
    ],
    "additional_testing_recommended": [
        "List of recommended tests to confirm diagnosis or rule out differentials"
    ],
    "clinical_summary": "Overall clinical assessment and diagnostic impression"
}}
Note: For 'probability', provide a number between 0 and 100 representing confidence percentage.
"""
        # Get LLM response
        start_time = time.time()
        print(f"Sending prompt to LLM for disease detection (second stage)...")
        
        response = Settings.llm.complete(prompt)
        
        print(f"LLM response received in {time.time() - start_time:.2f} seconds")
        
        # Process response - same as original implementation
        try:
            # Clean up response in case it includes markdown code block formatting
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            
            # Ensure we have the expected structure
            if not isinstance(result, dict):
                raise ValueError("Response is not a dictionary")
            
            if "matched_diseases" not in result:
                result["matched_diseases"] = []
            
            if "differential_diagnoses" not in result:
                result["differential_diagnoses"] = []
                
            if "additional_testing_recommended" not in result:
                result["additional_testing_recommended"] = []
                
            if "clinical_summary" not in result:
                result["clinical_summary"] = "No clinical summary provided."
            
            # Add timestamp
            result["timestamp"] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            print(f"Error processing LLM response: {str(e)}")
            print(f"Raw response: {response.text}")
            
            # Return error result
            return {
                "error": f"Failed to process LLM response: {str(e)}",
                "matched_diseases": [],
                "differential_diagnoses": [],
                "additional_testing_recommended": [],
                "clinical_summary": "Error in disease detection process.",
                "timestamp": datetime.now().isoformat()
            }
    
    def detect_diseases_llm(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to detect diseases based on patient data and medical corpus.
        
        Args:
            patient_data: Dictionary containing patient data
            
        Returns:
            Dictionary with detection results including matched diseases, probabilities, and reasoning
        """
        # Extract structured parameters from patient data
        patient_parameters = self.extract_patient_parameters(patient_data)
        
        # Convert corpus to simplified form for LLM context
        simplified_corpus = []
        for disease in self.corpus.values():  # Use .values() to iterate over dictionary values
            simplified = {
                "disease": disease["disease"],
                "icd_code": disease["icd_code"],
                "key_symptoms": [symptom["name"] for symptom in disease["parameters"].get("symptoms", [])],
                "key_findings": disease["parameters"].get("physical_findings", []),
                "key_labs": list(disease["parameters"].get("lab_values", {}).keys()),
                "diagnostic_criteria": disease["diagnostic_criteria"],
                "differential_diagnoses": disease["differential_diagnoses"]
            }
            simplified_corpus.append(simplified)
        
        # Create prompt for LLM
        prompt = f"""
        You are a clinical diagnostic expert. Based on the following patient information and medical corpus, evaluate the patient for potential diseases.

        PATIENT INFORMATION:
        {json.dumps(patient_parameters, indent=2)}

        MEDICAL CORPUS (REFERENCE DISEASES):
        {json.dumps(simplified_corpus, indent=2)}

        Analyze the patient's symptoms, vital signs, physical findings, lab results, and other clinical data against the provided medical corpus.
        Identify the most likely diseases/conditions and provide your clinical reasoning.

        Return your response as a JSON object with the following structure:
        {{
            "matched_diseases": [
                {{
                    "disease": "Name of Disease",
                    "icd_code": "ICD-10 Code",
                    "probability": 0-100 (confidence percentage),
                    "reasoning": "Clinical reasoning explaining why this disease matches"
                }}
            ],
            "differential_diagnoses": [
                {{
                    "disease": "Name of Disease",
                    "icd_code": "ICD-10 Code",
                    "probability": 0-100 (confidence percentage),
                    "reasoning": "Brief explanation"
                }}
            ],
            "additional_testing_recommended": [
                "List of recommended tests to confirm diagnosis or rule out differentials"
            ],
            "clinical_summary": "Overall clinical assessment and diagnostic impression"
        }}

        Focus on the most clinically relevant matches rather than trying to match every possible condition.
        """
        
        # Get LLM response
        start_time = time.time()
        print(f"Sending prompt to LLM for disease detection...")
        
        response = Settings.llm.complete(prompt)
        
        print(f"LLM response received in {time.time() - start_time:.2f} seconds")
        
        # Process response
        try:
            # Clean up response in case it includes markdown code block formatting
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            
            # Ensure we have the expected structure
            if not isinstance(result, dict):
                raise ValueError("Response is not a dictionary")
            
            if "matched_diseases" not in result:
                result["matched_diseases"] = []
            
            if "differential_diagnoses" not in result:
                result["differential_diagnoses"] = []
                
            if "additional_testing_recommended" not in result:
                result["additional_testing_recommended"] = []
                
            if "clinical_summary" not in result:
                result["clinical_summary"] = "No clinical summary provided."
            
            # Add timestamp
            result["timestamp"] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            print(f"Error processing LLM response: {str(e)}")
            print(f"Raw response: {response.text}")
            
            # Return error result
            return {
                "error": f"Failed to process LLM response: {str(e)}",
                "matched_diseases": [],
                "differential_diagnoses": [],
                "additional_testing_recommended": [],
                "clinical_summary": "Error in disease detection process.",
                "timestamp": datetime.now().isoformat()
            }
    
    def save_detection_result(self, patient_id: str, result: Dict[str, Any]) -> str:
        """
        Save the disease detection result to a file.
        
        Args:
            patient_id: Patient identifier
            result: Disease detection result dictionary
            
        Returns:
            Path to the saved result file
        """
        # Create results directory if it doesn't exist
        results_dir = os.path.join(self.corpus_dir, "results")
        if not os.path.exists(results_dir):
            os.makedirs(results_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{patient_id}_{timestamp}.json"
        filepath = os.path.join(results_dir, filename)
        
        # Save result to file
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Detection result saved to {filepath}")
        return filepath
    
    async def analyze_patient(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method to analyze a patient using the two-stage approach.
        
        Args:
            patient_data: Dictionary containing patient data
            
        Returns:
            Dictionary with detection results
        """
        # Get patient ID if available
        patient_id = patient_data.get("id", "unknown_patient")
        
        # STAGE 1: Identify potential ICD codes
        print(f"STAGE 1: Identifying potential ICD codes for patient {patient_id}")
        icd_codes = self.identify_potential_icd_codes(patient_data)
        
        # STAGE 2: Match against specific diseases
        print(f"STAGE 2: Matching patient against diseases with ICD codes: {icd_codes}")
        detection_result = await self.detect_diseases_with_icd_codes(patient_data, icd_codes)
        
        # Add the identified ICD codes to the result
        detection_result["identified_icd_codes"] = icd_codes
        
        # Save result if valid
        if "error" not in detection_result:
            self.save_detection_result(patient_id, detection_result)
        
        return detection_result

# Pydantic Models for input validation
class OrganizationCreate(BaseModel):
    name: str

class PatientAnalysisRequest(BaseModel):
    patient_input: Dict[str, Any]
    llm_model: str

class VitalSigns(BaseModel):
    temperature: Optional[float] = None
    heart_rate: Optional[int] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    bmi: Optional[float] = None
    pain_score: Optional[int] = None

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    primary_care_provider: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    organization_id:Optional[str] = None


class EncounterCreate(BaseModel):
    patient_id: str
    encounter_type: str
    chief_complaint: str
    vital_signs: Optional[VitalSigns] = None
    hpi: str
    ros: Optional[str] = None
    physical_exam: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    diagnosis_codes: Optional[str] = None
    followup_instructions: Optional[str] = None

class MedicalHistoryCreate(BaseModel):
    patient_id: str
    condition: str
    onset_date: Optional[str] = None
    status: str
    notes: Optional[str] = None


class FamilyHistoryCreate(BaseModel):
    patient_id: str
    relation: str
    condition: str
    onset_age: Optional[int] = None
    notes: Optional[str] = None

class MedicationCreate(BaseModel):
    patient_id: str
    name: str
    dosage: str
    frequency: str
    route: str
    start_date: str
    end_date: Optional[str] = None
    indication: Optional[str] = None
    pharmacy_notes: Optional[str] = None

class AllergyCreate(BaseModel):
    patient_id: str
    allergen: str
    reaction: str
    severity: str
    onset_date: Optional[str] = None
    notes: Optional[str] = None

class LabOrderCreate(BaseModel):
    patient_id: str
    test_name: str
    test_code: Optional[str] = None
    priority: str = "Routine"
    collection_date: Optional[datetime] = None  # Add this
    notes: Optional[str] = None

class LabOrderUpdate(BaseModel):
    test_code: Optional[str] = None
    priority: Optional[str] = None
    collection_date: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[str] = None  # Allow status updates like "Collected"

class LabResultCreate(BaseModel):
    lab_order_id: str
    result_value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    abnormal_flag: Optional[str] = None
    performing_lab: Optional[str] = None
    notes: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    is_doctor: bool = False
    organization_id: str
    role: str = "staff"

class AIAnalysisCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    analysis_type: str
    input_text: str
    llm_model: str
    scan_ids: List[str] = []  # Add this field to accept scan IDs


# Data processing functions
def load_data_from_frontend_input(user_input: Dict[str, Any], index_type: str = "") -> List[Document]:
    print(f"[LOAD_DATA] Loading data from frontend input of type: {user_input.get('type', 'unknown')}")
    input_type = user_input.get("type")
    payload = user_input.get("payload", "")
    if not isinstance(payload, dict):
        payload = {"data": payload}
        print(f"[LOAD_DATA] Converted non-dict payload to dict with 'data' key")
    data = payload.get("data", "")
    print(f"[LOAD_DATA] Payload data length: {len(str(data))}")
    context_str = user_input.get("context_str", f"Data from {input_type}")
    docs: List[Document] = []
    if input_type == "raw_text":
        print(f"[LOAD_DATA] Processing raw text input")
        doc = Document(text=data, metadata={"source": "raw_text", "context_str": context_str})
        docs.append(doc)
        print(f"[LOAD_DATA] Created document with text length: {len(doc.text)}")
    elif input_type == "local_file":
        print(f"[LOAD_DATA] Processing local file input: {data}")
        file_path = data
        if not os.path.exists(file_path):
            print(f"[LOAD_DATA] ERROR: File not found: {file_path}")
            return []
        reader = SimpleDirectoryReader(input_files=[file_path])
        docs = reader.load_data()
        print(f"[LOAD_DATA] Loaded {len(docs)} documents from file")
        for doc in docs:
            doc.metadata.update({"source": "local_file", "file_path": file_path, "context_str": context_str})
    print(f"[LOAD_DATA] Returning {len(docs)} documents")
    return docs

def build_ingestion_pipeline(vector_store=None, chunk_size=512, chunk_overlap=50):
    print(f"[PIPELINE] Building ingestion pipeline with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    transformations = [splitter, Settings.embed_model]
    pipeline = IngestionPipeline(transformations=transformations, vector_store=vector_store)
    print(f"[PIPELINE] Pipeline created with {len(transformations)} transformations")
    return pipeline

def process_user_inputs_and_build_index(
    user_inputs: List[Dict[str, Any]],
    index_type: str,
    index_params: Dict[str, Any],
    index_id: str,
    document_name: str
):
    print(f"[INDEX_BUILD] Processing user inputs to build {index_type} index with ID {index_id} for {document_name}")
    all_docs = [doc for ui in user_inputs for doc in load_data_from_frontend_input(ui, index_type)]
    print(f"[INDEX_BUILD] Loaded {len(all_docs)} documents")
    vector_store = ChromaVectorStore(chroma_collection=chroma_client.get_or_create_collection("ehr_data"))
    print(f"[INDEX_BUILD] Created/loaded Chroma collection 'ehr_data'")
    pipeline = build_ingestion_pipeline(vector_store=vector_store)
    print(f"[INDEX_BUILD] Running ingestion pipeline")
    nodes = pipeline.run(documents=all_docs)
    print(f"[INDEX_BUILD] Created {len(nodes)} nodes")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(nodes, storage_context=storage_context)
    print(f"[INDEX_BUILD] Created vector store index")
    query_engine = index.as_query_engine(similarity_top_k=5, llm=Settings.llm)
    print(f"[INDEX_BUILD] Created query engine with similarity_top_k=5")
    return {"type": "vector_store", "engine": query_engine}

def summarize_patient_data(docs: List[Document]) -> str:
    print(f"[SUMMARIZE] Summarizing {len(docs)} patient documents")
    full_text = " ".join([doc.text for doc in docs])
    print(f"[SUMMARIZE] Combined text length: {len(full_text)}")
    prompt = f"Summarize the following patient data in 50-100 words:\n\n{full_text}"
    print(f"[SUMMARIZE] Sending summarization prompt to LLM")
    summary = Settings.llm.complete(prompt).text.strip()
    print(f"[SUMMARIZE] Generated summary of length {len(summary)}")
    return summary

def generate_clinical_note(patient_data: Dict[str, Any], format_type: str = "soap") -> str:
    print(f"[CLINICAL_NOTE] Generating {format_type.upper()} note from patient data")
    
    # Extract patient info
    patient_info = f"Patient: {patient_data.get('first_name', '')} {patient_data.get('last_name', '')}"
    if patient_data.get('date_of_birth'):
        patient_info += f", DOB: {patient_data.get('date_of_birth')}"
    if patient_data.get('gender'):
        patient_info += f", Gender: {patient_data.get('gender')}"
    
    # Extract encounter info
    encounter_info = ""
    if 'encounter' in patient_data:
        enc = patient_data['encounter']
        if enc.get('chief_complaint'):
            encounter_info += f"\nChief Complaint: {enc.get('chief_complaint')}"
        
        # Add vital signs if available
        if enc.get('vital_signs'):
            vitals = enc['vital_signs']
            vital_info = "\nVital Signs:"
            if vitals.get('temperature'):
                vital_info += f" Temp: {vitals.get('temperature')}°F,"
            if vitals.get('heart_rate'):
                vital_info += f" HR: {vitals.get('heart_rate')} bpm,"
            if vitals.get('blood_pressure_systolic') and vitals.get('blood_pressure_diastolic'):
                vital_info += f" BP: {vitals.get('blood_pressure_systolic')}/{vitals.get('blood_pressure_diastolic')} mmHg,"
            if vitals.get('respiratory_rate'):
                vital_info += f" RR: {vitals.get('respiratory_rate')} breaths/min,"
            if vitals.get('oxygen_saturation'):
                vital_info += f" O2 Sat: {vitals.get('oxygen_saturation')}%,"
            encounter_info += vital_info.rstrip(',')
    
    # Format based on note type
    if format_type == "soap":
        subjective = f"S: {patient_data.get('encounter', {}).get('hpi', 'No HPI recorded.')}"
        
        objective = "O: "
        if patient_data.get('encounter', {}).get('physical_exam'):
            objective += patient_data['encounter']['physical_exam']
        else:
            objective += "No physical exam documented."
            
        assessment = "A: "
        if patient_data.get('encounter', {}).get('assessment'):
            assessment += patient_data['encounter']['assessment']
        else:
            assessment += "No assessment documented."
            
        plan = "P: "
        if patient_data.get('encounter', {}).get('plan'):
            plan += patient_data['encounter']['plan']
        else:
            plan += "No plan documented."
            
        note = f"{patient_info}\n{encounter_info}\n\n{subjective}\n\n{objective}\n\n{assessment}\n\n{plan}"
    
    else:  # narrative format
        narrative = f"{patient_info}\n{encounter_info}\n\n"
        
        if patient_data.get('encounter', {}).get('hpi'):
            narrative += f"History of Present Illness: {patient_data['encounter']['hpi']}\n\n"
            
        if patient_data.get('encounter', {}).get('physical_exam'):
            narrative += f"Physical Examination: {patient_data['encounter']['physical_exam']}\n\n"
            
        if patient_data.get('encounter', {}).get('assessment'):
            narrative += f"Assessment: {patient_data['encounter']['assessment']}\n\n"
            
        if patient_data.get('encounter', {}).get('plan'):
            narrative += f"Plan: {patient_data['encounter']['plan']}\n"
            
        note = narrative
    
    print(f"[CLINICAL_NOTE] Generated note of length {len(note)}")
    return note

def generate_mrn() -> str:
    """Generate a unique medical record number."""
    return f"MRN{uuid.uuid4().hex[:8].upper()}"

async def analyze_image_with_qwen_api(image_bytes, prompt="Describe this medical scan in detail, including any visible abnormalities or findings:"):
    """Analyze an image using the Qwen 2.5 VL model via Hugging Face API"""
    try:
        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}"
        }
        
        # Encode the image as base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Prepare the payload
        payload = {
            "inputs": {
                "image": image_b64,
                "text": prompt
            },
            "parameters": {
                "max_new_tokens": 512,
                "temperature": 0.7,
                "top_p": 0.9,
                "do_sample": True
            }
        }
        
        # Make the API request
        response = requests.post(QWEN_API_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "Failed to generate description")
            return result.get("generated_text", "Failed to generate description")
        else:
            print(f"Error from Hugging Face API: {response.status_code}, {response.text}")
            return f"Failed to analyze image: API error {response.status_code}"
            
    except Exception as e:
        print(f"Error analyzing image with Qwen API: {str(e)}")
        return f"Failed to analyze image: {str(e)}"

def init_gemma_model():
    """Initialize the Gemma 3 12B IT model locally"""
    global gemma_model, gemma_tokenizer
    
    if not USE_LOCAL_MODEL:
        return
    
    try:
        print("Loading Gemma model locally...")
        gemma_tokenizer = AutoProcessor.from_pretrained(
            LOCAL_MODEL_NAME,
            token=HUGGINGFACE_ACCESS_TOKEN
        )
        gemma_model = Gemma3ForConditionalGeneration.from_pretrained(
            LOCAL_MODEL_NAME,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            token=HUGGINGFACE_ACCESS_TOKEN
        ).eval()
        print("Gemma model loaded successfully!")
    except Exception as e:
        print(f"Error loading Gemma model locally: {str(e)}")
        print("Will fall back to API calls")

# Add this function to initialize the Medical NER model
def init_medical_ner_model():
    """Initialize the Medical NER model for entity extraction"""
    global medical_ner_pipeline
    try:
        print("Loading Medical NER model...")
        medical_ner_pipeline = pipeline("token-classification", 
                                      model=MEDICAL_NER_MODEL, 
                                      aggregation_strategy='simple')
        print("Medical NER model loaded successfully!")
    except Exception as e:
        print(f"Error loading Medical NER model: {str(e)}")
        medical_ner_pipeline = None

def extract_medical_entities(text):
    """Extract medical entities from clinical text using DeBERTa model"""
    global medical_ner_pipeline
    
    if medical_ner_pipeline is None:
        print("Medical NER pipeline not initialized. Initializing now...")
        init_medical_ner_model()
        if medical_ner_pipeline is None:
            return {"error": "Failed to initialize Medical NER model", "entities": []}
    
    try:
        # Split text into chunks if it's too long (to prevent tokenizer overflow)
        max_chunk_length = 400  # Tokens
        chunks = []
        words = text.split()
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            if len(current_chunk) >= max_chunk_length:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        # Process each chunk
        all_results = []
        for chunk in chunks:
            results = medical_ner_pipeline(chunk)
            all_results.extend(results)
        
        # Format results
        entities = []
        for entity in all_results:
            entities.append({
                "entity_group": entity["entity_group"],
                "word": entity["word"],
                "score": round(entity["score"], 4),
                "start": entity.get("start", 0),
                "end": entity.get("end", 0)
            })
        
        # Group entities by type
        entity_groups = {}
        for entity in entities:
            group = entity["entity_group"]
            if group not in entity_groups:
                entity_groups[group] = []
            
            # Add word if not already in the list
            word = entity["word"]
            if word not in entity_groups[group]:
                entity_groups[group].append(word)
        
        return {
            "success": True,
            "entities": entities,
            "entity_groups": entity_groups
        }
    except Exception as e:
        print(f"Error extracting medical entities: {str(e)}")
        return {"error": str(e), "entities": []}
       
def analyze_image_with_gemma_local(image_pil, prompt="Describe this medical scan in detail, including any visible abnormalities or findings:"):
    global gemma_model, gemma_tokenizer
    
    if gemma_model is None or gemma_tokenizer is None:
        logger.warning("Local Gemma model not initialized. Falling back to API.")
        return "Local Gemma model not initialized. Please use API version instead."
    
    try:
        logger.info("Saving image to temporary file")
        with tempfile.NamedTemporaryFile(suffix=".jpeg", delete=False) as temp_file:
            # Convert RGBA to RGB if needed before saving as JPEG
            if image_pil.mode == 'RGBA':
                logger.info("Converting RGBA image to RGB format")
                # Create a white background
                background = Image.new('RGB', image_pil.size, (255, 255, 255))
                # Paste the image on the background (using alpha channel as mask)
                background.paste(image_pil, mask=image_pil.split()[3])
                # Save the RGB image
                background.save(temp_file, format="JPEG")
                temp_path = temp_file.name
            else:
                # For RGB or other modes compatible with JPEG
                image_pil.save(temp_file, format="JPEG")
                temp_path = temp_file.name
        
        logger.info("Preparing messages with image path")
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a medical imaging expert."}]
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": temp_path},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        logger.info("Tokenizing input")
        inputs = gemma_tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt"
        ).to(gemma_model.device, dtype=torch.bfloat16)
        
        logger.info(f"Input IDs shape: {inputs['input_ids'].shape}")
        input_len = inputs["input_ids"].shape[-1]
        
        logger.info("Generating response")
        with torch.inference_mode():
            generation = gemma_model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )
            generation = generation[0][input_len:]
        
        logger.info("Decoding response")
        response = gemma_tokenizer.decode(generation, skip_special_tokens=True)
        
        logger.info("Cleaning up temporary file")
        os.unlink(temp_path)
        
        return response
    except Exception as e:
        logger.error(f"Error analyzing image with local Gemma model: {str(e)}", exc_info=True)
        return f"Failed to analyze image locally: {str(e)}"
      
async def analyze_scan(scan, bucket):
    """Download a scan from GCS and analyze it with the configured model"""
    try:
        print(f"[SCAN_ANALYSIS] Downloading scan {scan.file_name} from GCS")
        blob = bucket.blob(scan.storage_url)
        image_bytes = blob.download_as_bytes()
        
        # Prepare prompt based on scan type
        prompt = f"This is a {scan.scan_type} medical scan. Describe in detail what you see, including any visible abnormalities, findings, or relevant medical observations:"
        
        if scan.description:
            prompt += f" Note that the scan was taken for: {scan.description}"
            
        if USE_LOCAL_MODEL and gemma_model is not None:
            # Use local Gemma model
            print(f"[SCAN_ANALYSIS] Analyzing {scan.scan_type} with local Gemma model")
            image_pil = Image.open(BytesIO(image_bytes))
            result = analyze_image_with_gemma_local(image_pil, prompt)
        else:
            # Use Qwen API
            print(f"[SCAN_ANALYSIS] Analyzing {scan.scan_type} with Qwen VL API")
            result = await analyze_image_with_qwen_api(image_bytes, prompt)
            
        print(f"[SCAN_ANALYSIS] Analysis complete for {scan.file_name}")
        print(f"[SCAN RESULTS] {scan.description}")
        print(f"[SCAN RESULTS] {result}")
        return {
            "scan_type": scan.scan_type,
            "scan_date": scan.scan_date.isoformat(),
            "file_name": scan.file_name,
            "description": scan.description,
            "analysis": result
        }
        
    except Exception as e:
        print(f"[SCAN_ANALYSIS] Error analyzing scan {scan.file_name}: {str(e)}")
        return {
            "scan_type": scan.scan_type,
            "scan_date": scan.scan_date.isoformat() if hasattr(scan, 'scan_date') else "Unknown",
            "file_name": scan.file_name,
            "description": scan.description if hasattr(scan, 'description') else "No description",
            "analysis": f"Error analyzing scan: {str(e)}"
        }

async def fetch_web_context_from_perplexity(entity_groups, scan_analyses=None, analysis_type="diagnosis"):
    """
    Fetch relevant web context from Perplexity API based on extracted entities and scan analyses
    """
    try:
        # Create a query based on the entity groups and analysis type
        if analysis_type == "diagnosis":
            # Focus query on symptoms, signs, and diagnostic findings
            query_parts = []
            
            # Add symptoms and signs
            if "SIGN_SYMPTOM" in entity_groups:
                symptoms = ", ".join(entity_groups["SIGN_SYMPTOM"][:10])  # Limit to top 10
                query_parts.append(f"symptoms: {symptoms}")
                
            # Add diseases if present
            if "DISEASE_DISORDER" in entity_groups:
                diseases = ", ".join(entity_groups["DISEASE_DISORDER"][:5])  # Limit to top 5
                query_parts.append(f"possible conditions: {diseases}")
                
            # Add diagnostic findings
            if "DIAGNOSTIC_PROCEDURE" in entity_groups and "LAB_VALUE" in entity_groups:
                query_parts.append("with abnormal laboratory findings")
                
            # Add scan findings if available
            if scan_analyses:
                query_parts.append("with imaging findings showing abnormalities")
                
            # Build the query
            base_query = "What are the most likely diagnoses for a patient with "
            refined_query = base_query + " and ".join(query_parts) + "? Provide differential diagnosis with medical reasoning."
        elif analysis_type == "risk_assessment":
            # Focus query on risk factors and preventive measures
            risk_factors = []
            
            # Add known diseases as risk factors
            if "DISEASE_DISORDER" in entity_groups:
                # Filter out generic or uninformative terms
                relevant_diseases = [d for d in entity_groups["DISEASE_DISORDER"] 
                                    if len(d) > 3 and d.lower() not in ["off", "pain", "drug", "type", "allergies"]]
                if relevant_diseases:
                    diseases = ", ".join(relevant_diseases[:5])
                    risk_factors.append(f"conditions: {diseases}")
            
            # Add medications that might indicate conditions
            if "MEDICATION" in entity_groups:
                medications = ", ".join(entity_groups["MEDICATION"][:5])
                risk_factors.append(f"medications: {medications}")
            
            # Add diagnostic results and signs/symptoms
            clinical_findings = []
            
            if "SIGN_SYMPTOM" in entity_groups:
                # Filter out generic terms
                relevant_symptoms = [s for s in entity_groups["SIGN_SYMPTOM"] 
                                    if len(s) > 3 and s.lower() not in ["pain", "soft", "oriented"]]
                if relevant_symptoms:
                    clinical_findings.extend(relevant_symptoms[:5])
            
            if "DIAGNOSTIC_PROCEDURE" in entity_groups and "LAB_VALUE" in entity_groups:
                clinical_findings.append("abnormal laboratory values")
            
            if clinical_findings:
                risk_factors.append(f"clinical findings: {', '.join(clinical_findings)}")
            
            # Extract demographic info if available (often in DETAILED_DESCRIPTION)
            demographics = []
            if "DETAILED_DESCRIPTION" in entity_groups:
                # Look for age
                for desc in entity_groups["DETAILED_DESCRIPTION"]:
                    if desc.isdigit() and 18 <= int(desc) <= 100:
                        demographics.append(f"age {desc}")
                        break
            
            # Add any findings from scans
            if scan_analyses:
                for scan in scan_analyses:
                    if "ECG" in scan.get("scan_type", ""):
                        risk_factors.append("ECG findings suggestive of cardiac issues")
                        break
                    elif "X-ray" in scan.get("scan_type", ""):
                        risk_factors.append("abnormal imaging findings")
                        break
            
            # Build the query - make it more specific and medically focused
            if risk_factors:
                base_query = "What are the cardiovascular, metabolic, and overall health risks for a patient with "
                refined_query = base_query + " and ".join(risk_factors) + "? Provide a specific clinical risk assessment with risk levels (high/moderate/low) and evidence-based preventive measures."
            else:
                # Fallback if we couldn't extract meaningful risk factors
                refined_query = "What are the common cardiovascular and metabolic risk factors and their associated preventive measures? Include risk assessment guidelines and preventive strategies."    
                


        else:  # Genetic testing (default)
            # Focus query on genetic conditions related to findings
            condition_clues = []
            
            # Add sign/symptoms that might suggest genetic conditions
            if "SIGN_SYMPTOM" in entity_groups:
                condition_clues.append(f"symptoms: {', '.join(entity_groups['SIGN_SYMPTOM'][:8])}")
                
            # Add any known diseases
            if "DISEASE_DISORDER" in entity_groups:
                condition_clues.append(f"conditions: {', '.join(entity_groups['DISEASE_DISORDER'][:5])}")
                
            # Add family history
            if "FAMILY_HISTORY" in entity_groups:
                condition_clues.append(f"family history: {', '.join(entity_groups['FAMILY_HISTORY'])}")
                
            # Build the query
            base_query = "What rare genetic conditions should be considered for a patient with "
            refined_query = base_query + " and ".join(condition_clues) + "? Focus on conditions requiring genetic testing."
            
        print(f"[PERPLEXITY] Generated query for {analysis_type}: {refined_query}")
            
        # Call Perplexity API
        perplexity_url = "https://api.perplexity.ai/chat/completions"
        perplexity_payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "Provide a comprehensive answer with relevant web sources for this query. Include citations in your response."},
                {"role": "user", "content": refined_query}
            ],
            "max_tokens": 1000,
            "temperature": 0.2,
            "return_related_questions": True,
            "stream": False
        }
        
        perplexity_headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}", 
            "Content-Type": "application/json"
        }
        
        perplexity_response = requests.post(perplexity_url, json=perplexity_payload, headers=perplexity_headers)
        
        if perplexity_response.status_code == 200:
            response_data = perplexity_response.json()
            
            if "choices" in response_data and len(response_data["choices"]) > 0:
                main_content = response_data["choices"][0]["message"]["content"]
                citations = response_data.get("citations", [])
                related_questions = response_data.get("related_questions", [])
                
                # Format the response for better integration with our system
                formatted_response = f"--- WEB CONTEXT FROM PERPLEXITY AI ---\n\n{main_content}\n\n"
                
                if citations:
                    formatted_response += "SOURCES:\n" + "\n".join([f"- {cite}" for cite in citations]) + "\n\n"
                
                print(f"[PERPLEXITY] Retrieved RESULTS {formatted_response}")
                print(f"[PERPLEXITY] Retrieved {len(main_content)} characters of web context")
                return formatted_response
            else:
                print(f"[PERPLEXITY] No content in response: {response_data}")
                return "No relevant information found from web search."
        else:
            print(f"[PERPLEXITY] API error: {perplexity_response.status_code} - {perplexity_response.text}")
            return f"Error retrieving web information: {perplexity_response.status_code}"
            
    except Exception as e:
        print(f"[PERPLEXITY] Exception: {str(e)}")
        return f"Error retrieving web information: {str(e)}"

async def enhanced_literature_retrieval(entity_groups, analysis_type, scan_analyses=None):
    """
    Perform enhanced literature retrieval using vector database instead of Perplexity API
    """
    print(f"[LIT_RETRIEVAL] Starting enhanced literature retrieval for {analysis_type}")
    
    try:
        # 1. Fetch medical articles based on entity groups
        articles = medical_literature_manager.retrieve_medical_articles(
            entity_groups=entity_groups,
            analysis_type=analysis_type,
            max_results=20
        )
        
        if not articles:
            print(f"[LIT_RETRIEVAL] No articles found, returning empty context")
            return "No relevant medical literature found for this case."
        
        print(f"[LIT_RETRIEVAL] Retrieved {len(articles)} articles")
        
        # 2. Add articles to corpus if not already present
        medical_literature_manager.add_articles_to_corpus(
            articles=articles,
            analysis_type=analysis_type
        )
        
        # 3. Create retrieval query from entity groups
        retrieval_query = medical_literature_manager.process_entity_groups_for_retrieval(
            entity_groups=entity_groups,
            analysis_type=analysis_type
        )
        
        # 4. Retrieve relevant literature chunks
        relevant_literature = medical_literature_manager.retrieve_relevant_literature(
            query=retrieval_query,
            analysis_type=analysis_type,
            top_k=7
        )
        
        # 5. Format retrieved literature into context
        context = medical_literature_manager.prepare_literature_context(relevant_literature)
        
        print(f"[LIT_RETRIEVAL] Generated context with {len(context)} characters")
        return context
        
    except Exception as e:
        print(f"[LIT_RETRIEVAL] Error in enhanced literature retrieval: {str(e)}")
        return f"Error retrieving medical literature: {str(e)}"

# Add this function to load common ICD-10 and CPT codes into the database
def generate_medical_codes(clinical_text, entity_groups=None, use_llm=True):
    """
    Generate ICD-10 and CPT codes from clinical text and extracted entities.
    
    Args:
        clinical_text (str): The clinical text from the encounter
        entity_groups (dict, optional): Pre-extracted entity groups. If None, will extract entities.
        use_llm (bool): Whether to use LLM for more accurate code generation
        
    Returns:
        dict: Dictionary with 'icd10_codes' and 'cpt_codes' lists
    """
    print(f"[AUTOCODING] Generating medical codes for text of length {len(clinical_text)}")
    
    # If entity groups not provided, extract them
    if not entity_groups:
        entity_results = extract_medical_entities(clinical_text)
        if "entity_groups" in entity_results:
            entity_groups = entity_results["entity_groups"]
        else:
            entity_groups = {}
            print(f"[AUTOCODING] Warning: Failed to extract entities, continuing with direct mapping")
    
    # Initialize response structure
    result = {
        "icd10_codes": [],
        "cpt_codes": [],
        "entity_matches": []
    }
    
    # Connect to database
    db = SessionLocal()
    
    try:
        # 1. First approach: Direct database mapping of entities to codes
        if "DISEASE_DISORDER" in entity_groups:
            for disease in entity_groups["DISEASE_DISORDER"]:
                # Look for matching ICD-10 codes in the database
                db_codes = db.query(MedicalCode).filter(
                    MedicalCode.type == "ICD-10",
                    MedicalCode.common_terms.like(f"%{disease}%")
                ).all()
                
                for code in db_codes:
                    if code.code not in [c["code"] for c in result["icd10_codes"]]:
                        result["icd10_codes"].append({
                            "code": code.code,
                            "description": code.description,
                            "matched_term": disease,
                            "confidence": "high" if disease.lower() in code.description.lower() else "medium"
                        })
                        result["entity_matches"].append(f"Matched '{disease}' to ICD-10: {code.code} ({code.description})")
        
        # Map procedures to CPT codes        
        if "PROCEDURE" in entity_groups or "DIAGNOSTIC_PROCEDURE" in entity_groups:
            procedures = entity_groups.get("PROCEDURE", []) + entity_groups.get("DIAGNOSTIC_PROCEDURE", [])
            for procedure in procedures:
                # Look for matching CPT codes in the database
                db_codes = db.query(MedicalCode).filter(
                    MedicalCode.type == "CPT",
                    MedicalCode.common_terms.like(f"%{procedure}%")
                ).all()
                
                for code in db_codes:
                    if code.code not in [c["code"] for c in result["cpt_codes"]]:
                        result["cpt_codes"].append({
                            "code": code.code,
                            "description": code.description,
                            "matched_term": procedure,
                            "confidence": "high" if procedure.lower() in code.description.lower() else "medium"
                        })
                        result["entity_matches"].append(f"Matched '{procedure}' to CPT: {code.code} ({code.description})")
        
        # 2. If use_llm is True and we don't have enough codes, use LLM to generate codes
        if use_llm and (len(result["icd10_codes"]) < 2 or len(entity_groups.get("DISEASE_DISORDER", [])) > len(result["icd10_codes"])):
            print(f"[AUTOCODING] Using LLM to generate more accurate codes")
            
            # Create a structured prompt for the LLM
            diagnoses = entity_groups.get("DISEASE_DISORDER", [])
            symptoms = entity_groups.get("SIGN_SYMPTOM", [])
            procedures = entity_groups.get("PROCEDURE", []) + entity_groups.get("DIAGNOSTIC_PROCEDURE", [])
            
            clinical_data = {
                "diagnoses": diagnoses,
                "symptoms": symptoms,
                "procedures": procedures,
                "clinical_text_excerpt": clinical_text[:500] + "..." if len(clinical_text) > 500 else clinical_text
            }
            
            # Create the prompt
            prompt = f"""
            You are a professional medical coder. Based on the provided clinical information, generate appropriate ICD-10 and CPT codes.
            
            Clinical Information:
            Diagnoses: {", ".join(diagnoses) if diagnoses else "None explicitly mentioned"}
            Symptoms: {", ".join(symptoms) if symptoms else "None explicitly mentioned"}
            Procedures: {", ".join(procedures) if procedures else "None explicitly mentioned"}
            
            Clinical Note Excerpt:
            {clinical_data['clinical_text_excerpt']}
            
            Return your response in the following JSON format:
            {{
                "icd10_codes": [
                    {{"code": "A00.0", "description": "Description of the code", "confidence": "high/medium/low"}}
                ],
                "cpt_codes": [
                    {{"code": "00100", "description": "Description of the code", "confidence": "high/medium/low"}}
                ],
                "reasoning": "Brief explanation of your code selection"
            }}
            
            For each code, include only codes that are clearly supported by the provided information.
            """
            
            # Call the LLM (using the default model set in Settings)
            try:
                response = Settings.llm.complete(prompt).text
                response = response.strip()
                
                # Try to extract JSON from the response
                if response.startswith("```json"):
                    response = response[7:]
                if response.endswith("```"):
                    response = response[:-3]
                response = response.strip()
                
                llm_result = json.loads(response)
                
                # Merge results, avoiding duplicates
                existing_icd10_codes = [c["code"] for c in result["icd10_codes"]]
                for code in llm_result.get("icd10_codes", []):
                    if code["code"] not in existing_icd10_codes:
                        result["icd10_codes"].append(code)
                        result["entity_matches"].append(f"LLM generated ICD-10: {code['code']} ({code['description']})")
                
                existing_cpt_codes = [c["code"] for c in result["cpt_codes"]]
                for code in llm_result.get("cpt_codes", []):
                    if code["code"] not in existing_cpt_codes:
                        result["cpt_codes"].append(code)
                        result["entity_matches"].append(f"LLM generated CPT: {code['code']} ({code['description']})")
                
                # Add reasoning if available
                if "reasoning" in llm_result:
                    result["reasoning"] = llm_result["reasoning"]
                    
            except Exception as e:
                print(f"[AUTOCODING] Error using LLM for code generation: {str(e)}")
                result["error"] = f"LLM code generation failed: {str(e)}"
    
    finally:
        db.close()
    
    # Format the final result for display
    result["formatted_icd10"] = "; ".join([f"{c['code']} ({c['description']})" for c in result["icd10_codes"]])
    result["formatted_cpt"] = "; ".join([f"{c['code']} ({c['description']})" for c in result["cpt_codes"]])
    
    print(f"[AUTOCODING] Generated {len(result['icd10_codes'])} ICD-10 codes and {len(result['cpt_codes'])} CPT codes")
    return result

def load_sample_medical_codes(db: Session):
    """Load a set of common ICD-10 and CPT codes into the database for testing."""
    print("[SETUP] Loading sample medical codes into database")
    
    # Check if we already have codes in the database
    existing_codes = db.query(MedicalCode).count()
    if existing_codes > 0:
        print(f"[SETUP] Database already contains {existing_codes} medical codes, skipping import")
        return
    
    # Common ICD-10 codes with descriptions and search terms
    icd10_codes = [
        {
            "code": "I10", 
            "description": "Essential (primary) hypertension",
            "category": "Cardiovascular",
            "common_terms": json.dumps(["hypertension", "high blood pressure", "HTN", "elevated blood pressure"])
        },
        {
            "code": "E11.9", 
            "description": "Type 2 diabetes mellitus without complications",
            "category": "Endocrine",
            "common_terms": json.dumps(["diabetes", "type 2 diabetes", "diabetes mellitus", "T2DM", "diabetic"])
        },
        {
            "code": "J44.9", 
            "description": "Chronic obstructive pulmonary disease, unspecified",
            "category": "Respiratory",
            "common_terms": json.dumps(["COPD", "chronic obstructive pulmonary disease", "chronic bronchitis", "emphysema"])
        },
        {
            "code": "M54.5", 
            "description": "Low back pain",
            "category": "Musculoskeletal",
            "common_terms": json.dumps(["back pain", "lower back pain", "lumbago", "lumbar pain", "LBP"])
        },
        {
            "code": "F41.9", 
            "description": "Anxiety disorder, unspecified",
            "category": "Mental Health",
            "common_terms": json.dumps(["anxiety", "anxious", "anxiety disorder", "nervousness", "panic"])
        },
        {
            "code": "F32.9", 
            "description": "Major depressive disorder, single episode, unspecified",
            "category": "Mental Health",
            "common_terms": json.dumps(["depression", "depressive", "depressed", "MDD", "depressive disorder"])
        },
        {
            "code": "J45.909", 
            "description": "Unspecified asthma, uncomplicated",
            "category": "Respiratory",
            "common_terms": json.dumps(["asthma", "asthmatic", "reactive airway", "bronchial asthma"])
        },
        {
            "code": "R50.9", 
            "description": "Fever, unspecified",
            "category": "Symptoms",
            "common_terms": json.dumps(["fever", "febrile", "pyrexia", "elevated temperature", "high temperature"])
        },
        {
            "code": "R07.9", 
            "description": "Chest pain, unspecified",
            "category": "Symptoms",
            "common_terms": json.dumps(["chest pain", "chest discomfort", "chest pressure", "chest tightness"])
        },
        {
            "code": "R51", 
            "description": "Headache",
            "category": "Symptoms",
            "common_terms": json.dumps(["headache", "head pain", "cephalgia", "cephalic pain"])
        },
        {
            "code": "N39.0", 
            "description": "Urinary tract infection, site not specified",
            "category": "Infectious",
            "common_terms": json.dumps(["UTI", "urinary tract infection", "bladder infection", "cystitis"])
        },
        {
            "code": "K21.9", 
            "description": "Gastro-esophageal reflux disease without esophagitis",
            "category": "Digestive",
            "common_terms": json.dumps(["GERD", "acid reflux", "reflux", "heartburn", "gastroesophageal reflux"])
        },
        {
            "code": "R10.9", 
            "description": "Unspecified abdominal pain",
            "category": "Symptoms",
            "common_terms": json.dumps(["abdominal pain", "stomach pain", "belly pain", "abd pain"])
        },
        {
            "code": "J00", 
            "description": "Acute nasopharyngitis [common cold]",
            "category": "Respiratory",
            "common_terms": json.dumps(["common cold", "cold", "upper respiratory infection", "URI", "nasopharyngitis"])
        },
        {
            "code": "E78.5", 
            "description": "Hyperlipidemia, unspecified",
            "category": "Endocrine",
            "common_terms": json.dumps(["hyperlipidemia", "high cholesterol", "elevated lipids", "dyslipidemia", "hypercholesterolemia"])
        }
    ]
    
    # Common CPT codes with descriptions and search terms
    cpt_codes = [
        {
            "code": "99213", 
            "description": "Office or other outpatient visit, established patient, low to moderate complexity",
            "category": "Evaluation & Management",
            "common_terms": json.dumps(["office visit", "outpatient visit", "follow-up", "check-up"])
        },
        {
            "code": "99214", 
            "description": "Office or other outpatient visit, established patient, moderate to high complexity",
            "category": "Evaluation & Management",
            "common_terms": json.dumps(["complex visit", "detailed visit", "comprehensive visit"])
        },
        {
            "code": "99203", 
            "description": "Office or other outpatient visit, new patient, detailed history and exam",
            "category": "Evaluation & Management",
            "common_terms": json.dumps(["new patient", "initial visit", "first office visit"])
        },
        {
            "code": "80053", 
            "description": "Comprehensive metabolic panel",
            "category": "Laboratory",
            "common_terms": json.dumps(["CMP", "metabolic panel", "comprehensive metabolic", "chemistry panel"])
        },
        {
            "code": "85025", 
            "description": "Complete blood count (CBC) with differential",
            "category": "Laboratory",
            "common_terms": json.dumps(["CBC", "complete blood count", "blood count", "differential"])
        },
        {
            "code": "82607", 
            "description": "Vitamin B-12 (Cyanocobalamin) level",
            "category": "Laboratory",
            "common_terms": json.dumps(["vitamin B12", "B12 level", "cobalamin", "cyanocobalamin"])
        },
        {
            "code": "71045", 
            "description": "X-ray, chest, single view",
            "category": "Radiology",
            "common_terms": json.dumps(["chest x-ray", "CXR", "chest radiograph", "chest film"])
        },
        {
            "code": "71046", 
            "description": "X-ray, chest, 2 views",
            "category": "Radiology",
            "common_terms": json.dumps(["chest x-ray 2 views", "CXR 2 views", "PA and lateral chest"])
        },
        {
            "code": "93000", 
            "description": "Electrocardiogram, complete",
            "category": "Cardiology",
            "common_terms": json.dumps(["ECG", "EKG", "electrocardiogram", "cardiac rhythm", "heart tracing"])
        },
        {
            "code": "93306", 
            "description": "Echocardiography, complete",
            "category": "Cardiology",
            "common_terms": json.dumps(["echo", "echocardiogram", "heart ultrasound", "cardiac echo"])
        },
        {
            "code": "20610", 
            "description": "Arthrocentesis, major joint or bursa",
            "category": "Procedures",
            "common_terms": json.dumps(["joint injection", "joint aspiration", "knee injection", "shoulder injection"])
        },
        {
            "code": "96372", 
            "description": "Therapeutic, prophylactic, or diagnostic injection; subcutaneous or intramuscular",
            "category": "Procedures",
            "common_terms": json.dumps(["injection", "IM injection", "shot", "intramuscular", "subcutaneous"])
        },
        {
            "code": "90471", 
            "description": "Immunization administration, one vaccine",
            "category": "Preventive",
            "common_terms": json.dumps(["vaccine", "vaccination", "immunization", "vaccine administration"])
        },
        {
            "code": "99397", 
            "description": "Periodic comprehensive preventive E/M, established patient, 65+ years",
            "category": "Preventive",
            "common_terms": json.dumps(["annual exam", "physical", "preventive visit", "wellness visit", "annual physical"])
        },
        {
            "code": "99213-GT", 
            "description": "Office or other outpatient visit via telehealth",
            "category": "Telehealth",
            "common_terms": json.dumps(["telehealth", "telemedicine", "virtual visit", "video visit", "remote visit"])
        }
    ]
    
    # Add ICD-10 codes to database
    for code_data in icd10_codes:
        db_code = MedicalCode(
            id=str(uuid.uuid4()),
            code=code_data["code"],
            type="ICD-10",
            description=code_data["description"],
            category=code_data["category"],
            common_terms=code_data["common_terms"]
        )
        db.add(db_code)
    
    # Add CPT codes to database
    for code_data in cpt_codes:
        db_code = MedicalCode(
            id=str(uuid.uuid4()),
            code=code_data["code"],
            type="CPT",
            description=code_data["description"],
            category=code_data["category"],
            common_terms=code_data["common_terms"]
        )
        db.add(db_code)
    
    db.commit()
    print(f"[SETUP] Added {len(icd10_codes)} ICD-10 codes and {len(cpt_codes)} CPT codes to database")

# Helper function to calculate age from date of birth
def calculate_age(dob):
    if not dob:
        return None
        
    try:
        # Convert string to date if needed
        if isinstance(dob, str):
            birth_date = datetime.strptime(dob, '%Y-%m-%d')
        else:
            birth_date = dob
            
        today = datetime.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except Exception:
        return None

#Copilot
async def gather_context_data(db: Session, patient_id: Optional[str] = None, 
                              encounter_id: Optional[str] = None, 
                              current_view: str = "unknown",
                              view_mode: str = "list") -> Dict[str, Any]:
    """
    Gather relevant context data based on what the user is currently viewing.
    Handles both list views (multiple patients) and detail views (specific patient).
    """
    context_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "current_view": current_view,
        "view_mode": view_mode
    }
    
    # If in list view mode, gather summary data for the current view
    if view_mode == "list":
        print(f'[VIEW MODE COPILOT] {view_mode}')
        if current_view == "encounters":
            # Get recent encounters summary
            recent_encounters = db.query(Encounter).order_by(Encounter.encounter_date.desc()).limit(10).all()
            
            context_data["recent_encounters"] = [{
                "id": encounter.id,
                "date": encounter.encounter_date.isoformat(),
                "patient_id": encounter.patient_id,
                "patient_name": get_patient_name(db, encounter.patient_id),
                "chief_complaint": encounter.chief_complaint,
                "encounter_type": encounter.encounter_type
            } for encounter in recent_encounters]
            
            # Get encounter statistics
            encounter_count = db.query(func.count(Encounter.id)).scalar()
            encounter_types = db.query(Encounter.encounter_type, func.count(Encounter.id)).\
                              group_by(Encounter.encounter_type).all()
            
            context_data["encounter_stats"] = {
                "total_count": encounter_count,
                "by_type": {t[0]: t[1] for t in encounter_types}
            }
            
        elif current_view == "lab-results":
            # Get recent lab results summary - FIXED: direct join with LabOrder to properly fetch results
            recent_labs = db.query(LabResult).join(LabOrder, LabResult.lab_order_id == LabOrder.id).\
                          order_by(LabResult.result_date.desc()).limit(10).all()
            
            context_data["recent_lab_results"] = [{
                "id": lab.id,
                "date": lab.result_date.isoformat(),
                "patient_id": get_lab_order_patient_id(db, lab.lab_order_id),
                "patient_name": get_patient_name_from_lab(db, lab.lab_order_id),
                "test_name": get_lab_test_name(db, lab.lab_order_id),
                "result_value": lab.result_value,
                "unit": lab.unit,
                "reference_range": lab.reference_range,
                "abnormal_flag": lab.abnormal_flag
            } for lab in recent_labs]
            
            # Get lab statistics
            lab_count = db.query(func.count(LabResult.id)).scalar()
            abnormal_count = db.query(func.count(LabResult.id)).\
                             filter(LabResult.abnormal_flag.in_(["High", "Low", "Abnormal"])).scalar()
            
            context_data["lab_stats"] = {
                "total_count": lab_count,
                "abnormal_count": abnormal_count,
                "abnormal_percentage": round((abnormal_count / lab_count * 100) if lab_count > 0 else 0, 1)
            }
    
        elif current_view == "patients":
            # Get recent patients summary
            recent_patients = db.query(Patient).order_by(Patient.created_at.desc()).limit(10).all()
            
            context_data["recent_patients"] = [{
                "id": patient.id,
                "name": f"{patient.first_name} {patient.last_name}",
                "mrn": patient.mrn,
                "gender": patient.gender,
                "age": calculate_age(patient.date_of_birth),
                "date_of_birth": patient.date_of_birth.isoformat() if hasattr(patient.date_of_birth, 'isoformat') else patient.date_of_birth
            } for patient in recent_patients]
            
            # Get patient statistics
            patient_count = db.query(func.count(Patient.id)).scalar()
            gender_counts = db.query(Patient.gender, func.count(Patient.id)).\
                            group_by(Patient.gender).all()
            
            # Calculate age distribution
            current_year = datetime.utcnow().year
            age_ranges = {
                "0-18": 0,
                "19-44": 0,
                "45-64": 0,
                "65+": 0
            }
            
            all_patients = db.query(Patient.date_of_birth).all()
            for patient in all_patients:
                if patient.date_of_birth:
                    age = calculate_age(patient.date_of_birth)
                    if age <= 18:
                        age_ranges["0-18"] += 1
                    elif age <= 44:
                        age_ranges["19-44"] += 1
                    elif age <= 64:
                        age_ranges["45-64"] += 1
                    else:
                        age_ranges["65+"] += 1
            
            context_data["patient_stats"] = {
                "total_count": patient_count,
                "by_gender": {g[0]: g[1] for g in gender_counts},
                "age_distribution": age_ranges
            }
            
    # Calculate recent activity
    recent_encounters_count = db.query(func.count(Encounter.id)).\
                             filter(Encounter.encounter_date >= datetime.utcnow() - timedelta(days=30)).scalar()
    recent_labs_count = db.query(func.count(LabResult.id)).\
                        join(LabOrder).\
                        filter(LabResult.result_date >= datetime.utcnow() - timedelta(days=30)).scalar()
    
    context_data["recent_activity"] = {
        "encounters_last_30_days": recent_encounters_count,
        "lab_results_last_30_days": recent_labs_count
    }
    
    # If we have a specific patient, get patient-specific data
    if patient_id:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if patient:
            # Add patient basics
            context_data["patient"] = {
                "id": patient.id,
                "name": f"{patient.first_name} {patient.last_name}",
                "age": calculate_age(patient.date_of_birth),
                "gender": patient.gender,
                "mrn": patient.mrn
            }
            
            # Adding encounters details to the logic
            encounters = db.query(Encounter).filter(Encounter.patient_id == patient_id).order_by(Encounter.encounter_date).all()
            
            # Include detailed encounter information
            context_data["encounters"] = [{
                "id": encounter.id,
                "date": encounter.encounter_date.isoformat(),
                "encounter_type": encounter.encounter_type,
                "chief_complaint": encounter.chief_complaint,
                "vital_signs": json.loads(encounter.vital_signs) if encounter.vital_signs else {},
                "hpi": encounter.hpi,
                "ros": encounter.ros,
                "physical_exam": encounter.physical_exam,
                "assessment": encounter.assessment,
                "plan": encounter.plan,
                "diagnosis_codes": encounter.diagnosis_codes,
                "followup_instructions": encounter.followup_instructions
            } for encounter in encounters]
            
            # Add a latest encounter field for quick reference
            if encounters:
                latest_encounter = max(encounters, key=lambda e: e.encounter_date)
                context_data["latest_encounter"] = {
                    "id": latest_encounter.id,
                    "date": latest_encounter.encounter_date.isoformat(),
                    "encounter_type": latest_encounter.encounter_type,
                    "chief_complaint": latest_encounter.chief_complaint
                }
                
                # Set specific flags to make it absolutely clear in the prompt
                context_data["has_latest_encounter"] = True
                context_data["latest_chief_complaint"] = latest_encounter.chief_complaint
                context_data["latest_encounter_date"] = latest_encounter.encounter_date.isoformat()
            
            # Get medical history
            medical_history = db.query(MedicalHistory).filter(MedicalHistory.patient_id == patient_id).all()
            context_data["medical_history"] = [{
                "condition": history.condition,
                "status": history.status
            } for history in medical_history]
            
            # Get medications
            medications = db.query(Medication).filter(Medication.patient_id == patient_id).all()
            context_data["medications"] = [{
                "name": med.name,
                "dosage": med.dosage,
                "frequency": med.frequency,
                "active": med.active
            } for med in medications]
            
            # Get allergies
            allergies = db.query(Allergy).filter(Allergy.patient_id == patient_id).all()
            context_data["allergies"] = [{
                "allergen": allergy.allergen,
                "reaction": allergy.reaction,
                "severity": allergy.severity
            } for allergy in allergies]
            
            # FIXED: Get lab results directly for this patient
            # This mirrors how lab results are fetched in other parts of the application
            lab_results = []
            
            # First get all lab orders for the patient
            lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
            context_data["lab_orders"] = [{
                "id": order.id,
                "test_name": order.test_name,
                "status": order.status,
                "order_date": order.order_date.isoformat() if order.order_date else None
            } for order in lab_orders]
            print(f'[LAB COPILOT] {lab_orders}')
            # Then get all results for those orders
            for order in lab_orders:
                order_results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
                for result in order_results:
                    lab_results.append({
                        "id": result.id,
                        "test_name": order.test_name,
                        "result_value": result.result_value,
                        "unit": result.unit,
                        "reference_range": result.reference_range,
                        "abnormal_flag": result.abnormal_flag,
                        "result_date": result.result_date.isoformat() if result.result_date else None
                    })
            print(f'[LAB COPILOT] {lab_results}')
            # Store both raw data and processed summary
            context_data["lab_results"] = lab_results
            
            # Add a summary field that matches what's checked in the Copilot response
            context_data["has_lab_results"] = len(lab_results) > 0
            context_data["lab_results_count"] = len(lab_results)
    
    # If we have an encounter ID but no patient ID, extract the patient ID from the encounter
    elif encounter_id and not patient_id:
        encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
        if encounter:
            # Add encounter data
            context_data["encounter"] = {
                "id": encounter.id,
                "date": encounter.encounter_date.isoformat(),
                "chief_complaint": encounter.chief_complaint,
                "encounter_type": encounter.encounter_type,
                "vital_signs": json.loads(encounter.vital_signs) if encounter.vital_signs else {},
                "assessment": encounter.assessment,
                "plan": encounter.plan
            }
            
            # Get patient data for this encounter
            patient = db.query(Patient).filter(Patient.id == encounter.patient_id).first()
            if patient:
                context_data["patient"] = {
                    "id": patient.id,
                    "name": f"{patient.first_name} {patient.last_name}",
                    "age": calculate_age(patient.date_of_birth),
                    "gender": patient.gender,
                    "mrn": patient.mrn
                }
                
                # Add this for convenience
                context_data["patient_id"] = patient.id
                
                # FIXED: Get lab results for this patient as well
                lab_results = []
                lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient.id).all()
                
                for order in lab_orders:
                    results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
                    for result in results:
                        lab_results.append({
                            "test_name": order.test_name,
                            "result_value": result.result_value,
                            "unit": result.unit,
                            "reference_range": result.reference_range,
                            "abnormal_flag": result.abnormal_flag,
                            "result_date": result.result_date.isoformat()
                        })
                
                context_data["lab_results"] = lab_results
    
    # Add view-specific data
    if current_view == "encounters" and encounter_id:
        # Get the specific encounter
        encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
        if encounter:
            context_data["current_encounter"] = {
                "id": encounter.id,
                "date": encounter.encounter_date.isoformat(),
                "chief_complaint": encounter.chief_complaint,
                "vital_signs": json.loads(encounter.vital_signs) if encounter.vital_signs else {},
                "hpi": encounter.hpi,
                "assessment": encounter.assessment,
                "plan": encounter.plan
            }
    
    elif current_view == "lab-results" and view_mode == "detail" and patient_id:
        # FIXED: Get lab results for specific patient using the same approach as other parts of the app
        lab_results = []
        lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
        
        for order in lab_orders:
            results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
            for result in results:
                lab_results.append({
                    "test_name": order.test_name,
                    "result_value": result.result_value,
                    "unit": result.unit,
                    "reference_range": result.reference_range,
                    "abnormal_flag": result.abnormal_flag,
                    "result_date": result.result_date.isoformat()
                })
        print(f'[FETCHED LAB RESULTS COPILOT] {lab_results}')
        # Sort by date and take most recent 10
        lab_results.sort(key=lambda x: x.get("result_date", ""), reverse=True)
        context_data["patient_lab_results"] = lab_results[:10]
    
    return context_data

# survey


# Endpoint to get all surveys
@app.get("/api/surveys", response_model=List[dict])
async def get_surveys(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all surveys for the current user's organization"""
    surveys = db.query(Survey).filter(Survey.organization_id == current_user.organization_id).all()
    
    return [{
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "category": survey.category,
        "created_at": survey.created_at.isoformat(),
        "questions_count": survey.questions_count,
        "responses_count": survey.responses_count
    } for survey in surveys]

# Create new survey
@app.post("/api/surveys", response_model=dict)
async def create_survey(survey: SurveyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new survey"""
    survey_id = str(uuid.uuid4())
    
    # Create survey record
    db_survey = Survey(
        id=survey_id,
        title=survey.title,
        description=survey.description,
        category=survey.category,
        questions_count=len(survey.questions),
        responses_count=0,
        organization_id=current_user.organization_id,
        created_by=current_user.id
    )
    
    db.add(db_survey)
    
    # Create questions if provided
    for i, question_data in enumerate(survey.questions):
        question_id = str(uuid.uuid4())
        options_json = json.dumps(question_data.get("options", []))
        
        db_question = SurveyQuestion(
            id=question_id,
            survey_id=survey_id,
            text=question_data.get("text", ""),
            type=question_data.get("type", "text"),
            options=options_json,
            order=i
        )
        
        db.add(db_question)
    
    db.commit()
    db.refresh(db_survey)
    
    return {
        "id": db_survey.id,
        "title": db_survey.title,
        "description": db_survey.description,
        "category": db_survey.category,
        "created_at": db_survey.created_at.isoformat(),
        "questions_count": db_survey.questions_count,
        "responses_count": db_survey.responses_count
    }

# Get a specific survey with questions
@app.get("/api/surveys/{survey_id}", response_model=dict)
async def get_survey(survey_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a specific survey with its questions"""
    print(f"DEBUG: User accessing survey {survey_id}")
    print(f"DEBUG: User ID: {current_user.id}, Username: {current_user.username}")
    print(f"DEBUG: User organization: {current_user.organization_id}")
    
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.organization_id == current_user.organization_id).first()
    
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    # Get questions
    questions = db.query(SurveyQuestion).filter(SurveyQuestion.survey_id == survey_id).order_by(SurveyQuestion.order).all()
    
    questions_list = []
    for question in questions:
        # Parse options from JSON
        try:
            options = json.loads(question.options) if question.options else []
        except:
            options = []
            
        questions_list.append({
            "id": question.id,
            "text": question.text,
            "type": question.type,
            "options": options
        })
    
    return {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "category": survey.category,
        "created_at": survey.created_at.isoformat(),
        "questions_count": survey.questions_count,
        "responses_count": survey.responses_count,
        "questions": questions_list
    }

# Update a survey
@app.put("/api/surveys/{survey_id}", response_model=dict)
async def update_survey(
    survey_id: str, 
    survey_update: SurveyUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Update a survey's basic information and questions"""
    print(f"Received update for survey {survey_id}")
    print(f"Update data: {survey_update}")
    print(f"Update data: {survey_update.questions}")
    print(f"Questions included: {hasattr(survey_update, 'questions')}")
    
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.organization_id == current_user.organization_id).first()
    
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    # Update fields if provided
    if survey_update.title is not None:
        survey.title = survey_update.title
    
    if survey_update.description is not None:
        survey.description = survey_update.description
    
    if survey_update.category is not None:
        survey.category = survey_update.category
    
    # Update questions if provided
    if hasattr(survey_update, 'questions') and survey_update.questions is not None:
        # First, clear existing questions
        db.query(SurveyQuestion).filter(SurveyQuestion.survey_id == survey_id).delete()
        
        # Then add new questions
        for i, question_data in enumerate(survey_update.questions):
            question_id = str(uuid.uuid4())
            
            # Handle options format - ensure it's a JSON string
            options = question_data.get("options", [])
            options_json = json.dumps(options) if isinstance(options, list) else options
            
            db_question = SurveyQuestion(
                id=question_id,
                survey_id=survey_id,
                text=question_data.get("text", ""),
                type=question_data.get("type", "text"),
                options=options_json,
                order=i
            )
            
            db.add(db_question)
        
        # Update the questions_count
        survey.questions_count = len(survey_update.questions)
    
    survey.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(survey)
    
    # Get questions and format for response
    questions = db.query(SurveyQuestion).filter(
        SurveyQuestion.survey_id == survey_id
    ).order_by(SurveyQuestion.order).all()
    
    formatted_questions = []
    for question in questions:
        try:
            options = json.loads(question.options) if question.options else []
        except:
            options = []
            
        formatted_questions.append({
            "id": question.id,
            "text": question.text,
            "type": question.type,
            "options": options
        })
    
    return {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "category": survey.category,
        "questions": formatted_questions,
        "questions_count": survey.questions_count,
        "updated_at": survey.updated_at.isoformat(),
        "message": "Survey updated successfully"
    }

# Add a question to a survey
@app.post("/api/surveys/{survey_id}/questions", response_model=dict)
async def add_survey_question(
    survey_id: str,
    question: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new question to a survey"""
    # Check if survey exists and belongs to user's organization
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.organization_id == current_user.organization_id).first()
    
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    # Get current max order
    max_order_result = db.query(func.max(SurveyQuestion.order)).filter(SurveyQuestion.survey_id == survey_id).first()
    next_order = (max_order_result[0] or -1) + 1
    
    # Create question
    question_id = str(uuid.uuid4())
    options_json = json.dumps(question.options)
    
    db_question = SurveyQuestion(
        id=question_id,
        survey_id=survey_id,
        text=question.text,
        type=question.type,
        options=options_json,
        order=next_order
    )
    
    db.add(db_question)
    
    # Update question count
    survey.questions_count += 1
    survey.updated_at = datetime.utcnow()
    
    db.commit()
    
    # Get updated survey with questions
    questions = db.query(SurveyQuestion).filter(SurveyQuestion.survey_id == survey_id).order_by(SurveyQuestion.order).all()
    
    questions_list = []
    for q in questions:
        try:
            options = json.loads(q.options) if q.options else []
        except:
            options = []
            
        questions_list.append({
            "id": q.id,
            "text": q.text,
            "type": q.type,
            "options": options
        })
    
    return {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "category": survey.category,
        "questions_count": survey.questions_count,
        "questions": questions_list
    }

# Delete a question from a survey
@app.delete("/api/surveys/{survey_id}/questions/{question_id}", response_model=dict)
async def delete_survey_question(
    survey_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a question from a survey"""
    # Check if survey exists and belongs to user's organization
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.organization_id == current_user.organization_id).first()
    
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    # Check if question exists
    question = db.query(SurveyQuestion).filter(SurveyQuestion.id == question_id, SurveyQuestion.survey_id == survey_id).first()
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Delete question
    db.delete(question)
    
    # Update question count
    survey.questions_count -= 1
    survey.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "Question deleted successfully",
        "survey_id": survey_id,
        "question_id": question_id
    }

# Send survey (placeholder endpoint)
@app.post("/api/surveys/{survey_id}/send", response_model=dict)
async def send_survey(
    survey_id: str,
    recipients: List[str] = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a survey to specified recipients"""
    # Check if survey exists and belongs to user's organization
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.organization_id == current_user.organization_id).first()
    
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    # In a real implementation, you would send emails or notifications here
    # For now, we'll just return a success message
    
    return {
        "message": f"Survey sent to {len(recipients)} recipients",
        "survey_id": survey_id,
        "recipients": recipients
    }

# Helper functions
def get_patient_name(db: Session, patient_id: str) -> str:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient:
        return f"{patient.first_name} {patient.last_name}"
    return "Unknown Patient"

def get_lab_order_patient_id(db: Session, lab_order_id: str) -> str:
    lab_order = db.query(LabOrder).filter(LabOrder.id == lab_order_id).first()
    if lab_order:
        return lab_order.patient_id
    return None

def get_patient_name_from_lab(db: Session, lab_order_id: str) -> str:
    lab_order = db.query(LabOrder).filter(LabOrder.id == lab_order_id).first()
    if lab_order:
        return get_patient_name(db, lab_order.patient_id)
    return "Unknown Patient"

def get_lab_test_name(db: Session, lab_order_id: str) -> str:
    lab_order = db.query(LabOrder).filter(LabOrder.id == lab_order_id).first()
    if lab_order:
        return lab_order.test_name
    return "Unknown Test"

def create_query_prompt(context_data: Dict[str, Any], query: str, view_mode: str) -> str:
    """
    Create a prompt for the LLM based on the user's specific query and context,
    handling both list and detail views.
    """
    # Base prompt structure
    prompt = f"""
    You are an AI assistant for healthcare professionals using an Electronic Health Record (EHR) system.
    Answer the following question based on the available data and clinical context provided.
    
    CURRENT VIEW: {context_data.get('current_view', 'unknown')}
    VIEW MODE: {view_mode}
    TIMESTAMP: {context_data.get('timestamp', datetime.utcnow().isoformat())}
    """
    
    # Add patient-specific information if available
    if 'patient' in context_data:
        prompt += f"\nPATIENT INFORMATION:\n{json.dumps(context_data.get('patient', {}), indent=2)}"
    
    # Add view-specific relevant data
    if view_mode == "list":
        if context_data.get('current_view') == "encounters" and 'recent_encounters' in context_data:
            prompt += f"\n\nRECENT ENCOUNTERS:\n{json.dumps(context_data.get('recent_encounters', []), indent=2)}"
            prompt += f"\n\nENCOUNTER STATISTICS:\n{json.dumps(context_data.get('encounter_stats', {}), indent=2)}"
        
        elif context_data.get('current_view') == "lab-results" and 'recent_lab_results' in context_data:
            prompt += f"\n\nRECENT LAB RESULTS:\n{json.dumps(context_data.get('recent_lab_results', []), indent=2)}"
            prompt += f"\n\nLAB STATISTICS:\n{json.dumps(context_data.get('lab_stats', {}), indent=2)}"
        elif context_data.get('current_view') == "patients" and 'recent_patients' in context_data:
            prompt += f"\n\nRECENT PATIENTS:\n{json.dumps(context_data.get('recent_patients', []), indent=2)}"
            prompt += f"\n\nPATIENT STATISTICS:\n{json.dumps(context_data.get('patient_stats', {}), indent=2)}"
            prompt += f"\n\nRECENT ACTIVITY:\n{json.dumps(context_data.get('recent_activity', {}), indent=2)}"

    else:
        # For patient detail mode, add more specific context
        if 'current_encounter' in context_data:
            prompt += f"\n\nCURRENT ENCOUNTER:\n{json.dumps(context_data.get('current_encounter', {}), indent=2)}"
        
        if 'medical_history' in context_data:
            prompt += f"\n\nMEDICAL HISTORY:\n{json.dumps(context_data.get('medical_history', []), indent=2)}"
        
        if 'medications' in context_data:
            prompt += f"\n\nMEDICATIONS:\n{json.dumps(context_data.get('medications', []), indent=2)}"
        
        if 'allergies' in context_data:
            prompt += f"\n\nALLERGIES:\n{json.dumps(context_data.get('allergies', []), indent=2)}"
        
        if 'patient_lab_results' in context_data:
            prompt += f"\n\nLABORATORY RESULTS:\n{json.dumps(context_data.get('patient_lab_results', []), indent=2)}"

        if 'encounters' in context_data:
            encounters = context_data.get('encounters', [])
            prompt += f"\n\nPATIENT ENCOUNTERS ({len(encounters)} total):"
            for i, enc in enumerate(encounters):
                prompt += f"\n\nEncounter {i+1} - {enc.get('date')}:"
                prompt += f"\n  Type: {enc.get('encounter_type', 'Unknown')}"
                prompt += f"\n  Chief Complaint: {enc.get('chief_complaint', 'None documented')}"
                if enc.get('assessment'):
                    prompt += f"\n  Assessment: {enc.get('assessment')}"
                if enc.get('plan'):
                    prompt += f"\n  Plan: {enc.get('plan')}"
        
        if 'lab_results' in context_data:
            lab_results = context_data.get('lab_results', [])
            prompt += f"\n\nLAB RESULTS: This patient has {len(lab_results)} lab result(s) available.\n"
            prompt += f"{json.dumps(context_data.get('lab_results', []), indent=2)}" 
    # Add the user's query
    prompt += f"\n\nUSER QUESTION: {query}"
    
    # Add response formatting instructions
    prompt += """
    
    Please respond with clinically relevant and accurate information. Format your response as a JSON with these fields:
    1. "answer": Your direct answer to the question
    2. "suggestions": List of follow-up actions or questions (max 3)
    3. "references": Any specific data points you referenced (e.g., "Glucose level from 2023-04-05")
    
    Only include factual information you can determine from the provided data. If you cannot answer with certainty, say so clearly.
    """
    
    return prompt

def create_insight_prompt(context_data: Dict[str, Any], current_view: str) -> str:
    """
    Create a prompt for the LLM to generate proactive insights based on context.
    """
    prompt = f"""
    You are an AI assistant for healthcare professionals using an Electronic Health Record (EHR) system.
    Generate helpful insights based on the patient data and current view in the EHR.
    
    CURRENT VIEW: {current_view}
    
    PATIENT INFORMATION:
    {json.dumps(context_data.get('patient', {}), indent=2)}
    
    RELEVANT CLINICAL DATA:
    {json.dumps({k: v for k, v in context_data.items() if k not in ['current_view', 'patient', 'timestamp']}, indent=2)}
    
    Based on the current view ({current_view}) and available patient data, provide:
    
    1. A key observation that might be helpful to the healthcare provider
    2. Potential action items or considerations
    3. Any relevant clinical insights (e.g., potential drug interactions, concerning lab trends, etc.)
    
    Format your response as a JSON with these fields:
    1. "key_observation": One important observation based on the data
    2. "suggestions": List of actionable suggestions (max 3)
    3. "insights": Any clinical patterns or issues to be aware of
    4. "references": Specific data points you referenced
    
    Only include factual information you can determine from the provided data. Focus on being clinically relevant and practical.
    """
    return prompt

def parse_copilot_response(response: str) -> Dict[str, Any]:
    """
    Parse the LLM response into a structured format.
    """
    # Clean up response if it's wrapped in markdown code blocks or similar
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    if response.endswith("```"):
        response = response[:-3]
    response = response.strip()
    
    try:
        # Parse as JSON
        result = json.loads(response)
        return result
    except json.JSONDecodeError:
        # If not valid JSON, create a simple structure
        return {
            "answer": response,
            "suggestions": [],
            "references": []
        }


# API endpoints: Authentication
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Users
# Modified version of the create_user endpoint
# Modified version of the create_user endpoint
@app.post("/api/users", response_model=dict)
async def create_user(user: UserCreate, db = Depends(get_db)):
    # Check if user already exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash the password for Homosapiens
    hashed_password = get_password_hash(user.password)
    
     # Register the user with Telephone AI in the background
    # This won't block the response
    telephone_result = await register_with_telephone_ai(
        email=user.email,
        password=user.password,
        name=user.full_name, 
        organization_id=user.organization_id  # Add this parameter

    )
    # Create user in Homosapiens database
    db_user = User(
        id=str(uuid.uuid4()),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        is_doctor=user.is_doctor,
        organization_id=user.organization_id,
        role=user.role,
        telephone_ai_token= telephone_result.get("telephone_ai_token"),
        telephone_ai_user_id= telephone_result.get("telephone_ai_user_id")
        
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
   
    
    # Return response immediately without waiting for Telephone AI registration
    return {
        "id": db_user.id,
        "username": db_user.username,
        "email": db_user.email,
        "full_name": db_user.full_name,
        "is_doctor": db_user.is_doctor,
        "organization_id": db_user.organization_id,
        "telephone_ai_token": telephone_result.get("telephone_ai_token"),  # Include this!
        "telephone_ai_user_id": telephone_result.get("telephone_ai_user_id")  # Include this!

    }


# Make sure to add this import at the top of the file with other imports

@app.get("/api/users/me", response_model=dict)
async def read_users_me(current_user = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_doctor": current_user.is_doctor,
                "organization_id": current_user.organization_id,  # Add this line
          "telephone_ai_token": current_user.telephone_ai_token,
        "telephone_ai_user_id": current_user.telephone_ai_user_id
    }

# Patients
class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    primary_care_provider: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

@app.put("/api/patients/{patient_id}", response_model=dict)
async def update_patient(
    patient_id: str,
    patient_update: PatientUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Check if patient exists
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Check if user has access to this patient
    if not current_user.is_doctor and not user_has_patient_access(db, current_user.id, patient_id):
        raise HTTPException(status_code=403, detail="You don't have access to this patient")
    
    # Check if patient belongs to user's organization
    if db_patient.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Patient does not belong to your organization")
    
    # Update fields that were provided
    update_data = patient_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_patient, key, value)
    
    db.commit()
    db.refresh(db_patient)
    
    # Update JSON file
    patient_path = f"patients/{db_patient.id}.json"
    with open(patient_path, "w") as f:
        patient_dict = {
            "id": db_patient.id,
            "mrn": db_patient.mrn,
            "first_name": db_patient.first_name,
            "last_name": db_patient.last_name,
            "date_of_birth": db_patient.date_of_birth,
            "gender": db_patient.gender,
            "address": db_patient.address,
            "phone": db_patient.phone,
            "email": db_patient.email,
            "insurance_provider": db_patient.insurance_provider,
            "insurance_id": db_patient.insurance_id,
            "primary_care_provider": db_patient.primary_care_provider,
            "emergency_contact_name": db_patient.emergency_contact_name,
            "emergency_contact_phone": db_patient.emergency_contact_phone,
            "created_at": db_patient.created_at.isoformat(),
            "updated_at": db_patient.updated_at.isoformat(),
            "organization_id": db_patient.organization_id
        }
        json.dump(patient_dict, f, indent=2)
    
    return {
        "id": db_patient.id,
        "mrn": db_patient.mrn,
        "first_name": db_patient.first_name,
        "last_name": db_patient.last_name,
        "date_of_birth": db_patient.date_of_birth,
        "gender": db_patient.gender,
        "message": "Patient updated successfully"
    }

@app.post("/api/patients", response_model=dict)
async def create_patient(patient: PatientCreate, db = Depends(get_db), current_user = Depends(get_current_user)):
    mrn = generate_mrn()
    
    db_patient = Patient(
        id=str(uuid.uuid4()),
        mrn=mrn,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        address=patient.address,
        phone=patient.phone,
        email=patient.email,
        insurance_provider=patient.insurance_provider,
        insurance_id=patient.insurance_id,
        primary_care_provider=patient.primary_care_provider,
        emergency_contact_name=patient.emergency_contact_name,
        emergency_contact_phone=patient.emergency_contact_phone,
        organization_id=current_user.organization_id

    )
    
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    
    # Save as JSON for reference
    patient_path = f"patients/{db_patient.id}.json"
    with open(patient_path, "w") as f:
        patient_dict = {
            "id": db_patient.id,
            "mrn": db_patient.mrn,
            "first_name": db_patient.first_name,
            "last_name": db_patient.last_name,
            "date_of_birth": db_patient.date_of_birth,
            "gender": db_patient.gender,
            "address": db_patient.address,
            "phone": db_patient.phone,
            "email": db_patient.email,
            "insurance_provider": db_patient.insurance_provider,
            "insurance_id": db_patient.insurance_id,
            "primary_care_provider": db_patient.primary_care_provider,
            "emergency_contact_name": db_patient.emergency_contact_name,
            "emergency_contact_phone": db_patient.emergency_contact_phone,
            "created_at": db_patient.created_at.isoformat(),
            "updated_at": db_patient.updated_at.isoformat(),
            "organization_id": db_patient.organization_id

        }
        json.dump(patient_dict, f, indent=2)
    
    return {
        "id": db_patient.id,
        "mrn": db_patient.mrn,
        "first_name": db_patient.first_name,
        "last_name": db_patient.last_name,
        "date_of_birth": db_patient.date_of_birth,
        "gender": db_patient.gender,
        "message": "Patient created successfully"
    }


@app.get("/api/patients", response_model=List[dict])
async def get_patients(db = Depends(get_db), current_user = Depends(get_current_user)):
    # Doctors and admins can see all patients
    if current_user.is_doctor:
        # patients = db.query(Patient).all()
        patients = db.query(Patient).filter(Patient.organization_id == current_user.organization_id).all()

    else:
        # Regular users can only see patients they have access to
        access_records = db.query(UserPatientAccess).filter(
            UserPatientAccess.user_id == current_user.id
        ).all()
        
        patient_ids = [record.patient_id for record in access_records]
        # patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
        patients = db.query(Patient).filter(
            Patient.id.in_(patient_ids),
            Patient.organization_id == current_user.organization_id
        ).all()
    
    return [{
        "id": patient.id,
        "mrn": patient.mrn,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender
    } for patient in patients]

@app.get("/api/patients/{patient_id}", response_model=dict)
async def get_patient(patient_id: str, db = Depends(get_db), current_user = Depends(get_current_user)):
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Check if user has access to this patient
    if not current_user.is_doctor and not user_has_patient_access(db, current_user.id, patient_id):
        raise HTTPException(status_code=403, detail="You don't have access to this patient")
    
    # Get related data
    encounters = db.query(Encounter).filter(Encounter.patient_id == patient_id).all()
    medical_history = db.query(MedicalHistory).filter(MedicalHistory.patient_id == patient_id).all()
    family_history = db.query(FamilyHistory).filter(FamilyHistory.patient_id == patient_id).all()
    medications = db.query(Medication).filter(Medication.patient_id == patient_id).all()
    allergies = db.query(Allergy).filter(Allergy.patient_id == patient_id).all()
    scans = db.query(PatientScan).filter(PatientScan.patient_id == patient_id).all()

    # Get lab orders and results
    lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
    lab_results = []
    for order in lab_orders:
        results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
        lab_results.extend(results)
    
    return {
        "id": patient.id,
        "mrn": patient.mrn,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "address": patient.address,
        "phone": patient.phone,
        "email": patient.email,
        "insurance_provider": patient.insurance_provider,
        "insurance_id": patient.insurance_id,
        "primary_care_provider": patient.primary_care_provider,
        "emergency_contact_name": patient.emergency_contact_name,
        "emergency_contact_phone": patient.emergency_contact_phone,
        "encounters": [{
            "id": encounter.id,
            "encounter_date": encounter.encounter_date.isoformat(),
            "encounter_type": encounter.encounter_type,
            "chief_complaint": encounter.chief_complaint
        } for encounter in encounters],
        "medical_history": [{
            "id": history.id,
            "condition": history.condition,
            "onset_date": history.onset_date,
            "status": history.status,
                "notes": history.notes  # Add this line

        } for history in medical_history],
        "family_history": [{
            "id": history.id,
            "relation": history.relation,
            "condition": history.condition,
            "onset_age": history.onset_age
        } for history in family_history],
        "medications": [{
  "id": med.id,
  "name": med.name,
  "dosage": med.dosage,
  "frequency": med.frequency,
  "route": med.route,  # Already added in previous fix
  "start_date": med.start_date,  # Add this
  "indication": med.indication,  # Add this if needed
  "active": med.active
} for med in medications],
        "allergies": [{
            "id": allergy.id,
            "allergen": allergy.allergen,
            "reaction": allergy.reaction,
            "severity": allergy.severity
        } for allergy in allergies],
            "scans": [{
        "id": scan.id,
        "scan_type": scan.scan_type,
        "scan_date": scan.scan_date.isoformat(),
        "file_name": scan.file_name
    } for scan in scans],
        "lab_orders": [{
            "id": order.id,
            "test_name": order.test_name,
            "order_date": order.order_date.isoformat(),
            "status": order.status
        } for order in lab_orders]
    }

@app.post("/api/medications", response_model=dict)
async def create_medication(medication: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not current_user.is_doctor:
        raise HTTPException(status_code=403, detail="Only doctors can add medications")
    
    db_medication = Medication(
        id=str(uuid.uuid4()),
        patient_id=medication["patient_id"],
        name=medication["name"],
        dosage=medication.get("dosage"),
        frequency=medication.get("frequency"),
        route=medication.get("route"),
        start_date=medication.get("start_date"),
        indication=medication.get("indication"),
        prescriber_id=current_user.id,
        active=medication.get("active", True),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    
    return {
        "id": db_medication.id,
        "name": db_medication.name,
        "dosage": db_medication.dosage,
        "frequency": db_medication.frequency,
        "route": db_medication.route,
        "start_date": db_medication.start_date,
        "indication": db_medication.indication,
        "active": db_medication.active,
        "message": "Medication added successfully"
    }

#
#public patient routes
@app.post("/api/public/patients", response_model=dict)
async def create_public_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    mrn = generate_mrn()
    db_patient = Patient(
        id=str(uuid.uuid4()),
        mrn=mrn,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        phone=patient.phone,
        organization_id=patient.organization_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    
    # Save as JSON
    patient_path = f"patients/{db_patient.id}.json"
    os.makedirs(os.path.dirname(patient_path), exist_ok=True)
    with open(patient_path, "w") as f:
        patient_dict = {
            "id": db_patient.id,
            "mrn": db_patient.mrn,
            "first_name": db_patient.first_name,
            "last_name": db_patient.last_name,
            "date_of_birth": db_patient.date_of_birth,
            "phone": db_patient.phone,
            "organization_id": db_patient.organization_id,
            "created_at": db_patient.created_at.isoformat(),
            "updated_at": db_patient.updated_at.isoformat()
        }
        json.dump(patient_dict, f, indent=2)
    
    return {
        "id": db_patient.id,
        "mrn": db_patient.mrn,
        "first_name": db_patient.first_name,
        "last_name": db_patient.last_name,
        "date_of_birth": db_patient.date_of_birth,
        "phone": db_patient.phone,
        "organization_id": db_patient.organization_id,
        "message": "Patient created successfully"
    }

@app.put("/api/public/patients/{patient_id}", response_model=dict)
async def update_public_patient(patient_id: str, patient_update: PatientUpdate, db: Session = Depends(get_db)):
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    update_data = patient_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_patient, key, value)
    
    db_patient.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_patient)
    
    # Update JSON
    patient_path = f"patients/{db_patient.id}.json"
    with open(patient_path, "w") as f:
        patient_dict = {
            "id": db_patient.id,
            "mrn": db_patient.mrn,
            "first_name": db_patient.first_name,
            "last_name": db_patient.last_name,
            "date_of_birth": db_patient.date_of_birth,
            "phone": db_patient.phone,
            "organization_id": db_patient.organization_id,
            "created_at": db_patient.created_at.isoformat(),
            "updated_at": db_patient.updated_at.isoformat()
        }
        json.dump(patient_dict, f, indent=2)
    
    return {
        "id": db_patient.id,
        "mrn": db_patient.mrn,
        "first_name": db_patient.first_name,
        "last_name": db_patient.last_name,
        "date_of_birth": db_patient.date_of_birth,
        "phone": db_patient.phone,
        "organization_id": db_patient.organization_id,
        "message": "Patient updated successfully"
    }

@app.get("/api/public/patients/{patient_id}", response_model=dict)
async def get_public_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    return {
        "id": patient.id,
        "mrn": patient.mrn,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth,
        "phone": patient.phone,
        "organization_id": patient.organization_id
    }


#scans
@app.post("/api/scans", response_model=dict)
async def upload_patient_scan(
    patient_id: str = Form(...),
    scan_type: str = Form(...),
    description: str = Form(None),
    notes: str = Form(None),
    file: UploadFile = File(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    scan_id = str(uuid.uuid4())
    
    # Upload to GCS
    bucket = storage_client.bucket(BUCKET_NAME)
    file_path = f"patient_scans/{patient_id}/{scan_id}/{file.filename}"
    blob = bucket.blob(file_path)
    blob.upload_from_string(
        file_content, 
        content_type=file.content_type
    )
    
    # Create database record
    scan = PatientScan(
        id=scan_id,
        patient_id=patient_id,
        provider_id=current_user.id,
        scan_type=scan_type,
        description=description,
        file_name=file.filename,
        file_size=file_size,
        storage_url=file_path,
        content_type=file.content_type,
        notes=notes
    )
    
    db.add(scan)
    db.commit()
    db.refresh(scan)
    
    # Generate a signed URL for temporary access
    signed_url = blob.generate_signed_url(
        expiration=datetime.utcnow() + timedelta(hours=1),
        method="GET"
    )
    
    return {
        "id": scan.id,
        "patient_id": scan.patient_id,
        "scan_type": scan.scan_type,
        "file_name": scan.file_name,
        "scan_date": scan.scan_date.isoformat(),
        "url": signed_url,
        "message": "Scan uploaded successfully"
    }

@app.get("/api/patients/{patient_id}/scans", response_model=List[dict])
async def get_patient_scans(
    patient_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get all scans for the patient
    scans = db.query(PatientScan).filter(PatientScan.patient_id == patient_id).all()
    
    result = []
    for scan in scans:
        # Generate a signed URL for each scan
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(scan.storage_url)
        signed_url = blob.generate_signed_url(
            expiration=datetime.utcnow() + timedelta(hours=1),
            method="GET"
        )
        
        result.append({
            "id": scan.id,
            "scan_type": scan.scan_type,
            "scan_date": scan.scan_date.isoformat(),
            "description": scan.description,
            "file_name": scan.file_name,
            "file_size": scan.file_size,
            "content_type": scan.content_type,
            "notes": scan.notes,
            "url": signed_url,
            "created_at": scan.created_at.isoformat()
        })
    
    return result

@app.get("/api/scans/{scan_id}", response_model=dict)
async def get_scan(
    scan_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    scan = db.query(PatientScan).filter(PatientScan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Generate a signed URL
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(scan.storage_url)
    signed_url = blob.generate_signed_url(
        expiration=datetime.utcnow() + timedelta(hours=1),
        method="GET"
    )
    
    return {
        "id": scan.id,
        "patient_id": scan.patient_id,
        "provider_id": scan.provider_id,
        "scan_type": scan.scan_type,
        "scan_date": scan.scan_date.isoformat(),
        "description": scan.description,
        "file_name": scan.file_name,
        "file_size": scan.file_size,
        "content_type": scan.content_type,
        "notes": scan.notes,
        "url": signed_url,
        "created_at": scan.created_at.isoformat()
    }
# Encounters
@app.post("/api/encounters", response_model=dict)
async def create_encounter(encounter: EncounterCreate, db = Depends(get_db), current_user = Depends(get_current_user)):
    # Verify patient exists
    patient = db.query(Patient).filter(Patient.id == encounter.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Convert vital signs to JSON string if provided
    vital_signs_json = "{}"
    if encounter.vital_signs:
        vital_signs_dict = {k: v for k, v in encounter.vital_signs.dict().items() if v is not None}
        vital_signs_json = json.dumps(vital_signs_dict)
    
    db_encounter = Encounter(
        id=str(uuid.uuid4()),
        patient_id=encounter.patient_id,
        provider_id=current_user.id,
        encounter_type=encounter.encounter_type,
        chief_complaint=encounter.chief_complaint,
        vital_signs=vital_signs_json,
        hpi=encounter.hpi,
        ros=encounter.ros,
        physical_exam=encounter.physical_exam,
        assessment=encounter.assessment,
        plan=encounter.plan,
        diagnosis_codes=encounter.diagnosis_codes,
        followup_instructions=encounter.followup_instructions
    )
    
    db.add(db_encounter)
    db.commit()
    db.refresh(db_encounter)
    
    # Generate a clinical note
    patient_data = {
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "encounter": {
            "chief_complaint": encounter.chief_complaint,
            "vital_signs": encounter.vital_signs.dict() if encounter.vital_signs else {},
            "hpi": encounter.hpi,
            "physical_exam": encounter.physical_exam,
            "assessment": encounter.assessment,
            "plan": encounter.plan
        }
    }
    
    clinical_note = generate_clinical_note(patient_data, format_type="soap")
    
    # Save encounter as JSON for reference
    encounter_path = f"encounters/{db_encounter.id}.json"
    with open(encounter_path, "w") as f:
        encounter_dict = {
            "id": db_encounter.id,
            "patient_id": db_encounter.patient_id,
            "provider_id": db_encounter.provider_id,
            "encounter_date": db_encounter.encounter_date.isoformat(),
            "encounter_type": db_encounter.encounter_type,
            "chief_complaint": db_encounter.chief_complaint,
            "vital_signs": json.loads(db_encounter.vital_signs),
            "hpi": db_encounter.hpi,
            "ros": db_encounter.ros,
            "physical_exam": db_encounter.physical_exam,
            "assessment": db_encounter.assessment,
            "plan": db_encounter.plan,
            "diagnosis_codes": db_encounter.diagnosis_codes,
            "followup_instructions": db_encounter.followup_instructions,
            "clinical_note": clinical_note,
            "created_at": db_encounter.created_at.isoformat(),
            "updated_at": db_encounter.updated_at.isoformat()
        }
        json.dump(encounter_dict, f, indent=2)
    
    return {
        "id": db_encounter.id,
        "patient_id": db_encounter.patient_id,
        "encounter_date": db_encounter.encounter_date.isoformat(),
        "encounter_type": db_encounter.encounter_type,
        "chief_complaint": db_encounter.chief_complaint,
        "clinical_note": clinical_note,
        "message": "Encounter created successfully"
    }

@app.get("/api/encounters/{encounter_id}", response_model=dict)
async def get_encounter(encounter_id: str, db = Depends(get_db), current_user = Depends(get_current_user)):
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")
    
    # Get patient info
    patient = db.query(Patient).filter(Patient.id == encounter.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Associated patient not found")
    
    # Generate clinical note
    patient_data = {
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "encounter": {
            "chief_complaint": encounter.chief_complaint,
            "vital_signs": json.loads(encounter.vital_signs),
            "hpi": encounter.hpi,
            "physical_exam": encounter.physical_exam,
            "assessment": encounter.assessment,
            "plan": encounter.plan
        }
    }
    
    clinical_note = generate_clinical_note(patient_data, format_type="soap")
    
    return {
        "id": encounter.id,
        "patient": {
            "id": patient.id,
            "mrn": patient.mrn,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender
        },
        "encounter_date": encounter.encounter_date.isoformat(),
        "encounter_type": encounter.encounter_type,
        "chief_complaint": encounter.chief_complaint,
        "vital_signs": json.loads(encounter.vital_signs),
        "hpi": encounter.hpi,
        "ros": encounter.ros,
        "physical_exam": encounter.physical_exam,
        "assessment": encounter.assessment,
        "plan": encounter.plan,
        "diagnosis_codes": encounter.diagnosis_codes,
        "followup_instructions": encounter.followup_instructions,
        "clinical_note": clinical_note
    }

@app.post("/api/encounters/{encounter_id}/autocode", response_model=AutocodeResponse)
async def autocode_encounter(
    encounter_id: str, 
    request: AutocodeRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate ICD-10 and CPT codes for an encounter using AI.
    Optionally updates the encounter with the generated codes.
    """
    print(f"[API] Autocoding encounter {encounter_id}")
    
    if request is None:
        # Default values if no request body provided
        request = AutocodeRequest(
            encounter_id=encounter_id,
            use_llm=True,
            update_encounter=False
        )
    
    # Fetch the encounter
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")
    
    # Build the clinical text for analysis
    clinical_text = ""
    
    # Add chief complaint
    if encounter.chief_complaint:
        clinical_text += f"Chief Complaint: {encounter.chief_complaint}\n\n"
    
    # Add HPI
    if encounter.hpi:
        clinical_text += f"History of Present Illness: {encounter.hpi}\n\n"
    
    # Add physical exam
    if encounter.physical_exam:
        clinical_text += f"Physical Examination: {encounter.physical_exam}\n\n"
    
    # Add assessment
    if encounter.assessment:
        clinical_text += f"Assessment: {encounter.assessment}\n\n"
    
    # Add plan
    if encounter.plan:
        clinical_text += f"Plan: {encounter.plan}\n\n"
    
    # Extract entities
    entity_results = extract_medical_entities(clinical_text)
    entity_groups = entity_results.get("entity_groups", {})
    
    # Generate codes
    codes_result = generate_medical_codes(
        clinical_text=clinical_text,
        entity_groups=entity_groups,
        use_llm=request.use_llm
    )
    
    # Update the encounter if requested
    if request.update_encounter:
        # Format codes for storing in encounter
        formatted_codes = []
        
        # Add ICD-10 codes
        for code in codes_result.get("icd10_codes", []):
            formatted_codes.append(f"{code['code']} ({code['description']})")
        
        # Add CPT codes
        for code in codes_result.get("cpt_codes", []):
            formatted_codes.append(f"{code['code']} ({code['description']})")
        
        # Update encounter
        encounter.diagnosis_codes = "; ".join(formatted_codes)
        db.commit()
        
        # Add to response
        codes_result["updated"] = True
        print(f"[API] Updated encounter {encounter_id} with {len(formatted_codes)} codes")
    
    # Ensure we have the encounter_id in the result
    response = {
        "encounter_id": encounter_id,
        **codes_result
    }
    
    return response

# Add an endpoint to get medical codes from the database
@app.get("/api/medical-codes", response_model=Dict[str, Any])
async def get_medical_codes(
    code_type: str = Query(None, description="Filter by code type (ICD-10 or CPT)"),
    category: str = Query(None, description="Filter by category"),
    search: str = Query(None, description="Search by code or description"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get medical codes from the database with optional filtering.
    """
    query = db.query(MedicalCode)
    
    # Apply filters
    if code_type:
        query = query.filter(MedicalCode.type == code_type)
    
    if category:
        query = query.filter(MedicalCode.category == category)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                MedicalCode.code.like(search_term),
                MedicalCode.description.like(search_term),
                MedicalCode.common_terms.like(search_term)
            )
        )
    
    # Get results
    total = query.count()
    codes = query.limit(limit).all()
    
    # Format response
    results = []
    for code in codes:
        results.append({
            "id": code.id,
            "code": code.code,
            "type": code.type,
            "description": code.description,
            "category": code.category,
            "common_terms": json.loads(code.common_terms)
        })
    
    return {
        "total": total,
        "limit": limit,
        "results": results
    }
# MedRAG Analysis (Keep existing implementation but enhance with EHR integration)
@app.post("/api/analyze_patient")
async def analyze_patient(request: PatientAnalysisRequest, db = Depends(get_db)):
    print(f"[API] Received request to analyze patient with model: {request.llm_model}")
    try:
        print(f"[API] Starting patient analysis")
        # Load and index patient data
        print(f"[API] Loading patient data")
        patient_docs = load_data_from_frontend_input(request.patient_input, index_type="vector_store")
        print(f"[API] Loaded {len(patient_docs)} patient documents")
        index_id = str(uuid.uuid4())
        print(f"[API] Generated index ID: {index_id}")
        
        print(f"[API] Building index for patient data")
        index = process_user_inputs_and_build_index(
            [request.patient_input],
            "vector_store",
            {"vector_store_type": "chroma"},
            index_id,
            "patient_data"
        )
        print(f"[API] Index built successfully")
        
        # Generate query from patient data using LLM
        print(f"[API] Extracting patient data text")
        patient_data = patient_docs[0].text
        print(f"[API] Patient data length: {len(patient_data)}")
        
        print(f"[API] Generating query from patient data")
        query = summarize_patient_data(patient_docs)
        print(f"[API] Generated query: {query}")
        
        # Retrieve relevant medical literature using MedRAG
        print(f"[API] Initializing MedRAG with model: {request.llm_model}")
        medrag = MedRAG(llm_name=request.llm_model, rag=True)
        
        print(f"[API] Retrieving relevant medical literature for query")
        messages, retrieved_docs, scores = medrag.createMessage(question=query, k=32, split=True)
        print(f"[API] Retrieved {len(retrieved_docs)} documents")
        
        print(f"[API] Building context from retrieved documents")
        context = "\n".join([doc["contents"] for doc in retrieved_docs])
        print(f"[API] Context length: {len(context)}")
        
        # Create prompt for genetic testing recommendation
        print(f"[API] Creating prompt with patient data and context")
        prompt = ehr_prompt.render(patient_data=patient_data, context=context)
        print(f"[API] Prompt created with length: {len(prompt)}")
        
        # Add requested full prompt logging
        print(f"[API] FULL AUGMENTED PROMPT:\n{'-'*80}\n{prompt}\n{'-'*80}")
        
        # Set LLM and get response
        print(f"[API] Setting LLM to {request.llm_model}")
        Settings.llm = LLM_MODELS[request.llm_model]
        
        print(f"[API] Sending prompt to LLM for completion")
        response = Settings.llm.complete(prompt).text
        print(f"[API] Raw LLM Response: {repr(response)}")  # Show exact output
        response = response.strip()
        if response.startswith("```json"):
            print(f"[API] Removing ```json prefix")
            response = response[7:]  # Remove ```json
        if response.endswith("```"):
            print(f"[API] Removing ``` suffix")
            response = response[:-3]  # Remove ```
        response = response.strip()
        
        # Parse response
        print(f"[API] Parsing response as JSON")
        try:
            result = json.loads(response)
            print(f"[API] Successfully parsed JSON response: {result.keys()}")
            recommendation = result["testing_recommendation"]
            reasoning = result["reasoning"]
            confidence = result.get("confidence", "80%")
            print(f"[API] Recommendation: {recommendation}, Confidence: {confidence}")
        except Exception as e:
            print(f"[API] ERROR parsing response: {str(e)}")
            recommendation = "Error"
            reasoning = f"Failed to parse LLM response: {str(e)}"
            confidence = "0%"
        
        # Add AI note to patient record
        print(f"[API] Creating AI note")
        ai_note = {
            "recommendation": recommendation,
            "reasoning": reasoning,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"[API] Creating patient record")
        patient_record = {
            "patient_data": patient_data,
            "ai_note": ai_note,
            "retrieved_docs": retrieved_docs
        }
        
        # Save to local storage and GCS
        print(f"[API] Saving record to local storage")
        record_path = f"ehr_records/{index_id}.json"
        with open(record_path, "w") as f:
            json.dump(patient_record, f, indent=2)
            
        print(f"[API] Saving record to Google Cloud Storage")
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"ehr_records/{index_id}.json")
        blob.upload_from_filename(record_path)
        print(f"[API] Generated signed URL for download")
        
        # Store analysis in database if patient_id is found
        try:
            # Extract patient identifiers if present
            patient_id = None
            encounter_id = None
            
            # Try to parse a patient ID from the text
            if "MRN" in patient_data:
                mrn_search = db.query(Patient).filter(Patient.mrn == patient_data.split("MRN")[1].split()[0]).first()
                if mrn_search:
                    patient_id = mrn_search.id
            
            if patient_id:
                ai_analysis = AIAnalysis(
                    id=index_id,
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    analysis_type="Genetic Testing",
                    recommendation=recommendation,
                    reasoning=reasoning,
                    confidence=confidence,
                    model_used=request.llm_model
                )
                db.add(ai_analysis)
                db.commit()
                print(f"[API] AI analysis saved to database for patient {patient_id}")
        except Exception as e:
            print(f"[API] Warning: Could not save analysis to database: {str(e)}")
        
        print(f"[API] Patient analysis complete, returning results")
        return {
            "record_id": index_id,
            "recommendation": recommendation,
            "reasoning": reasoning,
            "confidence": confidence,
            "download_url": blob.generate_signed_url(datetime.utcnow() + timedelta(days=7), method="GET", version="v4")
        }
    except Exception as e:
        print(f"[API] ERROR in analyze_patient: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add this endpoint to your existing app in paste.txt
@app.get("/api/patients/{patient_id}/timeline")
async def get_patient_timeline(
    patient_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    types: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(f"[API] Generating timeline for patient {patient_id}")
    
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    min_dates = []
    max_dates = []
    
    # Convert to datetime helper
    def to_datetime(value):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        elif isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=pytz.utc)
        return None
    
    # Encounters
    encounter_dates = db.query(func.min(Encounter.encounter_date), func.max(Encounter.encounter_date)).filter(Encounter.patient_id == patient_id).first()
    if encounter_dates and encounter_dates[0]:
        min_dates.append(to_datetime(encounter_dates[0]))
        max_dates.append(to_datetime(encounter_dates[1]))
    
    # Lab orders
    lab_order_dates = db.query(func.min(LabOrder.order_date), func.max(LabOrder.order_date)).filter(LabOrder.patient_id == patient_id).first()
    if lab_order_dates and lab_order_dates[0]:
        min_dates.append(to_datetime(lab_order_dates[0]))
        max_dates.append(to_datetime(lab_order_dates[1]))
    
    # Lab results
    lab_result_dates = db.query(func.min(LabResult.result_date), func.max(LabResult.result_date)).join(LabOrder, LabResult.lab_order_id == LabOrder.id).filter(LabOrder.patient_id == patient_id).first()
    if lab_result_dates and lab_result_dates[0]:
        min_dates.append(to_datetime(lab_result_dates[0]))
        max_dates.append(to_datetime(lab_result_dates[1]))
    
    # Medications
    med_start_min = db.query(func.min(Medication.start_date)).filter(Medication.patient_id == patient_id).scalar()
    med_start_max = db.query(func.max(Medication.start_date)).filter(Medication.patient_id == patient_id).scalar()
    med_end_max = db.query(func.max(Medication.end_date)).filter(Medication.patient_id == patient_id).scalar()
    if med_start_min:
        min_dates.append(to_datetime(med_start_min))
    if med_start_max:
        max_dates.append(to_datetime(med_start_max))
    if med_end_max:
        max_dates.append(to_datetime(med_end_max))
    
    # Scans
    scan_dates = db.query(func.min(PatientScan.scan_date), func.max(PatientScan.scan_date)).filter(PatientScan.patient_id == patient_id).first()
    if scan_dates and scan_dates[0]:
        min_dates.append(to_datetime(scan_dates[0]))
        max_dates.append(to_datetime(scan_dates[1]))
    
    # AI analyses
    ai_dates = db.query(func.min(AIAnalysis.analysis_date), func.max(AIAnalysis.analysis_date)).filter(AIAnalysis.patient_id == patient_id).first()
    if ai_dates and ai_dates[0]:
        min_dates.append(to_datetime(ai_dates[0]))
        max_dates.append(to_datetime(ai_dates[1]))
    
    # Determine overall min and max dates
    overall_min = min(min_dates) if min_dates else None
    overall_max = max(max_dates) if max_dates else None
    
    timeline = []
    
    parsed_start_date = None
    parsed_end_date = None
    
    if start_date:
        try:
            parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            print(f"[API] Filtering timeline from {parsed_start_date}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    
    if end_date:
        try:
            parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            print(f"[API] Filtering timeline to {parsed_end_date}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    type_filters = None
    if types:
        type_filters = types.lower().split(',')
        print(f"[API] Filtering timeline by types: {type_filters}")

    def should_include_event(event_type, event_date):
        if event_date.tzinfo is None:
            event_date = event_date.replace(tzinfo=pytz.utc)
        if type_filters and event_type not in type_filters:
            return False
        if parsed_start_date and event_date < parsed_start_date:
            return False
        if parsed_end_date and event_date > parsed_end_date:
            return False
        return True
    
    if not type_filters or "encounter" in type_filters:
        encounters = db.query(Encounter).filter(Encounter.patient_id == patient_id).all()
        for encounter in encounters:
            event_date = encounter.encounter_date
            if should_include_event("encounter", event_date):
                timeline.append({
                    "id": encounter.id,
                    "date": event_date.isoformat(),
                    "type": "encounter",
                    "subtype": encounter.encounter_type,
                    "title": "Clinical Encounter",
                    "details": encounter.chief_complaint,
                    "provider": encounter.provider_id,
                    "icon": "clipboard"
                })
    
    if not type_filters or "lab" in type_filters:
        lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
        for order in lab_orders:
            event_date = order.order_date
            if should_include_event("lab", event_date):
                timeline.append({
                    "id": order.id,
                    "date": event_date.isoformat(),
                    "type": "lab",
                    "subtype": "order",
                    "title": f"Lab Ordered: {order.test_name}",
                    "details": f"Status: {order.status}",
                    "provider": order.provider_id,
                    "icon": "flask"
                })
            
            results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
            for result in results:
                result_date = result.result_date
                if should_include_event("lab", result_date):
                    abnormal_flag = ""
                    if result.abnormal_flag:
                        if result.abnormal_flag.lower() == "high":
                            abnormal_flag = "⬆️ "
                        elif result.abnormal_flag.lower() == "low":
                            abnormal_flag = "⬇️ "
                    timeline.append({
                        "id": result.id,
                        "date": result_date.isoformat(),
                        "type": "lab",
                        "subtype": "result",
                        "title": f"Lab Result: {order.test_name}",
                        "details": f"{abnormal_flag}{result.result_value} {result.unit} [{result.reference_range}]",
                        "provider": order.provider_id,
                        "related_to": order.id,
                        "icon": "chart-bar"
                    })
    
    if not type_filters or "medication" in type_filters:
        medications = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        for medication in medications:
            start_date = datetime.fromisoformat(medication.start_date) if isinstance(medication.start_date, str) else medication.start_date
            if should_include_event("medication", start_date):
                timeline.append({
                    "id": medication.id,
                    "date": start_date.isoformat(),
                    "type": "medication",
                    "subtype": "start",
                    "title": f"Started Medication: {medication.name}",
                    "details": f"{medication.dosage}, {medication.frequency}, {medication.route}",
                    "provider": medication.prescriber_id,
                    "icon": "pill"
                })
            
            if medication.end_date:
                end_date = datetime.fromisoformat(medication.end_date) if isinstance(medication.end_date, str) else medication.end_date
                if should_include_event("medication", end_date):
                    timeline.append({
                        "id": f"{medication.id}-end",
                        "date": end_date.isoformat(),
                        "type": "medication",
                        "subtype": "end",
                        "title": f"Stopped Medication: {medication.name}",
                        "details": f"Completed course or discontinued",
                        "provider": medication.prescriber_id,
                        "related_to": medication.id,
                        "icon": "pill-off"
                    })
    
    if not type_filters or "scan" in type_filters:
        scans = db.query(PatientScan).filter(PatientScan.patient_id == patient_id).all()
        for scan in scans:
            event_date = scan.scan_date
            if should_include_event("scan", event_date):
                timeline.append({
                    "id": scan.id,
                    "date": event_date.isoformat(),
                    "type": "scan",
                    "subtype": scan.scan_type,
                    "title": f"Imaging: {scan.scan_type}",
                    "details": scan.description or "No description provided",
                    "provider": scan.provider_id,
                    "has_image": True,
                    "icon": "image"
                })
    
    if not type_filters or "ai_analysis" in type_filters:
        analyses = db.query(AIAnalysis).filter(AIAnalysis.patient_id == patient_id).all()
        for analysis in analyses:
            event_date = analysis.analysis_date
            if should_include_event("ai_analysis", event_date):
                analysis_type = analysis.analysis_type
                timeline.append({
                    "id": analysis.id,
                    "date": event_date.isoformat(),
                    "type": "ai_analysis",
                    "subtype": analysis_type,
                    "title": f"AI Analysis: {analysis_type}",
                    "details": analysis.recommendation,
                    "confidence": analysis.confidence,
                    "provider": analysis.reviewer_id,
                    "related_to": analysis.encounter_id,
                    "icon": "brain"
                })
    
    sorted_timeline = sorted(timeline, key=lambda x: x["date"], reverse=True)
    
    print(f"[API] Generated timeline with {len(sorted_timeline)} events")
    
    return {
        "timeline": sorted_timeline,
        "date_range": {
            "start": overall_min.isoformat() if overall_min else None,
            "end": overall_max.isoformat() if overall_max else None
        }
    }

@app.get("/api/patients/{patient_id}/dashboard")
async def get_patient_dashboard(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive patient dashboard data including trends and summary statistics.
    """
    print(f"[API] Generating dashboard for patient {patient_id}")
    
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get all encounters in chronological order
    encounters = db.query(Encounter).filter(Encounter.patient_id == patient_id).order_by(Encounter.encounter_date).all()
    
    # Initialize vital sign trend data
    vital_trends = {
        "dates": [],
        "heart_rate": [],
        "blood_pressure_systolic": [],
        "blood_pressure_diastolic": [],
        "respiratory_rate": [],
        "temperature": [],
        "oxygen_saturation": []
    }
    
    # Extract vital signs from encounters
    for encounter in encounters:
        # Add date to trends
        vital_trends["dates"].append(encounter.encounter_date.isoformat())
        
        # Parse vital signs from JSON
        vital_signs = json.loads(encounter.vital_signs) if encounter.vital_signs else {}
        
        # Add vital sign data points (or null if missing)
        vital_trends["heart_rate"].append(vital_signs.get("heart_rate"))
        vital_trends["blood_pressure_systolic"].append(vital_signs.get("blood_pressure_systolic"))
        vital_trends["blood_pressure_diastolic"].append(vital_signs.get("blood_pressure_diastolic"))
        vital_trends["respiratory_rate"].append(vital_signs.get("respiratory_rate"))
        vital_trends["temperature"].append(vital_signs.get("temperature"))
        vital_trends["oxygen_saturation"].append(vital_signs.get("oxygen_saturation"))
    
    # Get lab results and organize them by test name
    lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
    
    # Initialize lab trends structure
    lab_trends = {"dates": []}
    lab_dates = {}  # Map to track date to index for each lab result
    
    # Process lab results
    for order in lab_orders:
        results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
        
        for result in results:
            # Only process results with numerical values
            try:
                result_value = float(result.result_value)
                test_name = order.test_name
                
                # Initialize array for this test if not exists
                if test_name not in lab_trends:
                    lab_trends[test_name] = []
                
                # Get the date in ISO format
                result_date = result.result_date.isoformat()
                
                # Check if we've seen this date before
                if result_date not in lab_dates:
                    lab_dates[result_date] = len(lab_trends["dates"])
                    lab_trends["dates"].append(result_date)
                    
                    # Pad all existing test arrays with null values
                    for test in lab_trends:
                        if test != "dates" and len(lab_trends[test]) < len(lab_trends["dates"]):
                            lab_trends[test].extend([None] * (len(lab_trends["dates"]) - len(lab_trends[test])))
                
                # Find the index for this date
                date_index = lab_dates[result_date]
                
                # Ensure the test array is padded up to this index
                if len(lab_trends[test_name]) <= date_index:
                    lab_trends[test_name].extend([None] * (date_index + 1 - len(lab_trends[test_name])))
                
                # Add the result value at the correct index
                lab_trends[test_name][date_index] = result_value
                
            except (ValueError, TypeError):
                # Skip non-numeric results
                continue
    
    # Calculate summary statistics
    active_medications = db.query(Medication).filter(
        Medication.patient_id == patient_id,
        Medication.active == True
    ).count()
    
    pending_labs = db.query(LabOrder).filter(
    LabOrder.patient_id == patient_id,
    LabOrder.status.in_(["Ordered", "Collected", "In Progress"])
    ).count()

    total_labs = db.query(LabOrder).filter(
        LabOrder.patient_id == patient_id
    ).count()
    
    last_encounter_date = None
    if encounters:
        last_encounter = max(encounters, key=lambda e: e.encounter_date)
        last_encounter_date = last_encounter.encounter_date.isoformat()
    
    # Gather AI analyses
    analyses = db.query(AIAnalysis).filter(AIAnalysis.patient_id == patient_id).all()
    
    # Format dashboard response
    dashboard = {
    "patient": {
        "id": patient.id,
        "name": f"{patient.first_name} {patient.last_name}",
        "mrn": patient.mrn,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender
    },
    "vital_trends": vital_trends,
    "lab_trends": lab_trends,
    "summary": {
        "total_encounters": len(encounters),
        "active_medications": active_medications,
        "pending_labs": pending_labs,
        "total_labs": total_labs,  # Add this new field
        "last_encounter_date": last_encounter_date,
        "total_analyses": len(analyses)
    }
}
    
    print(f"[API] Dashboard generated with {len(encounters)} encounters and {len(lab_trends) - 1} lab test trends")
    return dashboard

@app.get("/api/patients/{patient_id}/insights")
async def get_patient_insights(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get personalized health insights for a patient.
    """
    print(f"[API] Getting insights for patient {patient_id}")
    
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get insights ordered by most recent first
    insights = db.query(PatientInsights).filter(
        PatientInsights.patient_id == patient_id
    ).order_by(PatientInsights.generated_at.desc()).all()
    
    # Format response
    insights_response = [
        {
            "id": insight.id,
            "insight_type": insight.insight_type,
            "insight_text": insight.insight_text,
            "generated_at": insight.generated_at.isoformat()
        }
        for insight in insights
    ]
    
    print(f"[API] Returning {len(insights_response)} insights")
    return insights_response

@app.post("/api/patients/{patient_id}/insights")
async def generate_patient_insights(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate new personalized health insights for a patient using AI.
    """
    print(f"[API] Generating new insights for patient {patient_id}")
    
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Gather patient data for analysis
    patient_data = {}
    
    # Basic demographics
    patient_data["demographics"] = {
        "name": f"{patient.first_name} {patient.last_name}",
        "age": calculate_age(patient.date_of_birth),
        "gender": patient.gender
    }
    
    # Medical conditions from history
    medical_history = db.query(MedicalHistory).filter(MedicalHistory.patient_id == patient_id).all()
    patient_data["conditions"] = [
        {
            "condition": history.condition,
            "status": history.status
        }
        for history in medical_history
    ]
    
    # Medications
    medications = db.query(Medication).filter(Medication.patient_id == patient_id).all()
    patient_data["medications"] = [
        {
            "name": med.name,
            "dosage": med.dosage,
            "frequency": med.frequency,
            "active": med.active
        }
        for med in medications
    ]
    
    # Allergies
    allergies = db.query(Allergy).filter(Allergy.patient_id == patient_id).all()
    patient_data["allergies"] = [allergy.allergen for allergy in allergies]
    
    # Recent vitals from last encounter
    latest_encounter = db.query(Encounter).filter(
        Encounter.patient_id == patient_id
    ).order_by(Encounter.encounter_date.desc()).first()
    
    if latest_encounter:
        vitals = json.loads(latest_encounter.vital_signs) if latest_encounter.vital_signs else {}
        patient_data["vitals"] = vitals
    
    # Recent lab results
    recent_labs = []
    lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
    
    for order in lab_orders:
        results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
        if results:
            for result in results:
                recent_labs.append({
                    "test_name": order.test_name,
                    "result_value": result.result_value,
                    "unit": result.unit,
                    "reference_range": result.reference_range,
                    "abnormal_flag": result.abnormal_flag,
                    "result_date": result.result_date.isoformat()
                })
    
    # Sort labs by date (most recent first) and keep only the latest 10
    recent_labs.sort(key=lambda x: x.get("result_date", ""), reverse=True)
    patient_data["recent_labs"] = recent_labs[:10]
    
    # Convert patient data to string for the LLM
    patient_data_str = json.dumps(patient_data, indent=2)
    
    # Extract medical entities for more focused insights
    entity_results = extract_medical_entities(patient_data_str)
    
    # Generate different types of insights
    insight_types = ["lifestyle", "medication", "screening", "risk"]
    generated_insights = []
    
    for insight_type in insight_types:
        try:
            # Create a different prompt for each insight type
            if insight_type == "lifestyle":
                prompt = f"""
                Based on the following patient data, provide ONE specific, actionable lifestyle recommendation that would benefit this patient.
                Focus on diet, exercise, sleep, or stress management based on their medical conditions and risk factors.
                Keep your response under 150 words and focus on practical, personalized advice.
                
                Patient Data:
                {patient_data_str}
                
                Extracted Medical Entities:
                {json.dumps(entity_results.get("entity_groups", {}), indent=2)}
                
                Format your response as plain text with NO markdown, lists, or other formatting.
                """
            elif insight_type == "medication":
                prompt = f"""
                Based on the following patient data, provide ONE specific insight about medication management, adherence, or potential interactions.
                If there are no medications, suggest appropriate preventive medications based on their risk factors.
                Keep your response under 150 words and focus on practical, personalized advice.
                
                Patient Data:
                {patient_data_str}
                
                Extracted Medical Entities:
                {json.dumps(entity_results.get("entity_groups", {}), indent=2)}
                
                Format your response as plain text with NO markdown, lists, or other formatting.
                """
            elif insight_type == "screening":
                prompt = f"""
                Based on the following patient data, recommend ONE appropriate screening test or health check that would be valuable for this patient.
                Consider their age, gender, medical conditions, family history, and risk factors.
                Keep your response under 150 words and explain the rationale.
                
                Patient Data:
                {patient_data_str}
                
                Extracted Medical Entities:
                {json.dumps(entity_results.get("entity_groups", {}), indent=2)}
                
                Format your response as plain text with NO markdown, lists, or other formatting.
                """
            elif insight_type == "risk":
                prompt = f"""
                Based on the following patient data, identify ONE specific health risk this patient may face and provide a targeted recommendation to address it.
                Consider their medical conditions, vitals, lab results, and behavioral factors.
                Keep your response under 150 words and be specific about both the risk and the intervention.
                
                Patient Data:
                {patient_data_str}
                
                Extracted Medical Entities:
                {json.dumps(entity_results.get("entity_groups", {}), indent=2)}
                
                Format your response as plain text with NO markdown, lists, or other formatting.
                """
            
            # Generate the insight using LLM
            print(f"[API] Generating {insight_type} insight with LLM")
            insight_text = Settings.llm.complete(prompt).text.strip()
            
            # Limit insight length if needed
            if len(insight_text) > 500:
                insight_text = insight_text[:497] + "..."
            
            # Create insight record
            db_insight = PatientInsights(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                insight_type=insight_type,
                insight_text=insight_text,
                generated_at=datetime.utcnow()
            )
            
            db.add(db_insight)
            
            # Add to response list
            generated_insights.append({
                "id": db_insight.id,
                "insight_type": insight_type,
                "insight_text": insight_text,
                "generated_at": db_insight.generated_at.isoformat()
            })
            
        except Exception as e:
            print(f"[API] Error generating {insight_type} insight: {str(e)}")
            # Continue to next insight type even if one fails
    
    # Commit all successful insights to database
    db.commit()
    
    print(f"[API] Generated {len(generated_insights)} insights for patient {patient_id}")
    return generated_insights


@app.post("/api/patients/{patient_id}/diseases")
async def detect_patient_diseases(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Detect diseases for a patient using the DiseaseDetectionSystem.
    """
    print(f"[API] Detecting diseases for patient {patient_id}")
    
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Gather patient data for analysis - using the same format as in insights endpoint
    patient_data = {}
    
    # Basic information
    patient_data["id"] = patient.id
    patient_data["mrn"] = patient.mrn
    patient_data["first_name"] = patient.first_name
    patient_data["last_name"] = patient.last_name
    patient_data["date_of_birth"] = patient.date_of_birth
    patient_data["gender"] = patient.gender
    
    # Medical conditions from history
    medical_history = db.query(MedicalHistory).filter(MedicalHistory.patient_id == patient_id).all()
    patient_data["medical_history"] = [
        {
            "condition": history.condition,
            "status": history.status,
            "onset_date": history.onset_date,
            "notes": history.notes
        }
        for history in medical_history
    ]
    
    # Family history
    family_history = db.query(FamilyHistory).filter(FamilyHistory.patient_id == patient_id).all()
    patient_data["family_history"] = [
        {
            "relation": history.relation,
            "condition": history.condition,
            "onset_age": history.onset_age,
            "notes": history.notes
        }
        for history in family_history
    ]
    
    # Medications
    medications = db.query(Medication).filter(Medication.patient_id == patient_id).all()
    patient_data["medications"] = [
        {
            "name": med.name,
            "dosage": med.dosage,
            "frequency": med.frequency,
            "route": med.route,
            "start_date": med.start_date,
            "active": med.active
        }
        for med in medications
    ]
    
    # Allergies
    allergies = db.query(Allergy).filter(Allergy.patient_id == patient_id).all()
    patient_data["allergies"] = [
        {
            "allergen": allergy.allergen,
            "reaction": allergy.reaction,
            "severity": allergy.severity
        }
        for allergy in allergies
    ]
    
    # Encounter data
    latest_encounter = db.query(Encounter).filter(
        Encounter.patient_id == patient_id
    ).order_by(Encounter.encounter_date.desc()).first()
    
    if latest_encounter:
        patient_data["encounter"] = {
            "encounter_date": latest_encounter.encounter_date.isoformat(),
            "encounter_type": latest_encounter.encounter_type,
            "chief_complaint": latest_encounter.chief_complaint,
            "vital_signs": json.loads(latest_encounter.vital_signs) if latest_encounter.vital_signs else {},
            "hpi": latest_encounter.hpi,
            "ros": latest_encounter.ros,
            "physical_exam": latest_encounter.physical_exam,
            "assessment": latest_encounter.assessment,
            "plan": latest_encounter.plan,
            "diagnosis_codes": latest_encounter.diagnosis_codes
        }
    
    # Lab results
    lab_results = []
    lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
    
    for order in lab_orders:
        results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
        for result in results:
            lab_results.append({
                "test_name": order.test_name,
                "result_value": result.result_value,
                "unit": result.unit,
                "reference_range": result.reference_range,
                "abnormal_flag": result.abnormal_flag,
                "result_date": result.result_date.isoformat()
            })
    
    patient_data["lab_results"] = lab_results
    
    # Scans
    scans = db.query(PatientScan).filter(PatientScan.patient_id == patient_id).all()
    patient_data["scans"] = []
    
    for scan in scans:
        # Get the scan analysis if available
        patient_data["scans"].append({
            "scan_type": scan.scan_type,
            "scan_date": scan.scan_date.isoformat(),
            "description": scan.description,
            "analysis": scan.notes or "No analysis available"
        })
    print(f'[PATIENT SCAN] {patient_data["scans"]}')
    # Initialize disease detection system and analyze patient
    disease_detection = DiseaseDetectionSystem()
    
    # Use default LLM model specified in the disease detection system
    detection_result = await disease_detection.analyze_patient(patient_data)
    
    # Save the analysis in the database
    analysis_id = str(uuid.uuid4())
    # print(f'[DEBUG DISEASE] {detection_result}')
    # Create a summary from the top disease match
    if detection_result.get("matched_diseases") and len(detection_result["matched_diseases"]) > 0:
        top_match = detection_result["matched_diseases"][0]
        recommendation = f"Likely diagnosis: {top_match['disease']} (ICD-10: {top_match.get('icd_code', 'Not specified')})"
        confidence = f"{top_match.get('probability', 0)}%"
    else:
        recommendation = "No clear diagnosis identified"
        confidence = "0%"
    
    # Create reasoning from clinical summary and recommendations
    reasoning = detection_result.get("clinical_summary", "No clinical summary provided.")
    if detection_result.get("additional_testing_recommended"):
        reasoning += "\n\nRecommended tests: " + ", ".join(detection_result["additional_testing_recommended"])
    
    # Add differential diagnoses
    if detection_result.get("differential_diagnoses"):
        reasoning += "\n\nDifferential diagnoses:\n"
        for i, diff in enumerate(detection_result["differential_diagnoses"][:5], 1):
            reasoning += f"{i}. {diff['disease']} ({diff.get('probability', 0)}%): {diff.get('reasoning', 'No explanation provided')}\n"
    
    # Save to database
    db_analysis = AIAnalysis(
        id=analysis_id,
        patient_id=patient_id,
        encounter_id=latest_encounter.id if latest_encounter else None,
        analysis_type="Disease Detection",
        recommendation=recommendation,
        reasoning=reasoning,
        confidence=confidence,
        model_used="Gemini",
        analysis_date=datetime.utcnow(),
        reviewed_by_provider=False
    )
    
    db.add(db_analysis)
    db.commit()
    
    # Return results with both the summary and full detection result
    return {
        "analysis_id": analysis_id,
        "summary": {
            "recommendation": recommendation,
            "reasoning": reasoning,
            "confidence": confidence
        },
        "full_result": detection_result
    }


# Copilot
@app.post("/api/copilot/query")
async def copilot_query(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process a copilot query with current context and return AI response.
    
    This endpoint accepts:
    - patient_id: Optional patient ID if in patient context
    - encounter_id: Optional encounter ID if in encounter context
    - current_view: What screen/tab the user is viewing (e.g., "dashboard", "lab-results")
    - view_mode: Either "list" (multiple patients) or "detail" (specific patient)
    - query: The user's explicit question (optional - if not provided, generate contextual insights)
    - action: Optional specific action to perform, like "detect_disease"
    """
    
    patient_id = request.get("patient_id")
    encounter_id = request.get("encounter_id")
    current_view = request.get("current_view", "unknown")
    view_mode = request.get("view_mode", "list")
    query = request.get("query", "")
    action = request.get("action", "")
    
    # Check if we need to perform a specific action
    if action == "detect_disease" and patient_id:
        try:
            # Call the disease detection endpoint directly
            print(f"[COPILOT] Calling disease detection for patient {patient_id}")
            detection_result = await detect_patient_diseases(
                patient_id=patient_id,
                db=db,
                current_user=current_user
            )
            
            # Format the response for the copilot
            return {
                "answer": f"Disease detection analysis completed. {detection_result['summary']['recommendation']}",
                "details": detection_result['summary']['reasoning'],
                "confidence": detection_result['summary']['confidence'],
                "analysis_id": detection_result['analysis_id'],
                "action_performed": "detect_disease",
                "suggestions": [
                    "View full analysis details",
                    "What does this diagnosis mean?",
                    "What treatments are recommended for this condition?"
                ],
                "references": ["Disease Detection Analysis"]
            }
        except Exception as e:
            print(f"[COPILOT] Error in disease detection: {str(e)}")
            return {
                "answer": "I encountered an error while trying to analyze diseases for this patient.",
                "error": str(e),
                "suggestions": [
                    "Try again later",
                    "Check patient data for completeness",
                    "Contact support if the issue persists"
                ]
            }
    
    # Get relevant context based on what the user is viewing
    context_data = await gather_context_data(
        db=db,
        patient_id=patient_id,
        encounter_id=encounter_id,
        current_view=current_view,
        view_mode=view_mode
    )
    
    # Check if the query is asking about disease detection
    if patient_id and (
        "disease" in query.lower() or 
        "diagnos" in query.lower() or 
        "detect" in query.lower() or
        "analyze symptoms" in query.lower() or
        "what condition" in query.lower()
    ):
        try:
            # Call the disease detection endpoint
            print(f"[COPILOT] Query about diseases detected, calling disease detection for patient {patient_id}")
            detection_result = await detect_patient_diseases(
                patient_id=patient_id,
                db=db,
                current_user=current_user
            )
            
            # Format the response for the copilot
            return {
                "answer": f"Based on the patient's data, I've run a disease detection analysis. {detection_result['summary']['recommendation']}",
                "details": detection_result['summary']['reasoning'],
                "confidence": detection_result['summary']['confidence'],
                "analysis_id": detection_result['analysis_id'],
                "action_performed": "detect_disease",
                "suggestions": [
                    "View full analysis details",
                    "What does this diagnosis mean?",
                    "What treatments are recommended for this condition?"
                ],
                "references": ["Disease Detection Analysis"]
            }
        except Exception as e:
            print(f"[COPILOT] Error in disease detection: {str(e)}")
            # Fall back to normal query processing if disease detection fails
            pass
    
    # Create appropriate prompt based on context and query
    if query:
        # User is asking a specific question
        prompt = create_query_prompt(context_data, query, view_mode)
    else:
        # Generate proactive insights based on current view
        prompt = create_insight_prompt(context_data, current_view)
    
    # Use the configured LLM to generate the response
    llm_response = Settings.llm.complete(prompt).text
    
    # Parse and structure the response
    try:
        structured_response = parse_copilot_response(llm_response)
        return structured_response
    except Exception as e:
        print(f"[COPILOT] Error parsing response: {str(e)}")
        return {
            "error": "Failed to parse AI response",
            "raw_response": llm_response
        }

@app.get("/api/patients/{patient_id}/disease-timeline")
async def get_disease_timeline(
    patient_id: str,
    timeline_range: str = "1-year",  # Options: "1-week", "1-month", "6-months", "1-year", "5-years"
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a future disease progression timeline for a patient based on current health data
    and AI predictions.
    """
    print(f"[API] Generating disease timeline for patient {patient_id} with range {timeline_range}")
    
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # First, get the disease detection result to use as a foundation
    # Run disease detection or get cached results if available
    disease_detection = await detect_patient_diseases(
        patient_id=patient_id,
        db=db,
        current_user=current_user
    )
    
    # Extract the diagnosed conditions from the results
    matched_diseases = disease_detection.get("full_result", {}).get("matched_diseases", [])
    if not matched_diseases:
        print(f"[API] No matched diseases found for patient {patient_id}")
        return {
            "timeline": [],
            "message": "Unable to generate timeline - no diseases detected"
        }
    
    # Get the primary disease (highest probability)
    primary_disease = matched_diseases[0]
    disease_name = primary_disease.get("disease", "Unknown condition")
    confidence = primary_disease.get("probability", 0)
    
    # Parse the timeline range into timeframes
    timeframe_mapping = {
        "1-week": {"unit": "days", "interval": 1, "periods": 7},
        "1-month": {"unit": "days", "interval": 3, "periods": 10},
        "6-months": {"unit": "weeks", "interval": 2, "periods": 12},
        "1-year": {"unit": "months", "interval": 1, "periods": 12},
        "5-years": {"unit": "months", "interval": 3, "periods": 20}
    }
    
    timeframe = timeframe_mapping.get(timeline_range, timeframe_mapping["1-year"])
    
    # Get patient's medication, lab results, and other relevant data
    medications = db.query(Medication).filter(Medication.patient_id == patient_id).all()
    lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
    lab_results = []
    for order in lab_orders:
        results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
        if results:
            for result in results:
                lab_results.append({
                    "test_name": order.test_name,
                    "result_value": result.result_value,
                    "unit": result.unit,
                    "reference_range": result.reference_range,
                    "abnormal_flag": result.abnormal_flag,
                    "result_date": result.result_date.isoformat() if hasattr(result.result_date, 'isoformat') else result.result_date
                })
    
    # Calculate date ranges for the timeline
    start_date = datetime.utcnow()
    
    # Create a context object with all relevant patient information
    context = {
        "patient": {
            "id": patient.id,
            "name": f"{patient.first_name} {patient.last_name}",
            "age": calculate_age(patient.date_of_birth),
            "gender": patient.gender,
            "current_diagnosis": disease_name,
            "diagnosis_confidence": confidence
        },
        "current_medications": [
            {
                "name": med.name,
                "dosage": med.dosage,
                "frequency": med.frequency,
                "route": med.route,
                "active": med.active
            }
            for med in medications
        ],
        "recent_lab_results": lab_results[:10],  # Most recent 10 lab results
        "disease_details": primary_disease,
        "differential_diagnoses": disease_detection.get("full_result", {}).get("differential_diagnoses", []),
        "timeframe": timeframe
    }

    # Corrected prompt with proper escaping of curly braces
    prompt = f"""
    You are a medical AI assistant tasked with predicting the likely progression of a patient's disease over time.
    Based on the patient information and current diagnosis below, generate a detailed timeline showing the expected 
    progression of their condition, potential symptoms, recommended treatments, and expected lab results at each stage.
    
    PATIENT INFORMATION:
    Name: {patient.first_name} {patient.last_name}
    Age: {calculate_age(patient.date_of_birth)}
    Gender: {patient.gender}
    Primary Diagnosis: {disease_name} (Confidence: {confidence}%)
    
    CURRENT MEDICATIONS:
    {json.dumps(context["current_medications"], indent=2)}
    
    RECENT LAB RESULTS:
    {json.dumps(context["recent_lab_results"], indent=2)}
    
    DIAGNOSIS DETAILS:
    {json.dumps(primary_disease, indent=2)}
    
    DIFFERENTIAL DIAGNOSES:
    {json.dumps(context["differential_diagnoses"], indent=2)}
    
    TIMEFRAME:
    Create a timeline with {timeframe["periods"]} points, each separated by {timeframe["interval"]} {timeframe["unit"]}.
    Start from the current date ({start_date.strftime('%Y-%m-%d')}).
    
    For each timepoint in the timeline, predict:
    1. The expected symptoms and severity (mild, moderate, severe)
    2. Disease progression status (improving, stable, worsening)
    3. Recommended treatments or medication changes
    4. Expected lab values that should be monitored
    5. Any potential complications to watch for
    
    Return your response as a JSON array with the following structure:
    [
      {{
        "date": "ISO-format date string",
        "timepoint_label": "e.g., 'Initial'/'Week 2'/'Month 3'/etc.",
        "symptoms": [
          {{
            "name": "symptom name",
            "severity": "mild/moderate/severe"
          }}
        ],
        "status": "improving/stable/worsening",
        "disease_stage": "early/progressing/advanced/etc.",
        "treatment_recommendations": ["recommendation 1", "recommendation 2"],
        "expected_lab_values": [
          {{
            "test": "test name",
            "expected_value": "value",
            "interpretation": "description"
          }}
        ],
        "potential_complications": ["complication 1", "complication 2"],
        "notes": "Additional relevant information for this timepoint"
      }}
    ]
    
    IMPORTANT: Return only valid JSON. Do not include any explanatory notes or comments outside the JSON structure.
    
    Be medically accurate and base your predictions on established progression patterns for {disease_name}.
    Incorporate the patient's age, gender, current medications, and lab results into your predictions.
    """
    
    # Call the LLM to generate the timeline
    print(f"[API] Calling LLM to generate disease timeline for {disease_name}")
    response = Settings.llm.complete(prompt)
    print(f"[API] Received response from LLM")
    
    # Parse the response
    try:
        # Clean up response in case it includes markdown code block formatting
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        # Clean up any comments or trailing text that might break JSON parsing
        # Find the closing bracket of the JSON array
        try:
            # Look for the matching closing bracket of the JSON array
            bracket_count = 0
            for i, char in enumerate(response_text):
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        # Found the closing bracket of the main array
                        response_text = response_text[:i+1]
                        break
        except Exception as e:
            print(f"[API] Error trying to clean response text: {str(e)}")
        
        # Remove any comments that might be inside the JSON
        try:
            lines = response_text.split('\n')
            cleaned_lines = []
            for line in lines:
                # Remove lines that start with // or /* (JSON comments)
                if line.strip().startswith("//") or line.strip().startswith("/*"):
                    continue
                # Remove inline comments
                comment_start = line.find("//")
                if comment_start != -1:
                    line = line[:comment_start]
                cleaned_lines.append(line)
            response_text = "\n".join(cleaned_lines)
        except Exception as e:
            print(f"[API] Error removing comments: {str(e)}")
        
        # Try to parse the JSON
        try:
            timeline_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"[API] JSON parsing error: {str(e)}")
            # Try a more aggressive approach - use regex to extract the JSON array
            import re
            match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if match:
                try:
                    timeline_data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    # If still failing, create a minimal valid structure
                    timeline_data = []
            else:
                timeline_data = []
        
        # Validate the response structure
        if not isinstance(timeline_data, list):
            print(f"[API] Invalid timeline data format: not a list")
            timeline_data = []
        
        # Enhance the timeline data with additional metadata
        enhanced_timeline = {
            "patient_id": patient_id,
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "primary_diagnosis": disease_name,
            "confidence": confidence,
            "generated_at": datetime.utcnow().isoformat(),
            "timeline_range": timeline_range,
            "timeline_data": timeline_data
        }
        
        # Save the timeline prediction to the database
        timeline_id = str(uuid.uuid4())
        prediction_record = {
            "id": timeline_id,
            "patient_id": patient_id,
            "primary_diagnosis": disease_name,
            "confidence": confidence,
            "timeline_range": timeline_range,
            "timeline_data": json.dumps(timeline_data),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Save to file for reference
        timeline_path = f"ehr_records/disease_timeline_{timeline_id}.json"
        with open(timeline_path, "w") as f:
            json.dump(enhanced_timeline, f, indent=2)
        
        print(f"[API] Successfully generated disease timeline with {len(timeline_data)} timepoints")
        return enhanced_timeline
        
    except Exception as e:
        print(f"[API] Error parsing LLM response for disease timeline: {str(e)}")
        print(f"[API] Raw response: {response.text}")
        
        # Return error response
        return {
            "error": f"Failed to generate disease timeline: {str(e)}",
            "patient_id": patient_id,
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "primary_diagnosis": disease_name,
            "confidence": confidence,
            "generated_at": datetime.utcnow().isoformat(),
            "timeline_range": timeline_range,
            "timeline_data": []
        }
# AI Analysis endpoints
@app.post("/api/ai_analysis", response_model=dict)
async def create_ai_analysis(analysis: AIAnalysisCreate, db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"[API] Creating AI analysis for patient {analysis.patient_id}, type: {analysis.analysis_type}")
    # Verify patient exists
    patient = db.query(Patient).filter(Patient.id == analysis.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Process any selected scans if available
    enhanced_input_text = analysis.input_text
    scan_analyses = []
    
    if analysis.scan_ids and len(analysis.scan_ids) > 0:
        print(f"[API] Processing {len(analysis.scan_ids)} selected scans")
        
        # Get scan records from the database
        scans = db.query(PatientScan).filter(PatientScan.id.in_(analysis.scan_ids)).all()
        if not scans:
            print(f"[API] No scans found in database for the provided IDs")
        else:
            print(f"[API] Found {len(scans)} scans in database")
            
            # Set up GCS bucket for downloading scans
            bucket = storage_client.bucket(BUCKET_NAME)
            
            # Analyze each scan in parallel
            scan_analysis_tasks = [analyze_scan(scan, bucket) for scan in scans]
            
            # Gather all scan analysis results
            for scan_task in scan_analysis_tasks:
                scan_analysis = await scan_task
                scan_analyses.append(scan_analysis)
            
            # Add scan analyses to the input text
            if scan_analyses:
                scan_section = "\n\n--- IMAGING & SCANS ANALYSIS ---\n"
                for idx, analysis_result in enumerate(scan_analyses, 1):
                    scan_section += f"\n[Scan {idx}: {analysis_result['scan_type']} ({analysis_result['scan_date']})]"
                    scan_section += f"\nFile: {analysis_result['file_name']}"
                    if analysis_result['description']:
                        scan_section += f"\nDescription: {analysis_result['description']}"
                    scan_section += f"\nAnalysis: {analysis_result['analysis']}\n"
                
                enhanced_input_text += scan_section
                print(f"[API] Enhanced input text with scan analyses")
    
    # Extract medical entities from the clinical text
    print(f"[API] Extracting medical entities from clinical text")
    entity_results = extract_medical_entities(enhanced_input_text)
    
    # Add entity analysis to the input text
    if "entity_groups" in entity_results and entity_results["entity_groups"]:
        entity_section = "\n\n--- MEDICAL ENTITY ANALYSIS ---\n"
        for entity_type, entities in entity_results["entity_groups"].items():
            if entities:
                entity_section += f"\n{entity_type}: {', '.join(entities)}"
        
        enhanced_input_text += entity_section
        print(f"[API] Enhanced input text with medical entity analysis")
        print(f"[API] Identified {len(entity_results['entities'])} medical entities across {len(entity_results['entity_groups'])} categories")
    
    # Create input format for analysis
    patient_input = {
        "type": "raw_text",
        "payload": enhanced_input_text
    }
    
    # Determine which type of analysis to perform based on analysis_type
    analysis_type = analysis.analysis_type.lower()
    
    # Load patient data as document
    patient_docs = [Document(text=enhanced_input_text, metadata={"source": "raw_text"})]
    
    # Generate query for context retrieval
    query = summarize_patient_data(patient_docs)
    
    # Choose context retrieval method based on analysis type
    if analysis_type == "genetic testing recommendation":
        # Use MedRAG for genetic testing (existing implementation)
        print(f"[API] Using MedRAG corpus for genetic testing analysis")
        medrag = MedRAG(llm_name=analysis.llm_model, rag=True)
        messages, retrieved_docs, scores = medrag.createMessage(question=query, k=32, split=True)
        context = "\n".join([doc["contents"] for doc in retrieved_docs])
        
        # Create prompt
        prompt = ehr_prompt.render(patient_data=enhanced_input_text, context=context)
        
    elif analysis_type == "diagnosis suggestion" or analysis_type == "risk assessment":
        # Use enhanced literature retrieval instead of Perplexity API
        print(f"[API] Using enhanced literature retrieval for {analysis_type}")
        perplexity_type = "diagnosis" if analysis_type == "diagnosis suggestion" else "risk_assessment"
        
        # Get literature-based context using the new enhanced retrieval
        web_context = await enhanced_literature_retrieval(
            entity_groups=entity_results.get("entity_groups", {}), 
            analysis_type=perplexity_type,
            scan_analyses=scan_analyses
        )
        print(f'[WEB CONTEXT] {web_context}')
        # Choose appropriate template
        if analysis_type == "diagnosis suggestion":
            prompt = diagnosis_prompt.render(patient_data=enhanced_input_text, context=web_context)
        else:  # risk assessment
            prompt = risk_assessment_prompt.render(patient_data=enhanced_input_text, context=web_context)
            
        # For tracking - use a placeholder for retrieved docs
        retrieved_docs = [{"id": "medical_literature", "contents": web_context}]
        
    else:
        # Default to genetic testing if unknown type
        print(f"[API] Unknown analysis type '{analysis_type}', defaulting to genetic testing")
        medrag = MedRAG(llm_name=analysis.llm_model, rag=True)
        messages, retrieved_docs, scores = medrag.createMessage(question=query, k=32, split=True)
        context = "\n".join([doc["contents"] for doc in retrieved_docs])
        prompt = ehr_prompt.render(patient_data=enhanced_input_text, context=context)
    
    # Log the full prompt for debugging
    print(f"[API] FULL AUGMENTED PROMPT:\n{'-'*80}\n{prompt[:500]}...\n[...truncated...]\n{'-'*80}")
    
    # Set LLM
    Settings.llm = LLM_MODELS[analysis.llm_model]
    
    # Get response
    response = Settings.llm.complete(prompt).text
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    if response.endswith("```"):
        response = response[:-3]
    response = response.strip()
    
    # Parse response based on analysis type
    try:
        result = json.loads(response)
        
        if analysis_type == "genetic testing recommendation":
            recommendation = result.get("testing_recommendation", "Unknown")
            reasoning = result.get("reasoning", "No reasoning provided")
            confidence = result.get("confidence", "80%")
            
        elif analysis_type == "diagnosis suggestion":
            recommendation = result.get("primary_diagnosis", "Unknown")
            reasoning = result.get("reasoning", "No reasoning provided")
            
            # Format differential diagnoses if present
            if "differential_diagnoses" in result:
                differential = result["differential_diagnoses"]
                if isinstance(differential, list):
                    reasoning += "\n\nDifferential Diagnoses:\n" + "\n".join([f"- {dx}" for dx in differential[:5]])
                elif isinstance(differential, dict):
                    reasoning += "\n\nDifferential Diagnoses:\n" + "\n".join([f"- {dx}: {desc}" for dx, desc in list(differential.items())[:5]])
                    
            confidence = result.get("confidence", "75%")
            
        elif analysis_type == "risk assessment":
            recommendation = "Risk Assessment"
            
            # Format risk areas if present
            if "risk_areas" in result:
                risk_areas = result["risk_areas"]
                high_risks = []
                
                if isinstance(risk_areas, dict):
                    # Handle dictionary format 
                    for area, level in risk_areas.items():
                        if isinstance(level, str) and "high" in level.lower():
                            high_risks.append(f"{area}")
                elif isinstance(risk_areas, list):
                    # Handle list format with extra checks
                    for item in risk_areas:
                        if isinstance(item, dict):
                            # It's a dict in a list - extract relevant info
                            if "area" in item and "level" in item:
                                if "high" in str(item["level"]).lower():
                                    high_risks.append(f"{item['area']}")
                            else:
                                # Just use the first k/v pair
                                for k, v in item.items():
                                    high_risks.append(f"{v}")
                                    break
                        else:
                            # Regular string item
                            high_risks.append(str(item))
                    
                if high_risks:
                    recommendation = "High Risk: " + ", ".join(high_risks)
                else:
                    recommendation = "No high-risk areas identified"
            
            # Build reasoning from multiple fields with robust parsing
            reasoning_parts = []
            
            # Risk factors with robust handling
            if "risk_factors" in result:
                factors = result["risk_factors"]
                factor_text = "Risk Factors:\n"
                
                if isinstance(factors, list):
                    factor_items = []
                    for factor in factors:
                        if isinstance(factor, dict):
                            # Dictionary in a list - format appropriately
                            for k, v in factor.items():
                                if isinstance(v, (list, tuple)):
                                    factor_items.append(f"- {k}: {', '.join(str(x) for x in v)}")
                                else:
                                    factor_items.append(f"- {k}: {v}")
                        else:
                            # String or other simple type
                            factor_items.append(f"- {str(factor)}")
                    factor_text += "\n".join(factor_items)
                elif isinstance(factors, dict):
                    # Simple dictionary
                    factor_text += "\n".join([f"- {k}: {v}" for k, v in factors.items()])
                else:
                    # Anything else, convert to string
                    factor_text += str(factors)
                
                reasoning_parts.append(factor_text)
            
            # Mitigation strategies with similar robust handling
            if "mitigation_strategies" in result:
                strategies = result["mitigation_strategies"]
                strategy_text = "Mitigation Strategies:\n"
                
                if isinstance(strategies, list):
                    strategy_items = []
                    for strategy in strategies:
                        if isinstance(strategy, dict):
                            # Dictionary in a list
                            for k, v in strategy.items():
                                if isinstance(v, (list, tuple)):
                                    strategy_items.append(f"- {k}: {', '.join(str(x) for x in v)}")
                                else:
                                    strategy_items.append(f"- {k}: {v}")
                        else:
                            # String or other simple type
                            strategy_items.append(f"- {str(strategy)}")
                    strategy_text += "\n".join(strategy_items)
                elif isinstance(strategies, dict):
                    # Simple dictionary
                    strategy_text += "\n".join([f"- {k}: {v}" for k, v in strategies.items()])
                else:
                    # Anything else, convert to string
                    strategy_text += str(strategies)
                
                reasoning_parts.append(strategy_text)
            
            # Follow-up recommendations
            if "follow_up_recommendations" in result:
                follow_up = result["follow_up_recommendations"]
                follow_up_text = "Follow-up Recommendations:\n"
                
                if isinstance(follow_up, list):
                    follow_up_text += "\n".join([f"- {rec}" for rec in follow_up])
                elif isinstance(follow_up, dict):
                    follow_up_text += "\n".join([f"- {k}: {v}" for k, v in follow_up.items()])
                else:
                    follow_up_text += str(follow_up)
                
                reasoning_parts.append(follow_up_text)
            
            # Join all reasoning sections
            reasoning = "\n\n".join(reasoning_parts) if reasoning_parts else "No detailed reasoning provided."
            confidence = result.get("confidence", "85%")
        
        else:
            # Default parsing
            recommendation = result.get("recommendation", "Unknown")
            reasoning = result.get("reasoning", "No reasoning provided")
            confidence = result.get("confidence", "70%")
            
    except Exception as e:
        print(f"[API] ERROR parsing response: {str(e)}")
        recommendation = "Error"
        reasoning = f"Failed to parse LLM response: {str(e)}"
        confidence = "0%"
    
    # Create analysis record
    analysis_id = str(uuid.uuid4())
    
    db_analysis = AIAnalysis(
        id=analysis_id,
        patient_id=analysis.patient_id,
        encounter_id=analysis.encounter_id,
        analysis_type=analysis.analysis_type,
        recommendation=recommendation,
        reasoning=reasoning,
        confidence=confidence,
        model_used=analysis.llm_model
    )
    
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    
    # Save analysis to file
    analysis_record = {
        "id": db_analysis.id,
        "patient_id": db_analysis.patient_id,
        "encounter_id": db_analysis.encounter_id,
        "analysis_type": db_analysis.analysis_type,
        "input_text": enhanced_input_text,
        "recommendation": db_analysis.recommendation,
        "reasoning": db_analysis.reasoning,
        "confidence": db_analysis.confidence,
        "model_used": db_analysis.model_used,
        "retrieved_docs": retrieved_docs,
        "scan_analyses": scan_analyses,
        "medical_entities": entity_results.get("entity_groups", {}),
        "analysis_date": db_analysis.analysis_date.isoformat(),
        "created_at": db_analysis.created_at.isoformat()
    }
    
    analysis_path = f"ehr_records/{db_analysis.id}.json"
    with open(analysis_path, "w") as f:
        json.dump(analysis_record, f, indent=2)
    
    return {
        "id": db_analysis.id,
        "patient_id": db_analysis.patient_id,
        "analysis_type": db_analysis.analysis_type,
        "recommendation": db_analysis.recommendation,
        "reasoning": db_analysis.reasoning,
        "confidence": db_analysis.confidence,
        "model_used": db_analysis.model_used,
        "scan_count": len(scan_analyses),
        "entity_count": len(entity_results.get("entities", [])),
        "message": "Analysis created successfully"
    }

# Add this code to your backend after the existing `/api/ai_analysis` POST endpoint
@app.get("/api/ai_analysis", response_model=List[dict])
async def get_ai_analyses(db = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Get all AI analyses, with patient names included for display
    """
    print(f"[API] Fetching AI analyses for user {current_user.username}")
    
    analyses = db.query(AIAnalysis).all()
    
    results = []
    for analysis in analyses:
        # Get patient info for each analysis
        patient = db.query(Patient).filter(Patient.id == analysis.patient_id).first()
        patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Unknown Patient"
        
        # Format analysis for response
        analysis_data = {
            "id": analysis.id,
            "patient_id": analysis.patient_id,
            "patient_name": patient_name,  # Include patient name for display
            "encounter_id": analysis.encounter_id,
            "analysis_type": analysis.analysis_type,
            "recommendation": analysis.recommendation,
            "reasoning": analysis.reasoning,
            "confidence": analysis.confidence,
            "model_used": analysis.model_used,
            "analysis_date": analysis.analysis_date.isoformat(),
            "reviewed_by_provider": analysis.reviewed_by_provider,
            "created_at": analysis.created_at.isoformat()
        }
        
        # If reviewed, add reviewer info
        if analysis.reviewed_by_provider and analysis.reviewer_id:
            reviewer = db.query(User).filter(User.id == analysis.reviewer_id).first()
            if reviewer:
                analysis_data["reviewer_name"] = reviewer.full_name
        
        results.append(analysis_data)
    
    print(f"[API] Returning {len(results)} AI analyses")
    return results

@app.get("/api/ai_analysis/{analysis_id}", response_model=dict)
async def get_ai_analysis(analysis_id: str, db = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Get a specific AI analysis by ID
    """
    print(f"[API] Fetching AI analysis {analysis_id}")
    
    analysis = db.query(AIAnalysis).filter(AIAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get patient info
    patient = db.query(Patient).filter(Patient.id == analysis.patient_id).first()
    patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Unknown Patient"
    
    # Format analysis for response
    analysis_data = {
        "id": analysis.id,
        "patient_id": analysis.patient_id,
        "patient_name": patient_name,
        "encounter_id": analysis.encounter_id,
        "analysis_type": analysis.analysis_type,
        "recommendation": analysis.recommendation,
        "reasoning": analysis.reasoning,
        "confidence": analysis.confidence,
        "model_used": analysis.model_used,
        "analysis_date": analysis.analysis_date.isoformat(),
        "reviewed_by_provider": analysis.reviewed_by_provider,
        "created_at": analysis.created_at.isoformat()
    }
    
    # If reviewed, add reviewer info
    if analysis.reviewed_by_provider and analysis.reviewer_id:
        reviewer = db.query(User).filter(User.id == analysis.reviewer_id).first()
        if reviewer:
            analysis_data["reviewer_name"] = reviewer.full_name
    
    return analysis_data

# Add this endpoint to mark an analysis as reviewed
@app.put("/api/ai_analysis/{analysis_id}/review", response_model=dict)
async def review_ai_analysis(
    analysis_id: str, 
    review_notes: str = Form(""), 
    db = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    """
    Mark an AI analysis as reviewed by a provider
    """
    print(f"[API] Marking AI analysis {analysis_id} as reviewed")
    
    if not current_user.is_doctor:
        raise HTTPException(status_code=403, detail="Only doctors can review analyses")
    
    analysis = db.query(AIAnalysis).filter(AIAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Update the analysis
    analysis.reviewed_by_provider = True
    analysis.reviewer_id = current_user.id
    analysis.review_notes = review_notes
    analysis.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "id": analysis.id,
        "reviewed_by_provider": True,
        "reviewer_id": current_user.id,
        "review_notes": review_notes,
        "message": "Analysis marked as reviewed"
    }

@app.post("/api/patients/bulk", response_model=Dict[str, Any])
async def bulk_create_patients(
    file: UploadFile = File(...),
    db = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    """
    Create multiple patients from a CSV or Excel file
    """
    print(f"[API] Bulk patient upload requested by {current_user.username}")
    
    # Check file extension
    file_extension = file.filename.split('.')[-1].lower()
    if file_extension not in ['csv', 'xlsx', 'xls']:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a CSV or Excel file.")
    
    # Read the file content
    contents = await file.read()
    
    try:
        # Parse the file based on its extension
        if file_extension == 'csv':
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        else:  # Excel file
            df = pd.read_excel(io.BytesIO(contents))
        
        # Validate the DataFrame columns
        required_columns = ['first_name', 'last_name', 'date_of_birth', 'gender']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        # Prepare counters for statistics
        total_patients = len(df)
        successful_patients = 0
        failed_patients = 0
        error_records = []
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Prepare patient data with proper type conversion
                patient_data = {
                    "first_name": str(row.get('first_name', '')),
                    "last_name": str(row.get('last_name', '')),
                    "date_of_birth": row.get('date_of_birth').strftime('%Y-%m-%d') if pd.notnull(row.get('date_of_birth')) else '',
                    "gender": str(row.get('gender', '')),
                    "address": str(row.get('address', '')) if pd.notnull(row.get('address')) else None,
                    "phone": str(row.get('phone', '')) if pd.notnull(row.get('phone')) else None,
                    "email": str(row.get('email', '')) if pd.notnull(row.get('email')) else None,
                    "insurance_provider": str(row.get('insurance_provider', '')) if pd.notnull(row.get('insurance_provider')) else None,
                    "insurance_id": str(row.get('insurance_id', '')) if pd.notnull(row.get('insurance_id')) else None,
                    "primary_care_provider": str(row.get('primary_care_provider', '')) if pd.notnull(row.get('primary_care_provider')) else None,
                    "emergency_contact_name": str(row.get('emergency_contact_name', '')) if pd.notnull(row.get('emergency_contact_name')) else None,
                    "emergency_contact_phone": str(row.get('emergency_contact_phone', '')) if pd.notnull(row.get('emergency_contact_phone')) else None
                }
                
                # Validate the patient data
                if not patient_data["first_name"]:
                    raise ValueError("First name is required")
                if not patient_data["last_name"]:
                    raise ValueError("Last name is required")
                if not patient_data["date_of_birth"]:
                    raise ValueError("Date of birth is required")
                if not patient_data["gender"]:
                    raise ValueError("Gender is required")
                
                # Generate MRN
                mrn = generate_mrn()
                
                # Create patient record with explicit datetime fields
                now = datetime.utcnow()
                db_patient = Patient(
                    id=str(uuid.uuid4()),
                    mrn=mrn,
                    first_name=patient_data["first_name"],
                    last_name=patient_data["last_name"],
                    date_of_birth=patient_data["date_of_birth"],
                    gender=patient_data["gender"],
                    address=patient_data["address"],
                    phone=patient_data["phone"],
                    email=patient_data["email"],
                    insurance_provider=patient_data["insurance_provider"],
                    insurance_id=patient_data["insurance_id"],
                    primary_care_provider=patient_data["primary_care_provider"],
                    emergency_contact_name=patient_data["emergency_contact_name"],
                    emergency_contact_phone=patient_data["emergency_contact_phone"],
                    created_at=now,
                    updated_at=now
                )
                
                db.add(db_patient)
                
                # Save as JSON for reference (optional)
                patient_path = f"patients/{db_patient.id}.json"
                with open(patient_path, "w") as f:
                    patient_dict = {
                        "id": db_patient.id,
                        "mrn": db_patient.mrn,
                        "first_name": db_patient.first_name,
                        "last_name": db_patient.last_name,
                        "date_of_birth": db_patient.date_of_birth,
                        "gender": db_patient.gender,
                        "address": db_patient.address,
                        "phone": db_patient.phone,
                        "email": db_patient.email,
                        "insurance_provider": db_patient.insurance_provider,
                        "insurance_id": db_patient.insurance_id,
                        "primary_care_provider": db_patient.primary_care_provider,
                        "emergency_contact_name": db_patient.emergency_contact_name,
                        "emergency_contact_phone": db_patient.emergency_contact_phone,
                        "created_at": db_patient.created_at.isoformat() if db_patient.created_at else now.isoformat(),
                        "updated_at": db_patient.updated_at.isoformat() if db_patient.updated_at else now.isoformat()
                    }
                    json.dump(patient_dict, f, indent=2)
                
                successful_patients += 1
                
            except Exception as e:
                failed_patients += 1
                error_records.append({
                    "row": index + 2,  # +2 because index is 0-based and we need to account for header row
                    "data": row.to_dict(),
                    "error": str(e)
                })
                print(f"[API] Error processing patient at row {index + 2}: {str(e)}")
        
        # Commit all successful records to database
        try:
            db.commit()
            print(f"[API] Successfully committed {successful_patients} patients to database")
        except Exception as e:
            # If there's an error committing, roll back and count all as failed
            db.rollback()
            failed_patients = total_patients
            successful_patients = 0
            print(f"[API] Error committing patients to database: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        # Prepare response
        result = {
            "total": total_patients,
            "successful": successful_patients,
            "failed": failed_patients,
            "errors": error_records[:10] if error_records else []  # Limit to first 10 errors
        }
        
        # Save error log if there were failures
        if error_records:
            error_log_path = f"ehr_records/bulk_upload_errors_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            with open(error_log_path, "w") as f:
                json.dump({
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": current_user.username,
                    "filename": file.filename,
                    "total": total_patients,
                    "failed": failed_patients,
                    "errors": error_records
                }, f, indent=2)
            print(f"[API] Error log saved to {error_log_path}")
        
        return result
        
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    except pd.errors.ParserError:
        raise HTTPException(status_code=400, detail="Unable to parse the file. Please ensure it is a valid CSV or Excel file.")
    except Exception as e:
        print(f"[API] Unexpected error in bulk upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/api/patients/{patient_id}/report")
async def download_patient_report(patient_id: str, type: str = "full", db: Session = Depends(get_db)):
    """
    Generate a PDF patient report for either the last encounter or full history.
    """
    report_type = type
    logger.info(f"Generating report for patient {patient_id} with report_type={report_type}")

    # Fetch patient
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Initialize PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Company Header
    company_name = "Penn Healthcare"
    story.append(Paragraph(f"{company_name}", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Patient Report - {patient.first_name} {patient.last_name}", styles['Heading1']))
    story.append(Spacer(1, 12))

    # Patient Info
    dob = patient.date_of_birth
    if isinstance(dob, str):
        try:
            dob = datetime.strptime(dob, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            dob = dob
    else:
        dob = dob.strftime("%Y-%m-%d")

    patient_info = [
        ["MRN", patient.mrn],
        ["Date of Birth", dob],
        ["Gender", patient.gender]
    ]
    story.append(Paragraph("Patient Information", styles['Heading2']))
    story.append(Table(patient_info, colWidths=[100, 200]))
    story.append(Spacer(1, 12))
    print(f"[REPORT TYPE] {report_type}")
    # Encounters
    if report_type == "last":
        encounter = db.query(Encounter).filter(Encounter.patient_id == patient_id).order_by(Encounter.encounter_date.desc()).first()
        encounters = [encounter] if encounter else []
        logger.info(f"Last encounter mode: Found {len(encounters)} encounter(s) - {encounter.encounter_date if encounter else 'None'}")
    else:  # full
        encounters = db.query(Encounter).filter(Encounter.patient_id == patient_id).order_by(Encounter.encounter_date).all()
        logger.info(f"Full report mode: Found {len(encounters)} encounters")

    if encounters:
        story.append(Paragraph("Encounters", styles['Heading2']))
        for enc in encounters:
            enc_date = enc.encounter_date
            if isinstance(enc_date, str):
                try:
                    enc_date = datetime.strptime(enc_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                except ValueError:
                    enc_date = enc_date
            else:
                enc_date = enc_date.strftime("%Y-%m-%d")

            enc_data = [
                ["Date", enc_date],
                ["Type", enc.encounter_type or "N/A"],
                ["Chief Complaint", enc.chief_complaint or "N/A"],
                ["Vital Signs", json.dumps(json.loads(enc.vital_signs), indent=2) if enc.vital_signs != "{}" else "Not recorded"],
                ["History of Present Illness", enc.hpi or "N/A"],
                ["Review of Systems", enc.ros or "N/A"],
                ["Physical Exam", enc.physical_exam or "N/A"],
                ["Assessment", enc.assessment or "N/A"],
                ["Plan", enc.plan or "N/A"],
                ["Diagnosis Codes", enc.diagnosis_codes or "N/A"],
                ["Follow-up Instructions", enc.followup_instructions or "N/A"]
            ]
            story.append(Paragraph(f"Encounter - {enc_date}", styles['Heading3']))
            story.append(Table(enc_data, colWidths=[150, 350]))
            story.append(Spacer(1, 12))

            # AI Analysis (only for this encounter)
            ai_analyses = db.query(AIAnalysis).filter(AIAnalysis.encounter_id == enc.id).all()
            if ai_analyses:
                story.append(Paragraph("AI Analysis", styles['Heading3']))
                for analysis in ai_analyses:
                    analysis_data = [
                        ["Type", analysis.analysis_type],
                        ["Recommendation", analysis.recommendation],
                        ["Reasoning", analysis.reasoning],
                        ["Confidence", analysis.confidence]
                    ]
                    story.append(Table(analysis_data, colWidths=[150, 350]))
                story.append(Spacer(1, 6))

            # Lab Results (only for this encounter, if linked)
            lab_orders = db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()
            lab_results = []
            for order in lab_orders:
                if report_type == "last" and order.order_date <= enc.encounter_date:  # Only include labs up to this encounter
                    results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
                    lab_results.extend(results)
                elif report_type != "last":  # Include all labs for full report
                    results = db.query(LabResult).filter(LabResult.lab_order_id == order.id).all()
                    lab_results.extend(results)
            if lab_results:
                story.append(Paragraph("Lab Results", styles['Heading3']))
                lab_data = [["Test", "Result", "Unit", "Reference Range", "Abnormal Flag"]]
                for lab in lab_results:
                    lab_data.append([
                        lab.test_name or "N/A",
                        lab.result_value or "N/A",
                        lab.unit or "N/A",
                        lab.reference_range or "N/A",
                        lab.abnormal_flag or "N/A"
                    ])
                story.append(Table(lab_data, colWidths=[100, 100, 50, 100, 100]))
                story.append(Spacer(1, 6))

    else:
        story.append(Paragraph("No encounters found.", styles['Normal']))
        logger.info("No encounters found for this patient")

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=patient_report_{patient_id}_{report_type}.pdf"
        }
    )

## Allergies
@app.post("/api/allergies", response_model=dict)
async def create_allergy(
    allergy: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new allergy record for a patient.
    """
    print(f"[API] Creating allergy record with data: {allergy}")
    
    # Verify patient exists
    patient = db.query(Patient).filter(Patient.id == allergy["patient_id"]).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Create allergy record
    db_allergy = Allergy(
        id=str(uuid.uuid4()),
        patient_id=allergy["patient_id"],
        allergen=allergy["allergen"],
        reaction=allergy.get("reaction"),
        severity=allergy.get("severity", "Unknown"),
        onset_date=allergy.get("onset_date"),
        notes=allergy.get("notes")
    )
    
    db.add(db_allergy)
    db.commit()
    db.refresh(db_allergy)
    
    return {
        "id": db_allergy.id,
        "patient_id": db_allergy.patient_id,
        "allergen": db_allergy.allergen,
        "reaction": db_allergy.reaction,
        "severity": db_allergy.severity,
        "message": "Allergy record created successfully"
    }

@app.put("/api/allergies/{allergy_id}", response_model=dict)
async def update_allergy(
    allergy_id: str,
    allergy_update: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing allergy record.
    """
    print(f"[API] Updating allergy record {allergy_id} with data: {allergy_update}")
    
    # Find the allergy record
    db_allergy = db.query(Allergy).filter(Allergy.id == allergy_id).first()
    if not db_allergy:
        raise HTTPException(status_code=404, detail="Allergy record not found")
    
    # Verify the user has access to this patient's data
    patient = db.query(Patient).filter(Patient.id == db_allergy.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Associated patient not found")
    
    # Update fields
    if "allergen" in allergy_update:
        db_allergy.allergen = allergy_update["allergen"]
    
    if "reaction" in allergy_update:
        db_allergy.reaction = allergy_update["reaction"]
    
    if "severity" in allergy_update:
        db_allergy.severity = allergy_update["severity"]
    
    if "onset_date" in allergy_update:
        db_allergy.onset_date = allergy_update["onset_date"]
    
    if "notes" in allergy_update:
        db_allergy.notes = allergy_update["notes"]
    
    db_allergy.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_allergy)
    
    return {
        "id": db_allergy.id,
        "patient_id": db_allergy.patient_id,
        "allergen": db_allergy.allergen,
        "reaction": db_allergy.reaction,
        "severity": db_allergy.severity,
        "message": "Allergy record updated successfully"
    }

@app.delete("/api/allergies/{allergy_id}", response_model=dict)
async def delete_allergy(
    allergy_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an allergy record.
    """
    print(f"[API] Deleting allergy record {allergy_id}")
    
    # Find the allergy record
    db_allergy = db.query(Allergy).filter(Allergy.id == allergy_id).first()
    if not db_allergy:
        raise HTTPException(status_code=404, detail="Allergy record not found")
    
    # Delete the record
    db.delete(db_allergy)
    db.commit()
    
    return {
        "id": allergy_id,
        "message": "Allergy record deleted successfully"
    }
# Add this endpoint to your API section in the backend
# Update the API endpoint with improved error handling
from datetime import date

class MedicalHistoryUpdate(BaseModel):
    """Schema for updating medical history records"""
    condition: Optional[str] = None
    onset_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None

@app.post("/api/medical-histories", response_model=dict)
async def create_medical_history(
    medical_history: MedicalHistoryCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new medical history record for a patient.
    """
    print(f"[API] Creating medical history record for patient {medical_history.patient_id}")
    print(f"[API] Data received: {medical_history}")
    
    try:
        # Check if patient exists
        patient = db.query(Patient).filter(Patient.id == medical_history.patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Optional: Check permissions
        if not current_user.is_doctor and False:  # Temporarily disabled for testing
            raise HTTPException(status_code=403, detail="Only doctors can add medical history records")
        
        # Create new medical history record
        history_id = str(uuid.uuid4())
        
        db_history = MedicalHistory(
            id=history_id,
            patient_id=medical_history.patient_id,
            condition=medical_history.condition,
            onset_date=medical_history.onset_date,
            status=medical_history.status,
            notes=medical_history.notes
        )
        
        db.add(db_history)
        db.commit()
        db.refresh(db_history)
        
        print(f"[API] Created medical history record {history_id} for patient {medical_history.patient_id}")
        
        return {
            "id": db_history.id,
            "patient_id": db_history.patient_id,
            "condition": db_history.condition,
            "onset_date": db_history.onset_date,
            "status": db_history.status,
            "message": "Medical history record created successfully"
        }
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Log any other exceptions
        print(f"[API] Error creating medical history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create medical history: {str(e)}")

@app.put("/api/medical-histories/{record_id}", response_model=dict)
async def update_medical_history(
    record_id: str,
    medical_history: MedicalHistoryUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing medical history record.
    """
    print(f"[API] Updating medical history record {record_id}")
    print(f"[API] Update data received: {medical_history}")
    
    try:
        # Get the existing record
        existing_record = db.query(MedicalHistory).filter(MedicalHistory.id == record_id).first()
        if not existing_record:
            raise HTTPException(status_code=404, detail="Medical history record not found")
        
        # Optional: Check permissions (uncomment if needed)
        # if not current_user.is_doctor:
        #     raise HTTPException(status_code=403, detail="Only doctors can update medical history records")
        
        # Update fields
        if medical_history.condition is not None:
            existing_record.condition = medical_history.condition
        if medical_history.onset_date is not None:
            existing_record.onset_date = medical_history.onset_date
        if medical_history.status is not None:
            existing_record.status = medical_history.status
        if medical_history.notes is not None:
            existing_record.notes = medical_history.notes
            
        existing_record.updated_at = datetime.utcnow()
        
        # Commit changes
        db.commit()
        db.refresh(existing_record)
        
        print(f"[API] Updated medical history record {record_id}")
        
        return {
            "id": existing_record.id,
            "patient_id": existing_record.patient_id,
            "condition": existing_record.condition,
            "onset_date": existing_record.onset_date,
            "status": existing_record.status,
            "notes": existing_record.notes,
            "message": "Medical history record updated successfully"
        }
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Log any other exceptions
        print(f"[API] Error updating medical history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update medical history: {str(e)}")
    
@app.delete("/api/medical-histories/{record_id}", response_model=dict)
async def delete_medical_history(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an existing medical history record.
    """
    print(f"[API] Deleting medical history record {record_id}")
    
    try:
        # Get the existing record
        existing_record = db.query(MedicalHistory).filter(MedicalHistory.id == record_id).first()
        if not existing_record:
            raise HTTPException(status_code=404, detail="Medical history record not found")
        
        # Optional: Check permissions (uncomment if needed)
        # if not current_user.is_doctor:
        #     raise HTTPException(status_code=403, detail="Only doctors can delete medical history records")
        
        # Delete the record
        db.delete(existing_record)
        db.commit()
        
        print(f"[API] Deleted medical history record {record_id}")
        
        return {
            "id": record_id,
            "message": "Medical history record deleted successfully"
        }
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Log any other exceptions
        print(f"[API] Error deleting medical history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete medical history: {str(e)}")
        
# Add Lab Order Endpoint
@app.post("/api/lab-orders", response_model=dict)
async def create_lab_order(
    lab_order: LabOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_doctor:
        raise HTTPException(status_code=403, detail="Only doctors can order labs")
    
    patient = db.query(Patient).filter(Patient.id == lab_order.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    db_lab_order = LabOrder(
        id=str(uuid.uuid4()),
        patient_id=lab_order.patient_id,
        provider_id=current_user.id,
        test_name=lab_order.test_name,
        test_code=lab_order.test_code,
        priority=lab_order.priority,
        status="Ordered",
        order_date=datetime.utcnow().replace(tzinfo=pytz.utc),
        collection_date=lab_order.collection_date,  # Set this if provided
        notes=lab_order.notes
    )
    
    db.add(db_lab_order)
    db.commit()
    db.refresh(db_lab_order)
    
    return {
        "id": db_lab_order.id,
        "patient_id": db_lab_order.patient_id,
        "test_name": db_lab_order.test_name,
        "order_date": db_lab_order.order_date.isoformat(),
        "status": db_lab_order.status,
        "test_code": db_lab_order.test_code,
        "priority": db_lab_order.priority,
        "collection_date": db_lab_order.collection_date.isoformat() if db_lab_order.collection_date else None,
        "notes": db_lab_order.notes,
        "message": "Lab order created successfully"
    }

@app.put("/api/lab-orders/{lab_order_id}", response_model=dict)
async def update_lab_order(
    lab_order_id: str,
    update_data: LabOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_doctor:
        raise HTTPException(status_code=403, detail="Only doctors can update labs")
    
    db_lab_order = db.query(LabOrder).filter(LabOrder.id == lab_order_id).first()
    if not db_lab_order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    
    # Update only provided fields
    if update_data.test_code is not None:
        db_lab_order.test_code = update_data.test_code
    if update_data.priority is not None:
        db_lab_order.priority = update_data.priority
    if update_data.collection_date is not None:
        db_lab_order.collection_date = update_data.collection_date.replace(tzinfo=pytz.utc) if update_data.collection_date else None
    if update_data.notes is not None:
        db_lab_order.notes = update_data.notes
    if update_data.status is not None:
        db_lab_order.status = update_data.status
    
    db.commit()
    db.refresh(db_lab_order)
    
    return {
        "id": db_lab_order.id,
        "test_name": db_lab_order.test_name,
        "test_code": db_lab_order.test_code,
        "priority": db_lab_order.priority,
        "collection_date": db_lab_order.collection_date.isoformat() if db_lab_order.collection_date else None,
        "notes": db_lab_order.notes,
        "status": db_lab_order.status,
        "message": "Lab order updated successfully"
    }
# Add Lab Result Endpoint
@app.post("/api/lab-results", response_model=dict)
async def create_lab_result(
    lab_result: LabResultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if lab order exists
    lab_order = db.query(LabOrder).filter(LabOrder.id == lab_result.lab_order_id).first()
    if not lab_order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    
    # Create new lab result
    db_lab_result = LabResult(
        id=str(uuid.uuid4()),
        lab_order_id=lab_result.lab_order_id,
        result_value=lab_result.result_value,
        unit=lab_result.unit,
        reference_range=lab_result.reference_range,
        abnormal_flag=lab_result.abnormal_flag,
        performing_lab=lab_result.performing_lab,
        result_date=datetime.utcnow().replace(tzinfo=pytz.utc),
        notes=lab_result.notes
    )
    
    # Add to database
    db.add(db_lab_result)
    
    # Update lab order status to "Completed" when a result is added
    lab_order.status = "Completed"
    
    # If collection date isn't set, set it to current time
    if not lab_order.collection_date:
        lab_order.collection_date = datetime.utcnow().replace(tzinfo=pytz.utc)
    
    # Commit changes
    db.commit()
    db.refresh(db_lab_result)
    
    # Return the result
    return {
        "id": db_lab_result.id,
        "lab_order_id": db_lab_result.lab_order_id,
        "result_value": db_lab_result.result_value,
        "result_date": db_lab_result.result_date.isoformat(),
        "message": "Lab result added successfully"
    }
# Add Endpoint to Get Lab Order Details
@app.get("/api/lab-orders/{lab_order_id}", response_model=dict)
async def get_lab_order(
    lab_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lab_order = db.query(LabOrder).filter(LabOrder.id == lab_order_id).first()
    if not lab_order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    
    patient = db.query(Patient).filter(Patient.id == lab_order.patient_id).first()
    results = db.query(LabResult).filter(LabResult.lab_order_id == lab_order_id).all()
    
    # Format date fields properly
    order_date = lab_order.order_date.isoformat() if lab_order.order_date else None
    collection_date = lab_order.collection_date.isoformat() if lab_order.collection_date else None
    
    return {
        "id": lab_order.id,
        "patient": {
            "id": patient.id,
            "name": f"{patient.first_name} {patient.last_name}",
            "mrn": patient.mrn
        },
        "test_name": lab_order.test_name,
        "test_code": lab_order.test_code,  # This might be None but should be returned
        "priority": lab_order.priority,
        "status": lab_order.status,
        "order_date": order_date,
        "collection_date": collection_date,  # This is important to include
        "notes": lab_order.notes,
        "results": [{
            "id": result.id,
            "result_value": result.result_value,
            "unit": result.unit,
            "reference_range": result.reference_range,
            "abnormal_flag": result.abnormal_flag,
            "performing_lab": result.performing_lab,
            "result_date": result.result_date.isoformat() if result.result_date else None,
            "notes": result.notes
        } for result in results]
    }




#may102025
# @app.post("/api/index/assistant-documents")
# async def index_assistant_documents(request: dict):
#     assistant_id = request.get("assistant_id")
#     documents = request.get("documents", [])
#     print("INDEXING DOCUMENTS")
#     print(f"Assistant ID: {assistant_id}")
#     print(f"Number of documents to index: {len(documents)}")
    
#     if not assistant_id or not documents:
#         print("ERROR: assistant_id and documents are required")
#         return {"error": "assistant_id and documents are required"}
    
#     # Define a separate collection for documents
#     collection_name = f"documents_{assistant_id}_knowledge"
#     print(f"Creating/accessing collection: {collection_name}")
#     collection = chroma_client.get_or_create_collection(collection_name)
#     print(f"Collection size before indexing: {collection.count()}")
    
#     # Prepare LlamaIndex documents
#     llama_documents = []
#     for doc in documents:
#         doc_id = doc.get("id")
#         doc_name = doc.get("name", "Unnamed Document")
#         content = doc.get("content", "")
#         print(f"Processing document: {doc_name} (ID: {doc_id})")
#         print(f"Document content length: {len(content)} characters")
        
#         # Split large documents into chunks
#         splitter = SentenceSplitter(chunk_size=512, chunk_overlap=100)
#         chunks = splitter.split_text(content)
#         print(f"Document split into {len(chunks)} chunks")
        
#         for i, chunk in enumerate(chunks):
#             llama_doc = Document(
#                 text=chunk,
#                 metadata={
#                     "knowledge_type": "document",
#                     "document_id": doc_id,
#                     "document_name": doc_name,
#                     "assistant_id": assistant_id,
#                     "chunk_id": i
#                 }
#             )
#             llama_documents.append(llama_doc)
    
#     print(f"Total LlamaIndex documents created: {len(llama_documents)}")
    
#     # Set up vector store
#     vector_store = ChromaVectorStore(chroma_collection=collection)
#     print("Vector store setup complete")
    
#     # Create ingestion pipeline
#     pipeline = IngestionPipeline(
#         transformations=[
#             SentenceSplitter(chunk_size=512, chunk_overlap=100),
#             Settings.embed_model  # Use the same embedding model as flow indexing
#         ],
#         vector_store=vector_store
#     )
#     print("Ingestion pipeline created")
    
#     # Process and index documents
#     print("Starting document ingestion...")
#     nodes = pipeline.run(documents=llama_documents)
#     print(f"Ingestion complete. Created {len(nodes)} nodes")
#     print(f"Collection size after indexing: {collection.count()}")
    
#     return {
#         "status": "success",
#         "indexed_documents": len(documents),
#         "nodes_created": len(nodes),
#         "collection_name": collection_name
#     }

# @app.post("/api/shared/vector_chat")        
# async def vector_flow_chat(request: dict):
#     """
#     Process a chat message using the vector-based flow knowledge index.
#     This endpoint doesn't rely on Firestore or Gemini services.
#     """
#     import traceback  # Add missing import

#     try:
#         print("\n==== STARTING VECTOR CHAT PROCESSING ====")
#         message = request.get("message", "")
#         sessionId = request.get("sessionId", "")
#         flow_id = request.get("flow_id")
#         assistant_id = request.get("assistantId")
#         session_data = request.get("session_data", {})
#         previous_messages = request.get("previous_messages", [])
        
#         print(f"Message: '{message}'")
#         print(f"Session ID: {sessionId}")
#         print(f"Flow ID: {flow_id}")
#         print(f"Assistant ID: {assistant_id}")
#         print(f"Session data: {json.dumps(session_data, indent=2)}")
#         print(f"Number of previous messages: {len(previous_messages)}")
        
#         if not flow_id:
#             print("ERROR: flow_id is required")
#             return {
#                 "error": "flow_id is required",
#                 "content": "Missing required parameters"
#             }
        
#         # Create context for the query
#         current_node_id = session_data.get('currentNodeId')
#         print(f"Current node ID: {current_node_id}")
        
#         # Format previous messages for better context
#         conversation_history = ""
#         for msg in previous_messages:
#             role = msg.get("role", "unknown")
#             content = msg.get("content", "")
#             conversation_history += f"{role}: {content}\n"
        
#         print(f"Conversation history length: {len(conversation_history)} characters")
        
# #         context_text = f"""
# # The user message is: "{message}"

# # The current node ID is: {current_node_id or "None - this is the first message"}

# # Previous conversation:
# # {conversation_history}

# # The session data is:
# # {json.dumps(session_data, indent=2)}

# # Based on this information, process the message according to the flow logic.

# # If this is the first message, start with the node that has nodeType='starting'.
# # If currentNodeId is set, process that node.

# # You MUST follow these steps:
# # 1. Identify the correct node to process
# # 2. Follow the appropriate processing logic for that node type
# # 3. Determine the next node based on the user's message and the flow rules
# # 4. Generate the appropriate response
# # 5. Specify the next node ID and state updates
# # 6. Read the node's INSTRUCTION, which contains a message intended to guide the response.
# # 7. Treat the node's message as an instruction, not the literal text to send. Generate a natural, conversational response that captures the intent of the instruction in a friendly and appropriate tone.
# # 8. Do not repeat the instruction message verbatim under any circumstances.

# # Return your response as a JSON object with the following structure:
# # {{
# #     "content": "The response to send to the user",
# #     "next_node_id": "ID of the next node to process",
# #     "state_updates": {{
# #         "key": "value"
# #     }}
# # }}
# # """
        
        
#         # Get the flow knowledge index
#         flow_collection_name = f"flow_{flow_id}_knowledge"
#         print(f"Accessing flow collection: {flow_collection_name}")
        
#         # Check if collection exists
#         try:
#             flow_collection = chroma_client.get_collection(flow_collection_name)
#             print(f"Flow collection found with {flow_collection.count()} entries")
#         except ValueError:
#             # Collection doesn't exist, need to create the index first
#             print(f"ERROR: Flow collection {flow_collection_name} not found")
#             return {
#                 "error": "Flow knowledge index not found. Please index the flow first.",
#                 "content": "I'm having trouble processing your request. Please try again later."
#             }
        
#         # Create vector store and index
#         flow_vector_store = ChromaVectorStore(chroma_collection=flow_collection)
#         flow_storage_context = StorageContext.from_defaults(vector_store=flow_vector_store)
#         flow_index = VectorStoreIndex.from_vector_store(flow_vector_store, storage_context=flow_storage_context)
#         print("Flow vector index created successfully")
        
#             # Document retrieval section within vector_flow_chat function:
#         document_collection_name = f"documents_{assistant_id}_knowledge"  # flow_id is assistant_id
#         print(f"Checking for document collection: {document_collection_name}")
#         document_context = ""

#         # Check for cached index/retriever in app state first
#         document_indexes = getattr(app.state, "document_indexes", {})
#         cached_index_data = document_indexes.get(assistant_id)

#         if cached_index_data and "retriever" in cached_index_data:
#             print(f"Using cached document retriever for assistant {assistant_id}")
#             document_retriever = cached_index_data["retriever"]
            
#             # Get initial candidates from vector retriever
#             print(f"Retrieving documents for query: '{message}'")
#             retrieved_nodes = document_retriever.retrieve(message)
            
#             # Apply BM25 reranking if we have enough nodes
#             try:
#                 from llama_index.core.retrievers import BM25Retriever
                
#                 # Get just the node objects (without scores)
#                 node_objs = [n.node for n in retrieved_nodes]
                
#                 if len(node_objs) > 1:
#                     print(f"Applying BM25 reranking to {len(node_objs)} nodes")
#                     bm25_retriever = BM25Retriever.from_defaults(
#                         nodes=node_objs, 
#                         similarity_top_k=min(5, len(node_objs))
#                     )
                    
#                     # Get reranked results
#                     reranked_nodes = bm25_retriever.retrieve(message)
                    
#                     # Use these for generating context
#                     if reranked_nodes:
#                         document_text = "\n\n".join([n.node.get_content() for n in reranked_nodes])
#                         document_context = f"Relevant Document Content:\n{document_text}"
#                 else:
#                     # Not enough nodes for reranking, use as is
#                     document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#                     document_context = f"Relevant Document Content:\n{document_text}"
                
#                 print(f"Document retrieval complete, found content with {len(document_context)} characters")
#             except Exception as e:
#                 print(f"Error in BM25 reranking: {str(e)}, using vector results")
#                 document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#                 document_context = f"Relevant Document Content:\n{document_text}"

#         # If no cached index, fall back to the original approach
#         else:
#             try:
#                 document_collection = chroma_client.get_collection(document_collection_name)
#                 document_count = document_collection.count()
#                 print(f"Document collection found with {document_count} entries")
                
#                 if document_count > 0:
#                     print("Creating document vector store and index on the fly")
#                     document_vector_store = ChromaVectorStore(chroma_collection=document_collection)
#                     document_index = VectorStoreIndex.from_vector_store(document_vector_store)
                    
#                     # Create a better retriever that we'll cache for next time
#                     document_retriever = document_index.as_retriever(similarity_top_k=20)
                    
#                     # Cache for future use
#                     document_indexes[assistant_id] = {
#                         "index": document_index,
#                         "retriever": document_retriever,
#                         "created_at": datetime.now().isoformat()
#                     }
#                     app.state.document_indexes = document_indexes
                    
#                     # Query using standard approach for now
#                     print(f"Querying document index for: '{message}'")
#                     document_query_engine = document_index.as_query_engine(similarity_top_k=20)
#                     document_response = document_query_engine.query(message)
#                     document_context = f"Relevant Document Content:\n{document_response.response}"
#                     print(f"Document query returned content")
#                     print("Document context summary: " + document_context[:100] + "..." if len(document_context) > 100 else document_context)
#                 else:
#                     print("Document collection exists but is empty")
#             except ValueError:
#                 print(f"Document index {document_collection_name} not found; proceeding with flow only.")
        
#         context_text = f"""
# The user message is: "{message}"

# The current node ID is: {current_node_id or "None - this is the first message"}

# Previous conversation:
# {conversation_history}

# The session data is:
# {json.dumps(session_data, indent=2)}

# Relevant Document Content:
# {document_context}

# You are a helpful assistant tasked with providing accurate, specific, and context-aware responses. Follow these steps:
# 1. Identify the user's intent from the message and conversation history.
# 2. **IMPORTANT**: Scan the Relevant Document Content for any URLs, phone numbers, email addresses, or other specific resources (e.g., websites, programs, contact information).
# 3. **CRITICAL REQUIREMENT**: If ANY resources like URLs, phone numbers, or contact information are found in the document content, you MUST include them verbatim in your response regardless of whether the user explicitly requested them.
# 4. Generate a natural, conversational response that directly addresses the user's query, incorporating document content as needed.
# 5. Maintain continuity with the conversation history to stay focused on the user's current intent.
# 6. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION, but prioritize document content for specific details.
# 7. Do not repeat the node's INSTRUCTION verbatim; use it as a guide to craft a friendly, relevant response.
# 8. If no relevant document content is found, provide a helpful response based on the flow logic or general knowledge, and ask for clarification if needed.
# 9. Before finalizing your response, double-check that you've included all resource links, phone numbers, and contact methods from the document context.

# Return your response as a JSON object with the following structure:
# {{
#     "content": "The response to send to the user, including specific document content where applicable",
#     "next_node_id": "ID of the next node to process",
#     "state_updates": {{
#         "key": "value"
#     }}
# }}
# """
        
        
#         full_context = f"{context_text}\n\n{document_context}"
#         print(f"Full context length: {len(full_context)} characters")
        
#         # Create query engine
#         print("Creating flow query engine")
#         query_engine = flow_index.as_query_engine(
#             response_mode="compact",
#             similarity_top_k=7,  # Retrieve more context for complete instructions
#             llm=Settings.llm  # Use the specified LLM
#         )
        
#         # Query the index
#         print("Querying flow index with full context")
#         response = query_engine.query(full_context)
#         print("Query complete, processing response")
        
#         # Process the response
#         try:
#             # Parse the response text as JSON
#             response_text = response.response
#             print(f"Raw response length: {len(response_text)} characters")
            
#             # Clean up the response if it contains markdown code blocks
#             if "```json" in response_text:
#                 print("Parsing JSON from markdown code block with ```json")
#                 response_text = response_text.split("```json")[1].split("```")[0].strip()
#             elif "```" in response_text:
#                 print("Parsing JSON from markdown code block")
#                 response_text = response_text.split("```")[1].split("```")[0].strip()
            
#             print(f"Cleaned response: {response_text[:100]}..." if len(response_text) > 100 else response_text)
#             response_data = json.loads(response_text)
#             print("Successfully parsed JSON response")
            
#             # Extract fields
#             ai_response = response_data.get("content", "I'm having trouble processing your request.")
#             next_node_id = response_data.get("next_node_id")
#             state_updates = response_data.get("state_updates", {})
            
#             print(f"AI response length: {len(ai_response)} characters")
#             print(f"Next node ID: {next_node_id}")
#             print(f"State updates: {json.dumps(state_updates, indent=2)}")
#             print("==== VECTOR CHAT PROCESSING COMPLETE ====\n")
            
#             # Return the complete response
#             return {
#                 "content": ai_response,
#                 "next_node_id": next_node_id,
#                 "state_updates": state_updates
#             }
            
#         except Exception as e:
#             print(f"ERROR processing vector response: {str(e)}")
#             print(f"Response text that failed to parse: {response_text[:200]}...")
            
#             # Fallback to direct LLM response
#             print("Using fallback LLM response")
#             fallback_prompt = f"""
#             You are a helpful assistant. The user has sent the following message:
            
#             "{message}"
            
#             Previous conversation:
#             {conversation_history}
            
#             Please provide a helpful response.
#             """
            
#             fallback_response = Settings.llm.complete(fallback_prompt)
#             print(f"Fallback response generated, length: {len(fallback_response.text)} characters")
#             print("==== VECTOR CHAT PROCESSING COMPLETE (FALLBACK) ====\n")
            
#             return {
#                 "content": fallback_response.text,
#                 "error": f"Vector processing failed: {str(e)}",
#                 "fallback": True
#             }
            
#     except Exception as e:
#         print(f"CRITICAL ERROR in vector_chat: {str(e)}")
#         traceback_str = traceback.format_exc()
#         print(f"Traceback: {traceback_str}")
#         print("==== VECTOR CHAT PROCESSING FAILED ====\n")
#         return {
#             "error": f"Failed to process message: {str(e)}",
#             "content": "I'm having trouble processing your request. Please try again later."
#         } 

#lastworking on local may112025
# for the shared chat endpoint
# @app.post("/api/index/flow-knowledge")
# async def create_flow_knowledge_index(flow_data: dict):
#     """
#     Convert an entire flow structure into a knowledge base for LlamaIndex.
#     """
#     flow_id = flow_data.get("id", str(uuid.uuid4()))
#     nodes = flow_data.get("nodes", [])
#     edges = flow_data.get("edges", [])
    
#     documents = []
    
#     # Process all nodes
#     for node in nodes:
#         node_id = node.get("id")
#         node_type = node.get("type")
#         node_data = node.get("data", {})
        
#         # Create base document text
#         doc_text = f"NODE ID: {node_id}\nNODE TYPE: {node_type}\n\n"
        
#         # Add node specific processing instructions
#         if node_type == "dialogueNode":
#             doc_text += f"INSTRUCTION: When the user is at this dialogue node, display the message '{node_data.get('message', '')}' to the user.\n\n"
#             doc_text += "FUNCTIONS:\n"
#             for func in node_data.get("functions", []):
#                 func_id = func.get("id")
#                 func_content = func.get("content", "")
                
#                 # Find the edge for this function
#                 func_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"function-{node_id}-{func_id}"]
#                 if func_edges:
#                     target_node_id = func_edges[0].get("target")
#                     doc_text += f"- If user response matches '{func_content}', proceed to node {target_node_id}\n"
            
#         elif node_type == "scriptNode":
#             doc_text += f"INSTRUCTION: When the user is at this script node, display the message '{node_data.get('message', '')}' to the user.\n\n"
#             doc_text += "FUNCTIONS:\n"
#             for func in node_data.get("functions", []):
#                 func_id = func.get("id")
#                 func_content = func.get("content", "")
                
#                 # Find the edge for this function
#                 func_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"function-{node_id}-{func_id}"]
#                 if func_edges:
#                     target_node_id = func_edges[0].get("target")
#                     doc_text += f"- If processing this node requires '{func_content}', proceed to node {target_node_id}\n"
            
#         elif node_type == "fieldSetterNode":
#             doc_text += f"INSTRUCTION: When the user is at this field setter node, request the value for field '{node_data.get('fieldName', '')}' using the message: '{node_data.get('message', '')}'.\n\n"
            
#             # Find the outgoing edge
#             setter_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"{node_id}-right"]
#             if setter_edges:
#                 target_node_id = setter_edges[0].get("target")
#                 doc_text += f"After capturing the field value, proceed to node {target_node_id}\n"
            
#         elif node_type == "responseNode":
#             doc_text += f"INSTRUCTION: When the user is at this response node, display the message '{node_data.get('message', '')}' and then use the LLM to generate a conversational response.\n\n"
#             doc_text += "TRIGGERS:\n"
#             for trigger in node_data.get("triggers", []):
#                 trigger_id = trigger.get("id")
#                 trigger_content = trigger.get("content", "")
                
#                 # Find the edge for this trigger
#                 trigger_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"trigger-{node_id}-{trigger_id}"]
#                 if trigger_edges:
#                     target_node_id = trigger_edges[0].get("target")
#                     doc_text += f"- If user's response matches '{trigger_content}', proceed to node {target_node_id}\n"
            
#         elif node_type == "callTransferNode":
#             doc_text += f"INSTRUCTION: When the user is at this call transfer node, display the message '{node_data.get('message', '')}' and create a notification for human takeover.\n\n"
            
#             # Find any outgoing edge
#             transfer_edges = [e for e in edges if e.get("source") == node_id]
#             if transfer_edges:
#                 target_node_id = transfer_edges[0].get("target")
#                 doc_text += f"After notifying about the transfer, proceed to node {target_node_id}\n"
        
#         # Create document
#         documents.append(Document(
#             text=doc_text,
#             metadata={
#                 "node_id": node_id,
#                 "node_type": node_type,
#                 "flow_id": flow_id
#             }
#         ))
    
#     # Add global flow processing instructions
#     starting_node = next((node for node in nodes if node.get("data", {}).get("nodeType") == "starting" or 
#                     "nodeType" in node and node["nodeType"] == "starting"), None)
#     starting_node_id = starting_node["id"] if starting_node else None

#     print(f"Found starting node with ID: {starting_node_id}")

#     flow_instructions = f"""
#     FLOW ID: {flow_id}
    
#     GENERAL PROCESSING INSTRUCTIONS:
    
#     1. STARTING: use {starting_node_id} or When a new conversation begins, find the node with nodeType='starting' and process it first.
    
#     2. DIALOGUENODE PROCESSING:
#        - Display the node's message to the user
#        - Wait for user input
#        - Match user input against the node's functions
#        - If a match is found, transition to the corresponding target node
#        - If no match is found, generate a response using the LLM
    
#     3. SCRIPTNODE PROCESSING:
#        - Display the node's message to the user
#        - If the node has functions, check if any should be activated
#        - If a function is activated, transition to its target node
#        - Otherwise, move to the next connected node if one exists
    
#     4. FIELDSETTERNODE PROCESSING:
#        - Request the specified field value from the user
#        - Wait for user input
#        - Validate the input as a valid value for the field
#        - If valid, store the value and transition to the next node
#        - If invalid, ask the user again
    
#     5. RESPONSENODE PROCESSING:
#        - Display the node's message to the user
#        - Wait for user input
#        - Generate a response using the LLM
#        - Check if the user's next message matches any triggers
#        - If a trigger matches, transition to its target node
    
#     6. CALLTRANSFERNODE PROCESSING:
#        - Display the node's message to the user
#        - Create a notification for human transfer
#        - Transition to the next node if one exists
    
#     7. SESSION STATE:
#        - Always track which node the user is currently at
#        - Store field values collected from FieldSetterNodes
#        - Mark whether you're awaiting a response from the user
    
#     8. OUT-OF-FLOW HANDLING:
#        - If the user asks a question unrelated to the current node:
#          a. If it's a simple question, answer it directly
#          b. After answering, return to the current node's flow
#     """
    
#     # Add flow processing document
#     documents.append(Document(
#         text=flow_instructions,
#         metadata={
#             "flow_id": flow_id,
#             "type": "flow_instructions"
#         }
#     ))
    
#     # Add node connections document for reference
#     connections_text = "NODE CONNECTIONS:\n\n"
#     for edge in edges:
#         source = edge.get("source")
#         target = edge.get("target")
#         source_handle = edge.get("sourceHandle")
#         connections_text += f"From node {source} to node {target}"
#         if source_handle:
#             connections_text += f" via {source_handle}"
#         connections_text += "\n"
    
#     documents.append(Document(
#         text=connections_text,
#         metadata={
#             "flow_id": flow_id,
#             "type": "connections"
#         }
#     ))
    
#     # Create the index directory if it doesn't exist
#     os.makedirs("flow_indices", exist_ok=True)
    
#     # Create vector store
#     collection_name = f"flow_{flow_id}_knowledge"
#     # Delete existing collection if it exists
#     try:
#         chroma_client.delete_collection(collection_name)
#         print(f"Deleted existing collection {collection_name}")
#         time.sleep(1)
#     except ValueError:
#         print(f"Collection {collection_name} did not exist")

    
#     vector_store = ChromaVectorStore(
#         chroma_collection=chroma_client.get_or_create_collection(collection_name)
#     )
    
#     # Create ingestion pipeline
#     pipeline = IngestionPipeline(
#         transformations=[
#             SentenceSplitter(chunk_size=512, chunk_overlap=100),
#             Settings.embed_model
#         ],
#         vector_store=vector_store
#     )
    
#     # Process documents
#     nodes = pipeline.run(documents=documents)
    
#     # Create index
#     storage_context = StorageContext.from_defaults(vector_store=vector_store)
#     index = VectorStoreIndex(nodes, storage_context=storage_context)
    
#     # Save metadata about this index
#     index_metadata = {
#         "flow_id": flow_id,
#         "node_count": len(nodes),
#         "created_at": datetime.utcnow().isoformat(),
#         "collection_name": collection_name
#     }
    
#     with open(f"flow_indices/{flow_id}_metadata.json", "w") as f:
#         json.dump(index_metadata, f, indent=2)
    
#     return {
#         "status": "success", 
#         "flow_id": flow_id,
#         "indexed_documents": len(documents),
#         "nodes_created": len(nodes)
#     }

# @app.post("/api/index/assistant-documents")
# async def index_assistant_documents(request: dict):
#     assistant_id = request.get("assistant_id")
#     documents = request.get("documents", [])
#     print("INDEXING DOCUMENTS")
#     print(f"Assistant ID: {assistant_id}")
#     print(f"Number of documents to index: {len(documents)}")
    
#     if not assistant_id or not documents:
#         print("ERROR: assistant_id and documents are required")
#         return {"error": "assistant_id and documents are required"}
    
#     # Define a separate collection for documents
#     collection_name = f"documents_{assistant_id}_knowledge"
#     print(f"Creating/accessing collection: {collection_name}")
    
#     try:
#         collection = chroma_client.get_or_create_collection(collection_name)
#         print(f"Collection size before indexing: {collection.count()}")
#     except Exception as e:
#         print(f"Error creating/accessing collection: {str(e)}")
#         return {"error": f"Failed to create/access collection: {str(e)}"}
    
#     # Prepare LlamaIndex documents
#     llama_documents = []
#     for doc in documents:
#         doc_id = doc.get("id")
#         doc_name = doc.get("name", "Unnamed Document")
#         content = doc.get("content", "")
#         print(f"Processing document: {doc_name} (ID: {doc_id})")
#         print(f"Document content length: {len(content)} characters")
        
#         # Create a Document object with metadata
#         llama_doc = Document(
#             text=content,
#             metadata={
#                 "knowledge_type": "document",
#                 "document_id": doc_id,
#                 "document_name": doc_name,
#                 "assistant_id": assistant_id
#             }
#         )
#         llama_documents.append(llama_doc)
    
#     print(f"Total LlamaIndex documents created: {len(llama_documents)}")
    
#     # Set up vector store
#     vector_store = ChromaVectorStore(chroma_collection=collection)
#     print("Vector store setup complete")
    
#     # IMPORTANT: Avoid using extractors that require LLM in the ingestion pipeline
#     # Those cause the nested async loop issues
    
#     # Create a simpler pipeline without LLM-based extractors
#     splitter = SentenceSplitter(chunk_size=512, chunk_overlap=100)
    
#     # First, just split the documents into nodes
#     nodes = []
#     for doc in llama_documents:
#         nodes.extend(splitter.get_nodes_from_documents([doc]))
    
#     print(f"Split documents into {len(nodes)} nodes")
    
#     # Set up storage context
#     storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
#     # Create the VectorStoreIndex with the nodes
#     print("Creating VectorStoreIndex...")
#     base_index = VectorStoreIndex(nodes, storage_context=storage_context)
    
#     # Embed and store in vector store
#     print("Embedding and storing nodes...")
#     for node in nodes:
#         # Ensure node has embedding
#         if node.embedding is None:
#             embedding = Settings.embed_model.get_text_embedding(
#                 node.get_content(metadata_mode="all")
#             )
#             node.embedding = embedding
        
#         # Add to vector store directly
#         vector_store.add([node])
    
#     print(f"Successfully indexed {len(nodes)} nodes")
    
#     # Create retriever with similarity search
#     retriever = base_index.as_retriever(
#         similarity_top_k=20
#     )
    
#     # Store index and retriever in app state for later use
#     document_indexes = getattr(app.state, "document_indexes", {})
#     document_indexes[assistant_id] = {
#         "index": base_index,
#         "retriever": retriever,
#         "created_at": datetime.now().isoformat(),
#         "document_count": len(llama_documents),
#         "node_count": len(nodes)
#     }
#     app.state.document_indexes = document_indexes
    
#     print(f"Collection size after indexing: {collection.count()}")
    
#     return {
#         "status": "success",
#         "indexed_documents": len(documents),
#         "nodes_created": len(nodes),
#         "collection_name": collection_name
#     }

# @app.post("/api/shared/vector_chat")        
# async def vector_flow_chat(request: dict):
#     """
#     Process a chat message using the vector-based flow knowledge index.
#     This endpoint doesn't rely on Firestore or Gemini services.
#     """
#     import traceback  # Add missing import
    
#     try:
#         print("\n==== STARTING VECTOR CHAT PROCESSING ====")
#         message = request.get("message", "")
#         sessionId = request.get("sessionId", "")
#         flow_id = request.get("flow_id")
#         assistant_id = request.get("assistantId")
#         session_data = request.get("session_data", {})
#         previous_messages = request.get("previous_messages", [])
        
#         print(f"Message: '{message}'")
#         print(f"Session ID: {sessionId}")
#         print(f"Flow ID: {flow_id}")
#         print(f"Assistant ID: {assistant_id}")
#         print(f"Session data: {json.dumps(session_data, indent=2)}")
#         print(f"Number of previous messages: {len(previous_messages)}")
        
#         if not flow_id:
#             print("ERROR: flow_id is required")
#             return {
#                 "error": "flow_id is required",
#                 "content": "Missing required parameters"
#             }
        
#         # Create context for the query
#         current_node_id = session_data.get('currentNodeId')
#         print(f"Current node ID: {current_node_id}")
        
#         # Format previous messages for better context
#         conversation_history = ""
#         for msg in previous_messages:
#             role = msg.get("role", "unknown")
#             content = msg.get("content", "")
#             conversation_history += f"{role}: {content}\n"
        
#         print(f"Conversation history length: {len(conversation_history)} characters")
        
#         # Get the flow knowledge index
#         flow_collection_name = f"flow_{flow_id}_knowledge"
#         print(f"Accessing flow collection: {flow_collection_name}")
        
#         # Check if collection exists
#         try:
#             flow_collection = chroma_client.get_collection(flow_collection_name)
#             print(f"Flow collection found with {flow_collection.count()} entries")
#         except ValueError:
#             # Collection doesn't exist, need to create the index first
#             print(f"ERROR: Flow collection {flow_collection_name} not found")
#             return {
#                 "error": "Flow knowledge index not found. Please index the flow first.",
#                 "content": "I'm having trouble processing your request. Please try again later."
#             }
        
#         # Create vector store and index
#         flow_vector_store = ChromaVectorStore(chroma_collection=flow_collection)
#         flow_storage_context = StorageContext.from_defaults(vector_store=flow_vector_store)
#         flow_index = VectorStoreIndex.from_vector_store(flow_vector_store, storage_context=flow_storage_context)
#         print("Flow vector index created successfully")
        
#         # Document retrieval section - MADE OPTIONAL
#         document_collection_name = f"documents_{assistant_id}_knowledge"  # flow_id is assistant_id
#         print(f"Checking for document collection: {document_collection_name}")
#         document_context = ""  # Initialize empty context

#         # Check for cached index/retriever in app state first
#         document_indexes = getattr(app.state, "document_indexes", {})
#         cached_index_data = document_indexes.get(assistant_id)

#         # Try to load document context if available, but don't fail if not
#         try:
#             if cached_index_data and "retriever" in cached_index_data:
#                 print(f"Using cached document retriever for assistant {assistant_id}")
#                 document_retriever = cached_index_data["retriever"]
                
#                 # Get initial candidates from vector retriever
#                 print(f"Retrieving documents for query: '{message}'")
#                 retrieved_nodes = document_retriever.retrieve(message)
                
#                 # Apply BM25 reranking if we have enough nodes
#                 try:
#                     from llama_index.core.retrievers import BM25Retriever
                    
#                     # Get just the node objects (without scores)
#                     node_objs = [n.node for n in retrieved_nodes]
                    
#                     if len(node_objs) > 1:
#                         print(f"Applying BM25 reranking to {len(node_objs)} nodes")
#                         bm25_retriever = BM25Retriever.from_defaults(
#                             nodes=node_objs, 
#                             similarity_top_k=min(5, len(node_objs))
#                         )
                        
#                         # Get reranked results
#                         reranked_nodes = bm25_retriever.retrieve(message)
                        
#                         # Use these for generating context
#                         if reranked_nodes:
#                             document_text = "\n\n".join([n.node.get_content() for n in reranked_nodes])
#                             document_context = f"Relevant Document Content:\n{document_text}"
#                     else:
#                         # Not enough nodes for reranking, use as is
#                         document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#                         document_context = f"Relevant Document Content:\n{document_text}"
                    
#                     print(f"Document retrieval complete, found content with {len(document_context)} characters")
#                 except Exception as e:
#                     print(f"Error in BM25 reranking: {str(e)}, using vector results")
#                     document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#                     document_context = f"Relevant Document Content:\n{document_text}"
            
#             # If no cached index, try the original approach
#             elif document_indexes.get(assistant_id) is None:
#                 try:
#                     document_collection = chroma_client.get_collection(document_collection_name)
#                     document_count = document_collection.count()
#                     print(f"Document collection found with {document_count} entries")
                    
#                     if document_count > 0:
#                         print("Creating document vector store and index on the fly")
#                         document_vector_store = ChromaVectorStore(chroma_collection=document_collection)
#                         document_index = VectorStoreIndex.from_vector_store(document_vector_store)
                        
#                         # Create a better retriever that we'll cache for next time
#                         document_retriever = document_index.as_retriever(similarity_top_k=20)
                        
#                         # Cache for future use
#                         document_indexes[assistant_id] = {
#                             "index": document_index,
#                             "retriever": document_retriever,
#                             "created_at": datetime.now().isoformat()
#                         }
#                         app.state.document_indexes = document_indexes
                        
#                         # Query using standard approach for now
#                         print(f"Querying document index for: '{message}'")
#                         document_query_engine = document_index.as_query_engine(similarity_top_k=20)
#                         document_response = document_query_engine.query(message)
#                         document_context = f"Relevant Document Content:\n{document_response.response}"
#                         print(f"Document query returned content")
#                         print("Document context summary: " + document_context[:100] + "..." if len(document_context) > 100 else document_context)
#                     else:
#                         print("Document collection exists but is empty")
#                 except ValueError as e:
#                     print(f"Document collection {document_collection_name} not found; proceeding with flow only: {str(e)}")
#                     # Save an empty entry to avoid retrying each time
#                     document_indexes[assistant_id] = {
#                         "index": None,
#                         "retriever": None,
#                         "created_at": datetime.now().isoformat(),
#                         "error": str(e)
#                     }
#                     app.state.document_indexes = document_indexes
#         except Exception as doc_error:
#             # If anything goes wrong with document retrieval, log it but continue
#             print(f"ERROR in document retrieval (non-critical): {str(doc_error)}")
#             print("Continuing without document context")
        
#         # Define the context text based on whether document context is available
#         document_context_section = ""
#         if document_context:
#             document_context_section = f"""
# Relevant Document Content:
# {document_context}

# You are a helpful assistant tasked with providing accurate, specific, and context-aware responses. Follow these steps:
# 1. Identify the user's intent from the message and conversation history.
# 2. **IMPORTANT**: Scan the Relevant Document Content for any URLs, phone numbers, email addresses, or other specific resources (e.g., websites, programs, contact information).
# 3. **CRITICAL REQUIREMENT**: If ANY resources like URLs, phone numbers, or contact information are found in the document content, you MUST include them verbatim in your response regardless of whether the user explicitly requested them.
# 4. Generate a natural, conversational response that directly addresses the user's query, incorporating document content as needed.
# 5. Maintain continuity with the conversation history to stay focused on the user's current intent.
# 6. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION, but prioritize document content for specific details.
# 7. Do not repeat the node's INSTRUCTION verbatim; use it as a guide to craft a friendly, relevant response.
# 8. If no relevant document content is found, provide a helpful response based on the flow logic or general knowledge, and ask for clarification if needed.
# 9. Before finalizing your response, double-check that you've included all resource links, phone numbers, and contact methods from the document context.
# """
#         else:
#             # Simpler context when no documents are available
#             document_context_section = """
# You are a helpful assistant tasked with providing accurate and context-aware responses. Follow these steps:
# 1. Identify the user's intent from the message and conversation history.
# 2. Generate a natural, conversational response that directly addresses the user's query.
# 3. Maintain continuity with the conversation history to stay focused on the user's current intent.
# 4. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION.
# 5. Do not repeat the node's INSTRUCTION verbatim; use it as a guide to craft a friendly, relevant response.
# """
        
#         context_text = f"""
# The user message is: "{message}"

# The current node ID is: {current_node_id or "None - this is the first message"}

# IMPORTANT: If this is the first message after survey questions (userMessageCount == surveyQuestions.length), 
# you MUST transition to the designated starting node which has nodeType='starting', not to node_7.

# Previous conversation:
# {conversation_history}

# The session data is:
# {json.dumps(session_data, indent=2)}

# {document_context_section}

# Return your response as a JSON object with the following structure:
# {{
#     "content": "The response to send to the user, including specific document content where applicable",
#     "next_node_id": "ID of the next node to process",
#     "state_updates": {{
#         "key": "value"
#     }}
# }}
# """
        
#         full_context = context_text
#         print(f"Full context length: {len(full_context)} characters")
        
#         # Create query engine
#         print("Creating flow query engine")
#         query_engine = flow_index.as_query_engine(
#             response_mode="compact",
#             similarity_top_k=7,  # Retrieve more context for complete instructions
#             llm=Settings.llm  # Use the specified LLM
#         )
        
#         # Query the index
#         print("Querying flow index with full context")
#         response = query_engine.query(full_context)
#         print("Query complete, processing response")
        
#         # Process the response
#         try:
#             # Parse the response text as JSON
#             response_text = response.response
#             print(f"Raw response length: {len(response_text)} characters")
            
#             # Clean up the response if it contains markdown code blocks
#             if "```json" in response_text:
#                 print("Parsing JSON from markdown code block with ```json")
#                 response_text = response_text.split("```json")[1].split("```")[0].strip()
#             elif "```" in response_text:
#                 print("Parsing JSON from markdown code block")
#                 response_text = response_text.split("```")[1].split("```")[0].strip()
            
#             print(f"Cleaned response: {response_text[:100]}..." if len(response_text) > 100 else response_text)
#             response_data = json.loads(response_text)
#             print("Successfully parsed JSON response")
            
#             # Extract fields
#             ai_response = response_data.get("content", "I'm having trouble processing your request.")
#             next_node_id = response_data.get("next_node_id")
#             state_updates = response_data.get("state_updates", {})
            
#             print(f"AI response length: {len(ai_response)} characters")
#             print(f"Next node ID: {next_node_id}")
#             print(f"State updates: {json.dumps(state_updates, indent=2)}")
#             print("==== VECTOR CHAT PROCESSING COMPLETE ====\n")
            
#             # Return the complete response
#             return {
#                 "content": ai_response,
#                 "next_node_id": next_node_id,
#                 "state_updates": state_updates
#             }
            
#         except Exception as e:
#             print(f"ERROR processing vector response: {str(e)}")
#             print(f"Response text that failed to parse: {response_text[:200]}...")
            
#             # Fallback to direct LLM response
#             print("Using fallback LLM response")
#             fallback_prompt = f"""
#             You are a helpful assistant. The user has sent the following message:
            
#             "{message}"
            
#             Previous conversation:
#             {conversation_history}
            
#             Please provide a helpful response.
#             """
            
#             fallback_response = Settings.llm.complete(fallback_prompt)
#             print(f"Fallback response generated, length: {len(fallback_response.text)} characters")
#             print("==== VECTOR CHAT PROCESSING COMPLETE (FALLBACK) ====\n")
            
#             return {
#                 "content": fallback_response.text,
#                 "error": f"Vector processing failed: {str(e)}",
#                 "fallback": True
#             }
            
#     except Exception as e:
#         print(f"CRITICAL ERROR in vector_chat: {str(e)}")
#         traceback_str = traceback.format_exc()
#         print(f"Traceback: {traceback_str}")
#         print("==== VECTOR CHAT PROCESSING FAILED ====\n")
#         return {
#             "error": f"Failed to process message: {str(e)}",
#             "content": "I'm having trouble processing your request. Please try again later."
#         }


## GCS
app.state.flow_indices = {}
app.state.document_indexes = {}

class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    detected_language: str

class TranslationRequest(BaseModel):
    text: str
    target_language: str = "en"  # Make target_language optional with default value

@app.post("/api/translate-to-language")
async def translate_to_language(request: TranslationRequest):
    try:
        text = request.text
        target_language = request.target_language
        if not text or len(text.strip()) < 1 or target_language == 'en':
            return {"translated_text": text}
        translation_prompt = f"""
        Translate the following English text to {target_language}.
        
        IMPORTANT: Return ONLY the translated text with no explanations, options, or additional content.
        
        Text to translate: "{text}"
        
        Translation:
        """
        translation_response = Settings.llm.complete(translation_prompt)
        translated_text = translation_response.text.strip()
        return {"translated_text": translated_text}
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return {"translated_text": text}
    
@app.post("/api/translate-to-english")
async def translate_to_english(request: TranslationRequest):
    """
    Simple endpoint to translate any text to English.
    Returns original text, translated text, and detected language.
    """
    try:
        text = request.text
        
        # Skip empty text
        if not text or len(text.strip()) < 1:
            return {
                "original_text": text,
                "translated_text": text,
                "detected_language": "en"
            }
        
        # Detect language
        language_prompt = f"""
        Detect the language of the following text and respond with only the ISO language code:
        If the text is a proper noun (e.g., a name), a date (e.g., 29/04/1999), or ambiguous, assume it is English ('en').
        Text: "{text}"
        
        Language code:
        """
        language_response = Settings.llm.complete(language_prompt)
        detected_language = language_response.text.strip().lower()
        
        # Normalize common responses
        if detected_language in ['hindi', 'hin'] or detected_language.startswith('hi'):
            detected_language = 'hi'
        elif detected_language in ['english', 'eng'] or detected_language.startswith('en'):
            detected_language = 'en'
        
        # If already English, return as is
        if detected_language == 'en':
            return {
                "original_text": text,
                "translated_text": text,
                "detected_language": "en"
            }
        
        # Translate to English
        translation_prompt = f"""
        Translate the following text to English:
        
        Return ONLY the translated text with no explanations, options, or additional content.
        NOTE : For Date like for example : 29/04/1999 or any other Dates consider them english"
        
        Text: "{text}"
        
        English translation:
        """
        translation_response = Settings.llm.complete(translation_prompt)
        translated_text = translation_response.text.strip()
        
        return {
            "original_text": text,
            "translated_text": translated_text,
            "detected_language": detected_language
        }
        
    except Exception as e:
        print(f"Translation error: {str(e)}")
        # In case of error, return original text
        return {
            "original_text": text,
            "translated_text": text,
            "detected_language": "unknown"
        }
    
@app.post("/api/index/flow-knowledge")
async def create_flow_knowledge_index(flow_data: dict):
    """
    Convert an entire flow structure into a knowledge base for LlamaIndex.
    """
    flow_id = flow_data.get("id", str(uuid.uuid4()))
    nodes = flow_data.get("nodes", [])
    edges = flow_data.get("edges", [])
    
    documents = []
    
    # Process all nodes
    for node in nodes:
        node_id = node.get("id")
        node_type = node.get("type")
        node_data = node.get("data", {})
        
        # Create base document text
        doc_text = f"NODE ID: {node_id}\nNODE TYPE: {node_type}\n\n"
        
        # Add node specific processing instructions
        if node_type == "dialogueNode":
            doc_text += f"INSTRUCTION: When the user is at this dialogue node, display the message '{node_data.get('message', '')}' to the user.\n\n"
            doc_text += "FUNCTIONS:\n"
            for func in node_data.get("functions", []):
                func_id = func.get("id")
                func_content = func.get("content", "")
                func_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"function-{node_id}-{func_id}"]
                if func_edges:
                    target_node_id = func_edges[0].get("target")
                    doc_text += f"- If user response matches or replied with or user intent matches with '{func_content}', proceed to node {target_node_id}\n"
        
        elif node_type == "scriptNode":
            doc_text += f"INSTRUCTION: When the user is at this script node, display the message '{node_data.get('message', '')}' to the user.\n\n"
            doc_text += "FUNCTIONS:\n"
            for func in node_data.get("functions", []):
                func_id = func.get("id")
                func_content = func.get("content", "")
                func_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"function-{node_id}-{func_id}"]
                if func_edges:
                    target_node_id = func_edges[0].get("target")
                    
        elif node_type == "notificationNode":
            doc_text += f"INSTRUCTION: {node_data.get('message', 'Send a notification with the following details:')}\n"
            doc_text += f"- Notification Type: {node_data.get('messageType', 'whatsapp')}\n"
            doc_text += f"- Title: {node_data.get('title', '')}\n"
            doc_text += f"- Schedule: {node_data.get('type', 'immediate')}\n"
            if node_data.get('type') == 'scheduled' and node_data.get('scheduledFor'):
                doc_text += f"- Scheduled For: {node_data.get('scheduledFor')}\n"
            if node_data.get('assistantId'):
                doc_text += f"- Assistant ID: {node_data.get('assistantId')}\n"
            
            # Add survey questions if they exist
            if node_data.get('surveyQuestions') and len(node_data.get('surveyQuestions', [])) > 0:
                doc_text += "- Survey Questions:\n"
                for i, question in enumerate(node_data['surveyQuestions'], 1):
                    doc_text += f"  {i}. Question: {question.get('text', '')}\n"
                    doc_text += f"     Type: {question.get('type', 'text')}\n"
                    doc_text += f"     ID: {question.get('id', '')}\n"
                    if question.get('options') and len(question['options']) > 0:
                        options = ", ".join([opt.get('text', '') for opt in question['options']])
                        doc_text += f"     Options: {options}\n"
            
            doc_text += "\n"
            doc_text += f"- After sending notification, proceed to node {target_node_id}\n"
            
            # Add node data section for easier parsing
            doc_text += "\nNODE DATA: " + json.dumps({
                "message": node_data.get('message', ''),
                "messageType": node_data.get('messageType', 'whatsapp'),
                "title": node_data.get('title', ''),
                "scheduleType": node_data.get('type', 'immediate'),
                "scheduledFor": node_data.get('scheduledFor', ''),
                "assistantId": node_data.get('assistantId', ''),
                "surveyQuestions": [{
                    "id": q.get('id', ''),
                    "text": q.get('text', ''),
                    "type": q.get('type', 'text'),
                    "options": q.get('options', [])
                } for q in node_data.get('surveyQuestions', [])]
            })
        
        elif node_type == "fieldSetterNode":
            doc_text += f"INSTRUCTION: When the user is at this field setter node, request the value for field '{node_data.get('fieldName', '')}' using the message: '{node_data.get('message', '')}'.\n\n"
            setter_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"{node_id}-right"]
            if setter_edges:
                target_node_id = setter_edges[0].get("target")
                doc_text += f"After capturing the field value, proceed to node {target_node_id}\n"
        
        elif node_type == "responseNode":
            doc_text += f"INSTRUCTION: When the user is at this response node, display the message '{node_data.get('message', '')}' and then use the LLM to generate a conversational response.\n\n"
            doc_text += "TRIGGERS:\n"
            for trigger in node_data.get("triggers", []):
                trigger_id = trigger.get("id")
                trigger_content = trigger.get("content", "")
                trigger_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"trigger-{node_id}-{trigger_id}"]
                if trigger_edges:
                    target_node_id = trigger_edges[0].get("target")
                    doc_text += f"- If user's response matches '{trigger_content}', proceed to node {target_node_id}\n"
        
        elif node_type == "callTransferNode":
            doc_text += f"INSTRUCTION: When the user is at this call transfer node, display the message '{node_data.get('message', '')}' and create a notification for human takeover.\n\n"
            transfer_edges = [e for e in edges if e.get("source") == node_id]
            if transfer_edges:
                target_node_id = transfer_edges[0].get("target")
                doc_text += f"After notifying about the transfer, proceed to node {target_node_id}\n"
        
        elif node_type == "surveyNode":
            doc_text += f"INSTRUCTION: When the user is at this survey node, display the message '{node_data.get('message', '')}' and present the survey titled '{node_data.get('surveyData', {}).get('title', '')}' with the following details:\n"
            survey_data = node_data.get("surveyData", {})
            doc_text += f"  - Survey ID: {survey_data.get('id', '')}\n"
            doc_text += f"  - Description: {survey_data.get('description', '')}\n"
            doc_text += f"  - Questions:\n"
            for question in survey_data.get("questions", []):
                doc_text += f"    - {question.get('text', '')} (Type: {question.get('type', '')})\n"
                for option in question.get("options", []):
                    doc_text += f"      - Option: {option}\n"
            doc_text += "\nTRIGGERS:\n"
            for trigger in node_data.get("triggers", []):
                trigger_id = trigger.get("id")
                trigger_content = trigger.get("content", "")
                trigger_edges = [e for e in edges if e.get("source") == node_id and e.get("sourceHandle") == f"trigger-{node_id}-{trigger_id}"]
                if trigger_edges:
                    target_node_id = trigger_edges[0].get("target")
                    doc_text += f"- If survey outcome is '{trigger_content}', proceed to node {target_node_id}\n"
        
        # Create document
        documents.append(Document(
            text=doc_text,
            metadata={
                "node_id": node_id,
                "node_type": node_type,
                "flow_id": flow_id
            }
        ))
    # Add global flow processing instructions
    starting_node = next((node for node in nodes if node.get("data", {}).get("nodeType") == "starting" or 
                    "nodeType" in node and node["nodeType"] == "starting"), None)
    starting_node_id = starting_node["id"] if starting_node else None
    print('starting node', starting_node)
    print(f"Found starting node with ID: {starting_node_id}")

    flow_instructions = f"""
    FLOW ID: {flow_id}
    
    GENERAL PROCESSING INSTRUCTIONS:
    
    1. STARTING: use {starting_node_id} or When a new conversation begins, find the node with nodeType='starting' and process it first.
    
    2. DIALOGUENODE PROCESSING:
       - Display the node's message to the user
       - Wait for user input
       - Match user input against the node's functions
       - If a match is found (NOTE: if user input matches  or intent of input matches with particular function for example if function says "if user replied with no" and user replied with i don't know then both are same thing), -> transition to the corresponding target node 
       - If no match is found, generate a response using the LLM
    
    3. SCRIPTNODE PROCESSING:
       - Display the node's message to the user
       - If the node has functions, check if any should be activated
       - If a function is activated, transition to its target node
       - Otherwise, move to the next connected node if one exists
    
    4. FIELDSETTERNODE PROCESSING:
       - Request the specified field value from the user
       - Wait for user input
       - Validate the input as a valid value for the field
       - If valid, store the value and transition to the next node
       - If invalid, ask the user again
    
    5. RESPONSENODE PROCESSING:
       - Display the node's message to the user
       - Wait for user input
       - Generate a response using the LLM
       - Check if the user's next message matches any triggers
       - If a trigger matches, transition to its target node
    
    6. CALLTRANSFERNODE PROCESSING:
       - Display the node's message to the user
       - Create a notification for human transfer
       - Transition to the next node if one exists
    
    7. SESSION STATE:
       - Always track which node the user is currently at
       - Store field values collected from FieldSetterNodes
       - Mark whether you're awaiting a response from the user
    
    8. OUT-OF-FLOW HANDLING:
       - If the user asks a question unrelated to the current node:
         a. If it's a simple question, answer it directly
         b. After answering, return to the current node's flow
    """
    
    # Add flow processing document
    documents.append(Document(
        text=flow_instructions,
        metadata={
            "flow_id": flow_id,
            "type": "flow_instructions"
        }
    ))
    
    # Add node connections document for reference
    connections_text = "NODE CONNECTIONS:\n\n"
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        source_handle = edge.get("sourceHandle")
        connections_text += f"From node {source} to node {target}"
        if source_handle:
            connections_text += f" via {source_handle}"
        connections_text += "\n"
    
    documents.append(Document(
        text=connections_text,
        metadata={
            "flow_id": flow_id,
            "type": "connections"
        }
    ))
    
    # Create the index directory if it doesn't exist
    os.makedirs("flow_indices", exist_ok=True)
    
    collection_name = f"flow_{flow_id}_knowledge"
    
    # Ensure collection is fully deleted
    try:
        chroma_client.delete_collection(collection_name)
        print(f"Deleted existing collection {collection_name}")
        # Wait longer to ensure deletion propagates
        time.sleep(2)
    except ValueError:
        print(f"Collection {collection_name} did not exist")
    
    try:
        chroma_client.get_collection(collection_name)
        print(f"[INDEX] ERROR: Collection {collection_name} still exists after deletion")
        raise Exception("Chroma collection deletion failed")
    except chromadb.errors.InvalidCollectionException:
        print(f"[INDEX] Confirmed collection {collection_name} is deleted")

    # Create a new collection explicitly
    chroma_collection = chroma_client.create_collection(collection_name)
    print(f"Created new collection {collection_name}")
    
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    
    # Create ingestion pipeline
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=512, chunk_overlap=100),
            Settings.embed_model
        ],
        vector_store=vector_store
    )
    
    # Process documents
    print(f"Processing {len(documents)} documents")
    nodes = pipeline.run(documents=documents)
    print(f"Created {len(nodes)} nodes")
    
    # Verify collection contents
    collection_count = chroma_collection.count()
    print(f"Chroma collection {collection_name} now has {collection_count} embeddings")
    
    # Create index
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(nodes, storage_context=storage_context)
    
    # Persist locally
    persist_dir = f"flow_indices/{flow_id}"
    os.makedirs(persist_dir, exist_ok=True)
    storage_context.persist(persist_dir=persist_dir)
    
    # Upload to GCS
    bucket = storage_client.bucket(BUCKET_NAME)
    for root, _, files in os.walk(persist_dir):
        for file in files:
            local_path = os.path.join(root, file)
            gcs_path = f"flow_indices/{flow_id}/{file}"
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(local_path)
            print(f"Uploaded {local_path} to GCS: {gcs_path}")
    
    # Clean up local directory
    shutil.rmtree(persist_dir)
    
    # Save metadata
    index_metadata = {
        "flow_id": flow_id,
        "node_count": len(nodes),
        "created_at": datetime.utcnow().isoformat(),
        "collection_name": collection_name,
        "gcs_path": f"flow_indices/{flow_id}",
        "embedding_count": collection_count
    }
    meta_file = f"flow_indices/{flow_id}_meta.pkl"
    with open(meta_file, "wb") as f:
        pickle.dump(index_metadata, f)
    gcs_meta_path = f"flow_metadata/{flow_id}_meta.pkl"
    blob = bucket.blob(gcs_meta_path)
    blob.upload_from_filename(meta_file)
    os.remove(meta_file)
    
    # Cache in memory
    app.state.flow_indices[flow_id] = index
    
    return {
        "status": "success",
        "flow_id": flow_id,
        "indexed_documents": len(documents),
        "nodes_created": len(nodes),
        "embeddings_in_collection": collection_count
    }

@app.post("/api/classify-intent")
async def classify_intent(request: dict):
    """
    Classify user intent using LLM and match with available assistant categories
    """
    try:
        message = request.get("message", "")
        organization_id = request.get("organization_id")
        current_assistant_id = request.get("current_assistant_id")
        available_categories = request.get("available_categories", ["default"])
        
        print(f"[INTENT CLASSIFICATION] Message: '{message}'")
        print(f"[INTENT CLASSIFICATION] Organization: {organization_id}")
        print(f"[INTENT CLASSIFICATION] Available categories: {available_categories}")
        
        if not message or not organization_id:
            return {
                "error": "message and organization_id are required",
                "selected_category": "default",
                "assistant_id": current_assistant_id,
                "should_switch": False
            }
        
        # Ensure default is always available
        if 'default' not in available_categories:
            available_categories.append('default')
        
        # If only default category available, no need to classify
        if len(available_categories) == 1 and available_categories[0] == 'default':
            print("[INTENT CLASSIFICATION] Only default category available, skipping classification")
            return {
                "selected_category": "default",
                "assistant_id": current_assistant_id,
                "should_switch": False,
                "confidence": "n/a"
            }
        
        # Construct the prompt for the LLM to route intent (using actual available categories)
        routing_prompt = f"""
The user has just started a new conversation with the message: "{message}".

You need to determine the primary intent of the user's message and select the single most appropriate chat category from the following list of available options: {", ".join(available_categories)}.

Guidelines:
- Analyze the user's message for specific medical or health-related intents
- Match the intent to one of the available categories for this organization
- If the user's message is a general greeting, unclear question, or does not clearly fit any specific category, you MUST select 'default'
- Do NOT select any category that is not in the provided list: {", ".join(available_categories)}
- Be conservative - only select specialized categories if the intent is clear

Available categories and their purposes:
{chr(10).join([f"- {cat}: {'General assistance and routing' if cat == 'default' else f'Specialized for {cat}-related queries'}" for cat in available_categories])}

Your response should be a JSON object containing ONLY the selected category.

```json
{{
    "selected_category": "category_name"
}}
```

Examples:
User message: "Hi there, I'm feeling sick and have a fever."
Available categories: ['default', 'symptoms', 'pregnancy']
Response: {{"selected_category": "symptoms"}}

User message: "Hello!"  
Available categories: ['default', 'symptoms', 'pregnancy']
Response: {{"selected_category": "default"}}

User message: "I think I might be pregnant."
Available categories: ['default', 'symptoms', 'pregnancy']
Response: {{"selected_category": "pregnancy"}}

User message: "I need help with my symptoms"
Available categories: ['default', 'symptoms']
Response: {{"selected_category": "symptoms"}}

User message: "I have questions about my wellness checkup"
Available categories: ['default', 'wellness', 'symptoms']
Response: {{"selected_category": "wellness"}}

Current available categories for this organization: {", ".join(available_categories)}
User message: "{message}"
"""

        try:
            # Use the same LLM approach as vector_chat
            routing_response_text = Settings.llm.complete(routing_prompt).text
            
            # Parse JSON response (same approach as vector_chat)
            if "```json" in routing_response_text:
                routing_response_text = routing_response_text.split("```json")[1].split("```")[0].strip()
            
            routing_data = json.loads(routing_response_text)
            selected_category = routing_data.get("selected_category", "default").lower().strip()
            
            # Normalize and validate category
            if selected_category not in [cat.lower() for cat in available_categories]:
                print(f"[INTENT] LLM selected '{selected_category}' which is not valid. Using 'default'.")
                selected_category = 'default'
            
            print(f"[INTENT] Selected category: {selected_category}")
            
            return {
                "selected_category": selected_category,
                "assistant_id": None,  # Node.js will handle assistant lookup
                "should_switch": selected_category != 'default',
                "confidence": "high" if selected_category != 'default' else "low"
            }
            
        except json.JSONDecodeError as e:
            print(f"[INTENT] JSON parsing error: {str(e)}")
            print(f"[INTENT] Raw response: {routing_response_text}")
            return {
                "selected_category": "default",
                "assistant_id": current_assistant_id,
                "should_switch": False,
                "error": "Failed to parse LLM response"
            }
            
    except Exception as e:
        print(f"[INTENT] Error in intent classification: {str(e)}")
        return {
            "selected_category": "default", 
            "assistant_id": current_assistant_id,
            "should_switch": False,
            "error": str(e)
        }


@app.post("/api/index/assistant-documents")
async def index_assistant_documents(request: dict):
    assistant_id = request.get("assistant_id")
    documents = request.get("documents", [])
    print("INDEXING DOCUMENTS")
    print(f"Assistant ID: {assistant_id}")
    print(f"Number of documents to index: {len(documents)}")
    
    if not assistant_id or not documents:
        print("ERROR: assistant_id and documents are required")
        return {"error": "assistant_id and documents are required"}
    
    # Define a separate collection for documents
    collection_name = f"documents_{assistant_id}_knowledge"
    print(f"Creating/accessing collection: {collection_name}")
    
    try:
        collection = chroma_client.get_or_create_collection(collection_name)
        print(f"Collection size before indexing: {collection.count()}")
    except Exception as e:
        print(f"Error creating/accessing collection: {str(e)}")
        return {"error": f"Failed to create/access collection: {str(e)}"}
    
    # Prepare LlamaIndex documents
    llama_documents = []
    for doc in documents:
        doc_id = doc.get("id")
        doc_name = doc.get("name", "Unnamed Document")
        content = doc.get("content", "")
        print(f"Processing document: {doc_name} (ID: {doc_id})")
        print(f"Document content length: {len(content)} characters")
        
        # Create a Document object with metadata
        llama_doc = Document(
            text=content,
            metadata={
                "knowledge_type": "document",
                "document_id": doc_id,
                "document_name": doc_name,
                "assistant_id": assistant_id
            }
        )
        llama_documents.append(llama_doc)
    
    print(f"Total LlamaIndex documents created: {len(llama_documents)}")
    
    # Set up vector store
    vector_store = ChromaVectorStore(chroma_collection=collection)
    print("Vector store setup complete")

    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=100)
    
    # First, just split the documents into nodes
    nodes = []
    for doc in llama_documents:
        nodes.extend(splitter.get_nodes_from_documents([doc]))
    
    print(f"Split documents into {len(nodes)} nodes")
    
    # Set up storage context
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # Create the VectorStoreIndex with the nodes
    print("Creating VectorStoreIndex...")
    base_index = VectorStoreIndex(nodes, storage_context=storage_context)
    
    # Embed and store in vector store
    print("Embedding and storing nodes...")
    for node in nodes:
        # Ensure node has embedding
        if node.embedding is None:
            embedding = Settings.embed_model.get_text_embedding(
                node.get_content(metadata_mode="all")
            )
            node.embedding = embedding
        
        # Add to vector store directly
        vector_store.add([node])
    
    print(f"Successfully indexed {len(nodes)} nodes")
    # Persist locally
    persist_dir = f"document_indices/{assistant_id}"
    os.makedirs(persist_dir, exist_ok=True)
    storage_context.persist(persist_dir=persist_dir)
    # Create retriever with similarity search
    retriever = base_index.as_retriever(
        similarity_top_k=20
    )
    
    # Upload to GCS
    bucket = storage_client.bucket(BUCKET_NAME)
    for root, _, files in os.walk(persist_dir):
        for file in files:
            local_path = os.path.join(root, file)
            gcs_path = f"document_indices/{assistant_id}/{file}"
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(local_path)
            print(f"Uploaded {local_path} to GCS: {gcs_path}")

    # Clean up local directory
    shutil.rmtree(persist_dir)

    # Save metadata
    index_metadata = {
        "assistant_id": assistant_id,
        "document_count": len(llama_documents),
        "node_count": len(nodes),
        "created_at": datetime.now().isoformat(),
        "collection_name": collection_name,
        "gcs_path": f"document_indices/{assistant_id}"
    }
    meta_file = f"document_indices/{assistant_id}_meta.pkl"
    with open(meta_file, "wb") as f:
        pickle.dump(index_metadata, f)
    gcs_meta_path = f"document_metadata/{assistant_id}_meta.pkl"
    blob = bucket.blob(gcs_meta_path)
    blob.upload_from_filename(meta_file)
    os.remove(meta_file)

    # Create retriever and cache
    retriever = base_index.as_retriever(similarity_top_k=20)
    app.state.document_indexes[assistant_id] = {
        "index": base_index,
        "retriever": retriever,
        "created_at": datetime.now().isoformat(),
        "document_count": len(llama_documents),
        "node_count": len(nodes)
    }

    return {
        "status": "success",
        "indexed_documents": len(documents),
        "nodes_created": len(nodes),
        "collection_name": collection_name
    }


def get_starting_node(flow_index):
    try:
        retriever = flow_index.as_retriever(similarity_top_k=10)
        query_str = "GENERAL PROCESSING INSTRUCTIONS"  # Target the flow_instructions document
        print(f"Querying for starting node with: '{query_str}'")
        node_docs = retriever.retrieve(query_str)
        print(f"Retrieved {len(node_docs)} documents for starting node query")
        
        # First, look for the flow_instructions document to get starting_node_id
        starting_node_id = None
        for doc in node_docs:
            if doc.metadata.get("type") == "flow_instructions":
                content = doc.get_content()
                print(f"Found flow_instructions: {content[:200]}...")
                import re
                match = re.search(r"1\. STARTING: use (\w+)", content)
                if match:
                    starting_node_id = match.group(1)
                    print(f"Found starting node ID '{starting_node_id}' in flow instructions")
                    break
        
        if starting_node_id and starting_node_id != "None":
            # Re-query for the specific node using its NODE ID
            specific_docs = retriever.retrieve(f"NODE ID: {starting_node_id}")
            for specific_doc in specific_docs:
                print(f"Checking specific document: {specific_doc.get_content()[:100]}...")
                print(f"Specific document metadata: {specific_doc.metadata}")
                if specific_doc.metadata.get("node_id") == starting_node_id:
                    print(f"Verified starting node with ID: {starting_node_id}")
                    return starting_node_id, specific_doc.get_content()
        
        print("No starting node found")
        return None, ""
    except Exception as e:
        print(f"Error finding starting node: {str(e)}")
        return None, ""

# @app.post("/api/shared/vector_chat")
# async def vector_flow_chat(request: dict):
#     """
#     Process a chat message using the vector-based flow knowledge index.
#     This endpoint doesn't rely on Firestore or Gemini services.
#     """
#     import traceback
#     import json
#     from datetime import datetime
#     from llama_index.core import VectorStoreIndex, StorageContext
#     from llama_index.vector_stores.chroma import ChromaVectorStore
#     from llama_index.retrievers.bm25 import BM25Retriever
#     from langdetect import detect, DetectorFactory
#     from langdetect.lang_detect_exception import LangDetectException

#     eastern = pytz.timezone('America/New_York')
#     current_time = datetime.now(eastern)
#     current_date = current_time.date().strftime('%m/%d/%Y')
#     print(f"[CURRENT DATE] {current_date}")
#     try:
#         print("\n==== STARTING VECTOR CHAT PROCESSING ====")
#         message = request.get("message", "")
#         sessionId = request.get("sessionId", "")
#         flow_id = request.get("flow_id")
#         assistant_id = request.get("assistantId")
#         session_data = request.get("session_data", {})
#         previous_messages = request.get("previous_messages", [])
#         patientId = request.get("patientId", "")
#         patient_history = request.get("patient_history", "")  # New: Extract patient history
#         print(f"[PATIENT HISTORY] {patient_history}")
#         onboarding_status_from_session = session_data.get("onboardingStatus") # Use .get() for safety
#         print(f"[ONBOARDING STATUS], {onboarding_status_from_session}")
#         Onboarding = None
#         print(f"Message: '{message}'")
#         print(f"Session ID: {sessionId}")
#         print(f"Flow ID: {flow_id}")
#         print(f"Assistant ID: {assistant_id}")
#         print(f"Session data: {json.dumps(session_data, indent=2)}")
#         print(f"Number of previous messages: {len(previous_messages)}")
#         print(f"previous messages",previous_messages )
#         # Add after retrieving session data
#         is_new_session = not session_data.get('currentNodeId') and len(previous_messages) <= 6
#         print(f"Is likely new session: {is_new_session}")
#         print(f"session data {session_data}")
#         current_node_id = session_data.get('currentNodeId')
#         current_node_doc = ""
#         print(f"Current node ID: {current_node_id}")
#         survey_questions_length = session_data.get('survey_questions_length', 0)
#         user_message_count = sum(1 for msg in previous_messages if msg.get("role") == "user")
#         is_post_survey_start = (current_node_id is None and 
#                             user_message_count >= survey_questions_length and 
#                             survey_questions_length > 0)
#         print(f"[CHAT] Survey questions length: {survey_questions_length}")
#         print(f"[CHAT] User message count: {user_message_count}")
#         print(f"[CHAT] Is post-survey start: {is_post_survey_start}")

        
        
#         # Try to get starting node info from app state if available
#         if hasattr(app.state, 'starting_node_ids') and flow_id in getattr(app.state, 'starting_node_ids', {}):
#             print(f"Cached starting node for flow {flow_id}: {app.state.starting_node_ids[flow_id]}")
#         else:
#             print("No cached starting node info available")
            
#         if not flow_id:
#             print("ERROR: flow_id is required")
#             return {
#                 "error": "flow_id is required",
#                 "content": "Missing required parameters"
#             }
        
#         # Load flow index
#         if flow_id not in app.state.flow_indices:
#             bucket = storage_client.bucket(BUCKET_NAME)
#             meta_file = f"temp_flow_{flow_id}_meta.pkl"
#             blob = bucket.blob(f"flow_metadata/{flow_id}_meta.pkl")
#             try:
#                 blob.download_to_filename(meta_file)
#                 with open(meta_file, "rb") as f:
#                     metadata = pickle.load(f)
#                 os.remove(meta_file)
#             except Exception as e:
#                 print(f"Failed to load flow index metadata from GCS: {str(e)}")
#                 return {
#                     "error": "Flow knowledge index not found. Please index the flow first.",
#                     "content": "I'm having trouble processing your request."
#                 }

#             temp_dir = f"temp_flow_{flow_id}"
#             os.makedirs(temp_dir, exist_ok=True)
#             for blob in bucket.list_blobs(prefix=f"flow_indices/{flow_id}/"):
#                 local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
#                 blob.download_to_filename(local_path)

#             collection_name = metadata["collection_name"]
#             print("DEBUG: Entering Chroma collection block")
#             try:
#                 chroma_collection = chroma_client.get_collection(collection_name)
#                 print(f"Found existing Chroma collection {collection_name}")
#             except chromadb.errors.InvalidCollectionException:
#                 print(f"Creating new Chroma collection {collection_name}")
#                 chroma_collection = chroma_client.create_collection(collection_name)
#             vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

#             storage_context = StorageContext.from_defaults(
#                 persist_dir=temp_dir, vector_store=vector_store
#             )
#             flow_index = load_index_from_storage(storage_context)
#             app.state.flow_indices[flow_id] = flow_index
#             shutil.rmtree(temp_dir)
#         else:
#             flow_index = app.state.flow_indices[flow_id]
#             print('Flow Data', flow_index)
#             print(f"[CHAT] Using cached flow index for flow_id: {flow_id}")

        
#         patient = db.query(Patient).filter(Patient.id == patientId).first()
#         if not patient:
#             raise HTTPException(status_code=404, detail="Patient not found")
#         patient_dict = {
#             "id": patient.id,
#             "mrn": patient.mrn,
#             "first_name": patient.first_name,
#             "last_name": patient.last_name,
#             "date_of_birth": patient.date_of_birth,
#             "gender": patient.gender,

#         }
#         patient_fields = json.dumps(patient_dict, indent=2)
#         required_fields = ["first_name", "last_name", "date_of_birth"]
#         missing_fields = []
#         for field in required_fields:
#             value = getattr(patient, field, None)
#             if not value or (isinstance(value, str) and not value.strip()):
#                 missing_fields.append(field)


#         print(f"[MISSING FIELDS], {missing_fields}")
#         print(f"[PATIENT FIELDS], {patient_fields}")

#         onboarding_status_to_send = "in_progress" # Default to in_progress
#         if not missing_fields:
#                 onboarding_status_to_send = "completed"

        
#         if missing_fields: 
#             print("==== PATIENT ONBOARDING/CHAT START ====\n")
#             patient_fields_prompt = f"""

#             Current Date (MM/DD/YYYY) : {current_date}

#             Patient Profile (includes phone and organization_id):
#             {patient_fields}

#             User Message : 
#             {message}

#             You are a friendly, conversational assistant helping a patient with healthcare interactions. Your goal is to have a natural, human-like conversation. You need to:

#             1. Check the patient's profile to see if any required fields are missing, and ask for them one at a time if needed.
#             2. If the profile is complete, guide the conversation using flow instructions as a loose guide, but respond naturally to the user's message.
#             3. When the user asks specific questions about medical information, treatments, or medications, ALWAYS check the document content first and provide that information.
#             4. Maintain a warm, empathetic tone, like you're talking to a friend.

#             Instructions:
#             1. **Check Patient Profile**:
#             - Review the `Patient Profile` JSON to identify any fields (excluding `id`, `mrn`, `created_at`, `updated_at`, `organization_id`, `phone`) that are null, empty, or missing.
#             - If any fields are missing, select one to ask for in a natural way (e.g., "Hey, I don't have your first name yet, could you share it?").
#             - Validate user input based on the field type:
#                 - Text fields (e.g., names): Alphabetic characters, spaces, or hyphens only (/^[a-zA-Z\s-]+$/).
#                 - Dates (e.g., date_of_birth): Valid date, convertible to MM/DD/YYYY, not after {current_date}.
#             - If the user provides a valid value for the requested field, issue an `UPDATE_PATIENT` command with:
#                 - patient_id: {patientId}
#                 - field_name: the field (e.g., "first_name")
#                 - field_value: the validated value
#             - If the input is invalid, ask again with a friendly clarification (e.g., "Sorry, that doesn't look like a valid date. Could you try again, like 03/29/1996?").
#             - If no fields are missing, proceed to conversation flow.
#             - Use `organization_id` and `phone` from the `Patient Profile`, not from the request.
#             IMPORTANT: Only ever ask for these missing profile fields—first name, last name, date of birth, gender, and email.  
#             Do ​not​ ask for insurance, address, emergency contact, or any other fields, even if they’re empty.  


#             2. **Response Structure**:
#             Return a JSON object:
#             ```json
#             {{
#                 "content": "Your friendly response to the user",
#                 "next_node_id": "ID of the next node or current node",
#                 "state_updates": {{"key": "value"}},
#                 "database_operation": {{
#                 "operation": "UPDATE_PATIENT | CREATE_PATIENT",
#                 "parameters": {{
#                     "patient_id": "string",
#                     "field_name": "string",
#                     "field_value": "string"
#                 }}
#                 }} // Optional, only when updating/creating
#             }}
#             ```
#             Examples:
#             - Profile: {{"first_name": null, "last_name": null, "date_of_birth": null}}, Message: "hi"
#             - Response: {{"content": "Hey, nice to hear from you! I need a bit of info to get you set up. Could you share your first name?", "next_node_id": null, "state_updates": {{}}}}
#             - Profile: {{"first_name": "Shenal", "last_name": null, "date_of_birth": null}}, Message: "Jones"
#             - Response: {{"content": "Awesome, thanks for sharing, Shenal Jones! What's your date of birth, like 03/29/1996?", "next_node_id": null, "state_updates": {{}}, "database_operation": {{"operation": "UPDATE_PATIENT", "parameters": {{"patient_id": "{patientId}", "field_name": "last_name", "field_value": "Jones"}}}}}}
# """
            
#             response_text = Settings.llm.complete(patient_fields_prompt).text  # Replace with Settings.llm.complete
#             if "```json" in response_text:
#                 response_text = response_text.split("```json")[1].split("```")[0].strip()
#             response_data = json.loads(response_text)

#             content = response_data.get("content", "I'm having trouble processing your request.")
#             next_node_id = response_data.get("next_node_id")
#             state_updates = response_data.get("state_updates", {})
#             database_operation = response_data.get("database_operation")

#             operation_result = None
#             if database_operation:
#                 operation = database_operation.get("operation")
#                 parameters = database_operation.get("parameters", {})
#                 try:
#                     if operation == "UPDATE_PATIENT":
#                         patient = db.query(Patient).filter(Patient.id == patientId).first()
#                         if not patient:
#                             raise HTTPException(status_code=404, detail="Patient not found")
#                         setattr(patient, parameters["field_name"], parameters["field_value"])
#                         patient.updated_at = datetime.utcnow()
#                         db.commit()
#                         db.refresh(patient)
#                         operation_result = {
#                             "id": patient.id,
#                             "mrn": patient.mrn,
#                             "first_name": patient.first_name,
#                             "last_name": patient.last_name,
#                             "date_of_birth": patient.date_of_birth,
#                             "phone": patient.phone,
#                             "organization_id": patient.organization_id
#                         }
#                         # Update JSON file
#                         patient_path = f"patients/{patient.id}.json"
#                         os.makedirs(os.path.dirname(patient_path), exist_ok=True)
#                         with open(patient_path, "w") as f:
#                             patient_dict = {
#                                 "id": patient.id,
#                                 "mrn": patient.mrn,
#                                 "first_name": patient.first_name,
#                                 "last_name": patient.last_name,
#                                 "date_of_birth": patient.date_of_birth,
#                                 "phone": patient.phone,
#                                 "organization_id": patient.organization_id,
#                                 "created_at": patient.created_at.isoformat() if patient.created_at else None,
#                                 "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
#                             }
#                             json.dump(patient_dict, f, indent=2)
#                         content += f"\nProfile updated successfully!"
#                         missing_fields = []
#                         for field in required_fields:
#                             value = getattr(patient, field, None)
#                             if not value or (isinstance(value, str) and not value.strip()):
#                                 missing_fields.append(field)
                        
#                         # Update onboarding status based on recalculated missing fields
#                         if not missing_fields:
#                             onboarding_status_to_send = "completed"
#                             print(f"🎉 ONBOARDING COMPLETE! All required fields now filled.")
#                         else:
#                             print(f"Still missing fields after UPDATE: {missing_fields}")
#                             # onboarding_status_to_send stays "in_progress"
#                         starting_node_id, starting_node_doc = get_starting_node(flow_index)
#                         print(f"[STARTING NODE, FROM UPDATE] {starting_node_id, starting_node_doc}")
#                         if starting_node_id:
#                             current_node_id = starting_node_id
#                             current_node_doc = starting_node_doc
                
#                     elif operation == "CREATE_PATIENT":
#                         # Fallback if patientId is invalid; use session_data for phone/organization_id
#                         mrn = generate_mrn()
#                         patient = Patient(
#                             id=str(uuid.uuid4()),
#                             mrn=mrn,
#                             first_name=parameters.get("first_name", ""),
#                             last_name=parameters.get("last_name", ""),
#                             date_of_birth=parameters.get("date_of_birth"),
#                             phone=session_data.get("phone", "unknown"),
#                             organization_id=session_data.get("organization_id", "default_org"),
#                             created_at=datetime.utcnow(),
#                             updated_at=datetime.utcnow()
#                         )
#                         db.add(patient)
#                         db.commit()
#                         db.refresh(patient)
#                         operation_result = {
#                             "id": patient.id,
#                             "mrn": patient.mrn,
#                             "first_name": patient.first_name,
#                             "last_name": patient.last_name,
#                             "date_of_birth": patient.date_of_birth,
#                             "phone": patient.phone,
#                             "organization_id": patient.organization_id
#                         }
#                         # Save JSON file
#                         patient_path = f"patients/{patient.id}.json"
#                         os.makedirs(os.path.dirname(patient_path), exist_ok=True)
#                         with open(patient_path, "w") as f:
#                             patient_dict = {
#                                 "id": patient.id,
#                                 "mrn": patient.mrn,
#                                 "first_name": patient.first_name,
#                                 "last_name": patient.last_name,
#                                 "date_of_birth": patient.date_of_birth,
#                                 "phone": patient.phone,
#                                 "organization_id": patient.organization_id,
#                                 "created_at": patient.created_at.isoformat() if patient.created_at else None,
#                                 "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
#                             }
#                             json.dump(patient_dict, f, indent=2)
#                         content += f"\nProfile created successfully!"
#                         missing_fields = []
#                         for field in required_fields:
#                             value = getattr(patient, field, None)
#                             if not value or (isinstance(value, str) and not value.strip()):
#                                 missing_fields.append(field)
                        
#                         # Update onboarding status based on recalculated missing fields
#                         if not missing_fields:
#                             onboarding_status_to_send = "completed"
#                             print(f"🎉 ONBOARDING COMPLETE! All required fields now filled.")
#                         else:
#                             print(f"Still missing fields after update: {missing_fields}")
#                             # onboarding_status_to_send stays "in_progress"
#                         starting_node_id, starting_node_doc = get_starting_node(flow_index)
#                         print(f"[STARTING NODE] {starting_node_id, starting_node_doc}")
#                         if starting_node_id:
#                             current_node_id = starting_node_id
#                             current_node_doc = starting_node_doc
                
#                 except Exception as e:
#                     db.rollback()
#                     print(f"Database operation failed: {str(e)}")
#                     content += f"\nSorry, I couldn’t update your profile. Let’s try again."
#                     response_data["next_node_id"] = current_node_id

#             print(f"Response: {content}")
#             print(f"Next node ID: {next_node_id}")
#             print("==== PATIENT ONBOARDING/CHAT COMPLETE ====\n")
        
#             response = {
#                 "content": content,
#                 "next_node_id": current_node_id,
#                 "state_updates": state_updates,
#                 "onboarding_status": onboarding_status_to_send 
#             }
#             if operation_result:
#                 response["operation_result"] = operation_result
#             return response
        
      
#         # Format previous messages for better context
#         conversation_history = ""
#         if is_post_survey_start:
#             print("[CHAT] Excluding survey messages from conversation history")
#             # Only include non-survey messages (after survey completion)
#             message = 'hi'
#             conversation_history = ""
#             # for msg in previous_messages[user_message_count * 2:]:  # Skip survey Q&A pairs
#             #     role = msg.get("role", "unknown")
#             #     content = msg.get("content", "")
#             #     conversation_history += f"{role}: {content}\n"

#         else:
#             # Include all messages for ongoing conversation
#             for msg in previous_messages:
#                 role = msg.get("role", "unknown")
#                 content = msg.get("content", "")
#                 conversation_history += f"{role}: {content}\n"
#         print("conversation history", conversation_history, message)
        

#         if not session_data.get("currentNodeId") and not previous_messages:  # New session
#             starting_node_id, starting_node_doc = get_starting_node(flow_index)
#             print(f"[STARTING NODE] {starting_node_id, starting_node_doc}")
#             if starting_node_id:
#                 current_node_id = starting_node_id
#                 current_node_doc = starting_node_doc
                

#         # Basic String Query Approach - No Filters
#         if current_node_id:
#             try:
#                 # Create basic retriever with no filters
#                 retriever = flow_index.as_retriever(similarity_top_k=10)
                
#                 # Query directly for the node ID as text
#                 query_str = f"NODE ID: {current_node_id}"
#                 print(f"Querying for: '{query_str}'")
                
#                 # Use the most basic retrieval pattern
#                 node_docs = retriever.retrieve(query_str)
                
#                 # Check if we got any results
#                 if node_docs:
#                     # Find exact match for node_id in results
#                     exact_matches = [
#                         doc for doc in node_docs 
#                         if doc.metadata and doc.metadata.get("node_id") == current_node_id
#                     ]
                    
#                     if exact_matches:
#                         current_node_doc = exact_matches[0].get_content()
#                         print(f"Found exact match for node {current_node_id}")
#                     else:
#                         # Just use the top result
#                         current_node_doc = node_docs[0].get_content()
#                         print(f"No exact match, using top result")
                    
#                     print(f"Retrieved document for node {current_node_id}: {current_node_doc[:100]}...")
#                 else:
#                     print(f"No document found for node {current_node_id}")
#                     current_node_doc = "No specific node instructions available."
#             except Exception as e:
#                 print(f"Error retrieving node document: {str(e)}")
#                 current_node_doc = "Error retrieving node instructions."
                    
#         print(f"[CURRENT NODE DOC] {current_node_doc}")
#         # Check if last assistant message asked about LMP and current message is a date
#         calculated_gestational_info = ""
#         if previous_messages and len(previous_messages) >= 1:
#             last_assistant_msg = None
#             for msg in reversed(previous_messages):
#                 if msg.get("role") == "assistant":
#                     last_assistant_msg = msg.get("content", "").lower()
#                     break
            
#             if last_assistant_msg and any(keyword in last_assistant_msg for keyword in ["lmp", "mm/dd/yyyy", "gestational age"]):
#                 try:
#                     from datetime import datetime
#                     import re
                    
#                     # Check if current message is a date
#                     date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
#                     match = re.search(date_pattern, message.strip())
                    
#                     if match:
#                         month, day, year = match.groups()
#                         try:
#                             parsed_lmp = datetime.strptime(f"{month.zfill(2)}/{day.zfill(2)}/{year}", "%m/%d/%Y")
#                             current_datetime = datetime.strptime(current_date, "%m/%d/%Y")
                            
#                             if parsed_lmp <= current_datetime:
#                                 days_diff = (current_datetime - parsed_lmp).days
#                                 weeks = min(days_diff // 7, 40)
                                
#                                 if weeks <= 12:
#                                     trimester = "first"
#                                 elif weeks <= 27:
#                                     trimester = "second"
#                                 else:
#                                     trimester = "third"
                                
#                                 calculated_gestational_info = f"CALCULATED GESTATIONAL AGE FOR USER: Based on LMP {message.strip()}, the patient is {weeks} weeks pregnant and in the {trimester} trimester."
#                                 print(f"[MANUAL CALCULATION] {calculated_gestational_info}")
#                         except ValueError:
#                             pass
#                 except Exception as e:
#                     print(f"Error in manual gestational age calculation: {e}")


#         print(f"[DETECTED NODE] {current_node_id, current_node_doc}")
#         # Load document index (optional)
#         document_retriever = None
#         document_context = ""
#         if assistant_id:
#             if assistant_id not in app.state.document_indexes:
#                 bucket = storage_client.bucket(BUCKET_NAME)
#                 meta_file = f"temp_doc_{assistant_id}_meta.pkl"
#                 blob = bucket.blob(f"document_metadata/{assistant_id}_meta.pkl")
#                 try:
#                     blob.download_to_filename(meta_file)
#                     with open(meta_file, "rb") as f:
#                         metadata = pickle.load(f)
#                     os.remove(meta_file)

#                     temp_dir = f"temp_doc_{assistant_id}"
#                     os.makedirs(temp_dir, exist_ok=True)
#                     for blob in bucket.list_blobs(prefix=f"document_indices/{assistant_id}/"):
#                         local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
#                         blob.download_to_filename(local_path)

#                     collection_name = metadata["collection_name"]
#                     print("DEBUG: Entering Chroma collection block for documents")
#                     try:
#                         chroma_collection = chroma_client.get_collection(collection_name)
#                         print(f"Found existing Chroma collection {collection_name} for document index")
#                     except chromadb.errors.InvalidCollectionException:
#                         print(f"Creating new Chroma collection {collection_name} for document index")
#                         chroma_collection = chroma_client.create_collection(collection_name)
#                     vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

#                     storage_context = StorageContext.from_defaults(
#                         persist_dir=temp_dir, vector_store=vector_store
#                     )
#                     document_index = load_index_from_storage(storage_context)
#                     document_retriever = document_index.as_retriever(similarity_top_k=20)
#                     app.state.document_indexes[assistant_id] = {
#                         "index": document_index,
#                         "retriever": document_retriever,
#                         "created_at": metadata["created_at"],
#                         "document_count": metadata["document_count"],
#                         "node_count": metadata["node_count"]
#                     }
#                     shutil.rmtree(temp_dir)
#                 except Exception as e:
#                     print(f"Document index not found or failed to load: {str(e)}")
#             else:
#                 document_retriever = app.state.document_indexes[assistant_id]["retriever"]

#         if document_retriever:
#             print(f"Retrieving documents for query: '{message}'")
#             retrieved_nodes = document_retriever.retrieve(message)
#             document_text = ""
#             if retrieved_nodes:
#                 try:
#                     node_objs = [n.node for n in retrieved_nodes]
#                     if len(node_objs) > 1:
#                         print(f"Applying BM25 reranking to {len(node_objs)} nodes")
#                         bm25_retriever = BM25Retriever.from_defaults(
#                             nodes=node_objs, 
#                             similarity_top_k=min(5, len(node_objs))
#                         )
#                         reranked_nodes = bm25_retriever.retrieve(message)
#                         document_text = "\n\n".join([n.node.get_content() for n in reranked_nodes])
#                     else:
#                         document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#                 except Exception as e:
#                     print(f"BM25 reranking failed: {str(e)}, using vector results")
#                     document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#             document_context = f"Relevant Document Content:\n{document_text}" if document_text else ""
#             print(f"Document retrieval complete, found content with {len(document_context)} characters")
#         else:
#             print("No document retriever available, proceeding without document context")


#         is_survey_node = "NODE TYPE: surveyNode" in current_node_doc
#         # Define context section
#         document_context_section = f"""
# Relevant Document Content:
# {document_context}

# You are a helpful assistant tasked with providing accurate, specific, and context-aware responses. Follow these steps:
# 1. Identify the user's intent from the message and conversation history.
# 2. **IMPORTANT**: Scan the Relevant Document Content for any URLs, phone numbers, email addresses, or other specific resources.
# 3. **CRITICAL REQUIREMENT**: If ANY resources like URLs, phone numbers, or contact information are found, include them verbatim in your response.
# 4. Generate a natural, conversational response addressing the user's query, incorporating document content as needed.
# 5. Maintain continuity with the conversation history.
# 6. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION, but prioritize document content for specific details.
# 7. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
# 8. If no relevant document content is found, provide a helpful response based on the flow logic or general knowledge.
# 9. Double-check that all resource links, phone numbers, and contact methods from the document context are included.
# """ if document_context else """
# You are a helpful assistant tasked with providing accurate and context-aware responses. Follow these steps:
# 1. Identify the user's intent from the message and conversation history.
# 2. Generate a natural, conversational response addressing the user's query.
# 3. Maintain continuity with the conversation history.
# 4. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION.
# 5. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
# """

#         context_text = f"""

# The user message is: "{message}"

# The current node ID is: {current_node_id or "None - this is the first message"}

# current node documentation: {current_node_doc}

# Current Date (The current date in Eastern Time (MM/DD/YYYY)) is: {current_date}

# IMPORTANT: If this is the first message after survey questions (userMessageCount == surveyQuestions.length), 
# you MUST transition to the designated starting node which has nodeType='starting', not to node_7.



# Previous conversation:
# {conversation_history}

# The session data is:
# {json.dumps(session_data, indent=2)}

# Instructions for the deciding next node:

# Instructions for the deciding next node (CAN BE USED BUT NOT STRICTLY NECESSARY):
# 1. Remember one thing IMP: that the user always reply with {message}, Your task it to match the user {message} with current node documentation. 
# 2. If the current node's document ({current_node_doc}) is available and if "INSTRUCTION:" in current node doc is given make sure to include everything in the response but in Human Response Format. 
# 3. If the current node's document ({current_node_doc}) is available, use that to determine the next node based on the user's response that matches with Functions and message.
# 4. **MANDATORY**: If the current node's document ({current_node_doc}) contains a "FUNCTIONS:" section, you MUST match the user's response '{message}' to the conditions specified (e.g., 'If user replied with yes') and set 'next_node_id' to the corresponding node (e.g., 'proceed to node node_5'). Do NOT select a different node unless no FUNCTIONS match.
# 5. Many Dialogue Nodes may have similar functions (e.g., Node 1 might have functions "Yes" or "No" leading to different nodes, and Node 3 might also have "Yes" or "No" leading to different nodes). Therefore, evaluate the users response strictly in the context of the current node’s transitions or functions.
# 6. Rather than Acknowldge the user like "Okay Lets Move to another node" Execute that another node from functions (For Dialogue Node) which is matched with user message.
# 7. Do NOT include any acknowledgment text like "Okay," "I understand," "Let's move on," or "Great" in the response. Directly perform the next node's action as defined in its instructions (EXCEPT IF IT IS A nodetype == starting NODE WHICH ALWAYS STARTS WITH GREETINGS Like Great or Okay Let's Move On ).
# 8. For Dialogue Nodes and Survey Nodes, if the user's response matches a Function (e.g., 'If user replied with yes') or Trigger (e.g., 'If survey outcome is Completed'), identify the next node ID and retrieve its instructions to IMMEDIATELY execute its action (e.g., ask the next question).
# 9. If the user's response matches a function (For Dialogue Node) in the current node (e.g., 'If user replied with yes'), transition to the specified next node and IMMEDIATELY execute its action (e.g., ask the next question).
# 10. For Survey Nodes, if the user's response matches a Trigger (e.g., 'If survey outcome is Completed'), transition to the specified next node and IMMEDIATELY execute its action, as defined in the Next Node Instructions.
# 11. Do NOT provide generic responses For Dialogue Nodes with Functions like "Okay, let's move to the next node"; instead, directly perform the next node's action as defined in its instructions.
# 12. If the user's message does not match any Functions or Triggers in the current node's instructions, and no further progression is possible (e.g., no next node defined in the flow), use the Relevant Document Content {document_context_section} to generate a helpful response addressing the user's query. If no relevant document content is available, provide a general helpful response based on the conversation history.
# 13. Maintain conversation continuity and ensure responses are contextually appropriate.
# 14. If a date is provided in response to a function, update the date to MM/DD/YYYY format. The user message comes in as a string '29/04/1999' or something else. Consider this as a date only and store it in the required format.
# 15. If **`INSTRUCTION : `** In the current Node Doc Provides the asks to calculate the ** Gestational Age **. Then Provide the User with This Calculated Gestational Age `{calculated_gestational_info}`
# 16. If the current node's instruction mentions calculating or reporting gestational age, perform the calculation as in step 14 using the most recent date from the conversation history or session data.

# NOTE: If the user's message '{message}' does not match any Triggers or Functions defined in the current node's instructions ('{current_node_doc}'), set 'next_node_id' to the current node ID ('{current_node_id}') and generate a response that either re-prompts the user for a valid response or provides clarification, unless the node type specifies otherwise (e.g., scriptNode or callTransferNode).

# IMP NOTE: If **`INSTRUCTION : `** In the current Node Doc Provides the asks to calculate the ** Gestational Age **. Then Provide the User with This Calculated Gestational Age `{calculated_gestational_info}`

# Return your response as a JSON object with the following structure:
# {{
#     "content": "The response to send to the user, including specific document content where applicable",
#     "next_node_id": "ID of the next node to process (or current node if no match)",
#     "state_updates": {{
#         "key": "value"
#     }}
# }}
# """



#         print(f"[CHAT] Conversation history: {conversation_history}")

#         full_context = context_text
#         print(f"Full context length: {len(full_context)} characters")

#         # Create query engine
#         print("Creating flow query engine")
#         query_engine = flow_index.as_query_engine(
#             response_mode="compact",
#             similarity_top_k=7,
#             llm=Settings.llm
#         )

#         # Query the index
#         print("Querying flow index with full context")
#         response = query_engine.query(full_context)
#         print("Query complete, processing response")

#         # Process the response
#         try:
#             response_text = response.response
#             print(f"Raw response length: {len(response_text)} characters")

#             if "```json" in response_text:
#                 print("Parsing JSON from markdown code block with ```json")
#                 response_text = response_text.split("```json")[1].split("```")[0].strip()
#             elif "```" in response_text:
#                 print("Parsing JSON from markdown code block")
#                 response_text = response_text.split("```")[1].split("```")[0].strip()

#             print(f"Cleaned response: {response_text[:100]}..." if len(response_text) > 100 else response_text)
#             response_data = json.loads(response_text)
#             print("Successfully parsed JSON response")

#             ai_response = response_data.get("content", "I'm having trouble processing your request.")
#             next_node_id = response_data.get("next_node_id")
#             state_updates = response_data.get("state_updates", {})

#             # Check if no function match and no progression (e.g., no functions or all unmatched)
#             has_functions = False
#             if "FUNCTIONS:" in current_node_doc:
#                 functions_section = current_node_doc.split("FUNCTIONS:")[1]
#                 # Check if there are any non-empty lines after FUNCTIONS:
#                 has_functions = any(f.strip() for f in functions_section.split("\n") if f.strip())
#             print(f"[HAS FUNCTION] ({has_functions}), Current Node ID : {current_node_id}")

#             # Enter fallback if no functions exist
#             # print(f"DOCUMENT CONTEXT {document_context}")
#             if not has_functions and not is_survey_node and current_node_id is None:
#                 print("No function match and no progression detected, generating fallback response")
#                 if document_context_section:
#                     print("Using document context for response")
#                     fallback_prompt = f"""
#                     You are a helpful assistant. The user has sent the following message:
                    
#                     The user's last message was: "{message}"

#                     Previous conversation:
#                     {conversation_history}
                    
#                     Relevant Document Content:
#                     {document_context_section}
                    
#                     INSTRUCTION:
#                      INSTRUCTIONS FOR YOUR RESPONSE:
#                     1.  **PRIMARY REQUIREMENT**: You MUST first deliver the message provided in "Current Node's Primary Message/Instruction" verbatim or rephrased naturally. This is the essential response for this stage of the conversation.
#                     2.  After including the primary message, if the "Relevant Document Content" is present and offers *additional, helpful* information directly related to the user's query or the ongoing conversation (especially if no further flow options exist for this node), integrate it gracefully and naturally.
#                     3.  Maintain a natural, conversational, and empathetic tone.
#                     4.  Ensure any URLs, phone numbers, email addresses, or specific resources from either the "Current Node's Primary Message/Instruction" or "Relevant Document Content" are included verbatim.
                    
#                     Please provide a helpful response based on the document content, addressing the user's query.
#                     """
#                 else:
#                     print("No document context available, using general fallback")
#                     fallback_prompt = f"""
#                     You are a helpful assistant. The user has sent the following message:
                    
#                     "{message}"
                    
#                     Previous conversation:
#                     {conversation_history}
                    
#                     I couldn't find specific information to proceed. Please provide a helpful response based on the conversation history.
#                     """
#                 fallback_response = Settings.llm.complete(fallback_prompt)
#                 ai_response = fallback_response.text
#                 print(f"Fallback response generated, length: {len(ai_response)} characters")

            

#             print(f'[AI RESPONSE]', ai_response)
#             rephrase_prompt = f"""
#             You are a friendly, conversational assistant tasked with rephrasing a given text to sound natural, human-like, and context-aware.

#             CRITICAL: You must ONLY rephrase the text in 'Original Response': {ai_response}. Do NOT create new content or ask different questions.
#             CRITICAL: Do NOT ask any questions that are not in the Original Response {ai_response}
#             CRITICAL: Keep ALL content including phone number placeholders like $Clinic_Phone$. 

#             Instructions:
#             1.  **Rephrase** the 'Original Response' to sound natural and human-like, preserving its exact intent and type (statement or question).
#             2.  **Personalize the response:** If the patient's first name is available in 'Patient Profile', use it at the beginning of the response.
#             3.  **Subtly incorporate relevant 'Patient History':** Only incorporate 'Patient History' if it directly supports the original response without altering its intent or introducing new questions. If any detail from the 'Patient History' can be seamlessly and non-contradictorily woven into the rephrased 'Original Response' to make it more contextually rich, do so. For example, if the original response is a general greeting and the history mentions a positive pregnancy test, you can add "I see you recently reported a positive pregnancy test." If the original response is a question about a date, you might add, "We have your last reported LMP as [date], would you like to update that?"
#             4.  **Maintain the original intent and type:** If the 'Original Response' is a question, the rephrased response MUST be a question. If it's a statement, it MUST be a statement. Do not add new questions or change the core meaning.
#             5.  **Crucially: Do NOT contradict or question the 'Original Response'.** Your goal is to enhance it, not to challenge its premise or introduce new, conflicting information.
#             6.  **Do NOT** include acknowledgment phrases like 'Okay,' 'Great,' 'I understand,' or 'Let's move on' unless they ar
#             7.  If the `Original Response` includes calculated values (e.g., gestational age), preserve them verbatim in the rephrased response.
#             8.  **Do NOT** ask for confirmation of previously provided data (e.g., LMP date) unless explicitly instructed by the `Original Response` or node instructions.

#             Original Response (from the main LLM, this is the message you must rephrase): "{ai_response}"
            
#             User message: "{message}"

#             Patient Profile (for personalization, e.g., first_name):
#             {patient_fields}

#             Patient History (for subtle contextual enrichment, use only if it fits without contradiction):
#             {patient_history}

#             Return the rephrased response as a string.
#             """
#             print("Calling secondary LLM for rephrasing")
#             rephrased_response = Settings.llm.complete(rephrase_prompt).text.strip()
#             if rephrased_response.startswith('"') and rephrased_response.endswith('"'):
#                 rephrased_response = rephrased_response[1:-1]
#             if not has_functions:
#                 next_node_id = None
#                 print(f"[END NODE] Setting next_node_id to None - no further progression")

#             print(f"Rephrased response: {rephrased_response}")
#             print(f"AI response length: {len(ai_response)} characters")
#             print(f"Next node ID: {next_node_id}")
#             print(f"State updates: {json.dumps(state_updates, indent=2)}")
#             print("==== VECTOR CHAT PROCESSING COMPLETE ====\n")
            
#             return {
#                 "content": rephrased_response,
#                 "next_node_id": next_node_id,
#                 "state_updates": state_updates,
#                 "onboarding_status": onboarding_status_to_send 


#             }

#         except Exception as e:
#             print(f"ERROR processing vector response: {str(e)}")
#             print(f"Response text that failed to parse: {response_text[:200]}...")

#             # Fallback to direct LLM response
#             print("Using fallback LLM response")
#             fallback_prompt = f"""
#             You are a helpful assistant. The user has sent the following message:
            
#             "{message}"
            
#             Previous conversation:
#             {conversation_history}
            
#             Please provide a helpful response.
#             """

#             fallback_response = Settings.llm.complete(fallback_prompt)
#             print(f"Fallback response generated, length: {len(fallback_response.text)} characters")
#             print("==== VECTOR CHAT PROCESSING COMPLETE (FALLBACK) ====\n")

#             return {
#                 "content": fallback_response.text,
#                 "error": f"Vector processing failed: {str(e)}",
#                 "fallback": True
#             }

#     except Exception as e:
#         print(f"CRITICAL ERROR in vector_chat: {str(e)}")
#         traceback_str = traceback.format_exc()
#         print(f"Traceback: {traceback_str}")
#         print("==== VECTOR CHAT PROCESSING FAILED ====\n")
#         return {
#             "error": f"Failed to process message: {str(e)}",
#             "content": "I'm having trouble processing your request. Please try again later."
#         }
    
def call_vertex_endpoint(prompt, max_tokens=1000, temperature=0.3):
    """Helper function to call Vertex AI endpoint"""
    try:
        parameters = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
            "top_k": 40,
            "top_p": 0.95
        }
        response = endpoint.predict(instances=[{"prompt": prompt}], parameters=parameters)
        if response.predictions and len(response.predictions) > 0:
            return response.predictions[0]
        else:
            return "No response generated"
    except Exception as e:
        print(f"Error calling Vertex AI endpoint: {str(e)}")
        return f"Error: {str(e)}"


@app.post("/api/shared/vector_chat")
async def vector_flow_chat(request: dict):
    """
    Process a chat message using the vector-based flow knowledge index.
    This endpoint doesn't rely on Firestore or Gemini services.
    """
    import traceback
    import json
    from datetime import datetime
    from llama_index.core import VectorStoreIndex, StorageContext
    from llama_index.vector_stores.chroma import ChromaVectorStore
    from llama_index.retrievers.bm25 import BM25Retriever
    from langdetect import detect, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException

    eastern = pytz.timezone('America/New_York')
    current_time = datetime.now(eastern)
    current_date = current_time.date().strftime('%m/%d/%Y')
    print(f"[CURRENT DATE] {current_date}")
    try:
        print("\n==== STARTING VECTOR CHAT PROCESSING ====")
        message = request.get("message", "")
        sessionId = request.get("sessionId", "")
        flow_id = request.get("flow_id")
        assistant_id = request.get("assistantId")
        session_data = request.get("session_data", {})
        previous_messages = request.get("previous_messages", [])
        patientId = request.get("patientId", "")
        patient_history = request.get("patient_history", "")  # New: Extract patient history
        print(f"[PATIENT HISTORY] {patient_history}")
        onboarding_status_from_session = session_data.get("onboardingStatus") # Use .get() for safety
        print(f"[ONBOARDING STATUS], {onboarding_status_from_session}")
        Onboarding = None
        print(f"Message: '{message}'")
        print(f"Session ID: {sessionId}")
        print(f"Flow ID: {flow_id}")
        print(f"Assistant ID: {assistant_id}")
        print(f"Session data: {json.dumps(session_data, indent=2)}")
        print(f"Number of previous messages: {len(previous_messages)}")
        print(f"previous messages",previous_messages )
        # Add after retrieving session data
        is_new_session = not session_data.get('currentNodeId') and len(previous_messages) <= 6
        print(f"Is likely new session: {is_new_session}")
        print(f"session data {session_data}")
        current_node_id = session_data.get('currentNodeId')
        current_node_doc = ""
        print(f"Current node ID: {current_node_id}")
        survey_questions_length = session_data.get('survey_questions_length', 0)
        user_message_count = sum(1 for msg in previous_messages if msg.get("role") == "user")
        is_post_survey_start = (current_node_id is None and 
                            user_message_count >= survey_questions_length and 
                            survey_questions_length > 0)
        common_greetings = ['hi', 'hello', 'hey', 'good', 'morning', 'afternoon', 'evening']

        print(f"[CHAT] Survey questions length: {survey_questions_length}")
        print(f"[CHAT] User message count: {user_message_count}")
        print(f"[CHAT] Is post-survey start: {is_post_survey_start}")

        
        
        # Try to get starting node info from app state if available
        if hasattr(app.state, 'starting_node_ids') and flow_id in getattr(app.state, 'starting_node_ids', {}):
            print(f"Cached starting node for flow {flow_id}: {app.state.starting_node_ids[flow_id]}")
        else:
            print("No cached starting node info available")
            
        if not flow_id:
            print("ERROR: flow_id is required")
            return {
                "error": "flow_id is required",
                "content": "Missing required parameters"
            }
        
        # Load flow index
        if flow_id not in app.state.flow_indices:
            bucket = storage_client.bucket(BUCKET_NAME)
            meta_file = f"temp_flow_{flow_id}_meta.pkl"
            blob = bucket.blob(f"flow_metadata/{flow_id}_meta.pkl")
            try:
                blob.download_to_filename(meta_file)
                with open(meta_file, "rb") as f:
                    metadata = pickle.load(f)
                os.remove(meta_file)
            except Exception as e:
                print(f"Failed to load flow index metadata from GCS: {str(e)}")
                return {
                    "error": "Flow knowledge index not found. Please index the flow first.",
                    "content": "I'm having trouble processing your request."
                }

            temp_dir = f"temp_flow_{flow_id}"
            os.makedirs(temp_dir, exist_ok=True)
            for blob in bucket.list_blobs(prefix=f"flow_indices/{flow_id}/"):
                local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
                blob.download_to_filename(local_path)

            collection_name = metadata["collection_name"]
            print("DEBUG: Entering Chroma collection block")
            try:
                chroma_collection = chroma_client.get_collection(collection_name)
                print(f"Found existing Chroma collection {collection_name}")
            except chromadb.errors.InvalidCollectionException:
                print(f"Creating new Chroma collection {collection_name}")
                chroma_collection = chroma_client.create_collection(collection_name)
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

            storage_context = StorageContext.from_defaults(
                persist_dir=temp_dir, vector_store=vector_store
            )
            flow_index = load_index_from_storage(storage_context)
            app.state.flow_indices[flow_id] = flow_index
            shutil.rmtree(temp_dir)
        else:
            flow_index = app.state.flow_indices[flow_id]
            print('Flow Data', flow_index)
            print(f"[CHAT] Using cached flow index for flow_id: {flow_id}")

        
        patient = db.query(Patient).filter(Patient.id == patientId).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        patient_dict = {
            "id": patient.id,
            "mrn": patient.mrn,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,

        }
        patient_fields = json.dumps(patient_dict, indent=2)
        required_fields = ["first_name", "last_name", "date_of_birth"]
        missing_fields = []
        for field in required_fields:
            value = getattr(patient, field, None)
            if not value or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)


        print(f"[MISSING FIELDS], {missing_fields}")
        print(f"[PATIENT FIELDS], {patient_fields}")

        onboarding_status_to_send = "in_progress" # Default to in_progress
        if not missing_fields:
                onboarding_status_to_send = "completed"

        
        if missing_fields: 
            print("==== PATIENT ONBOARDING/CHAT START ====\n")
            # Direct approach - no LLM needed
            import re

            # Determine which field to ask for (first missing field)
            field_to_ask = missing_fields[0]

            # Check if user provided information for the current missing field
            database_operation = None
            content = ""

            if field_to_ask == "first_name":
                # Filter out common greetings and check if this is a greeting/start message
                common_greetings = ['hi', 'hello', 'hey', 'good', 'morning', 'afternoon', 'evening']
                message_lower = message.strip().lower()
                
                # If it's a greeting or very short, ask for name instead of extracting
                if message_lower in common_greetings or len(message.strip()) < 2:
                    content = "Hey, nice to hear from you! I need a bit of info to get you set up. Could you share your first name?"
                else:
                    # Try to extract name from non-greeting messages
                    name_match = re.search(r'\b([A-Za-z]{2,})\b', message.strip())
                    if name_match:
                        extracted_name = name_match.group(1).lower()
                        database_operation = {
                            "operation": "UPDATE_PATIENT",
                            "parameters": {
                                "patient_id": patientId,
                                "field_name": "first_name",
                                "field_value": extracted_name
                            }
                        }
                        content = f"Great! I've got your first name as {extracted_name.title()}. Now I need your last name."
                    else:
                        content = "I need your first name. Could you please share it?"

            elif field_to_ask == "last_name":
                name_match = re.search(r'\b([A-Za-z]+)\b', message.strip())
                if name_match:
                    extracted_name = name_match.group(1).lower()
                    database_operation = {
                        "operation": "UPDATE_PATIENT",
                        "parameters": {
                            "patient_id": patientId,
                            "field_name": "last_name",
                            "field_value": extracted_name
                        }
                    }
                    content = f"Perfect! Last name recorded as {extracted_name.title()}. What's your date of birth? Please use format MM/DD/YYYY like 03/29/1996."
                else:
                    content = "I need your last name. Could you please share it?"

            elif field_to_ask == "date_of_birth":
                date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', message.strip())
                if date_match:
                    month, day, year = date_match.groups()
                    formatted_date = f"{month.zfill(2)}/{day.zfill(2)}/{year}"
                    try:
                        parsed_date = datetime.strptime(formatted_date, "%m/%d/%Y")
                        current_datetime = datetime.strptime(current_date, "%m/%d/%Y")
                        
                        if parsed_date <= current_datetime:
                            database_operation = {
                                "operation": "UPDATE_PATIENT",
                                "parameters": {
                                    "patient_id": patientId,
                                    "field_name": "date_of_birth",
                                    "field_value": formatted_date
                                }
                            }
                            content = f"Perfect! Thanks for providing your information. Your profile is now complete and please say 'Hi' To Get started."
                        else:
                            content = "That date seems to be in the future. Could you please provide a valid date of birth in MM/DD/YYYY format?"
                    except ValueError:
                        content = "I couldn't understand that date format. Could you please use MM/DD/YYYY format like 03/29/1996?"
                else:
                    content = "I need your date of birth. Please use the format MM/DD/YYYY, like 03/29/1996."

            next_node_id = None
            state_updates = {}

            operation_result = None
            if database_operation:
                operation = database_operation.get("operation")
                parameters = database_operation.get("parameters", {})
                try:
                    if operation == "UPDATE_PATIENT":
                        patient = db.query(Patient).filter(Patient.id == patientId).first()
                        if not patient:
                            raise HTTPException(status_code=404, detail="Patient not found")
                        setattr(patient, parameters["field_name"], parameters["field_value"])
                        patient.updated_at = datetime.utcnow()
                        db.commit()
                        db.refresh(patient)
                        operation_result = {
                            "id": patient.id,
                            "mrn": patient.mrn,
                            "first_name": patient.first_name,
                            "last_name": patient.last_name,
                            "date_of_birth": patient.date_of_birth,
                            "phone": patient.phone,
                            "organization_id": patient.organization_id
                        }
                        # Update JSON file
                        patient_path = f"patients/{patient.id}.json"
                        os.makedirs(os.path.dirname(patient_path), exist_ok=True)
                        with open(patient_path, "w") as f:
                            patient_dict = {
                                "id": patient.id,
                                "mrn": patient.mrn,
                                "first_name": patient.first_name,
                                "last_name": patient.last_name,
                                "date_of_birth": patient.date_of_birth,
                                "phone": patient.phone,
                                "organization_id": patient.organization_id,
                                "created_at": patient.created_at.isoformat() if patient.created_at else None,
                                "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
                            }
                            json.dump(patient_dict, f, indent=2)
                        content += f"\nProfile updated successfully!"
                        missing_fields = []
                        for field in required_fields:
                            value = getattr(patient, field, None)
                            if not value or (isinstance(value, str) and not value.strip()):
                                missing_fields.append(field)
                        
                        # Update onboarding status based on recalculated missing fields
                        if not missing_fields:
                            onboarding_status_to_send = "completed"
                            print(f"🎉 ONBOARDING COMPLETE! All required fields now filled.")
                        else:
                            print(f"Still missing fields after UPDATE: {missing_fields}")
                            # onboarding_status_to_send stays "in_progress"
                        starting_node_id, starting_node_doc = get_starting_node(flow_index)
                        print(f"[STARTING NODE, FROM UPDATE] {starting_node_id, starting_node_doc}")
                        if starting_node_id:
                            current_node_id = starting_node_id
                            current_node_doc = starting_node_doc
                
                    elif operation == "CREATE_PATIENT":
                        # Fallback if patientId is invalid; use session_data for phone/organization_id
                        mrn = generate_mrn()
                        patient = Patient(
                            id=str(uuid.uuid4()),
                            mrn=mrn,
                            first_name=parameters.get("first_name", ""),
                            last_name=parameters.get("last_name", ""),
                            date_of_birth=parameters.get("date_of_birth"),
                            phone=session_data.get("phone", "unknown"),
                            organization_id=session_data.get("organization_id", "default_org"),
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(patient)
                        db.commit()
                        db.refresh(patient)
                        operation_result = {
                            "id": patient.id,
                            "mrn": patient.mrn,
                            "first_name": patient.first_name,
                            "last_name": patient.last_name,
                            "date_of_birth": patient.date_of_birth,
                            "phone": patient.phone,
                            "organization_id": patient.organization_id
                        }
                        # Save JSON file
                        patient_path = f"patients/{patient.id}.json"
                        os.makedirs(os.path.dirname(patient_path), exist_ok=True)
                        with open(patient_path, "w") as f:
                            patient_dict = {
                                "id": patient.id,
                                "mrn": patient.mrn,
                                "first_name": patient.first_name,
                                "last_name": patient.last_name,
                                "date_of_birth": patient.date_of_birth,
                                "phone": patient.phone,
                                "organization_id": patient.organization_id,
                                "created_at": patient.created_at.isoformat() if patient.created_at else None,
                                "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
                            }
                            json.dump(patient_dict, f, indent=2)
                        content += f"\nProfile created successfully!"
                        missing_fields = []
                        for field in required_fields:
                            value = getattr(patient, field, None)
                            if not value or (isinstance(value, str) and not value.strip()):
                                missing_fields.append(field)
                        
                        # Update onboarding status based on recalculated missing fields
                        if not missing_fields:
                            onboarding_status_to_send = "completed"
                            print(f"🎉 ONBOARDING COMPLETE! All required fields now filled.")
                        else:
                            print(f"Still missing fields after update: {missing_fields}")
                            # onboarding_status_to_send stays "in_progress"
                        starting_node_id, starting_node_doc = get_starting_node(flow_index)
                        print(f"[STARTING NODE] {starting_node_id, starting_node_doc}")
                        if starting_node_id:
                            current_node_id = starting_node_id
                            current_node_doc = starting_node_doc
                
                except Exception as e:
                    db.rollback()
                    print(f"Database operation failed: {str(e)}")
                    content += f"\nSorry, I couldn’t update your profile. Let’s try again."
                    response_data["next_node_id"] = current_node_id

            print(f"Response: {content}")
            print(f"Next node ID: {next_node_id}")
            print("==== PATIENT ONBOARDING/CHAT COMPLETE ====\n")
        
            response = {
                "content": content,
                "next_node_id": current_node_id,
                "state_updates": state_updates,
                "onboarding_status": onboarding_status_to_send 
            }
            if operation_result:
                response["operation_result"] = operation_result
            return response
        
      
        # Format previous messages for better context
        conversation_history = ""
        if is_post_survey_start:
            print("[CHAT] Excluding survey messages from conversation history")
            # Only include non-survey messages (after survey completion)
            message = 'hi'
            conversation_history = ""
            # for msg in previous_messages[user_message_count * 2:]:  # Skip survey Q&A pairs
            #     role = msg.get("role", "unknown")
            #     content = msg.get("content", "")
            #     conversation_history += f"{role}: {content}\n"

        else:
            # Include all messages for ongoing conversation
            for msg in previous_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                conversation_history += f"{role}: {content}\n"
        print("conversation history", conversation_history, message)
        

        if not session_data.get("currentNodeId") and not previous_messages:  # New session
            starting_node_id, starting_node_doc = get_starting_node(flow_index)
            print(f"[STARTING NODE] {starting_node_id, starting_node_doc}")
            if starting_node_id:
                current_node_id = starting_node_id
                current_node_doc = starting_node_doc
                
        #Special Case For the Survey Node
        if message.lower().strip() == 'completed survey' and current_node_id:
            try:
                retriever = flow_index.as_retriever(
                    filters=MetadataFilters(filters=[
                        MetadataFilter(
                            key="node_id", 
                            value=current_node_id, 
                            operator=FilterOperator.EQ
                        )
                    ])
                )
                node_docs = retriever.retrieve(f"NODE ID: {current_node_id}")
                
                if node_docs:
                    current_node_content = node_docs[0].get_content()
                    is_current_survey_node = "NODE TYPE: surveyNode" in current_node_content
                    
                    if is_current_survey_node:
                        print(f"[SURVEY COMPLETION] Detected 'completed' message on survey node {current_node_id}")
                        
                        # Check for completion trigger in TRIGGERS section
                        if "TRIGGERS:" in current_node_content:
                            triggers_section = current_node_content.split("TRIGGERS:")[1].strip()
                            
                            import re
                            completion_match = re.search(r"If survey outcome is ['\"]?Completed['\"]?, proceed to node (\w+)", triggers_section)
                            
                            if completion_match:
                                current_node_id = completion_match.group(1)
                                print(f"[SURVEY COMPLETION] Setting current_node_id to: {current_node_id}")
                            else:
                                print(f"[SURVEY COMPLETION] No completion trigger found, returning completion message")
                                return {
                                    "content": "Thanks for filling out the survey, is there anything you need help with?",
                                    "next_node_id": None,
                                    "state_updates": {},
                                    "onboarding_status": onboarding_status_to_send
                                }
                        else:
                            print(f"[SURVEY COMPLETION] No TRIGGERS section found, returning completion message")
                            return {
                                "content": "Thanks for filling out the survey, is there anything you need help with?",
                                "next_node_id": None,
                                "state_updates": {},
                                "onboarding_status": onboarding_status_to_send
                            }
            except Exception as e:
                print(f"[SURVEY COMPLETION] Error checking survey completion: {str(e)}")

        # Basic String Query Approach - No Filters
        if current_node_id:
            try:
                # Create basic retriever with no filters
                # retriever = flow_index.as_retriever(similarity_top_k=10)
                
                # # Query directly for the node ID as text
                # query_str = f"NODE ID: {current_node_id}"
                # print(f"Querying for: '{query_str}'")
                
                # # Use the most basic retrieval pattern
                # node_docs = retriever.retrieve(query_str)
                
                retriever = flow_index.as_retriever(
                    filters=MetadataFilters(filters=[
                        MetadataFilter(
                            key="node_id", 
                            value=current_node_id, 
                            operator=FilterOperator.EQ
                        )
                    ])
                )
                
                # Query for the node - the filter ensures we only get exact matches
                query_str = f"NODE ID: {current_node_id}"
                print(f"Querying for: '{query_str}' with metadata filter")
                
                node_docs = retriever.retrieve(query_str)
                # Check if we got any results
                if node_docs:
                    # Find exact match for node_id in results
                    exact_matches = [
                        doc for doc in node_docs 
                        if doc.metadata and doc.metadata.get("node_id") == current_node_id
                    ]
                    
                    if exact_matches:
                        current_node_doc = exact_matches[0].get_content()
                        print(f"Found exact match for node {current_node_id}")
                    else:
                        # Just use the top result
                        current_node_doc = node_docs[0].get_content()
                        print(f"No exact match, using top result")
                    
                    print(f"Retrieved document for node {current_node_id}: {current_node_doc[:100]}...")
                else:
                    print(f"No document found for node {current_node_id}")
                    current_node_doc = "No specific node instructions available."
            except Exception as e:
                print(f"Error retrieving node document: {str(e)}")
                try:
                    print("Falling back to similarity search approach")
                    retriever = flow_index.as_retriever(similarity_top_k=1000)  # Use high number as fallback
                    query_str = f"NODE ID: {current_node_id}"
                    node_docs = retriever.retrieve(query_str)
                    
                    if node_docs:
                        exact_matches = [
                            doc for doc in node_docs 
                            if doc.metadata and doc.metadata.get("node_id") == current_node_id
                        ]
                        
                        if exact_matches:
                            current_node_doc = exact_matches[0].get_content()
                            print(f"Found exact match for node {current_node_id} using fallback")
                        else:
                            current_node_doc = node_docs[0].get_content()
                            print(f"No exact match, using top result from fallback")
                    else:
                        current_node_doc = "No specific node instructions available."
                except Exception as fallback_e:
                    print(f"Fallback approach also failed: {str(fallback_e)}")
                    current_node_doc = "Error retrieving node instructions"
                    
        print(f"[CURRENT NODE DOC] {current_node_doc}")
        # Check if last assistant message asked about LMP and current message is a date
        calculated_gestational_info = ""
        if previous_messages and len(previous_messages) >= 1:
            last_assistant_msg = None
            for msg in reversed(previous_messages):
                if msg.get("role") == "assistant":
                    last_assistant_msg = msg.get("content", "").lower()
                    break
            
            if last_assistant_msg and any(keyword in last_assistant_msg for keyword in ["lmp", "mm/dd/yyyy", "gestational age"]):
                try:
                    from datetime import datetime
                    import re
                    
                    # Check if current message is a date
                    date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
                    match = re.search(date_pattern, message.strip())
                    
                    if match:
                        month, day, year = match.groups()
                        try:
                            parsed_lmp = datetime.strptime(f"{month.zfill(2)}/{day.zfill(2)}/{year}", "%m/%d/%Y")
                            current_datetime = datetime.strptime(current_date, "%m/%d/%Y")
                            
                            if parsed_lmp <= current_datetime:
                                days_diff = (current_datetime - parsed_lmp).days
                                weeks = min(days_diff // 7, 40)
                                
                                if weeks <= 12:
                                    trimester = "first"
                                elif weeks <= 27:
                                    trimester = "second"
                                else:
                                    trimester = "third"
                                
                                calculated_gestational_info = f"CALCULATED GESTATIONAL AGE FOR USER: Based on LMP {message.strip()}, the patient is {weeks} weeks pregnant and in the {trimester} trimester."
                                print(f"[MANUAL CALCULATION] {calculated_gestational_info}")
                        except ValueError:
                            pass
                except Exception as e:
                    print(f"Error in manual gestational age calculation: {e}")


        print(f"[DETECTED NODE] {current_node_id, current_node_doc}")
        # Load document index (optional)
        document_retriever = None
        document_context = ""
        if assistant_id:
            if assistant_id not in app.state.document_indexes:
                bucket = storage_client.bucket(BUCKET_NAME)
                meta_file = f"temp_doc_{assistant_id}_meta.pkl"
                blob = bucket.blob(f"document_metadata/{assistant_id}_meta.pkl")
                try:
                    blob.download_to_filename(meta_file)
                    with open(meta_file, "rb") as f:
                        metadata = pickle.load(f)
                    os.remove(meta_file)

                    temp_dir = f"temp_doc_{assistant_id}"
                    os.makedirs(temp_dir, exist_ok=True)
                    for blob in bucket.list_blobs(prefix=f"document_indices/{assistant_id}/"):
                        local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
                        blob.download_to_filename(local_path)

                    collection_name = metadata["collection_name"]
                    print("DEBUG: Entering Chroma collection block for documents")
                    try:
                        chroma_collection = chroma_client.get_collection(collection_name)
                        print(f"Found existing Chroma collection {collection_name} for document index")
                    except chromadb.errors.InvalidCollectionException:
                        print(f"Creating new Chroma collection {collection_name} for document index")
                        chroma_collection = chroma_client.create_collection(collection_name)
                    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

                    storage_context = StorageContext.from_defaults(
                        persist_dir=temp_dir, vector_store=vector_store
                    )
                    document_index = load_index_from_storage(storage_context)
                    document_retriever = document_index.as_retriever(similarity_top_k=20)
                    app.state.document_indexes[assistant_id] = {
                        "index": document_index,
                        "retriever": document_retriever,
                        "created_at": metadata["created_at"],
                        "document_count": metadata["document_count"],
                        "node_count": metadata["node_count"]
                    }
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    print(f"Document index not found or failed to load: {str(e)}")
            else:
                document_retriever = app.state.document_indexes[assistant_id]["retriever"]

        if document_retriever:
            print(f"Retrieving documents for query: '{message}'")
            retrieved_nodes = document_retriever.retrieve(message)
            document_text = ""
            if retrieved_nodes:
                try:
                    node_objs = [n.node for n in retrieved_nodes]
                    if len(node_objs) > 1:
                        print(f"Applying BM25 reranking to {len(node_objs)} nodes")
                        bm25_retriever = BM25Retriever.from_defaults(
                            nodes=node_objs, 
                            similarity_top_k=min(5, len(node_objs))
                        )
                        reranked_nodes = bm25_retriever.retrieve(message)
                        document_text = "\n\n".join([n.node.get_content() for n in reranked_nodes])
                    else:
                        document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
                except Exception as e:
                    print(f"BM25 reranking failed: {str(e)}, using vector results")
                    document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
            document_context = f"Relevant Document Content:\n{document_text}" if document_text else ""
            print(f"Document retrieval complete, found content with {len(document_context)} characters")
        else:
            print("No document retriever available, proceeding without document context")


        is_survey_node = "NODE TYPE: surveyNode" in current_node_doc
        # Define context section
        document_context_section = f"""
            Relevant Document Content:
            {document_context}

            You are a helpful assistant tasked with providing accurate, specific, and context-aware responses. Follow these steps:
            1. Identify the user's intent from the message and conversation history.
            2. **IMPORTANT**: Scan the Relevant Document Content for any URLs, phone numbers, email addresses, or other specific resources.
            3. **CRITICAL REQUIREMENT**: If ANY resources like URLs, phone numbers, or contact information are found, include them verbatim in your response.
            4. Generate a natural, conversational response addressing the user's query, incorporating document content as needed.
            5. Maintain continuity with the conversation history.
            6. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION, but prioritize document content for specific details.
            7. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
            8. If no relevant document content is found, provide a helpful response based on the flow logic or general knowledge.
            9. Double-check that all resource links, phone numbers, and contact methods from the document context are included.
            """ if document_context else """
            You are a helpful assistant tasked with providing accurate and context-aware responses. Follow these steps:
            1. Identify the user's intent from the message and conversation history.
            2. Generate a natural, conversational response addressing the user's query.
            3. Maintain continuity with the conversation history.
            4. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION.
            5. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
            """

        # Check if user message doesn't match current node functions and provide document context response
        if current_node_id and current_node_doc and document_context and message.lower().strip() not in common_greetings:
            # Check if current node has functions
            if "FUNCTIONS:" in current_node_doc:
                # Check if user message matches any function
                function_match_prompt = f"""
                User message: "{message}"
                Current node functions: {current_node_doc.split("FUNCTIONS:")[1] if "FUNCTIONS:" in current_node_doc else "None"}
                
                Does the user's message match any of the functions/conditions listed? 
                Return only "MATCH" or "NO_MATCH"
                """
                
                try:
                    # match_response = Settings.llm.complete(function_match_prompt).text.strip()
                    match_response = call_vertex_endpoint(function_match_prompt, max_tokens=10, temperature=0.0)
                    if isinstance(match_response, str):
                        match_response = match_response.strip()

                    print(f"[FUNCTION MATCH CHECK] {match_response}")
                    
                    if "NO_MATCH" in match_response.upper():
                        # User message doesn't match functions, provide document context + current node instruction
                        
                        # Extract current node instruction
                        current_instruction = ""
                        try:
                            instruction_start = current_node_doc.find("INSTRUCTION:") + len("INSTRUCTION:")
                            instruction_end = current_node_doc.find("FUNCTIONS:") if "FUNCTIONS:" in current_node_doc else len(current_node_doc)
                            current_instruction = current_node_doc[instruction_start:instruction_end].strip()
                        except Exception as e:
                            print(f"Error extracting current instruction: {str(e)}")
                        
                        # Generate combined response from document context + current node instruction
                        combined_response_prompt = f"""
                        You are a helpful assistant. The user has sent the following message:
                        
                        The user's last message was: "{message}"
                        
                        Relevant Document Content:
                        {document_context_section}
                        
                        INSTRUCTION:
                        INSTRUCTIONS FOR YOUR RESPONSE:
                        1.  **PRIMARY REQUIREMENT**: You MUST first deliver the message provided in "Current Node's Primary Message/Instruction" verbatim or rephrased naturally. This is the essential response for this stage of the conversation.
                        2.  After including the primary message, if the "Relevant Document Content" is present and offers *additional, helpful* information directly related to the user's query or the ongoing conversation (especially if no further flow options exist for this node), integrate it gracefully and naturally.
                        3.  Maintain a natural, conversational, and empathetic tone.
                        4.  Ensure any URLs, phone numbers, email addresses, or specific resources from either the "Current Node's Primary Message/Instruction" or "Relevant Document Content" are included verbatim.
                        
                        MUST Format your response like this:
                        "The Information you are asking for is this: [specific detailed answer from document context including any medications, dosages, recommendations, etc.] + Okay Now, {current_instruction}" 
                        
                        Please provide a helpful response based on the document content, addressing the user's query.
                        """
                        # final_response = Settings.llm.complete(combined_response_prompt).text.strip()
                        final_response = call_vertex_endpoint(combined_response_prompt, max_tokens=500, temperature=0.3)
                        if isinstance(final_response, str):
                            final_response = final_response.strip()

                        if final_response.startswith('"') and final_response.endswith('"'):
                            final_response = final_response[1:-1]

                        print(f"[NO FUNCTION MATCH] Providing document context + staying at current node {current_node_id}")

                        return {
                            "content": final_response,
                            "next_node_id": current_node_id,  # Stay at current node
                            "state_updates": {},
                            "onboarding_status": onboarding_status_to_send
                        }
                        
                except Exception as e:
                    print(f"Error in function match check: {str(e)}")
                    
        full_context = f"""
        The user message is: "{message}"

        The current node ID is: {current_node_id or "None - this is the first message"}

        Current node documentation: {current_node_doc}

        Current Date (The current date in Eastern Time (MM/DD/YYYY)) is: {current_date}

        Previous conversation:
        {conversation_history}

        The session data is:
        {json.dumps(session_data, indent=2)}

        Instructions for matching user response and determining next node:
        1. **Match User Response**: Analyze the user's message '{message}' against the 'FUNCTIONS' section in the current node documentation ('{current_node_doc}').
        2. **Extract Next Node ID**: If the user's response matches a condition in the FUNCTIONS section (e.g., 'If user replied with yes'), extract the corresponding next node ID (e.g., 'node_8').
        3. **Handle No Match**: If no condition matches, set 'next_node_id' to the current node ID ('{current_node_id}') and indicate a need to re-prompt.
        4. **Response Structure**: Return a JSON object with:
        - "next_node_id": The ID of the next node or current node if no match.
        
        Return the response as a JSON object:
        {{
            "next_node_id": "ID of the next node or current node",
      
        }}
        """
            
        
        # Process the response
        try:
            try:
                # response_text = Settings.llm.complete(full_context).text
                response_text = call_vertex_endpoint(full_context, max_tokens=50, temperature=0.0)

                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                response_data = json.loads(response_text)
                print("Successfully parsed function matching response")
                next_node_id = response_data.get("next_node_id", current_node_id)
        
            except Exception as e:
                print(f"Error matching user response to functions: {str(e)}")
                next_node_id = current_node_id
            print(f"Raw LLM response: {response_text}")
            print(f"Matched next node ID: {next_node_id}")
    
            # Retrieve next node documentation
            next_node_doc = ""
            if next_node_id:
                try:
                    retriever = flow_index.as_retriever(
                        filters=MetadataFilters(filters=[
                            MetadataFilter(
                                key="node_id", 
                                value=next_node_id, 
                                operator=FilterOperator.EQ
                            )
                        ])
                    )
                    node_docs = retriever.retrieve(f"NODE ID: {next_node_id}")
                    # print(f"[RETERIVED NODE DOCS FOR {query_str}], {node_docs}")
                    if node_docs:
                        exact_matches = [
                            doc for doc in node_docs 
                            if doc.metadata and doc.metadata.get("node_id") == next_node_id
                        ]
                        if exact_matches:
                            next_node_doc = exact_matches[0].get_content()
                            print(f"Found exact match for next node {next_node_id}")
                        else:
                            next_node_doc = node_docs[0].get_content()
                            print(f"No exact match for next node, using top result")
                    else:
                        print(f"No document found for next node {next_node_id}")
                        next_node_doc = "No specific node instructions available."
                except Exception as e:
                    print(f"Error retrieving next node document: {str(e)}")
                    next_node_doc = "Error retrieving node instructions."
            else:
                next_node_doc = current_node_doc
                print("No next node ID, using current node documentation")

            print(f"[NEXT NODE DOC] {next_node_doc}")

            # Extract instruction from next node documentation
            ai_response = "I'm having trouble processing your request."
            next_doc_functions = False
            if next_node_doc:
                try:
                    instruction_start = next_node_doc.find("INSTRUCTION:") + len("INSTRUCTION:")
                    instruction_end = next_node_doc.find("FUNCTIONS:") if "FUNCTIONS:" in next_node_doc else len(next_node_doc)
                    instruction_text = next_node_doc[instruction_start:instruction_end].strip()
                    ai_response = instruction_text
                    print(f"Extracted instruction: {ai_response[:100]}...")
                    if "FUNCTIONS:" in next_node_doc:
                        functions_start = next_node_doc.find("FUNCTIONS:") + len("FUNCTIONS:")
                        functions_text = next_node_doc[functions_start:].strip()
                        
                        # Set next_doc_functions to True if functions exist and are not empty
                        if functions_text and functions_text.strip():
                            next_doc_functions = True
                            print(f"Functions found: {len(functions_text)} characters, NEXT DOC FUNCTION {next_doc_functions}")
                        else:
                            next_doc_functions = False
                            print("Functions section is empty")
                    else:
                        next_doc_functions = False
                        print("No FUNCTIONS section found")

                except Exception as e:
                    print(f"Error extracting instruction from next node: {str(e)}")
                    ai_response = "No specific instructions available for the next step."


            if calculated_gestational_info:
                ai_response += f" {calculated_gestational_info}"
            # Check if no function match and no progression (e.g., no functions or all unmatched)
            has_functions = False
            if "FUNCTIONS:" in current_node_doc:
                functions_section = current_node_doc.split("FUNCTIONS:")[1]
                # Check if there are any non-empty lines after FUNCTIONS:
                has_functions = any(f.strip() for f in functions_section.split("\n") if f.strip())
            print(f"[HAS FUNCTION] ({has_functions}), Current Node ID : {current_node_id}")

            # Enter fallback if no functions exist
            # print(f"DOCUMENT CONTEXT {document_context}")
            if not has_functions and not is_survey_node and current_node_id is None:
                print("No function match and no progression detected, generating fallback response")
                if document_context_section:
                    print("Using document context for response")
                    fallback_prompt = f"""
                    You are a helpful assistant. The user has sent the following message:
                    
                    The user's last message was: "{message}"

                    Previous conversation:
                    {conversation_history}
                    
                    Relevant Document Content:
                    {document_context_section}
                    
                    INSTRUCTION:
                     INSTRUCTIONS FOR YOUR RESPONSE:
                    1.  **PRIMARY REQUIREMENT**: You MUST first deliver the message provided in "Current Node's Primary Message/Instruction" verbatim or rephrased naturally. This is the essential response for this stage of the conversation.
                    2.  After including the primary message, if the "Relevant Document Content" is present and offers *additional, helpful* information directly related to the user's query or the ongoing conversation (especially if no further flow options exist for this node), integrate it gracefully and naturally.
                    3.  Maintain a natural, conversational, and empathetic tone.
                    4.  Ensure any URLs, phone numbers, email addresses, or specific resources from either the "Current Node's Primary Message/Instruction" or "Relevant Document Content" are included verbatim.
                    
                    Please provide a helpful response based on the document content, addressing the user's query.
                    """
                else:
                    print("No document context available, using general fallback")
                    fallback_prompt = f"""
                    You are a helpful assistant. The user has sent the following message:
                    
                    "{message}"
                    
                    Previous conversation:
                    {conversation_history}
                    
                    I couldn't find specific information to proceed. Please provide a helpful response based on the conversation history.
                    """
                # fallback_response = Settings.llm.complete(fallback_prompt)
                # ai_response = fallback_response.text

                fallback_response_text = call_vertex_endpoint(fallback_prompt, max_tokens=500, temperature=0.3)
                ai_response = fallback_response_text if isinstance(fallback_response_text, str) else str(fallback_response_text)

                print(f"Fallback response generated, length: {len(ai_response)} characters")

            

            print(f'[AI RESPONSE]', ai_response)
            rephrase_prompt = f"""
            You are a friendly, conversational assistant tasked with rephrasing a given text to sound natural, human-like, and context-aware.

            CRITICAL: You must ONLY rephrase the text in 'Original Response': {ai_response}. Do NOT create new content or ask different questions.
            CRITICAL: Do NOT ask any questions that are not in the Original Response {ai_response}
            CRITICAL: Keep ALL content including phone number placeholders like $Clinic_Phone$. 

            Instructions:
            1.  **Rephrase** the 'Original Response' to sound natural and human-like, preserving its exact intent and type (statement or question).
            2.  **Personalize the response:** If the patient's first name is available in 'Patient Profile', use it at the beginning of the response.
            3.  **Subtly incorporate relevant 'Patient History':** Only incorporate 'Patient History' if it directly supports the original response without altering its intent or introducing new questions. If any detail from the 'Patient History' can be seamlessly and non-contradictorily woven into the rephrased 'Original Response' to make it more contextually rich, do so. For example, if the original response is a general greeting and the history mentions a positive pregnancy test, you can add "I see you recently reported a positive pregnancy test." If the original response is a question about a date, you might add, "We have your last reported LMP as [date], would you like to update that?"
            4.  **Maintain the original intent and type:** If the 'Original Response' is a question, the rephrased response MUST be a question. If it's a statement, it MUST be a statement. Do not add new questions or change the core meaning.
            5.  **Crucially: Do NOT contradict or question the 'Original Response'.** Your goal is to enhance it, not to challenge its premise or introduce new, conflicting information.
            6.  **Do NOT** include acknowledgment phrases like 'Okay,' 'Great,' 'I understand,' or 'Let's move on' unless they ar
            7.  If the `Original Response` includes calculated values (e.g., gestational age), preserve them verbatim in the rephrased response.
            8.  **Do NOT** ask for confirmation of previously provided data (e.g., LMP date) unless explicitly instructed by the `Original Response` or node instructions.

            Original Response (from the main LLM, this is the message you must rephrase): "{ai_response}"
            
            User message: "{message}"

            Patient Profile (for personalization, e.g., first_name):
            {patient_fields}

            Patient History (for subtle contextual enrichment, use only if it fits without contradiction):
            {patient_history}

            Return the rephrased response as a string.
            """
            print("Calling secondary LLM for rephrasing")
            # rephrased_response = Settings.llm.complete(rephrase_prompt).text.strip()
            rephrased_response = call_vertex_endpoint(rephrase_prompt, max_tokens=300, temperature=0.3)
            if isinstance(rephrased_response, str):
                rephrased_response = rephrased_response.strip()

            if rephrased_response.startswith('"') and rephrased_response.endswith('"'):
                rephrased_response = rephrased_response[1:-1]
            
            print(f"Rephrased response: {rephrased_response}")
            print(f"AI response length: {len(ai_response)} characters")
            print(f"Next node ID: {next_node_id}")
            print("==== VECTOR CHAT PROCESSING COMPLETE ====\n")
            
            # Check if the next node is a notification node and include all relevant data
            # Check if the next node is a notification node BEFORE setting next_node_id to None
            is_survey_node = "NODE TYPE: surveyNode" in current_node_doc
            is_next_survey_node = next_node_id and "NODE TYPE: surveyNode" in next_node_doc

            if is_survey_node or is_next_survey_node:
                survey_node_id = current_node_id if is_survey_node else next_node_id
                print(f"[SURVEY NODE] Detected survey node: {survey_node_id}")
                return {
                    "content": None,
                    "next_node_id": survey_node_id,  # Return the survey node ID
                    "node_type": "surveyNode",
                    "state_updates": {},
                    "onboarding_status": onboarding_status_to_send
                }

            if next_node_id and "NODE TYPE: notificationNode" in next_node_doc:
                # Extract node data from the instruction section
                node_data = {}
                
                # Parse the notification data from the instruction text
                try:
                    lines = next_node_doc.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith('- Notification Type:'):
                            node_data['messageType'] = line.split(':', 1)[1].strip()
                        elif line.startswith('- Title:'):
                            node_data['title'] = line.split(':', 1)[1].strip()
                        elif line.startswith('- Schedule:'):
                            node_data['scheduleType'] = line.split(':', 1)[1].strip()
                        elif line.startswith('- Assistant ID:'):
                            node_data['assistantId'] = line.split(':', 1)[1].strip()
                        elif line.startswith('INSTRUCTION:'):
                            # Extract the main message from the instruction
                            instruction_text = line.split(':', 1)[1].strip()
                            node_data['message'] = instruction_text
                        elif line.startswith('NODE DATA:'):
                            # Extract and parse the JSON data containing survey questions
                            try:
                                node_data_str = line.split('NODE DATA:', 1)[1].strip()
                                # Find the first JSON object in the node data
                                json_start = node_data_str.find('{')
                                json_end = node_data_str.rfind('}') + 1
                                if json_start >= 0 and json_end > json_start:
                                    parsed_data = json.loads(node_data_str[json_start:json_end])
                                    if 'surveyQuestions' in parsed_data:
                                        node_data['surveyQuestions'] = parsed_data['surveyQuestions']
                            except Exception as e:
                                print(f"Error parsing survey questions: {str(e)}")
                    
                    print(f"[NOTIFICATION NODE] Parsed node data: {node_data}")
                    print(f"[SURVEY QUESTIONS] Found {len(node_data.get('surveyQuestions', []))} questions")
                    
                except Exception as e:
                    print(f"Error parsing notification node data: {str(e)}")
                
                print(f"[NOTIFICATION NODE] Setting next_node_id to None after processing notification")
                return {
                    "content": rephrased_response,
                    "next_node_id": None,  # Set to None for notification nodes
                    "node_type": "notificationNode",
                    "message": node_data.get("message", ""),
                    "notification_type": node_data.get("messageType", "whatsapp"),
                    "title": node_data.get("title", ""),
                    "schedule_type": node_data.get("scheduleType", ""),
                    "scheduled_for": node_data.get("scheduledFor", ""),
                    "assistant_id": node_data.get("assistantId", ""),
                    "survey_questions": node_data.get("surveyQuestions", []),
                    "state_updates": {},
                    "onboarding_status": onboarding_status_to_send
                }
            
            if not next_doc_functions:
                next_node_id = None
                print(f"[END NODE] Setting next_node_id to None - no further progression")
            # For non-notification nodes, return the standard response
            return {
                "content": rephrased_response,
                "next_node_id": next_node_id,
                "state_updates": {},
                "onboarding_status": onboarding_status_to_send
            }

        except Exception as e:
            print(f"ERROR processing vector response: {str(e)}")
            print(f"Response text that failed to parse: {response_text[:200]}...")

            # Fallback to direct LLM response
            print("Using fallback LLM response")
            fallback_prompt = f"""
            You are a helpful assistant. The user has sent the following message:
            
            "{message}"
            
            Previous conversation:
            {conversation_history}
            
            Please provide a helpful response.
            """

            # fallback_response = Settings.llm.complete(fallback_prompt)
            fallback_response_text = call_vertex_endpoint(fallback_prompt, max_tokens=300, temperature=0.3)
            class FallbackResponse:
                def __init__(self, text):
                    self.text = text
            fallback_response = FallbackResponse(fallback_response_text if isinstance(fallback_response_text, str) else str(fallback_response_text))

            print(f"Fallback response generated, length: {len(fallback_response.text)} characters")
            print("==== VECTOR CHAT PROCESSING COMPLETE (FALLBACK) ====\n")

            return {
                "content": fallback_response.text,
                "error": f"Vector processing failed: {str(e)}",
                "fallback": True
            }

    except Exception as e:
        print(f"CRITICAL ERROR in vector_chat: {str(e)}")
        traceback_str = traceback.format_exc()
        print(f"Traceback: {traceback_str}")
        print("==== VECTOR CHAT PROCESSING FAILED ====\n")
        return {
            "error": f"Failed to process message: {str(e)}",
            "content": "I'm having trouble processing your request. Please try again later."
        }


# @app.post("/api/shared/vector_chat")
# async def vector_flow_chat(request: dict):
#     """
#     Process a chat message using the vector-based flow knowledge index.
#     This endpoint doesn't rely on Firestore or Gemini services.
#     """
#     import traceback
#     import json
#     from datetime import datetime
#     from llama_index.core import VectorStoreIndex, StorageContext
#     from llama_index.vector_stores.chroma import ChromaVectorStore
#     from llama_index.retrievers.bm25 import BM25Retriever
#     from langdetect import detect, DetectorFactory
#     from langdetect.lang_detect_exception import LangDetectException

#     eastern = pytz.timezone('America/New_York')
#     current_time = datetime.now(eastern)
#     current_date = current_time.date().strftime('%m/%d/%Y')
#     print(f"[CURRENT DATE] {current_date}")
#     try:
#         print("\n==== STARTING VECTOR CHAT PROCESSING ====")
#         message = request.get("message", "")
#         sessionId = request.get("sessionId", "")
#         flow_id = request.get("flow_id")
#         assistant_id = request.get("assistantId")
#         session_data = request.get("session_data", {})
#         previous_messages = request.get("previous_messages", [])
#         patientId = request.get("patientId", "")
#         patient_history = request.get("patient_history", "")  # New: Extract patient history
#         print(f"[PATIENT HISTORY] {patient_history}")
#         onboarding_status_from_session = session_data.get("onboardingStatus") # Use .get() for safety
#         print(f"[ONBOARDING STATUS], {onboarding_status_from_session}")
#         Onboarding = None
#         print(f"Message: '{message}'")
#         print(f"Session ID: {sessionId}")
#         print(f"Flow ID: {flow_id}")
#         print(f"Assistant ID: {assistant_id}")
#         print(f"Session data: {json.dumps(session_data, indent=2)}")
#         print(f"Number of previous messages: {len(previous_messages)}")
#         print(f"previous messages",previous_messages )
#         # Add after retrieving session data
#         is_new_session = not session_data.get('currentNodeId') and len(previous_messages) <= 6
#         print(f"Is likely new session: {is_new_session}")
#         print(f"session data {session_data}")
#         current_node_id = session_data.get('currentNodeId')
#         current_node_doc = ""
#         print(f"Current node ID: {current_node_id}")
#         survey_questions_length = session_data.get('survey_questions_length', 0)
#         user_message_count = sum(1 for msg in previous_messages if msg.get("role") == "user")
#         is_post_survey_start = (current_node_id is None and 
#                             user_message_count >= survey_questions_length and 
#                             survey_questions_length > 0)
#         common_greetings = ['hi', 'hello', 'hey', 'good', 'morning', 'afternoon', 'evening']

#         print(f"[CHAT] Survey questions length: {survey_questions_length}")
#         print(f"[CHAT] User message count: {user_message_count}")
#         print(f"[CHAT] Is post-survey start: {is_post_survey_start}")

        
        
#         # Try to get starting node info from app state if available
#         if hasattr(app.state, 'starting_node_ids') and flow_id in getattr(app.state, 'starting_node_ids', {}):
#             print(f"Cached starting node for flow {flow_id}: {app.state.starting_node_ids[flow_id]}")
#         else:
#             print("No cached starting node info available")
            
#         if not flow_id:
#             print("ERROR: flow_id is required")
#             return {
#                 "error": "flow_id is required",
#                 "content": "Missing required parameters"
#             }
        
#         # Load flow index
#         if flow_id not in app.state.flow_indices:
#             bucket = storage_client.bucket(BUCKET_NAME)
#             meta_file = f"temp_flow_{flow_id}_meta.pkl"
#             blob = bucket.blob(f"flow_metadata/{flow_id}_meta.pkl")
#             try:
#                 blob.download_to_filename(meta_file)
#                 with open(meta_file, "rb") as f:
#                     metadata = pickle.load(f)
#                 os.remove(meta_file)
#             except Exception as e:
#                 print(f"Failed to load flow index metadata from GCS: {str(e)}")
#                 return {
#                     "error": "Flow knowledge index not found. Please index the flow first.",
#                     "content": "I'm having trouble processing your request."
#                 }

#             temp_dir = f"temp_flow_{flow_id}"
#             os.makedirs(temp_dir, exist_ok=True)
#             for blob in bucket.list_blobs(prefix=f"flow_indices/{flow_id}/"):
#                 local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
#                 blob.download_to_filename(local_path)

#             collection_name = metadata["collection_name"]
#             print("DEBUG: Entering Chroma collection block")
#             try:
#                 chroma_collection = chroma_client.get_collection(collection_name)
#                 print(f"Found existing Chroma collection {collection_name}")
#             except chromadb.errors.InvalidCollectionException:
#                 print(f"Creating new Chroma collection {collection_name}")
#                 chroma_collection = chroma_client.create_collection(collection_name)
#             vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

#             storage_context = StorageContext.from_defaults(
#                 persist_dir=temp_dir, vector_store=vector_store
#             )
#             flow_index = load_index_from_storage(storage_context)
#             app.state.flow_indices[flow_id] = flow_index
#             shutil.rmtree(temp_dir)
#         else:
#             flow_index = app.state.flow_indices[flow_id]
#             print('Flow Data', flow_index)
#             print(f"[CHAT] Using cached flow index for flow_id: {flow_id}")

        
#         patient = db.query(Patient).filter(Patient.id == patientId).first()
#         if not patient:
#             raise HTTPException(status_code=404, detail="Patient not found")
#         patient_dict = {
#             "id": patient.id,
#             "mrn": patient.mrn,
#             "first_name": patient.first_name,
#             "last_name": patient.last_name,
#             "date_of_birth": patient.date_of_birth,
#             "gender": patient.gender,

#         }
#         patient_fields = json.dumps(patient_dict, indent=2)
#         required_fields = ["first_name", "last_name", "date_of_birth"]
#         missing_fields = []
#         for field in required_fields:
#             value = getattr(patient, field, None)
#             if not value or (isinstance(value, str) and not value.strip()):
#                 missing_fields.append(field)


#         print(f"[MISSING FIELDS], {missing_fields}")
#         print(f"[PATIENT FIELDS], {patient_fields}")

#         onboarding_status_to_send = "in_progress" # Default to in_progress
#         if not missing_fields:
#                 onboarding_status_to_send = "completed"

        
#         if missing_fields: 
#             print("==== PATIENT ONBOARDING/CHAT START ====\n")
#             # Direct approach - no LLM needed
#             import re

#             # Determine which field to ask for (first missing field)
#             field_to_ask = missing_fields[0]

#             # Check if user provided information for the current missing field
#             database_operation = None
#             content = ""

#             if field_to_ask == "first_name":
#                 # Filter out common greetings and check if this is a greeting/start message
#                 common_greetings = ['hi', 'hello', 'hey', 'good', 'morning', 'afternoon', 'evening']
#                 message_lower = message.strip().lower()
                
#                 # If it's a greeting or very short, ask for name instead of extracting
#                 if message_lower in common_greetings or len(message.strip()) < 2:
#                     content = "Hey, nice to hear from you! I need a bit of info to get you set up. Could you share your first name?"
#                 else:
#                     # Try to extract name from non-greeting messages
#                     name_match = re.search(r'\b([A-Za-z]{2,})\b', message.strip())
#                     if name_match:
#                         extracted_name = name_match.group(1).lower()
#                         database_operation = {
#                             "operation": "UPDATE_PATIENT",
#                             "parameters": {
#                                 "patient_id": patientId,
#                                 "field_name": "first_name",
#                                 "field_value": extracted_name
#                             }
#                         }
#                         content = f"Great! I've got your first name as {extracted_name.title()}. Now I need your last name."
#                     else:
#                         content = "I need your first name. Could you please share it?"

#             elif field_to_ask == "last_name":
#                 name_match = re.search(r'\b([A-Za-z]+)\b', message.strip())
#                 if name_match:
#                     extracted_name = name_match.group(1).lower()
#                     database_operation = {
#                         "operation": "UPDATE_PATIENT",
#                         "parameters": {
#                             "patient_id": patientId,
#                             "field_name": "last_name",
#                             "field_value": extracted_name
#                         }
#                     }
#                     content = f"Perfect! Last name recorded as {extracted_name.title()}. What's your date of birth? Please use format MM/DD/YYYY like 03/29/1996."
#                 else:
#                     content = "I need your last name. Could you please share it?"

#             elif field_to_ask == "date_of_birth":
#                 date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', message.strip())
#                 if date_match:
#                     month, day, year = date_match.groups()
#                     formatted_date = f"{month.zfill(2)}/{day.zfill(2)}/{year}"
#                     try:
#                         parsed_date = datetime.strptime(formatted_date, "%m/%d/%Y")
#                         current_datetime = datetime.strptime(current_date, "%m/%d/%Y")
                        
#                         if parsed_date <= current_datetime:
#                             database_operation = {
#                                 "operation": "UPDATE_PATIENT",
#                                 "parameters": {
#                                     "patient_id": patientId,
#                                     "field_name": "date_of_birth",
#                                     "field_value": formatted_date
#                                 }
#                             }
#                             content = f"Perfect! Thanks for providing your information. Your profile is now complete and please say 'Hi' To Get started."
#                         else:
#                             content = "That date seems to be in the future. Could you please provide a valid date of birth in MM/DD/YYYY format?"
#                     except ValueError:
#                         content = "I couldn't understand that date format. Could you please use MM/DD/YYYY format like 03/29/1996?"
#                 else:
#                     content = "I need your date of birth. Please use the format MM/DD/YYYY, like 03/29/1996."

#             next_node_id = None
#             state_updates = {}

#             operation_result = None
#             if database_operation:
#                 operation = database_operation.get("operation")
#                 parameters = database_operation.get("parameters", {})
#                 try:
#                     if operation == "UPDATE_PATIENT":
#                         patient = db.query(Patient).filter(Patient.id == patientId).first()
#                         if not patient:
#                             raise HTTPException(status_code=404, detail="Patient not found")
#                         setattr(patient, parameters["field_name"], parameters["field_value"])
#                         patient.updated_at = datetime.utcnow()
#                         db.commit()
#                         db.refresh(patient)
#                         operation_result = {
#                             "id": patient.id,
#                             "mrn": patient.mrn,
#                             "first_name": patient.first_name,
#                             "last_name": patient.last_name,
#                             "date_of_birth": patient.date_of_birth,
#                             "phone": patient.phone,
#                             "organization_id": patient.organization_id
#                         }
#                         # Update JSON file
#                         patient_path = f"patients/{patient.id}.json"
#                         os.makedirs(os.path.dirname(patient_path), exist_ok=True)
#                         with open(patient_path, "w") as f:
#                             patient_dict = {
#                                 "id": patient.id,
#                                 "mrn": patient.mrn,
#                                 "first_name": patient.first_name,
#                                 "last_name": patient.last_name,
#                                 "date_of_birth": patient.date_of_birth,
#                                 "phone": patient.phone,
#                                 "organization_id": patient.organization_id,
#                                 "created_at": patient.created_at.isoformat() if patient.created_at else None,
#                                 "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
#                             }
#                             json.dump(patient_dict, f, indent=2)
#                         content += f"\nProfile updated successfully!"
#                         missing_fields = []
#                         for field in required_fields:
#                             value = getattr(patient, field, None)
#                             if not value or (isinstance(value, str) and not value.strip()):
#                                 missing_fields.append(field)
                        
#                         # Update onboarding status based on recalculated missing fields
#                         if not missing_fields:
#                             onboarding_status_to_send = "completed"
#                             print(f"🎉 ONBOARDING COMPLETE! All required fields now filled.")
#                         else:
#                             print(f"Still missing fields after UPDATE: {missing_fields}")
#                             # onboarding_status_to_send stays "in_progress"
#                         starting_node_id, starting_node_doc = get_starting_node(flow_index)
#                         print(f"[STARTING NODE, FROM UPDATE] {starting_node_id, starting_node_doc}")
#                         if starting_node_id:
#                             current_node_id = starting_node_id
#                             current_node_doc = starting_node_doc
                
#                     elif operation == "CREATE_PATIENT":
#                         # Fallback if patientId is invalid; use session_data for phone/organization_id
#                         mrn = generate_mrn()
#                         patient = Patient(
#                             id=str(uuid.uuid4()),
#                             mrn=mrn,
#                             first_name=parameters.get("first_name", ""),
#                             last_name=parameters.get("last_name", ""),
#                             date_of_birth=parameters.get("date_of_birth"),
#                             phone=session_data.get("phone", "unknown"),
#                             organization_id=session_data.get("organization_id", "default_org"),
#                             created_at=datetime.utcnow(),
#                             updated_at=datetime.utcnow()
#                         )
#                         db.add(patient)
#                         db.commit()
#                         db.refresh(patient)
#                         operation_result = {
#                             "id": patient.id,
#                             "mrn": patient.mrn,
#                             "first_name": patient.first_name,
#                             "last_name": patient.last_name,
#                             "date_of_birth": patient.date_of_birth,
#                             "phone": patient.phone,
#                             "organization_id": patient.organization_id
#                         }
#                         # Save JSON file
#                         patient_path = f"patients/{patient.id}.json"
#                         os.makedirs(os.path.dirname(patient_path), exist_ok=True)
#                         with open(patient_path, "w") as f:
#                             patient_dict = {
#                                 "id": patient.id,
#                                 "mrn": patient.mrn,
#                                 "first_name": patient.first_name,
#                                 "last_name": patient.last_name,
#                                 "date_of_birth": patient.date_of_birth,
#                                 "phone": patient.phone,
#                                 "organization_id": patient.organization_id,
#                                 "created_at": patient.created_at.isoformat() if patient.created_at else None,
#                                 "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
#                             }
#                             json.dump(patient_dict, f, indent=2)
#                         content += f"\nProfile created successfully!"
#                         missing_fields = []
#                         for field in required_fields:
#                             value = getattr(patient, field, None)
#                             if not value or (isinstance(value, str) and not value.strip()):
#                                 missing_fields.append(field)
                        
#                         # Update onboarding status based on recalculated missing fields
#                         if not missing_fields:
#                             onboarding_status_to_send = "completed"
#                             print(f"🎉 ONBOARDING COMPLETE! All required fields now filled.")
#                         else:
#                             print(f"Still missing fields after update: {missing_fields}")
#                             # onboarding_status_to_send stays "in_progress"
#                         starting_node_id, starting_node_doc = get_starting_node(flow_index)
#                         print(f"[STARTING NODE] {starting_node_id, starting_node_doc}")
#                         if starting_node_id:
#                             current_node_id = starting_node_id
#                             current_node_doc = starting_node_doc
                
#                 except Exception as e:
#                     db.rollback()
#                     print(f"Database operation failed: {str(e)}")
#                     content += f"\nSorry, I couldn’t update your profile. Let’s try again."
#                     response_data["next_node_id"] = current_node_id

#             print(f"Response: {content}")
#             print(f"Next node ID: {next_node_id}")
#             print("==== PATIENT ONBOARDING/CHAT COMPLETE ====\n")
        
#             response = {
#                 "content": content,
#                 "next_node_id": current_node_id,
#                 "state_updates": state_updates,
#                 "onboarding_status": onboarding_status_to_send 
#             }
#             if operation_result:
#                 response["operation_result"] = operation_result
#             return response
        
      
#         # Format previous messages for better context
#         conversation_history = ""
#         if is_post_survey_start:
#             print("[CHAT] Excluding survey messages from conversation history")
#             # Only include non-survey messages (after survey completion)
#             message = 'hi'
#             conversation_history = ""
#             # for msg in previous_messages[user_message_count * 2:]:  # Skip survey Q&A pairs
#             #     role = msg.get("role", "unknown")
#             #     content = msg.get("content", "")
#             #     conversation_history += f"{role}: {content}\n"

#         else:
#             # Include all messages for ongoing conversation
#             for msg in previous_messages:
#                 role = msg.get("role", "unknown")
#                 content = msg.get("content", "")
#                 conversation_history += f"{role}: {content}\n"
#         print("conversation history", conversation_history, message)
        

#         if not session_data.get("currentNodeId") and not previous_messages:  # New session
#             starting_node_id, starting_node_doc = get_starting_node(flow_index)
#             print(f"[STARTING NODE] {starting_node_id, starting_node_doc}")
#             if starting_node_id:
#                 current_node_id = starting_node_id
#                 current_node_doc = starting_node_doc
                
#         #Special Case For the Survey Node
#         if message.lower().strip() == 'completed survey' and current_node_id:
#             try:
#                 retriever = flow_index.as_retriever(
#                     filters=MetadataFilters(filters=[
#                         MetadataFilter(
#                             key="node_id", 
#                             value=current_node_id, 
#                             operator=FilterOperator.EQ
#                         )
#                     ])
#                 )
#                 node_docs = retriever.retrieve(f"NODE ID: {current_node_id}")
                
#                 if node_docs:
#                     current_node_content = node_docs[0].get_content()
#                     is_current_survey_node = "NODE TYPE: surveyNode" in current_node_content
                    
#                     if is_current_survey_node:
#                         print(f"[SURVEY COMPLETION] Detected 'completed' message on survey node {current_node_id}")
                        
#                         # Check for completion trigger in TRIGGERS section
#                         if "TRIGGERS:" in current_node_content:
#                             triggers_section = current_node_content.split("TRIGGERS:")[1].strip()
                            
#                             import re
#                             completion_match = re.search(r"If survey outcome is ['\"]?Completed['\"]?, proceed to node (\w+)", triggers_section)
                            
#                             if completion_match:
#                                 current_node_id = completion_match.group(1)
#                                 print(f"[SURVEY COMPLETION] Setting current_node_id to: {current_node_id}")
#                             else:
#                                 print(f"[SURVEY COMPLETION] No completion trigger found, returning completion message")
#                                 return {
#                                     "content": "Thanks for filling out the survey, is there anything you need help with?",
#                                     "next_node_id": None,
#                                     "state_updates": {},
#                                     "onboarding_status": onboarding_status_to_send
#                                 }
#                         else:
#                             print(f"[SURVEY COMPLETION] No TRIGGERS section found, returning completion message")
#                             return {
#                                 "content": "Thanks for filling out the survey, is there anything you need help with?",
#                                 "next_node_id": None,
#                                 "state_updates": {},
#                                 "onboarding_status": onboarding_status_to_send
#                             }
#             except Exception as e:
#                 print(f"[SURVEY COMPLETION] Error checking survey completion: {str(e)}")

#         # Basic String Query Approach - No Filters
#         if current_node_id:
#             try:
#                 # Create basic retriever with no filters
#                 # retriever = flow_index.as_retriever(similarity_top_k=10)
                
#                 # # Query directly for the node ID as text
#                 # query_str = f"NODE ID: {current_node_id}"
#                 # print(f"Querying for: '{query_str}'")
                
#                 # # Use the most basic retrieval pattern
#                 # node_docs = retriever.retrieve(query_str)
                
#                 retriever = flow_index.as_retriever(
#                     filters=MetadataFilters(filters=[
#                         MetadataFilter(
#                             key="node_id", 
#                             value=current_node_id, 
#                             operator=FilterOperator.EQ
#                         )
#                     ])
#                 )
                
#                 # Query for the node - the filter ensures we only get exact matches
#                 query_str = f"NODE ID: {current_node_id}"
#                 print(f"Querying for: '{query_str}' with metadata filter")
                
#                 node_docs = retriever.retrieve(query_str)
#                 # Check if we got any results
#                 if node_docs:
#                     # Find exact match for node_id in results
#                     exact_matches = [
#                         doc for doc in node_docs 
#                         if doc.metadata and doc.metadata.get("node_id") == current_node_id
#                     ]
                    
#                     if exact_matches:
#                         current_node_doc = exact_matches[0].get_content()
#                         print(f"Found exact match for node {current_node_id}")
#                     else:
#                         # Just use the top result
#                         current_node_doc = node_docs[0].get_content()
#                         print(f"No exact match, using top result")
                    
#                     print(f"Retrieved document for node {current_node_id}: {current_node_doc[:100]}...")
#                 else:
#                     print(f"No document found for node {current_node_id}")
#                     current_node_doc = "No specific node instructions available."
#             except Exception as e:
#                 print(f"Error retrieving node document: {str(e)}")
#                 try:
#                     print("Falling back to similarity search approach")
#                     retriever = flow_index.as_retriever(similarity_top_k=1000)  # Use high number as fallback
#                     query_str = f"NODE ID: {current_node_id}"
#                     node_docs = retriever.retrieve(query_str)
                    
#                     if node_docs:
#                         exact_matches = [
#                             doc for doc in node_docs 
#                             if doc.metadata and doc.metadata.get("node_id") == current_node_id
#                         ]
                        
#                         if exact_matches:
#                             current_node_doc = exact_matches[0].get_content()
#                             print(f"Found exact match for node {current_node_id} using fallback")
#                         else:
#                             current_node_doc = node_docs[0].get_content()
#                             print(f"No exact match, using top result from fallback")
#                     else:
#                         current_node_doc = "No specific node instructions available."
#                 except Exception as fallback_e:
#                     print(f"Fallback approach also failed: {str(fallback_e)}")
#                     current_node_doc = "Error retrieving node instructions"
                    
#         print(f"[CURRENT NODE DOC] {current_node_doc}")
#         # Check if last assistant message asked about LMP and current message is a date
#         calculated_gestational_info = ""
#         if previous_messages and len(previous_messages) >= 1:
#             last_assistant_msg = None
#             for msg in reversed(previous_messages):
#                 if msg.get("role") == "assistant":
#                     last_assistant_msg = msg.get("content", "").lower()
#                     break
            
#             if last_assistant_msg and any(keyword in last_assistant_msg for keyword in ["lmp", "mm/dd/yyyy", "gestational age",]):
#                 try:
#                     from datetime import datetime
#                     import re
                    
#                     # Check if current message is a date
#                     date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
#                     match = re.search(date_pattern, message.strip())
                    
#                     if match:
#                         month, day, year = match.groups()
#                         try:
#                             parsed_lmp = datetime.strptime(f"{month.zfill(2)}/{day.zfill(2)}/{year}", "%m/%d/%Y")
#                             current_datetime = datetime.strptime(current_date, "%m/%d/%Y")
                            
#                             if parsed_lmp <= current_datetime:
#                                 days_diff = (current_datetime - parsed_lmp).days
#                                 weeks = min(days_diff // 7, 40)
                                
#                                 if weeks <= 12:
#                                     trimester = "first"
#                                 elif weeks <= 27:
#                                     trimester = "second"
#                                 else:
#                                     trimester = "third"
                                
#                                 calculated_gestational_info = f"CALCULATED GESTATIONAL AGE FOR USER: Based on LMP {message.strip()}, the patient is {weeks} weeks pregnant and in the {trimester} trimester."
#                                 print(f"[MANUAL CALCULATION] {calculated_gestational_info}")
#                         except ValueError:
#                             pass
#                 except Exception as e:
#                     print(f"Error in manual gestational age calculation: {e}")
        
#             if last_assistant_msg and any(keyword in last_assistant_msg for keyword in ["due date", "estimated due date"]):
#                 try:
#                     from datetime import datetime
#                     import re
#                     from datetime import timedelta
                    
#                     # Check if current message is a date
#                     date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
#                     match = re.search(date_pattern, message.strip())
                    
#                     if match:
#                         month, day, year = match.groups()
#                         try:
#                             parsed_edd = datetime.strptime(f"{month.zfill(2)}/{day.zfill(2)}/{year}", "%m/%d/%Y")
#                             current_datetime = datetime.strptime(current_date, "%m/%d/%Y")
                            
#                             if parsed_edd >= current_datetime:
#                                 days_until_due = (parsed_edd - current_datetime).days
#                                 weeks_pregnant = max(0, (280 - days_until_due) // 7)  # 280 days = 40 weeks total pregnancy
                                
#                                 if weeks_pregnant < 4 or weeks_pregnant > 42:
#                                     calculated_gestational_info = "The estimated due date doesn't seem right. Please check and provide a valid due date in MM/DD/YYYY format."
#                                 else:
#                                     if weeks_pregnant <= 12:
#                                         trimester = "first"
#                                     elif weeks_pregnant <= 27:
#                                         trimester = "second"
#                                     else:
#                                         trimester = "third"
                                    
#                                     calculated_gestational_info = f"CALCULATED GESTATIONAL AGE FOR USER: Based on Estimated Due Date {message.strip()}, the patient is {weeks_pregnant} weeks pregnant in the {trimester} trimester."
#                                     print(f"[MANUAL CALCULATION] {calculated_gestational_info}")
#                             else:
#                                 calculated_gestational_info = "The estimated due date is in the past. Please provide a valid future date in MM/DD/YYYY format."
#                         except ValueError:
#                             calculated_gestational_info = "I couldn't understand that date format. Please use MM/DD/YYYY format, like 10/05/2025."
#                 except Exception as e:
#                     print(f"Error in manual gestational age calculation (EDD): {e}")
        
#         print(f"[CALCULATED GESTATIONAL INFO] {calculated_gestational_info}")

#         print(f"[DETECTED NODE] {current_node_id, current_node_doc}")
#         # Load document index (optional)
#         document_retriever = None
#         document_context = ""
#         if assistant_id:
#             if assistant_id not in app.state.document_indexes:
#                 bucket = storage_client.bucket(BUCKET_NAME)
#                 meta_file = f"temp_doc_{assistant_id}_meta.pkl"
#                 blob = bucket.blob(f"document_metadata/{assistant_id}_meta.pkl")
#                 try:
#                     blob.download_to_filename(meta_file)
#                     with open(meta_file, "rb") as f:
#                         metadata = pickle.load(f)
#                     os.remove(meta_file)

#                     temp_dir = f"temp_doc_{assistant_id}"
#                     os.makedirs(temp_dir, exist_ok=True)
#                     for blob in bucket.list_blobs(prefix=f"document_indices/{assistant_id}/"):
#                         local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
#                         blob.download_to_filename(local_path)

#                     collection_name = metadata["collection_name"]
#                     print("DEBUG: Entering Chroma collection block for documents")
#                     try:
#                         chroma_collection = chroma_client.get_collection(collection_name)
#                         print(f"Found existing Chroma collection {collection_name} for document index")
#                     except chromadb.errors.InvalidCollectionException:
#                         print(f"Creating new Chroma collection {collection_name} for document index")
#                         chroma_collection = chroma_client.create_collection(collection_name)
#                     vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

#                     storage_context = StorageContext.from_defaults(
#                         persist_dir=temp_dir, vector_store=vector_store
#                     )
#                     document_index = load_index_from_storage(storage_context)
#                     document_retriever = document_index.as_retriever(similarity_top_k=20)
#                     app.state.document_indexes[assistant_id] = {
#                         "index": document_index,
#                         "retriever": document_retriever,
#                         "created_at": metadata["created_at"],
#                         "document_count": metadata["document_count"],
#                         "node_count": metadata["node_count"]
#                     }
#                     shutil.rmtree(temp_dir)
#                 except Exception as e:
#                     print(f"Document index not found or failed to load: {str(e)}")
#             else:
#                 document_retriever = app.state.document_indexes[assistant_id]["retriever"]

#         if document_retriever:
#             print(f"Retrieving documents for query: '{message}'")
#             retrieved_nodes = document_retriever.retrieve(message)
#             document_text = ""
#             if retrieved_nodes:
#                 try:
#                     node_objs = [n.node for n in retrieved_nodes]
#                     if len(node_objs) > 1:
#                         print(f"Applying BM25 reranking to {len(node_objs)} nodes")
#                         bm25_retriever = BM25Retriever.from_defaults(
#                             nodes=node_objs, 
#                             similarity_top_k=min(5, len(node_objs))
#                         )
#                         reranked_nodes = bm25_retriever.retrieve(message)
#                         document_text = "\n\n".join([n.node.get_content() for n in reranked_nodes])
#                     else:
#                         document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#                 except Exception as e:
#                     print(f"BM25 reranking failed: {str(e)}, using vector results")
#                     document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#             document_context = f"Relevant Document Content:\n{document_text}" if document_text else ""
#             print(f"Document retrieval complete, found content with {len(document_context)} characters")
#         else:
#             print("No document retriever available, proceeding without document context")


#         is_survey_node = "NODE TYPE: surveyNode" in current_node_doc
#         # Define context section
#         document_context_section = f"""
#             Relevant Document Content:
#             {document_context}

#             You are a helpful assistant tasked with providing accurate, specific, and context-aware responses. Follow these steps:
#             1. Identify the user's intent from the message and conversation history.
#             2. **IMPORTANT**: Scan the Relevant Document Content for any URLs, phone numbers, email addresses, or other specific resources.
#             3. **CRITICAL REQUIREMENT**: If ANY resources like URLs, phone numbers, or contact information are found, include them verbatim in your response.
#             4. Generate a natural, conversational response addressing the user's query, incorporating document content as needed.
#             5. Maintain continuity with the conversation history.
#             6. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION, but prioritize document content for specific details.
#             7. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
#             8. If no relevant document content is found, provide a helpful response based on the flow logic or general knowledge.
#             9. Double-check that all resource links, phone numbers, and contact methods from the document context are included.
#             """ if document_context else """
#             You are a helpful assistant tasked with providing accurate and context-aware responses. Follow these steps:
#             1. Identify the user's intent from the message and conversation history.
#             2. Generate a natural, conversational response addressing the user's query.
#             3. Maintain continuity with the conversation history.
#             4. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION.
#             5. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
#             """

#         # Check if user message doesn't match current node functions and provide document context response
#         if current_node_id and current_node_doc and document_context and message.lower().strip() not in common_greetings:
#             # Check if current node has functions
#             if "FUNCTIONS:" in current_node_doc:
#                 # Check if user message matches any function
#                 function_match_prompt = f"""
#                 User message: "{message}"
#                 Current node functions: {current_node_doc.split("FUNCTIONS:")[1] if "FUNCTIONS:" in current_node_doc else "None"}
                
#                 Does the user's message match any of the functions/conditions listed? 
#                 Return only "MATCH" or "NO_MATCH"
#                 """
                
#                 try:
#                     match_response = Settings.llm.complete(function_match_prompt).text.strip()
#                     print(f"[FUNCTION MATCH CHECK] {match_response}")
                    
#                     if "NO_MATCH" in match_response.upper():
#                         # User message doesn't match functions, provide document context + current node instruction
                        
#                         # Extract current node instruction
#                         current_instruction = ""
#                         try:
#                             instruction_start = current_node_doc.find("INSTRUCTION:") + len("INSTRUCTION:")
#                             instruction_end = current_node_doc.find("FUNCTIONS:") if "FUNCTIONS:" in current_node_doc else len(current_node_doc)
#                             current_instruction = current_node_doc[instruction_start:instruction_end].strip()
#                         except Exception as e:
#                             print(f"Error extracting current instruction: {str(e)}")
                        
#                         # Generate combined response from document context + current node instruction
#                         combined_response_prompt = f"""
#                         You are a helpful assistant. The user has sent the following message:
                        
#                         The user's last message was: "{message}"
                        
#                         Relevant Document Content:
#                         {document_context_section}
                        
#                         INSTRUCTION:
#                         INSTRUCTIONS FOR YOUR RESPONSE:
#                         1.  **PRIMARY REQUIREMENT**: You MUST first deliver the message provided in "Current Node's Primary Message/Instruction" verbatim or rephrased naturally. This is the essential response for this stage of the conversation.
#                         2.  After including the primary message, if the "Relevant Document Content" is present and offers *additional, helpful* information directly related to the user's query or the ongoing conversation (especially if no further flow options exist for this node), integrate it gracefully and naturally.
#                         3.  Maintain a natural, conversational, and empathetic tone.
#                         4.  Ensure any URLs, phone numbers, email addresses, or specific resources from either the "Current Node's Primary Message/Instruction" or "Relevant Document Content" are included verbatim.
                        
#                         MUST Format your response like this:
#                         "The Information you are asking for is this: [specific detailed answer from document context including any medications, dosages, recommendations, etc.] + Okay Now, {current_instruction}" 
                        
#                         Please provide a helpful response based on the document content, addressing the user's query.
#                         """
#                         final_response = Settings.llm.complete(combined_response_prompt).text.strip()
#                         if final_response.startswith('"') and final_response.endswith('"'):
#                             final_response = final_response[1:-1]

#                         print(f"[NO FUNCTION MATCH] Providing document context + staying at current node {current_node_id}")

#                         return {
#                             "content": final_response,
#                             "next_node_id": current_node_id,  # Stay at current node
#                             "state_updates": {},
#                             "onboarding_status": onboarding_status_to_send
#                         }
                        
#                 except Exception as e:
#                     print(f"Error in function match check: {str(e)}")
                    
#         full_context = f"""
#         The user message is: "{message}"

#         The current node ID is: {current_node_id or "None - this is the first message"}

#         Current node documentation: {current_node_doc}

#         Current Date (The current date in Eastern Time (MM/DD/YYYY)) is: {current_date}

#         Previous conversation:
#         {conversation_history}

#         The session data is:
#         {json.dumps(session_data, indent=2)}

#         Instructions for matching user response and determining next node:
#         1. **Match User Response**: Analyze the user's message '{message}' against the 'FUNCTIONS' section in the current node documentation ('{current_node_doc}').
#         2. **Extract Next Node ID**: If the user's response matches a condition in the FUNCTIONS section (e.g., 'If user replied with yes'), extract the corresponding next node ID (e.g., 'node_8').
#         3. **Handle No Match**: If no condition matches, set 'next_node_id' to the current node ID ('{current_node_id}') and indicate a need to re-prompt.
#         4. **Response Structure**: Return a JSON object with:
#         - "next_node_id": The ID of the next node or current node if no match.
        
#         Return the response as a JSON object:
#         {{
#             "next_node_id": "ID of the next node or current node",
      
#         }}
#         """
            
        
#         # Process the response
#         try:
#             try:
#                 response_text = Settings.llm.complete(full_context).text
#                 if "```json" in response_text:
#                     response_text = response_text.split("```json")[1].split("```")[0].strip()
#                 response_data = json.loads(response_text)
#                 print("Successfully parsed function matching response")
#                 next_node_id = response_data.get("next_node_id", current_node_id)
        
#             except Exception as e:
#                 print(f"Error matching user response to functions: {str(e)}")
#                 next_node_id = current_node_id
#             print(f"Raw LLM response: {response_text}")
#             print(f"Matched next node ID: {next_node_id}")
    
#             # Retrieve next node documentation
#             next_node_doc = ""
#             if next_node_id:
#                 try:
#                     retriever = flow_index.as_retriever(
#                         filters=MetadataFilters(filters=[
#                             MetadataFilter(
#                                 key="node_id", 
#                                 value=next_node_id, 
#                                 operator=FilterOperator.EQ
#                             )
#                         ])
#                     )
#                     node_docs = retriever.retrieve(f"NODE ID: {next_node_id}")
#                     # print(f"[RETERIVED NODE DOCS FOR {query_str}], {node_docs}")
#                     if node_docs:
#                         exact_matches = [
#                             doc for doc in node_docs 
#                             if doc.metadata and doc.metadata.get("node_id") == next_node_id
#                         ]
#                         if exact_matches:
#                             next_node_doc = exact_matches[0].get_content()
#                             print(f"Found exact match for next node {next_node_id}")
#                         else:
#                             next_node_doc = node_docs[0].get_content()
#                             print(f"No exact match for next node, using top result")
#                     else:
#                         print(f"No document found for next node {next_node_id}")
#                         next_node_doc = "No specific node instructions available."
#                 except Exception as e:
#                     print(f"Error retrieving next node document: {str(e)}")
#                     next_node_doc = "Error retrieving node instructions."
#             else:
#                 next_node_doc = current_node_doc
#                 print("No next node ID, using current node documentation")

#             print(f"[NEXT NODE DOC] {next_node_doc}")

#             # Extract instruction from next node documentation
#             ai_response = "I'm having trouble processing your request."
#             next_doc_functions = False
#             if next_node_doc:
#                 try:
#                     instruction_start = next_node_doc.find("INSTRUCTION:") + len("INSTRUCTION:")
#                     instruction_end = next_node_doc.find("FUNCTIONS:") if "FUNCTIONS:" in next_node_doc else len(next_node_doc)
#                     instruction_text = next_node_doc[instruction_start:instruction_end].strip()
#                     ai_response = instruction_text
#                     print(f"Extracted instruction: {ai_response[:100]}...")
#                     if "FUNCTIONS:" in next_node_doc:
#                         functions_start = next_node_doc.find("FUNCTIONS:") + len("FUNCTIONS:")
#                         functions_text = next_node_doc[functions_start:].strip()
                        
#                         # Set next_doc_functions to True if functions exist and are not empty
#                         if functions_text and functions_text.strip():
#                             next_doc_functions = True
#                             print(f"Functions found: {len(functions_text)} characters, NEXT DOC FUNCTION {next_doc_functions}")
#                         else:
#                             next_doc_functions = False
#                             print("Functions section is empty")
#                     else:
#                         next_doc_functions = False
#                         print("No FUNCTIONS section found")

#                 except Exception as e:
#                     print(f"Error extracting instruction from next node: {str(e)}")
#                     ai_response = "No specific instructions available for the next step."


#             if calculated_gestational_info:
#                 ai_response += f" {calculated_gestational_info}"
#             # Check if no function match and no progression (e.g., no functions or all unmatched)
#             has_functions = False
#             if "FUNCTIONS:" in current_node_doc:
#                 functions_section = current_node_doc.split("FUNCTIONS:")[1]
#                 # Check if there are any non-empty lines after FUNCTIONS:
#                 has_functions = any(f.strip() for f in functions_section.split("\n") if f.strip())
#             print(f"[HAS FUNCTION] ({has_functions}), Current Node ID : {current_node_id}")

#             # Enter fallback if no functions exist
#             # print(f"DOCUMENT CONTEXT {document_context}")
#             if not has_functions and not is_survey_node and current_node_id is None:
#                 print("No function match and no progression detected, generating fallback response")
#                 if document_context_section:
#                     print("Using document context for response")
#                     fallback_prompt = f"""
#                     You are a helpful assistant. The user has sent the following message:
                    
#                     The user's last message was: "{message}"

#                     Previous conversation:
#                     {conversation_history}
                    
#                     Relevant Document Content:
#                     {document_context_section}
                    
#                     INSTRUCTION:
#                      INSTRUCTIONS FOR YOUR RESPONSE:
#                     1.  **PRIMARY REQUIREMENT**: You MUST first deliver the message provided in "Current Node's Primary Message/Instruction" verbatim or rephrased naturally. This is the essential response for this stage of the conversation.
#                     2.  After including the primary message, if the "Relevant Document Content" is present and offers *additional, helpful* information directly related to the user's query or the ongoing conversation (especially if no further flow options exist for this node), integrate it gracefully and naturally.
#                     3.  Maintain a natural, conversational, and empathetic tone.
#                     4.  Ensure any URLs, phone numbers, email addresses, or specific resources from either the "Current Node's Primary Message/Instruction" or "Relevant Document Content" are included verbatim.
                    
#                     Please provide a helpful response based on the document content, addressing the user's query.
#                     """
#                 else:
#                     print("No document context available, using general fallback")
#                     fallback_prompt = f"""
#                     You are a helpful assistant. The user has sent the following message:
                    
#                     "{message}"
                    
#                     Previous conversation:
#                     {conversation_history}
                    
#                     I couldn't find specific information to proceed. Please provide a helpful response based on the conversation history.
#                     """
#                 fallback_response = Settings.llm.complete(fallback_prompt)
#                 ai_response = fallback_response.text
#                 print(f"Fallback response generated, length: {len(ai_response)} characters")

            

#             print(f'[AI RESPONSE]', ai_response)
#             rephrase_prompt = f"""
#             You are a friendly, conversational assistant tasked with rephrasing a given text to sound natural, human-like, and context-aware.

#             CRITICAL: You must ONLY rephrase the text in 'Original Response': {ai_response}. Do NOT create new content or ask different questions.
#             CRITICAL: Do NOT ask any questions that are not in the Original Response {ai_response}
#             CRITICAL: Keep ALL content including phone number placeholders like $Clinic_Phone$. 

#             Instructions:
#             1.  **Rephrase** the 'Original Response' to sound natural and human-like, preserving its exact intent and type (statement or question).
#             2.  **Personalize the response:** If the patient's first name is available in 'Patient Profile', use it at the beginning of the response.
#             3.  **Subtly incorporate relevant 'Patient History':** Only incorporate 'Patient History' if it directly supports the original response without altering its intent or introducing new questions. If any detail from the 'Patient History' can be seamlessly and non-contradictorily woven into the rephrased 'Original Response' to make it more contextually rich, do so. For example, if the original response is a general greeting and the history mentions a positive pregnancy test, you can add "I see you recently reported a positive pregnancy test." If the original response is a question about a date, you might add, "We have your last reported LMP as [date], would you like to update that?"
#             4.  **Maintain the original intent and type:** If the 'Original Response' is a question, the rephrased response MUST be a question. If it's a statement, it MUST be a statement. Do not add new questions or change the core meaning.
#             5.  **Crucially: Do NOT contradict or question the 'Original Response'.** Your goal is to enhance it, not to challenge its premise or introduce new, conflicting information.
#             6.  **Do NOT** include acknowledgment phrases like 'Okay,' 'Great,' 'I understand,' or 'Let's move on' unless they ar
#             7.  If the `Original Response` includes calculated values (e.g., gestational age), preserve them verbatim in the rephrased response.
#             8.  **Do NOT** ask for confirmation of previously provided data (e.g., LMP date) unless explicitly instructed by the `Original Response` or node instructions.

#             Original Response (from the main LLM, this is the message you must rephrase): "{ai_response}"
            
#             User message: "{message}"

#             Patient Profile (for personalization, e.g., first_name):
#             {patient_fields}

#             Patient History (for subtle contextual enrichment, use only if it fits without contradiction):
#             {patient_history}

#             Return the rephrased response as a string.
#             """
#             print("Calling secondary LLM for rephrasing")
#             rephrased_response = Settings.llm.complete(rephrase_prompt).text.strip()
#             if rephrased_response.startswith('"') and rephrased_response.endswith('"'):
#                 rephrased_response = rephrased_response[1:-1]
            
#             print(f"Rephrased response: {rephrased_response}")
#             print(f"AI response length: {len(ai_response)} characters")
#             print(f"Next node ID: {next_node_id}")
#             print("==== VECTOR CHAT PROCESSING COMPLETE ====\n")
            
#             # Check if the next node is a notification node and include all relevant data
#             # Check if the next node is a notification node BEFORE setting next_node_id to None
#             is_survey_node = "NODE TYPE: surveyNode" in current_node_doc
#             is_next_survey_node = next_node_id and "NODE TYPE: surveyNode" in next_node_doc

#             if is_survey_node or is_next_survey_node:
#                 survey_node_id = current_node_id if is_survey_node else next_node_id
#                 print(f"[SURVEY NODE] Detected survey node: {survey_node_id}")
#                 return {
#                     "content": None,
#                     "next_node_id": survey_node_id,  # Return the survey node ID
#                     "node_type": "surveyNode",
#                     "state_updates": {},
#                     "onboarding_status": onboarding_status_to_send
#                 }

#             if next_node_id and "NODE TYPE: notificationNode" in next_node_doc:
#                 # Extract node data from the instruction section
#                 node_data = {}
                
#                 # Parse the notification data from the instruction text
#                 try:
#                     lines = next_node_doc.split('\n')
#                     for line in lines:
#                         line = line.strip()
#                         if line.startswith('- Notification Type:'):
#                             node_data['messageType'] = line.split(':', 1)[1].strip()
#                         elif line.startswith('- Title:'):
#                             node_data['title'] = line.split(':', 1)[1].strip()
#                         elif line.startswith('- Schedule:'):
#                             node_data['scheduleType'] = line.split(':', 1)[1].strip()
#                         elif line.startswith('- Assistant ID:'):
#                             node_data['assistantId'] = line.split(':', 1)[1].strip()
#                         elif line.startswith('INSTRUCTION:'):
#                             # Extract the main message from the instruction
#                             instruction_text = line.split(':', 1)[1].strip()
#                             node_data['message'] = instruction_text
#                         elif line.startswith('NODE DATA:'):
#                             # Extract and parse the JSON data containing survey questions
#                             try:
#                                 node_data_str = line.split('NODE DATA:', 1)[1].strip()
#                                 # Find the first JSON object in the node data
#                                 json_start = node_data_str.find('{')
#                                 json_end = node_data_str.rfind('}') + 1
#                                 if json_start >= 0 and json_end > json_start:
#                                     parsed_data = json.loads(node_data_str[json_start:json_end])
#                                     if 'surveyQuestions' in parsed_data:
#                                         node_data['surveyQuestions'] = parsed_data['surveyQuestions']
#                             except Exception as e:
#                                 print(f"Error parsing survey questions: {str(e)}")
                    
#                     print(f"[NOTIFICATION NODE] Parsed node data: {node_data}")
#                     print(f"[SURVEY QUESTIONS] Found {len(node_data.get('surveyQuestions', []))} questions")
                    
#                 except Exception as e:
#                     print(f"Error parsing notification node data: {str(e)}")
                
#                 print(f"[NOTIFICATION NODE] Setting next_node_id to None after processing notification")
#                 return {
#                     "content": rephrased_response,
#                     "next_node_id": None,  # Set to None for notification nodes
#                     "node_type": "notificationNode",
#                     "message": node_data.get("message", ""),
#                     "notification_type": node_data.get("messageType", "whatsapp"),
#                     "title": node_data.get("title", ""),
#                     "schedule_type": node_data.get("scheduleType", ""),
#                     "scheduled_for": node_data.get("scheduledFor", ""),
#                     "assistant_id": node_data.get("assistantId", ""),
#                     "survey_questions": node_data.get("surveyQuestions", []),
#                     "state_updates": {},
#                     "onboarding_status": onboarding_status_to_send
#                 }
            
#             if not next_doc_functions:
#                 next_node_id = None
#                 print(f"[END NODE] Setting next_node_id to None - no further progression")
#             # For non-notification nodes, return the standard response
#             return {
#                 "content": rephrased_response,
#                 "next_node_id": next_node_id,
#                 "state_updates": {},
#                 "onboarding_status": onboarding_status_to_send
#             }

#         except Exception as e:
#             print(f"ERROR processing vector response: {str(e)}")
#             print(f"Response text that failed to parse: {response_text[:200]}...")

#             # Fallback to direct LLM response
#             print("Using fallback LLM response")
#             fallback_prompt = f"""
#             You are a helpful assistant. The user has sent the following message:
            
#             "{message}"
            
#             Previous conversation:
#             {conversation_history}
            
#             Please provide a helpful response.
#             """

#             fallback_response = Settings.llm.complete(fallback_prompt)
#             print(f"Fallback response generated, length: {len(fallback_response.text)} characters")
#             print("==== VECTOR CHAT PROCESSING COMPLETE (FALLBACK) ====\n")

#             return {
#                 "content": fallback_response.text,
#                 "error": f"Vector processing failed: {str(e)}",
#                 "fallback": True
#             }

#     except Exception as e:
#         print(f"CRITICAL ERROR in vector_chat: {str(e)}")
#         traceback_str = traceback.format_exc()
#         print(f"Traceback: {traceback_str}")
#         print("==== VECTOR CHAT PROCESSING FAILED ====\n")
#         return {
#             "error": f"Failed to process message: {str(e)}",
#             "content": "I'm having trouble processing your request. Please try again later."
#         }
    


class FlowDocumentationRequest(BaseModel):
    flow_data: Dict[str, Any]
    assistant_id: str
    name: Optional[str] = None

# @app.post("/api/generate/flow-documentation")
# async def generate_flow_documentation(request: FlowDocumentationRequest):
#     """
#     Generate structured flow documentation from flow builder data.
    
#     This endpoint processes the flow nodes and edges to create a structured,
#     readable documentation format that can be used by AI assistants.
#     """
#     try:
#         flow_data = request.flow_data
#         assistant_id = request.assistant_id
#         assistant_name = request.name or "Assistant"
        
#         if not flow_data or not isinstance(flow_data, dict):
#             raise HTTPException(status_code=400, detail="Invalid flow data format")
        
#         nodes = flow_data.get("nodes", [])
#         edges = flow_data.get("edges", [])
        
#         if not nodes:
#             return {"flow_instructions": "No flow nodes found."}
            
#         # Build a node map for quick lookups
#         node_map = {node["id"]: node for node in nodes}
        
#         # Build connection map to track node relationships
#         connections = {}
#         for edge in edges:
#             source = edge.get("source")
#             target = edge.get("target")
#             source_handle = edge.get("sourceHandle", "")
            
#             if source not in connections:
#                 connections[source] = []
            
#             # Store connection with handle info
#             connections[source].append({
#                 "target": target,
#                 "handle": source_handle
#             })
        
#         # Identify starting nodes (those with nodeType="starting")
#         starting_nodes = [node for node in nodes if node.get("data", {}).get("nodeType") == "starting"]
        
#         # If no explicit starting nodes, look for nodes that have no incoming edges
#         if not starting_nodes:
#             target_nodes = set(edge["target"] for edge in edges)
#             starting_nodes = [node for node in nodes if node["id"] not in target_nodes]
        
#         # Generate documentation prompt for LLM
#         llm_input = f"""
# Please generate structured flow documentation based on the following conversation flow data.
# The documentation should be formatted in a clear, hierarchical structure with node titles and their corresponding messages.

# Flow Name: {assistant_name}

# Flow Structure:
# """
        
#         # Process nodes by type to organize them logically
#         for node in nodes:
#             node_id = node["id"]
#             node_data = node.get("data", {})
#             node_type = node_data.get("type", "unknown")
#             node_title = node_data.get("heading", "") or f"Node {node_id}"
#             node_message = node_data.get("message", "")
#             node_class = node.get("type", "unknown")
            
#             # Format node info for the LLM input
#             llm_input += f"\n- Node ID: {node_id}"
#             llm_input += f"\n  Type: {node_class}"
#             llm_input += f"\n  Title: {node_title}"
#             llm_input += f"\n  Message: \"{node_message}\""
            
#             # Add function/option information for dialogue and response nodes
#             if node_class in ["dialogueNode", "scriptNode"] and "functions" in node_data:
#                 llm_input += "\n  Options:"
#                 for func in node_data.get("functions", []):
#                     llm_input += f"\n    - {func.get('content', 'Option')}"
            
#             # Add trigger information for response nodes
#             if node_class == "responseNode" and "triggers" in node_data:
#                 llm_input += "\n  Triggers:"
#                 for trigger in node_data.get("triggers", []):
#                     llm_input += f"\n    - {trigger.get('content', 'Trigger')}"
            
#             # Add field information for field setter nodes
#             if node_class == "fieldSetterNode":
#                 field_name = node_data.get("fieldName", "")
#                 llm_input += f"\n  Field: {field_name}"
            
#             # Add survey information for survey nodes
#             if node_class == "surveyNode" and "surveyData" in node_data:
#                 survey_data = node_data.get("surveyData", {})
#                 survey_name = survey_data.get("name", "Unknown Survey")
#                 llm_input += f"\n  Survey: {survey_name}"
            
#             # Add connections information
#             if node_id in connections:
#                 llm_input += "\n  Connections:"
#                 for conn in connections[node_id]:
#                     target_id = conn["target"]
#                     target_node = node_map.get(target_id, {})
#                     target_title = target_node.get("data", {}).get("heading", "") or f"Node {target_id}"
#                     llm_input += f"\n    - To: {target_title} (ID: {target_id})"
            
#             llm_input += "\n"
        
#         # Add edge information to help understand the flow
#         llm_input += "\nFlow Connections:"
#         for edge in edges:
#             source_id = edge.get("source")
#             target_id = edge.get("target")
#             source_node = node_map.get(source_id, {})
#             target_node = node_map.get(target_id, {})
#             source_title = source_node.get("data", {}).get("heading", "") or f"Node {source_id}"
#             target_title = target_node.get("data", {}).get("heading", "") or f"Node {target_id}"
            
#             llm_input += f"\n- {source_title} → {target_title}"
        
#         llm_input += """

# Based on the above flow structure, please generate clear, structured documentation in the following format:

# • **Node-Title**  
#   "Message text that would be shown to the user"

# • **Another-Node-Title**  
#   "Another message text"

# –– **Branch name (if applicable)** ––  
# • **Branch-Node**  
#   "Message for this branch node"

# The documentation should be clearly organized, showing the logical flow of the conversation,
# with any branches or decision points clearly marked. Use the node titles as section headers,
# and include the exact message text that would be shown to users.

# Make sure to:
# 1. Group related nodes together
# 2. Use bullet points and indentation to show hierarchy
# 3. Mark branches or decision paths clearly
# 4. Preserve the exact message text in quotes
# 5. Create a logical reading order that follows the conversation flow

# The output should be formatted similar to this example:

# Current Flow Instructions:

# • **Menu-Items**  
#   "What are you looking for today?  
#    1. Options listed here  
#    2. More options here"

# • **First-Step**  
#   "Question or message to user"

# –– **Branch A** ––  
# • **Branch-A-Node-1**  
#   "Message for this branch"

# –– **Branch B** ––  
# • **Branch-B-Node-1**  
#   "Message for other branch"
# """
        
#         # Call the LLM to generate the structured documentation
#         response = Settings.llm.complete(llm_input)
#         flow_instructions = response.text.strip()
        
#         # Extract just the formatted instructions part if needed
#         if "Current Flow Instructions:" in flow_instructions:
#             flow_instructions = flow_instructions.split("Current Flow Instructions:")[1].strip()
        
#         return {
#             "assistant_id": assistant_id,
#             "flow_instructions": flow_instructions
#         }
        
#     except Exception as e:
#         print(f"Error generating flow documentation: {str(e)}")
#         raise HTTPException(
#             status_code=500, 
#             detail=f"Failed to generate flow documentation: {str(e)}"
#         )
    
@app.post("/api/generate/flow-documentation")
async def generate_flow_documentation(request: FlowDocumentationRequest):
    """
    Generate structured flow documentation from flow builder data.
    
    This endpoint processes the flow nodes and edges to create a structured,
    readable documentation format that can be used by AI assistants.
    
    The function now handles two formats:
    1. Traditional nodes/edges format
    2. Direct textInstructions format (pre-formatted instructions)
    """
    try:
        flow_data = request.flow_data
        assistant_id = request.assistant_id
        assistant_name = request.name or "Assistant"
        
        if not flow_data or not isinstance(flow_data, dict):
            raise HTTPException(status_code=400, detail="Invalid flow data format")
        
        # Check if textInstructions is provided directly
#         if "textInstructions" in flow_data and flow_data["textInstructions"]:
#             # Process direct text instructions
#             text_instructions = flow_data["textInstructions"]
            
#             # Create a prompt for the LLM to format the text instructions properly
# #             llm_input = f"""
# # You are tasked with formatting conversation flow instructions into a standardized format, regardless of the input format. The input could be completely unformatted paragraphs, a partially formatted document, or might already have some structure.

# # Flow Name: {assistant_name}

# # Input Instructions:
# # ```
# # {text_instructions}
# # ```

# # Your task is to transform the input into a structured conversation flow with this format:

# # • **Node-Title**  
# #   "Message text that would be shown to the user"

# # • **Another-Node-Title**  
# #   "Another message text"

# # –– **Branch name (if applicable)** ––  
# # • **Branch-Node**  
# #   "Message for this branch node"

# # IMPORTANT INSTRUCTIONS:

# # 1. HANDLING UNFORMATTED TEXT:
# #    - If the input is an unformatted paragraph or lacks clear structure, identify logical sections and create appropriate node titles
# #    - Extract conversation elements and turn them into proper message nodes
# #    - Identify decision points and create appropriate branches

# # 2. HANDLING PARTIALLY FORMATTED TEXT:
# #    - If the input has markers like '#', '*', '-', numbers, or other formatting elements, transform them to match the target format
# #    - Convert any existing headers or titles into bold node titles with **Title** format
# #    - Keep text in quotes if already quoted, or add quotes around message content if not already quoted

# # 3. STRUCTURE REQUIREMENTS:
# #    - Each conversation node must have a clear title in bold with ** markers
# #    - Each message must be in quotes
# #    - Use bullet points (•) for all nodes
# #    - Mark branches with –– **Branch Name** –– format
# #    - Preserve the logical flow and hierarchy of the conversation

# # 4. CONTENT GUIDELINES:
# #    - Preserve all original wording and content
# #    - Don't add, remove, or substantially change any conversation elements
# #    - If there are numberings or options within messages, keep them as is
# #    - All text representing what would be shown to users should be in quotes

# # 5. FORMAT SPECIFICALLY FOR CHATBOTS:
# #    - Focus on creating a flow that represents a conversation between a chatbot and user
# #    - Identify and properly format any conditional branches or decision points
# #    - Group related nodes under appropriate branches

# # Provide the reformatted flow instructions following these guidelines. The output should be clean, consistent, and ready for implementation in a conversational interface.

# # ADDITIONAL TIPS FOR HANDLING COMPLETELY UNSTRUCTURED TEXT:
# # - If the input is just a paragraph describing a conversation flow:
# #   - Identify key interaction points (questions, responses, decision points)
# #   - Create logical node titles based on the content (e.g., "Initial-Greeting", "Service-Selection", "Contact-Info")
# #   - Organize the flow in a logical sequence
# #   - Format user-facing messages in quotes
# #   - Create appropriate branch structure for different conversation paths

# # EXAMPLE TRANSFORMATION (for completely unstructured text):

# # Input: "The assistant should first greet users and ask what service they need. If they select medical advice, ask for symptoms. If they select appointment booking, ask for preferred date. For symptoms, provide relevant information or escalate to human agent."

# # Output:
# # • **Initial-Greeting**  
# #   "Hello! Welcome to our service. How can I help you today?"

# # • **Service-Selection**  
# #   "What service are you looking for? 1. Medical advice 2. Appointment booking"

# # –– **Medical Advice Branch** ––  
# # • **Symptom-Collection**  
# #   "What symptoms are you experiencing?"

# # • **Provide-Information**  
# #   "Based on your symptoms, here's some information that might help..."

# # –– **Appointment Branch** ––  
# # • **Date-Selection**  
# #   "What date would you prefer for your appointment?"

# # Make sure the final output follows the required format with appropriate titles, quoted messages, bullet points, and branch markers.
# # """
            
#             # Call the LLM to process and standardize the text instructions
#             response = Settings.llm.complete(llm_input)
#             flow_instructions = response.text.strip()
            
#             # Return the processed instructions
#             return {
#                 "assistant_id": assistant_id,
#                 "flow_instructions": flow_instructions
#             }
        if "textInstructions" in flow_data and flow_data["textInstructions"]:
            import os
            import sys
            from llama_index.core import VectorStoreIndex, Document
            # Settings is often used for global configuration, keep if used elsewhere
            # from llama_index.core import Settings
            from llama_index.core.node_parser import TokenTextSplitter
            # You don't need to explicitly import StorageContext if you are not using from_defaults
            # But keeping it doesn't hurt.
            # from llama_index.core import StorageContext

            try:
                # Process direct text instructions
                text_instructions = flow_data["textInstructions"]

                # Create a document from the flow instructions
                documents = [Document(text=text_instructions)]

                # Split the text into manageable chunks
                text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=50)
                nodes = text_splitter.get_nodes_from_documents(documents)

                # Get the absolute path for storage
                base_dir = os.path.abspath(os.path.dirname(__file__))
                persist_dir = os.path.join(base_dir, "flow_instructions_storage", f"flow_instruction_{assistant_id}")

                print(f"Target directory for persistence: {persist_dir}") # Changed print message

                # Create directory with proper permissions
                os.makedirs(persist_dir, exist_ok=True)

                # Keep the writability check - it's good practice, though the LlamaIndex persist()
                # call will also fail if there are permissions issues.
                try:
                    test_file_path = os.path.join(persist_dir, "test_write.txt")
                    with open(test_file_path, 'w') as f:
                        f.write("Test write access")
                    if os.path.exists(test_file_path):
                        os.remove(test_file_path)
                        print(f"Directory {persist_dir} is confirmed writable")
                    else:
                        # This path is unlikely unless directory creation itself failed silently
                        print(f"Warning: Test file creation succeeded but file not found. Directory {persist_dir} writability uncertain.")
                except Exception as perm_error:
                    print(f"Error: Directory {persist_dir} write test failed: {str(perm_error)}. Persistence may fail.")
                    # You might want to handle this error more explicitly, perhaps raise it
                    # or return an error response here if persistence is critical.
                    # For now, let's allow it to proceed so the persist() call gets a chance.


                # --- FIX START ---

                # 1. REMOVE this line: StorageContext.from_defaults is for LOADING existing indices, not creating new ones.
                # storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

                # 2. Create the index directly from nodes. It will use an in-memory storage context initially.
                print("Creating VectorStoreIndex from nodes...") # Added debug print
                # Pass nodes directly. No need for storage_context argument here when creating a new index to be persisted later.
                index = VectorStoreIndex(nodes)
                print("VectorStoreIndex created.") # Added debug print

                # 3. Persist the index to the specified directory *after* creation.
                # This method is responsible for creating the necessary files (docstore.json etc.)
                try:
                    print(f"Attempting to persist index to {persist_dir}...") # Added debug print
                    # Pass the persist_dir to the persist method
                    index.storage_context.persist(persist_dir=persist_dir)
                    print(f"Successfully persisted index to {persist_dir}")

                    # --- FIX END ---

                    # List the contents of the directory to verify files were created
                    print("Files created in the directory:")
                    if os.path.exists(persist_dir): # Added check just in case
                        for file in os.listdir(persist_dir):
                            print(f" - {file}")
                    else:
                        print(f" - Directory {persist_dir} does not exist after persist attempt.")

                except Exception as persist_error:
                    # This catch block handles errors during the actual writing to disk
                    print(f"Error persisting index: {str(persist_error)}")
                    return {
                        "assistant_id": assistant_id,
                        "flow_instructions": "Error indexing during persistence: " + str(persist_error),
                        "stacktrace": traceback.format_exc(), # Make sure traceback is imported
                        "fallback": text_instructions[:500] + "..." if len(text_instructions) > 500 else text_instructions
                    }
                print(f"Indexed text instructions sucessfully", 
                    "assistant_id", assistant_id,
                    "flow_instructions", text_instructions,  # Return actual text instructions
                    "persist_dir", persist_dir,  # Return this for debugging
                    "instruction_type","indexed"  # Add flag to indicate it's indexed
                      )
                return {
                    "assistant_id": assistant_id,
                    "flow_instructions": text_instructions,  # Return actual text instructions
                    "persist_dir": persist_dir,  # Return this for debugging
                    "instruction_type": "indexed"  # Add flag to indicate it's indexed
                }
            except Exception as e:
                # This catch block handles errors during node creation, directory creation, etc.
                print(f"Error in flow instructions indexing (general catch): {str(e)}")
                print(f"Python version: {sys.version}")
                print(f"Current working directory: {os.getcwd()}")
                return {
                    "assistant_id": assistant_id,
                    "flow_instructions": f"Error: {str(e)}",
                    "stacktrace": traceback.format_exc() # Make sure traceback is imported
                }
        
        else:
            # Process the traditional nodes and edges format
            nodes = flow_data.get("nodes", [])
            edges = flow_data.get("edges", [])
            
            if not nodes:
                return {"flow_instructions": "No flow nodes found."}
                
            # Build a node map for quick lookups
            node_map = {node["id"]: node for node in nodes}
            
            # Build connection map to track node relationships
            connections = {}
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")
                source_handle = edge.get("sourceHandle", "")
                
                if source not in connections:
                    connections[source] = []
                
                # Store connection with handle info
                connections[source].append({
                    "target": target,
                    "handle": source_handle
                })
            
            # Identify starting nodes (those with nodeType="starting")
            starting_nodes = [node for node in nodes if node.get("data", {}).get("nodeType") == "starting"]
            
            # If no explicit starting nodes, look for nodes that have no incoming edges
            if not starting_nodes:
                target_nodes = set(edge["target"] for edge in edges)
                starting_nodes = [node for node in nodes if node["id"] not in target_nodes]
            
            # Generate documentation prompt for LLM
            llm_input = f"""
Please generate structured flow documentation based on the following conversation flow data.
The documentation should be formatted in a clear, hierarchical structure with node titles and their corresponding messages.

Flow Name: {assistant_name}

Flow Structure:
"""
            
            # Process nodes by type to organize them logically
            for node in nodes:
                node_id = node["id"]
                node_data = node.get("data", {})
                node_type = node_data.get("type", "unknown")
                node_title = node_data.get("heading", "") or f"Node {node_id}"
                node_message = node_data.get("message", "")
                node_class = node.get("type", "unknown")
                
                # Format node info for the LLM input
                llm_input += f"\n- Node ID: {node_id}"
                llm_input += f"\n  Type: {node_class}"
                llm_input += f"\n  Title: {node_title}"
                llm_input += f"\n  Message: \"{node_message}\""
                
                # Add function/option information for dialogue and response nodes
                if node_class in ["dialogueNode", "scriptNode"] and "functions" in node_data:
                    llm_input += "\n  Options:"
                    for func in node_data.get("functions", []):
                        llm_input += f"\n    - {func.get('content', 'Option')}"
                
                # Add trigger information for response nodes
                if node_class == "responseNode" and "triggers" in node_data:
                    llm_input += "\n  Triggers:"
                    for trigger in node_data.get("triggers", []):
                        llm_input += f"\n    - {trigger.get('content', 'Trigger')}"
                
                # Add field information for field setter nodes
                if node_class == "fieldSetterNode":
                    field_name = node_data.get("fieldName", "")
                    llm_input += f"\n  Field: {field_name}"
                
                # Add survey information for survey nodes
                if node_class == "surveyNode" and "surveyData" in node_data:
                    survey_data = node_data.get("surveyData", {})
                    survey_name = survey_data.get("name", "Unknown Survey")
                    llm_input += f"\n  Survey: {survey_name}"
                
                # Add connections information
                if node_id in connections:
                    llm_input += "\n  Connections:"
                    for conn in connections[node_id]:
                        target_id = conn["target"]
                        target_node = node_map.get(target_id, {})
                        target_title = target_node.get("data", {}).get("heading", "") or f"Node {target_id}"
                        llm_input += f"\n    - To: {target_title} (ID: {target_id})"
                
                llm_input += "\n"
            
            # Add edge information to help understand the flow
            llm_input += "\nFlow Connections:"
            for edge in edges:
                source_id = edge.get("source")
                target_id = edge.get("target")
                source_node = node_map.get(source_id, {})
                target_node = node_map.get(target_id, {})
                source_title = source_node.get("data", {}).get("heading", "") or f"Node {source_id}"
                target_title = target_node.get("data", {}).get("heading", "") or f"Node {target_id}"
                
                llm_input += f"\n- {source_title} → {target_title}"
            
            llm_input += """

Based on the above flow structure, please generate clear, structured documentation in the following format:

• **Node-Title**  
  "Message text that would be shown to the user"

• **Another-Node-Title**  
  "Another message text"

–– **Branch name (if applicable)** ––  
• **Branch-Node**  
  "Message for this branch node"

The documentation should be clearly organized, showing the logical flow of the conversation,
with any branches or decision points clearly marked. Use the node titles as section headers,
and include the exact message text that would be shown to users.

Make sure to:
1. Group related nodes together
2. Use bullet points and indentation to show hierarchy
3. Mark branches or decision paths clearly
4. Preserve the exact message text in quotes
5. Create a logical reading order that follows the conversation flow

The output should be formatted similar to this example:

Current Flow Instructions:

• **Menu-Items**  
  "What are you looking for today?  
   1. Options listed here  
   2. More options here"

• **First-Step**  
  "Question or message to user"

–– **Branch A** ––  
• **Branch-A-Node-1**  
  "Message for this branch"

–– **Branch B** ––  
• **Branch-B-Node-1**  
  "Message for other branch"
"""
            
            # Call the LLM to generate the structured documentation
            response = Settings.llm.complete(llm_input)
            flow_instructions = response.text.strip()
            
            # Extract just the formatted instructions part if needed
            if "Current Flow Instructions:" in flow_instructions:
                flow_instructions = flow_instructions.split("Current Flow Instructions:")[1].strip()
            
            return {
                "assistant_id": assistant_id,
                "flow_instructions": flow_instructions
            }
        
    except Exception as e:
        print(f"Error generating flow documentation: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate flow documentation: {str(e)}"
        )
    
@app.post("/api/patient_onboarding")
async def patient_onboarding(request: Dict, db: Session = Depends(get_db)):
    try:
        print("\n==== STARTING PATIENT ONBOARDING/CHAT ====")
        from llama_index.retrievers.bm25 import BM25Retriever
        from llama_index.core import StorageContext, load_index_from_storage
        # --- Import BM25Retriever and RetrieverQueryEngine ---
        from llama_index.core.query_engine import RetrieverQueryEngine
        from llama_index.core import VectorStoreIndex, StorageContext
        from llama_index.core.retrievers import VectorIndexRetriever
        from llama_index.core.retrievers import QueryFusionRetriever

        
        import os

        # Request validation
        message = request.get("message", "").strip()
        sessionId = request.get("sessionId", "")
        patientId = request.get("patientId", "")
        assistantId = request.get("assistantId", "")
        flow_id = request.get("flow_id", "")
        session_data = request.get("session_data", {})
        previous_messages = request.get("previous_messages", [])
        flow_instructions = request.get("instruction_type")
        patient_history = request.get("patient_history", "")
        current_node_id = session_data.get('currentNodeId')
        # print(f"[PATIENT HISTORY], {patient_history}")

        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        if not sessionId:
            raise HTTPException(status_code=400, detail="Session ID is required")
        if not patientId:
            raise HTTPException(status_code=400, detail="Patient ID is required")
        if not assistantId:
            raise HTTPException(status_code=400, detail="Assistant ID is required")
        if not flow_id:
            raise HTTPException(status_code=400, detail="Flow ID is required")

        # --- Import BM25Retriever and RetrieverQueryEngine ---
        from llama_index.retrievers.bm25 import BM25Retriever
        from llama_index.core.query_engine import RetrieverQueryEngine
        # ----------------------------------------------------
        query_to_use = message
        if previous_messages:
            # print(f"Previous messages found ({len(previous_messages)}). Building contextual query.")
            context_messages = previous_messages[-4:] # Get last 3 messages

            context_str = "Conversation history:\n"
            for msg_obj in context_messages:
                 role = msg_obj.get('role', 'unknown').capitalize()
                 content = msg_obj.get('content', 'N/A')
                 context_str += f"{role}: {content}\n"

            # Combine context with the current message to form the query
            # Structure the query to help the retriever understand it's a follow-up
            query_to_use = f"{context_str}\nCurrent user input: {message} and the Current Node ID : {current_node_id}\nConsidering this, what is the relevant flow instruction and the next step and nodes?"

            # print(f"Augmented Query for Retrieval:\n{query_to_use}")
        else:
            print("No previous messages found. Using original message for retrieval.")
            # query_to_use remains the original message



        # if flow_instructions == "indexed" and assistantId:
        #     try:
        #         # Define the persist directory path for this assistant's flow instructions
        #         base_dir = os.path.abspath(os.path.dirname(__file__))
        #         persist_dir = os.path.join(base_dir, "flow_instructions_storage", f"flow_instruction_{assistantId}")

        #         print(f"Attempting to load index from: {persist_dir}")

        #         # Check if the directory exists
        #         if os.path.exists(persist_dir):
        #             # Load the storage context from the persist directory
        #             storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

        #             # Load the index from storage
        #             print("Loading index from storage...")
        #             index = load_index_from_storage(storage_context)
        #             print("Index loaded successfully.")

        #             # --- Create the BM25 Retriever ---
        #             # Retrieve all nodes from the index's document store to build the BM25 index over them.
        #             all_nodes = list(index.docstore.docs.values())

        #             bm25_retriever = None # Initialize to None
        #             if not all_nodes:
        #                 print("Warning: Could not retrieve nodes from index docstore to build BM25Retriever.")
        #             else:
        #                 # Use from_defaults with the retrieved nodes
        #                 print(f"Building BM25Retriever from {len(all_nodes)} nodes...")
        #                 # Set similarity_top_k here when creating the retriever instance
        #                 bm25_retriever = BM25Retriever.from_defaults(nodes=all_nodes, similarity_top_k=5)
        #                 print("BM25Retriever built.")

        #             # --- Create a query engine ---
        #             # Use RetrieverQueryEngine directly when using a custom retriever
        #             query_engine = None # Initialize query_engine

        #             if bm25_retriever:
        #                 # Create the query engine using the custom BM25 retriever
        #                 # RetrieverQueryEngine will use the default LLM from Settings for synthesis
        #                 print("Creating query engine using BM25Retriever...")
        #                 query_engine = RetrieverQueryEngine(retriever=bm25_retriever)
        #             else:
        #                 # Fallback: If BM25 failed to build, use the index's default vector retriever
        #                 print("Falling back to creating query engine using default VectorRetriever...")
        #                 # Use index.as_query_engine() which wraps the default vector retriever
        #                 query_engine = index.as_query_engine(similarity_top_k=5) # Configure default retriever here

        #             if query_engine is None:
        #                 raise ValueError("Failed to create any query engine (BM25 or default).")


        #             # --- Keep the rest of the query logic ---
        #             print(f"Querying index with message: '{query_to_use}'")
        #             response = query_engine.query(query_to_use)

        #             retrieved_text = response.response
        #             source_nodes = response.source_nodes # This will now be the nodes retrieved by the active retriever

        #             print(f"Successfully queried index for assistant: {assistantId}")
        #             print(f"LLM Synthesized Response: {retrieved_text}")

        #             print("\n--- Retrieved Source Nodes ---")
        #             if source_nodes:
        #                 retrieved_texts = []
        #                 # Check if nodes have scores before trying to format
        #                 score_available = hasattr(source_nodes[0], 'score') if source_nodes else False
        #                 for i, node_with_score in enumerate(source_nodes):
        #                     score_str = f" (Score: {node_with_score.score:.4f})" if score_available else ""
        #                     retrieved_texts.append(node_with_score.node.text)
        #                     # print(f"Node {i+1}{score_str}:")
        #                     # print(node_with_score.node.text)
        #                     # print("-" * 20)
        #             else:
        #                 print("No source nodes were retrieved by the retriever.")
        #             print("----------------------------\n")

        #             # flow_instructions = retrieved_text # Or the raw text from source_nodes if preferred
        #             flow_instructions = "\n---\n".join(retrieved_texts)

        #         else:
        #             print(f"Warning: Flow instructions directory not found for assistant: {assistantId} at {persist_dir}")
        #             flow_instructions = "No indexed flow instructions found."

        #     except Exception as e:
        #         print(f"Error retrieving indexed flow instructions: {str(e)}")
        #         # Ensure traceback is imported if you use it
        #         # print(f"Stacktrace: {traceback.format_exc()}")
        #         flow_instructions = f"Error retrieving flow instructions: {str(e)}"

        if flow_instructions == "indexed" and assistantId:
            try:    
                base_dir = os.path.abspath(os.path.dirname(__file__))
                persist_dir = os.path.join(base_dir, "flow_instructions_storage", f"flow_instruction_{assistantId}")
                print(f"Attempting to load index from: {persist_dir}")

                if os.path.exists(persist_dir):
                    # Load the storage context from the persist directory
                    storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
                    print("Loading index from storage...")
                    index = load_index_from_storage(storage_context)
                    print("Index loaded successfully.")

                    # Create VectorStoreRetriever
                    print("Building VectorStoreRetriever...")
                    vector_retriever = VectorIndexRetriever(
                        index=index,
                        similarity_top_k=5,  # Retrieve top 5 most similar nodes
                        embed_model=Settings.embed_model  # Use a lightweight embedding model
                    )
                    print("VectorStoreRetriever built.")

                    # Create query engine
                    print("Creating query engine using VectorStoreRetriever...")
                    query_engine = RetrieverQueryEngine(retriever=vector_retriever)
                    
                    # --- Keep the rest of the query logic ---
                    print(f"Querying index with message: '{query_to_use}'")
                    response = query_engine.query(query_to_use)

                    retrieved_text = response.response
                    source_nodes = response.source_nodes # This will now be the nodes retrieved by the active retriever

                    print(f"Successfully queried index for assistant: {assistantId}")
                    print(f"LLM Synthesized Response: {retrieved_text}")

                    print("\n--- Retrieved Source Nodes ---")
                    if source_nodes:
                        retrieved_texts = []
                        # Check if nodes have scores before trying to format
                        score_available = hasattr(source_nodes[0], 'score') if source_nodes else False
                        for i, node_with_score in enumerate(source_nodes):
                            score_str = f" (Score: {node_with_score.score:.4f})" if score_available else ""
                            retrieved_texts.append(node_with_score.node.text)
                            # print(f"Node {i+1}{score_str}:")
                            # print(node_with_score.node.text)
                            # print("-" * 20)
                    else:
                        print("No source nodes were retrieved by the retriever.")
                    print("----------------------------\n")

                    # flow_instructions = retrieved_text # Or the raw text from source_nodes if preferred
                    flow_instructions = "\n---\n".join(retrieved_texts)

                else:
                    print(f"Warning: Flow instructions directory not found for assistant: {assistantId} at {persist_dir}")
                    flow_instructions = "No indexed flow instructions found."

            except Exception as e:
                print(f"Error retrieving indexed flow instructions: {str(e)}")
                # Ensure traceback is imported if you use it
                # print(f"Stacktrace: {traceback.format_exc()}")
                flow_instructions = f"Error retrieving flow instructions: {str(e)}"
        
        print(f"[FETCHED FLOW INSTRUCTIONS], {flow_instructions}")
        # Get patient profile directly from Patient table
        patient = db.query(Patient).filter(Patient.id == patientId).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        patient_dict = {
            "id": patient.id,
            "mrn": patient.mrn,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,

        }
        #  "email": patient.email,
        #     "address": patient.address,
            
        #   "phone": patient.phone,
        # "insurance_provider": patient.insurance_provider,
            # "insurance_id": patient.insurance_id,
            # "primary_care_provider": patient.primary_care_provider,
            # "emergency_contact_name": patient.emergency_contact_name,
            # "emergency_contact_phone": patient.emergency_contact_phone,
            # "organization_id": patient.organization_id,
            # "created_at": patient.created_at.isoformat() if patient.created_at else None,
            # "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
        patient_fields = json.dumps(patient_dict, indent=2)

        # Format conversation history
        conversation_history = ""
        for msg in previous_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            conversation_history += f"{role}: {content}\n"

        # Current date
        eastern = pytz.timezone('America/New_York')
        current_date = datetime.now(eastern).date().strftime('%m/%d/%Y')

        # Load flow index
        if flow_id not in app.state.flow_indices:
            bucket = storage_client.bucket(BUCKET_NAME)
            meta_file = f"temp_flow_{flow_id}_meta.pkl"
            blob = bucket.blob(f"flow_metadata/{flow_id}_meta.pkl")
            try:
                blob.download_to_filename(meta_file)
                with open(meta_file, "rb") as f:
                    metadata = pickle.load(f)
                os.remove(meta_file)
            except Exception as e:
                print(f"Failed to load flow index metadata: {str(e)}")
                return {
                    "error": "Flow knowledge index not found",
                    "content": "I'm having trouble processing your request."
                }

            temp_dir = f"temp_flow_{flow_id}"
            os.makedirs(temp_dir, exist_ok=True)
            for blob in bucket.list_blobs(prefix=f"flow_indices/{flow_id}/"):
                local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
                blob.download_to_filename(local_path)

            collection_name = metadata["collection_name"]
            try:
                chroma_collection = chroma_client.get_collection(collection_name)
                print(f"Found existing Chroma collection {collection_name}")
            except chromadb.errors.InvalidCollectionException:
                print(f"Creating new Chroma collection {collection_name}")
                chroma_collection = chroma_client.create_collection(collection_name)
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

            storage_context = StorageContext.from_defaults(
                persist_dir=temp_dir, vector_store=vector_store
            )
            # Use load_index_from_storage instead of VectorStoreIndex.load_from_storage
            flow_index = load_index_from_storage(storage_context)
            app.state.flow_indices[flow_id] = flow_index
            shutil.rmtree(temp_dir)
        else:
            flow_index = app.state.flow_indices[flow_id]

        # Get current node
        current_node_doc = ""
        # if current_node_id:
        #     try:
        #         # Create basic retriever with no filters
        #         retriever = flow_index.as_retriever(similarity_top_k=10)
                
        #         # Query directly for the node ID as text
        #         query_str = f"NODE ID: {current_node_id}"
        #         print(f"Querying for: '{query_str}'")
                
        #         # Use the most basic retrieval pattern
        #         node_docs = retriever.retrieve(query_str)
                
        #         # Check if we got any results
        #         if node_docs:
        #             # Find exact match for node_id in results
        #             exact_matches = [
        #                 doc for doc in node_docs 
        #                 if doc.metadata and doc.metadata.get("node_id") == current_node_id
        #             ]
                    
        #             if exact_matches:
        #                 current_node_doc = exact_matches[0].get_content()
        #                 print(f"Found exact match for node {current_node_id}")
        #             else:
        #                 # Just use the top result
        #                 current_node_doc = node_docs[0].get_content()
        #                 print(f"No exact match, using top result")
                    
        #             print(f"Retrieved document for node {current_node_id}: {current_node_doc[:100]}...")
        #         else:
        #             print(f"No document found for node {current_node_id}")
        #             current_node_doc = "No specific node instructions available."
        #     except Exception as e:
        #         print(f"Error retrieving node document: {str(e)}")
        #         current_node_doc = "Error retrieving node instructions."
        # elif not previous_messages:
        #     starting_node_id, starting_node_doc = get_starting_node(flow_index)
        #     if starting_node_id:
        #         current_node_id = starting_node_id
        #         current_node_doc = starting_node_doc
        #         print(f"[STARTING NODE] {current_node_id, current_node_doc}")
        #     else:
        #         current_node_id = None
        #         current_node_doc = "No starting node found."
       
       
        print('[CURRENT NODE ID]', current_node_id)
        # Load document index
        document_context = ""
        document_retriever = None
        if assistantId and assistantId not in app.state.document_indexes:
            bucket = storage_client.bucket(BUCKET_NAME)
            meta_file = f"temp_doc_{assistantId}_meta.pkl"
            blob = bucket.blob(f"document_metadata/{assistantId}_meta.pkl")
            try:
                blob.download_to_filename(meta_file)
                with open(meta_file, "rb") as f:
                    metadata = pickle.load(f)
                os.remove(meta_file)
                temp_dir = f"temp_doc_{assistantId}"
                os.makedirs(temp_dir, exist_ok=True)
                for blob in bucket.list_blobs(prefix=f"document_indices/{assistantId}/"):
                    local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
                    blob.download_to_filename(local_path)
                collection_name = metadata["collection_name"]
                print("DEBUG: Entering Chroma collection block for documents")
                try:
                    chroma_collection = chroma_client.get_collection(collection_name)
                    print(f"Found existing Chroma collection {collection_name} for document index")
                except chromadb.errors.InvalidCollectionException:
                    print(f"Creating new Chroma collection {collection_name} for document index")
                    chroma_collection = chroma_client.create_collection(collection_name)
                vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

                storage_context = StorageContext.from_defaults(
                    persist_dir=temp_dir, vector_store=vector_store
                )
                # Use load_index_from_storage instead of VectorStoreIndex.load_from_storage
                document_index = load_index_from_storage(storage_context)
                document_retriever = document_index.as_retriever(similarity_top_k=20)
                app.state.document_indexes[assistantId] = {
                    "index": document_index,
                    "retriever": document_retriever,
                    "created_at": metadata["created_at"],
                    "document_count": metadata["document_count"],
                    "node_count": metadata["node_count"]
                }
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Document index not found: {str(e)}")
        else:
            document_retriever = app.state.document_indexes.get(assistantId, {}).get("retriever")

        query_for_doc = message
        if previous_messages:
            context_messages = previous_messages[-4:] # Get last 3 messages

            context_str = "Conversation history:\n"
            for msg_obj in context_messages:
                 role = msg_obj.get('role', 'unknown').capitalize()
                 content = msg_obj.get('content', 'N/A')
                 context_str += f"{role}: {content}\n"

            # Combine context with the current message to form the query
            # Structure the query to help the retriever understand it's a follow-up
            query_for_doc = f"{context_str}\nCurrent user input: {message}\nConsidering this, what is the relevant context you can reterive?"

            print(f"Document Augmented Query for Retrieval:\n{query_for_doc}")
        else:
            print("No previous messages found. Using original message for retrieval.")
            # query_to_use remains the original message


        if document_retriever:
            print(f"Retrieving documents for query: '{message}'")
            retrieved_nodes = document_retriever.retrieve(message)
            document_text = ""
            if retrieved_nodes:
                try:
                    node_objs = [n.node for n in retrieved_nodes]
                    if len(node_objs) > 1:
                        print(f"Applying BM25 reranking to {len(node_objs)} nodes")
                        bm25_retriever = BM25Retriever.from_defaults(
                            nodes=node_objs, 
                            similarity_top_k=min(5, len(node_objs))
                        )
                        reranked_nodes = bm25_retriever.retrieve(message)
                        document_text = "\n\n".join([n.node.get_content() for n in reranked_nodes])
                    else:
                        document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
                except Exception as e:
                    print(f"BM25 reranking failed: {str(e)}, using vector results")
                    document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
            document_context = f"Relevant Document Content:\n{document_text}" if document_text else ""
            print(f"Document retrieval complete, found content with {len(document_context)} characters")
        else:
            print("No document retriever available, proceeding without document context")

        print('[DOCUMENT CONTEXT]', document_context[:200])

#         flow_instruction_context=  f"""
# # Current Flow Instructions:

# • **Onboarding**
#   Initial patient enrollment with four main branches:
#   - Pregnancy Preference Unknown
#   - Desired Pregnancy Preference
#   - Undesired/Unsure Pregnancy Preference
#   - Early Pregnancy Loss
#   Final pathways to either Offboarding or Program Archived

# • **Follow-Up Confirmation of Pregnancy Survey**
#   "Hi $patient_firstname. As your virtual health buddy, my mission is to help you find the best care for your needs. 
#   Have you had a moment to take your home pregnancy test?"
#   Reply Y or N

#   [If Y] "It sounds like you're sharing your pregnancy test results, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] "Were the results positive? Reply Y or N"

#   [If YES] "Sounds good. In order to give you accurate information, it's helpful for me to know the first day of your last menstrual period (LMP).
#   Do you know this date? Reply Y or N (It's OK if you're uncertain)"

#   [If Y] "Great. Your LMP is a good way to tell your gestational age. Please reply in this format: MM/DD/YYYY"

#   [Upon receiving date] "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps.
#   Stay tuned for your estimated gestational age, we're calculating it now."
#   [LMP Updated]
#   [Update LMP on dashboard]

#   [If N] "Not a problem. Do you know your Estimated Due Date? Reply Y or N (again, it's OK if you're uncertain)"

#   [If Y] "Great. Please reply in this format: MM/DD/YYYY"

#   [Upon receiving date] "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps.
#   Stay tuned for your estimated gestational age, we're calculating it now."
#   [EDD Updated]
#   [Update EDD on dashboard]

#   [If both N] "We know it can be hard to keep track of periods sometimes. Have you been seen in the Penn Medicine system? Reply Y or N"

#   [If Y] "Perfect. Over the next few days we're here for you and ready to help with your next moves. Stay tuned!"

#   [If N] "Not a problem. Contact the call center $clinic_phone$ and have them add you as a 'new patient'. This way, if you need any assistance in the future, we'll be able to help you quickly."
#   [LMP Unknown]
#   [Low – No Alert to Penn]

#   [If test result N] "Thanks for sharing. If you have any questions or if there's anything you'd like to talk about, we're here for you. Contact the call center $clinic_phone$ for any follow-ups & to make an appointment with your OB/GYN."

#   "Being a part of your care journey has been a real privilege. Since I only guide you through this brief period, I won't be available for texting after today. If you find yourself pregnant in the future, text me back at this number, and I'll be here to support you once again."
#   [Archive Patient]
#   [Patient not pregnant]
#   [No Alert to Penn]

# • **Pregnancy Test Results NLP Survey**
#   "It sounds like you're sharing your pregnancy test results, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] "Were the results positive? Reply Y or N"

#   [If YES] "Sounds good. In order to give you accurate information, it's helpful for me to know the first day of your last menstrual period (LMP). Do you know this date? Reply Y or N (It's OK if you're uncertain)"

#   [If Y] "Great. Your LMP is a good way to tell your gestational age. Please reply in this format: MM/DD/YYYY"

#   [Upon receiving date] "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."
#   [LMP Updated]
#   [Update LMP on dashboard]

#   [If N] "Not a problem. Do you know your Estimated Due Date? Reply Y or N (again, it's OK if you're uncertain)"

#   [If Y] "Great. Please reply in this format: MM/DD/YYYY"

#   [Upon receiving date] "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."
#   [EDD Updated]
#   [Update EDD on dashboard]

#   [If both N] "We know it can be hard to keep track of periods sometimes. Have you been seen in the Penn Medicine system? Reply Y or N"

#   [If Y] "Perfect. Over the next few days we're here for you and ready to help with your next moves. Stay tuned!"

#   [If N] "Not a problem. Contact the call center $clinic_phone$ and have them add you as a 'new patient'. This way, if you need any assistance in the future, we'll be able to help you quickly."
#   [LMP Unknown]
#   [Low – No Alert to Penn]

#   [If test result N] "Thanks for sharing. If you have any questions or if there's anything you'd like to talk about, we're here for you. Contact the call center $clinic_phone$ for any follow-ups & to make an appointment with your OB/GYN."

#   "Being a part of your care journey has been a real privilege. Since I only guide you through this brief period, I won't be available for texting after today. If you find yourself pregnant in the future, text me back at this number, and I'll be here to support you once again."
#   [Archive Patient]
#   [Patient not pregnant]
#   [No Alert to Penn]

# • **Pregnancy Intention Survey**
#   "$patient_firstName$, pregnancy can stir up many different emotions. These can range from uncertainty and regret to joy and happiness. You might even feel multiple emotions at the same time. It's okay to have these feelings. We're here to help support you through it all.

#   I'm checking in on how you're feeling about being pregnant. Are you: A) Excited B) Not sure C) Not excited Reply with just 1 letter"

#   [If A - Excited] "Well that is exciting news! Some people feel excited, and want to continue their pregnancy, and others aren't sure. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."
#   [Excited about being pregnant]
#   [Low - no alert to Penn]

#   [If B - Not sure] "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."
#   [Not sure about being pregnant]
#   [Low - no alert to Penn]

#   [If C - Not excited] "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."
#   [Not Excited about being pregnant]
#   [Low - no alert to Penn]

#   "Would you prefer us to connect you with providers who can help with: A) Continuing my pregnancy B) Talking with me about what my options are C) Getting an abortion Reply with just 1 letter"

#   [If A → A (Continuing pregnancy)] "Do you have a prenatal provider? Reply Y or N"
#   [EPS Desired]
#   [Change Early Pregnancy Preference to DESIRED]

#   [If Y] "Great, it sounds like you're on the right track! Call $clinic_phone$ to make an appointment."

#   [If N] "It's important to receive prenatal care early on. Sometimes it takes a few weeks to get in. Call $clinic_phone$ to schedule an appointment with Penn OB/GYN Associates or Dickens Clinic."
#   [7 days later]
#   Established Care Survey - OB

#   [If Any → B (Options)] "We understand your emotions, and it's important to take the necessary time to navigate through them. The team at The Pregnancy Early Access Center (PEACE) provides abortion, miscarriage management, and pregnancy prevention. Call $clinic_phone$ to schedule an appointment with PEACE. https://www.pennmedicine.org/make-an-appointment"
#   [EPS Unsure]
#   [Change Early Pregnancy Preference to UNSURE]
#   [4 days later]
#   Established Care Survey - PEACE

#   [If Any → C (Abortion)] "Call $clinic_phone$ to be scheduled with PEACE. https://www.pennmedicine.org/make-an-appointment We'll check back with you to make sure you're connected to care. We have a few more questions before your visit. It'll help us find the right care for you."
#   [EPS Undesired]
#   [Change Early Pregnancy Preference to UNDESIRED / UNSURE]
#   [4 days later]
#   Established Care Survey - PEACE

# SYMPTOM MANAGEMENT FLOWS:

# • **Menu-Items**  
#   "What are you looking for today?  
#    A) I have a question about symptoms
#    B) I have a question about medications
#    C) I have a question about an appointment
#    D) Information about what to expect at a PEACE visit
#    E) Something else
#    F) Nothing at this time
#    Reply with just one letter."

#   [If A] "We understand questions and concerns come up. You can try texting this number with your question, and I may have an answer. This isn't an emergency line, so it’s best to reach out to your provider if you have an urgent concern by calling $clinic_phone$. If you're worried or feel like this is something serious – it's essential to seek medical attention."

#   [If B] "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"

#   [If C] "Unfortunately, I can’t see when your appointment is, but you can call the clinic to find out more information. If I don’t answer all of your questions, or you have a more complex question, you can contact the Penn care team at $clinic_phone$ who can give you further instructions. I can also provide some general information about what to expect at a visit. Just ask me."

#   [If D] "The Pregnancy Early Access Center is a support team who's here to help you think through the next steps and make sure you have all the information you need. They're a listening ear, judgment-free and will support any decision you make. You can have an abortion, you can place the baby for adoption or you can continue the pregnancy and choose to parent. They are there to listen to you and answer any of your questions."

#   "Sometimes, they use an ultrasound to confirm how far along you are to help in discussing options for your pregnancy. If you're considering an abortion, they'll review both types of abortion (medical and surgical) and tell you about the required counseling and consent (must be done at least 24 hours before the procedure). They can also discuss financial assistance and connect you with resources to help cover the cost of care."

#   [If E] "OK, I understand and I might be able to help. Try texting your question to this number. Remember, I do best with short sentences about one topic. If you need more urgent help or prefer to speak to someone on the phone, you can reach your care team at $clinic_phone$ & ask for your clinic. If you're worried or feel like this is something serious – it's essential to seek medical attention."

#   [If F] "OK, remember you can text this number at any time with questions or concerns."

# • **Symptom-Triage**  
#   "What symptom are you experiencing? Reply 'Bleeding', 'Nausea', 'Vomiting', 'Pain', or 'Other'"

# • **Vaginal Bleeding - 1st Trimester**
#   "Let me ask a few more questions about your medical history to determine the next best steps. Have you ever had an ectopic pregnancy (this is a pregnancy in your tube or anywhere outside of your uterus)? Reply Y or N"

#   [If Y] "Considering your past history, you should be seen by a provider immediately. Now: Call your OB/GYN ASAP (Call $clinic_phone$ to make an urgent appointment with PEACE – the Early Pregnancy Access Center – if you do not have a provider) If you're not feeling well or have a medical emergency, visit your local ER."
#   [Patient reports heavy vaginal bleeding with previous ectopic pregnancy]
#   [High – Alert to Penn]

#   "Over the past 2 hours, is your bleeding so heavy that you've filled 4 or more super pads? Reply Y or N"

#   [If Y] "This amount of bleeding during pregnancy means you should be seen by a provider immediately. Now: Call your OB/GYN. (Call $clinic_phone$, option 5 to make an urgent appointment with PEACE – the Early Pregnancy Access Center) If you're not feeling well or have a medical emergency, visit your local ER."
#   [Patient reports heavy vaginal bleeding]
#   [High – Alert to Penn]

#   "Are you in any pain or cramping? Reply Y or N"

#   [If Y] "Have you been to the ER during this pregnancy? Reply Y or N"

#   [If Y] "Any amount of bleeding during pregnancy should be reported to a provider. Call your provider for guidance."
#   [Ongoing symptoms post ER visit]
#   [Medium – Alert to Penn]
#   [EPS ER Visit becomes TRUE for ER visit this pregnancy]

#   [If N] "While bleeding or spotting in early pregnancy can be alarming, it's pretty common. Based on your exam in the ER, it's okay to keep an eye on it from home. If you notice new symptoms, feel worse, or are concerned about your health and need to be seen urgently, go to the emergency department."
#   [Patient reports light vaginal bleeding with cramps]
#   [Medium – Alert to Penn]

#   [If N] "While bleeding or spotting in early pregnancy can be alarming, it's actually quite common and doesn't always mean a miscarriage. But keeping an eye on it is important. Always check the color of the blood (brown, pink, or bright red) and keep a note."
#   [Patient reports light vaginal bleeding (no cramps)]
#   [Low – Alert to Penn]

#   "If you continue bleeding, getting checked out by a provider can be helpful. Keep an eye on your bleeding. We'll check in on you again tomorrow. If the bleeding continues or you feel worse, make sure you contact a provider. And remember: If you do not feel well or you're having a medical emergency — especially if you've filled 4 or more super pads in two hours — go to your local ER. If you still have questions or concerns, call PEACE $clinic_phone$, option 5."
#   [Follow-up: 24 hours later]
#   Vaginal Bleeding – 1st Trimester Follow-up

# • **Vaginal Bleeding - Follow-up**
#   "Hey $patient_firstname, just checking on you. How's your vaginal bleeding today? A) Stopped B) Stayed the same C) Gotten heavier Reply with just one letter"

#   [If A - Stopped] "We're glad to hear it. If anything changes - especially if you begin filling 4 or more super pads in two hours, go to your local ER."
#   [Patient reports stopped bleeding]
#   [Low - No alert to Penn]

#   [If B - Same] "Thanks for sharing—we're sorry to hear your situation hasn't improved. Since your vaginal bleeding has lasted longer than a day, we recommend you call your OB/GYN or $clinic_phone$ and ask for the Early Pregnancy Access Center. If you do not feel well or you're having a medical emergency - especially if you've filled 4 or more super pads in two hours -- go to your local ER."
#   [Patient reports persistent vaginal bleeding]
#   [Low - Alert to Penn]

#   [If C - Heavier] "Sorry to hear that. Thanks for sharing. Since your vaginal bleeding has lasted longer than a day, and has increased, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."
#   [Patient reports increased vaginal bleeding]
#   [Medium - Alert to Penn]

# • **Nausea - 1st Trimester**
#   "We're sorry to hear it—and we're here to help. Nausea and vomiting are very common during pregnancy. Staying hydrated and eating small, frequent meals can help, along with natural remedies like ginger and vitamin B6. Let's make sure there's nothing you need to be seen for right away. Have you been able to keep food or liquids in your stomach for 24 hours? Reply Y or N"

#   [If Y] "OK, thanks for letting us know. Nausea and vomiting are very common during pregnancy. To feel better, staying hydrated and eating small, frequent meals (even before you feel hungry) is important. Avoid an empty stomach by taking small sips of water or nibbling on bland snacks throughout the day. Try eating protein-rich foods like meat or beans."

#   [If N] "OK, thanks for letting us know. There are safe treatment options for you! Your care team at Penn recommends trying a natural remedy like ginger and vitamin B6 (take one 25mg tablet every 8 hours as needed). If this isn't working, you can try unisom – an over-the-counter medication – unless you have an allergy. Let your provider know. You can use this medicine until they call you back."
#   [Patient reports nausea with 24 hrs no foods or liquids staying down]
#   [Medium – Alert to Penn]

#   "If your nausea gets worse and you can't keep foods or liquids down for over 24 hours, contact your provider or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you!"
#   [Follow-up scheduled: Nausea 1st Trimester Follow-up]

# • **Nausea - 1st Trimester Follow-up**
#   "Hey $patient_firstname, just checking on you. How's your nausea today? A) Better B) Stayed the same C) Worse Reply with just the letter"

#   [If A] "We're glad to hear it. If anything changes - especially if you can't keep foods or liquids down for 24+ hours, reach out to your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you."
#   [Patient reports nausea better]
#   [Low - No alert to Penn]

#   [If B] "Thanks for sharing—Sorry you aren't feeling better yet, but we're glad to hear you could keep a little down. Would you like us to check on you tomorrow as well? Reply Y or N"
#   [Patient reports nausea staying the same]
#   [Low - No alert to Penn]

#   [If Y] "OK. We're here to help. Let us know if anything changes."
#   [Follow-up in 24 hours]

#   [If N] "OK. We're here to help. Let us know if anything changes. If you can't keep foods or liquids down for 24+ hours, contact your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. There are safe ways to treat this, so don't wait. If you're not feeling well or have a medical emergency, visit your local ER."

#   [If C] "Have you kept food or drinks down since I last checked in? Reply Y or N"

#   [If N] "Sorry to hear that. Thanks for sharing. Since your vomiting has increased and worsened, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please visit your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."
#   [Patient reports worsening nausea with 24 hrs no food/liquid]
#   [Medium – Alert to Penn]

# • **Vomiting - 1st Trimester**
#   "Hi $patient_firstName$, It sounds like you're concerned about vomiting. Is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] TRIGGER 2ND NODE → NAUSEA TRIAGE

# • **Vomiting - 1st Trimester Follow-up**
#   "Checking on you, $patient_firstname. How's your vomiting today? A) Better B) Stayed the same C) Worse Reply with just the letter"

#   [If A] "We're glad to hear it. If anything changes - especially if you can't keep foods or liquids down for 24+ hours, reach out to your OB or call $clinic_phone$ if you have not seen an OB yet. Don't wait—there are safe treatment options for you."
#   [Patient reports vomiting better]
#   [Low - No alert to Penn]

#   [If B] "Thanks for sharing—Sorry you aren't feeling better yet. Would you like us to check on you tomorrow as well? Reply Y or N"
#   [Patient reports vomiting staying the same]
#   [Low - No alert to Penn]

#   [If Y] "OK. We're here to help. Let us know if anything changes."

#   [If N] "OK. We're here to help. Let us know if anything changes. If you can't keep foods or liquids down for 24+ hours, contact your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. If you're not feeling well or have a medical emergency, visit your local ER."

#   [If C] "Sorry to hear that. Thanks for sharing. Since your vomiting has increased and worsened, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."
#   [Patient reports worsening vomiting with >24 hrs no foods or liquids staying down]
#   [Medium – Alert to Penn]

# • **Pain - Early Pregnancy**
#   "We're sorry to hear this. It sounds like you're concerned about pain, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] Trigger EPS Vaginal Bleeding (First Trimester)
#   [Patient reports pain]
#   [Low - No Alert to Penn]

# • **Ectopic Pregnancy Concern**
#   "We're sorry to hear this. It sounds like you're concerned about an ectopic pregnancy, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] Trigger EPS Vaginal Bleeding (First Trimester)
#   [Patient reports possible ectopic pregnancy]
#   [Low - No Alert to Penn]

# • **Menstrual Period Concern**
#   "It sounds like you're concerned about your menstrual period, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] "EPS Vaginal Bleeding (First Trimester) Let me ask you a few more questions about your medical history to determine the next best steps."
#   [Patient reports menstrual period]
#   [Low - No Alert to Penn]

# PREGNANCY DECISION SUPPORT FLOWS:

# • **Possible Early Pregnancy Loss**
#   "It sounds like you're concerned about pregnancy loss (miscarriage), is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] "We're sorry to hear this. Has a healthcare provider confirmed an early pregnancy loss (that your pregnancy stopped growing)? A) Yes B) No C) Not Sure Reply with just the letter"

#   [If A] "We're here to listen and offer support. It's helpful to talk about the options to manage this. We can help schedule you an appointment. Call $clinic_phone$ and ask for the PEACE clinic. We'll check in on you in a few days."
#   [Patient reports confirmed early pregnancy loss]
#   [High – Alert to Penn & Scheduling]
#   [Turn on Early Pregnancy Loss tip program]
#   [Updating enrollment field with today's date]

#   [If B] Trigger Vaginal Bleeding – 1st Trimester
#   [Patient reports possible early pregnancy loss]
#   [Low – No Alert to Penn]

#   [If C] "Sorry to hear this has been confusing for you. We recommend scheduling an appointment with PEACE so that they can help explain what's going on. Call $clinic_phone$, option 5 and we can help schedule you a visit so that you can get the information you need, and your situation becomes more clear."
#   Trigger Vaginal Bleeding – 1st Trimester
#   [Patient reports possible early pregnancy loss]
#   [Low – No Alert to Penn]

# • **Undesired Pregnancy - Desires Abortion**
#   "It sounds like you want to get connected to care for an abortion, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] "The decision about this pregnancy is yours and no one is better able to decide than you. Please call $clinic_phone$ and ask to be connected to the PEACE clinic (pregnancy early access center). The clinic intake staff will answer your questions and help schedule an abortion. You can also find more information about laws in your state and how to get an abortion at AbortionFinder.org"
#   [Patient requesting Abortion]
#   [No alert to Penn]
#   [Turn on Undesired tip program]
#   [Updating enrollment field with today's date]

# • **Undesired Pregnancy - Completed Abortion**
#   "It sounds like you've already had an abortion, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] "Caring for yourself after an abortion is important. Follow the instructions given to you. Most people can return to normal activities 1 to 2 days after the procedure. You may have cramps and light bleeding for up to 2 weeks. Call $clinic_phone$, option 5 and ask to be connected to the PEACE clinic (pregnancy early access center) if you have any questions or concerns."

#   "Being a part of your care journey has been a real privilege. On behalf of your team at Penn, we hope we've been helpful to you during this time. Since I only guide you through this brief period, I won't be available for texting after today. Remember, you have a lot of resources available from Penn AND your community right at your fingertips."
#   [Patient stating Completed Abortion]
#   [No alert to Penn]
#   [Archive Patient]

# • **Desired Pregnancy Survey**
#   "It sounds like you want to get connected to care for your pregnancy, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] "That's something I can definitely do! Call $clinic_phone$ Penn OB/GYN Associates or Dickens Clinic and make an appointment. It's important to receive prenatal care early on (and throughout your pregnancy) to reduce the risk of complications and ensure that both you and your baby are healthy."
#   [Patient requesting to keep pregnancy]
#   [Low - No alert to Penn]
#   [Turn on Desired Pregnancy tip program]
#   [Updating enrollment field with today's date]

# • **Unsure About Pregnancy Survey**
#   "Becoming a parent is a big step. Deciding if you want to continue a pregnancy is a personal decision. Talking openly and honestly with your partner or healthcare team is key. We're here for you. You can also try some thought work here: https://www.pregnancyoptions.info/pregnancy-options-workbook Would you like to get connected to care to discuss your options for pregnancy, is that correct? Reply Y or N"

#   [If N] "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

#   [If Y] "Few decisions are greater than this one, but we've got your back. The decision about this pregnancy is yours and no one is better able to decide than you. Please call $clinic_phone$, and ask to be scheduled in the PEACE clinic (pregnancy early access center). They are here to support you no matter what you choose."
#   [Patient unsure about pregnancy]
#   [Low - No alert to Penn]
#   [Turn on EPS Unsure tip program]
#   [Updating enrollment field with today's date]

# POSTPARTUM SUPPORT FLOWS:

# • **Postpartum Onboarding – Week 1**
#   "Hi $patient_firstname$, congratulations on your new baby! Let's get started with a few short messages to support you and your newborn. You can always reply STOP to stop receiving messages."
#   [DAY: 0, TIME: 8 AM]

#   "Feeding your baby is one of the most important parts of newborn care. Feeding your baby at least 8-12 times every 24 hours is normal and important to support their growth. You may need to wake your baby to feed if they're sleepy or jaundiced."
#   [DAY: 0, TIME: 12 PM]

#   "It's important to keep track of your baby's output (wet and dirty diapers) to know they're feeding well. By the time your baby is 5 days old, they should have 5+ wet diapers and 3+ poops per day."
#   [DAY: 0, TIME: 4 PM]

#   "Jaundice is common in newborns and usually goes away on its own. Signs of jaundice include yellowing of the skin or eyes. If you're worried or if your baby isn't feeding well or is hard to wake up, call your pediatrician or visit the ER."
#   [DAY: 0, TIME: 8 PM]

#   "Schedule a pediatrician visit. [Add scheduling link or instructions]"
#   [DAY: 1, TIME: 8 AM]

#   "Hi $patient_firstname$, following up to check on how you're feeling after delivery. The postpartum period is a time of recovery, both physically and emotionally. It's normal to feel tired, sore, or even overwhelmed. You're not alone. Let us know if you need support."
#   [DAY: 1, TIME: 12 PM]

#   "Some symptoms may require urgent care. If you experience chest pain, heavy bleeding, or trouble breathing, call 911 or go to the ER. For other questions or concerns, message us anytime."
#   [DAY: 1, TIME: 4 PM]

# • **Postpartum Onboarding – Week 2**
#   "Hi $patient_firstname$, checking in to see how things are going now that your baby is about a week old. We shared some helpful info last week and want to make sure you're doing okay."
#   [DAY: 7, TIME: 8 AM]

#   "Hi there—feeling different emotions after delivery is common. You may feel joy, sadness, or both. About 80% of people experience the 'baby blues,' which typically go away in a couple of weeks. If you're not feeling well emotionally or have thoughts of hurting yourself or others, please reach out for help."
#   [DAY: 7, TIME: 12 PM]

#   "Experts recommend always placing your baby on their back to sleep, in a crib or bassinet without blankets, pillows, or stuffed toys. This reduces the risk of SIDS (Sudden Infant Death Syndrome)."
#   [DAY: 7, TIME: 4 PM]

#   "Reminder to schedule your postpartum check-in."
#   [DAY: 9, TIME: 8 AM]

#   "Diaper rash is common. It can usually be treated with diaper cream and frequent diaper changes. If your baby develops a rash that doesn't go away or seems painful, call your pediatrician."
#   [DAY: 9, TIME: 12 PM]

#   "Hi $patient_firstname$, checking in again—how is feeding going? Breastfeeding can be challenging at times. It's okay to ask for help from a lactation consultant or your provider. Let us know if you have questions."
#   [DAY: 9, TIME: 4 PM]

#   "Hi $patient_firstname$, just a quick note about contraception. You can get pregnant again even if you haven't gotten your period yet. If you're not ready to be pregnant again soon, it's important to consider your birth control options. Talk to your provider to learn what's right for you."
#   [DAY: 10, TIME: 12 PM]

#   "Birth control is available at no cost with most insurance plans. Let us know if you'd like support connecting to resources."
#   [DAY: 10, TIME: 5 PM]

# EMERGENCY SITUATION MANAGEMENT:

# • **Emergency Room Survey**
#   "It sounds like you are telling me about an emergency. Are you currently in the ER (or on your way)? Reply Y or N"

#   [If Y] "We're sorry to hear and thanks for sharing. Glad you're seeking care. Please let us know if there's anything we can do for you."
#   [High Alert: Current ER Visit]
#   [Patient has reported a current emergency room visit]
#   [High alert to Penn]
#   [Checkbox becomes TRUE for ER visit this pregnancy]

#   [If N] "Were you recently discharged from an emergency room visit?"

#   [If Y] "We're sorry to hear about your visit. To help your care team stay in the loop, would you like us to pass on any info? No worries if not, just reply 'no'."
#   "Let us know if you need anything else."
#   [High Alert: Recent ER Visit]
#   [Patient has reported a recent emergency room visit]
#   [High alert to Penn]
#   [Checkbox becomes TRUE for ER visit this pregnancy]

#   [If N] "If you're not feeling well or have a medical emergency, go to your local ER. If I misunderstood your message, try rephrasing & using short sentences. You may also reply MENU for a list of support options."

# EVALUATION SURVEYS:

# • **Pre-Program Impact Survey**
#   "Hi there, $patient_firstName$. As you start this program, we'd love to hear your thoughts! We're asking a few questions to understand how you're feeling about managing your early pregnancy."

#   "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"

#   "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"

#   "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."

# • **Post-Program Impact Survey**
#   "Hi $patient_firstname$, glad you finished the program! Sharing your thoughts would be a huge help in making the program even better for others."

#   "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"

#   "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"

#   "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."

# • **NPS Quantitative Survey**
#   "Hi $patient_firstname$, I have two quick questions about using this text messaging service (last time I promise):"

#   "On a 0-10 scale, with 10 being 'extremely likely,' how likely are you to recommend this text message program to someone with the same (or similar) situation? Reply with a number 0-10"

#   Next: → NPS Qualitative Survey

# • **NPS Qualitative Survey**
#   "Thanks for your response. What's the reason for your score?"

#   "Thanks, your feedback helps us improve future programs."

# MENU RESPONSES:

# • **A. Symptoms Response**
#   "We understand questions and concerns come up. By texting this number, you can connect with your question, and I may have an answer. This isn't an emergency line, so it's best to reach out to your doctor if you have an urgent concern by calling $clinic_phone$. If you're worried or feel like this is something serious - it's essential to seek medical attention."

# • **B. Medications Response**
#   "Do you have questions about: A) Medication management B) Medications that are safe in pregnancy C) Abortion medications"

#   "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"

# • **C. Appointment Response**
#   "Unfortunately, I can't see when your appointment is, but you can call the clinic to find out more information. If I don't answer all of your questions, or you have a more complex question, you can contact the Penn care team at $clinic_phone$ who can give you more detailed information about your appointment or general information about what to expect at a visit. Just ask me."

# • **D. PEACE Visit Response**
#   "The Pregnancy Early Access Center is a support team, which is here to help you make choices throughout the next steps and make sure you have all the information you need. They're like planning for judgment-free care. You can ask all your questions at your visit. You have options, you can place the baby for adoption or you can continue the pregnancy and choose to parent."

#   "Sometimes, they use an ultrasound to confirm how far along you are to help in discussing options for your pregnancy. If you're considering an abortion, they'll review both types of abortion (medical and surgical) and tell you about the required counseling and consent (must be done at least 24 hours before the procedure). They can also discuss financial assistance and connect you with resources to help cover the cost of care."

# • **E. Something Else Response**
#   "Ok, I understand and I might be able to help. Try texting your question to this number. Remember, I do best with short questions that are on one topic. If you need more urgent help or prefer to speak to someone on the phone, you can reach your care team at $clinic_phone$ & ask for your clinic. If you're worried or feel like this is something serious – it's essential to seek medical attention."

# • **F. Nothing Response**
#   "OK, remember you can text this number at any time with questions or concerns."

# ADDITIONAL INSTRUCTIONS:

# • **Always-On Q & A ON FIT**
#   "Always-On Q & A ON FIT - Symptom Triage (Nausea, Vomiting & Bleeding + Pregnancy Preference)"

# • **General Default Response**
#   "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."
        
#         """
       
#         flow_instruction_context = f"""
# Current Flow Instructions:

# • **Menu-Items**  
#   “What are you looking for today?  
#    1. Pregnancy test  
#    2. Early pregnancy-loss support  
#    3. Abortion  
#    4. Symptoms-related help  
#    5. Miscarriage support”

# • **Pregnancy-Test**  
#   “Have you had a positive pregnancy test? Reply yes, no, or unsure.”

# • **LMP-Query**  
#   “Do you know the day of your last menstrual period?”

# • **LMP-Date**  
#   “What was the first day of your last menstrual period? (MM/DD/YYYY)”

# • **Symptom-Triage**  
#   “What symptom are you experiencing? Reply ‘Bleeding’, ‘Nausea’, or ‘Vomiting’.”

# –– **Bleeding branch** ––  
# • **Bleeding-Triage**  
#   “Have you had a history of ectopic pregnancy? Reply EY for Yes, EN for No.”

# • **Bleeding-Heavy-Check**  
#   “Is the bleeding heavy (4+ super-pads in 2 hrs)? Reply Y or N.”

# • **Bleeding-Urgent**  
#   “This could be serious. Please call your OB/GYN at [clinic_phone] or go to ER. Are you seeing miscarriage?”

# • **Bleeding-Pain-Check**  
#   “Are you experiencing any pain or cramping? Reply Y or N.”

# • **Bleeding-Advice**  
#   “Please monitor your bleeding and note the color. Contact your provider. I’ll check in in 24 hrs.”

# –– **Nausea branch** ––  
# • **Nausea-Triage**  
#   “Have you been able to keep food or liquids down in the last 24 hrs? Reply Y or N.”

# • **Nausea-Advice**  
#   “Try small meals, ginger, or vitamin B6. I’ll check back in 24 hrs.”

# • **Nausea-Urgent**  
#   “If you can’t keep anything down, contact your provider or PEACE at [clinic_phone]. You might need Unisom.”

# –– **Miscarriage support** ––  
# • **Miscarriage-Support**  
#   “I’m sorry you’re going through this. Do you need emotional support or infection-prevention support?”

# • **Miscarriage-Emotions**  
#   “How are you feeling emotionally? I can connect you to social resources if needed.”

# • **Miscarriage-Infection**  
#   “To prevent infection, avoid tampons, sex, or swimming. Let me know if you develop fever.”

# • **Call-Transfer**  
#   “I’m transferring you now to a specialist for further assistance.”  

# """
#         flow_instruction_context = f"""
# Main Menu
# Node ID: menu-items
# "What are you looking for today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) I have a question about a pregnancy test F) I need help with pregnancy loss G) Something else H) Nothing at this time I) Take the Pre-Program Impact Survey J) Take the Post-Program Impact Survey K) Take the NPS Quantitative Survey Reply with just one letter."

# If A → go to symptoms-response
# If B → go to medications-response
# If C → go to appointment-response
# If D → go to peace-visit-response
# If E → go to follow-up-confirmation-of-pregnancy-survey
# If F → go to pregnancy-loss-response
# If G → go to something-else-response
# If H → go to nothing-response
# If I → go to pre-program-impact-survey
# If J → go to post-program-impact-survey
# If K → go to nps-quantitative-survey

# Pregnancy Test Flow
# Node ID: follow-up-confirmation-of-pregnancy-survey
# "Hi $patient_firstname. As your virtual health buddy, my mission is to help you find the best care for your needs. Have you had a moment to take your home pregnancy test? Reply Y or N"

# If Y or Yes → go to pregnancy-test-results-nlp-survey
# If N or No → go to default-response

# Node ID: pregnancy-test-results-nlp-survey
# "It sounds like you're sharing your pregnancy test results, is that correct? Reply Y or N"

# If Y or Yes → go to pregnancy-test-result-confirmation
# If N or No → go to default-response

# Node ID: pregnancy-test-result-confirmation
# "Were the results positive? Reply Y or N"

# If Y or Yes → go to ask-for-lmp
# If N or No → go to negative-test-result-response

# LMP and Dating Flow
# Node ID: ask-for-lmp
# "Sounds good. In order to give you accurate information, it's helpful for me to know the first day of your last menstrual period (LMP). Do you know this date? Reply Y or N (It's OK if you're uncertain)"

# If Y or Yes → go to enter-lmp-date
# If N or No → go to ask-for-edd

# Node ID: enter-lmp-date
# "Great. Your LMP is a good way to tell your gestational age. Please reply in this format: MM/DD/YYYY"

# If date provided (MM/DD/YYYY format) → go to lmp-date-received

# Node ID: lmp-date-received
# "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."
# Next node: null (Calculate gestational age and provide response, then wait for user's next message)
# Node ID: ask-for-edd
# "Not a problem. Do you know your Estimated Due Date? Reply Y or N (again, it's OK if you're uncertain)"

# If Y or Yes → go to enter-edd-date
# If N or No → go to check-penn-medicine-system

# Node ID: enter-edd-date
# "Great. Please reply in this format: MM/DD/YYYY"

# If date provided (MM/DD/YYYY format) → go to edd-date-received

# Node ID: edd-date-received
# "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."
# Next node: null (Calculate gestational age and provide response, then wait for user's next message)
# Node ID: check-penn-medicine-system
# "We know it can be hard to keep track of periods sometimes. Have you been seen in the Penn Medicine system? Reply Y or N"

# If Y or Yes → go to penn-system-confirmation
# If N or No → go to register-as-new-patient

# Node ID: penn-system-confirmation
# "Perfect. Over the next few days we're here for you and ready to help with your next moves. Stay tuned!"
# Next node: null
# Node ID: register-as-new-patient
# "Not a problem. Contact the call center $clinic_phone$ and have them add you as a 'new patient'. This way, if you need any assistance in the future, we'll be able to help you quickly."
# Next node: null
# Care Options Routing
# Node ID: prenatal-provider-check
# "Do you have a prenatal provider? Reply Y or N"

# If Y or Yes → go to schedule-appointment
# If N or No → go to schedule-with-penn-obgyn

# Node ID: schedule-appointment
# "Great, it sounds like you're on the right track! Call $clinic_phone$ to make an appointment."
# Next node: null
# Node ID: schedule-with-penn-obgyn
# "It's important to receive prenatal care early on. Sometimes it takes a few weeks to get in. Call $clinic_phone$ to schedule an appointment with Penn OB/GYN Associates or Dickens Clinic."
# Next node: null
# Node ID: connect-to-peace-clinic
# "We understand your emotions, and it's important to take the necessary time to navigate through them. The team at The Pregnancy Early Access Center (PEACE) provides abortion, miscarriage management, and pregnancy prevention. Call $clinic_phone$ to schedule an appointment with PEACE. https://www.pennmedicine.org/make-an-appointment"
# Next node: null
# Node ID: connect-to-peace-for-abortion
# "Call $clinic_phone$ to be scheduled with PEACE. https://www.pennmedicine.org/make-an-appointment We'll check back with you to make sure you're connected to care. We have a few more questions before your visit. It'll help us find the right care for you."
# Next node: null
# Negative Test Results
# Node ID: negative-test-result-response
# "Thanks for sharing. If you have any questions or if there's anything you'd like to talk about, we're here for you. Contact the call center $clinic_phone$ for any follow-ups & to make an appointment with your OB/GYN.
# Being a part of your care journey has been a real privilege. Since I only guide you through this brief period, I won't be available for texting after today. If you find yourself pregnant in the future, text me back at this number, and I'll be here to support you once again."
# Next node: null
# Symptom Management
# Node ID: symptoms-response
# "We understand questions and concerns come up. You can try texting this number with your question, and I may have an answer. This isn't an emergency line, so it's best to reach out to your provider if you have an urgent concern by calling $clinic_phone$. If you're worried or feel like this is something serious – it's essential to seek medical attention.
# What symptom are you experiencing? Reply 'Bleeding', 'Nausea', 'Vomiting', 'Pain', or 'Other'"

# If "Bleeding" → go to vaginal-bleeding-1st-trimester
# If "Nausea" → go to nausea-1st-trimester
# If "Vomiting" → go to vomiting-1st-trimester
# If "Pain" → go to pain-early-pregnancy
# If "Other" → go to default-response

# Bleeding Assessment
# Node ID: vaginal-bleeding-1st-trimester
# "Let me ask a few more questions about your medical history to determine the next best steps. Have you ever had an ectopic pregnancy (this is a pregnancy in your tube or anywhere outside of your uterus)? Reply Y or N"

# If Y or Yes → go to immediate-provider-visit
# If N or No → go to heavy-bleeding-check

# Node ID: immediate-provider-visit
# "Considering your past history, you should be seen by a provider immediately. Now: Call your OB/GYN ASAP (Call $clinic_phone$ to make an urgent appointment with PEACE – the Early Pregnancy Access Center – if you do not have a provider) If you're not feeling well or have a medical emergency, visit your local ER."
# Next node: null
# Node ID: heavy-bleeding-check
# "Over the past 2 hours, is your bleeding so heavy that you've filled 4 or more super pads? Reply Y or N"

# If Y or Yes → go to urgent-provider-visit-for-heavy-bleeding
# If N or No → go to pain-or-cramping-check

# Node ID: urgent-provider-visit-for-heavy-bleeding
# "This amount of bleeding during pregnancy means you should be seen by a provider immediately. Now: Call your OB/GYN. (Call $clinic_phone$, option 5 to make an urgent appointment with PEACE – the Early Pregnancy Access Center) If you're not feeling well or have a medical emergency, visit your local ER."
# Next node: null
# Node ID: pain-or-cramping-check
# "Are you in any pain or cramping? Reply Y or N"

# If Y or Yes → go to er-visit-check-during-pregnancy
# If N or No → go to monitor-bleeding

# Node ID: er-visit-check-during-pregnancy
# "Have you been to the ER during this pregnancy? Reply Y or N"

# If Y or Yes → go to report-bleeding-to-provider
# If N or No → go to monitor-bleeding-at-home

# Node ID: report-bleeding-to-provider
# "Any amount of bleeding during pregnancy should be reported to a provider. Call your provider for guidance.
# If you continue bleeding, getting checked out by a provider can be helpful. Keep an eye on your bleeding. We'll check in on you again tomorrow. If the bleeding continues or you feel worse, make sure you contact a provider. And remember: If you do not feel well or you're having a medical emergency — especially if you've filled 4 or more super pads in two hours — go to your local ER. If you still have questions or concerns, call PEACE $clinic_phone$, option 5."
# Next node: null
# Node ID: monitor-bleeding-at-home
# "While bleeding or spotting in early pregnancy can be alarming, it's pretty common. Based on your exam in the ER, it's okay to keep an eye on it from home. If you notice new symptoms, feel worse, or are concerned about your health and need to be seen urgently, go to the emergency department.
# If you continue bleeding, getting checked out by a provider can be helpful. Keep an eye on your bleeding. We'll check in on you again tomorrow. If the bleeding continues or you feel worse, make sure you contact a provider. And remember: If you do not feel well or you're having a medical emergency — especially if you've filled 4 or more super pads in two hours — go to your local ER. If you still have questions or concerns, call PEACE $clinic_phone$, option 5."
# Next node: null
# Node ID: monitor-bleeding
# "While bleeding or spotting in early pregnancy can be alarming, it's actually quite common and doesn't always mean a miscarriage. But keeping an eye on it is important. Always check the color of the blood (brown, pink, or bright red) and keep a note.
# If you continue bleeding, getting checked out by a provider can be helpful. Keep an eye on your bleeding. We'll check in on you again tomorrow. If the bleeding continues or you feel worse, make sure you contact a provider. And remember: If you do not feel well or you're having a medical emergency — especially if you've filled 4 or more super pads in two hours — go to your local ER. If you still have questions or concerns, call PEACE $clinic_phone$, option 5."
# Next node: null
# Nausea Management
# Node ID: nausea-1st-trimester
# "We're sorry to hear it—and we're here to help. Nausea and vomiting are very common during pregnancy. Staying hydrated and eating small, frequent meals can help, along with natural remedies like ginger and vitamin B6. Let's make sure there's nothing you need to be seen for right away. Have you been able to keep food or liquids in your stomach for 24 hours? Reply Y or N"

# If Y or Yes → go to nausea-management-advice
# If N or No → go to nausea-treatment-options

# Node ID: nausea-management-advice
# "OK, thanks for letting us know. Nausea and vomiting are very common during pregnancy. To feel better, staying hydrated and eating small, frequent meals (even before you feel hungry) is important. Avoid an empty stomach by taking small sips of water or nibbling on bland snacks throughout the day. Try eating protein-rich foods like meat or beans.
# If your nausea gets worse and you can't keep foods or liquids down for over 24 hours, contact your provider or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you!"

# Next node: null

# Node ID: nausea-treatment-options

# "OK, thanks for letting us know. There are safe treatment options for you! Your care team at Penn recommends trying a natural remedy like ginger and vitamin B6 (take one 25mg tablet every 8 hours as needed). If this isn't working, you can try unisom – an over-the-counter medication – unless you have an allergy. Let your provider know. You can use this medicine until they call you back.
# If your nausea gets worse and you can't keep foods or liquids down for over 24 hours, contact your provider or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you!"
# Next node: null
# Vomiting Management
# Node ID: vomiting-1st-trimester
# "Hi $patient_firstName$, It sounds like you're concerned about vomiting. Is that correct? Reply Y or N"

# If N or No → go to default-response
# If Y or Yes → go to nausea-1st-trimester

# Pain Management
# Node ID: pain-early-pregnancy
# "We're sorry to hear this. It sounds like you're concerned about pain, is that correct? Reply Y or N"

# If N or No → go to default-response
# If Y or Yes → go to vaginal-bleeding-1st-trimester

# Medications Management
# Node ID: medications-response
# "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy
# Do you have questions about:
# A) Medication management
# B) Medications that are safe in pregnancy
# C) Abortion medications
# Reply with just one letter."

# If A → go to medication-management-response
# If B → go to safe-medications-response
# If C → go to abortion-medications-response

# Node ID: medication-management-response
# "Medication management during pregnancy can be tricky. Always check with your provider before starting or stopping any medication. They'll work with you to ensure you're taking the safest options available."
# Next node: null
# Node ID: safe-medications-response
# "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"

# Next node: null

# Node ID: abortion-medications-response
# "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"
# Next node: null
# Pregnancy Loss Management
# Node ID: pregnancy-loss-response
# "It sounds like you're concerned about pregnancy loss (miscarriage), is that correct? Reply Y or N"

# If N or No → go to default-response
# If Y or Yes → go to confirm-pregnancy-loss

# Node ID: confirm-pregnancy-loss
# "We're sorry to hear this. Has a healthcare provider confirmed an early pregnancy loss (that your pregnancy stopped growing)? A) Yes B) No C) Not Sure Reply with just the letter"

# If (Yes) → go to support-and-schedule-appointment
# If (No)  → go to vaginal-bleeding-1st-trimester
# If  Unsure or Not Sture → go to schedule-peace-appointment

# Node ID: support-and-schedule-appointment
# "We're here to listen and offer support. It's helpful to talk about the options to manage this. We can help schedule you an appointment. Call $clinic_phone$ and ask for the PEACE clinic. We'll check in on you in a few days."
# Next node: null

# Node ID: schedule-peace-appointment
# "Sorry to hear this has been confusing for you. We recommend scheduling an appointment with PEACE so that they can help explain what's going on. Call $clinic_phone$, option 5 and we can help schedule you a visit so that you can get the information you need, and your situation becomes more clear."
# Next node: go to vaginal-bleeding-1st-trimester
# Other Menu Responses

# Node ID: appointment-response

# "Unfortunately, I can't see when your appointment is, but you can call the clinic to find out more information. If I don't answer all of your questions, or you have a more complex question, you can contact the Penn care team at $clinic_phone$ who can give you further instructions. I can also provide some general information about what to expect at a visit. Just ask me."

# Next node: Route based on user's next message

# If user asks about symptoms → go to symptoms-response
# If user asks about medications → go to medications-response
# If user asks about appointments → stay in appointment-response
# If user asks general questions → go to menu-items
# If user says thanks/goodbye → go to nothing-response

# Node ID: peace-visit-response
# "The Pregnancy Early Access Center is a support team who's here to help you think through the next steps and make sure you have all the information you need. They're a listening ear, judgment-free and will support any decision you make. You can have an abortion, you can place the baby for adoption or you can continue the pregnancy and choose to parent. They are there to listen to you and answer any of your questions.
# Sometimes, they use an ultrasound to confirm how far along you are to help in discussing options for your pregnancy. If you're considering an abortion, they'll review both types of abortion (medical and surgical) and tell you about the required counseling and consent (must be done at least 24 hours before the procedure). They can also discuss financial assistance and connect you with resources to help cover the cost of care."
# Next node: Route based on user's next message

# If user asks about symptoms → go to symptoms-response
# If user asks about medications → go to medications-response
# If user asks about appointments → go to appointment-response
# If user asks general questions → go to menu-items
# If user says thanks/goodbye → go to nothing-response

# Node ID: something-else-response
# "OK, I understand and I might be able to help. Try texting your question to this number. Remember, I do best with short sentences about one topic. If you need more urgent help or prefer to speak to someone on the phone, you can reach your care team at $clinic_phone$ & ask for your clinic. If you're worried or feel like this is something serious – it's essential to seek medical attention."
# Next node: Route based on user's next message

# If user provides specific question → route to appropriate node
# If unclear → go to menu-items

# Node ID: nothing-response
# "OK, remember you can text this number at any time with questions or concerns."
# Next node: null
# Node ID: default-response
# "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."
# Next node: Route based on user's next message

# If user mentions symptoms → go to symptoms-response
# If user asks general questions → go to menu-items
# If no clear direction → go to menu-items

# Survey Flows
# Node ID: pre-program-impact-survey
# "Hi there, $patient_firstName$. As you start this program, we'd love to hear your thoughts! We're asking a few questions to understand how you're feeling about managing your early pregnancy.
# On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"

# If number provided (0-10) → go to knowledge-rating

# Node ID: knowledge-rating
# "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"

# If number provided (0-10) → go to thank-you-message

# Node ID: thank-you-message
# "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."
# Next node: null 
# Node ID: post-program-impact-survey
# "Hi $patient_firstname$, glad you finished the program! Sharing your thoughts would be a huge help in making the program even better for others."

# If response provided → go to post-program-confidence-rating

# Node ID: post-program-confidence-rating
# "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"

# If number provided (0-10) → go to post-program-knowledge-rating

# Node ID: post-program-knowledge-rating
# "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"

# If number provided (0-10) → go to post-program-thank-you

# Node ID: post-program-thank-you
# "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."
# Next node: null
# Node ID: nps-quantitative-survey
# "Hi $patient_firstname$, I have two quick questions about using this text messaging service (last time I promise):"

# If response provided → go to likelihood-to-recommend

# Node ID: likelihood-to-recommend
# "On a 0-10 scale, with 10 being 'extremely likely,' how likely are you to recommend this text message program to someone with the same (or similar) situation? Reply with a number 0-10"

# If number provided (0-10) → go to nps-qualitative-survey

# Node ID: nps-qualitative-survey
# "Thanks for your response. What's the reason for your score?"

# If response provided → go to feedback-acknowledgment

# Node ID: feedback-acknowledgment
# "Thanks, your feedback helps us improve future programs."
# Next node: null
# Pregnancy Intention Assessment
# Node ID: pregnancy-intention-survey
# "$patient_firstName$, pregnancy can stir up many different emotions. These can range from uncertainty and regret to joy and happiness. You might even feel multiple emotions at the same time. It's okay to have these feelings. We're here to help support you through it all. I'm checking in on how you're feeling about being pregnant. Are you: A) Excited B) Not sure C) Not excited Reply with just 1 letter"

# If A → go to excited-response
# If B → go to not-sure-response
# If C → go to not-excited-response

# Node ID: excited-response
# "Well that is exciting news! Some people feel excited, and want to continue their pregnancy, and others aren't sure. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you.
# Would you prefer us to connect you with providers who can help with: A) Continuing my pregnancy B) Talking with me about what my options are C) Getting an abortion Reply with just 1 letter"

# If A → go to prenatal-provider-check
# If B → go to connect-to-peace-clinic
# If C → go to connect-to-peace-for-abortion

# Node ID: not-sure-response
# "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you.
# Would you prefer us to connect you with providers who can help with: A) Continuing my pregnancy B) Talking with me about what my options are C) Getting an abortion Reply with just 1 letter"

# If A → go to prenatal-provider-check
# If B → go to connect-to-peace-clinic
# If C → go to connect-to-peace-for-abortion

# Node ID: not-excited-response
# "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you.
# Would you prefer us to connect you with providers who can help with: A) Continuing my pregnancy B) Talking with me about what my options are C) Getting an abortion Reply with just 1 letter"

# If A → go to prenatal-provider-check
# If B → go to connect-to-peace-clinic
# If C → go to connect-to-peace-for-abortion
# """
        
        flow_instruction_context = flow_instructions
        # print(f"[FLOW INSTURCTIONS] {flow_instruction_context}")
        document_context_section = f"""
Relevant Document Content:
{document_context}

You are a helpful assistant tasked with providing accurate, specific, and context-aware responses. Follow these steps:
1. Identify the user's intent from the message and conversation history.
2. **IMPORTANT**: Scan the Relevant Document Content for any URLs, phone numbers, email addresses, medical information, or other specific resources.
3. **CRITICAL REQUIREMENT**: If ANY resources like URLs, phone numbers, contact information, medication information, or treatment options are found, include them verbatim in your response.
4. Generate a natural, conversational response addressing the user's query, incorporating document content as needed.
5. Maintain continuity with the conversation history.
6. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION, but prioritize document content for specific details.
7. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
8. If no relevant document content is found, provide a helpful response based on the flow logic or general knowledge.
9. Double-check that all resource links, phone numbers, medication names, and contact methods from the document context are included.
""" if document_context else """
You are a helpful assistant tasked with providing accurate and context-aware responses. Follow these steps:
1. Identify the user's intent from the message and conversation history.
2. Generate a natural, conversational response addressing the user's query.
3. Maintain continuity with the conversation history.
4. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION.
5. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
"""
        # LLM prompt
        prompt = f"""
You are a friendly, conversational assistant helping a patient with healthcare interactions. Your goal is to have a natural, human-like conversation. You need to:

1. Check the patient's profile to see if any required fields are missing, and ask for them one at a time if needed.
2. If the profile is complete, guide the conversation using flow instructions as a loose guide, but respond naturally to the user's message.
3. If the user's message doesn't match the current flow instructions, use document content or general knowledge to provide a helpful, relevant response.
4. When the user asks specific questions about medical information, treatments, or medications, ALWAYS check the document content first and provide that information.
5. Maintain a warm, empathetic tone, like you're talking to a friend.

Current Date (MM/DD/YYYY): {current_date}

User Message: "{message}"

Conversation History:
{conversation_history}

Patient ID: {patientId}

Assistant ID: {assistantId}

Flow ID: {flow_id}

Patient Profile (includes phone and organization_id):
{patient_fields}

Structured Flow Instructions (Use this to guide conversation flow based on user responses):
{flow_instruction_context}

Document Content:
{document_context_section}

Current Node ID :
{current_node_id}

Session Data:
{json.dumps(session_data, indent=2)}

Instructions:
1. **Check Patient Profile**:
   - Review the `Patient Profile` JSON to identify any fields (excluding `id`, `mrn`, `created_at`, `updated_at`, `organization_id`, `phone`) that are null, empty, or missing.
   - If any fields are missing, select one to ask for in a natural way (e.g., "Hey, I don't have your first name yet, could you share it?").
   - Validate user input based on the field type:
     - Text fields (e.g., names): Alphabetic characters, spaces, or hyphens only (/^[a-zA-Z\s-]+$/).
     - Dates (e.g., date_of_birth): Valid date, convertible to MM/DD/YYYY, not after {current_date}.
   - If the user provides a valid value for the requested field, issue an `UPDATE_PATIENT` command with:
     - patient_id: {patientId}
     - field_name: the field (e.g., "first_name")
     - field_value: the validated value
   - If the input is invalid, ask again with a friendly clarification (e.g., "Sorry, that doesn't look like a valid date. Could you try again, like 03/29/1996?").
   - If no fields are missing, proceed to conversation flow.
   - Use `organization_id` and `phone` from the `Patient Profile`, not from the request.
   IMPORTANT: Only ever ask for these missing profile fields—first name, last name, date of birth, gender, and email.  
     Do ​not​ ask for insurance, address, emergency contact, or any other fields, even if they’re empty.  
    
2. **Conversation Flow**:
   - When a flow instruction indicates "Flow ends" or  next node id is null, the analyze the user message next_node_id to decide.
   - *CRITICAL* Do not Repeat the Same `Content` To The User Over and Over again, if the next node id is null , analyze the last {message} to Set the next node id or See the `Document Content` To Provide the Best Possible Answer
   - Use the `Current Node`, `User Message`, `Conversation History` and the `Structured Flow Instructions` to decide the what next question to ask and what is the next node id. 
   - If the patient profile is complete, use `Current Flow Instructions` OR `Structured Flow Instructions` as a guide to suggest what to ask or discuss next.
   - For example, if the user mentions bleeding, follow the Bleeding branch by asking the appropriate questions.
   - If the user mentions pregnancy test, ask if they've had a positive test, and then follow up with LMP questions.
   - If the user asks about medications or treatments, check the Document Content first.
   - Interpret the instructions as prompts for conversation topics (e.g., if the instruction says "Ask about symptoms," say something like, "So, how have you been feeling lately? Any symptoms you want to talk about?").
   - If the user's message matches the flow instructions, use the instructions to guide the next question or action, and update `next_node_id` to the next relevant node.
   - If the user's message doesn't match the flow instructions, use `Document Content` to provide a relevant response if available, or fall back to general knowledge with a natural reply (e.g., "I can help with that! Could you tell me more about what you need?").
   - For date-related instructions (e.g., gestational age):
     - Validate dates as MM/DD/YYYY, not after {current_date}.
     - For gestational age, calculate weeks from the provided date to {current_date}, determine trimester (First: ≤12 weeks, Second: 13–27 weeks, Third: ≥28 weeks), and include in the response (e.g., "You're about 20 weeks along, in your second trimester!").
     - Store in `state_updates` as `{{ "gestational_age_weeks": X, "trimester": "Second" }}`.
     - IMP: Remeber If Patient provides the LMP Don't Forget to Provide the  gestational age like First Trimester or Second or Third Trimester

3. **Response Style**:
   - Always respond in a warm, conversational tone (e.g., "Hey, thanks for sharing that!" or "No worries, let's try that again.").
   - Avoid robotic phrases like "Processing node" or "Moving to next step."
   - If the user goes off-topic, acknowledge their message and gently steer back to the flow if needed (e.g., "That's interesting! By the way, I still need your last name to complete your profile. Could you share it?").
   - If all profile fields are complete and no flow instructions apply, respond to the user's message naturally, using document content or general knowledge.

4. **Database Operations**:
   - Issue `UPDATE_PATIENT` when a valid field is provided, with `patient_id`, `field_name`, and `field_value`.
   - Issue `CREATE_PATIENT` only if the patient record is missing (unlikely, as patientId is provided), using `organization_id` and `phone` from session_data.

5. **Flow Progression**:
   - Update `next_node_id` based on the flow instructions if the user's response matches, or keep it the same if the response is off-topic or a field is still being collected.
   - Store any relevant session updates (e.g., gestational age) in `state_updates`.
6. **General Instructions**
    - If Conversation History  are found always start with **menu items* Node. 
    - If Any Nodes Have more than 2 options like A, B, C, D, E, etc then If User Message is E or D or Any of These Single Letter Then Match the response and go to that Node rather asking same question over again. 
    - **IMP** 
      - DO NOT REPOND WITH "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."
      - Instead Calculate the gestational age in the Current Node Using {current_date} and provide reponse For gestational age, calculate weeks from the provided date to {current_date}, determine trimester (First: ≤12 weeks, Second: 13–27 weeks, Third: ≥28 weeks), and include in the response (e.g., "You're about 20 weeks along, in your second trimester!").

7. **Response Structure**:
   Return a JSON object:
   ```json
   {{
     "content": "Your friendly response to the user",
     "next_node_id": "ID of the next node or current node",
     "state_updates": {{"key": "value"}},
     "database_operation": {{
       "operation": "UPDATE_PATIENT | CREATE_PATIENT",
       "parameters": {{
         "patient_id": "string",
         "field_name": "string",
         "field_value": "string"
       }}
     }} // Optional, only when updating/creating
   }}
   ```

Examples:
- Profile: {{"first_name": null, "last_name": null, "date_of_birth": null}}, Message: "hi"
  - Response: {{"content": "Hey, nice to hear from you! I need a bit of info to get you set up. Could you share your first name?", "next_node_id": null, "state_updates": {{}}}}
- Profile: {{"first_name": "Shenal", "last_name": null, "date_of_birth": null}}, Message: "Jones"
  - Response: {{"content": "Awesome, thanks for sharing, Shenal Jones! What's your date of birth, like 03/29/1996?", "next_node_id": null, "state_updates": {{}}, "database_operation": {{"operation": "UPDATE_PATIENT", "parameters": {{"patient_id": "{patientId}", "field_name": "last_name", "field_value": "Jones"}}}}}}
- Profile: {{"first_name": "Shenal", "last_name": "Jones", "date_of_birth": "03/29/1996"}}, Flow: "Ask about symptoms", Message: "I have a headache"
  - Response: {{"content": "Sorry to hear about your headache! How long have you been feeling this way?", "next_node_id": "node_symptom_duration", "state_updates": {{}}}}
- Profile complete, Flow: "Ask about symptoms", Message: "Book an appointment"
  - Response: {{"content": "Sure thing, let's get you an appointment! When are you free?", "next_node_id": "node_appointment", "state_updates": {{}}}}
"""

        # Call LLM
        response_text = Settings.llm.complete(prompt).text  # Replace with Settings.llm.complete
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        response_data = json.loads(response_text)

        content = response_data.get("content", "I'm having trouble processing your request.")
        next_node_id = response_data.get("next_node_id")
        state_updates = response_data.get("state_updates", {})
        database_operation = response_data.get("database_operation")

        # Execute database operation
        operation_result = None
        if database_operation:
            operation = database_operation.get("operation")
            parameters = database_operation.get("parameters", {})
            try:
                if operation == "UPDATE_PATIENT":
                    patient = db.query(Patient).filter(Patient.id == patientId).first()
                    if not patient:
                        raise HTTPException(status_code=404, detail="Patient not found")
                    setattr(patient, parameters["field_name"], parameters["field_value"])
                    patient.updated_at = datetime.utcnow()
                    db.commit()
                    db.refresh(patient)
                    operation_result = {
                        "id": patient.id,
                        "mrn": patient.mrn,
                        "first_name": patient.first_name,
                        "last_name": patient.last_name,
                        "date_of_birth": patient.date_of_birth,
                        "phone": patient.phone,
                        "organization_id": patient.organization_id
                    }
                    # Update JSON file
                    patient_path = f"patients/{patient.id}.json"
                    os.makedirs(os.path.dirname(patient_path), exist_ok=True)
                    with open(patient_path, "w") as f:
                        patient_dict = {
                            "id": patient.id,
                            "mrn": patient.mrn,
                            "first_name": patient.first_name,
                            "last_name": patient.last_name,
                            "date_of_birth": patient.date_of_birth,
                            "phone": patient.phone,
                            "organization_id": patient.organization_id,
                            "created_at": patient.created_at.isoformat() if patient.created_at else None,
                            "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
                        }
                        json.dump(patient_dict, f, indent=2)
                    content += f"\nProfile updated successfully!"
                elif operation == "CREATE_PATIENT":
                    # Fallback if patientId is invalid; use session_data for phone/organization_id
                    mrn = generate_mrn()
                    patient = Patient(
                        id=str(uuid.uuid4()),
                        mrn=mrn,
                        first_name=parameters.get("first_name", ""),
                        last_name=parameters.get("last_name", ""),
                        date_of_birth=parameters.get("date_of_birth"),
                        phone=session_data.get("phone", "unknown"),
                        organization_id=session_data.get("organization_id", "default_org"),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(patient)
                    db.commit()
                    db.refresh(patient)
                    operation_result = {
                        "id": patient.id,
                        "mrn": patient.mrn,
                        "first_name": patient.first_name,
                        "last_name": patient.last_name,
                        "date_of_birth": patient.date_of_birth,
                        "phone": patient.phone,
                        "organization_id": patient.organization_id
                    }
                    # Save JSON file
                    patient_path = f"patients/{patient.id}.json"
                    os.makedirs(os.path.dirname(patient_path), exist_ok=True)
                    with open(patient_path, "w") as f:
                        patient_dict = {
                            "id": patient.id,
                            "mrn": patient.mrn,
                            "first_name": patient.first_name,
                            "last_name": patient.last_name,
                            "date_of_birth": patient.date_of_birth,
                            "phone": patient.phone,
                            "organization_id": patient.organization_id,
                            "created_at": patient.created_at.isoformat() if patient.created_at else None,
                            "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
                        }
                        json.dump(patient_dict, f, indent=2)
                    content += f"\nProfile created successfully!"
            except Exception as e:
                db.rollback()
                print(f"Database operation failed: {str(e)}")
                content += f"\nSorry, I couldn’t update your profile. Let’s try again."
                response_data["next_node_id"] = current_node_id

        print(f"Response: {content}")
        print(f"Next node ID: {next_node_id}")
        print("==== PATIENT ONBOARDING/CHAT COMPLETE ====\n")

        response = {
            "content": content,
            "next_node_id": next_node_id,
            "state_updates": state_updates
        }
        if operation_result:
            response["operation_result"] = operation_result
        return response

    except Exception as e:
        print(f"ERROR in patient_onboarding: {str(e)}")
        return {
            "error": f"Failed to process message: {str(e)}",
            "content": "I'm having trouble processing your request. Please try again."
        }


# @app.post("/api/patient_onboarding")
# async def patient_onboarding(request: Dict, db: Session = Depends(get_db)):
#     try:
#         print("\n==== STARTING PATIENT ONBOARDING/CHAT ====")
#         from llama_index.retrievers.bm25 import BM25Retriever

#         # Request validation
#         message = request.get("message", "").strip()
#         sessionId = request.get("sessionId", "")
#         patientId = request.get("patientId", "")
#         assistantId = request.get("assistantId", "")
#         flow_id = request.get("flow_id", "")
#         session_data = request.get("session_data", {})
#         previous_messages = request.get("previous_messages", [])
#         flow_instructions = request.get("instruction_type")

#         if not message:
#             raise HTTPException(status_code=400, detail="Message is required")
#         if not sessionId:
#             raise HTTPException(status_code=400, detail="Session ID is required")
#         if not patientId:
#             raise HTTPException(status_code=400, detail="Patient ID is required")
#         if not assistantId:
#             raise HTTPException(status_code=400, detail="Assistant ID is required")
#         if not flow_id:
#             raise HTTPException(status_code=400, detail="Flow ID is required")

#         # --- Import BM25Retriever and RetrieverQueryEngine ---
#         from llama_index.retrievers.bm25 import BM25Retriever
#         from llama_index.core.query_engine import RetrieverQueryEngine
#         from llama_index.core import VectorStoreIndex, StorageContext
#         from llama_index.core.retrievers import VectorIndexRetriever
#         from llama_index.core.retrievers import QueryFusionRetriever

#         # ----------------------------------------------------
#         query_to_use = message
#         if previous_messages:
#             print(f"Previous messages found ({len(previous_messages)}). Building contextual query.")
#             context_messages = previous_messages[-4:] # Get last 3 messages

#             context_str = "Conversation history:\n"
#             for msg_obj in context_messages:
#                  role = msg_obj.get('role', 'unknown').capitalize()
#                  content = msg_obj.get('content', 'N/A')
#                  context_str += f"{role}: {content}\n"

#             # Combine context with the current message to form the query
#             # Structure the query to help the retriever understand it's a follow-up
#             # query_to_use = f"{context_str}\nCurrent user input: {message}\nConsidering this, what is the relevant flow instruction or the next step?"
#             query_to_use = f"{context_str}\nCurrent user input: {message}\nConsidering this, what is the relevant flow instruction or the next step? Respond only with the exact flow instruction text from the retrieved nodes unless no relevant node is found, then provide a general response."
#             print(f"Augmented Query for Retrieval:\n{query_to_use}")
#         else:
#             print("No previous messages found. Using original message for retrieval.")
#             # query_to_use remains the original message



#         if flow_instructions == "indexed" and assistantId:
#             try:    
#                 base_dir = os.path.abspath(os.path.dirname(__file__))
#                 persist_dir = os.path.join(base_dir, "flow_instructions_storage", f"flow_instruction_{assistantId}")
#                 print(f"Attempting to load index from: {persist_dir}")

#                 if os.path.exists(persist_dir):
#                     # Load the storage context from the persist directory
#                     storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
#                     print("Loading index from storage...")
#                     index = load_index_from_storage(storage_context)
#                     print("Index loaded successfully.")

#                     # Create VectorStoreRetriever
#                     print("Building VectorStoreRetriever...")
#                     vector_retriever = VectorIndexRetriever(
#                         index=index,
#                         similarity_top_k=10,  # Retrieve top 5 most similar nodes
#                         embed_model=Settings.embed_model  # Use a lightweight embedding model
#                     )
#                     print("VectorStoreRetriever built.")

#                     # Create query engine
#                     print("Creating query engine using VectorStoreRetriever...")
#                     query_engine = RetrieverQueryEngine(retriever=vector_retriever)
#                 # Define the persist directory path for this assistant's flow instructions
#                 # base_dir = os.path.abspath(os.path.dirname(__file__))
#                 # persist_dir = os.path.join(base_dir, "flow_instructions_storage", f"flow_instruction_{assistantId}")

#                 # print(f"Attempting to load index from: {persist_dir}")

#                 # # Check if the directory exists
#                 # if os.path.exists(persist_dir):
#                 #     # Load the storage context from the persist directory
#                 #     storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

#                 #     # Load the index from storage
#                 #     print("Loading index from storage...")
#                 #     index = load_index_from_storage(storage_context)
#                 #     print("Index loaded successfully.")

#                 #     # --- Create the BM25 Retriever ---
#                 #     # Retrieve all nodes from the index's document store to build the BM25 index over them.
#                 #     all_nodes = list(index.docstore.docs.values())

#                 #     bm25_retriever = None # Initialize to None
#                 #     if not all_nodes:
#                 #         print("Warning: Could not retrieve nodes from index docstore to build BM25Retriever.")
#                 #     else:
#                 #         # Use from_defaults with the retrieved nodes
#                 #         print(f"Building BM25Retriever from {len(all_nodes)} nodes...")
#                 #         # Set similarity_top_k here when creating the retriever instance
#                 #         bm25_retriever = BM25Retriever.from_defaults(nodes=all_nodes, similarity_top_k=5)
#                 #         print("BM25Retriever built.")

#                 #     # --- Create a query engine ---
#                 #     # Use RetrieverQueryEngine directly when using a custom retriever
#                 #     query_engine = None # Initialize query_engine

#                 #     if bm25_retriever:
#                 #         # Create the query engine using the custom BM25 retriever
#                 #         # RetrieverQueryEngine will use the default LLM from Settings for synthesis
#                 #         print("Creating query engine using BM25Retriever...")
#                 #         query_engine = RetrieverQueryEngine(retriever=bm25_retriever)
#                 #     else:
#                 #         # Fallback: If BM25 failed to build, use the index's default vector retriever
#                 #         print("Falling back to creating query engine using default VectorRetriever...")
#                 #         # Use index.as_query_engine() which wraps the default vector retriever
#                 #         query_engine = index.as_query_engine(similarity_top_k=5) # Configure default retriever here

#                 #     if query_engine is None:
#                 #         raise ValueError("Failed to create any query engine (BM25 or default).")
                    

                    
#                     # --- Keep the rest of the query logic ---
#                     print(f"Querying index with message: '{query_to_use}'")
#                     response = query_engine.query(query_to_use)

#                     retrieved_text = response.response
#                     source_nodes = response.source_nodes # This will now be the nodes retrieved by the active retriever

#                     print(f"Successfully queried index for assistant: {assistantId}")
#                     print(f"LLM Synthesized Response: {retrieved_text}")

#                     print("\n--- Retrieved Source Nodes ---")
#                     if source_nodes:
#                         retrieved_texts = []
#                         # Check if nodes have scores before trying to format
#                         score_available = hasattr(source_nodes[0], 'score') if source_nodes else False
#                         for i, node_with_score in enumerate(source_nodes):
#                             score_str = f" (Score: {node_with_score.score:.4f})" if score_available else ""
#                             retrieved_texts.append(node_with_score.node.text)
#                             # print(f"Node {i+1}{score_str}:")
#                             # print(node_with_score.node.text)
#                             # print("-" * 20)
#                     else:
#                         print("No source nodes were retrieved by the retriever.")
#                     print("----------------------------\n")

#                     # flow_instructions = retrieved_text # Or the raw text from source_nodes if preferred
#                     flow_instructions = "\n---\n".join(retrieved_texts)

#                 else:
#                     print(f"Warning: Flow instructions directory not found for assistant: {assistantId} at {persist_dir}")
#                     flow_instructions = "No indexed flow instructions found."

#             except Exception as e:
#                 print(f"Error retrieving indexed flow instructions: {str(e)}")
#                 # Ensure traceback is imported if you use it
#                 # print(f"Stacktrace: {traceback.format_exc()}")
#                 flow_instructions = f"Error retrieving flow instructions: {str(e)}"
        
#         # if flow_instructions == "indexed" and assistantId:
#         #     try:
#         #         base_dir = os.path.abspath(os.path.dirname(__file__))
#         #         persist_dir = os.path.join(base_dir, "flow_instructions_storage", f"flow_instruction_{assistantId}")

#         #         print(f"Attempting to load index from: {persist_dir}")

#         #         index = None # Initialize index
#         #         # Check if the directory exists
#         #         if os.path.exists(persist_dir):
#         #             # Load the storage context from the persist directory
#         #             storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

#         #             # Load the index from storage
#         #             print("Loading index from storage...")
#         #             index = load_index_from_storage(storage_context)
#         #             print("Index loaded successfully.")
#         #         else:
#         #             print(f"Warning: Flow instructions directory not found for assistant: {assistantId} at {persist_dir}. Cannot load index.")


#         #         # Initialize retrievers - proceed even if index wasn't loaded,
#         #         # though BM25 needs nodes from docstore which comes from index.
#         #         # Vector retriever *requires* the index.
#         #         bm25_retriever = None
#         #         vector_retriever = None
#         #         retrievers_list = []

#         #         # Create BM25 Retriever (needs nodes from loaded index)
#         #         if index:
#         #             all_nodes = list(index.docstore.docs.values())
#         #             if not all_nodes:
#         #                 print("Warning: Could not retrieve nodes from index docstore to build BM25Retriever. BM25 will not be used.")
#         #             else:
#         #                 print(f"Building BM25Retriever from {len(all_nodes)} nodes...")
#         #                 # similarity_top_k here is the initial fetch for BM25
#         #                 bm25_retriever = BM25Retriever.from_defaults(nodes=all_nodes, similarity_top_k=10) # Fetch more initial results
#         #                 retrievers_list.append(bm25_retriever)
#         #                 print("BM25Retriever built.")

#         #         # Create Vector Retriever (requires loaded index)
#         #         if index:
#         #             print("Building VectorIndexRetriever...")
#         #             # similarity_top_k here is the initial fetch for Vector
#         #             vector_retriever = VectorIndexRetriever(
#         #                 index=index,
#         #                 similarity_top_k=10, # Fetch more initial results
#         #                 # embed_model is picked up from global Settings unless specified
#         #             )
#         #             retrievers_list.append(vector_retriever)
#         #             print("VectorIndexRetriever built.")
#         #         else:
#         #             print("Warning: Index not loaded, cannot build VectorIndexRetriever.")


#         #         query_engine = None # Initialize query_engine

#         #         # Check if we have *any* retrievers to work with
#         #         if not retrievers_list:
#         #             print("Error: No retrievers could be initialized (index likely not found or empty).")
#         #             flow_instructions = "Indexed flow instructions not available or empty."
#         #         else:
#         #             # --- Create the QueryFusionRetriever for Hybrid Retrieval ---
                    
#         #             print(f"Building QueryFusionRetriever with {len(retrievers_list)} retrievers...")
#         #             # This retriever runs the query (or generated queries) through
#         #             # the list of retrievers and fuses the results using the mode="reciprocal_rerank".
#         #             # num_queries=4 means it will generate 3 extra queries. Set to 1 to disable.
#         #             # similarity_top_k is the *final* number of results after fusion.
#         #             fusion_retriever = QueryFusionRetriever(
#         #                 retrievers=retrievers_list,
#         #                 similarity_top_k=5, # How many *final* unique results from fusion are passed to the LLM
#         #                 num_queries=5,  # Number of queries to generate (1 + 3 generated). Set to 1 to disable.
#         #                 mode="reciprocal_rerank", # Use RRF to combine results
#         #                 use_async=False, # Recommended for speed
#         #                 verbose=True, # Good for debugging

#         #                 # query_gen_prompt="..." # Optional: override prompt for generating queries
#         #             )
#         #             print("QueryFusionRetriever built.")

#         #             # --- Create the query engine using the Fusion Retriever ---
#         #             print("Creating query engine using QueryFusionRetriever...")
#         #             query_engine = RetrieverQueryEngine(retriever=fusion_retriever)
#         #             print("Query engine built.")

#         #             # --- Query the engine ---
#         #             # Pass the augmented query to the engine. The retriever will
#         #             # potentially generate multiple queries from this, run them,
#         #             # fuse results, and then the LLM will use the original query
#         #             # and the fused nodes to synthesize the response.
#         #             print(f"Querying index with message: '{query_to_use}'")
#         #             response = query_engine.query(query_to_use)

#         #             # --- Process the response ---
#         #             # response.response contains the text synthesized by the LLM
#         #             retrieved_text = str(response) # Use str() for safety
#         #             source_nodes = response.source_nodes # Nodes returned by the fusion retriever

#         #             print(f"Successfully queried index for assistant: {assistantId}")
#         #             print(f"LLM Synthesized Response: {retrieved_text}")

#         #             print("\n--- Retrieved Source Nodes (after Fusion) ---")
#         #             if source_nodes:
#         #                 retrieved_texts = []
#         #                 # Check if nodes have scores before trying to format
#         #                 score_available = hasattr(source_nodes[0], 'score') if source_nodes else False
#         #                 for i, node_with_score in enumerate(source_nodes):
#         #                     score_str = f" (Score: {node_with_score.score:.4f})" if score_available else ""
#         #                     retrieved_texts.append(node_with_score.node.text)
#         #                     # print(f"Node {i+1}{score_str}:")
#         #                     # print(node_with_score.node.text)
#         #                     # print("-" * 20)
#         #             else:
#         #                 print("No source nodes were retrieved by the retriever.")
#         #             print("----------------------------\n")

#         #             # flow_instructions = retrieved_text # Or the raw text from source_nodes if preferred
#         #             flow_instructions = "\n---\n".join(retrieved_texts)


#         #             # --- Set the final flow_instructions ---
#         #             # Use the LLM's synthesized response! This is the key fix.


#         #     except Exception as e:
#         #         print(f"Error during indexed flow instruction retrieval: {str(e)}")
#         #         # Import traceback at the top if you uncomment this
#         #         # import traceback
#         #         # print(f"Stacktrace: {traceback.format_exc()}")
#         #         flow_instructions = f"Error retrieving flow instructions: {str(e)}"

#         # Get patient profile directly from Patient table
#         patient = db.query(Patient).filter(Patient.id == patientId).first()
#         if not patient:
#             raise HTTPException(status_code=404, detail="Patient not found")
#         patient_dict = {
#             "id": patient.id,
#             "mrn": patient.mrn,
#             "first_name": patient.first_name,
#             "last_name": patient.last_name,
#             "date_of_birth": patient.date_of_birth,
#             "gender": patient.gender,
#             "email": patient.email,
    
#         }
#             #  "phone": patient.phone,
#             # "address": patient.address,
#             # "insurance_provider": patient.insurance_provider,
#             # "insurance_id": patient.insurance_id,
#             # "primary_care_provider": patient.primary_care_provider,
#             # "emergency_contact_name": patient.emergency_contact_name,
#             # "emergency_contact_phone": patient.emergency_contact_phone,
#             # "organization_id": patient.organization_id,
#             # "created_at": patient.created_at.isoformat() if patient.created_at else None,
#             # "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
#         patient_fields = json.dumps(patient_dict, indent=2)

#         # Format conversation history
#         conversation_history = ""
#         for msg in previous_messages:
#             role = msg.get("role", "unknown")
#             content = msg.get("content", "")
#             conversation_history += f"{role}: {content}\n"

#         # Current date
#         eastern = pytz.timezone('America/New_York')
#         current_date = datetime.now(eastern).date().strftime('%m/%d/%Y')

#         # Load flow index
#         if flow_id not in app.state.flow_indices:
#             bucket = storage_client.bucket(BUCKET_NAME)
#             meta_file = f"temp_flow_{flow_id}_meta.pkl"
#             blob = bucket.blob(f"flow_metadata/{flow_id}_meta.pkl")
#             try:
#                 blob.download_to_filename(meta_file)
#                 with open(meta_file, "rb") as f:
#                     metadata = pickle.load(f)
#                 os.remove(meta_file)
#             except Exception as e:
#                 print(f"Failed to load flow index metadata: {str(e)}")
#                 return {
#                     "error": "Flow knowledge index not found",
#                     "content": "I'm having trouble processing your request."
#                 }

#             temp_dir = f"temp_flow_{flow_id}"
#             os.makedirs(temp_dir, exist_ok=True)
#             for blob in bucket.list_blobs(prefix=f"flow_indices/{flow_id}/"):
#                 local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
#                 blob.download_to_filename(local_path)

#             collection_name = metadata["collection_name"]
#             try:
#                 chroma_collection = chroma_client.get_collection(collection_name)
#                 print(f"Found existing Chroma collection {collection_name}")
#             except chromadb.errors.InvalidCollectionException:
#                 print(f"Creating new Chroma collection {collection_name}")
#                 chroma_collection = chroma_client.create_collection(collection_name)
#             vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

#             storage_context = StorageContext.from_defaults(
#                 persist_dir=temp_dir, vector_store=vector_store
#             )
#             # Use load_index_from_storage instead of VectorStoreIndex.load_from_storage
#             flow_index = load_index_from_storage(storage_context)
#             app.state.flow_indices[flow_id] = flow_index
#             shutil.rmtree(temp_dir)
#         else:
#             flow_index = app.state.flow_indices[flow_id]

#         # Get current node
#         current_node_id = session_data.get('currentNodeId')
#         print("[CURRENT NODE ID]",current_node_id)
#         current_node_doc = ""
#         # if current_node_id:
#         #     try:
#         #         # Create basic retriever with no filters
#         #         retriever = flow_index.as_retriever(similarity_top_k=10)
                
#         #         # Query directly for the node ID as text
#         #         query_str = f"NODE ID: {current_node_id}"
#         #         print(f"Querying for: '{query_str}'")
                
#         #         # Use the most basic retrieval pattern
#         #         node_docs = retriever.retrieve(query_str)
                
#         #         # Check if we got any results
#         #         if node_docs:
#         #             # Find exact match for node_id in results
#         #             exact_matches = [
#         #                 doc for doc in node_docs 
#         #                 if doc.metadata and doc.metadata.get("node_id") == current_node_id
#         #             ]
                    
#         #             if exact_matches:
#         #                 current_node_doc = exact_matches[0].get_content()
#         #                 print(f"Found exact match for node {current_node_id}")
#         #             else:
#         #                 # Just use the top result
#         #                 current_node_doc = node_docs[0].get_content()
#         #                 print(f"No exact match, using top result")
                    
#         #             print(f"Retrieved document for node {current_node_id}: {current_node_doc[:100]}...")
#         #         else:
#         #             print(f"No document found for node {current_node_id}")
#         #             current_node_doc = "No specific node instructions available."
#         #     except Exception as e:
#         #         print(f"Error retrieving node document: {str(e)}")
#         #         current_node_doc = "Error retrieving node instructions."
#         # elif not previous_messages:
#         #     starting_node_id, starting_node_doc = get_starting_node(flow_index)
#         #     if starting_node_id:
#         #         current_node_id = starting_node_id
#         #         current_node_doc = starting_node_doc
#         #         print(f"[STARTING NODE] {current_node_id, current_node_doc}")
#         #     else:
#         #         current_node_id = None
#         #         current_node_doc = "No starting node found."
       
       
#         print('[CURRENT NODE DOC]', current_node_doc)
#         # Load document index
#         document_context = ""
#         document_retriever = None
#         if assistantId and assistantId not in app.state.document_indexes:
#             bucket = storage_client.bucket(BUCKET_NAME)
#             meta_file = f"temp_doc_{assistantId}_meta.pkl"
#             blob = bucket.blob(f"document_metadata/{assistantId}_meta.pkl")
#             try:
#                 blob.download_to_filename(meta_file)
#                 with open(meta_file, "rb") as f:
#                     metadata = pickle.load(f)
#                 os.remove(meta_file)
#                 temp_dir = f"temp_doc_{assistantId}"
#                 os.makedirs(temp_dir, exist_ok=True)
#                 for blob in bucket.list_blobs(prefix=f"document_indices/{assistantId}/"):
#                     local_path = os.path.join(temp_dir, blob.name.split('/')[-1])
#                     blob.download_to_filename(local_path)
#                 collection_name = metadata["collection_name"]
#                 print("DEBUG: Entering Chroma collection block for documents")
#                 try:
#                     chroma_collection = chroma_client.get_collection(collection_name)
#                     print(f"Found existing Chroma collection {collection_name} for document index")
#                 except chromadb.errors.InvalidCollectionException:
#                     print(f"Creating new Chroma collection {collection_name} for document index")
#                     chroma_collection = chroma_client.create_collection(collection_name)
#                 vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

#                 storage_context = StorageContext.from_defaults(
#                     persist_dir=temp_dir, vector_store=vector_store
#                 )
#                 # Use load_index_from_storage instead of VectorStoreIndex.load_from_storage
#                 document_index = load_index_from_storage(storage_context)
#                 document_retriever = document_index.as_retriever(similarity_top_k=20)
#                 app.state.document_indexes[assistantId] = {
#                     "index": document_index,
#                     "retriever": document_retriever,
#                     "created_at": metadata["created_at"],
#                     "document_count": metadata["document_count"],
#                     "node_count": metadata["node_count"]
#                 }
#                 shutil.rmtree(temp_dir)
#             except Exception as e:
#                 print(f"Document index not found: {str(e)}")
#         else:
#             document_retriever = app.state.document_indexes.get(assistantId, {}).get("retriever")

#         if document_retriever:
#             print(f"Retrieving documents for query: '{message}'")
#             retrieved_nodes = document_retriever.retrieve(message)
#             document_text = ""
#             if retrieved_nodes:
#                 try:
#                     node_objs = [n.node for n in retrieved_nodes]
#                     if len(node_objs) > 1:
#                         print(f"Applying BM25 reranking to {len(node_objs)} nodes")
#                         bm25_retriever = BM25Retriever.from_defaults(
#                             nodes=node_objs, 
#                             similarity_top_k=min(5, len(node_objs))
#                         )
#                         reranked_nodes = bm25_retriever.retrieve(message)
#                         document_text = "\n\n".join([n.node.get_content() for n in reranked_nodes])
#                     else:
#                         document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#                 except Exception as e:
#                     print(f"BM25 reranking failed: {str(e)}, using vector results")
#                     document_text = "\n\n".join([n.node.get_content() for n in retrieved_nodes])
#             document_context = f"Relevant Document Content:\n{document_text}" if document_text else ""
#             print(f"Document retrieval complete, found content with {len(document_context)} characters")
#         else:
#             print("No document retriever available, proceeding without document context")

#         print('[DOCUMENT CONTEXT]', document_context[:200])

#         # flow_instruction_context = f"""
# # Current Flow Instructions:

# # • **Menu-Items**  
# #   “What are you looking for today?  
# #    1. Pregnancy test  
# #    2. Early pregnancy-loss support  
# #    3. Abortion  
# #    4. Symptoms-related help  
# #    5. Miscarriage support”

# # • **Pregnancy-Test**  
# #   “Have you had a positive pregnancy test? Reply yes, no, or unsure.”

# # • **LMP-Query**  
# #   “Do you know the day of your last menstrual period?”

# # • **LMP-Date**  
# #   “What was the first day of your last menstrual period? (MM/DD/YYYY)”

# # • **Symptom-Triage**  
# #   “What symptom are you experiencing? Reply ‘Bleeding’, ‘Nausea’, or ‘Vomiting’.”

# # –– **Bleeding branch** ––  
# # • **Bleeding-Triage**  
# #   “Have you had a history of ectopic pregnancy? Reply EY for Yes, EN for No.”

# # • **Bleeding-Heavy-Check**  
# #   “Is the bleeding heavy (4+ super-pads in 2 hrs)? Reply Y or N.”

# # • **Bleeding-Urgent**  
# #   “This could be serious. Please call your OB/GYN at [clinic_phone] or go to ER. Are you seeing miscarriage?”

# # • **Bleeding-Pain-Check**  
# #   “Are you experiencing any pain or cramping? Reply Y or N.”

# # • **Bleeding-Advice**  
# #   “Please monitor your bleeding and note the color. Contact your provider. I’ll check in in 24 hrs.”

# # –– **Nausea branch** ––  
# # • **Nausea-Triage**  
# #   “Have you been able to keep food or liquids down in the last 24 hrs? Reply Y or N.”

# # • **Nausea-Advice**  
# #   “Try small meals, ginger, or vitamin B6. I’ll check back in 24 hrs.”

# # • **Nausea-Urgent**  
# #   “If you can’t keep anything down, contact your provider or PEACE at [clinic_phone]. You might need Unisom.”

# # –– **Miscarriage support** ––  
# # • **Miscarriage-Support**  
# #   “I’m sorry you’re going through this. Do you need emotional support or infection-prevention support?”

# # • **Miscarriage-Emotions**  
# #   “How are you feeling emotionally? I can connect you to social resources if needed.”

# # • **Miscarriage-Infection**  
# #   “To prevent infection, avoid tampons, sex, or swimming. Let me know if you develop fever.”

# # • **Call-Transfer**  
# #   “I’m transferring you now to a specialist for further assistance.”  

# # """
# #         flow_instruction_context = f"""
# #         Main Patient Journey Flows

# #         Main Patient Journey Flows

# #         • **Start Conversation** (current_node_id: start_conversation)
# #           "Hi $patient_firstname! I'm here to help you with your healthcare needs. What would you like to talk about today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) I have a question about a pregnancy test  F) I need help with pregnancy loss  G) Something else H) Nothing at this time Reply with just one letter."
# #           (next_node_id: menu_items)

# # • **Menu-Items** (current_node_id: menu_items)
# #   "What are you looking for today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) I have a question about a pregnancy test F) I need help with pregnancy loss G) Something else H) Nothing at this time I) Take the Pre-Program Impact Survey J) Take the Post-Program Impact Survey K) Take the NPS Quantitative Survey Reply with just one letter."
# #   –– If A (Symptoms) –– (next_node_id: symptoms_response)
# #   –– If B (Medications) –– (next_node_id: medications_response)
# #   –– If C (Appointment) –– (next_node_id: appointment_response)
# #   –– If D (PEACE Visit) –– (next_node_id: peace_visit_response_part_1)
# #   –– If E (Pregnancy Test) –– (next_node_id: follow_up_confirmation_of_pregnancy_survey)
# #   –– If F (Pregnancy Loss) –– (next_node_id: pregnancy_loss_response)
# #   –– If G (Something Else) –– (next_node_id: something_else_response)
# #   –– If H (Nothing) –– (next_node_id: nothing_response)
# #   –– If I (Pre-Program Impact Survey) –– (next_node_id: pre_program_impact_survey)
# #   –– If J (Post-Program Impact Survey) –– (next_node_id: post_program_impact_survey)
# #   –– If K (NPS Quantitative Survey) –– (next_node_id: nps_quantitative_survey)

# #         • **Onboarding** (current_node_id: onboarding)
# #           "Initial patient enrollment with four main branches: Pregnancy Preference Unknown, Desired Pregnancy Preference, Undesired/Unsure Pregnancy Preference, Early Pregnancy Loss. Final pathways to either Offboarding or Program Archived."
# #           (next_node_id: follow_up_confirmation_of_pregnancy_survey)

# #         • **Follow-Up Confirmation of Pregnancy Survey** (current_node_id: follow_up_confirmation_of_pregnancy_survey)
# #           "Hi $patient_firstname. As your virtual health buddy, my mission is to help you find the best care for your needs. Have you had a moment to take your home pregnancy test? Reply Y or N"
# #           (next_node_id: pregnancy_test_results_nlp_survey)
# # (next_node_id: pregnancy_test_results_nlp_survey)

# # • Pregnancy Test Results NLP Survey (current_node_id: pregnancy_test_results_nlp_survey)

# # "It sounds like you're sharing your pregnancy test results, is that correct? Reply Y or N"

# # –– If N (Pregnancy Test Results) –– (next_node_id: default_response)

# # –– If Y (Pregnancy Test Results) –– (next_node_id: pregnancy_test_result_confirmation)

# # • Default Response (current_node_id: default_response)

# # "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

# # (next_node_id: null)

# # • Pregnancy Test Result Confirmation (current_node_id: pregnancy_test_result_confirmation)

# # "Were the results positive? Reply Y or N"

# # –– If YES (Result Positive) –– (next_node_id: ask_for_lmp)

# # –– If NO (Result Negative) –– (next_node_id: negative_test_result_response)

# # • Ask for LMP (current_node_id: ask_for_lmp)

# # "Sounds good. In order to give you accurate information, it's helpful for me to know the first day of your last menstrual period (LMP). Do you know this date? Reply Y or N (It's OK if you're uncertain)"

# # –– If Y (LMP Known) –– (next_node_id: enter_lmp_date)

# # –– If N (LMP Unknown) –– (next_node_id: ask_for_edd)

# # • Enter LMP Date (current_node_id: enter_lmp_date)

# # "Great. Your LMP is a good way to tell your gestational age. Please reply in this format: MM/DD/YYYY"

# # (next_node_id: lmp_date_received)

# # • LMP Date Received (current_node_id: lmp_date_received)

# # "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."

# # (next_node_id: pregnancy_intention_survey)

# # • Ask for EDD (current_node_id: ask_for_edd)

# # "Not a problem. Do you know your Estimated Due Date? Reply Y or N (again, it's OK if you're uncertain)"

# # –– If Y (EDD Known) –– (next_node_id: enter_edd_date)

# # –– If N (EDD Unknown) –– (next_node_id: check_penn_medicine_system)

# # • Enter EDD Date (current_node_id: enter_edd_date)

# # "Great. Please reply in this format: MM/DD/YYYY"

# # (next_node_id: edd_date_received)

# # • EDD Date Received (current_node_id: edd_date_received)

# # "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."

# # (next_node_id: pregnancy_intention_survey)

# # • Check Penn Medicine System (current_node_id: check_penn_medicine_system)

# # "We know it can be hard to keep track of periods sometimes. Have you been seen in the Penn Medicine system? Reply Y or N"

# # –– If Y (Seen in Penn System) –– (next_node_id: penn_system_confirmation)

# # –– If N (Not Seen in Penn System) –– (next_node_id: register_as_new_patient)

# # • Penn System Confirmation (current_node_id: penn_system_confirmation)

# # "Perfect. Over the next few days we're here for you and ready to help with your next moves. Stay tuned!"

# # (next_node_id: pregnancy_intention_survey)

# # • Register as New Patient (current_node_id: register_as_new_patient)

# # "Not a problem. Contact the call center $clinic_phone$ and have them add you as a 'new patient'. This way, if you need any assistance in the future, we'll be able to help you quickly."

# # (next_node_id: pregnancy_intention_survey)

# # • Negative Test Result Response (current_node_id: negative_test_result_response)

# # "Thanks for sharing. If you have any questions or if there's anything you'd like to talk about, we're here for you. Contact the call center $clinic_phone$ for any follow-ups & to make an appointment with your OB/GYN."

# # (next_node_id: offboarding_after_negative_result)

# # • Offboarding After Negative Result (current_node_id: offboarding_after_negative_result)

# # "Being a part of your care journey has been a real privilege. Since I only guide you through this brief period, I won't be available for texting after today. If you find yourself pregnant in the future, text me back at this number, and I'll be here to support you once again."

# # (next_node_id: null)

# # • Pregnancy Intention Survey (current_node_id: pregnancy_intention_survey)

# # "$patient_firstName$, pregnancy can stir up many different emotions. These can range from uncertainty and regret to joy and happiness. You might even feel multiple emotions at the same time. It's okay to have these feelings. We're here to help support you through it all. I'm checking in on how you're feeling about being pregnant. Are you: A) Excited B) Not sure C) Not excited Reply with just 1 letter"

# # –– If A (Excited) –– (next_node_id: excited_response)

# # –– If B (Not Sure) –– (next_node_id: not_sure_response)

# # –– If C (Not Excited) –– (next_node_id: not_excited_response)

# # • Excited Response (current_node_id: excited_response)

# # "Well that is exciting news! Some people feel excited, and want to continue their pregnancy, and others aren't sure. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."

# # (next_node_id: care_options_prompt)

# # • Not Sure Response (current_node_id: not_sure_response)

# # "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."

# # (next_node_id: care_options_prompt)

# # • Not Excited Response (current_node_id: not_excited_response)

# # "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."

# # (next_node_id: care_options_prompt)

# # • Care Options Prompt (current_node_id: care_options_prompt)

# # "Would you prefer us to connect you with providers who can help with: A) Continuing my pregnancy B) Talking with me about what my options are C) Getting an abortion Reply with just 1 letter"

# # –– If A (Continuing Pregnancy) –– (next_node_id: prenatal_provider_check)

# # –– If B (Options) –– (next_node_id: connect_to_peace_clinic)

# # –– If C (Abortion) –– (next_node_id: connect_to_peace_for_abortion)

# # • Prenatal Provider Check (current_node_id: prenatal_provider_check)

# # "Do you have a prenatal provider? Reply Y or N"

# # –– If Y (Has Prenatal Provider) –– (next_node_id: schedule_appointment)

# # –– If N (No Prenatal Provider) –– (next_node_id: schedule_with_penn_obgyn)

# # • Schedule Appointment (current_node_id: schedule_appointment)

# # "Great, it sounds like you're on the right track! Call $clinic_phone$ to make an appointment."

# # (next_node_id: null)

# # • Schedule with Penn OB/GYN (current_node_id: schedule_with_penn_obgyn)

# # "It's important to receive prenatal care early on. Sometimes it takes a few weeks to get in. Call $clinic_phone$ to schedule an appointment with Penn OB/GYN Associates or Dickens Clinic."

# # (next_node_id: null)

# # • Connect to PEACE Clinic (current_node_id: connect_to_peace_clinic)

# # "We understand your emotions, and it's important to take the necessary time to navigate through them. The team at The Pregnancy Early Access Center (PEACE) provides abortion, miscarriage management, and pregnancy prevention. Call $clinic_phone$ to schedule an appointment with PEACE. https://www.pennmedicine.org/make-an-appointment"

# # (next_node_id: null)

# # • Connect to PEACE for Abortion (current_node_id: connect_to_peace_for_abortion)

# # "Call $clinic_phone$ to be scheduled with PEACE. https://www.pennmedicine.org/make-an-appointment We'll check back with you to make sure you're connected to care. We have a few more questions before your visit. It'll help us find the right care for you."

# # (next_node_id: null)

# # Symptom Management Flows

# # • Menu-Items (current_node_id: menu_items)

# # "What are you looking for today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) Something else F) Nothing at this time Reply with just one letter."

# # –– If A (Symptoms) –– (next_node_id: symptoms_response)

# # –– If B (Medications) –– (next_node_id: medications_response)

# # –– If C (Appointment) –– (next_node_id: appointment_response)

# # –– If D (PEACE Visit) –– (next_node_id: peace_visit_response_part_1)

# # –– If E (Something Else) –– (next_node_id: something_else_response)

# # –– If F (Nothing) –– (next_node_id: nothing_response)

# # • Symptoms Response (current_node_id: symptoms_response)

# # "We understand questions and concerns come up. You can try texting this number with your question, and I may have an answer. This isn't an emergency line, so it’s best to reach out to your provider if you have an urgent concern by calling $clinic_phone$. If you're worried or feel like this is something serious – it's essential to seek medical attention."

# # (next_node_id: symptom_triage)

# # • Medications Response (current_node_id: medications_response)

# # "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"

# # (next_node_id: null)

# # • Appointment Response (current_node_id: appointment_response)

# # "Unfortunately, I can’t see when your appointment is, but you can call the clinic to find out more information. If I don’t answer all of your questions, or you have a more complex question, you can contact the Penn care team at $clinic_phone$ who can give you further instructions. I can also provide some general information about what to expect at a visit. Just ask me."

# # (next_node_id: null)

# # • PEACE Visit Response Part 1 (current_node_id: peace_visit_response_part_1)

# # "The Pregnancy Early Access Center is a support team who's here to help you think through the next steps and make sure you have all the information you need. They're a listening ear, judgment-free and will support any decision you make. You can have an abortion, you can place the baby for adoption or you can continue the pregnancy and choose to parent. They are there to listen to you and answer any of your questions."

# # (next_node_id: peace_visit_response_part_2)

# # • PEACE Visit Response Part 2 (current_node_id: peace_visit_response_part_2)

# # "Sometimes, they use an ultrasound to confirm how far along you are to help in discussing options for your pregnancy. If you're considering an abortion, they'll review both types of abortion (medical and surgical) and tell you about the required counseling and consent (must be done at least 24 hours before the procedure). They can also discuss financial assistance and connect you with resources to help cover the cost of care."

# # (next_node_id: null)

# # • Something Else Response (current_node_id: something_else_response)

# # "OK, I understand and I might be able to help. Try texting your question to this number. Remember, I do best with short sentences about one topic. If you need more urgent help or prefer to speak to someone on the phone, you can reach your care team at $clinic_phone$ & ask for your clinic. If you're worried or feel like this is something serious – it's essential to seek medical attention."

# # (next_node_id: null)

# # • Nothing Response (current_node_id: nothing_response)

# # "OK, remember you can text this number at any time with questions or concerns."

# # (next_node_id: null)

# # • Symptom-Triage (current_node_id: symptom_triage)

# # "What symptom are you experiencing? Reply 'Bleeding', 'Nausea', 'Vomiting', 'Pain', or 'Other'"

# # –– If Bleeding –– (next_node_id: vaginal_bleeding_1st_trimester)

# # –– If Nausea –– (next_node_id: nausea_1st_trimester)

# # –– If Vomiting –– (next_node_id: vomiting_1st_trimester)

# # –– If Pain –– (next_node_id: pain_early_pregnancy)

# # –– If Other –– (next_node_id: default_response)

# # • Vaginal Bleeding - 1st Trimester (current_node_id: vaginal_bleeding_1st_trimester)

# # "Let me ask a few more questions about your medical history to determine the next best steps. Have you ever had an ectopic pregnancy (this is a pregnancy in your tube or anywhere outside of your uterus)? Reply Y or N"

# # –– If Y (Previous Ectopic Pregnancy) –– (next_node_id: immediate_provider_visit)

# # –– If N (No Previous Ectopic Pregnancy) –– (next_node_id: heavy_bleeding_check)

# # • Immediate Provider Visit (current_node_id: immediate_provider_visit)

# # "Considering your past history, you should be seen by a provider immediately. Now: Call your OB/GYN ASAP (Call $clinic_phone$ to make an urgent appointment with PEACE – the Early Pregnancy Access Center – if you do not have a provider) If you're not feeling well or have a medical emergency, visit your local ER."

# # (next_node_id: null)

# # • Heavy Bleeding Check (current_node_id: heavy_bleeding_check)

# # "Over the past 2 hours, is your bleeding so heavy that you've filled 4 or more super pads? Reply Y or N"

# # –– If Y (Heavy Bleeding) –– (next_node_id: urgent_provider_visit_for_heavy_bleeding)

# # –– If N (No Heavy Bleeding) –– (next_node_id: pain_or_cramping_check)

# # • Urgent Provider Visit for Heavy Bleeding (current_node_id: urgent_provider_visit_for_heavy_bleeding)

# # "This amount of bleeding during pregnancy means you should be seen by a provider immediately. Now: Call your OB/GYN. (Call $clinic_phone$, option 5 to make an urgent appointment with PEACE – the Early Pregnancy Access Center) If you're not feeling well or have a medical emergency, visit your local ER."

# # (next_node_id: null)

# # • Pain or Cramping Check (current_node_id: pain_or_cramping_check)

# # "Are you in any pain or cramping? Reply Y or N"

# # –– If Y (Pain or Cramping) –– (next_node_id: er_visit_check_during_pregnancy)

# # –– If N (No Pain or Cramping) –– (next_node_id: monitor_bleeding)

# # • ER Visit Check During Pregnancy (current_node_id: er_visit_check_during_pregnancy)

# # "Have you been to the ER during this pregnancy? Reply Y or N"

# # –– If Y (Been to ER) –– (next_node_id: report_bleeding_to_provider)

# # –– If N (Not Been to ER) –– (next_node_id: monitor_bleeding_at_home)

# # • Report Bleeding to Provider (current_node_id: report_bleeding_to_provider)

# # "Any amount of bleeding during pregnancy should be reported to a provider. Call your provider for guidance."

# # (next_node_id: continued_bleeding_follow_up)

# # • Monitor Bleeding at Home (current_node_id: monitor_bleeding_at_home)

# # "While bleeding or spotting in early pregnancy can be alarming, it's pretty common. Based on your exam in the ER, it's okay to keep an eye on it from home. If you notice new symptoms, feel worse, or are concerned about your health and need to be seen urgently, go to the emergency department."

# # (next_node_id: continued_bleeding_follow_up)

# # • Monitor Bleeding (current_node_id: monitor_bleeding)

# # "While bleeding or spotting in early pregnancy can be alarming, it's actually quite common and doesn't always mean a miscarriage. But keeping an eye on it is important. Always check the color of the blood (brown, pink, or bright red) and keep a note."

# # (next_node_id: continued_bleeding_follow_up)

# # • Continued Bleeding Follow-Up (current_node_id: continued_bleeding_follow_up)

# # "If you continue bleeding, getting checked out by a provider can be helpful. Keep an eye on your bleeding. We'll check in on you again tomorrow. If the bleeding continues or you feel worse, make sure you contact a provider. And remember: If you do not feel well or you're having a medical emergency — especially if you've filled 4 or more super pads in two hours — go to your local ER. If you still have questions or concerns, call PEACE $clinic_phone$, option 5."

# # (next_node_id: vaginal_bleeding_follow_up)

# # • Vaginal Bleeding - Follow-up (current_node_id: vaginal_bleeding_follow_up)

# # "Hey $patient_firstname, just checking on you. How's your vaginal bleeding today? A) Stopped B) Stayed the same C) Gotten heavier Reply with just one letter"

# # –– If A (Stopped) –– (next_node_id: bleeding_stopped_response)

# # –– If B (Same) –– (next_node_id: persistent_bleeding_response)

# # –– If C (Heavier) –– (next_node_id: increased_bleeding_response)

# # • Bleeding Stopped Response (current_node_id: bleeding_stopped_response)

# # "We're glad to hear it. If anything changes - especially if you begin filling 4 or more super pads in two hours, go to your local ER."

# # (next_node_id: null)

# # • Persistent Bleeding Response (current_node_id: persistent_bleeding_response)

# # "Thanks for sharing—we're sorry to hear your situation hasn't improved. Since your vaginal bleeding has lasted longer than a day, we recommend you call your OB/GYN or $clinic_phone$ and ask for the Early Pregnancy Access Center. If you do not feel well or you're having a medical emergency - especially if you've filled 4 or more super pads in two hours -- go to your local ER."

# # (next_node_id: null)

# # • Increased Bleeding Response (current_node_id: increased_bleeding_response)

# # "Sorry to hear that. Thanks for sharing. Since your vaginal bleeding has lasted longer than a day, and has increased, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."

# # (next_node_id: null)

# # • Nausea - 1st Trimester (current_node_id: nausea_1st_trimester)

# # "We're sorry to hear it—and we're here to help. Nausea and vomiting are very common during pregnancy. Staying hydrated and eating small, frequent meals can help, along with natural remedies like ginger and vitamin B6. Let's make sure there's nothing you need to be seen for right away. Have you been able to keep food or liquids in your stomach for 24 hours? Reply Y or N"

# # –– If Y (Able to Keep Food/Liquids) –– (next_node_id: nausea_management_advice)

# # –– If N (Unable to Keep Food/Liquids) –– (next_node_id: nausea_treatment_options)

# # • Nausea Management Advice (current_node_id: nausea_management_advice)

# # "OK, thanks for letting us know. Nausea and vomiting are very common during pregnancy. To feel better, staying hydrated and eating small, frequent meals (even before you feel hungry) is important. Avoid an empty stomach by taking small sips of water or nibbling on bland snacks throughout the day. Try eating protein-rich foods like meat or beans."

# # (next_node_id: nausea_follow_up_warning)

# # • Nausea Treatment Options (current_node_id: nausea_treatment_options)

# # "OK, thanks for letting us know. There are safe treatment options for you! Your care team at Penn recommends trying a natural remedy like ginger and vitamin B6 (take one 25mg tablet every 8 hours as needed). If this isn't working, you can try unisom – an over-the-counter medication – unless you have an allergy. Let your provider know. You can use this medicine until they call you back."

# # (next_node_id: nausea_follow_up_warning)

# # • Nausea Follow-Up Warning (current_node_id: nausea_follow_up_warning)

# # "If your nausea gets worse and you can't keep foods or liquids down for over 24 hours, contact your provider or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you!"

# # (next_node_id: nausea_1st_trimester_follow_up)

# # • Nausea - 1st Trimester Follow-up (current_node_id: nausea_1st_trimester_follow_up)

# # "Hey $patient_firstname, just checking on you. How's your nausea today? A) Better B) Stayed the same C) Worse Reply with just the letter"

# # –– If A (Better) –– (next_node_id: nausea_improved_response)

# # –– If B (Stayed the Same) –– (next_node_id: nausea_same_response)

# # –– If C (Worse) –– (next_node_id: nausea_worsened_check)

# # • Nausea Improved Response (current_node_id: nausea_improved_response)

# # "We're glad to hear it. If anything changes - especially if you can't keep foods or liquids down for 24+ hours, reach out to your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you."

# # (next_node_id: null)

# # • Nausea Same Response (current_node_id: nausea_same_response)

# # "Thanks for sharing—Sorry you aren't feeling better yet, but we're glad to hear you could keep a little down. Would you like us to check on you tomorrow as well? Reply Y or N"

# # –– If Y (Check Tomorrow) –– (next_node_id: schedule_follow_up)

# # –– If N (No Follow-Up) –– (next_node_id: nausea_monitoring_advice)

# # • Schedule Follow-Up (current_node_id: schedule_follow_up)

# # "OK. We're here to help. Let us know if anything changes."

# # (next_node_id: null)

# # • Nausea Monitoring Advice (current_node_id: nausea_monitoring_advice)

# # "OK. We're here to help. Let us know if anything changes. If you can't keep foods or liquids down for 24+ hours, contact your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. There are safe ways to treat this, so don't wait. If you're not feeling well or have a medical emergency, visit your local ER."

# # (next_node_id: null)

# # • Nausea Worsened Check (current_node_id: nausea_worsened_check)

# # "Have you kept food or drinks down since I last checked in? Reply Y or N"

# # –– If N (Unable to Keep Food/Drinks) –– (next_node_id: urgent_nausea_response)

# # –– If Y (Able to Keep Food/Drinks) –– (next_node_id: null)

# # • Urgent Nausea Response (current_node_id: urgent_nausea_response)

# # "Sorry to hear that. Thanks for sharing. Since your vomiting has increased and worsened, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please visit your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."

# # (next_node_id: null)

# # • Vomiting - 1st Trimester (current_node_id: vomiting_1st_trimester)

# # "Hi $patient_firstName$, It sounds like you're concerned about vomiting. Is that correct? Reply Y or N"

# # –– If N (Not Concerned) –– (next_node_id: default_response)

# # –– If Y (Concerned) –– (next_node_id: trigger_nausea_triage)

# # • Trigger Nausea Triage (current_node_id: trigger_nausea_triage)

# # "TRIGGER 2ND NODE → NAUSEA TRIAGE"

# # (next_node_id: nausea_1st_trimester)

# # (Comment: This node triggers the Nausea - 1st Trimester flow, redirecting to nausea_1st_trimester.)

# # • Vomiting - 1st Trimester Follow-up (current_node_id: vomiting_1st_trimester_follow_up)

# # "Checking on you, $patient_firstname. How's your vomiting today? A) Better B) Stayed the same C) Worse Reply with just the letter"

# # –– If A (Better) –– (next_node_id: vomiting_improved_response)

# # –– If B (Stayed the Same) –– (next_node_id: vomiting_same_response)

# # –– If C (Worse) –– (next_node_id: vomiting_worsened_response)

# # • Vomiting Improved Response (current_node_id: vomiting_improved_response)

# # "We're glad to hear it. If anything changes - especially if you can't keep foods or liquids down for 24+ hours, reach out to your OB or call $clinic_phone$ if you have not seen an OB yet. Don't wait—there are safe treatment options for you."

# # (next_node_id: null)

# # • Vomiting Same Response (current_node_id: vomiting_same_response)

# # "Thanks for sharing—Sorry you aren't feeling better yet. Would you like us to check on you tomorrow as well? Reply Y or N"

# # –– If Y (Check Tomorrow) –– (next_node_id: schedule_vomiting_follow_up)

# # –– If N (No Follow-Up) –– (next_node_id: vomiting_monitoring_advice)

# # • Schedule Vomiting Follow-Up (current_node_id: schedule_vomiting_follow_up)

# # "OK. We're here to help. Let us know if anything changes."

# # (next_node_id: null)

# # • Vomiting Monitoring Advice (current_node_id: vomiting_monitoring_advice)

# # "OK. We're here to help. Let us know if anything changes. If you can't keep foods or liquids down for 24+ hours, contact your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. If you're not feeling well or have a medical emergency, visit your local ER."

# # (next_node_id: null)

# # • Vomiting Worsened Response (current_node_id: vomiting_worsened_response)

# # "Sorry to hear that. Thanks for sharing. Since your vomiting has increased and worsened, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."

# # (next_node_id: null)

# # • Pain - Early Pregnancy (current_node_id: pain_early_pregnancy)

# # "We're sorry to hear this. It sounds like you're concerned about pain, is that correct? Reply Y or N"

# # –– If N (Not Concerned) –– (next_node_id: default_response)

# # –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow_pain)

# # • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_pain)

# # "Trigger EPS Vaginal Bleeding (First Trimester)"

# # (next_node_id: vaginal_bleeding_1st_trimester)

# # (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# # • Ectopic Pregnancy Concern (current_node_id: ectopic_pregnancy_concern)

# # "We're sorry to hear this. It sounds like you're concerned about an ectopic pregnancy, is that correct? Reply Y or N"

# # –– If N (Not Concerned) –– (next_node_id: default_response)

# # –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow_ectopic)

# # • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_ectopic)

# # "Trigger EPS Vaginal Bleeding (First Trimester)"

# # (next_node_id: vaginal_bleeding_1st_trimester)

# # (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# # • Menstrual Period Concern (current_node_id: menstrual_period_concern)

# # "It sounds like you're concerned about your menstrual period, is that correct? Reply Y or N"

# # –– If N (Not Concerned) –– (next_node_id: default_response)

# # –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow_menstrual)

# # • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_menstrual)

# # "EPS Vaginal Bleeding (First Trimester) Let me ask you a few more questions about your medical history to determine the next best steps."

# # (next_node_id: vaginal_bleeding_1st_trimester)

# # (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# # Pregnancy Decision Support Flows

# # • Possible Early Pregnancy Loss (current_node_id: possible_early_pregnancy_loss)

# # "It sounds like you're concerned about pregnancy loss (miscarriage), is that correct? Reply Y or N"

# # –– If N (Not Concerned) –– (next_node_id: default_response)

# # –– If Y (Concerned) –– (next_node_id: confirm_pregnancy_loss)

# # • Confirm Pregnancy Loss (current_node_id: confirm_pregnancy_loss)

# # "We're sorry to hear this. Has a healthcare provider confirmed an early pregnancy loss (that your pregnancy stopped growing)? A) Yes B) No C) Not Sure Reply with just the letter"

# # –– If A (Confirmed Loss) –– (next_node_id: support_and_schedule_appointment)

# # –– If B (Not Confirmed) –– (next_node_id: trigger_vaginal_bleeding_flow_not_confirmed)

# # –– If C (Not Sure) –– (next_node_id: schedule_peace_appointment)

# # • Support and Schedule Appointment (current_node_id: support_and_schedule_appointment)

# # "We're here to listen and offer support. It's helpful to talk about the options to manage this. We can help schedule you an appointment. Call $clinic_phone$ and ask for the PEACE clinic. We'll check in on you in a few days."

# # (next_node_id: null)

# # • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_not_confirmed)

# # "Trigger Vaginal Bleeding – 1st Trimester"

# # (next_node_id: vaginal_bleeding_1st_trimester)

# # (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# # • Schedule PEACE Appointment (current_node_id: schedule_peace_appointment)

# # "Sorry to hear this has been confusing for you. We recommend scheduling an appointment with PEACE so that they can help explain what's going on. Call $clinic_phone$, option 5 and we can help schedule you a visit so that you can get the information you need, and your situation becomes more clear."

# # (next_node_id: trigger_vaginal_bleeding_flow_not_sure)

# # • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_not_sure)

# # "Trigger Vaginal Bleeding – 1st Trimester"

# # (next_node_id: vaginal_bleeding_1st_trimester)

# # (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# # • Undesired Pregnancy - Desires Abortion (current_node_id: undesired_pregnancy_desires_abortion)

# # "It sounds like you want to get connected to care for an abortion, is that correct? Reply Y or N"

# # –– If N (Not Interested) –– (next_node_id: default_response)

# # –– If Y (Interested) –– (next_node_id: abortion_care_connection)

# # • Abortion Care Connection (current_node_id: abortion_care_connection)

# # "The decision about this pregnancy is yours and no one is better able to decide than you. Please call $clinic_phone$ and ask to be connected to the PEACE clinic (pregnancy early access center). The clinic intake staff will answer your questions and help schedule an abortion. You can also find more information about laws in your state and how to get an abortion at AbortionFinder.org"

# # (next_node_id: null)

# # • Undesired Pregnancy - Completed Abortion (current_node_id: undesired_pregnancy_completed_abortion)

# # "It sounds like you've already had an abortion, is that correct? Reply Y or N"

# # –– If N (Not Completed) –– (next_node_id: default_response)

# # –– If Y (Completed) –– (next_node_id: post_abortion_care)

# # • Post-Abortion Care (current_node_id: post_abortion_care)

# # "Caring for yourself after an abortion is important. Follow the instructions given to you. Most people can return to normal activities 1 to 2 days after the procedure. You may have cramps and light bleeding for up to 2 weeks. Call $clinic_phone$, option 5 and ask to be connected to the PEACE clinic (pregnancy early access center) if you have any questions or concerns."

# # (next_node_id: offboarding_after_abortion)

# # • Offboarding After Abortion (current_node_id: offboarding_after_abortion)

# # "Being a part of your care journey has been a real privilege. On behalf of your team at Penn, we hope we've been helpful to you during this time. Since I only guide you through this brief period, I won't be available for texting after today. Remember, you have a lot of resources available from Penn AND your community right at your fingertips."

# # (next_node_id: null)

# # • Desired Pregnancy Survey (current_node_id: desired_pregnancy_survey)

# # "It sounds like you want to get connected to care for your pregnancy, is that correct? Reply Y or N"

# # –– If N (Not Interested) –– (next_node_id: default_response)

# # –– If Y (Interested) –– (next_node_id: connect_to_prenatal_care)

# # • Connect to Prenatal Care (current_node_id: connect_to_prenatal_care)

# # "That's something I can definitely do! Call $clinic_phone$ Penn OB/GYN Associates or Dickens Clinic and make an appointment. It's important to receive prenatal care early on (and throughout your pregnancy) to reduce the risk of complications and ensure that both you and your baby are healthy."

# # (next_node_id: null)

# # • Unsure About Pregnancy Survey (current_node_id: unsure_about_pregnancy_survey)

# # "Becoming a parent is a big step. Deciding if you want to continue a pregnancy is a personal decision. Talking openly and honestly with your partner or healthcare team is key. We're here for you. You can also try some thought work here: https://www.pregnancyoptions.info/pregnancy-options-workbook Would you like to get connected to care to discuss your options for pregnancy, is that correct? Reply Y or N"

# # –– If N (Not Interested) –– (next_node_id: default_response)

# # –– If Y (Interested) –– (next_node_id: connect_to_peace_clinic_for_options)

# # • Connect to PEACE Clinic for Options (current_node_id: connect_to_peace_clinic_for_options)

# # "Few decisions are greater than this one, but we've got your back. The decision about this pregnancy is yours and no one is better able to decide than you. Please call $clinic_phone$, and ask to be scheduled in the PEACE clinic (pregnancy early access center). They are here to support you no matter what you choose."

# # (next_node_id: null)

# # Postpartum Support Flows

# # • Postpartum Onboarding – Week 1 (current_node_id: postpartum_onboarding_week_1)

# # "Hi $patient_firstname$, congratulations on your new baby! Let's get started with a few short messages to support you and your newborn. You can always reply STOP to stop receiving messages." [DAY: 0, TIME: 8 AM]

# # (next_node_id: feeding_advice)

# # • Feeding Advice (current_node_id: feeding_advice)

# # "Feeding your baby is one of the most important parts of newborn care. Feeding your baby at least 8-12 times every 24 hours is normal and important to support their growth. You may need to wake your baby to feed if they're sleepy or jaundiced." [DAY: 0, TIME: 12 PM]

# # (next_node_id: track_baby_output)

# # • Track Baby Output (current_node_id: track_baby_output)

# # "It's important to keep track of your baby's output (wet and dirty diapers) to know they're feeding well. By the time your baby is 5 days old, they should have 5+ wet diapers and 3+ poops per day." [DAY: 0, TIME: 4 PM]

# # (next_node_id: jaundice_information)

# # • Jaundice Information (current_node_id: jaundice_information)

# # "Jaundice is common in newborns and usually goes away on its own. Signs of jaundice include yellowing of the skin or eyes. If you're worried or if your baby isn't feeding well or is hard to wake up, call your pediatrician or visit the ER." [DAY: 0, TIME: 8 PM]

# # (next_node_id: schedule_pediatrician_visit)

# # • Schedule Pediatrician Visit (current_node_id: schedule_pediatrician_visit)

# # "Schedule a pediatrician visit. [Add scheduling link or instructions]" [DAY: 1, TIME: 8 AM]

# # (next_node_id: postpartum_check_in)

# # • Postpartum Check-In (current_node_id: postpartum_check_in)

# # "Hi $patient_firstname$, following up to check on how you're feeling after delivery. The postpartum period is a time of recovery, both physically and emotionally. It's normal to feel tired, sore, or even overwhelmed. You're not alone. Let us know if you need support." [DAY: 1, TIME: 12 PM]

# # (next_node_id: urgent_symptoms_warning)

# # • Urgent Symptoms Warning (current_node_id: urgent_symptoms_warning)

# # "Some symptoms may require urgent care. If you experience chest pain, heavy bleeding, or trouble breathing, call 911 or go to the ER. For other questions or concerns, message us anytime." [DAY: 1, TIME: 4 PM]

# # (next_node_id: postpartum_onboarding_week_2)

# # • Postpartum Onboarding – Week 2 (current_node_id: postpartum_onboarding_week_2)

# # "Hi $patient_firstname$, checking in to see how things are going now that your baby is about a week old. We shared some helpful info last week and want to make sure you're doing okay." [DAY: 7, TIME: 8 AM]

# # (next_node_id: emotional_well_being_check)

# # • Emotional Well-Being Check (current_node_id: emotional_well_being_check)

# # "Hi there—feeling different emotions after delivery is common. You may feel joy, sadness, or both. About 80% of people experience the 'baby blues,' which typically go away in a couple of weeks. If you're not feeling well emotionally or have thoughts of hurting yourself or others, please reach out for help." [DAY: 7, TIME: 12 PM]

# # (next_node_id: sids_prevention_advice)

# # • SIDS Prevention Advice (current_node_id: sids_prevention_advice)

# # "Experts recommend always placing your baby on their back to sleep, in a crib or bassinet without blankets, pillows, or stuffed toys. This reduces the risk of SIDS (Sudden Infant Death Syndrome)." [DAY: 7, TIME: 4 PM]

# # (next_node_id: schedule_postpartum_check_in)

# # • Schedule Postpartum Check-In (current_node_id: schedule_postpartum_check_in)

# # "Reminder to schedule your postpartum check-in." [DAY: 9, TIME: 8 AM]

# # (next_node_id: diaper_rash_advice)

# # • Diaper Rash Advice (current_node_id: diaper_rash_advice)

# # "Diaper rash is common. It can usually be treated with diaper cream and frequent diaper changes. If your baby develops a rash that doesn't go away or seems painful, call your pediatrician." [DAY: 9, TIME: 12 PM]

# # (next_node_id: feeding_follow_up)

# # • Feeding Follow-Up (current_node_id: feeding_follow_up)

# # "Hi $patient_firstname$, checking in again—how is feeding going? Breastfeeding can be challenging at times. It's okay to ask for help from a lactation consultant or your provider. Let us know if you have questions." [DAY: 9, TIME: 4 PM]

# # (next_node_id: contraception_reminder)

# # • Contraception Reminder (current_node_id: contraception_reminder)

# # "Hi $patient_firstname$, just a quick note about contraception. You can get pregnant again even if you haven't gotten your period yet. If you're not ready to be pregnant again soon, it's important to consider your birth control options. Talk to your provider to learn what's right for you." [DAY: 10, TIME: 12 PM]

# # (next_node_id: contraception_resources)

# # • Contraception Resources (current_node_id: contraception_resources)

# # "Birth control is available at no cost with most insurance plans. Let us know if you'd like support connecting to resources." [DAY: 10, TIME: 5 PM]

# # (next_node_id: null)

# # Emergency Situation Management

# # • Emergency Room Survey (current_node_id: emergency_room_survey)

# # "It sounds like you are telling me about an emergency. Are you currently in the ER (or on your way)? Reply Y or N"

# # –– If Y (In ER) –– (next_node_id: current_er_response)

# # –– If N (Not In ER) –– (next_node_id: recent_er_visit_check)

# # • Current ER Response (current_node_id: current_er_response)

# # "We're sorry to hear and thanks for sharing. Glad you're seeking care. Please let us know if there's anything we can do for you."

# # (next_node_id: null)

# # • Recent ER Visit Check (current_node_id: recent_er_visit_check)

# # "Were you recently discharged from an emergency room visit?"

# # –– If Y (Recent ER Visit) –– (next_node_id: share_er_info)

# # –– If N (No Recent ER Visit) –– (next_node_id: er_recommendation)

# # • Share ER Info (current_node_id: share_er_info)

# # "We're sorry to hear about your visit. To help your care team stay in the loop, would you like us to pass on any info? No worries if not, just reply 'no'."

# # (next_node_id: follow_up_support)

# # • Follow-Up Support (current_node_id: follow_up_support)

# # "Let us know if you need anything else."

# # (next_node_id: null)

# # • ER Recommendation (current_node_id: er_recommendation)

# # "If you're not feeling well or have a medical emergency, go to your local ER. If I misunderstood your message, try rephrasing & using short sentences. You may also reply MENU for a list of support options."

# # (next_node_id: null)

# # Evaluation Surveys

# # • Pre-Program Impact Survey (current_node_id: pre_program_impact_survey)

# # "Hi there, $patient_firstName$. As you start this program, we'd love to hear your thoughts! We're asking a few questions to understand how you're feeling about managing your early pregnancy."

# # (next_node_id: confidence_rating)

# # • Confidence Rating (current_node_id: confidence_rating)

# # "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"

# # (next_node_id: knowledge_rating)

# # • Knowledge Rating (current_node_id: knowledge_rating)

# # "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"

# # (next_node_id: thank_you_message)

# # • Thank You Message (current_node_id: thank_you_message)

# # "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."

# # (next_node_id: null)

# # • Post-Program Impact Survey (current_node_id: post_program_impact_survey)

# # "Hi $patient_firstname$, glad you finished the program! Sharing your thoughts would be a huge help in making the program even better for others."

# # (next_node_id: post_program_confidence_rating)

# # • Post-Program Confidence Rating (current_node_id: post_program_confidence_rating)

# # "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"

# # (next_node_id: post_program_knowledge_rating)

# # • Post-Program Knowledge Rating (current_node_id: post_program_knowledge_rating)

# # "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"

# # (next_node_id: post_program_thank_you)

# # • Post-Program Thank You (current_node_id: post_program_thank_you)

# # "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."

# # (next_node_id: null)

# # • NPS Quantitative Survey (current_node_id: nps_quantitative_survey)

# # "Hi $patient_firstname$, I have two quick questions about using this text messaging service (last time I promise):"

# # (next_node_id: likelihood_to_recommend)

# # • Likelihood to Recommend (current_node_id: likelihood_to_recommend)

# # "On a 0-10 scale, with 10 being 'extremely likely,' how likely are you to recommend this text message program to someone with the same (or similar) situation? Reply with a number 0-10"

# # (next_node_id: nps_qualitative_survey)

# # • NPS Qualitative Survey (current_node_id: nps_qualitative_survey)

# # "Thanks for your response. What's the reason for your score?"

# # (next_node_id: feedback_acknowledgment)

# # • Feedback Acknowledgment (current_node_id: feedback_acknowledgment)

# # "Thanks, your feedback helps us improve future programs."

# # (next_node_id: null)

# # Menu Responses

# # • A. Symptoms Response (current_node_id: menu_a_symptoms_response)

# # "We understand questions and concerns come up. By texting this number, you can connect with your question, and I may have an answer. This isn't an emergency line, so it's best to reach out to your doctor if you have an urgent concern by calling $clinic_phone$. If you're worried or feel like this is something serious - it's essential to seek medical attention."

# # (next_node_id: symptom_triage)

# # • B. Medications Response (current_node_id: menu_b_medications_response)

# # "Do you have questions about: A) Medication management B) Medications that are safe in pregnancy C) Abortion medications"

# # (next_node_id: medications_follow_up)

# # (Comment: Assumes a follow-up response; next_node_id leads to Medications Follow-Up as the next logical step.)

# # • Medications Follow-Up (current_node_id: medications_follow_up)

# # "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"

# # (next_node_id: null)

# # • C. Appointment Response (current_node_id: menu_c_appointment_response)

# # "Unfortunately, I can't see when your appointment is, but you can call the clinic to find out more information. If I don't answer all of your questions, or you have a more complex question, you can contact the Penn care team at $clinic_phone$ who can give you more detailed information about your appointment or general information about what to expect at a visit. Just ask me."

# # (next_node_id: null)

# # • D. PEACE Visit Response (current_node_id: menu_d_peace_visit_response)

# # "The Pregnancy Early Access Center is a support team, which is here to help you make choices throughout the next steps and make sure you have all the information you need. They're like planning for judgment-free care. You can ask all your questions at your visit. You have options, you can place the baby for adoption or you can continue the pregnancy and choose to parent."

# # (next_node_id: peace_visit_details)

# # • PEACE Visit Details (current_node_id: peace_visit_details)

# # "Sometimes, they use an ultrasound to confirm how far along you are to help in discussing options for your pregnancy. If you're considering an abortion, they'll review both types of abortion (medical and surgical) and tell you about the required counseling and consent (must be done at least 24 hours before the procedure). They can also discuss financial assistance and connect you with resources to help cover the cost of care."

# # (next_node_id: null)

# # • E. Something Else Response (current_node_id: menu_e_something_else_response)

# # "Ok, I understand and I might be able to help. Try texting your question to this number. Remember, I do best with short questions that are on one topic. If you need more urgent help or prefer to speak to someone on the phone, you can reach your care team at $clinic_phone$ & ask for your clinic. If you're worried or feel like this is something serious – it's essential to seek medical attention."

# # (next_node_id: null)

# # • F. Nothing Response (current_node_id: menu_f_nothing_response)

# # "OK, remember you can text this number at any time with questions or concerns."

# # (next_node_id: null)

# # Additional Instructions

# # • Always-On Q & A ON FIT (current_node_id: always_on_qa_on_fit)

# # "Always-On Q & A ON FIT - Symptom Triage (Nausea, Vomiting & Bleeding + Pregnancy Preference)"

# # (next_node_id: symptom_triage)

# # (Comment: This node directs to Symptom-Triage as the starting point for Q&A.)

# # • General Default Response (current_node_id: general_default_response)

# # "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

# # (next_node_id: null)
# # """
        
        
#         flow_instruction_context = flow_instructions
#         print(f"[FLOW INSTURCTIONS] {flow_instruction_context}")
#         document_context_section = f"""
# Relevant Document Content:
# {document_context}

# You are a helpful assistant tasked with providing accurate, specific, and context-aware responses. Follow these steps:
# 1. Identify the user's intent from the message and conversation history.
# 2. **IMPORTANT**: Scan the Relevant Document Content for any URLs, phone numbers, email addresses, medical information, or other specific resources.
# 3. **CRITICAL REQUIREMENT**: If ANY resources like UfeRLs, phone numbers, contact information, medication information, or treatment options are found, include them verbatim in your response.
# 4. Generate a natural, conversational response addressing the user's query, incorporating document content as needed.
# 5. Maintain continuity with the conversation history.
# 6. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION, but prioritize document content for specific details.
# 7. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
# 8. If no relevant document content is found, provide a helpful response based on the flow logic or general knowledge.
# 9. Double-check that all resource links, phone numbers, medication names, and contact methods from the document context are included.
# """ if document_context else """
# You are a helpful assistant tasked with providing accurate and context-aware responses. Follow these steps:
# 1. Identify the user's intent from the message and conversation history.
# 2. Generate a natural, conversational response addressing the user's query.
# 3. Maintain continuity with the conversation history.
# 4. If the query matches a node in the flow logic, process it according to the node's INSTRUCTION.
# 5. Do not repeat the node's INSTRUCTION verbatim; craft a friendly, relevant response.
# """
#         # LLM prompt
# #         prompt = f"""
# # You are a friendly, conversational assistant helping a patient with healthcare interactions. Your goal is to have a natural, human-like conversation. You need to:

# # 1. Check the patient's profile to see if any required fields are missing, and ask for them one at a time if needed.
# # 2. If the profile is complete, guide the conversation using flow instructions as a loose guide, but respond naturally to the user's message.
# # 3. If the user's message doesn't match the current flow instructions, use document content or general knowledge to provide a helpful, relevant response.
# # 4. When the user asks specific questions about medical information, treatments, or medications, ALWAYS check the document content first and provide that information.
# # 5. Maintain a warm, empathetic tone, like you're talking to a friend.


# # Current Date (MM/DD/YYYY): {current_date}

# # User Message: "{message}"

# # Conversation History:
# # {conversation_history}

# # Patient ID: {patientId}

# # Assistant ID: {assistantId}

# # Flow ID: {flow_id}

# # Patient Profile (includes phone and organization_id):
# # {patient_fields}

# # Structured Flow Instructions (Use this to guide conversation flow based on user responses):
# # {flow_instruction_context}

# # Document Content:
# # {document_context}

# # Session Data:
# # {json.dumps(session_data, indent=2)}

# # Instructions:
# # 1. **Check Patient Profile**:
# #    - Review the `Patient Profile` JSON to identify any fields (excluding `id`, `mrn`, `created_at`, `updated_at`, `organization_id`, `phone`) that are null, empty, or missing.
# #    - If any fields are missing, select one to ask for in a natural way (e.g., "Hey, I don't have your first name yet, could you share it?").
# #    - Validate user input based on the field type:
# #      - Text fields (e.g., names): Alphabetic characters, spaces, or hyphens only (/^[a-zA-Z\s-]+$/).
# #      - Dates (e.g., date_of_birth): Valid date, convertible to MM/DD/YYYY, not after {current_date}.
# #    - If the user provides a valid value for the requested field, issue an `UPDATE_PATIENT` command with:
# #      - patient_id: {patientId}
# #      - field_name: the field (e.g., "first_name")
# #      - field_value: the validated value
# #    - If the input is invalid, ask again with a friendly clarification (e.g., "Sorry, that doesn't look like a valid date. Could you try again, like 03/29/1996?").
# #    - If no fields are missing, proceed to conversation flow.
# #    - Use `organization_id` and `phone` from the `Patient Profile`, not from the request.
# #    **IMPORTANT**: Only ask for these missing profile fields—first name, last name, date of birth, gender, and email.  
# #    Do ​not​ ask for insurance, address, emergency contact, or any other fields, even if they’re empty.  
    


# # 2. **Conversation Flow (If Profile Complete)**:
# #         If the `Patient Profile` is complete (no required fields missing):
# #         *   **Step 2.1 - Identify User Intent and Response Type**:
        
# #         - Based on the `User Message` and `Conversation History`, determine the user's *current* primary intent or topic.
# #         - Determine if the `User Message` is a *direct response* to the *last Assistant message* (e.g., 'Y', 'N', 'yes', 'no', a letter choice like 'A', 'B', 'E', a date like 'MM/DD/YYYY', or a specific keyword expected by the previous node like 'Bleeding'). Normalize direct responses ('Yes'/'y' -> 'Y', 'No'/'n' -> 'N', 'A'/'a' -> 'A', etc.).

# #         *   **Step 2.2 - Find the Most Relevant Flow Node from Retrieved Instructions**:
        
# #         - Carefully review the `Structured Flow Instructions` provided (these are texts from nodes retrieved).
# #         - **If the User Message IS a direct response:**
# #             - Identify the node *in the retrieved set* whose instruction text matches the *last Assistant message* from the `Conversation History`. This is the "current active node".
# #             - Find the branching logic within this node's text that corresponds to the normalized `User Message`.
# #             - Identify the `TARGET_NODE` ID from this branch.
# #             - Find the instruction text for this `TARGET_NODE` within the `Structured Flow Instructions` context. **Set the `content` of your response to this TARGET NODE's instruction text.**
            
# #             - Set `next_node_id` to the `TARGET_NODE` ID.
# #             - **Special LMP Date Handling**: 
# #             - If the current active node was asking for LMP (Last Menstural Period) date confirmation AND user provided a valid date (MM/DD/YYYY): 
# #                 - Validate dates as MM/DD/YYYY, not after {current_date}.
# #                 - For gestational age, calculate weeks from the provided date to {current_date}, determine trimester (First: ≤12 weeks, Second: 13–27 weeks, Third: ≥28 weeks), and include in the response (e.g., "You're about 20 weeks along, in your second trimester!").
# #                 - Store in `state_updates` as `{{ "gestational_age_weeks": X, "trimester": "Second" }}`.
# #                 - IMP: Remeber If Patient provides the LMP Don't Forget to Provide the  gestational age like First Trimester or Second or Third Trimester

# #         - ** If the User Message IS NOT a direct response (New Topic):**
# #             - **Focusing *primarily* on the user's *current* message's topic/intent**, examine the `Structured Flow Instructions` (retrieved nodes).
# #             - **Find the single node *in this retrieved set* whose instruction text represents the best *entry point* or *most relevant response* for the user's *current* query.** For example, if the user asks about symptoms, look for the node explicitly labeled "Symptoms Response" or "Always-On Q & A ON FIT".
# #             - **Set the `content` of your response to the instruction text of this most relevant entry point node.**
# #             - **CRITICAL:** After identifying the matched node and its content, immediately find the `(next_node_id: ...)` line associated with *that specific matched node* in the `Structured Flow Instructions`. **The value inside the parentheses `(...)` after `next_node_id:` is the `TARGET_NODE` ID for the next step in that flow.**
# #             - **Set the `next_node_id` output to this extracted `TARGET_NODE` ID.** If the instruction is `(next_node_id: null)`, set `next_node_id` to `null`. **DO NOT default `next_node_id` to `null` or `None` if a `next_node_id` is explicitly provided for the matched node.**
# #             - **Prioritize the *current* explicit user query over previous conversation topics when selecting the primary node for the response.**

# #         -   - After determining the primary flow node response, review the `Document Content`.
# #             - If the `Document Content` contains specific details (like resource URLs, phone numbers, exact medical advice, medication names, treatment options) highly relevant to the user's query *that are not already fully covered by the chosen flow node text*, augment the response to include these specific details. **Always include URLs, phone numbers, contact information, medication names, etc., from `Document Content` VERBATIM if they are relevant.**

# #         -    For date-related instructions (e.g., gestational age):
# #             - Validate dates as MM/DD/YYYY, not after {current_date}.
# #             - For gestational age, calculate weeks from the provided date to {current_date}, determine trimester (First: ≤12 weeks, Second: 13–27 weeks, Third: ≥28 weeks), and include in the response (e.g., "You're about 20 weeks along, in your second trimester!").
# #             - Store in `state_updates` as `{{ "gestational_age_weeks": X, "trimester": "Second" }}`.
# #             - IMP: Remeber If Patient provides the LMP Don't Forget to Provide the  gestational age like First Trimester or Second or Third Trimester

# # 3. **Response Style**:
# #    - Always respond in a warm, conversational tone (e.g., "Hey, thanks for sharing that!" or "No worries, let's try that again.").
# #    - Avoid robotic phrases like "Processing node" or "Moving to next step."
# #    - If the user goes off-topic, acknowledge their message and gently steer back to the flow if needed (e.g., "That's interesting! By the way, I still need your last name to complete your profile. Could you share it?").
# #    - If all profile fields are complete and no flow instructions apply, respond to the user's message naturally, using document content or general knowledge.

# # 4. **Database Operations**:
# #    - Issue `UPDATE_PATIENT` when a valid field is provided, with `patient_id`, `field_name`, and `field_value`.
# #    - Issue `CREATE_PATIENT` only if the patient record is missing (unlikely, as patientId is provided), using `organization_id` and `phone` from session_data.

# # 5. **Flow Progression**:
# #    - Update `next_node_id` based on the flow instructions if the user's response matches,.
# #    - Identify the Assistant's last message in `Conversation History`.
# #    - Normalize the `User Message` (e.g., "Yes" to "Y", "No" to "N").
# #    - Store any relevant session updates (e.g., gestational age) in `state_updates`.

# # 6. **General Instructions**
# #    - If Conversation History is Empty then always start with the **Menu-Items** to ask the user what they are looking for. 

# # 7. **Response Structure**:
# #    Return a JSON object:
# #    ```json
# #    {{
# #      "content": "Your friendly response to the user",
# #      "next_node_id": "ID of the next node or current node",
# #      "state_updates": {{"key": "value"}},
# #      "database_operation": {{
# #        "operation": "UPDATE_PATIENT | CREATE_PATIENT",
# #        "parameters": {{
# #          "patient_id": "string",
# #          "field_name": "string",
# #          "field_value": "string"
# #        }}
# #      }} // Optional, only when updating/creating
# #    }}
# #    ```

# # Examples:
# # - Profile: {{"first_name": null, "last_name": null, "date_of_birth": null}}, Message: "hi"
# #   - Response: {{"content": "Hey, nice to hear from you! I need a bit of info to get you set up. Could you share your first name?", "next_node_id": null, "state_updates": {{}}}}
# # - Profile: {{"first_name": "Shenal", "last_name": null, "date_of_birth": null}}, Message: "Jones"
# #   - Response: {{"content": "Awesome, thanks for sharing, Shenal Jones! What's your date of birth, like 03/29/1996?", "next_node_id": null, "state_updates": {{}}, "database_operation": {{"operation": "UPDATE_PATIENT", "parameters": {{"patient_id": "{patientId}", "field_name": "last_name", "field_value": "Jones"}}}}}}
# # - Profile: {{"first_name": "Shenal", "last_name": "Jones", "date_of_birth": "03/29/1996"}}, Flow: "Ask about symptoms", Message: "I have a headache"
# #   - Response: {{"content": "Sorry to hear about your headache! How long have you been feeling this way?", "next_node_id": "node_symptom_duration", "state_updates": {{}}}}
# # - Profile complete, Flow: "Ask about symptoms", Message: "Book an appointment"
# #   - Response: {{"content": "Sure thing, let's get you an appointment! When are you free?", "next_node_id": "node_appointment", "state_updates": {{}}}}
# # """

   
#         prompt = f"""
#         You are a friendly, conversational assistant helping a patient with healthcare interactions. Your goal is to have a natural, human-like conversation. You must strictly follow the provided instructions and use ONLY the information given in the context. Do NOT use outside knowledge for healthcare advice.

#  1. Check the patient's profile to see if any required fields are missing, and ask for them one at a time if needed.
# 2. If the profile is complete, guide the conversation using flow instructions as a loose guide, but respond naturally to the user's message.
# 3. If the user's message doesn't match the current flow instructions, use document content or general knowledge to provide a helpful, relevant response.
# 4. When the user asks specific questions about medical information, treatments, or medications, ALWAYS check the document content first and provide that information.
# 5. Maintain a warm, empathetic tone, like you're talking to a friend.
# 6. REMEMBER User Message :  {message} can be Yes for 'Y' or No for 'N' Or Vice Versa So Do not misinterpret them and Consider Same. 


# Current Date (MM/DD/YYYY): {current_date}

# User Message: "{message}"

# Conversation History:
# {conversation_history}

# Patient ID: {patientId}

# Assistant ID: {assistantId}

# Flow ID: {flow_id}

# Patient Profile (includes phone and organization_id):
# {patient_fields}

# Structured Flow Instructions (Use this to guide conversation flow based on user responses):
# {flow_instruction_context}

# Document Content:
# {document_context}

# Session Data:
# {json.dumps(session_data, indent=2)}

# 1.  **Check Patient Profile**:
#     - Review the `Patient Profile` JSON to identify any fields (excluding `id`, `mrn`, `created_at`, `updated_at`, `organization_id`, `phone`) that are null, empty, or missing.
#     - If any fields are missing, select **one** (from: first name, last name, date of birth, gender, email) to ask for in a natural way.
#     - If the user provides input for the requested field, validate it:
#         - Text (names, gender, email): Use regex `^[a-zA-Z0-9@.\s-]+$` (allows common characters, spaces, hyphen, @ . for email). Avoid names that look like random characters.
#         - Dates (date_of_birth, LMP, EDD): Must be a valid date in MM/DD/YYYY format, not after `Current Date`.
#     - If the user provides a valid value for the requested field, issue an `UPDATE_PATIENT` command with the patient_id, field_name, and field_value.
#     - If the input is invalid, ask again for the *same field* with a friendly clarification and the expected format (e.g., "Sorry, that doesn't look like a valid date. Could you try again, like 03/29/1996?").
#     - If no *required* fields (first name, last name, date of birth, gender, email) are missing, proceed to conversation flow.

# 2. **Conversation Flow (If Profile Complete)**:
   
#         **Step 2.1: Normalize User Input**
#             - Convert user responses to standard format:
#                 - "yes", "YES", "y", "Y" → "Y"
#                 - "no", "NO", "n", "N" → "N" 
#                 - "a", "A" → "A", "b", "B" → "B", etc.
#                 - Keep dates and other text as-is but validate format

#         **Step 2.2: Determine Response Type**
#             - **Direct Response**: User is answering the last assistant question (Y/N, A/B/C, date, etc.)
#             - **New Topic**: User introduces a new subject/question
            
#         **Step 2.3: Process Direct Responses**
#             If this is a direct response to the last assistant message:
            
#             a) **Find Current Active Node:**
#                 - Take the last assistant message from conversation history
#                 - Search through `Structured Flow Instructions` to find the node whose message text EXACTLY or CLOSELY matches the last assistant message
#                 - This is your "current_active_node"
            
#             b) **Follow Branching Logic:**
#                 - Within the current_active_node definition, find the branching logic that matches the normalized user input
#                 - Extract the target node_id from that branch
#                 - Example: If current_active_node has "If Y → Go to: enter_lmp_date" and user said "Y", then target_node_id = "enter_lmp_date"
            
#             c) **Get Target Node Content:**
#                 - Find the target_node_id definition in `Structured Flow Instructions`
#                 - Use that node's message as your response content
#                 - Extract the next_node_id from that target node's definition
            
#             d) **Special Date Handling:**
#                 - **LMP Date Input**: If current_active_node was asking for LMP date and user provided a date:
#                     * Validate format MM/DD/YYYY and not after {current_date}
#                     * Calculate gestational age: weeks = (current_date - lmp_date) / 7
#                     * Determine trimester: ≤12 weeks = "First", 13-27 weeks = "Second", ≥28 weeks = "Third"
#                     * Include gestational age in response: "You're about X weeks along, in your [trimester] trimester!"
#                     * Store in state_updates: {{"gestational_age_weeks": X, "trimester": "First/Second/Third"}}
#                     * Continue with the target node's flow
                
#                 - **EDD Date Input**: Similar validation and processing for estimated due dates
        
#         **Step 2.4: Process New Topics**
#             If this is NOT a direct response (user introduces new topic):
            
#             a) **Identify User Intent:**
#                 - Analyze user message for key topics: symptoms, bleeding, nausea, medications, appointments, pregnancy test, etc.
            
#             b) **Find Entry Point Node:**
#                 - Search `Structured Flow Instructions` for the most relevant entry point node
#                 - Examples:
#                     * "bleeding" → find "vaginal_bleeding_1st_trimester" node
#                     * "nausea" → find "nausea_1st_trimester" node  
#                     * "symptoms" → find "symptom_triage" node
#                     * "medication" → find "medications_response" node
#                     * "appointment" → find "appointment_response" node
            
#             c) **Set Response:**
#                 - Use the entry point node's message as response content
#                 - Set next_node_id to that node's next_node_id value
            
#         **Step 2.5: Fallback Processing**
#             - If no matching node found in flow instructions, check `Document Content` for relevant information
#             - If document content has relevant info, use it with next_node_id = null
#             - Otherwise, provide general helpful response with next_node_id = null

#         **Step 2.6: Response Enhancement**
#             - After determining primary response from flow node, scan `Document Content` for:
#                 * Phone numbers, URLs, medication names, specific resources
#                 * Include these VERBATIM if relevant to the user's query
#                 * Do not override the flow response, but enhance it with specific details

#         **Step 2.7: Handle Empty Conversation**
#             - If `Conversation History` is empty:
#                 * Find "start_conversation" node in `Structured Flow Instructions`
#                 * Use its message as response content  
#                 * Set next_node_id = "menu_items"
#                 * If "start_conversation" not found, use "menu_items" node message and set next_node_id = "menu_items"

#         **Critical Validation Rules:**
#             - All dates must be MM/DD/YYYY format and not after {current_date}
#             - For gestational age calculation: Use the exact formula (current_date - lmp_date) in days, then divide by 7 for weeks
#             - Always include gestational age and trimester in response when LMP is provided
#             - Y/N responses are case-insensitive and should work with yes/no variants
#             - Letter choices (A, B, C, etc.) are case-insensitive
#             - When following flow branches, use EXACT node_id matches from the flow instructions

# 3.  **Response Style**:
#     - Maintain a warm, empathetic, and conversational tone. Avoid rigid, overly formal language.
#     - If the user's input is unexpected or off-topic but doesn't trigger a new flow entry point, acknowledge it briefly and then deliver the message from the current flow node or a relevant fallback like `default_response`.

# 4.  **Database Operations**:
#     - Issue `UPDATE_PATIENT` as per Step 1.
#     - `CREATE_PATIENT` is unlikely needed as patientId is provided.

# 5.  **Flow Progression**:
#     - Set the `next_node_id` output variable to the `TARGET_NODE_ID` determined in Step 2.3. If the `(next_node_id: ...)` from the `TARGET_NODE_ID` definition was `null`, set `next_node_id` to `null`.

# 6.  **General Instructions**
#     - If `Conversation History` is empty, initiate the conversation by finding the definition for `menu_items` in `Structured Flow Instructions` and generating the response from its message. Set `next_node_id` based on its default `(next_node_id: menu_items)` -> `(next_node_id: menu_items)` branch definition (which usually self-loops or leads to the next step based on user selection, depending on how you interpret that initial message structure). For the initial menu, the *system* handles the branching based on the letter reply, so the initial `next_node_id` *sent to the system* should be the ID of the node *waiting* for the reply, which is `menu_items` itself. Wait, looking at the structure `Start Conversation` -> `menu_items`, then `Menu-Items` has the branches. So the initial response for empty history should be the message from `start_conversation`, and the `next_node_id` should be `menu_items`. If `start_conversation` isn't retrieved or active, then `menu_items` is the fallback entry. Yes, the original text shows `start_conversation` leads to `menu_items`. Let's stick to that flow. If `Conversation History` is empty, find `start_conversation`, use its message, and set `next_node_id` to `menu_items`. If `start_conversation` is not in retrieved context, default to `menu_items` message and set `next_node_id` to `menu_items`.
#     - If a profile field is missing (Step 1 applies), do *not* process the conversation flow (Step 2).

# 7.  **Response Structure**:
#     Return a JSON object:
#     ```json
#     {{
#       "content": "Your friendly response to the user, potentially augmented with document info and gestational age.",
#       "next_node_id": "ID of the next node or current node, based on flow logic or profile step.",
#       "state_updates": {{"gestational_age_weeks": N, "trimester": "String", ...}}, // Include date calculation results if applicable
#       "database_operation": {{
#         "operation": "UPDATE_PATIENT | CREATE_PATIENT", // Only include if an operation is needed
#         "parameters": {{
#           "patient_id": "string",
#           "field_name": "string",
#           "field_value": "string"
#         }}
#       }} // Optional, only when updating/creating
#     }}
#     ```

# Examples:

# - Profile: {{"first_name": null, "last_name": null, "date_of_birth": null}}, Message: "hi", Conversation History: Empty
#   - Response: {{"content": "Hey, nice to hear from you! I need a bit of info to get you set up. Could you share your first name?", "next_node_id": null, "state_updates": {{}}}} (Asks for first name first)
# - Profile: {{"first_name": "Shenal", "last_name": null, "date_of_birth": null}}, Message: "Jones", Conversation History: [{{"role": "assistant", "content": "Could you share your first name?"}}, {{"role": "user", "content": "Shenal"}}] 
# - Profile: {{"first_name": "Shenal", "last_name": null, "date_of_birth": null}}, Message: "Jones", Conversation History: [{{"role": "assistant", "content": "Hey Shenal! I need a bit more info... Could you share your last name?"}}, {{"role": "user", "content": "Jones"}}]
#   - Response: {{"content": "Awesome, thanks for sharing, Shenal Jones! Now, what's your date of birth, like 03/29/1996?", "next_node_id": null, "state_updates": {{}}, "database_operation": {{"operation": "UPDATE_PATIENT", "parameters": {{"patient_id": "{patientId}", "field_name": "last_name", "field_value": "Jones"}}}}}}
# - Profile complete, Conversation History: Empty, Message: "hi"
#   - Response: {{"content": "Hi $patient_firstname! I'm here to help you with your healthcare needs. What would you like to talk about today? A) I have a question about symptoms B) I have a question about medications ...", "next_node_id": "menu_items", "state_updates": {{}}}} (Uses the start_conversation message)
# - Profile complete, Conversation History: [... assistant: "What are you looking for today? A) Symptoms...", user: "A"], Message: "A"
#   - Response: {{"content": "We understand questions and concerns come up. You can try texting this number with your question... If you're worried... seek medical attention.", "next_node_id": "symptom_triage", "state_updates": {{}}}} (Follows Menu-Items 'A' branch)
# - Profile complete, Conversation History: [... assistant: "Please reply in this format: MM/DD/YYYY" (from enter_lmp_date)], Message: "12/01/2023" (Assuming current_date is 05/20/2024)
#   - Response: {{"content": "Perfect. Thanks so much. Based on that date, you're about 24 weeks along, in your second trimester! Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now.", "next_node_id": "pregnancy_intention_survey", "state_updates": {{"gestational_age_weeks": 24, "trimester": "Second"}}}} (Validates date, calculates age/trimester, includes in message, updates state, moves to next node)
# - Profile complete, Conversation History: [... assistant: "OK. We're here to help..."], Message: "Where can I get birth control?" Document Content includes the "Contraception Resources" node.
#   - Response: {{"content": "Okay, I can help with that. Birth control is available at no cost with most insurance plans. Let us know if you'd like support connecting to resources.", "next_node_id": "null", "state_updates": {{}}}} (Identifies "Contraception Resources" as best node for new topic, uses its message and next_node_id).
  
#   """
#         # Call LLM
#         response_text = Settings.llm.complete(prompt).text  # Replace with Settings.llm.complete
#         if "```json" in response_text:
#             response_text = response_text.split("```json")[1].split("```")[0].strip()
#         response_data = json.loads(response_text)
#         print(f"[LLM RESPONSE DATA] {response_data}")
#         content = response_data.get("content", "I'm having trouble processing your request.")
#         next_node_id = response_data.get("next_node_id")
#         state_updates = response_data.get("state_updates", {})
#         database_operation = response_data.get("database_operation")

#         # Execute database operation
#         operation_result = None
#         if database_operation:
#             operation = database_operation.get("operation")
#             parameters = database_operation.get("parameters", {})
#             try:
#                 if operation == "UPDATE_PATIENT":
#                     patient = db.query(Patient).filter(Patient.id == patientId).first()
#                     if not patient:
#                         raise HTTPException(status_code=404, detail="Patient not found")
#                     setattr(patient, parameters["field_name"], parameters["field_value"])
#                     patient.updated_at = datetime.utcnow()
#                     db.commit()
#                     db.refresh(patient)
#                     operation_result = {
#                         "id": patient.id,
#                         "mrn": patient.mrn,
#                         "first_name": patient.first_name,
#                         "last_name": patient.last_name,
#                         "date_of_birth": patient.date_of_birth,
#                         "phone": patient.phone,
#                         "organization_id": patient.organization_id
#                     }
#                     # Update JSON file
#                     patient_path = f"patients/{patient.id}.json"
#                     os.makedirs(os.path.dirname(patient_path), exist_ok=True)
#                     with open(patient_path, "w") as f:
#                         patient_dict = {
#                             "id": patient.id,
#                             "mrn": patient.mrn,
#                             "first_name": patient.first_name,
#                             "last_name": patient.last_name,
#                             "date_of_birth": patient.date_of_birth,
#                             "phone": patient.phone,
#                             "organization_id": patient.organization_id,
#                             "created_at": patient.created_at.isoformat() if patient.created_at else None,
#                             "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
#                         }
#                         json.dump(patient_dict, f, indent=2)
#                     content += f"\nProfile updated successfully!"
#                 elif operation == "CREATE_PATIENT":
#                     # Fallback if patientId is invalid; use session_data for phone/organization_id
#                     mrn = generate_mrn()
#                     patient = Patient(
#                         id=str(uuid.uuid4()),
#                         mrn=mrn,
#                         first_name=parameters.get("first_name", ""),
#                         last_name=parameters.get("last_name", ""),
#                         date_of_birth=parameters.get("date_of_birth"),
#                         phone=session_data.get("phone", "unknown"),
#                         organization_id=session_data.get("organization_id", "default_org"),
#                         created_at=datetime.utcnow(),
#                         updated_at=datetime.utcnow()
#                     )
#                     db.add(patient)
#                     db.commit()
#                     db.refresh(patient)
#                     operation_result = {
#                         "id": patient.id,
#                         "mrn": patient.mrn,
#                         "first_name": patient.first_name,
#                         "last_name": patient.last_name,
#                         "date_of_birth": patient.date_of_birth,
#                         "phone": patient.phone,
#                         "organization_id": patient.organization_id
#                     }
#                     # Save JSON file
#                     patient_path = f"patients/{patient.id}.json"
#                     os.makedirs(os.path.dirname(patient_path), exist_ok=True)
#                     with open(patient_path, "w") as f:
#                         patient_dict = {
#                             "id": patient.id,
#                             "mrn": patient.mrn,
#                             "first_name": patient.first_name,
#                             "last_name": patient.last_name,
#                             "date_of_birth": patient.date_of_birth,
#                             "phone": patient.phone,
#                             "organization_id": patient.organization_id,
#                             "created_at": patient.created_at.isoformat() if patient.created_at else None,
#                             "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
#                         }
#                         json.dump(patient_dict, f, indent=2)
#                     content += f"\nProfile created successfully!"
#             except Exception as e:
#                 db.rollback()
#                 print(f"Database operation failed: {str(e)}")
#                 content += f"\nSorry, I couldn’t update your profile. Let’s try again."
#                 response_data["next_node_id"] = current_node_id

#         print(f"Response: {content}")
#         print(f"Next node ID: {next_node_id}")
#         print("==== PATIENT ONBOARDING/CHAT COMPLETE ====\n")

#         response = {
#             "content": content,
#             "next_node_id": next_node_id,
#             "state_updates": state_updates
#         }
#         if operation_result:
#             response["operation_result"] = operation_result
#         return response

#     except Exception as e:
#         print(f"ERROR in patient_onboarding: {str(e)}")
#         return {
#             "error": f"Failed to process message: {str(e)}",
#             "content": "I'm having trouble processing your request. Please try again."
#         }

@app.get("/api/flow-index/{flow_id}")
async def check_flow_index_status(flow_id: str):
    """
    Check if a flow has been indexed and return its status.
    """
    try:
        # Check in-memory cache
        if flow_id in app.state.flow_indices:
            return {
                "indexed": True,
                "source": "memory",
                "metadata": {
                    "flow_id": flow_id,
                    "collection_name": f"flow_{flow_id}_knowledge"
                }
            }

        # Check GCS for metadata file
        bucket = storage_client.bucket(BUCKET_NAME)
        meta_blob = bucket.blob(f"flow_metadata/{flow_id}_meta.pkl")
        if meta_blob.exists():
            # Download metadata file to temporary location
            temp_meta_file = f"temp_{flow_id}_meta.pkl"
            meta_blob.download_to_filename(temp_meta_file)
            try:
                with open(temp_meta_file, "rb") as f:
                    metadata = pickle.load(f)
                os.remove(temp_meta_file)
                return {
                    "indexed": True,
                    "source": "gcs",
                    "metadata": metadata,
                    "document_count": metadata.get("embedding_count", 0)
                }
            except Exception as e:
                os.remove(temp_meta_file)
                return {
                    "indexed": False,
                    "error": f"Failed to read metadata: {str(e)}"
                }
        else:
            return {
                "indexed": False,
                "error": "Flow not indexed"
            }
    except Exception as e:
        return {
            "indexed": False,
            "error": f"Error checking index status: {str(e)}"
        }
    
@app.get("/api/index/status/{assistant_id}")
async def check_indexing_status(assistant_id: str):
    """Check the status of document indexing for an assistant"""
    try:
        # Check if the collection exists
        collection_name = f"documents_{assistant_id}_knowledge"
        try:
            collection = chroma_client.get_collection(collection_name)
            count = collection.count()
            return {
                "status": "completed" if count > 0 else "in_progress",
                "document_count": count
            }
        except ValueError:
            # Collection doesn't exist yet
            return {
                "status": "not_started",
                "document_count": 0
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

## Analyze Message
# @app.post("/api/analyze-message")
# async def analyze_message(request: dict):
#     try:
#         message = request.get("message", "")
#         response = request.get("response", "")
#         session_id = request.get("sessionId", "")
#         timestamp = request.get("timestamp", datetime.utcnow().isoformat())
        
#         print(f"Analyzing message. SessionID: {session_id}, Message: {message[:50]}...")
        
#         # Get current date in Eastern Time
#         eastern = pytz.timezone('America/New_York')
#         current_time = datetime.now(eastern)
#         current_date = current_time.date().strftime('%m/%d/%Y')
#         print(f"Found the current date: {current_date}")
        
#         # Fetch conversation history (last 5 messages for context)
#         db = SessionLocal()
#         recent_messages = db.query(SessionAnalytics).filter(
#             SessionAnalytics.session_id == session_id
#         ).order_by(SessionAnalytics.timestamp.desc()).limit(5).all()
#         db.close()
        
#         context = "\n".join([
#             f"AI: {msg.assistant_response}\nUser: {msg.message_text}"
#             for msg in reversed(recent_messages)
#         ])
        
#         # Prompt to analyze message and calculate trimester only for LMP responses
#         # prompt = f"""
#         # Current date: {current_date}

#         # Conversation context (recent messages):
#         # {context}

#         # Current message:
#         # User message: "{message}"
#         # AI response: "{response}"

#         # Analyze the current user message using the conversation context to understand the intent and categorize data correctly. Return results in JSON format:

#         # 1. Basic Analysis:
#         #    - Sentiment: Analyze the *user's message* for sentiment (positive, negative, neutral, anxious, confused).
#         #    - Urgency: Determine urgency based on the *user's message* (high, medium, low).
#         #    - Intent: Classify the *user's intent* (question, sharing information, seeking reassurance, reporting symptom).
#         #    - Topic: Identify the main topic of the *user's message*.
#         #    - Keywords: Extract 3-5 key terms from the *user's message*.

#         # 2. Medical Data Extraction (from *user's message* only):
#         #    - Dates: Extract dates provided by the user. Categorize based on context:
#         #      - "last_menstrual_period" if responding to an AI question about LMP (e.g., "What was the first day of your last menstrual period?").
#         #      - "due_date" for estimated delivery dates.
#         #      - "appointment_date" for explicit appointment mentions.
#         #    - Symptoms: Identify symptoms reported by the user with severity (none, mild, moderate, severe).
#         #    - Measurements: Extract numerical health data reported by the user (e.g., weight, blood pressure).
#         #    - Medications: Identify medications the user explicitly states they are taking.

#         # 3. Pregnancy-Specific Analysis (from *user's message* only):
#         #    - Trimester Indicators:
#         #      - Only calculate gestational age if:
#         #        - The AI's most recent message in the context asked for the last menstrual period (e.g., contains "last menstrual period" or "LMP" and requests a date).
#         #        - The user's current message provides a date in MM/DD/YYYY format.
#         #      - If both conditions are met:
#         #        - Convert the provided LMP date to a datetime object.
#         #        - Calculate weeks pregnant: ({current_date} - LMP_date).days / 7.
#         #        - Determine trimester:
#         #          - First trimester: 0–13 weeks.
#         #          - Second trimester: 14–26 weeks.
#         #          - Third trimester: 27–40 weeks.
#         #        - If the LMP date is invalid (e.g., future date relative to {current_date} or >1 year ago), return "Invalid LMP date".
#         #      - Otherwise, return null.
#         #    - Risk Factors: Identify any pregnancy-related complications or risk factors reported in the user's message (e.g., "high blood pressure", "gestational diabetes").
#         #    - Fetal Activity: Identify any user-reported fetal movements or activity (e.g., "I felt the baby kick").
#         #    - Emotional State: Identify any pregnancy-specific emotional states reported in the user's message (e.g., "I'm anxious about my pregnancy").

#         # 4. Contextual Analysis:
#         #    - Use the AI's most recent message in the context to determine if it asked for the LMP date for trimester calculation.
#         #    - Extract pregnancy-specific data (risk factors, fetal activity, emotional state) from the user's message independently of the LMP question.
#         #    - Do not extract medical or pregnancy data from the AI's response.
#         #    - If a date matches the user's date of birth (e.g., 29/04/1999 from survey responses), do not use it as LMP.

#         # Return your analysis as a JSON object:
#         # {{
#         #     "sentiment": "string",
#         #     "urgency": "string",
#         #     "intent": "string",
#         #     "topic": "string",
#         #     "keywords": ["string"],
#         #     "medical_data": {{
#         #         "dates": {{"type": "string", "value": "string"}} or null,
#         #         "symptoms": [{{"name": "string", "severity": "string"}}],
#         #         "measurements": {{"type": "string", "value": "string"}} or null,
#         #         "medications": ["string"]
#         #     }},
#         #     "pregnancy_specific": {{
#         #         "trimester_indicators": "string" or null,
#         #         "risk_factors": ["string"],
#         #         "fetal_activity": "string" or null,
#         #         "emotional_state": "string" or null
#         #     }}
#         # }}

#         # If no relevant data is found, return empty arrays or null values for the respective fields.
#         # """
#         prompt = f"""
#             Current date: {current_date}

#             Conversation context (recent messages):
#             {context}

#             Current message:
#             User message: "{message}"
#             AI response: "{response}"
#             LMP : Last Menstural Period 

#             Analyze the current user message using the conversation context to understand the intent and categorize data correctly. Return results in JSON format:

#             1. Basic Analysis:
#             - Sentiment: Analyze the *user's message* for sentiment (positive, negative, neutral, anxious, confused).
#             - Urgency: Determine urgency based on the *user's message* (high, medium, low).
#             - Intent: Classify the *user's intent* (question, sharing information, seeking reassurance, reporting symptom).
#             - Topic: Identify the main topic of the *user's message*.
#             - Keywords: Extract 3-5 key terms from the *user's message*.

#             2. Medical Data Extraction (from *user's message* only):
#             - Dates: Extract dates provided by the user in MM/DD/YYYY format. Categorize based on context:
#                 - "last_menstrual_period" if the AI's most recent message in the context explicitly asked for LMP (e.g., contains "last menstrual period" or "LMP" and requests a date).
#                 - "due_date" for estimated delivery dates.
#                 - "appointment_date" for explicit appointment mentions.
#             - Symptoms: Identify symptoms reported by the user with severity (none, mild, moderate, severe).
#             - Measurements: Extract numerical health data reported by the user (e.g., weight, blood pressure).
#             - Medications: Identify medications the user explicitly states they are taking.

#             3. Pregnancy-Specific Analysis (from *user's message* only):
#             - Trimester Indicators:
#                 - Only calculate gestational age if:
#                 - The AI's most recent message in the context contains "last menstrual period" or "LMP" and requests a date (e.g., "What was the first day of your last menstrual period?").
#                 - The user's current message provides a date in MM/DD/YYYY format.
#                 - If both conditions are met:
#                 - Parse the provided LMP date as a datetime object in MM/DD/YYYY format.
#                 - Calculate weeks pregnant: (({current_date} - LMP_date).days / 7).
#                 - Determine trimester:
#                     - First trimester: 0 to 13 weeks (inclusive).
#                     - Second trimester: 14 to 26 weeks (inclusive).
#                     - Third trimester: 27 to 40 weeks (inclusive).
#                 - Validate the LMP date:
#                     - If the LMP date is in the future relative to {current_date}, return "Invalid LMP date".
#                     - If the LMP date is more than 365 days (1 year) before {current_date}, return "Invalid LMP date".
#                 - Return the trimester as a string (e.g., "First trimester") or "Invalid LMP date" if validation fails.
#                 - Otherwise, return null (e.g., for symptom reports or non-LMP date messages).
#             - Risk Factors: Identify any pregnancy-related complications or risk factors reported in the user's message (e.g., "high blood pressure", "gestational diabetes").
#             - Fetal Activity: Identify any user-reported fetal movements or activity (e.g., "I felt the baby kick").
#             - Emotional State: Identify any pregnancy-specific emotional states reported in the user's message (e.g., "I'm anxious about my pregnancy").

#             4. Contextual Analysis:
#             - Use the AI's most recent message in the context to determine if it asked for the LMP date for trimester calculation.
#             - Extract pregnancy-specific data (risk factors, fetal activity, emotional state) from the user's message independently of the LMP question.
#             - Do not extract medical or pregnancy data from the AI's response.
#             - If a date matches the user's date of birth (e.g., 29/04/1999 from survey responses), do not use it as LMP.

#             Return your analysis as a JSON object:
#             {{
#                 "sentiment": "string",
#                 "urgency": "string",
#                 "intent": "string",
#                 "topic": "string",
#                 "keywords": ["string"],
#                 "medical_data": {{
#                     "dates": {{"type": "string", "value": "string"}} or null,
#                     "symptoms": [{{"name": "string", "severity": "string"}}],
#                     "measurements": {{"type": "string", "value": "string"}} or null,
#                     "medications": ["string"]
#                 }},
#                 "pregnancy_specific": {{
#                     "trimester_indicators": "string" or null,
#                     "risk_factors": ["string"],
#                     "fetal_activity": "string" or null,
#                     "emotional_state": "string" or null
#                 }}
#             }}

#             If no relevant data is found, return empty arrays or null values for the respective fields.
#             """
        
        
#         # Call the LLM
#         llm_response = Settings.llm.complete(prompt)
#         print(f"Raw LLM response: {llm_response.text[:200]}...")
        
#         # Parse and clean response
#         cleaned_response = llm_response.text.strip()
#         if cleaned_response.startswith("```json"):
#             cleaned_response = cleaned_response[7:]
#         if cleaned_response.endswith("```"):
#             cleaned_response = cleaned_response[:-3]
#         cleaned_response = cleaned_response.strip()
        
#         print(f"Cleaned response: {cleaned_response}...")
        
#         # Parse JSON
#         try:
#             analytics_data = json.loads(cleaned_response)
            
#             # Validate analytics data
#             def validate_analytics_data(data, user_message, ai_response):
#                 # Validate medications
#                 if "medications" in data.get("medical_data", {}):
#                     user_words = set(user_message.lower().split())
#                     valid_medications = [
#                         med for med in data["medical_data"]["medications"]
#                         if any(word in user_words for word in med.lower().split())
#                     ]
#                     data["medical_data"]["medications"] = valid_medications

#                 # Validate dates and ensure LMP is correctly identified
#                 if "medical_data" in data and "dates" in data["medical_data"]:
#                     # Handle null or invalid dates
#                     if data["medical_data"]["dates"] is None:
#                         data["medical_data"]["dates"] = None
#                     # Handle list of dates
#                     elif isinstance(data["medical_data"]["dates"], list):
#                         for date_entry in data["medical_data"]["dates"]:
#                             if isinstance(date_entry, dict) and date_entry.get("type") == "last_menstrual_period":
#                                 data["medical_data"]["dates"] = {
#                                     "type": "last_menstrual_period",
#                                     "value": date_entry.get("value")
#                                 }
#                                 break
#                         else:
#                             data["medical_data"]["dates"] = None
#                     # Handle dict dates
#                     elif isinstance(data["medical_data"]["dates"], dict):
#                         # Ensure it's an LMP date if AI asked for it
#                         if (data["medical_data"]["dates"].get("type") != "last_menstrual_period" or
#                             "last menstrual period" not in ai_response.lower()):  # Fixed condition
#                             data["medical_data"]["dates"] = None

#                 # Validate trimester_indicators
#                 if "pregnancy_specific" in data and "trimester_indicators" in data["pregnancy_specific"]:
#                     # Only calculate trimester if valid LMP date and AI asked for it
#                     if not (
#                         isinstance(data.get("medical_data", {}).get("dates"), dict) and
#                         data["medical_data"]["dates"] is not None and
#                         data["medical_data"]["dates"].get("type") == "last_menstrual_period" and
#                         "last menstrual period" in ai_response.lower()  # Fixed condition
#                     ):
#                         data["pregnancy_specific"]["trimester_indicators"] = None
#                     else:
#                         # Recalculate trimester to ensure correctness
#                         lmp_date_str = data["medical_data"]["dates"].get("value")
#                         try:
#                             lmp_date = datetime.strptime(lmp_date_str, '%m/%d/%Y').date()
#                             current_date_obj = datetime.strptime(current_date, '%m/%d/%Y').date()
#                             days_since_lmp = (current_date_obj - lmp_date).days
#                             weeks_pregnant = days_since_lmp / 7.0
#                             # Validate LMP date
#                             if days_since_lmp < 0:  # Future date
#                                 data["pregnancy_specific"]["trimester_indicators"] = "Invalid LMP date"
#                             elif days_since_lmp > 365:  # More than 1 year ago
#                                 data["pregnancy_specific"]["trimester_indicators"] = "Invalid LMP date"
#                             elif 0 <= weeks_pregnant <= 13:
#                                 data["pregnancy_specific"]["trimester_indicators"] = "First trimester"
#                             elif 14 <= weeks_pregnant <= 26:
#                                 data["pregnancy_specific"]["trimester_indicators"] = "Second trimester"
#                             elif 27 <= weeks_pregnant <= 40:
#                                 data["pregnancy_specific"]["trimester_indicators"] = "Third trimester"
#                             else:
#                                 data["pregnancy_specific"]["trimester_indicators"] = "Invalid LMP date"
#                         except ValueError:
#                             data["pregnancy_specific"]["trimester_indicators"] = "Invalid LMP date"

#                 return data
            
            
#             analytics_data = validate_analytics_data(analytics_data, message, response)
            
#             # Store in database
#             analytics_id = str(uuid.uuid4())
#             word_count = len(message.split())
#             medical_data_json = json.dumps(analytics_data.get("medical_data", {}))
#             pregnancy_specific_json = json.dumps(analytics_data.get("pregnancy_specific", {}))
#             emotional_state = analytics_data.get("pregnancy_specific", {}).get("emotional_state")
            
#             db = SessionLocal()
#             db_analytics = SessionAnalytics(
#                 id=analytics_id,
#                 session_id=session_id,
#                 timestamp=datetime.fromisoformat(timestamp),
#                 message_text=message,
#                 assistant_response=response,
#                 sentiment=analytics_data.get("sentiment", "neutral"),
#                 urgency=analytics_data.get("urgency", "low"),
#                 intent=analytics_data.get("intent", ""),
#                 topic=analytics_data.get("topic", ""),
#                 keywords=json.dumps(analytics_data.get("keywords", [])),
#                 word_count=word_count,
#                 medical_data=medical_data_json,
#                 pregnancy_specific=pregnancy_specific_json,
#                 emotional_state=emotional_state,
#                 session_duration=0,
#                 response_time=0
#             )
            
#             db.add(db_analytics)
#             db.commit()
#             db.refresh(db_analytics)
#             db.close()
            
#             print(f"Analytics saved for session {session_id}")
            
#             return {
#                 "status": "success",
#                 "analytics_id": analytics_id,
#                 "data": analytics_data
#             }
            
#         except json.JSONDecodeError as json_err:
#             print(f"JSON parsing error: {str(json_err)}")
#             analytics_id = str(uuid.uuid4())
#             word_count = len(message.split())
#             db = SessionLocal()
#             db_analytics = SessionAnalytics(
#                 id=analytics_id,
#                 session_id=session_id,
#                 timestamp=datetime.fromisoformat(timestamp),
#                 message_text=message,
#                 assistant_response=response,
#                 sentiment="neutral",
#                 urgency="low",
#                 intent="unknown",
#                 topic="general",
#                 keywords=json.dumps([]),
#                 word_count=word_count,
#                 medical_data=json.dumps({}),
#                 pregnancy_specific=json.dumps({}),
#                 emotional_state=None,
#                 session_duration=0,
#                 response_time=0
#             )
#             db.add(db_analytics)
#             db.commit()
#             db.refresh(db_analytics)
#             db.close()
            
#             return {
#                 "status": "partial_success",
#                 "message": f"Saved with default values due to LLM response parsing error: {str(json_err)}",
#                 "analytics_id": analytics_id,
#                 "raw_response": llm_response.text
#             }
            
#     except Exception as e:
#         print(f"Error in analyze-message endpoint: {str(e)}")
#         return {
#             "status": "error",
#             "message": f"Failed to analyze message: {str(e)}"
#         }

@app.post("/api/analyze-message")
async def analyze_message(request: dict):
    try:
        message = request.get("message", "")
        response = request.get("response", "")
        session_id = request.get("sessionId", "")
        timestamp = request.get("timestamp", datetime.utcnow().isoformat())
        
        print(f"Analyzing message. SessionID: {session_id}, Message: {message[:50]}...")
        
        # Get current date in Eastern Time
        eastern = pytz.timezone('America/New_York')
        current_time = datetime.now(eastern)
        current_date = current_time.date().strftime('%m/%d/%Y')
        print(f"Found the current date: {current_date}")
        
        # Fetch conversation history (last 5 messages for context)
        db = SessionLocal()
        recent_messages = db.query(SessionAnalytics).filter(
            SessionAnalytics.session_id == session_id
        ).order_by(SessionAnalytics.timestamp.desc()).limit(5).all()
        db.close()
        
        context = "\n".join([
            f"AI: {msg.assistant_response}\nUser: {msg.message_text}"
            for msg in reversed(recent_messages)
        ])
        
        prompt = f"""
            Current date: {current_date}

            Conversation context (recent messages):
            {context}

            Current message:
            User message: "{message}"
            AI response: "{response}"
            LMP : Last Menstural Period 

            Analyze the current user message using the conversation context to understand the intent and categorize data correctly. Return results in JSON format:

            1. Basic Analysis:
            - Sentiment: Analyze the *user's message* for sentiment (positive, negative, neutral, anxious, confused).
            - Urgency: Determine urgency based on the *user's message* (high, medium, low).
            - Intent: Classify the *user's intent* (question, sharing information, seeking reassurance, reporting symptom).
            - Topic: Identify the main topic of the *user's message*.
            - Keywords: Extract 3-5 key terms from the *user's message*.

            2. Medical Data Extraction (from *user's message* only):
            - Dates: Extract dates provided by the user in MM/DD/YYYY format. Categorize based on context:
                - "last_menstrual_period" if the AI's most recent message in the context explicitly asked for LMP (e.g., contains "last menstrual period" or "LMP" and requests a date).
                - "due_date" for estimated delivery dates.
                - "appointment_date" for explicit appointment mentions.
            - Symptoms: Identify symptoms reported by the user with severity (none, mild, moderate, severe).
            - Measurements: Extract numerical health data reported by the user (e.g., weight, blood pressure).
            - Medications: Identify medications the user explicitly states they are taking.

            3. Pregnancy-Specific Analysis (from *user's message* only):
            - Trimester Indicators:
                - Only calculate gestational age if:
                - The AI's most recent message in the context contains "last menstrual period" or "LMP" and requests a date (e.g., "What was the first day of your last menstrual period?").
                - The user's current message provides a date in MM/DD/YYYY format.
                - If both conditions are met:
                - Parse the provided LMP date as a datetime object in MM/DD/YYYY format.
                - Calculate weeks pregnant: (({current_date} - LMP_date).days / 7).
                - Determine trimester:
                    - First trimester: 0 to 13 weeks (inclusive).
                    - Second trimester: 14 to 26 weeks (inclusive).
                    - Third trimester: 27 to 40 weeks (inclusive).
                - Validate the LMP date:
                    - If the LMP date is in the future relative to {current_date}, return "Invalid LMP date".
                    - If the LMP date is more than 365 days (1 year) before {current_date}, return "Invalid LMP date".
                - Return the trimester as a string (e.g., "First trimester") or "Invalid LMP date" if validation fails.
                - Otherwise, return null (e.g., for symptom reports or non-LMP date messages).
            - Risk Factors: Identify any pregnancy-related complications or risk factors reported in the user's message (e.g., "high blood pressure", "gestational diabetes").
            - Fetal Activity: Identify any user-reported fetal movements or activity (e.g., "I felt the baby kick").
            - Emotional State: Identify any pregnancy-specific emotional states reported in the user's message (e.g., "I'm anxious about my pregnancy").

            4. Contextual Analysis:
            - Use the AI's most recent message in the context to determine if it asked for the LMP date for trimester calculation.
            - Extract pregnancy-specific data (risk factors, fetal activity, emotional state) from the user's message independently of the LMP question.
            - Do not extract medical or pregnancy data from the AI's response.
            - If a date matches the user's date of birth (e.g., 29/04/1999 from survey responses), do not use it as LMP.

            Return your analysis as a JSON object:
            {{
                "sentiment": "string",
                "urgency": "string",
                "intent": "string",
                "topic": "string",
                "keywords": ["string"],
                "medical_data": {{
                    "dates": {{"type": "string", "value": "string"}} or null,
                    "symptoms": [{{"name": "string", "severity": "string"}}],
                    "measurements": {{"type": "string", "value": "string"}} or null,
                    "medications": ["string"]
                }},
                "pregnancy_specific": {{
                    "trimester_indicators": "string" or null,
                    "risk_factors": ["string"],
                    "fetal_activity": "string" or null,
                    "emotional_state": "string" or null
                }}
            }}

            If no relevant data is found, return empty arrays or null values for the respective fields.
            """
        
        
        # Call the LLM
        llm_response = Settings.llm.complete(prompt)
        print(f"Raw LLM response: {llm_response.text[:200]}...")
        
        # Parse and clean response
        cleaned_response = llm_response.text.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        print(f"Cleaned response: {cleaned_response}...")
        
        # Parse JSON
        try:
            analytics_data = json.loads(cleaned_response)
            
            # REMOVED THE VALIDATION FUNCTION - Using data directly as returned by LLM
            
            # Store in database
            analytics_id = str(uuid.uuid4())
            word_count = len(message.split())
            medical_data_json = json.dumps(analytics_data.get("medical_data", {}))
            pregnancy_specific_json = json.dumps(analytics_data.get("pregnancy_specific", {}))
            emotional_state = analytics_data.get("pregnancy_specific", {}).get("emotional_state")
            
            db = SessionLocal()
            db_analytics = SessionAnalytics(
                id=analytics_id,
                session_id=session_id,
                timestamp=datetime.fromisoformat(timestamp),
                message_text=message,
                assistant_response=response,
                sentiment=analytics_data.get("sentiment", "neutral"),
                urgency=analytics_data.get("urgency", "low"),
                intent=analytics_data.get("intent", ""),
                topic=analytics_data.get("topic", ""),
                keywords=json.dumps(analytics_data.get("keywords", [])),
                word_count=word_count,
                medical_data=medical_data_json,
                pregnancy_specific=pregnancy_specific_json,
                emotional_state=emotional_state,
                session_duration=0,
                response_time=0
            )
            
            db.add(db_analytics)
            db.commit()
            db.refresh(db_analytics)
            db.close()
            
            print(f"Analytics saved for session {session_id}")
            
            return {
                "status": "success",
                "analytics_id": analytics_id,
                "data": analytics_data
            }
            
        except json.JSONDecodeError as json_err:
            print(f"JSON parsing error: {str(json_err)}")
            analytics_id = str(uuid.uuid4())
            word_count = len(message.split())
            db = SessionLocal()
            db_analytics = SessionAnalytics(
                id=analytics_id,
                session_id=session_id,
                timestamp=datetime.fromisoformat(timestamp),
                message_text=message,
                assistant_response=response,
                sentiment="neutral",
                urgency="low",
                intent="unknown",
                topic="general",
                keywords=json.dumps([]),
                word_count=word_count,
                medical_data=json.dumps({}),
                pregnancy_specific=json.dumps({}),
                emotional_state=None,
                session_duration=0,
                response_time=0
            )
            db.add(db_analytics)
            db.commit()
            db.refresh(db_analytics)
            db.close()
            
            return {
                "status": "partial_success",
                "message": f"Saved with default values due to LLM response parsing error: {str(json_err)}",
                "analytics_id": analytics_id,
                "raw_response": llm_response.text
            }
            
    except Exception as e:
        print(f"Error in analyze-message endpoint: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to analyze message: {str(e)}"
        }
    
@app.get("/api/export-session-analytics/{session_id}")
async def export_session_analytics(session_id: str):
    """
    Export all analytics data for a given session to an Excel file with pregnancy-specific data.
    """
    try:
        print(f"Exporting pregnancy analytics for session: {session_id}")
        
        db = SessionLocal()
        analytics_records = db.query(SessionAnalytics).filter(
            SessionAnalytics.session_id == session_id
        ).order_by(SessionAnalytics.timestamp).all()
        
        if not analytics_records:
            return JSONResponse(
                status_code=404,
                content={"message": f"No analytics found for session {session_id}"}
            )
        
        # Create a pandas DataFrame for basic data
        basic_data = []
        
        # Create separate DataFrames for medical data and pregnancy-specific data
        medical_data_rows = []
        pregnancy_data_rows = []
        
        for record in analytics_records:
            # Parse keywords if it's a JSON string
            try:
                keywords = json.loads(record.keywords) if record.keywords else []
                keywords_str = ", ".join(keywords)
            except:
                keywords_str = record.keywords or ""
            
            # Basic data for main sheet    
            basic_data.append({
                "timestamp": record.timestamp.isoformat() if record.timestamp else "",
                "message": record.message_text or "",
                "response": record.assistant_response or "",
                "sentiment": record.sentiment or "",
                "urgency": record.urgency or "",
                "intent": record.intent or "",
                "topic": record.topic or "",
                "keywords": keywords_str,
                "word_count": record.word_count or 0,
                "emotional_state": record.emotional_state or ""
            })
            
            # Parse JSON strings for medical_data and pregnancy_specific
            medical_data_dict = {}
            pregnancy_specific_dict = {}
            
            try:
                if record.medical_data and record.medical_data.strip():
                    medical_data_dict = json.loads(record.medical_data)
            except json.JSONDecodeError:
                print(f"Error parsing medical_data JSON for record ID: {record.id}")
            
            try:
                if record.pregnancy_specific and record.pregnancy_specific.strip():
                    pregnancy_specific_dict = json.loads(record.pregnancy_specific)
            except json.JSONDecodeError:
                print(f"Error parsing pregnancy_specific JSON for record ID: {record.id}")
            
            # Process medical data if available
            if medical_data_dict:
                # Dates processing
                if medical_data_dict.get("dates"):
                    for date_type, date_value in medical_data_dict["dates"].items():
                        medical_data_rows.append({
                            "timestamp": record.timestamp.isoformat() if record.timestamp else "",
                            "type": "date",
                            "subtype": date_type,
                            "value": date_value,
                            "details": "",
                            "message_reference": record.message_text[:50] + "..." if record.message_text else ""
                        })
                
                # Symptoms processing
                if medical_data_dict.get("symptoms"):
                    for symptom in medical_data_dict["symptoms"]:
                        medical_data_rows.append({
                            "timestamp": record.timestamp.isoformat() if record.timestamp else "",
                            "type": "symptom",
                            "subtype": symptom.get("name", ""),
                            "value": symptom.get("severity", ""),
                            "details": json.dumps(symptom),
                            "message_reference": record.message_text[:50] + "..." if record.message_text else ""
                        })
                
                # Measurements processing
                if medical_data_dict.get("measurements"):
                    for measure_type, measure_value in medical_data_dict["measurements"].items():
                        medical_data_rows.append({
                            "timestamp": record.timestamp.isoformat() if record.timestamp else "",
                            "type": "measurement",
                            "subtype": measure_type,
                            "value": str(measure_value),
                            "details": "",
                            "message_reference": record.message_text[:50] + "..." if record.message_text else ""
                        })
                
                # Medications processing
                if medical_data_dict.get("medications"):
                    for medication in medical_data_dict["medications"]:
                        medical_data_rows.append({
                            "timestamp": record.timestamp.isoformat() if record.timestamp else "",
                            "type": "medication",
                            "subtype": medication,
                            "value": "",
                            "details": "",
                            "message_reference": record.message_text[:50] + "..." if record.message_text else ""
                        })
            
            # Process pregnancy-specific data if available
            if pregnancy_specific_dict:
                # Trimester indicators
                if pregnancy_specific_dict.get("trimester_indicators"):
                    pregnancy_data_rows.append({
                        "timestamp": record.timestamp.isoformat() if record.timestamp else "",
                        "type": "trimester",
                        "value": pregnancy_specific_dict["trimester_indicators"],
                        "details": "",
                        "message_reference": record.message_text[:50] + "..." if record.message_text else ""
                    })
                
                # Risk factors
                if pregnancy_specific_dict.get("risk_factors"):
                    for risk in pregnancy_specific_dict["risk_factors"]:
                        pregnancy_data_rows.append({
                            "timestamp": record.timestamp.isoformat() if record.timestamp else "",
                            "type": "risk_factor",
                            "value": risk,
                            "details": "",
                            "message_reference": record.message_text[:50] + "..." if record.message_text else ""
                        })
                
                # Fetal activity
                if pregnancy_specific_dict.get("fetal_activity"):
                    pregnancy_data_rows.append({
                        "timestamp": record.timestamp.isoformat() if record.timestamp else "",
                        "type": "fetal_activity",
                        "value": pregnancy_specific_dict["fetal_activity"],
                        "details": "",
                        "message_reference": record.message_text[:50] + "..." if record.message_text else ""
                    })
        
        # Create DataFrames
        df_basic = pd.DataFrame(basic_data)
        df_medical = pd.DataFrame(medical_data_rows) if medical_data_rows else pd.DataFrame()
        df_pregnancy = pd.DataFrame(pregnancy_data_rows) if pregnancy_data_rows else pd.DataFrame()
        
        # Create Excel file with multiple sheets
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_basic.to_excel(writer, sheet_name="Conversation Analytics", index=False)
            
            if not df_medical.empty:
                df_medical.to_excel(writer, sheet_name="Medical Data", index=False)
            
            if not df_pregnancy.empty:
                df_pregnancy.to_excel(writer, sheet_name="Pregnancy Data", index=False)
        
        # Save the Excel file to disk for backup
        output.seek(0)
        filename = f"pregnancy_analytics_{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # Make sure the directory exists
        os.makedirs("./session_analytics", exist_ok=True)
        filepath = f"./session_analytics/{filename}"
        
        with open(filepath, "wb") as f:
            f.write(output.getvalue())
            
        print(f"Enhanced pregnancy analytics Excel file saved to {filepath}")
        
        # Return the file as a downloadable attachment
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
        
    except Exception as e:
        print(f"Error exporting pregnancy analytics: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to export pregnancy analytics: {str(e)}"}
        )
    
@app.post("/api/analyze-session")
async def analyze_session(request: dict):
    """
    Analyze a complete session to extract patient information and update database tables.
    
    This endpoint processes all messages in a session to extract:
    - Patient details (name, phone number, date of birth, etc.)
    - Medical data (symptoms, medications, allergies, etc.)
    - Update the appropriate database tables
    
    Args:
        request (dict): Contains sessionId and other parameters
        
    Returns:
        dict: Extracted information and update status
    """
    eastern = pytz.timezone('America/New_York')
    time = datetime.now(eastern)
    current_time = time.date()
    try:
        session_id = request.get("sessionId")
        patient_id = request.get("patientId")
        previous_session_summary = request.get("previousSessionSummary")  # New parameter
        previous_session_date = request.get("previousSessionDate")
        if not session_id:
            return {
                "status": "error",
                "message": "sessionId is required"
            }
            
        print(f"[API] Analyzing session {session_id} for patient data extraction")
        
        # Get database connection
        db = SessionLocal()
        
        # Fetch all analytics for this session
        analytics = db.query(SessionAnalytics).filter(
            SessionAnalytics.session_id == session_id
        ).order_by(SessionAnalytics.timestamp).all()
        
        if not analytics:
            print(f"[API] No session analytics found for session {session_id}")
            db.close()
            return {
                "status": "error",
                "message": f"No analytics found for session {session_id}"
            }
        
        # Prepare conversation history for the LLM
        conversation = []
        for entry in analytics:
            if entry.message_text:
                conversation.append({"role": "user", "content": entry.message_text})
            if entry.assistant_response:
                conversation.append({"role": "assistant", "content": entry.assistant_response})
        
        # If we somehow don't have any valid messages, exit
        if not conversation:
            print(f"[API] No valid messages found for session {session_id}")
            db.close()
            return {
                "status": "error",
                "message": f"No valid messages found for session {session_id}"
            }
        
        conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
        print(f"[API] Conversation sent to LLM:\n{conversation_text}")

        previous_summary_section = ""
        if previous_session_summary:
            previous_session_date = request.get("previousSessionDate", "unknown timestamp")
            previous_summary_section = f"""
            Previous Session Summary (for session_summary only):
            On {previous_session_date}, the patient reported: {previous_session_summary}
            
            For the session_summary:
            - Start with: "On {previous_session_date}, the patient reported [key details from previous summary, including diagnoses and significant findings]. In the current session on {time.strftime('%Y-%m-%d %H:%M:%S')}, the patient reported [current session findings]."
            - Include all current session medical information (pregnancy status, LMP date, symptoms, allergies, medications).
            - Use proper medical terminology and ensure clinical significance.
            - Do NOT use the previous session summary to populate patient_details, medical_info, or any other fields unless explicitly stated in the current conversation.
            """

        # Create a comprehensive prompt to extract patient information
        prompt = f"""
        You are tasked with extracting structured patient information from the following conversation between a patient and a healthcare AI assistant. 
        
        Conversation History:
        {conversation_text}
        

        {previous_summary_section}

        Based on this conversation, extract the following information:
        
        1. Patient Details:
           - Name (first name, last name)
           - Phone number
           - Date of birth
           - Gender
           - Email address
           - Address or location

        2. Medical Information:
           - Medical conditions/diagnoses mentioned (including pregnancy status)
           - Symptoms reported
           - Medications mentioned (with dosages if available)
           - Allergies mentioned (For example Messages include any mention of 'allergies' or symptoms like 'rashes,' 'itching,' or 'hives' that suggest an allergic reaction, even if no specific allergen is stated)
           - Vital signs or health measurements
           - Important pregnancy-related information:
             * Last menstrual period date
             * Positive pregnancy test status
             * Due date if mentioned
             * Gestational age if mentioned

        3. For the session_summary:
            - Create a concise but comprehensive summary of the medical conversation
            - ALWAYS include ALL identified medical information from the extraction including:
                * Pregnancy status if identified
                * Last menstrual period date if available
                * Any symptoms reported (severity and duration if mentioned)
                * Any specific allergies mentioned
                * Any medications discussed
                - Focus on clinical significance and use proper medical terminology
                - Highlight urgent concerns or recommendations
                - Format the summary as a structured clinical note that includes all key medical data extracted
            IMP For the session_summary:
                - Generate a concise, bullet-point summary of all medical information from the current session and all previous sessions, consolidating repetitive information.
                - Use the following structure:
                - **Patient**: [Name, if available]
                - **Pregnancy Status**: [Confirmed pregnant/not pregnant/unknown, with date of confirmation if applicable]
                - **Last Menstrual Period (LMP)**: [Most recent LMP date; note any conflicting dates for review]
                - **Gestational Age**: [Calculated based on the most recent LMP date, in weeks and days; note if ultrasound confirmation is pending]
                - **Symptoms**: [List all unique symptoms reported across sessions, with severity and duration if available; combine duplicates]
                - **Medications**: [List all medications discussed, with dosages/frequency if available; note if advised to consult provider]
                - **Allergies**: [List all allergies reported; specify 'None reported' if none mentioned]
                - **Recommendations**: [List key recommendations or urgent actions, e.g., contact provider, visit ER]
                - Deduplicate repetitive information (e.g., combine multiple pregnancy test confirmations into one entry).
                - If previous_session_summary is provided, extract key medical details and integrate them into the bullet points without repeating the full narrative.
                - If conflicting data (e.g., multiple LMP dates) exists, use the most recent date and note the conflict in parentheses.
                - Use proper medical terminology and prioritize clinical significance.
                - Keep the summary concise (aim for 5-10 bullet points total).
               
        Return the extracted information in JSON format:
        {{
            "patient_details": {{
                "first_name": "string",
                "last_name": "string",
                "phone": "string",
                "date_of_birth": "YYYY-MM-DD",
                "gender": "string",
                "email": "string",
                "address": "string"
            }},
            "medical_info": {{
                "conditions": [
                    {{
                        "condition": "string", 
                        "status": "active/resolved/unknown",
                        "onset_date": "YYYY-MM-DD",
                        "notes": "string"
                    }}
                ],
                "symptoms": [
                    {{"symptom": "string", "severity": "mild/moderate/severe/unknown"}}
                ],
                "medications": [
                    {{"name": "string", "dosage": "string", "frequency": "string", "route": "string"}}
                ],
                "allergies": [
                    {{"allergen": "string", "reaction": "string", "severity": "string"}}
                ],
                "vital_signs": {{
                    "temperature": "number",
                    "heart_rate": "number",
                    "blood_pressure_systolic": "number",
                    "blood_pressure_diastolic": "number",
                    "respiratory_rate": "number",
                    "oxygen_saturation": "number",
                    "weight": "number"
                }},
                "pregnancy_info": {{
                    "is_pregnant": "yes/no/unknown",
                    "last_menstrual_period": "YYYY-MM-DD",
                    "due_date": "YYYY-MM-DD",
                    "gestational_age_weeks": "number"
                }},
                "important_dates": [
                    {{"description": "string", "date": "YYYY-MM-DD"}}
                ]
            }},
            "session_summary": "string",
            "confidence_scores": {{
                "name": 0-100,
                "phone": 0-100,
                "dob": 0-100,
                "gender": 0-100,
                "conditions": 0-100,
                "allergies":0-100,
                "symptoms": 0-100,  
                "medications": 0-100,
                "pregnancy": 0-100
            }}
        }}
        Instructions:
        For each field, only include information explicitly stated in the conversation. For missing fields, leave them null or empty.
        For each major category (name, phone, etc.), include a confidence score from 0-100 indicating how certain you are of the extraction.
        Use the standard format provided for dates (YYYY-MM-DD).
        Phone numbers should be in a standardized format (e.g., "+1234567890" or "123-456-7890").
        For allergies:
            - Include any explicit mentions of 'allergies,' 'allergic,' or related terms (e.g., 'I have allergies,' 'I am allergic to X').
            - Identify symptoms or reactions suggestive of allergies based on medical knowledge (e.g., skin reactions like rashes, respiratory issues like wheezing, or swelling, especially if linked to triggers like foods, environmental factors, or medications).
            - If the patient mentions 'allergies' without specifying an allergen, set 'allergen' to 'Unknown' and describe the reaction as 'Patient reported allergies' or the associated symptom (e.g., 'rash' if mentioned).
        For the session_summary:
            - Create a concise (2-3 sentence) summary of the medical conversation
            - Focus on clinical significance and use proper medical terminology
            - Highlight symptoms, concerns, diagnoses, and recommended actions
                - ALWAYS include ALL identified medical information from the extraction including:
                * Pregnancy status if identified
                * Last menstrual period date if available
                * Any symptoms reported (severity and duration if mentioned)
                * Any specific allergies mentioned
                * Any medications discussed
                - Focus on clinical significance and use proper medical terminology
                - Highlight urgent concerns or recommendations
                - Format the summary as a structured clinical note that includes all key medical data extracted


        """
        
        # Get LLM response
        print(f"[API] Sending prompt to LLM for patient data extraction")
        llm_response = Settings.llm.complete(prompt)
        
        print(f"[API] Raw LLM response:\n{llm_response.text}")
        
        # Parse the response
        clean_response = llm_response.text.strip()
        
        # Clean up response if it contains markdown code blocks
        if "```json" in clean_response:
            clean_response = clean_response.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_response:
            clean_response = clean_response.split("```")[1].split("```")[0].strip()
            
        print(f"[API] Cleaned LLM response:\n{clean_response}")
            
        # Handle potential JSON formatting issues
        try:
            extracted_data = json.loads(clean_response)
        except json.JSONDecodeError as e:
            print(f"[API] JSON parse error: {str(e)}, attempting cleanup")
            # Try to fix common JSON issues
            clean_response = clean_response.replace("'", '"')  # Replace single quotes with double quotes
            clean_response = re.sub(r',\s*}', '}', clean_response)  # Remove trailing commas
            
            print(f"[API] Response after JSON cleanup attempt:\n{clean_response}")
            
            try:
                extracted_data = json.loads(clean_response)
            except json.JSONDecodeError:
                print(f"[API] Failed to parse LLM response as JSON even after cleanup")
                db.close()
                return {
                    "status": "error",
                    "message": "Failed to parse extracted data from LLM response",
                    "raw_response": llm_response.text
                }
        
        print(f"[API] Parsed extracted data:\n{json.dumps(extracted_data, indent=2)}")
        
        # Process the extracted data
        patient_details = extracted_data.get("patient_details", {})
        medical_info = extracted_data.get("medical_info", {})
        confidence_scores = extracted_data.get("confidence_scores", {})
        session_summary = extracted_data.get("session_summary", "No summary generated.") # Add this line

        print(f"[API] Confidence scores:\n{json.dumps(confidence_scores, indent=2)}")
        
        # Initialize a dictionary to track all updates
        updates_made = {
            "patient_details_updated": False,
            "medical_conditions_added": 0,
            "medications_added": 0,
            "allergies_added": 0,
            "updated_fields": []
        }
        
        # Only proceed with updates if we have a patient ID
        if patient_id:
            # Update patient record if data is available with reasonable confidence
            patient_record = db.query(Patient).filter(Patient.id == patient_id).first()
            
            if patient_record:
                print(f"[API] Found patient record: {patient_record.id}")
                
                # Update patient details with confidence threshold
                fields_updated = 0
                
                # Allow updating first name regardless of whether it's already set
                if patient_details.get("first_name") and confidence_scores.get("name", 0) >= 75:
                    patient_record.first_name = patient_details["first_name"]
                    fields_updated += 1
                    updates_made["updated_fields"].append("first_name")
                    print(f"[API] Updating patient first_name: {patient_details['first_name']}")
                
                # For other fields, only update if they're empty
                if patient_details.get("last_name") and not patient_record.last_name and confidence_scores.get("name", 0) >= 75:
                    patient_record.last_name = patient_details["last_name"]
                    fields_updated += 1
                    updates_made["updated_fields"].append("last_name")
                    print(f"[API] Updating patient last_name: {patient_details['last_name']}")
                
                if patient_details.get("phone") and not patient_record.phone and confidence_scores.get("phone", 0) >= 75:
                    patient_record.phone = patient_details["phone"]
                    fields_updated += 1
                    updates_made["updated_fields"].append("phone")
                    print(f"[API] Updating patient phone: {patient_details['phone']}")
                
                if patient_details.get("date_of_birth") and not patient_record.date_of_birth and confidence_scores.get("dob", 0) >= 75:
                    patient_record.date_of_birth = patient_details["date_of_birth"]
                    fields_updated += 1
                    updates_made["updated_fields"].append("date_of_birth")
                    print(f"[API] Updating patient date_of_birth: {patient_details['date_of_birth']}")
                
                if patient_details.get("gender") and not patient_record.gender and confidence_scores.get("gender", 0) >= 75:
                    patient_record.gender = patient_details["gender"]
                    fields_updated += 1
                    updates_made["updated_fields"].append("gender")
                    print(f"[API] Updating patient gender: {patient_details['gender']}")
                
                if patient_details.get("email") and not patient_record.email and confidence_scores.get("email", 0) >= 75:
                    patient_record.email = patient_details["email"]
                    fields_updated += 1
                    updates_made["updated_fields"].append("email")
                    print(f"[API] Updating patient email: {patient_details['email']}")
                
                if patient_details.get("address") and not patient_record.address and confidence_scores.get("address", 0) >= 75:
                    patient_record.address = patient_details["address"]
                    fields_updated += 1
                    updates_made["updated_fields"].append("address")
                    print(f"[API] Updating patient address: {patient_details['address']}")
                
                # Only update the patient record if fields were changed
                if fields_updated > 0:
                    patient_record.updated_at = datetime.utcnow()
                    updates_made["patient_details_updated"] = True
                    print(f"[API] Updated {fields_updated} patient detail fields")
                
                # Check for pregnancy info and merge with existing conditions to avoid duplicates
                pregnancy_info = medical_info.get("pregnancy_info", {})
                lmp_date = pregnancy_info.get("last_menstrual_period")
                is_pregnant = pregnancy_info.get("is_pregnant") == "yes"
                
                # Get all existing pregnancy and LMP conditions for this patient
                existing_pregnancies = db.query(MedicalHistory).filter(
                    MedicalHistory.patient_id == patient_id,
                    MedicalHistory.condition.ilike('%pregnancy%')
                ).all()
                
                existing_lmps = db.query(MedicalHistory).filter(
                    MedicalHistory.patient_id == patient_id,
                    MedicalHistory.condition.ilike('%menstrual%')
                ).all()
                
                existing_gestational_age = db.query(MedicalHistory).filter(
                    MedicalHistory.patient_id == patient_id,
                    MedicalHistory.condition.ilike('%gestational age%')
                ).all()
                
                print(f"[API] Found {len(existing_pregnancies)} existing pregnancy records, {len(existing_lmps)} LMP records, and {len(existing_gestational_age)} gestational age records")
                
                # Calculate gestational age if we have LMP date
                gestational_age_weeks = None
                if lmp_date:
                    try:
                        # Parse LMP date
                        eastern = pytz.timezone('America/New_York')
                        current_time = datetime.now(eastern)
                        today = current_time.date()

                        lmp_date_obj = datetime.strptime(lmp_date, '%Y-%m-%d').date()
                        # Calculate days since LMP
                        # today = datetime.now().date()
                        days_since_lmp = (today - lmp_date_obj).days
                        # Convert to weeks
                        gestational_age_weeks = days_since_lmp / 7
                        print(f"[API] Calculated gestational age: {gestational_age_weeks:.1f} weeks from LMP on {lmp_date}")
                    except Exception as e:
                        print(f"[API] Error calculating gestational age: {str(e)}")
                
                # Check if we have LMP and/or pregnancy info to update
                pregnancy_updating = False
                
                if is_pregnant or lmp_date:
                    # Format notes string
                    notes = "Pregnancy"
                    if lmp_date:
                        notes += f" with LMP date: {lmp_date}"
                    if is_pregnant:
                        notes += ". Positive pregnancy test confirmed."
                    
                    # Case 1: We have existing pregnancy records
                    if existing_pregnancies:
                        # Update most recent one
                        existing_pregnancy = existing_pregnancies[0]
                        print(f"[API] Updating existing pregnancy record: {existing_pregnancy.id}")
                        if lmp_date and not existing_pregnancy.onset_date:
                            existing_pregnancy.onset_date = current_time
                            pregnancy_updating = True
                        
                        # Update notes if empty
                        if not existing_pregnancy.notes:
                            existing_pregnancy.notes = notes
                            pregnancy_updating = True
                        elif "LMP date" not in existing_pregnancy.notes and lmp_date:
                            existing_pregnancy.notes += f" LMP date: {lmp_date}"
                            pregnancy_updating = True
                        
                        if pregnancy_updating:
                            existing_pregnancy.updated_at = datetime.utcnow()
                            updates_made["updated_fields"].append("pregnancy")
                            print(f"[API] Updated existing pregnancy record with LMP: {lmp_date}")
                    
                    # Case 2: No existing pregnancy records but we have info
                    else:
                        # Create new pregnancy record
                        new_pregnancy = MedicalHistory(
                            id=str(uuid.uuid4()),
                            patient_id=patient_id,
                            condition="Pregnancy",
                            status="Active",
                            onset_date=current_time,
                            notes=notes,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(new_pregnancy)
                        updates_made["medical_conditions_added"] += 1
                        print(f"[API] Added new pregnancy record with LMP: {lmp_date}")
                    
                    # Case 3: We have explicit LMP date but no dedicated LMP record
                    if lmp_date and not existing_lmps:
                        # Add a dedicated LMP record
                        lmp_record = MedicalHistory(
                            id=str(uuid.uuid4()),
                            patient_id=patient_id,
                            condition="Last Menstrual Period",
                            status="Completed",
                            onset_date=current_time,
                            notes=f"Last menstrual period started on {lmp_date}",
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(lmp_record)
                        updates_made["medical_conditions_added"] += 1
                        print(f"[API] Added dedicated LMP record: {lmp_date}")
                    
                    # Case 4: Add or update Gestational Age as a separate condition
                    if gestational_age_weeks:
                        # Format the gestational age for display
                        formatted_ga = f"{int(gestational_age_weeks)} weeks {int((gestational_age_weeks % 1) * 7)} days"
                        
                        if existing_gestational_age:
                            # Update existing gestational age record
                            ga_record = existing_gestational_age[0]
                            ga_record.status = "Active"
                            ga_record.onset_date = current_time
                            ga_record.notes = f"Calculated based on LMP date: {lmp_date}. Current gestational age: {formatted_ga}"
                            ga_record.updated_at = datetime.utcnow()
                            db.add(ga_record)  # Add this line to ensure the update is staged
                            updates_made["updated_fields"].append("gestational_age")
                            print(f"[API] Updated gestational age record: {formatted_ga}")
                        else:
                            # Create new gestational age record
                            ga_record = MedicalHistory(
                                id=str(uuid.uuid4()),
                                patient_id=patient_id,
                                condition=f"Gestational Age",
                                status="Active",
                                onset_date=current_time,
                                notes=f"Calculated based on LMP date: {lmp_date}. Current gestational age: {formatted_ga}",
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                            db.add(ga_record)
                            updates_made["medical_conditions_added"] += 1
                            print(f"[API] Added gestational age record: {formatted_ga}")
                
                # Process regular medical conditions
                if medical_info.get("conditions") and confidence_scores.get("conditions", 0) >= 70:
                    for condition_data in medical_info["conditions"]:
                        condition_name = condition_data.get("condition")
                        condition_status = condition_data.get("status", "active")
                        onset_date = condition_data.get("onset_date")
                        notes = condition_data.get("notes", "")
                        
                        # Skip pregnancy conditions as they're handled separately
                        if condition_name and "pregnancy" not in condition_name.lower():
                            # Check if this condition is already recorded
                            existing_condition = db.query(MedicalHistory).filter(
                                MedicalHistory.patient_id == patient_id,
                                func.lower(MedicalHistory.condition) == func.lower(condition_name)
                            ).first()
                            
                            if not existing_condition:
                                # Add new condition
                                new_condition = MedicalHistory(
                                    id=str(uuid.uuid4()),
                                    patient_id=patient_id,
                                    condition=condition_name,
                                    status=condition_status,
                                    onset_date=current_time,
                                    notes=notes,
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
                                )
                                db.add(new_condition)
                                updates_made["medical_conditions_added"] += 1
                                print(f"[API] Added medical condition: {condition_name} (status: {condition_status})")
                
                # Also check for LMP in important dates if not found in pregnancy info
                if not lmp_date and medical_info.get("important_dates"):
                    for date_entry in medical_info["important_dates"]:
                        description = date_entry.get("description", "").lower()
                        date = date_entry.get("date")
                        
                        if date and ("menstrual" in description or "lmp" in description):
                            lmp_date = date  # Set this for possible gestational age calculation
                            
                            # Add this as a LMP if not already added
                            if not existing_lmps:
                                lmp_record = MedicalHistory(
                                    id=str(uuid.uuid4()),
                                    patient_id=patient_id,
                                    condition="Last Menstrual Period",
                                    status="Completed",
                                    onset_date=current_time,
                                    notes=f"Last menstrual period started on {date}",
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
                                )
                                db.add(lmp_record)
                                updates_made["medical_conditions_added"] += 1
                                print(f"[API] Added LMP from important dates: {date}")
                                
                                # Calculate gestational age for this LMP date
                                try:
                                    # Parse LMP date
                                    eastern = pytz.timezone('America/New_York')
                                    current_time = datetime.now(eastern)
                                    today = current_time.date()
                                    lmp_date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                                    # Calculate days since LMP
                                    # today = datetime.now().date()
                                    days_since_lmp = (today - lmp_date_obj).days
                                    # Convert to weeks
                                    gestational_age_weeks = days_since_lmp / 7
                                    formatted_ga = f"{int(gestational_age_weeks)} weeks {int((gestational_age_weeks % 1) * 7)} days"
                                    
                                    # Add gestational age record
                                    if not existing_gestational_age:
                                        ga_record = MedicalHistory(
                                            id=str(uuid.uuid4()),
                                            patient_id=patient_id,
                                            condition=f"Gestational Age",
                                            status="Active",
                                            onset_date=current_time,
                                            notes=f"Calculated based on LMP date: {date}. Current gestational age: {formatted_ga}",
                                            created_at=datetime.utcnow(),
                                            updated_at=datetime.utcnow()
                                        )
                                        db.add(ga_record)
                                        updates_made["medical_conditions_added"] += 1
                                        print(f"[API] Added gestational age from important dates LMP: {formatted_ga}")
                                except Exception as e:
                                    print(f"[API] Error calculating gestational age from important dates: {str(e)}")
                                
                                # Also update existing pregnancy record if we have one
                                if existing_pregnancies and not existing_pregnancies[0].onset_date:
                                    existing_pregnancies[0].onset_date = current_time
                                    if not existing_pregnancies[0].notes:
                                        existing_pregnancies[0].notes = f"Pregnancy with LMP date: {date}"
                                    elif "LMP date" not in existing_pregnancies[0].notes:
                                        existing_pregnancies[0].notes += f" LMP date: {date}"
                                    existing_pregnancies[0].updated_at = datetime.utcnow()
                                    updates_made["updated_fields"].append("pregnancy")
                                    print(f"[API] Updated existing pregnancy with LMP from important dates: {date}")
                
                # Add medications if not already present
                if medical_info.get("medications") and confidence_scores.get("medications", 0) >= 70:
                    for medication_data in medical_info["medications"]:
                        med_name = medication_data.get("name")
                        med_dosage = medication_data.get("dosage", "")
                        med_frequency = medication_data.get("frequency", "")
                        med_route = medication_data.get("route", "")
                        
                        if med_name:
                            # Check if this medication is already recorded
                            existing_medication = db.query(Medication).filter(
                                Medication.patient_id == patient_id,
                                func.lower(Medication.name) == func.lower(med_name)
                            ).first()
                            
                            if not existing_medication:
                                # Add new medication
                                new_medication = Medication(
                                    id=str(uuid.uuid4()),
                                    patient_id=patient_id,
                                    name=med_name,
                                    dosage=med_dosage,
                                    frequency=med_frequency,
                                    route=med_route,
                                    active=True,
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
                                )
                                db.add(new_medication)
                                updates_made["medications_added"] += 1
                                print(f"[API] Added medication: {med_name}")
                
                # Process symptoms
                # Process symptoms
                if medical_info.get("symptoms") and confidence_scores.get("symptoms", confidence_scores.get("conditions", 0)) >= 50:
                    for symptom_data in medical_info["symptoms"]:
                        symptom_name = symptom_data.get("symptom")
                        symptom_severity = symptom_data.get("severity", "unknown")
                        
                        if symptom_name:
                            # Check if this symptom is already recorded
                            existing_symptom = db.query(MedicalHistory).filter(
                                MedicalHistory.patient_id == patient_id,
                                func.lower(MedicalHistory.condition) == func.lower(symptom_name)
                            ).first()
                            
                            if not existing_symptom:
                                # Add new symptom as a medical history condition
                                new_symptom = MedicalHistory(
                                    id=str(uuid.uuid4()),
                                    patient_id=patient_id,
                                    condition = symptom_name,
                                    status="Active",
                                    onset_date=datetime.utcnow().date(),
                                    notes=f"Severity: {symptom_severity}. Reported during chat session.",
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
                                )
                                db.add(new_symptom)
                                updates_made["medical_conditions_added"] += 1
                                print(f"[API] Added symptom: {symptom_name} (severity: {symptom_severity})")
                                
                # Add allergies if not already present
                # Process allergies
                if medical_info.get("allergies") and confidence_scores.get("allergies", 0) >= 70:
                    for allergy_data in medical_info["allergies"]:
                        allergen_name = allergy_data.get("allergen")
                        reaction = allergy_data.get("reaction", "")
                        severity = allergy_data.get("severity", "")
                        
                        # Only proceed if we have a valid allergen name
                        if allergen_name and allergen_name != "null":
                            # Check if this allergy is already recorded
                            existing_allergy = db.query(Allergy).filter(
                                Allergy.patient_id == patient_id,
                                func.lower(Allergy.allergen) == func.lower(allergen_name)
                            ).first()
                            
                            if not existing_allergy:
                                # Add new allergy
                                new_allergy = Allergy(
                                    id=str(uuid.uuid4()),
                                    patient_id=patient_id,
                                    allergen=allergen_name,
                                    reaction=reaction,
                                    severity=severity,
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
                                )
                                db.add(new_allergy)
                                updates_made["allergies_added"] += 1
                                print(f"[API] Added allergy: {allergen_name}")
                        else:
                            # If allergen name is not specified but allergies were mentioned
                            # Create a general allergy entry
                            if not db.query(Allergy).filter(
                                Allergy.patient_id == patient_id,
                                Allergy.allergen == "Unknown allergies"
                            ).first():
                                new_allergy = Allergy(
                                    id=str(uuid.uuid4()),
                                    patient_id=patient_id,
                                    allergen="Unknown allergies",
                                    reaction="Patient mentioned having allergies but did not specify",
                                    severity="Unknown",
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
                                )
                                db.add(new_allergy)
                                updates_made["allergies_added"] += 1
                                print(f"[API] Added general allergy note")
                # Commit all changes to the database
                db.commit()
                
                print(f"[API] Database updates summary:\n{json.dumps(updates_made, indent=2)}")
            else:
                print(f"[API] Warning: Patient ID {patient_id} not found in database")
        
        db.close()
        
        # Return the extracted data and update status
        return {
            "status": "success",
            "session_id": session_id,
            "extracted_data": extracted_data,
            "updates_made": updates_made,
            "session_summary": session_summary, 
            "message": "Session analyzed successfully"  
        }
        
    except Exception as e:
        print(f"[API] Error analyzing session: {str(e)}")
        traceback_str = traceback.format_exc()
        print(f"[API] Traceback: {traceback_str}")
        return {
            "status": "error",
            "message": f"Failed to analyze session: {str(e)}",
            "error_details": traceback_str
        }

# Additional endpoints for session analytics

@app.get("/api/session-analytics")
async def get_session_analytics_list(db: Session = Depends(get_db)):
    """
    Get a list of all sessions with analytics data.
    """
    try:
        print('FUNCTION FOUND [SESSION ANALYTICS]')
        # Get unique session IDs with counts
        session_stats = db.query(
            SessionAnalytics.session_id,
            func.count(SessionAnalytics.id).label("message_count"),
            func.min(SessionAnalytics.timestamp).label("start_time"),
            func.max(SessionAnalytics.timestamp).label("end_time")
        ).group_by(SessionAnalytics.session_id).all()
        
        results = []
        for stat in session_stats:
            # Calculate duration
            start_time = stat.start_time
            end_time = stat.end_time
            duration_seconds = (end_time - start_time).total_seconds()
            
            # Get sentiment distribution
            sentiment_counts = db.query(
                SessionAnalytics.sentiment,
                func.count(SessionAnalytics.id).label("count")
            ).filter(
                SessionAnalytics.session_id == stat.session_id
            ).group_by(SessionAnalytics.sentiment).all()
            
            sentiment_distribution = {
                item.sentiment: item.count for item in sentiment_counts
            }
            
            # Get the most common topic
            topics = db.query(
                SessionAnalytics.topic,
                func.count(SessionAnalytics.id).label("count")
            ).filter(
                SessionAnalytics.session_id == stat.session_id
            ).group_by(SessionAnalytics.topic).order_by(
                func.count(SessionAnalytics.id).desc()
            ).first()
            
            main_topic = topics.topic if topics else "Unknown"
            
            # Get pregnancy-related information
            pregnancy_data_exists = db.query(SessionAnalytics).filter(
                SessionAnalytics.session_id == stat.session_id,
                SessionAnalytics.pregnancy_specific.isnot(None),
                SessionAnalytics.pregnancy_specific != '{}'
            ).count() > 0
            
            results.append({
                "session_id": stat.session_id,
                "message_count": stat.message_count,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration_seconds,
                "sentiment_distribution": sentiment_distribution,
                "main_topic": main_topic,
                "has_pregnancy_data": pregnancy_data_exists
            })
        
        return {
            "total_sessions": len(results),
            "sessions": results
        }
        
    except Exception as e:
        print(f"Error getting session analytics list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session analytics list: {str(e)}"
        )

@app.get("/api/session-analytics/{session_id}")
async def get_session_analytics(session_id: str, db: Session = Depends(get_db)):
    """
    Get detailed analytics for a specific session.
    """
    print(f"Received request for session_id: {session_id}")

    try:
        # Get all analytics entries for this session
        analytics = db.query(SessionAnalytics).filter(
            SessionAnalytics.session_id == session_id
        ).order_by(SessionAnalytics.timestamp).all()
        
        if not analytics:
            raise HTTPException(
                status_code=404,
                detail=f"No analytics found for session {session_id}"
            )
        
        # Format the data
        messages = []
        
        # For pregnancy summary aggregation
        all_dates = {}
        all_symptoms = []
        all_measurements = {}
        all_medications = set()
        all_risk_factors = set()
        trimester_mentions = {}
        fetal_activity_mentions = []
        
        for entry in analytics:
            # Parse keywords JSON
            try:
                keywords = json.loads(entry.keywords) if entry.keywords else []
            except json.JSONDecodeError:
                keywords = []
            
            # Parse medical_data and pregnancy_specific JSON
            medical_data = {}
            pregnancy_specific = {}
            
            try:
                if entry.medical_data and entry.medical_data.strip():
                    medical_data = json.loads(entry.medical_data)
                    
                    # Aggregate dates for summary
                    if "dates" in medical_data and medical_data["dates"]:
                        for date_type, date_value in medical_data["dates"].items():
                            all_dates[date_type] = date_value
                    
                    # Aggregate symptoms for summary
                    if "symptoms" in medical_data and medical_data["symptoms"]:
                        all_symptoms.extend(medical_data["symptoms"])
                    
                    # Aggregate measurements for summary
                    if "measurements" in medical_data and medical_data["measurements"]:
                        all_measurements.update(medical_data["measurements"])
                    
                    # Aggregate medications for summary
                    if "medications" in medical_data and medical_data["medications"]:
                        all_medications.update(medical_data["medications"])
            except json.JSONDecodeError:
                print(f"Error parsing medical_data for entry ID: {entry.id}")
            
            try:
                if entry.pregnancy_specific and entry.pregnancy_specific.strip():
                    pregnancy_specific = json.loads(entry.pregnancy_specific)
                    
                    # Aggregate trimester mentions
                    if "trimester_indicators" in pregnancy_specific and pregnancy_specific["trimester_indicators"]:
                        trimester = pregnancy_specific["trimester_indicators"]
                        trimester_mentions[trimester] = trimester_mentions.get(trimester, 0) + 1
                    
                    # Aggregate risk factors
                    if "risk_factors" in pregnancy_specific and pregnancy_specific["risk_factors"]:
                        all_risk_factors.update(pregnancy_specific["risk_factors"])
                    
                    # Aggregate fetal activity
                    if "fetal_activity" in pregnancy_specific and pregnancy_specific["fetal_activity"]:
                        fetal_activity_mentions.append(pregnancy_specific["fetal_activity"])
            except json.JSONDecodeError:
                print(f"Error parsing pregnancy_specific for entry ID: {entry.id}")
            
            message_data = {
                "id": entry.id,
                "timestamp": entry.timestamp.isoformat(),
                "message": entry.message_text,
                "response": entry.assistant_response,
                "sentiment": entry.sentiment,
                "urgency": entry.urgency,
                "intent": entry.intent,
                "topic": entry.topic,
                "keywords": keywords,
                "word_count": entry.word_count,
                "session_duration": entry.session_duration,
                "response_time": entry.response_time,
                "medical_data": medical_data,
                "pregnancy_specific": pregnancy_specific,
                "emotional_state": entry.emotional_state
            }
            
            messages.append(message_data)
        
        # Calculate session summary stats
        sentiment_counts = {}
        urgency_counts = {}
        intent_counts = {}
        topic_counts = {}
        all_keywords = []
        total_word_count = 0
        
        for message in messages:
            # Count sentiments
            sentiment = message["sentiment"]
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            
            # Count urgencies
            urgency = message["urgency"]
            urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1
            
            # Count intents
            intent = message["intent"]
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
            
            # Count topics
            topic = message["topic"]
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
            # Collect keywords
            if message["keywords"]:
                all_keywords.extend(message["keywords"])
            
            # Sum word counts
            total_word_count += message["word_count"]
        
        # Get the most common keywords
        keyword_counts = {}
        for keyword in all_keywords:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Calculate duration
        start_time = analytics[0].timestamp
        end_time = analytics[-1].timestamp
        duration_seconds = (end_time - start_time).total_seconds()
        
        # Create pregnancy summary
        current_trimester = None
        trimester_mention_count = 0
        
        if trimester_mentions:
            # Find the most mentioned trimester
            current_trimester = max(trimester_mentions.items(), key=lambda x: x[1])[0]
            trimester_mention_count = trimester_mentions[current_trimester]
        
        # Sort symptoms by severity for the top symptoms
        top_symptoms = []
        if all_symptoms:
            # Create a severity ranking
            severity_rank = {
                "severe": 3,
                "moderate": 2,
                "mild": 1,
                None: 0
            }
            
            # Count symptoms by name and get the highest severity
            symptom_severity = {}
            for symptom in all_symptoms:
                name = symptom.get("name", "")
                severity = symptom.get("severity", "mild")
                
                if name in symptom_severity:
                    # Update with higher severity if found
                    if severity_rank.get(severity, 0) > severity_rank.get(symptom_severity[name], 0):
                        symptom_severity[name] = severity
                else:
                    symptom_severity[name] = severity
            
            # Convert to list and sort by severity
            top_symptoms = [{"name": name, "severity": sev} for name, sev in symptom_severity.items()]
            top_symptoms.sort(key=lambda x: severity_rank.get(x["severity"], 0), reverse=True)
            top_symptoms = top_symptoms[:5]  # Limit to top 5
        
        # Create a pregnancy summary object
        pregnancy_summary = {
            "trimester": current_trimester,
            "trimester_mention_count": trimester_mention_count,
            "top_symptoms": top_symptoms,
            "risk_factors": list(all_risk_factors),
            "key_dates": all_dates,
            "medications": list(all_medications),
            "has_fetal_activity": len(fetal_activity_mentions) > 0
        }
        
        # Return the complete analytics data
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration_seconds,
            "total_word_count": total_word_count,
            "sentiment_distribution": sentiment_counts,
            "urgency_distribution": urgency_counts,
            "intent_distribution": intent_counts,
            "topic_distribution": topic_counts,
            "top_keywords": dict(top_keywords),
            "messages": messages,
            "pregnancy_summary": pregnancy_summary
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error getting session analytics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session analytics: {str(e)}"
        )



# Make sure to add these imports at the top of your Python file if not already present:
# from sqlalchemy import func
# from io import BytesIO
# import pandas as pd

# Add this function to the Python code to register users with Telephone AI
# Add this to the imports section of your main.py file

# Update the register_with_telephone_ai function to use this configuration
# Add this function to your main.py file to register users with Telephone AI
async def register_with_telephone_ai(email, password, name, organization_id=None):

    """
    Register a user with the Telephone AI application.
    
    Args:
        email (str): User's email address
        password (str): User's password
        name (str): User's full name
    
    Returns:
        dict: Response from the Telephone AI API
    """
    try:
        print(f"[INTEGRATION] Registering user {email} with Telephone AI")
        
        # Configure the Telephone AI API endpoint
        telephone_ai_url = "http://localhost:3003/api/auth/register"  # Update with actual server URL
        
        # Prepare the request payload based on Telephone AI's expected format
        payload = {
            "email": email,
            "password": password,
            "name": name,
            "plan": "free",
            "accountType": "private",  # Default to private account type
            "organization_id": organization_id  # Add this line to pass the organization ID

        }
        
        # Make the API request
        headers = {"Content-Type": "application/json"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(telephone_ai_url, json=payload, headers=headers) as response:
                response_data = await response.json()
                
                print(f"[INTEGRATION] Telephone AI response status: {response.status}")
                print(f"[INTEGRATION] Telephone AI response data: {json.dumps(response_data)}")
                
                if response.status >= 400:
                    print(f"[INTEGRATION] Error registering with Telephone AI: {response_data.get('error', 'Unknown error')}")
                    return {
                        "success": False,
                        "error": response_data.get('error', 'Unknown error'),
                        "status": response.status
                    }
                
                # Store the token in local storage for the user to use with Telephone AI
                telephone_ai_token = response_data.get("token")
                telephone_ai_user_id = response_data.get("user", {}).get("id")
                
                # You need to save this token somewhere - either in a cookie, database,
                # or pass it back to the client to store in localStorage
                
                print(f"[INTEGRATION] Successfully registered user with Telephone AI")
                return {
                    "success": True,
                    "telephone_ai_token": telephone_ai_token,
                    "telephone_ai_user_id": telephone_ai_user_id,
                    "data": response_data
                }
    
    except Exception as e:
        print(f"[INTEGRATION] Exception during Telephone AI registration: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Make sure to add this import at the top of the file with other imports
# Main Function
# Initialize Gemma model if using local version
if USE_LOCAL_MODEL:
    # Initialize in background to avoid blocking app startup
    import threading
    # threading.Thread(target=init_gemma_model).start()
    # threading.Thread(target=init_medical_ner_model).start()

try:
    with SessionLocal() as db:
        load_sample_medical_codes(db)
except Exception as e:
    print(f"[SETUP] Error loading sample medical codes: {str(e)}")

if __name__ == "__main__":
    
    print("[MAIN] Starting Professional EHR and MedRAG Analysis System")
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=min(cpu_count() + 1, 8), reload=True)
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=min(cpu_count() + 1, 8)) 
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)

    print("[MAIN] Server shutdown")


