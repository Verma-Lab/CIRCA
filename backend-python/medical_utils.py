from test import universal_extractor
import json
import os
import uuid
import requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import pytz
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
import uvicorn
import nest_asyncio
import pickle
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
from disease_detection import DiseaseDetectionSystem

import concurrent.futures
import re
import time
import hashlib

# Keep all existing imports
from llama_index.core import Document, VectorStoreIndex, SimpleDirectoryReader, StorageContext
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
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()

HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")   # Replace with your actual key
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-VL-32B-Instruct"
HUGGINGFACE_ACCESS_TOKEN = os.environ.get("HUGGINGFACE_ACCESS_TOKEN") 
USE_LOCAL_MODEL = True  # Set to False to use Qwen API instead of local Gemma
LOCAL_MODEL_NAME = "google/gemma-3-4b-it"  # Smaller model that can run locally
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")   # Add your actual API key here
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
credentials_path = "op8imize-58b8c4ee316b.json"  # Replace with your actual path
storage_client = storage.Client.from_service_account_json(credentials_path)
BUCKET_NAME = "persist-ai"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") 

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# API Keys - keep existing configuration
XAI_API_KEY = "your-xai-api-key-here"
OPENAI_API_KEY = "your-openai-api-key-here"
os.environ["XAI_API_KEY"] = XAI_API_KEY
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Setting LLMs - keep existing configuration
llm = Gemini(
    model="models/gemini-1.5-flash",
    api_key=GOOGLE_API_KEY,  
)
openai_llm = OpenAI(model="gpt-3.5-turbo", api_key=OPENAI_API_KEY, logprobs=False, default_headers={})
LLM_MODELS = {
    "Gemini-Pro": llm,
    "Chat Gpt o3-mini": openai_llm,
}

Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
Settings.llm = llm

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
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

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

# Pydantic Models for input validation
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


