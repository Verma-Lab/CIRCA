# CIRCA

[![Demo](https://img.shields.io/badge/Demo-Live-brightgreen)](https://your-demo-url.com)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue)](https://your-github-url.com)

## Overview

CIRCA RAG System Architecture is a comprehensive end-to-end Retrieval-Augmented Generation (RAG) application that delivers AI-driven patient consultations via voice, WhatsApp, and SMS in 27+ languages. The system utilizes the LlamaIndex framework with ChromaDB for vector search, built on a MERN stack for frontend and backend, supported by Python FastAPI microservices and SQL for structured data, and integrated with Firestore and Google Cloud Platform as the core infrastructure. Enables real-time contextual retrieval from vector embeddings to provide critical medical guidance.

# EHR and MedRAG Analysis System Documentation
**Version: 1.0**  
**Last Updated: [Current Date]**

## Table of Contents
1. [Overview](#overview-detailed)
2. [Core Technologies](#core-technologies)
3. [Setup and Configuration](#setup-and-configuration)
4. [Environment Variables](#environment-variables)
5. [Database Setup](#database-setup)
6. [Google Cloud Storage (GCS)](#google-cloud-storage-gcs)
7. [ChromaDB](#chromadb)
8. [LLM Configuration](#llm-configuration)
9. [Application Structure](#application-structure)
10. [FastAPI Application](#fastapi-application)
11. [Database Models](#database-models)
12. [Global Storage](#global-storage)
13. [Key Functionalities and API Endpoints](#key-functionalities-and-api-endpoints)
14. [Authentication](#authentication)
15. [Organizations](#organizations)
16. [Users](#users)
17. [Patients](#patients)
18. [Encounters](#encounters)
19. [Medical History, Family History, Medications, Allergies](#medical-history-family-history-medications-allergies)
20. [Lab Orders and Results](#lab-orders-and-results)
21. [Patient Scans](#patient-scans)
22. [AI-Powered Analysis (General)](#ai-powered-analysis-general)
23. [Medical Codes & Autocoding](#medical-codes--autocoding)
24. [Patient Insights](#patient-insights)
25. [Surveys](#surveys)
26. [Conversational AI & Flow Management](#conversational-ai--flow-management)
27. [Flow Knowledge Indexing](#flow-knowledge-indexing)
28. [Assistant Document Indexing](#assistant-document-indexing)
29. [Vector Chat Endpoint](#vector-chat-endpoint)
30. [Intent Classification](#intent-classification)
31. [Translation Services](#translation-services)
32. [Session Analytics](#session-analytics)
33. [EHR Copilot](#ehr-copilot)
34. [Helper Functions](#helper-functions)
35. [Error Handling](#error-handling)
36. [Twilio Integration with Shared Chat](#twilio-integration-with-shared-chat)
37. [Assistant Management](#assistant-management)

## Overview (Detailed)

The Professional EHR and MedRAG Analysis System is a comprehensive FastAPI-based application designed to manage Electronic Health Records (EHR) and provide advanced medical analysis capabilities. It features robust data management for patients, encounters, medical histories, medications, labs, and scans. The system integrates Large Language Models (LLMs) and vector databases (ChromaDB with LlamaIndex) for intelligent conversational AI, document retrieval, and various analytical tasks within the EHR workflow.

**Key features include:**

- Secure user authentication and organization-based data segregation
- CRUD operations for all major EHR components
- A sophisticated vector-based chat system for patient interaction, driven by dynamic conversation flows
- Indexing capabilities for conversational flows and supplementary medical documents
- AI-driven patient insights and medical code suggestions
- A "Copilot" feature to assist healthcare professionals within the EHR interface
- Bulk data import and PDF report generation

The system is designed to be modular and extensible, leveraging modern Python libraries for backend development, AI integration, and data storage.

## Core Technologies

- **Backend Framework**: FastAPI
- **Database**: SQLite (via SQLAlchemy ORM)
- **Vector Database**: ChromaDB
- **LLM Orchestration**: LlamaIndex
- **LLM Providers**: Google Gemini, OpenAI (configurable)
- **Embedding Models**: HuggingFace Transformers (e.g., BAAI/bge-small-en-v1.5)
- **Authentication**: JWT (JSON Web Tokens) with Passlib for password hashing
- **Cloud Storage**: Google Cloud Storage (GCS) for persisting indices and large files
- **Data Handling**: Pydantic for data validation, Pandas for bulk operations
- **Asynchronous Operations**: asyncio, aiohttp

## Setup and Configuration

### Environment Variables

The application relies on several environment variables for API keys and other configurations. These are typically loaded from a `.env` file:

```env
HUGGINGFACE_API_KEY=your_huggingface_api_key
HUGGINGFACE_ACCESS_TOKEN=your_huggingface_access_token
PERPLEXITY_API_KEY=your_perplexity_api_key
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key
SECRET_KEY=09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

- **HUGGINGFACE_API_KEY**: API key for Hugging Face services
- **HUGGINGFACE_ACCESS_TOKEN**: Access token for Hugging Face Hub
- **PERPLEXITY_API_KEY**: API key for Perplexity AI (used by MedicalLiteratureManager for RAG)
- **GOOGLE_API_KEY**: API key for Google AI services (Gemini)
- **OPENAI_API_KEY**: API key for OpenAI services
- **SECRET_KEY**: A secret key for JWT token generation (e.g., 09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7)
- **ALGORITHM**: JWT signing algorithm (e.g., HS256)
- **ACCESS_TOKEN_EXPIRE_MINUTES**: Duration for access token validity

### Database Setup

- **URL**: `DATABASE_URL = "sqlite:///./ehr_database.db"` (configurable)
- **Engine**: SQLAlchemy create_engine is used
- **Tables**: Defined using SQLAlchemy's declarative base and created via `Base.metadata.create_all(bind=engine)`
- **Session Management**: SessionLocal provides database sessions, managed by the get_db dependency

### Google Cloud Storage (GCS)

- **Credentials**: Loaded from a service account JSON file (e.g., `vermalab-gemini-psom-e3ea-b93f97927cc3.json`)
- **Bucket Name**: `BUCKET_NAME = "circa-ai"` (configurable)
- Used for storing and retrieving flow indices, document indices, and patient scan files

### ChromaDB

- **Client**: `chromadb.PersistentClient(path="./chroma_data")`. Data is persisted locally in the `./chroma_data` directory
- Used as the vector store for LlamaIndex to store embeddings for conversational flows and supplementary documents

### LLM Configuration

- **Default LLM**: Settings.llm is configured to use Google Gemini (`models/gemini-2.0-flash`)
- **Embedding Model**: Settings.embed_model is set to `HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")`
- Multiple LLM models (Gemini, OpenAI) can be configured and selected

## Application Structure

### FastAPI Application

- Initialized as `app = FastAPI(title="Professional EHR and MedRAG Analysis System")`
- Includes CORS (Cross-Origin Resource Sharing) middleware to allow requests from all origins (configurable for production)
- Manages application state for caching indices (`app.state.flow_indices`, `app.state.document_indexes`)

### Database Models

The application uses SQLAlchemy to define its database schema. Key models include:

- **Organization**: Represents a healthcare organization
- **User**: Stores user accounts, including credentials, roles (doctor, staff), organization, and Telephone AI integration tokens
- **UserPatientAccess**: Manages explicit access permissions for users to patient records
- **Patient**: Core patient demographic and administrative information
- **Encounter**: Records of patient visits, including chief complaint, HPI, assessment, plan, and vital signs (stored as JSON)
- **MedicalHistory**: Patient's past and current medical conditions
- **FamilyHistory**: Patient's family medical conditions
- **Medication**: Patient's prescribed and current medications
- **Allergy**: Patient's allergies and reactions
- **LabOrder**: Orders for laboratory tests
- **LabResult**: Results of laboratory tests, linked to LabOrder
- **AIAnalysis**: Stores results of AI-driven analyses performed on patient data (e.g., genetic testing recommendations, diagnosis suggestions)
- **PatientScan**: Metadata for patient imaging scans (e.g., X-rays, ECGs), with file storage handled by GCS
- **MedicalCode**: Stores ICD-10 and CPT codes with descriptions and common terms for autocoding
- **PatientInsights**: Stores AI-generated personalized health insights for patients
- **Survey**: Defines surveys that can be administered
- **SurveyQuestion**: Defines individual questions within a survey, including type and options (stored as JSON)
- **SessionAnalytics**: Stores analytics data for chat sessions, including sentiment, intent, topic, and extracted medical/pregnancy information

### Global Storage

The application uses in-memory dictionaries for caching and status tracking:

- **app.state.flow_indices**: Caches loaded LlamaIndex VectorStoreIndex objects for conversational flows, keyed by flow_id
- **app.state.document_indexes**: Caches loaded LlamaIndex VectorStoreIndex and retriever objects for supplementary documents, keyed by assistant_id
- **index_storage** (deprecated/unused in current context): Potentially for other types of indices
- **processing_status** (deprecated/unused in current context): For tracking long-running processing tasks
- **index_metadata** (deprecated/unused in current context): Metadata for other indices
- **document_index_mapping** (deprecated/unused in current context): Mapping for document indices

## Key Functionalities and API Endpoints

### Authentication

**POST /token**: User login
- **Request**: OAuth2PasswordRequestForm (username, password)
- **Response**: Access token and token type
- Authenticates users against the User table and generates a JWT access token

### Organizations

**POST /api/organizations**: Create a new organization
- **Request Body**: OrganizationCreate model (name)
- **Response**: Organization ID and name

**GET /api/organizations**: Get a list of all organizations
- **Response**: List of organization objects

### Users

**POST /api/users**: Create a new user
- **Request Body**: UserCreate model (username, email, password, full_name, is_doctor, organization_id, role)
- **Response**: User details including ID, username, email, and Telephone AI integration tokens
- Hashes the password. Registers the user with an external "Telephone AI" service asynchronously

**GET /api/users/me**: Get details of the currently authenticated user
- **Response**: User details

### Patients

**POST /api/patients**: Create a new patient record
- **Request Body**: PatientCreate model. Requires first_name, last_name, date_of_birth, gender. organization_id is taken from the current user
- **Response**: Basic patient details and a success message
- Generates a unique MRN. Saves patient data to the database and a JSON file in `./patients/`

**GET /api/patients**: List patients accessible to the current user
- **Response**: List of basic patient details
- Doctors/admins see all patients in their organization; other users see patients based on UserPatientAccess records

**GET /api/patients/{patient_id}**: Get detailed information for a specific patient
- **Response**: Comprehensive patient data including demographics, encounters, medical history, medications, allergies, scans, and lab orders
- Checks user access permissions

**PUT /api/patients/{patient_id}**: Update an existing patient's record
- **Request Body**: PatientUpdate model (allows partial updates)
- **Response**: Basic patient details and a success message
- Checks user access and organization. Updates database and JSON file

**POST /api/patients/bulk**: Create multiple patients from a CSV or Excel file
- **Request**: UploadFile
- **Response**: Summary of total, successful, and failed patient creations, with error details for failures
- Parses the file, validates required columns, and creates patient records

**GET /api/patients/{patient_id}/report**: Download a PDF patient report
- **Query Parameters**: type ("full" or "last" for last encounter)
- **Response**: A StreamingResponse containing the PDF file
- Generates a report using ReportLab, including patient info, encounters, AI analyses, and lab results

#### Public Patient Routes (/api/public/patients):

- **POST /api/public/patients**: Create a patient without authentication (e.g., for external system integration)
- **PUT /api/public/patients/{patient_id}**: Update a patient publicly
- **GET /api/public/patients/{patient_id}**: Get patient details publicly

These routes operate similarly to their authenticated counterparts but do not require a logged-in user.

### Encounters

**POST /api/encounters**: Create a new patient encounter
- **Request Body**: EncounterCreate model
- **Response**: Encounter details and a SOAP clinical note
- Links to the current user as the provider. Stores vital signs as a JSON string. Generates and saves a clinical note

**GET /api/encounters/{encounter_id}**: Get details for a specific encounter
- **Response**: Full encounter details, associated patient info, and a generated SOAP clinical note

**POST /api/encounters/{encounter_id}/autocode**: Generate ICD-10 and CPT codes for an encounter
- **Request Body**: AutocodeRequest model (use_llm, update_encounter)
- **Response**: AutocodeResponse model with suggested codes, entity matches, and reasoning
- Extracts clinical text from the encounter, uses extract_medical_entities and generate_medical_codes (which can use an LLM) to suggest codes. Optionally updates the encounter record

### Medical History, Family History, Medications, Allergies

Standard CRUD operations are available for these linked patient records:

#### Medical History (/api/medical-histories):
- **POST**: Create a medical history entry (MedicalHistoryCreate)
- **PUT /{record_id}**: Update a medical history entry (MedicalHistoryUpdate)
- **DELETE /{record_id}**: Delete a medical history entry

#### Medications (/api/medications):
- **POST**: Create a medication entry (takes a dict, prescriber_id is current user)

#### Allergies (/api/allergies):
- **POST**: Create an allergy entry (takes a dict)
- **PUT /{allergy_id}**: Update an allergy entry
- **DELETE /{allergy_id}**: Delete an allergy entry

(Family History endpoints are defined in models but not explicitly implemented as API routes in the provided code snippet)

### Lab Orders and Results

**POST /api/lab-orders**: Create a new lab order
- **Request Body**: LabOrderCreate model
- **Response**: Lab order details
- Only doctors can create lab orders

**PUT /api/lab-orders/{lab_order_id}**: Update an existing lab order
- **Request Body**: LabOrderUpdate model
- **Response**: Updated lab order details

**GET /api/lab-orders/{lab_order_id}**: Get details for a specific lab order, including its results
- **Response**: Lab order details and associated lab results

**POST /api/lab-results**: Add a result to an existing lab order
- **Request Body**: LabResultCreate model
- **Response**: Lab result details
- Updates the corresponding LabOrder status to "Completed"

### Patient Scans

**POST /api/scans**: Upload a patient scan
- **Request**: Form data (patient_id, scan_type, description, notes, file)
- **Response**: Scan metadata including a GCS signed URL for temporary access
- Uploads the file to GCS under `patient_scans/{patient_id}/{scan_id}/`

**GET /api/patients/{patient_id}/scans**: List all scans for a patient
- **Response**: List of scan metadata, each with a GCS signed URL

**GET /api/scans/{scan_id}**: Get details for a specific scan
- **Response**: Scan metadata with a GCS signed URL

### AI-Powered Analysis (General)

**POST /api/ai_analysis**: Create a new AI analysis record
- **Request Body**: AIAnalysisCreate model (patient_id, encounter_id, analysis_type, input_text, llm_model, scan_ids)
- **Response**: Details of the created AI analysis

This endpoint orchestrates various AI analyses:
- If scan_ids are provided, it downloads scans from GCS and analyzes them using analyze_scan (which can use local Gemma or Qwen API)
- Extracts medical entities from input_text (and scan analyses) using extract_medical_entities
- Retrieves context:
  - For "genetic testing recommendation": Uses MedRAG class (corpus-based retrieval)
  - For "diagnosis suggestion" or "risk assessment": Uses enhanced_literature_retrieval (which uses MedicalLiteratureManager for RAG with Perplexity-sourced articles and ChromaDB)
- Constructs a prompt using the appropriate template (ehr_prompt, diagnosis_prompt, risk_assessment_prompt)
- Sends the prompt to the selected LLM
- Parses the LLM response and stores it in the AIAnalysis table and as a JSON file in `./ehr_records/`

**GET /api/ai_analysis**: List all AI analyses
- **Response**: List of AI analysis records, including patient name

**GET /api/ai_analysis/{analysis_id}**: Get a specific AI analysis by ID
- **Response**: Detailed AI analysis record

**PUT /api/ai_analysis/{analysis_id}/review**: Mark an AI analysis as reviewed by a provider
- **Request**: Form data (review_notes)
- **Response**: Confirmation message. Only doctors can review

### Medical Codes & Autocoding

**GET /api/medical-codes**: Retrieve medical codes (ICD-10, CPT) from the database
- **Query Parameters**: code_type, category, search, limit
- **Response**: List of matching medical codes

The generate_medical_codes function (used by `/api/encounters/{encounter_id}/autocode`) suggests codes by:
- Directly mapping extracted medical entities (from extract_medical_entities) to codes in the MedicalCode table
- Optionally, using an LLM with a structured prompt to generate more codes if initial mapping is insufficient

load_sample_medical_codes populates the MedicalCode table with common codes on application startup if the table is empty.

### Patient Insights

**POST /api/patients/{patient_id}/insights**: Generate new personalized health insights for a patient
- **Response**: List of generated insights
- Gathers patient data (demographics, conditions, medications, allergies, recent vitals, labs)
- Extracts medical entities
- For each insight type ("lifestyle", "medication", "screening", "risk"), it creates a specific prompt and calls an LLM
- Saves generated insights to the PatientInsights table

**GET /api/patients/{patient_id}/insights**: Get existing insights for a patient
- **Response**: List of previously generated insights

### Surveys

**POST /api/surveys**: Create a new survey with questions
- **Request Body**: SurveyCreate model (title, description, category, list of questions)
- **Response**: Created survey details

**GET /api/surveys**: Get all surveys for the current user's organization
- **Response**: List of survey objects

**GET /api/surveys/{survey_id}**: Get a specific survey with its questions
- **Response**: Survey details and its questions

**PUT /api/surveys/{survey_id}**: Update a survey's information and/or questions
- **Request Body**: SurveyUpdate model
- **Response**: Updated survey details. Clears existing questions and adds new ones if questions are provided

**POST /api/surveys/{survey_id}/questions**: Add a new question to an existing survey
- **Request Body**: QuestionCreate model
- **Response**: Updated survey details including the new question

**DELETE /api/surveys/{survey_id}/questions/{question_id}**: Delete a question from a survey
- **Response**: Confirmation message

**POST /api/surveys/{survey_id}/send**: Placeholder to send a survey to recipients
- **Request Body**: recipients (list of strings)
- **Response**: Confirmation message. (Actual sending logic is not implemented)

## Conversational AI & Flow Management

### Flow Knowledge Indexing

**POST /api/index/flow-knowledge**: Creates a vector knowledge base for a given conversational flow
- **Request Body**: A JSON object representing the flow structure (nodes, edges)
- Processes each node (dialogue, script, fieldSetter, response, callTransfer, survey, notification) and its connections
- Generates textual descriptions for each node's behavior, instructions, and transitions
- Creates LlamaIndex Document objects from these descriptions with metadata (node_id, node_type, flow_id)
- Adds global flow processing instructions and node connection summaries as separate documents
- Uses an IngestionPipeline with SentenceSplitter and Settings.embed_model to process and embed these documents
- Stores embeddings in a ChromaDB collection named `flow_{flow_id}_knowledge`
- Persists the LlamaIndex StorageContext locally, then uploads it to GCS under `flow_indices/{flow_id}/`
- Saves metadata about the index (including GCS path and collection name) to a .pkl file in GCS under `flow_metadata/{flow_id}_meta.pkl`
- Caches the loaded index in app.state.flow_indices

**GET /api/flow-index/{flow_id}**: Checks if a flow has been indexed
- **Response**: Indexing status, source (memory/GCS), and metadata

### Assistant Document Indexing

**POST /api/index/assistant-documents**: Indexes supplementary documents for an assistant
- **Request Body**: assistant_id and a list of documents (each with id, name, content)
- Creates LlamaIndex Document objects from the provided content with metadata
- Uses SentenceSplitter and Settings.embed_model for processing
- Stores embeddings in a ChromaDB collection named `documents_{assistant_id}_knowledge`
- Persists the index to GCS under `document_indices/{assistant_id}/` and metadata to `document_metadata/{assistant_id}_meta.pkl`
- Caches the loaded index and retriever in app.state.document_indexes

**GET /api/index/status/{assistant_id}**: Checks the status of document indexing for an assistant
- **Response**: Indexing status and document count from ChromaDB

### Vector Chat Endpoint (/api/shared/vector_chat)

This is the primary endpoint for handling chat messages within a defined conversational flow.

**Request Body:**
- **message**: User's current message
- **sessionId**: Unique ID for the session
- **flow_id**: ID of the conversational flow to use
- **assistantId**: ID of the assistant (used for document retrieval)
- **session_data**: Dictionary holding current session state (e.g., currentNodeId, onboardingStatus)
- **previous_messages**: List of prior messages in the conversation
- **patientId**: ID of the patient
- **patient_history**: Summary of patient's past interactions

#### Core Logic:

**Initialization**: Parses request, gets current date

**Flow Index Loading**:
- Checks app.state.flow_indices cache
- If not cached, downloads index files and metadata from GCS (flow_indices/, flow_metadata/)
- Reconstructs VectorStoreIndex using ChromaDB and load_index_from_storage
- Caches the index

**Patient Onboarding**:
- Retrieves patient record from the database
- Checks for missing required fields (first_name, last_name, date_of_birth)
- If fields are missing:
  - Uses a direct, rule-based approach (no LLM for this part) to ask for the first missing field
  - Parses user's message for the requested information using regex
  - If valid, prepares a database operation to update the patient record
  - Crafts a response asking for the next missing field or confirming completion
  - Updates the onboarding_status_to_send
  - Performs the database update and saves the updated patient record to a JSON file
  - If onboarding completes, it may set current_node_id to the flow's starting node
  - Returns the onboarding-specific response

**Context Building (If Onboarding Complete)**:
- Formats previous_messages into conversation_history
- Handles is_post_survey_start logic (if user just completed survey questions, resets message to "hi" and clears history for the LLM prompt)
- **Starting Node**: If it's a new session (no currentNodeId and no previous_messages), calls get_starting_node(flow_index) to find the initial node
- **Current Node Document**: If current_node_id exists, retrieves its documentation from flow_index using a VectorIndexRetriever with metadata filters for an exact match on node_id. Includes fallback to similarity search if exact match fails
- **Gestational Age Calculation**: If the last assistant message asked for LMP and the current user message is a date, it manually calculates gestational age and trimester. This calculated_gestational_info is added to the LLM prompt

**Document Index Loading & Retrieval**:
- Checks app.state.document_indexes cache for the assistant_id
- If not cached, downloads document index from GCS (document_indices/, document_metadata/)
- Reconstructs VectorStoreIndex and creates a retriever (similarity_top_k=20)
- Caches the index and retriever
- If a document_retriever is available, it retrieves relevant document snippets based on the user's message
- Applies BM25 reranking to the retrieved document nodes for better relevance
- The reranked document text forms the document_context

**LLM Interaction for Flow Navigation & Response Generation**:

*Main Prompt Construction (full_context)*:
- Includes user message, current node ID, current node documentation, current date, conversation history, session data
- Crucially, it instructs the LLM to analyze the user's message against the FUNCTIONS section of the current_node_doc to determine the next_node_id
- The LLM is expected to return a JSON with next_node_id

*First LLM Call (Flow Logic)*: Sends full_context to Settings.llm.complete(). Parses the JSON response to get next_node_id

*Next Node Document Retrieval*: Based on next_node_id, retrieves the documentation for this upcoming node from flow_index (similar to current node retrieval)

*Instruction Extraction*: Extracts the "INSTRUCTION:" text from next_node_doc. This becomes the base ai_response. Checks if next_node_doc has FUNCTIONS to determine next_doc_functions

*Fallback for No Progression*: If current_node_doc has no FUNCTIONS and it's not a survey node or start of conversation, it might generate a fallback response using document_context_section

*Second LLM Call (Rephrasing)*:
- Constructs rephrase_prompt with the ai_response, user message, patient profile, and patient history
- Instructs the LLM to rephrase ai_response naturally, personalize it, and subtly incorporate patient history without changing intent or asking new questions
- Calls Settings.llm.complete() to get the rephrased_response

**Notification Node Handling**:
- If next_node_id corresponds to a "NODE TYPE: notificationNode":
  - Parses notification details (messageType, title, scheduleType, message, surveyQuestions) from next_node_doc
  - Returns a specific response structure for notification nodes, setting next_node_id to None

**Final Response**:
- If next_doc_functions is false (meaning the next node has no further branching logic), next_node_id is set to None to end the flow at that point
- Returns the rephrased_response, final next_node_id, empty state_updates, and onboarding_status_to_send

**Error Handling**: Includes extensive try-except blocks for GCS operations, ChromaDB, LLM calls, and JSON parsing, with fallbacks

### Intent Classification

**POST /api/classify-intent**: Classifies user intent to route to an appropriate assistant/category
- **Request Body**: message, organization_id, current_assistant_id, available_categories
- **Response**: selected_category, assistant_id (null, handled by Node.js), should_switch, confidence
- Constructs a prompt for the LLM to select the best category from available_categories based on the user's message
- If only "default" category is available, skips LLM call
- Validates LLM's selected category against available options

### Translation Services

**POST /api/translate-to-language**: Translates English text to a target language
- **Request Body**: TranslationRequest (text, target_language)
- **Response**: translated_text
- Uses an LLM prompt for translation. Skips if target_language is "en" or text is empty

**POST /api/translate-to-english**: Translates text from any language to English
- **Request Body**: TranslationRequest (text)
- **Response**: original_text, translated_text, detected_language
- First, uses an LLM prompt to detect the language of the input text
- If not English, uses another LLM prompt to translate to English

### Session Analytics

**POST /api/analyze-message**: Analyzes a user message and AI response for session analytics
- **Request Body**: message, response, sessionId, timestamp
- **Response**: Status and analytics data
- Fetches recent conversation history for context
- Constructs a detailed prompt for an LLM to extract:
  - Basic analysis: sentiment, urgency, intent, topic, keywords
  - Medical data: dates (LMP, due date, appointment), symptoms, measurements, medications
  - Pregnancy-specific: trimester indicators (calculated if LMP is asked for and provided), risk factors, fetal activity, emotional state
- Stores the parsed analytics in the SessionAnalytics table

**GET /api/session-analytics**: Get a list of all sessions with summary analytics
- **Response**: List of sessions with message count, start/end times, duration, sentiment distribution, main topic, and pregnancy data flag

**GET /api/session-analytics/{session_id}**: Get detailed analytics for a specific session
- **Response**: Comprehensive analytics including all messages, aggregated stats, and a pregnancy summary (trimester, top symptoms, risk factors, etc.)

**GET /api/export-session-analytics/{session_id}**: Export analytics for a session to an Excel file
- **Response**: StreamingResponse with an Excel file
- Creates an Excel file with sheets for "Conversation Analytics", "Medical Data", and "Pregnancy Data"

**POST /api/analyze-session**: Analyzes a complete session to extract and update patient information in the database
- **Request Body**: sessionId, patientId, previousSessionSummary, previousSessionDate
- **Response**: Status, extracted data, summary of updates, and a session summary
- Fetches all SessionAnalytics for the given session
- Constructs a prompt for an LLM to extract patient details, medical info (conditions, symptoms, medications, allergies, vitals, pregnancy info), and generate a session summary
- Updates the Patient, MedicalHistory, Medication, and Allergy tables based on extracted data and confidence scores. Handles pregnancy and LMP information specifically, creating or updating MedicalHistory records

### EHR Copilot

**POST /api/copilot/query**: Processes a query within the EHR Copilot interface
- **Request Body**: patient_id, encounter_id, current_view, view_mode, query, action
- **Response**: Structured JSON with "answer", "suggestions", "references"
- If action is "detect_disease", it calls the detect_patient_diseases endpoint
- If query suggests disease detection, it also calls detect_patient_diseases
- Otherwise, it calls gather_context_data to get relevant EHR data based on the user's current view
- Constructs a prompt (create_query_prompt if query exists, create_insight_prompt otherwise) for the LLM
- Parses the LLM response using parse_copilot_response

## Helper Functions

- **get_db()**: FastAPI dependency to provide a database session
- **Authentication Helpers** (verify_password, get_password_hash, authenticate_user, create_access_token, get_current_user): Standard functions for password management and JWT-based user authentication
- **user_has_patient_access(db, user_id, patient_id, required_level)**: Checks if a user has the necessary access level to a patient's record, considering organization match and explicit permissions
- **CustomizeSentenceTransformer**: A class that extends SentenceTransformer to load models with CLS pooling if a standard sentence-transformer model isn't found by name
- **load_data_from_frontend_input(...)**: Converts user input (raw text, local file path) into LlamaIndex Document objects
- **build_ingestion_pipeline(...)**: Creates a LlamaIndex IngestionPipeline with SentenceSplitter and the configured embedding model
- **summarize_patient_data(docs)**: Uses an LLM to generate a short summary from a list of documents
- **generate_clinical_note(patient_data, format_type)**: Generates a clinical note (SOAP or narrative) from patient and encounter data
- **generate_mrn()**: Generates a unique Medical Record Number

#### Image Analysis Functions:
- **init_gemma_model**: Initializes a local Gemma model for image analysis if USE_LOCAL_MODEL is true
- **analyze_image_with_qwen_api**: Analyzes an image using the Qwen VL Hugging Face API
- **analyze_image_with_gemma_local**: Analyzes an image using the local Gemma model
- **analyze_scan**: Downloads a scan from GCS and analyzes it using either the local Gemma model or the Qwen API

#### Medical Entity Extraction Functions:
- **init_medical_ner_model**: Initializes a local Medical NER (Named Entity Recognition) model (Clinical-AI-Apollo/Medical-NER)
- **extract_medical_entities**: Extracts medical entities (symptoms, diseases, medications, etc.) from text using the NER model, grouping them by type
- **fetch_web_context_from_perplexity(entity_groups, scan_analyses, analysis_type)**: Fetches relevant web context from Perplexity AI based on extracted entities and scan analyses to augment LLM prompts for diagnosis or risk assessment
- **enhanced_literature_retrieval(entity_groups, analysis_type, scan_analyses)**: Orchestrates literature retrieval using MedicalLiteratureManager (fetches articles via Perplexity, adds to ChromaDB corpus, retrieves relevant chunks for RAG)

#### MedicalLiteratureManager Class:
Manages retrieval, processing, and vector storage (ChromaDB) of medical literature for RAG.
- **retrieve_perplexity_articles()**: Fetches article links from Perplexity AI
- **extract_article_content()**: Extracts content from article URLs using universal_extractor
- **retrieve_medical_articles()**: Orchestrates fetching and content extraction for a given query/entity group
- **add_articles_to_corpus()**: Adds new articles to the ChromaDB vector store, creating embeddings
- **get_relevant_context() / retrieve_relevant_literature() / prepare_literature_context()**: Retrieves and formats context from the vector store for RAG

#### Additional Helper Functions:
- **generate_medical_codes(clinical_text, entity_groups, use_llm)**: Suggests ICD-10 and CPT codes based on clinical text and extracted entities, optionally using an LLM for refinement
- **load_sample_medical_codes(db)**: Populates the MedicalCode table with a predefined set of common codes if the table is empty
- **calculate_age(dob)**: Calculates age from a date of birth string

#### Copilot Helpers:
- **gather_context_data**: Collects relevant data from the EHR based on the user's current view (list or detail) and patient/encounter context
- **create_query_prompt**: Constructs a detailed prompt for the LLM when the user asks a specific question in the Copilot
- **create_insight_prompt**: Constructs a prompt for the LLM to generate proactive insights based on the current EHR context
- **parse_copilot_response**: Parses the LLM's JSON response for the Copilot into a structured dictionary
- **get_starting_node(flow_index)**: Queries a flow index to find the node marked as the starting point of a conversation
- **register_with_telephone_ai(email, password, name, organization_id)**: Asynchronously registers a new user with an external "Telephone AI" service

## Error Handling

The application uses FastAPI's HTTPException for standard HTTP errors. Extensive try-except blocks are used throughout the code, especially in API endpoints and functions interacting with external services (LLMs, GCS, ChromaDB) or performing complex parsing. Logging (logger and print statements) is used to record errors and processing steps. Fallbacks are implemented in some critical paths, for example, in vector_flow_chat if JSON parsing of LLM response fails.

This documentation provides a high-level overview of the system's architecture and functionalities. For specific implementation details, refer to the source code comments and individual function docstrings.

# Twilio Integration with Shared Chat: Voice, WhatsApp & SMS

This document outlines how Twilio communications (Voice, WhatsApp, SMS) are received, processed, and responded to, detailing the interaction between twilioRoutes.js (the Twilio interface) and shared-chat.js (the core conversational logic and TTS provider).

## Core Components:

### twilioRoutes.js:
**Role**: Acts as the primary interface for all incoming and outgoing Twilio communications. It handles webhook requests from Twilio, routes them to the appropriate assistant, manages initial patient/session setup, and forwards messages for processing. For voice calls, it's responsible for generating TwiML to control the call flow.

**Key Functions**:
- Receiving Twilio webhooks for new messages/calls
- Determining communication type (SMS, WhatsApp, Voice)
- Identifying or creating patient and assistant records
- Managing session state (especially for notifications and user-initiated conversations)
- Redirecting requests to assistant-specific handlers
- Interacting with TwilioService for sending replies and controlling calls
- Calling internal or external APIs (including shared-chat.js and a Python backend) for message processing and patient management

### shared-chat.js:
**Role**: Contains the core logic for processing user messages and generating AI or flow-based responses. It also provides Text-To-Speech (TTS) services for voice interactions.

**Key Functions**:
- Receiving messages forwarded from twilioRoutes.js
- Utilizing EnhancedFlowProcessor to manage conversations based on predefined assistant flows (assistant.flowData). This includes handling survey nodes, notification nodes, and other specialized flow steps
- Employing Retrieval Augmented Generation (RAG) by searching vector stores for relevant documents if no flow is active or as a fallback
- Interacting with geminiService (or other LLMs) to generate responses
- Managing multi-language translations
- Saving chat messages and session data to Firestore
- Providing a TTS endpoint (/shared/:shareId/chat/audio) that converts text responses into playable audio for voice calls
- Interacting with a Python backend for advanced tasks like intent classification, vector-based chat, and patient onboarding

### TwilioService.js (Utility Class):
**Role**: Encapsulates direct interactions with the Twilio SDK, such as sending SMS/WhatsApp messages, making outbound calls, and generating TwiML responses. This keeps the route handlers cleaner.

### Python Backend (PYTHON_API_URL):
**Role**: Provides supplementary services like patient creation, advanced intent classification, vector-based chat processing for flows, and message/session analytics.

## Communication Flows:

### 1. WhatsApp & SMS Flow

#### Incoming Message:

**Twilio Webhook**: Twilio sends a webhook to `/api/assistants/twilio/router` in twilioRoutes.js when a new WhatsApp or SMS message arrives.

**Initial Routing (twilioRoutes.js)**:
- determineCommunicationType identifies the message as WhatsApp or SMS
- Phone number is cleaned via cleanPhoneNumber
- determineOrganizationId and getDefaultAssistantId (or logic based on patient_phone_mappings) identify the target assistant. New patients might be created via createPatientViaPython
- Special logic checks if the incoming message is a response to a recent notification (e.g., a survey) using patient_notifications
- The is_user_initiated flag is determined
- The request (with its original body) is redirected (HTTP 307) to an assistant-specific route like `/api/assistants/:assistantId/whatsapp/incoming` or `/api/assistants/:assistantId/sms/incoming`. The is_user_initiated flag is passed as a query parameter

**Assistant-Specific Handling (twilioRoutes.js)**:
- The target route (e.g., `/whatsapp/incoming`) receives the request
- A session is established or retrieved from the chat_sessions collection in Firestore
- patientId is determined from patient_phone_mappings
- **Pregnancy Test Logic**: pregnancy_test_completion function is called. If the pregnancy test flow is active, it handles the interaction and may respond directly or indicate completion
- **Intent Classification** (for user-initiated first messages): If is_user_initiated is true and it's the first message (or second after a "hi"), classifyIntentAndGetAssistant (in shared-chat.js, called via Python API) might be invoked to select a specialized assistant based on the user's message. If an intent switch occurs, the assistantId for the current interaction is updated
- **Doctor Takeover Check**: If the session is marked as takenOverBy a doctor, an acknowledgment message is sent, and AI processing is skipped
- **Message Processing**: The message is then sent for processing. This typically involves an internal HTTP POST request to `/api/shared/:shareId/chat`, which is handled by shared-chat.js

**Chat Logic (shared-chat.js - /shared/:shareId/chat)**:

**Message Reception**: Receives the message, sessionId, patientId, and other relevant data

**Language Handling**: The incoming message is translated to English via the Python API. The detected language is stored in the session to translate the response back

**Survey Handling (Notification-based)**: If the session is linked to a notification with survey questions (checked via sessionData.phoneNumber and recent patient_notifications), handleNotificationSurveyResponse manages the survey interaction

**Flow Processing**:
- If the assistant has flowData and the Python API confirms the flow is indexed, the request is sent to the Python backend's `/api/shared/vector_chat` endpoint. This endpoint uses the flow definition, session state (sessionData), patient history, and previous messages to determine the next step
- The Python backend can trigger notificationNode logic, which is then handled by handleNotificationNode in shared-chat.js to create and potentially send notifications via TwilioService
- Survey nodes within the flow are also managed, potentially by returning the first question of a survey if a survey node is hit

**Fallback/Standard Chat**: If no flow is active or as a fallback, RAG is performed:
- geminiService.generateEmbeddings creates an embedding for the user's message
- vectors.searchVectors queries for relevant documents/instructions
- geminiService.generateSharedResponse (or similar) generates an AI response using the built context

**Response Generation**: The processed response content is prepared

**Message Saving**: Both user and assistant messages are saved to Firestore via saveMessages, which also updates the chat_sessions collection and stores message embeddings in the background

**Language Translation (Outgoing)**: The response content is translated back to the user's preferred language using translateToLanguage (via Python API)

The (potentially translated) response content is returned to the caller (which is twilioRoutes.js)

**Sending Reply (twilioRoutes.js)**:
- The assistant-specific handler (e.g., `/whatsapp/incoming`) receives the response content from shared-chat.js
- TwilioService.sendWhatsAppMessage (or sendSmsMessage) sends the reply to the user via Twilio
- An empty TwiML MessagingResponse is sent back to Twilio to acknowledge the incoming webhook

### 2. Voice Flow

#### Incoming Call:

**Twilio Webhook**: Twilio sends a webhook to `/api/assistants/twilio/router` in twilioRoutes.js when a new call arrives

**Initial Routing (twilioRoutes.js)**:
- Similar to SMS/WhatsApp, it determines the communication type (voice), identifies the assistant, and handles patient/organization mapping
- Redirects (HTTP 307) to `/api/assistants/:assistantId/voice/incoming`

**Call Handling (twilioRoutes.js - /assistants/:assistantId/voice/incoming)**:
- Retrieves assistant details and the primaryShareId (which is the voiceShareId of the assistant)
- Calls twilioService.handleIncomingCall(primaryShareId, From, { patientId }). This service method:
  - Typically fetches an initial greeting. This might involve a call to the chat logic in shared-chat.js to get a dynamic greeting or use a predefined one
  - Generates TwiML:
    - Uses `<Play>` with an audio URL. This URL points to `/api/shared/:shareId/chat/audio` (in shared-chat.js) to stream the TTS for the greeting. The voiceName for TTS is often part of the share link's data
    - Uses `<Gather>` to collect the user's speech. The action attribute of `<Gather>` is set to `/api/assistants/:assistantId/voice/transcription` (or `/api/shared/:shareId/voice/transcription` for direct shared links)
  - Sends this TwiML response to Twilio

#### Speech Transcription & Processing:

**Twilio Webhook (twilioRoutes.js - /voice/transcription)**: After the user speaks, Twilio transcribes the speech and POSTs the SpeechResult to the action URL specified in `<Gather>`

**Transcription Handling**:
- If SpeechResult is empty, an error message (e.g., "I couldn't hear what you said.") is generated. This text is converted to speech by calling `/api/shared/:shareId/chat/audio` (in shared-chat.js). The TwiML plays this audio and re-gathers input
- If speech is present, twilioService.handleTranscription(primaryShareId, sessionId, transcriptionText, callId) is called. This method:
  - Sends the transcriptionText to the chat logic, similar to how WhatsApp/SMS messages are processed. This is usually an internal HTTP POST to `/api/shared/:shareId/chat` (handled by shared-chat.js)

**Chat Logic (shared-chat.js - /shared/:shareId/chat)**:
- Receives the transcribed text
- Processes it using EnhancedFlowProcessor or RAG/LLM as described in the WhatsApp/SMS flow
- Returns the AI/flow-generated text response

**Response Audio Generation (twilioRoutes.js via TwilioService and then shared-chat.js)**:
- The text response from shared-chat.js is received by twilioService.handleTranscription
- This service then makes a GET request to `/api/shared/:shareId/chat/audio` (in shared-chat.js), passing the response text, language, and voiceName to get a streamable TTS audio URL

**TTS Streaming (shared-chat.js - /shared/:shareId/chat/audio)**:
- Receives the text
- Uses @google-cloud/text-to-speech client (via streamTextToSpeech utility) to generate audio and streams it back to the caller (which is the TwiML `<Play>` verb)

**Continuing Conversation (twilioRoutes.js - /voice/transcription)**:
- Constructs new TwiML:
  - `<Play>`s the TTS audio URL of the AI's response
  - `<Gather>`s again for the user's next input, with the action pointing back to the same transcription route to continue the loop
- Sends this TwiML to Twilio

## Summary of Connections:

### twilioRoutes.js -> shared-chat.js (for chat logic):
- **WhatsApp/SMS**: HTTP POST to `/api/shared/:shareId/chat`
- **Voice**: twilioService.handleTranscription internally calls `/api/shared/:shareId/chat` with transcribed text

### twilioRoutes.js -> shared-chat.js (for TTS audio):
- **Voice**: TwiML `<Play>` verb uses URLs like `/api/shared/:shareId/chat/audio` which are handled by shared-chat.js to stream TTS

### Both twilioRoutes.js and shared-chat.js -> Python Backend:
For tasks like patient creation, advanced flow processing (vector_chat), intent classification, translations, and analytics

### Firestore: 
Used extensively by both files for storing/retrieving assistant configurations, chat history, session data, patient mappings, notifications, etc.

### TwilioService: 
Abstracted Twilio SDK calls, used by twilioRoutes.js and potentially by shared-chat.js (e.g., for sending notifications triggered by flows)

This interconnected system allows for a flexible and robust handling of communications across different channels, leveraging Twilio for the transport layer and shared-chat.js for the intelligent processing and response generation, with twilioRoutes.js orchestrating the interactions.

# Assistant Management (assistant.js) Documentation

This document outlines the functionalities provided by assistant.js, which serves as the core backend module for managing AI assistants. It handles their creation, configuration (including knowledge documents, flowcharts, KPIs, and customization), updates, and direct chat interactions.

## Core Responsibilities:

assistant.js is responsible for the entire lifecycle and operational aspects of AI assistants within the platform. Its key duties include:

- **Assistant Lifecycle Management**: Providing API endpoints for creating, retrieving, updating, and deleting assistants
- **Knowledge Base Configuration**: Managing the documents (uploaded files, Google Docs, Google Sheets) that form the knowledge base for each assistant. This includes uploading, processing, extracting text, and triggering indexing for Retrieval Augmented Generation (RAG)
- **Conversational Flow Management**: Handling the flowData object, which defines the structured conversational flows (flowcharts) for assistants. This includes storing the flow and initiating its indexing via a Python backend for optimized execution
- **Customization and Personalization**: Managing assistant-specific settings like avatar, voice (for TTS), biographical information, and professional details
- **KPI (Key Performance Indicator) Configuration**: Allowing the setup and updating of KPI tracking for assistants designated as "representative" type
- **Survey Integration**: Linking assistants to predefined surveys and storing survey data
- **Direct Chat Interaction**: Providing an endpoint (/:assistantId/chat) for users to interact directly with their configured assistants, leveraging their knowledge base and flows
- **Notification Management**: Handling notifications related to assistant activities, such as appointment requests generated during chat interactions

## Key Workflows and Interactions:

### 1. Assistant Creation (POST /)

This endpoint handles the creation of a new AI assistant.

**Data Reception**: Receives assistant metadata (name, description, category, instructions), customization details (bio, expertise, etc.), flowData (JSON representing the flowchart), assistantType (e.g., "representative"), kpiSettings (if applicable), organization_id, and survey_id

**File Handling**:
- Uses multer to handle multipart/form-data, including uploaded files for the knowledge base, an optional avatar image, and an optional voice sample
- Uploaded files (documents, avatar, voice) are temporarily stored, then uploaded to Google Cloud Storage (GCS) under a path specific to the assistant (e.g., assistants/<assistantId>/documents/, assistants/<assistantId>/avatar/)
- Signed URLs are generated for avatar and voice files for frontend access

**Document Processing**:
- **Uploaded Files**: Text is extracted from uploaded documents (PDF, DOCX, TXT, CSV) using libraries like pdf-parse, mammoth, and papaparse
- **Selected Existing Documents**: If selectedDocuments (referring to previously uploaded documents in the user's library) are provided, their content is fetched
- **Google Docs/Sheets Integration**: If Google Docs or Sheets are selected (via selectedDocuments containing Google file IDs), their content is fetched using the Google APIs (googleapis). Helper functions like getGoogleDocContent and getGoogleSheetContent facilitate this

**Flow Data (flowData) Processing**:
- The received flowData JSON is parsed. If it doesn't have an id, the new assistant's ID is assigned as the flowData.id
- This flowData is sent to the Python Backend (PYTHON_API_URL/api/index/flow-knowledge) for indexing. This indexing likely prepares the flow for efficient execution by the EnhancedFlowProcessor or the Python backend itself during chat

**Knowledge Document Indexing**:
- All extracted text content from new uploads, selected documents, and Google Workspace files is compiled
- This collection of documents (ID, name, content) is sent to the Python Backend (PYTHON_API_URL/api/index/assistant-documents) for embedding and indexing into a vector store. This enables RAG capabilities for the assistant
- The assistant's documentCount and documentIds (list of associated document identifiers and metadata) are updated

**Survey Integration**:
- If a survey_id is provided, survey data is fetched from the Python Backend (PYTHON_API_URL/api/surveys/:survey_id) using a JWT token generated by generatePythonToken
- Both survey_id and the fetched survey_data are stored with the assistant

**KPI Configuration**:
- If assistantType is "representative" and kpiSettings are provided, these settings (categories, active KPIs) are parsed and stored in the assistant's kpiConfig

**Firestore Storage**:
- A new assistant document is created in the assistants collection in Firestore
- This document stores all metadata, customization (including avatar/voice URLs), flowData, kpiConfig, survey_id, survey_data, organization_id, documentIds, and initial status
- Uploaded documents (not Google Docs/Sheets) also get individual records in the documents collection in Firestore, linking them to the assistant and user, and storing their GCS storagePath

### 2. Assistant Update (PUT /:id, PUT /:id/flow, PUT /:id/kpi)

These endpoints manage updates to existing assistants.

**PUT /:id (General Update)**:
- Updates basic assistant metadata (name, description, category, instructions)
- Handles changes to the document knowledge base:
  - **Document Deletion**: Documents removed from selectedDocuments are deleted from GCS (if applicable) and their vector embeddings are removed (via vectors.deleteVectors). Their Firestore records in the documents collection are also deleted
  - **Document Addition**: New files uploaded or new Google Docs/Sheets selected are processed similarly to assistant creation (text extraction, embedding, indexing via Python API, GCS storage, Firestore record creation)
  - **Document Re-processing**: Existing selected documents are re-processed to ensure their embeddings are up-to-date if their content might have changed (though direct content update isn't explicitly handled here, re-selecting implies re-processing)
- Updates survey_id and re-fetches/updates survey_data from the Python backend
- The assistant's documentIds and documentCount are updated in Firestore

**PUT /:id/flow (Flow Update)**:
- Specifically updates the flowData for an assistant
- The new flowData is sent to the Python Backend (PYTHON_API_URL/api/index/flow-knowledge) for re-indexing
- The updated flowData is saved to the assistant's document in Firestore

**PUT /:id/kpi (KPI Configuration Update)**:
- Updates the kpiConfig (categories, activeKPIs) for "representative" type assistants
- Saves the updated kpiConfig to Firestore

**PUT /:id/kpi/metrics (KPI Metrics Update)**:
- Allows updating specific metrics within the kpiConfig.metrics field

### 3. Chat Interaction (POST /:assistantId/chat)

This endpoint allows direct chat with a specific assistant, distinct from the shared link chat.

**Authentication**: Protected by verifyToken, ensuring only the assistant's owner can use this endpoint

**Context Building**:
- Retrieves the assistant's instructions from Firestore
- Generates an embedding for the user's message using geminiService
- Performs a vector search (RAG) using vectors.searchVectors against the assistant's indexed documents and workflow_result type vectors (if any, from workflowRoutes.js outputs)
- Fetches previous messages from the chat_messages collection for conversational history
- Constructs a context array including system instructions, relevant vector content, and previous messages

**Calendar Integration**:
- Calls geminiService.handleCalendarQuery to detect if the message relates to calendar operations (scheduling, checking availability)
- If calendar-related, geminiService (which internally might call /api/calendar routes) handles the interaction, potentially creating/modifying events or checking availability. The response from this service is returned directly

**Training Mode**:
- If isTraining is true, the user's message is treated as new knowledge
- geminiService.classifyContent categorizes the message
- The message embedding is stored in the vector store (vectors.storeVectors) with metadata indicating it's a training document
- The assistant's documentCount and trainingStats are updated in Firestore

**Response Generation**:
- If not a calendar query or training, geminiService.generateResponse is called with the built context and user message to generate an AI response
- User-specified preferences like language, tone, responseStyle, complexityLevel, and interactionStyle are passed to geminiService

**Message Storage**:
- Both the user's message and the assistant's response are saved to the chat_messages collection in Firestore, associated with the assistantId and userId
- The assistant's response record includes contextUsed (metadata about the vectors used for RAG)

### 4. Document Management and Previews

**GET /:id/documents/previews**: Fetches a list of documents associated with an assistant, including generating signed GCS URLs for previews of stored files (PDF, DOCX, TXT)

**GET /:id/documents**: Retrieves a comprehensive list of an assistant's documents, including those from GCS and integrated Google Docs/Sheets. It ensures Google Doc/Sheet names are up-to-date by calling getGoogleFileName

**POST /:id/documents**: Adds a new document to an assistant (seems to be a more granular way to add documents post-creation, complementing the main update route)

**DELETE /:id/documents/:docId**: Removes a document from an assistant, deleting it from GCS and Firestore, and updating the assistant's documentIds

### 5. Notification System

**GET /:assistantId/notifications/count**: Returns the count of unread notifications for an assistant

**GET /:assistantId/notifications**: Lists unread notifications for an assistant

**POST /:assistantId/notifications/:notificationId/:action**: Handles actions on notifications (e.g., "approve" or "dismiss")
- If an "appointment_request" notification is approved, it attempts to create a calendar event using Google Calendar APIs (via /api/calendar routes, by making internal HTTP requests or calling shared services). It uses extractEventDetails to parse information from the notification

**POST /notifications**: Creates a new notification for an assistant (likely used internally or by other services)

## Interaction with External Services/Components:

### Firestore (firestore service):
**Primary Datastore**: Stores assistants (metadata, configs, flowData, kpiConfig, survey_data, customization, documentIds), documents (metadata for uploaded files), chat_messages (history for /:assistantId/chat), workflow_instances and workflow_results (read for context in chat), assistant_notifications, and users (for creator data and auth)

### Google Cloud Storage (BUCKET_NAME):
- Stores physical files uploaded by users (documents for knowledge base, avatars, voice samples)
- Accessed via generateSignedUrl for providing temporary read access to files

### Gemini AI (geminiService):
- **generateEmbeddings**: For creating vector representations of text (user messages, document content)
- **generateResponse**: For generating conversational AI responses based on context
- **classifyContent**: For categorizing content during training mode
- **handleCalendarQuery**: For interpreting and acting on calendar-related user requests

### Vector Store (vectors service):
- **storeVectors**: To save document embeddings for RAG
- **searchVectors**: To retrieve relevant document chunks based on user query embeddings
- **deleteVectors**: To remove embeddings when documents are deleted

### Python Backend (PYTHON_API_URL):
- **POST /api/index/flow-knowledge**: Called during assistant creation and flowData updates to index the flowchart for efficient processing
- **POST /api/index/assistant-documents**: Called during assistant creation and document updates to process and index knowledge documents (text extraction, chunking, embedding, and storage in a vector database managed by the Python service)
- **GET /api/surveys/:survey_id**: Fetches detailed survey data when a survey_id is associated with an assistant

### Google APIs (googleapis library):
- **Google Drive API**: Used to list files (Docs, Sheets) from the user's Drive
- **Google Docs API**: Used by getGoogleDocContent to fetch the textual content of a Google Document
- **Google Sheets API**: Used by getGoogleSheetContent to fetch data from a Google Spreadsheet
- Authentication is handled via OAuth 2.0, with tokens stored in the user's Firestore document

### Additional Libraries and Services:
- **Multer**: Middleware for handling multipart/form-data file uploads in Express.js
- **Axios**: Used for making HTTP requests to the Python backend and potentially internal API calls
- **Chrono-node, Luxon**: Used for date/time parsing and manipulation, especially in calendar-related functionalities
- **jsonwebtoken (jwt)**: Used by generatePythonToken to create JWTs for secure communication with the Python backend

## Security and Authorization:

**verifyToken Middleware**: Most routes are protected by this middleware, ensuring that the user making the request is authenticated via a JWT. The user's ID (req.user.id) is made available to the route handlers

**Ownership Checks**: For operations like updating or deleting an assistant, or accessing its sensitive data (like chat history or notifications), the system verifies that assistant.userId matches req.user.id

**Signed URLs**: GCS signed URLs are used to provide time-limited, secure access to stored files like avatars and document previews, rather than making them publicly readable

This comprehensive system allows users to create, customize, and manage powerful AI assistants with diverse knowledge sources and conversational capabilities.

## 🚀 Installation & Setup

### Prerequisites

- Node.js >= 16.0.0
- Python >= 3.8
- Google Cloud Platform account
- Twilio account
- HuggingFace account (for embeddings)
- OpenAI API key (optional)
- Perplexity API key

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/circa-rag-system.git
cd circa-rag-system
```

### 2. Environment Setup

Create a `.env` file in the root directory with all the required environment variables as specified in the Environment Variables section above.

### 3. Python Backend Setup
```bash
# Navigate to Python backend directory
cd python-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python init_db.py

# Start FastAPI server
uvicorn main:app --reload --port 8000
```

### 4. Node.js Backend Setup
```bash
# Navigate to Node.js backend directory
cd nodejs-backend

# Install dependencies
npm install

# Start the server
npm run dev
```

### 5. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

## 📊 Database Models & Schema

All database models are defined using SQLAlchemy ORM with comprehensive relationships and constraints as detailed in the Database Models section above.

## 🔧 Testing

### Python Backend Tests
```bash
cd python-backend
pytest tests/ -v
```

### Node.js Backend Tests
```bash
cd nodejs-backend
npm test
```

## 🚀 Deployment

Follow production deployment guidelines with proper security configurations, HTTPS setup, and cloud infrastructure scaling.

## 📞 Support

For comprehensive support, refer to the complete documentation sections above covering every aspect of the CIRCA RAG system architecture, implementation, and functionality.
