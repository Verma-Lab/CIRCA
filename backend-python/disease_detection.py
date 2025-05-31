import json
import os
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
import numpy as np

# LLM-related imports
from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
from llama_index.llms.openai import OpenAI
from main import extract_medical_entities, enhanced_literature_retrieval, MedicalLiteratureManager


# Import constants and models from the main application
GOOGLE_API_KEY = "AIzaSyAq-ZOzYNYGjtZB1SlJVSDXMVd-CQldubE"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-openai-api-key-here")

# Configure LLMs
llm = Gemini(
    model="models/gemini-1.5-flash",
    api_key=GOOGLE_API_KEY,
)
# openai_llm = OpenAI(model="gpt-3.5-turbo", api_key=OPENAI_API_KEY, logprobs=False, default_headers={})
Settings.llm = llm



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
        for filename in os.listdir(self.diagnosis_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.diagnosis_dir, filename), 'r') as f:
                        disease_def = json.load(f)
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
            if code in self.corpus:
                relevant_diseases.append(self.corpus[code])
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

# # Example usage
# if __name__ == "__main__":
#     # Initialize system
#     disease_detection = DiseaseDetectionSystem()
    
#     # Sample patient data (simplified for testing)
#     sample_patient = {
#         "id": "P12345",
#         "first_name": "John",
#         "last_name": "Doe",
#         "date_of_birth": "1965-08-15",
#         "gender": "Male",
#         "encounter": {
#             "chief_complaint": "Shortness of breath and swelling in legs",
#             "hpi": "65-year-old male with history of hypertension and previous MI presenting with progressive dyspnea on exertion and lower extremity edema for the past 2 weeks. Reports orthopnea requiring 3 pillows to sleep.",
#             "vital_signs": {
#                 "temperature": 37.2,
#                 "heart_rate": 105,
#                 "blood_pressure_systolic": 145,
#                 "blood_pressure_diastolic": 92,
#                 "respiratory_rate": 24,
#                 "oxygen_saturation": 92
#             },
#             "physical_exam": "Jugular venous distention noted. Bilateral crackles in lung bases. 2+ pitting edema in bilateral lower extremities. S3 gallop present.",
#             "assessment": "Patient presenting with signs and symptoms consistent with heart failure exacerbation."
#         },
#         "medical_history": [
#             {"condition": "Hypertension", "status": "Active"},
#             {"condition": "Myocardial Infarction", "status": "Resolved"},
#             {"condition": "Hyperlipidemia", "status": "Active"}
#         ],
#         "medications": [
#             {"name": "Lisinopril", "dosage": "20mg", "frequency": "daily"},
#             {"name": "Atorvastatin", "dosage": "40mg", "frequency": "daily"},
#             {"name": "Aspirin", "dosage": "81mg", "frequency": "daily"}
#         ],
#         "lab_results": [
#             {"test_name": "BNP", "result_value": "750", "unit": "pg/mL", "reference_range": "<100", "abnormal_flag": "High"},
#             {"test_name": "Troponin", "result_value": "0.02", "unit": "ng/mL", "reference_range": "<0.04", "abnormal_flag": "Normal"},
#             {"test_name": "Creatinine", "result_value": "1.3", "unit": "mg/dL", "reference_range": "0.7-1.2", "abnormal_flag": "High"}
#         ],
#         "scans": [
#             {
#                 "scan_type": "Chest X-ray",
#                 "analysis": "Cardiomegaly and pulmonary vascular congestion. No infiltrates or effusions."
#             }
#         ]
#     }
    
#     # Analyze patient
#     result = disease_detection.analyze_patient(sample_patient)
    
#     # Print result
#     print(json.dumps(result, indent=2))